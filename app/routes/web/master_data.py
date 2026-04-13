from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_permission
from app.db.models.master_data import AssetType, Department, Employee, Location
from app.db.models.master_reference import AssetCategory, AssetStatus, Vendor, IncidentCategory, Priority, MaintenanceType
from app.db.session import get_db

import io
import openpyxl

router = APIRouter(prefix='/master-data', tags=['master_data'])
templates = Jinja2Templates(directory='app/templates')

MODEL_CONFIG = {
    'departments': {
        'label': 'Phòng ban',
        'description': 'Quản lý danh mục phòng ban dùng chung cho tài sản, nhân sự và báo cáo.',
        'icon': 'building',
        'accent': 'blue',
        'model': Department,
        'title_field': 'name',
        'columns': [
            {'key': 'code', 'label': 'Mã', 'type': 'text', 'required': True, 'placeholder': 'VD: IT'},
            {'key': 'name', 'label': 'Tên phòng ban', 'type': 'text', 'required': True, 'placeholder': 'VD: Phòng Công nghệ Thông tin'},
            {'key': 'is_active', 'label': 'Kích hoạt', 'type': 'boolean'},
            {'key': 'note', 'label': 'Ghi chú', 'type': 'textarea', 'placeholder': 'Thông tin bổ sung...'},
        ],
        'table_columns': ['code', 'name', 'is_active', 'note'],
        'unique_field': 'code',
    },
    'employees': {
        'label': 'Nhân viên',
        'description': 'Quản lý danh mục nhân sự cơ bản phục vụ bàn giao tài sản và tra cứu nội bộ.',
        'icon': 'users',
        'accent': 'emerald',
        'model': Employee,
        'title_field': 'full_name',
        'columns': [
            {'key': 'employee_code', 'label': 'Mã nhân viên', 'type': 'text', 'required': True, 'placeholder': 'VD: NV001'},
            {'key': 'full_name', 'label': 'Họ và tên', 'type': 'text', 'required': True, 'placeholder': 'Nguyễn Văn A'},
            {'key': 'department_id', 'label': 'ID phòng ban', 'type': 'number', 'placeholder': 'VD: 1'},
            {'key': 'title', 'label': 'Chức danh', 'type': 'text', 'placeholder': 'VD: IT Support'},
            {'key': 'email', 'label': 'Email', 'type': 'email', 'placeholder': 'name@company.com'},
            {'key': 'phone', 'label': 'Số điện thoại', 'type': 'text', 'placeholder': '090xxxxxxx'},
            {'key': 'is_active', 'label': 'Kích hoạt', 'type': 'boolean'},
            {'key': 'note', 'label': 'Ghi chú', 'type': 'textarea', 'placeholder': 'Thông tin bổ sung...'},
        ],
        'table_columns': ['employee_code', 'full_name', 'department_id', 'title', 'email', 'phone', 'is_active'],
        'unique_field': 'employee_code',
    },
    'asset_types': {
        'label': 'Loại tài sản',
        'description': 'Quản lý danh mục loại tài sản, nhóm phân loại và quy ước đặt mã.',
        'icon': 'tag',
        'accent': 'amber',
        'model': AssetType,
        'title_field': 'name',
        'columns': [
            {'key': 'code', 'label': 'Mã loại', 'type': 'text', 'required': True, 'placeholder': 'VD: LAPTOP'},
            {'key': 'name', 'label': 'Tên loại tài sản', 'type': 'text', 'required': True, 'placeholder': 'VD: Laptop'},
            {'key': 'category_group', 'label': 'Nhóm phân loại', 'type': 'text', 'placeholder': 'VD: User Device'},
            {'key': 'is_active', 'label': 'Kích hoạt', 'type': 'boolean'},
            {'key': 'note', 'label': 'Ghi chú', 'type': 'textarea', 'placeholder': 'Thông tin bổ sung...'},
        ],
        'table_columns': ['code', 'name', 'category_group', 'is_active', 'note'],
        'unique_field': 'code',
    },
    'locations': {
        'label': 'Vị trí',
        'description': 'Quản lý danh mục vị trí, khu vực và điểm đặt tài sản trong hệ thống.',
        'icon': 'map-pin',
        'accent': 'rose',
        'model': Location,
        'title_field': 'name',
        'columns': [
            {'key': 'code', 'label': 'Mã vị trí', 'type': 'text', 'required': True, 'placeholder': 'VD: HN-F1'},
            {'key': 'name', 'label': 'Tên vị trí', 'type': 'text', 'required': True, 'placeholder': 'VD: Hà Nội - Tầng 1'},
            {'key': 'site_group', 'label': 'Nhóm khu vực', 'type': 'text', 'placeholder': 'VD: Head Office'},
            {'key': 'is_active', 'label': 'Kích hoạt', 'type': 'boolean'},
            {'key': 'note', 'label': 'Ghi chú', 'type': 'textarea', 'placeholder': 'Thông tin bổ sung...'},
        ],
        'table_columns': ['code', 'name', 'site_group', 'is_active', 'note'],
        'unique_field': 'code',
    },
    'asset_categories': {
        'label': 'Nhóm tài sản',
        'description': 'Danh mục chuẩn hóa nhóm tài sản cho Phase 1 normalization.',
        'icon': 'boxes',
        'accent': 'violet',
        'model': AssetCategory,
        'title_field': 'name',
        'columns': [
            {'key': 'code', 'label': 'Mã nhóm', 'type': 'text', 'required': True, 'placeholder': 'VD: LAPTOP'},
            {'key': 'name', 'label': 'Tên nhóm', 'type': 'text', 'required': True, 'placeholder': 'VD: Laptop'},
            {'key': 'description', 'label': 'Mô tả', 'type': 'textarea', 'placeholder': 'Thông tin bổ sung...'},
            {'key': 'is_active', 'label': 'Kích hoạt', 'type': 'boolean'},
            {'key': 'sort_order', 'label': 'Thứ tự', 'type': 'number', 'placeholder': '0'},
        ],
        'table_columns': ['code', 'name', 'description', 'is_active', 'sort_order'],
        'unique_field': 'code',
    },
    'asset_statuses': {
        'label': 'Trạng thái tài sản',
        'description': 'Danh mục trạng thái tài sản chuẩn hóa dùng chung.',
        'icon': 'activity',
        'accent': 'emerald',
        'model': AssetStatus,
        'title_field': 'name',
        'columns': [
            {'key': 'code', 'label': 'Mã trạng thái', 'type': 'text', 'required': True, 'placeholder': 'VD: IN_STOCK'},
            {'key': 'name', 'label': 'Tên trạng thái', 'type': 'text', 'required': True, 'placeholder': 'VD: In Stock'},
            {'key': 'description', 'label': 'Mô tả', 'type': 'textarea', 'placeholder': 'Thông tin bổ sung...'},
            {'key': 'is_active', 'label': 'Kích hoạt', 'type': 'boolean'},
            {'key': 'sort_order', 'label': 'Thứ tự', 'type': 'number', 'placeholder': '0'},
        ],
        'table_columns': ['code', 'name', 'description', 'is_active', 'sort_order'],
        'unique_field': 'code',
    },
    'vendors': {
        'label': 'Nhà cung cấp',
        'description': 'Danh mục nhà cung cấp và đối tác bảo trì.',
        'icon': 'truck',
        'accent': 'amber',
        'model': Vendor,
        'title_field': 'name',
        'columns': [
            {'key': 'code', 'label': 'Mã NCC', 'type': 'text', 'required': True, 'placeholder': 'VD: DELL'},
            {'key': 'name', 'label': 'Tên NCC', 'type': 'text', 'required': True, 'placeholder': 'VD: Dell Việt Nam'},
            {'key': 'description', 'label': 'Mô tả', 'type': 'textarea', 'placeholder': 'Thông tin bổ sung...'},
            {'key': 'is_active', 'label': 'Kích hoạt', 'type': 'boolean'},
            {'key': 'sort_order', 'label': 'Thứ tự', 'type': 'number', 'placeholder': '0'},
        ],
        'table_columns': ['code', 'name', 'description', 'is_active', 'sort_order'],
        'unique_field': 'code',
    },
    'incident_categories': {
        'label': 'Nhóm sự cố',
        'description': 'Danh mục phân loại ticket sự cố.',
        'icon': 'shield-alert',
        'accent': 'rose',
        'model': IncidentCategory,
        'title_field': 'name',
        'columns': [
            {'key': 'code', 'label': 'Mã nhóm', 'type': 'text', 'required': True, 'placeholder': 'VD: HARDWARE'},
            {'key': 'name', 'label': 'Tên nhóm', 'type': 'text', 'required': True, 'placeholder': 'VD: Hardware'},
            {'key': 'description', 'label': 'Mô tả', 'type': 'textarea', 'placeholder': 'Thông tin bổ sung...'},
            {'key': 'is_active', 'label': 'Kích hoạt', 'type': 'boolean'},
            {'key': 'sort_order', 'label': 'Thứ tự', 'type': 'number', 'placeholder': '0'},
        ],
        'table_columns': ['code', 'name', 'description', 'is_active', 'sort_order'],
        'unique_field': 'code',
    },
    'priorities': {
        'label': 'Độ ưu tiên',
        'description': 'Danh mục ưu tiên chuẩn hóa cho ticket sự cố.',
        'icon': 'flame',
        'accent': 'orange',
        'model': Priority,
        'title_field': 'name',
        'columns': [
            {'key': 'code', 'label': 'Mã ưu tiên', 'type': 'text', 'required': True, 'placeholder': 'VD: HIGH'},
            {'key': 'name', 'label': 'Tên ưu tiên', 'type': 'text', 'required': True, 'placeholder': 'VD: High'},
            {'key': 'description', 'label': 'Mô tả', 'type': 'textarea', 'placeholder': 'Thông tin bổ sung...'},
            {'key': 'is_active', 'label': 'Kích hoạt', 'type': 'boolean'},
            {'key': 'sort_order', 'label': 'Thứ tự', 'type': 'number', 'placeholder': '0'},
        ],
        'table_columns': ['code', 'name', 'description', 'is_active', 'sort_order'],
        'unique_field': 'code',
    },
    'maintenance_types': {
        'label': 'Loại bảo trì',
        'description': 'Danh mục loại bảo trì chuẩn hóa.',
        'icon': 'wrench',
        'accent': 'yellow',
        'model': MaintenanceType,
        'title_field': 'name',
        'columns': [
            {'key': 'code', 'label': 'Mã loại', 'type': 'text', 'required': True, 'placeholder': 'VD: PREVENTIVE'},
            {'key': 'name', 'label': 'Tên loại', 'type': 'text', 'required': True, 'placeholder': 'VD: Preventive'},
            {'key': 'description', 'label': 'Mô tả', 'type': 'textarea', 'placeholder': 'Thông tin bổ sung...'},
            {'key': 'is_active', 'label': 'Kích hoạt', 'type': 'boolean'},
            {'key': 'sort_order', 'label': 'Thứ tự', 'type': 'number', 'placeholder': '0'},
        ],
        'table_columns': ['code', 'name', 'description', 'is_active', 'sort_order'],
        'unique_field': 'code',
    },
}


def _get_config(model_name: str):
    return MODEL_CONFIG.get(model_name)


def _parse_form_data(request_form, config):
    data = {}
    for field in config['columns']:
        key = field['key']
        if field['type'] == 'boolean':
            data[key] = request_form.get(key) == 'true'
            continue
        raw = request_form.get(key)
        value = raw.strip() if isinstance(raw, str) else raw
        if value == '':
            value = None
        if field['type'] == 'number' and value is not None:
            try:
                value = int(value)
            except (TypeError, ValueError):
                value = None
        data[key] = value
    return data


def _clean_import_row(row_data, config):
    allowed_fields = {field['key'] for field in config['columns'] if field['key'] != 'id'}
    cleaned = {}
    for field in config['columns']:
        key = field['key']
        if key not in allowed_fields:
            continue
        value = row_data.get(key)
        if isinstance(value, str):
            value = value.strip()
        if value == '':
            value = None
        if field['type'] == 'boolean':
            value = str(value).strip().lower() in ('1', 'true', 'yes', 'y', 'on') if value is not None else False
        if field['type'] == 'number' and value is not None:
            try:
                value = int(value)
            except (TypeError, ValueError):
                value = None
        cleaned[key] = value
    return cleaned


@router.get('/{model_name}', response_class=HTMLResponse)
@require_permission('can_manage_system')
async def list_model(request: Request, model_name: str, current_user=None, db: Session = Depends(get_db)):
    config = _get_config(model_name)
    if not config:
        return RedirectResponse('/', status_code=303)
    items = db.scalars(select(config['model']).order_by(config['model'].id.asc())).all()
    return templates.TemplateResponse(
        'master_data/list.html',
        {
            'request': request,
            'current_user': current_user,
            'model_name': model_name,
            'config': config,
            'items': items,
            'p': '/master-data/' + model_name,
        },
    )


@router.post('/{model_name}/create')
@require_permission('can_manage_system')
async def create_model(request: Request, model_name: str, current_user=None, db: Session = Depends(get_db)):
    config = _get_config(model_name)
    if not config:
        return RedirectResponse('/', status_code=303)
    form = await request.form()
    data = _parse_form_data(form, config)
    db.add(config['model'](**data))
    db.commit()
    return RedirectResponse(f'/master-data/{model_name}', status_code=303)


@router.post('/{model_name}/edit/{item_id}')
@require_permission('can_manage_system')
async def edit_model(request: Request, model_name: str, item_id: int, current_user=None, db: Session = Depends(get_db)):
    config = _get_config(model_name)
    if not config:
        return RedirectResponse('/', status_code=303)
    item = db.get(config['model'], item_id)
    if not item:
        return RedirectResponse(f'/master-data/{model_name}', status_code=303)
    form = await request.form()
    data = _parse_form_data(form, config)
    for key, value in data.items():
        setattr(item, key, value)
    db.commit()
    return RedirectResponse(f'/master-data/{model_name}', status_code=303)


@router.post('/{model_name}/import')
@require_permission('can_manage_system')
async def import_model(request: Request, model_name: str, current_user=None, file: UploadFile = File(...), db: Session = Depends(get_db)):
    config = _get_config(model_name)
    if not config:
        return RedirectResponse('/', status_code=303)

    contents = await file.read()
    workbook = openpyxl.load_workbook(io.BytesIO(contents))
    sheet = workbook.active
    headers = [cell.value for cell in sheet[1]]
    unique_field = config.get('unique_field')

    for row in sheet.iter_rows(min_row=2, values_only=True):
        row_data = dict(zip(headers, row))
        cleaned = _clean_import_row(row_data, config)
        if any(v is not None and v != '' for v in cleaned.values()):
            existing = None
            unique_value = cleaned.get(unique_field) if unique_field else None
            if unique_field and unique_value not in (None, ''):
                existing = db.scalar(select(config['model']).where(getattr(config['model'], unique_field) == unique_value))
            if existing:
                for key, value in cleaned.items():
                    setattr(existing, key, value)
            else:
                db.add(config['model'](**cleaned))

    db.commit()
    return RedirectResponse(f'/master-data/{model_name}', status_code=303)


@router.get('/{model_name}/export')
@require_permission('can_manage_system')
async def export_model(model_name: str, current_user=None, db: Session = Depends(get_db)):
    config = _get_config(model_name)
    if not config:
        return RedirectResponse('/', status_code=303)

    items = db.scalars(select(config['model']).order_by(config['model'].id.asc())).all()
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = config['label'][:31]

    columns = [field['key'] for field in config['columns']]
    sheet.append(columns)

    for item in items:
        sheet.append([getattr(item, key, None) for key in columns])

    output = io.BytesIO()
    workbook.save(output)
    output.seek(0)

    filename = f'{model_name}_export.xlsx'
    headers = {'Content-Disposition': f'attachment; filename="{filename}"'}
    return StreamingResponse(output, media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', headers=headers)
