"""Client Adapter sử dụng genshin.py cho Auto Redeem & Daily Check-in.

Hỗ trợ:
1. Đổi mã quà tặng cho Genshin Impact, Honkai: Star Rail, ZZZ, HI3 qua genshin.Client.
2. Tự động nhận diện lỗi: AlreadyClaimed, RedemptionCooldown, InvalidCookies, RedemptionInvalid, LevelTooLow.
3. Tự động refresh token (ltoken_v2, cookie_token_v2) khi có stoken/stoken_v2.
4. Tự động lưu cookie mới đã refresh vào cơ sở dữ liệu.
"""

import asyncio
from typing import Any, Dict, Optional, Tuple
import genshin
from loguru import logger

from app.games.enums import GameType


def to_genshin_game(game: GameType) -> genshin.Game:
    """Chuyển đổi GameType sang genshin.Game enum."""
    if game == GameType.GENSHIN:
        return genshin.Game.GENSHIN
    elif game == GameType.HSR:
        return genshin.Game.STARRAIL
    return genshin.Game.GENSHIN


def to_genshin_region(server_region: Optional[str]) -> genshin.Region:
    """Chuyển đổi vùng máy chủ của tài khoản sang genshin.Region.

    Mặc định là OVERSEAS (máy chủ quốc tế). Chỉ tài khoản máy chủ Trung Quốc mới
    dùng CHINESE.
    """
    if server_region and str(server_region).strip().lower() in ("china", "cn", "chinese"):
        return genshin.Region.CHINESE
    return genshin.Region.OVERSEAS


def parse_cookie_to_dict(raw_cookie: str) -> Dict[str, str]:
    """Phân tích chuỗi cookie thành dictionary, tự động chuẩn hóa các cặp token v1/v2."""
    cookie_dict: Dict[str, str] = {}
    for part in raw_cookie.split(";"):
        if "=" in part:
            k, v = part.strip().split("=", 1)
            cookie_dict[k.strip()] = v.strip()

    # Chuẩn hóa ltuid <-> account_id
    ltuid = cookie_dict.get("ltuid_v2") or cookie_dict.get("ltuid") or cookie_dict.get("account_id") or cookie_dict.get("account_id_v2")
    if ltuid:
        cookie_dict.setdefault("account_id", ltuid)
        cookie_dict.setdefault("account_id_v2", ltuid)
        cookie_dict.setdefault("ltuid", ltuid)
        cookie_dict.setdefault("ltuid_v2", ltuid)

    # Chuẩn hóa ltmid <-> account_mid / mid
    ltmid = cookie_dict.get("ltmid_v2") or cookie_dict.get("ltmid") or cookie_dict.get("account_mid_v2") or cookie_dict.get("mid")
    if ltmid:
        cookie_dict.setdefault("account_mid_v2", ltmid)
        cookie_dict.setdefault("mid", ltmid)
        cookie_dict.setdefault("ltmid_v2", ltmid)

    # Chuẩn hóa stoken (cần thiết để tự động gia hạn cookie_token đổi mã)
    stoken = cookie_dict.get("stoken_v2") or cookie_dict.get("stoken")
    if stoken:
        cookie_dict.setdefault("stoken", stoken)
        cookie_dict.setdefault("stoken_v2", stoken)

    # Chuẩn hóa cookie_token: ưu tiên bản v2 (mới hơn), tránh bản v1 cũ che khuất,
    # và đồng bộ cả hai khóa để mọi endpoint đổi mã đều đọc được token.
    ctoken = cookie_dict.get("cookie_token_v2") or cookie_dict.get("cookie_token")
    if ctoken:
        cookie_dict["cookie_token"] = ctoken
        cookie_dict["cookie_token_v2"] = ctoken

    return cookie_dict


class HoyoClientAdapter:
    """Adapter tích hợp thư viện genshin.py bao bọc các thao tác API an toàn."""

    def __init__(
        self,
        game: GameType,
        uid: int,
        raw_cookie: str,
        account_id: Optional[int] = None,
        discord_user_id: Optional[int] = None,
        server_region: Optional[str] = None,
    ):
        self.game = game
        self.uid = uid
        self.raw_cookie = raw_cookie
        self.account_id = account_id
        self.discord_user_id = discord_user_id
        self.server_region = server_region
        self.cookie_dict = parse_cookie_to_dict(raw_cookie)
        self.genshin_game = to_genshin_game(game)
        self.genshin_region = to_genshin_region(server_region)

    @property
    def has_stoken(self) -> bool:
        """Cookie có stoken (dùng để tự động gia hạn cookie_token đổi mã) hay không."""
        return bool(self.cookie_dict.get("stoken") or self.cookie_dict.get("stoken_v2"))

    @property
    def has_cookie_token(self) -> bool:
        """Cookie có cookie_token (token dùng riêng cho việc đổi mã) hay không."""
        return bool(self.cookie_dict.get("cookie_token") or self.cookie_dict.get("cookie_token_v2"))

    def _get_client(self) -> genshin.Client:
        """Khởi tạo genshin.Client với cookie hiện tại."""
        client = genshin.Client()
        client.set_cookies(self.cookie_dict)
        client.default_game = self.genshin_game
        client.uid = self.uid
        client.region = self.genshin_region
        return client

    async def try_refresh_tokens(self) -> bool:
        """
        Thử gia hạn tự động cookie_token_v2 và ltoken_v2 nếu tài khoản có stoken/stoken_v2.

        Đây là cơ chế cốt lõi giúp Đổi Giftcode hoạt động lâu dài: token đổi mã
        (cookie_token) có thời hạn rất ngắn, nhưng chỉ cần có `stoken` là bot có thể
        tự làm mới nó vô thời hạn (giống cơ chế của hoyo-buddy gốc).

        Trả về True nếu refresh thành công và đã lưu CSDL, ngược lại False.
        """
        has_mid = bool(
            self.cookie_dict.get("ltmid_v2")
            or self.cookie_dict.get("mid")
            or self.cookie_dict.get("account_mid_v2")
        )

        if not (self.has_stoken and has_mid):
            logger.warning(
                f"Không thể làm mới token đổi mã cho UID {self.uid}: thiếu "
                f"{'stoken' if not self.has_stoken else 'ltmid_v2/mid'} trong cookie."
            )
            return False

        try:
            logger.info(f"Đang thực hiện tự động làm mới token đổi mã qua stoken cho UID {self.uid}...")
            refreshed = await genshin.fetch_cookie_with_stoken_v2(
                self.cookie_dict,
                token_types=[2, 4],  # 2: ltoken_v2, 4: cookie_token_v2
            )
            if refreshed:
                self.cookie_dict.update(refreshed)
                # Đồng bộ cookie_token (v1) trỏ cùng giá trị với cookie_token_v2 để mọi
                # endpoint đổi mã đều đọc được token mới.
                if refreshed.get("cookie_token_v2"):
                    self.cookie_dict["cookie_token"] = refreshed["cookie_token_v2"]

                new_raw = "; ".join(f"{k}={v}" for k, v in self.cookie_dict.items())
                self.raw_cookie = new_raw

                # Lưu phiên cập nhật mới vào database nếu có đủ thông tin
                if self.discord_user_id:
                    from app.db.repositories.automation import SessionRepository
                    await SessionRepository.save_session(
                        discord_user_id=self.discord_user_id,
                        game=self.game,
                        uid=self.uid,
                        raw_cookie=new_raw,
                    )
                logger.info(f"Đã làm mới và lưu token đổi mã thành công cho UID {self.uid}!")
                return True
        except Exception as e:
            logger.warning(f"Làm mới token bằng stoken thất bại cho UID {self.uid}: {e}")

        return False

    def _auth_help_message(self) -> str:
        """Tạo thông điệp hướng dẫn khắc phục khi xác thực đổi mã thất bại."""
        has_mid = bool(
            self.cookie_dict.get("ltmid_v2")
            or self.cookie_dict.get("mid")
            or self.cookie_dict.get("account_mid_v2")
            or self.cookie_dict.get("ltmid")
        )
        if self.has_stoken and not has_mid:
            return (
                "Cookie có `stoken` nhưng thiếu mã định danh `ltmid_v2` (hoặc `mid`). "
                "HoYoLAB yêu cầu mã này để cấp lại token đổi mã. "
                "Hãy dùng `/auto session_add` để thêm lại Cookie đầy đủ."
            )
        if self.has_stoken:
            return (
                "Không thể xác thực đổi mã dù cookie đã có `stoken`. Phiên đăng nhập có thể đã bị thu hồi "
                "hoặc đăng xuất khỏi thiết bị. Hãy dùng `/auto session_add` để cập nhật lại cookie."
            )
        return (
            "Cookie thiếu token đổi mã (`cookie_token`) còn hiệu lực. Token này có thời hạn ngắn "
            "và chỉ tự gia hạn được khi cookie có đủ bộ `stoken` + `ltmid_v2`. "
            "Hãy dùng `/auto session_add` để thêm Cookie đầy đủ (kèm `stoken`), sau đó dùng `/auto verify` để kiểm tra."
        )

    async def redeem_code(self, code: str) -> Tuple[str, str]:
        """
        Đổi mã Giftcode cho tài khoản bằng genshin.py với cơ chế tự làm mới token và bắt lỗi chi tiết.

        Khi gặp lỗi xác thực (InvalidCookies / retcode -1071), bot sẽ tự động thử làm mới
        cookie_token qua stoken rồi đổi lại một lần — đây là điều kiện bắt buộc để đổi mã
        hoạt động lâu dài.

        Trả về: (status, message)
        status: SUCCESS, ALREADY_REDEEMED, INVALID_CODE, EXPIRED, LEVEL_TOO_LOW, REGION_LOCK, AUTH_REQUIRED, RATE_LIMITED, NETWORK_ERROR, FAILED
        """
        code_clean = code.strip().upper()

        has_mid = bool(
            self.cookie_dict.get("ltmid_v2")
            or self.cookie_dict.get("mid")
            or self.cookie_dict.get("account_mid_v2")
            or self.cookie_dict.get("ltmid")
        )

        # Kiểm tra trước: nếu không có cookie_token và không thể làm mới (thiếu stoken hoặc mid)
        if not self.has_cookie_token and not (self.has_stoken and has_mid):
            return "AUTH_REQUIRED", self._auth_help_message()

        # Nếu chưa có cookie_token nhưng có stoken + mid, chủ động refresh trước
        if not self.has_cookie_token and self.has_stoken and has_mid:
            await self.try_refresh_tokens()

        async def _attempt(allow_refresh: bool) -> Tuple[str, str]:
            client = self._get_client()
            try:
                await client.redeem_code(code_clean, uid=self.uid, game=self.genshin_game)
                return "SUCCESS", "Đổi mã thành công! Phần thưởng đã được gửi vào hòm thư trong game."
            except (genshin.errors.AlreadyClaimed, genshin.errors.RedemptionClaimed):
                return "ALREADY_REDEEMED", "Mã này đã được đổi từ trước trên tài khoản này."
            except genshin.errors.RedemptionInvalid:
                return "INVALID_CODE", "Mã giftcode không tồn tại hoặc không hợp lệ."
            except genshin.errors.RedeemGameLevelTooLow:
                return "LEVEL_TOO_LOW", "Cấp bậc nhân vật trong game (Adventure Rank / Cấp Khai Phá) chưa đủ điều kiện nhận quà của mã này."
            except genshin.errors.RedemptionRegionLock:
                return "REGION_LOCK", "Mã giftcode bị giới hạn khu vực máy chủ."
            except genshin.errors.RedemptionCooldown:
                logger.warning(f"HoYoverse kích hoạt Cooldown đổi mã cho UID {self.uid}. Tạm dừng 5 giây...")
                await asyncio.sleep(5.0)
                try:
                    await client.redeem_code(code_clean, uid=self.uid, game=self.genshin_game)
                    return "SUCCESS", "Đổi mã thành công sau nhịp chờ cooldown!"
                except Exception as retry_err:
                    return "RATE_LIMITED", f"Hệ thống đang trong thời gian chờ giãn cách đổi mã (Cooldown): {retry_err}"
            except genshin.errors.InvalidCookies:
                # Lỗi xác thực đổi mã -> thử làm mới cookie_token bằng stoken rồi đổi lại.
                if allow_refresh:
                    refreshed = await self.try_refresh_tokens()
                    if refreshed:
                        return await _attempt(allow_refresh=False)
                return "AUTH_REQUIRED", self._auth_help_message()
            except (genshin.errors.TooManyRequests, genshin.errors.VisitsTooFrequently):
                return "RATE_LIMITED", "Yêu cầu quá dồn dập (Rate Limited), máy chủ HoYoverse tạm thời từ chối."
            except genshin.errors.GenshinException as ge:
                retcode = getattr(ge, "retcode", None)
                msg = getattr(ge, "msg", str(ge))
                if retcode in (-2017, -2018):
                    return "ALREADY_REDEEMED", "Mã này đã được đổi từ trước trên tài khoản này."
                elif retcode == -2016:
                    # Cooldown đổi mã -> chờ rồi thử lại một lần
                    await asyncio.sleep(5.0)
                    return await _attempt(allow_refresh=False)
                elif retcode == -2001:
                    return "EXPIRED", "Mã giftcode đã hết hạn sử dụng."
                elif retcode in (-2003, -2004, -2006, -2014, -1065):
                    return "INVALID_CODE", "Mã giftcode không tồn tại hoặc không hợp lệ."
                elif retcode == -2008:
                    return "REGION_LOCK", "Mã giftcode bị giới hạn khu vực máy chủ."
                elif retcode == -1073:
                    return "AUTH_REQUIRED", "Tài khoản HoYoLAB này không liên kết với UID game đã khai báo."
                elif retcode in (-1071, -100, 10001, 10103):
                    # Token đổi mã không hợp lệ/hết hạn -> thử làm mới rồi đổi lại.
                    if allow_refresh:
                        refreshed = await self.try_refresh_tokens()
                        if refreshed:
                            return await _attempt(allow_refresh=False)
                    return "AUTH_REQUIRED", self._auth_help_message()
                return "FAILED", f"Lỗi ({retcode or 'Hoyo'}): {msg}"
            except (asyncio.TimeoutError, Exception) as e:
                err_str = str(e)
                if "timeout" in err_str.lower() or "connect" in err_str.lower() or isinstance(e, asyncio.TimeoutError):
                    logger.error(f"Lỗi mạng/timeout khi đổi mã {code_clean} cho UID {self.uid}: {e}")
                    return "NETWORK_ERROR", f"Lỗi kết nối mạng tới máy chủ HoYoverse: {e}"
                logger.error(f"Lỗi ngoại lệ khi đổi mã {code_clean} cho UID {self.uid}: {e}")
                return "FAILED", err_str

        return await _attempt(allow_refresh=True)

    # Mã "mồi" chắc chắn không tồn tại, dùng để kiểm tra quyền đổi mã mà KHÔNG đổi thật mã nào.
    PROBE_CODE = "MAPLELEAFVERIFY0000"

    async def check_cookie_token_valid(self) -> Tuple[bool, str]:
        """Kiểm tra (chỉ đọc) xem `cookie_token` dùng cho đổi mã còn hiệu lực hay không.

        Gọi endpoint thông tin tài khoản của HoYoLAB — KHÔNG đổi mã, KHÔNG tác động tài khoản.
        """
        if not self.has_cookie_token:
            return False, "Cookie không có `cookie_token`/`cookie_token_v2`."
        try:
            info = await genshin.fetch_cookie_token_info(
                self.cookie_dict,
                source="cookie_token",
                region=self.genshin_region,
            )
            return True, f"Token đổi mã còn hiệu lực (account_id={info.get('account_id')})."
        except Exception as e:
            return False, f"Token đổi mã KHÔNG hợp lệ hoặc đã hết hạn ({e})."

    async def verify_redeem_access(self) -> Tuple[bool, str, str]:
        """Kiểm tra khả năng xác thực Đổi Giftcode mà không đổi mã thật.

        Gửi một mã giả tới API đổi mã: nếu máy chủ trả về lỗi "mã không hợp lệ/hết hạn/..."
        thì tức là đã xác thực THÀNH CÔNG (máy chủ đã xử lý yêu cầu). Nếu trả về lỗi xác thực
        (AUTH_REQUIRED / -1071) thì cookie không dùng được để đổi mã.

        Trả về: (auth_ok, status, message)
        """
        status, msg = await self.redeem_code(self.PROBE_CODE)
        if status in ("AUTH_REQUIRED", "FAILED"):
            return False, status, msg
        # INVALID_CODE / ALREADY_REDEEMED / EXPIRED / LEVEL_TOO_LOW / REGION_LOCK
        # đều nghĩa là máy chủ đã chấp nhận xác thực và xử lý mã.
        return True, status, msg

    async def claim_daily_checkin(self) -> Tuple[str, Optional[str], Optional[str]]:
        """
        Thực hiện điểm danh hàng ngày qua genshin.Client.
        Trả về: (status, reward_summary, error_code)
        status: SUCCESS, ALREADY_CHECKED, AUTH_REQUIRED, FAILED
        """
        client = self._get_client()
        try:
            reward = await client.claim_daily_reward(game=self.genshin_game)
            if reward:
                reward_text = f"Đã nhận: {reward.amount}x {reward.name}"
            else:
                reward_text = "Đã nhận phần thưởng điểm danh hôm nay"
            return "SUCCESS", reward_text, None
        except (genshin.errors.AlreadyClaimed,):
            return "ALREADY_CHECKED", "Hôm nay bạn đã điểm danh rồi", None
        except genshin.errors.InvalidCookies:
            refreshed = await self.try_refresh_tokens()
            if refreshed:
                client_new = self._get_client()
                try:
                    reward = await client_new.claim_daily_reward(game=self.genshin_game)
                    reward_text = f"Đã nhận: {reward.amount}x {reward.name}" if reward else "Đã nhận quà"
                    return "SUCCESS", reward_text, None
                except genshin.errors.AlreadyClaimed:
                    return "ALREADY_CHECKED", "Hôm nay bạn đã điểm danh rồi", None
                except Exception as e:
                    return "FAILED", None, str(e)

            return "AUTH_REQUIRED", None, "Cookie hết hạn hoặc không hợp lệ (Cần đăng nhập lại)"
        except genshin.errors.DailyGeetestTriggered:
            return "FAILED", None, "HoYoLAB kích hoạt xác minh Geetest Captcha"
        except Exception as e:
            logger.error(f"Lỗi điểm danh qua genshin.Client cho UID {self.uid}: {e}")
            return "FAILED", None, str(e)
