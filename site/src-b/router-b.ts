import { useEffect, useState } from "react";
import { scenarios } from "@/data/fixtures";

/**
 * The router, and why routes are paths rather than fragments.
 *
 * This design is one long marketing page whose sections are reached by
 * `#case`, `#how`, `#stack` — real in-page anchors the browser scrolls to —
 * plus a handful of screens that replace the page entirely. Both kinds of
 * destination live in the same header, and telling them apart is the whole job
 * of this file. Reading a section anchor as a route does not throw: it renders
 * a different page than the one the visitor is looking at the URL of.
 *
 * The split used to be the leading slash inside the fragment — `#case` an
 * anchor, `#/docs` a route. It worked, and it cost the site its index. A
 * fragment is never sent to a server, so `#/docs` is not a URL: it is the same
 * URL as `/` with a note for the client. Search engines index the URL, so three
 * of the four screens here did not exist to one, and the pages were left
 * competing for a single entry with whatever the landing page happened to say.
 *
 * So the rule is now:
 *
 *   /              the marketing page
 *   /docs          a route — a real URL, prerendered, indexable on its own
 *   /playground    also a route
 *   #case          an anchor — the browser handles it, this router says HOME
 *
 * Anchors keep working from any screen: `/#case` is a path of `/` and a
 * fragment of `case`, so the marketing page renders and the effect below
 * scrolls to the section once it exists.
 *
 * An unrecognised path resolves to NOT_FOUND rather than falling back to the
 * marketing page. Rendering home under `/playgound` tells a visitor they are
 * somewhere they are not, hides the typo that got them there, and — now that
 * these are real URLs — invites a crawler to index the same page under every
 * misspelling anyone ever links.
 */

export const B_ROUTES = ["", "playground", "docs", "legal"] as const;

export type BRoute = (typeof B_ROUTES)[number];

/** A path that names no route. Rendered as such, and served as a 404. */
export const B_NOT_FOUND = " not-found" as const;

export type BResolved = BRoute | typeof B_NOT_FOUND;

export interface BLocation {
  route: BResolved;
  /** The second segment, for `/playground/<scenario id>`. */
  param: string | null;
}

/** Only the playground takes a second segment. */
const PARAMETERISED: ReadonlySet<BRoute> = new Set<BRoute>(["playground"]);

/**
 * The scenario ids `/playground/<id>` accepts, and nothing else.
 *
 * A route used to be valid whatever its parameter, which was harmless while
 * these were fragments: the playground opened on its picker and no server had
 * an opinion. As real URLs it is not harmless in either direction. Every
 * misspelling becomes a distinct address answering 200 with the same page,
 * which is what a crawler indexes; and the server, having no document for it,
 * answers with the not-found page while the client renders the playground over
 * the top — a hydration mismatch that throws away the whole prerendered tree.
 *
 * So the parameter is part of what makes the route real, and the two ends
 * agree about which URLs exist.
 */
const SCENARIO_IDS: ReadonlySet<string> = new Set(scenarios.map((s) => s.id));

/** The path a route is served at. The inverse of `readLocation`. */
export function pathFor(route: BRoute, param?: string | null): string {
  const tail = param ? `/${encodeURIComponent(param)}` : "";
  return route ? `/${route}${tail}` : "/";
}

export function readLocation(pathname: string): BLocation {
  const path = pathname.replace(/^\/+/, "").replace(/\/+$/, "");
  if (path === "") return { route: "", param: null };

  const [head, ...rest] = path.split("/");
  const match = B_ROUTES.find((r) => r === head);
  if (match === undefined || rest.length > 1) return { route: B_NOT_FOUND, param: null };

  const param = rest.length === 1 ? decodeURIComponent(rest[0]) : null;
  if (param !== null && !PARAMETERISED.has(match)) return { route: B_NOT_FOUND, param: null };
  if (param !== null && !SCENARIO_IDS.has(param)) return { route: B_NOT_FOUND, param: null };

  return { route: match, param };
}

/**
 * Where this document is, and nothing else.
 *
 * There is no `go`, no `pushState` and no `popstate` listener, because nothing
 * in this design navigates from script: every destination is an `<a href>`, so
 * every navigation is a document load and every document is prerendered. The
 * client-side router that used to live here existed to make a fragment change
 * swap a screen, and with real URLs the browser does that itself, better —
 * back and forward included, at no cost in code.
 *
 * A crawler follows those anchors and gets a complete page each time, which is
 * the same property, arrived at from the other side.
 */
export function useBRoute(): [BLocation] {
  const [location] = useState<BLocation>(() =>
    typeof window === "undefined"
      ? readLocation(prerenderPath())
      : readLocation(window.location.pathname),
  );

  /*
   * Scroll to the anchor once the page that contains it exists.
   *
   * The browser scrolls on load by looking for the element *at that moment*,
   * and arriving from another screen there is no such element: the marketing
   * page has not rendered yet. So following `/#case` from the playground put
   * the fragment in the address bar, rendered the right page, and left the
   * reader at the top of it — a link that reports success and does nothing,
   * which is the shape a visitor reads as broken.
   *
   * This effect runs after the commit that renders the section, so the element
   * is there to find. It is deliberately not conditional on where the reader
   * came from: re-scrolling to a section already in view costs nothing and is
   * what the browser would have done anyway.
   *
   * No `behavior: "smooth"` — a reader who asked for reduced motion is asking
   * about this too, and the CSS block that would otherwise stop it cannot
   * reach a scroll issued from script.
   */
  useEffect(() => {
    if (location.route !== "") return;
    const hash = window.location.hash;
    if (!hash) return;
    document.getElementById(decodeURIComponent(hash.slice(1)))?.scrollIntoView();
  }, [location]);

  /*
   * Carry a link written against the old fragment routes over to its path.
   *
   * `#/docs` is not sent to a server, so nothing on the host can redirect it —
   * it arrives as a request for `/` with a note only the client can read. A
   * visitor following a link shared while the routes were fragments would land
   * on the marketing page, which is the wrong screen and looks like the link
   * rotted. `replace` rather than `assign` so the dead URL does not sit in the
   * history and send them straight back on the first press of Back.
   */
  useEffect(() => {
    const hash = window.location.hash;
    if (!hash.startsWith("#/")) return;
    const moved = readLocation(hash.slice(1));
    if (moved.route === B_NOT_FOUND) return;
    window.location.replace(pathFor(moved.route, moved.param));
  }, []);

  return [location];
}

/**
 * The path being prerendered, read from a global the prerender step sets.
 *
 * There is no `window.location` in the SSR pass, and every route has to render
 * its own screen or the whole exercise produces four copies of the landing
 * page. `globalThis` rather than an argument because `SiteB` is rendered by
 * three different tools — the prerender step, the smoke check and the render
 * audit — and threading a prop through all of them would let one of them
 * forget, silently, in the direction of "looks fine".
 */
export function prerenderPath(): string {
  return (globalThis as { __BEACON_PRERENDER_PATH__?: string }).__BEACON_PRERENDER_PATH__ ?? "/";
}
