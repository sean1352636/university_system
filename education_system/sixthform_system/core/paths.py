"""Centralised file/directory paths for the Sixth Form System.

All modules that need to read or write files inside this system should
import from here rather than building paths with ``Path(__file__).parent``.
That keeps the layout in one place — if the data/ directory moves or
needs to honour an environment override, only this module changes.

Environment overrides
---------------------
``EDU_SIXTHFORM_DATA_DIR``  Absolute path to use for the data directory
                           (default: ``<package>/data``).
"""

from __future__ import annotations

import os
from pathlib import Path

# ── Package layout ──────────────────────────────────────────────────
PACKAGE_ROOT: Path = Path(__file__).resolve().parent.parent

# ── Data directory ──────────────────────────────────────────────────
# Holds the local SQLite DB(s). Overridable via env so tests / installers
# can redirect it without touching code.
DATA_DIR: Path = Path(
    os.environ.get("EDU_SIXTHFORM_DATA_DIR")
    or (PACKAGE_ROOT / "data")
).resolve()

# ── Individual files ────────────────────────────────────────────────
STUDENTS_DB: Path = DATA_DIR / "sixthform.db"

# Enrolments live in the same SQLite file as students so cross-table
# joins / FK cascades work without coordinating two connections.
ENROLMENTS_DB: Path = STUDENTS_DB

# Courses share the same DB for the same reason — staff want to filter
# students by course / course by status etc.
COURSES_DB: Path = STUDENTS_DB

# Subjects (qualifications offered by the sixth form) are the source
# of truth for what student/course dropdowns can pick from.
SUBJECTS_DB: Path = STUDENTS_DB

# Class groups (teaching sets within a course) and their many-to-many
# membership table.
CLASS_GROUPS_DB: Path = STUDENTS_DB

# Timetable slots: which class group meets on which day/period/room.
TIMETABLE_DB: Path = STUDENTS_DB

# Attendance records: one row per (slot, student, date).
ATTENDANCE_DB: Path = STUDENTS_DB

# Homework / coursework assignments and per-student submissions.
HOMEWORK_DB: Path = STUDENTS_DB

# Gradebook: per-assignment grade boundary overrides (read against
# homework submissions to compute letter grades and averages).
GRADEBOOK_DB: Path = STUDENTS_DB

# Predicted grades: one row per (student, subject) with the A-Level
# letter the teacher expects them to achieve.
PREDICTED_GRADES_DB: Path = STUDENTS_DB

# Mock exams: practice papers + per-student results, keyed on subject.
MOCK_EXAMS_DB: Path = STUDENTS_DB

# Exam entries: formal board registrations (one row per
# student / paper_code / season / year).
EXAM_ENTRIES_DB: Path = STUDENTS_DB

# Results day: the board-awarded result per exam entry (1:1).
EXAM_RESULTS_DB: Path = STUDENTS_DB

# UCAS applications: one application per student + their choices.
UCAS_DB: Path = STUDENTS_DB

# Personal statement drafts (separate from the body stored on the
# UCAS application — staff iterate here, then push the chosen draft
# to the application).
PERSONAL_STATEMENTS_DB: Path = STUDENTS_DB

# UCAS academic references written by a teacher / tutor.
REFERENCES_DB: Path = STUDENTS_DB

# University offer tracking — companion details on top of ucas_choices.
OFFERS_DB: Path = STUDENTS_DB

# Apprenticeship applications (separate from UCAS; one row per
# application, any number per student).
APPRENTICESHIPS_DB: Path = STUDENTS_DB

# Careers guidance: tracked careers sessions + per-student aspirations.
CAREERS_DB: Path = STUDENTS_DB

# Tutor groups (pastoral form groups; each student is in one).
TUTOR_GROUPS_DB: Path = STUDENTS_DB

# Behaviour log: positive and negative pastoral entries.
BEHAVIOUR_DB: Path = STUDENTS_DB

# Safeguarding concerns and chronological updates (highly sensitive —
# access should be restricted to DSLs / safeguarding staff by the
# auth layer; the data layer itself doesn't gate this).
SAFEGUARDING_DB: Path = STUDENTS_DB

# Wellbeing: check-ins, support sessions, and long-running flags.
WELLBEING_DB: Path = STUDENTS_DB

# Attendance concerns: tracked interventions on top of raw attendance.
ATTENDANCE_CONCERNS_DB: Path = STUDENTS_DB

# Staff directory: teachers, tutors, pastoral, admin, etc.
STAFF_DB: Path = STUDENTS_DB

# Parent / guardian contacts: many per student.
PARENT_CONTACTS_DB: Path = STUDENTS_DB

# Parents' evenings: events + per-slot bookings.
PARENTS_EVENINGS_DB: Path = STUDENTS_DB

# Notices & bulletins: school-wide announcements.
NOTICES_DB: Path = STUDENTS_DB

# Email / messaging: log of all sent and received messages.
MESSAGES_DB: Path = STUDENTS_DB

# Fees: per-student charges and the payments against them.
FEES_DB: Path = STUDENTS_DB

# Bursary applications: 16-19 bursary fund applications + disbursements.
BURSARIES_DB: Path = STUDENTS_DB

# Trips & payments: school trips, bookings, and per-booking payments.
TRIPS_DB: Path = STUDENTS_DB

# Receipts: issued payment receipts (line items linkable to fees/trips/bursaries).
RECEIPTS_DB: Path = STUDENTS_DB

# Progress tracking: periodic progress reviews + per-review targets.
PROGRESS_DB: Path = STUDENTS_DB

# Settings: local key-value preferences for the sixth-form system.
SETTINGS_DB: Path = STUDENTS_DB


def ensure_directories() -> None:
    """Create any directories listed above. Safe to call repeatedly."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)


__all__ = [
    "PACKAGE_ROOT",
    "DATA_DIR",
    "STUDENTS_DB",
    "ENROLMENTS_DB",
    "COURSES_DB",
    "SUBJECTS_DB",
    "CLASS_GROUPS_DB",
    "TIMETABLE_DB",
    "ATTENDANCE_DB",
    "HOMEWORK_DB",
    "GRADEBOOK_DB",
    "PREDICTED_GRADES_DB",
    "MOCK_EXAMS_DB",
    "EXAM_ENTRIES_DB",
    "EXAM_RESULTS_DB",
    "UCAS_DB",
    "PERSONAL_STATEMENTS_DB",
    "REFERENCES_DB",
    "OFFERS_DB",
    "APPRENTICESHIPS_DB",
    "CAREERS_DB",
    "TUTOR_GROUPS_DB",
    "BEHAVIOUR_DB",
    "SAFEGUARDING_DB",
    "WELLBEING_DB",
    "ATTENDANCE_CONCERNS_DB",
    "STAFF_DB",
    "PARENT_CONTACTS_DB",
    "PARENTS_EVENINGS_DB",
    "NOTICES_DB",
    "MESSAGES_DB",
    "FEES_DB",
    "BURSARIES_DB",
    "TRIPS_DB",
    "RECEIPTS_DB",
    "PROGRESS_DB",
    "SETTINGS_DB",
    "ensure_directories",
]
