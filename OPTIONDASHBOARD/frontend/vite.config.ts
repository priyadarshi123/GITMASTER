import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// Dev: `npm run dev` (port 5173) proxies /api to the Python backend on 8050.
// Prod: `npm run build` -> dist/, served by FastAPI itself.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { proxy: { "/api": "http://127.0.0.1:8050" } },
  build: { chunkSizeWarningLimit: 800 },   // single-user app; charts library is most of it
});
