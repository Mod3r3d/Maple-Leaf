"""Tiện ích sao chép chuỗi Cookie đầy đủ (có stoken) đã lưu trong CSDL máy tính vào Clipboard."""

import asyncio
import os
import subprocess
import sys
from pathlib import Path

# Tắt log ồn ào
os.environ["LOGURU_LEVEL"] = "ERROR"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.db.database import db  # noqa: E402
from app.security.encryption import cipher  # noqa: E402


async def get_cookie() -> str | None:
    await db.connect()
    try:
        async with db.get_connection() as conn:
            cursor = await conn.execute("SELECT cookie_encrypted FROM sessions LIMIT 1")
            row = await cursor.fetchone()
            if row:
                return cipher.decrypt(row[0])
            return None
    finally:
        await db.close()


def copy_to_clipboard(text: str) -> bool:
    """Sao chép text vào Clipboard của hệ điều hành."""
    try:
        if sys.platform == "win32":
            subprocess.run(["powershell", "-NoProfile", "-Command", "$input | Set-Clipboard"], input=text, text=True, check=True)
            return True
        elif sys.platform == "darwin":
            subprocess.run(["pbcopy"], input=text, text=True, check=True)
            return True
        else:
            subprocess.run(["xclip", "-selection", "clipboard"], input=text, text=True, check=True)
            return True
    except Exception:
        return False


def main():
    cookie = asyncio.run(get_cookie())
    if not cookie:
        print("❌ Không tìm thấy cookie nào trong CSDL máy tính. Hãy chạy scripts/get_full_cookie.py trước.")
        return

    print("=" * 64)
    print("📋 CHUỖI COOKIE HOYOLAB ĐẦY ĐỦ (CÓ STOKEN)")
    print("=" * 64)
    print(cookie)
    print("=" * 64)

    if copy_to_clipboard(cookie):
        print("✅ ĐÃ TỰ ĐỘNG SAO CHÉP VÀO BỘ NHỚ TẠM (CLIPBOARD)!")
        print("👉 Bây giờ bạn chỉ cần vào Discord:")
        print("   1. Gõ lệnh: /auto session_add")
        print("   2. Chọn áp dụng cho: Tất cả tài khoản")
        print("   3. Nhấn Ctrl + V để dán cookie vào và bấm Gửi.")
        print("   4. Gõ /auto verify để kiểm tra lại.")
    else:
        print("👉 Hãy bôi đen và sao chép chuỗi cookie ở trên, sau đó dán vào /auto session_add trên Discord.")


if __name__ == "__main__":
    main()
