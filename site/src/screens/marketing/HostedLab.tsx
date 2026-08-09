import { NextSteps } from "@/components/shell/NextSteps";
import type { Go } from "@/router";

/**
 * The commercial section, without a waitlist.
 *
 * A signup form would imply a pipeline that does not exist, and collecting
 * addresses creates an obligation with nothing behind it. What this stage of
 * the project actually needs is a conversation — the proposal calls for pricing
 * interviews and explicitly no premature paywall — and a form gets you an
 * address where a question gets you the interview.
 *
 * There is no component here for social proof, and none anywhere in this
 * system. Nothing to fill in later means no pressure to invent it.
 */

interface Props {
  onGo: Go;
}

export function HostedLab({ onGo }: Props) {
  return (
    <>
    <div className="mx-auto max-w-[1180px] px-5 py-14 sm:px-11">
      <header className="mb-10">
        <h1 className="mb-4 max-w-[26ch] text-[clamp(1.8rem,5vw,2.5rem)] leading-[1.1] font-medium tracking-[-0.035em] text-balance">
          There is no hosted lab yet. This is the page where I ask whether there should be.
        </h1>
        <p className="max-w-[66ch] text-[16px] leading-relaxed text-text-muted text-pretty">
          Beacon is open source and runs entirely on your machine. It will stay that way — the
          open core is meant to be useful without an account, not a trial of something else.
        </p>
      </header>

      <section className="mb-10 grid gap-4 lg:grid-cols-2">
        <article className="rounded-card border border-line bg-surface p-6">
          <h2 className="mb-3 text-[17px] font-medium">What I would build next</h2>
          <ul className="flex flex-col gap-2.5">
            {[
              "Private scenario packs modelled on work your agents actually do, rather than a synthetic inbox.",
              "Runs on infrastructure that is a real sandbox, not process isolation.",
              "Scheduled regression checks against a baseline, with the report going somewhere a team reads.",
              "Scenario development as a service, for organisations who know the failure they fear but not how to assert it.",
            ].map((item) => (
              <li key={item} className="flex gap-2.5 text-[14px] leading-relaxed text-text-muted">
                <span aria-hidden="true" className="mt-2.5 h-px w-2.5 flex-none bg-line-strong" />
                <span className="text-pretty">{item}</span>
              </li>
            ))}
          </ul>
        </article>

        <article className="rounded-card border border-line bg-surface p-6">
          <h2 className="mb-3 text-[17px] font-medium">What I want to know first</h2>
          <p className="mb-4 text-[14px] leading-relaxed text-text-muted text-pretty">
            Whether any of that is worth paying for, and which part. I would rather have ten
            conversations about what you actually need than a list of email addresses waiting
            for something that may never be the right thing to build.
          </p>
          <p className="mb-5 text-[14px] leading-relaxed text-text-muted text-pretty">
            If you evaluate agents, or you are being asked to sign off on one, tell me what
            would have to be true for a report like this to be useful to you.
          </p>
          <a
            href="https://github.com/RealMaxPower/project-beacon/discussions"
            className="hit-target inline-flex items-center rounded-row bg-text px-4 py-2.5 text-[13.5px] font-medium text-bg"
          >
            Start a discussion
          </a>
        </article>
      </section>

      <section className="rounded-card border border-line border-l-[3px] border-l-accent bg-surface p-6">
        <h2 className="mb-3 text-[17px] font-medium">Why there is no form on this page</h2>
        <p className="max-w-[70ch] text-[14.5px] leading-relaxed text-text-muted text-pretty">
          A waitlist implies a queue, a queue implies a product, and there is no product to
          queue for. The rest of this site argues that you should not trust a claim nobody can
          check — it would be a strange place to start collecting signups for something that
          does not exist.
        </p>
      </section>
    </div>

    <NextSteps
      onGo={onGo}
      lead="None of that is built. What is built runs on your machine today, and is the thing worth judging the idea on."
    />
    </>
  );
}
