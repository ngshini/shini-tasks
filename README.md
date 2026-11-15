# Shini Tasks — app quản lý việc cá nhân trên máy tính

Bảng cột nhắc việc chạy **ngay trên máy của bạn**: dữ liệu lưu local (SQLite),
không tài khoản, không đám mây. Dữ liệu của bạn không bao giờ rời máy — app chỉ
tự kiểm tra bản mới trên GitHub mỗi ngày một lần (không gửi kèm dữ liệu cá nhân nào).

![Phiên bản](https://img.shields.io/badge/version-1.4.1-blue) ![Windows](https://img.shields.io/badge/Windows-Setup.exe-green) ![Linux](https://img.shields.io/badge/Linux-chạy%20từ%20source-orange)

## Cài đặt

### Windows
1. Tải **ShiniTasks-Setup.exe** ở mục [Releases](../../releases) → chạy → trình cài tiếng Việt.
2. Nếu Windows SmartScreen cảnh báo (bản cài chưa có chữ ký số): bấm **More info → Run anyway**.
3. Lần đầu engine chạy, Firewall hỏi thì bấm **Allow** (để điện thoại truy cập qua mạng nội bộ/Tailscale).
4. Engine tự chạy khi đăng nhập Windows; mở app mà engine chưa chạy thì app tự bật. Gỡ cài đặt **không xoá dữ liệu**.

### Linux
Cần Python 3 + GTK4 + Libadwaita (PyGObject). Chạy engine `python3 server.py`
(nên đặt làm systemd user service) và app desktop `python3 app.py`.

## Chức năng chính
- **Nhiều dự án**: mỗi dự án có bộ cột Kanban riêng; thanh bên gọn theo mẫu Todoist (cột của dự án nằm ngay dưới tên dự án), chuyển dự án ngay trên thanh công cụ.
- **Bảng cột tuỳ biến**: tự thêm/đổi tên/đổi màu cột, kéo-thả việc giữa các cột, kéo vào cột Đã xong để hoàn thành.
- **Bình luận + tệp đính kèm** trong từng việc (file lưu trên từng máy, không đi theo khi đồng bộ); ngày bắt đầu + người được giao cho mỗi việc.
- **4 mức ưu tiên đặt tên tuỳ ý** (mặc định: Làm ngay / Quan trọng / Gấp / Thường), nhãn #tag (có quản lý: đổi tên/gỡ nhãn hàng loạt), việc con (checklist) ngay trên thẻ.
- **Đồng hồ bấm giờ**: ghi thời gian làm THẬT cho từng việc, thống kê hiện riêng giờ thật vs ước lượng.
- **Thùng rác**: xoá việc là vào thùng rác 30 ngày, khôi phục được — không còn xoá là mất luôn.
- **Tìm mọi nơi** (Enter trong ô tìm): mọi dự án, cả việc đã xong, khớp cả trong bình luận.
- **Lịch tuần kiểu Google Calendar**: bấm ô trống để tạo việc, kéo để dời giờ, tự xếp lịch, **chặn trùng giờ** khi lưu.
- **Trang Hôm nay + Thống kê**: chuỗi ngày liên tiếp, so sánh tuần, đúng-hạn %, tỉ lệ hoàn thành, sắp đến hạn, xuất báo cáo tuần ra ảnh PNG.
- **Việc lặp nâng cao**: mỗi ngày/tuần/tháng, lặp theo thứ (T2, T4, T6…), giới hạn số lần, **bỏ qua một kỳ** khi bận; việc con tự reset mỗi lần lặp.
- **Nhắc việc**: thông báo trước hạn, quá hạn 30 phút nhắc lại mức khẩn, bản tin 07:30 sáng + xem trước 20:30 tối.
- **Đồng bộ 2 máy** (cùng mạng/Tailscale) và xuất/nhập JSON, xuất CSV cho Excel; engine tự sao lưu database mỗi ngày (giữ 14 bản) và **khôi phục từ bản sao lưu ngay trong app**.
- **Tự dọn dẹp**: việc đã xong quá 15 ngày tự xoá khỏi bảng cho gọn — nhưng vẫn tính đầy đủ trong thống kê (chuỗi ngày, đúng hạn, theo cột).
- **Tự báo bản mới**: mỗi ngày app kiểm tra GitHub một lần; có bản mới là hiện nút ⬆ ngay trên thanh tiêu đề — bấm vào là mở trang tải.

## Thêm việc siêu nhanh
- **Alt+E** ở bất kỳ đâu: cửa sổ bắt việc — dán một đoạn chữ, một danh sách nhiều dòng, hay một câu tự nhiên đều được.
- **Câu tự nhiên tiếng Việt** trong ô thêm nhanh, ví dụ:
  `Mai 9h họp team !gấp #work 30p nhắc 15p`
  `tập thể dục mỗi T2 T4 T6 lúc 6h lặp 12 lần`
  Cú pháp: ngày (`mai`, `thứ 6`, `20/11`) · giờ (`9h`, `14h30`) · `!gấp` `!quan trọng` ·
  `#nhãn` · thời lượng (`30p`, `1h30`) · `nhắc 15p` · lặp (`mỗi ngày`, `mỗi T2 T4`, `lặp 12 lần`).
- **Điện thoại**: phím tắt iOS/Android gọi `POST /api/quick` qua Tailscale; xem lịch qua
  `GET /api/calendar.ics` (đăng ký vào lịch iPhone/Google Calendar). Xem file `HUONG-DAN-DIEN-THOAI.md`.
- **File inbox**: ghi mỗi việc 1 dòng vào `inbox.txt` trong thư mục dữ liệu — app tự nhặt trong 5 giây.

## Dữ liệu nằm ở đâu
- Windows: `%APPDATA%\Shini Tasks` (tasks.db, settings.json, inbox.txt, backups/)
- Linux: ngay trong thư mục app.
Muốn khoá API ghi: đặt biến môi trường `SHINI_TASKS_TOKEN` rồi gửi kèm header `X-Token`.

## API chính
`GET /api/tasks` · `POST /api/tasks` · `POST /api/quick` · `PATCH /api/tasks/<id>` ·
`DELETE /api/tasks/<id>` · `POST /api/tasks/<id>/done` · `GET /api/stats` ·
`GET /api/export` · `POST /api/import` · `GET /api/calendar.ics`
