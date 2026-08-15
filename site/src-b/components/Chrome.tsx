import { useEffect, useRef, useState } from "react";
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

/** The ids the nav's anchors point at. `/#case` names `case`. */
const NAV_SECTIONS = NAV.flatMap(([, href]) => href.split("#")[1] ?? []);

/**
 * How far below the top of the content the section probe sits.
 *
 * Not zero, because that is exactly where a boundary lands. Following `/#compare`
 * puts the top of that section on the anchor line and the *last pixel* of the
 * section before it on the same line, and which of the two a sub-pixel layout
 * rounds onto the probe is a coin toss — it came up "Your stack" for a reader
 * looking at the comparison table. A few pixels into the content is inside one
 * section however the boundary rounds, and is imperceptible while scrolling.
 */
const PROBE_INSET = 8;

/**
 * Which of the nav's own sections is under the header, or null.
 *
 * The header used to mark the route and nothing else, on the grounds that
 * calling a section current would be a claim about where the reader is that
 * this header could not check. The claim is checkable — that is what an
 * IntersectionObserver is — and leaving it unchecked had a cost of its own:
 * five of the seven links could never light up, including while the address
 * bar read `/#case`, so the cue looked broken rather than principled.
 *
 * What is checked is deliberately narrow: a section is current while it covers
 * one probe line, and when the reader is somewhere the nav does not name —
 * which is ten of this page's fifteen sections — nothing is current. The usual
 * scroll-spy rule instead keeps the last heading you passed lit, which here
 * would report "The case" to somebody halfway through the integrity panel. No
 * highlight is the honest answer to "where am I" when the answer is "nowhere
 * in this list".
 *
 * The line is one pixel rather than a band, and that is load-bearing. A band
 * deep enough to be worth the name always straddles a boundary: sections here
 * are contiguous, so it holds the tail of one and the head of the next, and
 * whichever of the two the rule prefers is wrong half the time. It reported
 * "How it grades" to a reader who had just clicked "Your stack" and was
 * looking at it. One line falls inside exactly one section, and there is
 * nothing left to prefer.
 *
 * Nothing resolves during render, so the prerendered markup and the first
 * client render agree and hydration survives; the highlight arrives on the
 * commit after mount. Without script the nav is exactly what it was.
 */
function useSectionInView(enabled: boolean, header: React.RefObject<HTMLElement | null>) {
  const [id, setId] = useState<string | null>(null);

  useEffect(() => {
    if (!enabled) {
      setId(null);
      return;
    }

    const targets = NAV_SECTIONS.map((s) => document.getElementById(s)).filter((el) => el !== null);
    if (targets.length === 0) return;
    /*
     * Document order, asked of the document rather than assumed of `NAV`. The
     * two agree today; the tie-break below reads this order as "further down
     * the page", and a header reordered for emphasis should not quietly change
     * what that means.
     */
    targets.sort((a, b) =>
      a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1,
    );

    const onLine = new Set<string>();
    let observer: IntersectionObserver | null = null;

    /*
     * Re-observed on resize, because the line moves: the header takes a second
     * row below `lg`, and the viewport the margins are measured against is
     * what a rotation changes.
     */
    const observe = () => {
      observer?.disconnect();
      onLine.clear();
      /*
       * Where the reader's eye starts, which is not the header's bottom edge.
       * Following `/#stack` leaves that section's top at its own
       * `scroll-margin-top` — read from the element rather than repeated here,
       * so the stylesheet stays the one place it is decided — and the pixels
       * above that still belong to the section before it. Probing them lit the
       * previous link on every anchor followed.
       *
       * The `max` is a guard rather than a correction. That margin is computed
       * from the header's own height and clears it at every width, and if a
       * change to one of them ever stops being true, a probe line behind the
       * header is a line nobody is reading.
       */
      const anchor = parseFloat(getComputedStyle(targets[0]).scrollMarginTop) || 0;
      const top = Math.max(anchor, Math.round(header.current?.getBoundingClientRect().height ?? 0));
      const line = top + PROBE_INSET;
      const bottom = Math.max(0, window.innerHeight - line - 1);
      observer = new IntersectionObserver(
        (entries) => {
          for (const entry of entries) {
            if (entry.isIntersecting) onLine.add(entry.target.id);
            else onLine.delete(entry.target.id);
          }
          /*
           * The last in document order, not the first. One line lands in one
           * section, so this is only reached when two of them round to sharing
           * an edge — and there the lower one is the one being scrolled into.
           */
          const lowest = [...targets].reverse().find((el) => onLine.has(el.id));
          setId(lowest?.id ?? null);
        },
        { rootMargin: `-${line}px 0px -${bottom}px 0px` },
      );
      for (const target of targets) observer.observe(target);
    };

    observe();
    window.addEventListener("resize", observe);
    return () => {
      observer?.disconnect();
      window.removeEventListener("resize", observe);
    };
  }, [enabled, header]);

  return id;
}

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

  const shell = useRef<HTMLElement>(null);
  const section = useSectionInView(route === "", shell);

  /*
   * Two kinds of destination, so two values of `aria-current`. A route is a
   * `page`; a section is a `location`, which is the token ARIA has for a place
   * within the page you are already on. Both paint the same, because to a
   * reader they answer the same question.
   */
  const current = (href: string): "page" | "location" | undefined => {
    const [path, hash] = href.split("#");
    if (hash !== undefined) return path === "/" && hash === section ? "location" : undefined;
    return href.slice(1) === route ? "page" : undefined;
  };

  return (
    <header
      ref={shell}
      className="sticky top-0 z-50 border-b border-b-line bg-b-bg/90 backdrop-blur"
    >
      {/*
        The bypass WCAG 2.4.1 asks for, and the reason it is not `sr-only`.
        
        Nine navigation links repeat on every page. A keyboard reader had to
        walk all nine to reach the content, on every navigation. Hidden until
        focused rather than hidden outright: a sighted keyboard user needs to
        see where the focus went, and a skip link nobody can see is the version
        of this that gets shipped broken and never noticed.
      */}
      <a
        href="#main"
        className="sr-only rounded-md bg-b-src text-[13.5px] font-medium text-b-on-accent focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-[60] focus:inline-flex focus:h-11 focus:items-center focus:px-4"
      >
        Skip to content
      </a>
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
        {/*
          `inline-flex` with vertical padding, because these are targets.
          
          They were bare inline links in a line of 11.5px type: 14px tall,
          against the 24px WCAG 2.5.8 asks for. The layout audit exempted them
          because it treated any sibling text as a sentence, and the sibling
          text here is the middle dot between them.
        */}
        <p className="mt-0.5 font-b-mono text-[11.5px] text-b-faint">
          <a
            href="/legal"
            className="inline-flex items-center py-1.5 hover:text-b-text"
          >
            Licensing and privacy
          </a>
          <span aria-hidden="true" className="px-2">
            ·
          </span>
          <a
            href={REPO}
            rel="noreferrer"
            className="inline-flex items-center py-1.5 hover:text-b-text"
          >
            github.com/RealMaxPower/project-beacon
          </a>
        </p>
      </div>
    </footer>
  );
}
