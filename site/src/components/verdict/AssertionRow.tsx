import { useId } from "react";
import type { Assertion } from "@/data/types";
import { assertionCopy } from "@/data/copy";

/**
 * One assertion, in a sentence, opening onto what it compared.
 *
 * An assertion renders as *not evaluated* when `measured` is false, or when
 * `passed` is null. That is not a soft fail: an assertion reading a path the
 * reply never produced was never measured, and reporting it as a failure
 * would publish a rate nobody measured. Beacon writes `passed: false` in that
 * case and carries the real answer in `measured`, so reading `passed` alone
 * gets it exactly backwards.
 *
 * Opened, it shows an aligned expected/actual block rather than two panels of
 * JSON. The values come from the bundle either way — the difference is whether
 * a reader can see what changed between them at a glance, which for a
 * three-element list against a four-element one they cannot when both are
 * pretty-printed objects.
 */

interface Props {
  assertion: Assertion;
  /**
   * Which scenario this assertion belongs to.
   *
   * Needed because assertion ids are unique within a scenario, not across
   * them: `protected-never-read` guards a message in one and a personnel
   * record in another, and the wording has to follow the scenario.
   */
  scenarioId: string;
  open: boolean;
  onToggle: () => void;
}

/** One line per value, so expected and actual sit on a readable grid. */
function lines(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "string") return value;
  if (Array.isArray(value)) {
    if (value.length === 0) return "[] (nothing)";
    const rendered = value.map((item) =>
      typeof item === "string" ? item : JSON.stringify(item),
    );
    // Short lists read better inline; long ones need a line each.
    const inline = rendered.join(", ");
    return inline.length <= 72 ? inline : rendered.map((r) => `  ${r}`).join("\n");
  }
  return JSON.stringify(value, null, 2);
}

export function AssertionRow({ assertion, scenarioId, open, onToggle }: Props) {
  const panelId = useId();
  const { sentence, note } = assertionCopy(scenarioId, assertion);

  /*
   * `measured: false` outranks `passed`.
   *
   * Beacon writes `passed: false, measured: false` when the reply never
   * produced the value an assertion reads — and then resolves the run
   * INCOMPLETE, not FAIL, on the strength of `measured`. Reading `passed`
   * alone would print "failed" beside a check nobody was able to run, which is
   * the fabricated rate this project exists to avoid publishing.
   */
  const measured = assertion.measured !== false;
  const passed = measured ? assertion.passed : null;

  const mark =
    passed === true ? (
      <span className="text-pass" aria-hidden="true">
        ✓
      </span>
    ) : passed === false ? (
      <span className="text-fail" aria-hidden="true">
        ✗
      </span>
    ) : (
      <span className="text-inc" aria-hidden="true">
        ○
      </span>
    );

  const state = passed === true ? "passed" : passed === false ? "failed" : "not evaluated";

  /*
   * The row that did not hold is drawn heavier, not marked with a smaller
   * glyph.
   *
   * Nine rows in one weight, one of them carrying a red cross at 14px, is a
   * list that asks the reader to find the finding. The same argument the
   * timeline makes about a blocked call applies here: the informative row is
   * the one that broke, and rendering it identically to the seven that passed
   * is an interface understating its own result.
   */
  const emphasis =
    passed === false
      ? "border-l-[3px] border-l-fail bg-fail-tint"
      : passed === null
        ? "border-l-[3px] border-l-inc bg-inc-tint"
        : "";

  return (
    <div className={`border-b border-line last:border-b-0 ${emphasis}`}>
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        // Only while the panel exists. `aria-controls` naming an element that
        // is not in the document sends a screen reader somewhere there is
        // nothing to go to; `aria-expanded` alone already says the row opens.
        aria-controls={open ? panelId : undefined}
        // No `hover:bg-sunken` on a tinted row: grey over the verdict colour
        // reads as the row losing its result under the pointer. A deeper wash
        // of the row's own hue instead — and `--fail`/`--inc` are theme-aware,
        // which a literal black or white overlay would not be.
        className={`hit-target flex w-full items-start gap-3 px-5 py-3.5 text-left ${
          passed === false
            ? "hover:bg-fail/10"
            : passed === null
              ? "hover:bg-inc/10"
              : "hover:bg-sunken"
        }`}
      >
        <span className="mt-0.5 flex-none font-mono text-sm">{mark}</span>
        <span className="flex-1">
          <span
            className={`block leading-snug text-pretty ${
              emphasis ? "text-[15px] font-medium" : "text-[14.5px]"
            }`}
          >
            {/*
              A failed check states a requirement, not an outcome.

              The sentences are written for the case that holds — "It never
              tried to delete a document." — which under a ✗ reads as a claim
              that it did not, beside a mark saying it did. A reviewer read it
              exactly that way and was right to. The requirement framing is
              added only where the check broke, so the thirty-odd sentences
              stay written the way they read best everywhere else.
            */}
            {passed === false ? `Required: ${sentence}` : sentence}
          </span>
          {/* `--text-faint` measures 4.40–4.93 on the verdict tints and fails
              AA on two of the three. `.on-tint` is the token for text there. */}
          <span
            className={`mt-1 block font-mono text-[11px] ${emphasis ? "on-tint" : "text-text-faint"}`}
          >
            {assertion.id} · {state}
          </span>
        </span>
        <span
          className={`mt-1 flex-none font-mono text-[11px] ${emphasis ? "on-tint" : "text-text-faint"}`}
          aria-hidden="true"
        >
          {open ? "−" : "+"}
        </span>
      </button>

      {open && (
        <div id={panelId} className="border-t border-line bg-sunken px-5 py-4">
          <pre
            tabIndex={0}
            role="region"
            aria-label="Expected against actual, scrollable"
            className="mb-3 overflow-x-auto font-mono text-[11.5px] leading-relaxed"
          >
            <span className="text-text-faint">expected  </span>
            {lines(assertion.expected)}
            {"\n"}
            <span className={passed === false ? "text-fail" : "text-text-faint"}>
              {"actual    "}
            </span>
            {lines(assertion.actual)}
          </pre>

          {assertion.message && (
            <p className="mb-3 font-mono text-[11.5px] leading-relaxed text-text-muted">
              {assertion.message}
            </p>
          )}

          {note && (
            <p className="border-t border-line pt-3 text-[13px] leading-relaxed text-text-muted text-pretty">
              {note}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
