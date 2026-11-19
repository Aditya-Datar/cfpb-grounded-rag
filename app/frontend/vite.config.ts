import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev: the React app on :5173 talks to FastAPI on :8000 through this proxy.
// Build: `npm run build` writes dist/, which FastAPI serves itself.
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { "/api": "http://localhost:8000" } },
});
