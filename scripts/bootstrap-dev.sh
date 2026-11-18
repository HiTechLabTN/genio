#!/usr/bin/env bash
set -e

REMOTE_USER="hitech"
POP_IP="100.85.172.4"
TN_IP="100.88.221.37"
MOUNT_POP="$HOME/Serveurs/pop-os-projects"
MOUNT_TN="$HOME/Serveurs/tn-data"
OS_TYPE="$(uname -s)"

echo "=== Initialisation de l'environnement HiTechLab ==="

# 1. Détection de l'OS et installation automatique des prérequis (Tailscale, sshfs, tmux, mosh)
if [[ "$OS_TYPE" == "Darwin" ]]; then
    command -v brew >/dev/null 2>&1 || { echo "Installe Homebrew d'abord : https://brew.sh"; exit 1; }
    command -v tailscale >/dev/null 2>&1 || brew install --cask tailscale
    command -v sshfs >/dev/null 2>&1 || brew install macfuse gromgit/fuse/sshfs-mac
    command -v tmux >/dev/null 2>&1 || brew install tmux mosh
elif [[ "$OS_TYPE" == "Linux" ]]; then
    if ! command -v tailscale >/dev/null 2>&1; then
        echo "Installation de Tailscale..."
        curl -fsSL https://tailscale.com | sh
    fi
    if command -v apt-get >/dev/null 2>&1; then
        sudo apt-get update -qq && sudo apt-get install -y -qq sshfs tmux mosh openssh-client
    elif command -v dnf >/dev/null 2>&1; then
        sudo dnf install -y fuse-sshfs tmux mosh openssh-clients
    elif command -v pacman >/dev/null 2>&1; then
        sudo pacman -Sy --noconfirm sshfs tmux mosh openssh
    fi
else
    echo "Système non supporté directement. Utilise WSL2 sous Windows."
    exit 1
fi

# 2. Connexion assistée au réseau Tailscale si nécessaire
if [[ "$OS_TYPE" == "Linux" ]]; then
    sudo systemctl enable --now tailscaled 2>/dev/null || true
fi

if ! tailscale status >/dev/null 2>&1; then
    echo ""
    echo ">>> Machine non connectée à Tailscale. Scanne le QR code ou ouvre le lien ci-dessous :"
    sudo tailscale up --qr
fi

# 3. Génération d'une clé SSH ed25519 si absente
mkdir -p ~/.ssh && chmod 700 ~/.ssh
if [ ! -f ~/.ssh/id_ed25519 ]; then
    ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519 -N "" -C "$USER@$(hostname)"
fi

# 4. Configuration SSH optimisée (MagicDNS + IP Tailscale de secours + Multiplexing)
if ! grep -q "Host pop-os" ~/.ssh/config 2>/dev/null; then
    cat << 'SSHEOF' >> ~/.ssh/config

# --- HiTechLab Tailscale Infrastructure ---
Host pop-os
    HostName 100.85.172.4
    User hitech
    ServerAliveInterval 15
    ServerAliveCountMax 3
    TCPKeepAlive yes
    ControlMaster auto
    ControlPath ~/.ssh/cm-%r@%h:%p
    ControlPersist 10m

Host tn
    HostName 100.88.221.37
    User hitech
    ServerAliveInterval 15
    ServerAliveCountMax 3
    TCPKeepAlive yes
    ControlMaster auto
    ControlPath ~/.ssh/cm-%r@%h:%p
    ControlPersist 10m
SSHEOF
    chmod 600 ~/.ssh/config
fi

# 5. Autorisation SSH sans mot de passe sur pop-os et tn
for HOST in pop-os tn; do
    if ! ssh -o BatchMode=yes -o ConnectTimeout=5 "$HOST" exit 2>/dev/null; then
        echo ""
        echo ">>> Autorisation SSH requise une seule fois pour '$HOST' (mot de passe de $REMOTE_USER) :"
        ssh-copy-id -i ~/.ssh/id_ed25519.pub "${REMOTE_USER}@${HOST}" || echo "Serveur $HOST injoignable."
    fi
done

# 6. Montage optimisé des dossiers distants (/data/projects et /data) + Favoris
mkdir -p "$MOUNT_POP" "$MOUNT_TN"
OPTS="reconnect,ServerAliveInterval=15,ServerAliveCountMax=3,Ciphers=aes128-gcm@openssh.com,compression=no,kernel_cache,auto_cache"

mountpoint -q "$MOUNT_POP" 2>/dev/null || sshfs "${REMOTE_USER}@pop-os:/data/projects" "$MOUNT_POP" -o "$OPTS" 2>/dev/null || true
mountpoint -q "$MOUNT_TN" 2>/dev/null || sshfs "${REMOTE_USER}@tn:/data" "$MOUNT_TN" -o "$OPTS" 2>/dev/null || true

if [ -d "$HOME/.config/gtk-3.0" ]; then
    grep -q "$MOUNT_POP" ~/.config/gtk-3.0/bookmarks 2>/dev/null || echo "file://$MOUNT_POP Pop-OS Projects" >> ~/.config/gtk-3.0/bookmarks
    grep -q "$MOUNT_TN" ~/.config/gtk-3.0/bookmarks 2>/dev/null || echo "file://$MOUNT_TN TN Server Data" >> ~/.config/gtk-3.0/bookmarks
fi

ln -sfn "$MOUNT_POP" "$HOME/pop-os-projects"
ln -sfn "$MOUNT_TN" "$HOME/tn-data"

echo ""
echo "=== Environnement prêt ! ==="
echo "- Dossier Vibe Coding (pop-os) : ~/Serveurs/pop-os-projects (épinglé dans tes favoris)"
echo "- Dossier Production (TN)      : ~/Serveurs/tn-data (épinglé dans tes favoris)"
echo "- Terminal persistant          : tape 'mosh pop-os' ou 'ssh pop-os'"
