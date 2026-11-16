# Shini Tasks Constitution

## Core Principles

### I. Local-First, Không Tài Khoản

Mọi dữ liệu của người dùng MUST nằm trên máy của chính họ. Không tính năng nào
được phép yêu cầu tài khoản, máy chủ đám mây, hay kết nối mạng mới hoạt động.
Các dịch vụ ngoài (kiểm tra bản mới, thông báo Telegram, AI điền form) chỉ là
lớp cộng thêm tuỳ chọn: khi vắng mặt hoặc lỗi, chúng MUST suy giảm êm (bỏ qua
và báo rõ), không bao giờ chặn luồng chính.

*Rationale*: đây là định vị của sản phẩm — app việc cá nhân chạy hoàn toàn
local là lý do người dùng chọn nó thay vì các SaaS quản lý việc.

### II. Dữ Liệu Không Bao Giờ Mất

Xoá MUST luôn khôi phục được: việc xoá vào thùng rác và chỉ bị xoá hẳn sau
30 ngày; việc đã xong được lưu trữ phục vụ thống kê trước khi dọn sau 15 ngày;
sao lưu tự động MUST chạy hằng ngày; khôi phục sao lưu MUST chụp lại dữ liệu
hiện tại trước khi thay; nhập dữ liệu (import/sync) MUST NOT làm sống lại bản
ghi đã bị dọn. Mọi thay đổi schema MUST có đường migration giữ nguyên dữ liệu
cũ và MUST được kiểm thử trên bản sao của dữ liệu thật trước khi chạm vào bản
thật.

*Rationale*: dữ liệu việc làm là thứ người dùng không thể tạo lại; một lần mất
dữ liệu là mất luôn niềm tin vào sản phẩm.

### III. Đọc Rõ Ở Cả Hai Theme — Ghim Màu Mọi Bề Mặt

Mọi bề mặt và mọi dòng chữ nhìn thấy được MUST có màu được ghim tường minh cho
CẢ theme sáng và theme tối. Không phần tử giao diện nào được dựa vào màu mặc
định của theme hệ thống (bài học theme "Sweet": popup Adw.Dialog ra khung đen,
chữ trong danh sách thả xuống của DropDown bị chìm). Mỗi thay đổi giao diện
MUST được quét đủ mọi trạng thái — hộp thoại, menu, popup thả xuống, lịch,
nút ở mọi trạng thái — ở cả hai theme trước khi coi là xong.

*Rationale*: ba lỗi đọc-không-được liên tiếp (v1.1.1, v1.6.1, v1.6.2) đều từ
cùng một gốc: tin vào mặc định của theme hệ thống.

### IV. Ghi Việc Trong Vài Giây

Thêm một việc MUST làm được trong vài giây từ bất cứ đâu: ô nhập nhanh hiểu
ngôn ngữ tự nhiên tiếng Việt (hạn, mức ưu tiên, nhãn, người làm, quy tắc lặp),
cửa sổ bắt việc toàn cục bằng phím tắt, và đường ghi việc từ điện thoại. Văn
bản dài hoặc nhiều dòng MUST được suy luận thành việc/việc con một cách đoán
được, và bản xem trước phân tích MUST cho người dùng thấy máy hiểu gì trước
khi lưu.

*Rationale*: một app việc thắng ở tốc độ ghi lại ý nghĩ; ghi chậm là mất việc.

### V. Sửa Không Bao Giờ Mất Lặng Lẽ

Mọi thay đổi của người dùng MUST hoặc được lưu ngay, hoặc khi đóng trình sửa
mà còn chữ chưa lưu thì MUST hỏi rõ: Lưu và đóng / Bỏ thay đổi / Ở lại. Xung
đột lịch (hai việc chồng giờ nhau) MUST bị chặn kèm giải thích, không bao giờ
lặng lẽ xếp chồng. Việc lặp MUST sinh kỳ tiếp theo một cách đoán được (đánh
dấu xong hoặc bỏ qua một kỳ), và việc con của kỳ mới MUST bắt đầu lại từ đầu.

*Rationale*: mất một dòng chữ đang gõ dở, hay một lịch bị chồng mà không báo,
đều là lỗi phá niềm tin ngang với mất dữ liệu.

### VI. Một Khung Thống Nhất, Spec Là Nguồn Sự Thật

Điều hướng chỉ sống ở thanh bên; bảng, danh sách, lịch, hôm nay, Gantt, sơ đồ
và thống kê là các cách NHÌN của cùng một dữ liệu, không phải các màn hình
riêng lẻ. Thẻ việc chỉ mang tối đa ~5 tín hiệu liếc nhanh cộng toàn bộ việc
con hiển thị đầy đủ; chi tiết của mọi việc mở trong cùng một popup lớp phủ
mềm. Mọi việc MỚI — dự án, tính năng, sản phẩm — MUST bắt đầu bằng Spec Kit:
dựng khung constitution → spec → plan → tasks trước khi viết code. Không
hiểu luồng thì MUST hỏi chủ dự án cho tới khi hiểu mới ghi; điểm chưa rõ ghi
`[NEEDS CLARIFICATION: ...]` chứ không đoán. Spec là nguồn sự thật: đổi yêu
cầu thì sửa spec trước, rồi plan, tasks, test, cuối cùng mới code. Trước khi
làm phải đọc lại các file md liên quan; có sửa gì thì cập nhật ngược vào đúng
file md đó trong cùng một vòng.

*Rationale*: dự án này đã trả giá cho kiểu "vá đâu hay đó" bằng một cuộc đại
tu khung (v1.5.0) và nhiều vòng đảo quyết định; spec sống là cách giữ mọi
quyết định đã chốt không bị dựng lại hay làm ngược lại.

### VII. Kiểm Chứng Trước Khi Nói Xong

Không thay đổi nào được báo "xong" khi chưa kiểm chứng ở nơi người dùng sẽ
nhìn thấy: giao diện bằng ảnh render thật ở cả hai theme, engine bằng test
trên bản sao dữ liệu, phát hành bằng CI xanh và bản cài dựng thành công. Mỗi
tiêu chí nghiệm thu Given / When / Then trong spec của tính năng mới MUST
thành một test tự động viết trước code; test chưa xanh thì việc chưa xong.
Số liệu hệ thống không đo được MUST hiện "chưa có số đo", không bao giờ bịa.

*Rationale*: "agent nói xong" không phải là xong — bằng chứng kiểm chứng mới
là xong.

## Ranh Giới Cứng & Ràng Buộc

- MUST NOT hứa hay xây tự động hoá tài khoản Zalo cá nhân; kênh thông báo ra
  điện thoại là Telegram (bot của chính người dùng) và thông báo desktop.
- Thông tin nhạy cảm (token bot, khoá API) MUST chỉ lưu local, chỉ hiển thị
  tối đa 4 ký tự cuối, không bao giờ vào log, repo hay bộ nhớ hội thoại.
- File đính kèm sống theo từng máy và KHÔNG đi theo khi đồng bộ/xuất dữ
  liệu — giới hạn này MUST được nói rõ trong ghi chú phát hành.
- Thông báo trên Windows không có nút hành động — MUST nói rõ thay vì giả vờ
  tương đương với Linux.
- Thời gian "làm thật" chỉ đến từ đồng hồ bấm giờ trong app; mọi con số ước
  lượng MUST được ghi nhãn là ước lượng.
- Repo công khai: MUST NOT chứa IP/Tailscale/đường dẫn máy riêng/mật khẩu
  hay dữ liệu cá nhân của bất kỳ ai.

## Quy Trình Phát Triển & Phát Hành

- Luồng Spec Kit cho việc mới: constitution (một lần cho dự án) → specify →
  clarify (khi có điểm mờ) → plan → checklist → tasks → analyze → implement →
  converge. Dừng ở cổng duyệt sau specify, sau plan và sau tasks, trừ khi chủ
  dự án đã yêu cầu chạy trọn gói.
- `muse.md` ở gốc repo là nhật ký làm việc và lịch sử quyết định; constitution
  này là văn bản quy phạm. Khi hai bên lệch nhau, constitution thắng và
  `muse.md` MUST được sửa lại cho khớp.
- Phát hành: bump đủ 4 nơi — `VERSION` trong `server.py` và `app.py`,
  `AppVersion` trong `packaging/ShiniTasks.iss`, badge trong `README.md` —
  kèm ghi chú phát hành tiếng Việt; commit dưới danh tính của chủ dự án.
- File test/probe/script tạm MUST NOT vào commit phát hành; chúng sống ngoài
  repo hoặc ở thư mục tạm.
- Trước mọi thao tác trên máy thật của người dùng: báo trước làm gì, máy nào,
  khi nào; không bao giờ bơm phím/chuột vào phiên đang dùng.

## Governance

Constitution này đứng trên mọi thói quen và tài liệu làm việc khác của dự án.
Sửa đổi constitution MUST đi kèm: lý do, tăng phiên bản theo quy tắc bên dưới,
và một Sync Impact Report; sửa đổi có hiệu lực khi chủ dự án duyệt. Mọi plan
và đợt rà soát (analyze/converge) MUST đối chiếu công việc với constitution;
điểm nào không tuân thủ phải được nêu tên và hoặc sửa, hoặc xin sửa
constitution trước — không lặng lẽ bỏ qua.

Phiên bản constitution theo semver: MAJOR khi gỡ hoặc định nghĩa lại một
nguyên tắc theo hướng không tương thích ngược; MINOR khi thêm nguyên tắc/mục
mới hoặc mở rộng đáng kể; PATCH khi chỉ làm rõ câu chữ. `muse.md` ghi lại
toàn bộ quá trình áp dụng; constitution chỉ giữ phần quy phạm hiện hành.

**Version**: 1.0.0 | **Ratified**: 2026-11-16 | **Last Amended**: 2026-11-16
