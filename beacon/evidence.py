from __future__ import annotations

import json
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
        marker = "PASS" if assertion["passed"] else "FAIL"
        lines.append(
            f"| {marker} | {assertion['description']} | "
            f"{_display(assertion['actual'])} | {_display(assertion['expected'])} |"
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
            lines.extend([f"### {name}", "", str(content), ""])
    else:
        lines.append("- No artifacts.")

    lines.extend(["", "## Limitations", ""])
    for limitation in evidence.limitations:
        lines.append(f"- {limitation}")
    lines.append("")
    return "\n".join(lines)
