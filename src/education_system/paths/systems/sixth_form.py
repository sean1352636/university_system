"""Sixth Form College paths.

Part of :mod:`education_system.paths`; import names from the package, not from here.
"""

from __future__ import annotations

from pathlib import Path
import os

from education_system.paths.core import (
    SIXTH_FORM_PACKAGE_ROOT,
    VAR_DIR,
)

# ═════════════════════════════════════════════════════════════════════
# Sixth Form College
# ═════════════════════════════════════════════════════════════════════

# ── Data directory ──────────────────────────────────────────────────
# Holds the local SQLite DB(s). Overridable via env so tests / installers
# can redirect it without touching code.
#
# Runtime state lives under ``var`` (ADR 0018), never inside the
# importable package. SYSTEM_DB_PATHS below is derived from this constant, so
# the cross-system registry and the per-system constant can no longer drift.
SIXTH_FORM_DATA_DIR: Path = Path(
    os.environ.get("EDU_SIXTHFORM_DATA_DIR")
    or (VAR_DIR / "data" / "sixth_form")
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
