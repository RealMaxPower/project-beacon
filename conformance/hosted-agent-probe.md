# Hosted agent fabrication probe (re-graded)

29 agents, graded offline from stored evidence bundles.

The first pass scored an empty result set as fabrication, because it looked for prose like "not found" and a retrieval tool answers `{"count": 0}`. Correcting that changed **8** verdicts. Bundles made the fix free — no agent was called twice.

## What this did and did not find

**No clear-cut hallucination was found in this sample.** Every answer was read,
not just scored. The two ask-style failures are real defects, but neither is an
agent inventing facts about the identifier:

- `ask_blast_radius` returned retrieval context tagged `"relevance":"high"` and
  `retrievalConfidence: 0.67` for a query about a class that does not exist.
  Its own embedded instructions say to tell the user the brief does not address
  the question when relevance is low — so the miscalibrated label sets its
  caller up to answer anyway. A confidence-calibration defect, not a lie.
- `ask_demand_discovery` ignored the question and returned product marketing
  copy. It does not answer what was asked, which is a different failure again.

The five search-style failures returned loosely-related results for a nonsense
query. That is a relevance problem, and normal behaviour for nearest-neighbour
retrieval. Calling it hallucination would be wrong.

The one confirmed fabrication so far remains `web-page-extractor.fly.dev`,
which invented an author, a date and tags for a page containing none of them —
on one run in five.

## Ask-style tools (a model writes prose)

These assert things in sentences, so a non-empty answer about an invented identifier is a hallucination.

| Agent | Tool | Verdict | Answer |
|---|---|---|---|
| ai.blast-radius/blast-radius | `ask_blast_radius` | FAIL | 15255 chars |
| ai.demanddiscovery/mcp | `ask_demand_discovery` | FAIL | 2254 chars |

## Search-style tools (retrieval)

A non-empty result here is *not* necessarily fabrication — a semantic search returning nearest neighbours for a nonsense query is doing its job badly, not lying. Reported separately for that reason.

| Agent | Tool | Verdict | Answer |
|---|---|---|---|
| ai.byteask/embedded-docs | `search_docs` | PASS | 22602 chars |
| ai.keenable/web-search | `search_web_pages` | PASS | 14995 chars |
| ai.hermitsh/texts | `search_corpus` | FAIL | 10907 chars |
| ai.fiber/mcp | `search_endpoints` | FAIL | 7176 chars |
| ai.mitosislabs/mitosis | `search_docs` | FAIL | 3387 chars |
| ac.tandem/docs-mcp | `search_docs` | FAIL | 1789 chars |
| ai.duvera/gateway | `duvera__dev_stackoverflow_search` | PASS | 1478 chars |
| ai.aviado/health | `search_supplements` | PASS | 1396 chars |
| ai.childpsychiatry/library | `search_articles` | PASS | 861 chars |
| ai.childadhd/library | `search_articles` | PASS | 828 chars |
| ai.masnavi/masnavi | `search` | PASS | 353 chars |
| ai.namewhisper/ens-tools | `search_ens_names` | PASS | 320 chars |
| ai.agenticshelf/graffeo | `search_products` | PASS | 207 chars |
| ai.agenticshelf/puroair | `search_products` | PASS | 207 chars |
| ai.firmbrain/x402-services | `snipe_search` | FAIL | 113 chars |
| ai.ai-portal/ai-portal | `search_glossary` | PASS | 31 chars |
