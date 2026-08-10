import { facts } from "@/data/fixtures";
import { Band } from "../components/Band";

/**
 * What is worth building on top.
 *
 * Kept from the source design, with the seven contribution slots replaced by
 * the five this repository can actually take today — each one a thing the code
 * already has a seam for. A scenario pack is a worked example in the tree; an
 * adapter is a class with a documented interface; a subject is a file in
 * examples/subjects with an entry in the manifest. None of these is aspiration.
 */

const REPO = "https://github.com/RealMaxPower/project-beacon";

const WAYS = [
  ["01", "Scenarios", "A scenario is JSON plus a synthetic service. There is a worked pack in the tree, with a test that runs it from outside the repository."],
  ["02", "Adversarial subjects", "A subject that misbehaves in a specific way, with the verdict it should earn recorded beside it. A check that never fails measures nothing."],
  ["03", "Protocol adapters", "Beacon speaks MCP, A2A and a JSONL bridge. Another protocol is another adapter, not a fork."],
  ["04", "Conformance surveys", "Beacon's own clients, run against the official SDKs. The last one found seven defects in the client."],
  ["05", "Assertion types", "The grading vocabulary is small on purpose. A new comparison is a new type, declared in the scenario rather than coded into a run."],
] as const;

export function Contribute() {
  return (
    <Band
      id="contribute"
      eyebrow="07 — Open source"
      heading="A lab is only useful if you can read what it did."
      lede={
        <>
          Everything here is Apache 2.0, has no runtime dependencies, and ships{" "}
          {facts.subjects} adversarial subjects whose recorded verdicts are checked against the
          code on every run. The point is that you can disagree with it.
        </>
      }
    >
      <ul className="b-cells grid sm:grid-cols-2 xl:grid-cols-3">
        {WAYS.map(([n, head, body]) => (
          <li key={n} className="px-5 py-6">
            <p className="b-eyebrow text-b-src">{n}</p>
            <p className="mt-3 font-b-display text-[16px] font-semibold tracking-[-0.015em]">
              {head}
            </p>
            <p className="mt-2 text-[13px] leading-relaxed text-b-muted">{body}</p>
          </li>
        ))}
      </ul>

      <div className="mt-10 rounded-xl border border-b-line bg-b-raised p-6">
        <p className="text-[15px] leading-relaxed">
          The scaffold generates a scenario <em>and</em> a subject written to break it, because a
          scenario nobody has watched fail is a claim rather than a check.
        </p>
        <div className="mt-5 flex flex-wrap gap-3">
          <a
            href={`${REPO}/blob/main/CONTRIBUTING.md`}
            rel="noreferrer"
            className="hit-target inline-flex items-center rounded-md bg-b-src px-4 text-[13.5px] font-medium text-b-on-accent"
          >
            Contributing
          </a>
          <a
            href={`${REPO}/tree/main/examples/scenario-pack`}
            rel="noreferrer"
            className="hit-target inline-flex items-center rounded-md border border-b-line-strong px-4 text-[13.5px] font-medium"
          >
            The worked pack
          </a>
        </div>
      </div>
    </Band>
  );
}
