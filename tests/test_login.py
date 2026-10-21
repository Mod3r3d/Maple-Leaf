"""Kiểm thử lớp đăng nhập HoYoLAB dùng cho lệnh `/auto login`.

Không gọi mạng: mọi lời gọi tới HoYoLAB đều được thay bằng hàm giả.
"""

import unittest
from unittest.mock import patch

import genshin

from app.automation.login import (
    LoginNeedsCaptcha,
    LoginNeedsEmailCode,
    login_with_app,
)


class _FakeAppLoginResult:
    def to_dict(self):
        return {"stoken": "v2_stoken", "ltuid_v2": "123", "ltmid_v2": "mid", "account_id_v2": "123"}


class TestLoginGuards(unittest.IsolatedAsyncioTestCase):
    async def test_email_verification_raises_friendly_error_and_restores_hook(self):
        from genshin.client.components.auth import server as auth_server

        original = auth_server.enter_code

        async def fake_login(self, email, password, *, device_id=None, geetest_solver=None):
            await auth_server.enter_code()

        with patch.object(genshin.Client, "login_with_app_password", new=fake_login), patch(
            "app.automation.login.get_or_create_device_id", return_value="test-device"
        ):
            with self.assertRaises(LoginNeedsEmailCode):
                await login_with_app("user@example.com", "secret")

        # Hook phải được khôi phục, nếu không các lần đăng nhập sau sẽ hỏng.
        self.assertIs(auth_server.enter_code, original)

    async def test_captcha_raises_friendly_error(self):
        async def fake_login(self, email, password, *, device_id=None, geetest_solver=None):
            await geetest_solver(object())

        with patch.object(genshin.Client, "login_with_app_password", new=fake_login), patch(
            "app.automation.login.get_or_create_device_id", return_value="test-device"
        ):
            with self.assertRaises(LoginNeedsCaptcha):
                await login_with_app("user@example.com", "secret")

    async def test_successful_login_returns_full_cookie(self):
        async def fake_login(self, email, password, *, device_id=None, geetest_solver=None):
            return _FakeAppLoginResult()

        async def fake_refresh(cookies, *, token_types):
            return {"ltoken_v2": "v2_ltoken", "cookie_token_v2": "v2_cookie"}

        with patch.object(genshin.Client, "login_with_app_password", new=fake_login), patch(
            "app.automation.login.get_or_create_device_id", return_value="test-device"
        ), patch("genshin.fetch_cookie_with_stoken_v2", new=fake_refresh):
            cookies = await login_with_app("user@example.com", "secret")

        self.assertEqual(cookies["stoken"], "v2_stoken")
        self.assertEqual(cookies["ltoken_v2"], "v2_ltoken")
        self.assertEqual(cookies["cookie_token_v2"], "v2_cookie")

    async def test_interactive_otp_callback_resolves(self):
        from genshin.client.components.auth import server as auth_server

        received_code = None

        async def fake_login(self, email, password, *, device_id=None, geetest_solver=None):
            nonlocal received_code
            received_code = await auth_server.enter_code()
            return _FakeAppLoginResult()

        async def fake_otp():
            return "654321"

        with patch.object(genshin.Client, "login_with_app_password", new=fake_login), patch(
            "app.automation.login.get_or_create_device_id", return_value="test-device"
        ), patch("genshin.fetch_cookie_with_stoken_v2", return_value={}):
            cookies = await login_with_app("user@example.com", "secret", otp_callback=fake_otp)

        self.assertEqual(received_code, "654321")
        self.assertEqual(cookies["stoken"], "v2_stoken")

    async def test_interactive_captcha_callback_resolves(self):
        captured_session_id = None
        captured_url = None

        async def fake_captcha_cb(session_id, url):
            nonlocal captured_session_id, captured_url
            captured_session_id = session_id
            captured_url = url
            # Simulate user completing captcha on web
            from app.bot.health_server import health_server
            session = health_server._captcha_sessions.get(session_id)
            if session and not session.future.done():
                session.future.set_result("captcha_solved_mock")

        async def fake_login(client_self, email, password, *, device_id=None, geetest_solver=None):
            result = await geetest_solver(object())
            assert result == "captcha_solved_mock"
            return _FakeAppLoginResult()

        with patch.object(genshin.Client, "login_with_app_password", new=fake_login), patch(
            "app.automation.login.get_or_create_device_id", return_value="test-device"
        ), patch("genshin.fetch_cookie_with_stoken_v2", return_value={}):
            cookies = await login_with_app("user@example.com", "secret", captcha_callback=fake_captcha_cb)

        self.assertIsNotNone(captured_session_id)
        self.assertIn("/captcha/", captured_url)
        self.assertEqual(cookies["stoken"], "v2_stoken")


if __name__ == "__main__":
    unittest.main()
