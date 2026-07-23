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

# Email templates live in the package itself (not the data dir), so
# they ship with the code rather than being editable runtime state.
EMAIL_TEMPLATES_DIR: Path = PACKAGE_ROOT / "data" / "templates" / "email"

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

# University visits: trips to universities (open days, taster days,
# applicant visit days, UCAS fairs) with a per-student attendee list.
UNIVERSITY_VISITS_DB: Path = STUDENTS_DB

# Extended Project Qualification: one project per student, plus
# production-log entries and milestones.
EPQ_DB: Path = STUDENTS_DB

# Work experience: employer directory + per-student placements.
WORK_EXPERIENCE_DB: Path = STUDENTS_DB

# Room & resource booking: bookable resources + bookings with clash
# detection.
ROOM_BOOKING_DB: Path = STUDENTS_DB

# KS5 leaver destinations: one record per (student, checkpoint) for
# statutory destination-measure reporting.
DESTINATIONS_DB: Path = STUDENTS_DB

# Medical records: per-student profile + conditions / medications /
# allergies. Sensitive — access should be gated by the auth layer.
MEDICAL_RECORDS_DB: Path = STUDENTS_DB

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

# Student Wellbeing: student-facing self-service journal — daily mood
# entries, personal wellbeing goals, and saved help resources. Distinct
# from the staff-facing `WELLBEING_DB` schema (which holds pastoral
# check-ins, sessions and flags).
STUDENT_WELLBEING_DB: Path = STUDENTS_DB

# Prevent Duty: statutory anti-radicalisation register. Three linked
# tables — Prevent concerns (per student), Channel referrals (one per
# escalated concern), and staff Prevent training records.
PREVENT_DUTY_DB: Path = STUDENTS_DB

# System logs: every Python ``logging`` record emitted by sixth-form
# modules can be captured to this table via the SQLite log handler in
# ``core.log_store``. Lives in the same DB so the audit trail moves
# with the data.
SYSTEM_LOGS_DB: Path = STUDENTS_DB

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

# Absence requests: planned-absence requests submitted on behalf of
# students (medical, university open day, family circumstances, etc.)
# with an approval workflow.
ABSENCE_REQUESTS_DB: Path = STUDENTS_DB

# Academic year: year metadata, terms within a year, and holiday/break
# periods. One year can be marked "current"; reports anchor to it.
ACADEMIC_YEAR_DB: Path = STUDENTS_DB

# Accessibility: per-student SEND/EHCP profile + the individual
# accommodations (exam access, classroom, assistive tech, etc.) they
# are entitled to.
ACCESSIBILITY_DB: Path = STUDENTS_DB

# Activity feed: system-wide audit/event log. One row per user action
# (login, CRUD, approvals, status changes, etc.) for filtering and
# review.
ACTIVITY_FEED_DB: Path = STUDENTS_DB

# Advanced search: cross-domain query layer. Stores saved searches and
# a small history table; results themselves come live from the other
# domain modules.
ADVANCED_SEARCH_DB: Path = STUDENTS_DB

# Admissions: pre-enrolment pipeline. Applicants progress through
# review/interview/offer/accept and can be converted to a `students`
# row once enrolled.
ADMISSIONS_DB: Path = STUDENTS_DB

# Onboarding: post-enrolment checklists. One row per student-checklist
# pair, with a 1:N child table of individual tick-box items.
ONBOARDING_DB: Path = STUDENTS_DB

# Bulk operations: audit log of cross-record actions (mass behaviour
# entries, mass accommodation grants, field updates, etc.).
BULK_OPERATIONS_DB: Path = STUDENTS_DB

# Alumni: leavers' contact + destinations data. Created when a student
# leaves the sixth form, typically via Bulk Operations archive.
ALUMNI_DB: Path = STUDENTS_DB

# Calendar: school-wide events (trips, exams, INSET, parents' evenings,
# meetings, deadlines, etc.).
CALENDAR_DB: Path = STUDENTS_DB

# Lesson plans: per-lesson teacher notes (objectives, activities,
# resources, homework). Anchored to a subject and optionally a course
# or class group.
LESSON_PLANS_DB: Path = STUDENTS_DB

# Cover agencies: external supply-teacher agencies the school works
# with (contact + rate + rating).
COVER_AGENCY_DB: Path = STUDENTS_DB

# Cover: per-absence cover requests — who's out, which periods need
# covering, and how (internal, supply agency, class split, etc.).
COVER_DB: Path = STUDENTS_DB

# Assignments: coursework-style assignments with per-student
# submission tracking (parallels but is broader than `homework`).
ASSIGNMENTS_DB: Path = STUDENTS_DB

# Enrichments: extra-curricular activities and the per-student
# enrolment in each (clubs, DofE, sports squads, etc.).
ENRICHMENTS_DB: Path = STUDENTS_DB

# Library: books / resources catalogue + per-student loans.
LIBRARY_DB: Path = STUDENTS_DB

# Study Planner: per-student study tasks and sessions (revision plan).
STUDY_PLANNER_DB: Path = STUDENTS_DB

# Baseline assessment: initial diagnostic results per student per
# subject (GCSE points, CAT4, MidYIS, initial test, etc.) — the source
# of truth that targets are anchored against.
BASELINE_ASSESSMENT_DB: Path = STUDENTS_DB

# Target setting: per-student, per-subject grade targets (minimum,
# aspirational, current) plus review history.
TARGET_SETTING_DB: Path = STUDENTS_DB

# ILP: Individual Learning Plans — holistic per-student plans with
# goals and periodic reviews (academic, SEND, pastoral, etc.).
ILP_DB: Path = STUDENTS_DB

# Intervention tracking: targeted, time-bound interventions per
# student with per-session attendance and impact grading.
INTERVENTION_TRACKING_DB: Path = STUDENTS_DB

# Value added: per-student per-subject prior-attainment / expected /
# actual grade comparison (ALPS / VESPA-style residual).
VALUE_ADDED_DB: Path = STUDENTS_DB

# Early warning: at-risk alerts raised from attendance, behaviour,
# grades, etc. with acknowledge / resolve workflow.
EARLY_WARNING_DB: Path = STUDENTS_DB

# Observations: teacher lesson observations (QA / drop-ins / peer
# observations / formal appraisal observations).
OBSERVATIONS_DB: Path = STUDENTS_DB

# Self assessment: per-student self-evaluation submissions across
# multiple dimensions (effort, organisation, wellbeing, subject
# confidence, etc.) with optional reviewer feedback.
SELF_ASSESSMENT_DB: Path = STUDENTS_DB

# Quality assurance: QA cycles (work scrutiny / learning walk / book
# look / planning review) with per-finding judgement, action, owner,
# evidence and impact follow-up.
QUALITY_ASSURANCE_DB: Path = STUDENTS_DB

# SEF Builder: Self-Evaluation Form. Stores per-area drafts (Quality
# of Education, Behaviour & Attitudes, Personal Development,
# Leadership & Management, Sixth Form Provision) with judgements,
# strengths, areas to develop, evidence and improvement actions.
SEF_BUILDER_DB: Path = STUDENTS_DB

# SEND register: per-student SEND register entries with status
# (Monitoring / SEN Support / EHCP / Exited), primary & secondary
# need codes, assess-plan-do-review cycle, provision summary, key
# worker / SENCo, external agencies and review schedule.
SEND_DB: Path = STUDENTS_DB

# Disciplinary: formal disciplinary cases beyond the behaviour log —
# warnings, detentions, internal exclusions, suspensions, permanent
# exclusions, behaviour contracts. Each case has a workflow from
# Reported through Sanction Served to Closed (or Appealed).
DISCIPLINARY_DB: Path = STUDENTS_DB

# Student support: lighter-touch academic / pastoral support
# referrals (catch-up sessions, study skills, exam prep tutoring,
# organisation support, welfare referrals) with priority, referrer
# and assigned support staff. Workflow Referred → Triaged →
# In Progress → Resolved → Closed.
STUDENT_SUPPORT_DB: Path = STUDENTS_DB

# Peer mentoring: mentor↔mentee pairings (both `students` rows)
# plus a per-pairing session log. Programmes include UCAS Buddies,
# Subject Tutoring, Reading Buddies, Wellbeing Mentor, etc.
PEER_MENTORING_DB: Path = STUDENTS_DB

# First aid: per-student first aid incidents (head bumps, cuts,
# allergic reactions, asthma, fainting, etc.) with first aider,
# treatment given, parent-informed and follow-up tracking.
FIRST_AID_DB: Path = STUDENTS_DB

# Emergency: site-wide emergency incidents (fire alarm, lockdown,
# intruder, evacuation, medical emergency, drills). Includes a
# response timeline and post-incident debrief.
EMERGENCY_DB: Path = STUDENTS_DB

# Equality & Diversity: per-incident log of discrimination /
# harassment / bullying / hate incidents tagged with protected
# characteristic, plus investigation and actions-taken workflow.
EQUALITY_DIVERSITY_DB: Path = STUDENTS_DB

# Complaints: formal complaints register with stage (Informal /
# Formal Stage 1 / Formal Stage 2 / Appeal), category, outcome
# (Upheld / Partially Upheld / Not Upheld / Withdrawn) and
# escalation tracking.
COMPLAINTS_DB: Path = STUDENTS_DB

# Feedback: general low-formality feedback log (positive /
# suggestions / questions / concerns) tagged by category and
# source, with optional star rating and lightweight response flow.
FEEDBACK_DB: Path = STUDENTS_DB

# Surveys: two-table schema — survey definitions (with JSON-encoded
# question spec) and per-response answer rows. Used for student
# voice, parent surveys, staff pulse checks, etc.
SURVEYS_DB: Path = STUDENTS_DB

# Student council: three-table schema — members (FK to students),
# meetings (free-standing), and motions (FK cascade on meetings).
# Tracks council membership, meetings + minutes, and per-motion
# votes / outcomes.
STUDENT_COUNCIL_DB: Path = STUDENTS_DB

# Transport: routes (operator/timetable/cost) and per-student
# transport arrangements (mode, pickup point, days, fee status).
TRANSPORT_DB: Path = STUDENTS_DB

# Staff HR: per-staff HR record (employment status, salary scale,
# DBS expiry, right-to-work, safeguarding training, reviews) and
# a leave / absence events log (annual / sick / parental / TOIL).
STAFF_HR_DB: Path = STUDENTS_DB

# Departments: department definitions + department membership
# mapping (staff ↔ department) for joint-department teachers and
# departmental responsibility roles (HoD / 2i/c / Teacher / TA).
DEPARTMENTS_DB: Path = STUDENTS_DB

# Staff absence: operational daily absence tracker (who's out today,
# expected return, cover arranged, RTW meeting). Distinct from the
# HR leave log — focused on day-to-day cover & notification.
STAFF_ABSENCE_DB: Path = STUDENTS_DB

# Staff wellbeing: per-staff wellbeing check-ins, concern flags,
# workload reviews, EAP / OH referrals. Confidential by default.
STAFF_WELLBEING_DB: Path = STUDENTS_DB

# Recruitment: vacancies + per-vacancy applicants (FK cascade)
# with shortlisting / interview / offer / start-date workflow.
RECRUITMENT_DB: Path = STUDENTS_DB

# Appraisals: per-staff per-cycle appraisal records plus per-
# appraisal objectives (FK cascade). Includes mid-year / end-year
# review dates, overall grade and pay-progression decision.
APPRAISALS_DB: Path = STUDENTS_DB

# CPD: continuing-professional-development activities (catalogue)
# plus per-staff attendance records (FK cascade on activities and
# staff). Captures hours, evaluation rating and impact on practice.
CPD_DB: Path = STUDENTS_DB

# DBS Checks: the safeguarding-compliance DBS register. One row
# per DBS check per staff member (FK cascade). Tracks level,
# expiry, update-service subscription and sign-off.
DBS_CHECKS_DB: Path = STUDENTS_DB

# Visitors: sign-in / sign-out log for everyone on site that
# isn't a student or member of staff. Tracks DBS / ID seen,
# safeguarding briefing, host, escort, badge and departure
# overdue.
VISITORS_DB: Path = STUDENTS_DB

# Announcements: site-wide announcements / banners / news.
# Audience flags (students / staff / parents / governors /
# public), priority, pinned + banner flags, publish & expiry
# scheduling with auto-expiry.
ANNOUNCEMENTS_DB: Path = STUDENTS_DB

# Notifications: per-recipient targeted notifications inbox.
# Distinct from messages (conversations) and announcements
# (broadcast). One row per (recipient, notification).
NOTIFICATIONS_DB: Path = STUDENTS_DB

# Letter templates: reusable letter / email templates with
# {{placeholder}} merge fields and a simple render helper.
LETTER_TEMPLATES_DB: Path = STUDENTS_DB

# Document Hub: central registry of versioned documents
# (policies, handbooks, forms) with category/audience scoping.
DOCUMENT_HUB_DB: Path = STUDENTS_DB

# Attachments: per-record file references attached to any
# linked entity (student, staff, notice, behaviour, etc.).
ATTACHMENTS_DB: Path = STUDENTS_DB

# Census / ILR: statutory data returns (autumn / spring /
# summer school census, ILR aims and learner records).
CENSUS_ILR_DB: Path = STUDENTS_DB

# Expense claims: staff and student expense reimbursement.
EXPENSE_CLAIMS_DB: Path = STUDENTS_DB

# Funding: 16-19 funding band tracking, bursary allocations
# and external grants.
FUNDING_DB: Path = STUDENTS_DB

# Audit Reports: canned compliance reports built on top of the
# activity feed. Saved report definitions and snapshot runs.
AUDIT_REPORTS_DB: Path = STUDENTS_DB

# Data Export: bulk exports of one or more domain datasets to a
# folder, with presets and a job/run history.
DATA_EXPORT_DB: Path = STUDENTS_DB

# Compliance: regulatory and operational compliance items
# (policy reviews, training, inspections, GDPR retention, …)
# with owners, due dates and status.
COMPLIANCE_DB: Path = STUDENTS_DB

# Governance: governing-body / trust board records — members, terms,
# meetings and decisions.
GOVERNANCE_DB: Path = STUDENTS_DB

# Policies: policy register — versioned policy documents with owner,
# review cadence, status and approval audit trail.
POLICIES_DB: Path = STUDENTS_DB

# GDPR: data-subject requests, records of processing activities,
# breach log and consent records.
GDPR_DB: Path = STUDENTS_DB

# Risk management: risk register with assessment scoring, mitigation
# actions and review history.
RISK_MANAGEMENT_DB: Path = STUDENTS_DB

# Health & Safety: incident/hazard register with assessor, severity,
# RIDDOR-reportable flag, corrective actions and review. Companion
# child table of corrective actions / sign-offs per incident.
HEALTH_SAFETY_DB: Path = STUDENTS_DB

# Assets: fixed-asset register (laptops, projectors, lab kit, etc.)
# with location, custodian, purchase, depreciation, condition,
# status (In Use / In Storage / Repair / Disposed) and a per-asset
# maintenance log.
ASSETS_DB: Path = STUDENTS_DB

# Multi-Language: supported locales, translation entries, and per-user
# language preferences.
MULTI_LANGUAGE_DB: Path = STUDENTS_DB

# To-Do: lightweight personal / shared task list (status, priority,
# owner, assignee, due date).
TODO_DB: Path = STUDENTS_DB

# Risk analytics: predictive risk snapshots derived from attendance,
# behaviour, baseline, mock and predicted-grade data.
RISK_ANALYTICS_DB: Path = STUDENTS_DB

# Timetable optimiser: saved auto-generated timetable plans and their
# proposed slot assignments (staging before committing to the live
# timetable_slots table).
TIMETABLE_OPTIMISER_DB: Path = STUDENTS_DB

# UCAS workflow: per-student application checklist / sign-off pipeline
# tying together UCAS, references, predicted grades and statements.
UCAS_WORKFLOW_DB: Path = STUDENTS_DB

# Automation rules: trigger → condition → action rules plus the audit
# log of actions the engine has fired.
AUTOMATION_RULES_DB: Path = STUDENTS_DB

# Parent portal: parent/guardian login accounts and the students each
# account is allowed to view.
PARENT_PORTAL_DB: Path = STUDENTS_DB


def ensure_directories() -> None:
    """Create any directories listed above. Safe to call repeatedly."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)


__all__ = [
    "PACKAGE_ROOT",
    "DATA_DIR",
    "EMAIL_TEMPLATES_DIR",
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
    "UNIVERSITY_VISITS_DB",
    "EPQ_DB",
    "WORK_EXPERIENCE_DB",
    "ROOM_BOOKING_DB",
    "DESTINATIONS_DB",
    "MEDICAL_RECORDS_DB",
    "TUTOR_GROUPS_DB",
    "BEHAVIOUR_DB",
    "SAFEGUARDING_DB",
    "WELLBEING_DB",
    "STUDENT_WELLBEING_DB",
    "PREVENT_DUTY_DB",
    "SYSTEM_LOGS_DB",
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
    "ABSENCE_REQUESTS_DB",
    "ACADEMIC_YEAR_DB",
    "ACCESSIBILITY_DB",
    "ACTIVITY_FEED_DB",
    "ADVANCED_SEARCH_DB",
    "ADMISSIONS_DB",
    "ONBOARDING_DB",
    "BULK_OPERATIONS_DB",
    "ALUMNI_DB",
    "CALENDAR_DB",
    "LESSON_PLANS_DB",
    "COVER_AGENCY_DB",
    "COVER_DB",
    "ASSIGNMENTS_DB",
    "ENRICHMENTS_DB",
    "LIBRARY_DB",
    "STUDY_PLANNER_DB",
    "BASELINE_ASSESSMENT_DB",
    "TARGET_SETTING_DB",
    "ILP_DB",
    "INTERVENTION_TRACKING_DB",
    "VALUE_ADDED_DB",
    "EARLY_WARNING_DB",
    "OBSERVATIONS_DB",
    "SELF_ASSESSMENT_DB",
    "QUALITY_ASSURANCE_DB",
    "SEF_BUILDER_DB",
    "SEND_DB",
    "DISCIPLINARY_DB",
    "STUDENT_SUPPORT_DB",
    "PEER_MENTORING_DB",
    "FIRST_AID_DB",
    "EMERGENCY_DB",
    "EQUALITY_DIVERSITY_DB",
    "COMPLAINTS_DB",
    "FEEDBACK_DB",
    "SURVEYS_DB",
    "STUDENT_COUNCIL_DB",
    "TRANSPORT_DB",
    "STAFF_HR_DB",
    "DEPARTMENTS_DB",
    "STAFF_ABSENCE_DB",
    "STAFF_WELLBEING_DB",
    "RECRUITMENT_DB",
    "APPRAISALS_DB",
    "CPD_DB",
    "DBS_CHECKS_DB",
    "VISITORS_DB",
    "ANNOUNCEMENTS_DB",
    "NOTIFICATIONS_DB",
    "LETTER_TEMPLATES_DB",
    "DOCUMENT_HUB_DB",
    "ATTACHMENTS_DB",
    "CENSUS_ILR_DB",
    "EXPENSE_CLAIMS_DB",
    "FUNDING_DB",
    "AUDIT_REPORTS_DB",
    "DATA_EXPORT_DB",
    "COMPLIANCE_DB",
    "GOVERNANCE_DB",
    "POLICIES_DB",
    "GDPR_DB",
    "RISK_MANAGEMENT_DB",
    "HEALTH_SAFETY_DB",
    "ASSETS_DB",
    "MULTI_LANGUAGE_DB",
    "TODO_DB",
    "RISK_ANALYTICS_DB",
    "TIMETABLE_OPTIMISER_DB",
    "UCAS_WORKFLOW_DB",
    "AUTOMATION_RULES_DB",
    "PARENT_PORTAL_DB",
    "ensure_directories",
]
