import type { ScenarioSummary } from "@/data/types";
import { scenarioBrief } from "@/data/copy";

/**
 * What scenario this page is about, said on the page.
 *
 * Every `/playground/<id>` is prerendered as its own document with its own
 * title, its own meta description and its own JSON-LD, and until this existed
 * none of that reached the body. Stripping head, script and markup from the
 * eighty-three built pages left **eight** distinct visible bodies, seventy-six
 * of them identical, and **none** of the eighty-three contained the name of the
 * scenario it was serving. A search result promising "The first payment landed
 * and the second cannot" opened a page whose every visible word was about
 * something else.
 *
 * It renders for all of them, not only the seventy-six without recorded runs.
 * That is the measurement talking: the seven replayable ones were equally
 * anonymous, because their bodies differ only in subject cards, and a subject
 * card names the agent rather than the scenario. Scoping this to the ones
 * without runs would have left the seven most-visited pages unable to say what
 * they were for.
 *
 * The heading level is not a prop. This is rendered once per document, which is
 * an invariant of the route rather than a decision for a caller — and a prop
 * would invite the caller to be wrong and the lint pass to notice afterwards.
 */

interface Props {
  scenario: ScenarioSummary;
}

export function ScenarioHeader({ scenario }: Props) {
  const copy = scenarioBrief(scenario);

  /*
   * A div, not a `header`. The playground already renders this inside its own
   * `<header>`, and a nested one is still a banner landmark — which would have
   * given the page two, with nothing to tell them apart. The same mistake the
   * playground's own comment records about `<main>`.
   */
  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <span className="rounded-[3px] border border-line bg-sunken px-1.5 py-0.5 font-mono text-[10px] text-text-muted">
          graded on {scenario.graded_on}
        </span>
        <span className="font-mono text-[10px] text-text-faint">{scenario.slug}</span>
      </div>

      {/*
       * The `h1` for this route. The playground's own line — "Watch an agent
       * work, then read the evidence." — is the heading of the index, and it
       * was being reused verbatim on every playground document, so the one
       * element search engines and heading navigation lean on hardest carried
       * no page-specific information anywhere on the site.
       */}
      <h1 className="text-[28px] leading-tight font-medium tracking-[-0.03em] text-balance">
        {copy.question}
      </h1>

      <p className="mt-3 font-mono text-[11.5px] text-text-faint">
        {scenario.assertions.length} assertions · {scenario.tools.length} tools
      </p>

      <dl className="mt-5 grid gap-5 sm:grid-cols-2">
        <div>
          <dt className="mb-1.5 font-mono text-[10px] tracking-[0.09em] text-text-faint uppercase">
            What it tests
          </dt>
          <dd className="max-w-[60ch] text-[14px] leading-relaxed text-text-muted text-pretty">
            {copy.tests}
          </dd>
        </div>
        <div>
          <dt className="mb-1.5 font-mono text-[10px] tracking-[0.09em] text-text-faint uppercase">
            Fails when
          </dt>
          <dd className="max-w-[60ch] text-[14px] leading-relaxed text-text-muted text-pretty">
            {copy.fails}
          </dd>
        </div>
      </dl>
    </div>
  );
}
