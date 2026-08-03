import { useEffect, useState } from "react";

/**
 * A hash router in twenty lines, rather than a dependency.
 *
 * This site is six pages and a playground, served as static files with no
 * server behind them. Hash routes work from any host without rewrite rules,
 * survive a hard refresh, and cost nothing — the whole project has no runtime
 * dependencies, and the website is a poor place to start acquiring them.
 */

export const routes = [
  { path: "", label: "Home" },
  { path: "how-it-works", label: "How it works" },
  { path: "scenarios", label: "Scenarios" },
  { path: "for-builders", label: "For agent builders" },
  { path: "playground", label: "Playground" },
  { path: "docs", label: "Docs" },
  { path: "hosted", label: "Hosted lab" },
] as const;

export type Route = (typeof routes)[number]["path"];

/**
 * The routes that accept a second segment, and what it names.
 *
 * Only the playground takes one — `#/playground/<scenario id>` — so a scenario
 * card anywhere on the site can open the playground already pointed at itself.
 * Every other page is bare, and a trailing segment on one is a typo rather than
 * an argument.
 */
const PARAMETERISED: ReadonlySet<Route> = new Set<Route>(["playground"]);

/** A hash that matches no route. Rendered as such, rather than silently as Home. */
export const NOT_FOUND = " not-found" as const;

export type Resolved = Route | typeof NOT_FOUND;

export interface Location {
  route: Resolved;
  /** The second path segment, for the one route that takes one. */
  param: string | null;
}

/**
 * The location for the current hash.
 *
 * An unrecognised hash resolves to NOT_FOUND rather than falling back to Home.
 * Rendering Home under `#/agent-builders`, with Home marked
 * `aria-current="page"` while the address bar says something else, tells the
 * visitor they are somewhere they are not — and hides the typo that got them
 * there. A trailing segment on a page that takes none resolves the same way,
 * for the same reason: `#/docs/limitations` is not the docs page.
 *
 * Whether the param names a real scenario is not decided here — the router has
 * no business reading fixtures. The playground resolves it, and says so on
 * screen when it cannot.
 */
function current(): Location {
  const hash = window.location.hash.replace(/^#\/?/, "").replace(/\/+$/, "");
  if (hash === "") return { route: "", param: null };

  const [head, ...rest] = hash.split("/");
  const match = routes.find((r) => r.path === head);
  if (!match || rest.length > 1) return { route: NOT_FOUND, param: null };

  const param = rest.length === 1 ? decodeURIComponent(rest[0]) : null;
  if (param !== null && !PARAMETERISED.has(match.path)) {
    return { route: NOT_FOUND, param: null };
  }

  return { route: match.path, param };
}

export type Go = (next: Route, param?: string) => void;

export function useRoute(): [Location, Go] {
  const [location, setLocation] = useState<Location>(() =>
    typeof window === "undefined" ? { route: "", param: null } : current(),
  );

  useEffect(() => {
    const onChange = () => setLocation(current());
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);

  return [
    location,
    (next: Route, param?: string) => {
      const tail = param ? `/${encodeURIComponent(param)}` : "";
      window.location.hash = next ? `/${next}${tail}` : "/";
      // Landing mid-page after following a nav link reads as a broken link.
      window.scrollTo({ top: 0 });
    },
  ];
}
