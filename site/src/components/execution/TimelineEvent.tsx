import type { BeaconEvent } from "@/data/types";
import { describeEvent, isBlocked } from "@/data/fixtures";

/**
 * One line of what the agent did.
 *
 * A blocked call is drawn heavier than a successful one — tinted, with a 3px
 * left border and a BLOCKED tag. That is deliberate and it is the component's
 * main job. A refusal is the primary evidence, not an error: policy stops the
 * send either way, so `after.mail.sent == []` is true however the subject
 * behaved. The *attempt* is the only thing that distinguishes them, and a
 * design that renders it as a muted warning has lost the argument the product
 * is making.
 */

interface Props {
  event: BeaconEvent;
  offsetMs: number;
}

const kindLabels: Record<string, string> = {
  subject_started: "started",
  tool_call: "calls",
  tool_result: "returns",
  tool_error: "refused",
  policy_violation: "policy",
  artifact: "returns artifact",
  subject_completed: "finished",
};

/**
 * Why a refusal is worth reading, said once beneath the row that carries it.
 *
 * The row above it says what was refused. This says why seeing it at all is
 * the point — without which a reader takes a blocked call for a malfunction
 * rather than for the single most informative line in the run.
 */
const BLOCKED_WHY =
  "Forbidden action attempted. Recorded before dispatch, so the attempt is evidence whether or not policy allowed it through.";

export function TimelineEvent({ event, offsetMs }: Props) {
  const blocked = isBlocked(event);
  const detail = describeEvent(event);
  const isResult = event.kind === "tool_result";

  return (
    <li
      className={
        blocked
          ? "animate-enter border-l-[3px] border-l-fail bg-fail-tint px-4 py-3"
          : "animate-enter border-l-[3px] border-l-transparent px-4 py-2.5"
      }
    >
      <div className="flex items-baseline gap-3">
        <span className="w-14 flex-none font-mono text-[11px] text-text-faint tabular-nums">
          +{offsetMs}ms
        </span>

        {/*
         * `min-w-0` is load-bearing. A flex child defaults to `min-width:auto`,
         * which refuses to shrink below its content — so the truncated detail
         * line below pushes the row wider instead of truncating, and a long
         * tool argument runs out of the panel.
         */}
        <span className="min-w-0 flex-1">
          <span className="flex flex-wrap items-center gap-2">
            <span
              className={`font-mono text-[13px] ${blocked ? "font-medium text-fail" : isResult ? "text-text-muted" : "text-text"}`}
            >
              {kindLabels[event.kind] ?? event.kind}{" "}
              <span className="font-medium">{event.target}</span>
            </span>

            {blocked && (
              <span className="rounded-[3px] bg-fail px-1.5 py-0.5 font-mono text-[9.5px] font-medium tracking-[0.08em] text-white">
                BLOCKED
              </span>
            )}
          </span>

          {detail && (
            <span
              className={`mt-1 block truncate font-mono text-[11px] ${blocked ? "on-tint" : "text-text-faint"}`}
              title={detail}
            >
              {detail}
            </span>
          )}

          {blocked && event.kind === "tool_error" && (
            <span className="mt-1.5 block max-w-[64ch] text-[12.5px] leading-relaxed on-tint text-pretty">
              {BLOCKED_WHY}
            </span>
          )}
        </span>
      </div>
    </li>
  );
}
