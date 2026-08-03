import { ProvenanceTag } from "@/components/shell/ProvenanceTag";
import { bundleSource } from "@/data/fixtures";
import type { Evidence } from "@/data/types";

/**
 * Take the evidence with you.
 *
 * Downloads what is already in the page — the same bytes the run wrote. There
 * is no server here to ask for a fresh copy, which is the point: an evidence
 * bundle that only exists inside somebody else's product is not evidence you
 * can check.
 */

interface Props {
  evidence: Evidence;
}

function download(name: string, contents: string) {
  const url = URL.createObjectURL(new Blob([contents], { type: "application/json" }));
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = name;
  anchor.click();
  URL.revokeObjectURL(url);
}

export function ExportBundle({ evidence }: Props) {
  const files = [
    {
      name: "evidence.json",
      what: "The machine-readable bundle: scenario, subject, every assertion with what it compared, the state digests, and the limitations.",
      contents: () => bundleSource(evidence.run_id, "evidence.json"),
    },
    {
      name: "events.json",
      what: "Every tool call, result, refusal and artifact, in order, with timestamps.",
      contents: () => bundleSource(evidence.run_id, "events.json"),
    },
  ];

  return (
    <section>
      <header className="mb-6">
        <h2 className="mb-2 text-2xl leading-tight font-medium tracking-[-0.025em] text-balance">
          Take the evidence with you
        </h2>
        <p className="max-w-[68ch] text-[15px] leading-relaxed text-text-muted text-pretty">
          A run that fails produces the same bundle as one that passes. So does one that never
          finished. Evidence you only get when the news is good is marketing, not measurement.
        </p>
      </header>

      <div className="grid gap-4 sm:grid-cols-2">
        {files.map((file) => (
          <article key={file.name} className="rounded-card border border-line bg-surface p-5">
            <div className="mb-2 flex items-center justify-between gap-2">
              <h3 className="font-mono text-[13px] font-medium">{file.name}</h3>
              <ProvenanceTag level="repo" />
            </div>
            <p className="mb-4 text-[13.5px] leading-relaxed text-text-muted text-pretty">
              {file.what}
            </p>
            <button
              type="button"
              onClick={() => download(file.name, file.contents())}
              className="hit-target inline-flex items-center rounded-row bg-text px-3.5 py-2 text-[12.5px] font-medium text-bg"
            >
              Download
            </button>
          </article>
        ))}
      </div>

      <div className="mt-5 rounded-card border border-line border-l-[3px] border-l-line-strong bg-surface p-5">
        <h3 className="mb-2 font-mono text-[10.5px] uppercase tracking-[0.1em] text-text-faint">
          What the bundle does not protect you from
        </h3>
        <p className="mb-3 max-w-[72ch] text-[13.5px] leading-relaxed text-text-muted text-pretty">
          A credential passed to a subject is removed from the bundle wherever it appears — in
          tool arguments, results, artifacts, stderr and the recorded command, in raw,
          URL-encoded and base64 forms. That is <em className="text-text">exact-value
          matching</em>, not a guarantee: a subject that transforms a secret before emitting it
          defeats it, and its network access is unrestricted either way.
        </p>
        <p className="max-w-[72ch] text-[13.5px] leading-relaxed text-text-muted text-pretty">
          Every redacted bundle says so in its own limitations, rather than leaving you to
          infer it from the absence of a key.
        </p>
      </div>

      <div className="mt-4 rounded-card border border-line bg-sunken p-5">
        <h3 className="mb-2 font-mono text-[10.5px] uppercase tracking-[0.1em] text-text-faint">
          Where these came from
        </h3>
        <p className="max-w-[72ch] text-[13.5px] leading-relaxed text-text-muted text-pretty">
          Recorded by <code className="font-mono text-text">site/tools/build_fixtures.py</code>,
          which runs the real scenario against a real subject from{" "}
          <code className="font-mono text-text">examples/subjects/</code> and commits what
          Beacon wrote. The single edit made to any of it is rewriting the recording machine's
          repository path to <code className="font-mono text-text">&lt;repo&gt;</code>, which
          is why that string appears in the recorded command.
        </p>
      </div>
    </section>
  );
}
