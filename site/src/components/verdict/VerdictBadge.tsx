import type { BadgeState } from "@/data/types";

/**
 * Five states, three hues, and never colour alone.
 *
 * FLAKY and REGRESSION are built from PASS and FAIL rather than adding hues of
 * their own: the result vocabulary is exactly PASS, FAIL and INCOMPLETE, and a
 * fourth colour would imply a fourth kind of answer. Each state also carries a
 * shape — check, cross, dashed hollow ring, 45° hatch, delta arrow — so the set
 * survives greyscale and colour blindness.
 */

interface Props {
  state: BadgeState;
  /** Appended inside the badge, e.g. a rate for FLAKY or a delta for REGRESSION. */
  detail?: string;
  size?: "sm" | "md";
}

const box =
  "inline-flex items-center gap-1.5 rounded-[3px] border font-mono font-medium tracking-[0.06em] whitespace-nowrap";

const sizing = {
  sm: "px-1.5 py-1 text-[10.5px]",
  md: "px-2.5 py-1.5 text-xs",
} as const;

function Check() {
  return (
    <svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M3 8.5 L6.5 12 L13 4.5" />
    </svg>
  );
}

function Cross() {
  return (
    <svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" aria-hidden="true">
      <path d="M4 4 L12 12 M12 4 L4 12" />
    </svg>
  );
}

function Hollow() {
  return <span className="inline-block h-[11px] w-[11px] rounded-full border-2 border-dashed border-current" aria-hidden="true" />;
}

function Delta() {
  return (
    <svg width="11" height="11" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M8 3 L8 13 M4 9 L8 13 L12 9" />
    </svg>
  );
}

export function VerdictBadge({ state, detail, size = "md" }: Props) {
  const label = detail ? `${state} ${detail}` : state;

  if (state === "FLAKY") {
    return (
      <span className={`${box} ${sizing[size]} hatch-flaky border-line-strong text-text`}>
        {label}
      </span>
    );
  }

  if (state === "REGRESSION") {
    return (
      <span className={`${box} ${sizing[size]} border-fail/30 border-l-[3px] border-l-fail bg-fail-tint text-fail`}>
        <Delta />
        {detail ?? state}
      </span>
    );
  }

  const styles = {
    PASS: "bg-pass-tint border-pass/30 text-pass",
    FAIL: "bg-fail-tint border-fail/30 text-fail",
    INCOMPLETE: "bg-inc-tint border-dashed border-inc/50 text-inc",
  } as const;

  const icon = { PASS: <Check />, FAIL: <Cross />, INCOMPLETE: <Hollow /> }[state];

  return (
    <span className={`${box} ${sizing[size]} ${styles[state]}`}>
      {icon}
      {label}
    </span>
  );
}
