from typing import Any
from datetime import datetime
import io

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
import openpyxl
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import has_permission, require_module_access, require_permission
from app.db.models import Asset, AssetAssignment, AssetType, Department, Employee, Location, AssetStatus
from app.db.session import get_db
from app.services.audit import log_audit
from app.services.asset_service import (
    ASSET_STATUSES,
    STATUS_LABELS,
    IMPORT_HEADERS,
    REQUIRED_IMPORT_HEADERS,
    normalize_asset_status as _normalize_status,
    days_to_warranty as _days_to_warranty,
    log_asset_event as _log_event,
    resolve_department_id as _resolve_department_id,
    resolve_asset_type_value as _resolve_asset_type_value,
    resolve_location_id as _resolve_location_id,
    resolve_status_value as _resolve_status_value,
    resolve_employee_id as _resolve_employee_id,
    set_asset_status as _set_asset_status,
    allowed_transitions_for as _allowed_transitions_for,
    get_active_assignment as _get_active_assignment,
    close_active_assignment as _close_active_assignment,
    create_assignment as _create_assignment,
    apply_assignment_change as _apply_assignment_change,
    filtered_assets as _filtered_assets,
    load_import_rows as _load_import_rows,
    rows_from_preview_token as _rows_from_preview_token,
    build_import_preview as _build_import_preview,
    commit_import_rows as _commit_import_rows,
)
from app.services.zalo import send_zalo_notification

router = APIRouter(prefix='/assets', tags=['assets'])
templates = Jinja2Templates(directory='app/templates')


# ---------------------------------------------------------------------------
# Presentation helpers (view/template concerns only)
# ---------------------------------------------------------------------------

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
    employee_rows = db.scalars(select(Employee).where(Employee.is_active == True).order_by(Employee.full_name.asc())).all()
    location_rows = db.scalars(select(Location).where(Location.is_active == True).order_by(Location.name.asc())).all()
    status_rows = db.scalars(select(AssetStatus).where(AssetStatus.is_active == True).order_by(AssetStatus.sort_order.asc(), AssetStatus.name.asc())).all()
    return {
        'asset_type_options': asset_type_rows,
        'department_options': department_rows,
        'employee_options': employee_rows,
        'location_options': location_rows,
        'status_options': status_rows,
    }


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


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get('/api/list')
@require_module_access('assets')
def asset_api_list(request: Request, db: Session = Depends(get_db), current_user: Any = None, status: str | None = Query(None)):
    try:
        stmt = select(Asset)
        stmt = stmt.where(Asset.asset_type != 'Camera')
        if status:
            raw_status = status.strip().lower()
            stmt = stmt.where(Asset.status == raw_status)
        else:
            stmt = stmt.where(Asset.status.in_(['assigned', 'in_stock']))
        assets = db.scalars(stmt.order_by(Asset.asset_code.asc())).all()
        return {
            'items': [
                {
                    'id': a.id,
                    'asset_code': a.asset_code,
                    'asset_name': a.asset_name,
                    'asset_type': a.asset_type,
                    'department': a.department or 'Chưa phân loại',
                } for a in assets
            ]
        }
    except Exception as e:
        return {'items': [], 'error': str(e)}


@router.get('/', response_class=HTMLResponse)
@require_module_access('assets')
def asset_list(request: Request, q: str | None = Query(default=None), asset_type: str | None = Query(default=None), department: str | None = Query(default=None), status: str | None = Query(default=None), warranty: str | None = Query(default=None), filter: str | None = Query(default=None), db: Session = Depends(get_db), current_user=None):
    assets = [_asset_view_model(asset) for asset in _filtered_assets(db, q=q, asset_type=asset_type, department=department, status=status, warranty=warranty, filter=filter)]
    asset_types = sorted(r for r in db.scalars(
        select(Asset.asset_type).where(Asset.asset_type.is_not(None), Asset.asset_type != '', Asset.asset_type != 'Camera').distinct()
    ).all() if r)
    departments = sorted(r for r in db.scalars(
        select(Asset.department).where(Asset.department.is_not(None), Asset.department != '').distinct()
    ).all() if r)
    statuses = ASSET_STATUSES
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
        'days_to_warranty': _days_to_warranty,
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
            asset.notes or '',
        ])
    stream = io.BytesIO()
    wb.save(stream)
    content = stream.getvalue()
    return Response(
        content=content,
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={
            'Content-Disposition': 'attachment; filename="assets_export.xlsx"',
            'Content-Length': str(len(content)),
        },
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
            'Content-Length': str(len(content)),
        },
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
            log_audit(db, actor=current_user.username if current_user else None, module='assets', action='bulk_update', entity_type='asset', entity_id=asset.id, metadata={'updates': updates})
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
            log_audit(db, actor=current_user.username if current_user else None, module='assets', action='bulk_archive', entity_type='asset', entity_id=asset.id, metadata={'from_status': 'not_retired', 'to_status': 'retired'})
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
    restorable_statuses = {'retired', 'disposed', 'lost'}
    updated_count = 0
    for asset_id in ids:
        asset = db.get(Asset, asset_id)
        if not asset:
            continue
        normalized_status = _normalize_status(asset.status)
        if normalized_status not in restorable_statuses:
            continue
        previous_status = normalized_status
        try:
            _old_status, current_status = _set_asset_status(db, asset, 'in_stock', current_user.username, 'Cập nhật hàng loạt: khôi phục asset')
        except ValueError:
            continue
        _log_event(db, asset.id, 'asset_restored', 'Khôi phục asset', f'Cập nhật hàng loạt: {previous_status} -> {current_status} cho {asset.asset_code}', current_user.username)
        log_audit(db, actor=current_user.username if current_user else None, module='assets', action='bulk_restore', entity_type='asset', entity_id=asset.id, metadata={'from_status': previous_status, 'to_status': 'in_stock'})
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
def asset_assign(asset_id: int, request: Request, background_tasks: BackgroundTasks, assigned_user: str = Form(...), department: str = Form(default=''), note: str = Form(default=''), db: Session = Depends(get_db), current_user=None):
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
    background_tasks.add_task(
        send_zalo_notification,
        title=f'CẤP PHÁT TÀI SẢN #{asset.asset_code}',
        description=f'{asset.asset_name} đã được cấp phát',
        Người_nhận=new_user,
        Bộ_phận=department.strip() or asset.department or 'Không xác định',
        Ghi_chú=note.strip() or 'Cấp phát asset',
    )
    return RedirectResponse(url=f'/assets/{asset_id}', status_code=303)


@router.post('/{asset_id}/return')
@require_permission('can_edit_assets')
def asset_return(asset_id: int, request: Request, background_tasks: BackgroundTasks, note: str = Form(default=''), db: Session = Depends(get_db), current_user=None):
    asset = db.get(Asset, asset_id)
    if not asset:
        return RedirectResponse(url='/assets/', status_code=303)
    if not asset.assigned_user:
        return RedirectResponse(url=f'/assets/{asset_id}', status_code=303)
    previous_user = asset.assigned_user
    _close_active_assignment(db, asset, current_user.username, note.strip() or 'Thu hồi asset', close_status='returned')
    previous_status, current_status = _set_asset_status(db, asset, 'in_stock', current_user.username, note.strip() or 'Thu hồi asset')
    if previous_status != current_status:
        _log_event(db, asset.id, 'asset_status_changed', 'Đổi trạng thái asset', f'{previous_status} -> {current_status}', current_user.username)
    log_audit(db, actor=current_user.username if current_user else None, module='assets', action='return', entity_type='asset', entity_id=asset.id, metadata={'returned_user': previous_user})
    db.commit()
    background_tasks.add_task(
        send_zalo_notification,
        title=f'THU HỒI TÀI SẢN #{asset.asset_code}',
        description=f'{asset.asset_name} đã được thu hồi',
        Người_trả=previous_user,
        Ghi_chú=note.strip() or 'Thu hồi asset',
    )
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
