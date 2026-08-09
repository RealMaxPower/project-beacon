import { Mark } from "@/components/shell/Mark";
import { ThemeToggle, useTheme } from "@/components/shell/ThemeToggle";
import { Playground } from "@/screens/playground/Playground";
import { Home } from "@/screens/marketing/Home";
import { HowItWorks } from "@/screens/marketing/HowItWorks";
import { Scenarios } from "@/screens/marketing/Scenarios";
import { ForBuilders } from "@/screens/marketing/ForBuilders";
import { Docs } from "@/screens/marketing/Docs";
import { HostedLab } from "@/screens/marketing/HostedLab";
import { NOT_FOUND, routes, useRoute, type Go, type Resolved } from "@/router";

/**
 * The shell.
 *
 * There is no logo wall, counter, testimonial or badge in this application, and
 * no component exists to build one. Nothing to fill in later means no pressure
 * to invent it.
 */

function screenFor(route: Resolved, param: string | null, go: Go) {
  switch (route) {
    case NOT_FOUND:
      return (
        <div className="mx-auto max-w-[1180px] px-5 py-20 sm:px-10">
          <p className="mb-3 font-mono text-[11px] uppercase tracking-[0.12em] text-text-faint">
            404
          </p>
          <h1 className="mb-4 max-w-[22ch] text-[clamp(1.6rem,4.5vw,2.125rem)] leading-tight font-medium tracking-[-0.03em] text-balance">
            There is no page at that address.
          </h1>
          <p className="mb-6 max-w-[60ch] text-[15px] leading-relaxed text-text-muted text-pretty">
            The link may be mistyped, or it may have pointed at something that no longer
            exists. Everything this site has is in the navigation above.
          </p>
          <button
            type="button"
            onClick={() => go("")}
            className="hit-target inline-flex items-center rounded-row bg-text px-4 text-[13.5px] font-medium text-bg"
          >
            Go to the home page
          </button>
        </div>
      );
    case "how-it-works":
      return <HowItWorks onGo={go} />;
    case "scenarios":
      return <Scenarios onGo={go} />;
    case "for-builders":
      return <ForBuilders onGo={go} />;
    case "playground":
      /*
       * Keyed on the deep-link target so arriving from a scenario card
       * starts a fresh run at that scenario, rather than leaving whatever
       * was half-finished on screen with a new heading over it.
       */
      return <Playground key={param ?? ""} scenarioId={param} />;
    case "docs":
      return <Docs onGo={go} />;
    case "hosted":
      return <HostedLab onGo={go} />;
    default:
      return <Home onGo={go} />;
  }
}

export function App() {
  const [theme, toggle] = useTheme();
  const [{ route, param }, go] = useRoute();

  return (
    <>
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:top-3 focus:left-3 focus:z-50 focus:rounded-row focus:bg-text focus:px-3 focus:py-2 focus:text-bg"
      >
        Skip to content
      </a>

      {/*
       * The nav carries the pages you read. The playground is a filled button
       * on the right instead: it is the thing the site is for, and burying it
       * as the sixth item in a row of links understates that.
       */}
      {/*
       * Two rows on a phone, one from `sm` up — and it does not wrap.
       *
       * Wrapping put the header at 219px on a 390px screen: 26% of the
       * viewport, permanently, with content ghosting through a 95%-opaque
       * background. The nav scrolls sideways instead, which costs a gesture and
       * gives the page back a quarter of itself.
       */}
      <header className="sticky top-0 z-50 border-b border-line bg-bg/95 backdrop-blur">
        <div className="mx-auto max-w-[1180px] px-5 sm:px-10">
          <div className="flex items-center gap-3 py-2">
            <button
              type="button"
              onClick={() => go("")}
              className="hit-target flex flex-none items-center gap-2.5 pr-2"
              aria-label="Beacon, home"
            >
              <Mark size={19} />
              <span className="text-[17px] leading-none font-medium tracking-[-0.025em]">
                Beacon
              </span>
            </button>

            <nav
              aria-label="Main"
              className="-mx-1 hidden min-w-0 flex-1 items-center gap-0.5 lg:flex"
            >
              {routes
                .filter((r) => r.path !== "playground" && r.path !== "hosted")
                .map((r) => (
                  <button
                    key={r.path}
                    type="button"
                    onClick={() => go(r.path)}
                    aria-current={route === r.path ? "page" : undefined}
                    className={`hit-target inline-flex flex-none items-center rounded-row px-3 text-[13.5px] ${
                      route === r.path
                        ? "bg-sunken font-medium text-text"
                        : "text-text-muted hover:text-text"
                    }`}
                  >
                    {r.label}
                  </button>
                ))}
            </nav>

            <div className="ml-auto flex flex-none items-center gap-2">
              <button
                type="button"
                onClick={() => go("playground")}
                className="hit-target inline-flex items-center rounded-row bg-text px-3 text-[13px] font-medium text-bg sm:px-4"
              >
                Playground
              </button>
              <ThemeToggle theme={theme} onToggle={toggle} />
              <a
                href="https://github.com/RealMaxPower/project-beacon"
                className="hit-target hidden items-center rounded-row border border-line-strong px-3.5 font-mono text-[13px] text-text-muted hover:text-text lg:inline-flex"
              >
                GitHub
              </a>
            </div>
          </div>

          {/*
           * The same nav, on its own scrolling row, only where it will not fit.
           *
           * The fade is not decoration. At 390px this row hides 119px — two of
           * five destinations — and the only cue was a scrollbar, which iOS
           * does not draw until after you have already scrolled. Two pages were
           * undiscoverable unless you guessed to swipe a row that did not look
           * swipeable. The mask stops at the last item, so it fades nothing
           * when everything fits.
           */}
          <div className="relative lg:hidden">
            <nav
              aria-label="Main"
              className="flex items-center gap-0.5 overflow-x-auto pb-1.5 [mask-image:linear-gradient(to_right,black_calc(100%-2.5rem),transparent)]"
            >
            {routes
              .filter((r) => r.path !== "playground" && r.path !== "hosted")
              .map((r) => (
                <button
                  key={r.path}
                  type="button"
                  onClick={() => go(r.path)}
                  aria-current={route === r.path ? "page" : undefined}
                  className={`hit-target inline-flex flex-none items-center rounded-row px-3 text-[13.5px] ${
                    route === r.path
                      ? "bg-sunken font-medium text-text"
                      : "text-text-muted"
                  }`}
                >
                  {r.label}
                </button>
                ))}
            </nav>
          </div>
        </div>
      </header>

      <main id="main">{screenFor(route, param, go)}</main>

      <footer className="border-t border-line">
        <div className="mx-auto max-w-[1180px] px-5 py-8 sm:px-11">
          <p className="max-w-[72ch] text-[13px] leading-relaxed text-text-muted text-pretty">
            Beacon grades observable outcomes and state changes. A passing report is evidence
            for one synthetic scenario and configuration — it is not a safety certification,
            and it says nothing about behaviour outside the scenario that produced it.
          </p>
          <p className="mt-3 font-mono text-[11px] text-text-faint">
            Apache 2.0 · all scenario fixtures are synthetic ·{" "}
            <a href="https://github.com/RealMaxPower/project-beacon" className="hover:text-text">
              github.com/RealMaxPower/project-beacon
            </a>
          </p>
        </div>
      </footer>
    </>
  );
}
