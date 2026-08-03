import { InboxView } from "@/components/select/InboxView";
import { WorldView } from "@/components/select/WorldView";
import { JsonViewer } from "@/components/shell/JsonViewer";
import { scenarioFor, scenarioSource } from "@/data/fixtures";
import type { Evidence } from "@/data/types";

/**
 * Step three: the world, before anything touches it.
 *
 * Reading this screen is what makes every later one legible. The fixtures come
 * out of the scenario in the evidence bundle, so what is drawn here is exactly
 * what the subject was given — including the message carrying an injected
 * instruction and the one it is not allowed to open.
 */

interface Props {
  evidence: Evidence;
  expert: boolean;
}

interface MailFixture {
  messages?: Parameters<typeof InboxView>[0]["messages"];
  policy?: Record<string, unknown>;
}

export function WorldBefore({ evidence, expert }: Props) {
  const scenario = scenarioFor(evidence);
  const mail = scenario.fixtures?.mail as MailFixture | undefined;
  const messages = mail?.messages ?? [];

  if (expert) {
    const file = scenarioSource(scenario.slug);
    return (
      <section className="flex flex-col gap-4">
        <h2 className="text-2xl leading-tight font-medium tracking-[-0.025em]">
          The scenario, as declared.
        </h2>
        {file ? (
          <JsonViewer source={file.text} label={file.path} maxHeight={560} />
        ) : (
          // Named for what it is. The projection is not the file, and a panel
          // that says otherwise is the defect this branch exists to avoid.
          <JsonViewer
            value={scenario}
            label="site/src/data/generated/scenarios.json — projection, not the scenario file"
            provenance="illustrative"
          />
        )}
      </section>
    );
  }

  return (
    <section>
      <header className="mb-6">
        <p className="mb-2 font-mono text-[11px] uppercase tracking-[0.12em] text-text-faint">
          {scenario.name}
        </p>
        <h2 className="mb-2 text-2xl leading-tight font-medium tracking-[-0.025em] text-balance">
          The world, before the agent touches it
        </h2>
        <p className="mb-4 max-w-[64ch] text-[15px] leading-relaxed text-text-muted text-pretty">
          {scenario.description}
        </p>
        <p className="max-w-[64ch] rounded-card border border-line bg-sunken p-4 text-[13.5px] leading-relaxed text-text-muted text-pretty">
          <span className="font-medium text-text">What it was told: </span>
          {scenario.goal}
        </p>
      </header>

      {messages.length > 0 ? (
        <>
          <p className="mb-4 max-w-[68ch] text-[14px] leading-relaxed text-text-muted text-pretty">
            A synthetic mailbox. {messages.length} messages, all invented.{" "}
            {messages.filter((m) => m.labels.includes("action_required")).length} need a reply,{" "}
            {messages.filter((m) => m.protected).length} is protected, and one carries an
            instruction aimed at the agent rather than at you.
          </p>
          <InboxView messages={messages} />
        </>
      ) : (
        <WorldView scenario={scenario} />
      )}

      <dl className="mt-5 grid gap-4 sm:grid-cols-2">
        <div className="rounded-card border border-line bg-surface p-4">
          <dt className="mb-2 font-mono text-[10.5px] uppercase tracking-[0.1em] text-text-faint">
            Tools it may call
          </dt>
          <dd className="flex flex-wrap gap-1.5">
            {scenario.tools.length > 0 ? (
              scenario.tools.map((tool) => (
                <span
                  key={tool}
                  className="rounded-[3px] border border-line bg-sunken px-1.5 py-1 font-mono text-[10.5px]"
                >
                  {tool}
                </span>
              ))
            ) : (
              // Four scenarios expose no tools at all. An empty row read as a
              // rendering failure; "none" is the actual answer, and it is the
              // reason those runs are graded on the reply instead of on state.
              <span className="font-mono text-[12px] text-text-muted">none</span>
            )}
          </dd>
          <p className="mt-2.5 text-xs leading-relaxed text-text-faint text-pretty">
            {scenario.tools.length > 0
              ? "This list is authoritative. Anything else is refused and recorded as an attempt."
              : "This scenario gives the subject nothing to call, so there is no state to change — it is graded on what it returned."}
          </p>
        </div>

        <div className="rounded-card border border-line bg-surface p-4">
          <dt className="mb-2 font-mono text-[10.5px] uppercase tracking-[0.1em] text-text-faint">
            What it must return
          </dt>
          <dd className="font-mono text-[12.5px]">
            {scenario.output_contract?.artifact ?? "—"}
          </dd>
          <p className="mt-2.5 text-xs leading-relaxed text-text-faint text-pretty">
            {scenario.output_contract?.description ??
              "No output contract; this scenario is graded on state alone."}
          </p>
        </div>
      </dl>
    </section>
  );
}
