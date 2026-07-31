# Changelog

Notable changes to Project Beacon. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow
[semantic versioning](https://semver.org/spec/v2.0.0.html).

Two kinds of entry appear here, and the difference matters more than usual for
this project. **Added** is what Beacon can now do. **Fixed** is where Beacon
was reporting something it could not support — a wrong verdict, or a claim in
an evidence bundle that nothing had tested. The second kind is the more
important one: a harness that grades agents has no business shipping
statements it cannot back.

## [Unreleased]

Nothing is published yet. `pip install project-beacon` does not work; clone
the repository. Packaging and the release workflow are in place and verified
against a clean environment, so the first tag will publish.

### Added

- Seven scenarios: three graded on the state of a synthetic service, four on
  what a hosted agent returned — grounding, fabrication, output-schema
  conformance, and injection resistance at two integration levels.
- `beacon init`, which scaffolds a scenario that runs immediately together
  with the subject that violates it.
- `beacon scenarios`, and scenario resolution by bare name so a shipped
  scenario needs no path.
- `conforms_to` and `contains_none` assertions. The first reports every
  violation with its path rather than the first, and refuses a misspelled
  keyword instead of ignoring it.
- Regression detection against either a committed baseline or the last N runs,
  with a significance test so a flaky subject does not fail CI at random.
- Cross-run flakiness rates, replacing a binary stable/divergent verdict.
- An A2A subject adapter, and MCP stdio, Streamable HTTP and server-façade
  support, so an MCP host can be the subject over loopback HTTP.
- `--port` and `--token-env` for the façade, so a hand-configured GUI host
  keeps working between runs.
- A service registry, so a scenario pack can bring its own synthetic service
  without editing anything under `beacon/` — demonstrated by
  `examples/scenario-pack/` and enforced by a test that runs it from outside
  the repository.
- Credential passthrough by name only, with redaction from the evidence
  bundle, verified by a canary subject that tries to leak its key three ways.
- Reference A2A servers for all five official SDKs under `conformance/`.

### Fixed

- **An assertion Beacon could not evaluate was reported as failed.** An
  unreachable path became `passed: false`, so the report stated a conclusion
  about the subject that nothing had established — "Every entity the agent
  reports appears in the page it was given: FAILED" for a comparison that never
  ran, because a real model returned prose where the scenario expected
  `primary_entities[].value`. `docs/architecture.md` already drew the line
  between *the subject did the wrong thing* and *we do not know what the
  subject did*, and the runner already applied it when the declared artifact
  never arrived; it now reaches a path inside one. Such an assertion carries
  `measured: false`, prints as `NOT MEASURED`, and resolves the run to
  INCOMPLETE. `evidence_version` is `0.2`: the field is new and the same
  subject behaviour that reported FAIL now reports INCOMPLETE.
- **Three scenarios and `beacon init` graded a shape they never published.**
  `output_contract` is the only part of a scenario the subject is told, so a
  `conforms_to` on the contracted artifact is unmeetable unless the same schema
  appears there. `web-extraction-contract` and `web-extraction-grounding`
  demanded `url`, `page_type`, `primary_entities`, `tables`, `actions` and
  `metadata` while the contract said only "Structured extraction of the page at
  the URL in the goal" — a shape that was one hosted agent's native output, so
  those scenarios could grade that agent and nothing else. The loader now
  refuses a scenario whose published and graded schemas are absent or disagree,
  which found the same defect in `injection-resistance` and in what `beacon
  init` generates. `output_contract.schema` is published in the `start`
  message with the rest of the contract.
- **`--repeat` called every model-backed subject non-deterministic.** State was
  compared byte-for-byte, so a subject that wrote prose into a service diverged
  on wording alone — and the command exits non-zero, so the CI recipe in
  `docs/agent-builders.md` failed every run for any such scenario. Found on the
  first run of the bridge against a real model: five repeats of
  `inbox-briefing` returned PASS with one distinct assertion vector and
  identical draft metadata, reported DIVERGENT because the drafts were phrased
  differently. State is now compared by shape — a different number of drafts, a
  renamed or missing field, a changed count or flag, a body that is sometimes
  empty all still diverge, and a wording-only difference is reported as a note
  instead of a failure. `state.after_digest` in the bundle stays exact, because
  tamper evidence asks a different question. The adversarial suite could not
  have caught this: all forty subjects write byte-identical prose.
- **A credential could survive in the evidence bundle.** `usage` was the one
  field the redaction pass never walked, and `UsageRecorder` stores a `target`
  per call — the agent URL for an A2A subject. `--authorization` was never
  registered as a secret at all, unlike the `--env-secret` values the command
  and MCP-host adapters register. A token passed in an agent URL's query
  string therefore reached `evidence.json` intact, in the one artifact this
  project tells people to share.
- **A rejected scenario left an empty run directory behind.** The run
  directory was created before the services were built, so a scenario scoping
  a tool no service provides raised after taking a run id — and
  `--baseline-recent` reads that directory looking for previous runs.
- **Two tests launched subjects with a literal `python3`.** `docs/windows.md`
  says in its own words that this is a Store alias stub on Windows. One of the
  two was the falsifiability audit, the check that guarantees no report states
  something nobody has tested. Both passed on macOS and would have failed the
  Windows leg the moment it ran. `tests/test_suite_portability.py` now fails on
  any hardcoded interpreter.
- **The source distribution shipped a test suite that could not run.** With no
  `MANIFEST.in`, the sdist carried neither `examples/`, `schemas/`, `docs/`,
  `tests/stubs/` nor `.github/` — twelve test files read the first two, and
  thirteen README commands name a path under `examples/`. The release smoke
  test exercised only the subset of the CLI that needs no data files, so it
  stayed green throughout. It now unpacks the sdist and runs the suite.
- **The declared setuptools floor did not support the metadata in use.**
  `pyproject.toml` writes its licence as a PEP 639 SPDX expression, which needs
  setuptools 77; the floor said 69. Local builds passed because the local
  setuptools is newer than the floor — only an isolated build honouring it
  fails.
- **Claims about the project that nothing checked had drifted.** The README
  said "twenty-one subjects" ten lines above its own "40/40 verdicts correct";
  it credited the A2A SDK sweep with four defects where the survey records
  five; it called evidence "immutable" when nothing enforces that and no
  command verifies a digest; it said scenario validation is "checked against
  the published JSON Schema" when nothing under `beacon/` reads `schemas/`; it
  listed grading an MCP server as still to do when `MCPToolSubjectAdapter` is
  what probed 29 hosted agents; three documents described a CI that has not run
  automatically since `a23cdf3`; and `conformance/hosted-agent-probe.md` still
  quoted a five-run fabrication rate of 20% against the twelve-run 67% used
  everywhere else — the exact mistake the rest of the project warns about.
  `tests/test_documented_claims.py` and `tests/test_packaging.py` now pin the
  countable ones to their source of truth.
- **Six defects that made a working agent look broken.** A bare `Message`
  reply was reported INCOMPLETE — "did not run" — because only a `Task` was
  handled; the reply text was dropped entirely; `ROLE_AGENT` was not
  recognised as the agent; the legacy `/.well-known/agent.json` path was never
  tried, hiding two live public agents; an omitted `preferredTransport`
  defaulted to REST against JSON-RPC agents; and a version declared only on
  the interface was ignored. Found by running all five official A2A SDKs and
  three live deployments.
- **Assertions that could not fail.** `nothing-sent` was true regardless of
  the subject, and `messages-preserved` became unfalsifiable as a side effect
  of correctly removing a trapped tool. Both were stated in `report.md` as
  findings. `tests/test_falsifiability.py` now runs the audit that caught
  them across every scenario.
- **Citations satisfied by a name-drop.** Two `cites` assertions used
  corroborating tokens that appear inside the reference they corroborate, so
  naming the document passed the check. Now refused when the scenario loads.
- An assertion field the type does not read was accepted and silently
  ignored, so an authoring mistake printed as the agent's failure.
- `validate` reported every fixture as a service, including pinned documents.
- A subject that took time to shut down was killed and then blamed for it.
- Tool names contained dots, which providers reject, so a run failed on its
  first tool call rather than producing a verdict.
- An evaluator error destroyed the run instead of failing one assertion.
- MCP stdio parsing died on a blank line; the HTTP client did not follow
  307/308 on POST, which made a reachable server look dead.

### Known limitations

- The process runner is not a hardened container or VM sandbox.
- No native runtime adapter for OpenClaw, Hermes, Codex or similar.
- The MCP façade has never been driven by a GUI host. It needs a person; see
  [docs/running-it-yourself.md](docs/running-it-yourself.md).
- A passing report is evidence for one scenario and one configuration. It is
  not a safety certification.
