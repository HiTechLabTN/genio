# PARTIE A — Mesh fidèle (rapport avec preuves regardées)

## 1. Isolation régression InstantMesh (regardé, pas statistique)
- `A_im3_raw_front.png` : **amas rouge hérissé de pointes avec un trou béant, aucun bras/jambe/tête** — pas humanoïde.
- `A_im3_raw_profile.png` : **3 blocs déconnectés qui flottent** — confirme l'échec.
- Conclusion : `v2_im_mesh3.glb` (23 606 verts, euler 14, 10 composantes) est **déjà cassé AVANT subdivision/bake**.
  Le bug est dans la reconstruction InstantMesh elle-même (poses/fond/calibration), PAS dans `bake_views_subdiv*.py`.
  Inutile de rendre après chaque sous-étape du bake : la cause est en amont. Filière InstantMesh abandonnée.
- Ancien rapport "✅ reconnaissable" invalidé : il reposait sur des % de pixels, jamais sur un visionnage.

## 2. Repli appliqué : géométrie v2_clean + nouvelle couleur bake
- `A_v2clean_geo_front.png` (matériau neutre) : **petit personnage chibi de dos, grosse tête, manteau long, bras le long du corps, jambes + chaussures épaisses** — géométrie humanoïde saine (91 093 verts).
- Orientation trouvée par test : avant = -Z trimesh (= +Y Blender). Caméras Y-up : front 0° / 34R 45° / profil 90° / dos 180° / 34L 315°, GRID512 z-buffer + facing, GAIN 1.42/CONTRAST 1.10/SAT 1.12, 152 verts sans vue.
- `v2_fallback_baked.glb` (2.9 MB) : **mêmes sommets/faces que v2_clean** (couleurs seules changées) → les poids de rig existants restent applicables.

## 3. Porte : rendus REGARDÉS et décrits (une phrase chacun)
- `A_gate_front.png` : **vieil homme chibi de face avec fez rouge à bandeau or, lunettes rondes, grosse barbe grise, manteau rouge à bordure or sur tunique grise** — visage et coiffe immédiatement reconnaissables.
- `A_gate_threequarter.png` : **même personnage à 3/4, lunettes/barbe/fez visibles, chaîne or sur la poitrine, épaulières claires** — identité conservée sous angle.
- `A_gate_profile.png` : **profil avec nez, masse de barbe, fez vu de côté, manteau rouge, bout de botte vers l'avant** — silhouette lisible.
- `A_gate_back.png` : dos du manteau rouge, retombée de cheveux gris.

## 4. Checklist vs hero (point par point, sans "partiel ✅" gratuit)
| Élément | Verdict | Preuve |
|---|---|---|
| Chachia/fez rouge + bandeau or | ✅ | gate_front : calotte rouge + bandeau or |
| Gland noir | ❌ absent | ni les vues sources ni le mesh ne le montrent → à sculpter |
| Cheveux gris | ✅ | mèches grises latérales + dos |
| Visage/lunettes/barbe grise | ✅ | lunettes rondes, yeux, barbe fournie |
| Casque audio | ❌ absent | à modéliser (tore + coussinets) |
| Cape/manteau rouge bordure or | ✅ | manteau rouge + passepoil or |
| Pendentif G doré | ⚠️ chaîne or visible, lettre G illisible | à ajouter (disque + lettre) |
| Bras/jambes robot blanc | ⚠️ mains claires, manches rouges, bottes or/noir (style chibi des vues, pas robot blanc du hero) | divergence assumée, à trancher avec AZMI |
| Baskets rouge/blanc | ⚠️ bottes chunky or/noir, pas sneakers | idem |
| Texture métallique parasite | ✅ éliminée | fini le bruit gris/rouge |

## 5. Itération anti-coutures ÉCHOUÉE (diagnostic honnête, règle stop-si-cassé)
- `A_v2blend_BROKEN_front.png` : **statue au bruit irisé chrome, visage illisible** — le blend softmax top-2 (facing^4, 10 546 sans-vue, NaN au cast) a tout cassé.
- Fichier `v2_fallback_baked_v2.glb` **supprimé**. Version verrouillée = v1 winner-takes-all (coutures verticales légères restantes sur le manteau, acceptées).

## 6. Décision porte A
**PASS CONDITIONNEL** : personnage humanoïde sain, visage/coiffe/manteau fidèles aux 5 vues, texture parasite éliminée, rig existant réutilisable.
Réserves explicites : gland, casque, lettre G manquants (ajouts géométrie prévus) ; style chibi des vues vs hero réaliste (arbitrage AZMI).
Filière InstantMesh : abandonnée avec preuve. Aucun bump version.
