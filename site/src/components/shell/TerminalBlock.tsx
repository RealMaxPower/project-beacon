import { useState } from "react";

/**
 * A command, or what one printed.
 *
 * Dark in both themes. A terminal that turns white in light mode stops reading
 * as a terminal, and every block on this site is something you would paste into
 * one.
 *
 * Must be a `pre`: these lines carry backslash continuations and aligned
 * columns, and both break the moment whitespace collapses. Comment lines are
 * dimmed rather than coloured, so the commands stay the thing you see first.
 */

interface Props {
  lines: string[];
  label?: string;
  /**
   * Offer to copy the block.
   *
   * Off by default, because most blocks here are transcripts — output a reader
   * is meant to compare against, not paste. On for the ones that are an
   * instruction, which is the whole point of "there is nothing to install".
   */
  copyable?: boolean;
}

export function TerminalBlock({ lines, label, copyable = false }: Props) {
  /*
   * Three states, not two. "Copy" that silently does nothing when the browser
   * refuses the clipboard — an insecure origin, a permission denied — teaches
   * a reader that the button is broken rather than that the paste did not
   * happen, and they find out at the terminal.
   */
  const [state, setState] = useState<"idle" | "copied" | "failed">("idle");

  /*
   * Comment lines go too. They say what each command is for, and a reader
   * pasting the block into a shell is exactly the person who wants them —
   * they are inert there.
   */
  async function copy() {
    try {
      await navigator.clipboard.writeText(lines.join("\n"));
      setState("copied");
    } catch {
      setState("failed");
    }
    setTimeout(() => setState("idle"), 2000);
  }

  return (
    <figure className="overflow-hidden rounded-card border border-[#262A31] bg-[#16191E]">
      {(label || copyable) && (
        <figcaption className="flex items-center gap-3 border-b border-[#262A31] pr-2 pl-[18px] font-mono text-[11.5px] text-[#828A99]">
          {/* A caption element is still needed when there is no label, or the
              copy button has nothing to sit in. */}
          <span className="py-2.5">{label ?? "bash"}</span>
          {copyable && (
            <button
              type="button"
              onClick={copy}
              // `hit-target`, like every other control here. Sized to the text
              // it holds, this came out 31px — the design system's floor is 44,
              // and `tools/visual.mjs` measures it.
              className="hit-target ml-auto inline-flex items-center rounded-row border border-[#383D46] px-3 font-mono text-[11px] text-[#E9EBEF] transition-colors hover:border-[#5C626E]"
            >
              {state === "copied" ? "Copied" : state === "failed" ? "Press ⌘C" : "Copy"}
            </button>
          )}
        </figcaption>
      )}
      <pre className="overflow-x-auto px-[18px] py-5 font-mono text-[13.5px] leading-[2] text-[#E9EBEF]">
        {lines.map((line, index) => (
          <span
            key={index}
            className={line.trimStart().startsWith("#") ? "text-[#828A99]" : undefined}
          >
            {line}
            {index < lines.length - 1 ? "\n" : ""}
          </span>
        ))}
      </pre>
    </figure>
  );
}
