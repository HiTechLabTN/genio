# MEMORY — architecture (implémentation)

`genio_server/core/memory_schema.py` : `MemoryItem` frozen (texte, kind,
source, timestamp, confidence, provenance, trust SYSTEM/OPERATOR/VERIFIED/
UNVERIFIED/QUARANTINED, expiration, scope, origin).

- Working : tampon borné du tour (20), jamais persisté.
- Episodic : façade lecture `sessions.db` filtrée par session (fail-safe
  hors-loop) ; écritures par la boucle uniquement.
- Semantic : JSONL (`state/semantic_memory.jsonl`) ; externe non vérifié →
  QUARANTINED ; correction = supersède avec chaîne de provenance ; purge
  à expiration ; suppression explicite.
- System : faits statiques lecture seule.

Seul l'autoritaire (SYSTEM/OPERATOR/VERIFIED non expiré) alimente le prompt
(additif). Anti-poison : quarantaine + confiance + isolation par scope.
Tests : `tests/test_memory_architecture.py`. Moteur legacy `core/memory_engine.py`
(règles statiques) coexiste en source de contexte (non cassé).
