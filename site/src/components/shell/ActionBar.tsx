import type { ReactNode } from "react";

/**
 * The next thing to do, pinned where it can always be reached.
 *
 * The playground's advance control used to sit *after* the step's content, so
 * on the world and run screens you scrolled past an entire state diff or an
 * entire event log to find "Run it" — and on a phone that is two or three
 * screens of scrolling to reach a button whose whole job is to say "keep
 * going". A reader who does not scroll all the way down concludes the run has
 * finished, because nothing on screen suggests otherwise.
 *
 * Fixed rather than sticky: sticky positioning needs an ancestor taller than
 * the viewport, and the first two steps are frequently shorter than one.
 *
 * The bar carries exactly one action. It is a signpost, not a toolbar — the
 * step's own controls (pause, skip to end, expert mode) stay with the content
 * they operate on, where their meaning is.
 */

interface Props {
  /** Where the reader is, in words. Left of the action. */
  status: string;
  /** The action itself. A button, or a button and a link. */
  children: ReactNode;
}

export function ActionBar({ status, children }: Props) {
  return (
    <div className="fixed inset-x-0 bottom-0 z-40 border-t border-line bg-bg/95 backdrop-blur">
      <div className="mx-auto flex max-w-[1180px] items-center gap-4 px-5 py-3 sm:px-11">
        {/*
         * Gone on a phone rather than truncated. At 390px this clipped to
         * "inbox-briefing-draft-only · nothing h…", which is a scenario id
         * already printed above the fold and half a word of English. The step
         * rail says where you are; this only ever added detail.
         */}
        <p className="hidden min-w-0 flex-1 truncate font-mono text-[11.5px] text-text-faint sm:block">
          {status}
        </p>
        <div className="flex-1 sm:hidden" />
        <div className="flex flex-none items-center gap-2">{children}</div>
      </div>
    </div>
  );
}
