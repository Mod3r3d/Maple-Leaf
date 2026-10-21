"""Dịch vụ thống nhất xử lý đổi mã Giftcode (RedeemService).

Tập trung nghiệp vụ đổi mã cho cả lệnh thủ công (/giftcode redeem)
và hệ thống tự động chạy ngầm (Persistent Redemption Queue).
"""

import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple
from urllib.parse import parse_qs, unquote, urlparse

from loguru import logger

from app.automation.providers.hoyolab import HoYoLABRedeemProvider
from app.config import settings
from app.db.models.account import AccountModel
from app.db.models.automation import RedemptionJobModel
from app.db.repositories.accounts import AccountRepository
from app.db.repositories.automation import (
    AutomationSettingsRepository,
    GiftCodeRepository,
    RedemptionJobRepository,
    SessionRepository,
)
from app.games.enums import GameType

# Các lỗi tạm thời cho phép thử lại (Retry)
RETRYABLE_STATUSES = {"NETWORK_ERROR", "TIMEOUT", "RATE_LIMITED"}

# Các lỗi dứt điểm hoặc hoàn thành (Không Retry)
TERMINAL_STATUSES = {
    "SUCCESS",
    "ALREADY_REDEEMED",
    "EXPIRED",
    "INVALID_CODE",
    "ACCOUNT_NOT_ELIGIBLE",
    "LEVEL_TOO_LOW",
    "REGION_LOCK",
}

# Lịch trình backoff retry theo số lần thử
BACKOFF_DELAYS_SECONDS = [30, 120, 600]
MAX_RETRY_ATTEMPTS = 3

# Regex mã quà tặng: 4-32 ký tự, gồm chữ cái, số, gạch nối và gạch dưới
GIFTCODE_REGEX = re.compile(r"^[A-Z0-9_\-]{4,32}$")


def normalize_giftcode(raw_input: str) -> Optional[str]:
    """Chuẩn hóa mã Giftcode từ chuỗi nhập vào hoặc URL đổi mã HoYoverse.

    Hỗ trợ:
    - Mã thuần: 'GENSHINGIFT', '  hsr2024  ' -> 'GENSHINGIFT', 'HSR2024'
    - URL đổi mã HoYoverse / HoYoLAB:
      * https://genshin.hoyoverse.com/en/gift?code=GENSHINGIFT
      * https://hsr.hoyoverse.com/gift?cdkey=HSRGIFT
      * https://act.hoyolab.com/.../?gift_code=SPECIAL
    - Chuỗi có chứa tham số '?code=...', '?cdkey=...', '?giftcode=...'

    Trả về mã đã chuẩn hóa (in hoa, bỏ khoảng trắng), hoặc None nếu không hợp lệ.
    """
    if not raw_input or not isinstance(raw_input, str):
        return None

    cleaned = raw_input.strip()
    if not cleaned:
        return None

    # Nếu chuỗi là URL hoặc chứa cấu trúc liên kết web
    if "://" in cleaned or cleaned.startswith("www.") or "hoyoverse.com" in cleaned or "hoyolab.com" in cleaned:
        candidate_url = cleaned if "://" in cleaned else f"https://{cleaned}"
        try:
            parsed = urlparse(candidate_url)
            query_params = parse_qs(parsed.query)
            for param in ("code", "cdkey", "giftcode", "gift_code"):
                if param in query_params and query_params[param]:
                    extracted = unquote(query_params[param][0]).strip()
                    if extracted:
                        cleaned = extracted
                        break
        except Exception as e:
            logger.debug(f"Lỗi khi giải mã URL đổi mã '{raw_input}': {e}")

    # Bỏ khoảng trắng thừa và viết hoa
    final_code = cleaned.strip().upper()

    # Kiểm tra theo định dạng chuẩn
    if not GIFTCODE_REGEX.match(final_code):
        return None

    return final_code


class RedeemService:
    """Service điều phối toàn bộ luồng đổi mã quà tặng."""

    @staticmethod
    async def redeem_for_account(
        account: AccountModel,
        code: str,
        gift_code_id: Optional[int] = None,
        is_manual: bool = False,
    ) -> Tuple[str, str]:
        """Thực hiện đổi mã cho một tài khoản cụ thể."""
        clean_code = normalize_giftcode(code)
        if not clean_code:
            return (
                "INVALID_CODE",
                f"Mã quà tặng '{code}' không hợp lệ hoặc sai định dạng. Vui lòng nhập mã trực tiếp (VD: `GENSHINGIFT`) "
                f"hoặc dán liên kết có chứa tham số `?code=...`.",
            )

        # 1. Tìm hoặc liên kết gift_code_id nếu chưa có
        if not gift_code_id:
            existing = await GiftCodeRepository.search_code(clean_code, game=account.game)
            if existing:
                gift_code_id = existing[0].id
            else:
                # Tạo gift code tạm trong DB
                model, _ = await GiftCodeRepository.add_code(clean_code, account.game, source="manual" if is_manual else "auto")
                gift_code_id = model.id

        # 2. Kiểm tra xem mã đã được đổi thành công/trùng lặp trên account này chưa
        if not is_manual and await GiftCodeRepository.is_redeemed(account.id, gift_code_id):
            return "ALREADY_REDEEMED", "Mã này đã được ghi nhận đổi thành công trước đó."

        # 3. Lấy session cookie
        sess = await SessionRepository.get_session(account.discord_user_id, account.game, account.uid)
        if not sess:
            return "AUTH_REQUIRED", "Chưa liên kết Cookie HoYoLAB. Hãy dùng /auto session_add để thêm cookie."

        cookie = await SessionRepository.get_decrypted_cookie(sess)
        if not cookie:
            return "AUTH_REQUIRED", "Không thể giải mã Cookie hoặc Cookie rỗng."

        # 4. Kiểm tra chế độ DRY-RUN
        if settings.AUTOMATION_MODE == "dry-run" and not is_manual:
            logger.info(f"[DRY-RUN] Giả lập đổi mã {clean_code} cho {account.nickname or account.uid}")
            await GiftCodeRepository.record_redemption(
                account_id=account.id,
                gift_code_id=gift_code_id,
                game=account.game,
                code=clean_code,
                status="SUCCESS",
                response_msg="[DRY-RUN] Giả lập đổi mã thành công",
            )
            return "SUCCESS", "[Mô Phỏng - Dry Run] Giả lập đổi mã thành công (Không gọi HoYoverse, không gửi quà trong game)"

        # 5. Gọi Provider thực hiện đổi mã thực tế
        status, msg = await HoYoLABRedeemProvider.redeem_code(
            game=account.game,
            uid=account.uid,
            server_region=account.server.value,
            code=clean_code,
            cookie=cookie,
            discord_user_id=account.discord_user_id,
        )

        # 6. Ghi lại lịch sử đổi mã
        await GiftCodeRepository.record_redemption(
            account_id=account.id,
            gift_code_id=gift_code_id,
            game=account.game,
            code=clean_code,
            status=status,
            response_msg=msg,
        )

        # 7. Xử lý khi Cookie hết hạn hoặc thiếu quyền
        if status == "AUTH_REQUIRED":
            # Không đánh dấu EXPIRED toàn bộ session vì ltoken_v2 vẫn có thể dùng để điểm danh hàng ngày bình thường.
            logger.warning(f"Tài khoản UID {account.uid} thiếu hoặc hết hạn token đổi mã (cookie_token). Điểm danh vẫn duy trì bình thường.")

        return status, msg

    @staticmethod
    async def process_job(job: RedemptionJobModel) -> Tuple[str, str]:
        """Xử lý một Job trong Persistent Redemption Queue."""
        await RedemptionJobRepository.mark_running(job.id)

        account = await AccountRepository.get_by_id(job.account_id)
        if not account:
            await RedemptionJobRepository.mark_completed(job.id, status="CANCELLED", error_message="Tài khoản không tồn tại")
            return "CANCELLED", "Tài khoản không tồn tại"

        gift = await GiftCodeRepository.get_by_id(job.gift_code_id)
        if not gift:
            await RedemptionJobRepository.mark_completed(job.id, status="CANCELLED", error_message="Mã giftcode không tồn tại")
            return "CANCELLED", "Mã giftcode không tồn tại"

        # Thực hiện đổi mã qua RedeemService
        status, msg = await RedeemService.redeem_for_account(
            account=account,
            code=gift.code,
            gift_code_id=gift.id,
            is_manual=False,
        )

        # Phân loại trạng thái job theo kết quả
        if status in TERMINAL_STATUSES:
            # Lỗi dứt khoát hoặc thành công -> Hoàn thành job
            await RedemptionJobRepository.mark_completed(
                job.id,
                status=status if status in ("SUCCESS", "ALREADY_REDEEMED") else "FAILED",
                error_code=status if status not in ("SUCCESS", "ALREADY_REDEEMED") else None,
                error_message=msg,
            )
        elif status == "AUTH_REQUIRED":
            # Lỗi xác thực -> Đánh dấu FAILED không retry tránh spam
            await RedemptionJobRepository.mark_completed(
                job.id,
                status="FAILED",
                error_code="AUTH_REQUIRED",
                error_message=msg,
            )
        elif status in RETRYABLE_STATUSES:
            # Lỗi mạng / timeout / rate limit -> Tính toán backoff thử lại
            current_attempts = job.attempt_count + 1
            if current_attempts >= MAX_RETRY_ATTEMPTS:
                await RedemptionJobRepository.mark_completed(
                    job.id,
                    status="FAILED",
                    error_code="MAX_RETRIES_EXCEEDED",
                    error_message=f"Vượt quá số lần thử lại tối đa ({MAX_RETRY_ATTEMPTS}). Lỗi cuối: {msg}",
                )
            else:
                delay = BACKOFF_DELAYS_SECONDS[min(current_attempts - 1, len(BACKOFF_DELAYS_SECONDS) - 1)]
                next_retry = datetime.now(timezone.utc) + timedelta(seconds=delay)
                next_retry_str = next_retry.strftime("%Y-%m-%d %H:%M:%S")
                await RedemptionJobRepository.mark_retry(
                    job_id=job.id,
                    next_retry_at_str=next_retry_str,
                    error_code=status,
                    error_message=msg,
                )
                logger.info(f"Đã lên lịch thử lại job #{job.id} sau {delay}s (lần {current_attempts})")
        else:
            await RedemptionJobRepository.mark_completed(
                job.id,
                status="FAILED",
                error_code=status,
                error_message=msg,
            )

        return status, msg

    @staticmethod
    async def get_redeem_status_overview() -> Dict[str, Any]:
        """Tổng hợp thông tin trạng thái Auto Redeem phục vụ lệnh Discord UX."""
        active_genshin = await AutomationSettingsRepository.get_active_automation_accounts("redeem_enabled")
        genshin_accs = [item for item in active_genshin if item[0].game == GameType.GENSHIN]
        hsr_accs = [item for item in active_genshin if item[0].game == GameType.HSR]

        pending_jobs = await RedemptionJobRepository.get_pending_or_retry_jobs(limit=100)

        active_codes_genshin = await GiftCodeRepository.get_active_codes(GameType.GENSHIN)
        active_codes_hsr = await GiftCodeRepository.get_active_codes(GameType.HSR)

        return {
            "genshin_opted_in": len(genshin_accs),
            "hsr_opted_in": len(hsr_accs),
            "genshin_accounts": [acc for acc, _, _ in genshin_accs],
            "hsr_accounts": [acc for acc, _, _ in hsr_accs],
            "pending_queue_count": len(pending_jobs),
            "active_codes_genshin_count": len(active_codes_genshin),
            "active_codes_hsr_count": len(active_codes_hsr),
        }


redeem_service = RedeemService()
