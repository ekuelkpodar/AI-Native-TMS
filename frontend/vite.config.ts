import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// API target: set VITE_API_PROXY_TARGET to point elsewhere in dev,
// or VITE_API_URL for a full base URL used by the client.
const proxyTarget = process.env.VITE_API_PROXY_TARGET || "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: proxyTarget,
        changeOrigin: true,
      },
    },
  },
});
