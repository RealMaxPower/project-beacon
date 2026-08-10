import type { Verdict } from "@/data/types";

/**
 * The mark, at page scale, drawn from the runs it is about.
 *
 * `Mark.tsx` is three concentric arcs leaving a filled origin — "a measurement
 * widening from a point". The finding this page opens with has the same shape:
 * one starting state, several paths, more than one answer. So the hero graphic
 * is the logo with its arc count set by the data instead of by the logo.
 *
 * The colour rule is the whole reason this is legible rather than decorative.
 * `tokens.css` gives PASS, FAIL and INCOMPLETE ownership of green, red and
 * amber, and forbids chrome from borrowing any of them. Here the arc is the
 * path — chrome, so it is the accent — and the dot is the answer, so it is the
 * verdict hue. Nothing crosses. A reader who has seen a verdict badge anywhere
 * else on the site already knows what the endpoints mean.
 *
 * There is no motion. The graphic is a still diagram of a finished set of runs,
 * and animating it would be the site's third animation spent on decoration,
 * against a token comment that allows exactly two and reserves both for a run
 * that is actually happening.
 *
 * It is `aria-hidden`. Everything it depicts is stated in the prose beside it
 * and operable in the row of buttons beneath it — the picture is never the only
 * route to anything.
 */

export interface SweepRun {
  key: string;
  label: string;
  verdict: Verdict;
}

interface Props {
  runs: SweepRun[];
  /** First eight of the shared `before` digest, printed at the origin. */
  before: string;
  /** First eight of the shared `after` digest, printed at the convergence. */
  after: string;
}

/** Verdict hues, by the same names the badges use. */
const STROKE: Record<Verdict, string> = {
  PASS: "var(--pass)",
  FAIL: "var(--fail)",
  INCOMPLETE: "var(--inc)",
};

export function Sweep({ runs, before, after }: Props) {
  /*
   * Authored in a 1000×360 space and scaled uniformly.
   *
   * `none` would shear the dots into ellipses on a wide band. `slice` fills the
   * box but crops horizontally, and on a phone that cropped away both endpoints
   * and their digests — leaving arcs that begin and end nowhere, which is the
   * one thing this diagram must not say. `meet` letterboxes instead: shorter on
   * a narrow screen, complete at every width.
   */
  const W = 1000;
  const H = 360;
  const originX = 110;
  const originY = H / 2;
  const endX = W - 190;

  /*
   * Both ends converge. Only the middle diverges.
   *
   * This is the whole finding, and getting it wrong inverts the claim. A fan
   * that starts at a point and spreads to five separate endpoints draws five
   * different end states, which is the opposite of what the runs show. These
   * leave one state, behave differently, and arrive at the same state — so the
   * paths bow apart and come back, and the verdict dot sits at the point of
   * maximum divergence, which is exactly where the difference between these
   * agents lives.
   */
  const spread = 132;
  const step = runs.length > 1 ? (spread * 2) / (runs.length - 1) : 0;
  /** The control-point offset for path `i`. */
  const swell = (i: number) => originY - spread + step * i;
  /*
   * Where path `i` actually is at its midpoint.
   *
   * Not `swell(i)` — that is the control point, and a cubic does not pass
   * through its controls. For a curve from y₀ out to a doubled control at yₛ
   * and back to y₀, the midpoint is `0.25·y₀ + 0.75·yₛ`. Placing the verdict
   * dot at the control instead left the outer two floating clear of their own
   * paths, which reads as a rendering fault rather than as a diagram.
   */
  const midpoint = (i: number) => originY * 0.25 + swell(i) * 0.75;

  return (
    <div className="pointer-events-none relative select-none" aria-hidden="true">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        preserveAspectRatio="xMidYMid meet"
        className="block h-auto w-full"
        role="presentation"
        focusable="false"
      >
        {/*
          The hairline field, drawn as strokes rather than as a background
          gradient. A CSS grid-background would be the conventional way and is
          wrong three times over here: gradient is a reserved vocabulary in this
          system, a background under text invalidates every published contrast
          ratio, and `tools/visual.mjs` reads the presence of a gradient as a
          scroll-affordance cue. `--line` on `--bg` measures 1.22:1, which is
          the "present but not noticeable" the effect needs, and it inverts with
          the theme for free because it is the same token.
        */}
        <g stroke="var(--line)" strokeWidth="1">
          {Array.from({ length: 13 }, (_, i) => {
            const x = (W / 12) * i;
            return <line key={`v${i}`} x1={x} y1="0" x2={x} y2={H} />;
          })}
        </g>

        {/* Each run's path: out from the shared origin, back to the shared end. */}
        <g fill="none" stroke="var(--accent)" strokeWidth="1.25" strokeLinecap="round">
          {runs.map((run, i) => (
            <path
              key={run.key}
              d={
                `M ${originX} ${originY} ` +
                `C ${originX + 190} ${swell(i)}, ${endX - 190} ${swell(i)}, ${endX} ${originY}`
              }
            />
          ))}
        </g>

        {/* The verdict, where the paths are furthest apart. */}
        {runs.map((run, i) => (
          <circle key={run.key} cx={W / 2} cy={midpoint(i)} r="6.5" fill={STROKE[run.verdict]} />
        ))}

        {/* The two states, each a filled origin drawn the way the mark draws one. */}
        <circle cx={originX} cy={originY} r="5.5" fill="var(--text)" />
        <circle cx={endX} cy={originY} r="5.5" fill="var(--text)" />

        <g fill="var(--text-faint)" fontFamily="var(--font-mono)" fontSize="13">
          <text x={originX} y={originY + 32} textAnchor="middle">
            {before}
          </text>
          <text x={endX} y={originY + 32} textAnchor="middle">
            {after}
          </text>
        </g>
        <g fill="var(--text-faint)" fontFamily="var(--font-mono)" fontSize="11.5">
          <text x={originX} y={originY - 22} textAnchor="middle">
            before
          </text>
          <text x={endX} y={originY - 22} textAnchor="middle">
            after
          </text>
        </g>
      </svg>
    </div>
  );
}
