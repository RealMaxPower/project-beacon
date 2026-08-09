import type { ReactNode } from "react";

/**
 * A question, opening onto the argument that answers it.
 *
 * The pages here are essays, and every paragraph in them is load-bearing — but
 * a reader arriving cold cannot tell which three paragraphs are the claim and
 * which are the reasoning behind it. This puts the reasoning one click away
 * without removing a word of it.
 *
 * Native `details`, not the `useState` + `aria-expanded` pattern
 * `AssertionRow` uses, for three reasons. The prose stays in the document when
 * the panel is shut, so `tools/lint.tsx` still audits it and it is still there
 * with JavaScript off. It needs no state. And there is no `aria-controls` to
 * point at an element that is not rendered, which is the bug that pattern
 * exists to work around.
 *
 * The summary is always a real question. "Read more" tells a reader nothing
 * about whether the thing behind it is worth their click, which is the whole
 * job of the control.
 *
 * What may go in here is rationale — why a check is shaped the way it is, what
 * was tried first, what a number does not mean. A limitation may not. This
 * site's argument is that a bound belongs beside the claim it bounds, and a
 * bound behind a click is a bound most readers never see.
 */

interface Props {
  /** A question, in the reader's words. Never "Read more". */
  question: string;
  children: ReactNode;
  /** Open on load. For the one or two places the detail is the point. */
  defaultOpen?: boolean;
}

export function Disclosure({ question, children, defaultOpen = false }: Props) {
  return (
    <details
      open={defaultOpen}
      className="group rounded-card border border-line bg-surface [&[open]]:bg-sunken"
    >
      <summary
        className="hit-target flex cursor-pointer list-none items-center gap-3 px-4 py-3 text-[14px] leading-snug font-medium text-text-muted transition-colors hover:text-text [&::-webkit-details-marker]:hidden"
      >
        {/*
         * A rotating chevron rather than a +/−: this control opens prose, and
         * the page already spends its +/− vocabulary on assertion rows, where
         * the thing that opens is a comparison.
         */}
        <svg
          width="11"
          height="11"
          viewBox="0 0 16 16"
          fill="none"
          strokeWidth="2.4"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
          className="flex-none stroke-current transition-transform group-open:rotate-90"
        >
          <path d="M5.5 3 L11 8 L5.5 13" />
        </svg>
        <span className="text-pretty">{question}</span>
      </summary>

      {/*
       * `hidden` until open, explicitly.
       *
       * Current Chromium hides a shut `details` through `::details-content`
       * rather than `display: none`, and the children keep a layout box at
       * their last position — so `tools/visual.mjs` measured every collapsed
       * paragraph as text sitting on top of the section below it, on every
       * page that has one. Toggling display from the `open` attribute is pure
       * CSS, so it still works with JavaScript off.
       */}
      <div className="hidden border-t border-line px-4 py-4 group-open:block [&>p+p]:mt-3 [&>p]:max-w-[70ch] [&>p]:text-[14px] [&>p]:leading-relaxed [&>p]:text-text-muted [&>p]:text-pretty">
        {children}
      </div>
    </details>
  );
}
