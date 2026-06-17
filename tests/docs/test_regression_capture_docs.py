from __future__ import annotations

import re
from pathlib import Path

import pytest

_STALE_BOUNDED_SCAN_WORDING_PATTERNS = (
    re.compile(r"\bexplicitly bounded local/dev\b", re.IGNORECASE),
    re.compile(r"\bexplicitly classified\b", re.IGNORECASE),
    re.compile(r"\bexplicit classification\b", re.IGNORECASE),
    re.compile(r"\bexplicit local, relation-backed\b", re.IGNORECASE),
    re.compile(r"\bclassified as local, relation-backed\b", re.IGNORECASE),
    re.compile(r"\bbounded local relation-backed\b", re.IGNORECASE),
)


@pytest.mark.regression_capture("bounded-scan-docs-no-user-provided-classification")
def test_public_docs_do_not_reintroduce_user_provided_bounded_scan_classification() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    docs_paths = [
        repo_root / "README.md",
        repo_root / "CHANGELOG.md",
        *sorted((repo_root / "docs").rglob("*.md")),
    ]

    matches: list[str] = []
    for path in docs_paths:
        text = path.read_text(encoding="utf-8")
        for pattern in _STALE_BOUNDED_SCAN_WORDING_PATTERNS:
            if pattern.search(text):
                matches.append(f"{path.relative_to(repo_root)} matches {pattern.pattern}")

    assert matches == []
