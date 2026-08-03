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
}

export function TerminalBlock({ lines, label }: Props) {
  return (
    <figure className="overflow-hidden rounded-card border border-[#262A31] bg-[#16191E]">
      {label && (
        <figcaption className="border-b border-[#262A31] px-[18px] py-2.5 font-mono text-[11.5px] text-[#828A99]">
          {label}
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
