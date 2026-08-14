import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { Analytics } from "@vercel/analytics/react";
import "./fonts.css";
import "./tokens.css";
import { App } from "./App";

const root = document.getElementById("root");
if (!root) throw new Error("No #root element to mount into.");

// See `src-b/main-b.tsx` for why this is here and what it changed on the
// legal page. Both documents mount it, so page views are attributed while
// this design is still reachable at `/a`.
createRoot(root).render(
  <StrictMode>
    <App />
    <Analytics />
  </StrictMode>,
);
