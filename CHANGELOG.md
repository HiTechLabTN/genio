# Changelog

Toutes les modifications architecturales significatives du repo Genio sont
documentées ici, par phase.

## Phase 0 — Baseline de sécurité

- **`genio_server/tools/bash_tool.py`** : remplacement de `DENIED_PREFIXES`
  (liste de préfixes facilement contournables) par la fonction
  `is_dangerous(command) -> Optional[str]` qui tokenise chaque segment
  (chevron `&&`, pipe `|`, point-virgule `;`) avec `shlex.split` et refuse :
  - `rm -rf` / `-r`/`-f` ciblant `/`, `/*`, `~`, `.`, `..` ou un chemin hors
    du workdir autorisé ;
  - `dd` sur `/dev/sd*` (via `of=`/`if=`) ;
  - `mkfs.*` ;
  - redirection `>` sur `/dev/sd*` ;
  - `chmod -R 777 /` ;
  - fork bombs (`:(){ :|:& };:`) ;
  - `sudo` (refus par défaut, activable via `GENIO_ALLOW_SUDO=1`).
  - Contournements de l'audit couverts : `sudo rm -rf /`, `rm -rf /*`,
    `bash -c "rm -rf /"`, `cd / && rm -rf .`.
- **Nouveau** `test_bash_tool_safety.py` : 37 cas (refus dangereux + commandes
  légitimes + gardes d'environnement).
- **`genio_server/server/main.py`** :
  - garde de démarrage `GENIO_ENV` (`dev` par défaut) : en `prod`, un
    `GENIO_API_KEY` vide fait échouer le démarrage avec un message explicite ;
  - `allow_origins` passé de `*` à une liste lue depuis `GENIO_CORS_ORIGINS`
    (CSV), défaut `["http://localhost:1420"]` (port Tauri dev).

## Phase 1 — Unification mémoire / agent interactif

- **`core/memory_engine.py`** : nouvelle catégorie de données `session_context`
  (liste de faits projet/utilisateur `{ts, category, text}`), distincte des
  `rules` éditoriales de contenu. Méthodes : `add_context(text, category)` et
  `context_text(limit=20)` (bornée, déduplique les faits consécutifs).
  Aucune modification des règles Darija/SVG existantes (pipeline de contenu
  intact).
- **`genio_server/core/agent_loop.py`** : `build_instructions()` injecte
  `get_memory().context_text()` (le contexte de session, PAS les rules
  éditoriales) dans le system prompt. Paramètre optionnel `memory=` pour un
  test propre ; import de `core.memory_engine` en best-effort avec dégradation
  silencieuse si non résolvable.
- **Nouveau** `test_phase1_memory_agent.py` (4 cas).
