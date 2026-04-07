from types import SimpleNamespace

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_login, require_permission
from app.db.models import User
from app.db.session import get_db
from app.security import hash_password, verify_password

router = APIRouter(prefix='/users', tags=['users'])
templates = Jinja2Templates(directory='app/templates')
MIN_PASSWORD_LENGTH = 8
MODULE_KEYS = ['dashboard', 'assets', 'maintenance', 'incidents', 'resources', 'documents']
ACTION_KEYS = [
    'create_assets', 'edit_assets', 'import_assets', 'export_assets',
    'create_maintenance', 'edit_maintenance', 'export_maintenance',
    'create_incidents', 'edit_incidents', 'export_incidents',
    'manage_users', 'manage_system', 'manage_resources', 'manage_documents',
]


def _module_flags_from_form(can_view_dashboard: str | None, can_view_assets: str | None, can_view_maintenance: str | None, can_view_incidents: str | None, can_view_resources: str | None, can_view_documents: str | None):
    return {
        'can_view_dashboard': can_view_dashboard == 'true',
        'can_view_assets': can_view_assets == 'true',
        'can_view_maintenance': can_view_maintenance == 'true',
        'can_view_incidents': can_view_incidents == 'true',
        'can_view_resources': can_view_resources == 'true',
        'can_view_documents': can_view_documents == 'true',
    }


def _action_flags_from_form(**values):
    return {f'can_{key}': values.get(f'can_{key}') == 'true' for key in ACTION_KEYS}


def _apply_role_defaults(role: str, module_flags: dict, action_flags: dict):
    if role == 'admin':
        for key in list(module_flags):
            module_flags[key] = True
        for key in list(action_flags):
            action_flags[key] = True
        return module_flags, action_flags
    if role == 'technician':
        module_flags['can_view_dashboard'] = True
        module_flags['can_view_assets'] = True
        module_flags['can_view_maintenance'] = True
        module_flags['can_view_incidents'] = True
        action_flags['can_create_maintenance'] = True
        action_flags['can_edit_maintenance'] = True
        action_flags['can_export_maintenance'] = True
        action_flags['can_create_incidents'] = True
        action_flags['can_edit_incidents'] = True
    if action_flags.get('can_manage_resources'):
        module_flags['can_view_resources'] = True
    if action_flags.get('can_manage_documents'):
        module_flags['can_view_documents'] = True
    return module_flags, action_flags


def _build_form_user(*, username: str = '', role: str = 'user', full_name: str = '', is_active: bool = True, module_flags: dict | None = None, action_flags: dict | None = None, existing_user: User | None = None):
    module_flags = module_flags or {f'can_view_{key}': key not in ('resources', 'documents') for key in MODULE_KEYS}
    action_flags = action_flags or {
        'can_create_assets': False,
        'can_edit_assets': False,
        'can_import_assets': False,
        'can_export_assets': False,
        'can_create_maintenance': False,
        'can_edit_maintenance': False,
        'can_export_maintenance': False,
        'can_create_incidents': True,
        'can_edit_incidents': False,
        'can_export_incidents': False,
        'can_manage_users': False,
        'can_manage_system': False,
        'can_manage_resources': False,
        'can_manage_documents': False,
    }
    base = {
        'id': existing_user.id if existing_user else None,
        'username': existing_user.username if existing_user else username.strip(),
        'role': role,
        'full_name': full_name.strip() or None,
        'is_active': is_active,
    }
    base.update(module_flags)
    base.update(action_flags)
    return SimpleNamespace(**base)


def _render_user_form(request: Request, current_user, *, user_obj=None, error: str | None = None):
    return templates.TemplateResponse('users/form.html', {'request': request, 'user_obj': user_obj, 'current_user': current_user, 'error': error})


@router.get('/', response_class=HTMLResponse)
@require_permission('can_manage_users')
def user_list(request: Request, db: Session = Depends(get_db), current_user=None):
    users = db.scalars(select(User).order_by(User.username.asc())).all()
    return templates.TemplateResponse('users/list.html', {'request': request, 'users': users, 'current_user': current_user})


@router.get('/new', response_class=HTMLResponse)
@require_permission('can_manage_users')
def user_new(request: Request, current_user=None):
    return _render_user_form(request, current_user, user_obj=None)


@router.post('/new')
@require_permission('can_manage_users')
def user_create(request: Request, username: str = Form(...), password: str = Form(...), role: str = Form(...), full_name: str = Form(default=''), can_view_dashboard: str | None = Form(default=None), can_view_assets: str | None = Form(default=None), can_view_maintenance: str | None = Form(default=None), can_view_incidents: str | None = Form(default=None), can_view_resources: str | None = Form(default=None), can_create_assets: str | None = Form(default=None), can_edit_assets: str | None = Form(default=None), can_import_assets: str | None = Form(default=None), can_export_assets: str | None = Form(default=None), can_create_maintenance: str | None = Form(default=None), can_edit_maintenance: str | None = Form(default=None), can_export_maintenance: str | None = Form(default=None), can_create_incidents: str | None = Form(default=None), can_edit_incidents: str | None = Form(default=None), can_export_incidents: str | None = Form(default=None), can_manage_users: str | None = Form(default=None), can_manage_system: str | None = Form(default=None), can_manage_resources: str | None = Form(default=None), can_view_documents: str | None = Form(default=None), can_manage_documents: str | None = Form(default=None), db: Session = Depends(get_db), current_user=None):
    module_flags = _module_flags_from_form(can_view_dashboard, can_view_assets, can_view_maintenance, can_view_incidents, can_view_resources, can_view_documents)
    action_flags = _action_flags_from_form(
        can_create_assets=can_create_assets,
        can_edit_assets=can_edit_assets,
        can_import_assets=can_import_assets,
        can_export_assets=can_export_assets,
        can_create_maintenance=can_create_maintenance,
        can_edit_maintenance=can_edit_maintenance,
        can_export_maintenance=can_export_maintenance,
        can_create_incidents=can_create_incidents,
        can_edit_incidents=can_edit_incidents,
        can_export_incidents=can_export_incidents,
        can_manage_users=can_manage_users,
        can_manage_system=can_manage_system,
        can_manage_resources=can_manage_resources,
        can_manage_documents=can_manage_documents,
    )
    module_flags, action_flags = _apply_role_defaults(role, module_flags, action_flags)
    form_user = _build_form_user(username=username, role=role, full_name=full_name, is_active=True, module_flags=module_flags, action_flags=action_flags)
    existing = db.scalar(select(User).where(User.username == username.strip()))
    if existing:
        return _render_user_form(request, current_user, user_obj=form_user, error='Tài khoản đã tồn tại')
    if len(password.strip()) < MIN_PASSWORD_LENGTH:
        return _render_user_form(request, current_user, user_obj=form_user, error=f'Mật khẩu phải có ít nhất {MIN_PASSWORD_LENGTH} ký tự')
    user = User(username=username.strip(), password='[hashed]', password_hash=hash_password(password), role=role, full_name=full_name.strip() or None, is_active=True, **module_flags, **action_flags)
    db.add(user)
    db.commit()
    return RedirectResponse('/users/', status_code=303)


@router.get('/{user_id}/edit', response_class=HTMLResponse)
@require_permission('can_manage_users')
def user_edit(user_id: int, request: Request, db: Session = Depends(get_db), current_user=None):
    user_obj = db.get(User, user_id)
    return _render_user_form(request, current_user, user_obj=user_obj)


@router.post('/{user_id}/edit')
@require_permission('can_manage_users')
def user_update(request: Request, user_id: int, password: str = Form(default=''), role: str = Form(...), full_name: str = Form(default=''), is_active: str | None = Form(default=None), can_view_dashboard: str | None = Form(default=None), can_view_assets: str | None = Form(default=None), can_view_maintenance: str | None = Form(default=None), can_view_incidents: str | None = Form(default=None), can_view_resources: str | None = Form(default=None), can_create_assets: str | None = Form(default=None), can_edit_assets: str | None = Form(default=None), can_import_assets: str | None = Form(default=None), can_export_assets: str | None = Form(default=None), can_create_maintenance: str | None = Form(default=None), can_edit_maintenance: str | None = Form(default=None), can_export_maintenance: str | None = Form(default=None), can_create_incidents: str | None = Form(default=None), can_edit_incidents: str | None = Form(default=None), can_export_incidents: str | None = Form(default=None), can_manage_users: str | None = Form(default=None), can_manage_system: str | None = Form(default=None), can_manage_resources: str | None = Form(default=None), can_view_documents: str | None = Form(default=None), can_manage_documents: str | None = Form(default=None), db: Session = Depends(get_db), current_user=None):
    user_obj = db.get(User, user_id)
    if not user_obj:
        return RedirectResponse('/users/', status_code=303)
    new_is_active = is_active == 'true'
    module_flags = _module_flags_from_form(can_view_dashboard, can_view_assets, can_view_maintenance, can_view_incidents, can_view_resources, can_view_documents)
    action_flags = _action_flags_from_form(
        can_create_assets=can_create_assets,
        can_edit_assets=can_edit_assets,
        can_import_assets=can_import_assets,
        can_export_assets=can_export_assets,
        can_create_maintenance=can_create_maintenance,
        can_edit_maintenance=can_edit_maintenance,
        can_export_maintenance=can_export_maintenance,
        can_create_incidents=can_create_incidents,
        can_edit_incidents=can_edit_incidents,
        can_export_incidents=can_export_incidents,
        can_manage_users=can_manage_users,
        can_manage_system=can_manage_system,
        can_manage_resources=can_manage_resources,
        can_manage_documents=can_manage_documents,
    )
    module_flags, action_flags = _apply_role_defaults(role, module_flags, action_flags)
    form_user = _build_form_user(role=role, full_name=full_name, is_active=new_is_active, module_flags=module_flags, action_flags=action_flags, existing_user=user_obj)
    if current_user and current_user.id == user_obj.id and role != 'admin':
        return _render_user_form(request, current_user, user_obj=form_user, error='Không thể tự bỏ quyền admin của chính mình')
    if current_user and current_user.id == user_obj.id and not new_is_active:
        return _render_user_form(request, current_user, user_obj=form_user, error='Không thể tự archive tài khoản đang đăng nhập')
    if current_user and current_user.id == user_obj.id and not action_flags.get('can_manage_users', False) and role != 'admin':
        return _render_user_form(request, current_user, user_obj=form_user, error='Không thể tự gỡ quyền quản trị người dùng của chính mình')
    user_obj.role = role
    user_obj.full_name = full_name.strip() or None
    user_obj.is_active = new_is_active
    for key, value in module_flags.items():
        setattr(user_obj, key, value)
    for key, value in action_flags.items():
        setattr(user_obj, key, value)
    if password.strip():
        if len(password.strip()) < MIN_PASSWORD_LENGTH:
            return _render_user_form(request, current_user, user_obj=form_user, error=f'Mật khẩu phải có ít nhất {MIN_PASSWORD_LENGTH} ký tự')
        user_obj.password_hash = hash_password(password)
        user_obj.password = '[hashed]'
    db.commit()
    return RedirectResponse('/users/', status_code=303)


@router.post('/{user_id}/archive')
@require_permission('can_manage_users')
def user_archive(user_id: int, request: Request, db: Session = Depends(get_db), current_user=None):
    user_obj = db.get(User, user_id)
    if not user_obj:
        return RedirectResponse('/users/', status_code=303)
    if current_user and current_user.id == user_obj.id:
        return RedirectResponse('/users/', status_code=303)
    user_obj.is_active = False
    db.commit()
    return RedirectResponse('/users/', status_code=303)


@router.post('/{user_id}/restore')
@require_permission('can_manage_users')
def user_restore(user_id: int, request: Request, db: Session = Depends(get_db), current_user=None):
    user_obj = db.get(User, user_id)
    if not user_obj:
        return RedirectResponse('/users/', status_code=303)
    user_obj.is_active = True
    db.commit()
    return RedirectResponse('/users/', status_code=303)


@router.get('/change-password', response_class=HTMLResponse)
@require_login
def change_password_page(request: Request, force: int = Query(default=0), current_user=None):
    return templates.TemplateResponse('users/change_password.html', {'request': request, 'current_user': current_user, 'error': None, 'force_change': bool(force)})


@router.post('/change-password')
@require_login
def change_password_submit(request: Request, old_password: str = Form(...), new_password: str = Form(...), confirm_new_password: str = Form(...), force: str = Form(default=''), db: Session = Depends(get_db), current_user=None):
    user_obj = db.get(User, current_user.id)
    force_change = force == '1'
    if not (verify_password(old_password, user_obj.password_hash) or verify_password(old_password, user_obj.password)):
        return templates.TemplateResponse('users/change_password.html', {'request': request, 'current_user': current_user, 'error': 'Mật khẩu cũ không đúng', 'force_change': force_change})
    if new_password != confirm_new_password:
        return templates.TemplateResponse('users/change_password.html', {'request': request, 'current_user': current_user, 'error': 'Mật khẩu nhập lại không khớp', 'force_change': force_change})
    if len(new_password.strip()) < MIN_PASSWORD_LENGTH:
        return templates.TemplateResponse('users/change_password.html', {'request': request, 'current_user': current_user, 'error': f'Mật khẩu mới phải có ít nhất {MIN_PASSWORD_LENGTH} ký tự', 'force_change': force_change})
    if verify_password(new_password, user_obj.password_hash) or new_password == old_password:
        return templates.TemplateResponse('users/change_password.html', {'request': request, 'current_user': current_user, 'error': 'Mật khẩu mới phải khác mật khẩu cũ', 'force_change': force_change})
    user_obj.password_hash = hash_password(new_password)
    user_obj.password = '[hashed]'
    db.commit()
    return RedirectResponse('/', status_code=303)
