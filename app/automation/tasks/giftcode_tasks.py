import asyncio
from typing import Any, Dict
from loguru import logger
from app.automation.notifications import notification_service
from app.automation.providers.giftcodes import GiftcodeDiscoveryProvider
from app.automation.providers.hoyolab import HoYoLABRedeemProvider
from app.automation.tasks.base import AutomationTask
from app.config import settings
from app.db.repositories.automation import (
    AutomationSettingsRepository,
    GiftCodeRepository,
    SessionRepository,
)
from app.games.enums import GameType
from app.automation.providers.giftcodes import GiftcodeAggregator


class GiftcodeDiscoveryTask(AutomationTask):
    def __init__(self):
        super().__init__(name="giftcode_discovery")
        self.aggregator = GiftcodeAggregator()

    async def execute(self) -> Dict[str, Any]:
        from app.services.redeem_service import normalize_giftcode

        total_discovered = 0
        new_codes_count = 0

        for game in (GameType.GENSHIN, GameType.HSR):
            codes = await self.aggregator.collect(game)
            for c_info in codes:
                raw_code = c_info.get("code")
                code_str = normalize_giftcode(raw_code) if raw_code else None
                source = c_info.get("source", "aggregator")
                sources = ", ".join(c_info.get("sources_list", [source]))
                rewards = c_info.get("rewards")
                confidence = c_info.get("confidence", "MEDIUM")
                expires_at = c_info.get("expires_at")

                if not code_str:
                    continue
                total_discovered += 1
                model, is_new = await GiftCodeRepository.add_or_update_code(
                    code=code_str,
                    game=game,
                    source=source,
                    sources=sources,
                    rewards=rewards,
                    confidence=confidence,
                    expires_at=expires_at,
                )
                if is_new:
                    new_codes_count += 1
                    logger.info(
                        f"[{self.name}] Phát hiện mã Giftcode mới ({confidence}): {code_str} "
                        f"({game.display_name}) - Nguồn: {sources}"
                    )
                # Nghỉ nhẹ giữa các bản ghi để tránh giữ khóa CSDL quá lâu
                await asyncio.sleep(0.05)

        return {
            "status": "SUCCESS",
            "message": f"Quét {total_discovered} mã từ nhiều nguồn, phát hiện {new_codes_count} mã mới.",
            "total_discovered": total_discovered,
            "new_codes": new_codes_count,
        }


class GiftcodeRedeemTask(AutomationTask):
    def __init__(self, game: GameType | None = None):
        name = f"giftcode_redeem_{game.value}" if game else "giftcode_redeem_all"
        super().__init__(name=name, game=game)

    async def execute(self) -> Dict[str, Any]:
        from app.db.repositories.accounts import AccountRepository
        from app.db.repositories.automation import RedemptionJobRepository
        from app.services.redeem_service import RedeemService

        accounts_to_redeem = await AutomationSettingsRepository.get_active_automation_accounts("redeem_enabled")
        if self.game:
            accounts_to_redeem = [item for item in accounts_to_redeem if item[0].game == self.game]

        # 1. Enqueue các jobs đổi mã mới vào hàng đợi bền vững (Persistent Queue)
        enqueued_count = 0
        for acc, auto_set, sess in accounts_to_redeem:
            if sess.session_status != "VALID":
                continue
            active_codes = await GiftCodeRepository.get_active_codes(acc.game)
            for gift in active_codes:
                if gift.game != acc.game:
                    continue
                if not await GiftCodeRepository.is_redeemed(acc.id, gift.id):
                    job = await RedemptionJobRepository.enqueue_job(gift.id, acc.id, acc.game)
                    if job:
                        enqueued_count += 1

        # 2. Phục hồi các jobs bị treo ở RUNNING do restart/redeploy
        await RedemptionJobRepository.reset_stale_running_jobs()

        # 3. Lấy danh sách jobs PENDING hoặc RETRY đến hạn
        pending_jobs = await RedemptionJobRepository.get_pending_or_retry_jobs(limit=30)
        if self.game:
            pending_jobs = [j for j in pending_jobs if j.game == self.game]

        total_processed = 0
        success_count = 0
        failed_count = 0
        auth_failed_user_ids = set()

        # 4. Xử lý từng job qua RedeemService
        for job in pending_jobs:
            total_processed += 1
            account = await AccountRepository.get_by_id(job.account_id)
            gift = await GiftCodeRepository.get_by_id(job.gift_code_id)

            if not account or not gift:
                await RedemptionJobRepository.mark_completed(
                    job.id, status="CANCELLED", error_message="Tài khoản hoặc mã không còn tồn tại"
                )
                failed_count += 1
                continue

            # Bỏ qua nếu user này vừa gặp lỗi AUTH_REQUIRED trong đợt quét hiện tại
            if account.discord_user_id in auth_failed_user_ids:
                await RedemptionJobRepository.mark_completed(
                    job.id, status="FAILED", error_code="AUTH_REQUIRED", error_message="Session tài khoản đã hết hạn"
                )
                failed_count += 1
                continue

            auto_set = await AutomationSettingsRepository.get_settings(account.discord_user_id, account.id)

            status, msg = await RedeemService.process_job(job)

            if status == "SUCCESS":
                success_count += 1
                if auto_set and auto_set.notify_mode == "ALL":
                    is_dry = settings.AUTOMATION_MODE == "dry-run"
                    title = f"{'🧪 [Mô Phỏng] ' if is_dry else '🎁 '}Tự Động Đổi Mã Thành Công — {account.game.display_name}"
                    desc = (
                        f"Đã {'mô phỏng đổi' if is_dry else 'đổi'} thành công mã: **`{gift.code}`**\n"
                        f"Tài khoản: **{account.nickname or account.uid}** (UID: `{account.uid}`)\n\n"
                        f"{'⚠️ *Chế độ Dry-Run: Đây là lần chạy mô phỏng kiểm thử. Hệ thống không gọi API HoYoverse và phần thưởng KHÔNG gửi vào hòm thư trong game.*' if is_dry else 'Vui lòng kiểm tra hòm thư trong game.'}"
                    )
                    await notification_service.notify_user(
                        discord_user_id=account.discord_user_id,
                        title=title,
                        description=desc,
                        color=settings.SUCCESS_COLOR if not is_dry else 0xF39C12,
                        channel_id=auto_set.notify_channel_id,
                    )
            elif status == "AUTH_REQUIRED":
                failed_count += 1
                auth_failed_user_ids.add(account.discord_user_id)
                if auto_set and auto_set.notify_mode in ("ALL", "FAILURE_ONLY"):
                    await notification_service.notify_user(
                        discord_user_id=account.discord_user_id,
                        title=f"⚠️ Cần Cập Nhật Cookie Đổi Mã — {account.game.display_name}",
                        description=(
                            f"Tài khoản: **{account.nickname or account.uid}** (UID: `{account.uid}`)\n"
                            f"**Lý do:** {msg}\n\n"
                            f"👉 **Khắc phục:** Hãy dùng lệnh `/auto session_add` để cập nhật lại Cookie "
                            f"(Nên bổ sung `stoken` và `ltmid_v2` để bot tự động gia hạn token vĩnh viễn không bao giờ hết hạn)."
                        ),
                        color=settings.ERROR_COLOR,
                        channel_id=auto_set.notify_channel_id,
                    )
            elif status == "ALREADY_REDEEMED":
                # Đã đổi trước đó, không tính là lỗi
                pass
            elif status in ("FAILED", "INVALID_CODE", "EXPIRED", "LEVEL_TOO_LOW", "REGION_LOCK"):
                failed_count += 1
                if auto_set and auto_set.notify_mode in ("ALL", "FAILURE_ONLY"):
                    # Chỉ thông báo khi job đã hoàn toàn thất bại sau khi hết lượt retry
                    if job.attempt_count + 1 >= 3:
                        await notification_service.notify_user(
                            discord_user_id=account.discord_user_id,
                            title=f"⚠️ Đổi Mã Thất Bại — {account.game.display_name}",
                            description=(
                                f"Không thể đổi mã: **`{gift.code}`**\n"
                                f"Tài khoản: **{account.nickname or account.uid}** (UID: `{account.uid}`)\n"
                                f"Lý do: {msg}"
                            ),
                            color=settings.ERROR_COLOR,
                            channel_id=auto_set.notify_channel_id,
                        )
            else:
                # RETRYABLE_STATUSES (NETWORK_ERROR, TIMEOUT, RATE_LIMITED)
                pass

            # Nghỉ an toàn để tuân thủ Rate Limit giữa các lần gọi HoYoLAB API (0.01s trong dry-run)
            await asyncio.sleep(2.5 if settings.AUTOMATION_MODE != "dry-run" else 0.01)

        return {
            "status": "SUCCESS",
            "message": f"Hàng đợi: đưa vào {enqueued_count} jobs, xử lý {total_processed} jobs, thành công {success_count}, thất bại/lỗi {failed_count}.",
            "enqueued": enqueued_count,
            "processed": total_processed,
            "success": success_count,
            "failed": failed_count,
        }

