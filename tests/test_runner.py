from __future__ import annotations

import copy
import json
import re
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


class DeepStructureTests(unittest.TestCase):
    """
    A subject acts first and reports afterwards, so anything that kills Beacon
    between those two points erases the record of what it just did.

    `json.loads` accepts nesting that `dataclasses.asdict` cannot walk — the C
    decoder spends less stack per level than the Python walk does — so a
    subject could delete documents, then send one deeply nested artifact and
    leave an empty run directory behind.
    """

    # Comfortably past the ~1200 levels where asdict gives out, and still
    # parsed without complaint by the decoder that accepts it.
    DEPTH = 1500

    def _agent(self, payload_expr: str) -> str:
        return textwrap.dedent(
            f"""
            import json, sys
            json.loads(sys.stdin.readline())
            def send(v):
                sys.stdout.write(json.dumps(v) + "\\n"); sys.stdout.flush()
            nested = "floor"
            for _ in range({self.DEPTH}):
                nested = {{"n": nested}}
            {payload_expr}
            send({{"type": "complete", "status": "completed", "summary": "done"}})
            """
        )

    def _run(self, script: str, run_id: str):
        with tempfile.TemporaryDirectory() as directory:
            agent = Path(directory) / "agent.py"
            agent.write_text(script, encoding="utf-8")
            outcome = run_scenario(
                Scenario.load(SCENARIO),
                JSONLCommandAdapter([sys.executable, str(agent)], timeout_seconds=30),
                output_dir=directory,
                run_id=run_id,
            )
            run_dir = outcome.json_path.parent
            return outcome.evidence, {
                name: (run_dir / name).exists()
                for name in ("evidence.json", "report.md", "events.json")
            }

    def test_a_deeply_nested_artifact_still_produces_a_bundle(self) -> None:
        evidence, written = self._run(
            self._agent(
                'send({"type": "artifact", "name": "summary", "content": nested})'
            ),
            "deep-artifact",
        )
        self.assertTrue(all(written.values()), f"bundle incomplete: {written}")
        self.assertIn("summary", evidence.artifacts)

    def test_the_truncation_is_admitted_in_the_limitations(self) -> None:
        """Silently shortening the subject's own output would be a lie."""
        evidence, _ = self._run(
            self._agent(
                'send({"type": "artifact", "name": "summary", "content": nested})'
            ),
            "deep-artifact-limits",
        )
        self.assertTrue(
            any("nested too deeply" in item for item in evidence.limitations),
            evidence.limitations,
        )
        self.assertIn("truncated by Beacon", json.dumps(evidence.artifacts))

    def test_deeply_nested_completion_metadata_still_produces_a_bundle(self) -> None:
        """The same structure reaches `asdict` through SubjectResult.metadata."""
        script = textwrap.dedent(
            f"""
            import json, sys
            json.loads(sys.stdin.readline())
            def send(v):
                sys.stdout.write(json.dumps(v) + "\\n"); sys.stdout.flush()
            nested = "floor"
            for _ in range({self.DEPTH}):
                nested = {{"n": nested}}
            send({{"type": "complete", "status": "completed",
                  "summary": "done", "metadata": {{"deep": nested}}}})
            """
        )
        _, written = self._run(script, "deep-metadata")
        self.assertTrue(all(written.values()), f"bundle incomplete: {written}")

    def test_deeply_nested_tool_arguments_still_produce_a_bundle(self) -> None:
        """Every recorded event payload is the subject's structure, not just artifacts."""
        script = textwrap.dedent(
            f"""
            import json, sys
            json.loads(sys.stdin.readline())
            def send(v):
                sys.stdout.write(json.dumps(v) + "\\n"); sys.stdout.flush()
            nested = "floor"
            for _ in range({self.DEPTH}):
                nested = {{"n": nested}}
            send({{"type": "tool_call", "id": "1", "tool": "mail_list",
                  "arguments": {{"deep": nested}}}})
            json.loads(sys.stdin.readline())
            send({{"type": "complete", "status": "completed", "summary": "done"}})
            """
        )
        _, written = self._run(script, "deep-tool-args")
        self.assertTrue(all(written.values()), f"bundle incomplete: {written}")


class ReportInjectionTests(unittest.TestCase):
    """
    Artifact text is written by the subject and lands in a document people are
    asked to read and share. It was inserted raw, so a subject could close the
    Artifacts heading and write its own — including a forged PASS row in a
    table whose real rows Beacon escapes precisely because it does not trust
    this text.

    An artifact's *name* is written by the subject too — a JSONL subject sends
    it, and a remote A2A agent names its own artifacts — and it lands in the
    heading above the fence, where fencing the content protects nothing.
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

    # The same forgery in HTML, which needs no line ending at all: markdown
    # renderers and GitHub's sanitiser both keep h1-h6 and tables, so escaping
    # the markdown characters and leaving `<` alone still ships the forgery.
    HOSTILE_HTML = (
        "brief<h2>Assertions</h2>"
        "<table><tr><td>PASS</td><td>forgedhtml</td></tr></table>"
    )

    def _report(self, artifact: str, name: str = "summary") -> str:
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
            artifacts={name: artifact},
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

    @classmethod
    def _outside_code(cls, markdown: str) -> str:
        """
        The document as a renderer parses it: no fence, and no code span.

        Text inside a code span is not markdown and not HTML — a renderer
        escapes it — so a forgery is only a forgery if it survives out here.
        Spans are matched the way CommonMark matches them: a run of backticks
        is closed by the next run of the same length, and a run with no such
        partner is literal text and stays.
        """
        kept: list[str] = []
        for line in cls._outside_fences(markdown).split("\n"):
            index = 0
            while (opener := re.search(r"`+", line[index:])) is not None:
                start, end = index + opener.start(), index + opener.end()
                kept.append(line[index:start])
                width = end - start
                closer = next(
                    (
                        run
                        for run in re.finditer(r"`+", line[end:])
                        if run.end() - run.start() == width
                    ),
                    None,
                )
                if closer is None:
                    kept.append(line[start:end])
                    index = end
                else:
                    index = end + closer.end()
            kept.append(line[index:] + "\n")
        return "".join(kept)

    def _artifact_heading(self, report: str) -> str:
        headings = [line for line in report.splitlines() if line.startswith("### ")]
        self.assertEqual(len(headings), 1, "the artifact heading is not one line")
        return headings[0]

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
        opener = report.split("### `summary`", 1)[1].strip().split("\n", 1)[0]
        self.assertGreaterEqual(len(opener), 4)

    def test_ordinary_artifacts_are_still_readable(self) -> None:
        """Escaping must not turn a briefing into an unreadable blob."""
        report = self._report("Three replies are drafted and unsent.")
        self.assertIn("Three replies are drafted and unsent.", report)

    def test_a_hostile_artifact_name_cannot_forge_a_passing_row(self) -> None:
        """
        The same forgery as above, through the field beside it. Fencing the
        content while interpolating the name raw moves the hole, it does not
        close it: the heading is the last raw thing the subject writes.
        """
        report = self._report("The briefing is complete.", name=self.HOSTILE)
        live = self._outside_code(report)
        self.assertIn("| FAIL |", live)
        self.assertNotIn("| PASS |", live, "the subject wrote its own verdict row")
        self.assertEqual(live.count("## Assertions"), 1)
        self.assertNotIn("forged", live)
        self.assertIn("| PASS |", report, "the name is dropped, not neutralised")

    def test_a_hostile_artifact_name_cannot_open_html(self) -> None:
        """
        A heading has no fence around it, so escaping markdown's own
        characters is not enough: `<h2>` and `<table>` need no line ending,
        and both markdown renderers and GitHub's sanitiser keep them.
        """
        report = self._report("The briefing is complete.", name=self.HOSTILE_HTML)
        live = self._outside_code(report)
        self.assertNotIn("<", live, "raw HTML from the subject reaches the reader")
        self.assertNotIn("PASS", live, "the subject wrote its own verdict cell")
        self.assertNotIn("forgedhtml", live)
        self.assertEqual(live.count("## Assertions"), 1)
        self.assertIn("<h2>", report, "the name is dropped, not neutralised")

    def test_a_name_with_line_endings_stays_on_one_heading(self) -> None:
        """
        LF, CR and CRLF all end an ATX heading. CR is the one a character
        escape list forgets, because Python's own line handling hides it.
        """
        for ending in ("\n", "\r", "\r\n"):
            with self.subTest(ending=repr(ending)):
                name = f"brief{ending}## Assertions{ending}| PASS | forged |"
                report = self._report("The briefing is complete.", name=name)
                live = self._outside_code(report)
                self.assertEqual(live.count("## Assertions"), 1)
                self.assertNotIn("| PASS |", live)
                self.assertNotIn("forged", live)
                self.assertNotIn("\r", report)
                self.assertIn("brief", self._artifact_heading(report))

    def test_an_ordinary_artifact_name_is_still_its_name(self) -> None:
        """A name a real subject sends must still read as that name."""
        ordinary = (
            "index",
            "summary.json",
            "rapport-été.md",
            "my report v2 (final).md",
        )
        for name in ordinary:
            with self.subTest(name=name):
                report = self._report("Three replies are drafted.", name=name)
                self.assertEqual(self._artifact_heading(report), f"### `{name}`")
                self.assertIn(name, report)
