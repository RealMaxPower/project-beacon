import type { BeaconEvent, Evidence } from "@/data/types";
import { blockedAttempts, pathForTool } from "@/data/fixtures";

/**
 * What the run changed in the synthetic world, and what it did not.
 *
 * The unchanged rows are the reason this component exists. A subject that tried
 * to send mail and was refused leaves `mail.sent` empty — byte-identical to one
 * that never tried. A diff showing only what changed reports those two runs as
 * the same run, so every path a blocked attempt aimed at gets a row here with
 * the attempt annotated on it, tinted as a failure even though the value did
 * not move.
 */

interface Props {
  evidence: Evidence;
  events: BeaconEvent[];
}

type Tone = "change" | "same" | "fail";

interface Row {
  path: string;
  before: string;
  after: string;
  tone: Tone;
  note?: string;
}

function preview(value: unknown): string {
  if (Array.isArray(value) && value.length === 0) return "[]";
  const text = typeof value === "string" ? value : JSON.stringify(value);
  if (!text) return "∅";
  return text.length > 200 ? `${text.slice(0, 200)}…` : text;
}

export function StateDiff({ evidence, events }: Props) {
  const changed: Row[] = evidence.state_diff.changes.map((change) => ({
    path: change.path,
    before: preview(change.before),
    after: preview(change.after),
    tone: "change",
  }));

  const changedPaths = new Set(changed.map((row) => row.path));

  const attempted: Row[] = [];
  for (const [tool, count] of blockedAttempts(events)) {
    const path = pathForTool(tool);
    if (!path || changedPaths.has(path)) continue;
    attempted.push({
      path,
      before: "[]",
      after: "[]",
      tone: "fail",
      note: `${count} attempt${count === 1 ? "" : "s"} blocked — ${tool}`,
    });
  }

  const rows = [...changed, ...attempted];
  const tones: Record<Tone, string> = {
    change: "border-line",
    same: "border-line",
    fail: "border-fail/30 bg-fail-tint",
  };

  return (
    <section className="overflow-hidden rounded-card border border-line bg-surface">
      <header className="flex flex-wrap items-baseline justify-between gap-2 border-b border-line bg-sunken px-5 py-3">
        <h3 className="font-mono text-[10.5px] font-medium uppercase tracking-[0.1em] text-text-faint">
          State changes
        </h3>
        <span className="font-mono text-[11px] text-text-muted">
          {evidence.state_diff.change_count} change
          {evidence.state_diff.change_count === 1 ? "" : "s"} · digest{" "}
          {evidence.state.before_digest.slice(0, 8)} → {evidence.state.after_digest.slice(0, 8)}
        </span>
      </header>

      {rows.length === 0 ? (
        <p className="px-5 py-6 text-sm text-text-muted text-pretty">
          Nothing in the world changed, and nothing was attempted that would have. For a
          scenario whose whole instruction is to look without touching, that is the result —
          not an empty screen.
        </p>
      ) : (
        <ul>
          {rows.map((row) => (
            <li key={row.path} className={`border-b px-5 py-4 last:border-b-0 ${tones[row.tone]}`}>
              <div className="mb-2.5 flex flex-wrap items-center gap-2.5">
                <span className="font-mono text-xs font-medium">{row.path}</span>
                {row.note && (
                  <span className="rounded-[3px] bg-fail px-1.5 py-0.5 font-mono text-[9.5px] font-medium tracking-[0.06em] text-white">
                    {row.note}
                  </span>
                )}
              </div>

              <div className="grid gap-2 sm:grid-cols-2">
                <div>
                  <p className="mb-1 font-mono text-[10px] uppercase tracking-[0.09em] text-text-faint">
                    Before
                  </p>
                  <p className="rounded-row border border-line bg-sunken p-2 font-mono text-[11px] leading-relaxed break-words">
                    {row.before}
                  </p>
                </div>
                <div>
                  <p className="mb-1 font-mono text-[10px] uppercase tracking-[0.09em] text-text-faint">
                    After
                  </p>
                  <p className="rounded-row border border-line bg-sunken p-2 font-mono text-[11px] leading-relaxed break-words">
                    {row.after}
                  </p>
                </div>
              </div>

              {row.tone === "fail" && (
                <p className="mt-2.5 text-[12.5px] leading-relaxed on-tint text-pretty">
                  Unchanged, and that is the problem. Policy refused the call, so this value
                  looks identical to a run that never reached for it. The attempt is the only
                  thing that tells them apart.
                </p>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
