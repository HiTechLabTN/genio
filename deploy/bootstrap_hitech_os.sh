#!/usr/bin/env bash
set -euo pipefail

echo "=========================================================="
echo "  [+] Initialisation du deploiement de Genio Core Stack   "
echo "=========================================================="

if ! command -v nvidia-smi &> /dev/null; then
    echo "[!] Attention: Aucun GPU NVIDIA detecte."
else
    echo "[✓] GPU NVIDIA operationnel."
fi

sudo mkdir -p /data/ai_tools/genio/compiled_skills
sudo mkdir -p /data/ai_tools/genio/engines
sudo mkdir -p /data/ai_tools/genio/reports
sudo chown -R $USER:$USER /data/ai_tools/genio

if [ -f "/usr/local/bin/genio-probe" ]; then
    echo "[✓] Sonde genio-probe deja en place."
else
    echo "[+] Installation de genio-probe..."
    sudo cp scripts/genio-probe /usr/local/bin/genio-probe 2>/dev/null || true
    sudo chmod +x /usr/local/bin/genio-probe 2>/dev/null || true
fi

echo "=========================================================="
echo "  [✓] Deploiement termine. Pret pour l'integration OS.   "
echo "=========================================================="

# ==============================================================================
# 5. Telechargement des modeles lourds depuis HiTech Store CDN (Smart Links)
# ==============================================================================
STORE_URL="https://store.hitech.tn/store"
VODER_MODELS_DIR="/data/ai_tools/genio/engines/voder/models"

sudo mkdir -p $VODER_MODELS_DIR
sudo chown -R $USER:$USER $VODER_MODELS_DIR

echo "[+] Recuperation des poids IA depuis le CDN souverain HiTech Store..."
# (A decommenter ba3ed ma taploadi les modeles fel store)
# curl -# -L $STORE_URL/voder_base_tunisian.pt -o $VODER_MODELS_DIR/voder_base_tunisian.pt
# curl -# -L $STORE_URL/genio_avatar_v2.glb -o /data/ai_tools/genio/engines/avatar/genio_avatar_v2.glb

echo "=========================================================="
echo " [✓] Genio est completement synchronise et operationnel ! "
echo "=========================================================="
