from datetime import datetime, timedelta

from sqlalchemy import and_, func, or_, select
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

    today = datetime.utcnow().date()
    now = datetime.utcnow()
    alert_date = today + timedelta(days=ALERT_WARRANTY_DAYS)

    warranty_expiring_assets = db.scalars(
        select(Asset)
        .where(Asset.warranty_expiry.is_not(None), Asset.warranty_expiry != '')
        .where(Asset.warranty_expiry >= str(today))
        .where(Asset.warranty_expiry <= str(alert_date))
        .order_by(Asset.warranty_expiry.asc())
        .limit(10)
    ).all()
    warranty_expiring = [
        {'asset': a, 'days': (_parse_asset_date(a.warranty_expiry) - today).days}
        for a in warranty_expiring_assets
        if _parse_asset_date(a.warranty_expiry)
    ]

    missing_assignment = db.scalars(
        select(Asset)
        .where(Asset.status.in_(['assigned', 'borrowed']))
        .where(or_(Asset.assigned_user.is_(None), Asset.assigned_user == ''))
        .limit(10)
    ).all()

    missing_core_info = db.scalars(
        select(Asset)
        .where(or_(
            Asset.serial_number.is_(None), Asset.serial_number == '',
            Asset.location.is_(None), Asset.location == '',
        ))
        .limit(10)
    ).all()

    overdue_maintenance = db.scalars(
        select(Maintenance)
        .join(Asset)
        .where(Maintenance.next_maintenance_date.is_not(None))
        .where(Maintenance.next_maintenance_date < today)
        .where(~Asset.status.in_(['retired', 'disposed']))
        .order_by(Maintenance.next_maintenance_date.asc())
        .limit(10)
    ).all()

    upcoming_maintenance = db.scalars(
        select(Maintenance)
        .join(Asset)
        .where(Maintenance.next_maintenance_date.is_not(None))
        .where(Maintenance.next_maintenance_date.between(today, today + timedelta(days=7)))
        .where(~Asset.status.in_(['retired', 'disposed']))
        .order_by(Maintenance.next_maintenance_date.asc())
        .limit(10)
    ).all()

    overdue_incidents_raw = db.scalars(
        select(Incident)
        .where(Incident.status.in_(INCIDENT_OPEN_STATUSES))
        .where(Incident.reported_at.is_not(None))
        .where(or_(
            and_(Incident.priority == 'high',   Incident.reported_at < now - timedelta(hours=INCIDENT_SLA_HOURS['high'])),
            and_(Incident.priority == 'medium',  Incident.reported_at < now - timedelta(hours=INCIDENT_SLA_HOURS['medium'])),
            and_(Incident.priority == 'low',     Incident.reported_at < now - timedelta(hours=INCIDENT_SLA_HOURS['low'])),
            and_(~Incident.priority.in_(['high', 'medium', 'low']), Incident.reported_at < now - timedelta(hours=INCIDENT_SLA_HOURS['medium'])),
        ))
        .order_by(Incident.reported_at.asc())
        .limit(10)
    ).all()
    overdue_incidents = [
        {'incident': item, 'due_at': _incident_due_at(item), 'priority': _normalize_priority(item.priority)}
        for item in overdue_incidents_raw
    ]

    return templates.TemplateResponse('dashboard.html', {
        'request': request,
        'stats': {'total_assets': total_assets, 'open_incidents': open_incidents, 'total_maintenances': total_maintenances, 'active_assets': active_assets},
        'asset_types': type_rows,
        'departments': dept_rows[:8],
        'incident_statuses': status_rows,
        'alerts': {
            'warranty_expiring': warranty_expiring,
            'overdue_maintenance': overdue_maintenance,
            'upcoming_maintenance': upcoming_maintenance,
            'overdue_incidents': overdue_incidents,
            'missing_assignment': missing_assignment,
            'missing_core_info': missing_core_info,
        },
        'current_user': current_user
    })
