from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
VERCEL = SITE / "vercel.json"

#: Every property a header rule may carry. Vercel's schema declares
#: `additionalProperties: false` on these, so anything else fails the build
#: rather than being ignored.
HEADER_RULE_KEYS = {"source", "headers", "has", "missing"}


@unittest.skipUnless(SITE.is_dir(), "the site has not been built in this checkout")
class VercelConfigTests(unittest.TestCase):
    """
    The deploy config is valid before a deploy says so.

    A `"//"` key was added to a header rule to explain why the rule exists —
    the habit everywhere else in this repository, and the one thing this file
    cannot accept. Vercel's schema sets `additionalProperties: false`, so the
    production build failed on it. Nothing here checked the file, so the first
    thing to read it was the deploy.

    JSON has no comments. That is the whole reason this module exists: the
    explanation a change like that needs has to live in a test, where it is
    both readable and enforced, instead of in a key the schema will reject.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.config = json.loads(VERCEL.read_text(encoding="utf-8"))

    def test_it_is_json_with_rules_to_check(self) -> None:
        self.assertGreater(len(self.config.get("headers", [])), 0, "no header rules found")

    def test_no_rule_carries_a_property_the_schema_refuses(self) -> None:
        """
        The failure, stated exactly. A comment key is the likely one, but the
        check is the general rule rather than a ban on `//` — the schema
        refuses every unknown property, not that one.
        """
        for index, rule in enumerate(self.config["headers"]):
            with self.subTest(rule=index):
                self.assertEqual(
                    sorted(set(rule) - HEADER_RULE_KEYS),
                    [],
                    "Vercel sets additionalProperties:false on header rules, "
                    "so an extra key fails the build rather than being ignored",
                )

    def test_nothing_in_the_file_is_shaped_like_a_comment(self) -> None:
        """
        Belt and braces, at any depth. The rule above only covers header rules;
        the same instinct would put a `//` in a redirect or at the top level.
        """
        found: list[str] = []

        def walk(node: object, path: str) -> None:
            if isinstance(node, dict):
                for key, value in node.items():
                    if key.startswith(("//", "#", "_comment")):
                        found.append(f"{path}.{key}")
                    walk(value, f"{path}.{key}")
            elif isinstance(node, list):
                for i, value in enumerate(node):
                    walk(value, f"{path}[{i}]")

        walk(self.config, "$")
        self.assertEqual(found, [], f"JSON has no comments; these will fail the build: {found}")

    def test_the_noindex_is_scoped_to_the_deployment_alias(self) -> None:
        """
        The header that must never reach the real origin.

        Vercel serves byte-identical documents at `project-beacon-*.vercel.app`,
        canonicals and all, so the site was indexable at two origins with only a
        canonical hint holding them together. The fix is a `noindex` on the
        alias — and an unscoped one would remove the entire site from search,
        which is a mistake that stays silent for about a week.

        So the assertion is not that a noindex exists. It is that every noindex
        carries a host condition.
        """
        noindex = [
            rule
            for rule in self.config["headers"]
            if any(h["key"].lower() == "x-robots-tag" for h in rule.get("headers", []))
        ]
        self.assertEqual(len(noindex), 1, "expected exactly one X-Robots-Tag rule")

        for rule in noindex:
            conditions = rule.get("has", [])
            self.assertTrue(conditions, "an unscoped X-Robots-Tag would deindex beaconlab.dev")
            # The value is a regex, so its dots arrive escaped: `(.*)\.vercel\.app`.
            # Comparing against the literal host misses every correctly written
            # pattern, which is how the first version of this reported the fix
            # as the defect.
            hosts = [
                c.get("value", "").replace("\\", "")
                for c in conditions
                if c.get("type") == "host"
            ]
            self.assertTrue(
                any("vercel.app" in host for host in hosts),
                f"the noindex is not scoped to the deployment alias: {conditions}",
            )

    def test_the_real_origin_is_never_the_target_of_a_noindex(self) -> None:
        """The other direction, said plainly, because it is the expensive one."""
        for rule in self.config["headers"]:
            keys = {h["key"].lower() for h in rule.get("headers", [])}
            if "x-robots-tag" not in keys:
                continue
            for condition in rule.get("has", []):
                with self.subTest(condition=condition):
                    self.assertNotIn("beaconlab.dev", condition.get("value", ""))


if __name__ == "__main__":
    unittest.main()
