"""Idempotent schema bootstrap for Collaborative (Partner) Provision.

Programme governance already models a programme's versions, approvals and
teach-out, but only ever as something *we* deliver ourselves. Nothing
recorded that a programme is delivered by somebody else under our award —
franchised, validated, joint, dual or articulated — which is the thing an
auditor asks about first and the thing that carries the most risk.

Five tables on the central university DB:

* ``partner_institutions``   — the organisation, and its due-diligence state
* ``partnership_agreements`` — the contract: type, term, student numbers
* ``collaborative_programmes`` — a programme delivered under an agreement
* ``partner_cohorts``        — an intake at a partner, with headcount
* ``partner_reviews``        — due diligence and annual monitoring visits

``collaborative_programmes.programme_code`` is a soft link to
``governed_programmes.programme_code``; it is deliberately not a foreign
key, because a partner may deliver a programme that predates programme
governance.
"""

from __future__ import annotations

import logging

from education_system.paths import UNIVERSITY_DEFAULT_DB_PATH
from education_system.systems.university.infrastructure.database.db import (
    get_connection,
    sqlite3,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------

# How the provision is delivered. The distinction matters: under franchise
# we own the curriculum and the partner teaches it; under validation the
# partner owns the curriculum and we award against it.
DELIVERY_MODELS = (
    "Franchise",
    "Validation",
    "Joint Award",
    "Dual Award",
    "Articulation",
    "Distance/Flexible with support",
    "Placement Provider",
    "Study Abroad Exchange",
)

PARTNER_TYPES = (
    "UK Further Education College",
    "UK Higher Education Provider",
    "Overseas Higher Education Provider",
    "Private Training Provider",
    "Employer",
    "NHS / Public Body",
    "Other",
)

AGREEMENT_STATUSES = (
    "Under Negotiation",
    "Due Diligence",
    "Approved",
    "Active",
    "Under Review",
    "Suspended",
    "Teach-Out",
    "Terminated",
)

RISK_LEVELS = ("Low", "Medium", "High")

REVIEW_TYPES = (
    "Initial Due Diligence",
    "Annual Monitoring",
    "Periodic Review",
    "Link Tutor Visit",
    "Student Voice Review",
    "Financial Health Check",
    "Exit / Teach-Out Review",
)

REVIEW_OUTCOMES = (
    "Approved",
    "Approved with Conditions",
    "Approved with Recommendations",
    "Deferred",
    "Not Approved",
)


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_CREATE_PARTNERS = """
CREATE TABLE IF NOT EXISTS partner_institutions (
    partner_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name                TEXT    NOT NULL,
    partner_type        TEXT,
    country             TEXT,
    city                TEXT,
    ukprn               TEXT,
    website             TEXT,
    contact_name        TEXT,
    contact_email       TEXT,
    contact_phone       TEXT,
    risk_level          TEXT    DEFAULT 'Medium',
    due_diligence_date  TEXT,
    due_diligence_due   TEXT,
    notes               TEXT,
    active              INTEGER NOT NULL DEFAULT 1,
    created_at          TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(name, country)
);
"""

_CREATE_AGREEMENTS = """
CREATE TABLE IF NOT EXISTS partnership_agreements (
    agreement_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    partner_id          INTEGER NOT NULL,
    reference           TEXT,
    delivery_model      TEXT    NOT NULL,
    status              TEXT    NOT NULL DEFAULT 'Under Negotiation',
    start_date          TEXT,
    end_date            TEXT,
    review_due          TEXT,
    max_students        INTEGER,
    fee_share_pct       REAL,
    signed_by           TEXT,
    signed_date         TEXT,
    contract_ref        TEXT,
    notes               TEXT,
    created_at          TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (partner_id)
        REFERENCES partner_institutions(partner_id) ON DELETE CASCADE
);
"""

_CREATE_PROGRAMMES = """
CREATE TABLE IF NOT EXISTS collaborative_programmes (
    collab_programme_id INTEGER PRIMARY KEY AUTOINCREMENT,
    agreement_id        INTEGER NOT NULL,
    programme_code      TEXT,
    programme_title     TEXT    NOT NULL,
    award               TEXT,
    level               TEXT,
    credits             INTEGER,
    language            TEXT DEFAULT 'English',
    delivery_site       TEXT,
    link_tutor          TEXT,
    external_examiner   TEXT,
    first_intake        TEXT,
    final_intake        TEXT,
    status              TEXT    NOT NULL DEFAULT 'Active',
    created_at          TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (agreement_id)
        REFERENCES partnership_agreements(agreement_id) ON DELETE CASCADE
);
"""

_CREATE_COHORTS = """
CREATE TABLE IF NOT EXISTS partner_cohorts (
    cohort_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    collab_programme_id INTEGER NOT NULL,
    academic_year       TEXT    NOT NULL,
    intake_month        TEXT,
    planned_headcount   INTEGER,
    actual_headcount    INTEGER,
    registered_headcount INTEGER,
    completed_headcount INTEGER,
    notes               TEXT,
    created_at          TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (collab_programme_id)
        REFERENCES collaborative_programmes(collab_programme_id) ON DELETE CASCADE
);
"""

_CREATE_REVIEWS = """
CREATE TABLE IF NOT EXISTS partner_reviews (
    review_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    partner_id          INTEGER NOT NULL,
    agreement_id        INTEGER,
    review_type         TEXT    NOT NULL,
    review_date         TEXT    NOT NULL,
    reviewer            TEXT,
    outcome             TEXT,
    findings            TEXT,
    conditions          TEXT,
    next_review_due     TEXT,
    created_at          TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (partner_id)
        REFERENCES partner_institutions(partner_id) ON DELETE CASCADE,
    FOREIGN KEY (agreement_id)
        REFERENCES partnership_agreements(agreement_id) ON DELETE SET NULL
);
"""

_INDEXES = (
    "CREATE INDEX IF NOT EXISTS idx_partner_active "
    "ON partner_institutions(active);",
    "CREATE INDEX IF NOT EXISTS idx_partner_country "
    "ON partner_institutions(country);",
    "CREATE INDEX IF NOT EXISTS idx_agreement_partner "
    "ON partnership_agreements(partner_id);",
    "CREATE INDEX IF NOT EXISTS idx_agreement_status "
    "ON partnership_agreements(status);",
    "CREATE INDEX IF NOT EXISTS idx_agreement_review_due "
    "ON partnership_agreements(review_due);",
    "CREATE INDEX IF NOT EXISTS idx_collab_prog_agreement "
    "ON collaborative_programmes(agreement_id);",
    "CREATE INDEX IF NOT EXISTS idx_collab_prog_code "
    "ON collaborative_programmes(programme_code);",
    "CREATE INDEX IF NOT EXISTS idx_partner_cohort_prog "
    "ON partner_cohorts(collab_programme_id);",
    "CREATE INDEX IF NOT EXISTS idx_partner_review_partner "
    "ON partner_reviews(partner_id);",
)

_TRIGGER_TOUCH_PARTNER = """
CREATE TRIGGER IF NOT EXISTS partner_institutions_touch
AFTER UPDATE ON partner_institutions
BEGIN
    UPDATE partner_institutions SET updated_at = CURRENT_TIMESTAMP
     WHERE partner_id = NEW.partner_id;
END;
"""

_TRIGGER_TOUCH_AGREEMENT = """
CREATE TRIGGER IF NOT EXISTS partnership_agreements_touch
AFTER UPDATE ON partnership_agreements
BEGIN
    UPDATE partnership_agreements SET updated_at = CURRENT_TIMESTAMP
     WHERE agreement_id = NEW.agreement_id;
END;
"""

# A review that sets a next-review date is the authority on when the
# agreement is next looked at, so mirror it rather than asking the user to
# type the same date into two places.
_TRIGGER_REVIEW_SETS_DUE = """
CREATE TRIGGER IF NOT EXISTS partner_review_sets_agreement_due
AFTER INSERT ON partner_reviews
WHEN NEW.agreement_id IS NOT NULL
     AND NEW.next_review_due IS NOT NULL AND NEW.next_review_due <> ''
BEGIN
    UPDATE partnership_agreements
       SET review_due = NEW.next_review_due,
           updated_at = CURRENT_TIMESTAMP
     WHERE agreement_id = NEW.agreement_id;
END;
"""


def ensure_collaborative_provision_schema(db_path=None) -> None:
    """Create the partner-provision tables, indexes and triggers. Idempotent."""
    path = str(db_path or UNIVERSITY_DEFAULT_DB_PATH)
    try:
        conn = get_connection(path)
    except sqlite3.Error:
        logger.exception("could not open %s for partner provision bootstrap", path)
        return
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        for stmt in (_CREATE_PARTNERS, _CREATE_AGREEMENTS, _CREATE_PROGRAMMES,
                     _CREATE_COHORTS, _CREATE_REVIEWS, *_INDEXES,
                     _TRIGGER_TOUCH_PARTNER, _TRIGGER_TOUCH_AGREEMENT,
                     _TRIGGER_REVIEW_SETS_DUE):
            try:
                conn.execute(stmt)
            except sqlite3.OperationalError:
                logger.exception("partner provision bootstrap failed: %s",
                                 stmt.strip().split("\n", 1)[0])
        conn.commit()
    finally:
        conn.close()


__all__ = [
    "DELIVERY_MODELS", "PARTNER_TYPES", "AGREEMENT_STATUSES", "RISK_LEVELS",
    "REVIEW_TYPES", "REVIEW_OUTCOMES", "ensure_collaborative_provision_schema",
]
