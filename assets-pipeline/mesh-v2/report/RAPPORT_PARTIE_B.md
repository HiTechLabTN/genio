# PARTIE B — Mouvement vivant (code + vérifications automatiques ; watch live à faire)

## Ce qui existait (étendu, pas reconstruit)
- `mascotAnimator.ts` : 8 contextes, mémoire de gestes par utilisateur, dérive Rapier via `moveTo`.
- `RiggedMascot.tsx` : fondu fixe 0.35s, look-at tête lerp 0.08, lip-sync, blink auto.
- `MascotStage.tsx` : re-roll pose au changement d'état + toutes les 3.5s en idle, ressort fixe 60/18, impulsions physiques fixes.

## Changements
1. `lib/mascotAnimator.ts` : `TRANSITION_MS` (error 180ms → thinking 750ms), `SPRING_BY_CONTEXT`
   (thinking 38/22 posé, error 120/14 vif), `PoseTarget.fadeMs` renseigné par `nextPose`.
2. `RiggedMascot.tsx` : fondu clip = `TRANSITION_MS[activeClip]` ; **respiration permanente**
   (`position.y = -0.35 + sin(t*1.4)*0.009`, réduite en error) ; **transfert de poids**
   (`rotation.z = sin(t*0.5)*0.012` en idle/listening/thinking) ; **dérive du regard**
   (`sin(t*0.3)*0.15` yaw en idle-like) — plus de pose figée.
3. `MascotStage.tsx` : ressort framer-motion = `SPRING_BY_CONTEXT[contexte]` ;
   gain d'impulsion Rapier = `stiffness/60` (cohérence énergie clip ↔ vitesse dérive :
   pas de glissade rapide pendant une pose lente). `moveTo` reste réservé à idle/listening
   (déjà le cas dans `generateVariant`) → pas de "marche sur place".

## Vérifications faites
- `tsc --noEmit` : propre.
- `mascotMaster.test.ts` : 16/16 pass.
- Checks Partie B (temporaires, 3/3 pass) : error < thinking (fade), fadeMs cohérent, ressort thinking < error.
- `test_phase_motion_memory.py` : exit 0.

## Watch live RESTANT (à faire dans l'app par AZMI — procédure)
1. Ouvrir la scène mascot, contexte idle : capture t0, attendre 4s, capture t1 → diff pixels > 0
   attendu (respiration + regard + re-roll 3.5s).
2. Décrire : le balancement paraît-il naturel (lent, faible amplitude) ou robotique ?
3. Déclencher `error` puis `thinking` : le fondu error doit claquer (~180ms), thinking fondre (~750ms).
4. Vérifier l'absence de glissade : en thinking, le déplacement reste quasi nul.
Sans ce watch, la Partie B reste "code-complete", pas "PASS" (règle de la mission).
