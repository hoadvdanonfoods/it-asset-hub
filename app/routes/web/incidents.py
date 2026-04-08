from datetime import datetime, timezone
import io
from zoneinfo import ZoneInfo

from fastapi import APIRouter, BackgroundTasks, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response, StreamingResponse
from fastapi.templating import Jinja2Templates
import openpyxl
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.auth import require_module_access, require_permission
from app.db.models import Asset, Incident, IncidentEvent
from app.db.session import get_db
from app.services.zalo import send_zalo_notification

router = APIRouter(prefix='/incidents', tags=['incidents'])
templates = Jinja2Templates(directory='app/templates')
INCIDENT_PRIORITIES = ['low', 'medium', 'high']
INCIDENT_STATUSES = ['open', 'in_progress', 'waiting_user', 'waiting_vendor', 'resolved', 'closed', 'cancelled']
INCIDENT_STATUS_META = {
    'open': {'label': 'Mới tiếp nhận', 'badge': 'text-bg-secondary'},
    'in_progress': {'label': 'Đang xử lý', 'badge': 'text-bg-primary'},
    'waiting_user': {'label': 'Chờ người dùng phản hồi', 'badge': 'text-bg-warning'},
    'waiting_vendor': {'label': 'Chờ nhà cung cấp', 'badge': 'text-bg-info'},
    'resolved': {'label': 'Đã xử lý xong', 'badge': 'text-bg-success'},
    'closed': {'label': 'Đã đóng', 'badge': 'text-bg-dark'},
    'cancelled': {'label': 'Đã hủy', 'badge': 'text-bg-light text-dark border'},
}
INCIDENT_PRIORITY_META = {
    'low': {'label': 'Thấp', 'badge': 'text-bg-secondary'},
    'medium': {'label': 'Trung bình', 'badge': 'text-bg-warning'},
    'high': {'label': 'Cao', 'badge': 'text-bg-danger'},
}
FINAL_INCIDENT_STATUSES = {'resolved', 'closed', 'cancelled'}


def format_bangkok_datetime(value: datetime | None) -> str:
    if not value:
        return ''
    dt = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
    return dt.astimezone(ZoneInfo('Asia/Bangkok')).strftime('%d/%m/%Y %H:%M')


def format_vn_date(value: datetime | None) -> str:
    if not value:
        return ''
    dt = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
    return dt.astimezone(ZoneInfo('Asia/Bangkok')).strftime('%d/%m/%Y')


def format_duration(start: datetime | None, end: datetime | None) -> str:
    if not start or not end:
        return ''
    total_minutes = int((end - start).total_seconds() // 60)
    if total_minutes < 60:
        return f'{total_minutes} phút'
    hours, minutes = divmod(total_minutes, 60)
    if hours < 24:
        return f'{hours} giờ {minutes} phút'
    days, hours = divmod(hours, 24)
    return f'{days} ngày {hours} giờ {minutes} phút'


def status_label(status: str | None) -> str:
    key = (status or 'open').strip()
    return INCIDENT_STATUS_META.get(key, {'label': key}).get('label', key)


def status_badge_class(status: str | None) -> str:
    key = (status or 'open').strip()
    return INCIDENT_STATUS_META.get(key, {'badge': 'text-bg-secondary'}).get('badge', 'text-bg-secondary')


def priority_label(priority: str | None) -> str:
    key = (priority or 'medium').strip()
    return INCIDENT_PRIORITY_META.get(key, {'label': key}).get('label', key)


def priority_badge_class(priority: str | None) -> str:
    key = (priority or 'medium').strip()
    return INCIDENT_PRIORITY_META.get(key, {'badge': 'text-bg-warning'}).get('badge', 'text-bg-warning')


def _normalize_status(value: str | None) -> str:
    raw = (value or '').strip().lower()
    aliases = {
        'new': 'open',
        'processing': 'in_progress',
        'done': 'resolved',
        'complete': 'resolved',
        'completed': 'resolved',
        'cancel': 'cancelled',
    }
    normalized = aliases.get(raw, raw or 'open')
    return normalized if normalized in INCIDENT_STATUSES else 'open'


def _normalize_priority(value: str | None) -> str:
    raw = (value or '').strip().lower()
    return raw if raw in INCIDENT_PRIORITIES else 'medium'


def _log_incident_event(db: Session, incident_id: int, event_type: str, title: str, description: str | None = None, actor: str | None = None):
    db.add(IncidentEvent(incident_id=incident_id, event_type=event_type, title=title, description=description, actor=actor))


def _incident_owner_candidates(current_user) -> list[str]:
    values = []
    if not current_user:
        return values
    for value in [current_user.full_name, current_user.username]:
        clean = (value or '').strip()
        if clean and clean not in values:
            values.append(clean)
    return values


def _base_incident_stmt_for_user(current_user):
    stmt = select(Incident)
    if current_user and current_user.role != 'admin' and not getattr(current_user, 'can_edit_incidents', False):
        owner_values = _incident_owner_candidates(current_user)
        if owner_values:
            stmt = stmt.where(or_(*[Incident.reported_by == value for value in owner_values]))
        else:
            stmt = stmt.where(Incident.id == -1)
    return stmt


def _filtered_incidents(db: Session, current_user, status: str | None = None, priority: str | None = None):
    stmt = _base_incident_stmt_for_user(current_user)
    if status:
        stmt = stmt.where(Incident.status == status)
    if priority:
        stmt = stmt.where(Incident.priority == priority)
    return db.scalars(stmt.order_by(Incident.reported_at.desc())).all()


def _can_access_incident(item: Incident | None, current_user) -> bool:
    if not item or not current_user:
        return False
    if current_user.role == 'admin' or getattr(current_user, 'can_edit_incidents', False):
        return True
    owner_values = _incident_owner_candidates(current_user)
    return (item.reported_by or '').strip() in owner_values


def _apply_status_effects(item: Incident, new_status: str):
    if new_status in FINAL_INCIDENT_STATUSES:
        if not item.resolved_at:
            item.resolved_at = datetime.utcnow()
    else:
        item.resolved_at = None


@router.get('/', response_class=HTMLResponse)
@require_module_access('incidents')
def incident_list(request: Request, status: str | None = Query(default=None), priority: str | None = Query(default=None), db: Session = Depends(get_db), current_user=None):
    items = _filtered_incidents(db, current_user, status=status, priority=priority)
    return templates.TemplateResponse('incidents/list.html', {
        'request': request,
        'items': items,
        'status': status or '',
        'priority': priority or '',
        'current_user': current_user,
        'format_bangkok_datetime': format_bangkok_datetime,
        'format_duration': format_duration,
        'status_label': status_label,
        'status_badge_class': status_badge_class,
        'priority_label': priority_label,
        'priority_badge_class': priority_badge_class,
        'incident_statuses': INCIDENT_STATUSES,
        'incident_priorities': INCIDENT_PRIORITIES,
    })


@router.get('/export')
@require_permission('can_export_incidents')
def incident_export(request: Request, status: str | None = Query(default=None), priority: str | None = Query(default=None), db: Session = Depends(get_db), current_user=None):
    items = _filtered_incidents(db, current_user, status=status, priority=priority)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Incidents'
    ws.append(['ID', 'Thiết bị', 'Người báo', 'Bộ phận', 'Ưu tiên', 'Trạng thái', 'Báo lúc', 'Hoàn tất lúc', 'Thời gian xử lý', 'Mô tả', 'Hướng xử lý'])
    for item in items:
        ws.append([item.id, item.asset.asset_code if item.asset else '', item.reported_by or '', item.requester_department or '', priority_label(item.priority), status_label(item.status), str(item.reported_at), str(item.resolved_at) if item.resolved_at else '', format_duration(item.reported_at, item.resolved_at), item.issue_description, item.resolution or ''])
    stream = io.BytesIO()
    wb.save(stream)
    content = stream.getvalue()
    return Response(
        content=content,
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={
            'Content-Disposition': 'attachment; filename="incidents_export.xlsx"',
            'Content-Length': str(len(content))
        }
    )


@router.get('/new', response_class=HTMLResponse)
@require_permission('can_create_incidents')
def incident_new(request: Request, db: Session = Depends(get_db), current_user=None):
    assets = db.scalars(select(Asset).order_by(Asset.asset_code.asc())).all()
    return templates.TemplateResponse('incidents/form.html', {
        'request': request,
        'assets': assets,
        'item': None,
        'current_user': current_user,
        'incident_statuses': INCIDENT_STATUSES,
        'incident_priorities': INCIDENT_PRIORITIES,
        'status_label': status_label,
        'priority_label': priority_label,
    })


@router.post('/new')
@require_permission('can_create_incidents')
def incident_create(request: Request, background_tasks: BackgroundTasks, asset_id: int = Form(...), reported_by: str = Form(default=''), requester_department: str = Form(default=''), issue_description: str = Form(...), priority: str = Form(default='medium'), status: str = Form(default='open'), db: Session = Depends(get_db), current_user=None):
    normalized_priority = _normalize_priority(priority)
    normalized_status = _normalize_status(status if current_user and getattr(current_user, 'can_edit_incidents', False) else 'open')
    effective_reported_by = reported_by.strip() or (current_user.full_name or current_user.username if current_user else None)
    item = Incident(asset_id=asset_id, reported_by=effective_reported_by, requester_department=requester_department.strip() or None, issue_description=issue_description.strip(), priority=normalized_priority, status=normalized_status, reported_at=datetime.utcnow())
    _apply_status_effects(item, normalized_status)
    db.add(item)
    db.flush()
    _log_incident_event(db, item.id, 'incident_created', 'Báo cáo sự cố', f'Ticket được tạo với trạng thái {status_label(item.status)}', current_user.username if current_user else None)
    db.commit()
    
    # Tạm ẩn tính năng gửi Zalo theo yêu cầu
    # background_tasks.add_task(
    #     send_zalo_notification,
    #     title=f"SỰ CỐ MỚI (Mã ID: {item.id})",
    #     description=issue_description.strip(),
    #     Mức_độ=priority_label(item.priority),
    #     Người_báo=effective_reported_by or "Không xác định",
    #     Phòng_ban=requester_department.strip() or "Không xác định"
    # )
    
    return RedirectResponse(url='/incidents/', status_code=303)


@router.get('/{incident_id}', response_class=HTMLResponse)
@require_module_access('incidents')
def incident_detail(incident_id: int, request: Request, db: Session = Depends(get_db), current_user=None):
    item = db.get(Incident, incident_id)
    if not _can_access_incident(item, current_user):
        return RedirectResponse(url='/incidents/', status_code=303)
    return templates.TemplateResponse('incidents/detail.html', {
        'request': request,
        'item': item,
        'current_user': current_user,
        'format_bangkok_datetime': format_bangkok_datetime,
        'format_duration': format_duration,
        'status_label': status_label,
        'status_badge_class': status_badge_class,
        'priority_label': priority_label,
        'priority_badge_class': priority_badge_class,
    })


@router.get('/{incident_id}/request-form', response_class=HTMLResponse)
@require_module_access('incidents')
def incident_request_form(incident_id: int, request: Request, db: Session = Depends(get_db), current_user=None):
    item = db.get(Incident, incident_id)
    if not _can_access_incident(item, current_user):
        return RedirectResponse(url='/incidents/', status_code=303)
    return templates.TemplateResponse('incidents/request_form_print.html', {'request': request, 'item': item, 'current_user': current_user, 'format_vn_date': format_vn_date})


@router.get('/{incident_id}/edit', response_class=HTMLResponse)
@require_permission('can_edit_incidents')
def incident_edit(incident_id: int, request: Request, db: Session = Depends(get_db), current_user=None):
    item = db.get(Incident, incident_id)
    assets = db.scalars(select(Asset).order_by(Asset.asset_code.asc())).all()
    return templates.TemplateResponse('incidents/form.html', {
        'request': request,
        'assets': assets,
        'item': item,
        'current_user': current_user,
        'format_bangkok_datetime': format_bangkok_datetime,
        'incident_statuses': INCIDENT_STATUSES,
        'incident_priorities': INCIDENT_PRIORITIES,
        'status_label': status_label,
        'priority_label': priority_label,
    })


@router.post('/{incident_id}/edit')
@require_permission('can_edit_incidents')
def incident_update(request: Request, incident_id: int, background_tasks: BackgroundTasks, asset_id: int = Form(...), reported_by: str = Form(default=''), requester_department: str = Form(default=''), issue_description: str = Form(...), priority: str = Form(default='medium'), status: str = Form(default='open'), resolution: str = Form(default=''), db: Session = Depends(get_db), current_user=None):
    item = db.get(Incident, incident_id)
    old_status = item.status
    old_priority = item.priority
    old_resolution = item.resolution or ''
    old_department = item.requester_department or ''
    item.asset_id = asset_id
    item.reported_by = reported_by.strip() or None
    item.requester_department = requester_department.strip() or None
    item.issue_description = issue_description.strip()
    item.priority = _normalize_priority(priority)
    item.status = _normalize_status(status)
    item.resolution = resolution.strip() or None

    if old_status != item.status:
        _apply_status_effects(item, item.status)
        _log_incident_event(db, item.id, 'status_changed', 'Đổi trạng thái sự cố', f'{status_label(old_status)} -> {status_label(item.status)}', current_user.username if current_user else None)

    if old_priority != item.priority:
        _log_incident_event(db, item.id, 'priority_changed', 'Cập nhật mức độ ưu tiên', f'{priority_label(old_priority)} -> {priority_label(item.priority)}', current_user.username if current_user else None)

    if (resolution.strip() or '') != old_resolution:
        _log_incident_event(db, item.id, 'resolution_updated', 'Cập nhật hướng xử lý', 'Đã cập nhật nội dung xử lý sự cố', current_user.username if current_user else None)

    if (item.requester_department or '') != old_department:
        _log_incident_event(db, item.id, 'department_updated', 'Cập nhật bộ phận yêu cầu', f'{old_department or "(trống)"} -> {item.requester_department or "(trống)"}', current_user.username if current_user else None)

    db.commit()
    
    # Gửi thông báo Zalo nếu trạng thái chuyển sang Đã giải quyết (hoặc closed)
    # Tạm ẩn tính năng Zalo
    # if item.status in ['resolved', 'closed'] and old_status not in ['resolved', 'closed']:
    #      background_tasks.add_task(
    #         send_zalo_notification,
    #         title=f"SỰ CỐ ĐÃ XỬ LÝ XONG (Mã ID: {item.id})",
    #         description=f"Hướng xử lý: {item.resolution or 'Không có thông tin'}",
    #         Trạng_thái=status_label(item.status),
    #         Mức_độ=priority_label(item.priority),
    #         Người_báo=item.reported_by or "Không rõ"
    #     )
         
    return RedirectResponse(url=f'/incidents/{incident_id}', status_code=303)
