# Security policy

Project Beacon is an early technical MVP and must not be treated as a hardened
sandbox or a safety certification system.

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
- MCP and A2A inspectors connect directly to configured targets.
- Evidence digests are unsigned SHA-256 integrity checks.
- CLI authorization values exist in process arguments and may be visible to
  local process inspection; this option is for disposable test credentials
  only.

Security hardening is a release gate before untrusted-subject or hosted use.

