import { facts } from "@/data/fixtures";

/**
 * Header and footer.
 *
 * The mark is the same three-arc figure the first design uses, drawn from the
 * same path data — one brand, two dressings. It is inlined rather than
 * imported because it is coloured from this design's tokens, and the shared
 * component takes `currentColor` from a palette that does not exist here.
 */

const REPO = "https://github.com/RealMaxPower/project-beacon";

const NAV = [
  ["The case", "#case"],
  ["How it grades", "#how"],
  ["Your stack", "#stack"],
  ["What exists", "#status"],
  ["Quickstart", "#quickstart"],
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

export function Header() {
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
            href="#top"
            className="hit-target flex flex-none items-center gap-2.5 pr-2 text-b-text"
          >
            <Mark />
            <span className="font-b-display text-[15.5px] font-semibold tracking-[-0.02em]">
              Outcome Assurance
            </span>
          </a>

          <nav aria-label="Main" className="hidden min-w-0 flex-1 items-center gap-1 lg:flex">
            {NAV.map(([label, href]) => (
              <a
                key={href}
                href={href}
                className="hit-target inline-flex flex-none items-center rounded-md px-2.5 text-[13.5px] text-b-muted hover:text-b-text"
              >
                {label}
              </a>
            ))}
          </nav>

          <a
            href={REPO}
            rel="noreferrer"
            className="hit-target ml-auto inline-flex flex-none items-center rounded-md bg-b-text px-3.5 text-[13px] font-medium text-b-bg"
          >
            Source
          </a>
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
              className="hit-target inline-flex flex-none items-center rounded-md px-2.5 text-[13.5px] text-b-muted"
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
    <footer className="border-t border-b-line" data-ground="paper">
      <div className="b-measure py-12">
        <div className="flex items-center gap-2.5 text-b-text">
          <Mark />
          <span className="font-b-display text-[15.5px] font-semibold tracking-[-0.02em]">
            Outcome Assurance
          </span>
        </div>

        <p className="b-lede mt-6 max-w-[68ch] text-[14px]">
          Beacon grades observable outcomes and state changes. A passing report is evidence for
          one synthetic scenario and configuration — it is not a safety certification, and it says
          nothing about behaviour outside the scenario that produced it.
        </p>

        <p className="mt-5 font-b-mono text-[11.5px] text-b-faint">
          Apache 2.0 · every scenario fixture is synthetic · {facts.scenarios} scenarios ·{" "}
          <a href={REPO} rel="noreferrer" className="hover:text-b-text">
            github.com/RealMaxPower/project-beacon
          </a>
        </p>
      </div>
    </footer>
  );
}
