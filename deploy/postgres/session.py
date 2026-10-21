"""Quản lý kết nối Async Database (SQLAlchemy 2.0 Async + asyncpg/aiosqlite)."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from loguru import logger
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings
from deploy.postgres.orm import Base

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_async_engine() -> AsyncEngine:
    """Khởi tạo hoặc trả về AsyncEngine hiện tại."""
    global _engine
    if _engine is None:
        url = settings.async_database_url
        is_sqlite = url.startswith("sqlite")

        kwargs = {"echo": False}
        if not is_sqlite:
            # Tối ưu kết nối PostgreSQL trên Render
            kwargs.update({
                "pool_size": 10,
                "max_overflow": 20,
                "pool_pre_ping": True,
                "pool_recycle": 1800,
            })

        _engine = create_async_engine(url, **kwargs)
        logger.info(f"Đã khởi tạo SQLAlchemy AsyncEngine: {url.split('@')[-1] if '@' in url else url}")

    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Trả về async_sessionmaker dùng chung."""
    global _session_factory
    if _session_factory is None:
        engine = get_async_engine()
        _session_factory = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
    return _session_factory


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Context manager an toàn cung cấp phiên làm việc AsyncSession với tự động rollback nếu lỗi."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db():
    """Khởi tạo bảng trong cơ sở dữ liệu nếu chưa tồn tại."""
    engine = get_async_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Đã khởi tạo và đồng bộ bảng cơ sở dữ liệu SQLAlchemy thành công.")


async def close_db():
    """Đóng pool kết nối cơ sở dữ liệu khi tắt bot."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
        logger.info("Đã đóng kết nối SQLAlchemy AsyncEngine.")
