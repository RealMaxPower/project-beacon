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
import { SiteB } from "@b/SiteB";
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

/**
 * A semantic colour may not travel alone.
 *
 * `tokens-b.css` has stated this rule in prose since it was written, and said
 * plainly that nothing enforced it: four accents at AA on a warm light ground
 * leave `ok` against `review` at ΔE 6.1 under protanopia, inside the band the
 * palette validator permits *only* when a second encoding is present. The file
 * promised the check would land with the first section that had anything for it
 * to examine. There are eleven of them now.
 *
 * The rule: an element carrying one of the four accents — as text colour, as a
 * border, by class or by inline style — must have a word. Its own text counts;
 * so does its parent's, because a coloured mark beside a label is exactly the
 * shape the rule permits and is how the pipeline's rings and the verdict chips
 * are built. What fails is a coloured element sitting in a container with no
 * text anywhere in it, which is a swatch that means something to whoever wrote
 * it and nothing to a reader who cannot see the hue.
 *
 * Scoped to this design's vocabulary. The shared playground is styled in the
 * first design's names and carries its own encoding — every verdict there
 * ships a glyph and a word — and that is checked by the palette work behind
 * `AssertionRow` rather than here.
 */
const ACCENT = /(?:text|border)-b-(?:ok|bad|review|src)\b|var\(--b-(?:ok|bad|review|src)\)/;

function auditColourNeverAlone(where: string, html: string) {
  interface Frame {
    accent: boolean;
    text: string;
    parent: Frame | null;
  }

  const root: Frame = { accent: false, text: "", parent: null };
  const stack: Frame[] = [root];
  const naked: Frame[] = [];
  const VOID = new Set([
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
  ]);

  const token = /<\/?([a-zA-Z][a-zA-Z0-9-]*)([^>]*)>|([^<]+)/g;
  for (const [whole, tag, attrs, text] of html.matchAll(token)) {
    if (text !== undefined) {
      const words = text.replace(/&[a-z]+;/g, " ").trim();
      if (words) for (const frame of stack) frame.text += words + " ";
      continue;
    }
    // Ask the match whether it is a closing tag. The first version of this
    // computed the position of the slash from lastIndex and the lengths of the
    // captures, got it wrong, and so never popped the stack — which made every
    // element a child of the last one that opened, gave every accent a parent
    // full of text, and reported a clean page no matter what was on it.
    if (whole.startsWith("</")) {
      if (stack.length > 1) stack.pop();
      continue;
    }
    const frame: Frame = {
      accent: ACCENT.test(attrs),
      text: "",
      parent: stack[stack.length - 1],
    };
    // An accessible name is a word, even when the element shows none.
    const label = /aria-label="([^"]+)"/.exec(attrs);
    if (label) frame.text += label[1] + " ";
    if (frame.accent) naked.push(frame);
    if (!VOID.has(tag.toLowerCase()) && !attrs.trimEnd().endsWith("/")) stack.push(frame);
  }

  const alone = naked.filter(
    (f) => !f.text.trim() && !(f.parent && f.parent.text.trim()),
  );
  if (alone.length) {
    report(
      where,
      "a semantic colour with no word beside it",
      `${alone.length} element(s); the palette separates ok from review by ΔE 6.1 on paper, which needs a second encoding`,
    );
  }
}

function audit(where: string, html: string) {
  auditColourNeverAlone(where, html);
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
function withHash<T>(hash: string, render: () => T): T {
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
    return render();
  } finally {
    (globalThis as Record<string, unknown>).window = previous;
    delete (globalThis as Record<string, unknown>).localStorage;
  }
}

const shellAt = (hash: string) => withHash(hash, () => renderToStaticMarkup(<App />));

/*
 * The second design at a given fragment.
 *
 * Its router reads `window.location.hash` exactly as the first one's does, so
 * the same stub steers it — and the fragments below are chosen for the one
 * thing this router does that the other cannot: `#case` has no leading slash
 * and must render the marketing page, not a not-found. That distinction is
 * invisible to a check that only ever renders the default.
 */
const siteBAt = (hash: string) => withHash(hash, () => renderToStaticMarkup(<SiteB />));

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
  /*
   * The second design, at every fragment its router distinguishes.
   *
   * The landmark rule below matters more here than anywhere: this design
   * brings its own header, main and footer, and it now wraps the first
   * design's playground — which brings its own `<main>` in the shell it was
   * written for. Two mains is exactly the defect that rule exists to catch,
   * and it is why the playground route is audited rather than assumed.
   */
  ["Site B · marketing", () => siteBAt("")],
  ["Site B · #case anchor", () => siteBAt("#case")],
  ["Site B · #/playground", () => siteBAt("#/playground")],
  [
    "Site B · #/playground/<id>",
    () => siteBAt("#/playground/inbox-briefing-draft-only"),
  ],
  ["Site B · #/playground/<unknown>", () => siteBAt("#/playground/no-such-scenario")],
  ["Site B · #/docs", () => siteBAt("#/docs")],
  ["Site B · #/not-a-page", () => siteBAt("#/not-a-page")],
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
