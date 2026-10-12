"""Các kiểu dữ liệu Enum dùng trong HoyoBot (Genshin Impact & Honkai: Star Rail)."""

import re
from enum import Enum


# Emoji Unicode mặc định — dùng khi người dùng KHÔNG cấu hình emoji tuỳ biến.
# Nhờ vậy bot hiển thị đúng trên mọi server Discord, không phụ thuộc server của tác giả.
DEFAULT_GAME_EMOJI = {
    "genshin": "🍃",
    "hsr": "🚄",
}

# Thẻ emoji tuỳ biến của Discord, ví dụ: <:genshin_icon:123> hoặc <a:name:123>
_CUSTOM_EMOJI_RE = re.compile(r"^<(a?):(\w+):(\d+)>$")


class GameType(str, Enum):
    GENSHIN = "genshin"
    HSR = "hsr"

    @property
    def display_name(self) -> str:
        if self == GameType.GENSHIN:
            return "Genshin Impact"
        return "Honkai: Star Rail"

    @property
    def short_name(self) -> str:
        if self == GameType.GENSHIN:
            return "Genshin"
        return "Star Rail"

    @property
    def emoji(self) -> str:
        """Emoji hiển thị của game (emoji tuỳ biến nếu được cấu hình, ngược lại là Unicode)."""
        from app.config import settings

        custom = settings.GENSHIN_EMOJI if self == GameType.GENSHIN else settings.HSR_EMOJI
        if custom and custom.strip():
            return custom.strip()
        return DEFAULT_GAME_EMOJI[self.value]

    @property
    def discord_emoji(self):
        """Trả về `PartialEmoji` nếu là emoji tuỳ biến, ngược lại trả về chuỗi Unicode."""
        import discord

        raw = self.emoji
        match = _CUSTOM_EMOJI_RE.match(raw)
        if match:
            animated, name, emoji_id = match.groups()
            return discord.PartialEmoji(name=name, id=int(emoji_id), animated=bool(animated))
        return raw

    @property
    def icon_url(self) -> str:
        if self == GameType.GENSHIN:
            return "https://enka.network/ui/UI_AvatarIcon_Paimon.png"
        return "https://raw.githubusercontent.com/Mar-7th/StarRailRes/master/icon/avatar/1001.png"


class ServerRegion(str, Enum):
    ASIA = "Asia"
    AMERICA = "America"
    EUROPE = "Europe"
    TW_HK_MO = "TW/HK/MO"
    CHINA = "China"
    UNKNOWN = "Không xác định"


class GenshinElement(str, Enum):
    PYRO = "Hỏa"
    HYDRO = "Thủy"
    ANEMO = "Phong"
    ELECTRO = "Lôi"
    DENDRO = "Thảo"
    CRYO = "Băng"
    GEO = "Nham"
    NONE = "Vô thuộc tính"


class HSRElement(str, Enum):
    PHYSICAL = "Vật Lý"
    FIRE = "Hỏa"
    ICE = "Băng"
    LIGHTNING = "Lôi"
    WIND = "Phong"
    QUANTUM = "Lượng Tử"
    IMAGINARY = "Số Ảo"
    NONE = "Vô thuộc tính"


class HSRPath(str, Enum):
    DESTRUCTION = "Hủy Diệt"
    HUNT = "Săn Bắn"
    ERUDITION = "Tri Thức"
    HARMONY = "Hòa Hợp"
    NIHILITY = "Hư Vô"
    PRESERVATION = "Bảo Hộ"
    ABUNDANCE = "Trù Phú"
    REMEMBRANCE = "Ký Ức"
    UNKNOWN = "Chưa rõ"


class GenshinWeaponType(str, Enum):
    SWORD = "Kiếm Đơn"
    CLAYMORE = "Trọng Kiếm"
    POLEARM = "Vũ Khí Cán Dài"
    BOW = "Cung"
    CATALYST = "Pháp Khí"
    UNKNOWN = "Khác"
