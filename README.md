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
