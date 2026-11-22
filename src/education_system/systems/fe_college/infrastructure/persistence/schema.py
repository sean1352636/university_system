"""SQLite schema and bootstrap for the FE College system.

``init_db()`` is idempotent (every statement is ``CREATE ... IF NOT EXISTS``)
and is called on every launch from ``cli_main.run`` / ``gui_main.run``.

All tables live in one file (``FE_COLLEGE_DB``). Learner-owned rows cascade on
delete so removing a learner cannot leave orphaned attendance, fee or referral
records behind; reference data (courses, staff, rooms) uses ``ON DELETE SET
NULL`` or ``RESTRICT`` instead, because deleting a course should never silently
delete the enrolments that prove it ran.
"""

from __future__ import annotations

import logging
import os
import sqlite3

from education_system.systems.fe_college.infrastructure.persistence import (
    connect,
    ensure_directories,
    transaction,
)

logger = logging.getLogger(__name__)

# ── Reference data ──────────────────────────────────────────────────────────

_STAFF_SCHEMA = """
CREATE TABLE IF NOT EXISTS staff (
    staff_id             TEXT PRIMARY KEY,
    first_name           TEXT NOT NULL,
    last_name            TEXT NOT NULL,
    email                TEXT NOT NULL,
    role                 TEXT NOT NULL DEFAULT 'Lecturer',
    department           TEXT,
    employment_status    TEXT NOT NULL DEFAULT 'Full-time',
    contracted_hours     REAL NOT NULL DEFAULT 24,
    phone                TEXT,
    room                 TEXT,
    start_date           TEXT,
    end_date             TEXT,
    is_safeguarding_lead INTEGER NOT NULL DEFAULT 0,
    is_exams_officer     INTEGER NOT NULL DEFAULT 0,
    dbs_checked          INTEGER NOT NULL DEFAULT 0,
    qualifications       TEXT,
    notes                TEXT,
    created_at           TEXT DEFAULT (datetime('now')),
    updated_at           TEXT DEFAULT (datetime('now'))
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_fe_staff_email  ON staff(lower(email));
CREATE INDEX IF NOT EXISTS idx_fe_staff_role          ON staff(role);
CREATE INDEX IF NOT EXISTS idx_fe_staff_department    ON staff(department);
CREATE INDEX IF NOT EXISTS idx_fe_staff_status        ON staff(employment_status);
"""

_ROOMS_SCHEMA = """
CREATE TABLE IF NOT EXISTS rooms (
    room_id        TEXT PRIMARY KEY,
    name           TEXT NOT NULL,
    room_type      TEXT NOT NULL DEFAULT 'Classroom',
    capacity       INTEGER NOT NULL DEFAULT 0,
    building       TEXT,
    floor          TEXT,
    campus         TEXT NOT NULL DEFAULT 'Main Campus',
    status         TEXT NOT NULL DEFAULT 'available',
    has_projector  INTEGER NOT NULL DEFAULT 1,
    is_accessible  INTEGER NOT NULL DEFAULT 1,
    notes          TEXT
);
CREATE INDEX IF NOT EXISTS idx_fe_rooms_type   ON rooms(room_type);
CREATE INDEX IF NOT EXISTS idx_fe_rooms_status ON rooms(status);
"""

_COURSES_SCHEMA = """
CREATE TABLE IF NOT EXISTS courses (
    course_id             TEXT PRIMARY KEY,
    title                 TEXT NOT NULL,
    qualification_type    TEXT NOT NULL,
    level                 TEXT NOT NULL DEFAULT '3',
    curriculum_area       TEXT,
    academic_year         TEXT,
    mode_of_study         TEXT NOT NULL DEFAULT 'Full-time',
    status                TEXT NOT NULL DEFAULT 'recruiting',
    course_leader         TEXT,
    awarding_body         TEXT,
    guided_learning_hours INTEGER NOT NULL DEFAULT 0,
    duration_weeks        INTEGER NOT NULL DEFAULT 0,
    capacity              INTEGER NOT NULL DEFAULT 0,
    start_date            TEXT,
    end_date              TEXT,
    campus                TEXT NOT NULL DEFAULT 'Main Campus',
    fee                   REAL NOT NULL DEFAULT 0,
    description           TEXT,
    created_at            TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (course_leader) REFERENCES staff(staff_id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_fe_courses_area   ON courses(curriculum_area);
CREATE INDEX IF NOT EXISTS idx_fe_courses_status ON courses(status);
CREATE INDEX IF NOT EXISTS idx_fe_courses_year   ON courses(academic_year);
CREATE INDEX IF NOT EXISTS idx_fe_courses_leader ON courses(course_leader);

CREATE TABLE IF NOT EXISTS units (
    unit_id               TEXT NOT NULL,
    course_id             TEXT NOT NULL,
    title                 TEXT NOT NULL,
    unit_type             TEXT NOT NULL DEFAULT 'Mandatory',
    credits               INTEGER NOT NULL DEFAULT 10,
    guided_learning_hours INTEGER NOT NULL DEFAULT 60,
    assessment_method     TEXT NOT NULL DEFAULT 'Internal — assignment',
    sequence              INTEGER NOT NULL DEFAULT 0,
    description           TEXT,
    PRIMARY KEY (unit_id, course_id),
    FOREIGN KEY (course_id) REFERENCES courses(course_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_fe_units_course ON units(course_id);

CREATE TABLE IF NOT EXISTS entry_requirements (
    course_id          TEXT PRIMARY KEY,
    min_age            INTEGER NOT NULL DEFAULT 16,
    max_age            INTEGER NOT NULL DEFAULT 0,
    min_prior_level    TEXT,
    min_gcse_english   TEXT,
    min_gcse_maths     TEXT,
    required_subjects  TEXT,
    interview_required INTEGER NOT NULL DEFAULT 0,
    dbs_required       INTEGER NOT NULL DEFAULT 0,
    portfolio_required INTEGER NOT NULL DEFAULT 0,
    notes              TEXT,
    FOREIGN KEY (course_id) REFERENCES courses(course_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS qualifications (
    qan                TEXT PRIMARY KEY,
    title              TEXT NOT NULL,
    qualification_type TEXT NOT NULL,
    level              TEXT NOT NULL DEFAULT '3',
    awarding_body      TEXT NOT NULL,
    size               TEXT NOT NULL DEFAULT 'Diploma',
    total_credits      INTEGER NOT NULL DEFAULT 0,
    is_active          INTEGER NOT NULL DEFAULT 1
);
"""

# ── Learners ────────────────────────────────────────────────────────────────

_STUDENTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS students (
    student_id              TEXT PRIMARY KEY,
    first_name              TEXT NOT NULL,
    middle_name             TEXT,
    last_name               TEXT NOT NULL,
    preferred_name          TEXT,
    date_of_birth           TEXT,
    gender                  TEXT,
    uln                     TEXT,
    -- The platform's canonical cross-system identity, stamped when the
    -- learner arrived from (or was matched to) another system. Also what
    -- makes a redelivered handover idempotent: a second delivery finds
    -- this row instead of creating a duplicate learner.
    journey_id              TEXT,
    email                   TEXT,
    phone                   TEXT,
    address                 TEXT,             -- address line 1
    address_line2           TEXT,
    town                    TEXT,
    postcode                TEXT,
    learner_type            TEXT NOT NULL DEFAULT '16-18 Study Programme',
    mode_of_study           TEXT NOT NULL DEFAULT 'Full-time',
    status                  TEXT NOT NULL DEFAULT 'applicant',
    tutor_group             TEXT,
    personal_tutor          TEXT,
    start_date              TEXT,
    end_date                TEXT,
    prior_attainment        TEXT,
    has_ehcp                INTEGER NOT NULL DEFAULT 0,
    has_lldd                INTEGER NOT NULL DEFAULT 0,  -- learning difficulty / disability
    learning_support        TEXT,
    medical_notes           TEXT,
    emergency_contact_name  TEXT,
    emergency_contact_relationship TEXT,
    emergency_contact_phone TEXT,
    notes                   TEXT,
    created_at              TEXT DEFAULT (datetime('now')),
    updated_at              TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (personal_tutor) REFERENCES staff(staff_id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_fe_students_status ON students(status);
CREATE INDEX IF NOT EXISTS idx_fe_students_name   ON students(last_name, first_name);
CREATE INDEX IF NOT EXISTS idx_fe_students_tutor  ON students(personal_tutor);
CREATE INDEX IF NOT EXISTS idx_fe_students_group  ON students(tutor_group);
-- A ULN identifies a learner nationally; two records sharing one is a
-- duplicate. Partial index so the many blank ULNs don't collide with
-- each other.
CREATE UNIQUE INDEX IF NOT EXISTS idx_fe_students_uln
    ON students(uln) WHERE uln IS NOT NULL AND uln <> '';

CREATE TABLE IF NOT EXISTS enrolments (
    enrolment_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id        TEXT NOT NULL,
    course_id         TEXT NOT NULL,
    academic_year     TEXT NOT NULL,
    status            TEXT NOT NULL DEFAULT 'active',
    is_main_aim       INTEGER NOT NULL DEFAULT 1,
    start_date        TEXT,
    end_date          TEXT,
    expected_end_date TEXT,
    withdrawal_reason TEXT,
    funding_source    TEXT,
    predicted_grade   TEXT,
    final_grade       TEXT,
    created_at        TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE,
    FOREIGN KEY (course_id)  REFERENCES courses(course_id)   ON DELETE CASCADE
);
-- One enrolment per learner per course per year. Re-enrolling on the same
-- course in a later year is a different row, which is what makes repeat
-- years visible in the reports.
CREATE UNIQUE INDEX IF NOT EXISTS idx_fe_enrolments_unique
    ON enrolments(student_id, course_id, academic_year);
CREATE INDEX IF NOT EXISTS idx_fe_enrolments_course ON enrolments(course_id, status);
CREATE INDEX IF NOT EXISTS idx_fe_enrolments_year   ON enrolments(academic_year);

CREATE TABLE IF NOT EXISTS learning_aims (
    aim_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    enrolment_id      INTEGER NOT NULL,
    lars_code         TEXT NOT NULL,
    aim_type          TEXT NOT NULL DEFAULT 'Programme aim',
    funding_model     INTEGER NOT NULL DEFAULT 35,
    start_date        TEXT,
    planned_end_date  TEXT,
    actual_end_date   TEXT,
    completion_status INTEGER NOT NULL DEFAULT 1,
    outcome           INTEGER,
    funding_value     REAL NOT NULL DEFAULT 0,
    FOREIGN KEY (enrolment_id) REFERENCES enrolments(enrolment_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_fe_aims_enrolment ON learning_aims(enrolment_id);

CREATE TABLE IF NOT EXISTS support_plans (
    plan_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id     TEXT NOT NULL,
    support_type   TEXT NOT NULL,
    status         TEXT NOT NULL DEFAULT 'proposed',
    detail         TEXT,
    hours_per_week REAL NOT NULL DEFAULT 0,
    start_date     TEXT,
    review_date    TEXT,
    end_date       TEXT,
    coordinator    TEXT,
    created_at     TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (student_id)  REFERENCES students(student_id) ON DELETE CASCADE,
    FOREIGN KEY (coordinator) REFERENCES staff(staff_id)      ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_fe_support_student ON support_plans(student_id, status);

CREATE TABLE IF NOT EXISTS targets (
    target_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id     TEXT NOT NULL,
    description    TEXT NOT NULL,
    status         TEXT NOT NULL DEFAULT 'set',
    course_id      TEXT,
    set_by         TEXT,
    set_date       TEXT,
    due_date       TEXT,
    completed_date TEXT,
    review_note    TEXT,
    created_at     TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE,
    FOREIGN KEY (set_by)     REFERENCES staff(staff_id)      ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_fe_targets_student ON targets(student_id, status);
"""

# ── Delivery ────────────────────────────────────────────────────────────────

_TEACHING_SCHEMA = """
CREATE TABLE IF NOT EXISTS class_groups (
    group_id      TEXT PRIMARY KEY,
    course_id     TEXT NOT NULL,
    name          TEXT NOT NULL,
    teacher_id    TEXT,
    academic_year TEXT,
    capacity      INTEGER NOT NULL DEFAULT 0,
    room          TEXT,
    notes         TEXT,
    FOREIGN KEY (course_id)  REFERENCES courses(course_id) ON DELETE CASCADE,
    FOREIGN KEY (teacher_id) REFERENCES staff(staff_id)    ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_fe_groups_course  ON class_groups(course_id);
CREATE INDEX IF NOT EXISTS idx_fe_groups_teacher ON class_groups(teacher_id);

CREATE TABLE IF NOT EXISTS group_members (
    group_id   TEXT NOT NULL,
    student_id TEXT NOT NULL,
    PRIMARY KEY (group_id, student_id),
    FOREIGN KEY (group_id)   REFERENCES class_groups(group_id) ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES students(student_id)   ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS sessions (
    session_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id     TEXT NOT NULL,
    group_id      TEXT,
    teacher_id    TEXT,
    room_id       TEXT,
    day           TEXT NOT NULL,
    period        TEXT NOT NULL,
    academic_year TEXT,
    unit_id       TEXT,
    notes         TEXT,
    FOREIGN KEY (course_id)  REFERENCES courses(course_id)     ON DELETE CASCADE,
    FOREIGN KEY (group_id)   REFERENCES class_groups(group_id) ON DELETE SET NULL,
    FOREIGN KEY (teacher_id) REFERENCES staff(staff_id)        ON DELETE SET NULL,
    FOREIGN KEY (room_id)    REFERENCES rooms(room_id)         ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_fe_sessions_slot    ON sessions(day, period);
CREATE INDEX IF NOT EXISTS idx_fe_sessions_teacher ON sessions(teacher_id, day, period);
CREATE INDEX IF NOT EXISTS idx_fe_sessions_room    ON sessions(room_id, day, period);
CREATE INDEX IF NOT EXISTS idx_fe_sessions_course  ON sessions(course_id);

CREATE TABLE IF NOT EXISTS attendance (
    record_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id   TEXT NOT NULL,
    course_id    TEXT NOT NULL,
    session_date TEXT NOT NULL,
    period       TEXT,
    mark         TEXT NOT NULL DEFAULT 'present',
    minutes_late INTEGER NOT NULL DEFAULT 0,
    recorded_by  TEXT,
    note         TEXT,
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE,
    FOREIGN KEY (course_id)  REFERENCES courses(course_id)   ON DELETE CASCADE
);
-- One mark per learner per course per period per day. Re-saving a register
-- overwrites (UPSERT) rather than duplicating, which is what makes a
-- half-completed register safe to submit twice.
CREATE UNIQUE INDEX IF NOT EXISTS idx_fe_attendance_unique
    ON attendance(student_id, course_id, session_date, period);
CREATE INDEX IF NOT EXISTS idx_fe_attendance_student ON attendance(student_id);
CREATE INDEX IF NOT EXISTS idx_fe_attendance_course  ON attendance(course_id, session_date);

CREATE TABLE IF NOT EXISTS assignments (
    assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id     TEXT NOT NULL,
    title         TEXT NOT NULL,
    unit_id       TEXT,
    group_id      TEXT,
    status        TEXT NOT NULL DEFAULT 'draft',
    set_by        TEXT,
    issue_date    TEXT,
    due_date      TEXT,
    criteria      TEXT,
    max_marks     INTEGER NOT NULL DEFAULT 0,
    brief         TEXT,
    created_at    TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (course_id) REFERENCES courses(course_id) ON DELETE CASCADE,
    FOREIGN KEY (set_by)    REFERENCES staff(staff_id)    ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_fe_assignments_course ON assignments(course_id, status);
CREATE INDEX IF NOT EXISTS idx_fe_assignments_due    ON assignments(due_date);

CREATE TABLE IF NOT EXISTS submissions (
    submission_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    assignment_id   INTEGER NOT NULL,
    student_id      TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'not_submitted',
    submitted_at    TEXT,
    marked_at       TEXT,
    marked_by       TEXT,
    grade           TEXT,
    marks           INTEGER,
    is_resubmission INTEGER NOT NULL DEFAULT 0,
    file_ref        TEXT,
    feedback        TEXT,
    FOREIGN KEY (assignment_id) REFERENCES assignments(assignment_id) ON DELETE CASCADE,
    FOREIGN KEY (student_id)    REFERENCES students(student_id)       ON DELETE CASCADE,
    FOREIGN KEY (marked_by)     REFERENCES staff(staff_id)            ON DELETE SET NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_fe_submissions_unique
    ON submissions(assignment_id, student_id);
CREATE INDEX IF NOT EXISTS idx_fe_submissions_student ON submissions(student_id);

CREATE TABLE IF NOT EXISTS feedback (
    feedback_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    submission_id    INTEGER NOT NULL,
    author_id        TEXT,
    body             TEXT NOT NULL,
    feedback_type    TEXT NOT NULL DEFAULT 'Summative',
    strengths        TEXT,
    improvements     TEXT,
    given_at         TEXT,
    seen_by_student  INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (submission_id) REFERENCES submissions(submission_id) ON DELETE CASCADE,
    FOREIGN KEY (author_id)     REFERENCES staff(staff_id)            ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_fe_feedback_submission ON feedback(submission_id);

CREATE TABLE IF NOT EXISTS internal_verification (
    iv_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    submission_id INTEGER NOT NULL,
    verifier_id   TEXT,
    outcome       TEXT NOT NULL DEFAULT 'Agreed',
    comments      TEXT,
    verified_at   TEXT,
    FOREIGN KEY (submission_id) REFERENCES submissions(submission_id) ON DELETE CASCADE,
    FOREIGN KEY (verifier_id)   REFERENCES staff(staff_id)            ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS lesson_plans (
    plan_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id       TEXT NOT NULL,
    title           TEXT NOT NULL,
    teacher_id      TEXT,
    group_id        TEXT,
    unit_id         TEXT,
    session_id      INTEGER,
    lesson_date     TEXT,
    status          TEXT NOT NULL DEFAULT 'draft',
    objectives      TEXT,
    activities      TEXT,
    resources       TEXT,
    differentiation TEXT,
    assessment      TEXT,
    homework        TEXT,
    evaluation      TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (course_id)  REFERENCES courses(course_id) ON DELETE CASCADE,
    FOREIGN KEY (teacher_id) REFERENCES staff(staff_id)    ON DELETE SET NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_fe_plans_teacher ON lesson_plans(teacher_id, lesson_date);

CREATE TABLE IF NOT EXISTS staff_unavailability (
    staff_id TEXT NOT NULL,
    day      TEXT NOT NULL,
    period   TEXT NOT NULL,
    reason   TEXT,
    PRIMARY KEY (staff_id, day, period),
    FOREIGN KEY (staff_id) REFERENCES staff(staff_id) ON DELETE CASCADE
);
"""

# ── Exams ───────────────────────────────────────────────────────────────────

_EXAMS_SCHEMA = """
CREATE TABLE IF NOT EXISTS exam_series (
    series_id           TEXT PRIMARY KEY,
    name                TEXT NOT NULL,
    awarding_body       TEXT,
    academic_year       TEXT,
    status              TEXT NOT NULL DEFAULT 'planned',
    entry_deadline      TEXT,
    late_entry_deadline TEXT,
    results_date        TEXT
);

CREATE TABLE IF NOT EXISTS exam_sittings (
    sitting_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    series_id        TEXT NOT NULL,
    unit_id          TEXT NOT NULL,
    paper            TEXT,
    exam_date        TEXT,
    start_time       TEXT NOT NULL DEFAULT '09:00',
    duration_minutes INTEGER NOT NULL DEFAULT 90,
    room_id          TEXT,
    invigilator_id   TEXT,
    seats            INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (series_id)      REFERENCES exam_series(series_id) ON DELETE CASCADE,
    FOREIGN KEY (room_id)        REFERENCES rooms(room_id)         ON DELETE SET NULL,
    FOREIGN KEY (invigilator_id) REFERENCES staff(staff_id)        ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_fe_sittings_series ON exam_sittings(series_id);
CREATE INDEX IF NOT EXISTS idx_fe_sittings_date   ON exam_sittings(exam_date);

CREATE TABLE IF NOT EXISTS access_arrangements (
    arrangement_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id       TEXT NOT NULL,
    arrangement_type TEXT NOT NULL,
    status           TEXT NOT NULL DEFAULT 'requested',
    evidence_type    TEXT,
    approved_by      TEXT,
    approved_on      TEXT,
    valid_until      TEXT,
    notes            TEXT,
    FOREIGN KEY (student_id)  REFERENCES students(student_id) ON DELETE CASCADE,
    FOREIGN KEY (approved_by) REFERENCES staff(staff_id)      ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_fe_arrangements_student ON access_arrangements(student_id, status);

CREATE TABLE IF NOT EXISTS exam_entries (
    entry_id             INTEGER PRIMARY KEY AUTOINCREMENT,
    sitting_id           INTEGER NOT NULL,
    student_id           TEXT NOT NULL,
    status               TEXT NOT NULL DEFAULT 'entered',
    entry_type           TEXT NOT NULL DEFAULT 'First entry',
    entered_on           TEXT,
    candidate_number     TEXT,
    seat_number          TEXT,
    fee                  REAL NOT NULL DEFAULT 0,
    access_arrangement_id INTEGER,
    FOREIGN KEY (sitting_id)  REFERENCES exam_sittings(sitting_id) ON DELETE CASCADE,
    FOREIGN KEY (student_id)  REFERENCES students(student_id)      ON DELETE CASCADE,
    FOREIGN KEY (access_arrangement_id)
        REFERENCES access_arrangements(arrangement_id) ON DELETE SET NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_fe_entries_unique
    ON exam_entries(sitting_id, student_id);

CREATE TABLE IF NOT EXISTS exam_results (
    result_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_id           INTEGER NOT NULL,
    student_id         TEXT NOT NULL,
    unit_id            TEXT NOT NULL,
    grade              TEXT,
    marks              INTEGER,
    ums                INTEGER,
    status             TEXT NOT NULL DEFAULT 'provisional',
    released_on        TEXT,
    qualification_type TEXT,
    review_requested   TEXT,
    review_outcome     TEXT,
    FOREIGN KEY (entry_id)   REFERENCES exam_entries(entry_id) ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES students(student_id)   ON DELETE CASCADE
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_fe_results_entry ON exam_results(entry_id);
CREATE INDEX IF NOT EXISTS idx_fe_results_student      ON exam_results(student_id);
"""

# ── Finance ─────────────────────────────────────────────────────────────────

_FINANCE_SCHEMA = """
CREATE TABLE IF NOT EXISTS fees (
    fee_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id    TEXT NOT NULL,
    fee_type      TEXT NOT NULL,
    amount        REAL NOT NULL DEFAULT 0,
    status        TEXT NOT NULL DEFAULT 'due',
    course_id     TEXT,
    academic_year TEXT,
    description   TEXT,
    due_date      TEXT,
    raised_on     TEXT,
    waiver_reason TEXT,
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE,
    FOREIGN KEY (course_id)  REFERENCES courses(course_id)   ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_fe_fees_student ON fees(student_id, status);
CREATE INDEX IF NOT EXISTS idx_fe_fees_due     ON fees(due_date);

CREATE TABLE IF NOT EXISTS payments (
    payment_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    fee_id      INTEGER NOT NULL,
    student_id  TEXT NOT NULL,
    amount      REAL NOT NULL DEFAULT 0,
    method      TEXT NOT NULL DEFAULT 'Card',
    status      TEXT NOT NULL DEFAULT 'received',
    paid_on     TEXT,
    reference   TEXT,
    received_by TEXT,
    is_reversal INTEGER NOT NULL DEFAULT 0,
    note        TEXT,
    FOREIGN KEY (fee_id)      REFERENCES fees(fee_id)         ON DELETE CASCADE,
    FOREIGN KEY (student_id)  REFERENCES students(student_id) ON DELETE CASCADE,
    FOREIGN KEY (received_by) REFERENCES staff(staff_id)      ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_fe_payments_fee     ON payments(fee_id);
CREATE INDEX IF NOT EXISTS idx_fe_payments_student ON payments(student_id);

CREATE TABLE IF NOT EXISTS bursaries (
    bursary_id               INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id               TEXT NOT NULL,
    bursary_type             TEXT NOT NULL,
    status                   TEXT NOT NULL DEFAULT 'applied',
    amount_awarded           REAL NOT NULL DEFAULT 0,
    amount_paid              REAL NOT NULL DEFAULT 0,
    academic_year            TEXT,
    attendance_condition_pct REAL NOT NULL DEFAULT 90,
    applied_on               TEXT,
    decided_on               TEXT,
    decided_by               TEXT,
    evidence                 TEXT,
    notes                    TEXT,
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE,
    FOREIGN KEY (decided_by) REFERENCES staff(staff_id)      ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_fe_bursaries_student ON bursaries(student_id, status);

CREATE TABLE IF NOT EXISTS funding_allocations (
    allocation_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    funding_source TEXT NOT NULL,
    academic_year  TEXT NOT NULL,
    allocated      REAL NOT NULL DEFAULT 0,
    earned         REAL NOT NULL DEFAULT 0,
    learner_count  INTEGER NOT NULL DEFAULT 0,
    notes          TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_fe_funding_unique
    ON funding_allocations(funding_source, academic_year);
"""

# ── Facilities & pastoral ───────────────────────────────────────────────────

_FACILITIES_SCHEMA = """
CREATE TABLE IF NOT EXISTS equipment (
    asset_id       TEXT PRIMARY KEY,
    name           TEXT NOT NULL,
    category       TEXT NOT NULL,
    status         TEXT NOT NULL DEFAULT 'available',
    room_id        TEXT,
    serial_number  TEXT,
    purchased_on   TEXT,
    last_inspected TEXT,
    loaned_to      TEXT,
    loan_due       TEXT,
    notes          TEXT,
    FOREIGN KEY (room_id) REFERENCES rooms(room_id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_fe_equipment_status ON equipment(status);

CREATE TABLE IF NOT EXISTS bookings (
    booking_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    room_id      TEXT NOT NULL,
    booking_date TEXT NOT NULL,
    start_time   TEXT NOT NULL,
    end_time     TEXT NOT NULL,
    purpose      TEXT NOT NULL DEFAULT 'Meeting',
    booked_by    TEXT,
    status       TEXT NOT NULL DEFAULT 'confirmed',
    headcount    INTEGER NOT NULL DEFAULT 0,
    notes        TEXT,
    FOREIGN KEY (room_id)   REFERENCES rooms(room_id) ON DELETE CASCADE,
    FOREIGN KEY (booked_by) REFERENCES staff(staff_id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_fe_bookings_room ON bookings(room_id, booking_date);
"""

_PASTORAL_SCHEMA = """
CREATE TABLE IF NOT EXISTS tutorials (
    tutorial_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id           TEXT NOT NULL,
    tutor_id             TEXT,
    tutorial_type        TEXT NOT NULL DEFAULT 'Individual review',
    status               TEXT NOT NULL DEFAULT 'scheduled',
    scheduled_for        TEXT,
    held_on              TEXT,
    attendance_discussed INTEGER NOT NULL DEFAULT 0,
    progress_discussed   INTEGER NOT NULL DEFAULT 0,
    targets_set          TEXT,
    notes                TEXT,
    student_comment      TEXT,
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE,
    FOREIGN KEY (tutor_id)   REFERENCES staff(staff_id)      ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_fe_tutorials_student ON tutorials(student_id, held_on);

CREATE TABLE IF NOT EXISTS behaviour_records (
    record_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id      TEXT NOT NULL,
    behaviour_type  TEXT NOT NULL,
    summary         TEXT NOT NULL,
    logged_by       TEXT,
    logged_on       TEXT,
    course_id       TEXT,
    detail          TEXT,
    action_taken    TEXT,
    parent_informed INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE,
    FOREIGN KEY (logged_by)  REFERENCES staff(staff_id)      ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_fe_behaviour_student ON behaviour_records(student_id, logged_on);

CREATE TABLE IF NOT EXISTS referrals (
    referral_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id    TEXT NOT NULL,
    referral_type TEXT NOT NULL,
    reason        TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'open',
    urgency       TEXT NOT NULL DEFAULT 'routine',
    referred_by   TEXT,
    referred_on   TEXT,
    assigned_to   TEXT,
    actioned_on   TEXT,
    closed_on     TEXT,
    outcome       TEXT,
    FOREIGN KEY (student_id)  REFERENCES students(student_id) ON DELETE CASCADE,
    FOREIGN KEY (referred_by) REFERENCES staff(staff_id)      ON DELETE SET NULL,
    FOREIGN KEY (assigned_to) REFERENCES staff(staff_id)      ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_fe_referrals_status  ON referrals(status, urgency);
CREATE INDEX IF NOT EXISTS idx_fe_referrals_student ON referrals(student_id);

CREATE TABLE IF NOT EXISTS wellbeing_checkins (
    checkin_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id       TEXT NOT NULL,
    mood             INTEGER NOT NULL,
    checked_on       TEXT,
    source           TEXT NOT NULL DEFAULT 'Self',
    note             TEXT,
    recorded_by      TEXT,
    follow_up_needed INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_fe_wellbeing_student ON wellbeing_checkins(student_id, checked_on);
"""

_COMMS_SCHEMA = """
-- One log of every message the college sends or receives, mirroring the
-- other systems' email centres. Addressed by email address rather than
-- always by learner, so admissions enquiries, employer correspondence and
-- supplier mail fit the same table as a message to a learner's parent.
--
-- ON DELETE SET NULL, not CASCADE: deleting a learner must not erase the
-- record that the college wrote to them. The correspondence is evidence of
-- what was communicated and when.
CREATE TABLE IF NOT EXISTS email_messages (
    message_id    TEXT PRIMARY KEY,
    direction     TEXT NOT NULL DEFAULT 'Outgoing',
    channel       TEXT NOT NULL DEFAULT 'Email',
    category      TEXT NOT NULL DEFAULT 'General',
    priority      TEXT NOT NULL DEFAULT 'Normal',
    status        TEXT NOT NULL DEFAULT 'Draft',
    subject       TEXT NOT NULL,
    body          TEXT,
    from_name     TEXT,
    from_address  TEXT,
    to_name       TEXT,
    to_address    TEXT,
    student_id    TEXT,
    staff_id      TEXT,
    tags          TEXT,
    created_at    TEXT DEFAULT (datetime('now')),
    sent_at       TEXT,
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE SET NULL,
    FOREIGN KEY (staff_id)   REFERENCES staff(staff_id)      ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_fe_email_status    ON email_messages(status);
CREATE INDEX IF NOT EXISTS idx_fe_email_direction ON email_messages(direction);
CREATE INDEX IF NOT EXISTS idx_fe_email_student   ON email_messages(student_id);
CREATE INDEX IF NOT EXISTS idx_fe_email_sent      ON email_messages(sent_at);
"""

# Order matters: reference tables before the rows that point at them, so the
# foreign keys resolve on a fresh database.
_ALL_SCHEMAS = (
    _STAFF_SCHEMA,
    _ROOMS_SCHEMA,
    _COURSES_SCHEMA,
    _STUDENTS_SCHEMA,
    _TEACHING_SCHEMA,
    _EXAMS_SCHEMA,
    _FINANCE_SCHEMA,
    _FACILITIES_SCHEMA,
    _PASTORAL_SCHEMA,
    _COMMS_SCHEMA,
)


_STUDENT_DETAIL_COLUMNS: tuple[tuple[str, str], ...] = (
    ("middle_name", "TEXT"),
    ("preferred_name", "TEXT"),
    ("gender", "TEXT"),
    ("address_line2", "TEXT"),
    ("town", "TEXT"),
    ("has_lldd", "INTEGER NOT NULL DEFAULT 0"),
    ("medical_notes", "TEXT"),
    ("emergency_contact_relationship", "TEXT"),
)


def _migrate(conn: sqlite3.Connection) -> None:
    """Bring an existing database up to the current schema.

    The scripts above only ever *create*: ``CREATE TABLE IF NOT EXISTS``
    is a no-op once the table is there, so a column added to a definition
    never reaches a database that already exists. Adding it here closes
    that gap. Every step must be idempotent — this runs on every launch.
    """
    cols = {r[1] for r in conn.execute("PRAGMA table_info(students)").fetchall()}
    if not cols:
        return  # fresh database; the scripts have just built it correctly
    if "journey_id" not in cols:
        conn.execute("ALTER TABLE students ADD COLUMN journey_id TEXT")
        logger.info("Added students.journey_id (cross-system identity link)")
    # Personal, address, emergency-contact and needs details (2026-11-06).
    for column, ddl in _STUDENT_DETAIL_COLUMNS:
        if column not in cols:
            conn.execute(f"ALTER TABLE students ADD COLUMN {column} {ddl}")
            logger.info("Added students.%s", column)
    # Deferred until the column is known to exist.
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_fe_students_journey "
        "ON students(journey_id) WHERE journey_id IS NOT NULL")


def init_db() -> None:
    """Create every table and index. Idempotent — safe on every launch."""
    ensure_directories()
    with transaction() as conn:
        for script in _ALL_SCHEMAS:
            conn.executescript(script)
        _migrate(conn)
    logger.debug("FE College schema ready")


def is_empty() -> bool:
    """Whether the database holds no learners yet."""
    try:
        conn = connect()
    except sqlite3.Error:
        return True
    try:
        row = conn.execute("SELECT COUNT(*) FROM students").fetchone()
        return (row[0] if row else 0) == 0
    except sqlite3.Error:
        # No students table yet — an uninitialised database is empty.
        return True
    finally:
        conn.close()


def bootstrap(seed: bool | None = None) -> None:
    """Initialise the schema and, on a fresh database, seed demo data.

    ``seed`` defaults to the ``EDU_DEV_SEED`` flag the rest of the platform
    uses, so a production launch gets an empty college and a dev launch gets
    something to look at. Seeding never runs against a database that already
    holds learners.
    """
    init_db()
    if seed is None:
        seed = os.environ.get("EDU_DEV_SEED", "").strip().lower() in ("1", "true", "yes", "on")
    if not seed or not is_empty():
        return
    from education_system.systems.fe_college.infrastructure.persistence import demo_data

    try:
        demo_data.seed()
        logger.info("Seeded FE College demo data")
    except Exception:
        logger.exception("FE College demo seeding failed — continuing with an empty college")


def reset_db() -> None:
    """Drop every FE College table and recreate the schema.

    Development helper. Deliberately not reachable from any interface — it is
    called by tests and by an operator at a REPL, never by a menu item.
    """
    with transaction() as conn:
        names = [
            r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
        ]
        conn.execute("PRAGMA foreign_keys = OFF")
        for name in names:
            conn.execute(f'DROP TABLE IF EXISTS "{name}"')
        conn.execute("PRAGMA foreign_keys = ON")
    init_db()


__all__ = ["bootstrap", "init_db", "is_empty", "reset_db"]
