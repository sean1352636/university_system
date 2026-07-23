"""SEF Builder data layer for Sixth Form System.

A SEF (Self-Evaluation Form) is built per cycle (e.g. '2025-2026').
Each cycle has one section per OFSTED-aligned area; each section
carries a 1-4 judgement, strengths, areas to develop, evidence and
improvement actions. Status flows Draft → In Review → Approved →
Published → Archived. There is at most one section per (cycle, area).
"""

from __future__ import annotations

import datetime as _dt
import logging
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator
from education_system.post_16.sixthform_system.core import paths as _paths

logger = logging.getLogger(__name__)

AREAS: tuple[str, ...] = (
    "Quality of Education",
    "Behaviour & Attitudes",
    "Personal Development",
    "Leadership & Management",
    "Sixth Form Provision",
    "Safeguarding",
    "Overall Effectiveness",
)
DEFAULT_AREA = "Quality of Education"

STATUSES: tuple[str, ...] = (
    "Draft",
    "In Review",
    "Approved",
    "Published",
    "Archived",
)
DEFAULT_STATUS = "Draft"

JUDGEMENTS: tuple[int, ...] = (1, 2, 3, 4)
_JUDGEMENT_LABELS = {
    1: "Outstanding",
    2: "Good",
    3: "Requires Improvement",
    4: "Inadequate",
}


def judgement_label(j: int | None) -> str:
    if j is None:
        return "—"
    return _JUDGEMENT_LABELS.get(j, "Unknown")


class ValidationError(Exception):
    pass


@dataclass
class SEFSection:
    section_id: int
    cycle: str
    area: str
    judgement: int | None
    status: str
    summary_statement: str | None
    strengths: str | None
    areas_to_develop: str | None
    evidence: str | None
    improvement_actions: str | None
    author: str | None
    reviewer: str | None
    approved_by: str | None
    approved_on: str | None
    last_updated: str
    created_on: str

    @property
    def is_open(self) -> bool:
        return self.status in ("Draft", "In Review")

    @property
    def is_published(self) -> bool:
        return self.status == "Published"

    @property
    def judgement_label(self) -> str:
        return judgement_label(self.judgement)


@dataclass
class SEFSummary:
    total: int = 0
    open_count: int = 0
    published: int = 0
    distinct_cycles: int = 0
    average_judgement: float | None = None
    by_status: dict[str, int] = field(default_factory=dict)
    by_area: dict[str, int] = field(default_factory=dict)
    by_judgement: dict[int, int] = field(default_factory=dict)


@dataclass
class CycleSummary:
    cycle: str
    total: int
    published: int
    average_judgement: float | None
    judgement_by_area: dict[str, int]


# ── DB ─────────────────────────────────────────────────────────────

@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    _paths.ensure_directories()
    conn = sqlite3.connect(_paths.SEF_BUILDER_DB)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sef_sections (
                section_id INTEGER PRIMARY KEY AUTOINCREMENT,
                cycle TEXT NOT NULL,
                area TEXT NOT NULL,
                judgement INTEGER,
                status TEXT NOT NULL,
                summary_statement TEXT,
                strengths TEXT,
                areas_to_develop TEXT,
                evidence TEXT,
                improvement_actions TEXT,
                author TEXT,
                reviewer TEXT,
                approved_by TEXT,
                approved_on TEXT,
                last_updated TEXT NOT NULL,
                created_on TEXT NOT NULL,
                UNIQUE(cycle, area)
            )
        """)


# ── Validation ─────────────────────────────────────────────────────

def _check_date(label: str, value: str | None) -> None:
    if value in (None, ""):
        return
    try:
        _dt.date.fromisoformat(value)
    except ValueError:
        raise ValidationError(f"{label} must be YYYY-MM-DD")


def _validate_payload(p: dict[str, Any],
                          *, existing_id: int | None = None) -> dict[str, Any]:
    out = dict(p)
    out["cycle"] = (out.get("cycle") or "").strip()
    if not out["cycle"]:
        raise ValidationError("Cycle is required (e.g. '2025-2026')")
    out["area"] = (out.get("area") or "").strip()
    if out["area"] not in AREAS:
        raise ValidationError(
            f"Area must be one of: {', '.join(AREAS)}")

    j = out.get("judgement")
    if j in (None, ""):
        out["judgement"] = None
    else:
        try:
            jv = int(j)
        except (TypeError, ValueError):
            raise ValidationError("Judgement must be 1-4 (1=Outstanding)")
        if jv not in JUDGEMENTS:
            raise ValidationError("Judgement must be 1-4 (1=Outstanding)")
        out["judgement"] = jv

    status = (out.get("status") or DEFAULT_STATUS).strip()
    if status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    out["status"] = status

    for k in ("summary_statement", "strengths", "areas_to_develop",
               "evidence", "improvement_actions",
               "author", "reviewer", "approved_by"):
        v = out.get(k)
        out[k] = (v.strip() if isinstance(v, str) else v) or None

    _check_date("Approved on", out.get("approved_on"))
    out["approved_on"] = (
        (out.get("approved_on") or "").strip() or None)

    # Uniqueness of (cycle, area)
    with _connect() as conn:
        row = conn.execute(
            "SELECT section_id FROM sef_sections "
            "WHERE cycle=? AND area=?",
            (out["cycle"], out["area"])).fetchone()
    if row and row["section_id"] != existing_id:
        raise ValidationError(
            f"A section for '{out['area']}' already exists "
            f"in cycle {out['cycle']}")
    return out


# ── CRUD ───────────────────────────────────────────────────────────

def _row(r: sqlite3.Row) -> SEFSection:
    return SEFSection(
        section_id=r["section_id"],
        cycle=r["cycle"],
        area=r["area"],
        judgement=r["judgement"],
        status=r["status"],
        summary_statement=r["summary_statement"],
        strengths=r["strengths"],
        areas_to_develop=r["areas_to_develop"],
        evidence=r["evidence"],
        improvement_actions=r["improvement_actions"],
        author=r["author"],
        reviewer=r["reviewer"],
        approved_by=r["approved_by"],
        approved_on=r["approved_on"],
        last_updated=r["last_updated"],
        created_on=r["created_on"],
    )


def create_section(payload: dict[str, Any]) -> SEFSection:
    init_db()
    p = _validate_payload(payload)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        cur = conn.execute("""
            INSERT INTO sef_sections (
              cycle, area, judgement, status,
              summary_statement, strengths, areas_to_develop,
              evidence, improvement_actions,
              author, reviewer, approved_by, approved_on,
              last_updated, created_on
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            p["cycle"], p["area"], p["judgement"], p["status"],
            p["summary_statement"], p["strengths"],
            p["areas_to_develop"], p["evidence"],
            p["improvement_actions"],
            p["author"], p["reviewer"],
            p["approved_by"], p["approved_on"],
            now, now,
        ))
        new_id = cur.lastrowid
    return get_section(new_id)


def update_section(section_id: int,
                       payload: dict[str, Any]) -> SEFSection:
    init_db()
    if get_section(section_id) is None:
        raise ValidationError(f"No SEF section with id {section_id}")
    p = _validate_payload(payload, existing_id=section_id)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        conn.execute("""
            UPDATE sef_sections SET
              cycle=?, area=?, judgement=?, status=?,
              summary_statement=?, strengths=?, areas_to_develop=?,
              evidence=?, improvement_actions=?,
              author=?, reviewer=?, approved_by=?, approved_on=?,
              last_updated=?
            WHERE section_id=?
        """, (
            p["cycle"], p["area"], p["judgement"], p["status"],
            p["summary_statement"], p["strengths"],
            p["areas_to_develop"], p["evidence"],
            p["improvement_actions"],
            p["author"], p["reviewer"],
            p["approved_by"], p["approved_on"],
            now, section_id,
        ))
    return get_section(section_id)


def delete_section(section_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM sef_sections WHERE section_id=?",
            (section_id,))
        return cur.rowcount > 0


def get_section(section_id: int) -> SEFSection | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM sef_sections WHERE section_id=?",
            (section_id,)).fetchone()
        return _row(r) if r else None


def list_sections(*,
                      cycle: str | None = None,
                      area: str | None = None,
                      status: str | None = None,
                      judgement: int | None = None,
                      author_like: str | None = None,
                      open_only: bool = False,
                      published_only: bool = False,
                      ) -> list[SEFSection]:
    init_db()
    sql = "SELECT * FROM sef_sections WHERE 1=1"
    params: list[Any] = []
    if cycle:
        sql += " AND cycle=?"
        params.append(cycle)
    if area:
        sql += " AND area=?"
        params.append(area)
    if status:
        sql += " AND status=?"
        params.append(status)
    if judgement is not None:
        sql += " AND judgement=?"
        params.append(judgement)
    if author_like:
        sql += " AND author LIKE ?"
        params.append(f"%{author_like}%")
    if open_only:
        sql += " AND status IN ('Draft','In Review')"
    if published_only:
        sql += " AND status='Published'"
    sql += " ORDER BY cycle DESC, area"
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row(r) for r in rows]


def list_cycles() -> list[str]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT DISTINCT cycle FROM sef_sections "
            "ORDER BY cycle DESC").fetchall()
    return [r["cycle"] for r in rows]


# ── Workflow ───────────────────────────────────────────────────────

def set_status(section_id: int, status: str) -> SEFSection:
    if status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    s = get_section(section_id)
    if s is None:
        raise ValidationError(f"No SEF section with id {section_id}")
    return update_section(section_id,
                              {**_to_dict(s), "status": status})


def submit_for_review(section_id: int, *,
                          reviewer: str | None = None) -> SEFSection:
    s = get_section(section_id)
    if s is None:
        raise ValidationError(f"No SEF section with id {section_id}")
    data = _to_dict(s)
    data["status"] = "In Review"
    if reviewer:
        data["reviewer"] = reviewer
    return update_section(section_id, data)


def approve(section_id: int, *, approved_by: str,
                approved_on: str | None = None) -> SEFSection:
    if not approved_by:
        raise ValidationError("Approved-by is required")
    s = get_section(section_id)
    if s is None:
        raise ValidationError(f"No SEF section with id {section_id}")
    data = _to_dict(s)
    data["status"] = "Approved"
    data["approved_by"] = approved_by
    data["approved_on"] = (approved_on
                                or _dt.date.today().isoformat())
    return update_section(section_id, data)


def publish(section_id: int) -> SEFSection:
    return set_status(section_id, "Published")


def archive(section_id: int) -> SEFSection:
    return set_status(section_id, "Archived")


def _to_dict(s: SEFSection) -> dict[str, Any]:
    return {
        "cycle": s.cycle,
        "area": s.area,
        "judgement": s.judgement,
        "status": s.status,
        "summary_statement": s.summary_statement,
        "strengths": s.strengths,
        "areas_to_develop": s.areas_to_develop,
        "evidence": s.evidence,
        "improvement_actions": s.improvement_actions,
        "author": s.author,
        "reviewer": s.reviewer,
        "approved_by": s.approved_by,
        "approved_on": s.approved_on,
    }


# ── Summaries ─────────────────────────────────────────────────────

def summary() -> SEFSummary:
    rows = list_sections()
    out = SEFSummary(total=len(rows))
    if not rows:
        return out
    j_total = 0
    j_count = 0
    cycles: set[str] = set()
    for s in rows:
        cycles.add(s.cycle)
        if s.is_open:
            out.open_count += 1
        if s.is_published:
            out.published += 1
        out.by_status[s.status] = out.by_status.get(s.status, 0) + 1
        out.by_area[s.area] = out.by_area.get(s.area, 0) + 1
        if s.judgement is not None:
            j_total += s.judgement
            j_count += 1
            out.by_judgement[s.judgement] = out.by_judgement.get(
                s.judgement, 0) + 1
    out.distinct_cycles = len(cycles)
    if j_count:
        out.average_judgement = round(j_total / j_count, 2)
    return out


def cycle_summary(cycle: str) -> CycleSummary:
    rows = list_sections(cycle=cycle)
    j_total = 0
    j_count = 0
    published = 0
    by_area: dict[str, int] = {}
    for s in rows:
        if s.is_published:
            published += 1
        if s.judgement is not None:
            j_total += s.judgement
            j_count += 1
            by_area[s.area] = s.judgement
    return CycleSummary(
        cycle=cycle,
        total=len(rows),
        published=published,
        average_judgement=(round(j_total / j_count, 2)
                              if j_count else None),
        judgement_by_area=by_area,
    )


__all__ = [
    "AREAS", "DEFAULT_AREA",
    "STATUSES", "DEFAULT_STATUS",
    "JUDGEMENTS", "judgement_label",
    "ValidationError",
    "SEFSection", "SEFSummary", "CycleSummary",
    "init_db",
    "create_section", "update_section", "delete_section",
    "get_section", "list_sections", "list_cycles",
    "set_status", "submit_for_review", "approve",
    "publish", "archive",
    "summary", "cycle_summary",
]
