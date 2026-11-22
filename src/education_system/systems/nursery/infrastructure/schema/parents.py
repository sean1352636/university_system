"""Parent contacts, consents, messages, updates, newsletters, meetings, requests and signed forms.

Split out of ``database.py``, which imports every name here and keeps
``connect``/``init_db``. Import from ``database``, not from here.
"""

from __future__ import annotations


# ── Parents & Communication ───────────────────────────────────────────────────

# ``parent_contacts`` = the parents / carers attached to a child. Captures who
# holds parental responsibility, who is allowed to collect and the primary
# day-to-day contact (the one the setting calls first). Distinct from
# ``emergency_contacts``, which are the back-up people called only when a parent
# can't be reached.
_PARENT_CONTACTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS parent_contacts (
    contact_id              TEXT PRIMARY KEY,
    pupil_id                TEXT NOT NULL,
    full_name               TEXT NOT NULL,
    relationship            TEXT,
    phone                   TEXT,
    email                   TEXT,
    address                 TEXT,
    is_primary              INTEGER NOT NULL DEFAULT 0,
    parental_responsibility INTEGER NOT NULL DEFAULT 1,
    can_collect             INTEGER NOT NULL DEFAULT 1,
    notes                   TEXT,
    created_at              TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_parent_contacts_pupil ON parent_contacts(pupil_id);
"""

# ``emergency_contacts`` = the back-up people a setting calls when a parent can't
# be reached. Ordered by ``priority`` (1 = call first). ``can_collect`` records
# whether they're on the authorised collection list as well.
_EMERGENCY_CONTACTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS emergency_contacts (
    contact_id     TEXT PRIMARY KEY,
    pupil_id       TEXT NOT NULL,
    full_name      TEXT NOT NULL,
    relationship   TEXT,
    phone_primary  TEXT,
    phone_alt      TEXT,
    priority       INTEGER NOT NULL DEFAULT 1,
    can_collect    INTEGER NOT NULL DEFAULT 0,
    notes          TEXT,
    created_at     TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_emergency_contacts_pupil ON emergency_contacts(pupil_id);
"""

# ``consents`` = the parental permissions a setting must record and be able to
# evidence (photos, outings, sun cream, emergency medical treatment, nappy
# changing, face painting, social media, etc.). Each row is one permission for
# one child with a granted / refused / pending status and an optional review /
# expiry date. The simple boolean consents on the ``enrolments`` record are the
# enrolment snapshot; this table is the living, auditable consent register.
_CONSENTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS consents (
    consent_id    TEXT PRIMARY KEY,
    pupil_id      TEXT NOT NULL,
    consent_type  TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'granted',
    date_recorded TEXT,
    expiry_date   TEXT,
    recorded_by   TEXT,
    notes         TEXT,
    created_at    TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE,
    FOREIGN KEY (recorded_by) REFERENCES staff(staff_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_consents_pupil  ON consents(pupil_id);
CREATE INDEX IF NOT EXISTS idx_consents_status ON consents(status);
"""

# ``parent_messages`` = the two-way message log with parents (nursery app,
# email, SMS, phone or in-person notes). ``direction`` is outgoing/incoming and
# ``status`` tracks draft → sent → read → replied so staff can see what is
# outstanding.
_PARENT_MESSAGES_SCHEMA = """
CREATE TABLE IF NOT EXISTS parent_messages (
    message_id   TEXT PRIMARY KEY,
    pupil_id     TEXT NOT NULL,
    direction    TEXT NOT NULL DEFAULT 'outgoing',
    channel      TEXT,
    subject      TEXT,
    body         TEXT,
    message_date TEXT,
    staff_id     TEXT,
    status       TEXT NOT NULL DEFAULT 'sent',
    created_at   TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE,
    FOREIGN KEY (staff_id) REFERENCES staff(staff_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_parent_messages_pupil  ON parent_messages(pupil_id);
CREATE INDEX IF NOT EXISTS idx_parent_messages_status ON parent_messages(status);
"""

# ``daily_updates`` = the at-a-glance "how was my child's day" summary shared
# with parents (mood, meals, sleep, nappies/toileting and activities). One row
# per child per day; ``shared`` flips to 1 once it's been sent to the parent.
# Complements the fuller free-text ``daily_diary`` and the specialist sleep /
# nappy / meal logs by rolling them into a single parent-facing update.
_DAILY_UPDATES_SCHEMA = """
CREATE TABLE IF NOT EXISTS daily_updates (
    update_id   TEXT PRIMARY KEY,
    pupil_id    TEXT NOT NULL,
    update_date TEXT,
    mood        TEXT,
    meals       TEXT,
    sleep       TEXT,
    nappies     TEXT,
    activities  TEXT,
    notes       TEXT,
    staff_id    TEXT,
    shared      INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE,
    FOREIGN KEY (staff_id) REFERENCES staff(staff_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_daily_updates_pupil ON daily_updates(pupil_id);
CREATE INDEX IF NOT EXISTS idx_daily_updates_date  ON daily_updates(update_date);
"""

# ``newsletters`` = setting-wide bulletins issued to parents (whole setting or a
# single room). Not attached to a child. Moves draft → published, stamping
# ``published_date`` when it goes out.
_NEWSLETTERS_SCHEMA = """
CREATE TABLE IF NOT EXISTS newsletters (
    newsletter_id  TEXT PRIMARY KEY,
    title          TEXT NOT NULL,
    issue_date     TEXT,
    audience       TEXT,
    body           TEXT,
    author         TEXT,
    status         TEXT NOT NULL DEFAULT 'draft',
    published_date TEXT,
    created_at     TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (author) REFERENCES staff(staff_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_newsletters_status ON newsletters(status);
"""

# ``parent_meetings`` = scheduled meetings / consultations with a child's
# parents (settling review, progress chat, 2-year check, concern, parents'
# evening). Moves scheduled → completed/cancelled; ``summary`` holds the agreed
# outcome once held.
_PARENT_MEETINGS_SCHEMA = """
CREATE TABLE IF NOT EXISTS parent_meetings (
    meeting_id   TEXT PRIMARY KEY,
    pupil_id     TEXT NOT NULL,
    meeting_date TEXT,
    meeting_time TEXT,
    meeting_type TEXT,
    staff_id     TEXT,
    location     TEXT,
    status       TEXT NOT NULL DEFAULT 'scheduled',
    summary      TEXT,
    notes        TEXT,
    created_at   TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE,
    FOREIGN KEY (staff_id) REFERENCES staff(staff_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_parent_meetings_pupil  ON parent_meetings(pupil_id);
CREATE INDEX IF NOT EXISTS idx_parent_meetings_status ON parent_meetings(status);
"""

# ── Parent self-service ──────────────────────────────────────────────────────

# ``parent_requests`` = everything a parent submits for themselves rather than
# phoning the office: an extra session, an absence, a change of address, a
# consent answer. ``payload`` holds the type-specific body as JSON. Approving a
# request **applies** it to the real domain table and stamps ``applied_ref``, so
# nothing is ever re-keyed by staff.
_PARENT_REQUESTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS parent_requests (
    request_id    TEXT PRIMARY KEY,
    pupil_id      TEXT NOT NULL,
    request_type  TEXT NOT NULL,
    submitted_by  TEXT,
    submitted_at  TEXT NOT NULL,
    payload       TEXT,
    status        TEXT NOT NULL DEFAULT 'pending',
    decided_by    TEXT,
    decided_at    TEXT,
    decision_note TEXT,
    applied_ref   TEXT,
    notes         TEXT,
    created_at    TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE,
    FOREIGN KEY (decided_by) REFERENCES staff(staff_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_parent_requests_pupil  ON parent_requests(pupil_id);
CREATE INDEX IF NOT EXISTS idx_parent_requests_status ON parent_requests(status);
CREATE INDEX IF NOT EXISTS idx_parent_requests_type   ON parent_requests(request_type);
"""

# ── Digital registration forms & signatures ──────────────────────────────────

# ``form_templates`` = the wording a parent is asked to sign, versioned. Editing
# the wording of a live form issues a NEW version rather than mutating the old
# one, so a signature always points at exactly what was agreed.
_FORM_TEMPLATES_SCHEMA = """
CREATE TABLE IF NOT EXISTS form_templates (
    template_id    TEXT PRIMARY KEY,
    name           TEXT NOT NULL,
    form_type      TEXT NOT NULL,
    version        TEXT NOT NULL DEFAULT '1.0',
    body           TEXT NOT NULL,
    required       INTEGER NOT NULL DEFAULT 1,
    renew_months   INTEGER,
    status         TEXT NOT NULL DEFAULT 'active',
    effective_from TEXT,
    superseded_by  TEXT,
    notes          TEXT,
    created_at     TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_form_templates_type ON form_templates(form_type);
CREATE UNIQUE INDEX IF NOT EXISTS idx_form_templates_version
    ON form_templates(form_type, version);
"""

# ``form_submissions`` = a signed return. It pins the template version and a
# hash of the exact wording, plus a signature digest over (form, signer, time),
# so a later edit to the template can never silently change what was signed.
_FORM_SUBMISSIONS_SCHEMA = """
CREATE TABLE IF NOT EXISTS form_submissions (
    submission_id    TEXT PRIMARY KEY,
    template_id      TEXT NOT NULL,
    form_type        TEXT NOT NULL,
    template_version TEXT NOT NULL,
    body_hash        TEXT NOT NULL,
    pupil_id         TEXT NOT NULL,
    respondent_name  TEXT NOT NULL,
    respondent_relationship TEXT,
    signature_name   TEXT,
    signed_at        TEXT,
    signature_hash   TEXT,
    source           TEXT NOT NULL DEFAULT 'portal',
    answers          TEXT,
    status           TEXT NOT NULL DEFAULT 'signed',
    witnessed_by     TEXT,
    notes            TEXT,
    created_at       TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (template_id) REFERENCES form_templates(template_id)
        ON DELETE CASCADE,
    FOREIGN KEY (pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE,
    FOREIGN KEY (witnessed_by) REFERENCES staff(staff_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_form_submissions_pupil ON form_submissions(pupil_id);
CREATE INDEX IF NOT EXISTS idx_form_submissions_type  ON form_submissions(form_type);
"""
