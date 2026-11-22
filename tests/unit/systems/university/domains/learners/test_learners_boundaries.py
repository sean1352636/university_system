"""Import-boundary tests for the Learners vertical slice.

The rules live in ``tests/unit/systems/university/domains/conftest.py``; this
module supplies only what Learners currently violates. The allow-list is a
ratchet — see ``_assert_ratchet`` — so it can only shrink.

Learners has the largest allow-list of any slice so far, and it is concentrated:
``interfaces/gui/students/student_crud_gui/`` reaches into five other domains.
Creating or updating a student currently triggers admissions selection,
timetable sync, library holds, health records, visa/ATAS compliance and fee
creation — inline, from the GUI. That is the strongest case in the university
for an application service that publishes a learner-changed event instead.
"""

from __future__ import annotations

SLICE = "learners"

_UNI = "education_system.systems.university"
_LEGACY = f"{_UNI}.domain"
_ADM = f"{_UNI}.domains.admissions"
_OPS = f"{_UNI}.domains.operations"          # domains not yet migrated
_FIN = f"{_UNI}.domains.finance"    # already a slice
_GOV = f"{_UNI}.domains.governance.domain"

#: Alumni fundraising posts payments through Finance's integration module.
_FINANCE_INTEGRATION = f"{_FIN}.infrastructure.finance_integration"

KNOWN_VIOLATIONS: set[tuple[str, str]] = {
    # --- Alumni UI reaching into Finance ----------------------------------
    ("interfaces/gui/alumni/business_directory.py", _FINANCE_INTEGRATION),
    ("interfaces/gui/alumni/events.py", _FINANCE_INTEGRATION),
    ("interfaces/gui/alumni/main_gui.py", f"{_FIN}.interfaces.gui.finance"),

    # --- student_crud_gui: cross-domain orchestration in the UI ------------
    # Academics
    (
        "interfaces/gui/students/student_crud_gui/create.py",
        f"{_UNI}.domains.admissions.domain.services.admissions_selection",
    ),
    (
        "interfaces/gui/students/student_crud_gui/update.py",
        f"{_UNI}.domains.admissions.domain.services.admissions_selection",
    ),
    (
        "interfaces/gui/students/student_crud_gui/delete.py",
        f"{_UNI}.domains.admissions.domain.services.admissions_selection",
    ),
    (
        "interfaces/gui/students/student_crud_gui/importers.py",
        f"{_UNI}.domains.admissions.domain.services.admissions_selection",
    ),
    (
        "interfaces/gui/students/student_crud_gui/modules_reassign.py",
        f"{_UNI}.domains.curriculum.domain.modules",
    ),
    (
        "interfaces/gui/students/student_crud_gui/timetable.py",
        f"{_UNI}.domains.teaching.domain.timetable_bridge",
    ),
    (
        "interfaces/gui/students/student_crud_gui/sync/chat_rooms.py",
        f"{_UNI}.domains.admissions.domain.services.admissions_selection.module_chat",
    ),
    # Pastoral — medical data, which the document wants private to that slice
    (
        "interfaces/gui/students/student_crud_gui/create.py",
        f"{_UNI}.domains.health.domain.health.records",
    ),
    # Governance — visa and ATAS international compliance (now a slice)
    (
        "interfaces/gui/students/student_crud_gui/sync/atas.py",
        f"{_GOV}.compliance.international_compliance.services",
    ),
    # Newly visible now Pastoral is a slice: the alumni careers UI opens
    # Pastoral's student-jobs window directly. Reaches into another domain's
    # GUI were invisible while it lived at interfaces/gui/pastoral/.
    (
        "interfaces/gui/alumni/jobs_career.py",
        f"{_UNI}.domains.student_life.interfaces.gui.student_jobs.jobs_gui",
    ),
    # Newly visible now Academics is a slice: student records link straight
    # into the Academics library UI.
    ("interfaces/gui/students/_cross_links.py",
     f"{_UNI}.domains.library.interfaces.gui.library._cross_links"),
    ("interfaces/gui/students/student_records_gui.py",
     f"{_UNI}.domains.library.interfaces.gui.library.cross_module_api"),
    # Finance — enrolment fee creation. The document has Admissions publish an
    # accepted-applicant outcome, Learners create the record, and Finance create
    # the fee liability; today the student GUI does the third step itself.
    # Carried from Academics/Pastoral when they were split into areas (2026-10-24):
    # inside one slice these were not cross-domain reaches.
    ('domain/parent_portal/__init__.py',
     'tkinter'),
    ('domain/parent_portal/academics.py',
     f"{_UNI}.domains.assessment.interfaces.gui.assignment_system.integrations.parent_portal"),
    ('domain/parent_portal/academics.py',
     f"{_UNI}.domains.assessment.interfaces.gui.grade_tracking.integrations.parent_portal"),
    ('interfaces/gui/parent_portal/attendance.py',
     f"{_UNI}.domains.teaching.interfaces.gui.attendance_tracker"),
    ('interfaces/gui/parent_portal/financial.py',
     f"{_UNI}.domains.finance.domain.ledger"),
    ('interfaces/gui/parent_portal/grades.py',
     f"{_UNI}.domains.assessment.interfaces.gui.grade_tracking_management_gui"),
}


def test_slice_is_in_place(slice_violations) -> None:
    """The slice exists where the migration says it does."""
    slice_violations(SLICE)  # asserts the directory is there


def test_boundary_ratchet(assert_slice_ratchet) -> None:
    """No new boundary violation, and no stale allow-list entry."""
    assert_slice_ratchet(SLICE, KNOWN_VIOLATIONS)
