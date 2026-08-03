/**
 * Swap the plain-English layer for what Beacon actually wrote.
 *
 * Default off, because the playground is for someone deciding whether to trust
 * an agent. But it has to exist: an engineer will not believe a friendly
 * summary they cannot check, and the JSON behind these screens is real, so
 * there is nothing to hide behind the toggle.
 */

interface Props {
  on: boolean;
  onChange: (next: boolean) => void;
}

export function ExpertToggle({ on, onChange }: Props) {
  return (
    <button
      type="button"
      onClick={() => onChange(!on)}
      aria-pressed={on}
      className={`hit-target inline-flex items-center gap-2.5 rounded-row border px-3 py-2 font-mono text-[11.5px] transition-colors ${
        on ? "border-accent bg-sunken text-text" : "border-line text-text-muted hover:border-line-strong"
      }`}
    >
      <span
        aria-hidden="true"
        className={`inline-block h-2 w-2 rounded-full ${on ? "bg-accent" : "border border-line-strong"}`}
      />
      Expert mode
    </button>
  );
}
