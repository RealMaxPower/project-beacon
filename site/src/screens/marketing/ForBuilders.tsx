import { Disclosure } from "@/components/shell/Disclosure";
import { NextSteps } from "@/components/shell/NextSteps";
import { TerminalBlock } from "@/components/shell/TerminalBlock";
import { facts } from "@/data/fixtures";
import type { Go } from "@/router";

/**
 * The page for someone who has an agent and ships changes to it.
 *
 * The pitch is narrow on purpose: did today's change make it worse, and can you
 * find out before your users do. Everything here is a command they can run.
 */

interface Props {
  onGo: Go;
}

export function ForBuilders({ onGo }: Props) {
  return (
    <>
    <div className="mx-auto max-w-[1180px] px-5 py-14 sm:px-11">
      <header className="mb-12">
        <h1 className="mb-4 max-w-[24ch] text-[clamp(1.8rem,5vw,2.5rem)] leading-[1.1] font-medium tracking-[-0.035em] text-balance">
          Did today's change make your agent worse?
        </h1>
        <p className="max-w-[66ch] text-[16px] leading-relaxed text-text-muted text-pretty">
          Beacon has no model in it and never calls one. Your agent brings its own, so there is
          no key to hand over and no inference cost on Beacon's side. Grading is deterministic
          string and state comparison — reproducible, free, and it does not drift when somebody
          else updates a judge model underneath you.
        </p>
      </header>

      <section className="mb-14">
        <h2 className="mb-4 text-[clamp(1.3rem,3.2vw,1.6rem)] leading-tight font-medium tracking-[-0.025em]">
          Start from something that runs
        </h2>
        <TerminalBlock copyable lines={["python3 -m beacon init my-first-probe"]} />
        <p className="mt-4 max-w-[66ch] text-[14.5px] leading-relaxed text-text-muted text-pretty">
          That writes a scenario and two subjects: one that satisfies every assertion, and one
          that violates exactly one. Run both.{" "}
          <strong className="font-medium text-text">The second is meant to fail</strong> — and
          watching it fail is how you know the assertion measures something.
        </p>
      </section>

      <section className="mb-14">
        <h2 className="mb-4 text-[clamp(1.3rem,3.2vw,1.6rem)] leading-tight font-medium tracking-[-0.025em]">
          One run is not a measurement
        </h2>
        <p className="mb-5 max-w-[66ch] text-[15px] leading-relaxed text-text-muted text-pretty">
          <code className="font-mono text-text">--repeat</code> runs the same scenario against
          the same subject several times and compares the verdict, the state digests, and the
          per-assertion result vector.
        </p>
        <TerminalBlock
          copyable
          lines={[
            "python3 -m beacon run scenarios/inbox-briefing/scenario.json --repeat 5",
            "",
            "Determinism: STABLE across 5 runs (state shape, verdict, and",
            "assertion results identical).",
          ]}
        />
        <div className="mt-4 max-w-[72ch]">
          <Disclosure question="Won't a model-backed agent look non-deterministic every time?">
            <p>
              It would, if the comparison were byte-for-byte: a subject that rewrites its
              wording every run would be reported as non-deterministic however correctly it
              behaved. String contents are dropped from the comparison and everything around
              them is kept — a different number of drafts, a renamed or missing field, a
              changed count or flag, or a body that is sometimes empty all still diverge.
            </p>
          </Disclosure>
        </div>
      </section>

      <section className="mb-14">
        <h2 className="mb-4 text-[clamp(1.3rem,3.2vw,1.6rem)] leading-tight font-medium tracking-[-0.025em]">
          Fail the build when it regresses
        </h2>
        <p className="mb-5 max-w-[66ch] text-[16px] leading-relaxed font-medium text-pretty">
          Non-zero exit, so CI fails — and comparison is by pass rate, not by a single run.
        </p>
        <TerminalBlock
          copyable
          lines={[
            "# Against a committed snapshot, recorded on the first run",
            "python3 -m beacon run scenarios/inbox-briefing/scenario.json \\",
            "  --repeat 10 --baseline baselines/reference.json",
            "",
            "# Or against the last 20 runs already in the output directory",
            "python3 -m beacon run scenarios/inbox-briefing/scenario.json \\",
            "  --repeat 10 --baseline-recent 20",
          ]}
        />
        <div className="mt-4 max-w-[72ch]">
          <Disclosure question="Why a rate, and not just whether this run passed?">
            <p>
              Because a subject failing a quarter of the time still passes three single-run
              comparisons in four. A drop counts as a regression only when the sample rules out
              chance, so a flaky agent does not fail your build at random — and how many runs
              it takes to prove one scales with how flaky the baseline said the subject was.
            </p>
          </Disclosure>
        </div>
      </section>

      <section className="mb-14">
        <h2 className="mb-4 text-[clamp(1.3rem,3.2vw,1.6rem)] leading-tight font-medium tracking-[-0.025em]">
          Exit codes are the integration
        </h2>
        <p className="mb-6 max-w-[66ch] text-[15px] leading-relaxed text-text-muted text-pretty">
          There is no plugin to install and no reporting format to adopt. Beacon is a command
          that exits non-zero when something is wrong, which every CI system already
          understands.
        </p>

        <div className="overflow-x-auto rounded-card border border-line">
          <table className="w-full min-w-[38rem] border-collapse text-left">
            <thead>
              <tr className="bg-sunken">
                {["Exit", "Means", "When"].map((head) => (
                  <th
                    key={head}
                    className="border-b border-line px-4 py-3 font-mono text-[10.5px] font-medium uppercase tracking-[0.09em] text-text-faint"
                  >
                    {head}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {[
                [
                  "0",
                  "Nothing to act on",
                  "Every run passed, the runs agreed with each other, and none regressed against the baseline.",
                ],
                [
                  "1",
                  "Look at this",
                  "An assertion failed, two runs disagreed, or a pass rate dropped far enough that the sample rules out chance.",
                ],
                [
                  "2",
                  "The scenario is wrong",
                  "It would not load or validate. An authoring error, not a verdict about your agent.",
                ],
              ].map(([code, means, when]) => (
                <tr key={code} className="border-b border-line last:border-b-0">
                  <td className="px-4 py-3 font-mono text-[12.5px]">{code}</td>
                  <td className="px-4 py-3 text-[13.5px] whitespace-nowrap">{means}</td>
                  <td className="px-4 py-3 text-[13.5px] text-text-muted">{when}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <p className="mt-4 max-w-[68ch] text-[14px] leading-relaxed text-text-muted text-pretty">
          Note what 0 requires: passing is not enough on its own. A run that passed but
          disagreed with the run before it still fails the build, because a verdict that
          changes between identical runs is not a verdict you can act on.
        </p>
      </section>

      <section className="mb-14">
        <h2 className="mb-4 text-[clamp(1.3rem,3.2vw,1.6rem)] leading-tight font-medium tracking-[-0.025em]">
          Wrapping an agent that speaks neither MCP nor A2A
        </h2>
        <p className="mb-3 max-w-[66ch] text-[16px] leading-relaxed font-medium text-pretty">
          About thirty lines of JSONL over stdio.
        </p>
        <p className="mb-5 max-w-[66ch] text-[15px] leading-relaxed text-text-muted text-pretty">
          The child process receives one <code className="font-mono text-text">start</code>{" "}
          message carrying the goal, the tools this scenario exposes, and the artifact it must
          return. Assertions are never sent.
        </p>
        <TerminalBlock
          lines={[
            "{",
            '  "type": "start",',
            '  "run_id": "run-...",',
            '  "scenario": { "goal": "...", "output_contract": { "artifact": "summary" } },',
            '  "tools": [ { "name": "mail_list_messages", "inputSchema": {} } ]',
            "}",
          ]}
          label="what your bridge receives"
        />
        <div className="mt-4 max-w-[72ch]">
          <Disclosure question="What happens if the bridge calls a tool that isn't in that list?">
            <p>
              The tool list is authoritative: anything else is refused and recorded as an
              attempt. A requirement the subject was never told about is not one it can meet,
              which is why the contract travels with the goal.
            </p>
          </Disclosure>
        </div>
      </section>

      <section className="rounded-card border border-line bg-surface p-6">
        <h2 className="mb-3 text-[17px] font-medium">
          How this project checks its own verdicts
        </h2>
        <p className="mb-4 max-w-[70ch] text-[14.5px] leading-relaxed text-text-muted text-pretty">
          A passing test suite shows the pipeline runs. It does not show the verdicts are
          right, because for a long time every subject Beacon had graded was written by Beacon
          against the assertions doing the grading. So there are now {facts.subjects} subjects
          that behave the way a real agent plausibly does — labelling handled mail, citing ids
          in uppercase, obeying an injected instruction, crashing, hanging, corrupting stdout —
          each with the verdict it should produce recorded next to it.
        </p>
        <dl className="grid grid-cols-2 gap-4 border-t border-line pt-4 sm:grid-cols-4">
          {[
            { k: "Subjects", v: String(facts.subjects) },
            { k: "Should PASS", v: String(facts.subjects_by_expected_verdict.PASS) },
            { k: "Should FAIL", v: String(facts.subjects_by_expected_verdict.FAIL) },
            { k: "Open defects", v: String(facts.subjects_with_open_defects) },
          ].map((stat) => (
            <div key={stat.k}>
              <dt className="mb-1.5 font-mono text-[10.5px] uppercase tracking-[0.1em] text-text-faint">
                {stat.k}
              </dt>
              <dd className="font-mono text-[19px]">{stat.v}</dd>
            </div>
          ))}
        </dl>
        {/*
         * The point of this section, and it is about Beacon rather than about
         * the subjects. "Six were wrong" on its own reads as six bad subjects,
         * which is the opposite of what happened.
         */}
        <div className="mt-5 border-t border-line pt-4">
          <p className="mb-3 text-[14.5px] leading-snug font-medium text-balance">
            Six of the first thirteen got the wrong verdict — from Beacon.
          </p>
          <Disclosure question="Which six, and what was wrong with them?">
            <p>
              Not close calls. A subject that did the task correctly and took three seconds to
              shut down was reported INCOMPLETE with every assertion passing. One that labelled
              the mail it handled, using a tool Beacon had advertised to it, was reported FAIL.
              All six are fixed, and this suite is what keeps them fixed — because until it
              existed, every subject Beacon had ever graded was written by Beacon, against the
              assertions doing the grading.
            </p>
          </Disclosure>
        </div>
      </section>
    </div>

    <NextSteps
      onGo={onGo}
      lead={`Every command on this page runs against the ${facts.scenarios} scenarios that ship, so you can watch the shape of it before pointing anything at your own agent.`}
    />
    </>
  );
}
