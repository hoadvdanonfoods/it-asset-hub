from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from app.config import (
    APP_NAME,
    APP_VERSION,
    AUTO_BACKFILL_ASSET_EVENTS,
    AUTO_CREATE_DEFAULT_ADMIN,
    DATA_DIR,
    DEFAULT_ADMIN_PASSWORD,
    DEFAULT_ADMIN_USERNAME,
    IS_PRODUCTION,
)
from app.db.base import Base
from app.db.migrations import ensure_schema
from app.db.models import Asset, AssetEvent, User
from app.db.session import SessionLocal, engine
from app.routes.web.assets import router as assets_router
from app.routes.web.auth import router as auth_router
from app.routes.web.dashboard import router as dashboard_router
from app.routes.web.incidents import router as incidents_router
from app.routes.web.maintenance import router as maintenance_router
from app.routes.web.qr import router as qr_router
from app.routes.web.users import router as users_router
from app.routes.web.system_tools import router as system_tools_router
from app.routes.web.resources import router as resources_router
from app.routes.web.documents import router as documents_router
from app.routes.web.discovery import router as discovery_router
from app.routes.web.checklist import router as checklist_router
from app.security import hash_password
import app.db.models  # noqa: F401

DATA_DIR.mkdir(parents=True, exist_ok=True)
Base.metadata.create_all(bind=engine)
ensure_schema()


def ensure_default_admin():
    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.username == DEFAULT_ADMIN_USERNAME))
        if not user and AUTO_CREATE_DEFAULT_ADMIN and not IS_PRODUCTION:
            user = User(
                username=DEFAULT_ADMIN_USERNAME,
                password='[hashed]',
                password_hash=hash_password(DEFAULT_ADMIN_PASSWORD),
                role='admin',
                full_name='Administrator',
            )
            db.add(user)
            
        if user and user.role == 'admin':
            user.can_view_dashboard = True
            user.can_view_assets = True
            user.can_view_maintenance = True
            user.can_view_incidents = True
            user.can_view_resources = True
            user.can_create_assets = True
            user.can_edit_assets = True
            user.can_import_assets = True
            user.can_export_assets = True
            user.can_create_maintenance = True
            user.can_edit_maintenance = True
            user.can_export_maintenance = True
            user.can_create_incidents = True
            user.can_edit_incidents = True
            user.can_export_incidents = True
            user.can_manage_users = True
            user.can_manage_system = True
            user.can_manage_resources = True
            user.can_view_documents = True
            user.can_manage_documents = True
            
        if user and not user.password_hash:
            user.password_hash = hash_password(user.password or DEFAULT_ADMIN_PASSWORD)
            user.password = '[hashed]'
            
        db.commit()
    finally:
        db.close()


def backfill_asset_events():
    db = SessionLocal()
    try:
        for asset in db.scalars(select(Asset)).all():
            has_events = db.scalar(select(AssetEvent.id).where(AssetEvent.asset_id == asset.id).limit(1))
            if not has_events:
                db.add(AssetEvent(asset_id=asset.id, event_type='asset_created', title='Khởi tạo asset', description='Asset có sẵn trong hệ thống', actor='system'))
        db.commit()
    finally:
        db.close()


ensure_default_admin()
if AUTO_BACKFILL_ASSET_EVENTS:
    backfill_asset_events()
app = FastAPI(title=APP_NAME)
app.state.app_version = APP_VERSION

static_dir = Path('app/static')
app.mount('/static', StaticFiles(directory=static_dir), name='static')

app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(assets_router)
app.include_router(maintenance_router)
app.include_router(incidents_router)
app.include_router(qr_router)
app.include_router(users_router)
app.include_router(system_tools_router)
app.include_router(resources_router)
app.include_router(documents_router)
app.include_router(discovery_router)
app.include_router(checklist_router)

# Centralized Template Context Injection
import sys
for router_obj in [
    auth_router, dashboard_router, assets_router, maintenance_router,
    incidents_router, qr_router, users_router, system_tools_router,
    resources_router, documents_router, discovery_router, checklist_router
]:
    module = sys.modules.get(router_obj.__module__)
    if module and hasattr(module, 'templates'):
        module.templates.env.globals['APP_NAME'] = APP_NAME
        module.templates.env.globals['APP_VERSION'] = APP_VERSION
        from app.auth import has_permission
        module.templates.env.globals['has_permission'] = has_permission


@app.get('/health')
def health():
    return {'status': 'ok', 'app': APP_NAME, 'version': APP_VERSION}
