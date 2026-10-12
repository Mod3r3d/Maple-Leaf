# Hướng dẫn đóng góp (Contributing)

Cảm ơn bạn đã quan tâm đến Maple Leaf! Mọi đóng góp — báo lỗi, đề xuất tính năng, sửa mã nguồn
hay cải thiện tài liệu — đều được hoan nghênh.

---

## 1. Chuẩn bị môi trường

```bash
git clone https://github.com/<ten-ban>/hoyoBot.git
cd hoyoBot

# Cách nhanh nhất (tự tạo venv + cài dependency + tạo .env):
#   Windows:  scripts\setup.bat
#   Linux/macOS:  bash scripts/setup.sh

# Hoặc làm thủ công:
python -m venv .venv
.venv/Scripts/activate          # Windows
source .venv/bin/activate       # Linux/macOS
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env            # rồi điền DISCORD_TOKEN
```

Chạy bot:

```bash
python -m app.main
```

---

## 2. Chạy kiểm thử

```bash
python -m unittest discover tests -v
```

**Mọi PR đều phải pass toàn bộ test hiện có.** Nếu bạn thêm tính năng mới, hãy thêm test tương ứng
trong thư mục `tests/`.

---

## 3. Kiểm tra chất lượng mã (tùy chọn nhưng khuyến khích)

```bash
ruff check .          # lint
ruff format .         # định dạng
```

---

## 4. Quy ước mã nguồn

- **Python 3.12+**, dùng `async/await` xuyên suốt (discord.py + aiosqlite).
- **Ngôn ngữ:** toàn bộ chuỗi hiển thị cho người dùng (embed, lỗi, mô tả lệnh) là **tiếng Việt**.
  Comment và docstring cũng dùng tiếng Việt để đồng bộ.
- **Kiến trúc phân tầng** — hãy giữ đúng luồng:
  `commands/` (giao diện Discord) → `services/` (nghiệp vụ) → `games/` & `db/` (dữ liệu).
  Không gọi thẳng API HoYoLAB từ trong `commands/`.
- **Không hard-code** ID kênh, ID server, token hay emoji của server cá nhân.
- Đặt tên theo `snake_case` cho hàm/biến, `PascalCase` cho class.

### Quản lý dependency

Dự án dùng mô hình **hai file** để vừa dễ nâng cấp vừa đảm bảo tái lập được môi trường:

| File | Vai trò |
|---|---|
| `requirements.in` | Khai báo **trực tiếp** các thư viện dùng trong code (dải `>=`) — đây là file bạn sửa |
| `requirements.txt` | Bản **đã ghim cứng** (`==`) dùng để cài đặt — **file sinh tự động, không sửa tay** |

Khi cần thêm/cập nhật thư viện:

```bash
pip install -r requirements-dev.txt        # có sẵn pip-tools
# 1) sửa requirements.in
# 2) sinh lại file ghim:
pip-compile requirements.in --output-file requirements.txt
# 3) đồng bộ môi trường theo đúng bản ghim:
pip-sync requirements.txt
```

> ⚠️ Gói chỉ dành cho Windows (ví dụ `colorama`, `win32-setctime`) phải giữ environment marker
> `; sys_platform == "win32"` để không làm hỏng cài đặt trên Linux/macOS.

---

## 5. ⚠️ Quy tắc bảo mật (BẮT BUỘC)

Đọc thêm [`SECURITY.md`](SECURITY.md). Tóm tắt:

1. **Không commit bí mật**: `.env`, `data/.secret.key`, `data/*.db*`, `logs/`.
   Luôn chạy `git status` trước khi commit.
2. **Không log cookie/token.** Dùng `mask_cookie()` khi cần hiển thị.
3. **Không commit dữ liệu người dùng thật.**

---

## 6. Quy trình gửi PR

1. Fork repo và tạo nhánh: `git checkout -b feat/ten-tinh-nang`.
2. Commit theo [Conventional Commits](https://www.conventionalcommits.org/):
   `feat: ...`, `fix: ...`, `docs: ...`, `refactor: ...`, `test: ...`, `chore: ...`.
3. Đảm bảo `python -m unittest discover tests` pass.
4. Mở Pull Request, mô tả rõ **vấn đề** và **cách giải quyết**, kèm ảnh chụp nếu là thay đổi UI.
5. Cập nhật `CHANGELOG.md` nếu thay đổi ảnh hưởng đến người dùng.

---

## 7. Báo lỗi

Khi mở issue, vui lòng kèm:

- Phiên bản Python và hệ điều hành.
- Các bước tái hiện lỗi.
- Log liên quan (**che token và cookie trước khi dán!**).
