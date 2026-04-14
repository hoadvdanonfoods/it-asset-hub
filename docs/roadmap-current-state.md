# IT Asset Hub Roadmap (Hiệu chỉnh theo code hiện tại)

Cập nhật theo trạng thái code hiện tại của dự án, không bám máy móc theo gap analysis cũ.

## 0. Mặt bằng hiện tại

### Đã có rồi
- Asset detail page đã hoạt động
- Asset lifecycle đã có:
  - assign
  - return
  - transfer
  - borrow
  - borrow-return
- Status history và assignment history đã có
- Employee master data CRUD cơ bản đã có
- Bulk archive đã có cho một số module và generic master-data
- Import/export Excel đã có trên nhiều module
- Audit log framework đã có sẵn

### Còn thiếu thật
- Bulk xử lý user đăng nhập
- Bulk deactivate employee có kiểm tra liên kết thiết bị
- Security production còn yếu
- Audit coverage chưa đủ đều
- UX một số form master-data còn thô
- Notification vẫn đang bị tắt
- Một số module business còn thiếu field/flow quan trọng

---

## P1. Ưu tiên cao nhất, vận hành an toàn ngay

### 1. Bulk archive user đăng nhập
**Mục tiêu:** Cho phép archive nhiều tài khoản cùng lúc mà không làm gãy hệ thống.

**Cần làm:**
- checkbox chọn nhiều user trong `/users/`
- action bulk archive
- action bulk restore
- chặn:
  - tự archive chính mình
  - archive admin cuối cùng
  - archive user đang là tài khoản duy nhất có `can_manage_users` nếu cần

**Kết quả mong đợi:**
- dọn user nghỉ việc nhanh
- an toàn hơn delete cứng
- có thể rollback

### 2. Bulk deactivate employee có kiểm tra assignment
**Mục tiêu:** Cho phép vô hiệu hóa nhiều nhân sự mà không làm sai dữ liệu tài sản.

**Cần làm:**
- chọn nhiều employee trong master data
- trước khi deactivate:
  - kiểm tra `asset_assignments` active
  - kiểm tra `assets.current_assignment_id`
  - kiểm tra `assets.assigned_user`
- nếu còn giữ tài sản:
  - block thao tác
  - hiện danh sách asset đang giữ
- nếu sạch:
  - set `is_active = false`

**Kết quả mong đợi:**
- nhân sự nghỉ việc được xử lý hàng loạt
- không phá assignment history
- không làm lệch trạng thái thiết bị

### 3. Báo cáo bulk result rõ ràng
**Cần làm:** Sau mỗi bulk action, trả summary:
- thành công bao nhiêu
- bị chặn bao nhiêu
- lý do bị chặn
- record nào cần xử lý thủ công

**Lý do:** Không nên chỉ redirect im lặng sau thao tác hàng loạt.

---

## P2. Security production, cần làm sớm

### 4. Khóa cấu hình production không an toàn
**Cần làm:**
- nếu `IS_PRODUCTION=true` và `SECRET_KEY` vẫn là fallback thì fail startup
- cảnh báo nếu `DEFAULT_ADMIN_PASSWORD=admin123`
- review `AUTO_CREATE_DEFAULT_ADMIN`

### 5. Session timeout
**Cần làm:**
- chuyển từ `URLSafeSerializer` sang token có expiry
- timeout ví dụ 8 giờ
- redirect về login khi hết hạn

### 6. Rate limit login
**Cần làm:**
- giới hạn số lần login fail theo IP hoặc username
- cooldown ngắn khi fail liên tiếp

### 7. Audit log cho login/logout và action nhạy cảm
**Cần làm:**
- log login success/fail
- log logout
- log xem password resource
- log đổi quyền user
- log bulk user/employee actions

---

## P3. Chuẩn hóa UX và dữ liệu master

### 8. Employee form: đổi `department_id` từ number sang dropdown
**Cần làm:**
- load danh sách departments
- chọn bằng dropdown
- vẫn giữ compatibility dữ liệu cũ

### 9. Hoàn thiện dropdown master-data ở các form liên quan
**Ưu tiên:**
- vendor trong asset form
- requester department trong incident form
- maintenance type / vendor nếu còn chỗ chưa đồng bộ

### 10. Audit log cho Master Data
**Cần làm:**
- create/edit/bulk archive/import trên:
  - departments
  - employees
  - locations
  - asset categories/status/vendors

---

## P4. Hoàn thiện module nghiệp vụ

### 11. Incident workflow còn thiếu
**Cần làm:**
- thêm `assigned_to`
- audit log cho create/update/close
- xem xét CSAT sau khi đóng ticket
- bật lại notification sau khi có rule rõ ràng

### 12. Maintenance module
**Cần làm:**
- audit log create/edit/delete
- lọc theo maintenance type
- xem dashboard chi phí
- sau đó mới tính recurring schedule

### 13. Resources security and compliance
**Cần làm:**
- permission riêng cho xem password
- log action xem password
- review export có lộ password không
- cân nhắc thêm `created_at`

### 14. Documents cleanup
**Cần làm:**
- rà lại double commit
- tìm kiếm tốt hơn
- versioning nếu cần thật

---

## P5. Notification và dashboard

### 15. Bật lại notification
**Cần làm:**
- xác nhận rule nghiệp vụ gửi khi nào
- bật lại Zalo hoặc thêm email
- tránh spam

### 16. Dashboard optimization
**Cần làm:**
- bỏ pattern load all assets nếu đang dùng ở dashboard
- chuyển sang SQL aggregation
- thêm KPI thực dụng:
  - tài sản sắp hết bảo hành
  - sự cố theo trạng thái
  - chi phí bảo trì
  - top tài sản hay lỗi

---

## P6. Polish sau cùng

### 17. Toast, breadcrumb, empty state
### 18. Pagination chuẩn hơn
### 19. Mobile/responsive check
### 20. Chuẩn bị PostgreSQL production path

---

## Thứ tự triển khai khuyến nghị

### Sprint 1
- bulk archive users
- bulk deactivate employees an toàn
- summary/report cho bulk actions

### Sprint 2
- `SECRET_KEY` production guard
- session timeout
- login rate limit
- login/logout audit

### Sprint 3
- employee department dropdown
- vendor/requester dropdown cleanup
- master-data audit log

### Sprint 4
- incident `assigned_to`
- incident audit log
- maintenance audit log + filters

### Sprint 5
- resource password permission + audit
- notification
- dashboard optimization

---

## Khuyến nghị chốt

Nếu ưu tiên theo giá trị thực tế và nhu cầu vận hành hiện tại, nên bắt đầu bằng:

**Sprint 1: bulk archive users + bulk deactivate employees an toàn.**
