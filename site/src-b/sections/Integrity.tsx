import { useEffect, useMemo, useState } from "react";
import { evidenceFor } from "@/data/fixtures";

/**
 * Change a protected field, watch the digest stop matching.
 *
 * This is the source design's approval-binding panel, rebuilt on something
 * this repository has. The design binds an approval to an action digest, and
 * Beacon has no actions and no approvals — but it does hash every bundle it
 * writes, and `project-beacon verify` recomputes that hash. So the interaction
 * survives intact and becomes a demonstration of a real property rather than
 * an illustration of an imagined one.
 *
 * The hash is real. The design labelled its digest `sha256:` while computing a
 * 32-bit FNV variant, sliced to twelve characters — a false statement about
 * the artefact on screen, sitting directly beneath copy about rigour. This
 * calls `crypto.subtle.digest("SHA-256", …)`, so the value here is the value
 * `shasum -a 256` gives for the same bytes, and a reader can check it.
 *
 * What it does not claim: that a digest proves authorship. It is unsigned, and
 * the caption says so — an edit is detectable, an author is not provable.
 */

const RUN = "misbehaving";

async function sha256(text: string): Promise<string> {
  const bytes = new TextEncoder().encode(text);
  const hash = await crypto.subtle.digest("SHA-256", bytes);
  return [...new Uint8Array(hash)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

export function Integrity() {
  const evidence = evidenceFor(RUN);

  /** The fields a reader can tamper with, and what each would become. */
  const fields = useMemo(
    () => [
      {
        key: "result",
        label: "Verdict",
        original: evidence.result,
        altered: "PASS",
      },
      {
        key: "subject",
        label: "Subject",
        original: evidence.subject.name,
        altered: "Demo agent — well behaved",
      },
      {
        key: "digest",
        label: "State after",
        original: evidence.state.after_digest.slice(0, 24),
        altered: "0000000000000000000000dd",
      },
      {
        key: "assertions",
        label: "Checks satisfied",
        original: `${evidence.assertions.filter((a) => a.passed).length} of ${evidence.assertions.length}`,
        altered: `${evidence.assertions.length} of ${evidence.assertions.length}`,
      },
    ],
    [evidence],
  );

  const [edited, setEdited] = useState<Record<string, boolean>>({});
  const [digest, setDigest] = useState<string | null>(null);
  const [baseline, setBaseline] = useState<string | null>(null);

  const payload = useMemo(
    () => fields.map((f) => `${f.key}=${edited[f.key] ? f.altered : f.original}`).join("\n"),
    [fields, edited],
  );
  const untouched = useMemo(
    () => fields.map((f) => `${f.key}=${f.original}`).join("\n"),
    [fields],
  );

  useEffect(() => {
    let live = true;
    sha256(untouched).then((h) => live && setBaseline(h));
    return () => {
      live = false;
    };
  }, [untouched]);

  useEffect(() => {
    let live = true;
    sha256(payload).then((h) => live && setDigest(h));
    return () => {
      live = false;
    };
  }, [payload]);

  const dirty = Object.values(edited).some(Boolean);
  const matches = digest !== null && digest === baseline;

  return (
    <section id="integrity" className="b-band">
      <div className="b-measure">
        <p className="b-eyebrow mb-6 text-b-review">03 — Integrity</p>
        <h2 className="b-h2 max-w-[22ch]">A report you can recompute is a report you can argue with.</h2>
        <p className="b-lede mt-5 max-w-[58ch]">
          Beacon writes a SHA-256 over the bundle it produces, and{" "}
          <code className="font-b-mono text-b-src">beacon verify</code> recomputes it. Change any
          field below and the digest stops matching — which is the whole of what a hash buys you,
          and no more than that.
        </p>

        <div className="mt-10 grid gap-5 lg:grid-cols-[1fr_1.15fr]">
          {/*
            Two cards, because the claim is a contrast and prose flattened it.
            The source design stages the same move — a dashed red card against a
            solid green one — for approval that is vague against approval that is
            bound. Beacon's version of that contrast is the true one about a
            hash: it tells you the bytes changed, and it tells you nothing at all
            about who changed them. The dashed edge is the second encoding the
            palette rule requires, so the pair still separates without colour.
          */}
          <div className="flex flex-col gap-4">
            <div
              className="rounded-xl border p-6"
              style={{
                borderColor: "var(--b-ok)",
                background: "color-mix(in oklab, var(--b-ok) 7%, transparent)",
              }}
            >
              <p className="b-eyebrow mb-3" style={{ color: "var(--b-ok)" }}>
                It detects
              </p>
              <p className="text-[15px] leading-snug text-b-text">
                “These are not the bytes that were written.”
              </p>
              <p className="mt-3 text-[13px] leading-relaxed text-b-muted">
                Recompute the hash, compare it to the one in the bundle, and a single altered
                field shows up. That works for a reader who was not there and trusts nobody.
              </p>
            </div>

            <div
              className="rounded-xl border border-dashed p-6"
              style={{
                borderColor: "var(--b-bad)",
                background: "color-mix(in oklab, var(--b-bad) 6%, transparent)",
              }}
            >
              <p className="b-eyebrow mb-3" style={{ color: "var(--b-bad)" }}>
                It does not prove
              </p>
              <p className="text-[15px] leading-snug text-b-text">
                “These are the bytes Beacon wrote.”
              </p>
              <p className="mt-3 text-[13px] leading-relaxed text-b-muted">
                The digest is <span className="text-b-review">unsigned</span>. Anyone who can
                change the bundle can recompute it, so this is a check against accident and drift
                — not against somebody who wants to deceive you.
              </p>
            </div>
          </div>

          <div className="overflow-hidden rounded-xl border border-b-line bg-b-raised">
            <div className="flex items-center justify-between gap-3 border-b border-b-line px-5 py-3.5">
              <span className="font-b-mono text-[12px] text-b-src">bundle://{evidence.run_id}</span>
              <span
                className="b-eyebrow rounded-[4px] border px-2 py-1"
                style={{ borderColor: "var(--b-review)", color: "var(--b-review)" }}
              >
                Unsigned
              </span>
            </div>

            {/*
              Label left, value right — the design's arrangement, and the reason
              it works is that the values are mono and the right edge lines them
              up into a column a reader can scan for the one that changed.
            */}
            <dl className="divide-y divide-b-line">
              {fields.map((field) => {
                const changed = Boolean(edited[field.key]);
                return (
                  <div
                    key={field.key}
                    className="flex items-baseline justify-between gap-4 px-5 py-3"
                  >
                    <dt className="flex-none text-[12.5px] text-b-faint">{field.label}</dt>
                    <dd
                      className={`min-w-0 text-right font-b-mono text-[12.5px] break-all ${changed ? "text-b-bad" : "text-b-text"}`}
                    >
                      {changed ? field.altered : field.original}
                      {changed && <span className="b-eyebrow ml-2 text-b-bad">edited</span>}
                    </dd>
                  </div>
                );
              })}

              <div className="flex items-baseline justify-between gap-4 px-5 py-3">
                <dt className="flex-none text-[12.5px] text-b-faint">SHA-256 over those bytes</dt>
                {/*
                  All sixty-four characters. It was truncated to thirty-two
                  with an ellipsis, which is fine for a digest nobody is asked
                  to check and wrong for this one: the sentence below tells a
                  reader to compare it against their own, and half a hash
                  cannot be compared against anything.
                */}
                <dd className="min-w-0 text-right font-b-mono text-[12px] break-all text-b-src">
                  {digest ?? "computing…"}
                </dd>
              </div>
            </dl>

            {/*
              A live region, because the verdict is the thing that changes and a
              reader operating the buttons by keyboard has no other way to know
              it did.
            */}
            <div
              aria-live="polite"
              className="border-t px-5 py-4"
              style={{
                borderColor: matches ? "var(--b-ok)" : "var(--b-bad)",
                background: `color-mix(in oklab, var(${matches ? "--b-ok" : "--b-bad"}) 8%, transparent)`,
              }}
            >
              <p
                className="b-eyebrow flex items-center gap-2"
                style={{ color: matches ? "var(--b-ok)" : "var(--b-bad)" }}
              >
                <span aria-hidden="true">{matches ? "✓" : "✗"}</span>
                {matches ? "Digest matches" : "Digest does not match"}
              </p>
              <p className="mt-2 text-[13px] leading-relaxed text-b-muted">
                {dirty
                  ? "One protected field was changed, so this is no longer the bundle that was written. Every field feeds the same hash, which is why one edit is enough."
                  : "These are the four values as recorded. Change any one of them and the hash above stops agreeing with the bundle."}
              </p>
            </div>

            {/*
              The controls, gathered into one row rather than a button per line.
              Per-row buttons put a permanent affordance beside every value and
              made the list read as a form; here the values are just values, and
              the row underneath says plainly what it is for.
            */}
            <div className="border-t border-b-line px-5 py-4">
              <p className="b-eyebrow mb-3 text-b-faint">Change a protected field</p>
              <div className="flex flex-wrap gap-2">
                {fields.map((field) => {
                  const changed = Boolean(edited[field.key]);
                  return (
                    <button
                      key={field.key}
                      type="button"
                      aria-pressed={changed}
                      onClick={() =>
                        setEdited((current) => ({ ...current, [field.key]: !current[field.key] }))
                      }
                      className="hit-target rounded-md border px-3 font-b-mono text-[12px]"
                      style={{
                        borderColor: changed ? "var(--b-bad)" : "var(--b-line-strong)",
                        color: changed ? "var(--b-bad)" : "var(--b-text)",
                      }}
                    >
                      {field.label}
                    </button>
                  );
                })}
                <button
                  type="button"
                  onClick={() => setEdited({})}
                  disabled={!dirty}
                  className="hit-target rounded-md border px-3 font-b-mono text-[12px] disabled:opacity-40"
                  style={{ borderColor: "var(--b-src)", color: "var(--b-src)" }}
                >
                  Reset
                </button>
              </div>
            </div>
          </div>
        </div>

        {/*
          The bytes, not a description of them.
          
          This used to say "hash the same four lines", and the four lines a
          reader could see were the values beside their human labels — Verdict,
          Subject, State after. What is actually hashed is `key=value` under
          the machine names, joined by newlines, with no trailing newline. So
          anyone who followed the sentence literally got a different digest and
          the only honest conclusion available to them was that this page was
          wrong. On the section whose argument is that a result you cannot
          re-derive is a result you cannot argue with.
          
          Printing the payload costs eight lines and removes the ambiguity
          completely: what is below is what goes in, byte for byte.
        */}
        <div className="mt-6 overflow-hidden rounded-xl border border-b-line">
          <p className="border-b border-b-line px-5 py-3 text-[12.5px] leading-relaxed text-b-muted">
            Computed in your browser with <code className="font-b-mono">crypto.subtle</code>, over
            exactly these bytes — no trailing newline. Run it yourself and you will get the digest
            above, which is the point of printing it rather than describing it.
          </p>
          <pre
            tabIndex={0}
            role="region"
            aria-label="Command to reproduce the digest, scrollable"
            className="overflow-x-auto px-5 py-4 font-b-mono text-[11.5px] leading-relaxed text-b-text"
          >
{`printf '${payload.replace(/\n/g, "\\n")}' | shasum -a 256`}
          </pre>
        </div>
      </div>
    </section>
  );
}
