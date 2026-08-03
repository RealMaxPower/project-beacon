import { useState } from "react";
import { VerdictBanner } from "@/components/verdict/VerdictBanner";
import { AssertionRow } from "@/components/verdict/AssertionRow";
import { StateDiff } from "@/components/verdict/StateDiff";
import { ArtifactPanel } from "@/components/verdict/ArtifactPanel";
import { LimitationsBlock } from "@/components/verdict/LimitationsBlock";
import { JsonViewer } from "@/components/shell/JsonViewer";
import { bundleSource } from "@/data/fixtures";
import type { BeaconEvent, Evidence } from "@/data/types";

/**
 * Step five: what it did, and what that does and does not prove.
 *
 * `LimitationsBlock` renders in both modes and has no way to be dismissed.
 * Limitations ship inside the evidence bundle, so they ship inside every
 * surface that shows one.
 */

interface Props {
  evidence: Evidence;
  events: BeaconEvent[];
  expert: boolean;
}

export function Verdict({ evidence, events, expert }: Props) {
  const [open, setOpen] = useState<string | null>(null);

  if (expert) {
    return (
      <section className="flex flex-col gap-4">
        <h2 className="text-2xl leading-tight font-medium tracking-[-0.025em]">
          The evidence bundle, as written.
        </h2>
        <JsonViewer source={bundleSource(evidence.run_id, "evidence.json")} label="evidence.json" maxHeight={560} />
        <LimitationsBlock items={evidence.limitations} />
      </section>
    );
  }

  return (
    <section className="flex flex-col gap-5">
      <VerdictBanner evidence={evidence} />

      <div className="overflow-hidden rounded-card border border-line bg-surface">
        <header className="flex flex-wrap items-baseline justify-between gap-2 border-b border-line bg-sunken px-5 py-3">
          <h3 className="font-mono text-[10.5px] font-medium uppercase tracking-[0.1em] text-text-faint">
            Assertions
          </h3>
          <span className="font-mono text-[11px] text-text-muted">
            open one to see what it compared
          </span>
        </header>

        {evidence.assertions.map((assertion) => (
          <AssertionRow
            key={assertion.id}
            assertion={assertion}
            scenarioId={evidence.scenario.id}
            open={open === assertion.id}
            onToggle={() => setOpen((current) => (current === assertion.id ? null : assertion.id))}
          />
        ))}
      </div>

      <StateDiff evidence={evidence} events={events} />
      <ArtifactPanel evidence={evidence} />
      <LimitationsBlock items={evidence.limitations} />
    </section>
  );
}
