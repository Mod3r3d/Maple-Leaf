# Changelog

Mọi thay đổi đáng chú ý của dự án được ghi tại đây.
Định dạng theo [Keep a Changelog](https://keepachangelog.com/vi/1.1.0/),
phiên bản theo [Semantic Versioning](https://semver.org/lang/vi/).

## [Unreleased]

### Added
- **Giấy phép MIT** (`LICENSE`) — dự án chính thức mở cho cộng đồng sử dụng, sửa và phân phối.
- `requirements.in` + `requirements.txt` **ghim cứng phiên bản** (kèm environment marker cho gói
  chỉ dành Windows) để mọi người cài ra đúng bộ thư viện đã kiểm thử.
- Lệnh `/auto verify` để kiểm tra cookie có đổi được Giftcode hay không (không đổi mã thật).
- Script `scripts/get_full_cookie.py` — lấy cookie HoYoLAB đầy đủ (kèm `stoken`) qua đăng nhập
  app, tự ghi vào CSDL của bot.
- Tài liệu `docs/HUONG_DAN_LAY_STOKEN.md` hướng dẫn lấy `stoken` (PCAPdroid + script local).
- Tài liệu `app/db/README.md` (kiến trúc lớp CSDL) và `deploy/postgres/README.md`.
- Emoji game có thể cấu hình qua `GENSHIN_EMOJI` / `HSR_EMOJI` (mặc định dùng Unicode, chạy
  đúng trên mọi server).
- Script cài đặt một lệnh: `scripts/setup.sh` và `scripts/setup.bat`.
- CI GitHub Actions (chạy unit test).
- `SECURITY.md`, `CONTRIBUTING.md`, `CHANGELOG.md`, `.editorconfig`, `.dockerignore`,
  `pyproject.toml`, `requirements-dev.txt`.

### Changed
- **Đổi tên dự án:** Chính thức đổi tên bot và dự án thành **Maple Leaf** — áp dụng nhất quán cho
  tên class (`MapleLeaf`), CSDL (`data/mapleleaf.db`), file log (`logs/mapleleaf.log`), tài liệu,
  link clone và cấu hình Docker.
- **Test dùng CSDL tạm:** bộ kiểm thử nay chạy trên file CSDL tạm (`tests/db_test_utils.py`),
  **không còn ghi vào dữ liệu thật** của người dùng.
- **Dọn lớp CSDL trùng lặp:** `app/db/database.py` (`SCHEMA_SQL`) là **nguồn sự thật duy nhất**
  cho runtime SQLite. Toàn bộ nhánh PostgreSQL (SQLAlchemy ORM, Alembic, script migrate, migration
  SQL cũ) được chuyển vào `deploy/postgres/` và đánh dấu rõ là **tuỳ chọn, thử nghiệm**.
- README viết lại, bổ sung bản tiếng Anh (`README.en.md`).
- Sắp xếp lại tài liệu: kế hoạch nội bộ chuyển vào `docs/dev/`.

### Fixed
- **Bảo mật:** gỡ `data/.secret.key` và các file CSDL `*.db-wal` / `*.db-shm` khỏi git và bổ sung
  `.gitignore` — trước đây khoá mã hoá và dữ liệu cookie bị đưa lên repository.
- **`.env` làm sập bot:** các giá trị màu dạng hex (`0x5BC0BE`) trong `.env` khiến pydantic không
  parse được và `Settings()` ném lỗi. Đã thêm validator chấp nhận `0xRRGGBB`, `#RRGGBB` và số thập phân.
- **Khoá mã hoá không khớp làm sập tác vụ:** `SecretCipher.decrypt` nay trả về chuỗi rỗng kèm cảnh
  báo thay vì ném `InvalidToken`, nhờ đó tác vụ nền không chết khi khoá bị xoay.
- Redeem Giftcode: tự động làm mới `cookie_token` qua `stoken` rồi thử lại khi gặp lỗi xác thực
  (`InvalidCookies` / retcode `-1071`).
- Không còn đánh dấu session `EXPIRED` khi chỉ lỗi đổi mã — nhờ đó Điểm danh không bị hỏng theo.
- Modal `/auto session_add` không còn lỗi `400 Bad Request` do nhãn vượt 45 ký tự.
- `.env.example` được đồng bộ đầy đủ với `app/config.py`.

### Security
- **Xoay khoá mã hoá:** khoá Fernet cũ (`data/.secret.key`) từng bị commit lên repository nên đã bị
  coi là lộ — đã xoá để sinh khoá mới.
- **Dọn session cũ:** toàn bộ cookie đã lưu bằng khoá cũ đã được xoá; người dùng cần liên kết lại
  cookie HoYoLAB (`/auto session_add` hoặc `scripts/get_full_cookie.py`).
- **Khuyến nghị reset Discord Bot Token** (token từng xuất hiện trong log/traceback công khai).

## [1.0.0] - 2026-10-05

### Added
- Bản phát hành đầu tiên: bot Discord cho Genshin Impact và Honkai: Star Rail.
- Điểm danh HoYoLAB, Giftcode (tra cứu + đổi mã thủ công + tự động), nhiệm vụ Mimo, Điểm danh
  Đồng hành, thông báo sự kiện web.
- Hồ sơ người chơi và thẻ nhân vật dạng ảnh (Pillow).
- Hướng dẫn build nhân vật, tra cứu, xem tủ trưng bày nhân vật.
- Mã hoá cookie bằng Fernet; giao diện 100% tiếng Việt.
