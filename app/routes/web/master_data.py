from fastapi import APIRouter, Depends, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.db.models.master_data import Department, Employee, AssetType, Location
from app.auth import get_current_user, require_permission
import openpyxl
import io

router = APIRouter(prefix="/master-data", tags=["master_data"])
from fastapi.templating import Jinja2Templates
templates = Jinja2Templates(directory="app/templates")

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

MODELS = {'departments': Department, 'employees': Employee, 'asset_types': AssetType, 'locations': Location}

@router.get("/{model_name}", response_class=HTMLResponse)
@require_permission("can_manage_system")
async def list_model(request: Request, model_name: str, db: Session = Depends(get_db)):
    if model_name not in MODELS: return RedirectResponse("/")
    items = db.query(MODELS[model_name]).all()
    # pass p mapped cleanly so nav active state works
    return templates.TemplateResponse("master_data/list.html", {"request": request, "items": items, "model_name": model_name, "p": "/master-data/"+model_name})

@router.post("/{model_name}/create")
@require_permission("can_manage_system")
async def create_model(request: Request, model_name: str, db: Session = Depends(get_db)):
    form = await request.form()
    data = dict(form)
    model = MODELS[model_name]
    new_item = model(**data)
    db.add(new_item)
    db.commit()
    return RedirectResponse(f"/master-data/{model_name}", status_code=303)

@router.post("/{model_name}/edit/{id}")
@require_permission("can_manage_system")
async def edit_model(request: Request, model_name: str, id: int, db: Session = Depends(get_db)):
    form = await request.form()
    data = dict(form)
    item = db.query(MODELS[model_name]).get(id)
    if item:
        for k,v in data.items(): 
            if hasattr(item, k): setattr(item, k, v)
        db.commit()
    return RedirectResponse(f"/master-data/{model_name}", status_code=303)

@router.post("/{model_name}/import")
@require_permission("can_manage_system")
async def import_model(request: Request, model_name: str, file: UploadFile = File(...), db: Session = Depends(get_db)):
    contents = await file.read()
    wb = openpyxl.load_workbook(io.BytesIO(contents))
    sheet = wb.active
    model = MODELS[model_name]
    headers = [cell.value for cell in sheet[1]]
    for row in sheet.iter_rows(min_row=2, values_only=True):
        data = dict(zip(headers, row))
        cleaned = {k:v for k,v in data.items() if hasattr(model, k) and k != 'id'}
        if cleaned: db.add(model(**cleaned))
    db.commit()
    return RedirectResponse(f"/master-data/{model_name}", status_code=303)
