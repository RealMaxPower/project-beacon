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
 * The opacity is a measurement, not a taste. The lines sit behind hero text, so
 * they raise the ground under it, and every ratio in `tokens-b.css` was taken
 * against the flat ink. At 10% the composited ground is #25282d, where the hero
 * still clears AA on everything it uses — text 13.78, src 8.69, muted 5.66, bad
 * 5.36 — but `--b-faint` falls to 3.80, so the hero does not use it. The one
 * line that did (the scenario count under the buttons) is muted now, and that
 * is the whole cost of the grid being visible. At 6% it would still have been
 * 4.25, which is under AA and looked like nothing anyway.
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
          <line x1="0" y1="0" x2="64" y2="0" stroke="currentColor" strokeWidth="1" opacity="0.1" />
          <line x1="0" y1="0" x2="0" y2="64" stroke="currentColor" strokeWidth="1" opacity="0.1" />
        </pattern>
      </defs>
      <rect width="100%" height="100%" fill="url(#b-blueprint)" />
    </svg>
  );
}
