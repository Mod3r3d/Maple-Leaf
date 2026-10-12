# ✦ Maple Leaf — Discord Bot cho Genshin Impact & Honkai: Star Rail

[![Python](https://img.shields.io/badge/python-3.12%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![discord.py](https://img.shields.io/badge/discord.py-2.3%2B-5865F2?logo=discord&logoColor=white)](https://github.com/Rapptz/discord.py)
[![Tests](https://img.shields.io/badge/tests-unittest-brightgreen)](tests/)
[![Docker](https://img.shields.io/badge/docker-ready-2496ED?logo=docker&logoColor=white)](Dockerfile)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**Maple Leaf** là bot Discord viết bằng Python, chuyên cho **Genshin Impact** và **Honkai: Star Rail**.
Bot có kiến trúc phân tầng, giao diện **100% tiếng Việt**, thẻ ảnh (card) đồ hoạ bằng Pillow, và
**lớp tự động hoá chạy nền** (điểm danh, giftcode, Mimo, sự kiện web) với cookie được **mã hoá**.

> 🌐 English version: [`README.en.md`](README.en.md)

---

## ✨ Tính năng

### 🎮 Hồ sơ & nhân vật
- **`/profile`** — thẻ hồ sơ người chơi (AR, Cấp Thế Giới, Thành Tựu / Cấp Khai Phá, Cân Bằng).
- **`/characters`** — xem toàn bộ tủ trưng bày nhân vật, có phân trang.
- **`/build`** — hướng dẫn build nhân vật (vũ khí, thánh di vật, chỉ số, đội hình) kèm **autocomplete**.
- **`/search`** — tra cứu nhanh thông tin nhân vật / nguyên tố / vận mệnh.

### ⚙️ Tự động hoá chạy nền (`/auto`)
- **Điểm danh HoYoLAB** hàng ngày cho mọi tài khoản đã bật.
- **Tự động đổi Giftcode** — tự quét mã mới từ nhiều nguồn và đổi cho tài khoản của bạn.
- **Nhiệm vụ Mimo** và **Điểm danh Đồng hành**.
- **Thông báo sự kiện web** của cả hai game.
- `/auto status`, `/auto toggle`, `/auto session_add`, `/auto verify`, `/auto run`, `/auto history`.

### 🔐 Bảo mật
- Cookie HoYoLAB được **mã hoá đối xứng Fernet** trước khi lưu CSDL.
- Không bao giờ ghi cookie thô vào log hay hiển thị ra Discord.
- Người dùng toàn quyền bật/tắt và **thu hồi phiên** bất kỳ lúc nào.
- Xem [`SECURITY.md`](SECURITY.md) trước khi triển khai công khai.

---

## 🚀 Cài đặt nhanh

### Yêu cầu
- **Python 3.12+**
- Một bot Discord (tạo tại [Discord Developer Portal](https://discord.com/developers/applications))
- **Bật cả 2 Privileged Intent** cho bot: `SERVER MEMBERS` và `MESSAGE CONTENT`.

### Cách 1 — Script tự động (khuyến nghị)

```bash
# Windows
scripts\setup.bat

# Linux / macOS
bash scripts/setup.sh
```

Script sẽ tự tạo môi trường ảo, cài thư viện và tạo file `.env` cho bạn.

### Cách 2 — Làm thủ công

```bash
git clone https://github.com/Mod3r3d/Maple-Leaf.git
cd Maple-Leaf

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt
cp .env.example .env             # Windows: copy .env.example .env
```

### Cấu hình

Mở `.env` và điền **tối thiểu** `DISCORD_TOKEN`:

```env
DISCORD_TOKEN=token_bot_cua_ban
```

Các biến khác đều có giá trị mặc định hợp lý. Danh sách đầy đủ:

| Biến | Mặc định | Mô tả |
|---|---|---|
| `DISCORD_TOKEN` | *(bắt buộc)* | Token bot Discord |
| `DATABASE_PATH` | `data/mapleleaf.db` | Đường dẫn CSDL SQLite |
| `DATABASE_URL` | *(trống)* | Dùng PostgreSQL thay SQLite (nếu điền, bỏ qua `DATABASE_PATH`) |
| `AUTOMATION_ENABLED` | `True` | Bật/tắt toàn bộ lớp chạy nền |
| `AUTOMATION_MODE` | `live` | `live` = gọi API thật, `dry-run` = chỉ giả lập |
| `ENCRYPTION_KEY` | *(tự sinh)* | Khoá Fernet mã hoá cookie |
| `TIMEZONE` | `Asia/Ho_Chi_Minh` | Múi giờ cho lịch chạy nền |
| `ADMIN_USER_IDS` | *(trống)* | ID Discord được dùng `/admin`, cách nhau bởi dấu phẩy |
| `GENSHIN_EMOJI` / `HSR_EMOJI` | *(trống)* | Emoji tuỳ biến của server (mặc định dùng Unicode) |

> Xem toàn bộ biến và giải thích trong [`.env.example`](.env.example).

### Chạy bot

```bash
python -m app.main
```

Khi bot online, dùng `/auto session_add` trong Discord để liên kết cookie HoYoLAB.

---

## 🐳 Chạy bằng Docker

```bash
cp .env.example .env      # rồi điền DISCORD_TOKEN
docker compose up -d --build
docker compose logs -f
```

---

## 🎁 Giftcode không đổi được?

Đây là vấn đề phổ biến nhất. Tóm tắt: API đổi mã cần `cookie_token` (chỉ sống ~2 giờ), và muốn bot
**tự gia hạn** thì cookie phải có **`stoken`** — mà `stoken` **không** có trong cookie trình duyệt.

👉 Đọc hướng dẫn đầy đủ: [`docs/HUONG_DAN_LAY_STOKEN.md`](docs/HUONG_DAN_LAY_STOKEN.md)

Cách nhanh nhất:

```bash
.venv/Scripts/python.exe scripts/get_full_cookie.py --discord-user-id <ID_DISCORD_CUA_BAN>
```

Sau đó vào Discord chạy `/auto verify` để kiểm tra.

---

## 🧪 Kiểm thử

```bash
python -m unittest discover tests -v
```

CI tự động chạy test trên Windows và Linux mỗi khi push/PR (xem [`.github/workflows/ci.yml`](.github/workflows/ci.yml)).

---

## 📁 Cấu trúc dự án

```text
Maple-Leaf/
├── app/
│   ├── main.py              # Điểm khởi chạy
│   ├── config.py            # Cấu hình (pydantic-settings)
│   ├── bot/                 # Discord client, error handler, lifecycle
│   ├── automation/          # Lớp tự động hoá chạy nền
│   │   ├── manager.py       #   APScheduler async
│   │   ├── client.py        #   Adapter genshin.py (đổi mã, điểm danh)
│   │   ├── notifications.py #   Gửi thông báo DM/kênh
│   │   ├── tasks/           #   Checkin, Giftcode, Mimo, Accompany, WebEvent
│   │   └── providers/       #   HoYoLAB API, nguồn giftcode, Mimo
│   ├── commands/            # Nhóm Slash Commands
│   ├── services/            # Nghiệp vụ (gồm redeem_service.py)
│   ├── games/               # Lớp trừu tượng game
│   │   ├── genshin/         #   Provider, models, build data
│   │   └── hsr/             #   Provider, models, data JSON
│   ├── db/                  # aiosqlite: database.py, models/, repositories/ (xem app/db/README.md)
│   ├── integrations/        # Enka.Network client + cache TTL
│   ├── render/              # Vẽ thẻ ảnh bằng Pillow
│   ├── security/            # Mã hoá Fernet
│   ├── ui/                  # Views, Modals, Buttons, Select
│   └── utils/               # Localization, validators, rate limit
├── deploy/postgres/         # Triển khai PostgreSQL (TÙY CHỌN, thử nghiệm)
├── data/                    # Dữ liệu runtime (không commit)
├── docs/                    # Tài liệu (xem docs/README.md)
├── scripts/                 # setup.sh/.bat, get_full_cookie.py
├── tests/                   # Unit test (unittest)
├── .env.example
├── Dockerfile / docker-compose.yml
├── requirements.txt
└── README.md
```

---

## 🛠️ Xử lý sự cố

| Hiện tượng | Nguyên nhân & cách xử lý |
|---|---|
| Bot không online | Chưa điền `DISCORD_TOKEN`, hoặc chưa bật Privileged Intent |
| Slash command không hiện | Chờ vài phút để Discord đồng bộ, hoặc kick/re-invite bot |
| `/auto` báo chưa có tài khoản | Chạy `/account add` trước |
| Giftcode đổi thất bại (`AUTH_REQUIRED`) | Cookie thiếu `stoken` → xem [hướng dẫn lấy stoken](docs/HUONG_DAN_LAY_STOKEN.md) |
| Ảnh thẻ bị lỗi font tiếng Việt | Cài font hỗ trợ tiếng Việt cho hệ thống (Docker đã kèm sẵn) |

---

## 🤝 Đóng góp

Mọi đóng góp đều được hoan nghênh! Đọc [`CONTRIBUTING.md`](CONTRIBUTING.md) trước khi mở PR.
Lịch sử thay đổi ở [`CHANGELOG.md`](CHANGELOG.md).

---

## 🙏 Ghi công

Dự án sử dụng các thư viện và dịch vụ mã nguồn mở sau:

- [genshin.py](https://github.com/seriaati/genshin.py) — client API HoYoLAB.
- [Enka.Network](https://enka.network/) — dữ liệu nhân vật Genshin.
- [hoyo-codes.seria.moe](https://hoyo-codes.seria.moe/) — nguồn giftcode.
- [hoyo-buddy](https://github.com/seriaati/hoyo-buddy) — nguồn cảm hứng cho luồng đổi mã & xử lý token.
- [Mar-7th/StarRailRes](https://github.com/Mar-7th/StarRailRes) — tài nguyên Star Rail.

---

## ⚠️ Miễn trừ trách nhiệm

Dự án này **không liên kết, không được tài trợ và không được chấp thuận** bởi HoYoverse.
Đây là công cụ cộng đồng, sử dụng cookie tài khoản của chính bạn. Hãy tự chịu trách nhiệm khi
sử dụng và luôn tuân thủ Điều khoản dịch vụ của HoYoverse.

---

## 📄 Giấy phép

Phát hành theo giấy phép **MIT** — xem file [`LICENSE`](LICENSE).
Bạn được tự do sử dụng, sao chép, chỉnh sửa và phân phối, miễn là giữ nguyên thông báo bản quyền.
