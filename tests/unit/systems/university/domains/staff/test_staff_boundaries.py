"""Import-boundary tests for the Staff vertical slice.

The rules live in ``tests/unit/systems/university/domains/conftest.py``; this
module supplies only what Staff currently violates. The allow-list is a
ratchet — see ``_assert_ratchet`` — so it can only shrink.

Four entries across 120 modules makes this the cleanest slice by ratio so far.

**Not covered by these rules, but worth recording.** Staff took its schema with
it, per the document's "extract staff schema/repository code from the shared
database package". Six of the seven modules are unambiguously HR. The seventh,
``staff_hr_academic_schemas.py``, is the academic-staff side of HR (teaching
portfolios, sabbaticals, peer review, mentoring) — but it also defines tables
other domains own: ``external_examiners`` and ``examiner_assignments``, which
Assessment's routes query, and ``programmes``, ``programme_modules``,
``learning_outcomes`` and ``syllabi``, which belong to Academics. The seven
modules import only each other, so they had to move as a unit; splitting that
790-line DDL module by owning domain is follow-up work, and an import-boundary
test cannot see it because the coupling is through table names, not imports.
"""

from __future__ import annotations

SLICE = "staff"

_UNI = "education_system.systems.university"

KNOWN_VIOLATIONS: set[tuple[str, str]] = {
    # The background checker is a Tk application with its own SQLite access,
    # sitting in the domain layer. It belongs in interfaces/gui/ with a
    # repository behind it.
    ("domain/staff_hr/background_checks/university_bg_checker.py", "sqlite3"),
    ("domain/staff_hr/background_checks/university_bg_checker.py", "tkinter"),
    # The same event bus Governance depends on: it lives inside *Academics' GUI
    # package*, so a staff contract rule cannot raise an event without importing
    # another domain's user interface. Four domain services across two slices now
    # depend on it, which makes moving it to shared infrastructure the single
    # highest-leverage fix left in the migration.
    (
        "domain/staff_hr/services/managers/contract_manager.py",
        f"{_UNI}.interfaces.gui.academics._event_bus",
    ),
    # Payroll posts straight into Finance's ledger. Pay runs should be raised as
    # events for Finance to post, the same shape as the Governance fines and the
    # Learners enrolment fees.
    (
        "domain/staff_hr/services/managers/payroll_manager.py",
        f"{_UNI}.domains.finance.domain.ledger",
    ),
}


def test_slice_is_in_place(slice_violations) -> None:
    """The slice exists where the migration says it does."""
    slice_violations(SLICE)  # asserts the directory is there


def test_boundary_ratchet(assert_slice_ratchet) -> None:
    """No new boundary violation, and no stale allow-list entry."""
    assert_slice_ratchet(SLICE, KNOWN_VIOLATIONS)


def test_schema_moved_with_the_slice() -> None:
    """Staff owns its HR schema rather than the shared database package."""
    from pathlib import Path

    uni = (
        Path(__file__).resolve().parents[6]
        / "src/education_system/systems/university"
    )
    slice_schema = uni / "domains/staff/infrastructure/database"
    shared_schema = uni / "infrastructure/database/schemas"

    assert sorted(p.name for p in slice_schema.glob("staff_hr_*.py")), (
        "the staff HR schema modules are missing from the slice"
    )
    leftover = sorted(p.name for p in shared_schema.glob("staff_hr_*.py"))
    assert not leftover, (
        f"staff HR schema still in the shared database package: {leftover}"
    )
