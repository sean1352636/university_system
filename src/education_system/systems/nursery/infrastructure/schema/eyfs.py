"""EYFS learning and development: profiles, tracking, observations, journeys, next steps, checks, planning, evidence.

Split out of ``database.py``, which imports every name here and keeps
``connect``/``init_db``. Import from ``database``, not from here.
"""

from __future__ import annotations


# ── EYFS Learning & Development ────────────────────────────────────────────────
# The EYFS (Early Years Foundation Stage) framework: seven areas of learning —
# three prime (Communication & Language, Physical Development, Personal/Social &
# Emotional) and four specific (Literacy, Mathematics, Understanding the World,
# Expressive Arts & Design) — plus the three Characteristics of Effective
# Learning. The tables below back the assessment, observation and planning cycle.

# ``eyfs_profiles`` = a per-child attainment snapshot across the seven areas,
# each judged Emerging / Expected / Exceeding for a term. The summative view a
# key person shares at a review point.
_EYFS_PROFILE_SCHEMA = """
CREATE TABLE IF NOT EXISTS eyfs_profiles (
    profile_id             TEXT PRIMARY KEY,
    pupil_id               TEXT NOT NULL,
    assessment_date        TEXT,
    term                   TEXT,
    communication_language TEXT,
    physical_development   TEXT,
    pse_development        TEXT,
    literacy               TEXT,
    mathematics            TEXT,
    understanding_world    TEXT,
    expressive_arts        TEXT,
    summary                TEXT,
    assessor               TEXT,
    status                 TEXT NOT NULL DEFAULT 'draft',
    created_at             TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE,
    FOREIGN KEY (assessor) REFERENCES staff(staff_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_eyfs_profiles_pupil ON eyfs_profiles(pupil_id);
"""

# ``development_tracking`` = a single area assessment for a child at a point in
# time: the area (one of the seven), an optional aspect, the Development Matters
# age band reached and a judgement (Emerging / Developing / Secure). Tracking
# these over time shows progress per area.
_DEVELOPMENT_TRACKING_SCHEMA = """
CREATE TABLE IF NOT EXISTS development_tracking (
    record_id       TEXT PRIMARY KEY,
    pupil_id        TEXT NOT NULL,
    area            TEXT NOT NULL,
    aspect          TEXT,
    age_band        TEXT,
    judgement       TEXT,
    assessment_date TEXT,
    assessor        TEXT,
    next_steps      TEXT,
    notes           TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE,
    FOREIGN KEY (assessor) REFERENCES staff(staff_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_devtrack_pupil ON development_tracking(pupil_id);
CREATE INDEX IF NOT EXISTS idx_devtrack_area  ON development_tracking(area);
"""

# ``observations`` = the day-to-day observations of a child at play that evidence
# learning (spontaneous, planned or focused), tagged to an area of learning with
# the identified next step.
_OBSERVATIONS_SCHEMA = """
CREATE TABLE IF NOT EXISTS observations (
    observation_id   TEXT PRIMARY KEY,
    pupil_id         TEXT NOT NULL,
    observation_date TEXT,
    observation_type TEXT,
    area             TEXT,
    title            TEXT,
    description      TEXT,
    context          TEXT,
    next_step        TEXT,
    staff_id         TEXT,
    created_at       TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE,
    FOREIGN KEY (staff_id) REFERENCES staff(staff_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_observations_pupil ON observations(pupil_id);
CREATE INDEX IF NOT EXISTS idx_observations_date  ON observations(observation_date);
"""

# ``learning_journeys`` = the curated entries that make up each child's learning
# journey / journal — milestones and "wow moments", tagged to an area and
# optionally shared with parents.
_LEARNING_JOURNEYS_SCHEMA = """
CREATE TABLE IF NOT EXISTS learning_journeys (
    entry_id           TEXT PRIMARY KEY,
    pupil_id           TEXT NOT NULL,
    entry_date         TEXT,
    title              TEXT,
    area               TEXT,
    description        TEXT,
    wow_moment         INTEGER NOT NULL DEFAULT 0,
    shared_with_parent INTEGER NOT NULL DEFAULT 0,
    staff_id           TEXT,
    notes              TEXT,
    created_at         TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE,
    FOREIGN KEY (staff_id) REFERENCES staff(staff_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_journeys_pupil ON learning_journeys(pupil_id);
"""

# ``next_steps`` = the planned next steps for a child's learning, drawn from
# observations/assessment. Each has an area, a target and a planned → in_progress
# → achieved status.
_NEXT_STEPS_SCHEMA = """
CREATE TABLE IF NOT EXISTS next_steps (
    step_id       TEXT PRIMARY KEY,
    pupil_id      TEXT NOT NULL,
    area          TEXT,
    description   TEXT NOT NULL,
    planned_date  TEXT,
    target_date   TEXT,
    status        TEXT NOT NULL DEFAULT 'planned',
    achieved_date TEXT,
    staff_id      TEXT,
    notes         TEXT,
    created_at    TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE,
    FOREIGN KEY (staff_id) REFERENCES staff(staff_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_next_steps_pupil  ON next_steps(pupil_id);
CREATE INDEX IF NOT EXISTS idx_next_steps_status ON next_steps(status);
"""

# ``progress_check_2yr`` = the statutory EYFS progress check at age two, covering
# the three prime areas with a summary, identified strengths and any concerns,
# and whether it was shared with the parents and health visitor.
_PROGRESS_CHECK_2YR_SCHEMA = """
CREATE TABLE IF NOT EXISTS progress_check_2yr (
    check_id             TEXT PRIMARY KEY,
    pupil_id             TEXT NOT NULL,
    check_date           TEXT,
    age_months           INTEGER,
    comm_language        TEXT,
    physical_development TEXT,
    pse_development      TEXT,
    summary              TEXT,
    strengths            TEXT,
    areas_of_concern     TEXT,
    shared_with_parents  INTEGER NOT NULL DEFAULT 0,
    shared_with_hv       INTEGER NOT NULL DEFAULT 0,
    staff_id             TEXT,
    status               TEXT NOT NULL DEFAULT 'draft',
    created_at           TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE,
    FOREIGN KEY (staff_id) REFERENCES staff(staff_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_progress2yr_pupil ON progress_check_2yr(pupil_id);
"""

# ``effective_learning`` = observations against the three Characteristics of
# Effective Learning (Playing & Exploring, Active Learning, Creating & Thinking
# Critically) — how a child learns, not what.
_EFFECTIVE_LEARNING_SCHEMA = """
CREATE TABLE IF NOT EXISTS effective_learning (
    record_id        TEXT PRIMARY KEY,
    pupil_id         TEXT NOT NULL,
    observation_date TEXT,
    characteristic   TEXT,
    aspect           TEXT,
    description      TEXT,
    staff_id         TEXT,
    notes            TEXT,
    created_at       TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE,
    FOREIGN KEY (staff_id) REFERENCES staff(staff_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_effective_learning_pupil ON effective_learning(pupil_id);
"""

# ``curriculum_planning`` = activity / curriculum plans at room or setting level
# (not attached to a child): a theme, learning intention, the planned activities
# and resources, moving planned → delivered.
_CURRICULUM_PLANNING_SCHEMA = """
CREATE TABLE IF NOT EXISTS curriculum_planning (
    plan_id            TEXT PRIMARY KEY,
    title              TEXT NOT NULL,
    plan_date          TEXT,
    room               TEXT,
    area               TEXT,
    theme              TEXT,
    learning_intention TEXT,
    activities         TEXT,
    resources          TEXT,
    staff_id           TEXT,
    status             TEXT NOT NULL DEFAULT 'planned',
    created_at         TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (staff_id) REFERENCES staff(staff_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_curriculum_status ON curriculum_planning(status);
"""

# ``cohort_tracking`` = cohort-level attainment snapshots (not per child): for a
# named cohort/room/term and area of learning, how many children are below /
# on-track / above expected. Supports gap analysis across groups.
_COHORT_TRACKING_SCHEMA = """
CREATE TABLE IF NOT EXISTS cohort_tracking (
    cohort_id       TEXT PRIMARY KEY,
    cohort_name     TEXT NOT NULL,
    room            TEXT,
    term            TEXT,
    area            TEXT,
    total_children  INTEGER,
    below_count     INTEGER,
    on_track_count  INTEGER,
    above_count     INTEGER,
    assessment_date TEXT,
    staff_id        TEXT,
    notes           TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (staff_id) REFERENCES staff(staff_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_cohort_tracking_room ON cohort_tracking(room);
"""

# ``evidence`` = the Photos & Evidence library: photos, videos, work samples and
# notes captured as evidence of a child's learning, tagged to an area and
# optionally shared with parents.
_EVIDENCE_SCHEMA = """
CREATE TABLE IF NOT EXISTS evidence (
    evidence_id        TEXT PRIMARY KEY,
    pupil_id           TEXT NOT NULL,
    capture_date       TEXT,
    title              TEXT,
    evidence_type      TEXT,
    area               TEXT,
    file_ref           TEXT,
    description        TEXT,
    shared_with_parent INTEGER NOT NULL DEFAULT 0,
    staff_id           TEXT,
    created_at         TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE,
    FOREIGN KEY (staff_id) REFERENCES staff(staff_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_evidence_pupil ON evidence(pupil_id);
CREATE INDEX IF NOT EXISTS idx_evidence_type  ON evidence(evidence_type);
"""
