# IT Asset Hub

Hệ thống quản lý tài sản IT nội bộ cho **Danonfoods** — quản lý thiết bị, sự cố, bảo trì, và tài liệu trên một nền tảng duy nhất.

## Tính năng

| Module | Mô tả |
|--------|-------|
| **Dashboard** | Tổng quan tài sản, sự cố, cảnh báo bảo hành |
| **Tài sản** | Quản lý thiết bị, cấp phát, chuyển giao, import Excel |
| **Sự cố** | Ticket IT, ưu tiên, SLA, lịch sử xử lý |
| **Bảo trì** | Lịch bảo trì, lịch sử kỹ thuật |
| **Tài liệu** | Lưu trữ và tra cứu tài liệu nội bộ |
| **Tài nguyên** | Quản lý mật khẩu, tài khoản thiết bị |
| **QR Code** | In mã QR cho từng thiết bị |
| **Checklist Camera** | Kiểm tra trạng thái hệ thống camera |
| **Zalo Notifications** | Thông báo tự động khi có sự cố hoặc cấp phát tài sản |

## Công nghệ

- **Backend:** FastAPI + SQLAlchemy 2.0 (async-ready)
- **Database:** SQLite (dev) / PostgreSQL (production)
- **Templates:** Jinja2 (server-side rendering)
- **CSS:** Tailwind CSS v4 — build local, không dùng CDN
- **Icons:** Lucide — file tĩnh local
- **Fonts:** Inter + Plus Jakarta Sans — woff2 local
- **Notifications:** Zalo OA API (background task)
- **Logging:** Python `logging` với `TimedRotatingFileHandler`
- **Tests:** pytest + SQLite in-memory

## Cài đặt nhanh

```bash
# 1. Tạo virtualenv
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux/Mac

# 2. Cài dependencies
pip install -r requirements.txt

# 3. Tạo file .env (copy từ mẫu)
copy .env.example .env

# 4. Chạy app
uvicorn app.main:app --reload --port 8010
```

Mở: <http://127.0.0.1:8010>  
Đăng nhập mặc định: `admin` / `admin123`

## Biến môi trường

Xem file [.env.example](.env.example) để biết toàn bộ cấu hình.  
Các biến quan trọng khi deploy production:

```env
IS_PRODUCTION=true
SECRET_KEY=<chuỗi ngẫu nhiên dài>
DEFAULT_ADMIN_PASSWORD=<mật khẩu mạnh>
AUTO_CREATE_DEFAULT_ADMIN=false
DATABASE_URL=postgresql+psycopg://user:pass@host:5432/dbname
SESSION_COOKIE_SECURE=true

# Zalo notification (tuỳ chọn)
ZALO_BOT_URL=https://openapi.zalo.me/v2.0/oa/message
ZALO_BOT_TOKEN=<token từ Zalo OA>
ZALO_NOTIFICATION_TARGET=<user_id nhận thông báo>
```

## Chạy tests

```bash
pip install pytest
python -m pytest tests/ -v
```

53 tests bao gồm: chuẩn hoá trạng thái, chuyển trạng thái, cấp phát tài sản, lọc danh sách, import token roundtrip.

## Reset database test

```bash
python scripts/reset_test_db.py              # backup DB cũ + reset
python scripts/reset_test_db.py --no-backup  # reset không backup
python scripts/reset_test_db.py --clear-uploads --clear-camera-checklists
```

## Build Tailwind CSS

Sau khi thêm class mới vào templates, rebuild CSS:

```bash
./tailwindcss.exe -i app/static/css/input.css -o app/static/css/tailwind.min.css --minify
```

> `tailwindcss.exe` không được commit. Tải về tại: https://github.com/tailwindlabs/tailwindcss/releases

## Deploy trên Windows Server

1. Cài PostgreSQL, tạo database và user
2. Tạo file `.env` với cấu hình production
3. Cài app dưới dạng Windows Service bằng NSSM:
   ```bat
   nssm install ITAssetHub "C:\path\to\.venv\Scripts\uvicorn.exe"
   nssm set ITAssetHub AppParameters "app.main:app --host 0.0.0.0 --port 8010"
   nssm start ITAssetHub
   ```
4. Xem thêm script triển khai tại `scripts/`

## Cấu trúc dự án

```
app/
├── db/
│   ├── models/         # SQLAlchemy models
│   ├── migrations.py   # Schema migration tự động
│   └── session.py      # DB session factory
├── routes/web/         # FastAPI route handlers (presentation only)
├── services/
│   ├── asset_service.py   # Business logic tài sản
│   ├── zalo.py            # Gửi thông báo Zalo
│   └── audit.py           # Audit log
├── templates/          # Jinja2 HTML templates
├── static/             # CSS, JS, fonts (tất cả local)
├── auth.py             # Xác thực + phân quyền
├── config.py           # Cấu hình từ .env
└── main.py             # App entry point + middleware

tests/
├── conftest.py         # Fixtures: in-memory SQLite, rollback per test
└── test_asset_service.py
```
