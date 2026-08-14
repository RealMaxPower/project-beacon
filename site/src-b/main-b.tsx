import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { Analytics } from "@vercel/analytics/react";
import "./tokens-b.css";
import { SiteB } from "./SiteB";

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
createRoot(root).render(
  <StrictMode>
    <SiteB />
    <Analytics />
  </StrictMode>,
);
