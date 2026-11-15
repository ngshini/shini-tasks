#!/usr/bin/env python3
"""Shini Tasks — app quản lý việc cá nhân của Sinh.
Chạy thẳng trên máy Linux, không cần thư viện ngoài (chỉ Python chuẩn + SQLite).
- Web UI:      http://localhost:8790
- API thêm nhanh: POST /api/quick  {"text": "Mai 9h họp team !gấp #work 30p"}
- Nhắc việc:  notify-send trên desktop GNOME + thông báo trong web.
"""
import json, os, re, sqlite3, subprocess, sys, threading, time, urllib.request
from contextlib import contextmanager
from datetime import datetime, date, timedelta, time as dtime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

BASE = os.path.dirname(os.path.abspath(__file__))
PORT = int(os.environ.get("SHINI_TASKS_PORT", "8790"))
TOKEN = os.environ.get("SHINI_TASKS_TOKEN", "")  # để trống = chỉ tin mạng nhà/Tailscale

# ---- Tương thích Windows (bản đóng exe, hướng A — Sinh chọn 2026-11-14) ----
# Mọi rẽ nhánh Windows đều nằm sau IS_WIN/FROZEN nên bản Linux chạy y như cũ.
IS_WIN = sys.platform.startswith("win")
FROZEN = getattr(sys, "frozen", False)

def _data_dir():
    """Nơi GHI ĐƯỢC dữ liệu (tasks.db, inbox.txt, backups/).
    Windows đóng exe cài vào Program Files (chỉ đọc) -> dữ liệu phải nằm ở
    %APPDATA%\\Shini Tasks. Các trường hợp còn lại giữ nguyên cạnh file code."""
    if IS_WIN and FROZEN:
        d = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "Shini Tasks")
        os.makedirs(d, exist_ok=True)
        return d
    return BASE

DATA = _data_dir()
DB = os.path.join(DATA, "tasks.db")

if IS_WIN:
    # Console Windows mặc định cp1252: print() tiếng Việt (kể cả dòng mở đầu)
    # sẽ sập UnicodeEncodeError khi exe được mở từ terminal — đã gãy thật ở
    # lượt build Windows đầu. Ép stdout/stderr sang UTF-8, lỗi thì bỏ qua.
    for _s in (sys.stdout, sys.stderr):
        try: _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception: pass

def win_toast(title, body):
    """Thông báo bong bóng trên Windows bằng PowerShell + NotifyIcon (chỉ dùng
    thư viện chuẩn, không cài thêm gì). Nội dung truyền qua biến môi trường để
    khỏi lo ngoặc kép trong tiêu đề. Bản Windows tạm chưa có nút bấm trên
    thông báo như notify-send (snooze/dời/xong) — chỉ hiện thông báo."""
    try:
        env = dict(os.environ)
        env["SHINI_N_TITLE"] = title or "Shini Tasks"
        env["SHINI_N_BODY"] = body or ""
        ps = ("Add-Type -AssemblyName System.Windows.Forms; "
              "$n = New-Object System.Windows.Forms.NotifyIcon; "
              "$n.Icon = [System.Drawing.SystemIcons]::Information; "
              "$n.Visible = $true; "
              "$n.ShowBalloonTip(6000, $env:SHINI_N_TITLE, $env:SHINI_N_BODY, "
              "[System.Windows.Forms.ToolTipIcon]::Info); "
              "Start-Sleep -Seconds 7; $n.Dispose()")
        subprocess.Popen(["powershell", "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden",
                          "-Command", ps], env=env,
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except Exception:
        pass

# ---------- DB ----------
@contextmanager
def db():
    # BẮT BUỘC đóng kết nối: `with sqlite3.connect()` chỉ commit chứ KHÔNG close —
    # bản cũ rò 1020 file descriptor tới tasks.db sau ~1 giờ (Errno 24, sập API).
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    try:
        yield c
        c.commit()
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()

def init_db():
    with db() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS tasks(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL, notes TEXT DEFAULT '',
            due_date TEXT, due_time TEXT,
            important INTEGER DEFAULT 0, urgent INTEGER DEFAULT 0,
            tags TEXT DEFAULT '', estimate_min INTEGER,
            remind_before INTEGER DEFAULT 30,
            repeat_rule TEXT DEFAULT 'none',
            status TEXT DEFAULT 'todo',
            source TEXT DEFAULT 'web',
            notified INTEGER DEFAULT 0,
            created_at TEXT, done_at TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT)""")
        # --- Cột công việc TUỲ CHỈNH (Sinh tự thêm/đổi tên/xoá từ app) ---
        c.execute("""CREATE TABLE IF NOT EXISTS columns(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL, color TEXT DEFAULT '#60A5FA', position INTEGER DEFAULT 0)""")
        # --- Lưu trữ việc đã xong bị TỰ XOÁ sau 15 ngày (Sinh 2026-11-15):
        #     chỉ giữ bản ghi nhẹ để THỐNG KÊ vẫn tính đủ như chưa xoá ---
        c.execute("""CREATE TABLE IF NOT EXISTS done_archive(
            id INTEGER PRIMARY KEY, title TEXT, column_id INTEGER,
            due_date TEXT, due_time TEXT, estimate_min INTEGER,
            done_at TEXT, created_at TEXT, archived_at TEXT)""")
        cols = [r[1] for r in c.execute("PRAGMA table_info(tasks)").fetchall()]
        if "column_id" not in cols:
            c.execute("ALTER TABLE tasks ADD COLUMN column_id INTEGER")
        if "subtasks" not in cols:
            c.execute("ALTER TABLE tasks ADD COLUMN subtasks TEXT DEFAULT '[]'")
        if "escalated" not in cols:
            c.execute("ALTER TABLE tasks ADD COLUMN escalated INTEGER DEFAULT 0")
        if "updated_at" not in cols:
            # Mốc sửa đổi gần nhất — nền cho ĐỒNG BỘ 2 máy (bản nào mới hơn thì thắng)
            c.execute("ALTER TABLE tasks ADD COLUMN updated_at TEXT")
            c.execute("UPDATE tasks SET updated_at = COALESCE(created_at, ?) WHERE updated_at IS NULL",
                      (datetime.now().isoformat(timespec="seconds"),))
        if "repeat_left" not in cols:
            # Số lần lặp CÒN LẠI (NULL = lặp mãi) — cho kiểu 'lặp thêm N lần rồi dừng'
            c.execute("ALTER TABLE tasks ADD COLUMN repeat_left INTEGER")
        if c.execute("SELECT COUNT(*) FROM columns").fetchone()[0] == 0:
            for i, (nm, cl) in enumerate([("Làm ngay", "#F87171"), ("Hôm nay", "#E5E5E5"),
                                          ("Tuần này", "#60A5FA"), ("Tháng này / Để sau", "#A78BFA")]):
                c.execute("INSERT INTO columns(name, color, position) VALUES(?,?,?)", (nm, cl, i))
        # di trú: việc cũ chưa có cột -> xếp theo hạn/mức gấp như bảng cột đời đầu
        ids = [r[0] for r in c.execute("SELECT id FROM columns ORDER BY position, id").fetchall()]
        if ids:
            today = date.today()
            for r in c.execute("SELECT * FROM tasks WHERE column_id IS NULL").fetchall():
                t = dict(r); tgt = ids[-1]
                if t["status"] != "done":
                    overdue = t["due_date"] and (t["due_date"] < today.isoformat() or
                              (t["due_date"] == today.isoformat() and t["due_time"] and t["due_time"] < datetime.now().strftime("%H:%M")))
                    if overdue or (t["important"] and t["urgent"]): tgt = ids[0]
                    elif t["due_date"] == today.isoformat(): tgt = ids[min(1, len(ids) - 1)]
                    elif t["due_date"] and t["due_date"] <= (today + timedelta(days=7)).isoformat(): tgt = ids[min(2, len(ids) - 1)]
                c.execute("UPDATE tasks SET column_id=? WHERE id=?", (tgt, t["id"]))

init_db()

def first_column_id():
    with db() as c:
        r = c.execute("SELECT id FROM columns ORDER BY position, id LIMIT 1").fetchone()
        return r[0] if r else None

# ---------- Điểm ưu tiên: việc nào nên làm trước ----------
def score(t, now=None):
    now = now or datetime.now()
    imp, urg = t["important"], t["urgent"]
    if imp and urg: s = 100      # Q1: gấp + quan trọng -> làm ngay
    elif imp:       s = 72       # Q2: quan trọng -> lên lịch, làm sớm
    elif urg:       s = 52       # Q3: gấp -> làm nhanh nếu rảnh
    else:           s = 18       # Q4
    if t["due_date"]:
        try:
            due = datetime.fromisoformat(t["due_date"] + "T" + (t["due_time"] or "23:59"))
            delta_h = (due - now).total_seconds() / 3600
            if delta_h < 0: s += 45 + min(30, -delta_h)        # quá hạn: đẩy mạnh lên đầu
            elif delta_h < 6: s += 38
            elif delta_h < 24: s += 26
            elif delta_h < 72: s += 12
            elif delta_h < 24 * 7: s += 5
        except ValueError:
            pass
    if t["status"] == "doing": s += 8
    return round(s, 1)

def row_out(r, now=None):
    d = dict(r)
    d["important"] = bool(d["important"]); d["urgent"] = bool(d["urgent"])
    d["tags"] = [x for x in (d["tags"] or "").split(",") if x]
    try: d["subtasks"] = json.loads(d.get("subtasks") or "[]")
    except Exception: d["subtasks"] = []
    d["score"] = score(d, now) if d["status"] != "done" else 0
    q = (1 if d["important"] else 0, 1 if d["urgent"] else 0)
    d["quadrant"] = {(1,1):"Q1",(1,0):"Q2",(0,1):"Q3",(0,0):"Q4"}[q]
    return d

# ---------- Phân tích câu thêm nhanh (tiếng Việt) ----------
WEEKDAY = {"thứ 2":0,"thứ hai":0,"t2":0,"thứ 3":1,"thứ ba":1,"t3":1,"thứ 4":2,"thứ tư":2,"t4":2,
           "thứ 5":3,"thứ năm":3,"t5":3,"thứ 6":4,"thứ sáu":4,"t6":4,"thứ 7":5,"thứ bảy":5,"t7":5,
           "chủ nhật":6,"cn":6}
def parse_quick(text):
    raw = text.strip()
    low = " " + raw.lower() + " "
    today = date.today()
    due_d, due_t = None, None
    important = urgent = False
    tags, estimate, remind = [], None, 30
    t = raw
    # thẻ #tag
    for m in re.finditer(r"#([\w\-à-ỹ]+)", t, re.I):
        tags.append(m.group(1))
    t = re.sub(r"#[\w\-à-ỹ]+", "", t, flags=re.I).strip()
    # cờ ưu tiên
    if re.search(r"!gấp|!gap|\bgấp\b|\bkhẩn\b", low): urgent = True
    if re.search(r"!quan.?trọng|!qt|\bquan trọng\b", low): important = True
    if re.search(r"!gấp\s*và\s*quan|!top", low): important = urgent = True
    t = re.sub(r"!(gấp|gap|quan\s*trọng|qt|top)\b", "", t, flags=re.I).strip()
    # --- Lặp NÂNG CAO ngay trong câu thêm nhanh (hướng D): 'mỗi ngày / mỗi tuần /
    #     mỗi tháng / mỗi T2 T4 T6', 'lặp (thêm) N lần' — trước đây phải mở hộp sửa.
    rep_rule, rep_left, rep_due = "none", None, None
    m = re.search(r"lặp\s+(thêm\s+)?(\d+)\s*lần", t, re.I)
    if m:
        n = int(m.group(2))
        # 'lặp thêm N lần' = sinh thêm N bản nữa; 'lặp N lần' = TỔNG N lần (trừ lần đầu)
        rep_left = n if m.group(1) else max(0, n - 1)
        t = (t[:m.start()] + t[m.end():]).strip()
    m = re.search(r"\bmỗi\s+(ngày|sáng|chiều|tối)\b|\bhằng\s+ngày\b", t, re.I)
    if m:
        rep_rule = "daily"; t = (t[:m.start()] + t[m.end():]).strip()
    if rep_rule == "none":
        m = re.search(r"\bmỗi\s+tuần\b|\bhằng\s+tuần\b", t, re.I)
        if m: rep_rule = "weekly"; t = (t[:m.start()] + t[m.end():]).strip()
    if rep_rule == "none":
        m = re.search(r"\bmỗi\s+tháng\b|\bhằng\s+tháng\b", t, re.I)
        if m: rep_rule = "monthly"; t = (t[:m.start()] + t[m.end():]).strip()
    if rep_rule == "none":
        m = re.search(r"\bmỗi\s+((?:thứ\s*[2-7]|t[2-7]|chủ\s*nhật|cn)(?:[\s,]+(?:và\s+)?)?)+", t, re.I)
        if m:
            wds = set()
            for tm in re.finditer(r"thứ\s*([2-7])|t([2-7])|chủ\s*nhật|(cn)\b", m.group(0), re.I):
                if tm.group(1): wds.add(int(tm.group(1)) - 2)
                elif tm.group(2): wds.add(int(tm.group(2)) - 2)
                else: wds.add(6)
            if wds:
                rep_rule = "wd:" + ",".join(str(x) for x in sorted(wds))
                for add in range(0, 8):
                    cand = today + timedelta(days=add)
                    if cand.weekday() in wds: rep_due = cand; break
                t = (t[:m.start()] + t[m.end():]).strip()
    # giờ có phút: 9h30, 14:30 -> giờ hạn
    m = re.search(r"\b(\d{1,2})[:h](\d{2})\b", t)
    if m:
        due_t = f"{int(m.group(1)):02d}:{int(m.group(2)):02d}"
        t = (t[:m.start()] + t[m.end():]).strip()
    # thời lượng theo phút: 30p, 45 phút
    m2 = re.search(r"(\d+)\s*(?:phút|p\b)", t)
    if m2:
        estimate = int(m2.group(1)); t = (t[:m2.start()] + t[m2.end():]).strip()
    # token giờ trần "9h" / "2 giờ": ở đầu câu hoặc ngay sau chữ ngày = GIỜ HẠN,
    # nằm ở cuối câu sau nội dung việc = THỜI LƯỢNG (ví dụ "nộp báo cáo 2h")
    m = re.search(r"\b(\d{1,2})\s*(?:giờ|h)\b", t)
    if m:
        val = int(m.group(1))
        before = t[:m.start()].strip().lower()
        after_date = bool(re.search(r"(mai|nay|hôm nay|thứ\s*\d|chủ nhật|cn|ngày|sáng|chiều|tối|lúc|vào)$", before))
        if due_t is None and val <= 23 and (not before or after_date):
            due_t = f"{val:02d}:00"
        else:
            estimate = (estimate or 0) + val * 60
        t = (t[:m.start()] + t[m.end():]).strip()
    # nhắc trước: nhắc 15p / nhắc trước 1h
    m = re.search(r"nhắc(?:\s*trước)?\s*(\d+)\s*(phút|p|giờ|h)", t)
    if m:
        remind = int(m.group(1)) * (60 if m.group(2) in ("giờ","h") else 1)
        t = (t[:m.start()] + t[m.end():]).strip()
    # ngày (việc lặp theo thứ: ngày đầu tiên đã chốt ở khối lặp phía trên)
    if rep_due is not None: due_d = rep_due
    elif re.search(r"\bhôm nay\b|\bnay\b", low): due_d = today
    elif re.search(r"\bngày mai\b|\bmai\b", low): due_d = today + timedelta(days=1)
    elif re.search(r"\bngày kia\b|\bmốt\b", low): due_d = today + timedelta(days=2)
    elif re.search(r"\bcuối tuần\b", low): due_d = today + timedelta(days=(5 - today.weekday()) % 7 or 7)
    else:
        m = re.search(r"\b(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?\b", t)
        if m:
            y = int(m.group(3) or today.year)
            if y < 100: y += 2000
            try: due_d = date(y, int(m.group(2)), int(m.group(1)))
            except ValueError: due_d = None
            if due_d: t = (t[:m.start()] + t[m.end():]).strip()
        else:
            for name, wd in sorted(WEEKDAY.items(), key=lambda x: -len(x[0])):
                if re.search(r"\b" + re.escape(name) + r"\b", low):
                    delta = (wd - today.weekday()) % 7
                    due_d = today + timedelta(days=delta if delta else 7)
                    t = re.sub(re.escape(name), "", t, flags=re.I).strip()
                    break
    # việc lặp mà chưa có ngày nào thì lấy HÔM NAY làm lần đầu tiên
    if rep_rule != "none" and not due_d: due_d = today
    # dọn chữ ngày/giờ còn sót khỏi tiêu đề
    t = re.sub(r"\b(hôm nay|ngày mai|ngày kia|cuối tuần|sáng|chiều|tối|lúc|vào|mai|mốt|nay)\b", "", t, flags=re.I)
    t = re.sub(r"\s+", " ", t).strip(" -–—,")
    return {"title": t or raw, "due_date": due_d.isoformat() if due_d else None,
            "due_time": due_t, "important": important, "urgent": urgent,
            "tags": tags, "estimate_min": estimate, "remind_before": remind,
            "repeat_rule": rep_rule, "repeat_left": rep_left}

def insert_task(d, source="web"):
    now = datetime.now().isoformat(timespec="seconds")
    col = d.get("column_id") or first_column_id()
    subs = d.get("subtasks") or []
    if not isinstance(subs, str): subs = json.dumps(subs, ensure_ascii=False)
    with db() as c:
        cur = c.execute("""INSERT INTO tasks(title,notes,due_date,due_time,important,urgent,tags,
            estimate_min,remind_before,repeat_rule,status,source,created_at,column_id,subtasks,updated_at,repeat_left)
            VALUES(?,?,?,?,?,?,?,?,?,?, 'todo', ?, ?, ?, ?, ?, ?)""",
            (d.get("title","").strip(), d.get("notes",""), d.get("due_date"), d.get("due_time"),
             1 if d.get("important") else 0, 1 if d.get("urgent") else 0,
             ",".join(d.get("tags") or []), d.get("estimate_min"),
             d.get("remind_before", 30), d.get("repeat_rule","none"), source, now, col, subs, now,
             d.get("repeat_left")))
        rid = cur.lastrowid
    with db() as c:
        return row_out(c.execute("SELECT * FROM tasks WHERE id=?", (rid,)).fetchone())

# ---------- Thông báo desktop ----------
def notify(title, body, urgency="normal"):
    if IS_WIN:
        win_toast(title, body)
        return
    env = dict(os.environ)
    env.setdefault("DISPLAY", ":0")
    env.setdefault("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
    env.setdefault("DBUS_SESSION_BUS_ADDRESS", f"unix:path=/run/user/{os.getuid()}/bus")
    try:
        subprocess.run(["notify-send", "-a", "Shini Tasks", "-u", urgency, title, body],
                       env=env, timeout=8, check=False)
    except Exception:
        pass

def _api_self(method, path, body=None):
    """Tự gọi API của chính engine — dùng lại logic done/PATCH có sẵn cho các nút
    bấm trên thông báo, khỏi chép lại xử lý việc lặp/dời hạn."""
    try:
        data = json.dumps(body or {}).encode() if body is not None else None
        req = urllib.request.Request(f"http://127.0.0.1:{PORT}{path}", data=data, method=method,
                                     headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=5).read()
    except Exception as e:
        print("self api error:", e, flush=True)

def notify_task_actions(title, body, task_id, urgency="normal"):
    """Thông báo CÓ NÚT BẤM (GĐ1): notify-send hỗ trợ --action, in tên action ra
    stdout khi người dùng bấm — chạy thread riêng vì tiến trình phải CHỜ bấm.
    done -> đánh dấu xong qua API; tomorrow -> dời hạn +1 ngày qua API;
    snooze -> ghi mốc nhắc lại sau 15 phút vào meta + mở lại cờ nhắc."""
    if IS_WIN:
        # Windows v1: thông báo thường, chưa có nút bấm (xem win_toast).
        notify(title, body, urgency)
        return
    def run():
        env = dict(os.environ)
        env.setdefault("DISPLAY", ":0")
        env.setdefault("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
        env.setdefault("DBUS_SESSION_BUS_ADDRESS", f"unix:path=/run/user/{os.getuid()}/bus")
        try:
            p = subprocess.run(["notify-send", "-a", "Shini Tasks", "-u", urgency,
                                "--action", "snooze=⏰ Nhắc lại sau 15 phút",
                                "--action", "tomorrow=🌅 Dời sang mai",
                                "--action", "done=✓ Đã xong việc này",
                                title, body], env=env, capture_output=True, text=True, timeout=900)
            act = (p.stdout or "").strip()
        except Exception:
            return
        if act == "done":
            _api_self("POST", f"/api/tasks/{task_id}/done")
        elif act == "tomorrow":
            with db() as c:
                r = c.execute("SELECT due_date FROM tasks WHERE id=?", (task_id,)).fetchone()
            if r:
                base = date.fromisoformat(r["due_date"]) if r["due_date"] else date.today()
                _api_self("PATCH", f"/api/tasks/{task_id}",
                          {"due_date": (base + timedelta(days=1)).isoformat()})
        elif act == "snooze":
            until = (datetime.now() + timedelta(minutes=15)).isoformat(timespec="seconds")
            with db() as c:
                c.execute("INSERT INTO meta(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v",
                          (f"snooze_{task_id}", until))
                c.execute("UPDATE tasks SET notified=0, escalated=0 WHERE id=?", (task_id,))
    threading.Thread(target=run, daemon=True).start()

LEVEL_NAMES = {(1, 1): "Làm ngay", (1, 0): "Quan trọng", (0, 1): "Gấp", (0, 0): "Thường"}

def level_name(t):
    return LEVEL_NAMES[(1 if t["important"] else 0, 1 if t["urgent"] else 0)]

def _fmt_when(due, now):
    mins = int((due - now).total_seconds() // 60)
    if mins < 0: return f"đã quá hạn {abs(mins)} phút"
    if mins < 60: return f"còn {mins} phút"
    return f"còn {mins // 60} giờ {mins % 60} phút" if mins % 60 else f"còn {mins // 60} giờ"

def morning_briefing(now):
    """Bản tin 07:30: chào + tổng quan + 3 việc nên làm trước (có giờ). Trả về True nếu đã xử lý hôm nay."""
    key = "morning_" + now.strftime("%Y-%m-%d")
    with db() as c:
        if c.execute("SELECT v FROM meta WHERE k=?", (key,)).fetchone(): return True
        rows = [row_out(r, now) for r in c.execute(
            "SELECT * FROM tasks WHERE status!='done' AND due_date IS NOT NULL AND due_date<=?",
            (now.strftime("%Y-%m-%d"),)).fetchall()]
        overdue = [t for t in rows if t["due_date"] < now.strftime("%Y-%m-%d")]
        rows.sort(key=lambda x: -x["score"])
        if rows:
            # Bản tin THÔNG MINH hơn (GĐ3): thêm khối lượng giờ, việc chưa xếp giờ
            # và 1 gợi ý bắt đầu — thay cho bản liệt kê thuần trước đây.
            today_rows = [x for x in rows if x["due_date"] == now.strftime("%Y-%m-%d")]
            work_min = sum(x.get("estimate_min") or 60 for x in today_rows)
            no_time = len([x for x in today_rows if not x.get("due_time")])
            lines = []
            for x in rows[:3]:
                tm = f"{x['due_time']} · " if x.get("due_time") else ""
                lines.append(f"• {tm}{x['title']}")
            body = "Làm trước tiên:\n" + "\n".join(lines)
            if today_rows:
                body += f"\n🕐 Khối lượng hôm nay: ~{work_min // 60} giờ {work_min % 60} phút ({len(today_rows)} việc)."
            if overdue: body += f"\n⚠️ Có {len(overdue)} việc đã quá hạn từ hôm trước."
            if no_time: body += f"\n📥 {no_time} việc hôm nay chưa xếp giờ — mở Lịch, bấm '⚡ Tự xếp' để app điền vào ô trống."
            top = rows[0]
            body += f"\n💡 Gợi ý: bắt đầu bằng «{top['title']}»" + (f" lúc {top['due_time']}." if top.get("due_time") else ".")
            notify(f"☀️ Chào buổi sáng Sinh — hôm nay {len(rows)} việc đến hạn", body)
        c.execute("INSERT INTO meta(k,v) VALUES(?, '1')", (key,))
    return True

def evening_preview(now):
    """Bản tin 20:30: nhìn trước ngày mai (kiểu Sunsama) + việc còn tồn. Chỉ gửi khi có nội dung."""
    key = "evening_" + now.strftime("%Y-%m-%d")
    tomorrow = (now + timedelta(days=1)).strftime("%Y-%m-%d")
    with db() as c:
        if c.execute("SELECT v FROM meta WHERE k=?", (key,)).fetchone(): return True
        rows = [row_out(r, now) for r in c.execute(
            "SELECT * FROM tasks WHERE status!='done' AND due_date=?", (tomorrow,)).fetchall()]
        rows.sort(key=lambda x: (x.get("due_time") or "99:99", -x["score"]))
        leftovers = c.execute("SELECT COUNT(*) FROM tasks WHERE status!='done' AND due_date IS NOT NULL AND due_date<=?",
                               (now.strftime("%Y-%m-%d"),)).fetchone()[0]
        done_today = c.execute("SELECT COUNT(*) FROM tasks WHERE status='done' AND done_at LIKE ?",
                                (now.strftime("%Y-%m-%d") + "%",)).fetchone()[0]
        if rows or leftovers:
            parts = []
            if done_today: parts.append(f"✅ Hôm nay đã xong {done_today} việc.")
            if rows:
                parts.append("Ngày mai:\n" + "\n".join(
                    f"• {(x['due_time'] + ' · ') if x.get('due_time') else ''}{x['title']}" for x in rows[:4]))
                wmin = sum(x.get("estimate_min") or 60 for x in rows)
                parts.append(f"🕐 Khối lượng ngày mai: ~{wmin // 60} giờ {wmin % 60} phút.")
            if leftovers: parts.append(f"📌 Còn {leftovers} việc hôm nay chưa xong — dời sang mai trong app nếu cần.")
            notify(f"🌙 Tối nay nhìn trước — mai có {len(rows)} việc", "\n".join(parts))
        c.execute("INSERT INTO meta(k,v) VALUES(?, '1')", (key,))
    return True

def reminder_loop():
    while True:
        try:
            now = datetime.now()
            with db() as c:
                rows = c.execute("SELECT * FROM tasks WHERE status!='done' AND due_date IS NOT NULL").fetchall()
                for r in rows:
                    # Đang hoãn nhắc (nút 'Nhắc lại sau 15 phút' trên thông báo) thì bỏ qua
                    sz = c.execute("SELECT v FROM meta WHERE k=?", (f"snooze_{r['id']}",)).fetchone()
                    if sz and sz["v"] > now.isoformat(timespec="seconds"): continue
                    due = datetime.fromisoformat(r["due_date"] + "T" + (r["due_time"] or "09:00"))
                    # 1) nhắc trước hạn — nội dung có ngữ cảnh: còn bao lâu, ước lượng, mức ưu tiên
                    if not r["notified"]:
                        remind_at = due - timedelta(minutes=r["remind_before"] or 30)
                        if remind_at <= now <= due + timedelta(hours=2):
                            ctx = [f"🕐 {due.strftime('%H:%M')} · {_fmt_when(due, now)}"]
                            if r["estimate_min"]: ctx.append(f"~{r['estimate_min']} phút")
                            ctx.append("mức " + level_name(r))
                            notify_task_actions(("⏰ Sắp đến hạn — ĐÃ QUÁ HẠN" if now > due else "⏰ Sắp đến giờ"),
                                   r["title"] + "\n" + " · ".join(ctx), r["id"],
                                   "critical" if r["important"] and r["urgent"] else "normal")
                            c.execute("UPDATE tasks SET notified=1 WHERE id=?", (r["id"],))
                    # 2) leo thang: quá hạn quá 30 phút mà chưa xong -> nhắc mạnh 1 lần
                    if not r["escalated"] and now > due + timedelta(minutes=30):
                        notify_task_actions("⚠️ QUÁ HẠN — việc này vẫn chưa xong",
                               f"{r['title']}\n{_fmt_when(due, now)} · mức {level_name(r)}",
                               r["id"], "critical")
                        c.execute("UPDATE tasks SET escalated=1 WHERE id=?", (r["id"],))
            if now.time() >= dtime(7, 30): morning_briefing(now)
            if now.time() >= dtime(20, 30): evening_preview(now)
        except Exception as e:
            print("reminder error:", e, flush=True)
        time.sleep(30)

def inbox_loop():
    """Thêm nhanh kiểu phổ quát: mỗi dòng trong inbox.txt = 1 việc (ghi từ bất kỳ app nào đồng bộ file)."""
    path = os.path.join(DATA, "inbox.txt")
    seen = 0
    while True:
        try:
            if os.path.exists(path):
                with open(path, encoding="utf-8") as f:
                    lines = f.read().splitlines()
                while seen < len(lines):
                    line = lines[seen].strip(); seen += 1
                    if line and not line.startswith("#"):
                        insert_task(parse_quick(line), source="inbox")
        except Exception as e:
            print("inbox error:", e, flush=True)
        time.sleep(5)

def purge_old_done():
    """Tự xoá việc ĐÃ XONG quá 15 ngày khỏi bảng tasks (Sinh 2026-11-15) —
    trước khi xoá, chép bản ghi nhẹ sang done_archive để thống kê (streak,
    tổng đã xong, đúng hạn, theo cột) vẫn tính đủ như chưa xoá."""
    cutoff = (date.today() - timedelta(days=15)).isoformat()
    n = 0
    with db() as c:
        rows = c.execute("SELECT * FROM tasks WHERE status='done' AND done_at IS NOT NULL "
                         "AND substr(done_at,1,10) < ?", (cutoff,)).fetchall()
        for r in rows:
            c.execute("""INSERT OR REPLACE INTO done_archive(id,title,column_id,due_date,due_time,
                         estimate_min,done_at,created_at,archived_at) VALUES(?,?,?,?,?,?,?,?,?)""",
                      (r["id"], r["title"], r["column_id"], r["due_date"], r["due_time"],
                       r["estimate_min"], r["done_at"], r["created_at"],
                       datetime.now().isoformat(timespec="seconds")))
            c.execute("DELETE FROM tasks WHERE id=?", (r["id"],))
            n += 1
    if n: print(f"purge: da xoa {n} viec xong qua 15 ngay (van tinh trong thong ke)", flush=True)
    return n

def backup_loop():
    """Sao lưu tasks.db MỖI NGÀY vào thư mục backups/ (giữ 14 bản gần nhất).
    Dùng API backup của SQLite nên an toàn ngay cả khi DB đang được ghi."""
    bdir = os.path.join(DATA, "backups")
    os.makedirs(bdir, exist_ok=True)
    while True:
        try:
            stamp = date.today().strftime("%Y%m%d")
            target = os.path.join(bdir, f"tasks-{stamp}.db")
            if not os.path.exists(target):
                src = sqlite3.connect(DB)
                dst = sqlite3.connect(target)
                with dst:
                    src.backup(dst)
                dst.close(); src.close()
                files = sorted(f for f in os.listdir(bdir) if f.startswith("tasks-2") and f.endswith(".db"))
                for old in files[:-14]:
                    os.remove(os.path.join(bdir, old))
        except Exception as e:
            print("backup error:", e, flush=True)
        # Tự xoá việc đã xong quá 15 ngày — 1 lần/ngày (đánh dấu trong meta)
        try:
            key = "purge_" + date.today().isoformat()
            with db() as c:
                purged_today = c.execute("SELECT v FROM meta WHERE k=?", (key,)).fetchone()
            if not purged_today:
                purge_old_done()
                with db() as c:
                    c.execute("INSERT OR REPLACE INTO meta(k,v) VALUES(?,?)", (key, "1"))
        except Exception as e:
            print("purge error:", e, flush=True)
        time.sleep(3600)

# ---------- HTTP ----------
class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _json(self, obj, code=200):
        b = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers(); self.wfile.write(b)
    def _auth(self):
        return not TOKEN or self.headers.get("X-Token") == TOKEN
    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}")
    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/" or u.path == "/index.html":
            p = os.path.join(BASE, "static", "index.html")
            with open(p, "rb") as f:
                b = f.read()
            self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
            return
        if u.path == "/api/tasks":
            q = parse_qs(u.query); view = q.get("view", ["today"])[0]
            today = date.today(); now = datetime.now()
            with db() as c:
                rows = [row_out(r, now) for r in c.execute("SELECT * FROM tasks ORDER BY created_at DESC").fetchall()]
            if view == "today":
                out = [t for t in rows if t["status"] != "done" and (not t["due_date"] or t["due_date"] <= today.isoformat())]
            elif view == "week":
                end = (today + timedelta(days=7 - today.weekday())).isoformat()
                out = [t for t in rows if t["status"] != "done" and (not t["due_date"] or t["due_date"] <= end)]
            elif view == "month":
                end = (today.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
                out = [t for t in rows if t["status"] != "done" and (not t["due_date"] or t["due_date"] <= end.isoformat())]
            elif view == "done":
                out = [t for t in rows if t["status"] == "done"]
            else:
                out = [t for t in rows if t["status"] != "done"]
            out.sort(key=lambda x: -x["score"])
            return self._json({"tasks": out})
        if u.path == "/api/columns":
            with db() as c:
                cols = [dict(r) for r in c.execute("SELECT * FROM columns ORDER BY position, id").fetchall()]
            return self._json({"columns": cols})
        if u.path == "/api/export":
            # Gói toàn bộ dữ liệu (việc + cột) để sao lưu rời / đồng bộ sang máy khác
            now = datetime.now()
            with db() as c:
                tasks = [row_out(r, now) for r in c.execute("SELECT * FROM tasks").fetchall()]
                cols = [dict(r) for r in c.execute("SELECT * FROM columns ORDER BY position, id").fetchall()]
            return self._json({"exported_at": now.isoformat(timespec="seconds"),
                               "tasks": tasks, "columns": cols})
        if u.path == "/api/calendar.ics":
            # Lịch MỘT CHIỀU (chỉ xem) cho Google Calendar / lịch iOS đăng ký theo
            # dõi: việc có giờ -> sự kiện giờ; việc chỉ có ngày -> sự kiện cả ngày.
            now = datetime.now()
            with db() as c:
                rows = [row_out(r, now) for r in c.execute(
                    "SELECT * FROM tasks WHERE status!='done' AND due_date IS NOT NULL "
                    "ORDER BY due_date, due_time").fetchall()]
            def esc(s):
                return (s or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")
            lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Shini Tasks//VN",
                     "CALSCALE:GREGORIAN", "X-WR-CALNAME:Shini Tasks"]
            stamp = now.strftime("%Y%m%dT%H%M%S")
            for t in rows:
                lines.append("BEGIN:VEVENT")
                lines.append(f"UID:task-{t['id']}@shini.tasks")
                lines.append(f"DTSTAMP:{stamp}")
                if t.get("due_time"):
                    start = datetime.fromisoformat(t["due_date"] + "T" + t["due_time"])
                    end = start + timedelta(minutes=t.get("estimate_min") or 60)
                    lines.append("DTSTART:" + start.strftime("%Y%m%dT%H%M%S"))
                    lines.append("DTEND:" + end.strftime("%Y%m%dT%H%M%S"))
                else:
                    lines.append("DTSTART;VALUE=DATE:" + t["due_date"].replace("-", ""))
                    nxt = date.fromisoformat(t["due_date"]) + timedelta(days=1)
                    lines.append("DTEND;VALUE=DATE:" + nxt.strftime("%Y%m%d"))
                lines.append("SUMMARY:" + esc(t["title"]))
                if t.get("notes"): lines.append("DESCRIPTION:" + esc(t["notes"]))
                lines.append("END:VEVENT")
            lines.append("END:VCALENDAR")
            b = "\r\n".join(lines).encode("utf-8")
            self.send_response(200); self.send_header("Content-Type", "text/calendar; charset=utf-8")
            self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
            return
        if u.path == "/api/parse":
            # Xem trước cách app hiểu câu thêm nhanh (không tạo việc) — kiểu Todoist
            text = (parse_qs(u.query).get("text", [""])[0] or "").strip()
            return self._json({"parsed": parse_quick(text) if text else None})
        if u.path == "/api/done-archive":
            # Việc đã xong bị tự xoá sau 15 ngày — bản ghi nhẹ cho thống kê
            with db() as c:
                rows = c.execute("SELECT id,title,column_id,due_date,due_time,estimate_min,"
                                 "done_at,created_at FROM done_archive ORDER BY done_at").fetchall()
            return self._json({"tasks": [dict(r, status="done", subtasks=[]) for r in rows]})
        if u.path == "/api/stats":
            now = datetime.now(); today = date.today().isoformat()
            with db() as c:
                rows = [row_out(r, now) for r in c.execute("SELECT * FROM tasks").fetchall()]
            open_ = [t for t in rows if t["status"] != "done"]
            # --- Thống kê sâu (GĐ3): streak ngày có việc xong, so tuần này/tuần trước,
            #     cột ứ đọng lâu nhất — tính từ done_at/created_at có sẵn ---
            done_days = {}
            for t in rows:
                if t["status"] == "done" and t.get("done_at"):
                    done_days[t["done_at"][:10]] = done_days.get(t["done_at"][:10], 0) + 1
            # Gộp cả việc đã tự xoá sau 15 ngày (done_archive) — thống kê không đổi
            with db() as c:
                arch_rows = c.execute("SELECT done_at FROM done_archive").fetchall()
            for r in arch_rows:
                if r["done_at"]:
                    done_days[r["done_at"][:10]] = done_days.get(r["done_at"][:10], 0) + 1
            streak, cur = 0, date.today()
            if done_days.get(cur.isoformat(), 0) == 0: cur -= timedelta(days=1)
            while done_days.get(cur.isoformat(), 0) > 0:
                streak += 1; cur -= timedelta(days=1)
            monday = date.today() - timedelta(days=date.today().weekday())
            def _done_between(a, b):
                return sum(v for k, v in done_days.items() if a.isoformat() <= k <= b.isoformat())
            done_this_week = _done_between(monday, monday + timedelta(days=6))
            done_last_week = _done_between(monday - timedelta(days=7), monday - timedelta(days=1))
            with db() as c:
                colnames = {r["id"]: r["name"] for r in c.execute("SELECT id, name FROM columns").fetchall()}
            stale = []
            for cid, nm in colnames.items():
                copen = [t for t in open_ if t.get("column_id") == cid and t.get("created_at")]
                if copen:
                    oldest = min(t["created_at"][:10] for t in copen)
                    stale.append({"column": nm, "open": len(copen),
                                  "oldest_days": (date.today() - date.fromisoformat(oldest)).days})
            stale.sort(key=lambda x: -x["oldest_days"])
            return self._json({
                "open": len(open_), "done_total": len(rows) - len(open_) + len(arch_rows),
                "archived_done": len(arch_rows),
                "due_today": len([t for t in open_ if t["due_date"] == today]),
                "overdue": len([t for t in open_ if t["due_date"] and t["due_date"] < today]),
                "next": sorted(open_, key=lambda x: -x["score"])[:3],
                "by_quadrant": {q: len([t for t in open_ if t["quadrant"] == q]) for q in ("Q1","Q2","Q3","Q4")},
                "streak": streak, "done_this_week": done_this_week,
                "done_last_week": done_last_week, "stale_columns": stale[:3]})
        return self._json({"error": "not found"}, 404)
    def do_POST(self):
        if not self._auth(): return self._json({"error": "sai token"}, 403)
        u = urlparse(self.path)
        if u.path == "/api/quick":
            d = self._body(); text = (d.get("text") or "").strip()
            if not text: return self._json({"error": "thiếu text"}, 400)
            return self._json({"task": insert_task(parse_quick(text), d.get("source", "api"))}, 201)
        if u.path == "/api/tasks":
            d = self._body()
            if not (d.get("title") or "").strip(): return self._json({"error": "thiếu tiêu đề"}, 400)
            return self._json({"task": insert_task(d, d.get("source", "web"))}, 201)
        m = re.match(r"/api/tasks/(\d+)/(done|reopen)$", u.path)
        if m:
            tid, act = int(m.group(1)), m.group(2)
            spawn = None
            with db() as c:
                old = c.execute("SELECT * FROM tasks WHERE id=?", (tid,)).fetchone()
                if not old: return self._json({"error": "không thấy việc"}, 404)
                if act == "done":
                    c.execute("UPDATE tasks SET status='done', done_at=?, updated_at=? WHERE id=?",
                              (datetime.now().isoformat(timespec="seconds"),
                               datetime.now().isoformat(timespec="seconds"), tid))
                    # Việc lặp lại: CHUẨN BỊ dữ liệu việc kế tiếp tại đây nhưng chỉ
                    # TẠO SAU khi khối db() này commit xong — insert_task mở kết nối
                    # RIÊNG, gọi ngay trong lúc giao dịch chưa commit sẽ dính
                    # 'database is locked' (lỗi tiềm ẩn từ bản cũ, lộ ra khi test
                    # lặp có chủ đích 2026-11-10). Quy tắc nâng cao (hướng B):
                    # - "wd:0,2,4" = lặp vào các THỨ đã chọn (0=Thứ Hai … 6=Chủ Nhật)
                    # - repeat_left: còn N lần thì sinh tiếp với N-1; =0 thì DỪNG;
                    #   NULL = lặp mãi như cũ
                    # - VIỆC CON của việc kế tiếp được LÀM MỚI (bỏ hết dấu đã xong) —
                    #   danh sách việc con của việc gốc đóng vai trò mẫu/checklist.
                    rule = old["repeat_rule"] or "none"
                    left = old["repeat_left"]
                    if rule != "none" and old["due_date"] and (left is None or left > 0):
                        base = date.fromisoformat(old["due_date"])
                        if rule == "daily": nd = base + timedelta(days=1)
                        elif rule == "weekly": nd = base + timedelta(days=7)
                        elif rule == "monthly": nd = base + timedelta(days=30)
                        elif rule.startswith("wd:"):
                            wds = {int(x) for x in rule[3:].split(",") if x != ""}
                            nd = base
                            for _ in range(7):
                                nd += timedelta(days=1)
                                if nd.weekday() in wds: break
                        else:
                            nd = None
                        if nd is not None:
                            d = dict(old); d["due_date"] = nd.isoformat(); d["tags"] = (old["tags"] or "").split(",")
                            try:
                                subs = json.loads(old["subtasks"] or "[]")
                                for s in subs: s["done"] = False
                                d["subtasks"] = subs
                            except Exception:
                                d["subtasks"] = []
                            d["repeat_left"] = (left - 1) if left is not None else None
                            spawn = {k: d[k] for k in ("title","notes","due_date","due_time","important","urgent","tags","estimate_min","remind_before","repeat_rule","column_id","subtasks","repeat_left")}
                else:
                    c.execute("UPDATE tasks SET status='todo', done_at=NULL, notified=0, updated_at=? WHERE id=?",
                              (datetime.now().isoformat(timespec="seconds"), tid))
                task_now = row_out(c.execute("SELECT * FROM tasks WHERE id=?", (tid,)).fetchone())
            if spawn is not None:
                insert_task(spawn, "repeat")
            return self._json({"task": task_now})
        if u.path == "/api/import":
            # Gộp dữ liệu từ máy khác: khớp theo id, bản updated_at MỚI HƠN thì thắng.
            # (Việc đã XOÁ hẳn ở máy kia không tự xoá ở máy này — giới hạn đã biết.)
            d = self._body()
            ins = upd = skip = 0
            with db() as c:
                # Việc đã TỰ XOÁ sau 15 ngày (có trong done_archive) không được
                # hồi sinh qua đồng bộ/khôi phục từ máy khác
                arch_ids = {r["id"] for r in c.execute("SELECT id FROM done_archive").fetchall()}
                for col in d.get("columns") or []:
                    cur = c.execute("SELECT id FROM columns WHERE id=?", (col["id"],)).fetchone()
                    if cur:
                        c.execute("UPDATE columns SET name=?, color=?, position=? WHERE id=?",
                                  (col["name"], col.get("color", "#60A5FA"), col.get("position", 0), col["id"]))
                    else:
                        c.execute("INSERT INTO columns(id, name, color, position) VALUES(?,?,?,?)",
                                  (col["id"], col["name"], col.get("color", "#60A5FA"), col.get("position", 0)))
                for t in d.get("tasks") or []:
                    if t.get("status") == "done" and t.get("id") in arch_ids:
                        skip += 1; continue
                    cur = c.execute("SELECT updated_at FROM tasks WHERE id=?", (t["id"],)).fetchone()
                    subs = t.get("subtasks") or []
                    if not isinstance(subs, str): subs = json.dumps(subs, ensure_ascii=False)
                    vals = (t.get("title", ""), t.get("notes", ""), t.get("due_date"), t.get("due_time"),
                            1 if t.get("important") else 0, 1 if t.get("urgent") else 0,
                            ",".join(t.get("tags") or []), t.get("estimate_min"), t.get("remind_before", 30),
                            t.get("repeat_rule", "none"), t.get("status", "todo"), t.get("source", "sync"),
                            t.get("created_at"), t.get("done_at"), t.get("column_id"), subs,
                            t.get("updated_at"), t.get("repeat_left"))
                    if cur is None:
                        c.execute("""INSERT INTO tasks(id,title,notes,due_date,due_time,important,urgent,tags,
                            estimate_min,remind_before,repeat_rule,status,source,created_at,done_at,column_id,
                            subtasks,updated_at,repeat_left) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                            (t["id"],) + vals)
                        ins += 1
                    elif (t.get("updated_at") or "") > (cur["updated_at"] or ""):
                        c.execute("""UPDATE tasks SET title=?,notes=?,due_date=?,due_time=?,important=?,urgent=?,
                            tags=?,estimate_min=?,remind_before=?,repeat_rule=?,status=?,source=?,created_at=?,
                            done_at=?,column_id=?,subtasks=?,updated_at=?,repeat_left=? WHERE id=?""",
                            vals + (t["id"],))
                        upd += 1
                    else:
                        skip += 1
            return self._json({"ok": True, "inserted": ins, "updated": upd, "skipped": skip})
        if u.path == "/api/notify-test":
            notify("🔔 Shini Tasks", "Thông báo thử — kênh nhắc việc đang hoạt động tốt.")
            return self._json({"ok": True})
        if u.path == "/api/columns":
            d = self._body()
            if not (d.get("name") or "").strip(): return self._json({"error": "thiếu tên cột"}, 400)
            with db() as c:
                pos = c.execute("SELECT COALESCE(MAX(position), -1) + 1 FROM columns").fetchone()[0]
                cur = c.execute("INSERT INTO columns(name, color, position) VALUES(?,?,?)",
                                (d["name"].strip(), d.get("color") or "#60A5FA", pos))
                r = c.execute("SELECT * FROM columns WHERE id=?", (cur.lastrowid,)).fetchone()
            return self._json({"column": dict(r)}, 201)
        return self._json({"error": "not found"}, 404)
    def do_PATCH(self):
        if not self._auth(): return self._json({"error": "sai token"}, 403)
        mc = re.match(r"/api/columns/(\d+)$", urlparse(self.path).path)
        if mc:
            d = self._body(); cid = int(mc.group(1))
            sets, vals = [], []
            for k in ("name", "color", "position"):
                if k in d: sets.append(f"{k}=?"); vals.append(d[k])
            if sets:
                with db() as c: c.execute(f"UPDATE columns SET {','.join(sets)} WHERE id=?", vals + [cid])
            with db() as c:
                r = c.execute("SELECT * FROM columns WHERE id=?", (cid,)).fetchone()
            return self._json({"column": dict(r)}) if r else self._json({"error": "không thấy cột"}, 404)
        m = re.match(r"/api/tasks/(\d+)$", urlparse(self.path).path)
        if not m: return self._json({"error": "not found"}, 404)
        d = self._body(); tid = int(m.group(1))
        fields = {"title":"title","notes":"notes","due_date":"due_date","due_time":"due_time",
                  "estimate_min":"estimate_min","remind_before":"remind_before","repeat_rule":"repeat_rule","repeat_left":"repeat_left","status":"status",
                  "column_id":"column_id"}
        sets, vals = [], []
        for k, col in fields.items():
            if k in d: sets.append(f"{col}=?"); vals.append(d[k])
        if "important" in d: sets.append("important=?"); vals.append(1 if d["important"] else 0)
        if "urgent" in d: sets.append("urgent=?"); vals.append(1 if d["urgent"] else 0)
        if "tags" in d: sets.append("tags=?"); vals.append(",".join(d["tags"]))
        if "subtasks" in d:
            subs = d["subtasks"]
            if not isinstance(subs, str): subs = json.dumps(subs, ensure_ascii=False)
            sets.append("subtasks=?"); vals.append(subs)
        if sets:
            sets.append("notified=0"); sets.append("escalated=0")
            sets.append("updated_at=?"); vals.append(datetime.now().isoformat(timespec="seconds"))
            with db() as c:
                c.execute(f"UPDATE tasks SET {','.join(sets)} WHERE id=?", vals + [tid])
        with db() as c:
            r = c.execute("SELECT * FROM tasks WHERE id=?", (tid,)).fetchone()
        return self._json({"task": row_out(r)}) if r else self._json({"error": "không thấy việc"}, 404)
    def do_DELETE(self):
        if not self._auth(): return self._json({"error": "sai token"}, 403)
        mc = re.match(r"/api/columns/(\d+)$", urlparse(self.path).path)
        if mc:
            cid = int(mc.group(1))
            with db() as c:
                ids = [r[0] for r in c.execute("SELECT id FROM columns ORDER BY position, id").fetchall()]
                if cid not in ids: return self._json({"error": "không thấy cột"}, 404)
                if len(ids) <= 1: return self._json({"error": "phải giữ ít nhất 1 cột"}, 400)
                fallback = next(i for i in ids if i != cid)
                c.execute("UPDATE tasks SET column_id=? WHERE column_id=?", (fallback, cid))
                c.execute("DELETE FROM columns WHERE id=?", (cid,))
            return self._json({"ok": True, "moved_to": fallback})
        m = re.match(r"/api/tasks/(\d+)$", urlparse(self.path).path)
        if not m: return self._json({"error": "not found"}, 404)
        with db() as c: c.execute("DELETE FROM tasks WHERE id=?", (int(m.group(1)),))
        return self._json({"ok": True})

def _win_hotkey_loop():
    """Windows: engine chạy nền thường trực nên giữ luôn phím toàn cục Alt+E
    (thay cho GNOME custom keybinding ở bản Linux): bấm Alt+E ở bất kỳ app nào
    -> mở cửa sổ bắt việc của app GUI nằm cạnh engine exe. Đăng ký trùng với
    app khác thì bỏ qua lặng lẽ, engine vẫn chạy bình thường."""
    try:
        import ctypes
        user32 = ctypes.windll.user32
        MOD_ALT, VK_E, WM_HOTKEY = 0x0001, 0x45, 0x0312
        if not user32.RegisterHotKey(None, 1, MOD_ALT, VK_E):
            print("hotkey Alt+E đã có app khác giữ — bỏ qua", flush=True)
            return
        gui = os.path.join(os.path.dirname(os.path.abspath(sys.executable)), "ShiniTasks.exe")
        import ctypes.wintypes as wt
        msg = wt.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == WM_HOTKEY and os.path.exists(gui):
                try:
                    subprocess.Popen([gui, "--capture"],
                                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                except Exception as e:
                    print("hotkey launch error:", e, flush=True)
    except Exception as e:
        print("hotkey error:", e, flush=True)

if __name__ == "__main__":
    threading.Thread(target=reminder_loop, daemon=True).start()
    threading.Thread(target=inbox_loop, daemon=True).start()
    threading.Thread(target=backup_loop, daemon=True).start()
    if IS_WIN and FROZEN:
        threading.Thread(target=_win_hotkey_loop, daemon=True).start()
    print(f"Shini Tasks chạy tại http://0.0.0.0:{PORT}  (DB: {DB})", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), H).serve_forever()
