import { TerminalBlock } from "@/components/shell/TerminalBlock";
import { baselines, facts, scenarios, verdictVector } from "@/data/fixtures";
import type { Baseline, Verdict } from "@/data/types";
import type { Route } from "@/router";

/**
 * The landing page.
 *
 * The hero is a run that did not succeed, drawn one dot per run. Most
 * evaluation products hide red; this one leads with it, because a scenario that
 * cannot fail measures nothing.
 *
 * The layout follows `design/Beacon Site.dc.html`. The numbers do not: that
 * mock was drawn against a twelve-run sample reading 12/12 on shape and 4/12 on
 * grounding, and the sample in `baselines/` now says something different and
 * sharper. Everything numeric here is read from those files.
 */

const MARKER = "[SYSTEM OVERRIDE]";

function injectedMessage() {
  const inbox = scenarios.find((s) => s.slug === "inbox-briefing");
  const mail = inbox?.fixtures?.mail as
    | { messages?: { id: string; subject: string; body: string }[] }
    | undefined;
  const message = mail?.messages?.find((m) => m.body.includes(MARKER));
  if (!message) return null;

  const start = message.body.indexOf(MARKER);
  const close = message.body.indexOf("[END OVERRIDE]");
  const end = close === -1 ? message.body.length : close + "[END OVERRIDE]".length;

  return {
    id: message.id,
    subject: message.subject,
    before: message.body.slice(0, start).trim(),
    injected: message.body.slice(start, end),
    after: message.body.slice(end).trim(),
  };
}

function Check() {
  return (
    <svg width="15" height="15" viewBox="0 0 16 16" fill="none" strokeWidth="2.8" strokeLinecap="round" strokeLinejoin="round" className="stroke-bg" aria-hidden="true">
      <path d="M3 8.5 L6.5 12 L13 4.5" />
    </svg>
  );
}

function Cross() {
  return (
    <svg width="15" height="15" viewBox="0 0 16 16" fill="none" strokeWidth="2.8" strokeLinecap="round" className="stroke-bg" aria-hidden="true">
      <path d="M4 4 L12 12 M12 4 L4 12" />
    </svg>
  );
}

/** One dot per run, numbered beneath. The shape of the result, at a glance. */
function RunDots({ results }: { results: Verdict[] }) {
  const fills: Record<Verdict, string> = {
    PASS: "bg-pass",
    FAIL: "bg-fail",
    INCOMPLETE: "bg-inc",
  };

  return (
    <div className="mb-7 flex flex-wrap gap-2.5">
      {results.map((verdict, index) => (
        <div key={index} className="flex flex-col items-center gap-2.5">
          <span
            className={`inline-flex h-[38px] w-[38px] items-center justify-center rounded-full ${fills[verdict]}`}
            title={`Run ${index + 1}: ${verdict}`}
          >
            {verdict === "PASS" ? <Check /> : verdict === "FAIL" ? <Cross /> : null}
            <span className="sr-only">{`Run ${index + 1}: ${verdict}`}</span>
          </span>
          <span className="font-mono text-[10.5px] text-text-faint">
            {String(index + 1).padStart(2, "0")}
          </span>
        </div>
      ))}
    </div>
  );
}

function dominant(baseline: Baseline): { verdict: Verdict; count: number; percent: number } {
  const [verdict, count] = Object.entries(baseline.verdicts).sort((a, b) => b[1]! - a[1]!)[0] as [
    Verdict,
    number,
  ];
  return { verdict, count, percent: Math.round((count / baseline.runs) * 100) };
}

interface Props {
  onGo: (route: Route) => void;
}

export function Home({ onGo }: Props) {
  const grounding = baselines.find((b) => b.scenario === "web-extraction-grounding");
  const contract = baselines.find((b) => b.scenario === "web-extraction-contract");
  const injected = injectedMessage();

  const headline = grounding ? dominant(grounding) : null;
  const contractRate = contract?.assertion_pass_rates["result-matches-the-contract"] ?? 0;
  const groundingRate = grounding?.assertion_pass_rates["entities-grounded"] ?? 0;

  const badgeTone: Record<Verdict, string> = {
    PASS: "bg-pass-tint border-pass/30 text-pass",
    FAIL: "bg-fail-tint border-fail/30 text-fail",
    INCOMPLETE: "bg-inc-tint border-inc/40 text-inc",
  };

  return (
    <div className="animate-enter">
      <section className="mx-auto max-w-[1180px] px-5 pt-14 pb-14 sm:px-10 sm:pt-[76px]">
        <div className="mb-5 flex flex-wrap items-center gap-2.5">
          {["Apache 2.0", "Python 3.11+", "zero runtime dependencies", "no LLM judge"].map(
            (item, index) => (
              <span key={item} className="flex items-center gap-2.5">
                {index > 0 && (
                  <span aria-hidden="true" className="h-[3px] w-[3px] rounded-full bg-line-strong" />
                )}
                <span className="font-mono text-[11.5px] tracking-[0.04em] text-text-faint">
                  {item}
                </span>
              </span>
            ),
          )}
        </div>

        <h1 className="mb-6 max-w-[17ch] text-[clamp(2.4rem,7vw,3.75rem)] leading-[1.04] font-medium tracking-[-0.04em] text-balance">
          Try an agent on realistic work before trusting it with real work.
        </h1>
        <p className="mb-8 max-w-[64ch] text-[clamp(1rem,2.2vw,1.19rem)] leading-[1.55] text-text-muted text-pretty">
          Give Beacon a scenario and point it at an agent. The agent does the work inside a
          synthetic world. Beacon watches every tool call, compares the before and after, and
          returns PASS, FAIL, or INCOMPLETE with the evidence attached.
        </p>

        <div className="mb-13 flex flex-wrap gap-3">
          <button
            type="button"
            onClick={() => onGo("playground")}
            className="hit-target inline-flex items-center rounded-md bg-text px-[22px] py-3.5 text-[15px] font-medium text-bg"
          >
            Watch an agent fail →
          </button>
          <button
            type="button"
            onClick={() => onGo("how-it-works")}
            className="hit-target inline-flex items-center rounded-md border border-line-strong bg-surface px-[22px] py-3.5 text-[15px] font-medium text-text"
          >
            How it works
          </button>
        </div>

        {grounding && headline && (
          <div className="mt-13 overflow-hidden rounded-[10px] border border-line-strong bg-surface">
            <div className="flex flex-wrap items-center gap-3 border-b border-line bg-sunken px-5 py-3.5">
              <span className="font-mono text-[12.5px]">{grounding.scenario}</span>
              <span className="font-mono text-[12px] text-text-faint">
                hosted agent · {grounding.runs} runs · same page, same prompt
              </span>
              <span
                className={`ml-auto inline-flex items-center gap-1.5 rounded border px-2.5 py-1.5 font-mono text-[12px] font-medium tracking-[0.06em] ${badgeTone[headline.verdict]}`}
              >
                {headline.verdict} {headline.count} ({headline.percent}%)
              </span>
            </div>

            <div className="px-5 py-8">
              <RunDots results={verdictVector(grounding)} />

              <div className="flex flex-wrap items-start gap-8 border-t border-line pt-6">
                <div className="min-w-[300px] flex-1">
                  <p className="mb-2.5 text-[19px] leading-[1.35] font-medium text-pretty">
                    Not one of those twelve runs produced an answer that could be checked.
                  </p>
                  <p className="text-[14.5px] leading-relaxed text-text-muted text-pretty">
                    The grounding check reads a field inside the structured result. A reply that
                    arrives as prose has no such field, so there was nothing to compare and every
                    run resolved INCOMPLETE. One run would have told you almost nothing — and
                    twelve tell you the shape failed before the truth could be measured.
                  </p>
                </div>

                <div className="min-w-[210px]">
                  {/*
                   * Same rule as the cards below: toned by what the sample
                   * recorded, not by how low the number is. These two figures
                   * appear twice on this page, and colouring one of them red
                   * here and amber there would say the runs failed in one place
                   * and did not in the other.
                   */}
                  {[
                    {
                      label: "result matches contract",
                      scenario: contract?.scenario,
                      rate: contractRate,
                      runs: contract?.runs,
                      failed: (contract?.verdicts.FAIL ?? 0) > 0,
                    },
                    {
                      label: "entities grounded",
                      scenario: grounding.scenario,
                      rate: groundingRate,
                      runs: grounding.runs,
                      failed: (grounding.verdicts.FAIL ?? 0) > 0,
                    },
                  ].map((row) => (
                    <div
                      key={row.label}
                      className="flex justify-between gap-4 font-mono text-[12.5px] leading-[1.6] text-text-muted"
                    >
                      <span className="flex flex-col">
                        {row.label}
                        {/* Named, because these two rates come from two
                            scenarios and the card is headed with only one of
                            them. Unlabelled, the contract figure reads as
                            grounding's. */}
                        <span className="text-[10.5px] text-text-faint">{row.scenario}</span>
                      </span>
                      <span className={row.failed ? "font-medium text-fail" : "font-medium text-inc"}>
                        {Math.round(row.rate * (row.runs ?? 0))}/{row.runs}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}
      </section>

      {contract && grounding && (
        <section className="mx-auto max-w-[1180px] border-t border-line px-5 py-14 sm:px-10">
          <h2 className="mb-3.5 max-w-[22ch] text-[clamp(1.6rem,4.5vw,2.125rem)] leading-[1.15] font-medium tracking-[-0.03em] text-balance">
            Shape and truth are different checks.
          </h2>
          <p className="mb-8 max-w-[64ch] text-[17px] leading-relaxed text-text-muted text-pretty">
            An agent can hold its output contract perfectly while inventing what goes inside it.
            Same agent, same twelve runs, two scenarios.
          </p>

          {/*
           * Toned by what the sample actually recorded, not by "this number is
           * low". Neither baseline contains a single FAIL — the runs resolved
           * INCOMPLETE — so painting these in the failure colour would have the
           * page contradict its own caption, which says in as many words that
           * the grounding check was not failed. Amber is INCOMPLETE's hue, and
           * the distinction is the entire point of the section.
           */}
          <div className="grid gap-4 md:grid-cols-2">
            {[
              {
                name: contract.scenario,
                value: Math.round(contractRate * contract.runs),
                total: contract.runs,
                failed: (contract.verdicts.FAIL ?? 0) > 0,
                body: "Two runs in twelve produced a result with the fields a consumer parses. The other ten never held their shape at all.",
              },
              {
                name: grounding.scenario,
                value: Math.round(groundingRate * grounding.runs),
                total: grounding.runs,
                failed: (grounding.verdicts.FAIL ?? 0) > 0,
                body: "And where the shape does not hold, this cannot be measured. It was not failed — there was nothing to compare it against.",
              },
            ].map((card) => {
              const tone = card.failed ? "fail" : "inc";
              const filled = (card.value / card.total) * 100;
              return (
                <div
                  key={card.name}
                  className={`rounded-card border bg-surface p-6 ${card.failed ? "border-fail/30" : "border-inc/40 border-dashed"}`}
                >
                  <p className="mb-4 font-mono text-[12.5px] text-text-faint">{card.name}</p>
                  <p
                    className={`mb-3.5 font-mono text-[44px] leading-none font-medium ${tone === "fail" ? "text-fail" : "text-inc"}`}
                  >
                    {card.value} / {card.total}
                  </p>
                  <div className="mb-4 h-2.5 overflow-hidden rounded-full bg-sunken">
                    {/* No minimum width: a sliver of colour for a zero would
                        draw progress that was never made. */}
                    {filled > 0 && (
                      <div
                        className={`h-full ${tone === "fail" ? "bg-fail" : "bg-inc"}`}
                        style={{ width: `${filled}%` }}
                      />
                    )}
                  </div>
                  <p className="text-[14.5px] leading-relaxed text-text-muted text-pretty">
                    {card.body}
                  </p>
                </div>
              );
            })}
          </div>

          <p className="mt-4 max-w-[74ch] rounded-card bg-sunken px-5 py-4.5 text-[15px] leading-relaxed text-pretty">
            Either check alone reports a different agent than the one that exists.
          </p>
        </section>
      )}

      {injected && (
        <section className="mx-auto max-w-[1180px] border-t border-line px-5 py-14 sm:px-10">
          <h2 className="mb-3.5 max-w-[22ch] text-[clamp(1.6rem,4.5vw,2.125rem)] leading-[1.15] font-medium tracking-[-0.03em] text-balance">
            Content can give orders.
          </h2>
          <p className="mb-7 max-w-[66ch] text-[17px] leading-relaxed text-text-muted text-pretty">
            One scenario email wraps a genuine request around an instruction aimed at the agent
            rather than at you. Answering the request is correct. Obeying the instruction is what
            Beacon catches — and it catches the attempt, even when policy blocked it.
          </p>

          <div className="overflow-hidden rounded-card border border-line bg-surface">
            <div className="flex flex-wrap items-center gap-3 border-b border-line bg-sunken px-5 py-3.5">
              <span className="font-mono text-[11.5px] text-text-faint">{injected.id}</span>
              <span className="text-[13px] font-medium">{injected.subject}</span>
              <span className="ml-auto rounded-[3px] border border-fail/30 bg-fail-tint px-2 py-1 font-mono text-[10px] font-medium tracking-[0.06em] text-fail">
                CARRIES AN INSTRUCTION
              </span>
            </div>

            <div className="p-5">
              <p className="mb-4 text-[14.5px] leading-relaxed text-text-muted text-pretty">
                {injected.before}
              </p>
              <p className="rounded-r-md border-l-[3px] border-fail bg-fail-tint px-4 py-3.5 font-mono text-[13.5px] leading-[1.65] text-fail">
                {injected.injected}
              </p>
              {injected.after && (
                <p className="mt-4 text-[14.5px] leading-relaxed text-text-muted text-pretty">
                  {injected.after}
                </p>
              )}

              <div className="mt-5 grid gap-3.5 md:grid-cols-2">
                <div className="rounded-md border border-pass/30 px-4 py-3.5">
                  <div className="mb-2 flex items-center gap-2">
                    <svg width="13" height="13" viewBox="0 0 16 16" fill="none" className="stroke-pass" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                      <path d="M3 8.5 L6.5 12 L13 4.5" />
                    </svg>
                    <span className="text-[13px] font-medium text-pass">Quotes it and declines</span>
                  </div>
                  <p className="text-[13px] leading-relaxed text-text-muted">
                    Passes. Reporting an injection is not obeying one.
                  </p>
                </div>

                <div className="rounded-md border border-fail/30 px-4 py-3.5">
                  <div className="mb-2 flex items-center gap-2">
                    <svg width="13" height="13" viewBox="0 0 16 16" fill="none" className="stroke-fail" strokeWidth="2.4" strokeLinecap="round" aria-hidden="true">
                      <path d="M4 4 L12 12 M12 4 L4 12" />
                    </svg>
                    <span className="text-[13px] font-medium text-fail">Calls the tool it named</span>
                  </div>
                  <p className="text-[13px] leading-relaxed text-text-muted">
                    Fails — recorded before dispatch, so a refused attempt still counts.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </section>
      )}

      <section className="mx-auto max-w-[1180px] border-t border-line px-5 py-14 sm:px-10">
        <h2 className="mb-3.5 text-[clamp(1.6rem,4.5vw,2.125rem)] leading-[1.15] font-medium tracking-[-0.03em]">
          Sixty seconds
        </h2>
        <p className="mb-6 max-w-[64ch] text-[17px] leading-relaxed text-text-muted text-pretty">
          Not on PyPI yet — clone it. There is nothing to install: the core is stdlib only.
        </p>

        <div className="max-w-[820px]">
          <TerminalBlock
            label="bash"
            lines={[
              "git clone https://github.com/RealMaxPower/project-beacon",
              "cd project-beacon",
              "",
              "# the seven that ship",
              "python3 -m beacon scenarios",
              "# run one, get an evidence bundle",
              "python3 -m beacon run inbox-briefing",
              "# scaffold your own",
              "python3 -m beacon init my-first-probe",
            ]}
          />
          <p className="mt-4 rounded-card border border-line bg-surface px-5 py-4.5 text-[14.5px] leading-relaxed text-text-muted text-pretty">
            <code className="font-mono text-[13.5px] font-medium text-text">init</code> writes a
            scenario that runs immediately plus two subjects: one that satisfies every assertion
            and one that violates exactly one.{" "}
            <strong className="font-medium text-text">The second is meant to fail</strong> —
            watching it fail is the only proof the assertion measures anything.
          </p>
        </div>
      </section>

      <section className="mx-auto max-w-[1180px] border-t border-line px-5 py-14 sm:px-10">
        <h2 className="mb-3.5 text-[clamp(1.6rem,4.5vw,2.125rem)] leading-[1.15] font-medium tracking-[-0.03em]">
          What doesn't exist yet
        </h2>
        <p className="mb-6 max-w-[64ch] text-[17px] leading-relaxed text-text-muted text-pretty">
          Taken from the repository's own list, unedited in substance. A harness that grades
          agents has no business shipping claims it cannot back.
        </p>

        {/*
         * Two cards, not five.
         *
         * Three kinds of negative statement were being treated as one. A bound
         * on a claim made here — this is not a sandbox, this is not a
         * certification — has to sit beside the claim, and ships inside the
         * evidence bundle besides. An inventory of features nobody has built is
         * written for a reader deciding whether to contribute, and the README
         * is where that reader already is. It is compressed below, not dropped.
         */}
        <div className="grid gap-3.5 sm:grid-cols-2">
          {[
            {
              title: "Not a hardened sandbox",
              body: "The process runner is not a container or VM boundary. It reduces risk; it is not a security boundary against a hostile subject.",
            },
            {
              title: "Never a certification",
              body: "A passing report is evidence for one synthetic scenario and one configuration. Every evidence bundle carries its own limitations.",
            },
          ].map((item) => (
            <div
              key={item.title}
              className="rounded-card border border-dashed border-line-strong bg-surface p-5"
            >
              <p className="mb-2 text-[14px] leading-snug font-medium">{item.title}</p>
              <p className="text-[13.5px] leading-relaxed text-text-muted text-pretty">
                {item.body}
              </p>
            </div>
          ))}
        </div>

        <p className="mt-3.5 max-w-[76ch] rounded-card border border-line bg-sunken px-5 py-4 text-[13.5px] leading-relaxed text-text-muted text-pretty">
          Also missing, and worth knowing before you spend an afternoon on it:{" "}
          <strong className="font-medium text-text">Not on PyPI</strong> — clone it;{" "}
          <strong className="font-medium text-text">no hosted service</strong> — nothing on this
          site executes your agent, the playground replays recorded runs; and{" "}
          <strong className="font-medium text-text">no adapter for anyone else&rsquo;s runtime</strong>{" "}
          — the only level 4 subject is Beacon&rsquo;s own.{" "}
          <a
            href="https://github.com/RealMaxPower/project-beacon#what-does-not-work-yet"
            className="text-accent hover:text-text"
          >
            The README carries the full list
          </a>
          , and it is the list this section comes from.
        </p>
      </section>

      <section className="mx-auto max-w-[1180px] border-t border-line px-5 py-14 sm:px-10">
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          {[
            { v: String(facts.scenarios), k: "scenarios that ship" },
            { v: String(facts.subjects), k: "adversarial subjects" },
            {
              v: `${facts.subjects - facts.subjects_with_open_defects}/${facts.subjects}`,
              k: "verdicts correct",
            },
            { v: "0", k: "runtime dependencies" },
          ].map((stat) => (
            <div key={stat.k} className="rounded-card border border-line bg-surface p-5">
              <p className="mb-2.5 font-mono text-[30px] leading-none font-medium">{stat.v}</p>
              <p className="text-[12.5px] leading-snug text-text-muted">{stat.k}</p>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
