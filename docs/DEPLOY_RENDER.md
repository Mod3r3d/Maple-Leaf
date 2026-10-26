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

## ⏰ Giữ bot online 24/7 vĩnh viễn trên gói Free

Gói **Free** của Render sẽ tự động đưa Web Service vào trạng thái "ngủ" (Sleep / Spin down) nếu sau 15 phút không có yêu cầu HTTP nào gửi đến. Khi ngủ, bot **ngắt kết nối Discord**, nên lệnh Slash sẽ báo *"Ứng dụng không phản hồi"*.

### Cách 1 — Tự giữ thức (đã tích hợp sẵn, không cần làm gì)

Bot tự gửi một request tới `https://<ten-app>.onrender.com/healthz` mỗi **10 phút** (đọc từ biến `RENDER_EXTERNAL_URL` do Render cấp). Miễn service đang chạy, nó sẽ không bị ngủ.

Tùy chỉnh trong **Environment Variables** của Render nếu cần:

```env
KEEPALIVE_ENABLED=True
KEEPALIVE_INTERVAL_MINUTES=10
```

> Lưu ý: cơ chế này **không đánh thức** được service đã ngủ (process bị đóng băng). Nếu service
> đã ngủ, lần gõ lệnh đầu tiên vẫn thất bại — hãy mở link web để đánh thức, sau đó bot tự giữ thức.

### Cách 2 — Dùng dịch vụ bên ngoài (dự phòng, chắc chắn hơn)

Dùng [UptimeRobot](https://uptimerobot.com) ping định kỳ — hoạt động kể cả khi service đã ngủ:

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

> Nên dùng **cả hai**: Cách 1 giữ service thức từ bên trong, Cách 2 đánh thức được từ bên ngoài.

---

## 🩺 Chẩn đoán lỗi "Ứng dụng không phản hồi"

Discord chỉ hiện thông báo này khi bot **không trả lời trong 3 giây**. Trên Render, nguyên nhân
thường gặp nhất là **service đang ngủ** (đã bị spin down) — lúc đó bot đã ngắt kết nối Discord nên
không nhận được lệnh. Mở link web sẽ đánh thức service, nhưng lệnh vừa gõ **không được chạy lại**.

Kiểm tra bằng `/healthz`:

```json
{
  "status": "ok",
  "bot_connected": true,
  "uptime_seconds": 842,
  "started_at": "2026-10-26T01:20:00+00:00",
  "gateway_latency_ms": 242.3,
  "guild_count": 1,
  "last_interaction_at": "2026-10-26T01:31:05+00:00",
  "last_interaction_ago_seconds": 20,
  "recently_restarted": false
}
```

| Dấu hiệu | Ý nghĩa | Cách xử lý |
|---|---|---|
| `uptime_seconds` nhỏ (vài phút) mỗi lần kiểm tra | Service liên tục bị ngủ/khởi động lại | Bật UptimeRobot như mục trên |
| `recently_restarted: true` | Vừa khởi động lại < 2 phút | Đợi bot kết nối lại rồi thử lệnh |
| `bot_connected: false` | Chưa kết nối Discord (đang reconnect) | Đợi 10–30 giây, xem lại Logs |
| `last_interaction_ago_seconds` rất lớn dù bạn vừa gõ lệnh | Lệnh không tới được bot | Service đang ngủ hoặc gateway đứt |
| Uptime dài nhưng vẫn timeout | Event loop bị chặn hoặc CPU bị bóp | Xem Logs Render, kiểm tra tác vụ nặng |

Các nguyên nhân khác cần xem trong **Render → Logs**:
- **Deploy/restart**: mỗi lần deploy, bot mất 20–60 giây để sẵn sàng.
- **Hết RAM (512 MB ở gói Free)**: tác vụ vẽ ảnh (Pillow) có thể làm service bị OOM-kill.
- **Crash do thiếu biến môi trường**: kiểm tra `DISCORD_TOKEN` đã được điền trong Render chưa.

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
