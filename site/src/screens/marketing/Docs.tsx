import { NextSteps } from "@/components/shell/NextSteps";
import { facts } from "@/data/fixtures";
import type { Go } from "@/router";
import { docDescriptions, ELSEWHERE } from "./docs-index";

/**
 * Every document, linked to the file it is.
 *
 * The list is generated from `docs/` and `conformance/`, so a card cannot point
 * at a page that was renamed or deleted. The descriptions are authored; the
 * filenames are not.
 */

const REPO = "https://github.com/RealMaxPower/project-beacon/blob/main";

function Card({ path, name }: { path: string; name: string }) {
  return (
    <a
      href={`${REPO}/${path}/${name}`}
      className="flex h-full flex-col rounded-card border border-line bg-surface p-5 transition-colors hover:border-line-strong"
    >
      <p className="mb-2 font-mono text-[12.5px] font-medium text-text">
        {path}/{name}
      </p>
      <p className="text-[13.5px] leading-relaxed text-text-muted text-pretty">
        {docDescriptions[name] ?? "See the repository."}
      </p>
    </a>
  );
}

interface Props {
  onGo: Go;
}

export function Docs({ onGo }: Props) {
  return (
    <>
    <div className="mx-auto max-w-[1180px] px-5 py-14 sm:px-11">
      <header className="mb-12">
        <h1 className="mb-4 max-w-[24ch] text-[clamp(1.8rem,5vw,2.5rem)] leading-[1.1] font-medium tracking-[-0.035em] text-balance">
          Documentation, and the surveys behind the claims.
        </h1>
        <p className="max-w-[64ch] text-[16px] leading-relaxed text-text-muted text-pretty">
          Everything lives in the repository. The surveys are the working records the README
          cites — where a number in the documentation came from, and what it cost to find out
          it was wrong.
        </p>
      </header>

      <section className="mb-12">
        <h2 className="mb-5 font-mono text-[10.5px] uppercase tracking-[0.1em] text-text-faint">
          Docs
        </h2>
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {facts.docs.map((name) => (
            <Card key={name} path="docs" name={name} />
          ))}
        </div>
      </section>

      <section className="mb-12">
        <h2 className="mb-5 font-mono text-[10.5px] uppercase tracking-[0.1em] text-text-faint">
          Conformance surveys
        </h2>
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {facts.surveys.map((name) => (
            <Card key={name} path="conformance" name={name} />
          ))}
        </div>
      </section>

      <section>
        <h2 className="mb-5 font-mono text-[10.5px] uppercase tracking-[0.1em] text-text-faint">
          Elsewhere in the repository
        </h2>
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {ELSEWHERE.map((item) => (
            <a
              key={item.path}
              href={item.href}
              className="flex h-full flex-col rounded-card border border-line bg-surface p-5 transition-colors hover:border-line-strong"
            >
              <p className="mb-2 font-mono text-[12.5px] font-medium text-text">{item.path}</p>
              <p className="text-[13.5px] leading-relaxed text-text-muted text-pretty">
                {item.body}
              </p>
            </a>
          ))}
        </div>
      </section>
    </div>

    {/*
     * No repository card here: every card on this page is already a link into
     * the repository, and a fourth way to say "go to GitHub" at the bottom of
     * a page made of GitHub links is noise.
     */}
    <NextSteps
      hideRepo
      onGo={onGo}
      lead="Every card above is a file in the repository. If you would rather see the thing working than read about it, the playground replays a run end to end."
    />
    </>
  );
}
