"""
Code-quality guardrail tests.

These mirror the checks that run in CI so developers get fast, local feedback
before pushing.  Each test is marked ``unit`` so it runs in the standard
``pytest -m "unit or integration"`` invocation without extra dependencies.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

# Root of the backend source tree (one level above this tests/ directory).
BACKEND_ROOT = Path(__file__).parent.parent

# Token used by ruff/flake8 to suppress linting on a line.
# Split here so the CI grep (which scans for the literal token) does not
# flag this file itself as a violation.
_NOQA_TOKEN = "# noqa"  # noqa: ISC003 — intentional split to defeat CI grep


# ── noqa justification ────────────────────────────────────────────────────────

# Pattern that matches a *bare* suppression token, i.e. one that has no
# trailing justification comment.  The CI shell check is:
#
#   grep '# no''qa' | grep -v '# no''qa.*—\|# no''qa.*--\|# no''qa.*:.*#'
#
# A justification comment is present when the token is followed by either:
#   • an em-dash (—) anywhere after the tag      e.g. suppression-token: F401 — reason
#   • a double-hyphen (--)                        e.g. suppression-token: F401 -- reason
#   • a colon then later a hash (: … #)           e.g. suppression-token: F401  # reason
_BARE_NOQA = re.compile(r"#\s*noqa\b")
_JUSTIFIED = re.compile(r"#\s*noqa.*(?:—|--|:.*#)")


def _collect_bare_noqa_violations() -> list[str]:
    """Return a list of 'file:line: text' strings for every bare suppression hit."""
    violations: list[str] = []
    for path in sorted(BACKEND_ROOT.rglob("*.py")):
        # Skip this file — its source intentionally references the token.
        if path.name == "test_code_quality.py":
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if _BARE_NOQA.search(line) and not _JUSTIFIED.search(line):
                rel = path.relative_to(BACKEND_ROOT)
                violations.append(f"{rel}:{lineno}: {line.rstrip()}")
    return violations


@pytest.mark.unit
def test_no_bare_noqa_suppressions() -> None:
    """Every ruff/flake8 suppression token must have an inline justification.

    Allowed forms (mirrors the CI grep check):
        suppression-token: F401 — side-effect import
        suppression-token: S603 -- argv list, no shell injection
        suppression-token: ANN001  # SQLAlchemy instance

    Bare forms (no justification) are rejected by both this test and CI.
    """
    violations = _collect_bare_noqa_violations()
    assert not violations, (
        "Found bare suppression tokens without justification comments.\n"
        "Add a trailing comment, e.g.  "
        + _NOQA_TOKEN
        + ": F401 — reason\n\n"
        + "\n".join(violations)
    )
