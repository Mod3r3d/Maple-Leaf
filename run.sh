#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
#  Maple Leaf — Script khởi chạy nhanh (Linux / macOS)
#  Chạy:  bash run.sh
# ═══════════════════════════════════════════════════════════════
set -euo pipefail

cd "$(dirname "$0")"

echo "==================================================="
echo "    🍁 MAPLE LEAF DISCORD BOT — KHỞI CHẠY"
echo "==================================================="

# 1. Kiểm tra môi trường ảo
if [ ! -f ".venv/bin/python" ]; then
    echo "[!] Chưa tìm thấy môi trường ảo .venv."
    echo "[*] Đang tự động chạy cài đặt ban đầu (scripts/setup.sh)..."
    bash scripts/setup.sh
fi

# 2. Kiểm tra file .env
if [ ! -f ".env" ]; then
    echo "[*] Chưa có file .env — đang tạo từ .env.example..."
    cp .env.example .env
fi

# 3. Kiểm tra DISCORD_TOKEN
if ! grep -q -E '^DISCORD_TOKEN=.+' .env || grep -q -E '^DISCORD_TOKEN=$' .env; then
    echo "========================================================"
    echo " ⚠️  CẢNH BÁO: Bạn chưa điền DISCORD_TOKEN trong file .env!"
    echo "========================================================"
    echo " 1. Vào: https://discord.com/developers/applications"
    echo " 2. Tạo/Chọn Bot -> Reset Token -> Copy Token."
    echo " 3. Dán Token vào dòng DISCORD_TOKEN=... trong file .env."
    echo "========================================================"
    exit 1
fi

# 4. Khởi chạy bot
echo "[*] Đang khởi động Maple Leaf Bot..."
echo "    Nhấn Ctrl+C để dừng bot bất kỳ lúc nào."
echo ""
./.venv/bin/python -m app.main
