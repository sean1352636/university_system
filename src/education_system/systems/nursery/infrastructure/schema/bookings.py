"""Contracted sessions, booking exceptions, closures, authorised collectors and late collections.

Split out of ``database.py``, which imports every name here and keeps
``connect``/``init_db``. Import from ``database``, not from here.
"""

from __future__ import annotations


# ── Sessions & bookings (the contracted booking calendar) ────────────────────

# ``booking_patterns`` = a child's *contracted* weekly pattern — the recurring
# sessions the parent is booked and billed for. One row per child per weekday
# per session, valid between ``start_date`` and an open-ended ``end_date``. This
# is what the setting plans occupancy, ratios and invoices against; the dated
# exceptions to it live in ``session_bookings``.
_BOOKING_PATTERNS_SCHEMA = """
CREATE TABLE IF NOT EXISTS booking_patterns (
    pattern_id   TEXT PRIMARY KEY,
    pupil_id     TEXT NOT NULL,
    weekday      INTEGER NOT NULL,
    session_type TEXT NOT NULL DEFAULT 'all-day',
    start_time   TEXT,
    end_time     TEXT,
    room         TEXT,
    funding      TEXT NOT NULL DEFAULT 'funded',
    start_date   TEXT NOT NULL,
    end_date     TEXT,
    status       TEXT NOT NULL DEFAULT 'active',
    notes        TEXT,
    created_at   TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_booking_patterns_pupil   ON booking_patterns(pupil_id);
CREATE INDEX IF NOT EXISTS idx_booking_patterns_weekday ON booking_patterns(weekday);
CREATE UNIQUE INDEX IF NOT EXISTS idx_booking_patterns_unique
    ON booking_patterns(pupil_id, weekday, session_type, start_date);
"""

# ``session_bookings`` = the dated exceptions layered over the weekly pattern:
# ad-hoc **extra** sessions a parent has booked on top of their contract, and
# **cancellations** of a contracted session. Resolving a date means taking that
# weekday's patterns, dropping the cancellations and adding the extras.
_SESSION_BOOKINGS_SCHEMA = """
CREATE TABLE IF NOT EXISTS session_bookings (
    booking_id   TEXT PRIMARY KEY,
    pupil_id     TEXT NOT NULL,
    session_date TEXT NOT NULL,
    session_type TEXT NOT NULL DEFAULT 'all-day',
    kind         TEXT NOT NULL DEFAULT 'extra',
    start_time   TEXT,
    end_time     TEXT,
    room         TEXT,
    chargeable   INTEGER NOT NULL DEFAULT 1,
    notice_days  INTEGER,
    reason       TEXT,
    status       TEXT NOT NULL DEFAULT 'confirmed',
    notes        TEXT,
    created_at   TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_session_bookings_date  ON session_bookings(session_date);
CREATE INDEX IF NOT EXISTS idx_session_bookings_pupil ON session_bookings(pupil_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_session_bookings_unique
    ON session_bookings(pupil_id, session_date, session_type, kind);
"""

# ``setting_closures`` = dates the setting (or a single room) is shut — bank
# holidays, the Christmas closure, INSET days, an emergency closure. A closure
# date resolves to zero booked children, so it suppresses ratio and occupancy
# alerts and drives the "are we charging for it?" billing question.
_CLOSURES_SCHEMA = """
CREATE TABLE IF NOT EXISTS setting_closures (
    closure_id   TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    start_date   TEXT NOT NULL,
    end_date     TEXT NOT NULL,
    closure_type TEXT NOT NULL DEFAULT 'holiday',
    room         TEXT,
    chargeable   INTEGER NOT NULL DEFAULT 0,
    notes        TEXT,
    created_at   TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_closures_start ON setting_closures(start_date);
"""

# ── Collections (who may take a child home, and what happens when they're late)

# ``authorised_collectors`` = the vetted list of people permitted to collect a
# child, each with an optional collection password (stored only as a salted
# hash, never in the clear) and a validity window. A name that isn't on this
# list — or is outside its window, or revoked — must not leave with the child.
_COLLECTORS_SCHEMA = """
CREATE TABLE IF NOT EXISTS authorised_collectors (
    collector_id  TEXT PRIMARY KEY,
    pupil_id      TEXT NOT NULL,
    full_name     TEXT NOT NULL,
    relationship  TEXT,
    phone         TEXT,
    password_hash TEXT,
    photo_on_file INTEGER NOT NULL DEFAULT 0,
    id_checked    INTEGER NOT NULL DEFAULT 0,
    is_escalation_contact INTEGER NOT NULL DEFAULT 0,
    valid_from    TEXT,
    valid_until   TEXT,
    status        TEXT NOT NULL DEFAULT 'active',
    notes         TEXT,
    created_at    TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_collectors_pupil  ON authorised_collectors(pupil_id);
CREATE INDEX IF NOT EXISTS idx_collectors_status ON authorised_collectors(status);
"""

# ``late_collections`` = the uncollected-child log. Records the booked due time,
# when the child was actually collected, the resulting late fee, and how far the
# setting had to escalate (parent → emergency contacts → manager → DSL → local
# authority) — the evidence trail Ofsted expects for an uncollected child.
_LATE_COLLECTIONS_SCHEMA = """
CREATE TABLE IF NOT EXISTS late_collections (
    record_id        TEXT PRIMARY KEY,
    pupil_id         TEXT NOT NULL,
    event_date       TEXT NOT NULL,
    due_time         TEXT NOT NULL,
    collected_time   TEXT,
    minutes_late     INTEGER NOT NULL DEFAULT 0,
    collected_by     TEXT,
    collector_id     TEXT,
    fee_amount       REAL NOT NULL DEFAULT 0,
    fee_status       TEXT NOT NULL DEFAULT 'due',
    escalation_stage TEXT NOT NULL DEFAULT 'none',
    escalated_to     TEXT,
    parent_contacted INTEGER NOT NULL DEFAULT 0,
    safeguarding_referral INTEGER NOT NULL DEFAULT 0,
    recorded_by      TEXT,
    notes            TEXT,
    created_at       TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE,
    FOREIGN KEY (collector_id) REFERENCES authorised_collectors(collector_id)
        ON DELETE SET NULL,
    FOREIGN KEY (recorded_by) REFERENCES staff(staff_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_late_collections_pupil ON late_collections(pupil_id);
CREATE INDEX IF NOT EXISTS idx_late_collections_date  ON late_collections(event_date);
"""
