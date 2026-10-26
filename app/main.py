"""Điểm khởi chạy ứng dụng Maple Leaf (Main Entrypoint)."""

import asyncio
import sys

from loguru import logger

from app.bot.client import MapleLeaf
from app.bot.health_server import health_server
from app.config import settings


def setup_logging():
    """Cấu hình định dạng ghi log trực quan và đẹp mắt."""
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    logger.remove()
    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    )
    logger.add(sys.stdout, format=log_format, level=settings.LOG_LEVEL, colorize=True)
    logger.add("logs/mapleleaf.log", rotation="10 MB", retention="7 days", format=log_format, level="DEBUG", encoding="utf-8")


async def start_bot_with_retry(
    bot: MapleLeaf,
    token: str,
    *,
    max_attempts: int = 5,
    base_delay: float = 30.0,
) -> None:
    """Đăng nhập bot, tự thử lại khi Discord trả 429 (global rate limit).

    Vì sao cần: Render Free dùng IP egress chung nên lỗi 429 khi đăng nhập khá phổ biến
    (đặc biệt khi vừa chạy bot ở máy khác với cùng token). Nếu để tiến trình thoát,
    Render sẽ đánh dấu deploy thất bại. Thay vào đó ta chờ theo cấp số nhân rồi thử lại.

    Chỉ thử lại với 429; các lỗi khác (token sai, mất mạng...) được ném ra ngay.
    """
    for attempt in range(1, max_attempts + 1):
        try:
            await bot.start(token)
            return
        except Exception as exc:  # noqa: BLE001
            is_rate_limited = getattr(exc, "status", None) == 429
            if not is_rate_limited or attempt == max_attempts:
                raise

            delay = min(300.0, base_delay * (2 ** (attempt - 1)))
            logger.warning(
                f"Discord đang tạm chặn đăng nhập (429 Too Many Requests). "
                f"Thử lại lần {attempt + 1}/{max_attempts} sau {delay:.0f} giây..."
            )
            await asyncio.sleep(delay)


async def run_bot(bot: MapleLeaf) -> None:
    """Mở Health Check trước, rồi mới đăng nhập.

    Nhờ vậy Render thấy cổng HTTP mở ngay cả khi Discord đang giới hạn đăng nhập,
    tránh việc deploy bị đánh dấu thất bại chỉ vì chờ 429 hết hạn.
    """
    await health_server.start(bot)
    try:
        async with bot:
            await start_bot_with_retry(bot, settings.DISCORD_TOKEN)
    finally:
        await health_server.stop()


def main():
    setup_logging()
    logger.info("Đang khởi động Maple Leaf (Genshin Impact & Honkai: Star Rail)...")

    if not settings.DISCORD_TOKEN:
        logger.warning(
            "⚠️ CHƯA CẤU HÌNH DISCORD_TOKEN trong file .env!\n"
            "👉 Vui lòng mở file .env và điền Token bot của bạn vào dòng:\n"
            "   DISCORD_TOKEN=your_token_here\n"
            "Sau đó chạy lại bot."
        )
        return

    bot = MapleLeaf()

    try:
        asyncio.run(run_bot(bot))
    except KeyboardInterrupt:
        logger.info("Nhận tín hiệu dừng từ người dùng (Ctrl+C). Đang tắt bot...")
    except Exception as e:
        logger.exception(f"Lỗi ngoài ý muốn khi chạy bot: {e}")


if __name__ == "__main__":
    main()
