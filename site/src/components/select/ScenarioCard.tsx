import type { ScenarioSummary } from "@/data/types";
import { scenarioCopy } from "@/data/copy";

/**
 * One scenario, as a question rather than a name.
 *
 * The failure line is not optional. A card that cannot state what would count
 * as failing is describing a check nobody has shown can fail, and this project
 * shipped exactly that once — an assertion on `after.mail.sent` that policy
 * made true whatever the subject did.
 */

interface Props {
  scenario: ScenarioSummary;
  selected: boolean;
  disabled?: boolean;
  /**
   * Availability, rendered inside the card.
   *
   * It used to sit in a sibling element after the card. The card is `h-full`,
   * so it already filled the grid row — anything after it overflowed into the
   * row below and printed on top of the next card.
   */
  note?: string;
  onPick: () => void;
}

export function ScenarioCard({ scenario, selected, disabled, note, onPick }: Props) {
  const copy = scenarioCopy[scenario.slug];

  return (
    <button
      type="button"
      onClick={onPick}
      disabled={disabled}
      aria-pressed={selected}
      className={`flex h-full flex-col rounded-card border bg-surface p-5 text-left transition-colors ${
        selected ? "border-accent ring-1 ring-accent" : "border-line hover:border-line-strong"
      } ${disabled ? "cursor-not-allowed opacity-50" : ""}`}
    >
      <div className="mb-3 flex items-center gap-2">
        <span className="rounded-[3px] border border-line bg-sunken px-1.5 py-0.5 font-mono text-[10px] text-text-muted">
          graded on {scenario.graded_on}
        </span>
        {!copy && (
          <span className="font-mono text-[10px] text-text-faint">{scenario.slug}</span>
        )}
      </div>

      <h3 className="mb-2 text-[17px] leading-snug font-medium text-balance">
        {copy?.question ?? scenario.name}
      </h3>

      <dl className="mb-4 flex-1 text-[13px] leading-relaxed">
        <dt className="mb-1 font-mono text-[10px] uppercase tracking-[0.09em] text-text-faint">
          What it tests
        </dt>
        <dd className="text-text-muted text-pretty">{copy?.tests ?? scenario.description}</dd>
      </dl>

      <dl className="border-t border-line pt-3 text-[12.5px] leading-relaxed">
        <dt className="mb-1 font-mono text-[10px] uppercase tracking-[0.09em] text-text-faint">
          Fails when
        </dt>
        <dd className="mb-3 text-text-muted text-pretty">
          {copy?.fails ?? "See the scenario's assertions."}
        </dd>
        <dd className="font-mono text-[11px] text-text-faint">
          {scenario.assertions.length} assertions · {scenario.tools.length} tools
        </dd>
      </dl>

      {note && (
        <p className="mt-3 border-t border-line pt-3 font-mono text-[10.5px] leading-relaxed text-text-faint text-pretty">
          {note}
        </p>
      )}
    </button>
  );
}
