# Mixamo — rig + animations Genio (manuel, 1 seule étape non locale)

Le pipeline v4.2 utilise un rig Blender 100% local (34 bones, enveloppes,
8 clips procéduraux). Mixamo reste l'option recommandée si tu veux des
animations mocap premium — c'est la SEULE étape qui sort du tout-local
(compte Adobe gratuit + upload manuel, impossible à automatiser en headless).

## Fichier à uploader
- `assets-pipeline/mesh-raw/v3_clean_mixamo.fbx` (1.9M, 20k verts, 1.7m,
  DECIMATE 40k tris, origine au sol) — exporté par `/tmp/clean_v3.py`.

## Upload Mixamo (https://www.mixamo.com/)
1. Connecte-toi (compte Adobe gratuit), Upload Character → `v3_clean_mixamo.fbx`.
2. Placement des repères : la robe + membres robotiques trompent la détection
   auto — ajuste à la main poignets/coudes/genoux sur les vues d'aide
   (prévoir 5-10 min, c'est le cas prévu par le prompt).
3. Download : personnage riggé FBX (cocher Skin) SANS animation d'abord.
4. Puis télécharger chaque clip IN PLACE (sans déplacement racine — le
   déplacement libre est géré par Rapier côté app) :
   - `Idle` → `idle` | `Waving` → `greeting` | `Head Turn`/`Look Around` → `listening`/`thinking`
   - `Thinking`/`Nodding` → `thinking` | `Talking`/`Talking Two` → `speaking`
   - `Yes`/`Celebration` → `success` | `No`/`Shrugging` → `error`
   - Clip restant → `executing`
5. Noms EXACTS requis par `src/lib/mascotAnimator.ts` :
   `idle, greeting, listening, thinking, executing, success, error, speaking`.

## Recombinaison Blender
Importer perso riggé + chaque clip (Mixamo duplique le squelette par export),
retargeter sur UN SEUL armature de référence, exporter
`genio_client/public/models/genio-mascot.glb` (glTF 2.0, Animation + All Actions),
puis `gltf-transform optimize --compress draco` → `-draco.glb`.

## Alternative 100% locale utilisée en v4.2 (aucun compte)
`/tmp/rig_v3_8clips.py` (34 bones + IK, 4 shape keys bouche/yeux) +
`/tmp/fix_nla_export.py` (8 strips NLA) + `/tmp/fix_envelope.py`
(parent ENVELOPE 38k/44k verts — AUTO Bone Heat échoue sur mesh TripoSR,
documenté). Résultat : `public/models/genio-mascot.glb` 11M (8 clips,
skin 34 joints) + `-draco.glb` 5M. Fidélité single-view correcte
(silhouette robe/barbe/membres OK, fez/lunettes approximatifs — limite
connue, multi-vues ComfyUI + Mixamo = upgrade futur).
