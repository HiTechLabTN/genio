# PARTIE D — Audit self-improve existant (avant tout plan d'extension)

## 1. Que fait-il concrètement (lu, pas deviné) — `genio/genio_gestures/self_improve.py` (71 lignes)
Fenêtre 01:00-06:00 + skip si load > 4 → 100 paires synthétiques (contexte × émotion) via
`POST localhost:8001/compose` (fallback plan neutre si service absent) → **score culture/personnalité/nouveauté
= `random.randint` (aléatoire, pas une vraie évaluation)** → top-10 en `genio_gestures/gestures.db` (table dataset)
→ `ollama create genio-gesture` depuis `qwen2.5:7b-instruct` → log `reports/v4/cron.log`.

## 2. Tourne-t-il réellement ?
- **Oui** : cron `0 1 * * *` installé ; log du 2026-09-09T01:03 `ollama create genio-gesture success` ;
  modèle `genio-gesture:latest` reconstruit il y a 47h ; DB = 200 lignes (150 réelles + 50 synthétiques cumulées).
- Ce matin : skip `load high 4.33` (garde-fou OK).

## 3. En quoi consiste son "amélioration" ?
- **Gestes uniquement** (plans tête/mains/bouche/corps pour le composer), PAS le cerveau texte, PAS les prompts,
  PAS les scores mémoire. Le "self-eval 0-10" du CHANGELOG est un tirage aléatoire 5-10 : la sélection du top-10
  ne mesure rien de réel. Le `ollama create` re-forge le modèle sur un SYSTEM d'une ligne + 10 plans.

## 4. Répond-il à la demande (Genio qui apprend seul) ?
- **Partiellement et à côté** : il entretient un composer de gestes, pas l'assistant. Aucun apprentissage sur les
  conversations, les prompts, les goûts d'AZMI, ni la qualité darija. Construire un 2e système parallèle est le
  risque à éviter — toute extension doit brancher sur : `gestures.db` + `mascotMemory` (déjà par-utilisateur côté
  client) + feedback explicite (`markPositive`, outcomes `recordMotionOutcome`).

## 5. Calibration à trancher avec AZMI (pas de code avant)
a) Remplacer le score aléatoire par un vrai signal (feedback utilisateur + outcomes existants) ?
b) Étendre au texte (paires Q/R darija notées) ou rester gestes ?
c) Garder la fenêtre 01-06h + garde load, ou passer à l'incrémental au fil de l'usage ?
