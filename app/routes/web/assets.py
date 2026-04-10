from dataclasses import asdict, dataclass
from typing import Any
from datetime import datetime
import base64
import io
import json

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response, StreamingResponse
from fastapi.templating import Jinja2Templates
import openpyxl
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.auth import has_permission, require_module_access, require_permission
from app.db.models import Asset, AssetAssignment, AssetEvent, User
from app.db.session import get_db

router = APIRouter(prefix='/assets', tags=['assets'])
templates = Jinja2Templates(directory='app/templates')
DATE_FMT = '%Y-%m-%d'
ASSET_STATUSES = ['active', 'in_repair', 'inactive', 'retired', 'lost', 'disposed']
IMPORT_HEADERS = [
    'Mã thiết bị',
    'Tên thiết bị',
    'Loại thiết bị',
    'Model',
    'Serial',
    'IP',
    'Bộ phận',
    'Người dùng',
    'Vị trí',
    'Ngày mua',
    'Hết bảo hành',
    'Trạng thái',
    'Ghi chú',
]
REQUIRED_IMPORT_HEADERS = ['Mã thiết bị', 'Tên thiết bị', 'Loại thiết bị']


@dataclass
class AssetImportDTO:
    asset_code: str
    asset_name: str
    asset_type: str
    model: str | None = None
    serial_number: str | None = None
    ip_address: str | None = None
    department: str | None = None
    assigned_user: str | None = None
    location: str | None = None
    purchase_date: str | None = None
    warranty_expiry: str | None = None
    status: str = 'active'
    notes: str | None = None

    @classmethod
    def from_row(cls, row_map: dict[str, str]):
        return cls(
            asset_code=row_map.get('Mã thiết bị', '').strip(),
            asset_name=row_map.get('Tên thiết bị', '').strip(),
            asset_type=row_map.get('Loại thiết bị', '').strip(),
            model=row_map.get('Model', '').strip() or None,
            serial_number=row_map.get('Serial', '').strip() or None,
            ip_address=row_map.get('IP', '').strip() or None,
            department=row_map.get('Bộ phận', '').strip() or None,
            assigned_user=row_map.get('Người dùng', '').strip() or None,
            location=row_map.get('Vị trí', '').strip() or None,
            purchase_date=row_map.get('Ngày mua', '').strip() or None,
            warranty_expiry=row_map.get('Hết bảo hành', '').strip() or None,
            status=_normalize_status(row_map.get('Trạng thái', '').strip() or 'active'),
            notes=row_map.get('Ghi chú', '').strip() or None,
        )


def _render_form(request: Request, asset: Asset | None = None, error: str | None = None, current_user=None):
    return templates.TemplateResponse('assets/form.html', {'request': request, 'asset': asset, 'error': error, 'current_user': current_user})


def _render_import_page(request: Request, *, error: str | None = None, summary: dict | None = None, preview: dict | None = None, current_user=None):
    return templates.TemplateResponse(
        'assets/import.html',
        {
            'request': request,
            'error': error,
            'summary': summary,
            'preview': preview,
            'current_user': current_user,
            'required_headers': REQUIRED_IMPORT_HEADERS,
            'all_headers': IMPORT_HEADERS,
        },
    )


def _parse_date(value: str | None):
    value = (value or '').strip()
    if not value:
        return None
    try:
        return datetime.strptime(value, DATE_FMT).date()
    except ValueError:
        return None


def _days_to_warranty(asset: Asset):
    expiry = _parse_date(asset.warranty_expiry)
    if not expiry:
        return None
    return (expiry - datetime.utcnow().date()).days


def _log_event(db: Session, asset_id: int, event_type: str, title: str, description: str | None = None, actor: str | None = None):
    db.add(AssetEvent(asset_id=asset_id, event_type=event_type, title=title, description=description, actor=actor))


def _normalize_text(value):
    if value is None:
        return ''
    if isinstance(value, datetime):
        return value.strftime(DATE_FMT)
    return str(value).strip()


def _normalize_status(value: str | None) -> str:
    raw = (value or '').strip().lower()
    aliases = {
        'repair': 'in_repair',
        'in-repair': 'in_repair',
        'in repair': 'in_repair',
        'broken': 'inactive',
        'archive': 'retired',
        'archived': 'retired',
    }
    normalized = aliases.get(raw, raw or 'active')
    return normalized if normalized in ASSET_STATUSES else 'active'


def _filtered_assets(db: Session, q: str | None = None, asset_type: str | None = None, department: str | None = None, status: str | None = None, warranty: str | None = None, filter: str | None = None):
    stmt = select(Asset)
    if q:
        like = f'%{q.strip()}%'
        stmt = stmt.where(or_(Asset.asset_code.ilike(like), Asset.asset_name.ilike(like), Asset.ip_address.ilike(like), Asset.assigned_user.ilike(like), Asset.serial_number.ilike(like)))
    if asset_type:
        stmt = stmt.where(Asset.asset_type == asset_type)
    else:
        # Tách biệt hoàn toàn: Loại bỏ Camera khỏi module Tài sản (quản lý riêng bên menu Checklist)
        stmt = stmt.where(Asset.asset_type != "Camera")
    if department:
        stmt = stmt.where(Asset.department == department)
    if status:
        stmt = stmt.where(Asset.status == status)
    if filter == 'missing_info':
        stmt = stmt.where(or_(Asset.serial_number.is_(None), Asset.serial_number == "", Asset.location.is_(None), Asset.location == ""))
    assets = db.scalars(stmt.order_by(Asset.asset_code.asc())).all()
    if warranty == 'expired':
        assets = [a for a in assets if (_days_to_warranty(a) is not None and _days_to_warranty(a) < 0)]
    elif warranty == 'expiring_30':
        assets = [a for a in assets if (_days_to_warranty(a) is not None and 0 <= _days_to_warranty(a) <= 30)]
    elif warranty == 'expiring_90':
        assets = [a for a in assets if (_days_to_warranty(a) is not None and 0 <= _days_to_warranty(a) <= 90)]
    return assets


def _load_import_rows(file_bytes: bytes):
    wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        raise ValueError('File import đang rỗng.')

    headers = [_normalize_text(value) for value in rows[0]]
    missing_headers = [name for name in REQUIRED_IMPORT_HEADERS if name not in headers]
    if missing_headers:
        raise ValueError(f'Thiếu cột bắt buộc: {", ".join(missing_headers)}')

    dtos = []
    for index, row in enumerate(rows[1:], start=2):
        row_map = {}
        has_data = False
        for header, cell in zip(headers, row):
            if not header:
                continue
            value = _normalize_text(cell)
            if value:
                has_data = True
            row_map[header] = value
        if not has_data:
            continue
        dtos.append((index, AssetImportDTO.from_row(row_map)))
    return dtos


def _preview_token_from_rows(rows: list[tuple[int, AssetImportDTO]], filename: str):
    payload = {'filename': filename, 'rows': [(idx, asdict(dto)) for idx, dto in rows]}
    return base64.urlsafe_b64encode(json.dumps(payload, ensure_ascii=False).encode('utf-8')).decode('ascii')


def _rows_from_preview_token(token: str):
    decoded = base64.urlsafe_b64decode(token.encode('ascii'))
    payload = json.loads(decoded.decode('utf-8'))
    return [(int(item[0]), AssetImportDTO(**item[1])) for item in payload['rows']], payload.get('filename', 'import.xlsx')


def _build_import_preview(rows: list[tuple[int, AssetImportDTO]], db: Session, filename: str):
    created = 0
    updated = 0
    skipped: list[str] = []
    sample_rows = []
    for row_number, dto in rows:
        if not dto.asset_code or not dto.asset_name or not dto.asset_type:
            skipped.append(f'Dòng {row_number}: thiếu Mã thiết bị / Tên thiết bị / Loại thiết bị')
            sample_rows.append({'row_number': row_number, 'asset_code': dto.asset_code, 'asset_name': dto.asset_name, 'asset_type': dto.asset_type, 'action': 'skip'})
            continue
        asset = db.scalar(select(Asset).where(Asset.asset_code == dto.asset_code))
        action = 'update' if asset else 'create'
        if action == 'create':
            created += 1
        else:
            updated += 1
        if len(sample_rows) < 20:
            sample_rows.append({'row_number': row_number, 'asset_code': dto.asset_code, 'asset_name': dto.asset_name, 'asset_type': dto.asset_type, 'action': action})
    return {
        'filename': filename,
        'created': created,
        'updated': updated,
        'skipped': skipped[:30],
        'total_rows': len(rows),
        'sample_rows': sample_rows,
        'token': _preview_token_from_rows(rows, filename),
    }


def _apply_assignment_change(db: Session, asset: Asset, new_user: str | None, actor: str | None, source: str):
    previous_user = asset.assigned_user
    now_dt = datetime.utcnow()
    now_str = now_dt.strftime('%Y-%m-%d %H:%M')
    if previous_user == new_user:
        return
    if previous_user:
        current_assignment = db.scalar(
            select(AssetAssignment)
            .where(AssetAssignment.asset_id == asset.id, AssetAssignment.status == 'assigned')
            .order_by(AssetAssignment.assigned_at.desc())
        )
        if current_assignment:
            current_assignment.status = 'returned'
            current_assignment.unassigned_at = now_dt
            current_assignment.returned_by = actor
        asset.unassigned_at = now_str
        _log_event(db, asset.id, 'returned', 'Thu hồi asset', f'Thu hồi từ {previous_user} ({source})', actor)
    if new_user:
        db.add(
            AssetAssignment(
                asset_id=asset.id,
                assigned_user=new_user,
                assigned_by=actor,
                assigned_at=now_dt,
                note=source,
            )
        )
        asset.assigned_at = now_str
        asset.unassigned_at = None
        _log_event(db, asset.id, 'assigned', 'Cấp phát asset', f'Gán cho {new_user} ({source})', actor)
    asset.assigned_user = new_user


def _commit_import_rows(rows: list[tuple[int, AssetImportDTO]], db: Session, actor: str):
    created = 0
    updated = 0
    skipped: list[str] = []
    for row_number, dto in rows:
        if not dto.asset_code or not dto.asset_name or not dto.asset_type:
            skipped.append(f'Dòng {row_number}: thiếu Mã thiết bị / Tên thiết bị / Loại thiết bị')
            continue

        asset = db.scalar(select(Asset).where(Asset.asset_code == dto.asset_code))
        if not asset:
            now_str = datetime.utcnow().strftime('%Y-%m-%d %H:%M') if dto.assigned_user else None
            asset = Asset(**asdict(dto), assigned_at=now_str)
            db.add(asset)
            db.flush()
            _log_event(db, asset.id, 'asset_imported', 'Import asset mới', f'Import từ Excel: {asset.asset_code}', actor)
            if dto.assigned_user:
                db.add(AssetAssignment(asset_id=asset.id, assigned_user=dto.assigned_user, assigned_by=actor, note='Import từ Excel'))
                _log_event(db, asset.id, 'assigned', 'Cấp phát asset', f'Gán cho {dto.assigned_user} (import Excel)', actor)
            created += 1
            continue

        previous_user = asset.assigned_user
        asset.asset_name = dto.asset_name
        asset.asset_type = dto.asset_type
        asset.model = dto.model
        asset.serial_number = dto.serial_number
        asset.ip_address = dto.ip_address
        asset.department = dto.department
        asset.location = dto.location
        asset.purchase_date = dto.purchase_date
        asset.warranty_expiry = dto.warranty_expiry
        asset.status = dto.status
        asset.notes = dto.notes
        _apply_assignment_change(db, asset, dto.assigned_user, actor, 'Import từ Excel')
        if previous_user == dto.assigned_user:
            asset.assigned_user = dto.assigned_user
        _log_event(db, asset.id, 'asset_imported', 'Cập nhật asset từ import', f'Cập nhật từ Excel: {asset.asset_code}', actor)
        updated += 1
    db.commit()
    return {'created': created, 'updated': updated, 'skipped': skipped, 'total_rows': len(rows)}


@router.get('/api/list')
@require_module_access('assets')
def asset_api_list(request: Request, db: Session = Depends(get_db), current_user: Any = None, status: str | None = Query(None)):
    try:
        stmt = select(Asset)
        
        # Exclude Cameras from general asset list if they are managed elsewhere
        stmt = stmt.where(Asset.asset_type != 'Camera')
        
        if status:
            raw_status = status.strip().lower()
            stmt = stmt.where(Asset.status == raw_status)
        else:
            stmt = stmt.where(Asset.status == 'active')
        
        assets = db.scalars(stmt.order_by(Asset.asset_code.asc())).all()
        return {
            "items": [
                {
                    "id": a.id, 
                    "asset_code": a.asset_code, 
                    "asset_name": a.asset_name, 
                    "asset_type": a.asset_type,
                    "department": a.department or "Chưa phân loại"
                } for a in assets
            ]
        }
    except Exception as e:
        return {"items": [], "error": str(e)}


@router.get('/', response_class=HTMLResponse)
@require_module_access('assets')
def asset_list(request: Request, q: str | None = Query(default=None), asset_type: str | None = Query(default=None), department: str | None = Query(default=None), status: str | None = Query(default=None), warranty: str | None = Query(default=None), filter: str | None = Query(default=None), db: Session = Depends(get_db), current_user=None):
    assets = _filtered_assets(db, q=q, asset_type=asset_type, department=department, status=status, warranty=warranty, filter=filter)
    asset_types = db.scalars(select(Asset.asset_type).where(Asset.asset_type != 'Camera').distinct().order_by(Asset.asset_type.asc())).all()
    departments = db.scalars(select(Asset.department).where(Asset.department.is_not(None)).distinct().order_by(Asset.department.asc())).all()
    statuses = [item for item in ASSET_STATUSES if item in {a.status for a in db.scalars(select(Asset)).all()} or item == status or item == 'active']
    return templates.TemplateResponse('assets/list.html', {
        'request': request, 
        'assets': assets, 
        'q': q or '', 
        'asset_type': asset_type or '', 
        'department': department or '', 
        'status': status or '', 
        'warranty': warranty or '', 
        'filter': filter or '',
        'asset_types': asset_types, 
        'departments': departments, 
        'statuses': statuses, 
        'current_user': current_user, 
        'days_to_warranty': _days_to_warranty
    })


@router.get('/export')
@require_permission('can_export_assets')
def asset_export(request: Request, q: str | None = Query(default=None), asset_type: str | None = Query(default=None), department: str | None = Query(default=None), status: str | None = Query(default=None), warranty: str | None = Query(default=None), filter: str | None = Query(default=None), db: Session = Depends(get_db), current_user=None):
    assets = _filtered_assets(db, q=q, asset_type=asset_type, department=department, status=status, warranty=warranty, filter=filter)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Assets'
    ws.append(IMPORT_HEADERS)
    for asset in assets:
        ws.append([
            asset.asset_code,
            asset.asset_name,
            asset.asset_type,
            asset.model or '',
            asset.serial_number or '',
            asset.ip_address or '',
            asset.department or '',
            asset.assigned_user or '',
            asset.location or '',
            asset.purchase_date or '',
            asset.warranty_expiry or '',
            asset.status,
            asset.notes or ''
        ])
    stream = io.BytesIO()
    wb.save(stream)
    content = stream.getvalue()
    return Response(
        content=content,
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={
            'Content-Disposition': 'attachment; filename="assets_export.xlsx"',
            'Content-Length': str(len(content))
        }
    )


@router.get('/import/template')
@require_permission('can_import_assets')
def asset_import_template(request: Request, current_user=None):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'ImportAssets'
    ws.append(IMPORT_HEADERS)
    ws.append(['TS-001', 'Laptop Dell Latitude 5440', 'Laptop', 'Latitude 5440', 'SN123456', '192.168.1.10', 'IT', 'Nguyen Van A', 'VP HCM', '2026-03-01', '2029-03-01', 'active', 'Máy cấp cho nhân sự mới'])
    for column_cells in ws.columns:
        letter = column_cells[0].column_letter
        ws.column_dimensions[letter].width = 22
    stream = io.BytesIO()
    wb.save(stream)
    content = stream.getvalue()
    return Response(
        content=content,
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={
            'Content-Disposition': 'attachment; filename="asset_import_template.xlsx"',
            'Content-Length': str(len(content))
        }
    )


@router.get('/import', response_class=HTMLResponse)
@require_permission('can_import_assets')
def asset_import_page(request: Request, current_user=None):
    return _render_import_page(request, current_user=current_user)


@router.post('/import/preview', response_class=HTMLResponse)
@require_permission('can_import_assets')
def asset_import_preview(request: Request, import_file: UploadFile = File(...), db: Session = Depends(get_db), current_user=None):
    filename = (import_file.filename or '').lower()
    if not filename.endswith('.xlsx'):
        return _render_import_page(request, error='Chỉ hỗ trợ file .xlsx', current_user=current_user)
    try:
        rows = _load_import_rows(import_file.file.read())
        preview = _build_import_preview(rows, db, import_file.filename or 'import.xlsx')
    except ValueError as exc:
        return _render_import_page(request, error=str(exc), current_user=current_user)
    except Exception:
        return _render_import_page(request, error='Không đọc được file Excel. Hãy dùng đúng file mẫu .xlsx.', current_user=current_user)
    return _render_import_page(request, preview=preview, current_user=current_user)


@router.post('/import/confirm', response_class=HTMLResponse)
@require_permission('can_import_assets')
def asset_import_confirm(request: Request, preview_token: str = Form(...), db: Session = Depends(get_db), current_user=None):
    try:
        rows, _filename = _rows_from_preview_token(preview_token)
    except Exception:
        return _render_import_page(request, error='Preview import không hợp lệ hoặc đã hết hạn.', current_user=current_user)
    summary = _commit_import_rows(rows, db, current_user.username)
    return _render_import_page(request, summary=summary, current_user=current_user)


@router.post('/import', response_class=HTMLResponse)
@require_permission('can_import_assets')
def asset_import_submit(request: Request, import_file: UploadFile = File(...), db: Session = Depends(get_db), current_user=None):
    filename = (import_file.filename or '').lower()
    if not filename.endswith('.xlsx'):
        return _render_import_page(request, error='Chỉ hỗ trợ file .xlsx', current_user=current_user)
    try:
        rows = _load_import_rows(import_file.file.read())
    except ValueError as exc:
        return _render_import_page(request, error=str(exc), current_user=current_user)
    except Exception:
        return _render_import_page(request, error='Không đọc được file Excel. Hãy dùng đúng file mẫu .xlsx.', current_user=current_user)
    summary = _commit_import_rows(rows, db, current_user.username)
    return _render_import_page(request, summary=summary, current_user=current_user)


@router.get('/new', response_class=HTMLResponse)
@require_permission('can_create_assets')
def asset_new(request: Request, current_user=None):
    return _render_form(request, current_user=current_user)


@router.post('/new')
@require_permission('can_create_assets')
def asset_create(request: Request, asset_code: str = Form(...), asset_name: str = Form(...), asset_type: str = Form(...), ip_address: str = Form(default=''), model: str = Form(default=''), serial_number: str = Form(default=''), department: str = Form(default=''), assigned_user: str = Form(default=''), location: str = Form(default=''), purchase_date: str = Form(default=''), warranty_expiry: str = Form(default=''), status: str = Form(default='active'), notes: str = Form(default=''), db: Session = Depends(get_db), current_user=None):
    existing = db.scalar(select(Asset).where(Asset.asset_code == asset_code.strip()))
    if existing:
        return _render_form(request, error='Mã thiết bị đã tồn tại.', current_user=current_user)
    normalized_status = _normalize_status(status)
    now_str = datetime.utcnow().strftime('%Y-%m-%d %H:%M') if assigned_user.strip() else None
    asset = Asset(asset_code=asset_code.strip(), asset_name=asset_name.strip(), asset_type=asset_type.strip(), ip_address=ip_address.strip() or None, model=model.strip() or None, serial_number=serial_number.strip() or None, department=department.strip() or None, assigned_user=assigned_user.strip() or None, assigned_at=now_str, location=location.strip() or None, purchase_date=purchase_date.strip() or None, warranty_expiry=warranty_expiry.strip() or None, status=normalized_status, notes=notes.strip() or None)
    db.add(asset)
    db.flush()
    _log_event(db, asset.id, 'asset_created', 'Tạo asset', f'Tạo thiết bị {asset.asset_code}', current_user.username)
    if asset.assigned_user:
        db.add(AssetAssignment(asset_id=asset.id, assigned_user=asset.assigned_user, assigned_by=current_user.username, note='Khởi tạo với người dùng đã gán'))
        _log_event(db, asset.id, 'assigned', 'Cấp phát asset', f'Gán cho {asset.assigned_user}', current_user.username)
    db.commit()
    return RedirectResponse(url='/assets/', status_code=303)


@router.get('/{asset_id}', response_class=HTMLResponse)
@require_module_access('assets')
def asset_detail(asset_id: int, request: Request, db: Session = Depends(get_db), current_user=None):
    asset = db.get(Asset, asset_id)
    if not asset:
        return RedirectResponse(url='/assets/', status_code=303)
    
    can_edit = has_permission(current_user, 'can_edit_assets')
    alerts = []
    if asset:
        days = _days_to_warranty(asset)
        if days is not None and days < 0:
            alerts.append(('danger', f'Bảo hành đã hết {abs(days)} ngày.'))
        elif days is not None and days <= 30:
            alerts.append(('warning', f'Bảo hành sẽ hết trong {days} ngày.'))
        if asset.status in ('retired', 'disposed', 'lost'):
            alerts.append(('secondary', f'Thiết bị đang ở trạng thái {asset.status}.'))
        elif asset.status == 'in_repair':
            alerts.append(('info', 'Thiết bị đang trong quá trình sửa chữa.'))
    return templates.TemplateResponse('assets/detail.html', {
        'request': request, 
        'asset': asset, 
        'alerts': alerts, 
        'current_user': current_user,
        'can_edit': can_edit
    })


@router.post('/{asset_id}/retire')
@require_permission('can_edit_assets')
def asset_retire(asset_id: int, request: Request, db: Session = Depends(get_db), current_user=None):
    asset = db.get(Asset, asset_id)
    if not asset:
        return RedirectResponse(url='/assets/', status_code=303)
    asset.status = 'retired'
    _log_event(db, asset.id, 'asset_retired', 'Ngừng sử dụng asset', f'Đánh dấu retired cho {asset.asset_code}', current_user.username)
    db.commit()
    return RedirectResponse(url='/assets/', status_code=303)


@router.post('/{asset_id}/restore')
@require_permission('can_edit_assets')
def asset_restore(asset_id: int, request: Request, db: Session = Depends(get_db), current_user=None):
    asset = db.get(Asset, asset_id)
    if not asset:
        return RedirectResponse(url='/assets/', status_code=303)
    asset.status = 'active'
    _log_event(db, asset.id, 'asset_restored', 'Khôi phục asset', f'Khôi phục active cho {asset.asset_code}', current_user.username)
    db.commit()
    return RedirectResponse(url='/assets/', status_code=303)


@router.get('/{asset_id}/edit', response_class=HTMLResponse)
@require_permission('can_edit_assets')
def asset_edit(asset_id: int, request: Request, db: Session = Depends(get_db), current_user=None):
    asset = db.get(Asset, asset_id)
    return _render_form(request, asset=asset, current_user=current_user)


@router.post('/{asset_id}/edit')
@require_permission('can_edit_assets')
def asset_update(request: Request, asset_id: int, asset_code: str = Form(...), asset_name: str = Form(...), asset_type: str = Form(...), ip_address: str = Form(default=''), model: str = Form(default=''), serial_number: str = Form(default=''), department: str = Form(default=''), assigned_user: str = Form(default=''), location: str = Form(default=''), purchase_date: str = Form(default=''), warranty_expiry: str = Form(default=''), status: str = Form(default='active'), notes: str = Form(default=''), db: Session = Depends(get_db), current_user=None):
    asset = db.get(Asset, asset_id)
    new_user = assigned_user.strip() or None
    old_status = asset.status
    asset.asset_code = asset_code.strip()
    asset.asset_name = asset_name.strip()
    asset.asset_type = asset_type.strip()
    asset.ip_address = ip_address.strip() or None
    asset.model = model.strip() or None
    asset.serial_number = serial_number.strip() or None
    asset.department = department.strip() or None
    asset.location = location.strip() or None
    asset.purchase_date = purchase_date.strip() or None
    asset.warranty_expiry = warranty_expiry.strip() or None
    asset.status = _normalize_status(status)
    asset.notes = notes.strip() or None
    _apply_assignment_change(db, asset, new_user, current_user.username, 'Cập nhật thông tin asset')
    if old_status != asset.status:
        _log_event(db, asset.id, 'asset_status_changed', 'Đổi trạng thái asset', f'{old_status} -> {asset.status}', current_user.username)
    _log_event(db, asset.id, 'asset_updated', 'Cập nhật asset', f'Cập nhật thông tin thiết bị {asset.asset_code}', current_user.username)
    db.commit()
    return RedirectResponse(url=f'/assets/{asset_id}', status_code=303)
