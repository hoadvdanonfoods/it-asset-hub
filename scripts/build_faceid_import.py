#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from openpyxl import Workbook

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_XLSX = REPO_ROOT / 'it-asset-hub' / 'state' / 'faceid_devices_import.xlsx' if REPO_ROOT.name != 'it-asset-hub' else REPO_ROOT / 'state' / 'faceid_devices_import.xlsx'
DESKTOP_XLSX = Path('/mnt/c/Users/Administrator/Desktop/faceid_devices_import.xlsx')

HEADERS = [
    'Mã thiết bị', 'Tên thiết bị', 'Loại thiết bị', 'Model', 'Serial', 'IP',
    'Bộ phận', 'Người dùng', 'Vị trí', 'Ngày mua', 'Hết bảo hành', 'Trạng thái', 'Ghi chú'
]

security_rows = [
    ('FACE-SEC-MP3-001', 'P2 Face Flap 2', 'FaceID Security', None, '2145221760007', '192.168.200.221', 'An Ninh', None, 'MP3 - Face Flap 2', None, None, 'in_stock', 'OCR từ ảnh FaceID An Ninh, cần kiểm tra lại tên thiết bị'),
    ('FACE-SEC-MP3-002', 'P2 Face Flap', 'FaceID Security', None, '2145221760046', '192.168.200.222', 'An Ninh', None, 'MP3 - Face Flap', None, None, 'in_stock', 'OCR từ ảnh FaceID An Ninh, cần kiểm tra lại tên thiết bị'),
    ('FACE-SEC-MP3-003', 'P2 Controller Flap 1', 'FaceID Security', None, 'AJYE210360014', '192.168.200.223', 'An Ninh', None, 'MP3 - Controller Flap 1', None, None, 'in_stock', 'OCR từ ảnh FaceID An Ninh, cần kiểm tra lại serial/IP'),
    ('FACE-SEC-MP3-004', 'P2 Controller Flap 2', 'FaceID Security', None, 'AJYE192060006', '192.168.200.224', 'An Ninh', None, 'MP3 - Controller Flap 2', None, None, 'in_stock', 'OCR từ ảnh FaceID An Ninh, cần kiểm tra lại serial/IP'),
    ('FACE-SEC-MP3-005', 'P2 Controller Flap 3', 'FaceID Security', None, 'AJYE210360017', '192.168.200.225', 'An Ninh', None, 'MP3 - Controller Flap 3', None, None, 'in_stock', 'OCR từ ảnh FaceID An Ninh, cần kiểm tra lại serial/IP'),
    ('FACE-SEC-MP3-006', 'P2 Face Flap 1', 'FaceID Security', None, '2145221760048', '192.168.200.220', 'An Ninh', None, 'MP3 - Face Flap 1', None, None, 'in_stock', 'OCR từ ảnh FaceID An Ninh'),
    ('FACE-SEC-ADF-001', 'ADF Access Control', 'FaceID Security', None, '8116245000083', None, 'An Ninh', None, 'ADF - Access Control', None, None, 'in_stock', 'OCR từ ảnh FaceID An Ninh, IP chưa đọc chắc chắn'),
    ('FACE-SEC-EPF-001', 'EPF Canteen', 'FaceID Security', None, '7385223940004', '192.168.200.241', 'An Ninh', None, 'EPF - Canteen', None, None, 'in_stock', 'OCR từ ảnh FaceID An Ninh'),
    ('FACE-SEC-EPF-002', 'EPF Access Control', 'FaceID Security', None, '8116235200560', None, 'An Ninh', None, 'EPF - Access Control', None, None, 'in_stock', 'OCR từ ảnh FaceID An Ninh, IP chưa đọc chắc chắn'),
    ('FACE-SEC-DOF-001', 'P1 Salon Out', 'FaceID Security', None, 'AJE1254300191', None, 'An Ninh', None, 'DOF - Salon Out', None, None, 'in_stock', 'OCR từ ảnh FaceID An Ninh, cần kiểm tra lại'),
    ('FACE-SEC-DOF-002', 'P4 Salon In', 'FaceID Security', None, 'AJE1254300192', None, 'An Ninh', None, 'DOF - Salon In', None, None, 'in_stock', 'OCR từ ảnh FaceID An Ninh, cần kiểm tra lại'),
]

attendance_rows = [
    ('FACE-ATT-ADF-001', 'Long Nguyên WH Face ID', 'FaceID Attendance', 'Face ID5', '6700593', '192.168.1.23', 'HR', None, 'ADF - Long Nguyên WH', None, None, 'in_stock', 'OCR từ ảnh FaceID chấm công, cần kiểm tra lại IP'),
    ('FACE-ATT-ADF-002', 'ADF 01 Face ID', 'FaceID Attendance', 'Face ID6', '6700592', '192.168.1.201', 'HR', None, 'ADF - 01', None, None, 'in_stock', 'OCR từ ảnh FaceID chấm công'),
    ('FACE-ATT-BCM-001', 'BCM 02 Face ID', 'FaceID Attendance', 'Face ID6', '6700711', '192.168.25.4', 'HR', None, 'BCM - 02', None, None, 'in_stock', 'OCR từ ảnh FaceID chấm công'),
    ('FACE-ATT-BCM-002', 'BCM 00 Face ID', 'FaceID Attendance', 'Face ID6', '6700684', '192.168.25.2', 'HR', None, 'BCM - 00', None, None, 'in_stock', 'OCR từ ảnh FaceID chấm công'),
    ('FACE-ATT-BCM-003', 'BCM Face ID', 'FaceID Attendance', 'Face ID6', '700685', '192.168.25.5', 'HR', None, 'BCM', None, None, 'in_stock', 'OCR từ ảnh FaceID chấm công'),
    ('FACE-ATT-SALA-001', 'Sala Office Face ID', 'FaceID Attendance', 'Face ID5', '700686', '192.168.35.5', 'HR', None, 'Sala Office', None, None, 'in_stock', 'OCR từ ảnh FaceID chấm công'),
    ('FACE-ATT-DOF-001', 'DOF WH1 Face ID', 'FaceID Attendance', 'Face ID6', '700572', '192.168.17.44', 'HR', None, 'DOF - WH1', None, None, 'in_stock', 'OCR từ ảnh FaceID chấm công'),
    ('FACE-ATT-MP3-001', 'MP3 P2-01 Packing Face ID', 'FaceID Attendance', 'Face ID5', '700590', '192.168.200.234', 'HR', None, 'MP3 - P2-01 Packing', None, None, 'in_stock', 'OCR từ ảnh FaceID chấm công'),
    ('FACE-ATT-MP3-002', 'MP3 P2-02 Candy Face ID', 'FaceID Attendance', 'Face ID5', '700587', '192.168.200.232', 'HR', None, 'MP3 - P2-02 Candy', None, None, 'in_stock', 'OCR từ ảnh FaceID chấm công'),
    ('FACE-ATT-MP3-003', 'MP3 P2-03 Medical Face ID', 'FaceID Attendance', 'Face ID6', '700586', '192.168.200.220', 'HR', None, 'MP3 - P2-03 Medical', None, None, 'in_stock', 'OCR từ ảnh FaceID chấm công'),
    ('FACE-ATT-MP3-004', 'MP3 P2-04 Warehouse Face ID', 'FaceID Attendance', 'Face ID5', '6700588', '192.168.200.236', 'HR', None, 'MP3 - P2-04 Warehouse', None, None, 'in_stock', 'OCR từ ảnh FaceID chấm công'),
    ('FACE-ATT-ADF-003', 'ADF 02 Face ID', 'FaceID Attendance', 'Face ID6', '700833', '192.168.1.202', 'HR', None, 'ADF - 02', None, None, 'in_stock', 'OCR từ ảnh FaceID chấm công'),
    ('FACE-ATT-MP3-005', 'MP3 P1-03 Medical Face ID', 'FaceID Attendance', 'Face ID5', '700574', '192.168.15.235', 'HR', None, 'MP3 - P1-03 Medical', None, None, 'in_stock', 'OCR từ ảnh FaceID chấm công'),
    ('FACE-ATT-MP3-006', 'MP3 P1-04 Kitchen Face ID', 'FaceID Attendance', 'Face ID5', '700581', '192.168.15.236', 'HR', None, 'MP3 - P1-04 Kitchen', None, None, 'in_stock', 'OCR từ ảnh FaceID chấm công'),
    ('FACE-ATT-MP3-007', 'MP3 P1-01 Fry-Dry Face ID', 'FaceID Attendance', 'Face ID5', '700834', '192.168.15.23', 'HR', None, 'MP3 - P1-01 Fry-Dry', None, None, 'in_stock', 'OCR từ ảnh FaceID chấm công, cần kiểm tra lại IP'),
    ('FACE-ATT-DOF-002', 'DOF 01 Packing Face ID', 'FaceID Attendance', 'Face ID5', '6700437', '192.168.17.45', 'HR', None, 'DOF - 01 Packing', None, None, 'in_stock', 'OCR từ ảnh FaceID chấm công'),
    ('FACE-ATT-EPF-001', 'EPF 01 Office Face ID', 'FaceID Attendance', 'Face ID5', '6700436', '192.168.200.245', 'HR', None, 'EPF - Office', None, None, 'in_stock', 'OCR từ ảnh FaceID chấm công'),
    ('FACE-ATT-MP3-008', 'MP3 P1-05 Office Face ID', 'FaceID Attendance', 'Face ID5', '6700432', '192.168.15.231', 'HR', None, 'MP3 - P1-05 Office', None, None, 'in_stock', 'OCR từ ảnh FaceID chấm công'),
    ('FACE-ATT-MP3-009', 'MP3 P1-02 Packing Face ID', 'FaceID Attendance', 'Face ID6', '6700435', '192.168.15.234', 'HR', None, 'MP3 - P1-02 Packing', None, None, 'in_stock', 'OCR từ ảnh FaceID chấm công'),
    ('FACE-ATT-EPF-002', 'EPF 02 Pro Face ID', 'FaceID Attendance', 'Face ID6', '6700566', '192.168.200.246', 'HR', None, 'EPF - Pro', None, None, 'in_stock', 'OCR từ ảnh FaceID chấm công'),
]


def main() -> int:
    wb = Workbook()
    ws = wb.active
    ws.title = 'Assets'
    ws.append(HEADERS)
    for row in security_rows + attendance_rows:
        ws.append(row)

    review = wb.create_sheet('ReviewOCR')
    review.append(['Nhóm', 'Số dòng', 'Ghi chú'])
    review.append(['FaceID Security', len(security_rows), 'Dựng từ OCR ảnh FaceID An Ninh, cần kiểm tra lại một số tên/serial/IP'])
    review.append(['FaceID Attendance', len(attendance_rows), 'Dựng từ OCR ảnh FaceID chấm công, cần kiểm tra lại một số tên/IP'])

    OUTPUT_XLSX.parent.mkdir(parents=True, exist_ok=True)
    wb.save(OUTPUT_XLSX)
    DESKTOP_XLSX.parent.mkdir(parents=True, exist_ok=True)
    wb.save(DESKTOP_XLSX)
    print(OUTPUT_XLSX)
    print(DESKTOP_XLSX)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
