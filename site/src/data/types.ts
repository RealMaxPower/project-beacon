/**
 * The shapes Beacon actually writes.
 *
 * These are not a guess at an API. They describe `evidence.json` and
 * `events.json` as recorded by `site/tools/build_fixtures.py`, which runs the
 * real thing — so if a field here is wrong, the fixtures will not typecheck
 * against it and the build fails rather than the page rendering something
 * plausible.
 */

export type Verdict = "PASS" | "FAIL" | "INCOMPLETE";

/** The two states derived from many runs rather than one. */
export type DerivedState = "FLAKY" | "REGRESSION";

export type BadgeState = Verdict | DerivedState;

export interface Assertion {
  id: string;
  description: string;
  passed: boolean | null;
  /**
   * Whether Beacon could evaluate this at all.
   *
   * Not the same as `passed`, and the difference is the whole argument the
   * Repeat screen makes. When a reply omits the field an assertion reads,
   * `beacon/evaluation.py` writes `passed: false` *and* `measured: false`, and
   * `resolve_result` turns the run INCOMPLETE rather than FAIL on the strength
   * of the second field — "we do not know" is not a verdict about the subject.
   *
   * This type omitted it, so the site had only `passed` to go on and would
   * have labelled such a row "failed": exactly the claim the rest of the site
   * spends a section repudiating. No shipped fixture is unmeasured today,
   * which is why nothing rendered wrongly — but the first hosted bundle added
   * to the playground would have.
   */
  measured?: boolean;
  actual: unknown;
  expected: unknown;
  message?: string;
}

export type EventKind =
  | "subject_started"
  | "tool_call"
  | "tool_result"
  | "tool_error"
  | "policy_violation"
  | "artifact"
  | "subject_completed"
  | (string & {});

export interface BeaconEvent {
  sequence: number;
  timestamp: string;
  kind: EventKind;
  target: string;
  payload: Record<string, unknown>;
}

export interface StateChange {
  path: string;
  before: unknown;
  after: unknown;
}

export interface Evidence {
  evidence_version: string;
  run_id: string;
  started_at: string;
  completed_at: string;
  scenario: {
    id: string;
    name: string;
    description: string;
    goal: string;
    tools?: string[];
    output_contract?: { artifact: string; description?: string };
    fixtures?: Record<string, unknown>;
  };
  subject: {
    id: string;
    name: string;
    adapter: string;
    integration_level: number;
    command?: string[] | null;
  };
  result: Verdict;
  assertions: Assertion[];
  state: { before_digest: string; after_digest: string };
  state_diff: { change_count: number; changes: StateChange[] };
  events: BeaconEvent[];
  /**
   * What the subject returned, by artifact name.
   *
   * Not always prose. A scenario graded with `conforms_to` expects a
   * structured object, and declaring these as strings made every such
   * artifact a runtime crash the moment one was rendered.
   */
  artifacts: Record<string, unknown>;
  reset_verified: boolean;
  limitations: string[];
  digest: string;
}

/** One demo the playground can replay, as recorded in `index.json`. */
export interface Fixture {
  key: string;
  label: string;
  shows: string;
  subject: string | null;
  behavior: string;
  expected: Verdict;
  verdict: Verdict;
  scenario: string;
  integration_level: number;
}

export interface FixtureIndex {
  generated_by: string;
  note: string;
  fixtures: Fixture[];
}

export interface ScenarioSummary {
  slug: string;
  id: string;
  name: string;
  description: string;
  goal: string;
  tools: string[];
  artifact: string | null;
  output_contract: { artifact: string; description?: string } | null;
  /**
   * The synthetic world, as declared. Not available from the evidence bundle —
   * `evidence.scenario` records which scenario ran, with fixtures and the tool
   * surface stripped — so the playground reads it from here.
   */
  fixtures: Record<string, unknown>;
  assertions: { id: string; description: string; type: string | null }[];
  graded_on: "service state" | "the answer";
}

export interface Baseline {
  file: string;
  baseline_version: string;
  recorded_at: string;
  scenario: string;
  subject: { name: string; id: string; adapter: string; command?: string[] | null };
  runs: number;
  verdicts: Partial<Record<Verdict, number>>;
  dominant_verdict: Verdict;
  assertion_pass_rates: Record<string, number>;
  state: { before_digest: string; after_digest: string };
}

/** Where a displayed value came from. Rendered, not just recorded. */
export type Provenance = "repo" | "proposal" | "illustrative";

/**
 * The counts the marketing pages state, each derived from what it counts.
 *
 * There is no test count or coverage percentage here on purpose. The README
 * gives a floor rather than a figure for both, because an exact number on a
 * website is wrong as soon as somebody writes a test.
 */
export interface AdapterFact {
  id: string;
  subject: string;
  interface: string;
  reached_by: string;
  status: string;
  level: number;
  /** Whether this adapter can be the subject of a graded run, or only inspects. */
  run: boolean;
  subject_id?: string;
}

export interface TaxonomyFacts {
  taxonomy_version: string;
  cells_total: number;
  cells_core: number;
  covered_total: number;
  covered_core: number;
  percent_total: number;
  percent_core: number;
  out_of_scope: number;
  by_family: Record<
    string,
    { total: number; core: number; covered: number; percent: number }
  >;
}

export interface Facts {
  subjects: number;
  subjects_by_expected_verdict: Record<Verdict, number>;
  subjects_with_open_defects: number;
  scenarios: number;
  scenarios_by_grading: Record<"service state" | "the answer", number>;
  adapters: AdapterFact[];
  docs: string[];
  surveys: string[];
  /**
   * Computed by `build_fixtures.py` from `taxonomy/failure-modes.json`. It was
   * exported and then declared nowhere for two taxonomy versions, so the one
   * taxonomy sentence on the site was hand-typed and said "ninety-five" while
   * this said 131.
   */
  taxonomy: TaxonomyFacts;
}
