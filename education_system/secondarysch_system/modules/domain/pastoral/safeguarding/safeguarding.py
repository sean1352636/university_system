"""Safeguarding data layer for the Secondary School System.

Two tables:

* ``safeguarding_concerns``    — one row per safeguarding concern
                                  raised about a pupil. Categories
                                  include neglect, physical /
                                  emotional / sexual abuse, CSE, FGM,
                                  Prevent, etc. Severity, DSL reviewer
                                  and a status workflow are tracked.
* ``safeguarding_actions``     — chronological log of actions taken
                                  on a concern (DSL meeting, parent
                                  contact, referral, etc.).

Concerns marked confidential are still logged but the description /
notes can be redacted in lists. The schema does not change behaviour;
logging access is the responsibility of the calling code.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
import sqlite3
from collections import Counter
from dataclasses import dataclass
from typing import Any

from education_system.secondarysch_system.modules.domain.pupils.pupils.pupils import (
    ValidationError, YEAR_GROUPS, _connect as _pupils_connect,
)

logger = logging.getLogger(__name__)

CONCERN_CATEGORIES: tuple[str, ...] = (
    "Neglect",
    "Physical abuse",
    "Emotional abuse",
    "Sexual abuse",
    "CSE (Child Sexual Exploitation)",
    "CCE (Child Criminal Exploitation)",
    "Domestic abuse exposure",
    "Bullying",
    "Online safety",
    "Mental health",
    "Self-harm",
    "Substance misuse",
    "FGM",
    "Forced marriage",
    "Prevent / radicalisation",
    "Missing from education",
    "Disclosure",
    "Other")
DEFAULT_CATEGORY: str = "Disclosure"

SEVERITIES: tuple[str, ...] = ("Low", "Medium", "High", "Critical")
DEFAULT_SEVERITY: str = "Medium"

CONCERN_STATUSES: tuple[str, ...] = (
    "Open", "Monitoring", "Referred",
    "Escalated", "Closed", "Transferred")
DEFAULT_STATUS: str = "Open"

REFERRAL_BODIES: tuple[str, ...] = (
    "MASH / Social Care", "Police", "CAMHS", "Early Help",
    "Channel (Prevent)", "Local Authority", "External agency",
    "Internal only", "Other")

ACTION_TYPES: tuple[str, ...] = (
    "DSL meeting", "Pupil interview", "Parent contact",
    "Multi-agency referral", "Police referral",
    "Strategy meeting", "Internal escalation",
    "Letter sent", "Phone call", "Home visit",
    "Follow-up review", "Other")
DEFAULT_ACTION_TYPE: str = "DSL meeting"

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS safeguarding_concerns (
    concern_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    pupil_id          TEXT NOT NULL,
    category          TEXT NOT NULL DEFAULT 'Disclosure',
    severity          TEXT NOT NULL DEFAULT 'Medium',
    incident_date     TEXT,
    incident_time     TEXT,
    location          TEXT,
    description       TEXT NOT NULL,
    raised_by         TEXT,
    raised_date       TEXT NOT NULL DEFAULT (date('now')),
    dsl_reviewer      TEXT,
    review_date       TEXT,
    status            TEXT NOT NULL DEFAULT 'Open',
    referral_body     TEXT,
    referral_date     TEXT,
    referral_reference TEXT,
    outcome           TEXT,
    closed_date       TEXT,
    confidential      INTEGER NOT NULL DEFAULT 1,
    notes             TEXT,
    created_at        TEXT DEFAULT (datetime('now')),
    updated_at        TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS safeguarding_actions (
    action_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    concern_id    INTEGER NOT NULL,
    action_date   TEXT NOT NULL DEFAULT (date('now')),
    action_type   TEXT NOT NULL DEFAULT 'DSL meeting',
    actioned_by   TEXT,
    summary       TEXT NOT NULL,
    outcome       TEXT,
    follow_up     TEXT,
    created_at    TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (concern_id) REFERENCES safeguarding_concerns(concern_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_sg_pupil
    ON safeguarding_concerns(pupil_id);
CREATE INDEX IF NOT EXISTS idx_sg_status
    ON safeguarding_concerns(status);
CREATE INDEX IF NOT EXISTS idx_sg_severity
    ON safeguarding_concerns(severity);
CREATE INDEX IF NOT EXISTS idx_sg_actions_concern
    ON safeguarding_actions(concern_id);
"""


@dataclass
class Concern:
    concern_id: int
    pupil_id: str
    category: str
    severity: str
    incident_date: str | None
    incident_time: str | None
    location: str | None
    description: str
    raised_by: str | None
    raised_date: str
    dsl_reviewer: str | None
    review_date: str | None
    status: str
    referral_body: str | None
    referral_date: str | None
    referral_reference: str | None
    outcome: str | None
    closed_date: str | None
    confidential: bool
    notes: str | None
    pupil_name: str | None = None
    pupil_year: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


@dataclass
class SGAction:
    action_id: int
    concern_id: int
    action_date: str
    action_type: str
    actioned_by: str | None
    summary: str
    outcome: str | None
    follow_up: str | None
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
        logger.exception("Failed to initialise safeguarding tables")
        raise
    logger.info("Secondary safeguarding tables ready")
    _DB_READY = True


def _row_concern(r: sqlite3.Row) -> Concern:
    keys = r.keys()
    return Concern(
        concern_id=r["concern_id"], pupil_id=r["pupil_id"],
        category=r["category"], severity=r["severity"],
        incident_date=r["incident_date"],
        incident_time=r["incident_time"],
        location=r["location"], description=r["description"],
        raised_by=r["raised_by"], raised_date=r["raised_date"],
        dsl_reviewer=r["dsl_reviewer"],
        review_date=r["review_date"],
        status=r["status"],
        referral_body=r["referral_body"],
        referral_date=r["referral_date"],
        referral_reference=r["referral_reference"],
        outcome=r["outcome"], closed_date=r["closed_date"],
        confidential=bool(r["confidential"]),
        notes=r["notes"],
        pupil_name=r["pupil_name"] if "pupil_name" in keys else None,
        pupil_year=r["pupil_year"] if "pupil_year" in keys else None,
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


def _row_action(r: sqlite3.Row) -> SGAction:
    return SGAction(
        action_id=r["action_id"], concern_id=r["concern_id"],
        action_date=r["action_date"], action_type=r["action_type"],
        actioned_by=r["actioned_by"], summary=r["summary"],
        outcome=r["outcome"], follow_up=r["follow_up"],
        created_at=r["created_at"],
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


def _validate_concern(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    pid = (data.get("pupil_id") or "").strip()
    if not pid:
        raise ValidationError("Pupil ID is required")
    from education_system.secondarysch_system.modules.domain.pupils.pupils import (
        pupils as pupils_data,
    )
    if pupils_data.get_pupil(pid) is None:
        raise ValidationError(f"No pupil with id {pid}")
    out["pupil_id"] = pid

    category = (data.get("category") or DEFAULT_CATEGORY).strip()
    if category not in CONCERN_CATEGORIES:
        raise ValidationError(
            f"Category must be one of: "
            f"{', '.join(CONCERN_CATEGORIES)}")
    out["category"] = category

    severity = (data.get("severity") or DEFAULT_SEVERITY).strip()
    if severity not in SEVERITIES:
        raise ValidationError(
            f"Severity must be one of {', '.join(SEVERITIES)}")
    out["severity"] = severity

    out["incident_date"] = _validate_date(
        data.get("incident_date"), "Incident date", required=False)
    t = (data.get("incident_time") or "").strip()
    if t:
        if not _TIME_RE.match(t):
            raise ValidationError(
                "Incident time must be HH:MM (24-hour)")
    out["incident_time"] = t or None
    out["location"] = (data.get("location") or "").strip() or None

    description = (data.get("description") or "").strip()
    if not description:
        raise ValidationError("Description is required")
    out["description"] = description

    out["raised_by"]   = (data.get("raised_by") or "").strip() or None
    out["raised_date"] = _validate_date(data.get("raised_date"),
                                          "Raised date")
    out["dsl_reviewer"] = (data.get("dsl_reviewer") or "").strip() or None
    out["review_date"] = _validate_date(
        data.get("review_date"), "Review date", required=False)

    status = (data.get("status") or DEFAULT_STATUS).strip()
    if status not in CONCERN_STATUSES:
        raise ValidationError(
            f"Status must be one of {', '.join(CONCERN_STATUSES)}")
    out["status"] = status

    body = (data.get("referral_body") or "").strip()
    if body and body not in REFERRAL_BODIES:
        raise ValidationError(
            f"Referral body must be one of "
            f"{', '.join(REFERRAL_BODIES)}")
    out["referral_body"] = body or None
    out["referral_date"] = _validate_date(
        data.get("referral_date"), "Referral date", required=False)
    out["referral_reference"] = (
        data.get("referral_reference") or "").strip() or None

    out["outcome"]     = (data.get("outcome") or "").strip() or None
    out["closed_date"] = _validate_date(
        data.get("closed_date"), "Closed date", required=False)

    confidential = data.get("confidential")
    out["confidential"] = (True if confidential is None
                            else bool(confidential))
    out["notes"]       = (data.get("notes") or "").strip() or None

    if status == "Closed" and not out["outcome"]:
        raise ValidationError(
            "Outcome is required when status is Closed")
    if status == "Closed" and not out["closed_date"]:
        out["closed_date"] = _dt.date.today().isoformat()
    if status == "Referred" and not out["referral_body"]:
        raise ValidationError(
            "Referral body is required when status is Referred")
    if out["closed_date"] and out["closed_date"] < out["raised_date"]:
        raise ValidationError("Closed date cannot be before raised date")
    if (out["referral_date"]
            and out["referral_date"] < out["raised_date"]):
        raise ValidationError(
            "Referral date cannot be before raised date")
    return out


def _validate_action(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    cid_raw = data.get("concern_id")
    if cid_raw in (None, ""):
        raise ValidationError("Concern ID is required")
    try:
        out["concern_id"] = int(cid_raw)
    except (TypeError, ValueError):
        raise ValidationError("Concern ID must be a number") from None

    out["action_date"] = _validate_date(data.get("action_date"),
                                          "Action date")
    atype = (data.get("action_type") or DEFAULT_ACTION_TYPE).strip()
    if atype not in ACTION_TYPES:
        raise ValidationError(
            f"Action type must be one of {', '.join(ACTION_TYPES)}")
    out["action_type"] = atype

    summary = (data.get("summary") or "").strip()
    if not summary:
        raise ValidationError("Summary is required")
    out["summary"] = summary

    out["actioned_by"] = (data.get("actioned_by") or "").strip() or None
    out["outcome"]     = (data.get("outcome") or "").strip() or None
    out["follow_up"]   = (data.get("follow_up") or "").strip() or None
    return out


# ── Concern CRUD ────────────────────────────────────────────────

def raise_concern(data: dict[str, Any]) -> Concern:
    init_db()
    payload = _validate_concern(data)
    try:
        with _connect() as conn:
            cur = conn.execute(
                """INSERT INTO safeguarding_concerns
                       (pupil_id, category, severity,
                        incident_date, incident_time, location,
                        description, raised_by, raised_date,
                        dsl_reviewer, review_date, status,
                        referral_body, referral_date,
                        referral_reference, outcome, closed_date,
                        confidential, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                           ?, ?, ?, ?, ?, ?, ?)""",
                (payload["pupil_id"], payload["category"],
                 payload["severity"], payload["incident_date"],
                 payload["incident_time"], payload["location"],
                 payload["description"], payload["raised_by"],
                 payload["raised_date"], payload["dsl_reviewer"],
                 payload["review_date"], payload["status"],
                 payload["referral_body"], payload["referral_date"],
                 payload["referral_reference"], payload["outcome"],
                 payload["closed_date"],
                 1 if payload["confidential"] else 0,
                 payload["notes"]),
            )
            conn.commit()
            new_id = cur.lastrowid
    except sqlite3.Error:
        logger.exception("Failed to raise safeguarding concern")
        raise
    rec = get(new_id)
    assert rec is not None
    # NOTE: do not log description content — keep payload narrow.
    logger.info(
        "Raised safeguarding concern #%d pupil=%s category=%s "
        "severity=%s status=%s confidential=%s",
        rec.concern_id, rec.pupil_id, rec.category, rec.severity,
        rec.status, rec.confidential)
    # Mirror onto the cross-system safeguarding register so the flag
    # follows the pupil into sixth form (best-effort; never blocks).
    try:
        from education_system.shared.safeguarding import alert_service
        alert_service.raise_flag_for_local_concern(
            "school", rec.pupil_id, category=rec.category,
            severity=rec.severity, summary=rec.category,
            source_ref=str(rec.concern_id), raised_by=rec.raised_by)
    except Exception:
        logger.debug("Cross-system safeguarding publish skipped for #%s",
                     rec.concern_id, exc_info=True)
    return rec


def get(concern_id: int) -> Concern | None:
    init_db()
    try:
        with _connect() as conn:
            r = conn.execute(
                """SELECT c.*,
                          (p.first_name || ' ' || p.last_name) AS pupil_name,
                          p.year_group AS pupil_year
                   FROM safeguarding_concerns c
                   LEFT JOIN pupils p ON p.pupil_id = c.pupil_id
                   WHERE c.concern_id = ?""",
                (concern_id,),
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get(%s) failed", concern_id)
        raise
    return _row_concern(r) if r else None


def list_concerns(*, pupil_id: str | None = None,
                  year_group: str | None = None,
                  category: str | None = None,
                  severity: str | None = None,
                  status: str | None = None,
                  date_from: str | None = None,
                  date_to: str | None = None) -> list[Concern]:
    init_db()
    where: list[str] = []
    params: list[Any] = []
    if pupil_id:
        where.append("c.pupil_id = ?")
        params.append(pupil_id.strip())
    if year_group:
        if year_group not in YEAR_GROUPS:
            raise ValidationError(
                f"Year filter must be one of {', '.join(YEAR_GROUPS)}")
        where.append("p.year_group = ?")
        params.append(year_group)
    if category:
        if category not in CONCERN_CATEGORIES:
            raise ValidationError(
                f"Category filter must be one of: "
                f"{', '.join(CONCERN_CATEGORIES)}")
        where.append("c.category = ?")
        params.append(category)
    if severity:
        if severity not in SEVERITIES:
            raise ValidationError(
                f"Severity filter must be one of "
                f"{', '.join(SEVERITIES)}")
        where.append("c.severity = ?")
        params.append(severity)
    if status:
        if status not in CONCERN_STATUSES:
            raise ValidationError(
                f"Status filter must be one of "
                f"{', '.join(CONCERN_STATUSES)}")
        where.append("c.status = ?")
        params.append(status)
    if date_from:
        where.append("c.raised_date >= ?")
        params.append(_validate_date(date_from, "From date"))
    if date_to:
        where.append("c.raised_date <= ?")
        params.append(_validate_date(date_to, "To date"))
    sql = ("""SELECT c.*,
                     (p.first_name || ' ' || p.last_name) AS pupil_name,
                     p.year_group AS pupil_year
              FROM safeguarding_concerns c
              LEFT JOIN pupils p ON p.pupil_id = c.pupil_id""")
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += (" ORDER BY CASE c.severity "
            " WHEN 'Critical' THEN 1 WHEN 'High' THEN 2 "
            " WHEN 'Medium' THEN 3 WHEN 'Low' THEN 4 END, "
            "c.raised_date DESC, c.concern_id DESC")
    try:
        with _connect() as conn:
            return [_row_concern(r)
                    for r in conn.execute(sql, tuple(params)).fetchall()]
    except sqlite3.Error:
        logger.exception("list_concerns failed")
        raise


def update(concern_id: int, data: dict[str, Any]) -> Concern:
    init_db()
    existing = get(concern_id)
    if existing is None:
        raise ValidationError(
            f"No safeguarding concern #{concern_id}")
    merged = {k: data.get(k, getattr(existing, k))
              for k in ("pupil_id", "category", "severity",
                         "incident_date", "incident_time", "location",
                         "description", "raised_by", "raised_date",
                         "dsl_reviewer", "review_date", "status",
                         "referral_body", "referral_date",
                         "referral_reference", "outcome",
                         "closed_date", "confidential", "notes")}
    payload = _validate_concern(merged)
    try:
        with _connect() as conn:
            conn.execute(
                """UPDATE safeguarding_concerns SET
                       pupil_id = ?, category = ?, severity = ?,
                       incident_date = ?, incident_time = ?,
                       location = ?, description = ?, raised_by = ?,
                       raised_date = ?, dsl_reviewer = ?,
                       review_date = ?, status = ?,
                       referral_body = ?, referral_date = ?,
                       referral_reference = ?, outcome = ?,
                       closed_date = ?, confidential = ?, notes = ?,
                       updated_at = datetime('now')
                   WHERE concern_id = ?""",
                (payload["pupil_id"], payload["category"],
                 payload["severity"], payload["incident_date"],
                 payload["incident_time"], payload["location"],
                 payload["description"], payload["raised_by"],
                 payload["raised_date"], payload["dsl_reviewer"],
                 payload["review_date"], payload["status"],
                 payload["referral_body"], payload["referral_date"],
                 payload["referral_reference"], payload["outcome"],
                 payload["closed_date"],
                 1 if payload["confidential"] else 0,
                 payload["notes"], concern_id),
            )
            conn.commit()
    except sqlite3.Error:
        logger.exception("Failed to update concern #%d", concern_id)
        raise
    rec = get(concern_id)
    assert rec is not None
    logger.info("Updated safeguarding concern #%d "
                "(status %s, severity %s)",
                rec.concern_id, rec.status, rec.severity)
    return rec


def set_status(concern_id: int, status: str,
                *, outcome: str | None = None,
                referral_body: str | None = None) -> Concern:
    payload: dict[str, Any] = {"status": status}
    if outcome is not None:
        payload["outcome"] = outcome
    if referral_body is not None:
        payload["referral_body"] = referral_body
    return update(concern_id, payload)


def delete(concern_id: int) -> bool:
    init_db()
    existing = get(concern_id)
    if existing is None:
        return False
    try:
        with _connect() as conn:
            conn.execute("PRAGMA foreign_keys=ON")
            cur = conn.execute(
                "DELETE FROM safeguarding_concerns "
                "WHERE concern_id = ?", (concern_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Failed to delete concern #%d", concern_id)
        raise
    if deleted:
        logger.info("Deleted safeguarding concern #%d (cascade: actions)",
                    concern_id)
    return deleted


# ── Actions ─────────────────────────────────────────────────────

def add_action(data: dict[str, Any]) -> SGAction:
    init_db()
    payload = _validate_action(data)
    if get(payload["concern_id"]) is None:
        raise ValidationError(
            f"No safeguarding concern #{payload['concern_id']}")
    try:
        with _connect() as conn:
            cur = conn.execute(
                """INSERT INTO safeguarding_actions
                       (concern_id, action_date, action_type,
                        actioned_by, summary, outcome, follow_up)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (payload["concern_id"], payload["action_date"],
                 payload["action_type"], payload["actioned_by"],
                 payload["summary"], payload["outcome"],
                 payload["follow_up"]),
            )
            conn.commit()
            new_id = cur.lastrowid
    except sqlite3.Error:
        logger.exception(
            "Failed to add action to concern %d",
            payload["concern_id"])
        raise
    logger.info(
        "Added safeguarding action #%d to concern #%d (%s, %s)",
        new_id, payload["concern_id"], payload["action_date"],
        payload["action_type"])
    rec = get_action(new_id)
    assert rec is not None
    return rec


def get_action(action_id: int) -> SGAction | None:
    init_db()
    try:
        with _connect() as conn:
            r = conn.execute(
                "SELECT * FROM safeguarding_actions WHERE action_id = ?",
                (action_id,),
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get_action(%s) failed", action_id)
        raise
    return _row_action(r) if r else None


def list_actions(concern_id: int) -> list[SGAction]:
    init_db()
    try:
        with _connect() as conn:
            return [_row_action(r) for r in conn.execute(
                "SELECT * FROM safeguarding_actions "
                "WHERE concern_id = ? "
                "ORDER BY action_date DESC, action_id DESC",
                (concern_id,),
            ).fetchall()]
    except sqlite3.Error:
        logger.exception("list_actions(%s) failed", concern_id)
        raise


def delete_action(action_id: int) -> bool:
    init_db()
    try:
        with _connect() as conn:
            cur = conn.execute(
                "DELETE FROM safeguarding_actions "
                "WHERE action_id = ?", (action_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception(
            "Failed to delete safeguarding action #%d", action_id)
        raise
    if deleted:
        logger.info("Deleted safeguarding action #%d", action_id)
    return deleted


def concern_summary(concern_id: int) -> dict[str, Any]:
    init_db()
    rec = get(concern_id)
    if rec is None:
        raise ValidationError(
            f"No safeguarding concern #{concern_id}")
    actions = list_actions(concern_id)
    return {
        "concern":      rec,
        "actions":      actions,
        "action_count": len(actions),
        "by_type":      dict(Counter(a.action_type for a in actions)),
    }


def cohort_summary(*, year_group: str | None = None,
                   date_from: str | None = None,
                   date_to: str | None = None) -> dict[str, Any]:
    rows = list_concerns(year_group=year_group,
                            date_from=date_from, date_to=date_to)
    open_count = sum(1 for r in rows
                       if r.status not in ("Closed",))
    return {
        "total":         len(rows),
        "open":          open_count,
        "by_status":     dict(Counter(r.status for r in rows)),
        "by_severity":   dict(Counter(r.severity for r in rows)),
        "by_category":   dict(Counter(r.category for r in rows)),
        "open_critical": sum(1 for r in rows
                              if r.severity == "Critical"
                              and r.status not in ("Closed",)),
    }


def pupils_with_concerns(*, severity_min: str = "High"
                         ) -> dict[str, list[Concern]]:
    """Return ``{pupil_id: [open concerns]}`` for pupils with at
    least one open concern at ``severity_min`` or above."""
    init_db()
    if severity_min not in SEVERITIES:
        raise ValidationError(
            f"severity_min must be one of {', '.join(SEVERITIES)}")
    threshold = SEVERITIES.index(severity_min)
    out: dict[str, list[Concern]] = {}
    for r in list_concerns():
        if r.status == "Closed":
            continue
        if SEVERITIES.index(r.severity) < threshold:
            continue
        out.setdefault(r.pupil_id, []).append(r)
    return out
