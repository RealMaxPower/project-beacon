import { ThemeToggle, useTheme } from "@/components/shell/ThemeToggle";
import { facts } from "@/data/fixtures";
import type { BResolved } from "../router-b";

/**
 * Header and footer.
 *
 * The mark is the same three-arc figure the first design uses, drawn from the
 * same path data — one brand, two dressings. It is inlined rather than
 * imported because it is coloured from this design's tokens, and the shared
 * component takes `currentColor` from a palette that does not exist here.
 */

const REPO = "https://github.com/RealMaxPower/project-beacon";

/*
 * Section anchors and one route, in one list.
 *
 * Anchors are written `/#case` rather than `#case` so they work from every
 * screen. A bare fragment on `/docs` sets the fragment of `/docs`, which has
 * no such section and no way to reach one; with the path in front, the browser
 * loads the marketing page and scrolls to the section, which is what the label
 * promises. It costs a document load from the other screens and nothing at all
 * from the page they point into.
 */
const NAV = [
  ["The case", "/#case"],
  ["How it grades", "/#how"],
  ["Your stack", "/#stack"],
  ["What exists", "/#status"],
  ["Quickstart", "/#quickstart"],
  ["Playground", "/playground"],
  ["Docs", "/docs"],
] as const;

function Mark() {
  return (
    <svg width="19" height="19" viewBox="0 0 24 24" aria-hidden="true" className="flex-none">
      <g fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
        <path d="M4 13.5A6.5 6.5 0 0 1 10.5 20" />
        <path d="M4 8.5A11.5 11.5 0 0 1 15.5 20" />
        <path d="M4 3.5A16.5 16.5 0 0 1 20.5 20" />
      </g>
      <circle cx="4" cy="20" r="2.2" fill="currentColor" />
    </svg>
  );
}

export function Header({ route }: { route: BResolved }) {
  /*
   * The first design's hook, unchanged. It writes `data-theme` to the root
   * element and knows nothing about either palette — which is the whole of
   * what a theme switch is here, because every colour is a custom property.
   * Its toggle is reusable for the same reason the playground was: every class
   * on it is a token name this design already declares.
   *
   * What the attribute means differs between the designs, and that is fine.
   * On the first it swaps a light palette for a dark one; here it swaps which
   * of two validated palettes is the page and which is the alternating band.
   */
  const [theme, toggleTheme] = useTheme();

  /*
   * `aria-current` on the route only. The section anchors are destinations on
   * the page rather than pages, and marking one current would be a claim about
   * where the reader is that this header cannot check — it does not know what
   * is in the viewport.
   */
  const current = (href: string) =>
    !href.includes("#") && href.slice(1) === route ? "page" : undefined;

  return (
    <header className="sticky top-0 z-50 border-b border-b-line bg-b-bg/90 backdrop-blur">
      {/*
        The nav takes its own row below `lg`, exactly as the first design's
        does, and for a reason found by measuring rather than by looking: a
        scrolling nav inline beside a button overflows *underneath* it. The
        mask hides that from a reader, but the links are still there, and a
        fade is not a boundary — `npm run visual` reported the collision at
        every width under 1024px.
      */}
      <div className="b-measure py-3">
        <div className="flex items-center gap-4">
          <a
            href="/"
            className="hit-target flex flex-none items-center gap-2.5 pr-2 text-b-text"
          >
            <Mark />
            <span className="font-b-display text-[15.5px] font-semibold tracking-[-0.02em]">
              Project Beacon
            </span>
          </a>

          <nav aria-label="Main" className="hidden min-w-0 flex-1 items-center gap-1 lg:flex">
            {NAV.map(([label, href]) => (
              <a
                key={href}
                href={href}
                aria-current={current(href)}
                className={`hit-target inline-flex flex-none items-center rounded-md px-2.5 text-[13.5px] hover:text-b-text ${
                  current(href) ? "text-b-src" : "text-b-muted"
                }`}
              >
                {label}
              </a>
            ))}
          </nav>

          <div className="ml-auto flex flex-none items-center gap-2">
            <ThemeToggle theme={theme} onToggle={toggleTheme} />
            <a
              href={REPO}
              rel="noreferrer"
              className="hit-target inline-flex flex-none items-center rounded-md bg-b-text px-3.5 text-[13px] font-medium text-b-bg"
            >
              Source
            </a>
          </div>
        </div>

        {/* Declared and painted: the cue the audit requires, on the row that
            actually scrolls. */}
        <nav
          aria-label="Sections"
          data-scroll-cue
          className="flex items-center gap-1 overflow-x-auto [mask-image:linear-gradient(to_right,black_calc(100%-2rem),transparent)] lg:hidden"
        >
          {NAV.map(([label, href]) => (
            <a
              key={href}
              href={href}
              aria-current={current(href)}
              className={`hit-target inline-flex flex-none items-center rounded-md px-2.5 text-[13.5px] ${
                current(href) ? "text-b-src" : "text-b-muted"
              }`}
            >
              {label}
            </a>
          ))}
        </nav>
      </div>
    </header>
  );
}

export function Footer() {
  return (
    <footer className="border-t border-b-line" data-ground="alt">
      <div className="b-measure py-12">
        <div className="flex items-center gap-2.5 text-b-text">
          <Mark />
          <span className="font-b-display text-[15.5px] font-semibold tracking-[-0.02em]">
            Project Beacon
          </span>
        </div>

        <p className="b-lede mt-6 max-w-[68ch] text-[14px]">
          Beacon grades observable outcomes and state changes. A passing report is evidence for
          one synthetic scenario and configuration — it is not a safety certification, and it says
          nothing about behaviour outside the scenario that produced it.
        </p>

        <p className="mt-5 font-b-mono text-[11.5px] text-b-faint">
          © 2026 Marshall Cahill and Project Beacon contributors · Apache 2.0 · every scenario fixture is
          synthetic · {facts.scenarios} scenarios
        </p>

        {/*
         * The licensing and privacy page belongs to the origin rather than to
         * either design — same policy, same fonts, same bundled packages — so
         * this links the one that exists instead of restating it in this
         * design's voice. A second copy would be a second place for a claim
         * about what the site collects to be wrong, and that is the one claim
         * here that must not be.
         */}
        <p className="mt-1.5 font-b-mono text-[11.5px] text-b-faint">
          <a href="/legal" className="hover:text-b-text">
            Licensing and privacy
          </a>{" "}
          ·{" "}
          <a href={REPO} rel="noreferrer" className="hover:text-b-text">
            github.com/RealMaxPower/project-beacon
          </a>
        </p>
      </div>
    </footer>
  );
}
