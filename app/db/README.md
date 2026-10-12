# Lớp cơ sở dữ liệu (Database Layer)

## Nguồn sự thật duy nhất (Single source of truth)

**Runtime của bot chỉ dùng một cơ chế CSDL duy nhất:**

```
app/db/database.py   ←  SCHEMA_SQL  (định nghĩa toàn bộ bảng + index)
```

- `database.py` mở kết nối **aiosqlite**, bật WAL mode + busy timeout, rồi chạy `SCHEMA_SQL`
  với `CREATE TABLE IF NOT EXISTS` → **tự tạo bảng ở lần chạy đầu**, không cần migration thủ công.
- Mọi thay đổi schema phải được thêm vào `SCHEMA_SQL` (và thêm `ALTER TABLE ... ADD COLUMN`
  trong khối migration an toàn ở `Database.connect()` nếu cột mới cần bổ sung cho CSDL cũ).

> ❗ **Không** tạo thêm file migration SQL rời rạc ở nơi khác — sẽ gây trùng lặp schema.

## Các lớp trong thư mục này

| Đường dẫn | Vai trò |
|---|---|
| `database.py` | Kết nối aiosqlite, `SCHEMA_SQL`, `AsyncRLock`, context manager `get_connection()` / `transaction()` |
| `models/` | **Dataclass thuần** mô tả dữ liệu (`AccountModel`, `SessionModel`, `GiftCodeModel`...) — không phải ORM |
| `repositories/` | Hàm truy vấn SQL thô, mỗi repository phụ trách một nhóm bảng |

## Luồng truy cập

```
commands/  ──►  services/  ──►  repositories/  ──►  database.db.get_connection()
```

- Luôn truy cập CSDL qua `async with db.get_connection() as conn:` để được xếp hàng tuần tự
  qua `AsyncRLock` (tránh lỗi `database is locked`).
- Dùng `async with db.transaction():` khi cần nhóm nhiều câu lệnh và tự rollback khi lỗi.

## PostgreSQL

Nếu bạn cần PostgreSQL, xem [`deploy/postgres/`](../../deploy/postgres/README.md).
Phần đó là **tuỳ chọn và chưa được nối vào runtime**.
