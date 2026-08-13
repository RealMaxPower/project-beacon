import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
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

createRoot(root).render(
  <StrictMode>
    <SiteB />
  </StrictMode>,
);
