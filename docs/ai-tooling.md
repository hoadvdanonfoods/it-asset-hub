# AI tooling tối giản cho it-asset-hub

Tài liệu này chọn lọc một bộ Everything Claude Code (ECC) nhỏ, thực dụng và phù hợp với `it-asset-hub`.

Mục tiêu không phải là mang toàn bộ ECC vào dự án, mà là lấy đúng những phần giúp dự án này an toàn hơn, ít bug hơn, và phát triển đều tay hơn.

## Mục tiêu của bộ tối giản này

Áp dụng cho các nhóm việc chính của `it-asset-hub`:
- FastAPI route và server-side logic
- SQLAlchemy model và query an toàn
- auth, session, permission, audit log
- UI form/list theo server-rendered template
- regression check sau mỗi sprint
- security hardening trước production

## Bộ ECC tối giản được chọn

### 1) `security-review`
**Dùng khi:**
- sửa `auth.py`, `config.py`
- thêm login/session/permission
- xử lý input từ form
- thêm route thao tác dữ liệu
- làm audit logging hoặc tích hợp ngoài

**Vì sao hữu ích cho dự án này:**
- dự án đang có backlog bảo mật rõ ràng: `SECRET_KEY`, session expiry, login rate limit, auth audit log
- rất hợp để review các route bulk action, incident, user management

**Áp dụng vào `it-asset-hub`:**
- không hardcode secret cho production
- mọi form submit phải validate đầu vào rõ ràng
- các route nhạy phải có permission check
- action thay đổi dữ liệu quan trọng phải có audit log
- tránh lộ thông tin nhạy trong flash/query-param/error

---

### 2) `verification-loop`
**Dùng khi:**
- vừa xong một feature
- chuẩn bị commit
- vừa refactor route/template/model
- vừa sửa bug production-like

**Vì sao hữu ích cho dự án này:**
- app có liên kết chéo giữa users, employees, assets, incidents
- rất dễ sửa một chỗ nhưng vỡ chỗ khác
- hợp với cách làm sprint nhỏ, patch nhanh, verify ngay

**Phiên bản áp dụng cho dự án này:**
1. `python -m compileall` cho file Python vừa sửa
2. test smoke bằng HTTP hoặc browser cho flow chính
3. kiểm tra `git diff --stat`
4. xác nhận không cuốn theo file không liên quan
5. commit nhỏ, đúng 1 mục tiêu

---

### 3) `backend-patterns`
**Dùng khi:**
- thêm route mới
- chỉnh business rule
- đụng query nhiều bảng
- thêm middleware/policy/rate limit

**Vì sao hữu ích cho dự án này:**
- `it-asset-hub` là app quản trị nội bộ, logic chủ yếu nằm ở backend
- nhiều nghiệp vụ cần rõ ràng giữa:
  - validation
  - permission
  - dependency checks
  - audit log
  - redirect/feedback UX

**Áp dụng vào `it-asset-hub`:**
- helper riêng cho parse/validate input bulk
- helper riêng cho feedback redirect
- query dependency rõ ràng trước khi archive/inactive
- tránh nhồi toàn bộ business rule vào template

---

### 4) `coding-standards`
**Dùng khi:**
- refactor file cũ
- thêm helper mới
- review readability
- muốn giữ style đều giữa các route/template

**Vì sao hữu ích cho dự án này:**
- codebase đang tăng dần số lượng helper và branch xử lý
- rất cần giữ code dễ đọc, ít “vá chồng vá”

**Ưu tiên thực tế cho dự án này:**
- tên hàm rõ nghĩa
- wording nhất quán giữa backend và template
- tách helper nếu một route bắt đầu quá dài
- không thêm abstraction khi chưa cần

---

### 5) `e2e-testing`
**Dùng khi:**
- bắt đầu dựng smoke test thật cho login, users, employees
- cần regression test cho các flow dễ vỡ

**Vì sao hữu ích cho dự án này:**
- dự án đang có nhiều flow UI quản trị dạng form/list/bulk action
- các flow này rất hợp để viết smoke test Playwright sau khi Sprint 1 ổn định

**Ưu tiên test đầu tiên:**
- login thành công
- vào `/users/`
- bulk archive bị chặn khi tự archive chính mình
- vào `/master-data/employees`
- inactive employee bị chặn khi còn giữ asset

---

## Những skill ECC không cần ôm vào lúc này

Hiện tại **không cần** mang vào bộ tối giản này:
- deep-research
- market-research
- claude-api
- x-api
- article-writing
- content-engine
- investor-materials
- các skill theo framework không dùng ở đây như Django, Laravel, Spring
- các skill media/video/social

Lý do: không sát nhu cầu hiện tại của `it-asset-hub`.

## Cách dùng thực tế cho dự án này

### Khi làm feature backend
Dùng tư duy kết hợp:
- `backend-patterns`
- `coding-standards`
- cuối cùng chạy `verification-loop`

### Khi làm phần auth/security
Dùng:
- `security-review`
- `backend-patterns`
- cuối cùng chạy `verification-loop`

### Khi sửa bug UI có liên quan route/template
Dùng:
- `coding-standards`
- `verification-loop`
- nếu có thao tác dữ liệu nhạy thì thêm `security-review`

### Khi bắt đầu viết regression test
Dùng:
- `e2e-testing`
- `verification-loop`

## Checklist tối giản cho mọi thay đổi quan trọng

Trước khi commit, nên đi qua checklist này:
- route có permission check chưa
- input đã parse/validate chưa
- có làm vỡ asset assignment/history không
- có cần audit log không
- template wording có khớp nghiệp vụ không
- compile/test smoke đã chạy chưa
- `git diff` có file lạ không

## Vị trí ECC source

ECC được giữ ngoài repo app tại:

`/home/hoadv/.openclaw/workspace/integrations/everything-claude-code`

Không copy toàn bộ ECC vào source `it-asset-hub`.

## Đề xuất lộ trình áp dụng

### Giai đoạn 1, áp dụng ngay
- dùng bộ tối giản này như guideline làm việc
- áp dụng cho Sprint 2 security
- bắt đầu viết smoke checklist chuẩn

### Giai đoạn 2, nếu thấy hữu ích
- thêm Playwright smoke tests thật
- thêm doc ngắn cho release/verification flow
- cân nhắc đồng bộ một phần Codex config nếu cần

## Kết luận

Với `it-asset-hub`, ECC nên được dùng như một **bộ khung làm việc gọn** để:
- siết security
- siết verification
- giữ backend sạch
- giảm regression

Không cần full ECC. Chỉ cần đúng phần có ích.