/**
 * How often one assertion held.
 *
 * Bar plus fraction plus percentage, never a bar alone — the bar is the
 * quickest read and the least precise one, and this is a screen about not
 * trusting quick reads.
 *
 * The row leads with the sentence, not the id. Three columns of `label · bar ·
 * fraction` put `result-matches-the-contract` in a 208px box that truncated it,
 * so the reader got a hyphenated identifier clipped mid-word and a coloured bar
 * with no idea what it measured — while `copy.ts` already held a sentence for
 * every one of these ids, which the verdict screen was using and this one was
 * not.
 *
 * A rate of zero is drawn as a rate of zero. Where an assertion was never
 * evaluated rather than failed, `evaluated` is false and the row says so,
 * because publishing 0% for something nobody measured is the exact mistake the
 * scenario behind this screen exists to catch.
 */

interface Props {
  /** The check in a sentence. What the reader is here to understand. */
  label: string;
  /** The assertion id, shown small beneath — the handle, not the heading. */
  id?: string;
  rate: number;
  total: number;
  evaluated?: boolean;
}

export function PassRateBar({ label, id, rate, total, evaluated = true }: Props) {
  const passed = Math.round(rate * total);
  const percent = Math.round(rate * 100);
  const tone = !evaluated ? "bg-inc" : rate === 1 ? "bg-pass" : "bg-fail";
  const figure = evaluated ? `${passed}/${total} · ${percent}%` : `measured 0/${total}`;

  return (
    <div className="border-b border-line py-3 last:border-b-0">
      <div className="mb-2 flex items-baseline justify-between gap-4">
        <p className="min-w-0 text-[13.5px] leading-snug text-pretty">{label}</p>
        <p
          className={`flex-none font-mono text-xs ${
            evaluated && rate < 1 ? "font-medium text-fail" : "text-text-muted"
          } ${!evaluated ? "font-medium text-inc" : ""}`}
        >
          {figure}
        </p>
      </div>

      <div className="flex items-center gap-3">
        {/*
         * No track at all where nothing was measured.
         *
         * This drew a full-width amber bar for `entities-grounded` beside the
         * words "measured 0/12" — a bar at 100% for a check that never ran,
         * which is the fabricated measurement this scenario exists to catch.
         * An empty trough is no better: beside a filled one it reads as zero
         * progress rather than as no measurement. The space is held so the
         * rows stay on a grid; the absence is the point.
         */}
        {evaluated ? (
          <span className="h-2 flex-1 overflow-hidden rounded-full bg-sunken">
            {percent > 0 && (
              <span className={`block h-full ${tone}`} style={{ width: `${percent}%` }} />
            )}
          </span>
        ) : (
          <span className="h-2 flex-1" aria-hidden="true" />
        )}
        {id && (
          <span className="max-w-[45%] flex-none truncate font-mono text-[10.5px] text-text-faint" title={id}>
            {id}
          </span>
        )}
      </div>
    </div>
  );
}
