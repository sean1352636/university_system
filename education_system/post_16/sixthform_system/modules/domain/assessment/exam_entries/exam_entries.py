"""Exam-entry data layer for the Sixth Form System.

An exam entry is a formal registration with an exam board for a single
paper sitting. One row per ``(student, paper_code, season, year)`` —
the UNIQUE constraint stops accidental double-entry of the same
candidate for the same paper.

Compared to mock exams:
* Mocks are practice papers we run internally; entries are externally
  invigilated board examinations.
* Mocks aggregate marks (one paper, many results); entries focus on
  *who is being entered* and their candidate number / fee / status.

Cascade: deleting a student wipes their entries.
"""

from __future__ import annotations

import logging
import re
import sqlite3
from dataclasses import dataclass
from typing import Any
from education_system.post_16.sixthform_system.core import paths
from education_system.post_16.sixthform_system.modules.domain.academics.subjects.subjects import EXAM_BOARDS

logger = logging.getLogger(__name__)

DB_PATH = paths.EXAM_ENTRIES_DB

SEASONS: tuple[str, ...] = ("Summer", "January", "November")
DEFAULT_SEASON: str = "Summer"

TIERS: tuple[str, ...] = ("Higher", "Foundation")  # mostly for GCSEs

STATUSES: tuple[str, ...] = ("Entered", "Withdrawn", "Absent", "Sat")
DEFAULT_STATUS: str = "Entered"

# Paper codes vary by board (Edexcel: 9MA0/01, AQA: 7367/1, OCR: H240/01).
# We allow anything 2–24 chars that looks paper-code-y.
_PAPER_CODE_RE = re.compile(r"^[A-Z0-9][A-Z0-9/.\-]{1,23}$")
_CANDIDATE_NO_RE = re.compile(r"^[A-Z0-9\- ]{2,16}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS exam_entries (
    entry_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id   TEXT NOT NULL,
    subject      TEXT NOT NULL,
    exam_board   TEXT NOT NULL,
    paper_code   TEXT NOT NULL,
    paper_title  TEXT,
    season       TEXT NOT NULL DEFAULT 'Summer',
    year         INTEGER NOT NULL,
    candidate_no TEXT,
    tier         TEXT,
    status       TEXT NOT NULL DEFAULT 'Entered',
    fee          REAL,
    notes        TEXT,
    created_at   TEXT DEFAULT (datetime('now')),
    updated_at   TEXT DEFAULT (datetime('now')),
    UNIQUE(student_id, paper_code, season, year),
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_entries_student ON exam_entries(student_id);
CREATE INDEX IF NOT EXISTS idx_entries_subject ON exam_entries(subject);
CREATE INDEX IF NOT EXISTS idx_entries_board   ON exam_entries(exam_board);
CREATE INDEX IF NOT EXISTS idx_entries_series  ON exam_entries(year, season);
CREATE INDEX IF NOT EXISTS idx_entries_status  ON exam_entries(status);
"""


@dataclass
class ExamEntry:
    entry_id: int
    student_id: str
    subject: str
    exam_board: str
    paper_code: str
    paper_title: str | None
    season: str
    year: int
    candidate_no: str | None
    tier: str | None
    status: str
    fee: float | None
    notes: str | None
    created_at: str
    updated_at: str


@dataclass
class EntryView:
    """One row in a bulk-entry sheet: student + existing entry (if any)."""
    student_id: str
    full_name: str
    entry: ExamEntry | None


# ── DB plumbing ────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    paths.ensure_directories()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


_DB_READY: bool = False


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    from education_system.post_16.sixthform_system.modules.domain.students.students import students as _students
    _students.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    logger.debug("Exam-entries schema ready at %s", DB_PATH)

    _DB_READY = True


def _row(r: sqlite3.Row) -> ExamEntry:
    return ExamEntry(
        entry_id=r["entry_id"], student_id=r["student_id"],
        subject=r["subject"], exam_board=r["exam_board"],
        paper_code=r["paper_code"], paper_title=r["paper_title"],
        season=r["season"], year=r["year"],
        candidate_no=r["candidate_no"], tier=r["tier"],
        status=r["status"], fee=r["fee"], notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


# ── Validation ────────────────────────────────────────────────────

class ValidationError(ValueError):
    """Raised for any invalid exam-entry input."""


def _require(value, label: str):
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        raise ValidationError(f"{label} is required")
    return value


def _validate_payload(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}

    sid = _require(data.get("student_id"), "Student ID").strip()
    from education_system.post_16.sixthform_system.modules.domain.students.students import students as _students
    if _students.get_student(sid) is None:
        raise ValidationError(f"No student with id {sid}")
    out["student_id"] = sid

    subject = _require(data.get("subject"), "Subject").strip()
    try:
        from education_system.post_16.sixthform_system.modules.domain.academics.subjects import subjects as _subjects
        if not _subjects.is_valid_subject(subject):
            raise ValidationError(f"Unknown subject: {subject}")
    except ImportError:
        pass
    out["subject"] = subject

    board = _require(data.get("exam_board"), "Exam board").strip()
    if board not in EXAM_BOARDS:
        raise ValidationError(
            f"Exam board must be one of: {', '.join(EXAM_BOARDS)}")
    out["exam_board"] = board

    code = _require(data.get("paper_code"), "Paper code").strip().upper()
    if not _PAPER_CODE_RE.match(code):
        raise ValidationError(
            "Paper code must be 2-24 chars: uppercase letters, digits, "
            "and . / -"
        )
    out["paper_code"] = code

    season = (data.get("season") or DEFAULT_SEASON).strip()
    if season not in SEASONS:
        raise ValidationError(
            f"Season must be one of: {', '.join(SEASONS)}")
    out["season"] = season

    year_raw = _require(data.get("year"), "Year")
    try:
        year = int(year_raw)
    except (TypeError, ValueError):
        raise ValidationError("Year must be a 4-digit number") from None
    if year < 2000 or year > 2099:
        raise ValidationError("Year must be between 2000 and 2099")
    out["year"] = year

    candidate = (data.get("candidate_no") or "").strip().upper()
    if candidate and not _CANDIDATE_NO_RE.match(candidate):
        raise ValidationError(
            "Candidate number must be 2-16 chars: letters, digits, spaces, "
            "hyphens"
        )
    out["candidate_no"] = candidate or None

    tier = (data.get("tier") or "").strip()
    if tier and tier not in TIERS:
        raise ValidationError(
            f"Tier must be blank or one of: {', '.join(TIERS)}")
    out["tier"] = tier or None

    status = (data.get("status") or DEFAULT_STATUS).strip()
    if status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    out["status"] = status

    fee = data.get("fee")
    if fee in (None, ""):
        out["fee"] = None
    else:
        try:
            f = float(fee)
        except (TypeError, ValueError):
            raise ValidationError("Fee must be a number") from None
        if f < 0 or f > 100000:
            raise ValidationError("Fee must be between 0 and 100,000")
        out["fee"] = round(f, 2)

    out["paper_title"] = (data.get("paper_title") or "").strip() or None
    out["notes"]       = (data.get("notes") or "").strip() or None
    return out


# ── CRUD ───────────────────────────────────────────────────────────

def create_entry(data: dict[str, Any]) -> ExamEntry:
    init_db()
    try:
        p = _validate_payload(data)
    except ValidationError as e:
        logger.warning("create_entry validation failed: %s", e)
        raise

    try:
        with _connect() as conn:
            cur = conn.execute(
                """INSERT INTO exam_entries
                       (student_id, subject, exam_board, paper_code,
                        paper_title, season, year, candidate_no, tier,
                        status, fee, notes,
                        created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                           datetime('now'), datetime('now'))""",
                (p["student_id"], p["subject"], p["exam_board"],
                 p["paper_code"], p["paper_title"], p["season"], p["year"],
                 p["candidate_no"], p["tier"], p["status"],
                 p["fee"], p["notes"]),
            )
            conn.commit()
            new_id = cur.lastrowid
    except sqlite3.IntegrityError as e:
        if "UNIQUE" in str(e):
            logger.warning(
                "create_entry: duplicate (%s, %s, %s, %s)",
                p["student_id"], p["paper_code"], p["season"], p["year"],
            )
            raise ValidationError(
                f"{p['student_id']} already has an entry for "
                f"{p['paper_code']} ({p['season']} {p['year']})"
            ) from e
        logger.exception("create_entry DB error")
        raise ValidationError(f"Database error: {e}") from e

    out = get_entry(new_id)
    assert out is not None
    logger.info(
        "Created exam entry #%d (%s for %s, %s %d, %s)",
        new_id, p["student_id"], p["paper_code"],
        p["season"], p["year"], p["status"],
    )
    return out


def get_entry(entry_id: int) -> ExamEntry | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM exam_entries WHERE entry_id = ?", (entry_id,),
        ).fetchone()
        return _row(r) if r else None


def list_entries(
    *,
    student_id: str | None = None,
    subject: str | None = None,
    exam_board: str | None = None,
    season: str | None = None,
    year: int | None = None,
    status: str | None = None,
    paper_code: str | None = None,
) -> list[ExamEntry]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id.strip())
    if subject:
        clauses.append("subject = ?")
        args.append(subject)
    if exam_board:
        if exam_board not in EXAM_BOARDS:
            raise ValidationError(
                f"Exam board must be one of: {', '.join(EXAM_BOARDS)}")
        clauses.append("exam_board = ?")
        args.append(exam_board)
    if season:
        if season not in SEASONS:
            raise ValidationError(
                f"Season must be one of: {', '.join(SEASONS)}")
        clauses.append("season = ?")
        args.append(season)
    if year is not None:
        clauses.append("year = ?")
        args.append(year)
    if status:
        if status not in STATUSES:
            raise ValidationError(
                f"Status must be one of: {', '.join(STATUSES)}")
        clauses.append("status = ?")
        args.append(status)
    if paper_code:
        clauses.append("paper_code = ?")
        args.append(paper_code.strip().upper())
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (
        f"SELECT * FROM exam_entries {where} "
        "ORDER BY year DESC, season, exam_board, paper_code, student_id"
    )
    with _connect() as conn:
        return [_row(r) for r in conn.execute(sql, args).fetchall()]


def entries_for_student(student_id: str) -> list[ExamEntry]:
    return list_entries(student_id=student_id)


def update_entry(entry_id: int, data: dict[str, Any]) -> ExamEntry:
    init_db()
    existing = get_entry(entry_id)
    if existing is None:
        logger.warning("update_entry: unknown id %d", entry_id)
        raise ValidationError(f"No exam entry with id {entry_id}")
    try:
        p = _validate_payload({
            "student_id":   existing.student_id,  # immutable
            "subject":      data.get("subject", existing.subject),
            "exam_board":   data.get("exam_board", existing.exam_board),
            "paper_code":   data.get("paper_code", existing.paper_code),
            "paper_title":  data.get("paper_title", existing.paper_title),
            "season":       data.get("season", existing.season),
            "year":         data.get("year", existing.year),
            "candidate_no": data.get("candidate_no", existing.candidate_no),
            "tier":         data.get("tier", existing.tier),
            "status":       data.get("status", existing.status),
            "fee":          data.get("fee", existing.fee),
            "notes":        data.get("notes", existing.notes),
        })
    except ValidationError as e:
        logger.warning("update_entry(%d) validation failed: %s", entry_id, e)
        raise

    try:
        with _connect() as conn:
            conn.execute(
                """UPDATE exam_entries SET
                       subject = ?, exam_board = ?, paper_code = ?,
                       paper_title = ?, season = ?, year = ?,
                       candidate_no = ?, tier = ?, status = ?, fee = ?,
                       notes = ?, updated_at = datetime('now')
                   WHERE entry_id = ?""",
                (p["subject"], p["exam_board"], p["paper_code"],
                 p["paper_title"], p["season"], p["year"],
                 p["candidate_no"], p["tier"], p["status"], p["fee"],
                 p["notes"], entry_id),
            )
            conn.commit()
    except sqlite3.IntegrityError as e:
        if "UNIQUE" in str(e):
            logger.warning("update_entry(%d): duplicate", entry_id)
            raise ValidationError(
                f"Another entry already exists for {existing.student_id} on "
                f"{p['paper_code']} ({p['season']} {p['year']})"
            ) from e
        logger.exception("update_entry DB error")
        raise ValidationError(f"Database error: {e}") from e

    out = get_entry(entry_id)
    assert out is not None
    logger.info(
        "Updated entry #%d (%s on %s, status=%s)",
        entry_id, out.student_id, out.paper_code, out.status,
    )
    return out


def delete_entry(entry_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM exam_entries WHERE entry_id = ?", (entry_id,),
        )
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted exam entry #%d", entry_id)
            return True
        logger.warning("delete_entry: unknown id %d", entry_id)
        return False


# ── Bulk-by-paper flow ────────────────────────────────────────────

def _roster_for_subject(subject: str) -> list:
    """Students taking the subject as any of their 3 A-Levels."""
    from education_system.post_16.sixthform_system.modules.domain.students.students import students as _students
    return [
        s for s in _students.list_students()
        if subject in (s.subjects if hasattr(s, "subjects") else
                       [s.subject_1, s.subject_2, s.subject_3])
    ]


def bulk_view(
    subject: str, paper_code: str, season: str, year: int,
) -> list[EntryView]:
    """Roster for ``subject`` joined to any existing entry for the
    given paper / season / year."""
    init_db()
    try:
        from education_system.post_16.sixthform_system.modules.domain.academics.subjects import subjects as _subjects
        if not _subjects.is_valid_subject(subject):
            raise ValidationError(f"Unknown subject: {subject}")
    except ImportError:
        pass
    if season not in SEASONS:
        raise ValidationError(
            f"Season must be one of: {', '.join(SEASONS)}")
    if not isinstance(year, int) or year < 2000 or year > 2099:
        raise ValidationError("Year must be between 2000 and 2099")

    paper_code = paper_code.strip().upper()
    students = _roster_for_subject(subject)
    sid_list = [s.student_id for s in students]
    if not sid_list:
        return []
    placeholders = ",".join("?" * len(sid_list))
    with _connect() as conn:
        rows = {
            r["student_id"]: _row(r)
            for r in conn.execute(
                f"""SELECT * FROM exam_entries
                    WHERE paper_code = ? AND season = ? AND year = ?
                      AND student_id IN ({placeholders})""",
                (paper_code, season, year, *sid_list),
            ).fetchall()
        }

    # Fold in any extra students who already have an entry for this paper
    # but aren't currently on the subject roster.
    extra_sids = set(rows) - set(sid_list)
    if extra_sids:
        from education_system.post_16.sixthform_system.modules.domain.students.students import students as _students
        for sid in extra_sids:
            s = _students.get_student(sid)
            if s is not None:
                students.append(s)

    return [
        EntryView(s.student_id, s.full_name, rows.get(s.student_id))
        for s in students
    ]


def save_bulk(
    *,
    subject: str,
    exam_board: str,
    paper_code: str,
    paper_title: str | None,
    season: str,
    year: int,
    tier: str | None,
    entries: dict[str, dict[str, Any]],
) -> int:
    """Upsert one row per student in ``entries``, all sharing the same
    paper / season / year. Per-row fields: candidate_no, status, fee,
    notes. Rows with status omitted default to ``Entered``. Returns
    rows written.

    Blank/missing entries are skipped — partial saves are fine.
    """
    init_db()
    written = 0
    for sid, payload in entries.items():
        if not any(payload.get(k) not in (None, "")
                   for k in ("candidate_no", "status", "fee", "notes")):
            # Treat empty rows as "skip" so a sheet of all-blanks doesn't
            # mass-create blank entries.
            continue
        full_payload = {
            "student_id":   sid,
            "subject":      subject,
            "exam_board":   exam_board,
            "paper_code":   paper_code,
            "paper_title":  paper_title,
            "season":       season,
            "year":         year,
            "tier":         tier,
            "candidate_no": payload.get("candidate_no"),
            "status":       payload.get("status") or DEFAULT_STATUS,
            "fee":          payload.get("fee"),
            "notes":        payload.get("notes"),
        }
        # If there's already an entry for this (student, paper, season,
        # year), update it; otherwise insert.
        with _connect() as conn:
            r = conn.execute(
                """SELECT entry_id FROM exam_entries
                   WHERE student_id = ? AND paper_code = ?
                     AND season = ? AND year = ?""",
                (sid, paper_code.strip().upper(), season, year),
            ).fetchone()
        if r is None:
            create_entry(full_payload)
        else:
            update_entry(r["entry_id"], full_payload)
        written += 1
    logger.info(
        "Bulk-saved %d entry/entries for %s (%s %d)",
        written, paper_code, season, year,
    )
    return written


# ── Summaries ─────────────────────────────────────────────────────

@dataclass
class SeriesSummary:
    """Counts for an entry "series" (board + season + year)."""
    total: int
    by_status: dict[str, int]
    by_subject: dict[str, int]
    total_fee: float


def series_summary(
    *,
    exam_board: str | None = None,
    season: str | None = None,
    year: int | None = None,
) -> SeriesSummary:
    init_db()
    rows = list_entries(
        exam_board=exam_board, season=season, year=year)
    by_status: dict[str, int] = {s: 0 for s in STATUSES}
    by_subject: dict[str, int] = {}
    total_fee = 0.0
    for r in rows:
        by_status[r.status] = by_status.get(r.status, 0) + 1
        by_subject[r.subject] = by_subject.get(r.subject, 0) + 1
        if r.fee is not None:
            total_fee += r.fee
    return SeriesSummary(
        total=len(rows),
        by_status=by_status,
        by_subject=by_subject,
        total_fee=round(total_fee, 2),
    )
