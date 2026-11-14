# -*- mode: python ; coding: utf-8 -*-
# App desktop Shini Tasks (app.py, GTK4 + Libadwaita) — dong kieu onedir.
# Phan GTK (DLL + typelib) do hook gi cua pyinstaller-hooks-contrib thu thap;
# spec nay cong them phan FILE DU LIEU ma hook khong lo: schemas, icon themes,
# cau hinh font toi gian, va ban sao typelib de rthook_shini.py tro vao.
import glob
import os

SPEC_DIR = os.path.dirname(os.path.abspath(SPEC))
ROOT = os.path.dirname(SPEC_DIR)
PREFIX = os.environ.get("MSYS2_PREFIX", "C:/msys64/ucrt64").replace("\\", "/")
ICON = os.path.join(SPEC_DIR, "shini.ico")

datas = []
# Ban sao typelib (du phong) — rthook cong vao GI_TYPELIB_PATH
for f in glob.glob(PREFIX + "/lib/girepository-1.0/*.typelib"):
    datas.append((f, "gi_typelibs"))
# GSettings schemas (org.gtk.gtk4.*, org.gnome.desktop.* neu co...)
schema_dir = PREFIX + "/share/glib-2.0/schemas"
if os.path.isdir(schema_dir):
    datas.append((schema_dir, "schemas"))
# Icon themes
for theme in ("Adwaita", "hicolor"):
    p = PREFIX + "/share/icons/" + theme
    if os.path.isdir(p):
        datas.append((p, "share/icons/" + theme))
# fontconfig: dung fonts.conf TOI GIAN cua rieng du an (tro vao C:\Windows\Fonts)
datas.append((os.path.join(SPEC_DIR, "fonts.conf"), "etc/fonts"))

a = Analysis(
    [os.path.join(ROOT, "app.py")],
    pathex=[ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "gi.repository.Gtk", "gi.repository.Adw", "gi.repository.Gdk",
        "gi.repository.Gsk", "gi.repository.Graphene", "gi.repository.Pango",
        "gi.repository.PangoCairo", "gi.repository.Gio", "gi.repository.GLib",
        "gi.repository.GObject", "cairo",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[os.path.join(SPEC_DIR, "rthook_shini.py")],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ShiniTasks",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    # SHINI_CONSOLE=1 khi CI can bat loi Python cua app (ban thuong tat console)
    console=os.environ.get("SHINI_CONSOLE") == "1",
    icon=ICON if os.path.exists(ICON) else None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="ShiniTasks",
)
