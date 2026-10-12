# Triển khai PostgreSQL (TÙY CHỌN — thử nghiệm)

> ⚠️ **Thư mục này KHÔNG thuộc runtime mặc định.**
> Maple Leaf mặc định chạy với **SQLite** (xem [`app/db/README.md`](../../app/db/README.md)).
> Toàn bộ mã trong đây chỉ dùng khi bạn muốn triển khai trên **PostgreSQL**.

---

## Vì sao tách riêng?

Runtime của bot (`app/db/database.py`) dùng **aiosqlite + SQL thô** — nhẹ, không cần cài thêm gì,
phù hợp cho hầu hết người dùng tải repo về chạy. Song song đó, dự án có sẵn một hướng triển khai
PostgreSQL (SQLAlchemy ORM + Alembic) dành cho các kịch bản deploy quy mô lớn hơn. Để tránh gây
nhầm lẫn cho người dùng mới, phần này được gom vào một chỗ và đánh dấu rõ là **tuỳ chọn**.

> 📌 **Trạng thái hiện tại:** phần PostgreSQL **chưa được nối vào runtime** — bot vẫn luôn dùng
> SQLite dù bạn có điền `DATABASE_URL`. Cần thêm việc để hoàn thiện (xem *Việc còn lại*).

---

## Nội dung

| File | Vai trò |
|---|---|
| `orm.py` | Mô hình SQLAlchemy ORM (nguồn schema cho PostgreSQL) |
| `session.py` | AsyncEngine + session factory (SQLAlchemy 2.0 async) |
| `alembic.ini` + `alembic/` | Cấu hình & migration Alembic |
| `migrate_sqlite_to_postgres.py` | Chuyển dữ liệu từ SQLite sang PostgreSQL |
| `legacy/migration_001_automation.sql` | Migration SQL thủ công đầu tiên (đã được thay bằng `SCHEMA_SQL`) |

---

## Cách dùng

```bash
# 1) Cài dependency (đã có trong requirements.txt)
pip install -r requirements.txt

# 2) Tạo bảng trên PostgreSQL bằng Alembic
python -m alembic -c deploy/postgres/alembic.ini upgrade head

# 3) Chuyển dữ liệu từ SQLite sang (tuỳ chọn)
python -m deploy.postgres.migrate_sqlite_to_postgres \
    --sqlite-path data/mapleleaf.db \
    --pg-url postgresql+asyncpg://user:pass@host:5432/dbname
```

---

## Việc còn lại (nếu muốn hoàn thiện)

Để PostgreSQL trở thành runtime thật sự, cần:

1. Viết lớp truy cập CSDL bất đồng bộ dùng SQLAlchemy thay cho `aiosqlite` trong `app/db/`.
2. Chuyển toàn bộ `app/db/repositories/*` sang dùng `AsyncSession` (hiện đang dùng SQL thô `?`).
3. Nối `settings.async_database_url` vào `app/bot/lifecycle.py` để tự chọn engine theo `DATABASE_URL`.

Đóng góp cho phần này rất được hoan nghênh — xem [`CONTRIBUTING.md`](../../CONTRIBUTING.md).
