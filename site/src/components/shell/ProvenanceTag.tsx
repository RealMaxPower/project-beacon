import type { Provenance } from "@/data/types";

/**
 * Where a displayed value came from.
 *
 * Delete this component only when nothing illustrative remains. While it
 * exists, it is doing the job the design handoff asked for: a viewer should
 * never have to guess whether a number on this page was measured or written.
 */

interface Props {
  level: Provenance;
  className?: string;
}

const labels: Record<Provenance, string> = {
  repo: "REPO",
  proposal: "PROPOSAL",
  illustrative: "ILLUSTRATIVE",
};

const styles: Record<Provenance, string> = {
  repo: "bg-text text-bg border-transparent",
  proposal: "border-line-strong text-text-muted",
  illustrative: "border-dashed border-line-strong text-text-faint",
};

export function ProvenanceTag({ level, className = "" }: Props) {
  return (
    <span
      title={
        level === "repo"
          ? "Recorded by a real run, or read from the repository."
          : level === "proposal"
            ? "From the pre-build proposal. Designed, not necessarily shipped."
            : "Authored copy. Not a measurement."
      }
      className={`inline-block rounded-[3px] border px-1.5 py-1 font-mono text-[9.5px] font-medium tracking-[0.08em] ${styles[level]} ${className}`}
    >
      {labels[level]}
    </span>
  );
}
