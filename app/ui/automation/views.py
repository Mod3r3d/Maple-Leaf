"""UI Views và Modals tương tác cho tính năng Automation v2."""

import asyncio
import time

import discord
import genshin
from discord.ui import Button, Modal, TextInput, View, button
from loguru import logger

from app.automation.login import (
    LoginError,
    LoginNeedsCaptcha,
    LoginNeedsEmailCode,
    LoginTimeout,
    login_with_app,
)
from app.automation.manager import automation_manager
from app.db.repositories.accounts import AccountRepository
from app.db.repositories.automation import (
    AutomationSettingsRepository,
    SessionRepository,
)
from app.games.enums import GameType
from app.security.encryption import inspect_cookie_tokens

# Giới hạn số lần thử đăng nhập để tránh dò mật khẩu qua Discord.
_LOGIN_ATTEMPTS: dict[int, list[float]] = {}
LOGIN_RATE_LIMIT = 3
LOGIN_RATE_WINDOW_SECONDS = 600


def _is_login_rate_limited(discord_user_id: int) -> bool:
    """Trả về True nếu người dùng đã thử quá nhiều lần trong cửa sổ thời gian."""
    now = time.monotonic()
    attempts = [t for t in _LOGIN_ATTEMPTS.get(discord_user_id, []) if now - t < LOGIN_RATE_WINDOW_SECONDS]
    if len(attempts) >= LOGIN_RATE_LIMIT:
        _LOGIN_ATTEMPTS[discord_user_id] = attempts
        return True

    attempts.append(now)
    _LOGIN_ATTEMPTS[discord_user_id] = attempts
    return False


class CookieInputModal(Modal, title="Thêm / Cập Nhật Cookie HoYoLAB"):
    # LƯU Ý: label của TextInput bị Discord giới hạn 1-45 ký tự.
    cookie_input = TextInput(
        label="Cookie HoYoLAB (kèm stoken đổi mã)",
        style=discord.TextStyle.paragraph,
        placeholder="ltuid_v2=...; ltmid_v2=...; ltoken_v2=...; cookie_token_v2=...; stoken_v2=...;",
        required=True,
        min_length=20,
        max_length=2000,
    )

    def __init__(
        self,
        discord_user_id: int,
        target_scope: str = "all",
        account_id: int | None = None,
        game: GameType | None = None,
        uid: int | None = None,
    ):
        super().__init__()
        self.discord_user_id = discord_user_id
        self.target_scope = target_scope
        self.account_id = account_id
        self.game = game
        self.uid = uid

    async def on_submit(self, interaction: discord.Interaction):
        raw_cookie = self.cookie_input.value.strip()

        user_accounts = await AccountRepository.get_accounts_by_user(self.discord_user_id)
        if not user_accounts:
            await interaction.response.send_message("❌ Bạn chưa có tài khoản nào được liên kết.", ephemeral=True)
            return

        targets = []
        for acc in user_accounts:
            if self.target_scope == "all":
                targets.append(acc)
            elif self.target_scope == acc.game.value:
                targets.append(acc)
            elif self.uid and acc.uid == self.uid:
                targets.append(acc)

        if not targets:
            targets = user_accounts

        saved_names = []
        for acc in targets:
            await SessionRepository.save_session(
                discord_user_id=self.discord_user_id,
                game=acc.game,
                uid=acc.uid,
                raw_cookie=raw_cookie,
            )
            await AutomationSettingsRepository.get_or_create(acc.id, self.discord_user_id)
            saved_names.append(f"{acc.game.emoji} **{acc.game.display_name}** (`{acc.uid}`)")

        analysis = inspect_cookie_tokens(raw_cookie)

        if analysis.get("has_checkin"):
            checkin_note = "📅 **Điểm danh hàng ngày:** Đã sẵn sàng."
        else:
            missing_chk = ", ".join(f"`{t}`" for t in analysis.get("missing_for_checkin", []))
            checkin_note = f"⚠️ **Điểm danh hàng ngày:** Chưa đủ token (Thiếu: {missing_chk})."

        if analysis.get("redeem_durable"):
            redeem_note = (
                "⚡ **Tự Động Gia Hạn & Đổi Giftcode:** Đã phát hiện đủ `stoken` và `ltmid_v2`! "
                "Bot sẽ tự động làm mới token đổi mã (`cookie_token`) vô thời hạn, Auto Redeem luôn sẵn sàng."
            )
        elif analysis.get("has_cookie_token"):
            redeem_note = (
                "🎁 **Đổi Giftcode Tạm Thời:** Đã phát hiện `cookie_token`, nhưng **thiếu `stoken` / `ltmid_v2`**. "
                "`cookie_token` chỉ có hiệu lực ngắn hạn — khi hết hạn, đổi Giftcode sẽ dừng lại và bot không thể "
                "tự gia hạn. Bạn nên thêm lại cookie đầy đủ (kèm `stoken` & `ltmid_v2`) để đổi mã hoạt động lâu dài."
            )
        elif analysis.get("has_stoken") and not analysis.get("has_mid"):
            redeem_note = (
                "⚠️ **Thiếu Mã Định Danh ltmid_v2:** Cookie có `stoken` nhưng thiếu `ltmid_v2` (hoặc `mid`). "
                "HoYoLAB yêu cầu thông tin này để cấp lại token đổi mã. Điểm danh vẫn dùng được, nhưng đổi mã chưa thể gia hạn."
            )
        else:
            redeem_note = (
                "⚠️ **Chưa Có Token Đổi Mã:** Cookie hiện tại **thiếu token đổi mã**. "
                "HoYoLAB yêu cầu `cookie_token` hoặc bộ (`stoken` + `ltmid_v2`). Bạn hãy dùng `/auto session_add` "
                "để cập nhật lại cookie đầy đủ khi muốn dùng tính năng đổi mã."
            )

        acc_list_str = "\n• " + "\n• ".join(saved_names)

        embed = discord.Embed(
            title="🔒 Đã Lưu & Đồng Bộ Cookie Thành Công!",
            description=(
                f"Đã lưu và tự động gộp Cookie cho các tài khoản:{acc_list_str}\n\n"
                f"{checkin_note}\n"
                f"{redeem_note}\n\n"
                f"💡 *Gợi ý:* Bạn có thể gõ `/auto run tac_vu: Điểm danh ngay` hoặc `/auto run tac_vu: Đổi Giftcode ngay` để kiểm tra kết quả."
            ),
            color=0x2ECC71,
        )
        embed.set_footer(text="Hệ thống luôn mã hóa bảo mật toàn bộ dữ liệu Cookie.")
        await interaction.response.send_message(embed=embed, ephemeral=True)


class EmailOTPModal(Modal, title="Xác Minh Email HoYoLAB"):
    """Cửa sổ Modal nhập mã xác minh OTP 6 số từ Email ngay trên Discord."""

    code = TextInput(
        label="Mã xác nhận 6 số từ Email",
        placeholder="Nhập 6 chữ số gửi từ HoYoverse...",
        min_length=6,
        max_length=6,
        required=True,
    )

    def __init__(self, future: asyncio.Future):
        super().__init__()
        self.future = future

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        if not self.future.done():
            self.future.set_result(self.code.value.strip())
        await interaction.followup.send(
            "⏳ Đã gửi mã OTP tới máy chủ HoYoLAB, vui lòng đợi hoàn tất đăng nhập...",
            ephemeral=True,
        )


class EmailOTPActionView(View):
    """View chứa nút bấm kích hoạt Modal nhập OTP an toàn."""

    def __init__(self, future: asyncio.Future, user_id: int):
        super().__init__(timeout=180.0)
        self.future = future
        self.user_id = user_id

    @button(
        label="Nhập Mã Xác Minh (OTP)",
        style=discord.ButtonStyle.primary,
        emoji="🔢",
    )
    async def enter_otp_btn(self, interaction: discord.Interaction, btn: Button):  # noqa: ARG002
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "❌ Nút này chỉ dành cho người thực hiện lệnh đăng nhập.",
                ephemeral=True,
            )
            return

        modal = EmailOTPModal(future=self.future)
        await interaction.response.send_modal(modal)

    async def on_timeout(self):
        if not self.future.done():
            self.future.set_exception(LoginTimeout("Đã hết thời gian chờ nhập mã xác minh OTP (3 phút)."))


class CaptchaLinkView(View):
    """View chứa nút Link trực tiếp mở trang giải Captcha trên trình duyệt."""

    def __init__(self, captcha_url: str):
        super().__init__(timeout=180.0)
        self.add_item(
            Button(
                label="Mở Trang Giải Captcha",
                url=captcha_url,
                style=discord.ButtonStyle.link,
                emoji="🧩",
            )
        )


class LoginModal(Modal, title="Đăng Nhập HoYoLAB"):
    """Đăng nhập bằng email + mật khẩu để bot tự lấy cookie đầy đủ (có `stoken`).

    Mật khẩu chỉ dùng một lần, không lưu vào CSDL và không ghi log.
    """

    email = TextInput(
        label="Email / tên đăng nhập",
        placeholder="email@example.com",
        required=True,
        max_length=100,
    )
    password = TextInput(
        label="Mật khẩu (không lưu lại)",
        placeholder="Mật khẩu hiện rõ khi gõ — tránh dùng nơi có người khác nhìn màn hình",
        required=True,
        max_length=128,
    )

    def __init__(self, discord_user_id: int):
        super().__init__()
        self.discord_user_id = discord_user_id

    async def on_submit(self, interaction: discord.Interaction):
        # Đăng nhập có thể mất vài giây → phải defer trước khi gọi mạng.
        await interaction.response.defer(ephemeral=True, thinking=True)

        if _is_login_rate_limited(self.discord_user_id):
            await interaction.followup.send(
                "⏳ Bạn đã thử đăng nhập quá nhiều lần. Vui lòng thử lại sau 10 phút.",
                ephemeral=True,
            )
            return

        accounts = await AccountRepository.get_accounts_by_user(self.discord_user_id)
        if not accounts:
            await interaction.followup.send(
                "❌ Bạn chưa có tài khoản game nào. Hãy dùng `/account add` trước.",
                ephemeral=True,
            )
            return

        email = self.email.value.strip()
        password = self.password.value

        async def on_captcha(session_id: str, captcha_url: str):
            embed = discord.Embed(
                title="🧩 HoYoLAB Yêu Cầu Giải Captcha",
                description=(
                    "HoYoLAB phát hiện đăng nhập mới và yêu cầu xác minh thanh trượt chống bot.\n\n"
                    "👉 **Bấm vào nút bên dưới để mở trang web giải Captcha** (trên điện thoại hoặc máy tính).\n\n"
                    "*(Sau khi bạn kéo khớp hình ảnh xong, Bot sẽ tự động tiếp tục đăng nhập)*"
                ),
                color=0xF39C12,
            )
            embed.set_footer(text="Cổng giải Captcha an toàn • Tự động tiếp tục sau khi kéo khớp hình")
            await interaction.followup.send(
                embed=embed,
                view=CaptchaLinkView(captcha_url),
                ephemeral=True,
            )

        async def on_captcha_solved():
            await interaction.followup.send(
                "✅ **Đã xác minh Captcha thành công!** Đang tiếp tục xử lý thông tin tài khoản...",
                ephemeral=True,
            )

        async def on_otp() -> str:
            future: asyncio.Future[str] = asyncio.get_running_loop().create_future()
            embed = discord.Embed(
                title="📩 HoYoLAB Đã Gửi Mã Xác Minh Email (OTP)",
                description=(
                    f"HoYoverse vừa gửi mã xác nhận 6 số đến email **{email}**.\n\n"
                    "👉 **Hãy mở email (lấy thư mới nhất) và nhấn nút bên dưới để nhập mã:**"
                ),
                color=0x3498DB,
            )
            embed.set_footer(text="Thời gian chờ: 3 phút • Vui lòng nhập đúng mã 6 số")
            view = EmailOTPActionView(future=future, user_id=self.discord_user_id)
            await interaction.followup.send(
                embed=embed,
                view=view,
                ephemeral=True,
            )
            return await asyncio.wait_for(future, timeout=180.0)

        try:
            cookies = await login_with_app(
                email,
                password,
                captcha_callback=on_captcha,
                captcha_solved_callback=on_captcha_solved,
                otp_callback=on_otp,
            )
        except LoginNeedsCaptcha as exc:
            await interaction.followup.send(f"⚠️ {exc}", ephemeral=True)
            return
        except LoginNeedsEmailCode as exc:
            await interaction.followup.send(f"⚠️ {exc}", ephemeral=True)
            return
        except LoginTimeout as exc:
            await interaction.followup.send(f"⏱️ {exc}", ephemeral=True)
            return
        except genshin.errors.AccountLoginFail:
            await interaction.followup.send(
                "❌ Sai mật khẩu. Nếu bạn đăng nhập HoYoLAB bằng Google/Facebook/Apple, "
                "hãy đặt mật khẩu tại `account.hoyolab.com` → Account Security trước.",
                ephemeral=True,
            )
            return
        except genshin.errors.AccountDoesNotExist:
            await interaction.followup.send("❌ Email/tên đăng nhập không tồn tại.", ephemeral=True)
            return
        except (genshin.errors.VerificationCodeRateLimited, genshin.errors.OTPRateLimited):
            await interaction.followup.send(
                "⏳ Bạn đã yêu cầu mã xác minh quá nhiều lần. Hãy đợi vài phút rồi thử lại sau.", ephemeral=True
            )
            return
        except genshin.errors.GeetestFailed:
            await interaction.followup.send(
                "❌ Xác thực Captcha không thành công hoặc đã hết hạn từ phía máy chủ HoYoLAB. "
                "Vui lòng thử đăng nhập lại và kéo khớp hình ảnh cẩn thận.",
                ephemeral=True,
            )
            return
        except genshin.errors.AccountHasLocked:
            await interaction.followup.send(
                "❌ Tài khoản đã bị tạm khóa do nhập sai mật khẩu quá số lần cho phép. "
                "Vui lòng đợi 20 phút rồi thử lại.",
                ephemeral=True,
            )
            return
        except genshin.errors.WrongOTP:
            await interaction.followup.send(
                "❌ Mã xác minh (OTP) không chính xác hoặc đã hết hạn. Hãy thử lại.",
                ephemeral=True,
            )
            return
        except genshin.errors.GenshinException as exc:
            logger.exception(f"HoYoLAB API error cho user {self.discord_user_id}: {exc}")
            ret = getattr(exc, "retcode", "ERR")
            msg = getattr(exc, "msg", str(exc))
            await interaction.followup.send(
                f"❌ Lỗi từ HoYoLAB ([{ret}]: {msg}). "
                "Hãy thử lại, hoặc dùng `scripts/get_full_cookie.py` trên máy tính.",
                ephemeral=True,
            )
            return
        except LoginError as exc:
            await interaction.followup.send(f"⚠️ {exc}", ephemeral=True)
            return
        except Exception as exc:  # noqa: BLE001
            # Không log email/mật khẩu — chỉ log loại lỗi.
            logger.exception(f"Đăng nhập HoYoLAB thất bại cho user {self.discord_user_id}: {type(exc).__name__}")
            await interaction.followup.send(
                f"❌ Đăng nhập thất bại ({type(exc).__name__}: {str(exc)[:120]}). "
                "Hãy thử lại, hoặc dùng `scripts/get_full_cookie.py` trên máy tính.",
                ephemeral=True,
            )
            return
        finally:
            # Xoá mật khẩu khỏi bộ nhớ sớm nhất có thể.
            password = ""

        raw_cookie = "; ".join(f"{k}={v}" for k, v in cookies.items() if v)
        saved_names = []
        for acc in accounts:
            await SessionRepository.save_session(
                discord_user_id=self.discord_user_id,
                game=acc.game,
                uid=acc.uid,
                raw_cookie=raw_cookie,
            )
            await AutomationSettingsRepository.get_or_create(acc.id, self.discord_user_id)
            saved_names.append(f"{acc.game.emoji} **{acc.game.display_name}** (`{acc.uid}`)")

        analysis = inspect_cookie_tokens(raw_cookie)
        embed = discord.Embed(
            title="✅ Đăng Nhập HoYoLAB Thành Công",
            description=(
                "Đã lấy cookie đầy đủ (có `stoken`) và lưu cho:\n• "
                + "\n• ".join(saved_names)
                + "\n\n⚡ Bot sẽ **tự gia hạn token 12 giờ/lần** — bạn không phải đăng nhập lại.\n"
                "👉 Chạy `/auto verify` để kiểm tra khả năng đổi Giftcode."
            ),
            color=0x2ECC71,
        )
        if not analysis.get("redeem_durable"):
            embed.add_field(
                name="⚠️ Chưa đủ bộ tự gia hạn",
                value=(
                    "Không thấy đủ `stoken` + `ltmid_v2`. Điểm danh vẫn dùng được, nhưng Đổi Giftcode "
                    "có thể hết hạn. Hãy dùng `scripts/get_full_cookie.py` để lấy cookie đầy đủ."
                ),
                inline=False,
            )
        embed.set_footer(text="Mật khẩu chỉ dùng một lần và không được lưu lại.")
        await interaction.followup.send(embed=embed, ephemeral=True)


class AutomationDashboardView(View):
    def __init__(self, author_id: int, accounts_data: list, timeout: float = 120.0):
        super().__init__(timeout=timeout)
        self.author_id = author_id
        self.accounts_data = accounts_data  # list of (AccountModel, AutomationSettingsModel, SessionModel | None)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ Bạn không có quyền thao tác trên menu này.", ephemeral=True)
            return False
        return True

    @button(label="✦ Điểm Danh Ngay", style=discord.ButtonStyle.primary, row=0)
    async def run_checkin_now(self, interaction: discord.Interaction, btn: Button):
        await interaction.response.defer(ephemeral=True)
        res = await automation_manager.run_manually("checkin")
        await interaction.followup.send(f"✦ **Kết quả Điểm danh:** {res.get('message', 'Đã thực thi')}", ephemeral=True)

    @button(label="◈ Đổi Giftcode Ngay", style=discord.ButtonStyle.primary, row=0)
    async def run_redeem_now(self, interaction: discord.Interaction, btn: Button):
        await interaction.response.defer(ephemeral=True)
        res = await automation_manager.run_manually("giftcode_redeem")
        await interaction.followup.send(f"◈ **Kết quả Đổi Mã:** {res.get('message', 'Đã thực thi')}", ephemeral=True)

    @button(label="Thêm / Cập Nhật Cookie", style=discord.ButtonStyle.secondary, emoji="⚙️", row=1)
    async def add_cookie_btn(self, interaction: discord.Interaction, btn: Button):
        if not self.accounts_data:
            await interaction.response.send_message("Bạn chưa có tài khoản nào. Hãy dùng `/account add` trước.", ephemeral=True)
            return

        modal = CookieInputModal(
            discord_user_id=interaction.user.id,
            target_scope="all",
        )
        await interaction.response.send_modal(modal)

    @button(label="Xem Cookie", style=discord.ButtonStyle.secondary, emoji="👁️", row=1)
    async def view_cookie_btn(self, interaction: discord.Interaction, btn: Button):
        await interaction.response.defer(ephemeral=True)
        embed = await build_cookie_view_embed(self.author_id, full=False)
        await interaction.followup.send(embed=embed, ephemeral=True)

    @button(label="Xóa Cookie Phiên", style=discord.ButtonStyle.danger, emoji="🗑️", row=1)
    async def delete_cookie_btn(self, interaction: discord.Interaction, btn: Button):
        if not self.accounts_data:
            await interaction.response.send_message("Bạn chưa có tài khoản nào.", ephemeral=True)
            return

        acc, _, _ = self.accounts_data[0]
        deleted = await SessionRepository.delete_session(interaction.user.id, acc.game, acc.uid)
        if deleted:
            await interaction.response.send_message(f"🗑️ Đã xóa phiên đăng nhập của tài khoản UID `{acc.uid}`.", ephemeral=True)
        else:
            await interaction.response.send_message("Tài khoản này chưa lưu Cookie nào.", ephemeral=True)


async def build_cookie_view_embed(discord_user_id: int, full: bool = False) -> discord.Embed:
    """Tạo Embed hiển thị thông tin và phân tích các Token trong Cookie hiện tại."""
    accounts = await AccountRepository.get_accounts_by_user(discord_user_id)
    if not accounts:
        return discord.Embed(
            title="🔒 Thông Tin Cookie HoYoLAB",
            description="❌ Bạn chưa liên kết tài khoản game nào. Hãy dùng lệnh `/account add` trước.",
            color=0xE74C3C,
        )

    embed = discord.Embed(
        title="🔒 Phiên Đăng Nhập & Cookie Hiện Tại",
        description=(
            "Chi tiết các mã xác thực (tokens) được lưu trữ an toàn trong hệ thống:\n"
            "*(Dữ liệu được mã hóa bảo mật bằng AES đối xứng)*"
        ),
        color=0x3498DB,
    )

    found_any = False
    for acc in accounts:
        sess = await SessionRepository.get_session(discord_user_id, acc.game, acc.uid)
        acc_title = f"{acc.game.emoji} {acc.nickname or acc.uid} ({acc.game.display_name} - `{acc.uid}`)"

        if not sess:
            embed.add_field(
                name=acc_title,
                value="❌ **Chưa liên kết Cookie.** Dùng `/auto session_add` để thêm.",
                inline=False,
            )
            continue

        found_any = True
        raw_cookie = await SessionRepository.get_decrypted_cookie(sess)
        analysis = inspect_cookie_tokens(raw_cookie, full=full)

        if analysis["has_checkin"]:
            checkin_badge = "✅ Sẵn sàng (`ltuid_v2`, `ltoken_v2`)"
        else:
            missing_chk = ", ".join(f"`{t}`" for t in analysis.get("missing_for_checkin", [])) or "`ltoken_v2`"
            checkin_badge = f"❌ Chưa đủ token (Thiếu: {missing_chk})"

        if analysis.get("redeem_durable"):
            redeem_badge = "⚡ Bền vững (Có `stoken` + `ltmid_v2` → Bot tự gia hạn `cookie_token` vô thời hạn)"
        elif analysis.get("has_cookie_token"):
            redeem_badge = "⚠️ Tạm thời (Có `cookie_token_v2` nhưng THIẾU `stoken`/`ltmid_v2` để tự gia hạn)"
        elif analysis.get("has_stoken") and not analysis.get("has_mid"):
            redeem_badge = "❌ Thiếu `ltmid_v2` (Có `stoken` nhưng thiếu mã định danh `ltmid_v2` để tự gia hạn)"
        else:
            redeem_badge = "❌ Chưa thể đổi mã (Thiếu `cookie_token_v2` và bộ `stoken` + `ltmid_v2`)"

        token_lines = []
        key_priority = ["ltuid_v2", "ltmid_v2", "ltoken_v2", "stoken", "stoken_v2", "account_id_v2", "cookie_token_v2", "cookie_token", "account_mid_v2"]
        for key in key_priority:
            if key in analysis["tokens"]:
                val = analysis["tokens"][key]
                if not full and len(val) > 16:
                    val = f"`{val[:6]}...{val[-6:]}` (Dài: {len(analysis['tokens'][key])})"
                else:
                    val = f"`{val}`"
                token_lines.append(f"• `{key}`: {val}")

        token_summary = "\n".join(token_lines) if token_lines else "• Không phát hiện token chuẩn"

        cookie_str = analysis["display_str"]
        if full:
            field_value = (
                f"**Trạng thái phiên:** `{sess.session_status}`\n"
                f"├─ Điểm danh (Check-in): {checkin_badge}\n"
                f"└─ Đổi Giftcode (Redeem): {redeem_badge}\n\n"
                f"**Chuỗi Cookie đầy đủ để sao chép:**\n"
                f"```text\n{raw_cookie}\n```"
            )
        else:
            field_value = (
                f"**Trạng thái phiên:** `{sess.session_status}`\n"
                f"├─ Điểm danh (Check-in): {checkin_badge}\n"
                f"└─ Đổi Giftcode (Redeem): {redeem_badge}\n\n"
                f"**Các Token đã lưu:**\n{token_summary}\n\n"
                f"**Chuỗi Cookie (Đã che bảo mật):**\n"
                f"```env\n{cookie_str}\n```"
            )
        embed.add_field(name=acc_title, value=field_value, inline=False)

    if not found_any:
        embed.set_footer(text="Bạn chưa lưu Cookie nào. Hãy dùng lệnh /auto session_add để thêm.")
    elif not full:
        embed.set_footer(text="💡 Mẹo: Dùng /auto session_view hien_thi_day_du:Đúng nếu bạn muốn sao chép toàn bộ chuỗi.")
    else:
        embed.set_footer(text="⚠️ Cảnh báo bảo mật: Tuyệt đối không chia sẻ chuỗi Cookie cho bất kỳ ai.")

    return embed
