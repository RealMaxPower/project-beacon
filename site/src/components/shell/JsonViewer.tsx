import { ProvenanceTag } from "./ProvenanceTag";
import type { Provenance } from "@/data/types";

/**
 * The bundle, unedited.
 *
 * Every value shown here was written by a real run — `site/tools/build_fixtures.py`
 * executes the scenario and commits what Beacon produced. The one edit made to
 * any of it is rewriting the recording machine's repository path to `<repo>`,
 * which is why that string appears in the command.
 */

/**
 * Either the file's bytes, or parsed data that is not claiming to be a file.
 *
 * Enforced by the type rather than by care. Re-serialising parsed JSON produces
 * a document with the same values and a different shape — different key order,
 * different byte count, different hash — and a panel tagged REPO under a
 * filename is making a claim about that exact file. Fixing the scenario panel
 * left the same defect in the two beside it, so the compiler now refuses the
 * combination instead of a reviewer having to notice it.
 */
type Source =
  | { provenance?: "repo"; source: string; value?: never }
  | { provenance: Exclude<Provenance, "repo">; value: unknown; source?: never };

type Props = Source & {
  label: string;
  maxHeight?: number;
};

export function JsonViewer({ value, source, label, provenance = "repo", maxHeight = 420 }: Props) {
  const text = source ?? JSON.stringify(value, null, 2);

  return (
    <figure className="overflow-hidden rounded-card border border-line bg-surface">
      <figcaption className="flex flex-wrap items-center justify-between gap-2 border-b border-line bg-sunken px-4 py-2.5">
        <span className="font-mono text-[11.5px] font-medium">{label}</span>
        <span className="flex items-center gap-2">
          <span className="font-mono text-[10.5px] text-text-faint">
            {new Blob([text]).size.toLocaleString()} bytes
          </span>
          <ProvenanceTag level={provenance} />
        </span>
      </figcaption>

      <pre
        style={{ maxHeight }}
        className="overflow-auto px-4 py-3 font-mono text-[11.5px] leading-relaxed"
      >
        {text}
      </pre>
    </figure>
  );
}
