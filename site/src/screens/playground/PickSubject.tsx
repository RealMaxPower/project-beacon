import { SubjectCard } from "@/components/select/SubjectCard";
import { fixtures } from "@/data/fixtures";
import type { Fixture } from "@/data/types";

/**
 * Step two: which agent.
 *
 * Every card here is a real file in `examples/subjects/`, and every expected
 * verdict is the one that subject's manifest entry records. The misbehaving one
 * is listed first deliberately — a lab that opens on the agent that behaves is
 * demonstrating the wrong thing.
 */

interface Props {
  scenarioId: string | null;
  selected: string | null;
  onPick: (key: string) => void;
}

export function PickSubject({ scenarioId, selected, onPick }: Props) {
  const available: Fixture[] = fixtures.filter(
    (f) => scenarioId === null || f.scenario === scenarioId,
  );

  return (
    <section>
      <header className="mb-6">
        <h2 className="mb-2 text-2xl leading-tight font-medium tracking-[-0.025em] text-balance">
          Which agent should try it?
        </h2>
        <p className="max-w-[64ch] text-[15px] leading-relaxed text-text-muted text-pretty">
          The expected verdict is on the card before you run it. These are recorded runs, so
          nothing is being hidden from you — and watching a check fail is the only proof it
          measures anything.
        </p>
      </header>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {available.map((fixture) => (
          <SubjectCard
            key={fixture.key}
            fixture={fixture}
            selected={selected === fixture.key}
            onPick={() => onPick(fixture.key)}
          />
        ))}

        <div className="flex h-full flex-col justify-between rounded-card border border-dashed border-line-strong bg-surface p-5">
          <div>
            <h3 className="mb-2 text-[15px] font-medium text-text-muted">Connect your own</h3>
            <p className="text-[13px] leading-relaxed text-text-faint text-pretty">
              Beacon grades an agent over MCP, A2A, or a JSONL bridge of about thirty lines.
              That runs on your machine, not in this browser — the playground only replays
              what was recorded.
            </p>
          </div>
          <p className="mt-4 font-mono text-[10.5px] break-all text-text-faint">
            python3 -m beacon run &lt;scenario&gt; --adapter a2a --agent-url …
          </p>
        </div>
      </div>
    </section>
  );
}
