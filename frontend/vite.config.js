import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { resolve } from "path";

// Two-page app -- Box Monitor and User Registrations -- built as plain
// static files (no SSR, no framework server) so deployment stays the same:
// `npm run build` then serve dist/ exactly like the old static HTML was
// served (python http.server, the existing Tailscale setup, etc).
export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      input: {
        main: resolve(__dirname, "index.html"),
        register: resolve(__dirname, "register.html"),
      },
    },
  },
});
