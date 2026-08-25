import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev-mode proxy: the dashboard runs on :5173 with HMR while /api (including
// the SSE stream), the demo site and tracker.js are served by FastAPI on :8000.
// Vite's proxy streams SSE unmodified (no buffering, no compression).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: "http://localhost:8000", changeOrigin: true },
      "/demo": { target: "http://localhost:8000", changeOrigin: true },
      "/tracker.js": { target: "http://localhost:8000", changeOrigin: true }
    }
  }
});
