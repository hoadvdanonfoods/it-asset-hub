from datetime import datetime
import io

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
import openpyxl
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_module_access, require_permission
from app.db.models import Asset, Maintenance
from app.db.session import get_db

router = APIRouter(prefix='/maintenance', tags=['maintenance'])
templates = Jinja2Templates(directory='app/templates')


def _filtered_maintenance(db: Session, technician: str | None = None, asset_code: str | None = None):
    items = db.scalars(select(Maintenance).order_by(Maintenance.maintenance_date.desc())).all()
    if technician:
        items = [i for i in items if (i.technician or '').lower() == technician.lower()]
    if asset_code:
        items = [i for i in items if i.asset and asset_code.lower() in i.asset.asset_code.lower()]
    return items


@router.get('/', response_class=HTMLResponse)
@require_module_access('maintenance')
def maintenance_list(request: Request, technician: str | None = Query(default=None), asset_code: str | None = Query(default=None), db: Session = Depends(get_db), current_user=None):
    items = _filtered_maintenance(db, technician=technician, asset_code=asset_code)
    techs = sorted({i.technician for i in db.scalars(select(Maintenance)).all() if i.technician})
    return templates.TemplateResponse('maintenance/list.html', {'request': request, 'items': items, 'technician': technician or '', 'asset_code': asset_code or '', 'techs': techs, 'current_user': current_user})


@router.get('/export')
@require_permission('can_export_maintenance')
def maintenance_export(request: Request, technician: str | None = Query(default=None), asset_code: str | None = Query(default=None), db: Session = Depends(get_db), current_user=None):
    items = _filtered_maintenance(db, technician=technician, asset_code=asset_code)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Maintenance'
    ws.append(['ID', 'Thiết bị', 'Ngày', 'Kỹ thuật viên', 'Chi phí', 'Ngày tiếp theo', 'Nội dung', 'Kết quả'])
    for item in items:
        ws.append([item.id, item.asset.asset_code if item.asset else '', str(item.maintenance_date), item.technician or '', float(item.cost) if item.cost is not None else '', str(item.next_maintenance_date) if item.next_maintenance_date else '', item.description, item.result or ''])
    stream = io.BytesIO()
    wb.save(stream)
    stream.seek(0)
    return StreamingResponse(stream, media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', headers={'Content-Disposition': 'attachment; filename=maintenance_export.xlsx'})


@router.get('/new', response_class=HTMLResponse)
@require_permission('can_create_maintenance')
def maintenance_new(request: Request, db: Session = Depends(get_db), current_user=None):
    assets = db.scalars(select(Asset).order_by(Asset.asset_code.asc())).all()
    return templates.TemplateResponse('maintenance/form.html', {'request': request, 'assets': assets, 'item': None, 'current_user': current_user})


@router.post('/new')
@require_permission('can_create_maintenance')
def maintenance_create(request: Request, asset_id: int = Form(...), maintenance_date: str = Form(...), description: str = Form(...), technician: str = Form(default=''), result: str = Form(default=''), cost: str = Form(default=''), next_maintenance_date: str = Form(default=''), db: Session = Depends(get_db), current_user=None):
    parsed_cost = float(cost) if str(cost).strip() else None
    item = Maintenance(asset_id=asset_id, maintenance_date=datetime.strptime(maintenance_date, '%Y-%m-%d').date(), description=description.strip(), technician=technician.strip() or None, result=result.strip() or None, cost=parsed_cost, next_maintenance_date=(datetime.strptime(next_maintenance_date, '%Y-%m-%d').date() if next_maintenance_date else None))
    db.add(item)
    db.commit()
    return RedirectResponse(url='/maintenance/', status_code=303)


@router.get('/{maintenance_id}', response_class=HTMLResponse)
@require_module_access('maintenance')
def maintenance_detail(maintenance_id: int, request: Request, db: Session = Depends(get_db), current_user=None):
    item = db.get(Maintenance, maintenance_id)
    return templates.TemplateResponse('maintenance/detail.html', {'request': request, 'item': item, 'current_user': current_user})


@router.get('/{maintenance_id}/edit', response_class=HTMLResponse)
@require_permission('can_edit_maintenance')
def maintenance_edit(maintenance_id: int, request: Request, db: Session = Depends(get_db), current_user=None):
    item = db.get(Maintenance, maintenance_id)
    assets = db.scalars(select(Asset).order_by(Asset.asset_code.asc())).all()
    return templates.TemplateResponse('maintenance/form.html', {'request': request, 'assets': assets, 'item': item, 'current_user': current_user})


@router.post('/{maintenance_id}/edit')
@require_permission('can_edit_maintenance')
def maintenance_update(request: Request, maintenance_id: int, asset_id: int = Form(...), maintenance_date: str = Form(...), description: str = Form(...), technician: str = Form(default=''), result: str = Form(default=''), cost: str = Form(default=''), next_maintenance_date: str = Form(default=''), db: Session = Depends(get_db), current_user=None):
    item = db.get(Maintenance, maintenance_id)
    item.asset_id = asset_id
    item.maintenance_date = datetime.strptime(maintenance_date, '%Y-%m-%d').date()
    item.description = description.strip()
    item.technician = technician.strip() or None
    item.result = result.strip() or None
    item.cost = float(cost) if str(cost).strip() else None
    item.next_maintenance_date = datetime.strptime(next_maintenance_date, '%Y-%m-%d').date() if next_maintenance_date else None
    db.commit()
    return RedirectResponse(url=f'/maintenance/{maintenance_id}', status_code=303)
