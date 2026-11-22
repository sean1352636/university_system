"""Exam entries: registering pupils with the exam boards for real exams.

Exam centre
    The school's centre number, name and exams officer (one row). The centre
    number goes on every board file.

Series
    A sitting of the real exams ("June 2027"): season, year, the board's
    **entry deadline** (standard fees up to and including it), the **late
    deadline** (late fees up to it; after it no new entries or tier changes
    can be made) and results day. Open -> Closed -> Archived (and back a
    step). Entries change only while the series is Open.

Specifications
    The qualification catalogue: board, specification code, title,
    qualification, whether it is tiered, the entry codes (one code, or a
    Foundation and a Higher code), the standard fee and the late fee. They
    can be built from the board and spec code already on each subject.

Candidates
    Each pupil gets one four-digit candidate number at this centre (kept for
    every series) and optionally their 13-character UCI.

Entries
    One row per pupil per specification per series, with tier, status, fee,
    who pays (school or parent, e.g. a resit) and notes. Status flow (the old
    names are kept):

    * **Provisional** - being put together; never sent to the board;
    * **Final** - confirmed; goes in the next board file;
    * **Withdrawn** - a Final entry taken out; the board is told;
    * **Cancelled** - a Provisional entry dropped; never sent.

    Moves: Provisional -> Final / Cancelled, Final -> Withdrawn (or back to
    Provisional while it has never been sent), Withdrawn -> Final,
    Cancelled -> Provisional. A Final entry needs a candidate number and, on
    a tiered specification, Foundation or Higher.

Fees
    An entry made Final up to the entry deadline is charged the standard fee;
    after it, the late fee (and is marked late). A Final entry withdrawn by
    the entry deadline is refunded (fee 0); after it the fee stands. A fee
    typed in by hand is kept as typed.

Board files
    A CSV per board of the entries the board hasn't been told about yet -
    new Final entries, changed tiers ("Amend") and withdrawals - stamped as
    sent once written. Sending everything again is allowed (a full file).

Statements of entry
    Each candidate's confirmed entries, candidate number and access
    arrangements, e-mailed to the pupil's school address and to their
    contacts, and shown in the pupil and parent portal.

Who may change things
    The exams officer (:data:`EXAM_ENTRY_EDITORS`) does everything; a teacher
    may set the tier of a provisional entry for a pupil they teach. Every
    change is audited.
"""

from __future__ import annotations

import csv
import datetime as _dt
import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from education_system.systems.secondary.modules.curriculum.domain import subjects as S
from education_system.systems.secondary.modules.curriculum.domain import teaching_groups as TG
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import EXAM_ENTRY_EDITORS, Principal
from education_system.systems.secondary.core.utilities.exports import safe_cell as _safe
from education_system.systems.secondary.core.academic_calendar.school_year import today as _today
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

MENU_LABEL = "Exam Entries"
EXAM_BOARDS: tuple[str, ...] = S.EXAM_BOARDS
DEFAULT_BOARD = "AQA"
QUALIFICATIONS: tuple[str, ...] = ("GCSE", "GCSE short course", "IGCSE", "Entry Level",
                                   "Functional Skills", "Other")
TIERS: tuple[str, ...] = ("Foundation", "Higher", "N/A")
DEFAULT_TIER = "N/A"
ENTRY_STATUSES: tuple[str, ...] = ("Provisional", "Final", "Withdrawn", "Cancelled")
DEFAULT_ENTRY_STATUS = "Provisional"
SEASONS: tuple[str, ...] = ("June", "November")
SERIES_STATUSES: tuple[str, ...] = ("Open", "Closed", "Archived")
FEE_PAYERS: tuple[str, ...] = ("School", "Parent")
MAX_FEE = 1000.0

_MOVES = {("Provisional", "Final"), ("Provisional", "Cancelled"), ("Final", "Withdrawn"),
          ("Final", "Provisional"), ("Withdrawn", "Final"), ("Cancelled", "Provisional")}
_SERIES_MOVES = {("Open", "Closed"), ("Closed", "Open"), ("Closed", "Archived"),
                 ("Archived", "Closed")}

_SPEC_RE = re.compile(r"^[A-Za-z0-9/\- ]{2,16}$")
_CODE_RE = re.compile(r"^[A-Za-z0-9/\-]{2,16}$")
_CAND_RE = re.compile(r"^\d{4}$")
_UCI_RE = re.compile(r"^[A-Z0-9]{13}$")
_CENTRE_RE = re.compile(r"^\d{5}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS exam_centre (
    centre_id        INTEGER PRIMARY KEY CHECK (centre_id = 1),
    centre_number    TEXT,
    centre_name      TEXT,
    officer_name     TEXT,
    officer_email    TEXT,
    updated_at       TEXT NOT NULL DEFAULT (datetime('now')),
    updated_by       TEXT
);
CREATE TABLE IF NOT EXISTS exam_series (
    series_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL UNIQUE COLLATE NOCASE,
    season          TEXT NOT NULL DEFAULT 'June',
    exam_year       INTEGER NOT NULL,
    entry_deadline  TEXT,
    late_deadline   TEXT,
    results_day     TEXT,
    status          TEXT NOT NULL DEFAULT 'Open'
                    CHECK (status IN ('Open', 'Closed', 'Archived')),
    notes           TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    created_by      TEXT,
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS exam_specs (
    spec_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_id       INTEGER NOT NULL REFERENCES subjects (subject_id),
    exam_board       TEXT NOT NULL,
    spec_code        TEXT NOT NULL,
    title            TEXT NOT NULL,
    qualification    TEXT NOT NULL DEFAULT 'GCSE',
    tiered           INTEGER NOT NULL DEFAULT 0,
    entry_code       TEXT,
    foundation_code  TEXT,
    higher_code      TEXT,
    fee              REAL,
    late_fee         REAL,
    is_active        INTEGER NOT NULL DEFAULT 1,
    notes            TEXT,
    created_at       TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at       TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (exam_board, spec_code)
);
CREATE TABLE IF NOT EXISTS exam_candidates (
    pupil_id          INTEGER PRIMARY KEY REFERENCES pupils (pupil_id) ON DELETE CASCADE,
    candidate_number  TEXT NOT NULL UNIQUE,
    uci               TEXT UNIQUE,
    assigned_by       TEXT,
    assigned_at       TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS exam_entries (
    entry_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    series_id     INTEGER NOT NULL REFERENCES exam_series (series_id),
    pupil_id      INTEGER NOT NULL REFERENCES pupils (pupil_id) ON DELETE CASCADE,
    spec_id       INTEGER NOT NULL REFERENCES exam_specs (spec_id),
    tier          TEXT NOT NULL DEFAULT 'N/A' CHECK (tier IN ('Foundation', 'Higher', 'N/A')),
    entry_status  TEXT NOT NULL DEFAULT 'Provisional'
                  CHECK (entry_status IN ('Provisional', 'Final', 'Withdrawn', 'Cancelled')),
    entry_date    TEXT NOT NULL DEFAULT (date('now')),
    fee           REAL,
    fee_manual    INTEGER NOT NULL DEFAULT 0,
    late          INTEGER NOT NULL DEFAULT 0,
    fee_payer     TEXT NOT NULL DEFAULT 'School' CHECK (fee_payer IN ('School', 'Parent')),
    resit         INTEGER NOT NULL DEFAULT 0,
    submitted_on  TEXT,
    sent_tier     TEXT,
    sent_status   TEXT,
    needs_resend  INTEGER NOT NULL DEFAULT 0,
    notes         TEXT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    created_by    TEXT,
    updated_at    TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (series_id, pupil_id, spec_id)
);
CREATE INDEX IF NOT EXISTS ix_exam_entries_pupil ON exam_entries (pupil_id);
CREATE INDEX IF NOT EXISTS ix_exam_entries_series ON exam_entries (series_id);
CREATE TABLE IF NOT EXISTS exam_entry_audit (
    audit_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    series_id  INTEGER,
    entry_id   INTEGER,
    pupil_id   INTEGER,
    action     TEXT NOT NULL,
    detail     TEXT,
    actor      TEXT NOT NULL,
    at         TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_exam_entry_audit_series ON exam_entry_audit (series_id);
"""

database.register_schema("exam_entries", _SCHEMA)

ValidationError = P.ValidationError
PermissionDenied = P.PermissionDenied
NotFound = P.NotFound


# ── Records ──────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Centre:
    centre_number: str | None = None
    centre_name: str | None = None
    officer_name: str | None = None
    officer_email: str | None = None
    updated_at: str | None = None
    updated_by: str | None = None


@dataclass(frozen=True)
class ExamSeries:
    series_id: int
    name: str
    season: str
    exam_year: int
    entry_deadline: str | None
    late_deadline: str | None
    results_day: str | None
    status: str
    notes: str | None
    created_at: str
    created_by: str | None
    updated_at: str

    @property
    def is_open(self) -> bool:
        return self.status == "Open"


@dataclass(frozen=True)
class Spec:
    spec_id: int
    subject_id: int
    exam_board: str
    spec_code: str
    title: str
    qualification: str
    tiered: bool
    entry_code: str | None
    foundation_code: str | None
    higher_code: str | None
    fee: float | None
    late_fee: float | None
    is_active: bool
    notes: str | None
    created_at: str
    updated_at: str
    subject_code: str = ""
    subject_name: str = ""

    @property
    def label(self) -> str:
        return f"{self.exam_board} {self.spec_code} {self.title}"

    def code_for(self, tier: str) -> str:
        if self.tiered and tier == "Foundation" and self.foundation_code:
            return self.foundation_code
        if self.tiered and tier == "Higher" and self.higher_code:
            return self.higher_code
        return self.entry_code or self.spec_code


@dataclass(frozen=True)
class Candidate:
    pupil_id: int
    candidate_number: str
    uci: str | None
    assigned_by: str | None
    assigned_at: str


@dataclass(frozen=True)
class ExamEntry:
    entry_id: int
    pupil_id: int
    subject_id: int
    exam_board: str
    spec_code: str | None
    tier: str
    candidate_number: str | None
    entry_status: str
    entry_date: str
    fee: float | None
    notes: str | None
    subject_code: str | None = None
    subject_name: str | None = None
    pupil_name: str | None = None
    pupil_year: int | None = None
    created_at: str | None = None
    updated_at: str | None = None
    series_id: int = 0
    series_name: str = ""
    spec_id: int = 0
    spec_title: str = ""
    qualification: str = ""
    tiered: bool = False
    entry_code: str = ""
    admission_no: str = ""
    on_roll: bool = True
    uci: str | None = None
    fee_manual: bool = False
    late: bool = False
    fee_payer: str = "School"
    resit: bool = False
    submitted_on: str | None = None
    sent_tier: str | None = None
    sent_status: str | None = None
    needs_resend: bool = False
    created_by: str | None = None

    @property
    def charged(self) -> float:
        """What the board will bill for this entry (0 until it is Final)."""
        return float(self.fee or 0) if self.entry_status in ("Final", "Withdrawn") else 0.0

    @property
    def unsent(self) -> bool:
        """True if the board needs telling about this entry."""
        if self.entry_status == "Final":
            return not self.submitted_on or self.needs_resend
        if self.entry_status == "Withdrawn":
            return bool(self.submitted_on) and self.needs_resend
        return False


def _num(v: float | None) -> str:
    if v is None:
        return ""
    return str(int(v)) if float(v).is_integer() else f"{v:.2f}"


def money(v: float | None) -> str:
    return "-" if v is None else f"£{v:,.2f}"


_SPEC_SELECT = ("SELECT x.*, s.code AS subject_code, s.name AS subject_name FROM exam_specs x "
                "JOIN subjects s USING (subject_id)")
_ENTRY_SELECT = (
    "SELECT e.*, x.subject_id, x.exam_board, x.spec_code, x.title AS spec_title, "
    "x.qualification, x.tiered, x.entry_code AS code1, x.foundation_code, x.higher_code, "
    "s.code AS subject_code, s.name AS subject_name, sr.name AS series_name, "
    "p.legal_last_name, p.legal_first_name, p.preferred_name, p.year_group AS pupil_year, "
    "p.admission_no, p.roll_status, c.candidate_number, c.uci "
    "FROM exam_entries e JOIN exam_specs x USING (spec_id) "
    "JOIN subjects s ON s.subject_id = x.subject_id "
    "JOIN exam_series sr ON sr.series_id = e.series_id "
    "JOIN pupils p ON p.pupil_id = e.pupil_id "
    "LEFT JOIN exam_candidates c ON c.pupil_id = e.pupil_id")


def _series_row(r) -> ExamSeries:
    return ExamSeries(**{k: r[k] for k in ExamSeries.__dataclass_fields__})


def _spec_row(r) -> Spec:
    d = {k: r[k] for k in Spec.__dataclass_fields__}
    d["tiered"], d["is_active"] = bool(d["tiered"]), bool(d["is_active"])
    return Spec(**d)


def _entry_row(r) -> ExamEntry:
    tiered = bool(r["tiered"])
    tier = r["tier"]
    if tiered and tier == "Foundation" and r["foundation_code"]:
        code = r["foundation_code"]
    elif tiered and tier == "Higher" and r["higher_code"]:
        code = r["higher_code"]
    else:
        code = r["code1"] or r["spec_code"]
    return ExamEntry(
        entry_id=r["entry_id"], pupil_id=r["pupil_id"], subject_id=r["subject_id"],
        exam_board=r["exam_board"], spec_code=r["spec_code"], tier=tier,
        candidate_number=r["candidate_number"], entry_status=r["entry_status"],
        entry_date=r["entry_date"], fee=r["fee"], notes=r["notes"],
        subject_code=r["subject_code"], subject_name=r["subject_name"],
        pupil_name=f"{r['preferred_name'] or r['legal_first_name']} {r['legal_last_name']}",
        pupil_year=r["pupil_year"], created_at=r["created_at"], updated_at=r["updated_at"],
        series_id=r["series_id"], series_name=r["series_name"], spec_id=r["spec_id"],
        spec_title=r["spec_title"], qualification=r["qualification"], tiered=tiered,
        entry_code=code, admission_no=r["admission_no"], on_roll=r["roll_status"] == "on_roll",
        uci=r["uci"], fee_manual=bool(r["fee_manual"]), late=bool(r["late"]),
        fee_payer=r["fee_payer"], resit=bool(r["resit"]), submitted_on=r["submitted_on"],
        sent_tier=r["sent_tier"], sent_status=r["sent_status"],
        needs_resend=bool(r["needs_resend"]), created_by=r["created_by"])


# ── Access and audit ─────────────────────────────────────────────────

def is_editor(actor: Principal) -> bool:
    return actor.role in EXAM_ENTRY_EDITORS


def _require(actor: Principal, action: str, target: Any = None) -> None:
    if not is_editor(actor):
        activity_log.record(action, target=target, outcome="denied", principal=actor)
        raise PermissionDenied("Only the exams officer can do that.")


def _require_staff(actor: Principal, action: str) -> None:
    if not actor.is_staff:
        activity_log.record(action, outcome="denied", principal=actor)
        raise PermissionDenied("Only school staff can see exam entries.")


def _audit(conn, action: str, actor: Principal, detail: dict, *, series_id: int | None = None,
           entry_id: int | None = None, pupil_id: int | None = None) -> None:
    conn.execute("INSERT INTO exam_entry_audit (series_id, entry_id, pupil_id, action, detail, "
                 "actor) VALUES (?, ?, ?, ?, ?, ?)",
                 (series_id, entry_id, pupil_id, action,
                  json.dumps(detail, sort_keys=True, default=str), actor.username or "unknown"))


def history(*, series_id: int | None = None, pupil_id: int | None = None,
            limit: int = 500) -> list[dict[str, Any]]:
    sql, params = "SELECT * FROM exam_entry_audit WHERE 1=1", []
    if series_id is not None:
        sql += " AND series_id = ?"
        params.append(int(series_id))
    if pupil_id is not None:
        sql += " AND pupil_id = ?"
        params.append(int(pupil_id))
    with database.connect() as conn:
        return [{"at": r["at"], "actor": r["actor"], "action": r["action"],
                 "entry_id": r["entry_id"], "pupil_id": r["pupil_id"],
                 "detail": json.loads(r["detail"] or "{}")}
                for r in conn.execute(sql + " ORDER BY audit_id DESC LIMIT ?",
                                      [*params, int(limit)])]


def _date(value: Any, label: str, problems: list[str], *, required: bool = False
          ) -> str | None:
    v = str(value or "").strip()
    if not v:
        if required:
            problems.append(f"{label} is required")
        return None
    try:
        return _dt.date.fromisoformat(v).isoformat()
    except ValueError:
        problems.append(f"{label} must be a date (YYYY-MM-DD)")
        return None


def _fee(value: Any, label: str, problems: list[str]) -> float | None:
    v = str(value if value is not None else "").strip().lstrip("£")
    if not v:
        return None
    try:
        f = round(float(v), 2)
    except ValueError:
        problems.append(f"{label} must be a number")
        return None
    if not 0 <= f <= MAX_FEE:
        problems.append(f"{label} must be between 0 and {MAX_FEE:g}")
        return None
    return f


def _choice(value: Any, options: tuple[str, ...], label: str, problems: list[str],
            default: str | None = None) -> str | None:
    v = str(value or "").strip()
    if not v:
        return default
    for o in options:
        if o.lower() == v.lower():
            return o
    problems.append(f"{label} must be one of {', '.join(options)}")
    return None


# ── Centre ───────────────────────────────────────────────────────────

def get_centre() -> Centre:
    with database.connect() as conn:
        r = conn.execute("SELECT * FROM exam_centre WHERE centre_id = 1").fetchone()
    return Centre(**{k: r[k] for k in Centre.__dataclass_fields__}) if r else Centre()


def update_centre(data: dict[str, Any], *, actor: Principal) -> Centre:
    _require(actor, "exam.centre.update")
    from education_system.systems.secondary.modules.pupils.domain import contacts as C
    cur = get_centre()
    merged = {k: getattr(cur, k) for k in ("centre_number", "centre_name", "officer_name",
                                           "officer_email")}
    merged.update({k: v for k, v in data.items() if k in merged and v is not None})
    problems = []
    number = str(merged["centre_number"] or "").strip()
    if number and not _CENTRE_RE.match(number):
        problems.append("The centre number is 5 digits")
    email = str(merged["officer_email"] or "").strip().lower()
    if email and not C.valid_email(email):
        problems.append("The exams officer's e-mail doesn't look right")
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        conn.execute(
            "INSERT INTO exam_centre (centre_id, centre_number, centre_name, officer_name, "
            "officer_email, updated_by) VALUES (1, ?, ?, ?, ?, ?) ON CONFLICT (centre_id) DO "
            "UPDATE SET centre_number = excluded.centre_number, centre_name = "
            "excluded.centre_name, officer_name = excluded.officer_name, officer_email = "
            "excluded.officer_email, updated_by = excluded.updated_by, updated_at = "
            "datetime('now')",
            (number or None, P._clean_text(merged["centre_name"], 100),
             P._clean_text(merged["officer_name"], 100), email or None, actor.username))
        _audit(conn, "centre.update", actor, {"centre_number": number or None})
    activity_log.record("exam.centre.update", principal=actor)
    return get_centre()


# ── Series ───────────────────────────────────────────────────────────

def get_series(series_id: int) -> ExamSeries:
    with database.connect() as conn:
        r = conn.execute("SELECT * FROM exam_series WHERE series_id = ?",
                         (int(series_id),)).fetchone()
    if r is None:
        raise NotFound(f"No exam series #{series_id}")
    return _series_row(r)


def list_series(*, status: str | None = None) -> list[ExamSeries]:
    sql, params = "SELECT * FROM exam_series", []
    if status:
        sql += " WHERE status = ?"
        params.append(status)
    with database.connect() as conn:
        return [_series_row(r) for r in conn.execute(
            sql + " ORDER BY exam_year DESC, season = 'June', name COLLATE NOCASE", params)]


def current_series() -> ExamSeries | None:
    """The open series with the nearest deadline (else the newest)."""
    open_ = list_series(status="Open")
    if not open_:
        return None
    return sorted(open_, key=lambda s: (s.entry_deadline or "9999", s.series_id))[0]


def _clean_series(data: dict[str, Any], current: ExamSeries | None) -> dict[str, Any]:
    keys = ("name", "season", "exam_year", "entry_deadline", "late_deadline", "results_day",
            "notes")
    merged = {k: getattr(current, k) for k in keys} if current else {}
    merged.update({k: v for k, v in data.items() if k in keys and v is not None})
    problems: list[str] = []
    season = _choice(merged.get("season"), SEASONS, "Season", problems, "June")
    try:
        year = int(str(merged.get("exam_year") or "").strip())
    except ValueError:
        year = 0
    if not 2000 <= year <= 2100:
        problems.append("Give the exam year (e.g. 2027)")
    name = P._clean_text(merged.get("name"), 60) or (f"{season} {year}" if season and year
                                                      else None)
    if not name:
        problems.append("Give the series a name")
    entry = _date(merged.get("entry_deadline"), "Entry deadline", problems)
    late = _date(merged.get("late_deadline"), "Late deadline", problems)
    results = _date(merged.get("results_day"), "Results day", problems)
    if entry and late and late < entry:
        problems.append("The late deadline can't be before the entry deadline")
    if late and not entry:
        problems.append("Give the entry deadline as well as the late deadline")
    if results and entry and results < entry:
        problems.append("Results day can't be before the entry deadline")
    if problems:
        raise ValidationError(problems)
    return {"name": name, "season": season, "exam_year": year, "entry_deadline": entry,
            "late_deadline": late, "results_day": results,
            "notes": P._clean_text(merged.get("notes"), 2000)}


def create_series(data: dict[str, Any], *, actor: Principal) -> ExamSeries:
    _require(actor, "exam.series.create")
    clean = _clean_series(data, None)
    with database.connect() as conn:
        if conn.execute("SELECT 1 FROM exam_series WHERE name = ? COLLATE NOCASE",
                        (clean["name"],)).fetchone():
            raise ValidationError([f"There is already a series called {clean['name']}"])
        sid = conn.execute(
            "INSERT INTO exam_series (name, season, exam_year, entry_deadline, late_deadline, "
            "results_day, notes, created_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (clean["name"], clean["season"], clean["exam_year"], clean["entry_deadline"],
             clean["late_deadline"], clean["results_day"], clean["notes"], actor.username)
        ).lastrowid
        _audit(conn, "series.create", actor, {"name": clean["name"]}, series_id=sid)
    activity_log.record("exam.series.create", target=f"series:{sid}", principal=actor)
    return get_series(sid)  # type: ignore[arg-type]


def update_series(series_id: int, data: dict[str, Any], *, actor: Principal) -> ExamSeries:
    s = get_series(series_id)
    _require(actor, "exam.series.update", f"series:{s.series_id}")
    if s.status == "Archived":
        raise ValidationError(["The series is archived - restore it first"])
    clean = _clean_series(data, s)
    changed = {k: v for k, v in clean.items() if getattr(s, k) != v}
    if not changed:
        return s
    with database.connect() as conn:
        if conn.execute("SELECT 1 FROM exam_series WHERE name = ? COLLATE NOCASE AND "
                        "series_id <> ?", (clean["name"], s.series_id)).fetchone():
            raise ValidationError([f"There is already a series called {clean['name']}"])
        conn.execute(
            "UPDATE exam_series SET name = ?, season = ?, exam_year = ?, entry_deadline = ?, "
            "late_deadline = ?, results_day = ?, notes = ?, updated_at = datetime('now') "
            "WHERE series_id = ?",
            (clean["name"], clean["season"], clean["exam_year"], clean["entry_deadline"],
             clean["late_deadline"], clean["results_day"], clean["notes"], s.series_id))
        _audit(conn, "series.update", actor, {"fields": sorted(changed)}, series_id=s.series_id)
    activity_log.record("exam.series.update", target=f"series:{s.series_id}", principal=actor)
    return get_series(s.series_id)


def set_series_status(series_id: int, status: str, *, actor: Principal) -> ExamSeries:
    s = get_series(series_id)
    _require(actor, "exam.series.status", f"series:{s.series_id}")
    if status == s.status:
        return s
    if status not in SERIES_STATUSES:
        raise ValidationError([f"Status must be one of {', '.join(SERIES_STATUSES)}"])
    if (s.status, status) not in _SERIES_MOVES:
        nxt = sorted(b for a, b in _SERIES_MOVES if a == s.status)
        raise ValidationError([f"An {s.status.lower()} series can move to " + " or ".join(nxt)])
    if status == "Closed":
        unsent = [e for e in list_entries(series_id=s.series_id) if e.unsent]
        if unsent:
            raise ValidationError([f"{len(unsent)} entry change(s) haven't been sent to the "
                                   "board yet - send the board files first"])
    with database.connect() as conn:
        conn.execute("UPDATE exam_series SET status = ?, updated_at = datetime('now') WHERE "
                     "series_id = ?", (status, s.series_id))
        _audit(conn, "series.status", actor, {"from": s.status, "to": status},
               series_id=s.series_id)
    activity_log.record("exam.series.status", target=f"series:{s.series_id}", principal=actor,
                        status=status)
    return get_series(s.series_id)


def delete_series(series_id: int, *, actor: Principal) -> bool:
    s = get_series(series_id)
    _require(actor, "exam.series.delete", f"series:{s.series_id}")
    with database.connect() as conn:
        n = conn.execute("SELECT count(*) FROM exam_entries WHERE series_id = ?",
                         (s.series_id,)).fetchone()[0]
        if n:
            raise ValidationError([f"The series has {n} entr{'y' if n == 1 else 'ies'} - "
                                   "it can't be deleted (close or archive it instead)"])
        conn.execute("DELETE FROM exam_series WHERE series_id = ?", (s.series_id,))
        _audit(conn, "series.delete", actor, {"name": s.name}, series_id=s.series_id)
    activity_log.record("exam.series.delete", target=f"series:{s.series_id}", principal=actor)
    return True


def deadline_state(s: ExamSeries, today: _dt.date | None = None) -> str:
    """"standard" (up to and including the entry deadline), "late" (after it,
    up to the late deadline, or with no late deadline set) or "closed" (after
    the late deadline)."""
    d = (today or _today()).isoformat()
    if not s.entry_deadline or d <= s.entry_deadline:
        return "standard"
    if s.late_deadline and d > s.late_deadline:
        return "closed"
    return "late"


def deadline_text(s: ExamSeries) -> str:
    state = deadline_state(s)
    if state == "standard":
        return (f"Standard entries until {s.entry_deadline}" if s.entry_deadline
                else "No deadline set")
    if state == "late":
        return ("Late fees apply" + (f" until {s.late_deadline}" if s.late_deadline else ""))
    return f"Late deadline {s.late_deadline} has passed - no new entries or tier changes"


def _open(s: ExamSeries) -> None:
    if s.status != "Open":
        raise ValidationError([f"{s.name} is {s.status.lower()} - entries can't change"])


# ── Specifications ───────────────────────────────────────────────────

def get_spec(spec_id: int) -> Spec:
    with database.connect() as conn:
        r = conn.execute(_SPEC_SELECT + " WHERE spec_id = ?", (int(spec_id),)).fetchone()
    if r is None:
        raise NotFound(f"No specification #{spec_id}")
    return _spec_row(r)


def list_specs(*, active_only: bool = False, subject_id: int | None = None,
               exam_board: str | None = None) -> list[Spec]:
    sql, params = _SPEC_SELECT + " WHERE 1=1", []
    if active_only:
        sql += " AND x.is_active = 1"
    if subject_id is not None:
        sql += " AND x.subject_id = ?"
        params.append(int(subject_id))
    if exam_board:
        sql += " AND x.exam_board = ?"
        params.append(exam_board)
    with database.connect() as conn:
        return [_spec_row(r) for r in conn.execute(
            sql + " ORDER BY s.name COLLATE NOCASE, x.exam_board, x.spec_code", params)]


def find_spec(code: str, board: str | None = None) -> Spec | None:
    """A spec by its spec code or any of its entry codes (case-insensitive)."""
    c = (code or "").strip().lower()
    hits = [x for x in list_specs() if (not board or x.exam_board.lower() == board.lower())
            and c in {(v or "").lower() for v in (x.spec_code, x.entry_code, x.foundation_code,
                                                  x.higher_code)}]
    return hits[0] if len(hits) == 1 else None


def _clean_spec(data: dict[str, Any], current: Spec | None) -> dict[str, Any]:
    keys = ("subject_id", "exam_board", "spec_code", "title", "qualification", "tiered",
            "entry_code", "foundation_code", "higher_code", "fee", "late_fee", "notes")
    merged = {k: getattr(current, k) for k in keys} if current else {}
    merged.update({k: v for k, v in data.items() if k in keys and v is not None})
    problems: list[str] = []
    subject = None
    try:
        subject = S.get(int(str(merged.get("subject_id") or "").strip()))
    except (ValueError, NotFound):
        problems.append("Choose the subject")
    board = _choice(merged.get("exam_board"), EXAM_BOARDS, "Exam board", problems)
    if not board and not any("Exam board" in p for p in problems):
        problems.append("Choose the exam board")
    spec = str(merged.get("spec_code") or "").strip().upper()
    if not spec or not _SPEC_RE.match(spec):
        problems.append("Spec code must be 2-16 letters, digits, / or -")
    title = P._clean_text(merged.get("title"), 100) or (subject.name if subject else None)
    qual = _choice(merged.get("qualification"), QUALIFICATIONS, "Qualification", problems,
                   "GCSE")
    tiered = P._as_bool(merged.get("tiered"), "Tiered", problems)
    codes = {}
    for k, label in (("entry_code", "Entry code"), ("foundation_code", "Foundation code"),
                     ("higher_code", "Higher code")):
        v = str(merged.get(k) or "").strip().upper()
        if v and not _CODE_RE.match(v):
            problems.append(f"{label} must be 2-16 letters, digits, / or -")
        codes[k] = v or None
    if tiered and not (codes["foundation_code"] and codes["higher_code"]):
        problems.append("A tiered specification needs a Foundation and a Higher entry code")
    if not tiered:
        codes["foundation_code"] = codes["higher_code"] = None
    fee = _fee(merged.get("fee"), "Fee", problems)
    late = _fee(merged.get("late_fee"), "Late fee", problems)
    if fee is not None and late is not None and late < fee:
        problems.append("The late fee can't be less than the standard fee")
    if problems:
        raise ValidationError(problems)
    return {"subject_id": subject.subject_id, "exam_board": board,  # type: ignore[union-attr]
            "spec_code": spec, "title": title, "qualification": qual, "tiered": int(tiered),
            **codes, "fee": fee, "late_fee": late,
            "notes": P._clean_text(merged.get("notes"), 1000)}


def create_spec(data: dict[str, Any], *, actor: Principal) -> Spec:
    _require(actor, "exam.spec.create")
    c = _clean_spec(data, None)
    with database.connect() as conn:
        if conn.execute("SELECT 1 FROM exam_specs WHERE exam_board = ? AND spec_code = ?",
                        (c["exam_board"], c["spec_code"])).fetchone():
            raise ValidationError([f"{c['exam_board']} {c['spec_code']} is already set up"])
        sid = conn.execute(
            "INSERT INTO exam_specs (subject_id, exam_board, spec_code, title, qualification, "
            "tiered, entry_code, foundation_code, higher_code, fee, late_fee, notes) VALUES "
            "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            tuple(c[k] for k in ("subject_id", "exam_board", "spec_code", "title",
                                 "qualification", "tiered", "entry_code", "foundation_code",
                                 "higher_code", "fee", "late_fee", "notes"))).lastrowid
        _audit(conn, "spec.create", actor, {"spec": f"{c['exam_board']} {c['spec_code']}"})
    activity_log.record("exam.spec.create", target=f"spec:{sid}", principal=actor)
    return get_spec(sid)  # type: ignore[arg-type]


def spec_in_use(spec_id: int) -> dict[str, int]:
    with database.connect() as conn:
        return {"entries": conn.execute("SELECT count(*) FROM exam_entries WHERE spec_id = ?",
                                        (int(spec_id),)).fetchone()[0],
                "sent": conn.execute("SELECT count(*) FROM exam_entries WHERE spec_id = ? AND "
                                     "submitted_on IS NOT NULL", (int(spec_id),)).fetchone()[0]}


def update_spec(spec_id: int, data: dict[str, Any], *, actor: Principal) -> Spec:
    x = get_spec(spec_id)
    _require(actor, "exam.spec.update", f"spec:{x.spec_id}")
    c = _clean_spec(data, x)
    changed = sorted(k for k, v in c.items()
                     if (int(getattr(x, k)) if k == "tiered" else getattr(x, k)) != v)
    if not changed:
        return x
    use = spec_in_use(x.spec_id)
    locked = {"subject_id", "exam_board", "spec_code", "tiered"} & set(changed)
    if use["entries"] and locked:
        raise ValidationError([f"Pupils are entered for this specification - the "
                               f"{', '.join(sorted(locked))} can't change (set up a new one)"])
    with database.connect() as conn:
        if conn.execute("SELECT 1 FROM exam_specs WHERE exam_board = ? AND spec_code = ? AND "
                        "spec_id <> ?", (c["exam_board"], c["spec_code"], x.spec_id)).fetchone():
            raise ValidationError([f"{c['exam_board']} {c['spec_code']} is already set up"])
        conn.execute(
            "UPDATE exam_specs SET subject_id = ?, exam_board = ?, spec_code = ?, title = ?, "
            "qualification = ?, tiered = ?, entry_code = ?, foundation_code = ?, "
            "higher_code = ?, fee = ?, late_fee = ?, notes = ?, updated_at = datetime('now') "
            "WHERE spec_id = ?",
            (*(c[k] for k in ("subject_id", "exam_board", "spec_code", "title", "qualification",
                              "tiered", "entry_code", "foundation_code", "higher_code", "fee",
                              "late_fee", "notes")), x.spec_id))
        if {"entry_code", "foundation_code", "higher_code"} & set(changed):
            # The board knows these entries by their old code - send them again.
            conn.execute("UPDATE exam_entries SET needs_resend = 1 WHERE spec_id = ? AND "
                         "submitted_on IS NOT NULL AND entry_status = 'Final'", (x.spec_id,))
        if {"fee", "late_fee"} & set(changed):
            _reprice(conn, x.spec_id)
        _audit(conn, "spec.update", actor, {"spec_id": x.spec_id, "fields": changed})
    activity_log.record("exam.spec.update", target=f"spec:{x.spec_id}", principal=actor)
    return get_spec(x.spec_id)


def set_spec_active(spec_id: int, active: bool, *, actor: Principal) -> Spec:
    x = get_spec(spec_id)
    _require(actor, "exam.spec.update", f"spec:{x.spec_id}")
    with database.connect() as conn:
        conn.execute("UPDATE exam_specs SET is_active = ?, updated_at = datetime('now') WHERE "
                     "spec_id = ?", (int(bool(active)), x.spec_id))
        _audit(conn, "spec.active", actor, {"spec_id": x.spec_id, "active": bool(active)})
    return get_spec(x.spec_id)


def delete_spec(spec_id: int, *, actor: Principal) -> bool:
    x = get_spec(spec_id)
    _require(actor, "exam.spec.delete", f"spec:{x.spec_id}")
    n = spec_in_use(x.spec_id)["entries"]
    if n:
        raise ValidationError([f"{n} entr{'y uses' if n == 1 else 'ies use'} this "
                               "specification - make it inactive instead"])
    with database.connect() as conn:
        conn.execute("DELETE FROM exam_specs WHERE spec_id = ?", (x.spec_id,))
        _audit(conn, "spec.delete", actor, {"spec": f"{x.exam_board} {x.spec_code}"})
    activity_log.record("exam.spec.delete", target=f"spec:{x.spec_id}", principal=actor)
    return True


def specs_from_subjects(*, actor: Principal) -> list[Spec]:
    """Set up a specification for every active exam subject with a board and
    spec code that isn't set up yet."""
    _require(actor, "exam.spec.create")
    have = {(x.exam_board, x.spec_code.upper()) for x in list_specs()}
    made = []
    for s in S.list_subjects(active_only=True):
        if s.qualification == "KS3" or not s.exam_board or not s.spec_code:
            continue
        if (s.exam_board, s.spec_code.strip().upper()) in have:
            continue
        qual = "GCSE" if s.qualification == "GCSE" else "Other"
        try:
            made.append(create_spec({"subject_id": s.subject_id, "exam_board": s.exam_board,
                                     "spec_code": s.spec_code, "title": s.name,
                                     "qualification": qual, "entry_code": s.spec_code},
                                    actor=actor))
        except ValidationError:
            continue  # e.g. a spec code the boards wouldn't accept - set it up by hand
    return made


def subjects_without_spec() -> list[S.Subject]:
    used = {x.subject_id for x in list_specs(active_only=True)}
    return [s for s in S.list_subjects(active_only=True, key_stage="KS4")
            if s.subject_id not in used and s.qualification != "KS3"]


# ── Candidates ───────────────────────────────────────────────────────

def candidate(pupil_id: int) -> Candidate | None:
    with database.connect() as conn:
        r = conn.execute("SELECT * FROM exam_candidates WHERE pupil_id = ?",
                         (int(pupil_id),)).fetchone()
    return Candidate(**{k: r[k] for k in Candidate.__dataclass_fields__}) if r else None


def candidates(pupil_ids: list[int] | None = None) -> dict[int, Candidate]:
    with database.connect() as conn:
        rows = conn.execute("SELECT * FROM exam_candidates").fetchall()
    out = {r["pupil_id"]: Candidate(**{k: r[k] for k in Candidate.__dataclass_fields__})
           for r in rows}
    return out if pupil_ids is None else {k: v for k, v in out.items() if k in set(pupil_ids)}


def _next_number(taken: set[str]) -> str:
    for n in range(1, 10000):
        s = f"{n:04d}"
        if s not in taken:
            return s
    raise ValidationError(["Every candidate number 0001-9999 is in use"])


def set_candidate(pupil_id: int, *, actor: Principal, candidate_number: str | None = None,
                  uci: str | None = None) -> Candidate:
    """Give a pupil a candidate number (the next free one if blank) and UCI.
    A number already sent to a board can't change."""
    _require(actor, "exam.candidate", f"pupil:{pupil_id}")
    pupil = P.get_pupil(int(pupil_id))
    if pupil is None:
        raise NotFound(f"No pupil #{pupil_id}")
    cur = candidate(pupil.pupil_id)
    problems = []
    number = (candidate_number or "").strip()
    if number and not _CAND_RE.match(number):
        problems.append("A candidate number is 4 digits")
    code = (uci or "").strip().upper() or (cur.uci if cur and uci is None else None)
    if code and not _UCI_RE.match(code):
        problems.append("A UCI is 13 letters and digits")
    with database.connect() as conn:
        taken = {r[0] for r in conn.execute(
            "SELECT candidate_number FROM exam_candidates WHERE pupil_id <> ?",
            (pupil.pupil_id,))}
        number = number or (cur.candidate_number if cur else _next_number(taken))
        if number in taken:
            problems.append(f"Candidate number {number} is already used")
        if code and conn.execute("SELECT 1 FROM exam_candidates WHERE uci = ? AND pupil_id <> ?",
                                 (code, pupil.pupil_id)).fetchone():
            problems.append("That UCI belongs to another pupil")
        sent = conn.execute("SELECT count(*) FROM exam_entries WHERE pupil_id = ? AND "
                            "submitted_on IS NOT NULL", (pupil.pupil_id,)).fetchone()[0]
        if cur and sent and number != cur.candidate_number:
            problems.append("Entries have been sent to the board under this candidate number - "
                            "it can't change")
        if problems:
            raise ValidationError(problems)
        conn.execute(
            "INSERT INTO exam_candidates (pupil_id, candidate_number, uci, assigned_by) VALUES "
            "(?, ?, ?, ?) ON CONFLICT (pupil_id) DO UPDATE SET candidate_number = "
            "excluded.candidate_number, uci = excluded.uci, assigned_by = excluded.assigned_by, "
            "assigned_at = datetime('now')", (pupil.pupil_id, number, code, actor.username))
        if cur and code != cur.uci and sent:
            conn.execute("UPDATE exam_entries SET needs_resend = 1 WHERE pupil_id = ? AND "
                         "submitted_on IS NOT NULL AND entry_status = 'Final'",
                         (pupil.pupil_id,))
        _audit(conn, "candidate", actor, {"from": cur.candidate_number if cur else None,
                                          "to": number, "uci": bool(code)},
               pupil_id=pupil.pupil_id)
    activity_log.record("exam.candidate", target=pupil.admission_no, principal=actor)
    return candidate(pupil.pupil_id)  # type: ignore[return-value]


def assign_numbers(pupil_ids: list[int], *, actor: Principal) -> int:
    """Give the next free candidate numbers to those of *pupil_ids* without one."""
    _require(actor, "exam.candidate")
    have = candidates()
    n = 0
    for pid in pupil_ids:
        if int(pid) not in have:
            set_candidate(int(pid), actor=actor)
            n += 1
    return n


# ── Entries: reading ─────────────────────────────────────────────────

def get(entry_id: int) -> ExamEntry | None:
    with database.connect() as conn:
        r = conn.execute(_ENTRY_SELECT + " WHERE e.entry_id = ?", (int(entry_id),)).fetchone()
    return _entry_row(r) if r else None


def get_entry(entry_id: int) -> ExamEntry:
    e = get(entry_id)
    if e is None:
        raise NotFound(f"No exam entry #{entry_id}")
    return e


def get_for(pupil_id: int, subject_id: int, series_id: int | None = None) -> ExamEntry | None:
    """The pupil's (live, if any) entry for a subject in a series (default: the
    current series)."""
    if series_id is None:
        cur = current_series()
        if cur is None:
            return None
        series_id = cur.series_id
    s = series_id
    rows = list_entries(series_id=s, pupil_id=pupil_id, subject_id=subject_id)
    live = [e for e in rows if e.entry_status in ("Provisional", "Final")]
    return (live or rows or [None])[0]


def list_entries(*, series_id: int | None = None, year_group: int | str | None = None,
                 subject_id: int | None = None, exam_board: str | None = None,
                 entry_status: str | None = None, tier: str | None = None,
                 pupil_id: int | str | None = None, spec_id: int | None = None
                 ) -> list[ExamEntry]:
    where, params = [], []
    for cond, val in (("e.series_id = ?", series_id), ("p.year_group = ?", year_group),
                      ("x.subject_id = ?", subject_id), ("x.exam_board = ?", exam_board),
                      ("e.entry_status = ?", entry_status), ("e.tier = ?", tier),
                      ("e.spec_id = ?", spec_id)):
        if val not in (None, ""):
            where.append(cond)
            params.append(val)
    if pupil_id not in (None, ""):
        ref = str(pupil_id).strip()
        if ref.isdigit():
            pid = int(ref)
        else:
            found = P.find_by_reference(ref)
            if found is None:
                return []
            pid = found.pupil_id
        where.append("e.pupil_id = ?")
        params.append(pid)
    sql = _ENTRY_SELECT + (" WHERE " + " AND ".join(where) if where else "")
    sql += (" ORDER BY sr.exam_year DESC, p.year_group, p.legal_last_name COLLATE NOCASE, "
            "p.legal_first_name COLLATE NOCASE, s.name COLLATE NOCASE")
    with database.connect() as conn:
        return [_entry_row(r) for r in conn.execute(sql, params)]


def entries_for_pupil(pupil_id: int, *, confirmed_only: bool = False) -> list[ExamEntry]:
    rows = list_entries(pupil_id=int(pupil_id))
    if confirmed_only:
        rows = [e for e in rows if e.entry_status == "Final"]
    return rows


# ── Entries: fees ────────────────────────────────────────────────────

def _price(spec_fee: float | None, spec_late: float | None, s: ExamSeries,
           today: _dt.date | None = None) -> tuple[float | None, bool]:
    if deadline_state(s, today) == "standard":
        return spec_fee, False
    return (spec_late if spec_late is not None else spec_fee), True


def _auto_fee(e: ExamEntry, spec: Spec) -> float | None:
    """The fee an entry would have without a typed-in one."""
    if e.entry_status == "Cancelled":
        return None
    if e.entry_status == "Withdrawn" and not e.fee:
        return 0.0
    if e.entry_status in ("Final", "Withdrawn") and e.late and spec.late_fee is not None:
        return spec.late_fee
    return spec.fee


def _reprice(conn, spec_id: int) -> None:
    """Spec fees changed: re-estimate provisional entries (Final fees were set
    when they were made Final and stay)."""
    x = conn.execute("SELECT fee FROM exam_specs WHERE spec_id = ?", (spec_id,)).fetchone()
    conn.execute("UPDATE exam_entries SET fee = ? WHERE spec_id = ? AND fee_manual = 0 AND "
                 "entry_status = 'Provisional'", (x["fee"], spec_id))


# ── Entries: changing ────────────────────────────────────────────────

def _clean_entry(data: dict[str, Any], current: ExamEntry | None) -> dict[str, Any]:
    keys = ("series_id", "pupil_id", "spec_id", "tier", "fee", "fee_payer", "resit", "notes")
    merged: dict[str, Any] = ({"series_id": current.series_id, "pupil_id": current.pupil_id,
                               "spec_id": current.spec_id, "tier": current.tier,
                               "fee": current.fee if current.fee_manual else None,
                               "fee_payer": current.fee_payer, "resit": current.resit,
                               "notes": current.notes} if current else {})
    merged.update({k: v for k, v in data.items() if k in keys and v is not None})
    problems: list[str] = []
    series = spec = pupil = None
    try:
        series = get_series(int(str(merged.get("series_id") or "").strip()))
    except (ValueError, NotFound):
        problems.append("Choose the exam series")
    ref = str(merged.get("pupil_id") or "").strip()
    if ref:
        pupil = (P.get_pupil(int(ref)) if ref.isdigit() else None) or P.find_by_reference(ref)
    if pupil is None:
        problems.append("Choose the pupil" if not ref else f"No pupil {ref}")
    sref = merged.get("spec_id")
    if sref in (None, "") and data.get("subject_id") not in (None, ""):
        try:
            subj_specs = list_specs(active_only=True, subject_id=int(data["subject_id"]))
        except (TypeError, ValueError):
            subj_specs = []
        if len(subj_specs) == 1:
            sref = subj_specs[0].spec_id
        elif len(subj_specs) > 1:
            problems.append("The subject has more than one specification - choose one")
        else:
            problems.append("No specification is set up for that subject")
    try:
        if sref not in (None, ""):
            spec = get_spec(int(str(sref).strip()))
    except (ValueError, NotFound):
        problems.append("Choose the specification")
    if spec is None and not any("specification" in p.lower() for p in problems):
        problems.append("Choose the specification")
    tier = _choice(merged.get("tier"), TIERS, "Tier", problems, DEFAULT_TIER)
    if spec and not spec.tiered and tier in ("Foundation", "Higher"):
        problems.append(f"{spec.spec_code} isn't tiered - the tier is N/A")
    fee = _fee(merged.get("fee"), "Fee", problems)
    payer = _choice(merged.get("fee_payer"), FEE_PAYERS, "Fee payer", problems, "School")
    resit = P._as_bool(merged.get("resit"), "Resit", problems)
    if pupil and current is None and pupil.roll_status != "on_roll":
        problems.append(f"{pupil.display_name} isn't on roll")
    if spec and current is None and not spec.is_active:
        problems.append(f"{spec.spec_code} is inactive")
    if problems:
        raise ValidationError(problems)
    return {"series": series, "pupil": pupil, "spec": spec, "tier": tier, "fee": fee,
            "fee_payer": payer, "resit": int(resit),
            "notes": P._clean_text(merged.get("notes"), 1000)}


def _check_status(e_status: str, c: dict[str, Any], cand: Candidate | None,
                  problems: list[str], name: str = "") -> None:
    if e_status != "Final":
        return
    pre = f"{name}: " if name else ""
    if c["spec"].tiered and c["tier"] not in ("Foundation", "Higher"):
        problems.append(f"{pre}choose Foundation or Higher before making the entry Final")
    if cand is None:
        problems.append(f"{pre}give the pupil a candidate number before making the entry Final")
    if deadline_state(c["series"]) == "closed":
        problems.append(f"{pre}the late deadline has passed - the board won't take new entries")


def create_entry(data: dict[str, Any], *, actor: Principal) -> ExamEntry:
    _require(actor, "exam.entry.create")
    c = _clean_entry(data, None)
    _open(c["series"])
    problems: list[str] = []
    status = _choice(data.get("entry_status"), ("Provisional", "Final"), "A new entry's status",
                     problems, "Provisional")
    if not problems:
        _check_status(status, c, candidate(c["pupil"].pupil_id), problems)  # type: ignore[arg-type]
    with database.connect() as conn:
        if conn.execute("SELECT 1 FROM exam_entries WHERE series_id = ? AND pupil_id = ? AND "
                        "spec_id = ?", (c["series"].series_id, c["pupil"].pupil_id,
                                        c["spec"].spec_id)).fetchone():
            problems.append(f"{c['pupil'].display_name} is already entered for "
                            f"{c['spec'].spec_code} in {c['series'].name}")
        dup = conn.execute(
            "SELECT x.spec_code FROM exam_entries e JOIN exam_specs x USING (spec_id) WHERE "
            "e.series_id = ? AND e.pupil_id = ? AND x.subject_id = ? AND e.entry_status IN "
            "('Provisional', 'Final')", (c["series"].series_id, c["pupil"].pupil_id,
                                         c["spec"].subject_id)).fetchone()
        if dup and dup[0] != c["spec"].spec_code and not P._as_bool(data.get("allow_second"),
                                                                     "", []):
            problems.append(f"{c['pupil'].display_name} is already entered for "
                            f"{c['spec'].subject_name} ({dup[0]}) in this series")
        if problems:
            raise ValidationError(problems)
        if c["fee"] is not None:
            fee, late = c["fee"], status == "Final" and deadline_state(c["series"]) != "standard"
        elif status == "Final":
            fee, late = _price(c["spec"].fee, c["spec"].late_fee, c["series"])
        else:
            fee, late = c["spec"].fee, False
        eid = conn.execute(
            "INSERT INTO exam_entries (series_id, pupil_id, spec_id, tier, entry_status, "
            "entry_date, fee, fee_manual, late, fee_payer, resit, notes, created_by) VALUES "
            "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (c["series"].series_id, c["pupil"].pupil_id, c["spec"].spec_id, c["tier"], status,
             _today().isoformat(), fee, int(c["fee"] is not None), int(late), c["fee_payer"],
             c["resit"], c["notes"], actor.username)).lastrowid
        _audit(conn, "entry.create", actor, {"spec": c["spec"].spec_code, "tier": c["tier"],
                                             "status": status},
               series_id=c["series"].series_id, entry_id=eid, pupil_id=c["pupil"].pupil_id)
    activity_log.record("exam.entry.create", target=f"entry:{eid}", principal=actor)
    return get_entry(eid)  # type: ignore[arg-type]


def update_entry(entry_id: int, data: dict[str, Any], *, actor: Principal) -> ExamEntry:
    """Change tier, fee, payer, resit or notes. The series, pupil and
    specification can't change (cancel and make a new entry)."""
    e = get_entry(entry_id)
    _require(actor, "exam.entry.update", f"entry:{e.entry_id}")
    s = get_series(e.series_id)
    _open(s)
    for k, label in (("series_id", "series"), ("pupil_id", "pupil"), ("spec_id",
                                                                       "specification")):
        if k in data and data[k] not in (None, "") and str(data[k]) != str(getattr(e, k)):
            raise ValidationError([f"The {label} of an entry can't change - cancel or withdraw "
                                   "it and make a new one"])
    data = {k: v for k, v in data.items() if k not in ("series_id", "pupil_id", "spec_id")}
    c = _clean_entry(data, e)
    problems: list[str] = []
    if e.entry_status in ("Withdrawn", "Cancelled") and c["tier"] != e.tier:
        problems.append(f"The entry is {e.entry_status.lower()} - reinstate it to change the tier")
    if e.entry_status == "Final" and c["tier"] != e.tier and _has_result(e.entry_id):
        problems.append("A result has been recorded for this entry - the tier can't change")
    if e.entry_status == "Final" and c["tier"] != e.tier:
        if c["spec"].tiered and c["tier"] not in ("Foundation", "Higher"):
            problems.append("A Final entry on a tiered specification needs Foundation or Higher")
        if e.submitted_on and deadline_state(s) == "closed":
            problems.append("The late deadline has passed - the board won't take tier changes")
    if problems:
        raise ValidationError(problems)
    typed = "fee" in data and str(data["fee"] or "").strip() != ""
    if typed and not e.fee_manual and c["fee"] == e.fee:
        typed = False  # the automatic fee shown back unchanged
    if typed:
        fee, manual = c["fee"], True
    elif "fee" in data and e.fee_manual:  # cleared: back to the automatic fee
        fee, manual = _auto_fee(e, c["spec"]), False
    else:
        fee, manual = e.fee, e.fee_manual
    changes = {k: (getattr(e, k), v) for k, v in (
        ("tier", c["tier"]), ("fee", fee), ("fee_payer", c["fee_payer"]),
        ("resit", bool(c["resit"])), ("notes", c["notes"])) if getattr(e, k) != v}
    if not changes and manual == e.fee_manual:
        return e
    resend = int(e.needs_resend or (bool(e.submitted_on) and e.entry_status == "Final"
                                    and c["tier"] != (e.sent_tier or e.tier)))
    if e.submitted_on and e.entry_status == "Final" and c["tier"] == e.sent_tier \
            and e.sent_status == "Final":
        resend = 0  # changed back to what the board already has
    with database.connect() as conn:
        conn.execute(
            "UPDATE exam_entries SET tier = ?, fee = ?, fee_manual = ?, fee_payer = ?, "
            "resit = ?, notes = ?, needs_resend = ?, updated_at = datetime('now') WHERE "
            "entry_id = ?", (c["tier"], fee, int(manual), c["fee_payer"], c["resit"],
                             c["notes"], resend, e.entry_id))
        _audit(conn, "entry.update", actor, {k: {"from": a, "to": b} for k, (a, b) in
                                             changes.items() if k != "notes"}
               | ({"notes": True} if "notes" in changes else {}),
               series_id=e.series_id, entry_id=e.entry_id, pupil_id=e.pupil_id)
    activity_log.record("exam.entry.update", target=f"entry:{e.entry_id}", principal=actor)
    return get_entry(e.entry_id)


def upsert(data: dict[str, Any], *, actor: Principal) -> ExamEntry:
    """The old "New / update" action: update the pupil's entry for that
    specification in the series if there is one, else make it."""
    c = _clean_entry({k: v for k, v in data.items() if k != "entry_status"}, None) \
        if not data.get("entry_id") else None
    existing = None
    if data.get("entry_id"):
        existing = get_entry(int(data["entry_id"]))
    elif c is not None:
        with database.connect() as conn:
            r = conn.execute("SELECT entry_id FROM exam_entries WHERE series_id = ? AND "
                             "pupil_id = ? AND spec_id = ?",
                             (c["series"].series_id, c["pupil"].pupil_id,
                              c["spec"].spec_id)).fetchone()
        existing = get_entry(r[0]) if r else None
    if existing is None:
        return create_entry(data, actor=actor)
    e = update_entry(existing.entry_id, {k: v for k, v in data.items()
                                         if k not in ("entry_status", "entry_id")}, actor=actor)
    status = (data.get("entry_status") or "").strip()
    if status and status != e.entry_status:
        e = set_status(e.entry_id, status, actor=actor)
    return e


def set_status(entry_id: int, new_status: str, *, actor: Principal,
               reason: str | None = None) -> ExamEntry:
    e = get_entry(entry_id)
    _require(actor, "exam.entry.status", f"entry:{e.entry_id}")
    s = get_series(e.series_id)
    _open(s)
    if new_status not in ENTRY_STATUSES:
        raise ValidationError([f"Status must be one of {', '.join(ENTRY_STATUSES)}"])
    if new_status == e.entry_status:
        return e
    if (e.entry_status, new_status) not in _MOVES:
        nxt = sorted(b for a, b in _MOVES if a == e.entry_status)
        raise ValidationError([f"A {e.entry_status.lower()} entry can be made "
                               + " or ".join(nxt)])
    problems: list[str] = []
    if new_status == "Provisional" and e.entry_status == "Final" and e.submitted_on:
        problems.append("The board already has this entry - withdraw it instead")
    if e.entry_status == "Final" and _has_result(e.entry_id):
        problems.append("A result has been recorded for this entry - it can't change status")
    if new_status == "Final":
        spec = get_spec(e.spec_id)
        pupil = P.get_pupil(e.pupil_id)
        if pupil is None or pupil.roll_status != "on_roll":
            problems.append("The pupil isn't on roll")
        _check_status("Final", {"spec": spec, "tier": e.tier, "series": s},
                      candidate(e.pupil_id), problems)
    if problems:
        raise ValidationError(problems)
    spec = get_spec(e.spec_id)
    fee, late, resend = e.fee, e.late, e.needs_resend
    if new_status == "Final":
        if not e.fee_manual:
            fee, late = _price(spec.fee, spec.late_fee, s)
        else:
            late = deadline_state(s) != "standard"
        # Back to Final after a withdrawal the board knows about -> tell it again.
        resend = bool(e.submitted_on) and (e.sent_status != "Final" or e.sent_tier != e.tier)
    elif new_status == "Withdrawn":
        if deadline_state(s) == "standard" and not e.fee_manual:
            fee = 0.0  # withdrawn by the entry deadline: no charge
        resend = bool(e.submitted_on) and e.sent_status != "Withdrawn"
    elif new_status == "Provisional":
        fee, late, resend = (e.fee if e.fee_manual else spec.fee), False, False
    elif new_status == "Cancelled":
        fee, late, resend = (e.fee if e.fee_manual else None), False, False
    with database.connect() as conn:
        conn.execute(
            "UPDATE exam_entries SET entry_status = ?, fee = ?, late = ?, needs_resend = ?, "
            "entry_date = CASE WHEN ? = 'Final' THEN ? ELSE entry_date END, "
            "updated_at = datetime('now') WHERE entry_id = ?",
            (new_status, fee, int(late), int(resend), new_status, _today().isoformat(),
             e.entry_id))
        _audit(conn, "entry.status", actor, {"from": e.entry_status, "to": new_status,
                                             "fee": fee, "late": late,
                                             "reason": P._clean_text(reason, 200)},
               series_id=e.series_id, entry_id=e.entry_id, pupil_id=e.pupil_id)
    activity_log.record("exam.entry.status", target=f"entry:{e.entry_id}", principal=actor,
                        status=new_status)
    return get_entry(e.entry_id)


def _has_result(entry_id: int) -> bool:
    """True if Exam Results holds a grade (or a withheld result) for the entry."""
    with database.connect() as conn:
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND "
                            "name = 'exam_results'").fetchone():
            return False
        return conn.execute("SELECT 1 FROM exam_results WHERE entry_id = ? AND status <> "
                            "'Pending'", (int(entry_id),)).fetchone() is not None


def set_tier(entry_id: int, tier: str, *, actor: Principal) -> ExamEntry:
    """The exams officer may change any tier; a teacher only a provisional
    entry for a pupil they teach."""
    e = get_entry(entry_id)
    if not is_editor(actor):
        from education_system.systems.secondary.modules.examinations.domain import mock_exams as MX
        if not (actor.is_staff and e.entry_status == "Provisional"
                and MX.teaches(actor, e.pupil_id, e.subject_id, TG.current_year())):
            activity_log.record("exam.entry.tier", target=f"entry:{e.entry_id}",
                                outcome="denied", principal=actor)
            raise PermissionDenied("You can set the tier of a provisional entry for a pupil "
                                   "you teach; ask the exams officer for anything else.")
        s = get_series(e.series_id)
        _open(s)
        problems: list[str] = []
        t = _choice(tier, TIERS, "Tier", problems)
        if t and not e.tiered and t != "N/A":
            problems.append(f"{e.spec_code} isn't tiered")
        if problems:
            raise ValidationError(problems)
        if t == e.tier:
            return e
        with database.connect() as conn:
            conn.execute("UPDATE exam_entries SET tier = ?, updated_at = datetime('now') WHERE "
                         "entry_id = ?", (t, e.entry_id))
            _audit(conn, "entry.tier", actor, {"from": e.tier, "to": t},
                   series_id=e.series_id, entry_id=e.entry_id, pupil_id=e.pupil_id)
        activity_log.record("exam.entry.tier", target=f"entry:{e.entry_id}", principal=actor)
        return get_entry(e.entry_id)
    return update_entry(e.entry_id, {"tier": tier}, actor=actor)


def delete(entry_id: int, *, actor: Principal) -> bool:
    """Only an entry the board has never had can be deleted (cancel it, or
    withdraw a sent one, to keep the record)."""
    e = get(entry_id)
    if e is None:
        return False
    _require(actor, "exam.entry.delete", f"entry:{e.entry_id}")
    if e.submitted_on or e.entry_status in ("Final", "Withdrawn"):
        raise ValidationError(["This entry is Final or has been sent to the board - withdraw "
                               "it instead of deleting it"])
    _open(get_series(e.series_id))
    with database.connect() as conn:
        conn.execute("DELETE FROM exam_entries WHERE entry_id = ?", (e.entry_id,))
        _audit(conn, "entry.delete", actor, {"spec": e.spec_code, "status": e.entry_status},
               series_id=e.series_id, entry_id=e.entry_id, pupil_id=e.pupil_id)
    activity_log.record("exam.entry.delete", target=f"entry:{e.entry_id}", principal=actor)
    return True


# ── Entries: in bulk ─────────────────────────────────────────────────

def suggested_tier(pupil_id: int, subject_id: int) -> str | None:
    """The tier the pupil was entered for in their most recent mock."""
    with database.connect() as conn:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE "
                                             "type = 'table'")}
        if "mock_entries" not in tables:
            return None
        r = conn.execute(
            "SELECT m.tier FROM mock_entries m JOIN mock_series s USING (series_id) WHERE "
            "m.pupil_id = ? AND m.subject_id = ? ORDER BY s.start_date DESC LIMIT 1",
            (int(pupil_id), int(subject_id))).fetchone()
    return r[0] if r else None


def taking(year_group: int, subject_id: int) -> list[P.Pupil]:
    """Pupils in the year group in a teaching group for the subject this year."""
    ids = {p.pupil_id for g in TG.list_groups(year_group=int(year_group),
                                              subject_id=int(subject_id))
           for p in TG.members(g.group_id)}
    return [p for p in P.list_pupils(year_group=int(year_group)) if p.pupil_id in ids]


def generate(series_id: int, year_group: int, *, actor: Principal,
             spec_ids: list[int] | None = None) -> dict[str, Any]:
    """Make provisional entries for the year group: everyone in a teaching
    group for each specification's subject who isn't entered yet, with the
    tier from their last mock where the specification is tiered."""
    s = get_series(series_id)
    _require(actor, "exam.entry.generate", f"series:{s.series_id}")
    _open(s)
    specs = [x for x in list_specs(active_only=True)
             if spec_ids is None or x.spec_id in {int(i) for i in spec_ids}]
    by_subject: dict[int, list[Spec]] = {}
    for x in specs:
        by_subject.setdefault(x.subject_id, []).append(x)
    out: dict[str, Any] = {"created": 0, "already": 0, "tiers": 0, "several_specs": [],
                           "no_pupils": []}
    with database.connect() as conn:
        entered = {(r[0], r[1]) for r in conn.execute(
            "SELECT e.pupil_id, x.subject_id FROM exam_entries e JOIN exam_specs x "
            "USING (spec_id) WHERE e.series_id = ? AND e.entry_status IN ('Provisional', "
            "'Final')", (s.series_id,))}
    rows = []
    for subject_id, xs in by_subject.items():
        if len(xs) > 1 and spec_ids is None:
            out["several_specs"].append(xs[0].subject_name)
            continue
        x = xs[0]
        pupils = taking(year_group, subject_id)
        if not pupils:
            out["no_pupils"].append(x.subject_name)
            continue
        for p in pupils:
            if (p.pupil_id, subject_id) in entered:
                out["already"] += 1
                continue
            tier = (suggested_tier(p.pupil_id, subject_id) or "N/A") if x.tiered else "N/A"
            out["tiers"] += tier != "N/A"
            rows.append((p, x, tier))
    with database.connect() as conn:
        for p, x, tier in rows:
            eid = conn.execute(
                "INSERT INTO exam_entries (series_id, pupil_id, spec_id, tier, entry_status, "
                "entry_date, fee, created_by) VALUES (?, ?, ?, ?, 'Provisional', ?, ?, ?)",
                (s.series_id, p.pupil_id, x.spec_id, tier, _today().isoformat(), x.fee,
                 actor.username)).lastrowid
            _audit(conn, "entry.create", actor, {"spec": x.spec_code, "tier": tier,
                                                 "status": "Provisional", "generated": True},
                   series_id=s.series_id, entry_id=eid, pupil_id=p.pupil_id)
    out["created"] = len(rows)
    activity_log.record("exam.entry.generate", target=f"series:{s.series_id}", principal=actor,
                        rows=len(rows), year_group=int(year_group))
    return out


def finalise(series_id: int, *, actor: Principal, entry_ids: list[int] | None = None
             ) -> dict[str, Any]:
    """Make provisional entries Final (all of them, or *entry_ids*). Entries
    that aren't ready stay provisional and are listed with the reason."""
    s = get_series(series_id)
    _require(actor, "exam.entry.finalise", f"series:{s.series_id}")
    _open(s)
    wanted = None if entry_ids is None else {int(i) for i in entry_ids}
    made, skipped = 0, []
    for e in list_entries(series_id=s.series_id, entry_status="Provisional"):
        if wanted is not None and e.entry_id not in wanted:
            continue
        try:
            set_status(e.entry_id, "Final", actor=actor)
            made += 1
        except ValidationError as ex:
            skipped.append((e, "; ".join(ex.problems)))
    return {"made": made, "skipped": skipped}


def assign_series_numbers(series_id: int, *, actor: Principal) -> int:
    """Candidate numbers for everyone entered in the series who hasn't one."""
    return assign_numbers(sorted({e.pupil_id for e in list_entries(series_id=series_id)
                                  if e.entry_status in ("Provisional", "Final")}), actor=actor)


# ── Summaries and checks ─────────────────────────────────────────────

def cohort_summary(*, series_id: int | None = None, year_group: int | str | None = None
                   ) -> dict[str, Any]:
    rows = list_entries(series_id=series_id, year_group=year_group)
    live = [r for r in rows if r.entry_status != "Cancelled"]
    billed = round(sum(r.charged for r in rows), 2)
    estimate = round(sum(r.fee or 0 for r in rows if r.entry_status == "Provisional"), 2)
    return {
        "total": len(rows),
        "candidates": len({r.pupil_id for r in live}),
        "by_status": dict(Counter(r.entry_status for r in rows)),
        "by_board": dict(Counter(r.exam_board for r in live)),
        "by_tier": dict(Counter(r.tier for r in live)),
        "by_subject": dict(Counter(r.subject_name for r in live)),
        "total_fees": billed,
        "billed": billed,
        "estimated": estimate,
        "late": sum(1 for r in rows if r.late and r.entry_status in ("Final", "Withdrawn")),
        "late_fees": round(sum(r.charged for r in rows if r.late), 2),
        "by_payer": {k: round(sum(r.charged for r in rows if r.fee_payer == k), 2)
                     for k in FEE_PAYERS},
        "unsent": sum(1 for r in rows if r.unsent),
    }


def fees_by(series_id: int, key: str = "subject") -> list[dict[str, Any]]:
    """Billed fees grouped by "subject", "board" or "payer"."""
    f = {"subject": lambda e: e.subject_name, "board": lambda e: e.exam_board,
         "payer": lambda e: e.fee_payer}[key]
    out: dict[str, dict[str, Any]] = {}
    for e in list_entries(series_id=series_id):
        if e.entry_status not in ("Final", "Withdrawn"):
            continue
        d = out.setdefault(f(e) or "", {"name": f(e), "entries": 0, "late": 0, "fees": 0.0})
        d["entries"] += 1
        d["late"] += e.late
        d["fees"] = round(d["fees"] + e.charged, 2)
    return sorted(out.values(), key=lambda d: (-d["fees"], d["name"]))


def checks(series_id: int, *, year_group: int | None = 11) -> list[dict[str, Any]]:
    """Things to sort out before the deadline, worst first."""
    s = get_series(series_id)
    rows = list_entries(series_id=s.series_id)
    live = [e for e in rows if e.entry_status in ("Provisional", "Final")]
    out: list[dict[str, Any]] = []

    def add(level: str, text: str, e: ExamEntry | None = None, pupil_id: int | None = None):
        out.append({"level": level, "text": text, "entry_id": e.entry_id if e else None,
                    "pupil_id": pupil_id or (e.pupil_id if e else None)})

    for e in live:
        who = f"{e.pupil_name} {e.subject_code}"
        if not e.on_roll:
            add("error", f"{who}: the pupil has left - withdraw or cancel the entry", e)
        if e.candidate_number is None:
            add("error", f"{who}: no candidate number", e)
        if e.tiered and e.tier == "N/A":
            add("error", f"{who}: no tier chosen", e)
    seen: dict[tuple[int, int], ExamEntry] = {}
    for e in live:
        k = (e.pupil_id, e.subject_id)
        if k in seen:
            add("warning", f"{e.pupil_name}: entered twice for {e.subject_name} "
                           f"({seen[k].spec_code} and {e.spec_code})", e)
        seen[k] = e
    prov = [e for e in live if e.entry_status == "Provisional"]
    state = deadline_state(s)
    if prov and s.entry_deadline:
        days = (_dt.date.fromisoformat(s.entry_deadline) - _today()).days
        if state == "standard" and days <= 14:
            add("warning", f"{len(prov)} provisional entr{'y' if len(prov) == 1 else 'ies'} - "
                           f"the entry deadline is in {days} day(s)")
        elif state == "late":
            add("warning", f"{len(prov)} provisional entr{'y' if len(prov) == 1 else 'ies'} - "
                           "made Final now they will be charged late fees")
        elif state == "closed":
            add("error", f"{len(prov)} provisional entr{'y' if len(prov) == 1 else 'ies'} "
                         "after the late deadline - they can't be made Final")
    unsent = [e for e in rows if e.unsent]
    if unsent:
        add("warning", f"{len(unsent)} change(s) not sent to the board yet")
    if year_group:
        for x in list_specs(active_only=True):
            have = {e.pupil_id for e in live if e.subject_id == x.subject_id}
            missing = [p for p in taking(year_group, x.subject_id) if p.pupil_id not in have]
            if missing:
                names = ", ".join(p.display_name for p in missing[:5])
                more = f" and {len(missing) - 5} more" if len(missing) > 5 else ""
                add("info", f"{x.subject_name}: {len(missing)} Year {year_group} pupil(s) "
                            f"taught it but not entered ({names}{more})")
    if not get_centre().centre_number:
        add("error", "The centre number isn't set (Exam centre)")
    order = {"error": 0, "warning": 1, "info": 2}
    return sorted(out, key=lambda d: order[d["level"]])


def access_arrangements(series_id: int) -> list[tuple[P.Pupil, str]]:
    """Candidates in the series with exam access arrangements (SEN details)."""
    from education_system.systems.secondary.modules.pupils.domain import sen_details as SEN
    out = []
    for pid in sorted({e.pupil_id for e in list_entries(series_id=series_id)
                       if e.entry_status == "Final"}):
        d = SEN.get(pid)
        p = P.get_pupil(pid)
        if d and d.exam_access and p:
            out.append((p, d.exam_access))
    return sorted(out, key=lambda t: (t[0].legal_last_name.lower(), t[0].legal_first_name))


# ── Board files ──────────────────────────────────────────────────────

BOARD_FILE_HEADINGS = ["Centre number", "Candidate number", "UCI", "Surname", "Forenames",
                       "Date of birth", "Gender", "Entry code", "Spec code", "Tier", "Action",
                       "Series"]


def board_rows(series_id: int, board: str, *, changes_only: bool = True) -> list[ExamEntry]:
    rows = [e for e in list_entries(series_id=series_id, exam_board=board)
            if e.entry_status in ("Final", "Withdrawn")]
    if changes_only:
        return [e for e in rows if e.unsent]
    return [e for e in rows if e.entry_status == "Final" or e.submitted_on]


def unsent_by_board(series_id: int) -> dict[str, int]:
    return dict(Counter(e.exam_board for e in list_entries(series_id=series_id) if e.unsent))


def _action(e: ExamEntry) -> str:
    if e.entry_status == "Withdrawn":
        return "Withdraw"
    return "Amend" if e.submitted_on else "New"


def export_board_file(series_id: int, board: str, path: str | Path, *, actor: Principal,
                      changes_only: bool = True, mark_sent: bool = True) -> int:
    """Write the board's entries file and (by default) record them as sent."""
    s = get_series(series_id)
    _require(actor, "exam.board_file", f"series:{s.series_id}")
    centre = get_centre()
    rows = board_rows(s.series_id, board, changes_only=changes_only)
    problems = []
    if not centre.centre_number:
        problems.append("Set the centre number first (Exam centre)")
    if not rows:
        problems.append(f"Nothing to send to {board}")
    for e in rows:
        if not e.candidate_number:
            problems.append(f"{e.pupil_name} has no candidate number")
    if problems:
        raise ValidationError(sorted(set(problems), key=problems.index))
    pupils = {e.pupil_id: P.get_pupil(e.pupil_id) for e in rows}
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(BOARD_FILE_HEADINGS)
        for e in rows:
            p = pupils[e.pupil_id]
            w.writerow([_safe(v) for v in (
                centre.centre_number, e.candidate_number, e.uci or "",
                p.legal_last_name if p else "", " ".join(filter(None, (
                    p.legal_first_name, p.middle_names))) if p else "",
                p.date_of_birth if p else "", (p.gender or "")[:1] if p else "",
                e.entry_code, e.spec_code, "" if e.tier == "N/A" else e.tier[:1], _action(e),
                s.name)])
    if mark_sent:
        today = _today().isoformat()
        with database.connect() as conn:
            for e in rows:
                conn.execute("UPDATE exam_entries SET submitted_on = ?, sent_tier = ?, "
                             "sent_status = ?, needs_resend = 0 WHERE entry_id = ?",
                             (today, e.tier, e.entry_status, e.entry_id))
            _audit(conn, "board_file", actor, {"board": board, "rows": len(rows),
                                               "changes_only": changes_only},
                   series_id=s.series_id)
    activity_log.record("exam.board_file", target=f"series:{s.series_id}", principal=actor,
                        rows=len(rows))
    return len(rows)


# ── Statements of entry ──────────────────────────────────────────────

def statement(pupil_id: int, series_id: int) -> dict[str, Any]:
    from education_system.systems.secondary.modules.pupils.domain import sen_details as SEN
    p = P.get_pupil(int(pupil_id))
    if p is None:
        raise NotFound(f"No pupil #{pupil_id}")
    s = get_series(series_id)
    rows = [e for e in list_entries(series_id=s.series_id, pupil_id=p.pupil_id)
            if e.entry_status == "Final"]
    d = SEN.get(p.pupil_id)
    c = candidate(p.pupil_id)
    return {"pupil": p, "series": s, "candidate": c, "entries": rows,
            "access": d.exam_access if d and d.exam_access else None, "centre": get_centre()}


def statement_text(st: dict[str, Any]) -> str:
    p, s, c = st["pupil"], st["series"], st["candidate"]
    centre = st["centre"]
    lines = [f"Statement of entry - {s.name}",
             f"Candidate: {p.legal_first_name} {p.legal_last_name}",
             f"Candidate number: {c.candidate_number if c else 'not yet given'}"
             + (f"    Centre: {centre.centre_number}" if centre.centre_number else ""),
             ""]
    if st["entries"]:
        lines.append("Entries:")
        for e in st["entries"]:
            lines.append(f"  {e.subject_name} - {e.qualification} {e.exam_board} {e.entry_code}"
                         + ("" if e.tier == "N/A" else f" ({e.tier} tier)"))
    else:
        lines.append("No confirmed entries.")
    if st["access"]:
        lines += ["", f"Access arrangements: {st['access']}"]
    return "\n".join(lines)


STATEMENT_TEMPLATE = "exam_statement"


def send_statements(series_id: int, *, actor: Principal, pupil_ids: list[int] | None = None
                    ) -> dict[str, Any]:
    """E-mail each candidate's statement of entry to their school address and
    their contacts. Returns the message id (run delivery next), the number of
    e-mails and pupils nobody could be e-mailed about."""
    s = get_series(series_id)
    _require(actor, "exam.statements", f"series:{s.series_id}")
    from education_system.systems.secondary.modules.communication.domain import email_outbox as E
    from education_system.systems.secondary.modules.communication.domain import email_templates
    from education_system.systems.secondary.modules.pupils.domain import pupil_accounts as PAC
    from education_system.systems.secondary.modules.pupils.domain import contacts as C
    ids = sorted({e.pupil_id for e in list_entries(series_id=s.series_id)
                  if e.entry_status == "Final"})
    if pupil_ids is not None:
        ids = [i for i in ids if i in {int(x) for x in pupil_ids}]
    if not ids:
        raise ValidationError(["No candidate has Final entries in this series"])
    template = email_templates.load_template(STATEMENT_TEMPLATE)
    officer = get_centre().officer_name or "the exams officer"
    contacts = C.emailable_for_pupils(ids)
    recipients, nobody = [], []
    for pid in ids:
        st = statement(pid, s.series_id)
        p = st["pupil"]
        to = []
        acct = PAC.get_for_pupil(pid)
        if acct and acct.status == "active":
            to.append((acct.school_email, p.display_name))
        to += [(c.email, c.full_name) for c in contacts.get(pid, []) if c.email]
        if not to:
            nobody.append(p)
            continue
        for address, name in to:
            subject, body = template.render({
                "recipient_name": name, "pupil_name": p.display_name,
                "pupil_first_name": p.preferred_name or p.legal_first_name,
                "series_name": s.name, "statement": statement_text(st),
                "officer_name": officer})
            recipients.append((address, name, subject, body))
    if not recipients:
        raise ValidationError(["None of the candidates has an e-mail address to send to"])
    mid = E.save_prepared("exam_statement", f"Statements of entry - {s.name}",
                          f"Statement of entry - {s.name}", "(one statement per candidate)",
                          recipients, actor=actor)
    with database.connect() as conn:
        _audit(conn, "statements", actor, {"pupils": len(ids) - len(nobody),
                                           "emails": len(recipients), "message_id": mid},
               series_id=s.series_id)
    activity_log.record("exam.statements", target=f"series:{s.series_id}", principal=actor,
                        recipients=len(recipients))
    return {"message_id": mid, "emails": len(recipients), "nobody": nobody}


# ── CSV ──────────────────────────────────────────────────────────────

def import_entries(series_id: int, path: str | Path, *, actor: Principal) -> int:
    """Provisional entries from a CSV: Admission no, Spec code (or an entry
    code), and optionally Board, Tier, Fee payer, Resit, Notes. All or
    nothing; every problem is reported by row. A pupil already entered for
    the specification has the tier/payer/notes updated."""
    s = get_series(series_id)
    _require(actor, "exam.entry.import", f"series:{s.series_id}")
    _open(s)
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        heads = {h.strip().lower(): h for h in (reader.fieldnames or [])}
        if "admission no" not in heads or "spec code" not in heads:
            raise ValidationError(["The file needs 'Admission no' and 'Spec code' columns"])
        lines = list(reader)

    def col(r, name):
        return (r.get(heads[name]) or "").strip() if name in heads else ""

    plan, problems, seen = [], [], set()
    for i, r in enumerate(lines, 2):
        ref, code = col(r, "admission no"), col(r, "spec code")
        if not ref and not code:
            continue
        p = P.find_by_reference(ref) if ref else None
        x = find_spec(code, col(r, "board") or None) if code else None
        if p is None:
            problems.append(f"Row {i}: no pupil {ref or '(blank)'}")
        if x is None:
            problems.append(f"Row {i}: no single specification with code {code or '(blank)'}")
        if p is None or x is None:
            continue
        if (p.pupil_id, x.spec_id) in seen:
            problems.append(f"Row {i}: {ref} {code} appears twice")
            continue
        seen.add((p.pupil_id, x.spec_id))
        tier = col(r, "tier") or ("N/A" if not x.tiered else "")
        if code.upper() == (x.foundation_code or "").upper():
            tier = tier or "Foundation"
        if code.upper() == (x.higher_code or "").upper():
            tier = tier or "Higher"
        data = {"series_id": s.series_id, "pupil_id": p.pupil_id, "spec_id": x.spec_id,
                "tier": tier or "N/A", "fee_payer": col(r, "fee payer") or None,
                "resit": col(r, "resit") or None, "notes": col(r, "notes") or None}
        try:
            _clean_entry(data, None)
        except ValidationError as ex:
            problems += [f"Row {i}: {m}" for m in ex.problems]
            continue
        plan.append(data)
    if problems:
        raise ValidationError(problems)
    for data in plan:
        upsert(data, actor=actor)
    activity_log.record("exam.entry.import", target=f"series:{s.series_id}", principal=actor,
                        rows=len(plan))
    return len(plan)


def export_entries(series_id: int, path: str | Path, *, actor: Principal) -> int:
    _require_staff(actor, "exam.entry.export")
    rows = list_entries(series_id=series_id)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["Admission no", "Pupil", "Year", "Candidate number", "Subject", "Board",
                    "Spec code", "Entry code", "Tier", "Status", "Fee", "Late", "Fee payer",
                    "Resit", "Sent to board", "Notes"])
        for e in rows:
            w.writerow([_safe(v) for v in (
                e.admission_no, e.pupil_name, e.pupil_year, e.candidate_number,
                e.subject_name, e.exam_board, e.spec_code, e.entry_code, e.tier,
                e.entry_status, _num(e.fee), "Y" if e.late else "", e.fee_payer,
                "Y" if e.resit else "", e.submitted_on or "", e.notes or "")])
    activity_log.record("exam.entry.export", target=f"series:{series_id}", principal=actor,
                        rows=len(rows))
    return len(rows)


S.register_usage("exam_specs", "subject_id", "exam specification(s)")
