import { Band } from "../components/Band";

/**
 * A different job from the tools already running.
 *
 * Ports almost unchanged from the source design — the argument holds for
 * Beacon without adjustment, because it is about a category rather than a
 * feature list. The third card is the inverted one, as in the design.
 */

const COLUMNS = [
  {
    head: "Agent runtimes",
    note: "LangGraph, n8n, MCP hosts, custom",
    points: ["Execute the work", "Own the tools and the loop", "Report what happened, not whether it should have"],
  },
  {
    head: "Observability",
    note: "Traces, spans, cost, latency",
    points: ["Explain behaviour", "Answer how long and how much", "Have no opinion about correctness"],
  },
  {
    head: "Beacon",
    note: "Scenarios, evidence, verdicts",
    points: [
      "Grades against checks declared in advance",
      "Records the attempt, not only the outcome",
      "Says INCOMPLETE when it could not tell",
      "Hands you the bundle it decided from",
    ],
    invert: true,
  },
];

export function Compare() {
  return (
    <Band
      id="compare"
      ground="alt"
      eyebrow="06 — Not another framework"
      heading="Runtimes execute. Traces explain. Neither one grades."
      lede="Beacon does not run your agent in production and does not want to. It asks a narrower question — did this behave, on work you can describe — and answers it the same way twice."
    >
      <div className="grid gap-5 lg:grid-cols-3">
        {COLUMNS.map((column) => (
          <div
            key={column.head}
            className={`rounded-xl border p-6 ${
              column.invert
                ? "border-transparent bg-[#0e1116] text-[#f5f7fa]"
                : "border-b-line bg-b-raised"
            }`}
          >
            <p
              className="font-b-display text-[17px] font-semibold tracking-[-0.015em]"
              style={column.invert ? { color: "#f5f7fa" } : undefined}
            >
              {column.head}
            </p>
            <p
              className="mt-1 font-b-mono text-[11.5px]"
              style={{ color: column.invert ? "#79828f" : undefined }}
            >
              {column.note}
            </p>
            <ul className="mt-5 flex flex-col gap-2.5">
              {column.points.map((point) => (
                <li
                  key={point}
                  className="flex gap-2.5 text-[13px] leading-relaxed"
                  style={{ color: column.invert ? "#d5dbe3" : undefined }}
                >
                  <span aria-hidden="true" style={{ color: column.invert ? "#4ed8ea" : undefined }}>
                    —
                  </span>
                  <span className={column.invert ? "" : "text-b-muted"}>{point}</span>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </Band>
  );
}
