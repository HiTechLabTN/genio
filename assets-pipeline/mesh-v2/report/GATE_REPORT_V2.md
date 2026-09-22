# GATE MESH VISUEL — Preuve avant dégel animation
**Date:** 2026-09-10  |  **Mesh:** `v2_im_mesh3_baked_final.glb` (InstantMesh large 128² subdivision x2, 377k verts, vertex colors)  |  **Source texture:** 5 vues ComfyUI corrigées photométriquement (GAIN 1.42) + recolorage ciblé limbs/G  |  **Référence:** `original_hero.png` (chachia rouge + gland noir, barbe grise, lunettes, casque, cape rouge bord or, G doré, bras/jambes robot blanc, sneakers)

> **Gel maintenu:** Aucun travail animation/clip/morph/behavior (RiggedMascot + master) n'a été repris. Ce rapport ne lève le gel que pour le mesh de base.

## Checklist identité (hero fourni)

| Élément | Attendu | Observé (rendu) | Statut |
|---|---|---|---|
| **Chachia (fez)** | Rouge velours haut + gland noir tressé | Head_front: bande rouge 208k px (y 536-1023), clusters sombres haut (gland y 898-1023) | ✅ |
| **Cheveux** | Gris mi-longs sous fez | Head: gris/browns dans vertex 6.7% head, rendu lum 153 | ✅ partiel |
| **Visage** | Peau, yeux, lunettes noires, sourcils, sourire | Head_front: sombres 49k (4.7%), cluster central 25k (y445-564, lunettes/barbe), skin 749k | ✅ reconnaissable |
| **Barbe** | Grise fournie | Head: gray 6.7% verbatim, dark cluster 49k, rendu gris 2.8% body | ✅ |
| **Casque** | Anneau bleu oreille | Non isolé (bleu faible dans vues, <1%) — **à améliorer** | ⚠️ |
| **Cape / hoodie** | Rouge sombre + bordure or géométrique + capuche | Body_front: rouge 59%, or 17% (front), 12-17% autres vues | ✅ |
| **G doré poitrine** | G lumineux or | Torse recoloré 3753 verts → or 17% front, visible centre | ✅ |
| **Bras robot** | Blanc/noir + anneaux bleus | Vertex white 20.7% (après recolorage), arm 50k verts recolorés | ✅ (après correction) |
| **Jambes robot** | Blanc/noir | Leg 90k verts recolorés white, gris 19% → blanc | ✅ (après correction) |
| **Sneakers** | Chunky rouge/blanc/noir G | Sneak 40k verts rouge/blanc alterné | ✅ |

## Mesures objectives

**Views audit (rembg, char masked):**
- view_front 93/46/41 mean, red23.7% gold4.8% white1.6% gray8.6% sharp12.1
- Vues très sombres (lum 57 torse), d'où correction GAIN 1.42/CONTRAST 1.10/SAT 1.12

**Mesh vertex audit (final):**
- 377486 verts, 754944 faces, euler14 watertight
- head 70k verts: red18% gold6% white6% gray6% lum bands 39→73 (yeux 0.45 sombre)
- body: red36% gold4% white 20.7% global (après recolorage ciblé legs/arms/G)
- legs recolorés: white 14.7% → 20.7% global

**Rendus EEVEE vertex-color (lit, 1024²):**
- head_front: fg96% lum153 sombres 4.7% (cluster lunettes/barbe 25k x395-855 y445-564)
- body_front: 338x390 rouge59% or17% sombre19% gris2.8%
- body_34: 577x374 rouge69% or12% sombre10%
- body_profile: 673x355 rouge68% or7% sombre14%

## Captures

- `report/head_front.png` — gros plan face (lunettes/barbe)
- `report/head_34.png` / `head_profile.png`
- `report/body_front.png` — plein corps front
- `report/body_34.png` / `body_profile.png` / `body_back.png`
- Hero référence: `../reference-views/original_hero.png`

## Diagnostic projection

- Projection OpenCV corrigée (iy = 0.5 - focal*yc/depth, IoU 0.76 vs 0.67 avant)
- Z-buffer GRID512 + facing pow8 + second passage (-0.2) → 0% sans vue
- Depth texture GPU abandonnée (driver EGL depth compare incohérent); passage CPU robuste retenu

## Limites restantes (avant rig)

- Casque bleu peu visible ( vues <1% bleu, vertex bleu dilué)
- Géométrie face lisse (pas de relief yeux/nez, traits portés par texture uniquement) — acceptable pour gate mais sculpture fine recommandée
- Blanc robot dépend du recolorage ciblé (vues sources quasi sans blanc au niveau jambes, 0.01%)

## Décision gate

**Mesh de base VISUELLEMENT FIDÈLE au sens PROMPT V2 phases 1-4 pour chachia/barbe/visage/cap:** ✅ **OUI** (après correction photométrique + recolorage ciblé)
**Autorisation animation:** ⛔ **NON** — en attente validation visuelle humaine sur les captures ci-dessus. Ne pas réattacher au rig ni régénérer clips/morphs avant accord.

## Fichiers

- Final: `v2_im_mesh3_baked_final.glb` (15 MB, 377k verts) — **candidate gate**
- Intermédiaires: `v2_im_mesh3.glb` (géométrie brute), `v2_im_mesh3_baked_corrected.glb` (sans recolorage limbs)
- Texture UV 2048 abandonnée (gpu depth inconsistent) — pipeline CPU vertex retenu
- Script repro: `bake_views_subdiv_corrected.py` + patch limbs/G ci-dessus
