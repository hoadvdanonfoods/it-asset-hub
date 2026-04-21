from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import require_permission
from app.db.models import Asset, AssetAssignment, User
from app.db.models.master_data import AssetType, Department, Employee, Location
from app.security import hash_password
from app.db.models.master_reference import AssetCategory, AssetStatus, Vendor, IncidentCategory, Priority, MaintenanceType
from app.db.session import get_db
from app.services.audit import log_audit

import base64
import io
import json
import openpyxl

router = APIRouter(prefix='/master-data', tags=['master_data'])
templates = Jinja2Templates(directory='app/templates')


def _md_preview_token(rows_cleaned: list[dict], filename: str) -> str:
    payload = {'filename': filename, 'rows': rows_cleaned}
    return base64.urlsafe_b64encode(json.dumps(payload, ensure_ascii=False).encode('utf-8')).decode('ascii')


def _rows_from_md_token(token: str) -> tuple[list[dict], str]:
    decoded = base64.urlsafe_b64decode(token.encode('ascii'))
    payload = json.loads(decoded.decode('utf-8'))
    return payload['rows'], payload.get('filename', 'import.xlsx')


def _build_md_preview(rows_cleaned: list[dict], config: dict, db: Session, filename: str) -> dict:
    unique_field = config.get('unique_field')
    created = updated = 0
    sample_rows = []
    for i, cleaned in enumerate(rows_cleaned):
        unique_value = cleaned.get(unique_field) if unique_field else None
        if unique_field and unique_value not in (None, ''):
            existing = db.scalar(select(config['model']).where(getattr(config['model'], unique_field) == unique_value))
            action = 'update' if existing else 'create'
        else:
            action = 'create'
        if action == 'create':
            created += 1
        else:
            updated += 1
        name_val = cleaned.get('name') or cleaned.get('full_name') or ''
        sample_rows.append({
            'row_number': i + 2,
            'code': cleaned.get(unique_field, '') if unique_field else '',
            'name': name_val,
            'action': action,
        })
    return {
        'filename': filename,
        'created': created,
        'updated': updated,
        'total_rows': created + updated,
        'sample_rows': sample_rows,
        'token': _md_preview_token(rows_cleaned, filename),
    }

def _auto_create_user_for_employee(employee, db: Session) -> bool:
    code = getattr(employee, 'employee_code', None)
    if not code:
        return False
    existing = db.scalar(select(User).where(User.username == code))
    if existing:
        return False
    db.add(User(
        username=code,
        password=code,
        password_hash=hash_password(code),
        role='user',
        full_name=getattr(employee, 'full_name', None),
        is_active=True,
        must_change_password=True,
        can_view_dashboard=True,
        can_view_assets=False,
        can_view_maintenance=False,
        can_view_incidents=True,
        can_view_resources=False,
        can_create_assets=False,
        can_edit_assets=False,
        can_import_assets=False,
        can_export_assets=False,
        can_create_maintenance=False,
        can_edit_maintenance=False,
        can_export_maintenance=False,
        can_create_incidents=True,
        can_edit_incidents=False,
        can_export_incidents=False,
        can_manage_users=False,
        can_manage_system=False,
        can_manage_resources=False,
        can_view_documents=False,
        can_manage_documents=False,
    ))
    return True


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
            {'key': 'department_id', 'label': 'Phòng ban', 'type': 'select', 'placeholder': 'Chọn phòng ban', 'options_source': 'departments', 'option_value': 'id', 'option_label': 'name'},
            {'key': 'title', 'label': 'Chức danh', 'type': 'text', 'placeholder': 'VD: IT Support'},
            {'key': 'email', 'label': 'Email', 'type': 'email', 'placeholder': 'name@company.com'},
            {'key': 'phone', 'label': 'Số điện thoại', 'type': 'text', 'placeholder': '090xxxxxxx'},
            {'key': 'is_active', 'label': 'Kích hoạt', 'type': 'boolean'},
            {'key': 'note', 'label': 'Ghi chú', 'type': 'textarea', 'placeholder': 'Thông tin bổ sung...'},
        ],
        'table_columns': ['employee_code', 'full_name', 'department_id', 'title', 'email', 'phone', 'is_active'],
        'table_display': {'department_id': 'department_name'},
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


def _get_form_options(db: Session, config):
    options = {}
    sources = {
        'departments': db.scalars(select(Department).where(Department.is_active == True).order_by(Department.name.asc())).all(),  # noqa: E712
        'employees': db.scalars(select(Employee).where(Employee.is_active == True).order_by(Employee.full_name.asc())).all(),  # noqa: E712
        'locations': db.scalars(select(Location).where(Location.is_active == True).order_by(Location.name.asc())).all(),  # noqa: E712
        'asset_types': db.scalars(select(AssetType).where(AssetType.is_active == True).order_by(AssetType.name.asc())).all(),  # noqa: E712
        'asset_categories': db.scalars(select(AssetCategory).where(AssetCategory.is_active == True).order_by(AssetCategory.name.asc())).all(),  # noqa: E712
        'asset_statuses': db.scalars(select(AssetStatus).where(AssetStatus.is_active == True).order_by(AssetStatus.sort_order.asc(), AssetStatus.name.asc())).all(),  # noqa: E712
        'vendors': db.scalars(select(Vendor).where(Vendor.is_active == True).order_by(Vendor.name.asc())).all(),  # noqa: E712
        'priorities': db.scalars(select(Priority).where(Priority.is_active == True).order_by(Priority.sort_order.asc(), Priority.name.asc())).all(),  # noqa: E712
        'incident_categories': db.scalars(select(IncidentCategory).where(IncidentCategory.is_active == True).order_by(IncidentCategory.name.asc())).all(),  # noqa: E712
        'maintenance_types': db.scalars(select(MaintenanceType).where(MaintenanceType.is_active == True).order_by(MaintenanceType.name.asc())).all(),  # noqa: E712
    }
    for field in config['columns']:
        source_name = field.get('options_source')
        if source_name:
            options[field['key']] = sources.get(source_name, [])
    return options


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


# Map FK field -> (model, pk column) for FK validation during import
_FK_FIELD_MODELS = {
    'department_id': (Department, 'id'),
}


def _sanitize_fk_fields(cleaned: dict, db: Session) -> dict:
    """Replace any FK id values that don't exist in the target DB with None."""
    for field_key, (model, pk_col) in _FK_FIELD_MODELS.items():
        if field_key not in cleaned:
            continue
        raw_id = cleaned[field_key]
        if raw_id is None:
            continue
        exists = db.scalar(select(model).where(getattr(model, pk_col) == raw_id))
        if not exists:
            cleaned[field_key] = None
    return cleaned


@router.get('/{model_name}', response_class=HTMLResponse)
@require_permission('can_manage_system')
async def list_model(request: Request, model_name: str, current_user=None, db: Session = Depends(get_db)):
    config = _get_config(model_name)
    if not config:
        return RedirectResponse('/', status_code=303)
    items = db.scalars(select(config['model']).order_by(config['model'].id.asc())).all()
    if model_name == 'employees':
        department_lookup = {dept.id: dept.name for dept in db.scalars(select(Department)).all()}
        for item in items:
            item.department_name = department_lookup.get(getattr(item, 'department_id', None), '')
    return templates.TemplateResponse(
        'master_data/list.html',
        {
            'request': request,
            'current_user': current_user,
            'model_name': model_name,
            'config': config,
            'items': items,
            'field_options': _get_form_options(db, config),
            'p': '/master-data/' + model_name,
        },
    )


@router.get('/{model_name}/bulk-edit', response_class=HTMLResponse)
@require_permission('can_manage_system')
async def bulk_edit_model(request: Request, model_name: str, current_user=None, db: Session = Depends(get_db)):
    config = _get_config(model_name)
    if not config:
        return RedirectResponse('/', status_code=303)
    return RedirectResponse(f'/master-data/{model_name}', status_code=303)


@router.post('/{model_name}/create')
@require_permission('can_manage_system')
async def create_model(request: Request, model_name: str, current_user=None, db: Session = Depends(get_db)):
    config = _get_config(model_name)
    if not config:
        return RedirectResponse('/', status_code=303)
    form = await request.form()
    data = _parse_form_data(form, config)
    new_obj = config['model'](**data)
    db.add(new_obj)
    if model_name == 'employees':
        db.flush()
        _auto_create_user_for_employee(new_obj, db)
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


@router.post('/{model_name}/bulk-edit')
@require_permission('can_manage_system')
async def bulk_edit_model_submit(request: Request, model_name: str, current_user=None, db: Session = Depends(get_db)):
    config = _get_config(model_name)
    if not config:
        return RedirectResponse('/', status_code=303)

    form = await request.form()
    item_ids_raw = (form.get('item_ids') or '').strip()
    if not item_ids_raw:
        return RedirectResponse(f'/master-data/{model_name}', status_code=303)

    item_ids = []
    for token in item_ids_raw.split(','):
        token = token.strip()
        if token.isdigit():
            item_ids.append(int(token))

    items = db.scalars(select(config['model']).where(config['model'].id.in_(item_ids))).all() if item_ids else []

    updates = {}
    for field in config['columns']:
        key = field['key']
        raw = form.get(key)
        if field['type'] == 'boolean':
            if raw in (None, ''):
                continue
            updates[key] = str(raw).strip().lower() == 'true'
            continue

        value = raw.strip() if isinstance(raw, str) else raw
        if value in (None, ''):
            continue
        if field['type'] == 'number':
            try:
                value = int(value)
            except (TypeError, ValueError):
                continue
        updates[key] = value

    for item in items:
        for key, value in updates.items():
            setattr(item, key, value)

    db.commit()
    return RedirectResponse(f'/master-data/{model_name}', status_code=303)


def _redirect_with_bulk_feedback(model_name: str, *, message: str | None = None, success: int = 0, blocked: int = 0, details: list[str] | None = None, tone: str = 'info'):
    params = [f'bulk_tone={tone}']
    if message:
        params.append(f'bulk_message={message}')
    if success:
        params.append(f'bulk_success={success}')
    if blocked:
        params.append(f'bulk_blocked={blocked}')
    if details:
        params.append(f"bulk_details={' || '.join(details[:12])}")
    query = '&'.join(params)
    return RedirectResponse(f"/master-data/{model_name}{'?' + query if query else ''}", status_code=303)


@router.post('/{model_name}/bulk-archive')
@require_permission('can_manage_system')
async def bulk_archive_model_submit(request: Request, model_name: str, current_user=None, db: Session = Depends(get_db)):
    config = _get_config(model_name)
    if not config:
        return RedirectResponse('/', status_code=303)

    form = await request.form()
    item_ids_raw = (form.get('item_ids') or '').strip()
    confirm_text = (form.get('confirm_text') or '').strip().upper()
    if not item_ids_raw or confirm_text != 'ARCHIVE':
        return _redirect_with_bulk_feedback(model_name, message='Xác nhận không hợp lệ')

    item_ids = []
    for token in item_ids_raw.split(','):
        token = token.strip()
        if token.isdigit():
            item_ids.append(int(token))

    success = 0
    blocked = 0
    details: list[str] = []

    if item_ids:
        items = db.scalars(select(config['model']).where(config['model'].id.in_(item_ids))).all()
        for item in items:
            if not hasattr(item, 'is_active'):
                blocked += 1
                continue

            if model_name == 'employees':
                active_assets = db.scalars(
                    select(Asset).where(
                        or_(Asset.current_assignment_id.is_not(None), Asset.assigned_user == item.full_name)
                    )
                ).all()
                blocking_assets = []
                for asset in active_assets:
                    active_assignment = db.scalar(
                        select(AssetAssignment).where(
                            AssetAssignment.asset_id == asset.id,
                            AssetAssignment.unassigned_at.is_(None),
                            AssetAssignment.employee_id == item.id,
                        ).order_by(AssetAssignment.assigned_at.desc())
                    )
                    if active_assignment or (asset.assigned_user and asset.assigned_user == item.full_name):
                        blocking_assets.append(asset.asset_code)
                if blocking_assets:
                    blocked += 1
                    preview = ', '.join(blocking_assets[:3])
                    suffix = '' if len(blocking_assets) <= 3 else f' và {len(blocking_assets) - 3} tài sản khác'
                    details.append(f'{item.full_name} ({item.employee_code}): còn giữ {len(blocking_assets)} tài sản, gồm {preview}{suffix}')
                    log_audit(db, actor=current_user.username if current_user else None, module='master_data', action='bulk_archive', entity_type='employee', entity_id=item.id, result='skipped', reason='active_assets', metadata={'employee_code': item.employee_code, 'assets': blocking_assets[:10]})
                    continue

            if getattr(item, 'is_active', None) is False:
                blocked += 1
                details.append(f'{getattr(item, config["title_field"], item.id)}: đã inactive')
                continue

            setattr(item, 'is_active', False)
            success += 1
            log_audit(db, actor=current_user.username if current_user else None, module='master_data', action='bulk_archive', entity_type=model_name.rstrip('s'), entity_id=item.id, metadata={'model': model_name, 'title': getattr(item, config['title_field'], None)})

    db.commit()
    tone = 'success' if success and not blocked else 'warning' if blocked else 'info'
    return _redirect_with_bulk_feedback(model_name, message='Đã xử lý inactive hàng loạt', success=success, blocked=blocked, details=details, tone=tone)


@router.post('/{model_name}/bulk-delete')
@require_permission('can_manage_system')
async def bulk_delete_model_submit(request: Request, model_name: str, current_user=None, db: Session = Depends(get_db)):
    config = _get_config(model_name)
    if not config:
        return RedirectResponse('/', status_code=303)

    form = await request.form()
    item_ids_raw = (form.get('item_ids') or '').strip()
    confirm_text = (form.get('confirm_text') or '').strip().upper()
    if not item_ids_raw or confirm_text != 'DELETE':
        return _redirect_with_bulk_feedback(model_name, message='Xác nhận không hợp lệ. Nhập chữ DELETE để tiếp tục.', tone='warning')

    item_ids = [int(t) for t in item_ids_raw.split(',') if t.strip().isdigit()]
    success = 0
    blocked = 0
    details: list[str] = []

    if item_ids:
        items = db.scalars(select(config['model']).where(config['model'].id.in_(item_ids))).all()
        for item in items:
            title = str(getattr(item, config['title_field'], item.id))

            # Block employees with active asset assignments
            if model_name == 'employees':
                active_assignment = db.scalar(
                    select(AssetAssignment).where(
                        AssetAssignment.employee_id == item.id,
                        AssetAssignment.unassigned_at.is_(None),
                    ).limit(1)
                )
                if active_assignment:
                    blocked += 1
                    details.append(f'{title}: còn bàn giao tài sản chưa thu hồi')
                    continue

            try:
                db.delete(item)
                db.flush()
                success += 1
                log_audit(db, actor=current_user.username if current_user else None, module='master_data', action='bulk_delete', entity_type=model_name, entity_id=item.id, metadata={'title': title})
            except IntegrityError:
                db.rollback()
                blocked += 1
                details.append(f'{title}: đang được tham chiếu bởi dữ liệu khác')

    db.commit()
    tone = 'success' if success and not blocked else 'warning' if blocked else 'info'
    return _redirect_with_bulk_feedback(model_name, message=f'Đã xóa {success} bản ghi.', success=success, blocked=blocked, details=details, tone=tone)


@router.post('/employees/bulk-create-users')
@require_permission('can_manage_system')
async def bulk_create_users_for_employees(request: Request, current_user=None, db: Session = Depends(get_db)):
    employees = db.scalars(select(Employee).where(Employee.is_active == True)).all()  # noqa: E712
    existing_usernames = set(db.scalars(select(User.username)).all())
    created = 0
    skipped = 0
    for emp in employees:
        if emp.employee_code and emp.employee_code not in existing_usernames:
            _auto_create_user_for_employee(emp, db)
            existing_usernames.add(emp.employee_code)
            created += 1
        else:
            skipped += 1
    db.commit()
    from urllib.parse import quote
    msg = quote(f'Đã tạo {created} tài khoản mới. {skipped} nhân viên đã có tài khoản hoặc thiếu mã.')
    return RedirectResponse(f'/master-data/employees?bulk_message={msg}&bulk_tone=success', status_code=303)


@router.get('/{model_name}/import', response_class=HTMLResponse)
@require_permission('can_manage_system')
async def import_model_page(request: Request, model_name: str, current_user=None, db: Session = Depends(get_db)):
    config = _get_config(model_name)
    if not config:
        return RedirectResponse('/', status_code=303)
    return templates.TemplateResponse('master_data/import.html', {
        'request': request, 'current_user': current_user,
        'model_name': model_name, 'config': config,
    })


@router.post('/{model_name}/import/preview', response_class=HTMLResponse)
@require_permission('can_manage_system')
async def import_model_preview(request: Request, model_name: str, current_user=None, file: UploadFile = File(...), db: Session = Depends(get_db)):
    config = _get_config(model_name)
    if not config:
        return RedirectResponse('/', status_code=303)
    contents = await file.read()
    workbook = openpyxl.load_workbook(io.BytesIO(contents))
    sheet = workbook.active
    headers = [cell.value for cell in sheet[1]]
    rows_cleaned = []
    for row in sheet.iter_rows(min_row=2, values_only=True):
        cleaned = _clean_import_row(dict(zip(headers, row)), config)
        if any(v is not None and v != '' for v in cleaned.values()):
            rows_cleaned.append(cleaned)
    preview = _build_md_preview(rows_cleaned, config, db, file.filename or 'import.xlsx')
    return templates.TemplateResponse('master_data/import.html', {
        'request': request, 'current_user': current_user,
        'model_name': model_name, 'config': config, 'preview': preview,
    })


@router.post('/{model_name}/import/confirm')
@require_permission('can_manage_system')
async def import_model_confirm(request: Request, model_name: str, current_user=None, preview_token: str = Form(...), db: Session = Depends(get_db)):
    config = _get_config(model_name)
    if not config:
        return RedirectResponse('/', status_code=303)
    rows_cleaned, _ = _rows_from_md_token(preview_token)
    unique_field = config.get('unique_field')
    created = updated = 0
    for cleaned in rows_cleaned:
        # Validate FK references — nullify any IDs that don't exist in target DB
        cleaned = _sanitize_fk_fields(cleaned, db)
        unique_value = cleaned.get(unique_field) if unique_field else None
        existing = None
        if unique_field and unique_value not in (None, ''):
            existing = db.scalar(select(config['model']).where(getattr(config['model'], unique_field) == unique_value))
        if existing:
            for key, value in cleaned.items():
                setattr(existing, key, value)
            updated += 1
        else:
            new_obj = config['model'](**cleaned)
            db.add(new_obj)
            if model_name == 'employees':
                db.flush()
                _auto_create_user_for_employee(new_obj, db)
            created += 1
    db.commit()
    from urllib.parse import quote
    msg = quote(f'Import xong: {created} thêm mới, {updated} cập nhật')
    return RedirectResponse(f'/master-data/{model_name}?bulk_message={msg}&bulk_tone=success', status_code=303)


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
            # Validate FK references — nullify any IDs that don't exist in target DB
            cleaned = _sanitize_fk_fields(cleaned, db)
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
