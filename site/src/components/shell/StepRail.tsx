import { steps, type StepKey } from "@/data/copy";

/**
 * Where you are in a run, and what is still ahead.
 *
 * Later steps stay reachable rather than being disabled — clicking one shows
 * an EmptyState explaining what it needs, which teaches the shape of a run
 * better than a greyed-out control does.
 */

interface Props {
  current: StepKey;
  reached: Set<StepKey>;
  onGo: (step: StepKey) => void;
}

export function StepRail({ current, reached, onGo }: Props) {
  return (
    <nav aria-label="Run steps" className="flex flex-wrap gap-1">
      {steps.map((step, index) => {
        const active = step.key === current;
        const done = reached.has(step.key) && !active;

        return (
          <button
            key={step.key}
            type="button"
            onClick={() => onGo(step.key)}
            aria-current={active ? "step" : undefined}
            className={`hit-target inline-flex items-center gap-2 rounded-row px-3 py-2 font-mono text-[11.5px] transition-colors ${
              active
                ? "bg-text text-bg"
                : done
                  ? "text-text hover:bg-sunken"
                  : "text-text-faint hover:bg-sunken"
            }`}
          >
            <span aria-hidden="true" className="tabular-nums opacity-60">
              {String(index + 1).padStart(2, "0")}
            </span>
            {step.label}
          </button>
        );
      })}
    </nav>
  );
}
