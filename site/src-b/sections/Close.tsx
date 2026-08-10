/**
 * The last thing on the page.
 *
 * Centred, unlike everything above it, which is the source design's one
 * departure from left alignment and is worth keeping: it reads as an ending
 * rather than another section.
 */

const REPO = "https://github.com/RealMaxPower/project-beacon";

export function Close() {
  return (
    <section className="border-t border-b-line py-[clamp(72px,8vw,132px)]">
      <div className="mx-auto max-w-[900px] px-[var(--b-gutter)] text-center">
        <h2 className="b-h2 mx-auto max-w-[20ch]">
          Give agent work a record somebody else can check.
        </h2>
        <p className="b-lede mx-auto mt-6 max-w-[52ch]">
          Run one scenario, read the bundle it writes, and recompute the digest yourself. If you
          disagree with a verdict, the evidence for it is in the file.
        </p>
        <div className="mt-9 flex flex-wrap justify-center gap-3">
          <a
            href="#case"
            className="hit-target inline-flex items-center rounded-md bg-b-src px-5 text-[14.5px] font-medium text-b-on-accent"
          >
            Open the case →
          </a>
          <a
            href={REPO}
            rel="noreferrer"
            className="hit-target inline-flex items-center rounded-md border border-b-line-strong px-5 text-[14.5px] font-medium"
          >
            Read the source
          </a>
        </div>
      </div>
    </section>
  );
}
