import io

import qrcode
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.auth import require_permission, require_module_access
from app.db.models import Asset
from app.db.session import get_db

router = APIRouter(prefix='/qr', tags=['qr'])
templates = Jinja2Templates(directory='app/templates')


def build_asset_qr_text(asset: Asset) -> str:
    lines = [
        f'Mã thiết bị: {asset.asset_code}',
        f'Tên thiết bị: {asset.asset_name}',
    ]
    if asset.asset_type:
        lines.append(f'Loại: {asset.asset_type}')
    if asset.department:
        lines.append(f'Bộ phận: {asset.department}')
    return '\n'.join(lines)


def build_qr_png(data: str) -> bytes:
    img = qrcode.make(data)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()


@router.get('/asset/{asset_id}.png')
@require_permission('can_edit_assets')
def asset_qr_png(asset_id: int, request: Request, db: Session = Depends(get_db), current_user=None):
    from app.auth import has_permission
    if not has_permission(current_user, 'can_edit_assets'):
        return RedirectResponse(url='/assets/', status_code=303)
    asset = db.get(Asset, asset_id)
    if not asset:
        return StreamingResponse(io.BytesIO(), media_type='image/png')
    png = build_qr_png(build_asset_qr_text(asset))
    return StreamingResponse(io.BytesIO(png), media_type='image/png')


@router.get('/asset/{asset_id}', response_class=HTMLResponse)
@require_permission('can_edit_assets')
def asset_qr_page(asset_id: int, request: Request, db: Session = Depends(get_db), current_user=None):
    from app.auth import has_permission
    if not has_permission(current_user, 'can_edit_assets'):
        return RedirectResponse(url='/assets/', status_code=303)
    asset = db.get(Asset, asset_id)
    qr_url = f'/qr/asset/{asset_id}.png'
    qr_text = build_asset_qr_text(asset) if asset else ''
    return templates.TemplateResponse(
        'qr/asset.html',
        {'request': request, 'asset': asset, 'qr_url': qr_url, 'qr_text': qr_text, 'current_user': current_user},
    )
