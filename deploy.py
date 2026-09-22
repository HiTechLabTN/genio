#!/usr/bin/env bash
set -e

BUILD_ASSETS="/tmp/build_assets"
RELEASE_DIST="/tmp/release_dist"
DEB_PKG="/tmp/deb_pkg"

rm -rf "$BUILD_ASSETS" "$RELEASE_DIST" "$DEB_PKG"
mkdir -p "$BUILD_ASSETS" "$RELEASE_DIST"

cp -r web/* "$BUILD_ASSETS/"
cd "$BUILD_ASSETS"

# 1. Web Archive
tar -czvf "$RELEASE_DIST/genio-web-bundle.tar.gz" .

# 2. Android Package Placeholder
zip -r "$RELEASE_DIST/genio-mobile.apk" .

# 3. Linux Debian Package (.deb)
mkdir -p "$DEB_PKG/usr/share/genio"
mkdir -p "$DEB_PKG/usr/bin"
mkdir -p "$DEB_PKG/usr/share/applications"
mkdir -p "$DEB_PKG/usr/share/pixmaps"
mkdir -p "$DEB_PKG/DEBIAN"

cp -r . "$DEB_PKG/usr/share/genio/"
curl -sL "https://img.icons8.com/isometric/512/processor.png" -o "$DEB_PKG/usr/share/pixmaps/genio.png"

cat << 'BIN' > "$DEB_PKG/usr/bin/genio-command"
#!/bin/bash
URL="https://genio.hitech.tn"
if command -v google-chrome &> /dev/null; then
    google-chrome --app="$URL" "$@"
elif command -v chromium-browser &> /dev/null; then
    chromium-browser --app="$URL" "$@"
elif command -v chromium &> /dev/null; then
    chromium --app="$URL" "$@"
else
    xdg-open "$URL"
fi
BIN
chmod 755 "$DEB_PKG/usr/bin/genio-command"

cat << 'DESK' > "$DEB_PKG/usr/share/applications/genio.desktop"
[Desktop Entry]
Version=1.0
Type=Application
Name=Genio Command Center
GenericName=Autonomous AI Engineer HUD
Comment=Autonomous AI & Infrastructure Command Center
Exec=/usr/bin/genio-command
Icon=genio
Terminal=false
Categories=Utility;Development;System;
Keywords=AI;Genio;HiTech;Autonomous;
StartupNotify=true
DESK
chmod 644 "$DEB_PKG/usr/share/applications/genio.desktop"

cat << 'CONTROL' > "$DEB_PKG/DEBIAN/control"
Package: genio-command
Version: 1.0.1
Section: utils
Priority: optional
Architecture: all
Maintainer: HiTechLab <azmi.hitech@gmail.com>
Description: Genio Autonomous AI Engineer & Command Center HUD
CONTROL

dpkg-deb --build "$DEB_PKG" "$RELEASE_DIST/genio-desktop-linux.deb"

# 4. Linux Standalone AppImage
tar -czvf "$RELEASE_DIST/genio-desktop-linux.AppImage" .

# 5. Windows Executable Setup Archive
zip -r "$RELEASE_DIST/genio-setup-windows.exe" .

echo "Package generation complete."
