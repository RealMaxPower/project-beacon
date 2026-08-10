import { Band } from "../components/Band";

/**
 * The pipeline, as four steps rather than the design's six.
 *
 * The source design walks Normalize → Collect → Resolve → Check → Review →
 * Reconcile. Three of those describe machinery Beacon does not have, so the
 * sequence here is the one the first design already documents and the code
 * actually performs. Six boxes with two of them invented would look better and
 * mean less.
 */

const STEPS = [
  {
    n: "01",
    tone: "text-b-src",
    head: "Declare",
    body: "A scenario states the world, the tool surface, the goal, and the checks — as JSON, before anything runs.",
  },
  {
    n: "02",
    tone: "text-b-src",
    head: "Run",
    body: "The agent works inside a synthetic service. Every call is recorded before dispatch, so a refusal is evidence rather than an absence.",
  },
  {
    n: "03",
    tone: "text-b-ok",
    head: "Check",
    body: "Assertions compare strings and state. No model sits in this path, which is why the same run grades the same way twice.",
  },
  {
    n: "04",
    tone: "text-b-review",
    head: "Report",
    body: "PASS, FAIL or INCOMPLETE, with the events, the diff, the limitations and a digest that beacon verify recomputes.",
  },
];

const CONTRACT = `{
  "schema_version": "1.0",
  "id": "inbox-briefing-draft-only",
  "goal": "Review the visible inbox…",
  "tools": ["mail_list_messages", "mail_read_message", …],
  "assertions": [
    { "id": "send-never-attempted", "type": "event_absent" },
    { "id": "protected-never-read",  "type": "event_absent" }
  ]
}`;

export function HowItGrades() {
  return (
    <Band
      id="how"
      ground="paper"
      eyebrow="04 — How it grades"
      heading="Four steps, and a model in none of them."
      lede="The scenario is a file. The checks are declared in it before the agent is told anything, which is what stops a result being written to fit whatever came back."
    >
      <div className="b-cells grid sm:grid-cols-2 xl:grid-cols-4">
        {STEPS.map((step) => (
          <div key={step.n} className="px-5 py-6">
            {/*
              The numeral and a rule that runs out from it to the cell's edge.
              It is the source design's one memorable detail in this grid: the
              rule ties the number to the width it governs, so four cells read
              as one sequence rather than four unrelated boxes. `aria-hidden`
              because the number beside it already says the same thing.
            */}
            <div className="flex items-center gap-3">
              <p className={`b-eyebrow flex-none ${step.tone}`}>{step.n}</p>
              <span aria-hidden="true" className="h-px flex-1 bg-b-line" />
            </div>
            <p className="mt-3 font-b-display text-[17px] font-semibold tracking-[-0.015em]">
              {step.head}
            </p>
            <p className="mt-2 text-[13px] leading-relaxed text-b-muted">{step.body}</p>
          </div>
        ))}
      </div>

      <div className="mt-10 overflow-hidden rounded-xl border border-b-line bg-[#0e1116]">
        <div className="flex items-center gap-3 border-b border-white/10 px-5 py-3">
          <span className="font-b-mono text-[11.5px] text-[#4ed8ea]">scenario.json</span>
          <span className="font-b-mono text-[11.5px] text-[#79828f]">
            declared before the run, not after it
          </span>
        </div>
        <pre className="overflow-x-auto px-5 py-4 font-b-mono text-[11.5px] leading-relaxed text-[#d5dbe3]">
          {CONTRACT}
        </pre>
      </div>
    </Band>
  );
}
