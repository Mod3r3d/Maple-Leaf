"""Provider kết nối API HoYoLAB cho Daily Check-in và Đổi Giftcode."""

from typing import Dict, Optional, Tuple

import aiohttp
from loguru import logger

from app.games.enums import GameType


class HoYoLABCheckinProvider:
    # URL điểm danh chính thức của HoYoLAB
    GENSHIN_SIGN_URL = "https://sg-hk4e-api.hoyolab.com/event/sol/sign"
    HSR_SIGN_URL = "https://sg-public-api.hoyolab.com/event/luna/os/sign"

    GENSHIN_ACT_ID = "e202102251931481"
    HSR_ACT_ID = "e202303301540311"

    @classmethod
    def _get_headers(cls, cookie: str) -> Dict[str, str]:
        return {
            "User-Agent": "Mozilla/5.0 (Linux; Android 12; Pixel 6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/102.0.0.0 Mobile Safari/537.36 miHoYoBBS/2.40.1",
            "Cookie": cookie,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
            "x-rpc-app_version": "2.40.1",
            "x-rpc-client_type": "5",
            "Referer": "https://act.hoyolab.com/",
            "Origin": "https://act.hoyolab.com",
        }

    @classmethod
    async def perform_checkin(
        cls,
        game: GameType,
        cookie: str,
        uid: Optional[int] = None,
        discord_user_id: Optional[int] = None,
    ) -> Tuple[str, Optional[str], Optional[str]]:
        """
        Thực hiện điểm danh hàng ngày. Ưu tiên qua HoyoClientAdapter (genshin.py),
        fallback sang HTTP trực tiếp nếu không có UID.
        """
        if uid:
            try:
                from app.automation.client import HoyoClientAdapter
                adapter = HoyoClientAdapter(
                    game=game,
                    uid=uid,
                    raw_cookie=cookie,
                    discord_user_id=discord_user_id,
                )
                return await adapter.claim_daily_checkin()
            except Exception as e:
                logger.warning(f"Điểm danh qua genshin.Client gặp lỗi, thử lại qua HTTP: {e}")

        if game == GameType.GENSHIN:
            url = cls.GENSHIN_SIGN_URL
            act_id = cls.GENSHIN_ACT_ID
        else:
            url = cls.HSR_SIGN_URL
            act_id = cls.HSR_ACT_ID

        headers = cls._get_headers(cookie)
        payload = {"act_id": act_id}

        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        retcode = data.get("retcode", -1)
                        message = data.get("message", "OK")

                        if retcode == 0:
                            return "SUCCESS", "Đã nhận phần thưởng điểm danh hôm nay", None
                        elif retcode == -5003:
                            return "ALREADY_CHECKED", "Hôm nay bạn đã điểm danh rồi", None
                        elif retcode in (-100, 10001, -107):
                            return "AUTH_REQUIRED", None, f"Cookie hết hạn hoặc không hợp lệ ({message})"
                        else:
                            return "FAILED", None, f"Mã lỗi {retcode}: {message}"
                    else:
                        return "FAILED", None, f"HTTP {resp.status}"

        except Exception as e:
            logger.error(f"Lỗi kết nối khi checkin {game.display_name}: {e}")
            return "FAILED", None, str(e)


class HoYoLABRedeemProvider:
    """Provider đổi Giftcode tích hợp thư viện chuẩn genshin.py và adapter thông minh."""

    @classmethod
    async def redeem_code(
        cls,
        game: GameType,
        uid: int,
        server_region: str,
        code: str,
        cookie: str,
        discord_user_id: Optional[int] = None,
    ) -> Tuple[str, str]:
        """
        Đổi mã Giftcode cho tài khoản qua HoyoClientAdapter (genshin.py)
        tự động xử lý cooldown, refresh stoken, và bắt lỗi chuẩn.
        """
        from app.automation.client import HoyoClientAdapter
        adapter = HoyoClientAdapter(
            game=game,
            uid=uid,
            raw_cookie=cookie,
            discord_user_id=discord_user_id,
            server_region=server_region,
        )
        return await adapter.redeem_code(code)
