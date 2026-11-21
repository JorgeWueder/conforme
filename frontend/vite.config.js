import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "localhost",
    port: 8501,
    strictPort: true,
    proxy: { "/api": process.env.CONFORME_API_DEV || "http://127.0.0.1:8000" },
  },
});
