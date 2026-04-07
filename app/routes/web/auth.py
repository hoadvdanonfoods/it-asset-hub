from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session
from itsdangerous import URLSafeSerializer

from app.auth import get_default_landing_path
from app.config import DEFAULT_ADMIN_PASSWORD, DEFAULT_ADMIN_USERNAME, SECRET_KEY, SESSION_COOKIE_NAME, SESSION_COOKIE_SAMESITE, SESSION_COOKIE_SECURE
from app.db.models import User
from app.db.session import get_db
from app.security import hash_password, verify_password

router = APIRouter(tags=['auth'])
templates = Jinja2Templates(directory='app/templates')
serializer = URLSafeSerializer(SECRET_KEY, salt='session')


def _is_default_password_user(user: User, raw_password: str) -> bool:
    return user.username == DEFAULT_ADMIN_USERNAME and raw_password == DEFAULT_ADMIN_PASSWORD


@router.get('/login', response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse('auth/login.html', {'request': request, 'error': None, 'warning': None})


@router.post('/login')
def login_submit(request: Request, username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.username == username.strip()))
    if not user or not user.is_active:
        return templates.TemplateResponse('auth/login.html', {'request': request, 'error': 'Tài khoản không tồn tại hoặc đã bị khóa', 'warning': None})
    if not (verify_password(password, user.password_hash) or verify_password(password, user.password)):
        return templates.TemplateResponse('auth/login.html', {'request': request, 'error': 'Sai tài khoản hoặc mật khẩu', 'warning': None})
    if not user.password_hash:
        user.password_hash = hash_password(password)
        user.password = '[hashed]'
        db.commit()
    token = serializer.dumps({'username': user.username})
    next_url = '/users/change-password?force=1' if _is_default_password_user(user, password) else get_default_landing_path(user)
    resp = RedirectResponse(url=next_url, status_code=303)
    resp.set_cookie(SESSION_COOKIE_NAME, token, httponly=True, samesite=SESSION_COOKIE_SAMESITE, secure=SESSION_COOKIE_SECURE)
    return resp


@router.get('/logout')
def logout():
    resp = RedirectResponse(url='/login', status_code=303)
    resp.delete_cookie(SESSION_COOKIE_NAME)
    return resp
