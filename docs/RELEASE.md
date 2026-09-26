# RELEASE — politique de version (implémentation)

- Commits ciblés par phase : `baseline: …`, `audit(phase2): …`,
  `runtime: …`, `security: …`, `phase-N: …` (une phase = un commit vert).
- Baseline propre exigée avant chaque bloc (worktree vérifié).
- Jamais : secrets, poids modèles (`.safetensors/.bin/.gguf` ignorés),
  DBs runtime (sauf sessions/gestures déjà suivies, petites),
  artefacts lourds (`dist/`, venvs ignorés).
- Binaires : `release.yml` / `release-binaries.yml` (Tauri/APK — `|| true`
  informatifs hors gates, à durcir si réactivés).
- Préparation release : `scripts/package_release.sh` ; staging :
  `export/staged_releases/` + preuves (frames, metrics, wav).
