import type { Evidence } from "@/data/types";

/**
 * What the subject actually returned.
 *
 * The absent state carries the reason rather than showing an empty box. A
 * missing artifact is a finding — the output contract names what the subject
 * must return, and a requirement it was told about and did not meet is
 * different from one it was never given.
 */

interface Props {
  evidence: Evidence;
}

export function ArtifactPanel({ evidence }: Props) {
  const contract = evidence.scenario.output_contract;
  const wanted = contract?.artifact;
  const entries = Object.entries(evidence.artifacts ?? {});
  const body = wanted ? evidence.artifacts?.[wanted] : entries[0]?.[1];

  return (
    <section className="overflow-hidden rounded-card border border-line bg-surface">
      {/* A heading in the same voice as the two panels above it. A mono label
          reading `ARTIFACT — SUMMARY` names the field; it does not say that
          what follows is the thing the agent handed back. */}
      <header className="border-b border-line bg-sunken px-5 py-3.5">
        <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
          <h3 className="text-[15px] font-medium">What the agent handed back</h3>
          {wanted && (
            <span className="font-mono text-[11px] text-text-muted">artifact · {wanted}</span>
          )}
        </div>
        {contract?.description && (
          <p className="mt-1 max-w-[72ch] text-[13px] leading-relaxed text-text-muted text-pretty">
            The scenario asked for this: {contract.description}
          </p>
        )}
      </header>

      {body !== undefined ? (
        <pre className="max-h-96 overflow-auto px-5 py-4 font-mono text-[12.5px] leading-relaxed whitespace-pre-wrap">
          {typeof body === "string" ? body : JSON.stringify(body, null, 2)}
        </pre>
      ) : (
        <div className="px-5 py-6">
          <p className="text-sm leading-relaxed text-text-muted text-pretty">
            No artifact named <code className="font-mono text-text">{wanted}</code> was
            returned.
            {entries.length > 0
              ? ` The subject returned ${entries.map(([k]) => k).join(", ")} instead — a renamed field is not the field.`
              : " The subject returned nothing under any name."}
          </p>
        </div>
      )}
    </section>
  );
}
