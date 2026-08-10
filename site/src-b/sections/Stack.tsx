import { Band } from "../components/Band";

/**
 * What it can be pointed at.
 *
 * The source design draws upstream systems flowing into a band and out again,
 * and that is the right picture for Beacon too: five adapters in, one bundle
 * out, with the grading in between and the same on every path. A flat grid of
 * adapter names — which is what stood here first — says what Beacon connects to
 * and nothing about what it does with the connection.
 *
 * The one thing the diagram must not flatten is the level. An MCP tool is
 * graded at level 1 and the in-process reference agent at level 4; drawing them
 * as equivalent inputs would be flattering and wrong, so each chip carries its
 * own, and the caption underneath says what a level is.
 */

const ADAPTERS = [
  ["a2a", "L2", "A2A agent over HTTP or JSON-RPC"],
  ["mcp-host", "L1", "any MCP-speaking agent host"],
  ["mcp-stdio", "L1", "an MCP server over stdio"],
  ["command", "L3", "any CLI, API or SDK agent, over JSONL"],
  ["reference", "L4", "Beacon's own in-process agent"],
] as const;

export function Stack() {
  return (
    <Band
      id="stack"
      eyebrow="05 — Your stack"
      heading="If it speaks a protocol Beacon knows, it can be graded."
      lede="Beacon sits beside whatever you already run rather than asking you to move it. What changes between adapters is not the grading — it is how much of the agent Beacon can see, and that is stated rather than smoothed over."
    >
      {/*
        The connectors are hairline `<span>`s rather than SVG: they are two
        straight vertical lines, and a rule that inherits `--b-line` costs
        nothing and stays correct on both grounds without a second colour.
      */}
      <div className="flex flex-col items-center">
        <ul className="grid w-full gap-3 sm:grid-cols-2 xl:grid-cols-5">
          {ADAPTERS.map(([id, level, what]) => (
            <li key={id} className="rounded-lg border border-b-line px-4 py-3.5">
              <div className="flex items-baseline justify-between gap-2">
                <span className="font-b-mono text-[13px] text-b-src">{id}</span>
                <span className="b-eyebrow text-b-faint">{level}</span>
              </div>
              <p className="mt-1.5 text-[12.5px] leading-snug text-b-muted">{what}</p>
            </li>
          ))}
        </ul>

        <span aria-hidden="true" className="h-8 w-px bg-b-line" />

        <div
          className="w-full rounded-xl border px-6 py-7 text-center"
          style={{
            borderColor: "var(--b-src)",
            background: "color-mix(in oklab, var(--b-src) 7%, transparent)",
          }}
        >
          <p className="font-b-display text-[22px] font-semibold tracking-[-0.02em] text-b-src">
            Beacon
          </p>
          <p className="mx-auto mt-2 max-w-[62ch] text-[13.5px] leading-relaxed text-b-muted">
            The same synthetic world, the same declared checks, the same string and state
            comparison — whichever adapter the agent arrived through.
          </p>
        </div>

        <span aria-hidden="true" className="h-8 w-px bg-b-line" />

        <ul className="grid w-full gap-3 sm:grid-cols-3">
          {(
            [
              ["evidence.json", "every event, in the order it was recorded"],
              ["report.md", "the same run, readable"],
              ["PASS · FAIL · INCOMPLETE", "one verdict, and why"],
            ] as const
          ).map(([name, what]) => (
            <li key={name} className="rounded-lg border border-b-line px-4 py-3.5">
              <p className="font-b-mono text-[13px] text-b-text">{name}</p>
              <p className="mt-1.5 text-[12.5px] leading-snug text-b-muted">{what}</p>
            </li>
          ))}
        </ul>
      </div>

      <p className="mt-8 max-w-[70ch] text-[13px] leading-relaxed text-b-faint">
        The level is how much of the agent the protocol lets Beacon observe, not how good the
        agent is. Level 4 is the reference agent, which Beacon owns — no third-party agent
        currently reaches it, and the row of adapters would read as an inventory of what works
        today if that went unsaid.
      </p>
    </Band>
  );
}
