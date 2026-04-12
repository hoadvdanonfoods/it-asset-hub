from datetime import datetime, timedelta

from sqlalchemy import func, select
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.auth import require_module_access
from app.db.models import Asset, Incident, Maintenance
from app.db.session import get_db

router = APIRouter()
templates = Jinja2Templates(directory='app/templates')

ALERT_WARRANTY_DAYS = 30
INCIDENT_OPEN_STATUSES = ['open', 'in_progress', 'waiting_user', 'waiting_vendor']
INCIDENT_FINAL_STATUSES = {'resolved', 'closed', 'cancelled'}
INCIDENT_SLA_HOURS = {
    'low': 24,
    'medium': 8,
    'high': 4,
}


def _parse_asset_date(value: str | None):
    if not value:
        return None
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except ValueError:
        return None


def _normalize_priority(value: str | None) -> str:
    raw = (value or '').strip().lower()
    return raw if raw in INCIDENT_SLA_HOURS else 'medium'


def _incident_due_at(item: Incident):
    if not item or not item.reported_at:
        return None
    return item.reported_at + timedelta(hours=INCIDENT_SLA_HOURS.get(_normalize_priority(item.priority), INCIDENT_SLA_HOURS['medium']))


def _maintenance_due_state(item: Maintenance):
    if not item or not item.next_maintenance_date:
        return 'unscheduled'
    today = datetime.utcnow().date()
    if item.next_maintenance_date < today:
        return 'overdue'
    if item.next_maintenance_date <= today + timedelta(days=7):
        return 'upcoming'
    return 'scheduled'


@router.get('/', response_class=HTMLResponse)
@require_module_access('dashboard')
def dashboard(request: Request, db: Session = Depends(get_db), current_user=None):
    total_assets = db.scalar(select(func.count()).select_from(Asset)) or 0
    open_incidents = db.scalar(select(func.count()).select_from(Incident).where(Incident.status.in_(INCIDENT_OPEN_STATUSES))) or 0
    total_maintenances = db.scalar(select(func.count()).select_from(Maintenance)) or 0
    active_assets = db.scalar(select(func.count()).select_from(Asset).where(Asset.status.in_(['in_stock', 'assigned', 'borrowed', 'repairing']))) or 0

    type_rows = [list(row) for row in db.execute(select(Asset.asset_type, func.count()).group_by(Asset.asset_type).order_by(func.count().desc(), Asset.asset_type.asc())).all()]
    dept_rows = [list(row) for row in db.execute(select(Asset.department, func.count()).where(Asset.department.is_not(None)).group_by(Asset.department).order_by(func.count().desc())).all()]
    status_rows = [list(row) for row in db.execute(select(Incident.status, func.count()).group_by(Incident.status).order_by(func.count().desc())).all()]

    assets = db.scalars(select(Asset).order_by(Asset.asset_code.asc())).all()
    open_incident_items = db.scalars(select(Incident).where(Incident.status.in_(INCIDENT_OPEN_STATUSES)).order_by(Incident.reported_at.asc())).all()
    maintenance_items = db.scalars(select(Maintenance).where(Maintenance.next_maintenance_date.is_not(None)).order_by(Maintenance.next_maintenance_date.asc())).all()

    today = datetime.utcnow().date()
    warranty_expiring = []
    missing_assignment = []
    missing_core_info = []

    for asset in assets:
        expiry = _parse_asset_date(asset.warranty_expiry)
        if expiry:
            days = (expiry - today).days
            if 0 <= days <= ALERT_WARRANTY_DAYS:
                warranty_expiring.append({'asset': asset, 'days': days})
        if asset.status in ('assigned', 'borrowed') and not (asset.assigned_user or '').strip():
            missing_assignment.append(asset)
        if not (asset.serial_number or '').strip() or not (asset.location or '').strip():
            missing_core_info.append(asset)

    overdue_maintenance = [item for item in maintenance_items if _maintenance_due_state(item) == 'overdue' and item.asset and item.asset.status not in ('retired', 'disposed')]
    upcoming_maintenance = [item for item in maintenance_items if _maintenance_due_state(item) == 'upcoming' and item.asset and item.asset.status not in ('retired', 'disposed')]

    overdue_incidents = []
    for item in open_incident_items:
        due_at = _incident_due_at(item)
        if not due_at:
            continue
        if datetime.utcnow() > due_at:
            overdue_incidents.append({'incident': item, 'due_at': due_at, 'priority': _normalize_priority(item.priority)})

    return templates.TemplateResponse('dashboard.html', {
        'request': request, 
        'stats': {'total_assets': total_assets, 'open_incidents': open_incidents, 'total_maintenances': total_maintenances, 'active_assets': active_assets}, 
        'asset_types': type_rows, 
        'departments': dept_rows[:8], 
        'incident_statuses': status_rows, 
        'alerts': {'warranty_expiring': warranty_expiring[:10], 'overdue_maintenance': overdue_maintenance[:10], 'upcoming_maintenance': upcoming_maintenance[:10], 'overdue_incidents': overdue_incidents[:10], 'missing_assignment': missing_assignment[:10], 'missing_core_info': missing_core_info[:10]}, 
        'current_user': current_user
    })
