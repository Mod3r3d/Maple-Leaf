"""Nhóm lệnh /auto quản lý trung tâm điều khiển Tự Động Hóa."""

from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from app.automation.manager import automation_manager
from app.db.repositories.accounts import AccountRepository
from app.db.repositories.automation import (
    AutomationSettingsRepository,
    CheckinRepository,
    GiftCodeRepository,
    SessionRepository,
)
from app.games.enums import GameType
from app.security.encryption import inspect_cookie_tokens
from app.ui.automation.views import (
    AutomationDashboardView,
    CookieInputModal,
    LoginModal,
    build_cookie_view_embed,
)


class AutoCommands(commands.GroupCog, group_name="auto"):
    """Trung tâm quản lý các tính năng tự động hóa (Điểm danh, Đổi giftcode, Mimo, Sự kiện)."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="status", description="Xem trạng thái hoạt động của các tính năng tự động hóa")
    async def auto_status(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        accounts = await AccountRepository.get_accounts_by_user(interaction.user.id)

        if not accounts:
            await interaction.followup.send(
                "Bạn chưa có tài khoản nào được liên kết! Dùng lệnh `/account add` trước để bắt đầu.",
                ephemeral=True,
            )
            return

        accounts_data = []
        embed = discord.Embed(
            title="✦ Bảng Điều Khiển Tự Động Hóa",
            description="Trạng thái cấu hình chạy nền cho các tài khoản game của bạn:",
            color=0x3498DB,
        )

        for acc in accounts:
            auto_set = await AutomationSettingsRepository.get_or_create(acc.id, interaction.user.id)
            sess = await SessionRepository.get_session(interaction.user.id, acc.game, acc.uid)
            accounts_data.append((acc, auto_set, sess))

            # Biểu tượng trạng thái session
            if not sess:
                session_text = "❌ Chưa liên kết Cookie (Bấm nút bên dưới để thêm)"
            elif sess.session_status == "VALID":
                session_text = "✅ Phiên đăng nhập hợp lệ (Đã mã hóa an toàn)"
            elif sess.session_status == "EXPIRED":
                session_text = "⚠️ Cookie đã hết hạn, cần cập nhật lại"
            else:
                session_text = f"❓ Trạng thái: {sess.session_status}"

            def mark(b: bool) -> str:
                return "✅ Bật" if b else "❌ Tắt"

            # Đánh giá riêng khả năng ĐỔI MÃ (khác với trạng thái điểm danh):
            # điểm danh dùng ltoken_v2, còn đổi mã cần cookie_token (+ stoken để tự gia hạn).
            redeem_ready = "— (chưa có cookie)"
            if sess:
                try:
                    raw = await SessionRepository.get_decrypted_cookie(sess)
                    info = inspect_cookie_tokens(raw)
                    if info["redeem_durable"]:
                        redeem_ready = "⚡ Bền vững (có `stoken` + `ltmid_v2`)"
                    elif info["has_cookie_token"]:
                        redeem_ready = "⚠️ Tạm thời (có `cookie_token_v2`, thiếu `stoken`)"
                    elif info["has_stoken"] and not info.get("has_mid"):
                        redeem_ready = "❌ Thiếu `ltmid_v2` (có `stoken` nhưng thiếu mid)"
                    else:
                        redeem_ready = "❌ Chưa thể đổi mã (thiếu token)"
                except Exception:
                    redeem_ready = "❓ Không đọc được cookie"

            field_val = (
                f"**UID:** `{acc.uid}` ({acc.server.value})\n"
                f"**Phiên HoYoLAB:** {session_text}\n"
                f"**Khả năng đổi Giftcode:** {redeem_ready}\n"
                f"├─ Tự động chạy nền: {mark(auto_set.automation_enabled)}\n"
                f"├─ Điểm danh hàng ngày: {mark(auto_set.checkin_enabled)}\n"
                f"├─ Tự động nhận Giftcode: {mark(auto_set.redeem_enabled)}\n"
                f"├─ Nhiệm vụ Mimo: {mark(auto_set.mimo_enabled)}\n"
                f"├─ Đồng hành (Accompany): {mark(auto_set.accompany_enabled)}\n"
                f"└─ Báo sự kiện Web: {mark(auto_set.event_notify_enabled)}\n"
            )
            embed.add_field(
                name=f"{acc.game.emoji} {acc.nickname or acc.uid} ({acc.game.display_name})",
                value=field_val,
                inline=False,
            )

        embed.set_footer(text="Dùng /auto toggle để bật/tắt từng tính năng, hoặc bấm các nút bên dưới để thao tác nhanh.")
        view = AutomationDashboardView(interaction.user.id, accounts_data)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    @app_commands.command(name="toggle", description="Bật hoặc tắt tính năng tự động cụ thể")
    @app_commands.describe(
        tinh_nang="Chọn tính năng bạn muốn bật hoặc tắt",
        trang_thai="Chọn BẬT hoặc TẮT",
    )
    @app_commands.choices(
        tinh_nang=[
            app_commands.Choice(name="Toàn bộ Tự Động Hóa (Tất cả)", value="automation"),
            app_commands.Choice(name="Điểm Danh Hàng Ngày (Check-in)", value="checkin"),
            app_commands.Choice(name="Tự Động Đổi Giftcode (Auto Redeem)", value="redeem"),
            app_commands.Choice(name="Nhiệm Vụ Mimo", value="mimo"),
            app_commands.Choice(name="Điểm Danh Đồng Hành (Accompany)", value="accompany"),
            app_commands.Choice(name="Thông Báo Sự Kiện Web", value="events"),
        ],
        trang_thai=[
            app_commands.Choice(name="Bật (Hoạt động)", value="1"),
            app_commands.Choice(name="Tắt (Tạm ngưng)", value="0"),
        ],
    )
    async def auto_toggle(
        self,
        interaction: discord.Interaction,
        tinh_nang: app_commands.Choice[str],
        trang_thai: app_commands.Choice[str],
    ):
        await interaction.response.defer(ephemeral=True)
        enabled = trang_thai.value == "1"

        accounts = await AccountRepository.get_accounts_by_user(interaction.user.id)
        if not accounts:
            await interaction.followup.send("Bạn chưa có tài khoản nào. Hãy dùng `/account add` trước.", ephemeral=True)
            return

        for acc in accounts:
            await AutomationSettingsRepository.get_or_create(acc.id, interaction.user.id)
            await AutomationSettingsRepository.update_feature(acc.id, tinh_nang.value, enabled)

        trang_thai_str = "BẬT" if enabled else "TẮT"
        await interaction.followup.send(
            f"✅ Đã **{trang_thai_str}** tính năng **{tinh_nang.name}** cho toàn bộ tài khoản của bạn!",
            ephemeral=True,
        )

    @app_commands.command(
        name="login",
        description="Đăng nhập HoYoLAB bằng email + mật khẩu để bot tự lấy cookie đầy đủ (có stoken)",
    )
    async def auto_login(self, interaction: discord.Interaction):
        accounts = await AccountRepository.get_accounts_by_user(interaction.user.id)
        if not accounts:
            await interaction.response.send_message(
                "Bạn chưa có tài khoản nào. Hãy dùng `/account add` trước.", ephemeral=True
            )
            return

        await interaction.response.send_modal(LoginModal(discord_user_id=interaction.user.id))

    @app_commands.command(name="session_add", description="Mở cửa sổ thêm/cập nhật Cookie HoYoLAB an toàn")
    @app_commands.describe(
        ap_dung="Chọn phạm vi áp dụng Cookie (mặc định áp dụng chung cho tất cả tài khoản game)"
    )
    @app_commands.choices(
        ap_dung=[
            app_commands.Choice(name="✦ Tất cả tài khoản game (Khuyên dùng)", value="all"),
            app_commands.Choice(name="Genshin Impact", value="genshin"),
            app_commands.Choice(name="Honkai: Star Rail", value="hsr"),
        ]
    )
    async def auto_session_add(
        self, interaction: discord.Interaction, ap_dung: Optional[app_commands.Choice[str]] = None
    ):
        accounts = await AccountRepository.get_accounts_by_user(interaction.user.id)
        if not accounts:
            await interaction.response.send_message(
                "Bạn chưa có tài khoản nào. Hãy dùng `/account add` trước.", ephemeral=True
            )
            return

        scope = ap_dung.value if ap_dung else "all"
        modal = CookieInputModal(
            discord_user_id=interaction.user.id,
            target_scope=scope,
        )
        await interaction.response.send_modal(modal)

    @app_commands.command(name="session_view", description="Xem thông tin chi tiết và các token trong Cookie hiện tại")
    @app_commands.describe(
        hien_thi_day_du="Hiện đầy đủ chuỗi Cookie không che (Mặc định: Tắt để bảo vệ an toàn)"
    )
    async def auto_session_view(
        self, interaction: discord.Interaction, hien_thi_day_du: bool = False
    ):
        await interaction.response.defer(ephemeral=True)
        embed = await build_cookie_view_embed(interaction.user.id, full=hien_thi_day_du)
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="session_remove", description="Xóa phiên đăng nhập Cookie HoYoLAB đã lưu")
    async def auto_session_remove(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        accounts = await AccountRepository.get_accounts_by_user(interaction.user.id)
        if not accounts:
            await interaction.followup.send("Bạn chưa có tài khoản nào.", ephemeral=True)
            return

        count = 0
        for acc in accounts:
            if await SessionRepository.delete_session(interaction.user.id, acc.game, acc.uid):
                count += 1

        await interaction.followup.send(
            f"🗑️ Đã xóa thành công {count} phiên đăng nhập Cookie khỏi hệ thống an toàn.",
            ephemeral=True,
        )

    @app_commands.command(name="run", description="Kích hoạt chạy ngay lập tức một tác vụ tự động")
    @app_commands.describe(tac_vu="Tác vụ muốn kích hoạt ngay")
    @app_commands.choices(
        tac_vu=[
            app_commands.Choice(name="Điểm danh ngay (Check-in)", value="checkin"),
            app_commands.Choice(name="Quét tìm Giftcode mới", value="giftcode_discovery"),
            app_commands.Choice(name="Đổi Giftcode ngay (Redeem)", value="giftcode_redeem"),
            app_commands.Choice(name="Nhiệm vụ Mimo", value="mimo"),
            app_commands.Choice(name="Điểm danh Đồng Hành", value="accompany"),
            app_commands.Choice(name="Quét Sự Kiện Web mới", value="events"),
            app_commands.Choice(name="Gia hạn token ngay (giữ đăng nhập)", value="token_refresh"),
        ]
    )
    async def auto_run_cmd(self, interaction: discord.Interaction, tac_vu: app_commands.Choice[str]):
        await interaction.response.defer(ephemeral=True)
        result = await automation_manager.run_manually(tac_vu.value)
        await interaction.followup.send(
            f"✦ **Kết quả thực thi {tac_vu.name}:**\n{result.get('message', 'Đã xử lý xong')}",
            ephemeral=True,
        )

    @app_commands.command(name="history", description="Xem lịch sử tự động điểm danh và đổi giftcode của tài khoản")
    @app_commands.describe(loai="Chọn loại lịch sử muốn xem")
    @app_commands.choices(
        loai=[
            app_commands.Choice(name="Tất cả (Điểm danh & Giftcode)", value="all"),
            app_commands.Choice(name="Lịch sử Điểm danh (Check-in)", value="checkin"),
            app_commands.Choice(name="Lịch sử Đổi Giftcode (Redeem)", value="redeem"),
        ]
    )
    async def auto_history(
        self, interaction: discord.Interaction, loai: Optional[app_commands.Choice[str]] = None
    ):
        await interaction.response.defer(ephemeral=True)
        accounts = await AccountRepository.get_accounts_by_user(interaction.user.id)
        if not accounts:
            await interaction.followup.send(
                "❌ Bạn chưa có tài khoản nào được liên kết. Hãy dùng `/account add` trước.",
                ephemeral=True,
            )
            return

        choice_val = loai.value if loai else "all"

        embed = discord.Embed(
            title="📜 Lịch Sử Tự Động Hóa (Check-in & Redeem)",
            description="Lịch sử các lần điểm danh và đổi mã quà tặng của tài khoản:",
            color=0x3498DB,
        )

        for acc in accounts:
            lines = []
            header = f"{acc.game.emoji} {acc.nickname or acc.uid} ({acc.game.display_name} - `{acc.uid}`)"

            # 1. Lịch sử điểm danh
            if choice_val in ("all", "checkin"):
                checkins = await CheckinRepository.get_history(acc.id, limit=5)
                if checkins:
                    lines.append("**📅 Điểm danh gần nhất:**")
                    for chk in checkins:
                        status_icon = "✅" if chk.status in ("SUCCESS", "ALREADY_CHECKED") else "❌"
                        r_hint = f" ({chk.reward_summary})" if chk.reward_summary else ""
                        lines.append(f"  {status_icon} `{chk.run_date}`: {chk.status}{r_hint}")
                else:
                    lines.append("**📅 Điểm danh:** *Chưa có nhật ký điểm danh*")

            # 2. Lịch sử đổi giftcode
            if choice_val in ("all", "redeem"):
                redeems = await GiftCodeRepository.get_redemption_history(acc.id, limit=5)
                if redeems:
                    lines.append("**🎁 Đổi Giftcode gần nhất:**")
                    for r in redeems:
                        status_icon = "✅" if r.status in ("SUCCESS", "ALREADY_REDEEMED") else "⚠️"
                        time_str = r.redeemed_at.strftime("%d/%m") if r.redeemed_at else ""
                        lines.append(f"  {status_icon} `{r.code}`: {r.status} {f'({time_str})' if time_str else ''}")
                else:
                    lines.append("**🎁 Giftcode:** *Chưa có lượt đổi mã nào*")

            embed.add_field(name=header, value="\n".join(lines) if lines else "*Không có dữ liệu*", inline=False)

        embed.set_footer(text="Dữ liệu được lưu trữ tự động an toàn trong hệ thống.")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="redeem_status", description="Xem trạng thái hệ thống Tự Động Đổi Mã (Auto Redeem)")
    async def auto_redeem_status(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        from app.config import settings
        from app.services.redeem_service import RedeemService

        overview = await RedeemService.get_redeem_status_overview()
        user_accounts = await AccountRepository.get_accounts_by_user(interaction.user.id)

        embed = discord.Embed(
            title="✦ Trạng Thái Hệ Thống Tự Động Đổi Mã (Auto Redeem)",
            description=f"Chế độ vận hành: **`{settings.AUTOMATION_MODE.upper()}`**",
            color=0x2ECC71 if settings.AUTOMATION_MODE != "dry-run" else 0xF39C12,
        )

        embed.add_field(
            name="📊 Thống Kê Chung",
            value=(
                f"• Tài khoản Genshin bật Auto: **{overview['genshin_opted_in']}**\n"
                f"• Tài khoản HSR bật Auto: **{overview['hsr_opted_in']}**\n"
                f"• Mã Genshin đang active: **{overview['active_codes_genshin_count']}**\n"
                f"• Mã HSR đang active: **{overview['active_codes_hsr_count']}**\n"
                f"• Hàng đợi bền vững (Queue): **{overview['pending_queue_count']}** jobs chờ xử lý"
            ),
            inline=False,
        )

        # Trạng thái tài khoản của chính user đang gọi lệnh
        if user_accounts:
            user_lines = []
            for acc in user_accounts:
                auto_set = await AutomationSettingsRepository.get_settings(interaction.user.id, acc.id)
                sess = await SessionRepository.get_session(interaction.user.id, acc.game, acc.uid)
                is_redeem = auto_set.redeem_enabled if auto_set else False

                # Khả năng đổi mã thực tế phụ thuộc vào cookie_token/stoken trong cookie,
                # KHÔNG phải trạng thái phiên điểm danh.
                redeem_ok = False
                redeem_detail = "Chưa có cookie"
                if sess:
                    try:
                        raw = await SessionRepository.get_decrypted_cookie(sess)
                        info = inspect_cookie_tokens(raw)
                        if info["redeem_durable"]:
                            redeem_ok = True
                            redeem_detail = "Sẵn sàng bền vững (`stoken` + `ltmid_v2`)"
                        elif info["has_cookie_token"]:
                            redeem_detail = "Tạm thời (thiếu `stoken` để tự gia hạn)"
                        elif info["has_stoken"] and not info.get("has_mid"):
                            redeem_detail = "Thiếu `ltmid_v2` để tự gia hạn"
                        else:
                            redeem_detail = "Thiếu token đổi mã"
                    except Exception:
                        redeem_detail = "Không đọc được cookie"

                if not is_redeem:
                    status_icon = "❌"
                    detail = "Đã tắt"
                elif redeem_ok:
                    status_icon = "✅"
                    detail = redeem_detail
                else:
                    status_icon = "⚠️"
                    detail = redeem_detail
                user_lines.append(
                    f"{status_icon} **{acc.nickname or acc.uid}** ({acc.game.display_name} - `{acc.uid}`): {detail}"
                )
            embed.add_field(name="👤 Tài Khoản Của Bạn", value="\n".join(user_lines), inline=False)

        embed.set_footer(text="Dùng /auto toggle để bật/tắt Auto Redeem | /auto verify để kiểm tra cookie đổi mã.")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(
        name="verify",
        description="Kiểm tra cookie có đổi được Giftcode hay không (KHÔNG đổi mã thật)",
    )
    async def auto_verify(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        from app.automation.client import HoyoClientAdapter

        accounts = await AccountRepository.get_accounts_by_user(interaction.user.id)
        if not accounts:
            await interaction.followup.send(
                "❌ Bạn chưa có tài khoản nào được liên kết. Hãy dùng `/account add` trước.",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title="🔎 Kiểm Tra Cookie Đổi Giftcode",
            description=(
                "Bot gửi một mã GIẢ tới API đổi mã (không đổi mã thật) để xác minh cookie của bạn "
                "có dùng được cho Giftcode hay không."
            ),
            color=0x3498DB,
        )

        for acc in accounts:
            header = f"{acc.game.emoji} {acc.nickname or acc.uid} (`{acc.uid}`)"
            sess = await SessionRepository.get_session(interaction.user.id, acc.game, acc.uid)
            if not sess:
                embed.add_field(name=header, value="❌ Chưa liên kết Cookie. Dùng `/auto session_add`.", inline=False)
                continue

            raw = await SessionRepository.get_decrypted_cookie(sess)
            info = inspect_cookie_tokens(raw)

            adapter = HoyoClientAdapter(
                game=acc.game,
                uid=acc.uid,
                raw_cookie=raw,
                discord_user_id=interaction.user.id,
                server_region=acc.server.value,
            )

            # Xác thực khả năng đổi mã trực tiếp bằng probe code
            auth_ok, status, msg = await adapter.verify_redeem_access()

            # Nếu chưa xác thực được nhưng có stoken + mid -> thử tự động gia hạn token và kiểm tra lại
            if not auth_ok and info.get("can_auto_refresh"):
                refreshed = await adapter.try_refresh_tokens()
                if refreshed:
                    auth_ok, status, msg = await adapter.verify_redeem_access()

            if auth_ok:
                verdict = "✅ **Cookie hợp lệ để đổi Giftcode.**"
                if info["redeem_durable"]:
                    verdict += " (có `stoken` → tự gia hạn bền vững)"
                else:
                    verdict += " ⚠️ Nhưng THIẾU `stoken` → token đổi mã sẽ hết hạn và bot không tự gia hạn được."
                api_detail = "Đã xác nhận quyền đổi mã với máy chủ HoYoverse."
            elif info.get("has_stoken") and not info.get("has_mid"):
                verdict = (
                    "❌ **Cookie có `stoken` nhưng thiếu `ltmid_v2` (hoặc `mid`), bot không thể tự cấp lại token đổi mã mới.**\n"
                    "👉 Hãy đăng nhập lại bằng `/auto login` hoặc dán cookie qua `/auto session_add`."
                )
                api_detail = f"`{status}` — {msg[:180]}"
            elif not info.get("has_cookie_token") and not info.get("has_stoken"):
                verdict = (
                    "❌ **Cookie thiếu hoàn toàn token đổi mã (`cookie_token`) và `stoken`.**\n"
                    "👉 Hãy đăng nhập lại bằng `/auto login` hoặc dán cookie qua `/auto session_add`."
                )
                api_detail = f"`{status}` — {msg[:180]}"
            elif info.get("redeem_durable"):
                verdict = (
                    f"❌ **Không xác thực được đổi mã dù có `stoken`.** ({msg})\n"
                    "👉 Phiên đăng nhập có thể đã bị đăng xuất hoặc thu hồi. Hãy đăng nhập lại bằng `/auto login`."
                )
                api_detail = f"`{status}` — {msg[:180]}"
            else:
                verdict = (
                    f"❌ **Token đổi mã (`cookie_token`) đã HẾT HẠN hoặc bị thu hồi.** ({msg})\n"
                    "👉 Hãy đăng nhập lại bằng `/auto login` hoặc dán cookie mới kèm `stoken` để bot tự gia hạn vĩnh viễn."
                )
                api_detail = f"`{status}` — {msg[:180]}"

            value = (
                f"{verdict}\n"
                f"├─ Token đổi mã: `cookie_token`={'có' if info['has_cookie_token'] else 'không'} | "
                f"`stoken`={'có' if info['has_stoken'] else 'không'} | `mid`={'có' if info.get('has_mid') else 'không'}\n"
                f"└─ Xác thực API: {api_detail}"
            )
            embed.add_field(name=header, value=value, inline=False)

        embed.set_footer(
            text="Cookie có 'stoken' sẽ tự gia hạn vĩnh viễn; không có thì cần dán lại cookie mới khi token hết hạn."
        )
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(AutoCommands(bot))

