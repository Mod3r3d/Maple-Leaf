"""Script di chuyển dữ liệu từ SQLite sang PostgreSQL (TÙY CHỌN, thử nghiệm).

Chỉ dùng khi bạn muốn triển khai bot trên PostgreSQL thay vì SQLite mặc định.

Cách sử dụng (chạy từ thư mục gốc dự án):
    python -m deploy.postgres.migrate_sqlite_to_postgres \
        [--sqlite-path data/hoyobot.db] \
        [--pg-url postgresql+asyncpg://user:pass@host:port/dbname]
"""

import argparse
import asyncio
import os
import sys
from datetime import datetime
from typing import Any, Dict, List

from loguru import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

# Đảm bảo mã hóa UTF-8 an toàn trên Windows console
if sys.stdout:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
if sys.stderr:
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Bổ sung thư mục gốc dự án vào PYTHONPATH để import được `app` và `deploy`
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from app.config import settings
from deploy.postgres.orm import Base

TABLES_ORDER = [
    "users",
    "accounts",
    "settings",
    "sessions",
    "automation_settings",
    "checkin_executions",
    "gift_codes",
    "giftcode_redemptions",
    "redemption_jobs",
    "web_events",
    "automation_logs",
    "automation_tasks",
]


async def fetch_sqlite_rows(sqlite_engine, table_name: str) -> List[Dict[str, Any]]:
    """Đọc toàn bộ bản ghi từ một bảng trong SQLite."""
    async with sqlite_engine.connect() as conn:
        result = await conn.execute(text(f"SELECT * FROM {table_name}"))
        rows = result.mappings().all()
        return [dict(r) for r in rows]


async def insert_pg_rows(pg_engine, table_name: str, rows: List[Dict[str, Any]]):
    """Ghi các bản ghi vào PostgreSQL."""
    if not rows:
        return

    # Chuẩn hóa kiểu dữ liệu ngày tháng và boolean nếu cần
    for row in rows:
        for k, v in list(row.items()):
            if isinstance(v, str) and len(v) >= 19 and ("-" in v and ":" in v):
                # Chuỗi timestamp từ sqlite ISO format
                try:
                    row[k] = datetime.fromisoformat(v)
                except Exception:
                    pass
            elif k in ("is_default", "redeem_enabled", "checkin_enabled", "mimo_enabled", "accompany_enabled", "notifications_enabled", "notification_enabled"):
                if v is not None:
                    row[k] = bool(v)

    keys = list(rows[0].keys())
    cols_str = ", ".join(f'"{k}"' for k in keys)
    vals_str = ", ".join(f":{k}" for k in keys)

    # Chèn dữ liệu bỏ qua xung đột (DO NOTHING) để an toàn khi chạy lại
    insert_sql = f'INSERT INTO "{table_name}" ({cols_str}) VALUES ({vals_str}) ON CONFLICT DO NOTHING'

    async with pg_engine.begin() as conn:
        for row in rows:
            try:
                await conn.execute(text(insert_sql), row)
            except Exception as e:
                logger.warning(f"Lỗi khi chèn dòng vào {table_name}: {e}")


async def count_table_rows(engine, table_name: str) -> int:
    """Đếm tổng số bản ghi trong bảng."""
    async with engine.connect() as conn:
        try:
            res = await conn.execute(text(f'SELECT COUNT(*) FROM "{table_name}"'))
            return res.scalar() or 0
        except Exception:
            return 0


async def run_migration(sqlite_path: str, pg_url: str):
    logger.info("=" * 60)
    logger.info("BẮT ĐẦU QUÁ TRÌNH DI CHUYỂN DỮ LIỆU: SQLite ➔ PostgreSQL")
    logger.info(f"SQLite Path : {sqlite_path}")
    logger.info(f"PG Target   : {pg_url.split('@')[-1] if '@' in pg_url else pg_url}")
    logger.info("=" * 60)

    sqlite_url = f"sqlite+aiosqlite:///{os.path.abspath(sqlite_path)}"
    
    # Chuẩn hóa pg_url để tương thích asyncpg
    if pg_url.startswith("postgres://"):
        pg_url = pg_url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif pg_url.startswith("postgresql://") and not pg_url.startswith("postgresql+asyncpg://"):
        pg_url = pg_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    sqlite_engine = create_async_engine(sqlite_url, echo=False)
    pg_engine = create_async_engine(pg_url, echo=False)

    # 1. Khởi tạo schema trên PostgreSQL nếu chưa có
    logger.info("Khởi tạo schema trên database đích...")
    async with pg_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    report = []

    # 2. Di chuyển từng bảng theo thứ tự khóa ngoại an toàn
    for table in TABLES_ORDER:
        try:
            sqlite_count_before = await count_table_rows(sqlite_engine, table)
            rows = await fetch_sqlite_rows(sqlite_engine, table)
            if rows:
                await insert_pg_rows(pg_engine, table, rows)
            
            pg_count_after = await count_table_rows(pg_engine, table)

            status = "✅ Khớp" if sqlite_count_before == pg_count_after else f"⚠️ Khác biệt ({sqlite_count_before} vs {pg_count_after})"
            report.append({
                "table": table,
                "sqlite_count": sqlite_count_before,
                "pg_count": pg_count_after,
                "status": status,
            })
            logger.info(f"Đã xử lý bảng {table:22}: SQLite = {sqlite_count_before:4} | PG = {pg_count_after:4} | {status}")
        except Exception as e:
            logger.error(f"Thất bại khi migrate bảng {table}: {e}")
            report.append({
                "table": table,
                "sqlite_count": -1,
                "pg_count": -1,
                "status": f"❌ Lỗi: {e}",
            })

    await sqlite_engine.dispose()
    await pg_engine.dispose()

    # 3. Hiển thị bảng tổng kết
    print("\n" + "=" * 65)
    print(f"{'BẢNG':<24} | {'SQLITE':<8} | {'POSTGRES':<8} | {'TRẠNG THÁI'}")
    print("-" * 65)
    for r in report:
        print(f"{r['table']:<24} | {r['sqlite_count']:<8} | {r['pg_count']:<8} | {r['status']}")
    print("=" * 65 + "\n")
    logger.info("Hoàn tất quá trình di chuyển! Dữ liệu gốc SQLite vẫn được bảo toàn nguyên vẹn.")


def main():
    parser = argparse.ArgumentParser(description="Migrate SQLite to PostgreSQL")
    parser.add_argument("--sqlite-path", default="data/hoyobot.db", help="Đường dẫn file SQLite")
    parser.add_argument(
        "--pg-url",
        default=os.environ.get("DATABASE_URL", ""),
        help="Chuỗi kết nối PostgreSQL (DATABASE_URL)",
    )
    args = parser.parse_args()

    if not args.pg_url:
        logger.error("Vui lòng cung cấp --pg-url hoặc thiết lập biến môi trường DATABASE_URL!")
        sys.exit(1)

    asyncio.run(run_migration(args.sqlite_path, args.pg_url))


if __name__ == "__main__":
    main()
