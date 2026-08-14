/**
 * Licensing and privacy, on one page.
 *
 * Kept out of the main navigation and reached from the footer, which is where
 * a visitor looks for it. It is short because there is little to disclose, and
 * that is the interesting part: a site arguing that claims should be checkable
 * should be able to state what it collects and have a reader confirm it from
 * the network tab in about ten seconds.
 *
 * Every claim here is one the Content-Security-Policy already enforces. If the
 * policy in `vercel.json` is ever loosened, this page becomes false — which is
 * why it names the directive rather than describing the behaviour vaguely.
 */

interface Props {
  onGo: (path: "docs" | "") => void;
}

export function Legal({ onGo }: Props) {
  return (
    <div className="mx-auto max-w-[1180px] px-5 py-14 sm:px-11">
      <header className="mb-10">
        <h1 className="mb-4 max-w-[26ch] text-[clamp(1.8rem,5vw,2.5rem)] leading-[1.1] font-medium tracking-[-0.035em] text-balance">
          Licensing and privacy
        </h1>
        <p className="max-w-[66ch] text-[16px] leading-relaxed text-text-muted text-pretty">
          What this site is licensed under, what it borrows, and what it knows
          about you. The last section is the short one.
        </p>
      </header>

      <section className="mb-10">
        <h2 className="mb-3 text-[19px] font-medium tracking-[-0.02em]">Licence</h2>
        <p className="mb-3 max-w-[66ch] text-[15px] leading-relaxed text-text-muted text-pretty">
          Project Beacon — the harness, the scenarios, this website and its
          source — is licensed under the Apache License 2.0, copyright the
          Project Beacon contributors. The full text ships in the{" "}
          <a
            className="underline decoration-line-strong underline-offset-2 hover:text-text"
            href="https://github.com/RealMaxPower/project-beacon/blob/main/LICENSE"
          >
            LICENSE
          </a>{" "}
          file in the repository.
        </p>
        <p className="max-w-[66ch] text-[15px] leading-relaxed text-text-muted text-pretty">
          Every scenario fixture is synthetic. No message, document, address or
          name in this site's recorded evidence belongs to a real person.
        </p>
      </section>

      <section className="mb-10">
        <h2 className="mb-3 text-[19px] font-medium tracking-[-0.02em]">
          What this site borrows
        </h2>
        <p className="mb-3 max-w-[66ch] text-[15px] leading-relaxed text-text-muted text-pretty">
          The pages are built with React, which is MIT licensed, and its notice
          travels with the compiled code as that licence requires. The typefaces
          are redistributed under the SIL Open Font Licence 1.1, which has its
          own attachment requirement, so its text ships beside the font files.
        </p>
        <ul className="max-w-[66ch] space-y-2 text-[15px] leading-relaxed text-text-muted">
          <li>
            <a
              className="font-mono text-[13.5px] underline decoration-line-strong underline-offset-2 hover:text-text"
              href="/THIRD-PARTY-NOTICES.txt"
            >
              /THIRD-PARTY-NOTICES.txt
            </a>{" "}
            — the packages compiled into these pages, with their licences.
          </li>
          <li>
            <a
              className="font-mono text-[13.5px] underline decoration-line-strong underline-offset-2 hover:text-text"
              href="/fonts/OFL.txt"
            >
              /fonts/OFL.txt
            </a>{" "}
            — the typefaces, their copyright holders, and the licence.
          </li>
        </ul>
      </section>

      <section className="mb-10">
        <h2 className="mb-3 text-[19px] font-medium tracking-[-0.02em]">Privacy</h2>
        <p className="mb-3 max-w-[66ch] text-[15px] leading-relaxed text-text-muted text-pretty">
          This site sets no cookies and has no forms. It makes no requests to
          any other host — its Content-Security-Policy declares{" "}
          <code className="font-mono text-[13.5px]">default-src 'none'</code>{" "}
          and{" "}
          <code className="font-mono text-[13.5px]">connect-src 'self'</code>,
          so nothing loads from a third party and the page cannot send anything
          off this origin. The typefaces are served from here rather than a font
          CDN specifically so that rendering a heading does not hand your
          address to someone else.
        </p>
        <p className="mb-3 max-w-[66ch] text-[15px] leading-relaxed text-text-muted text-pretty">
          It counts page views, using Vercel Web Analytics. That count is what{" "}
          <code className="font-mono text-[13.5px]">connect-src 'self'</code>{" "}
          permits and it is the only thing this page sends: a request to{" "}
          <code className="font-mono text-[13.5px]">/_vercel/insights/view</code>{" "}
          on this origin, carrying the path you are on. There is no cookie, no
          identifier, and nothing that follows you to another site. It exists so
          that "is anyone reading the docs" has an answer other than a guess.
        </p>
        <p className="mb-3 max-w-[66ch] text-[15px] leading-relaxed text-text-muted text-pretty">
          The playground runs entirely in your browser. It replays evidence
          recorded ahead of time and shipped with the page; nothing you do
          there — no scenario you pick, no run you open — is transmitted.
        </p>
        <p className="max-w-[66ch] text-[15px] leading-relaxed text-text-muted text-pretty">
          What remains is what any web server sees. This site is hosted on
          Vercel, whose infrastructure logs the usual request data — including
          your IP address — to serve the page and to protect the service. That
          processing is Vercel's, under{" "}
          <a
            className="underline decoration-line-strong underline-offset-2 hover:text-text"
            href="https://vercel.com/legal/privacy-policy"
          >
            their privacy policy
          </a>
          . Nobody here reads those logs for any purpose, and no profile,
          account or record of your visit is kept.
        </p>
      </section>

      <section className="mb-10">
        <h2 className="mb-3 text-[19px] font-medium tracking-[-0.02em]">
          What this site is not
        </h2>
        <p className="max-w-[66ch] text-[15px] leading-relaxed text-text-muted text-pretty">
          Nothing here is a safety certification, an audit, or advice. A passing
          report is evidence about one synthetic scenario and one configuration,
          and says nothing about behaviour outside it. The{" "}
          <button
            type="button"
            onClick={() => onGo("docs")}
            className="underline decoration-line-strong underline-offset-2 hover:text-text"
          >
            documentation
          </button>{" "}
          is candid about the limits, including the ones that are unflattering.
        </p>
      </section>

      <section>
        <h2 className="mb-3 text-[19px] font-medium tracking-[-0.02em]">Contact</h2>
        <p className="max-w-[66ch] text-[15px] leading-relaxed text-text-muted text-pretty">
          Conduct concerns go to conduct@beaconlab.dev. Security reports should
          not go in a public issue — the repository's{" "}
          <a
            className="underline decoration-line-strong underline-offset-2 hover:text-text"
            href="https://github.com/RealMaxPower/project-beacon/blob/main/SECURITY.md"
          >
            SECURITY.md
          </a>{" "}
          describes the private channel. Everything else belongs in an issue,
          where the answer is useful to whoever asks next.
        </p>
      </section>
    </div>
  );
}
