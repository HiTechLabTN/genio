#!/usr/bin/env bash
# Genio official bootstrap — safe curl|bash entry point.
#
#   curl -fsSL https://raw.githubusercontent.com/HiTechLabTN/genio/main/installer/bootstrap/install.sh | bash
#
# Integrity model (honest, no fake crypto claims):
#   - HTTPS only (curl --proto =https --tlsv1.2).
#   - Optional GENIO_REF pin (tag/branch/commit). When set, the cloned repo
#     is verified with `git rev-parse HEAD` and reported; the install
#     aborts if the checkout does not match a resolvable ref.
#   - No checksum/signature verification of the bootstrap itself is
#     implemented: GitHub TLS + pinned ref is the stated trust basis.
#     Do not claim more.
set -euo pipefail

GENIO_REPO="${GENIO_REPO:-https://github.com/HiTechLabTN/genio.git}"
GENIO_REF="${GENIO_REF:-main}"
GENIO_PREFIX="${GENIO_PREFIX:-$HOME/.local/share/genio}"
# GENIO_ASSISTANT=1 → assistant experience instead of --yes (needs a TTY;
# the assistant reads from /dev/tty because stdin is the script pipe).
GENIO_ASSISTANT="${GENIO_ASSISTANT:-}"

# Minimal fix command for a missing tool (small packages only, never bundles).
suggest_fix() {
  case "$1" in
    git) pkg="git" ;;
    python3) pkg="python3" ;;
    curl) pkg="curl" ;;
    *) pkg="$1" ;;
  esac
  if command -v apt-get >/dev/null 2>&1; then
    echo "sudo apt-get install -y $pkg"
  elif command -v dnf >/dev/null 2>&1; then
    echo "sudo dnf install -y $pkg"
  elif command -v pacman >/dev/null 2>&1; then
    echo "sudo pacman -S --noconfirm $pkg"
  elif command -v apk >/dev/null 2>&1; then
    echo "sudo apk add $pkg"
  else
    echo "(ركّب «$pkg» بمدير الحزم متاع نظامك)"
  fi
}

need() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "🧞 عسلامة، أنا جينيو." >&2
    echo "ناقصني «$1» باش نكمّل. الحزمة الصغيرة «$1» تكفي." >&2
    echo "نفّذ الأمر هذا ثم عاود:" >&2
    echo "  $(suggest_fix "$1")" >&2
    exit 13
  }
}
need git
need python3
need curl

echo "[genio bootstrap] repo=$GENIO_REPO ref=$GENIO_REF prefix=$GENIO_PREFIX"
rm -rf /tmp/genio-bootstrap-src
git clone --depth 1 --branch "$GENIO_REF" "$GENIO_REPO" /tmp/genio-bootstrap-src
HEAD_SHA="$(git -C /tmp/genio-bootstrap-src rev-parse HEAD)"
echo "[genio bootstrap] checked out $HEAD_SHA (ref=$GENIO_REF)"
if [ ! -x /tmp/genio-bootstrap-src/installer/genio ]; then
  echo "installer entry missing in source — aborting (fail closed)" >&2
  exit 15
fi
if [ -n "$GENIO_ASSISTANT" ]; then
  # Assistant experience (Tunisian consent/repair/verify/retry). Reads from
  # /dev/tty; falls back to --yes behavior when no terminal is available.
  exec python3 /tmp/genio-bootstrap-src/installer/genio install \
    --prefix "$GENIO_PREFIX" \
    --source /tmp/genio-bootstrap-src \
    --assistant "$@"
fi
exec python3 /tmp/genio-bootstrap-src/installer/genio install \
  --prefix "$GENIO_PREFIX" \
  --source /tmp/genio-bootstrap-src \
  --yes "$@"
