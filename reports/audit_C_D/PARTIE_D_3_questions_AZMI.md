# Partie D — 3 questions à trancher (avant tout code)

**Contexte :** le `self_improve` actuel tourne bien (cron 01h, DB 200, modèle 47h) mais son score est `random.randint` (aucune vraie mesure), et il ne touche que les gestes — pas le cerveau texte ni la darija.

**Q1 — Score :** Remplacer le tirage aléatoire par un vrai signal (feedback utilisateur pouce 👍/👎 + `markPositive`/`recordMotionOutcome` déjà en place), ou garder le tirage et juste logger ?

**Q2 — Périmètre :** Étendre l'apprentissage au **texte darija** (paires Q/R notées, prompt tunisien) ou **rester gestes uniquement** et brancher sur `mascotMemory` par utilisateur ?

**Q3 — Rythme :** Garder la fenêtre batch **01h–06h + garde load** (comme aujourd'hui, skip si charge>4), ou passer à de l'**incrémental continu** (après chaque interaction notée, <30s) ?

Réponds par : `Q1: A/B — Q2: A/B — Q3: A/B` + 1 ligne de préférence, on implémente seulement ce que tu valides.
