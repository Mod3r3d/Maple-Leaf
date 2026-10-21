"""Đăng nhập HoYoLAB qua endpoint **app** để lấy cookie đầy đủ (bao gồm `stoken`).

Vì sao cần module này?
    - Đăng nhập web (`login_with_password`) **không** trả về `stoken`.
    - Chỉ endpoint app (`login_with_app_password`) mới cấp `stoken` — thứ duy nhất
      giúp bot tự gia hạn `cookie_token` (token đổi Giftcode chỉ sống vài giờ).

Lưu ý khi chạy trong bot Discord:
    Luồng đăng nhập gốc của thư viện có 2 bước tương tác **trên máy chạy bot**:
    captcha (mở web server nội bộ) và mã xác minh email (nhập từ terminal).
    Bot không thể đưa 2 bước đó cho người dùng Discord, nên module này **chặn sớm**
    và trả về lỗi rõ ràng để người dùng chuyển sang script local.

    Mật khẩu chỉ tồn tại trong bộ nhớ trong lúc gọi API và **không được ghi log**.
"""

import asyncio
import uuid
from typing import Dict

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
            "HoYoLAB yêu cầu **captcha**. Bot không thể hiển thị captcha trong Discord — "
            "hãy chạy `scripts/get_full_cookie.py` trên máy tính để hoàn tất."
        )


class LoginNeedsEmailCode(LoginError):
    def __init__(self):
        super().__init__(
            "HoYoLAB yêu cầu **mã xác minh email** (thường gặp ở lần đăng nhập đầu trên thiết bị mới). "
            "Hãy chạy `scripts/get_full_cookie.py` trên máy tính để nhập mã."
        )


class LoginTimeout(LoginError):
    def __init__(self):
        super().__init__("Đăng nhập quá thời gian chờ. Hãy thử lại sau ít phút.")


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


async def login_with_app(email: str, password: str, *, timeout: float = 90.0) -> Dict[str, str]:
    """Đăng nhập app HoYoLAB và trả về dict cookie đầy đủ (có `stoken`).

    Raises:
        LoginNeedsCaptcha / LoginNeedsEmailCode / LoginTimeout / LoginError
        cùng các lỗi gốc của `genshin` (sai mật khẩu, tài khoản không tồn tại...).
    """
    # Import muộn để tránh vòng lặp import khi bot khởi động.
    from genshin.client.components.auth import server as auth_server

    async def _reject_captcha(_mmt):
        raise LoginNeedsCaptcha()

    async def _reject_email_code(*, prompt: str = "") -> str:  # noqa: ARG001
        raise LoginNeedsEmailCode()

    original_enter_code = auth_server.enter_code
    auth_server.enter_code = _reject_email_code

    try:
        async with _LOGIN_LOCK:
            client = genshin.Client()
            result = await asyncio.wait_for(
                client.login_with_app_password(
                    email,
                    password,
                    device_id=get_or_create_device_id(),
                    geetest_solver=_reject_captcha,
                ),
                timeout=timeout,
            )
    except asyncio.TimeoutError as exc:
        raise LoginTimeout() from exc
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
