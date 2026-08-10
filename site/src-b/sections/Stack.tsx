import { Band } from "../components/Band";

/**
 * What it can be pointed at.
 *
 * The source design draws upstream chips flowing into a band and out again.
 * The shape is kept; the names are Beacon's real adapters, with the
 * integration level each reaches — because the level is the honest part. An
 * MCP tool is graded at level 1 and the in-process reference agent at level 4,
 * and a diagram that showed them as equivalent inputs would be flattering and
 * wrong.
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
      <ul className="b-cells grid sm:grid-cols-2 xl:grid-cols-3">
        {ADAPTERS.map(([id, level, what]) => (
          <li key={id} className="px-5 py-5">
            <div className="flex items-baseline gap-3">
              <span className="font-b-mono text-[13px] text-b-src">{id}</span>
              <span className="b-eyebrow text-b-faint">{level}</span>
            </div>
            <p className="mt-2 text-[13px] leading-relaxed text-b-muted">{what}</p>
          </li>
        ))}
      </ul>

      <p className="mt-8 max-w-[70ch] text-[13px] leading-relaxed text-b-faint">
        The level is how much of the agent the protocol lets Beacon observe, not how good the
        agent is. Level 4 is the reference agent, which Beacon owns — no third-party agent
        currently reaches it, and the table would be an inventory of what works today if that
        went unsaid.
      </p>
    </Band>
  );
}
