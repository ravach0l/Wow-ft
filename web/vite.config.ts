import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Im Entwicklungsmodus leitet Vite API und Login an den lokalen Server weiter.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8000",
      "/auth": "http://127.0.0.1:8000",
    },
  },
});
