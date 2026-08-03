import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": new URL("./src", import.meta.url).pathname,
    },
  },
  build: {
    outDir: "dist",
    // The recorded bundles are imported as JSON and inlined. They are the
    // point of the playground, so they ship in the bundle rather than being
    // fetched — a demo that can fail to load its evidence is worse than one
    // that is simply large.
    assetsInlineLimit: 0,
  },
});
