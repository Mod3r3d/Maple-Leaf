"""Máy chủ HTTP nhẹ kiểm tra trạng thái hoạt động (Health Check Server) cho Render/Cloud."""

from typing import Optional

import discord
from aiohttp import web
from loguru import logger

from app.config import settings


class HealthCheckServer:
    def __init__(self):
        self._runner: Optional[web.AppRunner] = None
        self._site: Optional[web.TCPSite] = None
        self._bot: Optional[discord.Client] = None

    async def _handle_healthz(self, request: web.Request) -> web.Response:
        """Endpoint kiểm tra sức khoẻ cho Render / Cloud PaaS."""
        is_ready = bool(self._bot and self._bot.is_ready())
        return web.json_response({
            "status": "ok",
            "app": "Maple Leaf",
            "bot_connected": is_ready,
        })

    async def _handle_ping(self, request: web.Request) -> web.Response:
        return web.Response(text="pong", content_type="text/plain")

    async def _handle_root(self, request: web.Request) -> web.Response:
        """Trang thông tin trực quan hiển thị trạng thái bot 24/7."""
        bot_user = str(self._bot.user) if self._bot and self._bot.user else "Đang kết nối Discord..."
        guilds = len(self._bot.guilds) if self._bot else 0
        latency = round(self._bot.latency * 1000, 1) if self._bot and self._bot.latency else 0.0

        html = f"""<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Maple Leaf Bot — Hoạt động 24/7</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background: #0f172a;
            color: #f8fafc;
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
            padding: 20px;
        }}
        .card {{
            background: #1e293b;
            border-radius: 20px;
            padding: 36px 32px;
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.4);
            max-width: 480px;
            width: 100%;
            border: 1px solid #334155;
            text-align: center;
        }}
        .badge {{
            display: inline-flex;
            align-items: center;
            gap: 8px;
            background: rgba(16, 185, 129, 0.15);
            color: #34d399;
            border: 1px solid rgba(16, 185, 129, 0.3);
            padding: 6px 16px;
            border-radius: 9999px;
            font-size: 13px;
            font-weight: 600;
            margin-bottom: 20px;
        }}
        .badge-dot {{
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #10b981;
            box-shadow: 0 0 10px #10b981;
            animation: pulse 2s infinite;
        }}
        @keyframes pulse {{
            0%, 100% {{ opacity: 1; transform: scale(1); }}
            50% {{ opacity: 0.5; transform: scale(0.85); }}
        }}
        h1 {{
            font-size: 26px;
            color: #f1f5f9;
            margin-bottom: 6px;
            font-weight: 700;
        }}
        p.subtitle {{
            color: #94a3b8;
            font-size: 14px;
            margin-bottom: 28px;
        }}
        .grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 12px;
            text-align: left;
        }}
        .box {{
            background: #0f172a;
            padding: 14px 16px;
            border-radius: 12px;
            border: 1px solid #334155;
        }}
        .box-title {{
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: #64748b;
            margin-bottom: 4px;
            font-weight: 600;
        }}
        .box-val {{
            font-size: 15px;
            font-weight: 700;
            color: #e2e8f0;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}
        .footer {{
            margin-top: 24px;
            font-size: 12px;
            color: #64748b;
        }}
        .footer a {{
            color: #38bdf8;
            text-decoration: none;
        }}
        .footer a:hover {{
            text-decoration: underline;
        }}
    </style>
</head>
<body>
    <div class="card">
        <div class="badge">
            <span class="badge-dot"></span>
            Hoạt động 24/7 (Online)
        </div>
        <h1>🍁 Maple Leaf Bot</h1>
        <p class="subtitle">Genshin Impact &amp; Honkai: Star Rail Discord Bot</p>

        <div class="grid">
            <div class="box">
                <div class="box-title">Tài khoản Bot</div>
                <div class="box-val">{bot_user}</div>
            </div>
            <div class="box">
                <div class="box-title">Độ trễ (Ping)</div>
                <div class="box-val">{latency} ms</div>
            </div>
            <div class="box">
                <div class="box-title">Máy chủ Discord</div>
                <div class="box-val">{guilds} servers</div>
            </div>
            <div class="box">
                <div class="box-title">Health Check</div>
                <div class="box-val" style="color: #34d399;">/healthz (200 OK)</div>
            </div>
        </div>

        <div class="footer">
            Maple Leaf Bot &bull; Triển khai trên Render / Cloud &bull; <a href="/healthz">Kiểm tra API JSON</a>
        </div>
    </div>
</body>
</html>"""
        return web.Response(text=html, content_type="text/html")

    async def start(self, bot: Optional[discord.Client] = None):
        """Khởi động web server nếu có cấu hình PORT (mặc định trên Render là 10000)."""
        self._bot = bot
        port = settings.PORT
        if not port:
            logger.info("PORT không được đặt — bot chạy ở chế độ Worker thuần (không mở cổng HTTP).")
            return

        try:
            app = web.Application()
            app.router.add_get("/", self._handle_root)
            app.router.add_get("/healthz", self._handle_healthz)
            app.router.add_get("/ping", self._handle_ping)

            self._runner = web.AppRunner(app)
            await self._runner.setup()
            self._site = web.TCPSite(self._runner, settings.HEALTH_HOST, int(port))
            await self._site.start()
            logger.info(f"Đã mở Health Check Web Server tại http://{settings.HEALTH_HOST}:{port}/ (Render / Cloud)")
        except Exception as e:
            logger.exception(f"Không thể khởi động Health Check Web Server trên port {port}: {e}")

    async def stop(self):
        """Dọn dẹp web server khi bot tắt."""
        if self._runner:
            try:
                await self._runner.cleanup()
                logger.info("Đã dừng Health Check Web Server.")
            except Exception as e:
                logger.warning(f"Lỗi khi dừng web runner: {e}")
            finally:
                self._runner = None
                self._site = None


health_server = HealthCheckServer()
