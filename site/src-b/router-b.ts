import { useEffect, useState } from "react";

/**
 * This design's router, and why it is not the first design's.
 *
 * Site A is seven pages and every hash is a route, so `src/router.ts` can treat
 * the whole fragment as one. This design is one long marketing page whose
 * sections are reached by `#case`, `#how`, `#stack` — real in-page anchors that
 * the browser scrolls to and that must keep working. Pointing A's router at
 * this document would resolve every one of those to NOT_FOUND and render an
 * error page when a visitor clicked "The case" in the header.
 *
 * So the rule here is the leading slash, and it is the whole design:
 *
 *   #case          an anchor — the browser handles it, this router says HOME
 *   #/playground   a route — React swaps the view
 *   #/docs         also a route
 *   #/             HOME, explicitly
 *
 * That split is not a convention borrowed from anywhere; it is forced by the
 * document having both kinds of destination, and it is worth stating because
 * the failure it prevents is silent. An anchor misread as a route does not
 * throw — it renders a different page than the one the visitor is looking at
 * the URL of.
 *
 * An unrecognised route resolves to NOT_FOUND rather than falling back to the
 * marketing page, for the reason A's router gives at length: rendering home
 * under `#/playgound` tells a visitor they are somewhere they are not, and
 * hides the typo that got them there.
 */

export const B_ROUTES = ["", "playground", "docs", "legal"] as const;

export type BRoute = (typeof B_ROUTES)[number];

/** A `#/…` fragment that names no route. Rendered as such. */
export const B_NOT_FOUND = " not-found" as const;

export type BResolved = BRoute | typeof B_NOT_FOUND;

export interface BLocation {
  route: BResolved;
  /** The second segment, for `#/playground/<scenario id>`. */
  param: string | null;
}

/** Only the playground takes a second segment. */
const PARAMETERISED: ReadonlySet<BRoute> = new Set<BRoute>(["playground"]);

export function readLocation(hash: string): BLocation {
  /*
   * No leading slash means an in-page anchor, which is this document's own
   * business and not a route at all. `#top`, `#case`, and the bare `#` a
   * browser leaves behind all land here.
   */
  if (!hash.startsWith("#/")) return { route: "", param: null };

  const path = hash.slice(2).replace(/\/+$/, "");
  if (path === "") return { route: "", param: null };

  const [head, ...rest] = path.split("/");
  const match = B_ROUTES.find((r) => r === head);
  if (match === undefined || rest.length > 1) return { route: B_NOT_FOUND, param: null };

  const param = rest.length === 1 ? decodeURIComponent(rest[0]) : null;
  if (param !== null && !PARAMETERISED.has(match)) return { route: B_NOT_FOUND, param: null };

  return { route: match, param };
}

export type BGo = (next: BRoute, param?: string) => void;

export function useBRoute(): [BLocation, BGo] {
  const [location, setLocation] = useState<BLocation>(() =>
    typeof window === "undefined" ? { route: "", param: null } : readLocation(window.location.hash),
  );

  useEffect(() => {
    const onChange = () => setLocation(readLocation(window.location.hash));
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);

  /*
   * Scroll to the anchor once the page that contains it exists.
   *
   * The browser scrolls on a hash change by looking for the element *at that
   * moment*, and coming from the playground there is no such element: the
   * marketing page has not rendered yet. So clicking "The case" from the
   * playground put `#case` in the address bar, rendered the right page, and
   * left the reader at the top of it — a link that reports success and does
   * nothing, which is the shape a visitor reads as broken.
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
    if (!hash || hash.startsWith("#/")) return;
    document.getElementById(decodeURIComponent(hash.slice(1)))?.scrollIntoView();
  }, [location]);

  return [
    location,
    (next: BRoute, param?: string) => {
      const tail = param ? `/${encodeURIComponent(param)}` : "";
      window.location.hash = next ? `/${next}${tail}` : "/";
      // Landing mid-page after following a nav link reads as a broken link.
      window.scrollTo({ top: 0 });
    },
  ];
}
