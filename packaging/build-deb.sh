#!/bin/sh
# Đóng gói Shini Tasks thành file .deb cho Ubuntu/Debian (gói D, audit
# 2026-11-17). Chạy:  sh packaging/build-deb.sh [kiến trúc]
# Ra: dist/shini-tasks_<version>_all.deb
# Code cài vào /usr/share/shini-tasks (chỉ đọc); dữ liệu của từng người
# dùng nằm ở ~/.local/share/shini-tasks qua biến SHINI_TASKS_DATA mà
# launcher + systemd unit tự đặt — engine/app đã hỗ trợ từ gói D.
set -e
cd "$(dirname "$0")/.."
VER=$(grep -oP 'VERSION = "\K[^"]+' server.py | head -1)
ARCH="${1:-all}"
OUT="dist"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT
chmod 755 "$STAGE"
mkdir -p "$STAGE/usr/share/shini-tasks/static" \
         "$STAGE/usr/bin" \
         "$STAGE/usr/share/applications" \
         "$STAGE/usr/share/icons/hicolor/scalable/apps" \
         "$STAGE/usr/lib/systemd/user" \
         "$STAGE/DEBIAN" "$OUT"

cp server.py app.py "$STAGE/usr/share/shini-tasks/"
cp -r static/. "$STAGE/usr/share/shini-tasks/static/" 2>/dev/null || true
cp icon.svg "$STAGE/usr/share/icons/hicolor/scalable/apps/shini-tasks.svg"

cat > "$STAGE/usr/bin/shini-tasks" <<'EOF'
#!/bin/sh
# Launcher Shini Tasks (bản .deb): dữ liệu ở ~/.local/share/shini-tasks.
export SHINI_TASKS_DATA="${SHINI_TASKS_DATA:-$HOME/.local/share/shini-tasks}"
export GSK_RENDERER="${GSK_RENDERER:-cairo}"
exec python3 /usr/share/shini-tasks/app.py "$@"
EOF
chmod 755 "$STAGE/usr/bin/shini-tasks"

cat > "$STAGE/usr/share/applications/dev.shini.tasks.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=Shini Tasks
Comment=Quản lý việc cá nhân — local, không tài khoản
Exec=shini-tasks
Icon=shini-tasks
Terminal=false
Categories=Office;ProjectManagement;
StartupWMClass=dev.shini.tasks
EOF

cat > "$STAGE/usr/share/applications/dev.shini.tasks.capture.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=Shini Tasks — Bắt việc nhanh
Comment=Cửa sổ bắt việc siêu nhanh (gán phím tắt Alt+E cho mục này trong Cài đặt hệ thống)
Exec=shini-tasks --capture
Icon=shini-tasks
Terminal=false
NoDisplay=true
Categories=Office;
StartupWMClass=dev.shini.tasks.capture
EOF

cat > "$STAGE/usr/lib/systemd/user/shini-tasks.service" <<'EOF'
[Unit]
Description=Shini Tasks — engine (API + nhắc việc)
After=network.target

[Service]
Type=simple
Environment=SHINI_TASKS_DATA=%h/.local/share/shini-tasks
ExecStart=/usr/bin/python3 /usr/share/shini-tasks/server.py
Restart=on-failure
RestartSec=3

[Install]
WantedBy=default.target
EOF

cat > "$STAGE/DEBIAN/control" <<EOF
Package: shini-tasks
Version: $VER
Section: office
Priority: optional
Architecture: $ARCH
Depends: python3 (>= 3.10), python3-gi, gir1.2-gtk-4.0, gir1.2-adw-1, libnotify-bin
Maintainer: Shini Web <ngocsinh6905@gmail.com>
Description: Quản lý việc cá nhân — local, không tài khoản (tiếng Việt)
 Bảng kanban, lịch, nhắc việc có nút bấm, bấm giờ thật, đồng bộ 2 máy.
 Dữ liệu nằm hoàn toàn trên máy của bạn (~/.local/share/shini-tasks).
EOF

cat > "$STAGE/DEBIAN/postinst" <<'EOF'
#!/bin/sh
set -e
if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database -q /usr/share/applications || true
fi
cat <<'MSG'
Shini Tasks đã cài xong. Để engine nhắc việc tự chạy mỗi lần đăng nhập:
  systemctl --user enable --now shini-tasks
Rồi mở "Shini Tasks" trong menu ứng dụng. Gán phím Alt+E cho
"Shini Tasks — Bắt việc nhanh" trong Cài đặt → Bàn phím của hệ thống
để bắt việc siêu nhanh từ bất kỳ đâu.
MSG
exit 0
EOF
chmod 755 "$STAGE/DEBIAN/postinst"
chmod 755 "$STAGE/DEBIAN"
find "$STAGE/usr" -type d -exec chmod 755 {} +
find "$STAGE/usr" -type f -exec chmod 644 {} +
chmod 755 "$STAGE/usr/bin/shini-tasks"

dpkg-deb --build --root-owner-group "$STAGE" "$OUT/shini-tasks_${VER}_${ARCH}.deb"
echo "Da dong goi: $OUT/shini-tasks_${VER}_${ARCH}.deb"
