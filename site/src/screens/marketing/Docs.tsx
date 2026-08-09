import { NextSteps } from "@/components/shell/NextSteps";
import { facts } from "@/data/fixtures";
import type { Go } from "@/router";

/**
 * Every document, linked to the file it is.
 *
 * The list is generated from `docs/` and `conformance/`, so a card cannot point
 * at a page that was renamed or deleted. The descriptions are authored; the
 * filenames are not.
 */

const REPO = "https://github.com/RealMaxPower/project-beacon/blob/main";
const TREE = "https://github.com/RealMaxPower/project-beacon/tree/main";

/**
 * Directories and top-level files worth a card of their own.
 *
 * These are not under `docs/`, so `facts.docs` does not carry them — but they
 * are where a reader actually goes next, and leaving them off made this page a
 * list of the documentation rather than a map of the project.
 */
const ELSEWHERE = [
  {
    path: "README.md",
    href: `${REPO}/README.md`,
    body: "What works, what does not, and the sixty-second path from clone to an evidence bundle.",
  },
  {
    path: "schemas/",
    href: `${TREE}/schemas`,
    body: "The published scenario and evidence JSON Schema, kept in step with the code by test.",
  },
  {
    path: "examples/scenario-pack/",
    href: `${TREE}/examples/scenario-pack`,
    body: "A worked pack that brings its own synthetic service, with a test that runs it from outside the repository.",
  },
  {
    path: "examples/subjects/",
    href: `${TREE}/examples/subjects`,
    body: "The adversarial suite: subjects that behave the way a real agent plausibly does. Writing it caught Beacon returning the wrong verdict on six of the first thirteen.",
  },
];

const descriptions: Record<string, string> = {
  "agent-builders.md":
    "The shortest path if you have an agent: point Beacon at it, measure how often it fails rather than whether it failed once, and fail CI when it regresses.",
  "architecture.md":
    "The run lifecycle, and the boundary that keeps the core ignorant of any particular model provider or agent runtime.",
  "protocol-contracts.md":
    "What Beacon sends and expects over MCP, A2A and the JSONL bridge, message by message.",
  "running-it-yourself.md":
    "Running against a real model or a GUI host. Where the API key goes — your environment, never the command line — and how to wire the MCP façade into a desktop client.",
  "beacon-test-run.md":
    "The manual test plan for this site, walked end to end against a dev server. Three defects and seven notes, written down whether or not they were flattering.",
  "windows.md":
    "Why a literal python3 is a Store alias stub on Windows, and the two tests that spawned one and passed for weeks without running anything.",
  "a2a-survey.md":
    "Beacon's own A2A client, run against all five official SDKs as local servers. It found seven defects in the client — five of which would have reported a working agent as broken.",
  "hosted-agent-probe.md":
    "Twenty-nine hosted agents, graded offline from stored evidence bundles. Includes what the first pass got wrong and why re-grading was free.",
  "hosted-mcp-survey.md": "Beacon's MCP client against 200 hosted servers from the official registry. One initialize and one tools/list each; no tool calls were made.",
};

function Card({ path, name }: { path: string; name: string }) {
  return (
    <a
      href={`${REPO}/${path}/${name}`}
      className="flex h-full flex-col rounded-card border border-line bg-surface p-5 transition-colors hover:border-line-strong"
    >
      <p className="mb-2 font-mono text-[12.5px] font-medium text-text">
        {path}/{name}
      </p>
      <p className="text-[13.5px] leading-relaxed text-text-muted text-pretty">
        {descriptions[name] ?? "See the repository."}
      </p>
    </a>
  );
}

interface Props {
  onGo: Go;
}

export function Docs({ onGo }: Props) {
  return (
    <>
    <div className="mx-auto max-w-[1180px] px-5 py-14 sm:px-11">
      <header className="mb-12">
        <h1 className="mb-4 max-w-[24ch] text-[clamp(1.8rem,5vw,2.5rem)] leading-[1.1] font-medium tracking-[-0.035em] text-balance">
          Documentation, and the surveys behind the claims.
        </h1>
        <p className="max-w-[64ch] text-[16px] leading-relaxed text-text-muted text-pretty">
          Everything lives in the repository. The surveys are the working records the README
          cites — where a number in the documentation came from, and what it cost to find out
          it was wrong.
        </p>
      </header>

      <section className="mb-12">
        <h2 className="mb-5 font-mono text-[10.5px] uppercase tracking-[0.1em] text-text-faint">
          Docs
        </h2>
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {facts.docs.map((name) => (
            <Card key={name} path="docs" name={name} />
          ))}
        </div>
      </section>

      <section className="mb-12">
        <h2 className="mb-5 font-mono text-[10.5px] uppercase tracking-[0.1em] text-text-faint">
          Conformance surveys
        </h2>
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {facts.surveys.map((name) => (
            <Card key={name} path="conformance" name={name} />
          ))}
        </div>
      </section>

      <section>
        <h2 className="mb-5 font-mono text-[10.5px] uppercase tracking-[0.1em] text-text-faint">
          Elsewhere in the repository
        </h2>
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {ELSEWHERE.map((item) => (
            <a
              key={item.path}
              href={item.href}
              className="flex h-full flex-col rounded-card border border-line bg-surface p-5 transition-colors hover:border-line-strong"
            >
              <p className="mb-2 font-mono text-[12.5px] font-medium text-text">{item.path}</p>
              <p className="text-[13.5px] leading-relaxed text-text-muted text-pretty">
                {item.body}
              </p>
            </a>
          ))}
        </div>
      </section>
    </div>

    {/*
     * No repository card here: every card on this page is already a link into
     * the repository, and a fourth way to say "go to GitHub" at the bottom of
     * a page made of GitHub links is noise.
     */}
    <NextSteps
      hideRepo
      onGo={onGo}
      lead="Every card above is a file in the repository. If you would rather see the thing working than read about it, the playground replays a run end to end."
    />
    </>
  );
}
