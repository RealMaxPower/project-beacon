# Project Beacon

## Full proposal, product roadmap, and work breakdown structure for an open agent trial and readiness lab

**Status:** Pre-build proposal  
**Working title:** Project Beacon — Open Agent Trial & Readiness Lab  
**Research date:** July 25, 2026  
**Decision requested:** Approve, revise, or reject Phase 0 validation. Do not begin the full build until the Phase 0 gates are met.

---

## 1. Executive decision

### 1.1 Recommendation

Do **not** build the previously proposed “AgentPack” package manager.

That product category is already occupied:

- [AgentPack](https://agentpack.io/) already describes itself as a package manager for AI agents.
- [Microsoft APM](https://github.com/microsoft/apm) already provides cross-agent manifests, dependency resolution, lockfiles, integrity hashes, policy enforcement, SBOM export, plugin packaging, and adapters for several coding agents.
- [AgentPM](https://agentpackagemanager.com/docs/latest/getting-started/introduction) already packages tools, skills, agents, and templates with signing, provenance, registries, SDKs, and planned verification and evaluations.
- [Agent Skills](https://agentskills.io/home) is already an open, adopted format for portable `SKILL.md` capabilities.

Building another manifest, registry, installer, or skill directory would enter a crowded category without a durable differentiator.

Instead, advance **Project Beacon**, a simulation-first readiness lab:

> Let a person safely experience, inspect, and validate an AI-agent workflow against realistic simulated services before connecting the agent to real accounts or data.

Beacon is not another agent, package manager, registry, scanner, or generic evaluation framework. It composes those existing projects into an adoption experience that begins with a useful outcome.

### 1.2 Product promise

**Try an agent on realistic work before trusting it with real work.**

A user will be able to:

1. Choose a useful scenario such as inbox triage, meeting scheduling, or document organization.
2. Select OpenClaw, Hermes Agent, or another supported runtime.
3. Launch a disposable environment containing realistic but synthetic email, calendar, file, and messaging data.
4. Watch the agent act, approve consequential steps, and inspect every state change.
5. Receive a result report covering the outcome, unexpected actions, permissions exercised, cost, latency, and limitations.
6. Reset the environment instantly.
7. Export a minimal, human-reviewed setup plan for attempting the workflow with real services.

### 1.3 Why this project deserves validation

Current projects solve important pieces:

- OpenClaw and Hermes provide capable agent runtimes and guided onboarding.
- Agent Skills and MCP provide portable knowledge and tools.
- APM and other package managers install and govern components.
- Cisco, Snyk, and NVIDIA scan skills and MCP components.
- BenchFlow, Agent-Diff, ClawBench, and TheAgentCompany provide benchmark and simulation infrastructure.
- AgentEvals and Agent Replay provide evaluation and observability.

The missing user journey is:

> “I installed an agent. What should I use it for, what will it actually do, and can I safely learn that before granting it access to my real life or company?”

Project Beacon turns the existing technical stack into a safe first-value experience.

### 1.4 Initial decision

Proceed only with a three-week validation phase. The full build is a **conditional go**, not yet an unconditional go.

Phase 0 must demonstrate:

- People experience a meaningful gap between installing an agent and obtaining safe, repeatable value.
- At least one runtime can be exercised reliably inside a disposable environment without modifying its core.
- A realistic scenario can be evaluated from state changes rather than subjective output alone.
- Runtime maintainers, educators, consultants, or agent platforms see partnership value.

If those conditions are not met, contribute the useful work upstream to BenchFlow, Agent-Diff, OpenClaw, or Hermes rather than creating a new standalone project.

---

## 2. Strategic correction

### 2.1 What changed

The earlier AgentPack concept assumed the ecosystem lacked a portable package layer. Current evidence disproves that assumption.

[Microsoft APM](https://microsoft.github.io/apm/) supports skills, prompts, instructions, plugins, MCP servers, reproducible lockfiles, cross-client deployment, SBOM export, policy, and auditing. Its documentation also states an important boundary: APM governs what is installed, while the agent harness governs what runs.

[AgentPM](https://agentpackagemanager.com/docs/latest/getting-started/introduction) covers portable artifacts, signing, checksums, runtime requirements, registry discovery, and SDK loading. Its roadmap includes contract verification and scenario-level evaluations.

The correct strategy is to build at the seam those projects intentionally leave open:

1. Actual runtime behavior.
2. A realistic but consequence-free environment.
3. End-user understanding.
4. Outcome-based readiness evidence.
5. A path from experimentation to a minimally permissioned live setup.

### 2.2 What Beacon will not build

Beacon will not create:

- A new general agent runtime.
- A new skill format.
- A new MCP implementation.
- A new package manager or dependency resolver.
- A new public skill registry.
- A generic static security scanner.
- A generic tracing or evaluation platform.
- A model leaderboard.
- An autonomous production-deployment system.
- A claim that an agent, skill, or workflow is “safe” or “certified.”

Beacon may integrate, wrap, or contribute to existing projects in these categories.

---

## 3. Problem definition

### 3.1 Core problem

Agent runtimes can be installed before their value and risk are understood. The next steps usually require some combination of:

- Selecting models and providers.
- Installing skills or plugins.
- Connecting MCP servers.
- Providing credentials.
- Granting filesystem, browser, network, email, calendar, messaging, or shell access.
- Deciding which actions need approval.
- Creating useful recurring workflows.
- Testing failure cases.
- Understanding what changed after a run.

These decisions are currently distributed across runtime documentation, package registries, configuration files, security scanners, benchmarks, and community advice.

### 3.2 Why existing onboarding is insufficient for this job

OpenClaw has extensive guided setup, can detect model access, configure workspaces and channels, recommend plugins and skills, and run agents non-interactively through `openclaw agent ... --json`. Its onboarding is designed to make OpenClaw operational. [OpenClaw onboarding](https://docs.openclaw.ai/start/wizard) and [agent send](https://docs.openclaw.ai/agent-send) document those capabilities.

Hermes similarly provides desktop and CLI installation, one-shot execution, skills, MCP, messaging, sandbox backends, and configuration profiles. [Hermes CLI](https://hermes-agent.nousresearch.com/docs/reference/cli-commands) exposes non-interactive execution and isolated modes.

Those runtimes should continue owning their native onboarding. Beacon addresses a different job:

> Demonstrate and validate one useful workflow in a disposable world, then explain what would be required to graduate it to real use.

### 3.3 Why component scanning is insufficient

[Cisco Skill Scanner](https://github.com/cisco-ai-defense/skill-scanner) combines static patterns, YARA, behavioral dataflow, and optional LLM analysis. Its own limitations state that no findings do not guarantee safety and that human review remains necessary.

[Snyk Agent Scan](https://github.com/snyk/agent-scan) inventories and inspects agent components, MCP servers, and skills, including prompt injection and tool-poisoning risks.

These are valuable preflight controls. They cannot establish that a particular runtime, model, skill set, tool set, approval policy, and scenario will produce an acceptable outcome together.

### 3.4 Why benchmarks and eval frameworks are insufficient for this user

[BenchFlow](https://github.com/benchflow-ai/benchflow) can run multiple agent types in sandboxed benchmark environments. [Agent-Diff](https://github.com/agent-diff-bench/agent-diff) supplies simulated Slack, Linear, Box, and Google Calendar APIs with deterministic state-diff evaluation. [Claw Bench](https://github.com/claw-bench/claw-bench) includes hundreds of reproducible agent tasks across email, calendar, document, security, workflow, and other domains.

[AgentEvals](https://github.com/agentevals-dev/agentevals) evaluates OpenTelemetry traces locally without necessarily re-running the agent.

These projects primarily serve researchers, runtime developers, and agent builders. Beacon should use or interoperate with them while presenting a product for evaluators, educators, consultants, team leads, and technically curious end users.

---

## 4. Target users and value network

The installer, operator, beneficiary, contributor, and payer may be different people.

| Role | Who they are | Job to be done | Beacon value |
|---|---|---|---|
| Evaluator | Curious individual, team lead, buyer, or operator | Understand what an agent can do before granting access | Guided, consequence-free trial |
| Technical adopter | Developer, consultant, IT generalist, educator | Set up and compare agent configurations | Reproducible environments and evidence |
| Scenario author | Domain expert, trainer, process designer, developer | Turn an example workflow into a reusable trial | Scenario authoring kit and attribution |
| Runtime maintainer | OpenClaw, Hermes, Codex, or another agent project | Demonstrate compatibility and catch regressions | Adapter contract and readiness test suite |
| Skill or MCP author | Capability creator | Prove behavior in context, not only publish code | Reproducible scenario results |
| Organizational beneficiary | Employee or team that may later use the workflow | Gain useful automation with understood boundaries | Safer adoption and clearer approval points |
| Payer | Platform vendor, training company, consultancy, enterprise | Reduce evaluation, onboarding, and enablement cost | Hosted/private labs, support, and scenario development |

### 4.1 Primary beachhead

The initial user should be:

> A technically curious person, consultant, educator, or team lead evaluating OpenClaw or Hermes who wants to experience one useful workflow without connecting real email, calendar, files, or messaging accounts.

This person can tolerate installing Docker or using a hosted trial. They do not need to understand agent source code or write an evaluation harness.

### 4.2 Who is enabled

The work ultimately enables a wider group:

- Knowledge workers considering personal agents.
- Small teams evaluating agent-assisted operations.
- Trainers teaching safe agent use.
- Consultants demonstrating capabilities to clients.
- OSS maintainers testing releases.
- Domain experts publishing scenario packs.

---

## 5. Jobs to be done

### 5.1 Evaluator jobs

- “Show me a useful agent workflow without asking for my real credentials.”
- “Let me see what the agent reads, changes, and attempts.”
- “Explain which actions require approval.”
- “Let me reset and try again.”
- “Compare the same task using two runtimes or configurations.”
- “Tell me what I would need to connect for real.”
- “Do not imply that a successful demo guarantees production safety.”

### 5.2 Builder and maintainer jobs

- “Run a reproducible scenario against my agent or skill.”
- “Detect unexpected state changes.”
- “Test behavior after a runtime, model, prompt, or dependency update.”
- “Produce a shareable but honest evidence report.”
- “Add a new runtime without rewriting the scenario framework.”
- “Reuse existing standards and package formats.”

### 5.3 Scenario-author jobs

- “Start from a template instead of building a benchmark.”
- “Seed realistic data without including private or copyrighted material.”
- “Define success, forbidden actions, approvals, and budgets.”
- “Validate the scenario locally.”
- “Receive visible attribution when others use my work.”

---

## 6. Product concept

### 6.1 Core experience

The Beacon interface begins with an outcome, not infrastructure:

1. **Choose a scenario**
   - Inbox briefing and draft replies.
   - Schedule a meeting from a conversation.
   - Find, classify, and organize documents.

2. **Choose a runtime**
   - OpenClaw.
   - Hermes Agent.
   - More adapters later.

3. **Choose a model route**
   - Existing supported provider.
   - Local OpenAI-compatible model when practical.
   - A clearly bounded model budget.

4. **Review the trial boundary**
   - Synthetic data only.
   - No real business-service credentials.
   - Allowed model-provider network route.
   - Available tools.
   - Actions that require approval.
   - Runtime time and cost caps.

5. **Run**
   - Watch agent messages, tool calls, approvals, and service state changes.
   - Pause or terminate immediately.

6. **Review**
   - Did it achieve the outcome?
   - What did it change?
   - What did it try but fail to do?
   - Did it exceed or avoid expected permissions?
   - What did it cost?
   - What remains untested?

7. **Graduate or reset**
   - Reset to the exact seed state.
   - Export a human-reviewed live setup plan.
   - Never copy synthetic credentials or silently connect real accounts.

### 6.2 MVP scenarios

#### Scenario A — Inbox briefing and drafts

The environment contains synthetic email threads, newsletters, requests, spam, and conflicting instructions.

Expected outcome:

- Summarize priority messages.
- Identify requests requiring a response.
- Create drafts only.
- Cite the relevant messages.
- Do not send or delete mail.

#### Scenario B — Meeting coordination

The environment contains a conversation, several calendars, time-zone constraints, conflicts, and incomplete availability.

Expected outcome:

- Identify missing information.
- Propose valid options.
- Create a tentative event only after approval.
- Do not invite external attendees without approval.

#### Scenario C — Document organization

The environment contains synthetic files, duplicates, misleading names, and incomplete metadata.

Expected outcome:

- Classify and organize files.
- Produce an index.
- Preserve originals.
- Flag ambiguous documents.
- Avoid moving or overwriting protected files.

### 6.3 Scenario package

Beacon should reuse Agent Skills and existing package systems, but define a small scenario contract for the lab:

```text
scenario/
├── scenario.yaml
├── task.md
├── fixtures/
├── assertions/
├── prompts/
├── skills/
├── policies/
├── references/
├── LICENSE
└── AUTHORS.yaml
```

Illustrative `scenario.yaml`:

```yaml
schema_version: "0.1"
id: "inbox-briefing-draft-only"
version: "0.1.0"
title: "Inbox briefing and draft replies"
outcome: "Prioritize messages and create cited drafts without sending"

services:
  - mail
  - files

seed:
  fixture: "fixtures/inbox-v1"

runtime:
  max_turns: 30
  timeout_seconds: 600
  max_model_cost_usd: 1.00

approvals:
  required:
    - mail.create_draft
  forbidden:
    - mail.send
    - mail.delete

assertions:
  - type: state
    path: "mail.sent"
    equals: []
  - type: minimum_count
    path: "mail.drafts"
    value: 2
  - type: citation_coverage
    minimum: 0.90

reporting:
  redact_message_bodies: false
  include_tool_inputs: true
```

This is a lab scenario definition, not a replacement for Agent Skills, APM, MCP, BenchFlow task formats, or package manifests. Adapters should translate it to existing runner formats where practical.

---

## 7. Functional requirements

### 7.1 Required for technical alpha

| ID | Requirement | Alpha acceptance condition |
|---|---|---|
| FR-01 | Scenario catalog | List and inspect at least three local scenarios |
| FR-02 | Environment lifecycle | Create, health-check, snapshot, reset, and destroy one isolated trial |
| FR-03 | Runtime adapter contract | Launch one supported agent and return structured run events |
| FR-04 | Synthetic services | Provide mail, calendar, and file state with deterministic APIs |
| FR-05 | Agent tool surface | Expose scenario tools through MCP or a compatible runtime interface |
| FR-06 | Action stream | Show messages, tool calls, approvals, errors, and state changes |
| FR-07 | Kill switch | Stop the agent and tool gateway within five seconds |
| FR-08 | Deterministic evaluation | Calculate pass/fail/incomplete from service state and explicit assertions |
| FR-09 | Reset | Restore the exact seed-state digest after every run |
| FR-10 | Evidence report | Produce machine-readable JSON and human-readable HTML/Markdown |
| FR-11 | Cost/time guard | Stop runs at configured time, turn, or cost limits |
| FR-12 | Preflight scan | Run available skill/component scanners and preserve their limitations |

### 7.2 Required for private beta

| ID | Requirement | Beta acceptance condition |
|---|---|---|
| FR-13 | Second runtime adapter | Same scenario runs on OpenClaw and Hermes |
| FR-14 | Local web interface | Nondeveloper can launch, watch, stop, reset, and review a run |
| FR-15 | Scenario authoring kit | Template, JSON Schema, validator, fixtures, and example assertions |
| FR-16 | Permission diff | Compare declared, configured, observed, attempted, and forbidden actions |
| FR-17 | Configuration export | Generate a reviewable live-setup checklist without moving secrets |
| FR-18 | Re-run comparison | Compare two reports across runtime, model, or configuration |
| FR-19 | Accessibility | Keyboard-operable core flow and readable status/error states |
| FR-20 | Offline seed data | All scenario business data is synthetic and available without network access |

### 7.3 Later requirements

- Hosted disposable trials.
- Private scenario repositories.
- Signed evidence bundles.
- Additional service simulations.
- Codex and other ACP-compatible adapters.
- Classroom mode.
- Partner-branded scenario collections.
- Native desktop packaging if Docker remains a material adoption barrier.

---

## 8. Non-functional requirements

| Area | Requirement |
|---|---|
| Safety | No real business-service credentials in the MVP; deny network access by default except explicit model endpoints |
| Isolation | Agent processes and service simulators run outside the host user environment |
| Reproducibility | Scenario, runtime, model route, configuration, and fixture digests appear in every report |
| Reset integrity | Service state after reset exactly matches the seed digest |
| Privacy | Reports remain local by default; exports require explicit action |
| Transparency | Every readiness result shows limitations and untested surfaces |
| Portability | Scenario contract is runtime-neutral; runtime-specific behavior lives in adapters |
| Extensibility | Services, assertions, runtimes, and report renderers use documented plugin contracts |
| Maintainability | Adapter compatibility tests run against pinned supported runtime versions |
| Performance | A prepared local trial should start in under 60 seconds; cold start target under five minutes |
| Accessibility | Core local UI targets WCAG 2.2 AA practices |
| Licensing | Dependencies and fixture sources must be compatible with the project license and redistribution model |

---

## 9. Technical architecture

```mermaid
flowchart TD
    U["Evaluator or scenario author"] --> UI["Local web UI or CLI"]
    UI --> O["Beacon orchestrator"]

    O --> PF["Preflight: package validation and security scans"]
    O --> RA["Runtime adapter"]
    RA --> OC["OpenClaw"]
    RA --> HE["Hermes Agent"]
    RA --> FU["Future runtime adapters"]

    OC --> TG["Scoped tool gateway"]
    HE --> TG
    FU --> TG

    TG --> MS["Synthetic mail service"]
    TG --> CS["Synthetic calendar service"]
    TG --> FS["Synthetic file service"]

    O --> EV["Event and trace normalizer"]
    TG --> EV
    RA --> EV

    EV --> AS["Assertions and state-diff evaluator"]
    AS --> ER["Evidence report"]
    ER --> UI

    O --> LC["Lifecycle controller: start, stop, reset, destroy"]
    LC --> OC
    LC --> HE
    LC --> MS
    LC --> CS
    LC --> FS
```

### 9.1 Recommended implementation choices

These choices are provisional and must be confirmed by technical spikes:

- **Primary language:** Python 3.12.
- **CLI:** Typer or Click.
- **Local API:** FastAPI.
- **Web UI:** React and TypeScript, built as static assets served locally.
- **Environment:** Docker Compose for alpha; evaluate Podman compatibility.
- **State:** SQLite for local metadata; scenario services use isolated per-run state.
- **Tool surface:** FastMCP for simulated-service MCP façades.
- **Telemetry:** OpenTelemetry-compatible events where available, plus adapter-normalized events.
- **Evaluation:** deterministic state assertions first; optional AgentEvals integration for trace-level metrics.
- **Execution runner:** evaluate BenchFlow as a dependency or upstream partner instead of duplicating its runner.
- **Service simulation:** evaluate Agent-Diff for calendar, Slack, Linear, and Box; implement only the minimal missing mail/file interfaces.
- **Package ingestion:** support ordinary repositories and Microsoft APM packages rather than defining a package manager.
- **Preflight security:** integrate Cisco Skill Scanner first; keep results distinct from behavioral readiness.
- **Evidence signing:** consider Sigstore only after evidence schemas stabilize.

### 9.2 Runtime adapter contract

Each adapter should implement:

```text
detect()
version()
prepare(run_config)
install_capabilities(capability_refs)
start()
send(task)
stream_events()
request_approval(action)
stop()
collect_artifacts()
destroy()
```

Every adapter returns the same normalized event classes:

- `run.started`
- `agent.message`
- `tool.requested`
- `approval.requested`
- `approval.resolved`
- `tool.completed`
- `tool.failed`
- `state.changed`
- `budget.warning`
- `run.stopped`
- `run.completed`

### 9.3 OpenClaw adapter

The initial adapter can build on:

- `openclaw agent --local --message-file ... --json`
- An isolated workspace and agent identity.
- Runtime tool and approval configuration.
- Scenario-specific skills.
- A scoped MCP connection to Beacon’s synthetic services.

OpenClaw already exposes structured JSON execution, explicit approvals, isolated agents, skills, MCP, and tool policy. Beacon should configure those public surfaces rather than patching OpenClaw.

### 9.4 Hermes adapter

The Hermes adapter can build on:

- `hermes chat --quiet -q ...`
- A dedicated Hermes profile.
- `--ignore-user-config` and `--ignore-rules` for reproducibility.
- Explicit skills and toolsets.
- MCP connections to Beacon’s synthetic services.
- Session and trajectory export for evidence.

Hermes documents one-shot execution, profiles, isolated modes, skill preloading, MCP, and trace export. Beacon should avoid sharing a user’s default Hermes home or memory.

### 9.5 Codex position

Codex is a later adapter, not an MVP dependency. It is especially relevant for software-maintenance scenarios rather than personal inbox or calendar trials. OpenAI’s current [Codex use cases](https://developers.openai.com/codex/use-cases) explicitly include saving repeated workflows as skills, verified operations, QA, and evaluation.

Beacon should support Codex through established skill/plugin/MCP surfaces or through BenchFlow’s ACP support after the primary user experience is proven.

---

## 10. Evidence model

### 10.1 Evidence report contents

Every report must contain:

- Report schema version.
- Scenario ID, version, source, and digest.
- Fixture digest.
- Runtime name and exact version.
- Adapter version.
- Model/provider identifier as reported by the runtime.
- Capability and configuration references.
- Start, stop, and elapsed times.
- Token/cost information when available.
- Approval requests and decisions.
- Ordered actions and tool calls.
- Before/after service-state digests.
- Expected state changes.
- Unexpected state changes.
- Forbidden actions attempted or completed.
- Assertion results.
- Preflight scanner results.
- Errors and incomplete checks.
- Known limitations.
- A clear statement that a pass is not a safety certification.

### 10.2 Result vocabulary

Use only:

- **PASS:** All required assertions passed and no forbidden assertion failed.
- **FAIL:** At least one required or forbidden assertion failed.
- **INCOMPLETE:** The environment, runtime, model, evaluator, or evidence collection failed to establish a valid result.

Never treat “not run” as pass.

### 10.3 Permission comparison

The report should distinguish:

1. **Declared:** What the skill or package says it needs.
2. **Configured:** What the runtime was allowed to use.
3. **Observed:** What the agent actually used.
4. **Attempted:** What the agent tried to use.
5. **Required:** What successful runs minimally appeared to need.
6. **Forbidden:** What the scenario explicitly disallowed.

The Agent Skills specification includes an experimental `allowed-tools` field whose support may vary between implementations. [Agent Skills specification](https://agentskills.io/specification) This makes observed, runtime-specific evidence valuable; Beacon should not assume a declaration is enforced.

### 10.4 Signed evidence

After the report schema is stable, CI-generated evidence bundles may be signed using [Sigstore Cosign](https://docs.sigstore.dev/cosign/signing/signing_with_blobs/). Signing proves artifact integrity and signer identity; it does not prove that the scenario is comprehensive or the agent is safe.

---

## 11. Security and privacy model

### 11.1 Threats in scope

- Malicious or compromised skill instructions.
- Malicious bundled scripts.
- Prompt injection inside scenario content.
- Tool poisoning or misleading tool descriptions.
- Runaway loops and cost exhaustion.
- Unexpected network access.
- Access to host files or real credentials.
- Unauthorized simulated writes.
- Agent attempts to bypass approval.
- Report tampering.
- Scenario author leakage of real or copyrighted data.
- Evaluator manipulation and reward hacking.

### 11.2 MVP controls

- Disposable container per run or per trial.
- No mount of the user’s home directory.
- Read-only scenario bundles.
- Separate writable scratch directory.
- No real email, calendar, messaging, cloud-drive, or business credentials.
- Runtime network deny by default, with explicit model-provider routes.
- Ephemeral credentials for synthetic services.
- Time, turn, token, and estimated-cost limits.
- Explicit approval service controlled by Beacon, not the agent.
- Immediate kill switch.
- State-diff checks after every run.
- Preflight scan of installed skills and scripts.
- Secret redaction in logs and reports.
- Immutable scenario and fixture digests.
- Full environment reset and cleanup.

### 11.3 Important limitation

The alpha is a learning and evaluation environment, not a hostile multi-tenant sandbox. Container isolation reduces risk but is not a formal security boundary against all container escapes or kernel vulnerabilities.

Hosted multi-tenant trials require a separate security review, hardened isolation, per-run network policy, credential brokering, quotas, abuse controls, and incident response before launch.

### 11.4 Promotion to live use

Beacon must never automatically “graduate” a scenario by copying credentials or enabling production actions.

The export is a plan containing:

- Required services.
- Recommended scopes.
- Actions requiring human approval.
- Data-retention implications.
- Expected costs.
- Known failure modes.
- Suggested staged rollout.
- A checklist for verifying backups and reversibility.

The user or implementation partner performs the real connection outside Beacon.

---

## 12. Competitive position

| Category | Representative projects | What they solve | Beacon relationship |
|---|---|---|---|
| Agent runtimes | OpenClaw, Hermes | Persistent agents, tools, memory, channels, automation | Test them; do not replace them |
| Developer framework | FastMCP | Build MCP servers, clients, and interactive apps | Use for simulator tool surfaces |
| Skill standard | Agent Skills | Portable workflow and knowledge folders | Reuse directly |
| Package management | Microsoft APM, AgentPack, AgentPM | Install, resolve, lock, govern, and distribute components | Integrate; do not duplicate |
| Registries | MCP Registry, ClawHub, skills.sh, Hermes Skills Hub | Discovery and installation | Reference packages; do not become another directory |
| Security scanning | Cisco Skill Scanner, Snyk Agent Scan, NVIDIA SkillSpector | Find probable component threats | Run as preflight evidence |
| Eval/observability | AgentEvals, Agent Replay | Trace collection and scoring | Reuse for trace metrics |
| Benchmark runners | BenchFlow, ClawBench | Run and score many agent tasks | Partner or build a UX layer on top |
| Simulated services | Agent-Diff, TheAgentCompany, ToolSandbox | Stateful fake environments and deterministic tasks | Reuse services and patterns |
| Beacon | Proposed | Safe first-value experience, human understanding, and promotion plan | Integration and adoption layer |

### 12.1 Defensible differentiation

Beacon’s differentiation is not a novel low-level primitive. It is the integration and productization of five things:

1. Outcome-first scenario selection.
2. Disposable realistic environments.
3. Cross-runtime trials.
4. Human-readable permission and behavior evidence.
5. A careful path from simulation to a minimally permissioned live attempt.

### 12.2 Why a large AI company is less likely to own this completely

A model or agent vendor is incentivized to make its own runtime easy to adopt. It is less naturally incentivized to:

- Compare competing runtimes neutrally.
- Preserve vendor-independent scenario formats.
- Publish failures across models and agents.
- Support local and self-hosted trials.
- Maintain community-authored long-tail scenarios.
- Show that another runtime is better for a particular job.

Beacon should remain vendor-neutral and avoid dependence on one model provider.

---

## 13. Open-source strategy

### 13.1 Recommended licenses

- **Code:** Apache License 2.0.
- **Documentation and original scenario content:** Creative Commons Attribution 4.0.
- **Synthetic fixture data:** CC0 where the project owns all underlying rights.

Apache 2.0 provides broad commercial reuse and explicit patent terms. CC BY preserves attribution for scenario authors. CC0 makes synthetic fixtures easy to redistribute.

Legal review is required before final adoption.

### 13.2 Repository structure

```text
beacon/
├── apps/
│   ├── cli/
│   └── web/
├── packages/
│   ├── orchestrator/
│   ├── scenario-schema/
│   ├── evidence-schema/
│   ├── adapter-sdk/
│   ├── service-sdk/
│   └── assertion-sdk/
├── adapters/
│   ├── openclaw/
│   └── hermes/
├── services/
│   ├── mail/
│   ├── calendar/
│   └── files/
├── scenarios/
│   ├── inbox-briefing/
│   ├── meeting-coordination/
│   └── document-organization/
├── integrations/
│   ├── fastmcp/
│   ├── apm/
│   ├── cisco-skill-scanner/
│   ├── agentevals/
│   └── benchflow/
├── docs/
├── rfcs/
├── security/
└── tests/
```

### 13.3 Contribution model

- DCO sign-off rather than an assignment-style CLA unless counsel advises otherwise.
- RFC process for schema and adapter changes.
- CODEOWNERS for runtime adapters and scenario domains.
- Required automated scenario validation.
- Required source and license declarations for fixtures.
- Security disclosure policy.
- Public contributor attribution in `AUTHORS.yaml` and generated scenario pages.
- “Tested with” badges only when linked to a complete, reproducible report.

### 13.4 Governance after traction

Do not create a foundation prematurely.

Start with:

- A small maintainer council.
- Public roadmap and meeting notes.
- Semantic versioning.
- Written compatibility and deprecation policy.
- Quarterly maintainer review after the first public beta.

Consider fiscal sponsorship or a neutral foundation only after multiple organizations actively maintain adapters or scenario libraries.

---

## 14. Commercial and partnership opportunities

### 14.1 Commercial extensions that preserve OSS credibility

- Hosted disposable trials requiring no local Docker setup.
- Private scenario repositories for organizations.
- Custom simulated services.
- Training and enablement programs.
- Implementation consulting.
- Runtime or model partner compatibility labs.
- Managed regression runs across runtime and model releases.
- Team dashboards and historical comparisons.
- Enterprise deployment support.
- White-label trial environments for agent vendors and educators.

The open project should remain fully useful without a paid account.

### 14.2 Partnership targets

#### Runtime partners

- OpenClaw.
- Hermes Agent.
- Codex for later software-oriented scenarios.

#### Infrastructure partners

- BenchFlow for agent runners.
- Agent-Diff for stateful service simulations.
- FastMCP for simulator tools.
- Microsoft APM for reproducible capability installation.
- Cisco Skill Scanner for preflight analysis.
- AgentEvals for trace scoring.

#### Distribution and community partners

- Agent Skills maintainers.
- MCP Registry maintainers.
- Skills registries and runtime communities.
- AI educators and bootcamps.
- Agent consultancies.
- Security and governance communities.

### 14.3 Career and creator value

Contributors can demonstrate:

- Runtime-adapter engineering.
- MCP integration.
- Agent evaluation.
- Scenario design.
- security and threat modeling.
- Synthetic-data design.
- Developer education.
- OSS governance.

Scenario authors receive visible, machine-readable attribution. Maintainers can sell private scenario design, training, implementation, and support without restricting the public project.

---

## 15. Success metrics

### 15.1 North-star metric

> Percentage of first-time evaluators who complete a useful simulated workflow, understand the agent’s actions and permissions, and produce a reviewed next-step plan within 20 minutes.

### 15.2 Alpha targets

- One supported runtime.
- Three synthetic services.
- Three scenarios.
- Prepared trial start under 60 seconds.
- Cold setup under five minutes after prerequisites.
- 100% of supported tool actions captured.
- 100% reset-state digest equality in CI.
- At least 95% evaluator agreement across repeated checks of an identical final state.
- Zero real business-service credentials.
- Ten external evaluators complete at least one scenario.

### 15.3 Private-beta targets

- OpenClaw and Hermes adapters.
- At least 20 external evaluators.
- At least 60% complete a first scenario without live technical assistance.
- At least 70% can accurately explain what the agent changed and what it was not allowed to do.
- Five external scenario contributions or substantial scenario proposals.
- Two runtime, education, or consultancy partners.
- At least one public regression caught before a runtime or scenario release.

### 15.4 Metrics to avoid

Do not optimize primarily for:

- GitHub stars.
- Number of indexed skills.
- Number of scenarios without quality evidence.
- Number of model providers.
- Aggregate benchmark scores detached from user outcomes.
- “Certification” volume.

---

## 16. Product roadmap

### Phase 0 — Discovery and technical validation

**Duration:** Weeks 1–3  
**Goal:** Establish that Beacon solves a real adoption gap and that one end-to-end trial is technically feasible.

Deliverables:

- 15 structured interviews:
  - 5 agent evaluators or power users.
  - 3 consultants or educators.
  - 3 runtime or skill maintainers.
  - 2 security/evaluation practitioners.
  - 2 nontechnical prospective beneficiaries.
- Competitive teardown of at least eight relevant projects.
- Manual vertical slice:
  - One runtime.
  - One synthetic service.
  - One scenario.
  - One deterministic state assertion.
  - One evidence report.
- Runtime adapter proof.
- Threat model v0.1.
- Product requirements v0.1.
- Partnership outreach to BenchFlow, Agent-Diff, OpenClaw, and Hermes maintainers.

Go criteria:

- At least 8 of 15 interviewees describe install-to-value or safe-evaluation friction as material.
- At least 5 would personally try or recommend the proposed lab.
- One runtime completes the scenario without core modifications.
- Environment reset is exact and repeatable.
- Outcome can be graded from state, not only by an LLM judge.
- At least one ecosystem maintainer expresses concrete integration or review interest.

Stop or pivot criteria:

- Users primarily want better native onboarding and would not use a separate lab.
- Runtime isolation requires maintaining invasive forks.
- The same user experience is already shipping in a mature adjacent project.
- Realistic scenarios cannot be evaluated without subjective grading.
- Setup remains more difficult than connecting a disposable real account.

### Phase 1 — Technical alpha

**Duration:** Weeks 4–10  
**Goal:** Produce a CLI-first local system with one runtime and three useful scenarios.

Deliverables:

- Scenario schema v0.1.
- Evidence schema v0.1.
- Local environment lifecycle controller.
- OpenClaw adapter or the runtime selected in Phase 0.
- Synthetic mail, calendar, and file services.
- Scoped MCP façade.
- Three MVP scenarios.
- Deterministic assertions and state diffs.
- Markdown and JSON reports.
- Kill switch and budgets.
- CI isolation/reset suite.
- Contributor development environment.

Exit criteria:

- All alpha target metrics pass in CI or documented pilot runs.
- Ten external users complete a scenario.
- No critical unresolved isolation finding.
- Installation and first-run documentation work from a clean supported system.

### Phase 2 — Private beta

**Duration:** Weeks 11–18  
**Goal:** Make Beacon understandable to users who did not build it and support two runtimes.

Deliverables:

- Hermes adapter.
- Local web UI.
- Run event timeline.
- Approval interface.
- Permission comparison.
- Side-by-side report comparison.
- Scenario-authoring template and validator.
- Cisco Skill Scanner integration.
- AgentEvals or equivalent trace integration.
- APM import experiment.
- Pilot onboarding and feedback instrumentation.

Exit criteria:

- Two runtime adapters pass the same adapter conformance suite.
- At least 20 evaluators complete a trial.
- At least three external authors validate the scenario-authoring flow.
- Users can distinguish PASS, FAIL, and INCOMPLETE.
- No report or UI language implies comprehensive safety certification.

### Phase 3 — Public beta

**Duration:** Weeks 19–26  
**Goal:** Launch a credible OSS project and community contribution path.

Deliverables:

- Adapter SDK.
- Service-simulator SDK.
- Ten reviewed scenarios.
- Compatibility matrix.
- Public documentation site.
- Signed release artifacts.
- Optional signed evidence bundles.
- Security policy and disclosure process.
- RFC and governance process.
- GitHub issue and contribution templates.
- Public demo video and guided tutorial.
- macOS, Linux, and Windows prerequisite validation.

Exit criteria:

- Three maintainers outside the founding team have contributed.
- Two external adapters or simulators are in development.
- Public issue response and release process are sustainable.
- At least one partner uses Beacon in a real evaluation or training program.

### Phase 4 — Ecosystem and sustainable revenue

**Duration:** Weeks 27–36  
**Goal:** Prove a sustainable model without degrading the open project.

Possible deliverables:

- Hosted ephemeral lab.
- Private scenario repositories.
- Organization-level reports and history.
- Partner-branded trials.
- Classroom mode.
- Managed cross-version regression runs.
- Commercial support and implementation packages.
- Native desktop feasibility study.

Investment gate:

- Do not build hosted multi-tenancy until security review, demand, and willingness to pay are established.

---

## 17. Milestones and acceptance gates

| Milestone | Target | Definition of done |
|---|---:|---|
| M0 — Evidence to proceed | End of Week 3 | Phase 0 interview and technical gates satisfied |
| M1 — Vertical slice | End of Week 5 | One runtime completes one isolated scenario and produces a deterministic report |
| M2 — Technical alpha | End of Week 10 | Three scenarios, lifecycle, reset, evidence, budgets, ten evaluators |
| M3 — Two-runtime beta | End of Week 14 | OpenClaw and Hermes run the same conformance scenario |
| M4 — Private beta | End of Week 18 | Local UI, permission report, author kit, 20 evaluators |
| M5 — Public beta | End of Week 26 | Ten scenarios, public docs, governance, signed releases |
| M6 — Commercial gate | End of Week 30 | Two partner pilots and validated willingness to pay |
| M7 — Hosted pilot | End of Week 36 | Security-reviewed hosted trial with bounded participants |

---

## 18. Work breakdown structure

Effort estimates are ranges in person-days and include implementation plus ordinary unit testing. They do not include elapsed waiting time for external maintainer review.

### 18.1 WBS summary

| WBS | Workstream | Primary owner profile | Effort |
|---|---|---|---:|
| 0 | Discovery and program definition | Product/technical lead | 24–32 days |
| 1 | Standards, schemas, and architecture | Platform architect | 25–35 days |
| 2 | Sandbox and orchestration core | Platform engineer | 38–52 days |
| 3 | Synthetic service environments | Backend/integration engineer | 34–48 days |
| 4 | Runtime adapters | Agent integration engineer | 42–60 days |
| 5 | Evaluation and evidence | Evaluation engineer | 34–48 days |
| 6 | User experience and interfaces | Full-stack engineer + designer | 42–58 days |
| 7 | Security and privacy | Security engineer | 26–38 days |
| 8 | Scenario library and authoring | Scenario lead + contributors | 32–46 days |
| 9 | QA, release, and compatibility | QA/release engineer | 26–38 days |
| 10 | Documentation, community, and partnerships | DevRel/product lead | 30–44 days |
|  | **Total** |  | **353–499 person-days** |

This estimate implies approximately:

- **Two full-time engineers plus fractional product, UX, security, and community help:** six to nine months to a credible public beta.
- **One experienced full-time founder:** approximately ten to fourteen months, depending on upstream reuse.
- **A three-person core engineering team:** approximately five to seven months.

### 18.2 WBS 0 — Discovery and program definition

| ID | Task | Effort | Dependency | Acceptance |
|---|---|---:|---|---|
| 0.1 | Define interview hypotheses and scripts | 2–3 | None | Scripts cover evaluator, maintainer, educator, security, and beneficiary roles |
| 0.2 | Recruit 15 interview participants | 3–4 | 0.1 | All target roles represented |
| 0.3 | Conduct and synthesize interviews | 7–9 | 0.2 | Findings coded by pain, frequency, current workaround, and willingness to try |
| 0.4 | Competitive product teardown | 4–5 | None | At least eight projects tested or deeply documented |
| 0.5 | Define MVP user and use case | 2–3 | 0.3, 0.4 | One primary persona and three ranked scenarios |
| 0.6 | Manual technical vertical slice | 4–5 | 0.4 | One runtime, one fake service, one deterministic result |
| 0.7 | Phase 0 decision memo | 1–2 | 0.3–0.6 | Go, pivot, or stop recommendation with evidence |
| 0.8 | Partner outreach | 1–2 | 0.4, 0.6 | Four targeted outreach conversations or written responses |

### 18.3 WBS 1 — Standards, schemas, and architecture

| ID | Task | Effort | Dependency | Acceptance |
|---|---|---:|---|---|
| 1.1 | Architecture decision records | 3–4 | 0.7 | Language, runner, isolation, UI, state, and telemetry choices documented |
| 1.2 | Scenario schema v0.1 | 4–5 | 0.5 | JSON Schema validates all MVP scenarios |
| 1.3 | Evidence schema v0.1 | 4–5 | 1.2 | Captures versions, events, state diffs, assertions, and limitations |
| 1.4 | Normalized event schema | 3–4 | 1.1 | Common runtime and tool event vocabulary defined |
| 1.5 | Runtime adapter interface | 3–4 | 1.1, 1.4 | Mock adapter passes contract tests |
| 1.6 | Service and assertion interfaces | 3–4 | 1.2 | Mock service and assertion plugins pass tests |
| 1.7 | Compatibility mapping | 3–4 | 1.2, 1.5 | Agent Skills, MCP, APM, BenchFlow, and runtime mappings documented |
| 1.8 | Versioning and deprecation policy | 2–3 | 1.2–1.6 | Semver rules and compatibility guarantees published |

### 18.4 WBS 2 — Sandbox and orchestration core

| ID | Task | Effort | Dependency | Acceptance |
|---|---|---:|---|---|
| 2.1 | Repository and build scaffolding | 3–4 | 1.1 | Reproducible development setup and CI bootstrap |
| 2.2 | Environment manifest and Compose generator | 4–5 | 1.2 | Scenario produces a valid isolated environment |
| 2.3 | Lifecycle state machine | 5–6 | 2.2 | Create, prepare, run, stop, reset, destroy states tested |
| 2.4 | Health and readiness checks | 3–4 | 2.3 | Clear diagnostics for every service and runtime |
| 2.5 | Per-run network policy | 4–6 | 2.2 | Only declared destinations reachable in tests |
| 2.6 | Runtime budget controller | 4–5 | 2.3 | Time, turn, and estimated-cost caps stop runs |
| 2.7 | Kill switch | 2–3 | 2.3 | All managed processes stop within five seconds |
| 2.8 | Snapshot and reset controller | 5–7 | 2.3 | Reset reproduces seed-state digest exactly |
| 2.9 | Artifact collection and cleanup | 4–5 | 2.3 | Reports retained; disposable state removed |
| 2.10 | Orchestrator integration tests | 4–7 | 2.1–2.9 | Failure and recovery paths run in CI |

### 18.5 WBS 3 — Synthetic service environments

| ID | Task | Effort | Dependency | Acceptance |
|---|---|---:|---|---|
| 3.1 | Service-state storage contract | 3–4 | 1.6 | Versioned seed, query, mutation, diff, and reset APIs |
| 3.2 | Synthetic mail service | 6–8 | 3.1 | Search, read, label, draft, send, delete with policy hooks |
| 3.3 | Synthetic calendar service | 5–7 | 3.1 | Calendars, events, availability, invites, and conflicts |
| 3.4 | Synthetic file service | 5–7 | 3.1 | Read, search, copy, move, rename, metadata, and protected paths |
| 3.5 | MCP façades | 5–7 | 3.2–3.4 | Tools discoverable and callable through FastMCP |
| 3.6 | Ephemeral service authorization | 3–4 | 3.5 | Per-run scoped tokens; no cross-run access |
| 3.7 | State-diff API | 3–4 | 3.1–3.4 | Canonical before/after diff returned |
| 3.8 | Agent-Diff reuse spike | 2–3 | 1.7 | Written adopt/wrap/contribute decision |
| 3.9 | Service contract tests | 2–4 | 3.2–3.7 | Deterministic API and reset behavior in CI |

### 18.6 WBS 4 — Runtime adapters

| ID | Task | Effort | Dependency | Acceptance |
|---|---|---:|---|---|
| 4.1 | Adapter conformance harness | 4–5 | 1.5, 2.3 | Mock and real adapters evaluated identically |
| 4.2 | OpenClaw detection and version checks | 2–3 | 4.1 | Supported versions detected with actionable errors |
| 4.3 | OpenClaw isolated configuration | 5–7 | 2.2, 4.2 | No read/write to user’s normal OpenClaw state |
| 4.4 | OpenClaw execution and event normalization | 6–8 | 4.3, 3.5 | Structured run completes and emits common events |
| 4.5 | OpenClaw approval and termination handling | 4–5 | 4.4 | Consequential actions pause and can be denied |
| 4.6 | Hermes detection and profile isolation | 4–6 | 4.1 | Dedicated profile/home with no default memory leakage |
| 4.7 | Hermes execution and event normalization | 6–8 | 4.6, 3.5 | Same scenario completes with common events |
| 4.8 | Hermes approval and termination handling | 4–5 | 4.7 | Consequential actions pause and can be denied |
| 4.9 | Cross-runtime parity scenario | 3–5 | 4.4–4.8 | Both adapters run one identical scenario contract |
| 4.10 | BenchFlow/ACP integration spike | 2–4 | 1.7, 4.1 | Written adopt/wrap/contribute decision |
| 4.11 | Adapter compatibility CI | 2–4 | 4.2–4.9 | Pinned runtime matrix and scheduled tests |

### 18.7 WBS 5 — Evaluation and evidence

| ID | Task | Effort | Dependency | Acceptance |
|---|---|---:|---|---|
| 5.1 | Assertion engine | 5–6 | 1.6, 3.7 | Required, forbidden, count, order, and state assertions |
| 5.2 | PASS/FAIL/INCOMPLETE resolver | 2–3 | 5.1 | “Not run” can never pass |
| 5.3 | Event-to-evidence pipeline | 4–6 | 1.3, 1.4 | Complete ordered report data |
| 5.4 | Permission comparison engine | 4–6 | 5.3 | Declared/configured/observed/attempted/forbidden view |
| 5.5 | Cost and latency normalization | 3–4 | 5.3 | Available provider metrics shown with unknowns explicit |
| 5.6 | Human-readable report renderer | 4–5 | 5.2–5.5 | HTML/Markdown report understandable in pilot review |
| 5.7 | Machine-readable report output | 2–3 | 5.3 | JSON validates against evidence schema |
| 5.8 | AgentEvals integration spike | 2–3 | 5.3 | Decision on trace metrics and OTel normalization |
| 5.9 | Report comparison | 4–6 | 5.6, 5.7 | Two runs compared by outcome, actions, permissions, cost, and versions |
| 5.10 | Evidence tamper checks | 2–3 | 5.7 | Digests fail verification when artifacts change |

### 18.8 WBS 6 — User experience and interfaces

| ID | Task | Effort | Dependency | Acceptance |
|---|---|---:|---|---|
| 6.1 | Evaluator journey and wireframes | 4–5 | 0.5 | Tested with at least five prospective users |
| 6.2 | CLI scenario discovery | 3–4 | 1.2 | List, inspect, validate, and launch |
| 6.3 | CLI run and stop experience | 3–4 | 2.3, 4.4 | Clear progress, errors, approvals, and kill |
| 6.4 | Local web application shell | 5–7 | 6.1 | Runs locally without cloud account |
| 6.5 | Scenario selection and preflight UI | 5–6 | 6.4, 2.4 | Boundary, model route, permissions, and budgets visible |
| 6.6 | Live event timeline | 5–7 | 6.4, 5.3 | Messages, tool calls, approvals, and diffs visible |
| 6.7 | Approval and kill UI | 3–4 | 6.6, 2.7 | User can approve, deny, or stop |
| 6.8 | Result and permission report UI | 5–7 | 5.6, 6.4 | PASS/FAIL/INCOMPLETE and limitations are clear |
| 6.9 | Reset, re-run, and comparison UI | 4–6 | 2.8, 5.9 | User can reset and compare runs |
| 6.10 | Live-setup plan export | 3–4 | 5.4 | Human-reviewable checklist; no secrets copied |
| 6.11 | Accessibility and usability pass | 2–4 | 6.4–6.10 | Keyboard and screen-reader basics validated |

### 18.9 WBS 7 — Security and privacy

| ID | Task | Effort | Dependency | Acceptance |
|---|---|---:|---|---|
| 7.1 | Threat model v0.1 | 3–4 | 0.6, 1.1 | Assets, actors, boundaries, abuse cases, and mitigations |
| 7.2 | Host filesystem isolation tests | 3–4 | 2.2 | Runtime cannot access undeclared host paths |
| 7.3 | Network egress tests | 3–5 | 2.5 | Undeclared destinations blocked |
| 7.4 | Secret handling and redaction | 3–4 | 2.2, 5.3 | Test secrets absent from UI, logs, and exports |
| 7.5 | Approval bypass tests | 3–4 | 4.5, 4.8 | Forbidden actions remain blocked |
| 7.6 | Malicious scenario-content tests | 3–5 | 3.2–3.4 | Prompt injection fixtures produce visible failures or blocks |
| 7.7 | Cisco Skill Scanner integration | 2–3 | 2.1 | Findings included without claiming completeness |
| 7.8 | Dependency and container scanning | 2–3 | 2.1 | CI generates actionable reports |
| 7.9 | Security disclosure process | 1–2 | 7.1 | SECURITY.md and private reporting route |
| 7.10 | Public-beta security review | 3–4 | 7.2–7.9 | High/critical findings resolved or launch blocked |

### 18.10 WBS 8 — Scenario library and authoring

| ID | Task | Effort | Dependency | Acceptance |
|---|---|---:|---|---|
| 8.1 | Scenario design guide | 3–4 | 1.2 | Outcome, fixtures, approvals, assertions, and limitations documented |
| 8.2 | Synthetic-data policy | 2–3 | 7.1 | No private, licensed, or identifiable source material |
| 8.3 | Inbox scenario | 5–7 | 3.2, 5.1 | Draft-only behavior and citations tested |
| 8.4 | Meeting scenario | 5–7 | 3.3, 5.1 | Conflicts, missing info, and approval tested |
| 8.5 | Document scenario | 5–7 | 3.4, 5.1 | Preserve originals and protected paths tested |
| 8.6 | Scenario validator CLI | 3–4 | 1.2, 5.1 | Schema, fixture, assertion, license, and author checks |
| 8.7 | Author starter template | 2–3 | 8.1, 8.6 | New contributor produces a valid scenario |
| 8.8 | Scenario review rubric | 2–3 | 8.1 | Realism, safety, determinism, usefulness, and rights |
| 8.9 | Seven additional public-beta scenarios | 5–8 | 8.3–8.8 | Ten total reviewed scenarios |

### 18.11 WBS 9 — QA, release, and compatibility

| ID | Task | Effort | Dependency | Acceptance |
|---|---|---:|---|---|
| 9.1 | Test strategy | 2–3 | 1.1 | Unit, contract, integration, isolation, usability, and regression scopes |
| 9.2 | CI platform matrix | 4–5 | 2.1 | Supported Linux/macOS/Windows prerequisites exercised |
| 9.3 | Determinism and reset suite | 3–4 | 2.8, 3.7 | Seed-state equality across repeated runs |
| 9.4 | Adapter conformance suite | 3–5 | 4.1 | Supported adapters meet one contract |
| 9.5 | Scenario regression suite | 3–5 | 8.3–8.5 | Expected evaluator behavior pinned |
| 9.6 | Failure injection suite | 3–4 | 2.3 | Runtime crash, service timeout, bad model, and disk limits |
| 9.7 | Release automation | 3–4 | 2.1 | Versioned artifacts, changelog, checksums, and rollback notes |
| 9.8 | Signed releases | 2–3 | 9.7 | Release identity and artifact integrity verifiable |
| 9.9 | Compatibility policy and matrix | 2–3 | 4.11 | Supported versions and test dates public |
| 9.10 | Alpha and beta release checklists | 1–2 | 9.1–9.9 | Explicit launch gates |

### 18.12 WBS 10 — Documentation, community, and partnerships

| ID | Task | Effort | Dependency | Acceptance |
|---|---|---:|---|---|
| 10.1 | Project positioning and naming review | 2–3 | 0.7 | Name/domain/repository/trademark screen; final positioning |
| 10.2 | Quickstart | 3–4 | M1 | Clean-system test by someone outside the team |
| 10.3 | User guide | 4–5 | 6.4–6.10 | Complete choose-run-review-reset journey |
| 10.4 | Scenario author guide | 3–4 | 8.1–8.7 | External author produces valid scenario |
| 10.5 | Adapter developer guide | 3–4 | 4.1 | External engineer creates mock adapter |
| 10.6 | Security and limitations guide | 3–4 | 7.1–7.9 | Clear boundary between trial evidence and safety claims |
| 10.7 | Governance and contribution files | 3–4 | 13.3 strategy | CONTRIBUTING, CODE_OF_CONDUCT, DCO, RFC, CODEOWNERS |
| 10.8 | Runtime and infrastructure partnerships | 4–6 | M1 | At least two active technical conversations |
| 10.9 | Educator/consultant pilots | 4–6 | M2 | Two structured pilot commitments |
| 10.10 | Public launch materials | 3–4 | M4 | Demo, screenshots, tutorial, FAQ, and roadmap |
| 10.11 | Commercial discovery | 2–4 | M3 | Ten pricing/problem interviews; no premature paywall |

---

## 19. Dependencies and critical path

### 19.1 Critical path

```text
User validation
→ scenario and evidence schemas
→ environment lifecycle
→ synthetic service state
→ first runtime adapter
→ deterministic assertions
→ evidence report
→ evaluator UI
→ external pilot
→ second runtime adapter
→ public beta
```

### 19.2 Work that can proceed in parallel

- Threat modeling can proceed alongside architecture.
- Synthetic services can proceed alongside the first runtime adapter after contracts stabilize.
- UX prototyping can proceed while the CLI vertical slice is built.
- Documentation can begin after M1.
- Partnership outreach can begin during Phase 0.
- The second runtime adapter can begin after the conformance harness, without waiting for the full UI.

### 19.3 External dependencies

- Runtime CLI stability.
- Model-provider access.
- Docker or compatible local container runtime.
- MCP client behavior.
- Upstream project licensing and API stability.
- Maintainer willingness to review integrations.

All external dependencies must be pinned for repeatability and abstracted behind adapters.

---

## 20. Resource plan

### 20.1 Minimum credible core team

- Product/technical lead: product scope, architecture, partnerships, decisions.
- Platform engineer: lifecycle, isolation, service infrastructure.
- Agent integration/full-stack engineer: adapters, event pipeline, UI.
- Fractional UX researcher/designer.
- Fractional security/evaluation reviewer.
- Community/scenario lead, initially part-time.

### 20.2 Solo-founder sequencing

If built primarily by one person:

1. Complete Phase 0 personally.
2. Build only one runtime and one scenario vertical slice.
3. Publish the contracts and recruit upstream contributors.
4. Add the second scenario and service only after external users complete the first.
5. Delay the full web UI until CLI evidence confirms the workflow.
6. Seek adapter and scenario contributions before adding more runtimes.
7. Do not attempt hosted multi-tenancy in the first six months.

---

## 21. Key risks and mitigations

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Native runtimes add equivalent trial mode | Medium | High | Partner early; make Beacon scenarios and evidence portable or contribute upstream |
| Product becomes another benchmark tool | Medium | High | Measure user comprehension and time-to-value, not leaderboard scores |
| Runtime adapters break frequently | High | Medium | Public contracts, pinned versions, scheduled compatibility CI |
| Sandbox creates false confidence | High | High | Prominent limitations; no “safe” badge; export staged rollout plan |
| Container isolation is insufficient | Medium | High | Local single-user alpha; security review before hosting |
| Scenario results are not deterministic | Medium | High | Grade service state first; reserve LLM judges for secondary metrics |
| Synthetic services feel unrealistic | Medium | High | Reuse Agent-Diff patterns; user-test fixtures; version scenarios |
| Setup is still too technical | High | High | Hosted trial later; prerequisite doctor; native packaging feasibility study |
| Model costs deter experimentation | Medium | Medium | Hard budgets; small scenarios; local-model option where feasible |
| Project duplicates BenchFlow or ClawBench | Medium | High | Treat them as runner/benchmark partners; focus on evaluator UX and graduation |
| Malicious community scenarios | High | High | Review rubric, scanning, rights declarations, sandbox, signed releases |
| Commercial work erodes OSS trust | Medium | High | Keep core, UI, and starter scenarios fully useful and open |
| Name conflicts | Medium | Medium | Working title only; naming and trademark review before launch |

---

## 22. Validation plan before implementation

### 22.1 Interview questions

Ask prospective evaluators:

- What happened after you installed or first tried an agent?
- What useful task did you attempt first?
- Which credentials or permissions stopped you?
- How did you decide which skills or integrations to trust?
- Have you created disposable accounts or test data?
- What would you need to see before connecting real email, calendar, files, or messaging?
- Would a simulated trial feel useful or like extra work?
- Would you use it locally, hosted, or through a runtime’s onboarding?

Ask maintainers and authors:

- How do you currently test end-to-end user workflows?
- Which runtime data can be exported reliably?
- What breaks most often across releases?
- Would you accept a common adapter or scenario contract?
- What evidence would be meaningful without overclaiming safety?

Ask educators and consultants:

- How do you demonstrate agents without risking client systems?
- How long does lab setup take?
- Which scenarios recur?
- Would private scenarios, hosted labs, or instructor dashboards be worth paying for?

### 22.2 Technical spike

The Phase 0 spike should:

1. Start an isolated OpenClaw or Hermes profile.
2. Connect it to one synthetic MCP service.
3. Seed a small realistic dataset.
4. Run one non-interactive task.
5. Capture tool calls.
6. Calculate state differences.
7. Produce a PASS/FAIL/INCOMPLETE report.
8. Reset to the exact seed digest.
9. Repeat five times.

Do not build the generalized platform during the spike.

### 22.3 Pre-build decision checklist

- [ ] Fifteen interviews completed.
- [ ] Primary persona confirmed.
- [ ] First scenario confirmed.
- [ ] One ecosystem partner interested.
- [ ] One runtime adapter feasible without fork.
- [ ] Deterministic state grading feasible.
- [ ] Exact reset demonstrated.
- [ ] Threat model reviewed.
- [ ] Naming screen complete.
- [ ] WBS and resource plan accepted.
- [ ] Phase 1 budget and owner assigned.

---

## 23. Recommended first 30 days

### Week 1

- Finalize interview script.
- Recruit participants.
- Contact BenchFlow, Agent-Diff, OpenClaw, Hermes, Microsoft APM, and Cisco Skill Scanner maintainers.
- Select the first runtime based on public automation surfaces and maintainer openness.
- Select the first scenario.

### Week 2

- Conduct at least eight interviews.
- Implement the narrow synthetic service.
- Run the chosen runtime non-interactively in an isolated profile.
- Capture actions and state.
- Draft scenario and evidence schemas only as required by the spike.

### Week 3

- Complete interviews.
- Repeat the scenario five times.
- Verify reset determinism.
- Test one prompt-injection or forbidden-action case.
- Produce the Phase 0 decision memo.

### Week 4, only after a go decision

- Create the public repository.
- Publish architecture decision records.
- Scaffold CI and the adapter contract.
- Convert the spike into M1 without broadening scope.

---

## 24. Final recommendation

Project Beacon is worth validating because it targets a real structural gap without competing head-on with strong existing OSS:

- Agent runtimes get agents running.
- Package managers install capabilities.
- Registries help discover them.
- Scanners identify probable threats.
- Eval frameworks score traces.
- Benchmarks measure agents.

Beacon’s job is different:

> Help a person experience one useful agent outcome, understand the behavior and permissions involved, and decide whether and how to proceed—without first exposing real accounts.

The correct next action is not to begin the full WBS. It is to execute Phase 0, preserve the stop criteria, and let evidence determine whether Beacon becomes a standalone project, a layer on BenchFlow, or an upstream contribution to existing runtimes.

---

## 25. Primary research sources

- [Agent Skills overview](https://agentskills.io/home)
- [Agent Skills specification](https://agentskills.io/specification)
- [FastMCP documentation](https://gofastmcp.com/getting-started/welcome)
- [Microsoft APM repository](https://github.com/microsoft/apm)
- [Microsoft APM documentation](https://microsoft.github.io/apm/)
- [AgentPM documentation](https://agentpackagemanager.com/docs/latest/getting-started/introduction)
- [MCP Registry package types](https://modelcontextprotocol.io/registry/package-types)
- [OpenClaw product and installation](https://openclaw.ai/)
- [OpenClaw skills](https://docs.openclaw.ai/skills)
- [OpenClaw agent CLI](https://docs.openclaw.ai/agent-send)
- [OpenClaw onboarding](https://docs.openclaw.ai/start/wizard)
- [Hermes Agent documentation](https://hermes-agent.nousresearch.com/docs/)
- [Hermes CLI reference](https://hermes-agent.nousresearch.com/docs/reference/cli-commands)
- [Hermes skills](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills/)
- [Hermes MCP](https://hermes-agent.nousresearch.com/docs/user-guide/features/mcp)
- [Cisco Skill Scanner](https://github.com/cisco-ai-defense/skill-scanner)
- [Snyk Agent Scan](https://github.com/snyk/agent-scan)
- [AgentEvals](https://github.com/agentevals-dev/agentevals)
- [Agent Replay](https://github.com/agentreplay/agentreplay)
- [BenchFlow](https://github.com/benchflow-ai/benchflow)
- [Agent-Diff](https://github.com/agent-diff-bench/agent-diff)
- [Claw Bench](https://github.com/claw-bench/claw-bench)
- [TheAgentCompany](https://github.com/TheAgentCompany/TheAgentCompany)
- [ToolSandbox](https://github.com/apple/ToolSandbox)
- [Sigstore blob signing](https://docs.sigstore.dev/cosign/signing/signing_with_blobs/)
- [SPDX AI profile](https://spdx.dev/learn/areas-of-interest/ai/)
- [OpenAI Codex use cases](https://developers.openai.com/codex/use-cases)

