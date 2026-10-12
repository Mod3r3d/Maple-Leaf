#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
#  Maple Leaf — Script cài đặt nhanh (Linux / macOS)
#  Chạy:  bash scripts/setup.sh
# ─────────────────────────────────────────────────────────────
set -euo pipefail

cd "$(dirname "$0")/.."
echo "✦ Maple Leaf — Cài đặt môi trường"

# 1) Kiểm tra Python
if command -v python3 >/dev/null 2>&1; then
    PY=python3
elif command -v python >/dev/null 2>&1; then
    PY=python
else
    echo "❌ Không tìm thấy Python. Hãy cài Python 3.12+ rồi chạy lại."
    exit 1
fi
echo "• Dùng Python: $($PY --version)"

# 2) Tạo môi trường ảo
if [ ! -d ".venv" ]; then
    echo "• Đang tạo môi trường ảo .venv ..."
    "$PY" -m venv .venv
else
    echo "• Môi trường ảo .venv đã tồn tại, bỏ qua."
fi

# 3) Cài dependency
echo "• Đang cài đặt thư viện ..."
./.venv/bin/python -m pip install --upgrade pip -q
./.venv/bin/python -m pip install -r requirements.txt -q

# 4) Tạo file .env nếu chưa có
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "• Đã tạo .env từ .env.example"
else
    echo "• File .env đã tồn tại, giữ nguyên."
fi

# 5) Tạo thư mục runtime
mkdir -p data logs

cat <<'EOF'

✅ Cài đặt xong!

Bước tiếp theo:
  1. Mở file .env và điền DISCORD_TOKEN (lấy tại https://discord.com/developers/applications)
  2. Chạy bot:
       ./.venv/bin/python -m app.main

Kiểm thử:  ./.venv/bin/python -m unittest discover tests
EOF
