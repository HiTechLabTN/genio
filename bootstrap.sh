#!/usr/bin/env bash
# Genio — Zero-dependency bootstrap & hardware probe
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "🧠 Genio Bootstrap — Hardware Probe & Dependency Installer"
echo "════════════════════════════════════════════════════════════"

# --- Hardware Probe ---
echo ""
echo "🔍 Hardware Probe:"
echo "   CPU: $(nproc) cores"
echo "   RAM: $(free -h | awk '/Mem:/{print $2}')"
if command -v nvidia-smi &>/dev/null; then
    GPU=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null || echo "unknown")
    echo "   GPU: $GPU (NVENC available)"
else
    echo "   GPU: none (CPU-only mode)"
fi
echo "   Docker: $(docker --version 2>/dev/null || echo 'NOT INSTALLED')"
echo "   Python: $(python3 --version 2>/dev/null || echo 'NOT INSTALLED')"

# --- Dependencies ---
echo ""
echo "📦 Installing dependencies..."
pip install --quiet -r requirements.txt 2>/dev/null || pip3 install --quiet -r requirements.txt

# --- Playwright Browsers ---
echo "🌐 Installing Playwright browsers..."
python3 -m playwright install chromium --quiet 2>/dev/null || true

# --- Environment ---
if [ -f .env ]; then
    echo "🔐 .env found (secrets loaded)"
else
    echo "⚠️  No .env found — copy .env.example and fill in your keys"
fi

echo ""
echo "✅ Genio ready!"
echo "   Run: python3 core/executive_director.py --auto 'Your Lab Topic'"
