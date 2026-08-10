import { VerdictBadge } from "@/components/verdict/VerdictBadge";
import type { Evidence, Fixture } from "@/data/types";

/**
 * What each agent did, beside the one thing a diff can see.
 *
 * The figure exists because the argument is a *contrast* and prose makes the
 * reader hold five things in their head to feel it. Every column here differs
 * between the runs — how many times each reached for a forbidden tool, whether
 * it ever said it had finished — and then the last column is the same value
 * five times. A reader's eye runs across difference and lands on repetition,
 * which is the whole claim: grade by comparing before and after, and these five
 * agents are one agent.
 *
 * It replaced a drawing of five arcs leaving one point and arriving at another.
 * That was a picture of the *topology* — true, and silent about the mechanism.
 * It also carried the verdict as a bare coloured dot, which is the one thing
 * this palette cannot do: `#b3261e` and `#8a5a00` separate by ΔE 0.7 under
 * deuteranopia, so FAIL and INCOMPLETE were the same dot for a red-green
 * colourblind reader — and those two verdicts are exactly what this product
 * exists to tell apart. `VerdictBadge` carries a shape as well as a hue and
 * always did; the drawing simply was not using it.
 *
 * A real table, not a grid of divs: five rows of related records with a header
 * each way is what a table is for, and it is what a screen reader can navigate.
 */

export interface MatrixRun {
  fixture: Fixture;
  evidence: Evidence;
  /** Refused attempts, by the tool they were aimed at. */
  refused: Map<string, number>;
  /** Whether the subject ever signalled that it had finished. */
  completed: boolean;
  /** The single recorded state change, summarised. */
  diff: string;
}

interface Props {
  runs: MatrixRun[];
  /** The state-diff column heading — the field every run changed. */
  changed: string;
  onOpen: (scenarioId: string) => void;
}

/** A cell that reports attempts on one tool. */
function Attempts({ count }: { count: number }) {
  if (count === 0) {
    return (
      <span className="text-text-faint" title="not attempted">
        —
      </span>
    );
  }
  return (
    <span className="whitespace-nowrap text-fail">
      <span className="font-medium">{count}×</span>{" "}
      <span className="text-text-muted">refused</span>
    </span>
  );
}

export function OutcomeMatrix({ runs, changed, onOpen }: Props) {
  const columns = [
    { key: "mail_send_draft", head: "Tried to send", note: "mail it was told not to send" },
    { key: "mail_read_message", head: "Tried to open", note: "the message withheld from it" },
  ];

  return (
    <figure className="m-0">
      {/*
        Declared and painted. `tools/visual.mjs` requires both — the attribute
        alone would let anyone silence the audit, and the fade alone could be a
        decoration that promises nothing. The table is wider than a phone, and
        the only cue a browser gives for free is a scrollbar iOS draws after
        you have already scrolled.
      */}
      <div
        data-scroll-cue
        className="overflow-x-auto [mask-image:linear-gradient(to_right,black_calc(100%-2rem),transparent)]"
      >
        <table className="w-full min-w-[680px] border-collapse text-left">
          <caption className="sr-only">
            Five recorded runs of one scenario. Each row is one agent: what it attempted, whether
            it signalled completion, the one field it changed, and the verdict. The changed field
            is identical in every row.
          </caption>
          <thead>
            <tr className="border-b border-line-strong">
              <th scope="col" className="py-2.5 pr-4 font-mono text-[10.5px] font-medium tracking-[0.1em] text-text-faint uppercase">
                Agent
              </th>
              {columns.map((column) => (
                <th
                  key={column.key}
                  scope="col"
                  className="py-2.5 pr-4 font-mono text-[10.5px] font-medium tracking-[0.1em] text-text-faint uppercase"
                >
                  {column.head}
                </th>
              ))}
              <th scope="col" className="py-2.5 pr-4 font-mono text-[10.5px] font-medium tracking-[0.1em] text-text-faint uppercase">
                Said it finished
              </th>
              {/*
                The boundary. Everything to its left is what the agent did;
                everything to its right is what a report would contain. The rule
                is the figure's only piece of chrome, and it is doing the
                argument's work.
              */}
              {/*
                --text-muted, not --text-faint, and the difference is measured:
                faint is 4.78 on --sunken in light mode, which is under AA. The
                other headers sit on --bg where faint is 5.04 and legal. A guard
                in tests/test_site_claims.py caught this pairing here.
              */}
              <th
                scope="col"
                className="border-l border-line-strong bg-sunken py-2.5 pr-4 pl-4 font-mono text-[10.5px] font-medium tracking-[0.1em] text-text-muted uppercase"
              >
                {changed}
              </th>
              <th scope="col" className="py-2.5 font-mono text-[10.5px] font-medium tracking-[0.1em] text-text-faint uppercase">
                Verdict
              </th>
            </tr>
          </thead>
          <tbody>
            {runs.map((run) => (
              <tr key={run.fixture.key} className="border-b border-line last:border-b-0">
                {/*
                  The 44px target is taken by the button filling the cell rather
                  than by padding around it, so the row does not grow to 68px to
                  satisfy a rule about fingertips.
                */}
                <th scope="row" className="pr-4 text-[13.5px] font-normal">
                  <button
                    type="button"
                    onClick={() => onOpen(run.evidence.scenario.id)}
                    className="hit-target flex w-full items-center py-2 text-left hover:text-accent hover:underline"
                  >
                    {run.fixture.label}
                  </button>
                </th>
                {columns.map((column) => (
                  <td key={column.key} className="py-3 pr-4 text-[13px]">
                    <Attempts count={run.refused.get(column.key) ?? 0} />
                  </td>
                ))}
                <td className="py-3 pr-4 text-[13px]">
                  {run.completed ? (
                    <span className="text-text-muted">yes</span>
                  ) : (
                    <span className="whitespace-nowrap text-inc">
                      <span className="font-medium">no</span>{" "}
                      <span className="text-text-muted">— host went away</span>
                    </span>
                  )}
                </td>
                {/*
                  The identical column. Repeated five times on purpose: the
                  repetition is the finding, so it is not collapsed into a
                  rowspan or a footnote.
                */}
                <td className="border-l border-line-strong bg-sunken py-3 pr-4 pl-4 font-mono text-[13px] text-text">
                  {run.diff}
                </td>
                <td className="py-3">
                  <VerdictBadge state={run.evidence.result} size="sm" />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <figcaption className="mt-4 max-w-[74ch] text-[13.5px] leading-relaxed text-text-muted text-pretty">
        Everything left of the rule is what the agent did. Everything right of it is what a report
        that compares before and after would contain — the same value, five times. Every refused
        attempt was recorded before dispatch, which is why being stopped by policy still counts as
        having tried.
      </figcaption>
    </figure>
  );
}
