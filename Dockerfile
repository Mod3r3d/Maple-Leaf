FROM python:3.12-slim

# Log ra stdout ngay lập tức + không sinh file .pyc
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Cài đặt thư viện hệ thống cần thiết cho Pillow (vẽ ảnh thẻ nhân vật)
RUN apt-get update && apt-get install -y --no-install-recommends \
    fontconfig \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Thư mục runtime (được mount volume trong docker-compose.yml)
RUN mkdir -p /app/data /app/logs

CMD ["python", "-m", "app.main"]
