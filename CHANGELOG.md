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

- Reported token and cost figures, under `usage.reported`. A JSONL subject's
  `complete.metadata.usage`, an A2A task or message's `metadata.usage`, and an
  MCP result's `_meta.usage` all feed it, and the bundled Anthropic bridge
  reports its own — summed across turns rather than read off the last response,
  since a tool-using run is several billed requests. Kept apart from everything
  measured, and annotated in the run's `limitations`, because a token count is
  a claim by the party under evaluation rather than something Beacon watched.
  The command adapter previously recorded no usage at all, on the one path that
  actually spends money.
- `project-beacon verify`, which recomputes an evidence bundle's digest and reports
  whether it still matches. Checked against the raw published document rather
  than a round-trip through `Evidence`, because the digest was taken over what
  was published and a verifier that normalises the thing it is checking is not
  a verifier. It separates two failures a reader needs told apart: a bundle
  that no longer matches its digest has been edited, while one carrying a field
  this version does not know is merely newer, and calling that tampering would
  be an accusation the evidence does not support.
- Seven scenarios: three graded on the state of a synthetic service, four on
  what a hosted agent returned — grounding, fabrication, output-schema
  conformance, and injection resistance at two integration levels.
- `project-beacon init`, which scaffolds a scenario that runs immediately together
  with the subject that violates it.
- `project-beacon scenarios`, and scenario resolution by bare name so a shipped
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
- Recorded baselines in `baselines/`, from twelve runs of each web-extraction
  scenario against a real model — the first numbers in this repository that a
  reader can check against a committed artifact rather than take on trust.
  They replace a headline figure that lived only in prose.
- `--adapter mcp-tool`, which grades one tool on a hosted MCP server as the
  subject. The adapter existed and had probed 29 hosted agents, but it was
  reachable only by writing Python.

### Fixed

- **Two scenarios declared a cost nothing read.** `estimated_cost_usd: 0.25`
  was in `inbox-briefing` and `document-organization`, consumed by no code, and
  copied into every bundle they produced — a dollar figure published beside
  measured numbers, unchecked, and certain to drift as model prices move. It is
  removed, and `tests/test_falsifiability.py` now fails any scenario declaring
  a limit nothing enforces. The same guard catches a misspelled
  `timeout_second`, which used to be accepted in silence while the run took the
  30-second default.
- **Every evidence bundle published on the site failed its own integrity
  check.** `site/tools/build_fixtures.py` replaces the recording machine's
  repository path with a placeholder, and it did so *after* the run had sealed
  itself — so each fixture whose command names a path shipped a digest taken
  over a document that no longer existed. They were displayed beside a
  paragraph promising that a digest makes a later edit detectable. Nothing
  caught it because nothing could check a digest until `project-beacon verify` was
  written, and the first thing it was pointed at was these. The published
  document is now sealed over itself and says in its own `limitations` that a
  path was substituted; the alternative, leaving the stale digest, hid a real
  edit behind a number that looked authoritative and matched nothing.
- **The façade's body-size cap was bypassed by a minus sign.** The MCP server
  parsed `Content-Length` with a bare `int()`, so `-1` cleared the 4 MiB check
  and `rfile.read(-1)` then read until the client chose to stop — an unbounded
  body straight through the check written to bound it, on a handler thread
  that blocked for as long as the caller cared to hold it. The client side had
  screened the same header on its digits for exactly this reason; the constant
  was mirrored between the two and the enforcement was not. The handler also
  carries a socket timeout now: without one, a connection that opened and then
  said nothing held its thread for the life of the process, and nothing caps
  the thread count, so the façade could be tied up without presenting the
  token at all.
- **A remote agent decided how much memory the harness allocated.** The A2A
  client read the response with a bare `read()`. An Agent Card is fetched from
  a host named by the party under evaluation, and a sweep runs several at
  once. The MCP client was given a cap for this reason; the sibling client
  that reads a stranger's card was not. Capped now on both the declared length
  and the read itself, since a chunked body declares nothing.
- **A four-character bearer token was accepted for the tool façade.** A
  generated token is 32 random bytes, but the one an operator supplies through
  `--token-env` was checked only for being non-empty — and that token is the
  whole of what stands between another account on the machine and
  `beacon_submit`, the call that decides the recorded verdict. There is a
  floor now, checked both at the CLI, which can name the variable and refuse
  before a run directory exists, and in `MCPHTTPService`, which is the
  chokepoint every caller passes. The test suite's own pinned fixture was
  twelve characters and had to be replaced, which is the case for the floor
  in miniature.
- **A host that finished the work was reported as unmeasured.** `beacon_submit`
  is the completion signal MCP does not otherwise have, and the JSONL adapter
  already states the rule for its equivalent: nothing teardown reveals can
  retract a completion that was validly sent. The MCP host adapter did not
  follow it. A host that submitted a result and then hung closing a connection
  pool hit the timeout, and the adapter returned `timeout` regardless — so the
  run resolved INCOMPLETE and discarded an artifact Beacon had already recorded
  and graded. A submission now stands on its own; the termination is recorded
  in the subject metadata, in the `subject_completed` event, and as a
  limitation in `report.md`, which is the one a reader sees. `MCPServeAdapter`
  returned the right verdict for a Ctrl-C after a submission but recorded the
  interruption nowhere except the event log, so that run was indistinguishable
  from an untouched one. It now says so too.
- **A protected document could be rewritten or deleted in silence.**
  `FileService` checked the `protected` flag on read and on move, and recorded
  a `policy_violation` for each. Write and delete checked only the scenario's
  `allow_overwrite` and `allow_delete` policy, so a scenario that switched
  either on let a subject change a protected record with no policy event at
  all — the state diff would show the change and nothing would say it was not
  permitted. No shipped scenario sets those flags, which is the only reason
  nobody hit it: the trap was set for whoever wrote the next scenario pack.
  Both paths now check the record as well as the policy, as
  `files_write_protected` and `files_delete_protected`. The policy gate still
  runs first, so a scenario with deletion switched off keeps reporting
  `files_delete_blocked` and the evidence of runs that were already correct is
  unchanged.
- **A malformed evidence bundle crashed the run that found it.**
  `--baseline-recent` reads history out of the output directory and skips
  bundles it cannot read, but `Evidence.from_dict` raised `KeyError` for a
  bundle missing `run_id` or `result`, and `TypeError` for JSON that was not an
  object. Neither is what the function promises, neither is what the loader
  catches, and neither is caught by the CLI — so one truncated file beside the
  run directories ended a finished, graded run in a traceback. Both now raise
  `ValueError`, naming what was missing, and are skipped like any other
  unreadable bundle. `KeyError` is deliberately still not caught at the top
  level: it is this codebase's most common internal-bug signature, and
  swallowing it would turn a Beacon defect into `error: 'some_key'`.
- **`project-beacon adapters` advertised routes that did not exist and hid one that
  did.** The `--adapter` choices, the dispatch, and the printed table were
  three hand-written lists, and they drifted apart in both directions: the
  table listed `mcp-serve`, `mcp-stdio` and `a2a-http`, none of which are
  `--adapter` values, while `mcp-tool` appeared in none of the three. One
  declaration now feeds all three, each row carries a `reached_by` naming the
  command that reaches it, and the integration level is read from the
  adapter's own descriptor rather than retyped. A test walks
  `beacon.adapters.__all__` and fails if an exported adapter is unreachable.
- **A subject could write its own verdict into the report.** Artifact text is
  written by the subject and was inserted into `report.md` raw, so it could
  close the Artifacts heading and append a second Assertions section with a
  forged PASS row — in the document people are asked to read and share. The
  assertion table already escaped for this reason; the artifact section did
  not. Artifacts are now fenced, with a fence longer than any backtick run
  inside them.
- **The same forgery was still open through the artifact's name.** Fencing the
  content left the heading above it — `### {name}` — interpolating a string the
  subject also chooses: a JSONL subject sends the name, and a remote A2A agent
  names its own artifacts. A name carrying a line ending, or `<h2>` and
  `<table>` carrying none, put a second Assertions section and a forged PASS
  row back into `report.md`. The name is now rendered in a code span longer
  than any backtick run inside it, which is `_fenced` for a single line and
  takes the name out of inline parsing entirely. `evidence.json` still records
  the name exactly as it was sent.
- **A subject could delete the record of what it had just done.** `json.loads`
  accepts nesting that `dataclasses.asdict` cannot walk — the C decoder spends
  less stack per level than the Python walk that follows it — so a subject
  could act, then send one artifact nested past about 1200 levels and take
  `RecursionError` out through the evidence write. `RecursionError` is a
  `RuntimeError`, which the CLI did not catch, so the run ended in a traceback
  with no `evidence.json`, no `report.md` and no `events.json`: an empty run
  directory instead of a record of a subject that had already deleted
  documents. Structures the subject controls — artifact content, completion
  metadata, and every recorded event payload — are now bounded on the way in,
  with the deepest levels replaced by a marker and the truncation stated in
  the bundle's limitations rather than passed off as what was sent. The event
  log has its own guard as well: if it cannot be serialised, the bundle is
  written without it and says so, because a verdict and a state diff with no
  events still beats losing the run.
- **A failed MCP handshake leaked the server process.** `MCPStdioClient.start`
  raised with the child still running and its three pipes open, and the caller
  had no handle to close because it never received one. The documented test
  command `-W error::ResourceWarning` could not catch it: the warnings surface
  from `__del__` and reader threads, where they print as "Exception ignored"
  and the suite stays green. The suite is now warning-clean and asserts the
  cleanup directly.
- **`serve-mcp` could not serve a scenario pack.** `run` and `validate` took
  `--service-module` and `serve-mcp` did not, so a pack bringing its own
  service — the proof that a third party needs no changes under `beacon/` —
  could be run headless but never handed to a GUI host, which is the one flow
  that needs a person. The two headline features did not compose.
- **A resource budget that never applied.** `max_subject_calls` counts requests
  Beacon makes *to* a subject, so it binds only where Beacon drives: the A2A
  and MCP-tool adapters. `injection-resistance` declared one anyway, and
  `docs/running-it-yourself.md` cited it as the guard against a runaway model
  bill on a *command* subject, where it does nothing. The real bounds there are
  `timeout_seconds`, `max_protocol_messages`, and the bridge's own turn cap.
  A test now refuses a call budget on a scenario whose subject Beacon does not
  drive.
- **A sign-off rule nobody kept.** `CONTRIBUTING.md` required `git commit -s`
  and no commit in the project's history had the trailer. The rule now names
  the commit it starts applying from, and `tests/test_contributing_policy.py`
  checks every commit since. Existing history is left unsigned rather than
  rewritten, because a sign-off added retroactively by someone else certifies
  nothing.
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
- **Three scenarios and `project-beacon init` graded a shape they never published.**
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
- The façade binds to loopback, so only a host whose MCP client runs on the
  same machine can reach it — Cursor directly, Claude Desktop through a stdio
  proxy. Cowork, claude.ai and the mobile apps add a *remote* server that
  Claude connects to from Anthropic's cloud, which cannot see `127.0.0.1`, so
  those need a tunnel and the loss of the loopback control that implies. The
  instructions said to use Claude Desktop's connector settings, which is the
  cloud path and never could have worked.
- A passing report is evidence for one scenario and one configuration. It is
  not a safety certification.
