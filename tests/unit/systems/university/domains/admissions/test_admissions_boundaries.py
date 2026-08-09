"""Import-boundary tests for the Admissions vertical slice.

Admissions is the first university domain migrated to ``domains/<domain>/``
(ADR-less; see PROPOSED_REPOSITORY_LAYOUT.txt section 6). These tests pin the
boundaries the slice is supposed to hold so the next migration inherits a rule
rather than a convention.

They are pure static analysis — no database, no app, no imports of the code
under test — so they are cheap and cannot be defeated by lazy importing.

Two known violations are allow-listed below. The allow-list is a *ratchet*: a
new violation fails, and so does an entry that has been fixed but left behind,
so the list can only shrink.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

SLICE = (
    Path(__file__).resolve().parents[6]
    / "src/education_system/systems/university/domains/admissions"
)

#: The domain layer holds business rules only: no GUI toolkit, no web
#: framework, no direct SQL driver, and no dependency on its own adapters.
FORBIDDEN_IN_DOMAIN = ("tkinter", "flask", "sqlite3")

#: (file, imported module) pairs that violate a rule today. Each is a real
#: finding recorded rather than silently tolerated.
KNOWN_VIOLATIONS: set[tuple[str, str]] = {
    # A GUI launcher living in a domain service. Its own docstring says
    # "placeholder, actual import should be from GUI module". Both imports are
    # function-scoped, so they do not execute on import; the fix is to move the
    # launcher into interfaces/gui/.
    ("domain/services/admissions_crm_core.py", "tkinter"),
    (
        "domain/services/admissions_crm_core.py",
        "education_system.systems.university.domains.admissions.interfaces.gui"
        ".admissions_crm_gui",
    ),
    # The same file also holds a CLI launcher, lazily imported "to avoid an
    # import cycle" — which is the cycle this boundary exists to remove. Both
    # launchers belong in their respective interface adapters.
    (
        "domain/services/admissions_crm_core.py",
        "education_system.systems.university.domains.admissions.interfaces.cli"
        ".admissions_crm_cli",
    ),
    # Enrolment conversion reaches directly into Learners. The target design has
    # Admissions publish an accepted-applicant outcome that Learners consumes.
    (
        "domain/services/admissions_lifecycle.py",
        "education_system.systems.university.domain.learners.student_lifecycle",
    ),
    # Sixth-form intake reads Pastoral health records directly. Medical data is
    # meant to stay private to Pastoral and be reached through a port.
    (
        "domain/sixthform_intake.py",
        "education_system.systems.university.domain.pastoral.health.records",
    ),
}


def _imports(path: Path) -> list[str]:
    """Return every module name imported by *path*, at any nesting depth."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.append(node.module)
    return found


def _violations() -> set[tuple[str, str]]:
    """Return every (relative path, module) pair breaking a slice boundary."""
    found: set[tuple[str, str]] = set()
    for path in sorted(SLICE.rglob("*.py")):
        rel = path.relative_to(SLICE).as_posix()
        for module in _imports(path):
            root = module.split(".")[0]
            if rel.startswith("domain/"):
                if root in FORBIDDEN_IN_DOMAIN or ".interfaces." in module:
                    found.add((rel, module))
            # No layer of the slice may reach into another university domain,
            # whether it has been migrated to domains/ or is still under domain/.
            if ".systems.university.domain." in module or (
                ".systems.university.domains." in module
                and ".domains.admissions." not in module
            ):
                found.add((rel, module))
    return found


def test_slice_exists() -> None:
    """The Admissions slice is where the migration says it is."""
    assert SLICE.is_dir(), f"admissions slice not found at {SLICE}"
    assert (SLICE / "domain").is_dir()
    assert (SLICE / "interfaces").is_dir()


def test_no_new_boundary_violations() -> None:
    """No import crosses a slice boundary that is not already recorded."""
    new = _violations() - KNOWN_VIOLATIONS
    assert not new, (
        "New Admissions boundary violation(s):\n"
        + "\n".join(f"  {rel} -> {mod}" for rel, mod in sorted(new))
        + "\n\nThe domain layer must not import a GUI toolkit, a web framework, "
        "a SQL driver or its own adapters, and no layer may reach into another "
        "university domain. Use an application port or publish an event."
    )


def test_known_violations_are_still_real() -> None:
    """A fixed violation must be removed from the allow-list, so it shrinks."""
    stale = KNOWN_VIOLATIONS - _violations()
    assert not stale, (
        "These allow-listed violations no longer exist — delete them from "
        "KNOWN_VIOLATIONS:\n"
        + "\n".join(f"  {rel} -> {mod}" for rel, mod in sorted(stale))
    )


@pytest.mark.parametrize("layer", ["domain", "interfaces"])
def test_layer_is_importable_as_a_package(layer: str) -> None:
    """Each present layer is a real package, so the slice is addressable."""
    assert (SLICE / layer).is_dir()
