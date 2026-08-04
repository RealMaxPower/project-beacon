from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from beacon.models import Evidence


def write_evidence(evidence: Evidence, run_dir: Path) -> tuple[Path, Path]:
    json_path = run_dir / "evidence.json"
    markdown_path = run_dir / "report.md"
    json_path.write_text(
        json.dumps(evidence.to_dict(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(render_markdown(evidence), encoding="utf-8")
    return json_path, markdown_path


def _fenced(content: Any) -> str:
    """
    An artifact in a code fence long enough to survive its own contents.

    Artifact text is written by the subject, and it was previously dropped into
    the report raw. So a subject could close a heading, forge a PASS row in the
    assertion table, or end the document — in the artifact people are asked to
    read and share. The assertion table already escaped for this reason; the
    artifact section did not.

    A fence is used rather than escaping because an artifact is often JSON or
    prose that should stay readable. The fence is one backtick longer than the
    longest run inside the content, which is the rule CommonMark defines for
    exactly this, so no content can terminate it early.
    """
    text = (
        json.dumps(content, ensure_ascii=False, indent=2, sort_keys=True)
        if isinstance(content, (dict, list))
        else str(content)
    )
    longest = max((len(run) for run in re.findall(r"`+", text)), default=0)
    fence = "`" * max(3, longest + 1)
    return f"{fence}\n{text}\n{fence}"


def _code_span(value: Any) -> str:
    """
    A name in a code span long enough to survive its own contents.

    `_fenced` for a single line. An artifact's *name* is chosen by the subject
    just as its content is, and the heading above the fence interpolated that
    name raw — so a subject could end the heading and write its own verdict
    heading, its own passing assertion row, or its own evidence digest into the
    document people are asked to read and share. Escaping a list of characters
    is not enough here: a heading has no code fence around it, so raw HTML in a
    name (`<h2>`, `<table>`) renders as structure in GitHub's viewer and in a
    browser. A code span takes the name out of inline parsing entirely, so
    markup, HTML, links and images inside it are text.

    The span is one backtick longer than the longest run inside the name, which
    is the rule CommonMark defines for exactly this, so no name can terminate
    it early. Line endings become spaces because an ATX heading ends at the
    first one — and a padding space is added where CommonMark would otherwise
    read the name's own leading or trailing backtick as part of the delimiter.
    """
    text = re.sub(r"\r\n|[\r\n]", " ", str(value))
    longest = max((len(run) for run in re.findall(r"`+", text)), default=0)
    ticks = "`" * (longest + 1)
    padded = (
        not text
        or text.startswith("`")
        or text.endswith("`")
        or (text.startswith(" ") and text.endswith(" ") and text.strip(" ") != "")
    )
    pad = " " if padded else ""
    return f"{ticks}{pad}{text}{pad}{ticks}"


def _display(value: Any) -> str:
    if isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    else:
        text = str(value)
    text = text.replace("`", "\\`").replace("|", "\\|").replace("\n", "<br>")
    if len(text) > 280:
        text = text[:277] + "..."
    return f"`{text}`"


def render_markdown(evidence: Evidence) -> str:
    passed = sum(1 for item in evidence.assertions if item["passed"])
    lines = [
        f"# Beacon evidence: {evidence.result}",
        "",
        f"- **Run:** `{evidence.run_id}`",
        f"- **Scenario:** {evidence.scenario['name']} (`{evidence.scenario['id']}`)",
        f"- **Subject:** {evidence.subject.get('name', evidence.subject.get('id'))}",
        f"- **Integration:** {evidence.subject.get('adapter', 'unknown')} "
        f"(level {evidence.subject.get('integration_level', 'unknown')})",
        f"- **Assertions:** {passed}/{len(evidence.assertions)} passed",
        f"- **Reset verified:** {'yes' if evidence.reset_verified else 'no'}",
        f"- **Evidence digest:** `{evidence.digest}`",
        "",
        "## Assertions",
        "",
        "| Result | Assertion | Actual | Expected |",
        "|---|---|---|---|",
    ]
    for assertion in evidence.assertions:
        # "NOT MEASURED" rather than "FAIL": Beacon could not read what this
        # assertion asks about, so it has no finding, and printing one would
        # attribute to the subject a result nothing established.
        if not assertion.get("measured", True):
            marker = "NOT MEASURED"
            actual = _display(assertion.get("message", ""))
        else:
            marker = "PASS" if assertion["passed"] else "FAIL"
            actual = _display(assertion["actual"])
        lines.append(
            f"| {marker} | {assertion['description']} | "
            f"{actual} | {_display(assertion['expected'])} |"
        )

    lines.extend(
        [
            "",
            "## State changes",
            "",
        ]
    )
    changes = evidence.state_diff.get("changes", [])
    if changes:
        for change in changes:
            lines.append(
                f"- `{change['path']}`: {_display(change['before'])} → "
                f"{_display(change['after'])}"
            )
    else:
        lines.append("- No state changes.")

    lines.extend(["", "## Artifacts", ""])
    if evidence.artifacts:
        for name, content in evidence.artifacts.items():
            lines.extend([f"### {_code_span(name)}", "", _fenced(content), ""])
    else:
        lines.append("- No artifacts.")

    lines.extend(["", "## Limitations", ""])
    for limitation in evidence.limitations:
        lines.append(f"- {limitation}")
    lines.append("")
    return "\n".join(lines)
