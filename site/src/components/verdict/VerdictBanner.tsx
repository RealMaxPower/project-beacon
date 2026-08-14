import type { Evidence } from "@/data/types";
import { durationMs } from "@/data/fixtures";
import { assertionCopy } from "@/data/copy";
import { VerdictBadge } from "./VerdictBadge";

/**
 * The result, what produced it, and the facts that qualify it.
 *
 * Duration is derived from the bundle rather than passed in. Anything typed
 * twice eventually disagrees with itself, and a site arguing that displayed
 * evidence must be checkable against its source cannot afford a headline
 * number that drifted from the run underneath it.
 *
 * The banner names the check that decided the verdict. "At least one assertion
 * did not hold" over a list of nine rows, one of which carries a small red
 * cross, makes the reader do the search — and the row that matters was eighth
 * of nine, drawn exactly like the seven that passed.
 */

interface Props {
  evidence: Evidence;
  /**
   * Open that assertion's row in the list below.
   *
   * The banner says which check decided the verdict; the row says what it
   * compared. Naming it without offering the detail sends the reader back to
   * scanning the list for the id they were just shown.
   */
  onInspect?: (assertionId: string) => void;
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

export function VerdictBanner({ evidence, onInspect }: Props) {
  /*
   * `measured: false` outranks `passed`, here as in `AssertionRow`.
   *
   * This counted unevaluated assertions as `passed === null`, which the
   * bundles never write: Beacon records `passed: false, measured: false` and
   * resolves the run INCOMPLETE on the strength of the second field. So an
   * INCOMPLETE run printed "0/3 passed" with no note that nothing had been
   * measured — a failure rate for checks that never ran, on the banner
   * announcing that Beacon could not tell.
   */
  const measured = evidence.assertions.filter((a) => a.measured !== false);
  const unmeasured = evidence.assertions.filter((a) => a.measured === false);
  const passed = measured.filter((a) => a.passed === true).length;
  const seconds = (durationMs(evidence) / 1000).toFixed(2);

  /*
   * The checks that decided this verdict: the ones that failed, or — where
   * nothing could be measured — the ones nobody could run.
   */
  const deciding = evidence.result === "FAIL" ? measured.filter((a) => a.passed === false) : unmeasured;

  const decidingLabel =
    evidence.result === "FAIL"
      ? `The check${deciding.length === 1 ? "" : "s"} that did not hold`
      : `What could not be measured`;

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

      {deciding.length > 0 && (
        <div className="mb-5 rounded-card border border-current/25 bg-bg/60 p-4">
          <p className="mb-2.5 font-mono text-[10.5px] font-medium uppercase tracking-[0.1em] text-text-faint">
            {decidingLabel}
          </p>
          <ul className="flex flex-col gap-2">
            {deciding.map((assertion) => {
              const { sentence } = assertionCopy(evidence.scenario.id, assertion);
              return (
                <li key={assertion.id}>
                  {/*
                   * The sentence reads as the thing the check asserts — "It
                   * never tried to send mail." This comment used to argue that
                   * the heading above disambiguates it, and that was wrong:
                   * the heading is eleven words away in smaller type, the
                   * cross is right beside the sentence, and an external
                   * reviewer read it as a statement that the agent had not
                   * done the thing the cross says it did. A failed row states
                   * the requirement instead. The INCOMPLETE list is left
                   * alone: its mark is a circle under "What could not be
                   * measured", which contradicts nothing.
                   */}
                  <button
                    type="button"
                    onClick={() => onInspect?.(assertion.id)}
                    className="hit-target flex w-full items-start gap-3 rounded-row px-2 py-1.5 text-left hover:bg-bg"
                  >
                    <span
                      aria-hidden="true"
                      className={`mt-0.5 flex-none font-mono text-sm ${
                        evidence.result === "FAIL" ? "text-fail" : "text-inc"
                      }`}
                    >
                      {evidence.result === "FAIL" ? "✗" : "○"}
                    </span>
                    <span className="flex-1">
                      <span className="block text-[14.5px] leading-snug text-text text-pretty">
                        {evidence.result === "FAIL" ? `Required: ${sentence}` : sentence}
                      </span>
                      <span className="mt-1 block font-mono text-[11px] text-text-faint">
                        {assertion.id} · see what it compared
                      </span>
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      )}

      <dl className="grid grid-cols-2 gap-x-6 gap-y-3 font-mono text-xs sm:grid-cols-4">
        <div>
          <dt className="mb-1 on-tint">Assertions</dt>
          <dd className="text-text">
            {passed}/{measured.length} passed
            {unmeasured.length > 0 && ` · ${unmeasured.length} not measured`}
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
          An unsigned SHA-256 over the bundle. <code>beacon verify</code> recomputes it, so an edit
          made after the run is detectable. It is not a signature: anyone holding the file can
          regenerate both, so it says nothing about where the bundle came from.
        </p>
      </div>
    </section>
  );
}
