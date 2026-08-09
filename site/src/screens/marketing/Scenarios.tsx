import { NextSteps } from "@/components/shell/NextSteps";
import { TerminalBlock } from "@/components/shell/TerminalBlock";
import { ScenarioCard } from "@/components/select/ScenarioCard";
import { facts, scenarios } from "@/data/fixtures";
import type { Go } from "@/router";

/**
 * The seven that ship.
 *
 * Read from `scenarios/` rather than listed, so the number on this page cannot
 * disagree with the repository. Grouped by what each one grades, because that
 * split is the useful distinction: state a service ended in, or the answer that
 * came back.
 *
 * Clicking a card opens the playground at that scenario. It used to open the
 * playground at step one, which asked the visitor to find again, in a grid of
 * seven, the card they had just chosen.
 */

interface Props {
  onGo: Go;
}

const families = [
  {
    key: "service state" as const,
    title: "Graded on what changed",
    blurb:
      "A synthetic mail or file service with policy on it. These ask whether an agent did the work without doing anything it was told not to — and the forbidden action is recorded as an attempt, so a refusal still counts as evidence.",
  },
  {
    key: "the answer" as const,
    title: "Graded on what came back",
    blurb:
      "No state to change; the question is whether the reply holds its shape and whether what is inside it is true. These two are separate checks on purpose, because an agent can hold a contract perfectly while inventing the contents.",
  },
];

export function Scenarios({ onGo }: Props) {
  return (
    <>
    <div className="mx-auto max-w-[1180px] px-5 py-14 sm:px-11">
      <header className="mb-12">
        <h1 className="mb-4 max-w-[24ch] text-[clamp(1.8rem,5vw,2.5rem)] leading-[1.1] font-medium tracking-[-0.035em] text-balance">
          {facts.scenarios} scenarios, and each one can fail.
        </h1>
        <p className="max-w-[66ch] text-[16px] leading-relaxed text-text-muted text-pretty">
          Every card says what would count as failing. That is not decoration: this project
          once shipped an assertion that policy made true whatever the subject did, which is a
          check that measures nothing. A scenario that cannot state its failure condition has
          the same problem.
        </p>
      </header>

      {families.map((family) => {
        const members = scenarios.filter((s) => s.graded_on === family.key);
        return (
          <section key={family.key} className="mb-14">
            <div className="mb-5">
              <h2 className="mb-2 text-[clamp(1.2rem,3vw,1.45rem)] leading-tight font-medium tracking-[-0.025em]">
                {family.title}{" "}
                <span className="font-mono text-[15px] text-text-faint">{members.length}</span>
              </h2>
              <p className="max-w-[66ch] text-[14.5px] leading-relaxed text-text-muted text-pretty">
                {family.blurb}
              </p>
            </div>

            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
              {members.map((scenario) => (
                <ScenarioCard
                  key={scenario.slug}
                  scenario={scenario}
                  selected={false}
                  onPick={() => onGo("playground", scenario.id)}
                />
              ))}
            </div>
          </section>
        );
      })}

      <section className="rounded-card border border-line bg-surface p-6">
        <h2 className="mb-3 text-[17px] font-medium">Or bring your own</h2>
        <p className="mb-4 max-w-[68ch] text-[14.5px] leading-relaxed text-text-muted text-pretty">
          A scenario pack can add its own synthetic service without editing Beacon. There is a
          worked one in the repository, with a test that runs it from outside the repository — so
          "no need to edit Beacon" is evidence rather than a claim.
        </p>
        <TerminalBlock copyable lines={["python3 -m beacon init my-first-probe --service notes"]} />
      </section>
    </div>

    <NextSteps
      onGo={onGo}
      lead="Every card above opens a recorded run of that scenario — including the subjects written to break it. The same seven are in the repository, as JSON you can copy and edit."
    />
    </>
  );
}
