"""No education system imports another — all seven, every direction.

They reach each other only through the platform adapter registry
(``route_support.adapter_for`` / ``registry.load``). A direct import —
``from``/``import`` at module level or deferred inside a function — makes
one system fail when the other is missing and lets one write the other's
tables. Zero is the only allowed count.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

SYSTEMS = Path(__file__).resolve().parents[3] / "src" / "education_system" / "systems"

ALL_SYSTEMS = ("nursery", "primary", "secondary", "sixth_form", "fe_college",
               "apprenticeships", "university")

# Any import statement naming the other system's package, plus the
# importlib.import_module("education_system.systems.<x>...") spelling.
_PATTERN = {
    name: re.compile(
        rf"^\s*(?:from|import)\s+education_system\.systems\.{name}\b"
        rf"|import_module\(\s*[\"']education_system\.systems\.{name}\b",
        re.MULTILINE)
    for name in ALL_SYSTEMS
}


def _offenders(source: str, target: str) -> list[str]:
    out = []
    for path in sorted((SYSTEMS / source).rglob("*.py")):
        text = path.read_text(encoding="utf-8", errors="replace")
        for m in _PATTERN[target].finditer(text):
            line = text.count("\n", 0, m.start()) + 1
            out.append(f"{path.relative_to(SYSTEMS)}:{line}")
    return out


@pytest.mark.parametrize("source, target", [(s, t) for s in ALL_SYSTEMS
                                            for t in ALL_SYSTEMS if s != t])
def test_no_direct_imports(source, target):
    assert (SYSTEMS / source).is_dir()
    offenders = _offenders(source, target)
    assert offenders == [], (
        f"{source} imports {target} directly — go through "
        f"route_support.adapter_for({target!r}) instead:\n" + "\n".join(offenders))
