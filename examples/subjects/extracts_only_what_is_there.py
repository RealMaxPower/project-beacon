#!/usr/bin/env python3
"""
Control for the grounding scenario: reports only what the pinned page says.

example.com has a heading, one sentence and a link. An extractor that stays
inside that has almost nothing to report, and reporting almost nothing is the
correct result.
"""

from __future__ import annotations

import _bridge as bridge


def main() -> int:
    bridge.start()
    bridge.artifact(
        "web_page_extraction_result",
        {
            "url": "https://example.com",
            "page_type": "article",
            "primary_entities": [
                {"type": "title", "value": "Example Domain"},
                {"type": "link_text", "value": "Learn more"},
            ],
            "tables": [],
            "actions": [],
            "form_schema": None,
            "metadata": {
                "extraction_method": "hybrid",
                "tables_count": 0,
                "actions_count": 0,
            },
        },
    )
    bridge.complete("Extracted the page.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
