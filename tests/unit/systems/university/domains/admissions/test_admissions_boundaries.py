"""Import-boundary tests for the Admissions vertical slice.

The rules live in ``tests/unit/systems/university/domains/conftest.py``; this
module supplies only what Admissions currently violates. The allow-list is a
ratchet — see ``_assert_ratchet`` — so it can only shrink.
"""

from __future__ import annotations

SLICE = "admissions"

#: Real findings, recorded rather than tolerated. Each is work left in this slice.
KNOWN_VIOLATIONS: set[tuple[str, str]] = {
    # A GUI launcher living in a domain service. Its own docstring says
    # "placeholder, actual import should be from GUI module".
    ("domain/services/admissions_crm_core.py", "tkinter"),
    (
        "domain/services/admissions_crm_core.py",
        "education_system.systems.university.domains.admissions.interfaces.gui"
        ".admissions_crm_gui",
    ),
    # The same file holds a CLI launcher, lazily imported "to avoid an import
    # cycle" — which is the cycle this boundary exists to remove. Both launchers
    # belong in their respective interface adapters.
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


def test_slice_is_in_place(slice_violations) -> None:
    """The slice exists where the migration says it does."""
    slice_violations(SLICE)  # asserts the directory is there


def test_boundary_ratchet(assert_slice_ratchet) -> None:
    """No new boundary violation, and no stale allow-list entry."""
    assert_slice_ratchet(SLICE, KNOWN_VIOLATIONS)
