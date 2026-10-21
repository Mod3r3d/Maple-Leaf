"""Máy chủ HTTP kiểm tra trạng thái hoạt động (Health Check) và Cổng giải Captcha Web (Captcha Portal)."""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

import aiohttp
import discord
from aiohttp import web
from genshin.models.auth.geetest import (
    MMT,
    MMTResult,
    MMTv4,
    MMTv4Result,
    RiskyCheckMMT,
    RiskyCheckMMTResult,
    SessionMMT,
    SessionMMTResult,
    SessionMMTv4,
    SessionMMTv4Result,
)
from loguru import logger

from app.config import settings

GT_V3_URL = "https://static.geetest.com/static/js/gt.0.5.0.js"
GT_V4_URL = "https://static.geetest.com/v4/gt4.js"


@dataclass
class CaptchaSession:
    session_id: str
    mmt: Any
    future: asyncio.Future
    created_at: float = field(default_factory=time.time)
    lang: str = "vi"
    api_server: str = "api-na.geetest.com"
    for_new_os_app: bool = False


class HealthCheckServer:
    def __init__(self):
        self._runner: Optional[web.AppRunner] = None
        self._site: Optional[web.TCPSite] = None
        self._bot: Optional[discord.Client] = None
        self._captcha_sessions: Dict[str, CaptchaSession] = {}
        self._gt_cache: Dict[str, bytes] = {}

    def register_captcha_session(
        self,
        session_id: str,
        mmt: Any,
        future: asyncio.Future,
        *,
        lang: str = "vi",
        api_server: str = "api-na.geetest.com",
        for_new_os_app: bool = False,
    ) -> None:
        """Đăng ký một phiên giải Captcha mới."""
        self._captcha_sessions[session_id] = CaptchaSession(
            session_id=session_id,
            mmt=mmt,
            future=future,
            lang=lang,
            api_server=api_server,
            for_new_os_app=for_new_os_app,
        )

    def cleanup_captcha_session(self, session_id: str) -> None:
        """Thu hồi phiên giải Captcha khi hoàn tất hoặc timeout."""
        self._captcha_sessions.pop(session_id, None)

    async def _handle_healthz(self, request: web.Request) -> web.Response:
        """Endpoint kiểm tra sức khoẻ cho Render / Cloud PaaS."""
        is_ready = bool(self._bot and self._bot.is_ready())
        return web.json_response({
            "status": "ok",
            "app": "Maple Leaf",
            "bot_connected": is_ready,
            "active_captcha_sessions": len(self._captcha_sessions),
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
            margin-bottom: 28px;
        }}
        .box {{
            background: #0f172a;
            border: 1px solid #334155;
            border-radius: 12px;
            padding: 16px 12px;
            text-align: left;
        }}
        .box-title {{
            font-size: 12px;
            color: #64748b;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 4px;
        }}
        .box-val {{
            font-size: 15px;
            font-weight: 600;
            color: #e2e8f0;
            word-break: break-all;
        }}
        .footer {{
            font-size: 12px;
            color: #64748b;
            border-top: 1px solid #334155;
            padding-top: 16px;
        }}
        .footer a {{
            color: #38bdf8;
            text-decoration: none;
        }}
    </style>
</head>
<body>
    <div class="card">
        <div class="badge">
            <div class="badge-dot"></div>
            <span>Dịch Vụ Đang Hoạt Động 24/7</span>
        </div>
        <h1>🍁 Maple Leaf</h1>
        <p class="subtitle">Trợ thủ Discord cho Genshin Impact &amp; Honkai: Star Rail</p>

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

    async def _handle_gt_script(self, request: web.Request) -> web.Response:
        """Phục vụ file JavaScript Geetest Loader (v3 hoặc v4)."""
        version = request.match_info.get("version", "v4")
        if version in self._gt_cache:
            return web.Response(body=self._gt_cache[version], content_type="text/javascript")

        gt_url = GT_V4_URL if "4" in version else GT_V3_URL
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(gt_url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    content = await resp.read()
                    self._gt_cache[version] = content
                    return web.Response(body=content, content_type="text/javascript")
        except Exception as e:
            logger.error(f"Không thể tải Geetest script từ {gt_url}: {e}")
            return web.Response(status=502, text=f"Lỗi tải script Geetest: {e}")

    async def _handle_captcha_page(self, request: web.Request) -> web.Response:
        """Trang giao diện Web hiện đại giải Captcha HoYoLAB."""
        session_id = request.match_info.get("session_id", "")
        session = self._captcha_sessions.get(session_id)

        if not session or session.future.done():
            expired_html = """<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Phiên Captcha Đã Hết Hạn — Maple Leaf</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0f172a; color: #f8fafc; display: flex; align-items: center; justify-content: center; min-height: 100vh; padding: 20px; }
        .card { background: #1e293b; border-radius: 20px; padding: 36px 32px; max-width: 440px; text-align: center; border: 1px solid #334155; }
        h2 { margin: 16px 0 8px; color: #f1f5f9; }
        p { color: #94a3b8; font-size: 14px; line-height: 1.5; }
    </style>
</head>
<body>
    <div class="card">
        <div style="font-size: 48px;">⌛</div>
        <h2>Phiên Xác Minh Đã Hết Hạn</h2>
        <p>Phiên giải Captcha này đã hoàn tất hoặc đã quá thời gian chờ (120 giây).<br><br>Vui lòng quay lại Discord và sử dụng lại lệnh <code>/auto login</code>.</p>
    </div>
</body>
</html>"""
            return web.Response(text=expired_html, content_type="text/html", status=410)

        is_v4 = isinstance(session.mmt, (MMTv4, SessionMMTv4))
        gt_ver = "v4" if is_v4 else "v3"
        api_server = session.api_server or "api-na.geetest.com"
        lang = session.lang or "vi"
        for_new_os_app = str(session.for_new_os_app).lower()

        html = f"""<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="referrer" content="no-referrer"/>
    <title>Xác Minh Captcha HoYoLAB — Maple Leaf</title>
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
            padding: 32px 28px;
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.4);
            max-width: 440px;
            width: 100%;
            border: 1px solid #334155;
            text-align: center;
        }}
        .header {{
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
            margin-bottom: 8px;
        }}
        .header-icon {{ font-size: 28px; }}
        h1 {{ font-size: 22px; color: #f1f5f9; font-weight: 700; }}
        p.desc {{ color: #94a3b8; font-size: 14px; margin-bottom: 24px; line-height: 1.5; }}
        #loading {{
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 12px;
            padding: 30px 0;
            color: #38bdf8;
            font-size: 14px;
        }}
        .spinner {{
            width: 36px;
            height: 36px;
            border: 3px solid rgba(56, 189, 248, 0.2);
            border-top-color: #38bdf8;
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }}
        @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
        #captcha-box {{
            min-height: 50px;
            display: flex;
            justify-content: center;
            margin-bottom: 20px;
        }}
        #success-box {{
            display: none;
            padding: 20px 0;
        }}
        .success-icon {{
            font-size: 54px;
            margin-bottom: 12px;
            animation: pop 0.4s ease-out;
        }}
        @keyframes pop {{
            0% {{ transform: scale(0.6); opacity: 0; }}
            80% {{ transform: scale(1.1); }}
            100% {{ transform: scale(1); opacity: 1; }}
        }}
        .success-title {{
            font-size: 20px;
            font-weight: 700;
            color: #34d399;
            margin-bottom: 8px;
        }}
        .success-desc {{
            font-size: 14px;
            color: #94a3b8;
            line-height: 1.5;
        }}
        #error-box {{
            display: none;
            background: rgba(239, 68, 68, 0.15);
            border: 1px solid rgba(239, 68, 68, 0.3);
            border-radius: 10px;
            padding: 12px;
            color: #f87171;
            font-size: 13px;
            margin-top: 16px;
        }}
        .tip {{
            font-size: 12px;
            color: #64748b;
            border-top: 1px solid #334155;
            padding-top: 16px;
            margin-top: 20px;
        }}
    </style>
    <script src="/captcha/gt/{gt_ver}.js"></script>
</head>
<body>
    <div class="card">
        <div class="header">
            <span class="header-icon">🍁</span>
            <h1>Maple Leaf</h1>
        </div>
        <p class="desc">Xác minh Captcha HoYoLAB để đăng nhập an toàn.<br>Kéo thanh trượt hoặc giải câu đố hình ảnh bên dưới:</p>

        <div id="loading">
            <div class="spinner"></div>
            <span>Đang tải thử thách Captcha từ HoYoLAB...</span>
        </div>

        <div id="captcha-box"></div>

        <div id="success-box">
            <div class="success-icon">✅</div>
            <div class="success-title">Xác Minh Thành Công!</div>
            <p class="success-desc">
                Hệ thống đã nhận kết quả Captcha hợp lệ.<br>
                Bạn có thể <strong>đóng tab này</strong> và quay lại Discord để tiếp tục.
            </p>
        </div>

        <div id="error-box"></div>

        <div class="tip">
            Cổng xác minh an toàn &bull; Tự động đồng bộ lên Discord Bot
        </div>
    </div>

    <script>
        const geetestVersion = {"4" if is_v4 else "3"};
        const forNewOsApp = {for_new_os_app};
        const initGeetest = geetestVersion === 3 ? window.initGeetest : window.initGeetest4;

        fetch("/captcha/{session_id}/mmt")
            .then(res => {{
                if (!res.ok) throw new Error("Phiên giải Captcha không tồn tại hoặc đã hết hạn.");
                return res.json();
            }})
            .then(mmt => {{
                const initParams = geetestVersion === 3 ? {{
                    gt: mmt.gt,
                    challenge: mmt.challenge,
                    new_captcha: mmt.new_captcha,
                    api_server: "{api_server}",
                    https: /^https/i.test(window.location.protocol),
                    product: "bind",
                    lang: "{lang}",
                }} : {{
                    captchaId: mmt.captcha_id ?? mmt.gt,
                    riskType: mmt.risk_type,
                    userInfo: mmt.session_id ? JSON.stringify(forNewOsApp ? {{ session_id: mmt.session_id }} : {{ mmt_key: mmt.session_id }}) : undefined,
                    apiServers: ["{api_server}"],
                    product: "bind",
                    language: "{lang}",
                }};

                initGeetest(initParams, captcha => {{
                    captcha.onReady(() => {{
                        document.getElementById('loading').style.display = 'none';
                        geetestVersion === 3 ? captcha.verify() : captcha.showCaptcha();
                    }});

                    captcha.onSuccess(() => {{
                        const validateData = captcha.getValidate();
                        fetch("/captcha/{session_id}/send-data", {{
                            method: "POST",
                            headers: {{ "Content-Type": "application/json" }},
                            body: JSON.stringify({{
                                ...(mmt.session_id && {{ session_id: mmt.session_id }}),
                                ...(mmt.check_id && {{ check_id: mmt.check_id }}),
                                ...validateData
                            }})
                        }}).then(res => {{
                            if (res.ok) {{
                                document.getElementById('captcha-box').style.display = 'none';
                                document.getElementById('success-box').style.display = 'block';
                            }} else {{
                                throw new Error("Gửi kết quả giải Captcha thất bại.");
                            }}
                        }}).catch(err => {{
                            showError(err.message);
                        }});
                    }});

                    captcha.onError(err => {{
                        showError("Lỗi Captcha: " + (err.msg || JSON.stringify(err)));
                    }});
                }});
            }})
            .catch(err => {{
                document.getElementById('loading').style.display = 'none';
                showError(err.message);
            }});

        function showError(msg) {{
            const errBox = document.getElementById('error-box');
            errBox.innerText = msg;
            errBox.style.display = 'block';
        }}
    </script>
</body>
</html>"""
        return web.Response(text=html, content_type="text/html")

    async def _handle_captcha_mmt(self, request: web.Request) -> web.Response:
        """Trả về tham số MMT cấu hình cho Geetest Frontend."""
        session_id = request.match_info.get("session_id", "")
        session = self._captcha_sessions.get(session_id)
        if not session or session.future.done():
            return web.json_response({"error": "Phiên không tồn tại hoặc đã hết hạn"}, status=404)

        return web.json_response(session.mmt.model_dump())

    async def _handle_captcha_send_data(self, request: web.Request) -> web.Response:
        """Nhận kết quả xác minh từ trình duyệt và hoàn thành Future."""
        session_id = request.match_info.get("session_id", "")
        session = self._captcha_sessions.get(session_id)
        if not session or session.future.done():
            return web.json_response({"error": "Phiên không hợp lệ hoặc đã hoàn tất"}, status=404)

        try:
            data = await request.json()
            mmt = session.mmt
            if isinstance(mmt, RiskyCheckMMT):
                result = RiskyCheckMMTResult(**data)
            elif isinstance(mmt, SessionMMT):
                result = SessionMMTResult(**data)
            elif isinstance(mmt, SessionMMTv4):
                result = SessionMMTv4Result(**data)
            elif isinstance(mmt, MMT):
                result = MMTResult(**data)
            else:
                result = MMTv4Result(**data)

            session.future.set_result(result)
            logger.info(f"Đã giải Captcha thành công cho session {session_id}")
            return web.json_response({"status": "ok"})
        except Exception as e:
            logger.exception(f"Lỗi khi xử lý dữ liệu Captcha trả về: {e}")
            if not session.future.done():
                session.future.set_exception(e)
            return web.json_response({"error": str(e)}, status=400)

    async def start(self, bot: Optional[discord.Client] = None):
        """Khởi động web server cho Health Check và Cổng giải Captcha."""
        self._bot = bot
        port = settings.PORT
        if not port:
            logger.info("PORT không được đặt — bot chạy ở chế độ Worker thuần (không mở cổng HTTP).")
            return

        try:
            app = web.Application()
            # Health check routes
            app.router.add_get("/", self._handle_root)
            app.router.add_get("/healthz", self._handle_healthz)
            app.router.add_get("/ping", self._handle_ping)

            # Captcha portal routes
            app.router.add_get("/captcha/gt/{version}.js", self._handle_gt_script)
            app.router.add_get("/captcha/{session_id}", self._handle_captcha_page)
            app.router.add_get("/captcha/{session_id}/mmt", self._handle_captcha_mmt)
            app.router.add_post("/captcha/{session_id}/send-data", self._handle_captcha_send_data)

            self._runner = web.AppRunner(app)
            await self._runner.setup()
            self._site = web.TCPSite(self._runner, settings.HEALTH_HOST, int(port))
            await self._site.start()
            logger.info(f"Đã mở Health Check & Captcha Portal tại http://{settings.HEALTH_HOST}:{port}/ (Render / Cloud)")
        except OSError as e:
            logger.warning(f"Cổng {port} đang bận hoặc không thể mở Web Server ({e}). Sẽ chạy ở chế độ dự phòng.")
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
