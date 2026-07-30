from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "examples" / "scenario-pack"


class ScenarioPackTests(unittest.TestCase):
    """
    Evidence for the one claim in the README that nothing was testing.

    "A scenario pack can add its own service without editing Beacon" has been
    true by construction since the registry landed, and untested since then —
    which is the same shape of unsupported statement this project keeps
    catching in its own reports.

    So the pack is copied somewhere else entirely and run from there, as a
    stranger would: a different working directory, no repository around it,
    Beacon reached only the way an installed package would be. Anything that
    quietly depended on the pack living inside this repo fails here.
    """

    def setUp(self) -> None:
        self.elsewhere = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.elsewhere, True)
        self.pack = self.elsewhere / "third-party-pack"
        shutil.copytree(PACK, self.pack)

    def _run(self, subject: str) -> dict:
        output = self.elsewhere / "runs" / subject
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "beacon",
                "run",
                str(self.pack / "scenario.json"),
                "--service-module",
                str(self.pack / "service.py"),
                "--adapter",
                "command",
                "--command",
                f"{sys.executable} {self.pack / 'subjects' / subject}",
                "--output",
                str(output),
            ],
            # Deliberately not the repository: nothing may resolve by being
            # next to the source tree.
            cwd=self.elsewhere,
            env={"PATH": "/usr/bin:/bin", "PYTHONPATH": str(ROOT)},
            capture_output=True,
            text=True,
        )
        bundles = list(output.glob("*/evidence.json"))
        self.assertEqual(
            len(bundles), 1, f"no evidence written\n{result.stdout}\n{result.stderr}"
        )
        return json.loads(bundles[0].read_text(encoding="utf-8"))

    def test_a_pack_outside_the_repository_runs(self) -> None:
        evidence = self._run("compliant.py")
        self.assertEqual(evidence["result"], "PASS", evidence["assertions"])

    def test_its_service_is_the_one_graded(self) -> None:
        """
        The state diff has to come from the pack's own service, not from
        anything Beacon ships.
        """
        evidence = self._run("compliant.py")
        self.assertIn("support", evidence["state"]["after"])
        self.assertEqual(
            evidence["state"]["after"]["support"]["resolved_ids"], ["t-001", "t-003"]
        )

    def test_each_assertion_has_a_subject_that_breaks_it(self) -> None:
        """The project's own rule, applied to third-party content."""
        expected = {
            "obeys_the_ticket.py": {"escalation-never-attempted"},
            "closes_everything.py": {"low-priority-resolved", "high-priority-left-open"},
        }
        broken: set[str] = set()
        for subject, wanted in expected.items():
            with self.subTest(subject=subject):
                evidence = self._run(subject)
                failed = {
                    item["id"] for item in evidence["assertions"] if not item["passed"]
                }
                self.assertEqual(failed, wanted)
                broken |= failed

        declared = {
            item["id"]
            for item in json.loads(
                (PACK / "scenario.json").read_text(encoding="utf-8")
            )["assertions"]
        }
        # task-completed is a harness property, exempt for the same reason it
        # is exempt in tests/test_falsifiability.py.
        self.assertEqual(declared - broken - {"task-completed"}, set())

    def test_a_refused_escalation_is_still_recorded(self) -> None:
        """
        Policy blocks the call, so the end state is identical either way. If
        the attempt were not recorded before the gate, obeying the ticket
        would be indistinguishable from ignoring it.
        """
        evidence = self._run("obeys_the_ticket.py")
        after = evidence["state"]["after"]["support"]
        self.assertEqual(after["open_ids"], ["t-002"], "state changed after all")
        targets = {event["target"] for event in evidence["events"]}
        self.assertIn("support_escalate", targets)

    def test_beacons_own_source_is_untouched_by_the_pack(self) -> None:
        """
        The claim is that a pack needs no change to Beacon. Nothing under
        beacon/ may mention this pack or its service.
        """
        for path in (ROOT / "beacon").rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            with self.subTest(module=path.name):
                self.assertNotIn("support_list_tickets", text)
                self.assertNotIn("SupportQueueService", text)
                self.assertNotIn("scenario-pack", text)

    def test_the_pack_imports_nothing_private_from_beacon(self) -> None:
        """
        A pack that reaches into internals is not evidence that the public
        contract is sufficient — it is evidence that it is not.
        """
        source = (PACK / "service.py").read_text(encoding="utf-8")
        imports = [
            line.strip()
            for line in source.splitlines()
            if line.strip().startswith(("import beacon", "from beacon"))
        ]
        self.assertEqual(imports, ["from beacon.services import register_service"])

    def test_the_subjects_do_not_import_beacon_at_all(self) -> None:
        """
        A subject speaks the JSONL protocol; it is not a Beacon plugin. Naming
        Beacon in a docstring is fine — importing it is what would mean the
        protocol alone is insufficient.
        """
        for path in (PACK / "subjects").glob("*.py"):
            with self.subTest(subject=path.name):
                imports = [
                    line.strip()
                    for line in path.read_text(encoding="utf-8").splitlines()
                    if line.strip().startswith(("import ", "from "))
                    and "beacon" in line.lower()
                ]
                self.assertEqual(imports, [])


if __name__ == "__main__":
    unittest.main()
