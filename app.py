#!/usr/bin/env python3
"""Shini Tasks — APP DESKTOP (GTK4 + Libadwaita). Bản v4 theo yêu cầu của Sinh:
- CỘT TUỲ CHỈNH: tự thêm cột, đổi tên, đổi màu, xoá cột (việc dồn sang cột đầu),
  chuyển việc giữa các cột bằng nút ⇄, ô thêm việc nhỏ ngay trong từng cột.
- BỎ nhãn Q1–Q4: 4 mức ưu tiên hiển thị bằng TÊN SINH TỰ ĐẶT (lưu settings.json).
- 2 CHẾ ĐỘ SÁNG / TỐI: nút ☀/🌙 trên thanh tiêu đề, nhớ lựa chọn.
Engine dùng chung server.py (cổng 8790): nhắc hạn, bản tin sáng, thêm nhanh mọi nơi.
"""
import calendar, faulthandler, json, os, signal, subprocess, sys, threading, urllib.error, urllib.parse, urllib.request
from datetime import date, datetime, timedelta

# Windows (bản đóng exe — hướng A, 2026-11-14): ép renderer cairo cho giống
# bản Linux, phải đặt TRƯỚC khi GTK nạp. Linux không đổi gì.
if sys.platform.startswith("win"):
    os.environ.setdefault("GSK_RENDERER", "cairo")
    # Console Windows mac dinh cp1252 — print() tieng Viet se sap
    # UnicodeEncodeError (da thay o engine). Ep stdout/stderr sang UTF-8.
    for _s in (sys.stdout, sys.stderr):
        try: _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception: pass

try:
    import cairo
except Exception:
    cairo = None
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib, Gdk, GObject, Pango

def css_load(provider, data):
    """Nạp CSS vào CssProvider, tương thích MỌI phiên bản PyGObject/GTK4:
    bản mới trên MSYS2 đòi load_from_string hoặc load_from_data(data, length),
    bản trên Linux của Sinh chỉ cần load_from_data(data). (Build Windows 2026-11-14
    gãy ở apply_theme vì lỗi này — 12 chỗ gọi được gom về đây hết.)"""
    if isinstance(data, str):
        data = data.encode()
    try:
        provider.load_from_string(data.decode())
        return
    except Exception:
        pass
    try:
        provider.load_from_data(data)
    except TypeError:
        provider.load_from_data(data, len(data))

def _kids(w):
    """Danh sách widget con của một container — đi bằng get_first_child /
    get_next_sibling (API GTK4 gốc, chạy MỌI phiên bản PyGObject). Không lặp
    trực tiếp trên Gtk.Box: bản PyGObject trên Linux của Sinh lặp được, bản
    MSYS2 thì báo 'Box object is not iterable' (đã gãy build Windows)."""
    out = []
    c = w.get_first_child()
    while c is not None:
        out.append(c)
        c = c.get_next_sibling()
    return out

VERSION = "1.6.4"   # khớp với bản phát hành trên GitHub (server.py + .iss + README)
API = "http://127.0.0.1:8790"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TODAY = date.today().isoformat()   # ngày hôm nay dạng ISO, tính lúc mở app
IS_WIN = sys.platform.startswith("win")
FROZEN = getattr(sys, "frozen", False)
_ENV_DATA = os.environ.get("SHINI_TASKS_DATA", "").strip()
if _ENV_DATA:
    # Bản đóng gói (.deb): code ở /usr/share chỉ đọc — settings theo
    # SHINI_TASKS_DATA, CHUNG thư mục với engine (gói D audit 2026-11-17).
    os.makedirs(_ENV_DATA, exist_ok=True)
    SETTINGS_PATH = os.path.join(_ENV_DATA, "settings.json")
elif IS_WIN and FROZEN:
    # Thư mục cài đặt (Program Files) chỉ đọc -> settings nằm ở %APPDATA%,
    # CHUNG thư mục dữ liệu với engine (server.py _data_dir) để đồng bộ 2 máy
    # qua thư mục đó sau này nếu cần.
    _DATA_DIR = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "Shini Tasks")
    os.makedirs(_DATA_DIR, exist_ok=True)
    SETTINGS_PATH = os.path.join(_DATA_DIR, "settings.json")
else:
    SETTINGS_PATH = os.path.join(BASE_DIR, "settings.json")

DEFAULT_LABELS = {"L1": "Làm ngay", "L2": "Quan trọng", "L3": "Gấp", "L4": "Thường"}
LEVEL_COLORS = {"L1": "#F87171", "L2": "#A78BFA", "L3": "#FB923C", "L4": "#737373"}
PALETTE = ["#F87171", "#FB923C", "#FACC15", "#34D399", "#60A5FA", "#A78BFA", "#F472B6", "#E5E5E5"]

def load_settings():
    s = {"labels": dict(DEFAULT_LABELS), "theme": "dark", "sections": {}, "sidebar": True}
    try:
        with open(SETTINGS_PATH, encoding="utf-8") as f:
            d = json.load(f)
        # Giữ MỌI khóa đã lưu (peer_url, peer_token, gemini_key,
        # display_name, welcomed...) — bản cũ chỉ nạp 4 khóa cố định nên
        # các cài đặt kia MẤT khỏi bộ nhớ sau mỗi lần mở lại app (lỗi
        # tiềm ẩn phát hiện ở gói B audit 2026-11-17).
        for k, v in d.items():
            if k != "labels": s[k] = v
        s["labels"].update(d.get("labels") or {})
        if d.get("theme") in ("dark", "light"): s["theme"] = d["theme"]
        if isinstance(d.get("sections"), dict): s["sections"] = d["sections"]
        if isinstance(d.get("sidebar"), bool): s["sidebar"] = d["sidebar"]
    except Exception: pass
    return s

def save_settings(s):
    try:
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(s, f, ensure_ascii=False, indent=1)
    except Exception as e: print("save settings error:", e)

SETTINGS = load_settings()
if os.environ.get("SHINI_TASKS_THEME") in ("dark", "light"):
    SETTINGS["theme"] = os.environ["SHINI_TASKS_THEME"]

def _read_api_token():
    """Token API của engine CÙNG máy (audit 2026-11-17 mục A1): env
    SHINI_TASKS_TOKEN ghi đè; không thì file api-token.txt trong thư mục
    dữ liệu chung với engine (server.py tự sinh file này)."""
    env_tok = os.environ.get("SHINI_TASKS_TOKEN", "").strip()
    if env_tok: return env_tok
    d = _ENV_DATA or (_DATA_DIR if (IS_WIN and FROZEN) else BASE_DIR)
    try:
        return open(os.path.join(d, "api-token.txt"), encoding="utf-8").read().strip()
    except Exception:
        return ""

API_TOKEN = _read_api_token()

def level_of(t):
    if t["important"] and t["urgent"]: return "L1"
    if t["important"]: return "L2"
    if t["urgent"]: return "L3"
    return "L4"

DARK_CSS = """
window { background: #000000; color: #F5F5F5; }
headerbar { background: #0A0A0A; color: #F5F5F5; }
.sidebar { background: #050505; border-right: 1px solid #232323; }
.brand { font-size: 19px; font-weight: 800; color: #EDEDED; }
.brandsub { color: #A3A3A3; font-size: 12px; }
.sb-h { color: #9A9A9A; font-size: 11px; font-weight: 800; letter-spacing: 1.4px; margin-top: 8px; }
.sb-row { padding: 5px 2px; font-size: 13.5px; }
.sb-num { font-weight: 800; }
.dot { border-radius: 999px; min-width: 9px; min-height: 9px; }
.sb-note { color: #9A9A9A; font-size: 11.5px; }
progressbar > trough { min-height: 8px; border-radius: 999px; background: #1F1F1F; }
progressbar > trough > progress { min-height: 8px; border-radius: 999px; background: #E5E5E5; }
.cal-h { font-size: 12.5px; font-weight: 800; }
.cal-dow { color: #9A9A9A; font-size: 10.5px; font-weight: 700; }
button.cal-day { min-width: 26px; min-height: 26px; padding: 0; border: none; box-shadow: none; border-radius: 999px; font-size: 11.5px; background: transparent; color: #F5F5F5; }
.cal-num { font-size: 11.5px; font-weight: 700; color: #F5F5F5; }
button.cal-today .cal-num { color: #000000; }
button.cal-day:hover { background: #1F1F1F; }
button.cal-today { background: #E5E5E5; color: #000000; font-weight: 800; }
button.cal-sel { border: 2px solid #E5E5E5; }
.bar-day { color: #9A9A9A; font-size: 10px; }
.bar-n { font-size: 10.5px; font-weight: 800; }
.mut { color: #A3A3A3; font-size: 12.5px; }
.toolbar { background: #0A0A0A; border: 1px solid #232323; border-radius: 14px; padding: 8px 10px; }
.col { background: #0A0A0A; border: 1px solid #232323; border-radius: 16px; }
.colhead { padding: 12px 13px 10px; }
.colname { font-weight: 800; font-size: 13.5px; letter-spacing: .6px; }
.colcnt { border-radius: 999px; padding: 1px 9px; font-weight: 800; font-size: 12.5px; }
.coldot { border-radius: 999px; min-width: 10px; min-height: 10px; }
.card { background: #141414; border: 1px solid #2A2A2A; border-radius: 14px; padding: 11px 12px;
  box-shadow: 0 3px 10px rgba(0,0,0,0.45); }
.card:hover { border-color: #404040; background: #171717; }
.card.doing { border-color: rgba(251,146,60,.55); }
.card.done { opacity: 0.5; }
.cardtitle { font-size: 15px; font-weight: 700; }
.cardmeta { font-size: 12px; color: #A3A3A3; }
.chip { border-radius: 999px; padding: 2px 9px; font-size: 11px; font-weight: 800; }
.chip.L1 { background: rgba(248,113,113,.20); color: #FCA5A5; }
.chip.L2 { background: rgba(167,139,250,.20); color: #C4B5FD; }
.chip.L3 { background: rgba(251,146,60,.18); color: #FDBA74; }
.chip.L4 { background: rgba(255,255,255,.10); color: #D4D4D4; }
.tagchip { border-radius: 999px; padding: 1px 8px; font-size: 11px; color: #D4D4D4;
  background: rgba(255,255,255,.06); border: 1px solid rgba(255,255,255,.18); }
.due { font-size: 12px; font-weight: 700; color: #A3A3A3; }
.due.over { color: #FCA5A5; }
button.mini { min-width: 0; min-height: 0; padding: 3px 7px; border-radius: 8px; font-size: 13px; }
menubutton.mini > button { min-width: 0; min-height: 0; padding: 3px 6px; border-radius: 8px; font-size: 13px; }
button.chk { min-width: 16px; min-height: 16px; padding: 0; border-radius: 999px;
  border: 1.5px solid #525252; background: transparent; color: #FFFFFF; font-size: 10px; }
button.chk:hover { border-color: #34D399; }
button.chk.on { background: #34D399; border-color: #34D399; }
button.subchk { min-width: 13px; min-height: 13px; padding: 0; border-radius: 999px;
  border: 1.25px solid #525252; background: transparent; color: #FFFFFF; font-size: 8px; }
button.subchk:hover { border-color: #34D399; }
button.subchk.on { background: #34D399; border-color: #34D399; }
.subtask { color: #D6D6D6; font-size: 13px; }
button.starbtn { font-size: 17px; padding: 0 3px; background: transparent; border: none; box-shadow: none; color: #6E7B8F; }
button.starbtn.on { color: #FBBF24; }
.panebackdrop { background: rgba(4, 6, 12, 0.55); }
.panecard { background: #1F232E; border: 1px solid #3A4152; border-radius: 16px; overflow: hidden; }
popover listview > row { color: #EDEDED; }
popover listview > row label { color: #EDEDED; }
popover listview > row:selected { background: rgba(76, 141, 255, 0.30); color: #FFFFFF; }
popover listview > row:selected label { color: #FFFFFF; }
popover listbox > row { color: #EDEDED; }
popover listbox > row label { color: #EDEDED; }
popover listbox > row:selected { background: rgba(76, 141, 255, 0.30); color: #FFFFFF; }
popover listbox > row:selected label { color: #FFFFFF; }
.subtask-done { color: #8A8A8A; font-size: 13px; }
.empty { color: #9A9A9A; font-size: 12.5px; padding: 18px 6px; }
.coladd { border-top: 1px solid #232323; padding: 8px 10px; }
button.addbtn { background: #E5E5E5; color: #000000; border: none; border-radius: 10px; min-width: 34px; }
button.addbtn > label { color: #000000; }
button.addbtn:hover { background: #FFFFFF; }
.coladd entry { font-size: 13px; padding: 6px 9px; border-radius: 10px; }
button.addcol { border: 1.5px dashed #3A3A3A; border-radius: 16px; background: transparent; color: #A3A3A3; }
button.addcol:hover { border-color: #737373; color: #F5F5F5; background: rgba(255,255,255,0.03); }
entry, dropdown, searchentry { background: #111111; color: #F5F5F5; }
.quickentry { font-size: 15px; padding: 10px 12px; border-radius: 12px; }
textview.quickentry { background: #111111; color: #F5F5F5; caret-color: #F5F5F5; }
textview.quickentry text { background: #111111; color: #F5F5F5; }
button.suggested-action { background: #E5E5E5; color: #000000; }
button.suggested-action > label { color: #000000; }
button.suggested-action:hover { background: #FFFFFF; }
button.suggested-action:backdrop { background: #D4D4D4; color: #000000; }
button.suggested-action:backdrop > label { color: #000000; }
button.suggested-action:disabled { background: #262626; color: #B5B5B5; border: 1px solid #3A3A3A; }
button.suggested-action:disabled > label { color: #B5B5B5; }
button.suggested-action:disabled:backdrop { background: #262626; color: #9A9A9A; }
button.suggested-action:disabled:backdrop > label { color: #9A9A9A; }
button.destructive-action { background: #7F1D1D; color: #FECACA; }
.errlab { color: #F87171; font-weight: 700; font-size: 13px; }
button.viewbtn { border-radius: 10px; padding: 6px 14px; font-weight: 700; }
button.viewbtn-on { background: #E5E5E5; color: #000000; }
button.viewbtn-on > label { color: #000000; }
.calgrid { background: #050505; }
.slot { background: transparent; border-radius: 0; border-left-style: none; border-right-style: none;
  border-bottom-style: none; border-top: 1px solid #161616; box-shadow: none; min-height: 24px; padding: 0; }
.slot:hover { background: rgba(255,255,255,0.05); }
.slothour { border-top: 1px solid #2A2A2A; }
.gutter { color: #9A9A9A; font-size: 10.5px; }
.dayhead { font-weight: 800; font-size: 13px; padding: 8px 4px; color: #F5F5F5; }
.dayhead-today { color: #F87171; }
button.caltask { border-radius: 8px; padding: 3px 7px; font-size: 11.5px; font-weight: 700;
  border-style: none; box-shadow: none; }
.nowline { background: #EF4444; min-height: 2px; }
button.unsched { border-radius: 999px; padding: 4px 12px; font-size: 12.5px; font-weight: 700;
  background: rgba(255,255,255,.07); border: 1px dashed #525252; color: #E5E5E5; }
button.unsched > label { color: #E5E5E5; }
/* ===== V6: lớp hoàn thiện theo Apple Reminders / Google Calendar / Notion ===== */
button.viewbtn-on { background: #2563EB; color: #FFFFFF; }
button.viewbtn-on > label { color: #FFFFFF; }
button.smartrow { border-radius: 10px; padding: 7px 10px; background: transparent; box-shadow: none; border-style: none; }
button.smartrow:hover { background: rgba(255,255,255,0.05); }
button.smartrow-on { background: rgba(255,255,255,0.10); }
.smartico { border-radius: 8px; min-width: 26px; min-height: 26px; color: #FFFFFF; font-size: 13px; }
.smartlab { font-size: 13.5px; font-weight: 600; color: #F5F5F5; }
.smartnum { font-weight: 800; color: #A3A3A3; }
button.colrow { border-radius: 10px; padding: 6px 10px; background: transparent; box-shadow: none; border-style: none; }
button.colrow:hover { background: rgba(255,255,255,0.05); }
button.colrow-on { background: rgba(255,255,255,0.10); }
.card { padding: 13px 14px; }
.card .actions { opacity: 0; }
.card:hover .actions { opacity: 1; }
.duechip { border-radius: 999px; padding: 2px 9px; font-size: 11.5px; font-weight: 700;
  background: rgba(255,255,255,.08); color: #D4D4D4; }
.duechip-today { background: rgba(251,146,60,.20); color: #FDBA74; }
.duechip-over { background: rgba(248,113,113,.22); color: #FCA5A5; }
.preview { color: #93C5FD; font-size: 12.5px; }
.herotile { background: rgba(248,113,113,.18); border-radius: 12px; min-width: 42px; min-height: 42px;
  font-size: 19px; color: #FCA5A5; }
.daynum { font-size: 17px; font-weight: 800; color: #F5F5F5; }
expander > title { padding: 3px 2px; border-radius: 8px; }
expander > title:hover { background: rgba(255,255,255,0.05); }
button label { color: inherit; }
.hdrbtn { color: #F5F5F5; }
.hdrbtn > label { color: #F5F5F5; }
dropdown > button { color: #F5F5F5; background: #111111; }
dropdown > button label { color: #F5F5F5; }
button.dlgbtn { background: #141414; color: #F5F5F5; border: 1px solid #3A3A3A; border-radius: 10px; }
button.dlgbtn > label { color: #F5F5F5; }
button.dlgbtn:checked { background: #F5F5F5; color: #000000; }
button.dlgbtn:checked > label { color: #000000; }
button.dlgflat { color: #D4D4D4; }
button.dlgflat > label { color: #D4D4D4; }
button.dlgflat:hover { background: rgba(255,255,255,.08); }
menubutton.dlgbtn > button { background: #141414; color: #F5F5F5; border: 1px solid #3A3A3A; border-radius: 10px; }
menubutton.dlgbtn > button label { color: #F5F5F5; }
calendar.calpick { background: #141414; color: #F5F5F5; border-radius: 12px; }
calendar.calpick header { background: transparent; }
calendar.calpick label { color: #F5F5F5; }
calendar.calpick header button { color: #F5F5F5; }
spinbutton.timepick { background: #111111; color: #F5F5F5; border: 1px solid #3A3A3A; border-radius: 8px; min-height: 34px; }
spinbutton.timepick > text { color: #F5F5F5; background: transparent; }
spinbutton.timepick button { color: #F5F5F5; }
.timelab { color: #F5F5F5; font-weight: 700; }
button.viewbtn:not(.viewbtn-on) { background: rgba(255,255,255,0.07); color: #F5F5F5; }
button.viewbtn:not(.viewbtn-on) > label { color: #F5F5F5; }
button.toggle:not(.viewbtn-on) { color: #F5F5F5; }
.renamebtn, .renamebtn > label { color: #9A9A9A; }
menubutton.menubtn > button { background: rgba(255,255,255,.07); color: #F5F5F5; border: none; box-shadow: none; }
menubutton.menubtn > button:hover { background: rgba(255,255,255,.13); }
menubutton.menubtn > button label { color: #F5F5F5; }
popover { background: #141414; color: #F5F5F5; }
popover > contents { background: #141414; color: #F5F5F5; }
popover > arrow { background: #141414; }
popover listview { background: transparent; }
popover listview row { background: transparent; }
popover modelbutton { color: #F5F5F5; }
popover modelbutton > label { color: #F5F5F5; }
/* ===== VS CODE DARK (Sinh 2026-11-10 01:32: 'theme như VS Code — nền tối đen,
   chữ sáng có nhiều màu') — lớp phủ CUỐI của DARK_CSS: các rule dưới đây thắng
   các rule cùng selector ở trên theo thứ tự cascade. Bảng màu VS Code Dark+:
   nền #1E1E1E, panel #252526, thẻ #2D2D30, ô nhập #3C3C3C, nút phụ #3A3D41,
   nút chính #0E639C, chọn đang active #04395E, chữ #D4D4D4, chữ mờ #9D9D9D,
   xanh #569CD6, xanh nhạt #9CDCFE, tím #C586C0, cam #CE9178,
   xanh lá #B5CEA8 / #89D185, đỏ #F48771. ===== */
window { background: #1E1E1E; color: #D4D4D4; }
headerbar { background: #252526; color: #CCCCCC; }
.sidebar { background: #252526; border-right: 1px solid #2B2B2B; }
.toolbar { background: #252526; border: 1px solid #2D2D2D; }
.col { background: #252526; border: 1px solid #2D2D2D; }
.card { background: #2D2D30; border: 1px solid #3E3E42; box-shadow: 0 3px 10px rgba(0,0,0,0.35); }
.card:hover { border-color: #4E4E52; background: #323237; }
.mut { color: #9D9D9D; }
.brandsub { color: #9D9D9D; }
.sb-h { color: #9D9D9D; }
.sb-note { color: #9D9D9D; }
.cardmeta { color: #9D9D9D; }
.subtask { color: #D4D4D4; }
.subtask-done { color: #9D9D9D; }
.empty { color: #9D9D9D; }
.gutter { color: #9D9D9D; }
.cal-dow { color: #9D9D9D; }
.bar-day { color: #9D9D9D; }
.due { color: #9D9D9D; }
.due.over { color: #F48771; }
.smartlab { color: #D4D4D4; }
.smartnum { color: #9CDCFE; }
.preview { color: #569CD6; }
.hdrbtn { color: #CCCCCC; }
.hdrbtn > label { color: #CCCCCC; }
.renamebtn, .renamebtn > label { color: #9D9D9D; }
progressbar > trough { background: #3E3E42; }
progressbar > trough > progress { background: #007ACC; }
entry, dropdown, searchentry { background: #3C3C3C; color: #F0F0F0; }
dropdown > button { background: #3C3C3C; color: #F0F0F0; }
dropdown > button label { color: #F0F0F0; }
textview.quickentry { background: #252526; color: #D4D4D4; caret-color: #D4D4D4; }
textview.quickentry text { background: #252526; color: #D4D4D4; }
button.suggested-action { background: #0E639C; color: #FFFFFF; border: none; }
button.suggested-action > label { color: #FFFFFF; }
button.suggested-action:hover { background: #1177BB; }
button.suggested-action:backdrop { background: #0B4F7C; color: #FFFFFF; }
button.suggested-action:backdrop > label { color: #FFFFFF; }
button.suggested-action:disabled { background: #2D2D2D; color: #8B8B8B; border: 1px solid #3E3E42; }
button.suggested-action:disabled > label { color: #8B8B8B; }
button.suggested-action:disabled:backdrop { background: #2D2D2D; color: #8B8B8B; }
button.suggested-action:disabled:backdrop > label { color: #8B8B8B; }
button.addbtn { background: #3A3D41; color: #CCCCCC; border: none; }
button.addbtn > label { color: #CCCCCC; }
button.addbtn:hover { background: #45494E; }
button.dlgbtn { background: #3A3D41; color: #D4D4D4; border: 1px solid #3A3D41; }
button.dlgbtn > label { color: #D4D4D4; }
button.dlgbtn:checked { background: #0E639C; color: #FFFFFF; }
button.dlgbtn:checked > label { color: #FFFFFF; }
menubutton.dlgbtn > button { background: #3C3C3C; color: #F0F0F0; border: 1px solid #3C3C3C; }
menubutton.dlgbtn > button label { color: #F0F0F0; }
button.dlgflat { color: #9CDCFE; }
button.dlgflat > label { color: #9CDCFE; }
button.dlgflat:hover { background: rgba(255,255,255,.07); }
button.viewbtn-on { background: #0E639C; color: #FFFFFF; }
button.viewbtn-on > label { color: #FFFFFF; }
button.viewbtn:not(.viewbtn-on) { background: #3A3D41; color: #D4D4D4; }
button.viewbtn:not(.viewbtn-on) > label { color: #D4D4D4; }
button.toggle:not(.viewbtn-on) { color: #D4D4D4; }
menubutton.menubtn > button { background: #3A3D41; color: #D4D4D4; }
menubutton.menubtn > button:hover { background: #45494E; }
menubutton.menubtn > button label { color: #D4D4D4; }
button.addcol { border-color: #454545; color: #9D9D9D; }
button.addcol:hover { border-color: #007FD4; color: #FFFFFF; background: rgba(0,122,204,0.08); }
button.cal-day:hover { background: #2A2D2E; }
button.cal-today { background: #0E639C; color: #FFFFFF; }
button.cal-today .cal-num { color: #FFFFFF; }
button.cal-sel { border: 2px solid #007FD4; }
button.smartrow-on { background: #04395E; }
button.colrow-on { background: #04395E; }
button.chk { border-color: #6B6B6B; }
button.chk:hover { border-color: #89D185; }
button.chk.on { background: #89D185; border-color: #89D185; color: #14301B; }
button.subchk { border-color: #6B6B6B; }
button.subchk:hover { border-color: #89D185; }
button.subchk.on { background: #89D185; border-color: #89D185; color: #14301B; }
.chip.L1 { background: rgba(244,71,71,.20); color: #F48771; }
.chip.L2 { background: rgba(197,134,192,.20); color: #C586C0; }
.chip.L3 { background: rgba(206,145,120,.22); color: #CE9178; }
.chip.L4 { background: rgba(156,220,254,.14); color: #9CDCFE; }
.tagchip { color: #B5CEA8; background: rgba(181,206,168,.10); border: 1px solid rgba(181,206,168,.35); }
.duechip { background: #3A3D41; color: #D4D4D4; }
.duechip-today { background: rgba(206,145,120,.22); color: #CE9178; }
.duechip-over { background: rgba(244,71,71,.20); color: #F48771; }
.herotile { background: rgba(244,71,71,.16); color: #F48771; }
.errlab { color: #F48771; }
.calgrid { background: #1E1E1E; }
.slot { border-top: 1px solid #2B2B2B; }
.slot:hover { background: rgba(255,255,255,0.04); }
.slothour { border-top: 1px solid #3E3E42; }
.dayhead { color: #D4D4D4; }
.dayhead-today { color: #F48771; }
.daynum { color: #D4D4D4; }
.nowline { background: #F44747; }
button.unsched { background: rgba(255,255,255,.06); border: 1px dashed #6B6B6B; color: #D4D4D4; }
button.unsched > label { color: #D4D4D4; }
popover { background: #252526; color: #D4D4D4; }
popover > contents { background: #252526; color: #D4D4D4; }
popover > arrow { background: #252526; }
popover modelbutton { color: #D4D4D4; }
popover modelbutton > label { color: #D4D4D4; }
calendar.calpick { background: #252526; color: #D4D4D4; }
calendar.calpick label { color: #D4D4D4; }
calendar.calpick header button { color: #D4D4D4; }
spinbutton.timepick { background: #3C3C3C; color: #F0F0F0; border: 1px solid #3C3C3C; }
spinbutton.timepick > text { color: #F0F0F0; }
spinbutton.timepick button { color: #F0F0F0; }
.timelab { color: #D4D4D4; }
/* ===== TĂNG SÁNG TOÀN BỘ CHỮ (Sinh 2026-11-10 01:34, sau khi xem bản VS Code
   trên máy thật: 'tất cả chữ luôn — chữ đen này không nhìn bị khó quá'). Tông mờ
   kiểu VS Code gốc (#9D9D9D) lên màn hình của Sinh bị chìm; nâng toàn bộ thang
   chữ lên một bậc: chữ chính #EDEDED, chữ phụ #C8C8C8, placeholder #CFCFCF. ===== */
window { color: #EDEDED; }
.mut { color: #C8C8C8; }
.brandsub { color: #C8C8C8; }
.sb-h { color: #C8C8C8; }
.sb-note { color: #C8C8C8; }
.cardmeta { color: #C8C8C8; }
.subtask { color: #EDEDED; }
.subtask-done { color: #B5B5B5; }
.empty { color: #C8C8C8; }
.gutter { color: #C8C8C8; }
.cal-dow { color: #C8C8C8; }
.bar-day { color: #C8C8C8; }
.due { color: #C8C8C8; }
.smartlab { color: #EDEDED; }
.hdrbtn { color: #E8E8E8; }
.hdrbtn > label { color: #E8E8E8; }
.renamebtn, .renamebtn > label { color: #C8C8C8; }
.dayhead { color: #EDEDED; }
.daynum { color: #EDEDED; }
.preview { color: #7FB8EC; }
button.dlgbtn { color: #EDEDED; }
button.dlgbtn > label { color: #EDEDED; }
menubutton.menubtn > button { color: #EDEDED; }
menubutton.menubtn > button label { color: #EDEDED; }
button.viewbtn:not(.viewbtn-on) { color: #EDEDED; }
button.viewbtn:not(.viewbtn-on) > label { color: #EDEDED; }
button.toggle:not(.viewbtn-on) { color: #EDEDED; }
button.addcol { color: #C8C8C8; }
.duechip { color: #F0F0F0; }
.duechip-today { color: #E8B08F; }
.chip.L3 { color: #E8B08F; }
.chip.L2 { color: #D3A6CE; }
button.unsched { color: #EDEDED; }
button.unsched > label { color: #EDEDED; }
textview.quickentry { color: #EDEDED; caret-color: #EDEDED; }
textview.quickentry text { color: #EDEDED; }
popover { color: #EDEDED; }
popover > contents { color: #EDEDED; }
popover modelbutton { color: #EDEDED; }
popover modelbutton > label { color: #EDEDED; }
calendar.calpick { color: #EDEDED; }
calendar.calpick label { color: #EDEDED; }
calendar.calpick header button { color: #EDEDED; }
entry > text > placeholder { color: #CFCFCF; }
searchentry > text > placeholder { color: #CFCFCF; }
/* ===== CHỈNH THEO VS CODE TRÊN MÁY SINH (2026-11-10 01:36 — Sinh gửi ảnh chụp
   VS Code thật của mình: 'ở nền đen tôi muốn hiển thị như này nè'). Khác bản
   Dark+ gốc ở 3 điểm: (1) nền là ĐEN XANH (blue-black) đậm hơn #1E1E1E, panel
   chỉ sáng hơn nền một bậc, viền slate mảnh; (2) ô nhập/nút phụ cũng slate xanh
   thay vì xám trung tính; (3) màu chữ ký của theme đó: hồng keyword #FF8FA8 cho
   tiêu đề mục, cam số #F78C6C cho các con số, vùng chọn active xanh slate. ===== */
window { background: #191C24; }
headerbar { background: #1F232E; }
.sidebar { background: #1F232E; border-right: 1px solid #2E3442; }
.toolbar { background: #1F232E; border: 1px solid #2E3442; }
.col { background: #1F232E; border: 1px solid #2E3442; }
.card { background: #262B36; border: 1px solid #333A48; }
.card:hover { background: #2B303D; border-color: #3D4457; }
.calgrid { background: #191C24; }
.slot { border-top: 1px solid #232833; }
.slothour { border-top: 1px solid #333A48; }
entry, dropdown, searchentry { background: #2C3242; }
dropdown > button { background: #2C3242; }
spinbutton.timepick { background: #2C3242; border: 1px solid #2C3242; }
textview.quickentry { background: #21252F; }
textview.quickentry text { background: #21252F; }
button.dlgbtn { background: #343B4D; border: 1px solid #343B4D; }
menubutton.dlgbtn > button { background: #2C3242; border: 1px solid #2C3242; }
menubutton.menubtn > button { background: #343B4D; }
menubutton.menubtn > button:hover { background: #3E465C; }
button.viewbtn:not(.viewbtn-on) { background: #343B4D; }
button.addbtn { background: #343B4D; }
button.addbtn:hover { background: #3E465C; }
.duechip { background: #343B4D; }
popover { background: #21252F; }
popover > contents { background: #21252F; }
popover > arrow { background: #21252F; }
calendar.calpick { background: #21252F; }
button.smartrow-on { background: #2C3648; }
button.colrow-on { background: #2C3648; }
.sb-h { color: #FF8FA8; }
.smartnum { color: #F78C6C; }
.bar-n { color: #F78C6C; }
/* ===== CHỮ TRONG THẺ CŨNG CÓ MÀU (Sinh 2026-11-10 01:38, chụp cận cảnh 1 thẻ:
   'các chữ trong ô này cũng hiển thị màu luôn') — tô màu theo VAI TRÒ như code:
   tiêu đề = xanh lá (tên hàm) #A9DC76, việc con = xanh nhạt (biến) #9CDCFE,
   ghi chú + dòng meta = vàng nhạt (chuỗi) #E6DB74, chip đếm ☑ n/m = cam (số)
   #F78C6C. Chỉ áp cho DARK_CSS — bản sáng giữ chữ đen theo quy tắc của Sinh. ===== */
.cardtitle { color: #A9DC76; }
.subtask { color: #9CDCFE; }
.subtask-done { color: #7E8CA3; }
.cardmeta { color: #E6DB74; }
.tagchip.cntchip { color: #F78C6C; background: rgba(247,140,108,.12); border: 1px solid rgba(247,140,108,.35); }
/* ===== CHỐT LẠI THEO ẢNH VS CODE CỦA SINH (2026-11-10 01:41 — bản cầu vồng
   từng ký tự bị chê 'gớm quá'; Sinh gửi lại ảnh code: 'tôi muốn như VS Code
   như này nè'). Nguyên tắc trong ảnh: PHẦN LỚN chữ là trắng/xanh rất nhạt,
   màu chỉ dành cho điểm nhấn — hồng cho từ khóa/trạng thái, cam cho con số,
   xanh ngọc cho nhãn đặc biệt. Các rule dưới đây thắng lớp tô theo vai trò
   ngay phía trên: tiêu đề về trắng xanh nhạt (chữ thường trong code), việc
   con xanh nhạt, #tag xanh ngọc; meta đã tô theo từng mẩu bằng markup. ===== */
.cardtitle { color: #E6EDF7; }
.subtask { color: #9CDCFE; }
.chip.L1 { color: #FF8FA8; }
.duechip-over { color: #FF8FA8; }
.tagchip { color: #78DCE8; background: rgba(120,220,232,.10); border: 1px solid rgba(120,220,232,.35); }
.tagchip.cntchip { color: #F78C6C; background: rgba(247,140,108,.12); border: 1px solid rgba(247,140,108,.35); }
/* ===== GÓI NÂNG CẤP 3 GIAI ĐOẠN (2026-11-10 — kéo-thả, trang Hôm nay, tự xếp) ===== */
.col.drop-hover { border: 1px solid #569CD6; box-shadow: inset 0 0 0 1px #569CD6; }
button.slot.drop-hover { background: rgba(86,156,214,.25); }
.calgrip { background: rgba(255,255,255,.28); border-radius: 3px; min-height: 5px; margin: 2px 10px 3px 10px; }
.today-h { font-weight: 700; font-size: 15px; color: #E6EDF7; }
.today-cnt { color: #F78C6C; font-weight: 700; }
.statcard { background: #262B36; border: 1px solid #333A48; border-radius: 14px; padding: 12px 14px; }
.statnum { font-size: 23px; font-weight: 800; color: #EDEDED; }
/* ===== NÚT 'CHỈ QUÁ HẠN' (Sinh 2026-11-15: bật lọc thì MẤT MÀU CHỮ) =====
   Nút này trước đây KHÔNG có class riêng nên trạng thái :checked/:hover mượn
   style của theme hệ thống Sweet (nền đen + chữ đen -> chữ biến mất). Nay ghim
   cứng mọi trạng thái, cả nhãn con bên trong, theo đúng thang màu của app. */
button.overbtn { background: #343B4D; color: #EDEDED; border: 1px solid #333A48; }
button.overbtn > label { color: #EDEDED; }
button.overbtn:hover { background: #3E465C; }
button.overbtn:checked { background: #0E639C; color: #FFFFFF; border-color: #0E639C; }
button.overbtn:checked > label { color: #FFFFFF; }
button.overbtn:checked:hover { background: #1177BB; }
/* ===== BÌNH LUẬN TRONG HỘP SỬA VIỆC (gói KimesFlow, 2026-11-15) ===== */
.cmtau { font-weight: 700; color: #9CDCFE; }
.cmttext { color: #EDEDED; }
/* ===== TAB TRONG HỘP SỬA VIỆC (Sinh 2026-11-16: hộp quá dài) — ghim cứng
   màu tab cả 2 trạng thái, kể cả nhãn con bên trong, không mượn theme Sweet ===== */
notebook.dlgnb > header { background: transparent; border-bottom: 1px solid #333A48; box-shadow: none; }
notebook.dlgnb > header > tabs > tab { padding: 7px 12px; border-radius: 8px 8px 0 0; color: #9AA7BD; }
notebook.dlgnb > header > tabs > tab > label { color: #9AA7BD; }
notebook.dlgnb > header > tabs > tab:checked { background: #262B36; }
notebook.dlgnb > header > tabs > tab:checked > label { color: #FFFFFF; font-weight: 700; }
notebook.dlgnb > stack { background: transparent; }
/* ===== NÚT ⋯ CỦA DÒNG DỰ ÁN Ở SIDEBAR — bản đầu quên ghim màu nên theme sáng
   bị theme Sweet nhuộm thành ô đen chữ đen (ảnh kiểm chứng 2026-11-16) ===== */
menubutton.projmenu > button { background: #343B4D; color: #EDEDED; border: 1px solid #333A48; box-shadow: none; }
menubutton.projmenu > button > label { color: #EDEDED; }
menubutton.projmenu > button:hover { background: #3E465C; }
/* ===== KHUNG CHUẨN v1.5.0 (DARK) — sidebar điều hướng thuần + tab view +
   panel chi tiết phải. Mọi màu ghim cứng, không mượn theme Sweet. ===== */
button.sb2add { background: #262B36; color: #EDEDED; border: 1px solid #333A48; border-radius: 9px; box-shadow: none; padding: 7px 10px; }
button.sb2add > label { color: #EDEDED; }
button.sb2add:hover { background: #2E3547; }
entry.sb2search { background: #262B36; color: #EDEDED; border: 1px solid #333A48; border-radius: 9px; }
entry.sb2search image { color: #9AA7BD; }
button.sb2row { background: transparent; border: none; box-shadow: none; border-radius: 8px; padding: 6px 9px; }
button.sb2row label { color: #C8C8C8; }
button.sb2row:hover { background: #262B36; }
button.sb2row-on { background: #2E3A55; }
button.sb2row-on label { color: #FFFFFF; font-weight: 600; }
.sb2foot { border-top: 1px solid #2E3442; padding-top: 8px; margin-top: 8px; }
.vh-title { font-size: 20px; font-weight: 800; color: #EDEDED; }
.tabrow { border-bottom: 1px solid #2E3442; }
button.viewtab { background: transparent; border: none; box-shadow: none; border-radius: 0; padding: 7px 10px; color: #9AA7BD; }
button.viewtab > label { color: #9AA7BD; }
button.viewtab:hover > label { color: #EDEDED; }
button.viewtab-on { box-shadow: inset 0 -2px 0 #4C8DFF; }
button.viewtab-on > label { color: #FFFFFF; font-weight: 700; }
.flagchip { font-size: 11px; font-weight: 700; }
.flagchip.L1 { color: #F87171; } .flagchip.L2 { color: #FB923C; } .flagchip.L3 { color: #FACC15; }
.card.sel { border-color: #4C8DFF; box-shadow: 0 0 0 1px #4C8DFF; }
.pane { background: #1F232E; }
.pane-h { font-size: 11px; font-weight: 800; letter-spacing: 1.4px; color: #9AA7BD; margin-top: 6px; }
.pfield-k { font-size: 13px; color: #9AA7BD; }
entry.panetitle { font-size: 16px; font-weight: 700; background: #262B36; color: #EDEDED; border: 1px solid #333A48; border-radius: 9px; padding: 7px 10px; }
textview.panenotes { background: #262B36; color: #EDEDED; }
textview.panenotes text { background: #262B36; color: #EDEDED; }
.pane frame { background: #262B36; border: 1px solid #333A48; border-radius: 9px; }
.lrow { padding: 5px 8px; border-radius: 10px; }
.lrow.sel { background: #232A3D; box-shadow: inset 0 0 0 1px #4C8DFF; }
.lhead { font-size: 12px; font-weight: 700; letter-spacing: .5px; color: #C8C8C8; margin-top: 12px; }
.subtask { color: #D6D6D6; font-size: 13px; }
.subtask-done { color: #9A9A9A; font-size: 13px; }
/* Viền focus khi điều hướng bằng BÀN PHÍM (gói C audit 2026-11-17) */
button:focus-visible, entry:focus-visible, searchentry:focus-visible,
dropdown:focus-visible, spinbutton:focus-visible, textview:focus-visible {
  outline-color: #4C8DFF; outline-style: solid; outline-width: 2px; outline-offset: 1px; }
"""

LIGHT_CSS = """
window { background: #F4F4F2; color: #171717; }
headerbar { background: #ECECEA; color: #171717; }
.sidebar { background: #ECECEA; border-right: 1px solid #D9D9D6; }
.brand { font-size: 19px; font-weight: 800; color: #171717; }
.brandsub { color: #59636E; font-size: 12px; }
.sb-h { color: #59636E; font-size: 11px; font-weight: 800; letter-spacing: 1.4px; margin-top: 8px; }
.sb-row { padding: 5px 2px; font-size: 13.5px; }
.sb-num { font-weight: 800; }
.dot { border-radius: 999px; min-width: 9px; min-height: 9px; }
.sb-note { color: #59636E; font-size: 11.5px; }
progressbar > trough { min-height: 8px; border-radius: 999px; background: #D9D9D6; }
progressbar > trough > progress { min-height: 8px; border-radius: 999px; background: #171717; }
.cal-h { font-size: 12.5px; font-weight: 800; }
.cal-dow { color: #59636E; font-size: 10.5px; font-weight: 700; }
button.cal-day { min-width: 26px; min-height: 26px; padding: 0; border: none; box-shadow: none; border-radius: 999px; font-size: 11.5px; background: transparent; color: #171717; }
.cal-num { font-size: 11.5px; font-weight: 700; color: #171717; }
button.cal-today .cal-num { color: #FFFFFF; }
button.cal-day:hover { background: #DCDCDC; }
button.cal-today { background: #171717; color: #FFFFFF; font-weight: 800; }
button.cal-sel { border: 2px solid #171717; }
.bar-day { color: #59636E; font-size: 10px; }
.bar-n { font-size: 10.5px; font-weight: 800; }
.mut { color: #59636E; font-size: 12.5px; }
.toolbar { background: #FFFFFF; border: 1px solid #E0E0DC; border-radius: 14px; padding: 8px 10px; }
.col { background: #FFFFFF; border: 1px solid #E0E0DC; border-radius: 16px; }
.colhead { padding: 12px 13px 10px; }
.colname { font-weight: 800; font-size: 13.5px; letter-spacing: .6px; }
.colcnt { border-radius: 999px; padding: 1px 9px; font-weight: 800; font-size: 12.5px; }
.coldot { border-radius: 999px; min-width: 10px; min-height: 10px; }
.card { background: #FFFFFF; border: 1px solid #E2E2DE; border-radius: 14px; padding: 11px 12px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.07); }
.card:hover { border-color: #C9C9C4; background: #FAFAF8; }
.card.doing { border-color: rgba(234,88,12,.55); }
.card.done { opacity: 0.55; }
.cardtitle { font-size: 15px; font-weight: 700; }
.cardmeta { font-size: 12px; color: #6B7280; }
.chip { border-radius: 999px; padding: 2px 9px; font-size: 11px; font-weight: 800; }
.chip.L1 { background: rgba(248,113,113,.22); color: #B91C1C; }
.chip.L2 { background: rgba(167,139,250,.25); color: #6D28D9; }
.chip.L3 { background: rgba(251,146,60,.25); color: #C2410C; }
.chip.L4 { background: rgba(0,0,0,.07); color: #525252; }
.tagchip { border-radius: 999px; padding: 1px 8px; font-size: 11px; color: #404040;
  background: rgba(0,0,0,.045); border: 1px solid rgba(0,0,0,.14); }
.due { font-size: 12px; font-weight: 700; color: #6B7280; }
.due.over { color: #DC2626; }
button.mini { min-width: 0; min-height: 0; padding: 3px 7px; border-radius: 8px; font-size: 13px; }
menubutton.mini > button { min-width: 0; min-height: 0; padding: 3px 6px; border-radius: 8px; font-size: 13px; }
button.chk { min-width: 16px; min-height: 16px; padding: 0; border-radius: 999px;
  border: 1.5px solid #B6B6B0; background: transparent; color: #FFFFFF; font-size: 10px; }
button.chk:hover { border-color: #059669; }
button.chk.on { background: #059669; border-color: #059669; }
button.subchk { min-width: 13px; min-height: 13px; padding: 0; border-radius: 999px;
  border: 1.25px solid #B6B6B0; background: transparent; color: #FFFFFF; font-size: 8px; }
button.subchk:hover { border-color: #059669; }
button.subchk.on { background: #059669; border-color: #059669; }
.subtask { color: #333333; font-size: 13px; }
button.starbtn { font-size: 17px; padding: 0 3px; background: transparent; border: none; box-shadow: none; color: #B6BEC9; }
button.starbtn.on { color: #D97706; }
.panebackdrop { background: rgba(15, 20, 35, 0.45); }
.panecard { background: #FFFFFF; border: 1px solid #D8DEE9; border-radius: 16px; overflow: hidden; }
popover listview > row { color: #171717; }
popover listview > row label { color: #171717; }
popover listview > row:selected { background: rgba(37, 99, 235, 0.14); color: #171717; }
popover listview > row:selected label { color: #171717; }
popover listbox > row { color: #171717; }
popover listbox > row label { color: #171717; }
popover listbox > row:selected { background: rgba(37, 99, 235, 0.14); color: #171717; }
popover listbox > row:selected label { color: #171717; }
.subtask-done { color: #8A8A8A; font-size: 13px; }
.empty { color: #59636E; font-size: 12.5px; padding: 18px 6px; }
.coladd { border-top: 1px solid #E7E7E3; padding: 8px 10px; }
button.addbtn { background: #FFFFFF; color: #171717; border: 1px solid #171717; border-radius: 10px; min-width: 34px; }
button.addbtn > label { color: #171717; }
button.addbtn:hover { background: #F0F0EC; }
.coladd entry { font-size: 13px; padding: 6px 9px; border-radius: 10px; }
button.addcol { border: 1.5px dashed #C4C4BE; border-radius: 16px; background: transparent; color: #6B7280; }
button.addcol:hover { border-color: #9CA3AF; color: #171717; background: rgba(0,0,0,0.03); }
entry, dropdown, searchentry { background: #FFFFFF; color: #171717; }
.quickentry { font-size: 15px; padding: 10px 12px; border-radius: 12px; }
textview.quickentry { background: #FFFFFF; color: #171717; caret-color: #171717; }
textview.quickentry text { background: #FFFFFF; color: #171717; }
button.suggested-action { background: #FFFFFF; color: #171717; border: 1px solid #171717; }
button.suggested-action > label { color: #171717; }
button.suggested-action:hover { background: #F0F0EC; }
button.suggested-action:backdrop { background: #FFFFFF; color: #171717; }
button.suggested-action:backdrop > label { color: #171717; }
button.suggested-action:disabled { background: #E7E7E3; color: #6B7280; border: 1px solid #D9D9D6; }
button.suggested-action:disabled > label { color: #6B7280; }
button.suggested-action:disabled:backdrop { background: #E7E7E3; color: #6B7280; }
button.suggested-action:disabled:backdrop > label { color: #6B7280; }
button.destructive-action { background: #DC2626; color: #FFFFFF; }
.errlab { color: #B91C1C; font-weight: 700; font-size: 13px; }
button.viewbtn { border-radius: 10px; padding: 6px 14px; font-weight: 700; }
button.viewbtn-on { background: #171717; color: #FFFFFF; }
button.viewbtn-on > label { color: #FFFFFF; }
button.viewbtn:not(.viewbtn-on) { background: #FFFFFF; color: #171717; }
button.viewbtn:not(.viewbtn-on) > label { color: #171717; }
.calgrid { background: #FFFFFF; }
.slot { background: transparent; border-radius: 0; border-left-style: none; border-right-style: none;
  border-bottom-style: none; border-top: 1px solid #F0F0EC; box-shadow: none; min-height: 24px; padding: 0; }
.slot:hover { background: rgba(0,0,0,0.04); }
.slothour { border-top: 1px solid #DDDCD6; }
.gutter { color: #6B7280; font-size: 10.5px; }
.dayhead { font-weight: 800; font-size: 13px; padding: 8px 4px; color: #171717; }
.dayhead-today { color: #DC2626; }
button.caltask { border-radius: 8px; padding: 3px 7px; font-size: 11.5px; font-weight: 700;
  border-style: none; box-shadow: none; }
.nowline { background: #EF4444; min-height: 2px; }
button.unsched { border-radius: 999px; padding: 4px 12px; font-size: 12.5px; font-weight: 700;
  background: rgba(0,0,0,.04); border: 1px dashed #A8A8A2; color: #404040; }
button.unsched > label { color: #404040; }
/* ===== V6: lớp hoàn thiện theo Apple Reminders / Google Calendar / Notion ===== */
button.viewbtn-on { background: #1A73E8; color: #FFFFFF; }
button.viewbtn-on > label { color: #FFFFFF; }
button.smartrow { border-radius: 10px; padding: 7px 10px; background: transparent; box-shadow: none; border-style: none; }
button.smartrow:hover { background: rgba(0,0,0,0.045); }
button.smartrow-on { background: rgba(0,0,0,0.075); }
.smartico { border-radius: 8px; min-width: 26px; min-height: 26px; color: #FFFFFF; font-size: 13px; }
.smartlab { font-size: 13.5px; font-weight: 600; color: #171717; }
.smartnum { font-weight: 800; color: #59636E; }
button.colrow { border-radius: 10px; padding: 6px 10px; background: transparent; box-shadow: none; border-style: none; }
button.colrow:hover { background: rgba(0,0,0,0.045); }
button.colrow-on { background: rgba(0,0,0,0.075); }
.card { padding: 13px 14px; }
.card .actions { opacity: 0; }
.card:hover .actions { opacity: 1; }
.duechip { border-radius: 999px; padding: 2px 9px; font-size: 11.5px; font-weight: 700;
  background: rgba(0,0,0,.06); color: #525252; }
.duechip-today { background: rgba(251,146,60,.25); color: #9A3412; }
.duechip-over { background: rgba(248,113,113,.22); color: #B91C1C; }
.preview { color: #1459B4; font-size: 12.5px; }
.herotile { background: rgba(248,113,113,.16); border-radius: 12px; min-width: 42px; min-height: 42px;
  font-size: 19px; color: #DC2626; }
.daynum { font-size: 17px; font-weight: 800; color: #171717; }
expander > title { padding: 3px 2px; border-radius: 8px; }
expander > title:hover { background: rgba(0,0,0,0.045); }
button label { color: inherit; }
.hdrbtn { color: #171717; }
.hdrbtn > label { color: #171717; }
dropdown > button { color: #171717; background: #FFFFFF; }
dropdown > button label { color: #171717; }
button.dlgbtn { background: #FFFFFF; color: #171717; border: 1px solid #D8D8D2; border-radius: 10px; }
button.dlgbtn > label { color: #171717; }
button.dlgbtn:checked { background: #171717; color: #FFFFFF; }
button.dlgbtn:checked > label { color: #FFFFFF; }
button.dlgflat { color: #404040; }
button.dlgflat > label { color: #404040; }
button.dlgflat:hover { background: rgba(0,0,0,.05); }
menubutton.dlgbtn > button { background: #FFFFFF; color: #171717; border: 1px solid #D8D8D2; border-radius: 10px; }
menubutton.dlgbtn > button label { color: #171717; }
calendar.calpick { background: #FFFFFF; color: #171717; border-radius: 12px; }
calendar.calpick header { background: transparent; }
calendar.calpick label { color: #171717; }
calendar.calpick header button { color: #171717; }
spinbutton.timepick { background: #FFFFFF; color: #171717; border: 1px solid #D8D8D2; border-radius: 8px; min-height: 34px; }
spinbutton.timepick > text { color: #171717; background: transparent; }
spinbutton.timepick button { color: #171717; }
.timelab { color: #171717; font-weight: 700; }
button.viewbtn:not(.viewbtn-on) { color: #171717; }
button.toggle:not(.viewbtn-on) { color: #171717; }
.renamebtn, .renamebtn > label { color: #59636E; }
menubutton.menubtn > button { background: rgba(0,0,0,.055); color: #171717; border: none; box-shadow: none; }
menubutton.menubtn > button:hover { background: rgba(0,0,0,.10); }
menubutton.menubtn > button label { color: #171717; }
popover { background: #FFFFFF; color: #171717; }
popover > contents { background: #FFFFFF; color: #171717; }
popover > arrow { background: #FFFFFF; }
popover listview { background: transparent; }
popover listview row { background: transparent; }
popover modelbutton { color: #171717; }
popover modelbutton > label { color: #171717; }
/* ===== GÓI NÂNG CẤP 3 GIAI ĐOẠN (2026-11-10 — kéo-thả, trang Hôm nay, tự xếp) ===== */
.col.drop-hover { border: 1px solid #2563EB; box-shadow: inset 0 0 0 1px #2563EB; }
button.slot.drop-hover { background: rgba(37,99,235,.14); }
.calgrip { background: rgba(0,0,0,.22); border-radius: 3px; min-height: 5px; margin: 2px 10px 3px 10px; }
.today-h { font-weight: 700; font-size: 15px; color: #111111; }
.today-cnt { color: #C2410C; font-weight: 700; }
.statcard { background: #FFFFFF; border: 1px solid #E0E0DC; border-radius: 14px; padding: 12px 14px; }
.statnum { font-size: 23px; font-weight: 800; color: #111111; }
/* ===== NÚT 'CHỈ QUÁ HẠN' (Sinh 2026-11-15: bật lọc thì MẤT MÀU CHỮ) =====
   Như bản tối: ghim cứng mọi trạng thái + nhãn con. Đang bật lọc = nền đen
   chữ trắng (cùng quy ước với nút chọn mức ưu tiên trong hộp sửa việc). */
button.overbtn { background: #FFFFFF; color: #171717; border: 1px solid #D4D4D0; }
button.overbtn > label { color: #171717; }
button.overbtn:hover { background: #F0F0EE; }
button.overbtn:checked { background: #171717; color: #FFFFFF; border-color: #171717; }
button.overbtn:checked > label { color: #FFFFFF; }
button.overbtn:checked:hover { background: #2A2A2A; }
/* ===== BÌNH LUẬN TRONG HỘP SỬA VIỆC (gói KimesFlow, 2026-11-15) ===== */
.cmtau { font-weight: 700; color: #0969DA; }
.cmttext { color: #171717; }
/* ===== TAB TRONG HỘP SỬA VIỆC (Sinh 2026-11-16: hộp quá dài) ===== */
notebook.dlgnb > header { background: transparent; border-bottom: 1px solid #D4D4D0; box-shadow: none; }
notebook.dlgnb > header > tabs > tab { padding: 7px 12px; border-radius: 8px 8px 0 0; color: #59636E; }
notebook.dlgnb > header > tabs > tab > label { color: #59636E; }
notebook.dlgnb > header > tabs > tab:checked { background: #FFFFFF; }
notebook.dlgnb > header > tabs > tab:checked > label { color: #171717; font-weight: 700; }
notebook.dlgnb > stack { background: transparent; }
/* ===== NÚT ⋯ CỦA DÒNG DỰ ÁN Ở SIDEBAR (bản sáng) ===== */
menubutton.projmenu > button { background: #FFFFFF; color: #171717; border: 1px solid #D4D4D0; box-shadow: none; }
menubutton.projmenu > button > label { color: #171717; }
menubutton.projmenu > button:hover { background: #F0F0EE; }
/* ===== KHUNG CHUẨN v1.5.0 (LIGHT) — như bản tối: ghim cứng mọi màu ===== */
button.sb2add { background: #FFFFFF; color: #171717; border: 1px solid #D4D4D0; border-radius: 9px; box-shadow: none; padding: 7px 10px; }
button.sb2add > label { color: #171717; }
button.sb2add:hover { background: #F0F0EE; }
entry.sb2search { background: #FFFFFF; color: #171717; border: 1px solid #D4D4D0; border-radius: 9px; }
entry.sb2search image { color: #59636E; }
button.sb2row { background: transparent; border: none; box-shadow: none; border-radius: 8px; padding: 6px 9px; }
button.sb2row label { color: #3D4756; }
button.sb2row:hover { background: #E4E4E0; }
button.sb2row-on { background: #DCE6F7; }
button.sb2row-on label { color: #171717; font-weight: 600; }
.sb2foot { border-top: 1px solid #D9D9D6; padding-top: 8px; margin-top: 8px; }
.vh-title { font-size: 20px; font-weight: 800; color: #171717; }
.tabrow { border-bottom: 1px solid #D9D9D6; }
button.viewtab { background: transparent; border: none; box-shadow: none; border-radius: 0; padding: 7px 10px; color: #59636E; }
button.viewtab > label { color: #59636E; }
button.viewtab:hover > label { color: #171717; }
button.viewtab-on { box-shadow: inset 0 -2px 0 #2563EB; }
button.viewtab-on > label { color: #171717; font-weight: 700; }
.flagchip { font-size: 11px; font-weight: 700; }
.flagchip.L1 { color: #DC2626; } .flagchip.L2 { color: #EA580C; } .flagchip.L3 { color: #CA8A04; }
.card.sel { border-color: #2563EB; box-shadow: 0 0 0 1px #2563EB; }
.pane { background: #FFFFFF; }
.pane-h { font-size: 11px; font-weight: 800; letter-spacing: 1.4px; color: #59636E; margin-top: 6px; }
.pfield-k { font-size: 13px; color: #59636E; }
entry.panetitle { font-size: 16px; font-weight: 700; background: #FFFFFF; color: #171717; border: 1px solid #D4D4D0; border-radius: 9px; padding: 7px 10px; }
textview.panenotes { background: #FFFFFF; color: #171717; }
textview.panenotes text { background: #FFFFFF; color: #171717; }
.pane frame { background: #FFFFFF; border: 1px solid #D4D4D0; border-radius: 9px; }
.lrow { padding: 5px 8px; border-radius: 10px; }
.lrow.sel { background: #EAF0FC; box-shadow: inset 0 0 0 1px #2563EB; }
.lhead { font-size: 12px; font-weight: 700; letter-spacing: .5px; color: #3D4756; margin-top: 12px; }
.subtask { color: #333333; font-size: 13px; }
.subtask-done { color: #8A8A8A; font-size: 13px; }
/* Viền focus khi điều hướng bằng BÀN PHÍM (gói C audit 2026-11-17) */
button:focus-visible, entry:focus-visible, searchentry:focus-visible,
dropdown:focus-visible, spinbutton:focus-visible, textview:focus-visible {
  outline-color: #2563EB; outline-style: solid; outline-width: 2px; outline-offset: 1px; }
"""

def api(method, path, body=None, _retry=True):
    global API_TOKEN
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if API_TOKEN: headers["X-Token"] = API_TOKEN
    req = urllib.request.Request(API + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=4) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        # 403: token có thể vừa được engine sinh mới (lần chạy đầu) hoặc
        # vừa đổi — đọc lại file token và thử đúng MỘT lần nữa.
        if e.code == 403 and _retry:
            API_TOKEN = _read_api_token()
            return api(method, path, body, _retry=False)
        raise

def api_raw(path):
    """Tải dữ liệu nhị phân (file đính kèm) — api() chỉ đọc JSON nên cần hàm riêng."""
    headers = {"X-Token": API_TOKEN} if API_TOKEN else {}
    req = urllib.request.Request(API + path, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read()

def today_(): return date.today()
def this_sunday():
    t = today_(); return t + timedelta(days=6 - t.weekday())

def is_overdue(t):
    if not t.get("due_date") or t["status"] == "done": return False
    d = date.fromisoformat(t["due_date"])
    if d < today_(): return True
    if d == today_() and t.get("due_time"):
        return t["due_time"] < datetime.now().strftime("%H:%M")
    return False

def fmt_due(t):
    if not t.get("due_date"): return "Chưa đặt hạn"
    d = date.fromisoformat(t["due_date"]); diff = (d - today_()).days
    lbl = (f"Quá hạn {-diff} ngày" if diff < 0 else "Hôm nay" if diff == 0
           else "Ngày mai" if diff == 1 else d.strftime("%d/%m"))
    return lbl + (f" · {t['due_time']}" if t.get("due_time") else "")

def preview_bits(p):
    """Danh sách 'mảnh' mô tả cách app hiểu một câu thêm nhanh (dùng cho xem trước)."""
    if not p: return []
    bits = []
    if p.get("due_date"):
        d = date.fromisoformat(p["due_date"])
        when = "Hôm nay" if p["due_date"] == TODAY else ("Ngày mai" if (d - today_()).days == 1 else d.strftime("%d/%m"))
        bits.append("📅 " + when + (f" {p['due_time']}" if p.get("due_time") else ""))
    if p.get("urgent"): bits.append("🔥 Gấp")
    if p.get("important"): bits.append("⭐ Quan trọng")
    if p.get("assignee"): bits.append("👤 @" + p["assignee"])
    for tg in (p.get("tags") or []): bits.append("#" + tg)
    if p.get("estimate_min"): bits.append(f"~{p['estimate_min']} phút")
    if p.get("remind_before"): bits.append(f"🔔 nhắc trước {p['remind_before']}p")
    rr = p.get("repeat_rule")
    if rr and rr != "none":
        if rr.startswith("wd:"):
            wnames = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]
            lab = "mỗi " + ",".join(wnames[int(x)] for x in rr[3:].split(",") if x != "")
        else:
            lab = {"daily": "mỗi ngày", "weekly": "mỗi tuần", "monthly": "mỗi tháng"}.get(rr, rr)
        left = p.get("repeat_left")
        bits.append("🔁 " + lab + (f" · tổng {left + 1} lần" if left is not None else ""))
    return bits

def split_capture(text):
    """Phân loại nội dung dán vào cửa sổ bắt việc:
    - nhiều dòng ngắn -> danh sách nhiều việc
    - một đoạn dài / nhiều đoạn -> 1 việc: dòng đầu làm tiêu đề, toàn bộ làm ghi chú
    - một dòng ngắn -> câu thêm nhanh (app tự phân tích ngày/giờ/mức)"""
    raw = (text or "").strip()
    lines = [l.strip() for l in raw.splitlines() if l.strip()]
    if len(lines) >= 2 and all(len(l) <= 200 for l in lines):
        return "multi", lines
    if len(raw) > 160 or "\n" in raw:
        title = lines[0] if lines else raw
        if len(title) > 140:
            cut = title[:137].rsplit(" ", 1)[0]
            title = (cut or title[:137]) + "…"
        return "long", (title, raw)
    return "quick", raw

def create_from_text(text, source="capture"):
    """Tạo việc từ bất kỳ đoạn chữ nào. Trả về số việc đã tạo."""
    kind, payload = split_capture(text)
    if kind == "multi":
        for line in payload:
            api("POST", "/api/quick", {"text": line, "source": source})
        return len(payload)
    if kind == "long":
        title, notes = payload
        api("POST", "/api/tasks", {"title": title, "notes": notes, "source": source})
        return 1
    if payload:
        api("POST", "/api/quick", {"text": payload, "source": source})
        return 1
    return 0

def win_toast(title, body):
    """Thông báo bong bóng Windows qua PowerShell + NotifyIcon (chỉ thư viện
    chuẩn). Nội dung qua biến môi trường để khỏi lo ngoặc kép."""
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

def spawn_capture():
    """Mở tiến trình cửa sổ bắt việc siêu nhanh. Bản đóng exe: chính file exe
    tự nhận tham số --capture; bản chạy source: gọi lại app.py bằng python."""
    try:
        if FROZEN:
            subprocess.Popen([sys.executable, "--capture"])
        else:
            subprocess.Popen([sys.executable, os.path.abspath(__file__), "--capture"])
    except Exception as e:
        print("spawn capture error:", e)

def desktop_notify(title, body):
    if IS_WIN:
        win_toast(title, body)
        return
    try:
        env = dict(os.environ)
        env.setdefault("DISPLAY", ":0")
        subprocess.run(["notify-send", "-a", "Shini Tasks", title, body], env=env, timeout=6, check=False)
    except Exception:
        pass

def hm_to_min(s):
    """'09:30' -> 570. Sai định dạng -> None."""
    try:
        h, m = (s or "").strip().split(":")
        h, m = int(h), int(m)
        if 0 <= h <= 23 and 0 <= m <= 59: return h * 60 + m
    except Exception: pass
    return None

def min_to_hm(v):
    return f"{v // 60:02d}:{v % 60:02d}"

def find_conflict(tasks, date_iso, start_min, dur_min, exclude_id=None):
    """Việc nào đã chiếm khung giờ này? Trả về task trùng hoặc None.
    Chỉ tính việc CHƯA xong, có ngày + giờ bắt đầu. Sát biên (kết thúc = bắt đầu) KHÔNG tính là trùng."""
    end_min = start_min + (dur_min or 60)
    for t in tasks:
        if t["status"] == "done" or t["id"] == exclude_id: continue
        if t.get("due_date") != date_iso or not t.get("due_time"): continue
        s2 = hm_to_min(t["due_time"])
        if s2 is None: continue
        e2 = s2 + (t.get("estimate_min") or 60)
        if start_min < e2 and s2 < end_min: return t
    return None

def contrast_text(hexcolor):
    try:
        h = hexcolor.lstrip("#"); r, g, b = (int(h[i:i+2], 16) for i in (0, 2, 4))
        return "#101010" if (0.299*r + 0.587*g + 0.114*b) > 150 else "#FFFFFF"
    except Exception: return "#FFFFFF"

def hex_rgb(hexcolor):
    h = (hexcolor or "#888888").lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

def rgba_str(hexcolor, alpha):
    r, g, b = hex_rgb(hexcolor)
    return f"rgba({r},{g},{b},{alpha})"

def mix_hex(hexcolor, other, frac):
    """Pha màu: frac=0 -> hexcolor, frac=1 -> other (#RRGGBB)."""
    r1, g1, b1 = hex_rgb(hexcolor); r2, g2, b2 = hex_rgb(other)
    return "#%02X%02X%02X" % (round(r1 + (r2 - r1) * frac), round(g1 + (g2 - g1) * frac), round(b1 + (b2 - b1) * frac))

def notify_local(title, body):
    if IS_WIN:
        win_toast(title, body)
        return
    env = dict(os.environ)
    env.setdefault("DISPLAY", ":0")
    env.setdefault("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
    env.setdefault("DBUS_SESSION_BUS_ADDRESS", f"unix:path=/run/user/{os.getuid()}/bus")
    try: subprocess.run(["notify-send", "-a", "Shini Tasks", title, body], env=env, timeout=6)
    except Exception: pass

class Ring(Gtk.DrawingArea):
    """Vòng tiến độ nhỏ (16px) cạnh tên dự án ở sidebar — kiểu Things/Linear:
    cho biết dự án đã xong bao nhiêu phần, không tốn diện tích như thanh dài."""
    def __init__(self):
        super().__init__()
        self.set_size_request(16, 16)
        self._f = 0.0
        self.set_draw_func(self._draw)

    def set_fraction(self, f):
        self._f = max(0.0, min(1.0, f or 0))
        self.queue_draw()

    def _draw(self, area, cr, w, h):
        import math
        cr.set_line_width(2.6)
        cr.set_source_rgba(0.55, 0.58, 0.68, 0.35)
        cr.arc(8, 8, 6.2, 0, 2 * math.pi); cr.stroke()
        if self._f > 0:
            cr.set_source_rgb(0.30, 0.55, 1.0)
            cr.arc(8, 8, 6.2, -math.pi / 2, -math.pi / 2 + 2 * math.pi * self._f)
            cr.stroke()


class Bar(Gtk.DrawingArea):
    """Thanh ngang 9px tự vẽ bằng Cairo: rãnh + phần đã đầy bo tròn.
    Màu lấy theo theme hiện tại lúc vẽ — không phụ thuộc CSS của theme GTK
    (LevelBar/ProgressBar từng bị theme thổi phồng chiều cao và khó đọc)."""
    def __init__(self):
        super().__init__()
        self.frac = 0.0
        self.set_size_request(-1, 9)
        self.set_content_height(9)
        self.set_hexpand(True)
        self.set_draw_func(self._draw)

    def set_fraction(self, f):
        self.frac = max(0.0, min(1.0, float(f or 0)))
        self.queue_draw()

    def _draw(self, area, cr, w, h):
        light = SETTINGS["theme"] == "light"
        track = (0.0, 0.0, 0.0, 0.10) if light else (1.0, 1.0, 1.0, 0.10)
        fill = (0.09, 0.09, 0.09, 1.0) if light else (0.90, 0.90, 0.90, 1.0)
        r = h / 2.0
        def pill(width, rgba):
            if width <= 0: return
            cr.set_source_rgba(*rgba)
            if width <= h:
                cr.arc(width / 2.0, r, width / 2.0, 0, 6.2832); cr.fill(); return
            cr.rectangle(r, 0, width - 2 * r, h)
            cr.arc(r, r, r, 0, 6.2832); cr.fill()
            cr.arc(width - r, r, r, 0, 6.2832); cr.fill()
        pill(w, track)
        if self.frac > 0:
            pill(max(w * self.frac, h * 0.9), fill)


class BarsChart(Gtk.DrawingArea):
    """Biểu đồ cột dọc vẽ bằng Cairo (cho trang Thống kê): data = [(nhãn, số)].
    Màu đọc theo theme tại lúc vẽ — cùng nguyên tắc với Bar, không phụ thuộc
    theme GTK của hệ thống."""
    def __init__(self, height=170):
        super().__init__()
        self.set_content_height(height)
        self.data = []
        self.set_draw_func(self._draw)

    def set_data(self, data):
        self.data = data
        self.queue_draw()

    def _draw(self, _area, cr, w, h):
        dark = SETTINGS["theme"] == "dark"
        bar_c = (0.34, 0.61, 0.84) if dark else (0.15, 0.39, 0.92)
        today_c = (0.97, 0.55, 0.42)
        txt_c = (0.93, 0.93, 0.93) if dark else (0.07, 0.07, 0.07)
        lab_c = (0.78, 0.78, 0.78) if dark else (0.35, 0.39, 0.43)
        if not self.data: return
        n = len(self.data)
        mx = max(1, max(v for _l, v in self.data))
        base = h - 24
        top = 20
        slot = (w - 16) / n
        bw = min(36.0, slot * 0.55)
        cr.set_source_rgba(*lab_c, 0.35)
        cr.set_line_width(1)
        cr.move_to(8, base + 0.5); cr.line_to(w - 8, base + 0.5); cr.stroke()
        cr.select_font_face("Sans", 0, 0)  # 0=normal slant/weight qua API chữ của cairo
        for i, (lab, v) in enumerate(self.data):
            cx = 8 + slot * i + slot / 2
            bh = (base - top) * (v / mx) if v else 0
            cr.set_source_rgb(*(today_c if i == n - 1 else bar_c))
            if v:
                x0, y0 = cx - bw / 2, base - bh
                r = min(4, bw / 2, bh)
                cr.new_path()
                cr.arc(x0 + r, y0 + r, r, 3.14159, 3.14159 * 1.5)
                cr.arc(x0 + bw - r, y0 + r, r, 3.14159 * 1.5, 0)
                cr.line_to(x0 + bw, base); cr.line_to(x0, base)
                cr.close_path(); cr.fill()
                cr.set_source_rgb(*txt_c)
                cr.set_font_size(11)
                s = str(v)
                ext = cr.text_extents(s)
                cr.move_to(cx - ext.width / 2, y0 - 5); cr.show_text(s)
            cr.set_source_rgb(*lab_c)
            cr.set_font_size(9.5)
            ext = cr.text_extents(lab)
            cr.move_to(cx - ext.width / 2, base + 14); cr.show_text(lab)


def export_week_report(win):
    """Xuất BÁO CÁO TUẦN ra PNG bằng Cairo thuần — không mở cửa sổ nào (khỏi
    chớp màn hình), vẽ trên nền xanh-đen như theme tối của app. Trả về đường dẫn."""
    import cairo
    from gi.repository import PangoCairo as PCairo
    from gi.repository import Pango as PangoM
    today = today_()
    monday = today - timedelta(days=today.weekday())
    days = [monday + timedelta(days=i) for i in range(7)]
    done_by = {}
    for t in win.all_tasks:
        if t["status"] == "done" and t.get("done_at"):
            done_by[t["done_at"][:10]] = done_by.get(t["done_at"][:10], 0) + 1
    week_counts = [done_by.get(d.isoformat(), 0) for d in days]
    done_week = sum(week_counts)
    colnames = {c["id"]: c["name"] for c in win.columns}
    per_col = {}
    for t in win.all_tasks:
        if t["status"] == "done" and t.get("done_at") and days[0].isoformat() <= t["done_at"][:10] <= days[-1].isoformat():
            nm = colnames.get(t.get("column_id"), "ĐÃ XONG")
            per_col[nm] = per_col.get(nm, 0) + 1
    top_cols = sorted(per_col.items(), key=lambda kv: -kv[1])[:3]
    W, H = 920, 600
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    cr = cairo.Context(surf)
    cr.set_source_rgb(0.098, 0.11, 0.141); cr.paint()                     # #191C24
    cr.set_source_rgb(0.13, 0.145, 0.184)
    cr.rectangle(0, 0, W, 92); cr.fill()                                  # dải đầu #21252F
    def text(x, y, s, size, color, bold=False, right=False, center=False):
        # Neo theo MÉP TRÊN của khung chữ: phải bù logical extents của Pango,
        # nếu không chữ càng to càng bị vẽ trôi xuống dưới điểm y đã định
        # (bản đầu: chú thích KPI đè lên chính con số 34pt).
        lay = PCairo.create_layout(cr)
        lay.set_text(s, -1)
        lay.set_font_description(PangoM.FontDescription(("Bold " if bold else "") + str(size)))
        _ink, logical = lay.get_pixel_extents()
        tx = x - logical.width if right else (x - logical.width / 2 if center else x)
        cr.set_source_rgb(*color)
        cr.move_to(tx - logical.x, y - logical.y)
        PCairo.show_layout(cr, lay)
    WHITE, MUT, ORANGE, BLUE, PINK = (0.93, 0.93, 0.93), (0.78, 0.78, 0.78), (0.97, 0.55, 0.42), (0.48, 0.72, 0.93), (1.0, 0.56, 0.66)
    text(36, 26, "✦ SHINI TASKS — BÁO CÁO TUẦN", 20, WHITE, bold=True)
    text(36, 58, f"Tuần {monday.strftime('%d/%m')} – {days[-1].strftime('%d/%m/%Y')} · xuất ngày {today.strftime('%d/%m/%Y')}", 12.5, MUT)
    kpis = [(f"{done_week}", "việc đã xong tuần này", ORANGE),
            (f"{win.stats.get('streak', 0)}", "ngày chuỗi có việc xong", PINK),
            (f"{win.stats.get('open', 0)}", "việc đang mở", BLUE),
            (f"{win.stats.get('overdue', 0)}", "việc đang quá hạn", ORANGE)]
    for i, (num, cap, c) in enumerate(kpis):
        x = 36 + i * 218
        text(x, 116, num, 34, c, bold=True)
        text(x, 172, cap, 11.5, MUT)
    # biểu đồ 7 ngày
    base, top, x0, x1 = 400, 230, 46, W - 46
    mx = max(1, max(week_counts))
    slot = (x1 - x0) / 7
    cr.set_source_rgba(0.78, 0.78, 0.78, 0.3); cr.set_line_width(1)
    cr.move_to(x0, base + 0.5); cr.line_to(x1, base + 0.5); cr.stroke()
    VN = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"]
    for i, v in enumerate(week_counts):
        cx = x0 + slot * i + slot / 2
        bh = (base - top) * (v / mx) if v else 0
        if v:
            cr.set_source_rgb(*(ORANGE if days[i] == today else BLUE))
            cr.rectangle(cx - 26, base - bh, 52, bh); cr.fill()
            text(cx, base - bh - 26, str(v), 13, WHITE, bold=True, center=True)
        lay = PCairo.create_layout(cr); lay.set_text(VN[i], -1)
        lay.set_font_description(PangoM.FontDescription("10.5"))
        pw, _ = lay.get_pixel_size()
        cr.set_source_rgb(*MUT); cr.move_to(cx - pw / 2, base + 10); PCairo.show_layout(cr, lay)
    y = 448
    text(36, y, "Cột làm được nhiều nhất tuần này:", 13, WHITE, bold=True); y += 30
    if top_cols:
        for nm, n_ in top_cols:
            text(52, y, f"• {nm}: {n_} việc", 12.5, MUT); y += 24
    else:
        text(52, y, "• Chưa có việc nào xong trong tuần này", 12.5, MUT); y += 24
    text(W - 36, H - 34, "Shini Tasks · báo cáo tự động", 10.5, MUT, right=True)
    outdir = os.path.join(os.path.expanduser("~"), "Pictures", "Shini Tasks")
    os.makedirs(outdir, exist_ok=True)
    path = os.path.join(outdir, f"bao-cao-tuan-{monday.isoformat()}.png")
    surf.write_to_png(path)
    return path


class DetailPane:
    """Panel chi tiết BÊN PHẢI (v1.5.0 — thiết kế lại theo khung chuẩn các app
    lớn: Todoist/Linear/Asana đều mở panel phải khi chọn việc, không dùng hộp
    thoại giữa màn hình). Thay hẳn EditDialog cũ. Mọi trường TỰ LƯU ngay khi
    đổi (PATCH từng trường) — không còn nút Lưu/Hủy. Việc mới: tạo bản ghi
    "Việc mới" rồi mở panel này với ô tiêu đề được chọn sẵn để gõ đè."""

    def __init__(self, win):
        self.win = win
        self.task = None
        self._guard = False          # đang nạp giá trị vào control -> bỏ qua signal
        self._sec = {}               # tên mục -> widget (để cuộn tới khi mở từ chip 💬/📎)
        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.box.add_css_class("pane")
        self.box.set_margin_top(14); self.box.set_margin_bottom(14)
        self.box.set_margin_start(14); self.box.set_margin_end(14)

    # ---------- Mở / đóng ----------
    def open(self, task, section=None):
        self.task = dict(task)
        self.win._show_pane()
        self._build()
        vadj = self.win.pane_scroll.get_vadjustment()
        if vadj: vadj.set_value(0)
        if section:
            GLib.timeout_add(80, lambda: (self._scroll_to(section), False)[1])

    def _scroll_to(self, section):
        w = self._sec.get(section)
        if not w: return
        ok, _x, y = w.translate_coordinates(self.box, 0, 0)
        if ok:
            vadj = self.win.pane_scroll.get_vadjustment()
            if vadj: vadj.set_value(max(0, y - 8))

    def close(self):
        self.task = None
        self.win._hide_pane()

    def focus_title(self):
        if getattr(self, "e_title", None):
            self.e_title.grab_focus()
            self.e_title.select_region(0, -1)

    # ---------- Chữ chưa lưu (gõ dở trong các ô nhập) ----------
    def _num_dirty(self, entry, cur):
        txt = entry.get_text().strip()
        try: v = int(txt) if txt else None
        except Exception: return True
        return v != (cur or None)

    def _dirty_saves(self):
        """Tên các hàm _save_* cần gọi để lưu nốt chữ đang gõ dở. Các trường
        chọn-bấm (dropdown, ngày, sao, duyệt, việc con…) lưu NGAY khi đổi nên
        không nằm ở đây — chỉ các ô GÕ CHỮ mới lưu trễ (Enter / rời ô)."""
        if not self.task: return []
        t = self.task; out = []
        if getattr(self, "e_title", None) is not None \
                and self.e_title.get_text().strip() != (t.get("title") or ""):
            out.append("_save_title")
        if getattr(self, "tv_notes", None) is not None:
            buf = self.tv_notes.get_buffer()
            if buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False) != (t.get("notes") or ""):
                out.append("_save_notes")
        if getattr(self, "e_assignee", None) is not None \
                and self.e_assignee.get_text().strip() != (t.get("assignee") or ""):
            out.append("_save_assignee")
        if getattr(self, "e_tags", None) is not None \
                and self.e_tags.get_text().strip() != ", ".join(t.get("tags") or []):
            out.append("_save_tags")
        if getattr(self, "e_est", None) is not None \
                and self._num_dirty(self.e_est, t.get("estimate_min")):
            out.append("_save_est")
        if getattr(self, "e_rem", None) is not None \
                and self._num_dirty(self.e_rem, t.get("remind_before")):
            out.append("_save_rem")
        return out

    def _pending_dirty(self):
        return bool(self._dirty_saves())

    def _flush_pending(self):
        for name in self._dirty_saves():
            try: getattr(self, name)()
            except Exception: pass

    # ---------- Lưu từng trường ----------
    def _patch(self, body, rebuild=False):
        if not self.task: return
        try:
            r = api("PATCH", f"/api/tasks/{self.task['id']}", body)
            if r and r.get("task"): self.task = r["task"]
        except Exception as e:
            self.win._toast(f"⚠ Chưa lưu được thay đổi: {e}")
            return
        if rebuild: self._build()
        self.win.refresh()

    def _conflict_msg(self, date_iso, time_hm, est):
        if not date_iso or not time_hm: return None
        sm = hm_to_min(time_hm)
        if sm is None: return "⚠ Giờ bắt đầu chưa đúng định dạng."
        cf = find_conflict(self.win.all_tasks, date_iso, sm, est or 60,
                           exclude_id=self.task["id"])
        if cf: return f"⚠ Trùng lịch với việc “{cf['title']}” ({cf.get('due_time') or ''} cùng ngày) — đã hoàn lại giờ cũ."
        return None

    def _leave(self, widget, fn):
        ctl = Gtk.EventControllerFocus()
        ctl.connect("leave", lambda *_: fn())
        widget.add_controller(ctl)

    def _frow(self, label, widget):
        b = Gtk.Box(spacing=8)
        l = Gtk.Label(label=label, xalign=0); l.add_css_class("pfield-k")
        l.set_size_request(88, -1); l.set_valign(Gtk.Align.CENTER)
        b.append(l)
        try: widget.set_hexpand(True)
        except Exception: pass
        b.append(widget)
        return b

    # ---------- Dựng toàn bộ panel cho việc hiện tại ----------
    def _build(self):
        for c in _kids(self.box): self.box.remove(c)
        self._sec = {}
        t = self.task
        if not t: return
        self._guard = True
        win = self.win
        # --- Đầu panel: cột · dự án ... ghim + đóng ---
        hdr = Gtk.Box(spacing=8)
        col = next((c for c in win.columns if c["id"] == t.get("column_id")), None)
        proj = next((p for p in win.projects if p["id"] == t.get("project_id")), None)
        dot = Gtk.Box(); dot.set_size_request(9, 9); dot.set_valign(Gtk.Align.CENTER)
        prov = Gtk.CssProvider()
        css_load(prov, f".panedot {{ background: {(col or {}).get('color') or '#888'}; border-radius: 999px; }}".encode())
        dot.add_css_class("panedot")
        dot.get_style_context().add_provider(prov, Gtk.STYLE_PROVIDER_PRIORITY_USER)
        hdr.append(dot)
        where = Gtk.Label(label=f"{(col or {}).get('name', '—')} · {(proj or {}).get('name', '')}", xalign=0)
        where.add_css_class("mut"); where.set_ellipsize(Pango.EllipsizeMode.END); where.set_hexpand(True)
        hdr.append(where)
        pin = Gtk.ToggleButton(label="📌"); pin.add_css_class("dlgbtn"); pin.add_css_class("mini")
        pin.set_active(bool(t.get("pinned")))
        pin.set_tooltip_text("Ghim việc này lên mục ĐÃ GHIM ở thanh bên")
        pin.connect("toggled", lambda b: None if self._guard else self._patch({"pinned": 1 if b.get_active() else 0}))
        hdr.append(pin)
        xb = Gtk.Button(label="✕"); xb.add_css_class("dlgbtn"); xb.add_css_class("mini")
        xb.set_tooltip_text("Đóng panel (Esc)")
        xb.connect("clicked", lambda *_: win.request_close_pane())
        hdr.append(xb)
        self.box.append(hdr)
        # --- Hàng xong / menu phụ ---
        row = Gtk.Box(spacing=8)
        done = t["status"] == "done"
        self.done_btn = Gtk.Button(label="✓ Đã xong — bấm để mở lại" if done else "○ Đánh dấu xong")
        self.done_btn.add_css_class("dlgbtn")
        self.done_btn.connect("clicked", self._toggle_done)
        row.append(self.done_btn)
        mb = Gtk.MenuButton(label="⋯"); mb.add_css_class("dlgbtn")
        mb.set_tooltip_text("Nhân đôi · Dời mai · Bỏ qua kỳ · Xoá việc")
        pop = Gtk.Popover()
        pbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        pbox.set_margin_top(6); pbox.set_margin_bottom(6); pbox.set_margin_start(6); pbox.set_margin_end(6)
        dup = Gtk.Button(label="⧉ Nhân đôi việc"); dup.add_css_class("flat"); dup.add_css_class("dlgflat")
        dup.connect("clicked", lambda *_: (pop.popdown(), win._duplicate(self.task)))
        pbox.append(dup)
        tom = Gtk.Button(label="🌅 Dời sang mai"); tom.add_css_class("flat"); tom.add_css_class("dlgflat")
        tom.connect("clicked", lambda *_: (pop.popdown(), self._postpone_tomorrow()))
        pbox.append(tom)
        if (t.get("repeat_rule") or "none") != "none":
            sk = Gtk.Button(label="⏭ Bỏ qua kỳ này"); sk.add_css_class("flat"); sk.add_css_class("dlgflat")
            sk.connect("clicked", lambda *_: (pop.popdown(), self._skip_once()))
            pbox.append(sk)
        dele = Gtk.Button(label="🗑 Xoá việc (vào thùng rác)"); dele.add_css_class("flat"); dele.add_css_class("dlgflat")
        dele.connect("clicked", lambda *_: (pop.popdown(), win._delete(self.task), win.close_pane()))
        pbox.append(dele)
        pop.set_child(pbox)
        mb.set_popover(pop)
        row.append(mb)
        sp = Gtk.Box(); sp.set_hexpand(True); row.append(sp)
        self.box.append(row)
        # --- Tiêu đề ---
        self.e_title = Gtk.Entry(); self.e_title.add_css_class("panetitle")
        self.e_title.set_text(t["title"])
        self.e_title.connect("activate", self._save_title)
        self._leave(self.e_title, self._save_title)
        self.box.append(self.e_title)
        self.err_lab = Gtk.Label(label="", xalign=0, wrap=True)
        self.err_lab.add_css_class("errlab"); self.err_lab.set_visible(False)
        self.box.append(self.err_lab)
        # --- Trạng thái + ưu tiên ---
        self.d_status = Gtk.DropDown.new_from_strings(["Chưa làm", "Đang làm", "Đã xong"])
        self.d_status.set_selected({"todo": 0, "doing": 1, "done": 2}.get(t["status"], 0))
        self.d_status.connect("notify::selected", self._on_status)
        self.box.append(self._frow("Trạng thái", self.d_status))
        self._level = level_of(t)
        self.d_level = Gtk.DropDown.new_from_strings(
            [SETTINGS["labels"][lv] for lv in ("L1", "L2", "L3", "L4")])
        self.d_level.set_selected(("L1", "L2", "L3", "L4").index(self._level))
        self.d_level.set_tooltip_text("L1 = Gấp + Quan trọng · L2 = Quan trọng · L3 = Gấp · L4 = không cờ nào")
        self.d_level.connect("notify::selected", self._on_level_drop)
        self.box.append(self._frow("Ưu tiên", self.d_level))
        # --- Dự án + Cột ---
        self._proj_ids = [p["id"] for p in win.projects]
        self.d_proj = Gtk.DropDown.new_from_strings([p["name"] for p in win.projects] or ["(chưa có dự án)"])
        want_pid = t.get("project_id") or win.cur_project
        if want_pid in self._proj_ids: self.d_proj.set_selected(self._proj_ids.index(want_pid))
        self.d_col = Gtk.DropDown.new_from_strings(["…"])
        self._fill_cols(t.get("column_id"))
        self.d_proj.connect("notify::selected", self._on_proj)
        self.d_col.connect("notify::selected", self._on_col)
        if win.projects: self.box.append(self._frow("Dự án", self.d_proj))
        self.box.append(self._frow("Cột", self.d_col))
        # --- Ngày / giờ ---
        self._date_iso = t.get("due_date") or ""
        self._time_hm = t.get("due_time") or ""
        self._start_iso = t.get("start_date") or ""
        self.b_date = self._date_button("due")
        self.b_time = self._time_button()
        self._sync_date_btn(); self._sync_time_btn()
        drow = Gtk.Box(spacing=8)
        self.b_date.set_hexpand(True); self.b_time.set_hexpand(True)
        drow.append(self.b_date); drow.append(self.b_time)
        self.box.append(self._frow("Hạn", drow))
        qrow = Gtk.Box(spacing=6)
        for label, fn in [("Hôm nay", lambda: self._quick_date(today_().isoformat())),
                          ("Ngày mai", lambda: self._quick_date((today_() + timedelta(days=1)).isoformat())),
                          ("Cuối tuần", lambda: self._quick_date(this_sunday().isoformat())),
                          ("Xóa hạn", lambda: (self._set_date(""), self._set_time(""), self._save_schedule()))]:
            b = Gtk.Button(label=label); b.add_css_class("dlgbtn"); b.add_css_class("mini")
            b.connect("clicked", lambda *_ , f=fn: f()); qrow.append(b)
        self.box.append(qrow)
        # --- Nhóm "Chi tiết khác": trường ít dùng / đang trống gập lại cho
        # popup gọn (Sinh chê dư thừa 2026-11-17). Tự mở sẵn khi có giá trị.
        self.more_btn = Gtk.Button(label="▸ Chi tiết khác — bắt đầu · lặp · người làm · nhãn · đánh giá")
        self.more_btn.add_css_class("flat"); self.more_btn.add_css_class("dlgflat")
        self.more_btn.set_halign(Gtk.Align.START)
        self.more_btn.connect("clicked", self._toggle_more)
        self.box.append(self.more_btn)
        self.more_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.box.append(self.more_box)
        self.b_start = self._date_button("start")
        self._sync_start_btn()
        self.more_box.append(self._frow("Bắt đầu", self.b_start))
        # --- Lặp lại ---
        self.d_repeat = Gtk.DropDown.new_from_strings(["Không lặp", "Mỗi ngày", "Mỗi tuần", "Mỗi tháng", "Theo thứ…"])
        rule0 = (t.get("repeat_rule") or "none")
        self.d_repeat.set_selected(4 if rule0.startswith("wd:") else
                                   {"none": 0, "daily": 1, "weekly": 2, "monthly": 3}.get(rule0, 0))
        self.d_repeat.connect("notify::selected", lambda *_: None if self._guard else (self._sync_repeat_ui(), self._save_repeat()))
        self.more_box.append(self._frow("Lặp lại", self.d_repeat))
        self.wd_row = Gtk.Box(spacing=4)
        self.wd_btns = {}
        wd_sel = {int(x) for x in rule0[3:].split(",") if x != ""} if rule0.startswith("wd:") else set()
        for wd, lab in [(0, "T2"), (1, "T3"), (2, "T4"), (3, "T5"), (4, "T6"), (5, "T7"), (6, "CN")]:
            b = Gtk.ToggleButton(label=lab); b.add_css_class("dlgbtn"); b.add_css_class("mini")
            b.set_active(wd in wd_sel)
            b.connect("toggled", lambda *_: None if self._guard else self._save_repeat())
            self.wd_btns[wd] = b; self.wd_row.append(b)
        self.wd_field = self._frow("Vào các thứ", self.wd_row)
        self.more_box.append(self.wd_field)
        self.e_left = Gtk.Entry(placeholder_text="lặp mãi")
        if t.get("repeat_left") is not None: self.e_left.set_text(str(t["repeat_left"]))
        self.e_left.connect("activate", lambda *_: self._save_repeat())
        self._leave(self.e_left, self._save_repeat)
        self.left_field = self._frow("Lặp thêm (lần)", self.e_left)
        self.more_box.append(self.left_field)
        self._sync_repeat_ui()
        # --- Số phút / nhắc / người làm / nhãn ---
        self.e_est = Gtk.Entry(placeholder_text="30")
        if t.get("estimate_min"): self.e_est.set_text(str(t["estimate_min"]))
        self.e_est.connect("activate", self._save_est)
        self._leave(self.e_est, self._save_est)
        self.box.append(self._frow("Ước lượng (phút)", self.e_est))
        self.e_rem = Gtk.Entry(); self.e_rem.set_text(str(t.get("remind_before", 30)))
        self.e_rem.connect("activate", self._save_rem)
        self._leave(self.e_rem, self._save_rem)
        self.box.append(self._frow("Nhắc trước (phút)", self.e_rem))
        self.e_assignee = Gtk.Entry(placeholder_text="Tên người được giao…")
        if t.get("assignee"): self.e_assignee.set_text(t["assignee"])
        self.e_assignee.connect("activate", self._save_assignee)
        self._leave(self.e_assignee, self._save_assignee)
        self.more_box.append(self._frow("Người làm", self.e_assignee))
        self.e_tags = Gtk.Entry(placeholder_text="work, nhà, học…")
        self.e_tags.set_text(", ".join(t.get("tags") or []))
        self.e_tags.connect("activate", self._save_tags)
        self._leave(self.e_tags, self._save_tags)
        self.more_box.append(self._frow("Nhãn", self.e_tags))
        # --- Đồng hồ bấm giờ ---
        trow2 = Gtk.Box(spacing=8)
        self.timer_lab = Gtk.Label(label="", xalign=0, css_classes=["mut"])
        trow2.append(self.timer_lab)
        self.timer_btn = Gtk.Button(); self.timer_btn.add_css_class("dlgbtn")
        self.timer_btn.connect("clicked", self._toggle_timer)
        trow2.append(self.timer_btn)
        self.more_box.append(self._frow("Làm thật", trow2))
        self._sync_timer_ui()
        # --- Đánh giá & phê duyệt (gói Coogo v1.6.0) ---
        self.more_box.append(Gtk.Label(label="ĐÁNH GIÁ", xalign=0, css_classes=["pane-h"]))
        srow = Gtk.Box(spacing=2)
        self._star_btns = []
        for i in range(1, 6):
            on = (t.get("rating") or 0) >= i
            sb_ = Gtk.Button(label="★" if on else "☆")
            sb_.add_css_class("starbtn")
            if on: sb_.add_css_class("on")
            sb_.set_tooltip_text(f"Chấm {i} sao (bấm lại sao đang chọn để bỏ chấm)")
            sb_.connect("clicked", lambda *_ , n=i: self._set_rating(n))
            self._star_btns.append(sb_)
            srow.append(sb_)
        self.more_box.append(self._frow("Chấm sao", srow))
        self.d_verdict = Gtk.DropDown.new_from_strings(["Chưa duyệt", "Đã duyệt ✓", "Làm lại ↺"])
        self.d_verdict.set_selected({"": 0, "approved": 1, "redo": 2}.get(t.get("verdict") or "", 0))
        self.d_verdict.connect("notify::selected", self._on_verdict)
        self.more_box.append(self._frow("Phê duyệt", self.d_verdict))
        _has_more = bool(t.get("start_date") or (t.get("repeat_rule") or "none") != "none"
                         or t.get("assignee") or (t.get("tags") or [])
                         or (t.get("actual_min") or 0) > 0 or t.get("timer_start")
                         or (t.get("rating") or 0) > 0 or (t.get("verdict") or ""))
        self.more_box.set_visible(_has_more)
        self._sync_more_btn()
        # --- Mô tả ---
        self.box.append(Gtk.Label(label="MÔ TẢ", xalign=0, css_classes=["pane-h"]))
        frame = Gtk.Frame()
        self.tv_notes = Gtk.TextView(); self.tv_notes.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.tv_notes.add_css_class("panenotes")
        self.tv_notes.set_top_margin(6); self.tv_notes.set_bottom_margin(6)
        self.tv_notes.set_left_margin(8); self.tv_notes.set_right_margin(8)
        self.tv_notes.get_buffer().set_text(t.get("notes") or "")
        sw = Gtk.ScrolledWindow(); sw.set_min_content_height(64); sw.set_child(self.tv_notes)
        frame.set_child(sw)
        self.box.append(frame)
        self._leave(self.tv_notes, self._save_notes)
        # --- Việc con ---
        sec_sub = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        subs = t.get("subtasks") or []
        self.sub_head = Gtk.Label(label=f"VIỆC CON · {sum(1 for s in subs if s.get('done'))}/{len(subs)}",
                                  xalign=0, css_classes=["pane-h"])
        sec_sub.append(self.sub_head)
        self.sub_rows = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        sec_sub.append(self.sub_rows)
        for s in subs: self._sub_row(s.get("t", ""), bool(s.get("done")),
                                     s.get("desc") or s.get("d") or "",
                                     "d" if s.get("d") and not s.get("desc") else "desc")
        add_sub = Gtk.Button(label="＋ Thêm việc con"); add_sub.add_css_class("flat"); add_sub.add_css_class("dlgflat")
        add_sub.set_halign(Gtk.Align.START)
        add_sub.connect("clicked", lambda *_: self._sub_row("", False, focus=True))
        sec_sub.append(add_sub)
        self.box.append(sec_sub)
        self._sec["subtasks"] = sec_sub
        # --- File đính kèm ---
        sec_att = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        sec_att.append(Gtk.Label(label="FILE ĐÍNH KÈM", xalign=0, css_classes=["pane-h"]))
        self.att_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        sec_att.append(self.att_list)
        aadd = Gtk.Button(label="📎 Thêm file…"); aadd.add_css_class("flat"); aadd.add_css_class("dlgflat")
        aadd.set_halign(Gtk.Align.START)
        aadd.connect("clicked", self._pick_attachment)
        sec_att.append(aadd)
        self.box.append(sec_att)
        self._sec["files"] = sec_att
        # --- Bình luận ---
        sec_cmt = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        sec_cmt.append(Gtk.Label(label="BÌNH LUẬN", xalign=0, css_classes=["pane-h"]))
        self.cmt_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=7)
        sec_cmt.append(self.cmt_list)
        crow = Gtk.Box(spacing=6)
        self.e_cmt = Gtk.Entry(placeholder_text="Viết bình luận…"); self.e_cmt.set_hexpand(True)
        self.e_cmt.connect("activate", self._add_comment)
        catt = Gtk.Button(label="📎"); catt.add_css_class("dlgbtn")
        catt.set_tooltip_text("Gắn file / ảnh / video vào bình luận này")
        catt.connect("clicked", self._pick_cmt_file)
        csend = Gtk.Button(label="Gửi"); csend.add_css_class("dlgbtn")
        csend.connect("clicked", self._add_comment)
        crow.append(self.e_cmt); crow.append(catt); crow.append(csend)
        sec_cmt.append(crow)
        self._cmt_file = None
        self.cmt_file_row = Gtk.Box(spacing=6)
        self.cmt_file_lab = Gtk.Label(label="", xalign=0); self.cmt_file_lab.add_css_class("mut")
        self.cmt_file_lab.set_hexpand(True); self.cmt_file_lab.set_ellipsize(Pango.EllipsizeMode.END)
        cx = Gtk.Button(label="✕"); cx.add_css_class("mini"); cx.add_css_class("flat")
        cx.connect("clicked", lambda *_: self._stage_cmt_file(None))
        self.cmt_file_row.append(self.cmt_file_lab); self.cmt_file_row.append(cx)
        self.cmt_file_row.set_visible(False)
        sec_cmt.append(self.cmt_file_row)
        self.box.append(sec_cmt)
        self._sec["comments"] = sec_cmt
        self._load_comments(); self._load_attachments()
        self._guard = False

    # ---------- Các trường ----------
    def _toggle_done(self, *_):
        if not self.task: return
        tid = self.task["id"]
        self.win._toggle(self.task)
        nt = self.win._find_task(tid)
        if nt: self.task = nt; self._build()
        else: self.win.close_pane()

    def _postpone_tomorrow(self):
        """Dời hạn sang mai — kèm toast Hoàn tác (gói B audit 2026-11-17)."""
        if not self.task: return
        tid, old = self.task["id"], self.task.get("due_date")
        self._patch({"due_date": (today_() + timedelta(days=1)).isoformat()}, rebuild=True)
        def undo():
            self.win._safe(api, "PATCH", f"/api/tasks/{tid}", {"due_date": old})
            self.win.refresh(); self.win._pane_resync(tid)
        self.win._toast("🌅 Đã dời việc sang mai", undo_fn=undo)

    def _skip_once(self):
        try: api("POST", f"/api/tasks/{self.task['id']}/skip")
        except Exception as e:
            self.err_lab.set_text(f"Bỏ qua lỗi: {e}"); self.err_lab.set_visible(True); return
        self.win.refresh(); self.win.close_pane()

    def _save_title(self, *_):
        if self._guard or not self.task: return
        txt = self.e_title.get_text().strip()
        if not txt:
            self.e_title.set_text(self.task["title"]); return
        if txt != self.task["title"]: self._patch({"title": txt})

    def _on_status(self, *_):
        if self._guard or not self.task: return
        val = ["todo", "doing", "done"][self.d_status.get_selected()]
        cur = self.task["status"]
        if val == cur: return
        tid = self.task["id"]
        if val == "done":
            self.win._safe(api, "POST", f"/api/tasks/{tid}/done")
            title = self.task["title"]
            def undo():
                self.win._safe(api, "POST", f"/api/tasks/{tid}/reopen")
                self.win.refresh(); self.win._pane_resync(tid)
            self.win._toast(f"✓ Đã xong: {title}", undo_fn=undo)
        elif cur == "done":
            self.win._safe(api, "POST", f"/api/tasks/{tid}/reopen")
            if val == "doing": self._patch({"status": "doing"})
        else:
            self._patch({"status": val})
        self.win.refresh()
        nt = self.win._find_task(tid)
        if nt: self.task = nt; self._build()

    def _on_level_drop(self, *_):
        if self._guard or not self.task: return
        lv = ("L1", "L2", "L3", "L4")[self.d_level.get_selected()]
        if lv == self._level: return
        self._level = lv
        self._patch({"important": lv in ("L1", "L2"), "urgent": lv in ("L1", "L3")})

    def _fill_cols(self, want_col):
        pid = self._proj_ids[self.d_proj.get_selected()] if self._proj_ids else None
        self._cur_cols = [c for c in self.win.columns if c.get("project_id") == pid] or list(self.win.columns)
        self._guard = True
        self.d_col.set_model(Gtk.StringList.new([c["name"] for c in self._cur_cols]))
        ids = [c["id"] for c in self._cur_cols]
        if want_col in ids: self.d_col.set_selected(ids.index(want_col))
        self._guard = False

    def _on_proj(self, *_):
        if self._guard or not self.task: return
        pid = self._proj_ids[self.d_proj.get_selected()]
        self._fill_cols(None)
        if self._cur_cols:
            self._patch({"project_id": pid, "column_id": self._cur_cols[0]["id"]}, rebuild=True)

    def _on_col(self, *_):
        if self._guard or not self.task or not self._cur_cols: return
        cid = self._cur_cols[self.d_col.get_selected()]["id"]
        if cid != self.task.get("column_id"): self._patch({"column_id": cid}, rebuild=True)

    # ---------- Ngày / giờ ----------
    def _date_button(self, kind):
        b = Gtk.MenuButton(); b.add_css_class("dlgbtn")
        b.set_tooltip_text("Bấm để mở lịch chọn ngày")
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_top(10); box.set_margin_bottom(10); box.set_margin_start(10); box.set_margin_end(10)
        cal = Gtk.Calendar(); cal.add_css_class("calpick")
        box.append(cal)
        clr = Gtk.Button(label="Xóa ngày"); clr.add_css_class("flat"); clr.add_css_class("dlgflat")
        box.append(clr)
        pop = Gtk.Popover(); pop.set_child(box)
        b.set_popover(pop)
        if kind == "due":
            self.cal_due = cal
            cal.connect("day-selected", self._on_due_picked)
            clr.connect("clicked", lambda *_: (self._set_date(""), pop.popdown(), self._save_schedule()))
            pop.connect("map", lambda *_: self._sync_cal(cal, self._date_iso))
        else:
            self.cal_start = cal
            cal.connect("day-selected", self._on_start_picked)
            clr.connect("clicked", lambda *_: (self._set_start(""), pop.popdown(),
                                               self._patch({"start_date": None})))
            pop.connect("map", lambda *_: self._sync_cal(cal, self._start_iso))
        return b

    def _time_button(self):
        b = Gtk.MenuButton(); b.add_css_class("dlgbtn")
        b.set_tooltip_text("Bấm để chọn giờ bắt đầu")
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_top(10); box.set_margin_bottom(10); box.set_margin_start(10); box.set_margin_end(10)
        tspin = Gtk.Box(spacing=6); tspin.set_halign(Gtk.Align.CENTER)
        self.sp_h = Gtk.SpinButton.new_with_range(0, 23, 1); self.sp_h.set_wrap(True); self.sp_h.add_css_class("timepick")
        self.sp_m = Gtk.SpinButton.new_with_range(0, 59, 1); self.sp_m.set_wrap(True); self.sp_m.add_css_class("timepick")
        for sp in (self.sp_h, self.sp_m):
            sp.connect("output", lambda s: (s.set_text(f"{int(s.get_value()):02d}"), True)[1])
        colon = Gtk.Label(label=":"); colon.add_css_class("timelab")
        tspin.append(self.sp_h); tspin.append(colon); tspin.append(self.sp_m)
        box.append(tspin)
        tbtns = Gtk.Box(spacing=6); tbtns.set_halign(Gtk.Align.CENTER)
        tclr = Gtk.Button(label="Xóa giờ"); tclr.add_css_class("flat"); tclr.add_css_class("dlgflat")
        tok = Gtk.Button(label="Xong"); tok.add_css_class("dlgbtn")
        tbtns.append(tclr); tbtns.append(tok)
        box.append(tbtns)
        pop = Gtk.Popover(); pop.set_child(box)
        b.set_popover(pop)
        tclr.connect("clicked", lambda *_: (self._set_time(""), pop.popdown(), self._save_schedule()))
        tok.connect("clicked", lambda *_: (self._set_time(f"{int(self.sp_h.get_value()):02d}:{int(self.sp_m.get_value()):02d}"),
                                           pop.popdown(), self._save_schedule()))
        pop.connect("map", lambda *_: self._sync_time())
        return b

    def _sync_cal(self, cal, iso):
        try: d = date.fromisoformat(iso) if iso else today_()
        except Exception: d = today_()
        cal.select_day(GLib.DateTime.new_local(d.year, d.month, d.day, 0, 0, 0))

    def _sync_time(self):
        h, m = 9, 0
        if self._time_hm:
            try: h, m = map(int, self._time_hm.split(":"))
            except Exception: pass
        self.sp_h.set_value(h); self.sp_m.set_value(m)

    def _set_date(self, iso):
        self._date_iso = iso or ""
        self._sync_date_btn()

    def _set_time(self, hm):
        self._time_hm = hm or ""
        self._sync_time_btn()

    def _set_start(self, iso):
        self._start_iso = iso or ""
        self._sync_start_btn()

    def _sync_date_btn(self):
        if self._date_iso:
            try:
                d = date.fromisoformat(self._date_iso)
                self.b_date.set_label(f"📅 {d.strftime('%d/%m/%Y')}")
                return
            except Exception: pass
        self.b_date.set_label("📅 Chọn ngày…")

    def _sync_time_btn(self):
        self.b_time.set_label(f"🕐 {self._time_hm}" if self._time_hm else "🕐 Chọn giờ…")

    def _sync_start_btn(self):
        if self._start_iso:
            try:
                d = date.fromisoformat(self._start_iso)
                self.b_start.set_label(f"📅 {d.strftime('%d/%m/%Y')}")
                return
            except Exception: pass
        self.b_start.set_label("📅 Chọn ngày…")

    def _on_due_picked(self, cal):
        dt = cal.get_date()
        self._set_date(f"{dt.get_year():04d}-{dt.get_month():02d}-{dt.get_day_of_month():02d}")
        self.b_date.get_popover().popdown()
        self._save_schedule()

    def _on_start_picked(self, cal):
        dt = cal.get_date()
        self._set_start(f"{dt.get_year():04d}-{dt.get_month():02d}-{dt.get_day_of_month():02d}")
        self.b_start.get_popover().popdown()
        self._patch({"start_date": self._start_iso or None})

    def _quick_date(self, iso):
        self._set_date(iso)
        self._save_schedule()

    def _est_value(self):
        try: return int(self.e_est.get_text().strip())
        except Exception: return self.task.get("estimate_min") if self.task else None

    def _save_schedule(self):
        if self._guard or not self.task: return
        msg = self._conflict_msg(self._date_iso, self._time_hm, self._est_value())
        if msg:
            self.win._toast(msg)
            self._date_iso = self.task.get("due_date") or ""
            self._time_hm = self.task.get("due_time") or ""
            self._sync_date_btn(); self._sync_time_btn()
            return
        if (self._date_iso or None) != self.task.get("due_date") or (self._time_hm or None) != self.task.get("due_time"):
            self._patch({"due_date": self._date_iso or None, "due_time": self._time_hm or None})

    # ---------- Lặp / số / chữ ----------
    def _sync_more_btn(self):
        arrow = "▾" if self.more_box.get_visible() else "▸"
        self.more_btn.set_label(f"{arrow} Chi tiết khác — bắt đầu · lặp · người làm · nhãn · đánh giá")

    def _toggle_more(self, *_):
        self.more_box.set_visible(not self.more_box.get_visible())
        self._sync_more_btn()

    def _sync_repeat_ui(self):
        sel = self.d_repeat.get_selected()
        self.wd_field.set_visible(sel == 4)
        self.left_field.set_visible(sel != 0)

    def _repeat_value(self):
        sel = self.d_repeat.get_selected()
        if sel == 4:
            wds = sorted(wd for wd, b in self.wd_btns.items() if b.get_active())
            if not wds: return "weekly"
            return "wd:" + ",".join(str(w) for w in wds)
        return ["none", "daily", "weekly", "monthly"][sel]

    def _save_repeat(self):
        if self._guard or not self.task: return
        txt = self.e_left.get_text().strip()
        left = None
        if txt:
            try: left = max(0, int(txt))
            except ValueError: left = None
        self._patch({"repeat_rule": self._repeat_value(), "repeat_left": left})

    def _save_est(self, *_):
        if self._guard or not self.task: return
        txt = self.e_est.get_text().strip()
        val = None
        if txt:
            try: val = int(txt)
            except ValueError: return
        if val == self.task.get("estimate_min"): return
        msg = self._conflict_msg(self._date_iso, self._time_hm, val)
        if msg:
            self.win._toast(msg)
            self.e_est.set_text(str(self.task.get("estimate_min") or "")); return
        self._patch({"estimate_min": val})

    def _save_rem(self, *_):
        if self._guard or not self.task: return
        try: val = int(self.e_rem.get_text().strip())
        except ValueError: return
        if val != self.task.get("remind_before", 30): self._patch({"remind_before": val})

    def _save_assignee(self, *_):
        if self._guard or not self.task: return
        val = self.e_assignee.get_text().strip() or None
        if val != self.task.get("assignee"): self._patch({"assignee": val})

    def _save_tags(self, *_):
        if self._guard or not self.task: return
        val = [s.strip() for s in self.e_tags.get_text().split(",") if s.strip()]
        if val != (self.task.get("tags") or []): self._patch({"tags": val})

    def _save_notes(self):
        if self._guard or not self.task: return
        buf = self.tv_notes.get_buffer()
        val = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), True)
        if val != (self.task.get("notes") or ""): self._patch({"notes": val})

    # ---------- Đồng hồ bấm giờ ----------
    def _sync_timer_ui(self):
        t = self.task or {}
        run = t.get("timer_start")
        txt = f"Đã làm thật: {t.get('actual_min') or 0} phút"
        if run:
            try:
                el = int((datetime.now() - datetime.fromisoformat(run)).total_seconds() // 60)
                txt += f" · ⏱ đang chạy (+{el} phút)"
            except Exception:
                txt += " · ⏱ đang chạy"
        self.timer_lab.set_text(txt)
        self.timer_btn.set_label("⏸ Dừng" if run else "▶ Bấm giờ")

    def _toggle_timer(self, *_):
        run = (self.task or {}).get("timer_start")
        try:
            r = api("POST", f"/api/tasks/{self.task['id']}/timer",
                    {"action": "stop" if run else "start"})
            self.task = r["task"]
        except Exception as e:
            self.err_lab.set_text(f"Đồng hồ lỗi: {e}"); self.err_lab.set_visible(True)
            return
        self._sync_timer_ui()
        self.win.refresh()

    # ---------- Việc con ----------
    def _sub_row(self, text, done, desc="", desc_key="desc", focus=False):
        # Sinh (2026-11-19): việc con KHÔNG cần ô mô tả — chỉ một dòng
        # tên + tick xong. Mô tả cũ (nếu có) vẫn được GIỮ NGUYÊN trong
        # dữ liệu qua _desc_text/_desc_key, chỉ là không còn ô để sửa.
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        row = Gtk.Box(spacing=6)
        chk = Gtk.CheckButton(); chk.set_active(done); chk.set_valign(Gtk.Align.CENTER)
        chk.connect("toggled", lambda *_: self._save_subs())
        ent = Gtk.Entry(); ent.set_text(text); ent.set_hexpand(True)
        ent.set_placeholder_text("Tên việc con…")
        ent.connect("activate", lambda *_: self._save_subs())
        self._leave(ent, self._save_subs)
        rm = Gtk.Button(label="✕"); rm.add_css_class("mini"); rm.add_css_class("flat")
        rm.connect("clicked", lambda *_: (self.sub_rows.remove(outer), self._save_subs()))
        row.append(chk); row.append(ent); row.append(rm)
        outer.append(row)
        outer._chk, outer._ent = chk, ent
        outer._desc_text, outer._desc_key = desc or "", desc_key
        self.sub_rows.append(outer)
        if focus: ent.grab_focus()

    def _collect_subtasks(self):
        out = []
        for row in _kids(self.sub_rows):
            t = row._ent.get_text().strip()
            if t:
                item = {"t": t, "done": row._chk.get_active()}
                d = getattr(row, "_desc_text", "")
                if d: item[getattr(row, "_desc_key", "desc")] = d
                out.append(item)
        return out

    def _save_subs(self):
        if self._guard or not self.task: return
        subs = self._collect_subtasks()
        if subs != (self.task.get("subtasks") or []):
            self._patch({"subtasks": subs})
            self.sub_head.set_text(f"VIỆC CON · {sum(1 for s in subs if s.get('done'))}/{len(subs)}")

    # ---------- Bình luận ----------
    def _set_rating(self, n):
        if not self.task: return
        new = 0 if (self.task.get("rating") or 0) == n else n
        self._patch({"rating": new})
        for i, b in enumerate(self._star_btns, 1):
            b.set_label("★" if new >= i else "☆")
            (b.add_css_class if new >= i else b.remove_css_class)("on")
        self.win.refresh()

    def _on_verdict(self, *_):
        if self._guard or not self.task: return
        v = ["", "approved", "redo"][self.d_verdict.get_selected()]
        if v != (self.task.get("verdict") or ""):
            self._patch({"verdict": v})
            self.win.refresh()

    def _load_comments(self):
        for c in _kids(self.cmt_list): self.cmt_list.remove(c)
        try: rows = api("GET", f"/api/tasks/{self.task['id']}/comments")["comments"]
        except Exception: rows = []
        try: atts = api("GET", f"/api/tasks/{self.task['id']}/attachments")["attachments"]
        except Exception: atts = []
        by_cmt = {}
        for a in atts:
            if a.get("comment_id"): by_cmt.setdefault(a["comment_id"], []).append(a)
        if not rows:
            self.cmt_list.append(Gtk.Label(label="Chưa có bình luận nào.", xalign=0, css_classes=["mut"]))
            return
        for cm in rows:
            vb = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            hr = Gtk.Box(spacing=8)
            au = Gtk.Label(label=cm.get("author") or "Bạn", xalign=0); au.add_css_class("cmtau")
            hr.append(au)
            when = cm.get("created_at") or ""
            wl = Gtk.Label(label=(when[8:10] + "/" + when[5:7] + " " + when[11:16]) if len(when) >= 16 else "",
                           css_classes=["mut"])
            hr.append(wl)
            sp = Gtk.Box(); sp.set_hexpand(True); hr.append(sp)
            dl = Gtk.Button(label="🗑"); dl.add_css_class("mini"); dl.add_css_class("flat")
            dl.set_tooltip_text("Xoá bình luận này")
            dl.connect("clicked", lambda *_ , cid=cm["id"]: self._del_comment(cid))
            hr.append(dl)
            vb.append(hr)
            tx = Gtk.Label(label=cm.get("content") or "", xalign=0, wrap=True); tx.add_css_class("cmttext")
            vb.append(tx)
            for a in by_cmt.get(cm["id"], []):
                vb.append(self._cmt_attachment_widget(a))
            self.cmt_list.append(vb)

    def _cmt_attachment_widget(self, a):
        import os.path as _p
        ext = _p.splitext(a["filename"])[1].lower()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        if ext in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"):
            try:
                cache = os.path.join(GLib.get_tmp_dir(), "shini-cmt-media")
                os.makedirs(cache, exist_ok=True)
                path = os.path.join(cache, f"{a['id']}_{a['filename']}")
                if not os.path.exists(path):
                    open(path, "wb").write(api_raw(f"/api/attachments/{a['id']}/download"))
                pic = Gtk.Picture.new_for_filename(path)
                pic.set_content_fit(Gtk.ContentFit.CONTAIN)
                pic.set_size_request(210, 140); pic.set_halign(Gtk.Align.START)
                box.append(pic)
            except Exception: pass
        row = Gtk.Box(spacing=6)
        icon = "🎬" if ext in (".mp4", ".mov", ".webm", ".mkv") else "📄"
        nm = Gtk.Label(label=f"{icon} {a['filename']}", xalign=0); nm.set_hexpand(True)
        nm.set_ellipsize(Pango.EllipsizeMode.END)
        row.append(nm)
        dl = Gtk.Button(label="⬇ Tải"); dl.add_css_class("mini"); dl.add_css_class("flat")
        dl.connect("clicked", lambda *_ , aa=a: self._download_attachment(aa))
        row.append(dl)
        rm = Gtk.Button(label="✕"); rm.add_css_class("mini"); rm.add_css_class("flat")
        rm.connect("clicked", lambda *_ , aid=a["id"]: self._del_cmt_attachment(aid))
        row.append(rm)
        box.append(row)
        return box

    def _del_cmt_attachment(self, aid):
        try: api("DELETE", f"/api/attachments/{aid}")
        except Exception: return
        self._load_comments(); self._load_attachments(); self.win.refresh()

    def _pick_cmt_file(self, *_):
        dlg = Gtk.FileDialog(title="Chọn file gắn vào bình luận")
        dlg.open(self.win, None, self._cmt_file_chosen)

    def _cmt_file_chosen(self, dlg, res):
        try: f = dlg.open_finish(res)
        except Exception: return
        path = f.get_path()
        if path: self._stage_cmt_file(path)

    def _stage_cmt_file(self, path):
        self._cmt_file = path
        if path:
            self.cmt_file_lab.set_text("📎 " + os.path.basename(path) + " — sẽ gửi cùng bình luận")
            self.cmt_file_row.set_visible(True)
        else:
            self.cmt_file_row.set_visible(False)

    def _add_comment(self, *_):
        txt = self.e_cmt.get_text().strip()
        if not txt and not self._cmt_file: return
        if not txt: txt = "📎 File đính kèm"
        try:
            r = api("POST", f"/api/tasks/{self.task['id']}/comments",
                    {"author": SETTINGS.get("display_name") or "Bạn", "content": txt})
        except Exception: return
        cm = (r or {}).get("comment") or {}
        if self._cmt_file and cm.get("id"):
            try:
                import base64
                data = open(self._cmt_file, "rb").read()
                api("POST", f"/api/tasks/{self.task['id']}/attachments",
                    {"filename": os.path.basename(self._cmt_file),
                     "data_b64": base64.b64encode(data).decode(),
                     "comment_id": cm["id"]})
            except Exception: pass
        self._stage_cmt_file(None)
        self.e_cmt.set_text("")
        self._load_comments(); self.win.refresh()

    def _del_comment(self, cid):
        try: api("DELETE", f"/api/comments/{cid}")
        except Exception: return
        self._load_comments(); self.win.refresh()

    # ---------- File đính kèm ----------
    def _load_attachments(self):
        for c in _kids(self.att_list): self.att_list.remove(c)
        try: rows = api("GET", f"/api/tasks/{self.task['id']}/attachments")["attachments"]
        except Exception: rows = []
        rows = [a for a in rows if not a.get("comment_id")]
        if not rows:
            self.att_list.append(Gtk.Label(label="Chưa có file nào.", xalign=0, css_classes=["mut"]))
            return
        for a in rows:
            row = Gtk.Box(spacing=8)
            nm = Gtk.Label(label="📄 " + a["filename"], xalign=0); nm.set_hexpand(True)
            nm.set_ellipsize(Pango.EllipsizeMode.END)
            row.append(nm)
            sz = a.get("size") or 0
            row.append(Gtk.Label(label=(f"{sz / 1024:.0f} KB" if sz < 1024 * 1024 else f"{sz / 1024 / 1024:.1f} MB"),
                                 css_classes=["mut"]))
            dl = Gtk.Button(label="⬇ Tải"); dl.add_css_class("mini"); dl.add_css_class("flat")
            dl.connect("clicked", lambda *_ , aa=a: self._download_attachment(aa))
            row.append(dl)
            rm = Gtk.Button(label="✕"); rm.add_css_class("mini"); rm.add_css_class("flat")
            rm.connect("clicked", lambda *_ , aid=a["id"]: self._del_attachment(aid))
            row.append(rm)
            self.att_list.append(row)

    def _pick_attachment(self, *_):
        dlg = Gtk.FileDialog(title="Chọn file đính kèm")
        dlg.open(self.win, None, self._attachment_chosen)

    def _attachment_chosen(self, dlg, res):
        try: f = dlg.open_finish(res)
        except Exception: return
        path = f.get_path()
        if not path: return
        try: data = open(path, "rb").read()
        except Exception: return
        if len(data) > 25 * 1024 * 1024:
            self.err_lab.set_text("⚠ File quá 25 MB — hãy chọn file nhỏ hơn.")
            self.err_lab.set_visible(True); return
        import base64
        try:
            api("POST", f"/api/tasks/{self.task['id']}/attachments",
                {"filename": os.path.basename(path), "data_b64": base64.b64encode(data).decode()})
        except Exception: return
        self._load_attachments(); self.win.refresh()

    def _download_attachment(self, a):
        dlg = Gtk.FileDialog(title="Lưu file về máy")
        dlg.set_initial_name(a["filename"])
        dlg.save(self.win, None, lambda d, r: self._attachment_save(d, r, a))

    def _attachment_save(self, dlg, res, a):
        try: f = dlg.save_finish(res)
        except Exception: return
        path = f.get_path()
        if not path: return
        try:
            data = api_raw(f"/api/attachments/{a['id']}/download")
            open(path, "wb").write(data)
        except Exception: pass

    def _del_attachment(self, aid):
        try: api("DELETE", f"/api/attachments/{aid}")
        except Exception: return
        self._load_attachments(); self.win.refresh()



class ArchivedProjectsDialog(Gtk.Window):
    """Dự án đã lưu trữ (gói Coogo v1.6.0): xem danh sách + khôi phục.
    Lưu trữ chỉ ẩn dự án khỏi thanh bên — việc và dữ liệu giữ nguyên."""

    def __init__(self, parent, on_changed):
        super().__init__(title="Dự án đã lưu trữ", transient_for=parent, modal=True)
        self.win, self.on_changed = parent, on_changed
        self.set_default_size(420, -1)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_top(16); box.set_margin_bottom(16)
        box.set_margin_start(16); box.set_margin_end(16)
        box.append(Gtk.Label(label="Dự án đã lưu trữ chỉ bị ẩn khỏi thanh bên — "
                                   "mọi việc bên trong vẫn nguyên vẹn.",
                             xalign=0, wrap=True, css_classes=["mut"]))
        self.list_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.append(self.list_box)
        self.set_child(box)
        self._reload()

    def _reload(self):
        for c in _kids(self.list_box): self.list_box.remove(c)
        arch = [p for p in self.win.projects if p.get("archived")]
        if not arch:
            self.list_box.append(Gtk.Label(label="Chưa có dự án nào được lưu trữ.",
                                           xalign=0, css_classes=["mut"]))
            return
        for p in arch:
            row = Gtk.Box(spacing=8)
            lab = Gtk.Label(label="📦 " + p["name"], xalign=0); lab.set_hexpand(True)
            row.append(lab)
            b = Gtk.Button(label="↩ Khôi phục"); b.add_css_class("dlgbtn")
            b.connect("clicked", lambda *_ , pp=p: self._restore(pp))
            row.append(b)
            self.list_box.append(row)

    def _restore(self, p):
        try: api("PATCH", f"/api/projects/{p['id']}", {"archived": 0})
        except Exception: return
        self.on_changed()
        self._reload()


class WelcomeDialog(Gtk.Window):
    """Hướng dẫn nhanh (gói B audit 2026-11-17): tự hiện ở lần mở đầu
    tiên, mở lại ở chân thanh bên → ❓ Hướng dẫn sử dụng. Mục tiêu: người
    mới tự khám phá được các 'phép thuật' vốn ẩn của app (Alt+E, cú pháp
    gõ tắt, thông báo có nút bấm...) mà không cần ai chỉ."""

    SECTIONS = [
        ("⚡ BẮT VIỆC SIÊU NHANH",
         "• Bấm Alt+E ở BẤT KỲ đâu trên máy (hoặc nút ⚡ trên thanh tiêu đề): cửa sổ bắt việc hiện lên, "
         "gõ xong Enter là lưu, Esc là đóng. Dán nhiều dòng = mỗi dòng một việc.\n"
         "• Ô 'Thêm nhanh' trên bảng hiểu cú pháp gõ tắt, ví dụ:  mai 9h họp team !gấp #work 30p mỗi T2 T4\n"
         "   (! = mức ưu tiên, # = nhãn, 30p = ước lượng, 'mỗi…' = lặp lại, 'lặp 12 lần' = tổng số lần)\n"
         "• Có API key Gemini (ở ⚙ Cài đặt) thì bấm ✨ AI: gõ một câu tự nhiên, AI tự điền mọi trường."),
        ("🗂 LÀM VIỆC HẰNG NGÀY",
         "• Bấm vào thẻ để mở chi tiết: mọi thay đổi tự lưu ngay; có việc con, bình luận, file đính kèm, bấm giờ thật.\n"
         "• Kéo thẻ sang cột khác, thả vào cột ĐÃ XONG để hoàn thành; kéo lên Lịch để xếp giờ. "
         "Mọi thao tác lỡ tay đều có nút Hoàn tác ở thông báo nhỏ góc dưới.\n"
         "• 6 màn hình: Bảng · Danh sách · Lịch (Ngày/Tuần/Tháng) · Hôm nay · Sơ đồ · Thống kê. "
         "Ctrl+N việc mới · Ctrl+F/Ctrl+K tìm · Ctrl+B ẩn thanh bên."),
        ("🔔 NHẮC VIỆC",
         "• Đến gần hạn, thông báo trên máy hiện KÈM NÚT BẤM: hoãn nhắc, dời sang mai, đánh dấu xong — "
         "xử lý luôn khỏi mở app.\n"
         "• Muốn nhắc về điện thoại: nối Telegram trong ⚙ Cài đặt (tạo bot qua @BotFather, mất ~2 phút). "
         "Bản tin tổng hợp tự gửi lúc 07:30 và 20:30 mỗi ngày."),
        ("📱 TỪ ĐIỆN THOẠI & MÁY KHÁC",
         "• iPhone: tạo Shortcut theo file HUONG-DAN-DIEN-THOAI.md (trong thư mục app) để ghi việc từ xa qua Tailscale.\n"
         "• Hai máy tính chạy Shini Tasks đồng bộ hai chiều được: mở ⇄ Đồng bộ ở chân thanh bên, "
         "dán địa chỉ + token của máy kia."),
        ("🛡 DỮ LIỆU CỦA BẠN",
         "• Mọi thứ nằm trên máy của bạn, không tài khoản, không đám mây. Engine tự sao lưu mỗi ngày "
         "(giữ 14 bản), việc xoá vào thùng rác 30 ngày, việc xong quá 15 ngày được lưu trữ cho thống kê.\n"
         "• API có token bảo vệ: máy lạ cùng mạng không đọc/sửa được dữ liệu (token ở ⚙ Cài đặt)."),
    ]

    def __init__(self, parent):
        super().__init__(title="Hướng dẫn sử dụng — Shini Tasks", transient_for=parent, modal=True)
        self.set_default_size(560, 640)
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        scroll = Gtk.ScrolledWindow(); scroll.set_vexpand(True)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(16); box.set_margin_bottom(16)
        box.set_margin_start(18); box.set_margin_end(18)
        box.append(Gtk.Label(label="Chào mừng bạn đến với Shini Tasks 👋", xalign=0, css_classes=["pane-h"]))
        box.append(Gtk.Label(label="App quản lý việc cá nhân chạy ngay trên máy của bạn. "
                                   "Năm ý dưới đây là mọi thứ cần biết để dùng thạo:",
                             xalign=0, wrap=True, css_classes=["mut"]))
        for head, body in self.SECTIONS:
            box.append(Gtk.Label(label=head, xalign=0, css_classes=["pane-h"]))
            box.append(Gtk.Label(label=body, xalign=0, wrap=True, css_classes=["mut"]))
        scroll.set_child(box)
        outer.append(scroll)
        ok = Gtk.Button(label="Đã hiểu, bắt đầu thôi"); ok.add_css_class("suggested-action")
        ok.set_margin_top(10); ok.set_margin_bottom(12); ok.set_margin_start(18); ok.set_margin_end(18)
        ok.connect("clicked", lambda *_: self.close())
        outer.append(ok)
        self.set_child(outer)


class SettingsDialog(Gtk.Window):
    """Cài đặt (gói Coogo v1.6.0): thông báo Telegram về điện thoại của chính
    người dùng + API key Gemini cho nút ✨ AI điền form. Token/key chỉ lưu
    trên máy này (Telegram token nằm ở engine local, Gemini key ở settings)."""

    def __init__(self, parent):
        super().__init__(title="Cài đặt — Telegram & AI", transient_for=parent, modal=True)
        self.win = parent
        self.set_default_size(480, -1)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_margin_top(16); box.set_margin_bottom(16)
        box.set_margin_start(16); box.set_margin_end(16)
        box.append(Gtk.Label(label="NHẮC VIỆC", xalign=0, css_classes=["pane-h"]))
        box.append(Gtk.Label(label="Nhắc trước hạn áp dụng cho việc MỚI tạo (việc cũ giữ nguyên số đã đặt "
                                   "trong chi tiết). Hoãn nhắc là thời gian im lặng khi bấm nút "
                                   "'Nhắc lại sau' trên thông báo.",
                             xalign=0, wrap=True, css_classes=["mut"]))
        rrow = Gtk.Box(spacing=8)
        rrow.append(Gtk.Label(label="Nhắc trước (phút):", css_classes=["mut"]))
        self.sp_remind = Gtk.SpinButton.new_with_range(0, 1440, 5)
        self.sp_remind.set_value(30)
        rrow.append(self.sp_remind)
        rrow.append(Gtk.Label(label="Hoãn nhắc (phút):", css_classes=["mut"]))
        self.sp_snooze = Gtk.SpinButton.new_with_range(1, 240, 1)
        self.sp_snooze.set_value(15)
        rrow.append(self.sp_snooze)
        brem = Gtk.Button(label="Lưu"); brem.add_css_class("dlgbtn")
        brem.connect("clicked", self._save_remind)
        rrow.append(brem)
        self.rem_result = Gtk.Label(label="", xalign=0, css_classes=["mut"])
        rrow.append(self.rem_result)
        box.append(rrow)
        box.append(Gtk.Label(label="TELEGRAM — NHẮC VIỆC VỀ ĐIỆN THOẠI", xalign=0, css_classes=["pane-h"]))
        box.append(Gtk.Label(label="Cách nối: mở Telegram → tìm @BotFather → /newbot để tạo bot, "
                                   "copy token dán vào đây. Nhắn cho bot 1 tin bất kỳ, rồi mở "
                                   "@userinfobot để lấy Chat ID của bạn. Nhắc việc, quá hạn và "
                                   "bản tin sáng/tối sẽ về Telegram (kèm thông báo trên máy như cũ).",
                             xalign=0, wrap=True, css_classes=["mut"]))
        self.tg_status = Gtk.Label(label="", xalign=0, css_classes=["mut"])
        box.append(self.tg_status)
        self.e_tg_token = Gtk.Entry(placeholder_text="Token bot Telegram…")
        self.e_tg_token.set_visibility(False)
        box.append(self.e_tg_token)
        self.e_tg_chat = Gtk.Entry(placeholder_text="Chat ID của bạn (vd 123456789)…")
        box.append(self.e_tg_chat)
        trow = Gtk.Box(spacing=8)
        bsave = Gtk.Button(label="Lưu Telegram"); bsave.add_css_class("dlgbtn")
        bsave.connect("clicked", self._save_tg)
        trow.append(bsave)
        btest = Gtk.Button(label="Gửi thử"); btest.add_css_class("dlgbtn")
        btest.connect("clicked", self._test_tg)
        trow.append(btest)
        self.tg_result = Gtk.Label(label="", xalign=0, css_classes=["mut"])
        trow.append(self.tg_result)
        box.append(trow)
        box.append(Gtk.Label(label="AI GEMINI — NÚT ✨ ĐIỀN FORM", xalign=0, css_classes=["pane-h"]))
        box.append(Gtk.Label(label="Tạo API key miễn phí tại aistudio.google.com/apikey rồi dán vào đây. "
                                   "Có key rồi, ở ô Thêm nhanh cứ gõ một câu tiếng Việt tự nhiên và "
                                   "bấm ✨ AI — AI sẽ tự điền tiêu đề, hạn, giờ, ưu tiên, nhãn và gợi ý việc con.",
                             xalign=0, wrap=True, css_classes=["mut"]))
        self.e_gem = Gtk.Entry(placeholder_text="Gemini API key…")
        self.e_gem.set_visibility(False)
        self.e_gem.set_text(SETTINGS.get("gemini_key") or "")
        box.append(self.e_gem)
        brow = Gtk.Box(spacing=8)
        bgem = Gtk.Button(label="Lưu key AI"); bgem.add_css_class("dlgbtn")
        bgem.connect("clicked", self._save_gem)
        brow.append(bgem)
        self.gem_result = Gtk.Label(label="", xalign=0, css_classes=["mut"])
        brow.append(self.gem_result)
        box.append(brow)
        box.append(Gtk.Label(label="TOKEN API — BẢO VỆ DỮ LIỆU", xalign=0, css_classes=["pane-h"]))
        box.append(Gtk.Label(label="Mọi yêu cầu tới engine đều phải kèm token này, nên máy lạ cùng "
                                   "mạng không đọc hay sửa được việc của bạn. App trên máy này tự "
                                   "dùng token, bạn chỉ cần tới nó khi: ghi việc từ điện thoại (thêm "
                                   "header X-Token vào Shortcut) hoặc đồng bộ với máy kia (dán vào ô "
                                   "Token trong hộp Đồng bộ ở máy kia).",
                             xalign=0, wrap=True, css_classes=["mut"]))
        _tok = _read_api_token()
        krow = Gtk.Box(spacing=8)
        krow.append(Gtk.Label(label=f"Token hiện tại: ••••{_tok[-4:]}" if _tok else "Engine chưa sinh token",
                              css_classes=["mut"]))
        bcopy = Gtk.Button(label="Sao chép token"); bcopy.add_css_class("dlgbtn")
        bcopy.connect("clicked", self._copy_token)
        krow.append(bcopy)
        self.tok_result = Gtk.Label(label="", xalign=0, css_classes=["mut"])
        krow.append(self.tok_result)
        box.append(krow)
        box.append(Gtk.Label(label="QUẢN LÝ & DỮ LIỆU — MỞ NHANH", xalign=0, css_classes=["pane-h"]))
        box.append(Gtk.Label(label="Các công cụ này cũng nằm ở chân thanh bên — gom thêm tại đây "
                                   "để mọi cài đặt ở một chỗ.",
                             xalign=0, wrap=True, css_classes=["mut"]))
        hrow = Gtk.Box(spacing=8)
        for _label, _cls in [("🗑 Thùng rác", TrashDialog), ("🏷 Quản lý nhãn", TagsDialog),
                             ("✎ Tên mức ưu tiên", LabelsDialog), ("⇄ Đồng bộ · Sao lưu", SyncDialog)]:
            _b = Gtk.Button(label=_label); _b.add_css_class("dlgbtn")
            _b.connect("clicked", lambda *_ , c=_cls: c(self.win, self.win.refresh).present())
            hrow.append(_b)
        box.append(hrow)
        self.set_child(box)
        self._load_tg()

    def _save_remind(self, *_):
        try:
            api("POST", "/api/notify-config",
                {"remind_default": int(self.sp_remind.get_value()),
                 "snooze_min": int(self.sp_snooze.get_value())})
            self.rem_result.set_text("Đã lưu ✓")
        except Exception:
            self.rem_result.set_text("Lưu không được — engine chưa chạy?")

    def _copy_token(self, *_):
        tok = _read_api_token()
        if not tok:
            self.tok_result.set_text("Chưa có token — engine chưa chạy?")
            return
        disp = Gdk.Display.get_default()
        if disp is not None:
            disp.get_clipboard().set_content(Gdk.ContentProvider.new_for_value(tok))
        self.tok_result.set_text("Đã sao chép ✓")

    def _load_tg(self):
        try: cfg = api("GET", "/api/notify-config")
        except Exception: cfg = {}
        try:
            self.sp_remind.set_value(cfg.get("remind_default", 30))
            self.sp_snooze.set_value(cfg.get("snooze_min", 15))
        except Exception: pass
        self.e_tg_chat.set_text(cfg.get("telegram_chat") or "")
        if cfg.get("telegram_token_set"):
            self.tg_status.set_text(f"Đã nối Telegram (token ••••{cfg.get('telegram_token_tail', '')}). "
                                    "Để trống ô token nếu giữ nguyên.")
        else:
            self.tg_status.set_text("Chưa cấu hình Telegram.")

    def _save_tg(self, *_):
        body = {"telegram_chat": self.e_tg_chat.get_text().strip()}
        tok = self.e_tg_token.get_text().strip()
        if tok: body["telegram_token"] = tok
        try:
            api("POST", "/api/notify-config", body)
            self.tg_result.set_text("Đã lưu ✓")
            self._load_tg()
        except Exception:
            self.tg_result.set_text("Lưu không được — engine chưa chạy?")

    def _test_tg(self, *_):
        self._save_tg()
        try:
            r = api("POST", "/api/notify-test")
            self.tg_result.set_text("Đã gửi tin thử ✓ — xem Telegram" if r.get("ok") else "Gửi chưa được")
        except Exception as e:
            self.tg_result.set_text("Gửi chưa được — kiểm tra token/chat id")

    def _save_gem(self, *_):
        SETTINGS["gemini_key"] = self.e_gem.get_text().strip()
        save_settings(SETTINGS)
        self.gem_result.set_text("Đã lưu key ✓")


class ColumnDialog(Gtk.Window):
    """Thêm cột mới hoặc đổi tên/màu cột có sẵn."""
    def __init__(self, parent, column, on_saved):
        super().__init__(title="Đổi tên & màu cột" if column else "Thêm cột mới",
                         transient_for=parent, modal=True)
        self.column, self.on_saved = column, on_saved
        self.color = (column or {}).get("color", PALETTE[4])
        self.set_default_size(380, -1)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(16); box.set_margin_bottom(16); box.set_margin_start(16); box.set_margin_end(16)
        self.e_name = Gtk.Entry(placeholder_text="Tên cột, ví dụ: Dự án A, Việc nhà…")
        if column: self.e_name.set_text(column["name"])
        box.append(self.e_name)
        box.append(Gtk.Label(label="Màu cột", xalign=0, css_classes=["mut"]))
        prow = Gtk.Box(spacing=8)
        self.color_btns = {}
        for hexv in PALETTE:
            b = Gtk.ToggleButton()
            dot = Gtk.Box(); dot.set_size_request(20, 20); dot.add_css_class("coldot")
            prov = Gtk.CssProvider()
            css_load(prov, f".pick-{hexv[1:]} {{ background: {hexv}; }}".encode())
            dot.add_css_class(f"pick-{hexv[1:]}")
            Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), prov, Gtk.STYLE_PROVIDER_PRIORITY_USER - 1)
            b.set_child(dot)
            b.set_active(hexv == self.color)
            b.connect("toggled", lambda btn, h=hexv: self._pick(btn, h))
            self.color_btns[hexv] = b
            prow.append(b)
        box.append(prow)
        brow = Gtk.Box(spacing=8); brow.set_halign(Gtk.Align.END)
        cancel = Gtk.Button(label="Hủy"); cancel.add_css_class("dlgbtn"); cancel.connect("clicked", lambda *_: self.close())
        save = Gtk.Button(label="Lưu cột"); save.add_css_class("suggested-action")
        save.connect("clicked", self._save)
        brow.append(cancel); brow.append(save)
        box.append(brow)
        self.set_child(box)

    def _pick(self, btn, hexv):
        if btn.get_active():
            self.color = hexv
            for h, b in self.color_btns.items():
                if h != hexv: b.set_active(False)

    def _save(self, *_):
        name = self.e_name.get_text().strip()
        if not name: return
        try:
            if self.column: api("PATCH", f"/api/columns/{self.column['id']}", {"name": name, "color": self.color})
            else: api("POST", "/api/columns", {"name": name, "color": self.color,
                      "project_id": getattr(self.get_transient_for(), "cur_project", None)})
        except Exception as e: print("column save error:", e)
        self.on_saved(); self.close()

class ConfirmDialog(Gtk.Window):
    def __init__(self, parent, title, body, ok_label, on_ok):
        super().__init__(title=title, transient_for=parent, modal=True)
        self.on_ok = on_ok
        self.set_default_size(400, -1)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(16); box.set_margin_bottom(16); box.set_margin_start(16); box.set_margin_end(16)
        l = Gtk.Label(label=body, xalign=0, wrap=True)
        box.append(l)
        brow = Gtk.Box(spacing=8); brow.set_halign(Gtk.Align.END)
        cancel = Gtk.Button(label="Hủy"); cancel.add_css_class("dlgbtn"); cancel.connect("clicked", lambda *_: self.close())
        ok = Gtk.Button(label=ok_label); ok.add_css_class("destructive-action")
        ok.connect("clicked", self._ok)
        brow.append(cancel); brow.append(ok)
        box.append(brow)
        self.set_child(box)
    def _ok(self, *_):
        self.on_ok(); self.close()

class ProjectDialog(Gtk.Window):
    """Thêm dự án mới hoặc đổi tên/màu dự án (kiểu KimesFlow: mỗi dự án một
    bảng cột riêng). Dự án mới được engine cấp sẵn 3 cột mặc định."""
    def __init__(self, parent, project, on_saved):
        super().__init__(title="Đổi tên & màu dự án" if project else "Thêm dự án mới",
                         transient_for=parent, modal=True)
        self.project, self.on_saved = project, on_saved
        self.color = (project or {}).get("color", PALETTE[4])
        self.set_default_size(380, -1)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(16); box.set_margin_bottom(16); box.set_margin_start(16); box.set_margin_end(16)
        self.e_name = Gtk.Entry(placeholder_text="Tên dự án, ví dụ: Việc công ty, Học tập…")
        if project: self.e_name.set_text(project["name"])
        self.e_name.connect("activate", self._save)
        box.append(self.e_name)
        box.append(Gtk.Label(label="Màu dự án", xalign=0, css_classes=["mut"]))
        prow = Gtk.Box(spacing=8)
        self.color_btns = {}
        for hexv in PALETTE:
            b = Gtk.ToggleButton()
            dot = Gtk.Box(); dot.set_size_request(20, 20); dot.add_css_class("coldot")
            prov = Gtk.CssProvider()
            css_load(prov, f".pick-{hexv[1:]} {{ background: {hexv}; }}".encode())
            dot.add_css_class(f"pick-{hexv[1:]}")
            Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), prov, Gtk.STYLE_PROVIDER_PRIORITY_USER - 1)
            b.set_child(dot)
            b.set_active(hexv == self.color)
            b.connect("toggled", lambda btn, h=hexv: self._pick(btn, h))
            self.color_btns[hexv] = b
            prow.append(b)
        box.append(prow)
        brow = Gtk.Box(spacing=8); brow.set_halign(Gtk.Align.END)
        cancel = Gtk.Button(label="Hủy"); cancel.add_css_class("dlgbtn"); cancel.connect("clicked", lambda *_: self.close())
        save = Gtk.Button(label="Lưu dự án"); save.add_css_class("suggested-action")
        save.connect("clicked", self._save)
        brow.append(cancel); brow.append(save)
        box.append(brow)
        self.set_child(box)

    def _pick(self, btn, hexv):
        if btn.get_active():
            self.color = hexv
            for h, b in self.color_btns.items():
                if h != hexv: b.set_active(False)

    def _save(self, *_):
        name = self.e_name.get_text().strip()
        if not name: return
        try:
            if self.project:
                api("PATCH", f"/api/projects/{self.project['id']}", {"name": name, "color": self.color})
            else:
                api("POST", "/api/projects", {"name": name, "color": self.color})
        except Exception as e: print("project save error:", e)
        self.on_saved(); self.close()

class LabelsDialog(Gtk.Window):
    """Đổi tên 4 mức ưu tiên theo ý Sinh (lưu settings.json)."""
    def __init__(self, parent, on_saved):
        super().__init__(title="Đặt tên mức ưu tiên", transient_for=parent, modal=True)
        self.on_saved = on_saved
        self.set_default_size(400, -1)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_margin_top(16); box.set_margin_bottom(16); box.set_margin_start(16); box.set_margin_end(16)
        hint = Gtk.Label(label="Tên này hiện trên thẻ việc và ở sidebar.\nMức được tính tự động: Gấp + Quan trọng → mức 1, Quan trọng → mức 2, Gấp → mức 3, còn lại → mức 4.",
                         xalign=0, wrap=True, css_classes=["mut"])
        box.append(hint)
        self.entries = {}
        hints = {"L1": "Mức 1 (gấp + quan trọng)", "L2": "Mức 2 (quan trọng)",
                 "L3": "Mức 3 (gấp)", "L4": "Mức 4 (thường)"}
        for lv in ("L1", "L2", "L3", "L4"):
            row = Gtk.Box(spacing=8)
            dot = Gtk.Box(); dot.add_css_class("coldot"); dot.set_size_request(10, 10)
            dot.set_valign(Gtk.Align.CENTER)
            prov = Gtk.CssProvider()
            css_load(prov, f".lvdot-{lv} {{ background: {LEVEL_COLORS[lv]}; }}".encode())
            dot.add_css_class(f"lvdot-{lv}")
            Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), prov, Gtk.STYLE_PROVIDER_PRIORITY_USER - 1)
            row.append(dot)
            e = Gtk.Entry(); e.set_text(SETTINGS["labels"].get(lv, DEFAULT_LABELS[lv]))
            e.set_hexpand(True)
            self.entries[lv] = e
            f = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            f.append(Gtk.Label(label=hints[lv], xalign=0, css_classes=["mut"]))
            f.append(e); f.set_hexpand(True)
            row.append(f)
            box.append(row)
        brow = Gtk.Box(spacing=8); brow.set_halign(Gtk.Align.END)
        reset = Gtk.Button(label="Về mặc định"); reset.add_css_class("dlgbtn")
        reset.connect("clicked", self._reset)
        cancel = Gtk.Button(label="Hủy"); cancel.add_css_class("dlgbtn"); cancel.connect("clicked", lambda *_: self.close())
        save = Gtk.Button(label="Lưu tên"); save.add_css_class("suggested-action")
        save.connect("clicked", self._save)
        brow.append(reset); brow.append(cancel); brow.append(save)
        box.append(brow)
        self.set_child(box)

    def _reset(self, *_):
        for lv, e in self.entries.items(): e.set_text(DEFAULT_LABELS[lv])
    def _save(self, *_):
        for lv, e in self.entries.items():
            v = e.get_text().strip()
            if v: SETTINGS["labels"][lv] = v
        save_settings(SETTINGS)
        self.on_saved(); self.close()


class TrashDialog(Gtk.Window):
    """Thùng rác (v1.4.0): việc đã xoá nằm ở đây 30 ngày — khôi phục được,
    hoặc xoá hẳn ngay. Trước đây xoá là mất luôn, không có đường quay lại."""
    def __init__(self, parent, on_done):
        super().__init__(title="Thùng rác", transient_for=parent, modal=True)
        self.on_done = on_done
        self.set_default_size(520, -1)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_margin_top(16); box.set_margin_bottom(16); box.set_margin_start(16); box.set_margin_end(16)
        box.append(Gtk.Label(label="Việc đã xoá sẽ nằm ở đây 30 ngày rồi tự xoá hẳn. "
                                   "Khôi phục đưa việc về đúng cột/dự án cũ.",
                             xalign=0, wrap=True, css_classes=["mut"]))
        self.list_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.append(self.list_box)
        brow = Gtk.Box(spacing=8); brow.set_halign(Gtk.Align.END)
        empty = Gtk.Button(label="🧹 Dọn sạch thùng rác"); empty.add_css_class("dlgbtn")
        empty.connect("clicked", self._empty_all)
        close = Gtk.Button(label="Đóng"); close.add_css_class("dlgbtn"); close.connect("clicked", lambda *_: self.close())
        brow.append(empty); brow.append(close)
        box.append(brow)
        self.set_child(box)
        self._load()

    def _load(self):
        for c in _kids(self.list_box): self.list_box.remove(c)
        try:
            tasks = api("GET", "/api/tasks?view=trash")["tasks"]
        except Exception as e:
            self.list_box.append(Gtk.Label(label=f"Không đọc được thùng rác: {e}", xalign=0, css_classes=["mut"]))
            return
        if not tasks:
            self.list_box.append(Gtk.Label(label="Thùng rác trống.", xalign=0, css_classes=["mut"]))
            return
        for t in tasks:
            row = Gtk.Box(spacing=8)
            lab = Gtk.Label(label=t["title"], xalign=0); lab.set_hexpand(True)
            lab.set_ellipsize(Pango.EllipsizeMode.END)
            row.append(lab)
            when = (t.get("deleted_at") or "")[:10]
            row.append(Gtk.Label(label=f"xoá {when[8:10]}/{when[5:7]}", css_classes=["mut"]))
            rb = Gtk.Button(label="↩ Khôi phục"); rb.add_css_class("dlgbtn")
            rb.connect("clicked", lambda *_ , tid=t["id"]: self._act("restore", tid))
            db = Gtk.Button(label="Xoá hẳn"); db.add_css_class("dlgbtn")
            db.connect("clicked", lambda *_ , tid=t["id"]: self._act("perm", tid))
            row.append(rb); row.append(db)
            self.list_box.append(row)

    def _act(self, kind, tid):
        try:
            if kind == "restore": api("POST", f"/api/tasks/{tid}/restore")
            else: api("DELETE", f"/api/tasks/{tid}?permanent=1")
        except Exception:
            pass
        self._load(); self.on_done()

    def _empty_all(self, *_):
        try:
            tasks = api("GET", "/api/tasks?view=trash")["tasks"]
            for t in tasks: api("DELETE", f"/api/tasks/{t['id']}?permanent=1")
        except Exception:
            pass
        self._load(); self.on_done()


class TagsDialog(Gtk.Window):
    """Quản lý nhãn (v1.4.0): đổi tên nhãn ở MỌI việc cùng lúc / gỡ nhãn —
    trước đây nhãn gõ sai một chữ là thành nhãn mới, không sửa lại được."""
    def __init__(self, parent, on_done):
        super().__init__(title="Quản lý nhãn", transient_for=parent, modal=True)
        self.on_done = on_done
        self.set_default_size(520, -1)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_margin_top(16); box.set_margin_bottom(16); box.set_margin_start(16); box.set_margin_end(16)
        box.append(Gtk.Label(label="Đổi tên sẽ áp cho mọi việc đang mang nhãn đó. "
                                   "Đổi trùng tên một nhãn khác = gộp hai nhãn làm một.",
                             xalign=0, wrap=True, css_classes=["mut"]))
        self.list_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.append(self.list_box)
        brow = Gtk.Box(spacing=8); brow.set_halign(Gtk.Align.END)
        close = Gtk.Button(label="Đóng"); close.add_css_class("dlgbtn"); close.connect("clicked", lambda *_: self.close())
        brow.append(close); box.append(brow)
        self.set_child(box)
        self._load()

    def _load(self):
        for c in _kids(self.list_box): self.list_box.remove(c)
        try:
            tags = api("GET", "/api/tags")["tags"]
        except Exception as e:
            self.list_box.append(Gtk.Label(label=f"Không đọc được nhãn: {e}", xalign=0, css_classes=["mut"]))
            return
        if not tags:
            self.list_box.append(Gtk.Label(label="Chưa có nhãn nào.", xalign=0, css_classes=["mut"]))
            return
        for it in tags:
            row = Gtk.Box(spacing=8)
            lab = Gtk.Label(label=f"#{it['tag']}", xalign=0); lab.set_size_request(120, -1)
            lab.set_ellipsize(Pango.EllipsizeMode.END)
            row.append(lab)
            row.append(Gtk.Label(label=f"{it['count']} việc", css_classes=["mut"]))
            e = Gtk.Entry(placeholder_text="tên mới…"); e.set_hexpand(True)
            row.append(e)
            rb = Gtk.Button(label="Đổi tên"); rb.add_css_class("dlgbtn")
            rb.connect("clicked", lambda *_ , tg=it["tag"], en=e: self._rename(tg, en))
            db = Gtk.Button(label="Gỡ nhãn"); db.add_css_class("dlgbtn")
            db.connect("clicked", lambda *_ , tg=it["tag"]: self._delete(tg))
            row.append(rb); row.append(db)
            self.list_box.append(row)

    def _rename(self, old, entry):
        new = entry.get_text().strip()
        if not new: return
        try: api("POST", "/api/tags/rename", {"old": old, "new": new})
        except Exception: return
        self._load(); self.on_done()

    def _delete(self, tag):
        try: api("POST", "/api/tags/delete", {"tag": tag})
        except Exception: return
        self._load(); self.on_done()


class SearchDialog(Gtk.Window):
    """Tìm MỌI NƠI (v1.4.0): mọi dự án + cả việc đã xong + khớp trong bình
    luận — ô tìm trên bảng chỉ lọc việc đang hiện nên tìm việc cũ không ra."""
    def __init__(self, parent, query):
        super().__init__(title=f"Tìm mọi nơi: {query}", transient_for=parent, modal=True)
        self.win = parent
        self.set_default_size(560, -1)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_top(16); box.set_margin_bottom(16); box.set_margin_start(16); box.set_margin_end(16)
        self.list_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.append(self.list_box)
        brow = Gtk.Box(spacing=8); brow.set_halign(Gtk.Align.END)
        close = Gtk.Button(label="Đóng"); close.add_css_class("dlgbtn"); close.connect("clicked", lambda *_: self.close())
        brow.append(close); box.append(brow)
        self.set_child(box)
        try:
            tasks = api("GET", "/api/search?q=" + urllib.parse.quote(query))["tasks"]
        except Exception as e:
            tasks = []
            self.list_box.append(Gtk.Label(label=f"Tìm lỗi: {e}", xalign=0, css_classes=["mut"]))
        if not tasks:
            self.list_box.append(Gtk.Label(label="Không thấy việc nào khớp.", xalign=0, css_classes=["mut"]))
        for t in tasks:
            b = Gtk.Button(); b.add_css_class("dlgbtn")
            row = Gtk.Box(spacing=8)
            lab = Gtk.Label(label=t["title"], xalign=0); lab.set_hexpand(True)
            lab.set_ellipsize(Pango.EllipsizeMode.END)
            row.append(lab)
            meta = []
            if t.get("project_name"): meta.append(t["project_name"])
            meta.append("Đã xong" if t["status"] == "done" else "Đang mở")
            if t.get("due_date"): meta.append("hạn " + t["due_date"])
            if t.get("via_comment"): meta.append("khớp trong bình luận")
            row.append(Gtk.Label(label=" · ".join(meta), css_classes=["mut"]))
            b.set_child(row)
            b.connect("clicked", lambda *_ , tt=t: self._open(tt))
            self.list_box.append(b)

    def _open(self, t):
        self.close()
        self.win.open_task(t)


class RestoreDialog(Gtk.Window):
    """Khôi phục từ bản sao lưu (v1.4.0): engine tự sao lưu mỗi ngày nhưng
    trước đây muốn khôi phục phải chép file bằng tay. Trước khi thay, engine
    tự chụp lại dữ liệu hiện tại (pre-restore) nên vẫn quay lại được."""
    def __init__(self, parent, on_done):
        super().__init__(title="Khôi phục từ bản sao lưu", transient_for=parent, modal=True)
        self.on_done = on_done
        self.set_default_size(520, -1)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_margin_top(16); box.set_margin_bottom(16); box.set_margin_start(16); box.set_margin_end(16)
        box.append(Gtk.Label(label="Khôi phục sẽ THAY toàn bộ dữ liệu hiện tại bằng bản sao lưu đã chọn. "
                                   "Dữ liệu hiện tại được tự sao lưu lại ngay trước khi thay (bản pre-restore).",
                             xalign=0, wrap=True, css_classes=["mut"]))
        self.list_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.append(self.list_box)
        self.status = Gtk.Label(label="", xalign=0, wrap=True, css_classes=["mut"])
        box.append(self.status)
        brow = Gtk.Box(spacing=8); brow.set_halign(Gtk.Align.END)
        close = Gtk.Button(label="Đóng"); close.add_css_class("dlgbtn"); close.connect("clicked", lambda *_: self.close())
        brow.append(close); box.append(brow)
        self.set_child(box)
        self._load()

    def _load(self):
        for c in _kids(self.list_box): self.list_box.remove(c)
        try:
            bks = api("GET", "/api/backups")["backups"]
        except Exception as e:
            self.list_box.append(Gtk.Label(label=f"Không đọc được sao lưu: {e}", xalign=0, css_classes=["mut"]))
            return
        if not bks:
            self.list_box.append(Gtk.Label(label="Chưa có bản sao lưu nào.", xalign=0, css_classes=["mut"]))
            return
        for bk in bks:
            row = Gtk.Box(spacing=8)
            lab = Gtk.Label(label=bk["name"], xalign=0); lab.set_hexpand(True)
            lab.set_ellipsize(Pango.EllipsizeMode.END)
            row.append(lab)
            row.append(Gtk.Label(label=f"{bk['size'] // 1024} KB · {(bk['mtime'] or '')[:16].replace('T', ' ')}",
                                 css_classes=["mut"]))
            rb = Gtk.Button(label="Khôi phục"); rb.add_css_class("dlgbtn")
            rb.connect("clicked", lambda *_ , nm=bk["name"]: self._ask(nm))
            row.append(rb)
            self.list_box.append(row)

    def _ask(self, name):
        dlg = Gtk.AlertDialog()
        dlg.set_message(f"Khôi phục bản {name}?")
        dlg.set_detail("Toàn bộ dữ liệu hiện tại sẽ được thay bằng bản này (bản hiện tại được sao lưu lại trước).")
        dlg.set_buttons(["Huỷ", "Khôi phục"])
        dlg.set_cancel_button(0); dlg.set_default_button(0)
        dlg.choose(self, None, lambda d, r: self._done_ask(d, r, name))

    def _done_ask(self, dlg, res, name):
        try: idx = dlg.choose_finish(res)
        except Exception: return
        if idx != 1: return
        try:
            api("POST", "/api/restore", {"name": name})
            self.status.set_text("Đã khôi phục xong — bảng đã nạp lại dữ liệu của bản sao lưu.")
            self.on_done()
        except Exception as e:
            self.status.set_text(f"Khôi phục lỗi: {e}")

def http_json(base, method, path, body=None, timeout=10, token=""):
    """Gọi API JSON của một engine Shini Tasks BẤT KỲ (máy này hoặc máy kia qua
    Tailscale) — dùng cho đồng bộ/xuất/nhập. Máy kia có token thì phải kèm
    X-Token của máy kia (audit 2026-11-17 mục A1)."""
    data = json.dumps(body, ensure_ascii=False).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token: headers["X-Token"] = token
    req = urllib.request.Request(base.rstrip("/") + path, data=data, method=method,
                                 headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


class SyncDialog(Gtk.Window):
    """Đồng bộ 2 máy + sao lưu rời (GĐ2): engine đã tự sao lưu tasks.db mỗi ngày
    vào thư mục backups/; hộp này lo phần ĐỒNG BỘ với máy kia (gộp hai chiều theo
    mốc updated_at — bản mới hơn thắng) và xuất/nhập JSON thủ công."""
    def __init__(self, parent, on_done):
        super().__init__(title="Đồng bộ & sao lưu", transient_for=parent, modal=True)
        self.on_done = on_done
        self.set_default_size(470, -1)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_margin_top(16); box.set_margin_bottom(16); box.set_margin_start(16); box.set_margin_end(16)
        hint = Gtk.Label(label="Hai máy chạy Shini Tasks trên cùng mạng/Tailscale sẽ gộp dữ liệu: "
                               "việc khớp theo mã số, bản sửa MỚI HƠN thì thắng. Việc đã xoá hẳn ở "
                               "máy này sẽ không tự xoá ở máy kia.\n"
                               "Sao lưu tự động: engine chép tasks.db vào thư mục backups/ mỗi ngày (giữ 14 bản).",
                         xalign=0, wrap=True, css_classes=["mut"])
        box.append(hint)
        nrow = Gtk.Box(spacing=8)
        nrow.append(Gtk.Label(label="Tên của bạn (ký bình luận):", css_classes=["mut"]))
        self.dname = Gtk.Entry(placeholder_text="Bạn")
        self.dname.set_text(SETTINGS.get("display_name", ""))
        self.dname.set_hexpand(True)
        nrow.append(self.dname)
        saven = Gtk.Button(label="Lưu tên"); saven.add_css_class("dlgbtn")
        saven.connect("clicked", self._save_name)
        nrow.append(saven)
        box.append(nrow)
        row = Gtk.Box(spacing=8)
        row.append(Gtk.Label(label="Địa chỉ máy kia:", css_classes=["mut"]))
        self.peer = Gtk.Entry(placeholder_text="http://100.x.x.x:8790")
        self.peer.set_text(SETTINGS.get("peer_url", ""))
        self.peer.set_hexpand(True)
        row.append(self.peer)
        savep = Gtk.Button(label="Lưu địa chỉ"); savep.add_css_class("dlgbtn")
        savep.connect("clicked", self._save_peer)
        row.append(savep)
        box.append(row)
        trow = Gtk.Box(spacing=8)
        trow.append(Gtk.Label(label="Token của máy kia:", css_classes=["mut"]))
        self.ptok = Gtk.Entry(placeholder_text="Lấy ở Cài đặt của máy kia (mục Token API)…")
        self.ptok.set_visibility(False)
        self.ptok.set_text(SETTINGS.get("peer_token", ""))
        self.ptok.set_hexpand(True)
        trow.append(self.ptok)
        box.append(trow)
        brow = Gtk.Box(spacing=8)
        self.btn_sync = Gtk.Button(label="⇄ Đồng bộ 2 chiều"); self.btn_sync.add_css_class("suggested-action")
        self.btn_sync.connect("clicked", self._sync)
        bexp = Gtk.Button(label="💾 Xuất JSON…"); bexp.add_css_class("dlgbtn")
        bexp.connect("clicked", self._export)
        bimp = Gtk.Button(label="📥 Nhập JSON…"); bimp.add_css_class("dlgbtn")
        bimp.connect("clicked", self._import)
        brow.append(self.btn_sync); brow.append(bexp); brow.append(bimp)
        box.append(brow)
        brow2 = Gtk.Box(spacing=8)
        bcsv = Gtk.Button(label="⬇ Xuất CSV…"); bcsv.add_css_class("dlgbtn")
        bcsv.set_tooltip_text("Bảng tính Excel/Sheets: mọi việc kèm dự án, cột, hạn, giờ thật")
        bcsv.connect("clicked", self._export_csv)
        brs = Gtk.Button(label="📂 Khôi phục từ sao lưu…"); brs.add_css_class("dlgbtn")
        brs.set_tooltip_text("Thay dữ liệu hiện tại bằng một bản sao lưu hằng ngày")
        brs.connect("clicked", lambda *_: RestoreDialog(self, self.on_done).present())
        brow2.append(bcsv); brow2.append(brs)
        box.append(brow2)
        box.append(Gtk.Label(label="ĐỒNG BỘ QUA THƯ MỤC CHUNG", xalign=0, css_classes=["pane-h"]))
        box.append(Gtk.Label(label="Nếu hai máy cùng thấy một thư mục (Google Drive / Dropbox / thư mục "
                                   "mạng), xuất dữ liệu ra đó rồi sang máy kia nhập vào — khỏi cần "
                                   "Tailscale hay địa chỉ IP.",
                             xalign=0, wrap=True, css_classes=["mut"]))
        drow = Gtk.Box(spacing=8)
        self.sync_dir = Gtk.Entry(placeholder_text="Đường dẫn thư mục chung…")
        self.sync_dir.set_text(SETTINGS.get("sync_dir", ""))
        self.sync_dir.set_hexpand(True)
        drow.append(self.sync_dir)
        bx1 = Gtk.Button(label="⬆ Xuất ra thư mục"); bx1.add_css_class("dlgbtn")
        bx1.connect("clicked", self._dir_export)
        bx2 = Gtk.Button(label="⬇ Nhập từ thư mục"); bx2.add_css_class("dlgbtn")
        bx2.connect("clicked", self._dir_import)
        drow.append(bx1); drow.append(bx2)
        box.append(drow)
        self.status = Gtk.Label(label="", xalign=0, wrap=True, css_classes=["mut"])
        box.append(self.status)
        self.set_child(box)

    def _dir_path(self):
        d = self.sync_dir.get_text().strip()
        if d:
            SETTINGS["sync_dir"] = d; save_settings(SETTINGS)
        return d

    def _dir_export(self, *_):
        d = self._dir_path()
        if not d:
            self.status.set_text("⚠ Chưa nhập thư mục chung.")
            return
        try:
            os.makedirs(d, exist_ok=True)
            data = api("GET", "/api/export")
            with open(os.path.join(d, "shini-tasks-sync.json"), "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
            self.status.set_text("✓ Đã xuất file shini-tasks-sync.json ra thư mục chung — "
                                 "sang máy kia mở hộp này và bấm 'Nhập từ thư mục'.")
        except Exception as e:
            self.status.set_text(f"⚠ Xuất không được: {e}")

    def _dir_import(self, *_):
        d = self._dir_path()
        p = os.path.join(d, "shini-tasks-sync.json") if d else ""
        if not d or not os.path.exists(p):
            self.status.set_text("⚠ Không thấy file shini-tasks-sync.json trong thư mục đó.")
            return
        try:
            with open(p, encoding="utf-8") as f:
                data = json.load(f)
            r = api("POST", "/api/import", data)
            msg = (f"✓ Đã nhập: +{r.get('inserted', 0)} việc mới, {r.get('updated', 0)} cập nhật, "
                   f"{r.get('skipped', 0)} bỏ qua.")
            if r.get("overwritten"):
                msg += (f"\n⚠ {r['overwritten']} việc bị GHI ĐÈ vì nội dung khác nhau "
                        "(bản mới hơn thắng) — kiểm tra lại các việc vừa sửa.")
            self.status.set_text(msg)
            self.on_done()
        except Exception as e:
            self.status.set_text(f"⚠ Nhập không được: {e}")

    def _save_peer(self, *_):
        SETTINGS["peer_url"] = self.peer.get_text().strip()
        SETTINGS["peer_token"] = self.ptok.get_text().strip()
        save_settings(SETTINGS)
        self.status.set_text("Đã lưu địa chỉ + token máy kia.")

    def _save_name(self, *_):
        SETTINGS["display_name"] = self.dname.get_text().strip()
        save_settings(SETTINGS)
        self.status.set_text("Đã lưu tên — bình luận mới sẽ ký tên này.")

    def _sync(self, *_):
        peer = self.peer.get_text().strip()
        if not peer:
            self.status.set_text("⚠ Chưa nhập địa chỉ máy kia (dạng http://100.x.x.x:8790).")
            return
        ptok = self.ptok.get_text().strip()
        SETTINGS["peer_url"] = peer; SETTINGS["peer_token"] = ptok; save_settings(SETTINGS)
        self.btn_sync.set_sensitive(False)
        self.status.set_text("Đang đồng bộ…")
        def work():
            try:
                local = api("GET", "/api/export")
                remote = http_json(peer, "GET", "/api/export", token=ptok)
                r1 = http_json(peer, "POST", "/api/import", local, token=ptok)
                r2 = api("POST", "/api/import", remote)
                msg = (f"✓ Xong: gửi sang máy kia +{r1.get('inserted', 0)} việc mới, {r1.get('updated', 0)} cập nhật · "
                       f"nhận về +{r2.get('inserted', 0)} việc mới, {r2.get('updated', 0)} cập nhật.")
                ovw = (r1.get("overwritten", 0) or 0) + (r2.get("overwritten", 0) or 0)
                if ovw:
                    msg += (f"\n⚠ Có {ovw} việc bị GHI ĐÈ vì hai máy sửa khác nhau (bản mới hơn thắng) — "
                            "kiểm tra lại các việc vừa sửa gần đây ở cả hai máy.")
            except Exception as e:
                msg = f"⚠ Không đồng bộ được: {e} — kiểm tra máy kia có đang chạy Shini Tasks, cùng mạng Tailscale, và token máy kia đã đúng chưa."
            GLib.idle_add(self._sync_done, msg)
        threading.Thread(target=work, daemon=True).start()

    def _sync_done(self, msg):
        self.status.set_text(msg)
        self.btn_sync.set_sensitive(True)
        self.on_done()
        return False

    def _export_csv(self, *_):
        dlg = Gtk.FileDialog.new()
        dlg.set_title("Xuất CSV (mở bằng Excel / Google Sheets)")
        dlg.set_initial_name(f"shini-tasks-{datetime.now().strftime('%Y%m%d')}.csv")
        dlg.save(self, None, self._export_csv_done)

    def _export_csv_done(self, dlg, res):
        try:
            f = dlg.save_finish(res)
            data = api_raw("/api/export.csv")
            with open(f.get_path(), "wb") as fh:
                fh.write(data)
            self.status.set_text("✓ Đã xuất file CSV.")
        except GLib.Error:
            pass  # người dùng bấm Huỷ
        except Exception as e:
            self.status.set_text(f"⚠ Xuất CSV thất bại: {e}")

    def _export(self, *_):
        dlg = Gtk.FileDialog.new()
        dlg.set_title("Xuất dữ liệu Shini Tasks")
        dlg.set_initial_name(f"shini-tasks-{datetime.now().strftime('%Y%m%d')}.json")
        dlg.save(self, None, self._export_done)

    def _export_done(self, dlg, res):
        try:
            f = dlg.save_finish(res)
            data = api("GET", "/api/export")
            with open(f.get_path(), "w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False, indent=1)
            self.status.set_text(f"✓ Đã xuất {len(data.get('tasks', []))} việc ra file JSON.")
        except GLib.Error:
            pass  # người dùng bấm Huỷ
        except Exception as e:
            self.status.set_text(f"⚠ Xuất thất bại: {e}")

    def _import(self, *_):
        dlg = Gtk.FileDialog.new()
        dlg.set_title("Nhập dữ liệu Shini Tasks (JSON đã xuất)")
        dlg.open(self, None, self._import_done)

    def _import_done(self, dlg, res):
        try:
            f = dlg.open_finish(res)
            with open(f.get_path(), encoding="utf-8") as fh:
                data = json.load(fh)
            r = api("POST", "/api/import", data)
            self.status.set_text(f"✓ Đã nhập: +{r.get('inserted', 0)} việc mới, {r.get('updated', 0)} cập nhật, "
                                 f"{r.get('skipped', 0)} giữ nguyên.")
            self.on_done()
        except GLib.Error:
            pass
        except Exception as e:
            self.status.set_text(f"⚠ Nhập thất bại: {e}")


class CaptureWindow(Adw.ApplicationWindow):
    """Cửa sổ BẮT VIỆC SIÊU NHANH — mở bằng phím tắt toàn cục Alt+E từ bất kỳ app nào.
    Tự điền sẵn nội dung bạn vừa copy / vừa bôi đen; Enter là lưu, không cần mở app chính."""
    def __init__(self, app):
        super().__init__(application=app, title="Thêm việc nhanh — Shini Tasks")
        self.set_default_size(580, 340)
        self._src = 0
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        hb = Adw.HeaderBar()
        hb.set_title_widget(Gtk.Label(label="⚡ Thêm việc nhanh"))
        root.append(hb)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_top(14); box.set_margin_bottom(14); box.set_margin_start(16); box.set_margin_end(16)
        hint = Gtk.Label(label="Gõ hoặc dán bất cứ thứ gì — tin nhắn, ghi chú, danh sách… App tự hiểu ngày giờ, mức ưu tiên, nhãn.", xalign=0, wrap=True)
        hint.add_css_class("mut")
        box.append(hint)
        frame = Gtk.Frame()
        self.view = Gtk.TextView(); self.view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.view.add_css_class("quickentry")
        self.view.set_top_margin(8); self.view.set_bottom_margin(8)
        self.view.set_left_margin(10); self.view.set_right_margin(10)
        sw = Gtk.ScrolledWindow(); sw.set_min_content_height(104); sw.set_child(self.view)
        frame.set_child(sw)
        box.append(frame)
        self.preview = Gtk.Label(label="", xalign=0, wrap=True); self.preview.add_css_class("preview")
        box.append(self.preview)
        self.status = Gtk.Label(label="", xalign=0); self.status.add_css_class("smartlab")
        box.append(self.status)
        foot = Gtk.Label(label="Enter: lưu ngay · Shift+Enter: xuống dòng · Dán nhiều dòng = tạo nhiều việc · Esc: đóng", xalign=0)
        foot.add_css_class("mut")
        box.append(foot)
        root.append(box)
        self.set_content(root)
        keyctl = Gtk.EventControllerKey()
        keyctl.connect("key-pressed", self._on_key)
        self.add_controller(keyctl)
        self.view.get_buffer().connect("changed", self._on_changed)
        self._prefill()
        self.view.grab_focus()

    def _text(self):
        buf = self.view.get_buffer()
        return buf.get_text(buf.get_start_iter(), buf.get_end_iter(), True)

    def _prefill(self):
        pre = os.environ.get("SHINI_CAPTURE_PREFILL")
        if pre:
            self.view.get_buffer().set_text(pre); return
        disp = Gdk.Display.get_default()
        def use(text):
            if text and text.strip() and not self._text().strip():
                self.view.get_buffer().set_text(text.strip())
        def read(clip):
            try:
                clip.read_text_async(None, lambda c, res: _done(c, res))
            except Exception: pass
            def _done(c, res):
                try: use(c.read_text_finish(res))
                except Exception: pass
        read(disp.get_primary_clipboard())   # chữ vừa bôi đen
        GLib.timeout_add(250, lambda: (read(disp.get_clipboard()), False)[1])  # chữ vừa copy

    def _on_key(self, _ctl, keyval, _code, state):
        name = Gdk.keyval_name(keyval) or ""
        if name == "Escape": self.close(); return True
        if name in ("Return", "KP_Enter") and not (state & Gdk.ModifierType.SHIFT_MASK):
            self._save(); return True
        return False

    def _on_changed(self, *_):
        self._src += 1
        src = self._src
        def later():
            if src != self._src: return False
            text = self._text().strip()
            if not text:
                self.preview.set_text(""); return False
            kind, _p = split_capture(text)
            if kind == "multi":
                n = len([l for l in text.splitlines() if l.strip()])
                self.preview.set_text(f"📋 Sẽ tạo {n} việc từ {n} dòng")
                return False
            if kind == "long":
                self.preview.set_text("📝 Đoạn dài → 1 việc: dòng đầu làm tiêu đề, toàn bộ nội dung lưu vào ghi chú")
                return False
            def work():
                try: p = api("GET", "/api/parse?text=" + urllib.parse.quote(text)).get("parsed")
                except Exception: p = None
                bits = preview_bits(p)
                GLib.idle_add(lambda: (self.preview.set_text(("→ App hiểu là: " + " · ".join(bits)) if bits else ""), False)[1])
            threading.Thread(target=work, daemon=True).start()
            return False
        GLib.timeout_add(300, later)

    def _save(self):
        text = self._text().strip()
        if not text: self.close(); return
        self.status.set_text("Đang lưu…")
        def work():
            try: n = create_from_text(text)
            except Exception: n = -1
            def done():
                if n > 0:
                    self.status.set_text(f"✓ Đã lưu {n} việc vào Shini Tasks")
                    GLib.timeout_add(550, lambda: (self.close(), False)[1])
                else:
                    self.status.set_text("⚠️ Chưa lưu được — kiểm tra app Shini Tasks có đang chạy nền không")
                return False
            GLib.idle_add(done)
        threading.Thread(target=work, daemon=True).start()

def run_capture():
    Adw.init()
    app = Adw.Application(application_id="dev.shini.tasks.capture")
    def on_act(a):
        apply_theme()
        win = CaptureWindow(a)
        win.present()
        snap = os.environ.get("SHINI_TASKS_SNAPSHOT")
        if snap:
            def shot():
                renderer = None
                try:
                    from gi.repository import Gsk, Graphene
                    paintable = Gtk.WidgetPaintable.new(win)
                    w = paintable.get_intrinsic_width() or 580
                    h = paintable.get_intrinsic_height() or 340
                    snapshot = Gtk.Snapshot(); paintable.snapshot(snapshot, w, h)
                    node = snapshot.to_node()
                    renderer = Gsk.CairoRenderer(); renderer.realize(None)
                    rect = Graphene.Rect(); rect.init(0, 0, w, h)
                    tex = renderer.render_texture(node, rect)
                    tex.save_to_png(snap)
                    print("SNAPSHOT_OK", snap, w, h)
                except Exception as e:
                    print("SNAPSHOT_ERR", type(e).__name__, e)
                finally:
                    try:
                        if renderer: renderer.unrealize()
                    except Exception: pass
                a.quit(); return False
            GLib.timeout_add(1800, shot)
    app.connect("activate", on_act)
    return app.run([])

class MainWindow(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="Shini Tasks")
        self.set_default_size(1560, 880)
        self._last_hash = ""
        self.sb_nums = {}
        self.level_labels = {}
        self.all_tasks = []
        self.done_archive = []
        self.columns = []
        self.projects = []
        self.cur_project = SETTINGS.get("project_id")   # dự án đang xem ở bảng cột
        self.stats = {}
        self.q_text = ""
        self.f_tag = None
        self.f_assignee = None
        self.f_overdue = False
        self.f_date = None
        self.sort_mode = 0
        self.smart = "all"                # mục Thông minh đang chọn (sidebar kiểu Reminders)
        self.focus_col = None             # id cột đang tập trung ở sidebar (None = tất cả)
        self._parse_src = 0
        self.view_mode = "board"          # "board" = bảng cột như cũ · "calendar" = lưới lịch
        self.cal_offset = 0               # số tuần lệch so với tuần này (chế độ Tuần)
        self.cal_month_off = 0            # số tháng lệch so với tháng này (chế độ Tháng)
        self.cal_gran = "week"            # "week" | "day" | "month"
        self.cal_day = today_()           # ngày đang xem (chế độ Ngày)
        self._caltask_providers = {}
        self._col_providers = {}
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        hb = Adw.HeaderBar()
        self.crumb_lab = Gtk.Label(label="✦ Shini Tasks")
        hb.set_title_widget(self.crumb_lab)
        # Nút "🔔 Test thông báo": ĐÃ BỎ theo lời Sinh (2026-11-09 11:35) — endpoint
        # /api/notify-test của engine vẫn còn nguyên nếu sau này cần kiểm tra thông báo.
        self.theme_btn = Gtk.Button(); self.theme_btn.add_css_class("hdrbtn")
        self.theme_btn.set_tooltip_text("Chuyển chế độ Sáng / Tối")
        self.theme_btn.connect("clicked", self._toggle_theme)
        self._theme_btn_label()
        b_new = Gtk.Button(label="＋ Việc mới"); b_new.add_css_class("suggested-action")
        b_new.connect("clicked", lambda *_: self.new_task())
        b_cap = Gtk.Button(label="⚡ Bắt việc nhanh"); b_cap.add_css_class("hdrbtn")
        b_cap.set_tooltip_text("Mở cửa sổ bắt việc siêu nhanh — dán bất cứ đoạn chữ nào vào là thành việc (Alt+E từ mọi app)")
        b_cap.connect("clicked", lambda *_: spawn_capture())
        b_side = Gtk.Button(label="☰"); b_side.add_css_class("hdrbtn")
        b_side.set_tooltip_text("Ẩn / hiện toàn bộ thanh bên (Ctrl+B)")
        b_side.connect("clicked", lambda *_: self._toggle_sidebar())
        self.upd_btn = Gtk.Button(label=""); self.upd_btn.add_css_class("suggested-action")
        self.upd_btn.set_visible(False)
        self.upd_btn.set_tooltip_text("Có bản Shini Tasks mới — bấm để mở trang tải về")
        self.upd_btn.connect("clicked", self._open_update)
        # Nhãn báo mất kết nối engine (audit A7): chỉ hiện khi refresh lỗi.
        self.conn_lbl = Gtk.Label(label="⚠ Mất kết nối engine — đang tự nối lại…")
        self.conn_lbl.add_css_class("overdue"); self.conn_lbl.set_visible(False)
        hb.pack_start(b_side); hb.pack_start(self.theme_btn)
        hb.pack_end(b_new); hb.pack_end(b_cap); hb.pack_end(self.upd_btn); hb.pack_end(self.conn_lbl)
        root.append(hb)

        body = Gtk.Paned.new(Gtk.Orientation.HORIZONTAL)
        body.set_vexpand(True)
        body.set_resize_start_child(False); body.set_shrink_start_child(False)
        body.set_position(242)
        if not SETTINGS.get("sb_tidy_v1"):
            # Dọn sidebar theo template Todoist (2026-11-16): lịch tháng gập sẵn
            # từ nay — chỉ chạy 1 lần, sau đó tôn trọng lựa chọn của người dùng
            SETTINGS.setdefault("sections", {})["month"] = False
            SETTINGS["sb_tidy_v1"] = True
            save_settings(SETTINGS)
        self.sb_scroll = Gtk.ScrolledWindow()
        self.sb_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.sb_scroll.set_child(self._build_sidebar())
        self.sb_scroll.set_visible(SETTINGS.get("sidebar", True))
        body.set_start_child(self.sb_scroll)

        main = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        main.set_hexpand(True)
        # Thanh banner "LÀM TRƯỚC TIÊN" + Pomodoro: ĐÃ BỎ HẲN theo lời Sinh
        # (2026-11-09 11:34 'bỏ hẳn đi luôn') — sau 2 vòng thu gọn trước đó trong cùng buổi sáng.
        # ĐẦU VIEW (v1.5.0): tên dự án + tab chuyển view + Lọc/Hiển thị gom
        # góc phải — thay thanh công cụ cũ hơn chục nút bấm. Thêm nhanh nằm
        # ngay dưới tab, luôn thấy được cách app hiểu câu gõ tắt.
        vh = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        vh.set_margin_top(12); vh.set_margin_start(14); vh.set_margin_end(14)
        r1 = Gtk.Box(spacing=10)
        self.vh_dot = Gtk.Box(); self.vh_dot.set_size_request(11, 11); self.vh_dot.set_valign(Gtk.Align.CENTER)
        r1.append(self.vh_dot)
        self.vh_title = Gtk.Label(label="", xalign=0); self.vh_title.add_css_class("vh-title")
        r1.append(self.vh_title)
        spx = Gtk.Box(); spx.set_hexpand(True); r1.append(spx)
        self.flt_btn = Gtk.MenuButton(label="⧩ Lọc"); self.flt_btn.add_css_class("dlgbtn")
        self.flt_btn.set_tooltip_text("Lọc theo nhãn · sắp xếp · chỉ quá hạn")
        fpop = Gtk.Popover()
        fbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        fbox.set_margin_top(10); fbox.set_margin_bottom(10); fbox.set_margin_start(10); fbox.set_margin_end(10)
        fbox.append(Gtk.Label(label="Nhãn", xalign=0, css_classes=["mut"]))
        self.tag_drop = Gtk.DropDown.new_from_strings(["Tất cả nhãn"])
        self.tag_drop.connect("notify::selected", self._on_tag)
        fbox.append(self.tag_drop)
        fbox.append(Gtk.Label(label="Người làm", xalign=0, css_classes=["mut"]))
        self.assignee_drop = Gtk.DropDown.new_from_strings(["Tất cả mọi người"])
        self.assignee_drop.connect("notify::selected", self._on_assignee)
        fbox.append(self.assignee_drop)
        fbox.append(Gtk.Label(label="Sắp xếp", xalign=0, css_classes=["mut"]))
        self.sort_drop = Gtk.DropDown.new_from_strings(["Sắp xếp: Ưu tiên", "Sắp xếp: Hạn gần nhất"])
        self.sort_drop.connect("notify::selected", self._on_sort)
        fbox.append(self.sort_drop)
        self.over_btn = Gtk.ToggleButton(label="⚠ Chỉ quá hạn")
        self.over_btn.add_css_class("overbtn")
        self.over_btn.connect("toggled", self._on_over)
        fbox.append(self.over_btn)
        self.filter_lab = Gtk.Label(label="", xalign=0, wrap=True); self.filter_lab.add_css_class("mut")
        fbox.append(self.filter_lab)
        clr = Gtk.Button(label="Xoá mọi lọc"); clr.add_css_class("flat"); clr.add_css_class("dlgflat")
        clr.set_halign(Gtk.Align.START)
        clr.connect("clicked", self._clear_filters)
        fbox.append(clr)
        fpop.set_child(fbox)
        self.flt_btn.set_popover(fpop)
        r1.append(self.flt_btn)
        self.disp_btn = Gtk.MenuButton(label="↕ Hiển thị"); self.disp_btn.add_css_class("dlgbtn")
        dpop = Gtk.Popover()
        dbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        dbox.set_margin_top(6); dbox.set_margin_bottom(6); dbox.set_margin_start(6); dbox.set_margin_end(6)
        thb = Gtk.Button(label="☀️ / 🌙  Đổi sáng · tối"); thb.add_css_class("flat"); thb.add_css_class("dlgflat")
        thb.connect("clicked", lambda *_: (dpop.popdown(), self._toggle_theme()))
        dbox.append(thb)
        sbb = Gtk.Button(label="☰  Ẩn / hiện thanh bên (Ctrl+B)"); sbb.add_css_class("flat"); sbb.add_css_class("dlgflat")
        sbb.connect("clicked", lambda *_: (dpop.popdown(), self._toggle_sidebar()))
        dbox.append(sbb)
        dpop.set_child(dbox)
        self.disp_btn.set_popover(dpop)
        r1.append(self.disp_btn)
        vh.append(r1)
        tabs = Gtk.Box(spacing=2); tabs.add_css_class("tabrow")
        self.btn_board = Gtk.ToggleButton(label="▦ Bảng"); self.btn_board.add_css_class("viewtab")
        self.btn_list = Gtk.ToggleButton(label="☰ Danh sách"); self.btn_list.add_css_class("viewtab")
        self.btn_cal = Gtk.ToggleButton(label="📅 Lịch"); self.btn_cal.add_css_class("viewtab")
        self.btn_today = Gtk.ToggleButton(label="☀ Hôm nay"); self.btn_today.add_css_class("viewtab")
        self.btn_map = Gtk.ToggleButton(label="🗺 Sơ đồ"); self.btn_map.add_css_class("viewtab")
        self.btn_stats = Gtk.ToggleButton(label="📊 Thống kê"); self.btn_stats.add_css_class("viewtab")
        self.btn_board.set_active(True); self.btn_board.add_css_class("viewtab-on")
        self.btn_board.connect("toggled", lambda b: self._set_view("board") if b.get_active() else None)
        self.btn_list.connect("toggled", lambda b: self._set_view("list") if b.get_active() else None)
        self.btn_cal.connect("toggled", lambda b: self._set_view("calendar") if b.get_active() else None)
        self.btn_today.connect("toggled", lambda b: self._set_view("today") if b.get_active() else None)
        self.btn_map.connect("toggled", lambda b: self._set_view("mindmap") if b.get_active() else None)
        self.btn_stats.connect("toggled", lambda b: self._set_view("stats") if b.get_active() else None)
        for _b in (self.btn_board, self.btn_list, self.btn_cal, self.btn_today,
                   self.btn_map, self.btn_stats): tabs.append(_b)
        vh.append(tabs)
        qrow = Gtk.Box(spacing=8)
        self.quick = Gtk.Entry(placeholder_text="Thêm nhanh…")
        self.quick.add_css_class("quickentry"); self.quick.set_hexpand(True)
        self.quick.connect("activate", self._quick_add)
        self.quick.connect("changed", self._on_quick_changed)
        bq = Gtk.Button(label="Thêm"); bq.add_css_class("suggested-action")
        bq.connect("clicked", self._quick_add)
        self.ai_btn = Gtk.Button(label="✨ AI"); self.ai_btn.add_css_class("dlgbtn")
        self.ai_btn.set_tooltip_text("AI Gemini đọc câu tiếng Việt và tự điền form việc (tiêu đề, hạn, ưu tiên, việc con…) — cần API key trong ⚙ Cài đặt ở thanh bên")
        self.ai_btn.connect("clicked", self._quick_ai)
        qrow.append(self.quick); qrow.append(bq); qrow.append(self.ai_btn)
        vh.append(qrow)
        self.quick_preview = Gtk.Label(label="", xalign=0); self.quick_preview.add_css_class("preview")
        self.quick_preview.set_visible(False)
        vh.append(self.quick_preview)
        main.append(vh)

        scroll = Gtk.ScrolledWindow(); scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        scroll.set_vexpand(True)
        self.board = Gtk.Box(spacing=12)
        # Responsive (Sinh 2026-11-09 11:29): KHÔNG ghim halign=START nữa — board phải
        # giãn hết chiều ngang khung nhìn, các cột (hexpand) chia đều phần dư; thêm nhiều
        # cột thì mỗi cột tự hẹp lại tới min 205px rồi mới cuộn ngang.
        self.board.set_hexpand(True)
        self.board.set_margin_start(14); self.board.set_margin_end(14); self.board.set_margin_bottom(14)
        scroll.set_child(self.board)
        # Thanh báo TẬP TRUNG CỘT — chỉ hiện khi đang focus đúng 1 cột.
        # Trước đây bấm tên cột ở sidebar là bảng thu về 1 cột mà chỉ có một
        # dòng chữ nhỏ "Đang lọc…" ở thanh công cụ báo hiệu; Sinh bấm phải,
        # tưởng bảng hỏng vì không thấy các cột như cũ (2026-11-16 00:55).
        # Nay có thanh riêng + nút thoát rõ ràng ngay trên bảng.
        self.focus_bar = Gtk.Box(spacing=10)
        self.focus_bar.set_margin_start(14); self.focus_bar.set_margin_end(14)
        self.focus_bar.set_margin_bottom(8)
        self.focus_lab = Gtk.Label(label="", xalign=0); self.focus_lab.add_css_class("today-h")
        self.focus_bar.append(self.focus_lab)
        unf = Gtk.Button(label="✕ Xem tất cả cột"); unf.add_css_class("dlgbtn")
        unf.connect("clicked", lambda *_: self._set_focus(self.focus_col))
        self.focus_bar.append(unf)
        self.focus_bar.set_visible(False)
        board_page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        board_page.append(self.focus_bar); board_page.append(scroll)
        # Trang LỊCH (lưới thời gian kiểu Google Calendar)
        cal_page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        cal_page.set_margin_start(14); cal_page.set_margin_end(14)
        nav = Gtk.Box(spacing=8); nav.set_margin_bottom(8)
        self.cal_prev = Gtk.Button(label="‹"); self.cal_prev.add_css_class("dlgbtn"); self.cal_prev.connect("clicked", self._cal_nav, -1)
        self.cal_next = Gtk.Button(label="›"); self.cal_next.add_css_class("dlgbtn"); self.cal_next.connect("clicked", self._cal_nav, 1)
        self.cal_today_btn = Gtk.Button(label="Hôm nay"); self.cal_today_btn.add_css_class("dlgbtn"); self.cal_today_btn.connect("clicked", self._cal_today)
        self.cal_title = Gtk.Label(label="", xalign=0); self.cal_title.add_css_class("cal-h")
        self.cal_title.set_hexpand(True)
        self.gran_week = Gtk.ToggleButton(label="Tuần"); self.gran_week.add_css_class("viewbtn")
        self.gran_day = Gtk.ToggleButton(label="Ngày"); self.gran_day.add_css_class("viewbtn")
        self.gran_week.set_active(True); self.gran_week.add_css_class("viewbtn-on")
        self.gran_week.connect("toggled", lambda b: self._set_gran("week") if b.get_active() else None)
        self.gran_day.connect("toggled", lambda b: self._set_gran("day") if b.get_active() else None)
        self.gran_month = Gtk.ToggleButton(label="Tháng"); self.gran_month.add_css_class("viewbtn")
        self.gran_month.connect("toggled", lambda b: self._set_gran("month") if b.get_active() else None)
        nav.append(self.cal_prev); nav.append(self.cal_today_btn); nav.append(self.cal_next)
        nav.append(self.cal_title)
        self.btn_auto = Gtk.Button(label="⚡ Tự xếp"); self.btn_auto.add_css_class("dlgbtn")
        self.btn_auto.set_tooltip_text("Tự điền giờ cho các việc chưa xếp giờ vào ô trống trong tuần đang xem")
        self.btn_auto.connect("clicked", self._auto_schedule)
        nav.append(self.btn_auto)
        nav.append(self.gran_week); nav.append(self.gran_day); nav.append(self.gran_month)
        cal_page.append(nav)
        self.unsched_box = Gtk.Box(spacing=6); self.unsched_box.set_margin_bottom(8)
        cal_page.append(self.unsched_box)
        self.cal_scroll = Gtk.ScrolledWindow()
        self.cal_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.cal_scroll.set_vexpand(True)
        cal_page.append(self.cal_scroll)
        # Trang HÔM NAY (GĐ1): một cột dọc ở giữa, gom việc theo tình trạng hôm nay
        # Cuộn ngang TỰ ĐỘNG (không còn NEVER): khi panel chi tiết mở, vùng
        # giữa hẹp lại — trang có bề ngang cố định (Thống kê 880px) phải
        # cuộn được thay vì thổi phồng bề ngang tối thiểu của cả cửa sổ
        # làm panel tràn sang (lỗi đè nút Hiển thị, 2026-11-16)
        today_scroll = Gtk.ScrolledWindow(); today_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        today_outer = Gtk.Box(); today_outer.set_halign(Gtk.Align.CENTER)
        self.today_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.today_box.set_size_request(700, -1)
        self.today_box.set_margin_top(6); self.today_box.set_margin_bottom(16)
        self.today_box.set_margin_start(14); self.today_box.set_margin_end(14)
        today_outer.append(self.today_box)
        today_scroll.set_child(today_outer)
        # Trang THỐNG KÊ (hướng B): KPI + biểu đồ + theo cột + xuất báo cáo tuần
        stats_scroll = Gtk.ScrolledWindow(); stats_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        stats_outer = Gtk.Box(); stats_outer.set_halign(Gtk.Align.CENTER)
        self.stats_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.stats_box.set_size_request(880, -1)
        self.stats_box.set_margin_top(6); self.stats_box.set_margin_bottom(16)
        self.stats_box.set_margin_start(14); self.stats_box.set_margin_end(14)
        stats_outer.append(self.stats_box)
        stats_scroll.set_child(stats_outer)
        # Trang DANH SÁCH (v1.5.0): cùng dữ liệu với Bảng, trình bày phẳng
        list_scroll = Gtk.ScrolledWindow(); list_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        list_outer = Gtk.Box(); list_outer.set_halign(Gtk.Align.CENTER)
        self.list_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.list_box.set_size_request(880, -1)
        self.list_box.set_margin_top(2); self.list_box.set_margin_bottom(16)
        self.list_box.set_margin_start(14); self.list_box.set_margin_end(14)
        list_outer.append(self.list_box)
        list_scroll.set_child(list_outer)
        self.stack = Gtk.Stack()
        self.stack.set_vexpand(True); self.stack.set_margin_top(12)
        self.stack.add_named(board_page, "board")
        self.stack.add_named(list_scroll, "list")
        self.stack.add_named(cal_page, "calendar")
        self.stack.add_named(today_scroll, "today")
        self.stack.add_named(stats_scroll, "stats")
        # Chế độ THÁNG của trang LỊCH: dòng thời gian bắt đầu -> hạn.
        # (Gộp từ tab Gantt cũ — Sinh chốt 2026-11-17: Gantt và Lịch giống
        # nhau; phần riêng của Gantt là thanh kéo dài ngày + nhìn xa nhiều
        # tuần, đưa hết vào Lịch thành chế độ Tháng, xoá tab Gantt.)
        self.gantt_area = Gtk.DrawingArea()
        self.gantt_area.set_draw_func(self._gantt_draw)
        _gg = Gtk.GestureClick(); _gg.connect("released", self._gantt_click)
        self.gantt_area.add_controller(_gg)
        self.tl_scroll = Gtk.ScrolledWindow(); self.tl_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.tl_scroll.set_child(self.gantt_area)
        self.tl_scroll.set_vexpand(True)
        self.tl_scroll.set_visible(False)
        cal_page.append(self.tl_scroll)
        # Trang SƠ ĐỒ (mindmap Dự án -> Cột -> Việc -> Việc con)
        self.map_area = Gtk.DrawingArea()
        self.map_area.set_draw_func(self._map_draw)
        _mg = Gtk.GestureClick(); _mg.connect("released", self._map_click)
        self.map_area.add_controller(_mg)
        map_scroll = Gtk.ScrolledWindow(); map_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        map_scroll.set_child(self.map_area); map_scroll.set_vexpand(True)
        self.map_scroll = map_scroll
        # Thanh đầu trang Sơ đồ (gói C audit 2026-11-17): gợi ý thu gọn
        # nhánh + công tắc hiện việc đã xong (trước đây sơ đồ giấu hẳn).
        self.mm_show_done = False
        self.mm_collapsed = set()
        map_page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        mhead = Gtk.Box(spacing=10)
        mhead.set_margin_top(8); mhead.set_margin_bottom(8); mhead.set_margin_start(12); mhead.set_margin_end(12)
        mhead.append(Gtk.Label(label="Bấm vào tên cột để thu gọn / mở nhánh · bấm vào việc để mở chi tiết",
                               xalign=0, css_classes=["mut"]))
        _msp = Gtk.Box(); _msp.set_hexpand(True); mhead.append(_msp)
        self.mm_done_btn = Gtk.ToggleButton(label="Hiện việc đã xong")
        self.mm_done_btn.add_css_class("overbtn")
        self.mm_done_btn.connect("toggled", self._mm_toggle_done)
        mhead.append(self.mm_done_btn)
        map_page.append(mhead)
        map_page.append(map_scroll)
        self.stack.add_named(map_page, "mindmap")
        _vm = os.environ.get("SHINI_TASKS_VIEW")
        if _vm == "gantt": _vm = "calendar"   # Gantt đã gộp vào Lịch (chế độ Tháng)
        if _vm in ("calendar", "today", "stats", "list", "mindmap"):
            self.view_mode = _vm
            self.stack.set_visible_child_name(_vm)
            self.btn_board.set_active(False); self.btn_board.remove_css_class("viewtab-on")
            on = {"calendar": self.btn_cal, "today": self.btn_today, "stats": self.btn_stats,
                  "list": self.btn_list, "mindmap": self.btn_map}[_vm]
            on.set_active(True); on.add_css_class("viewtab-on")
            if os.environ.get("SHINI_TASKS_VIEW") == "gantt":
                self.cal_gran = "month"
                self.gran_week.set_active(False); self.gran_week.remove_css_class("viewbtn-on")
                self.gran_month.set_active(True); self.gran_month.add_css_class("viewbtn-on")
        main.append(self.stack)
        body.set_end_child(main)
        # Panel chi tiết BÊN PHẢI (v1.5.0) — ẩn cho tới khi chọn một việc
        self.selected_id = None
        self.pane = DetailPane(self)
        self.pane_scroll = Gtk.ScrolledWindow()
        self.pane_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.pane_scroll.set_child(self.pane.box)
        # Chi tiết việc = POPUP nổi giữa cửa sổ (Adw.Dialog) — Sinh chốt
        # 2026-11-16: panel phải cố định bóp bảng quá hẹp, cứ popup như cũ.
        # Popup chi tiết = LỚP PHỦ MỀM trong cửa sổ chính (Sinh 2026-11-16
        # 17:16: 'hiển thị mềm mại hơn, có thể click nơi khác để đóng'):
        # nền mờ phủ toàn cửa sổ + thẻ bo góc 16px nổi ở giữa; bấm vào vùng
        # mờ là đóng (qua request_close_pane — còn chữ chưa lưu thì hỏi).
        # Adw.Dialog hỏng vì bóng đổ cairo thành khung đen đè chữ; Gtk.Window
        # riêng thì cứng và không click-ngoài-đóng được — lớp phủ thắng cả hai.
        self.pane_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.pane_card.add_css_class("panecard")
        self.pane_card.set_halign(Gtk.Align.CENTER)
        self.pane_card.set_valign(Gtk.Align.CENTER)
        # Trong Gtk.Box, ScrolledWindow không tự giãn — phải ghim expand,
        # không thì nó co về chiều cao tự nhiên ~100px và thẻ trắng trơn.
        self.pane_scroll.set_vexpand(True)
        self.pane_scroll.set_hexpand(True)
        self.pane_card.append(self.pane_scroll)
        self.pane_backdrop = Gtk.Overlay()
        _dim = Gtk.Box(); _dim.add_css_class("panebackdrop")
        self.pane_backdrop.set_child(_dim)
        self.pane_backdrop.add_overlay(self.pane_card)
        _bg = Gtk.GestureClick()
        _bg.connect("released", lambda *_: self.request_close_pane())
        _dim.add_controller(_bg)
        self.pane_backdrop.set_visible(False)
        self._pane_shown = False
        outer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        body.set_hexpand(True)
        outer.append(body)
        root.append(outer)

        self.toasts = Adw.ToastOverlay()
        self.toasts.set_child(root)
        self.win_overlay = Gtk.Overlay()
        self.win_overlay.set_child(self.toasts)
        self.win_overlay.add_overlay(self.pane_backdrop)
        # Lớp phủ KHÔNG được tính vào kích thước tối thiểu của cửa sổ
        self.win_overlay.set_measure_overlay(self.pane_backdrop, False)
        self.set_content(self.win_overlay)
        keyctl = Gtk.EventControllerKey()
        keyctl.connect("key-pressed", self._on_key)
        self.add_controller(keyctl)
        self.refresh()
        GLib.timeout_add_seconds(5, self._tick)
        # Lần mở ĐẦU TIÊN: hiện hộp Hướng dẫn (gói B audit 2026-11-17);
        # mở lại bất cứ lúc nào ở chân thanh bên → ❓ Hướng dẫn sử dụng.
        if not SETTINGS.get("welcomed") or os.environ.get("SHINI_TASKS_WELCOME"):
            GLib.timeout_add(800, self._show_welcome)

    def _show_welcome(self):
        SETTINGS["welcomed"] = True; save_settings(SETTINGS)
        WelcomeDialog(self).present()
        return False

    # ---------- Theme ----------
    def _theme_btn_label(self):
        self.theme_btn.set_label("☀️ Sáng" if SETTINGS["theme"] == "dark" else "🌙 Tối")
    def _toggle_theme(self, *_):
        SETTINGS["theme"] = "light" if SETTINGS["theme"] == "dark" else "dark"
        save_settings(SETTINGS)
        apply_theme()
        self._theme_btn_label()
        self._last_hash = ""
        self.refresh()

    # ---------- Sidebar ----------
    def _sb_row(self, dot_color, label, key, label_key=None):
        row = Gtk.Box(spacing=8); row.add_css_class("sb-row")
        dot = Gtk.Box(); dot.add_css_class("dot")
        dot.set_size_request(9, 9); dot.set_valign(Gtk.Align.CENTER); dot.set_halign(Gtk.Align.CENTER)
        provider = Gtk.CssProvider(); css_load(provider, f".dot-{key} {{ background: {dot_color}; }}".encode())
        dot.add_css_class(f"dot-{key}")
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_USER - 1)
        row.append(dot)
        lab = Gtk.Label(label=label, xalign=0); lab.set_ellipsize(Pango.EllipsizeMode.END)
        row.append(lab)
        if label_key: self.level_labels[label_key] = lab
        sp = Gtk.Box(); sp.set_hexpand(True); row.append(sp)
        num = Gtk.Label(label="–"); num.add_css_class("sb-num"); row.append(num)
        self.sb_nums[key] = num
        return row

    def _section(self, parent, key, title, content, default=True):
        """Một mục sidebar gập/mở được; trạng thái lưu trong settings.json."""
        exp = Gtk.Expander()
        lab = Gtk.Label(label=title, xalign=0); lab.add_css_class("sb-h")
        exp.set_label_widget(lab)
        exp.set_child(content)
        exp.set_expanded(SETTINGS.get("sections", {}).get(key, default))
        exp.connect("notify::expanded", lambda e, *_: self._save_section(key, e.get_expanded()))
        parent.append(exp)
        return exp

    def _save_section(self, key, val):
        if SETTINGS.get("sections", {}).get(key, True) == val: return  # không đổi thì không ghi file
        SETTINGS.setdefault("sections", {})[key] = val
        save_settings(SETTINGS)

    SMART_DEFS = (("all", "📋", "#4C8DFF", "Tất cả việc"), ("today", "☀", "#FB923C", "Hôm nay"),
                  ("upcoming", "🗓", "#A78BFA", "Sắp tới"), ("overdue", "⚠", "#F87171", "Quá hạn"),
                  ("done", "✓", "#34D399", "Đã xong"))

    def _set_smart(self, key):
        self.smart = key
        if key in ("all", "done"): self.focus_col = None
        if self.view_mode not in ("board", "list"): self._set_view("board")
        self._last_hash = ""
        self.refresh()

    def _set_focus(self, cid):
        self.focus_col = None if self.focus_col == cid else cid
        if self.focus_col is not None: self.smart = "all"
        self._last_hash = ""
        self.refresh()

    def _smart_ok(self, t, key):
        if key == "all": return True
        if key == "done": return t["status"] == "done"
        if t["status"] == "done": return False
        d = t.get("due_date")
        if key == "today": return bool(d) and d <= TODAY
        if key == "overdue": return is_overdue(t)
        if key == "upcoming":
            if not d: return False
            dd = date.fromisoformat(d)
            return today_() <= dd <= today_() + timedelta(days=7)
        return True

    def _set_project(self, pid):
        if pid == self.cur_project: return
        SETTINGS["project_id"] = pid; save_settings(SETTINGS)
        self.cur_project = pid
        self.focus_col = None
        self._last_hash = ""
        self.refresh()

    def _render_projects(self):
        # v1.5.0: dòng dự án GỌN — chấm màu + tên + vòng tiến độ + số việc mở +
        # menu ⋯. Cột KHÔNG còn lồng dưới dự án (bảng tự nó đã hiện cột; muốn
        # chỉ xem 1 cột thì bấm vào TIÊU ĐỀ cột trên bảng).
        for c in _kids(self.proj_box): self.proj_box.remove(c)
        for p in [p for p in self.projects if not p.get("archived")]:
            n = sum(1 for t in self.all_tasks if t["status"] != "done" and t.get("project_id") == p["id"])
            nd = sum(1 for t in self.all_tasks if t["status"] == "done" and t.get("project_id") == p["id"])
            b = Gtk.Button(); b.add_css_class("colrow")
            if self.cur_project == p["id"]: b.add_css_class("colrow-on")
            row = Gtk.Box(spacing=9)
            dot = Gtk.Box(); dot.add_css_class("cdot2-x")
            dot.set_size_request(10, 10); dot.set_valign(Gtk.Align.CENTER)
            prov = Gtk.CssProvider()
            css_load(prov, f".cdot2-x {{ background: {p.get('color') or '#60A5FA'}; border-radius: 999px; }}".encode())
            dot.get_style_context().add_provider(prov, Gtk.STYLE_PROVIDER_PRIORITY_USER)
            row.append(dot)
            lab = Gtk.Label(label=p["name"], xalign=0); lab.add_css_class("smartlab"); lab.set_hexpand(True)
            lab.set_ellipsize(Pango.EllipsizeMode.END)
            row.append(lab)
            ring = Ring()
            ring.set_fraction((nd / (n + nd)) if (n + nd) else 0)
            ring.set_valign(Gtk.Align.CENTER)
            ring.set_tooltip_text(f"Đã xong {nd}/{n + nd} việc của dự án này")
            row.append(ring)
            row.append(Gtk.Label(label=str(n), css_classes=["smartnum"]))
            menu = Gtk.MenuButton(label="⋯"); menu.add_css_class("projmenu"); menu.add_css_class("mini")
            menu.set_valign(Gtk.Align.CENTER)
            pop = Gtk.Popover()
            pbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            pbox.set_margin_top(6); pbox.set_margin_bottom(6); pbox.set_margin_start(6); pbox.set_margin_end(6)
            eb = Gtk.Button(label="✎ Đổi tên & màu"); eb.add_css_class("flat"); eb.add_css_class("dlgflat")
            eb.connect("clicked", lambda *_ , pp=p: (pop.popdown(), ProjectDialog(self, pp, self.refresh).present()))
            pbox.append(eb)
            ab = Gtk.Button(label="📦 Lưu trữ dự án"); ab.add_css_class("flat"); ab.add_css_class("dlgflat")
            ab.connect("clicked", lambda *_ , pp=p: (pop.popdown(), self._archive_project(pp)))
            pbox.append(ab)
            if len(self.projects) > 1:
                db = Gtk.Button(label="🗑 Xoá dự án"); db.add_css_class("flat"); db.add_css_class("dlgflat")
                db.connect("clicked", lambda *_ , pp=p: (pop.popdown(), self._ask_del_project(pp)))
                pbox.append(db)
            pop.set_child(pbox)
            menu.set_popover(pop)
            row.append(menu)
            b.set_child(row)
            b.set_tooltip_text("Bấm để xem bảng của dự án này")
            b.connect("clicked", lambda *_ , pid=p["id"]: self._set_project(pid))
            self.proj_box.append(b)
        _arch = [p for p in self.projects if p.get("archived")]
        if _arch:
            ab2 = Gtk.Button(label=f"📦 Đã lưu trữ ({len(_arch)})")
            ab2.add_css_class("flat"); ab2.add_css_class("renamebtn")
            _al = ab2.get_child()
            if _al: _al.set_xalign(0)
            ab2.set_tooltip_text("Xem và khôi phục các dự án đã lưu trữ")
            ab2.connect("clicked", lambda *_: ArchivedProjectsDialog(self, self.refresh).present())
            self.proj_box.append(ab2)

    def _archive_project(self, p):
        try: api("PATCH", f"/api/projects/{p['id']}", {"archived": 1})
        except Exception: return
        if self.cur_project == p["id"]:
            rest = [q for q in self.projects if q["id"] != p["id"] and not q.get("archived")]
            if rest: self._set_project(rest[0]["id"])
        self._toast(f"📦 Đã lưu trữ dự án “{p['name']}” — khôi phục ở mục 📦 Đã lưu trữ dưới danh sách dự án")
        self._last_hash = ""
        self.refresh()

    def _ask_del_project(self, p):
        dlg = Gtk.AlertDialog()
        dlg.set_message(f"Xoá dự án “{p['name']}”?")
        dlg.set_detail("Mọi việc trong dự án sẽ dồn về dự án đầu tiên còn lại; các cột riêng của dự án này cũng bị xoá.")
        dlg.set_buttons(["Huỷ", "Xoá dự án"])
        dlg.set_cancel_button(0); dlg.set_default_button(0)
        dlg.choose(self, None, lambda d, r: self._del_project_done(d, r, p))

    def _del_project_done(self, dlg, res, p):
        try: idx = dlg.choose_finish(res)
        except Exception: return
        if idx != 1: return
        try: api("DELETE", f"/api/projects/{p['id']}")
        except Exception: return
        if self.cur_project == p["id"]:
            SETTINGS.pop("project_id", None); save_settings(SETTINGS)
            self.cur_project = None
        self._last_hash = ""
        self.refresh()

    def _build_sidebar(self):
        # KHUNG CHUẨN v1.5.0 (nghiên cứu 12 app lớn, Sinh duyệt 2026-11-16):
        # sidebar CHỈ để ĐIỀU HƯỚNG, thứ tự cố định như mọi app lớn:
        # Thêm việc + Tìm kiếm -> mục thông minh -> ĐÃ GHIM -> DỰ ÁN ->
        # (đáy) Đã xong / Thùng rác / quản lý / đồng bộ. Cột KHÔNG nằm trong
        # sidebar nữa; số liệu thuộc trang Thống kê, không nhét vào sidebar.
        sb = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        sb.add_css_class("sidebar"); sb.set_size_request(238, -1)
        sb.set_margin_top(14); sb.set_margin_bottom(14); sb.set_margin_start(12); sb.set_margin_end(12)
        brand = Gtk.Label(label="✦ Shini Tasks", xalign=0); brand.add_css_class("brand")
        sb.append(brand)
        now = datetime.now()
        VN = ["Thứ Hai","Thứ Ba","Thứ Tư","Thứ Năm","Thứ Sáu","Thứ Bảy","Chủ Nhật"]
        sub = Gtk.Label(label=f"{VN[now.weekday()]}, {now.day}/{now.month}/{now.year}", xalign=0)
        sub.add_css_class("brandsub"); sb.append(sub)
        addb = Gtk.Button(label="＋  Thêm việc"); addb.add_css_class("sb2add")
        _al = addb.get_child()
        if _al: _al.set_xalign(0)
        addb.set_margin_top(10)
        addb.set_tooltip_text("Tạo việc mới và mở panel chi tiết để điền (Ctrl+N)")
        addb.connect("clicked", lambda *_: self.new_task())
        sb.append(addb)
        srow = Gtk.Box(spacing=6)
        self.search = Gtk.SearchEntry(placeholder_text="Tìm… Enter = tìm mọi nơi")
        self.search.add_css_class("sb2search")
        self.search.set_hexpand(True)
        self.search.set_tooltip_text("Gõ để lọc bảng · Enter để TÌM MỌI NƠI (mọi dự án, việc đã xong, cả trong bình luận)")
        self.search.connect("search-changed", self._on_search)
        self.search.connect("activate", self._on_search_enter)
        srow.append(self.search)
        sbtn = Gtk.Button(label="🔍"); sbtn.add_css_class("flat")
        sbtn.set_tooltip_text("Tìm MỌI NƠI: mọi dự án, việc đã xong, cả trong bình luận")
        sbtn.connect("clicked", lambda *_: SearchDialog(self, self.search.get_text().strip()).present())
        srow.append(sbtn)
        sb.append(srow)
        self.smart_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.smart_box.set_margin_top(8)
        sb.append(self.smart_box)
        sb.append(Gtk.Label(label="ĐÃ GHIM", xalign=0, css_classes=["sb-h"]))
        self.pin_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        sb.append(self.pin_box)
        sb.append(Gtk.Label(label="DỰ ÁN", xalign=0, css_classes=["sb-h"]))
        self.proj_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        sb.append(self.proj_box)
        addp = Gtk.Button(label="＋ Thêm dự án"); addp.add_css_class("flat"); addp.add_css_class("renamebtn")
        addp.set_halign(Gtk.Align.START)
        addp.set_tooltip_text("Dự án mới có sẵn 3 cột: Cần làm · Đang làm · Hoàn thành")
        addp.connect("clicked", lambda *_: ProjectDialog(self, None, self.refresh).present())
        sb.append(addp)
        self.cal_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        self._section(sb, "month", "LỊCH THÁNG NÀY", self.cal_box, default=False)
        sp = Gtk.Box(); sp.set_vexpand(True); sb.append(sp)
        foot = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        foot.add_css_class("sb2foot")
        self.foot_done = Gtk.Button(); self.foot_done.add_css_class("sb2row")
        fd_row = Gtk.Box(spacing=9)
        fd_row.append(Gtk.Label(label="✓"))
        fd_lab = Gtk.Label(label="Đã xong", xalign=0); fd_lab.set_hexpand(True)
        fd_row.append(fd_lab)
        self.foot_done_num = Gtk.Label(label="0", css_classes=["smartnum"])
        fd_row.append(self.foot_done_num)
        self.foot_done.set_child(fd_row)
        self.foot_done.set_tooltip_text("Xem mọi việc đã hoàn thành")
        self.foot_done.connect("clicked", lambda *_: self._set_smart("done"))
        foot.append(self.foot_done)
        for label, tip, fn in [
            ("🗑  Thùng rác", "Việc đã xoá nằm ở đây 30 ngày — khôi phục được",
             lambda *_: TrashDialog(self, self.refresh).present()),
            ("🏷  Quản lý nhãn", "Đổi tên / gỡ nhãn cho mọi việc cùng lúc",
             lambda *_: TagsDialog(self, self.refresh).present()),
            ("✎  Tên mức ưu tiên", "Tự đặt tên 4 mức ưu tiên theo ý bạn",
             lambda *_: LabelsDialog(self, self.refresh).present()),
            ("⇄  Đồng bộ · Sao lưu", "Đồng bộ với máy kia qua Tailscale, xuất/nhập JSON, khôi phục sao lưu (engine cũng tự sao lưu mỗi ngày)",
             lambda *_: SyncDialog(self, self.refresh).present()),
            ("❓  Hướng dẫn sử dụng", "Bắt việc siêu nhanh, cú pháp gõ tắt, các màn hình, nhắc việc và an toàn dữ liệu",
             lambda *_: WelcomeDialog(self).present()),
            ("⚙  Cài đặt · Telegram & AI", "Nối Telegram để nhắc việc về điện thoại + API key Gemini cho nút ✨ AI điền form",
             lambda *_: SettingsDialog(self).present()),
        ]:
            b = Gtk.Button(label=label); b.add_css_class("sb2row")
            _bl = b.get_child()
            if _bl: _bl.set_xalign(0)
            b.set_tooltip_text(tip)
            b.connect("clicked", fn)
            foot.append(b)
        sb.append(foot)
        note = Gtk.Label(label=f"Shini Tasks v{VERSION} · Alt+E: bắt việc siêu nhanh", xalign=0)
        note.add_css_class("sb-note"); note.set_margin_top(8)
        sb.append(note)
        return sb

    def _render_sidebar_lists(self):
        # Hàng THÔNG MINH + hàng chuyển VIEW (Lịch/Thống kê là view ở vùng giữa,
        # không phải bộ lọc) — cùng một kiểu hàng cho gọn mắt như Todoist.
        counts = {k: sum(1 for t in self.all_tasks if self._smart_ok(t, k)) for k, *_ in self.SMART_DEFS}
        counts["all"] = sum(1 for t in self.all_tasks if t["status"] != "done")
        counts["done"] = sum(1 for t in self.all_tasks if t["status"] == "done")
        for c in _kids(self.smart_box): self.smart_box.remove(c)
        defs = [(k, icon, label) for k, icon, _c, label in self.SMART_DEFS if k != "done"]
        defs += [("calendar", "📅", "Lịch"), ("stats", "📊", "Thống kê")]
        for key, icon, label in defs:
            b = Gtk.Button(); b.add_css_class("sb2row")
            is_view = key in ("calendar", "stats")
            active = (self.view_mode == key) if is_view else \
                     (self.view_mode in ("board", "list") and self.smart == key)
            if active: b.add_css_class("sb2row-on")
            row = Gtk.Box(spacing=9)
            row.append(Gtk.Label(label=icon))
            lab = Gtk.Label(label=label, xalign=0); lab.add_css_class("smartlab"); lab.set_hexpand(True)
            lab.set_ellipsize(Pango.EllipsizeMode.END)
            row.append(lab)
            if not is_view:
                row.append(Gtk.Label(label=str(counts.get(key, 0)), css_classes=["smartnum"]))
            b.set_child(row)
            if is_view:
                b.connect("clicked", lambda *_ , k=key: self._set_view(k))
            else:
                b.connect("clicked", lambda *_ , k=key: self._set_smart(k))
            self.smart_box.append(b)
        self.foot_done_num.set_text(str(counts["done"]))
        (self.foot_done.add_css_class if self.smart == "done" and self.view_mode in ("board", "list")
         else self.foot_done.remove_css_class)("sb2row-on")
        self._render_pins()

    def _render_pins(self):
        # Mục ĐÃ GHIM: việc được ghim (📌 trong panel chi tiết) — như mục
        # Favorites của Todoist/Linear. Bấm là mở panel của việc đó.
        for c in _kids(self.pin_box): self.pin_box.remove(c)
        pins = [t for t in self.all_tasks if t.get("pinned") and t["status"] != "done"]
        pins.sort(key=lambda t: -t["score"])
        if not pins:
            e = Gtk.Label(label="Chưa ghim việc nào — mở một việc, bấm 📌 để ghim lên đây.", xalign=0)
            e.add_css_class("sb-note"); e.set_wrap(True)
            self.pin_box.append(e)
            return
        for t in pins:
            b = Gtk.Button(); b.add_css_class("sb2row")
            if getattr(self, "selected_id", None) == t["id"]: b.add_css_class("sb2row-on")
            row = Gtk.Box(spacing=9)
            row.append(Gtk.Label(label="📌"))
            lab = Gtk.Label(label=t["title"], xalign=0); lab.add_css_class("smartlab"); lab.set_hexpand(True)
            lab.set_ellipsize(Pango.EllipsizeMode.END)
            row.append(lab)
            b.set_child(row)
            b.set_tooltip_text("Mở việc đã ghim này")
            b.connect("clicked", lambda *_ , tt=t: self._open_pinned(tt))
            self.pin_box.append(b)

    def _open_pinned(self, t):
        if t.get("project_id") and t["project_id"] != self.cur_project:
            self._set_project(t["project_id"])
        self.open_task(t)

    def _clear_filters(self, *_):
        self._updating = True
        self.search.set_text("")
        self.tag_drop.set_selected(0)
        self._updating = False
        self.q_text = ""; self.f_tag = None; self.f_date = None; self.f_assignee = None
        self.assignee_drop.set_selected(0)
        if self.f_overdue:
            self.f_overdue = False; self.over_btn.set_active(False)
        self.refresh()

    def _render_month(self):
        for c in _kids(self.cal_box): self.cal_box.remove(c)
        t = today_()
        head = Gtk.Label(label=f"Tháng {t.month}/{t.year}", xalign=0); head.add_css_class("cal-h")
        self.cal_box.append(head)
        dow = Gtk.Box(spacing=2)
        for d in ["T2","T3","T4","T5","T6","T7","CN"]:
            l = Gtk.Label(label=d); l.add_css_class("cal-dow"); l.set_size_request(26, -1); dow.append(l)
        self.cal_box.append(dow)
        due_days = {}
        for task in self.all_tasks:
            if task.get("due_date"): due_days[task["due_date"]] = due_days.get(task["due_date"], 0) + 1
        for week in calendar.Calendar(firstweekday=0).monthdatescalendar(t.year, t.month):
            rowb = Gtk.Box(spacing=2)
            for d in week:
                if d.month != t.month:
                    l = Gtk.Label(label=""); l.set_size_request(26, 26); rowb.append(l); continue
                iso = d.isoformat()
                mark = "●" if iso in due_days else ""
                b = Gtk.Button()
                b.set_size_request(26, 26)
                b.add_css_class("cal-day")
                if d == t: b.add_css_class("cal-today")
                if self.f_date == iso: b.add_css_class("cal-sel")
                child = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
                n = Gtk.Label(label=str(d.day)); n.set_halign(Gtk.Align.CENTER); n.add_css_class("cal-num")
                dotl = Gtk.Label(label=mark); dotl.set_halign(Gtk.Align.CENTER)
                dotl.set_markup(f'<span foreground="#F87171" size="6000">{mark}</span>' if mark else "")
                child.append(n); child.append(dotl)
                b.set_child(child)
                b.connect("clicked", lambda *_ , iso=iso: self._toggle_date_filter(iso))
                rowb.append(b)
            self.cal_box.append(rowb)

    # (Biểu đồ "việc xong 7 ngày" từng ở sidebar đã gỡ theo template Todoist
    # 2026-11-16 — biểu đồ ngày đầy đủ có ở trang Thống kê.)

    # ---------- Lọc / tìm ----------
    def _passes(self, t):
        if not self._smart_ok(t, self.smart): return False
        if self.q_text and self.q_text.lower() not in (t["title"] + " " + (t.get("notes") or "")).lower(): return False
        if self.f_tag and self.f_tag not in (t.get("tags") or []): return False
        if self.f_assignee and (t.get("assignee") or "") != self.f_assignee: return False
        if self.f_overdue and not is_overdue(t): return False
        if self.f_date and t.get("due_date") != self.f_date: return False
        return True

    def _on_search(self, *_):
        self.q_text = self.search.get_text().strip(); self.refresh()
    def _on_search_enter(self, *_):
        # Enter trong ô tìm = mở TÌM MỌI NƠI (mọi dự án, cả việc đã xong và
        # bình luận) — ô tìm thường chỉ lọc việc đang hiện trên bảng
        q = self.search.get_text().strip()
        if q: SearchDialog(self, q).present()
    def _on_tag(self, *_):
        if getattr(self, "_updating", False): return
        tags = self._tag_list()
        i = self.tag_drop.get_selected()
        self.f_tag = tags[i] if 0 < i <= len(tags) else None
        self.refresh()
    def _on_assignee(self, *_):
        if getattr(self, "_updating", False): return
        people = getattr(self, "_people_cache", [])
        i = self.assignee_drop.get_selected()
        self.f_assignee = people[i - 1] if 0 < i <= len(people) else None
        self.refresh()

    def _on_sort(self, *_):
        self.sort_mode = self.sort_drop.get_selected(); self.refresh()
    def _on_over(self, *_):
        self.f_overdue = self.over_btn.get_active(); self.refresh()
    def _toggle_date_filter(self, iso):
        self.f_date = None if self.f_date == iso else iso
        self.refresh()
    def _tag_list(self):
        return sorted({x for t in self.all_tasks for x in (t.get("tags") or [])})

    def _on_key(self, _ctl, keyval, _code, state):
        ctrl = state & Gdk.ModifierType.CONTROL_MASK
        name = Gdk.keyval_name(keyval) or ""
        if not ctrl:
            if name == "Escape" and getattr(self, "pane", None) and self.pane.task:
                self.request_close_pane(); return True
            return False
        if name in ("n", "N"):
            self.new_task(); return True
        if name in ("f", "F", "k", "K"):
            self.search.grab_focus(); return True
        if name in ("r", "R"):
            self.refresh(); return True
        if name in ("b", "B"):
            self._toggle_sidebar(); return True
        return False

    def _toggle_sidebar(self):
        """Ẩn/hiện TOÀN BỘ thanh bên (cả cụm) — bảng việc giãn ra hết cỡ khi ẩn."""
        SETTINGS["sidebar"] = not SETTINGS.get("sidebar", True)
        save_settings(SETTINGS)
        self.sb_scroll.set_visible(SETTINGS["sidebar"])

    # ---------- Dữ liệu ----------
    def _safe(self, fn, *a):
        try: return fn(*a)
        except Exception as e: print("api error:", e); return None

    def _tick(self):
        self.refresh(maybe=True); return True

    def refresh(self, maybe=False):
        try:
            open_ = api("GET", "/api/tasks?view=all")["tasks"]
            done = api("GET", "/api/tasks?view=done")["tasks"]
            stats = api("GET", "/api/stats")
            columns = api("GET", "/api/columns")["columns"]
        except Exception:
            # Engine mất kết nối (audit 2026-11-17 mục A7): hiện nhãn báo
            # trên headerbar và thử tự khởi động lại dịch vụ MỘT lần cho
            # mỗi đợt mất (Linux/systemd — máy của người dùng có unit
            # shini-tasks); các tick sau chỉ chờ, không spam lệnh.
            self._eng_fails = getattr(self, "_eng_fails", 0) + 1
            if getattr(self, "conn_lbl", None) is not None:
                self.conn_lbl.set_visible(True)
            if self._eng_fails == 2 and not IS_WIN:
                try:
                    subprocess.run(["systemctl", "--user", "start", "shini-tasks"],
                                   capture_output=True, timeout=10)
                except Exception: pass
            if not maybe: self._render_error()
            return
        self._eng_fails = 0
        if getattr(self, "conn_lbl", None) is not None:
            self.conn_lbl.set_visible(False)
        self.all_tasks = open_ + done
        # Việc đang mở ở panel mà bị xoá nơi khác (thùng rác) -> đóng panel
        if getattr(self, "pane", None) is not None and self.pane.task and \
           self.pane.task["id"] not in {t["id"] for t in self.all_tasks}:
            self.selected_id = None
            self.pane.close()
        self.stats = stats
        self.columns = columns
        try: self.projects = api("GET", "/api/projects")["projects"]
        except Exception: pass   # engine cũ chưa có dự án — giữ danh sách đã có
        _pids = [p["id"] for p in self.projects]
        if self.cur_project not in _pids:
            self.cur_project = _pids[0] if _pids else None
        if stats.get("update_available"):
            self.upd_btn.set_label(f"⬆ Bản mới {stats.get('latest_version', '')}")
            self.upd_btn.set_visible(True)
        else:
            self.upd_btn.set_visible(False)
        try: self.done_archive = api("GET", "/api/done-archive")["tasks"]
        except Exception: pass   # engine cũ chưa có endpoint này — giữ bản đã có
        h = json.dumps([self.all_tasks, self.done_archive, stats, columns, self.projects, self.cur_project,
                        SETTINGS, self.q_text, self.f_tag,
                        self.f_overdue, self.f_date, self.sort_mode], sort_keys=True, ensure_ascii=False)
        if maybe and h == self._last_hash: return
        self._last_hash = h
        self._render()

    def _open_update(self, *_):
        url = (self.stats or {}).get("latest_url")
        if url:
            try: Gtk.UriLauncher(uri=url).launch(None, None, None)
            except Exception: pass

    def _render_error(self):
        self._board_structure = None; self._board_cache = {}
        for c in _kids(self.board): self.board.remove(c)
        l = Gtk.Label(label="Chưa kết nối được engine nhắc việc (server.py cổng 8790).\nKiểm tra: systemctl --user status shini-tasks")
        self.board.append(l)

    def _col_style(self, col):
        cid = col["id"]
        if cid in self._col_providers: return
        color = col["color"]; txt = contrast_text(color)
        prov = Gtk.CssProvider()
        css_load(prov, f".coldot-{cid} {{ background: {color}; }} .colcnt-{cid} {{ background: {color}; color: {txt}; }}".encode())
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), prov, Gtk.STYLE_PROVIDER_PRIORITY_USER - 1)
        self._col_providers[cid] = prov

    # ---------- Vẽ bảng theo TỪNG CỘT (GĐ2 — incremental render) ----------
    @staticmethod
    def _col_sig(tasks, filtering):
        """Chữ ký nội dung một cột: đủ mọi trường làm nên hình hài thẻ, để biết
        cột có thật sự đổi không mà dựng lại."""
        return (filtering, tuple(
            (t["id"], t.get("title"), t.get("notes"), t["status"], t.get("due_date"),
             t.get("due_time"), t.get("estimate_min"), t.get("repeat_rule"),
             t.get("important"), t.get("urgent"), tuple(t.get("tags") or []),
             json.dumps(t.get("subtasks") or [], ensure_ascii=False, sort_keys=True),
             t.get("comment_count"), t.get("attach_count"), t.get("assignee"),
             t.get("start_date"), t.get("score"), t.get("pinned"),
             t.get("actual_min"), t.get("timer_start")) for t in tasks))

    def _add_tile(self):
        add = Gtk.Button()
        add.add_css_class("addcol")
        add.set_size_request(120, -1)
        add.set_vexpand(True)
        inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        inner.set_valign(Gtk.Align.CENTER); inner.set_halign(Gtk.Align.CENTER)
        plus = Gtk.Label(label="＋"); plus.set_markup('<span size="18000">＋</span>')
        inner.append(plus)
        inner.append(Gtk.Label(label="Thêm cột"))
        add.set_child(inner)
        add.connect("clicked", lambda *_: ColumnDialog(self, None, self.refresh).present())
        return add

    def _sync_board(self, by, done_list, filtering):
        """Chỉ dựng lại CỘT NÀO có nội dung đổi; cột không đổi giữ nguyên cây
        widget (bản cũ dựng lại toàn bộ thẻ mỗi lần vẽ — tốn và là nguồn lag).
        Cấu trúc (danh sách cột/màu/tên mức/theme) đổi thì mới làm lại từ đầu."""
        structure = (tuple((c["id"], c["name"], c["color"]) for c in getattr(self, "_board_cols", self.columns)),
                     self.focus_col, self.smart, SETTINGS.get("theme"), self.cur_project,
                     tuple(SETTINGS["labels"][lv] for lv in ("L1", "L2", "L3", "L4")),
                     getattr(self, "selected_id", None), self.sort_mode)
        if structure != getattr(self, "_board_structure", None):
            self._board_structure = structure
            self._board_cache = {}
        wanted = []
        if self.smart == "done":
            # Mục ĐÃ XONG (v1.5.0): bảng chỉ còn đúng cột việc đã xong — cột
            # ĐÃ XONG không còn đứng lẫn với các cột đang làm như trước.
            wanted.append((("done",), self._col_sig(done_list, filtering),
                           lambda: self._column_widget(None, done_list, filtering)))
        else:
            for col in getattr(self, "_board_cols", self.columns):
                if self.focus_col is not None and col["id"] != self.focus_col: continue
                key = ("col", col["id"])
                wanted.append((key, self._col_sig(by[col["id"]], filtering),
                               lambda col=col: self._column_widget(col, by[col["id"]], filtering)))
            if self.focus_col is None:
                # Cột ĐÃ XONG đứng cuối bảng (Sinh muốn hiện lại 2026-11-17).
                # Việc xong quá 15 ngày tự rời cột: engine dọn hằng ngày vào
                # done_archive (vẫn tính thống kê) — xem purge_old_done.
                wanted.append((("done",), self._col_sig(done_list, filtering),
                               lambda: self._column_widget(None, done_list, filtering)))
            wanted.append((("__add__",), "static", self._add_tile))
        new_children = []
        for key, sig, build in wanted:
            ent = self._board_cache.get(key)
            if ent and ent[0] == sig:
                new_children.append(ent[1])
            else:
                w = build()
                self._board_cache[key] = (sig, w)
                new_children.append(w)
        cur = _kids(self.board)
        if len(cur) == len(new_children) and all(a is b for a, b in zip(cur, new_children)):
            return  # không cột nào đổi — giữ nguyên, khỏi đụng vào cây widget
        for ch in cur: self.board.remove(ch)
        for w in new_children: self.board.append(w)

    def _render(self):
        tags = self._tag_list()
        cur = self.tag_drop.get_selected()
        self._updating = True
        self.tag_drop.set_model(Gtk.StringList.new(["Tất cả nhãn"] + tags))
        if self.f_tag in tags: self.tag_drop.set_selected(tags.index(self.f_tag) + 1)
        elif cur and cur <= len(tags): self.tag_drop.set_selected(cur)
        self._updating = False
        _people = sorted({t["assignee"] for t in self.all_tasks if t.get("assignee")})
        if getattr(self, "_people_cache", None) != _people:
            self._people_cache = _people
            self._updating = True
            self.assignee_drop.set_model(Gtk.StringList.new(["Tất cả mọi người"] + _people))
            if self.f_assignee in _people:
                self.assignee_drop.set_selected(_people.index(self.f_assignee) + 1)
            self._updating = False
        shown = [t for t in self.all_tasks if self._passes(t)]
        filtering = bool(self.q_text or self.f_tag or self.f_assignee or self.f_overdue or self.f_date
                         or self.smart != "all" or self.focus_col is not None)
        # Bảng cột chỉ hiện việc + cột của DỰ ÁN đang chọn (các góc nhìn khác —
        # Hôm nay / Lịch / Thống kê — vẫn gồm mọi dự án)
        shown = [t for t in shown if (t.get("project_id") or self.cur_project) == self.cur_project]
        self._board_cols = [c for c in self.columns if c.get("project_id") == self.cur_project] or list(self.columns)
        bits = []
        smart_names = {k: lbl for k, _i, _c, lbl in self.SMART_DEFS}
        if self.smart != "all": bits.append(f"mục {smart_names.get(self.smart, '')}")
        if self.q_text: bits.append(f"tìm “{self.q_text}”")
        if self.f_tag: bits.append(f"nhãn #{self.f_tag}")
        if self.f_assignee: bits.append(f"người làm: {self.f_assignee}")
        if self.f_overdue: bits.append("chỉ quá hạn")
        if self.f_date: bits.append(f"ngày {self.f_date[8:10]}/{self.f_date[5:7]} (bấm lại ngày đó để bỏ lọc)")
        self.filter_lab.set_text(("Đang lọc: " + " · ".join(bits)) if bits else "")
        if self.focus_col is not None:
            fc = next((c["name"] for c in self.columns if c["id"] == self.focus_col), "")
            self.focus_lab.set_text(f"📌 Đang chỉ xem cột: {fc}")
            self.focus_bar.set_visible(True)
        else:
            self.focus_bar.set_visible(False)

        col_ids = [c["id"] for c in self._board_cols]
        first_id = col_ids[0] if col_ids else None
        by = {cid: [] for cid in col_ids}
        done_list = []
        for t in shown:
            if t["status"] == "done": done_list.append(t)
            else: by[t.get("column_id") if t.get("column_id") in by else first_id].append(t)
        for cid in by:
            if self.sort_mode == 1:
                by[cid].sort(key=lambda t: (t.get("due_date") or "9999", -(t["score"])))
            else:
                by[cid].sort(key=lambda t: -(t["score"]))
        done_list.sort(key=lambda t: t.get("done_at") or "", reverse=True)
        self._sync_board(by, done_list, filtering)
        if self.view_mode == "list": self._render_list()

        _p = next((p for p in self.projects if p["id"] == self.cur_project), None)
        self.crumb_lab.set_text(f"Dự án / {(_p or {}).get('name', '')}")
        self.vh_title.set_text((_p or {}).get("name", ""))
        self._vh_dot_style((_p or {}).get("color") or "#60A5FA")
        self.quick.set_placeholder_text(
            f"Thêm nhanh vào {(_p or {}).get('name', 'dự án')}… gõ tắt: mai 9h họp !gấp #nhãn 30p — rồi Enter")
        self._render_projects()
        self._render_sidebar_lists()
        self._render_month()
        if self.view_mode == "calendar": self._render_calendar()
        if self.view_mode == "today": self._render_today()
        if self.view_mode == "mindmap": self._mm_snap = True; self._render_mindmap()
        if self.view_mode == "stats": self._render_stats()

    # ---------- Chế độ LỊCH (lưới thời gian kiểu Google Calendar) ----------
    def _set_view(self, mode):
        # Cờ chống đệ quy: set_active() bên dưới tự nó phát lại signal "toggled";
        # bản cũ thiếu cờ này nên mỗi lần chuyển chế độ xem tự gọi lồng nhau ~1000 lần
        # (tới RecursionError) — đó là lý do chuyển Cột/Lịch bị chậm thấy rõ.
        if mode == self.view_mode or getattr(self, "_switching", False): return
        self._switching = True
        try:
            self.view_mode = mode
            for btn, m in ((self.btn_board, "board"), (self.btn_list, "list"), (self.btn_cal, "calendar"),
                           (self.btn_today, "today"),
                           (self.btn_map, "mindmap"), (self.btn_stats, "stats")):
                btn.set_active(m == mode)
                (btn.add_css_class if m == mode else btn.remove_css_class)("viewtab-on")
            self.stack.set_visible_child_name(mode)
            if mode == "list": self._render_list()
            if mode == "calendar": self._render_calendar()
            if mode == "today": self._render_today()
            if mode == "mindmap": self._mm_snap = True; self._render_mindmap()
            if mode == "stats": self._render_stats()
        finally:
            self._switching = False

    def _set_gran(self, gran):
        if gran == self.cal_gran or getattr(self, "_switching", False): return
        self._switching = True
        try:
            self.cal_gran = gran
            for btn, g in ((self.gran_week, "week"), (self.gran_day, "day"), (self.gran_month, "month")):
                btn.set_active(g == gran)
                (btn.add_css_class if g == gran else btn.remove_css_class)("viewbtn-on")
            self._render_calendar()
        finally:
            self._switching = False

    # ---------- Trang HÔM NAY (GĐ1) ----------
    def _render_today(self):
        """Gom việc đang mở theo 4 nhóm: Quá hạn / Đang làm / Hôm nay có giờ /
        Chưa xếp giờ · chưa có hạn. Mỗi việc chỉ rơi vào nhóm ĐẦU TIÊN khớp,
        tôn trọng bộ lọc hiện tại như các trang khác."""
        box = self.today_box
        for c in _kids(box): box.remove(c)
        today = today_().isoformat()
        open_ = [t for t in self.all_tasks if t["status"] != "done" and self._passes(t)]
        used = set()
        def take(pred):
            out = [t for t in open_ if t["id"] not in used and pred(t)]
            used.update(t["id"] for t in out)
            return out
        overdue = take(is_overdue)
        overdue.sort(key=lambda t: (t.get("due_date") or "", t.get("due_time") or ""))
        groups = [
            ("⚠ Quá hạn", overdue),
            ("▶ Đang làm", take(lambda t: t["status"] == "doing")),
            ("☀ Hôm nay", sorted(take(lambda t: t.get("due_date") == today and t.get("due_time")),
                                 key=lambda t: t["due_time"])),
            ("📥 Chưa xếp giờ · chưa có hạn", sorted(
                take(lambda t: (t.get("due_date") == today and not t.get("due_time")) or not t.get("due_date")),
                key=lambda t: -t["score"])),
        ]
        shown_any = False
        for name, items in groups:
            if not items: continue
            shown_any = True
            hdr = Gtk.Box(spacing=8)
            h = Gtk.Label(label=name, xalign=0); h.add_css_class("today-h"); hdr.append(h)
            cnt = Gtk.Label(label=str(len(items))); cnt.add_css_class("today-cnt"); hdr.append(cnt)
            box.append(hdr)
            for t in items: box.append(self._card(t))
        if not shown_any:
            e = Gtk.Label(label="🎉 Hôm nay không còn việc nào đang mở — thư giãn thôi!", xalign=0.5)
            e.add_css_class("empty")
            box.append(e)

    # ---------- Trang THỐNG KÊ (hướng B) ----------
    def _kpi(self, num, cap):
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        card.add_css_class("statcard"); card.set_hexpand(True)
        n = Gtk.Label(label=str(num), xalign=0); n.add_css_class("statnum"); card.append(n)
        c = Gtk.Label(label=cap, xalign=0, wrap=True); c.add_css_class("mut"); card.append(c)
        return card

    def _render_stats(self):
        """Số liệu thật từ dữ liệu hiện có: done_at (ngày xong), due_date (hạn),
        estimate_min (ước lượng) và — từ v1.4.0 — actual_min do đồng hồ bấm
        giờ ghi lại, hiện riêng một dòng để không lẫn thật với ước lượng."""
        box = self.stats_box
        for c in _kids(box): box.remove(c)
        s = self.stats
        tasks = self.all_tasks
        today = today_()
        done_tasks = [t for t in tasks if t["status"] == "done"] + list(getattr(self, "done_archive", []))
        with_due = [t for t in done_tasks if t.get("due_date") and t.get("done_at")]
        ontime = len([t for t in with_due if t["done_at"][:10] <= t["due_date"]])
        late = [t for t in with_due if t["done_at"][:10] > t["due_date"]]
        late_avg = (sum((date.fromisoformat(t["done_at"][:10]) - date.fromisoformat(t["due_date"])).days
                        for t in late) / len(late)) if late else 0
        pct = round(ontime / len(with_due) * 100) if with_due else None
        kpis = Gtk.Box(spacing=10)
        kpis.append(self._kpi(s.get("streak", 0), "🔥 ngày liền có việc xong"))
        kpis.append(self._kpi(s.get("done_this_week", 0), f"✅ xong tuần này (tuần trước: {s.get('done_last_week', 0)})"))
        kpis.append(self._kpi(f"{pct}%" if pct is not None else "—", "🎯 xong đúng hạn"))
        kpis.append(self._kpi(s.get("open", 0), f"📂 đang mở · ⚠ {s.get('overdue', 0)} quá hạn · ⏰ {s.get('due_soon', 0)} sắp đến hạn"))
        kpis.append(self._kpi(f"{s.get('completion_rate', 0)}%", "🏁 tỉ lệ hoàn thành (mọi thời gian)"))
        box.append(kpis)
        if s.get("actual_done_min") or s.get("estimate_done_min"):
            _tl = (f"⏱ Việc đã xong — làm thật: {s.get('actual_done_min', 0)} phút · "
                   f"ước lượng: {s.get('estimate_done_min', 0)} phút")
            if s.get("timers_running"): _tl += f" · ⏱ đang bấm giờ {s['timers_running']} việc"
            box.append(Gtk.Label(label=_tl, xalign=0, css_classes=["mut"]))
        if s.get("rated_count"):
            box.append(Gtk.Label(label=f"⭐ Đánh giá việc đã xong: trung bình {s.get('avg_rating', 0)}/5 "
                                       f"qua {s['rated_count']} việc đã chấm sao (chấm trong popup chi tiết)",
                                 xalign=0, css_classes=["mut"]))
        # Theo TRẠNG THÁI + theo MỨC ƯU TIÊN (gói KimesFlow: dashboard phân tích)
        bs = s.get("by_status") or {}
        bp = s.get("by_priority") or []
        if bs or bp:
            h0 = Gtk.Label(label="Theo trạng thái · Theo mức ưu tiên", xalign=0); h0.add_css_class("today-h"); box.append(h0)
            groups = [("Chưa làm", bs.get("todo", 0)), ("Đang làm", bs.get("doing", 0)), ("Đã xong", bs.get("done", 0))]
            groups += [(SETTINGS["labels"][lv], bp[i] if i < len(bp) else 0)
                       for i, lv in enumerate(("L1", "L2", "L3", "L4"))]
            gmx = max([n for _n, n in groups], default=0) or 1
            for nm, n in groups:
                row = Gtk.Box(spacing=10)
                lab = Gtk.Label(label=nm, xalign=0); lab.set_size_request(190, -1)
                lab.set_ellipsize(Pango.EllipsizeMode.END); row.append(lab)
                bar = Bar(); bar.set_fraction(n / gmx); bar.set_hexpand(True); bar.set_valign(Gtk.Align.CENTER)
                row.append(bar)
                row.append(Gtk.Label(label=f"{n} việc", css_classes=["mut"]))
                box.append(row)
        h1 = Gtk.Label(label="Việc xong — 14 ngày qua", xalign=0); h1.add_css_class("today-h"); box.append(h1)
        done_by = {}
        for t in done_tasks:
            if t.get("done_at"): done_by[t["done_at"][:10]] = done_by.get(t["done_at"][:10], 0) + 1
        days14 = [today - timedelta(days=i) for i in range(13, -1, -1)]
        chart = BarsChart()
        chart.set_data([(d.strftime("%d/%m"), done_by.get(d.isoformat(), 0)) for d in days14])
        box.append(chart)
        h2 = Gtk.Label(label="Theo cột", xalign=0); h2.add_css_class("today-h"); box.append(h2)
        colrows = []
        for col in self.columns:
            dn = len([t for t in done_tasks if t.get("column_id") == col["id"]])
            op = [t for t in tasks if t["status"] != "done" and t.get("column_id") == col["id"]]
            est = sum(t.get("estimate_min") or 60 for t in op)
            colrows.append((col["name"], dn, len(op), est))
        mx = max([dn for _n, dn, _o, _e in colrows], default=0) or 1
        for nm, dn, op, est in colrows:
            row = Gtk.Box(spacing=10)
            lab = Gtk.Label(label=nm, xalign=0); lab.set_size_request(190, -1)
            lab.set_ellipsize(Pango.EllipsizeMode.END); row.append(lab)
            bar = Bar(); bar.set_fraction(dn / mx); bar.set_hexpand(True); bar.set_valign(Gtk.Align.CENTER)
            row.append(bar)
            row.append(Gtk.Label(label=f"xong {dn} · đang mở {op} (~{est // 60}g{est % 60:02d}p chưa làm)", css_classes=["mut"]))
            box.append(row)
        notes = []
        stale = s.get("stale_columns") or []
        if stale: notes.append(f"⏳ Cột ứ nhất: {stale[0]['column']} — việc cũ nhất đã {stale[0]['oldest_days']} ngày chưa xong.")
        if late: notes.append(f"🎯 Đã xong trễ {len(late)} việc, trễ trung bình {late_avg:.1f} ngày.")
        elif with_due: notes.append("🎯 Mọi việc có hạn đã xong đều đúng hạn — tốt lắm!")
        open_est = sum(t.get("estimate_min") or 60 for t in tasks if t["status"] != "done")
        notes.append(f"🕐 Tổng thời lượng ước tính của việc đang mở: ~{open_est // 60} giờ {open_est % 60} phút (ước lượng — đo thời gian thật thuộc hướng A).")
        na = s.get("archived_done") or 0
        if na: notes.append(f"🧹 Đã tự xoá {na} việc xong quá 15 ngày khỏi bảng — vẫn tính đầy đủ trong thống kê này.")
        nl = Gtk.Label(label="\n".join(notes), xalign=0, wrap=True); nl.add_css_class("mut"); box.append(nl)
        brow = Gtk.Box(spacing=8)
        bexp = Gtk.Button(label="📸 Xuất báo cáo tuần (PNG)"); bexp.add_css_class("suggested-action")
        bexp.connect("clicked", self._export_report)
        brow.append(bexp)
        bai = Gtk.Button(label="✨ AI nhận xét tuần"); bai.add_css_class("dlgbtn")
        bai.set_tooltip_text("Gửi số liệu tuần cho Gemini (key của bạn, ở Cài đặt) — nhận nhận xét + gợi ý tuần tới")
        bai.connect("clicked", self._ai_week)
        brow.append(bai)
        brow.append(Gtk.Label(label="Lưu vào thư mục Pictures/Shini Tasks", css_classes=["mut"]))
        box.append(brow)

    # ---------- AI nhận xét tuần (gói D audit 2026-11-17) ----------
    def _ai_week(self, *_):
        key = SETTINGS.get("gemini_key") or ""
        if not key:
            self._toast("Chưa có Gemini API key — dán key (miễn phí) trong ⚙ Cài đặt ở thanh bên trước đã")
            SettingsDialog(self).present()
            return
        self._toast("✨ AI đang đọc số liệu tuần…")
        threading.Thread(target=self._ai_week_worker, args=(key,), daemon=True).start()

    def _ai_week_worker(self, key):
        try:
            st = self.stats or {}
            week_ago = (today_() - timedelta(days=7)).isoformat()
            done7 = [t for t in self.all_tasks if t["status"] == "done"
                     and (t.get("done_at") or "") >= week_ago]
            overdue = [t for t in self.all_tasks if is_overdue(t)]
            open_t = [t for t in self.all_tasks if t["status"] != "done"]
            facts = (
                f"Tổng quan: đang mở {st.get('open', len(open_t))} việc, đã xong tất cả {st.get('done_total', 0)} việc, "
                f"tỉ lệ hoàn thành {st.get('completion_rate', 0)}%, điểm sao trung bình {st.get('avg_rating', 0)}.\n"
                f"7 ngày qua xong {len(done7)} việc: " + "; ".join(t["title"] for t in done7[:12]) + "\n"
                f"Đang quá hạn {len(overdue)} việc: " + "; ".join(t["title"] for t in overdue[:8]) + "\n"
                f"Việc đang mở tiêu biểu: " + "; ".join(t["title"] for t in open_t[:12]))
            prompt = ("Bạn là trợ lý quản lý việc cá nhân. Dựa trên số liệu thật dưới đây, viết một nhận xét "
                      "tiếng Việt NGẮN GỌN (150–220 chữ), văn xuôi liền mạch, KHÔNG markdown, theo mạch: "
                      "tuần qua làm được gì đáng ghi nhận → điểm nghẽn rõ nhất (nêu tên việc cụ thể) → "
                      "đúng 3 gợi ý hành động cho tuần tới. Giọng thẳng thắn, khích lệ vừa phải, không sáo rỗng.\n\n"
                      + facts)
            payload = {"contents": [{"parts": [{"text": prompt}]}],
                       "generationConfig": {"temperature": 0.4}}
            req = urllib.request.Request(
                "https://generativelanguage.googleapis.com/v1beta/models/"
                f"gemini-2.0-flash:generateContent?key={key}",
                data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=30) as r:
                out = json.loads(r.read().decode())
            text = out["candidates"][0]["content"]["parts"][0]["text"].strip()
            GLib.idle_add(self._ai_week_done, text, None)
        except Exception as e:
            GLib.idle_add(self._ai_week_done, None, str(e)[:140])

    def _ai_week_done(self, text, err):
        if err or not text:
            self._toast(f"✨ AI chưa nhận xét được ({err or 'phản hồi lạ'})")
            return False
        dlg = Gtk.Window(title="✨ AI nhận xét tuần", transient_for=self, modal=True)
        dlg.set_default_size(520, -1)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_margin_top(16); box.set_margin_bottom(16); box.set_margin_start(16); box.set_margin_end(16)
        lab = Gtk.Label(label=text, xalign=0, wrap=True, selectable=True)
        box.append(lab)
        ok = Gtk.Button(label="Đóng"); ok.add_css_class("dlgbtn")
        ok.set_halign(Gtk.Align.END)
        ok.connect("clicked", lambda *_: dlg.close())
        box.append(ok)
        dlg.set_child(box)
        dlg.present()
        return False

    def _export_report(self, *_):
        try:
            path = export_week_report(self)
            self._toast(f"📸 Đã lưu báo cáo tuần: {path}")
        except Exception as e:
            self._toast(f"⚠ Xuất báo cáo thất bại: {e}")

    # ---------- Tự xếp lịch (GĐ3) ----------
    def _auto_schedule(self, *_):
        """Điền giờ cho các việc CHƯA XẾP GIỜ trong khoảng đang xem (kể cả việc
        quá hạn) vào ô trống 07:00–21:00, điểm ưu tiên cao xếp trước, không bao
        giờ xếp trùng — dùng chính find_conflict như khi xếp tay."""
        days = self._cal_days()
        day_isos = [d.isoformat() for d in days]
        cands = [t for t in self.all_tasks if t["status"] != "done" and not t.get("due_time")
                 and self._passes(t) and t.get("due_date")
                 and (t["due_date"] in day_isos or (self.cal_gran == "week" and is_overdue(t)))]
        cands.sort(key=lambda t: -t["score"])
        if not cands:
            self._toast("Không có việc nào chưa xếp giờ trong khoảng đang xem")
            return
        placed = 0
        for t in cands:
            dur = t.get("estimate_min") or 60
            start_day = t["due_date"] if t["due_date"] in day_isos else day_isos[0]
            i0 = day_isos.index(start_day)
            order = day_isos[i0:] + day_isos[:i0]
            if not is_overdue(t):
                order = [d for d in order if d >= t["due_date"]]  # không xếp sớm hơn ngày hạn
            done_ = False
            for diso in order:
                for smin in range(7 * 60, 21 * 60, 30):
                    if find_conflict(self.all_tasks, diso, smin, dur, exclude_id=t["id"]): continue
                    self._safe(api, "PATCH", f"/api/tasks/{t['id']}",
                               {"due_date": diso, "due_time": min_to_hm(smin)})
                    # cập nhật ngay bản trong bộ nhớ để việc xếp sau thấy ô đã kín
                    t["due_date"], t["due_time"] = diso, min_to_hm(smin)
                    placed += 1; done_ = True
                    break
                if done_: break
        self.refresh()
        msg = f"⚡ Đã tự xếp giờ cho {placed}/{len(cands)} việc"
        if placed < len(cands): msg += " — số còn lại không còn ô trống vừa trong tuần này"
        self._toast(msg)

    def _cal_nav(self, _btn, step):
        if self.cal_gran == "week": self.cal_offset += step
        elif self.cal_gran == "month": self.cal_month_off += step
        else: self.cal_day += timedelta(days=step)
        self._render_calendar()

    def _cal_today(self, *_):
        self.cal_offset = 0; self.cal_month_off = 0; self.cal_day = today_()
        self._render_calendar()

    def _cal_days(self):
        if self.cal_gran == "day": return [self.cal_day]
        monday = today_() - timedelta(days=today_().weekday()) + timedelta(weeks=self.cal_offset)
        return [monday + timedelta(days=i) for i in range(7)]

    def _cal_style(self, col):
        cid = (col or {}).get("id", "done")
        if cid in self._caltask_providers: return
        color = (col or {}).get("color", "#34D399")
        prov = Gtk.CssProvider()
        css_load(prov, f".caltask-{cid} {{ background: {color}; color: {contrast_text(color)}; }}".encode())
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), prov, Gtk.STYLE_PROVIDER_PRIORITY_USER - 1)
        self._caltask_providers[cid] = prov

    def _render_calendar(self):
        if self.cal_gran == "month":
            # Chế độ Tháng = dòng thời gian: hiện vùng timeline, ẩn lưới
            # giờ + dải chưa xếp giờ + nút Tự xếp (chỉ có nghĩa ở Tuần/Ngày).
            self.cal_scroll.set_visible(False)
            self.unsched_box.set_visible(False)
            self.btn_auto.set_visible(False)
            self.tl_scroll.set_visible(True)
            self._render_timeline()
            return
        self.cal_scroll.set_visible(True)
        self.unsched_box.set_visible(True)
        self.btn_auto.set_visible(True)
        self.tl_scroll.set_visible(False)
        SLOT0, STEP, ROWS = 6 * 60, 30, 36   # 06:00 -> 24:00, mỗi ô 30 phút
        days = self._cal_days()
        VN = ["Thứ Hai","Thứ Ba","Thứ Tư","Thứ Năm","Thứ Sáu","Thứ Bảy","Chủ Nhật"]
        if self.cal_gran == "week":
            self.cal_title.set_text(f"Tuần {days[0].strftime('%d/%m')} – {days[-1].strftime('%d/%m/%Y')}")
        else:
            d = days[0]
            self.cal_title.set_text(f"{VN[d.weekday()]}, {d.strftime('%d/%m/%Y')}")
        # dải việc chưa xếp giờ (có ngày trong khoảng đang xem nhưng chưa có giờ)
        for c in _kids(self.unsched_box): self.unsched_box.remove(c)
        day_isos = {d.isoformat() for d in days}
        unsched = [t for t in self.all_tasks if t["status"] != "done" and not t.get("due_time") and self._passes(t)
                   and t.get("due_date") and (t["due_date"] in day_isos or (self.cal_gran == "week" and is_overdue(t)))]
        if unsched:
            self.unsched_box.append(Gtk.Label(label="⏰ Chưa xếp giờ:", css_classes=["mut"]))
            sw = Gtk.ScrolledWindow(); sw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
            sw.set_hexpand(True)
            rowb = Gtk.Box(spacing=6)
            for t in unsched:
                b = Gtk.Button(label=f"{t['title']} · {fmt_due(t)}")
                b.add_css_class("unsched")
                b.set_tooltip_text("Bấm để xếp giờ — hoặc KÉO chip này thả vào một ô giờ bên dưới")
                # Chip chưa xếp giờ cũng kéo được (GĐ1): thả vào ô giờ = xếp giờ luôn
                usrc = Gtk.DragSource(actions=Gdk.DragAction.MOVE)
                usrc.connect("prepare", lambda s, x, y, tid=t["id"]:
                             Gdk.ContentProvider.new_for_value(f"task:{tid}"))
                b.add_controller(usrc)
                b.connect("clicked", lambda *_ , tt=t: self.open_task(tt))
                rowb.append(b)
            sw.set_child(rowb)
            self.unsched_box.append(sw)
        # lưới thời gian
        vadj = self.cal_scroll.get_vadjustment()
        saved_scroll = vadj.get_value() if vadj else 0
        grid = Gtk.Grid()
        grid.add_css_class("calgrid")
        # KHÔNG homogeneous: cột giờ giữ đúng 46px, các cột ngày (hexpand=True) chia đều
        # phần còn lại. Bản cũ homogeneous làm cột giờ phình bằng cột ngày — chế độ Ngày
        # chỉ có 1 cột ngày nên nửa trái màn hình trống hoác.
        grid.set_row_spacing(0); grid.set_column_spacing(0)
        colmap = {c["id"]: c for c in self.columns}
        # header ngày: tên thứ nhỏ + số ngày lớn; hôm nay = số trong vòng tròn màu (kiểu Google Calendar)
        grid.attach(Gtk.Label(label=""), 0, 0, 1, 1)
        for j, d in enumerate(days):
            hb = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
            hb.set_halign(Gtk.Align.CENTER); hb.set_margin_top(6); hb.set_margin_bottom(6)
            wd = Gtk.Label(label=VN[d.weekday()]); wd.add_css_class("mut")
            if d == today_(): wd.add_css_class("dayhead-today")
            hb.append(wd)
            num = Gtk.Label(label=str(d.day)); num.add_css_class("daynum")
            num.set_halign(Gtk.Align.CENTER)
            if d == today_():
                accent = "#2563EB" if SETTINGS["theme"] == "dark" else "#1A73E8"
                prov = Gtk.CssProvider()
                css_load(prov, f".todaynum-x {{ background: {accent}; color: #FFFFFF; border-radius: 999px; "
                                    "min-width: 30px; min-height: 30px; }}".encode())
                num.add_css_class("todaynum-x")
                num.get_style_context().add_provider(prov, Gtk.STYLE_PROVIDER_PRIORITY_USER)
            hb.append(num)
            grid.attach(hb, j + 1, 0, 1, 1)
        # cột giờ bên trái
        for i in range(ROWS):
            if i % 2 == 0:
                gl = Gtk.Label(label=min_to_hm(SLOT0 + i * STEP))
                gl.add_css_class("gutter"); gl.set_size_request(46, -1)
                gl.set_valign(Gtk.Align.START)
                grid.attach(gl, 0, i + 1, 1, 2)
        # ô trống: bấm để tạo việc tại giờ đó
        for j, d in enumerate(days):
            for i in range(ROWS):
                b = Gtk.Button()
                b.add_css_class("slot")
                if i % 2 == 0: b.add_css_class("slothour")
                b.set_size_request(-1, 24)
                b.set_hexpand(True)
                iso, hm = d.isoformat(), min_to_hm(SLOT0 + i * STEP)
                b.connect("clicked", lambda *_ , iso=iso, hm=hm: self.new_task(
                    preset={"due_date": iso, "due_time": hm, "estimate_min": 60}))
                # Ô giờ cũng là vùng THẢ (GĐ1): kéo khối việc / chip chưa xếp giờ /
                # thanh grip đổi thời lượng thả vào đây.
                sdt = Gtk.DropTarget.new(GObject.TYPE_STRING, Gdk.DragAction.MOVE)
                sdt.connect("drop", lambda _t, val, x, y, iso=iso, hm=hm, smin=SLOT0 + i * STEP:
                            self._on_slot_drop(val, iso, hm, smin))
                sdt.connect("enter", lambda *_ , bb=b: (bb.add_css_class("drop-hover"), Gdk.DragAction.MOVE)[1])
                sdt.connect("leave", lambda *_ , bb=b: bb.remove_css_class("drop-hover"))
                b.add_controller(sdt)
                grid.attach(b, j + 1, i + 1, 1, 1)
        # khối việc đã xếp giờ (tôn trọng bộ lọc hiện tại như ở bảng cột)
        for t in self.all_tasks:
            if t["status"] == "done" or not t.get("due_time") or not t.get("due_date"): continue
            if not self._passes(t): continue
            if t["due_date"] not in day_isos: continue
            sm = hm_to_min(t["due_time"])
            if sm is None: continue
            dur = t.get("estimate_min") or 60
            em = sm + dur
            j = days.index(date.fromisoformat(t["due_date"]))
            r0 = max(0, (max(sm, SLOT0) - SLOT0) // STEP)
            r1 = min(ROWS, -(-(min(em, SLOT0 + ROWS * STEP) - SLOT0) // STEP))
            if r1 <= r0: r1 = r0 + 1
            col = colmap.get(t.get("column_id"))
            color = (col or {}).get("color", "#34D399")
            b = Gtk.Button()
            b.add_css_class("caltask")
            # kiểu Apple/Google: nền NHẠT theo màu cột + thanh màu đậm ở mép trái + chữ sậm dễ đọc
            dark = SETTINGS["theme"] == "dark"
            tint = rgba_str(color, 0.30 if dark else 0.28)
            txt = mix_hex(color, "#FFFFFF", 0.62) if dark else mix_hex(color, "#111111", 0.45)
            bprov = Gtk.CssProvider()
            css_load(bprov, f"button {{ background: {tint}; color: {txt}; "
                                 f"box-shadow: inset 3px 0 0 {color}; }}".encode())
            b.get_style_context().add_provider(bprov, Gtk.STYLE_PROVIDER_PRIORITY_USER + 5)
            bl = Gtk.Label(label=f"{min_to_hm(sm)}–{min_to_hm(em)}\n{t['title']}", xalign=0, wrap=True)
            bl.set_ellipsize(Pango.EllipsizeMode.END)
            lprov = Gtk.CssProvider()
            css_load(lprov, f"label {{ color: {txt}; }}".encode())
            bl.get_style_context().add_provider(lprov, Gtk.STYLE_PROVIDER_PRIORITY_USER + 5)
            if r1 - r0 >= 2:
                # Khối ≥ 60 phút: thêm THANH GRIP ở đáy — kéo grip thả vào ô giờ
                # khác (cùng ngày) để đổi thời lượng; kéo THÂN khối để dời lịch.
                bl.set_vexpand(True); bl.set_valign(Gtk.Align.START)
                inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
                inner.append(bl)
                grip = Gtk.Box(); grip.add_css_class("calgrip")
                grip.set_cursor_from_name("ns-resize")
                grip.set_tooltip_text("Kéo thanh này thả vào ô giờ khác để đổi thời lượng")
                gsrc = Gtk.DragSource(actions=Gdk.DragAction.MOVE)
                gsrc.connect("prepare", lambda s, x, y, tid=t["id"]:
                             Gdk.ContentProvider.new_for_value(f"resize:{tid}"))
                grip.add_controller(gsrc)
                inner.append(grip)
                b.set_child(inner)
            else:
                b.set_child(bl)
            # Kéo thân khối việc = dời sang ngày/giờ khác (thả lên ô giờ, có chặn trùng)
            bsrc = Gtk.DragSource(actions=Gdk.DragAction.MOVE)
            def _bprep(s, x, y, c=b, tid=t["id"]):
                s.set_icon(Gtk.WidgetPaintable.new(c), int(x), int(y))
                return Gdk.ContentProvider.new_for_value(f"task:{tid}")
            bsrc.connect("prepare", _bprep)
            b.add_controller(bsrc)
            b.set_valign(Gtk.Align.FILL); b.set_hexpand(True)
            b.connect("clicked", lambda *_ , tt=t: self.open_task(tt))
            grid.attach(b, j + 1, r0 + 1, 1, r1 - r0)
        # vạch đỏ giờ hiện tại
        now = datetime.now()
        if today_() in days:
            nm_ = now.hour * 60 + now.minute
            if SLOT0 <= nm_ < SLOT0 + ROWS * STEP:
                j = days.index(today_())
                row = (nm_ - SLOT0) // STEP
                # margin qua property của widget — bản cũ tạo CssProvider gắn vào DISPLAY
                # mỗi lần render (không bao giờ gỡ) làm app càng chạy càng nặng.
                off = int((nm_ % STEP) / STEP * 24)
                line = Gtk.Box(); line.add_css_class("nowline")
                line.set_margin_top(off)
                line.set_valign(Gtk.Align.START); line.set_hexpand(True)
                grid.attach(line, j + 1, row + 1, 1, 1)
        self.cal_scroll.set_child(grid)
        first_cal = not getattr(self, "_cal_rendered", False)
        self._cal_rendered = True
        if first_cal:
            GLib.idle_add(lambda: (self.cal_scroll.get_vadjustment().set_value(0), False)[1])
        elif saved_scroll:
            GLib.idle_add(lambda: (self.cal_scroll.get_vadjustment().set_value(saved_scroll), False)[1])

    def _column_widget(self, col, tasks, filtering):
        is_done = col is None
        colw = Gtk.Box(orientation=Gtk.Orientation.VERTICAL); colw.add_css_class("col")
        colw.set_size_request(205, -1); colw.set_hexpand(True)
        head = Gtk.Box(spacing=8); head.add_css_class("colhead")
        dot = Gtk.Box(); dot.add_css_class("coldot"); dot.set_size_request(10, 10); dot.set_valign(Gtk.Align.CENTER)
        if is_done:
            prov = Gtk.CssProvider(); css_load(prov, b".coldot-done { background: #34D399; } .colcnt-done { background: #34D399; color: #101010; }")
            Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), prov, Gtk.STYLE_PROVIDER_PRIORITY_USER - 1)
            dot.add_css_class("coldot-done")
            name = "ĐÃ XONG"
        else:
            self._col_style(col)
            dot.add_css_class(f"coldot-{col['id']}")
            name = col["name"].upper()
        head.append(dot)
        nm = Gtk.Label(label=name, xalign=0); nm.add_css_class("colname")
        nm.set_ellipsize(Pango.EllipsizeMode.END); nm.set_hexpand(True)
        head.append(nm)
        cnt = Gtk.Label(label=str(len(tasks))); cnt.add_css_class("colcnt")
        cnt.add_css_class("colcnt-done" if is_done else f"colcnt-{col['id']}")
        head.append(cnt)
        if not is_done:
            mb = Gtk.MenuButton(label="⋯"); mb.add_css_class("mini"); mb.add_css_class("flat"); mb.add_css_class("menubtn")
            mb.set_tooltip_text("Đổi tên / màu / xoá cột")
            mb.set_popover(self._col_menu_popover(col, len(tasks)))
            head.append(mb)
        colw.append(head)
        # Vùng THẢ thẻ (GĐ1): cột thường = nhận chuyển cột; cột ĐÃ XONG = nhận
        # để đánh dấu xong. Khi kéo lơ lửng phía trên, cột sáng viền (.drop-hover).
        dt = Gtk.DropTarget.new(GObject.TYPE_STRING, Gdk.DragAction.MOVE)
        if is_done:
            dt.connect("drop", lambda _t, val, x, y: self._on_done_drop(val))
        else:
            dt.connect("drop", lambda _t, val, x, y, c=col: self._on_card_drop(val, c))
        dt.connect("enter", lambda *_: (colw.add_css_class("drop-hover"), Gdk.DragAction.MOVE)[1])
        dt.connect("leave", lambda *_: colw.remove_css_class("drop-hover"))
        colw.add_controller(dt)
        sc = Gtk.ScrolledWindow(); sc.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC); sc.set_vexpand(True)
        bodyb = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=9)
        bodyb.set_margin_top(4); bodyb.set_margin_bottom(10); bodyb.set_margin_start(10); bodyb.set_margin_end(10)
        if not tasks:
            e = Gtk.Label(label="Chưa có việc nào" if not filtering else "Không có việc khớp bộ lọc", xalign=0.5)
            e.add_css_class("empty"); bodyb.append(e)
        for t in tasks: bodyb.append(self._card(t))
        sc.set_child(bodyb); colw.append(sc)
        if not is_done:
            addrow = Gtk.Box(spacing=6); addrow.add_css_class("coladd")
            entry = Gtk.Entry(placeholder_text="＋ Việc nhỏ trong cột này…")
            entry.set_hexpand(True)
            entry.connect("activate", lambda *_ , c=col, e=entry: self._col_add(c, e))
            # Nút ＋ cuối ô thêm nhanh ĐÃ BỎ (Sinh 2026-11-10 01:36: 'mấy dấu cộng
            # này vô ích quá bỏ đi') — gõ xong Enter là thêm, nút bấm thừa.
            addrow.append(entry)
            colw.append(addrow)
        return colw

    def _col_menu_popover(self, col, n_tasks):
        pop = Gtk.Popover()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.set_margin_top(8); box.set_margin_bottom(8); box.set_margin_start(8); box.set_margin_end(8)
        b1 = Gtk.Button(label="✎ Đổi tên & màu cột"); b1.add_css_class("flat"); b1.add_css_class("dlgflat")
        b1.connect("clicked", lambda *_: (pop.popdown(), ColumnDialog(self, col, self.refresh).present()))
        box.append(b1)
        if len(self.columns) > 1:
            b2 = Gtk.Button(label="🗑 Xoá cột này"); b2.add_css_class("flat"); b2.add_css_class("dlgflat")
            def ask_delete(*_):
                pop.popdown()
                body = (f"Xoá cột “{col['name']}”? {n_tasks} việc trong cột sẽ chuyển sang cột đầu tiên "
                        f"(“{self.columns[0]['name']}”).") if n_tasks else f"Xoá cột “{col['name']}”? Cột đang trống."
                ConfirmDialog(self, "Xoá cột", body, "Xoá cột",
                              lambda: (self._safe(api, "DELETE", f"/api/columns/{col['id']}"), self.refresh())).present()
            b2.connect("clicked", ask_delete)
            box.append(b2)
        pop.set_child(box)
        return pop

    # ---------- Kéo-thả thẻ (GĐ1) ----------
    @staticmethod
    def _drop_task_id(val):
        try:
            kind, sid = str(val).split(":", 1)
            return int(sid) if kind in ("task", "resize") else None
        except Exception:
            return None

    def _find_task(self, tid):
        return next((x for x in self.all_tasks if x["id"] == tid), None)

    # ---------- Panel chi tiết + việc mới (v1.5.0) ----------
    def _vh_dot_style(self, color):
        if getattr(self, "_vh_color", None) == color: return
        self._vh_color = color
        prov = Gtk.CssProvider()
        css_load(prov, f".vhdot {{ background: {color}; border-radius: 999px; }}".encode())
        self.vh_dot.add_css_class("vhdot")
        self.vh_dot.get_style_context().add_provider(prov, Gtk.STYLE_PROVIDER_PRIORITY_USER)

    def _show_pane(self):
        if not self._pane_shown:
            self._pane_shown = True
            w = max(360, min(560, self.get_width() - 40))
            h = max(420, min(840, self.get_height() - 56))
            self.pane_card.set_size_request(w, h)
            self.pane_backdrop.set_visible(True)

    def _hide_pane(self):
        if self._pane_shown:
            self._pane_shown = False
            self.pane_backdrop.set_visible(False)
            self._on_pane_closed()

    def request_close_pane(self):
        """Đóng popup chi tiết CÓ HỎI khi còn chữ chưa lưu (Sinh 2026-11-16):
        các ô chữ trong popup chỉ lưu khi Enter / rời ô — đóng ngay lúc đang
        gõ dở (bấm ✕, Esc, hay click ra ngoài) sẽ mất chữ, nên phải hỏi trước:
        Lưu và đóng / Bỏ thay đổi / Ở lại."""
        if getattr(self, "pane", None) and self.pane.task \
                and self.pane._pending_dirty() and self._find_task(self.pane.task["id"]):
            dlg = Gtk.AlertDialog()
            dlg.set_message("Việc này có thay đổi chưa lưu")
            dlg.set_detail("Bạn vừa gõ sửa trong popup mà phần đó chưa kịp lưu. "
                           "Lưu lại rồi đóng, hay bỏ phần vừa sửa?")
            dlg.set_buttons(["Ở lại", "Bỏ thay đổi", "Lưu và đóng"])
            dlg.set_cancel_button(0); dlg.set_default_button(2)
            dlg.choose(self, None, self._close_confirm_done)
            return
        self.close_pane()

    def _close_confirm_done(self, dlg, res):
        try: idx = dlg.choose_finish(res)
        except Exception: return
        if idx == 2:
            self.pane._flush_pending()
            self.close_pane()
        elif idx == 1:
            self.pane._build()
            self.close_pane()

    def _on_pane_closed(self, *_):
        self._pane_shown = False
        self.pane.task = None
        if self.selected_id is not None:
            self.selected_id = None
            self._last_hash = ""
            self.refresh()

    def open_task(self, t, section=None):
        """Mở panel chi tiết bên phải cho việc t (đồng bộ bản mới nhất)."""
        fresh = self._find_task(t["id"]) or t
        if fresh.get("project_id") and fresh["project_id"] != self.cur_project:
            self._set_project(fresh["project_id"])
            fresh = self._find_task(t["id"]) or fresh
        self.selected_id = fresh["id"]
        self.pane.open(fresh, section)
        self._last_hash = ""
        self.refresh()

    def close_pane(self):
        self.selected_id = None
        self.pane.close()
        self._last_hash = ""
        self.refresh()

    def new_task(self, preset=None):
        """Việc mới kiểu Linear/Notion: tạo ngay 1 bản ghi rồi mở panel,
        ô tiêu đề được chọn sẵn để gõ đè — không qua hộp thoại trống."""
        body = {"title": "Việc mới"}
        fc = next((c for c in self.columns if c.get("project_id") == self.cur_project), None)
        if fc: body["column_id"] = fc["id"]
        if preset: body.update(preset)
        r = self._safe(api, "POST", "/api/tasks", body)
        self.refresh()
        nt = (r or {}).get("task")
        if nt:
            self.open_task(nt)
            GLib.timeout_add(80, lambda: (self.pane.focus_title(), False)[1])

    def _on_card_drop(self, val, col):
        """Thả thẻ vào một cột: chuyển việc sang cột đó (PATCH column_id)."""
        tid = self._drop_task_id(val)
        t = self._find_task(tid) if tid is not None else None
        if not t: return False
        if t.get("column_id") != col["id"]:
            old_col = t.get("column_id")
            self._safe(api, "PATCH", f"/api/tasks/{tid}", {"column_id": col["id"]})
            self.refresh()
            self._toast(f"⇄ Đã chuyển “{t['title']}” sang cột {col['name']}",
                        undo_fn=lambda: (self._safe(api, "PATCH", f"/api/tasks/{tid}",
                                                    {"column_id": old_col}), self.refresh()))
        return True

    def _on_done_drop(self, val):
        """Thả thẻ vào cột ĐÃ XONG: đánh dấu hoàn thành luôn."""
        tid = self._drop_task_id(val)
        t = self._find_task(tid) if tid is not None else None
        if not t or t["status"] == "done": return False
        self._safe(api, "POST", f"/api/tasks/{tid}/done")
        self.refresh()
        self._toast(f"✓ Đã xong: {t['title']}",
                    undo_fn=lambda: (self._safe(api, "POST", f"/api/tasks/{tid}/reopen"), self.refresh()))
        return True

    def _on_slot_drop(self, val, iso, hm, slotmin):
        """Thả lên một Ô GIỜ trên Lịch (GĐ1): "task:<id>" = dời việc tới ngày/giờ
        của ô đó (vẫn chặn trùng lịch như khi sửa tay); "resize:<id>" = đổi thời
        lượng cho tới ô được thả (chỉ trong cùng ngày, tối thiểu 30 phút)."""
        kind = str(val).split(":", 1)[0]
        tid = self._drop_task_id(val)
        t = self._find_task(tid) if tid is not None else None
        if not t: return False
        if kind == "resize":
            if t.get("due_date") != iso or not t.get("due_time"): return False
            start = hm_to_min(t["due_time"])
            new_dur = slotmin + 30 - start
            if new_dur < 30:
                self._toast("⚠ Thời lượng tối thiểu là 30 phút")
                return False
            cf = find_conflict(self.all_tasks, iso, start, new_dur, exclude_id=tid)
            if cf:
                self._toast(f"⚠ Kéo dài sẽ trùng với “{cf['title']}”")
                return False
            self._safe(api, "PATCH", f"/api/tasks/{tid}", {"estimate_min": new_dur})
            self.refresh()
            self._toast(f"↕ “{t['title']}” → {new_dur} phút")
            return True
        dur = t.get("estimate_min") or 60
        cf = find_conflict(self.all_tasks, iso, slotmin, dur, exclude_id=tid)
        if cf:
            self._toast(f"⚠ {hm} ngày {iso[8:10]}/{iso[5:7]} đã có “{cf['title']}” — không dời được")
            return False
        self._safe(api, "PATCH", f"/api/tasks/{tid}", {"due_date": iso, "due_time": hm})
        self.refresh()
        self._toast(f"🗓 Đã dời “{t['title']}” → {hm} · {iso[8:10]}/{iso[5:7]}")
        return True

    def _card_meta_markup(self, t, count_subs=True):
        """Một dòng meta DUY NHẤT trên thẻ (ngân sách ~5 tín hiệu như các app
        lớn): hạn (màu theo độ khẩn) · 🔁 lặp · ☑ việc con n/m · 💬 · 📎 ·
        ⏱ · 👤. Trường trống thì không hiện gì cả. Trả markup hoặc None."""
        dark = SETTINGS["theme"] == "dark"
        C = {"red": "#F87171" if dark else "#DC2626",
             "amber": "#FBBF24" if dark else "#B45309",
             "cyan": "#78DCE8" if dark else "#0E7490",
             "pink": "#FF7B9C" if dark else "#DB2777"}
        bits = []
        if t["status"] == "doing":
            bits.append(f'<span foreground="{C["pink"]}">▶ Đang làm</span>')
        d = t.get("due_date")
        if d:
            try:
                dd = date.fromisoformat(d)
                txt = f"📅 {dd.strftime('%d/%m')}"
                if t.get("due_time"): txt += f" {t['due_time']}"
                if t["status"] != "done" and d < TODAY:
                    bits.append(f'<span foreground="{C["red"]}">{txt} · Quá hạn</span>')
                elif t["status"] != "done" and d == TODAY:
                    bits.append(f'<span foreground="{C["red"]}">{txt} · Hôm nay</span>')
                elif t["status"] != "done" and dd <= today_() + timedelta(days=7):
                    bits.append(f'<span foreground="{C["amber"]}">{txt}</span>')
                else:
                    bits.append(txt)
            except Exception:
                pass
        if t.get("repeat_rule") not in (None, "none"):
            bits.append(f'<span foreground="{C["cyan"]}">🔁 lặp</span>')
        subs = t.get("subtasks") or []
        if subs and count_subs:
            bits.append(f"☑ {sum(1 for s in subs if s.get('done'))}/{len(subs)}")
        if t.get("comment_count"): bits.append(f"💬 {t['comment_count']}")
        if t.get("attach_count"): bits.append(f"📎 {t['attach_count']}")
        if t.get("timer_start"): bits.append("⏱ đang bấm giờ")
        elif t.get("actual_min"): bits.append(f"⏱ {t['actual_min']}p thật")
        if t.get("assignee"):
            bits.append(f"👤 {GLib.markup_escape_text(t['assignee'])}")
        return "  ·  ".join(bits) if bits else None

    def _card(self, t):
        # THẺ THEO KHUNG CHUẨN v1.5.0: cờ ưu tiên (chỉ khi khác mức thường) ->
        # tiêu đề (tối đa 2 dòng) -> ĐÚNG MỘT dòng meta. Không nút bấm hiện
        # sẵn, không danh sách việc con trên thẻ (việc con sống trong panel).
        # Bấm vào thẻ = mở panel chi tiết bên phải; ô ✓ vẫn tích xong ngay;
        # kéo-thả sang cột khác giữ nguyên như cũ.
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        card.add_css_class("card")
        if t["status"] == "done": card.add_css_class("done")
        if t["status"] == "doing": card.add_css_class("doing")
        if getattr(self, "selected_id", None) == t["id"]: card.add_css_class("sel")
        if t["status"] != "done":
            src = Gtk.DragSource(actions=Gdk.DragAction.MOVE)
            def _prep(s, x, y, c=card, tid=t["id"]):
                s.set_icon(Gtk.WidgetPaintable.new(c), int(x), int(y))
                return Gdk.ContentProvider.new_for_value(f"task:{tid}")
            src.connect("prepare", _prep)
            card.add_controller(src)
        lv = level_of(t)
        if lv != "L4" or t.get("pinned"):
            top = Gtk.Box(spacing=6)
            if lv != "L4":
                flag = Gtk.Label(label="⚑ " + SETTINGS["labels"][lv])
                flag.add_css_class("flagchip"); flag.add_css_class(lv)
                flag.set_ellipsize(Pango.EllipsizeMode.END)
                top.append(flag)
            sp = Gtk.Box(); sp.set_hexpand(True); top.append(sp)
            if t.get("pinned"): top.append(Gtk.Label(label="📌"))
            card.append(top)
        r2 = Gtk.Box(spacing=8)
        chk = Gtk.Button(label="✓" if t["status"] == "done" else "")
        chk.add_css_class("chk")
        if t["status"] == "done": chk.add_css_class("on")
        chk.set_size_request(16, 16); chk.set_valign(Gtk.Align.START)
        chk.set_tooltip_text("Tích xong / mở lại việc này")
        chk.connect("clicked", lambda *_ , tt=t: self._toggle(tt))
        r2.append(chk)
        title = Gtk.Label(xalign=0, wrap=True)
        title.add_css_class("cardtitle"); title.set_hexpand(True)
        title.set_ellipsize(Pango.EllipsizeMode.END); title.set_lines(2)
        if t["status"] == "done": title.set_markup(f"<s>{GLib.markup_escape_text(t['title'])}</s>")
        else: title.set_text(t["title"])
        r2.append(title)
        card.append(r2)
        subs = t.get("subtasks") or []
        for i, s in enumerate(subs):
            srow = Gtk.Box(spacing=6)
            sc = Gtk.Button(label="✓" if s.get("done") else "")
            sc.add_css_class("subchk")
            if s.get("done"): sc.add_css_class("on")
            sc.set_size_request(14, 14); sc.set_valign(Gtk.Align.START)
            sc.set_tooltip_text("Tích xong / mở lại việc con này")
            sc.connect("clicked", lambda *_ , tt=t, ii=i: self._sub_toggle(tt, ii))
            srow.append(sc)
            sl = Gtk.Label(xalign=0); sl.set_hexpand(True)
            sl.add_css_class("subtask-done" if s.get("done") else "subtask")
            sl.set_wrap(True); sl.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
            txt = GLib.markup_escape_text(s.get("t") or s.get("title") or "")
            if s.get("done"): sl.set_markup(f"<s>{txt}</s>")
            else: sl.set_text(s.get("t") or s.get("title") or "")
            srow.append(sl)
            card.append(srow)
        meta = self._card_meta_markup(t, count_subs=False)
        if meta:
            m = Gtk.Label(xalign=0); m.add_css_class("cardmeta")
            m.set_markup(meta)
            m.set_ellipsize(Pango.EllipsizeMode.END)
            card.append(m)
        g = Gtk.GestureClick()
        g.connect("released", lambda *_ , tt=t: self.open_task(tt))
        card.add_controller(g)
        card.set_tooltip_text("Bấm để mở chi tiết bên phải")
        return card

    # ---------- VIEW GANTT + SƠ ĐỒ (gói Coogo v1.6.0) ----------
    @staticmethod
    def _rgb(hx):
        hx = (hx or "#60A5FA").lstrip("#")
        if len(hx) == 3: hx = "".join(ch * 2 for ch in hx)
        try: return tuple(int(hx[i:i + 2], 16) / 255 for i in (0, 2, 4))
        except Exception: return (0.38, 0.65, 0.98)

    @staticmethod
    def _rr(cr, x, y, w, h, r):
        import math
        cr.new_path()
        cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
        cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
        cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
        cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
        cr.close_path()

    @staticmethod
    def _fit_text(cr, text, max_w):
        text = text or ""
        if cr.text_extents(text).width <= max_w: return text
        while text and cr.text_extents(text + "…").width > max_w:
            text = text[:-1]
        return text + "…" if text else ""

    # ----- Gantt: mỗi việc một thanh từ ngày bắt đầu tới hạn -----
    def _render_timeline(self):
        """Chế độ Tháng của Lịch (gộp từ Gantt v1.6.0): mỗi việc có ngày
        bắt đầu/hạn là một thanh từ ngày bắt đầu tới hạn, trong đúng tháng
        đang xem (cal_month_off). Bấm vào hàng = mở việc đó."""
        td = today_()
        y0, m0 = td.year, td.month + self.cal_month_off
        y0 += (m0 - 1) // 12; m0 = (m0 - 1) % 12 + 1
        first = date(y0, m0, 1)
        nxt = date(y0 + (1 if m0 == 12 else 0), 1 if m0 == 12 else m0 + 1, 1)
        ndays = (nxt - first).days
        last = first + timedelta(days=ndays - 1)
        self.cal_title.set_text(f"Tháng {m0:02d}/{y0}")
        tasks = [t for t in self.all_tasks
                 if self._passes(t)
                 and (t.get("project_id") or self.cur_project) == self.cur_project
                 and (t.get("due_date") or t.get("start_date"))
                 and (t.get("start_date") or t.get("due_date")) <= last.isoformat()
                 and (t.get("due_date") or t.get("start_date")) >= first.isoformat()]
        tasks.sort(key=lambda t: (t.get("start_date") or t.get("due_date") or "9999",
                                  t.get("due_date") or "9999"))
        self._gantt_tasks = tasks
        px = 26
        self._gantt_range = (first, ndays, px)
        self.gantt_area.set_size_request(216 + ndays * px + 16, 40 + max(1, len(tasks)) * 32 + 14)
        self.gantt_area.queue_draw()

    def _gantt_draw(self, area, cr, w, h):
        dark = SETTINGS["theme"] == "dark"
        txt = (0.90, 0.93, 0.97) if dark else (0.09, 0.09, 0.09)
        mut = (0.60, 0.64, 0.70) if dark else (0.42, 0.45, 0.51)
        grid = (1, 1, 1, 0.07) if dark else (0, 0, 0, 0.08)
        wknd = (1, 1, 1, 0.035) if dark else (0, 0, 0, 0.035)
        red = (0.97, 0.44, 0.44) if dark else (0.86, 0.15, 0.15)
        grn = (0.20, 0.83, 0.60) if dark else (0.02, 0.59, 0.41)
        LABW, HDR, ROWH = 216, 46, 32
        tasks = getattr(self, "_gantt_tasks", [])
        rng = getattr(self, "_gantt_range", None)
        cr.select_font_face("Sans", cairo.FontSlant.NORMAL, cairo.FontWeight.NORMAL)
        if not tasks or not rng:
            cr.set_source_rgb(*mut); cr.set_font_size(13)
            cr.move_to(16, 40)
            cr.show_text("Tháng này chưa có việc nào có ngày bắt đầu / hạn — đặt hạn cho việc là thanh sẽ hiện ở đây.")
            return
        d0, days, px = rng
        td = today_()
        colmap = {c["id"]: c for c in self.columns}
        # Nền cuối tuần + lưới ngày + nhãn ngày: hàng trên là dd/mm ở
        # thứ Hai và ngày 1; hàng dưới là số ngày của MỌI ngày (gói C —
        # trước đây chỉ ghi mỗi 7 ngày, khó dò ngày giữa khoảng).
        for i in range(days):
            d = d0 + timedelta(days=i)
            x = LABW + i * px
            if d.weekday() >= 5:
                cr.set_source_rgba(*wknd); cr.rectangle(x, 0, px, h); cr.fill()
            cr.set_source_rgba(*grid); cr.set_line_width(1)
            cr.move_to(x + 0.5, HDR - 10); cr.line_to(x + 0.5, h); cr.stroke()
            if d.day == 1 or (d.weekday() == 0 and d.day != 2):
                # (ngày 2 là thứ Hai ngay sau ngày 1: bỏ nhãn thứ Hai kẻo
                # hai nhãn dd/mm chồng nhau)
                cr.set_source_rgb(*mut); cr.set_font_size(10.5)
                cr.move_to(x + 3, 16); cr.show_text(d.strftime("%d/%m"))
            cr.set_source_rgba(*mut, 0.8); cr.set_font_size(8.5)
            _num = str(d.day)
            _nw = cr.text_extents(_num).width
            cr.move_to(x + (px - _nw) / 2, 33); cr.show_text(_num)
        # Đường "hôm nay"
        tx = LABW + (td - d0).days * px
        cr.set_source_rgb(*red); cr.set_line_width(1.6)
        cr.move_to(tx + 0.5, HDR - 10); cr.line_to(tx + 0.5, h); cr.stroke()
        cr.set_font_size(10.5); cr.move_to(tx + 4, 16); cr.show_text("hôm nay")
        # Các thanh việc
        for i, t in enumerate(tasks):
            y = HDR + i * ROWH
            s = date.fromisoformat(t.get("start_date") or t.get("due_date"))
            e = date.fromisoformat(t.get("due_date") or t.get("start_date"))
            if e < s: s, e = e, s
            # Kẹp trong khoảng đang vẽ (việc kéo dài qua mép tháng)
            s = max(s, d0); e = min(e, d0 + timedelta(days=days - 1))
            cr.set_source_rgb(*mut if t["status"] == "done" else txt)
            cr.set_font_size(12)
            cr.move_to(10, y + ROWH / 2 + 4)
            cr.show_text(self._fit_text(cr, t["title"], LABW - 20))
            bx = LABW + (s - d0).days * px
            bw = max(px, ((e - s).days + 1) * px)
            col = self._rgb((colmap.get(t.get("column_id")) or {}).get("color"))
            if t["status"] == "done":
                cr.set_source_rgba(*grn, 0.55)
            else:
                cr.set_source_rgba(*col, 0.85)
            self._rr(cr, bx + 1, y + 6, bw - 2, ROWH - 12, 6); cr.fill()
            if t["status"] != "done" and (t.get("due_date") or "") < td.isoformat():
                cr.set_source_rgb(*red); cr.set_line_width(1.6)
                self._rr(cr, bx + 1, y + 6, bw - 2, ROWH - 12, 6); cr.stroke()
            # Chữ TRÊN thanh khi thanh đủ rộng (>= 78px) — trước đây thanh
            # trơn, phải dò sang cột tên mới biết việc gì (gói C).
            if bw >= 78:
                cr.set_source_rgb(1, 1, 1); cr.set_font_size(10)
                cr.move_to(bx + 7, y + ROWH / 2 + 3.5)
                cr.show_text(self._fit_text(cr, t["title"], bw - 14))
            if t.get("due_time"):
                cr.set_source_rgb(*txt); cr.set_font_size(10.5)
                cr.move_to(bx + bw + 5, y + ROWH / 2 + 4); cr.show_text(t["due_time"])

    def _gantt_click(self, _g, x, y):
        tasks = getattr(self, "_gantt_tasks", [])
        i = int((y - 46) // 32)   # khớp HDR=46 trong _gantt_draw
        if 0 <= i < len(tasks): self.open_task(tasks[i])

    # ----- Sơ đồ: Dự án -> Cột -> Việc -> Việc con (mindmap trái sang phải) -----
    def _mm_toggle_done(self, b):
        self.mm_show_done = b.get_active()
        self._mm_snap = True
        self._render_mindmap()

    def _render_mindmap(self):
        proj = next((p for p in self.projects if p["id"] == self.cur_project), None)
        cols = [c for c in self.columns if c.get("project_id") == self.cur_project] or list(self.columns)
        first_id = cols[0]["id"] if cols else None
        ROWH = 27
        SUBCAP = 5   # tối đa 5 dòng việc con mỗi việc — quá thì gộp "+N nữa"
        X = {"root": 14, "col": 216, "task": 452, "sub": 712}
        W = {"root": 158, "col": 192, "task": 216, "sub": 236}
        nodes, y = [], 16
        for c in cols:
            tasks = [t for t in self.all_tasks
                     if (self.mm_show_done or t["status"] != "done") and self._passes(t)
                     and (t.get("project_id") or self.cur_project) == self.cur_project
                     and (t.get("column_id") or first_id) == c["id"]]
            if not tasks: continue
            collapsed = c["id"] in self.mm_collapsed
            y0, laid = y, []
            if collapsed:
                y += ROWH + 3
            else:
                for t in tasks:
                    subs = t.get("subtasks") or []
                    shown = min(len(subs), SUBCAP) + (1 if len(subs) > SUBCAP else 0)
                    th = max(1, shown) * ROWH
                    laid.append((t, y, th))
                    y += th
            colnode = {"kind": "col", "x": X["col"], "y": (y0 + y - 26) / 2, "w": W["col"], "h": 26,
                       "label": c["name"] + (f" · {len(tasks)} việc" if collapsed else ""),
                       "color": c.get("color") or "#60A5FA", "task": None,
                       "col_id": c["id"], "collapsed": collapsed}
            nodes.append(colnode)
            for t, ty, th in laid:
                tn = {"kind": "task", "x": X["task"], "y": ty + (th - 24) / 2, "w": W["task"], "h": 24,
                      "label": t["title"], "task": t, "parent": colnode,
                      "done": t["status"] == "done"}
                nodes.append(tn)
                subs = t.get("subtasks") or []
                for j, s in enumerate(subs[:SUBCAP]):
                    nodes.append({"kind": "sub", "x": X["sub"], "y": ty + j * ROWH + 2, "w": W["sub"], "h": 22,
                                  "label": s.get("t") or "", "done": bool(s.get("done")),
                                  "task": t, "parent": tn})
                if len(subs) > SUBCAP:
                    nodes.append({"kind": "more", "x": X["sub"], "y": ty + SUBCAP * ROWH + 2,
                                  "w": W["sub"], "h": 22,
                                  "label": f"+ {len(subs) - SUBCAP} việc con nữa…",
                                  "task": t, "parent": tn})
        total_h = max(y + 16, 170)
        if proj and any(n["kind"] == "col" for n in nodes):
            rn = {"kind": "root", "x": X["root"], "y": 16 + (total_h - 16 - 32) / 2, "w": W["root"], "h": 32,
                  "label": proj["name"], "color": proj.get("color") or "#60A5FA", "task": None}
            nodes.append(rn)
            for n in nodes:
                if n["kind"] == "col": n["parent"] = rn
        self._map_nodes = nodes
        self.map_area.set_size_request(X["sub"] + W["sub"] + 24, total_h)
        self.map_area.queue_draw()
        # Vào view / dữ liệu mới từ refresh -> về đầu sơ đồ; thao tác
        # gập/mở nhánh tại chỗ thì GIỮ vị trí cuộn (cờ _mm_snap do nơi
        # gọi refresh/chuyển view đặt, hàm này tự tắt sau khi dùng).
        if getattr(self, "_mm_snap", False):
            self._mm_snap = False
            def _top():
                try: self.map_scroll.get_vadjustment().set_value(0)
                except Exception: pass
                return False
            GLib.idle_add(_top)

    def _map_draw(self, area, cr, w, h):
        dark = SETTINGS["theme"] == "dark"
        txt = (0.90, 0.93, 0.97) if dark else (0.09, 0.09, 0.09)
        mut = (0.60, 0.64, 0.70) if dark else (0.42, 0.45, 0.51)
        cardbg = (0.15, 0.17, 0.21) if dark else (1, 1, 1)
        cardbd = (0.23, 0.26, 0.32) if dark else (0.82, 0.85, 0.90)
        accent = (0.30, 0.55, 1.0) if dark else (0.15, 0.39, 0.92)
        nodes = getattr(self, "_map_nodes", [])
        cr.select_font_face("Sans", cairo.FontSlant.NORMAL, cairo.FontWeight.NORMAL)
        if not nodes:
            cr.set_source_rgb(*mut); cr.set_font_size(13)
            cr.move_to(16, 40)
            cr.show_text("Chưa có việc đang mở nào trong dự án này để vẽ sơ đồ.")
            return
        # Đường nối (vẽ trước, nằm dưới các hộp)
        cr.set_line_width(1.6)
        for n in nodes:
            p = n.get("parent")
            if not p: continue
            x1, y1 = p["x"] + p["w"], p["y"] + p["h"] / 2
            x2, y2 = n["x"], n["y"] + n["h"] / 2
            cr.set_source_rgba(*self._rgb(p.get("color") or "#60A5FA"), 0.55)
            cr.move_to(x1, y1)
            cr.curve_to(x1 + 42, y1, x2 - 42, y2, x2, y2)
            cr.stroke()
        # Các hộp
        for n in nodes:
            x, y, nw, nh = n["x"], n["y"], n["w"], n["h"]
            if n["kind"] in ("root", "col"):
                cr.set_source_rgba(*self._rgb(n.get("color")), 0.92)
                self._rr(cr, x, y, nw, nh, 8); cr.fill()
                cr.set_source_rgb(1, 1, 1)
                cr.select_font_face("Sans", cairo.FontSlant.NORMAL, cairo.FontWeight.BOLD)
                cr.set_font_size(13 if n["kind"] == "root" else 12.5)
            elif n["kind"] == "task":
                if n.get("done"):
                    cr.set_source_rgba(*cardbg, 0.45)
                else:
                    cr.set_source_rgb(*cardbg)
                self._rr(cr, x, y, nw, nh, 7); cr.fill()
                sel = n["task"] and getattr(self, "selected_id", None) == n["task"]["id"]
                cr.set_source_rgb(*(accent if sel else cardbd))
                cr.set_line_width(2 if sel else 1.2)
                self._rr(cr, x, y, nw, nh, 7); cr.stroke()
                cr.set_source_rgb(*(mut if n.get("done") else txt)); cr.set_font_size(12)
            elif n["kind"] == "more":
                cr.set_source_rgb(*mut); cr.set_font_size(11.5)
            else:
                cr.set_source_rgba(*cardbg, 0.55); self._rr(cr, x, y, nw, nh, 6); cr.fill()
                cr.set_source_rgb(*cardbd); cr.set_line_width(1)
                self._rr(cr, x, y, nw, nh, 6); cr.stroke()
                cr.set_source_rgb(*(mut if n.get("done") else txt)); cr.set_font_size(11.5)
            label = n["label"] or ""
            fitted = self._fit_text(cr, label, nw - 18)
            cr.move_to(x + 10, y + nh / 2 + 4.5)
            cr.show_text(fitted)
            if n["kind"] in ("root", "col"):
                # Tam giác thu gọn/mở nhánh ở mép phải hộp — VẼ BẰNG NÉT
                # cairo (glyph ▸/▾ qua font toy hóa ô tofu, cùng bài học
                # với dấu ✓). Gốc: hướng phải khi MỌI cột đều đang gập.
                if n["kind"] == "root":
                    _cols = [m for m in nodes if m["kind"] == "col"]
                    _folded = bool(_cols) and all(m.get("collapsed") for m in _cols)
                else:
                    _folded = bool(n.get("collapsed"))
                cr.set_source_rgb(1, 1, 1)
                cx, cy = x + nw - 13, y + nh / 2
                if _folded:   # tam giác trỏ PHẢI
                    cr.move_to(cx - 3, cy - 5); cr.line_to(cx + 4, cy); cr.line_to(cx - 3, cy + 5)
                else:         # tam giác trỏ XUỐNG
                    cr.move_to(cx - 5, cy - 3); cr.line_to(cx + 5, cy - 3); cr.line_to(cx, cy + 4)
                cr.close_path(); cr.fill()
            if n["kind"] == "task" and n.get("done"):
                tw = cr.text_extents(fitted).width
                cr.set_source_rgb(*mut); cr.set_line_width(1.2)
                cr.move_to(x + 10, y + nh / 2)
                cr.line_to(x + 10 + tw, y + nh / 2)
                cr.stroke()
            if n["kind"] == "sub" and n.get("done"):
                # Gạch ngang việc con đã xong (vẽ bằng nét cairo — không phụ
                # thuộc glyph ✓, font hệ thống nào cũng hiện đúng)
                tw = cr.text_extents(fitted).width
                cr.set_line_width(1.2)
                cr.move_to(x + 10, y + nh / 2)
                cr.line_to(x + 10 + tw, y + nh / 2)
                cr.stroke()
            cr.select_font_face("Sans", cairo.FontSlant.NORMAL, cairo.FontWeight.NORMAL)

    def _map_click(self, _g, x, y):
        nodes = getattr(self, "_map_nodes", [])
        for n in reversed(nodes):
            if not (n["x"] <= x <= n["x"] + n["w"] and n["y"] <= y <= n["y"] + n["h"]):
                continue
            if n["kind"] == "col":
                cid = n.get("col_id")
                if cid in self.mm_collapsed: self.mm_collapsed.discard(cid)
                else: self.mm_collapsed.add(cid)
                self._render_mindmap(); return
            if n["kind"] == "root":
                col_ids = [m.get("col_id") for m in nodes if m["kind"] == "col"]
                if all(cid in self.mm_collapsed for cid in col_ids):
                    self.mm_collapsed.clear()
                else:
                    self.mm_collapsed = set(col_ids)
                self._render_mindmap(); return
            if n.get("task"):
                self.open_task(n["task"]); return

    # ---------- VIEW DANH SÁCH (v1.5.0 — tab thứ hai sau Bảng) ----------
    def _list_row(self, t):
        row = Gtk.Box(spacing=8); row.add_css_class("lrow")
        if getattr(self, "selected_id", None) == t["id"]: row.add_css_class("sel")
        chk = Gtk.Button(label="✓" if t["status"] == "done" else "")
        chk.add_css_class("chk")
        if t["status"] == "done": chk.add_css_class("on")
        chk.set_size_request(16, 16); chk.set_valign(Gtk.Align.CENTER)
        chk.connect("clicked", lambda *_ , tt=t: self._toggle(tt))
        row.append(chk)
        main = Gtk.Button(); main.add_css_class("flat"); main.set_hexpand(True)
        inner = Gtk.Box(spacing=10)
        lv = level_of(t)
        if lv != "L4":
            flag = Gtk.Label(label="⚑ " + SETTINGS["labels"][lv])
            flag.add_css_class("flagchip"); flag.add_css_class(lv)
            inner.append(flag)
        title = Gtk.Label(xalign=0); title.add_css_class("cardtitle"); title.set_hexpand(True)
        title.set_ellipsize(Pango.EllipsizeMode.END)
        if t["status"] == "done": title.set_markup(f"<s>{GLib.markup_escape_text(t['title'])}</s>")
        else: title.set_text(t["title"])
        inner.append(title)
        meta = self._card_meta_markup(t)
        if meta:
            m = Gtk.Label(); m.set_markup(meta); m.add_css_class("cardmeta")
            m.set_ellipsize(Pango.EllipsizeMode.END)
            inner.append(m)
        if t.get("pinned"): inner.append(Gtk.Label(label="📌"))
        main.set_child(inner)
        main.connect("clicked", lambda *_ , tt=t: self.open_task(tt))
        row.append(main)
        return row

    def _render_list(self):
        """Danh sách phẳng theo cột của dự án đang chọn — cùng bộ lọc với bảng."""
        box = self.list_box
        for c in _kids(box): box.remove(c)
        shown = [t for t in self.all_tasks if self._passes(t)
                 and (t.get("project_id") or self.cur_project) == self.cur_project]
        cols = [c for c in self.columns if c.get("project_id") == self.cur_project] or list(self.columns)
        if self.focus_col is not None:
            cols = [c for c in cols if c["id"] == self.focus_col]
        first_id = cols[0]["id"] if cols else None
        by = {c["id"]: [] for c in cols}
        done_list = []
        for t in shown:
            if t["status"] == "done": done_list.append(t)
            else: by[t.get("column_id") if t.get("column_id") in by else first_id].append(t)
        any_row = False
        for c in cols:
            items = by[c["id"]]
            if self.sort_mode == 1:
                items.sort(key=lambda t: (t.get("due_date") or "9999", -(t["score"])))
            else:
                items.sort(key=lambda t: -(t["score"]))
            hdr = Gtk.Box(spacing=8)
            dot = Gtk.Box(); dot.set_size_request(9, 9); dot.set_valign(Gtk.Align.CENTER)
            prov = Gtk.CssProvider()
            css_load(prov, f".ldot {{ background: {c['color']}; border-radius: 999px; }}".encode())
            dot.add_css_class("ldot")
            dot.get_style_context().add_provider(prov, Gtk.STYLE_PROVIDER_PRIORITY_USER)
            hdr.append(dot)
            hl = Gtk.Label(label=f"{c['name'].upper()} · {len(items)}", xalign=0)
            hl.add_css_class("lhead"); hdr.append(hl)
            box.append(hdr)
            if not items:
                e = Gtk.Label(label="Chưa có việc nào", xalign=0); e.add_css_class("empty")
                box.append(e)
            for t in items:
                box.append(self._list_row(t)); any_row = True
        if done_list:
            done_list.sort(key=lambda t: t.get("done_at") or "", reverse=True)
            hl = Gtk.Label(label=f"ĐÃ XONG · {len(done_list)}", xalign=0)
            hl.add_css_class("lhead"); box.append(hl)
            for t in done_list: box.append(self._list_row(t))
        if not any_row and not done_list:
            e = Gtk.Label(label="Không có việc nào khớp bộ lọc", xalign=0.5)
            e.add_css_class("empty"); box.append(e)

    # ---------- Hành động ----------
    def _toast(self, text, undo_fn=None):
        toast = Adw.Toast.new(text)
        toast.set_timeout(4)
        if undo_fn:
            toast.set_button_label("Hoàn tác")
            toast.connect("button-clicked", lambda *_: undo_fn())
        self.toasts.add_toast(toast)

    def _toggle(self, t):
        was_done = t["status"] == "done"
        self._safe(api, "POST", f"/api/tasks/{t['id']}/{'reopen' if was_done else 'done'}")
        if not was_done:
            tid, title = t["id"], t["title"]
            self._toast(f"✓ Đã xong: {title}",
                        undo_fn=lambda: (self._safe(api, "POST", f"/api/tasks/{tid}/reopen"), self.refresh()))
            def celebrate():
                try:
                    all_t = api("GET", "/api/tasks?view=all")["tasks"]
                    left = [x for x in all_t if x["status"] != "done" and x.get("due_date") and x["due_date"] <= TODAY]
                    had_today = any(x.get("due_date") and x["due_date"] <= TODAY for x in all_t)
                    if not left and had_today:
                        desktop_notify("🎉 Xong hết việc hôm nay!", "Bạn đã hoàn thành mọi việc đến hạn hôm nay. Nghỉ ngơi thôi!")
                except Exception: pass
            threading.Thread(target=celebrate, daemon=True).start()
        self.refresh()

    def _sub_toggle(self, t, idx):
        subs = [dict(s) for s in (t.get("subtasks") or [])]
        if idx >= len(subs): return
        subs[idx]["done"] = not subs[idx].get("done")
        self._safe(api, "PATCH", f"/api/tasks/{t['id']}", {"subtasks": subs})
        self.refresh()

    def _duplicate(self, t):
        body = {k: t.get(k) for k in ("title", "notes", "due_date", "due_time", "important", "urgent",
                                      "tags", "estimate_min", "remind_before", "repeat_rule", "column_id", "subtasks")}
        self._safe(api, "POST", "/api/tasks", body)
        self._toast(f"⧉ Đã nhân đôi việc “{t['title']}”")
        self.refresh()
    def _delete(self, t):
        tid, title = t["id"], t["title"]
        self._safe(api, "DELETE", f"/api/tasks/{tid}")
        self.refresh()
        self._toast(f"🗑 Đã xoá “{title}” (vào thùng rác)",
                    undo_fn=lambda: (self._safe(api, "POST", f"/api/tasks/{tid}/restore"), self.refresh()))

    def _pane_resync(self, tid):
        """Popup chi tiết đang mở đúng việc tid thì nạp lại nội dung —
        dùng sau các nút Hoàn tác để popup không hiển thị dữ kiện cũ."""
        pane = getattr(self, "pane", None)
        if pane is not None and getattr(pane, "task", None) and pane.task.get("id") == tid:
            nt = self._find_task(tid)
            if nt: pane.task = nt; pane._build()
    def _col_add(self, col, entry):
        title = entry.get_text().strip()
        if not title: return
        self._safe(api, "POST", "/api/tasks", {"title": title, "column_id": col["id"]})
        self.refresh()
    def _on_quick_changed(self, *_):
        # Xem trước cách app hiểu câu thêm nhanh (kiểu Todoist) — gọi /api/parse sau 350ms ngừng gõ
        self._parse_src += 1
        src = self._parse_src
        def later():
            if src != self._parse_src: return False
            text = self.quick.get_text().strip()
            if not text:
                self.quick_preview.set_visible(False); return False
            def work():
                try: p = api("GET", "/api/parse?text=" + urllib.parse.quote(text)).get("parsed")
                except Exception: p = None
                GLib.idle_add(lambda: (self._show_parse_preview(p), False)[1])
            threading.Thread(target=work, daemon=True).start()
            return False
        GLib.timeout_add(350, later)

    def _show_parse_preview(self, p):
        if not p:
            self.quick_preview.set_visible(False); return
        bits = preview_bits(p)
        self.quick_preview.set_text(("→ App hiểu là: " + " · ".join(bits)) if bits else "")
        self.quick_preview.set_visible(bool(bits))

    def _quick_add(self, *_):
        text = self.quick.get_text().strip()
        if not text: return
        _fc = next((c["id"] for c in self.columns if c.get("project_id") == self.cur_project), None)
        r = self._safe(api, "POST", "/api/quick", {"text": text, "source": "desktop", "column_id": _fc})
        if r: self.quick.set_text(""); self.refresh()

    # ---------- AI Gemini điền form (gói Coogo v1.6.0) ----------
    def _quick_ai(self, *_):
        text = self.quick.get_text().strip()
        if not text:
            self._toast("Gõ một câu mô tả việc trước — ví dụ: “Chiều mai 3h họp team, chuẩn bị slide, khá gấp”")
            return
        key = SETTINGS.get("gemini_key") or ""
        if not key:
            self._toast("Chưa có Gemini API key — dán key (miễn phí) trong ⚙ Cài đặt ở thanh bên trước đã")
            SettingsDialog(self).present()
            return
        self.ai_btn.set_sensitive(False)
        self.quick_preview.set_text("✨ AI đang đọc câu và điền form…")
        self.quick_preview.set_visible(True)
        threading.Thread(target=self._quick_ai_worker, args=(text, key), daemon=True).start()

    def _quick_ai_worker(self, text, key):
        td = today_()
        VN = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"]
        prompt = (
            f"Hôm nay là {VN[td.weekday()]} ngày {td.strftime('%d/%m/%Y')}. "
            "Đọc câu mô tả công việc bằng tiếng Việt dưới đây và trả về DUY NHẤT một JSON "
            "(không giải thích, không markdown) theo mẫu: "
            '{"title": "tiêu đề ngắn gọn", "due_date": "YYYY-MM-DD hoặc null", '
            '"due_time": "HH:MM hoặc null", "estimate_min": số phút hoặc null, '
            '"important": true/false, "urgent": true/false, '
            '"tags": ["nhãn"], "subtasks": ["việc con gợi ý, tối đa 5"]}. '
            "Ngày tháng tương đối (mai, thứ 6 này, tuần sau…) phải quy ra ngày thật theo hôm nay. "
            f"Câu mô tả: {text}")
        payload = {"contents": [{"parts": [{"text": prompt}]}],
                   "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"}}
        try:
            req = urllib.request.Request(
                "https://generativelanguage.googleapis.com/v1beta/models/"
                f"gemini-2.0-flash:generateContent?key={key}",
                data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=25) as r:
                out = json.loads(r.read().decode())
            spec = json.loads(out["candidates"][0]["content"]["parts"][0]["text"])
            GLib.idle_add(self._quick_ai_done, spec, None)
        except Exception as e:
            GLib.idle_add(self._quick_ai_done, None, str(e)[:140])

    def _quick_ai_done(self, spec, err):
        self.ai_btn.set_sensitive(True)
        if err or not spec:
            self.quick_preview.set_text(f"✨ AI chưa điền được ({err or 'phản hồi lạ'}) — Enter để thêm nhanh như thường.")
            return False
        body = {"title": (str(spec.get("title") or "").strip() or "Việc mới")}
        fc = next((c for c in self.columns if c.get("project_id") == self.cur_project), None)
        if fc: body["column_id"] = fc["id"]
        for k in ("due_date", "due_time", "estimate_min", "remind_before"):
            if spec.get(k): body[k] = spec[k]
        if spec.get("important"): body["important"] = True
        if spec.get("urgent"): body["urgent"] = True
        if spec.get("tags"):
            body["tags"] = [str(x).lstrip("#").strip() for x in spec["tags"] if str(x).strip()]
        subs = [{"t": str(s), "done": False} for s in (spec.get("subtasks") or []) if str(s).strip()]
        if subs: body["subtasks"] = subs
        r = self._safe(api, "POST", "/api/tasks", body)
        self.quick.set_text("")
        self.quick_preview.set_visible(False)
        self.refresh()
        nt = (r or {}).get("task")
        if nt:
            self._toast("✨ AI đã điền form — kiểm lại trong popup, sai đâu sửa đó")
            self.open_task(nt)
        return False

_THEME_PROVIDER = [None]
def apply_theme():
    display = Gdk.Display.get_default()
    if _THEME_PROVIDER[0] is not None:
        Gtk.StyleContext.remove_provider_for_display(display, _THEME_PROVIDER[0])
    prov = Gtk.CssProvider()
    css_load(prov, (LIGHT_CSS if SETTINGS["theme"] == "light" else DARK_CSS).encode())
    Gtk.StyleContext.add_provider_for_display(display, prov, Gtk.STYLE_PROVIDER_PRIORITY_USER)
    _THEME_PROVIDER[0] = prov
    Adw.StyleManager.get_default().set_color_scheme(
        Adw.ColorScheme.FORCE_LIGHT if SETTINGS["theme"] == "light" else Adw.ColorScheme.FORCE_DARK)

def ensure_engine():
    """Windows (bản đóng exe): engine là ShiniTasksEngine.exe nằm CẠNH file app.
    Mở app mà engine chưa chạy thì tự bật nó (không cửa sổ) và chờ API trả lời
    tối đa ~8 giây. Bản Linux dùng systemd nên hàm này không làm gì cả."""
    if not (IS_WIN and FROZEN):
        return
    try:
        urllib.request.urlopen(API + "/api/stats", timeout=1.5)
        return
    except Exception:
        pass
    eng = os.path.join(os.path.dirname(os.path.abspath(sys.executable)), "ShiniTasksEngine.exe")
    if not os.path.exists(eng):
        return
    try:
        subprocess.Popen([eng], creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        for _ in range(20):
            threading.Event().wait(0.4)
            try:
                urllib.request.urlopen(API + "/api/stats", timeout=1.5)
                return
            except Exception:
                continue
    except Exception as e:
        print("ensure engine error:", e)

def main():
    # Dây an toàn chẩn đoán: kill -USR1 <pid> sẽ in traceback mọi thread ra stderr
    # (dùng khi app bị treo/ăn CPU để biết chính xác nó kẹt ở đâu, không cần ptrace)
    try: faulthandler.register(signal.SIGUSR1)
    except Exception: pass
    ensure_engine()
    if "--capture" in sys.argv:
        return run_capture()
    Adw.init()
    app = Adw.Application(application_id="dev.shini.tasks")
    def on_activate(a):
        apply_theme()
        win = MainWindow(a)
        sz = os.environ.get("SHINI_TASKS_SIZE")
        if sz:
            try:
                w, h = sz.lower().split("x"); win.set_default_size(int(w), int(h))
            except Exception: pass
        win.present()
        opn = os.environ.get("SHINI_TASKS_OPEN")
        if opn:
            def _open_probe():
                ts = [t for t in win.all_tasks if t["status"] != "done"]
                t = next((x for x in ts if opn.lower() in x["title"].lower()), ts[0] if ts else None)
                if t: win.open_task(t)
                return False
            GLib.timeout_add(900, _open_probe)
        snap = os.environ.get("SHINI_TASKS_SNAPSHOT")
        if snap:
            def shot():
                renderer = None
                try:
                    from gi.repository import Gsk, Graphene
                    paintable = Gtk.WidgetPaintable.new(win)
                    w = paintable.get_intrinsic_width() or 1560
                    h = paintable.get_intrinsic_height() or 880
                    snapshot = Gtk.Snapshot()
                    paintable.snapshot(snapshot, w, h)
                    node = snapshot.to_node()
                    renderer = Gsk.CairoRenderer(); renderer.realize(None)
                    rect = Graphene.Rect(); rect.init(0, 0, w, h)
                    tex = renderer.render_texture(node, rect)
                    tex.save_to_png(snap)
                    print("SNAPSHOT_OK", snap, w, h)
                except Exception as e:
                    print("SNAPSHOT_ERR", type(e).__name__, e)
                finally:
                    try:
                        if renderer: renderer.unrealize()
                    except Exception: pass
                a.quit(); return False
            GLib.timeout_add(2200, shot)
    app.connect("activate", on_activate)
    return app.run(sys.argv)

if __name__ == "__main__":
    sys.exit(main())
