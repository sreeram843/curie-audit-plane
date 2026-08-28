import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig({
  plugins: [react()],
  envDir: "..",
  resolve: {
    alias: {
      "@contracts": path.resolve(__dirname, "../contracts"),
    },
  },
  server: {
    port: 5173,
    proxy: {
      "/transactions": "http://127.0.0.1:8080",
      "/content": "http://127.0.0.1:8080",
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
  },
});
