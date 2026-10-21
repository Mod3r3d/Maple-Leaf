# Hướng dẫn Deploy Maple Leaf Bot lên Render (24/7)

Tài liệu này hướng dẫn chi tiết cách triển khai **Maple Leaf Bot** lên nền tảng đám mây [Render.com](https://render.com) để bot hoạt động liên tục **24/7**.

---

## 🌟 Vì sao chọn Render?
- **Miễn phí**: Có gói Free Web Service sẵn sàng sử dụng.
- **Tự động build & deploy**: Mỗi khi bạn push code mới lên GitHub, Render sẽ tự động cập nhật lại bot.
- **Có sẵn Docker**: Dự án đã kèm `Dockerfile` và file cấu hình Blueprint `render.yaml` chuẩn chỉnh.
- **Tích hợp sẵn Health Check Server**: Bot tự động mở cổng HTTP để Render kiểm tra sức khoẻ (`/healthz`), tránh bị lỗi *Port Scan Timeout*.

---

## 🚀 Cách 1: Triển khai 1-Click bằng Blueprint (Khuyến nghị)

Dự án đã có sẵn file [`render.yaml`](../render.yaml). Bạn chỉ cần thực hiện:

1. Đẩy (push) mã nguồn bot lên tài khoản **GitHub** của bạn (chế độ Public hoặc Private).
2. Đăng nhập vào [Render.com](https://render.com) (có thể đăng nhập trực tiếp bằng tài khoản GitHub).
3. Tại trang chủ Render Dashboard, bấm nút **New +** ở góc trên cùng bên phải → chọn **Blueprint**.
4. Chọn repository GitHub chứa bot của bạn (`maple-leaf` hoặc `hoyoBot`).
5. Render sẽ tự động đọc file `render.yaml`:
   - Tên dịch vụ: `maple-leaf`
   - Môi trường: `Docker`
   - Khu vực (Region): `Singapore` (hoặc tuỳ chọn)
   - Nhập giá trị bí mật: Render sẽ hiện ô yêu cầu bạn điền **`DISCORD_TOKEN`**.
6. Bấm **Apply**. Render sẽ bắt đầu build container và khởi động bot!

---

## 🛠️ Cách 2: Triển khai thủ công (Web Service)

Nếu bạn muốn tạo thủ công từng bước thay vì dùng Blueprint:

1. Tại Render Dashboard, bấm **New +** → chọn **Web Service**.
2. Kết nối tới repository GitHub của bạn.
3. Điền thông tin cấu hình:
   - **Name**: `maple-leaf` (hoặc tên tuỳ ý).
   - **Region**: `Singapore` (độ trễ thấp nhất về Việt Nam & Châu Á).
   - **Branch**: `main`.
   - **Runtime**: Chọn **Docker**.
   - **Instance Type**: Chọn **Free**.
4. Mở rộng mục **Advanced** (hoặc tab **Environment**):
   - Thêm các biến môi trường sau:
     | Tên biến (Key) | Giá trị (Value) | Ghi chú |
     |---|---|---|
     | `DISCORD_TOKEN` | *Token của bot lấy từ Discord Developer Portal* | **Bắt buộc** |
     | `PORT` | `10000` | Cổng HTTP để Render health check |
     | `AUTOMATION_ENABLED` | `true` | Bật các tính năng tự động chạy nền |
     | `AUTOMATION_MODE` | `live` | Chế độ chạy thật |
     | `TIMEZONE` | `Asia/Ho_Chi_Minh` | Múi giờ Việt Nam |
     | `GENSHIN_EMOJI` | `<:genshin_icon:1559743970727301200>` | Emoji chuẩn Genshin |
     | `HSR_EMOJI` | `<:hsr_icon:1559743975764791436>` | Emoji chuẩn Honkai: Star Rail |
   - **Health Check Path**: Điền `/healthz`.
5. Bấm **Create Web Service**.

---

## ⏰ Giữ bot online 24/7 vĩnh viễn trên gói Free (UptimeRobot)

Gói **Free** của Render sẽ tự động đưa Web Service vào trạng thái "ngủ" (Sleep / Spin down) nếu sau 15 phút không có yêu cầu HTTP nào gửi đến.

Nhờ bot đã được tích hợp sẵn **Health Check Server** (`/healthz`), bạn có thể dùng dịch vụ giám sát miễn phí [UptimeRobot](https://uptimerobot.com) để ping bot định kỳ, giúp bot **hoạt động liên tục 24/7 mà không bao giờ bị ngủ**:

1. Đăng ký tài khoản miễn phí tại [UptimeRobot.com](https://uptimerobot.com).
2. Bấm **Add New Monitor**:
   - **Monitor Type**: Chọn `HTTP(s)`.
   - **Friendly Name**: `Maple Leaf Bot`.
   - **URL (or IP)**: Điền link Web Service của bạn trên Render kèm `/healthz`:
     ```text
     https://<ten-app-cua-ban>.onrender.com/healthz
     ```
   - **Monitoring Interval**: Chọn `5 minutes` (hoặc `10 minutes`).
3. Bấm **Create Monitor**.
4. Xong! Cứ 5 phút một lần UptimeRobot sẽ gửi tín hiệu HTTP nhẹ tới bot, giữ cho bot luôn luôn thức và hoạt động 24/7 trên Discord.

---

## 💾 Lưu ý về Cơ sở dữ liệu & Cookie tài khoản

- Trên gói **Free** của Render, hệ thống file là *ephemeral* (sẽ được làm mới khi redeploy hoặc restart).
- Để lưu trữ CSDL SQLite bền vững:
  - **Cách A (Khuyên dùng cho người dùng trả phí)**: Vào mục **Disks** trong Render Web Service → tạo 1 Persistent Disk (kích thước 1GB, giá $0.25/tháng) và mount vào đường dẫn `/app/data`.
  - **Cách B (Miễn phí 100% bằng Cloud Postgres)**: Tạo một CSDL PostgreSQL miễn phí trên [Neon.tech](https://neon.tech) hoặc [Supabase.com](https://supabase.com), sau đó thêm biến `DATABASE_URL=postgresql+asyncpg://user:pass@host/dbname` vào Render. Bot sẽ tự động lưu mọi dữ liệu lên Cloud Postgres mà không lo mất dữ liệu.

---

## 🔍 Kiểm tra trạng thái hoạt động

Sau khi deploy thành công, bạn có thể:
1. Mở trình duyệt truy cập thẳng vào link Render: `https://<ten-app-cua-ban>.onrender.com/`. Bạn sẽ thấy trang giao diện đẹp mắt hiển thị trạng thái online, latency và số máy chủ Discord bot đang tham gia.
2. Vào Discord gõ lệnh `/auto status` hoặc `/profile` để bắt đầu trải nghiệm!
