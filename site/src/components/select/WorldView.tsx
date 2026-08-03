import type { ScenarioSummary } from "@/data/types";

/**
 * The world a scenario hands its subject, whatever shape that world is.
 *
 * Only three of the seven scenarios are a mailbox. The rest give the agent a
 * folder of documents, a captured web page, or a block of content — and the
 * screen used to say "there is no world to draw" for four of them, which was
 * true of the component and false of the scenario. Every one of them has
 * material declared in its fixtures; it just is not mail.
 *
 * A protected or injected item is marked here for the same reason it is in the
 * inbox: those two are what the run turns on, and finding them by reading a
 * JSON blob is not the same as seeing them.
 */

const INJECTION_MARKERS = ["[SYSTEM OVERRIDE]", "IGNORE ALL PREVIOUS", "INSTRUCTION TO THE"];

function carriesInjection(text: string): boolean {
  const upper = text.toUpperCase();
  return INJECTION_MARKERS.some((marker) => upper.includes(marker));
}

interface FileEntry {
  path: string;
  content?: string;
  tags?: string[];
  protected?: boolean;
}

function Files({ files, policy }: { files: FileEntry[]; policy?: Record<string, unknown> }) {
  const forbidden = Object.entries(policy ?? {})
    .filter(([, allowed]) => allowed === false)
    .map(([rule]) => rule.replace(/^allow_/, ""));

  return (
    <div className="overflow-hidden rounded-card border border-line bg-surface">
      <header className="flex flex-wrap items-baseline justify-between gap-2 border-b border-line bg-sunken px-5 py-3">
        <h3 className="text-sm font-medium">Documents</h3>
        <span className="font-mono text-[11px] text-text-faint">
          {files.length} files · synthetic
          {forbidden.length > 0 && ` · policy forbids ${forbidden.join(", ")}`}
        </span>
      </header>

      <ul>
        {files.map((file) => {
          const injected = carriesInjection(file.content ?? "");
          return (
            <li key={file.path} className="border-b border-line px-5 py-4 last:border-b-0">
              <div className="mb-1.5 flex flex-wrap items-baseline gap-x-3 gap-y-1">
                <span className="font-mono text-[13px] font-medium">{file.path}</span>
                {file.tags && file.tags.length > 0 && (
                  <span className="font-mono text-[11px] text-text-faint">
                    {file.tags.join(", ")}
                  </span>
                )}
              </div>

              <p className="mb-2.5 line-clamp-2 text-[13.5px] leading-relaxed text-text-muted text-pretty">
                {file.content}
              </p>

              {injected && (
                <span className="rounded-[3px] border border-fail/40 bg-fail-tint px-1.5 py-0.5 font-mono text-[10px] text-fail">
                  contains an injected instruction
                </span>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function Material({ name, value }: { name: string; value: Record<string, unknown> }) {
  const entries = Object.entries(value).filter(([, v]) => typeof v === "string" && v.length > 0);

  return (
    <div className="overflow-hidden rounded-card border border-line bg-surface">
      <header className="border-b border-line bg-sunken px-5 py-3">
        <h3 className="text-sm font-medium">
          The material it was given
          <span className="ml-2 font-mono text-[11px] font-normal text-text-faint">{name}</span>
        </h3>
      </header>

      <dl className="divide-y divide-line">
        {entries.map(([key, text]) => (
          <div key={key} className="px-5 py-4">
            <dt className="mb-1.5 font-mono text-[10.5px] uppercase tracking-[0.09em] text-text-faint">
              {key}
            </dt>
            <dd className="max-h-40 overflow-y-auto text-[13.5px] leading-relaxed break-words text-text-muted text-pretty">
              {String(text)}
            </dd>
            {carriesInjection(String(text)) && (
              <span className="mt-2 inline-block rounded-[3px] border border-fail/40 bg-fail-tint px-1.5 py-0.5 font-mono text-[10px] text-fail">
                contains an injected instruction
              </span>
            )}
          </div>
        ))}
      </dl>
    </div>
  );
}

export function WorldView({ scenario }: { scenario: ScenarioSummary }) {
  const fixtures = scenario.fixtures ?? {};

  const files = (fixtures.files as { files?: FileEntry[]; policy?: Record<string, unknown> })
    ?.files;
  if (files?.length) {
    return (
      <>
        <p className="mb-4 max-w-[68ch] text-[14px] leading-relaxed text-text-muted text-pretty">
          A synthetic folder. {files.length} documents, all invented
          {files.some((f) => carriesInjection(f.content ?? "")) &&
            ", and one carries an instruction aimed at the agent rather than at you"}
          .
        </p>
        <Files
          files={files}
          policy={(fixtures.files as { policy?: Record<string, unknown> })?.policy}
        />
      </>
    );
  }

  // Whatever the scenario named its material — `probe`, `page`, `contract`,
  // `briefing`. Read from the fixture keys rather than a list here, so a new
  // scenario draws its world without this component being edited.
  const [name, value] =
    Object.entries(fixtures).find(([, v]) => v && typeof v === "object") ?? [];
  if (name && value) {
    return <Material name={name} value={value as Record<string, unknown>} />;
  }

  return (
    <p className="rounded-card border border-dashed border-line-strong p-6 text-sm text-text-muted">
      This scenario declares no fixtures.
    </p>
  );
}
