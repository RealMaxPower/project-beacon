/**
 * A screen with nothing on it yet.
 *
 * Neutral treatment, never amber. Amber is INCOMPLETE, which is a verdict —
 * and "you have not run this" is not a result about an agent. Gated steps in
 * the rail render one of these rather than sample data, so nothing on screen
 * is ever a placeholder pretending to be evidence.
 */

interface Props {
  title: string;
  body: string;
  ctaLabel?: string;
  onCta?: () => void;
  /** Set false on states that are not a results view, to drop the rationale. */
  explain?: boolean;
}

export function EmptyState({ title, body, ctaLabel, onCta, explain = true }: Props) {
  return (
    <div className="rounded-card border border-dashed border-line-strong bg-surface px-6 py-12 text-center">
      <h3 className="mb-2 text-[17px] font-medium text-balance">{title}</h3>
      <p className="mx-auto mb-5 max-w-[52ch] text-[14px] leading-relaxed text-text-muted text-pretty">
        {body}
      </p>
      {ctaLabel && onCta && (
        <button
          type="button"
          onClick={onCta}
          className="hit-target inline-flex items-center rounded-row bg-text px-4 py-2.5 text-[13px] font-medium text-bg"
        >
          {ctaLabel}
        </button>
      )}
      {explain && (
        <p className="mx-auto mt-6 max-w-[56ch] border-t border-line pt-5 text-[12.5px] leading-relaxed text-text-faint text-pretty">
          This screen stays empty on purpose. A results view with nothing behind it is where
          sample data gets mistaken for a finding, so it shows you nothing rather than
          something it did not measure.
        </p>
      )}
    </div>
  );
}
