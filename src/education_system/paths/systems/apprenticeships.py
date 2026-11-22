"""Apprenticeships paths.

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
# touching code. Runtime state lives under var (ADR 0018).
APPRENTICESHIPS_DATA_DIR: Path = Path(
    os.environ.get("EDU_APPRENTICESHIPS_DATA_DIR")
    or (VAR_DIR / "data" / "apprenticeships")
).resolve()

# Portfolio evidence file store: the documents an apprentice uploads as
# proof against their KSBs. Metadata rows live in the DB
# (``portfolio_evidence``); the bytes live here. Runtime user data.
APPRENTICESHIPS_EVIDENCE_DIR: Path = APPRENTICESHIPS_DATA_DIR / "evidence"

# Generated funding-audit evidence packs (one ZIP/PDF per export).
APPRENTICESHIPS_EXPORTS_DIR: Path = APPRENTICESHIPS_DATA_DIR / "exports"

# Uploaded record documents (agreements, ID, certificates, EPA paperwork).
# Metadata rows live in the DB (``documents``); the bytes live here under
# generated names — never the uploader's filename. Runtime user data.
APPRENTICESHIPS_DOCUMENTS_DIR: Path = APPRENTICESHIPS_DATA_DIR / "documents"

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

# User activity log: one line per thing a signed-in user does (see
# systems/apprenticeships/infrastructure/logging/activity_log.py).
APPRENTICESHIPS_LOG_DIR: Path = Path(
    os.environ.get("EDU_APPRENTICESHIPS_LOG_DIR")
    or (VAR_DIR / "logs" / "apprenticeships")
).resolve()
APPRENTICESHIPS_ACTIVITY_LOG: Path = APPRENTICESHIPS_LOG_DIR / "activity.log"

# Template assets ship with the code, not as editable runtime state.
APPRENTICESHIPS_PACKAGE_ROOT: Path = _SYSTEMS_ROOT / "apprenticeships"
APPRENTICESHIPS_EMAIL_TEMPLATES_DIR: Path = (
    APPRENTICESHIPS_PACKAGE_ROOT / "assets" / "templates" / "email"
)
