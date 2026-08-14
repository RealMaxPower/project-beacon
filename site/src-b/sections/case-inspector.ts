import { blockedAttempts, describeEvent, isBlocked } from "@/data/fixtures";
import type { BeaconEvent, Evidence, ScenarioSummary } from "@/data/types";

/**
 * What the case explorer's inspector shows, as a function rather than a closure.
 *
 * It was inline in `Case.tsx`, which made it unreachable to anything but a
 * browser: `renderToStaticMarkup` renders initial state, so the render audit
 * only ever saw one tab and one row of six tabs and twenty-seven events. Two
 * defects lived in the twenty-six it could not reach — a field read under a
 * name no message has, so every row on the World tab displayed the word
 * "unknown" as a sender; and a labelled section rendered empty on the two
 * events `describeEvent` deliberately has nothing to say about. Both are in
 * the class `tools/lint.tsx` already checks for. Neither was reachable.
 *
 * A pure function is reachable. `auditInspector` in the render audit now walks
 * every tab against every row and fails on either, which is coverage the
 * component could not have been given without simulating React state.
 */

export type TabId = "timeline" | "world" | "checks" | "state" | "artifact" | "verdict";

export const TAB_IDS: readonly TabId[] = [
  "timeline",
  "world",
  "checks",
  "state",
  "artifact",
  "verdict",
];

export interface Selection {
  title: string;
  meta: string;
  /** Labelled blocks, the way the design breaks its inspector up. */
  blocks: { label: string; body: string; numbered?: boolean }[];
  /** The footer pair: a name on the left, a value on the right. */
  footer?: { label: string; value: string };
  tone?: "src" | "review" | "ok" | "bad";
}

export interface InspectorInput {
  tab: TabId;
  picked: number;
  evidence: Evidence;
  events: BeaconEvent[];
  scenario: ScenarioSummary;
  elapsed: number[];
}

/** How many rows a tab offers, which is what bounds `picked`. */
export function rowCount(input: Omit<InspectorInput, "tab" | "picked">, tab: TabId): number {
  const mail = messagesIn(input.scenario);
  if (tab === "world") return Math.max(mail.length, 1);
  if (tab === "timeline") return Math.max(input.events.length, 1);
  if (tab === "checks") return Math.max(input.evidence.assertions.length, 1);
  if (tab === "state") return Math.max(input.evidence.state_diff.changes.length, 1);
  return 1;
}

function messagesIn(scenario: ScenarioSummary): Record<string, string>[] {
  return (scenario.fixtures?.mail as { messages?: Record<string, string>[] })?.messages ?? [];
}

export function selectionFor({
  tab,
  picked,
  evidence,
  events,
  scenario,
  elapsed,
}: InspectorInput): Selection {
  const mail = messagesIn(scenario);
  const refused = blockedAttempts(events);
  if (tab === "world") {
    const message = mail[picked] ?? {};
    return {
      title: String(message.id ?? "—"),
      // `sender`, which is what the fixture calls it. This read `message.from`
      // — a key no message in that file has — so every row on this tab fell
      // through to the fallback and displayed the word "unknown" as if it
      // were the sender's name.
      meta: `${String(message.sender ?? "")} · ${scenario.slug}`,
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
      ].filter((block) => block.body.trim() !== ""),
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
}
