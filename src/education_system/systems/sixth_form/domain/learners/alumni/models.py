"""Sixth-form alumni — Constants, enumerations, export field list, logger and the record dataclasses.

Split out of :mod:`education_system.systems.sixth_form.domain.learners.alumni.alumni`, which re-exports
every name; import from there.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any
from education_system.systems.sixth_form.infrastructure import log_store


logger = logging.getLogger("education_system.systems.sixth_form.domain.learners.alumni.alumni")

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
