import type { Fixture } from "@/data/types";
import { VerdictBadge } from "@/components/verdict/VerdictBadge";

/**
 * One agent you can run, with its expected verdict shown up front.
 *
 * Saying in advance what each demo will do is deliberate. The playground is
 * replaying recorded runs, and pretending otherwise — building suspense about
 * an outcome already on disk — would be the one dishonest thing on a site
 * whose subject is honest measurement.
 *
 * Two of the four misbehave on purpose. `examples/subjects/` holds hundreds of
 * them for exactly this reason: watching a check fail is the only proof it
 * measures anything.
 */

interface Props {
  fixture: Fixture;
  selected: boolean;
  onPick: () => void;
}

export function SubjectCard({ fixture, selected, onPick }: Props) {
  return (
    <button
      type="button"
      onClick={onPick}
      aria-pressed={selected}
      className={`flex h-full flex-col rounded-card border bg-surface p-5 text-left transition-colors ${
        selected ? "border-accent ring-1 ring-accent" : "border-line hover:border-line-strong"
      }`}
    >
      <div className="mb-3 flex items-center justify-between gap-3">
        <VerdictBadge state={fixture.expected} size="sm" />
        {/*
         * The interface, not just the number. "level 1" says nothing to
         * someone deciding whether this demo resembles their own setup;
         * "level 1 · MCP" does.
         */}
        <span className="font-mono text-[10px] text-text-faint">
          level {fixture.integration_level} ·{" "}
          {
            { 1: "MCP", 2: "A2A", 3: "JSONL bridge", 4: "in-process" }[
              fixture.integration_level
            ]
          }
        </span>
      </div>

      <h3 className="mb-2 text-[15px] leading-snug font-medium">{fixture.label}</h3>

      <p className="mb-3 flex-1 text-[13px] leading-relaxed text-text-muted text-pretty">
        {fixture.behavior}
      </p>

      <p className="border-t border-line pt-3 text-[12.5px] leading-relaxed text-text-faint text-pretty">
        {fixture.shows}
      </p>

      {fixture.subject && (
        <p className="mt-2 font-mono text-[10.5px] break-all text-text-faint">
          examples/subjects/{fixture.subject}.py
        </p>
      )}
    </button>
  );
}
