"""Mô hình SQLAlchemy ORM chuẩn cho PostgreSQL và SQLite."""

from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    discord_user_id = Column(Integer, unique=True, nullable=False, index=True)
    default_game = Column(String(32), nullable=False, default="genshin")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    discord_user_id = Column(Integer, nullable=False, index=True)
    game = Column(String(32), nullable=False)
    uid = Column(Integer, nullable=False)
    server = Column(String(32), nullable=False)
    nickname = Column(String(128), nullable=True)
    is_default = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("discord_user_id", "game", "uid", name="uq_accounts_user_game_uid"),
        Index("idx_accounts_user_game", "discord_user_id", "game"),
    )


class Setting(Base):
    __tablename__ = "settings"

    discord_user_id = Column(Integer, primary_key=True)
    theme = Column(String(32), nullable=False, default="dark")
    show_uid = Column(Boolean, nullable=False, default=False)
    use_cards = Column(Boolean, nullable=False, default=True)
    ephemeral_default = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Session(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    discord_user_id = Column(Integer, nullable=False, index=True)
    game = Column(String(32), nullable=False)
    uid = Column(Integer, nullable=False)
    cookie_encrypted = Column(Text, nullable=False)
    session_status = Column(String(32), nullable=False, default="VALID")
    last_auth_check = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("discord_user_id", "game", "uid", name="uq_sessions_user_game_uid"),
        Index("idx_sessions_user_game", "discord_user_id", "game"),
    )


class AutomationSetting(Base):
    __tablename__ = "automation_settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, unique=True, nullable=False, index=True)
    discord_user_id = Column(Integer, nullable=False, index=True)
    automation_enabled = Column(Boolean, nullable=False, default=True)
    checkin_enabled = Column(Boolean, nullable=False, default=True)
    redeem_enabled = Column(Boolean, nullable=False, default=True)
    mimo_enabled = Column(Boolean, nullable=False, default=True)
    accompany_enabled = Column(Boolean, nullable=False, default=False)
    event_notify_enabled = Column(Boolean, nullable=False, default=True)
    notify_mode = Column(String(32), nullable=False, default="FAILURE_ONLY")
    notify_channel_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CheckinExecution(Base):
    __tablename__ = "checkin_executions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, nullable=False, index=True)
    game = Column(String(32), nullable=False)
    run_date = Column(String(32), nullable=False)
    status = Column(String(32), nullable=False)
    reward_summary = Column(Text, nullable=True)
    error_code = Column(String(64), nullable=True)
    executed_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("account_id", "run_date", name="uq_checkin_account_date"),
        Index("idx_checkin_account_date", "account_id", "run_date"),
    )


class GiftCode(Base):
    __tablename__ = "gift_codes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(64), nullable=False)
    normalized_code = Column(String(64), nullable=True)
    game = Column(String(32), nullable=False)
    source = Column(String(64), nullable=False)
    sources = Column(Text, nullable=True)
    rewards = Column(Text, nullable=True)
    confidence = Column(String(32), nullable=False, default="MEDIUM")
    first_seen_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    last_checked_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String(32), nullable=False, default="ACTIVE")

    __table_args__ = (
        UniqueConstraint("game", "code", name="uq_gift_codes_game_code"),
        Index("idx_giftcodes_active", "game", "status"),
    )


class GiftcodeRedemption(Base):
    __tablename__ = "giftcode_redemptions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, nullable=False, index=True)
    gift_code_id = Column(Integer, nullable=False, index=True)
    game = Column(String(32), nullable=False)
    code = Column(String(64), nullable=False)
    status = Column(String(32), nullable=False)
    response_msg = Column(Text, nullable=True)
    attempt_count = Column(Integer, default=1)
    redeemed_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("account_id", "gift_code_id", name="uq_redemptions_account_code"),
    )


class RedemptionJob(Base):
    """Hàng đợi đổi mã Giftcode bất đồng bộ bền vững (Persistent Redemption Queue)."""
    __tablename__ = "redemption_jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    gift_code_id = Column(Integer, nullable=False, index=True)
    account_id = Column(Integer, nullable=False, index=True)
    game = Column(String(32), nullable=False)
    status = Column(String(32), nullable=False, default="PENDING")  # PENDING, RUNNING, SUCCESS, FAILED, RETRY, CANCELLED
    attempt_count = Column(Integer, default=0)
    next_retry_at = Column(DateTime, nullable=True)
    locked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    error_code = Column(String(64), nullable=True)
    error_message = Column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("gift_code_id", "account_id", name="uq_redemption_jobs_gift_account"),
        Index("idx_redemption_jobs_status_retry", "status", "next_retry_at"),
    )


class WebEvent(Base):
    __tablename__ = "web_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    external_id = Column(String(128), nullable=False)
    game = Column(String(32), nullable=False)
    title = Column(String(256), nullable=False)
    url = Column(Text, nullable=False)
    banner_url = Column(Text, nullable=True)
    start_at = Column(DateTime, nullable=True)
    end_at = Column(DateTime, nullable=True)
    first_seen_at = Column(DateTime, default=datetime.utcnow)
    last_seen_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("game", "external_id", name="uq_web_events_game_ext_id"),
    )


class AutomationLog(Base):
    __tablename__ = "automation_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_name = Column(String(64), nullable=False, index=True)
    game = Column(String(32), nullable=True)
    account_id = Column(Integer, nullable=True)
    status = Column(String(32), nullable=False)
    duration_ms = Column(Integer, default=0)
    message = Column(Text, nullable=True)
    error_detail = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_auto_logs_task_status", "task_name", "status"),
    )


class AutomationTask(Base):
    __tablename__ = "automation_tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, nullable=False, index=True)
    provider = Column(String(32), nullable=False)
    external_task_id = Column(String(128), nullable=False)
    task_name = Column(String(256), nullable=False)
    status = Column(String(32), nullable=False)
    reward = Column(Text, nullable=True)
    first_seen_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    last_error = Column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("account_id", "provider", "external_task_id", name="uq_auto_tasks_acc_prov_ext"),
    )
