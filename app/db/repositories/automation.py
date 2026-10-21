"""Repositories quản lý dữ liệu cho hệ thống Automation v2 với AsyncRLock điều phối."""

from datetime import datetime
from typing import List, Optional, Tuple

from loguru import logger

from app.db.database import db
from app.db.models.account import AccountModel
from app.db.models.automation import (
    AutomationLogModel,
    AutomationSettingsModel,
    CheckinExecutionModel,
    GiftCodeModel,
    GiftcodeRedemptionModel,
    RedemptionJobModel,
    SessionModel,
    WebEventModel,
)
from app.games.enums import GameType, ServerRegion
from app.security.encryption import cipher


class SessionRepository:
    @staticmethod
    async def save_session(
        discord_user_id: int,
        game: GameType,
        uid: int,
        raw_cookie: str,
        reopen_failed_jobs: bool = True,
    ) -> SessionModel:
        """Lưu hoặc cập nhật session cookie đã mã hóa, tự động gộp cookie mới với cookie cũ nếu có.

        `reopen_failed_jobs=False` dùng cho việc gia hạn token định kỳ: chỉ cập nhật
        cookie, không mở lại các job đã thất bại (tránh vòng lặp thử lại vô ích).
        """
        async with db.get_connection() as conn:
            final_cookie = raw_cookie.strip()
            # Nếu đã có session trước đó, gộp cookie để không làm mất token điểm danh (ltoken) hoặc token đổi mã (cookie_token)
            existing_sess = await SessionRepository.get_session(discord_user_id, game, uid)
            if existing_sess:
                try:
                    old_cookie = await SessionRepository.get_decrypted_cookie(existing_sess)
                    merged = {}
                    for p in old_cookie.split(";"):
                        if "=" in p:
                            k, v = p.split("=", 1)
                            merged[k.strip()] = v.strip()
                    for p in final_cookie.split(";"):
                        if "=" in p:
                            k, v = p.split("=", 1)
                            merged[k.strip()] = v.strip()
                    final_cookie = "; ".join(f"{k}={v}" for k, v in merged.items())
                except Exception as e:
                    logger.warning(f"Lỗi khi gộp cookie: {e}")

            encrypted = cipher.encrypt(final_cookie)

            cursor = await conn.execute(
                """
                INSERT INTO sessions (discord_user_id, game, uid, cookie_encrypted, session_status, last_auth_check)
                VALUES (?, ?, ?, ?, 'VALID', CURRENT_TIMESTAMP)
                ON CONFLICT(discord_user_id, game, uid) DO UPDATE SET
                    cookie_encrypted = excluded.cookie_encrypted,
                    session_status = 'VALID',
                    last_auth_check = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                RETURNING id, discord_user_id, game, uid, cookie_encrypted, session_status, last_auth_check, created_at, updated_at
                """,
                (discord_user_id, game.value, uid, encrypted),
            )
            row = await cursor.fetchone()

            # Tự động mở lại các redemption_jobs bị FAILED do AUTH_REQUIRED khi cập nhật session
            if reopen_failed_jobs:
                await conn.execute(
                    """
                    UPDATE redemption_jobs
                    SET status = 'PENDING', attempt_count = 0, error_code = NULL, error_message = NULL, completed_at = NULL, next_retry_at = NULL
                    WHERE account_id IN (SELECT id FROM accounts WHERE discord_user_id = ? AND game = ? AND uid = ?)
                      AND status = 'FAILED' AND error_code = 'AUTH_REQUIRED'
                    """,
                    (discord_user_id, game.value, uid),
                )
                # Xóa các bản ghi đổi lỗi AUTH_REQUIRED để cho phép quét và đổi lại
                await conn.execute(
                    """
                    DELETE FROM giftcode_redemptions
                    WHERE account_id IN (SELECT id FROM accounts WHERE discord_user_id = ? AND game = ? AND uid = ?)
                      AND status = 'AUTH_REQUIRED'
                    """,
                    (discord_user_id, game.value, uid),
                )

            await conn.commit()
            return SessionModel(
                id=row["id"],
                discord_user_id=row["discord_user_id"],
                game=GameType(row["game"]),
                uid=row["uid"],
                cookie_encrypted=row["cookie_encrypted"],
                session_status=row["session_status"],
                last_auth_check=row["last_auth_check"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )

    @staticmethod
    async def get_session(discord_user_id: int, game: GameType, uid: int) -> Optional[SessionModel]:
        """Lấy session của tài khoản."""
        async with db.get_connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM sessions WHERE discord_user_id = ? AND game = ? AND uid = ?",
                (discord_user_id, game.value, uid),
            )
            row = await cursor.fetchone()
            if not row:
                return None
            return SessionModel(
                id=row["id"],
                discord_user_id=row["discord_user_id"],
                game=GameType(row["game"]),
                uid=row["uid"],
                cookie_encrypted=row["cookie_encrypted"],
                session_status=row["session_status"],
                last_auth_check=row["last_auth_check"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )

    @staticmethod
    async def get_all_sessions() -> List[SessionModel]:
        """Lấy toàn bộ session đã lưu (dùng cho tác vụ tự gia hạn token).

        Không lọc theo cờ automation: dù người dùng tắt một tính năng nào đó thì
        cookie vẫn cần được giữ sống để lần bật lại không phải đăng nhập lại.
        """
        async with db.get_connection() as conn:
            cursor = await conn.execute(
                "SELECT id, discord_user_id, game, uid, cookie_encrypted, session_status, "
                "last_auth_check, created_at, updated_at FROM sessions ORDER BY id"
            )
            rows = await cursor.fetchall()

        return [
            SessionModel(
                id=row["id"],
                discord_user_id=row["discord_user_id"],
                game=GameType(row["game"]),
                uid=row["uid"],
                cookie_encrypted=row["cookie_encrypted"],
                session_status=row["session_status"],
                last_auth_check=row["last_auth_check"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in rows
        ]

    @staticmethod
    async def get_decrypted_cookie(session: SessionModel) -> str:
        """Giải mã cookie để gửi request."""
        return cipher.decrypt(session.cookie_encrypted)

    @staticmethod
    async def update_status(session_id: int, status: str):
        """Cập nhật trạng thái session (VALID, EXPIRED, INVALID)."""
        async with db.get_connection() as conn:
            await conn.execute(
                "UPDATE sessions SET session_status = ?, last_auth_check = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (status, session_id),
            )
            await conn.commit()

    @staticmethod
    async def delete_session(discord_user_id: int, game: GameType, uid: int) -> bool:
        """Xóa session khi người dùng hủy liên kết."""
        async with db.get_connection() as conn:
            cursor = await conn.execute(
                "DELETE FROM sessions WHERE discord_user_id = ? AND game = ? AND uid = ?",
                (discord_user_id, game.value, uid),
            )
            await conn.commit()
            return cursor.rowcount > 0


class AutomationSettingsRepository:
    @staticmethod
    async def get_settings(discord_user_id: int, account_id: int) -> AutomationSettingsModel:
        """Lấy hoặc tạo cài đặt tự động hóa (alias thuận tiện)."""
        return await AutomationSettingsRepository.get_or_create(account_id, discord_user_id)

    @staticmethod
    async def get_or_create(account_id: int, discord_user_id: int) -> AutomationSettingsModel:
        """Lấy hoặc tạo cài đặt tự động hóa cho một tài khoản game."""
        async with db.get_connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM automation_settings WHERE account_id = ?",
                (account_id,),
            )
            row = await cursor.fetchone()
            if row:
                return AutomationSettingsModel(
                    id=row["id"],
                    account_id=row["account_id"],
                    discord_user_id=row["discord_user_id"],
                    automation_enabled=bool(row["automation_enabled"]),
                    checkin_enabled=bool(row["checkin_enabled"]),
                    redeem_enabled=bool(row["redeem_enabled"]),
                    mimo_enabled=bool(row["mimo_enabled"]),
                    accompany_enabled=bool(row["accompany_enabled"]),
                    event_notify_enabled=bool(row["event_notify_enabled"]),
                    notify_mode=row["notify_mode"],
                    notify_channel_id=row["notify_channel_id"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )

            cursor = await conn.execute(
                """
                INSERT INTO automation_settings (
                    account_id, discord_user_id, automation_enabled, checkin_enabled,
                    redeem_enabled, mimo_enabled, accompany_enabled, event_notify_enabled, notify_mode
                )
                VALUES (?, ?, 1, 1, 1, 1, 0, 1, 'FAILURE_ONLY')
                RETURNING *
                """,
                (account_id, discord_user_id),
            )
            row = await cursor.fetchone()
            await conn.commit()
            return AutomationSettingsModel(
                id=row["id"],
                account_id=row["account_id"],
                discord_user_id=row["discord_user_id"],
                automation_enabled=bool(row["automation_enabled"]),
                checkin_enabled=bool(row["checkin_enabled"]),
                redeem_enabled=bool(row["redeem_enabled"]),
                mimo_enabled=bool(row["mimo_enabled"]),
                accompany_enabled=bool(row["accompany_enabled"]),
                event_notify_enabled=bool(row["event_notify_enabled"]),
                notify_mode=row["notify_mode"],
                notify_channel_id=row["notify_channel_id"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )

    @staticmethod
    async def update_feature(
        account_id: int,
        feature: str,
        enabled: bool,
    ):
        """Bật/tắt nhanh một tính năng tự động (checkin, redeem, mimo, accompany, event_notify, automation)."""
        valid_cols = {
            "automation": "automation_enabled",
            "checkin": "checkin_enabled",
            "redeem": "redeem_enabled",
            "mimo": "mimo_enabled",
            "accompany": "accompany_enabled",
            "events": "event_notify_enabled",
        }
        col = valid_cols.get(feature)
        if not col:
            return

        async with db.get_connection() as conn:
            await conn.execute(
                f"UPDATE automation_settings SET {col} = ?, updated_at = CURRENT_TIMESTAMP WHERE account_id = ?",
                (1 if enabled else 0, account_id),
            )
            await conn.commit()

    @staticmethod
    async def update_notify_mode(discord_user_id: int, notify_mode: str):
        """Cập nhật chế độ nhận thông báo cho toàn bộ cấu hình automation của user."""
        async with db.get_connection() as conn:
            await conn.execute(
                "UPDATE automation_settings SET notify_mode = ?, updated_at = CURRENT_TIMESTAMP WHERE discord_user_id = ?",
                (notify_mode, discord_user_id),
            )
            await conn.commit()

    @staticmethod
    async def update_notify_channel(discord_user_id: int, channel_id: Optional[int]):
        """Cập nhật kênh nhận thông báo Discord cho toàn bộ cấu hình automation của user."""
        async with db.get_connection() as conn:
            await conn.execute(
                "UPDATE automation_settings SET notify_channel_id = ?, updated_at = CURRENT_TIMESTAMP WHERE discord_user_id = ?",
                (channel_id, discord_user_id),
            )
            await conn.commit()

    @staticmethod
    async def get_active_automation_accounts(feature_col: str = "checkin_enabled") -> List[Tuple[AccountModel, AutomationSettingsModel, SessionModel]]:
        """Lấy danh sách các tài khoản có session hợp lệ và đã opt-in tính năng tương ứng."""
        query = f"""
        SELECT
            a.id AS a_id, a.discord_user_id AS a_user, a.game AS a_game, a.uid AS a_uid, a.server AS a_server, a.nickname AS a_nick, a.is_default AS a_def,
            s.id AS s_id, s.automation_enabled AS s_auto, s.checkin_enabled AS s_checkin, s.redeem_enabled AS s_redeem, s.mimo_enabled AS s_mimo, s.accompany_enabled AS s_accompany, s.event_notify_enabled AS s_event, s.notify_mode AS s_mode, s.notify_channel_id AS s_chan,
            sess.id AS sess_id, sess.cookie_encrypted AS sess_cookie, sess.session_status AS sess_status
        FROM accounts a
        JOIN automation_settings s ON a.id = s.account_id
        JOIN sessions sess ON a.discord_user_id = sess.discord_user_id AND a.game = sess.game AND a.uid = sess.uid
        WHERE s.automation_enabled = 1 AND s.{feature_col} = 1 AND sess.session_status = 'VALID'
        """
        async with db.get_connection() as conn:
            cursor = await conn.execute(query)
            rows = await cursor.fetchall()

            results = []
            for r in rows:
                acc = AccountModel(
                    id=r["a_id"],
                    discord_user_id=r["a_user"],
                    game=GameType(r["a_game"]),
                    uid=r["a_uid"],
                    server=ServerRegion(r["a_server"]),
                    nickname=r["a_nick"],
                    is_default=bool(r["a_def"]),
                )
                auto_set = AutomationSettingsModel(
                    id=r["s_id"],
                    account_id=r["a_id"],
                    discord_user_id=r["a_user"],
                    automation_enabled=bool(r["s_auto"]),
                    checkin_enabled=bool(r["s_checkin"]),
                    redeem_enabled=bool(r["s_redeem"]),
                    mimo_enabled=bool(r["s_mimo"]),
                    accompany_enabled=bool(r["s_accompany"]),
                    event_notify_enabled=bool(r["s_event"]),
                    notify_mode=r["s_mode"],
                    notify_channel_id=r["s_chan"],
                )
                sess = SessionModel(
                    id=r["sess_id"],
                    discord_user_id=r["a_user"],
                    game=GameType(r["a_game"]),
                    uid=r["a_uid"],
                    cookie_encrypted=r["sess_cookie"],
                    session_status=r["sess_status"],
                )
                results.append((acc, auto_set, sess))

            return results


class CheckinRepository:
    @staticmethod
    async def has_checked_in_today(account_id: int, run_date: str) -> bool:
        async with db.get_connection() as conn:
            cursor = await conn.execute(
                "SELECT COUNT(*) FROM checkin_executions WHERE account_id = ? AND run_date = ? AND status IN ('SUCCESS', 'ALREADY_CHECKED')",
                (account_id, run_date),
            )
            return (await cursor.fetchone())[0] > 0

    @staticmethod
    async def record_execution(
        account_id: int,
        game: GameType,
        run_date: str,
        status: str,
        reward_summary: Optional[str] = None,
        error_code: Optional[str] = None,
    ) -> CheckinExecutionModel:
        async with db.get_connection() as conn:
            cursor = await conn.execute(
                """
                INSERT INTO checkin_executions (account_id, game, run_date, status, reward_summary, error_code)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(account_id, run_date) DO UPDATE SET
                    status = excluded.status,
                    reward_summary = COALESCE(excluded.reward_summary, checkin_executions.reward_summary),
                    error_code = excluded.error_code,
                    executed_at = CURRENT_TIMESTAMP
                RETURNING *
                """,
                (account_id, game.value, run_date, status, reward_summary, error_code),
            )
            row = await cursor.fetchone()
            await conn.commit()
            return CheckinExecutionModel(
                id=row["id"],
                account_id=row["account_id"],
                game=GameType(row["game"]),
                run_date=row["run_date"],
                status=row["status"],
                reward_summary=row["reward_summary"],
                error_code=row["error_code"],
                executed_at=row["executed_at"],
            )

    @staticmethod
    async def get_history(account_id: int, limit: int = 7) -> List[CheckinExecutionModel]:
        async with db.get_connection() as conn:
            cursor = await conn.execute(
                """
                SELECT * FROM checkin_executions
                WHERE account_id = ?
                ORDER BY run_date DESC, id DESC
                LIMIT ?
                """,
                (account_id, limit),
            )
            rows = await cursor.fetchall()
            return [
                CheckinExecutionModel(
                    id=r["id"],
                    account_id=r["account_id"],
                    game=GameType(r["game"]),
                    run_date=r["run_date"],
                    status=r["status"],
                    reward_summary=r["reward_summary"],
                    error_code=r["error_code"],
                    executed_at=r["executed_at"],
                )
                for r in rows
            ]


class GiftCodeRepository:
    @staticmethod
    async def add_or_update_code(
        code: str,
        game: GameType,
        source: str = "auto_discovery",
        sources: Optional[str] = None,
        rewards: Optional[str] = None,
        confidence: str = "MEDIUM",
        expires_at: Optional[datetime] = None,
    ) -> Tuple[GiftCodeModel, bool]:
        clean_code = code.strip().upper()
        async with db.get_connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM gift_codes WHERE game = ? AND code = ?",
                (game.value, clean_code),
            )
            row = await cursor.fetchone()
            if row:
                # Code đã tồn tại, hợp nhất nguồn và cập nhật
                raw_sources = row["sources"] if "sources" in row.keys() and row["sources"] else row["source"]
                existing_sources = set((raw_sources or "").split(", "))
                new_sources = set((sources or source).split(", "))
                merged_sources = ", ".join(sorted([s for s in (existing_sources | new_sources) if s]))
                final_conf = "HIGH" if "official" in merged_sources or len(merged_sources.split(", ")) >= 2 else confidence
                final_rewards = rewards or (row["rewards"] if "rewards" in row.keys() else None)

                await conn.execute(
                    """
                    UPDATE gift_codes
                    SET sources = ?,
                        rewards = COALESCE(?, rewards),
                        confidence = ?,
                        last_checked_at = CURRENT_TIMESTAMP,
                        status = 'ACTIVE'
                    WHERE id = ?
                    """,
                    (merged_sources, final_rewards, final_conf, row["id"]),
                )
                await conn.commit()

                return GiftCodeModel(
                    id=row["id"],
                    code=row["code"],
                    game=GameType(row["game"]),
                    source=row["source"],
                    sources=merged_sources,
                    rewards=final_rewards,
                    confidence=final_conf,
                    status="ACTIVE",
                ), False

            # Thêm mới
            final_sources = sources or source
            cursor = await conn.execute(
                """
                INSERT INTO gift_codes (code, game, source, sources, rewards, confidence, expires_at, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'ACTIVE')
                RETURNING *
                """,
                (clean_code, game.value, source, final_sources, rewards, confidence, expires_at),
            )
            row = await cursor.fetchone()
            await conn.commit()
            return GiftCodeModel(
                id=row["id"],
                code=row["code"],
                game=GameType(row["game"]),
                source=row["source"],
                sources=row["sources"] if "sources" in row.keys() else final_sources,
                rewards=row["rewards"] if "rewards" in row.keys() else rewards,
                confidence=row["confidence"] if "confidence" in row.keys() else confidence,
                status=row["status"],
            ), True

    @staticmethod
    async def add_code(code: str, game: GameType, source: str = "auto_discovery") -> Tuple[GiftCodeModel, bool]:
        return await GiftCodeRepository.add_or_update_code(code=code, game=game, source=source)

    @staticmethod
    async def get_active_codes(game: GameType) -> List[GiftCodeModel]:
        async with db.get_connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM gift_codes WHERE game = ? AND status = 'ACTIVE' ORDER BY id DESC",
                (game.value,),
            )
            rows = await cursor.fetchall()
            return [
                GiftCodeModel(
                    id=r["id"],
                    code=r["code"],
                    game=GameType(r["game"]),
                    source=r["source"],
                    sources=r["sources"] if "sources" in r.keys() and r["sources"] else r["source"],
                    rewards=r["rewards"] if "rewards" in r.keys() else None,
                    confidence=r["confidence"] if "confidence" in r.keys() else "MEDIUM",
                    status=r["status"],
                )
                for r in rows
            ]

    @staticmethod
    async def is_redeemed(account_id: int, gift_code_id: int) -> bool:
        async with db.get_connection() as conn:
            cursor = await conn.execute(
                "SELECT COUNT(*) FROM giftcode_redemptions WHERE account_id = ? AND gift_code_id = ? AND status IN ('SUCCESS', 'ALREADY_REDEEMED', 'EXPIRED', 'INVALID_CODE')",
                (account_id, gift_code_id),
            )
            return (await cursor.fetchone())[0] > 0

    @staticmethod
    async def record_redemption(
        account_id: int,
        gift_code_id: int,
        game: GameType,
        code: str,
        status: str,
        response_msg: Optional[str] = None,
    ):
        async with db.get_connection() as conn:
            await conn.execute(
                """
                INSERT INTO giftcode_redemptions (account_id, gift_code_id, game, code, status, response_msg)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(account_id, gift_code_id) DO UPDATE SET
                    status = excluded.status,
                    response_msg = excluded.response_msg,
                    redeemed_at = CURRENT_TIMESTAMP
                """,
                (account_id, gift_code_id, game.value, code, status, response_msg),
            )
            await conn.commit()

    @staticmethod
    async def get_redemption_history(account_id: int, limit: int = 10) -> List[GiftcodeRedemptionModel]:
        async with db.get_connection() as conn:
            cursor = await conn.execute(
                """
                SELECT * FROM giftcode_redemptions
                WHERE account_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (account_id, limit),
            )
            rows = await cursor.fetchall()
            return [
                GiftcodeRedemptionModel(
                    id=r["id"],
                    account_id=r["account_id"],
                    gift_code_id=r["gift_code_id"],
                    game=GameType(r["game"]),
                    code=r["code"],
                    status=r["status"],
                    response_msg=r["response_msg"],
                    redeemed_at=r["redeemed_at"],
                )
                for r in rows
            ]

    @staticmethod
    async def get_by_id(gift_code_id: int) -> Optional[GiftCodeModel]:
        """Lấy thông tin GiftCode theo ID."""
        async with db.get_connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM gift_codes WHERE id = ?",
                (gift_code_id,),
            )
            r = await cursor.fetchone()
            if not r:
                return None
            return GiftCodeModel(
                id=r["id"],
                code=r["code"],
                game=GameType(r["game"]),
                source=r["source"],
                sources=r["sources"] if "sources" in r.keys() and r["sources"] else r["source"],
                rewards=r["rewards"] if "rewards" in r.keys() else None,
                confidence=r["confidence"] if "confidence" in r.keys() else "MEDIUM",
                status=r["status"],
            )

    @staticmethod
    async def search_code(query: str, game: Optional[GameType] = None) -> List[GiftCodeModel]:
        """Tìm kiếm mã Giftcode theo từ khóa/mã."""
        clean_q = f"%{query.strip().upper()}%"
        async with db.get_connection() as conn:
            if game:
                cursor = await conn.execute(
                    "SELECT * FROM gift_codes WHERE game = ? AND code LIKE ? ORDER BY id DESC LIMIT 20",
                    (game.value, clean_q),
                )
            else:
                cursor = await conn.execute(
                    "SELECT * FROM gift_codes WHERE code LIKE ? ORDER BY id DESC LIMIT 20",
                    (clean_q,),
                )
            rows = await cursor.fetchall()
            return [
                GiftCodeModel(
                    id=r["id"],
                    code=r["code"],
                    game=GameType(r["game"]),
                    source=r["source"],
                    sources=r["sources"] if "sources" in r.keys() and r["sources"] else r["source"],
                    rewards=r["rewards"] if "rewards" in r.keys() else None,
                    confidence=r["confidence"] if "confidence" in r.keys() else "MEDIUM",
                    status=r["status"],
                )
                for r in rows
            ]

    @staticmethod
    async def get_sources_summary() -> List[dict]:
        """Tổng hợp các nguồn thu thập mã và số lượng mã tương ứng."""
        async with db.get_connection() as conn:
            cursor = await conn.execute(
                """
                SELECT game, source, COUNT(*) as code_count, MAX(last_checked_at) as last_seen
                FROM gift_codes
                GROUP BY game, source
                ORDER BY game, code_count DESC
                """
            )
            rows = await cursor.fetchall()
            return [
                {
                    "game": r["game"],
                    "source": r["source"],
                    "count": r["code_count"],
                    "last_seen": r["last_seen"],
                }
                for r in rows
            ]


class WebEventRepository:
    @staticmethod
    async def upsert_event(
        external_id: str,
        game: GameType,
        title: str,
        url: str,
        banner_url: Optional[str] = None,
    ) -> Tuple[WebEventModel, bool]:
        async with db.get_connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM web_events WHERE game = ? AND external_id = ?",
                (game.value, external_id),
            )
            row = await cursor.fetchone()
            if row:
                await conn.execute(
                    "UPDATE web_events SET last_seen_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (row["id"],),
                )
                await conn.commit()
                return WebEventModel(
                    id=row["id"],
                    external_id=row["external_id"],
                    game=GameType(row["game"]),
                    title=row["title"],
                    url=row["url"],
                    banner_url=row["banner_url"],
                ), False

            cursor = await conn.execute(
                """
                INSERT INTO web_events (external_id, game, title, url, banner_url)
                VALUES (?, ?, ?, ?, ?)
                RETURNING *
                """,
                (external_id, game.value, title, url, banner_url),
            )
            row = await cursor.fetchone()
            await conn.commit()
            return WebEventModel(
                id=row["id"],
                external_id=row["external_id"],
                game=GameType(row["game"]),
                title=row["title"],
                url=row["url"],
                banner_url=row["banner_url"],
            ), True


class AutomationLogRepository:
    @staticmethod
    async def log(
        task_name: str,
        game: Optional[str] = None,
        account_id: Optional[int] = None,
        status: str = "SUCCESS",
        duration_ms: int = 0,
        message: Optional[str] = None,
        error_detail: Optional[str] = None,
    ):
        async with db.get_connection() as conn:
            await conn.execute(
                """
                INSERT INTO automation_logs (task_name, game, account_id, status, duration_ms, message, error_detail)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (task_name, game, account_id, status, duration_ms, message, error_detail),
            )
            await conn.commit()

    @staticmethod
    async def get_recent_logs(limit: int = 20) -> List[AutomationLogModel]:
        async with db.get_connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM automation_logs ORDER BY id DESC LIMIT ?",
                (limit,),
            )
            rows = await cursor.fetchall()
            return [
                AutomationLogModel(
                    id=r["id"],
                    task_name=r["task_name"],
                    game=r["game"],
                    account_id=r["account_id"],
                    status=r["status"],
                    duration_ms=r["duration_ms"],
                    message=r["message"],
                    error_detail=r["error_detail"],
                    created_at=r["created_at"],
                )
                for r in rows
            ]


class RedemptionJobRepository:
    """Quản lý hàng đợi đổi Giftcode bền vững (Persistent Redemption Queue)."""

    @staticmethod
    async def enqueue_job(gift_code_id: int, account_id: int, game: GameType) -> Optional[RedemptionJobModel]:
        """Thêm job đổi mã vào hàng đợi nếu chưa có."""
        async with db.get_connection() as conn:
            cursor = await conn.execute(
                """
                INSERT INTO redemption_jobs (gift_code_id, account_id, game, status, created_at)
                VALUES (?, ?, ?, 'PENDING', CURRENT_TIMESTAMP)
                ON CONFLICT(gift_code_id, account_id) DO UPDATE SET
                    status = CASE
                        WHEN redemption_jobs.status = 'FAILED' AND redemption_jobs.error_code IN ('AUTH_REQUIRED', 'MAX_RETRIES_EXCEEDED', 'NETWORK_ERROR', 'TIMEOUT') THEN 'PENDING'
                        ELSE redemption_jobs.status
                    END,
                    attempt_count = CASE
                        WHEN redemption_jobs.status = 'FAILED' AND redemption_jobs.error_code IN ('AUTH_REQUIRED', 'MAX_RETRIES_EXCEEDED', 'NETWORK_ERROR', 'TIMEOUT') THEN 0
                        ELSE redemption_jobs.attempt_count
                    END,
                    error_code = CASE
                        WHEN redemption_jobs.status = 'FAILED' AND redemption_jobs.error_code IN ('AUTH_REQUIRED', 'MAX_RETRIES_EXCEEDED', 'NETWORK_ERROR', 'TIMEOUT') THEN NULL
                        ELSE redemption_jobs.error_code
                    END,
                    error_message = CASE
                        WHEN redemption_jobs.status = 'FAILED' AND redemption_jobs.error_code IN ('AUTH_REQUIRED', 'MAX_RETRIES_EXCEEDED', 'NETWORK_ERROR', 'TIMEOUT') THEN NULL
                        ELSE redemption_jobs.error_message
                    END,
                    completed_at = CASE
                        WHEN redemption_jobs.status = 'FAILED' AND redemption_jobs.error_code IN ('AUTH_REQUIRED', 'MAX_RETRIES_EXCEEDED', 'NETWORK_ERROR', 'TIMEOUT') THEN NULL
                        ELSE redemption_jobs.completed_at
                    END,
                    next_retry_at = NULL
                RETURNING *
                """,
                (gift_code_id, account_id, game.value),
            )
            row = await cursor.fetchone()
            await conn.commit()
            if not row or row["status"] not in ("PENDING", "RETRY"):
                return None
            return RedemptionJobModel(
                id=row["id"],
                gift_code_id=row["gift_code_id"],
                account_id=row["account_id"],
                game=GameType(row["game"]),
                status=row["status"],
                attempt_count=row["attempt_count"],
                next_retry_at=row["next_retry_at"],
                locked_at=row["locked_at"],
                created_at=row["created_at"],
                completed_at=row["completed_at"],
                error_code=row["error_code"],
                error_message=row["error_message"],
            )

    @staticmethod
    async def get_pending_or_retry_jobs(limit: int = 50) -> List[RedemptionJobModel]:
        """Lấy danh sách các jobs PENDING hoặc RETRY đã đến hạn thực thi."""
        async with db.get_connection() as conn:
            cursor = await conn.execute(
                """
                SELECT * FROM redemption_jobs
                WHERE status IN ('PENDING', 'RETRY')
                  AND (next_retry_at IS NULL OR next_retry_at <= CURRENT_TIMESTAMP)
                ORDER BY id ASC
                LIMIT ?
                """,
                (limit,),
            )
            rows = await cursor.fetchall()
            return [
                RedemptionJobModel(
                    id=r["id"],
                    gift_code_id=r["gift_code_id"],
                    account_id=r["account_id"],
                    game=GameType(r["game"]),
                    status=r["status"],
                    attempt_count=r["attempt_count"],
                    next_retry_at=r["next_retry_at"],
                    locked_at=r["locked_at"],
                    created_at=r["created_at"],
                    completed_at=r["completed_at"],
                    error_code=r["error_code"],
                    error_message=r["error_message"],
                )
                for r in rows
            ]

    @staticmethod
    async def mark_running(job_id: int):
        """Khóa job và chuyển sang trạng thái RUNNING."""
        async with db.get_connection() as conn:
            await conn.execute(
                "UPDATE redemption_jobs SET status = 'RUNNING', locked_at = CURRENT_TIMESTAMP WHERE id = ?",
                (job_id,),
            )
            await conn.commit()

    @staticmethod
    async def mark_completed(
        job_id: int, status: str = "SUCCESS", error_code: Optional[str] = None, error_message: Optional[str] = None
    ):
        """Đánh dấu job đã hoàn thành (SUCCESS, FAILED, CANCELLED)."""
        async with db.get_connection() as conn:
            await conn.execute(
                """
                UPDATE redemption_jobs
                SET status = ?, completed_at = CURRENT_TIMESTAMP, error_code = ?, error_message = ?
                WHERE id = ?
                """,
                (status, error_code, error_message, job_id),
            )
            await conn.commit()

    @staticmethod
    async def mark_retry(
        job_id: int, next_retry_at_str: str, error_code: Optional[str] = None, error_message: Optional[str] = None
    ):
        """Đánh dấu job cần thử lại sau một khoảng thời gian backoff."""
        async with db.get_connection() as conn:
            await conn.execute(
                """
                UPDATE redemption_jobs
                SET status = 'RETRY',
                    attempt_count = attempt_count + 1,
                    next_retry_at = ?,
                    error_code = ?,
                    error_message = ?
                WHERE id = ?
                """,
                (next_retry_at_str, error_code, error_message, job_id),
            )
            await conn.commit()

    @staticmethod
    async def reset_stale_running_jobs():
        """Khôi phục các job bị kẹt ở RUNNING khi bot bị restart/crash."""
        async with db.get_connection() as conn:
            await conn.execute(
                """
                UPDATE redemption_jobs
                SET status = 'RETRY', next_retry_at = CURRENT_TIMESTAMP
                WHERE status = 'RUNNING'
                """
            )
            await conn.commit()

