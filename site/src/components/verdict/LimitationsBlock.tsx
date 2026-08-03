/**
 * What this run does not tell you.
 *
 * There is no `onDismiss` prop and no collapsed variant, and that absence is
 * the specification rather than an omission. Limitations ship inside the
 * evidence bundle, so they ship inside every surface that displays one. The
 * items come from `evidence.limitations` — the same strings `beacon/runner.py`
 * writes — never from copy held here.
 */

interface Props {
  items: string[];
}

export function LimitationsBlock({ items }: Props) {
  return (
    <section
      aria-label="Limitations"
      className="rounded-card border border-line bg-sunken p-5"
    >
      <h3 className="mb-3 font-mono text-[10.5px] font-medium uppercase tracking-[0.1em] text-text-faint">
        Limitations
      </h3>
      <ul className="flex flex-col gap-2">
        {items.map((item) => (
          <li key={item} className="flex gap-2.5 text-[13.5px] leading-relaxed text-text-muted">
            <span className="mt-2 h-px w-2.5 flex-none bg-line-strong" aria-hidden="true" />
            <span className="text-pretty">{item}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
