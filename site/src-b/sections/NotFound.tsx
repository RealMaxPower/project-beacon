/**
 * A `#/…` fragment that names no route.
 *
 * Rendered rather than redirected, because the alternative — quietly showing
 * the marketing page — tells a visitor they are somewhere they are not and
 * hides the typo that got them there. The first design's router makes the same
 * argument at length; this is the page that argument requires.
 *
 * Note what is *not* here: an in-page anchor never reaches this. `#case` has no
 * leading slash, so `router-b.ts` reads it as an anchor and resolves HOME, and
 * the browser scrolls. Only `#/something` can miss.
 */

export function NotFound() {
  return (
    <section className="b-band">
      <div className="b-measure">
        <p className="b-eyebrow mb-6 text-b-review">Not found</p>
        <h1 className="b-h2 max-w-[20ch]">That address does not name a page here.</h1>
        <p className="b-lede mt-5 max-w-[54ch]">
          This site has four: the page you were on, the playground, the documentation, and
          licensing and privacy. The address bar is showing none of them, which usually means a
          mistyped link rather than something that moved.
        </p>
        <div className="mt-9 flex flex-wrap gap-3">
          <a
            href="/"
            className="hit-target inline-flex items-center rounded-md bg-b-src px-5 text-[14.5px] font-medium text-b-on-accent"
          >
            Back to the start
          </a>
          <a
            href="/playground"
            className="hit-target inline-flex items-center rounded-md border border-b-line-strong px-5 text-[14.5px] font-medium text-b-text"
          >
            Open the playground
          </a>
          <a
            href="/docs"
            className="hit-target inline-flex items-center rounded-md border border-b-line-strong px-5 text-[14.5px] font-medium text-b-text"
          >
            Read the documentation
          </a>
        </div>
      </div>
    </section>
  );
}
