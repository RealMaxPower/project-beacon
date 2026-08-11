import { Band } from "../components/Band";

/**
 * The stake, before any evidence.
 *
 * The source design's version contrasts a "typical agent workflow" ending in
 * an unknown outcome against a chain ending in a recorded one. The contrast
 * holds for Beacon; the second column is rewritten to the chain Beacon
 * actually produces — a scenario, recorded calls, deterministic checks, and a
 * verdict with the bundle attached. No claims, no review tasks, no bound
 * approvals: Beacon has none of those, and drawing them would be inventing a
 * product.
 */

const WITHOUT = ["Prompt", "Tools", "Answer", "Unknown outcome"];
const WITH = ["Scenario", "Recorded calls", "Deterministic checks", "Verdict + evidence"];

const QUESTIONS = [
  "Which tool calls did it actually make?",
  "What did it try to do and get refused?",
  "Which checks were evaluated, and which could not be?",
  "Did the state change, or only the attempt?",
  "Would the same run come out this way again?",
  "Can somebody else recompute this from the bundle?",
];

function Chain({ steps, tone }: { steps: string[]; tone: "bad" | "ok" }) {
  return (
    <ol className="flex flex-col gap-2">
      {steps.map((step, i) => {
        const last = i === steps.length - 1;
        return (
          <li
            key={step}
            className={`rounded-md border px-4 py-2.5 text-[13.5px] ${
              last && tone === "bad"
                ? "border-b-bad/40 text-b-bad"
                : last
                  ? "border-b-ok/40 text-b-ok"
                  : "border-b-line text-b-muted"
            }`}
          >
            {step}
          </li>
        );
      })}
    </ol>
  );
}

export function MissingLayer() {
  return (
    <Band
      id="missing-layer"
      ground="alt"
      eyebrow="01 — The missing layer"
      heading="An agent can finish a task without anyone being able to say what it did."
      lede="A finished task and a result somebody can rely on are two different things. The distance between them is where the evidence goes missing — and a report that compares before and after cannot close it, because the most informative thing an agent does is often the thing it was stopped from doing."
    >
      <div className="grid gap-5 lg:grid-cols-2">
        <div className="rounded-xl border border-dashed border-b-line-strong p-6">
          <p className="b-eyebrow mb-5 text-b-faint">Without a record</p>
          <Chain steps={WITHOUT} tone="bad" />
        </div>
        <div className="rounded-xl border border-b-line bg-b-raised p-6">
          <p className="b-eyebrow mb-5 text-b-src">With one</p>
          <Chain steps={WITH} tone="ok" />
        </div>
      </div>

      <ul className="b-cells mt-10 grid gap-px sm:grid-cols-2 xl:grid-cols-3">
        {QUESTIONS.map((question) => (
          <li key={question} className="px-4 py-5 text-[13.5px] leading-relaxed text-b-muted">
            {question}
          </li>
        ))}
      </ul>
    </Band>
  );
}
