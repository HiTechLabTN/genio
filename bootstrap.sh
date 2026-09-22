#!/usr/bin/env bash
set -e
echo "🚀 مرحباً بك في مثبت Genio Autonomous AI v4.0"
sudo apt update && sudo apt install -y python3-pip python3-venv ffmpeg docker.io docker-compose curl jq zip
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
[ -f requirements.txt ] && pip install -r requirements.txt
if ! command -v ollama &> /dev/null; then
    curl -fsSL https://ollama.com/install.sh | sh
fi
echo "✅ اكتمل تثبيت وتجهيز بيئة Genio بنجاح!"
