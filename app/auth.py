import asyncio
from functools import wraps
from typing import Callable

from fastapi import Request
from fastapi.responses import RedirectResponse
from itsdangerous import URLSafeSerializer
from sqlalchemy import select

from app.config import DEFAULT_ADMIN_PASSWORD, DEFAULT_ADMIN_USERNAME, SESSION_COOKIE_NAME, SECRET_KEY
from app.db.models import User
from app.db.session import SessionLocal
from app.security import verify_password

serializer = URLSafeSerializer(SECRET_KEY, salt='session')
PERMISSION_FIELD_BY_MODULE = {
    'dashboard': 'can_view_dashboard',
    'assets': 'can_view_assets',
    'maintenance': 'can_view_maintenance',
    'incidents': 'can_view_incidents',
    'resources': 'can_view_resources',
    'documents': 'can_view_documents',
}


def get_current_user(request: Request):
    if request is None:
        return None
    cookie = request.cookies.get(SESSION_COOKIE_NAME)
    if not cookie:
        return None
    try:
        data = serializer.loads(cookie)
        username = data.get('username')
    except Exception:
        return None
    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.username == username))
        if user and not user.is_active:
            return None
        return user
    finally:
        db.close()


def _must_force_password_change(user: User) -> bool:
    if not user or user.username != DEFAULT_ADMIN_USERNAME:
        return False
    if user.password == DEFAULT_ADMIN_PASSWORD:
        return True
    if user.password_hash and verify_password(DEFAULT_ADMIN_PASSWORD, user.password_hash):
        return True
    return False


def has_permission(user: User | None, field_name: str) -> bool:
    if not user:
        return False
    if user.role == 'admin':
        return True
    return bool(getattr(user, field_name, False))


def has_module_access(user: User | None, module: str) -> bool:
    field_name = PERMISSION_FIELD_BY_MODULE.get(module)
    if not field_name:
        return False
    return has_permission(user, field_name)


def get_default_landing_path(user: User | None) -> str:
    if not user:
        return '/login'
    ordered_modules = [
        ('dashboard', '/'),
        ('assets', '/assets/'),
        ('maintenance', '/maintenance/'),
        ('incidents', '/incidents/'),
        ('resources', '/resources/'),
        ('documents', '/documents/'),
    ]
    for module, path in ordered_modules:
        if has_module_access(user, module):
            return path
    if has_permission(user, 'can_manage_users'):
        return '/users/'
    if has_permission(user, 'can_manage_system'):
        return '/system/'
    return '/users/change-password'


def _resolve_request(args, kwargs):
    request = kwargs.get('request')
    if request is None:
        for arg in args:
            if hasattr(arg, 'cookies'):
                request = arg
                break
    return request


def _authorized_user_or_redirect(request: Request):
    user = get_current_user(request)
    if not user:
        return None, RedirectResponse(url='/login', status_code=303)
    if request and request.url.path != '/users/change-password' and _must_force_password_change(user):
        return None, RedirectResponse(url='/users/change-password?force=1', status_code=303)
    return user, None


def require_login(view_func: Callable):
    if asyncio.iscoroutinefunction(view_func):
        @wraps(view_func)
        async def wrapper(*args, **kwargs):
            request = _resolve_request(args, kwargs)
            user, redirect = _authorized_user_or_redirect(request)
            if redirect:
                return redirect
            kwargs['current_user'] = user
            return await view_func(*args, **kwargs)
    else:
        @wraps(view_func)
        def wrapper(*args, **kwargs):
            request = _resolve_request(args, kwargs)
            user, redirect = _authorized_user_or_redirect(request)
            if redirect:
                return redirect
            kwargs['current_user'] = user
            return view_func(*args, **kwargs)

    return wrapper


def require_admin(view_func: Callable):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        request = _resolve_request(args, kwargs)
        user, redirect = _authorized_user_or_redirect(request)
        if redirect:
            return redirect
        if user.role != 'admin':
            return RedirectResponse(url=get_default_landing_path(user), status_code=303)
        kwargs['current_user'] = user
        return view_func(*args, **kwargs)

    return wrapper


def require_module_access(module: str):
    def decorator(view_func: Callable):
        if asyncio.iscoroutinefunction(view_func):
            @wraps(view_func)
            async def wrapper(*args, **kwargs):
                request = _resolve_request(args, kwargs)
                user, redirect = _authorized_user_or_redirect(request)
                if redirect:
                    return redirect
                if not has_module_access(user, module):
                    return RedirectResponse(url=get_default_landing_path(user), status_code=303)
                kwargs['current_user'] = user
                return await view_func(*args, **kwargs)
        else:
            @wraps(view_func)
            def wrapper(*args, **kwargs):
                request = _resolve_request(args, kwargs)
                user, redirect = _authorized_user_or_redirect(request)
                if redirect:
                    return redirect
                if not has_module_access(user, module):
                    return RedirectResponse(url=get_default_landing_path(user), status_code=303)
                kwargs['current_user'] = user
                return view_func(*args, **kwargs)

        return wrapper

    return decorator


def require_permission(field_name: str):
    def decorator(view_func: Callable):
        if asyncio.iscoroutinefunction(view_func):
            @wraps(view_func)
            async def wrapper(*args, **kwargs):
                request = _resolve_request(args, kwargs)
                user, redirect = _authorized_user_or_redirect(request)
                if redirect:
                    return redirect
                if not has_permission(user, field_name):
                    return RedirectResponse(url=get_default_landing_path(user), status_code=303)
                kwargs['current_user'] = user
                return await view_func(*args, **kwargs)
        else:
            @wraps(view_func)
            def wrapper(*args, **kwargs):
                request = _resolve_request(args, kwargs)
                user, redirect = _authorized_user_or_redirect(request)
                if redirect:
                    return redirect
                if not has_permission(user, field_name):
                    return RedirectResponse(url=get_default_landing_path(user), status_code=303)
                kwargs['current_user'] = user
                return view_func(*args, **kwargs)

        return wrapper

    return decorator



