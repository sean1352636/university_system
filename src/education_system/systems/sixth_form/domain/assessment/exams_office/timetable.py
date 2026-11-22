"""The board exam timetable, candidate clashes and contingency days.

One timetable row per component paper per series: date, AM/PM session,
start time, duration, board. Rows link to exam entries by
``(component_code, season, year)``, which is how candidate clashes are
found: a candidate entered for two papers timetabled in the same
session on the same day.

A clash is resolved by recording what the centre will do (JCQ's
options: sit the papers one after the other in the session with a
supervised break, or move one to the next session with the candidate
kept under supervision in between). A resolution may move one paper's
time for that candidate.

Each series has a JCQ contingency day (a whole day kept free in case
national disruption stops a session) recorded here so nothing else is
booked on it.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from education_system.systems.sixth_form.domain.assessment.exams_office import store
from education_system.systems.sixth_form.domain.assessment.exams_office.boards import (
    SESSION_START,
    SESSIONS,
)
from education_system.systems.sixth_form.domain.assessment.exams_office.store import (
    ValidationError,
)

logger = logging.getLogger(__name__)

RESOLUTION_METHODS: tuple[str, ...] = (
    "Sit consecutively in the same session (supervised break)",
    "Supervised move to the next session",
    "Overnight supervision to the next morning",
    "Move to the contingency day (board approval)",
    "Entry changed / withdrawn",
)

# JCQ: when clashing papers are sat back to back, the total time in one
# session above which a move to another session should be considered.
MAX_CONSECUTIVE_MINUTES: int = 5 * 60

_SCHEMA = """
CREATE TABLE IF NOT EXISTS exams_timetable (
    timetable_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    exam_board       TEXT NOT NULL,
    season           TEXT NOT NULL,
    year             INTEGER NOT NULL,
    entry_code       TEXT,
    component_code   TEXT NOT NULL,
    title            TEXT,
    exam_date        TEXT NOT NULL,
    session          TEXT NOT NULL,
    start_time       TEXT NOT NULL,
    duration_minutes INTEGER NOT NULL,
    notes            TEXT,
    UNIQUE(exam_board, component_code, season, year)
);
CREATE INDEX IF NOT EXISTS idx_exams_tt_date ON exams_timetable(exam_date, session);
CREATE INDEX IF NOT EXISTS idx_exams_tt_series ON exams_timetable(year, season);

CREATE TABLE IF NOT EXISTS exams_contingency_days (
    contingency_id INTEGER PRIMARY KEY AUTOINCREMENT,
    season         TEXT NOT NULL,
    year           INTEGER NOT NULL,
    exam_date      TEXT NOT NULL,
    session        TEXT,
    notes          TEXT,
    UNIQUE(season, year, exam_date, session)
);

CREATE TABLE IF NOT EXISTS exams_clash_resolutions (
    resolution_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id      TEXT NOT NULL,
    season          TEXT NOT NULL,
    year            INTEGER NOT NULL,
    exam_date       TEXT NOT NULL,
    session         TEXT NOT NULL,
    method          TEXT NOT NULL,
    moved_timetable_id INTEGER,
    moved_to_date   TEXT,
    moved_to_session TEXT,
    moved_to_time   TEXT,
    supervisor      TEXT,
    notes           TEXT,
    recorded_by     TEXT,
    recorded_at     TEXT DEFAULT (datetime('now')),
    UNIQUE(student_id, season, year, exam_date, session),
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE,
    FOREIGN KEY (moved_timetable_id) REFERENCES exams_timetable(timetable_id)
        ON DELETE SET NULL
);
"""


def init_db() -> None:
    store.ensure("timetable", _SCHEMA)


# ── Shapes ──────────────────────────────────────────────────────────

@dataclass
class Paper:
    timetable_id: int
    exam_board: str
    season: str
    year: int
    entry_code: str | None
    component_code: str
    title: str | None
    exam_date: str
    session: str
    start_time: str
    duration_minutes: int
    notes: str | None

    @property
    def end_time(self) -> str:
        return store.add_minutes(self.start_time, self.duration_minutes)

    @property
    def label(self) -> str:
        return (f"{self.component_code} {self.exam_date} {self.session} "
                f"{self.start_time}-{self.end_time}")


@dataclass
class ContingencyDay:
    contingency_id: int
    season: str
    year: int
    exam_date: str
    session: str | None
    notes: str | None


@dataclass
class Resolution:
    resolution_id: int
    student_id: str
    season: str
    year: int
    exam_date: str
    session: str
    method: str
    moved_timetable_id: int | None
    moved_to_date: str | None
    moved_to_session: str | None
    moved_to_time: str | None
    supervisor: str | None
    notes: str | None
    recorded_by: str | None
    recorded_at: str | None


@dataclass
class Clash:
    """One candidate entered for two or more papers in one session."""
    student_id: str
    full_name: str
    exam_date: str
    session: str
    papers: list[Paper] = field(default_factory=list)
    resolution: Resolution | None = None
    extra_time_pct: int = 0

    @property
    def total_minutes(self) -> int:
        base = sum(p.duration_minutes for p in self.papers)
        return round(base * (100 + self.extra_time_pct) / 100)

    @property
    def resolved(self) -> bool:
        return self.resolution is not None

    @property
    def needs_move(self) -> bool:
        """Too long to sit back to back in one session."""
        return self.total_minutes > MAX_CONSECUTIVE_MINUTES


def _paper(r) -> Paper:
    return Paper(**{k: r[k] for k in (
        "timetable_id", "exam_board", "season", "year", "entry_code",
        "component_code", "title", "exam_date", "session", "start_time",
        "duration_minutes", "notes")})


def _resolution(r) -> Resolution:
    return Resolution(**{k: r[k] for k in (
        "resolution_id", "student_id", "season", "year", "exam_date",
        "session", "method", "moved_timetable_id", "moved_to_date",
        "moved_to_session", "moved_to_time", "supervisor", "notes",
        "recorded_by", "recorded_at")})


# ── Timetable ───────────────────────────────────────────────────────

def save_paper(data: dict[str, Any], *, timetable_id: int | None = None) -> Paper:
    """Add a paper to the timetable, or update one."""
    init_db()
    board = store.board(data.get("exam_board"))
    season, year = store.season_year(data.get("season"), data.get("year"))
    comp = (store.text(data.get("component_code"), "Component code", limit=24,
                       required=True) or "").upper()
    session = store.choice(data.get("session"), "Session", SESSIONS)
    start = store.time(data.get("start_time"), "Start time") or SESSION_START[session]
    duration = store.integer(data.get("duration_minutes"), "Duration (minutes)",
                             lo=1, hi=600)
    entry_code = (store.text(data.get("entry_code"), "Entry code", limit=24) or "").upper()
    title = store.text(data.get("title"), "Title", limit=120)
    if duration is None or not entry_code or not title:
        # Fill gaps from the component catalogue.
        from education_system.systems.sixth_form.domain.assessment.exams_office import (
            entry_admin,
        )
        comp_row = entry_admin.get_component(comp, board)
        if comp_row:
            duration = duration or comp_row.duration_minutes
            entry_code = entry_code or comp_row.entry_code
            title = title or comp_row.component_title
        entry_code = entry_code or entry_admin.derive_entry_code(comp) or ""
    if duration is None:
        raise ValidationError("Duration (minutes) is required")
    exam_date = store.date(data.get("exam_date"), "Exam date", required=True)
    if is_contingency(season, year, exam_date, session):
        raise ValidationError(
            f"{exam_date} {session} is the {season} {year} contingency session — "
            "nothing else may be timetabled on it")
    vals = (board, season, year, entry_code or None, comp, title, exam_date,
            session, start, duration, store.text(data.get("notes"), "Notes", limit=500))
    try:
        with store.connect() as conn:
            if timetable_id is None:
                cur = conn.execute(
                    """INSERT INTO exams_timetable
                           (exam_board, season, year, entry_code, component_code,
                            title, exam_date, session, start_time,
                            duration_minutes, notes)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", vals)
                timetable_id = int(cur.lastrowid)
            else:
                conn.execute(
                    """UPDATE exams_timetable SET exam_board = ?, season = ?,
                           year = ?, entry_code = ?, component_code = ?,
                           title = ?, exam_date = ?, session = ?,
                           start_time = ?, duration_minutes = ?, notes = ?
                       WHERE timetable_id = ?""", (*vals, timetable_id))
            conn.commit()
    except store.IntegrityError as e:
        raise ValidationError(
            f"{comp} is already timetabled for {board} {season} {year}") from e
    out = get_paper(timetable_id)
    assert out is not None
    logger.info("Timetabled %s", out.label)
    return out


def get_paper(timetable_id: int) -> Paper | None:
    init_db()
    with store.connect() as conn:
        r = conn.execute("SELECT * FROM exams_timetable WHERE timetable_id = ?",
                         (timetable_id,)).fetchone()
    return _paper(r) if r else None


def list_papers(*, season: str | None = None, year: int | None = None,
                exam_board: str | None = None, date_from: str | None = None,
                date_to: str | None = None,
                component_code: str | None = None) -> list[Paper]:
    init_db()
    clauses, args = [], []
    if season:
        clauses.append("season = ?")
        args.append(season)
    if year is not None:
        clauses.append("year = ?")
        args.append(int(year))
    if exam_board:
        clauses.append("exam_board = ?")
        args.append(store.board(exam_board))
    if date_from:
        clauses.append("exam_date >= ?")
        args.append(store.date(date_from, "From"))
    if date_to:
        clauses.append("exam_date <= ?")
        args.append(store.date(date_to, "To"))
    if component_code:
        clauses.append("component_code = ?")
        args.append(component_code.strip().upper())
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with store.connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM exams_timetable {where} "
            "ORDER BY exam_date, session, start_time, component_code", args).fetchall()
    return [_paper(r) for r in rows]


def delete_paper(timetable_id: int) -> bool:
    init_db()
    with store.connect() as conn:
        cur = conn.execute("DELETE FROM exams_timetable WHERE timetable_id = ?",
                           (timetable_id,))
        conn.commit()
    return bool(cur.rowcount)


def entries_for_paper(paper: Paper) -> list:
    """The live (not withdrawn) entries the paper's candidates come from."""
    from education_system.systems.sixth_form.domain.assessment.exam_entries import (
        exam_entries as _entries,
    )
    return [e for e in _entries.list_entries(
                paper_code=paper.component_code, season=paper.season,
                year=paper.year, exam_board=paper.exam_board)
            if e.status != "Withdrawn"]


def unscheduled_entries(season: str, year: int) -> list[tuple[str, str, int]]:
    """Component codes with entries but no timetable row: (board, code, count)."""
    from education_system.systems.sixth_form.domain.assessment.exam_entries import (
        exam_entries as _entries,
    )
    timetabled = {(p.exam_board, p.component_code)
                  for p in list_papers(season=season, year=year)}
    counts: dict[tuple[str, str], int] = {}
    for e in _entries.list_entries(season=season, year=year):
        if e.status == "Withdrawn":
            continue
        from education_system.systems.sixth_form.domain.assessment.exams_office.boards import (
            normalise_board,
        )
        key = (normalise_board(e.exam_board) or e.exam_board, e.paper_code)
        if key not in timetabled:
            counts[key] = counts.get(key, 0) + 1
    return [(b, c, n) for (b, c), n in sorted(counts.items())]


# ── Contingency days ────────────────────────────────────────────────

def save_contingency(data: dict[str, Any]) -> ContingencyDay:
    init_db()
    season, year = store.season_year(data.get("season"), data.get("year"))
    exam_date = store.date(data.get("exam_date"), "Contingency date", required=True)
    session = store.choice(data.get("session"), "Session", SESSIONS, required=False)
    clashes = [p for p in list_papers(season=season, year=year)
               if p.exam_date == exam_date and (session is None or p.session == session)]
    if clashes:
        raise ValidationError(
            f"{len(clashes)} paper(s) are already timetabled then, e.g. "
            f"{clashes[0].label}")
    try:
        with store.connect() as conn:
            cur = conn.execute(
                "INSERT INTO exams_contingency_days (season, year, exam_date, session, notes) "
                "VALUES (?, ?, ?, ?, ?)",
                (season, year, exam_date, session,
                 store.text(data.get("notes"), "Notes", limit=500)))
            conn.commit()
            r = conn.execute("SELECT * FROM exams_contingency_days WHERE contingency_id = ?",
                             (cur.lastrowid,)).fetchone()
    except store.IntegrityError as e:
        raise ValidationError("That contingency session is already recorded") from e
    return ContingencyDay(**dict(r))


def list_contingency(*, season: str | None = None,
                     year: int | None = None) -> list[ContingencyDay]:
    init_db()
    clauses, args = [], []
    if season:
        clauses.append("season = ?")
        args.append(season)
    if year is not None:
        clauses.append("year = ?")
        args.append(int(year))
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with store.connect() as conn:
        rows = conn.execute(f"SELECT * FROM exams_contingency_days {where} "
                            "ORDER BY exam_date, session", args).fetchall()
    return [ContingencyDay(**dict(r)) for r in rows]


def delete_contingency(contingency_id: int) -> bool:
    init_db()
    with store.connect() as conn:
        cur = conn.execute("DELETE FROM exams_contingency_days WHERE contingency_id = ?",
                           (contingency_id,))
        conn.commit()
    return bool(cur.rowcount)


def is_contingency(season: str, year: int, exam_date: str, session: str | None) -> bool:
    for c in list_contingency(season=season, year=year):
        if c.exam_date == exam_date and (c.session is None or session is None
                                         or c.session == session):
            return True
    return False


# ── Candidate timetables and clashes ────────────────────────────────

def candidate_timetable(student_id: str, season: str, year: int) -> list[Paper]:
    """Every timetabled paper a candidate is entered for, in order."""
    from education_system.systems.sixth_form.domain.assessment.exam_entries import (
        exam_entries as _entries,
    )
    codes = {e.paper_code for e in _entries.list_entries(
        student_id=student_id, season=season, year=int(year)) if e.status != "Withdrawn"}
    return [p for p in list_papers(season=season, year=year) if p.component_code in codes]


def get_resolution(student_id: str, season: str, year: int, exam_date: str,
                   session: str) -> Resolution | None:
    init_db()
    with store.connect() as conn:
        r = conn.execute(
            "SELECT * FROM exams_clash_resolutions WHERE student_id = ? AND season = ? "
            "AND year = ? AND exam_date = ? AND session = ?",
            (student_id, season, int(year), exam_date, session)).fetchone()
    return _resolution(r) if r else None


def list_resolutions(*, season: str | None = None, year: int | None = None,
                     student_id: str | None = None) -> list[Resolution]:
    init_db()
    clauses, args = [], []
    if season:
        clauses.append("season = ?")
        args.append(season)
    if year is not None:
        clauses.append("year = ?")
        args.append(int(year))
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with store.connect() as conn:
        rows = conn.execute(f"SELECT * FROM exams_clash_resolutions {where} "
                            "ORDER BY exam_date, session, student_id", args).fetchall()
    return [_resolution(r) for r in rows]


def candidate_clashes(season: str, year: int, *,
                      unresolved_only: bool = False) -> list[Clash]:
    """Every candidate entered for 2+ papers in one date + session."""
    from education_system.systems.sixth_form.domain.assessment.exam_entries import (
        exam_entries as _entries,
    )
    from education_system.systems.sixth_form.domain.assessment.exams_office import (
        access_arrangements as _access,
    )
    season, year = store.season_year(season, year)
    papers = list_papers(season=season, year=year)
    by_code: dict[str, list[Paper]] = {}
    for p in papers:
        by_code.setdefault(p.component_code, []).append(p)
    slots: dict[tuple[str, str, str], list[Paper]] = {}
    for e in _entries.list_entries(season=season, year=year):
        if e.status == "Withdrawn":
            continue
        for p in by_code.get(e.paper_code, []):
            slots.setdefault((e.student_id, p.exam_date, p.session), []).append(p)
    names = store.student_names()
    resolutions = {(r.student_id, r.exam_date, r.session): r
                   for r in list_resolutions(season=season, year=year)}
    out: list[Clash] = []
    extra_cache: dict[str, int] = {}
    for (sid, d, sess), ps in sorted(slots.items(), key=lambda kv: (kv[0][1], kv[0][2], kv[0][0])):
        unique = {p.timetable_id: p for p in ps}
        if len(unique) < 2:
            continue
        res = resolutions.get((sid, d, sess))
        if unresolved_only and res is not None:
            continue
        if sid not in extra_cache:
            try:
                extra_cache[sid] = _access.for_student(sid).extra_time_pct
            except Exception:
                logger.exception("Could not read access arrangements for %s", sid)
                extra_cache[sid] = 0
        out.append(Clash(sid, names.get(sid, "(unknown)"), d, sess,
                         sorted(unique.values(), key=lambda p: p.start_time),
                         res, extra_cache[sid]))
    return out


def resolve_clash(data: dict[str, Any]) -> Resolution:
    """Record how a candidate's clash will be handled (upsert)."""
    init_db()
    sid = store.student(data.get("student_id"))
    season, year = store.season_year(data.get("season"), data.get("year"))
    exam_date = store.date(data.get("exam_date"), "Clash date", required=True)
    session = store.choice(data.get("session"), "Session", SESSIONS)
    method = store.choice(data.get("method"), "Method", RESOLUTION_METHODS)
    clash = next((c for c in candidate_clashes(season, year)
                  if c.student_id == sid and c.exam_date == exam_date
                  and c.session == session), None)
    if clash is None:
        raise ValidationError(f"{sid} has no clash on {exam_date} {session}")
    moved_id = store.integer(data.get("moved_timetable_id"), "Paper moved")
    if moved_id is not None and moved_id not in {p.timetable_id for p in clash.papers}:
        raise ValidationError("The paper moved must be one of the clashing papers")
    to_date = store.date(data.get("moved_to_date"), "Moved to date")
    to_session = store.choice(data.get("moved_to_session"), "Moved to session",
                              SESSIONS, required=False)
    to_time = store.time(data.get("moved_to_time"), "Moved to time")
    if moved_id is not None and not to_date and "consecutively" not in method:
        raise ValidationError("Give the date the paper is moved to")
    if to_date and to_session and moved_id is not None:
        # The moved paper must not land on another clash for this candidate.
        others = [p for p in candidate_timetable(sid, season, year)
                  if p.exam_date == to_date and p.session == to_session
                  and p.timetable_id != moved_id]
        if others and "Overnight" not in method:
            raise ValidationError(
                f"{sid} already sits {others[0].component_code} in {to_date} "
                f"{to_session}")
    if to_session and not to_time:
        to_time = SESSION_START[to_session]
    vals = (sid, season, year, exam_date, session, method, moved_id, to_date,
            to_session, to_time, store.text(data.get("supervisor"), "Supervisor", limit=120),
            store.text(data.get("notes"), "Notes", limit=1000), store.actor())
    with store.connect() as conn:
        conn.execute(
            """INSERT INTO exams_clash_resolutions
                   (student_id, season, year, exam_date, session, method,
                    moved_timetable_id, moved_to_date, moved_to_session,
                    moved_to_time, supervisor, notes, recorded_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(student_id, season, year, exam_date, session) DO UPDATE SET
                   method = excluded.method,
                   moved_timetable_id = excluded.moved_timetable_id,
                   moved_to_date = excluded.moved_to_date,
                   moved_to_session = excluded.moved_to_session,
                   moved_to_time = excluded.moved_to_time,
                   supervisor = excluded.supervisor,
                   notes = excluded.notes,
                   recorded_by = excluded.recorded_by,
                   recorded_at = datetime('now')""", vals)
        conn.commit()
    out = get_resolution(sid, season, year, exam_date, session)
    assert out is not None
    logger.info("Clash for %s on %s %s resolved: %s", sid, exam_date, session, method)
    return out


def delete_resolution(resolution_id: int) -> bool:
    init_db()
    with store.connect() as conn:
        cur = conn.execute("DELETE FROM exams_clash_resolutions WHERE resolution_id = ?",
                           (resolution_id,))
        conn.commit()
    return bool(cur.rowcount)


# ── Sittings from the timetable ─────────────────────────────────────

def create_sitting(timetable_id: int, *, room: str, populate: bool = True,
                   invigilator: str | None = None) -> Any:
    """Open an exam-room register for a timetabled paper and fill it.

    Candidates whose clash resolution moves this paper elsewhere are
    left out of this sitting (they sit it at the moved time).
    """
    from education_system.systems.sixth_form.domain.academics.attendance import (
        attendance_exams as _exams,
    )
    paper = get_paper(timetable_id)
    if paper is None:
        raise ValidationError(f"No timetabled paper #{timetable_id}")
    room = store.text(room, "Room", limit=60, required=True)
    sitting = _exams.create_sitting({
        "paper_code": paper.component_code, "paper_title": paper.title,
        "exam_board": paper.exam_board, "date": paper.exam_date,
        "start_time": paper.start_time, "end_time": paper.end_time,
        "room": room, "series": paper.season, "year": paper.year,
        "invigilator": invigilator, "timetable_id": paper.timetable_id,
    })
    if populate:
        moved = {r.student_id for r in list_resolutions(season=paper.season, year=paper.year)
                 if r.moved_timetable_id == paper.timetable_id and r.moved_to_date}
        _exams.populate_from_entries(sitting.sitting_id, exclude=moved)
    return _exams.get_sitting(sitting.sitting_id)
