import { Footer, Header } from "./components/Chrome";
import { Facts } from "./sections/Facts";
import { Hero } from "./sections/Hero";
import { MissingLayer } from "./sections/MissingLayer";
import { Quickstart } from "./sections/Quickstart";
import { Status } from "./sections/Status";

/**
 * The second design.
 *
 * Built from `design/Outcome Assurance.dc.html`, with its visual system kept
 * and its content replaced. The design markets a product with claims, review
 * tasks, bound approvals and reconciled external outcomes; this repository has
 * scenarios, recorded tool calls, deterministic assertions and a verdict. The
 * sections that described the former are gone rather than filled with
 * plausible substitutes, and the ones that remain read their numbers from the
 * same recorded runs the first design uses.
 *
 * Two sections are still to come — the case explorer on Beacon's own tabs, and
 * the integrity panel that recomputes a bundle digest with real SHA-256.
 */

export function SiteB() {
  return (
    <>
      <Header />
      <main>
        <Hero />
        <Facts />
        <MissingLayer />
        <Status />
        <Quickstart />
      </main>
      <Footer />
    </>
  );
}
