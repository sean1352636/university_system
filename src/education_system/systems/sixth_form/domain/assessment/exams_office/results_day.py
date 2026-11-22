"""Results day: embargo and release, qualification results, board imports.

Board results arrive before results day under embargo. They are
imported (from the board's CSV export) with ``released = 0`` and the
series' embargo time, so staff can check them while students cannot
see them. At the embargo time the series is released: every result in
it is flagged released and the release is logged.

Per-paper results live in ``exam_results`` (one row per component
entry). The grade a candidate actually takes away is the qualification
grade for the entry code, which the board awards from the total across
components; those rows live in ``exams_qualification_results``.

Grade changes (post-results reviews, corrections) are kept in
``exams_result_history`` for both kinds of result.
"""

from __future__ import annotations

import csv
import io
import logging
from dataclasses import dataclass, field
from typing import Any

from education_system.systems.sixth_form.domain.assessment.exams_office import store
from education_system.systems.sixth_form.domain.assessment.exams_office.store import (
    ValidationError,
)

logger = logging.getLogger(__name__)

# Results are published to candidates from 08:00 on results day.
DEFAULT_RELEASE_TIME: str = "08:00"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS exams_results_release (
    release_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    season         TEXT NOT NULL,
    year           INTEGER NOT NULL,
    exam_board     TEXT NOT NULL DEFAULT '',
    results_date   TEXT NOT NULL,
    embargo_until  TEXT NOT NULL,
    released_at    TEXT,
    released_by    TEXT,
    notes          TEXT,
    UNIQUE(season, year, exam_board)
);

CREATE TABLE IF NOT EXISTS exams_qualification_results (
    qual_result_id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id     TEXT NOT NULL,
    exam_board     TEXT NOT NULL,
    entry_code     TEXT NOT NULL,
    subject        TEXT,
    qualification_type TEXT,
    season         TEXT NOT NULL,
    year           INTEGER NOT NULL,
    grade          TEXT NOT NULL,
    marks          INTEGER,
    ums            INTEGER,
    released       INTEGER NOT NULL DEFAULT 0,
    embargo_until  TEXT,
    source         TEXT,
    notes          TEXT,
    recorded_at    TEXT DEFAULT (datetime('now')),
    updated_at     TEXT DEFAULT (datetime('now')),
    UNIQUE(student_id, entry_code, season, year),
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_exams_qual_series
    ON exams_qualification_results(year, season);

CREATE TABLE IF NOT EXISTS exams_result_history (
    history_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    result_id      INTEGER,
    qual_result_id INTEGER,
    old_grade      TEXT,
    new_grade      TEXT,
    old_marks      INTEGER,
    new_marks      INTEGER,
    reason         TEXT,
    source_ref     TEXT,
    changed_by     TEXT,
    changed_at     TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (result_id) REFERENCES exam_results(result_id) ON DELETE CASCADE,
    FOREIGN KEY (qual_result_id)
        REFERENCES exams_qualification_results(qual_result_id) ON DELETE CASCADE
);
"""


def _results_init() -> None:
    from education_system.systems.sixth_form.domain.assessment.exam_results import (
        exam_results as _results,
    )
    _results.init_db()


def init_db() -> None:
    store.ensure("results_day", _SCHEMA, after=(_results_init,))


# ── Shapes ──────────────────────────────────────────────────────────

@dataclass
class Release:
    release_id: int
    season: str
    year: int
    exam_board: str        # '' = every board in the series
    results_date: str
    embargo_until: str
    released_at: str | None
    released_by: str | None
    notes: str | None

    @property
    def released(self) -> bool:
        return bool(self.released_at)

    @property
    def due(self) -> bool:
        return not self.released and self.embargo_until <= store.now()


@dataclass
class QualificationResult:
    qual_result_id: int
    student_id: str
    exam_board: str
    entry_code: str
    subject: str | None
    qualification_type: str | None
    season: str
    year: int
    grade: str
    marks: int | None
    ums: int | None
    released: bool
    embargo_until: str | None
    source: str | None
    notes: str | None
    recorded_at: str | None
    updated_at: str | None
    full_name: str | None = None

    @property
    def visible(self) -> bool:
        return self.released or bool(self.embargo_until and self.embargo_until <= store.now())


@dataclass
class HistoryRow:
    history_id: int
    result_id: int | None
    qual_result_id: int | None
    old_grade: str | None
    new_grade: str | None
    old_marks: int | None
    new_marks: int | None
    reason: str | None
    source_ref: str | None
    changed_by: str | None
    changed_at: str


@dataclass
class ImportReport:
    rows: int = 0
    components: int = 0
    qualifications: int = 0
    problems: list[str] = field(default_factory=list)


_QUAL_FIELDS = ("qual_result_id", "student_id", "exam_board", "entry_code", "subject",
                "qualification_type", "season", "year", "grade", "marks", "ums",
                "released", "embargo_until", "source", "notes", "recorded_at",
                "updated_at")


def _qual(r, names: dict[str, str] | None = None) -> QualificationResult:
    q = QualificationResult(**{k: r[k] for k in _QUAL_FIELDS})
    q.released = bool(q.released)
    q.full_name = (names or {}).get(q.student_id)
    return q


def _release(r) -> Release:
    return Release(**{k: r[k] for k in (
        "release_id", "season", "year", "exam_board", "results_date",
        "embargo_until", "released_at", "released_by", "notes")})


# ── Release schedule ────────────────────────────────────────────────

def schedule_release(data: dict[str, Any]) -> Release:
    """Set results day and the embargo time for a series (optionally one board)."""
    init_db()
    season, year = store.season_year(data.get("season"), data.get("year"))
    board = store.board(data.get("exam_board"), required=False) or ""
    results_date = store.date(data.get("results_date"), "Results date", required=True)
    embargo = store.datetime_(data.get("embargo_until"), "Embargo until") or \
        f"{results_date} {DEFAULT_RELEASE_TIME}"
    with store.connect() as conn:
        conn.execute(
            """INSERT INTO exams_results_release
                   (season, year, exam_board, results_date, embargo_until, notes)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(season, year, exam_board) DO UPDATE SET
                   results_date = excluded.results_date,
                   embargo_until = excluded.embargo_until,
                   notes = excluded.notes""",
            (season, year, board, results_date, embargo,
             store.text(data.get("notes"), "Notes", limit=500)))
        # Results already imported for the series pick up the new embargo.
        _apply_embargo(conn, season, year, board, embargo)
        conn.commit()
    out = get_release(season, year, board)
    assert out is not None
    return out


def _series_entry_ids(conn, season: str, year: int, board: str) -> list[int]:
    from education_system.systems.sixth_form.domain.assessment.exams_office.boards import (
        stored_names,
    )
    sql = "SELECT entry_id FROM exam_entries WHERE season = ? AND year = ?"
    args: list[Any] = [season, year]
    if board:
        names = stored_names(board)
        sql += f" AND exam_board IN ({','.join('?' * len(names))})"
        args.extend(names)
    return [r["entry_id"] for r in conn.execute(sql, args)]


def _apply_embargo(conn, season: str, year: int, board: str, embargo: str) -> None:
    ids = _series_entry_ids(conn, season, year, board)
    for i in range(0, len(ids), 500):
        chunk = ids[i:i + 500]
        conn.execute(
            f"UPDATE exam_results SET embargo_until = ? WHERE released = 0 "
            f"AND entry_id IN ({','.join('?' * len(chunk))})", (embargo, *chunk))
    sql = ("UPDATE exams_qualification_results SET embargo_until = ? "
           "WHERE released = 0 AND season = ? AND year = ?")
    args: list[Any] = [embargo, season, year]
    if board:
        sql += " AND exam_board = ?"
        args.append(board)
    conn.execute(sql, args)


def get_release(season: str, year: int, exam_board: str = "") -> Release | None:
    init_db()
    with store.connect() as conn:
        r = conn.execute(
            "SELECT * FROM exams_results_release WHERE season = ? AND year = ? "
            "AND exam_board = ?", (season, int(year), exam_board or "")).fetchone()
    return _release(r) if r else None


def release_for(season: str, year: int, exam_board: str | None) -> Release | None:
    """The board's own release record, else the whole-series one."""
    if exam_board:
        r = get_release(season, year, store.board(exam_board) or "")
        if r:
            return r
    return get_release(season, year, "")


def list_releases(*, year: int | None = None) -> list[Release]:
    init_db()
    sql = "SELECT * FROM exams_results_release"
    args: list[Any] = []
    if year is not None:
        sql += " WHERE year = ?"
        args.append(int(year))
    with store.connect() as conn:
        rows = conn.execute(sql + " ORDER BY results_date DESC, exam_board", args).fetchall()
    return [_release(r) for r in rows]


def release_series(season: str, year: int, exam_board: str | None = None, *,
                   actor: str | None = None) -> tuple[int, int]:
    """Release a series' results once its embargo has passed.

    Returns ``(component results released, qualification results released)``.
    """
    init_db()
    season, year = store.season_year(season, year)
    board = store.board(exam_board, required=False) or ""
    rel = get_release(season, year, board)
    if rel is None:
        raise ValidationError(
            f"No results day scheduled for {season} {year}"
            + (f" ({board})" if board else "") + " — schedule it first")
    if rel.released:
        raise ValidationError(f"Already released at {rel.released_at} by {rel.released_by}")
    if rel.embargo_until > store.now():
        raise ValidationError(
            f"Results are under embargo until {rel.embargo_until} — they cannot be "
            "released before then")
    who = store.actor(actor)
    with store.connect() as conn:
        ids = _series_entry_ids(conn, season, year, board)
        comp = 0
        for i in range(0, len(ids), 500):
            chunk = ids[i:i + 500]
            cur = conn.execute(
                f"UPDATE exam_results SET released = 1, "
                f"released_at = COALESCE(released_at, ?) WHERE released = 0 "
                f"AND entry_id IN ({','.join('?' * len(chunk))})",
                (rel.results_date, *chunk))
            comp += cur.rowcount
        sql = ("UPDATE exams_qualification_results SET released = 1, "
               "updated_at = datetime('now') WHERE released = 0 AND season = ? AND year = ?")
        args: list[Any] = [season, year]
        if board:
            sql += " AND exam_board = ?"
            args.append(board)
        qual = conn.execute(sql, args).rowcount
        conn.execute(
            "UPDATE exams_results_release SET released_at = ?, released_by = ? "
            "WHERE release_id = ?", (store.now(), who, rel.release_id))
        conn.commit()
    logger.info("Released %s %d %s: %d component, %d qualification result(s)",
                season, year, board or "(all boards)", comp, qual)
    return comp, qual


def release_due(*, actor: str | None = None) -> list[tuple[Release, int, int]]:
    """Release every scheduled series whose embargo has passed."""
    out = []
    for rel in list_releases():
        if rel.due:
            comp, qual = release_series(rel.season, rel.year, rel.exam_board or None,
                                        actor=actor)
            out.append((rel, comp, qual))
    return out


def embargoed_counts(season: str, year: int) -> tuple[int, int]:
    """(component, qualification) results still hidden for a series."""
    init_db()
    with store.connect() as conn:
        ids = _series_entry_ids(conn, season, int(year), "")
        comp = 0
        for i in range(0, len(ids), 500):
            chunk = ids[i:i + 500]
            comp += conn.execute(
                f"SELECT COUNT(*) FROM exam_results WHERE released = 0 AND entry_id IN "
                f"({','.join('?' * len(chunk))})", chunk).fetchone()[0]
        qual = conn.execute(
            "SELECT COUNT(*) FROM exams_qualification_results WHERE released = 0 "
            "AND season = ? AND year = ?", (season, int(year))).fetchone()[0]
    return comp, qual


def hold_result(result_id: int, *, embargo_until: str | None = None) -> None:
    """Put one component result back under embargo (e.g. a late correction)."""
    init_db()
    with store.connect() as conn:
        conn.execute("UPDATE exam_results SET released = 0, embargo_until = ? "
                     "WHERE result_id = ?",
                     (store.datetime_(embargo_until, "Embargo until"), int(result_id)))
        conn.commit()


# ── Qualification results ───────────────────────────────────────────

def _validate_grade(grade: str, qualification_type: str | None) -> str:
    from education_system.systems.sixth_form.domain.academics.qualifications import (
        grade_scales,
    )
    try:
        return grade_scales.validate_grade(grade, qualification_type)
    except ValueError as e:
        raise ValidationError(str(e)) from None


def _qualification_type_for(board: str, entry_code: str) -> str | None:
    from education_system.systems.sixth_form.domain.assessment.exams_office import (
        entry_admin,
    )
    comps = entry_admin.list_components(exam_board=board, entry_code=entry_code)
    return next((c.qualification_type for c in comps if c.qualification_type), None)


def save_qualification_result(data: dict[str, Any], *, source: str = "manual",
                              released: bool | None = None,
                              reason: str | None = None) -> QualificationResult:
    """Record a candidate's overall grade for an entry code (upsert)."""
    init_db()
    from education_system.systems.sixth_form.domain.assessment.exam_entries import (
        exam_entries as _entries,
    )
    sid = store.student(data.get("student_id"))
    board = store.board(data.get("exam_board"))
    season, year = store.season_year(data.get("season"), data.get("year"))
    code = (store.text(data.get("entry_code"), "Entry code", limit=24,
                       required=True) or "").upper()
    entries = [e for e in _entries.list_entries(student_id=sid, season=season, year=year)
               if (e.entry_code or "") == code]
    if not entries:
        raise ValidationError(f"{sid} has no {season} {year} entries under {code}")
    qual_type = (store.text(data.get("qualification_type"), "Qualification type", limit=60)
                 or _qualification_type_for(board, code))
    grade = _validate_grade(store.text(data.get("grade"), "Grade", limit=20,
                                       required=True), qual_type)
    marks = store.integer(data.get("marks"), "Marks", lo=0, hi=10000)
    ums = store.integer(data.get("ums"), "UMS", lo=0, hi=10000)
    rel = release_for(season, year, board)
    if released is None:
        released = bool(rel and rel.released) if source == "import" else True
    embargo = None if released else (rel.embargo_until if rel else None)
    existing = get_qualification_result(sid, code, season, year)
    with store.connect() as conn:
        conn.execute(
            """INSERT INTO exams_qualification_results
                   (student_id, exam_board, entry_code, subject, qualification_type,
                    season, year, grade, marks, ums, released, embargo_until,
                    source, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(student_id, entry_code, season, year) DO UPDATE SET
                   exam_board = excluded.exam_board,
                   subject = excluded.subject,
                   qualification_type = excluded.qualification_type,
                   grade = excluded.grade, marks = excluded.marks,
                   ums = excluded.ums,
                   released = MAX(exams_qualification_results.released, excluded.released),
                   embargo_until = excluded.embargo_until,
                   source = excluded.source,
                   notes = COALESCE(excluded.notes, exams_qualification_results.notes),
                   updated_at = datetime('now')""",
            (sid, board, code, entries[0].subject, qual_type, season, year, grade,
             marks, ums, 1 if released else 0, embargo, source,
             store.text(data.get("notes"), "Notes", limit=500)))
        conn.commit()
    out = get_qualification_result(sid, code, season, year)
    assert out is not None
    if existing and (existing.grade, existing.marks) != (out.grade, out.marks):
        log_grade_change(qual_result_id=out.qual_result_id, old_grade=existing.grade,
                         new_grade=out.grade, old_marks=existing.marks,
                         new_marks=out.marks, reason=reason or f"Updated ({source})")
    return out


def get_qualification_result(student_id: str, entry_code: str, season: str,
                             year: int) -> QualificationResult | None:
    init_db()
    with store.connect() as conn:
        r = conn.execute(
            "SELECT * FROM exams_qualification_results WHERE student_id = ? AND "
            "entry_code = ? AND season = ? AND year = ?",
            (student_id, entry_code.upper(), season, int(year))).fetchone()
    return _qual(r) if r else None


def get_qualification_result_by_id(qual_result_id: int) -> QualificationResult | None:
    init_db()
    with store.connect() as conn:
        r = conn.execute("SELECT * FROM exams_qualification_results WHERE qual_result_id = ?",
                         (int(qual_result_id),)).fetchone()
    return _qual(r) if r else None


def list_qualification_results(*, season: str | None = None, year: int | None = None,
                               student_id: str | None = None,
                               exam_board: str | None = None,
                               released_only: bool | None = None) -> list[QualificationResult]:
    init_db()
    if released_only is None:
        try:
            from education_system.systems.sixth_form.domain.governance.user_management import (
                access as _access,
            )
            who = _access.current()
            released_only = who.is_student or who.is_parent
        except Exception:
            released_only = False
    clauses, args = [], []
    for col, val in (("season", season), ("student_id", student_id)):
        if val:
            clauses.append(f"{col} = ?")
            args.append(val)
    if year is not None:
        clauses.append("year = ?")
        args.append(int(year))
    if exam_board:
        clauses.append("exam_board = ?")
        args.append(store.board(exam_board))
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    names = store.student_names()
    with store.connect() as conn:
        rows = conn.execute(f"SELECT * FROM exams_qualification_results {where} "
                            "ORDER BY year DESC, season, student_id, entry_code",
                            args).fetchall()
    out = [_qual(r, names) for r in rows]
    return [q for q in out if q.visible] if released_only else out


def delete_qualification_result(qual_result_id: int) -> bool:
    init_db()
    with store.connect() as conn:
        cur = conn.execute("DELETE FROM exams_qualification_results WHERE qual_result_id = ?",
                           (int(qual_result_id),))
        conn.commit()
    return bool(cur.rowcount)


@dataclass
class ComponentTotal:
    """Component results rolled up under an entry code, for checking."""
    student_id: str
    full_name: str
    exam_board: str
    entry_code: str
    season: str
    year: int
    components_entered: int
    components_with_results: int
    total_marks: int | None
    qualification_grade: str | None


def component_totals(season: str, year: int) -> list[ComponentTotal]:
    """Per candidate per entry code: components entered vs resulted and
    the total of their marks, beside any qualification grade held."""
    from education_system.systems.sixth_form.domain.assessment.exam_entries import (
        exam_entries as _entries,
    )
    from education_system.systems.sixth_form.domain.assessment.exam_results import (
        exam_results as _results,
    )
    season, year = store.season_year(season, year)
    names = store.student_names()
    results = {r.result.entry_id: r.result
               for r in _results.list_results(season=season, year=year, released_only=False)}
    quals = {(q.student_id, q.entry_code): q
             for q in list_qualification_results(season=season, year=year,
                                                 released_only=False)}
    groups: dict[tuple[str, str], list] = {}
    for e in _entries.list_entries(season=season, year=year):
        if e.status == "Withdrawn":
            continue
        groups.setdefault((e.student_id, e.entry_code or e.paper_code), []).append(e)
    out = []
    for (sid, code), es in sorted(groups.items()):
        res = [results[e.entry_id] for e in es if e.entry_id in results]
        marks = [r.marks for r in res if r.marks is not None]
        q = quals.get((sid, code))
        out.append(ComponentTotal(sid, names.get(sid, "(unknown)"), es[0].exam_board,
                                  code, season, year, len(es), len(res),
                                  sum(marks) if marks else None, q.grade if q else None))
    return out


# ── History ─────────────────────────────────────────────────────────

def log_grade_change(*, result_id: int | None = None, qual_result_id: int | None = None,
                     old_grade: str | None, new_grade: str | None,
                     old_marks: int | None = None, new_marks: int | None = None,
                     reason: str | None = None, source_ref: str | None = None,
                     actor: str | None = None) -> None:
    init_db()
    with store.connect() as conn:
        conn.execute(
            """INSERT INTO exams_result_history
                   (result_id, qual_result_id, old_grade, new_grade, old_marks,
                    new_marks, reason, source_ref, changed_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (result_id, qual_result_id, old_grade, new_grade, old_marks, new_marks,
             reason, source_ref, store.actor(actor)))
        conn.commit()


def history(*, result_id: int | None = None,
            qual_result_id: int | None = None) -> list[HistoryRow]:
    init_db()
    clauses, args = [], []
    if result_id is not None:
        clauses.append("result_id = ?")
        args.append(int(result_id))
    if qual_result_id is not None:
        clauses.append("qual_result_id = ?")
        args.append(int(qual_result_id))
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with store.connect() as conn:
        rows = conn.execute(f"SELECT * FROM exams_result_history {where} "
                            "ORDER BY changed_at DESC, history_id DESC", args).fetchall()
    return [HistoryRow(**{k: r[k] for k in (
        "history_id", "result_id", "qual_result_id", "old_grade", "new_grade",
        "old_marks", "new_marks", "reason", "source_ref", "changed_by",
        "changed_at")}) for r in rows]


# ── Board CSV import ────────────────────────────────────────────────

_HEADER_ALIASES: dict[str, tuple[str, ...]] = {
    "board": ("board", "exam_board", "awarding_body", "awarding body"),
    "candidate": ("candidate_number", "candidate number", "candidate_no",
                  "candidate no", "candidate", "cand_no"),
    "uci": ("uci", "unique candidate identifier"),
    "entry_code": ("entry_code", "entry code", "option code", "option_code",
                   "qualification code", "cash-in code"),
    "component_code": ("component_code", "component code", "component", "paper_code",
                       "paper code", "unit code"),
    "grade": ("grade", "result", "overall grade"),
    "marks": ("marks", "mark", "raw mark", "total mark"),
    "ums": ("ums", "uniform mark"),
}


def _map_headers(fieldnames: list[str]) -> dict[str, str]:
    found: dict[str, str] = {}
    for name in fieldnames or []:
        low = (name or "").strip().lower()
        for key, aliases in _HEADER_ALIASES.items():
            if low in aliases and key not in found:
                found[key] = name
    missing = [k for k in ("candidate", "entry_code", "grade") if k not in found]
    if "board" not in found:
        missing.append("board")
    if missing:
        raise ValidationError(
            "The results file is missing column(s): " + ", ".join(missing)
            + " (expected: board, candidate number, entry code, grade, marks)")
    return found


def import_results_csv(content: str, *, season: str, year: int,
                       dry_run: bool = False) -> ImportReport:
    """Import a board results file in CSV form (see :func:`import_result_rows`)."""
    reader = csv.DictReader(io.StringIO(content.lstrip("\ufeff")))
    cols = _map_headers(list(reader.fieldnames or []))
    rows: list[tuple[int, dict[str, str]]] = []
    for n, row in enumerate(reader, start=2):
        rows.append((n, {key: (row.get(col) or "").strip() for key, col in cols.items()}))
    return import_result_rows(rows, season=season, year=year, dry_run=dry_run)


def import_result_rows(rows: list[tuple[int, dict[str, str]]], *, season: str,
                       year: int, dry_run: bool = False) -> ImportReport:
    """Import parsed board result rows (CSV or EDI fixed-width).

    ``rows`` holds ``(line number, {board, candidate, uci, entry_code,
    component_code, grade, marks, ums})``. Each row is matched to a
    student by candidate number (or UCI), then:

    * a ``component_code``, or an entry code that is itself one of the
      candidate's component codes, writes a per-paper result;
    * otherwise the entry code is treated as the qualification code and
      writes a qualification result.

    Results land under the series' embargo (``released = 0``) unless the
    series has already been released. With ``dry_run`` nothing is
    written; the report says what would happen.
    """
    init_db()
    from education_system.systems.sixth_form.domain.assessment.exam_entries import (
        exam_entries as _entries,
    )
    from education_system.systems.sixth_form.domain.assessment.exam_results import (
        exam_results as _results,
    )
    from education_system.systems.sixth_form.domain.assessment.exams_office import (
        candidates,
    )
    season, year = store.season_year(season, year)
    report = ImportReport()
    entries_by_student: dict[str, list] = {}
    for e in _entries.list_entries(season=season, year=year):
        entries_by_student.setdefault(e.student_id, []).append(e)

    for n, row in rows:
        report.rows += 1

        def cell(key: str, _row=row) -> str:
            return (_row.get(key) or "").strip()

        board = store.board(cell("board"), required=False) if cell("board") else None
        if cell("board") and board is None:
            report.problems.append(f"Line {n}: unknown board {cell('board')!r}")
            continue
        sid = candidates.find_student(cell("candidate"), board=board, uci=cell("uci"))
        if sid is None:
            report.problems.append(
                f"Line {n}: no student with candidate number {cell('candidate')!r}")
            continue
        grade = cell("grade")
        if not grade:
            report.problems.append(f"Line {n}: no grade")
            continue
        code = cell("entry_code").upper()
        comp = cell("component_code").upper()
        mine = entries_by_student.get(sid, [])
        target = next((e for e in mine if e.paper_code == (comp or code)), None)
        try:
            if target is not None:
                rel = release_for(season, year, target.exam_board)
                released = bool(rel and rel.released)
                payload = {
                    "entry_id": target.entry_id, "grade": grade,
                    "marks": cell("marks") or None, "ums": cell("ums") or None,
                    "released_at": rel.results_date if rel else None,
                    "notes": None,
                }
                # Same checks save_result applies (grade scale, marks range).
                checked = _results._validate_payload(payload)
                if not dry_run:
                    before = _results.get_for_entry(target.entry_id)
                    embargo = None if released else (rel.embargo_until if rel else None)
                    with store.connect() as conn:
                        # Lay the row down hidden *before* the upsert so a new
                        # result is never visible, even for a moment.
                        conn.execute(
                            "INSERT OR IGNORE INTO exam_results "
                            "(entry_id, grade, released, embargo_until, source) "
                            "VALUES (?, ?, ?, ?, 'import')",
                            (target.entry_id, checked["grade"],
                             1 if released else 0, embargo))
                        conn.execute(
                            "UPDATE exam_results SET released = ?, embargo_until = ?, "
                            "source = 'import' WHERE entry_id = ?",
                            (1 if released else 0, embargo, target.entry_id))
                        conn.commit()
                    after = _results.save_result(payload)
                    if before and (before.grade, before.marks) != (after.grade, after.marks):
                        log_grade_change(result_id=after.result_id, old_grade=before.grade,
                                         new_grade=after.grade, old_marks=before.marks,
                                         new_marks=after.marks,
                                         reason="Board results import")
                report.components += 1
            elif any((e.entry_code or "") == code for e in mine):
                if not dry_run:
                    save_qualification_result({
                        "student_id": sid,
                        "exam_board": board or next(e.exam_board for e in mine
                                                    if (e.entry_code or "") == code),
                        "entry_code": code, "season": season, "year": year,
                        "grade": grade, "marks": cell("marks") or None,
                        "ums": cell("ums") or None,
                    }, source="import", reason="Board results import")
                report.qualifications += 1
            else:
                report.problems.append(
                    f"Line {n}: {sid} has no {season} {year} entry for {comp or code}")
        except (ValidationError, ValueError) as e:
            report.problems.append(f"Line {n}: {e}")
    logger.info("Results import %s %d: %d rows, %d component, %d qualification, "
                "%d problem(s)%s", season, year, report.rows, report.components,
                report.qualifications, len(report.problems),
                " (dry run)" if dry_run else "")
    return report
