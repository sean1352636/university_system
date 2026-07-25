"""Prevent-duty referral tracking for the Secondary School System.

UK statutory duty to safeguard pupils from being drawn into terrorism.
Each row records a Prevent concern: pupil, concern type (e.g. Far-right,
Islamist extremism, Incel, Other), risk level, referral pathway
(Internal / Channel / Police) and outcome.
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
    ValidationError, _connect as _pupils_connect,
)

logger = logging.getLogger(__name__)

CONCERN_TYPES: tuple[str, ...] = (
    "Far-right extremism", "Islamist extremism",
    "Far-left extremism", "Incel/Misogynistic",
    "Single-issue (animal rights, environmental, etc.)",
    "Conspiracy theories", "Vulnerability to radicalisation",
    "Hate speech / Online", "Other")
DEFAULT_CONCERN: str = "Vulnerability to radicalisation"

RISK_LEVELS: tuple[str, ...] = (
    "Low", "Medium", "High", "Imminent")
DEFAULT_RISK: str = "Low"

REFERRAL_PATHWAYS: tuple[str, ...] = (
    "Internal monitoring", "DSL only",
    "Channel referral (Prevent)", "Police referral",
    "Other agency", "No referral")
DEFAULT_PATHWAY: str = "Internal monitoring"

STATUSES: tuple[str, ...] = (
    "Open", "Monitoring", "Channel panel", "Closed — no further action",
    "Closed — supported", "Closed — escalated")
DEFAULT_STATUS: str = "Open"

OUTCOMES: tuple[str, ...] = (
    "Pending", "Diverted", "Supported", "Charged",
    "No further action", "Other")
DEFAULT_OUTCOME: str = "Pending"

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS prevent_referrals (
    referral_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    pupil_id         TEXT NOT NULL,
    concern_type     TEXT NOT NULL DEFAULT 'Vulnerability to radicalisation',
    risk_level       TEXT NOT NULL DEFAULT 'Low',
    raised_by        TEXT NOT NULL,
    raised_date      TEXT NOT NULL DEFAULT (date('now')),
    dsl_informed     INTEGER NOT NULL DEFAULT 0,
    dsl_name         TEXT,
    dsl_informed_date TEXT,
    description      TEXT NOT NULL,
    indicators       TEXT,
    online_activity  TEXT,
    referral_pathway TEXT NOT NULL DEFAULT 'Internal monitoring',
    referral_date    TEXT,
    referral_ref     TEXT,
    agencies_involved TEXT,
    parents_informed INTEGER NOT NULL DEFAULT 0,
    parents_informed_date TEXT,
    next_review_date TEXT,
    status           TEXT NOT NULL DEFAULT 'Open',
    outcome          TEXT NOT NULL DEFAULT 'Pending',
    closed_date      TEXT,
    closure_notes    TEXT,
    notes            TEXT,
    created_at       TEXT DEFAULT (datetime('now')),
    updated_at       TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_pr_pupil
    ON prevent_referrals(pupil_id);
CREATE INDEX IF NOT EXISTS idx_pr_status
    ON prevent_referrals(status);
CREATE INDEX IF NOT EXISTS idx_pr_risk
    ON prevent_referrals(risk_level);
CREATE INDEX IF NOT EXISTS idx_pr_date
    ON prevent_referrals(raised_date);
"""


@dataclass
class Referral:
    referral_id: int
    pupil_id: str
    concern_type: str
    risk_level: str
    raised_by: str
    raised_date: str
    dsl_informed: bool
    dsl_name: str | None
    dsl_informed_date: str | None
    description: str
    indicators: str | None
    online_activity: str | None
    referral_pathway: str
    referral_date: str | None
    referral_ref: str | None
    agencies_involved: str | None
    parents_informed: bool
    parents_informed_date: str | None
    next_review_date: str | None
    status: str
    outcome: str
    closed_date: str | None
    closure_notes: str | None
    notes: str | None
    pupil_name: str | None = None
    pupil_year: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


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
        logger.exception(
            "Failed to initialise prevent_referrals tables")
        raise
    logger.info("Secondary prevent_referrals tables ready")
    _DB_READY = True


def _row(r: sqlite3.Row) -> Referral:
    keys = r.keys()
    return Referral(
        referral_id=r["referral_id"], pupil_id=r["pupil_id"],
        concern_type=r["concern_type"], risk_level=r["risk_level"],
        raised_by=r["raised_by"], raised_date=r["raised_date"],
        dsl_informed=bool(r["dsl_informed"]),
        dsl_name=r["dsl_name"],
        dsl_informed_date=r["dsl_informed_date"],
        description=r["description"], indicators=r["indicators"],
        online_activity=r["online_activity"],
        referral_pathway=r["referral_pathway"],
        referral_date=r["referral_date"],
        referral_ref=r["referral_ref"],
        agencies_involved=r["agencies_involved"],
        parents_informed=bool(r["parents_informed"]),
        parents_informed_date=r["parents_informed_date"],
        next_review_date=r["next_review_date"],
        status=r["status"], outcome=r["outcome"],
        closed_date=r["closed_date"],
        closure_notes=r["closure_notes"], notes=r["notes"],
        pupil_name=r["pupil_name"] if "pupil_name" in keys else None,
        pupil_year=r["pupil_year"] if "pupil_year" in keys else None,
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


def _validate_date(value: Any, label: str, *,
                   required: bool = True) -> str | None:
    if value in (None, "") or (isinstance(value, str)
                                  and not value.strip()):
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


def _validate(data: dict[str, Any]) -> dict[str, Any]:
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

    ctype = (data.get("concern_type") or DEFAULT_CONCERN).strip()
    if ctype not in CONCERN_TYPES:
        raise ValidationError(
            f"Concern type must be one of "
            f"{', '.join(CONCERN_TYPES)}")
    out["concern_type"] = ctype

    risk = (data.get("risk_level") or DEFAULT_RISK).strip()
    if risk not in RISK_LEVELS:
        raise ValidationError(
            f"Risk level must be one of {', '.join(RISK_LEVELS)}")
    out["risk_level"] = risk

    raised_by = (data.get("raised_by") or "").strip()
    if not raised_by:
        raise ValidationError("Raised-by is required")
    out["raised_by"] = raised_by

    out["raised_date"] = _validate_date(
        data.get("raised_date"), "Raised date")

    out["dsl_informed"]      = bool(data.get("dsl_informed"))
    out["dsl_name"]          = (data.get("dsl_name") or "").strip() or None
    out["dsl_informed_date"] = _validate_date(
        data.get("dsl_informed_date"), "DSL informed date",
        required=False)
    if out["dsl_informed"]:
        if not out["dsl_name"]:
            raise ValidationError(
                "DSL name is required when DSL has been informed")
        if not out["dsl_informed_date"]:
            out["dsl_informed_date"] = _dt.date.today().isoformat()

    description = (data.get("description") or "").strip()
    if not description:
        raise ValidationError("Description is required")
    if len(description) > 4000:
        raise ValidationError(
            "Description is too long (max 4000 chars)")
    out["description"] = description

    out["indicators"]      = (data.get("indicators") or "").strip() or None
    out["online_activity"] = (data.get("online_activity") or "").strip() or None

    pathway = (data.get("referral_pathway") or DEFAULT_PATHWAY).strip()
    if pathway not in REFERRAL_PATHWAYS:
        raise ValidationError(
            f"Referral pathway must be one of "
            f"{', '.join(REFERRAL_PATHWAYS)}")
    out["referral_pathway"] = pathway

    out["referral_date"] = _validate_date(
        data.get("referral_date"), "Referral date",
        required=False)
    out["referral_ref"]  = (data.get("referral_ref") or "").strip() or None
    out["agencies_involved"] = (
        data.get("agencies_involved") or "").strip() or None

    if pathway in ("Channel referral (Prevent)",
                     "Police referral", "Other agency"):
        if not out["referral_date"]:
            raise ValidationError(
                f"Referral date is required for pathway {pathway}")
        if not out["dsl_informed"]:
            raise ValidationError(
                "DSL must be informed before an external referral")

    out["parents_informed"] = bool(data.get("parents_informed"))
    out["parents_informed_date"] = _validate_date(
        data.get("parents_informed_date"),
        "Parents informed date", required=False)
    if (out["parents_informed"]
            and not out["parents_informed_date"]):
        out["parents_informed_date"] = _dt.date.today().isoformat()

    out["next_review_date"] = _validate_date(
        data.get("next_review_date"), "Next review date",
        required=False)
    if (out["next_review_date"]
            and out["next_review_date"] < out["raised_date"]):
        raise ValidationError(
            "Next review date cannot be before raised date")

    status = (data.get("status") or DEFAULT_STATUS).strip()
    if status not in STATUSES:
        raise ValidationError(
            f"Status must be one of {', '.join(STATUSES)}")
    out["status"] = status

    outcome = (data.get("outcome") or DEFAULT_OUTCOME).strip()
    if outcome not in OUTCOMES:
        raise ValidationError(
            f"Outcome must be one of {', '.join(OUTCOMES)}")
    out["outcome"] = outcome

    out["closed_date"] = _validate_date(
        data.get("closed_date"), "Closed date", required=False)
    out["closure_notes"] = (
        data.get("closure_notes") or "").strip() or None

    is_closed = status.startswith("Closed")
    if is_closed:
        if not out["closed_date"]:
            out["closed_date"] = _dt.date.today().isoformat()
        if out["closed_date"] < out["raised_date"]:
            raise ValidationError(
                "Closed date cannot be before raised date")
        if outcome == "Pending":
            raise ValidationError(
                "Outcome cannot be 'Pending' on a closed referral")
    else:
        if out["closed_date"]:
            raise ValidationError(
                "Closed date should only be set when status is "
                "one of the Closed values")

    if risk in ("High", "Imminent") and not out["dsl_informed"]:
        raise ValidationError(
            f"DSL must be informed for {risk}-risk referrals")

    out["notes"] = (data.get("notes") or "").strip() or None
    return out


def create(data: dict[str, Any]) -> Referral:
    init_db()
    payload = _validate(data)
    try:
        with _connect() as conn:
            cur = conn.execute(
                """INSERT INTO prevent_referrals
                       (pupil_id, concern_type, risk_level,
                        raised_by, raised_date, dsl_informed,
                        dsl_name, dsl_informed_date, description,
                        indicators, online_activity,
                        referral_pathway, referral_date,
                        referral_ref, agencies_involved,
                        parents_informed, parents_informed_date,
                        next_review_date, status, outcome,
                        closed_date, closure_notes, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                           ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (payload["pupil_id"], payload["concern_type"],
                 payload["risk_level"], payload["raised_by"],
                 payload["raised_date"],
                 1 if payload["dsl_informed"] else 0,
                 payload["dsl_name"], payload["dsl_informed_date"],
                 payload["description"], payload["indicators"],
                 payload["online_activity"],
                 payload["referral_pathway"],
                 payload["referral_date"], payload["referral_ref"],
                 payload["agencies_involved"],
                 1 if payload["parents_informed"] else 0,
                 payload["parents_informed_date"],
                 payload["next_review_date"],
                 payload["status"], payload["outcome"],
                 payload["closed_date"], payload["closure_notes"],
                 payload["notes"]),
            )
            conn.commit()
            new_id = cur.lastrowid
    except sqlite3.Error:
        logger.exception("Failed to create Prevent referral")
        raise
    rec = get(new_id)
    assert rec is not None
    logger.info(
        "Created Prevent referral #%d pupil=%s concern=%s "
        "risk=%s pathway=%s status=%s",
        rec.referral_id, rec.pupil_id, rec.concern_type,
        rec.risk_level, rec.referral_pathway, rec.status)
    return rec


def get(referral_id: int) -> Referral | None:
    init_db()
    try:
        with _connect() as conn:
            r = conn.execute(
                """SELECT pr.*,
                          (p.first_name || ' ' || p.last_name) AS pupil_name,
                          p.year_group AS pupil_year
                   FROM prevent_referrals pr
                   LEFT JOIN pupils p ON p.pupil_id = pr.pupil_id
                   WHERE pr.referral_id = ?""",
                (referral_id,),
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get(%s) failed", referral_id)
        raise
    return _row(r) if r else None


def list_referrals(*, pupil_id: str | None = None,
                    status: str | None = None,
                    risk_level: str | None = None,
                    concern_type: str | None = None,
                    pathway: str | None = None,
                    open_only: bool = False,
                    from_date: str | None = None,
                    to_date: str | None = None) -> list[Referral]:
    init_db()
    where: list[str] = []
    params: list[Any] = []
    if pupil_id:
        where.append("pr.pupil_id = ?")
        params.append(pupil_id.strip())
    if status:
        if status not in STATUSES:
            raise ValidationError(
                f"Status filter must be one of "
                f"{', '.join(STATUSES)}")
        where.append("pr.status = ?")
        params.append(status)
    if risk_level:
        if risk_level not in RISK_LEVELS:
            raise ValidationError(
                f"Risk level filter must be one of "
                f"{', '.join(RISK_LEVELS)}")
        where.append("pr.risk_level = ?")
        params.append(risk_level)
    if concern_type:
        if concern_type not in CONCERN_TYPES:
            raise ValidationError(
                f"Concern type filter must be one of "
                f"{', '.join(CONCERN_TYPES)}")
        where.append("pr.concern_type = ?")
        params.append(concern_type)
    if pathway:
        if pathway not in REFERRAL_PATHWAYS:
            raise ValidationError(
                f"Pathway filter must be one of "
                f"{', '.join(REFERRAL_PATHWAYS)}")
        where.append("pr.referral_pathway = ?")
        params.append(pathway)
    if open_only:
        where.append("pr.status NOT LIKE 'Closed%'")
    if from_date:
        if not _DATE_RE.match(from_date):
            raise ValidationError("From date must be YYYY-MM-DD")
        where.append("pr.raised_date >= ?")
        params.append(from_date)
    if to_date:
        if not _DATE_RE.match(to_date):
            raise ValidationError("To date must be YYYY-MM-DD")
        where.append("pr.raised_date <= ?")
        params.append(to_date)
    sql = ("""SELECT pr.*,
                     (p.first_name || ' ' || p.last_name) AS pupil_name,
                     p.year_group AS pupil_year
              FROM prevent_referrals pr
              LEFT JOIN pupils p ON p.pupil_id = pr.pupil_id""")
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY pr.raised_date DESC, pr.referral_id DESC"
    try:
        with _connect() as conn:
            return [_row(r) for r in
                    conn.execute(sql, tuple(params)).fetchall()]
    except sqlite3.Error:
        logger.exception("list_referrals failed")
        raise


def update(referral_id: int, data: dict[str, Any]) -> Referral:
    init_db()
    existing = get(referral_id)
    if existing is None:
        raise ValidationError(f"No Prevent referral #{referral_id}")
    merged = {k: data.get(k, getattr(existing, k))
              for k in ("pupil_id", "concern_type", "risk_level",
                         "raised_by", "raised_date", "dsl_informed",
                         "dsl_name", "dsl_informed_date",
                         "description", "indicators",
                         "online_activity", "referral_pathway",
                         "referral_date", "referral_ref",
                         "agencies_involved", "parents_informed",
                         "parents_informed_date",
                         "next_review_date", "status", "outcome",
                         "closed_date", "closure_notes", "notes")}
    # When status moves away from closed, clear closed_date if not supplied.
    if (not merged["status"].startswith("Closed")
            and data.get("closed_date") in (None, "")):
        merged["closed_date"] = None
    payload = _validate(merged)
    try:
        with _connect() as conn:
            conn.execute(
                """UPDATE prevent_referrals SET
                       pupil_id = ?, concern_type = ?,
                       risk_level = ?, raised_by = ?,
                       raised_date = ?, dsl_informed = ?,
                       dsl_name = ?, dsl_informed_date = ?,
                       description = ?, indicators = ?,
                       online_activity = ?,
                       referral_pathway = ?, referral_date = ?,
                       referral_ref = ?, agencies_involved = ?,
                       parents_informed = ?,
                       parents_informed_date = ?,
                       next_review_date = ?, status = ?,
                       outcome = ?, closed_date = ?,
                       closure_notes = ?, notes = ?,
                       updated_at = datetime('now')
                   WHERE referral_id = ?""",
                (payload["pupil_id"], payload["concern_type"],
                 payload["risk_level"], payload["raised_by"],
                 payload["raised_date"],
                 1 if payload["dsl_informed"] else 0,
                 payload["dsl_name"], payload["dsl_informed_date"],
                 payload["description"], payload["indicators"],
                 payload["online_activity"],
                 payload["referral_pathway"],
                 payload["referral_date"], payload["referral_ref"],
                 payload["agencies_involved"],
                 1 if payload["parents_informed"] else 0,
                 payload["parents_informed_date"],
                 payload["next_review_date"],
                 payload["status"], payload["outcome"],
                 payload["closed_date"], payload["closure_notes"],
                 payload["notes"], referral_id),
            )
            conn.commit()
    except sqlite3.Error:
        logger.exception(
            "Failed to update Prevent referral #%d", referral_id)
        raise
    rec = get(referral_id)
    assert rec is not None
    logger.info(
        "Updated Prevent referral #%d (status %s, risk %s)",
        rec.referral_id, rec.status, rec.risk_level)
    return rec


def set_status(referral_id: int, status: str,
                 outcome: str | None = None) -> Referral:
    payload: dict[str, Any] = {"status": status}
    if outcome is not None:
        payload["outcome"] = outcome
    return update(referral_id, payload)


def close_referral(referral_id: int,
                    *, outcome: str,
                    closure_notes: str | None = None,
                    status: str = "Closed — no further action"
                    ) -> Referral:
    if not status.startswith("Closed"):
        raise ValidationError(
            "close_referral requires a Closed status")
    return update(referral_id, {
        "status": status,
        "outcome": outcome,
        "closure_notes": closure_notes,
        "closed_date": _dt.date.today().isoformat(),
    })


def delete(referral_id: int) -> bool:
    init_db()
    existing = get(referral_id)
    if existing is None:
        return False
    try:
        with _connect() as conn:
            cur = conn.execute(
                "DELETE FROM prevent_referrals "
                "WHERE referral_id = ?", (referral_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception(
            "Failed to delete Prevent referral #%d", referral_id)
        raise
    if deleted:
        logger.info("Deleted Prevent referral #%d", referral_id)
    return deleted


def cohort_summary(*, from_date: str | None = None,
                    to_date: str | None = None) -> dict[str, Any]:
    rows = list_referrals(from_date=from_date, to_date=to_date)
    open_rows = [r for r in rows
                   if not r.status.startswith("Closed")]
    return {
        "total":           len(rows),
        "open":            len(open_rows),
        "high_risk":       sum(1 for r in rows
                                  if r.risk_level in ("High", "Imminent")),
        "channel":         sum(1 for r in rows
                                  if r.referral_pathway
                                       == "Channel referral (Prevent)"),
        "police":          sum(1 for r in rows
                                  if r.referral_pathway
                                       == "Police referral"),
        "by_status":       dict(Counter(r.status for r in rows)),
        "by_risk":         dict(Counter(r.risk_level for r in rows)),
        "by_concern":      dict(Counter(r.concern_type for r in rows)),
        "by_pathway":      dict(Counter(r.referral_pathway for r in rows)),
        "pupils":          len({r.pupil_id for r in rows}),
        "dsl_informed":    sum(1 for r in rows if r.dsl_informed),
        "parents_informed": sum(1 for r in rows
                                   if r.parents_informed),
    }
