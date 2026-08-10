import { Band } from "../components/Band";

/**
 * The commands, as they actually are.
 *
 * The source design's quickstart runs `python3 -m outcome_assurance demo`,
 * which does not exist. These are `beacon`'s real subcommands, and the second
 * one is deliberately the scaffold that ships with a subject written to fail —
 * a scenario that cannot fail measures nothing, and the fastest way to believe
 * that is to watch one fail on purpose.
 */

const STEPS = [
  ["git clone https://github.com/RealMaxPower/project-beacon", "no dependencies to install"],
  ["python3 -m beacon scenarios", "what ships, and what each one grades"],
  ["python3 -m beacon run inbox-briefing", "one run, one evidence bundle"],
  ["python3 -m beacon verify <bundle>", "recompute the digest yourself"],
  ["python3 -m beacon init my-first-probe", "scaffolds a scenario and a subject that breaks it"],
] as const;

export function Quickstart() {
  return (
    <Band
      id="quickstart"
      ground="paper"
      eyebrow="05 — Quickstart"
      heading="Clone it, run one scenario, read the bundle."
      lede="Nothing to install: Beacon is standard library only, and the scenarios that ship are synthetic worlds rather than anything that reaches your network."
    >
      <div className="overflow-hidden rounded-xl border border-b-line bg-[#0e1116]">
        <div className="flex items-center gap-2 border-b border-white/10 px-4 py-2.5">
          <span aria-hidden="true" className="h-2.5 w-2.5 rounded-full bg-[#ff6e55]" />
          <span aria-hidden="true" className="h-2.5 w-2.5 rounded-full bg-[#f0ac3a]" />
          <span aria-hidden="true" className="h-2.5 w-2.5 rounded-full bg-[#5bdd93]" />
          <span className="ml-2 font-b-mono text-[11px] text-[#79828f]">bash</span>
        </div>
        <ol className="px-5 py-5">
          {STEPS.map(([command, note]) => (
            <li key={command} className="py-2">
              <p className="font-b-mono text-[12.5px] break-all text-[#f5f7fa]">
                <span className="text-[#4ed8ea]">$ </span>
                {command}
              </p>
              <p className="mt-1 font-b-mono text-[11.5px] text-[#79828f]"># {note}</p>
            </li>
          ))}
        </ol>
      </div>
    </Band>
  );
}
