/**
 * The faint grid the source design lays behind its hero.
 *
 * Drawn as SVG rather than a CSS background, and not for purity: this project's
 * own guard forbids `background-image` outright, because that property is how a
 * raster gets onto a page without anybody noticing, and every ratio published in
 * `tokens-b.css` is measured against a flat ground that an image would silently
 * stop being. A `<pattern>` of two hairlines costs nothing, tiles the same way,
 * and stays a vector at any density.
 *
 * `currentColor` carries it without a second colour — on ink it lightens, on
 * paper it darkens, and neither needs its own value.
 *
 * The opacity is a measurement, not a taste, and it is different in each theme
 * because the budget is. The lines sit behind hero text and raise the ground
 * under it, while every ratio in `tokens-b.css` was taken against a flat one.
 *
 * On ink, 10% composites to #25282d, where the hero clears AA on everything it
 * uses — text 13.78, src 8.69, muted 5.66 — but `--b-faint` falls to 3.80, so
 * the hero does not use it. The one line that did, the scenario count under the
 * buttons, is muted instead. At 6% it would still have been 4.25, under AA, and
 * looked like nothing anyway.
 *
 * On paper the same 10% composites to #dedbd5 and takes `--b-src` — the eyebrow
 * — down to 4.04, because that accent starts at 4.95 rather than 11.11 and has
 * almost nothing to give. 4% is what fits: #ebe8e2, src 4.57, muted 6.07. Dark
 * lines on a light ground read more strongly than light on dark at equal alpha,
 * so the two are closer in appearance than the numbers suggest.
 *
 * It is decoration with no meaning, so it is `aria-hidden` and sits behind
 * everything at `-z-10`. Nothing in the hero depends on it being visible.
 */
export function Blueprint() {
  return (
    <svg
      aria-hidden="true"
      focusable="false"
      className="pointer-events-none absolute inset-0 -z-10 h-full w-full"
      style={{
        color: "var(--b-text)",
        maskImage: "radial-gradient(120% 90% at 50% 0%, black, transparent 72%)",
        WebkitMaskImage: "radial-gradient(120% 90% at 50% 0%, black, transparent 72%)",
      }}
    >
      <defs>
        <pattern id="b-blueprint" width="64" height="64" patternUnits="userSpaceOnUse">
          {/* Opacity lives on the rect, so one token governs both strokes. */}
          <line x1="0" y1="0" x2="64" y2="0" stroke="currentColor" strokeWidth="1" />
          <line x1="0" y1="0" x2="0" y2="64" stroke="currentColor" strokeWidth="1" />
        </pattern>
      </defs>
      <rect width="100%" height="100%" fill="url(#b-blueprint)" style={{ opacity: "var(--b-grid)" }} />
    </svg>
  );
}
