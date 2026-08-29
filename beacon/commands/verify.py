from __future__ import annotations

"""`project-beacon verify` — recompute a bundle's digest."""

import json
import sys
from pathlib import Path

from beacon.models import Evidence, canonical_digest


def verify(path: Path) -> int:
    """
    Recompute a bundle's digest and say whether it still matches.

    Checked against the raw parsed document rather than against a round-trip
    through `Evidence`, because the digest was taken over what was published.
    Loading first would normalise types on the way in, and a verifier that
    silently repairs the thing it is checking is not a verifier.

    That also separates two failures a reader needs told apart: a bundle whose
    digest does not match has been edited, while a bundle this version cannot
    interpret is merely newer. The second is not tampering, and reporting it as
    tampering would be the false accusation this command exists to avoid.
    """
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        print(
            f"error: {path} is not an evidence bundle: expected a JSON object, "
            f"got {type(document).__name__}",
            file=sys.stderr,
        )
        return 2

    recorded = document.get("digest")
    if not isinstance(recorded, str) or not recorded:
        print(
            f"error: {path} carries no digest, so there is nothing to verify",
            file=sys.stderr,
        )
        return 2

    published = dict(document)
    published["digest"] = ""
    computed = canonical_digest(published)

    # Read after the digest check, never before: whether Beacon understands the
    # bundle is a separate question from whether the bundle is intact.
    try:
        Evidence.from_dict(document)
        readable = ""
    except ValueError as exc:
        readable = str(exc)

    if computed != recorded:
        print(f"MODIFIED: {path}", file=sys.stderr)
        print(f"  recorded: {recorded}", file=sys.stderr)
        print(f"  computed: {computed}", file=sys.stderr)
        print(
            "  The bundle does not match its own digest, so it changed after "
            "the run that produced it.",
            file=sys.stderr,
        )
        return 1

    print(f"VERIFIED: {path}")
    print(f"  digest: {recorded}")
    print(f"  run:    {document.get('run_id', '(unnamed)')}")
    print(f"  result: {document.get('result', '(none)')}")
    if readable:
        print(f"  note:   this version of Beacon cannot read the bundle: {readable}")
        print("          The digest still matches, so the file is intact.")
    # The thing a reader most needs told, since a matching digest invites the
    # opposite conclusion.
    print(
        "  The digest is an unsigned integrity check. It shows the bundle was "
        "not edited\n  after the run; it does not show which machine produced "
        "it, or that the run happened."
    )
    return 0
