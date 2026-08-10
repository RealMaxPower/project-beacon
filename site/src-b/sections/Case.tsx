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
  /** Labelled blocks, the way the design breaks its inspector up. */
  blocks: { label: string; body: string; numbered?: boolean }[];
  /** The footer pair: a name on the left, a value on the right. */
  footer?: { label: string; value: string };
  tone?: "src" | "review" | "ok" | "bad";
}

/**
 * A row, drawn as a bordered card rather than a list line.
 *
 * The design gives every row its own hairline box with a gap to the next, and
 * selection reads as a tinted card with a coloured left edge. Flat rows on a
 * divided list looked like a table and made the selected one hard to find; the
 * card carries the selection without needing a heavier fill.
 */
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
  const accent =
    tone === "bad" ? "var(--b-bad)" : tone === "ok" ? "var(--b-ok)" : "var(--b-src)";
  return (
    <li>
      <button
        type="button"
        onClick={onSelect}
        aria-pressed={selected}
        className="hit-target flex w-full items-center gap-3 rounded-lg border border-l-2 px-4 py-2.5 text-left text-[13px] transition-colors"
        /*
         * The coloured left edge is selection, or it is a verdict — never
         * decoration. An accent on every row spent the one signal that tells a
         * reader which row the inspector is describing, and rows carrying a
         * real tone (a refusal, a failed check) keep theirs either way so the
         * colour still means the thing it means.
         */
        style={{
          borderColor: selected ? accent : "var(--b-line)",
          borderLeftColor: selected || tone ? accent : "var(--b-line)",
          background: selected ? "color-mix(in oklab, var(--b-src) 9%, transparent)" : "transparent",
        }}
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
  return (
    <ul className="flex max-h-[420px] flex-col gap-2 overflow-x-hidden overflow-y-auto p-4">
      {children}
    </ul>
  );
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
        meta: `${String(message.from ?? "unknown")} · ${scenario.slug}`,
        blocks: [
          { label: "As declared", body: String(message.body ?? ""), numbered: true },
          {
            label: "Where it came from",
            body: "Written into the scenario file. Nothing here was fetched, and no real mailbox was read — this is the whole world the subject was given.",
          },
        ],
        footer: { label: "fixture", value: `mail.messages[${picked}]` },
        tone: "src",
      };
    }
    if (tab === "timeline") {
      const event = events[picked] ?? events[0];
      return {
        title: `${event.kind} · ${event.target}`,
        meta: `event ${picked + 1} of ${events.length}`,
        blocks: [
          { label: "What happened", body: describeEvent(event) ?? "" },
          { label: "Payload", body: JSON.stringify(event.payload, null, 2), numbered: true },
        ],
        footer: { label: "recorded at", value: `+${elapsed[picked] ?? 0}ms, before dispatch` },
        tone: isBlocked(event) ? "bad" : "src",
      };
    }
    if (tab === "checks") {
      const assertion = evidence.assertions[picked] ?? evidence.assertions[0];
      return {
        title: assertion.id,
        meta: assertion.passed ? "satisfied" : "failed",
        blocks: [
          { label: "What it checks", body: assertion.description },
          {
            label: "Expected against actual",
            body: `expected  ${JSON.stringify(assertion.expected)}\nactual    ${JSON.stringify(assertion.actual)}`,
            numbered: true,
          },
          ...(assertion.message ? [{ label: "Message", body: assertion.message }] : []),
        ],
        footer: { label: "graded by", value: "string and state comparison" },
        tone: assertion.passed ? "ok" : "bad",
      };
    }
    if (tab === "state") {
      const change = evidence.state_diff.changes[picked] ?? evidence.state_diff.changes[0];
      const attempts = [...refused.entries()];
      return {
        title: change?.path ?? "no change",
        meta: `${evidence.state_diff.change_count} field changed`,
        blocks: [
          ...(change
            ? [
                {
                  label: "Before and after",
                  body: `before  ${JSON.stringify(change.before)}\nafter   ${JSON.stringify(change.after)}`,
                  numbered: true,
                },
              ]
            : []),
          ...(attempts.length
            ? [
                {
                  label: "Attempted, and absent from this diff",
                  body: attempts
                    .map(([tool, n]) => `${tool} — ${n} attempt${n === 1 ? "" : "s"}, all refused`)
                    .join("\n"),
                },
              ]
            : []),
        ],
        footer: { label: "reset verified", value: String(evidence.reset_verified) },
        tone: "src",
      };
    }
    if (tab === "artifact") {
      const [name, value] = Object.entries(evidence.artifacts)[0] ?? ["—", ""];
      return {
        title: name,
        meta: "returned by the subject",
        blocks: [
          {
            label: "As returned",
            body: typeof value === "string" ? value : JSON.stringify(value, null, 2),
            numbered: true,
          },
        ],
        footer: {
          label: "contract asks for",
          value: scenario.output_contract?.artifact ?? "nothing in particular",
        },
        tone: "src",
      };
    }
    const failed = evidence.assertions.filter((a) => a.passed === false);
    return {
      title: evidence.result,
      meta: `${evidence.assertions.length - failed.length} of ${evidence.assertions.length} checks satisfied`,
      blocks: [
        {
          label: "How it was graded",
          body: "By comparing strings and state. No model sits anywhere in this path, which is why the same run grades the same way every time.",
        },
        {
          label: failed.length ? "What failed" : "Result",
          body: failed.length
            ? failed.map((a) => `${a.id} — ${a.description}`).join("\n")
            : "Every declared check was satisfied.",
        },
      ],
      footer: { label: "sha256", value: `${evidence.digest.slice(0, 16)}…` },
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
            <span
              className="b-eyebrow ml-auto rounded-[4px] border px-2 py-1"
              style={{ borderColor: "var(--b-bad)", color: "var(--b-bad)" }}
            >
              {evidence.result} {evidence.assertions.filter((a) => a.passed).length}/
              {evidence.assertions.length}
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
            <div className="min-w-0 p-4">
              <p className="b-eyebrow mb-3 text-b-faint">Inspector</p>

              <div className="overflow-hidden rounded-lg border border-b-line bg-b-bg">
                <div className="border-b border-b-line px-4 py-3">
                  <p className={`font-b-mono text-[13px] break-all ${toneClass}`}>
                    {selection.title}
                  </p>
                  <p className="mt-1 font-b-mono text-[11px] text-b-faint">{selection.meta}</p>
                </div>

                <div className="max-h-[300px] overflow-y-auto">
                  {selection.blocks.map((block) => (
                    <div key={block.label} className="border-b border-b-line px-4 py-3.5 last:border-b-0">
                      <p className="b-eyebrow mb-2 text-b-src">{block.label}</p>
                      {block.numbered ? (
                        <ol
                          className="border-l-2 pl-3 font-b-mono text-[11.5px] leading-[1.7]"
                          style={{ borderColor: "var(--b-src)" }}
                        >
                          {block.body.split("\n").map((line, i) => (
                            <li key={i} className="flex gap-3">
                              <span
                                aria-hidden="true"
                                className="w-4 flex-none text-right text-b-faint"
                              >
                                {i + 1}
                              </span>
                              <span className="min-w-0 flex-1 break-words whitespace-pre-wrap text-b-muted">
                                {line}
                              </span>
                            </li>
                          ))}
                        </ol>
                      ) : (
                        <p className="text-[13px] leading-relaxed whitespace-pre-wrap text-b-muted">
                          {block.body}
                        </p>
                      )}
                    </div>
                  ))}
                </div>

                {selection.footer && (
                  <div className="flex items-baseline justify-between gap-4 border-t border-b-line px-4 py-3">
                    <span className="font-b-mono text-[11px] text-b-faint">
                      {selection.footer.label}
                    </span>
                    <span className="min-w-0 truncate font-b-mono text-[11px] text-b-src">
                      {selection.footer.value}
                    </span>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
