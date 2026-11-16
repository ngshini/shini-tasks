# muse.md — Shini Tasks

> File này dành cho AI agent (Muse) đọc TRƯỚC khi làm việc với repo này, để
> không phải hỏi lại từ đầu và không lặp lại lỗi cũ. Cấu trúc theo chuẩn
> `AGENTS.md` đang dùng rộng rãi (phân tích 2.500+ repo trên GitHub): Vai trò →
> Tổng quan → Lệnh → Kiến trúc → Quy ước → Kiểm thử → Ranh giới → Lịch sử quyết
> định. Cập nhật file này mỗi khi có quyết định lớn hoặc bài học mới.
>
> Chủ dự án: **ngshini** (GitHub). Mọi commit/push dùng danh tính của chủ dự
> án, không dùng tên agent.

## 1. Tổng quan

Shini Tasks là app quản lý việc cá nhân chạy **hoàn toàn local** trên máy người
dùng: không tài khoản, không đám mây, dữ liệu SQLite nằm trên máy. Đây là sản
phẩm công khai (repo public, phát hành bản cài Windows qua GitHub Releases) —
không đưa thông tin cá nhân (IP, đường dẫn máy riêng, tên thật ngoài những gì
README đã có) vào bất cứ file nào trong repo.

- **Engine** `server.py`: Python stdlib + SQLite, API HTTP ở cổng **8790**,
  thông báo desktop, nhắc việc, sao lưu hằng ngày, tự kiểm tra bản mới.
- **App desktop** `app.py`: GTK4 + Libadwaita (PyGObject). Đây là giao diện
  chính. Giao diện web trong `static/` chỉ là trang dự phòng — **đừng đề xuất
  dùng web thay app desktop**, chủ dự án đã bác bỏ dứt khoát.
- **Windows**: đóng gói bằng PyInstaller + Inno Setup, build qua GitHub
  Actions (`.github/workflows/build-windows.yml`). Bản cài chưa có chữ ký số
  (SmartScreen hiện cảnh báo — đã chấp nhận).

## 2. Lệnh thường dùng

```bash
# Chạy engine (Linux)
python3 server.py                      # cổng 8790, hoặc systemd user service: shini-tasks
systemctl --user restart shini-tasks   # khởi động lại engine khi sửa server.py

# Chạy app desktop (Linux)
GSK_RENDERER=cairo python3 app.py      # LUÔN ghim GSK_RENDERER=cairo (hiệu năng + chụp hình)

# Kiểm tra cú pháp sau mỗi lần sửa
python3 -m py_compile app.py server.py

# Chụp hình kiểm chứng giao diện (Xvfb, không đụng vào màn hình thật của người dùng)
GSK_RENDERER=cairo SHINI_TASKS_THEME=dark SHINI_TASKS_SNAPSHOT=/tmp/shot.png \
  xvfb-run -a dbus-run-session -- python3 app.py
# Biến môi trường kiểm thử: SHINI_TASKS_VIEW=board|list|calendar|today|stats,
# SHINI_TASKS_OPEN="<mảnh tiêu đề việc>" (mở sẵn chi tiết việc đó),
# SHINI_TASKS_SIZE=WxH, SHINI_CAPTURE_PREFILL.

# Kiểm thử engine trên BẢN SAO dữ liệu (không bao giờ test trên DB thật)
# chép tasks.db + server.py mới vào thư mục tạm, chạy SHINI_TASKS_PORT=8799,
# chạy script test, rồi huỷ. Nhớ nạp server.py MỚI vào bản sao trước khi test.
```

## 3. Kiến trúc nhanh

- `server.py` — toàn bộ engine: bảng `tasks`, `columns`, `projects`,
  `comments`, `attachments`, `done_archive`, `meta`. Migration viết ở cuối
  `init_db()`. Mọi thay đổi schema phải chạy được trên DB cũ của người dùng.
- `app.py` — toàn bộ app desktop trong một file: `MainWindow` (khung chính),
  `DetailPane` (chi tiết việc, hiện dưới dạng popup `Adw.Dialog`), các dialog
  phụ (Thùng rác, Nhãn, Đồng bộ, Tìm kiếm…), hai khối CSS `DARK_CSS` /
  `LIGHT_CSS`.
- Dữ liệu việc con (`subtasks`) lưu JSON với khóa rút gọn: **`{"t": tiêu đề,
  "d": mô tả, "done": bool}`** — đọc sai khóa (`title`) là thẻ hiện hàng trống.
- File đính kèm nằm ở `<thư mục dữ liệu>/attachments/`, không đi theo khi
  đồng bộ/xuất JSON (chỉ metadata + bình luận đi theo).

## 4. Quy ước & bài học cứng (đã trả giá, đừng học lại)

1. **Theme hệ thống của người dùng là "Sweet" (dark)** — bất kỳ widget nào
   không được app ghim màu tường minh sẽ render theo Sweet và hỏng chữ ở một
   trong hai theme. Quy tắc: ghim CỨNG màu nền + màu chữ cho mọi bề mặt và
   mọi nhãn quan trọng, ở CẢ HAI theme. "Template trắng thì trắng hết, chữ
   đen" — mọi bề mặt trong một theme phải đồng nhất.
2. Nhãn GTK lồng trong `Gtk.Button` **không** thừa hưởng màu dùng được — ghim
   màu cho nhãn con. Selector CSS `button.x > label` không ăn khi nhãn nằm
   trong Box con; dùng selector hậu duệ `button.x label`.
3. `with sqlite3.connect()` **không** đóng kết nối (từng gây cạn file
   descriptor). Dùng helper `db()` (contextmanager đóng trong `finally`).
4. Không gọi hàm tự mở `db()` (vd `insert_task`, `default_project_id`) khi
   đang giữ một transaction `db()` khác — sẽ `database is locked`. Chuẩn bị
   dữ liệu trong block, gọi hàm sau khi commit.
5. `Gtk.ScrolledWindow` có policy ngang `NEVER` sẽ ép bề ngang tối thiểu của
   cả cửa sổ theo nội dung cố định bên trong → tràn/chồng lấn. Trang nào bọc
   nội dung rộng cố định thì để policy ngang `AUTOMATIC`.
   `set_propagate_natural_width(False)` làm tình hình tệ hơn — đừng thử lại.
6. Widget con có `hexpand` ngầm sẽ làm `Gtk.Box` chia đều phần dư — ghim
   `set_hexpand(False)` tường minh cho panel/cột phụ khi cần giữ bề ngang.
7. Nút `Gtk.ToggleButton` mà handler tự gọi `set_active()` lên chính nhóm của
   nó sẽ đệ quy ~1000 lần (không crash nhưng thao tác chậm như đơ) — handler
   chỉ chạy khi nút chuyển sang active + cờ chống tái nhập.
8. Trên máy người dùng: giết tiến trình theo **PID lấy từ pgrep**, không dùng
   `pkill -f` (dễ giết nhầm cả shell SSH). App thật chạy với cmdline tương đối
   `python3 app.py`.
9. Mọi thay đổi giao diện phải **kiểm chứng bằng ảnh render thật** (Xvfb,
   cả 2 theme, mọi view bị ảnh hưởng) trước khi nói "xong". Không tuyên bố
   hoàn thành khi chưa có bằng chứng.
10. File test/probe/script phụ (`test_*.py`, `probe_*.py`, `release-notes-*.md`,
    thư mục `mockups/`) **không commit** vào repo.

## 5. Ranh giới

**Luôn làm:**
- **Đọc trước — ghi lại sau (Sinh chốt 2026-11-16):** trước khi làm bất cứ
  việc gì, đọc lại các file md liên quan (`muse.md` này, và từ khi có
  Spec Kit: `.specify/memory/constitution.md` + `spec.md` của tính năng);
  có sửa gì — code, hành vi, quy định — thì cập nhật ngược vào đúng file
  md đó. Các file md là nguồn sự thật sống của dự án, không phải giấy
  viết một lần rồi bỏ.
- **Phát hành chỉ khi Sinh kêu (chốt 2026-11-17):** sửa nhỏ thì CHỈ
  deploy lên máy Linux của Sinh cho anh kiểm tra và sửa tiếp theo ý anh;
  KHÔNG tự bump version, KHÔNG tự tạo GitHub release. Giữ nguyên số
  version của bản phát hành gần nhất trong lúc test. Khi nào Sinh nói
  "đưa lên / phát hành" mới bump đủ 4 nơi + tạo release một lần cho cả
  chùm thay đổi đã tích luỹ.
- Sửa đúng điểm được chỉ, không tự mở rộng phạm vi.
- Kiểm chứng trên bản sao dữ liệu / render Xvfb trước khi đụng vào bản thật.
- Bump đủ 4 nơi khi phát hành: `VERSION` trong `server.py` + `app.py`,
  `AppVersion` trong `packaging/ShiniTasks.iss`, badge trong `README.md`.

**Hỏi trước:**
- Xoá dữ liệu thật, đổi schema làm mất dữ liệu cũ, đổi hành vi đã chốt
  (xem mục 6) theo hướng khác.

**Không bao giờ:**
- Xoá việc/dữ liệu thật của người dùng để "test".
- Đưa IP/Tailscale/đường dẫn máy riêng/mật khẩu vào repo hoặc file công khai.
- Commit bằng danh tính agent.
- Bịa số liệu (tốc độ, dung lượng, thống kê) khi engine không đo được —
  hiện "chưa có số đo" thay vì invent.

## 6. Toàn bộ quá trình theo yêu cầu của chủ dự án (lịch sử quyết định)

App được xây theo từng yêu cầu ngắn, sửa đúng điểm, kiểm chứng rồi mới đi
tiếp. Các quyết định dưới đây ĐANG HIỆU LỰC trừ khi ghi "đã thay".

- **2026-11-08 — Khởi đầu.** Yêu cầu: app quản lý việc cá nhân. Bản web bị
  bác ("không ưng") → chuyển hẳn sang **app desktop GTK4**. Giữ đến nay.
- **v3–v4.** Tìm kiếm/lọc/sắp xếp, lịch tháng mini, cột Kanban **tự tuỳ biến**
  (thêm/đổi tên/đổi màu/xoá), bỏ ma trận Eisenhower → **4 mức ưu tiên tự đặt
  tên** được (mặc định Làm ngay/Quan trọng/Gấp/Thường). Hai theme sáng/tối.
- **v5.** View **Lịch** dạng lưới giờ tuần/ngày; việc có `due_date` +
  `due_time` + `estimate_min`; **chặn trùng giờ** khi lưu.
- **v6–v7.** Sidebar thông minh (Tất cả/Hôm nay/Sắp tới/Quá hạn — bấm là lọc
  thật), thẻ gọn kiểu Notion/Jira, ô thêm nhanh hiểu câu tự nhiên tiếng Việt
  (`/api/parse`). **Cửa sổ bắt việc siêu nhanh** bằng phím tắt toàn cục
  (chốt là **Alt+E** ngày 2026-11-10): dán nhiều dòng = nhiều việc, đoạn dài
  = 1 việc + ghi chú. **Việc con** dạng checklist.
- **2026-11-10 — Ba giai đoạn nâng cấp.** (1) Engine: `updated_at`, sao lưu
  hằng ngày, nút hành động trên thông báo (hoãn 15p/dời mai/xong), bản tin
  07:30 + 20:30. (2) Kéo-thả thẻ giữa cột + trên lịch, trang **Hôm nay**,
  **Tự xếp lịch**, đồng bộ 2 máy qua export/import. (3) **Thống kê** (chuỗi
  ngày, biểu đồ 14 ngày, theo cột/trạng thái/ưu tiên, xuất báo cáo tuần PNG)
  + lặp nâng cao theo thứ (`wd:0,2,4`) và giới hạn số lần.
- **2026-11-10 — Hướng D.** Câu tự nhiên hiểu thêm lệnh lặp ("mỗi T2 T4 T6",
  "lặp 12 lần"), xuất lịch ICS, bắt việc từ điện thoại qua API
  (`POST /api/quick`, xem `HUONG-DAN-DIEN-THOAI.md`).
- **2026-11-12.** Trong hộp sửa việc, Enter ở bất kỳ ô nào cũng = Lưu.
- **2026-11-14 — Đóng gói Windows + xuất bản công khai.** Đóng gói nguyên
  app GTK thành bản cài Windows (PyInstaller + Inno Setup, CI trên GitHub
  Actions). Chủ dự án quyết: **phát hành cho người khác dùng** → repo chuyển
  public sau khi **gộp lịch sử git về một commit** để xoá dấu vết cá nhân,
  nội dung cá nhân hoá được gỡ khỏi code/README. Từ đây app là sản phẩm
  công khai: mỗi bản phát hành kèm ghi chú tiếng Việt + hướng dẫn cài đè
  giữ nguyên dữ liệu + cách qua SmartScreen.
- **v1.2.0 (2026-11-15).** Việc đã xong quá **15 ngày tự xoá khỏi bảng nhưng
  vẫn tính trong thống kê** (bảng `done_archive`). **v1.2.1:** app tự kiểm
  tra bản mới mỗi ngày (đọc redirect của `releases/latest`, không dùng REST
  API vì dễ dính rate-limit) và hiện nút ⬆ trên thanh tiêu đề.
- **v1.3.0 (2026-11-16) — Học từ KimesFlow.** Chủ dự án chỉ đích danh repo
  KimesFlow của mình và chọn 6 nhóm tính năng: **nhiều dự án** (mỗi dự án bộ
  cột riêng), việc con có mô tả + tiến độ, **bình luận**, **file đính kèm**,
  cú pháp thêm nhanh (`#urgent`, `due:…`, `@người`), thống kê dashboard.
  Không chọn: AI chia việc, Telegram, mindmap, đa người dùng/cloud (phá vỡ
  định vị local-không-tài-khoản).
- **v1.4.0 (2026-11-16) — Gói hoàn thiện.** **Thùng rác** (xoá mềm 30 ngày,
  khôi phục được), **đồng hồ bấm giờ** đo thời gian làm thật (`actual_min`),
  **tìm mọi nơi** (kể cả trong bình luận), **quản lý nhãn** (đổi tên/gộp),
  **bỏ qua một kỳ** lặp, **khôi phục từ sao lưu ngay trong app**, xuất CSV.
- **v1.4.1.** Sửa lỗi "bảng thu về 1 cột" khó hiểu: thêm thanh báo "Đang chỉ
  xem cột X" + nút thoát ngay trên bảng (bài học: trạng thái ẩn mà không có
  chỉ báo + đường thoát rõ ràng sẽ bị tưởng là lỗi).
- **2026-11-16 — Làm gọn sidebar theo mẫu Todoist.** Sidebar từng phình 7
  mục mở chồng nhau → bị chê "rối ren hết rồi". Nguyên tắc rút ra: sidebar
  chỉ chứa điều hướng.
- **2026-11-16 — Nghiên cứu 12 app → khung chuẩn → v1.5.0.** Chủ dự án vẫn
  không ưng tổng thể ("chỗ nào cũng không ưng hết") → nghiên cứu sâu
  Todoist/TickTick/Notion/Linear/Asana/Trello/ClickUp/MS To Do/Apple
  Reminders/Things 3/Jira/Planify. Kết luận: gần như mọi app dùng chung một
  khung (sidebar 240–280px chỉ điều hướng theo thứ tự cố định + thanh trên
  mỏng 1 nút Thêm + panel chi tiết bên phải; thẻ việc có "ngân sách" ~5 tín
  hiệu; cảm giác rối đến từ số loại đối tượng và số nút hiện cùng lúc, không
  phải mật độ). Dựng mẫu bằng dữ liệu thật, chủ dự án duyệt → **v1.5.0**:
  sidebar điều hướng thuần + mục **Đã ghim** 📌 + vòng tiến độ dự án, tab
  Bảng/**Danh sách (mới)**/Lịch/Hôm nay/Thống kê, thẻ rút còn ~5 tín hiệu,
  cột ĐÃ XONG rời bảng, chi tiết việc chuyển thành panel phải tự lưu từng
  trường (thay hộp thoại).
- **v1.5.1 (2026-11-16) — Sửa theo dùng thật.** Sau nửa ngày dùng v1.5.0,
  chủ dự án yêu cầu đảo 2 điểm của khung chuẩn: (1) **việc con hiển thị lại
  trên thẻ** (hàng tròn + tên, bấm tròn để tích, tối đa 6 hàng) — nhìn lướt
  thấy việc con quan trọng hơn "ngân sách tín hiệu"; (2) **chi tiết việc về
  lại dạng popup** (`Adw.Dialog` nổi giữa màn hình) vì panel phải cố định
  bóp bảng quá hẹp. Phần còn lại của v1.5.0 giữ nguyên. Bài học: mẫu duyệt
  trên mockup ≠ cảm giác dùng thật — quyết định cuối luôn thuộc về trải
  nghiệm thực tế của chủ dự án.
- **v1.6.0 (2026-11-16) — Gói Coogo.** Chủ dự án gửi link sản phẩm Coogo
  Flow (app quản lý dự án cho team trên Google Apps Script) và chọn "đưa
  tính năng còn thiếu vào Shini Tasks". Đã bổ sung, giữ nguyên định vị local
  cá nhân: **view Sơ đồ** (mindmap Dự án → Cột → Việc → Việc con, vẽ Cairo),
  **view Gantt** (thanh bắt đầu → hạn, đường hôm nay), **đánh giá & phê
  duyệt** (`tasks.rating` 1–5 sao + `tasks.verdict` ''/approved/redo, chấm
  trong popup, thống kê hiện điểm trung bình), **lưu trữ dự án**
  (`projects.archived`, khôi phục ở mục 📦 Đã lưu trữ), **bình luận gắn
  file/ảnh/video** (`attachments.comment_id`, ảnh xem trước trong popup),
  **lọc theo người làm**, **thông báo Telegram** cho chính người dùng
  (bot token + chat id cấu hình trong ⚙ Cài đặt, lưu ở bảng `meta` của
  engine qua `/api/notify-config`; `notify()` được bọc để soi gương sang
  Telegram, có khử trùng 5 giây), **AI Gemini điền form** (nút ✨ ở ô thêm
  nhanh, key lưu trong settings của app, model gemini-2.0-flash, trả JSON).
  KHÔNG làm: thông báo Zalo (Zalo không cho tự động hoá tài khoản cá nhân —
  đừng hứa), tính năng team thật (giao việc cho tài khoản khác, chat nhiều
  người) vì phá định vị không-tài-khoản. Bài học kỹ thuật: view vẽ bằng
  Cairo (Gantt/Sơ đồ) thì `import cairo` phải ở cấp module; glyph ✓ không
  có trong font mà Cairo toy API chọn — việc con đã xong trên Sơ đồ dùng nét
  gạch ngang vẽ tay thay cho ký tự ✓.
- **v1.6.1 (2026-11-16) — Vá theo dùng thật, 3 điểm.** (1) **Việc con trên
  thẻ hiện TẤT CẢ và xuống dòng đầy đủ** — bỏ giới hạn 6 hàng và bỏ cắt
  "…" (nhãn `set_wrap(True)` + WORD_CHAR). (2) **Popup chi tiết bỏ hẳn
  Adw.Dialog**: ở theme sáng nó có KHUNG ĐEN đặc ~10px (bóng đổ Adw vẽ bằng
  GSK cairo thành đen đặc) và đè mất chữ đầu các nhãn ("Trạng thái" →
  "rạng thái"). Thử Gtk.Window riêng: hết khung đen nhưng "cứng" và không
  click-ngoài-đóng được. Chốt cuối: **lớp phủ tự dựng trong cửa sổ chính**
  (`Gtk.Overlay`: nền mờ `.panebackdrop` + thẻ bo góc 16px `.panecard`,
  bấm vùng mờ để đóng; nhớ `set_measure_overlay(backdrop, False)` và
  `set_vexpand(True)` cho ScrolledWindow trong thẻ, không nó co còn
  ~100px). (3) **Đóng popup khi còn chữ chưa lưu thì HỎI**: các ô gõ chữ
  (tiêu đề, mô tả, người làm, nhãn, ước lượng, nhắc trước) chỉ lưu khi
  Enter/rời ô — `DetailPane._dirty_saves()` phát hiện, mọi đường đóng
  (✕ / Esc / click ra ngoài) đi qua `MainWindow.request_close_pane()` →
  hộp hỏi Lưu và đóng / Bỏ thay đổi / Ở lại. Các trường chọn-bấm lưu ngay
  nên không hỏi.
- **v1.6.2 (2026-11-16) — Chữ trong popup thả xuống của DropDown bị chìm.**
  Danh sách chọn của Gtk.DropDown (listview bên trong popover) chưa từng
  được ghim màu hàng/nhãn — theme Sweet nuốt mất chữ (theme sáng: chữ xám
  nhạt trên nền trắng, gần như tàng hình). Đã ghim ở đuôi cả 2 theme:
  `popover listview/listbox > row` + `row label` + `row:selected`. Kiểm
  chứng bằng probe mở thật popup của ô Dự án và render popover bằng chính
  kỹ thuật snapshot của app (WidgetPaintable → Gsk.CairoRenderer): sáng
  và tối đều rõ. Bài học probe: `get_current_image()` trả Paintable chứ
  không phải Texture (không có save_to_png); ngoại lệ trong callback GLib
  làm app treo tới timeout thay vì thoát — luôn bọc try/finally + quit.
- **Spec Kit vào dự án (2026-11-16, lệnh của chủ dự án + video tham chiếu
  anh gửi):** `specify init --here --force` (bản không có `--force` treo
  ở câu hỏi thư mục-không-trống). **Constitution v1.0.0** ở
  `.specify/memory/constitution.md` — 7 nguyên tắc (local-first; dữ liệu
  không bao giờ mất; ghim màu cả hai theme; ghi việc trong vài giây; sửa
  không mất lặng lẽ; một khung + spec là nguồn sự thật; kiểm chứng trước
  khi nói xong) + ranh giới cứng + quy trình phát hành. **Spec as-built
  `specs/001-luong-hoat-dong/spec.md`**: 8 user story theo luồng thật của
  hệ thống, tiêu chí nghiệm thu dạng Given/When/Then, FR-001…FR-024,
  SC-001…SC-007, checklist đạt toàn bộ. Quy tắc đứng của chủ dự án (ghi ở
  mục 5 + skill speckit): việc mới nào cũng dựng khung Spec Kit trước;
  không hiểu luồng thì hỏi tới khi hiểu mới ghi, điểm mờ dùng thẻ
  `[NEEDS CLARIFICATION]`; đổi yêu cầu sửa spec → plan → tasks → test →
  code. Đang dừng ở cổng duyệt specify — plan/tasks theo hướng converge
  chờ anh duyệt.
- **v1.6.3 (2026-11-17, Sinh chê popup chi tiết "dư thừa quá nhiều"):**
  các trường phụ của DetailPane (Bắt đầu, Lặp lại + 2 hàng con, Người
  làm, Nhãn, Làm thật, ĐÁNH GIÁ/Chấm sao/Phê duyệt) gập vào nhóm
  **"Chi tiết khác"** sau hàng Hạn — một nút `▸/▾` + `more_box`; nhóm TỰ
  MỞ khi việc có giá trị ở bất kỳ trường phụ nào (start_date, repeat,
  assignee, tags, actual_min, timer đang chạy, rating, verdict). Trường
  lõi luôn hiện: Trạng thái/Ưu tiên/Dự án/Cột/Hạn/Ước lượng/Nhắc trước.
  Kiểm chứng 2 render: việc "Dự định phát triển về bảo mật" (đúng ảnh anh
  gửi) gập gọn vừa một màn hình theme sáng; việc seed đầy giá trị tự mở
  đủ trường theme tối. Spec 001 không đổi — mọi trường vẫn ở nguyên trong
  cùng popup, chỉ gập hiển thị.
- **v1.6.4 (2026-11-17, Sinh muốn cột ĐÃ XONG hiện lại trên bảng):** đảo
  quyết định v1.5.0 lần nữa theo dùng thật — `_sync_board` thêm cột ĐÃ
  XONG (chính widget `_column_widget(None, done_list)` của mục ĐÃ XONG)
  đứng cuối các cột dự án, trước ô thêm cột; đang ghim-một-cột thì ẩn.
  Quy tắc 15 ngày KHÔNG phải làm mới: engine đã có `purge_old_done` từ
  v1.2.0 (done_at < hôm nay − 15 ngày → chép sang done_archive rồi xoá
  khỏi bảng tasks, chạy hằng ngày) nên việc xong quá 15 ngày tự rời cột
  mà thống kê vẫn đủ. Sửa luôn tooltip chân thanh bên còn ghi "cột ĐÃ
  XONG đã rời khỏi bảng". Đã ghi ngược vào spec 001 (Story 2, kịch bản
  6). Kiểm chứng render bảng cả sáng + tối: cột ĐÃ XONG hiện đúng việc
  đã xong của dự án.

## 7. Cách chủ dự án làm việc (để phối hợp cho đúng)

- Yêu cầu thường **ngắn, gõ nhanh, chỉ đúng điểm cần sửa** (kèm ảnh chụp khi
  là lỗi giao diện — ảnh đó chính là đặc tả). Đọc ý đằng sau câu chữ, làm
  đúng điểm đó, kiểm chứng bằng ảnh/đo đạc thật rồi báo lại ngắn gọn.
- Đánh giá bằng **sản phẩm chạy được**, không phải lời giải thích. Kết quả
  đưa trước, giải thích sau.
- Khi hướng đi lớn chưa rõ, đưa mẫu/lựa chọn trước; khi đã ra lệnh cụ thể
  thì làm thẳng, không hỏi lại.
- File này (`muse.md`) được tạo ngày 2026-11-16 theo yêu cầu của chủ dự
  án, sau khi tham khảo cấu trúc `AGENTS.md` ở các tài liệu/repo khác.
- **Đổi chính sách phát hành (2026-11-17 00:16, lệnh của Sinh):** từ nay
  sửa nhỏ chỉ deploy lên máy anh để anh test và góp ý tiếp — KHÔNG tự
  phát hành từng bản nhỏ nữa. Chỉ khi anh kêu "đưa lên" mới bump version
  + release một lần cho cả chùm. Đã ghi vào mục 5 ở trên và constitution
  (lên v1.0.1). Hai bản v1.6.3/v1.6.4 vừa đăng trước lệnh này vẫn giữ
  nguyên trên GitHub.
- **Gộp Gantt vào Lịch (2026-11-17 00:38, lệnh của Sinh — CHƯA phát
  hành, chỉ deploy máy anh theo chính sách mới, version giữ 1.6.4):**
  tab Gantt bị xoá hẳn; phần riêng của Gantt (thanh bắt đầu→hạn + nhìn
  xa) thành **chế độ Tháng** của Lịch — nút chuyển nay là Tuần/Ngày/
  Tháng, `cal_month_off` + `_cal_nav`/`_cal_today` theo tháng,
  `_render_timeline()` (từ `_render_gantt`) khoá khoảng vẽ đúng tháng
  đang xem và kẹp thanh ở mép tháng; ở chế độ Tháng ẩn lưới giờ, dải
  chưa xếp giờ và nút Tự xếp. Tên nội bộ `_gantt_*` giữ nguyên để khỏi
  churn; hook test `SHINI_TASKS_VIEW=gantt` nay mở Lịch+Tháng. Đã ghi
  ngược vào spec 001 (FR-019 + Story 7 kịch bản 3). Kiểm chứng: render
  Tháng theme tối (thanh/đường hôm nay/nhãn ngày đúng dữ liệu thật) +
  render Tuần theme sáng không đổi.
- 2026-11-17 (gói vá A theo audit): vá toàn bộ mục A của AUDIT-2026-11-17
  (file audit để ở gốc repo, không commit). (1) **Token API**: engine tự
  sinh `api-token.txt` trong thư mục dữ liệu (quyền 600, env
  SHINI_TASKS_TOKEN ghi đè); `_auth()` nay chặn CẢ do_GET (trước chỉ
  chặn ghi) — feed ICS là ngoại lệ duy nhất, chấp nhận `?token=` trên
  URL. App đọc token cùng file, gặp 403 thì đọc lại file và thử lại 1
  lần. Cài đặt có mục TOKEN API (hiện 4 số cuối + nút sao chép); hộp
  Đồng bộ có ô "Token của máy kia" (lưu `peer_token`); hướng dẫn điện
  thoại đã bổ sung header X-Token + ?token= cho ICS. **Mọi script test
  từ nay phải gửi header X-Token đọc từ `<data dir>/api-token.txt`.**
  (2) SQLite bật **WAL + busy_timeout=5000** trong `db()`. (3) `_body()`
  bắt lỗi JSON + trần 40MB, body rác trả {} thay vì sập handler.
  (4) reminder_loop thu hẹp: chỉ quét việc còn điều kiện nhắc, hạn ≤ 8
  ngày tới, đọc xong đóng transaction, cập nhật cờ bằng transaction
  ngắn; thêm index idx_tasks_due. (5) `/api/import` trả thêm
  `overwritten` (số việc bị ghi đè khi nội dung thật sự khác); hộp Đồng
  bộ hiển thị cảnh báo. (6) Bấm giờ dùng `_elapsed_mins()` làm tròn nửa
  phút trở lên (phiên 40 giây = 1 phút; trước đây tròn xuống = 0).
  (7) App mất kết nối engine: hiện nhãn ⚠ trên headerbar + tự
  `systemctl --user start shini-tasks` một lần mỗi đợt mất (Linux).
  Test `test_fix_a.py` 12/12 trên bản sao (không commit). Kiểm chứng
  live: không token → 403, có token → 200, app nạp đủ dữ liệu thật.
  Chưa release — chờ lệnh của Sinh (quy tắc phát hành 2026-11-17).
- 2026-11-17 (gói B theo audit — trải nghiệm người dùng): (1) **Hướng
  dẫn lần đầu**: WelcomeDialog 5 mục (bắt việc nhanh/cú pháp gõ tắt,
  làm việc hằng ngày, nhắc, điện thoại & máy khác, an toàn dữ liệu) tự
  hiện ở lần mở đầu (cờ `welcomed` trong settings), mở lại ở chân thanh
  bên → ❓ Hướng dẫn sử dụng. (2) **Hoàn tác**: toast vốn đã có nút
  Hoàn tác ở _toggle; nay nối thêm cho thả thẻ vào cột ĐÃ XONG, kéo
  chuyển cột, xoá việc (khôi phục từ thùng rác), đổi trạng thái sang
  Đã xong trong popup, và 🌅 Dời sang mai (PATCH lại hạn cũ); thêm
  `MainWindow._pane_resync(tid)` để popup đang mở nạp lại sau hoàn tác.
  (3) **Cài đặt gom một chỗ**: SettingsDialog thêm mục QUẢN LÝ & DỮ
  LIỆU mở nhanh Thùng rác/Nhãn/Mức ưu tiên/Đồng bộ. (4) **Tìm kiếm dễ
  thấy**: placeholder "Tìm… Enter = tìm mọi nơi" + nút 🔍 cạnh ô tìm mở
  thẳng Tìm Mọi Nơi. (5) **Nhắc tuỳ biến**: meta `cfg_remind_default`
  (0–1440) + `cfg_snooze_min` (1–240) qua /api/notify-config; insert
  dùng mặc định khi việc không ghi rõ; **parse_quick đổi remind khởi
  tạo 30 → None** để mặc định cấu hình có hiệu lực cả đường thêm
  nhanh; nhãn + thời lượng snooze trên thông báo đọc từ cấu hình.
  SettingsDialog có mục NHẮC VIỆC (2 SpinButton). (6) **Bắt được lỗi
  tiềm ẩn thật**: `load_settings()` chỉ nạp 4 khóa cố định — peer_url,
  peer_token, gemini_key, display_name... bị rơi khỏi bộ nhớ sau mỗi
  lần mở app và sẽ bị ghi đè mất hẳn ở lần lưu cài đặt kế tiếp; đã sửa
  thành nạp mọi khóa đã lưu. Test: test_fix_b.py 6/6 trên bản sao;
  render kiểm chứng WelcomeDialog + SettingsDialog (tối) và thanh bên
  (sáng). Chưa release — chờ lệnh của Sinh.
