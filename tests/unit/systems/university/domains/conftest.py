"""Shared boundary analysis for the university vertical slices.

The university is being decomposed one business domain at a time into
``systems/university/domains/<domain>/`` (PROPOSED_REPOSITORY_LAYOUT.txt
section 6). Every migrated slice gets a test module that pins its boundaries;
the *rules* live here so there is one definition rather than one per slice.

The analysis is pure static AST inspection — no database, no app, and it never
imports the code under test, so a lazily-imported violation cannot hide from it.

Exposed as a fixture rather than a plain helper because pytest does not make
conftest symbols importable by test modules.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

#: tests/unit/systems/university/domains/conftest.py -> ... -> <repo root>
REPO_ROOT = Path(__file__).resolve().parents[5]
DOMAINS_ROOT = REPO_ROOT / "src/education_system/systems/university/domains"

#: The domain layer holds business rules only: no GUI toolkit, no web
#: framework, no direct SQL driver.
FORBIDDEN_IN_DOMAIN = ("tkinter", "flask", "sqlite3")

#: Use cases must not drive the user directly — opening a window or a browser
#: tab from an application service makes it unusable from the API or the CLI.
#: Narrower than FORBIDDEN_IN_DOMAIN on purpose: a service may legitimately talk
#: to a database, but never to a screen.
FORBIDDEN_IN_APPLICATION = ("tkinter", "webbrowser")

_UNIVERSITY = "education_system.systems.university"


def _is_delivery_adapter(module: str) -> bool:
    """Is *module* an inbound adapter — a slice's own interfaces, or the shell?

    University delivery code lives in two places: ``domains/<d>/interfaces/`` for
    a domain's own adapters, and the system-wide ``university/shell/`` for the
    launcher, menus, main window and cross-cutting routes. Matching only the
    first would silently stop detecting domain-to-shell imports, which is exactly
    what happened when the shell moved out of ``interfaces/{cli,gui}/shell/``.

    The shell test is anchored to the full university prefix on purpose: a bare
    ``".shell."`` also matches unrelated modules such as
    ``...church_management/ui/shell.py``.
    """
    return ".interfaces." in module or f"{_UNIVERSITY}.shell." in module


def _imported_modules(path: Path) -> list[str]:
    """Every module name imported by *path*, including inside functions."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.append(node.module)
    return found


def _violations(slice_name: str) -> set[tuple[str, str]]:
    """Return every ``(path relative to the slice, module)`` breaking a rule.

    Two rules are enforced:

    1. The slice's ``domain/`` layer may not import a GUI toolkit, a web
       framework, a SQL driver, or any inbound adapter — its own
       ``interfaces/`` or the system-wide ``shell/``. Dependencies point
       inward, never out to a delivery layer.
    2. The slice's ``application/`` layer may not drive the user directly: a use
       case that opens a window or a browser tab cannot be called from the API
       or the CLI.
    3. No layer of the slice may reach into another university domain, whether
       that domain has already been migrated to ``domains/`` or is still under
       the legacy ``domain/``. Cross-domain work goes through an application
       port or a published event.
    """
    root = DOMAINS_ROOT / slice_name
    assert root.is_dir(), f"no migrated slice at {root}"

    found: set[tuple[str, str]] = set()
    for path in sorted(root.rglob("*.py")):
        rel = path.relative_to(root).as_posix()
        for module in _imported_modules(path):
            # Not `root` — that name holds the slice directory in this scope.
            top = module.split(".")[0]
            if rel.startswith("domain/"):
                if top in FORBIDDEN_IN_DOMAIN or _is_delivery_adapter(module):
                    found.add((rel, module))
            if rel.startswith("application/") and top in FORBIDDEN_IN_APPLICATION:
                found.add((rel, module))
            reaches_legacy = f"{_UNIVERSITY}.domain." in module
            reaches_other_slice = (
                f"{_UNIVERSITY}.domains." in module
                and f".domains.{slice_name}." not in module
            )
            if reaches_legacy or reaches_other_slice:
                found.add((rel, module))
    return found


def _assert_ratchet(slice_name: str, known: set[tuple[str, str]]) -> None:
    """Compare the slice's real violations against its *known* allow-list.

    New violations fail. So do allow-listed entries that have since been fixed,
    so the list can only ever shrink.
    """
    actual = _violations(slice_name)
    new = actual - known
    assert not new, (
        f"New {slice_name} boundary violation(s):\n"
        + "\n".join(f"  {rel} -> {mod}" for rel, mod in sorted(new))
        + "\n\nThe domain layer must not import a GUI toolkit, a web framework, "
        "a SQL driver or its own adapters, and no layer may reach into another "
        "university domain. Use an application port or publish an event."
    )
    stale = known - actual
    assert not stale, (
        f"These allow-listed {slice_name} violations no longer exist — delete "
        "them from KNOWN_VIOLATIONS:\n"
        + "\n".join(f"  {rel} -> {mod}" for rel, mod in sorted(stale))
    )


@pytest.fixture(scope="session")
def slice_violations():
    """Return a callable ``(slice_name) -> set[(relative_path, module)]``."""
    return _violations


@pytest.fixture(scope="session")
def assert_slice_ratchet():
    """Return a callable ``(slice_name, known_violations) -> None``."""
    return _assert_ratchet
