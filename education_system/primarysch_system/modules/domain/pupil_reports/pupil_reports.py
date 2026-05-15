"""Pupil reports data layer.

One row per (pupil, academic_year, term). Reports start in ``draft``
status; ``publish`` flips them to ``published`` and stamps a
``published_on`` date. Published reports can be reverted to draft if
they need amending.
"""

from __future__ import annotations

import logging
import re
import sqlite3
from dataclasses import dataclass
from typing import Any

from education_system.primarysch_system.modules.domain.pupils import (
    pupils as pupils_data,
)
from education_system.primarysch_system.modules.domain.pupils.pupils import (
    Pupil, ValidationError, YEAR_GROUPS,
    _connect as _pupils_connect, _DOB_RE,
)

logger = logging.getLogger(__name__)

TERMS: tuple[str, ...] = ("Autumn", "Spring", "Summer")
STATUSES: tuple[str, ...] = ("draft", "published")

_ACADEMIC_YEAR_RE = re.compile(r"^\d{4}(-\d{2}|-\d{4})?$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS pupil_reports (
    report_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    pupil_id         TEXT NOT NULL,
    academic_year    TEXT NOT NULL,
    term             TEXT NOT NULL,
    headline         TEXT,
    summary          TEXT,
    strengths        TEXT,
    next_steps       TEXT,
    attendance_pct   REAL,
    behaviour        TEXT,
    status           TEXT NOT NULL DEFAULT 'draft',
    authored_by      TEXT,
    published_on     TEXT,
    notes            TEXT,
    created_at       TEXT DEFAULT (datetime('now')),
    updated_at       TEXT DEFAULT (datetime('now')),
    UNIQUE(pupil_id, academic_year, term),
    FOREIGN KEY(pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_reports_pupil    ON pupil_reports(pupil_id);
CREATE INDEX IF NOT EXISTS idx_reports_year     ON pupil_reports(academic_year);
CREATE INDEX IF NOT EXISTS idx_reports_status   ON pupil_reports(status);
"""


@dataclass
class Report:
    report_id: int
    pupil_id: str
    academic_year: str
    term: str
    headline: str | None
    summary: str | None
    strengths: str | None
    next_steps: str | None
    attendance_pct: float | None
    behaviour: str | None
    status: str
    authored_by: str | None
    published_on: str | None
    notes: str | None
    created_at: str | None = None
    updated_at: str | None = None

    @property
    def is_draft(self) -> bool:
        return self.status == "draft"

    @property
    def is_published(self) -> bool:
        return self.status == "published"


_DB_READY = False


def _connect() -> sqlite3.Connection:
    return _pupils_connect()


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    pupils_data.init_db()
    try:
        with _connect() as conn:
            conn.executescript(_SCHEMA)
    except sqlite3.Error:
        logger.exception("Failed to initialise pupil_reports table")
        raise
    logger.info("Primary pupil_reports table ready")
    _DB_READY = True


def _row(r: sqlite3.Row) -> Report:
    return Report(
        report_id=r["report_id"],
        pupil_id=r["pupil_id"],
        academic_year=r["academic_year"],
        term=r["term"],
        headline=r["headline"],
        summary=r["summary"],
        strengths=r["strengths"],
        next_steps=r["next_steps"],
        attendance_pct=r["attendance_pct"],
        behaviour=r["behaviour"],
        status=r["status"],
        authored_by=r["authored_by"],
        published_on=r["published_on"],
        notes=r["notes"],
        created_at=r["created_at"],
        updated_at=r["updated_at"],
    )


def _validate(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    pid = (data.get("pupil_id") or "").strip()
    if not pid:
        raise ValidationError("Pupil ID is required")
    out["pupil_id"] = pid
    ay = (data.get("academic_year") or "").strip()
    if not ay:
        raise ValidationError("Academic year is required (e.g. 2025-26)")
    if not _ACADEMIC_YEAR_RE.match(ay):
        raise ValidationError("Academic year must look like 2025 or 2025-26")
    out["academic_year"] = ay
    term = (data.get("term") or "").strip().title()
    if not term:
        raise ValidationError("Term is required")
    if term not in TERMS:
        raise ValidationError(f"Term must be one of {', '.join(TERMS)}")
    out["term"] = term
    out["headline"]   = (data.get("headline") or "").strip() or None
    out["summary"]    = (data.get("summary") or "").strip() or None
    out["strengths"]  = (data.get("strengths") or "").strip() or None
    out["next_steps"] = (data.get("next_steps") or "").strip() or None
    att_raw = data.get("attendance_pct")
    if att_raw in (None, ""):
        out["attendance_pct"] = None
    else:
        try:
            att = float(att_raw)
        except (TypeError, ValueError) as e:
            raise ValidationError("Attendance % must be a number") from e
        if not (0.0 <= att <= 100.0):
            raise ValidationError("Attendance % must be between 0 and 100")
        out["attendance_pct"] = att
    out["behaviour"]   = (data.get("behaviour") or "").strip() or None
    status = (data.get("status") or "draft").strip().lower() or "draft"
    if status not in STATUSES:
        raise ValidationError(
            f"Status must be one of {', '.join(STATUSES)}")
    out["status"] = status
    out["authored_by"] = (data.get("authored_by") or "").strip() or None
    pub_on = (data.get("published_on") or "").strip()
    if pub_on and not _DOB_RE.match(pub_on):
        raise ValidationError("Published-on date must be YYYY-MM-DD")
    out["published_on"] = pub_on or None
    out["notes"] = (data.get("notes") or "").strip() or None
    return out


def create(data: dict[str, Any]) -> Report:
    init_db()
    payload = _validate(data)
    if pupils_data.get_pupil(payload["pupil_id"]) is None:
        raise ValidationError(f"No pupil with id {payload['pupil_id']}")
    try:
        with _connect() as conn:
            dup = conn.execute(
                "SELECT report_id FROM pupil_reports "
                "WHERE pupil_id = ? AND academic_year = ? AND term = ?",
                (payload["pupil_id"], payload["academic_year"],
                 payload["term"]),
            ).fetchone()
            if dup:
                raise ValidationError(
                    f"A report for pupil {payload['pupil_id']} in "
                    f"{payload['academic_year']} {payload['term']} "
                    f"already exists (#{dup['report_id']})")
            cur = conn.execute(
                """INSERT INTO pupil_reports
                       (pupil_id, academic_year, term, headline, summary,
                        strengths, next_steps, attendance_pct, behaviour,
                        status, authored_by, published_on, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (payload["pupil_id"], payload["academic_year"],
                 payload["term"], payload["headline"], payload["summary"],
                 payload["strengths"], payload["next_steps"],
                 payload["attendance_pct"], payload["behaviour"],
                 payload["status"], payload["authored_by"],
                 payload["published_on"], payload["notes"]),
            )
            conn.commit()
            new_id = cur.lastrowid
    except sqlite3.Error:
        logger.exception("Failed to create pupil report")
        raise
    rec = get(new_id)
    assert rec is not None
    logger.info("Created report #%d (pupil %s, %s %s, %s)",
                rec.report_id, rec.pupil_id, rec.academic_year,
                rec.term, rec.status)
    return rec


def get(report_id: int) -> Report | None:
    init_db()
    try:
        with _connect() as conn:
            r = conn.execute(
                "SELECT * FROM pupil_reports WHERE report_id = ?",
                (report_id,),
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get report(%s) failed", report_id)
        raise
    return _row(r) if r else None


def update(report_id: int, data: dict[str, Any]) -> Report:
    init_db()
    existing = get(report_id)
    if existing is None:
        raise ValidationError(f"No report #{report_id}")
    if existing.is_published:
        raise ValidationError(
            "Report is published — revert to draft before editing")
    merged = {
        "pupil_id":       data.get("pupil_id", existing.pupil_id),
        "academic_year":  data.get("academic_year", existing.academic_year),
        "term":           data.get("term", existing.term),
        "headline":       data.get("headline", existing.headline),
        "summary":        data.get("summary", existing.summary),
        "strengths":      data.get("strengths", existing.strengths),
        "next_steps":     data.get("next_steps", existing.next_steps),
        "attendance_pct": data.get("attendance_pct", existing.attendance_pct),
        "behaviour":      data.get("behaviour", existing.behaviour),
        "status":         data.get("status", existing.status),
        "authored_by":    data.get("authored_by", existing.authored_by),
        "published_on":   data.get("published_on", existing.published_on),
        "notes":          data.get("notes", existing.notes),
    }
    payload = _validate(merged)
    if pupils_data.get_pupil(payload["pupil_id"]) is None:
        raise ValidationError(f"No pupil with id {payload['pupil_id']}")
    try:
        with _connect() as conn:
            dup = conn.execute(
                "SELECT report_id FROM pupil_reports "
                "WHERE pupil_id = ? AND academic_year = ? AND term = ? "
                "AND report_id <> ?",
                (payload["pupil_id"], payload["academic_year"],
                 payload["term"], report_id),
            ).fetchone()
            if dup:
                raise ValidationError(
                    f"Another report for that pupil / year / term "
                    f"already exists (#{dup['report_id']})")
            conn.execute(
                """UPDATE pupil_reports SET
                       pupil_id = ?, academic_year = ?, term = ?,
                       headline = ?, summary = ?, strengths = ?,
                       next_steps = ?, attendance_pct = ?, behaviour = ?,
                       status = ?, authored_by = ?, published_on = ?,
                       notes = ?, updated_at = datetime('now')
                   WHERE report_id = ?""",
                (payload["pupil_id"], payload["academic_year"],
                 payload["term"], payload["headline"], payload["summary"],
                 payload["strengths"], payload["next_steps"],
                 payload["attendance_pct"], payload["behaviour"],
                 payload["status"], payload["authored_by"],
                 payload["published_on"], payload["notes"], report_id),
            )
            conn.commit()
    except sqlite3.Error:
        logger.exception("Failed to update report #%d", report_id)
        raise
    rec = get(report_id)
    assert rec is not None
    logger.info("Updated report #%d", report_id)
    return rec


def publish(report_id: int, *, published_on: str | None = None) -> Report:
    init_db()
    existing = get(report_id)
    if existing is None:
        raise ValidationError(f"No report #{report_id}")
    if existing.is_published:
        return existing
    if published_on:
        published_on = published_on.strip()
        if not _DOB_RE.match(published_on):
            raise ValidationError("Published-on date must be YYYY-MM-DD")
    try:
        with _connect() as conn:
            pub_date = published_on or conn.execute(
                "SELECT date('now')").fetchone()[0]
            conn.execute(
                "UPDATE pupil_reports SET status = 'published', "
                "published_on = ?, updated_at = datetime('now') "
                "WHERE report_id = ?",
                (pub_date, report_id),
            )
            conn.commit()
    except sqlite3.Error:
        logger.exception("Failed to publish report #%d", report_id)
        raise
    rec = get(report_id)
    assert rec is not None
    logger.info("Published report #%d on %s", report_id, rec.published_on)
    return rec


def revert_to_draft(report_id: int) -> Report:
    init_db()
    existing = get(report_id)
    if existing is None:
        raise ValidationError(f"No report #{report_id}")
    if existing.is_draft:
        return existing
    try:
        with _connect() as conn:
            conn.execute(
                "UPDATE pupil_reports SET status = 'draft', "
                "published_on = NULL, updated_at = datetime('now') "
                "WHERE report_id = ?",
                (report_id,),
            )
            conn.commit()
    except sqlite3.Error:
        logger.exception("Failed to revert report #%d", report_id)
        raise
    rec = get(report_id)
    assert rec is not None
    logger.info("Reverted report #%d to draft", report_id)
    return rec


def delete(report_id: int) -> bool:
    init_db()
    try:
        with _connect() as conn:
            cur = conn.execute(
                "DELETE FROM pupil_reports WHERE report_id = ?",
                (report_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Failed to delete report #%d", report_id)
        raise
    if deleted:
        logger.info("Deleted report #%d", report_id)
    return deleted


def list_reports(
    *, academic_year: str | None = None,
    term: str | None = None,
    status: str | None = None,
    pupil_id: str | None = None,
    year_group: str | None = None,
) -> list[tuple[Report, Pupil | None]]:
    init_db()
    if term is not None and term not in TERMS:
        raise ValidationError(f"Term filter must be one of {', '.join(TERMS)}")
    if status is not None and status not in STATUSES:
        raise ValidationError(
            f"Status filter must be one of {', '.join(STATUSES)}")
    if year_group is not None and year_group not in YEAR_GROUPS:
        raise ValidationError(
            f"Year filter must be one of {', '.join(YEAR_GROUPS)}")
    where: list[str] = []
    params: list[Any] = []
    if academic_year:
        where.append("academic_year = ?")
        params.append(academic_year.strip())
    if term:
        where.append("term = ?")
        params.append(term)
    if status:
        where.append("status = ?")
        params.append(status)
    if pupil_id:
        where.append("pupil_id = ?")
        params.append(pupil_id.strip())
    sql = "SELECT * FROM pupil_reports"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY academic_year DESC, term, pupil_id"
    try:
        with _connect() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
    except sqlite3.Error:
        logger.exception("list_reports failed")
        raise
    out: list[tuple[Report, Pupil | None]] = []
    for r in rows:
        rec = _row(r)
        p = pupils_data.get_pupil(rec.pupil_id)
        if year_group and (p is None or p.year_group != year_group):
            continue
        out.append((rec, p))
    return out


def list_for_pupil(pupil_id: str) -> list[Report]:
    init_db()
    if pupils_data.get_pupil(pupil_id) is None:
        raise ValidationError(f"No pupil with id {pupil_id}")
    try:
        with _connect() as conn:
            rows = conn.execute(
                "SELECT * FROM pupil_reports WHERE pupil_id = ? "
                "ORDER BY academic_year DESC, term",
                (pupil_id,),
            ).fetchall()
    except sqlite3.Error:
        logger.exception("list_for_pupil(%s) failed", pupil_id)
        raise
    return [_row(r) for r in rows]


def summary(
    *, academic_year: str | None = None,
    term: str | None = None,
) -> dict[str, Any]:
    init_db()
    rows = list_reports(academic_year=academic_year, term=term)
    total = len(rows)
    draft = sum(1 for r, _ in rows if r.is_draft)
    published = total - draft
    att_values = [r.attendance_pct for r, _ in rows
                  if r.attendance_pct is not None]
    return {
        "total": total,
        "draft": draft,
        "published": published,
        "published_pct": (published / total * 100.0) if total else 0.0,
        "average_attendance": (sum(att_values) / len(att_values))
                              if att_values else None,
        "attendance_count": len(att_values),
    }


def known_years() -> list[str]:
    init_db()
    try:
        with _connect() as conn:
            rows = conn.execute(
                "SELECT DISTINCT academic_year FROM pupil_reports "
                "ORDER BY academic_year DESC"
            ).fetchall()
    except sqlite3.Error:
        logger.exception("known_years failed")
        raise
    return [r["academic_year"] for r in rows]
