"""Import-boundary tests for the Assessment vertical slice.

The rules live in ``tests/unit/systems/university/domains/conftest.py``; this
module supplies only what Assessment currently violates. The allow-list is a
ratchet — see ``_assert_ratchet`` — so it can only shrink.
"""

from __future__ import annotations

SLICE = "assessment"

#: Real findings, recorded rather than tolerated. Each is work left in this slice.
KNOWN_VIOLATIONS: set[tuple[str, str]] = {
    # Direct SQL driver in a domain service — should go through a repository or
    # unit of work, which is what check_architecture.py enforces for the files
    # it already governs.
    ("domain/external_examiners/services/external_examiner_service.py", "sqlite3"),
    # A domain module importing this slice's own GUI adapter. The dependency
    # points outward; the launcher belongs in interfaces/gui/.
    (
        "domain/mitigating_circumstances/integration.py",
        "education_system.systems.university.domains.assessment.interfaces.gui"
        ".mitigating_circumstances.mitigating_circumstances_gui",
    ),
    # Assessment reaching into Admissions for recognition of prior learning.
    # Now visible as a cross-slice call because both domains have been migrated;
    # the target design is a query port on Admissions.
    (
        "domain/academic_progress/services/progress_service.py",
        "education_system.systems.university.domains.admissions.domain"
        ".prior_learning_recognition.services.prior_learning_service",
    ),
    (
        "domain/grading/grade_calculation/transcripts.py",
        "education_system.systems.university.domains.admissions.domain"
        ".prior_learning_recognition.services.prior_learning_service",
    ),
    # External-examiner adapters read the Academics curriculum specification
    # directly. Academics has not been migrated yet, so this still points at the
    # legacy domain/ tree; it becomes a port when Academics moves.
    (
        "interfaces/cli/external_examiners/external_examiner_cli.py",
        "education_system.systems.university.domain.academics"
        ".curriculum_specification.services.curriculum_specification_service",
    ),
    (
        "interfaces/gui/external_examiners/external_examiner_gui.py",
        "education_system.systems.university.domain.academics"
        ".curriculum_specification.services.curriculum_specification_service",
    ),
}


def test_slice_is_in_place(slice_violations) -> None:
    """The slice exists where the migration says it does."""
    slice_violations(SLICE)  # asserts the directory is there


def test_boundary_ratchet(assert_slice_ratchet) -> None:
    """No new boundary violation, and no stale allow-list entry."""
    assert_slice_ratchet(SLICE, KNOWN_VIOLATIONS)
