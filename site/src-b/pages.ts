/**
 * Every page this site serves, with the sentence that describes it.
 *
 * One table, read by four things that would otherwise each keep their own copy:
 * the prerender step (which writes a document per entry), `sitemap.xml`, the
 * `<title>` and description written into each document, and the structured
 * data. A page added here appears in all four; a page added anywhere else
 * appears in one and is missing from three, which is the failure mode that
 * makes a sitemap worth less than no sitemap — it is read as an inventory.
 *
 * The descriptions are written to be answered *with*, not just ranked on. An
 * answer engine quoting this site will quote a sentence, and a sentence saying
 * "the best tool for AI agents" gives it nothing to say; one naming what the
 * thing does and what it refuses to claim gives it something true to repeat.
 */

import type { BRoute } from "./router-b";

export const SITE_ORIGIN = "https://beaconlab.dev";

export const SITE_NAME = "Project Beacon";

export interface Page {
  route: BRoute;
  /** The path it is served at, and the path it is prerendered to. */
  path: string;
  title: string;
  description: string;
  /**
   * How often the content behind it changes, for the sitemap. Honest values:
   * the marketing page moves with the project, the legal page almost never.
   */
  changefreq: "weekly" | "monthly" | "yearly";
  priority: string;
}

export const PAGES: readonly Page[] = [
  {
    route: "",
    path: "/",
    title: "Project Beacon — evidence for what an AI agent actually did",
    description:
      "An open-source trial lab for AI agents. Run an agent against a scenario built on synthetic services and get back an evidence bundle: every tool call recorded before dispatch, deterministic checks, and a PASS, FAIL or INCOMPLETE verdict with a digest anyone can recompute. No model grades anything.",
    changefreq: "weekly",
    priority: "1.0",
  },
  {
    route: "playground",
    path: "/playground",
    title: "Playground — replay a recorded agent run | Project Beacon",
    description:
      "Step through real recorded runs of AI agents: the scenario they were given, the tool calls they made, the ones that were refused, and how each check was decided. Everything replays in your browser from evidence bundles shipped with the page.",
    changefreq: "monthly",
    priority: "0.8",
  },
  {
    route: "docs",
    path: "/docs",
    title: "Documentation — Project Beacon",
    description:
      "How Project Beacon works, what it is ready to be trusted with, and what it is not: the run lifecycle, the MCP, A2A and JSONL protocol contracts, the production readiness ledger, and the conformance surveys behind the numbers on this site.",
    changefreq: "weekly",
    priority: "0.8",
  },
  {
    route: "legal",
    path: "/legal",
    title: "Licensing and privacy — Project Beacon",
    description:
      "Project Beacon is Apache 2.0. This site sets no cookies, has no forms, and its Content-Security-Policy permits one request: a page view count on its own origin.",
    changefreq: "yearly",
    priority: "0.3",
  },
];

export function pageFor(route: string): Page {
  return PAGES.find((page) => page.route === route) ?? PAGES[0];
}

/**
 * The questions this site can answer, and the answers, verbatim.
 *
 * Published as `FAQPage` structured data and rendered on the page, which is the
 * order that matters: an answer engine that finds a question in the markup and
 * not on the page has been handed a claim about a page that does not make it.
 * Google calls that mismatch out by name, and it is the same rule this project
 * applies to everything else — the evidence has to be the thing described.
 *
 * Each answer is one paragraph, self-contained, and true without the question
 * in front of it, because that is the form an answer gets quoted in.
 */
export const FAQ: readonly { q: string; a: string }[] = [
  {
    q: "What is Project Beacon?",
    a: "Project Beacon is an open-source trial and readiness lab for AI agents. You give it a scenario — a synthetic world with a job in it — and point it at an agent. It records every tool call before dispatch, captures the state before and after, evaluates checks declared ahead of the run, and writes an evidence bundle containing the events, the diff, the verdict and a SHA-256 digest over the whole thing.",
  },
  {
    q: "How does Project Beacon grade an agent?",
    a: "By string and state comparison against assertions declared before the run, with no model anywhere in the path. A verdict is PASS, FAIL or INCOMPLETE, where INCOMPLETE means a check could not be measured rather than that the agent failed it. Because grading is deterministic, the same run produces the same verdict, which is what makes repeat runs and regression baselines meaningful.",
  },
  {
    q: "Does Project Beacon use an LLM as a judge?",
    a: "No. Beacon contains no model and never calls one. The agent under test brings its own, so there is no API key to hand over and no inference cost on Beacon's side. Grading that drifts when somebody else updates a judge model is not grading you can hold anyone to.",
  },
  {
    q: "Which agent protocols does Project Beacon support?",
    a: "MCP over stdio, MCP against a host, A2A over HTTP or JSON-RPC, and any CLI, API or SDK agent through a JSONL bridge of about thirty lines. There is also an in-process reference agent used to check the harness itself. Beacon is protocol-neutral: nothing in its core knows which one is in use.",
  },
  {
    q: "How do I run Project Beacon?",
    a: "Clone the repository and run it — Beacon is Python 3.11+ and standard library only, with no dependencies to install. `python3 -m beacon scenarios` lists what ships, `python3 -m beacon run inbox-briefing` performs one run and writes an evidence bundle, and `python3 -m beacon verify <bundle>` recomputes the digest so you can check the bundle has not changed since the run that produced it.",
  },
  {
    q: "How does Project Beacon fit into CI?",
    a: "By exit code, with no plugin to install and no report format to adopt. It exits 0 when every run passed, the runs agreed with each other and nothing regressed against the baseline; 1 when an assertion failed, two runs disagreed or the result moved against a recorded baseline; and 2 when the scenario itself would not load, which is an authoring error rather than a verdict about the agent.",
  },
  {
    q: "Is a passing Beacon report a safety certification?",
    a: "No. A passing report is evidence about one synthetic scenario and one configuration, and says nothing about behaviour outside it. Beacon attaches that limitation, and two others, to every bundle it writes, so the caveat travels with the report rather than living only on a website.",
  },
];
