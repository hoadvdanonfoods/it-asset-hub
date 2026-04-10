import csv
import io
from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.auth import require_admin
from app.db.models import AuditLog
from app.db.session import get_db

router = APIRouter(prefix='/audit', tags=['audit'])
templates = Jinja2Templates(directory='app/templates')


def _build_filters(
    *,
    date_from: str | None,
    date_to: str | None,
    actor: str | None,
    action: str | None,
    module: str | None,
    result: str | None,
    keyword: str | None,
):
    conditions = []
    if date_from:
        try:
            conditions.append(AuditLog.created_at >= datetime.strptime(date_from, '%Y-%m-%d'))
        except ValueError:
            pass
    if date_to:
        try:
            end_dt = datetime.strptime(date_to, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
            conditions.append(AuditLog.created_at <= end_dt)
        except ValueError:
            pass
    if actor:
        conditions.append(AuditLog.actor == actor)
    if action:
        conditions.append(AuditLog.action == action)
    if module:
        conditions.append(AuditLog.module == module)
    if result:
        conditions.append(AuditLog.result == result)
    if keyword:
        like = f'%{keyword.strip()}%'
        conditions.append(
            or_(
                AuditLog.entity_id.ilike(like),
                AuditLog.reason.ilike(like),
                AuditLog.metadata_json.ilike(like),
            )
        )
    return and_(*conditions) if conditions else None


@router.get('/', response_class=HTMLResponse)
@require_admin
def audit_list(
    request: Request,
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    actor: str | None = Query(default=None),
    action: str | None = Query(default=None),
    module: str | None = Query(default=None),
    result: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=10, le=200),
    db: Session = Depends(get_db),
    current_user=None,
):
    stmt = select(AuditLog)
    filters = _build_filters(date_from=date_from, date_to=date_to, actor=actor, action=action, module=module, result=result, keyword=keyword)
    if filters is not None:
        stmt = stmt.where(filters)

    total = len(db.scalars(stmt).all())
    items = db.scalars(stmt.order_by(AuditLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()

    actors = db.scalars(select(AuditLog.actor).where(AuditLog.actor.is_not(None)).distinct().order_by(AuditLog.actor.asc())).all()
    actions = db.scalars(select(AuditLog.action).distinct().order_by(AuditLog.action.asc())).all()
    modules = db.scalars(select(AuditLog.module).distinct().order_by(AuditLog.module.asc())).all()

    return templates.TemplateResponse(
        'audit/list.html',
        {
            'request': request,
            'current_user': current_user,
            'items': items,
            'actors': actors,
            'actions': actions,
            'modules': modules,
            'filters': {
                'date_from': date_from or '',
                'date_to': date_to or '',
                'actor': actor or '',
                'action': action or '',
                'module': module or '',
                'result': result or '',
                'keyword': keyword or '',
            },
            'page': page,
            'page_size': page_size,
            'total': total,
            'total_pages': max(1, (total + page_size - 1) // page_size),
        },
    )


@router.get('/export')
@require_admin
def audit_export(
    request: Request,
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    actor: str | None = Query(default=None),
    action: str | None = Query(default=None),
    module: str | None = Query(default=None),
    result: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user=None,
):
    stmt = select(AuditLog)
    filters = _build_filters(date_from=date_from, date_to=date_to, actor=actor, action=action, module=module, result=result, keyword=keyword)
    if filters is not None:
        stmt = stmt.where(filters)
    rows = db.scalars(stmt.order_by(AuditLog.created_at.desc())).all()

    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(['timestamp', 'actor', 'module', 'action', 'entity_type', 'entity_id', 'result', 'reason', 'metadata'])
    for item in rows:
        writer.writerow([
            item.created_at.isoformat(sep=' ', timespec='seconds') if item.created_at else '',
            item.actor or '',
            item.module,
            item.action,
            item.entity_type,
            item.entity_id or '',
            item.result,
            item.reason or '',
            item.metadata_json or '',
        ])

    content = stream.getvalue().encode('utf-8-sig')
    return Response(
        content=content,
        media_type='text/csv; charset=utf-8',
        headers={'Content-Disposition': 'attachment; filename="audit_logs.csv"'},
    )
