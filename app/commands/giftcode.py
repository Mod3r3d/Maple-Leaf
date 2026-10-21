"""Nhóm lệnh /giftcode tra cứu mã quà tặng và đổi thưởng thủ công."""

from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from app.automation.providers.hoyolab import HoYoLABRedeemProvider
from app.db.repositories.accounts import AccountRepository
from app.db.repositories.automation import (
    GiftCodeRepository,
    SessionRepository,
)
from app.games.enums import GameType


class GiftcodeCommands(commands.GroupCog, group_name="giftcode"):
    """Tra cứu các mã quà tặng Giftcode hoạt động và đổi quà."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="list", description="Xem danh sách các mã Giftcode đang hoạt động")
    @app_commands.describe(game="Chọn tựa game muốn xem mã")
    @app_commands.choices(
        game=[
            app_commands.Choice(name="Genshin Impact", value=GameType.GENSHIN.value),
            app_commands.Choice(name="Honkai: Star Rail", value=GameType.HSR.value),
        ]
    )
    async def giftcode_list(self, interaction: discord.Interaction, game: Optional[app_commands.Choice[str]] = None):
        await interaction.response.defer()
        target_game = GameType(game.value) if game else None

        games_to_query = [target_game] if target_game else [GameType.GENSHIN, GameType.HSR]

        embed = discord.Embed(
            title="🎁 Danh Sách Giftcode Đang Hoạt Động",
            description="Các mã quà tặng phát hiện được bởi hệ thống tự động:",
            color=0xF39C12,
        )

        for g in games_to_query:
            codes = await GiftCodeRepository.get_active_codes(g)
            if not codes:
                embed.add_field(name=f"{g.display_name}", value="*Hiện chưa có mã mới*", inline=False)
                continue

            code_lines = []
            for c in codes:
                badge = "✅" if getattr(c, "confidence", "MEDIUM") == "HIGH" else "🟢"
                rewards = c.rewards
                if rewards and len(rewards) > 42:
                    rewards = rewards[:39] + "..."
                reward_info = f" • *{rewards}*" if rewards else ""
                src_display = c.sources if c.sources else c.source
                code_lines.append(f"{badge} **`{c.code}`**{reward_info}\n   └─ Xác nhận: `{src_display}`")

            # Chia nhỏ code_lines thành từng field không vượt quá 900 ký tự
            chunks = []
            curr_chunk = []
            curr_len = 0
            for line in code_lines:
                line_len = len(line) + 1
                if curr_len + line_len > 900:
                    if curr_chunk:
                        chunks.append(curr_chunk)
                    curr_chunk = [line]
                    curr_len = line_len
                else:
                    curr_chunk.append(line)
                    curr_len += line_len
            if curr_chunk:
                chunks.append(curr_chunk)

            game_icon = g.emoji
            for p_idx, chunk in enumerate(chunks):
                part_label = f" (Phần {p_idx + 1})" if len(chunks) > 1 else ""
                field_title = f"{game_icon} {g.display_name}{part_label} — {len(codes)} mã hoạt động"
                embed.add_field(
                    name=field_title,
                    value="\n".join(chunk),
                    inline=False,
                )

        embed.set_footer(text="✅: Đã xác thực qua nhiều nguồn | Bot tự động đổi mã cho tài khoản bật Auto Redeem")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="redeem", description="Đổi thủ công một mã Giftcode cho tài khoản của bạn")
    @app_commands.describe(code="Mã giftcode hoặc liên kết đổi mã HoYoverse", game="Chọn tựa game")
    @app_commands.choices(
        game=[
            app_commands.Choice(name="Genshin Impact", value=GameType.GENSHIN.value),
            app_commands.Choice(name="Honkai: Star Rail", value=GameType.HSR.value),
        ]
    )
    async def giftcode_redeem(
        self, interaction: discord.Interaction, code: str, game: app_commands.Choice[str]
    ):
        await interaction.response.defer(ephemeral=True)
        from app.services.redeem_service import RedeemService, normalize_giftcode

        clean_code = normalize_giftcode(code)
        if not clean_code:
            embed = discord.Embed(
                title="❌ Mã Giftcode Không Hợp Lệ",
                description=(
                    f"Giá trị bạn nhập: `{code}` không đúng định dạng mã quà tặng.\n\n"
                    "👉 **Định dạng được hỗ trợ:**\n"
                    "• **Mã trực tiếp:** Gồm 4–32 ký tự chữ và số (VD: `GENSHINGIFT`, `STARRAILGIFT`).\n"
                    "• **Liên kết đổi mã:** Dán URL trang đổi mã chứa `?code=...` hoặc `?cdkey=...`\n"
                    "  *(VD: `https://genshin.hoyoverse.com/en/gift?code=GENSHINGIFT`)*"
                ),
                color=0xE74C3C,
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        game_enum = GameType(game.value)
        acc = await AccountRepository.get_default_account(interaction.user.id, game_enum)
        if not acc:
            await interaction.followup.send(
                f"❌ Bạn chưa có tài khoản {game_enum.display_name} mặc định nào. Hãy dùng `/account add` trước.",
                ephemeral=True,
            )
            return

        status, msg = await RedeemService.redeem_for_account(
            account=acc,
            code=clean_code,
            is_manual=True,
        )

        status_colors = {
            "SUCCESS": 0x2ECC71,          # Xanh lá
            "ALREADY_REDEEMED": 0xF1C40F, # Vàng
            "INVALID_CODE": 0xE67E22,     # Cam
            "EXPIRED": 0xE67E22,          # Cam
            "LEVEL_TOO_LOW": 0x9B59B6,    # Tím
            "REGION_LOCK": 0x95A5A6,      # Xám
            "AUTH_REQUIRED": 0xE74C3C,    # Đỏ
            "RATE_LIMITED": 0xE67E22,     # Cam
            "NETWORK_ERROR": 0xE74C3C,    # Đỏ
            "FAILED": 0xE74C3C,           # Đỏ
        }

        status_titles = {
            "SUCCESS": "🎁 Đổi Mã Thành Công",
            "ALREADY_REDEEMED": "⚠️ Mã Đã Được Đổi Trước Đó",
            "INVALID_CODE": "❌ Mã Không Tồn Tại Hoặc Không Hợp Lệ",
            "EXPIRED": "⏰ Mã Đã Hết Hạn Sử Dụng",
            "LEVEL_TOO_LOW": "⚠️ Cấp Bậc Chưa Đủ Điều Kiện",
            "REGION_LOCK": "🌐 Giới Hạn Khu Vực Máy Chủ",
            "AUTH_REQUIRED": "🔒 Cần Cập Nhật Cookie Đổi Mã",
            "RATE_LIMITED": "⏳ Giới Hạn Tần Suất (Rate Limited)",
            "NETWORK_ERROR": "📡 Lỗi Kết Nối Mạng",
            "FAILED": "❌ Đổi Mã Thất Bại",
        }

        color = status_colors.get(status, 0x95A5A6)
        title = f"{status_titles.get(status, '🎁 Kết Quả Đổi Mã')}: {clean_code}"

        embed = discord.Embed(
            title=title,
            description=(
                f"Tài khoản: {acc.game.emoji} **{acc.nickname or acc.uid}** (`{acc.uid}` • {acc.server.value})\n"
                f"Trạng thái: **`{status}`**\n\n"
                f"**Kết quả:** {msg}"
            ),
            color=color,
        )
        if status == "AUTH_REQUIRED":
            embed.set_footer(text="Mẹo: Dùng /auto session_add để thêm cookie (kèm stoken để tự gia hạn).")
        elif status == "SUCCESS":
            embed.set_footer(text="Phần thưởng sẽ được gửi trực tiếp vào hòm thư trong game của bạn.")

        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="search", description="Tra cứu thông tin và độ tin cậy của một mã Giftcode")
    @app_commands.describe(code="Mã giftcode hoặc liên kết cần tra cứu")
    async def giftcode_search(self, interaction: discord.Interaction, code: str):
        await interaction.response.defer(ephemeral=True)
        from app.services.redeem_service import normalize_giftcode

        clean_code = normalize_giftcode(code) or code.strip().upper()
        results = await GiftCodeRepository.search_code(clean_code)

        if not results:
            await interaction.followup.send(
                f"🔍 Không tìm thấy thông tin cho mã **`{clean_code}`** trong cơ sở dữ liệu hệ thống.",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title=f"🔍 Kết Quả Tra Cứu Giftcode: {clean_code}",
            description=f"Tìm thấy **{len(results)}** mã liên quan trong hệ thống:",
            color=0x3498DB,
        )

        for item in results:
            badge = "✅ Chính thức / Đã xác thực" if item.confidence == "HIGH" else "🟢 Cộng đồng"
            status_text = "🟢 Hoạt động" if item.status == "ACTIVE" else f"⚪ {item.status}"
            rewards_text = item.rewards if item.rewards else "Chưa có thông tin phần thưởng"
            src_text = item.sources if item.sources else item.source

            field_val = (
                f"**Game:** {item.game.emoji} {item.game.display_name}\n"
                f"**Trạng thái:** {status_text} | **Độ tin cậy:** {badge}\n"
                f"**Nguồn thu thập:** `{src_text}`\n"
                f"**Phần thưởng:** {rewards_text}"
            )
            embed.add_field(name=f"Mã: `{item.code}`", value=field_val, inline=False)

        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="sources", description="Xem các nguồn phát hiện Giftcode đang hoạt động")
    async def giftcode_sources(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        sources = await GiftCodeRepository.get_sources_summary()

        embed = discord.Embed(
            title="📡 Các Nguồn Thu Thập Giftcode (Aggregator Sources)",
            description=(
                "Bot tự động tổng hợp mã từ nhiều nguồn độc lập, chuẩn hóa và loại bỏ trùng lặp:\n"
                "• **Official API**: Thông báo và sự kiện chính thức HoYoverse\n"
                "• **HoYoLAB Community**: Bài viết và chuyên mục quà tặng HoYoLAB\n"
                "• **Seria Game Codes**: Kho mã cộng đồng cập nhật liên tục\n"
            ),
            color=0x9B59B6,
        )

        if sources:
            for s in sources:
                g_enum = GameType(s["game"])
                last_seen = s["last_seen"] or "N/A"
                embed.add_field(
                    name=f"{g_enum.emoji} {g_enum.display_name} — Nguồn: `{s['source']}`",
                    value=f"• Đã thu thập: **{s['count']}** mã\n• Lần kiểm tra cuối: `{last_seen}`",
                    inline=True,
                )
        else:
            embed.add_field(
                name="Trạng thái nguồn",
                value="Hệ thống đang sẵn sàng và đồng bộ với các API thu thập mã.",
                inline=False,
            )

        embed.set_footer(text="Cơ chế Aggregator tự động gộp nguồn để tăng độ tin cậy của mã quà tặng.")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="history", description="Xem lịch sử đổi giftcode của tài khoản bạn")
    async def giftcode_history(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        accounts = await AccountRepository.get_accounts_by_user(interaction.user.id)
        if not accounts:
            await interaction.followup.send(
                "❌ Bạn chưa có tài khoản nào được liên kết. Hãy dùng `/account add` trước.",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title="🎁 Lịch Sử Đổi Mã Giftcode",
            description="Các mã giftcode đã được đổi cho tài khoản của bạn:",
            color=0xF39C12,
        )

        for acc in accounts:
            redeems = await GiftCodeRepository.get_redemption_history(acc.id, limit=8)
            header = f"{acc.game.emoji} {acc.nickname or acc.uid} ({acc.game.display_name} - `{acc.uid}`)"
            if redeems:
                lines = []
                for r in redeems:
                    status_icon = "✅" if r.status in ("SUCCESS", "ALREADY_REDEEMED") else "⚠️"
                    date_str = r.redeemed_at.strftime("%d/%m %H:%M") if r.redeemed_at else ""
                    lines.append(f"{status_icon} **`{r.code}`** — {r.status} {f'({date_str})' if date_str else ''}")
                embed.add_field(name=header, value="\n".join(lines), inline=False)
            else:
                embed.add_field(name=header, value="*Chưa có lượt đổi mã nào ghi nhận*", inline=False)

        embed.set_footer(text="Hệ thống lưu vết để đảm bảo không bị đổi trùng lặp mã.")
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(GiftcodeCommands(bot))

