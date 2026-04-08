from datetime import datetime, date, timedelta
import io

from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response, StreamingResponse
from fastapi.templating import Jinja2Templates
import openpyxl
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_module_access, require_permission
from app.db.models import Asset, Maintenance, AssetEvent
from app.db.session import get_db

router = APIRouter(prefix='/maintenance', tags=['maintenance'])
templates = Jinja2Templates(directory='app/templates')

def format_bangkok_datetime(value) -> str:
    if not value: return ''
    if isinstance(value, str): return value
    return value.strftime('%d/%m/%Y %H:%M')

def status_label(status: str | None) -> str:
    return (status or 'completed').upper()

def priority_label(priority: str | None) -> str:
    return (priority or 'medium').upper()


def _filtered_maintenance(db: Session, technician: str | None = None, asset_code: str | None = None):
    stmt = select(Maintenance).join(Asset, isouter=True).order_by(Maintenance.maintenance_date.desc())
    if technician:
        stmt = stmt.where(Maintenance.technician.ilike(f"%{technician.strip()}%"))
    if asset_code:
        stmt = stmt.where(Asset.asset_code.ilike(f"%{asset_code.strip()}%"))
    return db.scalars(stmt).all()


@router.get('/', response_class=HTMLResponse)
@require_module_access('maintenance')
def maintenance_list(request: Request, technician: str | None = Query(default=None), asset_code: str | None = Query(default=None), db: Session = Depends(get_db), current_user=None):
    items = _filtered_maintenance(db, technician=technician, asset_code=asset_code)
    techs = sorted({i.technician for i in db.scalars(select(Maintenance)).all() if i.technician})
    
    # Add first_day_of_month and today for the filter/reporting modal
    today_dt = datetime.now()
    first_day = today_dt.replace(day=1).strftime('%Y-%m-%d')
    
    return templates.TemplateResponse('maintenance/list.html', {
        'request': request, 
        'items': items, 
        'technician': technician or '', 
        'asset_code': asset_code or '', 
        'techs': techs, 
        'current_user': current_user,
        'today': today_dt.strftime('%Y-%m-%d'),
        'first_day_of_month': first_day
    })


@router.get('/export')
@require_permission('can_export_maintenance')
def maintenance_export(request: Request, start_date: str = Query(None), end_date: str = Query(None), technician: str | None = Query(default=None), asset_code: str | None = Query(default=None), db: Session = Depends(get_db), current_user=None):
    if start_date and end_date:
        ctx = _get_maintenance_report_context(db, start_date, end_date, technician)
        items = ctx["items"]
    else:
        items = _filtered_maintenance(db, technician=technician, asset_code=asset_code)
        
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Maintenance'
    ws.append(['ID', 'Thiết bị', 'Ngày', 'Kỹ thuật viên', 'Chi phí', 'Ngày tiếp theo', 'Nội dung', 'Kết quả'])
    for item in items:
        ws.append([item.id, item.asset.asset_code if item.asset else '', str(item.maintenance_date), item.technician or '', float(item.cost) if item.cost is not None else '', str(item.next_maintenance_date) if item.next_maintenance_date else '', item.description, item.result or ''])
    stream = io.BytesIO()
    wb.save(stream)
    content = stream.getvalue()
    return Response(
        content=content,
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={
            'Content-Disposition': 'attachment; filename="maintenance_export.xlsx"',
            'Content-Length': str(len(content))
        }
    )


@router.get('/new', response_class=HTMLResponse)
@require_permission('can_create_maintenance')
def maintenance_new(request: Request, db: Session = Depends(get_db), current_user=None):
    assets = db.scalars(select(Asset).order_by(Asset.asset_code.asc())).all()
    return templates.TemplateResponse('maintenance/form.html', {'request': request, 'assets': assets, 'item': None, 'current_user': current_user, 'today': datetime.now().strftime('%Y-%m-%d')})


@router.post('/new')
@require_permission('can_create_maintenance')
def maintenance_create(request: Request, asset_id: int = Form(...), maintenance_date: str = Form(...), description: str = Form(...), technician: str = Form(default=''), result: str = Form(default=''), cost: str = Form(default=''), next_maintenance_date: str = Form(default=''), db: Session = Depends(get_db), current_user=None):
    parsed_cost = float(cost) if str(cost).strip() else None
    item = Maintenance(
        asset_id=asset_id, 
        maintenance_date=datetime.strptime(maintenance_date, '%Y-%m-%d').date(), 
        description=description.strip(), 
        technician=technician.strip() or None, 
        result=result.strip() or None, 
        cost=parsed_cost, 
        next_maintenance_date=(datetime.strptime(next_maintenance_date, '%Y-%m-%d').date() if next_maintenance_date else None)
    )
    db.add(item)
    
    # Log event
    event = AssetEvent(
        asset_id=asset_id,
        event_type="maintenance_log",
        title=f"Bảo trì: {technician.strip() or 'N/A'}",
        description=f"Chi tiết: {description.strip()}",
        actor=current_user.username if current_user else "system"
    )
    db.add(event)
    
    db.commit()
    return RedirectResponse(url='/maintenance/', status_code=303)


@router.get('/{maintenance_id}', response_class=HTMLResponse)
@require_module_access('maintenance')
def maintenance_detail(maintenance_id: int, request: Request, db: Session = Depends(get_db), current_user=None):
    item = db.get(Maintenance, maintenance_id)
    return templates.TemplateResponse('maintenance/detail.html', {
        'request': request, 
        'item': item, 
        'current_user': current_user,
        'status_label': status_label,
        'priority_label': priority_label,
        'format_bangkok_datetime': format_bangkok_datetime
    })


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

# ---------------------------------------------------------------------------
# BATCH & REPORTING ENHANCEMENTS
# ---------------------------------------------------------------------------

def _get_maintenance_report_context(db: Session, start_date: str, end_date: str, technician: str = None, asset_type: str = None):
    """Internal helper to fetch maintenance data for reports."""
    start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
    end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
    
    stmt = select(Maintenance).join(Asset).where(
        Maintenance.maintenance_date >= start_dt,
        Maintenance.maintenance_date <= end_dt
    )
    
    if technician:
        stmt = stmt.where(Maintenance.technician == technician)
    if asset_type:
        stmt = stmt.where(Asset.asset_type == asset_type)
        
    items = db.scalars(stmt.order_by(Maintenance.maintenance_date.desc())).all()
    
    return {
        "items": items,
        "start_date": start_date,
        "end_date": end_date,
        "total_cost": sum(float(i.cost or 0) for i in items)
    }

@router.get("/report/preview")
@require_permission("can_export_maintenance")
def maintenance_report_preview(
    request: Request,
    start_date: str,
    end_date: str,
    technician: str = Query(None),
    asset_type: str = Query(None),
    db: Session = Depends(get_db),
    current_user=None
):
    try:
        ctx = _get_maintenance_report_context(db, start_date, end_date, technician, asset_type)
        return templates.TemplateResponse("maintenance/report_preview_table.html", {
            "request": request,
            **ctx
        })
    except Exception as e:
        return HTMLResponse(content=f"<div class='p-8 text-rose-500 font-bold'>Lỗi: {str(e)}</div>")

@router.post("/api/batch")
@require_permission("can_create_maintenance")
async def maintenance_batch_create(
    request: Request,
    db: Session = Depends(get_db),
    current_user=None
):
    try:
        data = await request.json()
        asset_ids = data.get("asset_ids", [])
        m_date = datetime.strptime(data.get("maintenance_date"), "%Y-%m-%d").date()
        desc = data.get("description", "").strip()
        tech = data.get("technician", "").strip() or None
        res_text = data.get("result", "").strip() or None
        cost_val = float(data.get("cost", 0)) if data.get("cost") else None
        next_date = None
        if data.get("next_maintenance_date"):
            next_date = datetime.strptime(data.get("next_maintenance_date"), "%Y-%m-%d").date()

        if not asset_ids:
            return {"success": False, "error": "Chưa chọn thiết bị nào"}

        for aid in asset_ids:
            # 1. Create Maintenance record
            m_record = Maintenance(
                asset_id=aid,
                maintenance_date=m_date,
                description=desc,
                technician=tech,
                result=res_text,
                cost=cost_val,
                next_maintenance_date=next_date
            )
            db.add(m_record)
            
            # 2. Add to Asset History (Event)
            event = AssetEvent(
                asset_id=aid,
                event_type="maintenance_log",
                title=f"Bảo trì định kỳ: {tech or 'N/A'}",
                description=f"Nội dung: {desc}\nKết quả: {res_text or 'Hoàn tất'}",
                actor=current_user.username if current_user else "system"
            )
            db.add(event)

        db.commit()
        return {"success": True, "count": len(asset_ids)}
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
