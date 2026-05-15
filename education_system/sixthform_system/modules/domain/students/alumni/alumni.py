"""Alumni — leavers' destinations and contact register.

One row per former student. An alumni record can be created either:

* manually (e.g. for someone who left before the system was deployed),
  via :func:`create_alumnus`, or

* by archiving an existing student via :func:`archive_student`, which
  copies their identifying fields onto a new alumnus row, optionally
  deletes the underlying ``students`` row, and stores a back-reference
  to the original student id.

The shape is deliberately broader than the Students table so we can
keep alumni reachable: home email, phone, social-media handles, current
employer / role / location, and an opt-in-contact flag for whether
they want us to reach out (school events, references, mentoring, etc.).
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
import secrets
import sqlite3
from dataclasses import dataclass
from typing import Any, Callable
from education_system.sixthform_system.core import paths
from education_system.sixthform_system.core import log_store
from education_system.sixthform_system.modules.domain.students.alumni import (
    alumni as data,
)

logger = logging.getLogger(__name__)

# Make sure logger records emitted from this module land in the
# sixth-form ``system_logs`` SQLite table — this is idempotent and
# cheap, so it's safe to do at import time.
try:
    log_store.install()
except Exception:
    # Never let logging setup break the module — fall back to plain
    # Python logging if the DB handler can't be attached.
    logger.exception("Failed to attach log_store handler")


def _log_action(action: str, *, actor: str | None = None,
                  level: int = logging.INFO, **fields: Any) -> None:
    """Emit a structured user-action log record. Fields are folded
    into the log line so the ``system_logs`` table captures who did
    what (the matching ``alumni_audit_log`` table still holds the
    per-field diff for alumni updates).

    Always called for side-effecting operations: create, update,
    delete, merge, send, import, export, etc. Never raises — if
    logging itself fails the caller is unaffected."""
    try:
        bits: list[str] = [f"action={action}"]
        if actor:
            bits.append(f"actor={actor}")
        for k, v in fields.items():
            if v is None or v == "":
                continue
            s = str(v)
            if len(s) > 120:
                s = s[:117] + "..."
            bits.append(f"{k}={s}")
        logger.log(level, " ".join(bits))
    except Exception:
        # Logging must never crash the calling path.
        pass

DB_PATH = paths.ALUMNI_DB


DESTINATION_TYPES: tuple[str, ...] = (
    "University",
    "Apprenticeship",
    "Employment",
    "Gap Year",
    "Further Study",
    "Self-Employed",
    "Volunteering",
    "Unknown",
    "Other",
)
DEFAULT_DESTINATION: str = "Unknown"

LEAVING_REASONS: tuple[str, ...] = (
    "Completed Course",
    "Transferred Out",
    "Withdrew",
    "Excluded",
    "Health / Personal",
    "Other",
)
DEFAULT_LEAVING_REASON: str = "Completed Course"

STATUSES: tuple[str, ...] = (
    "Active", "Lost Contact", "Deceased", "Opt-out",
)
DEFAULT_STATUS: str = "Active"

GENDER_OPTIONS: tuple[str, ...] = (
    "Female", "Male", "Non-binary", "Prefer not to say", "Other",
)

SECTORS: tuple[str, ...] = (
    "Technology", "Finance", "Healthcare", "Education",
    "Public Sector", "Legal", "Engineering", "Manufacturing",
    "Retail", "Hospitality", "Media", "Arts & Creative",
    "Charity / Non-profit", "Armed Forces", "Sciences & Research",
    "Construction", "Agriculture", "Other",
)

SALARY_BANDS: tuple[str, ...] = (
    "Under £20k", "£20k–£30k", "£30k–£45k", "£45k–£60k",
    "£60k–£80k", "£80k–£100k", "£100k+", "Prefer not to say",
)

EDUCATION_STATUSES: tuple[str, ...] = (
    "In Progress", "Completed", "Withdrawn", "Deferred",
)
DEFAULT_EDUCATION_STATUS: str = "In Progress"

ACHIEVEMENT_CATEGORIES: tuple[str, ...] = (
    "Award", "Publication", "Promotion", "Public Recognition",
    "Qualification", "Other",
)

EMAIL_LABELS: tuple[str, ...] = ("Personal", "Work", "Other")
PHONE_LABELS: tuple[str, ...] = ("Mobile", "Home", "Work", "Other")

CONSENT_SCOPES: tuple[str, ...] = (
    "Newsletter", "Events", "Fundraising", "Mentoring", "Surveys",
    "Photo Use", "Data Storage", "Directory",
)
DIRECTORY_CONSENT_SCOPE: str = "Directory"

SOCIAL_PLATFORMS: tuple[str, ...] = (
    "LinkedIn", "GitHub", "ORCID", "Twitter/X", "Instagram",
    "Facebook", "Mastodon", "Bluesky", "TikTok", "YouTube",
    "Personal Site", "Other",
)
CONNECTION_KINDS: tuple[str, ...] = (
    "Friend", "Classmate", "Colleague", "Mentor", "Family", "Other",
)
CHAPTER_ROLES: tuple[str, ...] = (
    "Member", "Officer", "Chair", "Treasurer", "Secretary",
)
CONSENT_VERSION: str = "v1"
PORTAL_TOKEN_TTL_DAYS: int = 14
HARD_BOUNCE_THRESHOLD: int = 3

EVENT_TYPES: tuple[str, ...] = (
    "Reunion", "Careers Fair", "Prize-Giving", "Networking",
    "Lecture", "Workshop", "Awards", "Other",
)
EVENT_STATUSES: tuple[str, ...] = (
    "Planning", "Open", "Cancelled", "Completed",
)
DEFAULT_EVENT_STATUS: str = "Planning"

RSVP_STATUSES: tuple[str, ...] = (
    "Invited", "Accepted", "Declined", "Tentative", "No Response",
)
DEFAULT_RSVP_STATUS: str = "Invited"

MENTORSHIP_STATUSES: tuple[str, ...] = (
    "Active", "Paused", "Completed", "Cancelled",
)
DEFAULT_MENTORSHIP_STATUS: str = "Active"

SESSION_FORMATS: tuple[str, ...] = (
    "Video", "Phone", "In-Person", "Email", "Other",
)

WORK_EXP_STATUSES: tuple[str, ...] = (
    "Open", "Closed", "Filled", "Cancelled",
)
WORK_EXP_APP_STATUSES: tuple[str, ...] = (
    "Submitted", "Shortlisted", "Offered", "Accepted",
    "Declined", "Rejected", "Withdrawn",
)

REFERENCE_TYPES: tuple[str, ...] = (
    "UCAS", "Job", "Postgrad", "Personal", "Other",
)

VOLUNTEER_ACTIVITY_TYPES: tuple[str, ...] = (
    "Mock Interview", "Panel", "Workshop", "Mentoring",
    "Speaker / Talk", "Careers Fair", "Other",
)

PAYMENT_METHODS: tuple[str, ...] = (
    "Card", "Bank Transfer", "Direct Debit", "Cheque",
    "Cash", "Other",
)

PLEDGE_STATUSES: tuple[str, ...] = (
    "Open", "Fulfilled", "Partial", "Cancelled",
)
DEFAULT_PLEDGE_STATUS: str = "Open"

CAMPAIGN_STATUSES: tuple[str, ...] = (
    "Planning", "Active", "Closed", "Cancelled",
)
DEFAULT_CAMPAIGN_STATUS: str = "Active"

# Days a soft-deleted alumnus stays recoverable. After this it can
# be physically purged by ``purge_expired_soft_deletes``.
SOFT_DELETE_UNDO_DAYS: int = 30

SURVEY_INVITATION_TTL_DAYS: int = 60

# Fields that can be exported. Each is tagged with a sensitivity
# class used by the consent-respecting redaction layer.
EXPORT_FIELDS: tuple[tuple[str, str], ...] = (
    ("alumni_id",            "id"),
    ("original_student_id",  "id"),
    ("first_name",           "name"),
    ("last_name",            "name"),
    ("preferred_name",       "name"),
    ("pronouns",             "name"),
    ("gender",               "sensitive"),
    ("dob",                  "sensitive"),
    ("leaving_year",         "aggregate"),
    ("leaving_date",         "aggregate"),
    ("leaving_reason",       "aggregate"),
    ("destination_type",     "aggregate"),
    ("destination_detail",   "aggregate"),
    ("current_role",         "professional"),
    ("current_employer",     "professional"),
    ("current_sector",       "aggregate"),
    ("current_location",     "professional"),
    ("country",              "aggregate"),
    ("region",               "aggregate"),
    ("email",                "contact"),
    ("phone",                "contact"),
    ("address",              "contact"),
    ("linkedin",             "professional"),
    ("other_social",         "contact"),
    ("bio",                  "public"),
    ("photo_path",           "public"),
    ("status",               "aggregate"),
    ("last_contacted",       "aggregate"),
    ("notes",                "internal"),
)


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_DATE_RE  = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_YEAR_RE  = re.compile(r"^(19|20|21)\d{2}$")
_PHONE_RE = re.compile(r"^[0-9 +()\-]+$")


_SCHEMA = """
CREATE TABLE IF NOT EXISTS alumni (
    alumni_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    original_student_id  TEXT,
    first_name           TEXT NOT NULL,
    last_name            TEXT NOT NULL,
    preferred_name       TEXT,
    pronouns             TEXT,
    gender               TEXT,
    dob                  TEXT,
    leaving_year         TEXT,
    leaving_date         TEXT,
    leaving_reason       TEXT,
    destination_type     TEXT NOT NULL DEFAULT 'Unknown',
    destination_detail   TEXT,
    current_role         TEXT,
    current_employer     TEXT,
    current_sector       TEXT,
    current_location     TEXT,
    country              TEXT,
    region               TEXT,
    email                TEXT,
    phone                TEXT,
    address              TEXT,
    linkedin             TEXT,
    other_social         TEXT,
    photo_path           TEXT,
    bio                  TEXT,
    opt_in_contact       INTEGER NOT NULL DEFAULT 0,
    status               TEXT NOT NULL DEFAULT 'Active',
    last_contacted       TEXT,
    notes                TEXT,
    created_at           TEXT DEFAULT (datetime('now')),
    updated_at           TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_alm_last_name      ON alumni(last_name);
CREATE INDEX IF NOT EXISTS idx_alm_leaving_year   ON alumni(leaving_year);
CREATE INDEX IF NOT EXISTS idx_alm_destination    ON alumni(destination_type);
CREATE INDEX IF NOT EXISTS idx_alm_status         ON alumni(status);
CREATE INDEX IF NOT EXISTS idx_alm_original       ON alumni(original_student_id);

CREATE TABLE IF NOT EXISTS alumni_education (
    education_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    alumni_id      INTEGER NOT NULL,
    qualification  TEXT NOT NULL,
    subject        TEXT,
    institution    TEXT NOT NULL,
    start_date     TEXT,
    end_date       TEXT,
    grade          TEXT,
    status         TEXT NOT NULL DEFAULT 'In Progress',
    notes          TEXT,
    created_at     TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (alumni_id) REFERENCES alumni(alumni_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_aedu_alumni ON alumni_education(alumni_id);

CREATE TABLE IF NOT EXISTS alumni_career (
    career_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    alumni_id      INTEGER NOT NULL,
    role           TEXT NOT NULL,
    employer       TEXT NOT NULL,
    sector         TEXT,
    country        TEXT,
    location       TEXT,
    start_date     TEXT,
    end_date       TEXT,
    is_current     INTEGER NOT NULL DEFAULT 0,
    salary_band    TEXT,
    notes          TEXT,
    created_at     TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (alumni_id) REFERENCES alumni(alumni_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_acar_alumni ON alumni_career(alumni_id);
CREATE INDEX IF NOT EXISTS idx_acar_sector ON alumni_career(sector);

CREATE TABLE IF NOT EXISTS alumni_emails (
    email_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    alumni_id   INTEGER NOT NULL,
    email       TEXT NOT NULL,
    label       TEXT NOT NULL DEFAULT 'Personal',
    is_primary  INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (alumni_id) REFERENCES alumni(alumni_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_aeml_alumni ON alumni_emails(alumni_id);

CREATE TABLE IF NOT EXISTS alumni_phones (
    phone_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    alumni_id   INTEGER NOT NULL,
    phone       TEXT NOT NULL,
    label       TEXT NOT NULL DEFAULT 'Mobile',
    is_primary  INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (alumni_id) REFERENCES alumni(alumni_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_aphn_alumni ON alumni_phones(alumni_id);

CREATE TABLE IF NOT EXISTS alumni_tags (
    tag_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE COLLATE NOCASE
);

CREATE TABLE IF NOT EXISTS alumni_tag_links (
    alumni_id   INTEGER NOT NULL,
    tag_id      INTEGER NOT NULL,
    PRIMARY KEY (alumni_id, tag_id),
    FOREIGN KEY (alumni_id) REFERENCES alumni(alumni_id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id)    REFERENCES alumni_tags(tag_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_atag_tag ON alumni_tag_links(tag_id);

CREATE TABLE IF NOT EXISTS alumni_achievements (
    achievement_id INTEGER PRIMARY KEY AUTOINCREMENT,
    alumni_id      INTEGER NOT NULL,
    date           TEXT,
    title          TEXT NOT NULL,
    category       TEXT,
    description    TEXT,
    url            TEXT,
    created_at     TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (alumni_id) REFERENCES alumni(alumni_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_aach_alumni ON alumni_achievements(alumni_id);

CREATE TABLE IF NOT EXISTS alumni_channel_prefs (
    alumni_id     INTEGER PRIMARY KEY,
    opt_in_email  INTEGER NOT NULL DEFAULT 1,
    opt_in_post   INTEGER NOT NULL DEFAULT 1,
    opt_in_phone  INTEGER NOT NULL DEFAULT 1,
    opt_in_sms    INTEGER NOT NULL DEFAULT 1,
    updated_at    TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (alumni_id) REFERENCES alumni(alumni_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS alumni_consent (
    consent_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    alumni_id     INTEGER NOT NULL,
    scope         TEXT NOT NULL,
    version       TEXT NOT NULL,
    granted_at    TEXT NOT NULL,
    withdrawn_at  TEXT,
    source        TEXT,
    notes         TEXT,
    FOREIGN KEY (alumni_id) REFERENCES alumni(alumni_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_acon_alumni ON alumni_consent(alumni_id);
CREATE INDEX IF NOT EXISTS idx_acon_scope  ON alumni_consent(scope);

CREATE TABLE IF NOT EXISTS alumni_portal_tokens (
    token       TEXT PRIMARY KEY,
    alumni_id   INTEGER NOT NULL,
    expires_at  TEXT NOT NULL,
    used_at     TEXT,
    created_at  TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (alumni_id) REFERENCES alumni(alumni_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_atok_alumni ON alumni_portal_tokens(alumni_id);

CREATE TABLE IF NOT EXISTS alumni_events (
    event_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    event_type  TEXT NOT NULL DEFAULT 'Reunion',
    event_date  TEXT,
    end_date    TEXT,
    location    TEXT,
    capacity    INTEGER,
    cost_pence  INTEGER NOT NULL DEFAULT 0,
    status      TEXT NOT NULL DEFAULT 'Planning',
    notes       TEXT,
    created_at  TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_aevt_date   ON alumni_events(event_date);
CREATE INDEX IF NOT EXISTS idx_aevt_status ON alumni_events(status);

CREATE TABLE IF NOT EXISTS alumni_event_rsvps (
    rsvp_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id    INTEGER NOT NULL,
    alumni_id   INTEGER NOT NULL,
    status      TEXT NOT NULL DEFAULT 'Invited',
    attended    INTEGER NOT NULL DEFAULT 0,
    guests      INTEGER NOT NULL DEFAULT 0,
    notes       TEXT,
    created_at  TEXT DEFAULT (datetime('now')),
    UNIQUE(event_id, alumni_id),
    FOREIGN KEY (event_id)  REFERENCES alumni_events(event_id) ON DELETE CASCADE,
    FOREIGN KEY (alumni_id) REFERENCES alumni(alumni_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_arsvp_alumni ON alumni_event_rsvps(alumni_id);

CREATE TABLE IF NOT EXISTS alumni_mentorships (
    mentorship_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    mentor_alumni_id  INTEGER NOT NULL,
    mentee_student_id TEXT NOT NULL,
    topic             TEXT,
    started_on        TEXT NOT NULL,
    ended_on          TEXT,
    status            TEXT NOT NULL DEFAULT 'Active',
    notes             TEXT,
    created_at        TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (mentor_alumni_id) REFERENCES alumni(alumni_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_amen_mentor ON alumni_mentorships(mentor_alumni_id);
CREATE INDEX IF NOT EXISTS idx_amen_mentee ON alumni_mentorships(mentee_student_id);

CREATE TABLE IF NOT EXISTS alumni_mentor_sessions (
    session_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    mentorship_id    INTEGER NOT NULL,
    session_date     TEXT NOT NULL,
    duration_minutes INTEGER,
    format           TEXT,
    summary          TEXT,
    mentor_feedback  TEXT,
    mentee_feedback  TEXT,
    created_at       TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (mentorship_id) REFERENCES alumni_mentorships(mentorship_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_amses_mship ON alumni_mentor_sessions(mentorship_id);

CREATE TABLE IF NOT EXISTS alumni_speakers (
    alumni_id           INTEGER PRIMARY KEY,
    topics              TEXT,
    year_groups         TEXT,
    availability_notes  TEXT,
    last_confirmed_at   TEXT,
    updated_at          TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (alumni_id) REFERENCES alumni(alumni_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS alumni_work_exp_offers (
    offer_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    alumni_id       INTEGER NOT NULL,
    title           TEXT NOT NULL,
    employer        TEXT,
    sector          TEXT,
    location        TEXT,
    duration_weeks  INTEGER,
    start_window    TEXT,
    vacancy_count   INTEGER NOT NULL DEFAULT 1,
    requirements    TEXT,
    deadline        TEXT,
    status          TEXT NOT NULL DEFAULT 'Open',
    notes           TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (alumni_id) REFERENCES alumni(alumni_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_awxo_alumni ON alumni_work_exp_offers(alumni_id);
CREATE INDEX IF NOT EXISTS idx_awxo_status ON alumni_work_exp_offers(status);

CREATE TABLE IF NOT EXISTS alumni_work_exp_applications (
    application_id INTEGER PRIMARY KEY AUTOINCREMENT,
    offer_id       INTEGER NOT NULL,
    student_id     TEXT NOT NULL,
    applied_on     TEXT NOT NULL,
    status         TEXT NOT NULL DEFAULT 'Submitted',
    outcome_notes  TEXT,
    UNIQUE(offer_id, student_id),
    FOREIGN KEY (offer_id) REFERENCES alumni_work_exp_offers(offer_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS alumni_references (
    reference_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    alumni_id     INTEGER NOT NULL,
    staff_id      TEXT,
    ref_type      TEXT NOT NULL DEFAULT 'Job',
    requested_on  TEXT,
    sent_on       TEXT,
    target_name   TEXT,
    target_url    TEXT,
    notes         TEXT,
    created_at    TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (alumni_id) REFERENCES alumni(alumni_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_aref_alumni ON alumni_references(alumni_id);

CREATE TABLE IF NOT EXISTS alumni_volunteer_hours (
    volunteer_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    alumni_id      INTEGER NOT NULL,
    activity_date  TEXT NOT NULL,
    hours          REAL NOT NULL,
    activity_type  TEXT NOT NULL DEFAULT 'Other',
    event_id       INTEGER,
    notes          TEXT,
    created_at     TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (alumni_id) REFERENCES alumni(alumni_id) ON DELETE CASCADE,
    FOREIGN KEY (event_id)  REFERENCES alumni_events(event_id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_avol_alumni ON alumni_volunteer_hours(alumni_id);

CREATE TABLE IF NOT EXISTS alumni_campaigns (
    campaign_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL UNIQUE COLLATE NOCASE,
    description   TEXT,
    target_pence  INTEGER,
    start_on      TEXT,
    end_on        TEXT,
    status        TEXT NOT NULL DEFAULT 'Active',
    created_at    TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS alumni_donations (
    donation_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    alumni_id      INTEGER NOT NULL,
    campaign_id    INTEGER,
    donation_date  TEXT NOT NULL,
    amount_pence   INTEGER NOT NULL,
    gift_aid       INTEGER NOT NULL DEFAULT 0,
    payment_method TEXT,
    anonymous      INTEGER NOT NULL DEFAULT 0,
    restricted_to  TEXT,
    notes          TEXT,
    created_at     TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (alumni_id)   REFERENCES alumni(alumni_id) ON DELETE CASCADE,
    FOREIGN KEY (campaign_id) REFERENCES alumni_campaigns(campaign_id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_adon_alumni   ON alumni_donations(alumni_id);
CREATE INDEX IF NOT EXISTS idx_adon_campaign ON alumni_donations(campaign_id);
CREATE INDEX IF NOT EXISTS idx_adon_date     ON alumni_donations(donation_date);

CREATE TABLE IF NOT EXISTS alumni_pledges (
    pledge_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    alumni_id     INTEGER NOT NULL,
    campaign_id   INTEGER,
    pledged_on    TEXT NOT NULL,
    amount_pence  INTEGER NOT NULL,
    due_by        TEXT,
    status        TEXT NOT NULL DEFAULT 'Open',
    notes         TEXT,
    created_at    TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (alumni_id)   REFERENCES alumni(alumni_id) ON DELETE CASCADE,
    FOREIGN KEY (campaign_id) REFERENCES alumni_campaigns(campaign_id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_apld_alumni   ON alumni_pledges(alumni_id);
CREATE INDEX IF NOT EXISTS idx_apld_campaign ON alumni_pledges(campaign_id);

CREATE TABLE IF NOT EXISTS alumni_audit_log (
    audit_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    alumni_id   INTEGER NOT NULL,
    field       TEXT NOT NULL,
    old_value   TEXT,
    new_value   TEXT,
    changed_by  TEXT,
    changed_at  TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (alumni_id) REFERENCES alumni(alumni_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_aaud_alumni ON alumni_audit_log(alumni_id);
CREATE INDEX IF NOT EXISTS idx_aaud_when   ON alumni_audit_log(changed_at);

CREATE TABLE IF NOT EXISTS alumni_saved_searches (
    search_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    name             TEXT NOT NULL UNIQUE COLLATE NOCASE,
    description      TEXT,
    filters_json     TEXT NOT NULL,
    owner_staff_id   TEXT,
    created_at       TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS alumni_surveys (
    survey_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    name           TEXT NOT NULL,
    description    TEXT,
    questions_json TEXT NOT NULL,
    status         TEXT NOT NULL DEFAULT 'Draft',
    created_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS alumni_survey_invitations (
    invitation_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    survey_id      INTEGER NOT NULL,
    alumni_id      INTEGER NOT NULL,
    token          TEXT NOT NULL UNIQUE,
    sent_at        TEXT,
    completed_at   TEXT,
    expires_at     TEXT NOT NULL,
    UNIQUE(survey_id, alumni_id),
    FOREIGN KEY (survey_id) REFERENCES alumni_surveys(survey_id)
        ON DELETE CASCADE,
    FOREIGN KEY (alumni_id) REFERENCES alumni(alumni_id)
        ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_asinv_alumni ON alumni_survey_invitations(alumni_id);

CREATE TABLE IF NOT EXISTS alumni_survey_responses (
    response_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    invitation_id  INTEGER NOT NULL UNIQUE,
    answers_json   TEXT NOT NULL,
    submitted_at   TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (invitation_id)
        REFERENCES alumni_survey_invitations(invitation_id)
        ON DELETE CASCADE
);
"""

# Columns added after the initial release. Each entry is
# (column_name, "TYPE [DEFAULT ...]") — applied with ALTER TABLE on
# existing databases.
_ALUMNI_NEW_COLUMNS: tuple[tuple[str, str], ...] = (
    ("pronouns",       "TEXT"),
    ("gender",         "TEXT"),
    ("current_sector", "TEXT"),
    ("country",        "TEXT"),
    ("region",         "TEXT"),
    ("photo_path",     "TEXT"),
    ("bio",            "TEXT"),
    ("bounce_count",   "INTEGER NOT NULL DEFAULT 0"),
    ("deleted_at",     "TEXT"),
)


@dataclass
class Alumnus:
    alumni_id: int
    original_student_id: str | None
    first_name: str
    last_name: str
    preferred_name: str | None
    pronouns: str | None
    gender: str | None
    dob: str | None
    leaving_year: str | None
    leaving_date: str | None
    leaving_reason: str | None
    destination_type: str
    destination_detail: str | None
    current_role: str | None
    current_employer: str | None
    current_sector: str | None
    current_location: str | None
    country: str | None
    region: str | None
    email: str | None
    phone: str | None
    address: str | None
    linkedin: str | None
    other_social: str | None
    photo_path: str | None
    bio: str | None
    bounce_count: int
    opt_in_contact: bool
    status: str
    last_contacted: str | None
    notes: str | None
    deleted_at: str | None
    created_at: str
    updated_at: str

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def display_name(self) -> str:
        if self.preferred_name:
            return f"{self.preferred_name} ({self.first_name}) {self.last_name}"
        return self.full_name


@dataclass
class Education:
    education_id: int
    alumni_id: int
    qualification: str
    subject: str | None
    institution: str
    start_date: str | None
    end_date: str | None
    grade: str | None
    status: str
    notes: str | None
    created_at: str


@dataclass
class Career:
    career_id: int
    alumni_id: int
    role: str
    employer: str
    sector: str | None
    country: str | None
    location: str | None
    start_date: str | None
    end_date: str | None
    is_current: bool
    salary_band: str | None
    notes: str | None
    created_at: str


@dataclass
class AlumniEmail:
    email_id: int
    alumni_id: int
    email: str
    label: str
    is_primary: bool


@dataclass
class AlumniPhone:
    phone_id: int
    alumni_id: int
    phone: str
    label: str
    is_primary: bool


@dataclass
class Tag:
    tag_id: int
    name: str


@dataclass
class Achievement:
    achievement_id: int
    alumni_id: int
    date: str | None
    title: str
    category: str | None
    description: str | None
    url: str | None
    created_at: str


@dataclass
class ChannelPrefs:
    alumni_id: int
    opt_in_email: bool
    opt_in_post: bool
    opt_in_phone: bool
    opt_in_sms: bool
    updated_at: str


@dataclass
class Consent:
    consent_id: int
    alumni_id: int
    scope: str
    version: str
    granted_at: str
    withdrawn_at: str | None
    source: str | None
    notes: str | None


@dataclass
class PortalToken:
    token: str
    alumni_id: int
    expires_at: str
    used_at: str | None
    created_at: str


@dataclass
class UnarchivedLeaver:
    student_id: str
    full_name: str
    email: str | None
    ucas_cycle_year: int | None
    final_destination: str | None
    last_exam_year: int | None


@dataclass
class Summary:
    total: int
    by_status: dict[str, int]
    by_destination: dict[str, int]
    by_leaving_year: dict[str, int]
    contactable: int            # opt-in + status=Active + has email/phone
    no_contact_method: int      # status=Active but no email and no phone
    most_recent_year: str | None


# ── DB plumbing ────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    paths.ensure_directories()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


_DB_READY: bool = False


def _migrate_alumni_columns(conn: sqlite3.Connection) -> None:
    existing = {row[1] for row in conn.execute(
        "PRAGMA table_info(alumni)").fetchall()}
    for col, decl in _ALUMNI_NEW_COLUMNS:
        if col not in existing:
            conn.execute(f"ALTER TABLE alumni ADD COLUMN {col} {decl}")


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        _migrate_alumni_columns(conn)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_alm_sector "
            "ON alumni(current_sector)")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_alm_country "
            "ON alumni(country)")
        # Drop the legacy parallel comms table — comms now live in
        # the shared ``messages`` module.
        conn.execute("DROP TABLE IF EXISTS alumni_communications")
    logger.debug("Alumni schema ready at %s", DB_PATH)

    _DB_READY = True


def _opt(r: sqlite3.Row, key: str) -> Any:
    try:
        return r[key]
    except (IndexError, KeyError):
        return None


def _row(r: sqlite3.Row) -> Alumnus:
    return Alumnus(
        alumni_id=r["alumni_id"],
        original_student_id=r["original_student_id"],
        first_name=r["first_name"], last_name=r["last_name"],
        preferred_name=r["preferred_name"],
        pronouns=_opt(r, "pronouns"),
        gender=_opt(r, "gender"),
        dob=r["dob"],
        leaving_year=r["leaving_year"], leaving_date=r["leaving_date"],
        leaving_reason=r["leaving_reason"],
        destination_type=r["destination_type"],
        destination_detail=r["destination_detail"],
        current_role=r["current_role"],
        current_employer=r["current_employer"],
        current_sector=_opt(r, "current_sector"),
        current_location=r["current_location"],
        country=_opt(r, "country"),
        region=_opt(r, "region"),
        email=r["email"], phone=r["phone"], address=r["address"],
        linkedin=r["linkedin"], other_social=r["other_social"],
        photo_path=_opt(r, "photo_path"),
        bio=_opt(r, "bio"),
        bounce_count=int(_opt(r, "bounce_count") or 0),
        opt_in_contact=bool(r["opt_in_contact"]),
        status=r["status"], last_contacted=r["last_contacted"],
        notes=r["notes"],
        deleted_at=_opt(r, "deleted_at"),
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


# ── Validation ────────────────────────────────────────────────────

class ValidationError(ValueError):
    """User-supplied input is invalid. The message is intended for
    direct display in CLI/GUI surfaces — keep it concise and concrete."""


class NotFoundError(ValidationError):
    """Targeted lookup (e.g. by id) didn't match any row. Subclass of
    ValidationError so existing ``except ValidationError`` handlers
    keep working; callers that care about the distinction can catch
    this directly."""


class IntegrationError(ValidationError):
    """A side-effecting operation against an external resource failed
    — file system, optional dependency, pluggable callback. Carries
    the underlying cause via ``__cause__`` (set by ``raise … from``)."""


def _require(value, label: str):
    if value in (None, "") or (isinstance(value, str)
                                  and not value.strip()):
        raise ValidationError(f"{label} is required")
    return value


def _validate_date(value: Any, label: str, *,
                    required: bool = False) -> str | None:
    if value in (None, "") or (isinstance(value, str)
                                  and not value.strip()):
        if required:
            raise ValidationError(f"{label} is required")
        return None
    s = str(value).strip()
    if not _DATE_RE.match(s):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    try:
        _dt.date.fromisoformat(s)
    except ValueError:
        raise ValidationError(f"{label} is not a real date") from None
    return s


def _validate_year(value: Any) -> str | None:
    if value in (None, "") or (isinstance(value, str)
                                  and not value.strip()):
        return None
    s = str(value).strip()
    if not _YEAR_RE.match(s):
        raise ValidationError(
            "Leaving year must be a 4-digit year (e.g. 2024)")
    return s


def _validate_email(value: Any) -> str | None:
    if not value:
        return None
    s = str(value).strip()
    if not _EMAIL_RE.match(s):
        raise ValidationError("Email is not a valid address")
    return s


def _validate_phone(value: Any) -> str | None:
    if not value:
        return None
    s = str(value).strip()
    if not _PHONE_RE.match(s):
        raise ValidationError("Phone contains invalid characters")
    return s


def _validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["first_name"] = _require(payload.get("first_name"),
                                    "First name").strip()
    out["last_name"]  = _require(payload.get("last_name"),
                                    "Last name").strip()
    out["preferred_name"] = (payload.get("preferred_name")
                                or "").strip() or None
    out["pronouns"] = (payload.get("pronouns") or "").strip() or None
    gender = (payload.get("gender") or "").strip()
    if gender and gender not in GENDER_OPTIONS:
        raise ValidationError(
            f"Gender must be one of: {', '.join(GENDER_OPTIONS)}")
    out["gender"] = gender or None
    out["original_student_id"] = (
        payload.get("original_student_id") or "").strip() or None
    out["dob"]          = _validate_date(payload.get("dob"),
                                              "Date of birth")
    out["leaving_year"] = _validate_year(payload.get("leaving_year"))
    out["leaving_date"] = _validate_date(payload.get("leaving_date"),
                                              "Leaving date")
    reason = (payload.get("leaving_reason") or "").strip()
    if reason and reason not in LEAVING_REASONS:
        raise ValidationError(
            f"Leaving reason must be one of: "
            f"{', '.join(LEAVING_REASONS)}")
    out["leaving_reason"] = reason or None

    dest = (payload.get("destination_type") or DEFAULT_DESTINATION).strip()
    if dest not in DESTINATION_TYPES:
        raise ValidationError(
            f"Destination type must be one of: "
            f"{', '.join(DESTINATION_TYPES)}")
    out["destination_type"] = dest
    out["destination_detail"] = (payload.get("destination_detail")
                                   or "").strip() or None

    out["current_role"]      = (payload.get("current_role")
                                  or "").strip() or None
    out["current_employer"]  = (payload.get("current_employer")
                                  or "").strip() or None
    sector = (payload.get("current_sector") or "").strip()
    if sector and sector not in SECTORS:
        raise ValidationError(
            f"Sector must be one of: {', '.join(SECTORS)}")
    out["current_sector"]    = sector or None
    out["current_location"]  = (payload.get("current_location")
                                  or "").strip() or None
    out["country"] = (payload.get("country") or "").strip() or None
    out["region"]  = (payload.get("region")  or "").strip() or None
    out["email"]   = _validate_email(payload.get("email"))
    out["phone"]   = _validate_phone(payload.get("phone"))
    out["address"] = (payload.get("address") or "").strip() or None
    out["linkedin"]     = (payload.get("linkedin")
                              or "").strip() or None
    out["other_social"] = (payload.get("other_social")
                              or "").strip() or None
    out["photo_path"] = (payload.get("photo_path") or "").strip() or None
    out["bio"]        = (payload.get("bio") or "").strip() or None
    out["opt_in_contact"] = bool(payload.get("opt_in_contact"))

    status = (payload.get("status") or DEFAULT_STATUS).strip()
    if status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    out["status"] = status
    out["last_contacted"] = _validate_date(
        payload.get("last_contacted"), "Last contacted")
    out["notes"] = (payload.get("notes") or "").strip() or None
    return out


# ── CRUD ──────────────────────────────────────────────────────────

def create_alumnus(payload: dict[str, Any]) -> Alumnus:
    init_db()
    p = _validate_payload(payload)
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO alumni
                   (original_student_id, first_name, last_name,
                    preferred_name, pronouns, gender,
                    dob, leaving_year, leaving_date,
                    leaving_reason, destination_type,
                    destination_detail, current_role, current_employer,
                    current_sector, current_location, country, region,
                    email, phone, address,
                    linkedin, other_social, photo_path, bio,
                    opt_in_contact, status,
                    last_contacted, notes, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                       ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                       datetime('now'), datetime('now'))""",
            (p["original_student_id"], p["first_name"], p["last_name"],
             p["preferred_name"], p["pronouns"], p["gender"],
             p["dob"], p["leaving_year"],
             p["leaving_date"], p["leaving_reason"],
             p["destination_type"], p["destination_detail"],
             p["current_role"], p["current_employer"],
             p["current_sector"], p["current_location"],
             p["country"], p["region"],
             p["email"], p["phone"],
             p["address"], p["linkedin"], p["other_social"],
             p["photo_path"], p["bio"],
             1 if p["opt_in_contact"] else 0, p["status"],
             p["last_contacted"], p["notes"]),
        )
        conn.commit()
        new_id = cur.lastrowid
    out = get_alumnus(new_id)
    assert out is not None
    _log_action("alumnus.create", alumni_id=new_id,
                  name=f"{p['first_name']} {p['last_name']}",
                  leaving_year=p["leaving_year"],
                  destination=p["destination_type"])
    return out


def get_alumnus(alumni_id: int) -> Alumnus | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM alumni WHERE alumni_id = ?",
            (alumni_id,)).fetchone()
        return _row(r) if r else None


def get_alumnus_by_original_id(student_id: str) -> Alumnus | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM alumni "
            "WHERE original_student_id = ? "
            "ORDER BY alumni_id DESC LIMIT 1",
            (student_id.strip(),)).fetchone()
        return _row(r) if r else None


def list_alumni(
    *,
    leaving_year: str | None = None,
    destination_type: str | None = None,
    status: str | None = None,
    contactable_only: bool = False,
    search: str | None = None,
    employer: str | None = None,
    university: str | None = None,
    sector: str | None = None,
    country: str | None = None,
    tag: str | None = None,
    has_email: bool | None = None,
    include_deleted: bool = False,
) -> list[Alumnus]:
    init_db()
    clauses, args = [], []
    if not include_deleted:
        clauses.append("deleted_at IS NULL")
    if leaving_year:
        clauses.append("leaving_year = ?")
        args.append(_validate_year(leaving_year))
    if destination_type:
        if destination_type not in DESTINATION_TYPES:
            raise ValidationError(
                f"Destination type must be one of: "
                f"{', '.join(DESTINATION_TYPES)}")
        clauses.append("destination_type = ?")
        args.append(destination_type)
    if status:
        if status not in STATUSES:
            raise ValidationError(
                f"Status must be one of: {', '.join(STATUSES)}")
        clauses.append("status = ?")
        args.append(status)
    if contactable_only:
        clauses.append(
            "opt_in_contact = 1 AND status = 'Active' "
            "AND (email IS NOT NULL OR phone IS NOT NULL)")
    if employer:
        clauses.append(
            "(current_employer LIKE ? OR "
            " alumni_id IN (SELECT alumni_id FROM alumni_career "
            "                WHERE employer LIKE ?))")
        like = f"%{employer.strip()}%"
        args.extend([like, like])
    if university:
        # Either current destination detail or any historical
        # education record points at this institution.
        like = f"%{university.strip()}%"
        clauses.append(
            "((destination_type = 'University' "
            "  AND destination_detail LIKE ?) OR "
            " alumni_id IN (SELECT alumni_id FROM alumni_education "
            "                WHERE institution LIKE ?))")
        args.extend([like, like])
    if sector:
        if sector not in SECTORS:
            raise ValidationError(
                f"Sector must be one of: {', '.join(SECTORS)}")
        clauses.append(
            "(current_sector = ? OR "
            " alumni_id IN (SELECT alumni_id FROM alumni_career "
            "                WHERE sector = ? AND is_current = 1))")
        args.extend([sector, sector])
    if country:
        clauses.append("country = ?")
        args.append(country.strip())
    if tag:
        clauses.append(
            "alumni_id IN (SELECT l.alumni_id FROM alumni_tag_links l "
            "  JOIN alumni_tags t ON t.tag_id = l.tag_id "
            "  WHERE t.name = ? COLLATE NOCASE)")
        args.append(tag.strip())
    if has_email is True:
        clauses.append("email IS NOT NULL AND email != ''")
    elif has_email is False:
        clauses.append("(email IS NULL OR email = '')")
    if search:
        s = f"%{search.strip()}%"
        clauses.append(
            "(first_name LIKE ? OR last_name LIKE ? OR "
            "preferred_name LIKE ? OR email LIKE ? OR "
            "original_student_id LIKE ? OR current_employer LIKE ? "
            "OR destination_detail LIKE ?)")
        args.extend([s, s, s, s, s, s, s])
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM alumni {where} "
           "ORDER BY leaving_year DESC NULLS LAST, "
           "last_name ASC, first_name ASC")
    with _connect() as conn:
        return [_row(r) for r in conn.execute(sql, args).fetchall()]


def update_alumnus(alumni_id: int,
                    payload: dict[str, Any], *,
                    actor: str | None = None) -> Alumnus:
    """Update an alumnus and record any field-level changes in
    ``alumni_audit_log``. Pass ``actor`` (a staff id / username) to
    attribute the edit; if omitted the audit row records 'system'."""
    init_db()
    existing = get_alumnus(alumni_id)
    if existing is None:
        raise ValidationError(f"No alumnus #{alumni_id}")
    merged = {
        "original_student_id": payload.get("original_student_id",
                                            existing.original_student_id),
        "first_name":          payload.get("first_name",
                                            existing.first_name),
        "last_name":           payload.get("last_name",
                                            existing.last_name),
        "preferred_name":      payload.get("preferred_name",
                                            existing.preferred_name),
        "pronouns":            payload.get("pronouns",
                                            existing.pronouns),
        "gender":              payload.get("gender", existing.gender),
        "dob":                 payload.get("dob", existing.dob),
        "leaving_year":        payload.get("leaving_year",
                                            existing.leaving_year),
        "leaving_date":        payload.get("leaving_date",
                                            existing.leaving_date),
        "leaving_reason":      payload.get("leaving_reason",
                                            existing.leaving_reason),
        "destination_type":    payload.get("destination_type",
                                            existing.destination_type),
        "destination_detail":  payload.get("destination_detail",
                                            existing.destination_detail),
        "current_role":        payload.get("current_role",
                                            existing.current_role),
        "current_employer":    payload.get("current_employer",
                                            existing.current_employer),
        "current_sector":      payload.get("current_sector",
                                            existing.current_sector),
        "current_location":    payload.get("current_location",
                                            existing.current_location),
        "country":             payload.get("country", existing.country),
        "region":              payload.get("region", existing.region),
        "email":               payload.get("email", existing.email),
        "phone":               payload.get("phone", existing.phone),
        "address":             payload.get("address", existing.address),
        "linkedin":            payload.get("linkedin",
                                            existing.linkedin),
        "other_social":        payload.get("other_social",
                                            existing.other_social),
        "photo_path":          payload.get("photo_path",
                                            existing.photo_path),
        "bio":                 payload.get("bio", existing.bio),
        "opt_in_contact":      payload.get("opt_in_contact",
                                            existing.opt_in_contact),
        "status":              payload.get("status", existing.status),
        "last_contacted":      payload.get("last_contacted",
                                            existing.last_contacted),
        "notes":               payload.get("notes", existing.notes),
    }
    p = _validate_payload(merged)
    with _connect() as conn:
        conn.execute(
            """UPDATE alumni SET
                   original_student_id = ?, first_name = ?, last_name = ?,
                   preferred_name = ?, pronouns = ?, gender = ?,
                   dob = ?, leaving_year = ?,
                   leaving_date = ?, leaving_reason = ?,
                   destination_type = ?, destination_detail = ?,
                   current_role = ?, current_employer = ?,
                   current_sector = ?, current_location = ?,
                   country = ?, region = ?,
                   email = ?, phone = ?,
                   address = ?, linkedin = ?, other_social = ?,
                   photo_path = ?, bio = ?,
                   opt_in_contact = ?, status = ?, last_contacted = ?,
                   notes = ?, updated_at = datetime('now')
               WHERE alumni_id = ?""",
            (p["original_student_id"], p["first_name"], p["last_name"],
             p["preferred_name"], p["pronouns"], p["gender"],
             p["dob"], p["leaving_year"],
             p["leaving_date"], p["leaving_reason"],
             p["destination_type"], p["destination_detail"],
             p["current_role"], p["current_employer"],
             p["current_sector"], p["current_location"],
             p["country"], p["region"],
             p["email"], p["phone"],
             p["address"], p["linkedin"], p["other_social"],
             p["photo_path"], p["bio"],
             1 if p["opt_in_contact"] else 0, p["status"],
             p["last_contacted"], p["notes"], alumni_id),
        )
        conn.commit()
    out = get_alumnus(alumni_id)
    assert out is not None
    _audit_diff(existing, out, actor=actor)
    _log_action("alumnus.update", actor=actor, alumni_id=alumni_id,
                  status=out.status, fields=len(payload))
    return out


# Fields the audit log tracks. We deliberately skip purely
# derived/internal ones (created_at / updated_at / bounce_count).
_AUDITABLE_FIELDS: tuple[str, ...] = (
    "first_name", "last_name", "preferred_name", "pronouns",
    "gender", "dob", "leaving_year", "leaving_date",
    "leaving_reason", "destination_type", "destination_detail",
    "current_role", "current_employer", "current_sector",
    "current_location", "country", "region",
    "email", "phone", "address", "linkedin", "other_social",
    "photo_path", "bio", "opt_in_contact", "status",
    "last_contacted", "notes", "original_student_id",
)


def _audit_diff(before: Alumnus, after: Alumnus, *,
                  actor: str | None) -> None:
    actor_label = (actor or "system").strip() or "system"
    changes: list[tuple[str, str | None, str | None]] = []
    for f in _AUDITABLE_FIELDS:
        old = getattr(before, f, None)
        new = getattr(after, f, None)
        if isinstance(old, bool):
            old = "1" if old else "0"
        if isinstance(new, bool):
            new = "1" if new else "0"
        if (old or None) != (new or None):
            changes.append((f,
                             None if old in (None, "") else str(old),
                             None if new in (None, "") else str(new)))
    if not changes:
        return
    with _connect() as conn:
        conn.executemany(
            """INSERT INTO alumni_audit_log
                   (alumni_id, field, old_value, new_value, changed_by)
               VALUES (?, ?, ?, ?, ?)""",
            [(after.alumni_id, f, o, n, actor_label)
             for f, o, n in changes])
        conn.commit()


def list_audit_log(alumni_id: int, *,
                    limit: int = 200) -> list[dict[str, Any]]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT audit_id, field, old_value, new_value, "
            "       changed_by, changed_at "
            "FROM alumni_audit_log WHERE alumni_id = ? "
            "ORDER BY changed_at DESC, audit_id DESC LIMIT ?",
            (alumni_id, int(limit))).fetchall()
    return [dict(r) for r in rows]


def set_status(alumni_id: int, status: str) -> Alumnus:
    if status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    return update_alumnus(alumni_id, {"status": status})


def record_contact(alumni_id: int, *,
                   when: str | None = None,
                   channel: str = "Other",
                   staff_id: str | None = None,
                   subject: str | None = None,
                   summary: str | None = None,
                   log: bool = True) -> Alumnus:
    """Bump ``last_contacted`` and (by default) write a row to the
    shared messages log. Pass ``log=False`` to update the field only."""
    day = when or _dt.date.today().isoformat()
    out = update_alumnus(alumni_id, {"last_contacted": day})
    if log:
        add_communication(alumni_id, {
            "date":     day,
            "channel":  channel,
            "staff_id": staff_id,
            "subject":  subject or f"Contact recorded ({channel})",
            "summary":  summary,
            "status":   "Sent",
        })
    return out


def delete_alumnus(alumni_id: int, *,
                    actor: str | None = None) -> bool:
    """Soft delete — flips ``deleted_at`` to now. The row stays in
    the table for the undo window (see ``SOFT_DELETE_UNDO_DAYS``)
    and can be brought back with :func:`restore_alumnus`. Use
    :func:`purge_alumnus` to remove it physically."""
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE alumni SET deleted_at = datetime('now'), "
            "updated_at = datetime('now') "
            "WHERE alumni_id = ? AND deleted_at IS NULL",
            (alumni_id,))
        conn.commit()
        if cur.rowcount:
            with _connect() as c2:
                c2.execute(
                    """INSERT INTO alumni_audit_log
                           (alumni_id, field, old_value, new_value,
                            changed_by)
                       VALUES (?, 'deleted_at', NULL,
                                 datetime('now'), ?)""",
                    (alumni_id,
                     (actor or "system").strip() or "system"))
                c2.commit()
            _log_action("alumnus.soft_delete", actor=actor,
                          alumni_id=alumni_id)
            return True
    return False


def restore_alumnus(alumni_id: int, *,
                     actor: str | None = None) -> Alumnus:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE alumni SET deleted_at = NULL, "
            "updated_at = datetime('now') "
            "WHERE alumni_id = ? AND deleted_at IS NOT NULL",
            (alumni_id,))
        conn.commit()
        if cur.rowcount == 0:
            raise ValidationError(
                f"No soft-deleted alumnus #{alumni_id}")
        conn.execute(
            """INSERT INTO alumni_audit_log
                   (alumni_id, field, old_value, new_value,
                    changed_by)
               VALUES (?, 'deleted_at', 'soft-deleted', NULL, ?)""",
            (alumni_id,
             (actor or "system").strip() or "system"))
        conn.commit()
    a = get_alumnus(alumni_id)
    assert a is not None
    _log_action("alumnus.restore", actor=actor, alumni_id=alumni_id)
    return a


def list_soft_deleted() -> list[Alumnus]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM alumni WHERE deleted_at IS NOT NULL "
            "ORDER BY deleted_at DESC").fetchall()
    return [_row(r) for r in rows]


def purge_alumnus(alumni_id: int) -> bool:
    """Physical delete. Audit / child rows cascade per their FK
    ``ON DELETE CASCADE`` definitions."""
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM alumni WHERE alumni_id = ?", (alumni_id,))
        conn.commit()
        if cur.rowcount:
            _log_action("alumnus.purge", alumni_id=alumni_id,
                          level=logging.WARNING)
            return True
    return False


def purge_expired_soft_deletes(*,
                                 undo_days: int = SOFT_DELETE_UNDO_DAYS
                                 ) -> int:
    """Hard-delete every soft-deleted alumnus whose deletion is older
    than ``undo_days``. Returns the count purged."""
    init_db()
    cutoff = (_dt.datetime.now()
                - _dt.timedelta(days=undo_days)
                ).strftime("%Y-%m-%d %H:%M:%S")
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM alumni WHERE deleted_at IS NOT NULL "
            "AND deleted_at < ?", (cutoff,))
        conn.commit()
        purged = cur.rowcount
    if purged:
        _log_action("alumnus.purge_expired", purged=purged,
                      undo_days=undo_days, level=logging.WARNING)
    return purged


# ── Deduplication ────────────────────────────────────────────────

@dataclass
class DuplicateCandidate:
    score: float
    primary: Alumnus
    other: Alumnus


def find_duplicates(*, threshold: float = 0.85,
                       include_deleted: bool = False
                       ) -> list[DuplicateCandidate]:
    """Pairwise compare alumni and return candidate duplicates.
    Names are compared via :class:`difflib.SequenceMatcher` after
    case-folding; if DOBs are present on both rows they must match
    exactly. The lower-numbered alumni_id is treated as the primary
    so merges default to keeping the older record."""
    from difflib import SequenceMatcher
    rows = list_alumni(include_deleted=include_deleted)
    out: list[DuplicateCandidate] = []
    for i, a in enumerate(rows):
        a_name = f"{a.first_name} {a.last_name}".lower().strip()
        for b in rows[i + 1:]:
            if a.dob and b.dob and a.dob != b.dob:
                continue
            b_name = f"{b.first_name} {b.last_name}".lower().strip()
            score = SequenceMatcher(None, a_name, b_name).ratio()
            if score < threshold:
                continue
            primary, other = (
                (a, b) if a.alumni_id < b.alumni_id else (b, a))
            out.append(DuplicateCandidate(
                score=score, primary=primary, other=other))
    out.sort(key=lambda c: -c.score)
    return out


# ── Merge ────────────────────────────────────────────────────────

# Child tables whose ``alumni_id`` foreign key must be repointed at
# the keeper when merging two alumni.
_CHILD_TABLES_FOR_MERGE: tuple[str, ...] = (
    "alumni_education", "alumni_career",
    "alumni_emails", "alumni_phones",
    "alumni_achievements",
    "alumni_tag_links",
    "alumni_event_rsvps",
    "alumni_work_exp_offers",
    "alumni_references",
    "alumni_volunteer_hours",
    "alumni_donations", "alumni_pledges",
    "alumni_consent",
    "alumni_portal_tokens",
    "alumni_audit_log",
    "alumni_survey_invitations",
)


def merge_alumni(keep_id: int, merge_id: int, *,
                  actor: str | None = None) -> Alumnus:
    """Merge two alumni records. All child rows referencing
    ``merge_id`` are repointed at ``keep_id``; non-null fields from
    the merged record fill in gaps in the keeper; the merged row is
    then physically deleted. The keeper's ``original_student_id``
    is preserved unless it was empty (in which case the merged
    record's id is used).

    Raises ``ValidationError`` if either id is unknown or they are
    equal. The whole operation is wrapped in a single transaction —
    on failure nothing is changed."""
    init_db()
    if keep_id == merge_id:
        raise ValidationError(
            "keep_id and merge_id must be different")
    keep  = get_alumnus(keep_id)
    other = get_alumnus(merge_id)
    if keep is None or other is None:
        raise ValidationError(
            "Both alumni must exist (no soft-delete filter)")

    # Ensure the messages-side migration has run before we open our
    # own connection — adding a column on a *different* connection
    # after we've begun a transaction here would otherwise leave us
    # with a stale schema view.
    _messages_module().init_db()

    # Fields where we let ``other`` fill in if the keeper is blank.
    fill_fields = list(_AUDITABLE_FIELDS) + ["photo_path", "bio"]
    filled: dict[str, Any] = {}
    for f in fill_fields:
        if (getattr(keep, f, None) in (None, "")
                and getattr(other, f, None) not in (None, "")):
            filled[f] = getattr(other, f)

    # Prefer the older / non-null original_student_id.
    if not keep.original_student_id and other.original_student_id:
        filled["original_student_id"] = other.original_student_id

    with _connect() as conn:
        try:
            # Repoint plain child tables.
            for tbl in _CHILD_TABLES_FOR_MERGE:
                conn.execute(
                    f"UPDATE OR IGNORE {tbl} "
                    f"SET alumni_id = ? WHERE alumni_id = ?",
                    (keep_id, merge_id))
                # If the OR-IGNORE skipped rows because of a UNIQUE
                # collision (e.g. tag links, RSVPs), drop the
                # losing rows so the cascade-delete of merge_id
                # doesn't kill them.
                conn.execute(
                    f"DELETE FROM {tbl} WHERE alumni_id = ?",
                    (merge_id,))
            # Mentor side of mentorships uses a different column.
            conn.execute(
                "UPDATE alumni_mentorships "
                "SET mentor_alumni_id = ? "
                "WHERE mentor_alumni_id = ?",
                (keep_id, merge_id))
            # Channel prefs: keep the keeper's row; drop the loser's.
            conn.execute(
                "DELETE FROM alumni_channel_prefs WHERE alumni_id = ?",
                (merge_id,))
            # Speakers: keep keeper's row; drop loser's.
            conn.execute(
                "DELETE FROM alumni_speakers WHERE alumni_id = ?",
                (merge_id,))
            # messages.alumni_id is a soft link; repoint it.
            conn.execute(
                "UPDATE messages SET alumni_id = ? WHERE alumni_id = ?",
                (keep_id, merge_id))
            # Finally remove the merged shell row.
            conn.execute(
                "DELETE FROM alumni WHERE alumni_id = ?",
                (merge_id,))
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    if filled:
        update_alumnus(keep_id, filled, actor=actor)
    with _connect() as conn:
        conn.execute(
            """INSERT INTO alumni_audit_log
                   (alumni_id, field, old_value, new_value,
                    changed_by)
               VALUES (?, 'merge', ?, NULL, ?)""",
            (keep_id, f"merged #{merge_id} into here",
             (actor or "system").strip() or "system"))
        conn.commit()

    final = get_alumnus(keep_id)
    assert final is not None
    _log_action("alumnus.merge", actor=actor,
                  kept=keep_id, merged=merge_id,
                  level=logging.WARNING)
    return final


# ── Archive an existing student ───────────────────────────────────

def archive_student(
    student_id: str,
    *,
    leaving_year: str | None = None,
    leaving_date: str | None = None,
    leaving_reason: str | None = None,
    destination_type: str = DEFAULT_DESTINATION,
    destination_detail: str | None = None,
    notes: str | None = None,
    delete_student: bool = False,
) -> Alumnus:
    """Create an alumnus row from an existing student. By default the
    underlying ``students`` row is kept (so attendance / behaviour
    history stays linked); pass ``delete_student=True`` to remove
    it. Idempotent if an alumnus row already exists for this id —
    that existing row is updated with any newly supplied destination
    fields and returned."""
    init_db()
    from education_system.sixthform_system.modules.domain.students.students import (
        students as _students,
    )
    student = _students.get_student(student_id.strip())
    if student is None:
        raise ValidationError(f"No student with id {student_id}")

    existing = get_alumnus_by_original_id(student.student_id)
    if existing is not None:
        return update_alumnus(existing.alumni_id, {
            "leaving_year":       leaving_year or existing.leaving_year,
            "leaving_date":       leaving_date or existing.leaving_date,
            "leaving_reason":     leaving_reason or existing.leaving_reason,
            "destination_type":   destination_type
                                  if destination_type != DEFAULT_DESTINATION
                                  else existing.destination_type,
            "destination_detail": destination_detail
                                  or existing.destination_detail,
            "notes":              notes or existing.notes,
        })

    today = _dt.date.today()
    fallback_year = str(today.year if today.month >= 9 else today.year - 1)
    a = create_alumnus({
        "original_student_id": student.student_id,
        "first_name":          student.first_name,
        "last_name":           student.last_name,
        "leaving_year":        leaving_year or fallback_year,
        "leaving_date":        leaving_date or today.isoformat(),
        "leaving_reason":      leaving_reason or DEFAULT_LEAVING_REASON,
        "destination_type":    destination_type,
        "destination_detail":  destination_detail,
        "email":               student.email,
        "phone":               student.phone,
        "status":              DEFAULT_STATUS,
        "notes":               notes,
    })
    if delete_student:
        try:
            _students.delete_student(student.student_id)
        except Exception:
            logger.exception(
                "Archived alumnus #%d but could not delete student %s",
                a.alumni_id, student.student_id)
    _log_action("alumnus.archive_student", alumni_id=a.alumni_id,
                  student_id=student.student_id,
                  destination=destination_type,
                  delete_student=delete_student)
    return a


# ── Summary ───────────────────────────────────────────────────────

def summary() -> Summary:
    init_db()
    rows = list_alumni()
    by_status = {s: 0 for s in STATUSES}
    by_dest   = {d: 0 for d in DESTINATION_TYPES}
    by_year:    dict[str, int] = {}
    contactable = 0
    no_contact = 0
    most_recent_year: str | None = None
    for a in rows:
        by_status[a.status] = by_status.get(a.status, 0) + 1
        by_dest[a.destination_type] = by_dest.get(
            a.destination_type, 0) + 1
        if a.leaving_year:
            by_year[a.leaving_year] = by_year.get(
                a.leaving_year, 0) + 1
            if most_recent_year is None or a.leaving_year > most_recent_year:
                most_recent_year = a.leaving_year
        if (a.status == "Active" and a.opt_in_contact
                and (a.email or a.phone)):
            contactable += 1
        if a.status == "Active" and not (a.email or a.phone):
            no_contact += 1
    return Summary(
        total=len(rows),
        by_status=by_status,
        by_destination=by_dest,
        by_leaving_year=dict(sorted(by_year.items(),
                                      key=lambda kv: kv[0],
                                      reverse=True)),
        contactable=contactable,
        no_contact_method=no_contact,
        most_recent_year=most_recent_year,
    )


# ── Education history ─────────────────────────────────────────────

def _require_alumnus(conn: sqlite3.Connection, alumni_id: int) -> None:
    r = conn.execute(
        "SELECT 1 FROM alumni WHERE alumni_id = ?", (alumni_id,)
    ).fetchone()
    if r is None:
        raise ValidationError(f"No alumnus #{alumni_id}")


def _row_education(r: sqlite3.Row) -> Education:
    return Education(
        education_id=r["education_id"], alumni_id=r["alumni_id"],
        qualification=r["qualification"], subject=r["subject"],
        institution=r["institution"],
        start_date=r["start_date"], end_date=r["end_date"],
        grade=r["grade"], status=r["status"], notes=r["notes"],
        created_at=r["created_at"],
    )


def add_education(alumni_id: int, payload: dict[str, Any]) -> Education:
    init_db()
    qual   = _require(payload.get("qualification"), "Qualification").strip()
    inst   = _require(payload.get("institution"),   "Institution").strip()
    status = (payload.get("status") or DEFAULT_EDUCATION_STATUS).strip()
    if status not in EDUCATION_STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(EDUCATION_STATUSES)}")
    start = _validate_date(payload.get("start_date"), "Start date")
    end   = _validate_date(payload.get("end_date"),   "End date")
    subject = (payload.get("subject") or "").strip() or None
    grade   = (payload.get("grade")   or "").strip() or None
    notes   = (payload.get("notes")   or "").strip() or None
    with _connect() as conn:
        _require_alumnus(conn, alumni_id)
        cur = conn.execute(
            """INSERT INTO alumni_education
                   (alumni_id, qualification, subject, institution,
                    start_date, end_date, grade, status, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (alumni_id, qual, subject, inst, start, end,
             grade, status, notes),
        )
        conn.commit()
        new_id = cur.lastrowid
        r = conn.execute(
            "SELECT * FROM alumni_education WHERE education_id = ?",
            (new_id,)).fetchone()
    return _row_education(r)


def list_education(alumni_id: int) -> list[Education]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM alumni_education WHERE alumni_id = ? "
            "ORDER BY COALESCE(end_date, start_date, '') DESC, "
            "education_id DESC",
            (alumni_id,)).fetchall()
    return [_row_education(r) for r in rows]


def update_education(education_id: int,
                      payload: dict[str, Any]) -> Education:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM alumni_education WHERE education_id = ?",
            (education_id,)).fetchone()
        if r is None:
            raise ValidationError(f"No education row #{education_id}")
    merged = {
        "qualification": payload.get("qualification", r["qualification"]),
        "subject":       payload.get("subject",       r["subject"]),
        "institution":   payload.get("institution",   r["institution"]),
        "start_date":    payload.get("start_date",    r["start_date"]),
        "end_date":      payload.get("end_date",      r["end_date"]),
        "grade":         payload.get("grade",         r["grade"]),
        "status":        payload.get("status",        r["status"]),
        "notes":         payload.get("notes",         r["notes"]),
    }
    qual   = _require(merged["qualification"], "Qualification").strip()
    inst   = _require(merged["institution"],   "Institution").strip()
    status = (merged["status"] or DEFAULT_EDUCATION_STATUS).strip()
    if status not in EDUCATION_STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(EDUCATION_STATUSES)}")
    start = _validate_date(merged["start_date"], "Start date")
    end   = _validate_date(merged["end_date"],   "End date")
    with _connect() as conn:
        conn.execute(
            """UPDATE alumni_education SET
                   qualification = ?, subject = ?, institution = ?,
                   start_date = ?, end_date = ?, grade = ?,
                   status = ?, notes = ?
               WHERE education_id = ?""",
            (qual, (merged["subject"] or "").strip() or None,
             inst, start, end,
             (merged["grade"] or "").strip() or None, status,
             (merged["notes"] or "").strip() or None, education_id),
        )
        conn.commit()
        r2 = conn.execute(
            "SELECT * FROM alumni_education WHERE education_id = ?",
            (education_id,)).fetchone()
    return _row_education(r2)


def delete_education(education_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM alumni_education WHERE education_id = ?",
            (education_id,))
        conn.commit()
        return cur.rowcount > 0


# ── Career history ────────────────────────────────────────────────

def _row_career(r: sqlite3.Row) -> Career:
    return Career(
        career_id=r["career_id"], alumni_id=r["alumni_id"],
        role=r["role"], employer=r["employer"], sector=r["sector"],
        country=r["country"], location=r["location"],
        start_date=r["start_date"], end_date=r["end_date"],
        is_current=bool(r["is_current"]),
        salary_band=r["salary_band"], notes=r["notes"],
        created_at=r["created_at"],
    )


def _validate_career_payload(payload: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["role"]     = _require(payload.get("role"),     "Role").strip()
    out["employer"] = _require(payload.get("employer"), "Employer").strip()
    sector = (payload.get("sector") or "").strip()
    if sector and sector not in SECTORS:
        raise ValidationError(
            f"Sector must be one of: {', '.join(SECTORS)}")
    out["sector"]      = sector or None
    out["country"]     = (payload.get("country")  or "").strip() or None
    out["location"]    = (payload.get("location") or "").strip() or None
    out["start_date"]  = _validate_date(payload.get("start_date"),
                                          "Start date")
    out["end_date"]    = _validate_date(payload.get("end_date"),
                                          "End date")
    out["is_current"]  = bool(payload.get("is_current"))
    band = (payload.get("salary_band") or "").strip()
    if band and band not in SALARY_BANDS:
        raise ValidationError(
            f"Salary band must be one of: {', '.join(SALARY_BANDS)}")
    out["salary_band"] = band or None
    out["notes"]       = (payload.get("notes") or "").strip() or None
    return out


def add_career(alumni_id: int, payload: dict[str, Any]) -> Career:
    init_db()
    p = _validate_career_payload(payload)
    with _connect() as conn:
        _require_alumnus(conn, alumni_id)
        if p["is_current"]:
            conn.execute(
                "UPDATE alumni_career SET is_current = 0 "
                "WHERE alumni_id = ?", (alumni_id,))
        cur = conn.execute(
            """INSERT INTO alumni_career
                   (alumni_id, role, employer, sector, country, location,
                    start_date, end_date, is_current, salary_band, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (alumni_id, p["role"], p["employer"], p["sector"],
             p["country"], p["location"], p["start_date"], p["end_date"],
             1 if p["is_current"] else 0, p["salary_band"], p["notes"]),
        )
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_career WHERE career_id = ?",
            (cur.lastrowid,)).fetchone()
    return _row_career(r)


def list_career(alumni_id: int) -> list[Career]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM alumni_career WHERE alumni_id = ? "
            "ORDER BY is_current DESC, "
            "COALESCE(end_date, start_date, '') DESC, career_id DESC",
            (alumni_id,)).fetchall()
    return [_row_career(r) for r in rows]


def update_career(career_id: int, payload: dict[str, Any]) -> Career:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM alumni_career WHERE career_id = ?",
            (career_id,)).fetchone()
        if r is None:
            raise ValidationError(f"No career row #{career_id}")
    merged = {
        "role":        payload.get("role",        r["role"]),
        "employer":    payload.get("employer",    r["employer"]),
        "sector":      payload.get("sector",      r["sector"]),
        "country":     payload.get("country",     r["country"]),
        "location":    payload.get("location",    r["location"]),
        "start_date":  payload.get("start_date",  r["start_date"]),
        "end_date":    payload.get("end_date",    r["end_date"]),
        "is_current":  payload.get("is_current",  bool(r["is_current"])),
        "salary_band": payload.get("salary_band", r["salary_band"]),
        "notes":       payload.get("notes",       r["notes"]),
    }
    p = _validate_career_payload(merged)
    with _connect() as conn:
        if p["is_current"]:
            conn.execute(
                "UPDATE alumni_career SET is_current = 0 "
                "WHERE alumni_id = ? AND career_id != ?",
                (r["alumni_id"], career_id))
        conn.execute(
            """UPDATE alumni_career SET
                   role = ?, employer = ?, sector = ?, country = ?,
                   location = ?, start_date = ?, end_date = ?,
                   is_current = ?, salary_band = ?, notes = ?
               WHERE career_id = ?""",
            (p["role"], p["employer"], p["sector"], p["country"],
             p["location"], p["start_date"], p["end_date"],
             1 if p["is_current"] else 0, p["salary_band"],
             p["notes"], career_id),
        )
        conn.commit()
        r2 = conn.execute(
            "SELECT * FROM alumni_career WHERE career_id = ?",
            (career_id,)).fetchone()
    return _row_career(r2)


def delete_career(career_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM alumni_career WHERE career_id = ?",
            (career_id,))
        conn.commit()
        return cur.rowcount > 0


# ── Emails / phones ───────────────────────────────────────────────

def _row_email(r: sqlite3.Row) -> AlumniEmail:
    return AlumniEmail(
        email_id=r["email_id"], alumni_id=r["alumni_id"],
        email=r["email"], label=r["label"],
        is_primary=bool(r["is_primary"]),
    )


def _row_phone(r: sqlite3.Row) -> AlumniPhone:
    return AlumniPhone(
        phone_id=r["phone_id"], alumni_id=r["alumni_id"],
        phone=r["phone"], label=r["label"],
        is_primary=bool(r["is_primary"]),
    )


def add_email(alumni_id: int, email: str, *,
              label: str = "Personal",
              is_primary: bool = False) -> AlumniEmail:
    init_db()
    addr = _validate_email(email)
    if not addr:
        raise ValidationError("Email is required")
    if label not in EMAIL_LABELS:
        raise ValidationError(
            f"Label must be one of: {', '.join(EMAIL_LABELS)}")
    with _connect() as conn:
        _require_alumnus(conn, alumni_id)
        if is_primary:
            conn.execute(
                "UPDATE alumni_emails SET is_primary = 0 "
                "WHERE alumni_id = ?", (alumni_id,))
        cur = conn.execute(
            "INSERT INTO alumni_emails "
            "(alumni_id, email, label, is_primary) VALUES (?, ?, ?, ?)",
            (alumni_id, addr, label, 1 if is_primary else 0))
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_emails WHERE email_id = ?",
            (cur.lastrowid,)).fetchone()
    return _row_email(r)


def list_emails(alumni_id: int) -> list[AlumniEmail]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM alumni_emails WHERE alumni_id = ? "
            "ORDER BY is_primary DESC, email_id ASC",
            (alumni_id,)).fetchall()
    return [_row_email(r) for r in rows]


def set_primary_email(email_id: int) -> AlumniEmail:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM alumni_emails WHERE email_id = ?",
            (email_id,)).fetchone()
        if r is None:
            raise ValidationError(f"No email row #{email_id}")
        conn.execute(
            "UPDATE alumni_emails SET is_primary = 0 "
            "WHERE alumni_id = ?", (r["alumni_id"],))
        conn.execute(
            "UPDATE alumni_emails SET is_primary = 1 WHERE email_id = ?",
            (email_id,))
        conn.commit()
        r2 = conn.execute(
            "SELECT * FROM alumni_emails WHERE email_id = ?",
            (email_id,)).fetchone()
    return _row_email(r2)


def delete_email(email_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM alumni_emails WHERE email_id = ?", (email_id,))
        conn.commit()
        return cur.rowcount > 0


def add_phone(alumni_id: int, phone: str, *,
              label: str = "Mobile",
              is_primary: bool = False) -> AlumniPhone:
    init_db()
    num = _validate_phone(phone)
    if not num:
        raise ValidationError("Phone is required")
    if label not in PHONE_LABELS:
        raise ValidationError(
            f"Label must be one of: {', '.join(PHONE_LABELS)}")
    with _connect() as conn:
        _require_alumnus(conn, alumni_id)
        if is_primary:
            conn.execute(
                "UPDATE alumni_phones SET is_primary = 0 "
                "WHERE alumni_id = ?", (alumni_id,))
        cur = conn.execute(
            "INSERT INTO alumni_phones "
            "(alumni_id, phone, label, is_primary) VALUES (?, ?, ?, ?)",
            (alumni_id, num, label, 1 if is_primary else 0))
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_phones WHERE phone_id = ?",
            (cur.lastrowid,)).fetchone()
    return _row_phone(r)


def list_phones(alumni_id: int) -> list[AlumniPhone]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM alumni_phones WHERE alumni_id = ? "
            "ORDER BY is_primary DESC, phone_id ASC",
            (alumni_id,)).fetchall()
    return [_row_phone(r) for r in rows]


def set_primary_phone(phone_id: int) -> AlumniPhone:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM alumni_phones WHERE phone_id = ?",
            (phone_id,)).fetchone()
        if r is None:
            raise ValidationError(f"No phone row #{phone_id}")
        conn.execute(
            "UPDATE alumni_phones SET is_primary = 0 "
            "WHERE alumni_id = ?", (r["alumni_id"],))
        conn.execute(
            "UPDATE alumni_phones SET is_primary = 1 WHERE phone_id = ?",
            (phone_id,))
        conn.commit()
        r2 = conn.execute(
            "SELECT * FROM alumni_phones WHERE phone_id = ?",
            (phone_id,)).fetchone()
    return _row_phone(r2)


def delete_phone(phone_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM alumni_phones WHERE phone_id = ?", (phone_id,))
        conn.commit()
        return cur.rowcount > 0


# ── Tags ──────────────────────────────────────────────────────────

def _row_tag(r: sqlite3.Row) -> Tag:
    return Tag(tag_id=r["tag_id"], name=r["name"])


def list_all_tags() -> list[Tag]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM alumni_tags ORDER BY name COLLATE NOCASE"
        ).fetchall()
    return [_row_tag(r) for r in rows]


def get_or_create_tag(name: str) -> Tag:
    init_db()
    nm = _require(name, "Tag name").strip()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM alumni_tags WHERE name = ? COLLATE NOCASE",
            (nm,)).fetchone()
        if r:
            return _row_tag(r)
        cur = conn.execute(
            "INSERT INTO alumni_tags (name) VALUES (?)", (nm,))
        conn.commit()
        return Tag(tag_id=cur.lastrowid, name=nm)


def list_tags_for(alumni_id: int) -> list[Tag]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT t.* FROM alumni_tags t "
            "JOIN alumni_tag_links l ON l.tag_id = t.tag_id "
            "WHERE l.alumni_id = ? "
            "ORDER BY t.name COLLATE NOCASE",
            (alumni_id,)).fetchall()
    return [_row_tag(r) for r in rows]


def list_alumni_for_tag(tag_id: int) -> list[Alumnus]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT a.* FROM alumni a "
            "JOIN alumni_tag_links l ON l.alumni_id = a.alumni_id "
            "WHERE l.tag_id = ? "
            "ORDER BY a.last_name ASC, a.first_name ASC",
            (tag_id,)).fetchall()
    return [_row(r) for r in rows]


def add_tag(alumni_id: int, name: str) -> Tag:
    init_db()
    tag = get_or_create_tag(name)
    with _connect() as conn:
        _require_alumnus(conn, alumni_id)
        conn.execute(
            "INSERT OR IGNORE INTO alumni_tag_links "
            "(alumni_id, tag_id) VALUES (?, ?)",
            (alumni_id, tag.tag_id))
        conn.commit()
    return tag


def remove_tag(alumni_id: int, tag_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM alumni_tag_links "
            "WHERE alumni_id = ? AND tag_id = ?",
            (alumni_id, tag_id))
        conn.commit()
        return cur.rowcount > 0


def delete_tag(tag_id: int) -> bool:
    """Delete a tag globally (and all its links)."""
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM alumni_tags WHERE tag_id = ?", (tag_id,))
        conn.commit()
        return cur.rowcount > 0


# ── Achievements ──────────────────────────────────────────────────

def _row_achievement(r: sqlite3.Row) -> Achievement:
    return Achievement(
        achievement_id=r["achievement_id"], alumni_id=r["alumni_id"],
        date=r["date"], title=r["title"], category=r["category"],
        description=r["description"], url=r["url"],
        created_at=r["created_at"],
    )


def add_achievement(alumni_id: int,
                     payload: dict[str, Any]) -> Achievement:
    init_db()
    title    = _require(payload.get("title"), "Title").strip()
    date     = _validate_date(payload.get("date"), "Date")
    category = (payload.get("category") or "").strip()
    if category and category not in ACHIEVEMENT_CATEGORIES:
        raise ValidationError(
            f"Category must be one of: "
            f"{', '.join(ACHIEVEMENT_CATEGORIES)}")
    desc = (payload.get("description") or "").strip() or None
    url  = (payload.get("url") or "").strip() or None
    with _connect() as conn:
        _require_alumnus(conn, alumni_id)
        cur = conn.execute(
            """INSERT INTO alumni_achievements
                   (alumni_id, date, title, category, description, url)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (alumni_id, date, title, category or None, desc, url))
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_achievements "
            "WHERE achievement_id = ?", (cur.lastrowid,)).fetchone()
    return _row_achievement(r)


def list_achievements(alumni_id: int) -> list[Achievement]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM alumni_achievements WHERE alumni_id = ? "
            "ORDER BY COALESCE(date, '') DESC, achievement_id DESC",
            (alumni_id,)).fetchall()
    return [_row_achievement(r) for r in rows]


def update_achievement(achievement_id: int,
                        payload: dict[str, Any]) -> Achievement:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM alumni_achievements "
            "WHERE achievement_id = ?", (achievement_id,)).fetchone()
        if r is None:
            raise ValidationError(
                f"No achievement #{achievement_id}")
    merged = {
        "date":        payload.get("date",        r["date"]),
        "title":       payload.get("title",       r["title"]),
        "category":    payload.get("category",    r["category"]),
        "description": payload.get("description", r["description"]),
        "url":         payload.get("url",         r["url"]),
    }
    title    = _require(merged["title"], "Title").strip()
    date     = _validate_date(merged["date"], "Date")
    category = (merged["category"] or "").strip()
    if category and category not in ACHIEVEMENT_CATEGORIES:
        raise ValidationError(
            f"Category must be one of: "
            f"{', '.join(ACHIEVEMENT_CATEGORIES)}")
    with _connect() as conn:
        conn.execute(
            """UPDATE alumni_achievements SET
                   date = ?, title = ?, category = ?,
                   description = ?, url = ?
               WHERE achievement_id = ?""",
            (date, title, category or None,
             (merged["description"] or "").strip() or None,
             (merged["url"] or "").strip() or None,
             achievement_id))
        conn.commit()
        r2 = conn.execute(
            "SELECT * FROM alumni_achievements "
            "WHERE achievement_id = ?", (achievement_id,)).fetchone()
    return _row_achievement(r2)


def delete_achievement(achievement_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM alumni_achievements WHERE achievement_id = ?",
            (achievement_id,))
        conn.commit()
        return cur.rowcount > 0


# ── Communications log (delegates to the messages module) ────────

def _messages_module():
    """Lazy import of the shared sixth-form messaging module."""
    from education_system.sixthform_system.modules.domain.staff_comms.messages \
        import messages as _msg
    return _msg


# Re-export the messages module's channels/statuses so callers (CLI,
# views) have one source of truth.
def _comm_channels() -> tuple[str, ...]:
    return _messages_module().CHANNELS


def _comm_statuses() -> tuple[str, ...]:
    return _messages_module().STATUSES


# Backward-compat exports — these were previously defined here.
COMM_CHANNELS = _messages_module().CHANNELS
COMM_STATUSES = _messages_module().STATUSES


def add_communication(alumni_id: int,
                       payload: dict[str, Any]):
    """Record a communication against an alumnus by writing into the
    shared messages log. ``payload`` accepts our previous shape
    (``date`` / ``channel`` / ``staff_id`` / ``subject`` / ``summary``
    / ``status``); legacy channels we used to expose ("Phone",
    "Post", "In Person", "Event") are mapped to the messages
    module's vocabulary."""
    msg = _messages_module()
    init_db()
    raw_channel = (payload.get("channel") or "Email").strip()
    channel_map = {
        "Phone":      "Phone Call",
        "Post":       "Letter",
        "In Person":  "In-Person Meeting",
        "Event":      "In-Person Meeting",
    }
    channel = channel_map.get(raw_channel, raw_channel)
    if channel not in msg.CHANNELS:
        channel = "Other"
    raw_status = (payload.get("status") or "Sent").strip()
    status_map = {
        "Bounced":  "Failed",
        "No Reply": "Sent",
        "Note":     "Received",
    }
    status = status_map.get(raw_status, raw_status)
    if status not in msg.STATUSES:
        status = "Sent"

    alumnus = get_alumnus(alumni_id)
    if alumnus is None:
        raise ValidationError(f"No alumnus #{alumni_id}")

    day = _validate_date(payload.get("date")
                            or _dt.date.today().isoformat(),
                          "Date", required=True)
    # messages.sent_at accepts "YYYY-MM-DD" or "YYYY-MM-DD HH:MM[:SS]"
    sent_at = day if status in msg.SENT_STATUSES else None
    return msg.create_message({
        "direction":  ("Incoming" if status == "Received"
                         else "Outgoing"),
        "channel":    channel,
        "status":     status,
        "subject":    (payload.get("subject")
                        or f"Contact ({raw_channel})"),
        "body":       payload.get("summary") or "",
        "alumni_id":  alumni_id,
        "to_name":    alumnus.full_name,
        "to_address": (alumnus.email
                         if channel in ("Email", "Portal") else None),
        "staff_id":   (payload.get("staff_id") or "").strip().upper()
                         or None,
        "sent_at":    sent_at,
        "tags":       payload.get("tags"),
        "notes":      payload.get("notes"),
    })


def list_communications(alumni_id: int) -> list:
    """Return the messages-module rows logged against this alumnus,
    newest first."""
    return _messages_module().list_messages(alumni_id=alumni_id)


def delete_communication(comm_id: int) -> bool:
    return _messages_module().delete_message(comm_id)


# ── Bounces ──────────────────────────────────────────────────────

def record_bounce(alumni_id: int, *, hard: bool = True,
                   reason: str | None = None) -> Alumnus:
    """Record a delivery bounce. Hard bounces increment ``bounce_count``
    and auto-flip ``status`` to 'Lost Contact' at the threshold.
    The bounce is also written to the messages log as a Failed
    Outgoing message tagged ``bounce-hard`` / ``bounce-soft``."""
    init_db()
    a0 = get_alumnus(alumni_id)
    if a0 is None:
        raise ValidationError(f"No alumnus #{alumni_id}")
    if hard:
        with _connect() as conn:
            conn.execute(
                "UPDATE alumni SET bounce_count = bounce_count + 1, "
                "updated_at = datetime('now') WHERE alumni_id = ?",
                (alumni_id,))
            conn.commit()
    try:
        _messages_module().create_message({
            "direction":  "Outgoing",
            "channel":    "Email",
            "status":     "Failed",
            "subject":    "Hard bounce" if hard else "Soft bounce",
            "body":       reason or ("Hard bounce recorded"
                                       if hard
                                       else "Soft bounce recorded"),
            "alumni_id":  alumni_id,
            "to_name":    a0.full_name,
            "to_address": a0.email,
            "tags":       "bounce-hard" if hard else "bounce-soft",
        })
    except Exception:
        logger.exception(
            "Could not log bounce to messages for alumnus #%d",
            alumni_id)
    a = get_alumnus(alumni_id)
    assert a is not None
    _log_action("alumnus.bounce", alumni_id=alumni_id,
                  hard=hard, bounce_count=a.bounce_count)
    if hard and a.bounce_count >= HARD_BOUNCE_THRESHOLD \
            and a.status == "Active":
        a = set_status(alumni_id, "Lost Contact")
        _log_action("alumnus.auto_status_change",
                      alumni_id=alumni_id, status="Lost Contact",
                      reason="hard_bounce_threshold",
                      bounces=a.bounce_count,
                      level=logging.WARNING)
    return a


def clear_bounces(alumni_id: int) -> Alumnus:
    init_db()
    with _connect() as conn:
        _require_alumnus(conn, alumni_id)
        conn.execute(
            "UPDATE alumni SET bounce_count = 0, "
            "updated_at = datetime('now') WHERE alumni_id = ?",
            (alumni_id,))
        conn.commit()
    a = get_alumnus(alumni_id)
    assert a is not None
    return a


# ── Channel preferences ───────────────────────────────────────────

def _row_prefs(r: sqlite3.Row) -> ChannelPrefs:
    return ChannelPrefs(
        alumni_id=r["alumni_id"],
        opt_in_email=bool(r["opt_in_email"]),
        opt_in_post=bool(r["opt_in_post"]),
        opt_in_phone=bool(r["opt_in_phone"]),
        opt_in_sms=bool(r["opt_in_sms"]),
        updated_at=r["updated_at"],
    )


def get_channel_prefs(alumni_id: int) -> ChannelPrefs:
    """Return prefs, creating defaults seeded from ``opt_in_contact``
    if no row exists yet."""
    init_db()
    with _connect() as conn:
        _require_alumnus(conn, alumni_id)
        r = conn.execute(
            "SELECT * FROM alumni_channel_prefs WHERE alumni_id = ?",
            (alumni_id,)).fetchone()
        if r is None:
            seed = conn.execute(
                "SELECT opt_in_contact FROM alumni WHERE alumni_id = ?",
                (alumni_id,)).fetchone()
            default = 1 if seed and seed["opt_in_contact"] else 0
            conn.execute(
                """INSERT INTO alumni_channel_prefs
                       (alumni_id, opt_in_email, opt_in_post,
                        opt_in_phone, opt_in_sms)
                   VALUES (?, ?, ?, ?, ?)""",
                (alumni_id, default, default, default, default))
            conn.commit()
            r = conn.execute(
                "SELECT * FROM alumni_channel_prefs WHERE alumni_id = ?",
                (alumni_id,)).fetchone()
    return _row_prefs(r)


def update_channel_prefs(alumni_id: int, *,
                          opt_in_email: bool | None = None,
                          opt_in_post:  bool | None = None,
                          opt_in_phone: bool | None = None,
                          opt_in_sms:   bool | None = None
                          ) -> ChannelPrefs:
    cur = get_channel_prefs(alumni_id)
    new = ChannelPrefs(
        alumni_id=alumni_id,
        opt_in_email=cur.opt_in_email if opt_in_email is None
                       else bool(opt_in_email),
        opt_in_post=cur.opt_in_post   if opt_in_post  is None
                       else bool(opt_in_post),
        opt_in_phone=cur.opt_in_phone if opt_in_phone is None
                       else bool(opt_in_phone),
        opt_in_sms=cur.opt_in_sms     if opt_in_sms   is None
                       else bool(opt_in_sms),
        updated_at="",
    )
    with _connect() as conn:
        conn.execute(
            """UPDATE alumni_channel_prefs
                   SET opt_in_email = ?, opt_in_post = ?,
                       opt_in_phone = ?, opt_in_sms = ?,
                       updated_at = datetime('now')
                   WHERE alumni_id = ?""",
            (1 if new.opt_in_email else 0,
             1 if new.opt_in_post  else 0,
             1 if new.opt_in_phone else 0,
             1 if new.opt_in_sms   else 0,
             alumni_id))
        # Keep the legacy alumni.opt_in_contact in sync: 1 if any channel
        # is enabled, else 0.
        any_on = (new.opt_in_email or new.opt_in_post
                   or new.opt_in_phone or new.opt_in_sms)
        conn.execute(
            "UPDATE alumni SET opt_in_contact = ?, "
            "updated_at = datetime('now') WHERE alumni_id = ?",
            (1 if any_on else 0, alumni_id))
        conn.commit()
    return get_channel_prefs(alumni_id)


# ── GDPR consent ──────────────────────────────────────────────────

def _row_consent(r: sqlite3.Row) -> Consent:
    return Consent(
        consent_id=r["consent_id"], alumni_id=r["alumni_id"],
        scope=r["scope"], version=r["version"],
        granted_at=r["granted_at"], withdrawn_at=r["withdrawn_at"],
        source=r["source"], notes=r["notes"],
    )


def grant_consent(alumni_id: int, scope: str, *,
                   version: str = CONSENT_VERSION,
                   source: str | None = None,
                   notes: str | None = None,
                   when: str | None = None) -> Consent:
    init_db()
    if scope not in CONSENT_SCOPES:
        raise ValidationError(
            f"Scope must be one of: {', '.join(CONSENT_SCOPES)}")
    granted_at = when or _dt.datetime.now().isoformat(
        timespec="seconds")
    with _connect() as conn:
        _require_alumnus(conn, alumni_id)
        cur = conn.execute(
            """INSERT INTO alumni_consent
                   (alumni_id, scope, version, granted_at,
                    source, notes)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (alumni_id, scope, version, granted_at,
             (source or "").strip() or None,
             (notes or "").strip() or None))
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_consent WHERE consent_id = ?",
            (cur.lastrowid,)).fetchone()
    _log_action("consent.grant", alumni_id=alumni_id,
                  scope=scope, version=version, source=source)
    return _row_consent(r)


def withdraw_consent(consent_id: int, *,
                      when: str | None = None,
                      notes: str | None = None) -> Consent:
    init_db()
    when_iso = when or _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM alumni_consent WHERE consent_id = ?",
            (consent_id,)).fetchone()
        if r is None:
            raise ValidationError(f"No consent #{consent_id}")
        if r["withdrawn_at"]:
            return _row_consent(r)
        merged_notes = ((r["notes"] or "") + ("\n" if r["notes"] else "")
                          + f"withdrawn: {notes}") if notes else r["notes"]
        conn.execute(
            "UPDATE alumni_consent SET withdrawn_at = ?, notes = ? "
            "WHERE consent_id = ?",
            (when_iso, merged_notes, consent_id))
        conn.commit()
        r2 = conn.execute(
            "SELECT * FROM alumni_consent WHERE consent_id = ?",
            (consent_id,)).fetchone()
    out = _row_consent(r2)
    _log_action("consent.withdraw", alumni_id=out.alumni_id,
                  consent_id=consent_id, scope=out.scope)
    return out


def list_consents(alumni_id: int, *,
                   active_only: bool = False) -> list[Consent]:
    init_db()
    sql = ("SELECT * FROM alumni_consent WHERE alumni_id = ? "
            + ("AND withdrawn_at IS NULL " if active_only else "")
            + "ORDER BY granted_at DESC, consent_id DESC")
    with _connect() as conn:
        rows = conn.execute(sql, (alumni_id,)).fetchall()
    return [_row_consent(r) for r in rows]


def has_active_consent(alumni_id: int, scope: str) -> bool:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT 1 FROM alumni_consent "
            "WHERE alumni_id = ? AND scope = ? "
            "AND withdrawn_at IS NULL "
            "ORDER BY granted_at DESC LIMIT 1",
            (alumni_id, scope)).fetchone()
    return r is not None


# ── Retention / anonymise ─────────────────────────────────────────

def find_retention_candidates(*, years: int = 7
                                ) -> list[Alumnus]:
    """Alumni with status Opt-out or Deceased whose last update is
    older than ``years`` years."""
    init_db()
    cutoff = (_dt.date.today() - _dt.timedelta(days=365 * years)
                ).isoformat()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM alumni "
            "WHERE status IN ('Opt-out', 'Deceased') "
            "AND substr(updated_at, 1, 10) < ? "
            "ORDER BY updated_at ASC", (cutoff,)).fetchall()
    return [_row(r) for r in rows]


def anonymise_alumnus(alumni_id: int) -> Alumnus:
    """Replace identifying fields with placeholders and clear all
    child PII (emails, phones, address, bio, photo). Preserves
    aggregate fields useful for outcome stats (leaving year,
    destination type, sector)."""
    init_db()
    with _connect() as conn:
        _require_alumnus(conn, alumni_id)
        conn.execute(
            """UPDATE alumni SET
                   first_name = 'Anonymised',
                   last_name  = '#' || ?,
                   preferred_name = NULL, pronouns = NULL,
                   gender = NULL, dob = NULL,
                   original_student_id = NULL,
                   email = NULL, phone = NULL, address = NULL,
                   linkedin = NULL, other_social = NULL,
                   photo_path = NULL, bio = NULL,
                   notes = NULL, last_contacted = NULL,
                   current_role = NULL, current_employer = NULL,
                   current_location = NULL, region = NULL,
                   updated_at = datetime('now')
               WHERE alumni_id = ?""",
            (alumni_id, alumni_id))
        for tbl in ("alumni_emails", "alumni_phones",
                     "alumni_portal_tokens",
                     "alumni_achievements", "alumni_career",
                     "alumni_education"):
            try:
                conn.execute(
                    f"DELETE FROM {tbl} WHERE alumni_id = ?",
                    (alumni_id,))
            except sqlite3.OperationalError:
                continue
        conn.commit()
    a = get_alumnus(alumni_id)
    assert a is not None
    _log_action("alumnus.anonymise", alumni_id=alumni_id,
                  level=logging.WARNING)
    return a


# ── Self-service portal tokens ────────────────────────────────────

def _row_token(r: sqlite3.Row) -> PortalToken:
    return PortalToken(
        token=r["token"], alumni_id=r["alumni_id"],
        expires_at=r["expires_at"], used_at=r["used_at"],
        created_at=r["created_at"],
    )


def create_portal_token(alumni_id: int, *,
                         ttl_days: int = PORTAL_TOKEN_TTL_DAYS
                         ) -> PortalToken:
    init_db()
    tok = secrets.token_urlsafe(24)
    expires = (_dt.datetime.now()
                + _dt.timedelta(days=ttl_days)
                ).isoformat(timespec="seconds")
    with _connect() as conn:
        _require_alumnus(conn, alumni_id)
        conn.execute(
            """INSERT INTO alumni_portal_tokens
                   (token, alumni_id, expires_at) VALUES (?, ?, ?)""",
            (tok, alumni_id, expires))
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_portal_tokens WHERE token = ?",
            (tok,)).fetchone()
    _log_action("portal.token_issued", alumni_id=alumni_id,
                  ttl_days=ttl_days, expires_at=expires)
    return _row_token(r)


def validate_portal_token(token: str) -> PortalToken | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM alumni_portal_tokens WHERE token = ?",
            (token,)).fetchone()
        if r is None:
            return None
        tok = _row_token(r)
    now_iso = _dt.datetime.now().isoformat(timespec="seconds")
    if tok.used_at:
        return None
    if tok.expires_at < now_iso:
        return None
    return tok


_SELF_SERVICE_FIELDS: frozenset[str] = frozenset({
    "preferred_name", "pronouns", "current_role", "current_employer",
    "current_sector", "current_location", "country", "region",
    "email", "phone", "linkedin", "other_social", "bio",
})


def apply_self_service_update(token: str,
                                payload: dict[str, Any]) -> Alumnus:
    """Apply an alumnus's own edits via a single-use portal token.
    Only a whitelisted set of fields can be updated. The token is
    marked used on success."""
    tok = validate_portal_token(token)
    if tok is None:
        raise ValidationError("Invalid or expired portal token")
    safe = {k: v for k, v in payload.items()
              if k in _SELF_SERVICE_FIELDS}
    if not safe:
        raise ValidationError("No editable fields in payload")
    out = update_alumnus(tok.alumni_id, safe, actor="self-service")
    with _connect() as conn:
        conn.execute(
            "UPDATE alumni_portal_tokens SET used_at = ? "
            "WHERE token = ?",
            (_dt.datetime.now().isoformat(timespec="seconds"), token))
        conn.commit()
    _log_action("portal.self_service_apply", actor="self-service",
                  alumni_id=tok.alumni_id, fields=len(safe))
    return out


# ── Email sending (via the messages module) ───────────────────────

def _render(template: str, context: dict[str, Any]) -> str:
    """Tiny placeholder renderer: {first_name}, {last_name} etc."""
    out = template
    for k, v in context.items():
        out = out.replace("{" + k + "}", str(v) if v is not None else "")
    return out


def _alumnus_context(a: Alumnus) -> dict[str, Any]:
    return {
        "first_name":     a.first_name,
        "last_name":      a.last_name,
        "preferred_name": a.preferred_name or a.first_name,
        "leaving_year":   a.leaving_year or "",
    }


def send_email_to_alumnus(alumni_id: int, subject: str, body: str,
                            *, staff_id: str | None = None,
                            respect_optin: bool = True,
                            category: str = "General"):
    """Compose-and-send an outgoing email logged in the shared
    messages module. Returns the created
    :class:`messages.Message`."""
    init_db()
    a = get_alumnus(alumni_id)
    if a is None:
        raise ValidationError(f"No alumnus #{alumni_id}")
    if not a.email:
        raise ValidationError("Alumnus has no primary email")
    if respect_optin:
        prefs = get_channel_prefs(alumni_id)
        if not prefs.opt_in_email:
            raise ValidationError(
                "Alumnus has opted out of email contact")
    ctx = _alumnus_context(a)
    msg = _messages_module()
    out = msg.create_message({
        "direction":  "Outgoing",
        "channel":    "Email",
        "category":   category,
        "status":     "Sent",
        "subject":    _render(subject, ctx),
        "body":       _render(body, ctx),
        "alumni_id":  alumni_id,
        "to_name":    a.full_name,
        "to_address": a.email,
        "staff_id":   (staff_id or "").strip().upper() or None,
        "sent_at":    msg._now(),
    })
    _log_action("alumnus.send_email", actor=staff_id,
                  alumni_id=alumni_id, message_id=out.message_id,
                  subject=out.subject)
    return out


def send_email_bulk(filters: dict[str, Any], subject: str, body: str,
                     *, staff_id: str | None = None,
                     category: str = "General"):
    """Mail-merge to every alumnus matching ``filters`` (same kwargs
    as :func:`list_alumni`) who has an email, is Active and has
    ``opt_in_email`` set. One messages row per recipient, sharing a
    thread. Returns the messages ``BulkResult``."""
    init_db()
    rows = list_alumni(**filters)
    msg = _messages_module()
    recipients: list[tuple[int, str, str]] = []
    skipped = 0
    for a in rows:
        if not a.email or a.status != "Active":
            skipped += 1
            continue
        try:
            prefs = get_channel_prefs(a.alumni_id)
        except ValidationError:
            skipped += 1
            continue
        if not prefs.opt_in_email:
            skipped += 1
            continue
        ctx = _alumnus_context(a)
        # Per-recipient merge: create one outgoing message per
        # alumnus so placeholders render against their record.
        try:
            msg.create_message({
                "direction":  "Outgoing",
                "channel":    "Email",
                "category":   category,
                "status":     "Sent",
                "subject":    _render(subject, ctx),
                "body":       _render(body, ctx),
                "alumni_id":  a.alumni_id,
                "to_name":    a.full_name,
                "to_address": a.email,
                "staff_id":   (staff_id or "").strip().upper() or None,
                "sent_at":    msg._now(),
            })
            recipients.append((a.alumni_id, a.full_name, a.email))
        except Exception:
            logger.exception(
                "Bulk send failed for alumnus #%d", a.alumni_id)
            skipped += 1
    _log_action("alumnus.send_email_bulk", actor=staff_id,
                  sent=len(recipients), skipped=skipped,
                  filters=str(filters))
    return len(recipients), skipped


# ── Cross-module linking (#11–#15) ────────────────────────────────

def _safe_import(path: str):
    try:
        from importlib import import_module
        return import_module(path)
    except Exception:
        return None


def was_bursary_recipient(student_id: str) -> bool:
    bm = _safe_import(
        "education_system.sixthform_system.modules.domain.finance.bursaries.bursaries")
    if bm is None:
        return False
    try:
        approved, paid, _outstanding = bm.student_summary(student_id)
    except Exception:
        logger.debug("Bursary lookup failed for %s",
                       student_id, exc_info=True)
        return False
    return (approved or 0) > 0 or (paid or 0) > 0


def bursary_summary_for(student_id: str
                          ) -> tuple[float, float, float] | None:
    bm = _safe_import(
        "education_system.sixthform_system.modules.domain.finance.bursaries.bursaries")
    if bm is None:
        return None
    try:
        return bm.student_summary(student_id)
    except Exception:
        logger.debug("bursary_summary_for(%s) failed",
                       student_id, exc_info=True)
        return None


def _ucas_destination_for(student_id: str
                            ) -> tuple[str | None, int | None]:
    """Return (destination_detail, cycle_year) from the most recent
    UCAS application whose firm/insurance choice is the student's
    final destination. Best-effort."""
    um = _safe_import(
        "education_system.sixthform_system.modules.domain.progression.ucas.ucas")
    if um is None:
        return (None, None)
    try:
        app = um.get_application_for_student(student_id)
        if app is None:
            return (None, None)
        choices = um.list_choices(app.application_id)
        firm = next((c for c in choices
                       if (c.final_decision or "").lower() == "firm"),
                      None)
        target = firm or next((c for c in choices
                                  if (c.final_decision or "").lower()
                                  == "insurance"), None)
        if target is None:
            return (None, app.cycle_year)
        detail = f"{target.university} — {target.course_name}"
        return (detail, app.cycle_year)
    except Exception:
        logger.exception("UCAS lookup failed for %s", student_id)
        return (None, None)


def _exam_results_for(student_id: str
                        ) -> list[tuple[str, str, str | None, int | None]]:
    """Return list of (subject, grade, board, year) tuples for the
    student. Empty list if exam_results module unavailable.

    Tries the modern ``results_for_student`` API first, then the
    older ``list_results`` keyword form, then the legacy
    ``list_results_with_detail`` name — accommodates schema drift
    across exam_results module versions."""
    em = _safe_import(
        "education_system.sixthform_system.modules.domain."
        "exam_results.exam_results")
    if em is None:
        return []
    rows = None
    for fn_name, kwargs in (
            ("results_for_student", {"student_id": student_id}),
            ("list_results",        {"student_id": student_id}),
            ("list_results_with_detail",
                {"student_id": student_id}),
            ("list_results_with_detail", {})):
        fn = getattr(em, fn_name, None)
        if fn is None:
            continue
        try:
            rows = fn(**kwargs)
            if not kwargs:
                rows = [r for r in rows
                          if getattr(r, "student_id", None)
                              == student_id]
            break
        except TypeError:
            # Wrong kwargs for this version — try the next form.
            continue
        except Exception:
            logger.warning(
                "exam_results.%s failed for %s",
                fn_name, student_id, exc_info=True)
            return []
    if rows is None:
        return []
    out: list[tuple[str, str, str | None, int | None]] = []
    for r in rows:
        try:
            grade = (r.result.grade if r.result else None) or ""
            if not grade:
                continue
            out.append((r.subject, grade,
                         getattr(r, "exam_board", None),
                         getattr(r, "year", None)))
        except Exception:
            continue
    return out


def _career_aspiration_for(student_id: str) -> str | None:
    cm = _safe_import(
        "education_system.sixthform_system.modules.domain.progression.careers.careers")
    if cm is None:
        return None
    try:
        a = cm.get_aspiration_for_student(student_id)
    except Exception:
        logger.debug("careers aspiration lookup failed for %s",
                       student_id, exc_info=True)
        return None
    if a is None:
        return None
    parts = [a.target_career, a.target_course, a.target_employer]
    return " / ".join(p for p in parts if p) or None


def archive_student_enriched(student_id: str, **kwargs) -> Alumnus:
    """Like :func:`archive_student` but first auto-fills destination
    detail from UCAS, seeds A-level results into the education table
    from exam_results, tags bursary recipients, and links any career
    aspiration in the notes. Any ``**kwargs`` accepted by
    ``archive_student`` override auto-derived values."""
    init_db()
    ucas_detail, ucas_year = _ucas_destination_for(student_id)
    aspiration = _career_aspiration_for(student_id)
    derived: dict[str, Any] = {}
    if ucas_detail and not kwargs.get("destination_detail"):
        derived["destination_detail"] = ucas_detail
        derived["destination_type"] = (kwargs.get("destination_type")
                                          or "University")
    if ucas_year and not kwargs.get("leaving_year"):
        derived["leaving_year"] = str(ucas_year)
    if aspiration and not kwargs.get("notes"):
        derived["notes"] = f"Aspiration on leaving: {aspiration}"
    payload = {**derived, **kwargs}
    a = archive_student(student_id, **payload)
    # Seed A-level results into education history
    existing_edu = list_education(a.alumni_id)
    if not existing_edu:
        for subject, grade, board, year in _exam_results_for(student_id):
            try:
                add_education(a.alumni_id, {
                    "qualification": "A-Level",
                    "subject":       subject,
                    "institution":   board or "Sixth Form",
                    "end_date":      f"{year}-08-31" if year else None,
                    "grade":         grade,
                    "status":        "Completed",
                })
            except ValidationError:
                continue
    # Tag bursary recipients
    if was_bursary_recipient(student_id):
        try:
            add_tag(a.alumni_id, "Bursary recipient")
        except Exception:
            logger.exception("Failed to tag bursary recipient #%d",
                              a.alumni_id)
    _log_action("alumnus.archive_enriched",
                  alumni_id=a.alumni_id, student_id=student_id,
                  destination=a.destination_type,
                  edu_rows=len(list_education(a.alumni_id)))
    return a


def alumnus_for_student(student_id: str) -> Alumnus | None:
    """Alias of :func:`get_alumnus_by_original_id` — intended for
    use from the students module to show 'this student became
    alumnus #N' on their profile."""
    return get_alumnus_by_original_id(student_id)


def find_unarchived_leavers() -> list[UnarchivedLeaver]:
    """Return current students who look like leavers — i.e. either
    have a UCAS application with a final decision, or recorded
    A-level (i.e. exam) results from a past summer — but no alumni
    row yet. Sort by oldest cycle/exam year first."""
    init_db()
    sm = _safe_import(
        "education_system.sixthform_system.modules.domain.students.students.students")
    if sm is None:
        return []
    try:
        students = sm.list_students()
    except Exception:
        logger.warning("students.list_students() failed",
                         exc_info=True)
        return []
    out: list[UnarchivedLeaver] = []
    today_year = _dt.date.today().year
    for s in students:
        if get_alumnus_by_original_id(s.student_id) is not None:
            continue
        detail, cycle = _ucas_destination_for(s.student_id)
        exams = _exam_results_for(s.student_id)
        last_year = max((y for _, _, _, y in exams if y), default=None)
        is_leaver = False
        if detail and cycle and cycle <= today_year:
            is_leaver = True
        if last_year and last_year < today_year:
            is_leaver = True
        if not is_leaver:
            continue
        out.append(UnarchivedLeaver(
            student_id=s.student_id, full_name=s.full_name,
            email=getattr(s, "email", None),
            ucas_cycle_year=cycle, final_destination=detail,
            last_exam_year=last_year))
    out.sort(key=lambda x: (x.ucas_cycle_year or x.last_exam_year
                              or today_year, x.student_id))
    return out


@dataclass
class CareerAdviceRow:
    destination_type: str
    detail: str
    sector: str | None
    count: int


def destinations_for_advice(*, subject: str | None = None,
                              sector: str | None = None,
                              limit: int = 25
                              ) -> list[CareerAdviceRow]:
    """Aggregate alumni destinations for use by the careers module
    when advising current students. If ``subject`` is given, restrict
    to alumni who studied that A-level subject (joining via the
    education history). If ``sector`` is given, restrict to alumni
    now working in that sector."""
    init_db()
    args: list[Any] = []
    join = ""
    where = ["a.status != 'Deceased'", "a.destination_type != 'Unknown'"]
    if subject:
        join = ("JOIN alumni_education e ON e.alumni_id = a.alumni_id "
                 "AND e.qualification = 'A-Level' "
                 "AND e.subject = ? COLLATE NOCASE ")
        args.append(subject)
    if sector:
        where.append("a.current_sector = ?")
        args.append(sector)
    sql = (f"SELECT a.destination_type AS d, "
            f"COALESCE(a.destination_detail, '—') AS detail, "
            f"a.current_sector AS sector, COUNT(*) AS n "
            f"FROM alumni a {join}"
            f"WHERE {' AND '.join(where)} "
            f"GROUP BY a.destination_type, a.destination_detail, "
            f"a.current_sector "
            f"ORDER BY n DESC LIMIT ?")
    args.append(limit)
    with _connect() as conn:
        rows = conn.execute(sql, args).fetchall()
    return [CareerAdviceRow(
        destination_type=r["d"], detail=r["detail"],
        sector=r["sector"], count=r["n"]) for r in rows]


# ══ Engagement & programmes ══════════════════════════════════════
#
# Money is stored in pence to keep totals exact. Helpers below
# accept either pounds (float, will be rounded to nearest penny) or
# pence (int) — see ``_money_in``.


def _pounds_to_pence(value: Any, label: str, *,
                       allow_zero: bool = False,
                       required: bool = True) -> int:
    """Coerce a money amount expressed in *pounds* to integer pence.
    Accepts ``int``/``float`` (pounds) or ``str`` (with optional
    leading £ and commas). Always multiplies by 100."""
    if value in (None, "") or (isinstance(value, str)
                                  and not value.strip()):
        if required:
            raise ValidationError(f"{label} is required")
        return 0
    if isinstance(value, bool):
        raise ValidationError(f"{label} must be a number")
    s = str(value).strip().lstrip("£").replace(",", "")
    try:
        pence = round(float(s) * 100)
    except ValueError:
        raise ValidationError(f"{label} is not a valid amount") \
            from None
    if pence < 0:
        raise ValidationError(f"{label} cannot be negative")
    if not allow_zero and pence == 0:
        raise ValidationError(f"{label} must be greater than zero")
    return pence


def _resolve_money(payload: dict[str, Any],
                     pence_key: str, pounds_key: str,
                     label: str, *,
                     allow_zero: bool = False,
                     required: bool = True) -> int:
    """Read a money amount from either ``<pence_key>`` (raw integer
    pence) or ``<pounds_key>`` (pounds, float-ish). Pence wins if
    both are supplied."""
    if payload.get(pence_key) not in (None, ""):
        try:
            p = int(payload[pence_key])
        except (TypeError, ValueError):
            raise ValidationError(
                f"{label} (pence) must be an integer") from None
        if p < 0:
            raise ValidationError(f"{label} cannot be negative")
        if not allow_zero and p == 0:
            raise ValidationError(
                f"{label} must be greater than zero")
        return p
    return _pounds_to_pence(payload.get(pounds_key), label,
                              allow_zero=allow_zero,
                              required=required)


def _money_out(pence: int | None) -> str:
    if pence is None:
        return "—"
    return f"£{pence / 100:,.2f}"


# ── Events ───────────────────────────────────────────────────────

@dataclass
class Event:
    event_id: int
    name: str
    event_type: str
    event_date: str | None
    end_date: str | None
    location: str | None
    capacity: int | None
    cost_pence: int
    status: str
    notes: str | None
    created_at: str


def _row_event(r: sqlite3.Row) -> Event:
    return Event(
        event_id=r["event_id"], name=r["name"],
        event_type=r["event_type"], event_date=r["event_date"],
        end_date=r["end_date"], location=r["location"],
        capacity=r["capacity"], cost_pence=int(r["cost_pence"] or 0),
        status=r["status"], notes=r["notes"],
        created_at=r["created_at"],
    )


def _validate_event(payload: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["name"] = _require(payload.get("name"), "Name").strip()
    et = (payload.get("event_type") or EVENT_TYPES[0]).strip()
    if et not in EVENT_TYPES:
        raise ValidationError(
            f"Event type must be one of: {', '.join(EVENT_TYPES)}")
    out["event_type"] = et
    out["event_date"] = _validate_date(payload.get("event_date"),
                                          "Event date")
    out["end_date"]   = _validate_date(payload.get("end_date"),
                                          "End date")
    out["location"] = (payload.get("location") or "").strip() or None
    cap = payload.get("capacity")
    if cap in (None, ""):
        out["capacity"] = None
    else:
        try:
            out["capacity"] = max(0, int(cap))
        except (TypeError, ValueError):
            raise ValidationError("Capacity must be a number") from None
    out["cost_pence"] = _resolve_money(payload, "cost_pence", "cost",
                                          "Cost", allow_zero=True,
                                          required=False)
    status = (payload.get("status") or DEFAULT_EVENT_STATUS).strip()
    if status not in EVENT_STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(EVENT_STATUSES)}")
    out["status"] = status
    out["notes"] = (payload.get("notes") or "").strip() or None
    return out


def create_event(payload: dict[str, Any]) -> Event:
    init_db()
    p = _validate_event(payload)
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO alumni_events
                   (name, event_type, event_date, end_date, location,
                    capacity, cost_pence, status, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (p["name"], p["event_type"], p["event_date"], p["end_date"],
             p["location"], p["capacity"], p["cost_pence"],
             p["status"], p["notes"]))
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_events WHERE event_id = ?",
            (cur.lastrowid,)).fetchone()
    out = _row_event(r)
    _log_action("event.create", event_id=out.event_id,
                  name=out.name, event_type=out.event_type,
                  event_date=out.event_date)
    return out


def get_event(event_id: int) -> Event | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM alumni_events WHERE event_id = ?",
            (event_id,)).fetchone()
    return _row_event(r) if r else None


def list_events(*, status: str | None = None,
                  upcoming_only: bool = False) -> list[Event]:
    init_db()
    clauses, args = [], []
    if status:
        if status not in EVENT_STATUSES:
            raise ValidationError(
                f"Status must be one of: {', '.join(EVENT_STATUSES)}")
        clauses.append("status = ?")
        args.append(status)
    if upcoming_only:
        clauses.append("(event_date IS NULL OR event_date >= ?)")
        args.append(_dt.date.today().isoformat())
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM alumni_events {where} "
            "ORDER BY COALESCE(event_date, '9999') ASC, event_id DESC")
    with _connect() as conn:
        return [_row_event(r)
                  for r in conn.execute(sql, args).fetchall()]


def update_event(event_id: int, payload: dict[str, Any]) -> Event:
    existing = get_event(event_id)
    if existing is None:
        raise ValidationError(f"No event #{event_id}")
    merged = {
        "name":       payload.get("name", existing.name),
        "event_type": payload.get("event_type", existing.event_type),
        "event_date": payload.get("event_date", existing.event_date),
        "end_date":   payload.get("end_date", existing.end_date),
        "location":   payload.get("location", existing.location),
        "capacity":   payload.get("capacity", existing.capacity),
        "cost_pence": payload.get("cost_pence", existing.cost_pence),
        "status":     payload.get("status", existing.status),
        "notes":      payload.get("notes", existing.notes),
    }
    p = _validate_event(merged)
    with _connect() as conn:
        conn.execute(
            """UPDATE alumni_events SET
                   name = ?, event_type = ?, event_date = ?, end_date = ?,
                   location = ?, capacity = ?, cost_pence = ?,
                   status = ?, notes = ?
               WHERE event_id = ?""",
            (p["name"], p["event_type"], p["event_date"], p["end_date"],
             p["location"], p["capacity"], p["cost_pence"],
             p["status"], p["notes"], event_id))
        conn.commit()
    out = get_event(event_id)
    assert out is not None
    return out


def delete_event(event_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM alumni_events WHERE event_id = ?",
            (event_id,))
        conn.commit()
        return cur.rowcount > 0


# ── RSVPs ────────────────────────────────────────────────────────

@dataclass
class Rsvp:
    rsvp_id: int
    event_id: int
    alumni_id: int
    status: str
    attended: bool
    guests: int
    notes: str | None
    created_at: str


def _row_rsvp(r: sqlite3.Row) -> Rsvp:
    return Rsvp(
        rsvp_id=r["rsvp_id"], event_id=r["event_id"],
        alumni_id=r["alumni_id"], status=r["status"],
        attended=bool(r["attended"]),
        guests=int(r["guests"] or 0),
        notes=r["notes"], created_at=r["created_at"],
    )


def set_rsvp(event_id: int, alumni_id: int, *,
              status: str = DEFAULT_RSVP_STATUS,
              attended: bool | None = None,
              guests: int | None = None,
              notes: str | None = None) -> Rsvp:
    """Create or update an RSVP. Upserts on the unique
    (event_id, alumni_id) key."""
    init_db()
    if status not in RSVP_STATUSES:
        raise ValidationError(
            f"RSVP status must be one of: {', '.join(RSVP_STATUSES)}")
    with _connect() as conn:
        if get_event(event_id) is None:
            raise ValidationError(f"No event #{event_id}")
        _require_alumnus(conn, alumni_id)
        existing = conn.execute(
            "SELECT * FROM alumni_event_rsvps "
            "WHERE event_id = ? AND alumni_id = ?",
            (event_id, alumni_id)).fetchone()
        if existing:
            new_status   = status
            new_attended = (existing["attended"]
                              if attended is None
                              else (1 if attended else 0))
            new_guests   = (existing["guests"]
                              if guests is None
                              else max(0, int(guests)))
            new_notes    = (existing["notes"]
                              if notes is None
                              else (notes.strip() or None))
            conn.execute(
                "UPDATE alumni_event_rsvps SET status = ?, "
                "attended = ?, guests = ?, notes = ? "
                "WHERE rsvp_id = ?",
                (new_status, new_attended, new_guests, new_notes,
                 existing["rsvp_id"]))
            conn.commit()
            r = conn.execute(
                "SELECT * FROM alumni_event_rsvps WHERE rsvp_id = ?",
                (existing["rsvp_id"],)).fetchone()
        else:
            conn.execute(
                """INSERT INTO alumni_event_rsvps
                       (event_id, alumni_id, status, attended,
                        guests, notes)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (event_id, alumni_id, status,
                 1 if attended else 0,
                 max(0, int(guests or 0)),
                 (notes or "").strip() or None))
            conn.commit()
            r = conn.execute(
                "SELECT * FROM alumni_event_rsvps "
                "WHERE event_id = ? AND alumni_id = ?",
                (event_id, alumni_id)).fetchone()
    return _row_rsvp(r)


def list_rsvps_for_event(event_id: int) -> list[Rsvp]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM alumni_event_rsvps WHERE event_id = ? "
            "ORDER BY status, rsvp_id",
            (event_id,)).fetchall()
    return [_row_rsvp(r) for r in rows]


def list_rsvps_for_alumnus(alumni_id: int) -> list[Rsvp]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM alumni_event_rsvps WHERE alumni_id = ? "
            "ORDER BY rsvp_id DESC",
            (alumni_id,)).fetchall()
    return [_row_rsvp(r) for r in rows]


def delete_rsvp(rsvp_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM alumni_event_rsvps WHERE rsvp_id = ?",
            (rsvp_id,))
        conn.commit()
        return cur.rowcount > 0


@dataclass
class EventAttendance:
    event_id: int
    invited: int
    accepted: int
    declined: int
    attended: int
    headcount: int     # attended + sum of guests for attended rows


def event_attendance(event_id: int) -> EventAttendance:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT status, attended, guests "
            "FROM alumni_event_rsvps WHERE event_id = ?",
            (event_id,)).fetchall()
    invited = accepted = declined = attended = headcount = 0
    for r in rows:
        invited += 1
        if r["status"] == "Accepted":
            accepted += 1
        if r["status"] == "Declined":
            declined += 1
        if r["attended"]:
            attended += 1
            headcount += 1 + int(r["guests"] or 0)
    return EventAttendance(
        event_id=event_id, invited=invited, accepted=accepted,
        declined=declined, attended=attended, headcount=headcount)


# ── Mentorships ──────────────────────────────────────────────────

@dataclass
class Mentorship:
    mentorship_id: int
    mentor_alumni_id: int
    mentee_student_id: str
    topic: str | None
    started_on: str
    ended_on: str | None
    status: str
    notes: str | None
    created_at: str


@dataclass
class MentorSession:
    session_id: int
    mentorship_id: int
    session_date: str
    duration_minutes: int | None
    format: str | None
    summary: str | None
    mentor_feedback: str | None
    mentee_feedback: str | None
    created_at: str


def _row_mentorship(r: sqlite3.Row) -> Mentorship:
    return Mentorship(
        mentorship_id=r["mentorship_id"],
        mentor_alumni_id=r["mentor_alumni_id"],
        mentee_student_id=r["mentee_student_id"],
        topic=r["topic"], started_on=r["started_on"],
        ended_on=r["ended_on"], status=r["status"],
        notes=r["notes"], created_at=r["created_at"],
    )


def _row_session(r: sqlite3.Row) -> MentorSession:
    return MentorSession(
        session_id=r["session_id"],
        mentorship_id=r["mentorship_id"],
        session_date=r["session_date"],
        duration_minutes=r["duration_minutes"],
        format=r["format"], summary=r["summary"],
        mentor_feedback=r["mentor_feedback"],
        mentee_feedback=r["mentee_feedback"],
        created_at=r["created_at"],
    )


def start_mentorship(mentor_alumni_id: int,
                      mentee_student_id: str,
                      *,
                      topic: str | None = None,
                      started_on: str | None = None,
                      notes: str | None = None) -> Mentorship:
    init_db()
    started = _validate_date(started_on or _dt.date.today().isoformat(),
                                "Start date", required=True)
    mentee = _require(mentee_student_id, "Mentee student id").strip()
    with _connect() as conn:
        _require_alumnus(conn, mentor_alumni_id)
        cur = conn.execute(
            """INSERT INTO alumni_mentorships
                   (mentor_alumni_id, mentee_student_id, topic,
                    started_on, status, notes)
               VALUES (?, ?, ?, ?, 'Active', ?)""",
            (mentor_alumni_id, mentee,
             (topic or "").strip() or None, started,
             (notes or "").strip() or None))
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_mentorships WHERE mentorship_id = ?",
            (cur.lastrowid,)).fetchone()
    return _row_mentorship(r)


def list_mentorships_by_mentor(alumni_id: int
                                  ) -> list[Mentorship]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM alumni_mentorships "
            "WHERE mentor_alumni_id = ? "
            "ORDER BY status='Active' DESC, started_on DESC",
            (alumni_id,)).fetchall()
    return [_row_mentorship(r) for r in rows]


def list_mentorships_by_mentee(student_id: str
                                  ) -> list[Mentorship]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM alumni_mentorships "
            "WHERE mentee_student_id = ? "
            "ORDER BY started_on DESC",
            (student_id.strip(),)).fetchall()
    return [_row_mentorship(r) for r in rows]


def end_mentorship(mentorship_id: int, *,
                    ended_on: str | None = None,
                    status: str = "Completed",
                    notes: str | None = None) -> Mentorship:
    if status not in MENTORSHIP_STATUSES:
        raise ValidationError(
            f"Status must be one of: "
            f"{', '.join(MENTORSHIP_STATUSES)}")
    end = _validate_date(ended_on or _dt.date.today().isoformat(),
                           "End date", required=True)
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE alumni_mentorships SET ended_on = ?, status = ?, "
            "notes = COALESCE(?, notes) "
            "WHERE mentorship_id = ?",
            (end, status, notes, mentorship_id))
        conn.commit()
        if cur.rowcount == 0:
            raise ValidationError(
                f"No mentorship #{mentorship_id}")
        r = conn.execute(
            "SELECT * FROM alumni_mentorships WHERE mentorship_id = ?",
            (mentorship_id,)).fetchone()
    return _row_mentorship(r)


def delete_mentorship(mentorship_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM alumni_mentorships WHERE mentorship_id = ?",
            (mentorship_id,))
        conn.commit()
        return cur.rowcount > 0


def log_mentor_session(mentorship_id: int,
                         payload: dict[str, Any]) -> MentorSession:
    init_db()
    day = _validate_date(payload.get("session_date")
                            or _dt.date.today().isoformat(),
                          "Session date", required=True)
    fmt = (payload.get("format") or "").strip()
    if fmt and fmt not in SESSION_FORMATS:
        raise ValidationError(
            f"Format must be one of: {', '.join(SESSION_FORMATS)}")
    dur = payload.get("duration_minutes")
    if dur in (None, ""):
        dur = None
    else:
        try:
            dur = max(0, int(dur))
        except (TypeError, ValueError):
            raise ValidationError("Duration must be minutes (number)") \
                from None
    with _connect() as conn:
        r0 = conn.execute(
            "SELECT 1 FROM alumni_mentorships WHERE mentorship_id = ?",
            (mentorship_id,)).fetchone()
        if r0 is None:
            raise ValidationError(
                f"No mentorship #{mentorship_id}")
        cur = conn.execute(
            """INSERT INTO alumni_mentor_sessions
                   (mentorship_id, session_date, duration_minutes,
                    format, summary, mentor_feedback, mentee_feedback)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (mentorship_id, day, dur, fmt or None,
             (payload.get("summary") or "").strip() or None,
             (payload.get("mentor_feedback") or "").strip() or None,
             (payload.get("mentee_feedback") or "").strip() or None))
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_mentor_sessions WHERE session_id = ?",
            (cur.lastrowid,)).fetchone()
    return _row_session(r)


def list_mentor_sessions(mentorship_id: int) -> list[MentorSession]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM alumni_mentor_sessions "
            "WHERE mentorship_id = ? "
            "ORDER BY session_date DESC, session_id DESC",
            (mentorship_id,)).fetchall()
    return [_row_session(r) for r in rows]


def delete_mentor_session(session_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM alumni_mentor_sessions WHERE session_id = ?",
            (session_id,))
        conn.commit()
        return cur.rowcount > 0


# ── Speakers register ────────────────────────────────────────────

@dataclass
class SpeakerProfile:
    alumni_id: int
    topics: str | None
    year_groups: str | None
    availability_notes: str | None
    last_confirmed_at: str | None
    updated_at: str


def _row_speaker(r: sqlite3.Row) -> SpeakerProfile:
    return SpeakerProfile(
        alumni_id=r["alumni_id"], topics=r["topics"],
        year_groups=r["year_groups"],
        availability_notes=r["availability_notes"],
        last_confirmed_at=r["last_confirmed_at"],
        updated_at=r["updated_at"],
    )


def upsert_speaker(alumni_id: int, *,
                    topics: str | None = None,
                    year_groups: str | None = None,
                    availability_notes: str | None = None,
                    confirm: bool = False) -> SpeakerProfile:
    init_db()
    today = _dt.date.today().isoformat()
    with _connect() as conn:
        _require_alumnus(conn, alumni_id)
        existing = conn.execute(
            "SELECT * FROM alumni_speakers WHERE alumni_id = ?",
            (alumni_id,)).fetchone()
        if existing:
            new_topics = ((topics or "").strip()
                            if topics is not None else existing["topics"])
            new_years  = ((year_groups or "").strip()
                            if year_groups is not None
                            else existing["year_groups"])
            new_avail  = ((availability_notes or "").strip()
                            if availability_notes is not None
                            else existing["availability_notes"])
            new_conf   = (today if confirm
                            else existing["last_confirmed_at"])
            conn.execute(
                """UPDATE alumni_speakers SET
                       topics = ?, year_groups = ?,
                       availability_notes = ?, last_confirmed_at = ?,
                       updated_at = datetime('now')
                   WHERE alumni_id = ?""",
                (new_topics or None, new_years or None,
                 new_avail or None, new_conf, alumni_id))
        else:
            conn.execute(
                """INSERT INTO alumni_speakers
                       (alumni_id, topics, year_groups,
                        availability_notes, last_confirmed_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (alumni_id,
                 (topics or "").strip() or None,
                 (year_groups or "").strip() or None,
                 (availability_notes or "").strip() or None,
                 today if confirm else None))
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_speakers WHERE alumni_id = ?",
            (alumni_id,)).fetchone()
    return _row_speaker(r)


def get_speaker(alumni_id: int) -> SpeakerProfile | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM alumni_speakers WHERE alumni_id = ?",
            (alumni_id,)).fetchone()
    return _row_speaker(r) if r else None


def list_speakers(*, topic_like: str | None = None,
                    year_group: str | None = None
                    ) -> list[SpeakerProfile]:
    init_db()
    clauses, args = [], []
    if topic_like:
        clauses.append("topics LIKE ?")
        args.append(f"%{topic_like.strip()}%")
    if year_group:
        clauses.append("year_groups LIKE ?")
        args.append(f"%{year_group.strip()}%")
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM alumni_speakers {where} "
            "ORDER BY COALESCE(last_confirmed_at, '') DESC, alumni_id")
    with _connect() as conn:
        return [_row_speaker(r)
                  for r in conn.execute(sql, args).fetchall()]


def remove_speaker(alumni_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM alumni_speakers WHERE alumni_id = ?",
            (alumni_id,))
        conn.commit()
        return cur.rowcount > 0


# ── Work-experience offers ───────────────────────────────────────

@dataclass
class WorkExpOffer:
    offer_id: int
    alumni_id: int
    title: str
    employer: str | None
    sector: str | None
    location: str | None
    duration_weeks: int | None
    start_window: str | None
    vacancy_count: int
    requirements: str | None
    deadline: str | None
    status: str
    notes: str | None
    created_at: str


@dataclass
class WorkExpApplication:
    application_id: int
    offer_id: int
    student_id: str
    applied_on: str
    status: str
    outcome_notes: str | None


def _row_wxo(r: sqlite3.Row) -> WorkExpOffer:
    return WorkExpOffer(
        offer_id=r["offer_id"], alumni_id=r["alumni_id"],
        title=r["title"], employer=r["employer"],
        sector=r["sector"], location=r["location"],
        duration_weeks=r["duration_weeks"],
        start_window=r["start_window"],
        vacancy_count=int(r["vacancy_count"] or 1),
        requirements=r["requirements"], deadline=r["deadline"],
        status=r["status"], notes=r["notes"],
        created_at=r["created_at"],
    )


def _row_wxa(r: sqlite3.Row) -> WorkExpApplication:
    return WorkExpApplication(
        application_id=r["application_id"], offer_id=r["offer_id"],
        student_id=r["student_id"], applied_on=r["applied_on"],
        status=r["status"], outcome_notes=r["outcome_notes"],
    )


def add_work_exp_offer(alumni_id: int,
                          payload: dict[str, Any]) -> WorkExpOffer:
    init_db()
    title = _require(payload.get("title"), "Title").strip()
    sector = (payload.get("sector") or "").strip()
    if sector and sector not in SECTORS:
        raise ValidationError(
            f"Sector must be one of: {', '.join(SECTORS)}")
    status = (payload.get("status") or "Open").strip()
    if status not in WORK_EXP_STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(WORK_EXP_STATUSES)}")
    weeks = payload.get("duration_weeks")
    weeks = max(0, int(weeks)) if weeks not in (None, "") else None
    vacancies = int(payload.get("vacancy_count") or 1) or 1
    deadline = _validate_date(payload.get("deadline"), "Deadline")
    with _connect() as conn:
        _require_alumnus(conn, alumni_id)
        cur = conn.execute(
            """INSERT INTO alumni_work_exp_offers
                   (alumni_id, title, employer, sector, location,
                    duration_weeks, start_window, vacancy_count,
                    requirements, deadline, status, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (alumni_id, title,
             (payload.get("employer") or "").strip() or None,
             sector or None,
             (payload.get("location") or "").strip() or None,
             weeks,
             (payload.get("start_window") or "").strip() or None,
             vacancies,
             (payload.get("requirements") or "").strip() or None,
             deadline, status,
             (payload.get("notes") or "").strip() or None))
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_work_exp_offers WHERE offer_id = ?",
            (cur.lastrowid,)).fetchone()
    return _row_wxo(r)


def list_work_exp_offers(*, alumni_id: int | None = None,
                            status: str | None = None,
                            open_only: bool = False
                            ) -> list[WorkExpOffer]:
    init_db()
    clauses, args = [], []
    if alumni_id is not None:
        clauses.append("alumni_id = ?")
        args.append(int(alumni_id))
    if status:
        if status not in WORK_EXP_STATUSES:
            raise ValidationError(
                f"Status must be one of: "
                f"{', '.join(WORK_EXP_STATUSES)}")
        clauses.append("status = ?")
        args.append(status)
    if open_only:
        clauses.append("status = 'Open'")
        clauses.append("(deadline IS NULL OR deadline >= ?)")
        args.append(_dt.date.today().isoformat())
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM alumni_work_exp_offers {where} "
            "ORDER BY COALESCE(deadline, '9999') ASC, offer_id DESC")
    with _connect() as conn:
        return [_row_wxo(r)
                  for r in conn.execute(sql, args).fetchall()]


def update_work_exp_status(offer_id: int, status: str) -> WorkExpOffer:
    if status not in WORK_EXP_STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(WORK_EXP_STATUSES)}")
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE alumni_work_exp_offers SET status = ? "
            "WHERE offer_id = ?", (status, offer_id))
        conn.commit()
        if cur.rowcount == 0:
            raise ValidationError(f"No offer #{offer_id}")
        r = conn.execute(
            "SELECT * FROM alumni_work_exp_offers WHERE offer_id = ?",
            (offer_id,)).fetchone()
    return _row_wxo(r)


def delete_work_exp_offer(offer_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM alumni_work_exp_offers WHERE offer_id = ?",
            (offer_id,))
        conn.commit()
        return cur.rowcount > 0


def apply_to_work_exp(offer_id: int, student_id: str, *,
                        applied_on: str | None = None,
                        outcome_notes: str | None = None
                        ) -> WorkExpApplication:
    init_db()
    day = _validate_date(applied_on or _dt.date.today().isoformat(),
                          "Applied on", required=True)
    sid = _require(student_id, "Student id").strip()
    with _connect() as conn:
        r0 = conn.execute(
            "SELECT 1 FROM alumni_work_exp_offers WHERE offer_id = ?",
            (offer_id,)).fetchone()
        if r0 is None:
            raise ValidationError(f"No offer #{offer_id}")
        try:
            cur = conn.execute(
                """INSERT INTO alumni_work_exp_applications
                       (offer_id, student_id, applied_on,
                        status, outcome_notes)
                   VALUES (?, ?, ?, 'Submitted', ?)""",
                (offer_id, sid, day,
                 (outcome_notes or "").strip() or None))
            conn.commit()
            new_id = cur.lastrowid
        except sqlite3.IntegrityError:
            raise ValidationError(
                f"{sid} has already applied to offer #{offer_id}") \
                from None
        r = conn.execute(
            "SELECT * FROM alumni_work_exp_applications "
            "WHERE application_id = ?", (new_id,)).fetchone()
    return _row_wxa(r)


def set_work_exp_application_status(application_id: int,
                                       status: str,
                                       *,
                                       notes: str | None = None
                                       ) -> WorkExpApplication:
    if status not in WORK_EXP_APP_STATUSES:
        raise ValidationError(
            f"Status must be one of: "
            f"{', '.join(WORK_EXP_APP_STATUSES)}")
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE alumni_work_exp_applications "
            "SET status = ?, outcome_notes = COALESCE(?, outcome_notes) "
            "WHERE application_id = ?",
            (status, notes, application_id))
        conn.commit()
        if cur.rowcount == 0:
            raise ValidationError(
                f"No application #{application_id}")
        r = conn.execute(
            "SELECT * FROM alumni_work_exp_applications "
            "WHERE application_id = ?",
            (application_id,)).fetchone()
    return _row_wxa(r)


def list_work_exp_applications(offer_id: int
                                  ) -> list[WorkExpApplication]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM alumni_work_exp_applications "
            "WHERE offer_id = ? "
            "ORDER BY applied_on DESC, application_id DESC",
            (offer_id,)).fetchall()
    return [_row_wxa(r) for r in rows]


def delete_work_exp_application(application_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM alumni_work_exp_applications "
            "WHERE application_id = ?", (application_id,))
        conn.commit()
        return cur.rowcount > 0


# ── References given ─────────────────────────────────────────────

@dataclass
class Reference:
    reference_id: int
    alumni_id: int
    staff_id: str | None
    ref_type: str
    requested_on: str | None
    sent_on: str | None
    target_name: str | None
    target_url: str | None
    notes: str | None
    created_at: str


def _row_reference(r: sqlite3.Row) -> Reference:
    return Reference(
        reference_id=r["reference_id"], alumni_id=r["alumni_id"],
        staff_id=r["staff_id"], ref_type=r["ref_type"],
        requested_on=r["requested_on"], sent_on=r["sent_on"],
        target_name=r["target_name"], target_url=r["target_url"],
        notes=r["notes"], created_at=r["created_at"],
    )


def add_reference(alumni_id: int,
                    payload: dict[str, Any]) -> Reference:
    init_db()
    rt = (payload.get("ref_type") or "Job").strip()
    if rt not in REFERENCE_TYPES:
        raise ValidationError(
            f"Reference type must be one of: "
            f"{', '.join(REFERENCE_TYPES)}")
    requested = _validate_date(payload.get("requested_on"),
                                  "Requested on")
    sent = _validate_date(payload.get("sent_on"), "Sent on")
    with _connect() as conn:
        _require_alumnus(conn, alumni_id)
        cur = conn.execute(
            """INSERT INTO alumni_references
                   (alumni_id, staff_id, ref_type, requested_on, sent_on,
                    target_name, target_url, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (alumni_id,
             ((payload.get("staff_id") or "").strip().upper()
                or None),
             rt, requested, sent,
             (payload.get("target_name") or "").strip() or None,
             (payload.get("target_url") or "").strip() or None,
             (payload.get("notes") or "").strip() or None))
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_references WHERE reference_id = ?",
            (cur.lastrowid,)).fetchone()
    return _row_reference(r)


def list_references(alumni_id: int) -> list[Reference]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM alumni_references WHERE alumni_id = ? "
            "ORDER BY COALESCE(sent_on, requested_on, created_at) "
            "DESC, reference_id DESC",
            (alumni_id,)).fetchall()
    return [_row_reference(r) for r in rows]


def mark_reference_sent(reference_id: int, *,
                          when: str | None = None) -> Reference:
    init_db()
    sent = _validate_date(when or _dt.date.today().isoformat(),
                            "Sent on", required=True)
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE alumni_references SET sent_on = ? "
            "WHERE reference_id = ?", (sent, reference_id))
        conn.commit()
        if cur.rowcount == 0:
            raise ValidationError(
                f"No reference #{reference_id}")
        r = conn.execute(
            "SELECT * FROM alumni_references WHERE reference_id = ?",
            (reference_id,)).fetchone()
    return _row_reference(r)


def delete_reference(reference_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM alumni_references WHERE reference_id = ?",
            (reference_id,))
        conn.commit()
        return cur.rowcount > 0


# ── Volunteer hours ──────────────────────────────────────────────

@dataclass
class VolunteerEntry:
    volunteer_id: int
    alumni_id: int
    activity_date: str
    hours: float
    activity_type: str
    event_id: int | None
    notes: str | None
    created_at: str


def _row_volunteer(r: sqlite3.Row) -> VolunteerEntry:
    return VolunteerEntry(
        volunteer_id=r["volunteer_id"], alumni_id=r["alumni_id"],
        activity_date=r["activity_date"],
        hours=float(r["hours"]),
        activity_type=r["activity_type"], event_id=r["event_id"],
        notes=r["notes"], created_at=r["created_at"],
    )


def log_volunteer_hours(alumni_id: int, hours: float, *,
                          activity_type: str = "Other",
                          activity_date: str | None = None,
                          event_id: int | None = None,
                          notes: str | None = None
                          ) -> VolunteerEntry:
    init_db()
    if activity_type not in VOLUNTEER_ACTIVITY_TYPES:
        raise ValidationError(
            f"Activity type must be one of: "
            f"{', '.join(VOLUNTEER_ACTIVITY_TYPES)}")
    try:
        h = float(hours)
    except (TypeError, ValueError):
        raise ValidationError("Hours must be a number") from None
    if h <= 0:
        raise ValidationError("Hours must be greater than zero")
    day = _validate_date(activity_date or _dt.date.today().isoformat(),
                           "Activity date", required=True)
    with _connect() as conn:
        _require_alumnus(conn, alumni_id)
        if event_id is not None:
            r0 = conn.execute(
                "SELECT 1 FROM alumni_events WHERE event_id = ?",
                (event_id,)).fetchone()
            if r0 is None:
                raise ValidationError(f"No event #{event_id}")
        cur = conn.execute(
            """INSERT INTO alumni_volunteer_hours
                   (alumni_id, activity_date, hours, activity_type,
                    event_id, notes)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (alumni_id, day, h, activity_type, event_id,
             (notes or "").strip() or None))
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_volunteer_hours "
            "WHERE volunteer_id = ?", (cur.lastrowid,)).fetchone()
    return _row_volunteer(r)


def list_volunteer_hours(alumni_id: int) -> list[VolunteerEntry]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM alumni_volunteer_hours WHERE alumni_id = ? "
            "ORDER BY activity_date DESC, volunteer_id DESC",
            (alumni_id,)).fetchall()
    return [_row_volunteer(r) for r in rows]


def total_volunteer_hours(alumni_id: int) -> float:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT COALESCE(SUM(hours), 0) AS h "
            "FROM alumni_volunteer_hours WHERE alumni_id = ?",
            (alumni_id,)).fetchone()
    return float(r["h"])


def delete_volunteer_entry(volunteer_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM alumni_volunteer_hours WHERE volunteer_id = ?",
            (volunteer_id,))
        conn.commit()
        return cur.rowcount > 0


# ── Campaigns / donations / pledges ──────────────────────────────

@dataclass
class Campaign:
    campaign_id: int
    name: str
    description: str | None
    target_pence: int | None
    start_on: str | None
    end_on: str | None
    status: str
    created_at: str


@dataclass
class Donation:
    donation_id: int
    alumni_id: int
    campaign_id: int | None
    donation_date: str
    amount_pence: int
    gift_aid: bool
    payment_method: str | None
    anonymous: bool
    restricted_to: str | None
    notes: str | None
    created_at: str


@dataclass
class Pledge:
    pledge_id: int
    alumni_id: int
    campaign_id: int | None
    pledged_on: str
    amount_pence: int
    due_by: str | None
    status: str
    notes: str | None
    created_at: str


def _row_campaign(r: sqlite3.Row) -> Campaign:
    return Campaign(
        campaign_id=r["campaign_id"], name=r["name"],
        description=r["description"],
        target_pence=(int(r["target_pence"])
                        if r["target_pence"] is not None else None),
        start_on=r["start_on"], end_on=r["end_on"],
        status=r["status"], created_at=r["created_at"],
    )


def _row_donation(r: sqlite3.Row) -> Donation:
    return Donation(
        donation_id=r["donation_id"], alumni_id=r["alumni_id"],
        campaign_id=r["campaign_id"],
        donation_date=r["donation_date"],
        amount_pence=int(r["amount_pence"]),
        gift_aid=bool(r["gift_aid"]),
        payment_method=r["payment_method"],
        anonymous=bool(r["anonymous"]),
        restricted_to=r["restricted_to"], notes=r["notes"],
        created_at=r["created_at"],
    )


def _row_pledge(r: sqlite3.Row) -> Pledge:
    return Pledge(
        pledge_id=r["pledge_id"], alumni_id=r["alumni_id"],
        campaign_id=r["campaign_id"],
        pledged_on=r["pledged_on"],
        amount_pence=int(r["amount_pence"]),
        due_by=r["due_by"], status=r["status"],
        notes=r["notes"], created_at=r["created_at"],
    )


def create_campaign(payload: dict[str, Any]) -> Campaign:
    init_db()
    name = _require(payload.get("name"), "Campaign name").strip()
    status = (payload.get("status") or DEFAULT_CAMPAIGN_STATUS).strip()
    if status not in CAMPAIGN_STATUSES:
        raise ValidationError(
            f"Status must be one of: "
            f"{', '.join(CAMPAIGN_STATUSES)}")
    has_target = (payload.get("target_pence") not in (None, "")
                    or payload.get("target") not in (None, ""))
    target_pence = (_resolve_money(payload, "target_pence", "target",
                                       "Target", allow_zero=True,
                                       required=False)
                      if has_target else None)
    start = _validate_date(payload.get("start_on"), "Start")
    end   = _validate_date(payload.get("end_on"), "End")
    with _connect() as conn:
        try:
            cur = conn.execute(
                """INSERT INTO alumni_campaigns
                       (name, description, target_pence, start_on,
                        end_on, status)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (name,
                 (payload.get("description") or "").strip() or None,
                 target_pence, start, end, status))
            conn.commit()
        except sqlite3.IntegrityError:
            raise ValidationError(
                f"A campaign called '{name}' already exists") \
                from None
        r = conn.execute(
            "SELECT * FROM alumni_campaigns WHERE campaign_id = ?",
            (cur.lastrowid,)).fetchone()
    out = _row_campaign(r)
    _log_action("campaign.create", campaign_id=out.campaign_id,
                  name=out.name,
                  target_pence=out.target_pence,
                  status=out.status)
    return out


def get_campaign(campaign_id: int) -> Campaign | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM alumni_campaigns WHERE campaign_id = ?",
            (campaign_id,)).fetchone()
    return _row_campaign(r) if r else None


def list_campaigns(*, status: str | None = None) -> list[Campaign]:
    init_db()
    sql = "SELECT * FROM alumni_campaigns"
    args: list[Any] = []
    if status:
        if status not in CAMPAIGN_STATUSES:
            raise ValidationError(
                f"Status must be one of: "
                f"{', '.join(CAMPAIGN_STATUSES)}")
        sql += " WHERE status = ?"
        args.append(status)
    sql += " ORDER BY created_at DESC"
    with _connect() as conn:
        return [_row_campaign(r)
                  for r in conn.execute(sql, args).fetchall()]


def update_campaign_status(campaign_id: int, status: str) -> Campaign:
    if status not in CAMPAIGN_STATUSES:
        raise ValidationError(
            f"Status must be one of: "
            f"{', '.join(CAMPAIGN_STATUSES)}")
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE alumni_campaigns SET status = ? "
            "WHERE campaign_id = ?", (status, campaign_id))
        conn.commit()
        if cur.rowcount == 0:
            raise ValidationError(f"No campaign #{campaign_id}")
        r = conn.execute(
            "SELECT * FROM alumni_campaigns WHERE campaign_id = ?",
            (campaign_id,)).fetchone()
    return _row_campaign(r)


def delete_campaign(campaign_id: int) -> bool:
    """Deletes the campaign and (via FK SET NULL) leaves donations
    and pledges intact but no longer associated with a campaign."""
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM alumni_campaigns WHERE campaign_id = ?",
            (campaign_id,))
        conn.commit()
        return cur.rowcount > 0


def record_donation(alumni_id: int,
                     payload: dict[str, Any]) -> Donation:
    init_db()
    amount_pence = _resolve_money(payload, "amount_pence", "amount",
                                       "Amount")
    method = (payload.get("payment_method") or "").strip()
    if method and method not in PAYMENT_METHODS:
        raise ValidationError(
            f"Payment method must be one of: "
            f"{', '.join(PAYMENT_METHODS)}")
    day = _validate_date(payload.get("donation_date")
                            or _dt.date.today().isoformat(),
                          "Donation date", required=True)
    cid = payload.get("campaign_id")
    if cid in (None, ""):
        cid = None
    else:
        cid = int(cid)
        if get_campaign(cid) is None:
            raise ValidationError(f"No campaign #{cid}")
    with _connect() as conn:
        _require_alumnus(conn, alumni_id)
        cur = conn.execute(
            """INSERT INTO alumni_donations
                   (alumni_id, campaign_id, donation_date, amount_pence,
                    gift_aid, payment_method, anonymous,
                    restricted_to, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (alumni_id, cid, day, amount_pence,
             1 if payload.get("gift_aid") else 0,
             method or None,
             1 if payload.get("anonymous") else 0,
             (payload.get("restricted_to") or "").strip() or None,
             (payload.get("notes") or "").strip() or None))
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_donations WHERE donation_id = ?",
            (cur.lastrowid,)).fetchone()
    out = _row_donation(r)
    _log_action("donation.record", alumni_id=alumni_id,
                  donation_id=out.donation_id,
                  amount_pence=out.amount_pence,
                  campaign_id=out.campaign_id,
                  gift_aid=out.gift_aid)
    return out


def list_donations(*, alumni_id: int | None = None,
                      campaign_id: int | None = None
                      ) -> list[Donation]:
    init_db()
    clauses, args = [], []
    if alumni_id is not None:
        clauses.append("alumni_id = ?")
        args.append(int(alumni_id))
    if campaign_id is not None:
        clauses.append("campaign_id = ?")
        args.append(int(campaign_id))
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM alumni_donations {where} "
            "ORDER BY donation_date DESC, donation_id DESC")
    with _connect() as conn:
        return [_row_donation(r)
                  for r in conn.execute(sql, args).fetchall()]


def delete_donation(donation_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM alumni_donations WHERE donation_id = ?",
            (donation_id,))
        conn.commit()
        return cur.rowcount > 0


def add_pledge(alumni_id: int, payload: dict[str, Any]) -> Pledge:
    init_db()
    amount_pence = _resolve_money(payload, "amount_pence", "amount",
                                       "Pledge amount")
    pledged = _validate_date(payload.get("pledged_on")
                                 or _dt.date.today().isoformat(),
                               "Pledged on", required=True)
    due_by = _validate_date(payload.get("due_by"), "Due by")
    status = (payload.get("status") or DEFAULT_PLEDGE_STATUS).strip()
    if status not in PLEDGE_STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(PLEDGE_STATUSES)}")
    cid = payload.get("campaign_id")
    if cid in (None, ""):
        cid = None
    else:
        cid = int(cid)
        if get_campaign(cid) is None:
            raise ValidationError(f"No campaign #{cid}")
    with _connect() as conn:
        _require_alumnus(conn, alumni_id)
        cur = conn.execute(
            """INSERT INTO alumni_pledges
                   (alumni_id, campaign_id, pledged_on, amount_pence,
                    due_by, status, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (alumni_id, cid, pledged, amount_pence, due_by, status,
             (payload.get("notes") or "").strip() or None))
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_pledges WHERE pledge_id = ?",
            (cur.lastrowid,)).fetchone()
    return _row_pledge(r)


def list_pledges(*, alumni_id: int | None = None,
                    campaign_id: int | None = None,
                    open_only: bool = False) -> list[Pledge]:
    init_db()
    clauses, args = [], []
    if alumni_id is not None:
        clauses.append("alumni_id = ?")
        args.append(int(alumni_id))
    if campaign_id is not None:
        clauses.append("campaign_id = ?")
        args.append(int(campaign_id))
    if open_only:
        clauses.append("status = 'Open'")
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM alumni_pledges {where} "
            "ORDER BY pledged_on DESC, pledge_id DESC")
    with _connect() as conn:
        return [_row_pledge(r)
                  for r in conn.execute(sql, args).fetchall()]


def update_pledge_status(pledge_id: int, status: str) -> Pledge:
    if status not in PLEDGE_STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(PLEDGE_STATUSES)}")
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE alumni_pledges SET status = ? "
            "WHERE pledge_id = ?", (status, pledge_id))
        conn.commit()
        if cur.rowcount == 0:
            raise ValidationError(f"No pledge #{pledge_id}")
        r = conn.execute(
            "SELECT * FROM alumni_pledges WHERE pledge_id = ?",
            (pledge_id,)).fetchone()
    return _row_pledge(r)


def delete_pledge(pledge_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM alumni_pledges WHERE pledge_id = ?",
            (pledge_id,))
        conn.commit()
        return cur.rowcount > 0


@dataclass
class CampaignTotals:
    campaign_id: int
    name: str
    target_pence: int | None
    raised_pence: int       # actual donations
    pledged_open_pence: int  # outstanding pledges (status=Open)
    donor_count: int


def campaign_totals(campaign_id: int) -> CampaignTotals:
    c = get_campaign(campaign_id)
    if c is None:
        raise ValidationError(f"No campaign #{campaign_id}")
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT COALESCE(SUM(amount_pence), 0) AS raised, "
            "COUNT(DISTINCT alumni_id) AS donors "
            "FROM alumni_donations WHERE campaign_id = ?",
            (campaign_id,)).fetchone()
        p = conn.execute(
            "SELECT COALESCE(SUM(amount_pence), 0) AS open "
            "FROM alumni_pledges "
            "WHERE campaign_id = ? AND status = 'Open'",
            (campaign_id,)).fetchone()
    return CampaignTotals(
        campaign_id=c.campaign_id, name=c.name,
        target_pence=c.target_pence,
        raised_pence=int(r["raised"]),
        pledged_open_pence=int(p["open"]),
        donor_count=int(r["donors"]))


# ══ Reporting & analytics ════════════════════════════════════════
#
# These functions are read-only and produce structured data the CLI
# and GUI can render or export. Where DfE / cohort definitions are
# concerned the constants below are the school's best-effort lookup
# table — adjust them in this module to match the spec for a given
# return year.


import csv as _csv         # noqa: E402  (kept near the reports for clarity)
import io as _io           # noqa: E402
import html as _html       # noqa: E402


RUSSELL_GROUP: tuple[str, ...] = (
    "University of Birmingham", "University of Bristol",
    "University of Cambridge", "Cardiff University",
    "Durham University", "University of Edinburgh",
    "University of Exeter", "University of Glasgow",
    "Imperial College London", "King's College London",
    "University of Leeds", "University of Liverpool",
    "London School of Economics", "University of Manchester",
    "Newcastle University", "University of Nottingham",
    "University of Oxford", "Queen Mary University of London",
    "Queen's University Belfast", "University of Sheffield",
    "University of Southampton", "University College London",
    "University of Warwick", "University of York",
)

OXBRIDGE: tuple[str, ...] = (
    "University of Oxford", "University of Cambridge",
)

# Pragmatic stand-in for the top third of UK HE providers by entry
# tariff. The HESA tariff bands change yearly; treat this list as a
# starting point and override in the constant for accurate stats.
TOP_THIRD_UNIVERSITIES: tuple[str, ...] = RUSSELL_GROUP + (
    "University of St Andrews", "University of Bath",
    "Lancaster University", "Loughborough University",
    "University of Sussex", "University of Reading",
    "University of Surrey",
)

# Map our destination_type to the DfE 16-18 destination category
# scheme (illustrative — confirm wording against the current
# specification before submission).
DFE_DESTINATION_CATEGORIES: dict[str, str] = {
    "University":     "Higher Education",
    "Apprenticeship": "Apprenticeship",
    "Further Study":  "Further Education",
    "Employment":     "Employment",
    "Self-Employed":  "Employment",
    "Gap Year":       "Other (incl gap year)",
    "Volunteering":   "Other (incl gap year)",
    "Unknown":        "Not known / unable to confirm",
    "Other":          "Other (incl gap year)",
}


def _contains_any(haystack: str | None,
                    needles: tuple[str, ...]) -> bool:
    if not haystack:
        return False
    s = haystack.lower()
    return any(n.lower() in s for n in needles)


# ── #33 KS5 destinations (DfE-style) ─────────────────────────────

def ks5_destinations_rows(*, leaving_year: str
                              ) -> list[dict[str, Any]]:
    """One row per alumnus for the given cohort. Columns map (best
    effort) to the DfE 16-18 destinations return. The shape is
    explicit (a list of dicts) so callers can write CSV / Excel /
    upload as they prefer."""
    init_db()
    if not _YEAR_RE.match(leaving_year):
        raise ValidationError(
            "Leaving year must be a 4-digit year (e.g. 2024)")
    rows = list_alumni(leaving_year=leaving_year)
    out: list[dict[str, Any]] = []
    for a in rows:
        category = DFE_DESTINATION_CATEGORIES.get(
            a.destination_type, "Not known / unable to confirm")
        out.append({
            "uln":                 a.original_student_id or "",
            "surname":             a.last_name,
            "forename":            a.first_name,
            "preferred_name":      a.preferred_name or "",
            "dob":                 a.dob or "",
            "gender":              a.gender or "",
            "leaving_year":        a.leaving_year or "",
            "leaving_date":        a.leaving_date or "",
            "destination_category": category,
            "destination_type":    a.destination_type,
            "destination_detail":  a.destination_detail or "",
            "country":             a.country or "",
            "region":              a.region or "",
            "consented_to_contact": "Y" if a.opt_in_contact else "N",
        })
    return out


def ks5_destinations_csv(*, leaving_year: str,
                           out_path: str | None = None) -> str:
    """Render the KS5 destinations rows as CSV. If ``out_path`` is
    given the file is written and the path returned; otherwise the
    CSV is returned as a string."""
    rows = ks5_destinations_rows(leaving_year=leaving_year)
    headers = list(rows[0].keys()) if rows else [
        "uln", "surname", "forename", "dob", "gender",
        "leaving_year", "destination_category",
        "destination_type", "destination_detail",
        "country", "region", "consented_to_contact",
    ]
    buf = _io.StringIO()
    w = _csv.DictWriter(buf, fieldnames=headers,
                          extrasaction="ignore",
                          quoting=_csv.QUOTE_MINIMAL)
    w.writeheader()
    for r in rows:
        w.writerow(r)
    _log_action("report.ks5_destinations_csv",
                  leaving_year=leaving_year, rows=len(rows),
                  out_path=str(out_path) if out_path else "(stdout)")
    if out_path:
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            f.write(buf.getvalue())
        return out_path
    return buf.getvalue()


# ── #34 Sustained destinations (1 / 3 / 5 years post-leaving) ────

@dataclass
class SustainedRow:
    alumni_id: int
    full_name: str
    leaving_year: str
    year_plus_1: str
    year_plus_3: str
    year_plus_5: str


def _activity_at(alumni_id: int, when: str) -> str:
    """Classify what the alumnus was doing at a particular date.
    Returns one of: 'In HE/FE', 'Employed', 'Mixed', 'Not known'."""
    init_db()
    with _connect() as conn:
        edu = conn.execute(
            "SELECT start_date, end_date, status "
            "FROM alumni_education WHERE alumni_id = ?",
            (alumni_id,)).fetchall()
        car = conn.execute(
            "SELECT start_date, end_date, is_current "
            "FROM alumni_career WHERE alumni_id = ?",
            (alumni_id,)).fetchall()
    in_study = False
    in_work  = False
    for r in edu:
        s = r["start_date"] or ""
        e = r["end_date"]   or ""
        st = r["status"] or ""
        if s and s > when:
            continue
        if e and e < when and st != "In Progress":
            continue
        in_study = True
        break
    for r in car:
        s = r["start_date"] or ""
        e = r["end_date"]   or ""
        if s and s > when:
            continue
        if r["is_current"]:
            in_work = True
            break
        if e and e < when:
            continue
        in_work = True
        break
    if in_study and in_work:
        return "Mixed"
    if in_study:
        return "In HE/FE"
    if in_work:
        return "Employed"
    return "Not known"


def sustained_destinations(*, leaving_year: str
                              ) -> list[SustainedRow]:
    init_db()
    if not _YEAR_RE.match(leaving_year):
        raise ValidationError(
            "Leaving year must be a 4-digit year (e.g. 2024)")
    base_year = int(leaving_year)
    rows = list_alumni(leaving_year=leaving_year)
    out: list[SustainedRow] = []
    for a in rows:
        out.append(SustainedRow(
            alumni_id=a.alumni_id, full_name=a.full_name,
            leaving_year=leaving_year,
            year_plus_1=_activity_at(a.alumni_id,
                                          f"{base_year + 1}-10-15"),
            year_plus_3=_activity_at(a.alumni_id,
                                          f"{base_year + 3}-10-15"),
            year_plus_5=_activity_at(a.alumni_id,
                                          f"{base_year + 5}-10-15"),
        ))
    return out


# ── #35 Cohort comparison (year-over-year destination mix) ───────

@dataclass
class CohortComparison:
    years: list[str]                       # sorted desc
    destinations: list[str]                # column order
    counts: dict[str, dict[str, int]]      # counts[year][dest]
    totals: dict[str, int]                 # totals[year]


def cohort_comparison() -> CohortComparison:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT leaving_year, destination_type, COUNT(*) AS n "
            "FROM alumni WHERE leaving_year IS NOT NULL "
            "GROUP BY leaving_year, destination_type"
        ).fetchall()
    counts: dict[str, dict[str, int]] = {}
    totals: dict[str, int] = {}
    years: set[str] = set()
    for r in rows:
        y = r["leaving_year"]
        d = r["destination_type"] or "Unknown"
        n = int(r["n"])
        counts.setdefault(y, {})[d] = n
        totals[y] = totals.get(y, 0) + n
        years.add(y)
    return CohortComparison(
        years=sorted(years, reverse=True),
        destinations=list(DESTINATION_TYPES),
        counts=counts, totals=totals)


# ── #36 University success rates ─────────────────────────────────

@dataclass
class UniversitySuccessRow:
    leaving_year: str
    uni_total: int
    russell: int
    oxbridge: int
    top_third: int


def university_success_rates() -> list[UniversitySuccessRow]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT leaving_year, destination_detail "
            "FROM alumni "
            "WHERE destination_type = 'University' "
            "AND leaving_year IS NOT NULL"
        ).fetchall()
    by_year: dict[str, dict[str, int]] = {}
    for r in rows:
        y = r["leaving_year"]
        d = r["destination_detail"] or ""
        s = by_year.setdefault(y, {"uni_total": 0, "russell": 0,
                                       "oxbridge": 0, "top_third": 0})
        s["uni_total"] += 1
        if _contains_any(d, RUSSELL_GROUP):
            s["russell"] += 1
        if _contains_any(d, OXBRIDGE):
            s["oxbridge"] += 1
        if _contains_any(d, TOP_THIRD_UNIVERSITIES):
            s["top_third"] += 1
    return [UniversitySuccessRow(
        leaving_year=y, uni_total=v["uni_total"],
        russell=v["russell"], oxbridge=v["oxbridge"],
        top_third=v["top_third"])
        for y, v in sorted(by_year.items(), reverse=True)]


# ── #37 Apprenticeship outcomes ──────────────────────────────────

_LEVEL_RE = re.compile(r"\blevel\s*(\d)\b", re.IGNORECASE)


@dataclass
class ApprenticeshipRow:
    leaving_year: str
    level: str            # "Level 2".."Level 7" or "Unknown"
    provider: str
    count: int


def apprenticeship_outcomes() -> list[ApprenticeshipRow]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT leaving_year, destination_detail "
            "FROM alumni WHERE destination_type = 'Apprenticeship' "
            "AND leaving_year IS NOT NULL"
        ).fetchall()
    bucket: dict[tuple[str, str, str], int] = {}
    for r in rows:
        y = r["leaving_year"]
        detail = (r["destination_detail"] or "").strip()
        m = _LEVEL_RE.search(detail)
        level = f"Level {m.group(1)}" if m else "Unknown"
        # Provider heuristic: the substring after " at " or " — "
        # or " - ", else the whole detail.
        provider = detail
        for sep in (" at ", " @ ", " — ", " - "):
            if sep in detail:
                provider = detail.split(sep, 1)[1].strip()
                break
        key = (y, level, provider or "Unknown")
        bucket[key] = bucket.get(key, 0) + 1
    return sorted(
        (ApprenticeshipRow(leaving_year=k[0], level=k[1],
                            provider=k[2], count=v)
         for k, v in bucket.items()),
        key=lambda r: (r.leaving_year, r.level, -r.count))


# ── #38 Disadvantage-gap (tagged vs cohort baseline) ─────────────

@dataclass
class GapRow:
    destination_type: str
    cohort_count: int
    cohort_pct: float
    tagged_count: int
    tagged_pct: float
    gap_pct: float       # tagged_pct - cohort_pct


def disadvantage_gap(*,
                      tag_name: str = "Bursary recipient",
                      leaving_year: str | None = None
                      ) -> list[GapRow]:
    init_db()
    args_y: list[Any] = []
    year_clause = ""
    if leaving_year:
        if not _YEAR_RE.match(leaving_year):
            raise ValidationError("Leaving year must be 4 digits")
        year_clause = "AND a.leaving_year = ?"
        args_y.append(leaving_year)
    with _connect() as conn:
        cohort = conn.execute(
            f"SELECT destination_type, COUNT(*) AS n FROM alumni a "
            f"WHERE 1 = 1 {year_clause} "
            "GROUP BY destination_type", args_y).fetchall()
        tagged = conn.execute(
            f"""SELECT a.destination_type, COUNT(*) AS n
                  FROM alumni a
                  JOIN alumni_tag_links l ON l.alumni_id = a.alumni_id
                  JOIN alumni_tags      t ON t.tag_id = l.tag_id
                 WHERE t.name = ? COLLATE NOCASE {year_clause}
              GROUP BY a.destination_type""",
            (tag_name, *args_y)).fetchall()
    c_total = sum(r["n"] for r in cohort) or 1
    t_total = sum(r["n"] for r in tagged) or 1
    c_map = {r["destination_type"]: int(r["n"]) for r in cohort}
    t_map = {r["destination_type"]: int(r["n"]) for r in tagged}
    out: list[GapRow] = []
    for d in DESTINATION_TYPES:
        c = c_map.get(d, 0)
        t = t_map.get(d, 0)
        c_pct = 100 * c / c_total
        t_pct = 100 * t / t_total
        out.append(GapRow(
            destination_type=d, cohort_count=c, cohort_pct=c_pct,
            tagged_count=t, tagged_pct=t_pct,
            gap_pct=t_pct - c_pct))
    return out


# ── #39 Geographic distribution ──────────────────────────────────

@dataclass
class GeoCell:
    country: str
    region: str
    count: int


def geographic_distribution() -> list[GeoCell]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT COALESCE(country, '—') AS c, "
            "COALESCE(region, '—') AS r, COUNT(*) AS n "
            "FROM alumni "
            "WHERE status NOT IN ('Deceased') "
            "AND (country IS NOT NULL OR current_location IS NOT NULL) "
            "GROUP BY c, r ORDER BY n DESC"
        ).fetchall()
    return [GeoCell(country=r["c"], region=r["r"], count=int(r["n"]))
              for r in rows]


# ── #40 Sector breakdown ─────────────────────────────────────────

@dataclass
class SectorRow:
    sector: str
    count: int
    pct: float


def sector_breakdown() -> list[SectorRow]:
    """Distribution of alumni by ``current_sector``. Falls back to
    the sector of the latest ``alumni_career.is_current`` row when
    the top-level field is empty."""
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            """SELECT COALESCE(NULLIF(a.current_sector, ''),
                                 (SELECT sector FROM alumni_career
                                  WHERE alumni_id = a.alumni_id
                                  AND is_current = 1
                                  ORDER BY career_id DESC LIMIT 1))
                       AS s,
                       COUNT(*) AS n
                FROM alumni a
               WHERE a.status NOT IN ('Deceased')
               GROUP BY s
               ORDER BY n DESC"""
        ).fetchall()
    total = sum(int(r["n"]) for r in rows) or 1
    return [SectorRow(sector=(r["s"] or "Unknown"),
                       count=int(r["n"]),
                       pct=100 * int(r["n"]) / total)
              for r in rows]


# ── #41 "Where are they now" HTML generator ──────────────────────

def alumni_with_public_consent() -> list[Alumnus]:
    """Alumni who are Active and have granted (and not withdrawn)
    the 'Photo Use' consent scope. Use this to decide who to
    publish on a public-facing site."""
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            """SELECT a.* FROM alumni a
               WHERE a.status = 'Active'
                 AND EXISTS (
                   SELECT 1 FROM alumni_consent c
                    WHERE c.alumni_id = a.alumni_id
                      AND c.scope = 'Photo Use'
                      AND c.withdrawn_at IS NULL)
               ORDER BY a.leaving_year DESC NULLS LAST,
                          a.last_name ASC""").fetchall()
    return [_row(r) for r in rows]


def _wan_profile_html(a: Alumnus) -> str:
    edu  = list_education(a.alumni_id)
    car  = list_career(a.alumni_id)
    ach  = list_achievements(a.alumni_id)

    def esc(x: str | None) -> str:
        return _html.escape(x or "")

    parts: list[str] = []
    parts.append(f"<!doctype html>\n<html lang='en'>\n<head>")
    parts.append("<meta charset='utf-8'>")
    parts.append(f"<title>{esc(a.display_name)}</title>")
    parts.append("<style>body{font-family:system-ui,sans-serif;"
                  "max-width:780px;margin:2em auto;padding:0 1em;"
                  "color:#222} h1{margin-bottom:.2em} .meta{color:#666;"
                  "margin-bottom:1.2em} h2{margin-top:1.4em;"
                  "border-bottom:1px solid #ccc;padding-bottom:2px} "
                  "ul{padding-left:1.2em}</style>")
    parts.append("</head>\n<body>")
    parts.append(f"<h1>{esc(a.display_name)}</h1>")
    bits = []
    if a.leaving_year:
        bits.append(f"Class of {esc(a.leaving_year)}")
    if a.current_role and a.current_employer:
        bits.append(f"{esc(a.current_role)} at "
                      f"{esc(a.current_employer)}")
    elif a.current_employer:
        bits.append(esc(a.current_employer))
    if a.current_sector:
        bits.append(esc(a.current_sector))
    if a.country or a.region:
        loc = ", ".join(filter(None, [a.region, a.country]))
        bits.append(esc(loc))
    if bits:
        parts.append(f"<div class='meta'>{' &middot; '.join(bits)}</div>")
    if a.photo_path:
        parts.append(f"<img src='{esc(a.photo_path)}' "
                      "alt='' style='max-width:240px;float:right;"
                      "margin:0 0 1em 1em;border-radius:6px'>")
    if a.bio:
        parts.append(f"<p>{esc(a.bio)}</p>")
    if edu:
        parts.append("<h2>Education</h2><ul>")
        for e in edu:
            line = f"<b>{esc(e.qualification)}</b>"
            if e.subject:
                line += f" {esc(e.subject)}"
            line += f" — {esc(e.institution)}"
            if e.grade:
                line += f" ({esc(e.grade)})"
            parts.append(f"<li>{line}</li>")
        parts.append("</ul>")
    if car:
        parts.append("<h2>Career</h2><ul>")
        for c in car:
            line = (f"<b>{esc(c.role)}</b> at {esc(c.employer)}")
            if c.is_current:
                line += " <small>(current)</small>"
            parts.append(f"<li>{line}</li>")
        parts.append("</ul>")
    if ach:
        parts.append("<h2>Achievements</h2><ul>")
        for x in ach:
            parts.append(f"<li>{esc(x.title)}</li>")
        parts.append("</ul>")
    parts.append("</body></html>\n")
    return "\n".join(parts)


def generate_where_are_they_now(out_dir: str | Path) -> int:
    """Write per-alumnus HTML profile pages plus an index page to
    ``out_dir``. Only alumni who are Active and have granted
    (and not withdrawn) the 'Photo Use' consent scope are
    included. Returns the number of profile pages written."""
    from pathlib import Path as _P
    base = _P(out_dir)
    base.mkdir(parents=True, exist_ok=True)
    rows = alumni_with_public_consent()
    index_items: list[str] = []
    for a in rows:
        fname = f"alumnus_{a.alumni_id}.html"
        (base / fname).write_text(_wan_profile_html(a),
                                       encoding="utf-8")
        meta = (a.current_role and a.current_employer
                  and f" — {_html.escape(a.current_role)} at "
                       f"{_html.escape(a.current_employer)}"
                  or "")
        index_items.append(
            f"<li><a href='{fname}'>"
            f"{_html.escape(a.display_name)}</a> "
            f"<small>({_html.escape(a.leaving_year or '—')})</small>"
            f"{meta}</li>")
    index_html = (
        "<!doctype html>\n<html><head><meta charset='utf-8'>"
        "<title>Where are they now?</title>"
        "<style>body{font-family:system-ui,sans-serif;max-width:780px;"
        "margin:2em auto;padding:0 1em} li{margin:.4em 0}</style>"
        "</head><body>"
        f"<h1>Where are they now? ({len(rows)} alumni)</h1>"
        "<ul>" + "\n".join(index_items) + "</ul>"
        "</body></html>"
    )
    (base / "index.html").write_text(index_html, encoding="utf-8")
    _log_action("report.where_are_they_now",
                  out_dir=str(out_dir), profiles=len(rows))
    return len(rows)


# ══ Operational quality ══════════════════════════════════════════

import json as _json  # noqa: E402


# ── Bulk CSV import ──────────────────────────────────────────────

# Header tokens our importer recognises (lower-case) → canonical
# alumnus field name. Used to suggest a default column mapping
# from the CSV's headers.
_IMPORT_FIELD_ALIASES: dict[str, str] = {
    "first_name": "first_name", "first name": "first_name",
    "forename": "first_name", "given name": "first_name",
    "last_name": "last_name", "last name": "last_name",
    "surname": "last_name", "family name": "last_name",
    "preferred_name": "preferred_name",
    "preferred name": "preferred_name",
    "pronouns": "pronouns",
    "gender": "gender",
    "dob": "dob", "date of birth": "dob",
    "leaving_year": "leaving_year", "leaving year": "leaving_year",
    "year of leaving": "leaving_year",
    "leaving_date": "leaving_date",
    "leaving date": "leaving_date",
    "leaving_reason": "leaving_reason",
    "leaving reason": "leaving_reason",
    "destination_type": "destination_type",
    "destination": "destination_type",
    "destination_detail": "destination_detail",
    "destination detail": "destination_detail",
    "current_role": "current_role", "current role": "current_role",
    "role": "current_role",
    "current_employer": "current_employer",
    "employer": "current_employer",
    "current_sector": "current_sector", "sector": "current_sector",
    "current_location": "current_location",
    "location": "current_location",
    "country": "country", "region": "region",
    "email": "email", "email address": "email",
    "phone": "phone", "telephone": "phone", "mobile": "phone",
    "address": "address",
    "linkedin": "linkedin", "linkedin url": "linkedin",
    "other_social": "other_social",
    "notes": "notes",
    "original_student_id": "original_student_id",
    "student id": "original_student_id",
    "uln": "original_student_id",
    "opt_in_contact": "opt_in_contact",
    "opt in": "opt_in_contact",
    "status": "status",
}


@dataclass
class ImportPreview:
    total_rows: int
    will_create: int
    will_skip: int            # blank / missing required
    will_update: int           # match on original_student_id
    errors: list[tuple[int, str]]   # (row_no, message)


def _import_resolve_value(value: Any, field: str) -> Any:
    """Coerce a CSV string into the right Python shape for one of
    our fields. Most are str-or-None; bools (opt_in_contact) get
    parsed from yes/no/1/0/true/false."""
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    if field == "opt_in_contact":
        return s.lower() in ("yes", "y", "true", "1", "on")
    return s


def parse_import_csv(source: str | Path) -> list[dict[str, str]]:
    """Read a CSV file from disk and return raw rows (str values)
    with whitespace stripped. The header row is used as keys."""
    rows: list[dict[str, str]] = []
    with open(source, encoding="utf-8-sig", newline="") as f:
        reader = _csv.DictReader(f)
        for r in reader:
            rows.append({(k or "").strip():
                          (v or "").strip()
                          for k, v in r.items()})
    return rows


def suggest_import_mapping(headers: list[str]) -> dict[str, str]:
    """Return a {csv_column: alumni_field} suggestion based on
    header aliasing. Unknown columns are omitted (caller picks)."""
    out: dict[str, str] = {}
    for h in headers:
        key = (h or "").strip().lower()
        if key in _IMPORT_FIELD_ALIASES:
            out[h] = _IMPORT_FIELD_ALIASES[key]
    return out


def _shape_import_payload(row: dict[str, str],
                            mapping: dict[str, str]
                            ) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for col, field in mapping.items():
        if not field:
            continue
        payload[field] = _import_resolve_value(row.get(col, ""), field)
    return payload


def preview_import(rows: list[dict[str, str]],
                     mapping: dict[str, str]) -> ImportPreview:
    """Dry-run an import. Validates every row through the same
    pipeline as :func:`create_alumnus` (so the user sees the same
    errors) but writes nothing."""
    init_db()
    will_create = will_update = will_skip = 0
    errors: list[tuple[int, str]] = []
    for i, row in enumerate(rows, 1):
        payload = _shape_import_payload(row, mapping)
        if not payload.get("first_name") or not payload.get("last_name"):
            will_skip += 1
            errors.append((i, "missing first_name / last_name"))
            continue
        try:
            _validate_payload(payload)
        except ValidationError as e:
            errors.append((i, str(e)))
            will_skip += 1
            continue
        oid = payload.get("original_student_id")
        existing = (get_alumnus_by_original_id(oid)
                      if oid else None)
        if existing:
            will_update += 1
        else:
            will_create += 1
    return ImportPreview(
        total_rows=len(rows), will_create=will_create,
        will_skip=will_skip, will_update=will_update, errors=errors)


@dataclass
class ImportResult:
    created: int
    updated: int
    skipped: int
    errors: list[tuple[int, str]]


def apply_import(rows: list[dict[str, str]],
                   mapping: dict[str, str], *,
                   actor: str | None = None) -> ImportResult:
    """Commit the rows from a previously-previewed import."""
    init_db()
    created = updated = skipped = 0
    errors: list[tuple[int, str]] = []
    for i, row in enumerate(rows, 1):
        payload = _shape_import_payload(row, mapping)
        if not payload.get("first_name") or not payload.get("last_name"):
            skipped += 1
            continue
        try:
            oid = payload.get("original_student_id")
            existing = (get_alumnus_by_original_id(oid)
                          if oid else None)
            if existing:
                update_alumnus(existing.alumni_id, payload,
                                 actor=actor)
                updated += 1
            else:
                create_alumnus(payload)
                created += 1
        except ValidationError as e:
            errors.append((i, str(e)))
            skipped += 1
    _log_action("alumnus.bulk_import", actor=actor,
                  created=created, updated=updated,
                  skipped=skipped, errors=len(errors),
                  level=logging.WARNING if errors else logging.INFO)
    return ImportResult(created=created, updated=updated,
                          skipped=skipped, errors=errors)


# ── Bulk export with column picker + consent-aware redaction ─────

# Field → sensitivity class lookup derived from EXPORT_FIELDS.
_EXPORT_SENS: dict[str, str] = {f: s for f, s in EXPORT_FIELDS}

REDACTION_PLACEHOLDER: str = "[redacted]"


def _redact(value: Any, field: str, alumnus: Alumnus,
              has_photo_consent: bool) -> Any:
    """Apply consent-aware redaction rules. Contact / sensitive
    fields are redacted when ``opt_in_contact`` is false or status
    is Opt-out. Public-tier fields (bio, photo_path) require active
    ``Photo Use`` consent."""
    if value in (None, ""):
        return ""
    sens = _EXPORT_SENS.get(field, "internal")
    if alumnus.status == "Opt-out":
        if sens in ("contact", "sensitive", "internal",
                     "professional", "name", "public"):
            return REDACTION_PLACEHOLDER
    if sens in ("contact", "sensitive") and not alumnus.opt_in_contact:
        return REDACTION_PLACEHOLDER
    if sens == "public" and not has_photo_consent:
        return REDACTION_PLACEHOLDER
    if sens == "internal":
        # Notes etc. — never exported.
        return REDACTION_PLACEHOLDER
    return value


def export_alumni_csv(*, out_path: str | Path | None = None,
                         columns: list[str] | None = None,
                         filters: dict[str, Any] | None = None,
                         respect_consent: bool = True
                         ) -> str:
    """Render alumni to CSV. ``columns`` defaults to every field in
    :data:`EXPORT_FIELDS` (in that order); pass a subset to limit
    output. When ``respect_consent`` is true (the default) PII
    fields are replaced with a placeholder for alumni who haven't
    opted in / have opted out (see :func:`_redact`).

    If ``out_path`` is provided the CSV is written there and the
    path is returned; otherwise the CSV string is returned."""
    init_db()
    if columns is None:
        columns = [f for f, _ in EXPORT_FIELDS]
    else:
        unknown = [c for c in columns if c not in _EXPORT_SENS]
        if unknown:
            raise ValidationError(
                f"Unknown column(s): {', '.join(unknown)}")
    rows = list_alumni(**(filters or {}))
    consent_cache: dict[int, bool] = {}
    buf = _io.StringIO()
    w = _csv.writer(buf, quoting=_csv.QUOTE_MINIMAL)
    w.writerow(columns)
    for a in rows:
        if respect_consent:
            if a.alumni_id not in consent_cache:
                consent_cache[a.alumni_id] = has_active_consent(
                    a.alumni_id, "Photo Use")
            photo_ok = consent_cache[a.alumni_id]
        else:
            photo_ok = True
        out_row: list[Any] = []
        for c in columns:
            raw = getattr(a, c, "")
            if isinstance(raw, bool):
                raw = "yes" if raw else "no"
            if respect_consent:
                out_row.append(_redact(raw, c, a, photo_ok))
            else:
                out_row.append(raw if raw is not None else "")
        w.writerow(out_row)
    _log_action("alumnus.bulk_export", rows=len(rows),
                  columns=len(columns),
                  respect_consent=respect_consent,
                  out_path=str(out_path) if out_path else "(stdout)")
    if out_path:
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            f.write(buf.getvalue())
        return str(out_path)
    return buf.getvalue()


# ── Saved searches ───────────────────────────────────────────────

@dataclass
class SavedSearch:
    search_id: int
    name: str
    description: str | None
    filters: dict[str, Any]
    owner_staff_id: str | None
    created_at: str


def _row_search(r: sqlite3.Row) -> SavedSearch:
    try:
        filters = _json.loads(r["filters_json"]) or {}
    except Exception:
        logger.warning("Corrupt filters_json for saved search #%s; "
                         "treating as empty",
                         r["search_id"], exc_info=True)
        filters = {}
    return SavedSearch(
        search_id=r["search_id"], name=r["name"],
        description=r["description"], filters=filters,
        owner_staff_id=r["owner_staff_id"],
        created_at=r["created_at"],
    )


# Filters that may appear in a saved-search payload (whitelist —
# anything else is rejected so saved searches stay portable).
_ALLOWED_SEARCH_KEYS: frozenset[str] = frozenset({
    "leaving_year", "destination_type", "status",
    "contactable_only", "search", "employer", "university",
    "sector", "country", "tag", "has_email", "include_deleted",
})


def save_search(name: str, filters: dict[str, Any], *,
                 description: str | None = None,
                 owner_staff_id: str | None = None,
                 replace: bool = False) -> SavedSearch:
    init_db()
    name = _require(name, "Search name").strip()
    bad = [k for k in filters if k not in _ALLOWED_SEARCH_KEYS]
    if bad:
        raise ValidationError(
            f"Unknown filter(s): {', '.join(bad)}")
    payload = _json.dumps(filters, sort_keys=True, default=str)
    with _connect() as conn:
        try:
            conn.execute(
                """INSERT INTO alumni_saved_searches
                       (name, description, filters_json,
                        owner_staff_id)
                   VALUES (?, ?, ?, ?)""",
                (name,
                 (description or "").strip() or None,
                 payload,
                 ((owner_staff_id or "").strip().upper() or None)))
        except sqlite3.IntegrityError:
            if not replace:
                raise ValidationError(
                    f"A saved search called '{name}' already "
                    "exists (use replace=True to overwrite)") \
                    from None
            conn.execute(
                """UPDATE alumni_saved_searches SET
                       description = ?, filters_json = ?,
                       owner_staff_id = ?
                   WHERE name = ?""",
                ((description or "").strip() or None,
                 payload,
                 ((owner_staff_id or "").strip().upper() or None),
                 name))
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_saved_searches WHERE name = ?",
            (name,)).fetchone()
    _log_action("saved_search.save", actor=owner_staff_id,
                  name=name, filters=str(filters))
    return _row_search(r)


def list_saved_searches() -> list[SavedSearch]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM alumni_saved_searches "
            "ORDER BY name COLLATE NOCASE").fetchall()
    return [_row_search(r) for r in rows]


def get_saved_search(name: str) -> SavedSearch | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM alumni_saved_searches "
            "WHERE name = ? COLLATE NOCASE",
            (name,)).fetchone()
    return _row_search(r) if r else None


def run_saved_search(name: str) -> list[Alumnus]:
    s = get_saved_search(name)
    if s is None:
        raise ValidationError(f"No saved search '{name}'")
    return list_alumni(**s.filters)


def delete_saved_search(name: str) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM alumni_saved_searches "
            "WHERE name = ? COLLATE NOCASE", (name,))
        conn.commit()
        deleted = cur.rowcount > 0
    if deleted:
        _log_action("saved_search.delete", name=name)
    return deleted


# ── Survey module ────────────────────────────────────────────────

# Recognised question types. Each entry maps to an alumnus field
# that may be auto-updated when the response comes in. ``None``
# means the answer is captured but not pushed back to the alumnus
# record.
SURVEY_QUESTION_TARGETS: dict[str, str | None] = {
    "current_role":     "current_role",
    "current_employer": "current_employer",
    "current_sector":   "current_sector",
    "current_location": "current_location",
    "country":          "country",
    "region":           "region",
    "email":            "email",
    "phone":            "phone",
    "linkedin":         "linkedin",
    "freeform":         None,
}


@dataclass
class Survey:
    survey_id: int
    name: str
    description: str | None
    questions: list[dict[str, Any]]
    status: str
    created_at: str


@dataclass
class SurveyInvitation:
    invitation_id: int
    survey_id: int
    alumni_id: int
    token: str
    sent_at: str | None
    completed_at: str | None
    expires_at: str


@dataclass
class SurveyResponse:
    response_id: int
    invitation_id: int
    answers: dict[str, Any]
    submitted_at: str


def _row_survey(r: sqlite3.Row) -> Survey:
    try:
        qs = _json.loads(r["questions_json"]) or []
    except Exception:
        logger.warning("Corrupt questions_json for survey #%s",
                         r["survey_id"], exc_info=True)
        qs = []
    return Survey(
        survey_id=r["survey_id"], name=r["name"],
        description=r["description"], questions=qs,
        status=r["status"], created_at=r["created_at"],
    )


def _row_invitation(r: sqlite3.Row) -> SurveyInvitation:
    return SurveyInvitation(
        invitation_id=r["invitation_id"], survey_id=r["survey_id"],
        alumni_id=r["alumni_id"], token=r["token"],
        sent_at=r["sent_at"], completed_at=r["completed_at"],
        expires_at=r["expires_at"],
    )


def _row_response(r: sqlite3.Row) -> SurveyResponse:
    try:
        ans = _json.loads(r["answers_json"]) or {}
    except Exception:
        logger.warning("Corrupt answers_json for response #%s",
                         r["response_id"], exc_info=True)
        ans = {}
    return SurveyResponse(
        response_id=r["response_id"],
        invitation_id=r["invitation_id"],
        answers=ans, submitted_at=r["submitted_at"],
    )


def create_survey(name: str,
                    questions: list[dict[str, Any]], *,
                    description: str | None = None) -> Survey:
    """Each question is a dict ``{"key": "...", "prompt": "...",
    "type": "current_role" | ... | "freeform"}``. Question
    ``type`` controls what (if anything) is written back to the
    alumnus profile when the response comes in."""
    init_db()
    name = _require(name, "Survey name").strip()
    if not questions:
        raise ValidationError("Survey needs at least one question")
    for i, q in enumerate(questions, 1):
        key = (q.get("key") or "").strip()
        if not key:
            raise ValidationError(
                f"Question {i} is missing 'key'")
        qtype = (q.get("type") or "freeform").strip()
        if qtype not in SURVEY_QUESTION_TARGETS:
            raise ValidationError(
                f"Question {i}: unknown type '{qtype}'. "
                f"Allowed: "
                f"{', '.join(sorted(SURVEY_QUESTION_TARGETS))}")
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO alumni_surveys
                   (name, description, questions_json, status)
               VALUES (?, ?, ?, 'Active')""",
            (name, (description or "").strip() or None,
             _json.dumps(questions)))
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_surveys WHERE survey_id = ?",
            (cur.lastrowid,)).fetchone()
    out = _row_survey(r)
    _log_action("survey.create", survey_id=out.survey_id,
                  name=out.name, questions=len(out.questions))
    return out


def get_survey(survey_id: int) -> Survey | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM alumni_surveys WHERE survey_id = ?",
            (survey_id,)).fetchone()
    return _row_survey(r) if r else None


def list_surveys() -> list[Survey]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM alumni_surveys ORDER BY created_at DESC"
        ).fetchall()
    return [_row_survey(r) for r in rows]


def close_survey(survey_id: int) -> Survey:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE alumni_surveys SET status = 'Closed' "
            "WHERE survey_id = ?", (survey_id,))
        conn.commit()
        if cur.rowcount == 0:
            raise ValidationError(f"No survey #{survey_id}")
    s = get_survey(survey_id)
    assert s is not None
    return s


def delete_survey(survey_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM alumni_surveys WHERE survey_id = ?",
            (survey_id,))
        conn.commit()
        return cur.rowcount > 0


def invite_to_survey(survey_id: int, alumni_id: int, *,
                       ttl_days: int = SURVEY_INVITATION_TTL_DAYS
                       ) -> SurveyInvitation:
    init_db()
    if get_survey(survey_id) is None:
        raise ValidationError(f"No survey #{survey_id}")
    tok = secrets.token_urlsafe(24)
    expires = (_dt.datetime.now()
                + _dt.timedelta(days=ttl_days)
                ).strftime("%Y-%m-%d %H:%M:%S")
    with _connect() as conn:
        _require_alumnus(conn, alumni_id)
        try:
            conn.execute(
                """INSERT INTO alumni_survey_invitations
                       (survey_id, alumni_id, token, expires_at)
                   VALUES (?, ?, ?, ?)""",
                (survey_id, alumni_id, tok, expires))
            conn.commit()
        except sqlite3.IntegrityError:
            raise ValidationError(
                f"Alumnus #{alumni_id} already invited to "
                f"survey #{survey_id}") from None
        r = conn.execute(
            "SELECT * FROM alumni_survey_invitations "
            "WHERE survey_id = ? AND alumni_id = ?",
            (survey_id, alumni_id)).fetchone()
    return _row_invitation(r)


def mark_invitation_sent(invitation_id: int) -> SurveyInvitation:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE alumni_survey_invitations "
            "SET sent_at = datetime('now') WHERE invitation_id = ?",
            (invitation_id,))
        conn.commit()
        if cur.rowcount == 0:
            raise ValidationError(
                f"No invitation #{invitation_id}")
        r = conn.execute(
            "SELECT * FROM alumni_survey_invitations "
            "WHERE invitation_id = ?",
            (invitation_id,)).fetchone()
    return _row_invitation(r)


def list_invitations(survey_id: int) -> list[SurveyInvitation]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM alumni_survey_invitations "
            "WHERE survey_id = ? ORDER BY invitation_id",
            (survey_id,)).fetchall()
    return [_row_invitation(r) for r in rows]


def send_survey_invitations(survey_id: int,
                              filters: dict[str, Any], *,
                              staff_id: str | None = None,
                              subject: str | None = None,
                              body_template: str | None = None
                              ) -> tuple[int, int]:
    """Invite every alumnus matching ``filters`` who has an email
    and ``opt_in_email``. Tokens are minted, an outgoing message is
    logged via the shared messages module, and each invitation is
    stamped ``sent_at``. Returns ``(sent, skipped)``."""
    init_db()
    survey = get_survey(survey_id)
    if survey is None:
        raise ValidationError(f"No survey #{survey_id}")
    rows = list_alumni(**filters)
    sent = skipped = 0
    msg = _messages_module()
    subject = subject or f"Help us update your alumni record: "\
                            f"{survey.name}"
    body_template = body_template or (
        "Hi {first_name},\n\n"
        "We're refreshing our alumni records and would love a quick "
        "update from you. Please open this link to fill in a short "
        "survey:\n\n"
        "{survey_link}\n\n"
        "Thanks,\nSixth-form alumni team")
    for a in rows:
        if not a.email:
            skipped += 1
            continue
        try:
            prefs = get_channel_prefs(a.alumni_id)
        except ValidationError:
            skipped += 1
            continue
        if not prefs.opt_in_email:
            skipped += 1
            continue
        try:
            inv = invite_to_survey(survey_id, a.alumni_id)
        except ValidationError:
            # Already invited — skip; existing token still works.
            skipped += 1
            continue
        link = f"alumni-survey/{inv.token}"
        body = _render(body_template, {
            "first_name":     a.first_name,
            "preferred_name": a.preferred_name or a.first_name,
            "last_name":      a.last_name,
            "survey_link":    link,
            "survey_name":    survey.name,
        })
        try:
            msg.create_message({
                "direction":  "Outgoing",
                "channel":    "Email",
                "category":   "General",
                "status":     "Sent",
                "subject":    subject,
                "body":       body,
                "alumni_id":  a.alumni_id,
                "to_name":    a.full_name,
                "to_address": a.email,
                "staff_id":   (staff_id or "").strip().upper()
                                or None,
                "sent_at":    msg._now(),
            })
            mark_invitation_sent(inv.invitation_id)
            sent += 1
        except Exception:
            logger.exception(
                "Failed to send survey invitation for alumnus #%d",
                a.alumni_id)
            skipped += 1
    _log_action("survey.invite_cohort", actor=staff_id,
                  survey_id=survey_id, sent=sent, skipped=skipped,
                  filters=str(filters))
    return sent, skipped


def validate_survey_token(token: str) -> SurveyInvitation | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM alumni_survey_invitations WHERE token = ?",
            (token,)).fetchone()
        if r is None:
            return None
        inv = _row_invitation(r)
    if inv.completed_at:
        return None
    now_iso = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if inv.expires_at < now_iso:
        return None
    return inv


def submit_survey_response(token: str,
                             answers: dict[str, Any], *,
                             apply_to_profile: bool = True,
                             actor: str | None = None
                             ) -> SurveyResponse:
    """Record a survey response and (optionally) push the
    well-known answers back into the alumnus profile. ``answers``
    keys must match a question ``key`` defined on the survey."""
    inv = validate_survey_token(token)
    if inv is None:
        raise ValidationError("Invalid or expired survey token")
    survey = get_survey(inv.survey_id)
    assert survey is not None
    init_db()
    with _connect() as conn:
        try:
            conn.execute(
                """INSERT INTO alumni_survey_responses
                       (invitation_id, answers_json)
                   VALUES (?, ?)""",
                (inv.invitation_id, _json.dumps(answers)))
        except sqlite3.IntegrityError:
            raise ValidationError(
                "Response already recorded for this invitation") \
                from None
        conn.execute(
            "UPDATE alumni_survey_invitations "
            "SET completed_at = datetime('now') "
            "WHERE invitation_id = ?", (inv.invitation_id,))
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_survey_responses "
            "WHERE invitation_id = ?",
            (inv.invitation_id,)).fetchone()

    if apply_to_profile:
        updates: dict[str, Any] = {}
        for q in survey.questions:
            qkey  = (q.get("key") or "").strip()
            qtype = (q.get("type") or "freeform").strip()
            target = SURVEY_QUESTION_TARGETS.get(qtype)
            if not target:
                continue
            if qkey in answers and answers[qkey] not in (None, ""):
                updates[target] = answers[qkey]
        if updates:
            try:
                update_alumnus(inv.alumni_id, updates,
                                 actor=actor or "survey")
            except ValidationError as e:
                logger.warning(
                    "Survey response for alumnus #%d failed to "
                    "apply: %s", inv.alumni_id, e)
    _log_action("survey.response_submitted",
                  actor=actor or "survey",
                  alumni_id=inv.alumni_id,
                  survey_id=inv.survey_id,
                  invitation_id=inv.invitation_id,
                  applied_to_profile=apply_to_profile)
    return _row_response(r)


def list_survey_responses(survey_id: int
                             ) -> list[SurveyResponse]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT r.* FROM alumni_survey_responses r "
            "JOIN alumni_survey_invitations i "
            "  ON i.invitation_id = r.invitation_id "
            "WHERE i.survey_id = ? "
            "ORDER BY r.submitted_at DESC",
            (survey_id,)).fetchall()
    return [_row_response(r) for r in rows]


@dataclass
class SurveyStats:
    survey_id: int
    invited: int
    sent: int
    completed: int


def survey_stats(survey_id: int) -> SurveyStats:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT COUNT(*) AS invited, "
            "       COUNT(sent_at) AS sent, "
            "       COUNT(completed_at) AS completed "
            "FROM alumni_survey_invitations WHERE survey_id = ?",
            (survey_id,)).fetchone()
    return SurveyStats(
        survey_id=survey_id, invited=int(r["invited"]),
        sent=int(r["sent"]), completed=int(r["completed"]))


# ════════════════════════════════════════════════════════════════════
# Engagement extensions — social handles, connections, chapters,
# engagement score, re-engagement worklist, milestones, lost-contact
# queue, and public directory listing.
# ════════════════════════════════════════════════════════════════════

_SCHEMA_ENGAGEMENT = """
CREATE TABLE IF NOT EXISTS alumni_social_handles (
    handle_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    alumni_id   INTEGER NOT NULL,
    platform    TEXT NOT NULL,
    handle      TEXT NOT NULL,
    url         TEXT,
    verified    INTEGER NOT NULL DEFAULT 0,
    verified_at TEXT,
    notes       TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(alumni_id, platform, handle),
    FOREIGN KEY (alumni_id) REFERENCES alumni(alumni_id)
        ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_asoc_alumni
    ON alumni_social_handles(alumni_id);
CREATE INDEX IF NOT EXISTS idx_asoc_platform
    ON alumni_social_handles(platform);

CREATE TABLE IF NOT EXISTS alumni_connections (
    connection_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    a_id           INTEGER NOT NULL,
    b_id           INTEGER NOT NULL,
    kind           TEXT NOT NULL DEFAULT 'Friend',
    since          TEXT,
    notes          TEXT,
    created_at     TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(a_id, b_id),
    CHECK (a_id < b_id),
    FOREIGN KEY (a_id) REFERENCES alumni(alumni_id) ON DELETE CASCADE,
    FOREIGN KEY (b_id) REFERENCES alumni(alumni_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_acon_a ON alumni_connections(a_id);
CREATE INDEX IF NOT EXISTS idx_acon_b ON alumni_connections(b_id);

CREATE TABLE IF NOT EXISTS alumni_chapters (
    chapter_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE COLLATE NOCASE,
    kind        TEXT NOT NULL DEFAULT 'Regional',
    region      TEXT,
    description TEXT,
    status      TEXT NOT NULL DEFAULT 'Active',
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS alumni_chapter_members (
    chapter_id  INTEGER NOT NULL,
    alumni_id   INTEGER NOT NULL,
    role        TEXT NOT NULL DEFAULT 'Member',
    joined_on   TEXT,
    left_on     TEXT,
    PRIMARY KEY (chapter_id, alumni_id),
    FOREIGN KEY (chapter_id) REFERENCES alumni_chapters(chapter_id)
        ON DELETE CASCADE,
    FOREIGN KEY (alumni_id)  REFERENCES alumni(alumni_id)
        ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_achm_alumni
    ON alumni_chapter_members(alumni_id);
"""


def _init_engagement_schema() -> None:
    """Idempotently install the engagement-extension tables. Called
    from :func:`init_db` after the main schema. Splitting it out keeps
    the original ``_SCHEMA`` constant unchanged so existing migrations
    keep working."""
    with _connect() as conn:
        conn.executescript(_SCHEMA_ENGAGEMENT)


# Re-wrap init_db so the engagement schema is also installed. The
# original init_db sets _DB_READY=True on first run; we wrap rather
# than edit so the original behaviour stays a single source of truth.
_original_init_db = init_db


def init_db() -> None:  # type: ignore[no-redef]
    already = _DB_READY
    _original_init_db()
    if not already:
        _init_engagement_schema()


# ── #1 Social handles ─────────────────────────────────────────────

@dataclass
class SocialHandle:
    handle_id: int
    alumni_id: int
    platform: str
    handle: str
    url: str | None
    verified: bool
    verified_at: str | None
    notes: str | None
    created_at: str


def _row_social(r: sqlite3.Row) -> SocialHandle:
    return SocialHandle(
        handle_id=r["handle_id"], alumni_id=r["alumni_id"],
        platform=r["platform"], handle=r["handle"],
        url=r["url"],
        verified=bool(r["verified"]),
        verified_at=r["verified_at"],
        notes=r["notes"], created_at=r["created_at"])


def add_social_handle(alumni_id: int, platform: str, handle: str, *,
                        url: str | None = None,
                        verified: bool = False,
                        notes: str | None = None,
                        actor: str | None = None) -> SocialHandle:
    init_db()
    platform = (platform or "").strip()
    handle = (handle or "").strip()
    if not platform:
        raise ValidationError("Platform is required")
    if platform not in SOCIAL_PLATFORMS:
        raise ValidationError(
            f"Platform must be one of: {', '.join(SOCIAL_PLATFORMS)}")
    if not handle:
        raise ValidationError("Handle is required")
    verified_at = (
        _dt.datetime.now().isoformat(timespec="seconds")
        if verified else None)
    with _connect() as conn:
        _require_alumnus(conn, alumni_id)
        try:
            cur = conn.execute(
                """INSERT INTO alumni_social_handles
                       (alumni_id, platform, handle, url, verified,
                        verified_at, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (alumni_id, platform, handle,
                 (url or "").strip() or None,
                 1 if verified else 0, verified_at,
                 (notes or "").strip() or None))
        except sqlite3.IntegrityError as exc:
            raise ValidationError(
                "That platform/handle is already recorded for this "
                "alumnus") from exc
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_social_handles WHERE handle_id = ?",
            (cur.lastrowid,)).fetchone()
    _log_action("social.add", actor=actor, alumni_id=alumni_id,
                  platform=platform, handle=handle, verified=verified)
    return _row_social(r)


def list_social_handles(alumni_id: int) -> list[SocialHandle]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM alumni_social_handles "
            "WHERE alumni_id = ? "
            "ORDER BY platform COLLATE NOCASE, handle_id",
            (alumni_id,)).fetchall()
    return [_row_social(r) for r in rows]


def update_social_handle(handle_id: int,
                           payload: dict[str, Any], *,
                           actor: str | None = None) -> SocialHandle:
    init_db()
    fields: dict[str, Any] = {}
    if "url" in payload:
        fields["url"] = (payload["url"] or "").strip() or None
    if "handle" in payload:
        h = (payload["handle"] or "").strip()
        if not h:
            raise ValidationError("Handle is required")
        fields["handle"] = h
    if "notes" in payload:
        fields["notes"] = (payload["notes"] or "").strip() or None
    if "verified" in payload:
        fields["verified"] = 1 if payload["verified"] else 0
        fields["verified_at"] = (
            _dt.datetime.now().isoformat(timespec="seconds")
            if payload["verified"] else None)
    if not fields:
        with _connect() as conn:
            r = conn.execute(
                "SELECT * FROM alumni_social_handles WHERE handle_id=?",
                (handle_id,)).fetchone()
        if r is None:
            raise ValidationError(f"No social handle #{handle_id}")
        return _row_social(r)
    sets = ", ".join(f"{k} = ?" for k in fields)
    vals = list(fields.values()) + [handle_id]
    with _connect() as conn:
        cur = conn.execute(
            f"UPDATE alumni_social_handles SET {sets} "
            f"WHERE handle_id = ?", vals)
        if cur.rowcount == 0:
            raise ValidationError(f"No social handle #{handle_id}")
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_social_handles WHERE handle_id = ?",
            (handle_id,)).fetchone()
    _log_action("social.update", actor=actor,
                  handle_id=handle_id, **{k: v for k, v in fields.items()
                                          if k != "verified_at"})
    return _row_social(r)


def verify_social_handle(handle_id: int, *,
                          actor: str | None = None) -> SocialHandle:
    return update_social_handle(handle_id, {"verified": True},
                                  actor=actor)


def delete_social_handle(handle_id: int, *,
                           actor: str | None = None) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM alumni_social_handles WHERE handle_id = ?",
            (handle_id,))
        conn.commit()
    if cur.rowcount:
        _log_action("social.delete", actor=actor, handle_id=handle_id)
    return cur.rowcount > 0


# ── #2 Connections graph ──────────────────────────────────────────

@dataclass
class Connection:
    connection_id: int
    a_id: int
    b_id: int
    kind: str
    since: str | None
    notes: str | None
    created_at: str


def _row_connection(r: sqlite3.Row) -> Connection:
    return Connection(
        connection_id=r["connection_id"],
        a_id=r["a_id"], b_id=r["b_id"],
        kind=r["kind"], since=r["since"],
        notes=r["notes"], created_at=r["created_at"])


def _normalise_pair(a: int, b: int) -> tuple[int, int]:
    if a == b:
        raise ValidationError(
            "An alumnus cannot be connected to themselves")
    return (a, b) if a < b else (b, a)


def connect_alumni(alumni_a: int, alumni_b: int, *,
                    kind: str = "Friend",
                    since: str | None = None,
                    notes: str | None = None,
                    actor: str | None = None) -> Connection:
    init_db()
    if kind not in CONNECTION_KINDS:
        raise ValidationError(
            f"Kind must be one of: {', '.join(CONNECTION_KINDS)}")
    lo, hi = _normalise_pair(alumni_a, alumni_b)
    since_iso = _validate_date(since, "Since", required=False)
    with _connect() as conn:
        _require_alumnus(conn, lo)
        _require_alumnus(conn, hi)
        existing = conn.execute(
            "SELECT * FROM alumni_connections "
            "WHERE a_id = ? AND b_id = ?", (lo, hi)).fetchone()
        if existing:
            return _row_connection(existing)
        cur = conn.execute(
            """INSERT INTO alumni_connections
                   (a_id, b_id, kind, since, notes)
               VALUES (?, ?, ?, ?, ?)""",
            (lo, hi, kind, since_iso,
             (notes or "").strip() or None))
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_connections WHERE connection_id = ?",
            (cur.lastrowid,)).fetchone()
    _log_action("connection.create", actor=actor,
                  a_id=lo, b_id=hi, kind=kind)
    return _row_connection(r)


def disconnect_alumni(alumni_a: int, alumni_b: int, *,
                       actor: str | None = None) -> bool:
    init_db()
    lo, hi = _normalise_pair(alumni_a, alumni_b)
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM alumni_connections "
            "WHERE a_id = ? AND b_id = ?", (lo, hi))
        conn.commit()
    if cur.rowcount:
        _log_action("connection.delete", actor=actor,
                      a_id=lo, b_id=hi)
    return cur.rowcount > 0


def list_connections(alumni_id: int) -> list[tuple[Connection, Alumnus]]:
    """Return all connections involving ``alumni_id``, each paired with
    the other party's Alumnus row."""
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            """SELECT c.*,
                      CASE WHEN c.a_id = ? THEN c.b_id
                           ELSE c.a_id END AS other_id
                 FROM alumni_connections c
                WHERE c.a_id = ? OR c.b_id = ?
                ORDER BY c.created_at DESC""",
            (alumni_id, alumni_id, alumni_id)).fetchall()
        out: list[tuple[Connection, Alumnus]] = []
        for r in rows:
            other = conn.execute(
                "SELECT * FROM alumni WHERE alumni_id = ?",
                (r["other_id"],)).fetchone()
            if other is None:
                continue
            out.append((_row_connection(r), _row(other)))
    return out


def _neighbours(conn: sqlite3.Connection, alumni_id: int) -> set[int]:
    rows = conn.execute(
        "SELECT a_id, b_id FROM alumni_connections "
        "WHERE a_id = ? OR b_id = ?",
        (alumni_id, alumni_id)).fetchall()
    out: set[int] = set()
    for r in rows:
        out.add(r["b_id"] if r["a_id"] == alumni_id else r["a_id"])
    return out


def mutuals_of(alumni_a: int, alumni_b: int) -> list[Alumnus]:
    init_db()
    with _connect() as conn:
        common = _neighbours(conn, alumni_a) & _neighbours(conn, alumni_b)
        if not common:
            return []
        placeholders = ",".join("?" * len(common))
        rows = conn.execute(
            f"SELECT * FROM alumni WHERE alumni_id IN ({placeholders}) "
            "ORDER BY last_name, first_name", tuple(common)).fetchall()
    return [_row(r) for r in rows]


def degrees_between(alumni_a: int, alumni_b: int, *,
                      max_depth: int = 6) -> int | None:
    """BFS over the undirected connection graph. Returns the number of
    hops separating the two alumni, or ``None`` if no path is found
    within ``max_depth``."""
    init_db()
    if alumni_a == alumni_b:
        return 0
    visited: set[int] = {alumni_a}
    frontier: set[int] = {alumni_a}
    with _connect() as conn:
        for depth in range(1, max_depth + 1):
            nxt: set[int] = set()
            for node in frontier:
                for n in _neighbours(conn, node):
                    if n in visited:
                        continue
                    if n == alumni_b:
                        return depth
                    nxt.add(n)
            if not nxt:
                return None
            visited |= nxt
            frontier = nxt
    return None


# ── #3 Chapters ───────────────────────────────────────────────────

CHAPTER_KINDS: tuple[str, ...] = (
    "Regional", "Industry", "Cohort", "Affinity", "Other",
)


@dataclass
class Chapter:
    chapter_id: int
    name: str
    kind: str
    region: str | None
    description: str | None
    status: str
    created_at: str


@dataclass
class ChapterMembership:
    chapter_id: int
    alumni_id: int
    role: str
    joined_on: str | None
    left_on: str | None


def _row_chapter(r: sqlite3.Row) -> Chapter:
    return Chapter(
        chapter_id=r["chapter_id"], name=r["name"],
        kind=r["kind"], region=r["region"],
        description=r["description"], status=r["status"],
        created_at=r["created_at"])


def _row_chapter_member(r: sqlite3.Row) -> ChapterMembership:
    return ChapterMembership(
        chapter_id=r["chapter_id"], alumni_id=r["alumni_id"],
        role=r["role"], joined_on=r["joined_on"],
        left_on=r["left_on"])


def create_chapter(name: str, *, kind: str = "Regional",
                     region: str | None = None,
                     description: str | None = None,
                     actor: str | None = None) -> Chapter:
    init_db()
    name = (name or "").strip()
    if not name:
        raise ValidationError("Chapter name is required")
    if kind not in CHAPTER_KINDS:
        raise ValidationError(
            f"Kind must be one of: {', '.join(CHAPTER_KINDS)}")
    with _connect() as conn:
        try:
            cur = conn.execute(
                """INSERT INTO alumni_chapters
                       (name, kind, region, description)
                   VALUES (?, ?, ?, ?)""",
                (name, kind,
                 (region or "").strip() or None,
                 (description or "").strip() or None))
        except sqlite3.IntegrityError as exc:
            raise ValidationError(
                f"A chapter named {name!r} already exists") from exc
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_chapters WHERE chapter_id = ?",
            (cur.lastrowid,)).fetchone()
    _log_action("chapter.create", actor=actor, name=name, kind=kind)
    return _row_chapter(r)


def list_chapters(*, status: str | None = None,
                    kind: str | None = None) -> list[Chapter]:
    init_db()
    sql = "SELECT * FROM alumni_chapters WHERE 1=1"
    params: list[Any] = []
    if status:
        sql += " AND status = ?"
        params.append(status)
    if kind:
        sql += " AND kind = ?"
        params.append(kind)
    sql += " ORDER BY name COLLATE NOCASE"
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_chapter(r) for r in rows]


def get_chapter(chapter_id: int) -> Chapter | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM alumni_chapters WHERE chapter_id = ?",
            (chapter_id,)).fetchone()
    return _row_chapter(r) if r else None


def update_chapter(chapter_id: int, payload: dict[str, Any], *,
                     actor: str | None = None) -> Chapter:
    init_db()
    fields: dict[str, Any] = {}
    for key in ("name", "region", "description"):
        if key in payload:
            val = (payload[key] or "").strip()
            if key == "name" and not val:
                raise ValidationError("Chapter name is required")
            fields[key] = val or None
    if "kind" in payload:
        if payload["kind"] not in CHAPTER_KINDS:
            raise ValidationError(
                f"Kind must be one of: {', '.join(CHAPTER_KINDS)}")
        fields["kind"] = payload["kind"]
    if "status" in payload:
        fields["status"] = payload["status"]
    if not fields:
        existing = get_chapter(chapter_id)
        if not existing:
            raise ValidationError(f"No chapter #{chapter_id}")
        return existing
    sets = ", ".join(f"{k} = ?" for k in fields)
    with _connect() as conn:
        cur = conn.execute(
            f"UPDATE alumni_chapters SET {sets} WHERE chapter_id = ?",
            list(fields.values()) + [chapter_id])
        if cur.rowcount == 0:
            raise ValidationError(f"No chapter #{chapter_id}")
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_chapters WHERE chapter_id = ?",
            (chapter_id,)).fetchone()
    _log_action("chapter.update", actor=actor,
                  chapter_id=chapter_id, **fields)
    return _row_chapter(r)


def delete_chapter(chapter_id: int, *,
                     actor: str | None = None) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM alumni_chapters WHERE chapter_id = ?",
            (chapter_id,))
        conn.commit()
    if cur.rowcount:
        _log_action("chapter.delete", actor=actor,
                      chapter_id=chapter_id)
    return cur.rowcount > 0


def add_chapter_member(chapter_id: int, alumni_id: int, *,
                         role: str = "Member",
                         joined_on: str | None = None,
                         actor: str | None = None
                         ) -> ChapterMembership:
    init_db()
    if role not in CHAPTER_ROLES:
        raise ValidationError(
            f"Role must be one of: {', '.join(CHAPTER_ROLES)}")
    joined_iso = _validate_date(joined_on, "Joined on", required=False)
    with _connect() as conn:
        _require_alumnus(conn, alumni_id)
        existing = conn.execute(
            "SELECT * FROM alumni_chapter_members "
            "WHERE chapter_id = ? AND alumni_id = ?",
            (chapter_id, alumni_id)).fetchone()
        if existing:
            conn.execute(
                "UPDATE alumni_chapter_members "
                "SET role = ?, joined_on = COALESCE(?, joined_on), "
                "    left_on = NULL "
                "WHERE chapter_id = ? AND alumni_id = ?",
                (role, joined_iso, chapter_id, alumni_id))
        else:
            conn.execute(
                """INSERT INTO alumni_chapter_members
                       (chapter_id, alumni_id, role, joined_on)
                   VALUES (?, ?, ?, ?)""",
                (chapter_id, alumni_id, role, joined_iso))
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_chapter_members "
            "WHERE chapter_id = ? AND alumni_id = ?",
            (chapter_id, alumni_id)).fetchone()
    _log_action("chapter.add_member", actor=actor,
                  chapter_id=chapter_id, alumni_id=alumni_id, role=role)
    return _row_chapter_member(r)


def set_chapter_role(chapter_id: int, alumni_id: int, role: str, *,
                       actor: str | None = None) -> ChapterMembership:
    init_db()
    if role not in CHAPTER_ROLES:
        raise ValidationError(
            f"Role must be one of: {', '.join(CHAPTER_ROLES)}")
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE alumni_chapter_members SET role = ? "
            "WHERE chapter_id = ? AND alumni_id = ?",
            (role, chapter_id, alumni_id))
        if cur.rowcount == 0:
            raise ValidationError("Member not in chapter")
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_chapter_members "
            "WHERE chapter_id = ? AND alumni_id = ?",
            (chapter_id, alumni_id)).fetchone()
    _log_action("chapter.set_role", actor=actor,
                  chapter_id=chapter_id, alumni_id=alumni_id, role=role)
    return _row_chapter_member(r)


def remove_chapter_member(chapter_id: int, alumni_id: int, *,
                            when: str | None = None,
                            actor: str | None = None) -> bool:
    """Soft-removes by stamping ``left_on``. Pass ``when=None`` for
    today. Use :func:`purge_chapter_member` to hard-delete."""
    init_db()
    left_iso = (
        _validate_date(when, "Left on", required=False)
        or _dt.date.today().isoformat())
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE alumni_chapter_members SET left_on = ? "
            "WHERE chapter_id = ? AND alumni_id = ? AND left_on IS NULL",
            (left_iso, chapter_id, alumni_id))
        conn.commit()
    if cur.rowcount:
        _log_action("chapter.remove_member", actor=actor,
                      chapter_id=chapter_id, alumni_id=alumni_id)
    return cur.rowcount > 0


def purge_chapter_member(chapter_id: int, alumni_id: int, *,
                           actor: str | None = None) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM alumni_chapter_members "
            "WHERE chapter_id = ? AND alumni_id = ?",
            (chapter_id, alumni_id))
        conn.commit()
    if cur.rowcount:
        _log_action("chapter.purge_member", actor=actor,
                      chapter_id=chapter_id, alumni_id=alumni_id)
    return cur.rowcount > 0


def list_chapter_members(chapter_id: int, *,
                           include_left: bool = False
                           ) -> list[tuple[ChapterMembership, Alumnus]]:
    init_db()
    sql = ("SELECT m.*, a.* FROM alumni_chapter_members m "
            "JOIN alumni a ON a.alumni_id = m.alumni_id "
            "WHERE m.chapter_id = ?")
    if not include_left:
        sql += " AND m.left_on IS NULL"
    sql += " ORDER BY a.last_name, a.first_name"
    with _connect() as conn:
        rows = conn.execute(sql, (chapter_id,)).fetchall()
    out: list[tuple[ChapterMembership, Alumnus]] = []
    for r in rows:
        out.append((_row_chapter_member(r), _row(r)))
    return out


def list_chapters_for(alumni_id: int, *,
                        include_left: bool = False
                        ) -> list[tuple[ChapterMembership, Chapter]]:
    init_db()
    sql = ("SELECT m.*, c.* FROM alumni_chapter_members m "
            "JOIN alumni_chapters c ON c.chapter_id = m.chapter_id "
            "WHERE m.alumni_id = ?")
    if not include_left:
        sql += " AND m.left_on IS NULL"
    sql += " ORDER BY c.name COLLATE NOCASE"
    with _connect() as conn:
        rows = conn.execute(sql, (alumni_id,)).fetchall()
    out: list[tuple[ChapterMembership, Chapter]] = []
    for r in rows:
        out.append((_row_chapter_member(r), _row_chapter(r)))
    return out


# ── #4 Engagement score ──────────────────────────────────────────

@dataclass
class EngagementScore:
    alumni_id: int
    score: float
    comms_opens: int
    events_attended: int
    donations_count: int
    donation_total_pence: int
    volunteer_hours: float
    months_since_contact: int | None
    decay: float


# Weights tuned for typical usage. Adjust here, not at call sites.
_ENG_WEIGHTS = {
    "comms_open":       1.0,
    "event_attended":   8.0,
    "rsvp_yes":         3.0,
    "donation_each":    6.0,
    "donation_per_£10": 0.5,
    "volunteer_per_hr": 2.0,
    "mentor_active":    10.0,
    "speaker_profile":  5.0,
    "wxp_offer":        4.0,
}


def _months_between(iso_date: str | None,
                      now: _dt.date | None = None) -> int | None:
    if not iso_date:
        return None
    try:
        d = _dt.date.fromisoformat(iso_date[:10])
    except ValueError:
        return None
    now = now or _dt.date.today()
    return (now.year - d.year) * 12 + (now.month - d.month)


def compute_engagement_score(alumni_id: int) -> EngagementScore:
    """Composite engagement score for one alumnus.

    Aggregates communications opens, event attendance and RSVPs,
    donation count and total, volunteer hours, active mentorship,
    speaker profile, and work-experience offers. Multiplies the raw
    sum by a recency-decay factor based on ``last_contacted``."""
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT last_contacted FROM alumni WHERE alumni_id = ?",
            (alumni_id,)).fetchone()
        if r is None:
            raise ValidationError(f"No alumnus #{alumni_id}")
        last_contacted = r["last_contacted"]
        events_attended = int(conn.execute(
            "SELECT COUNT(*) FROM alumni_event_rsvps "
            "WHERE alumni_id = ? AND attended = 1",
            (alumni_id,)).fetchone()[0])
        rsvp_yes = int(conn.execute(
            "SELECT COUNT(*) FROM alumni_event_rsvps "
            "WHERE alumni_id = ? AND status = 'Yes' AND attended = 0",
            (alumni_id,)).fetchone()[0])
        don = conn.execute(
            "SELECT COUNT(*) AS n, COALESCE(SUM(amount_pence),0) AS t "
            "FROM alumni_donations WHERE alumni_id = ?",
            (alumni_id,)).fetchone()
        donations_count = int(don["n"])
        donation_total = int(don["t"])
        vol_hours = float(conn.execute(
            "SELECT COALESCE(SUM(hours),0) FROM alumni_volunteer_hours "
            "WHERE alumni_id = ?", (alumni_id,)).fetchone()[0])
        active_mentor = int(conn.execute(
            "SELECT COUNT(*) FROM alumni_mentorships "
            "WHERE mentor_alumni_id = ? AND status = 'Active'",
            (alumni_id,)).fetchone()[0])
        speaker = int(conn.execute(
            "SELECT COUNT(*) FROM alumni_speakers WHERE alumni_id = ?",
            (alumni_id,)).fetchone()[0])
        wxp = int(conn.execute(
            "SELECT COUNT(*) FROM alumni_work_exp_offers "
            "WHERE alumni_id = ? AND status = 'Open'",
            (alumni_id,)).fetchone()[0])
    # Comms-open count comes from the shared messages module if it
    # has the corresponding bookkeeping; otherwise treat as 0.
    comms_opens = _count_comms_opens(alumni_id)
    raw = (
        comms_opens     * _ENG_WEIGHTS["comms_open"]
        + events_attended * _ENG_WEIGHTS["event_attended"]
        + rsvp_yes        * _ENG_WEIGHTS["rsvp_yes"]
        + donations_count * _ENG_WEIGHTS["donation_each"]
        + (donation_total / 1000.0) * _ENG_WEIGHTS["donation_per_£10"]
        + vol_hours       * _ENG_WEIGHTS["volunteer_per_hr"]
        + active_mentor   * _ENG_WEIGHTS["mentor_active"]
        + speaker         * _ENG_WEIGHTS["speaker_profile"]
        + wxp             * _ENG_WEIGHTS["wxp_offer"])
    months = _months_between(last_contacted)
    if months is None:
        decay = 0.5  # never contacted — heavy decay
    elif months <= 3:
        decay = 1.0
    elif months <= 12:
        decay = 0.85
    elif months <= 24:
        decay = 0.6
    elif months <= 48:
        decay = 0.35
    else:
        decay = 0.15
    return EngagementScore(
        alumni_id=alumni_id,
        score=round(raw * decay, 2),
        comms_opens=comms_opens,
        events_attended=events_attended,
        donations_count=donations_count,
        donation_total_pence=donation_total,
        volunteer_hours=vol_hours,
        months_since_contact=months,
        decay=decay)


def _count_comms_opens(alumni_id: int) -> int:
    """Pulled out so it stays defensive: the shared ``messages`` table
    may not have an ``opened_at`` column on older deployments."""
    try:
        msgs = _messages_module()
    except Exception:
        return 0
    db_path = getattr(msgs, "DB_PATH", None)
    if not db_path:
        return 0
    try:
        with sqlite3.connect(str(db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cols = {row[1] for row in conn.execute(
                "PRAGMA table_info(messages)").fetchall()}
            if "opened_at" not in cols or "alumni_id" not in cols:
                return 0
            r = conn.execute(
                "SELECT COUNT(*) FROM messages "
                "WHERE alumni_id = ? AND opened_at IS NOT NULL",
                (alumni_id,)).fetchone()
            return int(r[0]) if r else 0
    except sqlite3.Error:
        return 0


def engagement_leaderboard(*, limit: int = 50,
                              leaving_year: str | None = None
                              ) -> list[EngagementScore]:
    init_db()
    sql = "SELECT alumni_id FROM alumni WHERE status = 'Active'"
    params: list[Any] = []
    if leaving_year:
        sql += " AND leaving_year = ?"
        params.append(leaving_year)
    with _connect() as conn:
        ids = [r["alumni_id"] for r in conn.execute(sql, params).fetchall()]
    scored = [compute_engagement_score(a) for a in ids]
    scored.sort(key=lambda s: s.score, reverse=True)
    return scored[:limit]


# ── #5 Re-engagement worklist ─────────────────────────────────────

@dataclass
class ReEngagementCandidate:
    alumnus: Alumnus
    score: float
    months_since_contact: int | None
    reason: str


def re_engagement_worklist(*, score_threshold: float = 5.0,
                              months_quiet: int = 18,
                              leaving_year: str | None = None,
                              limit: int = 100
                              ) -> list[ReEngagementCandidate]:
    """Active alumni whose engagement score has fallen below
    ``score_threshold`` *or* who have had no contact for at least
    ``months_quiet`` months — ranked by who is most worth reaching
    again (highest historical engagement first, then longest gap)."""
    init_db()
    sql = ("SELECT * FROM alumni WHERE status = 'Active' "
            "AND deleted_at IS NULL")
    params: list[Any] = []
    if leaving_year:
        sql += " AND leaving_year = ?"
        params.append(leaving_year)
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    out: list[ReEngagementCandidate] = []
    for r in rows:
        a = _row(r)
        es = compute_engagement_score(a.alumni_id)
        quiet = (es.months_since_contact is None
                   or es.months_since_contact >= months_quiet)
        below = es.score < score_threshold
        if not (quiet or below):
            continue
        reasons = []
        if below:
            reasons.append(f"score {es.score} < {score_threshold}")
        if quiet:
            gap = (f"{es.months_since_contact}mo"
                    if es.months_since_contact is not None
                    else "never contacted")
            reasons.append(f"quiet ({gap})")
        out.append(ReEngagementCandidate(
            alumnus=a, score=es.score,
            months_since_contact=es.months_since_contact,
            reason="; ".join(reasons)))
    # Highest historical engagement first; tie-break on longest gap.
    out.sort(key=lambda c: (-c.score,
                              -(c.months_since_contact or 999)))
    return out[:limit]


# ── #6 Milestones / reminders ─────────────────────────────────────

MILESTONE_KINDS: tuple[str, ...] = (
    "Birthday", "Graduation Anniversary", "Work Anniversary",
)


@dataclass
class Milestone:
    alumni_id: int
    full_name: str
    kind: str
    when: str            # next-occurrence ISO date
    years: int | None    # 5, 10, 25 etc. for anniversaries
    detail: str | None   # employer/role for work anniversaries


def _next_anniversary(original: str | None,
                        now: _dt.date) -> tuple[_dt.date, int] | None:
    if not original:
        return None
    try:
        d = _dt.date.fromisoformat(original[:10])
    except ValueError:
        return None
    candidate = d.replace(year=now.year) if d.month != 2 or d.day != 29 \
        else _dt.date(now.year, 2, 28)
    if candidate < now:
        try:
            candidate = d.replace(year=now.year + 1)
        except ValueError:
            candidate = _dt.date(now.year + 1, 2, 28)
    years = candidate.year - d.year
    return candidate, years


def upcoming_milestones(*, days: int = 30,
                          kinds: tuple[str, ...] | None = None,
                          today: _dt.date | None = None
                          ) -> list[Milestone]:
    """Birthdays, graduation anniversaries and work anniversaries
    landing in the next ``days`` days.

    Graduation anniversaries fire only on round years (1, 5, 10, 15,
    20, 25, …). Work anniversaries fire on every year ≥ 1."""
    init_db()
    today = today or _dt.date.today()
    horizon = today + _dt.timedelta(days=days)
    wanted = set(kinds or MILESTONE_KINDS)
    out: list[Milestone] = []
    with _connect() as conn:
        rows = conn.execute(
            "SELECT alumni_id, first_name, last_name, preferred_name, "
            "       dob, leaving_date "
            "FROM alumni WHERE status = 'Active' AND deleted_at IS NULL"
        ).fetchall()
        for r in rows:
            full = f"{r['preferred_name'] or r['first_name']} " \
                     f"{r['last_name']}"
            if "Birthday" in wanted:
                nxt = _next_anniversary(r["dob"], today)
                if nxt and today <= nxt[0] <= horizon:
                    out.append(Milestone(
                        alumni_id=r["alumni_id"], full_name=full,
                        kind="Birthday",
                        when=nxt[0].isoformat(), years=nxt[1],
                        detail=None))
            if "Graduation Anniversary" in wanted:
                nxt = _next_anniversary(r["leaving_date"], today)
                if nxt and today <= nxt[0] <= horizon \
                        and nxt[1] >= 1 \
                        and (nxt[1] == 1 or nxt[1] % 5 == 0):
                    out.append(Milestone(
                        alumni_id=r["alumni_id"], full_name=full,
                        kind="Graduation Anniversary",
                        when=nxt[0].isoformat(), years=nxt[1],
                        detail=None))
        if "Work Anniversary" in wanted:
            crows = conn.execute(
                "SELECT c.alumni_id, c.role, c.employer, c.start_date, "
                "       a.first_name, a.last_name, a.preferred_name "
                "FROM alumni_career c "
                "JOIN alumni a ON a.alumni_id = c.alumni_id "
                "WHERE c.is_current = 1 AND a.status = 'Active' "
                "  AND a.deleted_at IS NULL AND c.start_date IS NOT NULL"
            ).fetchall()
            for r in crows:
                nxt = _next_anniversary(r["start_date"], today)
                if not nxt or not (today <= nxt[0] <= horizon):
                    continue
                if nxt[1] < 1:
                    continue
                full = f"{r['preferred_name'] or r['first_name']} " \
                         f"{r['last_name']}"
                out.append(Milestone(
                    alumni_id=r["alumni_id"], full_name=full,
                    kind="Work Anniversary",
                    when=nxt[0].isoformat(), years=nxt[1],
                    detail=f"{r['role']} @ {r['employer']}"))
    out.sort(key=lambda m: (m.when, m.full_name))
    return out


# ── #7 Lost-contact / find-a-friend queue ─────────────────────────

@dataclass
class LostContactCandidate:
    alumnus: Alumnus
    bounce_count: int
    has_email: bool
    has_phone: bool
    has_address: bool
    last_contacted: str | None


def lost_contact_queue(*,
                          bounce_threshold: int = HARD_BOUNCE_THRESHOLD,
                          require_no_phone: bool = True,
                          limit: int = 200
                          ) -> list[LostContactCandidate]:
    """Alumni who look unreachable:

    * email has hard-bounced at or beyond ``bounce_threshold`` *or*
      they have no email at all; AND
    * (default) they also have no phone number on file.

    Excludes opted-out, deceased, and already soft-deleted records."""
    init_db()
    out: list[LostContactCandidate] = []
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM alumni "
            "WHERE deleted_at IS NULL "
            "  AND status NOT IN ('Deceased', 'Opt-out')"
        ).fetchall()
        for r in rows:
            a = _row(r)
            primary = conn.execute(
                "SELECT 1 FROM alumni_emails WHERE alumni_id = ? LIMIT 1",
                (a.alumni_id,)).fetchone()
            has_email = bool(a.email) or primary is not None
            phone_row = conn.execute(
                "SELECT 1 FROM alumni_phones WHERE alumni_id = ? LIMIT 1",
                (a.alumni_id,)).fetchone()
            has_phone = bool(a.phone) or phone_row is not None
            email_dead = (a.bounce_count >= bounce_threshold
                            or not has_email)
            if not email_dead:
                continue
            if require_no_phone and has_phone:
                continue
            out.append(LostContactCandidate(
                alumnus=a, bounce_count=a.bounce_count,
                has_email=has_email, has_phone=has_phone,
                has_address=bool(a.address),
                last_contacted=a.last_contacted))
    out.sort(key=lambda c: (c.last_contacted or "0000-00-00"))
    return out[:limit]


# ── #8 Public directory ──────────────────────────────────────────

@dataclass
class DirectoryEntry:
    alumni_id: int
    display_name: str
    leaving_year: str | None
    current_role: str | None
    current_employer: str | None
    current_sector: str | None
    country: str | None
    region: str | None
    linkedin: str | None
    bio: str | None


def opt_in_directory(alumni_id: int, *,
                       source: str | None = None,
                       notes: str | None = None,
                       actor: str | None = None) -> Consent:
    """Grants the 'Directory' consent scope. Idempotent — if an active
    consent already exists for the scope, the existing one is
    returned without recording a duplicate."""
    init_db()
    existing = [c for c in list_consents(alumni_id, active_only=True)
                  if c.scope == DIRECTORY_CONSENT_SCOPE]
    if existing:
        return existing[0]
    out = grant_consent(alumni_id, DIRECTORY_CONSENT_SCOPE,
                          source=source, notes=notes)
    _log_action("directory.opt_in", actor=actor, alumni_id=alumni_id)
    return out


def opt_out_directory(alumni_id: int, *,
                        actor: str | None = None,
                        notes: str | None = None) -> int:
    """Withdraws every active 'Directory' consent for ``alumni_id``.
    Returns the number of consent rows withdrawn (usually 0 or 1)."""
    init_db()
    active = [c for c in list_consents(alumni_id, active_only=True)
                if c.scope == DIRECTORY_CONSENT_SCOPE]
    for c in active:
        withdraw_consent(c.consent_id, notes=notes)
    if active:
        _log_action("directory.opt_out", actor=actor,
                      alumni_id=alumni_id, count=len(active))
    return len(active)


def is_in_directory(alumni_id: int) -> bool:
    return has_active_consent(alumni_id, DIRECTORY_CONSENT_SCOPE)


def list_public_directory(*,
                             leaving_year: str | None = None,
                             sector: str | None = None,
                             country: str | None = None,
                             region: str | None = None,
                             q: str | None = None,
                             limit: int = 500
                             ) -> list[DirectoryEntry]:
    """All Active alumni who hold an in-force 'Directory' consent,
    optionally filtered. Returns the redacted public projection — no
    DOB, email, phone, address, or original_student_id."""
    init_db()
    sql = ("""SELECT a.* FROM alumni a
               WHERE a.status = 'Active'
                 AND a.deleted_at IS NULL
                 AND EXISTS (
                   SELECT 1 FROM alumni_consent c
                    WHERE c.alumni_id = a.alumni_id
                      AND c.scope = ?
                      AND c.withdrawn_at IS NULL)""")
    params: list[Any] = [DIRECTORY_CONSENT_SCOPE]
    if leaving_year:
        sql += " AND a.leaving_year = ?"
        params.append(leaving_year)
    if sector:
        sql += " AND a.current_sector = ?"
        params.append(sector)
    if country:
        sql += " AND a.country = ?"
        params.append(country)
    if region:
        sql += " AND a.region = ?"
        params.append(region)
    if q:
        like = f"%{q.strip()}%"
        sql += (" AND (a.first_name LIKE ? OR a.last_name LIKE ? "
                 "  OR a.preferred_name LIKE ? "
                 "  OR a.current_employer LIKE ? "
                 "  OR a.current_role LIKE ?)")
        params.extend([like, like, like, like, like])
    sql += (" ORDER BY a.leaving_year DESC NULLS LAST, "
             "          a.last_name ASC, a.first_name ASC LIMIT ?")
    params.append(limit)
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    out: list[DirectoryEntry] = []
    for r in rows:
        a = _row(r)
        out.append(DirectoryEntry(
            alumni_id=a.alumni_id,
            display_name=a.display_name,
            leaving_year=a.leaving_year,
            current_role=a.current_role,
            current_employer=a.current_employer,
            current_sector=a.current_sector,
            country=a.country,
            region=a.region,
            linkedin=a.linkedin,
            bio=a.bio))
    return out


# ════════════════════════════════════════════════════════════════════
# Career-cluster extensions (items 9–16) — skills, SOC/NAICS,
# employer directory, salary band analytics, promotion timeline,
# alumni job postings, internships, and mentor matching.
# ════════════════════════════════════════════════════════════════════

PROFICIENCY_LEVELS: tuple[str, ...] = (
    "Beginner", "Intermediate", "Advanced", "Expert",
)
JOB_STATUSES: tuple[str, ...] = (
    "Open", "Closed", "Filled", "Withdrawn",
)
JOB_TYPES: tuple[str, ...] = (
    "Graduate", "Junior", "Internship", "Part-time", "Contract",
    "Apprenticeship", "Other",
)
INTERNSHIP_STATUSES: tuple[str, ...] = JOB_STATUSES
APPLICATION_STATUSES: tuple[str, ...] = (
    "Submitted", "Shortlisted", "Interview", "Offered",
    "Accepted", "Rejected", "Withdrawn",
)


_SCHEMA_CAREER_EXT = """
CREATE TABLE IF NOT EXISTS alumni_skills (
    skill_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL UNIQUE COLLATE NOCASE,
    category   TEXT
);

CREATE TABLE IF NOT EXISTS alumni_skill_links (
    alumni_id    INTEGER NOT NULL,
    skill_id     INTEGER NOT NULL,
    proficiency  TEXT NOT NULL DEFAULT 'Intermediate',
    years        REAL,
    notes        TEXT,
    PRIMARY KEY (alumni_id, skill_id),
    FOREIGN KEY (alumni_id) REFERENCES alumni(alumni_id)
        ON DELETE CASCADE,
    FOREIGN KEY (skill_id)  REFERENCES alumni_skills(skill_id)
        ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_askl_skill
    ON alumni_skill_links(skill_id);

CREATE TABLE IF NOT EXISTS alumni_job_title_soc (
    pattern    TEXT PRIMARY KEY COLLATE NOCASE,
    soc_code   TEXT NOT NULL,
    soc_label  TEXT NOT NULL,
    naics_code TEXT
);

CREATE TABLE IF NOT EXISTS alumni_employers (
    employer_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical_name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    sector         TEXT,
    website        TEXT,
    country        TEXT,
    notes          TEXT,
    created_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS alumni_employer_aliases (
    alias          TEXT PRIMARY KEY COLLATE NOCASE,
    employer_id    INTEGER NOT NULL,
    FOREIGN KEY (employer_id) REFERENCES alumni_employers(employer_id)
        ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_aalias_eid
    ON alumni_employer_aliases(employer_id);

CREATE TABLE IF NOT EXISTS alumni_jobs (
    job_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    alumni_id     INTEGER NOT NULL,
    title         TEXT NOT NULL,
    employer      TEXT,
    sector        TEXT,
    location      TEXT,
    job_type      TEXT NOT NULL DEFAULT 'Graduate',
    salary_band   TEXT,
    description   TEXT,
    apply_url     TEXT,
    deadline      TEXT,
    status        TEXT NOT NULL DEFAULT 'Open',
    posted_at     TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (alumni_id) REFERENCES alumni(alumni_id)
        ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_ajob_alumni ON alumni_jobs(alumni_id);
CREATE INDEX IF NOT EXISTS idx_ajob_status ON alumni_jobs(status);

CREATE TABLE IF NOT EXISTS alumni_job_applications (
    application_id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id         INTEGER NOT NULL,
    applicant_kind TEXT NOT NULL DEFAULT 'Alumnus',
    applicant_id   TEXT NOT NULL,
    applied_on     TEXT NOT NULL DEFAULT (date('now')),
    status         TEXT NOT NULL DEFAULT 'Submitted',
    notes          TEXT,
    UNIQUE(job_id, applicant_kind, applicant_id),
    FOREIGN KEY (job_id) REFERENCES alumni_jobs(job_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS alumni_internships (
    internship_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    alumni_id       INTEGER NOT NULL,
    title           TEXT NOT NULL,
    employer        TEXT,
    sector          TEXT,
    location        TEXT,
    duration_weeks  INTEGER,
    paid            INTEGER NOT NULL DEFAULT 0,
    hourly_pence    INTEGER,
    start_window    TEXT,
    requirements    TEXT,
    apply_url       TEXT,
    deadline        TEXT,
    status          TEXT NOT NULL DEFAULT 'Open',
    posted_at       TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (alumni_id) REFERENCES alumni(alumni_id)
        ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_aint_alumni ON alumni_internships(alumni_id);
CREATE INDEX IF NOT EXISTS idx_aint_status ON alumni_internships(status);

CREATE TABLE IF NOT EXISTS alumni_internship_applications (
    application_id INTEGER PRIMARY KEY AUTOINCREMENT,
    internship_id  INTEGER NOT NULL,
    student_id     TEXT NOT NULL,
    applied_on     TEXT NOT NULL DEFAULT (date('now')),
    status         TEXT NOT NULL DEFAULT 'Submitted',
    notes          TEXT,
    UNIQUE(internship_id, student_id),
    FOREIGN KEY (internship_id)
        REFERENCES alumni_internships(internship_id) ON DELETE CASCADE
);
"""


def _init_career_ext_schema() -> None:
    with _connect() as conn:
        conn.executescript(_SCHEMA_CAREER_EXT)


# Extend init_db once more so the career-extension schema is created
# alongside the engagement schema. Re-wrap rather than edit.
_original_init_db_v2 = init_db


def init_db() -> None:  # type: ignore[no-redef]
    already = _DB_READY
    _original_init_db_v2()
    if not already:
        _init_career_ext_schema()


# ── #9 Skills ─────────────────────────────────────────────────────

@dataclass
class Skill:
    skill_id: int
    name: str
    category: str | None


@dataclass
class AlumnusSkill:
    alumni_id: int
    skill_id: int
    skill_name: str
    proficiency: str
    years: float | None
    notes: str | None


def _row_skill(r: sqlite3.Row) -> Skill:
    return Skill(skill_id=r["skill_id"], name=r["name"],
                   category=r["category"])


def list_all_skills() -> list[Skill]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM alumni_skills ORDER BY name COLLATE NOCASE"
            ).fetchall()
    return [_row_skill(r) for r in rows]


def get_or_create_skill(name: str, *,
                          category: str | None = None) -> Skill:
    init_db()
    name = (name or "").strip()
    if not name:
        raise ValidationError("Skill name is required")
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM alumni_skills WHERE name = ? COLLATE NOCASE",
            (name,)).fetchone()
        if r:
            return _row_skill(r)
        cur = conn.execute(
            "INSERT INTO alumni_skills (name, category) VALUES (?, ?)",
            (name, (category or "").strip() or None))
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_skills WHERE skill_id = ?",
            (cur.lastrowid,)).fetchone()
    return _row_skill(r)


def add_skill_to_alumnus(alumni_id: int, name: str, *,
                            proficiency: str = "Intermediate",
                            years: float | None = None,
                            notes: str | None = None,
                            actor: str | None = None) -> AlumnusSkill:
    init_db()
    if proficiency not in PROFICIENCY_LEVELS:
        raise ValidationError(
            f"Proficiency must be one of: "
            f"{', '.join(PROFICIENCY_LEVELS)}")
    skill = get_or_create_skill(name)
    with _connect() as conn:
        _require_alumnus(conn, alumni_id)
        conn.execute(
            """INSERT INTO alumni_skill_links
                   (alumni_id, skill_id, proficiency, years, notes)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(alumni_id, skill_id) DO UPDATE SET
                   proficiency = excluded.proficiency,
                   years       = excluded.years,
                   notes       = excluded.notes""",
            (alumni_id, skill.skill_id, proficiency, years,
             (notes or "").strip() or None))
        conn.commit()
    _log_action("skill.add", actor=actor, alumni_id=alumni_id,
                  skill=name, proficiency=proficiency)
    return AlumnusSkill(
        alumni_id=alumni_id, skill_id=skill.skill_id,
        skill_name=skill.name, proficiency=proficiency,
        years=years, notes=(notes or "").strip() or None)


def remove_skill_from_alumnus(alumni_id: int, skill_id: int, *,
                                actor: str | None = None) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM alumni_skill_links "
            "WHERE alumni_id = ? AND skill_id = ?",
            (alumni_id, skill_id))
        conn.commit()
    if cur.rowcount:
        _log_action("skill.remove", actor=actor,
                      alumni_id=alumni_id, skill_id=skill_id)
    return cur.rowcount > 0


def list_skills_for(alumni_id: int) -> list[AlumnusSkill]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            """SELECT l.alumni_id, l.skill_id, s.name, l.proficiency,
                      l.years, l.notes
                 FROM alumni_skill_links l
                 JOIN alumni_skills s ON s.skill_id = l.skill_id
                WHERE l.alumni_id = ?
                ORDER BY s.name COLLATE NOCASE""",
            (alumni_id,)).fetchall()
    return [AlumnusSkill(
        alumni_id=r["alumni_id"], skill_id=r["skill_id"],
        skill_name=r["name"], proficiency=r["proficiency"],
        years=r["years"], notes=r["notes"]) for r in rows]


def find_alumni_by_skill(name: str, *,
                            min_proficiency: str | None = None
                            ) -> list[Alumnus]:
    init_db()
    levels = list(PROFICIENCY_LEVELS)
    accept: set[str] = set(levels)
    if min_proficiency:
        if min_proficiency not in levels:
            raise ValidationError(
                f"Proficiency must be one of: {', '.join(levels)}")
        idx = levels.index(min_proficiency)
        accept = set(levels[idx:])
    placeholders = ",".join("?" * len(accept))
    with _connect() as conn:
        rows = conn.execute(
            f"""SELECT a.* FROM alumni a
                  JOIN alumni_skill_links l ON l.alumni_id = a.alumni_id
                  JOIN alumni_skills s ON s.skill_id = l.skill_id
                 WHERE s.name = ? COLLATE NOCASE
                   AND l.proficiency IN ({placeholders})
                   AND a.deleted_at IS NULL
                 ORDER BY a.last_name, a.first_name""",
            (name, *accept)).fetchall()
    return [_row(r) for r in rows]


# ── #10 SOC/NAICS classification ─────────────────────────────────

# A tiny built-in dictionary of UK SOC 2020-style codes. The
# `soc_classify` lookup combines this with anything stored in
# `alumni_job_title_soc`. Patterns match case-insensitively as
# substrings of the job title.
_BUILTIN_SOC_PATTERNS: tuple[tuple[str, str, str, str | None], ...] = (
    # (pattern, soc_code, soc_label, naics_code)
    ("software engineer", "2136", "Programmers and software development", "5415"),
    ("software developer", "2136", "Programmers and software development", "5415"),
    ("data scientist",   "2425", "Actuaries, economists and statisticians", "5417"),
    ("data analyst",     "2425", "Actuaries, economists and statisticians", "5417"),
    ("teacher",          "2314", "Secondary education teaching", "6111"),
    ("nurse",            "2231", "Nurses", "6221"),
    ("doctor",           "2211", "Medical practitioners", "6211"),
    ("solicitor",        "2412", "Solicitors", "5411"),
    ("barrister",        "2411", "Barristers and judges", "5411"),
    ("accountant",       "2421", "Chartered and certified accountants", "5412"),
    ("civil engineer",   "2121", "Civil engineers", "5413"),
    ("mechanical engineer", "2122", "Mechanical engineers", "5413"),
    ("electrical engineer", "2123", "Electrical engineers", "5413"),
    ("marketing manager", "1132", "Marketing and sales directors", "5418"),
    ("product manager",   "1136", "Information technology managers", "5415"),
    ("designer",         "3421", "Graphic designers", "5414"),
    ("consultant",       "2423", "Management consultants and business analysts", "5416"),
    ("researcher",       "2150", "Research and development managers", "5417"),
    ("journalist",       "2471", "Journalists, newspaper and periodical editors", "5111"),
)


def upsert_soc_pattern(pattern: str, soc_code: str,
                          soc_label: str, *,
                          naics_code: str | None = None) -> None:
    init_db()
    pattern = (pattern or "").strip().lower()
    if not pattern:
        raise ValidationError("Pattern is required")
    if not (soc_code or "").strip():
        raise ValidationError("SOC code is required")
    if not (soc_label or "").strip():
        raise ValidationError("SOC label is required")
    with _connect() as conn:
        conn.execute(
            """INSERT INTO alumni_job_title_soc
                   (pattern, soc_code, soc_label, naics_code)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(pattern) DO UPDATE SET
                   soc_code   = excluded.soc_code,
                   soc_label  = excluded.soc_label,
                   naics_code = excluded.naics_code""",
            (pattern, soc_code.strip(), soc_label.strip(),
             (naics_code or "").strip() or None))
        conn.commit()


def soc_classify(title: str | None
                    ) -> tuple[str, str, str | None] | None:
    """Return (soc_code, soc_label, naics_code) for the first matching
    pattern found in ``title``. Custom DB patterns override built-ins."""
    init_db()
    if not title:
        return None
    needle = title.lower()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT pattern, soc_code, soc_label, naics_code "
            "FROM alumni_job_title_soc").fetchall()
        for r in rows:
            if r["pattern"].lower() in needle:
                return (r["soc_code"], r["soc_label"], r["naics_code"])
    for pattern, code, label, naics in _BUILTIN_SOC_PATTERNS:
        if pattern in needle:
            return (code, label, naics)
    return None


def soc_breakdown(*, leaving_year: str | None = None
                     ) -> list[tuple[str, str, int]]:
    """Return (soc_code, soc_label, count) for current-job rows.
    Unclassified titles are returned under code ``'-'``."""
    init_db()
    sql = ("SELECT c.role FROM alumni_career c "
            "JOIN alumni a ON a.alumni_id = c.alumni_id "
            "WHERE c.is_current = 1 AND a.deleted_at IS NULL")
    params: list[Any] = []
    if leaving_year:
        sql += " AND a.leaving_year = ?"
        params.append(leaving_year)
    counts: dict[tuple[str, str], int] = {}
    with _connect() as conn:
        for r in conn.execute(sql, params).fetchall():
            cls = soc_classify(r["role"])
            key = (cls[0], cls[1]) if cls else ("-", "Unclassified")
            counts[key] = counts.get(key, 0) + 1
    return sorted(
        [(code, label, n) for (code, label), n in counts.items()],
        key=lambda t: (-t[2], t[1]))


# ── #11 Salary-band analytics ────────────────────────────────────

@dataclass
class SalaryBandRow:
    band: str
    count: int
    pct: float


def salary_band_breakdown(*, leaving_year: str | None = None,
                              sector: str | None = None
                              ) -> list[SalaryBandRow]:
    """Distribution of salary bands across current career rows.

    The salary_band column is already optional/free-text-ish; rows
    with no band recorded are grouped under ``'Unknown'`` to make
    completeness visible to the user."""
    init_db()
    sql = ("SELECT COALESCE(NULLIF(TRIM(c.salary_band), ''), 'Unknown') "
            "       AS band, COUNT(*) AS n "
            "  FROM alumni_career c "
            "  JOIN alumni a ON a.alumni_id = c.alumni_id "
            " WHERE c.is_current = 1 AND a.deleted_at IS NULL")
    params: list[Any] = []
    if leaving_year:
        sql += " AND a.leaving_year = ?"
        params.append(leaving_year)
    if sector:
        sql += " AND (c.sector = ? OR a.current_sector = ?)"
        params.extend([sector, sector])
    sql += " GROUP BY band"
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    total = sum(int(r["n"]) for r in rows) or 1
    out = [SalaryBandRow(band=r["band"], count=int(r["n"]),
                              pct=100 * int(r["n"]) / total)
            for r in rows]
    # Sort by SALARY_BANDS canonical order; unknowns last.
    order = {b: i for i, b in enumerate(SALARY_BANDS)}
    out.sort(key=lambda r: order.get(r.band, 99))
    return out


def median_salary_band(*, leaving_year: str | None = None,
                          sector: str | None = None) -> str | None:
    """Pick the band where the running cumulative percentage first
    reaches 50% (with bands in SALARY_BANDS order). Returns ``None`` if
    no banded rows exist."""
    rows = [r for r in salary_band_breakdown(leaving_year=leaving_year,
                                                  sector=sector)
              if r.band != "Unknown"]
    total = sum(r.count for r in rows)
    if total == 0:
        return None
    cum = 0
    for r in rows:
        cum += r.count
        if cum / total >= 0.5:
            return r.band
    return rows[-1].band


# ── #12 Promotion timeline ───────────────────────────────────────

@dataclass
class PromotionStep:
    career_id: int
    start_date: str | None
    end_date: str | None
    role: str
    employer: str
    is_current: bool


def promotion_timeline(alumni_id: int) -> list[PromotionStep]:
    """Career rows sorted chronologically. The list is also a
    promotion sequence if the alumnus's roles escalate; consumers can
    inspect ``role`` adjacency to flag promotions vs lateral moves."""
    init_db()
    rows = list_career(alumni_id)
    rows.sort(key=lambda c: (c.start_date or "0000-00-00", c.career_id))
    return [PromotionStep(
        career_id=c.career_id, start_date=c.start_date,
        end_date=c.end_date, role=c.role, employer=c.employer,
        is_current=c.is_current) for c in rows]


# ── #13 Employer directory ───────────────────────────────────────

@dataclass
class Employer:
    employer_id: int
    canonical_name: str
    sector: str | None
    website: str | None
    country: str | None
    notes: str | None
    created_at: str


def _row_employer(r: sqlite3.Row) -> Employer:
    return Employer(
        employer_id=r["employer_id"],
        canonical_name=r["canonical_name"],
        sector=r["sector"], website=r["website"],
        country=r["country"], notes=r["notes"],
        created_at=r["created_at"])


def upsert_employer(canonical_name: str, *,
                       sector: str | None = None,
                       website: str | None = None,
                       country: str | None = None,
                       notes: str | None = None,
                       actor: str | None = None) -> Employer:
    init_db()
    canonical_name = (canonical_name or "").strip()
    if not canonical_name:
        raise ValidationError("Employer name is required")
    with _connect() as conn:
        existing = conn.execute(
            "SELECT * FROM alumni_employers "
            "WHERE canonical_name = ? COLLATE NOCASE",
            (canonical_name,)).fetchone()
        if existing:
            conn.execute(
                """UPDATE alumni_employers
                      SET sector  = COALESCE(?, sector),
                          website = COALESCE(?, website),
                          country = COALESCE(?, country),
                          notes   = COALESCE(?, notes)
                    WHERE employer_id = ?""",
                ((sector or "").strip() or None,
                 (website or "").strip() or None,
                 (country or "").strip() or None,
                 (notes or "").strip() or None,
                 existing["employer_id"]))
            eid = existing["employer_id"]
        else:
            cur = conn.execute(
                """INSERT INTO alumni_employers
                       (canonical_name, sector, website, country, notes)
                   VALUES (?, ?, ?, ?, ?)""",
                (canonical_name,
                 (sector or "").strip() or None,
                 (website or "").strip() or None,
                 (country or "").strip() or None,
                 (notes or "").strip() or None))
            eid = cur.lastrowid
        conn.execute(
            "INSERT OR IGNORE INTO alumni_employer_aliases "
            "(alias, employer_id) VALUES (?, ?)",
            (canonical_name, eid))
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_employers WHERE employer_id = ?",
            (eid,)).fetchone()
    _log_action("employer.upsert", actor=actor,
                  employer_id=eid, name=canonical_name)
    return _row_employer(r)


def add_employer_alias(alias: str, employer_id: int, *,
                          actor: str | None = None) -> None:
    init_db()
    alias = (alias or "").strip()
    if not alias:
        raise ValidationError("Alias is required")
    with _connect() as conn:
        r = conn.execute(
            "SELECT 1 FROM alumni_employers WHERE employer_id = ?",
            (employer_id,)).fetchone()
        if r is None:
            raise ValidationError(f"No employer #{employer_id}")
        conn.execute(
            "INSERT OR REPLACE INTO alumni_employer_aliases "
            "(alias, employer_id) VALUES (?, ?)",
            (alias, employer_id))
        conn.commit()
    _log_action("employer.alias", actor=actor,
                  employer_id=employer_id, alias=alias)


def resolve_employer(name: str) -> Employer | None:
    """Resolve a free-text employer name via aliases. Returns ``None``
    if no canonical mapping exists yet."""
    init_db()
    if not name:
        return None
    with _connect() as conn:
        r = conn.execute(
            """SELECT e.* FROM alumni_employer_aliases al
                 JOIN alumni_employers e
                   ON e.employer_id = al.employer_id
                WHERE al.alias = ? COLLATE NOCASE""",
            ((name or "").strip(),)).fetchone()
    return _row_employer(r) if r else None


def list_employers() -> list[Employer]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM alumni_employers "
            "ORDER BY canonical_name COLLATE NOCASE").fetchall()
    return [_row_employer(r) for r in rows]


def delete_employer(employer_id: int, *,
                       actor: str | None = None) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM alumni_employers WHERE employer_id = ?",
            (employer_id,))
        conn.commit()
    if cur.rowcount:
        _log_action("employer.delete", actor=actor,
                      employer_id=employer_id)
    return cur.rowcount > 0


@dataclass
class TopEmployerRow:
    employer: str
    alumni_count: int


def top_employers(*, limit: int = 25,
                     leaving_year: str | None = None
                     ) -> list[TopEmployerRow]:
    """Count alumni per employer using the normalised name where one
    exists, else the free-text ``current_employer``. Useful for
    'top 25 employers of our alumni' boards."""
    init_db()
    sql = ("""SELECT COALESCE(e.canonical_name, a.current_employer)
                       AS name,
                     COUNT(*) AS n
                FROM alumni a
                LEFT JOIN alumni_employer_aliases al
                       ON al.alias = a.current_employer COLLATE NOCASE
                LEFT JOIN alumni_employers e
                       ON e.employer_id = al.employer_id
               WHERE a.current_employer IS NOT NULL
                 AND TRIM(a.current_employer) <> ''
                 AND a.deleted_at IS NULL
                 AND a.status = 'Active'""")
    params: list[Any] = []
    if leaving_year:
        sql += " AND a.leaving_year = ?"
        params.append(leaving_year)
    sql += " GROUP BY name ORDER BY n DESC, name COLLATE NOCASE LIMIT ?"
    params.append(limit)
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [TopEmployerRow(employer=r["name"], alumni_count=int(r["n"]))
            for r in rows]


# ── #14 Job postings board ────────────────────────────────────────

@dataclass
class JobPosting:
    job_id: int
    alumni_id: int
    title: str
    employer: str | None
    sector: str | None
    location: str | None
    job_type: str
    salary_band: str | None
    description: str | None
    apply_url: str | None
    deadline: str | None
    status: str
    posted_at: str


@dataclass
class JobApplication:
    application_id: int
    job_id: int
    applicant_kind: str
    applicant_id: str
    applied_on: str
    status: str
    notes: str | None


def _row_job(r: sqlite3.Row) -> JobPosting:
    return JobPosting(
        job_id=r["job_id"], alumni_id=r["alumni_id"],
        title=r["title"], employer=r["employer"],
        sector=r["sector"], location=r["location"],
        job_type=r["job_type"], salary_band=r["salary_band"],
        description=r["description"], apply_url=r["apply_url"],
        deadline=r["deadline"], status=r["status"],
        posted_at=r["posted_at"])


def _row_job_app(r: sqlite3.Row) -> JobApplication:
    return JobApplication(
        application_id=r["application_id"], job_id=r["job_id"],
        applicant_kind=r["applicant_kind"],
        applicant_id=r["applicant_id"],
        applied_on=r["applied_on"], status=r["status"],
        notes=r["notes"])


def post_job(alumni_id: int, payload: dict[str, Any], *,
                actor: str | None = None) -> JobPosting:
    init_db()
    title = (payload.get("title") or "").strip()
    if not title:
        raise ValidationError("Title is required")
    job_type = payload.get("job_type") or "Graduate"
    if job_type not in JOB_TYPES:
        raise ValidationError(
            f"Job type must be one of: {', '.join(JOB_TYPES)}")
    salary_band = (payload.get("salary_band") or "").strip() or None
    if salary_band and salary_band not in SALARY_BANDS:
        raise ValidationError(
            f"Salary band must be one of: {', '.join(SALARY_BANDS)}")
    deadline = _validate_date(
        payload.get("deadline"), "Deadline", required=False)
    with _connect() as conn:
        _require_alumnus(conn, alumni_id)
        cur = conn.execute(
            """INSERT INTO alumni_jobs
                   (alumni_id, title, employer, sector, location,
                    job_type, salary_band, description, apply_url,
                    deadline, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (alumni_id, title,
             (payload.get("employer") or "").strip() or None,
             (payload.get("sector") or "").strip() or None,
             (payload.get("location") or "").strip() or None,
             job_type, salary_band,
             (payload.get("description") or "").strip() or None,
             (payload.get("apply_url") or "").strip() or None,
             deadline,
             payload.get("status") or "Open"))
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_jobs WHERE job_id = ?",
            (cur.lastrowid,)).fetchone()
    _log_action("job.post", actor=actor, alumni_id=alumni_id,
                  title=title, job_id=r["job_id"])
    return _row_job(r)


def list_jobs(*, status: str | None = "Open",
                 alumni_id: int | None = None,
                 sector: str | None = None) -> list[JobPosting]:
    init_db()
    sql = "SELECT * FROM alumni_jobs WHERE 1=1"
    params: list[Any] = []
    if status:
        sql += " AND status = ?"
        params.append(status)
    if alumni_id is not None:
        sql += " AND alumni_id = ?"
        params.append(alumni_id)
    if sector:
        sql += " AND sector = ?"
        params.append(sector)
    sql += " ORDER BY posted_at DESC"
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_job(r) for r in rows]


def set_job_status(job_id: int, status: str, *,
                      actor: str | None = None) -> JobPosting:
    init_db()
    if status not in JOB_STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(JOB_STATUSES)}")
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE alumni_jobs SET status = ? WHERE job_id = ?",
            (status, job_id))
        if cur.rowcount == 0:
            raise ValidationError(f"No job #{job_id}")
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_jobs WHERE job_id = ?",
            (job_id,)).fetchone()
    _log_action("job.status", actor=actor,
                  job_id=job_id, status=status)
    return _row_job(r)


def delete_job(job_id: int, *,
                  actor: str | None = None) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM alumni_jobs WHERE job_id = ?", (job_id,))
        conn.commit()
    if cur.rowcount:
        _log_action("job.delete", actor=actor, job_id=job_id)
    return cur.rowcount > 0


def apply_to_job(job_id: int, *,
                    applicant_kind: str = "Alumnus",
                    applicant_id: str,
                    notes: str | None = None,
                    actor: str | None = None) -> JobApplication:
    init_db()
    if applicant_kind not in ("Alumnus", "Student", "External"):
        raise ValidationError(
            "Applicant kind must be Alumnus / Student / External")
    if not (applicant_id or "").strip():
        raise ValidationError("Applicant id is required")
    with _connect() as conn:
        r = conn.execute(
            "SELECT status FROM alumni_jobs WHERE job_id = ?",
            (job_id,)).fetchone()
        if r is None:
            raise ValidationError(f"No job #{job_id}")
        if r["status"] != "Open":
            raise ValidationError(
                f"Job #{job_id} is {r['status']}, not Open")
        try:
            cur = conn.execute(
                """INSERT INTO alumni_job_applications
                       (job_id, applicant_kind, applicant_id, notes)
                   VALUES (?, ?, ?, ?)""",
                (job_id, applicant_kind, applicant_id.strip(),
                 (notes or "").strip() or None))
        except sqlite3.IntegrityError as exc:
            raise ValidationError(
                "Already applied to this job") from exc
        conn.commit()
        row = conn.execute(
            "SELECT * FROM alumni_job_applications "
            "WHERE application_id = ?", (cur.lastrowid,)).fetchone()
    _log_action("job.apply", actor=actor, job_id=job_id,
                  applicant_kind=applicant_kind,
                  applicant_id=applicant_id)
    return _row_job_app(row)


def list_job_applications(job_id: int) -> list[JobApplication]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM alumni_job_applications "
            "WHERE job_id = ? ORDER BY applied_on DESC, "
            "application_id DESC", (job_id,)).fetchall()
    return [_row_job_app(r) for r in rows]


def set_job_application_status(application_id: int, status: str, *,
                                  actor: str | None = None
                                  ) -> JobApplication:
    init_db()
    if status not in APPLICATION_STATUSES:
        raise ValidationError(
            f"Status must be one of: "
            f"{', '.join(APPLICATION_STATUSES)}")
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE alumni_job_applications SET status = ? "
            "WHERE application_id = ?", (status, application_id))
        if cur.rowcount == 0:
            raise ValidationError(
                f"No application #{application_id}")
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_job_applications "
            "WHERE application_id = ?",
            (application_id,)).fetchone()
    _log_action("job.app.status", actor=actor,
                  application_id=application_id, status=status)
    return _row_job_app(r)


# ── #15 Internships board (for current sixth-formers) ─────────────

@dataclass
class Internship:
    internship_id: int
    alumni_id: int
    title: str
    employer: str | None
    sector: str | None
    location: str | None
    duration_weeks: int | None
    paid: bool
    hourly_pence: int | None
    start_window: str | None
    requirements: str | None
    apply_url: str | None
    deadline: str | None
    status: str
    posted_at: str


@dataclass
class InternshipApplication:
    application_id: int
    internship_id: int
    student_id: str
    applied_on: str
    status: str
    notes: str | None


def _row_internship(r: sqlite3.Row) -> Internship:
    return Internship(
        internship_id=r["internship_id"], alumni_id=r["alumni_id"],
        title=r["title"], employer=r["employer"], sector=r["sector"],
        location=r["location"],
        duration_weeks=r["duration_weeks"],
        paid=bool(r["paid"]), hourly_pence=r["hourly_pence"],
        start_window=r["start_window"],
        requirements=r["requirements"], apply_url=r["apply_url"],
        deadline=r["deadline"], status=r["status"],
        posted_at=r["posted_at"])


def _row_internship_app(r: sqlite3.Row) -> InternshipApplication:
    return InternshipApplication(
        application_id=r["application_id"],
        internship_id=r["internship_id"],
        student_id=r["student_id"],
        applied_on=r["applied_on"], status=r["status"],
        notes=r["notes"])


def post_internship(alumni_id: int, payload: dict[str, Any], *,
                       actor: str | None = None) -> Internship:
    init_db()
    title = (payload.get("title") or "").strip()
    if not title:
        raise ValidationError("Title is required")
    duration = payload.get("duration_weeks")
    if duration is not None and duration != "":
        try:
            duration = int(duration)
        except (TypeError, ValueError) as exc:
            raise ValidationError(
                "Duration (weeks) must be an integer") from exc
        if duration < 1:
            raise ValidationError("Duration must be ≥ 1 week")
    else:
        duration = None
    paid = bool(payload.get("paid"))
    hourly_pence = _pounds_to_pence(
        payload.get("hourly_pay"), "Hourly pay",
        required=False) if "hourly_pay" in payload \
        else payload.get("hourly_pence")
    if hourly_pence is not None:
        try:
            hourly_pence = int(hourly_pence)
        except (TypeError, ValueError) as exc:
            raise ValidationError(
                "Hourly pay must be a number") from exc
    deadline = _validate_date(
        payload.get("deadline"), "Deadline", required=False)
    with _connect() as conn:
        _require_alumnus(conn, alumni_id)
        cur = conn.execute(
            """INSERT INTO alumni_internships
                   (alumni_id, title, employer, sector, location,
                    duration_weeks, paid, hourly_pence, start_window,
                    requirements, apply_url, deadline, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (alumni_id, title,
             (payload.get("employer") or "").strip() or None,
             (payload.get("sector") or "").strip() or None,
             (payload.get("location") or "").strip() or None,
             duration, 1 if paid else 0, hourly_pence,
             (payload.get("start_window") or "").strip() or None,
             (payload.get("requirements") or "").strip() or None,
             (payload.get("apply_url") or "").strip() or None,
             deadline,
             payload.get("status") or "Open"))
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_internships WHERE internship_id = ?",
            (cur.lastrowid,)).fetchone()
    _log_action("internship.post", actor=actor,
                  alumni_id=alumni_id, title=title,
                  internship_id=r["internship_id"])
    return _row_internship(r)


def list_internships(*, status: str | None = "Open",
                        alumni_id: int | None = None,
                        sector: str | None = None,
                        paid_only: bool = False
                        ) -> list[Internship]:
    init_db()
    sql = "SELECT * FROM alumni_internships WHERE 1=1"
    params: list[Any] = []
    if status:
        sql += " AND status = ?"
        params.append(status)
    if alumni_id is not None:
        sql += " AND alumni_id = ?"
        params.append(alumni_id)
    if sector:
        sql += " AND sector = ?"
        params.append(sector)
    if paid_only:
        sql += " AND paid = 1"
    sql += " ORDER BY posted_at DESC"
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_internship(r) for r in rows]


def set_internship_status(internship_id: int, status: str, *,
                             actor: str | None = None) -> Internship:
    init_db()
    if status not in INTERNSHIP_STATUSES:
        raise ValidationError(
            f"Status must be one of: "
            f"{', '.join(INTERNSHIP_STATUSES)}")
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE alumni_internships SET status = ? "
            "WHERE internship_id = ?", (status, internship_id))
        if cur.rowcount == 0:
            raise ValidationError(f"No internship #{internship_id}")
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_internships WHERE internship_id = ?",
            (internship_id,)).fetchone()
    _log_action("internship.status", actor=actor,
                  internship_id=internship_id, status=status)
    return _row_internship(r)


def delete_internship(internship_id: int, *,
                         actor: str | None = None) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM alumni_internships WHERE internship_id = ?",
            (internship_id,))
        conn.commit()
    if cur.rowcount:
        _log_action("internship.delete", actor=actor,
                      internship_id=internship_id)
    return cur.rowcount > 0


def apply_to_internship(internship_id: int, student_id: str, *,
                           notes: str | None = None,
                           actor: str | None = None
                           ) -> InternshipApplication:
    init_db()
    if not (student_id or "").strip():
        raise ValidationError("Student id is required")
    with _connect() as conn:
        r = conn.execute(
            "SELECT status FROM alumni_internships "
            "WHERE internship_id = ?", (internship_id,)).fetchone()
        if r is None:
            raise ValidationError(f"No internship #{internship_id}")
        if r["status"] != "Open":
            raise ValidationError(
                f"Internship #{internship_id} is {r['status']}, "
                "not Open")
        try:
            cur = conn.execute(
                """INSERT INTO alumni_internship_applications
                       (internship_id, student_id, notes)
                   VALUES (?, ?, ?)""",
                (internship_id, student_id.strip(),
                 (notes or "").strip() or None))
        except sqlite3.IntegrityError as exc:
            raise ValidationError(
                "Already applied to this internship") from exc
        conn.commit()
        row = conn.execute(
            "SELECT * FROM alumni_internship_applications "
            "WHERE application_id = ?", (cur.lastrowid,)).fetchone()
    _log_action("internship.apply", actor=actor,
                  internship_id=internship_id, student_id=student_id)
    return _row_internship_app(row)


def list_internship_applications(internship_id: int
                                     ) -> list[InternshipApplication]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM alumni_internship_applications "
            "WHERE internship_id = ? "
            "ORDER BY applied_on DESC, application_id DESC",
            (internship_id,)).fetchall()
    return [_row_internship_app(r) for r in rows]


def set_internship_application_status(application_id: int, status: str,
                                          *, actor: str | None = None
                                          ) -> InternshipApplication:
    init_db()
    if status not in APPLICATION_STATUSES:
        raise ValidationError(
            f"Status must be one of: "
            f"{', '.join(APPLICATION_STATUSES)}")
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE alumni_internship_applications SET status = ? "
            "WHERE application_id = ?", (status, application_id))
        if cur.rowcount == 0:
            raise ValidationError(
                f"No internship application #{application_id}")
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_internship_applications "
            "WHERE application_id = ?",
            (application_id,)).fetchone()
    _log_action("internship.app.status", actor=actor,
                  application_id=application_id, status=status)
    return _row_internship_app(r)


# ── #16 Mentor matching ──────────────────────────────────────────

@dataclass
class MentorMatch:
    alumnus: Alumnus
    score: float
    reasons: list[str]


_MATCH_WEIGHTS = {
    "subject_overlap":   10.0,  # per shared subject
    "sector_match":       8.0,
    "university_match":  12.0,
    "country_match":      3.0,
    "region_match":       3.0,
    "is_speaker":         2.0,
    "active_mentor":      4.0,  # already mentoring → proven engagement
    "has_consent":        2.0,
    "opt_in_contact":     3.0,
    "skill_match":        2.0,  # per matching skill
}


def _student_context(student_id: str) -> dict[str, Any]:
    """Best-effort lookup of a student's subjects, target university,
    aspirations, and skills. Resilient to schema drift in the
    students/careers/aspirations modules — anything we can't fetch
    falls back to an empty list/value."""
    out: dict[str, Any] = {
        "subjects": [], "target_university": None,
        "aspiration_sector": None, "skills": [],
        "country": None, "region": None,
    }
    try:
        from education_system.sixthform_system.modules.domain.students.students \
            import students as students_mod
        s = students_mod.get_student(student_id)
        if s:
            out["subjects"] = list(getattr(s, "subjects", []) or [])
    except Exception:
        pass
    asp = _career_aspiration_for(student_id)
    if asp:
        out["aspiration_sector"] = asp
    return out


def match_mentors_for_student(student_id: str, *,
                                  limit: int = 10,
                                  require_consent: bool = True
                                  ) -> list[MentorMatch]:
    """Rank Active alumni as mentor candidates for ``student_id``.

    Scoring is additive — see ``_MATCH_WEIGHTS``. Already-active
    mentorships score higher (proven engagement); alumni without
    ``Mentoring`` consent are dropped when ``require_consent`` is
    true."""
    init_db()
    ctx = _student_context(student_id)
    student_subjects = {s.lower() for s in ctx["subjects"]}
    aspiration = (ctx.get("aspiration_sector") or "").lower()

    with _connect() as conn:
        alumni_rows = conn.execute(
            "SELECT * FROM alumni "
            "WHERE status = 'Active' AND deleted_at IS NULL"
            ).fetchall()
        speakers = {r["alumni_id"] for r in conn.execute(
            "SELECT alumni_id FROM alumni_speakers").fetchall()}
        active_mentors = {r["mentor_alumni_id"] for r in conn.execute(
            "SELECT DISTINCT mentor_alumni_id FROM alumni_mentorships "
            "WHERE status = 'Active'").fetchall()}

    matches: list[MentorMatch] = []
    for r in alumni_rows:
        a = _row(r)
        reasons: list[str] = []
        score = 0.0
        # Subject overlap with mentor's education rows.
        mentor_subjects = {
            (e.subject or "").lower()
            for e in list_education(a.alumni_id)
            if e.subject}
        overlap = student_subjects & mentor_subjects
        if overlap:
            score += len(overlap) * _MATCH_WEIGHTS["subject_overlap"]
            reasons.append(
                f"shared subjects: {', '.join(sorted(overlap))}")
        # Sector / aspiration match.
        if aspiration:
            sector_val = (a.current_sector or "").lower()
            if sector_val and sector_val == aspiration:
                score += _MATCH_WEIGHTS["sector_match"]
                reasons.append(f"sector match ({a.current_sector})")
        # University match — any of the mentor's institutions matches
        # any of the student's destination-university values from
        # alumni_education? We use the educations attached to the
        # alumnus as the alumnus's universities.
        unis = {(e.institution or "").lower()
                  for e in list_education(a.alumni_id)
                  if e.institution}
        if unis and ctx.get("target_university") \
                and ctx["target_university"].lower() in unis:
            score += _MATCH_WEIGHTS["university_match"]
            reasons.append(
                f"university match ({ctx['target_university']})")
        # Country / region (rough proxy — students module may not
        # carry these, so this is best-effort).
        if a.country and ctx.get("country") \
                and a.country.lower() == ctx["country"].lower():
            score += _MATCH_WEIGHTS["country_match"]
            reasons.append(f"country ({a.country})")
        if a.region and ctx.get("region") \
                and a.region.lower() == ctx["region"].lower():
            score += _MATCH_WEIGHTS["region_match"]
            reasons.append(f"region ({a.region})")
        if a.alumni_id in speakers:
            score += _MATCH_WEIGHTS["is_speaker"]
            reasons.append("registered speaker")
        if a.alumni_id in active_mentors:
            score += _MATCH_WEIGHTS["active_mentor"]
            reasons.append("currently mentoring")
        if has_active_consent(a.alumni_id, "Mentoring"):
            score += _MATCH_WEIGHTS["has_consent"]
            reasons.append("mentoring consent")
        elif require_consent:
            continue
        if a.opt_in_contact:
            score += _MATCH_WEIGHTS["opt_in_contact"]
        # Skill match: any student skill that this mentor lists.
        if ctx.get("skills"):
            mentor_skill_names = {
                s.skill_name.lower()
                for s in list_skills_for(a.alumni_id)}
            shared = mentor_skill_names & {
                x.lower() for x in ctx["skills"]}
            if shared:
                score += len(shared) * _MATCH_WEIGHTS["skill_match"]
                reasons.append(
                    f"shared skills: {', '.join(sorted(shared))}")
        if score <= 0:
            continue
        matches.append(MentorMatch(
            alumnus=a, score=round(score, 2), reasons=reasons))
    matches.sort(key=lambda m: m.score, reverse=True)
    return matches[:limit]


# ════════════════════════════════════════════════════════════════════
# Mentor + comms extensions (items 17–26).
# ════════════════════════════════════════════════════════════════════

SAFEGUARDING_STATUSES: tuple[str, ...] = (
    "Cleared", "Expiring Soon", "Expired", "Pending", "Suspended",
)
DRIP_STATUSES: tuple[str, ...] = ("Draft", "Active", "Paused", "Closed")
ENROLLMENT_STATUSES: tuple[str, ...] = (
    "Active", "Completed", "Unsubscribed", "Bounced",
)
NEWSLETTER_STATUSES: tuple[str, ...] = (
    "Draft", "Published", "Archived",
)
TRACK_KINDS: tuple[str, ...] = ("send", "open", "click", "bounce",
                                  "unsubscribe")


_SCHEMA_COMMS_EXT = """
CREATE TABLE IF NOT EXISTS alumni_mentor_profiles (
    alumni_id        INTEGER PRIMARY KEY,
    max_mentees      INTEGER NOT NULL DEFAULT 3,
    available_from   TEXT,
    available_until  TEXT,
    paused           INTEGER NOT NULL DEFAULT 0,
    bio              TEXT,
    updated_at       TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (alumni_id) REFERENCES alumni(alumni_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS alumni_mentor_safeguarding (
    alumni_id        INTEGER PRIMARY KEY,
    dbs_reference    TEXT,
    dbs_issued_on    TEXT,
    dbs_expires_on   TEXT,
    training_done_on TEXT,
    training_expires_on TEXT,
    status           TEXT NOT NULL DEFAULT 'Pending',
    notes            TEXT,
    updated_at       TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (alumni_id) REFERENCES alumni(alumni_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS alumni_email_templates (
    template_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL COLLATE NOCASE,
    version      INTEGER NOT NULL DEFAULT 1,
    subject      TEXT NOT NULL,
    body         TEXT NOT NULL,
    category     TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(name, version)
);

CREATE TABLE IF NOT EXISTS alumni_drip_campaigns (
    drip_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL UNIQUE COLLATE NOCASE,
    description  TEXT,
    status       TEXT NOT NULL DEFAULT 'Draft',
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS alumni_drip_steps (
    step_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    drip_id        INTEGER NOT NULL,
    position       INTEGER NOT NULL,
    delay_days     INTEGER NOT NULL DEFAULT 0,
    template_id    INTEGER,
    subject        TEXT,
    body           TEXT,
    UNIQUE(drip_id, position),
    FOREIGN KEY (drip_id)      REFERENCES alumni_drip_campaigns(drip_id)
        ON DELETE CASCADE,
    FOREIGN KEY (template_id)  REFERENCES alumni_email_templates(template_id)
        ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS alumni_drip_enrollments (
    enrollment_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    drip_id        INTEGER NOT NULL,
    alumni_id      INTEGER NOT NULL,
    enrolled_at    TEXT NOT NULL DEFAULT (datetime('now')),
    next_send_at   TEXT,
    current_step   INTEGER NOT NULL DEFAULT 0,
    status         TEXT NOT NULL DEFAULT 'Active',
    UNIQUE(drip_id, alumni_id),
    FOREIGN KEY (drip_id)   REFERENCES alumni_drip_campaigns(drip_id)
        ON DELETE CASCADE,
    FOREIGN KEY (alumni_id) REFERENCES alumni(alumni_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS alumni_ab_tests (
    test_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL UNIQUE COLLATE NOCASE,
    description  TEXT,
    filters_json TEXT,
    sent_at      TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS alumni_ab_variants (
    variant_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    test_id      INTEGER NOT NULL,
    label        TEXT NOT NULL,
    subject      TEXT NOT NULL,
    body         TEXT NOT NULL,
    sent_count   INTEGER NOT NULL DEFAULT 0,
    open_count   INTEGER NOT NULL DEFAULT 0,
    click_count  INTEGER NOT NULL DEFAULT 0,
    UNIQUE(test_id, label),
    FOREIGN KEY (test_id) REFERENCES alumni_ab_tests(test_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS alumni_ab_assignments (
    test_id     INTEGER NOT NULL,
    alumni_id   INTEGER NOT NULL,
    variant_id  INTEGER NOT NULL,
    PRIMARY KEY (test_id, alumni_id),
    FOREIGN KEY (test_id)    REFERENCES alumni_ab_tests(test_id)
        ON DELETE CASCADE,
    FOREIGN KEY (variant_id) REFERENCES alumni_ab_variants(variant_id)
        ON DELETE CASCADE,
    FOREIGN KEY (alumni_id)  REFERENCES alumni(alumni_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS alumni_sms_messages (
    sms_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    alumni_id   INTEGER NOT NULL,
    body        TEXT NOT NULL,
    sent_at     TEXT NOT NULL DEFAULT (datetime('now')),
    status      TEXT NOT NULL DEFAULT 'Sent',
    error       TEXT,
    FOREIGN KEY (alumni_id) REFERENCES alumni(alumni_id)
        ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_asms_alumni ON alumni_sms_messages(alumni_id);

CREATE TABLE IF NOT EXISTS alumni_postal_letters (
    letter_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    alumni_id   INTEGER NOT NULL,
    subject     TEXT NOT NULL,
    body        TEXT NOT NULL,
    pdf_path    TEXT,
    generated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (alumni_id) REFERENCES alumni(alumni_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS alumni_newsletters (
    newsletter_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    issue          TEXT NOT NULL UNIQUE COLLATE NOCASE,
    title          TEXT NOT NULL,
    status         TEXT NOT NULL DEFAULT 'Draft',
    published_at   TEXT,
    distribution_filters_json TEXT,
    created_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS alumni_newsletter_sections (
    section_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    newsletter_id  INTEGER NOT NULL,
    position       INTEGER NOT NULL,
    heading        TEXT NOT NULL,
    body           TEXT NOT NULL,
    UNIQUE(newsletter_id, position),
    FOREIGN KEY (newsletter_id)
        REFERENCES alumni_newsletters(newsletter_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS alumni_track_events (
    event_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    token       TEXT NOT NULL,
    alumni_id   INTEGER,
    kind        TEXT NOT NULL,
    payload     TEXT,
    at          TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (alumni_id) REFERENCES alumni(alumni_id)
        ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_atrk_token ON alumni_track_events(token);
CREATE INDEX IF NOT EXISTS idx_atrk_alumni ON alumni_track_events(alumni_id);

CREATE TABLE IF NOT EXISTS alumni_track_links (
    token        TEXT PRIMARY KEY,
    alumni_id    INTEGER,
    kind         TEXT NOT NULL DEFAULT 'click',
    target_url   TEXT,
    campaign_ref TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (alumni_id) REFERENCES alumni(alumni_id)
        ON DELETE CASCADE
);
"""

_MENTOR_SESSION_NEW_COLUMNS: tuple[tuple[str, str], ...] = (
    ("mentor_rating", "INTEGER"),  # 1..5 from mentee
    ("mentee_rating", "INTEGER"),  # 1..5 from mentor
)


def _init_comms_ext_schema() -> None:
    with _connect() as conn:
        conn.executescript(_SCHEMA_COMMS_EXT)
        existing = {row[1] for row in conn.execute(
            "PRAGMA table_info(alumni_mentor_sessions)").fetchall()}
        for col, decl in _MENTOR_SESSION_NEW_COLUMNS:
            if col not in existing:
                conn.execute(
                    f"ALTER TABLE alumni_mentor_sessions "
                    f"ADD COLUMN {col} {decl}")


_original_init_db_v3 = init_db


def init_db() -> None:  # type: ignore[no-redef]
    already = _DB_READY
    _original_init_db_v3()
    if not already:
        _init_comms_ext_schema()


# ── #17 Mentor capacity & availability ───────────────────────────

@dataclass
class MentorProfile:
    alumni_id: int
    max_mentees: int
    available_from: str | None
    available_until: str | None
    paused: bool
    bio: str | None
    updated_at: str


def _row_mentor_profile(r: sqlite3.Row) -> MentorProfile:
    return MentorProfile(
        alumni_id=r["alumni_id"],
        max_mentees=int(r["max_mentees"]),
        available_from=r["available_from"],
        available_until=r["available_until"],
        paused=bool(r["paused"]),
        bio=r["bio"],
        updated_at=r["updated_at"])


def upsert_mentor_profile(alumni_id: int, *,
                              max_mentees: int = 3,
                              available_from: str | None = None,
                              available_until: str | None = None,
                              paused: bool = False,
                              bio: str | None = None,
                              actor: str | None = None
                              ) -> MentorProfile:
    init_db()
    if max_mentees < 0:
        raise ValidationError("max_mentees must be ≥ 0")
    avail_from = _validate_date(available_from, "Available from",
                                    required=False)
    avail_until = _validate_date(available_until, "Available until",
                                     required=False)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        _require_alumnus(conn, alumni_id)
        conn.execute(
            """INSERT INTO alumni_mentor_profiles
                   (alumni_id, max_mentees, available_from,
                    available_until, paused, bio, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(alumni_id) DO UPDATE SET
                   max_mentees     = excluded.max_mentees,
                   available_from  = excluded.available_from,
                   available_until = excluded.available_until,
                   paused          = excluded.paused,
                   bio             = excluded.bio,
                   updated_at      = excluded.updated_at""",
            (alumni_id, max_mentees, avail_from, avail_until,
             1 if paused else 0, (bio or "").strip() or None, now))
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_mentor_profiles "
            "WHERE alumni_id = ?", (alumni_id,)).fetchone()
    _log_action("mentor.profile", actor=actor, alumni_id=alumni_id,
                  max_mentees=max_mentees, paused=paused)
    return _row_mentor_profile(r)


def get_mentor_profile(alumni_id: int) -> MentorProfile | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM alumni_mentor_profiles WHERE alumni_id = ?",
            (alumni_id,)).fetchone()
    return _row_mentor_profile(r) if r else None


def active_mentee_count(alumni_id: int) -> int:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT COUNT(*) FROM alumni_mentorships "
            "WHERE mentor_alumni_id = ? AND status = 'Active'",
            (alumni_id,)).fetchone()
    return int(r[0])


def mentor_has_capacity(alumni_id: int,
                          today: _dt.date | None = None) -> bool:
    """True when the mentor profile is not paused, within their
    availability window, and below ``max_mentees``."""
    init_db()
    p = get_mentor_profile(alumni_id)
    if p is None or p.paused:
        return False
    today = today or _dt.date.today()
    if p.available_from:
        try:
            if today < _dt.date.fromisoformat(p.available_from):
                return False
        except ValueError:
            pass
    if p.available_until:
        try:
            if today > _dt.date.fromisoformat(p.available_until):
                return False
        except ValueError:
            pass
    return active_mentee_count(alumni_id) < p.max_mentees


def list_available_mentors() -> list[MentorProfile]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM alumni_mentor_profiles "
            "WHERE paused = 0 ORDER BY alumni_id").fetchall()
    return [p for p in (_row_mentor_profile(r) for r in rows)
              if mentor_has_capacity(p.alumni_id)]


# ── #18 Mentor feedback / rating ─────────────────────────────────

def rate_mentor_session(session_id: int, *,
                          mentee_rating: int | None = None,
                          mentor_rating: int | None = None,
                          mentor_feedback: str | None = None,
                          mentee_feedback: str | None = None,
                          actor: str | None = None) -> None:
    """Record numeric ratings (1-5) and/or freeform feedback against a
    mentor session row. Either rating may be omitted."""
    init_db()
    for label, val in (("mentee_rating", mentee_rating),
                          ("mentor_rating", mentor_rating)):
        if val is not None and not (1 <= int(val) <= 5):
            raise ValidationError(f"{label} must be between 1 and 5")
    sets: list[str] = []
    vals: list[Any] = []
    if mentee_rating is not None:
        sets.append("mentee_rating = ?"); vals.append(int(mentee_rating))
    if mentor_rating is not None:
        sets.append("mentor_rating = ?"); vals.append(int(mentor_rating))
    if mentor_feedback is not None:
        sets.append("mentor_feedback = ?")
        vals.append((mentor_feedback or "").strip() or None)
    if mentee_feedback is not None:
        sets.append("mentee_feedback = ?")
        vals.append((mentee_feedback or "").strip() or None)
    if not sets:
        return
    vals.append(session_id)
    with _connect() as conn:
        cur = conn.execute(
            f"UPDATE alumni_mentor_sessions SET {', '.join(sets)} "
            f"WHERE session_id = ?", vals)
        if cur.rowcount == 0:
            raise ValidationError(f"No mentor session #{session_id}")
        conn.commit()
    _log_action("mentor.rate", actor=actor, session_id=session_id,
                  mentee_rating=mentee_rating,
                  mentor_rating=mentor_rating)


@dataclass
class MentorScorecard:
    alumni_id: int
    sessions: int
    avg_mentee_rating: float | None
    avg_mentor_rating: float | None


def mentor_scorecard(alumni_id: int) -> MentorScorecard:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            """SELECT COUNT(*) AS n,
                      AVG(mentee_rating) AS mr,
                      AVG(mentor_rating) AS gr
                 FROM alumni_mentor_sessions s
                 JOIN alumni_mentorships m
                   ON m.mentorship_id = s.mentorship_id
                WHERE m.mentor_alumni_id = ?""",
            (alumni_id,)).fetchone()
    return MentorScorecard(
        alumni_id=alumni_id, sessions=int(r["n"]),
        avg_mentee_rating=(round(float(r["mr"]), 2)
                              if r["mr"] is not None else None),
        avg_mentor_rating=(round(float(r["gr"]), 2)
                              if r["gr"] is not None else None))


# ── #19 Mentor safeguarding checks ───────────────────────────────

@dataclass
class MentorSafeguarding:
    alumni_id: int
    dbs_reference: str | None
    dbs_issued_on: str | None
    dbs_expires_on: str | None
    training_done_on: str | None
    training_expires_on: str | None
    status: str
    notes: str | None
    updated_at: str


def _row_safeguarding(r: sqlite3.Row) -> MentorSafeguarding:
    return MentorSafeguarding(
        alumni_id=r["alumni_id"],
        dbs_reference=r["dbs_reference"],
        dbs_issued_on=r["dbs_issued_on"],
        dbs_expires_on=r["dbs_expires_on"],
        training_done_on=r["training_done_on"],
        training_expires_on=r["training_expires_on"],
        status=r["status"], notes=r["notes"],
        updated_at=r["updated_at"])


def _derive_safeguarding_status(
        dbs_expires_on: str | None,
        training_expires_on: str | None,
        today: _dt.date | None = None) -> str:
    today = today or _dt.date.today()
    expiries: list[_dt.date] = []
    for s in (dbs_expires_on, training_expires_on):
        if not s:
            continue
        try:
            expiries.append(_dt.date.fromisoformat(s))
        except ValueError:
            continue
    if not expiries:
        return "Pending"
    if any(d < today for d in expiries):
        return "Expired"
    if any((d - today).days <= 60 for d in expiries):
        return "Expiring Soon"
    return "Cleared"


def upsert_mentor_safeguarding(alumni_id: int, *,
                                   dbs_reference: str | None = None,
                                   dbs_issued_on: str | None = None,
                                   dbs_expires_on: str | None = None,
                                   training_done_on: str | None = None,
                                   training_expires_on: str | None = None,
                                   status: str | None = None,
                                   notes: str | None = None,
                                   actor: str | None = None
                                   ) -> MentorSafeguarding:
    init_db()
    iso_dbs_iss = _validate_date(dbs_issued_on, "DBS issued",
                                     required=False)
    iso_dbs_exp = _validate_date(dbs_expires_on, "DBS expires",
                                     required=False)
    iso_tr_done = _validate_date(training_done_on, "Training done",
                                     required=False)
    iso_tr_exp = _validate_date(training_expires_on,
                                    "Training expires",
                                    required=False)
    if status and status not in SAFEGUARDING_STATUSES:
        raise ValidationError(
            f"Status must be one of: "
            f"{', '.join(SAFEGUARDING_STATUSES)}")
    derived = status or _derive_safeguarding_status(
        iso_dbs_exp, iso_tr_exp)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        _require_alumnus(conn, alumni_id)
        conn.execute(
            """INSERT INTO alumni_mentor_safeguarding
                   (alumni_id, dbs_reference, dbs_issued_on,
                    dbs_expires_on, training_done_on,
                    training_expires_on, status, notes, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(alumni_id) DO UPDATE SET
                   dbs_reference       = excluded.dbs_reference,
                   dbs_issued_on       = excluded.dbs_issued_on,
                   dbs_expires_on      = excluded.dbs_expires_on,
                   training_done_on    = excluded.training_done_on,
                   training_expires_on = excluded.training_expires_on,
                   status              = excluded.status,
                   notes               = excluded.notes,
                   updated_at          = excluded.updated_at""",
            (alumni_id,
             (dbs_reference or "").strip() or None,
             iso_dbs_iss, iso_dbs_exp,
             iso_tr_done, iso_tr_exp, derived,
             (notes or "").strip() or None, now))
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_mentor_safeguarding "
            "WHERE alumni_id = ?", (alumni_id,)).fetchone()
    _log_action("mentor.safeguarding", actor=actor,
                  alumni_id=alumni_id, status=derived)
    return _row_safeguarding(r)


def get_mentor_safeguarding(alumni_id: int
                                ) -> MentorSafeguarding | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM alumni_mentor_safeguarding "
            "WHERE alumni_id = ?", (alumni_id,)).fetchone()
    return _row_safeguarding(r) if r else None


def list_safeguarding_alerts(*, days: int = 60
                                  ) -> list[MentorSafeguarding]:
    """Anyone whose DBS or training expires within ``days`` days, or
    is already expired."""
    init_db()
    today = _dt.date.today()
    horizon = today + _dt.timedelta(days=days)
    with _connect() as conn:
        rows = conn.execute(
            """SELECT * FROM alumni_mentor_safeguarding
                WHERE (dbs_expires_on IS NOT NULL
                          AND dbs_expires_on <= ?)
                   OR (training_expires_on IS NOT NULL
                          AND training_expires_on <= ?)""",
            (horizon.isoformat(), horizon.isoformat())).fetchall()
    out = [_row_safeguarding(r) for r in rows]
    for s in out:
        # Recompute live status so list reflects 'today', not stored.
        s.status = _derive_safeguarding_status(
            s.dbs_expires_on, s.training_expires_on, today=today)
    out.sort(key=lambda s: (s.dbs_expires_on or s.training_expires_on
                              or "9999-99-99"))
    return out


# ── #20 Email templates library ──────────────────────────────────

@dataclass
class EmailTemplate:
    template_id: int
    name: str
    version: int
    subject: str
    body: str
    category: str | None
    created_at: str


def _row_template(r: sqlite3.Row) -> EmailTemplate:
    return EmailTemplate(
        template_id=r["template_id"], name=r["name"],
        version=int(r["version"]),
        subject=r["subject"], body=r["body"],
        category=r["category"], created_at=r["created_at"])


def create_email_template(name: str, subject: str, body: str, *,
                             category: str | None = None,
                             actor: str | None = None
                             ) -> EmailTemplate:
    init_db()
    name = (name or "").strip()
    if not name:
        raise ValidationError("Template name is required")
    if not (subject or "").strip():
        raise ValidationError("Subject is required")
    if not (body or "").strip():
        raise ValidationError("Body is required")
    with _connect() as conn:
        r = conn.execute(
            "SELECT MAX(version) AS v FROM alumni_email_templates "
            "WHERE name = ? COLLATE NOCASE", (name,)).fetchone()
        next_v = int(r["v"] or 0) + 1
        cur = conn.execute(
            """INSERT INTO alumni_email_templates
                   (name, version, subject, body, category)
               VALUES (?, ?, ?, ?, ?)""",
            (name, next_v, subject.strip(), body,
             (category or "").strip() or None))
        conn.commit()
        row = conn.execute(
            "SELECT * FROM alumni_email_templates "
            "WHERE template_id = ?", (cur.lastrowid,)).fetchone()
    _log_action("template.create", actor=actor, name=name,
                  version=next_v)
    return _row_template(row)


def list_email_templates(*, category: str | None = None,
                              latest_only: bool = True
                              ) -> list[EmailTemplate]:
    init_db()
    if latest_only:
        sql = ("""SELECT t.* FROM alumni_email_templates t
                    JOIN (SELECT name, MAX(version) AS v
                           FROM alumni_email_templates
                           GROUP BY name) m
                      ON m.name = t.name AND m.v = t.version""")
        params: list[Any] = []
        if category:
            sql += " WHERE t.category = ?"; params.append(category)
        sql += " ORDER BY t.name COLLATE NOCASE"
    else:
        sql = "SELECT * FROM alumni_email_templates"
        params = []
        if category:
            sql += " WHERE category = ?"; params.append(category)
        sql += " ORDER BY name COLLATE NOCASE, version DESC"
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_template(r) for r in rows]


def get_email_template(name: str, *,
                          version: int | None = None
                          ) -> EmailTemplate | None:
    init_db()
    with _connect() as conn:
        if version is None:
            r = conn.execute(
                "SELECT * FROM alumni_email_templates "
                "WHERE name = ? COLLATE NOCASE "
                "ORDER BY version DESC LIMIT 1",
                (name,)).fetchone()
        else:
            r = conn.execute(
                "SELECT * FROM alumni_email_templates "
                "WHERE name = ? COLLATE NOCASE AND version = ?",
                (name, version)).fetchone()
    return _row_template(r) if r else None


def delete_email_template(template_id: int, *,
                              actor: str | None = None) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM alumni_email_templates "
            "WHERE template_id = ?", (template_id,))
        conn.commit()
    if cur.rowcount:
        _log_action("template.delete", actor=actor,
                      template_id=template_id)
    return cur.rowcount > 0


def render_template(template: EmailTemplate, alumni_id: int
                       ) -> tuple[str, str]:
    """Render a template's subject and body against ``alumni_id``,
    using the same context builder as the existing send_email helpers
    (so merge fields stay consistent)."""
    init_db()
    a = get_alumnus(alumni_id)
    if a is None:
        raise ValidationError(f"No alumnus #{alumni_id}")
    ctx = _alumnus_context(a)
    return _render(template.subject, ctx), _render(template.body, ctx)


# ── #21 Drip campaigns ───────────────────────────────────────────

@dataclass
class DripCampaign:
    drip_id: int
    name: str
    description: str | None
    status: str
    created_at: str


@dataclass
class DripStep:
    step_id: int
    drip_id: int
    position: int
    delay_days: int
    template_id: int | None
    subject: str | None
    body: str | None


@dataclass
class DripEnrollment:
    enrollment_id: int
    drip_id: int
    alumni_id: int
    enrolled_at: str
    next_send_at: str | None
    current_step: int
    status: str


def _row_drip(r: sqlite3.Row) -> DripCampaign:
    return DripCampaign(
        drip_id=r["drip_id"], name=r["name"],
        description=r["description"], status=r["status"],
        created_at=r["created_at"])


def _row_drip_step(r: sqlite3.Row) -> DripStep:
    return DripStep(
        step_id=r["step_id"], drip_id=r["drip_id"],
        position=int(r["position"]),
        delay_days=int(r["delay_days"]),
        template_id=r["template_id"], subject=r["subject"],
        body=r["body"])


def _row_enrollment(r: sqlite3.Row) -> DripEnrollment:
    return DripEnrollment(
        enrollment_id=r["enrollment_id"], drip_id=r["drip_id"],
        alumni_id=r["alumni_id"],
        enrolled_at=r["enrolled_at"],
        next_send_at=r["next_send_at"],
        current_step=int(r["current_step"]),
        status=r["status"])


def create_drip_campaign(name: str, *,
                            description: str | None = None,
                            actor: str | None = None) -> DripCampaign:
    init_db()
    name = (name or "").strip()
    if not name:
        raise ValidationError("Drip campaign name is required")
    with _connect() as conn:
        try:
            cur = conn.execute(
                """INSERT INTO alumni_drip_campaigns
                       (name, description) VALUES (?, ?)""",
                (name, (description or "").strip() or None))
        except sqlite3.IntegrityError as exc:
            raise ValidationError(
                f"A drip campaign named {name!r} already exists"
            ) from exc
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_drip_campaigns WHERE drip_id = ?",
            (cur.lastrowid,)).fetchone()
    _log_action("drip.create", actor=actor, name=name)
    return _row_drip(r)


def add_drip_step(drip_id: int, *,
                     position: int, delay_days: int,
                     template_id: int | None = None,
                     subject: str | None = None,
                     body: str | None = None,
                     actor: str | None = None) -> DripStep:
    init_db()
    if position < 1:
        raise ValidationError("Position must be ≥ 1")
    if delay_days < 0:
        raise ValidationError("delay_days must be ≥ 0")
    if not template_id and not ((subject or "").strip()
                                  and (body or "").strip()):
        raise ValidationError(
            "Provide either a template_id or both subject + body")
    with _connect() as conn:
        r = conn.execute(
            "SELECT 1 FROM alumni_drip_campaigns WHERE drip_id = ?",
            (drip_id,)).fetchone()
        if r is None:
            raise ValidationError(f"No drip #{drip_id}")
        try:
            cur = conn.execute(
                """INSERT INTO alumni_drip_steps
                       (drip_id, position, delay_days, template_id,
                        subject, body)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (drip_id, position, delay_days, template_id,
                 (subject or "").strip() or None,
                 (body or "").strip() or None))
        except sqlite3.IntegrityError as exc:
            raise ValidationError(
                f"Position {position} already exists in drip "
                f"#{drip_id}") from exc
        conn.commit()
        row = conn.execute(
            "SELECT * FROM alumni_drip_steps WHERE step_id = ?",
            (cur.lastrowid,)).fetchone()
    _log_action("drip.step.add", actor=actor, drip_id=drip_id,
                  position=position)
    return _row_drip_step(row)


def list_drip_campaigns() -> list[DripCampaign]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM alumni_drip_campaigns "
            "ORDER BY name COLLATE NOCASE").fetchall()
    return [_row_drip(r) for r in rows]


def list_drip_steps(drip_id: int) -> list[DripStep]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM alumni_drip_steps "
            "WHERE drip_id = ? ORDER BY position",
            (drip_id,)).fetchall()
    return [_row_drip_step(r) for r in rows]


def set_drip_status(drip_id: int, status: str, *,
                       actor: str | None = None) -> DripCampaign:
    init_db()
    if status not in DRIP_STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(DRIP_STATUSES)}")
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE alumni_drip_campaigns SET status = ? "
            "WHERE drip_id = ?", (status, drip_id))
        if cur.rowcount == 0:
            raise ValidationError(f"No drip #{drip_id}")
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_drip_campaigns WHERE drip_id = ?",
            (drip_id,)).fetchone()
    _log_action("drip.status", actor=actor, drip_id=drip_id,
                  status=status)
    return _row_drip(r)


def enroll_in_drip(drip_id: int, alumni_id: int, *,
                       actor: str | None = None) -> DripEnrollment:
    init_db()
    with _connect() as conn:
        d = conn.execute(
            "SELECT status FROM alumni_drip_campaigns "
            "WHERE drip_id = ?", (drip_id,)).fetchone()
        if d is None:
            raise ValidationError(f"No drip #{drip_id}")
        _require_alumnus(conn, alumni_id)
        first_step = conn.execute(
            "SELECT delay_days FROM alumni_drip_steps "
            "WHERE drip_id = ? ORDER BY position LIMIT 1",
            (drip_id,)).fetchone()
        next_at = None
        if first_step is not None:
            when = _dt.date.today() + _dt.timedelta(
                days=int(first_step["delay_days"]))
            next_at = when.isoformat()
        try:
            cur = conn.execute(
                """INSERT INTO alumni_drip_enrollments
                       (drip_id, alumni_id, next_send_at)
                   VALUES (?, ?, ?)""",
                (drip_id, alumni_id, next_at))
        except sqlite3.IntegrityError as exc:
            raise ValidationError(
                "Already enrolled in this drip") from exc
        conn.commit()
        row = conn.execute(
            "SELECT * FROM alumni_drip_enrollments "
            "WHERE enrollment_id = ?",
            (cur.lastrowid,)).fetchone()
    _log_action("drip.enroll", actor=actor,
                  drip_id=drip_id, alumni_id=alumni_id)
    return _row_enrollment(row)


def unsubscribe_from_drip(drip_id: int, alumni_id: int, *,
                              actor: str | None = None) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE alumni_drip_enrollments SET status = 'Unsubscribed' "
            "WHERE drip_id = ? AND alumni_id = ?",
            (drip_id, alumni_id))
        conn.commit()
    if cur.rowcount:
        _log_action("drip.unsubscribe", actor=actor,
                      drip_id=drip_id, alumni_id=alumni_id)
    return cur.rowcount > 0


@dataclass
class DripTick:
    enrollment_id: int
    alumni_id: int
    step_id: int
    subject: str
    body: str


def tick_drip(*, today: _dt.date | None = None,
                 send: Callable[[int, str, str], None] | None = None
                 ) -> list[DripTick]:
    """Iterate every Active enrollment whose ``next_send_at`` is
    today or earlier, advance them by one step, schedule the next
    send, and (optionally) hand the rendered subject+body to
    ``send``. Returns the list of ticks dispatched.

    The actual delivery is left to ``send`` so tests can run the
    scheduler without sending real email; the default ``send=None``
    simply records the tick without dispatching."""
    init_db()
    today = today or _dt.date.today()
    out: list[DripTick] = []
    with _connect() as conn:
        rows = conn.execute(
            """SELECT e.* FROM alumni_drip_enrollments e
                 JOIN alumni_drip_campaigns d ON d.drip_id = e.drip_id
                WHERE e.status = 'Active'
                  AND d.status = 'Active'
                  AND e.next_send_at IS NOT NULL
                  AND e.next_send_at <= ?""",
            (today.isoformat(),)).fetchall()
    for r in rows:
        e = _row_enrollment(r)
        steps = list_drip_steps(e.drip_id)
        # current_step is 0-based: the next step to send.
        if e.current_step >= len(steps):
            with _connect() as conn:
                conn.execute(
                    "UPDATE alumni_drip_enrollments "
                    "SET status = 'Completed', next_send_at = NULL "
                    "WHERE enrollment_id = ?", (e.enrollment_id,))
                conn.commit()
            continue
        step = steps[e.current_step]
        subject, body = _resolve_drip_step_content(step, e.alumni_id)
        if send is not None:
            try:
                send(e.alumni_id, subject, body)
            except Exception:
                logger.exception("drip send failed alumni=%s step=%s",
                                   e.alumni_id, step.step_id)
                continue
        out.append(DripTick(
            enrollment_id=e.enrollment_id, alumni_id=e.alumni_id,
            step_id=step.step_id, subject=subject, body=body))
        new_step_idx = e.current_step + 1
        if new_step_idx < len(steps):
            nxt_when = today + _dt.timedelta(
                days=int(steps[new_step_idx].delay_days))
            next_at = nxt_when.isoformat()
            new_status = "Active"
        else:
            next_at = None
            new_status = "Completed"
        with _connect() as conn:
            conn.execute(
                "UPDATE alumni_drip_enrollments "
                "SET current_step = ?, next_send_at = ?, status = ? "
                "WHERE enrollment_id = ?",
                (new_step_idx, next_at, new_status, e.enrollment_id))
            conn.commit()
    return out


def _resolve_drip_step_content(step: DripStep, alumni_id: int
                                    ) -> tuple[str, str]:
    if step.template_id:
        with _connect() as conn:
            r = conn.execute(
                "SELECT * FROM alumni_email_templates "
                "WHERE template_id = ?", (step.template_id,)).fetchone()
        if r is None:
            raise ValidationError(
                f"Drip step #{step.step_id} references missing "
                f"template #{step.template_id}")
        return render_template(_row_template(r), alumni_id)
    a = get_alumnus(alumni_id)
    if a is None:
        raise ValidationError(f"No alumnus #{alumni_id}")
    ctx = _alumnus_context(a)
    return (_render(step.subject or "", ctx),
              _render(step.body or "", ctx))


# ── #22 A/B test send ────────────────────────────────────────────

@dataclass
class ABTest:
    test_id: int
    name: str
    description: str | None
    filters_json: str | None
    sent_at: str | None
    created_at: str


@dataclass
class ABVariant:
    variant_id: int
    test_id: int
    label: str
    subject: str
    body: str
    sent_count: int
    open_count: int
    click_count: int


def _row_ab_test(r: sqlite3.Row) -> ABTest:
    return ABTest(
        test_id=r["test_id"], name=r["name"],
        description=r["description"],
        filters_json=r["filters_json"],
        sent_at=r["sent_at"], created_at=r["created_at"])


def _row_ab_variant(r: sqlite3.Row) -> ABVariant:
    return ABVariant(
        variant_id=r["variant_id"], test_id=r["test_id"],
        label=r["label"], subject=r["subject"], body=r["body"],
        sent_count=int(r["sent_count"]),
        open_count=int(r["open_count"]),
        click_count=int(r["click_count"]))


def create_ab_test(name: str, *,
                      description: str | None = None,
                      filters: dict[str, Any] | None = None,
                      actor: str | None = None) -> ABTest:
    init_db()
    name = (name or "").strip()
    if not name:
        raise ValidationError("A/B test name is required")
    import json as _json
    fjson = _json.dumps(filters) if filters else None
    with _connect() as conn:
        try:
            cur = conn.execute(
                """INSERT INTO alumni_ab_tests
                       (name, description, filters_json)
                   VALUES (?, ?, ?)""",
                (name, (description or "").strip() or None, fjson))
        except sqlite3.IntegrityError as exc:
            raise ValidationError(
                f"A/B test {name!r} already exists") from exc
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_ab_tests WHERE test_id = ?",
            (cur.lastrowid,)).fetchone()
    _log_action("ab.create", actor=actor, name=name)
    return _row_ab_test(r)


def add_ab_variant(test_id: int, *,
                       label: str, subject: str, body: str,
                       actor: str | None = None) -> ABVariant:
    init_db()
    label = (label or "").strip()
    if not label:
        raise ValidationError("Variant label is required")
    if not (subject or "").strip():
        raise ValidationError("Subject is required")
    if not (body or "").strip():
        raise ValidationError("Body is required")
    with _connect() as conn:
        r = conn.execute(
            "SELECT 1 FROM alumni_ab_tests WHERE test_id = ?",
            (test_id,)).fetchone()
        if r is None:
            raise ValidationError(f"No A/B test #{test_id}")
        try:
            cur = conn.execute(
                """INSERT INTO alumni_ab_variants
                       (test_id, label, subject, body)
                   VALUES (?, ?, ?, ?)""",
                (test_id, label, subject.strip(), body))
        except sqlite3.IntegrityError as exc:
            raise ValidationError(
                f"Variant {label!r} already exists for this test"
            ) from exc
        conn.commit()
        row = conn.execute(
            "SELECT * FROM alumni_ab_variants WHERE variant_id = ?",
            (cur.lastrowid,)).fetchone()
    _log_action("ab.variant", actor=actor, test_id=test_id,
                  label=label)
    return _row_ab_variant(row)


def list_ab_variants(test_id: int) -> list[ABVariant]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM alumni_ab_variants WHERE test_id = ? "
            "ORDER BY variant_id", (test_id,)).fetchall()
    return [_row_ab_variant(r) for r in rows]


def assign_ab_audience(test_id: int, *,
                          filters: dict[str, Any] | None = None,
                          actor: str | None = None) -> dict[str, int]:
    """Stably hash each candidate alumnus to a variant. Returns the
    per-variant assignment counts."""
    init_db()
    import hashlib as _h
    variants = list_ab_variants(test_id)
    if not variants:
        raise ValidationError(
            f"A/B test #{test_id} has no variants")
    try:
        audience = list_alumni(**(filters or {}))
    except TypeError as exc:
        raise ValidationError(
            f"Invalid filter for A/B audience: {exc}") from exc
    counts: dict[str, int] = {v.label: 0 for v in variants}
    with _connect() as conn:
        for a in audience:
            h = int(_h.md5(
                f"{test_id}:{a.alumni_id}".encode()).hexdigest(), 16)
            v = variants[h % len(variants)]
            conn.execute(
                """INSERT OR REPLACE INTO alumni_ab_assignments
                       (test_id, alumni_id, variant_id)
                   VALUES (?, ?, ?)""",
                (test_id, a.alumni_id, v.variant_id))
            counts[v.label] += 1
        conn.commit()
    _log_action("ab.assign", actor=actor, test_id=test_id,
                  audience=len(audience))
    return counts


def record_ab_event(test_id: int, alumni_id: int, kind: str, *,
                       actor: str | None = None) -> None:
    """Bump send/open/click counters on the variant the alumnus is
    assigned to. ``kind`` must be 'send' | 'open' | 'click'."""
    init_db()
    if kind not in ("send", "open", "click"):
        raise ValidationError(
            "Kind must be 'send', 'open', or 'click'")
    col = {"send": "sent_count", "open": "open_count",
            "click": "click_count"}[kind]
    with _connect() as conn:
        r = conn.execute(
            "SELECT variant_id FROM alumni_ab_assignments "
            "WHERE test_id = ? AND alumni_id = ?",
            (test_id, alumni_id)).fetchone()
        if r is None:
            return
        conn.execute(
            f"UPDATE alumni_ab_variants SET {col} = {col} + 1 "
            f"WHERE variant_id = ?", (r["variant_id"],))
        conn.commit()
    _log_action(f"ab.{kind}", actor=actor, test_id=test_id,
                  alumni_id=alumni_id)


@dataclass
class ABResult:
    label: str
    sent: int
    opens: int
    clicks: int
    open_rate: float
    click_rate: float


def ab_test_results(test_id: int) -> list[ABResult]:
    init_db()
    out: list[ABResult] = []
    for v in list_ab_variants(test_id):
        opens = v.open_count
        clicks = v.click_count
        sent = max(v.sent_count, 1)
        out.append(ABResult(
            label=v.label, sent=v.sent_count,
            opens=opens, clicks=clicks,
            open_rate=round(100 * opens / sent, 2),
            click_rate=round(100 * clicks / sent, 2)))
    return out


# ── #23 SMS channel ──────────────────────────────────────────────

@dataclass
class SMSMessage:
    sms_id: int
    alumni_id: int
    body: str
    sent_at: str
    status: str
    error: str | None


def _row_sms(r: sqlite3.Row) -> SMSMessage:
    return SMSMessage(
        sms_id=r["sms_id"], alumni_id=r["alumni_id"],
        body=r["body"], sent_at=r["sent_at"],
        status=r["status"], error=r["error"])


# Pluggable SMS sender. Tests can monkey-patch this. Default is a
# no-op recorder: messages are stamped 'Sent' but nothing leaves the
# machine.
_sms_sender: Callable[[str, str], None] | None = None


def set_sms_sender(fn: Callable[[str, str], None] | None) -> None:
    """Install a callable ``fn(phone, body)`` invoked from
    :func:`send_sms_to_alumnus`. Pass ``None`` to clear and fall back
    to the default no-op."""
    global _sms_sender
    _sms_sender = fn


def send_sms_to_alumnus(alumni_id: int, body: str, *,
                           actor: str | None = None) -> SMSMessage:
    init_db()
    if not (body or "").strip():
        raise ValidationError("SMS body is required")
    a = get_alumnus(alumni_id)
    if a is None:
        raise ValidationError(f"No alumnus #{alumni_id}")
    prefs = get_channel_prefs(alumni_id)
    if not prefs.opt_in_sms:
        raise ValidationError(
            "Alumnus has not opted-in to SMS")
    phone = a.phone or ""
    if not phone:
        raise ValidationError("No phone on file")
    status = "Sent"
    error: str | None = None
    if _sms_sender is not None:
        try:
            _sms_sender(phone, body)
        except Exception as exc:
            status = "Failed"
            error = str(exc)[:240]
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO alumni_sms_messages
                   (alumni_id, body, status, error)
               VALUES (?, ?, ?, ?)""",
            (alumni_id, body.strip(), status, error))
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_sms_messages WHERE sms_id = ?",
            (cur.lastrowid,)).fetchone()
    _log_action("sms.send", actor=actor, alumni_id=alumni_id,
                  status=status)
    return _row_sms(r)


def list_sms_for(alumni_id: int) -> list[SMSMessage]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM alumni_sms_messages "
            "WHERE alumni_id = ? ORDER BY sent_at DESC",
            (alumni_id,)).fetchall()
    return [_row_sms(r) for r in rows]


# ── #24 Postal mail merge ────────────────────────────────────────

@dataclass
class PostalLetter:
    letter_id: int
    alumni_id: int
    subject: str
    body: str
    pdf_path: str | None
    generated_at: str


def _row_letter(r: sqlite3.Row) -> PostalLetter:
    return PostalLetter(
        letter_id=r["letter_id"], alumni_id=r["alumni_id"],
        subject=r["subject"], body=r["body"],
        pdf_path=r["pdf_path"], generated_at=r["generated_at"])


def generate_postal_letter(alumni_id: int, *,
                              subject: str, body: str,
                              out_dir: str | None = None,
                              actor: str | None = None
                              ) -> PostalLetter:
    """Render a letter against ``alumni_id``, persist its text + a
    plain ``.txt`` artefact in ``out_dir`` (or current dir), and
    return the row. We deliberately don't depend on a PDF library:
    consumers that want PDF can post-process the saved ``.txt``."""
    init_db()
    from pathlib import Path as _Path
    a = get_alumnus(alumni_id)
    if a is None:
        raise ValidationError(f"No alumnus #{alumni_id}")
    if not a.address:
        raise ValidationError(
            f"No postal address on file for #{alumni_id}")
    ctx = _alumnus_context(a)
    s = _render(subject, ctx)
    b = _render(body, ctx)
    out_path: str | None = None
    if out_dir:
        d = _Path(out_dir)
        try:
            d.mkdir(parents=True, exist_ok=True)
            p = d / (
                f"letter-{alumni_id}-"
                f"{int(_dt.datetime.now().timestamp())}.txt")
            p.write_text(
                f"To:\n{a.full_name}\n{a.address}\n\n"
                f"Subject: {s}\n\n{b}\n",
                encoding="utf-8")
        except OSError as exc:
            raise IntegrationError(
                f"Could not write letter to {d}: {exc}") from exc
        out_path = str(p)
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO alumni_postal_letters
                   (alumni_id, subject, body, pdf_path)
               VALUES (?, ?, ?, ?)""",
            (alumni_id, s, b, out_path))
        conn.commit()
        row = conn.execute(
            "SELECT * FROM alumni_postal_letters WHERE letter_id = ?",
            (cur.lastrowid,)).fetchone()
    _log_action("postal.generate", actor=actor,
                  alumni_id=alumni_id, path=out_path)
    return _row_letter(row)


def generate_postal_bulk(filters: dict[str, Any], *,
                            subject: str, body: str,
                            out_dir: str,
                            actor: str | None = None
                            ) -> list[PostalLetter]:
    """Mail-merge bulk-render letters for everyone matching
    ``filters`` who also has a postal address."""
    init_db()
    out: list[PostalLetter] = []
    try:
        audience = list_alumni(**filters)
    except TypeError as exc:
        raise ValidationError(
            f"Invalid filter for bulk postal: {exc}") from exc
    for a in audience:
        if not a.address:
            continue
        try:
            out.append(generate_postal_letter(
                a.alumni_id, subject=subject, body=body,
                out_dir=out_dir, actor=actor))
        except ValidationError:
            continue
    _log_action("postal.bulk", actor=actor,
                  count=len(out), out_dir=out_dir)
    return out


# ── #25 Newsletter issues ────────────────────────────────────────

@dataclass
class Newsletter:
    newsletter_id: int
    issue: str
    title: str
    status: str
    published_at: str | None
    distribution_filters_json: str | None
    created_at: str


@dataclass
class NewsletterSection:
    section_id: int
    newsletter_id: int
    position: int
    heading: str
    body: str


def _row_newsletter(r: sqlite3.Row) -> Newsletter:
    return Newsletter(
        newsletter_id=r["newsletter_id"], issue=r["issue"],
        title=r["title"], status=r["status"],
        published_at=r["published_at"],
        distribution_filters_json=r["distribution_filters_json"],
        created_at=r["created_at"])


def _row_section(r: sqlite3.Row) -> NewsletterSection:
    return NewsletterSection(
        section_id=r["section_id"],
        newsletter_id=r["newsletter_id"],
        position=int(r["position"]),
        heading=r["heading"], body=r["body"])


def create_newsletter(issue: str, title: str, *,
                          actor: str | None = None) -> Newsletter:
    init_db()
    issue = (issue or "").strip()
    if not issue:
        raise ValidationError("Issue label is required")
    if not (title or "").strip():
        raise ValidationError("Title is required")
    with _connect() as conn:
        try:
            cur = conn.execute(
                """INSERT INTO alumni_newsletters
                       (issue, title) VALUES (?, ?)""",
                (issue, title.strip()))
        except sqlite3.IntegrityError as exc:
            raise ValidationError(
                f"Newsletter issue {issue!r} already exists"
            ) from exc
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_newsletters "
            "WHERE newsletter_id = ?", (cur.lastrowid,)).fetchone()
    _log_action("newsletter.create", actor=actor, issue=issue)
    return _row_newsletter(r)


def add_newsletter_section(newsletter_id: int, *,
                                heading: str, body: str,
                                position: int | None = None,
                                actor: str | None = None
                                ) -> NewsletterSection:
    init_db()
    if not (heading or "").strip():
        raise ValidationError("Heading is required")
    if not (body or "").strip():
        raise ValidationError("Body is required")
    with _connect() as conn:
        r = conn.execute(
            "SELECT 1 FROM alumni_newsletters WHERE newsletter_id = ?",
            (newsletter_id,)).fetchone()
        if r is None:
            raise ValidationError(
                f"No newsletter #{newsletter_id}")
        if position is None:
            r2 = conn.execute(
                "SELECT COALESCE(MAX(position), 0) + 1 AS p "
                "FROM alumni_newsletter_sections "
                "WHERE newsletter_id = ?",
                (newsletter_id,)).fetchone()
            position = int(r2["p"])
        try:
            cur = conn.execute(
                """INSERT INTO alumni_newsletter_sections
                       (newsletter_id, position, heading, body)
                   VALUES (?, ?, ?, ?)""",
                (newsletter_id, position, heading.strip(), body))
        except sqlite3.IntegrityError as exc:
            raise ValidationError(
                f"Position {position} already used") from exc
        conn.commit()
        row = conn.execute(
            "SELECT * FROM alumni_newsletter_sections "
            "WHERE section_id = ?", (cur.lastrowid,)).fetchone()
    _log_action("newsletter.section", actor=actor,
                  newsletter_id=newsletter_id, position=position)
    return _row_section(row)


def list_newsletters() -> list[Newsletter]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM alumni_newsletters "
            "ORDER BY created_at DESC").fetchall()
    return [_row_newsletter(r) for r in rows]


def list_newsletter_sections(newsletter_id: int
                                  ) -> list[NewsletterSection]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM alumni_newsletter_sections "
            "WHERE newsletter_id = ? ORDER BY position",
            (newsletter_id,)).fetchall()
    return [_row_section(r) for r in rows]


def publish_newsletter(newsletter_id: int, *,
                          distribution_filters: dict[str, Any]
                              | None = None,
                          actor: str | None = None) -> Newsletter:
    init_db()
    import json as _json
    fjson = _json.dumps(distribution_filters) \
        if distribution_filters else None
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        cur = conn.execute(
            """UPDATE alumni_newsletters
                  SET status = 'Published',
                      published_at = ?,
                      distribution_filters_json = ?
                WHERE newsletter_id = ?""",
            (now, fjson, newsletter_id))
        if cur.rowcount == 0:
            raise ValidationError(
                f"No newsletter #{newsletter_id}")
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_newsletters "
            "WHERE newsletter_id = ?", (newsletter_id,)).fetchone()
    _log_action("newsletter.publish", actor=actor,
                  newsletter_id=newsletter_id)
    return _row_newsletter(r)


def render_newsletter_html(newsletter_id: int) -> str:
    n = next((x for x in list_newsletters()
                if x.newsletter_id == newsletter_id), None)
    if n is None:
        raise ValidationError(
            f"No newsletter #{newsletter_id}")
    parts = [f"<h1>{n.title}</h1>",
                f"<p><em>{n.issue}</em></p>"]
    for s in list_newsletter_sections(newsletter_id):
        parts.append(f"<h2>{s.heading}</h2>")
        parts.append(f"<div>{s.body}</div>")
    return "\n".join(parts)


def newsletter_audience(newsletter_id: int) -> list[Alumnus]:
    init_db()
    import json as _json
    with _connect() as conn:
        r = conn.execute(
            "SELECT distribution_filters_json FROM alumni_newsletters "
            "WHERE newsletter_id = ?", (newsletter_id,)).fetchone()
    if r is None:
        raise NotFoundError(f"No newsletter #{newsletter_id}")
    raw = r["distribution_filters_json"]
    if not raw:
        return list_alumni()
    try:
        filters = _json.loads(raw)
    except (ValueError, TypeError) as exc:
        # Stored JSON is corrupt — log loudly and fall back to no
        # filtering rather than 500-ing the audience tab.
        logger.warning(
            "Newsletter #%d has malformed filters_json: %s",
            newsletter_id, exc)
        return list_alumni()
    if not isinstance(filters, dict):
        logger.warning(
            "Newsletter #%d filters_json is not an object: %r",
            newsletter_id, type(filters))
        return list_alumni()
    try:
        return list_alumni(**filters)
    except TypeError as exc:
        # Stored filter key no longer exists on list_alumni — surface
        # as a ValidationError so the UI can show "stale filter" to
        # the user rather than crashing.
        raise ValidationError(
            f"Newsletter #{newsletter_id} stored filters are no "
            f"longer compatible: {exc}") from exc


# ── #26 Open/click tracking ──────────────────────────────────────

def _new_track_token() -> str:
    return secrets.token_urlsafe(16)


def create_tracking_pixel(alumni_id: int | None = None, *,
                              campaign_ref: str | None = None) -> str:
    """Mint a unique pixel token. Hosts can serve a 1×1 image at
    ``/track/pixel/<token>`` and call :func:`record_track_event` with
    kind='open' on hit."""
    init_db()
    token = _new_track_token()
    with _connect() as conn:
        conn.execute(
            """INSERT INTO alumni_track_links
                   (token, alumni_id, kind, campaign_ref)
               VALUES (?, ?, 'open', ?)""",
            (token, alumni_id,
             (campaign_ref or "").strip() or None))
        conn.commit()
    return token


def create_tracked_link(target_url: str, *,
                            alumni_id: int | None = None,
                            campaign_ref: str | None = None) -> str:
    """Mint a unique redirect token. The host should serve
    ``/track/click/<token>`` by recording a 'click' event then
    302-redirecting to ``target_url``."""
    init_db()
    if not (target_url or "").strip():
        raise ValidationError("target_url is required")
    token = _new_track_token()
    with _connect() as conn:
        conn.execute(
            """INSERT INTO alumni_track_links
                   (token, alumni_id, kind, target_url, campaign_ref)
               VALUES (?, ?, 'click', ?, ?)""",
            (token, alumni_id, target_url.strip(),
             (campaign_ref or "").strip() or None))
        conn.commit()
    return token


def record_track_event(token: str, kind: str, *,
                          payload: str | None = None) -> None:
    init_db()
    if kind not in TRACK_KINDS:
        raise ValidationError(
            f"Kind must be one of: {', '.join(TRACK_KINDS)}")
    with _connect() as conn:
        link = conn.execute(
            "SELECT alumni_id FROM alumni_track_links "
            "WHERE token = ?", (token,)).fetchone()
        alumni_id = link["alumni_id"] if link else None
        conn.execute(
            """INSERT INTO alumni_track_events
                   (token, alumni_id, kind, payload)
               VALUES (?, ?, ?, ?)""",
            (token, alumni_id, kind, payload))
        conn.commit()


def resolve_tracked_link(token: str) -> tuple[str, str | None]:
    """Return ``(kind, target_url)`` for a tracking token, raising
    if unknown. ``target_url`` is ``None`` for pixel tokens."""
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT kind, target_url FROM alumni_track_links "
            "WHERE token = ?", (token,)).fetchone()
    if r is None:
        raise ValidationError("Unknown tracking token")
    return r["kind"], r["target_url"]


@dataclass
class TrackingSummary:
    campaign_ref: str | None
    sends: int
    opens: int
    clicks: int
    unique_opens: int


def tracking_summary(*, campaign_ref: str | None = None
                          ) -> TrackingSummary:
    """Aggregate counts. ``campaign_ref`` filters to one campaign tag
    (the column on ``alumni_track_links``); ``None`` aggregates across
    every link."""
    init_db()
    with _connect() as conn:
        if campaign_ref:
            tokens_rows = conn.execute(
                "SELECT token FROM alumni_track_links "
                "WHERE campaign_ref = ?", (campaign_ref,)).fetchall()
            tokens = [r["token"] for r in tokens_rows]
            if not tokens:
                return TrackingSummary(
                    campaign_ref=campaign_ref, sends=0, opens=0,
                    clicks=0, unique_opens=0)
            placeholders = ",".join("?" * len(tokens))
            sends = int(conn.execute(
                f"SELECT COUNT(*) FROM alumni_track_events "
                f"WHERE kind = 'send' AND token IN ({placeholders})",
                tokens).fetchone()[0])
            opens = int(conn.execute(
                f"SELECT COUNT(*) FROM alumni_track_events "
                f"WHERE kind = 'open' AND token IN ({placeholders})",
                tokens).fetchone()[0])
            clicks = int(conn.execute(
                f"SELECT COUNT(*) FROM alumni_track_events "
                f"WHERE kind = 'click' AND token IN ({placeholders})",
                tokens).fetchone()[0])
            uniq = int(conn.execute(
                f"SELECT COUNT(DISTINCT alumni_id) "
                f"FROM alumni_track_events "
                f"WHERE kind = 'open' AND alumni_id IS NOT NULL "
                f"  AND token IN ({placeholders})",
                tokens).fetchone()[0])
        else:
            sends = int(conn.execute(
                "SELECT COUNT(*) FROM alumni_track_events "
                "WHERE kind = 'send'").fetchone()[0])
            opens = int(conn.execute(
                "SELECT COUNT(*) FROM alumni_track_events "
                "WHERE kind = 'open'").fetchone()[0])
            clicks = int(conn.execute(
                "SELECT COUNT(*) FROM alumni_track_events "
                "WHERE kind = 'click'").fetchone()[0])
            uniq = int(conn.execute(
                "SELECT COUNT(DISTINCT alumni_id) "
                "FROM alumni_track_events "
                "WHERE kind = 'open' "
                "  AND alumni_id IS NOT NULL").fetchone()[0])
    return TrackingSummary(
        campaign_ref=campaign_ref, sends=sends, opens=opens,
        clicks=clicks, unique_opens=uniq)


# ════════════════════════════════════════════════════════════════════
# Events / fundraising / outcomes extensions (items 27–40).
# ════════════════════════════════════════════════════════════════════

DONOR_STAGES: tuple[str, ...] = (
    "Identification", "Qualification", "Cultivation",
    "Solicitation", "Stewardship", "Disqualified",
)
RECURRING_FREQS: tuple[str, ...] = (
    "Monthly", "Quarterly", "Annually",
)
RECURRING_STATUSES: tuple[str, ...] = (
    "Active", "Paused", "Cancelled", "Failed",
)
BEQUEST_STATUSES: tuple[str, ...] = (
    "Pledged", "Confirmed", "Realised", "Withdrawn",
)
NEET_STATUSES: tuple[str, ...] = (
    "In Education", "In Employment", "In Training",
    "Self-Employed", "Other Positive", "NEET", "Unknown",
)
RUSSELL_GROUP_UNIVERSITIES: tuple[str, ...] = (
    "University of Birmingham", "University of Bristol",
    "University of Cambridge", "Cardiff University",
    "Durham University", "University of Edinburgh",
    "University of Exeter", "University of Glasgow",
    "Imperial College London", "King's College London",
    "University of Leeds", "University of Liverpool",
    "London School of Economics and Political Science",
    "University of Manchester", "Newcastle University",
    "University of Nottingham", "University of Oxford",
    "Queen Mary University of London", "Queen's University Belfast",
    "University of Sheffield", "University of Southampton",
    "University College London", "University of Warwick",
    "University of York",
)
OXBRIDGE_UNIVERSITIES: tuple[str, ...] = (
    "University of Cambridge", "University of Oxford",
)
PG_QUALIFICATIONS: tuple[str, ...] = (
    "MSc", "MA", "MEng", "MPhil", "MBA", "LLM", "MRes", "PhD",
    "DPhil", "EdD",
)


_SCHEMA_EVENTS_EXT = """
CREATE TABLE IF NOT EXISTS alumni_event_refunds (
    refund_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id     INTEGER NOT NULL,
    alumni_id    INTEGER NOT NULL,
    amount_pence INTEGER NOT NULL,
    reason       TEXT,
    refunded_at  TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (event_id)  REFERENCES alumni_events(event_id)
        ON DELETE CASCADE,
    FOREIGN KEY (alumni_id) REFERENCES alumni(alumni_id)
        ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_aerf_event
    ON alumni_event_refunds(event_id);
"""

_SCHEMA_FUNDRAISING_EXT = """
CREATE TABLE IF NOT EXISTS alumni_gift_aid_declarations (
    declaration_id INTEGER PRIMARY KEY AUTOINCREMENT,
    alumni_id      INTEGER NOT NULL,
    valid_from     TEXT NOT NULL,
    valid_until    TEXT,
    full_name      TEXT NOT NULL,
    address        TEXT NOT NULL,
    postcode       TEXT NOT NULL,
    signed_at      TEXT NOT NULL DEFAULT (datetime('now')),
    withdrawn_at   TEXT,
    notes          TEXT,
    FOREIGN KEY (alumni_id) REFERENCES alumni(alumni_id)
        ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_aga_alumni
    ON alumni_gift_aid_declarations(alumni_id);

CREATE TABLE IF NOT EXISTS alumni_recurring_donations (
    schedule_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    alumni_id      INTEGER NOT NULL,
    campaign_id    INTEGER,
    amount_pence   INTEGER NOT NULL,
    frequency      TEXT NOT NULL DEFAULT 'Monthly',
    next_charge_on TEXT NOT NULL,
    status         TEXT NOT NULL DEFAULT 'Active',
    failure_count  INTEGER NOT NULL DEFAULT 0,
    fund_code      TEXT,
    payment_method TEXT,
    started_on     TEXT NOT NULL DEFAULT (date('now')),
    cancelled_on   TEXT,
    notes          TEXT,
    FOREIGN KEY (alumni_id)   REFERENCES alumni(alumni_id)
        ON DELETE CASCADE,
    FOREIGN KEY (campaign_id) REFERENCES alumni_campaigns(campaign_id)
        ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_arec_alumni
    ON alumni_recurring_donations(alumni_id);
CREATE INDEX IF NOT EXISTS idx_arec_next
    ON alumni_recurring_donations(next_charge_on);

CREATE TABLE IF NOT EXISTS alumni_donor_pipeline (
    alumni_id     INTEGER PRIMARY KEY,
    stage         TEXT NOT NULL DEFAULT 'Identification',
    owner_staff_id TEXT,
    next_action   TEXT,
    next_action_on TEXT,
    capacity_pence INTEGER,
    notes         TEXT,
    updated_at    TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (alumni_id) REFERENCES alumni(alumni_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS alumni_donor_pipeline_log (
    log_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    alumni_id     INTEGER NOT NULL,
    from_stage    TEXT,
    to_stage      TEXT NOT NULL,
    changed_at    TEXT NOT NULL DEFAULT (datetime('now')),
    changed_by    TEXT,
    notes         TEXT,
    FOREIGN KEY (alumni_id) REFERENCES alumni(alumni_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS alumni_funds (
    fund_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    code         TEXT NOT NULL UNIQUE COLLATE NOCASE,
    name         TEXT NOT NULL,
    restricted   INTEGER NOT NULL DEFAULT 0,
    description  TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS alumni_bequests (
    bequest_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    alumni_id      INTEGER NOT NULL,
    estimated_pence INTEGER,
    will_mention   INTEGER NOT NULL DEFAULT 1,
    executor_name  TEXT,
    executor_email TEXT,
    executor_phone TEXT,
    confirmed_on   TEXT,
    realised_on    TEXT,
    status         TEXT NOT NULL DEFAULT 'Pledged',
    notes          TEXT,
    created_at     TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (alumni_id) REFERENCES alumni(alumni_id)
        ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_abq_alumni
    ON alumni_bequests(alumni_id);

CREATE TABLE IF NOT EXISTS alumni_matched_giving_schemes (
    scheme_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    employer     TEXT NOT NULL UNIQUE COLLATE NOCASE,
    multiplier   REAL NOT NULL DEFAULT 1.0,
    cap_pence    INTEGER,
    notes        TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

_SCHEMA_OUTCOMES_EXT = """
CREATE TABLE IF NOT EXISTS alumni_neet_checks (
    check_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    alumni_id     INTEGER NOT NULL,
    months_after  INTEGER NOT NULL,
    checked_on    TEXT NOT NULL DEFAULT (date('now')),
    status        TEXT NOT NULL DEFAULT 'Unknown',
    notes         TEXT,
    UNIQUE(alumni_id, months_after),
    FOREIGN KEY (alumni_id) REFERENCES alumni(alumni_id)
        ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_aneet_alumni
    ON alumni_neet_checks(alumni_id);
"""

_RSVP_NEW_COLUMNS: tuple[tuple[str, str], ...] = (
    ("amount_paid_pence", "INTEGER NOT NULL DEFAULT 0"),
    ("checkin_token",     "TEXT"),
    ("checkin_at",        "TEXT"),
    ("waitlisted",        "INTEGER NOT NULL DEFAULT 0"),
)

_DONATION_NEW_COLUMNS: tuple[tuple[str, str], ...] = (
    ("fund_code",         "TEXT"),
    ("matched_pence",     "INTEGER NOT NULL DEFAULT 0"),
    ("matched_scheme_id", "INTEGER"),
)

_ALUMNI_NEW_COLUMNS_V2: tuple[tuple[str, str], ...] = (
    ("first_gen_he", "INTEGER NOT NULL DEFAULT 0"),
)


def _init_events_funding_outcomes() -> None:
    with _connect() as conn:
        conn.executescript(_SCHEMA_EVENTS_EXT)
        conn.executescript(_SCHEMA_FUNDRAISING_EXT)
        conn.executescript(_SCHEMA_OUTCOMES_EXT)
        for table, cols in (
                ("alumni_event_rsvps", _RSVP_NEW_COLUMNS),
                ("alumni_donations",   _DONATION_NEW_COLUMNS),
                ("alumni",             _ALUMNI_NEW_COLUMNS_V2)):
            existing = {row[1] for row in conn.execute(
                f"PRAGMA table_info({table})").fetchall()}
            for col, decl in cols:
                if col not in existing:
                    conn.execute(
                        f"ALTER TABLE {table} ADD COLUMN {col} {decl}")


_original_init_db_v4 = init_db


def init_db() -> None:  # type: ignore[no-redef]
    already = _DB_READY
    _original_init_db_v4()
    if not already:
        _init_events_funding_outcomes()


# ── #27 Event ticketing, waitlist, refunds ───────────────────────

@dataclass
class TicketedRsvp:
    rsvp_id: int
    event_id: int
    alumni_id: int
    status: str
    waitlisted: bool
    guests: int
    amount_paid_pence: int


def _row_ticketed(r: sqlite3.Row) -> TicketedRsvp:
    return TicketedRsvp(
        rsvp_id=r["rsvp_id"], event_id=r["event_id"],
        alumni_id=r["alumni_id"], status=r["status"],
        waitlisted=bool(_opt(r, "waitlisted") or 0),
        guests=int(r["guests"]),
        amount_paid_pence=int(_opt(r, "amount_paid_pence") or 0))


def buy_ticket(event_id: int, alumni_id: int, *,
                  guests: int = 0,
                  amount_paid_pence: int | None = None,
                  actor: str | None = None) -> TicketedRsvp:
    """Sell a ticket: creates/updates the RSVP to 'Accepted', stamps
    the amount paid, and auto-waitlists if the event capacity is
    full. The caller decides ``amount_paid_pence`` (which may differ
    from the event's listed ``cost_pence`` for early-bird or comp
    tickets); when omitted it defaults to ``cost_pence * (1+guests)``."""
    init_db()
    if guests < 0:
        raise ValidationError("guests must be ≥ 0")
    with _connect() as conn:
        ev = conn.execute(
            "SELECT capacity, cost_pence FROM alumni_events "
            "WHERE event_id = ?", (event_id,)).fetchone()
        if ev is None:
            raise ValidationError(f"No event #{event_id}")
        if amount_paid_pence is None:
            amount_paid_pence = int(ev["cost_pence"] or 0) * (1 + guests)
        seats_used = conn.execute(
            "SELECT COALESCE(SUM(1 + guests), 0) FROM alumni_event_rsvps "
            "WHERE event_id = ? AND status = 'Accepted' "
            "  AND COALESCE(waitlisted, 0) = 0",
            (event_id,)).fetchone()[0]
        capacity = ev["capacity"]
        waitlist = (capacity is not None
                       and seats_used + 1 + guests > int(capacity))
        existing = conn.execute(
            "SELECT * FROM alumni_event_rsvps "
            "WHERE event_id = ? AND alumni_id = ?",
            (event_id, alumni_id)).fetchone()
        if existing:
            conn.execute(
                """UPDATE alumni_event_rsvps SET
                       status = 'Accepted',
                       guests = ?,
                       amount_paid_pence = ?,
                       waitlisted = ?
                   WHERE rsvp_id = ?""",
                (guests, amount_paid_pence,
                 1 if waitlist else 0, existing["rsvp_id"]))
            rsvp_id = existing["rsvp_id"]
        else:
            cur = conn.execute(
                """INSERT INTO alumni_event_rsvps
                       (event_id, alumni_id, status, guests,
                        amount_paid_pence, waitlisted)
                   VALUES (?, ?, 'Accepted', ?, ?, ?)""",
                (event_id, alumni_id, guests,
                 amount_paid_pence, 1 if waitlist else 0))
            rsvp_id = cur.lastrowid
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_event_rsvps WHERE rsvp_id = ?",
            (rsvp_id,)).fetchone()
    _log_action("event.ticket", actor=actor, event_id=event_id,
                  alumni_id=alumni_id, amount_pence=amount_paid_pence,
                  waitlisted=waitlist)
    return _row_ticketed(r)


def promote_from_waitlist(event_id: int, *,
                             actor: str | None = None
                             ) -> list[TicketedRsvp]:
    """Promote waitlisted RSVPs (oldest first) into the open ticket
    pool while capacity allows. Returns the newly seated RSVPs."""
    init_db()
    promoted: list[TicketedRsvp] = []
    with _connect() as conn:
        ev = conn.execute(
            "SELECT capacity FROM alumni_events WHERE event_id = ?",
            (event_id,)).fetchone()
        if ev is None or ev["capacity"] is None:
            return []
        capacity = int(ev["capacity"])
        seats_used = int(conn.execute(
            "SELECT COALESCE(SUM(1 + guests), 0) FROM alumni_event_rsvps "
            "WHERE event_id = ? AND status = 'Accepted' "
            "  AND COALESCE(waitlisted, 0) = 0",
            (event_id,)).fetchone()[0])
        waitlist = conn.execute(
            "SELECT * FROM alumni_event_rsvps "
            "WHERE event_id = ? AND COALESCE(waitlisted, 0) = 1 "
            "ORDER BY created_at, rsvp_id", (event_id,)).fetchall()
        for r in waitlist:
            need = 1 + int(r["guests"])
            if seats_used + need > capacity:
                continue
            conn.execute(
                "UPDATE alumni_event_rsvps SET waitlisted = 0 "
                "WHERE rsvp_id = ?", (r["rsvp_id"],))
            seats_used += need
            promoted.append(_row_ticketed(r))
        conn.commit()
    if promoted:
        _log_action("event.waitlist.promote", actor=actor,
                      event_id=event_id, count=len(promoted))
    return promoted


@dataclass
class EventRefund:
    refund_id: int
    event_id: int
    alumni_id: int
    amount_pence: int
    reason: str | None
    refunded_at: str


def refund_ticket(event_id: int, alumni_id: int, *,
                     amount_pence: int | None = None,
                     reason: str | None = None,
                     actor: str | None = None) -> EventRefund:
    """Record a refund row and zero-out the corresponding ticket's
    paid amount. ``amount_pence=None`` refunds the full amount on
    file."""
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT rsvp_id, amount_paid_pence FROM alumni_event_rsvps "
            "WHERE event_id = ? AND alumni_id = ?",
            (event_id, alumni_id)).fetchone()
        if r is None:
            raise ValidationError("No matching RSVP")
        paid = int(_opt(r, "amount_paid_pence") or 0)
        amt = paid if amount_pence is None else int(amount_pence)
        if amt <= 0 or amt > paid:
            raise ValidationError(
                f"Refund amount must be between 1 and {paid}p")
        cur = conn.execute(
            """INSERT INTO alumni_event_refunds
                   (event_id, alumni_id, amount_pence, reason)
               VALUES (?, ?, ?, ?)""",
            (event_id, alumni_id, amt,
             (reason or "").strip() or None))
        conn.execute(
            "UPDATE alumni_event_rsvps "
            "SET amount_paid_pence = amount_paid_pence - ? "
            "WHERE rsvp_id = ?", (amt, r["rsvp_id"]))
        conn.commit()
        row = conn.execute(
            "SELECT * FROM alumni_event_refunds WHERE refund_id = ?",
            (cur.lastrowid,)).fetchone()
    _log_action("event.refund", actor=actor, event_id=event_id,
                  alumni_id=alumni_id, amount_pence=amt)
    return EventRefund(
        refund_id=row["refund_id"], event_id=row["event_id"],
        alumni_id=row["alumni_id"],
        amount_pence=int(row["amount_pence"]),
        reason=row["reason"], refunded_at=row["refunded_at"])


def list_event_refunds(event_id: int) -> list[EventRefund]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM alumni_event_refunds WHERE event_id = ? "
            "ORDER BY refunded_at DESC", (event_id,)).fetchall()
    return [EventRefund(
        refund_id=r["refund_id"], event_id=r["event_id"],
        alumni_id=r["alumni_id"],
        amount_pence=int(r["amount_pence"]),
        reason=r["reason"], refunded_at=r["refunded_at"])
            for r in rows]


@dataclass
class EventFinance:
    event_id: int
    tickets_sold: int
    seats_used: int
    waitlist: int
    gross_pence: int
    refunds_pence: int
    net_pence: int


def event_finance(event_id: int) -> EventFinance:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            """SELECT
                 COUNT(*) FILTER (
                   WHERE status='Accepted'
                     AND COALESCE(waitlisted,0)=0)  AS tickets,
                 COALESCE(SUM(CASE WHEN status='Accepted'
                                AND COALESCE(waitlisted,0)=0
                              THEN 1 + guests ELSE 0 END), 0) AS seats,
                 COUNT(*) FILTER (
                   WHERE COALESCE(waitlisted,0)=1) AS waitlist,
                 COALESCE(SUM(amount_paid_pence), 0) AS gross
               FROM alumni_event_rsvps WHERE event_id = ?""",
            (event_id,)).fetchone()
        refunds = int(conn.execute(
            "SELECT COALESCE(SUM(amount_pence), 0) "
            "FROM alumni_event_refunds WHERE event_id = ?",
            (event_id,)).fetchone()[0])
    gross = int(r["gross"])
    return EventFinance(
        event_id=event_id, tickets_sold=int(r["tickets"]),
        seats_used=int(r["seats"]), waitlist=int(r["waitlist"]),
        gross_pence=gross, refunds_pence=refunds,
        net_pence=gross - refunds)


# ── #28 QR check-in ──────────────────────────────────────────────

def issue_checkin_token(rsvp_id: int, *,
                            actor: str | None = None) -> str:
    """Mint a unique check-in token for one RSVP. Idempotent — if a
    token already exists it is returned unchanged."""
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT checkin_token FROM alumni_event_rsvps "
            "WHERE rsvp_id = ?", (rsvp_id,)).fetchone()
        if r is None:
            raise ValidationError(f"No RSVP #{rsvp_id}")
        existing = _opt(r, "checkin_token")
        if existing:
            return existing
        token = secrets.token_urlsafe(12)
        conn.execute(
            "UPDATE alumni_event_rsvps SET checkin_token = ? "
            "WHERE rsvp_id = ?", (token, rsvp_id))
        conn.commit()
    _log_action("event.checkin.token", actor=actor, rsvp_id=rsvp_id)
    return token


def issue_event_checkin_tokens(event_id: int, *,
                                    actor: str | None = None) -> int:
    """Bulk-issue tokens for every accepted, non-waitlisted RSVP on
    an event that doesn't already have one. Returns count minted."""
    init_db()
    minted = 0
    with _connect() as conn:
        rows = conn.execute(
            "SELECT rsvp_id FROM alumni_event_rsvps "
            "WHERE event_id = ? AND status = 'Accepted' "
            "  AND COALESCE(waitlisted, 0) = 0 "
            "  AND (checkin_token IS NULL OR checkin_token = '')",
            (event_id,)).fetchall()
        for r in rows:
            token = secrets.token_urlsafe(12)
            conn.execute(
                "UPDATE alumni_event_rsvps SET checkin_token = ? "
                "WHERE rsvp_id = ?", (token, r["rsvp_id"]))
            minted += 1
        conn.commit()
    _log_action("event.checkin.bulk_token", actor=actor,
                  event_id=event_id, minted=minted)
    return minted


@dataclass
class CheckinResult:
    rsvp_id: int
    event_id: int
    alumni_id: int
    already_checked_in: bool
    checked_in_at: str


def check_in_by_token(token: str, *,
                         actor: str | None = None) -> CheckinResult:
    """Scan a check-in token: mark ``attended=1`` and stamp
    ``checkin_at``. If already checked in, returns the existing
    record without modification."""
    init_db()
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM alumni_event_rsvps "
            "WHERE checkin_token = ?", (token,)).fetchone()
        if r is None:
            raise ValidationError("Unknown check-in token")
        already = bool(_opt(r, "checkin_at"))
        if not already:
            conn.execute(
                "UPDATE alumni_event_rsvps SET attended = 1, "
                "    checkin_at = ? WHERE rsvp_id = ?",
                (now, r["rsvp_id"]))
            conn.commit()
    _log_action("event.checkin", actor=actor,
                  rsvp_id=r["rsvp_id"], event_id=r["event_id"],
                  already=already)
    return CheckinResult(
        rsvp_id=r["rsvp_id"], event_id=r["event_id"],
        alumni_id=r["alumni_id"], already_checked_in=already,
        checked_in_at=_opt(r, "checkin_at") or now)


# ── #29 Auto-feedback surveys on event close ─────────────────────

def close_event_with_feedback(event_id: int, *,
                                  survey_questions: list[dict[str, Any]]
                                  | None = None,
                                  invite_actor: str | None = None
                                  ) -> tuple[Event, Survey]:
    """Mark the event as ``Completed`` and auto-create a survey whose
    invitations are sent to every alumnus who actually attended.
    ``survey_questions`` follows the same shape used by
    :func:`create_survey`; a sensible default is supplied if omitted."""
    init_db()
    ev = get_event(event_id)
    if ev is None:
        raise ValidationError(f"No event #{event_id}")
    if "Completed" not in EVENT_STATUSES:
        raise ValidationError("'Completed' event status is not configured")
    update_event(event_id, {"status": "Completed"})
    questions = survey_questions or [
        {"key": "overall", "type": "freeform",
            "label": "Overall, how was the event? (1-5 or free text)"},
        {"key": "comments", "type": "freeform",
            "label": "Comments / what could be better?"},
    ]
    survey = create_survey(
        name=f"Feedback — {ev.name}",
        description=(
            f"Auto-generated feedback survey for event #{event_id}."),
        questions=questions)
    with _connect() as conn:
        rows = conn.execute(
            "SELECT alumni_id FROM alumni_event_rsvps "
            "WHERE event_id = ? AND attended = 1",
            (event_id,)).fetchall()
    for r in rows:
        try:
            invite_to_survey(survey.survey_id, r["alumni_id"])
        except ValidationError:
            continue
    _log_action("event.close.feedback", actor=invite_actor,
                  event_id=event_id, survey_id=survey.survey_id,
                  invited=len(rows))
    return get_event(event_id), survey  # type: ignore[return-value]


# ── #30 Reunion year planner ─────────────────────────────────────

REUNION_INTERVALS: tuple[int, ...] = (5, 10, 15, 20, 25, 30, 40, 50)


@dataclass
class ReunionSuggestion:
    leaving_year: str
    years_since: int
    cohort_size: int
    proposed_name: str
    proposed_date: str  # ISO


def suggest_reunions(*, today: _dt.date | None = None,
                          horizon_months: int = 18
                          ) -> list[ReunionSuggestion]:
    """Look at every distinct leaving cohort and propose a reunion
    event when the next round-year anniversary falls inside the
    given horizon."""
    init_db()
    today = today or _dt.date.today()
    horizon = today + _dt.timedelta(days=30 * horizon_months)
    out: list[ReunionSuggestion] = []
    with _connect() as conn:
        rows = conn.execute(
            "SELECT leaving_year, COUNT(*) AS n FROM alumni "
            "WHERE leaving_year IS NOT NULL "
            "  AND deleted_at IS NULL GROUP BY leaving_year"
        ).fetchall()
    for r in rows:
        try:
            ly = int(r["leaving_year"])
        except (TypeError, ValueError):
            continue
        for years in REUNION_INTERVALS:
            anniversary = _dt.date(ly + years, 7, 1)
            if today <= anniversary <= horizon:
                out.append(ReunionSuggestion(
                    leaving_year=str(ly),
                    years_since=years,
                    cohort_size=int(r["n"]),
                    proposed_name=f"Class of {ly} — {years}-year reunion",
                    proposed_date=anniversary.isoformat()))
                break
    out.sort(key=lambda s: s.proposed_date)
    return out


def create_reunion_events(*,
                              today: _dt.date | None = None,
                              horizon_months: int = 18,
                              actor: str | None = None
                              ) -> list[Event]:
    """Materialise the suggestions from :func:`suggest_reunions` into
    draft (``Planning``) events. Skips suggestions where a matching
    event name already exists."""
    init_db()
    created: list[Event] = []
    with _connect() as conn:
        existing = {row["name"] for row in conn.execute(
            "SELECT name FROM alumni_events").fetchall()}
    for s in suggest_reunions(today=today,
                                  horizon_months=horizon_months):
        if s.proposed_name in existing:
            continue
        try:
            created.append(create_event({
                "name": s.proposed_name,
                "event_type": "Reunion",
                "event_date": s.proposed_date,
                "status": "Planning",
                "notes": (f"Auto-suggested by planner — "
                              f"{s.years_since}y anniversary for "
                              f"{s.cohort_size} alumni"),
            }))
        except ValidationError:
            continue
    _log_action("reunion.plan", actor=actor, count=len(created))
    return created


# ── #31 Gift-Aid declarations ────────────────────────────────────

@dataclass
class GiftAidDeclaration:
    declaration_id: int
    alumni_id: int
    valid_from: str
    valid_until: str | None
    full_name: str
    address: str
    postcode: str
    signed_at: str
    withdrawn_at: str | None
    notes: str | None


def _row_gad(r: sqlite3.Row) -> GiftAidDeclaration:
    return GiftAidDeclaration(
        declaration_id=r["declaration_id"], alumni_id=r["alumni_id"],
        valid_from=r["valid_from"], valid_until=r["valid_until"],
        full_name=r["full_name"], address=r["address"],
        postcode=r["postcode"], signed_at=r["signed_at"],
        withdrawn_at=r["withdrawn_at"], notes=r["notes"])


def add_gift_aid_declaration(alumni_id: int, *,
                                  valid_from: str,
                                  full_name: str, address: str,
                                  postcode: str,
                                  valid_until: str | None = None,
                                  notes: str | None = None,
                                  actor: str | None = None
                                  ) -> GiftAidDeclaration:
    init_db()
    vfrom = _validate_date(valid_from, "Valid from", required=True)
    vuntil = _validate_date(valid_until, "Valid until", required=False)
    if not (full_name or "").strip():
        raise ValidationError("Full name is required")
    if not (address or "").strip():
        raise ValidationError("Address is required")
    if not (postcode or "").strip():
        raise ValidationError("Postcode is required")
    with _connect() as conn:
        _require_alumnus(conn, alumni_id)
        cur = conn.execute(
            """INSERT INTO alumni_gift_aid_declarations
                   (alumni_id, valid_from, valid_until,
                    full_name, address, postcode, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (alumni_id, vfrom, vuntil,
             full_name.strip(), address.strip(), postcode.strip(),
             (notes or "").strip() or None))
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_gift_aid_declarations "
            "WHERE declaration_id = ?",
            (cur.lastrowid,)).fetchone()
    _log_action("gad.add", actor=actor, alumni_id=alumni_id)
    return _row_gad(r)


def withdraw_gift_aid_declaration(declaration_id: int, *,
                                       when: str | None = None,
                                       actor: str | None = None
                                       ) -> GiftAidDeclaration:
    init_db()
    when_iso = when or _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE alumni_gift_aid_declarations "
            "SET withdrawn_at = ? WHERE declaration_id = ? "
            "  AND withdrawn_at IS NULL",
            (when_iso, declaration_id))
        if cur.rowcount == 0:
            raise ValidationError(
                f"No active declaration #{declaration_id}")
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_gift_aid_declarations "
            "WHERE declaration_id = ?",
            (declaration_id,)).fetchone()
    _log_action("gad.withdraw", actor=actor,
                  declaration_id=declaration_id)
    return _row_gad(r)


def get_active_gift_aid(alumni_id: int, on: str | None = None
                              ) -> GiftAidDeclaration | None:
    init_db()
    on = on or _dt.date.today().isoformat()
    with _connect() as conn:
        r = conn.execute(
            """SELECT * FROM alumni_gift_aid_declarations
                WHERE alumni_id = ?
                  AND valid_from <= ?
                  AND (valid_until IS NULL OR valid_until >= ?)
                  AND withdrawn_at IS NULL
                ORDER BY valid_from DESC LIMIT 1""",
            (alumni_id, on, on)).fetchone()
    return _row_gad(r) if r else None


def export_r68_csv(out_path: str | Path,  # type: ignore[name-defined]
                       *, year_start: str, year_end: str,
                       actor: str | None = None) -> int:
    """Write an HMRC R68-style CSV of every donation flagged
    ``gift_aid=1`` and covered by an active declaration in the
    window. Returns the number of rows written."""
    init_db()
    from pathlib import Path as _Path
    import csv as _csv
    yfrom = _validate_date(year_start, "Year start", required=True)
    yto = _validate_date(year_end, "Year end", required=True)
    with _connect() as conn:
        rows = conn.execute(
            """SELECT d.donation_id, d.donation_date, d.amount_pence,
                       a.first_name, a.last_name, a.address,
                       d.alumni_id
                  FROM alumni_donations d
                  JOIN alumni a ON a.alumni_id = d.alumni_id
                 WHERE d.gift_aid = 1
                   AND d.donation_date BETWEEN ? AND ?""",
            (yfrom, yto)).fetchall()
    p = _Path(out_path)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise IntegrationError(
            f"Cannot create output directory {p.parent}: {exc}") from exc
    count = 0
    try:
        with p.open("w", newline="", encoding="utf-8") as fh:
            w = _csv.writer(fh)
            w.writerow(["Title", "First name", "Last name",
                          "House no/name", "Postcode",
                          "Aggregated donations", "Sponsored event",
                          "Donation date", "Amount (£)"])
            for r in rows:
                gad = get_active_gift_aid(
                    r["alumni_id"], on=r["donation_date"])
                if gad is None:
                    continue
                postcode = gad.postcode
                house = gad.address.split(",")[0].strip()
                amount = int(r["amount_pence"]) / 100
                w.writerow(["", r["first_name"], r["last_name"],
                              house, postcode, "", "",
                              r["donation_date"], f"{amount:.2f}"])
                count += 1
    except OSError as exc:
        raise IntegrationError(
            f"Could not write {p}: {exc}") from exc
    _log_action("gad.r68", actor=actor, path=str(p), rows=count)
    return count


# ── #32 Recurring donations ──────────────────────────────────────

@dataclass
class RecurringSchedule:
    schedule_id: int
    alumni_id: int
    campaign_id: int | None
    amount_pence: int
    frequency: str
    next_charge_on: str
    status: str
    failure_count: int
    fund_code: str | None
    payment_method: str | None
    started_on: str
    cancelled_on: str | None
    notes: str | None


def _row_rec(r: sqlite3.Row) -> RecurringSchedule:
    return RecurringSchedule(
        schedule_id=r["schedule_id"], alumni_id=r["alumni_id"],
        campaign_id=r["campaign_id"],
        amount_pence=int(r["amount_pence"]),
        frequency=r["frequency"], next_charge_on=r["next_charge_on"],
        status=r["status"],
        failure_count=int(r["failure_count"]),
        fund_code=r["fund_code"], payment_method=r["payment_method"],
        started_on=r["started_on"], cancelled_on=r["cancelled_on"],
        notes=r["notes"])


def _advance_date(d: _dt.date, frequency: str) -> _dt.date:
    if frequency == "Monthly":
        m = d.month + 1
        y = d.year + (1 if m > 12 else 0)
        m = ((m - 1) % 12) + 1
        # Clamp day to the new month's last day.
        for day in (d.day, 28, 29, 30, 31):
            try:
                return _dt.date(y, m, min(day, 28))
            except ValueError:
                continue
        return _dt.date(y, m, 28)
    if frequency == "Quarterly":
        return _advance_date(_advance_date(_advance_date(d, "Monthly"),
                                                "Monthly"), "Monthly")
    if frequency == "Annually":
        try:
            return d.replace(year=d.year + 1)
        except ValueError:
            return _dt.date(d.year + 1, 2, 28)
    raise ValidationError(f"Unknown frequency {frequency!r}")


def create_recurring(alumni_id: int, *,
                          amount_pence: int, frequency: str = "Monthly",
                          next_charge_on: str | None = None,
                          campaign_id: int | None = None,
                          fund_code: str | None = None,
                          payment_method: str | None = None,
                          notes: str | None = None,
                          actor: str | None = None
                          ) -> RecurringSchedule:
    init_db()
    if amount_pence <= 0:
        raise ValidationError("amount_pence must be > 0")
    if frequency not in RECURRING_FREQS:
        raise ValidationError(
            f"Frequency must be one of: {', '.join(RECURRING_FREQS)}")
    nxt = _validate_date(next_charge_on, "Next charge",
                             required=False) \
        or _dt.date.today().isoformat()
    with _connect() as conn:
        _require_alumnus(conn, alumni_id)
        cur = conn.execute(
            """INSERT INTO alumni_recurring_donations
                   (alumni_id, campaign_id, amount_pence, frequency,
                    next_charge_on, fund_code, payment_method, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (alumni_id, campaign_id, amount_pence, frequency, nxt,
             (fund_code or "").strip() or None,
             (payment_method or "").strip() or None,
             (notes or "").strip() or None))
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_recurring_donations "
            "WHERE schedule_id = ?",
            (cur.lastrowid,)).fetchone()
    _log_action("recurring.create", actor=actor,
                  alumni_id=alumni_id,
                  amount_pence=amount_pence, frequency=frequency)
    return _row_rec(r)


def list_recurring(*, alumni_id: int | None = None,
                        status: str | None = None
                        ) -> list[RecurringSchedule]:
    init_db()
    sql = "SELECT * FROM alumni_recurring_donations WHERE 1=1"
    params: list[Any] = []
    if alumni_id is not None:
        sql += " AND alumni_id = ?"; params.append(alumni_id)
    if status:
        sql += " AND status = ?"; params.append(status)
    sql += " ORDER BY next_charge_on"
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_rec(r) for r in rows]


def set_recurring_status(schedule_id: int, status: str, *,
                              actor: str | None = None
                              ) -> RecurringSchedule:
    init_db()
    if status not in RECURRING_STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(RECURRING_STATUSES)}")
    cancelled = _dt.date.today().isoformat() \
        if status == "Cancelled" else None
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE alumni_recurring_donations "
            "SET status = ?, cancelled_on = COALESCE(?, cancelled_on) "
            "WHERE schedule_id = ?",
            (status, cancelled, schedule_id))
        if cur.rowcount == 0:
            raise ValidationError(f"No schedule #{schedule_id}")
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_recurring_donations "
            "WHERE schedule_id = ?",
            (schedule_id,)).fetchone()
    _log_action("recurring.status", actor=actor,
                  schedule_id=schedule_id, status=status)
    return _row_rec(r)


@dataclass
class RecurringTick:
    schedule_id: int
    alumni_id: int
    amount_pence: int
    donation_id: int | None
    success: bool
    error: str | None


def tick_recurring(*, today: _dt.date | None = None,
                        charge: Callable[[RecurringSchedule], bool]
                        | None = None,
                        actor: str | None = None
                        ) -> list[RecurringTick]:
    """Charge every Active schedule whose ``next_charge_on`` ≤ today.
    Default behaviour (``charge=None``) treats each charge as a
    success and records a corresponding ``alumni_donations`` row.
    Pass a callable to integrate with a real PSP — return ``True`` on
    success and ``False`` (raise) on failure. Three consecutive
    failures auto-flips the status to 'Failed'."""
    init_db()
    today = today or _dt.date.today()
    out: list[RecurringTick] = []
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM alumni_recurring_donations "
            "WHERE status = 'Active' AND next_charge_on <= ?",
            (today.isoformat(),)).fetchall()
    for r in rows:
        sched = _row_rec(r)
        ok = True
        error: str | None = None
        if charge is not None:
            try:
                ok = bool(charge(sched))
            except Exception as exc:
                ok = False
                error = str(exc)[:200]
        donation_id: int | None = None
        if ok:
            d = record_donation(sched.alumni_id, {
                "donation_date": today.isoformat(),
                "amount_pence": sched.amount_pence,
                "campaign_id": sched.campaign_id,
                "payment_method": sched.payment_method or "Direct Debit",
                "notes": f"Recurring schedule #{sched.schedule_id}",
            })
            donation_id = d.donation_id
            with _connect() as conn:
                nxt = _advance_date(_dt.date.fromisoformat(
                    sched.next_charge_on), sched.frequency)
                conn.execute(
                    "UPDATE alumni_recurring_donations "
                    "SET next_charge_on = ?, failure_count = 0 "
                    "WHERE schedule_id = ?",
                    (nxt.isoformat(), sched.schedule_id))
                conn.commit()
        else:
            with _connect() as conn:
                new_fails = sched.failure_count + 1
                new_status = "Failed" if new_fails >= 3 else "Active"
                conn.execute(
                    "UPDATE alumni_recurring_donations "
                    "SET failure_count = ?, status = ? "
                    "WHERE schedule_id = ?",
                    (new_fails, new_status, sched.schedule_id))
                conn.commit()
        out.append(RecurringTick(
            schedule_id=sched.schedule_id,
            alumni_id=sched.alumni_id,
            amount_pence=sched.amount_pence,
            donation_id=donation_id, success=ok, error=error))
    _log_action("recurring.tick", actor=actor,
                  processed=len(out),
                  failed=sum(1 for t in out if not t.success))
    return out


# ── #33 Donor pipeline (CRM stages) ──────────────────────────────

@dataclass
class DonorPipeline:
    alumni_id: int
    stage: str
    owner_staff_id: str | None
    next_action: str | None
    next_action_on: str | None
    capacity_pence: int | None
    notes: str | None
    updated_at: str


def _row_pipeline(r: sqlite3.Row) -> DonorPipeline:
    return DonorPipeline(
        alumni_id=r["alumni_id"], stage=r["stage"],
        owner_staff_id=r["owner_staff_id"],
        next_action=r["next_action"],
        next_action_on=r["next_action_on"],
        capacity_pence=r["capacity_pence"],
        notes=r["notes"], updated_at=r["updated_at"])


def set_donor_stage(alumni_id: int, stage: str, *,
                        owner_staff_id: str | None = None,
                        next_action: str | None = None,
                        next_action_on: str | None = None,
                        capacity_pence: int | None = None,
                        notes: str | None = None,
                        actor: str | None = None) -> DonorPipeline:
    init_db()
    if stage not in DONOR_STAGES:
        raise ValidationError(
            f"Stage must be one of: {', '.join(DONOR_STAGES)}")
    nxt = _validate_date(next_action_on, "Next action on",
                             required=False)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        _require_alumnus(conn, alumni_id)
        prev = conn.execute(
            "SELECT stage FROM alumni_donor_pipeline "
            "WHERE alumni_id = ?", (alumni_id,)).fetchone()
        prev_stage = prev["stage"] if prev else None
        conn.execute(
            """INSERT INTO alumni_donor_pipeline
                   (alumni_id, stage, owner_staff_id, next_action,
                    next_action_on, capacity_pence, notes, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(alumni_id) DO UPDATE SET
                   stage          = excluded.stage,
                   owner_staff_id = excluded.owner_staff_id,
                   next_action    = excluded.next_action,
                   next_action_on = excluded.next_action_on,
                   capacity_pence = excluded.capacity_pence,
                   notes          = excluded.notes,
                   updated_at     = excluded.updated_at""",
            (alumni_id, stage,
             (owner_staff_id or "").strip() or None,
             (next_action or "").strip() or None, nxt,
             capacity_pence, (notes or "").strip() or None, now))
        if prev_stage != stage:
            conn.execute(
                """INSERT INTO alumni_donor_pipeline_log
                       (alumni_id, from_stage, to_stage,
                        changed_by, notes)
                   VALUES (?, ?, ?, ?, ?)""",
                (alumni_id, prev_stage, stage, actor,
                 (notes or "").strip() or None))
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_donor_pipeline "
            "WHERE alumni_id = ?", (alumni_id,)).fetchone()
    _log_action("pipeline.stage", actor=actor,
                  alumni_id=alumni_id, stage=stage,
                  from_stage=prev_stage)
    return _row_pipeline(r)


def get_donor_pipeline(alumni_id: int) -> DonorPipeline | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM alumni_donor_pipeline "
            "WHERE alumni_id = ?", (alumni_id,)).fetchone()
    return _row_pipeline(r) if r else None


def list_donor_pipeline(*, stage: str | None = None,
                              owner_staff_id: str | None = None
                              ) -> list[DonorPipeline]:
    init_db()
    sql = "SELECT * FROM alumni_donor_pipeline WHERE 1=1"
    params: list[Any] = []
    if stage:
        sql += " AND stage = ?"; params.append(stage)
    if owner_staff_id:
        sql += " AND owner_staff_id = ?"; params.append(owner_staff_id)
    sql += " ORDER BY next_action_on ASC NULLS LAST"
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_pipeline(r) for r in rows]


# ── #34 Funds (restricted vs unrestricted) ───────────────────────

@dataclass
class Fund:
    fund_id: int
    code: str
    name: str
    restricted: bool
    description: str | None
    created_at: str


def _row_fund(r: sqlite3.Row) -> Fund:
    return Fund(
        fund_id=r["fund_id"], code=r["code"], name=r["name"],
        restricted=bool(r["restricted"]),
        description=r["description"], created_at=r["created_at"])


def upsert_fund(code: str, name: str, *,
                    restricted: bool = False,
                    description: str | None = None,
                    actor: str | None = None) -> Fund:
    init_db()
    code = (code or "").strip()
    if not code:
        raise ValidationError("Fund code is required")
    if not (name or "").strip():
        raise ValidationError("Fund name is required")
    with _connect() as conn:
        conn.execute(
            """INSERT INTO alumni_funds
                   (code, name, restricted, description)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(code) DO UPDATE SET
                   name        = excluded.name,
                   restricted  = excluded.restricted,
                   description = excluded.description""",
            (code, name.strip(), 1 if restricted else 0,
             (description or "").strip() or None))
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_funds WHERE code = ?",
            (code,)).fetchone()
    _log_action("fund.upsert", actor=actor, code=code,
                  restricted=restricted)
    return _row_fund(r)


def list_funds() -> list[Fund]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM alumni_funds "
            "ORDER BY restricted DESC, code COLLATE NOCASE"
            ).fetchall()
    return [_row_fund(r) for r in rows]


def tag_donation_fund(donation_id: int, fund_code: str, *,
                          actor: str | None = None) -> None:
    init_db()
    fund_code = (fund_code or "").strip()
    if not fund_code:
        raise ValidationError("Fund code is required")
    with _connect() as conn:
        f = conn.execute(
            "SELECT 1 FROM alumni_funds WHERE code = ?",
            (fund_code,)).fetchone()
        if f is None:
            raise ValidationError(f"No fund {fund_code!r}")
        cur = conn.execute(
            "UPDATE alumni_donations SET fund_code = ? "
            "WHERE donation_id = ?", (fund_code, donation_id))
        if cur.rowcount == 0:
            raise ValidationError(f"No donation #{donation_id}")
        conn.commit()
    _log_action("fund.tag", actor=actor,
                  donation_id=donation_id, fund_code=fund_code)


@dataclass
class FundTotals:
    fund_code: str
    fund_name: str
    restricted: bool
    raised_pence: int


def fund_totals(*, campaign_id: int | None = None
                     ) -> list[FundTotals]:
    init_db()
    sql = ("""SELECT COALESCE(d.fund_code, '(unallocated)') AS code,
                     COALESCE(f.name, '(unallocated)') AS name,
                     COALESCE(f.restricted, 0) AS restricted,
                     COALESCE(SUM(d.amount_pence), 0) AS total
                FROM alumni_donations d
                LEFT JOIN alumni_funds f ON f.code = d.fund_code""")
    params: list[Any] = []
    if campaign_id is not None:
        sql += " WHERE d.campaign_id = ?"; params.append(campaign_id)
    sql += " GROUP BY code, name, restricted ORDER BY total DESC"
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [FundTotals(
        fund_code=r["code"], fund_name=r["name"],
        restricted=bool(r["restricted"]),
        raised_pence=int(r["total"])) for r in rows]


# ── #35 Bequests / legacy register ───────────────────────────────

@dataclass
class Bequest:
    bequest_id: int
    alumni_id: int
    estimated_pence: int | None
    will_mention: bool
    executor_name: str | None
    executor_email: str | None
    executor_phone: str | None
    confirmed_on: str | None
    realised_on: str | None
    status: str
    notes: str | None
    created_at: str


def _row_bequest(r: sqlite3.Row) -> Bequest:
    return Bequest(
        bequest_id=r["bequest_id"], alumni_id=r["alumni_id"],
        estimated_pence=r["estimated_pence"],
        will_mention=bool(r["will_mention"]),
        executor_name=r["executor_name"],
        executor_email=r["executor_email"],
        executor_phone=r["executor_phone"],
        confirmed_on=r["confirmed_on"],
        realised_on=r["realised_on"], status=r["status"],
        notes=r["notes"], created_at=r["created_at"])


def add_bequest(alumni_id: int, *,
                    estimated_pence: int | None = None,
                    will_mention: bool = True,
                    executor_name: str | None = None,
                    executor_email: str | None = None,
                    executor_phone: str | None = None,
                    confirmed_on: str | None = None,
                    status: str = "Pledged",
                    notes: str | None = None,
                    actor: str | None = None) -> Bequest:
    init_db()
    if status not in BEQUEST_STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(BEQUEST_STATUSES)}")
    cdate = _validate_date(confirmed_on, "Confirmed on",
                                required=False)
    if executor_email:
        executor_email = _validate_email(executor_email)
    with _connect() as conn:
        _require_alumnus(conn, alumni_id)
        cur = conn.execute(
            """INSERT INTO alumni_bequests
                   (alumni_id, estimated_pence, will_mention,
                    executor_name, executor_email, executor_phone,
                    confirmed_on, status, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (alumni_id, estimated_pence,
             1 if will_mention else 0,
             (executor_name or "").strip() or None,
             executor_email,
             (executor_phone or "").strip() or None,
             cdate, status,
             (notes or "").strip() or None))
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_bequests WHERE bequest_id = ?",
            (cur.lastrowid,)).fetchone()
    _log_action("bequest.add", actor=actor, alumni_id=alumni_id,
                  status=status)
    return _row_bequest(r)


def list_bequests(*, status: str | None = None
                       ) -> list[Bequest]:
    init_db()
    sql = "SELECT * FROM alumni_bequests WHERE 1=1"
    params: list[Any] = []
    if status:
        sql += " AND status = ?"; params.append(status)
    sql += " ORDER BY created_at DESC"
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_bequest(r) for r in rows]


def set_bequest_status(bequest_id: int, status: str, *,
                            realised_on: str | None = None,
                            actor: str | None = None) -> Bequest:
    init_db()
    if status not in BEQUEST_STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(BEQUEST_STATUSES)}")
    rdate = _validate_date(realised_on, "Realised on", required=False)
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE alumni_bequests SET status = ?, "
            "    realised_on = COALESCE(?, realised_on) "
            "WHERE bequest_id = ?",
            (status, rdate, bequest_id))
        if cur.rowcount == 0:
            raise ValidationError(f"No bequest #{bequest_id}")
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_bequests WHERE bequest_id = ?",
            (bequest_id,)).fetchone()
    _log_action("bequest.status", actor=actor,
                  bequest_id=bequest_id, status=status)
    return _row_bequest(r)


# ── #36 Matched giving ───────────────────────────────────────────

@dataclass
class MatchedScheme:
    scheme_id: int
    employer: str
    multiplier: float
    cap_pence: int | None
    notes: str | None


def _row_scheme(r: sqlite3.Row) -> MatchedScheme:
    return MatchedScheme(
        scheme_id=r["scheme_id"], employer=r["employer"],
        multiplier=float(r["multiplier"]),
        cap_pence=r["cap_pence"], notes=r["notes"])


def upsert_matched_scheme(employer: str, *,
                              multiplier: float = 1.0,
                              cap_pence: int | None = None,
                              notes: str | None = None,
                              actor: str | None = None
                              ) -> MatchedScheme:
    init_db()
    employer = (employer or "").strip()
    if not employer:
        raise ValidationError("Employer is required")
    if multiplier <= 0:
        raise ValidationError("Multiplier must be > 0")
    with _connect() as conn:
        conn.execute(
            """INSERT INTO alumni_matched_giving_schemes
                   (employer, multiplier, cap_pence, notes)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(employer) DO UPDATE SET
                   multiplier = excluded.multiplier,
                   cap_pence  = excluded.cap_pence,
                   notes      = excluded.notes""",
            (employer, multiplier, cap_pence,
             (notes or "").strip() or None))
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_matched_giving_schemes "
            "WHERE employer = ?", (employer,)).fetchone()
    _log_action("matched.upsert", actor=actor,
                  employer=employer, multiplier=multiplier)
    return _row_scheme(r)


def list_matched_schemes() -> list[MatchedScheme]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM alumni_matched_giving_schemes "
            "ORDER BY employer COLLATE NOCASE").fetchall()
    return [_row_scheme(r) for r in rows]


def find_matched_scheme(employer: str | None
                            ) -> MatchedScheme | None:
    """Look up a matched-giving scheme by employer name. Aliases
    from the normalised employer directory are honoured."""
    init_db()
    if not employer:
        return None
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM alumni_matched_giving_schemes "
            "WHERE employer = ? COLLATE NOCASE",
            (employer.strip(),)).fetchone()
        if r:
            return _row_scheme(r)
    resolved = resolve_employer(employer)
    if resolved is None:
        return None
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM alumni_matched_giving_schemes "
            "WHERE employer = ? COLLATE NOCASE",
            (resolved.canonical_name,)).fetchone()
    return _row_scheme(r) if r else None


def auto_apply_matched_giving(donation_id: int, *,
                                   actor: str | None = None) -> int:
    """Look up the donor's current employer, find a matched-giving
    scheme, and write the matched amount onto the donation row.
    Returns the matched amount in pence (0 if no scheme applies)."""
    init_db()
    with _connect() as conn:
        r = conn.execute(
            """SELECT d.donation_id, d.amount_pence,
                       a.current_employer
                  FROM alumni_donations d
                  JOIN alumni a ON a.alumni_id = d.alumni_id
                 WHERE d.donation_id = ?""", (donation_id,)).fetchone()
        if r is None:
            raise ValidationError(f"No donation #{donation_id}")
    scheme = find_matched_scheme(r["current_employer"])
    if scheme is None:
        return 0
    matched = int(int(r["amount_pence"]) * scheme.multiplier)
    if scheme.cap_pence is not None:
        matched = min(matched, scheme.cap_pence)
    with _connect() as conn:
        conn.execute(
            "UPDATE alumni_donations "
            "SET matched_pence = ?, matched_scheme_id = ? "
            "WHERE donation_id = ?",
            (matched, scheme.scheme_id, donation_id))
        conn.commit()
    _log_action("matched.apply", actor=actor,
                  donation_id=donation_id, matched_pence=matched,
                  employer=r["current_employer"])
    return matched


# ── #37 NEET tracking ────────────────────────────────────────────

@dataclass
class NEETCheck:
    check_id: int
    alumni_id: int
    months_after: int
    checked_on: str
    status: str
    notes: str | None


def _row_neet(r: sqlite3.Row) -> NEETCheck:
    return NEETCheck(
        check_id=r["check_id"], alumni_id=r["alumni_id"],
        months_after=int(r["months_after"]),
        checked_on=r["checked_on"], status=r["status"],
        notes=r["notes"])


def record_neet_check(alumni_id: int, *,
                          months_after: int, status: str,
                          checked_on: str | None = None,
                          notes: str | None = None,
                          actor: str | None = None) -> NEETCheck:
    init_db()
    if months_after not in (3, 6, 12, 24):
        raise ValidationError(
            "months_after must be one of 3, 6, 12, 24")
    if status not in NEET_STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(NEET_STATUSES)}")
    when = _validate_date(checked_on, "Checked on", required=False) \
        or _dt.date.today().isoformat()
    with _connect() as conn:
        _require_alumnus(conn, alumni_id)
        conn.execute(
            """INSERT INTO alumni_neet_checks
                   (alumni_id, months_after, checked_on, status, notes)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(alumni_id, months_after) DO UPDATE SET
                   checked_on = excluded.checked_on,
                   status     = excluded.status,
                   notes      = excluded.notes""",
            (alumni_id, months_after, when, status,
             (notes or "").strip() or None))
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_neet_checks "
            "WHERE alumni_id = ? AND months_after = ?",
            (alumni_id, months_after)).fetchone()
    _log_action("neet.record", actor=actor,
                  alumni_id=alumni_id, months_after=months_after,
                  status=status)
    return _row_neet(r)


def list_neet_checks(alumni_id: int) -> list[NEETCheck]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM alumni_neet_checks WHERE alumni_id = ? "
            "ORDER BY months_after", (alumni_id,)).fetchall()
    return [_row_neet(r) for r in rows]


@dataclass
class NEETRateRow:
    months_after: int
    cohort: int
    neet: int
    not_neet: int
    unknown: int
    neet_rate_pct: float


def neet_breakdown(*, leaving_year: str | None = None
                        ) -> list[NEETRateRow]:
    """Aggregate NEET status by months-after-leaving. Alumni without
    a recorded check at a given milestone are counted as 'Unknown'."""
    init_db()
    rows: list[NEETRateRow] = []
    sql_alumni = ("SELECT alumni_id FROM alumni "
                    "WHERE deleted_at IS NULL")
    params: list[Any] = []
    if leaving_year:
        sql_alumni += " AND leaving_year = ?"
        params.append(leaving_year)
    with _connect() as conn:
        ids = [r["alumni_id"] for r in conn.execute(
            sql_alumni, params).fetchall()]
        cohort = len(ids)
    if cohort == 0:
        return rows
    for m in (3, 6, 12):
        with _connect() as conn:
            placeholders = ",".join("?" * len(ids))
            checks = conn.execute(
                f"SELECT status FROM alumni_neet_checks "
                f"WHERE months_after = ? AND alumni_id IN "
                f"({placeholders})",
                (m, *ids)).fetchall()
        neet = sum(1 for c in checks if c["status"] == "NEET")
        not_neet = sum(1 for c in checks
                          if c["status"] not in ("NEET", "Unknown"))
        unknown = cohort - neet - not_neet
        denom = neet + not_neet or 1
        rows.append(NEETRateRow(
            months_after=m, cohort=cohort, neet=neet,
            not_neet=not_neet, unknown=unknown,
            neet_rate_pct=round(100 * neet / denom, 1)))
    return rows


# ── #38 Russell Group / Oxbridge breakout ────────────────────────

def _is_uni_match(name: str | None, group: tuple[str, ...]) -> bool:
    if not name:
        return False
    n = name.lower()
    return any(u.lower() in n for u in group)


@dataclass
class UniGroupRow:
    leaving_year: str | None
    cohort: int
    russell_group: int
    russell_rate_pct: float
    oxbridge: int
    oxbridge_rate_pct: float


def russell_group_breakdown(*, leaving_year: str | None = None
                                  ) -> UniGroupRow:
    init_db()
    sql_a = "SELECT alumni_id, leaving_year FROM alumni " \
              "WHERE deleted_at IS NULL"
    params: list[Any] = []
    if leaving_year:
        sql_a += " AND leaving_year = ?"
        params.append(leaving_year)
    with _connect() as conn:
        alumni = conn.execute(sql_a, params).fetchall()
        cohort = len(alumni)
        rg = ox = 0
        for a in alumni:
            unis = conn.execute(
                "SELECT institution FROM alumni_education "
                "WHERE alumni_id = ?", (a["alumni_id"],)).fetchall()
            names = [u["institution"] for u in unis]
            if any(_is_uni_match(n, RUSSELL_GROUP_UNIVERSITIES)
                      for n in names):
                rg += 1
            if any(_is_uni_match(n, OXBRIDGE_UNIVERSITIES)
                      for n in names):
                ox += 1
    return UniGroupRow(
        leaving_year=leaving_year, cohort=cohort,
        russell_group=rg,
        russell_rate_pct=round(100 * rg / max(cohort, 1), 1),
        oxbridge=ox,
        oxbridge_rate_pct=round(100 * ox / max(cohort, 1), 1))


# ── #39 Postgraduate progression ─────────────────────────────────

@dataclass
class PostgraduateRow:
    alumni_id: int
    full_name: str
    leaving_year: str | None
    pg_qualifications: list[str]
    pg_institutions: list[str]


def postgraduate_progression(*, leaving_year: str | None = None
                                   ) -> list[PostgraduateRow]:
    """Alumni with at least one alumni_education row whose
    qualification matches a known PG label (MSc/PhD/etc.)."""
    init_db()
    sql = ("""SELECT a.alumni_id, a.first_name, a.last_name,
                      a.leaving_year
                 FROM alumni a WHERE deleted_at IS NULL""")
    params: list[Any] = []
    if leaving_year:
        sql += " AND a.leaving_year = ?"
        params.append(leaving_year)
    out: list[PostgraduateRow] = []
    with _connect() as conn:
        alumni = conn.execute(sql, params).fetchall()
        for a in alumni:
            edus = conn.execute(
                "SELECT qualification, institution "
                "FROM alumni_education WHERE alumni_id = ?",
                (a["alumni_id"],)).fetchall()
            pg = [(e["qualification"], e["institution"]) for e in edus
                    if any(p.lower() in (e["qualification"] or "").lower()
                              for p in PG_QUALIFICATIONS)]
            if not pg:
                continue
            out.append(PostgraduateRow(
                alumni_id=a["alumni_id"],
                full_name=f"{a['first_name']} {a['last_name']}",
                leaving_year=a["leaving_year"],
                pg_qualifications=[q for q, _ in pg],
                pg_institutions=[i for _, i in pg]))
    return out


@dataclass
class PostgraduateRate:
    leaving_year: str | None
    cohort: int
    pg_count: int
    pg_rate_pct: float


def postgraduate_rate(*, leaving_year: str | None = None
                           ) -> PostgraduateRate:
    init_db()
    sql = ("SELECT COUNT(*) FROM alumni WHERE deleted_at IS NULL")
    params: list[Any] = []
    if leaving_year:
        sql += " AND leaving_year = ?"
        params.append(leaving_year)
    with _connect() as conn:
        cohort = int(conn.execute(sql, params).fetchone()[0])
    pg = len(postgraduate_progression(leaving_year=leaving_year))
    return PostgraduateRate(
        leaving_year=leaving_year, cohort=cohort, pg_count=pg,
        pg_rate_pct=round(100 * pg / max(cohort, 1), 1))


# ── #40 First-generation HE outcomes ─────────────────────────────

def set_first_gen_he(alumni_id: int, value: bool, *,
                          actor: str | None = None) -> None:
    init_db()
    with _connect() as conn:
        _require_alumnus(conn, alumni_id)
        conn.execute(
            "UPDATE alumni SET first_gen_he = ? WHERE alumni_id = ?",
            (1 if value else 0, alumni_id))
        conn.commit()
    _log_action("first_gen_he.set", actor=actor,
                  alumni_id=alumni_id, value=value)


@dataclass
class FirstGenOutcomeRow:
    bucket: str  # 'first_gen' or 'continuing_gen'
    cohort: int
    in_he: int
    he_rate_pct: float
    russell_group: int
    russell_rate_pct: float


def first_gen_outcomes(*, leaving_year: str | None = None
                            ) -> list[FirstGenOutcomeRow]:
    """HE-entry and Russell-Group rates, split by ``first_gen_he``
    flag. ``in_he`` is the count of alumni with ``destination_type``
    set to 'University' or 'Further Study'."""
    init_db()
    sql_a = ("SELECT alumni_id, first_gen_he, destination_type "
              "FROM alumni WHERE deleted_at IS NULL")
    params: list[Any] = []
    if leaving_year:
        sql_a += " AND leaving_year = ?"
        params.append(leaving_year)
    with _connect() as conn:
        rows = conn.execute(sql_a, params).fetchall()
    buckets: dict[str, dict[str, int]] = {
        "first_gen":      {"cohort": 0, "in_he": 0, "rg": 0},
        "continuing_gen": {"cohort": 0, "in_he": 0, "rg": 0},
    }
    he_set = {"University", "Further Study"}
    with _connect() as conn:
        for r in rows:
            key = ("first_gen"
                     if _opt(r, "first_gen_he") else "continuing_gen")
            buckets[key]["cohort"] += 1
            if r["destination_type"] in he_set:
                buckets[key]["in_he"] += 1
            unis = conn.execute(
                "SELECT institution FROM alumni_education "
                "WHERE alumni_id = ?", (r["alumni_id"],)).fetchall()
            if any(_is_uni_match(u["institution"],
                                    RUSSELL_GROUP_UNIVERSITIES)
                      for u in unis):
                buckets[key]["rg"] += 1
    return [FirstGenOutcomeRow(
        bucket=k, cohort=v["cohort"], in_he=v["in_he"],
        he_rate_pct=round(100 * v["in_he"] / max(v["cohort"], 1), 1),
        russell_group=v["rg"],
        russell_rate_pct=round(100 * v["rg"] / max(v["cohort"], 1), 1))
            for k, v in buckets.items()]


# ════════════════════════════════════════════════════════════════════
# Final extensions (items 41–50): protected-characteristic gaps,
# HESA benchmarks, DfE 16-18 export, SAR bundle, erasure workflow,
# data-quality dashboard, dedupe buckets, webhooks, custom fields,
# media attachments.
# ════════════════════════════════════════════════════════════════════

CUSTOM_FIELD_TYPES: tuple[str, ...] = (
    "text", "number", "date", "boolean",
)
ERASURE_STATUSES: tuple[str, ...] = (
    "Requested", "Under Review", "Approved", "Completed",
    "Rejected", "Withdrawn",
)
WEBHOOK_EVENT_TYPES: tuple[str, ...] = (
    "alumnus.created", "alumnus.updated", "alumnus.deleted",
    "donation.recorded", "rsvp.changed", "event.closed",
    "consent.granted", "consent.withdrawn",
)
K_SUPPRESSION_THRESHOLD: int = 5

_PROTECTED_CHAR_COLS: tuple[tuple[str, str], ...] = (
    ("send",        "INTEGER NOT NULL DEFAULT 0"),
    ("fsm_ever_6",  "INTEGER NOT NULL DEFAULT 0"),
    ("eal",         "INTEGER NOT NULL DEFAULT 0"),
    ("looked_after", "INTEGER NOT NULL DEFAULT 0"),
    ("ethnicity",    "TEXT"),
)


_SCHEMA_FINAL_EXT = """
CREATE TABLE IF NOT EXISTS alumni_hesa_benchmarks (
    benchmark_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    leaving_year   TEXT NOT NULL,
    metric         TEXT NOT NULL,
    rate_pct       REAL NOT NULL,
    source         TEXT,
    UNIQUE(leaving_year, metric)
);

CREATE TABLE IF NOT EXISTS alumni_erasure_requests (
    request_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    alumni_id      INTEGER NOT NULL,
    requested_at   TEXT NOT NULL DEFAULT (datetime('now')),
    requested_by   TEXT,
    reason         TEXT,
    status         TEXT NOT NULL DEFAULT 'Requested',
    reviewer       TEXT,
    reviewed_at    TEXT,
    review_notes   TEXT,
    completed_at   TEXT,
    confirmation_sent_at TEXT,
    FOREIGN KEY (alumni_id) REFERENCES alumni(alumni_id)
        ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_aer_alumni
    ON alumni_erasure_requests(alumni_id);
CREATE INDEX IF NOT EXISTS idx_aer_status
    ON alumni_erasure_requests(status);

CREATE TABLE IF NOT EXISTS alumni_webhooks (
    webhook_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    url          TEXT NOT NULL,
    secret       TEXT,
    event_types  TEXT NOT NULL,
    active       INTEGER NOT NULL DEFAULT 1,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS alumni_webhook_events (
    event_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type   TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    queued_at    TEXT NOT NULL DEFAULT (datetime('now')),
    delivered_at TEXT,
    last_error   TEXT
);
CREATE INDEX IF NOT EXISTS idx_awhe_type
    ON alumni_webhook_events(event_type);

CREATE TABLE IF NOT EXISTS alumni_custom_fields (
    field_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL UNIQUE COLLATE NOCASE,
    label        TEXT NOT NULL,
    type         TEXT NOT NULL DEFAULT 'text',
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS alumni_custom_values (
    alumni_id   INTEGER NOT NULL,
    field_id    INTEGER NOT NULL,
    value       TEXT,
    PRIMARY KEY (alumni_id, field_id),
    FOREIGN KEY (alumni_id) REFERENCES alumni(alumni_id)
        ON DELETE CASCADE,
    FOREIGN KEY (field_id)  REFERENCES alumni_custom_fields(field_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS alumni_media (
    media_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    alumni_id    INTEGER NOT NULL,
    kind         TEXT NOT NULL DEFAULT 'photo',
    file_path    TEXT NOT NULL,
    caption      TEXT,
    consent_granted INTEGER NOT NULL DEFAULT 0,
    exif_stripped   INTEGER NOT NULL DEFAULT 0,
    is_profile      INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (alumni_id) REFERENCES alumni(alumni_id)
        ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_amedia_alumni
    ON alumni_media(alumni_id);
"""


def _init_final_ext_schema() -> None:
    with _connect() as conn:
        conn.executescript(_SCHEMA_FINAL_EXT)
        existing = {row[1] for row in conn.execute(
            "PRAGMA table_info(alumni)").fetchall()}
        for col, decl in _PROTECTED_CHAR_COLS:
            if col not in existing:
                conn.execute(
                    f"ALTER TABLE alumni ADD COLUMN {col} {decl}")


_original_init_db_v5 = init_db


def init_db() -> None:  # type: ignore[no-redef]
    already = _DB_READY
    _original_init_db_v5()
    if not already:
        _init_final_ext_schema()


# ── #41 Protected-characteristic gaps (k-suppression) ────────────

PROTECTED_CHARS: tuple[str, ...] = (
    "send", "fsm_ever_6", "eal", "looked_after",
)


def set_protected_characteristic(alumni_id: int, char: str,
                                       value: bool, *,
                                       actor: str | None = None) -> None:
    init_db()
    if char not in PROTECTED_CHARS:
        raise ValidationError(
            f"Characteristic must be one of: "
            f"{', '.join(PROTECTED_CHARS)}")
    with _connect() as conn:
        _require_alumnus(conn, alumni_id)
        conn.execute(
            f"UPDATE alumni SET {char} = ? WHERE alumni_id = ?",
            (1 if value else 0, alumni_id))
        conn.commit()
    _log_action("protected.set", actor=actor, alumni_id=alumni_id,
                  char=char, value=value)


def set_ethnicity(alumni_id: int, value: str | None, *,
                      actor: str | None = None) -> None:
    init_db()
    with _connect() as conn:
        _require_alumnus(conn, alumni_id)
        conn.execute(
            "UPDATE alumni SET ethnicity = ? WHERE alumni_id = ?",
            ((value or "").strip() or None, alumni_id))
        conn.commit()
    _log_action("ethnicity.set", actor=actor, alumni_id=alumni_id)


@dataclass
class ProtectedGapRow:
    characteristic: str
    bucket: str        # 'with' / 'without'
    cohort: int        # raw count (may be suppressed in display)
    he_rate_pct: float | None
    suppressed: bool


def protected_characteristic_gaps(*,
                                       leaving_year: str | None = None,
                                       k: int = K_SUPPRESSION_THRESHOLD
                                       ) -> list[ProtectedGapRow]:
    """For each binary protected characteristic, compare HE-entry
    rate between alumni with the flag set vs not. Any bucket with a
    cohort below ``k`` has its rate suppressed (set to ``None``) and
    is flagged via ``suppressed=True`` to satisfy small-n redaction
    rules."""
    init_db()
    he_set = ("University", "Further Study")
    out: list[ProtectedGapRow] = []
    sql_base = ("SELECT {col} AS flag, destination_type "
                  "FROM alumni WHERE deleted_at IS NULL")
    params_base: list[Any] = []
    if leaving_year:
        sql_base += " AND leaving_year = ?"
        params_base.append(leaving_year)
    with _connect() as conn:
        for char in PROTECTED_CHARS:
            rows = conn.execute(
                sql_base.format(col=char), params_base).fetchall()
            for bucket_label, want in (("with", 1), ("without", 0)):
                subset = [r for r in rows if int(r["flag"]) == want]
                cohort = len(subset)
                in_he = sum(1 for r in subset
                              if r["destination_type"] in he_set)
                suppressed = cohort < k
                rate = (round(100 * in_he / cohort, 1)
                          if (cohort and not suppressed) else None)
                out.append(ProtectedGapRow(
                    characteristic=char, bucket=bucket_label,
                    cohort=cohort, he_rate_pct=rate,
                    suppressed=suppressed))
    return out


# ── #42 HESA benchmark comparison ────────────────────────────────

@dataclass
class HESABenchmark:
    benchmark_id: int
    leaving_year: str
    metric: str
    rate_pct: float
    source: str | None


def _row_benchmark(r: sqlite3.Row) -> HESABenchmark:
    return HESABenchmark(
        benchmark_id=r["benchmark_id"],
        leaving_year=r["leaving_year"], metric=r["metric"],
        rate_pct=float(r["rate_pct"]), source=r["source"])


def upsert_hesa_benchmark(leaving_year: str, metric: str,
                              rate_pct: float, *,
                              source: str | None = None,
                              actor: str | None = None
                              ) -> HESABenchmark:
    init_db()
    leaving_year = (leaving_year or "").strip()
    metric = (metric or "").strip()
    if not leaving_year or not metric:
        raise ValidationError(
            "leaving_year and metric are required")
    if not 0 <= rate_pct <= 100:
        raise ValidationError("rate_pct must be between 0 and 100")
    with _connect() as conn:
        conn.execute(
            """INSERT INTO alumni_hesa_benchmarks
                   (leaving_year, metric, rate_pct, source)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(leaving_year, metric) DO UPDATE SET
                   rate_pct = excluded.rate_pct,
                   source   = excluded.source""",
            (leaving_year, metric, rate_pct,
             (source or "").strip() or None))
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_hesa_benchmarks "
            "WHERE leaving_year = ? AND metric = ?",
            (leaving_year, metric)).fetchone()
    _log_action("hesa.upsert", actor=actor,
                  leaving_year=leaving_year, metric=metric,
                  rate_pct=rate_pct)
    return _row_benchmark(r)


def list_hesa_benchmarks(*, leaving_year: str | None = None
                              ) -> list[HESABenchmark]:
    init_db()
    sql = "SELECT * FROM alumni_hesa_benchmarks"
    params: list[Any] = []
    if leaving_year:
        sql += " WHERE leaving_year = ?"; params.append(leaving_year)
    sql += " ORDER BY leaving_year DESC, metric"
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_benchmark(r) for r in rows]


@dataclass
class HESADeltaRow:
    metric: str
    leaving_year: str
    school_rate_pct: float
    hesa_rate_pct: float
    delta_pct: float


def _local_rate(metric: str, leaving_year: str | None) -> float | None:
    """Map a metric name to the corresponding internal rate. New
    metric names can be plugged in here without disturbing callers."""
    if metric == "he_entry":
        rows = first_gen_outcomes(leaving_year=leaving_year)
        cohort = sum(r.cohort for r in rows)
        in_he = sum(r.in_he for r in rows)
        return round(100 * in_he / max(cohort, 1), 1) if cohort else None
    if metric == "russell_group":
        r = russell_group_breakdown(leaving_year=leaving_year)
        return r.russell_rate_pct if r.cohort else None
    if metric == "oxbridge":
        r = russell_group_breakdown(leaving_year=leaving_year)
        return r.oxbridge_rate_pct if r.cohort else None
    if metric == "postgraduate":
        r = postgraduate_rate(leaving_year=leaving_year)
        return r.pg_rate_pct if r.cohort else None
    return None


def compare_with_hesa(leaving_year: str) -> list[HESADeltaRow]:
    init_db()
    benchmarks = list_hesa_benchmarks(leaving_year=leaving_year)
    out: list[HESADeltaRow] = []
    for b in benchmarks:
        local = _local_rate(b.metric, leaving_year)
        if local is None:
            continue
        out.append(HESADeltaRow(
            metric=b.metric, leaving_year=leaving_year,
            school_rate_pct=local, hesa_rate_pct=b.rate_pct,
            delta_pct=round(local - b.rate_pct, 1)))
    return out


# ── #43 DfE 16-18 destinations export ────────────────────────────

_DFE_BUCKETS = {
    "University":      "Sustained higher education",
    "Further Study":   "Sustained further education",
    "Apprenticeship":  "Apprenticeship",
    "Employment":      "Employment",
    "Self-Employed":   "Employment",
    "Volunteering":    "Other positive activity",
    "Gap Year":        "Other positive activity",
    "Other":           "Other",
    "Unknown":         "Activity not captured",
}


def export_dfe_destinations_csv(out_path: str,  # type: ignore[name-defined]
                                    *, leaving_year: str,
                                    actor: str | None = None) -> int:
    """Emit a DfE 16-18 destinations measure CSV for one cohort.

    Output columns track the published DfE structure: leaver, DfE
    bucket, sustained flag, university (if applicable). Returns the
    number of rows written."""
    init_db()
    from pathlib import Path as _Path
    import csv as _csv
    with _connect() as conn:
        rows = conn.execute(
            """SELECT a.*,
                       (SELECT institution FROM alumni_education e
                          WHERE e.alumni_id = a.alumni_id
                          ORDER BY e.start_date LIMIT 1) AS first_uni
                  FROM alumni a
                 WHERE a.leaving_year = ?
                   AND a.deleted_at IS NULL""",
            (leaving_year,)).fetchall()
    p = _Path(out_path)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise IntegrationError(
            f"Cannot create output directory {p.parent}: {exc}") from exc
    try:
        with p.open("w", newline="", encoding="utf-8") as fh:
            w = _csv.writer(fh)
            w.writerow(["Pupil reference", "First name", "Last name",
                           "Leaving year", "DfE category",
                           "Destination detail", "Institution",
                           "Sustained at 6 months"])
            for r in rows:
                bucket = _DFE_BUCKETS.get(
                    r["destination_type"], "Other")
                try:
                    sustained = _activity_at(r["alumni_id"], "6m") \
                        if "_activity_at" in globals() else "Unknown"
                except Exception:  # noqa: BLE001
                    # _activity_at is a best-effort helper from a
                    # sibling cluster; never let it fail the export.
                    sustained = "Unknown"
                w.writerow([
                    r["original_student_id"] or "",
                    r["first_name"], r["last_name"], leaving_year,
                    bucket, r["destination_detail"] or "",
                    r["first_uni"] or "", sustained])
    except OSError as exc:
        raise IntegrationError(
            f"Could not write {p}: {exc}") from exc
    _log_action("dfe.export", actor=actor,
                  leaving_year=leaving_year, rows=len(rows),
                  path=str(p))
    return len(rows)


# ── #44 SAR bundle generator ─────────────────────────────────────

def generate_sar_bundle(alumni_id: int, out_dir: str,  # type: ignore[name-defined]
                            *, actor: str | None = None) -> str:
    """Pack every row keyed to ``alumni_id`` across every table into
    one ZIP, one CSV per table. Returns the ZIP path."""
    init_db()
    from pathlib import Path as _Path
    import csv as _csv
    import io as _io
    import zipfile as _zip
    a = get_alumnus(alumni_id)
    if a is None:
        raise NotFoundError(f"No alumnus #{alumni_id}")
    d = _Path(out_dir)
    try:
        d.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise IntegrationError(
            f"Cannot create SAR output directory {d}: {exc}") from exc
    zip_path = d / (
        f"sar-{alumni_id}-"
        f"{_dt.datetime.now().strftime('%Y%m%d%H%M%S')}.zip")
    try:
      with _connect() as conn:
        tables = [row["name"] for row in conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type = 'table' AND name LIKE 'alumni%'"
            ).fetchall()]
        with _zip.ZipFile(zip_path, "w",
                            compression=_zip.ZIP_DEFLATED) as z:
            for tbl in sorted(tables):
                cols = [row[1] for row in conn.execute(
                    f"PRAGMA table_info({tbl})").fetchall()]
                if "alumni_id" not in cols and tbl != "alumni":
                    continue
                if tbl == "alumni":
                    rows = conn.execute(
                        "SELECT * FROM alumni WHERE alumni_id = ?",
                        (alumni_id,)).fetchall()
                else:
                    rows = conn.execute(
                        f"SELECT * FROM {tbl} WHERE alumni_id = ?",
                        (alumni_id,)).fetchall()
                if not rows:
                    continue
                buf = _io.StringIO()
                w = _csv.writer(buf)
                w.writerow(cols)
                for r in rows:
                    w.writerow([r[c] for c in cols])
                z.writestr(f"{tbl}.csv", buf.getvalue())
    except OSError as exc:
        raise IntegrationError(
            f"SAR bundle write failed at {zip_path}: {exc}") from exc
    _log_action("sar.bundle", actor=actor, alumni_id=alumni_id,
                  path=str(zip_path))
    return str(zip_path)


# ── #45 Right-to-erasure workflow ────────────────────────────────

@dataclass
class ErasureRequest:
    request_id: int
    alumni_id: int
    requested_at: str
    requested_by: str | None
    reason: str | None
    status: str
    reviewer: str | None
    reviewed_at: str | None
    review_notes: str | None
    completed_at: str | None
    confirmation_sent_at: str | None


def _row_erasure(r: sqlite3.Row) -> ErasureRequest:
    return ErasureRequest(
        request_id=r["request_id"], alumni_id=r["alumni_id"],
        requested_at=r["requested_at"],
        requested_by=r["requested_by"], reason=r["reason"],
        status=r["status"], reviewer=r["reviewer"],
        reviewed_at=r["reviewed_at"],
        review_notes=r["review_notes"],
        completed_at=r["completed_at"],
        confirmation_sent_at=r["confirmation_sent_at"])


def request_erasure(alumni_id: int, *,
                        requested_by: str | None = None,
                        reason: str | None = None,
                        actor: str | None = None) -> ErasureRequest:
    init_db()
    with _connect() as conn:
        _require_alumnus(conn, alumni_id)
        cur = conn.execute(
            """INSERT INTO alumni_erasure_requests
                   (alumni_id, requested_by, reason)
               VALUES (?, ?, ?)""",
            (alumni_id,
             (requested_by or "").strip() or None,
             (reason or "").strip() or None))
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_erasure_requests "
            "WHERE request_id = ?", (cur.lastrowid,)).fetchone()
    _log_action("erasure.request", actor=actor,
                  alumni_id=alumni_id, request_id=r["request_id"])
    _emit_webhook("alumnus.deleted", {"alumni_id": alumni_id,
                                          "stage": "requested"})
    return _row_erasure(r)


def review_erasure(request_id: int, *,
                       reviewer: str, decision: str,
                       review_notes: str | None = None,
                       actor: str | None = None) -> ErasureRequest:
    """Mark an erasure request as 'Approved' or 'Rejected'. Approval
    does NOT yet anonymise — call :func:`complete_erasure` after the
    statutory clock runs out (or as soon as you're ready)."""
    init_db()
    if decision not in ("Approved", "Rejected"):
        raise ValidationError(
            "decision must be 'Approved' or 'Rejected'")
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE alumni_erasure_requests "
            "SET status = ?, reviewer = ?, reviewed_at = ?, "
            "    review_notes = ? "
            "WHERE request_id = ? AND status IN "
            "    ('Requested', 'Under Review')",
            (decision, reviewer, now,
             (review_notes or "").strip() or None, request_id))
        if cur.rowcount == 0:
            raise ValidationError(
                f"No reviewable request #{request_id}")
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_erasure_requests "
            "WHERE request_id = ?", (request_id,)).fetchone()
    _log_action("erasure.review", actor=actor,
                  request_id=request_id, decision=decision)
    return _row_erasure(r)


def complete_erasure(request_id: int, *,
                         confirmation_sender: Callable[[int], None]
                         | None = None,
                         actor: str | None = None) -> ErasureRequest:
    """Carry out the anonymisation for an Approved request, stamp
    completed_at, and optionally fire ``confirmation_sender(alumni_id)``
    to email the data subject."""
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM alumni_erasure_requests "
            "WHERE request_id = ?", (request_id,)).fetchone()
        if r is None:
            raise ValidationError(
                f"No erasure request #{request_id}")
        if r["status"] != "Approved":
            raise ValidationError(
                "Request must be Approved before completion")
    anonymise_alumnus(r["alumni_id"])
    now = _dt.datetime.now().isoformat(timespec="seconds")
    conf_sent = None
    if confirmation_sender is not None:
        try:
            confirmation_sender(r["alumni_id"])
            conf_sent = now
        except Exception:
            logger.exception(
                "Erasure confirmation send failed for alumnus #%d",
                r["alumni_id"])
    with _connect() as conn:
        conn.execute(
            "UPDATE alumni_erasure_requests SET status = 'Completed', "
            "    completed_at = ?, confirmation_sent_at = ? "
            "WHERE request_id = ?",
            (now, conf_sent, request_id))
        conn.commit()
        row = conn.execute(
            "SELECT * FROM alumni_erasure_requests "
            "WHERE request_id = ?", (request_id,)).fetchone()
    _log_action("erasure.complete", actor=actor,
                  request_id=request_id, alumni_id=r["alumni_id"])
    return _row_erasure(row)


def list_erasure_requests(*, status: str | None = None
                               ) -> list[ErasureRequest]:
    init_db()
    sql = "SELECT * FROM alumni_erasure_requests WHERE 1=1"
    params: list[Any] = []
    if status:
        if status not in ERASURE_STATUSES:
            raise ValidationError(
                f"Status must be one of: "
                f"{', '.join(ERASURE_STATUSES)}")
        sql += " AND status = ?"
        params.append(status)
    sql += " ORDER BY requested_at DESC"
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_erasure(r) for r in rows]


# ── #46 Data quality dashboard ───────────────────────────────────

@dataclass
class DataQuality:
    total: int
    with_email_pct: float
    with_phone_pct: float
    with_address_pct: float
    missing_destination_pct: float
    stale_24mo_pct: float
    bounce_rate_pct: float
    opt_in_pct: float
    consent_data_storage_pct: float


def data_quality_report() -> DataQuality:
    init_db()
    with _connect() as conn:
        total = int(conn.execute(
            "SELECT COUNT(*) FROM alumni "
            "WHERE deleted_at IS NULL").fetchone()[0])
        if total == 0:
            return DataQuality(
                total=0, with_email_pct=0, with_phone_pct=0,
                with_address_pct=0, missing_destination_pct=0,
                stale_24mo_pct=0, bounce_rate_pct=0,
                opt_in_pct=0, consent_data_storage_pct=0)
        em = int(conn.execute(
            "SELECT COUNT(*) FROM alumni "
            "WHERE deleted_at IS NULL AND email IS NOT NULL "
            "  AND TRIM(email) <> ''").fetchone()[0])
        ph = int(conn.execute(
            "SELECT COUNT(*) FROM alumni "
            "WHERE deleted_at IS NULL AND phone IS NOT NULL "
            "  AND TRIM(phone) <> ''").fetchone()[0])
        ad = int(conn.execute(
            "SELECT COUNT(*) FROM alumni "
            "WHERE deleted_at IS NULL AND address IS NOT NULL "
            "  AND TRIM(address) <> ''").fetchone()[0])
        missing_dest = int(conn.execute(
            "SELECT COUNT(*) FROM alumni "
            "WHERE deleted_at IS NULL "
            "  AND (destination_type IS NULL "
            "       OR destination_type = 'Unknown')"
            ).fetchone()[0])
        bounce = int(conn.execute(
            "SELECT COUNT(*) FROM alumni "
            "WHERE deleted_at IS NULL "
            "  AND bounce_count >= ?",
            (HARD_BOUNCE_THRESHOLD,)).fetchone()[0])
        opt_in = int(conn.execute(
            "SELECT COUNT(*) FROM alumni "
            "WHERE deleted_at IS NULL AND opt_in_contact = 1"
            ).fetchone()[0])
        ds_consent = int(conn.execute(
            "SELECT COUNT(DISTINCT alumni_id) FROM alumni_consent "
            "WHERE scope = 'Data Storage' "
            "  AND withdrawn_at IS NULL").fetchone()[0])
        two_yrs_ago = (_dt.date.today() - _dt.timedelta(days=730)
                            ).isoformat()
        stale = int(conn.execute(
            "SELECT COUNT(*) FROM alumni "
            "WHERE deleted_at IS NULL "
            "  AND (last_contacted IS NULL "
            "       OR last_contacted < ?)",
            (two_yrs_ago,)).fetchone()[0])
    p = lambda n: round(100 * n / total, 1)
    return DataQuality(
        total=total,
        with_email_pct=p(em), with_phone_pct=p(ph),
        with_address_pct=p(ad),
        missing_destination_pct=p(missing_dest),
        stale_24mo_pct=p(stale), bounce_rate_pct=p(bounce),
        opt_in_pct=p(opt_in),
        consent_data_storage_pct=p(ds_consent))


# ── #47 Dedupe confidence buckets ────────────────────────────────

@dataclass
class DedupeBuckets:
    very_high: list[DuplicateCandidate]   # >= 0.95
    high:      list[DuplicateCandidate]   # 0.85 – 0.95
    medium:    list[DuplicateCandidate]   # 0.70 – 0.85


def dedupe_buckets(*, max_results: int = 200) -> DedupeBuckets:
    init_db()
    cands = find_duplicates(threshold=0.70)[:max_results]
    out = DedupeBuckets(very_high=[], high=[], medium=[])
    for c in cands:
        if c.score >= 0.95:
            out.very_high.append(c)
        elif c.score >= 0.85:
            out.high.append(c)
        else:
            out.medium.append(c)
    return out


def batch_confirm_merges(pairs: list[tuple[int, int]], *,
                              actor: str | None = None
                              ) -> tuple[int, list[str]]:
    """Run :func:`merge_alumni` for every (keep_id, merge_id) pair.
    Returns (successful_count, errors)."""
    init_db()
    ok = 0
    errors: list[str] = []
    for keep, drop in pairs:
        try:
            merge_alumni(keep, drop, actor=actor)
            ok += 1
        except Exception as exc:
            errors.append(f"keep={keep} merge={drop}: {exc}")
    _log_action("dedupe.batch_merge", actor=actor,
                  ok=ok, failed=len(errors))
    return ok, errors


# ── #48 Webhook events ───────────────────────────────────────────

@dataclass
class Webhook:
    webhook_id: int
    url: str
    secret: str | None
    event_types: list[str]
    active: bool
    created_at: str


def _row_webhook(r: sqlite3.Row) -> Webhook:
    return Webhook(
        webhook_id=r["webhook_id"], url=r["url"],
        secret=r["secret"],
        event_types=(r["event_types"] or "").split(","),
        active=bool(r["active"]),
        created_at=r["created_at"])


def register_webhook(url: str, *,
                          event_types: list[str],
                          secret: str | None = None,
                          actor: str | None = None) -> Webhook:
    init_db()
    if not (url or "").strip():
        raise ValidationError("Webhook URL is required")
    bad = [e for e in event_types if e not in WEBHOOK_EVENT_TYPES]
    if bad:
        raise ValidationError(
            f"Unknown event type(s): {', '.join(bad)}")
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO alumni_webhooks
                   (url, secret, event_types) VALUES (?, ?, ?)""",
            (url.strip(),
             (secret or "").strip() or None,
             ",".join(event_types)))
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_webhooks WHERE webhook_id = ?",
            (cur.lastrowid,)).fetchone()
    _log_action("webhook.register", actor=actor, url=url)
    return _row_webhook(r)


def list_webhooks() -> list[Webhook]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM alumni_webhooks "
            "ORDER BY webhook_id").fetchall()
    return [_row_webhook(r) for r in rows]


def set_webhook_active(webhook_id: int, active: bool, *,
                            actor: str | None = None) -> None:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE alumni_webhooks SET active = ? "
            "WHERE webhook_id = ?", (1 if active else 0, webhook_id))
        if cur.rowcount == 0:
            raise ValidationError(f"No webhook #{webhook_id}")
        conn.commit()
    _log_action("webhook.active", actor=actor,
                  webhook_id=webhook_id, active=active)


def delete_webhook(webhook_id: int, *,
                        actor: str | None = None) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM alumni_webhooks WHERE webhook_id = ?",
            (webhook_id,))
        conn.commit()
    if cur.rowcount:
        _log_action("webhook.delete", actor=actor,
                      webhook_id=webhook_id)
    return cur.rowcount > 0


# Pluggable transport: tests/callers can install their own delivery
# function. The default writes the queued row and leaves delivery to
# an out-of-process worker; pass set_webhook_transport(...) to
# integrate with the shared webhooks bus directly.
_webhook_transport: Callable[[str, str, dict[str, Any]], None] | None \
    = None


def set_webhook_transport(
        fn: Callable[[str, str, dict[str, Any]], None] | None
        ) -> None:
    global _webhook_transport
    _webhook_transport = fn


def _emit_webhook(event_type: str, payload: dict[str, Any]) -> None:
    """Internal helper. Queues a row in alumni_webhook_events and
    fires the configured transport for each subscribed webhook."""
    init_db()
    if event_type not in WEBHOOK_EVENT_TYPES:
        return  # defensive: unknown types are silently dropped
    import json as _json
    payload_json = _json.dumps(payload, default=str)
    with _connect() as conn:
        conn.execute(
            """INSERT INTO alumni_webhook_events
                   (event_type, payload_json) VALUES (?, ?)""",
            (event_type, payload_json))
        webhooks = conn.execute(
            "SELECT * FROM alumni_webhooks WHERE active = 1"
            ).fetchall()
        conn.commit()
    if _webhook_transport is None:
        return
    for w in webhooks:
        types = (w["event_types"] or "").split(",")
        if event_type not in types:
            continue
        try:
            _webhook_transport(w["url"], event_type, payload)
        except Exception:
            logger.exception("webhook transport failed url=%s", w["url"])


def list_recent_webhook_events(*, limit: int = 50
                                    ) -> list[dict[str, Any]]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM alumni_webhook_events "
            "ORDER BY event_id DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


# Hook existing top-level mutators so they auto-publish. We wrap
# rather than edit so existing call-sites stay unchanged.
_original_create_alumnus = create_alumnus
_original_record_donation = record_donation
_original_set_rsvp = set_rsvp


def create_alumnus(payload: dict[str, Any]) -> Alumnus:  # type: ignore[no-redef]
    a = _original_create_alumnus(payload)
    _emit_webhook("alumnus.created", {
        "alumni_id": a.alumni_id, "full_name": a.full_name,
        "leaving_year": a.leaving_year,
        "destination_type": a.destination_type})
    return a


def record_donation(alumni_id: int, payload: dict[str, Any]):  # type: ignore[no-redef]
    d = _original_record_donation(alumni_id, payload)
    _emit_webhook("donation.recorded", {
        "alumni_id": alumni_id,
        "donation_id": getattr(d, "donation_id", None),
        "amount_pence": getattr(d, "amount_pence", None)})
    return d


def set_rsvp(event_id: int, alumni_id: int, *,
                status: str | None = None,
                **kwargs):  # type: ignore[no-redef]
    r = _original_set_rsvp(event_id, alumni_id, status=status,
                              **kwargs)
    _emit_webhook("rsvp.changed", {
        "event_id": event_id, "alumni_id": alumni_id,
        "status": status})
    return r


# ── #49 Custom fields per institution ────────────────────────────

@dataclass
class CustomField:
    field_id: int
    name: str
    label: str
    type: str
    created_at: str


def _row_field(r: sqlite3.Row) -> CustomField:
    return CustomField(
        field_id=r["field_id"], name=r["name"], label=r["label"],
        type=r["type"], created_at=r["created_at"])


def add_custom_field(name: str, label: str, *,
                          type: str = "text",
                          actor: str | None = None) -> CustomField:
    init_db()
    name = (name or "").strip()
    if not name:
        raise ValidationError("Field name is required")
    if not (label or "").strip():
        raise ValidationError("Field label is required")
    if type not in CUSTOM_FIELD_TYPES:
        raise ValidationError(
            f"Type must be one of: {', '.join(CUSTOM_FIELD_TYPES)}")
    with _connect() as conn:
        try:
            cur = conn.execute(
                """INSERT INTO alumni_custom_fields
                       (name, label, type) VALUES (?, ?, ?)""",
                (name, label.strip(), type))
        except sqlite3.IntegrityError as exc:
            raise ValidationError(
                f"Custom field {name!r} already exists") from exc
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_custom_fields WHERE field_id = ?",
            (cur.lastrowid,)).fetchone()
    _log_action("custom_field.add", actor=actor, name=name, type=type)
    return _row_field(r)


def list_custom_fields() -> list[CustomField]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM alumni_custom_fields "
            "ORDER BY name COLLATE NOCASE").fetchall()
    return [_row_field(r) for r in rows]


def delete_custom_field(field_id: int, *,
                             actor: str | None = None) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM alumni_custom_fields WHERE field_id = ?",
            (field_id,))
        conn.commit()
    if cur.rowcount:
        _log_action("custom_field.delete", actor=actor,
                      field_id=field_id)
    return cur.rowcount > 0


def _coerce_custom(value: Any, type: str) -> str:
    if value in (None, ""):
        return ""
    if type == "boolean":
        return "1" if value else "0"
    if type == "number":
        return str(float(value))
    if type == "date":
        out = _validate_date(value, "value", required=False)
        return out or ""
    return str(value).strip()


def set_custom_value(alumni_id: int, name: str, value: Any, *,
                          actor: str | None = None) -> None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT field_id, type FROM alumni_custom_fields "
            "WHERE name = ? COLLATE NOCASE", (name,)).fetchone()
        if r is None:
            raise ValidationError(f"No custom field {name!r}")
        coerced = _coerce_custom(value, r["type"])
        _require_alumnus(conn, alumni_id)
        if coerced == "":
            conn.execute(
                "DELETE FROM alumni_custom_values "
                "WHERE alumni_id = ? AND field_id = ?",
                (alumni_id, r["field_id"]))
        else:
            conn.execute(
                """INSERT INTO alumni_custom_values
                       (alumni_id, field_id, value) VALUES (?, ?, ?)
                   ON CONFLICT(alumni_id, field_id) DO UPDATE SET
                       value = excluded.value""",
                (alumni_id, r["field_id"], coerced))
        conn.commit()
    _log_action("custom_field.set", actor=actor,
                  alumni_id=alumni_id, name=name)


def get_custom_values(alumni_id: int) -> dict[str, str]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            """SELECT f.name, v.value
                 FROM alumni_custom_values v
                 JOIN alumni_custom_fields f
                   ON f.field_id = v.field_id
                WHERE v.alumni_id = ?""", (alumni_id,)).fetchall()
    return {r["name"]: r["value"] for r in rows}


def search_by_custom(name: str, value: str) -> list[Alumnus]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            """SELECT a.* FROM alumni a
                 JOIN alumni_custom_values v
                   ON v.alumni_id = a.alumni_id
                 JOIN alumni_custom_fields f
                   ON f.field_id = v.field_id
                WHERE f.name = ? COLLATE NOCASE
                  AND v.value = ? COLLATE NOCASE
                  AND a.deleted_at IS NULL
                ORDER BY a.last_name, a.first_name""",
            (name, value)).fetchall()
    return [_row(r) for r in rows]


# ── #50 Photo / media attachments ────────────────────────────────

MEDIA_KINDS: tuple[str, ...] = (
    "photo", "graduation", "speaker_visit", "document", "video",
)


@dataclass
class MediaAttachment:
    media_id: int
    alumni_id: int
    kind: str
    file_path: str
    caption: str | None
    consent_granted: bool
    exif_stripped: bool
    is_profile: bool
    created_at: str


def _row_media(r: sqlite3.Row) -> MediaAttachment:
    return MediaAttachment(
        media_id=r["media_id"], alumni_id=r["alumni_id"],
        kind=r["kind"], file_path=r["file_path"],
        caption=r["caption"],
        consent_granted=bool(r["consent_granted"]),
        exif_stripped=bool(r["exif_stripped"]),
        is_profile=bool(r["is_profile"]),
        created_at=r["created_at"])


def _strip_exif(file_path: str) -> bool:
    """Best-effort EXIF strip. Returns True if a strip actually
    happened, False if the file is non-image or Pillow isn't
    installed. Never raises."""
    from pathlib import Path as _Path
    p = _Path(file_path)
    if p.suffix.lower() not in (".jpg", ".jpeg", ".tiff", ".webp",
                                   ".png"):
        return False
    try:
        from PIL import Image  # type: ignore
    except Exception:
        return False
    try:
        with Image.open(p) as im:
            data = list(im.getdata())
            stripped = Image.new(im.mode, im.size)
            stripped.putdata(data)
            stripped.save(p)
        return True
    except Exception:
        logger.exception("EXIF strip failed for %s", file_path)
        return False


def attach_media(alumni_id: int, file_path: str, *,
                      kind: str = "photo",
                      caption: str | None = None,
                      consent_granted: bool = False,
                      strip_exif: bool = True,
                      is_profile: bool = False,
                      actor: str | None = None
                      ) -> MediaAttachment:
    init_db()
    if kind not in MEDIA_KINDS:
        raise ValidationError(
            f"Kind must be one of: {', '.join(MEDIA_KINDS)}")
    from pathlib import Path as _Path
    if not _Path(file_path).exists():
        raise ValidationError(f"File not found: {file_path}")
    stripped = _strip_exif(file_path) if strip_exif else False
    with _connect() as conn:
        _require_alumnus(conn, alumni_id)
        if is_profile:
            conn.execute(
                "UPDATE alumni_media SET is_profile = 0 "
                "WHERE alumni_id = ?", (alumni_id,))
        cur = conn.execute(
            """INSERT INTO alumni_media
                   (alumni_id, kind, file_path, caption,
                    consent_granted, exif_stripped, is_profile)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (alumni_id, kind, str(file_path),
             (caption or "").strip() or None,
             1 if consent_granted else 0,
             1 if stripped else 0,
             1 if is_profile else 0))
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_media WHERE media_id = ?",
            (cur.lastrowid,)).fetchone()
    _log_action("media.attach", actor=actor,
                  alumni_id=alumni_id, kind=kind,
                  exif_stripped=stripped, is_profile=is_profile)
    return _row_media(r)


def list_media(alumni_id: int, *,
                    kind: str | None = None
                    ) -> list[MediaAttachment]:
    init_db()
    sql = "SELECT * FROM alumni_media WHERE alumni_id = ?"
    params: list[Any] = [alumni_id]
    if kind:
        sql += " AND kind = ?"; params.append(kind)
    sql += " ORDER BY created_at DESC"
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_media(r) for r in rows]


def set_media_consent(media_id: int, granted: bool, *,
                          actor: str | None = None) -> None:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE alumni_media SET consent_granted = ? "
            "WHERE media_id = ?", (1 if granted else 0, media_id))
        if cur.rowcount == 0:
            raise ValidationError(f"No media #{media_id}")
        conn.commit()
    _log_action("media.consent", actor=actor,
                  media_id=media_id, granted=granted)


def set_profile_media(alumni_id: int, media_id: int, *,
                          actor: str | None = None) -> None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT 1 FROM alumni_media "
            "WHERE media_id = ? AND alumni_id = ?",
            (media_id, alumni_id)).fetchone()
        if r is None:
            raise ValidationError(
                f"Media #{media_id} not attached to alumnus "
                f"#{alumni_id}")
        conn.execute(
            "UPDATE alumni_media SET is_profile = 0 "
            "WHERE alumni_id = ?", (alumni_id,))
        conn.execute(
            "UPDATE alumni_media SET is_profile = 1 "
            "WHERE media_id = ?", (media_id,))
        conn.commit()
    _log_action("media.profile", actor=actor,
                  alumni_id=alumni_id, media_id=media_id)


def delete_media(media_id: int, *,
                      delete_file: bool = False,
                      actor: str | None = None) -> bool:
    init_db()
    from pathlib import Path as _Path
    with _connect() as conn:
        r = conn.execute(
            "SELECT file_path FROM alumni_media WHERE media_id = ?",
            (media_id,)).fetchone()
        if r is None:
            return False
        path = r["file_path"]
        conn.execute(
            "DELETE FROM alumni_media WHERE media_id = ?",
            (media_id,))
        conn.commit()
    if delete_file:
        try:
            _Path(path).unlink(missing_ok=True)
        except Exception:
            logger.exception("Failed to unlink %s", path)
    _log_action("media.delete", actor=actor, media_id=media_id)
    return True



