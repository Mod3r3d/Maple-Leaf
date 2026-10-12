# Kế hoạch khắc phục Giftcode Redeem

## Mục tiêu

Đảm bảo lệnh `/giftcode redeem` và tác vụ Auto Redeem dùng đúng tài khoản, xác thực được session HoYoLAB, gửi mã đúng định dạng và trả kết quả dễ hiểu. Tham khảo cách Hoyo Buddy gắn client redeem với tài khoản, xử lý danh sách mã và báo lỗi theo kết quả provider; giữ kiến trúc service và hàng đợi hiện có của bot.

## Chẩn đoán hiện tại

- `SessionRepository.save_session` đặt session thành `VALID` mà chưa xác nhận cookie có token đổi mã.
- UI coi `cookie_token` hoặc `stoken` là dấu hiệu sẵn sàng, trong khi làm mới token bằng `stoken` còn cần thông tin `mid` phù hợp. Trạng thái hiển thị có thể lạc quan hơn khả năng thực tế.
- Redeem thủ công và tự động có điều kiện chạy khác nhau: thủ công dùng tài khoản mặc định; tự động còn cần automation bật, session hợp lệ và giftcode hoạt động.
- Đầu vào thủ công chỉ được `strip()` và viết hoa. Dán URL trang đổi mã sẽ gửi nguyên URL cho provider.
- `dry-run` có thể ghi nhận thành công giả lập mà không gọi API HoYoverse.
- Provider hiện trả trạng thái nhưng lệnh Discord chủ yếu hiển thị mã trạng thái thô; người dùng khó phân biệt lỗi cookie, mã, khu vực hay kết nối.

## Phạm vi sửa

### 1. Chuẩn hóa đầu vào mã

- Thêm một hàm chuẩn hóa dùng chung cho redeem thủ công và tự động.
- Chấp nhận mã thuần và URL; với URL, đọc tham số `code` bằng bộ phân tích URL và giải mã giá trị đúng cách.
- Chuẩn hóa khoảng trắng và chữ hoa; từ chối chuỗi rỗng hoặc định dạng không hợp lệ trước khi gọi HoYoLAB.
- Giữ rõ ngữ cảnh game; không tự chọn giftcode của game khác.

### 2. Làm rõ trạng thái session và khả năng redeem

- Phân biệt session được lưu với session đã có token cần cho redeem.
- Điều chỉnh thông báo trong `/auto session_view` và luồng thêm cookie để nêu chính xác token nào còn thiếu.
- Chỉ đánh dấu session `EXPIRED` khi provider xác nhận lỗi xác thực; không coi session `VALID` trong database là bằng chứng token redeem còn dùng được.
- Khi refresh bằng `stoken`, kiểm tra đủ dữ liệu cần thiết trước khi gọi refresh; lưu cookie mới qua `SessionRepository` như hiện tại.
- Không ghi cookie hoặc token nhạy cảm vào log hay phản hồi Discord.

### 3. Đồng nhất xử lý kết quả provider

- Giữ một service chung làm đầu mối cho redeem thủ công và Auto Redeem.
- Chuẩn hóa ánh xạ lỗi provider thành các trạng thái dễ xử lý: thành công, đã đổi, mã sai/hết hạn, không đủ điều kiện, giới hạn vùng, cần đăng nhập, giới hạn tốc độ và lỗi mạng.
- Bổ sung thông báo thân thiện cho `/giftcode redeem`, đồng thời giữ thông tin chẩn đoán không nhạy cảm trong log.
- Không retry các lỗi dứt điểm hoặc lỗi xác thực; chỉ retry lỗi mạng/time-out/rate limit theo backoff đã có.

### 4. Kiểm tra điều kiện của Auto Redeem

- Xác nhận task chỉ xử lý account đã bật `automation_enabled` và `redeem_enabled`, có session phù hợp, và giftcode thuộc đúng game.
- Xác nhận job `AUTH_REQUIRED` không bị đưa lại vào hàng đợi vô hạn; hướng người dùng cập nhật cookie.
- Hiển thị rõ số job được đưa vào, xử lý, thành công và lỗi trong kết quả tác vụ.
- Khi `AUTOMATION_MODE=dry-run`, ghi rõ đây là mô phỏng và không thông báo như một lần nhận thưởng thật.

## Trình tự triển khai

1. Ghi nhận cấu hình môi trường đang chạy: `AUTOMATION_MODE`, game, account mặc định, trạng thái opt-in và loại token cookie hiện có (chỉ ghi nhận tên token, không ghi giá trị).
2. Sửa hàm chuẩn hóa mã và dùng nó trong service redeem.
3. Sửa kiểm tra/trình bày trạng thái session để phân biệt token điểm danh, token redeem và khả năng refresh.
4. Chuẩn hóa lỗi provider và phản hồi lệnh Discord.
5. Rà soát điều kiện Auto Redeem, trạng thái job, retry và thông báo chế độ dry-run.
6. Sau khi thay đổi được yêu cầu kiểm chứng, kiểm tra riêng: mã thuần, URL redeem, thiếu token, token hết hạn, mỗi trạng thái lỗi provider, dry-run và luồng queue.

## Tiêu chí hoàn thành

- Mã thuần và URL chứa `?code=...` đều được chuẩn hóa thành đúng giftcode trước khi gửi provider.
- Cookie thiếu token redeem không được báo “sẵn sàng đổi mã” một cách gây hiểu nhầm; hướng dẫn nêu rõ cách cập nhật cookie.
- Lệnh thủ công chọn đúng tài khoản theo game và trả thông báo tiếng Việt hữu ích cho kết quả thành công/lỗi.
- Auto Redeem chỉ xử lý đúng account/game đã bật; lỗi xác thực không retry liên tục; lỗi tạm thời tuân thủ backoff.
- Dry-run được nhận diện là mô phỏng trong log và thông báo.
- Không làm lộ cookie/token; không làm mất thay đổi hiện có ngoài phạm vi redeem.

## Tham khảo

- ZIP do người dùng cung cấp: `hoyo-buddy-main/hoyo_buddy/hoyo/auto_tasks/auto_redeem.py` và `hoyo-buddy-main/hoyo_buddy/ui/hoyo/redeem.py`.
- Mã nguồn Hoyo Buddy: [auto_redeem.py](https://github.com/seriaati/hoyo-buddy/blob/main/hoyo_buddy/hoyo/auto_tasks/auto_redeem.py) và [redeem.py](https://github.com/seriaati/hoyo-buddy/blob/main/hoyo_buddy/ui/hoyo/redeem.py).
- Các file liên quan trong workspace: `app/automation/client.py`, `app/automation/providers/hoyolab.py`, `app/services/redeem_service.py`, `app/commands/giftcode.py`, `app/automation/tasks/giftcode_tasks.py`, `app/db/repositories/automation.py`, `app/ui/automation/views.py`.
