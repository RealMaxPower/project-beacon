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

  /*
   * Counted the way the bundle writes it: `measured` decides whether a check
   * ran, and `passed` is only meaningful once it did.
   */
  const measured = evidence.assertions.filter((a) => a.measured !== false);
  const held = measured.filter((a) => a.passed === true).length;
  const unmeasured = evidence.assertions.length - measured.length;

  return (
    <section className="flex flex-col gap-5">
      <VerdictBanner evidence={evidence} onInspect={setOpen} />

      <div className="overflow-hidden rounded-card border border-line bg-surface">
        {/*
         * A heading that says what the list is, not a label naming its type.
         * "ASSERTIONS" told a reader who already knew the word what they were
         * looking at, and everyone else nothing.
         */}
        <header className="border-b border-line bg-sunken px-5 py-3.5">
          <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
            <h3 className="text-[15px] font-medium">
              {held} of {measured.length} checks held
              {unmeasured > 0 && `, ${unmeasured} could not be run`}
            </h3>
            <span className="font-mono text-[11px] text-text-muted">
              open one to see what it compared
            </span>
          </div>
          <p className="mt-1 max-w-[72ch] text-[13px] leading-relaxed text-text-muted text-pretty">
            Every check this scenario makes, in the order it makes them. Each one is a
            comparison against the recorded run — no model judges any of this.
          </p>
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
