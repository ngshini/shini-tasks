# Shini Tasks — dùng từ điện thoại (hướng D, 2026-11-10)

Địa chỉ engine trên mạng Tailscale: **http://<IP-TAILSCALE-CUA-MAY-BAN>:8790**
Điều kiện: điện thoại cài app **Tailscale** và đăng nhập cùng tài khoản với máy Linux.

## 1) Phím tắt iOS "Thêm việc nhanh" (tạo 1 lần, ~1 phút)

Mở app **Phím tắt (Shortcuts)** → dấu **+** → đặt tên "Thêm việc Shini" → thêm lần lượt 3 hành động:

1. **Yêu cầu nhập** (Ask for Input) — kiểu: Văn bản, lời nhắc: `Việc gì?`
   (Muốn rảnh tay hơn: thay bằng hành động **Đọc chính tả văn bản** / Dictate Text.)
2. **Lấy nội dung của URL** (Get Contents of URL):
   - URL: `http://<IP-TAILSCALE-CUA-MAY-BAN>:8790/api/quick`
   - Bấm "Hiển thị thêm": Phương thức = **POST**, Kiểu nội dung = **JSON**
   - Thêm 2 trường: `text` = biến **Đầu vào đã cung cấp** (kết quả của bước 1), `source` = `ios-shortcut`
   - **Thêm tiêu đề (Header)**: khóa `X-Token`, giá trị = token API của bạn (mở app trên
     máy tính → ⚙ Cài đặt → mục TOKEN API → "Sao chép token" rồi dán vào đây).
     Từ bản vá bảo mật 2026-11-17, engine không nhận yêu cầu nào thiếu token này.
3. **Hiển thị thông báo** (Show Notification): nội dung `Đã thêm việc vào Shini Tasks ✓`

Xong. Thêm phím tắt ra màn hình chính hoặc gán vào nút Tác vụ (Action Button) / chạm mặt lưng.
Thử gõ: `tập thể dục mỗi T2 T4 T6 lúc 6h lặp 12 lần` — việc sẽ vào app với đúng quy tắc lặp.

> Cách dự phòng không cần cài gì: mở app trên máy tính và thêm như thường.

## 2) Xem việc trên lịch điện thoại (ICS, một chiều)

Engine phát lịch tại: **http://<IP-TAILSCALE-CUA-MAY-BAN>:8790/api/calendar.ics?token=<TOKEN-API-CUA-BAN>**
(thêm `?token=` ở cuối — app lịch không gửi được header nên token đi theo URL; token lấy ở ⚙ Cài đặt như trên)

- **iPhone**: Cài đặt → Lịch → Tài khoản → Thêm tài khoản → Khác → Thêm Lịch đã đăng ký → dán địa chỉ trên.
- **Google Calendar** (trên máy tính): Cài đặt → Thêm lịch → Từ URL → dán địa chỉ trên.

Việc có giờ thành sự kiện giờ; việc chỉ có ngày thành sự kiện cả ngày. Lịch tự làm mới theo lịch của app lịch (không tức thì — đây là kênh chỉ-xem).

## 3) Câu thêm nhanh hiểu thêm những gì (từ 2026-11-10)

- `mỗi ngày` / `mỗi sáng` / `hằng ngày` → lặp mỗi ngày
- `mỗi tuần` / `mỗi tháng` → lặp mỗi tuần / mỗi tháng
- `mỗi T2 T4 T6`, `mỗi thứ 3, thứ 5`, `mỗi CN` → lặp vào các thứ đã chọn (ngày đầu = thứ khớp gần nhất)
- `lặp 12 lần` → tổng cộng 12 lần · `lặp thêm 3 lần` → thêm 3 lần nữa
- Việc lặp chưa ghi ngày thì lần đầu tính là hôm nay.
