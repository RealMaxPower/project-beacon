## What changes, and why

<!-- What was wrong or missing. Link an issue if there is one. -->

## Checks

<!-- Delete what does not apply. -->

- [ ] `python3 -W error::ResourceWarning -m unittest discover -s tests` passes
- [ ] `python3 examples/subjects/run_suite.py` still reports every verdict correct

**If this adds or changes an assertion:**

- [ ] A subject exists that makes it **fail**, and it fails on that assertion
      and no other

  An assertion nobody has watched fail is a claim the evidence does not
  support. This project has shipped three of those and found each one late;
  `tests/test_falsifiability.py` now enforces it, so a new assertion without a
  breaking subject fails CI.

**If this adds a tool to a scenario's surface:**

- [ ] Either no assertion punishes its use, or the goal text tells the subject
      not to use it

  Removing the tool instead is the tempting fix and the wrong one — it leaves
  the assertion unable to fail. State the prohibition and keep the tool.

**If this changes what a report or the README claims:**

- [ ] The claim is supported by something that runs

  Accurate about its own limits, including what a passing run does not prove.

## Anything you could not verify

<!-- Said plainly here is worth more than left out. Untested is fine; untested
     and unmentioned is what causes trouble. -->
