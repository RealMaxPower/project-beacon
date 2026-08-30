from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stdout
from typing import Any
from unittest import mock

import beacon.adapters as adapters_module
from beacon.cli import ADAPTERS, RUN_ADAPTERS, _adapters, adapter_rows, build_parser
from beacon.commands.probe import mcp_inspect


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


class McpInspectTargetTests(unittest.TestCase):
    """
    `mcp-inspect` reaches a stdio server (--command) or a hosted
    Streamable-HTTP server (--url). Exactly one is required: neither leaves
    nothing to inspect, both is ambiguous. The mutually-exclusive group is the
    contract, and these pin it so a later edit cannot quietly make --command
    required again and re-strip hosted servers.
    """

    def _parse(self, argv: list[str]):
        return build_parser().parse_args(argv)

    def test_url_selects_the_http_target(self) -> None:
        args = self._parse(["mcp-inspect", "--url", "https://agent.example/mcp"])
        self.assertEqual(args.url, "https://agent.example/mcp")
        self.assertIsNone(args.command)

    def test_command_selects_the_stdio_target(self) -> None:
        args = self._parse(["mcp-inspect", "--command", "my-server --flag"])
        self.assertEqual(args.command, "my-server --flag")
        self.assertIsNone(args.url)

    def test_neither_target_is_rejected(self) -> None:
        with self.assertRaises(SystemExit):
            self._parse(["mcp-inspect"])

    def test_both_targets_are_rejected(self) -> None:
        with self.assertRaises(SystemExit):
            self._parse(
                ["mcp-inspect", "--command", "x", "--url", "https://agent.example/mcp"]
            )


class McpInspectHandlerTests(unittest.TestCase):
    """
    The parser tests above all stop at `parse_args`, so none of them reaches
    `mcp_inspect`. Nothing in the suite did, which is how a truthiness test on
    `args.url` got as far as review instead of going red here.

    No socket is opened by any of these: two patch the client out, and the
    third is refused before a client is built.
    """

    def _args(self, argv: list[str]) -> Any:
        return build_parser().parse_args(argv)

    def _client(self) -> Any:
        """A stand-in whose attributes survive `json.dumps`."""
        client = mock.MagicMock()
        entered = client.__enter__.return_value
        entered.protocol_version = "2025-06-18"
        entered.server_info = {"name": "fixture"}
        entered.capabilities = {}
        entered.list_tools.return_value = []
        return client

    def test_an_empty_url_is_refused_as_a_url_not_as_a_command(self) -> None:
        """
        `--url ""` is falsy. Under a truthiness test it fell through to the
        stdio branch, where `args.command` is None and `shlex.split(None)`
        answers — `ValueError: s argument must not be None` on 3.12+, naming an
        internal argument the caller never passed. Before 3.12 that call read
        from *stdin* instead of raising, so on 3.11 the command hung rather than
        failed. This repository supports 3.11 and CI runs it.

        The fix routes on which flag was given, so an empty URL is now judged
        as a URL, by the client that knows what one looks like.
        """
        with mock.patch("beacon.commands.probe.MCPStdioClient") as stdio:
            with self.assertRaises(ValueError) as caught:
                mcp_inspect(self._args(["mcp-inspect", "--url", ""]))
        stdio.assert_not_called()
        message = str(caught.exception)
        self.assertIn("http", message)
        self.assertNotIn("s argument", message)

    def test_a_url_binds_the_http_client_and_carries_the_credential(self) -> None:
        with mock.patch("beacon.commands.probe.MCPHTTPClient") as http:
            http.return_value = self._client()
            with redirect_stdout(io.StringIO()):
                code = mcp_inspect(
                    self._args(
                        [
                            "mcp-inspect",
                            "--url",
                            "https://agent.example/mcp",
                            "--authorization",
                            "Bearer fixture-token-DO-NOT-SHIP",
                            "--timeout",
                            "3",
                        ]
                    )
                )
        self.assertEqual(code, 0)
        http.assert_called_once_with(
            "https://agent.example/mcp",
            timeout_seconds=3.0,
            authorization="Bearer fixture-token-DO-NOT-SHIP",
        )

    def test_each_transport_keeps_its_own_timeout_when_none_is_given(self) -> None:
        """
        `--timeout` defaulted to 10 because this command only spoke stdio.
        `--url` inherited it, so a hosted server reached across the internet got
        half the 20s `MCPHTTPClient` asks for, while a local process that spawns
        in milliseconds got the larger share of the two.

        Unset now means "whatever this transport considers reasonable", which is
        checked by the client receiving no `timeout_seconds` at all rather than
        by asserting a number this test would have to keep in step.
        """
        with mock.patch("beacon.commands.probe.MCPHTTPClient") as http:
            http.return_value = self._client()
            with redirect_stdout(io.StringIO()):
                mcp_inspect(self._args(["mcp-inspect", "--url", "https://a.example/mcp"]))
        self.assertNotIn("timeout_seconds", http.call_args.kwargs)

        with mock.patch("beacon.commands.probe.MCPStdioClient") as stdio:
            stdio.return_value = self._client()
            with redirect_stdout(io.StringIO()):
                mcp_inspect(self._args(["mcp-inspect", "--command", "srv"]))
        self.assertNotIn("timeout_seconds", stdio.call_args.kwargs)

    def test_an_explicit_timeout_still_reaches_either_client(self) -> None:
        """The flag has to keep working, or the default has just been removed."""
        for flag, value, target in (
            ("--url", "https://a.example/mcp", "MCPHTTPClient"),
            ("--command", "srv", "MCPStdioClient"),
        ):
            with self.subTest(transport=flag):
                with mock.patch(f"beacon.commands.probe.{target}") as client:
                    client.return_value = self._client()
                    with redirect_stdout(io.StringIO()):
                        mcp_inspect(
                            self._args(
                                ["mcp-inspect", flag, value, "--timeout", "3"]
                            )
                        )
                self.assertEqual(client.call_args.kwargs["timeout_seconds"], 3.0)

    def test_a_command_still_binds_the_stdio_client(self) -> None:
        """The path that worked before must keep working, and unchanged."""
        with mock.patch("beacon.commands.probe.MCPStdioClient") as stdio:
            stdio.return_value = self._client()
            with redirect_stdout(io.StringIO()):
                code = mcp_inspect(
                    self._args(["mcp-inspect", "--command", "my-server --flag"])
                )
        self.assertEqual(code, 0)
        stdio.assert_called_once_with(["my-server", "--flag"])


if __name__ == "__main__":
    unittest.main()
