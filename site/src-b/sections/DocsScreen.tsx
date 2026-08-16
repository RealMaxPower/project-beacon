import { facts } from "@/data/fixtures";
import { docDescriptions, ELSEWHERE } from "@/screens/marketing/docs-index";

/**
 * The documentation, as a route rather than a band.
 *
 * The other design has this as one of seven pages. Here the marketing page is a
 * single scroll, so a reader who wants the protocol contract has nowhere to go —
 * `Quickstart` gives them a command and `Contribute` gives them a repository,
 * and the documents between those two with no door.
 *
 * The list is `facts.docs`, which `build_fixtures.py` derives from `docs/` and
 * `conformance/`. Both designs read it, so a card here cannot point at a file
 * that is not there, and adding a document adds it to both pages without
 * either being edited. The descriptions are shared for the same reason: they
 * were prose in the first design's screen, which meant a second copy here would
 * have been a second place for a document to be described wrongly.
 *
 * The conformance surveys are not under `docs/`, so they carry their own
 * path — the same distinction the first design draws, and the reason a card
 * knows which directory it came from rather than assuming.
 */

const REPO = "https://github.com/RealMaxPower/project-beacon/blob/main";

function Card({ path, name }: { path: string; name: string }) {
  return (
    <li>
      <a
        href={`${REPO}/${path}/${name}`}
        rel="noreferrer"
        className="flex h-full flex-col rounded-xl border border-b-line px-5 py-5 hover:border-b-line-strong"
      >
        <p className="font-b-mono text-[12.5px] break-all text-b-src">
          {path}/{name}
        </p>
        <p className="mt-2.5 text-[13px] leading-relaxed text-b-muted">
          {docDescriptions[name] ?? "Part of the published documentation."}
        </p>
      </a>
    </li>
  );
}

export function DocsScreen() {
  return (
    <>
      <section className="b-band">
        <div className="b-measure">
          <p className="b-eyebrow mb-6 text-b-src">Documentation</p>
          <h1 className="b-display max-w-[18ch]">Everything written down, and where it lives.</h1>
          <p className="b-lede mt-7 max-w-[62ch]">
            All of it is in the repository, so it is versioned with the code that it describes and
            it is readable without running anything. These cards are generated from what is
            actually on disk — a link here cannot outlive its file.
          </p>

          <ul className="mt-10 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {facts.docs.map((name) => (
              <Card key={name} path="docs" name={name} />
            ))}
            {facts.surveys?.map((name) => (
              <Card key={name} path="conformance" name={name} />
            ))}
          </ul>
        </div>
      </section>

      <section className="b-band" data-ground="alt">
        <div className="b-measure">
          <p className="b-eyebrow mb-6 text-b-src">Not documentation</p>
          <h2 className="b-h2 max-w-[20ch]">The four places a reader actually goes next.</h2>
          <ul className="mt-10 grid gap-4 sm:grid-cols-2">
            {ELSEWHERE.map((item) => (
              <li key={item.path}>
                <a
                  href={item.href}
                  rel="noreferrer"
                  className="flex h-full flex-col rounded-xl border border-b-line px-5 py-5 hover:border-b-line-strong"
                >
                  <p className="font-b-mono text-[12.5px] text-b-src">{item.path}</p>
                  <p className="mt-2.5 text-[13px] leading-relaxed text-b-muted">{item.body}</p>
                </a>
              </li>
            ))}
          </ul>
        </div>
      </section>
    </>
  );
}
