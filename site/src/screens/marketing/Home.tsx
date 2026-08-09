import { Disclosure } from "@/components/shell/Disclosure";
import { NextSteps } from "@/components/shell/NextSteps";
import { TerminalBlock } from "@/components/shell/TerminalBlock";
import {
  baselines,
  blockedAttempts,
  evidenceFor,
  eventsFor,
  facts,
  fixtures,
  scenarios,
  verdictVector,
  wasEvaluated,
} from "@/data/fixtures";
import type { Baseline, Verdict } from "@/data/types";
import type { Go } from "@/router";

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
  if (!inbox) return null;

  const mail = inbox.fixtures?.mail as
    | { messages?: { id: string; subject: string; body: string }[] }
    | undefined;
  const message = mail?.messages?.find((m) => m.body.includes(MARKER));
  if (!message) return null;

  const start = message.body.indexOf(MARKER);
  const close = message.body.indexOf("[END OVERRIDE]");
  const end = close === -1 ? message.body.length : close + "[END OVERRIDE]".length;

  return {
    id: message.id,
    // Carried so the link below the block opens the playground at the scenario
    // this message actually came from. The slug and the id differ for exactly
    // this scenario, and the playground resolves by id.
    scenarioId: inbox.id,
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
  onGo: Go;
}

export function Home({ onGo }: Props) {
  const grounding = baselines.find((b) => b.scenario === "web-extraction-grounding");
  const contract = baselines.find((b) => b.scenario === "web-extraction-contract");
  const injected = injectedMessage();

  const headline = grounding ? dominant(grounding) : null;
  const contractRate = contract?.assertion_pass_rates["result-matches-the-contract"] ?? 0;
  const groundingRate = grounding?.assertion_pass_rates["entities-grounded"] ?? 0;

  /*
   * Whether the check ran at all, from the one helper that decides it.
   *
   * Both figures appear twice on this page. Deciding "measured" separately
   * in each place is how the hero came to print a bare 0/12 beside a real
   * pass rate while the card below it explained that the same number was not
   * one.
   */
  const contractMeasured = contract
    ? wasEvaluated(contract, "result-matches-the-contract")
    : false;
  const groundingMeasured = grounding ? wasEvaluated(grounding, "entities-grounded") : false;

  /*
   * The run in the hero, read out of its bundle.
   *
   * Every figure here is derived rather than written: the assertion counts, the
   * event count, how many sends were refused and which tool refused them, and
   * which assertion failed. Re-record the fixtures with a different subject and
   * the sentence above changes with them, or the block disappears — which is
   * the only way a headline claim about a run stays true to the run.
   */
  const hero = (() => {
    const fixture = fixtures.find((f) => f.key === "misbehaving");
    if (!fixture) return null;

    const evidence = evidenceFor(fixture.key);
    const events = eventsFor(fixture.key);
    const refused = blockedAttempts(events);
    const [blockedTool, blocked] = [...refused.entries()].sort((a, b) => b[1] - a[1])[0] ?? [];
    if (!blockedTool || !blocked) return null;

    /*
     * Each refusal with the argument it carried.
     *
     * Drawn as three identical rows, these read as a rendering repeat rather
     * than as three separate attempts — the one thing the block exists to
     * show. The calls are distinguishable in the bundle: every `tool_call`
     * has a `call_id`, and the refusal that follows quotes it back, so the
     * draft each attempt reached for can be recovered rather than invented.
     */
    const calls = new Map(
      events
        .filter((e) => e.kind === "tool_call")
        .map((e) => [
          (e.payload as { call_id?: string }).call_id,
          Object.values((e.payload as { arguments?: Record<string, unknown> }).arguments ?? {})[0],
        ]),
    );
    const refusals = events
      .filter((e) => e.kind === "tool_error" && e.target === blockedTool)
      .map((e) => {
        const payload = e.payload as { call_id?: string; message?: string };
        return {
          id: e.sequence,
          argument: String(calls.get(payload.call_id) ?? ""),
          message: payload.message ?? "",
        };
      });

    return {
      evidence,
      events,
      blockedTool,
      blocked,
      refusals,
      // The work it was actually asked to do, counted the same way.
      drafts: events.filter((e) => e.kind === "tool_call" && e.target === "mail_create_draft")
        .length,
      passed: evidence.assertions.filter((a) => a.passed).length,
      total: evidence.assertions.length,
      failing: evidence.assertions.find((a) => a.passed === false),
    };
  })();

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

        {/*
          * The hero is a run that failed, and it has to be a run a stranger can
          * read.
          *
          * It used to be the hosted twelve-run baseline: `web-extraction-grounding`
          * as the first noun on the page, twelve identical amber dots, and
          * "not one of those twelve runs produced an answer that could be
          * checked". Every word of that is true and none of it is legible to
          * someone who does not yet know what a scenario is — the likeliest
          * first reading was that Beacon had malfunctioned. It also resolved
          * INCOMPLETE directly beneath a button that says "Watch an agent
          * fail", which is the one verdict that is explicitly not a failure.
          *
          * This is a FAIL, from a mailbox, and the misbehaviour is a sentence
          * long: it was told not to send, and it tried. The hosted baseline
          * still leads "Shape and truth" further down, where a reader has the
          * vocabulary for the subtler point it makes.
          */}
        {hero && (
          <div className="mt-13 overflow-hidden rounded-[10px] border border-line-strong bg-surface">
            <div className="flex flex-wrap items-center gap-3 border-b border-line bg-sunken px-5 py-3.5">
              <span className="font-mono text-[12.5px]">{hero.evidence.scenario.id}</span>
              <span className="font-mono text-[12px] text-text-faint">
                demo agent · level {hero.evidence.subject.integration_level} · {hero.events.length}{" "}
                recorded events
              </span>
              <span
                className={`ml-auto inline-flex items-center gap-1.5 rounded border px-2.5 py-1.5 font-mono text-[12px] font-medium tracking-[0.06em] ${badgeTone[hero.evidence.result]}`}
              >
                {hero.evidence.result} {hero.passed}/{hero.total}
              </span>
            </div>

            <div className="px-5 py-8">
              <p className="mb-2.5 max-w-[54ch] text-[19px] leading-[1.35] font-medium text-pretty">
                It did the work it was asked for, then tried {hero.blocked} times to send mail it
                was told not to send.
              </p>
              <p className="mb-7 max-w-[68ch] text-[14.5px] leading-relaxed text-text-muted text-pretty">
                {hero.drafts} draft replies created, which is the task. Policy refused every send.
                Beacon records the attempt before dispatch, so being stopped is not the same as
                not having tried.
              </p>

              {/*
                * The refused calls, drawn heavier than a successful one rather
                * than greyed out. A blocked attempt is the most informative
                * event in this run; rendering it as the faded row is how an
                * interface tells you the opposite of what happened.
                */}
              <div className="mb-4 flex flex-col gap-1.5">
                {hero.refusals.map((refusal) => (
                  <div
                    key={refusal.id}
                    className="flex flex-wrap items-center gap-3 rounded-md border border-fail/30 border-l-[3px] border-l-fail bg-fail-tint px-4 py-2.5"
                  >
                    <span className="font-mono text-[12.5px] font-medium on-tint">
                      {hero.blockedTool}
                    </span>
                    {refusal.argument && (
                      <span className="font-mono text-[12px] on-tint">{refusal.argument}</span>
                    )}
                    <span className="ml-auto rounded-[3px] border border-current/30 px-1.5 py-0.5 font-mono text-[10px] tracking-[0.08em] text-fail">
                      BLOCKED
                    </span>
                  </div>
                ))}
              </div>

              {/* The refusal in the service's own words, once — it is the same
                  sentence on all three, and repeating it per row buries the
                  drafts, which are what make the attempts distinct. */}
              <p className="mb-7 font-mono text-[11.5px] leading-relaxed text-text-faint">
                {hero.refusals[0]?.message} · recorded before dispatch
              </p>

              <div className="border-t border-line pt-6">
                <p className="mb-2 font-mono text-[12.5px] text-fail">{hero.failing?.id}</p>
                <p className="mb-4 max-w-[70ch] text-[14.5px] leading-relaxed text-text-muted text-pretty">
                  The one check that failed — and it is written as an attempt rather than an
                  outcome.
                </p>
                <Disclosure question="Why isn't it enough to check what the mailbox ended up like?">
                  <p>
                    Nothing was sent, so the mailbox ended exactly as a well-behaved run would
                    leave it — a report of what changed would call these two agents identical.
                  </p>
                </Disclosure>
              </div>
            </div>
          </div>
        )}
      </section>

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

          {/*
            * A quiet link rather than a button.
            *
            * The page has three and a half thousand pixels below the hero and,
            * until now, nothing to do in any of them — but a filled button
            * every second screen turns an argument into a funnel. This is the
            * text equivalent of "you can go and look at this one", placed
            * where the reader has just been shown a thing worth looking at.
            */}
          <button
            type="button"
            onClick={() => onGo("playground", injected.scenarioId)}
            className="hit-target mt-5 inline-flex items-center gap-1.5 text-[14.5px] font-medium text-accent hover:text-text"
          >
            Replay this run in the playground
            <span aria-hidden="true">→</span>
          </button>
        </section>
      )}

      {contract && grounding && (
        <section className="mx-auto max-w-[1180px] border-t border-line px-5 py-14 sm:px-10">
          <h2 className="mb-3.5 max-w-[22ch] text-[clamp(1.6rem,4.5vw,2.125rem)] leading-[1.15] font-medium tracking-[-0.03em] text-balance">
            Shape and truth are different checks.
          </h2>
          {/*
            * The lede said "same twelve runs", and there are twenty-four: two
            * baselines of twelve, one per scenario. The agent and the prompt
            * really are identical — the two scenario files carry the same goal
            * string, and differ only in what they assert — so that is what it
            * claims now.
            *
            * It also promised an agent holding its contract while inventing
            * the contents, which is a real failure mode and not the one in
            * this sample: the shape failed first, ten times in twelve, and
            * took the grounding check down with it. Claiming the more
            * dramatic story over evidence for a quieter one is the habit this
            * whole site argues against.
            */}
          <p className="mb-8 max-w-[66ch] text-[17px] leading-relaxed text-text-muted text-pretty">
            The agent above was a demo that misbehaves on purpose. This one is a real model,
            answering the same prompt twelve times against each of two scenarios. One grades the
            shape of the reply. The other grades whether what is inside it is really on the page.
          </p>

          {/*
            * The twelve-run strip, moved down from the hero.
            *
            * It reads as the shape of a result only once a visitor knows what a
            * run is, and above the fold it was twelve identical amber circles
            * introduced by a scenario id. Here it arrives after a single run
            * has been walked through in full, which is the context that makes
            * "all twelve came out the same" a finding rather than a texture.
            */}
          {headline && (
            <div className="mb-9 overflow-hidden rounded-card border border-line bg-surface">
              <div className="flex flex-wrap items-center gap-3 border-b border-line bg-sunken px-5 py-3.5">
                <span className="font-mono text-[12.5px]">{grounding.scenario}</span>
                <span className="font-mono text-[12px] text-text-faint">
                  hosted model · {grounding.runs} runs · same page, same prompt
                </span>
                <span
                  className={`ml-auto inline-flex items-center gap-1.5 rounded border px-2.5 py-1.5 font-mono text-[12px] font-medium tracking-[0.06em] ${badgeTone[headline.verdict]}`}
                >
                  {headline.verdict} {headline.count} ({headline.percent}%)
                </span>
              </div>
              <div className="px-5 pt-7 pb-6">
                <RunDots results={verdictVector(grounding)} />
                <p className="max-w-[72ch] border-t border-line pt-5 text-[14.5px] leading-relaxed text-text-muted text-pretty">
                  Twelve runs, twelve INCOMPLETEs, and not one of them a failure. The replies
                  arrived as prose with the data written out mid-sentence, so the field the
                  grounding check reads was never there to read. One run would have told you
                  almost nothing. Twelve tell you this is what the agent does.
                </p>
              </div>
            </div>
          )}

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
                asks: "Does the reply have the shape a consumer can parse?",
                value: Math.round(contractRate * contract.runs),
                total: contract.runs,
                measured: contractMeasured,
                failed: (contract.verdicts.FAIL ?? 0) > 0,
                body: "Two replies in twelve arrived with the fields a consumer reads. The other ten came back as prose with the data written out in the middle of a sentence.",
              },
              {
                name: grounding.scenario,
                asks: "Are the values in that reply actually on the page?",
                /*
                 * Zero, and not a pass rate.
                 *
                 * This check reads values out of the structured reply. Where
                 * there is no structured reply there is no value to read, so
                 * Beacon records the assertion as unmeasured and the run as
                 * INCOMPLETE. Rendering that as "0 / 12" in the same type as
                 * the card beside it published a fabrication rate nobody
                 * measured — the caption said "it was not failed" while the
                 * number said otherwise, and at 44px the number wins.
                 * `PassRateBar` already had the answer; this card was not
                 * using it.
                 *
                 * Still derived from the recorded rate rather than written as
                 * a literal zero: what makes the figure honest is that it
                 * follows the baseline, and a hardcoded 0 would keep saying
                 * zero after a re-recording said otherwise.
                 */
                value: Math.round(groundingRate * grounding.runs),
                total: grounding.runs,
                measured: groundingMeasured,
                failed: (grounding.verdicts.FAIL ?? 0) > 0,
                body: "Never ran. There was no structured reply to read a value out of, so there was nothing to compare against the page. Not a fabrication rate — an unanswered question.",
              },
            ].map((card) => {
              const tone = card.failed ? "fail" : "inc";
              const filled = card.measured ? (card.value / card.total) * 100 : 0;
              return (
                <div
                  key={card.name}
                  className={`rounded-card border bg-surface p-6 ${card.failed ? "border-fail/30" : "border-inc/40 border-dashed"}`}
                >
                  <p className="mb-1.5 font-mono text-[12.5px] text-text-faint">{card.name}</p>
                  {/* Each card says what it asks. The pair used to read as one
                      sentence split across two boxes, so the right-hand card
                      opened with "And where the shape does not hold, this
                      cannot be measured" — a fragment whose "this" was named
                      only in the card beside it, and not at all once the grid
                      stacks on a phone. */}
                  <p className="mb-4 text-[14px] leading-snug font-medium text-pretty">
                    {card.asks}
                  </p>
                  <p
                    className={`mb-3.5 font-mono leading-none font-medium ${tone === "fail" ? "text-fail" : "text-inc"}`}
                  >
                    {card.measured ? (
                      <span className="text-[44px]">
                        {card.value} / {card.total}
                      </span>
                    ) : (
                      <>
                        <span className="mr-2 align-middle text-[15px] tracking-[0.02em]">
                          measured
                        </span>
                        <span className="align-middle text-[44px]">0 / {card.total}</span>
                      </>
                    )}
                  </p>
                  {/*
                    * No track at all where nothing was measured.
                    *
                    * Removing the coloured fill was not enough: an empty
                    * trough beside a filled one is still a progress bar, and
                    * it reads as zero progress rather than as no measurement.
                    * The space is held so the two captions stay on the same
                    * line — the absence is the point, a ragged grid is not.
                    */}
                  {card.measured ? (
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
                  ) : (
                    <div className="mb-4 h-2.5" aria-hidden="true" />
                  )}
                  <p className="text-[14.5px] leading-relaxed text-text-muted text-pretty">
                    {card.body}
                  </p>
                </div>
              );
            })}
          </div>

          {/*
            * This said "either check alone reports a different agent than the
            * one that exists", which is a good line about a sample this is
            * not: one of the two checks here reports nothing at all. What the
            * runs actually show is the order the questions have to be asked
            * in, and what a zero is allowed to mean.
            */}
          <p className="mt-4 max-w-[74ch] text-[15.5px] leading-relaxed font-medium text-pretty">
            You cannot ask whether an answer is true until you can find the answer.
          </p>

          <div className="mt-4 max-w-[74ch]">
            <Disclosure question="So why not just report that second card as a zero?">
              <p>
                A check that never ran is not a check that failed — and reporting this zero as a
                fabrication rate would be inventing a measurement, on a page about not doing
                that.
              </p>
            </Disclosure>
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
            copyable
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

        {/*
         * Three limitations, on three lines.
         *
         * These were one sentence with three semicolons in it, which is how a
         * reader skims past all three. They are not collapsed and never will
         * be: a bound belongs beside the claim it bounds, and this whole site
         * argues that the ones behind a click are the ones nobody reads.
         */}
        <div className="mt-3.5 max-w-[76ch] rounded-card border border-line bg-sunken px-5 py-4">
          <p className="mb-3 text-[13.5px] leading-relaxed text-text-muted">
            Also missing, and worth knowing before you spend an afternoon on it:
          </p>
          <dl className="flex flex-col gap-2.5">
            {[
              { k: "Not on PyPI", v: "Clone it." },
              {
                k: "No hosted service",
                v: "Nothing on this site executes your agent — the playground replays recorded runs.",
              },
              {
                k: "No adapter for anyone else’s runtime",
                v: "The only level 4 subject is Beacon’s own.",
              },
            ].map((item) => (
              <div key={item.k} className="flex flex-col gap-0.5 sm:flex-row sm:gap-3">
                <dt className="flex-none text-[13.5px] leading-relaxed font-medium sm:w-[19rem]">
                  {item.k}
                </dt>
                <dd className="text-[13.5px] leading-relaxed text-text-muted text-pretty">
                  {item.v}
                </dd>
              </div>
            ))}
          </dl>
          <p className="mt-3.5 border-t border-line pt-3 text-[13.5px] leading-relaxed text-text-muted">
            <a
              href="https://github.com/RealMaxPower/project-beacon#what-does-not-work-yet"
              className="text-accent hover:text-text"
            >
              The README carries the full list
            </a>
            , and it is the list this section comes from.
          </p>
        </div>
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

      {/*
       * The clone command appears twice on this page, and that is deliberate.
       * "Sixty seconds" is where a reader who is already convinced goes
       * looking; this is where the reader who just finished the argument
       * arrives. Sending them back up four thousand pixels to find the first
       * one is the problem, not the repetition.
       */}
      <NextSteps
        onGo={onGo}
        lead="Everything above is a recorded run you can open, or a command you can paste. Nothing here asks you for an account, and there is no key to hand over — your agent brings its own model."
      />
    </div>
  );
}
