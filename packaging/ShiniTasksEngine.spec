# -*- mode: python ; coding: utf-8 -*-
# Engine Shini Tasks (server.py) — dong 1 file exe duy nhat, khong cua so console.
# server.py chi dung thu vien chuan nen spec nay gon: kem thu muc static/ de
# trang web du phong con dung duoc; du lieu (tasks.db...) khi chay tren Windows
# se tu sang %APPDATA%\Shini Tasks nho _data_dir() trong server.py.
import os

SPEC_DIR = os.path.dirname(os.path.abspath(SPEC))
ROOT = os.path.dirname(SPEC_DIR)
ICON = os.path.join(SPEC_DIR, "shini.ico")

a = Analysis(
    [os.path.join(ROOT, "server.py")],
    pathex=[ROOT],
    binaries=[],
    datas=[(os.path.join(ROOT, "static"), "static")],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="ShiniTasksEngine",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=ICON if os.path.exists(ICON) else None,
)
