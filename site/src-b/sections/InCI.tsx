import { Band } from "../components/Band";

/**
 * What adopting this actually looks like, which the quickstart does not cover.
 *
 * The quickstart gets a reader to one bundle. This is the next question — how
 * does it live in a pipeline — and the answer is unusually short, so it is
 * worth saying rather than leaving to the docs: there is no plugin and no
 * report format, because the integration is the exit code.
 *
 * The codes are read off `beacon/cli.py`. `run` returns 0 only when every run
 * passed *and* the runs agreed with each other *and* nothing regressed against
 * the baseline; 1 when any of those fails; 2 when the scenario itself would not
 * load, which is an authoring error and not a verdict about anyone's agent.
 * That third row is the one people are surprised by, and printing it beside the
 * other two is what stops a broken scenario being read as a failing agent.
 */

const CODES = [
  [
    "0",
    "Nothing to act on",
    "Every run passed, the runs agreed with each other, and none regressed against the baseline.",
  ],
  [
    "1",
    "Look at this",
    "An assertion failed, two runs disagreed, or the result moved against the recorded baseline.",
  ],
  [
    "2",
    "The scenario is wrong",
    "It would not load or validate. An authoring error, not a verdict about your agent.",
  ],
] as const;

const COMMANDS = [
  [
    "python3 -m beacon run inbox-briefing --repeat 5",
    "same scenario, five times — verdict, state digests and per-assertion results compared",
  ],
  [
    "python3 -m beacon run inbox-briefing \\\n    --repeat 10 --baseline baselines/reference.json",
    "against a committed snapshot, recorded on the first run",
  ],
  [
    "python3 -m beacon run inbox-briefing \\\n    --repeat 10 --baseline-recent 20",
    "or against the last 20 runs already in the output directory",
  ],
] as const;

export function InCI() {
  return (
    <Band
      id="ci"
      eyebrow="11 — In your pipeline"
      heading="The integration is the exit code."
      lede={
        <>
          There is no plugin to install and no reporting format to adopt. Beacon
          is a command that exits non-zero when something is wrong, which every
          CI system already understands.
        </>
      }
    >
      <div className="b-cells mb-8 grid gap-3 sm:grid-cols-3">
        {CODES.map(([code, verdict, when]) => (
          <div key={code} className="rounded-lg border border-b-line px-4 py-3.5">
            <div className="flex items-baseline gap-2.5">
              <span className="font-b-mono text-[15px] text-b-src">{code}</span>
              <span className="b-eyebrow text-b-faint">{verdict}</span>
            </div>
            <p className="mt-1.5 text-[12.5px] leading-snug text-b-muted">{when}</p>
          </div>
        ))}
      </div>

      <p className="b-lede mb-8 max-w-[66ch] text-[15px]">
        Note what <span className="font-b-mono text-[13.5px] text-b-src">0</span>{" "}
        requires. Passing is not enough on its own: a run that passed but
        disagreed with the run before it still fails the build, because a verdict
        that changes between identical runs is not a verdict anyone can act on.
        This is also why the useful question is how often an agent fails rather
        than whether it failed once.
      </p>

      <div className="overflow-hidden rounded-xl border border-b-line bg-[#0e1116]">
        <div className="flex items-center gap-2 border-b border-white/10 px-4 py-2.5">
          <span aria-hidden="true" className="h-2.5 w-2.5 rounded-full bg-[#ff6e55]" />
          <span aria-hidden="true" className="h-2.5 w-2.5 rounded-full bg-[#f0ac3a]" />
          <span aria-hidden="true" className="h-2.5 w-2.5 rounded-full bg-[#5bdd93]" />
          <span className="ml-2 font-b-mono text-[11px] text-[#79828f]">bash</span>
        </div>
        <ol className="px-5 py-5">
          {COMMANDS.map(([command, note]) => (
            <li key={command} className="py-2">
              <p className="font-b-mono text-[12.5px] whitespace-pre-wrap text-[#f5f7fa]">
                <span className="text-[#4ed8ea]">$ </span>
                {command}
              </p>
              <p className="mt-1 font-b-mono text-[11.5px] text-[#79828f]"># {note}</p>
            </li>
          ))}
        </ol>
      </div>
    </Band>
  );
}
