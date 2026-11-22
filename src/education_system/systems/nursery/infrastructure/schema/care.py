"""Daily care: attendance, accidents, sign-in/out, diary, sleep, toileting, meals, feeds, diet, injuries, medication.

Split out of ``database.py``, which imports every name here and keeps
``connect``/``init_db``. Import from ``database``, not from here.
"""

from __future__ import annotations


# ── Daily care / welfare (registers behind the Compliance & Reports) ──────────

# ``attendance_records`` = the daily register. One row per child per session
# (``all-day``/``am``/``pm``) on a given date, with a status (present / absent /
# late / sick / holiday), arrival + departure times and any absence reason. The
# Attendance Report aggregates these into attendance rates by child / room /
# date range. A unique index keeps one row per child-date-session.
_ATTENDANCE_SCHEMA = """
CREATE TABLE IF NOT EXISTS attendance_records (
    record_id      TEXT PRIMARY KEY,
    pupil_id       TEXT NOT NULL,
    attend_date    TEXT NOT NULL,
    room           TEXT,
    session        TEXT NOT NULL DEFAULT 'all-day',
    status         TEXT NOT NULL DEFAULT 'present',
    arrival_time   TEXT,
    departure_time TEXT,
    absence_reason TEXT,
    notes          TEXT,
    created_at     TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_attendance_date  ON attendance_records(attend_date);
CREATE INDEX IF NOT EXISTS idx_attendance_pupil ON attendance_records(pupil_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_attendance_unique
    ON attendance_records(pupil_id, attend_date, session);
"""

# ``accident_records`` = the statutory accident / incident / near-miss register.
# EYFS requires a written record of accidents, injuries and first aid given, and
# parents informed the same day; serious injuries may be RIDDOR-reportable. Each
# row links a child, what happened, the injury + body part, treatment +
# first-aider, whether the parent was informed / signed and whether it is
# RIDDOR-reportable. The Accident / Incident Report lists and summarises these.
_ACCIDENT_SCHEMA = """
CREATE TABLE IF NOT EXISTS accident_records (
    record_id         TEXT PRIMARY KEY,
    pupil_id          TEXT NOT NULL,
    record_type       TEXT NOT NULL DEFAULT 'accident',
    occurred_date     TEXT,
    occurred_time     TEXT,
    location          TEXT,
    description       TEXT,
    injury            TEXT,
    body_part         TEXT,
    treatment         TEXT,
    first_aider       TEXT,
    severity          TEXT NOT NULL DEFAULT 'minor',
    parent_informed   INTEGER NOT NULL DEFAULT 0,
    parent_signed     INTEGER NOT NULL DEFAULT 0,
    riddor_reportable INTEGER NOT NULL DEFAULT 0,
    action_taken      TEXT,
    recorded_by       TEXT,
    status            TEXT NOT NULL DEFAULT 'open',
    notes             TEXT,
    created_at        TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE,
    FOREIGN KEY (first_aider) REFERENCES staff(staff_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_accident_pupil ON accident_records(pupil_id);
CREATE INDEX IF NOT EXISTS idx_accident_date  ON accident_records(occurred_date);
CREATE INDEX IF NOT EXISTS idx_accident_type  ON accident_records(record_type);
"""


# ── Daily Care & Routines ─────────────────────────────────────────────────────
# The day-to-day care records an Early Years setting keeps for each child. The
# Daily Register reuses ``attendance_records`` and the Accident & Incident Log
# reuses ``accident_records`` (both defined above); the tables below back the
# remaining routines.

# ``sign_in_out_log`` = timestamped arrival / collection events. One row per
# in/out event, recording the time, who dropped off / collected the child (and
# their relationship — collectors must be on the authorised list) and the staff
# member who recorded it. Distinct from the daily register (present/absent): this
# is the legal record of who had the child and when.
_SIGN_IN_OUT_SCHEMA = """
CREATE TABLE IF NOT EXISTS sign_in_out_log (
    event_id     TEXT PRIMARY KEY,
    pupil_id     TEXT NOT NULL,
    event_date   TEXT NOT NULL,
    event_time   TEXT,
    direction    TEXT NOT NULL DEFAULT 'in',
    person_name  TEXT,
    relationship TEXT,
    recorded_by  TEXT,
    notes        TEXT,
    created_at   TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE,
    FOREIGN KEY (recorded_by) REFERENCES staff(staff_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_sign_in_out_pupil ON sign_in_out_log(pupil_id);
CREATE INDEX IF NOT EXISTS idx_sign_in_out_date  ON sign_in_out_log(event_date);
"""

# ``daily_diary`` = the staff diary of a child's day (mood, activities,
# highlights, free-text notes). One row per child per day. Feeds the
# parent-facing ``daily_updates`` but is the fuller practitioner record.
_DAILY_DIARY_SCHEMA = """
CREATE TABLE IF NOT EXISTS daily_diary (
    entry_id    TEXT PRIMARY KEY,
    pupil_id    TEXT NOT NULL,
    entry_date  TEXT NOT NULL,
    mood        TEXT,
    activities  TEXT,
    highlights  TEXT,
    notes       TEXT,
    staff_id    TEXT,
    created_at  TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE,
    FOREIGN KEY (staff_id) REFERENCES staff(staff_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_daily_diary_pupil ON daily_diary(pupil_id);
CREATE INDEX IF NOT EXISTS idx_daily_diary_date  ON daily_diary(entry_date);
"""

# ``sleep_log`` = nap records with safer-sleep checks. Each row is one sleep,
# with start/end, derived duration, where the child slept and how many sleep
# checks were carried out (settings check sleeping children at regular intervals).
_SLEEP_LOG_SCHEMA = """
CREATE TABLE IF NOT EXISTS sleep_log (
    sleep_id         TEXT PRIMARY KEY,
    pupil_id         TEXT NOT NULL,
    sleep_date       TEXT NOT NULL,
    start_time       TEXT,
    end_time         TEXT,
    duration_minutes INTEGER,
    location         TEXT,
    checks           INTEGER NOT NULL DEFAULT 0,
    staff_id         TEXT,
    notes            TEXT,
    created_at       TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE,
    FOREIGN KEY (staff_id) REFERENCES staff(staff_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_sleep_log_pupil ON sleep_log(pupil_id);
CREATE INDEX IF NOT EXISTS idx_sleep_log_date  ON sleep_log(sleep_date);
"""

# ``toileting_log`` = nappy changes and toilet/potty use. Each row records the
# time, the type (wet/soiled/dry nappy, toilet, potty, accident), whether barrier
# cream was applied and the staff member.
_TOILETING_LOG_SCHEMA = """
CREATE TABLE IF NOT EXISTS toileting_log (
    record_id     TEXT PRIMARY KEY,
    pupil_id      TEXT NOT NULL,
    log_date      TEXT NOT NULL,
    log_time      TEXT,
    type          TEXT NOT NULL DEFAULT 'nappy - wet',
    cream_applied INTEGER NOT NULL DEFAULT 0,
    staff_id      TEXT,
    notes         TEXT,
    created_at    TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE,
    FOREIGN KEY (staff_id) REFERENCES staff(staff_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_toileting_pupil ON toileting_log(pupil_id);
CREATE INDEX IF NOT EXISTS idx_toileting_date  ON toileting_log(log_date);
"""

# ``meals`` = the per-child meal log (Meals & Menus). One row per child per meal
# sitting, recording the meal type, the menu served, how much was eaten and the
# drink, plus an allergy-safe flag so kitchen/room staff can evidence that a
# child's dietary needs were honoured.
_MEALS_SCHEMA = """
CREATE TABLE IF NOT EXISTS meals (
    meal_id      TEXT PRIMARY KEY,
    pupil_id     TEXT NOT NULL,
    meal_date    TEXT NOT NULL,
    meal_type    TEXT NOT NULL DEFAULT 'Lunch',
    menu         TEXT,
    amount_eaten TEXT,
    drink        TEXT,
    allergy_safe INTEGER NOT NULL DEFAULT 1,
    staff_id     TEXT,
    notes        TEXT,
    created_at   TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE,
    FOREIGN KEY (staff_id) REFERENCES staff(staff_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_meals_pupil ON meals(pupil_id);
CREATE INDEX IF NOT EXISTS idx_meals_date  ON meals(meal_date);
"""

# ``bottle_feeds`` = milk feeds for babies. Records the milk type (formula /
# expressed breast milk / cow's milk / water), the amount offered vs taken, and
# whether the temperature was checked and the baby winded.
_BOTTLE_FEEDS_SCHEMA = """
CREATE TABLE IF NOT EXISTS bottle_feeds (
    feed_id             TEXT PRIMARY KEY,
    pupil_id            TEXT NOT NULL,
    feed_date           TEXT NOT NULL,
    feed_time           TEXT,
    milk_type           TEXT NOT NULL DEFAULT 'Formula',
    offered_ml          INTEGER,
    taken_ml            INTEGER,
    temperature_checked INTEGER NOT NULL DEFAULT 1,
    winded              INTEGER NOT NULL DEFAULT 0,
    staff_id            TEXT,
    notes               TEXT,
    created_at          TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE,
    FOREIGN KEY (staff_id) REFERENCES staff(staff_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_bottle_feeds_pupil ON bottle_feeds(pupil_id);
CREATE INDEX IF NOT EXISTS idx_bottle_feeds_date  ON bottle_feeds(feed_date);
"""

# ``dietary_requirements`` = the structured allergy / intolerance / dietary
# register behind the free-text ``pupils.allergies`` label. Each row records the
# category, allergen, severity, the reaction and the action required (e.g.
# EpiPen), so kitchen and room staff have an auditable care plan per child.
_DIETARY_SCHEMA = """
CREATE TABLE IF NOT EXISTS dietary_requirements (
    record_id       TEXT PRIMARY KEY,
    pupil_id        TEXT NOT NULL,
    category        TEXT NOT NULL DEFAULT 'allergy',
    allergen        TEXT,
    severity        TEXT,
    reaction        TEXT,
    action_required TEXT,
    epipen_required INTEGER NOT NULL DEFAULT 0,
    care_plan_ref   TEXT,
    status          TEXT NOT NULL DEFAULT 'active',
    notes           TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_dietary_pupil  ON dietary_requirements(pupil_id);
CREATE INDEX IF NOT EXISTS idx_dietary_status ON dietary_requirements(status);
"""

# ``existing_injuries`` = injuries a child arrives WITH (not sustained at the
# setting). EYFS good practice is to log these on arrival with the parent's
# explanation and a signature, to safeguard both child and setting.
_EXISTING_INJURIES_SCHEMA = """
CREATE TABLE IF NOT EXISTS existing_injuries (
    record_id       TEXT PRIMARY KEY,
    pupil_id        TEXT NOT NULL,
    observed_date   TEXT NOT NULL,
    observed_time   TEXT,
    body_part       TEXT,
    description     TEXT,
    explanation     TEXT,
    observed_by     TEXT,
    parent_informed INTEGER NOT NULL DEFAULT 1,
    parent_signed   INTEGER NOT NULL DEFAULT 0,
    notes           TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE,
    FOREIGN KEY (observed_by) REFERENCES staff(staff_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_existing_injuries_pupil ON existing_injuries(pupil_id);
CREATE INDEX IF NOT EXISTS idx_existing_injuries_date  ON existing_injuries(observed_date);
"""

# ``medication_log`` = the record of medicine administered (and prior parental
# consent). Each row captures the medicine, dose, route, the reason, when it was
# given and by whom, witnessed-by, and a status (administered / scheduled /
# refused). Settings must hold written parental consent before administering.
_MEDICATION_LOG_SCHEMA = """
CREATE TABLE IF NOT EXISTS medication_log (
    record_id        TEXT PRIMARY KEY,
    pupil_id         TEXT NOT NULL,
    medication_name  TEXT NOT NULL,
    dose             TEXT,
    route            TEXT,
    reason           TEXT,
    administered_date TEXT,
    administered_time TEXT,
    administered_by  TEXT,
    witnessed_by     TEXT,
    parent_consent   INTEGER NOT NULL DEFAULT 0,
    expiry_date      TEXT,
    status           TEXT NOT NULL DEFAULT 'administered',
    notes            TEXT,
    created_at       TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE,
    FOREIGN KEY (administered_by) REFERENCES staff(staff_id) ON DELETE SET NULL,
    FOREIGN KEY (witnessed_by) REFERENCES staff(staff_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_medication_pupil  ON medication_log(pupil_id);
CREATE INDEX IF NOT EXISTS idx_medication_status ON medication_log(status);
"""
