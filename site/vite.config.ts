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
    /*
     * One document again.
     *
     * There were two for a while, so a second design could be reviewed against
     * the first at a real URL rather than in a screenshot. The second won and
     * took the root; the first is gone, and with it the multi-entry `input`
     * this needed. `src/` did not go with it — the playground, the recorded
     * bundles and the shared components all still live there and are imported
     * by `src-b/`, which is why deleting a design deleted fifteen files rather
     * than a directory.
     */
    /*
     * No source maps, and the reason is the host rather than the principle.
     *
     * Lighthouse asks for them on a bundle this size and it is right to: a
     * stack trace from a minified file is unactionable, and the source is
     * public anyway. So they were turned on — and Vercel answers **403** for
     * every `.map` in a production deployment. What shipped was 1.9MB of maps
     * nobody could fetch and a `sourceMappingURL` in every file pointing at a
     * refusal, which is worse than the audit it was meant to satisfy: a
     * devtools that tries and fails is a worse experience than one that never
     * tries.
     *
     * Measured against the live deployment, not assumed. If the host ever
     * serves them, this is one word.
     */
    // The recorded bundles are imported as JSON and inlined. They are the
    // point of the playground, so they ship in the bundle rather than being
    // fetched — a demo that can fail to load its evidence is worse than one
    // that is simply large.
    assetsInlineLimit: 0,
  },
  /*
   * Keep the licence blocks the minifier would otherwise discard.
   *
   * React is MIT, which permits redistribution only with its notice attached,
   * and every visitor receives a compiled copy of it. The default drops
   * `@license` comments, so the built assets carried none — the same omission
   * the fonts had, arrived at through a lockfile instead of a download.
   *
   * `public/THIRD-PARTY-NOTICES.txt` is the authoritative copy and is what the
   * site links to; this keeps the notice in the artifact itself as well, so a
   * bundle that gets copied somewhere without the rest of the origin still
   * carries its own terms.
   */
  esbuild: {
    legalComments: "inline",
  },
});
