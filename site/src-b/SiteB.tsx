import { Playground } from "@/screens/playground/Playground";
import { Footer, Header } from "./components/Chrome";
import { DocsScreen } from "./sections/DocsScreen";
import { LegalScreen } from "./sections/LegalScreen";
import { NotFound } from "./sections/NotFound";
import { Case } from "./sections/Case";
import { Checks } from "./sections/Checks";
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
import { B_NOT_FOUND, useBRoute } from "./router-b";

/**
 * The second design.
 *
 * Built from a supplied mock that is not in this repository — the design/
 * directory holds the first design's files only — keeping its visual system
 * and its section rhythm, ink and paper alternating, one argument per band,
 * and replacing its content wholesale.
 *
 * That mock branded itself "Outcome Assurance". The wordmark here says Project
 * Beacon instead: outcome assurance is the category this sits in, the way
 * "continuous integration" is a category, and the body copy called the product
 * Beacon throughout while only the header disagreed. The design markets a product with claims,
 * review tasks, bound approvals and reconciled external outcomes. This
 * repository has scenarios, recorded tool calls, deterministic assertions and
 * a verdict, so the two sections that turned on the former were rebuilt on the
 * latter rather than filled with plausible substitutes: the case explorer runs
 * on Beacon's own tabs, and the approval panel became an integrity panel that
 * recomputes a real SHA-256.
 *
 * The playground is the first design's, imported rather than rebuilt. Its
 * utilities resolve through token *names*, so `tokens-b.css` declares those
 * names against this palette and all of it repaints — see the alias block
 * there for why a second copy was the wrong answer. What arrives here is one
 * implementation of a seven-step flow, and one place for its claims to be
 * checked.
 *
 * It is a route rather than a band because it is not an argument. Every
 * section above makes one and can be read by scrolling past it; the playground
 * asks the visitor to choose a scenario, choose a subject, and go — and a
 * multi-step flow embedded in a marketing scroll would leave them mid-run when
 * they meant to keep reading.
 */

export function SiteB() {
  const [location] = useBRoute();

  return (
    <>
      <Header route={location.route} />
      {location.route === "playground" ? (
        <main data-shared-screen>
          <Playground scenarioId={location.param} />
        </main>
      ) : location.route === "docs" ? (
        <main>
          <DocsScreen />
        </main>
      ) : location.route === "legal" ? (
        <main>
          <LegalScreen />
        </main>
      ) : location.route === B_NOT_FOUND ? (
        <main>
          <NotFound />
        </main>
      ) : (
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
          <Checks />
          <Contribute />
          <Quickstart />
          <Close />
        </main>
      )}
      <Footer />
    </>
  );
}
