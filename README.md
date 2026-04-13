# IT Asset Hub

Web tool nội bộ để quản lý thiết bị IT, bảo trì và ticket sự cố.

## MVP
- Dashboard tổng quan
- Danh sách thiết bị
- Chi tiết thiết bị
- Lịch sử bảo trì
- Ticket sự cố
- Import dữ liệu từ Excel

## Công nghệ
- FastAPI
- SQLAlchemy
- SQLite hoặc PostgreSQL
- Jinja2 + Bootstrap

## Khuyến nghị production
- Windows Server 2019: nên dùng PostgreSQL thay cho SQLite
- Chạy app bằng Windows Service (NSSM)
- Đổi `SECRET_KEY`, mật khẩu DB, và mật khẩu admin mặc định sau khi cài
- Xem bộ script triển khai tại `deploy/windows-server-2019/`

## Chạy nhanh
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=. uvicorn app.main:app --reload
```

Mở: <http://127.0.0.1:8000>

## Reset DB test local
Dùng khi muốn dọn dữ liệu test và khởi tạo lại database sạch trước khi test/import lại.

```bash
source .venv/bin/activate
python scripts/reset_test_db.py
```

Tùy chọn:

```bash
# không backup DB cũ
python scripts/reset_test_db.py --no-backup

# dọn luôn uploads và camera checklist test
python scripts/reset_test_db.py --clear-uploads --clear-camera-checklists
```

Script sẽ:
- backup file DB hiện tại vào `data/backups/` (mặc định)
- xóa DB SQLite test hiện tại
- khởi tạo lại schema sạch theo code hiện tại
