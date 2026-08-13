import { evidenceFor, facts, fixtures } from "@/data/fixtures";
import { Band } from "../components/Band";

/**
 * What exists, and what does not.
 *
 * The source design's version lists seventeen shipped capabilities and nine
 * absent ones for a product that does not exist in this repository. Every
 * line here was checked against the code instead: the CLI's own subcommands,
 * the adapters it lists, and the limitations Beacon writes into every bundle
 * it produces.
 *
 * The right-hand column is not a roadmap. The source design says so about its
 * own list and it is the right framing, so it is kept.
 */

/** The limitations Beacon itself attaches to every run. */
function recordedLimitations(): string[] {
  const first = fixtures[0];
  return first ? evidenceFor(first.key).limitations : [];
}

const AVAILABLE = [
  "Scenarios with deterministic, declared assertions",
  "Grading by string and state comparison — no model in the path",
  "PASS, FAIL and INCOMPLETE, with INCOMPLETE meaning could-not-measure",
  "Tool calls recorded before dispatch, so a refused attempt still counts",
  "State captured before and after, with a digest over each",
  "MCP, A2A and a JSONL bridge of about thirty lines",
  "Repeat runs with a recorded baseline and a regression check",
  "An evidence bundle whose digest `project-beacon verify` recomputes",
  "A scenario scaffold that ships with subjects proving it can fail",
];

export function Status() {
  const limitations = recordedLimitations();

  return (
    <Band
      id="status"
      eyebrow="07 — What exists"
      heading="An early lab, and an accurate list of what it does not do."
      lede={
        <>
          The left column is what the code does today. The right is not a roadmap — it is the
          set of limitations Beacon attaches to every bundle it writes, read out of a recorded
          run rather than typed here.
        </>
      }
    >
      <div className="grid gap-5 lg:grid-cols-2">
        <div className="rounded-xl border border-b-ok/30 bg-b-raised p-6">
          <p className="b-eyebrow mb-5 text-b-ok">Available now</p>
          <ul className="flex flex-col gap-3">
            {AVAILABLE.map((item) => (
              <li key={item} className="flex gap-3 text-[13.5px] leading-relaxed text-b-muted">
                <span aria-hidden="true" className="flex-none text-b-ok">
                  ✓
                </span>
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </div>

        <div className="rounded-xl border border-b-line p-6">
          <p className="b-eyebrow mb-5 text-b-review">Recorded limitations</p>
          <ul className="flex flex-col gap-3">
            {limitations.map((item) => (
              <li key={item} className="flex gap-3 text-[13.5px] leading-relaxed text-b-muted">
                <span aria-hidden="true" className="flex-none text-b-review">
                  —
                </span>
                <span>{item}</span>
              </li>
            ))}
          </ul>
          <p className="mt-5 border-t border-b-line pt-4 text-[12px] leading-relaxed text-b-faint">
            These ship inside every evidence bundle, so they travel with the report rather than
            living only on this page. {facts.subjects_with_open_defects} of the{" "}
            {facts.subjects} adversarial subjects currently produce a verdict Beacon disagrees
            with.
          </p>
        </div>
      </div>
    </Band>
  );
}
