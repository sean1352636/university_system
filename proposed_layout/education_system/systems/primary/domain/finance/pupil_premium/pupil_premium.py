"""Pupil-Premium data layer for the Primary School System.

Two tables:

* ``pupil_premium_records``  — one row per (pupil, academic_year)
                                tracking which eligibility category
                                a pupil falls under (Ever 6 FSM,
                                LAC / post-LAC, service child),
                                the funding rate, status, and notes.
* ``pp_interventions``       — interventions / spend lines paid for
                                out of pupil-premium funding for a
                                given pupil record. Tracks the amount
                                spent and the impact captured.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
import sqlite3
from collections import Counter
from dataclasses import dataclass
from typing import Any

from education_system.systems.primary.domain.learners.pupils.pupils import (
    ValidationError, YEAR_GROUPS, _connect as _pupils_connect,
)

logger = logging.getLogger(__name__)

CATEGORIES: tuple[str, ...] = (
    "Ever 6 FSM",
    "Free school meals",
    "LAC (Looked-after child)",
    "Post-LAC",
    "Service child",
    "Other")
DEFAULT_CATEGORY: str = "Ever 6 FSM"

PP_STATUSES: tuple[str, ...] = (
    "Eligible", "Provisional", "Withdrawn", "Reviewing")
DEFAULT_STATUS: str = "Eligible"

INTERVENTION_STATUSES: tuple[str, ...] = (
    "Planned", "Active", "Complete", "Cancelled")
DEFAULT_INT_STATUS: str = "Planned"

IMPACT_RATINGS: tuple[str, ...] = (
    "Not yet assessed", "Low", "Medium", "High", "Very high")

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_AY_RE = re.compile(r"^\d{4}/\d{2}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS pupil_premium_records (
    pp_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    pupil_id         TEXT NOT NULL,
    academic_year    TEXT NOT NULL,
    category         TEXT NOT NULL DEFAULT 'Ever 6 FSM',
    status           TEXT NOT NULL DEFAULT 'Eligible',
    funding_amount   REAL,
    start_date       TEXT NOT NULL DEFAULT (date('now')),
    end_date         TEXT,
    eligibility_source TEXT,
    keyworker        TEXT,
    notes            TEXT,
    created_at       TEXT DEFAULT (datetime('now')),
    updated_at       TEXT DEFAULT (datetime('now')),
    UNIQUE (pupil_id, academic_year)
);

CREATE TABLE IF NOT EXISTS pp_interventions (
    intervention_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    pp_id            INTEGER NOT NULL,
    title            TEXT NOT NULL,
    description      TEXT,
    spend            REAL NOT NULL DEFAULT 0,
    start_date       TEXT NOT NULL DEFAULT (date('now')),
    end_date         TEXT,
    status           TEXT NOT NULL DEFAULT 'Planned',
    impact_rating    TEXT NOT NULL DEFAULT 'Not yet assessed',
    impact_notes     TEXT,
    notes            TEXT,
    created_at       TEXT DEFAULT (datetime('now')),
    updated_at       TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pp_id) REFERENCES pupil_premium_records(pp_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_pp_pupil
    ON pupil_premium_records(pupil_id);
CREATE INDEX IF NOT EXISTS idx_pp_ay
    ON pupil_premium_records(academic_year);
CREATE INDEX IF NOT EXISTS idx_ppint_pp
    ON pp_interventions(pp_id);
"""


@dataclass
class PupilPremiumRecord:
    pp_id: int
    pupil_id: str
    academic_year: str
    category: str
    status: str
    funding_amount: float | None
    start_date: str
    end_date: str | None
    eligibility_source: str | None
    keyworker: str | None
    notes: str | None
    pupil_name: str | None = None
    pupil_year: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


@dataclass
class PPIntervention:
    intervention_id: int
    pp_id: int
    title: str
    description: str | None
    spend: float
    start_date: str
    end_date: str | None
    status: str
    impact_rating: str
    impact_notes: str | None
    notes: str | None
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
        logger.exception("Failed to initialise pupil_premium tables")
        raise
    logger.info("Secondary pupil_premium tables ready")
    _DB_READY = True


def _row_record(r: sqlite3.Row) -> PupilPremiumRecord:
    keys = r.keys()
    return PupilPremiumRecord(
        pp_id=r["pp_id"], pupil_id=r["pupil_id"],
        academic_year=r["academic_year"], category=r["category"],
        status=r["status"], funding_amount=r["funding_amount"],
        start_date=r["start_date"], end_date=r["end_date"],
        eligibility_source=r["eligibility_source"],
        keyworker=r["keyworker"], notes=r["notes"],
        pupil_name=r["pupil_name"] if "pupil_name" in keys else None,
        pupil_year=r["pupil_year"] if "pupil_year" in keys else None,
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


def _row_intervention(r: sqlite3.Row) -> PPIntervention:
    return PPIntervention(
        intervention_id=r["intervention_id"], pp_id=r["pp_id"],
        title=r["title"], description=r["description"],
        spend=r["spend"], start_date=r["start_date"],
        end_date=r["end_date"], status=r["status"],
        impact_rating=r["impact_rating"],
        impact_notes=r["impact_notes"], notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
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
    from education_system.systems.primary.domain.learners.pupils import (
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

    category = (data.get("category") or DEFAULT_CATEGORY).strip()
    if category not in CATEGORIES:
        raise ValidationError(
            f"Category must be one of {', '.join(CATEGORIES)}")
    out["category"] = category

    status = (data.get("status") or DEFAULT_STATUS).strip()
    if status not in PP_STATUSES:
        raise ValidationError(
            f"Status must be one of {', '.join(PP_STATUSES)}")
    out["status"] = status

    amt = data.get("funding_amount")
    if amt in (None, "") or (isinstance(amt, str) and not amt.strip()):
        out["funding_amount"] = None
    else:
        try:
            v = float(amt)
        except (TypeError, ValueError):
            raise ValidationError(
                "Funding amount must be a number") from None
        if v < 0 or v > 100000:
            raise ValidationError(
                "Funding amount must be between 0 and 100000")
        out["funding_amount"] = v

    out["start_date"] = _validate_date(data.get("start_date"),
                                         "Start date")
    out["end_date"]   = _validate_date(data.get("end_date"),
                                         "End date", required=False)
    if out["end_date"] and out["end_date"] < out["start_date"]:
        raise ValidationError("End date cannot be before start date")

    out["eligibility_source"] = (
        data.get("eligibility_source") or "").strip() or None
    out["keyworker"] = (data.get("keyworker") or "").strip() or None
    out["notes"]     = (data.get("notes") or "").strip() or None
    return out


def _validate_intervention(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    pp_raw = data.get("pp_id")
    if pp_raw in (None, ""):
        raise ValidationError("PP record ID is required")
    try:
        out["pp_id"] = int(pp_raw)
    except (TypeError, ValueError):
        raise ValidationError("PP record ID must be a number") from None

    title = (data.get("title") or "").strip()
    if not title:
        raise ValidationError("Title is required")
    if len(title) > 120:
        raise ValidationError("Title must be 120 chars or fewer")
    out["title"] = title

    out["description"] = (data.get("description") or "").strip() or None

    spend = data.get("spend")
    if spend in (None, "") or (isinstance(spend, str)
                                 and not spend.strip()):
        out["spend"] = 0.0
    else:
        try:
            v = float(spend)
        except (TypeError, ValueError):
            raise ValidationError("Spend must be a number") from None
        if v < 0 or v > 100000:
            raise ValidationError(
                "Spend must be between 0 and 100000")
        out["spend"] = v

    out["start_date"] = _validate_date(data.get("start_date"),
                                         "Start date")
    out["end_date"]   = _validate_date(data.get("end_date"),
                                         "End date", required=False)
    if out["end_date"] and out["end_date"] < out["start_date"]:
        raise ValidationError("End date cannot be before start date")

    status = (data.get("status") or DEFAULT_INT_STATUS).strip()
    if status not in INTERVENTION_STATUSES:
        raise ValidationError(
            f"Status must be one of "
            f"{', '.join(INTERVENTION_STATUSES)}")
    out["status"] = status

    impact = (data.get("impact_rating") or "Not yet assessed").strip()
    if impact not in IMPACT_RATINGS:
        raise ValidationError(
            f"Impact rating must be one of "
            f"{', '.join(IMPACT_RATINGS)}")
    out["impact_rating"] = impact

    out["impact_notes"] = (data.get("impact_notes") or "").strip() or None
    out["notes"]        = (data.get("notes") or "").strip() or None
    if status == "Complete" and impact == "Not yet assessed":
        raise ValidationError(
            "Impact rating must be set when status is Complete")
    return out


# ── Record CRUD ─────────────────────────────────────────────────

def upsert(data: dict[str, Any]) -> PupilPremiumRecord:
    init_db()
    payload = _validate_record(data)
    try:
        with _connect() as conn:
            row = conn.execute(
                "SELECT pp_id FROM pupil_premium_records "
                "WHERE pupil_id = ? AND academic_year = ?",
                (payload["pupil_id"], payload["academic_year"]),
            ).fetchone()
            cols = ("category", "status", "funding_amount",
                    "start_date", "end_date",
                    "eligibility_source", "keyworker", "notes")
            if row:
                conn.execute(
                    "UPDATE pupil_premium_records SET "
                    + ", ".join(f"{c} = ?" for c in cols)
                    + ", updated_at = datetime('now') "
                    "WHERE pp_id = ?",
                    (*(payload[c] for c in cols), row["pp_id"]),
                )
                pid = row["pp_id"]
                action = "updated"
            else:
                cur = conn.execute(
                    "INSERT INTO pupil_premium_records "
                    "(pupil_id, academic_year, " + ", ".join(cols)
                    + ") VALUES ("
                    + ", ".join(["?"] * (2 + len(cols))) + ")",
                    (payload["pupil_id"], payload["academic_year"],
                     *(payload[c] for c in cols)),
                )
                pid = cur.lastrowid
                action = "inserted"
            conn.commit()
    except sqlite3.Error:
        logger.exception(
            "Failed to upsert PP record for pupil %s year %s",
            payload["pupil_id"], payload["academic_year"])
        raise
    logger.info(
        "PP record %s: pupil=%s year=%s category=%s status=%s funding=%s",
        action, payload["pupil_id"], payload["academic_year"],
        payload["category"], payload["status"],
        payload["funding_amount"])
    rec = get(pid)
    assert rec is not None
    return rec


def get(pp_id: int) -> PupilPremiumRecord | None:
    init_db()
    try:
        with _connect() as conn:
            r = conn.execute(
                """SELECT pp.*,
                          (p.first_name || ' ' || p.last_name) AS pupil_name,
                          p.year_group AS pupil_year
                   FROM pupil_premium_records pp
                   LEFT JOIN pupils p ON p.pupil_id = pp.pupil_id
                   WHERE pp.pp_id = ?""",
                (pp_id,),
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get(%s) failed", pp_id)
        raise
    return _row_record(r) if r else None


def get_for(pupil_id: str,
            academic_year: str) -> PupilPremiumRecord | None:
    init_db()
    try:
        with _connect() as conn:
            r = conn.execute(
                """SELECT pp.*,
                          (p.first_name || ' ' || p.last_name) AS pupil_name,
                          p.year_group AS pupil_year
                   FROM pupil_premium_records pp
                   LEFT JOIN pupils p ON p.pupil_id = pp.pupil_id
                   WHERE pp.pupil_id = ? AND pp.academic_year = ?""",
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
                 category: str | None = None,
                 status: str | None = None,
                 pupil_id: str | None = None
                 ) -> list[PupilPremiumRecord]:
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
        where.append("pp.academic_year = ?")
        params.append(academic_year.strip())
    if category:
        if category not in CATEGORIES:
            raise ValidationError(
                f"Category filter must be one of "
                f"{', '.join(CATEGORIES)}")
        where.append("pp.category = ?")
        params.append(category)
    if status:
        if status not in PP_STATUSES:
            raise ValidationError(
                f"Status filter must be one of "
                f"{', '.join(PP_STATUSES)}")
        where.append("pp.status = ?")
        params.append(status)
    if pupil_id:
        where.append("pp.pupil_id = ?")
        params.append(pupil_id.strip())
    sql = ("""SELECT pp.*,
                     (p.first_name || ' ' || p.last_name) AS pupil_name,
                     p.year_group AS pupil_year
              FROM pupil_premium_records pp
              LEFT JOIN pupils p ON p.pupil_id = pp.pupil_id""")
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += (" ORDER BY pp.academic_year DESC, p.year_group, "
            "p.last_name, p.first_name")
    try:
        with _connect() as conn:
            return [_row_record(r)
                    for r in conn.execute(sql, tuple(params)).fetchall()]
    except sqlite3.Error:
        logger.exception("list_records failed")
        raise


def delete(pp_id: int) -> bool:
    init_db()
    existing = get(pp_id)
    if existing is None:
        return False
    try:
        with _connect() as conn:
            conn.execute("PRAGMA foreign_keys=ON")
            cur = conn.execute(
                "DELETE FROM pupil_premium_records WHERE pp_id = ?",
                (pp_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Failed to delete PP record #%d", pp_id)
        raise
    if deleted:
        logger.info("Deleted PP record #%d %s/%s "
                    "(cascade: interventions)",
                    pp_id, existing.pupil_id, existing.academic_year)
    return deleted


# ── Interventions ───────────────────────────────────────────────

def add_intervention(data: dict[str, Any]) -> PPIntervention:
    init_db()
    payload = _validate_intervention(data)
    if get(payload["pp_id"]) is None:
        raise ValidationError(f"No PP record #{payload['pp_id']}")
    try:
        with _connect() as conn:
            cur = conn.execute(
                """INSERT INTO pp_interventions
                       (pp_id, title, description, spend,
                        start_date, end_date, status,
                        impact_rating, impact_notes, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (payload["pp_id"], payload["title"],
                 payload["description"], payload["spend"],
                 payload["start_date"], payload["end_date"],
                 payload["status"], payload["impact_rating"],
                 payload["impact_notes"], payload["notes"]),
            )
            conn.commit()
            new_id = cur.lastrowid
    except sqlite3.Error:
        logger.exception(
            "Failed to add intervention to PP record %d",
            payload["pp_id"])
        raise
    logger.info(
        "Added PP intervention #%d to record #%d "
        "(spend=£%.2f, status=%s)",
        new_id, payload["pp_id"], payload["spend"],
        payload["status"])
    rec = get_intervention(new_id)
    assert rec is not None
    return rec


def get_intervention(intervention_id: int) -> PPIntervention | None:
    init_db()
    try:
        with _connect() as conn:
            r = conn.execute(
                "SELECT * FROM pp_interventions "
                "WHERE intervention_id = ?",
                (intervention_id,),
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get_intervention(%s) failed", intervention_id)
        raise
    return _row_intervention(r) if r else None


def list_interventions(pp_id: int) -> list[PPIntervention]:
    init_db()
    try:
        with _connect() as conn:
            return [_row_intervention(r) for r in conn.execute(
                "SELECT * FROM pp_interventions WHERE pp_id = ? "
                "ORDER BY start_date DESC, intervention_id DESC",
                (pp_id,),
            ).fetchall()]
    except sqlite3.Error:
        logger.exception("list_interventions(%s) failed", pp_id)
        raise


def update_intervention(intervention_id: int,
                         data: dict[str, Any]) -> PPIntervention:
    init_db()
    existing = get_intervention(intervention_id)
    if existing is None:
        raise ValidationError(
            f"No PP intervention #{intervention_id}")
    merged = {
        "pp_id":         existing.pp_id,
        "title":         data.get("title", existing.title),
        "description":   data.get("description",
                                    existing.description),
        "spend":         data.get("spend", existing.spend),
        "start_date":    data.get("start_date", existing.start_date),
        "end_date":      data.get("end_date", existing.end_date),
        "status":        data.get("status", existing.status),
        "impact_rating": data.get("impact_rating",
                                    existing.impact_rating),
        "impact_notes":  data.get("impact_notes",
                                    existing.impact_notes),
        "notes":         data.get("notes", existing.notes),
    }
    payload = _validate_intervention(merged)
    try:
        with _connect() as conn:
            conn.execute(
                """UPDATE pp_interventions SET
                       title = ?, description = ?, spend = ?,
                       start_date = ?, end_date = ?, status = ?,
                       impact_rating = ?, impact_notes = ?,
                       notes = ?, updated_at = datetime('now')
                   WHERE intervention_id = ?""",
                (payload["title"], payload["description"],
                 payload["spend"], payload["start_date"],
                 payload["end_date"], payload["status"],
                 payload["impact_rating"], payload["impact_notes"],
                 payload["notes"], intervention_id),
            )
            conn.commit()
    except sqlite3.Error:
        logger.exception(
            "Failed to update PP intervention #%d", intervention_id)
        raise
    rec = get_intervention(intervention_id)
    assert rec is not None
    logger.info("Updated PP intervention #%d (status %s, impact %s)",
                rec.intervention_id, rec.status, rec.impact_rating)
    return rec


def delete_intervention(intervention_id: int) -> bool:
    init_db()
    try:
        with _connect() as conn:
            cur = conn.execute(
                "DELETE FROM pp_interventions "
                "WHERE intervention_id = ?",
                (intervention_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception(
            "Failed to delete PP intervention #%d", intervention_id)
        raise
    if deleted:
        logger.info("Deleted PP intervention #%d", intervention_id)
    return deleted


def record_summary(pp_id: int) -> dict[str, Any]:
    init_db()
    rec = get(pp_id)
    if rec is None:
        raise ValidationError(f"No PP record #{pp_id}")
    ints = list_interventions(pp_id)
    total_spend = sum(i.spend for i in ints)
    return {
        "record":       rec,
        "interventions": ints,
        "total_spend":  round(total_spend, 2),
        "remaining":    (round((rec.funding_amount or 0)
                                  - total_spend, 2)
                            if rec.funding_amount is not None else None),
        "by_status":    dict(Counter(i.status for i in ints)),
        "by_impact":    dict(Counter(i.impact_rating for i in ints)),
    }


def cohort_summary(*, year_group: str | None = None,
                   academic_year: str | None = None) -> dict[str, Any]:
    init_db()
    rows = list_records(year_group=year_group,
                          academic_year=academic_year)
    total_funding = sum((r.funding_amount or 0) for r in rows)
    # Aggregate intervention totals
    int_total = 0.0
    int_count = 0
    try:
        with _connect() as conn:
            ids = [r.pp_id for r in rows]
            if ids:
                placeholders = ",".join("?" * len(ids))
                row = conn.execute(
                    f"SELECT COUNT(*), COALESCE(SUM(spend), 0) "
                    f"FROM pp_interventions WHERE pp_id IN "
                    f"({placeholders})",
                    tuple(ids),
                ).fetchone()
                int_count, int_total = row[0], float(row[1])
    except sqlite3.Error:
        logger.exception("cohort_summary intervention aggregation failed")
        raise
    return {
        "total":          len(rows),
        "by_category":    dict(Counter(r.category for r in rows)),
        "by_status":      dict(Counter(r.status for r in rows)),
        "total_funding":  round(total_funding, 2),
        "interventions":  int_count,
        "total_spend":    round(int_total, 2),
        "remaining":      round(total_funding - int_total, 2),
    }
