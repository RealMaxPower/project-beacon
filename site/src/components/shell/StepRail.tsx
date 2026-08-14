import { steps, type StepKey } from "@/data/copy";

/**
 * Where you are in a run, and what is still ahead.
 *
 * Later steps stay reachable rather than being disabled — clicking one shows
 * an EmptyState explaining what it needs, which teaches the shape of a run
 * better than a greyed-out control does.
 *
 * The rail alone was six chips of 11.5px monospace, which is a legend rather
 * than a position: at a glance you could see there were six of something, but
 * not which one you were in or how far through. The line above says it in
 * words and the bar below draws it, so neither reading depends on picking the
 * filled chip out of a row.
 */

interface Props {
  current: StepKey;
  reached: Set<StepKey>;
  onGo: (step: StepKey) => void;
}

export function StepRail({ current, reached, onGo }: Props) {
  const index = steps.findIndex((step) => step.key === current);
  const position = index === -1 ? 0 : index;
  const label = steps[position]?.label ?? "";

  return (
    <div className="flex flex-col gap-2.5">
      <p className="font-mono text-[11.5px] text-text-faint">
        Step {position + 1} of {steps.length}
        <span aria-hidden="true"> · </span>
        <span className="text-text">{label}</span>
      </p>

      {/*
       * Progress by steps reached, not by the step showing. Clicking ahead to
       * a screen that then says what it needs is not progress through a run,
       * and drawing it as such would tell a reader they were nearly finished
       * when nothing had been chosen yet.
       */}
      <div
        className="h-[3px] overflow-hidden rounded-full bg-sunken"
        role="presentation"
      >
        <div
          className="h-full bg-text transition-[width] duration-200"
          style={{ width: `${(reached.size / steps.length) * 100}%` }}
        />
      </div>

      {/* No negative margin: it puts the first and last chip 4px outside the
          page gutter, which reads to `tools/visual.mjs` — correctly — as a
          control clipped by an ancestor with no scroll cue. */}
      <nav aria-label="Run steps" className="flex flex-wrap gap-1">
        {steps.map((step, position) => {
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
              {/*
                No `opacity-60`, because there is none to spend.
                
                The numeral inherits the button's colour, and on an inactive
                step that is `--b-faint` — the dimmest token in the palette
                that still clears AA, at 5.98 on dark and 4.98 on light. Sixty
                percent alpha composites those to 2.89 and 2.36; even 75% lands
                at 3.86 and 3.07. The active step has headroom and the inactive
                one has none, so dimming was never available here, only
                unmeasured.
                
                `aria-hidden` does not exempt it: WCAG 1.4.3 is about what a
                low-vision reader can see, and a screen reader skipping it says
                nothing about that. The digits stay distinct from the label by
                being tabular monospace beside a word, which is what they were
                already doing.
              */}
              <span aria-hidden="true" className="tabular-nums">
                {String(position + 1).padStart(2, "0")}
              </span>
              {step.label}
            </button>
          );
        })}
      </nav>
    </div>
  );
}
