# Releasing

How `project-beacon` reaches PyPI, and the three pieces of state that live
outside the repository and cannot be checked from a clone.

0.1.0, 0.1.1, 0.1.2 and 0.2.0 have been released. The three pieces of external
state below are configured; they are kept here because they cannot be checked
from a clone, so the only way to know they are still right is to have written
down what they were set to.

## What already works

`.github/workflows/release.yml` does more than build. Its `build` job:

1. builds an sdist and a wheel with `python -m build`
2. runs `twine check --strict` on both
3. asserts the git tag matches `version` in `pyproject.toml`
4. installs the wheel into a fresh virtualenv **in an empty directory** and
   exercises the paths a new user takes — `--version`, `scenarios`, `validate`,
   `run`, `init`, and a `--adapter command` run against the scaffolded subject
5. unpacks the sdist and runs the shipped test suite out of it

Step 5 exists because step 4 alone stayed green for weeks while the sdist was
shipping without `examples/`, `docs/`, `schemas/` and `tests/stubs/` — so the
suite it did ship could not run. A smoke test that only touches the subset of
commands needing no data files will not catch that.

The `publish` job uses **PyPI trusted publishing**: no long-lived API token
exists in this repository, and there is none to leak. The publisher action is
pinned to a commit rather than to `release/v1`, because that is a branch, and
whoever can move a branch can publish as this project.

## The three things that live outside the repository

### 1. Register the trusted publisher on PyPI

At <https://pypi.org/manage/account/publishing/>, add a **pending publisher**
(the project does not exist on PyPI yet, so it must be pending rather than
attached to an existing project):

| Field | Value |
|---|---|
| PyPI project name | `project-beacon` |
| Owner | `RealMaxPower` |
| Repository name | `project-beacon` |
| Workflow name | `release.yml` |
| Environment name | `pypi` |

All five must match exactly. The environment name in particular is not
optional — `release.yml` declares `environment: name: pypi`, and PyPI checks
it.

### 2. Create the `pypi` environment on GitHub

Settings → Environments → New environment → `pypi`.

If it does not exist, the `publish` job fails to start rather than failing
loudly at the upload, which is a confusing way to find out. Adding a required
reviewer to this environment is worth considering: it makes publication a
deliberate act even when a tag is pushed by accident.

### 3. Enable the workflows

**This is the one that is invisible from a checkout.** All three workflows are
`disabled_manually` at the GitHub level — a switch in the Actions tab that
overrides the trigger blocks in the YAML. A tag pushed today runs nothing at
all, silently.

Workflow ids are per-repository, so read them rather than copying them from
anywhere — including from an earlier version of this file, which carried three
that belonged to a repository that no longer exists:

```bash
REPO=RealMaxPower/project-beacon
gh api /repos/$REPO/actions/workflows \
  --jq '.workflows[] | "\(.id)\t\(.state)\t\(.name)"'
```

Enable CI and release by the ids that prints:

```bash
gh api -X PUT /repos/$REPO/actions/workflows/<ci-id>/enable
gh api -X PUT /repos/$REPO/actions/workflows/<release-id>/enable
```

**Leave Conformance disabled.** It calls third-party MCP servers and hosted
agents belonging to people who did not ask to be measured, and it should stay
manual permanently — see the header comment in that workflow.

Re-run the listing afterwards. An `enable` against an id that does not exist
returns quietly enough to be mistaken for success.

## Cutting a release

Run the local gate first. CI runs the same suite across three operating
systems, but it takes longer to tell you:

```bash
python3 -W error::ResourceWarning -m unittest discover -s tests
python3 examples/subjects/run_suite.py
```

Then build and install it yourself, in an empty directory, exactly as the
workflow will:

```bash
python -m build
python -m twine check --strict dist/*
python -m venv /tmp/fresh && /tmp/fresh/bin/pip install --quiet dist/*.whl
mkdir -p /tmp/elsewhere && cd /tmp/elsewhere
/tmp/fresh/bin/project-beacon --version && /tmp/fresh/bin/project-beacon scenarios
/tmp/fresh/bin/project-beacon run inbox-briefing
```

**The version is typed in three places and derived everywhere else.**
`pyproject.toml`, `beacon/__init__.py`, and the two `# <version>` comments in
`docs/verifying-a-checkout.md` that annotate a `--version` command a reader is
asked to compare against. (Written without a literal version, because a
checklist that names one is a fourth place to forget.) `tests/test_builtins.py` asserts the first two agree
and `VerificationTranscriptTests` pins the third, and `release.yml` asserts the
tag matches `pyproject.toml` — so the tag is tied to the rest only through
tests that have to have run. Change all three, and run the suite, before
tagging.

Everywhere else reads `__version__`: the MCP `serverInfo`/`clientInfo` blocks
did not until 0.1.2, and announced 0.1.0 to every host for two releases.

Documentation that must move in the same commit as the version bump, because
each one currently states the opposite:

- `CHANGELOG.md` — `## [Unreleased]` becomes `## [0.1.0]`, and the paragraph
  under it says `pip install` does not work
- `README.md` — no CI badge, deliberately. A build badge on a repository whose
  workflows are `disabled_manually` reads as green because nothing has run,
  which is the most misleading state a badge has. Add it once CI is enabled and
  has passed once:
  `[![CI](https://github.com/RealMaxPower/project-beacon/actions/workflows/ci.yml/badge.svg)](https://github.com/RealMaxPower/project-beacon/actions/workflows/ci.yml)`
- `README.md` — the website badge and the paragraph under it link
  `https://beaconlab.dev`, which resolved to a parked host answering 403 while
  this was written. Load it before tagging: a dead link in the first screen of
  the README is the first thing a reader meets. The same origin appears in
  every canonical tag, the sitemap, `robots.txt` and `llms.txt`, so if it is
  wrong it is wrong in eleven places — `tests/test_site_seo.py` holds the
  README to whatever `SITE_ORIGIN` says, so they move together or not at all.
- `README.md` — the status badge reads `not on PyPI`, and the Quickstart says
  "Not on PyPI yet, so clone it"
- `pyproject.toml` — the `Changelog` URL points at the file rather than
  `/releases`, with a comment saying to move it once a tag exists
- `docs/production-readiness.md` — the Distribution section and the verdict
  table row for installing as a dependency
- `README.md` — **nothing in it may be relative.** `pyproject.toml` sets
  `readme = "README.md"`, so the file is published verbatim as the PyPI project
  page, where a relative path resolves against `pypi.org/project/project-beacon/`
  rather than against the repository and reaches nothing.

  This entry used to name only the demo image, because a broken image is
  visible. 0.1.0 shipped with the image correctly absolute and **29 relative
  links** beside it, which fail silently — the warning was followed to the
  letter and the letter was too narrow. A released description cannot be
  edited, so they are wrong on that version permanently.

  `tests/test_packaging.py::LongDescriptionTests` enforces this now, so it is a
  build failure rather than something to remember. The entry stays here because
  the reason is not obvious from the test name.

- **No static badge may carry a version number.** 0.1.1 bumped the two files a
  test holds together and left `status-v0.1.0` beside them, so that release's
  project page announces the previous version and always will. A static badge
  is a claim with no mechanism behind it; the computed `pypi/v` badge prints
  what was actually published rather than what was last typed, so the version
  belongs there and in no badge beside it.

  `tests/test_packaging.py::LongDescriptionTests` and `BadgeFactTests` enforce
  this, along with the two badges that were correct by luck — the interpreter
  list against the classifiers, the coverage floor against `--fail-under`.

- **A PyPI version badge is added *after* the first publish, never before.**
  Added beforehand, it points at a package that does not exist yet, the first
  request answers "package or version not found", and that answer is cached —
  into a description that can never be edited. This is the same rule stated
  above for the CI badge, and 0.1.0 carries a permanently red badge because the
  rule was written for one badge and not the other.

Then:

```bash
git tag v0.1.0
git push origin v0.1.0
```

The tag triggers `release.yml`, which builds, verifies, and publishes.

## If something goes wrong

**A version already on PyPI cannot be replaced.** There is no `skip-existing`
in the publish step and no overwrite on PyPI — a bad `0.1.0` means yanking it
and releasing `0.1.1`. This is the reason for the clean-environment install and
the sdist suite run: both happen before the upload, and both have caught real
distribution defects.

To rehearse without publishing, run the workflow by hand from the Actions tab
with `publish: false`. Everything except the upload runs, including the
clean-install exercise and the shipped suite.
