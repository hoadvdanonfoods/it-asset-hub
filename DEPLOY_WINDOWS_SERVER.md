# Hướng dẫn cài đặt IT Asset Hub trên Windows Server 2019

Tài liệu này hướng dẫn bạn cách triển khai dự án chuyên nghiệp trên môi trường Windows Server 2019, đảm bảo ứng dụng tự động khởi chạy và hoạt động ổn định.

## 1. Chuẩn bị môi trường
- **Cài đặt Python**: Tải và cài đặt Python 3.11 hoặc mới hơn từ [python.org](https://www.python.org/).
  - **Lưu ý**: Tích hợp "Add Python to PATH" trong lúc cài đặt.
- **Cài đặt Git**: Để cập nhật code dễ dàng từ GitHub.
- **Cài đặt PostgreSQL** (Nếu sử dụng database lớn): Tải tại [postgresql.org](https://www.postgresql.org/download/windows/).

## 2. Thiết lập dự án
Mở PowerShell (Run as Administrator) và thực hiện:
```powershell
# Di chuyển đến thư mục muốn cài đặt (ví dụ C:\inetpub\wwwroot)
cd C:\inetpub\wwwroot
git clone https://github.com/hoadvdanonfoods/it-asset-hub.git
cd it-asset-hub

# Tạo môi trường ảo
python -m venv .venv
.\.venv\Scripts\activate

# Cài đặt thư viện
pip install -r requirements.txt
pip install uvicorn[standard]
```

## 3. Cấu hình Biến môi trường (.env)
Tạo file `.env` trong thư mục gốc của dự án:
```env
APP_NAME="Danonfoods IT Asset Hub"
APP_PORT=8011
DATABASE_URL="sqlite:///C:/path/to/data/it_asset_hub.db" # Hoặc PostgreSQL URL
PYTHONHOME=""
PYTHONPATH="."
```

## 4. Chạy ứng dụng như một Windows Service (Khuyên dùng)
Để ứng dụng tự khởi động cùng Windows mà không cần mở cửa sổ CMD, bạn nên dùng **NSSM (Non-Sucking Service Manager)**:

1. Tải NSSM tại [nssm.cc](https://nssm.cc/download).
2. Giải nén và mở CMD (Admin) trỏ đến `nssm.exe`.
3. Chạy lệnh: `nssm install ITAssetHub`
4. Trong cửa sổ hiện ra, cấu hình:
   - **Path**: `C:\inetpub\wwwroot\it-asset-hub\.venv\Scripts\python.exe`
   - **Startup directory**: `C:\inetpub\wwwroot\it-asset-hub`
   - **Arguments**: `-m uvicorn app.main:app --host 0.0.0.0 --port 8011`
5. Tab **Environment**:
   ```
   PYTHONHOME=
   PYTHONPATH=.
   ```
6. Nhấn **Install service**. Sau đó vào `services.msc` để Start service `ITAssetHub`.

## 5. Cài đặt Web Server (IIS làm Reverse Proxy)
Để truy cập qua tên miền hoặc Port 80/443, hãy dùng IIS:

1. **Bật IIS**: Server Manager -> Manage -> Add Roles and Features -> Web Server (IIS).
2. **Cài đặt URL Rewrite & Application Request Routing (ARR)**:
   - Tải [URL Rewrite Module](https://www.iis.net/downloads/microsoft/url-rewrite).
   - Tải [ARR Module](https://www.iis.net/downloads/microsoft/application-request-routing).
3. **Cấu hình ARR**:
   - Mở IIS Manager -> Chọn Server Name -> **Application Request Routing Cache**.
   - Chọn **Server Proxy Settings** (bên phải) -> Tích chọn **Enable proxy**.
4. **Tạo Website mới/Cấu hình Default Web Site**:
   - Thêm quy tắc **URL Rewrite**:
     - Match URL: `(.*)`
     - Action Type: **Rewrite**
     - Rewrite URL: `http://localhost:8011/{R:1}`

## 🛡️ Bảo mật & Bảo trì
- **Firewall**: Đừng quên mở Port 80, 443 hoặc 8011 trong **Windows Firewall**.
- **SSL**: Nên sử dụng **Win-ACME** để cài đặt SSL (HTTPS) miễn phí từ Let's Encrypt cho IIS.

---
*Lưu ý: Luôn đảm bảo thư mục `data/` và `uploads/` có quyền **Write** cho User chạy Service.*
