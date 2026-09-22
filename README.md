# 🧞 Genio — Sovereign Autonomous AI Co-Founder & Technical Director

> **Genio** est l'ecosysteme d'intelligence artificielle souverain de l'infrastructure **HiTech Lab**.
> Concu pour operer en local sur station de travail (RTX 3060 12GB) et maille avec le cloud/VPS via Tailscale et Cloudflare Tunnels.

---

## 🏛️ Architecture & Composants Cles

                            ┌───────────────────────────────┐
                            │   Sovereign Cockpit (PWA)     │
                            └──────────────┬────────────────┘
                                           │ WebSocket / WebRTC
                                           ▼
    ┌─────────────────────────────────────────────────────────────────────────────┐
    │ Pop!_OS / HiTech-OS Host (RTX 3060 12GB)                                    │
    │                                                                             │
    │  [3D Avatar Engine]      [Core Agent Loop]        [Voice Synthesis]         │
    │  - Rigged Chibi GLB      - Gemma4:12B / Qwen2.5   - VODER Zero-Shot Local   │
    │  - Bone socket submeshes - 100% Tunisian Darija   - Low-latency port :5050  │
    │  - Three.js / React-R3F  - 0% Latin token leak    - Auto-offload idle 300s  │
    │                                                                             │
    │  [Midnight Patrol & Compiler]       [Telemetry & Health Probe]              │
    │  - Deterministic Scoring (0.5/0.3)  - JSON Telemetry (:8095, GPU, Mesh)    │
    │  - Skill generation in /compiled/   - genio-probe CLI daemon                │
    └─────────────────────────────────────────────────────────────────────────────┘

---

## 📊 Etat des Validations (Release Milestone)

| Chantier | Composant / Module | Metrique / Statut | Description |
| :--- | :--- | :--- | :--- |
| **Partie A** | Avatar 3D Chibi & Sockets | **PASS** | v2_fallback_baked_rigged.glb + sous-maillages (gland, casque). |
| **Partie B** | Mouvement & Cinematique | **PASS (11.75%)** | 60 FPS synchronise, cinematique continue sans vertex tearing. |
| **Partie C** | Persona Darija & Anti-leak | **PASS (0.00%)** | 10 cycles AgentLoop : 0.00% fuite latine, Darija pure. |
| **Partie D** | Evolution & Patrouille Minuit| **PASS** | Scoring deterministe (0.5/0.3/0.2) + timer 03:00. |
| **Audio** | VODER Zero-Shot Cloning | **ACTIVE (:5050)**| Remplacement souverain d'ElevenLabs avec dechargement intelligent. |
| **Ops** | Sonde Telemetrique | **ACTIVE** | Sortie JSON standardisee pour monitoring et self-healing. |

---

## 🚀 Installation & Deploiement Rapide (HiTech-OS / Debian-based)

Pour deployer Genio sur une nouvelle infrastructure ou apres l'installation de HiTech-OS :

    git clone [https://github.com/HiTechTN/Genio.git](https://github.com/HiTechTN/Genio.git) /data/ai_tools/genio
    cd /data/ai_tools/genio
    chmod +x deploy/bootstrap_hitech_os.sh
    ./deploy/bootstrap_hitech_os.sh

