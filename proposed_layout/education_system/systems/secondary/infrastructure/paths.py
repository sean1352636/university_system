"""Centralised file/directory paths for the Secondary School System.

All modules that need to read or write files inside this system should
import from here rather than building paths with ``Path(__file__).parent``.
That keeps the layout in one place — if the data/ directory moves or
needs to honour an environment override, only this module changes.

Environment overrides
---------------------
``EDU_SECONDARY_DATA_DIR``  Absolute path to use for the data directory
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
    os.environ.get("EDU_SECONDARY_DATA_DIR")
    or (PACKAGE_ROOT / "data")
).resolve()

# ── Individual files ────────────────────────────────────────────────
# Single SQLite file shared by pupils, admissions, enrolment, onboarding,
# and bulk operations — all live in the same DB so cross-table joins and
# FK cascades work without coordinating two connections.
PUPILS_DB: Path = DATA_DIR / "secondary.db"
ADMISSIONS_DB: Path = PUPILS_DB
ENROLMENT_DB: Path = PUPILS_DB
ONBOARDING_DB: Path = PUPILS_DB
ACADEMIC_YEAR_DB: Path = PUPILS_DB
CALENDAR_DB: Path = PUPILS_DB

# Equality & Diversity: per-incident log of discrimination /
# harassment / bullying / hate incidents tagged with protected
# characteristic, plus investigation and actions-taken workflow.
EQUALITY_DIVERSITY_DB: Path = PUPILS_DB

# Complaints: formal complaints register with stage (Informal /
# Formal Stage 1 / Formal Stage 2 / Appeal), category, outcome
# (Upheld / Partially Upheld / Not Upheld / Withdrawn) and
# escalation tracking.
COMPLAINTS_DB: Path = PUPILS_DB

# Feedback: general low-formality feedback log (positive /
# suggestions / questions / concerns) tagged by category and
# source, with optional star rating and lightweight response flow.
FEEDBACK_DB: Path = PUPILS_DB

# Surveys: two-table schema — survey definitions (with JSON-encoded
# question spec) and per-response answer rows.
SURVEYS_DB: Path = PUPILS_DB

# School Council: members, meetings/agenda items and actions.
SCHOOL_COUNCIL_DB: Path = PUPILS_DB

# Transport: routes, stops, pupil assignments and incidents.
TRANSPORT_DB: Path = PUPILS_DB

# Staff Directory: core staff records (name, role, department, etc.)
STAFF_DB: Path = PUPILS_DB

# Staff HR: employment terms, contracts, leave balances, etc.
STAFF_HR_DB: Path = PUPILS_DB

# Departments: department definitions and head-of-department links.
DEPARTMENTS_DB: Path = PUPILS_DB

# Staff comms / HR-adjacent modules — share the secondary DB.
STAFF_ABSENCE_DB: Path = PUPILS_DB
STAFF_WELLBEING_DB: Path = PUPILS_DB
RECRUITMENT_DB: Path = PUPILS_DB
APPRAISALS_DB: Path = PUPILS_DB
CPD_DB: Path = PUPILS_DB
DBS_CHECKS_DB: Path = PUPILS_DB
VISITORS_DB: Path = PUPILS_DB
PARENT_CONTACTS_DB: Path = PUPILS_DB
PARENTS_EVENINGS_DB: Path = PUPILS_DB
NOTICES_DB: Path = PUPILS_DB
ANNOUNCEMENTS_DB: Path = PUPILS_DB
NOTIFICATIONS_DB: Path = PUPILS_DB
ACTIVITY_FEED_DB: Path = PUPILS_DB
MESSAGES_DB: Path = PUPILS_DB
LETTER_TEMPLATES_DB: Path = PUPILS_DB
DOCUMENT_HUB_DB: Path = PUPILS_DB
ATTACHMENTS_DB: Path = PUPILS_DB

# Finance modules — share the secondary DB.
FEES_DB: Path = PUPILS_DB
TRIPS_DB: Path = PUPILS_DB
RECEIPTS_DB: Path = PUPILS_DB
EXPENSE_CLAIMS_DB: Path = PUPILS_DB
FUNDING_DB: Path = PUPILS_DB
CENSUS_DB: Path = PUPILS_DB

# Reports & Analytics modules.
PROGRESS_DB: Path = PUPILS_DB
AUDIT_REPORTS_DB: Path = PUPILS_DB
DATA_EXPORT_DB: Path = PUPILS_DB

# Shared system modules.
SETTINGS_DB: Path = PUPILS_DB

# Governance / System-section modules.
COMPLIANCE_DB: Path = PUPILS_DB
GOVERNANCE_DB: Path = PUPILS_DB
POLICIES_DB: Path = PUPILS_DB
GDPR_DB: Path = PUPILS_DB
RISK_MANAGEMENT_DB: Path = PUPILS_DB
HEALTH_SAFETY_DB: Path = PUPILS_DB
ASSETS_DB: Path = PUPILS_DB
TODO_DB: Path = PUPILS_DB


def ensure_directories() -> None:
    """Create the data directory if it doesn't exist yet."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
