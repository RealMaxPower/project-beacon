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
  /**
   * Where the card goes. Its own page, which is a real document.
   *
   * The card was a `<button>` with a click handler and no destination, so the
   * only address any scenario page had was the one in the sitemap: eighty-two
   * of the eighty-three could not be opened in a new tab, copied, shared, or
   * followed by a crawler, and the disclosure below the grid listed the rest as
   * text with nothing to click at all.
   */
  href: string;
  selected: boolean;
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

export function ScenarioCard({ scenario, href, selected, note, onPick }: Props) {
  const copy = scenarioCopy[scenario.slug];

  return (
    <a
      href={href}
      /*
       * `aria-current`, not `aria-pressed`. `aria-pressed` is defined for
       * toggle buttons; on a link a screen reader either drops it or announces
       * "link, pressed", which is not a state a link can be in. The card also
       * stopped being a toggle the moment it gained a destination — after the
       * click the address bar genuinely reads this href, so "selected" and
       * "points at the page you are on" became the same fact, which is what
       * `aria-current="page"` means. That equivalence only holds because the
       * click writes the URL; it would be a lie on a card that set state alone.
       */
      aria-current={selected ? "page" : undefined}
      onClick={(event) => {
        /*
         * In place, but only for the plain click. A card that calls
         * `preventDefault` unconditionally has silently taken cmd-click away
         * from the reader whose whole reason for cmd-clicking is to open two
         * scenarios side by side and compare them.
         */
        if (
          event.defaultPrevented ||
          event.button !== 0 ||
          event.metaKey ||
          event.ctrlKey ||
          event.shiftKey ||
          event.altKey
        ) {
          return;
        }
        event.preventDefault();
        onPick();
      }}
      className={`flex h-full flex-col rounded-card border bg-surface p-5 text-left no-underline transition-colors ${
        selected ? "border-accent ring-1 ring-accent" : "border-line hover:border-line-strong"
      }`}
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
    </a>
  );
}
