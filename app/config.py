"""Cấu hình ứng dụng Maple Leaf (bao gồm lớp Automation v2)."""

from pathlib import Path
from typing import List, Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Discord Bot Token
    DISCORD_TOKEN: str = ""

    # Database
    DATABASE_PATH: str = "data/mapleleaf.db"
    DATABASE_URL: Optional[str] = None

    # Debug & Logging
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # Cache & timeouts
    CACHE_TTL_SECONDS: int = 3600
    ENKA_TIMEOUT_SECONDS: int = 12

    # Automation v2 Core Settings
    AUTOMATION_ENABLED: bool = True
    AUTOMATION_MODE: str = "live"  # 'live' hoặc 'dry-run'
    ENCRYPTION_KEY: Optional[str] = None
    TIMEZONE: str = "Asia/Ho_Chi_Minh"

    # Scheduler Intervals
    CHECKIN_CRON_HOUR: int = 0
    CHECKIN_CRON_MINUTE: int = 5
    GIFTCODE_SCAN_INTERVAL_MINUTES: int = 60
    MIMO_SCAN_INTERVAL_MINUTES: int = 60
    WEB_EVENT_SCAN_INTERVAL_MINUTES: int = 120

    # Tự gia hạn token (giúp người dùng CHỈ CẦN ĐĂNG NHẬP MỘT LẦN).
    # Khi cookie có `stoken`, bot định kỳ lấy `cookie_token` mới (token đổi mã chỉ
    # sống vài giờ) và lưu lại vào CSDL, nên không bao giờ phải dán lại cookie.
    TOKEN_REFRESH_ENABLED: bool = True
    TOKEN_REFRESH_INTERVAL_HOURS: int = 12

    # Rate Limiting & Concurrency
    MAX_CONCURRENT_AUTOMATION_TASKS: int = 5
    PROVIDER_REQUEST_DELAY_SECONDS: float = 1.5

    # Admin Discord User IDs (danh sách ID cách nhau bởi dấu phẩy, ví dụ: "12345678,87654321")
    ADMIN_USER_IDS: str = ""

    # Health Check & Captcha Web Server (tự động kích hoạt khi có PORT trên Render / Cloud PaaS)
    PORT: Optional[int] = None
    HEALTH_HOST: str = "0.0.0.0"
    RENDER_EXTERNAL_URL: Optional[str] = None
    PUBLIC_URL: Optional[str] = None

    # Tự ping /healthz để Render Free không cho service "ngủ" (chỉ chạy khi có URL công khai)
    KEEPALIVE_ENABLED: bool = True
    KEEPALIVE_INTERVAL_MINUTES: int = 10

    @property
    def web_base_url(self) -> str:
        """URL công khai của web server để người dùng mở trang giải Captcha."""
        if self.PUBLIC_URL:
            return self.PUBLIC_URL.rstrip("/")
        if self.RENDER_EXTERNAL_URL:
            return self.RENDER_EXTERNAL_URL.rstrip("/")
        port = self.PORT or 10000
        return f"http://localhost:{port}"

    # Embed Colors
    GENSHIN_COLOR: int = 0x5BC0BE  # Xanh ngọc Genshin
    HSR_COLOR: int = 0x9370DB      # Tím huyền ảo Astral Express
    PRIMARY_COLOR: int = 0x3498DB  # Xanh lam chủ đạo
    SUCCESS_COLOR: int = 0x2ECC71  # Xanh lá thành công
    ERROR_COLOR: int = 0xE74C3C    # Đỏ báo lỗi
    WARNING_COLOR: int = 0xF39C12  # Vàng cảnh báo

    # Assets & Card rendering
    ASSETS_DIR: Path = BASE_DIR / "assets"
    DATA_DIR: Path = BASE_DIR / "data"

    # Emoji hiển thị cho từng game.
    # Để TRỐNG = dùng emoji Unicode mặc định (chạy đúng ở mọi server Discord).
    # Nếu server của bạn có emoji tuỳ biến, điền nguyên thẻ emoji vào đây, ví dụ:
    #   GENSHIN_EMOJI=<:genshin_icon:1556606822314672142>
    GENSHIN_EMOJI: str = ""
    HSR_EMOJI: str = ""

    @field_validator(
        "GENSHIN_COLOR",
        "HSR_COLOR",
        "PRIMARY_COLOR",
        "SUCCESS_COLOR",
        "ERROR_COLOR",
        "WARNING_COLOR",
        mode="before",
    )
    @classmethod
    def _parse_color(cls, value):
        """Cho phép khai báo màu dạng hex trong .env: `0x5BC0BE`, `#5BC0BE` hoặc số thập phân."""
        if isinstance(value, str):
            raw = value.strip()
            if raw.lower().startswith("0x"):
                return int(raw, 16)
            if raw.startswith("#"):
                return int(raw[1:], 16)
            if raw.isdigit():
                return int(raw)
        return value

    @property
    def db_file_path(self) -> Path:
        path = Path(self.DATABASE_PATH)
        if not path.is_absolute():
            return BASE_DIR / path
        return path

    @property
    def async_database_url(self) -> str:
        if self.DATABASE_URL:
            url = self.DATABASE_URL
            if url.startswith("postgres://"):
                url = url.replace("postgres://", "postgresql+asyncpg://", 1)
            elif url.startswith("postgresql://"):
                url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
            return url
        return f"sqlite+aiosqlite:///{self.db_file_path.as_posix()}"

    @property
    def is_postgres(self) -> bool:
        return bool(self.DATABASE_URL and ("postgres" in self.DATABASE_URL))

    @property
    def admin_ids(self) -> List[int]:
        if not self.ADMIN_USER_IDS:
            return []
        ids = []
        for x in self.ADMIN_USER_IDS.split(","):
            x = x.strip()
            if x.isdigit():
                ids.append(int(x))
        return ids


settings = Settings()
