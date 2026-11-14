# Runtime hook cua PyInstaller — chay TRUOC app.py khi ban exe khoi dong.
# Chi cho GTK4 biet noi tim: typelib (du phong, cong them vao duong cua
# pyinstaller-hooks-contrib neu co), GSettings schemas, icon theme, fontconfig.
import os
import sys

base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(sys.executable)))


def _prepend(env_name, path):
    if not os.path.isdir(path):
        return
    old = os.environ.get(env_name, "")
    parts = [p for p in old.split(os.pathsep) if p]
    if path not in parts:
        os.environ[env_name] = os.pathsep.join([path] + parts)


_prepend("GI_TYPELIB_PATH", os.path.join(base, "gi_typelibs"))
_prepend("XDG_DATA_DIRS", base)

schemas = os.path.join(base, "schemas")
if os.path.isdir(schemas):
    os.environ.setdefault("GSETTINGS_SCHEMA_DIR", schemas)

fonts_conf = os.path.join(base, "etc", "fonts", "fonts.conf")
if os.path.exists(fonts_conf):
    os.environ.setdefault("FONTCONFIG_FILE", fonts_conf)
