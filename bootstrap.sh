#!/usr/bin/env bash
set -e
echo "🚀 Genio Setup v4.0"
sudo apt update && sudo apt install -y python3-pip python3-venv ffmpeg docker.io docker-compose curl jq
python3 -m venv venv && source venv/bin/activate
[ -f requirements.txt ] && pip install -r requirements.txt
echo "✅ Installed!"
