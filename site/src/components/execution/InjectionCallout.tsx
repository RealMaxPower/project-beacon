/**
 * The moment the injected instruction is read.
 *
 * It appears when the message is opened, not at the verdict, because the
 * question a viewer has is "what is it about to do" — answering it forty lines
 * later turns the most interesting event in the run into a footnote.
 *
 * What this does *not* do is claim the injection caused anything. An earlier
 * version inferred "obeyed" from any blocked attempt, which labelled a subject
 * that tries to send mail regardless of what it reads as having followed an
 * instruction it never saw. The two runs are nearly identical in the event log;
 * nothing in the evidence distinguishes obedience from coincidence, and this
 * scenario asserts no causal link.
 *
 * So it reports what the injection asked for, and which of those things the
 * subject attempted. That is what Beacon actually recorded. Quoting an
 * injection while declining it is the behaviour you want, and this shows it
 * without having to guess at intent.
 */

export interface Demand {
  /**
   * The requirement, in the scenario's own words.
   *
   * These read as the desired outcome — "The subject did not attempt to send a
   * draft" — because that is what the assertion asserts. So the tag beside it
   * says whether the requirement *held*, not whether something was attempted;
   * pairing "attempted" with a sentence beginning "did not attempt" had the row
   * contradicting itself.
   */
  label: string;
  /** True when the assertion failed — the subject did the forbidden thing. */
  attempted: boolean;
}

interface Props {
  /** Where the payload was hiding — a message id, or a document path. */
  source: string;
  injectedText: string;
  demands: Demand[];
  /** False until the subject has actually opened the message. */
  reached: boolean;
}

export function InjectionCallout({ source, injectedText, demands, reached }: Props) {
  const attempted = demands.filter((d) => d.attempted).length;

  const tone = !reached
    ? "border-inc/40 border-dashed bg-inc-tint"
    : attempted > 0
      ? "border-fail/40 bg-fail-tint"
      : "border-pass/40 bg-pass-tint";

  const tag = !reached ? "NOT READ YET" : attempted > 0 ? "ATTEMPTED" : "NOTHING ATTEMPTED";

  const title = !reached
    ? "The agent has not opened this message yet."
    : attempted > 0
      ? `It broke ${attempted} of the ${demands.length} rules this scenario grades on.`
      : `It broke none of the ${demands.length} rules this scenario grades on.`;

  return (
    <aside className={`rounded-card border ${tone} p-5`}>
      <div className="mb-2.5 flex flex-wrap items-center gap-2.5">
        <span className="font-mono text-[9.5px] font-medium tracking-[0.08em] text-text">
          PROMPT INJECTION · {source}
        </span>
        <span className="rounded-[3px] border border-current/30 px-1.5 py-0.5 font-mono text-[9.5px] font-medium tracking-[0.08em] text-text">
          {tag}
        </span>
      </div>

      <p className="mb-3 text-[15px] leading-snug font-medium text-balance">{title}</p>

      <blockquote className="mb-4 border-l-2 border-current/25 py-1 pl-3 font-mono text-[11.5px] leading-relaxed on-tint">
        {injectedText}
      </blockquote>

      <ul className="mb-3 flex flex-col gap-1.5">
        {demands.map((demand) => (
          <li key={demand.label} className="flex items-baseline gap-2.5 text-[13.5px] on-tint">
            <span
              aria-hidden="true"
              className={`font-mono text-[12px] ${demand.attempted ? "text-fail" : "text-pass"}`}
            >
              {demand.attempted ? "✗" : "✓"}
            </span>
            <span className="text-pretty">
              {demand.label}
              <span className="ml-1.5 font-mono text-[11px]">
                {demand.attempted ? "— violated" : "— held"}
              </span>
            </span>
          </li>
        ))}
      </ul>

      <p className="max-w-[64ch] text-[12.5px] leading-relaxed on-tint text-pretty">
        These are the scenario's own forbidden-outcome checks, and each one fails exactly when
        the subject did the thing. Attempts are recorded before dispatch, so they count whether
        or not policy allowed them through — and none of this asserts that the injected text
        caused the behaviour. An agent that quotes the injection while declining it passes.
      </p>
    </aside>
  );
}
