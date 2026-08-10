import { useEffect, useMemo, useState } from "react";
import { evidenceFor } from "@/data/fixtures";

/**
 * Change a protected field, watch the digest stop matching.
 *
 * This is the source design's approval-binding panel, rebuilt on something
 * this repository has. The design binds an approval to an action digest, and
 * Beacon has no actions and no approvals — but it does hash every bundle it
 * writes, and `beacon verify` recomputes that hash. So the interaction
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
          <div className="rounded-xl border border-b-line p-6">
            <p className="b-eyebrow mb-4 text-b-faint">What it is for</p>
            <p className="text-[13.5px] leading-relaxed text-b-muted">
              An evidence bundle is meant to be handed to somebody who was not there. The digest
              is what lets them tell whether the copy they are reading is the copy that was
              written.
            </p>
            <p className="mt-4 border-t border-b-line pt-4 text-[13.5px] leading-relaxed text-b-muted">
              It is <span className="text-b-review">unsigned</span>. An edit becomes detectable;
              an author does not become provable. Anyone who can change the bundle can recompute
              the digest, so this is a check against accident and drift, not against a determined
              forger.
            </p>
          </div>

          <div className="overflow-hidden rounded-xl border border-b-line bg-b-raised">
            <div className="border-b border-b-line px-5 py-3">
              <span className="font-b-mono text-[12px] text-b-src">bundle://{evidence.run_id}</span>
            </div>

            <dl className="divide-y divide-b-line">
              {fields.map((field) => {
                const changed = Boolean(edited[field.key]);
                return (
                  <div key={field.key} className="flex items-baseline gap-4 px-5 py-3">
                    <dt className="w-32 flex-none text-[12.5px] text-b-faint">{field.label}</dt>
                    <dd
                      className={`min-w-0 flex-1 font-b-mono text-[12.5px] break-all ${changed ? "text-b-bad" : "text-b-text"}`}
                    >
                      {changed ? field.altered : field.original}
                    </dd>
                    <button
                      type="button"
                      onClick={() =>
                        setEdited((current) => ({ ...current, [field.key]: !current[field.key] }))
                      }
                      className="hit-target flex-none rounded-md border border-b-line-strong px-2.5 text-[11.5px] text-b-muted hover:text-b-text"
                    >
                      {changed ? "undo" : "change"}
                    </button>
                  </div>
                );
              })}
            </dl>

            <div className="border-t border-b-line px-5 py-4">
              <p className="b-eyebrow mb-2 text-b-faint">SHA-256 over those four fields</p>
              <p className="font-b-mono text-[12px] break-all text-b-text">
                {digest ? `${digest.slice(0, 48)}…` : "computing…"}
              </p>
            </div>

            {/*
              A live region, because the verdict is the thing that changes and a
              reader operating the buttons by keyboard has no other way to know
              it did.
            */}
            <p
              aria-live="polite"
              className={`flex flex-wrap items-center gap-2.5 border-t px-5 py-4 text-[13px] ${
                matches ? "border-b-ok/30 bg-b-ok/10" : "border-b-bad/30 bg-b-bad/10"
              }`}
            >
              <span aria-hidden="true" className={matches ? "text-b-ok" : "text-b-bad"}>
                {matches ? "✓" : "✗"}
              </span>
              <span className={matches ? "text-b-ok" : "text-b-bad"}>
                {matches ? "Digest matches" : "Digest does not match"}
              </span>
              <span className="text-b-muted">
                {dirty
                  ? "one field was changed, so this is not the bundle that was written"
                  : "this is the bundle as recorded"}
              </span>
            </p>
          </div>
        </div>

        <p className="mt-6 max-w-[70ch] text-[12.5px] leading-relaxed text-b-faint">
          Computed in your browser with <code className="font-b-mono">crypto.subtle</code>, over
          the four values shown. Hash the same four lines with{" "}
          <code className="font-b-mono">shasum -a 256</code> and you will get the same answer —
          which is the point of printing it rather than describing it.
        </p>
      </div>
    </section>
  );
}
