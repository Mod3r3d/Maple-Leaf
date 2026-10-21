"""Tác vụ giữ cho phiên HoYoLAB luôn sống — chỉ cần đăng nhập MỘT LẦN.

Bối cảnh:
    `cookie_token` (token dùng để đổi Giftcode) chỉ có hiệu lực khoảng vài giờ.
    Nếu không làm mới, vài giờ sau khi đăng nhập là tính năng đổi mã ngừng hoạt động
    và người dùng lại phải dán cookie mới.

Cách hoạt động:
    Khi cookie có `stoken` + `ltmid_v2`, bot có thể xin cấp lại `cookie_token_v2`
    và `ltoken_v2` bất kỳ lúc nào. Tác vụ này chạy định kỳ (mặc định 12 giờ/lần,
    cấu hình qua `TOKEN_REFRESH_INTERVAL_HOURS`), làm mới token cho TẤT CẢ phiên
    và lưu bản mới vào CSDL.

    Nhờ vậy: đăng nhập một lần → bot tự gia hạn mãi mãi, cho tới khi `stoken`
    bị thu hồi (đăng xuất khỏi mọi thiết bị, đổi mật khẩu...).
"""

from typing import Any, Dict, List

from loguru import logger

from app.automation.client import HoyoClientAdapter
from app.automation.tasks.base import AutomationTask
from app.db.repositories.automation import SessionRepository


class TokenRefreshTask(AutomationTask):
    """Làm mới `cookie_token`/`ltoken_v2` cho mọi phiên có `stoken`."""

    def __init__(self):
        super().__init__("Tự Gia Hạn Token HoYoLAB")

    async def execute(self) -> Dict[str, Any]:
        sessions = await SessionRepository.get_all_sessions()
        if not sessions:
            return {
                "status": "SUCCESS",
                "message": "Chưa có phiên đăng nhập nào — không cần gia hạn.",
            }

        refreshed = 0
        no_stoken = 0
        failed: List[str] = []

        for sess in sessions:
            label = f"{sess.game.short_name} · UID {sess.uid}"

            try:
                raw_cookie = await SessionRepository.get_decrypted_cookie(sess)
            except Exception as e:  # noqa: BLE001
                failed.append(f"{label} (không giải mã được cookie: {e})")
                continue

            if not raw_cookie:
                failed.append(f"{label} (cookie trống hoặc không giải mã được)")
                continue

            adapter = HoyoClientAdapter(
                game=sess.game,
                uid=sess.uid,
                raw_cookie=raw_cookie,
                discord_user_id=sess.discord_user_id,
            )

            if not adapter.has_stoken:
                no_stoken += 1
                continue

            if await adapter.try_refresh_tokens():
                refreshed += 1
            else:
                failed.append(f"{label} (stoken bị từ chối hoặc đã bị thu hồi)")

        parts = [f"Đã gia hạn {refreshed}/{len(sessions)} phiên."]
        if no_stoken:
            parts.append(
                f"{no_stoken} phiên thiếu `stoken` nên không tự gia hạn được — "
                f"chạy `scripts/get_full_cookie.py` một lần để bật chế độ đăng nhập một lần."
            )
        if failed:
            parts.append("Lỗi: " + "; ".join(failed))

        message = " ".join(parts)
        logger.info(f"[TokenRefresh] {message}")

        return {
            "status": "SUCCESS" if not failed else "PARTIAL_SUCCESS",
            "message": message,
            "refreshed": refreshed,
            "missing_stoken": no_stoken,
            "failed": len(failed),
        }
