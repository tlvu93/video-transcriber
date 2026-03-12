import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig, type UserConfig } from "vite";
import type { InlineConfig } from "vitest/node";

const API_PREFIX_PATTERN = /^\/api/;

interface AppViteConfig extends UserConfig {
  test?: InlineConfig;
}

const config: AppViteConfig = {
  plugins: [tailwindcss(), react()],
  server: {
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(API_PREFIX_PATTERN, ""),
        ws: true,
      },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./vitest.setup.ts",
    css: true,
  },
};

export default defineConfig(config);
