import { Footer, Header } from "./components/Chrome";
import { Case } from "./sections/Case";
import { Close } from "./sections/Close";
import { Compare } from "./sections/Compare";
import { Contribute } from "./sections/Contribute";
import { Facts } from "./sections/Facts";
import { Hero } from "./sections/Hero";
import { HowItGrades } from "./sections/HowItGrades";
import { Integrity } from "./sections/Integrity";
import { MissingLayer } from "./sections/MissingLayer";
import { Quickstart } from "./sections/Quickstart";
import { Stack } from "./sections/Stack";
import { Status } from "./sections/Status";

/**
 * The second design.
 *
 * Built from `Outcome Assurance.dc.html`, keeping its visual system and its
 * section rhythm — ink and paper alternating, one argument per band — and
 * replacing its content wholesale. The design markets a product with claims,
 * review tasks, bound approvals and reconciled external outcomes. This
 * repository has scenarios, recorded tool calls, deterministic assertions and
 * a verdict, so the two sections that turned on the former were rebuilt on the
 * latter rather than filled with plausible substitutes: the case explorer runs
 * on Beacon's own tabs, and the approval panel became an integrity panel that
 * recomputes a real SHA-256.
 */

export function SiteB() {
  return (
    <>
      <Header />
      <main>
        <Hero />
        <Facts />
        <MissingLayer />
        <Case />
        <Integrity />
        <HowItGrades />
        <Stack />
        <Compare />
        <Status />
        <Contribute />
        <Quickstart />
        <Close />
      </main>
      <Footer />
    </>
  );
}
