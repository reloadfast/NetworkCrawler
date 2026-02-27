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


# ── noqa justification ────────────────────────────────────────────────────────

# Pattern that matches a *bare* ``# noqa`` suppression, i.e. one that has no
# trailing justification comment.  The CI shell check is:
#
#   grep '# noqa' | grep -v '# noqa.*—\|# noqa.*--\|# noqa.*:.*#'
#
# A justification comment is present when the noqa tag is followed by either:
#   • an em-dash (—) anywhere after the tag      e.g. # noqa: F401 — reason
#   • a double-hyphen (--)                        e.g. # noqa: F401 -- reason
#   • a colon then later a hash (: … #)           e.g. # noqa: F401  # reason
_BARE_NOQA = re.compile(r"#\s*noqa\b")
_JUSTIFIED = re.compile(r"#\s*noqa.*(?:—|--|:.*#)")


def _collect_bare_noqa_violations() -> list[str]:
    """Return a list of 'file:line: text' strings for every bare noqa hit."""
    violations: list[str] = []
    for path in sorted(BACKEND_ROOT.rglob("*.py")):
        # Skip this file — its docstrings intentionally contain noqa examples.
        if path.name == "test_code_quality.py":
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if _BARE_NOQA.search(line) and not _JUSTIFIED.search(line):
                rel = path.relative_to(BACKEND_ROOT)
                violations.append(f"{rel}:{lineno}: {line.rstrip()}")
    return violations


@pytest.mark.unit
def test_no_bare_noqa_suppressions() -> None:
    """Every ``# noqa`` must be followed by an inline justification comment.

    Allowed forms (mirrors the CI grep check):
        # noqa: F401 — side-effect import
        # noqa: S603 -- argv list, no shell injection
        # noqa: ANN001  # SQLAlchemy instance

    Bare forms that are rejected:
        # noqa
        # noqa: F401
    """
    violations = _collect_bare_noqa_violations()
    assert not violations, (
        "Found bare '# noqa' suppressions without justification comments.\n"
        "Add a trailing comment, e.g.  # noqa: F401 — reason\n\n" + "\n".join(violations)
    )
