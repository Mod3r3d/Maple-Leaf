"""Kiểm thử cơ chế thử lại khi Discord trả 429 lúc đăng nhập."""

import unittest

from app.main import start_bot_with_retry


class FakeRateLimit(Exception):
    status = 429


class FakeFatalError(Exception):
    pass


class FakeHttp:
    """Giả lập HTTPClient của discord.py để kiểm tra việc đóng session."""

    def __init__(self):
        self.close_count = 0

    async def close(self):
        self.close_count += 1


class FakeBot:
    """Bot giả: `start()` ném lỗi `failures` lần đầu rồi thành công."""

    def __init__(self, failures: int, exc_type=FakeRateLimit):
        self.failures = failures
        self.exc_type = exc_type
        self.calls = 0
        self.http = FakeHttp()

    async def start(self, token: str):
        self.calls += 1
        if self.calls <= self.failures:
            raise self.exc_type()


class TestStartupRetry(unittest.IsolatedAsyncioTestCase):
    async def test_retries_on_429_then_succeeds(self):
        bot = FakeBot(failures=2)
        await start_bot_with_retry(bot, "token", max_attempts=4, base_delay=0.001)
        self.assertEqual(bot.calls, 3)
        # Mỗi lần lỗi phải đóng session cũ để tránh "Unclosed client session".
        self.assertEqual(bot.http.close_count, 2)

    async def test_gives_up_after_max_attempts(self):
        bot = FakeBot(failures=10)
        with self.assertRaises(FakeRateLimit):
            await start_bot_with_retry(bot, "token", max_attempts=3, base_delay=0.001)
        self.assertEqual(bot.calls, 3)
        self.assertEqual(bot.http.close_count, 3)

    async def test_non_429_error_propagates_immediately(self):
        bot = FakeBot(failures=1, exc_type=FakeFatalError)
        with self.assertRaises(FakeFatalError):
            await start_bot_with_retry(bot, "token", max_attempts=3, base_delay=0.001)
        self.assertEqual(bot.calls, 1)
        self.assertEqual(bot.http.close_count, 0)


if __name__ == "__main__":
    unittest.main()
