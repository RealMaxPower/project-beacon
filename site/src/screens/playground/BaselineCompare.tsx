import { RegressionCard } from "@/components/verdict/RegressionCard";
import { TerminalBlock } from "@/components/shell/TerminalBlock";
import { EmptyState } from "@/components/shell/EmptyState";
import { baselines, wasEvaluated } from "@/data/fixtures";

/**
 * Worse than it was, which `--repeat` cannot tell you.
 *
 * `--repeat` asks whether a subject agrees with itself right now. Whether it is
 * worse than it was is a different question, and a subject can be perfectly
 * self-consistent and consistently wrong.
 *
 * The comparison shown here is against the recorded baselines in this
 * repository. Where no second measurement exists yet, this screen says so
 * instead of inventing a "current" number to sit beside the recorded one — a
 * regression card with a fabricated half is worse than no card.
 */

export function BaselineCompare() {
  const grounding = baselines.find((b) => b.scenario === "web-extraction-grounding");
  const reference = baselines.find((b) => b.subject.adapter === "in-process");

  return (
    <section>
      <header className="mb-6">
        <h2 className="mb-2 text-2xl leading-tight font-medium tracking-[-0.025em] text-balance">
          Worse than it was
        </h2>
        <p className="max-w-[68ch] text-[15px] leading-relaxed text-text-muted text-pretty">
          Comparison is by pass <em>rate</em>, because a subject failing a quarter of the time
          still passes three single-run comparisons in four. A drop counts as a regression only
          when the sample rules out chance, so a flaky agent does not fail the build at random
          — and how many runs it takes to prove one scales with how flaky the baseline said the
          subject was.
        </p>
      </header>

      <div className="mb-6">
        <TerminalBlock
          copyable
          lines={[
            "# Against a committed snapshot, recorded on the first run",
            "python3 -m beacon run scenarios/web-extraction-grounding/scenario.json \\",
            "  --repeat 10 --baseline baselines/web-extraction-grounding.claude-sonnet-5.json",
            "",
            "# Or against the last 20 runs already in the output directory",
            "python3 -m beacon run scenarios/inbox-briefing/scenario.json \\",
            "  --repeat 10 --baseline-recent 20",
          ]}
          label="how a regression is checked"
        />
      </div>

      {grounding && reference ? (
        <>
          {/*
           * Read before the cards, not after them.
           *
           * Both cards compare a sample with itself, so the first reads "there
           * is no rate to compare" and the second "NO CHANGE 100% → 100%" —
           * two odd-looking outputs whose explanation sat in a paragraph below
           * both, after the reader had already decided the screen was broken.
           */}
          <p className="mb-5 max-w-[74ch] rounded-card border border-line bg-sunken px-5 py-4 text-[14px] leading-relaxed text-text-muted text-pretty">
            <strong className="font-medium text-text">
              Both cards below compare a recorded baseline against itself
            </strong>
            , because only one sample of each exists. That is the truthful output for a
            comparison with nothing to compare — and taking the second sample of the hosted one
            costs an API key and a few minutes. Until someone does, this screen will not show a
            drop it did not measure.
          </p>

          <div className="grid gap-4 xl:grid-cols-2">
          {/*
           * Two cards, showing the two honest outcomes available here.
           *
           * The grounding assertion has a recorded rate of 0.0, and that zero
           * means "never evaluated" rather than "passed none" — there is no
           * measurement to regress from. Feeding it to `percent()` printed
           * `0% → 0%` directly underneath the section explaining that it was
           * never evaluated, which is the mistake this whole screen is about.
           */}
          <RegressionCard
            assertionId="entities-grounded"
            baselineRate={grounding.assertion_pass_rates["entities-grounded"] ?? 0}
            currentRate={grounding.assertion_pass_rates["entities-grounded"] ?? 0}
            sample={grounding.runs}
            recordedAt={grounding.recorded_at}
            evaluated={wasEvaluated(grounding, "entities-grounded")}
          />

          <RegressionCard
            assertionId="send-never-attempted"
            baselineRate={reference.assertion_pass_rates["send-never-attempted"] ?? 0}
            currentRate={reference.assertion_pass_rates["send-never-attempted"] ?? 0}
            sample={reference.runs}
            recordedAt={reference.recorded_at}
            evaluated={wasEvaluated(reference, "send-never-attempted")}
          />
          </div>
        </>
      ) : (
        <EmptyState
          title="No baseline recorded yet"
          body="Run a scenario with --baseline and Beacon writes one on the first run. Every run after that is compared against it."
        />
      )}
    </section>
  );
}
