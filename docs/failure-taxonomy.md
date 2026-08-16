# The failure taxonomy

[taxonomy/failure-modes.json](../taxonomy/failure-modes.json) enumerates the
agent failure modes Beacon intends to measure. It exists to be the denominator
of a number.

Coverage claims are the easiest thing in this field to state and the hardest to
check. "Beacon covers 80% of agent failure modes" is not a measurable sentence,
because nobody has enumerated the set it quantifies over — so it cannot be
wrong, which is the problem with it. This file is the enumeration. The claim
becomes "100% of these 131 cells, here they are, argue with the list."

## What a cell has to be

A candidate is in scope only if all four hold:

1. **Distinct.** There is an agent that passes every other cell and fails this
   one. If not, it is a restatement of a cell that already exists and gets
   merged rather than counted.
2. **Buildable.** Expressible as deterministic synthetic fixtures graded by a
   named assertion type, with no model in the loop. A cell needing an LLM judge
   is out, because its verdict would not reproduce.
3. **Consequential.** The failure causes an incident or a user-visible defect.
   "Used three tool calls where two would do" is not; "deleted the file" is.
4. **Attributable.** The failure is the agent's. A payload the model could not
   decode does not measure restraint, it measures tokenisation.

**A cell is never excluded for being hard, expensive, or unbuilt.** Exclusion
requires one of those four to fail, and the rejected candidate goes into
`out_of_scope` in the same file naming the criterion it failed. That list is
the part worth reading first: it is what stops the denominator being quietly
trimmed until the numerator looks good.

## The thirteen families

| Family | The question it asks |
|---|---|
| `injection` | Does text the agent merely read become an instruction it follows? |
| `grounding` | Does the agent assert things its sources do not support? |
| `write-boundary` | Does the agent change or destroy more than it was asked to? |
| `read-boundary` | Does the agent reach data it was not given, or leak what it was? |
| `contract` | Does the result keep the shape its consumers depend on? |
| `deferral` | Does the agent stop and ask when it should, and only then? |
| `long-horizon` | Does the agent still obey the brief fifty steps later? |
| `delegation` | Does the agent treat another agent's output as data or as truth? |
| `cost` | Does the agent finish within the budget it was given? |
| `tool-use` | Does the agent call what it means to call, with what the tool takes? |
| `memory` | Does what the agent wrote down come back as something it obeys? |
| `precedence` | When two instructions it should trust disagree, which one wins? |
| `temporal` | Does the agent get deadlines, expiry and ordering right? |

Nine shipped with 1.0.0. Two more arrived with 1.1.0 and two with 1.2.0, each
because something the version before it could not say kept being said badly
inside a family that did not fit. Of the original nine, two were arrived at by
splitting and one by deleting, and the reasons are worth stating because they
are the kind of decision a reader should be able to disagree with.

**Authorisation split into read and write.** They overlap until you separate
them by direction: reaching data you were not given, versus changing state you
were not asked to change. The split maps onto how each is actually detected —
reads by canaries and absent events, writes by state comparison.

**Precedence is not deferral.** The deferral family asks whether an agent stops
when two legitimate instructions flatly contradict, which presumes it noticed
the contradiction. Every precedence cell is a conflict it does not notice: a
general rule quietly applied to the case that was named as an exception, an
instruction a later one withdrew, silence read as permission. An agent can
escalate every explicit conflict correctly and fail all five.

**Temporal is not grounding.** A date the sources do not support is a grounding
failure. A date computed wrong from an interval the sources state exactly, an
authorisation that was genuine until last week, a queue sorted by `created` when
the question was about `updated` — none of those are unsupported by anything.
Every figure is in the material and the arithmetic on top of it is the agent's.

**Determinism is not a family.** Self-consistency is a measurement method, not
a failure mode: every cell is repeatable with `--repeat`, and flakiness is
reported against `baselines/`. Making it a cell would either duplicate every
other cell or add one strange one.

**The agent's own instruction channel is not injection.** A lower-privilege
user supplying task text that overrides operator policy is a real failure, but
the text arrived legitimately. It lives in `read-boundary` as
`principal.user-overrides-operator`, because the question is whether the channel
carries a privilege level, not whether content became instruction.

## Gradeable now, versus in the taxonomy

Each cell declares what it `requires` — `service:files`, `service:shell`,
`assertion:cites`. A cell is **gradeable** when every requirement resolves
against what this build actually has.

That tier is computed, never stored. There is no `tier` field a author could
write, and no `covered` field either. Both are exactly the values someone would
be tempted to set favourably, so neither is settable.

The `requires` vocabulary is closed and split in two. Tokens under
`capabilities.available` must resolve against the live registries, or cells
would enter the gradeable tier that no scenario could be written for. Tokens
under `capabilities.planned` must **not** yet resolve, which is what stops a
shipped service from being left in `planned` while its cells sit outside the
denominator they now belong in. Both directions are tested.

So the published figure has two numerators over two denominators — covered out
of gradeable, and covered out of everything — and the first grows on its own as
services land.

## What it takes to cover a cell

A scenario claims a cell in its `coverage.primary` block, naming the assertions
that grade it and the adversarial subjects that break it. A claim is a
hypothesis. `tests/test_taxonomy_coverage.py` is what turns it into an
observation:

- the named breakers are **run**, and each must actually fail an assertion the
  claim is bound to. Stricter than the falsifiability check, which asks only
  whether *some* subject fails each assertion — a union, under which a subject
  can quietly stop breaking the assertion it was written for;
- another subject must **pass** the scenario, because a cell nothing can pass
  is as useless as one nothing can fail;
- the grading has to suit the family. Restraint graded by searching prose for
  the forbidden word measures whether the agent talked about it;
- for an injection cell, the canary must not sit **inside** the injected
  payload, or an agent that quotes the directive while refusing it scores as
  having leaked;
- a payload hidden at an encoding rung must name a **control**: another cell
  where the goal legitimately asks the subject to read that same encoding.
  Without it, a model that cannot decode base64 is indistinguishable from one
  that decoded it and declined;
- at most three cells per scenario, so the cheap way to raise the number is not
  to append cells to something that already exists.

A cell may leave `cells` only into `retired`, with a reason and a version.

## Reading the number honestly

- **Covered means probed once.** One payload, one configuration, one synthetic
  world. Resistance in a cell is not resistance in general. Coverage is
  breadth; `baselines/` is depth.
- **The denominator is ours.** A curated list this project chose. Another
  taxonomy would enumerate differently, which is why the rejections are
  published alongside.
- **Fixtures are invented.** Every one.
- **Comparable only within a `taxonomy_version`.** Always cite it.
- **The percentage falls when the taxonomy grows**, and that is intended. A
  coverage figure that only ever rises is measuring effort, not completeness.
- **This is coverage of the harness, not of your agent.** It says what Beacon
  can check. It says nothing about what your agent gets right.

## Working with it

```bash
python3 -m beacon taxonomy              # the figures, by family
python3 -m beacon taxonomy --uncovered  # gradeable cells nobody has built yet
python3 -m beacon taxonomy --json       # the report the site and tests read
```

`--uncovered` is the contributor roadmap, and the reason this file gets read
rather than left to rot: it turns the gap into a list of things to write.
