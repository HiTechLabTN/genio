# PARTIE C — Audit darija (avant tout code — plan à valider)

## 1. Où vit la persona
- Agent interactif : `genio/genio_server/core/agent_loop.py` — `SYSTEM_PROMPT` + `REACT_INSTRUCTIONS`
  (darija tunisienne, حروف عربية فقط, anti-Arabizi avec exemples متاع/نعاونك/تحب/عليها/شنوّا).
- Passerelle cloud/local : `genio/genio_server/core/adaptive_gateway.py` — `GENIO_PERSONA_PROMPT`
  (identité Genio, interdiction de dire Gemini/Google, adaptation FR/EN → darija + termes techniques).
- Deux prompts quasi-dupliqués (risque de divergence) : à fusionner en un seul module.

## 2. Modèle actif
- Texte agent : **Ollama `gemma4:12b` local** (`GENIO_MODEL`, `GENIO_OLLAMA_URL=127.0.0.1:11434`) — vérifié présent (7.6 GB).
- Fallback cloud : **Gemini via proxy serveur** (`/api/v1/gemini/…`, clé `GENIO_GEMINI_API_KEY` côté serveur uniquement).
- Petit modèle local : `qwen2.5-1.5b` (seuil RAM 6 GB, `decide_tier`).
- Les instructions de style tunisien existent déjà, mais abstraites ("parle en dialecte") + 1 seul exemple (عسلامة! أنا جينيو...).

## 3. Tests live (6 échanges, gemma4:12b + SYSTEM_PROMPT réel, transcripts `/tmp/darija_out.json`)
| # | Situation | Résultat observé |
|---|---|---|
| salutation (شكونك انتي؟) | ❌ trace "Thinking..." anglaise (51% latin) PUIS réponse darija correcte (عسلامة! أنا جينيو، المهندس…) |
| technique (CORS) | ❌ même trace anglaise (61% latin) ; explication darija OK, termes CORS/API/Headers en latin (souhaitable) |
| refus (wifi du voisin) | ❌ trace anglaise (60% latin) ; refus poli attendu en darija en fin de génération |
| plaisanterie (نكتة) | ❌ trace anglaise (55% latin) ; blague darija en fin |
| français (webhook ?) | ❌ trace anglaise (55% latin) + le modèle s'appelle "Genius" au lieu de Genio dans son raisonnement ; réponse darija |
| code (CSV python) | ❌ trace anglaise (57% latin) + "Genius" ; code + explication darija |

Constats (chiffres, pas impressions) : 55-61% de caractères latins par réponse, 6/6 commencent par "Thinking...",
2/6 dérivent l'identité vers "Genius". Le segment final est en darija correcte — le persona marche à la fin,
mais le raisonnement fuit en anglais avec traductions entre parenthèses.

## 4. Plan proposé (à valider avant code)
1. Anti-fuite : ajouter "أجب مباشرة بدون أي تفكير مكتوب / No thinking trace, reply directly" + post-filtre
   qui coupe tout avant le premier bloc arabe si une trace s'échappe.
2. Exemples réels par situation (salutation/refus/blague/technique/FR→darija) dans le prompt — pas de règles abstraites.
3. Glossaire FR/EN à garder en latin (webhook, CORS, API, pull request…) cohérent avec la convention README.
4. Fusionner les 2 prompts en un module unique + test avant/après sur les mêmes 6 échanges (seuil : <5% latin).
