"""Cơ chế mã hóa đối xứng an toàn cho Cookies và Thông tin xác thực (Fernet)."""

import os
from pathlib import Path
from cryptography.fernet import Fernet
from loguru import logger
from app.config import settings


class SecretCipher:
    def __init__(self):
        self._fernet: Fernet | None = None

    def _get_or_create_key(self) -> bytes:
        if settings.ENCRYPTION_KEY:
            return settings.ENCRYPTION_KEY.encode("utf-8")

        key_file = settings.DATA_DIR / ".secret.key"
        settings.DATA_DIR.mkdir(parents=True, exist_ok=True)

        if key_file.exists():
            return key_file.read_bytes().strip()

        new_key = Fernet.generate_key()
        try:
            key_file.write_bytes(new_key)
            logger.info("Đã tạo mới khóa mã hóa bảo mật tại data/.secret.key")
        except Exception as e:
            logger.warning(f"Không thể lưu key file: {e}")
        return new_key

    @property
    def cipher(self) -> Fernet:
        if self._fernet is None:
            key = self._get_or_create_key()
            self._fernet = Fernet(key)
        return self._fernet

    def encrypt(self, plain_text: str) -> str:
        """Mã hóa chuỗi văn bản bí mật."""
        if not plain_text:
            return ""
        encrypted_bytes = self.cipher.encrypt(plain_text.encode("utf-8"))
        return encrypted_bytes.decode("utf-8")

    def decrypt(self, cipher_text: str) -> str:
        """Giải mã văn bản đã mã hóa."""
        if not cipher_text:
            return ""
        decrypted_bytes = self.cipher.decrypt(cipher_text.encode("utf-8"))
        return decrypted_bytes.decode("utf-8")


def mask_cookie(cookie: str) -> str:
    """Che giấu một phần cookie nhạy cảm để hiển thị an toàn trên giao diện."""
    if not cookie:
        return "Chưa cấu hình"
    if len(cookie) <= 12:
        return "***"
    return f"{cookie[:4]}...{cookie[-4:]}"


def inspect_cookie_tokens(raw_cookie: str, full: bool = False) -> dict:
    """Phân tích các token có trong cookie và tạo chuỗi hiển thị an toàn."""
    if not raw_cookie:
        return {
            "tokens": {},
            "has_checkin": False,
            "has_redeem": False,
            "has_stoken": False,
            "has_cookie_token": False,
            "has_mid": False,
            "can_auto_refresh": False,
            "can_redeem_direct": False,
            "redeem_durable": False,
            "missing_for_checkin": ["ltoken_v2", "ltuid_v2"],
            "missing_for_redeem": ["cookie_token_v2", "stoken", "ltmid_v2"],
            "display_str": "Chưa có cookie nào được lưu.",
            "raw_cookie": "",
        }

    parts = [p.strip() for p in raw_cookie.split(";") if p.strip()]
    tokens = {}
    for p in parts:
        if "=" in p:
            k, v = p.split("=", 1)
            tokens[k.strip()] = v.strip()

    # 1. Token Điểm danh hàng ngày (Daily Check-in)
    has_ltoken = bool("ltoken_v2" in tokens or "ltoken" in tokens)
    has_ltuid = bool(
        "ltuid_v2" in tokens
        or "ltuid" in tokens
        or "account_id" in tokens
        or "account_id_v2" in tokens
    )
    has_checkin = has_ltoken and has_ltuid

    missing_for_checkin = []
    if not has_ltoken:
        missing_for_checkin.append("ltoken_v2")
    if not has_ltuid:
        missing_for_checkin.append("ltuid_v2")

    # 2. Token Đổi Giftcode (Direct vs Auto-refresh)
    has_cookie_token = bool("cookie_token_v2" in tokens or "cookie_token" in tokens)
    has_stoken = bool("stoken" in tokens or "stoken_v2" in tokens)
    has_mid = bool(
        "ltmid_v2" in tokens
        or "mid" in tokens
        or "account_mid_v2" in tokens
        or "ltmid" in tokens
    )

    # Đổi bền vững qua stoken bắt buộc phải có stoken VÀ ltmid_v2/mid
    can_auto_refresh = has_stoken and has_mid
    can_redeem_direct = has_cookie_token
    redeem_durable = can_auto_refresh
    has_redeem = can_redeem_direct or can_auto_refresh

    missing_for_redeem = []
    if not can_auto_refresh:
        if not has_stoken:
            missing_for_redeem.append("stoken")
        if not has_mid:
            missing_for_redeem.append("ltmid_v2")
    if not can_redeem_direct and not can_auto_refresh:
        missing_for_redeem.append("cookie_token_v2")

    display_parts = []
    for k, v in tokens.items():
        if not full and len(v) > 16:
            masked_v = f"{v[:6]}...{v[-6:]}"
        else:
            masked_v = v
        display_parts.append(f"{k}={masked_v}")

    return {
        "tokens": tokens,
        "has_checkin": has_checkin,
        "has_redeem": has_redeem,
        "has_stoken": has_stoken,
        "has_cookie_token": has_cookie_token,
        "has_mid": has_mid,
        "can_auto_refresh": can_auto_refresh,
        "can_redeem_direct": can_redeem_direct,
        "redeem_durable": redeem_durable,
        "missing_for_checkin": missing_for_checkin,
        "missing_for_redeem": missing_for_redeem,
        "display_str": "; ".join(display_parts),
        "raw_cookie": raw_cookie,
    }


cipher = SecretCipher()
