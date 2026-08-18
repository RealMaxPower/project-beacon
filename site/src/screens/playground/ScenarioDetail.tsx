import type { ScenarioSummary } from "@/data/types";
import { assertionCopy, NO_RECORDED_RUN, scenarioBrief } from "@/data/copy";
import { ScenarioHeader } from "./ScenarioHeader";

/**
 * A scenario that ships with Beacon but has no recorded run on this site.
 *
 * Seventy-six of the eighty-three are in this position, and until this existed
 * every one of them was handed to step two of the wizard — "Which agent should
 * try it?" — above an empty grid, because `PickSubject` filters the recorded
 * bundles down to none for these and the only thing left to render was the
 * dashed "Connect your own" card. The page asked a question it had no answers
 * for and never said why.
 *
 * So this is not the wizard with a message in it. There is no step rail, no
 * action bar and no expert toggle, because there is no run to step through or
 * be expert about, and a rail whose remaining steps all lead to empty states is
 * an offer the page cannot honour.
 *
 * What it shows instead is what the scenario *is*: the goal it hands a subject,
 * the tools it exposes, and the checks it grades on. That material already
 * shipped in `scenarios.json` and had never been rendered anywhere. It is also
 * what makes these pages genuinely distinct from one another rather than
 * seventy-six copies of one screen.
 *
 * The synthetic world is named but not dumped. `tickets-context-pressure`
 * carries tens of kilobytes of fixture JSON, a `<pre>` of it converts to
 * markdown at roughly one to one, and the twin-size guard in
 * `tests/test_site_markdown.py` would then fail on precisely the pages with the
 * most to show.
 */

interface Props {
  scenario: ScenarioSummary;
  /** The scenarios that do have runs, so the way out is a number and a link. */
  replayable: ScenarioSummary[];
}

export function ScenarioDetail({ scenario, replayable }: Props) {
  const services = Object.keys(scenario.fixtures);

  return (
    <div className="mx-auto max-w-[1180px] px-5 pt-10 pb-10 sm:px-11">
      <header className="mb-8 border-b border-line pb-7">
        <ScenarioHeader scenario={scenario} />
      </header>

      <div className="rounded-card border border-dashed border-line-strong bg-surface p-6">
        <h2 className="mb-2 text-[17px] leading-snug font-medium">
          Nothing has been recorded against this one yet.
        </h2>
        <p className="max-w-[64ch] text-[14px] leading-relaxed text-text-muted text-pretty">
          {NO_RECORDED_RUN} The playground replays evidence bundles, and there is no bundle for
          this scenario — so rather than show you a run that never happened, it says so.
        </p>
        <p className="mt-5 mb-1.5 font-mono text-[10px] tracking-[0.09em] text-text-faint uppercase">
          Run it yourself
        </p>
        <p className="rounded-row border border-line bg-sunken p-3 font-mono text-[11.5px] leading-relaxed break-all text-text-muted">
          python3 -m beacon run {scenario.slug}
        </p>
      </div>

      <section className="mt-9">
        <h2 className="mb-2 font-mono text-[10px] tracking-[0.09em] text-text-faint uppercase">
          What the agent is told
        </h2>
        <p className="max-w-[72ch] rounded-card border border-line bg-sunken p-4 text-[14px] leading-relaxed text-text-muted text-pretty">
          {scenario.goal}
        </p>
      </section>

      <section className="mt-9">
        <h2 className="mb-2.5 font-mono text-[10px] tracking-[0.09em] text-text-faint uppercase">
          The tools it may use
        </h2>
        <ul className="flex flex-wrap gap-2">
          {scenario.tools.map((tool) => (
            <li
              key={tool}
              className="rounded-[3px] border border-line bg-sunken px-2 py-1 font-mono text-[11px] text-text-muted"
            >
              {tool}
            </li>
          ))}
        </ul>
        {services.length > 0 && (
          <p className="mt-3 font-mono text-[11px] text-text-faint">
            against a synthetic {services.join(", ")}
          </p>
        )}
      </section>

      <section className="mt-9">
        <h2 className="mb-2.5 font-mono text-[10px] tracking-[0.09em] text-text-faint uppercase">
          What it checks
        </h2>
        <ul className="max-w-[72ch] divide-y divide-line overflow-hidden rounded-card border border-line bg-surface">
          {scenario.assertions.map((assertion) => (
            <li key={assertion.id} className="px-4 py-3">
              <p className="text-[13.5px] leading-relaxed text-text-muted text-pretty">
                {assertionCopy(scenario.id, assertion).sentence}
              </p>
              <p className="mt-1 font-mono text-[10.5px] text-text-faint">{assertion.id}</p>
            </li>
          ))}
        </ul>
      </section>

      <section className="mt-9 border-t border-line pt-7">
        <h2 className="mb-2.5 text-[15px] font-medium">
          {replayable.length} scenarios do have runs you can replay
        </h2>
        <ul className="flex flex-wrap gap-x-5 gap-y-2">
          {replayable.map((other) => (
            <li key={other.id}>
              <a
                href={`/playground/${other.id}`}
                className="text-[13.5px] leading-relaxed text-text-muted underline underline-offset-2 hover:text-text"
              >
                {scenarioBrief(other).question}
              </a>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
