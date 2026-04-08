from collections import defaultdict
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session
import os
import datetime
import openpyxl
import zipfile
import io
import json
import re
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse

from app.auth import require_module_access, require_permission, get_current_user, has_permission
from app.db.session import get_db
from app.db.models import Asset, AssetEvent

router = APIRouter(prefix="/checklist", tags=["checklist"])
templates = Jinja2Templates(directory="app/templates")


# ---------------------------------------------------------------------------
# Utility: Sort camera list by IP address numerically
# ---------------------------------------------------------------------------
def _ip_sort_key(cam):
    """Return a tuple of integers for sorting by IP address naturally."""
    ip = cam.ip_address or ""
    parts = []
    for seg in ip.split("."):
        try:
            parts.append(int(seg))
        except ValueError:
            parts.append(0)
    # Pad to 4 parts
    while len(parts) < 4:
        parts.append(0)
    return tuple(parts)


# ---------------------------------------------------------------------------
# GET /checklist/ — Main checklist page
# ---------------------------------------------------------------------------
@router.get("/", response_class=HTMLResponse)
@require_module_access("assets")
def checklist_index(request: Request, db: Session = Depends(get_db), current_user=None):
    # Danh sách tất cả NVR (đầu ghi)
    nvrs = db.scalars(select(Asset).where(Asset.asset_type == "NVR").order_by(Asset.asset_name)).all()

    # Lấy toàn bộ Camera
    cameras = db.scalars(select(Asset).where(Asset.asset_type == "Camera").order_by(Asset.asset_name)).all()

    # Phân nhóm Camera theo Location (Lưu tên hoặc IP NVR)
    grouped_cameras = defaultdict(list)
    for c in cameras:
        loc = c.location.strip() if c.location else "chưa_gán"
        grouped_cameras[loc].append(c)

    # Sort each group by IP address
    for loc in grouped_cameras:
        grouped_cameras[loc] = sorted(grouped_cameras[loc], key=_ip_sort_key)

    # Tạo map NVR objects bằng IP_ADDRESS của NVR để view dễ lấy tên
    nvr_map = {n.ip_address: n for n in nvrs if n.ip_address}

    # Current day for date picker default
    today = datetime.datetime.now().day

    return templates.TemplateResponse("assets/checklist.html", {
        "request": request,
        "nvrs": nvrs,
        "nvr_map": nvr_map,
        "grouped_cameras": grouped_cameras,
        "current_user": current_user,
        "today": today,
    })


# ---------------------------------------------------------------------------
# POST /checklist/save — Save checklist evaluations + update Excel
# ---------------------------------------------------------------------------
@router.post("/save")
async def checklist_save(request: Request, db: Session = Depends(get_db)):
    current_user = get_current_user(request)
    if not current_user or not has_permission(current_user, "can_edit_assets"):
        return RedirectResponse(url="/login", status_code=303)

    form_data = await request.form()
    actor = current_user.username if current_user else "System"
    checked_count = 0
    excel_updates = defaultdict(list)

    # Get the selected day from form, default to today
    try:
        selected_day = int(form_data.get("selected_day", datetime.datetime.now().day))
    except (ValueError, TypeError):
        selected_day = datetime.datetime.now().day

    for key, value in form_data.items():
        if key.startswith("cam_"):
            try:
                asset_id = int(key.split("_")[1])
                status_eval = value  # ok, warn, err
                note = form_data.get(f"notes_{asset_id}", "").strip()

                asset = db.get(Asset, asset_id)
                if not asset:
                    continue

                if status_eval == 'ok':
                    title = "Bảo trì: Tốt"
                    desc = note or "Bình thường (Checklist Nhanh)"
                    if asset.status == "broken":
                        asset.status = "active"
                elif status_eval == 'warn':
                    title = "Bảo trì: Cảnh báo"
                    desc = note or "Bị mờ / nhiễu / rung (Checklist Nhanh)"
                elif status_eval == 'err':
                    title = "Bảo trì: Lỗi Mất Hình"
                    desc = note or "Không lên hình / No Signal (Checklist Nhanh)"
                    asset.status = "broken"
                else:
                    continue

                new_event = AssetEvent(
                    asset_id=asset.id,
                    event_type="daily_checklist",
                    title=title,
                    description=desc,
                    actor=actor
                )
                db.add(new_event)

                # Group for excel update
                nvr_ip = asset.location.strip() if asset.location else ""
                if nvr_ip:
                    excel_updates[nvr_ip].append({
                        "cam_code": asset.asset_code,
                        "cam_name": asset.asset_name,
                        "status": status_eval,
                        "note": note
                    })

                checked_count += 1
            except Exception as e:
                print(f"Error handling cam {key}: {e}")
                continue

    db.commit()

    # ------ Update Excel Files with DYNAMIC row/col scanning ------
    checklist_dir = "data/camera_checklists"
    if os.path.exists(checklist_dir):
        for nvr_ip, cams in excel_updates.items():
            # Find matching file (look for IP in filename)
            for root, dirs, files in os.walk(checklist_dir):
                for file in files:
                    if file.endswith(".xlsx") and not file.startswith('~') and nvr_ip in file:
                        filepath = os.path.join(root, file)
                        try:
                            wb = openpyxl.load_workbook(filepath)
                            ws = wb.active

                            # === DYNAMIC ROW SCAN: Find the row for selected_day ===
                            # Scan column A (col 1) from row 10 onwards to find the day number
                            row_idx = None
                            for r in range(10, ws.max_row + 1):
                                cell_val = ws.cell(row=r, column=1).value
                                if cell_val is not None:
                                    try:
                                        if int(cell_val) == selected_day:
                                            row_idx = r
                                            break
                                    except (ValueError, TypeError):
                                        pass
                            if row_idx is None:
                                print(f"Day {selected_day} not found in column A of {filepath}")
                                wb.close()
                                continue

                            # === DYNAMIC COL SCAN: Build map from D-code -> column index ===
                            # Scan row 8 to find D1, D2, D3 etc.
                            d_col_map = {}  # {"D1": 3, "D2": 4, ...}
                            for c in range(1, ws.max_column + 1):
                                hdr = ws.cell(row=8, column=c).value
                                if hdr and str(hdr).strip().startswith("D"):
                                    d_col_map[str(hdr).strip()] = c

                            # === Find "Ghi chú" column from row 7 ===
                            note_col_idx = None
                            for c in range(ws.max_column, 0, -1):
                                val = ws.cell(row=7, column=c).value
                                if val and 'Ghi chú' in str(val):
                                    note_col_idx = c
                                    break

                            day_notes = []
                            for cam in cams:
                                try:
                                    # Extract D-index from cam_code e.g. "CAM-192.168.1.1-D5" -> "D5"
                                    d_code = "D" + cam["cam_code"].split("-D")[-1]
                                    col_idx = d_col_map.get(d_code)
                                    if col_idx is None:
                                        print(f"Column {d_code} not found in row 8 of {filepath}")
                                        continue

                                    mark = 'v' if cam["status"] == 'ok' else 'F'
                                    ws.cell(row=row_idx, column=col_idx).value = mark

                                    # Also update camera name in Row 9 to sync with DB
                                    ws.cell(row=9, column=col_idx).value = cam["cam_name"]

                                    if cam["note"]:
                                        day_notes.append(f'{d_code}: {cam["note"]}')
                                except Exception as ex:
                                    print(f"Error updating excel cell for {cam['cam_code']}: {ex}")

                            if day_notes and note_col_idx:
                                existing_note = ws.cell(row=row_idx, column=note_col_idx).value or ""
                                combined = existing_note + " | " + " | ".join(day_notes) if existing_note else " | ".join(day_notes)
                                ws.cell(row=row_idx, column=note_col_idx).value = combined

                            wb.save(filepath)
                            wb.close()
                        except Exception as e:
                            print(f"Error saving to excel file {filepath}: {e}")
                        break

    return RedirectResponse(url=f"/checklist/?success=1&count={checked_count}", status_code=303)


# ---------------------------------------------------------------------------
# GET /checklist/download — Download Excel files as ZIP
# ---------------------------------------------------------------------------
@router.get("/download")
@require_permission("can_export_assets")
def checklist_download(request: Request, current_user=None):
    checklist_dir = "data/camera_checklists"
    if not os.path.exists(checklist_dir):
        return RedirectResponse(url="/checklist/?error=No+Checklist+Dir", status_code=303)

    nvrs = request.query_params.getlist('nvr')

    s = io.BytesIO()
    with zipfile.ZipFile(s, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(checklist_dir):
            for file in files:
                if file.endswith('.xlsx') and not file.startswith('~'):
                    if not nvrs or any(nvr in file for nvr in nvrs):
                        filepath = os.path.join(root, file)
                        folder_name = os.path.basename(root)
                        arcname = file if folder_name == "camera_checklists" else f"{folder_name}_{file}"
                        zf.write(filepath, arcname=arcname)

    headers = {
        'Content-Disposition': 'attachment; filename="Camera_Checklists.zip"'
    }
    return StreamingResponse(
        iter([s.getvalue()]),
        media_type="application/x-zip-compressed",
        headers=headers
    )


# ===================================================================
# CRUD API Endpoints for Camera / NVR Management
# ===================================================================

@router.get("/api/cameras")
async def api_list_cameras(request: Request, db: Session = Depends(get_db)):
    """List all cameras grouped by NVR, returned as JSON."""
    current_user = get_current_user(request)
    if not current_user:
        return {"error": "Unauthorized"}, 401

    cameras = db.scalars(select(Asset).where(Asset.asset_type == "Camera").order_by(Asset.asset_name)).all()
    nvrs = db.scalars(select(Asset).where(Asset.asset_type == "NVR").order_by(Asset.asset_name)).all()

    return {
        "cameras": [
            {
                "id": c.id, "asset_code": c.asset_code, "asset_name": c.asset_name,
                "ip_address": c.ip_address, "location": c.location, "status": c.status,
                "model": c.model, "serial_number": c.serial_number, "notes": c.notes,
            }
            for c in cameras
        ],
        "nvrs": [
            {
                "id": n.id, "asset_code": n.asset_code, "asset_name": n.asset_name,
                "ip_address": n.ip_address, "location": n.location, "status": n.status,
                "model": n.model, "serial_number": n.serial_number, "notes": n.notes,
            }
            for n in nvrs
        ]
    }


@router.post("/api/camera")
async def api_create_camera(request: Request, db: Session = Depends(get_db)):
    """Create a new Camera or NVR asset."""
    current_user = get_current_user(request)
    if not current_user or not has_permission(current_user, "can_edit_assets"):
        return {"error": "Unauthorized"}, 403

    data = await request.json()
    asset_type = data.get("asset_type", "Camera")  # "Camera" or "NVR"
    asset_code = data.get("asset_code", "").strip()
    asset_name = data.get("asset_name", "").strip()
    ip_address = data.get("ip_address", "").strip()
    location = data.get("location", "").strip()
    model = data.get("model", "").strip()
    serial_number = data.get("serial_number", "").strip()
    notes = data.get("notes", "").strip()

    if not asset_code or not asset_name:
        return {"error": "Mã tài sản và Tên là bắt buộc"}, 400

    # Check duplicate code
    existing = db.scalar(select(Asset).where(Asset.asset_code == asset_code))
    if existing:
        return {"error": f"Mã tài sản '{asset_code}' đã tồn tại"}, 400

    new_asset = Asset(
        asset_code=asset_code,
        asset_name=asset_name,
        asset_type=asset_type,
        ip_address=ip_address or None,
        location=location or None,
        model=model or None,
        serial_number=serial_number or None,
        notes=notes or None,
        status="active",
    )
    db.add(new_asset)
    db.commit()
    db.refresh(new_asset)

    return {
        "success": True,
        "asset": {
            "id": new_asset.id, "asset_code": new_asset.asset_code,
            "asset_name": new_asset.asset_name, "ip_address": new_asset.ip_address,
            "location": new_asset.location, "asset_type": new_asset.asset_type,
        }
    }


@router.put("/api/camera/{asset_id}")
async def api_update_camera(asset_id: int, request: Request, db: Session = Depends(get_db)):
    """Update an existing Camera or NVR asset."""
    current_user = get_current_user(request)
    if not current_user or not has_permission(current_user, "can_edit_assets"):
        return {"error": "Unauthorized"}, 403

    data = await request.json()
    asset = db.get(Asset, asset_id)
    if not asset:
        return {"error": "Không tìm thấy tài sản"}, 404

    if "asset_name" in data and data["asset_name"].strip():
        asset.asset_name = data["asset_name"].strip()
    if "ip_address" in data:
        asset.ip_address = data["ip_address"].strip() or None
    if "location" in data:
        asset.location = data["location"].strip() or None
    if "model" in data:
        asset.model = data["model"].strip() or None
    if "serial_number" in data:
        asset.serial_number = data["serial_number"].strip() or None
    if "notes" in data:
        asset.notes = data["notes"].strip() or None
    if "asset_code" in data and data["asset_code"].strip():
        new_code = data["asset_code"].strip()
        if new_code != asset.asset_code:
            dup = db.scalar(select(Asset).where(Asset.asset_code == new_code))
            if dup:
                return {"error": f"Mã tài sản '{new_code}' đã tồn tại"}, 400
            asset.asset_code = new_code

    db.commit()
    return {
        "success": True,
        "asset": {
            "id": asset.id, "asset_code": asset.asset_code,
            "asset_name": asset.asset_name, "ip_address": asset.ip_address,
            "location": asset.location, "asset_type": asset.asset_type,
        }
    }


@router.delete("/api/camera/{asset_id}")
async def api_delete_camera(asset_id: int, request: Request, db: Session = Depends(get_db)):
    """Delete a Camera or NVR asset."""
    current_user = get_current_user(request)
    if not current_user or not has_permission(current_user, "can_edit_assets"):
        return {"error": "Unauthorized"}, 403

    asset = db.get(Asset, asset_id)
    if not asset:
        return {"error": "Không tìm thấy tài sản"}, 404

    db.delete(asset)
    db.commit()
    return {"success": True, "deleted_id": asset_id}


# ---------------------------------------------------------------------------
# POST /checklist/api/bulk-update-ips — One-time migration: assign IPs by D-index
# ---------------------------------------------------------------------------
@router.post("/api/bulk-update-ips")
def bulk_update_camera_ips(request: Request, db: Session = Depends(get_db)):
    """Bulk update camera ip_address = NVR_subnet.D_index (e.g. D23 on 192.168.40.x -> 192.168.40.23)."""
    current_user = get_current_user(request)
    if not current_user or not has_permission(current_user, "can_edit_assets"):
        return {"error": "Unauthorized"}

    cameras = db.scalars(select(Asset).where(Asset.asset_type == "Camera")).all()
    updated = 0
    skipped = 0

    for cam in cameras:
        nvr_ip = cam.location  # stored NVR IP
        if not nvr_ip:
            skipped += 1
            continue
        parts = nvr_ip.split(".")
        if len(parts) != 4:
            skipped += 1
            continue
        m = re.search(r"-D(\d+)$", cam.asset_code)
        if not m:
            skipped += 1
            continue
        d_idx = m.group(1)
        new_ip = f"{parts[0]}.{parts[1]}.{parts[2]}.{d_idx}"
        if cam.ip_address != new_ip:
            cam.ip_address = new_ip
            updated += 1
        else:
            skipped += 1

    db.commit()
    return {"success": True, "updated": updated, "skipped": skipped}
