import json
import os
import shutil
import subprocess
from datetime import datetime, date
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlparse

from fastapi import APIRouter, Form, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import inspect as sa_inspect, text

from app.auth import require_permission
from app.config import DATA_DIR, DEFAULT_DB_PATH, DATABASE_URL
from app.db.session import SessionLocal, engine, is_sqlite

router = APIRouter(prefix='/system', tags=['system'])
templates = Jinja2Templates(directory='app/templates')
BACKUP_DIR = DATA_DIR / 'backups'
BACKUP_DIR.mkdir(parents=True, exist_ok=True)


def _db_path() -> Path:
    return DEFAULT_DB_PATH


def _get_db_display() -> str:
    if is_sqlite:
        return str(DEFAULT_DB_PATH)
    try:
        parsed = urlparse(DATABASE_URL)
        netloc = parsed.hostname
        if parsed.port:
            netloc = f"{netloc}:{parsed.port}"
        if parsed.username:
            netloc = f"{parsed.username}@{netloc}"
        return f"{parsed.scheme}://{netloc}{parsed.path}"
    except Exception:
        return "PostgreSQL Database"


def _parse_pg_params() -> dict:
    parsed = urlparse(DATABASE_URL)
    return {
        'host': parsed.hostname or 'localhost',
        'port': str(parsed.port or 5432),
        'user': parsed.username or 'postgres',
        'password': parsed.password or '',
        'dbname': parsed.path.lstrip('/'),
    }


class _JsonEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if isinstance(obj, Decimal):
            return str(obj)
        if isinstance(obj, bytes):
            return obj.hex()
        return super().default(obj)


def _list_backups():
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    if is_sqlite:
        patterns = ['it_asset_hub_backup_*.db']
    else:
        patterns = ['it_asset_hub_backup_*.json', 'it_asset_hub_backup_*.sql']
    files = []
    for pattern in patterns:
        files.extend(BACKUP_DIR.glob(pattern))
    files = sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)
    result = []
    for item in files:
        stat = item.stat()
        suffix = item.suffix.lstrip('.')
        result.append({
            'name': item.name,
            'path': str(item),
            'size': stat.st_size,
            'modified_at': datetime.fromtimestamp(stat.st_mtime),
            'format': suffix.upper(),
        })
    return result


# ── JSON backup (SQLAlchemy thuần Python) ────────────────────────────────────

def _backup_pg_json(backup_file: Path) -> tuple[bool, str]:
    try:
        inspector = sa_inspect(engine)
        table_names = inspector.get_table_names()
        tables_data: dict[str, list] = {}
        with engine.connect() as conn:
            for table in table_names:
                result = conn.execute(text(f'SELECT * FROM "{table}"'))
                cols = list(result.keys())
                tables_data[table] = [dict(zip(cols, row)) for row in result.fetchall()]
        payload = {
            'version': 1,
            'created_at': datetime.now().isoformat(),
            'db_url': _get_db_display(),
            'tables': tables_data,
        }
        backup_file.write_text(
            json.dumps(payload, ensure_ascii=False, cls=_JsonEncoder),
            encoding='utf-8'
        )
        return True, ''
    except Exception as e:
        return False, str(e)


def _restore_pg_json(backup_file: Path) -> tuple[bool, str]:
    try:
        payload = json.loads(backup_file.read_text(encoding='utf-8'))
        tables_data: dict = payload.get('tables', payload)
        with engine.begin() as conn:
            conn.execute(text("SET session_replication_role = 'replica'"))
            for table in reversed(list(tables_data.keys())):
                conn.execute(text(f'TRUNCATE TABLE "{table}" RESTART IDENTITY CASCADE'))
            for table, rows in tables_data.items():
                if not rows:
                    continue
                cols = list(rows[0].keys())
                col_str = ', '.join(f'"{c}"' for c in cols)
                ph_str = ', '.join(f':{c}' for c in cols)
                stmt = text(f'INSERT INTO "{table}" ({col_str}) VALUES ({ph_str})')
                for row in rows:
                    conn.execute(stmt, row)
            for table in tables_data.keys():
                try:
                    conn.execute(text(
                        f"SELECT setval(pg_get_serial_sequence('\"{table}\"', 'id'), "
                        f"COALESCE((SELECT MAX(id) FROM \"{table}\"), 0) + 1, false)"
                    ))
                except Exception:
                    pass
            conn.execute(text("SET session_replication_role = 'DEFAULT'"))
        return True, ''
    except Exception as e:
        return False, str(e)


# ── SQL backup (pg_dump / psql) ───────────────────────────────────────────────

def _backup_pg_sql(backup_file: Path) -> tuple[bool, str]:
    params = _parse_pg_params()
    env = os.environ.copy()
    env['PGPASSWORD'] = params['password']
    try:
        result = subprocess.run(
            ['pg_dump', '-h', params['host'], '-p', params['port'],
             '-U', params['user'], '-d', params['dbname'], '-f', str(backup_file)],
            env=env, capture_output=True, text=True, timeout=300
        )
        if result.returncode != 0:
            return False, result.stderr.strip() or 'pg_dump thất bại'
        return True, ''
    except FileNotFoundError:
        return False, 'Không tìm thấy lệnh pg_dump. Hãy cài PostgreSQL client tools trên server.'
    except subprocess.TimeoutExpired:
        return False, 'pg_dump timeout sau 300 giây.'
    except Exception as e:
        return False, str(e)


def _restore_pg_sql(backup_file: Path) -> tuple[bool, str]:
    params = _parse_pg_params()
    env = os.environ.copy()
    env['PGPASSWORD'] = params['password']
    try:
        result = subprocess.run(
            ['psql', '-h', params['host'], '-p', params['port'],
             '-U', params['user'], '-d', params['dbname'], '-f', str(backup_file)],
            env=env, capture_output=True, text=True, timeout=600
        )
        if result.returncode != 0:
            return False, result.stderr.strip() or 'psql restore thất bại'
        return True, ''
    except FileNotFoundError:
        return False, 'Không tìm thấy lệnh psql. Hãy cài PostgreSQL client tools trên server.'
    except subprocess.TimeoutExpired:
        return False, 'psql timeout sau 600 giây.'
    except Exception as e:
        return False, str(e)


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get('/', response_class=HTMLResponse)
@require_permission('can_manage_system')
def system_index(request: Request, current_user=None):
    return templates.TemplateResponse('system/index.html', {
        'request': request,
        'current_user': current_user,
        'is_sqlite': is_sqlite,
        'db_display': _get_db_display(),
    })


@router.get('/backups', response_class=HTMLResponse)
@require_permission('can_manage_system')
def backup_list(request: Request, current_user=None,
                error: str | None = Query(default=None),
                success: str | None = Query(default=None)):
    backups = _list_backups()
    return templates.TemplateResponse('system/backups.html', {
        'request': request,
        'current_user': current_user,
        'backups': backups,
        'db_path': _get_db_display(),
        'is_sqlite': is_sqlite,
        'error': error,
        'success': success,
    })


@router.post('/backup')
@require_permission('can_manage_system')
def backup_create(request: Request, current_user=None):
    """Backup JSON (SQLAlchemy thuần Python)."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    if is_sqlite:
        db_file = _db_path()
        backup_file = BACKUP_DIR / f'it_asset_hub_backup_{timestamp}.db'
        SessionLocal.close_all()
        engine.dispose()
        shutil.copy2(db_file, backup_file)
    else:
        backup_file = BACKUP_DIR / f'it_asset_hub_backup_{timestamp}.json'
        ok, err = _backup_pg_json(backup_file)
        if not ok:
            if backup_file.exists():
                backup_file.unlink()
            return RedirectResponse(url=f'/system/backups?error={err}', status_code=303)
    return RedirectResponse(url='/system/backups?success=backup_created', status_code=303)


@router.post('/backup-sql')
@require_permission('can_manage_system')
def backup_create_sql(request: Request, current_user=None):
    """Backup SQL dùng pg_dump (cần PostgreSQL client tools)."""
    if is_sqlite:
        return RedirectResponse(url='/system/backups?error=Chỉ hỗ trợ PostgreSQL', status_code=303)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = BACKUP_DIR / f'it_asset_hub_backup_{timestamp}.sql'
    ok, err = _backup_pg_sql(backup_file)
    if not ok:
        if backup_file.exists():
            backup_file.unlink()
        return RedirectResponse(url=f'/system/backups?error={err}', status_code=303)
    return RedirectResponse(url='/system/backups?success=backup_created', status_code=303)


@router.get('/backups/{backup_name}/download')
@require_permission('can_manage_system')
def backup_download(backup_name: str, request: Request, current_user=None):
    valid_backups = [b['name'] for b in _list_backups()]
    if backup_name not in valid_backups:
        return RedirectResponse(url='/system/backups?error=Invalid+backup+file', status_code=303)
    file_path = BACKUP_DIR / backup_name
    if not file_path.exists():
        return RedirectResponse(url='/system/backups', status_code=303)
    if backup_name.endswith('.db'):
        media_type = 'application/octet-stream'
    elif backup_name.endswith('.sql'):
        media_type = 'text/plain'
    else:
        media_type = 'application/json'
    return FileResponse(path=file_path, media_type=media_type, filename=backup_name)


@router.get('/restore', response_class=HTMLResponse)
@require_permission('can_manage_system')
def restore_page(request: Request, current_user=None):
    backups = _list_backups()
    return templates.TemplateResponse('system/restore.html', {
        'request': request,
        'current_user': current_user,
        'backups': backups,
        'db_path': _get_db_display(),
        'error': None,
        'is_sqlite': is_sqlite,
    })


@router.post('/restore', response_class=HTMLResponse)
@require_permission('can_manage_system')
def restore_submit(request: Request, backup_name: str = Form(...),
                   confirm_text: str = Form(...), current_user=None):
    backups = _list_backups()
    ctx = {
        'request': request,
        'current_user': current_user,
        'backups': backups,
        'db_path': _get_db_display(),
        'is_sqlite': is_sqlite,
    }

    if confirm_text.strip().upper() != 'RESTORE':
        return templates.TemplateResponse('system/restore.html',
                                          {**ctx, 'error': 'Phải nhập đúng chữ RESTORE để xác nhận.'})

    backup_file = BACKUP_DIR / backup_name
    if not backup_file.exists():
        return templates.TemplateResponse('system/restore.html',
                                          {**ctx, 'error': 'Không tìm thấy file backup đã chọn.'})

    if is_sqlite:
        db_file = _db_path()
        safety = BACKUP_DIR / f'it_asset_hub_backup_before_restore_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db'
        SessionLocal.close_all()
        engine.dispose()
        if db_file.exists():
            shutil.copy2(db_file, safety)
        shutil.copy2(backup_file, db_file)
    elif backup_name.endswith('.json'):
        ok, err = _restore_pg_json(backup_file)
        if not ok:
            return templates.TemplateResponse('system/restore.html',
                                              {**ctx, 'error': f'Restore thất bại: {err}'})
    elif backup_name.endswith('.sql'):
        ok, err = _restore_pg_sql(backup_file)
        if not ok:
            return templates.TemplateResponse('system/restore.html',
                                              {**ctx, 'error': f'Restore thất bại: {err}'})
    else:
        return templates.TemplateResponse('system/restore.html',
                                          {**ctx, 'error': 'Định dạng file backup không được hỗ trợ.'})

    return RedirectResponse(url='/system/backups?success=restore_done', status_code=303)
