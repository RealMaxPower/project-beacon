/**
 * Load every page in a real browser and measure it.
 *
 * `lint.tsx` reads the DOM; this reads the *rendering*. They catch different
 * things, and the difference is not academic — the bug that shipped was a note
 * rendered after a card that already filled its grid row, so it printed on top
 * of the row below. Nothing about that is visible in the markup. It is a
 * question about boxes, and only a browser knows where the boxes are.
 *
 *     npm run visual
 *
 * What it measures, per page and per width:
 *
 *   - overlapping text, by intersecting the bounding rects of every element
 *     that renders text and is not an ancestor of the other;
 *   - horizontal overflow of the document, which is a scrollbar the design
 *     never asked for;
 *   - text clipped by a fixed height;
 *   - controls smaller than the 44px hit target the design system requires;
 *   - sticky furniture occupying more than 15% of the viewport;
 *   - controls hidden inside a scroll container that gives no cue it scrolls.
 *
 * Screenshots land in `.visual/` so a person can look at what it measured.
 */

import { chromium } from "playwright";
import { startStaticServer } from "./serve.mjs";
import { mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const SHOTS = join(ROOT, ".visual");
/*
 * The shared static server rather than `vite preview`.
 *
 * `vite preview` answers every path with `index.html`, which was right while
 * the site was one document and became wrong when each route became its own
 * prerendered file: this audit rendered the landing page at `/docs`, the
 * client hydrated the docs screen over it, and React reported a mismatch on
 * every page at every width. 238 failures, none of them about the site.
 */
const { server, base: BASE } = await startStaticServer();

/*
 * Every route names its theme, including the dark ones.
 *
 * They did not, and that was a hole rather than a shorthand. Playwright
 * defaults a context to `colorScheme: "light"`, the site reads
 * `prefers-color-scheme` to pick its theme, and the entries below that meant
 * to be dark simply left the field out — so `b` and `b-light` rendered the
 * same page twice and the dark theme was audited nowhere, while the comment
 * beside them claimed both palettes were covered.
 *
 * That mattered more than a duplicate screenshot: the two themes are the two
 * ends of an elevation ladder, a band is a different tone in each, and the
 * composited grounds a contrast check would care about only exist in one of
 * them at a time.
 */
const ROUTES = [
  ["b", "/", "dark"],
  // The playground inside the marketing shell. Its geometry is measured here
  // rather than inferred from the landing page: same seven-step flow, a
  // different header above it and a different composited ground under it.
  ["b-playground", "/playground", "dark"],
  // Licensing and privacy. Long prose in a measured column is where a width
  // regression shows up first, and it is not a page anyone would notice was
  // broken.
  ["b-legal", "/legal", "dark"],
  ["b-docs", "/docs", "dark"],
  /*
   * The same pages in light, which is not a lighter version of the same page.
   * The palettes are separately validated and the ladder runs the other way —
   * paper raises toward white and drops its bands into a deeper cream, ink
   * does the reverse. Same geometry only if nothing here depends on the theme,
   * which is the thing worth checking rather than assuming.
   */
  ["b-light", "/", "light"],
  ["b-playground-light", "/playground", "light"],
  ["b-legal-light", "/legal", "light"],
  ["b-docs-light", "/docs", "light"],
];

const WIDTHS = [390, 768, 1280, 1600];

let problems = 0;
// Worst sticky share seen, printed on success too. 14.9% against a >15 rule is
// a passing measurement with a tenth of a point of headroom, and a check that
// only speaks when it fails cannot tell you that.
let worstSticky = { where: "", share: 0 };
/*
 * A census of horizontal scrollers, printed on success.
 *
 * The hidden-controls check reports only failures, so a regression that
 * stops it seeing scrollers at all produces silence — and silence is
 * indistinguishable from a clean run. Counting what was inspected makes a
 * zero visible.
 */
let scrollersSeen = 0;
let scrollersCued = 0;
const report = (where, what) => {
  console.error(`  ✗ ${where}\n      ${what}`);
  problems += 1;
};

/**
 * Every element that paints its own text, with where it landed.
 *
 * Only leaves are considered: a paragraph and the span inside it always
 * "overlap", and reporting that would bury the one pair that matters.
 */
const MEASURE = `() => {
  const measured = [];
  for (const el of document.querySelectorAll("body *")) {
    const style = getComputedStyle(el);
    if (style.visibility === "hidden" || style.display === "none" || style.opacity === "0") continue;
    if (el.closest(".sr-only")) continue;

    const ownText = [...el.childNodes]
      .filter((n) => n.nodeType === 3)
      .map((n) => n.textContent.trim())
      .join(" ")
      .trim();
    if (!ownText) continue;

    const r = el.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) continue;

    /*
     * Skip what a scroll container has scrolled out of sight.
     *
     * \`getBoundingClientRect\` reports where an element *would* be, not
     * whether anyone can see it — so a row scrolled past the bottom of a
     * panel still returns a position, and that position lands on top of
     * whatever follows the panel. Two elements a reader can never see at the
     * same moment are not a collision, and reporting them buries the pairs
     * that are: one scrolling list produced a hundred and seventy of these.
     *
     * Only the clipping ancestors are consulted, and only on the axis they
     * actually clip.
     */
    /*
     * A closed <details> keeps its content's layout box.
     *
     * Chrome hides it with \`content-visibility\`, which skips painting and
     * leaves \`getBoundingClientRect\` reporting the same rect for every
     * collapsed answer — so the first use of <details> on this site produced
     * 214 collisions between paragraphs a reader cannot see. Nothing was
     * wrong with the page.
     *
     * The summary is exempt: it is the part that stays visible.
     */
    const collapsed = el.closest("details:not([open])");
    if (collapsed && !el.closest("summary")) continue;

    let hidden = false;
    for (let p = el.parentElement; p && p !== document.body; p = p.parentElement) {
      const ps = getComputedStyle(p);
      const clipsY = ps.overflowY === "auto" || ps.overflowY === "scroll" || ps.overflowY === "hidden";
      const clipsX = ps.overflowX === "auto" || ps.overflowX === "scroll" || ps.overflowX === "hidden";
      if (!clipsY && !clipsX) continue;
      const pr = p.getBoundingClientRect();
      if (clipsY && (r.bottom < pr.top + 1 || r.top > pr.bottom - 1)) { hidden = true; break; }
      if (clipsX && (r.right < pr.left + 1 || r.left > pr.right - 1)) { hidden = true; break; }
    }
    if (hidden) continue;

    measured.push({
      el,
      tag: el.tagName.toLowerCase(),
      text: ownText.slice(0, 70),
      x: r.x, y: r.y + window.scrollY, w: r.width, h: r.height,
      clipped: el.scrollHeight > el.clientHeight + 1 && style.overflowY === "hidden",
    });
  }

  /*
   * Overlap is decided here rather than in Node, because it needs
   * \`Node.contains\`. A paragraph that holds both raw text and an inline
   * <code> child paints text at both levels, and the parent's rect encloses
   * the child's by construction — every such pair intersects, and reporting
   * them buries the one pair that is a real collision.
   */
  const collisions = [];
  for (let i = 0; i < measured.length; i += 1) {
    for (let j = i + 1; j < measured.length; j += 1) {
      const a = measured[i], b = measured[j];
      if (a.el.contains(b.el) || b.el.contains(a.el)) continue;

      const ox = Math.max(0, Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x));
      const oy = Math.max(0, Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y));
      const area = ox * oy;
      if (area < 12) continue;
      collisions.push({ area: Math.round(area), a: a.text, b: b.text });
    }
  }

  const strip = ({ el, ...rest }) => rest;
  return {
    boxes: measured.map(strip),
    collisions,
    docWidth: document.documentElement.scrollWidth,
    viewport: window.innerWidth,
    /*
     * A sticky element is charged against the viewport for the whole visit.
     * The header once wrapped to four rows and stood at 219px on a 390px
     * screen — 26% of it, permanently, with content ghosting through a
     * 95%-opaque background. Nothing overlapped and nothing overflowed, so
     * every other check here was happy.
     */
    sticky: [...document.querySelectorAll("body *")]
      .filter((el) => ["sticky", "fixed"].includes(getComputedStyle(el).position))
      .map((el) => ({
        tag: el.tagName.toLowerCase(),
        h: Math.round(el.getBoundingClientRect().height),
        share: Math.round((el.getBoundingClientRect().height / window.innerHeight) * 100),
      }))
      .filter((s) => s.h > 0),

    /*
     * Controls that must be reachable by a fingertip.
     *
     * A link inside a sentence is exempt, and not as a convenience: WCAG's
     * target-size rule carves out targets in a block of text, because the only
     * way to give one 44px is to break the line spacing around it. The test is
     * whether the parent paints text of its own besides the link — that is what
     * "inline in prose" means structurally. The earlier version exempted the
     * whole footer instead, which was the right answer for the wrong reason and
     * would have hidden a real footer button.
     */
    /*
     * Controls hidden inside a horizontal scroll, with nothing saying so.
     *
     * A scrolling row is a fine way to fit five destinations onto a phone, but
     * the only cue browsers give for free is a scrollbar — and iOS draws that
     * as an overlay that appears after you have already scrolled. Two of five
     * nav items were unreachable unless the visitor guessed to swipe a row that
     * did not look swipeable.
     *
     * So the rule is not "never hide": it is "if you hide, mark it".
     *
     * What counts as marked used to be *any* gradient anywhere on the element
     * or its ::after. That is far too loose to mean anything. A decorative
     * background — a blueprint grid, a tint, a sheen — would satisfy it while
     * telling the reader nothing, and this audit would then report "no layout
     * problems" for a page with unreachable controls. A confident false
     * negative is worse than no check, and worse here than anywhere, because
     * the comment above says in as many words that the failure is invisible by
     * nature.
     *
     * A cue now has to be both *declared* and *painted*:
     *
     *   - declared: \`data-scroll-cue\` on the scroller. The attribute alone
     *     cannot satisfy this, or anyone can silence the audit by typing it.
     *   - painted: a mask, or a horizontal fade to transparent. The paint
     *     alone cannot satisfy it either, or a decorative gradient counts as a
     *     promise the author never made.
     *
     * Vertical and radial gradients are deliberately not accepted: a fade at
     * the bottom of a box says nothing about content lost off its right edge.
     */
    hiddenControls: (() => {
      // Every backslash is doubled because this whole function is the body of
      // a template literal in Node, and a single one is eaten before Chrome
      // ever sees the source.
      const HORIZONTAL_FADE = /^(?:-webkit-)?linear-gradient\\((?:to (?:right|left)|90deg|270deg)\\b/;
      const TRANSPARENT = /transparent|rgba?\\([^)]*,\\s*0(?:\\.0+)?\\s*\\)/;
      const fades = (value) =>
        Boolean(value) &&
        value !== "none" &&
        HORIZONTAL_FADE.test(value) &&
        TRANSPARENT.test(value);

      const out = [];
      let scrollers = 0;
      let cued = 0;

      for (const el of document.querySelectorAll("body *")) {
        if (el.scrollWidth <= el.clientWidth + 1) continue;
        scrollers += 1;

        const style = getComputedStyle(el);
        const after = getComputedStyle(el, "::after");
        const marked =
          el.hasAttribute("data-scroll-cue") &&
          (style.maskImage !== "none" ||
            style.webkitMaskImage !== "none" ||
            fades(style.backgroundImage) ||
            (after.content !== "none" && fades(after.backgroundImage)));
        if (marked) cued += 1;

        const box = el.getBoundingClientRect();
        const lost = [...el.querySelectorAll("button, a[href], [role=button]")].filter((c) => {
          const r = c.getBoundingClientRect();
          return r.width > 0 && (r.right > box.right + 1 || r.left < box.left - 1);
        });
        if (lost.length === 0) continue;

        if (!marked) {
          out.push({
            tag: el.tagName.toLowerCase(),
            hidden: Math.round(el.scrollWidth - el.clientWidth),
            labels: lost.map((c) => c.textContent.trim().slice(0, 30)),
          });
        }
      }
      return { found: out, scrollers, cued };
    })(),

    smallTargets: [...document.querySelectorAll("button, a[href], [role=button]")]
      .filter((el) => {
        if (el.closest(".sr-only")) return false;
        const parent = el.parentElement;
        if (!parent) return true;
        const siblingText = [...parent.childNodes]
          .filter((n) => n.nodeType === 3)
          .map((n) => n.textContent.trim())
          .join("");
        return siblingText.length === 0;
      })
      .map((el) => ({ el, r: el.getBoundingClientRect() }))
      .filter(({ r }) => r.height > 0 && r.height < 44)
      .map(({ el, r }) => ({ text: (el.textContent || el.getAttribute("aria-label") || "?").trim().slice(0, 40), h: Math.round(r.height) })),

    /*
     * Header bands whose two ends are padded differently.
     *
     * The idiom is everywhere on this site: a panel with a caption bar across
     * the top, a label at one end and a control at the other. It is drawn by
     * hand each time, so the padding is retyped each time, and the copy button
     * on every terminal block spent months 19px from the left and 9px from the
     * right. Nobody sees 10px as a number; they see a button that looks shoved
     * against the edge.
     *
     * The vertical half is the same defect turned ninety degrees. A control
     * with hit-target is 44px, and a bar with no padding of its own becomes
     * exactly that control's height — so it reads as a slot the button was
     * jammed into rather than a bar it sits in.
     *
     * Only two-ended bars qualify, or the right-hand measurement is the width
     * of the last word rather than a padding. "Pushed to the far side" is
     * detected as a void between the last two children, and that is the second
     * attempt: the first asked whether the last child had margin-left auto,
     * which computed style never reports. It resolves the keyword to a used
     * value — 415.656px on the block that prompted all this — so the filter was
     * dead code for precisely the case it was written for, and reported a
     * confident all-clear while the defect was on screen. A void is a fact
     * about the rendered box and cannot be resolved away.
     */
    lopsidedBands: [...document.querySelectorAll("figcaption, div, header")]
      .filter((row) => {
        const s = getComputedStyle(row);
        if (s.display !== "flex" || s.flexDirection.startsWith("column")) return false;
        const banded =
          s.borderBottomWidth !== "0px" ||
          s.borderTopWidth !== "0px" ||
          (s.backgroundColor !== "rgba(0, 0, 0, 0)" && s.backgroundColor !== "transparent");
        if (!banded) return false;
        const kids = [...row.children].filter((k) => k.getBoundingClientRect().width > 0);
        if (kids.length < 2) return false;
        if (s.justifyContent === "space-between") return true;
        const prev = kids[kids.length - 2].getBoundingClientRect();
        const last = kids[kids.length - 1].getBoundingClientRect();
        // Adjacent children — a tab strip, a row of chips — are not two-ended.
        return last.left - prev.right > 24;
      })
      .map((row) => {
        const kids = [...row.children].filter((k) => k.getBoundingClientRect().width > 0);
        const r = row.getBoundingClientRect();
        const f = kids[0].getBoundingClientRect();
        const l = kids[kids.length - 1].getBoundingClientRect();
        const tall = kids.map((k) => k.getBoundingClientRect()).filter((k) => k.height >= 40);
        return {
          text: (kids[0].textContent || "?").trim().slice(0, 34),
          left: Math.round(f.left - r.left),
          right: Math.round(r.right - l.right),
          vGap: tall.length
            ? Math.round(Math.min(...tall.map((k) => Math.min(k.top - r.top, r.bottom - k.bottom))))
            : null,
        };
      })
      .filter((b) => Math.abs(b.left - b.right) > 3 || (b.vGap !== null && b.vGap < 4)),

    /*
     * Pressable controls that do not offer a hand.
     *
     * Tailwind v3's Preflight gave buttons \`cursor: pointer\`; v4 dropped it,
     * and the whole site went to an arrow while every link kept a hand — two
     * controls that do the same thing telling a reader different stories about
     * whether they can be pressed. Nothing failed, nothing logged, and no
     * screenshot shows a cursor, so this is the only audit that can see it.
     *
     * Disabled controls are excluded rather than exempted: an arrow is the
     * correct cursor there, and requiring a hand would be requiring a lie.
     */
    handless: [...document.querySelectorAll("button:not(:disabled), summary, [role=button]:not([aria-disabled=true])")]
      .filter((el) => {
        const r = el.getBoundingClientRect();
        return r.width > 0 && r.height > 0 && getComputedStyle(el).cursor !== "pointer";
      })
      .map((el) => ({
        text: (el.textContent || el.getAttribute("aria-label") || "?").trim().slice(0, 40),
        cursor: getComputedStyle(el).cursor,
      })),
  };
}`;

mkdirSync(SHOTS, { recursive: true });

/*
 * Drive the Chrome already installed on this machine rather than Playwright's
 * own build. It saves a ~140MB download for a check that only needs a layout
 * engine, and it measures the browser people actually use. Set
 * `BEACON_BROWSER=bundled` to use Playwright's Chromium instead.
 */
const browser = await chromium.launch(
  process.env.BEACON_BROWSER === "bundled" ? {} : { channel: "chrome" },
);

for (const [name, hash, scheme] of ROUTES) {
  for (const width of WIDTHS) {
    const page = await browser.newPage({
      viewport: { width, height: 900 },
      ...(scheme ? { colorScheme: scheme } : {}),
    });
    const where = `${name} @ ${width}px`;

    /*
     * `vite preview` is not the host, and one endpoint only the host provides.
     *
     * Web Analytics is injected at Vercel's edge at `/_vercel/insights/*`;
     * those files are not in `dist/` and never will be, so previewing the
     * build 404s on them and every page reported a console error. That is a
     * fact about the preview server, not about the page, and letting it stand
     * would have made this tool cry wolf on all fourteen routes at four widths.
     *
     * Scoped to that prefix on purpose: any *other* 404 is still a defect, and
     * a broken font or a missing bundle must still fail here.
     */
    const fromTheEdge = (text) => text.includes("/_vercel/insights/");

    const errors = [];
    page.on("pageerror", (e) => errors.push(e.message));
    page.on("console", (m) => {
      if (m.type() !== "error") return;
      const text = m.text();
      if (!fromTheEdge(text) && !m.location()?.url?.includes("/_vercel/insights/")) {
        errors.push(text);
      }
    });

    await page.goto(`${BASE}${hash}`, { waitUntil: "networkidle" });
    // The timeline streams; let it settle so the measurement is of a real state.
    await page.waitForTimeout(400);

    // Invoked, not just evaluated: a string passed to `evaluate` is treated as
    // an expression, and a bare arrow function is an expression whose value is
    // the function itself.
    const { boxes, collisions, docWidth, viewport, handless, lopsidedBands, smallTargets, sticky, hiddenControls } = await page.evaluate(`(${MEASURE})()`);

    for (const message of errors) report(where, `console error: ${message}`);

    if (docWidth > viewport + 1) {
      report(where, `document is ${docWidth - viewport}px wider than the viewport`);
    }

    for (const box of boxes.filter((b) => b.clipped)) {
      report(where, `text clipped by a fixed height: "${box.text}"`);
    }

    for (const bar of sticky) {
      if (bar.share > worstSticky.share) worstSticky = { where, share: bar.share };
    }

    // 15% is generous for a header. The one that shipped was 26%.
    for (const bar of sticky.filter((s) => s.share > 15)) {
      report(where, `sticky <${bar.tag}> is ${bar.h}px — ${bar.share}% of the viewport`);
    }

    scrollersSeen += hiddenControls.scrollers;
    scrollersCued += hiddenControls.cued;

    for (const scroller of hiddenControls.found) {
      report(
        where,
        `<${scroller.tag}> hides ${scroller.hidden}px of controls with no scroll cue: ${scroller.labels.join(", ")}`,
      );
    }

    for (const target of smallTargets) {
      report(where, `hit target ${target.h}px, under the 44px the design system requires: "${target.text}"`);
    }

    for (const band of lopsidedBands) {
      report(
        where,
        band.vGap !== null && band.vGap < 4
          ? `header bar gives a ${44}px control ${band.vGap}px of room: "${band.text}"`
          : `header bar padded ${band.left}px one end and ${band.right}px the other: "${band.text}"`,
      );
    }

    for (const control of handless) {
      report(where, `pressable but shows "${control.cursor}" rather than a hand: "${control.text}"`);
    }

    for (const hit of collisions) {
      report(where, `text overlaps text (${hit.area}px²):\n        "${hit.a}"\n        "${hit.b}"`);
    }

    await page.screenshot({
      path: join(SHOTS, `${name}-${width}.png`),
      fullPage: width === 1280,
    });
    await page.close();
  }
}

await browser.close();
server.close();

console.log();
if (problems > 0) {
  console.error(`${problems} problem(s) found. Screenshots in site/.visual/`);
  process.exit(1);
}
console.log(`No layout problems found across ${ROUTES.length} pages × ${WIDTHS.length} widths.`);
console.log(`Worst sticky furniture: ${worstSticky.share}% of the viewport (${worstSticky.where}), against a 15% limit.`);
console.log(`Horizontal scrollers: ${scrollersSeen} inspected, ${scrollersCued} carrying a scroll cue.`);
console.log(`Screenshots in site/.visual/`);
