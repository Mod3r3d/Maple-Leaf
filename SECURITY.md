# Chính sách bảo mật (Security Policy)

## Dữ liệu nhạy cảm mà Maple Leaf xử lý

Maple Leaf lưu trữ những thông tin rất nhạy cảm, vì vậy việc bảo vệ chúng là ưu tiên số một:

| Dữ liệu | Nơi lưu | Cách bảo vệ |
|---|---|---|
| Cookie / Session HoYoLAB | `sessions` trong CSDL | **Mã hoá đối xứng Fernet** trước khi ghi |
| Khoá mã hoá | `data/.secret.key` (hoặc biến môi trường `ENCRYPTION_KEY`) | **Không bao giờ commit** |
| Discord Bot Token | `.env` | **Không bao giờ commit** |
| CSDL SQLite (`data/*.db`, `*.db-wal`, `*.db-shm`) | `data/` | **Không bao giờ commit** |

> ⚠️ File `*.db-wal` chứa các *trang dữ liệu thô* của CSDL, trong đó có cả cookie đã mã hoá.
> Nếu kẻ tấn công có **cả** file này **và** `data/.secret.key` thì cookie sẽ bị giải mã.
> Vì vậy hai loại file này **tuyệt đối không được** đưa lên git.

---

## Nguyên tắc bắt buộc khi đóng góp

1. **Không commit bí mật.** `.gitignore` đã chặn `.env`, `data/.secret.key`, `*.db*`, `logs/`.
   Trước khi mở PR, hãy chạy `git status` và kiểm tra lại.
2. **Không log cookie/token.** Không ghi cookie thô, `stoken`, `ltoken`, `cookie_token` vào log
   hay phản hồi Discord. Dùng `mask_cookie()` trong `app/security/encryption.py`.
3. **Không hard-code token** trong mã nguồn.

---

## Nếu bạn phát hiện rò rỉ bí mật

Nếu bạn vô tình commit `.env`, `data/.secret.key` hoặc file CSDL:

### 1. Gỡ khỏi git (không xoá file thật trên máy)

```bash
git rm --cached data/.secret.key data/*.db data/*.db-wal data/*.db-shm .env
```

### 2. Xoá khỏi **toàn bộ lịch sử** git

Chỉ gỡ ở commit mới là **chưa đủ** — bí mật vẫn nằm trong các commit cũ và vẫn tải được từ GitHub.
Có 2 cách:

**Cách A — tạo lại repo sạch (đơn giản nhất, khuyến nghị với repo ít commit):**

```bash
# Tạo nhánh mới với 1 commit duy nhất, không mang theo lịch sử cũ
git checkout --orphan clean-main
git add -A
git commit -m "Initial public release"
git branch -D main
git branch -m main
git push --force origin main
```

**Cách B — dùng `git-filter-repo` (giữ lại lịch sử):**

```bash
pip install git-filter-repo
git filter-repo --path data/.secret.key --path data/hoyobot.db-wal \
                --path data/hoyobot.db-shm --invert-paths
git push --force origin main
```

> Sau khi push, liên hệ GitHub Support để xoá cache các commit cũ nếu repo là public.
> Cách chắc chắn nhất là **xoá repo và tạo lại**.

### 3. Vô hiệu hoá mọi bí mật đã lộ (QUAN TRỌNG)

Xoá khỏi git **không** làm bí mật an toàn trở lại — phải đổi mới toàn bộ:

- **Khoá mã hoá:** xoá `data/.secret.key` để bot sinh khoá mới, rồi liên kết lại cookie
  (dữ liệu cũ sẽ không giải mã được nữa — điều này là mong muốn).
- **Cookie HoYoLAB:** đăng xuất khỏi HoYoLAB (đăng xuất mọi thiết bị) và đăng nhập lại,
  sau đó dùng `/auto session_add` hoặc `scripts/get_full_cookie.py` để nạp cookie mới.
- **Discord Bot Token:** vào Discord Developer Portal → Bot → **Reset Token**, cập nhật lại `.env`.

---

## Báo cáo lỗ hổng

Nếu bạn phát hiện lỗ hổng bảo mật, vui lòng **không** mở issue công khai. Hãy liên hệ riêng
với chủ dự án kèm mô tả và các bước tái hiện.
