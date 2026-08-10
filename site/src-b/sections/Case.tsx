import { useState } from "react";
import {
  blockedAttempts,
  describeEvent,
  evidenceFor,
  eventsFor,
  isBlocked,
  offsets,
  scenarioFor,
} from "@/data/fixtures";
import type { BeaconEvent, Evidence } from "@/data/types";

/**
 * The case explorer: two panes, six tabs, a live inspector.
 *
 * The source design's version has tabs for Sources, Claims, Requirements,
 * Review, Action and Outcome. Only one of those has anything behind it here —
 * Requirements are Beacon's assertions. Beacon does not extract claims from
 * sources, does not raise review tasks, has no notion of an action or an
 * approval bound to one, and does not reconcile an external outcome. Drawing
 * those tabs would have meant inventing the machinery underneath them, which
 * is the one thing this repository builds tests to prevent.
 *
 * So the shape is kept and the tabs are Beacon's: the world it was given, what
 * it did, what was checked, what changed, what it returned, and how it was
 * graded. Every panel reads a recorded bundle.
 *
 * The inspector is not decoration. A row selects, and the right pane explains
 * that row — which is the design's best idea and the reason the section is
 * worth porting at all.
 */

const RUN = "misbehaving";

type TabId = "world" | "timeline" | "checks" | "state" | "artifact" | "verdict";

const TABS: { id: TabId; label: string }[] = [
  { id: "world", label: "World" },
  { id: "timeline", label: "What it did" },
  { id: "checks", label: "Checks" },
  { id: "state", label: "What changed" },
  { id: "artifact", label: "What it returned" },
  { id: "verdict", label: "Verdict" },
];

interface Selection {
  title: string;
  meta: string;
  body: string;
  tone?: "src" | "review" | "ok" | "bad";
}

function Row({
  selected,
  onSelect,
  children,
  tone,
}: {
  selected: boolean;
  onSelect: () => void;
  children: React.ReactNode;
  tone?: "ok" | "bad" | "review";
}) {
  const edge =
    tone === "bad" ? "border-l-b-bad" : tone === "ok" ? "border-l-b-ok" : "border-l-b-src";
  return (
    <li>
      <button
        type="button"
        onClick={onSelect}
        aria-pressed={selected}
        className={`hit-target flex w-full items-center gap-3 border-l-2 px-4 py-2.5 text-left text-[13px] transition-colors ${
          selected ? `${edge} bg-b-src/10` : "border-l-transparent hover:bg-b-src/5"
        }`}
      >
        {children}
      </button>
    </li>
  );
}

function Panel({ children }: { children: React.ReactNode }) {
  /*
   * `overflow-x-hidden` is not redundant.
   *
   * When one axis is set to `auto` and the other is left `visible`, CSS
   * computes the visible one to `auto` as well — so a vertical scroller
   * quietly becomes a horizontal one too, and at 390px this list hid 23px of
   * rows sideways with no cue that it did.
   */
  return <ul className="max-h-[380px] overflow-x-hidden overflow-y-auto">{children}</ul>;
}

export function Case() {
  const evidence: Evidence = evidenceFor(RUN);
  const events: BeaconEvent[] = eventsFor(RUN);
  const scenario = scenarioFor(evidence);
  const elapsed = offsets(events);
  const refused = blockedAttempts(events);

  const [tab, setTab] = useState<TabId>("timeline");
  const [picked, setPicked] = useState(0);

  const mail = (scenario.fixtures?.mail as { messages?: Record<string, string>[] })?.messages ?? [];

  /** What the inspector shows, for the row selected on the current tab. */
  const selection = ((): Selection => {
    if (tab === "world") {
      const message = mail[picked] ?? {};
      return {
        title: String(message.id ?? "—"),
        meta: `${String(message.from ?? "unknown")} · declared in the scenario file`,
        body: String(message.body ?? ""),
        tone: "src",
      };
    }
    if (tab === "timeline") {
      const event = events[picked] ?? events[0];
      return {
        title: `${event.kind} · ${event.target}`,
        meta: `+${elapsed[picked] ?? 0}ms · recorded before dispatch`,
        body: describeEvent(event) ?? JSON.stringify(event.payload, null, 2),
        tone: isBlocked(event) ? "bad" : "src",
      };
    }
    if (tab === "checks") {
      const assertion = evidence.assertions[picked] ?? evidence.assertions[0];
      return {
        title: assertion.id,
        meta: assertion.passed ? "satisfied" : "failed",
        body: `${assertion.description}\n\nexpected  ${JSON.stringify(assertion.expected)}\nactual    ${JSON.stringify(assertion.actual)}${assertion.message ? `\n\n${assertion.message}` : ""}`,
        tone: assertion.passed ? "ok" : "bad",
      };
    }
    if (tab === "state") {
      const change = evidence.state_diff.changes[picked] ?? evidence.state_diff.changes[0];
      const attempts = [...refused.entries()];
      return {
        title: change?.path ?? "no change",
        meta: `${evidence.state_diff.change_count} field changed · reset verified ${evidence.reset_verified}`,
        body: change
          ? `before  ${JSON.stringify(change.before)}\nafter   ${JSON.stringify(change.after)}\n\n${
              attempts.length
                ? attempts
                    .map(([tool, n]) => `${tool} attempted ${n}× and refused — not in this diff`)
                    .join("\n")
                : ""
            }`
          : "",
        tone: "src",
      };
    }
    if (tab === "artifact") {
      const [name, value] = Object.entries(evidence.artifacts)[0] ?? ["—", ""];
      return {
        title: name,
        meta: scenario.output_contract?.artifact
          ? `the contract asks for ${scenario.output_contract.artifact}`
          : "returned by the subject",
        body: typeof value === "string" ? value : JSON.stringify(value, null, 2),
        tone: "src",
      };
    }
    const failed = evidence.assertions.filter((a) => a.passed === false);
    return {
      title: evidence.result,
      meta: `${evidence.assertions.length - failed.length} of ${evidence.assertions.length} checks satisfied`,
      body:
        `${evidence.subject.name} · integration level ${evidence.subject.integration_level}\n` +
        `digest  ${evidence.digest.slice(0, 32)}…\n\n` +
        (failed.length
          ? `failed: ${failed.map((a) => a.id).join(", ")}`
          : "every declared check was satisfied"),
      tone: evidence.result === "PASS" ? "ok" : evidence.result === "FAIL" ? "bad" : "review",
    };
  })();

  const toneClass =
    selection.tone === "bad"
      ? "text-b-bad"
      : selection.tone === "ok"
        ? "text-b-ok"
        : selection.tone === "review"
          ? "text-b-review"
          : "text-b-src";

  return (
    <section id="case" className="b-band">
      <div className="b-measure">
        <p className="b-eyebrow mb-6 text-b-src">02 — The case</p>
        <div className="flex flex-wrap items-end justify-between gap-4">
          <h2 className="b-h2 max-w-[20ch]">Open a run. Trace every check to what it read.</h2>
          <span className="b-eyebrow rounded-md border border-b-review/40 px-2.5 py-1.5 text-b-review">
            Synthetic scenario
          </span>
        </div>
        <p className="b-lede mt-5 max-w-[58ch]">
          One recorded run of {scenario.name.toLowerCase()}, against a subject written to
          misbehave. Select any row to see what it was, when it happened, and what Beacon did
          with it.
        </p>

        <div className="mt-10 overflow-hidden rounded-xl border border-b-line bg-b-raised">
          <div className="flex flex-wrap items-center gap-3 border-b border-b-line px-5 py-3">
            <span className="font-b-mono text-[12px] text-b-src">run://{evidence.run_id}</span>
            <span className="font-b-mono text-[11.5px] text-b-faint">
              {scenario.slug} · {events.length} events · level{" "}
              {evidence.subject.integration_level}
            </span>
          </div>

          {/* Declared and painted: the tab strip scrolls on a phone. */}
          <div
            role="tablist"
            aria-label="What to inspect"
            data-scroll-cue
            className="flex gap-1 overflow-x-auto border-b border-b-line px-3 [mask-image:linear-gradient(to_right,black_calc(100%-2rem),transparent)]"
          >
            {TABS.map((entry) => (
              <button
                key={entry.id}
                role="tab"
                type="button"
                aria-selected={tab === entry.id}
                onClick={() => {
                  setTab(entry.id);
                  setPicked(0);
                }}
                className={`hit-target flex-none border-b-2 px-3 text-[13px] whitespace-nowrap ${
                  tab === entry.id
                    ? "border-b-src text-b-text"
                    : "border-transparent text-b-muted hover:text-b-text"
                }`}
              >
                {entry.label}
              </button>
            ))}
          </div>

          <div className="grid lg:grid-cols-[1fr_1fr]">
            {/*
              `min-w-0`, because a grid item's default minimum is its
              content's min-content width — so the pane refused to go below
              371px on a 348px card, `truncate` never engaged, and 23px of
              every row was clipped by the card's own `overflow-hidden` with
              no way to scroll to it.
            */}
            <div className="min-w-0 border-b border-b-line lg:border-r lg:border-b-0">
              {tab === "world" && (
                <Panel>
                  {mail.map((message, i) => (
                    <Row key={String(message.id)} selected={picked === i} onSelect={() => setPicked(i)}>
                      <span className="font-b-mono text-[12px] text-b-src">
                        {String(message.id)}
                      </span>
                      <span className="min-w-0 flex-1 truncate text-b-muted">
                        {String(message.subject ?? "")}
                      </span>
                    </Row>
                  ))}
                </Panel>
              )}

              {tab === "timeline" && (
                <Panel>
                  {events.map((event, i) => (
                    <Row
                      key={event.sequence}
                      selected={picked === i}
                      onSelect={() => setPicked(i)}
                      tone={isBlocked(event) ? "bad" : undefined}
                    >
                      <span className="w-10 flex-none font-b-mono text-[11px] text-b-faint">
                        {String(i + 1).padStart(2, "0")}
                      </span>
                      <span className="min-w-0 flex-1 truncate">
                        <span className="text-b-muted">{event.kind} </span>
                        <span className="text-b-text">{event.target}</span>
                      </span>
                      {isBlocked(event) && (
                        <span className="b-eyebrow flex-none text-b-bad">refused</span>
                      )}
                    </Row>
                  ))}
                </Panel>
              )}

              {tab === "checks" && (
                <Panel>
                  {evidence.assertions.map((assertion, i) => (
                    <Row
                      key={assertion.id}
                      selected={picked === i}
                      onSelect={() => setPicked(i)}
                      tone={assertion.passed ? "ok" : "bad"}
                    >
                      <span
                        aria-hidden="true"
                        className={`w-4 flex-none font-b-mono ${assertion.passed ? "text-b-ok" : "text-b-bad"}`}
                      >
                        {assertion.passed ? "✓" : "✗"}
                      </span>
                      <span className="min-w-0 flex-1 truncate font-b-mono text-[12px]">
                        {assertion.id}
                      </span>
                      <span className="b-eyebrow flex-none text-b-faint">
                        {assertion.passed ? "met" : "failed"}
                      </span>
                    </Row>
                  ))}
                </Panel>
              )}

              {tab === "state" && (
                <Panel>
                  {evidence.state_diff.changes.map((change, i) => (
                    <Row key={change.path} selected={picked === i} onSelect={() => setPicked(i)}>
                      <span className="font-b-mono text-[12px] text-b-text">{change.path}</span>
                      <span className="b-eyebrow ml-auto flex-none text-b-ok">changed</span>
                    </Row>
                  ))}
                  {[...refused.entries()].map(([tool, count]) => (
                    <li key={tool} className="border-l-2 border-l-transparent px-4 py-2.5">
                      <span className="font-b-mono text-[12px] text-b-faint">{tool}</span>
                      <span className="ml-3 text-[12px] text-b-bad">
                        {count}× attempted, refused — no state change
                      </span>
                    </li>
                  ))}
                </Panel>
              )}

              {tab === "artifact" && (
                <Panel>
                  {Object.keys(evidence.artifacts).map((name, i) => (
                    <Row key={name} selected={picked === i} onSelect={() => setPicked(i)}>
                      <span className="font-b-mono text-[12px] text-b-src">{name}</span>
                    </Row>
                  ))}
                </Panel>
              )}

              {tab === "verdict" && (
                <Panel>
                  <li className="px-4 py-5">
                    <p className="font-b-mono text-[28px] leading-none text-b-bad">
                      {evidence.result}
                    </p>
                    <p className="mt-3 text-[13px] leading-relaxed text-b-muted">
                      Graded by comparing strings and state. No model sits anywhere in this path,
                      which is why the same run grades the same way every time.
                    </p>
                  </li>
                </Panel>
              )}
            </div>

            {/* The inspector. */}
            <div className="min-w-0 p-5">
              <p className={`font-b-mono text-[13px] ${toneClass}`}>{selection.title}</p>
              <p className="mt-1.5 text-[11.5px] text-b-faint">{selection.meta}</p>
              <pre className="mt-4 max-h-[300px] overflow-auto rounded-md border border-b-line bg-b-bg p-4 font-b-mono text-[11.5px] leading-relaxed whitespace-pre-wrap text-b-muted">
                {selection.body}
              </pre>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
