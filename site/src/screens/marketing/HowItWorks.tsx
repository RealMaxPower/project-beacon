import { Disclosure } from "@/components/shell/Disclosure";
import { NextSteps } from "@/components/shell/NextSteps";
import { PipelineDiagram } from "@/components/shell/PipelineDiagram";
import { TerminalBlock } from "@/components/shell/TerminalBlock";
import { facts } from "@/data/fixtures";
import type { Go } from "@/router";

/**
 * Four things, in order, every time.
 *
 * The taps are the content. Any test runner has a pipeline; what makes this one
 * worth drawing is where it records — and that an attempt is recorded before
 * dispatch, which is what makes a refusal evidence rather than an absence.
 */

const STEPS = [
  {
    name: "A scenario declares the work",
    detail:
      "A goal, the tools the agent may use, the forbidden actions, the output contract, and the seed data. The tool list is authoritative and assertions are never sent — a requirement the subject is never told about is not one it can meet.",
    // Not "validated against the published JSON Schema" — that phrasing is
    // wrong, and the CHANGELOG records it being removed from the README for
    // the same reason. Nothing under `beacon/` reads `schemas/`: validation is
    // enforced in code, and the published schema is kept in step with that code
    // by test.
    tap: "validated in code at load, kept in step with the published schema by test",
  },
  {
    name: "Your agent works inside a synthetic world",
    detail:
      "In process, a command it wraps, an MCP host, or an A2A endpoint. Beacon never needs your framework. Mail and file services with scoped tools and policy enforcement are seeded from the fixture, mutated by the agent, then reset.",
    tap: "events.json — every call, result, refusal and artifact, in order",
  },
  {
    name: "Every call is offered to the router, which decides",
    detail:
      "The attempt is recorded before the router rules on it. This is why a refused attempt is still evidence, and why a check on the final state can pass an agent that tried everything it was forbidden to do.",
    tap: "policy_violation, then tool_error carrying ToolPolicyError",
  },
  {
    name: "Evidence is written, whatever happened",
    detail:
      "Assertions resolve by string and state comparison — no model sits anywhere in this path, which is what makes the verdict reproducible and free. The world is then rebuilt and compared, and that equality is itself asserted.",
    tap: "evidence.json, events.json, report.md — and reset_verified",
  },
];

const LEVELS = [
  ["0", "Black-box prompt or API", "Output and simulated final state"],
  ["1", "MCP", "Tool discovery, calls, responses, and resulting state"],
  ["2", "A2A", "Agent discovery, tasks, messages, statuses, and artifacts"],
  ["3", "CLI / API / SDK / container bridge", "Lifecycle, events, budgets, and termination"],
  ["4", "Native runtime adapter", "Runtime configuration, approvals, cost, and richer traces"],
];

interface Props {
  onGo: Go;
}

export function HowItWorks({ onGo }: Props) {
  return (
    <>
    <div className="mx-auto max-w-[1180px] px-5 py-14 sm:px-11">
      <header className="mb-12">
        <h1 className="mb-4 max-w-[20ch] text-[clamp(1.8rem,5vw,2.5rem)] leading-[1.1] font-medium tracking-[-0.035em] text-balance">
          Four things, in order, every time.
        </h1>
        <p className="max-w-[64ch] text-[16px] leading-relaxed text-text-muted text-pretty">
          There is no LLM judge anywhere in this pipeline. Grading is string and state
          comparison, which is why it is reproducible and free.
        </p>
      </header>

      <section className="mb-16 max-w-[72ch]">
        <PipelineDiagram steps={STEPS} />
      </section>

      <section className="mb-16">
        <h2 className="mb-4 text-[clamp(1.3rem,3.2vw,1.6rem)] leading-tight font-medium tracking-[-0.025em]">
          Why the attempt is what gets graded
        </h2>
        {/*
         * The two cards are the argument; the paragraph was the argument
         * restated in prose above them. It reads first as a claim you can take
         * in at a glance, with the reasoning underneath for whoever wants it.
         */}
        <p className="mb-6 max-w-[68ch] text-[16px] leading-relaxed font-medium text-pretty">
          One of these two assertions can never fail. Only the other one measures anything.
        </p>

        <div className="grid gap-4 lg:grid-cols-2">
          <article className="rounded-card border border-line border-l-[3px] border-l-line-strong bg-surface p-5">
            <p className="mb-3 font-mono text-[12.5px] font-medium text-text-muted">
              after.mail.sent == []
            </p>
            <p className="mb-3 text-[14px] leading-relaxed text-text-muted text-pretty">
              True whatever the subject did, because policy already prevents it. It passes for
              an agent that never considered sending and for one that tried three times.
            </p>
            <p className="font-mono text-[11px] uppercase tracking-[0.09em] text-text-faint">
              Measures nothing
            </p>
          </article>

          <article className="rounded-card border border-fail/30 border-l-[3px] border-l-fail bg-fail-tint p-5">
            <p className="mb-3 font-mono text-[12.5px] font-medium text-fail">
              send-never-attempted
            </p>
            <p className="mb-3 text-[14px] leading-relaxed on-tint text-pretty">
              Recorded before dispatch. An agent that tried and was refused fails this, and
              should — the refusal is Beacon's doing, not the agent's restraint.
            </p>
            <p className="font-mono text-[11px] uppercase tracking-[0.09em] on-tint">
              The one that means something
            </p>
          </article>
        </div>

        <div className="mt-4 max-w-[72ch]">
          <Disclosure question="How does an assertion that cannot fail get shipped?">
            <p>
              Policy blocks sending either way, so a check on the final mailbox would be true
              however the agent behaved. That is an assertion that cannot fail — and this
              scenario shipped one until a coverage check found it.
            </p>
          </Disclosure>
        </div>
      </section>

      <section className="mb-16">
        <h2 className="mb-4 text-[clamp(1.3rem,3.2vw,1.6rem)] leading-tight font-medium tracking-[-0.025em]">
          Five ways an agent can be the subject
        </h2>
        <p className="mb-6 max-w-[66ch] text-[15px] leading-relaxed text-text-muted text-pretty">
          The deeper the integration, the more evidence there is to collect. The scenario does
          not know which adapter is driving it, so the bundle has one shape either way.
        </p>

        <div className="overflow-x-auto rounded-card border border-line">
          <table className="w-full min-w-[46rem] border-collapse text-left">
            <thead>
              <tr className="bg-sunken">
                {["Level", "Interface", "Evidence available"].map((head) => (
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
              {LEVELS.map(([level, iface, evidence]) => (
                <tr key={level} className="border-b border-line last:border-b-0">
                  <td className="px-4 py-3 font-mono text-[12.5px]">{level}</td>
                  <td className="px-4 py-3 text-[13.5px]">{iface}</td>
                  <td className="px-4 py-3 text-[13.5px] text-text-muted">{evidence}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/*
         * The table is a capability model, not an inventory. Printing it without
         * this note would let the two deepest rows read as things you can use
         * today, which is the kind of claim the rest of this site argues against.
         */}
        <p className="mt-4 max-w-[70ch] rounded-card border border-line bg-sunken p-4 text-[13.5px] leading-relaxed text-text-muted text-pretty">
          The only level 4 subject today is Beacon's own reference agent, where Beacon is the
          runtime. No adapter exists for anyone else's runtime yet, and the two deepest rungs
          promise evidence — approvals, cost — that Beacon does not currently collect from any
          subject.
        </p>
      </section>

      <section>
        <h2 className="mb-4 text-[clamp(1.3rem,3.2vw,1.6rem)] leading-tight font-medium tracking-[-0.025em]">
          No bridge code for MCP or A2A
        </h2>
        <p className="mb-6 max-w-[68ch] text-[16px] leading-relaxed font-medium text-pretty">
          Point the flag at your agent. Beacon speaks both protocols itself.
        </p>
        <TerminalBlock
          copyable
          lines={[
            "# An agent that speaks A2A",
            "python3 -m beacon run scenarios/web-extraction-grounding/scenario.json \\",
            "  --adapter a2a --agent-url https://your-agent.example",
            "",
            "# An MCP host: Beacon serves the synthetic tools, your host connects",
            "python3 -m beacon run scenarios/inbox-briefing/scenario.json \\",
            '  --adapter mcp-host --command "your-agent --mcp-config {config}"',
          ]}
        />
        <div className="mt-4 max-w-[72ch]">
          <Disclosure question="What happens if an MCP client just disconnects?">
            <p>
              MCP has no completion signal, so a client that disconnects looks exactly like one
              that crashed. Beacon will not call that a pass: the façade offers a{" "}
              <code className="font-mono text-text">beacon_submit</code> tool, and a session
              that ends without it resolves to INCOMPLETE — the honest answer when Beacon
              cannot tell whether the work was done.
            </p>
          </Disclosure>
        </div>
      </section>
    </div>

    <NextSteps
      onGo={onGo}
      lead={`That is the whole pipeline. The playground walks one run through it end to end; the repository has the ${facts.scenarios} scenarios that ship, and the command to scaffold your own.`}
    />
    </>
  );
}
