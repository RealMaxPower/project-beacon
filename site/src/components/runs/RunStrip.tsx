import type { Verdict } from "@/data/types";
import { RunDot } from "./RunDot";

/**
 * Every run, side by side.
 *
 * This is the screen where the argument lands: four passes in a row say
 * nothing that twelve runs cannot contradict. Dots fill sequentially so the
 * shape of the result arrives the way it would if you were watching.
 */

interface Props {
  results: Verdict[];
  /** How many have been revealed so far; the rest render as pending. */
  revealed?: number;
  label?: string;
}

export function RunStrip({ results, revealed = results.length, label }: Props) {
  const done = results.slice(0, revealed);
  const counts = done.reduce<Record<string, number>>((acc, verdict) => {
    acc[verdict] = (acc[verdict] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <div>
      {label && (
        <p className="mb-2.5 font-mono text-[10.5px] uppercase tracking-[0.1em] text-text-faint">
          {label}
        </p>
      )}
      {/* Numbered, so "the third and the ninth disagreed" is a thing a reader
          can say. Twelve unlabelled circles can only be counted. */}
      <div className="flex flex-wrap gap-2" role="list" aria-label={label ?? "Run results"}>
        {results.map((verdict, index) => (
          <span role="listitem" key={index} className="flex flex-col items-center gap-1.5">
            <RunDot state={index < revealed ? verdict : "pending"} index={index} />
            <span aria-hidden="true" className="font-mono text-[10px] text-text-faint">
              {String(index + 1).padStart(2, "0")}
            </span>
          </span>
        ))}
      </div>

      {/*
       * The tally only where there is something to tally. With one verdict
       * across every run it restated the panel's own headline in smaller type
       * — "PASS 10 (100%)" directly under "All 10 runs passed."
       */}
      {Object.keys(counts).length > 1 && (
        <p className="mt-3 font-mono text-xs text-text-muted">
          {Object.entries(counts)
            .sort((a, b) => b[1] - a[1])
            .map(
              ([verdict, count]) =>
                `${verdict} ${count} (${Math.round((count / results.length) * 100)}%)`,
            )
            .join(" · ")}
        </p>
      )}
    </div>
  );
}
