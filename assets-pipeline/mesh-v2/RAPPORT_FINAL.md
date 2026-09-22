# Rapport final — Mission « REFAIRE la mascotte 3D (v2, sans raccourcis) »

Date : 10 septembre 2026 — Machine : Pop!_OS/Linux, RTX 3060 12GB, 64GB RAM

## Résumé

La mascotte Genio a été entièrement refaite en 3D (v2) : vues multi-angles ComfyUI →
reconstruction TripoSR → remesh Blender manifold → rig Heat 100 % + 8 clips exacts →
texture éclaircie → intégration `public/models/genio-mascot.glb` + `-draco.glb` →
vérification mouvement réel dans l'app (build + vite preview + Playwright).

**Toutes les portes bloquantes sont PASS.**

---

## Phase 1 — Vues de référence multi-angles (ComfyUI)

- 5 vues A-pose générées : `assets-pipeline/reference-views-v2/`
  (`view_front`, `view_34L`, `view_34R`, `view_profile`, `view_back`).
- Référence de style : `assets-pipeline/reference-views/original_hero.png`
  (fez rouge + gland noir, barbe/cheveux gris, lunettes noires, casque,
  robe rouge à bordures dorées, membres robotiques blanc/noir, pendentif « G »,
  baskets blanc/rouge/noir).

## Phase 2 — Reconstruction 3D (TripoSR + remesh)

- TripoSR (cuda:0) → `mesh-v2/0/mesh.obj` → `remesh_v2.py` → `v2_remesh.blend`.
- **Manifold** : 75 208 verts, 0/150 424 arêtes non-manifold.
- Texture `texture_multi.png` 2048² : rouge 6,9 %, gris 13,1 %, peau 8,8 %,
  noir 42,3 % — palette conforme à la checklist.
- **Porte 2 — PASS avec réserves** : région visage (rendu EEVEE de
  `v2_clean.glb`) = fez 24 %, barbe 33 %, peau 8 % (front) ; 3/4 = fez 12-13 %,
  barbe 36-37 %, peau 4,5-5 %. Réserve : détail fin du visage limité par
  TripoSR (hist_intersect vs référence = 0,046).

## Phase 3 — Rig + animations (Blender)

- **Piège résolu** : l'export glTF duplique les verts aux coutures UV
  (91 093 verts, 31 352 arêtes non-manifold → Heat AUTO = 0 %). Solution :
  rigger depuis le **blend** manifold (`v2_remesh.blend`), pas depuis le glb.
- `rig_v2.py` : **HEAT_COVERAGE 75 208/75 208 = 100,0 %**, NONMANIFOLD 0/150 424,
  34 os, 4 morphs (mouth_open, smile, eye_blink_L/R).
- **8 clips EXACTS** (noms requis par `mascotAnimator.ts`) : `idle`,
  `greeting`, `listening`, `thinking`, `executing`, `success`, `error`,
  `speaking` — exportés via NLA strips (l'exporter Blender 3.0 ne sort que
  l'action active sinon).
- **Porte 3 — PASS** : Heat 100 %, 8/8 clips vérifiés par pygltflib.

## Phase 4 — Vérification visuelle et mouvement

- `check_anim.py` → **VERDICT IDLE_MOVES** : toutes les actions bougent
  (idle : head 0,0742 / upper_arm 0,0494 / hand 0,0604).
- Rendu EEVEE (Cycles cassé dans cet environnement — sortie binaire ;
  workbench trop sombre) : `gate_final/` front/3-4/profil/back.
- **Texture éclaircie** (`texture_multi_bright.png`, brightness ×2,0 +
  saturation ×1,3) : la texture d'origine (mean 50) rendait le personnage
  quasi invisible dans l'app (mean 13 sur la zone rouge). Après éclaircissement :
  rendus EEVEE front = barbe 81 %, peau 12 %, fez 7,5 %.
- **Porte 4 — PASS** : IDLE_MOVES + captures EEVEE.

## Phase 5 — Intégration + test mouvement réel

- `npm run build` OK ; `vite preview` sur 4180 ; backend genio (uvicorn 8000) actif.
- **Playwright — diff pixels entre 2 captures à 4 s d'écart** :
  - AVEC backend : **4,053 %** (> 0) ✓
  - SANS backend (réseau coupé) : **4,890 %** (> 0) ✓ — le cycle idle tourne
    par défaut (`agentStatus` initial `{kind:"idle"}`), **aucune correction
    MascotStage.tsx nécessaire**.
  - Fallback RiggedMascot (master bloqué) : **4,183 %** ✓ — notre v2 s'affiche
    et bouge (rouge 12 772 px, barbe 5 735 px, peau 14 022 px dans le canvas).
- **Draco validé dans le navigateur** (three.js DRACOLoader) : 1 mesh,
  34 bones, 8 clips, 4 morphs. Correction nécessaire : les accessors du mesh
  doivent rester dans le primitif (bufferView=None) pour que le décodeur
  connaisse les types (structure identique au master draco qui fonctionne).
- **Porte 5 — PASS** : mouvement réel vérifié avec et sans backend.

## Livrables

| Fichier | Taille | Contenu |
|---|---|---|
| `public/models/genio-mascot.glb` | 17,62 MB | v2 complet, 8 clips, 4 morphs, 34 os |
| `public/models/genio-mascot-draco.glb` | 11,78 MB | v2 draco (KHR_draco_mesh_compression), 8 clips |
| `assets-pipeline/mesh-v2/v2_rigged.blend` | — | source riggée (8 actions) |
| `assets-pipeline/mesh-v2/texture_multi_bright.png` | 2048² | texture éclaircie |

Chargement local : ~75-102 ms pour le glb 18,47 MB (durée mesurée Playwright).

## Limites connues

1. **L'app affiche le master (v4.3.0, `genio_mascot_master_draco.glb`) par
   défaut** ; notre v2 remplace `genio-mascot.glb` utilisé par `RiggedMascot`
   (fallback de la chaîne master → v3 → CyberAvatar). Le fallback a été
   vérifié fonctionnel (rendu + mouvement). Changer la hiérarchie d'affichage
   n'était pas dans le périmètre de la mission (régression possible : le
   master a 52 clips / 28 morphs).
2. Détail fin du visage limité par TripoSR (reconstruction mono-vue).
3. Rendu de vérification EEVEE uniquement (Cycles inutilisable ici).
4. `genio-mascot-draco.glb` n'est référencé par aucun code (livrable de
   remplacement, validé en chargement navigateur).
5. Pas de bump de version ni de commit (conflits git préexistants non touchés).

## Outils finalement utilisés

ComfyUI (vues multi-angles) → TripoSR (reconstruction) → Blender 3.0.1
(remesh, rig Heat, export NLA, rendus EEVEE) → draco3d Node (compression,
car Blender 3.0.1 n'a pas `libextern_draco.so`) → Playwright (tests mouvement).