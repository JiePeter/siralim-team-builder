/// <reference types="vitest/config" />
import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  // GitHub Pages serves a project site under /<repository>/.
  base: process.env.BASE_PATH || "/",
  plugins: [vue()],
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  server: {
    host: "127.0.0.1",
    port: Number(process.env.DEV_PORT || 5181),
    strictPort: true,
  },
  preview: {
    host: "127.0.0.1",
    port: Number(process.env.PREVIEW_PORT || 4181),
    strictPort: true,
  },
  test: {
    include: ["tests/unit/**/*.test.ts"],
    setupFiles: ["tests/unit/setup.ts"],
    environment: "jsdom",
  },
});
