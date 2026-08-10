import { facts } from "@/data/fixtures";

/**
 * The strip where a logo wall would go.
 *
 * Kept from the source design, including the line that makes it work: these
 * are facts about a codebase and a licence, not adoption. The design put that
 * sentence there deliberately and it is the best thing on the page — a strip
 * of numbers in this position reads as social proof unless it says otherwise.
 *
 * The source design's version carried "14 automated tests". That number is not
 * here, and its absence is deliberate: `facts.json` refuses to export a test
 * count, and a test enforces the refusal, because an exact figure is wrong the
 * moment somebody writes one more test.
 */

export function Facts() {
  const cells = [
    ["Runtime-neutral", "MCP, A2A, or a JSONL bridge"],
    ["Python 3.11+", "standard library only"],
    ["Zero runtime dependencies", "nothing to audit but the code"],
    ["Apache 2.0", "and the fixtures are synthetic"],
    [`${facts.scenarios} scenarios`, "each one able to fail"],
    [`${facts.subjects} subjects`, `${facts.subjects_by_expected_verdict.FAIL} written to break them`],
  ];

  return (
    <section aria-label="Project facts" className="border-y border-b-line bg-b-raised">
      <div className="b-measure py-9">
        <ul className="b-cells grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6">
          {cells.map(([head, note]) => (
            <li key={head} className="px-4 py-3 first:pl-0">
              <p className="font-b-mono text-[13px] font-medium text-b-text">{head}</p>
              <p className="mt-1 text-[12px] leading-snug text-b-faint">{note}</p>
            </li>
          ))}
        </ul>
        <p className="mt-6 text-[11.5px] text-b-faint">
          Project facts about the codebase and its licence. Not adoption metrics.
        </p>
      </div>
    </section>
  );
}
