import { ScenarioCard } from "@/components/select/ScenarioCard";
import { scenarios } from "@/data/fixtures";
import { scenarioCopy } from "@/data/copy";

/**
 * Step one: what should the agent be asked to do.
 *
 * Every count here is read from `scenarios/` and from the fixtures actually
 * shipped, never typed, so the screen cannot disagree with the repository.
 * That matters more than it sounds: the sentence used to say "every one of
 * them has recorded runs here" while the grid below it dimmed seventy-six
 * cards reading "no recorded run yet".
 *
 * Only scenarios with a recorded run are selectable; the rest are still shown,
 * because hiding most of what ships would misrepresent the project in the
 * other direction.
 */

interface Props {
  selected: string | null;
  runnable: Set<string>;
  onPick: (id: string) => void;
}

export function PickScenario({ selected, runnable, onPick }: Props) {
  return (
    <section>
      <header className="mb-6">
        <h2 className="mb-2 text-2xl leading-tight font-medium tracking-[-0.025em] text-balance">
          What should the agent try?
        </h2>
        <p className="max-w-[64ch] text-[15px] leading-relaxed text-text-muted text-pretty">
          Each of these is a synthetic world with a job in it. {scenarios.length} ship with
          Beacon — {scenarios.filter((s) => s.graded_on === "service state").length} graded on
          what changed in a simulated service, {scenarios.filter((s) => s.graded_on === "the answer").length}{" "}
          on what came back. {runnable.size} of them have recorded runs here, each with a
          subject that satisfies it and one that breaks it; the rest are shown because
          they ship, and you can run any of them yourself from a clone.
        </p>
      </header>

      {/*
       * The cards are `h-full` so every one in a row is the same height. That
       * only holds while nothing is rendered beside them inside the grid cell —
       * a sibling paragraph added its own height on top of a card that already
       * filled the row, and printed over the row beneath.
       */}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {scenarios.map((scenario) => (
          <ScenarioCard
            key={scenario.slug}
            scenario={scenario}
            selected={selected === scenario.id}
            disabled={!runnable.has(scenario.id)}
            note={runnable.has(scenario.id) ? undefined : "no recorded run yet"}
            onPick={() => onPick(scenario.id)}
          />
        ))}
      </div>

      {scenarios.some((s) => !scenarioCopy[s.slug]) && (
        <p className="mt-6 font-mono text-[11px] text-text-faint">
          A scenario without a plain-English question falls back to its own name and
          description, so a new one appears here without being edited in.
        </p>
      )}
    </section>
  );
}
