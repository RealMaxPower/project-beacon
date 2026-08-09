import { RunStrip } from "@/components/runs/RunStrip";
import { PassRateBar } from "@/components/runs/PassRateBar";
import { Disclosure } from "@/components/shell/Disclosure";
import { TerminalBlock } from "@/components/shell/TerminalBlock";
import { ProvenanceTag } from "@/components/shell/ProvenanceTag";
import { assertionCopy } from "@/data/copy";
import { baselines, verdictVector, wasEvaluated } from "@/data/fixtures";
import type { Baseline, Verdict } from "@/data/types";

/**
 * Step six: run it again, and again.
 *
 * This is where the argument lands. Four passes in a row say nothing that
 * twelve runs cannot contradict, and the numbers here are read out of
 * `baselines/*.json` rather than typed — the README quoted a five-run 20%
 * against a twelve-run figure three times larger for longer than it should
 * have, and reading the file is how that stops being possible.
 */

/** How the runs came out, in a sentence, before any of the detail. */
function headline(baseline: Baseline): { text: string; verdict: Verdict } {
  const [verdict, count] = Object.entries(baseline.verdicts).sort(
    (a, b) => (b[1] ?? 0) - (a[1] ?? 0),
  )[0] as [Verdict, number];

  const every = count === baseline.runs;
  const wording = {
    PASS: "passed",
    FAIL: "failed",
    INCOMPLETE: "came back INCOMPLETE",
  }[verdict];

  return {
    verdict,
    text: every
      ? `All ${baseline.runs} runs ${wording}.`
      : `${count} of ${baseline.runs} runs ${wording}.`,
  };
}

function Panel({ baseline }: { baseline: Baseline }) {
  const vector = verdictVector(baseline);
  const rates = Object.entries(baseline.assertion_pass_rates);
  const result = headline(baseline);

  const tone = {
    PASS: "text-pass",
    FAIL: "text-fail",
    INCOMPLETE: "text-inc",
  }[result.verdict];

  /*
   * A panel where every check held in every run is nine identical green bars
   * saying one thing. The summary states the measurement in full — nothing is
   * withheld, and the breakdown is one click away. Where anything moved, the
   * breakdown is the finding and stays open.
   */
  const uniform = rates.every(([id, rate]) => rate === 1 && wasEvaluated(baseline, id));

  const breakdown = (
    <div>
      {rates.map(([id, rate]) => (
        <PassRateBar
          key={id}
          id={id}
          label={assertionCopy(baseline.scenario, { id, description: id }).sentence}
          rate={rate}
          total={baseline.runs}
          evaluated={wasEvaluated(baseline, id)}
        />
      ))}
    </div>
  );

  return (
    <article className="flex flex-col rounded-card border border-line bg-surface p-5">
      {/*
       * The finding first, the identifier second. This opened on
       * `web-extraction-grounding` in monospace — the reader's first noun was
       * a scenario id, and what the twelve runs actually said was four
       * elements further down in 12px type.
       */}
      <h3 className={`mb-1.5 text-[19px] leading-snug font-medium text-balance ${tone}`}>
        {result.text}
      </h3>
      <p className="mb-4 font-mono text-[11px] text-text-faint">
        {baseline.scenario} · {baseline.subject.name}
        {baseline.subject.command ? ` · ${baseline.subject.command.join(" ")}` : ""}
      </p>

      <div className="mb-5">
        <RunStrip results={vector} label="Verdict, run by run" />
      </div>

      {/* Natural height, not `mt-auto`. Pushing the breakdown down to align
          the two footers opened a blank band inside the shorter panel that
          read as content that had failed to render. */}
      <div className="border-t border-line pt-4">
        {uniform ? (
          <Disclosure
            question={`Every one of the ${rates.length} checks held in all ${baseline.runs} runs — see them`}
          >
            {breakdown}
          </Disclosure>
        ) : (
          <>
            <p className="mb-1 text-[13px] font-medium">How often each check held</p>
            {breakdown}
          </>
        )}
      </div>

      <p className="mt-4 flex flex-wrap items-center gap-2 border-t border-line pt-3 font-mono text-[11px] text-text-faint">
        recorded {baseline.recorded_at.slice(0, 10)}
        <ProvenanceTag level="repo" />
      </p>
    </article>
  );
}

export function TwelveRuns() {
  const hosted = baselines.filter((b) => b.subject.adapter !== "in-process");
  const local = baselines.filter((b) => b.subject.adapter === "in-process");

  return (
    <section>
      {/*
       * The heading said "Twelve runs" over three panels of twelve, twelve and
       * ten. The count belongs on each panel, which reads it from the file.
       */}
      <header className="mb-6">
        <h2 className="mb-2 text-2xl leading-tight font-medium tracking-[-0.025em] text-balance">
          One run tells you almost nothing.
        </h2>
        <p className="max-w-[68ch] text-[15px] leading-relaxed text-text-muted text-pretty">
          The same agent, the same prompt, over and over. These are recorded multi-run
          measurements from this repository — not simulations of one. The command that produces
          them is the same one you would run.
        </p>
      </header>

      <div className="mb-6">
        <TerminalBlock
          copyable
          lines={[
            "python3 -m beacon run scenarios/web-extraction-grounding/scenario.json \\",
            "  --adapter command \\",
            '  --command "python3 examples/anthropic_jsonl_agent.py" \\',
            "  --env-secret ANTHROPIC_API_KEY \\",
            "  --repeat 12",
          ]}
          label="what recorded these"
        />
      </div>

      <div className="mb-6 grid gap-4 xl:grid-cols-2">
        {hosted.map((baseline) => (
          <Panel key={baseline.file} baseline={baseline} />
        ))}
      </div>

      <div className="mb-6 rounded-card border border-line border-l-[3px] border-l-accent bg-surface p-5">
        <h3 className="mb-2 text-[17px] leading-snug font-medium text-balance">
          Shape and truth are different checks, and one gates the other.
        </h3>
        <p className="max-w-[68ch] text-[14px] leading-relaxed text-text-muted text-pretty">
          Look at <code className="font-mono text-text">entities-grounded</code>. It was not
          failed — it was never <em>evaluated</em>. It reads a field inside the structured
          result, and a reply that arrives as prose has no such field, so there was nothing to
          compare and every run resolved INCOMPLETE. You cannot measure whether an agent tells
          the truth until it holds its shape, and a harness that scored those runs as failures
          would be publishing a fabrication rate it never measured.
        </p>
      </div>

      {local.length > 0 && (
        <div className="grid gap-4 xl:grid-cols-2">
          {local.map((baseline) => (
            <Panel key={baseline.file} baseline={baseline} />
          ))}
        </div>
      )}
    </section>
  );
}
