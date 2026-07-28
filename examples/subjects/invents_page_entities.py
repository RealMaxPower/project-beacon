#!/usr/bin/env python3
"""
Returns a well-formed extraction of a page that does not exist.

Copied in spirit from a live agent, which invented an author, a date and a
product listing for a page containing none of them, on two runs in three. The
shape is impeccable — every field a consumer parses is present and correctly
typed — which is why the shape assertion passes here and only grounding
notices anything is wrong.
"""

from __future__ import annotations

import _bridge as bridge


def main() -> int:
    bridge.start()
    bridge.artifact(
        "web_page_extraction_result",
        {
            "url": "https://example.com",
            "page_type": "product-page",
            "primary_entities": [
                {"type": "product_name", "value": "Super Widget"},
                {"type": "product_id", "value": "SW-456"},
                {"type": "author", "value": "John Doe"},
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
