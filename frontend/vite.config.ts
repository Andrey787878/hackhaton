/// <reference types="vitest/config" />
import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

// В разработке Vite проксирует /api на FastAPI, поэтому браузер работает
// с одним origin и CORS на сервере не нужен. В Docker ту же роль выполняет nginx.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, ".", "");
  const target = env.API_PROXY_TARGET || "http://localhost:8080";
  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: { "/api": { target, changeOrigin: true } },
    },
    preview: {
      port: 4173,
      proxy: { "/api": { target, changeOrigin: true } },
    },
    test: {
      environment: "node",
      include: ["src/**/*.test.ts"],
    },
  };
});
