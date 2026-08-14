/**
 * Licensing and privacy, as a route rather than a band.
 *
 * The footer has always linked this. It worked while this design lived at `/b`
 * and the link pointed across to the page of the design it replaced; the moment
 * this one took the root, `/#/legal` started resolving against this router,
 * which had no such route, and the link rendered a 404. A legal page reachable
 * only through a broken link is worse than none, because the footer says
 * otherwise.
 *
 * Every sentence here about what the site collects is a claim about the
 * Content-Security-Policy in `vercel.json`, quoted by directive rather than
 * described loosely, so a reader can check it from the network tab. Nothing
 * held the quote to the config until `PrivacyPolicyTests` did — and the first
 * thing it caught was this page saying `connect-src 'none'` after analytics
 * had relaxed it to `'self'`.
 */

const REPO = "https://github.com/RealMaxPower/project-beacon";

export function LegalScreen() {
  return (
    <div className="b-measure py-16">
      <header className="mb-12">
        <p className="mb-3 font-b-mono text-[11px] uppercase tracking-[0.12em] text-b-faint">
          Licensing and privacy
        </p>
        <h1 className="mb-5 max-w-[24ch] font-b-display text-[clamp(1.9rem,5vw,2.6rem)] leading-[1.08] font-semibold tracking-[-0.03em] text-balance">
          What this is licensed under, and what it knows about you.
        </h1>
        <p className="b-lede max-w-[66ch] text-[16px]">
          The second half is short, and it is short because there is nothing to
          disclose rather than because it has been trimmed.
        </p>
      </header>

      <section className="mb-12">
        <h2 className="mb-4 font-b-display text-[19px] font-semibold tracking-[-0.02em]">
          Licence
        </h2>
        <p className="b-lede mb-3 max-w-[66ch] text-[15px]">
          Project Beacon — the harness, the scenarios, this website and its
          source — is licensed under the Apache License 2.0, copyright Marshall
          Cahill and Project Beacon contributors. The full text ships in the{" "}
          <a className="underline underline-offset-2 hover:text-b-text" href={`${REPO}/blob/main/LICENSE`}>
            LICENSE
          </a>{" "}
          file.
        </p>
        <p className="b-lede max-w-[66ch] text-[15px]">
          Every scenario fixture is synthetic. No message, document, address or
          name in the recorded evidence on this site belongs to a real person.
        </p>
      </section>

      <section className="mb-12">
        <h2 className="mb-4 font-b-display text-[19px] font-semibold tracking-[-0.02em]">
          What this site borrows
        </h2>
        <p className="b-lede mb-4 max-w-[66ch] text-[15px]">
          These pages are built with React, which is MIT licensed, and its notice
          travels with the compiled code as that licence requires. The typefaces
          are redistributed under the SIL Open Font Licence 1.1, which has its own
          attachment requirement, so its text ships beside the font files.
        </p>
        <ul className="b-lede max-w-[66ch] space-y-2 text-[15px]">
          <li>
            <a
              className="font-b-mono text-b-src underline underline-offset-2 hover:text-b-text"
              href="/THIRD-PARTY-NOTICES.txt"
            >
              /THIRD-PARTY-NOTICES.txt
            </a>{" "}
            — the packages compiled into these pages, with their licences.
          </li>
          <li>
            <a
              className="font-b-mono text-b-src underline underline-offset-2 hover:text-b-text"
              href="/fonts/OFL.txt"
            >
              /fonts/OFL.txt
            </a>{" "}
            — the typefaces, their copyright holders, and the licence.
          </li>
        </ul>
      </section>

      <section className="mb-12">
        <h2 className="mb-4 font-b-display text-[19px] font-semibold tracking-[-0.02em]">
          Privacy
        </h2>
        <p className="b-lede mb-3 max-w-[66ch] text-[15px]">
          This site sets no cookies and has no forms. It makes no requests to any
          other host — its Content-Security-Policy declares{" "}
          <code className="font-b-mono whitespace-nowrap text-b-src">default-src &apos;none&apos;</code> and{" "}
          <code className="font-b-mono whitespace-nowrap text-b-src">connect-src &apos;self&apos;</code>, so
          nothing loads from a third party and the page cannot send anything off
          this origin. The typefaces are served from here rather than a font CDN
          precisely so that rendering a heading does not hand your address to
          someone else.
        </p>
        <p className="b-lede mb-3 max-w-[66ch] text-[15px]">
          It counts page views, using Vercel Web Analytics. That count is what{" "}
          <code className="font-b-mono whitespace-nowrap text-b-src">connect-src &apos;self&apos;</code>{" "}
          permits and it is the only thing this page sends: a request to{" "}
          <code className="font-b-mono whitespace-nowrap text-b-src">/_vercel/insights/view</code>{" "}
          on this origin, carrying the path you are on. There is no cookie, no
          identifier, and nothing that follows you to another site. It exists so
          that &ldquo;is anyone reading the docs&rdquo; has an answer other than
          a guess.
        </p>
        <p className="b-lede mb-3 max-w-[66ch] text-[15px]">
          The case explorer and the playground run entirely in your browser. They
          replay evidence recorded ahead of time and shipped with the page;
          nothing you do there — no scenario you pick, no run you open — is
          transmitted.
        </p>
        <p className="b-lede max-w-[66ch] text-[15px]">
          What remains is what any web server sees. This site is hosted on Vercel,
          whose infrastructure logs the usual request data — including your IP
          address — to serve the page and protect the service. That processing is
          Vercel&apos;s, under{" "}
          <a
            className="underline underline-offset-2 hover:text-b-text"
            href="https://vercel.com/legal/privacy-policy"
          >
            their privacy policy
          </a>
          . Nobody here reads those logs for any purpose, and no profile, account
          or record of your visit is kept.
        </p>
      </section>

      <section className="mb-12">
        <h2 className="mb-4 font-b-display text-[19px] font-semibold tracking-[-0.02em]">
          What this is not
        </h2>
        <p className="b-lede max-w-[66ch] text-[15px]">
          Nothing here is a safety certification, an audit, or advice. A passing
          report is evidence about one synthetic scenario and one configuration,
          and says nothing about behaviour outside it. The{" "}
          <a
            className="underline underline-offset-2 hover:text-b-text"
            href={`${REPO}/blob/main/docs/production-readiness.md`}
          >
            production readiness ledger
          </a>{" "}
          is candid about the limits, including the unflattering ones.
        </p>
      </section>

      <section>
        <h2 className="mb-4 font-b-display text-[19px] font-semibold tracking-[-0.02em]">
          Contact
        </h2>
        <p className="b-lede max-w-[66ch] text-[15px]">
          Conduct concerns go to conduct@beaconlab.dev. Security reports should
          not go in a public issue — the repository&apos;s{" "}
          <a
            className="underline underline-offset-2 hover:text-b-text"
            href={`${REPO}/blob/main/SECURITY.md`}
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
