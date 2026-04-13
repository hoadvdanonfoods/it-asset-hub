# Bộ từ điển chuẩn hóa dữ liệu tài sản (bản 1)

Mục tiêu: chuẩn hóa dữ liệu trước khi import vào IT Asset Hub, đặc biệt cho các tài sản IT dùng chung trong nhà máy, line sản xuất, khu vực vận hành, và các tài sản hạ tầng như NVR / FaceID.

## 1. Nguyên tắc mô hình dữ liệu

### Department = đơn vị quản lý / chủ quản
Dùng cho bộ phận chịu trách nhiệm quản lý tài sản.

Ví dụ:
- P.Sản Xuất
- P.QC
- Kho
- HR
- IT
- P.Bảo Trì
- P.ISO
- XNK
- Thu Mua
- R&D
- LAB

### Location = nơi đặt / nơi sử dụng thực tế
Dùng để thể hiện site + khu vực cụ thể.

Cú pháp khuyến nghị:
- `<SITE> - <KHU VỰC>`

Ví dụ:
- MP3 - Kế Toán
- MP3 - Planning Room
- MP3 - Showroom
- MP3 - Thổi Hủ
- MP3 - Ép Nhựa
- MP3 - Sấy 1-2
- MP3 - Sấy 3-4
- MP3 - Vô Hủ 1
- MP3 - Vô Hủ 2
- MP3 - Đóng Gói 1
- MP3 - Đóng Gói 2
- MP3 - Khu Chiên
- MP3 - Lon Giấy
- MP3 - Candy Room
- MP3 - Server Room
- MP3 - WHSSI
- MP3 - Y Tế
- ADF - P.Tổng Hợp
- ADF - QC-01
- ADF - P.SX
- ADF - P.WH
- ADF - P.Bảo Trì
- ADF - Khu Sấy Vỏ Lụa
- ADF - Khu Chẻ
- ADF - Khu WIP
- ADF - Khu Satake
- ADF - Meeting Room
- ADF - Free Room
- DOF - CCTV PC

### Assigned user = người chịu trách nhiệm cụ thể
Chỉ dùng khi tài sản được giao cho một người cụ thể.

Nếu tài sản dùng chung theo line / khu vực / phòng, ưu tiên:
- để trống `Assigned user`, hoặc
- dùng nhãn chuẩn `Dùng chung - <KHU VỰC>` nếu bắt buộc phải điền

Khuyến nghị: **để trống** cho tài sản dùng chung.

---

## 2. Chuẩn hóa Site / cơ sở

Giá trị gốc đang thấy:
- MP3
- ADF
- DOF
- CCTV PC
- rỗng
- None

### Chuẩn đề xuất
- `MP3`
- `ADF`
- `DOF`
- `DOF - CCTV PC` hoặc map `CCTV PC` thành location con thuộc site phù hợp
- rỗng / `None` -> để trống, chờ bổ sung hoặc suy luận từ mã thiết bị / phòng ban

---

## 3. Chuẩn hóa Asset Type

Giá trị gốc hiện có:
- PC
- NVR
- Printer

### Chuẩn dùng để import
- `PC`
- `Printer`
- `NVR`
- `FaceID Attendance`
- `FaceID Security`

### Quy tắc
- Máy chấm công khuôn mặt -> `FaceID Attendance`
- Máy Face an ninh / kiểm soát cửa -> `FaceID Security`
- Đầu ghi camera -> `NVR`
- Không gộp FaceID vào `PC` hay `NVR`

---

## 4. Từ điển Department chuẩn

## 4.1 Bộ phận văn phòng / hỗ trợ
| Giá trị gốc | Department chuẩn |
|---|---|
| Kế Toán | Kế Toán |
| kế toán | Kế Toán |
| HR | HR |
| Lễ Tân | Hành Chính |
| IT | IT |
| Thu Mua | Thu Mua |
| XNK | XNK |
| P.ISO | P.ISO |
| PR | PR |
| PR Assistant | PR |
| Y Tế | Y Tế |
| Y Te | Y Tế |
| QA office | QA |
| LAB | LAB |
| P.LAB | LAB |
| Design | Design |

## 4.2 Bộ phận sản xuất / vận hành
| Giá trị gốc | Department chuẩn |
|---|---|
| P.Sản Xuất | P.Sản Xuất |
| P.SX | P.Sản Xuất |
| P2 P.SX | P.Sản Xuất |
| Thổi Hủ | P.Sản Xuất |
| P.Thổi hủ | P.Sản Xuất |
| Ép nhựa | P.Sản Xuất |
| Vô Hủ | P.Sản Xuất |
| Vô Hủ 1 | P.Sản Xuất |
| Vô Hủ 2 | P.Sản Xuất |
| Chiên | P.Sản Xuất |
| Khu Chiên | P.Sản Xuất |
| Sấy 1-2 | P.Sản Xuất |
| Sấy 3-4 | P.Sản Xuất |
| Khu Sấy Vỏ lụa | P.Sản Xuất |
| P.Đóng Gói | P.Sản Xuất |
| P.Đóng Gói 02 | P.Sản Xuất |
| P.Đóng gói 1 | P.Sản Xuất |
| Đóng goi 1 | P.Sản Xuất |
| P2 Đóng Gói/ Chiên | P.Sản Xuất |
| P2-P.Đóng gói hạt dẻ | P.Sản Xuất |
| P2 .Đóng Gói/ Candy | P.Sản Xuất |
| P2 Candy Room | P.Sản Xuất |
| P2 Sấy | P.Sản Xuất |
| Khu Chẻ | P.Sản Xuất |
| Khu WIP | P.Sản Xuất |
| Khu Satake | P.Sản Xuất |
| P1-Lon Giấy | P.Sản Xuất |
| P.Lon Giấy | P.Sản Xuất |

## 4.3 Kho / logistics / bảo trì / QC
| Giá trị gốc | Department chuẩn |
|---|---|
| Kho FG | Kho FG |
| WH | Kho |
| P.WH | Kho |
| P2 WHSSI | Kho |
| WH-SSI | Kho |
| P2 Office Wh01 | Kho |
| P2 Office Wh02 | Kho |
| P.Bảo Trì | P.Bảo Trì |
| P.Bao Trì | P.Bảo Trì |
| P.QC | P.QC |
| P.QC-01 | P.QC |
| BV | An Ninh |
| BV-01 | An Ninh |
| BV-04 | An Ninh |
| BV-05 | An Ninh |
| BV-06 cookies | An Ninh |
| BV3 | An Ninh |
| BV4 | An Ninh |
| Cookies | Sản Xuất |

## 4.4 Khu/phòng đang nên chuyển sang Location, không nên giữ làm Department
Các giá trị sau nên coi là **Location label**, còn Department sẽ map về bộ phận chủ quản gần nhất:
- Planning Room -> Department: Planning / hoặc P.Kế Hoạch nếu có, Location: `<SITE> - Planning Room`
- Meeting Room -> Department: Hành Chính hoặc IT, Location: `<SITE> - Meeting Room`
- Show Room / Showroom -> Department: Sales hoặc PR, Location: `<SITE> - Showroom`
- New York Room -> Department: Hành Chính / Sales, Location: `<SITE> - New York Room`
- Canada Room -> Department: Hành Chính / Sales, Location: `<SITE> - Canada Room`
- Free Room -> Department: Hành Chính, Location: `<SITE> - Free Room`
- Office -> Department: Hành Chính, Location: `<SITE> - Office`
- Salon -> cần xác nhận nghiệp vụ, tạm để Department: Hành Chính hoặc Sản Xuất theo thực tế
- Trạm Bình Phước -> nên coi là Site/Location, không phải Department

---

## 5. Từ điển Location chuẩn

## 5.1 Quy tắc tạo Location
Từ dữ liệu gốc:
- lấy `Vị trí` làm site gốc: `MP3`, `ADF`, `DOF`
- nếu `Department` hiện tại thực chất là khu vực cụ thể, chuyển nó vào Location
- format: `<SITE> - <KHU VỰC>`

## 5.2 Ví dụ map Location
| Vị trí gốc | Department gốc | Location chuẩn |
|---|---|---|
| MP3 | Kế Toán | MP3 - Kế Toán |
| MP3 | Planning Room | MP3 - Planning Room |
| MP3 | Show Room | MP3 - Showroom |
| MP3 | Showroom | MP3 - Showroom |
| MP3 | New York Room | MP3 - New York Room |
| MP3 | P2 Candy Room | MP3 - Candy Room |
| MP3 | P2 Sấy | MP3 - Sấy |
| MP3 | P2-P.Đóng gói hạt dẻ | MP3 - Đóng Gói Hạt Dẻ |
| MP3 | Thổi Hủ | MP3 - Thổi Hủ |
| MP3 | Ép nhựa | MP3 - Ép Nhựa |
| MP3 | Vô Hủ 1 | MP3 - Vô Hủ 1 |
| MP3 | Vô Hủ 2 | MP3 - Vô Hủ 2 |
| MP3 | Chiên | MP3 - Chiên |
| MP3 | P.Đóng Gói 02 | MP3 - Đóng Gói 02 |
| ADF | P.Tổng Hợp | ADF - P.Tổng Hợp |
| ADF | P.QC-01 | ADF - QC-01 |
| ADF | P.Bảo Trì | ADF - P.Bảo Trì |
| ADF | Khu Sấy Vỏ lụa | ADF - Khu Sấy Vỏ Lụa |
| ADF | Khu Chẻ | ADF - Khu Chẻ |
| ADF | Khu WIP | ADF - Khu WIP |
| ADF | Khu Satake | ADF - Khu Satake |
| DOF | CCTV PC | DOF - CCTV PC |

## 5.3 Giá trị Location cần xử lý đặc biệt
| Giá trị gốc | Xử lý |
|---|---|
| None | để trống |
| rỗng | để trống |
| CCTV PC | nên nâng thành location con, ví dụ `DOF - CCTV PC` hoặc site thực tế tương ứng |

---

## 6. Quy tắc xử lý Assigned User

## 6.1 Khi giữ nguyên Assigned User
Giữ khi đây là tài sản giao cho người cụ thể:
- Dương
- Diệu
- Ngân KT
- Tuyền
- Phương
- Minh Diễm
- Thư HR
- ...

## 6.2 Khi nên để trống
Đặt trống nếu là nhãn dùng chung / tổ / vai trò chung:
- Tổ Trưởng
- Tổ trưởng
- QC
- HR
- All user
- all user
- Free
- None
- WH-PL
- C2
- BV
- Bảo trì
- Y Tế / Y Te (nếu là máy dùng chung khu vực)

## 6.3 Khi nên chuyển thành Notes thay vì Assigned User
Ví dụ:
- `( HP Laptop )`
- `HP PC`
- `Free`
- `All user`

Có thể chuyển thành:
- `Assigned user` = trống
- `Notes` += `Thiết bị dùng chung / nhãn cũ: HP PC`

---

## 7. Quy tắc chuẩn hóa trạng thái

Hiện file đang dùng gần như toàn bộ `active`.

### Quy tắc import đề xuất
- nếu `Assigned user` sau chuẩn hóa **có giá trị thực sự là người cụ thể** -> `assigned`
- nếu `Assigned user` để trống -> `in_stock` hoặc cân nhắc `assigned` nếu đây là tài sản lắp cố định theo khu vực

### Khuyến nghị thực tế cho tài sản lắp cố định tại line/khu vực
Để phản ánh đúng đang sử dụng thực tế, có thể dùng:
- `status = assigned`
- `assigned_user = trống`
- `location = <SITE> - <KHU VỰC>`
- `notes = dùng chung / tài sản khu vực`

Tuy nhiên do logic app hiện tại đang gắn `assigned` khá chặt với assignment, phương án an toàn trước mắt là:
- **tài sản dùng chung**: `status = in_stock`, `assigned_user = trống`, nhưng ghi rõ `location` + `notes`

Sau này nếu muốn mô hình đúng hơn, có thể bổ sung khái niệm `assigned_to_department` hoặc `custodian_unit`.

---

## 8. Quy tắc riêng cho FaceID và tài sản an ninh

### Face chấm công
- Asset Type: `FaceID Attendance`
- Department: `HR` hoặc `Hành Chính` hoặc đơn vị vận hành thực tế
- Assigned user: trống
- Location: `<SITE> - <CỔNG/KHU VỰC>`

### Face an ninh
- Asset Type: `FaceID Security`
- Department: `An Ninh` hoặc `IT`
- Assigned user: trống
- Location: `<SITE> - <CỔNG/KHU VỰC>`

### NVR
- Asset Type: `NVR`
- Department: `IT` hoặc `An Ninh`
- Assigned user: trống
- Location: phòng server / tủ camera / site lắp đặt

---

## 9. Chiến lược import khuyến nghị

## Đợt 1
Import tài sản hiện có từ file Excel sau khi chuẩn hóa:
- asset type
- department
- location
- assigned user
- status

## Đợt 2
Bổ sung FaceID từ ảnh / danh sách riêng:
- tạo file asset riêng cho FaceID Attendance
- tạo file asset riêng cho FaceID Security

## Đợt 3 (nếu cần)
Nâng cấp mô hình dữ liệu để hỗ trợ:
- `custodian_department`
- `site`
- `location_detail`
- tài sản dùng chung theo khu vực

---

## 10. Kết luận vận hành

### Chuẩn tối thiểu nên áp dụng ngay
- Department = đơn vị quản lý
- Location = site + khu vực thực tế
- Assigned user chỉ dùng cho người cụ thể
- tài sản dùng chung line/xưởng thì không gán người
- FaceID / NVR quản lý như tài sản hạ tầng IT, không như PC cá nhân

### Hướng đi đúng cho file hiện tại
1. chuẩn hóa file asset theo từ điển này
2. tách / dựng thêm danh sách FaceID từ ảnh
3. import vào DB sạch vừa reset
