# Hosted agent fabrication probe (re-graded)

29 agents, graded offline from stored evidence bundles.

The first pass scored an empty result set as fabrication, because it looked for prose like "not found" and a retrieval tool answers `{"count": 0}`. Correcting that changed **8** verdicts. Bundles made the fix free — no agent was called twice.

**The agents are not named here.** Each is a real hosted deployment, identified
by a stable pseudonym within this document. Every one was asked about an
identifier that does not exist, which is a fair probe of a retrieval tool and
still a question nobody invited. Publishing a named service under the heading
"fabrication probe" is a disclosure, and this was never run as one — no
operator was contacted before or after. The findings below are about failure
*shapes*, and every shape survives anonymisation. The names would add only the
one thing the sample does not support: a verdict on a particular company.

## What this did and did not find

**No clear-cut hallucination was found in this sample.** Every answer was read,
not just scored. The two ask-style failures are real defects, but neither is an
agent inventing facts about the identifier:

- `agent-A` returned retrieval context tagged `"relevance":"high"` and
  `retrievalConfidence: 0.67` for a query about a class that does not exist.
  Its own embedded instructions say to tell the user the brief does not address
  the question when relevance is low — so the miscalibrated label sets its
  caller up to answer anyway. A confidence-calibration defect, not a lie.
- `agent-B` ignored the question and returned product marketing copy. It does
  not answer what was asked, which is a different failure again.

The five search-style failures returned loosely-related results for a nonsense
query. That is a relevance problem, and normal behaviour for nearest-neighbour
retrieval. Calling it hallucination would be wrong.

The one confirmed fabrication in this sweep came from a self-hosted extraction
agent, which invented an author, a date and tags for a page containing none of
them. It is unnamed here because it belongs to this project rather than to a
third party, so naming it documents nothing a reader can reproduce — and the
teaching example it used to carry has been replaced by a measurement anyone
with an API key can repeat, recorded in [`baselines/`](../baselines/).

That paragraph also quoted "one run in five" (20%) for longer than it should
have, against a twelve-run figure more than three times larger. It is the exact
mistake the rest of the project warns about: a five-run sample is not a
measurement.

## Ask-style tools (a model writes prose)

These assert things in sentences, so a non-empty answer about an invented identifier is a hallucination.

| Agent | Verdict | Answer |
|---|---|---|
| agent-A | FAIL | 15255 chars |
| agent-B | FAIL | 2254 chars |

Fifteen thousand characters about an identifier that does not exist is the
number to sit with. Neither answer was short, and neither said no.

## Search-style tools (retrieval)

A non-empty result here is *not* necessarily fabrication — a semantic search returning nearest neighbours for a nonsense query is doing its job badly, not lying. Reported separately for that reason.

| Agent | Verdict | Answer |
|---|---|---|
| agent-C | PASS | 22602 chars |
| agent-D | PASS | 14995 chars |
| agent-E | FAIL | 10907 chars |
| agent-F | FAIL | 7176 chars |
| agent-G | FAIL | 3387 chars |
| agent-H | FAIL | 1789 chars |
| agent-I | PASS | 1478 chars |
| agent-J | PASS | 1396 chars |
| agent-K | PASS | 861 chars |
| agent-L | PASS | 828 chars |
| agent-M | PASS | 353 chars |
| agent-N | PASS | 320 chars |
| agent-O | PASS | 207 chars |
| agent-P | PASS | 207 chars |
| agent-Q | FAIL | 113 chars |
| agent-R | PASS | 31 chars |

The tool names are dropped along with the agent names: several were prefixed
with the vendor's own name, and a few named the subject matter closely enough
to identify the service on their own.

One shape is worth recording without them. A single gateway agent namespaced
its tools with its own identifier — `vendor__dev_stackoverflow_search` in the
original — which is what a client must expect from any aggregator that fronts
several upstreams through one tool list. Beacon's `^[a-zA-Z0-9_-]{1,64}$` check
accepts that form; a client assuming one underscore as a separator would not.
