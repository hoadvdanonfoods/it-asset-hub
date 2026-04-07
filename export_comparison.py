import csv
import os

desktop_path = r"C:\Users\Administrator\Desktop"
file_path = os.path.join(desktop_path, "So_Sanh_IT_Asset_Hub_vs_ASM.csv")

data = [
    ["Tiêu chí", "asm-internal.danonfoods.com (Cũ)", "IT Asset Hub (Mới)"],
    ["Công nghệ Backend", "PHP/NodeJS (Đồng bộ)", "Python + FastAPI (Bất đồng bộ, Model Pydantic)"],
    ["Công nghệ Frontend", "HTML + jQuery + Bootstrap 4", "HTML Jinja2 + Tailwind CSS (Native DOM, Không jQuery)"],
    ["Giao diện & Thẩm mỹ", "Theme AdminLTE (Cứng nhắc, hộp chữ nhật)", "Stitch Design/Tailwind (Glassmorphism, Darkmode, Đổ bóng mượt mà)"],
    ["Biểu đồ (Charts)", "Bảng tĩnh, hoặc biểu đồ tĩnh", "Chart.js (Tương tác động, Tự đổi màu theo Dark/Light Mode)"],
    ["Tốc độ Tải (Page Load)", "Trung bình (Load nặng do jQuery & CSS Reset lớn)", "Cực nhanh (Tailwind biên dịch siêu nhẹ, Async API)"],
    ["Khả năng mở rộng API", "Phải viết lại cổng giao tiếp (Legacy REST)", "Có sẵn /docs (Swagger UI), sẵn sàng cắm vào Mobile App"],
    ["Bảo mật (Security)", "Rủi ro từ các thư viện JS cũ", "Bảo mật cao nhờ FastAPI Security, Validation chặt chẽ"],
]

try:
    with open(file_path, mode='w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(data)
    print(f"Success: {file_path}")
except Exception as e:
    print(f"Error: {e}")
