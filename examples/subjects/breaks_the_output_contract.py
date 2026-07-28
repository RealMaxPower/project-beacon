#!/usr/bin/env python3
"""
Renames a field and lets one count drift out of step with its list.

Two changes a real deployment ships without announcing: `url` becomes
`page_url`, and `tables_count` says three while `tables` is empty. Neither is
a hallucination — every value here appears on the page or is plainly derived —
so a grounding check sees nothing wrong. The contract assertions are what
notice.
"""

from __future__ import annotations

import _bridge as bridge


def main() -> int:
    bridge.start()
    bridge.artifact(
        "web_page_extraction_result",
        {
            "page_url": "https://example.com",
            "page_type": "article",
            "primary_entities": [{"type": "title", "value": "Example Domain"}],
            "tables": [],
            "actions": [],
            "form_schema": None,
            "metadata": {
                "extraction_method": "hybrid",
                "tables_count": 3,
                "actions_count": 0,
            },
        },
    )
    bridge.complete("Extracted the page.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
