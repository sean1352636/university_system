"""The single source of truth for every filesystem path in the platform.

This module replaces the nine per-system ``paths.py`` modules that previously
each defined their own roots, data directories and database constants. Those
modules disagreed on 60 of their 225 names — ``DATA_DIR``, ``STAFF_DB``,
``ensure_directories`` and others meant different files in different packages,
so the same logical database resolved differently depending on which module a
caller happened to import.

Every name is therefore prefixed with the system that owns it
(``UNIVERSITY_``, ``SIXTH_FORM_``, ``FE_COLLEGE_``, ``SECONDARY_``, ``PRIMARY_``,
``NURSERY_``, ``APPRENTICESHIPS_``, ``PLATFORM_``). Only the three anchors that
are genuinely identical across all of them — :data:`PROGRAM_ROOT`,
:data:`VAR_DIR` and :data:`REPO_ROOT` — are left unprefixed.

Runtime state lives in one gitignored tree under ``program/var`` (ADR 0018),
never inside the importable package.

IMPORTANT: Directories are NOT created on import. Call the relevant
``ensure_*_directories()`` during application initialisation, or
:func:`ensure_all_directories` to create every system's tree at once.

This module depends on nothing beyond the standard library, so it can be
imported from anywhere without risking a circular import.
"""

from __future__ import annotations

import os
from pathlib import Path

# ═══════════════════════════════════════════════════════════════════════
# Roots
# ═══════════════════════════════════════════════════════════════════════

# `.../program/education_system/paths.py` -> the `education_system` package.
EDUCATION_SYSTEM_ROOT: Path = Path(__file__).resolve().parent
# -> the `program` directory (NOT the repository root, which is one level up).
PROGRAM_ROOT: Path = EDUCATION_SYSTEM_ROOT.parent
# Compatibility alias. New code should prefer PROGRAM_ROOT.
REPO_ROOT: Path = PROGRAM_ROOT

# Runtime state lives in one gitignored tree under program/ (ADR 0018).
VAR_DIR: Path = PROGRAM_ROOT / "var"

# Package roots, formerly derived from each module's own ``__file__``.
PLATFORM_ROOT: Path = EDUCATION_SYSTEM_ROOT / "platform"
_SYSTEMS_ROOT: Path = EDUCATION_SYSTEM_ROOT / "systems"
NURSERY_PACKAGE_ROOT: Path = _SYSTEMS_ROOT / "nursery"
PRIMARY_PACKAGE_ROOT: Path = _SYSTEMS_ROOT / "primary"
SECONDARY_PACKAGE_ROOT: Path = _SYSTEMS_ROOT / "secondary"
SIXTH_FORM_PACKAGE_ROOT: Path = _SYSTEMS_ROOT / "sixth_form"
UNIVERSITY_PROJECT_ROOT: Path = _SYSTEMS_ROOT / "university"

# University aliases kept for callers that used the older spellings.
UNIVERSITY_BASE_DIR: Path = UNIVERSITY_PROJECT_ROOT
UNIVERSITY_SYSTEM_DIR: Path = UNIVERSITY_PROJECT_ROOT
# The modules/ layer no longer exists (ADR 0018), so the package root is the
# source root.
UNIVERSITY_SRC_DIR: Path = UNIVERSITY_PROJECT_ROOT


def _ensure(dir_path: Path) -> Path:
    """Create *dir_path* (and parents) if it does not already exist."""
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path


def _university_resolve_email_config_file() -> Path:
    """Resolve the canonical email config path.

    Matches the resolution order in
    ``education_system.platform.integrations.email.config``:

      1. the platform-wide config — canonical, and what ``save_email_config``
         writes to;
      2. the per-university config, for installs predating the move to a
         shared location;
      3. the platform path as the default for fresh installs.

    This previously pointed at ``<education_system>/shared/data/config/``,
    which has not existed since the ADR 0018 move. That candidate could never
    resolve, so the university read a non-existent file and reported email as
    unconfigured even when the platform config was present.
    """
    if PLATFORM_EMAIL_CONFIG_PATH.exists():
        return PLATFORM_EMAIL_CONFIG_PATH
    legacy_candidate = UNIVERSITY_CONFIG_DIR / "email_config.json"
    if legacy_candidate.exists():
        return legacy_candidate
    return PLATFORM_EMAIL_CONFIG_PATH


# ═════════════════════════════════════════════════════════════════════
# Platform (shared across all five systems)
# ═════════════════════════════════════════════════════════════════════

# Static assets shipped inside the platform package (never runtime data)
PLATFORM_ASSETS_DIR: Path = PLATFORM_ROOT / "assets"
PLATFORM_TEMPLATES_DIR: Path = PLATFORM_ASSETS_DIR / "templates"
PLATFORM_DOCUMENT_TEMPLATES_DIR: Path = PLATFORM_TEMPLATES_DIR / "documents"
PLATFORM_EMAIL_TEMPLATES_DIR: Path = PLATFORM_TEMPLATES_DIR / "email"
PLATFORM_UI_TEMPLATES_DIR: Path = PLATFORM_TEMPLATES_DIR / "ui"

# Overridable via env, matching every per-system data dir below, so tests
# and installers can redirect it without touching code. This is the one
# that holds auth.db — and therefore the student journey, enrolments and
# transitions — so without an override a test that exercises anything
# cross-system has no choice but to read and write the running
# application's own auth database.
PLATFORM_DATA_DIR: Path = Path(
    os.environ.get("EDU_PLATFORM_DATA_DIR")
    or (VAR_DIR / "data" / "platform")
).resolve()
PLATFORM_DB_FILES_DIR: Path = PLATFORM_DATA_DIR / "db_files"
PLATFORM_CONFIG_DIR: Path = PLATFORM_DATA_DIR / "config"
PLATFORM_DOCUMENTS_DIR: Path = PLATFORM_DATA_DIR / "documents"
PLATFORM_LOGS_DIR: Path = VAR_DIR / "logs" / "platform"

# Databases shared across all five systems
PLATFORM_AUTH_DB_FILE: Path = PLATFORM_DB_FILES_DIR / "auth.db"
PLATFORM_AUDIT_DB_FILE: Path = PLATFORM_DB_FILES_DIR / "audit.db"
PLATFORM_MISCONDUCT_DB_FILE: Path = PLATFORM_DB_FILES_DIR / "misconduct.db"
PLATFORM_RATE_LIMITS_DB_FILE: Path = PLATFORM_DB_FILES_DIR / "rate_limits.db"

# Config written at runtime by the admin GUIs
PLATFORM_EMAIL_CONFIG_PATH: Path = PLATFORM_CONFIG_DIR / "email_config.json"
PLATFORM_SMS_CONFIG_PATH: Path = PLATFORM_CONFIG_DIR / "sms_config.json"


# ═════════════════════════════════════════════════════════════════════
# Nursery / Early Years
# ═════════════════════════════════════════════════════════════════════

# Runtime state lives under ``program/var`` (ADR 0018), never inside the
# importable package. SYSTEM_DB_PATHS below is derived from this constant, so
# the cross-system registry and the per-system constant can no longer drift.
NURSERY_DATA_DIR: Path = Path(
    os.environ.get("EDU_NURSERY_DATA_DIR")
    or (PROGRAM_ROOT / "var" / "data" / "nursery")
).resolve()

# All nursery modules share a single SQLite DB.
NURSERY_DB: Path = NURSERY_DATA_DIR / "nursery.db"
NURSERY_PUPILS_DB: Path = NURSERY_DB
NURSERY_STAFF_DB: Path = NURSERY_DB

# Per-module DB aliases for ported cross-cutting modules. Each module creates
# its own tables (``CREATE TABLE IF NOT EXISTS``) inside the shared nursery DB,
# mirroring how the other systems alias every module DB onto one file.
NURSERY_POLICIES_DB: Path = NURSERY_DB
NURSERY_GDPR_DB: Path = NURSERY_DB
NURSERY_RECRUITMENT_DB: Path = NURSERY_DB
NURSERY_COMPLAINTS_DB: Path = NURSERY_DB
NURSERY_FEEDBACK_DB: Path = NURSERY_DB
NURSERY_EXPENSE_CLAIMS_DB: Path = NURSERY_DB
NURSERY_AUDIT_REPORTS_DB: Path = NURSERY_DB
NURSERY_ACTIVITY_FEED_DB: Path = NURSERY_DB
NURSERY_STAFF_ABSENCE_DB: Path = NURSERY_DB
NURSERY_VISITORS_DB: Path = NURSERY_DB
NURSERY_DBS_CHECKS_DB: Path = NURSERY_DB
NURSERY_APPRAISALS_DB: Path = NURSERY_DB
NURSERY_SETTINGS_DB: Path = NURSERY_DB

# JSON email templates for the Email / Messaging centre. These ship with
# the code (assets/), not the runtime data dir, so they must not hang off
# the env-overridable NURSERY_DATA_DIR.
NURSERY_EMAIL_TEMPLATES_DIR: Path = NURSERY_PACKAGE_ROOT / "assets" / "templates" / "email"


# ═════════════════════════════════════════════════════════════════════
# Primary School
# ═════════════════════════════════════════════════════════════════════

PRIMARY_DATA_DIR: Path = Path(
    os.environ.get("EDU_PRIMARY_DATA_DIR")
    or (PROGRAM_ROOT / "var" / "data" / "primary")
).resolve()

# All primary modules share a single SQLite DB.
PRIMARY_PUPILS_DB: Path = PRIMARY_DATA_DIR / "primary.db"
PRIMARY_ADMISSIONS_DB: Path = PRIMARY_PUPILS_DB
PRIMARY_ENROLMENT_DB: Path = PRIMARY_PUPILS_DB
PRIMARY_ONBOARDING_DB: Path = PRIMARY_PUPILS_DB
PRIMARY_ACADEMIC_YEAR_DB: Path = PRIMARY_PUPILS_DB
PRIMARY_CALENDAR_DB: Path = PRIMARY_PUPILS_DB

# Pastoral / governance modules ported from secondary share the DB.
PRIMARY_EQUALITY_DIVERSITY_DB: Path = PRIMARY_PUPILS_DB
PRIMARY_COMPLAINTS_DB: Path = PRIMARY_PUPILS_DB
PRIMARY_FEEDBACK_DB: Path = PRIMARY_PUPILS_DB
PRIMARY_SURVEYS_DB: Path = PRIMARY_PUPILS_DB
PRIMARY_SCHOOL_COUNCIL_DB: Path = PRIMARY_PUPILS_DB
PRIMARY_TRANSPORT_DB: Path = PRIMARY_PUPILS_DB

PRIMARY_STAFF_DB: Path = PRIMARY_PUPILS_DB
PRIMARY_STAFF_HR_DB: Path = PRIMARY_PUPILS_DB
PRIMARY_DEPARTMENTS_DB: Path = PRIMARY_PUPILS_DB
PRIMARY_STAFF_ABSENCE_DB: Path = PRIMARY_PUPILS_DB
PRIMARY_STAFF_WELLBEING_DB: Path = PRIMARY_PUPILS_DB
PRIMARY_RECRUITMENT_DB: Path = PRIMARY_PUPILS_DB
PRIMARY_APPRAISALS_DB: Path = PRIMARY_PUPILS_DB
PRIMARY_CPD_DB: Path = PRIMARY_PUPILS_DB
PRIMARY_DBS_CHECKS_DB: Path = PRIMARY_PUPILS_DB
PRIMARY_VISITORS_DB: Path = PRIMARY_PUPILS_DB
PRIMARY_PARENT_CONTACTS_DB: Path = PRIMARY_PUPILS_DB
PRIMARY_PARENTS_EVENINGS_DB: Path = PRIMARY_PUPILS_DB
PRIMARY_NOTICES_DB: Path = PRIMARY_PUPILS_DB
PRIMARY_ANNOUNCEMENTS_DB: Path = PRIMARY_PUPILS_DB
PRIMARY_NOTIFICATIONS_DB: Path = PRIMARY_PUPILS_DB
PRIMARY_ACTIVITY_FEED_DB: Path = PRIMARY_PUPILS_DB
PRIMARY_MESSAGES_DB: Path = PRIMARY_PUPILS_DB
PRIMARY_LETTER_TEMPLATES_DB: Path = PRIMARY_PUPILS_DB
PRIMARY_DOCUMENT_HUB_DB: Path = PRIMARY_PUPILS_DB
PRIMARY_ATTACHMENTS_DB: Path = PRIMARY_PUPILS_DB

PRIMARY_FEES_DB: Path = PRIMARY_PUPILS_DB
PRIMARY_TRIPS_DB: Path = PRIMARY_PUPILS_DB
PRIMARY_RECEIPTS_DB: Path = PRIMARY_PUPILS_DB
PRIMARY_EXPENSE_CLAIMS_DB: Path = PRIMARY_PUPILS_DB
PRIMARY_FUNDING_DB: Path = PRIMARY_PUPILS_DB
PRIMARY_CENSUS_DB: Path = PRIMARY_PUPILS_DB

PRIMARY_PROGRESS_DB: Path = PRIMARY_PUPILS_DB
PRIMARY_AUDIT_REPORTS_DB: Path = PRIMARY_PUPILS_DB
PRIMARY_DATA_EXPORT_DB: Path = PRIMARY_PUPILS_DB

PRIMARY_SETTINGS_DB: Path = PRIMARY_PUPILS_DB
PRIMARY_COMPLIANCE_DB: Path = PRIMARY_PUPILS_DB
PRIMARY_GOVERNANCE_DB: Path = PRIMARY_PUPILS_DB
PRIMARY_POLICIES_DB: Path = PRIMARY_PUPILS_DB
PRIMARY_GDPR_DB: Path = PRIMARY_PUPILS_DB
PRIMARY_RISK_MANAGEMENT_DB: Path = PRIMARY_PUPILS_DB
PRIMARY_HEALTH_SAFETY_DB: Path = PRIMARY_PUPILS_DB
PRIMARY_ASSETS_DB: Path = PRIMARY_PUPILS_DB
PRIMARY_TODO_DB: Path = PRIMARY_PUPILS_DB

# JSON email templates for the Messaging centre. These ship with the code
# (assets/), not the runtime data dir, so they must not hang off the
# env-overridable PRIMARY_DATA_DIR. No templates are shipped yet, so
# ``load_template`` raises TemplateError until some are added.
PRIMARY_EMAIL_TEMPLATES_DIR: Path = PRIMARY_PACKAGE_ROOT / "assets" / "templates" / "email"


# ═════════════════════════════════════════════════════════════════════
# Secondary School
# ═════════════════════════════════════════════════════════════════════

# ── Data directory ──────────────────────────────────────────────────
# Holds the local SQLite DB(s). Overridable via env so tests / installers
# can redirect it without touching code.
#
# Runtime state lives under ``program/var`` (ADR 0018), never inside the
# importable package. SYSTEM_DB_PATHS below is derived from this constant, so
# the cross-system registry and the per-system constant can no longer drift.
SECONDARY_DATA_DIR: Path = Path(
    os.environ.get("EDU_SECONDARY_DATA_DIR")
    or (PROGRAM_ROOT / "var" / "data" / "secondary")
).resolve()

# ── Individual files ────────────────────────────────────────────────
# Single SQLite file shared by pupils, admissions, enrolment, onboarding,
# and bulk operations — all live in the same DB so cross-table joins and
# FK cascades work without coordinating two connections.
SECONDARY_PUPILS_DB: Path = SECONDARY_DATA_DIR / "secondary.db"
SECONDARY_ADMISSIONS_DB: Path = SECONDARY_PUPILS_DB
SECONDARY_ENROLMENT_DB: Path = SECONDARY_PUPILS_DB
SECONDARY_ONBOARDING_DB: Path = SECONDARY_PUPILS_DB
SECONDARY_ACADEMIC_YEAR_DB: Path = SECONDARY_PUPILS_DB
SECONDARY_CALENDAR_DB: Path = SECONDARY_PUPILS_DB

# Equality & Diversity: per-incident log of discrimination /
# harassment / bullying / hate incidents tagged with protected
# characteristic, plus investigation and actions-taken workflow.
SECONDARY_EQUALITY_DIVERSITY_DB: Path = SECONDARY_PUPILS_DB

# Complaints: formal complaints register with stage (Informal /
# Formal Stage 1 / Formal Stage 2 / Appeal), category, outcome
# (Upheld / Partially Upheld / Not Upheld / Withdrawn) and
# escalation tracking.
SECONDARY_COMPLAINTS_DB: Path = SECONDARY_PUPILS_DB

# Feedback: general low-formality feedback log (positive /
# suggestions / questions / concerns) tagged by category and
# source, with optional star rating and lightweight response flow.
SECONDARY_FEEDBACK_DB: Path = SECONDARY_PUPILS_DB

# Surveys: two-table schema — survey definitions (with JSON-encoded
# question spec) and per-response answer rows.
SECONDARY_SURVEYS_DB: Path = SECONDARY_PUPILS_DB

# School Council: members, meetings/agenda items and actions.
SECONDARY_SCHOOL_COUNCIL_DB: Path = SECONDARY_PUPILS_DB

# Transport: routes, stops, pupil assignments and incidents.
SECONDARY_TRANSPORT_DB: Path = SECONDARY_PUPILS_DB

# Staff Directory: core staff records (name, role, department, etc.)
SECONDARY_STAFF_DB: Path = SECONDARY_PUPILS_DB

# Staff HR: employment terms, contracts, leave balances, etc.
SECONDARY_STAFF_HR_DB: Path = SECONDARY_PUPILS_DB

# Departments: department definitions and head-of-department links.
SECONDARY_DEPARTMENTS_DB: Path = SECONDARY_PUPILS_DB

# Staff comms / HR-adjacent modules — share the secondary DB.
SECONDARY_STAFF_ABSENCE_DB: Path = SECONDARY_PUPILS_DB
SECONDARY_STAFF_WELLBEING_DB: Path = SECONDARY_PUPILS_DB
SECONDARY_RECRUITMENT_DB: Path = SECONDARY_PUPILS_DB
SECONDARY_APPRAISALS_DB: Path = SECONDARY_PUPILS_DB
SECONDARY_CPD_DB: Path = SECONDARY_PUPILS_DB
SECONDARY_DBS_CHECKS_DB: Path = SECONDARY_PUPILS_DB
SECONDARY_VISITORS_DB: Path = SECONDARY_PUPILS_DB
SECONDARY_PARENT_CONTACTS_DB: Path = SECONDARY_PUPILS_DB
SECONDARY_PARENTS_EVENINGS_DB: Path = SECONDARY_PUPILS_DB
SECONDARY_NOTICES_DB: Path = SECONDARY_PUPILS_DB
SECONDARY_ANNOUNCEMENTS_DB: Path = SECONDARY_PUPILS_DB
SECONDARY_NOTIFICATIONS_DB: Path = SECONDARY_PUPILS_DB
SECONDARY_ACTIVITY_FEED_DB: Path = SECONDARY_PUPILS_DB
SECONDARY_MESSAGES_DB: Path = SECONDARY_PUPILS_DB
SECONDARY_LETTER_TEMPLATES_DB: Path = SECONDARY_PUPILS_DB
SECONDARY_DOCUMENT_HUB_DB: Path = SECONDARY_PUPILS_DB
SECONDARY_ATTACHMENTS_DB: Path = SECONDARY_PUPILS_DB

# Finance modules — share the secondary DB.
SECONDARY_FEES_DB: Path = SECONDARY_PUPILS_DB
SECONDARY_TRIPS_DB: Path = SECONDARY_PUPILS_DB
SECONDARY_RECEIPTS_DB: Path = SECONDARY_PUPILS_DB
SECONDARY_EXPENSE_CLAIMS_DB: Path = SECONDARY_PUPILS_DB
SECONDARY_FUNDING_DB: Path = SECONDARY_PUPILS_DB
SECONDARY_CENSUS_DB: Path = SECONDARY_PUPILS_DB

# Reports & Analytics modules.
SECONDARY_PROGRESS_DB: Path = SECONDARY_PUPILS_DB
SECONDARY_AUDIT_REPORTS_DB: Path = SECONDARY_PUPILS_DB
SECONDARY_DATA_EXPORT_DB: Path = SECONDARY_PUPILS_DB

# Shared system modules.
SECONDARY_SETTINGS_DB: Path = SECONDARY_PUPILS_DB

# Governance / System-section modules.
SECONDARY_COMPLIANCE_DB: Path = SECONDARY_PUPILS_DB
SECONDARY_GOVERNANCE_DB: Path = SECONDARY_PUPILS_DB
SECONDARY_POLICIES_DB: Path = SECONDARY_PUPILS_DB
SECONDARY_GDPR_DB: Path = SECONDARY_PUPILS_DB
SECONDARY_RISK_MANAGEMENT_DB: Path = SECONDARY_PUPILS_DB
SECONDARY_HEALTH_SAFETY_DB: Path = SECONDARY_PUPILS_DB
SECONDARY_ASSETS_DB: Path = SECONDARY_PUPILS_DB
SECONDARY_TODO_DB: Path = SECONDARY_PUPILS_DB

# JSON email templates for the Messaging centre. These ship with the code
# (assets/), not the runtime data dir, so they must not hang off the
# env-overridable SECONDARY_DATA_DIR. No templates are shipped yet, so
# ``load_template`` raises TemplateError until some are added.
SECONDARY_EMAIL_TEMPLATES_DIR: Path = SECONDARY_PACKAGE_ROOT / "assets" / "templates" / "email"


# ═════════════════════════════════════════════════════════════════════
# Sixth Form College
# ═════════════════════════════════════════════════════════════════════

# ── Data directory ──────────────────────────────────────────────────
# Holds the local SQLite DB(s). Overridable via env so tests / installers
# can redirect it without touching code.
#
# Runtime state lives under ``program/var`` (ADR 0018), never inside the
# importable package. SYSTEM_DB_PATHS below is derived from this constant, so
# the cross-system registry and the per-system constant can no longer drift.
SIXTH_FORM_DATA_DIR: Path = Path(
    os.environ.get("EDU_SIXTHFORM_DATA_DIR")
    or (PROGRAM_ROOT / "var" / "data" / "sixth_form")
).resolve()

# Email templates live in the package itself (not the data dir), so
# they ship with the code rather than being editable runtime state.
SIXTH_FORM_EMAIL_TEMPLATES_DIR: Path = SIXTH_FORM_PACKAGE_ROOT / "assets" / "templates" / "email"

# Coursework file store: the actual documents students submit and the
# briefs / mark schemes teachers attach. Metadata rows live in the DB
# (``coursework_attachments``); the bytes live here, one directory per
# assignment. Runtime user data — never committed.
SIXTH_FORM_COURSEWORK_FILES_DIR: Path = SIXTH_FORM_DATA_DIR / "coursework_files"

# ── Individual files ────────────────────────────────────────────────
SIXTH_FORM_STUDENTS_DB: Path = SIXTH_FORM_DATA_DIR / "sixthform.db"

# Enrolments live in the same SQLite file as students so cross-table
# joins / FK cascades work without coordinating two connections.
SIXTH_FORM_ENROLMENTS_DB: Path = SIXTH_FORM_STUDENTS_DB

# Courses share the same DB for the same reason — staff want to filter
# students by course / course by status etc.
SIXTH_FORM_COURSES_DB: Path = SIXTH_FORM_STUDENTS_DB

# Subjects (qualifications offered by the sixth form) are the source
# of truth for what student/course dropdowns can pick from.
SIXTH_FORM_SUBJECTS_DB: Path = SIXTH_FORM_STUDENTS_DB

# Class groups (teaching sets within a course) and their many-to-many
# membership table.
SIXTH_FORM_CLASS_GROUPS_DB: Path = SIXTH_FORM_STUDENTS_DB

# Timetable slots: which class group meets on which day/period/room.
SIXTH_FORM_TIMETABLE_DB: Path = SIXTH_FORM_STUDENTS_DB

# Attendance records: one row per (slot, student, date).
SIXTH_FORM_ATTENDANCE_DB: Path = SIXTH_FORM_STUDENTS_DB

# Homework / coursework assignments and per-student submissions.
SIXTH_FORM_HOMEWORK_DB: Path = SIXTH_FORM_STUDENTS_DB

# Gradebook: per-assignment grade boundary overrides (read against
# homework submissions to compute letter grades and averages).
SIXTH_FORM_GRADEBOOK_DB: Path = SIXTH_FORM_STUDENTS_DB

# Predicted grades: one row per (student, subject) with the A-Level
# letter the teacher expects them to achieve.
SIXTH_FORM_PREDICTED_GRADES_DB: Path = SIXTH_FORM_STUDENTS_DB

# Mock exams: practice papers + per-student results, keyed on subject.
SIXTH_FORM_MOCK_EXAMS_DB: Path = SIXTH_FORM_STUDENTS_DB

# Exam entries: formal board registrations (one row per
# student / paper_code / season / year).
SIXTH_FORM_EXAM_ENTRIES_DB: Path = SIXTH_FORM_STUDENTS_DB

# Results day: the board-awarded result per exam entry (1:1).
SIXTH_FORM_EXAM_RESULTS_DB: Path = SIXTH_FORM_STUDENTS_DB

# UCAS applications: one application per student + their choices.
SIXTH_FORM_UCAS_DB: Path = SIXTH_FORM_STUDENTS_DB

# Personal statement drafts (separate from the body stored on the
# UCAS application — staff iterate here, then push the chosen draft
# to the application).
SIXTH_FORM_PERSONAL_STATEMENTS_DB: Path = SIXTH_FORM_STUDENTS_DB

# UCAS academic references written by a teacher / tutor.
SIXTH_FORM_REFERENCES_DB: Path = SIXTH_FORM_STUDENTS_DB

# University offer tracking — companion details on top of ucas_choices.
SIXTH_FORM_OFFERS_DB: Path = SIXTH_FORM_STUDENTS_DB

# Apprenticeship applications (separate from UCAS; one row per
# application, any number per student).
SIXTH_FORM_APPRENTICESHIPS_DB: Path = SIXTH_FORM_STUDENTS_DB

# Careers guidance: tracked careers sessions + per-student aspirations.
SIXTH_FORM_CAREERS_DB: Path = SIXTH_FORM_STUDENTS_DB

# University visits: trips to universities (open days, taster days,
# applicant visit days, UCAS fairs) with a per-student attendee list.
SIXTH_FORM_UNIVERSITY_VISITS_DB: Path = SIXTH_FORM_STUDENTS_DB

# Extended Project Qualification: one project per student, plus
# production-log entries and milestones.
SIXTH_FORM_EPQ_DB: Path = SIXTH_FORM_STUDENTS_DB

# Work experience: employer directory + per-student placements.
SIXTH_FORM_WORK_EXPERIENCE_DB: Path = SIXTH_FORM_STUDENTS_DB

# Room & resource booking: bookable resources + bookings with clash
# detection.
SIXTH_FORM_ROOM_BOOKING_DB: Path = SIXTH_FORM_STUDENTS_DB

# KS5 leaver destinations: one record per (student, checkpoint) for
# statutory destination-measure reporting.
SIXTH_FORM_DESTINATIONS_DB: Path = SIXTH_FORM_STUDENTS_DB

# Medical records: per-student profile + conditions / medications /
# allergies. Sensitive — access should be gated by the auth layer.
SIXTH_FORM_MEDICAL_RECORDS_DB: Path = SIXTH_FORM_STUDENTS_DB

# Tutor groups (pastoral form groups; each student is in one).
SIXTH_FORM_TUTOR_GROUPS_DB: Path = SIXTH_FORM_STUDENTS_DB

# Behaviour log: positive and negative pastoral entries.
SIXTH_FORM_BEHAVIOUR_DB: Path = SIXTH_FORM_STUDENTS_DB

# Safeguarding concerns and chronological updates (highly sensitive —
# access should be restricted to DSLs / safeguarding staff by the
# auth layer; the data layer itself doesn't gate this).
SIXTH_FORM_SAFEGUARDING_DB: Path = SIXTH_FORM_STUDENTS_DB

# Wellbeing: check-ins, support sessions, and long-running flags.
SIXTH_FORM_WELLBEING_DB: Path = SIXTH_FORM_STUDENTS_DB

# Student Wellbeing: student-facing self-service journal — daily mood
# entries, personal wellbeing goals, and saved help resources. Distinct
# from the staff-facing `SIXTH_FORM_WELLBEING_DB` schema (which holds pastoral
# check-ins, sessions and flags).
SIXTH_FORM_STUDENT_WELLBEING_DB: Path = SIXTH_FORM_STUDENTS_DB

# Prevent Duty: statutory anti-radicalisation register. Three linked
# tables — Prevent concerns (per student), Channel referrals (one per
# escalated concern), and staff Prevent training records.
SIXTH_FORM_PREVENT_DUTY_DB: Path = SIXTH_FORM_STUDENTS_DB

# System logs: every Python ``logging`` record emitted by sixth-form
# modules can be captured to this table via the SQLite log handler in
# ``core.log_store``. Lives in the same DB so the audit trail moves
# with the data.
SIXTH_FORM_SYSTEM_LOGS_DB: Path = SIXTH_FORM_STUDENTS_DB

# Attendance concerns: tracked interventions on top of raw attendance.
SIXTH_FORM_ATTENDANCE_CONCERNS_DB: Path = SIXTH_FORM_STUDENTS_DB

# Staff directory: teachers, tutors, pastoral, admin, etc.
SIXTH_FORM_STAFF_DB: Path = SIXTH_FORM_STUDENTS_DB

# Parent / guardian contacts: many per student.
SIXTH_FORM_PARENT_CONTACTS_DB: Path = SIXTH_FORM_STUDENTS_DB

# Parents' evenings: events + per-slot bookings.
SIXTH_FORM_PARENTS_EVENINGS_DB: Path = SIXTH_FORM_STUDENTS_DB

# Notices & bulletins: school-wide announcements.
SIXTH_FORM_NOTICES_DB: Path = SIXTH_FORM_STUDENTS_DB

# Email / messaging: log of all sent and received messages.
SIXTH_FORM_MESSAGES_DB: Path = SIXTH_FORM_STUDENTS_DB

# Fees: per-student charges and the payments against them.
SIXTH_FORM_FEES_DB: Path = SIXTH_FORM_STUDENTS_DB

# Bursary applications: 16-19 bursary fund applications + disbursements.
SIXTH_FORM_BURSARIES_DB: Path = SIXTH_FORM_STUDENTS_DB

# Trips & payments: school trips, bookings, and per-booking payments.
SIXTH_FORM_TRIPS_DB: Path = SIXTH_FORM_STUDENTS_DB

# Receipts: issued payment receipts (line items linkable to fees/trips/bursaries).
SIXTH_FORM_RECEIPTS_DB: Path = SIXTH_FORM_STUDENTS_DB

# Progress tracking: periodic progress reviews + per-review targets.
SIXTH_FORM_PROGRESS_DB: Path = SIXTH_FORM_STUDENTS_DB

# Settings: local key-value preferences for the sixth-form system.
SIXTH_FORM_SETTINGS_DB: Path = SIXTH_FORM_STUDENTS_DB

# Absence requests: planned-absence requests submitted on behalf of
# students (medical, university open day, family circumstances, etc.)
# with an approval workflow.
SIXTH_FORM_ABSENCE_REQUESTS_DB: Path = SIXTH_FORM_STUDENTS_DB

# Academic year: year metadata, terms within a year, and holiday/break
# periods. One year can be marked "current"; reports anchor to it.
SIXTH_FORM_ACADEMIC_YEAR_DB: Path = SIXTH_FORM_STUDENTS_DB

# Accessibility: per-student SEND/EHCP profile + the individual
# accommodations (exam access, classroom, assistive tech, etc.) they
# are entitled to.
SIXTH_FORM_ACCESSIBILITY_DB: Path = SIXTH_FORM_STUDENTS_DB

# Activity feed: system-wide audit/event log. One row per user action
# (login, CRUD, approvals, status changes, etc.) for filtering and
# review.
SIXTH_FORM_ACTIVITY_FEED_DB: Path = SIXTH_FORM_STUDENTS_DB

# Advanced search: cross-domain query layer. Stores saved searches and
# a small history table; results themselves come live from the other
# domain modules.
SIXTH_FORM_ADVANCED_SEARCH_DB: Path = SIXTH_FORM_STUDENTS_DB

# Admissions: pre-enrolment pipeline. Applicants progress through
# review/interview/offer/accept and can be converted to a `students`
# row once enrolled.
SIXTH_FORM_ADMISSIONS_DB: Path = SIXTH_FORM_STUDENTS_DB

# Onboarding: post-enrolment checklists. One row per student-checklist
# pair, with a 1:N child table of individual tick-box items.
SIXTH_FORM_ONBOARDING_DB: Path = SIXTH_FORM_STUDENTS_DB

# Bulk operations: audit log of cross-record actions (mass behaviour
# entries, mass accommodation grants, field updates, etc.).
SIXTH_FORM_BULK_OPERATIONS_DB: Path = SIXTH_FORM_STUDENTS_DB

# Alumni: leavers' contact + destinations data. Created when a student
# leaves the sixth form, typically via Bulk Operations archive.
SIXTH_FORM_ALUMNI_DB: Path = SIXTH_FORM_STUDENTS_DB

# Calendar: school-wide events (trips, exams, INSET, parents' evenings,
# meetings, deadlines, etc.).
SIXTH_FORM_CALENDAR_DB: Path = SIXTH_FORM_STUDENTS_DB

# Lesson plans: per-lesson teacher notes (objectives, activities,
# resources, homework). Anchored to a subject and optionally a course
# or class group.
SIXTH_FORM_LESSON_PLANS_DB: Path = SIXTH_FORM_STUDENTS_DB

# Cover agencies: external supply-teacher agencies the school works
# with (contact + rate + rating).
SIXTH_FORM_COVER_AGENCY_DB: Path = SIXTH_FORM_STUDENTS_DB

# Cover: per-absence cover requests — who's out, which periods need
# covering, and how (internal, supply agency, class split, etc.).
SIXTH_FORM_COVER_DB: Path = SIXTH_FORM_STUDENTS_DB

# Assignments: coursework-style assignments with per-student
# submission tracking (parallels but is broader than `homework`).
SIXTH_FORM_ASSIGNMENTS_DB: Path = SIXTH_FORM_STUDENTS_DB

# Enrichments: extra-curricular activities and the per-student
# enrolment in each (clubs, DofE, sports squads, etc.).
SIXTH_FORM_ENRICHMENTS_DB: Path = SIXTH_FORM_STUDENTS_DB

# Library: books / resources catalogue + per-student loans.
SIXTH_FORM_LIBRARY_DB: Path = SIXTH_FORM_STUDENTS_DB

# Study Planner: per-student study tasks and sessions (revision plan).
SIXTH_FORM_STUDY_PLANNER_DB: Path = SIXTH_FORM_STUDENTS_DB

# Baseline assessment: initial diagnostic results per student per
# subject (GCSE points, CAT4, MidYIS, initial test, etc.) — the source
# of truth that targets are anchored against.
SIXTH_FORM_BASELINE_ASSESSMENT_DB: Path = SIXTH_FORM_STUDENTS_DB

# Target setting: per-student, per-subject grade targets (minimum,
# aspirational, current) plus review history.
SIXTH_FORM_TARGET_SETTING_DB: Path = SIXTH_FORM_STUDENTS_DB

# ILP: Individual Learning Plans — holistic per-student plans with
# goals and periodic reviews (academic, SEND, pastoral, etc.).
SIXTH_FORM_ILP_DB: Path = SIXTH_FORM_STUDENTS_DB

# Intervention tracking: targeted, time-bound interventions per
# student with per-session attendance and impact grading.
SIXTH_FORM_INTERVENTION_TRACKING_DB: Path = SIXTH_FORM_STUDENTS_DB

# Value added: per-student per-subject prior-attainment / expected /
# actual grade comparison (ALPS / VESPA-style residual).
SIXTH_FORM_VALUE_ADDED_DB: Path = SIXTH_FORM_STUDENTS_DB

# Early warning: at-risk alerts raised from attendance, behaviour,
# grades, etc. with acknowledge / resolve workflow.
SIXTH_FORM_EARLY_WARNING_DB: Path = SIXTH_FORM_STUDENTS_DB

# Observations: teacher lesson observations (QA / drop-ins / peer
# observations / formal appraisal observations).
SIXTH_FORM_OBSERVATIONS_DB: Path = SIXTH_FORM_STUDENTS_DB

# Self assessment: per-student self-evaluation submissions across
# multiple dimensions (effort, organisation, wellbeing, subject
# confidence, etc.) with optional reviewer feedback.
SIXTH_FORM_SELF_ASSESSMENT_DB: Path = SIXTH_FORM_STUDENTS_DB

# Quality assurance: QA cycles (work scrutiny / learning walk / book
# look / planning review) with per-finding judgement, action, owner,
# evidence and impact follow-up.
SIXTH_FORM_QUALITY_ASSURANCE_DB: Path = SIXTH_FORM_STUDENTS_DB

# SEF Builder: Self-Evaluation Form. Stores per-area drafts (Quality
# of Education, Behaviour & Attitudes, Personal Development,
# Leadership & Management, Sixth Form Provision) with judgements,
# strengths, areas to develop, evidence and improvement actions.
SIXTH_FORM_SEF_BUILDER_DB: Path = SIXTH_FORM_STUDENTS_DB

# SEND register: per-student SEND register entries with status
# (Monitoring / SEN Support / EHCP / Exited), primary & secondary
# need codes, assess-plan-do-review cycle, provision summary, key
# worker / SENCo, external agencies and review schedule.
SIXTH_FORM_SEND_DB: Path = SIXTH_FORM_STUDENTS_DB

# Disciplinary: formal disciplinary cases beyond the behaviour log —
# warnings, detentions, internal exclusions, suspensions, permanent
# exclusions, behaviour contracts. Each case has a workflow from
# Reported through Sanction Served to Closed (or Appealed).
SIXTH_FORM_DISCIPLINARY_DB: Path = SIXTH_FORM_STUDENTS_DB

# Student support: lighter-touch academic / pastoral support
# referrals (catch-up sessions, study skills, exam prep tutoring,
# organisation support, welfare referrals) with priority, referrer
# and assigned support staff. Workflow Referred → Triaged →
# In Progress → Resolved → Closed.
SIXTH_FORM_STUDENT_SUPPORT_DB: Path = SIXTH_FORM_STUDENTS_DB

# Peer mentoring: mentor↔mentee pairings (both `students` rows)
# plus a per-pairing session log. Programmes include UCAS Buddies,
# Subject Tutoring, Reading Buddies, Wellbeing Mentor, etc.
SIXTH_FORM_PEER_MENTORING_DB: Path = SIXTH_FORM_STUDENTS_DB

# First aid: per-student first aid incidents (head bumps, cuts,
# allergic reactions, asthma, fainting, etc.) with first aider,
# treatment given, parent-informed and follow-up tracking.
SIXTH_FORM_FIRST_AID_DB: Path = SIXTH_FORM_STUDENTS_DB

# Emergency: site-wide emergency incidents (fire alarm, lockdown,
# intruder, evacuation, medical emergency, drills). Includes a
# response timeline and post-incident debrief.
SIXTH_FORM_EMERGENCY_DB: Path = SIXTH_FORM_STUDENTS_DB

# Equality & Diversity: per-incident log of discrimination /
# harassment / bullying / hate incidents tagged with protected
# characteristic, plus investigation and actions-taken workflow.
SIXTH_FORM_EQUALITY_DIVERSITY_DB: Path = SIXTH_FORM_STUDENTS_DB

# Complaints: formal complaints register with stage (Informal /
# Formal Stage 1 / Formal Stage 2 / Appeal), category, outcome
# (Upheld / Partially Upheld / Not Upheld / Withdrawn) and
# escalation tracking.
SIXTH_FORM_COMPLAINTS_DB: Path = SIXTH_FORM_STUDENTS_DB

# Feedback: general low-formality feedback log (positive /
# suggestions / questions / concerns) tagged by category and
# source, with optional star rating and lightweight response flow.
SIXTH_FORM_FEEDBACK_DB: Path = SIXTH_FORM_STUDENTS_DB

# Surveys: two-table schema — survey definitions (with JSON-encoded
# question spec) and per-response answer rows. Used for student
# voice, parent surveys, staff pulse checks, etc.
SIXTH_FORM_SURVEYS_DB: Path = SIXTH_FORM_STUDENTS_DB

# Student council: three-table schema — members (FK to students),
# meetings (free-standing), and motions (FK cascade on meetings).
# Tracks council membership, meetings + minutes, and per-motion
# votes / outcomes.
SIXTH_FORM_STUDENT_COUNCIL_DB: Path = SIXTH_FORM_STUDENTS_DB

# Transport: routes (operator/timetable/cost) and per-student
# transport arrangements (mode, pickup point, days, fee status).
SIXTH_FORM_TRANSPORT_DB: Path = SIXTH_FORM_STUDENTS_DB

# Staff HR: per-staff HR record (employment status, salary scale,
# DBS expiry, right-to-work, safeguarding training, reviews) and
# a leave / absence events log (annual / sick / parental / TOIL).
SIXTH_FORM_STAFF_HR_DB: Path = SIXTH_FORM_STUDENTS_DB

# Departments: department definitions + department membership
# mapping (staff ↔ department) for joint-department teachers and
# departmental responsibility roles (HoD / 2i/c / Teacher / TA).
SIXTH_FORM_DEPARTMENTS_DB: Path = SIXTH_FORM_STUDENTS_DB

# Staff absence: operational daily absence tracker (who's out today,
# expected return, cover arranged, RTW meeting). Distinct from the
# HR leave log — focused on day-to-day cover & notification.
SIXTH_FORM_STAFF_ABSENCE_DB: Path = SIXTH_FORM_STUDENTS_DB

# Staff wellbeing: per-staff wellbeing check-ins, concern flags,
# workload reviews, EAP / OH referrals. Confidential by default.
SIXTH_FORM_STAFF_WELLBEING_DB: Path = SIXTH_FORM_STUDENTS_DB

# Recruitment: vacancies + per-vacancy applicants (FK cascade)
# with shortlisting / interview / offer / start-date workflow.
SIXTH_FORM_RECRUITMENT_DB: Path = SIXTH_FORM_STUDENTS_DB

# Appraisals: per-staff per-cycle appraisal records plus per-
# appraisal objectives (FK cascade). Includes mid-year / end-year
# review dates, overall grade and pay-progression decision.
SIXTH_FORM_APPRAISALS_DB: Path = SIXTH_FORM_STUDENTS_DB

# CPD: continuing-professional-development activities (catalogue)
# plus per-staff attendance records (FK cascade on activities and
# staff). Captures hours, evaluation rating and impact on practice.
SIXTH_FORM_CPD_DB: Path = SIXTH_FORM_STUDENTS_DB

# DBS Checks: the safeguarding-compliance DBS register. One row
# per DBS check per staff member (FK cascade). Tracks level,
# expiry, update-service subscription and sign-off.
SIXTH_FORM_DBS_CHECKS_DB: Path = SIXTH_FORM_STUDENTS_DB

# Visitors: sign-in / sign-out log for everyone on site that
# isn't a student or member of staff. Tracks DBS / ID seen,
# safeguarding briefing, host, escort, badge and departure
# overdue.
SIXTH_FORM_VISITORS_DB: Path = SIXTH_FORM_STUDENTS_DB

# Announcements: site-wide announcements / banners / news.
# Audience flags (students / staff / parents / governors /
# public), priority, pinned + banner flags, publish & expiry
# scheduling with auto-expiry.
SIXTH_FORM_ANNOUNCEMENTS_DB: Path = SIXTH_FORM_STUDENTS_DB

# Notifications: per-recipient targeted notifications inbox.
# Distinct from messages (conversations) and announcements
# (broadcast). One row per (recipient, notification).
SIXTH_FORM_NOTIFICATIONS_DB: Path = SIXTH_FORM_STUDENTS_DB

# Letter templates: reusable letter / email templates with
# {{placeholder}} merge fields and a simple render helper.
SIXTH_FORM_LETTER_TEMPLATES_DB: Path = SIXTH_FORM_STUDENTS_DB

# Document Hub: central registry of versioned documents
# (policies, handbooks, forms) with category/audience scoping.
SIXTH_FORM_DOCUMENT_HUB_DB: Path = SIXTH_FORM_STUDENTS_DB

# Attachments: per-record file references attached to any
# linked entity (student, staff, notice, behaviour, etc.).
SIXTH_FORM_ATTACHMENTS_DB: Path = SIXTH_FORM_STUDENTS_DB

# Census / ILR: statutory data returns (autumn / spring /
# summer school census, ILR aims and learner records).
SIXTH_FORM_CENSUS_ILR_DB: Path = SIXTH_FORM_STUDENTS_DB

# Expense claims: staff and student expense reimbursement.
SIXTH_FORM_EXPENSE_CLAIMS_DB: Path = SIXTH_FORM_STUDENTS_DB

# Funding: 16-19 funding band tracking, bursary allocations
# and external grants.
SIXTH_FORM_FUNDING_DB: Path = SIXTH_FORM_STUDENTS_DB

# Audit Reports: canned compliance reports built on top of the
# activity feed. Saved report definitions and snapshot runs.
SIXTH_FORM_AUDIT_REPORTS_DB: Path = SIXTH_FORM_STUDENTS_DB

# Data Export: bulk exports of one or more domain datasets to a
# folder, with presets and a job/run history.
SIXTH_FORM_DATA_EXPORT_DB: Path = SIXTH_FORM_STUDENTS_DB

# Compliance: regulatory and operational compliance items
# (policy reviews, training, inspections, GDPR retention, …)
# with owners, due dates and status.
SIXTH_FORM_COMPLIANCE_DB: Path = SIXTH_FORM_STUDENTS_DB

# Governance: governing-body / trust board records — members, terms,
# meetings and decisions.
SIXTH_FORM_GOVERNANCE_DB: Path = SIXTH_FORM_STUDENTS_DB

# Policies: policy register — versioned policy documents with owner,
# review cadence, status and approval audit trail.
SIXTH_FORM_POLICIES_DB: Path = SIXTH_FORM_STUDENTS_DB

# GDPR: data-subject requests, records of processing activities,
# breach log and consent records.
SIXTH_FORM_GDPR_DB: Path = SIXTH_FORM_STUDENTS_DB

# Risk management: risk register with assessment scoring, mitigation
# actions and review history.
SIXTH_FORM_RISK_MANAGEMENT_DB: Path = SIXTH_FORM_STUDENTS_DB

# Health & Safety: incident/hazard register with assessor, severity,
# RIDDOR-reportable flag, corrective actions and review. Companion
# child table of corrective actions / sign-offs per incident.
SIXTH_FORM_HEALTH_SAFETY_DB: Path = SIXTH_FORM_STUDENTS_DB

# Assets: fixed-asset register (laptops, projectors, lab kit, etc.)
# with location, custodian, purchase, depreciation, condition,
# status (In Use / In Storage / Repair / Disposed) and a per-asset
# maintenance log.
SIXTH_FORM_ASSETS_DB: Path = SIXTH_FORM_STUDENTS_DB

# Multi-Language: supported locales, translation entries, and per-user
# language preferences.
SIXTH_FORM_MULTI_LANGUAGE_DB: Path = SIXTH_FORM_STUDENTS_DB

# To-Do: lightweight personal / shared task list (status, priority,
# owner, assignee, due date).
SIXTH_FORM_TODO_DB: Path = SIXTH_FORM_STUDENTS_DB

# Risk analytics: predictive risk snapshots derived from attendance,
# behaviour, baseline, mock and predicted-grade data.
SIXTH_FORM_RISK_ANALYTICS_DB: Path = SIXTH_FORM_STUDENTS_DB

# Timetable optimiser: saved auto-generated timetable plans and their
# proposed slot assignments (staging before committing to the live
# timetable_slots table).
SIXTH_FORM_TIMETABLE_OPTIMISER_DB: Path = SIXTH_FORM_STUDENTS_DB

# UCAS workflow: per-student application checklist / sign-off pipeline
# tying together UCAS, references, predicted grades and statements.
SIXTH_FORM_UCAS_WORKFLOW_DB: Path = SIXTH_FORM_STUDENTS_DB

# Automation rules: trigger → condition → action rules plus the audit
# log of actions the engine has fired.
SIXTH_FORM_AUTOMATION_RULES_DB: Path = SIXTH_FORM_STUDENTS_DB

# Parent portal: parent/guardian login accounts and the students each
# account is allowed to view.
SIXTH_FORM_PARENT_PORTAL_DB: Path = SIXTH_FORM_STUDENTS_DB


# ═════════════════════════════════════════════════════════════════════
# University
# ═════════════════════════════════════════════════════════════════════

UNIVERSITY_DATA_DIR: Path = VAR_DIR / "data" / "university"

# Database paths
UNIVERSITY_DB_DIR: Path = UNIVERSITY_DATA_DIR / "db_files"
UNIVERSITY_DB_FILES_DIR: Path = UNIVERSITY_DB_DIR  # Alias for clarity
UNIVERSITY_DEFAULT_DB_PATH: Path = UNIVERSITY_DB_DIR / "student_records.db"
UNIVERSITY_HEALTH_DB_PATH: Path = UNIVERSITY_DATA_DIR / "health" / "health_records.db"
UNIVERSITY_SAFEGUARDING_DB_PATH: Path = UNIVERSITY_DATA_DIR / "safeguarding" / "safeguarding_records.db"

# Backup metadata file
UNIVERSITY_BACKUP_METADATA_FILE: Path = UNIVERSITY_DATA_DIR / "backup_metadata.json"
UNIVERSITY_IMPORT_HISTORY_FILE: Path = UNIVERSITY_DATA_DIR / "import_history.json"

# Logging paths - under var/, not inside the package
UNIVERSITY_LOG_DIR: Path = VAR_DIR / "logs" / "university"

# Backup paths - organised by type under a single top-level directory
UNIVERSITY_BACKUP_DIR: Path = VAR_DIR / "backups" / "university"
UNIVERSITY_BACKUP_DATABASE_DIR: Path = UNIVERSITY_BACKUP_DIR / "database"
UNIVERSITY_BACKUP_FILES_DIR: Path = UNIVERSITY_BACKUP_DIR / "files"
UNIVERSITY_BACKUP_ATTENDANCE_DIR: Path = UNIVERSITY_BACKUP_DIR / "attendance"
UNIVERSITY_BACKUP_FINANCE_DIR: Path = UNIVERSITY_BACKUP_DIR / "finance"
UNIVERSITY_BACKUP_LIBRARY_DIR: Path = UNIVERSITY_BACKUP_DIR / "library"
UNIVERSITY_BACKUP_HEALTH_DIR: Path = UNIVERSITY_BACKUP_DIR / "health"
UNIVERSITY_BACKUP_SETTINGS_DIR: Path = UNIVERSITY_BACKUP_DIR / "settings"
UNIVERSITY_BACKUP_CALENDAR_DIR: Path = UNIVERSITY_BACKUP_DIR / "calendar"
UNIVERSITY_BACKUP_SUBMISSIONS_DIR: Path = UNIVERSITY_BACKUP_DIR / "submissions"
# Remote backup location and archive member names are centralized here so
# callers do not embed storage-layout literals.
UNIVERSITY_REMOTE_BACKUP_PATH: str = "/backups"
UNIVERSITY_DATABASE_BACKUP_FILENAME: str = "database.db"
# Backward-compatible aliases
UNIVERSITY_DB_BACKUPS_DIR: Path = UNIVERSITY_BACKUP_DATABASE_DIR

# Export paths - organised under data for consistent hierarchy
UNIVERSITY_EXPORTS_DIR: Path = UNIVERSITY_DATA_DIR / "exports"
UNIVERSITY_EXPORTS_DATABASE_DIR: Path = UNIVERSITY_EXPORTS_DIR / "database"
UNIVERSITY_EXPORTS_PDF_DIR: Path = UNIVERSITY_EXPORTS_DIR / "pdf"
UNIVERSITY_EXPORTS_TICKETS_DIR: Path = UNIVERSITY_EXPORTS_DIR / "tickets"
UNIVERSITY_EXPORTS_SUBMISSIONS_DIR: Path = UNIVERSITY_EXPORTS_DIR / "submissions"
UNIVERSITY_EXPORTS_REPORTS_DIR: Path = UNIVERSITY_EXPORTS_DIR / "reports"
UNIVERSITY_EXPORTS_BAKERY_DIR: Path = UNIVERSITY_EXPORTS_DIR / "bakery"
# Backward-compatible alias
UNIVERSITY_DB_EXPORTS_DIR: Path = UNIVERSITY_DB_DIR / "exports"

# Reports paths under data
UNIVERSITY_REPORTS_DIR: Path = UNIVERSITY_DATA_DIR / "reports"
UNIVERSITY_REPORT_TEMPLATES_DIR: Path = UNIVERSITY_DATA_DIR / "reports_templates"
UNIVERSITY_REPORT_CACHE_DIR: Path = UNIVERSITY_DATA_DIR / "report_cache"
UNIVERSITY_SCHEDULED_REPORTS_FILE: Path = UNIVERSITY_REPORTS_DIR / "scheduled_reports.json"

# Email subsystem paths - consolidated to templates/email
UNIVERSITY_EMAIL_DATA_DIR: Path = UNIVERSITY_DATA_DIR / "email"
UNIVERSITY_EMAIL_TEMPLATES_DIR: Path = UNIVERSITY_PROJECT_ROOT / "assets" / "templates" / "email"
UNIVERSITY_TEMPLATE_REGISTRY_DIR: Path = UNIVERSITY_PROJECT_ROOT / "assets" / "templates" / "registry"
UNIVERSITY_UI_TEMPLATES_DIR: Path = UNIVERSITY_PROJECT_ROOT / "assets" / "templates" / "ui"
UNIVERSITY_DOCUMENT_TEMPLATES_DIR: Path = UNIVERSITY_PROJECT_ROOT / "assets" / "templates" / "documents"
UNIVERSITY_DATA_TEMPLATES_DIR: Path = UNIVERSITY_PROJECT_ROOT / "assets" / "templates" / "data"
UNIVERSITY_SEED_TEMPLATES_DIR: Path = UNIVERSITY_PROJECT_ROOT / "assets" / "templates" / "seeds"

# Configuration directory
UNIVERSITY_CONFIG_DIR: Path = UNIVERSITY_DATA_DIR / "config"

# Canonical config/report/template files (previously hardcoded at many call sites)
UNIVERSITY_SAVED_REPORTS_FILE: Path = UNIVERSITY_CONFIG_DIR / "saved_reports.json"
UNIVERSITY_API_SERVER_CONFIG_FILE: Path = UNIVERSITY_CONFIG_DIR / "api_server_config.json"
UNIVERSITY_LICENSES_FILE: Path = UNIVERSITY_CONFIG_DIR / "licenses.json"
UNIVERSITY_DR_CONFIG_FILE: Path = UNIVERSITY_CONFIG_DIR / "dr_config.json"
UNIVERSITY_MAINTENANCE_WINDOWS_FILE: Path = UNIVERSITY_CONFIG_DIR / "maintenance_windows.json"
UNIVERSITY_FINANCE_GUI_SETTINGS_FILE: Path = UNIVERSITY_CONFIG_DIR / "finance_gui_settings.json"

UNIVERSITY_EMAIL_CONFIG_FILE: Path = _university_resolve_email_config_file()
UNIVERSITY_EMAIL_CONFIG_PATH: Path = UNIVERSITY_EMAIL_CONFIG_FILE

# Activity logger configuration lives in config data.
UNIVERSITY_LOGGER_CONFIG_DIR: Path = UNIVERSITY_CONFIG_DIR

# Chatbot assets (uploads/models) live under a dedicated namespace.
UNIVERSITY_CHATBOT_DATA_DIR: Path = UNIVERSITY_DATA_DIR / "chatbot"
UNIVERSITY_CHATBOT_UPLOAD_DIR: Path = UNIVERSITY_CHATBOT_DATA_DIR / "uploads"
UNIVERSITY_CHATBOT_MODELS_DIR: Path = UNIVERSITY_CHATBOT_DATA_DIR / "models"
UNIVERSITY_CHATBOT_CONFIG_PATH: Path = UNIVERSITY_LOGGER_CONFIG_DIR / "chatbot_config.json"

# QR codes directory
UNIVERSITY_QR_CODES_DIR: Path = UNIVERSITY_DATA_DIR / "qr_codes"

# Analytics directories - consolidated under data/analytics
UNIVERSITY_ANALYTICS_DIR: Path = UNIVERSITY_DATA_DIR / "analytics"
UNIVERSITY_ANALYTICS_PLOTS_DIR: Path = UNIVERSITY_ANALYTICS_DIR / "plots"
# Analytics reports now under main reports directory for consolidation
UNIVERSITY_ANALYTICS_REPORTS_DIR: Path = UNIVERSITY_REPORTS_DIR / "analytics"

# Submissions directory - for assignment submissions
UNIVERSITY_SUBMISSIONS_DIR: Path = UNIVERSITY_DATA_DIR / "submissions"

# Uploads directory - for general file uploads
UNIVERSITY_UPLOAD_DIR: Path = UNIVERSITY_DATA_DIR / "uploads"
UNIVERSITY_UPLOADS_DIR: Path = UNIVERSITY_UPLOAD_DIR  # Alias for consistency

# Temporary files directory - for temporary files (instead of /tmp)
UNIVERSITY_TEMP_DIR: Path = UNIVERSITY_DATA_DIR / "temp"

# Templates directory - shipped static assets under assets/
UNIVERSITY_TEMPLATES_DIR: Path = UNIVERSITY_PROJECT_ROOT / "assets" / "templates"
UNIVERSITY_EMAIL_TEMPLATE_MAPPING_FILE: Path = UNIVERSITY_TEMPLATE_REGISTRY_DIR / "email_template_mapping.json"
UNIVERSITY_ASSIGNMENT_TEMPLATES_DIR: Path = UNIVERSITY_UI_TEMPLATES_DIR / "assignments"
# Shipped, read-only backup-template seeds; user-saved templates go to data/ (UNIVERSITY_USER_BACKUP_TEMPLATES_DIR)
UNIVERSITY_BACKUP_TEMPLATES_DIR: Path = UNIVERSITY_SEED_TEMPLATES_DIR / "backup"
UNIVERSITY_USER_BACKUP_TEMPLATES_DIR: Path = UNIVERSITY_DATA_DIR / "backup_templates"
UNIVERSITY_MEDICAL_TEMPLATES_DIR: Path = UNIVERSITY_DOCUMENT_TEMPLATES_DIR / "medical"
UNIVERSITY_TICKET_TEMPLATES_DIR: Path = UNIVERSITY_UI_TEMPLATES_DIR / "ticketing"
UNIVERSITY_COURSE_EVALUATION_TEMPLATES_DIR: Path = UNIVERSITY_UI_TEMPLATES_DIR / "course_evaluation"

# Email reminder templates
UNIVERSITY_EMAIL_REMINDER_TEMPLATES_DIR: Path = UNIVERSITY_EMAIL_TEMPLATES_DIR / "communications" / "reminders"

# Finance templates directory - for finance seed/template data
UNIVERSITY_FINANCE_TEMPLATES_DIR: Path = UNIVERSITY_DOCUMENT_TEMPLATES_DIR / "finance"

# NLTK data directory - for natural language processing data
UNIVERSITY_NLTK_DATA_DIR: Path = UNIVERSITY_DATA_DIR / "nltk_data"

# Student documents directory - for student document storage
UNIVERSITY_STUDENT_DOCUMENTS_DIR: Path = UNIVERSITY_DATA_DIR / "student_documents"

# Branding directory - institution logo and other admin-supplied brand assets.
# Runtime data (an admin uploads it), so it belongs under var/ rather than the
# shipped assets/ tree.
UNIVERSITY_BRANDING_DIR: Path = UNIVERSITY_DATA_DIR / "branding"

# UNIVERSITY_EXPORTS_DIR is now defined above under "Export paths"

# Charts directory - for chart outputs
UNIVERSITY_CHARTS_DIR: Path = UNIVERSITY_REPORTS_DIR / "charts"

# Locales directory - for internationalization translation files
UNIVERSITY_LOCALES_DIR: Path = UNIVERSITY_DATA_DIR / "locales"
UNIVERSITY_LANGUAGE_CONFIG_PATH: Path = UNIVERSITY_CONFIG_DIR / "language_config.json"

# Assets directory - for static assets
UNIVERSITY_ASSETS_DIR: Path = UNIVERSITY_PROJECT_ROOT / "assets"

# Utility scripts moved out of the package to tools/<system> (ADR 0018)
UNIVERSITY_SCRIPTS_DIR: Path = REPO_ROOT / "tools" / "university"


# ═════════════════════════════════════════════════════════════════════
# FE College (Further Education)
# ═════════════════════════════════════════════════════════════════════
#
# The FE College package is launchable (its own CLI/GUI, shared-auth system
# key ``fe_college``) and is now a full member of the cross-system registry
# below. It was held out until ``student_journey`` grew a ``fe_college_*``
# slot of its own — the ``college_*`` columns already belong to sixth form,
# so reusing them would have merged two different institutions' learner ids
# onto one journey. With the slot in place it joins SYSTEM_DB_PATHS /
# SYSTEM_ORDER / SYSTEM_LABELS like any other system, and an FE learner
# shows up in the journey, transcript, GDPR and analytics services.

# ── Data directory ──────────────────────────────────────────────────
# Overridable via env so tests and installers can redirect it without
# touching code. Runtime state lives under program/var (ADR 0018).
FE_COLLEGE_DATA_DIR: Path = Path(
    os.environ.get("EDU_FE_COLLEGE_DATA_DIR")
    or (PROGRAM_ROOT / "var" / "data" / "fe_college")
).resolve()

# Coursework/evidence uploads: assignment submissions and the portfolio
# files a learner attaches. Metadata rows live in the DB; bytes live here.
FE_COLLEGE_SUBMISSIONS_DIR: Path = FE_COLLEGE_DATA_DIR / "submissions"

# Generated report exports (attendance, achievement, funding returns).
FE_COLLEGE_EXPORTS_DIR: Path = FE_COLLEGE_DATA_DIR / "exports"

# ── Individual files ────────────────────────────────────────────────
# One physical SQLite file, many logical names. Every screen joins across
# these tables (a learner's enrolments, attendance, grades and fees are
# read together on the profile alone), so splitting them across files
# would buy nothing and cost cross-connection coordination.
FE_COLLEGE_DB: Path = FE_COLLEGE_DATA_DIR / "fe_college.db"

FE_COLLEGE_STUDENTS_DB: Path = FE_COLLEGE_DB
FE_COLLEGE_STAFF_DB: Path = FE_COLLEGE_DB
FE_COLLEGE_COURSES_DB: Path = FE_COLLEGE_DB
FE_COLLEGE_ENROLMENTS_DB: Path = FE_COLLEGE_DB
FE_COLLEGE_ATTENDANCE_DB: Path = FE_COLLEGE_DB
FE_COLLEGE_ASSESSMENT_DB: Path = FE_COLLEGE_DB
FE_COLLEGE_TIMETABLE_DB: Path = FE_COLLEGE_DB
FE_COLLEGE_FINANCE_DB: Path = FE_COLLEGE_DB
FE_COLLEGE_EXAMS_DB: Path = FE_COLLEGE_DB
FE_COLLEGE_FACILITIES_DB: Path = FE_COLLEGE_DB
FE_COLLEGE_PASTORAL_DB: Path = FE_COLLEGE_DB

# Template assets ship with the code, not as editable runtime state.
FE_COLLEGE_PACKAGE_ROOT: Path = _SYSTEMS_ROOT / "fe_college"
FE_COLLEGE_EMAIL_TEMPLATES_DIR: Path = (
    FE_COLLEGE_PACKAGE_ROOT / "assets" / "templates" / "email"
)


# ═════════════════════════════════════════════════════════════════════
# Apprenticeships
# ═════════════════════════════════════════════════════════════════════
#
# Apprenticeships is a full member of the cross-system registry below, but
# it joins on different terms from the school-shaped systems. It is not a
# station on the nursery→university chain; it is a post-16 destination that
# secondary, sixth form and FE College feed into, that runs *concurrently*
# with university for a degree apprenticeship, and that feeds back into
# university for a top-up. So it has a ``student_journey`` slot and an
# entry in every registry here, but it is deliberately absent from
# ``progression.PHASE_ORDER``, which only describes the linear chain.
#
# Note the table names below and in SYSTEM_LEARNER_TABLE: this system keeps
# ``apprentices``/``apprentice_id``, not ``students``/``student_id``.

# ── Data directory ──────────────────────────────────────────────────
# Overridable via env so tests and installers can redirect it without
# touching code. Runtime state lives under program/var (ADR 0018).
APPRENTICESHIPS_DATA_DIR: Path = Path(
    os.environ.get("EDU_APPRENTICESHIPS_DATA_DIR")
    or (PROGRAM_ROOT / "var" / "data" / "apprenticeships")
).resolve()

# Portfolio evidence file store: the documents an apprentice uploads as
# proof against their KSBs. Metadata rows live in the DB
# (``portfolio_evidence``); the bytes live here. Runtime user data.
APPRENTICESHIPS_EVIDENCE_DIR: Path = APPRENTICESHIPS_DATA_DIR / "evidence"

# Generated funding-audit evidence packs (one ZIP/PDF per export).
APPRENTICESHIPS_EXPORTS_DIR: Path = APPRENTICESHIPS_DATA_DIR / "exports"

# ── Individual files ────────────────────────────────────────────────
# One physical SQLite file, many logical names — the tables are heavily
# joined (an apprentice's OTJ hours, reviews, portfolio and EPA record
# are read together on nearly every screen), so splitting them across
# files would buy nothing and cost cross-connection coordination.
APPRENTICESHIPS_DB: Path = APPRENTICESHIPS_DATA_DIR / "apprenticeships.db"

APPRENTICESHIPS_APPRENTICES_DB: Path = APPRENTICESHIPS_DB
APPRENTICESHIPS_EMPLOYERS_DB: Path = APPRENTICESHIPS_DB
APPRENTICESHIPS_PROGRAMMES_DB: Path = APPRENTICESHIPS_DB
APPRENTICESHIPS_TRAINING_DB: Path = APPRENTICESHIPS_DB
APPRENTICESHIPS_PORTFOLIO_DB: Path = APPRENTICESHIPS_DB
APPRENTICESHIPS_REVIEWS_DB: Path = APPRENTICESHIPS_DB
APPRENTICESHIPS_EPA_DB: Path = APPRENTICESHIPS_DB
APPRENTICESHIPS_FUNDING_DB: Path = APPRENTICESHIPS_DB
APPRENTICESHIPS_COMPLIANCE_DB: Path = APPRENTICESHIPS_DB
APPRENTICESHIPS_STAFF_DB: Path = APPRENTICESHIPS_DB

# Template assets ship with the code, not as editable runtime state.
APPRENTICESHIPS_PACKAGE_ROOT: Path = _SYSTEMS_ROOT / "apprenticeships"
APPRENTICESHIPS_EMAIL_TEMPLATES_DIR: Path = (
    APPRENTICESHIPS_PACKAGE_ROOT / "assets" / "templates" / "email"
)


# ═════════════════════════════════════════════════════════════════════
# Cross-system database registry (formerly kernel/database/paths.py)
# ═════════════════════════════════════════════════════════════════════

# Every shared service that queries across systems resolves database files
# through this registry rather than computing paths independently.
PLATFORM_AUTH_DB: Path = PLATFORM_AUTH_DB_FILE

SYSTEM_DB_PATHS: dict[str, Path] = {
    "nursery": NURSERY_DB,
    "primary": PRIMARY_PUPILS_DB,
    "secondary": SECONDARY_PUPILS_DB,
    "sixth_form": SIXTH_FORM_STUDENTS_DB,
    "fe_college": FE_COLLEGE_DB,
    "apprenticeships": APPRENTICESHIPS_DB,
    "university": UNIVERSITY_DEFAULT_DB_PATH,
}

# Display / iteration order. This is a reading order, not a progression
# chain: fe_college and apprenticeships are post-16 alternatives that sit
# beside sixth form, not stations between it and university. The chain of
# *recommended* next phases lives in cross_system.progression.PHASE_ORDER,
# which deliberately still names only the five linear phases.
SYSTEM_ORDER: list[str] = [
    "nursery", "primary", "secondary", "sixth_form", "fe_college",
    "apprenticeships", "university",
]

SYSTEM_LABELS: dict[str, str] = {
    "nursery": "Nursery",
    "primary": "Primary School",
    "secondary": "Secondary School",
    "sixth_form": "Sixth Form College",
    "fe_college": "FE College",
    "apprenticeships": "Apprenticeships",
    "university": "University",
}

# Where each system keeps its learner rows: system key -> (table, id column).
#
# Cross-cutting services (GDPR erasure and SAR, retention, the analytics
# warehouse, the single student view) have to open a system's database and
# find its learners without importing that system. They previously each
# carried their own copy of the rule as ``"pupils" if primary else
# "students"``, which quietly assumed every non-primary system uses a
# ``students``/``student_id`` pair. Apprenticeships does not — it has
# ``apprentices``/``apprentice_id`` — so the assumption now has to be
# stated in one place rather than re-derived in seven.
SYSTEM_LEARNER_TABLE: dict[str, tuple[str, str]] = {
    "nursery": ("pupils", "pupil_id"),
    "primary": ("pupils", "pupil_id"),
    "secondary": ("pupils", "pupil_id"),
    "sixth_form": ("students", "student_id"),
    "fe_college": ("students", "student_id"),
    "apprenticeships": ("apprentices", "apprentice_id"),
    "university": ("students", "student_id"),
}


def learner_table(system: str) -> tuple[str, str]:
    """The ``(table, id_column)`` holding ``system``'s learner records.

    Falls back to the historical ``students``/``student_id`` guess for an
    unregistered key, so a caller handed an unknown system degrades to the
    old behaviour instead of raising.
    """
    return SYSTEM_LEARNER_TABLE.get(system, ("students", "student_id"))


# ═════════════════════════════════════════════════════════════════════
# Directory creation
# ═════════════════════════════════════════════════════════════════════


def ensure_platform_directories() -> None:
    """Create the runtime directory structure. Safe to call repeatedly."""
    for d in (PLATFORM_DATA_DIR, PLATFORM_DB_FILES_DIR, PLATFORM_CONFIG_DIR, PLATFORM_DOCUMENTS_DIR, PLATFORM_LOGS_DIR):
        d.mkdir(parents=True, exist_ok=True)


def ensure_nursery_directories() -> None:
    NURSERY_DATA_DIR.mkdir(parents=True, exist_ok=True)


def ensure_primary_directories() -> None:
    PRIMARY_DATA_DIR.mkdir(parents=True, exist_ok=True)


def ensure_secondary_directories() -> None:
    """Create the data directory if it doesn't exist yet."""
    SECONDARY_DATA_DIR.mkdir(parents=True, exist_ok=True)


def ensure_sixth_form_directories() -> None:
    """Create any directories listed above. Safe to call repeatedly."""
    SIXTH_FORM_DATA_DIR.mkdir(parents=True, exist_ok=True)
    SIXTH_FORM_COURSEWORK_FILES_DIR.mkdir(parents=True, exist_ok=True)


def ensure_fe_college_directories() -> None:
    """Create the FE College runtime tree. Safe to call repeatedly."""
    FE_COLLEGE_DATA_DIR.mkdir(parents=True, exist_ok=True)
    FE_COLLEGE_SUBMISSIONS_DIR.mkdir(parents=True, exist_ok=True)
    FE_COLLEGE_EXPORTS_DIR.mkdir(parents=True, exist_ok=True)


def ensure_apprenticeships_directories() -> None:
    """Create the apprenticeships runtime tree. Safe to call repeatedly."""
    APPRENTICESHIPS_DATA_DIR.mkdir(parents=True, exist_ok=True)
    APPRENTICESHIPS_EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    APPRENTICESHIPS_EXPORTS_DIR.mkdir(parents=True, exist_ok=True)


def ensure_university_directories() -> None:
    """
    Explicitly create all required directories.

    This function should be called during application bootstrap/initialization,
    not at import time. This keeps imports side-effect free.
    """
    _ensure(UNIVERSITY_DATA_DIR)
    _ensure(UNIVERSITY_DB_DIR)
    _ensure(UNIVERSITY_LOG_DIR)
    # Backup subdirectories
    _ensure(UNIVERSITY_BACKUP_DATABASE_DIR)
    _ensure(UNIVERSITY_BACKUP_FILES_DIR)
    _ensure(UNIVERSITY_BACKUP_ATTENDANCE_DIR)
    _ensure(UNIVERSITY_BACKUP_FINANCE_DIR)
    _ensure(UNIVERSITY_BACKUP_LIBRARY_DIR)
    _ensure(UNIVERSITY_BACKUP_HEALTH_DIR)
    _ensure(UNIVERSITY_BACKUP_SETTINGS_DIR)
    _ensure(UNIVERSITY_BACKUP_CALENDAR_DIR)
    # Export subdirectories
    _ensure(UNIVERSITY_EXPORTS_DATABASE_DIR)
    _ensure(UNIVERSITY_EXPORTS_PDF_DIR)
    _ensure(UNIVERSITY_EXPORTS_TICKETS_DIR)
    _ensure(UNIVERSITY_EXPORTS_SUBMISSIONS_DIR)
    _ensure(UNIVERSITY_EXPORTS_REPORTS_DIR)
    _ensure(UNIVERSITY_EXPORTS_BAKERY_DIR)
    _ensure(UNIVERSITY_REPORTS_DIR)
    _ensure(UNIVERSITY_REPORT_TEMPLATES_DIR)
    _ensure(UNIVERSITY_REPORT_CACHE_DIR)
    _ensure(UNIVERSITY_EMAIL_DATA_DIR)
    _ensure(UNIVERSITY_EMAIL_TEMPLATES_DIR)
    _ensure(UNIVERSITY_LOGGER_CONFIG_DIR)
    _ensure(UNIVERSITY_CHATBOT_DATA_DIR)
    _ensure(UNIVERSITY_CHATBOT_UPLOAD_DIR)
    _ensure(UNIVERSITY_CHATBOT_MODELS_DIR)
    _ensure(UNIVERSITY_QR_CODES_DIR)
    _ensure(UNIVERSITY_ANALYTICS_DIR)
    _ensure(UNIVERSITY_ANALYTICS_PLOTS_DIR)
    _ensure(UNIVERSITY_ANALYTICS_REPORTS_DIR)
    _ensure(UNIVERSITY_SUBMISSIONS_DIR)
    _ensure(UNIVERSITY_UPLOAD_DIR)
    _ensure(UNIVERSITY_TEMPLATES_DIR)
    _ensure(UNIVERSITY_TEMPLATE_REGISTRY_DIR)
    _ensure(UNIVERSITY_UI_TEMPLATES_DIR)
    _ensure(UNIVERSITY_DOCUMENT_TEMPLATES_DIR)
    _ensure(UNIVERSITY_DATA_TEMPLATES_DIR)
    _ensure(UNIVERSITY_SEED_TEMPLATES_DIR)
    _ensure(UNIVERSITY_ASSIGNMENT_TEMPLATES_DIR)
    _ensure(UNIVERSITY_BACKUP_TEMPLATES_DIR)
    _ensure(UNIVERSITY_USER_BACKUP_TEMPLATES_DIR)
    _ensure(UNIVERSITY_MEDICAL_TEMPLATES_DIR)
    _ensure(UNIVERSITY_TICKET_TEMPLATES_DIR)
    _ensure(UNIVERSITY_EMAIL_REMINDER_TEMPLATES_DIR)
    _ensure(UNIVERSITY_FINANCE_TEMPLATES_DIR)
    _ensure(UNIVERSITY_NLTK_DATA_DIR)
    _ensure(UNIVERSITY_STUDENT_DOCUMENTS_DIR)
    _ensure(UNIVERSITY_BRANDING_DIR)
    _ensure(UNIVERSITY_TEMP_DIR)
    _ensure(UNIVERSITY_CONFIG_DIR)
    _ensure(UNIVERSITY_CHARTS_DIR)
    _ensure(UNIVERSITY_LOCALES_DIR)


def ensure_all_directories() -> None:
    """Create every system's runtime tree. Safe to call repeatedly."""
    ensure_platform_directories()
    ensure_nursery_directories()
    ensure_primary_directories()
    ensure_secondary_directories()
    ensure_sixth_form_directories()
    ensure_university_directories()
    ensure_fe_college_directories()
    ensure_apprenticeships_directories()


__all__ = [
    "APPRENTICESHIPS_APPRENTICES_DB",
    "APPRENTICESHIPS_COMPLIANCE_DB",
    "APPRENTICESHIPS_DATA_DIR",
    "APPRENTICESHIPS_DB",
    "APPRENTICESHIPS_EMAIL_TEMPLATES_DIR",
    "APPRENTICESHIPS_EMPLOYERS_DB",
    "APPRENTICESHIPS_EPA_DB",
    "APPRENTICESHIPS_EVIDENCE_DIR",
    "APPRENTICESHIPS_EXPORTS_DIR",
    "APPRENTICESHIPS_FUNDING_DB",
    "APPRENTICESHIPS_PACKAGE_ROOT",
    "APPRENTICESHIPS_PORTFOLIO_DB",
    "APPRENTICESHIPS_PROGRAMMES_DB",
    "APPRENTICESHIPS_REVIEWS_DB",
    "APPRENTICESHIPS_STAFF_DB",
    "APPRENTICESHIPS_TRAINING_DB",
    "EDUCATION_SYSTEM_ROOT",
    "FE_COLLEGE_ASSESSMENT_DB",
    "FE_COLLEGE_ATTENDANCE_DB",
    "FE_COLLEGE_COURSES_DB",
    "FE_COLLEGE_DATA_DIR",
    "FE_COLLEGE_DB",
    "FE_COLLEGE_EMAIL_TEMPLATES_DIR",
    "FE_COLLEGE_ENROLMENTS_DB",
    "FE_COLLEGE_EXAMS_DB",
    "FE_COLLEGE_EXPORTS_DIR",
    "FE_COLLEGE_FACILITIES_DB",
    "FE_COLLEGE_FINANCE_DB",
    "FE_COLLEGE_PACKAGE_ROOT",
    "FE_COLLEGE_PASTORAL_DB",
    "FE_COLLEGE_STAFF_DB",
    "FE_COLLEGE_STUDENTS_DB",
    "FE_COLLEGE_SUBMISSIONS_DIR",
    "FE_COLLEGE_TIMETABLE_DB",
    "NURSERY_ACTIVITY_FEED_DB",
    "NURSERY_APPRAISALS_DB",
    "NURSERY_AUDIT_REPORTS_DB",
    "NURSERY_COMPLAINTS_DB",
    "NURSERY_DATA_DIR",
    "NURSERY_DB",
    "NURSERY_DBS_CHECKS_DB",
    "NURSERY_EMAIL_TEMPLATES_DIR",
    "NURSERY_EXPENSE_CLAIMS_DB",
    "NURSERY_FEEDBACK_DB",
    "NURSERY_GDPR_DB",
    "NURSERY_PACKAGE_ROOT",
    "NURSERY_POLICIES_DB",
    "NURSERY_PUPILS_DB",
    "NURSERY_RECRUITMENT_DB",
    "NURSERY_SETTINGS_DB",
    "NURSERY_STAFF_ABSENCE_DB",
    "NURSERY_STAFF_DB",
    "NURSERY_VISITORS_DB",
    "PLATFORM_ASSETS_DIR",
    "PLATFORM_AUDIT_DB_FILE",
    "PLATFORM_AUTH_DB",
    "PLATFORM_AUTH_DB_FILE",
    "PLATFORM_CONFIG_DIR",
    "PLATFORM_DATA_DIR",
    "PLATFORM_DB_FILES_DIR",
    "PLATFORM_DOCUMENTS_DIR",
    "PLATFORM_DOCUMENT_TEMPLATES_DIR",
    "PLATFORM_EMAIL_CONFIG_PATH",
    "PLATFORM_EMAIL_TEMPLATES_DIR",
    "PLATFORM_LOGS_DIR",
    "PLATFORM_MISCONDUCT_DB_FILE",
    "PLATFORM_RATE_LIMITS_DB_FILE",
    "PLATFORM_ROOT",
    "PLATFORM_SMS_CONFIG_PATH",
    "PLATFORM_TEMPLATES_DIR",
    "PLATFORM_UI_TEMPLATES_DIR",
    "PRIMARY_ACADEMIC_YEAR_DB",
    "PRIMARY_ACTIVITY_FEED_DB",
    "PRIMARY_ADMISSIONS_DB",
    "PRIMARY_ANNOUNCEMENTS_DB",
    "PRIMARY_APPRAISALS_DB",
    "PRIMARY_ASSETS_DB",
    "PRIMARY_ATTACHMENTS_DB",
    "PRIMARY_AUDIT_REPORTS_DB",
    "PRIMARY_CALENDAR_DB",
    "PRIMARY_CENSUS_DB",
    "PRIMARY_COMPLAINTS_DB",
    "PRIMARY_COMPLIANCE_DB",
    "PRIMARY_CPD_DB",
    "PRIMARY_DATA_DIR",
    "PRIMARY_EMAIL_TEMPLATES_DIR",
    "PRIMARY_DATA_EXPORT_DB",
    "PRIMARY_DBS_CHECKS_DB",
    "PRIMARY_DEPARTMENTS_DB",
    "PRIMARY_DOCUMENT_HUB_DB",
    "PRIMARY_ENROLMENT_DB",
    "PRIMARY_EQUALITY_DIVERSITY_DB",
    "PRIMARY_EXPENSE_CLAIMS_DB",
    "PRIMARY_FEEDBACK_DB",
    "PRIMARY_FEES_DB",
    "PRIMARY_FUNDING_DB",
    "PRIMARY_GDPR_DB",
    "PRIMARY_GOVERNANCE_DB",
    "PRIMARY_HEALTH_SAFETY_DB",
    "PRIMARY_LETTER_TEMPLATES_DB",
    "PRIMARY_MESSAGES_DB",
    "PRIMARY_NOTICES_DB",
    "PRIMARY_NOTIFICATIONS_DB",
    "PRIMARY_ONBOARDING_DB",
    "PRIMARY_PACKAGE_ROOT",
    "PRIMARY_PARENTS_EVENINGS_DB",
    "PRIMARY_PARENT_CONTACTS_DB",
    "PRIMARY_POLICIES_DB",
    "PRIMARY_PROGRESS_DB",
    "PRIMARY_PUPILS_DB",
    "PRIMARY_RECEIPTS_DB",
    "PRIMARY_RECRUITMENT_DB",
    "PRIMARY_RISK_MANAGEMENT_DB",
    "PRIMARY_SCHOOL_COUNCIL_DB",
    "PRIMARY_SETTINGS_DB",
    "PRIMARY_STAFF_ABSENCE_DB",
    "PRIMARY_STAFF_DB",
    "PRIMARY_STAFF_HR_DB",
    "PRIMARY_STAFF_WELLBEING_DB",
    "PRIMARY_SURVEYS_DB",
    "PRIMARY_TODO_DB",
    "PRIMARY_TRANSPORT_DB",
    "PRIMARY_TRIPS_DB",
    "PRIMARY_VISITORS_DB",
    "PROGRAM_ROOT",
    "REPO_ROOT",
    "SECONDARY_ACADEMIC_YEAR_DB",
    "SECONDARY_ACTIVITY_FEED_DB",
    "SECONDARY_ADMISSIONS_DB",
    "SECONDARY_ANNOUNCEMENTS_DB",
    "SECONDARY_APPRAISALS_DB",
    "SECONDARY_ASSETS_DB",
    "SECONDARY_ATTACHMENTS_DB",
    "SECONDARY_AUDIT_REPORTS_DB",
    "SECONDARY_CALENDAR_DB",
    "SECONDARY_CENSUS_DB",
    "SECONDARY_COMPLAINTS_DB",
    "SECONDARY_COMPLIANCE_DB",
    "SECONDARY_CPD_DB",
    "SECONDARY_DATA_DIR",
    "SECONDARY_EMAIL_TEMPLATES_DIR",
    "SECONDARY_DATA_EXPORT_DB",
    "SECONDARY_DBS_CHECKS_DB",
    "SECONDARY_DEPARTMENTS_DB",
    "SECONDARY_DOCUMENT_HUB_DB",
    "SECONDARY_ENROLMENT_DB",
    "SECONDARY_EQUALITY_DIVERSITY_DB",
    "SECONDARY_EXPENSE_CLAIMS_DB",
    "SECONDARY_FEEDBACK_DB",
    "SECONDARY_FEES_DB",
    "SECONDARY_FUNDING_DB",
    "SECONDARY_GDPR_DB",
    "SECONDARY_GOVERNANCE_DB",
    "SECONDARY_HEALTH_SAFETY_DB",
    "SECONDARY_LETTER_TEMPLATES_DB",
    "SECONDARY_MESSAGES_DB",
    "SECONDARY_NOTICES_DB",
    "SECONDARY_NOTIFICATIONS_DB",
    "SECONDARY_ONBOARDING_DB",
    "SECONDARY_PACKAGE_ROOT",
    "SECONDARY_PARENTS_EVENINGS_DB",
    "SECONDARY_PARENT_CONTACTS_DB",
    "SECONDARY_POLICIES_DB",
    "SECONDARY_PROGRESS_DB",
    "SECONDARY_PUPILS_DB",
    "SECONDARY_RECEIPTS_DB",
    "SECONDARY_RECRUITMENT_DB",
    "SECONDARY_RISK_MANAGEMENT_DB",
    "SECONDARY_SCHOOL_COUNCIL_DB",
    "SECONDARY_SETTINGS_DB",
    "SECONDARY_STAFF_ABSENCE_DB",
    "SECONDARY_STAFF_DB",
    "SECONDARY_STAFF_HR_DB",
    "SECONDARY_STAFF_WELLBEING_DB",
    "SECONDARY_SURVEYS_DB",
    "SECONDARY_TODO_DB",
    "SECONDARY_TRANSPORT_DB",
    "SECONDARY_TRIPS_DB",
    "SECONDARY_VISITORS_DB",
    "SIXTH_FORM_ABSENCE_REQUESTS_DB",
    "SIXTH_FORM_ACADEMIC_YEAR_DB",
    "SIXTH_FORM_ACCESSIBILITY_DB",
    "SIXTH_FORM_ACTIVITY_FEED_DB",
    "SIXTH_FORM_ADMISSIONS_DB",
    "SIXTH_FORM_ADVANCED_SEARCH_DB",
    "SIXTH_FORM_ALUMNI_DB",
    "SIXTH_FORM_ANNOUNCEMENTS_DB",
    "SIXTH_FORM_APPRAISALS_DB",
    "SIXTH_FORM_APPRENTICESHIPS_DB",
    "SIXTH_FORM_ASSETS_DB",
    "SIXTH_FORM_ASSIGNMENTS_DB",
    "SIXTH_FORM_ATTACHMENTS_DB",
    "SIXTH_FORM_ATTENDANCE_CONCERNS_DB",
    "SIXTH_FORM_ATTENDANCE_DB",
    "SIXTH_FORM_AUDIT_REPORTS_DB",
    "SIXTH_FORM_AUTOMATION_RULES_DB",
    "SIXTH_FORM_BASELINE_ASSESSMENT_DB",
    "SIXTH_FORM_BEHAVIOUR_DB",
    "SIXTH_FORM_BULK_OPERATIONS_DB",
    "SIXTH_FORM_BURSARIES_DB",
    "SIXTH_FORM_CALENDAR_DB",
    "SIXTH_FORM_CAREERS_DB",
    "SIXTH_FORM_CENSUS_ILR_DB",
    "SIXTH_FORM_CLASS_GROUPS_DB",
    "SIXTH_FORM_COMPLAINTS_DB",
    "SIXTH_FORM_COMPLIANCE_DB",
    "SIXTH_FORM_COURSES_DB",
    "SIXTH_FORM_COURSEWORK_FILES_DIR",
    "SIXTH_FORM_COVER_AGENCY_DB",
    "SIXTH_FORM_COVER_DB",
    "SIXTH_FORM_CPD_DB",
    "SIXTH_FORM_DATA_DIR",
    "SIXTH_FORM_DATA_EXPORT_DB",
    "SIXTH_FORM_DBS_CHECKS_DB",
    "SIXTH_FORM_DEPARTMENTS_DB",
    "SIXTH_FORM_DESTINATIONS_DB",
    "SIXTH_FORM_DISCIPLINARY_DB",
    "SIXTH_FORM_DOCUMENT_HUB_DB",
    "SIXTH_FORM_EARLY_WARNING_DB",
    "SIXTH_FORM_EMAIL_TEMPLATES_DIR",
    "SIXTH_FORM_EMERGENCY_DB",
    "SIXTH_FORM_ENRICHMENTS_DB",
    "SIXTH_FORM_ENROLMENTS_DB",
    "SIXTH_FORM_EPQ_DB",
    "SIXTH_FORM_EQUALITY_DIVERSITY_DB",
    "SIXTH_FORM_EXAM_ENTRIES_DB",
    "SIXTH_FORM_EXAM_RESULTS_DB",
    "SIXTH_FORM_EXPENSE_CLAIMS_DB",
    "SIXTH_FORM_FEEDBACK_DB",
    "SIXTH_FORM_FEES_DB",
    "SIXTH_FORM_FIRST_AID_DB",
    "SIXTH_FORM_FUNDING_DB",
    "SIXTH_FORM_GDPR_DB",
    "SIXTH_FORM_GOVERNANCE_DB",
    "SIXTH_FORM_GRADEBOOK_DB",
    "SIXTH_FORM_HEALTH_SAFETY_DB",
    "SIXTH_FORM_HOMEWORK_DB",
    "SIXTH_FORM_ILP_DB",
    "SIXTH_FORM_INTERVENTION_TRACKING_DB",
    "SIXTH_FORM_LESSON_PLANS_DB",
    "SIXTH_FORM_LETTER_TEMPLATES_DB",
    "SIXTH_FORM_LIBRARY_DB",
    "SIXTH_FORM_MEDICAL_RECORDS_DB",
    "SIXTH_FORM_MESSAGES_DB",
    "SIXTH_FORM_MOCK_EXAMS_DB",
    "SIXTH_FORM_MULTI_LANGUAGE_DB",
    "SIXTH_FORM_NOTICES_DB",
    "SIXTH_FORM_NOTIFICATIONS_DB",
    "SIXTH_FORM_OBSERVATIONS_DB",
    "SIXTH_FORM_OFFERS_DB",
    "SIXTH_FORM_ONBOARDING_DB",
    "SIXTH_FORM_PACKAGE_ROOT",
    "SIXTH_FORM_PARENTS_EVENINGS_DB",
    "SIXTH_FORM_PARENT_CONTACTS_DB",
    "SIXTH_FORM_PARENT_PORTAL_DB",
    "SIXTH_FORM_PEER_MENTORING_DB",
    "SIXTH_FORM_PERSONAL_STATEMENTS_DB",
    "SIXTH_FORM_POLICIES_DB",
    "SIXTH_FORM_PREDICTED_GRADES_DB",
    "SIXTH_FORM_PREVENT_DUTY_DB",
    "SIXTH_FORM_PROGRESS_DB",
    "SIXTH_FORM_QUALITY_ASSURANCE_DB",
    "SIXTH_FORM_RECEIPTS_DB",
    "SIXTH_FORM_RECRUITMENT_DB",
    "SIXTH_FORM_REFERENCES_DB",
    "SIXTH_FORM_RISK_ANALYTICS_DB",
    "SIXTH_FORM_RISK_MANAGEMENT_DB",
    "SIXTH_FORM_ROOM_BOOKING_DB",
    "SIXTH_FORM_SAFEGUARDING_DB",
    "SIXTH_FORM_SEF_BUILDER_DB",
    "SIXTH_FORM_SELF_ASSESSMENT_DB",
    "SIXTH_FORM_SEND_DB",
    "SIXTH_FORM_SETTINGS_DB",
    "SIXTH_FORM_STAFF_ABSENCE_DB",
    "SIXTH_FORM_STAFF_DB",
    "SIXTH_FORM_STAFF_HR_DB",
    "SIXTH_FORM_STAFF_WELLBEING_DB",
    "SIXTH_FORM_STUDENTS_DB",
    "SIXTH_FORM_STUDENT_COUNCIL_DB",
    "SIXTH_FORM_STUDENT_SUPPORT_DB",
    "SIXTH_FORM_STUDENT_WELLBEING_DB",
    "SIXTH_FORM_STUDY_PLANNER_DB",
    "SIXTH_FORM_SUBJECTS_DB",
    "SIXTH_FORM_SURVEYS_DB",
    "SIXTH_FORM_SYSTEM_LOGS_DB",
    "SIXTH_FORM_TARGET_SETTING_DB",
    "SIXTH_FORM_TIMETABLE_DB",
    "SIXTH_FORM_TIMETABLE_OPTIMISER_DB",
    "SIXTH_FORM_TODO_DB",
    "SIXTH_FORM_TRANSPORT_DB",
    "SIXTH_FORM_TRIPS_DB",
    "SIXTH_FORM_TUTOR_GROUPS_DB",
    "SIXTH_FORM_UCAS_DB",
    "SIXTH_FORM_UCAS_WORKFLOW_DB",
    "SIXTH_FORM_UNIVERSITY_VISITS_DB",
    "SIXTH_FORM_VALUE_ADDED_DB",
    "SIXTH_FORM_VISITORS_DB",
    "SIXTH_FORM_WELLBEING_DB",
    "SIXTH_FORM_WORK_EXPERIENCE_DB",
    "SYSTEM_DB_PATHS",
    "SYSTEM_LABELS",
    "SYSTEM_ORDER",
    "UNIVERSITY_ANALYTICS_DIR",
    "UNIVERSITY_ANALYTICS_PLOTS_DIR",
    "UNIVERSITY_ANALYTICS_REPORTS_DIR",
    "UNIVERSITY_API_SERVER_CONFIG_FILE",
    "UNIVERSITY_ASSETS_DIR",
    "UNIVERSITY_ASSIGNMENT_TEMPLATES_DIR",
    "UNIVERSITY_BACKUP_ATTENDANCE_DIR",
    "UNIVERSITY_BACKUP_CALENDAR_DIR",
    "UNIVERSITY_BACKUP_DATABASE_DIR",
    "UNIVERSITY_BACKUP_DIR",
    "UNIVERSITY_BACKUP_FILES_DIR",
    "UNIVERSITY_BACKUP_FINANCE_DIR",
    "UNIVERSITY_BACKUP_HEALTH_DIR",
    "UNIVERSITY_BACKUP_LIBRARY_DIR",
    "UNIVERSITY_BACKUP_METADATA_FILE",
    "UNIVERSITY_BACKUP_SETTINGS_DIR",
    "UNIVERSITY_BACKUP_SUBMISSIONS_DIR",
    "UNIVERSITY_BACKUP_TEMPLATES_DIR",
    "UNIVERSITY_BASE_DIR",
    "UNIVERSITY_BRANDING_DIR",
    "UNIVERSITY_CHARTS_DIR",
    "UNIVERSITY_CHATBOT_CONFIG_PATH",
    "UNIVERSITY_CHATBOT_DATA_DIR",
    "UNIVERSITY_CHATBOT_MODELS_DIR",
    "UNIVERSITY_CHATBOT_UPLOAD_DIR",
    "UNIVERSITY_CONFIG_DIR",
    "UNIVERSITY_COURSE_EVALUATION_TEMPLATES_DIR",
    "UNIVERSITY_DATABASE_BACKUP_FILENAME",
    "UNIVERSITY_DATA_DIR",
    "UNIVERSITY_DATA_TEMPLATES_DIR",
    "UNIVERSITY_DB_BACKUPS_DIR",
    "UNIVERSITY_DB_DIR",
    "UNIVERSITY_DB_EXPORTS_DIR",
    "UNIVERSITY_DB_FILES_DIR",
    "UNIVERSITY_DEFAULT_DB_PATH",
    "UNIVERSITY_DOCUMENT_TEMPLATES_DIR",
    "UNIVERSITY_DR_CONFIG_FILE",
    "UNIVERSITY_EMAIL_CONFIG_FILE",
    "UNIVERSITY_EMAIL_CONFIG_PATH",
    "UNIVERSITY_EMAIL_DATA_DIR",
    "UNIVERSITY_EMAIL_REMINDER_TEMPLATES_DIR",
    "UNIVERSITY_EMAIL_TEMPLATES_DIR",
    "UNIVERSITY_EMAIL_TEMPLATE_MAPPING_FILE",
    "UNIVERSITY_EXPORTS_BAKERY_DIR",
    "UNIVERSITY_EXPORTS_DATABASE_DIR",
    "UNIVERSITY_EXPORTS_DIR",
    "UNIVERSITY_EXPORTS_PDF_DIR",
    "UNIVERSITY_EXPORTS_REPORTS_DIR",
    "UNIVERSITY_EXPORTS_SUBMISSIONS_DIR",
    "UNIVERSITY_EXPORTS_TICKETS_DIR",
    "UNIVERSITY_FINANCE_GUI_SETTINGS_FILE",
    "UNIVERSITY_FINANCE_TEMPLATES_DIR",
    "UNIVERSITY_HEALTH_DB_PATH",
    "UNIVERSITY_IMPORT_HISTORY_FILE",
    "UNIVERSITY_LANGUAGE_CONFIG_PATH",
    "UNIVERSITY_LICENSES_FILE",
    "UNIVERSITY_LOCALES_DIR",
    "UNIVERSITY_LOGGER_CONFIG_DIR",
    "UNIVERSITY_LOG_DIR",
    "UNIVERSITY_MAINTENANCE_WINDOWS_FILE",
    "UNIVERSITY_MEDICAL_TEMPLATES_DIR",
    "UNIVERSITY_NLTK_DATA_DIR",
    "UNIVERSITY_PROJECT_ROOT",
    "UNIVERSITY_QR_CODES_DIR",
    "UNIVERSITY_REMOTE_BACKUP_PATH",
    "UNIVERSITY_REPORTS_DIR",
    "UNIVERSITY_REPORT_CACHE_DIR",
    "UNIVERSITY_REPORT_TEMPLATES_DIR",
    "UNIVERSITY_SAFEGUARDING_DB_PATH",
    "UNIVERSITY_SAVED_REPORTS_FILE",
    "UNIVERSITY_SCHEDULED_REPORTS_FILE",
    "UNIVERSITY_SCRIPTS_DIR",
    "UNIVERSITY_SEED_TEMPLATES_DIR",
    "UNIVERSITY_SRC_DIR",
    "UNIVERSITY_STUDENT_DOCUMENTS_DIR",
    "UNIVERSITY_SUBMISSIONS_DIR",
    "UNIVERSITY_SYSTEM_DIR",
    "UNIVERSITY_TEMPLATES_DIR",
    "UNIVERSITY_TEMPLATE_REGISTRY_DIR",
    "UNIVERSITY_TEMP_DIR",
    "UNIVERSITY_TICKET_TEMPLATES_DIR",
    "UNIVERSITY_UI_TEMPLATES_DIR",
    "UNIVERSITY_UPLOADS_DIR",
    "UNIVERSITY_UPLOAD_DIR",
    "UNIVERSITY_USER_BACKUP_TEMPLATES_DIR",
    "VAR_DIR",
    "ensure_all_directories",
    "ensure_apprenticeships_directories",
    "ensure_fe_college_directories",
    "ensure_nursery_directories",
    "ensure_platform_directories",
    "ensure_primary_directories",
    "ensure_secondary_directories",
    "ensure_sixth_form_directories",
    "ensure_university_directories",
]
