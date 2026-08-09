import { TerminalBlock } from "@/components/shell/TerminalBlock";
import type { Go } from "@/router";

/**
 * What to do now, at the end of every page.
 *
 * Every page on this site used to end on a paragraph. Home ended on a stat
 * grid after four and a half thousand pixels; "How it works" ended on a note
 * about MCP completion signals. A reader who had just read the whole argument
 * was returned to the top of the page to find the one button in the header, or
 * to nothing at all.
 *
 * Three actions, because there are three things a reader of this site can
 * actually do: replay a recorded run, clone it and run their own, or read the
 * code. There is no fourth — no signup, no waitlist, no "talk to us" — and
 * there is no component here to build one.
 *
 * `section`, never `footer`: the shell already renders the one `contentinfo`
 * landmark the document is allowed, and `tools/lint.tsx` fails a second.
 */

const REPO = "https://github.com/RealMaxPower/project-beacon";

interface Props {
  onGo: Go;
  /**
   * How this page hands over, in its own words.
   *
   * Required rather than defaulted: the same closing sentence on six pages is
   * how a site starts sounding like it was assembled rather than written.
   */
  lead: string;
  /** Optional deep link — opens the playground already pointed at a scenario. */
  scenarioId?: string;
  /**
   * Drop the GitHub link. For the one page that already ends on a link into
   * the repository, where a second one is just noise.
   */
  hideRepo?: boolean;
}

export function NextSteps({ onGo, lead, scenarioId, hideRepo = false }: Props) {
  return (
    <section className="border-t border-line">
      <div className="mx-auto max-w-[1180px] px-5 py-12 sm:px-10">
        <h2 className="mb-3 max-w-[24ch] text-[clamp(1.4rem,3.6vw,1.75rem)] leading-[1.15] font-medium tracking-[-0.03em] text-balance">
          Three things you can do with this.
        </h2>
        <p className="mb-8 max-w-[64ch] text-[15.5px] leading-relaxed text-text-muted text-pretty">
          {lead}
        </p>

        {/*
         * `min-w-0` on both columns, not only in the `minmax(0, …)` track.
         *
         * A single-column grid has no track sizing to inherit, so on a phone
         * the terminal's longest line set the column's width and pushed the
         * whole document 204px wider than the viewport — the page scrolled
         * sideways and the copy button sat off the right edge of it.
         */}
        <div className="grid items-start gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.15fr)]">
          <div className="flex min-w-0 flex-col gap-4">
            <div className="rounded-card border border-line bg-surface p-5">
              <h3 className="mb-1.5 text-[15px] leading-snug font-medium">
                Watch one, without installing anything
              </h3>
              <p className="mb-4 max-w-[46ch] text-[13.5px] leading-relaxed text-text-muted text-pretty">
                Recorded runs, replayed in the browser — including the ones that fail. Nothing
                executes on this site.
              </p>
              <button
                type="button"
                onClick={() => onGo("playground", scenarioId)}
                className="hit-target inline-flex items-center rounded-row bg-text px-4 text-[13.5px] font-medium text-bg"
              >
                Open the playground
              </button>
            </div>

            {!hideRepo && (
              <div className="rounded-card border border-line bg-surface p-5">
                <h3 className="mb-1.5 text-[15px] leading-snug font-medium">Read the code</h3>
                <p className="mb-4 max-w-[46ch] text-[13.5px] leading-relaxed text-text-muted text-pretty">
                  Apache 2.0. The README carries what works, and the list of what does not.
                </p>
                {/* The label, not the URL. Spelled out, it is 224px of
                    unbreakable monospace, and on a phone that is wider than
                    the card it sits in. */}
                <a
                  href={REPO}
                  className="hit-target inline-flex items-center rounded-row border border-line-strong px-4 font-mono text-[13px] text-text-muted hover:text-text"
                >
                  Read it on GitHub
                </a>
              </div>
            )}
          </div>

          <div className="min-w-0 rounded-card border border-line bg-surface p-5">
            <h3 className="mb-1.5 text-[15px] leading-snug font-medium">
              Run it against your own agent
            </h3>
            <p className="mb-4 max-w-[52ch] text-[13.5px] leading-relaxed text-text-muted text-pretty">
              Not on PyPI yet, so clone it. There is nothing to install after that — the core is
              stdlib only.
            </p>
            <TerminalBlock
              copyable
              lines={[
                "git clone https://github.com/RealMaxPower/project-beacon",
                "cd project-beacon",
                "",
                "# run one, get an evidence bundle",
                "python3 -m beacon run inbox-briefing",
                "",
                "# scaffold your own scenario, plus a subject meant to fail it",
                "python3 -m beacon init my-first-probe",
              ]}
            />
          </div>
        </div>
      </div>
    </section>
  );
}
