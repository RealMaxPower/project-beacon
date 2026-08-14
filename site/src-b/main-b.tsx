import { StrictMode } from "react";
import { createRoot, hydrateRoot } from "react-dom/client";
import { Analytics } from "@vercel/analytics/react";
import "./tokens-b.css";
import { SiteB } from "./SiteB";
import { loadAllRuns } from "@/data/fixtures";

/**
 * The second design's entry.
 *
 * Deliberately separate from `src/main.tsx` rather than a route inside it.
 * The two designs have different type scales, different grounds and different
 * chrome; sharing a shell would mean one page rendering inside the other's
 * header, which is both a duplicate-landmark defect and a guarantee that
 * neither design can be judged on its own terms.
 *
 * What they do share is the evidence: both import the recorded bundles from
 * `@/data/fixtures`, so there is one set of runs on disk and no way for the
 * two sites to disagree about what happened in them.
 */

const root = document.getElementById("root");
if (!root) throw new Error("No #root in index.html.");

/*
 * Web Analytics is mounted at the entry rather than inside the design, because
 * it is not part of either design and both documents need it independently.
 *
 * It is the one thing on this site that talks to the network, and it is the
 * reason `connect-src` is `'self'` rather than `'none'`. That directive was a
 * claim on the legal page, so that page changed in the same commit — a privacy
 * statement that describes a policy the site no longer has is exactly the kind
 * of unbacked claim this project exists to catch.
 *
 * What it collects is a page view: no cookie, no identifier, no cross-site
 * anything. The beacon posts to `/_vercel/insights/view` on this origin, which
 * is why `'self'` is enough and no third-party host appears in the policy.
 */
/*
 * Hydrate what the prerender step already wrote, rather than replacing it.
 *
 * Every route is built to a real document with its content in it, so by the
 * time this runs the page has painted and been readable for some time. Calling
 * `createRoot().render()` here would throw that away and rebuild the same tree,
 * which is slower, flashes, and loses the reader's scroll position on a page
 * they may already have scrolled.
 *
 * The fallback is not defensive decoration. `npm run dev` serves this document
 * unprerendered, so the root really is empty there, and `hydrateRoot` on an
 * empty container is an error rather than a no-op.
 */
const page = (
  <StrictMode>
    <SiteB />
    <Analytics />
  </StrictMode>
);

/*
 * The playground's evidence is fetched before hydration, not during it.
 *
 * Only five of the seventeen recorded runs are in the main bundle — the ones
 * the marketing page renders. The playground needs all of them, and it needs
 * them synchronously, because hydration compares what the client renders
 * against what the server already sent. Awaiting here keeps every screen and
 * every test synchronous at the cost of one await on one route.
 */
function start() {
  if (root!.hasChildNodes()) {
    hydrateRoot(root!, page);
  } else {
    createRoot(root!).render(page);
  }
}

if (window.location.pathname.startsWith("/playground")) {
  loadAllRuns().then(start);
} else {
  start();
}
