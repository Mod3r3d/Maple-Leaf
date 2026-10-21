"""Bộ kiểm thử đơn vị cho toàn bộ hệ thống Automation v2."""

import unittest
from datetime import datetime
from unittest.mock import AsyncMock, patch

from app.automation.client import HoyoClientAdapter
from app.automation.manager import automation_manager
from app.automation.tasks.checkin_task import DailyCheckinTask
from app.automation.tasks.giftcode_tasks import GiftcodeDiscoveryTask, GiftcodeRedeemTask
from app.automation.tasks.token_refresh_task import TokenRefreshTask
from app.automation.tasks.web_event_task import WebEventMonitorTask
from app.config import settings
from app.db.repositories.accounts import AccountRepository
from app.db.repositories.automation import (
    AutomationLogRepository,
    AutomationSettingsRepository,
    CheckinRepository,
    GiftCodeRepository,
    SessionRepository,
    WebEventRepository,
)
from app.games.enums import GameType, ServerRegion
from app.security.encryption import cipher, mask_cookie
from tests.db_test_utils import TempDatabaseMixin


class TestSecurityAndEncryption(unittest.TestCase):
    def test_encrypt_and_decrypt(self):
        secret_cookie = "ltuid_v2=123456789; ltoken_v2=v2_abcdef1234567890; ltmid_v2=1a2b3c;"
        encrypted = cipher.encrypt(secret_cookie)
        self.assertNotEqual(secret_cookie, encrypted)

        decrypted = cipher.decrypt(encrypted)
        self.assertEqual(secret_cookie, decrypted)

    def test_mask_cookie(self):
        cookie = "ltoken_v2=v2_secret1234567890"
        masked = mask_cookie(cookie)
        self.assertTrue(masked.startswith("ltok"))
        self.assertTrue(masked.endswith("7890"))
        self.assertIn("...", masked)
        self.assertNotIn("secret123", masked)

    def test_normalize_giftcode(self):
        from app.services.redeem_service import normalize_giftcode

        # 1. Mã thuần
        self.assertEqual(normalize_giftcode("GENSHINGIFT"), "GENSHINGIFT")
        self.assertEqual(normalize_giftcode("  hsr2026  "), "HSR2026")
        self.assertEqual(normalize_giftcode("CODE_WITH-HYPHEN123"), "CODE_WITH-HYPHEN123")

        # 2. URL trang đổi mã HoYoverse
        self.assertEqual(
            normalize_giftcode("https://genshin.hoyoverse.com/en/gift?code=GENSHINGIFT"),
            "GENSHINGIFT",
        )
        self.assertEqual(
            normalize_giftcode("https://hsr.hoyoverse.com/gift?cdkey=STARRAILGIFT&foo=bar"),
            "STARRAILGIFT",
        )
        self.assertEqual(
            normalize_giftcode("https://act.hoyolab.com/puzzle/index.html?gift_code=SPECIAL2026"),
            "SPECIAL2026",
        )

        # 3. Chuỗi không hợp lệ
        self.assertIsNone(normalize_giftcode(""))
        self.assertIsNone(normalize_giftcode("   "))
        self.assertIsNone(normalize_giftcode("ABC"))  # Quá ngắn (< 4)
        self.assertIsNone(normalize_giftcode("CODE WITH SPACES"))
        self.assertIsNone(normalize_giftcode("https://genshin.hoyoverse.com/en/gift"))  # Thiếu param code

    def test_inspect_cookie_tokens_matrix(self):
        from app.security.encryption import inspect_cookie_tokens

        # Trường hợp 1: Chỉ có token điểm danh
        c_checkin = "ltuid_v2=12345; ltoken_v2=v2_tok123;"
        info1 = inspect_cookie_tokens(c_checkin)
        self.assertTrue(info1["has_checkin"])
        self.assertFalse(info1["has_cookie_token"])
        self.assertFalse(info1["can_auto_refresh"])
        self.assertFalse(info1["redeem_durable"])
        self.assertFalse(info1["has_redeem"])
        self.assertIn("cookie_token_v2", info1["missing_for_redeem"])

        # Trường hợp 2: Có cookie_token nhưng thiếu stoken (đổi mã tạm thời)
        c_temp = "ltuid_v2=12345; ltoken_v2=v2_tok123; cookie_token_v2=v2_cookie;"
        info2 = inspect_cookie_tokens(c_temp)
        self.assertTrue(info2["has_checkin"])
        self.assertTrue(info2["has_cookie_token"])
        self.assertTrue(info2["can_redeem_direct"])
        self.assertFalse(info2["can_auto_refresh"])
        self.assertFalse(info2["redeem_durable"])
        self.assertTrue(info2["has_redeem"])

        # Trường hợp 3: Có stoken nhưng thiếu ltmid_v2 (không tự gia hạn được)
        c_no_mid = "ltuid_v2=12345; ltoken_v2=v2_tok123; stoken_v2=v2_stok;"
        info3 = inspect_cookie_tokens(c_no_mid)
        self.assertTrue(info3["has_stoken"])
        self.assertFalse(info3["has_mid"])
        self.assertFalse(info3["can_auto_refresh"])
        self.assertFalse(info3["redeem_durable"])
        self.assertIn("ltmid_v2", info3["missing_for_redeem"])

        # Trường hợp 4: Đầy đủ stoken và ltmid_v2 (đổi mã bền vững)
        c_durable = "ltuid_v2=12345; ltoken_v2=v2_tok123; stoken_v2=v2_stok; ltmid_v2=mid123;"
        info4 = inspect_cookie_tokens(c_durable)
        self.assertTrue(info4["has_checkin"])
        self.assertTrue(info4["has_stoken"])
        self.assertTrue(info4["has_mid"])
        self.assertTrue(info4["can_auto_refresh"])
        self.assertTrue(info4["redeem_durable"])
        self.assertTrue(info4["has_redeem"])
        self.assertEqual(len(info4["missing_for_redeem"]), 0)


class TestAutomationDatabase(TempDatabaseMixin, unittest.IsolatedAsyncioTestCase):
    TEST_USER_ID = 888777666

    async def asyncSetUp(self):
        await self._open_temp_db()

    async def asyncTearDown(self):
        await self._close_temp_db()

    async def test_session_lifecycle(self):
        # 1. Lưu session
        raw_cookie = "ltuid=123; ltoken=abc;"
        sess = await SessionRepository.save_session(
            discord_user_id=self.TEST_USER_ID,
            game=GameType.GENSHIN,
            uid=819999999,
            raw_cookie=raw_cookie,
        )
        self.assertIsNotNone(sess)
        self.assertEqual(sess.session_status, "VALID")

        # 2. Đọc lại và giải mã
        loaded = await SessionRepository.get_session(self.TEST_USER_ID, GameType.GENSHIN, 819999999)
        self.assertIsNotNone(loaded)
        cookie_dec = await SessionRepository.get_decrypted_cookie(loaded)
        self.assertEqual(cookie_dec, raw_cookie)

        # 3. Cập nhật status
        await SessionRepository.update_status(sess.id, "EXPIRED")
        loaded_expired = await SessionRepository.get_session(self.TEST_USER_ID, GameType.GENSHIN, 819999999)
        self.assertEqual(loaded_expired.session_status, "EXPIRED")

        # 4. Xóa session
        deleted = await SessionRepository.delete_session(self.TEST_USER_ID, GameType.GENSHIN, 819999999)
        self.assertTrue(deleted)
        self.assertIsNone(await SessionRepository.get_session(self.TEST_USER_ID, GameType.GENSHIN, 819999999))

    async def test_automation_settings_and_accounts(self):
        acc = await AccountRepository.add_account(
            discord_user_id=self.TEST_USER_ID,
            game=GameType.HSR,
            uid=801111222,
            server=ServerRegion.ASIA,
            nickname="TestHSR",
        )
        # Thêm session hợp lệ
        await SessionRepository.save_session(self.TEST_USER_ID, GameType.HSR, 801111222, "dummy_cookie")

        # Tạo và cập nhật settings
        settings_model = await AutomationSettingsRepository.get_or_create(acc.id, self.TEST_USER_ID)
        self.assertTrue(settings_model.checkin_enabled)

        # Lấy danh sách tài khoản hợp lệ
        active = await AutomationSettingsRepository.get_active_automation_accounts("checkin_enabled")
        self.assertTrue(any(item[0].id == acc.id for item in active))

        # Tắt checkin
        await AutomationSettingsRepository.update_feature(acc.id, "checkin", False)
        active_after = await AutomationSettingsRepository.get_active_automation_accounts("checkin_enabled")
        self.assertFalse(any(item[0].id == acc.id for item in active_after))

    async def test_giftcode_repository(self):
        code = "TESTCODE2026"
        model1, is_new1 = await GiftCodeRepository.add_code(code, GameType.GENSHIN, "test")
        self.assertTrue(is_new1)
        self.assertEqual(model1.code, code)

        # Thêm lần 2 -> không trùng (is_new = False)
        model2, is_new2 = await GiftCodeRepository.add_code(code, GameType.GENSHIN, "test")
        self.assertFalse(is_new2)
        self.assertEqual(model2.id, model1.id)

        # Kiểm tra trạng thái đã redeem chưa
        redeemed = await GiftCodeRepository.is_redeemed(99999, model1.id)
        self.assertFalse(redeemed)

        await GiftCodeRepository.record_redemption(99999, model1.id, GameType.GENSHIN, code, "SUCCESS", "OK")
        self.assertTrue(await GiftCodeRepository.is_redeemed(99999, model1.id))

    async def test_web_event_repository(self):
        ev_id = "test_event_1"
        ev, is_new = await WebEventRepository.upsert_event(
            external_id=ev_id,
            game=GameType.GENSHIN,
            title="Sự Kiện Web Test",
            url="https://example.com/event",
        )
        self.assertTrue(is_new)
        self.assertEqual(ev.title, "Sự Kiện Web Test")

        # Lần 2 -> cập nhật, không trùng
        ev2, is_new2 = await WebEventRepository.upsert_event(
            external_id=ev_id,
            game=GameType.GENSHIN,
            title="Sự Kiện Web Test",
            url="https://example.com/event",
        )
        self.assertFalse(is_new2)


class TestAutomationTasksAndScheduler(TempDatabaseMixin, unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await self._open_temp_db()
        settings.AUTOMATION_MODE = "dry-run"

    async def asyncTearDown(self):
        settings.AUTOMATION_MODE = "live"
        await self._close_temp_db()

    async def test_checkin_task_dry_run(self):
        task = DailyCheckinTask(GameType.GENSHIN)
        result = await task.run()
        self.assertIn(result.get("status"), ("SUCCESS", "PARTIAL_SUCCESS"))

    async def test_giftcode_tasks_dry_run(self):
        discovery = GiftcodeDiscoveryTask()
        disc_res = await discovery.run()
        self.assertEqual(disc_res.get("status"), "SUCCESS")

        redeem = GiftcodeRedeemTask(GameType.GENSHIN)
        redeem_res = await redeem.run()
        self.assertEqual(redeem_res.get("status"), "SUCCESS")

    async def test_web_event_task(self):
        event_task = WebEventMonitorTask()
        res = await event_task.run()
        self.assertEqual(res.get("status"), "SUCCESS")

    async def test_scheduler_lifecycle(self):
        automation_manager.start()
        self.assertTrue(automation_manager._running)
        self.assertIsNotNone(automation_manager.scheduler)

        # Kiểm tra các jobs đã được đăng ký
        job_ids = [j.id for j in automation_manager.scheduler.get_jobs()]
        self.assertIn("job_daily_checkin", job_ids)
        self.assertIn("job_giftcode_pipeline", job_ids)
        self.assertIn("job_mimo_accompany", job_ids)
        self.assertIn("job_web_events", job_ids)

        automation_manager.stop()
        self.assertFalse(automation_manager._running)


class TestHoyoClientAdapter(unittest.TestCase):
    def test_parse_cookie_to_dict(self):
        from app.automation.client import parse_cookie_to_dict
        raw = "ltuid_v2=123456; ltoken_v2=token123; cookie_token_v2=ctoken456; ltmid_v2=mid789;"
        parsed = parse_cookie_to_dict(raw)
        self.assertEqual(parsed["ltuid_v2"], "123456")
        self.assertEqual(parsed["account_id"], "123456")
        self.assertEqual(parsed["cookie_token"], "ctoken456")
        self.assertEqual(parsed["mid"], "mid789")

    def test_to_genshin_game(self):
        import genshin
        from app.automation.client import to_genshin_game
        self.assertEqual(to_genshin_game(GameType.GENSHIN), genshin.Game.GENSHIN)
        self.assertEqual(to_genshin_game(GameType.HSR), genshin.Game.STARRAIL)


class TestPersistentQueueAndRedeemService(TempDatabaseMixin, unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await self._open_temp_db()

    async def asyncTearDown(self):
        await self._close_temp_db()

    async def test_queue_lifecycle(self):
        from app.db.repositories.automation import RedemptionJobRepository
        # Enqueue job
        job = await RedemptionJobRepository.enqueue_job(gift_code_id=9999, account_id=8888, game=GameType.GENSHIN)
        if job:
            self.assertEqual(job.status, "PENDING")
            await RedemptionJobRepository.mark_running(job.id)
            await RedemptionJobRepository.reset_stale_running_jobs()
            jobs = await RedemptionJobRepository.get_pending_or_retry_jobs(limit=10)
            self.assertTrue(any(j.id == job.id for j in jobs))
            await RedemptionJobRepository.mark_completed(job.id, status="SUCCESS")

    async def test_giftcode_search_and_sources(self):
        from app.db.repositories.automation import GiftCodeRepository
        # Add test code
        code_model, _ = await GiftCodeRepository.add_or_update_code(
            code="TESTSEARCH123",
            game=GameType.GENSHIN,
            source="official",
            sources="official, community",
            rewards="Primogems x60",
            confidence="HIGH",
        )
        search_res = await GiftCodeRepository.search_code("TESTSEARCH123")
        self.assertTrue(len(search_res) > 0)
        self.assertEqual(search_res[0].code, "TESTSEARCH123")

        sources_summary = await GiftCodeRepository.get_sources_summary()
        self.assertIsInstance(sources_summary, list)

    async def test_redeem_overview(self):
        from app.services.redeem_service import RedeemService
        overview = await RedeemService.get_redeem_status_overview()
        self.assertIn("genshin_opted_in", overview)
        self.assertIn("hsr_opted_in", overview)
        self.assertIn("pending_queue_count", overview)

    async def test_redeem_for_account_invalid_and_dryrun(self):
        from app.db.models.account import AccountModel
        from app.games.enums import GameType, ServerRegion
        from app.services.redeem_service import RedeemService

        fake_acc = AccountModel(
            id=99999,
            discord_user_id=123456789,
            game=GameType.GENSHIN,
            uid=800000001,
            server=ServerRegion.ASIA,
            nickname="TestTraveler",
            is_default=True,
        )

        # 1. Mã không hợp lệ -> INVALID_CODE
        status, msg = await RedeemService.redeem_for_account(fake_acc, "BAD CODE!")
        self.assertEqual(status, "INVALID_CODE")
        self.assertIn("không hợp lệ", msg)

        # 2. Không có session trong DB -> AUTH_REQUIRED
        status, msg = await RedeemService.redeem_for_account(fake_acc, "GENSHINGIFT")
        self.assertEqual(status, "AUTH_REQUIRED")
        self.assertIn("Chưa liên kết Cookie", msg)


class TestTokenRefreshTask(TempDatabaseMixin, unittest.IsolatedAsyncioTestCase):
    """Kiểm tra tác vụ giữ token sống — cơ chế "đăng nhập một lần"."""

    async def asyncSetUp(self):
        await self._open_temp_db()

    async def asyncTearDown(self):
        await self._close_temp_db()

    async def test_no_sessions_is_success(self):
        result = await TokenRefreshTask().execute()
        self.assertEqual(result["status"], "SUCCESS")
        self.assertIn("Chưa có phiên", result["message"])

    async def test_session_without_stoken_is_skipped(self):
        await SessionRepository.save_session(
            discord_user_id=111222333,
            game=GameType.GENSHIN,
            uid=800000001,
            raw_cookie="ltuid_v2=111222333; ltoken_v2=v2_abc; cookie_token_v2=v2_xyz;",
        )

        result = await TokenRefreshTask().execute()
        self.assertEqual(result["refreshed"], 0)
        self.assertEqual(result["missing_stoken"], 1)
        self.assertIn("stoken", result["message"])

    async def test_session_with_stoken_is_refreshed(self):
        await SessionRepository.save_session(
            discord_user_id=444555666,
            game=GameType.HSR,
            uid=800000002,
            raw_cookie="ltuid_v2=444555666; ltmid_v2=mid123; stoken=v2_stoken; cookie_token_v2=v2_old;",
        )

        with patch.object(HoyoClientAdapter, "try_refresh_tokens", new=AsyncMock(return_value=True)):
            result = await TokenRefreshTask().execute()

        self.assertEqual(result["refreshed"], 1)
        self.assertEqual(result["failed"], 0)
        self.assertEqual(result["status"], "SUCCESS")


if __name__ == "__main__":
    unittest.main()


