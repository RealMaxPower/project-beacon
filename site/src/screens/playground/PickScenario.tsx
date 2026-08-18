import { useMemo } from "react";
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
 * Fixing that sentence left a worse problem behind. The seven scenarios you
 * can actually replay were scattered through seventy-six you cannot, in
 * identical cards, so the first screen of the playground was mostly dead ends
 * and the working ones took scrolling to find. Honest and unusable is not an
 * improvement on dishonest.
 *
 * So the replayable ones come first and alone, as cards. The rest are still
 * here — hiding most of what ships would misrepresent the project in the other
 * direction — but as a compact list behind a disclosure that says how many
 * there are. A summary naming the count is not hiding; a wall of identical
 * disabled cards was not showing.
 */

interface Props {
  selected: string | null;
  runnable: Set<string>;
  onPick: (id: string) => void;
}

export function PickScenario({ selected, runnable, onPick }: Props) {
  const [replayable, shipsOnly] = useMemo(() => {
    const yes = scenarios.filter((s) => runnable.has(s.id));
    const no = scenarios.filter((s) => !runnable.has(s.id));
    return [yes, no];
  }, [runnable]);

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
          on what came back. {replayable.length} of them have recorded runs you can replay
          here, each with a subject that satisfies it and one that breaks it. Those are the
          ones below.
        </p>
      </header>

      {/*
       * The cards are `h-full` so every one in a row is the same height. That
       * only holds while nothing is rendered beside them inside the grid cell —
       * a sibling paragraph added its own height on top of a card that already
       * filled the row, and printed over the row beneath.
       */}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {replayable.map((scenario) => (
          <ScenarioCard
            key={scenario.slug}
            scenario={scenario}
            href={`/playground/${scenario.id}`}
            selected={selected === scenario.id}
            onPick={() => onPick(scenario.id)}
          />
        ))}
      </div>

      {shipsOnly.length > 0 && (
        <details className="mt-8 rounded-card border border-line bg-surface">
          <summary className="cursor-pointer list-none px-5 py-4 text-[14px] leading-relaxed text-text-muted">
            <span className="font-medium text-text">
              {shipsOnly.length} more scenarios ship with Beacon
            </span>{" "}
            — no recorded run here, so they cannot be replayed in the browser. Each has a page
            of its own describing what it asks and what it checks.
          </summary>

          <ul className="grid gap-x-6 gap-y-2 border-t border-line px-5 py-4 sm:grid-cols-2 xl:grid-cols-3">
            {/*
              * Links, and real ones — no handler, no `preventDefault`.
              *
              * The rule deciding which kind a scenario gets: in place when the
              * flow continues on this page, a full navigation when the
              * destination is a different page. A card above selects something
              * with five more steps behind it here; one of these goes to a page
              * that has no step two, so intercepting the click would only
              * simulate the navigation it was already going to make.
              *
              * These were plain text until now, which is the reason seventy-six
              * of the eighty-three scenario pages had no clickable route to
              * them from anywhere on the site.
              */}
            {shipsOnly.map((scenario) => (
              <li key={scenario.slug} className="text-[13px] leading-snug">
                <a
                  href={`/playground/${scenario.id}`}
                  className="-mx-2 block rounded-row px-2 py-1.5 no-underline hover:bg-sunken"
                >
                  <span className="text-text-muted text-pretty">{scenario.name}</span>
                  <span className="mt-0.5 block font-mono text-[11px] text-text-faint">
                    {scenario.slug} · {scenario.assertions.length} checks
                  </span>
                </a>
              </li>
            ))}
          </ul>
        </details>
      )}

      {scenarios.some((s) => !scenarioCopy[s.slug]) && (
        <p className="mt-6 font-mono text-[11px] text-text-faint">
          A scenario without a plain-English question falls back to its own name and
          description, so a new one appears here without being edited in.
        </p>
      )}
    </section>
  );
}
