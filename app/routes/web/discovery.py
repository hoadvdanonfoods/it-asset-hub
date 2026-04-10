from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session
import ipaddress
from datetime import datetime

from app.auth import require_permission
from app.db.models import Asset, AssetEvent
from app.db.session import get_db
from app.services.scanner import scan_network

router = APIRouter(prefix="/discovery", tags=["discovery"])
templates = Jinja2Templates(directory="app/templates")

@router.get("/", response_class=HTMLResponse)
@require_permission("can_create_assets")
def discovery_page(request: Request, current_user=None):
    return templates.TemplateResponse("assets/discovery.html", {
        "request": request, 
        "current_user": current_user, 
        "results": None,
        "selected_ip_range": ""
    })

@router.post("/scan", response_class=HTMLResponse)
@require_permission("can_create_assets")
def discovery_scan(request: Request, ip_range: str = Form(...), db: Session = Depends(get_db), current_user=None):
    error = None
    results = []
    try:
        network = ipaddress.ip_network(ip_range.strip(), strict=False)
        if network.num_addresses > 512:
            error = "Dải IP quá lớn. Vui lòng chọn dải nhỏ hơn (<= 512 IP)."
        else:
            ip_list = [str(ip) for ip in network.hosts()]
            active_hosts = scan_network(ip_list)
            
            # Đã tìm thấy, match với CSDL
            for host in active_hosts:
                # Fallback to ip if hostname empty
                if not host['hostname']:
                    host['hostname'] = f"Unknown-{host['ip']}"
                
                existing = db.scalar(select(Asset).where(
                    (Asset.ip_address == host['ip']) | 
                    (Asset.asset_name == host['hostname'])
                ))
                host['is_existing'] = existing is not None
                if existing:
                    host['existing_asset'] = existing
            results = active_hosts
    except ValueError:
        error = "Định dạng dải IP không hợp lệ (ví dụ cần đúng: 192.168.1.0/24, 10.0.0.0/24)"
        
    return templates.TemplateResponse("assets/discovery.html", {
        "request": request, 
        "current_user": current_user, 
        "results": results, 
        "selected_ip_range": ip_range,
        "error": error
    })

@router.post("/save")
@require_permission("can_create_assets")
def discovery_save(request: Request, selected_assets: list[str] = Form(default=[]), db: Session = Depends(get_db), current_user=None):
    saved_count = 0
    
    for item in selected_assets:
        parts = item.split("|", 1)
        if len(parts) != 2:
            continue
        ip, hostname = parts[0], parts[1]
        
        # Validate not exists again just to be safe
        existing = db.scalar(select(Asset).where((Asset.ip_address == ip) | (Asset.asset_name == hostname)))
        if not existing:
            now_str = datetime.utcnow().strftime('%Y%m')
            asset = Asset(
                asset_code=f"AUTODISC-{now_str}-{ip.replace('.', '')}",
                asset_name=hostname,
                asset_type="PC/Laptop",
                ip_address=ip,
                status="active"
            )
            db.add(asset)
            db.flush()
            
            db.add(AssetEvent(
                asset_id=asset.id, 
                event_type="asset_created", 
                title="Tạo từ Quét mạng", 
                description=f"Hệ thống phát hiện IP {ip} đang hoạt động", 
                actor=current_user.username
            ))
            saved_count += 1
            
    db.commit()
    redirect_url = "/assets/"
    if saved_count > 0:
        redirect_url += f"?q=AUTODISC"
    return RedirectResponse(url=redirect_url, status_code=303)

