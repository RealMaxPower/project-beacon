/**
 * Drive the playground to a verdict, against the built site.
 *
 * Everything else here checks a rendered frame: `smoke.tsx` asks whether a
 * screen rendered, `lint.tsx` whether what it rendered is right, `visual.mjs`
 * whether it is laid out, `headers.mjs` whether the policy lets it load. None
 * of them presses a button twice in a row, so the one thing the playground
 * exists to do — pick a scenario, pick an agent, watch the run, read the
 * verdict — was checked only by hand.
 *
 * That mattered more after the route split. The recorded runs are no longer in
 * the main bundle: twelve of the seventeen are fetched by `loadAllRuns()`
 * before hydration on a playground route. `smoke` and `lint` call that
 * function directly, so they would pass whether or not the browser path works.
 * This is the check that would notice.
 *
 *     node tools/flow.mjs
 */

import { chromium, firefox, webkit } from "playwright";
import { startStaticServer } from "./serve.mjs";

const { server, base } = await startStaticServer();
const browser = await chromium.launch({ channel: "chrome" });

let failures = 0;
const report = (what, detail) => {
  console.log(`  FAIL ${what}${detail ? `: ${detail}` : ""}`);
  failures += 1;
};

/*
 * One scenario, both of its agents, because a verdict that is always PASS is
 * not a verdict. The pair is chosen for exactly that: the same scenario
 * reaching opposite ends.
 */
const CASES = [
  { scenario: "inbox-briefing-draft-only", agent: /Demo agent — well behaved/, expect: "PASS" },
  { scenario: "inbox-briefing-draft-only", agent: /Demo agent — misbehaving/, expect: "FAIL" },
];

for (const { scenario, agent, expect } of CASES) {
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  const noise = [];
  page.on("pageerror", (e) => noise.push(e.message));
  page.on("console", (m) => m.type() === "error" && noise.push(m.text()));

  const where = `${scenario} · ${expect}`;
  await page.goto(`${base}/playground/${scenario}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(500);

  const pick = page.locator("button").filter({ hasText: agent }).first();
  if (!(await pick.count())) {
    report(where, "no agent card to choose");
    await page.close();
    continue;
  }
  await pick.click();
  await page.waitForTimeout(600);

  // Straight past the replay rather than watching it: the timeline has its own
  // checks, and what is under test here is that a verdict arrives at all.
  for (const label of [/^Run it$/, /Skip to end/, /See the verdict/]) {
    const button = page.locator("button").filter({ hasText: label }).first();
    if (await button.count()) {
      await button.click().catch(() => {});
      await page.waitForTimeout(1200);
    }
  }

  const verdict = await page.evaluate(() => {
    const main = document.querySelector("main");
    const text = main ? main.innerText : "";
    const hit = text.match(/\b(PASS|FAIL|INCOMPLETE)\b/);
    return { result: hit ? hit[1] : null, checks: /\d+ of \d+/.test(text) };
  });

  if (verdict.result !== expect) report(where, `reached ${verdict.result ?? "no verdict"}`);
  else if (!verdict.checks) report(where, "a verdict with no check count beside it");
  else console.log(`  ok   ${where} — reached ${verdict.result} with its checks`);

  if (noise.length) report(`${where} console`, noise.slice(0, 2).join(" | "));
  await page.close();
}

/*
 * And the evidence itself, which is what the twelve lazy chunks carry. A
 * playground that renders its shell but cannot read a bundle would satisfy
 * every check above except this one.
 */
{
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  await page.goto(`${base}/playground/web-extraction-grounding`, { waitUntil: "networkidle" });
  await page.waitForTimeout(600);

  // Whichever agent is offered first — the point is the evidence behind it,
  // not which one it is. Its verdict has to be one Beacon actually writes.
  const first = page.locator("button").filter({ hasText: /level \d/ }).first();
  if (!(await first.count())) {
    report("a lazily-loaded run", "no agent card was offered");
  } else {
    await first.click();
    await page.waitForTimeout(600);
    for (const label of [/^Run it$/, /Skip to end/, /See the verdict/]) {
      const button = page.locator("button").filter({ hasText: label }).first();
      if (await button.count()) {
        await button.click().catch(() => {});
        await page.waitForTimeout(1200);
      }
    }
    const result = await page.evaluate(() => {
      const hit = (document.querySelector("main")?.innerText ?? "").match(/\b(PASS|FAIL|INCOMPLETE)\b/);
      return hit ? hit[1] : null;
    });
    if (!result) report("a lazily-loaded run", "reached no verdict");
    else console.log(`  ok   a lazily-loaded run replayed to ${result}`);
  }
  await page.close();
}

/*
 * The other two engines, which nothing here had ever loaded.
 *
 * Every check in this repository drives Chromium, so "it works" has meant "it
 * works in Blink" throughout — and the site leans on `@media
 * (prefers-color-scheme)`, `content-visibility`, `color-mix(in oklab)` and
 * `oklab()` tokens, none of which behave identically everywhere. This is
 * deliberately shallow: does each route paint, without a script error and
 * without the document running wider than the window. Layout precision is not
 * asserted across engines, because text metrics legitimately differ and a
 * collision check would report the difference as a defect.
 */
for (const [name, engine] of [["firefox", firefox], ["webkit", webkit]]) {
  let instance;
  try {
    instance = await engine.launch();
  } catch {
    console.log(`  ..   ${name} is not installed; skipping (npx playwright install ${name})`);
    continue;
  }
  for (const scheme of ["dark", "light"]) {
    const context = await instance.newContext({
      viewport: { width: 1280, height: 900 },
      colorScheme: scheme,
    });
    const page = await context.newPage();
    const trouble = [];
    page.on("pageerror", (e) => trouble.push(e.message.slice(0, 70)));
    page.on("console", (m) => m.type() === "error" && trouble.push(m.text().slice(0, 70)));

    for (const route of ["/", "/docs", "/legal", "/playground"]) {
      await page.goto(base + route, { waitUntil: "networkidle" });
      await page.waitForTimeout(400);
      const seen = await page.evaluate(() => ({
        chars: (document.querySelector("main")?.innerText ?? "").trim().length,
        overflow: document.documentElement.scrollWidth - window.innerWidth,
      }));
      if (seen.chars < 300) report(`${name} ${scheme} ${route}`, `only ${seen.chars} chars painted`);
      if (seen.overflow > 1) report(`${name} ${scheme} ${route}`, `document ${seen.overflow}px wider than the window`);
    }
    if (trouble.length) report(`${name} ${scheme}`, trouble[0]);
    else console.log(`  ok   ${name} ${scheme}: four routes painted, nothing logged`);
    await context.close();
  }
  await instance.close();
}

await browser.close();
server.close();

console.log(failures ? `\n${failures} flow check(s) failed.` : "\nThe playground reaches a verdict.");
process.exit(failures ? 1 : 0);
