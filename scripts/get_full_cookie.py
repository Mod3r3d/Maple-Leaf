"""Lấy cookie HoYoLAB ĐẦY ĐỦ (bao gồm `stoken`) để tính năng Đổi Giftcode chạy bền vững.

Vì sao cần script này?
    - API đổi Giftcode cần `cookie_token`, nhưng token này chỉ sống ~2 giờ.
    - Muốn bot TỰ gia hạn thì cookie phải có `stoken` (~30 ngày).
    - `stoken` KHÔNG có trong cookie trình duyệt và KHÔNG được trả về bởi đăng nhập web.
      Chỉ endpoint đăng nhập **app HoYoLAB** mới trả về `stoken` — script này dùng đúng nó.

Cách chạy (trên máy đang chạy bot):
    .venv/Scripts/python.exe scripts/get_full_cookie.py

    Script tự nhận diện Discord User ID nếu CSDL chỉ có một người dùng.
    Nếu có nhiều người, chỉ định rõ:
    .venv/Scripts/python.exe scripts/get_full_cookie.py --discord-user-id <ID_DISCORD>

Tuỳ chọn:
    --game {all,genshin,hsr}   Chỉ áp dụng cho một game (mặc định: all)
    --uid <UID>                Chỉ áp dụng cho một tài khoản cụ thể
    --no-save                  Chỉ in cookie ra màn hình, không ghi vào CSDL
    --print-cookie             In đầy đủ chuỗi cookie (mặc định ẩn để tránh lộ token)

An toàn:
    - Mật khẩu được nhập ẩn (getpass) và KHÔNG bao giờ được lưu lại.
    - Chỉ cookie kết quả (đã mã hoá) được ghi vào CSDL của bot.
"""

import argparse
import asyncio
import getpass
import sys
import uuid
from pathlib import Path

# Cho phép import các module của dự án khi chạy trực tiếp từ thư mục gốc
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import genshin  # noqa: E402
from loguru import logger  # noqa: E402

from app.automation.login import patch_genshin_login  # noqa: E402
from app.config import settings  # noqa: E402
from app.db.database import db  # noqa: E402
from app.db.repositories.accounts import AccountRepository  # noqa: E402
from app.db.repositories.automation import SessionRepository  # noqa: E402

patch_genshin_login()

# Lưu device_id cố định để các lần đăng nhập sau ít bị hỏi mã xác minh email hơn.
DEVICE_ID_FILE = settings.DATA_DIR / ".app_device_id"


def get_or_create_device_id() -> str:
    """Đọc hoặc tạo mới device_id cố định cho việc đăng nhập app."""
    settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
    if DEVICE_ID_FILE.exists():
        value = DEVICE_ID_FILE.read_text(encoding="utf-8").strip()
        if value:
            return value

    value = str(uuid.uuid4())
    DEVICE_ID_FILE.write_text(value, encoding="utf-8")
    logger.info(f"Đã tạo device_id mới và lưu tại {DEVICE_ID_FILE}")
    return value


def build_cookie_string(cookies: dict) -> str:
    """Ghép dict cookie thành chuỗi 'k=v; k=v; ...'."""
    return "; ".join(f"{k}={v}" for k, v in cookies.items() if v)


async def login_and_build_cookie(account: str, password: str) -> str:
    """Đăng nhập qua endpoint app HoYoLAB và trả về chuỗi cookie đầy đủ (có stoken)."""
    device_id = get_or_create_device_id()
    client = genshin.Client()

    print("\nĐang đăng nhập qua endpoint app HoYoLAB (có thể hiện captcha/mã xác minh)...")
    result = await client.login_with_app_password(account, password, device_id=device_id)

    cookies: dict = dict(result.to_dict())
    print("✅ Đăng nhập thành công — đã nhận được `stoken`.")

    # Lấy thêm ltoken_v2 + cookie_token_v2 từ stoken để cookie dùng được ngay.
    try:
        refreshed = await genshin.fetch_cookie_with_stoken_v2(cookies, token_types=[2, 4])
        cookies.update(refreshed)
        print("✅ Đã lấy thêm `ltoken_v2` và `cookie_token_v2`.")
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Chưa lấy được ltoken_v2/cookie_token_v2 ngay (bot sẽ tự làm mới sau): {e}")

    return build_cookie_string(cookies)


async def resolve_discord_user_id(provided: int | None) -> int | None:
    """Xác định Discord user ID: dùng tham số, hoặc tự nhận diện nếu CSDL chỉ có 1 người."""
    if provided:
        return provided

    await db.connect()
    try:
        async with db.get_connection() as conn:
            cursor = await conn.execute(
                "SELECT DISTINCT discord_user_id FROM accounts ORDER BY discord_user_id"
            )
            rows = [r["discord_user_id"] for r in await cursor.fetchall()]
    finally:
        await db.close()

    if not rows:
        logger.error(
            "CSDL chưa có tài khoản game nào. Hãy dùng /account add trong Discord trước, "
            "rồi chạy lại script này."
        )
        return None

    if len(rows) == 1:
        print(f"ℹ️  Tự nhận diện Discord User ID: {rows[0]}")
        return rows[0]

    print("CSDL có nhiều người dùng:")
    for index, user_id in enumerate(rows, start=1):
        print(f"  {index}. {user_id}")

    choice = input("Chọn số thứ tự (hoặc nhập trực tiếp Discord User ID): ").strip()
    if choice.isdigit() and 1 <= int(choice) <= len(rows):
        return rows[int(choice) - 1]
    if choice.isdigit():
        return int(choice)

    logger.error("Lựa chọn không hợp lệ.")
    return None


async def save_to_database(discord_user_id: int, cookie_str: str, game: str, uid: int | None) -> int:
    """Ghi cookie vào bảng sessions của bot. Trả về số tài khoản đã cập nhật."""
    await db.connect()
    try:
        accounts = await AccountRepository.get_accounts_by_user(discord_user_id)
        if not accounts:
            logger.error(
                f"Không tìm thấy tài khoản nào của Discord user {discord_user_id}. "
                f"Hãy dùng /account add trong Discord trước."
            )
            return 0

        targets = []
        for acc in accounts:
            if game != "all" and acc.game.value != game:
                continue
            if uid and acc.uid != uid:
                continue
            targets.append(acc)

        if not targets:
            logger.error("Không có tài khoản nào khớp với bộ lọc --game/--uid.")
            return 0

        for acc in targets:
            await SessionRepository.save_session(
                discord_user_id=discord_user_id,
                game=acc.game,
                uid=acc.uid,
                raw_cookie=cookie_str,
            )
            logger.info(f"Đã cập nhật cookie cho {acc.game.value} UID {acc.uid}.")

        return len(targets)
    finally:
        await db.close()


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Lấy cookie HoYoLAB đầy đủ (có stoken) để Đổi Giftcode chạy bền vững."
    )
    parser.add_argument(
        "--discord-user-id",
        type=int,
        default=None,
        help="ID Discord của bạn (bỏ trống nếu CSDL chỉ có một người dùng — script tự nhận diện)",
    )
    parser.add_argument("--game", choices=["all", "genshin", "hsr"], default="all", help="Áp dụng cho game nào")
    parser.add_argument("--uid", type=int, default=None, help="Chỉ áp dụng cho UID cụ thể")
    parser.add_argument("--no-save", action="store_true", help="Chỉ in cookie, không ghi vào CSDL")
    parser.add_argument(
        "--print-cookie",
        action="store_true",
        help="In đầy đủ chuỗi cookie ra màn hình (mặc định: ẩn để tránh lộ token)",
    )
    args = parser.parse_args()

    print("=" * 64)
    print(" LẤY COOKIE HOYOLAB ĐẦY ĐỦ (CÓ STOKEN) — Maple Leaf")
    print("=" * 64)
    print("Mật khẩu chỉ dùng để đăng nhập một lần và KHÔNG được lưu lại.\n")

    discord_user_id = None
    if not args.no_save:
        discord_user_id = await resolve_discord_user_id(args.discord_user_id)
        if discord_user_id is None:
            return
        print()

    account = input("Email / tên đăng nhập HoYoLAB: ").strip()
    if not account:
        logger.error("Chưa nhập email/tên đăng nhập.")
        return
    password = getpass.getpass("Mật khẩu HoYoLAB (ẩn khi gõ): ")
    if not password:
        logger.error("Chưa nhập mật khẩu.")
        return

    try:
        cookie_str = await login_and_build_cookie(account, password)
    except genshin.errors.AccountDoesNotExist:
        logger.error("Email/tên đăng nhập không tồn tại. Kiểm tra lại.")
        return
    except genshin.errors.AccountLoginFail:
        logger.error("Sai mật khẩu. Kiểm tra lại.")
        return
    except (genshin.errors.VerificationCodeRateLimited, genshin.errors.OTPRateLimited):
        logger.error("Đã yêu cầu mã xác minh quá nhiều lần. Hãy đợi một vài phút rồi thử lại sau.")
        return
    except genshin.errors.WrongOTP:
        logger.error("❌ Mã xác minh (OTP) không chính xác hoặc đã hết hạn. Hãy kiểm tra email mới nhất được gửi từ HoYoverse và chạy lại script.")
        return
    except Exception as e:  # noqa: BLE001
        logger.exception(f"Đăng nhập thất bại: {e}")
        return

    print("\n" + "-" * 64)
    if args.print_cookie or args.no_save:
        print("CHUỖI COOKIE ĐẦY ĐỦ (dán vào /auto session_add nếu muốn dùng thủ công):")
        print("-" * 64)
        print(cookie_str)
    else:
        print("Đã nhận cookie đầy đủ (có `stoken`).")
        print("Chuỗi cookie được ẩn để tránh lộ token — thêm `--print-cookie` nếu bạn cần xem.")
    print("-" * 64)
    print("⚠️  TUYỆT ĐỐI không chia sẻ cookie cho bất kỳ ai.\n")

    if args.no_save:
        print("Đã bỏ qua bước ghi CSDL (--no-save).")
        return

    count = await save_to_database(discord_user_id, cookie_str, args.game, args.uid)
    if count:
        print(f"✅ Đã lưu cookie (kèm stoken) vào CSDL cho {count} tài khoản.")
        print("👉 Vào Discord chạy `/auto verify` để kiểm tra, rồi `/auto run tac_vu: Đổi Giftcode ngay`.")
    else:
        print("⚠️  Chưa ghi được vào CSDL. Bạn vẫn có thể dán chuỗi cookie ở trên vào `/auto session_add`.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nĐã huỷ.")
