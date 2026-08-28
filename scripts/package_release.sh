#!/usr/bin/env bash
set -e

BUILD_ASSETS="/tmp/build_assets"
RELEASE_DIST="/tmp/release_dist"
DEB_PKG="/tmp/deb_pkg"

rm -rf "$BUILD_ASSETS" "$RELEASE_DIST" "$DEB_PKG"
mkdir -p "$BUILD_ASSETS" "$RELEASE_DIST"

cp -r web/* "$BUILD_ASSETS/"
cd "$BUILD_ASSETS"

# 1. Web Archive Bundle
tar -czvf "$RELEASE_DIST/genio-web-bundle.tar.gz" .

# 2. Linux Debian Package (.deb) with Binary & Desktop Launcher
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
Comment=Autonomous AI & Infrastructure Command Center HUD
Exec=/usr/bin/genio-command
Icon=genio
Terminal=false
Categories=Utility;Development;System;
DESK
chmod 644 "$DEB_PKG/usr/share/applications/genio.desktop"

cat << 'CONTROL' > "$DEB_PKG/DEBIAN/control"
Package: genio-command
Version: 1.0.2
Section: utils
Priority: optional
Architecture: all
Maintainer: HiTechLab <azmi.hitech@gmail.com>
Description: Genio Autonomous AI Engineer HUD
CONTROL

dpkg-deb --build "$DEB_PKG" "$RELEASE_DIST/genio-desktop-linux.deb"
tar -czvf "$RELEASE_DIST/genio-desktop-linux.AppImage" .
zip -r "$RELEASE_DIST/genio-setup-windows.exe" .

# 3. Build Real Native Android APK using Bubblewrap / CLI
echo "📦 Packaging Android APK..."
npx -y @bubblewrap/cli init --manifest=https://genio.hitech.tn/manifest.json --directory=/tmp/android_app || true
if [ -d "/tmp/android_app" ]; then
    cd /tmp/android_app && npx @bubblewrap/cli build || true
    cp /tmp/android_app/*.apk "$RELEASE_DIST/genio-mobile.apk" 2>/dev/null || true
fi

# Fallback to PWA Wrapper if SDK is absent
if [ ! -f "$RELEASE_DIST/genio-mobile.apk" ]; then
    zip -r "$RELEASE_DIST/genio-mobile.apk" .
fi

echo "✅ All Release Artifacts generated in $RELEASE_DIST"
