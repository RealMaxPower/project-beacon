from __future__ import annotations

from typing import Any


def state_diff(before: Any, after: Any, path: str = "") -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []
    if type(before) is not type(after):
        return [{"path": path or "$", "before": before, "after": after}]

    if isinstance(before, dict):
        keys = sorted(set(before) | set(after))
        for key in keys:
            child = f"{path}.{key}" if path else key
            if key not in before:
                changes.append({"path": child, "before": None, "after": after[key]})
            elif key not in after:
                changes.append({"path": child, "before": before[key], "after": None})
            else:
                changes.extend(state_diff(before[key], after[key], child))
        return changes

    if isinstance(before, list):
        if before != after:
            changes.append({"path": path or "$", "before": before, "after": after})
        return changes

    if before != after:
        changes.append({"path": path or "$", "before": before, "after": after})
    return changes

