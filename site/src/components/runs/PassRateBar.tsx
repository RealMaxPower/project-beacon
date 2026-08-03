/**
 * How often one assertion held.
 *
 * Bar plus fraction plus percentage, never a bar alone — the bar is the
 * quickest read and the least precise one, and this is a screen about not
 * trusting quick reads.
 *
 * A rate of zero is drawn as a rate of zero. Where an assertion was never
 * evaluated rather than failed, `evaluated` is false and the row says so,
 * because publishing 0% for something nobody measured is the exact mistake the
 * scenario behind this screen exists to catch.
 */

interface Props {
  label: string;
  rate: number;
  total: number;
  evaluated?: boolean;
}

export function PassRateBar({ label, rate, total, evaluated = true }: Props) {
  const passed = Math.round(rate * total);
  const percent = Math.round(rate * 100);
  const tone = !evaluated ? "bg-inc" : rate === 1 ? "bg-pass" : "bg-fail";

  return (
    <div className="flex items-center gap-4 border-b border-line py-3 last:border-b-0">
      <span className="w-52 flex-none truncate font-mono text-xs" title={label}>
        {label}
      </span>

      <span className="h-2 flex-1 overflow-hidden rounded-full bg-sunken">
        <span
          className={`block h-full ${tone}`}
          style={{ width: `${Math.max(percent, evaluated ? 0 : 100)}%` }}
        />
      </span>

      <span className="w-32 flex-none text-right font-mono text-xs text-text-muted">
        {evaluated ? `${passed}/${total} · ${percent}%` : `measured 0/${total}`}
      </span>
    </div>
  );
}
