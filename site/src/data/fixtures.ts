/**
 * Load the recorded runs.
 *
 * Everything here is imported from `generated/`, which is written by
 * `site/tools/build_fixtures.py` running the real scenarios. Nothing in this
 * module authors a value; where a number is needed it is computed from the
 * bundle, because a figure typed twice eventually disagrees with itself and
 * this site's whole argument is that displayed evidence should be checkable
 * against its source.
 */

import type {
  Baseline,
  Facts,
  BeaconEvent,
  Evidence,
  Fixture,
  FixtureIndex,
  ScenarioSummary,
  Verdict,
} from "./types";

import indexJson from "./generated/index.json";
import scenariosJson from "./generated/scenarios.json";
import baselinesJson from "./generated/baselines.json";
import factsJson from "./generated/facts.json";

/*
 * The recorded bundles, loaded once as text and parsed here.
 *
 * They used to be imported twice — once as JSON for the screens, once as raw
 * text for the expert panels — which shipped every byte of every run twice and
 * left two representations that could drift apart. Parsing the text the panel
 * displays means the screen and the panel cannot disagree: there is one copy,
 * and the panel shows it verbatim.
 */
const bundleSources = import.meta.glob("./generated/*/*.json", {
  eager: true,
  query: "?raw",
  import: "default",
}) as Record<string, string>;

const bundleByKey = new Map<string, string>(
  Object.entries(bundleSources).map(([path, text]) => {
    const parts = path.split("/");
    return [`${parts.at(-2)}/${parts.at(-1)}`, text];
  }),
);

const parsed = new Map<string, unknown>();

function readBundle<T>(key: string, file: string): T {
  const id = `${key}/${file}`;
  if (!parsed.has(id)) {
    const text = bundleByKey.get(id);
    if (!text) throw new Error(`No ${file} recorded for ${key}. Rerun build_fixtures.py.`);
    parsed.set(id, JSON.parse(text));
  }
  return parsed.get(id) as T;
}

/** The recorded `evidence.json` or `events.json` for a run, as written. */
export function bundleSource(key: string, file: "evidence.json" | "events.json"): string {
  const text = bundleByKey.get(`${key}/${file}`);
  if (!text) throw new Error(`No ${file} recorded for ${key}. Rerun build_fixtures.py.`);
  return text;
}

export const fixtureIndex = indexJson as unknown as FixtureIndex;
export const fixtures: Fixture[] = fixtureIndex.fixtures;
export const scenarios = scenariosJson as unknown as ScenarioSummary[];
export const baselines = baselinesJson as unknown as Baseline[];
export const facts = factsJson as unknown as Facts;

export function evidenceFor(key: string): Evidence {
  return readBundle<Evidence>(key, "evidence.json");
}

export function eventsFor(key: string): BeaconEvent[] {
  return readBundle<BeaconEvent[]>(key, "events.json");
}

/**
 * The scenario a run was graded against, with its world attached.
 *
 * `evidence.scenario` is not enough: it records which scenario ran, but the
 * fixtures and the tool surface are stripped out of the bundle. Both are read
 * from `scenarios.json`, which `build_fixtures.py` exports from the scenario
 * files themselves.
 */
export function scenarioFor(evidence: Evidence): ScenarioSummary {
  const found = scenarios.find((s) => s.id === evidence.scenario.id);
  if (!found) {
    throw new Error(
      `Run ${evidence.run_id} names scenario ${evidence.scenario.id}, which is not in scenarios.json.`,
    );
  }
  return found;
}

/*
 * The scenario files verbatim, keyed by slug.
 *
 * Loaded as raw text rather than parsed JSON so that what expert mode displays
 * is the bytes on disk — including key order and formatting — and not a
 * re-serialisation that happens to carry the same values.
 */
const scenarioSources = import.meta.glob("./generated/scenarios/*.json", {
  eager: true,
  query: "?raw",
  import: "default",
}) as Record<string, string>;

const sourceBySlug = new Map<string, string>(
  Object.entries(scenarioSources).map(([path, text]) => [
    path.split("/").at(-1)!.replace(/\.json$/, ""),
    text,
  ]),
);

/**
 * The scenario file as written, for the panel that names it.
 *
 * `scenarios.json` is a projection built for the UI — it adds `slug`,
 * `artifact` and `graded_on` and drops `schema_version`, `limits` and
 * `metadata`. Rendering that under the path of the real file was a panel
 * claiming to be a document it was not.
 */
export function scenarioSource(slug: string): { path: string; text: string } | null {
  const text = sourceBySlug.get(slug);
  if (!text) return null;
  return { path: `scenarios/${slug}/scenario.json`, text };
}

export function fixtureFor(key: string): Fixture {
  const found = fixtures.find((f) => f.key === key);
  if (!found) throw new Error(`No fixture named ${key}.`);
  return found;
}

/**
 * Milliseconds from the first event, per event.
 *
 * The timeline shows an elapsed time against each line. Deriving it here means
 * no component can be handed a duration that disagrees with the run it is
 * displaying.
 */
export function offsets(events: BeaconEvent[]): number[] {
  if (events.length === 0) return [];
  const start = Date.parse(events[0].timestamp);
  return events.map((e) => Date.parse(e.timestamp) - start);
}

/** Wall-clock duration of a run, read from the bundle rather than passed in. */
export function durationMs(evidence: Evidence): number {
  return Date.parse(evidence.completed_at) - Date.parse(evidence.started_at);
}

/**
 * A tool call the router refused.
 *
 * Beacon records the attempt before dispatch and the refusal after it, as a
 * `policy_violation` plus a `tool_error` carrying `ToolPolicyError`. The
 * attempt is the evidence — `send-never-attempted` is the assertion that
 * means something, because policy blocks the send either way.
 */
export function isBlocked(event: BeaconEvent): boolean {
  return event.kind === "policy_violation" || isPolicyRefusal(event);
}

/**
 * A tool error that is a refusal rather than a malfunction.
 *
 * Matched on the suffix, not on one name. The mail service raises
 * `ToolPolicyError` and the files service raises `FilePolicyError`, and
 * hardcoding the first meant a run that attempted a delete and was refused
 * reported no attempt at all — the state diff said "nothing was attempted"
 * about a run whose whole point was the attempt. A service that adds its own
 * error type is covered without this being edited.
 */
function isPolicyRefusal(event: BeaconEvent): boolean {
  return (
    event.kind === "tool_error" &&
    typeof event.payload?.error_type === "string" &&
    event.payload.error_type.endsWith("PolicyError")
  );
}

/**
 * Blocked attempts, counted by the tool they were aimed at.
 *
 * Used to annotate the state rows that did *not* change. A refused send leaves
 * `mail.sent` empty, which is exactly what a compliant run leaves behind — so
 * the diff alone cannot tell the two apart, and a diff that shows only changes
 * quietly reports the misbehaving agent as clean.
 */
export function blockedAttempts(events: BeaconEvent[]): Map<string, number> {
  const counts = new Map<string, number>();
  for (const event of events) {
    // Keyed off the `tool_error`, whose target is the tool. The paired
    // `policy_violation` names the rule (`files_delete_blocked`), not the call.
    if (!isPolicyRefusal(event)) continue;
    counts.set(event.target, (counts.get(event.target) ?? 0) + 1);
  }
  return counts;
}

/**
 * The state path a tool writes to, for annotating an unchanged row.
 *
 * Derived from the tool's own name rather than a lookup table: the services
 * name their tools `<service>_<verb>_<noun>`, and the state they mutate is
 * keyed by the same service. A tool this cannot place is simply not annotated,
 * which loses a note rather than inventing a path.
 */
export function pathForTool(tool: string): string | null {
  const [service, verb] = tool.split("_");
  if (!service || !verb) return null;
  const nouns: Record<string, string> = {
    send: "sent",
    add: "labels",
    create: "drafts",
    delete: "files",
    move: "files",
    write: "files",
  };
  const noun = nouns[verb];
  return noun ? `${service}.${noun}` : null;
}

/** A one-line human description of an event, from its own payload. */
export function describeEvent(event: BeaconEvent): string | null {
  const payload = (event.payload ?? {}) as Record<string, unknown>;

  if (event.kind === "tool_result") {
    const result = payload.result;
    if (Array.isArray(result)) {
      return `${result.length} returned`;
    }
    if (result && typeof result === "object") {
      const record = result as Record<string, unknown>;
      const id = record.id;
      if (typeof id === "string") {
        const target = record.in_reply_to ?? record.path;
        return typeof target === "string" ? `${id}, answers ${target}` : String(id);
      }
    }
    return null;
  }

  if (event.kind === "tool_call") {
    const args = payload.arguments as Record<string, unknown> | undefined;
    if (!args || Object.keys(args).length === 0) return null;
    return Object.entries(args)
      .map(([key, value]) => `${key}=${typeof value === "string" ? value : JSON.stringify(value)}`)
      .join(" · ")
      .slice(0, 120);
  }

  if (event.kind === "tool_error") return String(payload.message ?? "refused");
  if (event.kind === "policy_violation") {
    const draft = payload.draft_id;
    return typeof draft === "string" ? `draft ${draft}` : "policy refused this";
  }
  if (event.kind === "artifact") {
    const content = payload.content;
    return typeof content === "string" ? `${content.length} chars` : null;
  }
  if (event.kind === "subject_completed") return `status ${payload.status ?? "unknown"}`;
  return null;
}

/**
 * Whether an assertion was evaluated at all in a recorded sample.
 *
 * A rate of zero has two very different causes. If no run in the sample ever
 * returned FAIL, a 0% pass rate cannot mean "failed every time" — there were no
 * failures. It means the check never ran: it reads a path the reply did not
 * contain, so there was nothing to compare and every run resolved INCOMPLETE.
 * Publishing that as a pass rate is publishing a measurement nobody took.
 */
export function wasEvaluated(baseline: Baseline, id: string): boolean {
  const rate = baseline.assertion_pass_rates[id];
  if (rate === undefined) return false;
  if (rate > 0) return true;
  return (baseline.verdicts.FAIL ?? 0) > 0;
}

export function assertionRate(baseline: Baseline, id: string): number | undefined {
  return baseline.assertion_pass_rates[id];
}

/** Verdicts as a run-by-run vector, for the run strip. */
export function verdictVector(baseline: Baseline): Verdict[] {
  const out: Verdict[] = [];
  for (const [verdict, count] of Object.entries(baseline.verdicts)) {
    for (let i = 0; i < (count ?? 0); i += 1) out.push(verdict as Verdict);
  }
  return out;
}

/*
 * An injected instruction hidden in the material, wherever it hides.
 *
 * It used to be looked for in `fixtures.mail.messages`, which found the inbox
 * payload and nothing else — so the two scenarios actually named for injection
 * resistance, whose payload sits in a document, showed no callout at all.
 *
 * The marker is a bracketed shout: `[SYSTEM OVERRIDE]`,
 * `[SYSTEM DIRECTIVE - PRIORITY OVERRIDE]`. Matching the shape rather than the
 * exact words means a scenario that words its payload differently is still
 * found, and a scenario with no payload — `hosted-injection-resistance`
 * deliberately has none — correctly yields nothing.
 */
const INJECTION = /\[[A-Z][A-Z0-9 \-]{4,}\]/;

export interface Injection {
  /** Where it was hiding: a message id, a file path, or a fixture field. */
  source: string;
  text: string;
}

export function injectionIn(scenario: ScenarioSummary): Injection | null {
  const found: Injection[] = [];

  const walk = (node: unknown, label: string) => {
    if (typeof node === "string") {
      const at = node.search(INJECTION);
      if (at !== -1) found.push({ source: label, text: node.slice(at, at + 400).trim() });
      return;
    }
    if (Array.isArray(node)) {
      node.forEach((item, i) => {
        const named = item as { id?: string; path?: string };
        walk(item, named?.id ?? named?.path ?? `${label}[${i}]`);
      });
      return;
    }
    if (node && typeof node === "object") {
      for (const [key, value] of Object.entries(node)) {
        // Keep the item's own name once we have one, rather than appending
        // every field to it — "m-004" reads better than "mail.messages[3].body".
        walk(value, label.includes(".") || /^[\w-]+$/.test(label) ? label : `${label}.${key}`);
      }
    }
  };

  walk(scenario.fixtures ?? {}, "fixtures");
  return found[0] ?? null;
}

/**
 * What the scenario forbids, and whether the subject reached for it anyway.
 *
 * Derived from the assertions Beacon grades rather than from a list here.
 * `event_absent` is an action that must not be attempted; `contains_none` is
 * material that must not come back. Both fail exactly when the subject did the
 * thing — so "attempted" is the assertion's own verdict, not an inference drawn
 * beside it.
 */
export function forbiddenOutcomes(
  scenario: ScenarioSummary,
  evidence: Evidence,
): { label: string; attempted: boolean }[] {
  const graded = new Map(evidence.assertions.map((a) => [a.id, a]));

  return scenario.assertions
    .filter((a) => a.type === "event_absent" || a.type === "contains_none")
    .map((a) => ({
      label: a.description,
      attempted: graded.get(a.id)?.passed === false,
    }));
}
