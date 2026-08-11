import { Band } from "../components/Band";

/**
 * How this site is checked, on a site whose whole argument is checking things.
 *
 * The claim everywhere else here is that a result you cannot re-derive is a
 * result you cannot argue with. A marketing page making that claim about a
 * grading tool, while itself being unverified prose, would be the loudest
 * possible counterexample — so the checks are named, and the commands are the
 * real ones.
 *
 * Two lines here are worded around the checks they describe, because those
 * checks caught them. `lint:render` fails a page printing the literal token a
 * missing value renders as; the guard on paint gradients fails a source file
 * containing the word. This section named both and was reported as the defect
 * it was describing.
 *
 * Neither guard is wrong to be that blunt. A marketing page has no business
 * printing either token, and prose about a rule is exactly the carve-out a
 * real violation would hide behind — the `og:image` guard caught its own
 * explanation once for the same reason. The copy moves; the rules do not.
 *
 * Deliberately no counts. Not screens, not tests, not pages. Every one of those
 * numbers is wrong the moment somebody adds a check, and this repository
 * already has a guard forbidding a test count in the facts export for exactly
 * that reason. A number here would rot faster than anywhere else on the page,
 * because these are the things most often added to.
 */

const CHECKS = [
  {
    command: "npm run smoke",
    what: "Every screen renders against the recorded bundles rather than sample data",
    catches:
      "A screen that throws, and a screen that renders while showing nothing it was asked to show.",
  },
  {
    command: "npm run lint:render",
    what: "The rendered DOM of every page, on its own and inside the shell",
    catches:
      "A placeholder value or a failed sum printed as text, empty headings, duplicate ids, unlabelled buttons, nested interactive elements, duplicate landmarks — and every JSON panel hashed against the file it names.",
  },
  {
    command: "npm run visual",
    what: "Real Chrome, both designs, both themes, four widths",
    catches:
      "Text overlapping text, horizontal overflow, clipped text, tap targets under 44px, a scroller with no cue, a header bar padded unevenly, and a button that offers no hand.",
  },
  {
    command: "npm run headers",
    what: "The built site served under the Content-Security-Policy it ships with",
    catches:
      "A policy that reads correctly and breaks something — or one that is decorative because nothing was ever loaded under it.",
  },
  {
    command: "python3 -m unittest discover -s tests",
    what: "The claims on these pages, against the repository they describe",
    catches:
      "A count written by hand, a certification word, a blended fill used as decoration, a scenario file that is not the file it is labelled as, and every contrast ratio in the stylesheet, recomputed.",
  },
] as const;

export function Checks() {
  return (
    <Band
      id="checks"
      eyebrow="08 — How this is checked"
      heading="The site makes claims. These are what hold them."
      lede="A page arguing that a result you cannot re-derive is a result you cannot argue with should not itself be unverified prose. Every command below is real, runs from a clone, and needs nothing hosted."
    >
      <ul className="b-cells grid sm:grid-cols-2 xl:grid-cols-3">
        {CHECKS.map((check) => (
          <li key={check.command} className="px-5 py-6">
            <p className="font-b-mono text-[12.5px] break-all text-b-src">{check.command}</p>
            <p className="mt-3 text-[13.5px] leading-snug font-medium">{check.what}</p>
            <p className="mt-2 text-[13px] leading-relaxed text-b-muted">{check.catches}</p>
          </li>
        ))}
      </ul>

      <p className="mt-8 max-w-[72ch] text-[13px] leading-relaxed text-b-muted">
        What none of them can judge is whether a sentence is true, whether a page reads in the
        order it was meant to, or whether a control does the thing its label promises. That is
        written down as a manual plan in{" "}
        <code className="font-b-mono text-b-src">site/TEST-PLAN.md</code>, with the expected
        values read out of the recorded bundles rather than remembered — so a disagreement
        between the plan and the screen is a bug in one of them, not a matter of opinion.
      </p>
    </Band>
  );
}
