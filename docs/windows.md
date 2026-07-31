# Running Beacon on Windows

Beacon is pure-stdlib Python and targets Windows alongside Linux and macOS.
The environment allowlist in the command adapter already carries `SYSTEMROOT`
and `WINDIR`, without which a Windows Python subject cannot start.

Nothing here needs WSL. Use PowerShell or `cmd`, native Python.

## Prerequisites

Python 3.11 or newer, from python.org or the Microsoft Store. No packages to
install. Check that the launcher works:

```powershell
python --version
```

Use `python`, not `python3` — on Windows `python3` is often a Store alias stub
that does nothing useful. Every command below uses `python`.

## Run the suite

```powershell
python -W error::ResourceWarning -m unittest discover -s tests -v
```

## Run the vertical slice

```powershell
python -m beacon validate scenarios/inbox-briefing/scenario.json
python -m beacon run scenarios/inbox-briefing/scenario.json
python -m beacon run scenarios/inbox-briefing/scenario.json --repeat 5
python examples/subjects/run_suite.py
```

Expected: `PASS` with nine passing assertions, `Determinism: STABLE across 5
runs`, and `40/40 verdicts correct`.

## Paths in `--command`

Both separators work. These are equivalent:

```powershell
python -m beacon run scenarios/inbox-briefing/scenario.json --adapter command --command "python examples\subjects\well_behaved.py"
python -m beacon run scenarios/inbox-briefing/scenario.json --adapter command --command "python examples/subjects/well_behaved.py"
```

Quote a path containing spaces:

```powershell
--command "python `"C:\Program Files\my agent\run.py`""
```

This needed fixing rather than documenting. `--command` is split with `shlex`,
whose POSIX mode treats the backslash as an escape character, so
`examples\subjects\well_behaved.py` silently became
`examplessubjectswell_behaved.py` and the run failed with a file-not-found
naming a path nobody typed. The CLI now splits with Windows rules on Windows.

Forward slashes remain the portable choice for anything you plan to share,
since the same command line then works on every platform.

## Environment variables

PowerShell:

```powershell
$env:ANTHROPIC_API_KEY = "sk-ant-..."
python -m beacon run scenarios/inbox-briefing/scenario.json --adapter command --command "python examples/anthropic_jsonl_agent.py" --env-secret ANTHROPIC_API_KEY --timeout 180
```

`cmd`:

```cmd
set ANTHROPIC_API_KEY=sk-ant-...
```

Note that only names are ever passed on the command line. Values are read from
Beacon's own environment, which keeps them out of `evidence.json` — where the
subject's command line is recorded verbatim — and out of shell history.

Environment variable names are case-insensitive on Windows but the names you
pass to `--env-secret` are matched against `os.environ` as given, so use the
exact casing.

## What differs from POSIX, and why it does not change a verdict

**Process termination.** Windows has no `SIGTERM`; `terminate()` maps to
`TerminateProcess`, so a killed subject reports a positive exit code rather
than the `-15` you see on Linux. Beacon treats any non-zero exit after a valid
`complete` as an event to record, not a verdict to change, so the platform
difference does not alter the result.

**Console encoding.** Pipes default to the locale encoding, which on Windows is
usually not UTF-8. The adapter reads and writes UTF-8, so the subject
environment sets `PYTHONIOENCODING=utf-8`. Without it, a subject emitting any
non-ASCII character — the em dash in the starter fixture, for one — produces a
decode error instead of a result. Non-Python subjects ignore the variable and
should write UTF-8 to stdout themselves.

**Line endings.** The bridge is newline-delimited JSON. Both sides run in text
mode, so `\r\n` is translated on the way in and out; a subject should write
`\n` and let Python handle it.

**Path separators in evidence.** `run_dir` and `command` are recorded as the
platform produces them, so bundles from Windows and Linux runs differ in those
fields. They are excluded from the `--repeat` determinism comparison, so
cross-platform runs still compare cleanly on verdict, state digests, and
assertion results.

## What CI would cover, and why it is not running

**No workflow runs automatically today.** Every one triggers on
`workflow_dispatch` only, because Actions minutes are billed on a private
repository and macOS bills at 10x — see CONTRIBUTING.md. So on Windows the
suite is only as covered as the last person to run it locally.

The matrix is still in the file and still correct: the `test` job would run the
full suite on Windows, macOS, and Linux across Python 3.11–3.13, and the
`vertical-slice` job would run the CLI on Windows and Linux — including the
`--command` path, which the unit tests never reach because they launch subjects
with `sys.executable` and absolute paths.

That gap is not theoretical. Two tests spawned subjects with a literal
`python3` — the Store alias stub described above — and passed for weeks on
macOS while being broken on Windows. `tests/test_suite_portability.py` now
fails on any hardcoded interpreter, because a platform bug only one runner can
catch is a bug nobody catches once that runner is switched off.

If you hit a Windows-specific failure, please include the output of
`python -VV` and whether you are on PowerShell or `cmd`.
