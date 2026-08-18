from __future__ import annotations

import base64
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
import urllib.parse
from pathlib import Path
from unittest import mock

from beacon.adapters import A2ASubjectAdapter, JSONLCommandAdapter
from beacon.cli import main
from beacon.models import Scenario
from beacon.runner import run_scenario
from beacon.secrets import (
    MINIMUM_SECRET_LENGTH,
    SecretError,
    SecretRegistry,
    looks_like_a_secret,
)


ROOT = Path(__file__).resolve().parents[1]
SCENARIO = ROOT / "scenarios" / "inbox-briefing" / "scenario.json"
A2A_SCENARIO = ROOT / "scenarios" / "hosted-injection-resistance" / "scenario.json"
CANARY = ROOT / "examples" / "subjects" / "leaks_its_key.py"
#: The repository's own metadata, which an unpacked sdist does not have.
#:
#: Bound to a name and guarded with `is_dir()` because that is the exemption
#: `tests/test_packaging.py` grants: a directory the suite reads is required to
#: be packaged unless the file both names it and skips on it. An inline
#: `(ROOT / ".git").exists()` is not enough, and the packaging guard said so.
GIT_DIR = ROOT / ".git"

SECRET_VALUE = "sk-beacon-canary-4f8a2b17c9de-DO-NOT-SHIP"


class _FakeA2AResponse:
    """Stands in for a urlopen context manager, as the A2A client uses it."""

    def __init__(self, value: dict) -> None:
        self._payload = json.dumps(value).encode("utf-8")

    def __enter__(self) -> "_FakeA2AResponse":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def read(self) -> bytes:
        return self._payload


class SecretRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = SecretRegistry()
        self.registry.register("API_KEY", SECRET_VALUE)

    def test_a_raw_value_is_replaced_by_a_named_placeholder(self) -> None:
        self.assertEqual(
            self.registry.redact_text(f"Bearer {SECRET_VALUE} end"),
            "Bearer [redacted:API_KEY] end",
        )

    def test_url_encoded_and_base64_forms_are_replaced(self) -> None:
        encoded = urllib.parse.quote(SECRET_VALUE, safe="")
        b64 = base64.b64encode(SECRET_VALUE.encode()).decode()
        redacted = self.registry.redact_text(f"?key={encoded} basic={b64}")
        self.assertNotIn(encoded, redacted)
        self.assertNotIn(b64, redacted)

    def test_nested_structures_are_walked(self) -> None:
        payload = {
            "events": [{"payload": {"arguments": {"body": SECRET_VALUE}}}],
            "list": [SECRET_VALUE, {"nested": [SECRET_VALUE]}],
        }
        self.assertNotIn(SECRET_VALUE, json.dumps(self.registry.redact(payload)))

    def test_dictionary_keys_are_redacted_too(self) -> None:
        redacted = self.registry.redact({SECRET_VALUE: "value"})
        self.assertEqual(list(redacted), ["[redacted:API_KEY]"])

    def test_unrelated_text_is_untouched(self) -> None:
        self.assertEqual(self.registry.redact_text("nothing here"), "nothing here")

    def test_non_strings_survive_unchanged(self) -> None:
        self.assertEqual(self.registry.redact({"n": 1, "b": True, "z": None}),
                         {"n": 1, "b": True, "z": None})

    def test_a_short_value_is_refused_rather_than_silently_redacted(self) -> None:
        """Redacting "abc" everywhere would corrupt unrelated evidence."""
        with self.assertRaises(SecretError) as caught:
            SecretRegistry().register("SHORT", "a" * (MINIMUM_SECRET_LENGTH - 1))
        self.assertIn("shorter than", str(caught.exception))

    def test_an_empty_value_is_refused(self) -> None:
        with self.assertRaises(SecretError):
            SecretRegistry().register("EMPTY", "")

    def test_an_inactive_registry_is_a_pass_through(self) -> None:
        registry = SecretRegistry()
        self.assertFalse(registry.active)
        self.assertEqual(registry.redact({"a": SECRET_VALUE}), {"a": SECRET_VALUE})

    def test_credential_shaped_names_are_recognised(self) -> None:
        for name in ("ANTHROPIC_API_KEY", "github_token", "DB_PASSWORD", "AUTH"):
            with self.subTest(name=name):
                self.assertTrue(looks_like_a_secret(name))
        for name in ("HOME", "LANG", "PATH"):
            with self.subTest(name=name):
                self.assertFalse(looks_like_a_secret(name))


A2A_CARD = {
    "name": "Credentialed fixture agent",
    "version": "1.0.0",
    "supportedInterfaces": [
        {
            "url": "http://fixture.invalid/",
            "protocolBinding": "JSONRPC",
            "protocolVersion": "1.0",
        }
    ],
    "capabilities": {"streaming": False},
    "skills": [],
}

A2A_REPLY = {
    "message": {
        "messageId": "m-1",
        "role": "ROLE_AGENT",
        "parts": [{"text": "The public note describes phase two."}],
    }
}


class A2ACredentialTests(unittest.TestCase):
    """
    An A2A subject's credential arrives on the command line, not from the
    environment, and the command line is written into evidence verbatim.

    Two holes met here. `--authorization` was never registered as a secret, so
    nothing knew the value to remove; and `usage` was absent from
    `REDACTED_EVIDENCE_FIELDS` while `UsageRecorder` stores a `target` per
    call, so an agent URL carrying the same token in a query string survived in
    the one field the redaction pass skipped.
    """

    TOKEN = "a2a-fixture-token-91b7c4e2-DO-NOT-SHIP"

    def _run(self, base_url: str, authorization: str | None):
        def fake_urlopen(request: object, timeout: float = 0, context=None):
            del timeout, context
            if request.full_url.endswith(".json"):
                return _FakeA2AResponse(A2A_CARD)
            return _FakeA2AResponse(
                {"jsonrpc": "2.0", "id": "1", "result": A2A_REPLY}
            )

        patcher = mock.patch(
            "beacon.protocols.a2a._open", side_effect=fake_urlopen
        )
        patcher.start()
        self.addCleanup(patcher.stop)

        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        outcome = run_scenario(
            Scenario.load(A2A_SCENARIO),
            A2ASubjectAdapter(
                base_url, timeout_seconds=5, authorization=authorization
            ),
            output_dir=directory.name,
            run_id="credentialed",
        )
        return outcome, outcome.json_path.parent

    def test_the_bearer_token_reaches_none_of_the_written_files(self) -> None:
        _, run_dir = self._run("http://fixture.invalid", f"Bearer {self.TOKEN}")
        for name in ("evidence.json", "report.md", "events.json"):
            with self.subTest(file=name):
                text = (run_dir / name).read_text(encoding="utf-8")
                self.assertNotIn(self.TOKEN, text)

    def test_a_token_in_the_agent_url_is_redacted_from_usage(self) -> None:
        """
        The regression this pair was written for. `usage.calls[].target` is the
        agent URL, and it was published unredacted.
        """
        outcome, run_dir = self._run(
            f"http://fixture.invalid/?access_token={self.TOKEN}",
            f"Bearer {self.TOKEN}",
        )
        self.assertTrue(outcome.evidence.usage["calls"], "no call was recorded")
        self.assertNotIn(self.TOKEN, json.dumps(outcome.evidence.usage))
        text = (run_dir / "evidence.json").read_text(encoding="utf-8")
        self.assertNotIn(self.TOKEN, text)
        self.assertGreater(
            outcome.evidence.subject["secret_redaction"]["replacements"],
            0,
            "the token was in the URL, so something had to be replaced",
        )

    def test_the_credential_is_named_even_when_nothing_needed_removing(self) -> None:
        """
        A header-only credential never reaches the bundle, so the replacement
        count is legitimately zero. The name is still recorded, because "a
        credential was in play" is part of the conditions of the run.
        """
        outcome, _ = self._run("http://fixture.invalid", f"Bearer {self.TOKEN}")
        record = outcome.evidence.subject["secret_redaction"]
        self.assertEqual(record["names"], ["authorization"])
        self.assertEqual(record["replacements"], 0)

    def test_the_digest_still_verifies_after_redacting_usage(self) -> None:
        """Redaction must precede finalize(), for the new field as for the rest."""
        from beacon.models import canonical_digest

        _, run_dir = self._run("http://fixture.invalid", f"Bearer {self.TOKEN}")
        document = json.loads((run_dir / "evidence.json").read_text(encoding="utf-8"))
        published = dict(document)
        published["digest"] = ""
        self.assertEqual(document["digest"], canonical_digest(published))

    def test_no_authorization_means_no_redaction_record(self) -> None:
        outcome, _ = self._run("http://fixture.invalid", None)
        self.assertNotIn("secret_redaction", outcome.evidence.subject)


class CanaryTests(unittest.TestCase):
    """
    The test that makes the redaction claim worth printing in the README.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.directory = tempfile.TemporaryDirectory()
        with mock.patch.dict(os.environ, {"BEACON_CANARY_SECRET": SECRET_VALUE}):
            cls.outcome = run_scenario(
                Scenario.load(SCENARIO),
                JSONLCommandAdapter(
                    [sys.executable, str(CANARY)],
                    timeout_seconds=15,
                    env_secrets=["BEACON_CANARY_SECRET"],
                ),
                output_dir=cls.directory.name,
                run_id="canary",
            )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.directory.cleanup()

    def _run_dir(self) -> Path:
        return self.outcome.json_path.parent

    def test_the_secret_reached_none_of_the_written_files(self) -> None:
        for name in ("evidence.json", "report.md", "events.json"):
            with self.subTest(file=name):
                text = (self._run_dir() / name).read_text(encoding="utf-8")
                self.assertNotIn(SECRET_VALUE, text)

    def test_encoded_forms_reached_none_of_them_either(self) -> None:
        encoded = urllib.parse.quote(SECRET_VALUE, safe="")
        b64 = base64.b64encode(SECRET_VALUE.encode()).decode()
        for name in ("evidence.json", "report.md", "events.json"):
            with self.subTest(file=name):
                text = (self._run_dir() / name).read_text(encoding="utf-8")
                self.assertNotIn(encoded, text)
                self.assertNotIn(b64, text)

    def test_the_placeholder_is_present_so_redaction_actually_ran(self) -> None:
        text = (self._run_dir() / "evidence.json").read_text(encoding="utf-8")
        self.assertIn("[redacted:BEACON_CANARY_SECRET]", text)

    def test_the_digest_verifies_against_the_published_document(self) -> None:
        """Redaction must precede finalize(), or the digest is of a lost draft."""
        from beacon.models import canonical_digest

        document = json.loads(
            (self._run_dir() / "evidence.json").read_text(encoding="utf-8")
        )
        published = dict(document)
        published["digest"] = ""
        self.assertEqual(document["digest"], canonical_digest(published))

    def test_the_bundle_states_what_redaction_does_not_cover(self) -> None:
        self.assertTrue(
            any(
                "defeats that" in limitation
                for limitation in self.outcome.evidence.limitations
            )
        )

    def test_the_bundle_records_which_names_were_redacted(self) -> None:
        record = self.outcome.evidence.subject["secret_redaction"]
        self.assertEqual(record["names"], ["BEACON_CANARY_SECRET"])
        self.assertGreater(record["replacements"], 0)


class EnvironmentIsolationTests(unittest.TestCase):
    def test_an_unrequested_variable_does_not_reach_the_subject(self) -> None:
        from beacon.adapters.command import _safe_environment

        with mock.patch.dict(os.environ, {"UNRELATED_TOKEN": "value"}):
            environment = _safe_environment("run-1")
        self.assertNotIn("UNRELATED_TOKEN", environment)

    def test_named_variables_are_copied(self) -> None:
        from beacon.adapters.command import _safe_environment

        with mock.patch.dict(os.environ, {"HOME": "/home/x", "K": SECRET_VALUE}):
            environment = _safe_environment("run-1", ["HOME"], ["K"])
        self.assertEqual(environment["HOME"], "/home/x")
        self.assertEqual(environment["K"], SECRET_VALUE)

    def test_a_secret_that_is_not_set_stops_the_run_before_it_starts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            outcome = run_scenario(
                Scenario.load(SCENARIO),
                JSONLCommandAdapter(
                    [sys.executable, str(CANARY)],
                    timeout_seconds=15,
                    env_secrets=["DEFINITELY_NOT_SET_ANYWHERE"],
                ),
                output_dir=directory,
                run_id="missing-secret",
            )
        self.assertEqual(outcome.evidence.result, "INCOMPLETE")
        self.assertIn(
            "DEFINITELY_NOT_SET_ANYWHERE",
            outcome.evidence.subject["execution"]["error"],
        )


class CliGuardTests(unittest.TestCase):
    def test_a_credential_shaped_name_must_use_env_secret(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            code = main(
                [
                    "run",
                    str(SCENARIO),
                    "--output",
                    directory,
                    "--adapter",
                    "command",
                    "--command",
                    "python3 examples/reference_jsonl_agent.py",
                    "--env-passthrough",
                    "ANTHROPIC_API_KEY",
                ]
            )
        self.assertEqual(code, 2)

    def test_environment_options_are_rejected_for_the_in_process_subject(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            code = main(
                [
                    "run",
                    str(SCENARIO),
                    "--output",
                    directory,
                    "--env-passthrough",
                    "HOME",
                ]
            )
        self.assertEqual(code, 2)


@unittest.skipUnless(
    (ROOT / ".env.example").is_file(),
    "the repository's .env.example is not in this checkout",
)
class ExampleEnvironmentFileTests(unittest.TestCase):
    """
    `.gitignore` ignores `.env` and then whitelists `.env.example` by name.

    Skipped when the file is absent, which is the case inside an unpacked
    sdist: `.env.example` is a repository convenience and has no business in
    `pip install project-beacon`. `tests/test_packaging.py` enforces this
    doctrine for *directories* — a path the suite reads unguarded must be
    packaged — and a file slipped past it, which is how the release workflow
    came to fail on the first tag rather than on the first run.

    That whitelist is a loaded gun: the shortest path from a working setup to a
    published key is `cp .env .env.example`, and the one rule written to keep
    secrets out of the repository is the rule that would let it through.
    """

    EXAMPLE = ROOT / ".env.example"

    def test_the_example_file_exists(self) -> None:
        """`.gitignore` negates this filename, so it should be a real file."""
        self.assertTrue(self.EXAMPLE.is_file())

    def test_no_variable_in_it_carries_a_value(self) -> None:
        for line in self.EXAMPLE.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                with self.subTest(line=line):
                    self.assertEqual(line.split("=", 1)[1], "")

    def test_every_variable_it_names_is_one_something_reads(self) -> None:
        """
        An example file listing a variable nothing consumes teaches a setting
        that does nothing, which is worse than omitting it: the reader sets it,
        sees no effect, and stops trusting the file.
        """
        named = {
            line.split("=", 1)[0].strip()
            for line in self.EXAMPLE.read_text(encoding="utf-8").splitlines()
            if "=" in line and not line.lstrip().startswith("#")
        }
        self.assertTrue(named, "the example file declares no variables at all")
        sources = "".join(
            path.read_text(encoding="utf-8")
            for directory in ("beacon", "examples", "docs")
            for path in (ROOT / directory).rglob("*")
            if path.suffix in {".py", ".md"}
        )
        for variable in sorted(named):
            with self.subTest(variable=variable):
                self.assertIn(variable, sources)


class RepositorySecretTests(unittest.TestCase):
    """
    Nothing credential-shaped is committed to this repository.

    Everything else in this file checks that a secret handed to a *run* stays
    out of the evidence it writes. That is the harness behaving. It says
    nothing about the repository itself, and the repository is the thing about
    to be made public — so a key pasted into a fixture, a token in an example,
    or a private key committed by accident would have passed every test here.

    Deliberate fixture credentials are exempt by the convention already in use
    above: a value that ends `-DO-NOT-SHIP` is one this suite planted on
    purpose. That keeps the allowance narrow and visible in the value itself,
    rather than in a list of paths that grows quietly.
    """

    #: Shapes that are credentials wherever they appear. Deliberately not
    #: "high entropy string", which flags every digest and base64 fixture in a
    #: project built on both.
    SHAPES = (
        ("Anthropic key", r"sk-ant-[A-Za-z0-9_\-]{16,}"),
        ("OpenAI key", r"sk-[A-Za-z0-9]{24,}"),
        ("GitHub token", r"gh[pousr]_[A-Za-z0-9]{20,}"),
        ("GitHub fine-grained token", r"github_pat_[A-Za-z0-9_]{20,}"),
        ("AWS access key id", r"AKIA[0-9A-Z]{16}"),
        ("Google API key", r"AIza[0-9A-Za-z_\-]{30,}"),
        ("Slack token", r"xox[baprs]-[A-Za-z0-9\-]{10,}"),
        ("private key", r"BEGIN (?:RSA |OPENSSH |EC |DSA |PGP )?PRIVATE KEY"),
        ("PEM certificate key", r"BEGIN ENCRYPTED PRIVATE KEY"),
    )

    #: Values this suite plants on purpose carry this marker.
    DELIBERATE = "DO-NOT-SHIP"

    def _tracked(self) -> list[Path]:
        listing = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=ROOT, capture_output=True, text=True, check=True,
        )
        return [ROOT / name for name in listing.stdout.split("\0") if name]

    @unittest.skipUnless(
        GIT_DIR.is_dir(), "not a git checkout, so there is nothing tracked"
    )
    def test_no_tracked_file_carries_a_credential(self) -> None:
        patterns = [(name, re.compile(shape)) for name, shape in self.SHAPES]
        scanned = 0
        for path in self._tracked():
            # This file states every shape it looks for, so it matches itself.
            if path.name == Path(__file__).name or not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue  # a font or an image cannot carry a pasted key
            scanned += 1
            for number, line in enumerate(text.splitlines(), start=1):
                if self.DELIBERATE in line:
                    continue
                for name, pattern in patterns:
                    if pattern.search(line):
                        self.fail(
                            f"{path.relative_to(ROOT)}:{number} looks like a "
                            f"{name}. If it is a fixture, end the value "
                            f"'-{self.DELIBERATE}'; if it is real, it must not "
                            f"be committed, and rotating it comes before "
                            f"removing it from history."
                        )

        # A scan that read nothing passes, and reports the same green as one
        # that read everything.
        self.assertGreater(scanned, 100, "the scan read almost nothing")


if __name__ == "__main__":
    unittest.main()
