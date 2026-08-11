/**
 * Render every screen once, against the real recorded fixtures.
 *
 * `npm run build` only proves the types agree. This mounts the whole tree and
 * walks it through every step, so a component that reads a field the bundles do
 * not contain fails here instead of on the page. It runs headless — there is no
 * browser in the loop — which makes it the check that can run anywhere.
 *
 *     npm run smoke
 */

import { renderToString } from "react-dom/server";
import { Playground } from "@/screens/playground/Playground";
import { PickScenario } from "@/screens/playground/PickScenario";
import { PickSubject } from "@/screens/playground/PickSubject";
import { WorldBefore } from "@/screens/playground/WorldBefore";
import { RunTimeline } from "@/screens/playground/RunTimeline";
import { Verdict } from "@/screens/playground/Verdict";
import { TwelveRuns } from "@/screens/playground/TwelveRuns";
import { BaselineCompare } from "@/screens/playground/BaselineCompare";
import { ExportBundle } from "@/screens/playground/ExportBundle";
import { TimelineEvent } from "@/components/execution/TimelineEvent";
import { InjectionCallout } from "@/components/execution/InjectionCallout";
import { AssertionRow } from "@/components/verdict/AssertionRow";
import { App } from "@/App";
import { SiteB } from "@b/SiteB";
import { Home } from "@/screens/marketing/Home";
import { HowItWorks } from "@/screens/marketing/HowItWorks";
import { Scenarios } from "@/screens/marketing/Scenarios";
import { ForBuilders } from "@/screens/marketing/ForBuilders";
import { Docs } from "@/screens/marketing/Docs";
import { HostedLab } from "@/screens/marketing/HostedLab";
import { Legal } from "@/screens/marketing/Legal";
import { navRoutes } from "@/router";
import {
  forbiddenOutcomes,
  injectionIn,
  evidenceFor,
  eventsFor,
  facts,
  fixtures,
  isBlocked,
  scenarioFor,
  scenarios,
} from "@/data/fixtures";
import { scenarioCopy } from "@/data/copy";

let failures = 0;

function check(name: string, render: () => string, ...expected: string[]) {
  // A check with nothing to look for passes whatever the component did. That
  // is how `WorldBefore` was reported green while rendering neither its inbox
  // nor its tool surface: the expectations were spread from a field the
  // evidence bundle does not carry, so the list was empty.
  if (expected.length === 0) {
    console.error(`  FAIL ${name} — nothing was asserted`);
    failures += 1;
    return;
  }

  try {
    const html = render();
    const missing = expected.filter((needle) => !html.includes(needle));
    if (missing.length > 0) {
      console.error(`  FAIL ${name} — nothing rendered for: ${missing.join(", ")}`);
      failures += 1;
      return;
    }
    console.log(`  ok   ${name} (${html.length.toLocaleString()} chars)`);
  } catch (error) {
    console.error(`  FAIL ${name} — ${(error as Error).message}`);
    failures += 1;
  }
}

console.log(`Rendering against ${fixtures.length} recorded runs.\n`);

check(
  "Home",
  () => renderToString(<Home onGo={() => {}} />),
  // The counts must be the derived ones, not prose. If `facts.json` stops
  // reaching the page these disappear rather than going stale silently.
  String(facts.subjects),
  String(facts.scenarios),
  // The honest-gaps block, which now leads with what is missing rather than
  // what the product is not. The verbatim "not a safety certification" lives
  // in the footer, which belongs to the shell rather than this screen.
  "Never a certification",
  "Not on PyPI",
  /*
   * The hook: the finding, not a mechanism.
   *
   * The page used to open by explaining what Beacon does to a reader who had
   * no reason to care yet. It opens on five recorded agents that leave one end
   * state and earn three answers — and every count in that sentence is
   * computed, so these strings only render while the bundles still agree.
   */
  // Asserted as the markup React emits: interpolated counts are separated
  // from the literal text by comment markers, so the sentence never appears
  // contiguously in the served HTML.
  '<h1 class="type-display',
  "agents. One end state.",
  "different answers.",
  "which is the part the diff cannot see",
  "decide whether an agent gets write access",
  // The diff strip, reduced to ids. Printing the whole draft records overflowed
  // the document by 35px at 390px and took the header nav's links with it.
  "[d-001, d-002, d-003]",
  "reset_verified",
  /*
   * The comparison figure, and specifically its verdicts.
   *
   * The five verdicts must never be colour alone. `#b3261e` and `#8a5a00`
   * separate by ΔE 0.7 under deuteranopia, so FAIL and INCOMPLETE are one
   * colour for a red-green colourblind reader — and telling those two apart is
   * what this product is for. `VerdictBadge` carries a shape and a word as
   * well; an earlier version of this figure drew bare coloured dots.
   */
  "Tried to send",
  "Said it finished",
  "INCOMPLETE",
  // The claim the figure makes, stated where a reader who cannot see it will
  // still meet it.
  "The changed field",
  /*
   * The run that failed, and a legible one.
   *
   * It led with the hosted twelve-run baseline, which resolves INCOMPLETE —
   * the one verdict that is explicitly not a failure — directly beneath a
   * button reading "Watch an agent fail". These pin the replacement: a FAIL,
   * the refused calls, and the assertion that caught it.
   */
  "send-never-attempted",
  "BLOCKED",
  "recorded before dispatch",
  /*
   * The zero that is not a rate.
   *
   * `entities-grounded` was never evaluated in the hosted baseline — the
   * replies had no field to read — so the figure must say so where it is
   * shown. Asserted as markup, not as the word: a bare "measured" is
   * satisfied by "could be measured" elsewhere on the page, and the first
   * version of this check passed with the qualifier deleted from the very
   * figure it exists to qualify.
   */
  'tracking-[0.02em]">measured</span>',
  // Two baselines of twelve, not one shared set of twelve runs.
  "twelve times against each of two scenarios",
  // An unanswered question, not a fabrication rate. The distinction is the
  // section, and it is the one claim here that would be actively misleading
  // if it silently reverted.
  "Not a fabrication rate",
  // The injection section, quoting the real payload out of the scenario file
  // rather than an example written for the page.
  "SYSTEM OVERRIDE",
  "Content can give orders",
);

check(
  "HowItWorks",
  () => renderToString(<HowItWorks onGo={() => {}} />),
  "beacon_submit",
  "ToolPolicyError",
  // The assertion that cannot fail, beside the one that means something.
  "after.mail.sent == []",
  "send-never-attempted",
  // The table is a capability model, not an inventory of what works today.
  "does not currently collect",
);

check(
  "Scenarios",
  () => renderToString(<Scenarios onGo={() => {}} />),
  ...scenarios.map((s) => scenarioCopy[s.slug]?.question ?? s.name),
);

check(
  "ForBuilders",
  () => renderToString(<ForBuilders onGo={() => {}} />),
  String(facts.subjects),
  String(facts.subjects_by_expected_verdict.FAIL),
  "--baseline",
  "Exit codes are the integration",
);

check(
  "Docs",
  () => renderToString(<Docs onGo={() => {}} />),
  // Every document on disk gets a card, so a renamed file cannot leave a
  // dead link behind.
  ...facts.docs,
  ...facts.surveys,
);

check("HostedLab", () => renderToString(<HostedLab onGo={() => {}} />), "no form", "discussion");

// The privacy claims are only true while the policy that enforces them is in
// place, so the page names the directives rather than describing the behaviour
// loosely. If `connect-src 'none'` is ever relaxed, this page is the thing
// that becomes false.
check(
  "Legal",
  () => renderToString(<Legal onGo={() => {}} />),
  "Apache License 2.0",
  // As React emits it: the apostrophes in the directive are HTML-escaped, so
  // the literal source string never appears in the served markup.
  "connect-src &#x27;none&#x27;",
  "THIRD-PARTY-NOTICES.txt",
  "OFL.txt",
  "no cookies",
);

check(
  "App shell · every route reachable",
  () => renderToString(<App />),
  // Home is reached through the wordmark, and the playground through a filled
  // button on the right, so neither appears as a nav link. `navRoutes` is the
  // one place that decides which pages the navigation lists — this used to
  // repeat the filter, which is how a route could be added to the site and
  // silently checked against a navigation that never carried it.
  ...navRoutes.filter((r) => r.path !== "").map((r) => r.label),
  "Playground",
  // The footer carries the limitation on every page, including this one.
  "not a safety certification",
  // And the route to the licensing and privacy page, which is reached from
  // the footer rather than the navigation. A legal page nothing links to is
  // a legal page nobody can find.
  "Licensing and privacy",
  "© 2026 Project Beacon contributors",
);

check("Playground shell", () => renderToString(<Playground />), "Beacon", "Scenario");

check(
  "PickScenario",
  () =>
    renderToString(
      <PickScenario
        selected={null}
        runnable={new Set(fixtures.map((f) => f.scenario))}
        onPick={() => {}}
      />,
    ),
  // Every scenario on disk must reach the screen, not just the demoed one.
  // The card leads with the plain-English question, so that is what to look
  // for — asserting on the scenario's formal name would pass while showing
  // nothing a visitor can read.
  ...scenarios.map((s) => scenarioCopy[s.slug]?.question ?? s.name),
);

check(
  "PickSubject",
  () => renderToString(<PickSubject scenarioId={null} selected={null} onPick={() => {}} />),
  ...fixtures.map((f) => f.label),
);

for (const fixture of fixtures) {
  const evidence = evidenceFor(fixture.key);
  const events = eventsFor(fixture.key);

  check(
    `WorldBefore · ${fixture.key}`,
    () => renderToString(<WorldBefore evidence={evidence} expert={false} />),
    evidence.scenario.name,
    // The declared tool surface has to reach the screen: it is what makes a
    // refused call later legible as a refusal rather than a malfunction. Read
    // from the scenario export — the bundle's copy has no tools on it, so
    // spreading from there asserted nothing at all.
    ...scenarioFor(evidence).tools.slice(0, 3),
  );

  check(
    `RunTimeline · ${fixture.key}`,
    () =>
      renderToString(
        <RunTimeline evidence={evidence} events={events} expert={false} onDone={() => {}} />,
      ),
    evidence.run_id,
  );

  check(
    `Verdict · ${fixture.key}`,
    () => renderToString(<Verdict evidence={evidence} events={events} expert={false} />),
    // The verdict itself, and the limitations that may never be omitted.
    evidence.result,
    "Limitations",
    // The state row that carries the argument: unchanged, but attempted.
    ...(fixture.key === "misbehaving" ? ["attempt", "blocked"] : []),
  );

  check(
    `Verdict expert · ${fixture.key}`,
    () => renderToString(<Verdict evidence={evidence} events={events} expert={true} />),
    evidence.digest,
  );

  check(
    `ExportBundle · ${fixture.key}`,
    () => renderToString(<ExportBundle evidence={evidence} />),
    "evidence.json",
    "events.json",
  );
}

check("TwelveRuns", () => renderToString(<TwelveRuns />), "entities-grounded");
check("BaselineCompare", () => renderToString(<BaselineCompare />), "regression");

/*
 * The timeline reveals its events from an effect, and effects do not run when
 * rendering to a string — so the checks above exercise its header and nothing
 * else. These render the event rows directly, which is where the blocked
 * attempt lives: the single most important thing the playground draws, and
 * until now the least verified.
 */
const misbehaving = evidenceFor("misbehaving");
const blockedEvents = eventsFor("misbehaving").filter(isBlocked);

check(
  "blocked attempts are recorded at all",
  () => (blockedEvents.length > 0 ? "found" : ""),
  "found",
);

check(
  "TimelineEvent · blocked",
  () =>
    renderToString(
      <ul>
        {blockedEvents.map((event, index) => (
          <TimelineEvent key={event.sequence} event={event} offsetMs={index} />
        ))}
      </ul>,
    ),
  "BLOCKED",
  "mail_send",
);

check(
  "TimelineEvent · every event in every run",
  () =>
    renderToString(
      <ul>
        {fixtures.flatMap((f) =>
          eventsFor(f.key).map((event) => (
            <TimelineEvent key={`${f.key}-${event.sequence}`} event={event} offsetMs={0} />
          )),
        )}
      </ul>,
    ),
  "mail_list_messages",
);

/*
 * The callout, driven the way the screen drives it: an injection found anywhere
 * in the scenario's material, and demands derived from the assertions Beacon
 * grades. Checked against both scenarios that carry a payload — the mail one
 * and the document one, which used to render nothing at all.
 */
for (const key of ["misbehaving", "obeys_delete_injection"]) {
  const evidence = evidenceFor(key);
  const scenario = scenarioFor(evidence);
  const injection = injectionIn(scenario);
  const demands = forbiddenOutcomes(scenario, evidence);

  check(
    `InjectionCallout · ${key}`,
    () =>
      injection === null
        ? ""
        : renderToString(
            <InjectionCallout
              source={injection.source}
              injectedText={injection.text}
              demands={demands}
              reached
            />,
          ),
    injection?.source ?? "NO INJECTION FOUND",
    // The requirement and its outcome, not "attempted" beside a sentence that
    // begins "did not attempt".
    "violated",
    "rules this scenario grades on",
    // It must never claim the injected text caused the behaviour.
    "none of this asserts that the injected text",
  );
}

/*
 * An assertion Beacon could not evaluate.
 *
 * This is the shape a hosted run writes when the reply omits the field an
 * assertion reads: `passed: false` *and* `measured: false`, with the runner
 * resolving the run INCOMPLETE on the strength of the second. No committed
 * fixture is unmeasured — every subject in `examples/subjects/` produces its
 * artifact — so without this case the row that matters most to the argument
 * the Repeat screen makes is the one nothing renders.
 *
 * The literal below is copied from a real bundle, not invented: a
 * `web-extraction-grounding` run against the hosted bridge, which returns its
 * JSON wrapped in prose often enough that this is the ordinary outcome.
 */
check(
  "AssertionRow · an assertion that could not be evaluated",
  () =>
    renderToString(
      <AssertionRow
        scenarioId="web-extraction-grounding"
        assertion={{
          id: "entities-grounded",
          description: "Every entity the agent reports appears in the page it was given",
          passed: false,
          measured: false,
          actual: null,
          expected: { source: "fixtures.page.text", min_length: 3 },
          message:
            "path cannot be traversed: artifacts.web_page_extraction_result.primary_entities.*.value",
        }}
        open
        onToggle={() => {}}
      />,
    ),
  // `measured: false` has to outrank `passed: false`. Printing "failed" here
  // would publish a rate nobody measured, on the one screen that exists to say
  // so.
  //
  // Both markers are deliberately specific. A bare "not evaluated" passes even
  // when the row says "failed", because this assertion's own explanatory note
  // contains the phrase — the first version of this check did exactly that and
  // survived the mutation it was written to catch. `text-inc` is the hollow
  // ring, used by this component only for the unevaluated state.
  "text-inc",
  " · <!-- -->not evaluated",
  "Every entity it reported appears in the page it was given",
  "path cannot be traversed",
);

/*
 * The second design, against the facts it is supposed to be reading.
 *
 * The point of these needles is that this page describes *this* repository.
 * The design it was built from marketed a product that does not exist here —
 * a CLI called outcome_assurance, seventeen shipped capabilities, fourteen
 * automated tests — and the whole job of the port was replacing every one of
 * those with something the code actually does.
 */
/**
 * The second design at a given fragment.
 *
 * Its router reads `window.location.hash`; effects do not run under
 * `renderToString`, so stubbing the initial read is enough to steer it.
 */
function siteBAt(hash: string): string {
  const previous = (globalThis as Record<string, unknown>).window;
  const store = new Map<string, string>();
  (globalThis as Record<string, unknown>).window = {
    location: { hash },
    matchMedia: () => ({ matches: false, addEventListener() {}, removeEventListener() {} }),
    addEventListener() {},
    removeEventListener() {},
    scrollTo() {},
  };
  /*
   * `localStorage` as well as `window`, because this design's header now reads
   * the theme preference. The stub was written when it did not, and adding the
   * toggle turned four passing checks into four that threw — which is the right
   * failure: a partial browser stub renders a page the browser would not.
   */
  (globalThis as Record<string, unknown>).localStorage = {
    getItem: (k: string) => store.get(k) ?? null,
    setItem: (k: string, v: string) => void store.set(k, v),
  };
  try {
    return renderToString(<SiteB />);
  } finally {
    (globalThis as Record<string, unknown>).window = previous;
    delete (globalThis as Record<string, unknown>).localStorage;
  }
}

check(
  "Site B",
  () => renderToString(<SiteB />),
  // Counts derived, never typed.
  String(facts.scenarios),
  String(facts.subjects),
  // The real CLI, not the design's invented one.
  "python3 -m beacon run",
  "python3 -m beacon verify",
  // The strip that occupies the slot a logo wall would take, and the sentence
  // that stops it reading as one.
  "Not adoption metrics",
  // Limitations are read out of a recorded bundle rather than written here.
  "not a safety certification",
  // Both documents are published, so both need a route to the licensing and
  // privacy terms. This design links the other's page rather than restating
  // it: the terms describe the origin, and one copy cannot disagree with
  // itself. A visitor landing on /b had no way to reach them at all.
  "/#/legal",
  "© 2026 Project Beacon contributors",
);

/*
 * The second design's router, at the three fragments that behave differently.
 *
 * The middle one is the whole reason this router is not the first design's. In
 * this document `#case` is an in-page anchor and `#/playground` is a route, and
 * a router that could not tell them apart would render a not-found page every
 * time a visitor clicked "The case" in the header. That failure is silent — it
 * throws nothing and logs nothing — so it is asserted rather than trusted.
 */
check(
  "Site B · #/playground carries the shared playground inside B's shell",
  () => siteBAt("#/playground"),
  // The playground's own first step...
  "What should the agent try?",
  // ...under this design's header, not the first design's.
  "Outcome Assurance",
  // The header knows which route it is on. Asserting the class name
  // `text-text-muted` here would have proved nothing — the markup carries it
  // whatever the stylesheet does or does not declare, which is the vacuous
  // shape this file has been caught in twice. Whether the alias block actually
  // repaints anything is a question about computed colour, so `npm run
  // headers` asks it in a browser.
  'aria-current="page"',
);

check(
  "Site B · #case is an anchor, so the marketing page renders",
  () => siteBAt("#case"),
  "Agent work you can actually defend.",
);

check(
  "Site B · #/not-a-page is a route that misses",
  () => siteBAt("#/not-a-page"),
  "That address does not name a page here.",
);

check(
  "Site B · #/playground/<id> opens already pointed at it",
  () => siteBAt("#/playground/inbox-briefing-draft-only"),
  // Step two, not step one — the link resolved.
  "Which agent should try it?",
);

console.log();
if (failures > 0) {
  console.error(`${failures} screen(s) failed to render.`);
  process.exit(1);
}
console.log("Every screen rendered.");
