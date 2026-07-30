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
- The model bridge in `examples/` has never been run against a real API key,
  and the MCP façade has never been driven by a GUI host. Both need a person;
  see [docs/running-it-yourself.md](docs/running-it-yourself.md).
- A passing report is evidence for one scenario and one configuration. It is
  not a safety certification.
