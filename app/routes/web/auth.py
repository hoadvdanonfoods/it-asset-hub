import time
from collections import defaultdict, deque

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import build_session_token, clear_session_cookie, get_default_landing_path, get_session_username
from app.config import DEFAULT_ADMIN_PASSWORD, DEFAULT_ADMIN_USERNAME, LOGIN_RATE_LIMIT_MAX_ATTEMPTS, LOGIN_RATE_LIMIT_WINDOW_SECONDS, SESSION_COOKIE_NAME, SESSION_COOKIE_SAMESITE, SESSION_COOKIE_SECURE, SESSION_MAX_AGE_SECONDS
from app.db.models import User
from app.db.session import get_db
from app.security import hash_password, verify_password
from app.services.audit import log_audit

router = APIRouter(tags=['auth'])
templates = Jinja2Templates(directory='app/templates')
_failed_login_attempts: dict[str, deque[float]] = defaultdict(deque)


def _is_default_password_user(user: User, raw_password: str) -> bool:
    return user.username == DEFAULT_ADMIN_USERNAME and raw_password == DEFAULT_ADMIN_PASSWORD


def _client_ip(request: Request) -> str:
    forwarded_for = request.headers.get('x-forwarded-for', '').split(',')[0].strip()
    if forwarded_for:
        return forwarded_for
    return request.client.host if request.client else 'unknown'


def _rate_limit_key(request: Request, username: str) -> str:
    return f"{_client_ip(request)}::{username.strip().lower()}"


def _prune_attempts(bucket: deque[float], now: float) -> None:
    while bucket and now - bucket[0] > LOGIN_RATE_LIMIT_WINDOW_SECONDS:
        bucket.popleft()


def _is_rate_limited(request: Request, username: str) -> bool:
    now = time.time()
    bucket = _failed_login_attempts[_rate_limit_key(request, username)]
    _prune_attempts(bucket, now)
    return len(bucket) >= LOGIN_RATE_LIMIT_MAX_ATTEMPTS


def _record_failed_login(request: Request, username: str) -> None:
    now = time.time()
    bucket = _failed_login_attempts[_rate_limit_key(request, username)]
    _prune_attempts(bucket, now)
    bucket.append(now)


def _clear_failed_logins(request: Request, username: str) -> None:
    _failed_login_attempts.pop(_rate_limit_key(request, username), None)


@router.get('/login', response_class=HTMLResponse)
def login_page(request: Request):
    message = request.query_params.get('message')
    warning = 'Mật khẩu đã được cập nhật. Vui lòng đăng nhập lại.' if message == 'password_changed' else None
    return templates.TemplateResponse('auth/login.html', {'request': request, 'error': None, 'warning': warning})


@router.post('/login')
def login_submit(request: Request, username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    username = username.strip()
    actor_ip = _client_ip(request)

    user = db.scalar(select(User).where(User.username == username))

    if _is_rate_limited(request, username):
        log_audit(db, actor=username or None, module='auth', action='login', entity_type='user', entity_id=user.id if user else None, result='blocked', reason='rate_limited', metadata={'ip': actor_ip})
        db.commit()
        return templates.TemplateResponse('auth/login.html', {'request': request, 'error': 'Bạn đã nhập sai quá nhiều lần. Vui lòng thử lại sau ít phút.', 'warning': None}, status_code=429)

    if not user or not user.is_active:
        _record_failed_login(request, username)
        log_audit(db, actor=username or None, module='auth', action='login', entity_type='user', entity_id=username or None, result='failed', reason='inactive_or_missing_user', metadata={'ip': actor_ip})
        db.commit()
        return templates.TemplateResponse('auth/login.html', {'request': request, 'error': 'Tài khoản không tồn tại hoặc đã bị khóa', 'warning': None})
    if not (verify_password(password, user.password_hash) or verify_password(password, user.password)):
        _record_failed_login(request, username)
        log_audit(db, actor=user.username, module='auth', action='login', entity_type='user', entity_id=user.id, result='failed', reason='invalid_password', metadata={'ip': actor_ip})
        db.commit()
        return templates.TemplateResponse('auth/login.html', {'request': request, 'error': 'Sai tài khoản hoặc mật khẩu', 'warning': None})
    if not user.password_hash:
        user.password_hash = hash_password(password)
        user.password = '[hashed]'
    _clear_failed_logins(request, username)
    token = build_session_token(user)
    next_url = '/users/change-password?force=1' if _is_default_password_user(user, password) else get_default_landing_path(user)
    log_audit(db, actor=user.username, module='auth', action='login', entity_type='user', entity_id=user.id, metadata={'ip': actor_ip, 'forced_password_change': _is_default_password_user(user, password)})
    db.commit()
    resp = RedirectResponse(url=next_url, status_code=303)
    resp.set_cookie(SESSION_COOKIE_NAME, token, httponly=True, samesite=SESSION_COOKIE_SAMESITE, secure=SESSION_COOKIE_SECURE, max_age=SESSION_MAX_AGE_SECONDS)
    return resp


@router.get('/logout')
def logout(request: Request, db: Session = Depends(get_db)):
    actor = None
    entity_id = None
    session_username = get_session_username(request)
    if session_username:
        user = db.scalar(select(User).where(User.username == session_username))
        if user:
            actor = user.username
            entity_id = user.id
    log_audit(db, actor=actor, module='auth', action='logout', entity_type='user', entity_id=entity_id, metadata={'ip': _client_ip(request)})
    db.commit()
    resp = RedirectResponse(url='/login', status_code=303)
    return clear_session_cookie(resp)
