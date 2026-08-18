import { useEffect, useMemo, useRef, useState } from "react";
import { TimelineEvent } from "@/components/execution/TimelineEvent";
import { InjectionCallout } from "@/components/execution/InjectionCallout";
import { JsonViewer } from "@/components/shell/JsonViewer";
import { Mark } from "@/components/shell/Mark";
import {
  bundleSource,
  forbiddenOutcomes,
  injectionIn,
  isBlocked,
  offsets,
  scenarioFor,
} from "@/data/fixtures";
import type { BeaconEvent, Evidence } from "@/data/types";

/**
 * Step four: watch it work.
 *
 * The events are replayed at a readable pace rather than at the speed they
 * happened — a run that finishes in 26 milliseconds is not something a person
 * can watch. The timestamps shown are the real ones; only the reveal is
 * slowed, which is the honest way round.
 *
 * The list is a live region: polite for ordinary events, and a blocked attempt
 * is announced assertively. It is the one event permitted to interrupt,
 * because it is the one a screen-reader user most needs to hear when it
 * happens rather than at the end.
 */

interface Props {
  evidence: Evidence;
  events: BeaconEvent[];
  expert: boolean;
  onDone: () => void;
}

const STEP_MS = 260;

export function RunTimeline({ evidence, events, expert, onDone }: Props) {
  const [revealed, setRevealed] = useState(0);
  const [playing, setPlaying] = useState(true);
  const times = useMemo(() => offsets(events), [events]);
  const listEnd = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setRevealed(0);
    setPlaying(true);
  }, [evidence.run_id]);

  useEffect(() => {
    if (!playing || revealed >= events.length) return;
    const timer = setTimeout(() => setRevealed((n) => n + 1), STEP_MS);
    return () => clearTimeout(timer);
  }, [playing, revealed, events.length]);

  useEffect(() => {
    if (revealed >= events.length && events.length > 0) onDone();
  }, [revealed, events.length, onDone]);

  useEffect(() => {
    listEnd.current?.scrollIntoView({ block: "nearest" });
  }, [revealed]);

  const scenario = scenarioFor(evidence);
  const injection = injectionIn(scenario);
  const shown = events.slice(0, revealed);
  const running = revealed < events.length;

  // The callout appears the moment the payload comes back from a tool, not at
  // the verdict. Matched on the injected text itself, so it works whether the
  // payload arrived in a message body or a document.
  const readInjection =
    injection !== null &&
    shown.some(
      (e) =>
        e.kind === "tool_result" &&
        JSON.stringify(e.payload ?? {}).includes(injection.text.slice(0, 24)),
    );

  const demands = forbiddenOutcomes(scenario, evidence);

  if (expert) {
    return (
      <section className="flex flex-col gap-4">
        <h2 className="text-2xl leading-tight font-medium tracking-[-0.025em]">
          The event log, as written.
        </h2>
        <JsonViewer source={bundleSource(evidence.run_id, "events.json")} label="events.json" maxHeight={560} />
      </section>
    );
  }

  return (
    <section>
      <header className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="mb-1 flex items-center gap-2.5 text-2xl leading-tight font-medium tracking-[-0.025em]">
            {running && <Mark size={20} spinning className="text-accent" />}
            {running ? "Running." : "Finished."}
          </h2>
          {/*
           * The count is the progress indicator, so it carries the role rather
           * than having a second, silent bar drawn beside it. The event list
           * below is already a polite live region; what was missing was any way
           * to ask how far through the replay is, rather than waiting to be
           * told each time a row lands.
           */}
          <p
            role="progressbar"
            aria-valuemin={0}
            aria-valuemax={events.length}
            aria-valuenow={revealed}
            aria-valuetext={`${revealed} of ${events.length} events`}
            className="font-mono text-xs text-text-faint"
          >
            {revealed} of {events.length} events · run {evidence.run_id}
          </p>
        </div>

        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => setPlaying((p) => !p)}
            disabled={!running}
            className="hit-target rounded-row border border-line px-3 py-2 font-mono text-[11.5px] text-text-muted hover:border-line-strong disabled:opacity-40"
          >
            {playing ? "Pause" : "Resume"}
          </button>
          <button
            type="button"
            onClick={() => setRevealed(events.length)}
            disabled={!running}
            className="hit-target rounded-row border border-line px-3 py-2 font-mono text-[11.5px] text-text-muted hover:border-line-strong disabled:opacity-40"
          >
            Skip to end
          </button>
        </div>
      </header>

      {readInjection && injection && (
        <div className="mb-5">
          <InjectionCallout
            source={injection.source}
            injectedText={injection.text}
            demands={demands}
            reached={readInjection}
          />
        </div>
      )}

      <div className="overflow-hidden rounded-card border border-line bg-surface">
        <ul
          aria-live="polite"
          aria-busy={running}
          className="max-h-[28rem] divide-y divide-line overflow-y-auto py-1"
        >
          {shown.map((event, index) => (
            <TimelineEvent key={event.sequence} event={event} offsetMs={times[index]} />
          ))}
          <div ref={listEnd} />
        </ul>
      </div>

      <p aria-live="assertive" className="sr-only">
        {shown.filter(isBlocked).length > 0
          ? `${shown.filter(isBlocked).length} blocked attempts so far.`
          : ""}
      </p>

      <p className="mt-4 max-w-[64ch] text-[13.5px] leading-relaxed text-text-muted text-pretty">
        A blocked call is drawn heavier than a successful one. Policy stops the send either
        way, so the end state looks identical whether or not the agent tried — the attempt is
        the only thing that tells them apart.
      </p>
    </section>
  );
}
