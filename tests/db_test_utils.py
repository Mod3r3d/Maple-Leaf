"""Tiện ích dùng chung cho bộ kiểm thử.

Mục đích: **cô lập cơ sở dữ liệu**. Test phải chạy trên một file CSDL tạm, tuyệt đối
KHÔNG được đụng vào `data/mapleleaf.db` (dữ liệu thật của người dùng).

Cách dùng:

    class TestSomething(TempDatabaseMixin, unittest.IsolatedAsyncioTestCase):
        async def asyncSetUp(self):
            await self._open_temp_db()

        async def asyncTearDown(self):
            await self._close_temp_db()
"""

import os
import tempfile
from pathlib import Path
from typing import Optional

from app.db.database import db


class TempDatabaseMixin:
    """Trộn vào test case để thay CSDL thật bằng một file tạm dùng một lần."""

    _temp_db_path: Optional[Path] = None

    async def _open_temp_db(self) -> Path:
        """Tạo file CSDL tạm, trỏ `db` sang đó rồi kết nối (bảng được tạo tự động)."""
        fd, raw_path = tempfile.mkstemp(prefix="mapleleaf_test_", suffix=".db")
        os.close(fd)
        # Xoá file rỗng vừa tạo để SQLite khởi tạo CSDL sạch hoàn toàn.
        try:
            os.unlink(raw_path)
        except OSError:
            pass

        self._temp_db_path = Path(raw_path)
        db.db_path = self._temp_db_path
        await db.connect()
        return self._temp_db_path

    async def _close_temp_db(self) -> None:
        """Đóng kết nối và xoá sạch các file CSDL tạm (kể cả -wal / -shm)."""
        try:
            await db.close()
        finally:
            if self._temp_db_path is not None:
                for suffix in ("", "-wal", "-shm"):
                    try:
                        os.unlink(f"{self._temp_db_path}{suffix}")
                    except OSError:
                        pass
                self._temp_db_path = None
