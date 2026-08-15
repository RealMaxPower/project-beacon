/**
 * The authored half of the documentation index.
 *
 * Filenames come from `facts.docs` and `facts.surveys`, which are derived from
 * what is on disk. These are the sentences a person wrote about each one, and
 * the handful of directories that are not documents but are where a reader
 * actually goes next.
 *
 * They live here rather than in a screen because both designs render this list.
 * A second copy would be a second place for a document to be described
 * wrongly, and the description is the only part of a card that a test cannot
 * check against the filesystem.
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
export const ELSEWHERE = [
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

export const docDescriptions: Record<string, string> = {
  "agent-builders.md":
    "The shortest path if you have an agent: point Beacon at it, measure how often it fails rather than whether it failed once, and fail CI when it regresses.",
  "failure-taxonomy.md":
    "The ninety-five failure modes Beacon means to measure, the four tests a candidate has to pass to be one of them, and the list of candidates that were rejected with the reason each was turned down.",
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
  "releasing.md":
    "How a version reaches PyPI, and the three pieces of state that live outside the repository: the trusted publisher, the environment, and the workflow switch a clone cannot see.",
  "production-readiness.md":
    "What Beacon is ready to be trusted with and what it is not, one limitation at a time, each with the file or command behind it and what would change the answer.",
  "a2a-survey.md":
    "Beacon's own A2A client, run against all five official SDKs as local servers. It found seven defects in the client — five of which would have reported a working agent as broken.",
  "hosted-agent-probe.md":
    "Twenty-nine hosted agents, graded offline from stored evidence bundles. Includes what the first pass got wrong and why re-grading was free.",
  "hosted-mcp-survey.md": "Beacon's MCP client against 200 hosted servers from the official registry. One initialize and one tools/list each; no tool calls were made.",
};
