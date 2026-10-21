"""Kiểm thử Health Check Web Server cho Render/Cloud."""

import unittest
from unittest.mock import patch, MagicMock
import aiohttp
from app.bot.health_server import HealthCheckServer
from app.config import settings


class TestHealthCheckServer(unittest.IsolatedAsyncioTestCase):
    async def test_no_port_does_not_start_server(self):
        server = HealthCheckServer()
        with patch.object(settings, "PORT", None):
            await server.start(None)
            self.assertIsNone(server._runner)
            self.assertIsNone(server._site)
            await server.stop()

    async def test_server_starts_and_responds_to_health_endpoints(self):
        server = HealthCheckServer()
        test_port = 18999
        fake_bot = MagicMock()
        fake_bot.is_ready.return_value = True
        fake_bot.user = "TestBot#1234"
        fake_bot.guilds = [1, 2]
        fake_bot.latency = 0.042

        with patch.object(settings, "PORT", test_port), patch.object(settings, "HEALTH_HOST", "127.0.0.1"):
            await server.start(fake_bot)
            self.assertIsNotNone(server._runner)
            self.assertIsNotNone(server._site)

            async with aiohttp.ClientSession() as session:
                # 1. Test /healthz
                async with session.get(f"http://127.0.0.1:{test_port}/healthz") as resp:
                    self.assertEqual(resp.status, 200)
                    data = await resp.json()
                    self.assertEqual(data["status"], "ok")
                    self.assertEqual(data["app"], "Maple Leaf")
                    self.assertTrue(data["bot_connected"])

                # 2. Test /ping
                async with session.get(f"http://127.0.0.1:{test_port}/ping") as resp:
                    self.assertEqual(resp.status, 200)
                    text = await resp.text()
                    self.assertEqual(text, "pong")

                # 3. Test / (root html page)
                async with session.get(f"http://127.0.0.1:{test_port}/") as resp:
                    self.assertEqual(resp.status, 200)
                    html = await resp.text()
                    self.assertIn("Maple Leaf Bot", html)
                    self.assertIn("TestBot#1234", html)

            # Clean shutdown
            await server.stop()
            self.assertIsNone(server._runner)
            self.assertIsNone(server._site)


if __name__ == "__main__":
    unittest.main()
