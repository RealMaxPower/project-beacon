import { useCallback, useMemo, useState } from "react";
import { StepRail } from "@/components/shell/StepRail";
import { ExpertToggle } from "@/components/shell/ExpertToggle";
import { EmptyState } from "@/components/shell/EmptyState";
import { PickScenario } from "./PickScenario";
import { PickSubject } from "./PickSubject";
import { WorldBefore } from "./WorldBefore";
import { RunTimeline } from "./RunTimeline";
import { Verdict } from "./Verdict";
import { TwelveRuns } from "./TwelveRuns";
import { BaselineCompare } from "./BaselineCompare";
import { ExportBundle } from "./ExportBundle";
import { emptyStates, type StepKey } from "@/data/copy";
import { evidenceFor, eventsFor, fixtures, scenarios } from "@/data/fixtures";

/**
 * The playground shell.
 *
 * Steps stay reachable rather than disabled: clicking ahead shows an
 * EmptyState that says what the step needs, which teaches the shape of a run
 * better than a greyed-out control. Nothing here renders sample data as a
 * placeholder — a screen with no run behind it says so.
 */

interface Props {
  /**
   * A scenario named by the URL — `#/playground/<id>`, which is how a scenario
   * card on the marketing pages opens this already pointed at itself.
   *
   * Matched on `id` rather than `slug`. They are the same string for six of the
   * seven; `inbox-briefing` is the directory and `inbox-briefing-draft-only` is
   * the id, and that is the one scenario with five recorded subjects — so
   * linking by slug would fail on precisely the card most likely to be clicked.
   */
  scenarioId?: string | null;
}

export function Playground({ scenarioId: requested = null }: Props) {
  /*
   * A requested scenario is honoured only if it exists. Silently dropping an
   * id that resolves to nothing would land the visitor on step one with no
   * indication that the link they followed was wrong — the same failure the
   * router refuses to make for pages.
   */
  const wanted = requested ? (scenarios.find((s) => s.id === requested) ?? null) : null;
  const unresolved = requested !== null && wanted === null;

  const [step, setStep] = useState<StepKey>(wanted ? "subject" : "scenario");
  const [scenarioId, setScenarioId] = useState<string | null>(wanted?.id ?? null);
  const [subjectKey, setSubjectKey] = useState<string | null>(null);
  const [expert, setExpert] = useState(false);
  const [ran, setRan] = useState(false);
  const [reached, setReached] = useState<Set<StepKey>>(() =>
    wanted ? new Set<StepKey>(["scenario", "subject"]) : new Set<StepKey>(["scenario"]),
  );

  const runnable = useMemo(() => new Set(fixtures.map((f) => f.scenario)), []);

  const go = useCallback((next: StepKey) => {
    setStep(next);
    setReached((seen) => new Set(seen).add(next));
  }, []);

  const evidence = subjectKey ? evidenceFor(subjectKey) : null;
  const events = subjectKey ? eventsFor(subjectKey) : [];

  const onRunDone = useCallback(() => setRan(true), []);

  return (
    <div className="mx-auto max-w-[1180px] px-5 py-10 sm:px-11">
      <header className="mb-8">
        <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-[28px] leading-tight font-medium tracking-[-0.03em] text-balance">
              Watch an agent work, then read the evidence.
            </h1>
            <p className="mt-1.5 font-mono text-[11.5px] text-text-faint">
              Recorded runs, replayed in your browser. Nothing is executing here.
            </p>
          </div>
          <ExpertToggle on={expert} onChange={setExpert} />
        </div>

        <StepRail current={step} reached={reached} onGo={go} />
      </header>

      {/*
        * A div, not a `main`. The shell already renders `<main id="main">`
        * around whichever screen is showing, and nesting a second one gave
        * the playground two main landmarks — so the skip link and a screen
        * reader's landmark list both offered a choice between them, with
        * nothing to distinguish the two.
        */}
      <div>
        {step === "scenario" && (
          <>
            {unresolved && (
              <p className="mb-6 rounded-card border border-inc/40 border-dashed bg-inc-tint p-4 text-[14px] leading-relaxed on-tint text-pretty">
                No scenario is named{" "}
                <code className="font-mono text-[13px]">{requested}</code>. The link that
                brought you here points at something this build does not ship. The{" "}
                {scenarios.length} it does are below.
              </p>
            )}
            <PickScenario
              selected={scenarioId}
              runnable={runnable}
              onPick={(id) => {
                setScenarioId(id);
                setSubjectKey(null);
                setRan(false);
                go("subject");
              }}
            />
          </>
        )}

        {step === "subject" &&
          (scenarioId ? (
            <PickSubject
              scenarioId={scenarioId}
              selected={subjectKey}
              onPick={(key) => {
                setSubjectKey(key);
                setRan(false);
                go("world");
              }}
            />
          ) : (
            <EmptyState
              {...emptyStates.noScenario}
              ctaLabel="Pick a scenario"
              onCta={() => go("scenario")}
            />
          ))}

        {step === "world" &&
          (evidence ? (
            <>
              <WorldBefore evidence={evidence} expert={expert} />
              <div className="mt-6">
                <button
                  type="button"
                  onClick={() => go("run")}
                  className="hit-target inline-flex items-center rounded-row bg-text px-4 py-2.5 text-[13px] font-medium text-bg"
                >
                  Run it
                </button>
              </div>
            </>
          ) : (
            <EmptyState
              {...emptyStates.noSubject}
              ctaLabel="Pick an agent"
              onCta={() => go("subject")}
            />
          ))}

        {step === "run" &&
          (evidence ? (
            <>
              <RunTimeline
                evidence={evidence}
                events={events}
                expert={expert}
                onDone={onRunDone}
              />
              {ran && (
                <div className="mt-6">
                  <button
                    type="button"
                    onClick={() => go("verdict")}
                    className="hit-target inline-flex items-center rounded-row bg-text px-4 py-2.5 text-[13px] font-medium text-bg"
                  >
                    See the verdict
                  </button>
                </div>
              )}
            </>
          ) : (
            <EmptyState
              {...emptyStates.noSubject}
              ctaLabel="Pick an agent"
              onCta={() => go("subject")}
            />
          ))}

        {step === "verdict" &&
          (evidence ? (
            <>
              <Verdict evidence={evidence} events={events} expert={expert} />

              {/*
               * The bridge to the next step. A verdict screen that ends without
               * it invites the reading this whole product argues against — that
               * one run settled something.
               */}
              <div className="mt-8 rounded-card border border-line border-l-[3px] border-l-accent bg-surface p-5">
                <h3 className="mb-2 text-[17px] leading-snug font-medium text-balance">
                  This verdict is a single sample.
                </h3>
                <p className="mb-4 max-w-[66ch] text-[14px] leading-relaxed text-text-muted text-pretty">
                  The question worth asking is how often it comes out this way. This subject is
                  deterministic: it returns {evidence.result} every time, with the same tool
                  calls in the same order. A model-backed one is where repetition changes the
                  answer.
                </p>
                <button
                  type="button"
                  onClick={() => go("repeat")}
                  className="hit-target inline-flex items-center rounded-row bg-text px-4 py-2.5 text-[13px] font-medium text-bg"
                >
                  Run it twelve times
                </button>
              </div>

              <div className="mt-8">
                <ExportBundle evidence={evidence} />
              </div>
            </>
          ) : (
            <EmptyState
              {...emptyStates.notRun}
              ctaLabel="Pick a scenario"
              onCta={() => go("scenario")}
            />
          ))}

        {step === "repeat" && (
          <>
            <TwelveRuns />
            <div className="mt-10">
              <BaselineCompare />
            </div>
          </>
        )}
      </div>
    </div>
  );
}
