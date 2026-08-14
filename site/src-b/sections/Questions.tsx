import { Band } from "../components/Band";
import { FAQ } from "../pages";

/**
 * The questions, on the page.
 *
 * This section and the `FAQPage` structured data in every document read the
 * same array in `pages.ts`, and that is the point rather than a convenience.
 * Marked-up questions that do not appear on the page are a claim about a page
 * that does not make it — Google names the mismatch as grounds for ignoring
 * the markup entirely, and it is the same rule this project applies to
 * everything else: the evidence has to be the thing described.
 *
 * `<details>` rather than a script-driven accordion. It is open-able without
 * JavaScript, which matters here more than anywhere: the readers this section
 * is written for are the ones who do not run any. The first is open because a
 * page of collapsed rows tells a visitor nothing about what is inside them.
 */
export function Questions() {
  return (
    <Band
      id="questions"
      ground="alt"
      eyebrow="12 — Questions"
      heading="The things people ask before they clone it."
      lede="Short answers, and each one is true on its own — including the ones where the answer is no."
    >
      <div className="b-cells overflow-hidden rounded-xl border border-b-line">
        {FAQ.map(({ q, a }, index) => (
          <details
            key={q}
            open={index === 0}
            className="group border-b border-b-line last:border-b-0"
          >
            <summary className="hit-target flex cursor-pointer list-none items-center justify-between gap-4 px-5 py-4 text-[15px] font-medium text-b-text marker:content-['']">
              {q}
              <span
                aria-hidden="true"
                className="flex-none font-b-mono text-[13px] text-b-faint group-open:hidden"
              >
                +
              </span>
              <span
                aria-hidden="true"
                className="hidden flex-none font-b-mono text-[13px] text-b-faint group-open:block"
              >
                −
              </span>
            </summary>
            <p className="b-lede max-w-[78ch] px-5 pb-5 text-[14.5px]">{a}</p>
          </details>
        ))}
      </div>
    </Band>
  );
}
