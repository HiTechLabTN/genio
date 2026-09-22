Contexte : le hotfix v3.0.1 n'a pas résolu l'écran noir. J'ai testé Genio moi-même
en conditions réelles (build + client connecté à un vrai genio_server local via
WebSocket, jusqu'au portail 3D) et reproduit le crash de façon empirique, puis
identifié et corrigé la vraie cause racine. Le correctif est prêt sur la branche
`fix/v3.0.2-black-screen`, livré en bundle Git avec tout l'historique.

## Ce qui causait l'écran noir

`genio_client/src/components/avatar/CyberAvatar.tsx` chargeait
`<Environment preset="city" />` (react-three/drei), qui va chercher un fichier
`.hdr` sur `raw.githack.com` au runtime. Quand ce fetch échoue (offline au premier
lancement, réseau restrictif, CORS selon le scheme de l'app packagée, CDN en panne),
le rejet de promesse survient hors du cycle de rendu React — un `<Suspense>`
n'attrape que l'attente, pas un échec définitif, et il n'y avait aucun
`ErrorBoundary` autour de ce Canvas. Le hotfix 3.0.1 ajoutait des ErrorBoundary
ailleurs (AndalusianBackground, MatrixTaskBoard, etc.) mais jamais autour de
`CyberAvatar`/`Dashboard`, donc il ne pouvait structurellement pas régler le
problème. Preuve empirique : après le crash, `document.getElementById('root')`
était complètement vide — pas un composant cassé, toute l'app démontée.

## Ce que fait le commit `7de1e8b`

1. Suppression de la dépendance `Environment`/HDR externe dans `CyberAvatar.tsx` —
   l'éclairage manuel déjà présent (ambient + directional + 2 point lights + spot)
   suffit visuellement, plus aucune dépendance réseau pour ce rendu.
2. Les deux usages de `<CyberAvatar>` dans `Dashboard.tsx` enveloppés dans
   `ErrorBoundary` (défense locale).
3. Nouveau `RootErrorBoundary` (`src/components/RootErrorBoundary.tsx`) autour de
   toute l'app dans `main.tsx` — dernier filet : une erreur qui échappe à tout le
   reste affiche un écran réel avec bouton "Recharger" au lieu d'un silence total.

## Vérification déjà faite

- `npm run build` passe (tsc strict inclus).
- Client servi en local + connecté à un vrai `genio_server` (uvicorn, WebSocket
  réel) — même scénario exact qui reproduisait le crash avant le correctif :
  root reste monté, le portail Chronos s'affiche avec les vraies métriques
  connectées, plus aucune erreur JS fatale ni "WebGLRenderer: Context Lost".

## Ce qui reste à faire (je ne peux pas le vérifier moi-même)

1. **Récupérer et pousser** la branche `fix/v3.0.2-black-screen` (voir
   INSTRUCTIONS_APPLIQUER.md joint — bundle Git ou patch `.patch`).
2. **Tester sur les vraies plateformes** que je ne peux pas simuler ici :
   build Tauri desktop (Windows/Linux/macOS) et build Capacitor Android/iOS —
   mon test a validé le rendu web (Chromium headless + vrai backend), pas les
   WebViews natives elles-mêmes. C'est là que le bug se manifestait pour toi,
   donc c'est la vérification la plus importante avant de taguer une release.
3. Si l'écran noir persiste malgré ce correctif sur une plateforme précise,
   collecter les logs de la WebView native (`adb logcat` pour Android,
   console DevTools distante pour Tauri via `--inspect` ou WebView2 DevTools) —
   ça indiquerait un deuxième problème indépendant, pas une régression de ce fix.
4. Bump version → 3.0.2 dans `package.json` / `tauri.conf.json` et tag une
   nouvelle release une fois testé.
5. Item encore en attente depuis les rounds précédents : police "Orbitron"
   toujours chargée depuis `fonts.gstatic.com` (échoue silencieusement hors
   ligne — cosmétique, pas fatal, mais même famille de problème : à
   self-hoster si l'app doit marcher offline).
