import type { Evidence } from "@/data/types";
import { durationMs } from "@/data/fixtures";
import { VerdictBadge } from "./VerdictBadge";

/**
 * The result, and the facts that qualify it.
 *
 * Duration is derived from the bundle rather than passed in. Anything typed
 * twice eventually disagrees with itself, and a site arguing that displayed
 * evidence must be checkable against its source cannot afford a headline
 * number that drifted from the run underneath it.
 */

interface Props {
  evidence: Evidence;
}

const headlines = {
  PASS: "Every assertion held.",
  FAIL: "At least one assertion did not hold.",
  INCOMPLETE: "Beacon could not tell whether the work was done.",
} as const;

const subs = {
  PASS: "Evidence for this scenario and this configuration. Not a certificate, and not a claim about anything else it might do.",
  FAIL: "The failure is the useful part: it names which check broke and what it compared.",
  INCOMPLETE:
    "Not an error. The subject never signalled completion, and a disconnect looks identical to a crash — so the honest answer is that this run does not say.",
} as const;

export function VerdictBanner({ evidence }: Props) {
  const passed = evidence.assertions.filter((a) => a.passed === true).length;
  const unevaluated = evidence.assertions.filter((a) => a.passed === null).length;
  const seconds = (durationMs(evidence) / 1000).toFixed(2);

  const tint = {
    PASS: "border-pass/30 bg-pass-tint",
    FAIL: "border-fail/30 bg-fail-tint",
    INCOMPLETE: "border-inc/40 border-dashed bg-inc-tint",
  }[evidence.result];

  return (
    <section className={`rounded-card border ${tint} p-6`}>
      <div className="mb-3 flex flex-wrap items-center gap-3">
        <VerdictBadge state={evidence.result} />
        <span className="font-mono text-[11px] on-tint">
          {evidence.scenario.name}
        </span>
      </div>

      <h2 className="mb-2 text-2xl leading-tight font-medium tracking-[-0.025em] text-balance">
        {headlines[evidence.result]}
      </h2>
      <p className="mb-5 max-w-[62ch] text-[14.5px] leading-relaxed on-tint text-pretty">
        {subs[evidence.result]}
      </p>

      <dl className="grid grid-cols-2 gap-x-6 gap-y-3 font-mono text-xs sm:grid-cols-4">
        <div>
          <dt className="mb-1 on-tint">Assertions</dt>
          <dd className="text-text">
            {passed}/{evidence.assertions.length} passed
            {unevaluated > 0 && ` · ${unevaluated} not evaluated`}
          </dd>
        </div>
        <div>
          <dt className="mb-1 on-tint">Reset</dt>
          <dd className="text-text">{evidence.reset_verified ? "exact" : "not verified"}</dd>
        </div>
        <div>
          <dt className="mb-1 on-tint">Duration</dt>
          <dd className="text-text">{seconds}s</dd>
        </div>
        <div>
          <dt className="mb-1 on-tint">Integration</dt>
          <dd className="text-text">level {evidence.subject.integration_level}</dd>
        </div>
      </dl>

      {/*
       * The digest is stated with what it is, because the alternative is what
       * this project already caught itself doing: the README called evidence
       * "immutable" when nothing enforces that, and a hash printed without
       * qualification invites exactly that reading.
       */}
      <div className="mt-5 border-t border-current/10 pt-4">
        <p className="font-mono text-[11px] break-all on-tint">digest {evidence.digest}</p>
        <p className="mt-1.5 text-[12px] leading-relaxed on-tint text-pretty">
          An unsigned SHA-256 over the bundle. It makes a later edit detectable by anyone who
          recomputes it — nothing here signs it, and no command ships yet that verifies one.
        </p>
      </div>
    </section>
  );
}
