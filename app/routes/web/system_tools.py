from datetime import datetime
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.auth import require_permission
from app.config import DATA_DIR, DEFAULT_DB_PATH, DATABASE_URL
from app.db.session import SessionLocal, engine, get_db, is_sqlite

router = APIRouter(prefix='/system', tags=['system'])
templates = Jinja2Templates(directory='app/templates')
BACKUP_DIR = DATA_DIR / 'backups'
BACKUP_DIR.mkdir(parents=True, exist_ok=True)


def _db_path() -> Path:
    return DEFAULT_DB_PATH


def _get_db_display() -> str:
    """Returns a sanitized DB string for UI display."""
    if is_sqlite:
        return str(DEFAULT_DB_PATH)
    
    # Sanitize Postgres URL: postgresql://user:pass@host:port/dbname -> postgresql://user@host:port/dbname
    from urllib.parse import urlparse
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


def _list_backups():
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(BACKUP_DIR.glob('it_asset_hub_backup_*.db'), key=lambda p: p.stat().st_mtime, reverse=True)
    result = []
    for item in files:
        stat = item.stat()
        result.append({'name': item.name, 'path': str(item), 'size': stat.st_size, 'modified_at': datetime.fromtimestamp(stat.st_mtime)})
    return result


@router.get('/', response_class=HTMLResponse)
@require_permission('can_manage_system')
def system_index(request: Request, current_user=None):
    return templates.TemplateResponse('system/index.html', {
        'request': request, 
        'current_user': current_user,
        'is_sqlite': is_sqlite,
        'db_display': _get_db_display()
    })


@router.get('/backups', response_class=HTMLResponse)
@require_permission('can_manage_system')
def backup_list(request: Request, current_user=None, error: str | None = Query(default=None)):
    backups = _list_backups() if is_sqlite else []
    return templates.TemplateResponse('system/backups.html', {
        'request': request, 
        'current_user': current_user, 
        'backups': backups, 
        'db_path': _get_db_display(),
        'is_sqlite': is_sqlite,
        'error': error
    })


@router.post('/backup')
@require_permission('can_manage_system')
def backup_create(request: Request, current_user=None):
    if not is_sqlite:
        # PostgreSQL backups should be handled externally (pg_dump, RDS snapshots, etc.)
        return RedirectResponse(url='/system/backups?error=PostgreSQL+backups+must+be+handled+externally', status_code=303)
    db_file = _db_path()
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = BACKUP_DIR / f'it_asset_hub_backup_{timestamp}.db'
    SessionLocal.close_all()
    engine.dispose()
    shutil.copy2(db_file, backup_file)
    return RedirectResponse(url='/system/backups', status_code=303)


@router.get('/backups/{backup_name}/download')
@require_permission('can_manage_system')
def backup_download(backup_name: str, request: Request, current_user=None):
    if not is_sqlite:
         return RedirectResponse(url='/system/backups', status_code=303)
         
    # Security: Validate filename against existing backups to prevent path traversal
    valid_backups = [b['name'] for b in _list_backups()]
    if backup_name not in valid_backups:
        return RedirectResponse(url='/system/backups?error=Invalid+backup+file', status_code=303)
        
    file_path = BACKUP_DIR / backup_name
    if not file_path.exists():
        return RedirectResponse(url='/system/backups', status_code=303)
    return FileResponse(
        path=file_path,
        media_type='application/octet-stream',
        filename=backup_name
    )


@router.get('/restore', response_class=HTMLResponse)
@require_permission('can_manage_system')
def restore_page(request: Request, current_user=None):
    backups = _list_backups() if is_sqlite else []
    return templates.TemplateResponse('system/restore.html', {
        'request': request, 
        'current_user': current_user, 
        'backups': backups, 
        'db_path': _get_db_display(),
        'error': None,
        'is_sqlite': is_sqlite
    })


@router.post('/restore', response_class=HTMLResponse)
@require_permission('can_manage_system')
def restore_submit(request: Request, backup_name: str = Form(...), confirm_text: str = Form(...), current_user=None):
    backups = _list_backups()
    if not is_sqlite:
        return templates.TemplateResponse('system/restore.html', {'request': request, 'current_user': current_user, 'backups': backups, 'error': 'Tiến trình Restore chỉ hỗ trợ SQLite. Với PostgreSQL, vui lòng sử dụng lệnh psql.'})
    if confirm_text.strip().upper() != 'RESTORE':
        return templates.TemplateResponse('system/restore.html', {'request': request, 'current_user': current_user, 'backups': backups, 'error': 'Phải nhập đúng chữ RESTORE để xác nhận.'})
    backup_file = BACKUP_DIR / backup_name
    if not backup_file.exists():
        return templates.TemplateResponse('system/restore.html', {'request': request, 'current_user': current_user, 'backups': backups, 'error': 'Không tìm thấy file backup đã chọn.'})
    db_file = _db_path()
    safety_backup = BACKUP_DIR / f'it_asset_hub_backup_before_restore_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db'
    SessionLocal.close_all()
    engine.dispose()
    if db_file.exists():
        shutil.copy2(db_file, safety_backup)
    shutil.copy2(backup_file, db_file)
    return RedirectResponse(url='/system/backups', status_code=303)
