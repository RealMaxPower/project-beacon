import { RunStrip } from "@/components/runs/RunStrip";
import { PassRateBar } from "@/components/runs/PassRateBar";
import { TerminalBlock } from "@/components/shell/TerminalBlock";
import { ProvenanceTag } from "@/components/shell/ProvenanceTag";
import { baselines, verdictVector, wasEvaluated } from "@/data/fixtures";
import type { Baseline } from "@/data/types";

/**
 * Step six: run it again, and again.
 *
 * This is where the argument lands. Four passes in a row say nothing that
 * twelve runs cannot contradict, and the numbers here are read out of
 * `baselines/*.json` rather than typed — the README quoted a five-run 20%
 * against a twelve-run figure three times larger for longer than it should
 * have, and reading the file is how that stops being possible.
 */

function Panel({ baseline }: { baseline: Baseline }) {
  const vector = verdictVector(baseline);
  const rates = Object.entries(baseline.assertion_pass_rates);

  return (
    <article className="rounded-card border border-line bg-surface p-5">
      <header className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="font-mono text-[13px] font-medium">{baseline.scenario}</h3>
        <span className="flex items-center gap-2">
          <span className="font-mono text-[11px] text-text-faint">
            {baseline.runs} runs · {baseline.recorded_at.slice(0, 10)}
          </span>
          <ProvenanceTag level="repo" />
        </span>
      </header>

      <p className="mb-4 font-mono text-[11px] text-text-faint">
        {baseline.subject.name}
        {baseline.subject.command ? ` · ${baseline.subject.command.join(" ")}` : ""}
      </p>

      <div className="mb-5">
        <RunStrip results={vector} label="Verdict, run by run" />
      </div>

      <div className="border-t border-line pt-1">
        <p className="mt-3 mb-1 font-mono text-[10.5px] uppercase tracking-[0.1em] text-text-faint">
          Per assertion
        </p>
        {rates.map(([id, rate]) => (
          <PassRateBar
            key={id}
            label={id}
            rate={rate}
            total={baseline.runs}
            evaluated={wasEvaluated(baseline, id)}
          />
        ))}
      </div>
    </article>
  );
}

export function TwelveRuns() {
  const hosted = baselines.filter((b) => b.subject.adapter !== "in-process");
  const local = baselines.filter((b) => b.subject.adapter === "in-process");

  return (
    <section>
      <header className="mb-6">
        <h2 className="mb-2 text-2xl leading-tight font-medium tracking-[-0.025em] text-balance">
          Twelve runs, same agent, same page
        </h2>
        <p className="max-w-[68ch] text-[15px] leading-relaxed text-text-muted text-pretty">
          A single passing run says little if the next one disagrees. These are recorded
          multi-run measurements from this repository — not simulations of one. The command
          that produces them is the same one you would run.
        </p>
      </header>

      <div className="mb-6">
        <TerminalBlock
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
