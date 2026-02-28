import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { visualizer } from "rollup-plugin-visualizer";

const analyze = process.env.ANALYZE === "true";

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    react(),
    // Only generate the bundle stats file when ANALYZE=true (via `npm run build:analyze`)
    ...(analyze
      ? [
          visualizer({
            open: false,
            filename: "dist/stats.html",
            gzipSize: true,
          }),
        ]
      : []),
  ],

  server: {
    port: 3000,
    proxy: {
      // Forward all /api requests to FastAPI during development
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },

  build: {
    outDir: "dist",
    sourcemap: true,
  },

  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./tests/setup.ts"],
    coverage: {
      provider: "v8",
      reporter: ["text", "html"],
    },
  },
});
