/**
 * Scenario → subject → synthetic world → evidence.
 *
 * A vertical rail, where the taps are the content: they say where evidence is
 * collected, which is the part that distinguishes this from any other diagram
 * of a test runner.
 */

interface Step {
  name: string;
  detail: string;
  tap?: string;
}

interface Props {
  steps: Step[];
}

export function PipelineDiagram({ steps }: Props) {
  return (
    <ol className="relative flex flex-col gap-6 pl-11">
      <span
        aria-hidden="true"
        className="absolute top-2 bottom-2 left-[26px] w-px bg-line"
      />
      {steps.map((step, index) => (
        <li key={step.name} className="relative">
          {/* Numbered, not bulleted. "Four things, in order" is the claim the
              section makes; an unnumbered ring does not make it. */}
          <span
            aria-hidden="true"
            className="absolute -top-0.5 -left-[31px] inline-flex h-[26px] w-[26px] items-center justify-center rounded-full bg-text font-mono text-[11px] font-medium text-bg"
          >
            {String(index + 1).padStart(2, "0")}
          </span>
          <h3 className="mb-1 text-[15px] font-medium">{step.name}</h3>
          <p className="mb-2 max-w-[58ch] text-[13.5px] leading-relaxed text-text-muted text-pretty">
            {step.detail}
          </p>
          {step.tap && (
            <p className="inline-block rounded-row border border-line bg-sunken px-2.5 py-1.5 font-mono text-[11px] text-text-muted">
              recorded here — {step.tap}
            </p>
          )}
        </li>
      ))}
    </ol>
  );
}
