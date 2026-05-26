# Hướng dẫn cấu hình Telegram notification

Tài liệu này mô tả cách cấu hình bot Telegram để Django tự gửi thông báo khi có sự kiện vận hành mới hoặc chỉ đạo sự kiện mới.

## 1. Luồng gửi tin hiện tại

File xử lý chính:

```text
app/nhatkyvanhanh/signals.py
```

Khi app `nhatkyvanhanh` được khởi động, Django gọi `ready()` trong:

```text
app/nhatkyvanhanh/apps.py
```

Hàm `ready()` import `nhatkyvanhanh.signals`, từ đó đăng ký các signal:

- `notify_new_sukien`: gửi Telegram khi tạo mới `SuKien`.
- `notify_new_chidao`: gửi Telegram khi tạo mới `ChiDaoSuKien`.

Tin nhắn được gửi qua hàm:

```python
send_telegram_notification(text)
```

Hàm này đọc 2 cấu hình từ Django settings:

```python
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
```

Sau đó gọi Telegram API:

```text
https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/sendMessage
```

Tin nhắn đang dùng `parse_mode=HTML`, vì vậy nội dung được escape bằng `escape_html()` trước khi gửi để tránh lỗi định dạng HTML.

Việc gửi tin chạy trong background daemon thread, nên request tạo sự kiện trên web không phải chờ Telegram trả lời.

## 2. Tạo Telegram bot

1. Mở Telegram và tìm bot chính thức: `@BotFather`.
2. Gửi lệnh:

```text
/newbot
```

3. Đặt tên hiển thị cho bot, ví dụ:

```text
VSH Notification Bot
```

4. Đặt username cho bot, username phải kết thúc bằng `bot`, ví dụ:

```text
vsh_notification_bot
```

5. BotFather sẽ trả về token dạng:

```text
1234567890:AAxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

Token này là `TELEGRAM_BOT_TOKEN`.

Không đưa token lên Git hoặc gửi cho người không quản trị hệ thống.

## 3. Thêm bot vào nhóm hoặc kênh Telegram

### Gửi vào nhóm

1. Tạo nhóm Telegram hoặc mở nhóm đang dùng.
2. Thêm bot vừa tạo vào nhóm.
3. Nên cấp quyền admin cho bot nếu nhóm có cấu hình hạn chế quyền gửi tin.
4. Gửi thử một tin nhắn bất kỳ vào nhóm, ví dụ:

```text
test
```

### Gửi vào kênh

1. Thêm bot vào kênh.
2. Cấp quyền admin cho bot.
3. Bot phải có quyền đăng bài trong kênh.

## 4. Lấy TELEGRAM_CHAT_ID

Sau khi đã thêm bot vào nhóm hoặc kênh, gọi URL sau trên trình duyệt:

```text
https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/getUpdates
```

Thay `<TELEGRAM_BOT_TOKEN>` bằng token thật.

Tìm phần `chat`, ví dụ:

```json
{
  "chat": {
    "id": -1001234567890,
    "title": "Nhóm vận hành",
    "type": "supergroup"
  }
}
```

Giá trị `id` là `TELEGRAM_CHAT_ID`.

Ví dụ:

```env
TELEGRAM_CHAT_ID=-1001234567890
```

Lưu ý:

- Chat ID của group/supergroup thường là số âm.
- Supergroup thường bắt đầu bằng `-100`.
- Nếu `getUpdates` không thấy dữ liệu, hãy gửi thêm một tin nhắn mới trong nhóm rồi tải lại URL.

## 5. Cấu hình file .env

Trong file `.env` ở gốc project, thêm hoặc cập nhật:

```env
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
```

Django đang đọc 2 biến này tại:

```text
app/app/settings_base.py
```

```python
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
```

Sau khi sửa `.env`, cần restart backend Django để settings được đọc lại.

## 6. Test gửi tin thủ công

Có thể test nhanh bằng Django shell:

```powershell
cd app
python manage.py shell
```

Trong shell:

```python
from nhatkyvanhanh.signals import send_telegram_notification
send_telegram_notification("<b>Test Telegram</b>\nCấu hình gửi tin hoạt động.")
```

Nếu cấu hình đúng, nhóm hoặc kênh Telegram sẽ nhận được tin nhắn.

## 7. Test theo nghiệp vụ

Tạo mới một `SuKien` trong hệ thống:

- Nếu tạo thành công, signal `notify_new_sukien` sẽ gửi tin "CÓ SỰ KIỆN MỚI".

Tạo mới một `ChiDaoSuKien` cho sự kiện:

- Nếu tạo thành công, signal `notify_new_chidao` sẽ gửi tin "CÓ CHỈ ĐẠO MỚI CHO SỰ KIỆN".

Signal chỉ gửi khi bản ghi được tạo mới. Nếu chỉ sửa bản ghi cũ thì hiện tại không gửi Telegram.

## 8. Xử lý lỗi thường gặp

### Không nhận được tin

Kiểm tra:

- `.env` đã có `TELEGRAM_BOT_TOKEN` và `TELEGRAM_CHAT_ID`.
- Backend Django đã được restart sau khi sửa `.env`.
- Bot đã được thêm vào đúng nhóm hoặc kênh.
- Bot có quyền gửi tin.
- `TELEGRAM_CHAT_ID` đúng, đặc biệt với supergroup thường có dạng `-100...`.

### Log báo thiếu token hoặc chat id

Nếu log có dòng:

```text
Telegram Bot Token or Chat ID is not configured in Django settings.
```

Nghĩa là Django chưa đọc được một trong hai biến môi trường:

```env
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
```

Kiểm tra lại file `.env` và cách load biến môi trường khi chạy backend.

### Telegram API trả lỗi

Nếu log có dạng:

```text
Telegram API error (status ...): ...
```

Thường là do:

- Token sai hoặc đã bị thu hồi.
- Chat ID sai.
- Bot chưa nằm trong nhóm/kênh.
- Bot không có quyền gửi tin.

## 9. Lưu ý bảo mật

- Không commit token thật lên Git.
- Nếu token đã bị lộ, vào `@BotFather` dùng lệnh `/revoke` để tạo token mới.
- Sau khi đổi token, cập nhật lại `.env` và restart backend.

