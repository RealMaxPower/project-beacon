import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": new URL("./src", import.meta.url).pathname,
      "@b": new URL("./src-b", import.meta.url).pathname,
    },
  },
  build: {
    outDir: "dist",
    rollupOptions: {
      /*
       * Two designs, two documents.
       *
       * Vite builds the root `index.html` alone unless told otherwise, so
       * without this the second entry simply never compiles. They share the
       * recorded bundles by import rather than by a copy step — there is one
       * set of evidence on disk and both sites read it, which is the only
       * arrangement where the two cannot disagree about a run.
       */
      input: {
        main: new URL("./index.html", import.meta.url).pathname,
        b: new URL("./b.html", import.meta.url).pathname,
      },
    },
    // The recorded bundles are imported as JSON and inlined. They are the
    // point of the playground, so they ship in the bundle rather than being
    // fetched — a demo that can fail to load its evidence is worse than one
    // that is simply large.
    assetsInlineLimit: 0,
  },
});
