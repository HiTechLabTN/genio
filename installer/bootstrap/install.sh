#!/usr/bin/env bash
# Genio official bootstrap — safe curl|bash entry point.
#
#   curl -fsSL https://raw.githubusercontent.com/HiTechLabTN/genio/main/installer/bootstrap/install.sh | bash
#
# Integrity model (honest, no fake crypto claims):
#   - HTTPS only (curl --proto =https --tlsv1.2).
#   - GENIO_REF accepts a branch (main), a tag (v5.0.0), or a full/short
#     commit SHA. The kind is resolved via ls-remote first: SHAs are NEVER
#     passed to `git clone --branch` (that always fails). SHA checkouts are
#     verified by prefix match against `git rev-parse HEAD`.
#   - No checksum/signature verification of the bootstrap itself is
#     implemented: GitHub TLS + pinned ref is the stated trust basis.
#     Do not claim more.
set -euo pipefail

# Bound stalled HTTP transfers (slow/broken networks fail fast with a clear
# message instead of hanging forever). No new dependencies.
export GIT_HTTP_LOW_SPEED_LIMIT=1000
export GIT_HTTP_LOW_SPEED_TIME=60

GENIO_REPO="${GENIO_REPO:-https://github.com/HiTechLabTN/genio.git}"
GENIO_REF="${GENIO_REF:-main}"
GENIO_PREFIX="${GENIO_PREFIX:-$HOME/.local/share/genio}"
# GENIO_ASSISTANT=1 → assistant experience instead of --yes (needs a TTY;
# the assistant reads from /dev/tty because stdin is the script pipe).
GENIO_ASSISTANT="${GENIO_ASSISTANT:-}"
# GENIO_RESOLVE_ONLY=1 → resolve + verify the ref, print the SHA, exit 0
# without installing. Useful to check a ref before running the installer.
GENIO_RESOLVE_ONLY="${GENIO_RESOLVE_ONLY:-}"

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

# Ref resolution: NEVER treat a commit SHA as a branch (that was the
# 4991070… failure: `git clone --branch <SHA>` always fails).
# Classify via ls-remote first, then use the matching strategy.
REF_KIND=""
if git ls-remote --heads "$GENIO_REPO" "$GENIO_REF" 2>/dev/null | grep -q .; then
  REF_KIND="branch"
elif git ls-remote --tags "$GENIO_REPO" "$GENIO_REF" 2>/dev/null | grep -q .; then
  REF_KIND="tag"
elif printf '%s' "$GENIO_REF" | grep -Eq '^[0-9a-fA-F]{4,40}$'; then
  REF_KIND="commit"
else
  echo "🧞 عسلامة، أنا جينيو." >&2
  echo "الـ ref «$GENIO_REF» موش branch ولا tag ولا commit معروف في $GENIO_REPO" >&2
  echo "تحقق من الاسم وعاود. مثال: GENIO_REF=main ولا GENIO_REF=v5.0.0" >&2
  exit 14
fi
echo "[genio bootstrap] ref kind=$REF_KIND"

if [ "$REF_KIND" = "commit" ]; then
  # Short SHAs cannot be fetched directly (protocol needs full OIDs):
  # resolve via GitHub API when the repo is on github.com, else require
  # the full SHA honestly.
  if printf '%s' "$GENIO_REF" | grep -Eq '^[0-9a-fA-F]{40}$'; then
    FULL_SHA="$GENIO_REF"
  else
    FULL_SHA=""
    case "$GENIO_REPO" in
      *github.com*)
        _slug="$(printf '%s' "$GENIO_REPO" | sed -e 's#.*github\.com[:/]##' -e 's#\.git$##')"
        FULL_SHA="$(curl -fsSL --max-time 20 "https://api.github.com/repos/$_slug/commits/$GENIO_REF" 2>/dev/null | python3 -c 'import json,sys; print(json.load(sys.stdin).get("sha",""))' 2>/dev/null)"
        ;;
    esac
    if ! printf '%s' "$FULL_SHA" | grep -Eq '^[0-9a-f]{40}$'; then
      echo "🧞 «$GENIO_REF» قصير وما نجمتش نحلو لكامل. استعمل الـ SHA الكامل (40 حرف)." >&2
      exit 14
    fi
    echo "[genio bootstrap] short SHA resolved: $GENIO_REF → $FULL_SHA"
    GENIO_REF="$FULL_SHA"
  fi
  # SHA: init + fetch the exact object, then checkout and verify.
  mkdir -p /tmp/genio-bootstrap-src
  git -C /tmp/genio-bootstrap-src init -q
  git -C /tmp/genio-bootstrap-src remote add origin "$GENIO_REPO"
  if ! git -C /tmp/genio-bootstrap-src fetch --depth 1 origin "$GENIO_REF"; then
    echo "🧞 الـ commit «$GENIO_REF» ما تلقاش على $GENIO_REPO" >&2
    exit 14
  fi
  git -C /tmp/genio-bootstrap-src checkout -q FETCH_HEAD
else
  # branch and tag: shallow single-branch clone (tags work with --branch).
  if ! git clone --depth 1 --branch "$GENIO_REF" "$GENIO_REPO" /tmp/genio-bootstrap-src; then
    echo "🧞 ما نجمتش نجيب «$GENIO_REF» ($REF_KIND) من $GENIO_REPO" >&2
    exit 14
  fi
fi
HEAD_SHA="$(git -C /tmp/genio-bootstrap-src rev-parse HEAD)"
echo "[genio bootstrap] resolved SHA=$HEAD_SHA"
if [ "$REF_KIND" = "commit" ]; then
  # Short SHAs match by prefix; full SHAs must match exactly.
  case "$HEAD_SHA" in
    "$GENIO_REF"*)
      ;;
    *)
      echo "SHA mismatch after checkout (want $GENIO_REF, got $HEAD_SHA) — aborting" >&2
      exit 14
      ;;
  esac
fi
if [ ! -x /tmp/genio-bootstrap-src/installer/genio ]; then
  echo "installer entry missing in source — aborting (fail closed)" >&2
  exit 15
fi
if [ -n "$GENIO_RESOLVE_ONLY" ]; then
  echo "[genio bootstrap] ref OK: kind=$REF_KIND sha=$HEAD_SHA (no install performed)"
  exit 0
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
