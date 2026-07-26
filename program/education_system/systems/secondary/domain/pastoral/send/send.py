"""SEND (Special Educational Needs and Disabilities) data layer.

Two tables:

* ``send_records``       — one row per (pupil, academic_year) on the
                            SEND register: provision stage (SEN Support
                            / EHCP / Monitoring / No SEN), category of
                            need, status, SENCo, key contacts.
* ``send_reviews``       — review history attached to a record. Each
                            review captures the date, reviewer,
                            progress notes, agreed adjustments, and
                            next-review date.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
import sqlite3
from collections import Counter
from dataclasses import dataclass
from typing import Any

from education_system.systems.secondary.domain.learners.pupils.pupils import (
    ValidationError, YEAR_GROUPS, _connect as _pupils_connect,
)

logger = logging.getLogger(__name__)

PROVISION_STAGES: tuple[str, ...] = (
    "No SEN", "Monitoring", "SEN Support", "EHCP (Education, Health, "
    "Care Plan)", "EHCP assessment in progress")
DEFAULT_STAGE: str = "Monitoring"

NEED_CATEGORIES: tuple[str, ...] = (
    "Communication and interaction",
    "Cognition and learning",
    "Social, emotional and mental health",
    "Sensory and/or physical needs",
    "Other")
DEFAULT_NEED: str = "Cognition and learning"

SEND_STATUSES: tuple[str, ...] = (
    "Active", "Discharged", "Transitioned", "On hold")
DEFAULT_STATUS: str = "Active"

REVIEW_OUTCOMES: tuple[str, ...] = (
    "Continue", "Adjust", "Escalate", "Discharge", "Reassess",
    "No change")
DEFAULT_OUTCOME: str = "Continue"

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_AY_RE = re.compile(r"^\d{4}/\d{2}$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS send_records (
    send_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    pupil_id           TEXT NOT NULL,
    academic_year      TEXT NOT NULL,
    provision_stage    TEXT NOT NULL DEFAULT 'Monitoring',
    primary_need       TEXT NOT NULL DEFAULT 'Cognition and learning',
    secondary_need     TEXT,
    status             TEXT NOT NULL DEFAULT 'Active',
    senco              TEXT,
    keyworker          TEXT,
    parent_contact     TEXT,
    parent_email       TEXT,
    ehcp_reference     TEXT,
    start_date         TEXT NOT NULL DEFAULT (date('now')),
    next_review_date   TEXT,
    provision_summary  TEXT,
    diagnosis          TEXT,
    notes              TEXT,
    created_at         TEXT DEFAULT (datetime('now')),
    updated_at         TEXT DEFAULT (datetime('now')),
    UNIQUE (pupil_id, academic_year)
);

CREATE TABLE IF NOT EXISTS send_reviews (
    review_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    send_id       INTEGER NOT NULL,
    review_date   TEXT NOT NULL DEFAULT (date('now')),
    reviewer      TEXT,
    progress      TEXT,
    adjustments   TEXT,
    outcome       TEXT NOT NULL DEFAULT 'Continue',
    next_review_date TEXT,
    notes         TEXT,
    created_at    TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (send_id) REFERENCES send_records(send_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_send_pupil
    ON send_records(pupil_id);
CREATE INDEX IF NOT EXISTS idx_send_stage
    ON send_records(provision_stage);
CREATE INDEX IF NOT EXISTS idx_send_reviews
    ON send_reviews(send_id);
"""


@dataclass
class SENDRecord:
    send_id: int
    pupil_id: str
    academic_year: str
    provision_stage: str
    primary_need: str
    secondary_need: str | None
    status: str
    senco: str | None
    keyworker: str | None
    parent_contact: str | None
    parent_email: str | None
    ehcp_reference: str | None
    start_date: str
    next_review_date: str | None
    provision_summary: str | None
    diagnosis: str | None
    notes: str | None
    pupil_name: str | None = None
    pupil_year: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


@dataclass
class SENDReview:
    review_id: int
    send_id: int
    review_date: str
    reviewer: str | None
    progress: str | None
    adjustments: str | None
    outcome: str
    next_review_date: str | None
    notes: str | None
    created_at: str | None = None


_DB_READY = False


def _connect() -> sqlite3.Connection:
    return _pupils_connect()


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    try:
        with _connect() as conn:
            conn.executescript(_SCHEMA)
    except sqlite3.Error:
        logger.exception("Failed to initialise send tables")
        raise
    logger.info("Secondary send tables ready")
    _DB_READY = True


def _row_record(r: sqlite3.Row) -> SENDRecord:
    keys = r.keys()
    return SENDRecord(
        send_id=r["send_id"], pupil_id=r["pupil_id"],
        academic_year=r["academic_year"],
        provision_stage=r["provision_stage"],
        primary_need=r["primary_need"],
        secondary_need=r["secondary_need"],
        status=r["status"], senco=r["senco"],
        keyworker=r["keyworker"],
        parent_contact=r["parent_contact"],
        parent_email=r["parent_email"],
        ehcp_reference=r["ehcp_reference"],
        start_date=r["start_date"],
        next_review_date=r["next_review_date"],
        provision_summary=r["provision_summary"],
        diagnosis=r["diagnosis"], notes=r["notes"],
        pupil_name=r["pupil_name"] if "pupil_name" in keys else None,
        pupil_year=r["pupil_year"] if "pupil_year" in keys else None,
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


def _row_review(r: sqlite3.Row) -> SENDReview:
    return SENDReview(
        review_id=r["review_id"], send_id=r["send_id"],
        review_date=r["review_date"], reviewer=r["reviewer"],
        progress=r["progress"], adjustments=r["adjustments"],
        outcome=r["outcome"],
        next_review_date=r["next_review_date"],
        notes=r["notes"], created_at=r["created_at"],
    )


def _validate_date(value: Any, label: str, *,
                   required: bool = True) -> str | None:
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        if required:
            return _dt.date.today().isoformat()
        return None
    s = str(value).strip()
    if not _DATE_RE.match(s):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    try:
        _dt.date.fromisoformat(s)
    except ValueError:
        raise ValidationError(f"{label} is not a real date") from None
    return s


def _validate_record(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    pid = (data.get("pupil_id") or "").strip()
    if not pid:
        raise ValidationError("Pupil ID is required")
    from education_system.systems.secondary.domain.learners.pupils import (
        pupils as pupils_data,
    )
    if pupils_data.get_pupil(pid) is None:
        raise ValidationError(f"No pupil with id {pid}")
    out["pupil_id"] = pid

    ay = (data.get("academic_year") or "").strip()
    if not ay:
        raise ValidationError("Academic year is required (e.g. 2025/26)")
    if not _AY_RE.match(ay):
        raise ValidationError(
            "Academic year must be in form YYYY/YY (e.g. 2025/26)")
    out["academic_year"] = ay

    stage = (data.get("provision_stage") or DEFAULT_STAGE).strip()
    if stage not in PROVISION_STAGES:
        raise ValidationError(
            f"Provision stage must be one of "
            f"{', '.join(PROVISION_STAGES)}")
    out["provision_stage"] = stage

    primary = (data.get("primary_need") or DEFAULT_NEED).strip()
    if primary not in NEED_CATEGORIES:
        raise ValidationError(
            f"Primary need must be one of "
            f"{', '.join(NEED_CATEGORIES)}")
    out["primary_need"] = primary

    secondary = (data.get("secondary_need") or "").strip()
    if secondary and secondary not in NEED_CATEGORIES:
        raise ValidationError(
            f"Secondary need must be one of "
            f"{', '.join(NEED_CATEGORIES)}")
    if secondary == primary:
        raise ValidationError(
            "Secondary need cannot equal primary need")
    out["secondary_need"] = secondary or None

    status = (data.get("status") or DEFAULT_STATUS).strip()
    if status not in SEND_STATUSES:
        raise ValidationError(
            f"Status must be one of {', '.join(SEND_STATUSES)}")
    out["status"] = status

    email = (data.get("parent_email") or "").strip()
    if email and not _EMAIL_RE.match(email):
        raise ValidationError("Parent email is not a valid address")
    out["parent_email"] = email or None

    ehcp = (data.get("ehcp_reference") or "").strip()
    out["ehcp_reference"] = ehcp or None
    if "EHCP" in stage and not ehcp:
        logger.warning(
            "EHCP-stage SEND record for pupil %s has no EHCP reference",
            pid)

    out["senco"]         = (data.get("senco") or "").strip() or None
    out["keyworker"]     = (data.get("keyworker") or "").strip() or None
    out["parent_contact"] = (data.get("parent_contact") or "").strip() or None
    out["provision_summary"] = (data.get("provision_summary") or "").strip() or None
    out["diagnosis"]     = (data.get("diagnosis") or "").strip() or None
    out["notes"]         = (data.get("notes") or "").strip() or None

    out["start_date"]       = _validate_date(
        data.get("start_date"), "Start date")
    out["next_review_date"] = _validate_date(
        data.get("next_review_date"), "Next review date",
        required=False)
    if (out["next_review_date"]
            and out["next_review_date"] < out["start_date"]):
        raise ValidationError(
            "Next review date cannot be before start date")
    return out


def _validate_review(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    sid_raw = data.get("send_id")
    if sid_raw in (None, ""):
        raise ValidationError("SEND record ID is required")
    try:
        out["send_id"] = int(sid_raw)
    except (TypeError, ValueError):
        raise ValidationError(
            "SEND record ID must be a number") from None

    out["review_date"] = _validate_date(data.get("review_date"),
                                          "Review date")
    out["reviewer"]    = (data.get("reviewer") or "").strip() or None
    out["progress"]    = (data.get("progress") or "").strip() or None
    out["adjustments"] = (data.get("adjustments") or "").strip() or None

    outcome = (data.get("outcome") or DEFAULT_OUTCOME).strip()
    if outcome not in REVIEW_OUTCOMES:
        raise ValidationError(
            f"Outcome must be one of {', '.join(REVIEW_OUTCOMES)}")
    out["outcome"] = outcome

    out["next_review_date"] = _validate_date(
        data.get("next_review_date"), "Next review date",
        required=False)
    if (out["next_review_date"]
            and out["next_review_date"] < out["review_date"]):
        raise ValidationError(
            "Next review date cannot be before review date")
    out["notes"] = (data.get("notes") or "").strip() or None
    return out


# ── Record CRUD ─────────────────────────────────────────────────

def upsert(data: dict[str, Any]) -> SENDRecord:
    init_db()
    payload = _validate_record(data)
    try:
        with _connect() as conn:
            row = conn.execute(
                "SELECT send_id FROM send_records "
                "WHERE pupil_id = ? AND academic_year = ?",
                (payload["pupil_id"], payload["academic_year"]),
            ).fetchone()
            cols = ("provision_stage", "primary_need", "secondary_need",
                    "status", "senco", "keyworker", "parent_contact",
                    "parent_email", "ehcp_reference", "start_date",
                    "next_review_date", "provision_summary",
                    "diagnosis", "notes")
            if row:
                conn.execute(
                    "UPDATE send_records SET "
                    + ", ".join(f"{c} = ?" for c in cols)
                    + ", updated_at = datetime('now') "
                    "WHERE send_id = ?",
                    (*(payload[c] for c in cols), row["send_id"]),
                )
                sid = row["send_id"]
                action = "updated"
            else:
                cur = conn.execute(
                    "INSERT INTO send_records "
                    "(pupil_id, academic_year, " + ", ".join(cols)
                    + ") VALUES ("
                    + ", ".join(["?"] * (2 + len(cols))) + ")",
                    (payload["pupil_id"], payload["academic_year"],
                     *(payload[c] for c in cols)),
                )
                sid = cur.lastrowid
                action = "inserted"
            conn.commit()
    except sqlite3.Error:
        logger.exception(
            "Failed to upsert SEND record for pupil %s year %s",
            payload["pupil_id"], payload["academic_year"])
        raise
    logger.info(
        "SEND record %s: pupil=%s year=%s stage=%s primary=%s status=%s",
        action, payload["pupil_id"], payload["academic_year"],
        payload["provision_stage"], payload["primary_need"],
        payload["status"])
    rec = get(sid)
    assert rec is not None
    return rec


def get(send_id: int) -> SENDRecord | None:
    init_db()
    try:
        with _connect() as conn:
            r = conn.execute(
                """SELECT s.*,
                          (p.first_name || ' ' || p.last_name) AS pupil_name,
                          p.year_group AS pupil_year
                   FROM send_records s
                   LEFT JOIN pupils p ON p.pupil_id = s.pupil_id
                   WHERE s.send_id = ?""",
                (send_id,),
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get(%s) failed", send_id)
        raise
    return _row_record(r) if r else None


def get_for(pupil_id: str,
            academic_year: str) -> SENDRecord | None:
    init_db()
    try:
        with _connect() as conn:
            r = conn.execute(
                """SELECT s.*,
                          (p.first_name || ' ' || p.last_name) AS pupil_name,
                          p.year_group AS pupil_year
                   FROM send_records s
                   LEFT JOIN pupils p ON p.pupil_id = s.pupil_id
                   WHERE s.pupil_id = ? AND s.academic_year = ?""",
                ((pupil_id or "").strip(),
                 (academic_year or "").strip()),
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get_for(%s, %s) failed",
                         pupil_id, academic_year)
        raise
    return _row_record(r) if r else None


def list_records(*, year_group: str | None = None,
                 academic_year: str | None = None,
                 provision_stage: str | None = None,
                 primary_need: str | None = None,
                 status: str | None = None,
                 pupil_id: str | None = None
                 ) -> list[SENDRecord]:
    init_db()
    where: list[str] = []
    params: list[Any] = []
    if year_group:
        if year_group not in YEAR_GROUPS:
            raise ValidationError(
                f"Year filter must be one of {', '.join(YEAR_GROUPS)}")
        where.append("p.year_group = ?")
        params.append(year_group)
    if academic_year:
        where.append("s.academic_year = ?")
        params.append(academic_year.strip())
    if provision_stage:
        if provision_stage not in PROVISION_STAGES:
            raise ValidationError(
                f"Stage filter must be one of "
                f"{', '.join(PROVISION_STAGES)}")
        where.append("s.provision_stage = ?")
        params.append(provision_stage)
    if primary_need:
        if primary_need not in NEED_CATEGORIES:
            raise ValidationError(
                f"Need filter must be one of "
                f"{', '.join(NEED_CATEGORIES)}")
        where.append("s.primary_need = ?")
        params.append(primary_need)
    if status:
        if status not in SEND_STATUSES:
            raise ValidationError(
                f"Status filter must be one of "
                f"{', '.join(SEND_STATUSES)}")
        where.append("s.status = ?")
        params.append(status)
    if pupil_id:
        where.append("s.pupil_id = ?")
        params.append(pupil_id.strip())
    sql = ("""SELECT s.*,
                     (p.first_name || ' ' || p.last_name) AS pupil_name,
                     p.year_group AS pupil_year
              FROM send_records s
              LEFT JOIN pupils p ON p.pupil_id = s.pupil_id""")
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += (" ORDER BY s.academic_year DESC, p.year_group, "
            "p.last_name, p.first_name")
    try:
        with _connect() as conn:
            return [_row_record(r)
                    for r in conn.execute(sql, tuple(params)).fetchall()]
    except sqlite3.Error:
        logger.exception("list_records failed")
        raise


def delete(send_id: int) -> bool:
    init_db()
    existing = get(send_id)
    if existing is None:
        return False
    try:
        with _connect() as conn:
            conn.execute("PRAGMA foreign_keys=ON")
            cur = conn.execute(
                "DELETE FROM send_records WHERE send_id = ?",
                (send_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Failed to delete SEND record #%d", send_id)
        raise
    if deleted:
        logger.info("Deleted SEND record #%d %s/%s "
                    "(cascade: reviews)",
                    send_id, existing.pupil_id, existing.academic_year)
    return deleted


# ── Reviews ─────────────────────────────────────────────────────

def add_review(data: dict[str, Any]) -> SENDReview:
    init_db()
    payload = _validate_review(data)
    if get(payload["send_id"]) is None:
        raise ValidationError(f"No SEND record #{payload['send_id']}")
    try:
        with _connect() as conn:
            cur = conn.execute(
                """INSERT INTO send_reviews
                       (send_id, review_date, reviewer, progress,
                        adjustments, outcome, next_review_date, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (payload["send_id"], payload["review_date"],
                 payload["reviewer"], payload["progress"],
                 payload["adjustments"], payload["outcome"],
                 payload["next_review_date"], payload["notes"]),
            )
            # Also push the next review date back onto the parent record
            # so the SEND register's "next review" column is fresh.
            if payload["next_review_date"]:
                conn.execute(
                    "UPDATE send_records SET next_review_date = ?, "
                    "updated_at = datetime('now') WHERE send_id = ?",
                    (payload["next_review_date"], payload["send_id"]),
                )
            conn.commit()
            new_id = cur.lastrowid
    except sqlite3.Error:
        logger.exception(
            "Failed to add review to SEND record %d",
            payload["send_id"])
        raise
    logger.info(
        "Added SEND review #%d to record #%d (outcome=%s, next=%s)",
        new_id, payload["send_id"], payload["outcome"],
        payload["next_review_date"])
    rec = get_review(new_id)
    assert rec is not None
    return rec


def get_review(review_id: int) -> SENDReview | None:
    init_db()
    try:
        with _connect() as conn:
            r = conn.execute(
                "SELECT * FROM send_reviews WHERE review_id = ?",
                (review_id,),
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get_review(%s) failed", review_id)
        raise
    return _row_review(r) if r else None


def list_reviews(send_id: int) -> list[SENDReview]:
    init_db()
    try:
        with _connect() as conn:
            return [_row_review(r) for r in conn.execute(
                "SELECT * FROM send_reviews WHERE send_id = ? "
                "ORDER BY review_date DESC, review_id DESC",
                (send_id,),
            ).fetchall()]
    except sqlite3.Error:
        logger.exception("list_reviews(%s) failed", send_id)
        raise


def delete_review(review_id: int) -> bool:
    init_db()
    try:
        with _connect() as conn:
            cur = conn.execute(
                "DELETE FROM send_reviews WHERE review_id = ?",
                (review_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception(
            "Failed to delete SEND review #%d", review_id)
        raise
    if deleted:
        logger.info("Deleted SEND review #%d", review_id)
    return deleted


def record_summary(send_id: int) -> dict[str, Any]:
    init_db()
    rec = get(send_id)
    if rec is None:
        raise ValidationError(f"No SEND record #{send_id}")
    reviews = list_reviews(send_id)
    return {
        "record":      rec,
        "reviews":     reviews,
        "review_count": len(reviews),
        "by_outcome":  dict(Counter(r.outcome for r in reviews)),
        "last_review": reviews[0].review_date if reviews else None,
    }


def cohort_summary(*, year_group: str | None = None,
                   academic_year: str | None = None) -> dict[str, Any]:
    rows = list_records(year_group=year_group,
                          academic_year=academic_year)
    return {
        "total":          len(rows),
        "by_stage":       dict(Counter(r.provision_stage for r in rows)),
        "by_primary_need": dict(Counter(r.primary_need for r in rows)),
        "by_status":      dict(Counter(r.status for r in rows)),
        "ehcp_count":     sum(1 for r in rows
                                if "EHCP" in r.provision_stage),
    }


def overdue_reviews(today: str | None = None) -> list[SENDRecord]:
    """Return Active SEND records whose ``next_review_date`` is in the
    past (or today if not specified)."""
    init_db()
    cmp_date = (today or _dt.date.today().isoformat())
    rows = list_records(status="Active")
    return [r for r in rows
            if r.next_review_date and r.next_review_date < cmp_date]
