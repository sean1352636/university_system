"""Shared boundary analysis for the sixth form vertical slices.

The sixth form is being decomposed one business area at a time into
``systems/sixth_form/domains/<area>/{domain,infrastructure,interfaces/{gui,cli}}``,
mirroring the university's slices. Every migrated slice gets a test module that
pins its boundaries; the *rules* live here so there is one definition rather
than one per slice. Modelled on
``tests/unit/systems/university/domains/conftest.py``, whose rules are tied to
the university's package names.

The analysis is pure static AST inspection — no database, no app, and it never
imports the code under test, so a lazily-imported violation cannot hide from it.

Exposed as fixtures rather than plain helpers because pytest does not make
conftest symbols importable by test modules.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

#: tests/unit/systems/sixth_form/domains/conftest.py -> ... -> <repo root>
REPO_ROOT = Path(__file__).resolve().parents[5]
DOMAINS_ROOT = REPO_ROOT / "src/education_system/systems/sixth_form/domains"

#: The domain layer holds business rules only: no GUI toolkit, no web
#: framework, no direct SQL driver (the same list tools/check_layout.py applies
#: to the legacy ``sixth_form/domain/`` tree).
FORBIDDEN_IN_DOMAIN = ("tkinter", "flask", "sqlite3")

_SIXTH_FORM = "education_system.systems.sixth_form"

#: Sixth form modules any slice may use: the shared plumbing package.
_SHARED_PREFIXES = (f"{_SIXTH_FORM}.infrastructure",)

#: Shared UI helpers a slice's interfaces/ may use: private (``_``-prefixed)
#: modules sitting directly in the system-wide gui/ or cli/ package, such as
#: ``interfaces/gui/_ui.py``. Area helpers deeper down (``interfaces/gui/
#: operations/_ops_ui.py``) are another area's internals and do not qualify.
_SHARED_UI_PACKAGES = (f"{_SIXTH_FORM}.interfaces.gui", f"{_SIXTH_FORM}.interfaces.cli")


def _is_delivery_adapter(module: str) -> bool:
    """Is *module* an inbound adapter — any ``interfaces`` package, the API or
    ``platform.delivery``? Same test as tools/check_layout.py's ``_is_adapter``
    (the sixth form has no ``shell`` package)."""
    return (
        ".interfaces." in module
        or module.endswith(".interfaces")
        or module.startswith("education_system.api")
        or module.startswith("education_system.platform.delivery")
    )


def _within(module: str, prefix: str) -> bool:
    return module == prefix or module.startswith(prefix + ".")


def _is_allowed_sixth_form_import(module: str, slice_name: str) -> bool:
    """May slice *slice_name* import sixth form module *module*?"""
    if module == _SIXTH_FORM:  # the system package itself (SYSTEM_NAME, ...)
        return True
    if _within(module, f"{_SIXTH_FORM}.domains.{slice_name}"):
        return True
    if any(_within(module, p) for p in _SHARED_PREFIXES):
        return True
    package, _, leaf = module.rpartition(".")
    return package in _SHARED_UI_PACKAGES and leaf.startswith("_")


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
       ``interfaces/``, another area's, the API or ``platform.delivery``.
       Dependencies point inward, never out to a delivery layer.
    2. No layer of the slice may reach into another sixth form area, whether
       that area has already been migrated to ``domains/`` or is still under
       the legacy ``domain/`` / ``interfaces/<area>/`` trees. Allowed: the
       slice itself, ``sixth_form.infrastructure``, the ``sixth_form`` package
       and the shared ``interfaces/{gui,cli}/_*.py`` UI helpers.
    """
    root = DOMAINS_ROOT / slice_name
    assert root.is_dir(), f"no migrated slice at {root}"

    found: set[tuple[str, str]] = set()
    for path in sorted(root.rglob("*.py")):
        rel = path.relative_to(root).as_posix()
        for module in _imported_modules(path):
            top = module.split(".")[0]
            if rel.startswith("domain/"):
                if top in FORBIDDEN_IN_DOMAIN or _is_delivery_adapter(module):
                    found.add((rel, module))
            if (_within(module, _SIXTH_FORM)
                    and not _is_allowed_sixth_form_import(module, slice_name)):
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
        f"New sixth form {slice_name} boundary violation(s):\n"
        + "\n".join(f"  {rel} -> {mod}" for rel, mod in sorted(new))
        + "\n\nThe domain layer must not import a GUI toolkit, a web framework, "
        "a SQL driver or any adapter, and no layer may reach into another "
        "sixth form area. Use sixth_form.infrastructure or move the shared "
        "piece into the slice."
    )
    stale = known - actual
    assert not stale, (
        f"These allow-listed sixth form {slice_name} violations no longer "
        "exist — delete them from KNOWN_VIOLATIONS:\n"
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
