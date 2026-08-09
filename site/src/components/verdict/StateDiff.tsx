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

/** How many lines of a value are shown before it is cut. */
const MAX_LINES = 18;

/**
 * A value, laid out to be read rather than parsed.
 *
 * This used to be `JSON.stringify` cut at 200 characters, which for the one
 * row that matters — three drafts an agent wrote — produced a single wrapped
 * line of `[{"id":"d-001","to":"maya@…","subject":"Re: Contract…` ending in an
 * ellipsis. Every field name, quote and brace competed with the content, and
 * the third draft was past the cut. Indented, the same value is a list of
 * three things with five fields each.
 */
function preview(value: unknown): string {
  if (Array.isArray(value) && value.length === 0) return "[] (nothing)";
  if (value === null || value === undefined) return "∅";
  if (typeof value === "string") return value || "∅";

  const text = JSON.stringify(value, null, 2);
  if (!text) return "∅";

  const lines = text.split("\n");
  if (lines.length <= MAX_LINES) return text;

  const hidden = lines.length - MAX_LINES;
  return `${lines.slice(0, MAX_LINES).join("\n")}\n… ${hidden} more line${hidden === 1 ? "" : "s"} — the whole value is in evidence.json`;
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
      <header className="border-b border-line bg-sunken px-5 py-3.5">
        <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
          <h3 className="text-[15px] font-medium">
            {evidence.state_diff.change_count} change
            {evidence.state_diff.change_count === 1 ? "" : "s"} to the synthetic world
          </h3>
          <span className="font-mono text-[11px] text-text-muted">
            digest {evidence.state.before_digest.slice(0, 8)} →{" "}
            {evidence.state.after_digest.slice(0, 8)}
          </span>
        </div>
        <p className="mt-1 max-w-[72ch] text-[13px] leading-relaxed text-text-muted text-pretty">
          What the mailbox or folder looked like before the agent touched it, and after. Rows
          the agent reached for and was refused are here too, tinted — they did not move, and
          that is the point.
        </p>
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

              {/*
               * `pre`, not `p`. The values are indented JSON now, and a
               * paragraph collapses every newline that makes them readable.
               * Each scrolls on its own axis rather than widening the card.
               */}
              {/* `items-start`: an empty "before" beside eighteen lines of
                  "after" stretched into a tall blank box, which reads as a
                  value that failed to load rather than as nothing. */}
              <div className="grid items-start gap-2 sm:grid-cols-2">
                <div className="min-w-0">
                  <p className="mb-1 font-mono text-[10px] uppercase tracking-[0.09em] text-text-faint">
                    Before
                  </p>
                  <pre className="overflow-x-auto rounded-row border border-line bg-sunken p-2.5 font-mono text-[11px] leading-relaxed">
                    {row.before}
                  </pre>
                </div>
                <div className="min-w-0">
                  <p className="mb-1 font-mono text-[10px] uppercase tracking-[0.09em] text-text-faint">
                    After
                  </p>
                  <pre className="overflow-x-auto rounded-row border border-line bg-sunken p-2.5 font-mono text-[11px] leading-relaxed">
                    {row.after}
                  </pre>
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
