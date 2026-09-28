/// <reference types="vitest/config" />
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
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
