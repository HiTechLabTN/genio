#!/usr/bin/env bash
# Apply the Android cleartext-traffic overlay onto the Tauri-generated Android project.
# Copies the hardened AndroidManifest.xml + network_security_config.xml into
# src-tauri/gen/android AFTER `tauri android init` regenerates the project.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OVERLAY="$ROOT/android-overlay"
DEST="$ROOT/src-tauri/gen/android/app/src/main"

if [ ! -d "$DEST" ]; then
  echo "ERROR: generated Android project not found at $DEST (run 'npx tauri android init' first)" >&2
  exit 1
fi

cp "$OVERLAY/AndroidManifest.xml" "$DEST/AndroidManifest.xml"
mkdir -p "$DEST/res/xml"
cp "$OVERLAY/res/xml/network_security_config.xml" "$DEST/res/xml/network_security_config.xml"

echo "Android cleartext overlay applied to $DEST"
