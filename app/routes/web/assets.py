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
from app.db.models import Asset, AssetAssignment, AssetEvent, AssetStatusHistory, User, Department, Employee, AssetType, Location, AssetStatus
from app.db.session import get_db
from app.services.audit import log_audit

router = APIRouter(prefix='/assets', tags=['assets'])
templates = Jinja2Templates(directory='app/templates')
DATE_FMT = '%Y-%m-%d'
ASSET_STATUSES = ['in_stock', 'assigned', 'borrowed', 'repairing', 'retired', 'disposed', 'lost']
ASSET_STATUS_TRANSITIONS = {
    'in_stock': {'in_stock', 'assigned', 'borrowed', 'repairing', 'retired', 'disposed', 'lost'},
    'assigned': {'assigned', 'repairing', 'in_stock', 'retired', 'disposed', 'lost', 'borrowed'},
    'borrowed': {'borrowed', 'in_stock', 'repairing', 'retired', 'disposed', 'lost', 'assigned'},
    'repairing': {'repairing', 'in_stock', 'retired', 'disposed', 'lost', 'assigned'},
    'retired': {'retired'},
    'disposed': {'disposed'},
    'lost': {'lost'},
}
STATUS_LABELS = {
    'in_stock': 'In Stock',
    'assigned': 'Assigned',
    'borrowed': 'Borrowed',
    'repairing': 'Repairing',
    'retired': 'Retired',
    'disposed': 'Disposed',
    'lost': 'Lost',
}
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
            status=_normalize_status(row_map.get('Trạng thái', '').strip() or 'in_stock'),
            notes=row_map.get('Ghi chú', '').strip() or None,
        )


def _display_asset_type(asset: Asset | None) -> str:
    if not asset:
        return ''
    return getattr(getattr(asset, 'category', None), 'name', None) or asset.asset_type or ''


def _display_department(asset: Asset | None) -> str:
    if not asset:
        return ''
    return getattr(getattr(asset, 'department_ref', None), 'name', None) or asset.department or ''


def _display_location(asset: Asset | None) -> str:
    if not asset:
        return ''
    return getattr(getattr(asset, 'location_ref', None), 'name', None) or asset.location or ''


def _display_status(asset: Asset | None) -> str:
    if not asset:
        return 'in_stock'
    status_value = getattr(getattr(asset, 'status_ref', None), 'code', None) or asset.status or 'in_stock'
    return _normalize_status(status_value)


def _master_data_context(db: Session):
    asset_type_rows = db.scalars(select(AssetType).where(AssetType.is_active == True).order_by(AssetType.name.asc())).all()
    department_rows = db.scalars(select(Department).where(Department.is_active == True).order_by(Department.name.asc())).all()
    location_rows = db.scalars(select(Location).where(Location.is_active == True).order_by(Location.name.asc())).all()
    status_rows = db.scalars(select(AssetStatus).where(AssetStatus.is_active == True).order_by(AssetStatus.sort_order.asc(), AssetStatus.name.asc())).all()
    return {
        'asset_type_options': asset_type_rows,
        'department_options': department_rows,
        'location_options': location_rows,
        'status_options': status_rows,
    }


def _resolve_department_id(db: Session, value: str | None):
    raw = (value or '').strip()
    if not raw:
        return None
    return db.scalar(select(Department.id).where(or_(Department.name == raw, Department.code == raw)).limit(1))


def _resolve_asset_type_value(db: Session, value: str | None):
    raw = (value or '').strip()
    if not raw:
        return '', None
    row = db.execute(select(AssetType.id, AssetType.name).where(or_(AssetType.name == raw, AssetType.code == raw)).limit(1)).first()
    if row:
        return row[1], row[0]
    return raw, None


def _resolve_location_id(db: Session, value: str | None):
    raw = (value or '').strip()
    if not raw:
        return None
    return db.scalar(select(Location.id).where(or_(Location.name == raw, Location.code == raw)).limit(1))


def _resolve_status_value(db: Session, value: str | None):
    normalized = _normalize_status(value)
    row = db.execute(select(AssetStatus.id, AssetStatus.code).where(or_(AssetStatus.code == normalized, AssetStatus.code == normalized.upper(), AssetStatus.name == value)).limit(1)).first()
    return normalized, (row[0] if row else None)


def _set_asset_status(db: Session, asset: Asset, target_status: str | None, actor: str | None, note: str | None = None):
    old_status = asset.status
    old_status_id = asset.status_id
    normalized_status, status_id = _resolve_status_value(db, target_status)
    _assert_valid_status_transition(old_status, normalized_status)
    asset.status = normalized_status
    asset.status_id = status_id
    _record_status_history(db, asset, old_status, old_status_id, normalized_status, status_id, actor, note)
    return old_status, normalized_status


def _resolve_employee_id(db: Session, value: str | None):
    raw = (value or '').strip()
    if not raw:
        return None
    return db.scalar(select(Employee.id).where(or_(Employee.full_name == raw, Employee.employee_code == raw)).limit(1))


def _allowed_transitions_for(asset: Asset | None) -> set[str]:
    current = _normalize_status(getattr(asset, 'status', None) if asset else None)
    return ASSET_STATUS_TRANSITIONS.get(current, {current})


def _asset_action_flags(asset: Asset | None, active_assignment: AssetAssignment | None = None) -> dict[str, bool]:
    current = _normalize_status(getattr(asset, 'status', None) if asset else None)
    assignment_state = getattr(active_assignment, 'status', None)
    has_assignee = bool(getattr(asset, 'assigned_user', None))
    allowed = _allowed_transitions_for(asset)
    return {
        'can_assign': (not has_assignee) and ('assigned' in allowed) and current in {'in_stock', 'repairing'},
        'can_borrow': (not has_assignee) and ('borrowed' in allowed) and current in {'in_stock'},
        'can_return': has_assignee and assignment_state == 'assigned' and ('in_stock' in allowed),
        'can_transfer': has_assignee and assignment_state == 'assigned' and ('assigned' in allowed),
        'can_borrow_return': has_assignee and assignment_state == 'borrowed' and ('in_stock' in allowed),
        'can_retire': 'retired' in allowed and current != 'retired',
        'can_restore': current in {'retired', 'disposed', 'lost'} and ('in_stock' in allowed or current in {'retired', 'disposed', 'lost'}),
    }


def _asset_view_model(asset: Asset):
    asset.display_asset_type = _display_asset_type(asset)
    asset.display_department = _display_department(asset)
    asset.display_location = _display_location(asset)
    asset.display_status = _display_status(asset)
    asset.status_label = STATUS_LABELS.get(asset.display_status, asset.display_status)
    return asset


def _render_form(request: Request, db: Session, asset: Asset | None = None, error: str | None = None, current_user=None):
    if asset:
        _asset_view_model(asset)
    context = {'request': request, 'asset': asset, 'error': error, 'current_user': current_user}
    context.update(_master_data_context(db))
    return templates.TemplateResponse('assets/form.html', context)


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


def _assert_valid_status_transition(old_status: str | None, new_status: str | None):
    current = _normalize_status(old_status)
    target = _normalize_status(new_status)
    allowed = ASSET_STATUS_TRANSITIONS.get(current, {current})
    if target not in allowed:
        raise ValueError(f'Không cho phép chuyển trạng thái từ {current} sang {target}.')


def _record_status_history(db: Session, asset: Asset, old_status: str | None, old_status_id: int | None, new_status: str | None, new_status_id: int | None, actor: str | None, note: str | None = None):
    normalized_old = _normalize_status(old_status)
    normalized_new = _normalize_status(new_status)
    if normalized_old == normalized_new and old_status_id == new_status_id:
        return
    db.add(
        AssetStatusHistory(
            asset_id=asset.id,
            old_status_id=old_status_id,
            new_status_id=new_status_id,
            old_status_code=normalized_old,
            new_status_code=normalized_new,
            changed_by=actor,
            note=note,
        )
    )


def _normalize_text(value):
    if value is None:
        return ''
    if isinstance(value, datetime):
        return value.strftime(DATE_FMT)
    return str(value).strip()


def _normalize_status(value: str | None) -> str:
    raw = (value or '').strip().lower()
    aliases = {
        'active': 'assigned',
        'inactive': 'in_stock',
        'in_repair': 'repairing',
        'repair': 'repairing',
        'in-repair': 'repairing',
        'in repair': 'repairing',
        'broken': 'repairing',
        'archive': 'retired',
        'archived': 'retired',
        'instock': 'in_stock',
        'in stock': 'in_stock',
    }
    normalized = aliases.get(raw, raw or 'in_stock')
    return normalized if normalized in ASSET_STATUSES else 'in_stock'


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


def _get_active_assignment(db: Session, asset: Asset):
    return db.scalar(
        select(AssetAssignment)
        .where(AssetAssignment.asset_id == asset.id, AssetAssignment.status.in_(['assigned', 'borrowed']))
        .order_by(AssetAssignment.assigned_at.desc())
    )


def _close_active_assignment(db: Session, asset: Asset, actor: str | None, source: str, close_status: str = 'returned'):
    now_dt = datetime.utcnow()
    now_str = now_dt.strftime('%Y-%m-%d %H:%M')
    current_assignment = _get_active_assignment(db, asset)
    previous_user = asset.assigned_user
    if current_assignment:
        current_assignment.status = close_status
        current_assignment.unassigned_at = now_dt
        current_assignment.returned_by = actor
    if previous_user:
        title = 'Thu hồi asset' if close_status == 'returned' else 'Kết thúc mượn asset'
        event_type = 'returned' if close_status == 'returned' else 'borrow_returned'
        _log_event(db, asset.id, event_type, title, f'Thu hồi từ {previous_user} ({source})', actor)
    asset.current_assignment_id = None
    asset.assigned_user = None
    asset.unassigned_at = now_str
    return previous_user


def _create_assignment(db: Session, asset: Asset, new_user: str, actor: str | None, source: str, assignment_status: str = 'assigned'):
    now_dt = datetime.utcnow()
    now_str = now_dt.strftime('%Y-%m-%d %H:%M')
    assignment = AssetAssignment(
        asset_id=asset.id,
        employee_id=_resolve_employee_id(db, new_user),
        assigned_user=new_user,
        assigned_by=actor,
        assigned_at=now_dt,
        note=source,
        status=assignment_status,
    )
    db.add(assignment)
    db.flush()
    asset.current_assignment_id = assignment.id
    asset.assigned_user = new_user
    asset.assigned_at = now_str
    asset.unassigned_at = None
    title = 'Cấp phát asset' if assignment_status == 'assigned' else 'Cho mượn asset'
    event_type = 'assigned' if assignment_status == 'assigned' else 'borrowed'
    _log_event(db, asset.id, event_type, title, f'Gán cho {new_user} ({source})', actor)
    return assignment


def _apply_assignment_change(db: Session, asset: Asset, new_user: str | None, actor: str | None, source: str):
    previous_user = asset.assigned_user
    if previous_user == new_user:
        return
    if previous_user:
        _close_active_assignment(db, asset, actor, source, close_status='returned')
    if new_user:
        _create_assignment(db, asset, new_user, actor, source, assignment_status='assigned')


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
            asset_type_value, category_id = _resolve_asset_type_value(db, dto.asset_type)
            requested_status = 'assigned' if dto.assigned_user and _normalize_status(dto.status) == 'in_stock' else dto.status
            status_value, status_id = _resolve_status_value(db, requested_status)
            asset = Asset(**asdict(dto), asset_type=asset_type_value, category_id=category_id, department_id=_resolve_department_id(db, dto.department), location_id=_resolve_location_id(db, dto.location), status=status_value, status_id=status_id, assigned_at=now_str)
            db.add(asset)
            db.flush()
            _log_event(db, asset.id, 'asset_imported', 'Import asset mới', f'Import từ Excel: {asset.asset_code}', actor)
            if dto.assigned_user:
                assignment = AssetAssignment(asset_id=asset.id, employee_id=_resolve_employee_id(db, dto.assigned_user), assigned_user=dto.assigned_user, assigned_by=actor, note='Import từ Excel')
                db.add(assignment)
                db.flush()
                asset.current_assignment_id = assignment.id
                _log_event(db, asset.id, 'assigned', 'Cấp phát asset', f'Gán cho {dto.assigned_user} (import Excel)', actor)
            created += 1
            continue

        previous_user = asset.assigned_user
        asset.asset_name = dto.asset_name
        asset.asset_type, asset.category_id = _resolve_asset_type_value(db, dto.asset_type)
        asset.model = dto.model
        asset.serial_number = dto.serial_number
        asset.ip_address = dto.ip_address
        asset.department = dto.department
        asset.department_id = _resolve_department_id(db, dto.department)
        asset.location = dto.location
        asset.location_id = _resolve_location_id(db, dto.location)
        asset.purchase_date = dto.purchase_date
        asset.warranty_expiry = dto.warranty_expiry
        requested_status = 'assigned' if dto.assigned_user and _normalize_status(dto.status) == 'in_stock' else dto.status
        previous_status, current_status = _set_asset_status(db, asset, requested_status, actor, 'Import từ Excel')
        asset.notes = dto.notes
        _apply_assignment_change(db, asset, dto.assigned_user, actor, 'Import từ Excel')
        if previous_user == dto.assigned_user:
            asset.assigned_user = dto.assigned_user
        if previous_status != current_status:
            _log_event(db, asset.id, 'asset_status_changed', 'Đổi trạng thái asset', f'{previous_status} -> {current_status}', actor)
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
            stmt = stmt.where(Asset.status.in_(['assigned', 'in_stock']))
        
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
    assets = [_asset_view_model(asset) for asset in _filtered_assets(db, q=q, asset_type=asset_type, department=department, status=status, warranty=warranty, filter=filter)]
    asset_types = sorted({asset.display_asset_type or asset.asset_type for asset in assets if (asset.display_asset_type or asset.asset_type) and (asset.display_asset_type or asset.asset_type) != 'Camera'})
    departments = sorted({asset.display_department or asset.department for asset in assets if asset.display_department or asset.department})
    statuses = [item for item in ASSET_STATUSES if item in {a.display_status or a.status for a in assets} or item == status or item == 'in_stock']
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
        'status_labels': STATUS_LABELS,
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
def asset_new(request: Request, db: Session = Depends(get_db), current_user=None):
    return _render_form(request, db, current_user=current_user)


@router.post('/new')
@require_permission('can_create_assets')
def asset_create(request: Request, asset_code: str = Form(...), asset_name: str = Form(...), asset_type: str = Form(...), ip_address: str = Form(default=''), model: str = Form(default=''), serial_number: str = Form(default=''), department: str = Form(default=''), assigned_user: str = Form(default=''), location: str = Form(default=''), purchase_date: str = Form(default=''), warranty_expiry: str = Form(default=''), status: str = Form(default='in_stock'), notes: str = Form(default=''), db: Session = Depends(get_db), current_user=None):
    existing = db.scalar(select(Asset).where(Asset.asset_code == asset_code.strip()))
    if existing:
        return _render_form(request, db, error='Mã thiết bị đã tồn tại.', current_user=current_user)
    asset_type_value, category_id = _resolve_asset_type_value(db, asset_type)
    requested_status = status
    if assigned_user.strip() and _normalize_status(status) == 'in_stock':
        requested_status = 'assigned'
    normalized_status, status_id = _resolve_status_value(db, requested_status)
    now_str = datetime.utcnow().strftime('%Y-%m-%d %H:%M') if assigned_user.strip() else None
    asset = Asset(asset_code=asset_code.strip(), asset_name=asset_name.strip(), asset_type=asset_type_value, category_id=category_id, ip_address=ip_address.strip() or None, model=model.strip() or None, serial_number=serial_number.strip() or None, department=department.strip() or None, department_id=_resolve_department_id(db, department), assigned_user=assigned_user.strip() or None, assigned_at=now_str, location=location.strip() or None, location_id=_resolve_location_id(db, location), purchase_date=purchase_date.strip() or None, warranty_expiry=warranty_expiry.strip() or None, status=normalized_status, status_id=status_id, notes=notes.strip() or None)
    db.add(asset)
    db.flush()
    _log_event(db, asset.id, 'asset_created', 'Tạo asset', f'Tạo thiết bị {asset.asset_code}', current_user.username)
    if asset.assigned_user:
        assignment = AssetAssignment(asset_id=asset.id, employee_id=_resolve_employee_id(db, asset.assigned_user), assigned_user=asset.assigned_user, assigned_by=current_user.username, note='Khởi tạo với người dùng đã gán')
        db.add(assignment)
        db.flush()
        asset.current_assignment_id = assignment.id
        _log_event(db, asset.id, 'assigned', 'Cấp phát asset', f'Gán cho {asset.assigned_user}', current_user.username)
    db.commit()
    return RedirectResponse(url='/assets/', status_code=303)


@router.get('/bulk-update', include_in_schema=False)
@router.get('/bulk-update/')
@require_permission('can_edit_assets')
def asset_bulk_update_get(request: Request, current_user=None):
    """Handle accidental GET requests to bulk-update by redirecting to list."""
    return RedirectResponse(url='/assets/', status_code=303)


@router.post('/bulk-update', include_in_schema=False)
@router.post('/bulk-update/')
@require_permission('can_edit_assets')
def asset_bulk_update(request: Request, asset_ids: str = Form(...), department: str = Form(default=None), status: str = Form(default=None), assigned_user: str = Form(default=None), location: str = Form(default=None), db: Session = Depends(get_db), current_user=None):
    ids = [int(i.strip()) for i in asset_ids.split(',') if i.strip()]
    if not ids:
        return RedirectResponse(url='/assets/', status_code=303)

    updates = {}
    if department and department.strip():
        updates['department'] = department.strip()
        updates['department_id'] = _resolve_department_id(db, department)
    if status and status.strip():
        updates['status'], updates['status_id'] = _resolve_status_value(db, status)
    if assigned_user and assigned_user.strip():
        updates['assigned_user'] = assigned_user.strip()
    if location and location.strip():
        updates['location'] = location.strip()
        updates['location_id'] = _resolve_location_id(db, location)

    if not updates:
        return RedirectResponse(url='/assets/', status_code=303)

    updated_count = 0
    for asset_id in ids:
        asset = db.get(Asset, asset_id)
        if not asset:
            continue
        
        changed = False
        old_status = asset.status
        
        if 'department' in updates and asset.department != updates['department']:
            asset.department = updates['department']
            asset.department_id = updates.get('department_id')
            changed = True
        if 'status' in updates and asset.status != updates['status']:
            try:
                previous_status, current_status = _set_asset_status(db, asset, updates['status'], current_user.username, 'Cập nhật hàng loạt (Bulk edit)')
            except ValueError:
                continue
            changed = True
            _log_event(db, asset.id, 'asset_status_changed', 'Bulk edit: Đổi trạng thái', f'{previous_status} -> {current_status}', current_user.username)
        if 'location' in updates and asset.location != updates['location']:
            asset.location = updates['location']
            asset.location_id = updates.get('location_id')
            changed = True
        
        if 'assigned_user' in updates:
            new_user = updates['assigned_user']
            if asset.assigned_user != new_user:
                _apply_assignment_change(db, asset, new_user, current_user.username, 'Cập nhật hàng loạt (Bulk edit)')
                changed = True
        
        if changed:
            _log_event(db, asset.id, 'asset_updated', 'Cập nhật hàng loạt', 'Cập nhật thông tin qua Bulk Edit', current_user.username)
            log_audit(
                db,
                actor=current_user.username if current_user else None,
                module='assets',
                action='bulk_update',
                entity_type='asset',
                entity_id=asset.id,
                metadata={'updates': updates},
            )
            updated_count += 1

    db.commit()
    return RedirectResponse(url=f'/assets/?success={updated_count}', status_code=303)


@router.get('/bulk-archive', include_in_schema=False)
@router.get('/bulk-archive/')
@require_permission('can_edit_assets')
def asset_bulk_archive_get(request: Request, current_user=None):
    return RedirectResponse(url='/assets/', status_code=303)


@router.post('/bulk-archive', include_in_schema=False)
@router.post('/bulk-archive/')
@require_permission('can_edit_assets')
def asset_bulk_archive(request: Request, asset_ids: str = Form(...), confirm_text: str = Form(default=''), db: Session = Depends(get_db), current_user=None):
    if confirm_text != 'ARCHIVE':
        return RedirectResponse(url='/assets/', status_code=303)

    ids = [int(i.strip()) for i in asset_ids.split(',') if i.strip()]
    if not ids:
        return RedirectResponse(url='/assets/', status_code=303)

    updated_count = 0
    for asset_id in ids:
        asset = db.get(Asset, asset_id)
        if not asset:
            continue
        if asset.status != 'retired':
            try:
                previous_status, current_status = _set_asset_status(db, asset, 'retired', current_user.username, 'Cập nhật hàng loạt: ngừng sử dụng asset')
            except ValueError:
                continue
            _log_event(db, asset.id, 'asset_retired', 'Ngừng sử dụng asset', f'Cập nhật hàng loạt: {previous_status} -> {current_status} cho {asset.asset_code}', current_user.username)
            log_audit(
                db,
                actor=current_user.username if current_user else None,
                module='assets',
                action='bulk_archive',
                entity_type='asset',
                entity_id=asset.id,
                metadata={'from_status': 'not_retired', 'to_status': 'retired'},
            )
            updated_count += 1

    db.commit()
    return RedirectResponse(url=f'/assets/?success={updated_count}', status_code=303)


@router.get('/bulk-restore', include_in_schema=False)
@router.get('/bulk-restore/')
@require_permission('can_edit_assets')
def asset_bulk_restore_get(request: Request, current_user=None):
    return RedirectResponse(url='/assets/', status_code=303)


@router.post('/bulk-restore', include_in_schema=False)
@router.post('/bulk-restore/')
@require_permission('can_edit_assets')
def asset_bulk_restore(request: Request, asset_ids: str = Form(...), db: Session = Depends(get_db), current_user=None):
    ids = [int(i.strip()) for i in asset_ids.split(',') if i.strip()]
    if not ids:
        return RedirectResponse(url='/assets/', status_code=303)

    updated_count = 0
    for asset_id in ids:
        asset = db.get(Asset, asset_id)
        if not asset:
            continue
        if asset.status in ('retired', 'disposed', 'lost', 'repairing', 'assigned', 'borrowed', 'in_stock'):
            previous_status = asset.status
            try:
                _old_status, current_status = _set_asset_status(db, asset, 'in_stock', current_user.username, 'Cập nhật hàng loạt: khôi phục asset')
            except ValueError:
                continue
            _log_event(db, asset.id, 'asset_restored', 'Khôi phục asset', f'Cập nhật hàng loạt: {previous_status} -> {current_status} cho {asset.asset_code}', current_user.username)
            log_audit(
                db,
                actor=current_user.username if current_user else None,
                module='assets',
                action='bulk_restore',
                entity_type='asset',
                entity_id=asset.id,
                metadata={'from_status': previous_status, 'to_status': 'in_stock'},
            )
            updated_count += 1

    db.commit()
    return RedirectResponse(url=f'/assets/?success={updated_count}', status_code=303)



@router.get('/{asset_id}', response_class=HTMLResponse)
@require_module_access('assets')
def asset_detail(asset_id: int, request: Request, db: Session = Depends(get_db), current_user=None):
    asset = db.get(Asset, asset_id)
    if not asset:
        return RedirectResponse(url='/assets/', status_code=303)
    
    can_edit = has_permission(current_user, 'can_edit_assets')
    alerts = []
    active_assignment = _get_active_assignment(db, asset)
    if asset:
        days = _days_to_warranty(asset)
        if days is not None and days < 0:
            alerts.append(('danger', f'Bảo hành đã hết {abs(days)} ngày.'))
        elif days is not None and days <= 30:
            alerts.append(('warning', f'Bảo hành sẽ hết trong {days} ngày.'))
        normalized_status = _normalize_status(asset.status)
        if normalized_status in ('retired', 'disposed', 'lost'):
            alerts.append(('secondary', f"Thiết bị đang ở trạng thái {STATUS_LABELS.get(normalized_status, normalized_status)}."))
        elif normalized_status == 'repairing':
            alerts.append(('info', 'Thiết bị đang trong quá trình sửa chữa.'))
    if asset:
        _asset_view_model(asset)
    action_flags = _asset_action_flags(asset, active_assignment)
    return templates.TemplateResponse('assets/detail.html', {
        'request': request, 
        'asset': asset, 
        'alerts': alerts, 
        'current_user': current_user,
        'can_edit': can_edit,
        'active_assignment': active_assignment,
        'status_history': list(asset.status_history or []),
        'action_flags': action_flags,
        'allowed_transitions': sorted(_allowed_transitions_for(asset)),
    })


@router.post('/{asset_id}/assign')
@require_permission('can_edit_assets')
def asset_assign(asset_id: int, request: Request, assigned_user: str = Form(...), department: str = Form(default=''), note: str = Form(default=''), db: Session = Depends(get_db), current_user=None):
    asset = db.get(Asset, asset_id)
    if not asset:
        return RedirectResponse(url='/assets/', status_code=303)
    new_user = assigned_user.strip()
    if not new_user:
        return RedirectResponse(url=f'/assets/{asset_id}', status_code=303)
    if asset.assigned_user and asset.assigned_user != new_user:
        return RedirectResponse(url=f'/assets/{asset_id}', status_code=303)
    if department.strip():
        asset.department = department.strip()
        asset.department_id = _resolve_department_id(db, department)
    _create_assignment(db, asset, new_user, current_user.username, note.strip() or 'Cấp phát asset')
    previous_status, current_status = _set_asset_status(db, asset, 'assigned', current_user.username, note.strip() or 'Cấp phát asset')
    if previous_status != current_status:
        _log_event(db, asset.id, 'asset_status_changed', 'Đổi trạng thái asset', f'{previous_status} -> {current_status}', current_user.username)
    log_audit(db, actor=current_user.username if current_user else None, module='assets', action='assign', entity_type='asset', entity_id=asset.id, metadata={'assigned_user': new_user})
    db.commit()
    return RedirectResponse(url=f'/assets/{asset_id}', status_code=303)


@router.post('/{asset_id}/return')
@require_permission('can_edit_assets')
def asset_return(asset_id: int, request: Request, note: str = Form(default=''), db: Session = Depends(get_db), current_user=None):
    asset = db.get(Asset, asset_id)
    if not asset:
        return RedirectResponse(url='/assets/', status_code=303)
    if not asset.assigned_user:
        return RedirectResponse(url=f'/assets/{asset_id}', status_code=303)
    previous_user = _close_active_assignment(db, asset, current_user.username, note.strip() or 'Thu hồi asset', close_status='returned')
    previous_status, current_status = _set_asset_status(db, asset, 'in_stock', current_user.username, note.strip() or 'Thu hồi asset')
    if previous_status != current_status:
        _log_event(db, asset.id, 'asset_status_changed', 'Đổi trạng thái asset', f'{previous_status} -> {current_status}', current_user.username)
    log_audit(db, actor=current_user.username if current_user else None, module='assets', action='return', entity_type='asset', entity_id=asset.id, metadata={'returned_user': previous_user})
    db.commit()
    return RedirectResponse(url=f'/assets/{asset_id}', status_code=303)


@router.post('/{asset_id}/transfer')
@require_permission('can_edit_assets')
def asset_transfer(asset_id: int, request: Request, assigned_user: str = Form(...), department: str = Form(default=''), note: str = Form(default=''), db: Session = Depends(get_db), current_user=None):
    asset = db.get(Asset, asset_id)
    if not asset:
        return RedirectResponse(url='/assets/', status_code=303)
    new_user = assigned_user.strip()
    if not new_user or new_user == (asset.assigned_user or '').strip():
        return RedirectResponse(url=f'/assets/{asset_id}', status_code=303)
    previous_user = asset.assigned_user
    if department.strip():
        asset.department = department.strip()
        asset.department_id = _resolve_department_id(db, department)
    if previous_user:
        _close_active_assignment(db, asset, current_user.username, note.strip() or 'Chuyển giao asset', close_status='returned')
    _create_assignment(db, asset, new_user, current_user.username, note.strip() or 'Chuyển giao asset', assignment_status='assigned')
    previous_status, current_status = _set_asset_status(db, asset, 'assigned', current_user.username, note.strip() or 'Chuyển giao asset')
    if previous_status != current_status:
        _log_event(db, asset.id, 'asset_status_changed', 'Đổi trạng thái asset', f'{previous_status} -> {current_status}', current_user.username)
    _log_event(db, asset.id, 'asset_transferred', 'Chuyển giao asset', f'{previous_user or "Chưa có người dùng"} -> {new_user}', current_user.username)
    log_audit(db, actor=current_user.username if current_user else None, module='assets', action='transfer', entity_type='asset', entity_id=asset.id, metadata={'from_user': previous_user, 'to_user': new_user})
    db.commit()
    return RedirectResponse(url=f'/assets/{asset_id}', status_code=303)


@router.post('/{asset_id}/borrow')
@require_permission('can_edit_assets')
def asset_borrow(asset_id: int, request: Request, assigned_user: str = Form(...), department: str = Form(default=''), note: str = Form(default=''), db: Session = Depends(get_db), current_user=None):
    asset = db.get(Asset, asset_id)
    if not asset:
        return RedirectResponse(url='/assets/', status_code=303)
    new_user = assigned_user.strip()
    if not new_user:
        return RedirectResponse(url=f'/assets/{asset_id}', status_code=303)
    if asset.assigned_user:
        return RedirectResponse(url=f'/assets/{asset_id}', status_code=303)
    if department.strip():
        asset.department = department.strip()
        asset.department_id = _resolve_department_id(db, department)
    _create_assignment(db, asset, new_user, current_user.username, note.strip() or 'Cho mượn asset', assignment_status='borrowed')
    previous_status, current_status = _set_asset_status(db, asset, 'borrowed', current_user.username, note.strip() or 'Cho mượn asset')
    if previous_status != current_status:
        _log_event(db, asset.id, 'asset_status_changed', 'Đổi trạng thái asset', f'{previous_status} -> {current_status}', current_user.username)
    log_audit(db, actor=current_user.username if current_user else None, module='assets', action='borrow', entity_type='asset', entity_id=asset.id, metadata={'borrowed_by': new_user})
    db.commit()
    return RedirectResponse(url=f'/assets/{asset_id}', status_code=303)


@router.post('/{asset_id}/borrow-return')
@require_permission('can_edit_assets')
def asset_borrow_return(asset_id: int, request: Request, note: str = Form(default=''), db: Session = Depends(get_db), current_user=None):
    asset = db.get(Asset, asset_id)
    if not asset:
        return RedirectResponse(url='/assets/', status_code=303)
    active_assignment = _get_active_assignment(db, asset)
    if not active_assignment or active_assignment.status != 'borrowed':
        return RedirectResponse(url=f'/assets/{asset_id}', status_code=303)
    previous_user = _close_active_assignment(db, asset, current_user.username, note.strip() or 'Thu hồi asset mượn', close_status='returned')
    previous_status, current_status = _set_asset_status(db, asset, 'in_stock', current_user.username, note.strip() or 'Thu hồi asset mượn')
    if previous_status != current_status:
        _log_event(db, asset.id, 'asset_status_changed', 'Đổi trạng thái asset', f'{previous_status} -> {current_status}', current_user.username)
    log_audit(db, actor=current_user.username if current_user else None, module='assets', action='borrow_return', entity_type='asset', entity_id=asset.id, metadata={'returned_user': previous_user})
    db.commit()
    return RedirectResponse(url=f'/assets/{asset_id}', status_code=303)


@router.post('/{asset_id}/retire')
@require_permission('can_edit_assets')
def asset_retire(asset_id: int, request: Request, db: Session = Depends(get_db), current_user=None):
    asset = db.get(Asset, asset_id)
    if not asset:
        return RedirectResponse(url='/assets/', status_code=303)
    try:
        previous_status, current_status = _set_asset_status(db, asset, 'retired', current_user.username, 'Ngừng sử dụng asset')
    except ValueError:
        return RedirectResponse(url=f'/assets/{asset_id}', status_code=303)
    _log_event(db, asset.id, 'asset_retired', 'Ngừng sử dụng asset', f'{previous_status} -> {current_status} cho {asset.asset_code}', current_user.username)
    db.commit()
    return RedirectResponse(url='/assets/', status_code=303)


@router.post('/{asset_id}/restore')
@require_permission('can_edit_assets')
def asset_restore(asset_id: int, request: Request, db: Session = Depends(get_db), current_user=None):
    asset = db.get(Asset, asset_id)
    if not asset:
        return RedirectResponse(url='/assets/', status_code=303)
    try:
        previous_status, current_status = _set_asset_status(db, asset, 'in_stock', current_user.username, 'Khôi phục asset')
    except ValueError:
        return RedirectResponse(url=f'/assets/{asset_id}', status_code=303)
    _log_event(db, asset.id, 'asset_restored', 'Khôi phục asset', f'{previous_status} -> {current_status} cho {asset.asset_code}', current_user.username)
    db.commit()
    return RedirectResponse(url='/assets/', status_code=303)


@router.get('/{asset_id}/edit', response_class=HTMLResponse)
@require_permission('can_edit_assets')
def asset_edit(asset_id: int, request: Request, db: Session = Depends(get_db), current_user=None):
    asset = db.get(Asset, asset_id)
    return _render_form(request, db, asset=asset, current_user=current_user)


@router.post('/{asset_id}/edit')
@require_permission('can_edit_assets')
def asset_update(request: Request, asset_id: int, asset_code: str = Form(...), asset_name: str = Form(...), asset_type: str = Form(...), ip_address: str = Form(default=''), model: str = Form(default=''), serial_number: str = Form(default=''), department: str = Form(default=''), assigned_user: str = Form(default=''), location: str = Form(default=''), purchase_date: str = Form(default=''), warranty_expiry: str = Form(default=''), status: str = Form(default='in_stock'), notes: str = Form(default=''), db: Session = Depends(get_db), current_user=None):
    asset = db.get(Asset, asset_id)
    new_user = assigned_user.strip() or None
    old_status = asset.status
    asset.asset_code = asset_code.strip()
    asset.asset_name = asset_name.strip()
    asset.asset_type, asset.category_id = _resolve_asset_type_value(db, asset_type)
    asset.ip_address = ip_address.strip() or None
    asset.model = model.strip() or None
    asset.serial_number = serial_number.strip() or None
    asset.department = department.strip() or None
    asset.department_id = _resolve_department_id(db, department)
    asset.location = location.strip() or None
    asset.location_id = _resolve_location_id(db, location)
    asset.purchase_date = purchase_date.strip() or None
    asset.warranty_expiry = warranty_expiry.strip() or None
    requested_status = status
    if new_user and _normalize_status(status) == 'in_stock':
        requested_status = 'assigned'
    elif not new_user and _normalize_status(status) == 'assigned':
        requested_status = 'in_stock'
    try:
        previous_status, current_status = _set_asset_status(db, asset, requested_status, current_user.username, 'Cập nhật thông tin asset')
    except ValueError as exc:
        return _render_form(request, db, asset=asset, error=str(exc), current_user=current_user)
    asset.notes = notes.strip() or None
    _apply_assignment_change(db, asset, new_user, current_user.username, 'Cập nhật thông tin asset')
    if old_status != asset.status:
        _log_event(db, asset.id, 'asset_status_changed', 'Đổi trạng thái asset', f'{previous_status} -> {current_status}', current_user.username)
    _log_event(db, asset.id, 'asset_updated', 'Cập nhật asset', f'Cập nhật thông tin thiết bị {asset.asset_code}', current_user.username)
    db.commit()
    return RedirectResponse(url=f'/assets/{asset_id}', status_code=303)

