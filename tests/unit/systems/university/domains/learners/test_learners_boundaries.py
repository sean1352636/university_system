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
_LEGACY = f"{_UNI}.domain"          # domains not yet migrated
_FIN = f"{_UNI}.domains.finance"    # already a slice

#: Alumni fundraising posts payments through Finance's integration module.
_FINANCE_INTEGRATION = f"{_FIN}.infrastructure.finance_integration"

KNOWN_VIOLATIONS: set[tuple[str, str]] = {
    # --- Domain layer depending outward -----------------------------------
    # The alumni menu is a Tk menu living in the domain layer, and it imports
    # this slice's own GUI package. Both belong in interfaces/gui/.
    ("domain/alumni/menu.py", "tkinter"),
    ("domain/alumni/menu.py", f"{_UNI}.domains.learners.interfaces.gui.alumni"),
    # Donations record payments directly through Finance rather than raising a
    # donation-received event for Finance to consume.
    ("domain/alumni/donations.py", _FINANCE_INTEGRATION),

    # --- Alumni UI reaching into Finance ----------------------------------
    ("interfaces/gui/alumni/business_directory.py", _FINANCE_INTEGRATION),
    ("interfaces/gui/alumni/donations.py", _FINANCE_INTEGRATION),
    ("interfaces/gui/alumni/events.py", _FINANCE_INTEGRATION),
    ("interfaces/gui/alumni/main_gui.py", f"{_FIN}.interfaces.gui.finance"),

    # --- An API route reaching into Academics ------------------------------
    ("interfaces/api/student_routes.py", f"{_LEGACY}.academics.services.modules"),

    # --- student_crud_gui: cross-domain orchestration in the UI ------------
    # Academics
    (
        "interfaces/gui/students/student_crud_gui/create.py",
        f"{_LEGACY}.academics.services.admissions_selection",
    ),
    (
        "interfaces/gui/students/student_crud_gui/create.py",
        f"{_LEGACY}.academics.services.course_management.timetable_sync",
    ),
    (
        "interfaces/gui/students/student_crud_gui/update.py",
        f"{_LEGACY}.academics.services.admissions_selection",
    ),
    (
        "interfaces/gui/students/student_crud_gui/update.py",
        f"{_LEGACY}.academics.services.course_management.timetable_sync",
    ),
    (
        "interfaces/gui/students/student_crud_gui/delete.py",
        f"{_LEGACY}.academics.services.admissions_selection",
    ),
    (
        "interfaces/gui/students/student_crud_gui/importers.py",
        f"{_LEGACY}.academics.services.admissions_selection",
    ),
    (
        "interfaces/gui/students/student_crud_gui/modules_reassign.py",
        f"{_LEGACY}.academics.services.modules",
    ),
    (
        "interfaces/gui/students/student_crud_gui/timetable.py",
        f"{_LEGACY}.academics.services.timetable_bridge",
    ),
    (
        "interfaces/gui/students/student_crud_gui/sync/chat_rooms.py",
        f"{_LEGACY}.academics.services.admissions_selection.module_chat",
    ),
    # Operations — textbook library holds
    (
        "interfaces/gui/students/student_crud_gui/create.py",
        f"{_LEGACY}.operations.commerce.textbooks.services.library_holds",
    ),
    (
        "interfaces/gui/students/student_crud_gui/update.py",
        f"{_LEGACY}.operations.commerce.textbooks.services.library_holds",
    ),
    # Pastoral — medical data, which the document wants private to that slice
    (
        "interfaces/gui/students/student_crud_gui/create.py",
        f"{_LEGACY}.pastoral.health.records",
    ),
    # Governance — visa and ATAS international compliance
    (
        "interfaces/gui/students/student_crud_gui/sync/visa.py",
        f"{_LEGACY}.governance.compliance.international_compliance.services",
    ),
    (
        "interfaces/gui/students/student_crud_gui/sync/atas.py",
        f"{_LEGACY}.governance.compliance.international_compliance.services",
    ),
    # Finance — enrolment fee creation. The document has Admissions publish an
    # accepted-applicant outcome, Learners create the record, and Finance create
    # the fee liability; today the student GUI does the third step itself.
    (
        "interfaces/gui/students/student_crud_gui/create.py",
        f"{_FIN}.domain.services.enrolment_fees",
    ),
    (
        "interfaces/gui/students/student_crud_gui/update.py",
        f"{_FIN}.domain.services.enrolment_fees",
    ),
}


def test_slice_is_in_place(slice_violations) -> None:
    """The slice exists where the migration says it does."""
    slice_violations(SLICE)  # asserts the directory is there


def test_boundary_ratchet(assert_slice_ratchet) -> None:
    """No new boundary violation, and no stale allow-list entry."""
    assert_slice_ratchet(SLICE, KNOWN_VIOLATIONS)
