/**
 * Mark A — Sweep. Three concentric arcs from a fixed origin.
 *
 * A measurement widening from a point, not a building. Monochrome geometry
 * only, so it inverts cleanly and survives the rename that trademark screening
 * may force — the wordmark beside it is just type, so renaming costs one
 * string. It doubles as the run-in-progress spinner, which is why the arcs
 * share an origin.
 *
 * At 16px the outer arc needs the heavier stroke or it greys out.
 */

interface Props {
  size?: number;
  spinning?: boolean;
  className?: string;
}

export function Mark({ size = 20, spinning = false, className = "" }: Props) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      className={`${spinning ? "animate-sweep" : ""} ${className}`}
      role="img"
      aria-label="Beacon"
    >
      <g
        fill="none"
        stroke="currentColor"
        strokeWidth={size <= 16 ? 2.2 : 1.8}
        strokeLinecap="round"
      >
        <path d="M4 13.5A6.5 6.5 0 0 1 10.5 20" />
        <path d="M4 8.5A11.5 11.5 0 0 1 15.5 20" />
        <path d="M4 3.5A16.5 16.5 0 0 1 20.5 20" />
      </g>
      <circle cx="4" cy="20" r="2" fill="currentColor" />
    </svg>
  );
}
