# Branding Genio

Toutes les icônes et bannières de ce projet dérivent des mêmes visuels
sources (mascotte 3D "Genio", fez rouge, style Pixar) par recadrage et
redimensionnement uniquement — jamais de régénération — pour garantir une
identité visuelle cohérente sur toutes les plateformes.

## Source de vérité

- `genio_client/resources/icon.png` — icône carrée maître (1024×1024),
  utilisée par `@capacitor/assets` pour générer Android + iOS.
- `genio_client/resources/icon-foreground.png` /
  `genio_client/resources/icon-background.png` — calques de l'icône
  adaptive Android (API 26+).
- `genio_client/public/icon.ico` / `genio_client/public/icon.png` — icônes
  Electron (Windows/Linux), référencées directement dans le champ `build`
  de `genio_client/package.json`.
- `genio_client/public/favicon.ico` + `genio_client/public/icons/*.png` —
  favicon et icônes PWA (`manifest.webmanifest`).
- `docs/hero-banner.png` — bannière utilisée en tête de README.
- `docs/logo-lockup.png` — logo horizontal (cercle "G" + wordmark "Genio").
- `docs/github-social-preview.png` — aperçu de lien GitHub (768×384).

## Régénérer les icônes natives (Android/iOS)

Le dossier `genio_client/android/` (et `ios/` le cas échéant) est régénéré
à chaque run CI via Capacitor — il n'est jamais commité (voir `.gitignore`).
Pour régénérer localement après avoir changé `resources/icon*.png` :

```bash
cd genio_client
npx cap add android      # si le dossier android/ n'existe pas encore
npm run assets:generate  # capacitor-assets generate — lit resources/
npx cap sync android
```

## Action manuelle ponctuelle (GitHub)

Le "Social preview" (aperçu affiché quand un lien vers ce repo est partagé)
n'est pas versionnable — GitHub le stocke hors du repo. À faire une seule
fois (ou à chaque changement de bannière) :

1. Aller sur https://github.com/HiTechLabTN/genio/settings
2. Section **Social preview** → Edit → uploader
   `docs/github-social-preview.png`.

## Limite de résolution connue

L'icône source (`resources/icon.png`) est dérivée d'un recadrage natif de
430×430px depuis l'illustration originale. Les exports à 1024px (App Store
iOS, Electron) sont donc un agrandissement ~×2.3 : net aux tailles
d'affichage réelles (icône d'app, dock, launcher), plus doux si on zoome à
100% dans un inspecteur d'assets. Pour une netteté parfaite à 1024px, il
faudrait repartir d'un rendu source en plus haute résolution.
