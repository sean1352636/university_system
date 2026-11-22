"""Student finance (Student Finance England) guidance checklist per applicant.

Applying to university and applying for the money to go are two separate
applications, and the second is the one learners forget: a firm place
with no tuition-fee loan in place is a learner who cannot enrol. The
college does not apply on anyone's behalf, but it can see who has not
started. One row per applicant per cycle in ``ucas_sfe_checklist``:

* application **opened** (an SFE account created, application started)
* application **submitted**
* **evidence** — whether SFE asked for any (household income, identity,
  estrangement) and when it went in
* **entitlement** — the date the funding letter arrived
* **course start** and the **deadline** that follows from it

Applicants are those holding a UCAS application in the cycle; anyone
else can be added (a learner going via a direct application, say).
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
from education_system.systems.sixth_form.infrastructure import database as _sql
from dataclasses import dataclass
from typing import Any

from education_system import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_UCAS_DB

# ── Key dates ───────────────────────────────────────────────────────
# Student Finance England publishes these every year; the values below
# are the usual pattern, not the published dates. CHECK THEM AGAINST
# gov.uk/student-finance EACH CYCLE and change them here.
#
#: Applications for the next academic year normally open in late
#: February / March of the entry year.
SFE_APPLICATIONS_OPEN = (3, 1)          # (month, day) in the entry year
#: The "apply by" date SFE gives new full-time students so their money
#: is ready for the start of term — historically mid-to-late May.
SFE_RECOMMENDED_DEADLINE = (5, 22)      # (month, day) in the entry year
#: SFE's own statement of how long a complete application takes.
SFE_PROCESSING_WEEKS = 6
#: The final cut-off: nine months after the first day of the academic year.
SFE_FINAL_DEADLINE_MONTHS = 9
#: Used when the actual course start is not yet known.
DEFAULT_COURSE_START = (9, 21)          # (month, day) in the entry year

EVIDENCE_TYPES: tuple[str, ...] = (
    "None requested", "Household income", "Identity / passport",
    "Estrangement", "Residency", "Other",
)

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS ucas_sfe_checklist (
    checklist_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id            TEXT NOT NULL,
    cycle_year            INTEGER NOT NULL,
    opened_on             TEXT,
    submitted_on          TEXT,
    customer_ref          TEXT,
    evidence_type         TEXT,
    evidence_requested_on TEXT,
    evidence_sent_on      TEXT,
    entitlement_on        TEXT,
    course_start          TEXT,
    guidance_given_on     TEXT,
    guidance_given_by     TEXT,
    notes                 TEXT,
    updated_at            TEXT DEFAULT (datetime('now')),
    UNIQUE (student_id, cycle_year),
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);
"""


class ValidationError(ValueError):
    """Raised for invalid student-finance checklist input."""


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
    from education_system.systems.sixth_form.domain.progression.university import ucas as _ucas
    _ucas.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    _DB_READY = True


def _date(value: Any, label: str) -> str | None:
    s = (str(value).strip() if value is not None else "")
    if not s:
        return None
    if not _DATE_RE.match(s):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    try:
        _dt.date.fromisoformat(s)
    except ValueError:
        raise ValidationError(f"{label} is not a real date") from None
    return s


def key_dates(cycle_year: int) -> dict[str, _dt.date]:
    """The cycle's SFE dates from the constants above."""
    start = _dt.date(cycle_year, *DEFAULT_COURSE_START)
    final_month = 9 + SFE_FINAL_DEADLINE_MONTHS            # Sept + 9 → June next year
    final = _dt.date(cycle_year + (final_month - 1) // 12, (final_month - 1) % 12 + 1, 1)
    return {
        "applications_open": _dt.date(cycle_year, *SFE_APPLICATIONS_OPEN),
        "recommended_deadline": _dt.date(cycle_year, *SFE_RECOMMENDED_DEADLINE),
        "default_course_start": start,
        "final_deadline": final,
    }


def apply_by(cycle_year: int, course_start: str | None) -> _dt.date:
    """The date to submit by for money on day one: SFE's recommended
    deadline, or processing time before the course start if that is
    earlier (e.g. a course starting in August)."""
    kd = key_dates(cycle_year)
    start = (_dt.date.fromisoformat(course_start) if course_start
             else kd["default_course_start"])
    return min(kd["recommended_deadline"],
               start - _dt.timedelta(weeks=SFE_PROCESSING_WEEKS))


_FIELDS = ("opened_on", "submitted_on", "customer_ref", "evidence_type",
           "evidence_requested_on", "evidence_sent_on", "entitlement_on",
           "course_start", "guidance_given_on", "guidance_given_by", "notes")


def _validate(data: dict[str, Any]) -> dict[str, Any]:
    p: dict[str, Any] = {}
    for f in _FIELDS:
        v = data.get(f)
        if f.endswith("_on") or f == "course_start":
            p[f] = _date(v, f.replace("_", " ").capitalize())
        else:
            p[f] = (str(v).strip() if v is not None else "") or None
    if p["evidence_type"] and p["evidence_type"] not in EVIDENCE_TYPES:
        raise ValidationError(f"Evidence type must be one of: {', '.join(EVIDENCE_TYPES)}")
    if p["submitted_on"] and not p["opened_on"]:
        p["opened_on"] = p["submitted_on"]
    if p["opened_on"] and p["submitted_on"] and p["submitted_on"] < p["opened_on"]:
        raise ValidationError("Submitted date is before the opened date")
    if p["evidence_sent_on"] and not p["evidence_requested_on"]:
        p["evidence_requested_on"] = p["evidence_sent_on"]
    return p


def get(student_id: str, cycle_year: int) -> dict[str, Any] | None:
    init_db()
    with _connect() as conn:
        r = conn.execute("SELECT * FROM ucas_sfe_checklist WHERE student_id=? AND cycle_year=?",
                         (student_id, cycle_year)).fetchone()
    return dict(r) if r else None


def save(student_id: str, cycle_year: int, data: dict[str, Any]) -> dict[str, Any]:
    """Create or update the applicant's checklist; omitted keys keep their value."""
    init_db()
    from education_system.systems.sixth_form.domain.learners.students import students as _students
    if _students.get_student(student_id) is None:
        raise ValidationError(f"No student with id {student_id}")
    existing = get(student_id, cycle_year) or {}
    p = _validate({f: data.get(f, existing.get(f)) for f in _FIELDS})
    with _connect() as conn:
        conn.execute(
            f"""INSERT INTO ucas_sfe_checklist (student_id, cycle_year, {', '.join(_FIELDS)}, updated_at)
                VALUES (?, ?, {', '.join('?' for _ in _FIELDS)}, datetime('now'))
                ON CONFLICT(student_id, cycle_year) DO UPDATE SET
                    {', '.join(f'{f}=excluded.{f}' for f in _FIELDS)},
                    updated_at=datetime('now')""",
            (student_id, int(cycle_year), *[p[f] for f in _FIELDS]))
        conn.commit()
    out = get(student_id, cycle_year)
    assert out is not None
    return out


def delete(student_id: str, cycle_year: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute("DELETE FROM ucas_sfe_checklist WHERE student_id=? AND cycle_year=?",
                           (student_id, cycle_year))
        conn.commit()
    return bool(cur.rowcount)


@dataclass
class ChecklistRow:
    student_id: str
    student_name: str
    cycle_year: int
    record: dict[str, Any] | None
    apply_by: _dt.date
    state: str

    def as_row(self) -> dict[str, Any]:
        r = self.record or {}
        return {"student_id": self.student_id, "student_name": self.student_name,
                "cycle_year": self.cycle_year,
                "opened_on": r.get("opened_on"), "submitted_on": r.get("submitted_on"),
                "evidence": (r.get("evidence_type") or "—") + (
                    f" (sent {r['evidence_sent_on']})" if r.get("evidence_sent_on") else ""),
                "entitlement_on": r.get("entitlement_on"),
                "apply_by": self.apply_by.isoformat(), "state": self.state}


def _state(rec: dict[str, Any] | None, deadline: _dt.date, today: _dt.date) -> str:
    rec = rec or {}
    if rec.get("entitlement_on"):
        return "Funding confirmed"
    evidence_needed = (rec.get("evidence_type") not in (None, "", "None requested")
                       and not rec.get("evidence_sent_on"))
    if rec.get("submitted_on"):
        return "Evidence outstanding" if evidence_needed else "Submitted — awaiting SFE"
    if today > deadline:
        return "Not submitted — past apply-by date"
    if rec.get("opened_on"):
        return "Started, not submitted"
    return "Not started"


def cohort(cycle_year: int, *, today: _dt.date | None = None,
           state: str | None = None) -> list[ChecklistRow]:
    """Every applicant (UCAS application or existing checklist) with status."""
    init_db()
    today = today or _dt.date.today()
    from education_system.systems.sixth_form.domain.progression.university import ucas as _ucas
    from education_system.systems.sixth_form.domain.learners.students import students as _students
    names = {s.student_id: s.full_name for s in _students.list_students()}
    with _connect() as conn:
        recs = {r["student_id"]: dict(r) for r in conn.execute(
            "SELECT * FROM ucas_sfe_checklist WHERE cycle_year=?", (cycle_year,))}
    ids = {a.student_id for a in _ucas.list_applications(cycle_year=cycle_year)} | set(recs)
    out = []
    for sid in sorted(ids, key=lambda s: names.get(s, s)):
        rec = recs.get(sid)
        deadline = apply_by(cycle_year, (rec or {}).get("course_start"))
        row = ChecklistRow(sid, names.get(sid, "(unknown)"), cycle_year, rec, deadline,
                           _state(rec, deadline, today))
        if state and row.state != state:
            continue
        out.append(row)
    return out


STATES: tuple[str, ...] = (
    "Not started", "Started, not submitted", "Not submitted — past apply-by date",
    "Submitted — awaiting SFE", "Evidence outstanding", "Funding confirmed",
)

__all__ = ["SFE_APPLICATIONS_OPEN", "SFE_RECOMMENDED_DEADLINE", "SFE_PROCESSING_WEEKS",
           "SFE_FINAL_DEADLINE_MONTHS", "DEFAULT_COURSE_START", "EVIDENCE_TYPES",
           "STATES", "ValidationError", "ChecklistRow", "key_dates", "apply_by",
           "get", "save", "delete", "cohort"]
