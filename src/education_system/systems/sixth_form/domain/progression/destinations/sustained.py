"""Sustained destinations and the NCCIS-style export.

``destinations.py`` records where a leaver went at three checkpoints
(leaving, +6 months, +12 months). The DfE destination measure asks a
different question — whether the destination was **sustained** — and
that cannot be read off three snapshots: it needs to know what the
learner was doing in each month. This module adds:

* **Month-by-month activity** (``dest_activity_months``): one row per
  learner per month per activity (HE, FE, apprenticeship, employment …),
  with where the information came from.
* **Leaver year** (``dest_leavers``): which summer the learner left, so
  the measurement window is known. Defaults from their last Year 13
  enrolment when not set.
* **The sustained calculation** (:func:`sustained_status`) against the
  window and rules below.
* **An NCCIS-style CSV export** with a **configurable column layout**
  (``dest_export_layouts``).

NCCIS NOTE: local authorities collect destination/activity data through
NCCIS (the National Client Caseload Information System) and each LA's
import accepts a particular file layout and activity-code set. The exact
specification is the LA's — CHECK IT WITH YOUR LOCAL AUTHORITY and set
the export layout's columns and activity-code mapping to match. The
default layout here is a starting point, not the specification.
"""

from __future__ import annotations

import csv
import datetime as _dt
import io
import json
import logging
import re
from education_system.systems.sixth_form.infrastructure import database as _sql
from dataclasses import dataclass, field
from typing import Any

from education_system import paths

from education_system.systems.sixth_form.domain.progression.destinations.destinations import (
    DESTINATION_TYPES,
)

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_DESTINATIONS_DB

# ── The DfE sustained-destination rules ─────────────────────────────
# From the DfE 16-18 destination measures technical guidance: a leaver's
# destination is "sustained" when they were in it for the first two terms
# of the year after leaving — defined as October to March. Education must
# cover every month of the window; employment needs 5 of the 6 months; an
# apprenticeship counts if 6 consecutive months fall anywhere in the
# destination year (August to July); a mix of education and employment
# counts if every month has one or the other. VERIFY AGAINST THE CURRENT
# TECHNICAL GUIDANCE before relying on the figures.
#
#: Calendar months of the window, in the year after leaving (Oct–Mar).
SUSTAINED_WINDOW_MONTHS: tuple[int, ...] = (10, 11, 12, 1, 2, 3)
#: Months of the window employment must cover.
EMPLOYMENT_MONTHS_REQUIRED = 5
#: Consecutive months an apprenticeship must run, within Aug–Jul.
APPRENTICESHIP_MONTHS_REQUIRED = 6

EDUCATION_TYPES = frozenset({"Higher Education", "Further Education", "Training"})
EMPLOYMENT_TYPES = frozenset({"Employment"})
APPRENTICESHIP_TYPES = frozenset({"Apprenticeship"})

ACTIVITY_SOURCES: tuple[str, ...] = (
    "Local authority / NCCIS", "UCAS", "Learner", "Parent", "Employer",
    "Provider", "College follow-up", "Other",
    # Months recorded from the university's own enrolment / progression /
    # withdrawal events (university_confirmations).
    "University (confirmed by institution)",
)

SUSTAINED_STATUSES: tuple[str, ...] = (
    "Sustained education", "Sustained apprenticeship", "Sustained employment",
    "Sustained education/employment combination", "Not sustained",
    "Window not yet complete", "No activity recorded",
)

_MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS dest_leavers (
    student_id    TEXT PRIMARY KEY,
    leaver_year   INTEGER NOT NULL,
    leaving_date  TEXT,
    notes         TEXT,
    updated_at    TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS dest_activity_months (
    activity_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id     TEXT NOT NULL,
    month          TEXT NOT NULL,
    activity_type  TEXT NOT NULL,
    provider       TEXT,
    source         TEXT,
    notes          TEXT,
    created_at     TEXT DEFAULT (datetime('now')),
    UNIQUE (student_id, month, activity_type),
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_dest_act_student ON dest_activity_months(student_id, month);

CREATE TABLE IF NOT EXISTS dest_export_layouts (
    layout_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL UNIQUE,
    columns_json  TEXT NOT NULL,
    delimiter     TEXT NOT NULL DEFAULT ',',
    code_map_json TEXT,
    notes         TEXT,
    updated_at    TEXT DEFAULT (datetime('now'))
);
"""

#: Starting layout. Headers follow common NCCIS client-file naming; the
#: activity code column is blank until the LA's code set is entered in the
#: layout's code map.
DEFAULT_LAYOUT_NAME = "NCCIS-style (confirm with LA)"
DEFAULT_LAYOUT_COLUMNS: tuple[tuple[str, str], ...] = (
    ("Surname", "student.last_name"),
    ("Forename", "student.first_name"),
    ("DateOfBirth", "student.date_of_birth"),
    ("Gender", "student.gender"),
    ("ULN", "student.uln"),
    ("Postcode", "student.postcode"),
    ("LearnerReference", "student.student_id"),
    ("LeavingDate", "leaver.leaving_date"),
    ("ActivityCode", "activity.latest_code"),
    ("Activity", "activity.latest_type"),
    ("ActivityMonth", "activity.latest_month"),
    ("Provider", "activity.latest_provider"),
    ("DestinationAtLeaving", "dest.LEAVING.destination_type"),
    ("DestinationInstitution", "dest.LEAVING.institution"),
    ("Sustained", "sustained.status"),
)

_DEST_FIELDS = ("destination_type", "institution", "course", "study_level", "employer",
                "role", "start_date", "confirmed_via", "confirmed_date")


class ValidationError(ValueError):
    """Raised for invalid sustained-destination or export input."""


def _connect() -> _sql.Connection:
    paths.ensure_sixth_form_directories()
    conn = _sql.connect(str(DB_PATH))
    conn.row_factory = _sql.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


_DB_READY = False


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    from education_system.systems.sixth_form.domain.progression.destinations import (
        destinations as _dest,
    )
    _dest.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        if conn.execute("SELECT COUNT(*) FROM dest_export_layouts").fetchone()[0] == 0:
            conn.execute(
                "INSERT INTO dest_export_layouts (name, columns_json, delimiter, notes) "
                "VALUES (?, ?, ',', ?)",
                (DEFAULT_LAYOUT_NAME,
                 json.dumps([{"header": h, "field": f} for h, f in DEFAULT_LAYOUT_COLUMNS]),
                 "Starting point only — confirm the column layout and activity codes "
                 "with your local authority."))
        conn.commit()
    _DB_READY = True


def _student(student_id: str):
    from education_system.systems.sixth_form.domain.learners.students import students as _students
    st = _students.get_student((student_id or "").strip())
    if st is None:
        raise ValidationError(f"No student with id {student_id}")
    return st


def _month(value: Any, label: str = "Month") -> str:
    s = (str(value).strip() if value is not None else "")[:7]
    if not _MONTH_RE.match(s):
        raise ValidationError(f"{label} must be YYYY-MM")
    return s


def _month_add(month: str, n: int) -> str:
    y, m = int(month[:4]), int(month[5:7])
    idx = y * 12 + (m - 1) + n
    return f"{idx // 12:04d}-{idx % 12 + 1:02d}"


# ── Leaver year ─────────────────────────────────────────────────────

def _derived_leaver_year(conn: _sql.Connection, student_id: str) -> int | None:
    if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='enrolments'"
                    ).fetchone() is None:
        return None
    r = conn.execute(
        "SELECT academic_year FROM enrolments WHERE student_id=? AND year_group=13 "
        "AND archived_at IS NULL ORDER BY academic_year DESC LIMIT 1",
        (student_id,)).fetchone()
    if not r:
        return None
    m = re.search(r"(\d{4})", r["academic_year"] or "")
    return int(m.group(1)) + 1 if m else None


def leaver_year(student_id: str) -> int | None:
    """The summer the learner left: set explicitly, else from their last
    Year 13 enrolment ("2025/26" → 2026)."""
    init_db()
    with _connect() as conn:
        r = conn.execute("SELECT leaver_year FROM dest_leavers WHERE student_id=?",
                         (student_id,)).fetchone()
        if r:
            return r["leaver_year"]
        return _derived_leaver_year(conn, student_id)


def set_leaver(student_id: str, leaver_year_: int, *, leaving_date: str | None = None,
               notes: str | None = None) -> None:
    init_db()
    _student(student_id)
    try:
        year = int(leaver_year_)
    except (TypeError, ValueError):
        raise ValidationError("Leaver year must be a year") from None
    if not 2000 <= year <= 2100:
        raise ValidationError("Leaver year looks wrong")
    if leaving_date and not _DATE_RE.match(leaving_date):
        raise ValidationError("Leaving date must be YYYY-MM-DD")
    with _connect() as conn:
        conn.execute(
            """INSERT INTO dest_leavers (student_id, leaver_year, leaving_date, notes, updated_at)
               VALUES (?, ?, ?, ?, datetime('now'))
               ON CONFLICT(student_id) DO UPDATE SET leaver_year=excluded.leaver_year,
                   leaving_date=excluded.leaving_date, notes=excluded.notes,
                   updated_at=datetime('now')""",
            (student_id, year, leaving_date or None, (notes or "").strip() or None))
        conn.commit()


def leavers(year: int) -> list[str]:
    """Student ids who left in *year* (explicit or derived)."""
    init_db()
    from education_system.systems.sixth_form.domain.learners.students import students as _students
    with _connect() as conn:
        explicit = {r["student_id"]: r["leaver_year"]
                    for r in conn.execute("SELECT student_id, leaver_year FROM dest_leavers")}
        out = []
        for s in _students.list_students():
            y = explicit.get(s.student_id)
            if y is None:
                y = _derived_leaver_year(conn, s.student_id)
            if y == year:
                out.append(s.student_id)
    return out


# ── Activity months ─────────────────────────────────────────────────

def record_activity(student_id: str, month: str, activity_type: str, *,
                    provider: str | None = None, source: str | None = None,
                    notes: str | None = None) -> dict[str, Any]:
    init_db()
    _student(student_id)
    m = _month(month)
    if activity_type not in DESTINATION_TYPES:
        raise ValidationError(f"Activity must be one of: {', '.join(DESTINATION_TYPES)}")
    if source and source not in ACTIVITY_SOURCES:
        raise ValidationError(f"Source must be one of: {', '.join(ACTIVITY_SOURCES)}")
    with _connect() as conn:
        conn.execute(
            """INSERT INTO dest_activity_months
                   (student_id, month, activity_type, provider, source, notes)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(student_id, month, activity_type) DO UPDATE SET
                   provider=excluded.provider, source=excluded.source,
                   notes=excluded.notes""",
            (student_id, m, activity_type, (provider or "").strip() or None, source,
             (notes or "").strip() or None))
        conn.commit()
        return dict(conn.execute(
            "SELECT * FROM dest_activity_months WHERE student_id=? AND month=? "
            "AND activity_type=?", (student_id, m, activity_type)).fetchone())


def record_activity_range(student_id: str, from_month: str, to_month: str,
                          activity_type: str, **kwargs: Any) -> int:
    """The same activity for every month from *from_month* to *to_month*."""
    start, end = _month(from_month, "From"), _month(to_month, "To")
    if end < start:
        raise ValidationError("'To' is before 'From'")
    n, m = 0, start
    while m <= end:
        record_activity(student_id, m, activity_type, **kwargs)
        n += 1
        m = _month_add(m, 1)
        if n > 60:
            raise ValidationError("Range is longer than five years")
    return n


def list_activity(student_id: str) -> list[dict[str, Any]]:
    init_db()
    with _connect() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM dest_activity_months WHERE student_id=? ORDER BY month, activity_type",
            (student_id,))]


def delete_activity(activity_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute("DELETE FROM dest_activity_months WHERE activity_id=?",
                           (activity_id,))
        conn.commit()
    return bool(cur.rowcount)


# ── Sustained calculation ───────────────────────────────────────────

def window_months(year_left: int) -> list[str]:
    """The six YYYY-MM months of the window for a learner leaving in
    *year_left*: October year_left to March year_left + 1."""
    return [f"{year_left + (1 if m < 8 else 0):04d}-{m:02d}" for m in SUSTAINED_WINDOW_MONTHS]


@dataclass
class SustainedResult:
    student_id: str
    student_name: str
    leaver_year: int | None
    status: str
    window: list[str]
    by_month: dict[str, list[str]] = field(default_factory=dict)
    detail: str = ""

    def as_row(self) -> dict[str, Any]:
        covered = sum(1 for m in self.window if self.by_month.get(m))
        return {"student_id": self.student_id, "student_name": self.student_name,
                "leaver_year": self.leaver_year or "—", "status": self.status,
                "months": f"{covered}/{len(self.window)}", "detail": self.detail}


def _evaluate(acts: dict[str, set[str]], year_left: int, today: _dt.date) -> tuple[str, str]:
    window = window_months(year_left)
    if not acts:
        return "No activity recorded", ""
    if today.strftime("%Y-%m") <= window[-1]:
        return "Window not yet complete", f"window ends {window[-1]}"

    def covered(types: frozenset[str]) -> int:
        return sum(1 for m in window if acts.get(m, set()) & types)

    # Apprenticeship: 6 consecutive months within Aug (year_left) – Jul.
    year_months = [f"{year_left + (1 if m < 8 else 0):04d}-{m:02d}"
                   for m in (8, 9, 10, 11, 12, 1, 2, 3, 4, 5, 6, 7)]
    run = best = 0
    for m in year_months:
        run = run + 1 if acts.get(m, set()) & APPRENTICESHIP_TYPES else 0
        best = max(best, run)
    if best >= APPRENTICESHIP_MONTHS_REQUIRED:
        return "Sustained apprenticeship", f"{best} consecutive months"
    edu = covered(EDUCATION_TYPES)
    if edu == len(window):
        return "Sustained education", "every month Oct–Mar"
    emp = covered(EMPLOYMENT_TYPES)
    if emp >= EMPLOYMENT_MONTHS_REQUIRED:
        return "Sustained employment", f"{emp} of {len(window)} months"
    combo = covered(EDUCATION_TYPES | EMPLOYMENT_TYPES | APPRENTICESHIP_TYPES)
    if combo == len(window):
        return "Sustained education/employment combination", "every month covered"
    return "Not sustained", (f"education {edu}/6, employment {emp}/6, "
                             f"any positive {combo}/6")


def sustained_status(student_id: str, *, year_left: int | None = None,
                     today: _dt.date | None = None) -> SustainedResult:
    init_db()
    st = _student(student_id)
    year_left = year_left or leaver_year(student_id)
    acts: dict[str, set[str]] = {}
    for a in list_activity(student_id):
        acts.setdefault(a["month"], set()).add(a["activity_type"])
    if year_left is None:
        return SustainedResult(st.student_id, st.full_name, None, "No activity recorded"
                               if not acts else "Not sustained", [], {},
                               "leaver year unknown — set it first")
    status, detail = _evaluate(acts, year_left, today or _dt.date.today())
    window = window_months(year_left)
    return SustainedResult(st.student_id, st.full_name, year_left, status, window,
                           {m: sorted(acts.get(m, ())) for m in window}, detail)


def cohort_sustained(year_left: int, *, today: _dt.date | None = None) -> list[SustainedResult]:
    return [sustained_status(sid, year_left=year_left, today=today)
            for sid in leavers(year_left)]


def cohort_summary(year_left: int) -> dict[str, int]:
    counts = {s: 0 for s in SUSTAINED_STATUSES}
    for r in cohort_sustained(year_left):
        counts[r.status] = counts.get(r.status, 0) + 1
    return counts


# ── Export layouts ──────────────────────────────────────────────────

def list_layouts() -> list[dict[str, Any]]:
    init_db()
    with _connect() as conn:
        rows = [dict(r) for r in conn.execute("SELECT * FROM dest_export_layouts ORDER BY name")]
    for r in rows:
        r["columns"] = json.loads(r["columns_json"])
        r["code_map"] = json.loads(r["code_map_json"]) if r["code_map_json"] else {}
    return rows


def get_layout(name: str) -> dict[str, Any]:
    for layout in list_layouts():
        if layout["name"] == name:
            return layout
    raise ValidationError(f"No export layout called {name!r}")


def available_fields() -> list[str]:
    """Every field an export column can use."""
    init_db()
    with _connect() as conn:
        student_cols = [r["name"] for r in conn.execute("PRAGMA table_info(students)")]
    from education_system.systems.sixth_form.domain.progression.destinations.destinations import (
        CHECKPOINTS,
    )
    fields = [f"student.{c}" for c in student_cols]
    fields += [f"dest.{cp}.{f}" for cp in CHECKPOINTS for f in _DEST_FIELDS]
    fields += ["leaver.year", "leaver.leaving_date", "sustained.status", "sustained.months",
               "activity.latest_type", "activity.latest_month", "activity.latest_provider",
               "activity.latest_code", "const:<text>"]
    return fields


def parse_columns(text: str) -> list[dict[str, str]]:
    """``Header=field`` per line (or comma-separated) → column specs."""
    cols = []
    for part in re.split(r"[\n;]+", text or ""):
        part = part.strip()
        if not part:
            continue
        if "=" not in part:
            raise ValidationError(f"'{part}' should be Header=field")
        header, fld = (p.strip() for p in part.split("=", 1))
        if not header or not fld:
            raise ValidationError(f"'{part}' should be Header=field")
        cols.append({"header": header, "field": fld})
    if not cols:
        raise ValidationError("A layout needs at least one column")
    return cols


def save_layout(name: str, columns: list[dict[str, str]], *, delimiter: str = ",",
                code_map: dict[str, str] | None = None, notes: str | None = None) -> dict[str, Any]:
    """Create or replace a layout. Field names are checked against
    :func:`available_fields`, except ``student.*``: a student column that
    does not exist yet (``student.uln``, ``student.postcode``) is allowed
    and exports blank until the student record carries it."""
    init_db()
    name = (name or "").strip()
    if not name:
        raise ValidationError("Layout name is required")
    if delimiter not in (",", ";", "|", "\t"):
        raise ValidationError("Delimiter must be , ; | or tab")
    known = set(available_fields())
    for col in columns:
        f = col["field"]
        if not (f in known or f.startswith("const:") or f.startswith("student.")):
            raise ValidationError(f"Unknown field '{f}'")
    for k in (code_map or {}):
        if k not in DESTINATION_TYPES:
            raise ValidationError(f"Code map key '{k}' is not an activity type")
    with _connect() as conn:
        conn.execute(
            """INSERT INTO dest_export_layouts (name, columns_json, delimiter, code_map_json,
                                                notes, updated_at)
               VALUES (?, ?, ?, ?, ?, datetime('now'))
               ON CONFLICT(name) DO UPDATE SET columns_json=excluded.columns_json,
                   delimiter=excluded.delimiter, code_map_json=excluded.code_map_json,
                   notes=excluded.notes, updated_at=datetime('now')""",
            (name, json.dumps(columns), delimiter,
             json.dumps(code_map) if code_map else None, (notes or "").strip() or None))
        conn.commit()
    return get_layout(name)


def delete_layout(name: str) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute("DELETE FROM dest_export_layouts WHERE name=?", (name,))
        conn.commit()
    return bool(cur.rowcount)


def _row_values(student_row: _sql.Row, dest_rows: dict[str, _sql.Row],
                acts: list[dict[str, Any]], leaver: _sql.Row | None,
                sustained: SustainedResult, code_map: dict[str, str]) -> dict[str, Any]:
    latest = acts[-1] if acts else None
    vals: dict[str, Any] = {f"student.{k}": student_row[k] for k in student_row.keys()}
    for cp, r in dest_rows.items():
        for f in _DEST_FIELDS:
            vals[f"dest.{cp}.{f}"] = r[f]
    vals["leaver.year"] = sustained.leaver_year
    vals["leaver.leaving_date"] = leaver["leaving_date"] if leaver else None
    vals["sustained.status"] = sustained.status
    vals["sustained.months"] = sustained.as_row()["months"]
    vals["activity.latest_type"] = latest["activity_type"] if latest else None
    vals["activity.latest_month"] = latest["month"] if latest else None
    vals["activity.latest_provider"] = latest["provider"] if latest else None
    vals["activity.latest_code"] = code_map.get(latest["activity_type"]) if latest else None
    return vals


def export_csv(layout_name: str, year_left: int) -> str:
    """The cohort that left in *year_left*, one row each, in the layout."""
    init_db()
    layout = get_layout(layout_name)
    ids = leavers(year_left)
    out = io.StringIO()
    writer = csv.writer(out, delimiter=layout["delimiter"], lineterminator="\n")
    writer.writerow([c["header"] for c in layout["columns"]])
    with _connect() as conn:
        for sid in ids:
            srow = conn.execute("SELECT * FROM students WHERE student_id=?", (sid,)).fetchone()
            dest = {r["checkpoint"]: r for r in conn.execute(
                "SELECT * FROM dest_records WHERE student_id=?", (sid,))}
            leaver = conn.execute("SELECT * FROM dest_leavers WHERE student_id=?",
                                  (sid,)).fetchone()
            acts = [dict(r) for r in conn.execute(
                "SELECT * FROM dest_activity_months WHERE student_id=? ORDER BY month", (sid,))]
            sus = sustained_status(sid, year_left=year_left)
            vals = _row_values(srow, dest, acts, leaver, sus, layout["code_map"])
            writer.writerow([c["field"][6:] if c["field"].startswith("const:")
                             else ("" if vals.get(c["field"]) is None else vals[c["field"]])
                             for c in layout["columns"]])
    logger.info("Destinations export '%s' for leavers of %d: %d row(s)",
                layout_name, year_left, len(ids))
    return out.getvalue()


def export_to_file(layout_name: str, year_left: int, path: str) -> int:
    """Write :func:`export_csv` to *path* (chosen by the user); returns rows."""
    text = export_csv(layout_name, year_left)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)
    return max(0, text.count("\n") - 1)


__all__ = [
    "SUSTAINED_WINDOW_MONTHS", "EMPLOYMENT_MONTHS_REQUIRED",
    "APPRENTICESHIP_MONTHS_REQUIRED", "ACTIVITY_SOURCES", "SUSTAINED_STATUSES",
    "DEFAULT_LAYOUT_NAME", "ValidationError", "SustainedResult",
    "leaver_year", "set_leaver", "leavers", "record_activity", "record_activity_range",
    "list_activity", "delete_activity", "window_months", "sustained_status",
    "cohort_sustained", "cohort_summary", "list_layouts", "get_layout",
    "available_fields", "parse_columns", "save_layout", "delete_layout",
    "export_csv", "export_to_file",
]
