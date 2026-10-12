# Hướng dẫn lấy `stoken` để Đổi Giftcode hoạt động bền vững

> Mục đích: lấy `stoken` để bot tự gia hạn `cookie_token` — nhờ đó tính năng
> Đổi Giftcode (Auto Redeem) chạy mãi mà không cần dán lại cookie.

---

## 1. Vì sao cần `stoken`?

| Token | Vòng đời | Vai trò |
|---|---|---|
| `cookie_token` / `cookie_token_v2` | **~2 giờ** | Token dùng để đổi Giftcode — hết hạn cực nhanh |
| `stoken` | **~30 ngày** | Dùng để **cấp lại** `cookie_token` |
| `ltuid_v2`, `ltmid_v2` | dài hạn | ID tài khoản + device fingerprint |

Vì `cookie_token` chỉ sống ~2 giờ, bot **bắt buộc** phải có `stoken` mới tự cấp lại được.
Nếu không có `stoken`, mỗi khi token hết hạn bạn phải dán lại cookie mới.

**Lưu ý quan trọng:** `stoken` **không bao giờ xuất hiện trong cookie trình duyệt** —
nó chỉ được cấp trong **app HoYoLAB**. Đây là lý do bạn mở DevTools trên web sẽ không thấy.

---

## 2. Cách A — PCAPdroid (Android, không cần root, không nhập mật khẩu)

### 2.1. Cài đặt

1. Cài **PCAPdroid**:
   - F-Droid / Google Play, hoặc
   - GitHub Releases: `github.com/emanuele-f/PCAPdroid/releases`
2. Cài thêm addon **PCAPdroid-mitm** (bắt buộc để giải mã TLS).

   ⚠️ **Addon này KHÔNG có trên Google Play hay F-Droid** — chỉ phát hành trên GitHub,
   nên bạn sẽ không tìm thấy nó trong store. Tải thủ công:

   - Mở trên điện thoại: `https://github.com/emanuele-f/PCAPdroid-mitm/releases/latest`
   - Tải file APK **`PCAPdroid-mitm_v2.4_arm64-v8a.apk`** (bản mới nhất v2.4).
     *Chọn `arm64-v8a` cho gần như mọi điện thoại hiện đại; `x86_64` chỉ dành cho giả lập.*
   - Khi trình duyệt hỏi, cho phép **"Cài đặt ứng dụng không rõ nguồn gốc"** rồi cài file APK.
   - Yêu cầu tối thiểu: Android 7.0 (API 24) trở lên.

   > Link tải trực tiếp:
   > `https://github.com/emanuele-f/PCAPdroid-mitm/releases/download/v2.4/PCAPdroid-mitm_v2.4_arm64-v8a.apk`

> Nếu điện thoại đang bật VPN khác, hãy tắt trước — PCAPdroid cần dùng khe VPN.

### 2.2. Bật giải mã TLS

1. Mở **PCAPdroid** → menu **☰** → **Settings** (Cài đặt).
2. Vào **TLS decryption** → bật lên. *Setup wizard* sẽ hiện ra và dẫn từng bước:
   - **Bước 1:** cài addon `PCAPdroid-mitm` (nếu chưa cài).
   - **Bước 2:** cài **CA certificate**:
     `Cài đặt hệ thống → Bảo mật → Mã hóa & thông tin xác thực → Cài đặt chứng chỉ → Chứng chỉ CA`
     → chọn file chứng chỉ do PCAPdroid cung cấp.
     *(Một số máy ghi là "Cài đặt từ bộ nhớ" → "Chứng chỉ CA".)*
3. Quay lại **Settings** → mục **Capture** → bật **PCAPdroid extension** (tiện ích mở rộng).
4. Ở màn hình chính PCAPdroid, mục **Traffic dump** chọn **No dump** (không cần lưu file).

### 2.3. Bắt gói tin

1. Trong PCAPdroid, mở tab **Connections** (Kết nối) → bấm nút **▶ Start**.
2. Mở **app HoYoLAB** → đảm bảo đã đăng nhập → vào tab **Tôi / Profile** rồi kéo refresh.
   *(Nếu app đang đăng nhập sẵn thì không cần nhập lại mật khẩu.)*
3. Quay lại PCAPdroid → tab **Connections**:
   - Lọc theo app **HoYoLAB** (biểu tượng app).
   - **Bỏ qua các kết nối DNS** — giao thức `DNS (UDP)` chỉ là truy vấn tên miền,
     **không bao giờ chứa cookie**. Dấu hiệu: mục "Giải mã" ghi *"Không được mã hóa"*.
   - Chỉ chọn kết nối **HTTPS/TLS**. Trong tab **Tổng quan**, mục "Giải mã" phải ghi
     **"Đã giải mã"** (khoá xanh 🔓). Nếu ghi *"Không thể giải mã"* → xem mục 2.4.
   - Ưu tiên host: `api-account-os.hoyolab.com`, `sg-public-api.hoyoverse.com`,
     `bbs-api-os.hoyolab.com`, `*.hoyoverse.com`.
4. Bấm vào kết nối HTTPS đã giải mã → tab **PAYLOAD** → phần chữ bên phải sẽ hiện dạng HTTP
   (`GET /... HTTP/1.1`, các header...). Tìm dòng **`Cookie:`** → copy giá trị
   **`stoken=...`** (thường bắt đầu bằng `v2_...`).
   - Nếu không thấy ở request, tìm request **`getBySToken`**, hoặc xem **response** có dòng
     `Set-Cookie: stoken=...`.
5. Ghi lại kèm các giá trị liên quan (nếu chưa có): `ltuid_v2=...`, `ltmid_v2=...`.

> ⚠️ Nếu `stoken` bắt đầu bằng `v2_` thì **bắt buộc phải kèm `ltmid_v2`**, nếu không bot
> sẽ không làm mới được token.

### 2.4. Giới hạn cần biết

- Nếu request vẫn hiện 🔒 (khoá đỏ) = **không giải mã được**. Nguyên nhân thường gặp:
  - App dùng **certificate pinning**, hoặc
  - App **không tin chứng chỉ CA do người dùng cài** (mặc định từ Android 7+).
- Khi đó cần thiết bị **đã root + LSPosed** (module unpinning) hoặc dùng cách B.

---

## 3. Cách B — Script local `scripts/get_full_cookie.py` (KHUYẾN NGHỊ)

Không cần bắt gói tin, không cần root. Nhập email + mật khẩu **một lần, ẩn, không lưu lại**;
script dùng endpoint đăng nhập **app HoYoLAB** (cách duy nhất trả về `stoken`) rồi ghi cookie
đầy đủ thẳng vào CSDL của bot.

**Điểm mấu chốt kỹ thuật:** đăng nhập **web** (`login_with_password`) **không** trả về `stoken`;
chỉ đăng nhập **app** (`login_with_app_password`) mới có. Đó là lý do script dùng endpoint app.

### Cách chạy

Mở terminal tại thư mục dự án và chạy:

```bash
.venv/Scripts/python.exe scripts/get_full_cookie.py --discord-user-id <ID_DISCORD_CUA_BAN>
```

- `<ID_DISCORD_CUA_BAN>`: ID Discord của bạn (bật Developer Mode trong Discord → chuột phải
  vào tên mình → Copy User ID).
- Tuỳ chọn: `--game {all,genshin,hsr}`, `--uid <UID>`, `--no-save` (chỉ in cookie, không ghi CSDL).

Script sẽ hỏi email/tên đăng nhập và mật khẩu (ẩn khi gõ). Nếu HoYo yêu cầu **captcha**, một
trang web nhỏ sẽ mở ở `http://localhost:5000` để bạn giải. Nếu yêu cầu **mã xác minh email**,
nhập mã ngay trong terminal.

Khi xong, script ghi cookie vào CSDL và in chuỗi cookie ra màn hình. Sau đó vào Discord chạy
`/auto verify` rồi `/auto run tac_vu: Đổi Giftcode ngay`.

> ⚠️ Mật khẩu **không** được lưu. Chỉ cookie (đã mã hoá bằng Fernet) được ghi vào CSDL.

### Phương án tham khảo khác
- Công cụ cộng đồng: `github.com/Smexhy/hoyolab-cookie-helper` (cùng cơ chế, dùng `genshin.py`).

---

## 4. Sau khi có `stoken` — nạp vào bot

Ghép một chuỗi duy nhất (thêm `stoken` vào cookie đang có):

```
ltuid_v2=...; ltmid_v2=...; ltoken_v2=...; cookie_token_v2=...; stoken=v2_...;
```

Trong Discord:

1. `/auto session_add` → dán chuỗi trên.
2. `/auto verify` → bot kiểm tra token + thử đổi bằng mã giả (không đổi mã thật).
3. Nếu ✅ → `/auto run tac_vu: Đổi Giftcode ngay`.

Từ đây bot sẽ **tự gia hạn `cookie_token` vô thời hạn**, không cần dán lại nữa.

---

## 5. Xử lý sự cố nhanh

| Hiện tượng | Nguyên nhân | Cách xử lý |
|---|---|---|
| `/auto verify` báo token hết hạn | `cookie_token` cũ | Dán cookie mới, hoặc thêm `stoken` |
| `stoken` báo lỗi "missing mid" | Thiếu `ltmid_v2` | Thêm `ltmid_v2` vào cookie |
| Redeem vẫn lỗi `-1071` dù có `stoken` | Phiên bị thu hồi/đăng xuất | Lấy `stoken` mới |
| PCAPdroid không giải mã được request | Certificate pinning | Root + LSPosed, hoặc dùng Cách B |
