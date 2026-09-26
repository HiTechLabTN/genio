# MODEL_ROUTING — routeur résilient (implémentation)

`core/model_router.py` : endpoints `ollama-primary` + `ollama-backup-N`
(11434), `gemini`/`openrouter` (si clés, taggés CLOUD_FALLBACK).
Backends déclarés : OLLAMA_LOCAL (+), GGUF_DIRECT (−, pas de llama-server),
HITECH_OS_DAEMON (−, pas de socket), CLOUD_FALLBACK (si `GENIO_ALLOW_CLOUD=1`).

Failover ordonné par priorité + retry vide→retry, timeout par tour 120s
(env), disjoncteur exponentiel (5s→300s) + reset au succès.
Porte vie privée : cloud sauté + tracé sans autorisation explicite.
Limite : modèles `:cloud` via router Ollama local = confiance router.
Tests : `tests/test_model_router.py`.
