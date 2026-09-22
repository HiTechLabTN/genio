# Appliquer le correctif écran noir (v3.0.2)

## Option A — bundle Git (recommandé)

```bash
git fetch /chemin/vers/genio-fix-v3.0.2-black-screen.bundle fix/v3.0.2-black-screen:fix/v3.0.2-black-screen
git checkout fix/v3.0.2-black-screen
git push origin fix/v3.0.2-black-screen
# puis merge vers main (PR ou direct) :
git checkout main
git merge fix/v3.0.2-black-screen
git push origin main
```

## Option B — patch

```bash
git am patches/0001-fix-black-screen-*.patch
```

Un seul commit (`7de1e8b`), basé directement sur `origin/main` (qui inclut déjà
v3.0.0 et le hotfix v3.0.1) — pas de conflit attendu.
