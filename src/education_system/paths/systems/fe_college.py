"""FE College (Further Education) paths.

Part of :mod:`education_system.paths`; import names from the package, not from here.
"""

from __future__ import annotations

from pathlib import Path
import os

from education_system.paths.core import (
    _SYSTEMS_ROOT,
    VAR_DIR,
)

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
# touching code. Runtime state lives under var (ADR 0018).
FE_COLLEGE_DATA_DIR: Path = Path(
    os.environ.get("EDU_FE_COLLEGE_DATA_DIR")
    or (VAR_DIR / "data" / "fe_college")
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

# User activity log: one line per thing a signed-in user does (see
# systems/fe_college/infrastructure/logging/activity_log.py).
FE_COLLEGE_LOG_DIR: Path = Path(
    os.environ.get("EDU_FE_COLLEGE_LOG_DIR")
    or (VAR_DIR / "logs" / "fe_college")
).resolve()
FE_COLLEGE_ACTIVITY_LOG: Path = FE_COLLEGE_LOG_DIR / "activity.log"

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
