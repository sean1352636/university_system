"""Import-boundary tests for the Progression vertical slice.

The rules live in ``tests/unit/systems/university/domains/conftest.py``; this
module supplies only what Progression currently violates. The allow-list is a
ratchet — see ``_assert_ratchet`` — so it can only shrink.
"""

from __future__ import annotations

SLICE = "progression"

_UNI = "education_system.systems.university"
_APL = (
    f"{_UNI}.domains.admissions.domain.prior_learning_recognition"
    ".services.prior_learning_service"
)

KNOWN_VIOLATIONS: set[tuple[str, str]] = {
    # Four domain modules ask Admissions directly for recognition of prior
    # learning, to credit it against an apprenticeship or placement. Assessment
    # reaches into the same service from its own slice — so this is one shared
    # need, and the strongest candidate in the university for a published query
    # port on Admissions rather than four private imports.
    ("domain/apprenticeships/apprenticeship_service.py", _APL),
    ("domain/apprenticeships/apprenticeship_system.py", _APL),
    ("domain/placements/placement_service.py", _APL),
    ("domain/placements/placement_tracker.py", _APL),
    # Direct SQL driver in the domain layer; these predate the repository and
    # unit-of-work pattern the modernised core uses.
    ("domain/apprenticeships/apprenticeship_service.py", "sqlite3"),
    ("domain/apprenticeships/apprenticeship_system.py", "sqlite3"),
    ("domain/placements/placement_tracker.py", "sqlite3"),
    # Three domain modules are really standalone Tk applications. They belong in
    # interfaces/gui/, which is where the rest of this slice's UI already lives.
    ("domain/apprenticeships/apprenticeship_system.py", "tkinter"),
    ("domain/employer_portal/employer_portal_app.py", "tkinter"),
    ("domain/placements/placement_tracker.py", "tkinter"),
    # Domain modules importing this slice's own adapters — the dependency points
    # outward. Same shape as the Finance and Admissions launchers.
    (
        "domain/employer_portal/employer_portal_app.py",
        f"{_UNI}.domains.progression.interfaces.gui.employer_portal.employer_portal_gui",
    ),
    (
        "domain/portfolio/__init__.py",
        f"{_UNI}.domains.progression.interfaces.cli.portfolio.portfolio_cli",
    ),
}


def test_slice_is_in_place(slice_violations) -> None:
    """The slice exists where the migration says it does."""
    slice_violations(SLICE)  # asserts the directory is there


def test_boundary_ratchet(assert_slice_ratchet) -> None:
    """No new boundary violation, and no stale allow-list entry."""
    assert_slice_ratchet(SLICE, KNOWN_VIOLATIONS)
