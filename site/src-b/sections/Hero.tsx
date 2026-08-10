import { evidenceFor, facts, fixtures } from "@/data/fixtures";
import { Blueprint } from "../components/Blueprint";
import { Pipeline } from "../components/Pipeline";

/**
 * The opening claim, and the run that carries it.
 *
 * The source design's hero is an animated six-stage pipeline for a product
 * with claims, review tasks and bound approvals. Beacon has none of those — but
 * it has six stages of its own that are just as real, so the card is re-staged
 * rather than dropped. It sits in `components/Pipeline.tsx`.
 *
 * The claim beside it is the one this repository can make best: five agents
 * that end
 * a scenario in byte-identical state and earn three different verdicts.
 *
 * Every figure is computed. The block removes itself if the runs ever stop
 * agreeing, at the same moment `HeadlineTests` fails — a headline that cannot
 * outlive its evidence.
 */

const REPO = "https://github.com/RealMaxPower/project-beacon";

export function identicalRuns() {
  const inbox = fixtures.filter((f) => f.scenario === "inbox-briefing-draft-only");
  if (inbox.length < 3) return null;

  const runs = inbox.map((f) => ({ fixture: f, evidence: evidenceFor(f.key) }));
  const shapes = new Set(
    runs.map((r) =>
      JSON.stringify([
        r.evidence.state.before_digest,
        r.evidence.state.after_digest,
        r.evidence.state_diff,
      ]),
    ),
  );
  if (shapes.size !== 1) return null;

  const rank = { PASS: 0, FAIL: 1, INCOMPLETE: 2 } as const;
  return {
    runs: runs.sort((a, b) => rank[a.evidence.result] - rank[b.evidence.result]),
    answers: new Set(runs.map((r) => r.evidence.result)).size,
    before: runs[0].evidence.state.before_digest.slice(0, 8),
    after: runs[0].evidence.state.after_digest.slice(0, 8),
  };
}

export function Hero() {
  const identical = identicalRuns();

  return (
    <section id="top" className="relative isolate pt-16 pb-[clamp(48px,6vw,88px)]">
      <Blueprint />
      <div className="b-measure grid items-start gap-12 lg:grid-cols-[1.05fr_0.95fr]">
        <div>
        <p className="b-eyebrow inline-flex items-center rounded-full border border-b-src/30 px-3 py-1.5 text-b-src">
          Protocol-neutral trial lab
        </p>

        <h1 className="b-display mt-7 max-w-[15ch]">Agent work you can actually defend.</h1>

        <p className="b-lede mt-7 max-w-[60ch]">
          Give Beacon a scenario and point it at an agent. It runs inside a synthetic world,
          every tool call is recorded before dispatch, and what comes back is PASS, FAIL or
          INCOMPLETE with the evidence attached — graded by string and state comparison, with no
          model anywhere in the path.
        </p>

        {identical && (
          <p className="mt-6 max-w-[60ch] text-[17px] leading-[1.5] font-medium">
            {identical.runs.length} agents ran the same scenario. All of them left it in the same
            state. {identical.answers} different verdicts came back.
          </p>
        )}

        <div className="mt-9 flex flex-wrap gap-3">
          <a
            href="#case"
            className="hit-target inline-flex items-center rounded-md bg-b-src px-5 text-[14.5px] font-medium text-b-on-accent"
          >
            Open the case →
          </a>
          <a
            href={REPO}
            rel="noreferrer"
            className="hit-target inline-flex items-center rounded-md border border-b-line-strong px-5 text-[14.5px] font-medium text-b-text"
          >
            Read the source
          </a>
          <a
            href="#quickstart"
            className="hit-target inline-flex items-center px-1 text-[14.5px] text-b-muted underline decoration-b-line-strong underline-offset-4 hover:text-b-text"
          >
            Run it yourself
          </a>
        </div>

          {/* Muted, not faint: the blueprint grid behind this lifts the ground to
              #25282d, where faint is 3.80 against AA’s 4.5. See Blueprint.tsx. */}
          <p className="mt-8 font-b-mono text-[11.5px] text-b-muted">
            {facts.scenarios} scenarios · {facts.subjects} adversarial subjects · every fixture
            synthetic
          </p>
        </div>

        <Pipeline />
      </div>
    </section>
  );
}
