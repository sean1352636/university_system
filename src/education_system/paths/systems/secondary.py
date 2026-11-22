"""Secondary School paths.

Part of :mod:`education_system.paths`; import names from the package, not from here.
"""

from __future__ import annotations

from pathlib import Path
import os

from education_system.paths.core import (
    SECONDARY_PACKAGE_ROOT,
    VAR_DIR,
)

# ═════════════════════════════════════════════════════════════════════
# Secondary School
# ═════════════════════════════════════════════════════════════════════

# ── Data directory ──────────────────────────────────────────────────
# Holds the local SQLite DB(s). Overridable via env so tests / installers
# can redirect it without touching code.
#
# Runtime state lives under ``var`` (ADR 0018), never inside the
# importable package. SYSTEM_DB_PATHS below is derived from this constant, so
# the cross-system registry and the per-system constant can no longer drift.
SECONDARY_DATA_DIR: Path = Path(
    os.environ.get("EDU_SECONDARY_DATA_DIR")
    or (VAR_DIR / "data" / "secondary")
).resolve()

# ── Individual files ────────────────────────────────────────────────
# Single SQLite file shared by pupils, admissions, enrolment, onboarding,
# and bulk operations — all live in the same DB so cross-table joins and
# FK cascades work without coordinating two connections.
SECONDARY_PUPILS_DB: Path = SECONDARY_DATA_DIR / "secondary.db"

# User activity log: one line per thing a signed-in user does (see
# systems/secondary/infrastructure/activity_log.py).
SECONDARY_LOG_DIR: Path = Path(
    os.environ.get("EDU_SECONDARY_LOG_DIR")
    or (VAR_DIR / "logs" / "secondary")
).resolve()
SECONDARY_ACTIVITY_LOG: Path = SECONDARY_LOG_DIR / "activity.log"
# Sandbox delivery mode writes each outgoing e-mail here as an .eml file.
SECONDARY_EMAIL_SANDBOX_DIR: Path = SECONDARY_DATA_DIR / "email_sandbox"
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

# JSON e-mail templates (admissions, welcome, reports, behaviour notes...).
# They ship with the code in secondary/resources/ (shared by every module), not
# the runtime data dir, so they must not hang off the env-overridable SECONDARY_DATA_DIR.
SECONDARY_EMAIL_TEMPLATES_DIR: Path = SECONDARY_PACKAGE_ROOT / "resources" / "email_templates"
