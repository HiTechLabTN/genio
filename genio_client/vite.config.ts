import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

// @ts-expect-error process is a nodejs global
const host = process.env.TAURI_DEV_HOST;

// https://vite.dev/config/
export default defineConfig(async () => ({
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["favicon.ico", "icons/*.png", "fonts/*.woff2"],
      manifest: false,
      workbox: {
        maximumFileSizeToCacheInBytes: 10 * 1024 * 1024,
        globPatterns: ["**/*.{js,css,html,ico,png,svg,webp,woff2}"],
        // Le chunk three.js (~1MB) ne se précache PAS : il ne se télécharge
        // qu'à la demande en mode mascotte (MascotStage lazy). Idem rapier.
        globIgnores: ["**/three-*.js", "**/rapier-*.js"],
        navigateFallbackDenylist: [/^\/chat\.html/, /^\/console\.html/, /^\/sw\.js/, /^\/workbox/],
        runtimeCaching: [
          {
            urlPattern: /^https:\/\/fonts\.googleapis\.com\/.*/i,
            handler: "CacheFirst",
            options: { cacheName: "google-fonts-cache", expiration: { maxEntries: 10, maxAgeSeconds: 60 * 60 * 24 * 365 } },
          },
          {
            urlPattern: /^https:\/\/fonts\.gstatic\.com\/.*/i,
            handler: "CacheFirst",
            options: { cacheName: "gstatic-fonts-cache", expiration: { maxEntries: 10, maxAgeSeconds: 60 * 60 * 24 * 365 } },
          },
        ],
      },
    }),
  ],
  build: {
    target: "es2020",
    cssCodeSplit: true,
    sourcemap: false,
    chunkSizeWarningLimit: 600,
    // Pas de préchargement des chunks 3D lourds au boot : three/rapier ne se
    // téléchargent qu'à la demande (mode mascotte lazy). Critique mobile.
    modulePreload: {
      resolveDependencies: (filename, deps) =>
        deps.filter((d) => !/three-|rapier-/.test(d)),
    },
    rollupOptions: {
      output: {
        // Ne remonte JAMAIS les deps transitives des chunks lazy en imports
        // statiques : le graphe three/GLB de MascotStage reste strictement
        // à la demande (sinon chaque route retélécharge 3.3MB au boot).
        hoistTransitiveImports: false,
        manualChunks(id) {
          if (id.includes("node_modules")) {
            // PAS de chunk three partagé : three/fiber/drei n'ont qu'un seul
            // consommateur (MascotStage lazy) — partagé, chaque route le
            // retéléchargerait au boot via le helper preload. Inliné dans le
            // chunk async, il ne part qu'en mode mascotte.
            if (id.includes("@dimforge/rapier")) return "rapier";
            if (id.includes("framer-motion")) return "motion";
            if (id.includes("react-dom") || id === "react" || id.includes("/react/")) return "react";
            if (id.includes("lucide-react")) return "vendor";
          }
        },
      },
    },
  },

  // Production preview (genio-web.service :8098 ← cloudflared genio.hitech.tn) :
  // autorise l'host public + LAN à travers le tunnel (sinon 403 Vite).
  preview: {
    port: 8098,
    strictPort: true,
    host: "0.0.0.0",
    allowedHosts: ["genio.hitech.tn", "localhost", "127.0.0.1"],
  },
  // Vite options tailored for Tauri development and only applied in `tauri dev` or `tauri build`
  //
  // 1. prevent Vite from obscuring rust errors
  clearScreen: false,
  // 2. tauri expects a fixed port, fail if that port is not available
  server: {
    port: 1420,
    strictPort: true,
    host: host || false,
    hmr: host
      ? {
          protocol: "ws",
          host,
          port: 1421,
        }
      : undefined,
    watch: {
      // 3. tell Vite to ignore watching `src-tauri`
      ignored: ["**/src-tauri/**"],
    },
  },
}));
