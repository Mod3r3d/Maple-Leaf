"""Đăng nhập HoYoLAB qua endpoint **app** để lấy cookie đầy đủ (bao gồm `stoken`).

Hỗ trợ giải Captcha tương tác qua Cổng Web Portal (HealthCheckServer)
và nhập mã xác thực OTP 6 số từ Email trực tiếp qua Discord Modal.
"""

import asyncio
import uuid
from typing import Any, Awaitable, Callable, Dict, Optional

import genshin
from loguru import logger

from app.config import settings

DEVICE_ID_FILE = settings.DATA_DIR / ".app_device_id"

# Chỉ cho phép một lượt đăng nhập tại một thời điểm: hàm `enter_code` của thư viện
# bị vá tạm thời, đăng nhập song song sẽ làm hỏng việc khôi phục.
_LOGIN_LOCK = asyncio.Lock()


class LoginError(Exception):
    """Lỗi đăng nhập với thông điệp hiển thị được cho người dùng."""


class LoginNeedsCaptcha(LoginError):
    def __init__(self):
        super().__init__(
            "HoYoLAB yêu cầu **captcha**. Vui lòng mở đường dẫn giải Captcha được cung cấp để hoàn tất."
        )


class LoginNeedsEmailCode(LoginError):
    def __init__(self):
        super().__init__(
            "HoYoLAB yêu cầu **mã xác minh email** (thường gặp ở lần đăng nhập đầu trên thiết bị mới). "
            "Vui lòng nhấn nút nhập mã xác nhận trên Discord để hoàn tất."
        )


class LoginTimeout(LoginError):
    def __init__(self, message: str = "Đăng nhập quá thời gian chờ (180 giây). Hãy thử lại sau ít phút."):
        super().__init__(message)


def get_or_create_device_id() -> str:
    """Đọc hoặc tạo device_id cố định (giúp các lần đăng nhập sau ít bị xác minh hơn)."""
    settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
    if DEVICE_ID_FILE.exists():
        value = DEVICE_ID_FILE.read_text(encoding="utf-8").strip()
        if value:
            return value

    value = str(uuid.uuid4())
    DEVICE_ID_FILE.write_text(value, encoding="utf-8")
    logger.info(f"Đã tạo device_id mới cho đăng nhập HoYoLAB tại {DEVICE_ID_FILE}")
    return value


def patch_genshin_login() -> None:
    """Vá lỗi upstream của thư viện genshin.py:

    Trong genshin/client/components/auth/client.py, sau khi giải xong Captcha gửi email
    (mmt = await self._send_verification_email(result)), thư viện bỏ quên bước gọi lại
    `await self._send_verification_email(result, mmt_result=mmt_result)`.
    Điều này khiến HoYoLAB không bao giờ thực sự gửi email OTP về hòm thư người dùng!
    """
    from genshin.client.components.auth import server
    from genshin.client.components.auth.client import AuthClient
    from genshin.models.auth.geetest import SessionMMT, SessionMMTv4
    from genshin.models.auth.verification import ActionTicket

    if getattr(AuthClient, "_maple_leaf_patched", False):
        return

    async def patched_login_with_app_password(
        self,
        account: str,
        password: str,
        *,
        device_id: Optional[str] = None,
        device_name: Optional[str] = None,
        device_model: Optional[str] = None,
        encrypted: bool = False,
        geetest_solver: Optional[Any] = None,
        port: int = 5000,
    ) -> Any:
        device_id = device_id or self.generate_app_device_id()
        result = await self._app_login(
            account,
            password,
            device_id=device_id,
            device_name=device_name,
            device_model=device_model,
            encrypted=encrypted,
        )

        if isinstance(result, SessionMMT):
            if geetest_solver:
                mmt_result = await geetest_solver(result)
            else:
                mmt_result = await server.solve_geetest(result, port=port)

            result = await self._app_login(
                account,
                password,
                device_id=device_id,
                device_name=device_name,
                device_model=device_model,
                encrypted=encrypted,
                mmt_result=mmt_result,
            )
        elif isinstance(result, SessionMMTv4):
            if geetest_solver:
                mmt_result = await geetest_solver(result)
            else:
                mmt_result = await server.solve_geetest(
                    result,
                    port=port,
                    for_new_os_app=True,
                    api_server=server.HOYOLAB_GT_SERVER,
                )

            result = await self._app_login(
                account,
                password,
                device_id=device_id,
                device_name=device_name,
                device_model=device_model,
                encrypted=encrypted,
                mmt_result=mmt_result,
            )

        if isinstance(result, ActionTicket):
            # Email verification required
            mmt = await self._send_verification_email(result)
            if mmt:
                if geetest_solver:
                    mmt_result = await geetest_solver(mmt)
                else:
                    mmt_result = await server.solve_geetest(mmt, port=port)

                # VÁ LỖI UPSTREAM: Gọi lại _send_verification_email kèm mmt_result đã giải
                # để HoYoLAB thực sự gửi email OTP chứa mã 6 số về hòm thư người dùng!
                await self._send_verification_email(result, mmt_result=mmt_result)

            code = await server.enter_code()
            await self._verify_email(code, result)

            result = await self._app_login(
                account,
                password,
                device_id=device_id,
                device_name=device_name,
                device_model=device_model,
                encrypted=encrypted,
                ticket=result,
            )

        return result

    AuthClient.login_with_app_password = patched_login_with_app_password
    AuthClient._maple_leaf_patched = True
    logger.debug("Đã áp dụng bản vá lỗi gửi email OTP HoYoLAB cho genshin.py.")


# Kích hoạt bản vá ngay khi module được nạp
patch_genshin_login()


async def login_with_app(
    email: str,
    password: str,
    *,
    timeout: float = 180.0,
    captcha_callback: Optional[Callable[[str, str], Awaitable[None]]] = None,
    captcha_solved_callback: Optional[Callable[[], Awaitable[None]]] = None,
    otp_callback: Optional[Callable[[], Awaitable[str]]] = None,
) -> Dict[str, str]:
    """Đăng nhập app HoYoLAB và trả về dict cookie đầy đủ (có `stoken`).

    Hỗ trợ:
    - captcha_callback(session_id, captcha_url): Được gọi khi HoYoLAB yêu cầu giải Captcha.
    - captcha_solved_callback(): Được gọi khi Captcha được giải thành công trên Web.
    - otp_callback() -> str: Được gọi khi HoYoLAB yêu cầu mã xác minh OTP 6 số từ email.
    """
    # Import muộn để tránh vòng lặp import khi bot khởi động.
    from genshin.client.components.auth import server as auth_server

    from app.bot.health_server import health_server

    async def _handle_captcha(mmt: Any) -> Any:
        """Xử lý Geetest Captcha qua Web Portal của Maple Leaf."""
        if not captcha_callback:
            raise LoginNeedsCaptcha()

        session_id = str(uuid.uuid4())
        captcha_url = f"{settings.web_base_url}/captcha/{session_id}"
        future = asyncio.get_running_loop().create_future()

        health_server.register_captcha_session(session_id, mmt, future)
        try:
            await captcha_callback(session_id, captcha_url)

            # Đợi người dùng kéo thanh trượt Captcha trên trình duyệt
            res = await asyncio.wait_for(future, timeout=120.0)
            if captcha_solved_callback:
                await captcha_solved_callback()
            return res
        except asyncio.TimeoutError as exc:
            raise LoginTimeout("Quá thời gian chờ giải Captcha (120 giây). Vui lòng thử lại.") from exc
        finally:
            health_server.cleanup_captcha_session(session_id)

    async def _handle_email_code(*, prompt: str = "") -> str:  # noqa: ARG001
        """Xử lý nhập mã xác thực OTP 6 số từ email."""
        if otp_callback:
            code = await otp_callback()
            if not code:
                raise LoginError("Chưa nhập mã xác nhận OTP.")
            return code
        raise LoginNeedsEmailCode()

    original_enter_code = auth_server.enter_code
    auth_server.enter_code = _handle_email_code

    try:
        async with _LOGIN_LOCK:
            client = genshin.Client()
            result = await asyncio.wait_for(
                client.login_with_app_password(
                    email,
                    password,
                    device_id=get_or_create_device_id(),
                    geetest_solver=_handle_captcha,
                ),
                timeout=timeout,
            )
    except asyncio.TimeoutError as exc:
        raise LoginTimeout() from exc
    except genshin.errors.WrongOTP as exc:
        raise LoginError("Mã xác minh (OTP) không chính xác hoặc đã hết hạn. Hãy thử lại.") from exc
    except (genshin.errors.VerificationCodeRateLimited, genshin.errors.OTPRateLimited) as exc:
        raise LoginError("Đã yêu cầu mã xác minh quá nhiều lần. Vui lòng chờ vài phút rồi thử lại.") from exc
    finally:
        auth_server.enter_code = original_enter_code

    cookies: Dict[str, str] = {k: v for k, v in dict(result.to_dict()).items() if v}
    if not cookies.get("stoken"):
        raise LoginError(
            "Đăng nhập thành công nhưng HoYoLAB không trả về `stoken`. "
            "Hãy dùng `scripts/get_full_cookie.py` để lấy cookie đầy đủ."
        )

    # Lấy thêm ltoken_v2 + cookie_token_v2 để dùng được ngay (không bắt buộc).
    try:
        refreshed = await genshin.fetch_cookie_with_stoken_v2(cookies, token_types=[2, 4])
        cookies.update({k: v for k, v in dict(refreshed).items() if v})
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Chưa lấy được ltoken_v2/cookie_token_v2 ngay sau đăng nhập: {exc}")

    return cookies
