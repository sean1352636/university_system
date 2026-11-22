"""Entry administration: entry codes, components, deadlines, fees, amendments.

A board entry is made against an *entry code* (the qualification or
"cash-in" code, e.g. Pearson 9MA0, AQA 7357, OCR H240). The papers a
candidate sits are its *components* (9MA0/01, 9MA0/02 ...). The
existing ``exam_entries`` table holds one row per component sat; the
``entry_code`` column added to it ties those rows back to the option
they belong to, and the catalogue here lists which components make up
each entry code so a whole option can be entered in one step.

Deadlines and fees are per board and series. An entry made after the
entry deadline attracts the late fee; after the final late deadline the
very-late fee. Amendments (changing a component or tier) and
withdrawals carry their own fee once their deadline has passed. Every
create, change, withdrawal and deletion of an entry is written to the
amendment history by hooks in :mod:`exam_entries`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from education_system.systems.sixth_form.domain.assessment.exams_office import store
from education_system.systems.sixth_form.domain.assessment.exams_office.store import (
    ValidationError,
)

logger = logging.getLogger(__name__)

# Fee bands an entry falls into, by the date it was made.
BAND_STANDARD = "Standard"
BAND_LATE = "Late"
BAND_VERY_LATE = "Very late"
FEE_BANDS: tuple[str, ...] = (BAND_STANDARD, BAND_LATE, BAND_VERY_LATE)

AMENDMENT_ACTIONS: tuple[str, ...] = (
    "Entered", "Amended", "Withdrawn", "Reinstated", "Deleted")

DEADLINE_KINDS: tuple[str, ...] = (
    "Entry deadline", "Final late deadline", "Amendment deadline",
    "Withdrawal deadline")

# Fields whose change counts as an amendment the board must be told of.
_BOARD_FIELDS: tuple[str, ...] = (
    "paper_code", "entry_code", "tier", "exam_board", "season", "year",
    "candidate_no")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS exams_entry_components (
    component_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    exam_board       TEXT NOT NULL,
    entry_code       TEXT NOT NULL,
    entry_title      TEXT,
    qualification_type TEXT,
    component_code   TEXT NOT NULL,
    component_title  TEXT,
    duration_minutes INTEGER,
    entry_fee        REAL,
    is_active        INTEGER NOT NULL DEFAULT 1,
    notes            TEXT,
    UNIQUE(exam_board, entry_code, component_code)
);
CREATE INDEX IF NOT EXISTS idx_exams_comp_entry
    ON exams_entry_components(entry_code);

CREATE TABLE IF NOT EXISTS exams_series_deadlines (
    deadline_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    exam_board           TEXT NOT NULL,
    season               TEXT NOT NULL,
    year                 INTEGER NOT NULL,
    entry_deadline       TEXT NOT NULL,
    final_late_deadline  TEXT,
    late_fee             REAL,
    very_late_fee        REAL,
    amendment_deadline   TEXT,
    amendment_fee        REAL,
    withdrawal_deadline  TEXT,
    withdrawal_fee       REAL,
    notes                TEXT,
    updated_at           TEXT DEFAULT (datetime('now')),
    UNIQUE(exam_board, season, year)
);

CREATE TABLE IF NOT EXISTS exams_entry_amendments (
    amendment_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_id      INTEGER,
    student_id    TEXT NOT NULL,
    exam_board    TEXT,
    paper_code    TEXT,
    season        TEXT,
    year          INTEGER,
    action        TEXT NOT NULL,
    changes       TEXT,
    fee           REAL,
    fee_band      TEXT,
    reason        TEXT,
    amended_by    TEXT,
    amended_at    TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (entry_id) REFERENCES exam_entries(entry_id)
        ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_exams_amend_entry
    ON exams_entry_amendments(entry_id);
CREATE INDEX IF NOT EXISTS idx_exams_amend_student
    ON exams_entry_amendments(student_id);
"""


def init_db() -> None:
    store.ensure("entry_admin", _SCHEMA)


# ── Shapes ──────────────────────────────────────────────────────────

@dataclass
class Component:
    component_id: int
    exam_board: str
    entry_code: str
    entry_title: str | None
    qualification_type: str | None
    component_code: str
    component_title: str | None
    duration_minutes: int | None
    entry_fee: float | None
    is_active: bool
    notes: str | None


@dataclass
class SeriesDeadlines:
    deadline_id: int
    exam_board: str
    season: str
    year: int
    entry_deadline: str
    final_late_deadline: str | None
    late_fee: float | None
    very_late_fee: float | None
    amendment_deadline: str | None
    amendment_fee: float | None
    withdrawal_deadline: str | None
    withdrawal_fee: float | None
    notes: str | None


@dataclass
class Amendment:
    amendment_id: int
    entry_id: int | None
    student_id: str
    exam_board: str | None
    paper_code: str | None
    season: str | None
    year: int | None
    action: str
    changes: str | None
    fee: float | None
    fee_band: str | None
    reason: str | None
    amended_by: str | None
    amended_at: str


@dataclass
class CalendarItem:
    date: str
    exam_board: str
    season: str
    year: int
    kind: str
    fee: float | None
    days_left: int


@dataclass
class FeeLine:
    entry_id: int | None
    student_id: str
    paper_code: str | None
    what: str            # "Late entry", "Amendment", "Withdrawal" ...
    band: str | None
    fee: float
    on_date: str


def _component(r) -> Component:
    return Component(
        component_id=r["component_id"], exam_board=r["exam_board"],
        entry_code=r["entry_code"], entry_title=r["entry_title"],
        qualification_type=r["qualification_type"],
        component_code=r["component_code"],
        component_title=r["component_title"],
        duration_minutes=r["duration_minutes"], entry_fee=r["entry_fee"],
        is_active=bool(r["is_active"]), notes=r["notes"])


def _deadlines(r) -> SeriesDeadlines:
    return SeriesDeadlines(**{k: r[k] for k in (
        "deadline_id", "exam_board", "season", "year", "entry_deadline",
        "final_late_deadline", "late_fee", "very_late_fee",
        "amendment_deadline", "amendment_fee", "withdrawal_deadline",
        "withdrawal_fee", "notes")})


def _amendment(r) -> Amendment:
    return Amendment(**{k: r[k] for k in (
        "amendment_id", "entry_id", "student_id", "exam_board", "paper_code",
        "season", "year", "action", "changes", "fee", "fee_band", "reason",
        "amended_by", "amended_at")})


def _code(value: Any, label: str) -> str:
    from education_system.systems.sixth_form.domain.assessment.exam_entries import (
        exam_entries as _entries,
    )
    s = (store.text(value, label, limit=24, required=True) or "").upper()
    if not _entries._PAPER_CODE_RE.match(s):
        raise ValidationError(
            f"{label} must be 2-24 chars: uppercase letters, digits, . / -")
    return s


def derive_entry_code(paper_code: str | None) -> str | None:
    """The entry code a component code belongs to (``9MA0/01`` -> ``9MA0``).

    Uses the catalogue first; otherwise the part before the first ``/``.
    """
    code = (paper_code or "").strip().upper()
    if not code:
        return None
    try:
        init_db()
        with store.connect() as conn:
            r = conn.execute(
                "SELECT entry_code FROM exams_entry_components "
                "WHERE component_code = ? ORDER BY is_active DESC LIMIT 1",
                (code,)).fetchone()
        if r:
            return r["entry_code"]
    except Exception:
        logger.exception("derive_entry_code catalogue lookup failed")
    return code.split("/", 1)[0] if "/" in code else code


# ── Component catalogue ─────────────────────────────────────────────

def save_component(data: dict[str, Any]) -> Component:
    """Add or update one component of an entry code."""
    init_db()
    board = store.board(data.get("exam_board"))
    entry_code = _code(data.get("entry_code"), "Entry code")
    comp_code = _code(data.get("component_code"), "Component code")
    qual = store.text(data.get("qualification_type"), "Qualification type", limit=60)
    if qual:
        from education_system.systems.sixth_form.domain.academics.qualifications import (
            grade_scales,
        )
        if qual not in grade_scales.QUALIFICATION_TYPES:
            raise ValidationError(
                "Qualification type must be one of: "
                + ", ".join(grade_scales.QUALIFICATION_TYPES))
    row = (board, entry_code,
           store.text(data.get("entry_title"), "Entry title", limit=120),
           qual, comp_code,
           store.text(data.get("component_title"), "Component title", limit=120),
           store.integer(data.get("duration_minutes"), "Duration (minutes)", lo=1, hi=600),
           store.money(data.get("entry_fee"), "Entry fee"),
           store.flag(data.get("is_active", True)),
           store.text(data.get("notes"), "Notes", limit=500))
    with store.connect() as conn:
        conn.execute(
            """INSERT INTO exams_entry_components
                   (exam_board, entry_code, entry_title, qualification_type,
                    component_code, component_title, duration_minutes,
                    entry_fee, is_active, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(exam_board, entry_code, component_code) DO UPDATE SET
                   entry_title = excluded.entry_title,
                   qualification_type = excluded.qualification_type,
                   component_title = excluded.component_title,
                   duration_minutes = excluded.duration_minutes,
                   entry_fee = excluded.entry_fee,
                   is_active = excluded.is_active,
                   notes = excluded.notes""", row)
        conn.commit()
        r = conn.execute(
            "SELECT * FROM exams_entry_components WHERE exam_board = ? "
            "AND entry_code = ? AND component_code = ?",
            (board, entry_code, comp_code)).fetchone()
    logger.info("Saved component %s of %s (%s)", comp_code, entry_code, board)
    return _component(r)


def list_components(*, exam_board: str | None = None,
                    entry_code: str | None = None,
                    active_only: bool = False) -> list[Component]:
    init_db()
    clauses, args = [], []
    if exam_board:
        clauses.append("exam_board = ?")
        args.append(store.board(exam_board))
    if entry_code:
        clauses.append("entry_code = ?")
        args.append(entry_code.strip().upper())
    if active_only:
        clauses.append("is_active = 1")
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with store.connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM exams_entry_components {where} "
            "ORDER BY exam_board, entry_code, component_code", args).fetchall()
    return [_component(r) for r in rows]


def get_component(component_code: str, exam_board: str | None = None) -> Component | None:
    rows = [c for c in list_components(exam_board=exam_board)
            if c.component_code == (component_code or "").strip().upper()]
    return rows[0] if rows else None


def delete_component(component_id: int) -> bool:
    init_db()
    with store.connect() as conn:
        cur = conn.execute(
            "DELETE FROM exams_entry_components WHERE component_id = ?",
            (component_id,))
        conn.commit()
    return bool(cur.rowcount)


def enter_for_option(*, student_id: str, exam_board: str, entry_code: str,
                     subject: str, season: str, year: int,
                     candidate_no: str | None = None, tier: str | None = None,
                     notes: str | None = None) -> list:
    """Enter a candidate for every active component of an entry code.

    Components the candidate is already entered for are left alone.
    Returns the entries created.
    """
    from education_system.systems.sixth_form.domain.assessment.exam_entries import (
        exam_entries as _entries,
    )
    from education_system.systems.sixth_form.domain.assessment.exams_office import (
        candidates,
    )
    board = store.board(exam_board)
    code = _code(entry_code, "Entry code")
    comps = list_components(exam_board=board, entry_code=code, active_only=True)
    if not comps:
        raise ValidationError(
            f"No components recorded for {code} ({board}) — add them to the "
            "component catalogue first")
    season, year = store.season_year(season, year)
    cand = candidate_no or candidates.candidate_number(student_id)
    existing = {e.paper_code for e in _entries.list_entries(
        student_id=student_id, season=season, year=year)}
    created = []
    for comp in comps:
        if comp.component_code in existing:
            continue
        created.append(_entries.create_entry({
            "student_id": student_id, "subject": subject,
            "exam_board": board, "paper_code": comp.component_code,
            "paper_title": comp.component_title, "entry_code": code,
            "season": season, "year": year, "candidate_no": cand,
            "tier": tier, "fee": comp.entry_fee, "notes": notes,
        }))
    logger.info("Entered %s for %d component(s) of %s", student_id,
                len(created), code)
    return created


# ── Deadlines and fees ──────────────────────────────────────────────

def save_deadlines(data: dict[str, Any]) -> SeriesDeadlines:
    """Record one board's deadlines and fees for a series (upsert)."""
    init_db()
    board = store.board(data.get("exam_board"))
    season, year = store.season_year(data.get("season"), data.get("year"))
    entry = store.date(data.get("entry_deadline"), "Entry deadline", required=True)
    final = store.date(data.get("final_late_deadline"), "Final late deadline")
    if final and final < entry:
        raise ValidationError("The final late deadline cannot be before the entry deadline")
    vals = (board, season, year, entry, final,
            store.money(data.get("late_fee"), "Late fee"),
            store.money(data.get("very_late_fee"), "Very late fee"),
            store.date(data.get("amendment_deadline"), "Amendment deadline"),
            store.money(data.get("amendment_fee"), "Amendment fee"),
            store.date(data.get("withdrawal_deadline"), "Withdrawal deadline"),
            store.money(data.get("withdrawal_fee"), "Withdrawal fee"),
            store.text(data.get("notes"), "Notes", limit=500))
    with store.connect() as conn:
        conn.execute(
            """INSERT INTO exams_series_deadlines
                   (exam_board, season, year, entry_deadline,
                    final_late_deadline, late_fee, very_late_fee,
                    amendment_deadline, amendment_fee, withdrawal_deadline,
                    withdrawal_fee, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(exam_board, season, year) DO UPDATE SET
                   entry_deadline = excluded.entry_deadline,
                   final_late_deadline = excluded.final_late_deadline,
                   late_fee = excluded.late_fee,
                   very_late_fee = excluded.very_late_fee,
                   amendment_deadline = excluded.amendment_deadline,
                   amendment_fee = excluded.amendment_fee,
                   withdrawal_deadline = excluded.withdrawal_deadline,
                   withdrawal_fee = excluded.withdrawal_fee,
                   notes = excluded.notes,
                   updated_at = datetime('now')""", vals)
        conn.commit()
    out = get_deadlines(board, season, year)
    assert out is not None
    logger.info("Saved deadlines for %s %s %d", board, season, year)
    return out


def get_deadlines(exam_board: str, season: str, year: int) -> SeriesDeadlines | None:
    init_db()
    from education_system.systems.sixth_form.domain.assessment.exams_office.boards import (
        stored_names,
    )
    names = stored_names(exam_board)
    marks = ",".join("?" * len(names))
    with store.connect() as conn:
        r = conn.execute(
            f"SELECT * FROM exams_series_deadlines WHERE exam_board IN ({marks}) "
            "AND season = ? AND year = ?", (*names, season, int(year))).fetchone()
    return _deadlines(r) if r else None


def list_deadlines(*, year: int | None = None) -> list[SeriesDeadlines]:
    init_db()
    sql = "SELECT * FROM exams_series_deadlines"
    args: list[Any] = []
    if year is not None:
        sql += " WHERE year = ?"
        args.append(int(year))
    with store.connect() as conn:
        rows = conn.execute(sql + " ORDER BY year DESC, season, exam_board",
                            args).fetchall()
    return [_deadlines(r) for r in rows]


def delete_deadlines(deadline_id: int) -> bool:
    init_db()
    with store.connect() as conn:
        cur = conn.execute(
            "DELETE FROM exams_series_deadlines WHERE deadline_id = ?", (deadline_id,))
        conn.commit()
    return bool(cur.rowcount)


def fee_band(exam_board: str, season: str, year: int,
             on_date: str | None = None) -> tuple[str, float]:
    """Which fee band an entry made on *on_date* falls in, and its late fee.

    Returns ``(band, late_fee)``; the late fee is 0 for a standard entry
    or when no deadlines are recorded for the series.
    """
    when = store.date(on_date, "Date") or store.today()
    d = get_deadlines(exam_board, season, year)
    if d is None or when <= d.entry_deadline:
        return BAND_STANDARD, 0.0
    if d.final_late_deadline and when > d.final_late_deadline:
        return BAND_VERY_LATE, float(d.very_late_fee or d.late_fee or 0.0)
    return BAND_LATE, float(d.late_fee or 0.0)


def late_fee_calculator(*, season: str, year: int, exam_board: str | None = None,
                        as_of: str | None = None) -> list[FeeLine]:
    """Every late, amendment and withdrawal fee owed for a series.

    Late fees come from the date each entry was made against that
    board's deadlines; amendment and withdrawal fees from the amendment
    history (each logged change after its deadline).
    """
    init_db()
    season, year = store.season_year(season, year)
    cutoff = store.date(as_of, "As of") or store.today()
    from education_system.systems.sixth_form.domain.assessment.exam_entries import (
        exam_entries as _entries,
    )
    lines: list[FeeLine] = []
    for e in _entries.list_entries(season=season, year=year,
                                   exam_board=exam_board or None):
        made = (e.created_at or "")[:10] or cutoff
        if made > cutoff:
            continue
        band, fee = fee_band(e.exam_board, season, year, made)
        if band != BAND_STANDARD and fee:
            lines.append(FeeLine(e.entry_id, e.student_id, e.paper_code,
                                 f"{band} entry", band, fee, made))
    for a in list_amendments(season=season, year=year, exam_board=exam_board):
        if a.fee and a.action in ("Amended", "Withdrawn") and a.amended_at[:10] <= cutoff:
            lines.append(FeeLine(a.entry_id, a.student_id, a.paper_code,
                                 "Amendment" if a.action == "Amended" else "Withdrawal",
                                 a.fee_band, float(a.fee), a.amended_at[:10]))
    lines.sort(key=lambda f: (f.on_date, f.student_id))
    return lines


def deadline_calendar(*, year: int | None = None, from_date: str | None = None,
                      to_date: str | None = None) -> list[CalendarItem]:
    """Every recorded deadline as dated items, soonest first."""
    import datetime as _dt
    start = store.date(from_date, "From")
    end = store.date(to_date, "To")
    today = _dt.date.fromisoformat(store.today())
    items: list[CalendarItem] = []
    for d in list_deadlines(year=year):
        for kind, when, fee in (
            ("Entry deadline", d.entry_deadline, None),
            ("Final late deadline", d.final_late_deadline, d.very_late_fee),
            ("Amendment deadline", d.amendment_deadline, d.amendment_fee),
            ("Withdrawal deadline", d.withdrawal_deadline, d.withdrawal_fee),
        ):
            if not when:
                continue
            if (start and when < start) or (end and when > end):
                continue
            if kind == "Entry deadline":
                fee = d.late_fee   # what missing it costs
            items.append(CalendarItem(
                when, d.exam_board, d.season, d.year, kind, fee,
                (_dt.date.fromisoformat(when) - today).days))
    items.sort(key=lambda i: (i.date, i.exam_board, i.kind))
    return items


# ── Amendment history (fed by exam_entries hooks) ───────────────────

def _change_fee(entry, action: str, on_date: str) -> tuple[float | None, str | None]:
    d = get_deadlines(entry.exam_board, entry.season, entry.year)
    if d is None:
        return None, None
    if action == "Withdrawn":
        if d.withdrawal_deadline and on_date > d.withdrawal_deadline:
            return d.withdrawal_fee, "After withdrawal deadline"
        return None, None
    if action == "Amended":
        if d.amendment_deadline and on_date > d.amendment_deadline:
            return d.amendment_fee, "After amendment deadline"
    return None, None


def log_amendment(entry, action: str, *, changes: str | None = None,
                  fee: float | None = None, band: str | None = None,
                  reason: str | None = None, actor: str | None = None) -> Amendment:
    init_db()
    if action not in AMENDMENT_ACTIONS:
        raise ValidationError(f"Action must be one of: {', '.join(AMENDMENT_ACTIONS)}")
    with store.connect() as conn:
        cur = conn.execute(
            """INSERT INTO exams_entry_amendments
                   (entry_id, student_id, exam_board, paper_code, season, year,
                    action, changes, fee, fee_band, reason, amended_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (None if action == "Deleted" else entry.entry_id, entry.student_id,
             entry.exam_board, entry.paper_code, entry.season, entry.year,
             action, changes, fee, band, reason, store.actor(actor)))
        conn.commit()
        r = conn.execute("SELECT * FROM exams_entry_amendments WHERE amendment_id = ?",
                         (cur.lastrowid,)).fetchone()
    return _amendment(r)


def on_entry_created(entry) -> tuple[str, float]:
    """Hook: log the entry and work out its fee band. Returns (band, fee)."""
    band, fee = fee_band(entry.exam_board, entry.season, entry.year,
                         (entry.created_at or "")[:10] or None)
    log_amendment(entry, "Entered", fee=fee or None, band=band,
                  changes=f"Entered for {entry.paper_code}")
    return band, fee


def on_entry_updated(before, after, *, reason: str | None = None) -> Amendment | None:
    """Hook: log what changed between two versions of an entry."""
    changed = [f for f in (*_BOARD_FIELDS, "status", "fee", "notes", "subject",
                           "paper_title")
               if getattr(before, f, None) != getattr(after, f, None)]
    if not changed:
        return None
    if before.status != "Withdrawn" and after.status == "Withdrawn":
        action = "Withdrawn"
    elif before.status == "Withdrawn" and after.status != "Withdrawn":
        action = "Reinstated"
    else:
        action = "Amended"
    desc = "; ".join(f"{f}: {getattr(before, f, None) or '—'} → "
                     f"{getattr(after, f, None) or '—'}" for f in changed)
    fee, band = (None, None)
    # Only board-facing changes cost money; a note or our own fee field does not.
    if action == "Withdrawn" or any(f in _BOARD_FIELDS for f in changed):
        fee, band = _change_fee(after, action, store.today())
    return log_amendment(after, action, changes=desc, fee=fee, band=band,
                         reason=reason)


def on_entry_deleted(entry) -> None:
    log_amendment(entry, "Deleted",
                  changes=f"Entry #{entry.entry_id} for {entry.paper_code} deleted")


def list_amendments(*, entry_id: int | None = None, student_id: str | None = None,
                    season: str | None = None, year: int | None = None,
                    exam_board: str | None = None,
                    action: str | None = None) -> list[Amendment]:
    init_db()
    clauses, args = [], []
    if entry_id is not None:
        clauses.append("entry_id = ?")
        args.append(int(entry_id))
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id.strip())
    if season:
        clauses.append("season = ?")
        args.append(season)
    if year is not None:
        clauses.append("year = ?")
        args.append(int(year))
    if exam_board:
        from education_system.systems.sixth_form.domain.assessment.exams_office.boards import (
            stored_names,
        )
        names = stored_names(exam_board)
        clauses.append(f"exam_board IN ({','.join('?' * len(names))})")
        args.extend(names)
    if action:
        clauses.append("action = ?")
        args.append(action)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with store.connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM exams_entry_amendments {where} "
            "ORDER BY amended_at DESC, amendment_id DESC", args).fetchall()
    return [_amendment(r) for r in rows]
