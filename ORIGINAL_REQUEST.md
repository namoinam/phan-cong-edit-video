# Original User Request

## Initial Request — 2026-06-08T17:22:24+07:00

Xây dựng một **Internal Portal** (trang nội bộ tổng hợp) cho team Nam ởi Nam tại `namoinam.com/portal/`, bao gồm sidebar điều hướng cố định, trang Dashboard tổng quan, 2 trang Kanban mới (Quản lý sản phẩm + Quản lý Video AI), và nhúng các trang công cụ hiện có qua iFrame.

Working directory: `/private/tmp/phan-cong-edit-video-deploy`
Integrity mode: development

---

## Design Reference
- Màu xanh chủ đạo: `#1456F0` (hover `#0442D2`)
- Font: `Be Vietnam Pro` (Google Fonts)
- Nền: `#F7F8FA`, thẻ trắng `#FFFFFF`, bo góc `12px`, bóng đổ nhẹ
- Phong cách: Lark/Notion/Linear — sạch sẽ, tối giản, chuyên nghiệp
- File CSS gốc cần kế thừa các biến từ: `/private/tmp/phan-cong-edit-video-deploy/style.css`

---

## Requirements

### R1. Tạo file `portal/index.html` — Layout chính của Portal
Tạo file mới tại `/private/tmp/phan-cong-edit-video-deploy/portal/index.html`. Layout gồm 2 vùng: **Sidebar cố định bên trái** (240px, nền trắng, border phải nhẹ) và **vùng content bên phải** (chiếm phần còn lại). Sidebar luôn hiển thị, không cuộn theo content. Khi click menu item, nội dung tương ứng load trong vùng content (không reload toàn trang).

### R2. Sidebar điều hướng đầy đủ
Sidebar gồm:
- Logo/Brand: "NAM ƠI NAM" kèm icon nhỏ ở top
- Menu items (icon + nhãn): **Dashboard** 🏠, **Quản lý sản phẩm** 📋, **Quản lý Video AI** 🤖, **Theo dõi sản phẩm edit** 📦 (mở `../theo-doi-san-pham-edit/` trong iFrame), **Phân công edit video** 🎬 (mở `../phan-cong-edit-video/` trong iFrame), **Bảng lương thưởng** 💰 (mở `../bang-tinh-luong-thuong/` trong iFrame), **Cài đặt** ⚙️ (placeholder)
- Active state: nền xanh nhạt `#EBF2FF`, chữ xanh `#1456F0`, border-radius 8px
- Hover effect mượt mà transition 0.15s
- Bottom: avatar circle + tên "Nam"

### R3. Trang Dashboard (trang mặc định khi vào portal)
Hiển thị khi click "Dashboard" hoặc khi vào portal lần đầu. Gồm:
- Header: tiêu đề "Dashboard" + ngày giờ hiện tại (cập nhật realtime)
- 4 thẻ stat (trắng, bo góc 12px, shadow nhẹ, icon màu): "Sản phẩm đang edit" (icon xanh), "Video AI hôm nay" (icon tím), "Video chờ duyệt" (icon cam), "Đã đăng tháng này" (icon xanh lá) — số liệu tĩnh demo
- Phần dưới: 2 cột — Recent activity (danh sách hoạt động giả lập) + Quick links (nút link nhanh đến từng trang con)

### R4. Trang "Quản lý sản phẩm" — Kanban Board
Board Kanban với 6 cột trạng thái: **Đang Check | Đã Nhập Hàng | Bán Chạy | Cần Quay+Edit | Đã Đăng | Cần Quay Lại**. Mỗi thẻ sản phẩm hiển thị: ảnh thumbnail + tên sản phẩm + badge trạng thái + link icon. Nút "+ Thêm sản phẩm" ở header. Dữ liệu demo JSON (5-8 sản phẩm mẫu với thumbnail từ placeholder ảnh). Lưu localStorage. Hỗ trợ drag & drop thẻ giữa các cột.

### R5. Trang "Quản lý Video AI" — Kanban Board
Board Kanban với 4 cột cố định: **Video Mẫu → Đang Tạo → Đã Duyệt → Đã Đăng**. Mỗi thẻ video hiển thị: Thumbnail 16:9 (ảnh placeholder đẹp) + Tên sản phẩm (bold) + Caption (2 dòng, chữ xám nhỏ) + Link video (icon link) + Avatar người phụ trách (circle nhỏ + tên). Nút "+ Thêm video" ở header. Dữ liệu demo JSON (6-8 video mẫu). Lưu localStorage. Hỗ trợ drag & drop thẻ giữa các cột.

### R6. Nhúng các trang công cụ hiện có qua iFrame
Khi click "Theo dõi sản phẩm edit", "Phân công edit video", "Bảng lương thưởng" trong sidebar — hiển thị một `<iframe>` chiếm toàn bộ vùng content (width: 100%, height: 100vh). Không cần sửa gì các file HTML hiện có của 3 trang này.

### R7. Responsive Mobile
Trên mobile (< 768px): Sidebar ẩn mặc định, hiện nút hamburger (☰) ở top-left để toggle sidebar dạng overlay với backdrop mờ. Kanban board cuộn ngang mượt mà (`overflow-x: auto`). Dashboard cards stack thành 2 cột.

---

## Acceptance Criteria

### Giao diện & Brand
- [ ] Font `Be Vietnam Pro` được load và áp dụng toàn portal
- [ ] Màu active sidebar đúng chữ `#1456F0`, background `#EBF2FF`
- [ ] Nền tổng thể `#F7F8FA`, thẻ trắng `#FFFFFF`, bo góc `12px`
- [ ] Hover effects có transition mượt 0.15–0.2s
- [ ] Toàn bộ giao diện trông premium, sạch sẽ như Lark/Linear

### Điều hướng
- [ ] Click từng menu item sidebar → vùng content thay đổi không reload toàn trang
- [ ] Menu item active được highlight đúng (chỉ 1 item active tại 1 thời điểm)
- [ ] iFrame load đúng 3 trang `../theo-doi-san-pham-edit/`, `../phan-cong-edit-video/`, `../bang-tinh-luong-thuong/`
- [ ] Dashboard là trang mặc định khi mở portal

### Kanban
- [ ] Cả 2 Kanban board hiển thị đủ cột và thẻ dữ liệu mẫu
- [ ] Mỗi thẻ Video AI đủ 5 trường: thumbnail, tên, caption, link, người phụ trách
- [ ] Drag & drop thẻ giữa các cột hoạt động (thẻ chuyển cột được)
- [ ] Dữ liệu persist qua localStorage (F5 không mất dữ liệu)

### Responsive
- [ ] Mobile: hamburger button hiển thị, sidebar toggle hoạt động
- [ ] Kanban cuộn ngang được trên màn hình nhỏ
- [ ] Dashboard cards không vỡ layout trên mobile
