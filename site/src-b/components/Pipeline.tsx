import { blockedAttempts, evidenceFor, eventsFor, scenarioFor } from "@/data/fixtures";

/**
 * The showpiece: one run, end to end, as six stages down a rail.
 *
 * This is the source design's assurance-pipeline card, re-staged. Its six were
 * Agent result → Evidence → Claims → Requirements → Human approval → External
 * outcome, and three of those describe machinery this repository does not
 * have. Beacon's own six are just as real and rather more concrete: what was
 * declared, who ran, what it did, what it was refused, what was checked, what
 * came back. Every value below is read out of a recorded bundle.
 *
 * Three things the original did that are deliberately not done here.
 *
 * The rail is three solid segments rather than a cyan→amber→green gradient.
 * Gradient is a reserved vocabulary in this project — it means a mixed verdict
 * — and segments say the same thing about sequence without borrowing it.
 *
 * The reveal is CSS keyframes with a per-stage delay, not a JavaScript
 * timeline. The original drove it with `setTimeout` and imperative DOM writes,
 * looped every eight seconds, and — worst — its Replay button cleared the
 * reduced-motion flag permanently, so a visitor who had asked for no motion
 * got animation for the rest of the session. Here there is no timer, no loop,
 * and the block in `tokens-b.css` stops all of it for anyone who asked.
 *
 * Only opacity animates. A transform would move the element's rect mid-flight,
 * and `npm run visual` screenshots at an arbitrary moment — an animation that
 * changes geometry turns a layout audit into a coin toss. Fading leaves every
 * box exactly where it will end up, so the static render, the reduced-motion
 * render and the finished animation are the same picture.
 */

const RUN = "misbehaving";

/**
 * A stage marker: a hollow ring on the rail, not a filled dot.
 *
 * The design draws these as rings the rail passes through, which reads as a
 * station on a line rather than a bullet beside a list. Filled dots looked
 * like list markers and made the rail decorative.
 */
function Dot({ tone }: { tone: "src" | "bad" | "ok" | "review" }) {
  const colour =
    tone === "bad" ? "var(--b-bad)" : tone === "ok" ? "var(--b-ok)" : tone === "review" ? "var(--b-review)" : "var(--b-src)";
  return (
    <span
      aria-hidden="true"
      className="relative z-10 mt-1 h-2.5 w-2.5 flex-none rounded-full border-2"
      style={{ borderColor: colour, background: "var(--b-raised)" }}
    />
  );
}

/** A bordered content tile, which is how the design carries every stage body. */
function Tile({
  children,
  tone,
}: {
  children: React.ReactNode;
  tone?: "ok" | "bad" | "review";
}) {
  const edge =
    tone === "bad"
      ? "var(--b-bad)"
      : tone === "ok"
        ? "var(--b-ok)"
        : tone === "review"
          ? "var(--b-review)"
          : "var(--b-line)";
  return (
    <div
      className="rounded-md border px-3 py-2"
      style={{ borderColor: edge, opacity: tone ? 1 : 0.95 }}
    >
      {children}
    </div>
  );
}

function Chip({ label, tone }: { label: string; tone: "ok" | "bad" }) {
  return (
    <span
      className="rounded-[4px] border px-1.5 py-0.5 font-b-mono text-[10.5px] whitespace-nowrap"
      style={{
        borderColor: tone === "ok" ? "var(--b-ok)" : "var(--b-bad)",
        color: tone === "ok" ? "var(--b-ok)" : "var(--b-bad)",
      }}
    >
      {label}
    </span>
  );
}

export function Pipeline() {
  const evidence = evidenceFor(RUN);
  const events = eventsFor(RUN);
  const scenario = scenarioFor(evidence);

  const limits = events.find((e) => e.kind === "limits_overridden")?.payload as
    | { timeout_seconds?: { declared: number; applied: number } }
    | undefined;
  const drafts = events
    .filter((e) => e.kind === "tool_result" && e.target === "mail_create_draft")
    .map((e) => String((e.payload.result as { id?: string })?.id ?? ""));
  const refused = blockedAttempts(events);
  const passed = evidence.assertions.filter((a) => a.passed).length;
  const failing = evidence.assertions.find((a) => a.passed === false);

  const stages: { title: string; tone: "src" | "bad" | "ok" | "review"; body: React.ReactNode }[] = [
    {
      title: "Declared",
      tone: "src",
      body: (
        <Tile>
          <p className="font-b-mono text-[12.5px] text-b-text">{scenario.slug}</p>
          <p className="mt-0.5 font-b-mono text-[11px] text-b-faint">
            {scenario.assertions.length} checks · {scenario.tools.length} tools
          </p>
        </Tile>
      ),
    },
    {
      title: "Subject",
      tone: "src",
      body: (
        <Tile>
          <p className="font-b-mono text-[12.5px] text-b-text">{evidence.subject.adapter}</p>
          <p className="mt-0.5 font-b-mono text-[11px] text-b-faint">
            level {evidence.subject.integration_level}
            {limits?.timeout_seconds &&
              ` · timeout ${limits.timeout_seconds.declared}s → ${limits.timeout_seconds.applied}s`}
          </p>
        </Tile>
      ),
    },
    {
      title: "Did the work",
      tone: "ok",
      body: (
        <div className="grid grid-cols-3 gap-2">
          {drafts.map((id) => (
            <Tile key={id}>
              <p className="font-b-mono text-[11.5px] text-b-text">{id}</p>
              <p className="mt-0.5 font-b-mono text-[10.5px] text-b-ok">created</p>
            </Tile>
          ))}
        </div>
      ),
    },
    {
      title: "Was refused",
      tone: "bad",
      body: (
        <div className="flex flex-col gap-1.5">
          {[...refused.entries()].map(([tool, count]) =>
            Array.from({ length: count }, (_, i) => (
              <Tile key={`${tool}-${i}`} tone="bad">
                <div className="flex items-baseline justify-between gap-3">
                  <span className="font-b-mono text-[11.5px] text-b-text">{tool}</span>
                  <span className="font-b-mono text-[10.5px] text-b-bad">BLOCKED</span>
                </div>
              </Tile>
            )),
          )}
        </div>
      ),
    },
    {
      title: "Checked",
      tone: passed === evidence.assertions.length ? "ok" : "review",
      body: (
        <div className="flex flex-wrap gap-2">
          <Chip label={`${passed} of ${evidence.assertions.length} MET`} tone="ok" />
          {failing && <Chip label={`${failing.id} FAILED`} tone="bad" />}
        </div>
      ),
    },
    {
      title: "Verdict",
      tone: evidence.result === "PASS" ? "ok" : evidence.result === "FAIL" ? "bad" : "review",
      body: (
        <Tile tone={evidence.result === "PASS" ? "ok" : "bad"}>
          <p className="font-b-mono text-[12.5px]" style={{ color: "var(--b-bad)" }}>
            {evidence.result}
          </p>
          <p className="mt-0.5 font-b-mono text-[11px] text-b-faint">
            sha256:{evidence.digest.slice(0, 16)}…
          </p>
        </Tile>
      ),
    },
  ];

  return (
    <div className="overflow-hidden rounded-xl border border-b-line bg-b-raised">
      <div className="flex items-center justify-between gap-3 border-b border-b-line px-5 py-3.5">
        <span className="b-eyebrow text-b-faint">Recorded run · synthetic</span>
        <span
          className="b-eyebrow rounded-[4px] border px-2 py-1"
          style={{ borderColor: "var(--b-bad)", color: "var(--b-bad)" }}
        >
          {evidence.result} {passed}/{evidence.assertions.length}
        </span>
      </div>

      <ol className="relative px-5 py-6">
        {/*
          The rail: three segments, not a gradient. It sits behind the dots and
          stops short of the last one so the sequence reads as ending rather
          than continuing off the card.
        */}
        {/*
          Three stacked segments, each its own element.

          The first attempt set three colour layers on one background with
          `/ 100% 34%` sizes — which does nothing, because background-size
          applies to images and a colour fills its box whatever you tell it.
          The rail simply was not drawn, and no check would ever have said so:
          it is the connective device of the whole card and its absence is
          invisible to every audit here.
        */}
        {(["--b-src", "--b-review", "--b-bad"] as const).map((token, i) => (
          <span
            key={token}
            aria-hidden="true"
            className="absolute left-[26px] w-px"
            style={{
              top: `calc(2rem + ${i} * ((100% - 4.5rem) / 3))`,
              height: "calc((100% - 4.5rem) / 3)",
              background: `var(${token})`,
              opacity: 0.45,
            }}
          />
        ))}

        {stages.map((stage, i) => (
          <li
            key={stage.title}
            className="b-stage relative flex gap-4 py-2.5"
            style={{ animationDelay: `${140 + i * 130}ms` }}
          >
            <Dot tone={stage.tone} />
            <div className="min-w-0 flex-1">
              <p className="b-eyebrow text-b-faint">{stage.title}</p>
              <div className="mt-2">{stage.body}</div>
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}
