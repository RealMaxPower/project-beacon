import { facts } from "@/data/fixtures";

/**
 * Version B, under construction.
 *
 * A deliberate stub: it exists so the second entry point can be proved to
 * build, serve under the real Content-Security-Policy, and pass the audits
 * before a single section of the design is ported. Standing the pipeline up
 * first is what makes every later failure attributable to the thing that
 * caused it.
 */

export function SiteB() {
  return (
    <main className="b-shell">
      <p className="b-eyebrow">Outcome Assurance</p>
      <h1 className="b-display">Agent work you can defend.</h1>
      <p className="b-lede">
        The second design is being built. It reads the same recorded runs as the first —{" "}
        {facts.scenarios} scenarios and {facts.subjects} adversarial subjects — so neither site
        can describe a run the other does not have.
      </p>
    </main>
  );
}
