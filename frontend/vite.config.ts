/// <reference types="vitest/config" />
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    // PWA (§11.5): el service worker sale de src/sw.ts y se sirve como /sw.js
    VitePWA({
      strategies: "injectManifest",
      srcDir: "src",
      filename: "sw.ts",
      registerType: "prompt",
      injectRegister: false, // lo registra main.tsx
      manifest: {
        name: "Monitoreo del hogar",
        short_name: "Alarma hogar",
        lang: "es",
        start_url: "/",
        scope: "/",
        display: "standalone",
        theme_color: "#0f172a",
        background_color: "#0f172a",
        icons: [
          {
            src: "/icons/icon-192.png",
            sizes: "192x192",
            type: "image/png",
            purpose: "any maskable",
          },
          {
            src: "/icons/icon-512.png",
            sizes: "512x512",
            type: "image/png",
            purpose: "any maskable",
          },
        ],
      },
      injectManifest: { globPatterns: ["**/*.{js,css,html,png,webmanifest}"] },
    }),
  ],
  server: {
    // La app y la API quedan en el mismo origen (localhost:5173): la cookie de sesión
    // funciona igual que en producción (§11.7).
    proxy: {
      "/api": "http://127.0.0.1:8011",
      "/ws": { target: "ws://127.0.0.1:8011", ws: true },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
  },
});
