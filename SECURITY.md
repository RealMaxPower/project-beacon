# Security policy

Project Beacon is an early technical MVP and must not be treated as a hardened
sandbox or a safety certification system.

## Reporting a vulnerability

Do not open a public issue, pull request, or discussion for a security problem.

Report privately through GitHub's private vulnerability reporting on this
repository: **Security → Report a vulnerability**. If that is unavailable to
you, contact a maintainer listed in `.github/CODEOWNERS` privately and ask for
a secure channel before sending details.

Please include the affected version or commit, what an attacker can achieve,
and the smallest reproduction you have. A scenario file or subject script that
demonstrates the issue is ideal — and if it does so through Beacon's own
adapters, keep the fixtures synthetic.

Expect an acknowledgement within a week. Because nothing has been published
yet — the release pipeline is built and tested, but no tag has been cut and
there is nothing on PyPI to patch — there is no patch-time commitment yet; we
will tell you what we intend to do and when. We will credit you in the fix unless you
prefer otherwise.

Please give us a reasonable chance to respond before disclosing publicly.

### Out of scope

The limitations listed below are known, documented, and intentional at this
stage. Reports that restate them are not vulnerabilities. In particular, a
subject process reaching host resources available to the current user is the
*expected* behavior of the MVP runner, not a bug — see "Known security
limitations".

## Safe use of this MVP

- Run only subjects and MCP servers you trust on your workstation.
- Use synthetic fixtures and disposable test credentials.
- Do not connect production email, calendars, files, chat, customer data, or
  privileged infrastructure.
- Review generated reports before sharing them because tool outputs may contain
  sensitive content supplied by the tested subject.
- Prefer an isolated development machine or VM for unknown code.

## Known security limitations

- Child processes can access resources available to the current operating
  system user.
- There is no network egress firewall.
- There is no container, VM, seccomp, AppArmor, or sandbox-exec policy.
- MCP and A2A inspectors connect directly to configured targets. Both refuse a
  redirect that leaves the origin they were aimed at, and the MCP client also
  refuses one resolving inside the harness's own network — but that check
  resolves the name separately from the connection that follows it. A DNS
  answer that changes between the two defeats it. Treat the refusal as a guard
  against a careless redirect, not against a hostile resolver.
- Evidence digests are unsigned SHA-256 integrity checks.
- CLI authorization values exist in process arguments and may be visible to
  local process inspection; this option is for disposable test credentials
  only.

Security hardening is a release gate before untrusted-subject or hosted use.

