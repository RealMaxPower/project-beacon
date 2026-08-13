from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stdout
from typing import Any
from unittest import mock

import beacon.adapters as adapters_module
from beacon.cli import ADAPTERS, RUN_ADAPTERS, _adapters, adapter_rows, build_parser


# Every adapter exported from `beacon.adapters` has to be reachable from the
# command line. Nothing is exempt today, and this set is deliberately empty
# rather than absent: an exemption is a decision somebody has to write down and
# defend in review, not a line quietly added to a filter.
#
# Modelled on HARNESS_ASSERTIONS in test_falsifiability.py, including its
# warning — widening an exemption list is how a guarantee becomes a formality.
UNREACHABLE_BY_DESIGN: frozenset[str] = frozenset()


def _is_subject_adapter(value: Any) -> bool:
    """
    A class that can be a subject: it describes itself and it runs.

    `SubjectAdapter` itself matches that shape and is excluded, because it is
    the contract rather than an implementation of it — there is nothing for
    the CLI to reach. It is filtered here instead of exempted below so that
    the exemption list stays a record of adapters we chose not to expose.
    """
    return (
        isinstance(value, type)
        and not getattr(value, "_is_protocol", False)
        and isinstance(getattr(value, "descriptor", None), property)
        and callable(getattr(value, "execute", None))
    )


class ReachabilityTests(unittest.TestCase):
    """
    The listing, the `--adapter` choices and the dispatch used to be three
    hand-written lists, and they drifted apart in both directions at once.

    `MCPToolSubjectAdapter` was complete, exported, and used for a 29-agent
    survey, but appeared in none of the three — so the only way to reach it
    was to write Python, and the README carried a paragraph apologising for
    that. Meanwhile the listing advertised three ids that were never
    `--adapter` values, so a reader following it got `invalid choice`.

    Prose could not catch either. These tests can.
    """

    def test_every_exported_subject_adapter_is_reachable_from_the_cli(self) -> None:
        exported = {
            name
            for name in adapters_module.__all__
            if _is_subject_adapter(getattr(adapters_module, name))
        }
        self.assertTrue(exported, "no adapters found; the detection is wrong")
        reachable = {
            spec.probe().__class__.__name__ for spec in ADAPTERS if spec.probe
        }
        missing = exported - reachable - UNREACHABLE_BY_DESIGN
        self.assertEqual(
            missing,
            set(),
            f"exported from beacon.adapters but unreachable from the CLI: "
            f"{sorted(missing)}",
        )

    def test_the_adapter_choices_are_exactly_the_run_rows(self) -> None:
        action = next(
            item
            for item in build_parser()._subparsers._group_actions[0]
            .choices["run"]
            ._actions
            if item.dest == "adapter"
        )
        self.assertEqual(
            sorted(action.choices), sorted(spec.flag for spec in RUN_ADAPTERS)
        )

    def test_every_row_says_how_it_is_reached_and_the_route_exists(self) -> None:
        """
        The bug a reader actually hit. `mcp-stdio` and `a2a-http` are real
        capabilities but they are not `--adapter` values, and the listing gave
        no way to tell.
        """
        parser = build_parser()
        subcommands = parser._subparsers._group_actions[0].choices
        run_choices = set(
            next(
                item for item in subcommands["run"]._actions if item.dest == "adapter"
            ).choices
        )
        for row in adapter_rows():
            with self.subTest(adapter=row["id"]):
                reached = row["reached_by"]
                if reached.startswith("beacon run "):
                    self.assertIn(row["id"], run_choices)
                else:
                    self.assertIn(reached.split()[1], subcommands)

    def test_the_integration_level_is_read_from_the_adapter_not_retyped(self) -> None:
        """A level bumped in the adapter and not in the CLI is a wrong claim."""
        for spec in ADAPTERS:
            if spec.probe is None:
                continue
            with self.subTest(adapter=spec.flag):
                row = next(r for r in adapter_rows() if r["id"] == spec.flag)
                descriptor = spec.probe().descriptor
                self.assertEqual(row["level"], descriptor["integration_level"])
                self.assertEqual(row["subject_id"], descriptor["id"])

    def test_a_client_row_still_declares_a_level(self) -> None:
        for spec in ADAPTERS:
            if spec.probe is None:
                with self.subTest(adapter=spec.flag):
                    self.assertIsNotNone(spec.level)

    def test_building_a_probe_adapter_starts_nothing(self) -> None:
        """
        The listing constructs an adapter purely to read its descriptor, so
        every `__init__` has to stay free of I/O. If one starts opening
        sockets or spawning processes, `project-beacon adapters` becomes a command
        that reaches out to the network to print a table.
        """
        def explode(*_args: Any, **_kwargs: Any) -> Any:
            raise AssertionError("constructing an adapter touched the outside world")

        with (
            mock.patch("subprocess.Popen", explode),
            mock.patch("urllib.request.urlopen", explode),
            mock.patch("socket.socket", explode),
        ):
            for spec in ADAPTERS:
                if spec.probe is None:
                    continue
                with self.subTest(adapter=spec.flag):
                    spec.probe().descriptor

    def test_the_listing_is_valid_json_and_every_row_is_complete(self) -> None:
        stream = io.StringIO()
        with redirect_stdout(stream):
            self.assertEqual(_adapters(), 0)
        rows = json.loads(stream.getvalue())
        self.assertEqual([row["id"] for row in rows], [s.flag for s in ADAPTERS])
        for row in rows:
            with self.subTest(adapter=row["id"]):
                for key in ("id", "subject", "interface", "reached_by", "status"):
                    self.assertTrue(row[key], f"{key} is empty")
                self.assertIsInstance(row["level"], int)

    def test_the_flags_are_unique(self) -> None:
        flags = [spec.flag for spec in ADAPTERS]
        self.assertEqual(len(flags), len(set(flags)))


if __name__ == "__main__":
    unittest.main()
