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

export function RunDot({ state, index, size = 22 }: Props) {
  const style = { width: size, height: size };

  const classes = {
    PASS: "bg-pass-tint border border-pass text-pass",
    FAIL: "bg-fail-tint border border-fail text-fail",
    INCOMPLETE: "border-2 border-dashed border-inc text-inc",
    pending: "border-2 border-dashed border-line-strong text-text-faint animate-pulse-slow",
  }[state];

  const glyph = { PASS: "✓", FAIL: "✗", INCOMPLETE: "○", pending: "" }[state];

  return (
    <span
      style={style}
      title={`Run ${index + 1}: ${state}`}
      className={`inline-flex flex-none items-center justify-center rounded-full font-mono text-[10px] leading-none ${classes}`}
    >
      <span className="sr-only">{`Run ${index + 1}: ${state}`}</span>
      <span aria-hidden="true">{glyph}</span>
    </span>
  );
}
