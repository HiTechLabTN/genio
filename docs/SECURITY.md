# SECURITY — garanties de confinement et politiques

## Garanties (implémentées + testées)

- **Sandbox fail-closed** : strict sans conteneur → `SANDBOX_UNAVAILABLE`
  (125), jamais d'hôte. Quotas : 512m RAM, 256 pids, 2 CPU, FS lecture seule
  sauf `/work` (+`/tmp` tmpfs). Tests : `test_sandbox_security.py`.
- **Bash structuré** : parse shlex + 10 classes BLOCK (privesc, setuid, mkfs,
  dd devices, chmod 777, fork, docker escape/socket, credentials, /proc/sys,
  LD_PRELOAD, traversal, interpreter escape, rm destructif) ; regex en
  défense en profondeur. Tests : `test_bash_security.py`.
- **FS boundary** : autorisation APRÈS realpath (symlink, `..`, /etc/shadow,
  /root/.ssh, docker.sock, devices). Tests : `test_filesystem_security.py`.
- **Computer-use** : kill-switch, rate-limit 0.5s, coords bornées, caps
  (2000ch, 5 touches, scroll ±20). Tests : `test_computer_use_safety.py`.
- **Browser** : anti-SSRF (IP + DNS-rebinding fail-closed), contextes isolés
  par session, contenu `UNTRUSTED_CONTENT`. Tests : `test_browser_isolation.py`.
- **Uploads** : magic bytes (jamais MIME client), quota 50MB/session, TTL 1h,
  0o600. Tests : `test_upload_security.py`.
- **API/WS** : Bearer 15min (HMAC), rate-limit IP, corps 10MB, nonces
  `[0-9a-f]{32}`, erreurs assainies. Tests : `test_api_security.py`.

## Limites connues (honnêtes)

- Mode `development` (défaut) : sandbox opt-in (`GENIO_SANDBOX_MODE`) ;
  durcissement complet = `GENIO_SECURITY_MODE=strict`.
- `API_KEY` vide = API ouverte (dev assumé ; prod exige clé + Bearer).
- noexec des stagings = montage hôte (non applicable d'ici).
- Modèles `:cloud` via router Ollama local = confiance router (limitation
  connue : pas d'allowlist par modèle à ce stade).
