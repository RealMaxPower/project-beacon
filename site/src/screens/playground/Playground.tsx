import { useCallback, useMemo, useState } from "react";
import { ActionBar } from "@/components/shell/ActionBar";
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
    /*
     * The top of the new step, not wherever the old one left you.
     *
     * Cards further down a grid are the ones most likely to be clicked — the
     * scenario picker is seven cards deep — and advancing kept the scroll
     * position, so you arrived at step three already scrolled past its
     * heading, with the sticky header covering the step rail. It read as a
     * page that had half-loaded. The router does this for pages already.
     */
    window.scrollTo({ top: 0 });
  }, []);

  const evidence = subjectKey ? evidenceFor(subjectKey) : null;
  const events = subjectKey ? eventsFor(subjectKey) : [];

  const onRunDone = useCallback(() => setRan(true), []);

  const restart = useCallback(() => {
    setScenarioId(null);
    setSubjectKey(null);
    setRan(false);
    setReached(new Set<StepKey>(["scenario"]));
    setStep("scenario");
    window.scrollTo({ top: 0 });
  }, []);

  const scenario = scenarioId ? scenarios.find((s) => s.id === scenarioId) : null;

  /*
   * The bar carries the one action that moves the run forward, and nothing
   * else. The first two steps have none: choosing a card *is* the action
   * there, and a bar saying "pick one" below a grid of cards that say "pick
   * one" is furniture.
   */
  const bar = (() => {
    if (step === "world" && evidence) {
      return {
        status: `${scenario?.id ?? ""} · nothing has run yet`,
        action: (
          <button
            type="button"
            onClick={() => go("run")}
            className="hit-target inline-flex items-center rounded-row bg-text px-4 text-[13px] font-medium text-bg"
          >
            Run it
          </button>
        ),
      };
    }

    if (step === "run" && evidence) {
      return {
        // Disabled rather than absent while the events are still arriving.
        // A control that appears only once the run finishes gives no warning
        // that there is a step after this one, which is the reading the whole
        // rail exists to prevent.
        status: ran ? `${events.length} events recorded` : "replaying the recorded events…",
        action: (
          <button
            type="button"
            onClick={() => go("verdict")}
            disabled={!ran}
            className="hit-target inline-flex items-center rounded-row bg-text px-4 text-[13px] font-medium text-bg disabled:opacity-40"
          >
            See the verdict
          </button>
        ),
      };
    }

    if (step === "verdict" && evidence) {
      return {
        status: `${evidence.result} · one run, one sample`,
        action: (
          <button
            type="button"
            onClick={() => go("repeat")}
            className="hit-target inline-flex items-center rounded-row bg-text px-4 text-[13px] font-medium text-bg"
          >
            Run it twelve times
          </button>
        ),
      };
    }

    if (step === "repeat") {
      return {
        status: "that is the whole loop",
        action: (
          <>
            <a
              href="https://github.com/RealMaxPower/project-beacon"
              className="hit-target hidden items-center rounded-row border border-line-strong px-3.5 font-mono text-[12.5px] text-text-muted hover:text-text sm:inline-flex"
            >
              Run it yourself
            </a>
            <button
              type="button"
              onClick={restart}
              className="hit-target inline-flex items-center rounded-row bg-text px-4 text-[13px] font-medium text-bg"
            >
              Start over
            </button>
          </>
        ),
      };
    }

    return null;
  })();

  return (
    <div
      // Room for the fixed bar, so the last row of content is never underneath
      // it. Only when there is one — the picking steps get the space back.
      className={`mx-auto max-w-[1180px] px-5 pt-10 sm:px-11 ${bar ? "pb-28" : "pb-10"}`}
    >
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
            <WorldBefore evidence={evidence} expert={expert} />
          ) : (
            <EmptyState
              {...emptyStates.noSubject}
              ctaLabel="Pick an agent"
              onCta={() => go("subject")}
            />
          ))}

        {step === "run" &&
          (evidence ? (
            <RunTimeline
              evidence={evidence}
              events={events}
              expert={expert}
              onDone={onRunDone}
            />
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
               *
               * The button that used to live here is in the action bar, where
               * it is reachable without scrolling past the assertions, the
               * state diff, the artifact and the limitations to get to it. The
               * argument stays: it is the reason to press the button, and it
               * belongs next to the verdict it qualifies.
               */}
              <div className="mt-8 rounded-card border border-line border-l-[3px] border-l-accent bg-surface p-5">
                <h3 className="mb-2 text-[17px] leading-snug font-medium text-balance">
                  This verdict is a single sample.
                </h3>
                <p className="max-w-[66ch] text-[14px] leading-relaxed text-text-muted text-pretty">
                  The question worth asking is how often it comes out this way. This subject is
                  deterministic: it returns {evidence.result} every time, with the same tool
                  calls in the same order. A model-backed one is where repetition changes the
                  answer.
                </p>
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

      {bar && <ActionBar status={bar.status}>{bar.action}</ActionBar>}
    </div>
  );
}
