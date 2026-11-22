"""Sixth-form alumni — Connection, the single init_db (base schema then each extension schema), row mapping and payload validation.

Owns the mutable module state ``DB_PATH`` and ``_DB_READY`` (forwarded by the ``alumni`` facade).

Split out of :mod:`education_system.systems.sixth_form.domain.learners.alumni.alumni`, which re-exports
every name; import from there.
"""

from __future__ import annotations

import datetime as _dt
from typing import Any
from education_system import paths
from education_system.systems.sixth_form.infrastructure import database as db

from .models import (
    Alumnus,
    DEFAULT_DESTINATION,
    DEFAULT_STATUS,
    DESTINATION_TYPES,
    GENDER_OPTIONS,
    LEAVING_REASONS,
    SECTORS,
    STATUSES,
    _DATE_RE,
    _EMAIL_RE,
    _PHONE_RE,
    _YEAR_RE,
    logger,
)
from .schema import (
    _ALUMNI_NEW_COLUMNS,
    _ALUMNI_NEW_COLUMNS_V2,
    _DONATION_NEW_COLUMNS,
    _MENTOR_SESSION_NEW_COLUMNS,
    _PROTECTED_CHAR_COLS,
    _RSVP_NEW_COLUMNS,
    _SCHEMA,
    _SCHEMA_CAREER_EXT,
    _SCHEMA_COMMS_EXT,
    _SCHEMA_ENGAGEMENT,
    _SCHEMA_EVENTS_EXT,
    _SCHEMA_FINAL_EXT,
    _SCHEMA_FUNDRAISING_EXT,
    _SCHEMA_OUTCOMES_EXT,
)


DB_PATH = paths.SIXTH_FORM_ALUMNI_DB


# ── DB plumbing ────────────────────────────────────────────────────

def _connect() -> db.Connection:
    paths.ensure_sixth_form_directories()
    conn = db.connect(str(DB_PATH))
    conn.row_factory = db.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


_DB_READY: bool = False


def _migrate_alumni_columns(conn: db.Connection) -> None:
    existing = {row[1] for row in conn.execute(
        "PRAGMA table_info(alumni)").fetchall()}
    for col, decl in _ALUMNI_NEW_COLUMNS:
        if col not in existing:
            conn.execute(f"ALTER TABLE alumni ADD COLUMN {col} {decl}")


def _opt(r: db.Row, key: str) -> Any:
    try:
        return r[key]
    except (IndexError, KeyError):
        return None


def _row(r: db.Row) -> Alumnus:
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


def _init_engagement_schema() -> None:
    """Idempotently install the engagement-extension tables. Called
    from :func:`init_db` after the main schema. Splitting it out keeps
    the original ``_SCHEMA`` constant unchanged so existing migrations
    keep working."""
    with _connect() as conn:
        conn.executescript(_SCHEMA_ENGAGEMENT)


def _init_career_ext_schema() -> None:
    with _connect() as conn:
        conn.executescript(_SCHEMA_CAREER_EXT)


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


def _init_final_ext_schema() -> None:
    with _connect() as conn:
        conn.executescript(_SCHEMA_FINAL_EXT)
        existing = {row[1] for row in conn.execute(
            "PRAGMA table_info(alumni)").fetchall()}
        for col, decl in _PROTECTED_CHAR_COLS:
            if col not in existing:
                conn.execute(
                    f"ALTER TABLE alumni ADD COLUMN {col} {decl}")


# ── init_db ───────────────────────────────────────────────────────
# The old single-file module grew its schema by re-binding ``init_db``
# five times, each wrapper capturing ``already = _DB_READY`` before
# calling the previous one and then installing one extension schema.
# This is the same sequence written out once: the base schema (which
# sets ``_DB_READY``), then each extension schema in the original
# order — all skipped when ``_DB_READY`` was already true on entry.

_EXT_SCHEMA_STEPS = (
    _init_engagement_schema,
    _init_career_ext_schema,
    _init_comms_ext_schema,
    _init_events_funding_outcomes,
    _init_final_ext_schema,
)


def _init_db_through(steps: int) -> None:
    """Run the base schema, then the first ``steps`` extension schemas,
    unless the database was already initialised on entry."""
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
    for step in _EXT_SCHEMA_STEPS[:steps]:
        step()


def init_db() -> None:
    _init_db_through(len(_EXT_SCHEMA_STEPS))


# Names kept from the old wrapper chain. Each is the init_db that was
# in force at that point of the old file: the base schema only, then
# base + the first 1..4 extension schemas.
def _original_init_db() -> None:
    _init_db_through(0)


def _original_init_db_v2() -> None:
    _init_db_through(1)


def _original_init_db_v3() -> None:
    _init_db_through(2)


def _original_init_db_v4() -> None:
    _init_db_through(3)


def _original_init_db_v5() -> None:
    _init_db_through(4)
