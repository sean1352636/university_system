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
        "education_system.systems.university.domains.curriculum."
        "domain.curriculum_specification.services.curriculum_specification_service",
    ),
    (
        "interfaces/gui/external_examiners/external_examiner_gui.py",
        "education_system.systems.university.domains.curriculum."
        "domain.curriculum_specification.services.curriculum_specification_service",
    ),
    # Carried from Academics/Pastoral when they were split into areas (2026-10-24):
    # inside one slice these were not cross-domain reaches.
    ('domain/ai_grading/auto_grader.py',
     'education_system.systems.university.domains.assessment.interfaces.gui.assignment_system._file_viewer'),
    ('domain/assignments/exam_integrity/exam_integrity.py',
     'education_system.systems.university.domains.assessment.interfaces.gui.assignment_system.integrations'),
    ('domain/exam_management/seating.py',
     'sqlite3'),
    ('interfaces/gui/assignment_system/_file_viewer.py',
     'education_system.systems.university.domains.integrity.domain.plagiarism.checker'),
    ('interfaces/gui/assignment_system/admin_tools_manager_parts/admintoolsmanager_init.py',
     'education_system.systems.university.domains.integrity.interfaces.gui.plagiarism_main_gui.cases_panel'),
    ('interfaces/gui/assignment_system/admin_tools_manager_parts/admintoolsmanager_show_accommodations.py',
     'education_system.systems.university.domains.teaching.interfaces.gui._cross_launchers'),
    ('interfaces/gui/assignment_system/assessment_manager.py',
     'education_system.systems.university.domains.teaching.interfaces.gui._cross_launchers'),
    ('interfaces/gui/assignment_system/assignment_gui.py',
     'education_system.systems.university.domains.curriculum.domain.curriculum_specification.services.curriculum_specification_service'),
    ('interfaces/gui/assignment_system/assignment_gui.py',
     'education_system.systems.university.domains.curriculum.interfaces.gui.curriculum_specification.curriculum_specification_gui'),
    ('interfaces/gui/assignment_system/assignment_gui.py',
     'education_system.systems.university.domains.integrity.interfaces.gui.plagiarism_main_gui.window'),
    ('interfaces/gui/assignment_system/assignment_gui.py',
     'education_system.systems.university.domains.teaching.interfaces.gui._cross_dialogs'),
    ('interfaces/gui/assignment_system/assignment_gui.py',
     'education_system.systems.university.domains.teaching.interfaces.gui._cross_launchers'),
    ('interfaces/gui/assignment_system/assignment_manager/creation.py',
     'education_system.systems.university.domains.teaching.interfaces.gui._cross_services'),
    ('interfaces/gui/assignment_system/file_preview.py',
     'education_system.systems.university.domains.teaching.interfaces.gui.academic_calendar.main_gui'),
    ('interfaces/gui/assignment_system/integrations/attendance.py',
     'education_system.systems.university.domains.teaching.domain.attendance.records'),
    ('interfaces/gui/assignment_system/integrations/finance.py',
     'education_system.systems.university.domains.finance.infrastructure.finance_integration'),
    ('interfaces/gui/assignment_system/integrations/kpi.py',
     'education_system.systems.university.domains.operations.domain.reporting.kpi_dashboard.services.kpi_dashboard_service'),
    ('interfaces/gui/assignment_system/integrations/legal.py',
     'education_system.systems.university.domains.governance.domain.legal.services.legal_services_core'),
    ('interfaces/gui/assignment_system/notifications.py',
     'education_system.systems.university.domains.operations.interfaces.gui.communications.notifications.notifications_gui'),
    ('interfaces/gui/assignment_system/submission_manager.py',
     'education_system.systems.university.domains.teaching.interfaces.gui._cross_services'),
    ('interfaces/gui/exam_management/app.py',
     'education_system.systems.university.domains.teaching.interfaces.gui._cross_dialogs'),
    ('interfaces/gui/exam_management/app.py',
     'education_system.systems.university.domains.teaching.interfaces.gui._cross_launchers'),
    ('interfaces/gui/exam_management/data_manager.py',
     'education_system.systems.university.domains.teaching.interfaces.gui._cross_services'),
    ('interfaces/gui/exam_management/data_manager.py',
     'education_system.systems.university.domains.teaching.interfaces.gui.academic_calendar.database'),
    ('interfaces/gui/exam_management/dialogs.py',
     'education_system.systems.university.domains.teaching.interfaces.gui._cross_services'),
    ('interfaces/gui/exam_management/room_booking.py',
     'education_system.systems.university.domains.operations.domain.campus.room_booking.services.room_booking_service'),
    ('interfaces/gui/exam_management/tabs/exams_tab.py',
     'education_system.systems.university.domains.curriculum.domain.course_management.examiner_assignments'),
    ('interfaces/gui/exam_management/tabs/exams_tab.py',
     'education_system.systems.university.domains.teaching.interfaces.gui._cross_services'),
    ('interfaces/gui/exam_management/tabs/exams_tab.py',
     'education_system.systems.university.domains.teaching.interfaces.gui.academic_calendar.database'),
    ('interfaces/gui/grade_tracking/grades/ui/add_dialog.py',
     'education_system.systems.university.domains.teaching.interfaces.gui._cross_services'),
    ('interfaces/gui/grade_tracking/integrations/attendance.py',
     'education_system.systems.university.domains.teaching.domain.attendance.records'),
    ('interfaces/gui/grade_tracking/integrations/kpi.py',
     'education_system.systems.university.domains.operations.domain.reporting.kpi_dashboard.services.kpi_dashboard_service'),
    ('interfaces/gui/grade_tracking/integrations/legal.py',
     'education_system.systems.university.domains.governance.domain.legal.services.legal_services_core'),
    ('interfaces/gui/grade_tracking/layout_manager.py',
     'education_system.systems.university.domains.teaching.interfaces.gui._cross_dialogs'),
    ('interfaces/gui/grade_tracking/layout_manager.py',
     'education_system.systems.university.domains.teaching.interfaces.gui._cross_launchers'),
    ('interfaces/gui/grade_tracking_management_gui/core.py',
     'education_system.systems.university.domains.curriculum.domain.curriculum_specification.services.curriculum_specification_service'),
}


def test_slice_is_in_place(slice_violations) -> None:
    """The slice exists where the migration says it does."""
    slice_violations(SLICE)  # asserts the directory is there


def test_boundary_ratchet(assert_slice_ratchet) -> None:
    """No new boundary violation, and no stale allow-list entry."""
    assert_slice_ratchet(SLICE, KNOWN_VIOLATIONS)
