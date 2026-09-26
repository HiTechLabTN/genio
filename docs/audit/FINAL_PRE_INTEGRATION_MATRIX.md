# FINAL_PRE_INTEGRATION_MATRIX — GENIO → HiTech-OS gate

SHA audité : `0876057` (+ fixes d'audit à committer : voir § FIXES).
Run CI : `36235662671` (success 4/4). Statuts : PASS/FAIL/UNTESTED/UNAVAILABLE/LIMITATION.

| Gate | Expected | Actual | Evidence | Status |
|---|---|---|---|---|
| CI lint | green pin 0.15.16 | success (job+step API) ; local `All checks passed!` | `gh api .../runs/36235662671/jobs`, `ruff check --select E4,E7,E9,F` exit 0 | PASS |
| CI backend | 287 passed + 27 legacy | Full suite success ; env-suites success (15 deselects nominatifs) | API steps success ; local 287 passed/1 xfailed + 27 passed/15 deselected, exit 0 | PASS |
| CI frontend | tsc+vitest+build | 7/7 steps success ; local tsc 0, vitest 16/16, build dist+sw.js | API steps ; `npm run build` local | PASS |
| CI docker-build | image buildable | success ; `genio:audit3` 314MB rebuildé, sans .env/TOKEN | API step ; `docker build`, `docker run` probes | PASS |
| Deselects (15) | tous légitimes | 2 OBSOLETE (échouent partout) + 13 EXTERNAL_DEP (passent avec sibling, prouvé local 15 passed/2 failed) | run manuel §5, table d'audit | PASS |
| Sibling dep | isolée | try/except + sys.path conditionnel ; runtime ne touche jamais ces chemins (grep) | `core/executive_director.py:27-32`,imports audit | PASS |
| sys.path | justifié | 2 fichiers prod auto-racinés ; 29 tests auto-racinés ; PYTHONPATH bloqué en sandbox | grep audit §8 | PASS |
| Packaging | modes supportés | pas de paquet installé ; systemd WorkingDirectory + Docker WORKDIR + CI root pinnent le CWD (prouvé depuis /tmp) | §9 | LIMITATION |
| Ruff | pin enforced | CI == local == 0.15.16, commande identique, verte des deux côtés | ci.yml:28-29, `ruff --version` | PASS |
| Frontend assets | tous trackés | 3 png latents ajoutés (`-f` + exceptions ciblées) ; 0 UNTRACKED restant ; dead components documentés | audit imports vs ls-files | PASS |
| Playwright | ordre garanti | deps → module → `install --with-deps chromium` → tests ; skipif étroit (2 tests) | ci.yml, `needs_browser` | PASS |
| Sécurité (15 familles) | 123 verts, 0 deselect | 123 passed local ; 0 `--deselect` sécurité en CI | run §15 | PASS |
| Sandbox fail-closed | HOST=0 | live : `SANDBOX_UNAVAILABLE`, rc 125, canaris absents | §16 | PASS |
| Secrets | 0 commité | scans history+live : 1 faux positif (fixture synthétique) ; `.env` réel non tracké | §17 | PASS |
| Docker secrets | hors image | `.env`+patterns `**` vérifiés absents de l'image (`docker run` probe) | §17-18 | PASS |
| Docker hardening | non-root/healthcheck | image root, pas de HEALTHCHECK (recommandation phase OS) | Dockerfile.web | LIMITATION |
| Runtime services | 5×200 + tunnel | :8000/:8098/:5050/:8001/:11434 + genio.hitech.tn 200 | sondes §20 | PASS |
| Voice | 422/200, 0 orphelin | `ar`→422 explicite, `auto`→200 wav 3.44s, PID==MainPID | §21 | PASS |
| Router | cloud fermé | défaut fermé, opt-in explicite, UNAVAILABLE honnêtes (GGUF, socket OS) | §22 | PASS |
| HiTech-OS IPC | contrat seul | v1.0, UDS, adapters, 0 import interne OS, socket env-overridable | §23 | PASS |
| Historique rescue | isolé | 4 commits mono-objet, diffs vérifiés | §24 | PASS |
| Régression vs bdfd9fa | rien retiré | 9 fichiers CI/porta/docs ; 0 feature/API retirée ; +4 tests boot | diffstat §25 | PASS |
| Docs | conformes | boot-guard ajoutée à SECURITY.md ; README quickstart corrigé (`.env.example` créée, vraie entry) | §26 | PASS |
| Release workflows | — | `release-binaries.yml` : masking `|| echo/|| true` étendu (hors gate CI, workflow tag en échec) | §3 | LIMITATION |
| systemd D-Bus | — | restart via systemctl impossible ici (timeouts) ; services laissés sains | RC + §20 | LIMITATION |
| VRAM LLM/TTS | — | contention documentée (éviction planifiée, pas de partage) | RC | LIMITATION |
| Défaut development | — | API ouverte+sandbox opt-in sans clé ; prod=`prod`/`strict`+clé (garde testée) | boot-guard | LIMITATION |
