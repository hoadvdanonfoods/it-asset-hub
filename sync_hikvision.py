import asyncio
import httpx
import xml.etree.ElementTree as ET
import sys
import re
from urllib.parse import urlparse

# Thêm thư mục hiện tại vào path để import các module của app
sys.path.append('.')
from app.db.session import SessionLocal
from app.db.models.asset import Asset
from sqlalchemy import select, update

# Danh sách đầu ghi do người dùng cung cấp
NVR_LIST = [
    {"name": "Camera MP3 ", "url": "http://cctv-mp3.danonfoods.com:81/", "username": "it", "password": "Its12345689$"},
    {"name": "Camera Mp3 ", "url": "http://cctv-mp3.danonfoods.com:82/", "username": "it", "password": "Its12345689$"},
    {"name": "Camera Mp3", "url": "http://cctv-mp3.danonfoods.com:83/", "username": "it", "password": "Its12345689$"},
    {"name": "Camera Mp3", "url": "http://cctv-mp3.danonfoods.com:84/", "username": "it", "password": "Its12345689$"},
    {"name": "Camera Mp3", "url": "http://cctv-mp3.danonfoods.com:85/", "username": "it", "password": "Its12345689$"},
    {"name": "Camera Mp3", "url": "http://cctv-mp3.danonfoods.com:86/", "username": "it", "password": "Its12345689$"},
    {"name": "Camera Mp3", "url": "http://cctv-mp3.danonfoods.com:87/", "username": "it", "password": "Its12345689$"},
    {"name": "Camera Mp3", "url": "http://cctv-mp3.danonfoods.com:88/", "username": "it", "password": "Its12345689$"},
    {"name": "Camera Mp3", "url": "http://cctv-mp3.danonfoods.com:89/", "username": "it", "password": "72UbeaFnPf"},
    {"name": "Camera ADF", "url": "http://cctv.andifoods.com:81", "username": "admin", "password": "aDmin1999#"},
    {"name": "Camera ADF", "url": "http://cctv.andifoods.com:82", "username": "admin", "password": "aDmin1999#"},
    {"name": "Camera ADF", "url": "http://cctv.andifoods.com:83", "username": "admin", "password": "aDmin1999#"},
    {"name": "Camera DOF", "url": "http://cctv-dof.danonfoods.com:81", "username": "it", "password": "Its12345689$"},
    {"name": "Camera DOF", "url": "http://cctv-dof.danonfoods.com:82", "username": "it", "password": "Its12345689$"},
    {"name": "Camera Sala", "url": "http://cctv-bcm.danonfoods.com:181", "username": "it", "password": "Its12345689$"},
    {"name": "Camera Kho Bàu Bàng A18", "url": "http://103.17.89.123:81", "username": "admin", "password": "aDmin1999#"},
    {"name": "Camera Kho Long Nguyên ADF", "url": "http://203.210.239.189:81", "username": "admin", "password": "aDmin1999#"},
    {"name": "Camera Atco", "url": "http://cctv-atco.andifoods.com:81", "username": "admin", "password": "aDmin1999#"}
]

async def get_channels(client, base_url):
    endpoints = [
        "/ISAPI/System/Video/inputs/channels",
        "/ISAPI/ContentMgmt/InputProxy/channels"
    ]
    for ep in endpoints:
        try:
            resp = await client.get(ep, timeout=15.0)
            if resp.status_code == 200:
                return resp.text
        except Exception:
            continue
    return None

def parse_channels(xml_data):
    channels = []
    try:
        # Use a regex or simple XML parsing to handle different schemas
        # Strip namespaces if present for easier selection
        xml_data = re.sub(' xmlns="[^"]+"', '', xml_data)
        root = ET.fromstring(xml_data)
        
        # Look for VideoInputChannel or InputProxyChannel
        items = root.findall('.//VideoInputChannel') or root.findall('.//InputProxyChannel')
        for item in items:
            c_id = item.findtext('id')
            c_name = item.findtext('name')
            if c_id and c_name:
                channels.append({"id": c_id, "name": c_name.strip()})
    except Exception as e:
        print(f"  Error parsing XML: {e}")
    return channels

async def sync_nvr(nvr_info, db):
    url = nvr_info['url']
    if not url.startswith('http'):
        url = 'http://' + url
    
    parsed = urlparse(url)
    nvr_identifier = f"{parsed.hostname}:{parsed.port}" if parsed.port else parsed.hostname
    
    print(f"\n[*] Processing NVR: {nvr_info['name']} ({nvr_identifier})")
    
    # 1. Ensure NVR exists in DB
    nvr_obj = db.query(Asset).filter(Asset.asset_type == 'NVR', Asset.ip_address == nvr_identifier).first()
    if not nvr_obj:
        nvr_obj = Asset(
            asset_code=f"NVR-{nvr_identifier.replace('.', '_').replace(':', '_')}",
            asset_name=nvr_info['name'].strip(),
            asset_type="NVR",
            ip_address=nvr_identifier,
            status="active"
        )
        db.add(nvr_obj)
        db.flush()
        print(f"  + Created NVR asset in DB")
    else:
        nvr_obj.asset_name = nvr_info['name'].strip()
        nvr_obj.status = "active"
        print(f"  ~ Updated NVR asset in DB")

    # 2. Fetch channels from NVR
    async with httpx.AsyncClient(auth=httpx.DigestAuth(nvr_info['username'], nvr_info['password']), base_url=url, verify=False) as client:
        xml_data = await get_channels(client, url)
        if not xml_data:
            print(f"  [!] Could not connect to NVR or fetch channels from {url}")
            return False
        
        channels = parse_channels(xml_data)
        if not channels:
            print(f"  [!] No channels found in XML response from {url}")
            return False

        print(f"  Found {len(channels)} channels.")

        # 3. Mark all current cameras for this NVR as inactive in DB initially
        db.query(Asset).filter(Asset.asset_type == 'Camera', Asset.location == nvr_identifier).update({"status": "inactive"})
        db.flush()

        # 4. Update/Create Camera assets
        count_updated = 0
        count_created = 0
        for chan in channels:
            cam_code = f"CAM-{nvr_identifier.replace('.', '_').replace(':', '_')}-D{chan['id']}"
            cam_obj = db.query(Asset).filter(Asset.asset_code == cam_code).first()
            
            if cam_obj:
                cam_obj.asset_name = chan['name']
                cam_obj.status = "active"
                cam_obj.location = nvr_identifier
                count_updated += 1
            else:
                new_cam = Asset(
                    asset_code=cam_code,
                    asset_name=chan['name'],
                    asset_type="Camera",
                    location=nvr_identifier,
                    status="active"
                )
                db.add(new_cam)
                count_created += 1
        
        db.flush()
        print(f"  Summary: {count_updated} updated, {count_created} created.")
        return True

async def main():
    db = SessionLocal()
    
    print("[!] Clearing existing NVR and Camera assets for a clean sync...")
    db.query(Asset).filter(Asset.asset_type.in_(['NVR', 'Camera'])).delete(synchronize_session=False)
    db.commit()
    
    success_count = 0
    for nvr in NVR_LIST:
        try:
            if await sync_nvr(nvr, db):
                success_count += 1
                db.commit()
            else:
                db.rollback()
        except Exception as e:
            print(f"  [!!] Fatal error sync NVR {nvr['name']}: {e}")
            db.rollback()
    
    db.close()
    print(f"\n[DONE] Successfully synced {success_count}/{len(NVR_LIST)} NVRs.")

if __name__ == "__main__":
    asyncio.run(main())
