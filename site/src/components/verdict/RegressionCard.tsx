import { VerdictBadge } from "./VerdictBadge";

/**
 * Worse than it was, which is a different question from failing.
 *
 * Both rates are always rendered together: a single number is not a
 * regression. Comparison is by pass *rate* rather than by verdict, because a
 * subject that fails a quarter of the time still passes three single-run
 * comparisons in four.
 */

interface Props {
  assertionId: string;
  baselineRate: number;
  currentRate: number;
  sample: number;
  recordedAt: string;
  /**
   * Whether the assertion was evaluated at all.
   *
   * A rate of `0` in a baseline has two meanings, and only one of them is a
   * number. If the check never ran — it read a path the reply did not contain —
   * then there is no pass rate to compare, and printing `0%` publishes a
   * measurement nobody took.
   */
  evaluated?: boolean;
}

function percent(rate: number): string {
  return `${Math.round(rate * 100)}%`;
}

export function RegressionCard({
  assertionId,
  baselineRate,
  currentRate,
  sample,
  recordedAt,
  evaluated = true,
}: Props) {
  const worse = evaluated && currentRate < baselineRate;

  if (!evaluated) {
    return (
      <article className="rounded-card border border-inc/40 border-l-[3px] border-l-inc border-dashed bg-surface p-5">
        <div className="mb-3 flex flex-wrap items-center gap-3">
          <VerdictBadge state="INCOMPLETE" size="sm" />
          <span className="font-mono text-xs font-medium">{assertionId}</span>
        </div>
        <p className="max-w-[64ch] text-[14.5px] leading-relaxed text-text-muted text-pretty">
          There is no pass rate to compare. This assertion was never evaluated in the recorded
          sample — it reads a field the replies did not contain, so across all {sample} runs
          there was nothing to compare it against. A regression is a drop from one measurement
          to another, and this has neither.
        </p>
        <p className="mt-4 border-t border-line pt-4 font-mono text-[11px] text-text-faint">
          recorded {recordedAt.slice(0, 10)}
        </p>
      </article>
    );
  }

  return (
    <article
      className={`rounded-card border border-line border-l-[3px] bg-surface p-5 ${
        worse ? "border-l-fail" : "border-l-line-strong"
      }`}
    >
      <div className="mb-3 flex flex-wrap items-center gap-3">
        {/* The badge follows the finding. A red REGRESSION chip above the words
            "No regression" is the card arguing with itself. */}
        {worse ? (
          <VerdictBadge
            state="REGRESSION"
            detail={`${percent(baselineRate)} → ${percent(currentRate)}`}
          />
        ) : (
          <span className="inline-flex items-center rounded-[3px] border border-line-strong px-2 py-1 font-mono text-[11px] font-medium tracking-[0.06em] text-text-muted">
            NO CHANGE {percent(baselineRate)} → {percent(currentRate)}
          </span>
        )}
        <span className="font-mono text-xs font-medium">{assertionId}</span>
      </div>

      <p className="mb-4 max-w-[64ch] text-[14.5px] leading-relaxed text-text-muted text-pretty">
        {worse ? (
          <>
            Passed {percent(baselineRate)} of baseline runs, {percent(currentRate)} now, over{" "}
            {sample} run{sample === 1 ? "" : "s"}. A drop counts as a regression only when the
            sample rules out chance, so a flaky subject does not fail the build at random.
          </>
        ) : (
          <>
            No regression: {percent(currentRate)} now against {percent(baselineRate)} recorded,
            over {sample} run{sample === 1 ? "" : "s"}.
          </>
        )}
      </p>

      <dl className="grid grid-cols-3 gap-4 border-t border-line pt-4 font-mono text-[11px]">
        <div>
          <dt className="mb-1 text-text-faint">Baseline</dt>
          <dd>{percent(baselineRate)}</dd>
        </div>
        <div>
          <dt className="mb-1 text-text-faint">Now</dt>
          <dd className={worse ? "text-fail" : undefined}>{percent(currentRate)}</dd>
        </div>
        <div>
          <dt className="mb-1 text-text-faint">Recorded</dt>
          <dd>{recordedAt.slice(0, 10)}</dd>
        </div>
      </dl>
    </article>
  );
}
