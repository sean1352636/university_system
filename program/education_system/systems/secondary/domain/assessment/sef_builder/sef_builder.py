"""Self-Evaluation Form (SEF) data layer for the Secondary School System.

Two tables:

* ``sef_documents`` — one row per SEF version (academic year + version
                      tag). Has overall judgement, status (Draft /
                      Submitted / Approved / Archived), author /
                      approved_by, and notes.
* ``sef_sections``  — one row per Ofsted-style section attached to a
                      SEF document. Sections carry their own
                      judgement, strengths, areas_for_development,
                      evidence, and action_plan. Unique on
                      (sef_id, section_code).

A fresh document is seeded with the canonical Ofsted section list when
``init_sections()`` is called.
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

# Ofsted-style sections used as defaults when seeding a SEF.
DEFAULT_SECTIONS: tuple[tuple[str, str], ...] = (
    ("QUAL_ED",  "Quality of education"),
    ("BEH_ATT",  "Behaviour and attitudes"),
    ("PER_DEV",  "Personal development"),
    ("LEAD_MGMT", "Leadership and management"),
    ("SAFEGUARD", "Safeguarding"),
    ("CURRIC",   "Curriculum"),
    ("SEND",     "SEND / inclusion"),
    ("EQUAL",    "Equality, diversity and inclusion"),
)

JUDGEMENTS: tuple[str, ...] = (
    "Outstanding", "Good", "Requires improvement",
    "Inadequate", "Not yet evaluated")
DEFAULT_JUDGEMENT: str = "Not yet evaluated"

SEF_STATUSES: tuple[str, ...] = (
    "Draft", "Submitted", "Approved", "Archived")
DEFAULT_STATUS: str = "Draft"

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_AY_RE = re.compile(r"^\d{4}/\d{2}$")
_VERSION_RE = re.compile(r"^[A-Za-z0-9.\- ]{1,16}$")
_CODE_RE = re.compile(r"^[A-Z0-9_]{2,16}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sef_documents (
    sef_id              INTEGER PRIMARY KEY AUTOINCREMENT,
    academic_year       TEXT NOT NULL,
    version             TEXT NOT NULL DEFAULT 'v1',
    title               TEXT,
    status              TEXT NOT NULL DEFAULT 'Draft',
    headline_judgement  TEXT NOT NULL DEFAULT 'Not yet evaluated',
    author              TEXT,
    approved_by         TEXT,
    approved_date       TEXT,
    notes               TEXT,
    created_at          TEXT DEFAULT (datetime('now')),
    updated_at          TEXT DEFAULT (datetime('now')),
    UNIQUE (academic_year, version)
);

CREATE TABLE IF NOT EXISTS sef_sections (
    section_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    sef_id             INTEGER NOT NULL,
    section_code       TEXT NOT NULL,
    section_title      TEXT NOT NULL,
    judgement          TEXT NOT NULL DEFAULT 'Not yet evaluated',
    strengths          TEXT,
    areas_for_development TEXT,
    evidence           TEXT,
    action_plan        TEXT,
    last_updated_by    TEXT,
    created_at         TEXT DEFAULT (datetime('now')),
    updated_at         TEXT DEFAULT (datetime('now')),
    UNIQUE (sef_id, section_code),
    FOREIGN KEY (sef_id) REFERENCES sef_documents(sef_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_sef_doc_year
    ON sef_documents(academic_year);
CREATE INDEX IF NOT EXISTS idx_sef_sections_doc
    ON sef_sections(sef_id);
"""


@dataclass
class SEFDocument:
    sef_id: int
    academic_year: str
    version: str
    title: str | None
    status: str
    headline_judgement: str
    author: str | None
    approved_by: str | None
    approved_date: str | None
    notes: str | None
    created_at: str | None = None
    updated_at: str | None = None


@dataclass
class SEFSection:
    section_id: int
    sef_id: int
    section_code: str
    section_title: str
    judgement: str
    strengths: str | None
    areas_for_development: str | None
    evidence: str | None
    action_plan: str | None
    last_updated_by: str | None
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
        logger.exception("Failed to initialise sef_builder tables")
        raise
    logger.info("Secondary sef_builder tables ready")
    _DB_READY = True


def _row_doc(r: sqlite3.Row) -> SEFDocument:
    return SEFDocument(
        sef_id=r["sef_id"], academic_year=r["academic_year"],
        version=r["version"], title=r["title"],
        status=r["status"],
        headline_judgement=r["headline_judgement"],
        author=r["author"], approved_by=r["approved_by"],
        approved_date=r["approved_date"], notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


def _row_section(r: sqlite3.Row) -> SEFSection:
    return SEFSection(
        section_id=r["section_id"], sef_id=r["sef_id"],
        section_code=r["section_code"],
        section_title=r["section_title"],
        judgement=r["judgement"], strengths=r["strengths"],
        areas_for_development=r["areas_for_development"],
        evidence=r["evidence"], action_plan=r["action_plan"],
        last_updated_by=r["last_updated_by"],
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


def _validate_doc(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    ay = (data.get("academic_year") or "").strip()
    if not ay:
        raise ValidationError("Academic year is required (e.g. 2025/26)")
    if not _AY_RE.match(ay):
        raise ValidationError(
            "Academic year must be in form YYYY/YY (e.g. 2025/26)")
    out["academic_year"] = ay

    version = (data.get("version") or "v1").strip()
    if not _VERSION_RE.match(version):
        raise ValidationError(
            "Version must be 1–16 chars (letters/digits/. - space)")
    out["version"] = version

    out["title"] = (data.get("title") or "").strip() or None

    status = (data.get("status") or DEFAULT_STATUS).strip()
    if status not in SEF_STATUSES:
        raise ValidationError(
            f"Status must be one of {', '.join(SEF_STATUSES)}")
    out["status"] = status

    judgement = (data.get("headline_judgement")
                  or DEFAULT_JUDGEMENT).strip()
    if judgement not in JUDGEMENTS:
        raise ValidationError(
            f"Judgement must be one of {', '.join(JUDGEMENTS)}")
    out["headline_judgement"] = judgement

    out["author"]      = (data.get("author") or "").strip() or None
    out["approved_by"] = (data.get("approved_by") or "").strip() or None
    out["approved_date"] = _validate_date(
        data.get("approved_date"), "Approved date", required=False)
    out["notes"]       = (data.get("notes") or "").strip() or None

    if out["status"] == "Approved":
        if not out["approved_by"]:
            raise ValidationError(
                "Approved by is required when status is Approved")
        if not out["approved_date"]:
            out["approved_date"] = _dt.date.today().isoformat()
        if out["headline_judgement"] == "Not yet evaluated":
            raise ValidationError(
                "Headline judgement is required when status is Approved")
    return out


def _validate_section(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    sid_raw = data.get("sef_id")
    if sid_raw in (None, ""):
        raise ValidationError("SEF ID is required")
    try:
        out["sef_id"] = int(sid_raw)
    except (TypeError, ValueError):
        raise ValidationError("SEF ID must be a number") from None

    code = (data.get("section_code") or "").strip().upper()
    if not code:
        raise ValidationError("Section code is required")
    if not _CODE_RE.match(code):
        raise ValidationError(
            "Section code must be 2–16 chars (A-Z, 0-9, _)")
    out["section_code"] = code

    title = (data.get("section_title") or "").strip()
    if not title:
        raise ValidationError("Section title is required")
    out["section_title"] = title

    judgement = (data.get("judgement") or DEFAULT_JUDGEMENT).strip()
    if judgement not in JUDGEMENTS:
        raise ValidationError(
            f"Judgement must be one of {', '.join(JUDGEMENTS)}")
    out["judgement"] = judgement

    out["strengths"]              = (data.get("strengths") or "").strip() or None
    out["areas_for_development"]  = (data.get("areas_for_development") or "").strip() or None
    out["evidence"]               = (data.get("evidence") or "").strip() or None
    out["action_plan"]            = (data.get("action_plan") or "").strip() or None
    out["last_updated_by"]        = (data.get("last_updated_by") or "").strip() or None
    return out


# ── Document CRUD ───────────────────────────────────────────────

def create_document(data: dict[str, Any], *,
                    seed_sections: bool = True) -> SEFDocument:
    init_db()
    payload = _validate_doc(data)
    try:
        with _connect() as conn:
            dup = conn.execute(
                "SELECT sef_id FROM sef_documents "
                "WHERE academic_year = ? AND version = ?",
                (payload["academic_year"], payload["version"]),
            ).fetchone()
            if dup:
                raise ValidationError(
                    f"A SEF for {payload['academic_year']} "
                    f"({payload['version']}) already exists")
            cur = conn.execute(
                """INSERT INTO sef_documents
                       (academic_year, version, title, status,
                        headline_judgement, author, approved_by,
                        approved_date, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (payload["academic_year"], payload["version"],
                 payload["title"], payload["status"],
                 payload["headline_judgement"], payload["author"],
                 payload["approved_by"], payload["approved_date"],
                 payload["notes"]),
            )
            conn.commit()
            new_id = cur.lastrowid
    except sqlite3.Error:
        logger.exception("Failed to create SEF document")
        raise
    rec = get_document(new_id)
    assert rec is not None
    logger.info("Created SEF document #%d %s/%s (status=%s)",
                rec.sef_id, rec.academic_year, rec.version, rec.status)
    if seed_sections:
        try:
            init_sections(new_id)
        except Exception:
            logger.exception(
                "Section seeding failed for SEF #%d", new_id)
    return rec


def get_document(sef_id: int) -> SEFDocument | None:
    init_db()
    try:
        with _connect() as conn:
            r = conn.execute(
                "SELECT * FROM sef_documents WHERE sef_id = ?",
                (sef_id,),
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get_document(%s) failed", sef_id)
        raise
    return _row_doc(r) if r else None


def list_documents(*, academic_year: str | None = None,
                   status: str | None = None) -> list[SEFDocument]:
    init_db()
    where: list[str] = []
    params: list[Any] = []
    if academic_year:
        where.append("academic_year = ?")
        params.append(academic_year.strip())
    if status:
        if status not in SEF_STATUSES:
            raise ValidationError(
                f"Status filter must be one of "
                f"{', '.join(SEF_STATUSES)}")
        where.append("status = ?")
        params.append(status)
    sql = "SELECT * FROM sef_documents"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY academic_year DESC, version DESC"
    try:
        with _connect() as conn:
            return [_row_doc(r)
                    for r in conn.execute(sql, tuple(params)).fetchall()]
    except sqlite3.Error:
        logger.exception("list_documents failed")
        raise


def update_document(sef_id: int,
                    data: dict[str, Any]) -> SEFDocument:
    init_db()
    existing = get_document(sef_id)
    if existing is None:
        raise ValidationError(f"No SEF document #{sef_id}")
    merged = {k: data.get(k, getattr(existing, k))
              for k in ("academic_year", "version", "title", "status",
                         "headline_judgement", "author", "approved_by",
                         "approved_date", "notes")}
    payload = _validate_doc(merged)
    try:
        with _connect() as conn:
            dup = conn.execute(
                "SELECT sef_id FROM sef_documents "
                "WHERE academic_year = ? AND version = ? "
                "  AND sef_id <> ?",
                (payload["academic_year"], payload["version"], sef_id),
            ).fetchone()
            if dup:
                raise ValidationError(
                    f"Another SEF for {payload['academic_year']} "
                    f"({payload['version']}) already exists")
            conn.execute(
                """UPDATE sef_documents SET
                       academic_year = ?, version = ?, title = ?,
                       status = ?, headline_judgement = ?,
                       author = ?, approved_by = ?, approved_date = ?,
                       notes = ?, updated_at = datetime('now')
                   WHERE sef_id = ?""",
                (payload["academic_year"], payload["version"],
                 payload["title"], payload["status"],
                 payload["headline_judgement"], payload["author"],
                 payload["approved_by"], payload["approved_date"],
                 payload["notes"], sef_id),
            )
            conn.commit()
    except sqlite3.Error:
        logger.exception("Failed to update SEF document #%d", sef_id)
        raise
    rec = get_document(sef_id)
    assert rec is not None
    logger.info("Updated SEF document #%d (status %s, judgement %s)",
                rec.sef_id, rec.status, rec.headline_judgement)
    return rec


def set_status(sef_id: int, status: str,
               *, approved_by: str | None = None) -> SEFDocument:
    payload: dict[str, Any] = {"status": status}
    if approved_by is not None:
        payload["approved_by"] = approved_by
    return update_document(sef_id, payload)


def delete_document(sef_id: int) -> bool:
    init_db()
    existing = get_document(sef_id)
    if existing is None:
        return False
    try:
        with _connect() as conn:
            conn.execute("PRAGMA foreign_keys=ON")
            cur = conn.execute(
                "DELETE FROM sef_documents WHERE sef_id = ?",
                (sef_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Failed to delete SEF document #%d", sef_id)
        raise
    if deleted:
        logger.info("Deleted SEF document #%d %s/%s "
                    "(cascade: sections)",
                    sef_id, existing.academic_year, existing.version)
    return deleted


# ── Section CRUD ────────────────────────────────────────────────

def init_sections(sef_id: int) -> int:
    """Seed the canonical Ofsted section list if not already present."""
    init_db()
    if get_document(sef_id) is None:
        raise ValidationError(f"No SEF document #{sef_id}")
    added = 0
    try:
        with _connect() as conn:
            for code, title in DEFAULT_SECTIONS:
                row = conn.execute(
                    "SELECT 1 FROM sef_sections "
                    "WHERE sef_id = ? AND section_code = ?",
                    (sef_id, code),
                ).fetchone()
                if row:
                    continue
                conn.execute(
                    """INSERT INTO sef_sections
                           (sef_id, section_code, section_title)
                       VALUES (?, ?, ?)""",
                    (sef_id, code, title),
                )
                added += 1
            conn.commit()
    except sqlite3.Error:
        logger.exception("init_sections(%d) failed", sef_id)
        raise
    if added:
        logger.info("Seeded %d default section(s) for SEF #%d",
                    added, sef_id)
    return added


def upsert_section(data: dict[str, Any]) -> SEFSection:
    init_db()
    payload = _validate_section(data)
    if get_document(payload["sef_id"]) is None:
        raise ValidationError(f"No SEF document #{payload['sef_id']}")
    try:
        with _connect() as conn:
            row = conn.execute(
                "SELECT section_id FROM sef_sections "
                "WHERE sef_id = ? AND section_code = ?",
                (payload["sef_id"], payload["section_code"]),
            ).fetchone()
            if row:
                conn.execute(
                    """UPDATE sef_sections SET
                           section_title = ?, judgement = ?,
                           strengths = ?, areas_for_development = ?,
                           evidence = ?, action_plan = ?,
                           last_updated_by = ?,
                           updated_at = datetime('now')
                       WHERE section_id = ?""",
                    (payload["section_title"], payload["judgement"],
                     payload["strengths"],
                     payload["areas_for_development"],
                     payload["evidence"], payload["action_plan"],
                     payload["last_updated_by"], row["section_id"]),
                )
                sid = row["section_id"]
                action = "updated"
            else:
                cur = conn.execute(
                    """INSERT INTO sef_sections
                           (sef_id, section_code, section_title,
                            judgement, strengths,
                            areas_for_development, evidence,
                            action_plan, last_updated_by)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (payload["sef_id"], payload["section_code"],
                     payload["section_title"], payload["judgement"],
                     payload["strengths"],
                     payload["areas_for_development"],
                     payload["evidence"], payload["action_plan"],
                     payload["last_updated_by"]),
                )
                sid = cur.lastrowid
                action = "inserted"
            conn.commit()
    except sqlite3.Error:
        logger.exception(
            "Failed to upsert SEF section %s on document %d",
            payload["section_code"], payload["sef_id"])
        raise
    logger.info("SEF section %s: sef=#%d code=%s judgement=%s",
                action, payload["sef_id"], payload["section_code"],
                payload["judgement"])
    rec = get_section(sid)
    assert rec is not None
    return rec


def get_section(section_id: int) -> SEFSection | None:
    init_db()
    try:
        with _connect() as conn:
            r = conn.execute(
                "SELECT * FROM sef_sections WHERE section_id = ?",
                (section_id,),
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get_section(%s) failed", section_id)
        raise
    return _row_section(r) if r else None


def list_sections(sef_id: int) -> list[SEFSection]:
    init_db()
    try:
        with _connect() as conn:
            return [_row_section(r) for r in conn.execute(
                "SELECT * FROM sef_sections WHERE sef_id = ? "
                "ORDER BY section_id",
                (sef_id,),
            ).fetchall()]
    except sqlite3.Error:
        logger.exception("list_sections(%s) failed", sef_id)
        raise


def delete_section(section_id: int) -> bool:
    init_db()
    try:
        with _connect() as conn:
            cur = conn.execute(
                "DELETE FROM sef_sections WHERE section_id = ?",
                (section_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception(
            "Failed to delete SEF section #%d", section_id)
        raise
    if deleted:
        logger.info("Deleted SEF section #%d", section_id)
    return deleted


def document_summary(sef_id: int) -> dict[str, Any]:
    init_db()
    doc = get_document(sef_id)
    if doc is None:
        raise ValidationError(f"No SEF document #{sef_id}")
    sections = list_sections(sef_id)
    evaluated = [s for s in sections
                 if s.judgement != "Not yet evaluated"]
    return {
        "document":      doc,
        "sections":      sections,
        "section_count": len(sections),
        "evaluated":     len(evaluated),
        "by_judgement":  dict(Counter(s.judgement for s in sections)),
    }
