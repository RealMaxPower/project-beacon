import type { Verdict } from "@/data/types";

/**
 * One run in a strip of them.
 *
 * Pending is a dashed outline with a pulse, never a filled neutral — a filled
 * grey dot reads as a fourth result, and there are only three.
 */

interface Props {
  state: Verdict | "pending";
  index: number;
  size?: number;
}

export function RunDot({ state, index, size = 28 }: Props) {
  const style = { width: size, height: size };

  /*
   * Filled for the two results that are answers, outlined for the two that
   * are not.
   *
   * At 22px with a tinted fill and a 10px glyph, twelve of these read as a row
   * of smudges: whether a dot said ✓ or ○ was only legible if you already knew
   * which to expect, and the amber dash and the grey dash were the same shape.
   * PASS and FAIL now carry their colour solid, the way the hero strip on the
   * home page draws them, so the pattern in a strip is readable at a glance
   * and INCOMPLETE stays visibly the odd one out — which it is.
   */
  const classes = {
    PASS: "bg-pass text-bg",
    FAIL: "bg-fail text-bg",
    INCOMPLETE: "border-2 border-dashed border-inc bg-inc-tint text-inc",
    pending: "border-2 border-dashed border-line-strong text-text-faint animate-pulse-slow",
  }[state];

  /*
   * No glyph for INCOMPLETE. A dashed amber ring over a tint is already
   * unmistakable beside a solid disc, and it is the same dashed-border
   * language `VerdictBadge` uses for the verdict — where a `?` would be a
   * fourth symbol in a vocabulary of three.
   */
  const glyph = { PASS: "✓", FAIL: "✗", INCOMPLETE: "", pending: "" }[state];

  return (
    <span
      style={style}
      title={`Run ${index + 1}: ${state}`}
      className={`inline-flex flex-none items-center justify-center rounded-full font-mono text-[12px] font-medium leading-none ${classes}`}
    >
      <span className="sr-only">{`Run ${index + 1}: ${state}`}</span>
      <span aria-hidden="true">{glyph}</span>
    </span>
  );
}
