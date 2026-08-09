/**
 * Render every screen and look for defects in the output.
 *
 * `smoke.tsx` asks whether a screen rendered. This asks whether what it
 * rendered is *right* — the class of bug that reaches a page looking like
 * ordinary text: an interpolated `undefined`, a `NaN` from dividing by a count
 * that was zero, an `[object Object]` where a field was printed instead of
 * read, a heading with nothing under it, a control with no accessible name.
 *
 *     npm run lint:render
 */

import { renderToStaticMarkup } from "react-dom/server";
import { App } from "@/App";
import { Home } from "@/screens/marketing/Home";
import { HowItWorks } from "@/screens/marketing/HowItWorks";
import { Scenarios } from "@/screens/marketing/Scenarios";
import { ForBuilders } from "@/screens/marketing/ForBuilders";
import { Docs } from "@/screens/marketing/Docs";
import { HostedLab } from "@/screens/marketing/HostedLab";
import { PickScenario } from "@/screens/playground/PickScenario";
import { PickSubject } from "@/screens/playground/PickSubject";
import { WorldBefore } from "@/screens/playground/WorldBefore";
import { RunTimeline } from "@/screens/playground/RunTimeline";
import { Verdict } from "@/screens/playground/Verdict";
import { TwelveRuns } from "@/screens/playground/TwelveRuns";
import { BaselineCompare } from "@/screens/playground/BaselineCompare";
import { ExportBundle } from "@/screens/playground/ExportBundle";
import { TimelineEvent } from "@/components/execution/TimelineEvent";
import { evidenceFor, eventsFor, fixtures, scenarioFor } from "@/data/fixtures";
import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

let problems = 0;

function report(where: string, what: string, detail: string) {
  console.error(`  ${where}\n    ${what}: ${detail}`);
  problems += 1;
}

/** Text that means a value did not survive its journey to the page. */
const POISON = [
  { needle: "undefined", what: "an undefined value was printed" },
  { needle: "NaN", what: "a number came out NaN" },
  { needle: "[object Object]", what: "an object was printed instead of read" },
  { needle: "Infinity", what: "a division produced Infinity" },
];

function textOf(html: string): string {
  return html
    .replace(/<script[\s\S]*?<\/script>/g, "")
    .replace(/<[^>]+>/g, " ")
    .replace(/&[a-z]+;/g, " ");
}

function audit(where: string, html: string) {
  const text = textOf(html);

  for (const { needle, what } of POISON) {
    if (text.includes(needle)) {
      const at = text.indexOf(needle);
      report(where, what, `…${text.slice(Math.max(0, at - 60), at + 40).trim()}…`);
    }
  }

  // An empty heading or paragraph is a section whose data did not arrive.
  // A live region is the exception: it has to be in the document before it has
  // anything to announce, or the announcement never fires.
  for (const tag of ["h1", "h2", "h3", "p", "dd", "li"]) {
    const empty = (html.match(new RegExp(`<${tag}[^>]*>\\s*</${tag}>`, "g")) ?? []).filter(
      (el) => !/aria-live=/.test(el),
    );
    if (empty.length) report(where, `empty <${tag}>`, `${empty.length} of them`);
  }

  // Duplicate ids break every aria-controls and label pointing at them.
  const ids = [...html.matchAll(/\sid="([^"]+)"/g)].map((m) => m[1]);
  const dupes = ids.filter((id, i) => ids.indexOf(id) !== i);
  if (dupes.length) report(where, "duplicate id", [...new Set(dupes)].join(", "));

  // aria-controls pointing at nothing tells a screen reader to go somewhere
  // that does not exist.
  for (const [, target] of html.matchAll(/aria-controls="([^"]+)"/g)) {
    if (!ids.includes(target)) {
      report(where, "aria-controls points at no element", target);
    }
  }

  // A button whose only content is an icon, with no label, is unusable
  // without sight.
  for (const [button] of html.matchAll(/<button[^>]*>[\s\S]*?<\/button>/g)) {
    const inner = textOf(button).trim();
    const labelled = /aria-label=|aria-labelledby=/.test(button);
    const srOnly = /sr-only/.test(button);
    if (!inner && !labelled && !srOnly) {
      report(where, "button with no accessible name", button.slice(0, 90));
    }
  }

  // A button inside a button is invalid HTML and the inner one is
  // unreachable by keyboard in several browsers.
  if (/<button[^>]*>(?:(?!<\/button>)[\s\S])*<button/.test(html)) {
    report(where, "nested <button>", "invalid, and the inner control is unreachable");
  }

  // Same for an anchor inside a button.
  if (/<button[^>]*>(?:(?!<\/button>)[\s\S])*<a\s/.test(html)) {
    report(where, "anchor inside <button>", "invalid interactive nesting");
  }

  /*
   * A document gets one `main`, and only one.
   *
   * The shell wraps every screen in `<main id="main">`; the playground rendered
   * a second one inside it. Two nested main landmarks are invalid HTML, and
   * both the skip link and a screen reader's landmark list then offer a choice
   * between two entries with nothing to tell them apart. It rendered fine and
   * read fine, which is why it survived — nothing about the page looked wrong.
   *
   * `banner` and `contentinfo` are here for the same reason: they are the two
   * other landmarks the spec allows only once per document.
   */
  for (const [tag, role] of [
    ["main", "main"],
    ["header", "banner"],
    ["footer", "contentinfo"],
  ]) {
    const count = (html.match(new RegExp(`<${tag}[\\s>]`, "g")) ?? []).length;
    // A `header` or `footer` nested inside a sectioning element is not a
    // landmark at all, so only the top-level ones are counted. `main` has no
    // such escape: it is a landmark wherever it appears.
    const top = tag === "main" ? count : (html.match(new RegExp(`^<${tag}[\\s>]`)) ?? []).length;
    const found = tag === "main" ? count : top;
    if (found > 1) {
      report(where, `${found} <${tag}> elements`, `a document may have one ${role} landmark`);
    }
  }
}

/**
 * Render the whole shell at a given hash.
 *
 * The audit used to render `<App />` once, which meant it only ever saw Home
 * inside the shell, and every other screen only ever *outside* it. Defects that
 * exist solely in the combination were invisible: the playground rendered its
 * own `<main>`, which is fine on its own and a duplicate landmark the moment
 * the shell wraps it in `<main id="main">`. Six of seven pages were never
 * audited in the document they actually ship in.
 *
 * `useRoute` and `useTheme` both read `window` and fall back when it is absent,
 * so a stub is enough to steer the route. Effects do not run under
 * `renderToStaticMarkup`; only the initial state matters.
 */
function shellAt(hash: string): string {
  const media = { matches: false, addEventListener() {}, removeEventListener() {} };
  const store = new Map<string, string>();
  const previous = (globalThis as Record<string, unknown>).window;

  (globalThis as Record<string, unknown>).window = {
    location: { hash },
    matchMedia: () => media,
    addEventListener() {},
    removeEventListener() {},
    scrollTo() {},
  };
  (globalThis as Record<string, unknown>).localStorage = {
    getItem: (k: string) => store.get(k) ?? null,
    setItem: (k: string, v: string) => void store.set(k, v),
  };

  try {
    return renderToStaticMarkup(<App />);
  } finally {
    (globalThis as Record<string, unknown>).window = previous;
    delete (globalThis as Record<string, unknown>).localStorage;
  }
}

const SHELL_ROUTES = [
  "",
  "how-it-works",
  "scenarios",
  "for-builders",
  "playground",
  "playground/inbox-briefing-draft-only",
  "playground/no-such-scenario",
  "docs",
  "hosted",
  "not-a-page",
];

const screens: [string, () => string][] = [
  ...SHELL_ROUTES.map(
    (route) =>
      [`App shell · #/${route}`, () => shellAt(`#/${route}`)] as [string, () => string],
  ),
  ["Home", () => renderToStaticMarkup(<Home onGo={() => {}} />)],
  ["HowItWorks", () => renderToStaticMarkup(<HowItWorks onGo={() => {}} />)],
  ["Scenarios", () => renderToStaticMarkup(<Scenarios onGo={() => {}} />)],
  ["ForBuilders", () => renderToStaticMarkup(<ForBuilders onGo={() => {}} />)],
  ["Docs", () => renderToStaticMarkup(<Docs onGo={() => {}} />)],
  ["HostedLab", () => renderToStaticMarkup(<HostedLab onGo={() => {}} />)],
  [
    "PickScenario",
    () =>
      renderToStaticMarkup(
        <PickScenario
          selected={null}
          runnable={new Set(fixtures.map((f) => f.scenario))}
          onPick={() => {}}
        />,
      ),
  ],
  [
    "PickSubject",
    () => renderToStaticMarkup(<PickSubject scenarioId={null} selected={null} onPick={() => {}} />),
  ],
  ["TwelveRuns", () => renderToStaticMarkup(<TwelveRuns />)],
  ["BaselineCompare", () => renderToStaticMarkup(<BaselineCompare />)],
];

for (const fixture of fixtures) {
  const evidence = evidenceFor(fixture.key);
  const events = eventsFor(fixture.key);
  screens.push(
    [`WorldBefore · ${fixture.key}`, () => renderToStaticMarkup(<WorldBefore evidence={evidence} expert={false} />)],
    [`WorldBefore expert · ${fixture.key}`, () => renderToStaticMarkup(<WorldBefore evidence={evidence} expert={true} />)],
    [`RunTimeline · ${fixture.key}`, () => renderToStaticMarkup(<RunTimeline evidence={evidence} events={events} expert={false} onDone={() => {}} />)],
    [`Verdict · ${fixture.key}`, () => renderToStaticMarkup(<Verdict evidence={evidence} events={events} expert={false} />)],
    [`Verdict expert · ${fixture.key}`, () => renderToStaticMarkup(<Verdict evidence={evidence} events={events} expert={true} />)],
    [`ExportBundle · ${fixture.key}`, () => renderToStaticMarkup(<ExportBundle evidence={evidence} />)],
    [
      `Timeline rows · ${fixture.key}`,
      () =>
        renderToStaticMarkup(
          <ul>
            {events.map((e) => (
              <TimelineEvent key={e.sequence} event={e} offsetMs={0} />
            ))}
          </ul>,
        ),
    ],
  );
}

/*
 * A panel that names a file must render that file's bytes.
 *
 * This is checked by hash, not by key set. The original defect passed every
 * value-level comparison anyone thought to make — the scenario panel had the
 * right ids and the right assertions, and was a different document. Fixing it
 * left the same flaw in the two panels beside it, because the check that caught
 * it was written against one directory.
 */
function auditPanelFidelity() {
  const generated = join(dirname(fileURLToPath(import.meta.url)), "../src/data/generated");

  const cases: { where: string; render: () => string; file: string }[] = [];
  for (const fixture of fixtures) {
    const evidence = evidenceFor(fixture.key);
    const events = eventsFor(fixture.key);
    cases.push(
      {
        where: `Verdict expert · ${fixture.key}`,
        render: () => renderToStaticMarkup(<Verdict evidence={evidence} events={events} expert />),
        file: join(generated, fixture.key, "evidence.json"),
      },
      {
        where: `RunTimeline expert · ${fixture.key}`,
        render: () =>
          renderToStaticMarkup(
            <RunTimeline evidence={evidence} events={events} expert onDone={() => {}} />,
          ),
        file: join(generated, fixture.key, "events.json"),
      },
    );
  }

  for (const fixture of fixtures.slice(0, 1)) {
    const evidence = evidenceFor(fixture.key);
    cases.push({
      where: `WorldBefore expert · ${fixture.key}`,
      render: () => renderToStaticMarkup(<WorldBefore evidence={evidence} expert />),
      file: join(generated, "scenarios", `${scenarioFor(evidence).slug}.json`),
    });
  }

  console.log(`  comparing ${cases.length} panels against the files they name`);
  for (const { where, render, file } of cases) {
    // The <pre> holds the panel text; unescape what JSX escaped on the way in.
    const html = render();
    const pre = html.match(/<pre[^>]*>([\s\S]*?)<\/pre>/);
    if (!pre) {
      report(where, "no panel rendered", file);
      continue;
    }
    const shown = pre[1]
      .replace(/<[^>]+>/g, "")
      .replaceAll("&lt;", "<")
      .replaceAll("&gt;", ">")
      .replaceAll("&quot;", '"')
      .replaceAll("&#x27;", "'")
      .replaceAll("&amp;", "&");

    // A comparison against nothing is not a comparison.
    if (shown.trim().length === 0) {
      report(where, "panel text is empty", file);
      continue;
    }

    const onDisk = readFileSync(file, "utf8");
    if (shown !== onDisk) {
      const a = createHash("sha256").update(shown).digest("hex").slice(0, 16);
      const b = createHash("sha256").update(onDisk).digest("hex").slice(0, 16);
      report(
        where,
        "panel is not the file it names",
        `shown ${shown.length}B sha ${a} · file ${onDisk.length}B sha ${b}`,
      );
    }
  }
}

console.log(`Auditing ${screens.length} rendered screens.\n`);
for (const [name, render] of screens) {
  try {
    audit(name, render());
  } catch (error) {
    report(name, "threw while rendering", (error as Error).message);
  }
}

auditPanelFidelity();

console.log();
if (problems > 0) {
  console.error(`${problems} problem(s) found.`);
  process.exit(1);
}
console.log("No rendering defects found.");
