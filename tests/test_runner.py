from __future__ import annotations

import copy
import json
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

from beacon.adapters import JSONLCommandAdapter, ReferenceInboxAdapter
from beacon.models import Scenario, canonical_digest
from beacon.runner import run_scenario
from beacon.services import register_service


ROOT = Path(__file__).resolve().parents[1]
SCENARIO = ROOT / "scenarios" / "inbox-briefing" / "scenario.json"
REFERENCE_COMMAND = ROOT / "examples" / "reference_jsonl_agent.py"


def _action_required_count() -> int:
    """
    How many replies the reference subjects are expected to draft.

    Derived from the fixture rather than hardcoded, so adding a message to the
    scenario cannot silently invalidate these tests.
    """
    messages = Scenario.load(SCENARIO).fixtures["mail"]["messages"]
    return sum(
        1 for message in messages if "action_required" in message.get("labels", [])
    )


class ResetVerificationTests(unittest.TestCase):
    """
    `reset_verified` is printed in every report as "Reset verified: yes", and
    a review twice concluded it was tautological — reset restores from the
    same deepcopy `before` was taken from, so of course the digests match.

    That reasoning holds only for a reset that restores everything. `before`
    is snapshotted from a clean service, so a reset that forgets some state
    leaves the subject's leftovers visible and the digests differ. The claim
    is real; nothing was testing it, which is what let the doubt persist.
    """

    class LossyService:
        """Restores its seed and forgets what the subject accumulated."""

        TOOL_DEFINITIONS = (
            {
                "name": "probe_touch",
                "description": "Accumulate a scrap of state.",
                "inputSchema": {"type": "object", "properties": {}},
            },
        )

        def __init__(self, fixture: dict, recorder: object) -> None:
            self._seed = copy.deepcopy(fixture.get("items", []))
            self._items = copy.deepcopy(self._seed)
            self._scratch: list[str] = []

        def definitions(self) -> tuple:
            return self.TOOL_DEFINITIONS

        def call(self, tool: str, arguments: dict) -> dict:
            self._scratch.append("residue")
            return {"ok": True}

        def snapshot(self) -> dict:
            return {
                "items": copy.deepcopy(self._items),
                "scratch": list(self._scratch),
            }

        def reset(self) -> None:
            self._items = copy.deepcopy(self._seed)  # forgets _scratch

    def _scenario(self) -> Scenario:
        return Scenario.from_dict(
            {
                "schema_version": "0.1",
                "id": "reset-probe",
                "name": "Reset probe",
                "description": "d",
                "goal": "Call the tool once.",
                "fixtures": {"resetprobe": {"items": [1, 2]}},
                "tools": ["probe_touch"],
                "assertions": [
                    {
                        "id": "task-completed",
                        "type": "equals",
                        "path": "subject.status",
                        "expected": "completed",
                        "description": "d",
                    }
                ],
            }
        )

    def _run(self, script: str) -> object:
        with tempfile.TemporaryDirectory() as directory:
            agent = Path(directory) / "agent.py"
            agent.write_text(script, encoding="utf-8")
            return run_scenario(
                self._scenario(),
                JSONLCommandAdapter([sys.executable, str(agent)]),
                output_dir=directory,
                run_id="reset-probe",
            ).evidence

    TOUCHING_AGENT = textwrap.dedent(
        """
        import json, sys
        json.loads(sys.stdin.readline())
        def send(v):
            sys.stdout.write(json.dumps(v) + "\\n"); sys.stdout.flush()
        send({"type": "tool_call", "id": "1", "tool": "probe_touch", "arguments": {}})
        json.loads(sys.stdin.readline())
        send({"type": "complete", "status": "completed", "summary": "done"})
        """
    )

    IDLE_AGENT = textwrap.dedent(
        """
        import json, sys
        json.loads(sys.stdin.readline())
        sys.stdout.write(json.dumps(
            {"type": "complete", "status": "completed", "summary": "done"}) + "\\n")
        sys.stdout.flush()
        """
    )

    def setUp(self) -> None:
        register_service(
            "resetprobe",
            lambda fixture, recorder: ResetVerificationTests.LossyService(
                fixture, recorder
            ),
        )
        self.addCleanup(
            lambda: __import__(
                "beacon.services.registry", fromlist=["_FACTORIES"]
            )._FACTORIES.pop("resetprobe", None)
        )

    def test_a_reset_that_forgets_state_is_reported_as_unverified(self) -> None:
        evidence = self._run(self.TOUCHING_AGENT)
        self.assertEqual(evidence.result, "PASS")
        self.assertFalse(
            evidence.reset_verified,
            "a lossy reset went unnoticed, so the report's claim is empty",
        )

    def test_the_same_service_verifies_when_nothing_accumulated(self) -> None:
        """
        Rules out the opposite error: a check that reports 'not verified' for
        every service would also fail the test above, and mean just as little.
        """
        evidence = self._run(self.IDLE_AGENT)
        self.assertTrue(evidence.reset_verified)

    def test_the_shipped_services_verify_on_a_real_run(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            evidence = run_scenario(
                Scenario.load(SCENARIO),
                ReferenceInboxAdapter(),
                output_dir=directory,
                run_id="reset-real",
            ).evidence
        self.assertTrue(evidence.reset_verified)


class RejectedScenarioTests(unittest.TestCase):
    """
    A scenario Beacon refuses to run must not leave a run directory behind.

    `--baseline-recent` reads the output directory to find previous runs of the
    same scenario and subject. An empty directory from a run that never started
    is not evidence of anything, and the run id it occupies cannot be reused.
    """

    def _unrunnable(self) -> Scenario:
        """A scenario that scopes a tool no registered service provides."""
        raw = json.loads(SCENARIO.read_text(encoding="utf-8"))
        raw["tools"] = ["calendar_list_events"]
        return Scenario.from_dict(raw)

    def test_the_scenario_is_still_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError) as caught:
                run_scenario(
                    self._unrunnable(),
                    ReferenceInboxAdapter(),
                    output_dir=directory,
                    run_id="rejected",
                )
        self.assertIn("no service provides", str(caught.exception))

    def test_no_run_directory_survives_the_rejection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                run_scenario(
                    self._unrunnable(),
                    ReferenceInboxAdapter(),
                    output_dir=directory,
                    run_id="rejected",
                )
            self.assertEqual(
                sorted(Path(directory).iterdir()),
                [],
                "an empty run directory was left behind",
            )


class RunnerTests(unittest.TestCase):
    def test_reference_adapter_produces_passing_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            outcome = run_scenario(
                Scenario.load(SCENARIO),
                ReferenceInboxAdapter(),
                output_dir=directory,
                run_id="reference-pass",
            )
            evidence = outcome.evidence
            self.assertEqual(evidence.result, "PASS")
            self.assertEqual(
                len(evidence.state["after"]["mail"]["drafts"]),
                _action_required_count(),
            )
            self.assertEqual(evidence.state["after"]["mail"]["sent"], [])
            self.assertTrue(evidence.reset_verified)
            self.assertEqual(evidence.digest, canonical_digest(evidence.unsigned_dict()))
            self.assertTrue(outcome.json_path.exists())
            self.assertTrue(outcome.markdown_path.exists())
            self.assertIn(
                "# Beacon evidence: PASS",
                outcome.markdown_path.read_text(encoding="utf-8"),
            )

    def test_external_jsonl_adapter_uses_same_scenario_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            adapter = JSONLCommandAdapter(
                [sys.executable, str(REFERENCE_COMMAND)],
                timeout_seconds=10,
            )
            outcome = run_scenario(
                Scenario.load(SCENARIO),
                adapter,
                output_dir=directory,
                run_id="command-pass",
            )
            self.assertEqual(outcome.evidence.result, "PASS")
            self.assertEqual(
                outcome.evidence.subject["adapter"],
                "jsonl-command",
            )
            tool_calls = [
                event
                for event in outcome.evidence.events
                if event["kind"] == "tool_call"
            ]
            # One listing, then a read and a draft per action-required message.
            self.assertEqual(len(tool_calls), 1 + 2 * _action_required_count())


if __name__ == "__main__":
    unittest.main()



class SubjectStderrTests(unittest.TestCase):
    """
    A subject that dies takes its traceback with it unless someone keeps it.

    stderr was drained only after a successful `complete`, so every failure
    path reported a symptom — "closed stdout before completion" — and
    discarded the one thing that said why. Found when Windows CI failed on
    two scaffold tests and the logs contained nothing to act on.
    """

    def _run(self, body: str) -> object:
        with tempfile.TemporaryDirectory() as directory:
            agent = Path(directory) / "agent.py"
            agent.write_text(textwrap.dedent(body), encoding="utf-8")
            return run_scenario(
                Scenario.load(SCENARIO),
                JSONLCommandAdapter([sys.executable, str(agent)]),
                output_dir=directory,
                run_id="stderr-probe",
            ).evidence

    def test_a_crashing_subject_reports_its_traceback(self) -> None:
        evidence = self._run(
            """
            import json, sys
            json.loads(sys.stdin.readline())
            raise RuntimeError("this is why the subject died")
            """
        )
        error = evidence.subject["execution"]["error"]
        self.assertIn("this is why the subject died", error)
        self.assertIn("subject stderr", error)

    def test_the_original_diagnosis_is_kept_alongside_it(self) -> None:
        """The stderr is added to the reason, not swapped for it."""
        evidence = self._run(
            """
            import json, sys
            json.loads(sys.stdin.readline())
            raise RuntimeError("boom")
            """
        )
        self.assertIn(
            "closed stdout before completion", evidence.subject["execution"]["error"]
        )

    def test_a_silent_subject_still_reports_the_plain_reason(self) -> None:
        """No stderr means no stderr section, not an empty one."""
        evidence = self._run(
            """
            import json, sys
            json.loads(sys.stdin.readline())
            sys.exit(0)
            """
        )
        error = evidence.subject["execution"]["error"]
        self.assertNotIn("subject stderr", error)
        self.assertTrue(error)

    def test_a_subject_that_completes_is_unaffected(self) -> None:
        evidence = self._run(
            """
            import json, sys
            json.loads(sys.stdin.readline())
            sys.stderr.write("a warning nobody should be punished for\n")
            sys.stdout.write(json.dumps(
                {"type": "complete", "status": "completed", "summary": "done"}) + "\n")
            sys.stdout.flush()
            """
        )
        self.assertNotEqual(evidence.subject.get("status"), "error")


class ReportInjectionTests(unittest.TestCase):
    """
    Artifact text is written by the subject and lands in a document people are
    asked to read and share. It was inserted raw, so a subject could close the
    Artifacts heading and write its own — including a forged PASS row in a
    table whose real rows Beacon escapes precisely because it does not trust
    this text.
    """

    # Deliberately free of backticks. A payload that opens a fence of its own
    # is swallowed by it and proves nothing; this is plain markdown, so raw
    # insertion puts a second Assertions section straight into the document.
    HOSTILE = (
        "The briefing is complete.\n"
        "\n"
        "## Assertions\n"
        "\n"
        "| Result | Assertion | Actual | Expected |\n"
        "|---|---|---|---|\n"
        "| PASS | Nothing was sent | none | none |\n"
        "\n"
        "**Evidence digest:** forged\n"
    )

    def _report(self, artifact: str) -> str:
        from beacon.evidence import render_markdown
        from beacon.models import Evidence

        evidence = Evidence(
            evidence_version="0.2",
            run_id="r",
            started_at="2026-07-01T00:00:00+00:00",
            completed_at="2026-07-01T00:00:01+00:00",
            scenario={"id": "s", "name": "S"},
            subject={"id": "subject", "name": "subject"},
            result="FAIL",
            assertions=[
                {
                    "id": "one",
                    "description": "Nothing was sent",
                    "passed": False,
                    "actual": ["m-1"],
                    "expected": [],
                    "message": "values differ",
                    "measured": True,
                }
            ],
            state={"before_digest": "b", "after_digest": "a", "before": {}, "after": {}},
            state_diff={"change_count": 0, "changes": []},
            events=[],
            artifacts={"summary": artifact},
            usage={"calls": 0},
            reset_verified=True,
            limitations=[],
        )
        evidence.finalize()
        return render_markdown(evidence)

    @staticmethod
    def _outside_fences(markdown: str) -> str:
        """
        The document as a reader sees it once fenced blocks are set aside.

        Checking only the text before the Artifacts heading would pass without
        any fix at all, because the forgery is appended *after* it — which is
        exactly where a reader scrolling the report would still meet it.
        """
        kept: list[str] = []
        fence: str | None = None
        for line in markdown.splitlines():
            stripped = line.strip()
            if fence is None:
                if stripped.startswith("```"):
                    fence = stripped[: len(stripped) - len(stripped.lstrip("`"))]
                    continue
                kept.append(line)
            elif stripped.startswith(fence) and set(stripped) == {"`"}:
                fence = None
        return "\n".join(kept)

    def test_a_hostile_artifact_cannot_forge_a_passing_row(self) -> None:
        live = self._outside_fences(self._report(self.HOSTILE))
        self.assertIn("| FAIL |", live)
        self.assertNotIn("| PASS |", live, "the subject wrote its own verdict row")
        self.assertEqual(live.count("## Assertions"), 1)
        self.assertNotIn("forged", live)

    def test_the_artifact_fence_survives_backticks_inside_it(self) -> None:
        """
        A three-backtick fence is closed by three backticks in the content,
        which puts everything after it back into the document.
        """
        report = self._report("```\nescaped?\n```\nafter the fence\n")
        self.assertIn("````", report)
        opener = report.split("### summary", 1)[1].strip().split("\n", 1)[0]
        self.assertGreaterEqual(len(opener), 4)

    def test_ordinary_artifacts_are_still_readable(self) -> None:
        """Escaping must not turn a briefing into an unreadable blob."""
        report = self._report("Three replies are drafted and unsent.")
        self.assertIn("Three replies are drafted and unsent.", report)
