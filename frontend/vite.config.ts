import { fileURLToPath, URL } from "node:url";
import vue from "@vitejs/plugin-vue";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
      "@schema": fileURLToPath(new URL("../schemas/rules.schema.json", import.meta.url)),
      "@rules": fileURLToPath(new URL("../rules", import.meta.url)),
    },
  },
  server: { fs: { allow: [".."] } },
  test: { environment: "jsdom", include: ["tests/**/*.spec.ts"] },
});
