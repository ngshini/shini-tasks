# Feature Specification: Luồng Hoạt Động Toàn Hệ Thống Shini Tasks

**Feature Branch**: `001-luong-hoat-dong`

**Created**: 2026-11-16

**Status**: Approved (as-built — mô tả hệ thống đang chạy v1.6.2)

**Input**: User description: "dùng skill speckit để ghi lại được luồng hoạt
động rồi ghi lại quy định thống nhất toàn bộ hệ thống" — chủ dự án yêu cầu
ghi lại toàn bộ luồng hoạt động của Shini Tasks thành spec, làm nền cho mọi
phát triển về sau theo quy trình Spec Kit.

## CÁI GÌ

Shini Tasks là app quản lý việc cá nhân chạy hoàn toàn trên máy người dùng:
ghi việc trong vài giây, tổ chức theo dự án và cột, lên lịch theo thời gian,
nhắc trước hạn, đo thời gian làm thật, tự đánh giá việc đã xong, và giữ dữ
liệu an toàn bằng sao lưu/đồng bộ — tất cả không cần tài khoản.

## VÌ SAO

Người dùng cá nhân cần một nơi duy nhất để (1) không quên việc, (2) nhìn
thấy ngay hôm nay phải làm gì, (3) biết mình đã làm được bao nhiêu — mà
không phụ thuộc mạng, không bị khoá vào một dịch vụ đám mây. Tài liệu này
chốt toàn bộ luồng đó thành nguồn sự thật: mọi thay đổi về sau sửa ở đây
trước, rồi mới tới plan, tasks, test và code.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ghi việc trong vài giây (Priority: P1)

Người dùng nảy ra một việc ở bất cứ đâu — đang trong app, đang ở app khác,
hay đang cầm điện thoại — và ghi lại xong trong vài giây, kèm hạn, mức ưu
tiên, nhãn, người làm và quy tắc lặp được máy tự hiểu từ câu chữ tiếng Việt.

**Why this priority**: ghi chậm là mất việc; đây là cửa ngõ của mọi luồng
khác.

**Independent Test**: gõ một câu có hạn và độ ưu tiên vào ô nhập nhanh, xem
trước cách máy hiểu, lưu — việc xuất hiện đúng cột với đúng hạn.

**Acceptance Scenarios**:

1. **Given** ô nhập nhanh đang trống, **When** người dùng gõ "Họp nhóm mai
   9h #gap @minh" và nhấn Thêm, **Then** việc được tạo ở cột đầu của dự án
   hiện tại với hạn là ngày mai 09:00, mức ưu tiên cao nhất và người làm là
   "minh".
2. **Given** người dùng đang gõ, **When** nội dung có ngày/giờ/lặp, **Then**
   dòng xem trước hiện các mảnh đã hiểu (hạn, lặp, ưu tiên) trước khi lưu.
3. **Given** người dùng ở bất kỳ app nào trên máy, **When** nhấn phím tắt
   toàn cục của cửa sổ bắt việc, **Then** cửa sổ bắt việc mở với vùng chọn
   hiện tại (hoặc clipboard) điền sẵn; Enter là lưu xong, nhiều dòng dán vào
   thành nhiều việc.
4. **Given** người dùng dán một đoạn dài nhiều câu, **When** lưu, **Then**
   đoạn đó thành một việc: dòng đầu là tiêu đề, toàn văn nằm trong mô tả.
5. **Given** người dùng đã nhập khoá AI của mình, **When** gõ một câu tự
   nhiên và bấm nút AI, **Then** AI điền sẵn tiêu đề/hạn/ước lượng/việc con
   và popup chi tiết mở ra để người dùng duyệt trước khi coi là xong.
6. **Given** điện thoại và máy tính cùng mạng riêng của người dùng, **When**
   người dùng gửi một câu từ phím tắt trên điện thoại, **Then** việc xuất
   hiện trong app trên máy tính.

---

### User Story 2 - Tổ chức theo dự án và cột (Priority: P1)

Người dùng chia công việc thành các dự án; mỗi dự án có các cột trạng thái
riêng do mình đặt tên, tô màu, sắp xếp. Việc di chuyển giữa các cột bằng
kéo-thả; một cột có thể được ghim xem riêng khi cần tập trung.

**Why this priority**: đây là khung xương tổ chức — không có nó, danh sách
việc phẳng sẽ chìm trong vài chục việc.

**Independent Test**: tạo dự án mới (có sẵn 3 cột mặc định), thêm cột, kéo
một việc sang cột khác, lưu trữ dự án — bảng thay đổi đúng từng bước.

**Acceptance Scenarios**:

1. **Given** một dự án mới được tạo, **When** nó xuất hiện lần đầu, **Then**
   nó có sẵn 3 cột "Cần làm / Đang làm / Hoàn thành" và là dự án đang chọn.
2. **Given** bảng đang hiện, **When** người dùng kéo một thẻ việc sang cột
   khác, **Then** việc thuộc về cột đó ngay, và kéo thả vào cột đã xong
   tương đương đánh dấu hoàn thành.
3. **Given** người dùng bấm vào tiêu đề một cột trên bảng, **When** chế độ
   xem một cột bật, **Then** bảng chỉ hiện cột đó kèm một dải băng rõ ràng
   báo đang xem một cột và nút thoát về xem tất cả.
4. **Given** một dự án không còn dùng, **When** người dùng lưu trữ nó,
   **Then** nó biến khỏi danh sách dự án đang hoạt động nhưng khôi phục lại
   được nguyên trạng từ mục đã lưu trữ.
5. **Given** người dùng xoá cột đang có việc, **When** xác nhận, **Then**
   các việc trong cột rơi về cột đầu tiên của cùng dự án — không việc nào
   mất.

---

### User Story 3 - Mở việc và sửa chi tiết không mất chữ (Priority: P1)

Mọi việc mở ra trong cùng một popup lớp phủ mềm nổi giữa màn hình trên nền
mờ; bấm ra ngoài, bấm ✕ hoặc Esc để đóng. Mỗi trường tự lưu khi đổi; riêng
các ô gõ chữ (tiêu đề, mô tả, người làm, nhãn, số phút) nếu đóng lúc đang
gõ dở thì app hỏi lưu hay bỏ. Trên thẻ, toàn bộ việc con hiện đầy đủ, chữ
dài tự xuống dòng, bấm vòng tròn là tích xong việc con ngay tại thẻ.

**Why this priority**: popup chi tiết là nơi người dùng sống lâu nhất trong
app; mất chữ hay chữ bị cắt đều phá niềm tin ngay lập tức.

**Independent Test**: mở một việc, gõ sửa tiêu đề mà không nhấn Enter, bấm
ra vùng mờ — hộp hỏi xuất hiện; chọn Lưu và đóng, mở lại thấy tiêu đề mới.

**Acceptance Scenarios**:

1. **Given** một việc bất kỳ ở bất kỳ cách nhìn nào, **When** người dùng
   bấm vào nó, **Then** popup chi tiết mở ở giữa màn hình trên nền mờ, hiển
   thị đầy đủ mọi trường của việc đó.
2. **Given** popup đang mở và không có thay đổi chưa lưu, **When** người
   dùng bấm vào vùng mờ xung quanh, **Then** popup đóng ngay không hỏi.
3. **Given** người dùng vừa gõ sửa trong một ô chữ mà chưa lưu, **When**
   đóng popup bằng bất kỳ đường nào (✕ / Esc / bấm ra ngoài), **Then** app
   hỏi "Lưu và đóng / Bỏ thay đổi / Ở lại" và chỉ đóng theo lựa chọn đó.
4. **Given** một thẻ có nhiều việc con với chữ dài, **When** nhìn ở cột,
   **Then** tất cả việc con đều hiện, không giới hạn số lượng, không bị cắt
   chữ — chữ dài tự xuống dòng trọn vẹn.
5. **Given** một việc con chưa xong, **When** người dùng bấm vòng tròn cạnh
   nó ngay trên thẻ, **Then** việc con thành đã xong (gạch ngang) mà không
   cần mở popup.
6. **Given** bất kỳ ô chọn thả xuống nào trong app, **When** bung danh sách
   xuống, **Then** chữ bên trong rõ nét ở cả theme sáng và tối, hàng đang
   chọn được tô nổi bật.

---

### User Story 4 - Lên lịch theo thời gian (Priority: P2)

Người dùng đặt ngày bắt đầu, hạn và giờ cho việc; xem việc trên lưới lịch
tuần/ngày; kéo thả để đổi giờ, kéo mép để đổi độ dài. Hai việc không bao
giờ được xếp chồng giờ lặng lẽ. Việc lặp theo ngày/tuần/tháng hoặc theo thứ
trong tuần, có thể giới hạn số kỳ; xong một kỳ thì kỳ sau tự sinh, hoặc bỏ
qua một kỳ. Nút tự xếp lịch gom các việc chưa có giờ vào các khe trống.

**Why this priority**: hạn mà không có giờ và vị trí trên lịch thì vẫn dễ
trôi; lịch là nơi cam kết thời gian thành hình.

**Independent Test**: tạo việc có giờ trùng việc khác — bị chặn kèm giải
thích; kéo việc sang khe trống — lưu được; đánh dấu xong một việc lặp theo
thứ — kỳ sau xuất hiện đúng thứ đã chọn.

**Acceptance Scenarios**:

1. **Given** hai việc cùng ngày, **When** người dùng đặt giờ cho việc thứ
   hai chồng lên việc thứ nhất, **Then** việc lưu bị chặn và app nói rõ
   đang trùng với việc nào.
2. **Given** lưới lịch tuần, **When** người dùng bấm vào một ô giờ trống,
   **Then** một việc mới được tạo với ngày/giờ điền sẵn từ ô đó.
3. **Given** một việc lặp "mỗi thứ 2, 4, 6", **When** người dùng đánh dấu
   xong kỳ hiện tại, **Then** kỳ tiếp theo xuất hiện vào thứ kế tiếp trong
   quy tắc, với việc con được làm mới lại từ đầu.
4. **Given** một việc lặp chưa tới hạn, **When** người dùng chọn "Bỏ qua kỳ
   này", **Then** kỳ hiện tại biến mất và kỳ sau xuất hiện đúng quy tắc.
5. **Given** vài việc có hạn hôm nay nhưng chưa có giờ, **When** người dùng
   bấm Tự xếp, **Then** các việc được đặt vào khe trống 07:00–21:00 theo
   từng ô 30 phút, không chồng nhau.

---

### User Story 5 - Làm việc, ghi dấu quá trình (Priority: P2)

Trong popup chi tiết, người dùng bấm giờ đo thời gian làm thật (xong việc
thì đồng hồ tự dừng), để lại bình luận — kèm ảnh/video/file trong chính
bình luận đó — đính kèm tài liệu cho việc, ghim việc quan trọng lên mục
ĐÃ GHIM, dời việc sang mai, hay nhân đôi việc.

**Why this priority**: đây là lớp "đang làm thật" — biến danh sách việc
thành nhật ký công việc có bằng chứng.

**Independent Test**: bấm giờ một việc, dừng, đánh dấu xong — thống kê hiện
số phút làm thật; gửi một bình luận kèm ảnh — ảnh hiện ngay trong bình luận.

**Acceptance Scenarios**:

1. **Given** một việc đang mở, **When** người dùng bấm Bấm giờ rồi sau đó
   đánh dấu xong, **Then** đồng hồ tự dừng và số phút làm thật được cộng
   vào việc.
2. **Given** ô bình luận, **When** người dùng đính kèm một ảnh rồi gửi,
   **Then** bình luận hiện kèm ảnh xem trước ngay trong dòng bình luận;
   file đó không lẫn vào danh sách file đính kèm của việc.
3. **Given** một việc quan trọng, **When** người dùng ghim nó, **Then** nó
   xuất hiện ở mục ĐÃ GHIM trên thanh bên dù đang ở dự án khác.
4. **Given** một việc chưa làm kịp hôm nay, **When** người dùng chọn Dời
   sang mai, **Then** hạn của việc lùi đúng một ngày, giữ nguyên giờ.

---

### User Story 6 - Không bỏ lỡ việc (Priority: P2)

App tự nhắc trước hạn bằng thông báo có nút hành động (hoãn 15 phút, dời
mai, đánh dấu xong ngay trên thông báo); việc quá hạn lâu bị nhắc lại ở mức
khẩn một lần; mỗi sáng và tối app gửi bản tóm tắt. Người dùng có thể nối
thêm kênh Telegram bằng bot của chính mình để nhận các nhắc này trên điện
thoại. Mọi kênh nhắc đều là cộng thêm — tắt hết vẫn không mất việc nào.

**Why this priority**: app việc mà không nhắc thì chỉ là danh sách chết;
nhắc đúng lúc mới là giá trị cốt lõi sau ghi việc.

**Independent Test**: đặt một việc có hạn sau 10 phút và nhắc trước 30
phút — thông báo đến ngay kèm 3 nút; bấm Hoãn — 15 phút sau nhắc lại.

**Acceptance Scenarios**:

1. **Given** một việc sắp tới hạn trong khoảng nhắc trước đã đặt, **When**
   thời điểm nhắc tới, **Then** thông báo hiện kèm các nút Hoãn 15 phút /
   Dời mai / Xong.
2. **Given** một việc đã quá hạn hơn 30 phút mà chưa xong, **When** vòng
   nhắc chạy, **Then** đúng một thông báo mức khẩn được gửi cho việc đó.
3. **Given** 07:30 hoặc 20:30 hằng ngày, **When** tới giờ, **Then** bản
   tóm tắt (việc hôm nay, quá hạn, đã xong) được gửi đúng một lần.
4. **Given** người dùng đã khai token bot Telegram và chat id của mình,
   **When** một nhắc bất kỳ được gửi, **Then** cùng nội dung đó đến
   Telegram; token chỉ hiện 4 ký tự cuối trong màn hình cài đặt.

---

### User Story 7 - Nhìn tiến độ và tự đánh giá (Priority: P3)

Người dùng xem thống kê: tỉ lệ hoàn thành, việc sắp tới hạn, biểu đồ 14
ngày, theo cột/trạng thái/ưu tiên, thời gian làm thật so với ước lượng,
chuỗi ngày liên tục. Việc đã xong có thể chấm sao và phê duyệt (đã duyệt /
làm lại). Cùng một dữ liệu còn nhìn được dạng Gantt (thanh thời gian) và
sơ đồ cây dự án → cột → việc → việc con. Cuối tuần xuất được ảnh báo cáo.

**Why this priority**: nhìn lại là động lực duy trì thói quen; chấm sao và
phê duyệt biến "xong" thành "xong có chất lượng".

**Independent Test**: chấm 5 sao cho một việc đã xong và duyệt nó — thống
kê hiện điểm trung bình; mở Gantt — việc có ngày bắt đầu/hạn thành một
thanh đúng vị trí.

**Acceptance Scenarios**:

1. **Given** vài việc đã xong được chấm sao, **When** mở Thống kê, **Then**
   điểm trung bình và số việc đã chấm hiện rõ; việc xong bị dọn sau 15
   ngày vẫn được tính vào thống kê.
2. **Given** một việc đã xong, **When** người dùng chọn "Làm lại", **Then**
   việc mang dấu làm lại để nhìn thấy ngay trong popup chi tiết.
3. **Given** các việc có ngày bắt đầu và hạn, **When** mở Gantt, **Then**
   mỗi việc là một thanh từ ngày bắt đầu tới hạn, có đường đánh dấu hôm
   nay; việc quá hạn viền đỏ, việc xong màu xanh mờ.
4. **Given** một dự án đang chọn, **When** mở Sơ đồ, **Then** cây hiện
   dự án → các cột → các việc đang mở → việc con, bấm vào một việc là mở
   popup chi tiết của nó.

---

### User Story 8 - Dữ liệu luôn an toàn, mang theo được (Priority: P3)

Việc xoá vào thùng rác và khôi phục được trong 30 ngày. Nhãn có màn quản
lý riêng (đổi tên là gộp, xoá hàng loạt). Dữ liệu xuất được ra bảng tính và
ra file để chuyển máy; hai máy đồng bộ hai chiều theo thời gian sửa mới
nhất; trong app khôi phục được từ các bản sao lưu tự động hằng ngày. App
tự kiểm tra bản mới và báo ngay trong giao diện khi có.

**Why this priority**: dữ liệu là tài sản tích luỹ theo năm; an toàn và
mang theo được là điều kiện để người dùng dám gắn bó.

**Independent Test**: xoá một việc rồi khôi phục từ thùng rác; xuất file
rồi nhập vào một bản sao của app — dữ liệu khớp, việc đã bị dọn hẳn không
sống lại.

**Acceptance Scenarios**:

1. **Given** một việc vừa xoá, **When** mở Thùng rác và bấm Khôi phục,
   **Then** việc trở lại đúng cột và dự án cũ; sau 30 ngày trong thùng rác
   việc bị xoá hẳn.
2. **Given** một nhãn viết sai, **When** đổi tên nó trong Quản lý nhãn,
   **Then** mọi việc mang nhãn cũ chuyển sang nhãn mới, trùng thì gộp làm
   một.
3. **Given** hai máy cùng một bộ dữ liệu, **When** đồng bộ hai chiều,
   **Then** mỗi việc lấy bản sửa mới nhất; file đính kèm không đi theo và
   giới hạn này được báo trước.
4. **Given** một bản phát hành mới trên trang dự án, **When** app kiểm tra
   định kỳ, **Then** nút báo bản mới hiện trong app kèm đúng phiên bản.

---

### Edge Cases

- Việc không có hạn: không bao giờ bị nhắc, không hiện ở Gantt, vẫn hiện
  đầy đủ ở bảng/danh sách và mục Tất cả việc.
- Việc con rỗng tiêu đề khi lưu popup: bị bỏ qua lặng lẽ, không tạo việc
  con ma.
- Đóng app giữa lúc đồng hồ đang chạy: mở lại vẫn thấy đồng hồ đang chạy
  của việc đó (trạng thái bấm giờ nằm trong dữ liệu, không nằm trong RAM).
- Mất mạng hoàn toàn: mọi luồng chính vẫn chạy; chỉ kiểm tra bản mới, AI
  và Telegram tạm nghỉ và báo rõ khi người dùng bấm vào.
- Khôi phục một bản sao lưu cũ hơn phiên bản hiện tại: dữ liệu được nâng
  cấp schema ngay sau khi khôi phục để app không lỗi "thiếu cột".
- Hai máy cùng sửa một việc rồi đồng bộ: bản sửa mới nhất thắng; xung đột
  giờ giấc vẫn bị chặn ở lần mở sửa tiếp theo.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Hệ thống MUST cho phép ghi việc bằng câu chữ tự nhiên tiếng
  Việt, tự hiểu hạn, giờ, mức ưu tiên (kể cả dạng `#hashtag`), nhãn, người
  làm và quy tắc lặp, kèm xem trước trước khi lưu.
- **FR-002**: Hệ thống MUST có cửa sổ bắt việc toàn cục mở bằng phím tắt,
  tự điền vùng chọn/clipboard, dán nhiều dòng thành nhiều việc, đoạn dài
  thành một việc có mô tả đầy đủ.
- **FR-003**: Hệ thống MUST nhận việc từ điện thoại qua mạng riêng của
  người dùng mà không cần tài khoản.
- **FR-004**: Hệ thống MUST tổ chức việc theo dự án → cột; dự án mới có 3
  cột mặc định; cột tuỳ biến được tên/màu/thứ tự; xoá cột thì việc rơi về
  cột đầu của cùng dự án; dự án lưu trữ và khôi phục được.
- **FR-005**: Hệ thống MUST cho kéo-thả việc giữa các cột, và kéo vào cột
  đã xong tương đương hoàn thành việc.
- **FR-006**: Mọi việc MUST mở trong cùng một popup chi tiết dạng lớp phủ
  mềm; đóng được bằng bấm ra ngoài, ✕ hoặc Esc.
- **FR-007**: Mọi trường trong popup MUST tự lưu khi thay đổi; các ô gõ
  chữ còn thay đổi chưa lưu khi đóng MUST kích hoạt hộp hỏi Lưu và đóng /
  Bỏ thay đổi / Ở lại ở mọi đường đóng.
- **FR-008**: Thẻ việc MUST hiển thị toàn bộ việc con (không giới hạn số
  lượng, không cắt chữ, chữ dài xuống dòng) và cho tích xong việc con ngay
  trên thẻ.
- **FR-009**: Mọi ô chọn thả xuống MUST hiển thị chữ rõ nét ở cả hai theme,
  hàng đang chọn nổi bật.
- **FR-010**: Hệ thống MUST chặn lưu khi hai việc chồng giờ nhau, kèm
  thông báo nêu rõ việc bị trùng.
- **FR-011**: Việc lặp MUST hỗ trợ theo ngày/tuần/tháng và theo thứ trong
  tuần, giới hạn được số kỳ; hoàn thành hoặc bỏ qua một kỳ MUST sinh kỳ
  tiếp theo với việc con làm mới.
- **FR-012**: Hệ thống MUST có tự xếp lịch: đặt các việc chưa có giờ vào
  khe trống 07:00–21:00 theo ô 30 phút, không chồng chéo.
- **FR-013**: Hệ thống MUST đo thời gian làm thật bằng đồng hồ bấm giờ
  theo từng việc, tự dừng khi việc hoàn thành, và cộng dồn qua các lần
  bấm.
- **FR-014**: Bình luận MUST chứa được chữ và file (ảnh xem trước tại
  chỗ); file của bình luận MUST tách bạch với file đính kèm của việc.
- **FR-015**: Hệ thống MUST nhắc trước hạn bằng thông báo có hành động
  (hoãn 15 phút / dời mai / xong), leo thang mức khẩn một lần cho việc quá
  hạn trên 30 phút, và gửi tóm tắt sáng/tối mỗi ngày.
- **FR-016**: Hệ thống MUST cho phép nối Telegram bằng bot của chính
  người dùng để nhân bản mọi thông báo; bí mật chỉ hiển thị 4 ký tự cuối.
- **FR-017**: Hệ thống MUST thống kê được: tỉ lệ hoàn thành, sắp tới hạn,
  14 ngày gần nhất, theo trạng thái/ưu tiên, làm thật so với ước lượng,
  điểm chấm sao trung bình — gồm cả việc đã xong bị dọn khỏi bảng.
- **FR-018**: Việc đã xong MUST chấm sao (0–5) và phê duyệt được (chưa
  duyệt / đã duyệt / làm lại).
- **FR-019**: Cùng một dữ liệu MUST nhìn được ở các dạng: Bảng, Danh sách,
  Lịch, Hôm nay, Gantt, Sơ đồ cây, Thống kê; lọc theo nhãn/người làm/quá
  hạn và tìm kiếm toàn cục gồm cả nội dung bình luận.
- **FR-020**: Xoá việc MUST là xoá mềm vào thùng rác, khôi phục được
  trong 30 ngày; việc xong MUST được lưu trữ cho thống kê trước khi dọn
  sau 15 ngày.
- **FR-021**: Hệ thống MUST sao lưu tự động hằng ngày, khôi phục được từ
  trong app (có chụp lại hiện trạng trước khi thay), xuất được dữ liệu ra
  bảng tính và file chuyển máy, đồng bộ hai chiều theo thời gian sửa mới
  nhất mà không làm sống lại bản ghi đã dọn.
- **FR-022**: Hệ thống MUST tự kiểm tra bản mới mỗi ngày và báo trong giao
  diện khi có bản mới hơn, kèm đường dẫn tải.
- **FR-023**: Hệ thống MUST chạy hoàn toàn không cần mạng và không cần tài
  khoản; tính năng phụ thuộc mạng MUST suy giảm êm và báo rõ.
- **FR-024**: Mọi bề mặt và chữ trong giao diện MUST đọc rõ ở cả theme
  sáng và tối theo Nguyên tắc III của constitution.

### Key Entities

- **Dự án**: một mảng công việc lớn; có tên, màu, trạng thái lưu trữ; chứa
  nhiều cột và nhiều việc. Luôn tồn tại ít nhất một dự án.
- **Cột**: một trạng thái trong quy trình của một dự án; có tên, màu, thứ
  tự; thuộc đúng một dự án.
- **Việc**: đơn vị công việc trung tâm; có tiêu đề, mô tả, trạng thái
  (đang mở / đã xong / trong thùng rác), mức ưu tiên 4 cấp (tên gọi tuỳ
  biến), ngày bắt đầu, hạn + giờ, ước lượng phút, nhắc trước, người làm,
  nhãn, quy tắc lặp + số kỳ còn lại, ghim, thời gian làm thật + trạng thái
  bấm giờ, chấm sao + phê duyệt, thời điểm sửa gần nhất.
- **Việc con**: một mục trong danh sách con của một việc; có tiêu đề, mô
  tả riêng, trạng thái xong/chưa; được làm mới khi việc lặp sinh kỳ mới.
- **Bình luận**: một dòng trao đổi trong một việc; có tác giả, thời gian,
  nội dung chữ và có thể kèm một file.
- **File đính kèm**: một tệp gắn với việc hoặc với một bình luận; lưu trên
  chính máy đó, không đi theo đồng bộ.
- **Sao lưu**: bản chụp toàn bộ dữ liệu tại một thời điểm, tạo tự động
  hằng ngày hoặc ngay trước mỗi lần khôi phục.
- **Cài đặt**: lựa chọn của người dùng trên máy đó (theme, thanh bên, tên
  hiển thị, bí mật của các kênh phụ) — không đồng bộ theo dữ liệu việc.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Người dùng ghi xong một việc có hạn từ bất kỳ đâu trong tối
  đa 10 giây thao tác (không tính thời gian gõ chữ).
- **SC-002**: 100% trường hợp đóng popup khi còn chữ chưa lưu đều xuất
  hiện hộp hỏi lưu — không trường hợp nào mất chữ lặng lẽ.
- **SC-003**: 0 việc nào bị mất do xoá nhầm, dọn dẹp tự động, khôi phục
  sao lưu hay đồng bộ — mọi đường xoá đều có đường quay lại trong hạn đã
  công bố (30 ngày thùng rác, sao lưu hằng ngày giữ 14 bản).
- **SC-004**: 100% bề mặt giao diện đọc rõ ở cả hai theme khi quét kiểm
  chứng (hộp thoại, menu, popup thả xuống, lịch, thẻ, popup chi tiết).
- **SC-005**: 0 lịch nào bị xếp chồng giờ mà không bị chặn kèm giải thích.
- **SC-006**: Mọi việc có hạn và có đặt nhắc đều phát đúng ít nhất một
  thông báo trước hạn khi app đang chạy.
- **SC-007**: Người dùng mới mở spec này (hoặc một AI mới đọc spec này) có
  thể kể lại đúng toàn bộ luồng của hệ thống mà không cần đọc code.

## Assumptions

- Một người dùng trên một máy tại một thời điểm; "người làm" là nhãn chữ
  tự do, không phải tài khoản — đúng định vị local, không tài khoản.
- Giao diện và nội dung trợ giúp bằng tiếng Việt; tên các mức ưu tiên do
  người dùng tự đặt lại được.
- Tài liệu này là spec as-built của hệ thống đang chạy (v1.6.2): các kịch
  bản nghiệm thu mô tả hành vi hiện hành đã được kiểm chứng, đồng thời là
  chuẩn để các thay đổi về sau không được phá.
- Các bước tiếp theo của quy trình Spec Kit (plan, tasks) cho spec này
  nhằm đối chiếu hệ thống hiện hành (converge), không phải để xây mới từ
  đầu — sẽ chạy khi chủ dự án duyệt ở cổng specify.
