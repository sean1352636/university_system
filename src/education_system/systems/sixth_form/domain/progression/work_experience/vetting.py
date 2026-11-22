"""Health & safety vetting of placement employers, and the T Level gate.

``work_experience.py`` recorded a placement's risk assessment and
consent as two yes/no ticks and knew nothing about the employer beyond
its contact details, so a placement could start at an employer whose
liability insurance had lapsed and nobody would see it. This module
holds the vetting a college is expected to keep:

* **Employer's liability insurance** (``we_employer_insurance``) — insurer,
  policy, cover, expiry, and who saw the certificate. A placement cannot
  be confirmed, or move to *In Progress*, unless a policy is in force on
  its start date (:func:`insurance_problem`, enforced in
  ``work_experience`` itself).
* **Risk assessments** (``we_risk_assessments``) — for the employer or a
  specific placement: date, reviewer, hazards, controls, risk level,
  outcome and when it is next due for review.
* **Placement visits** (``we_placement_visits``) — pre-placement, monitoring
  and final-review visits or checks, with concerns and actions.
* **Safeguarding contact** at the employer (columns on ``we_employers``).

**T Level industry placements.** A T Level requires an industry
placement of at least :data:`TLEVEL_PLACEMENT_HOURS` hours, which may be
split across up to two employers. A placement can be linked to the
student's T Level learning aim — read from the learning-aims table the
qualifications area maintains, if it exists, by inspecting
``sqlite_master`` rather than importing it — and signed off as complete
only when the hours across its linked placements reach the minimum, it
is Completed, and a final review is on record.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
from education_system.systems.sixth_form.infrastructure import database as _sql
from dataclasses import dataclass, field
from typing import Any

from education_system import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_WORK_EXPERIENCE_DB

#: DfE minimum for a T Level industry placement (around 45 days).
#: Check the current T Level industry placement delivery guidance.
TLEVEL_PLACEMENT_HOURS: float = 315.0
#: T Level placements may be split across at most this many employers.
TLEVEL_MAX_EMPLOYERS = 2

RISK_LEVELS: tuple[str, ...] = ("Low", "Medium", "High")
RA_OUTCOMES: tuple[str, ...] = ("Approved", "Approved with conditions", "Not approved")
VISIT_TYPES: tuple[str, ...] = (
    "Pre-placement", "Monitoring", "Final review", "Phone / online check",
)

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_EMPLOYER_COLUMNS = (
    ("safeguarding_contact_name", "TEXT"),
    ("safeguarding_contact_phone", "TEXT"),
    ("safeguarding_contact_email", "TEXT"),
)
_PLACEMENT_COLUMNS = (
    ("confirmed_on", "TEXT"),
    ("confirmed_by", "TEXT"),
    ("tlevel_aim_ref", "TEXT"),
    ("tlevel_completed_on", "TEXT"),
    ("tlevel_signed_off_by", "TEXT"),
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS we_employer_insurance (
    insurance_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    employer_id       INTEGER NOT NULL,
    insurer           TEXT NOT NULL,
    policy_number     TEXT,
    cover_amount      TEXT,
    start_date        TEXT,
    expiry_date       TEXT NOT NULL,
    seen_by           TEXT,
    seen_on           TEXT,
    notes             TEXT,
    created_at        TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (employer_id) REFERENCES we_employers(employer_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_we_ins_employer ON we_employer_insurance(employer_id, expiry_date);

CREATE TABLE IF NOT EXISTS we_risk_assessments (
    ra_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    employer_id      INTEGER NOT NULL,
    placement_id     INTEGER,
    assessed_on      TEXT NOT NULL,
    reviewer         TEXT NOT NULL,
    hazards          TEXT NOT NULL,
    controls         TEXT,
    risk_level       TEXT NOT NULL DEFAULT 'Low',
    outcome          TEXT NOT NULL DEFAULT 'Approved',
    next_review_due  TEXT,
    notes            TEXT,
    created_at       TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (employer_id) REFERENCES we_employers(employer_id) ON DELETE CASCADE,
    FOREIGN KEY (placement_id) REFERENCES we_placements(placement_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_we_ra_employer ON we_risk_assessments(employer_id, assessed_on);

CREATE TABLE IF NOT EXISTS we_placement_visits (
    visit_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    placement_id  INTEGER NOT NULL,
    visit_date    TEXT NOT NULL,
    visit_type    TEXT NOT NULL DEFAULT 'Monitoring',
    visited_by    TEXT NOT NULL,
    student_seen  INTEGER NOT NULL DEFAULT 1,
    concerns      TEXT,
    actions       TEXT,
    notes         TEXT,
    created_at    TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (placement_id) REFERENCES we_placements(placement_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_we_visits_placement ON we_placement_visits(placement_id);
"""


class ValidationError(ValueError):
    """Raised for invalid vetting input or a failed gate."""


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
    from education_system.systems.sixth_form.domain.progression.work_experience import (
        work_experience as _we,
    )
    _we.init_db()
    with _connect() as conn:
        for table, columns in (("we_employers", _EMPLOYER_COLUMNS),
                               ("we_placements", _PLACEMENT_COLUMNS)):
            have = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
            for col, ddl in columns:
                if col not in have:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}")
        conn.executescript(_SCHEMA)
        conn.commit()
    _DB_READY = True
    logger.debug("Work-experience vetting schema ready at %s", DB_PATH)


def _date(value: Any, label: str, *, required: bool = False) -> str | None:
    s = (str(value).strip() if value is not None else "")
    if not s:
        if required:
            raise ValidationError(f"{label} is required")
        return None
    if not _DATE_RE.match(s):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    try:
        _dt.date.fromisoformat(s)
    except ValueError:
        raise ValidationError(f"{label} is not a real date") from None
    return s


def _text(value: Any) -> str | None:
    return (str(value).strip() if value is not None else "") or None


def _employer(employer_id: Any):
    from education_system.systems.sixth_form.domain.progression.work_experience import (
        work_experience as _we,
    )
    try:
        emp = _we.get_employer(int(employer_id))
    except (TypeError, ValueError):
        emp = None
    if emp is None:
        raise ValidationError(f"No employer with id {employer_id}")
    return emp


def _placement(placement_id: Any):
    from education_system.systems.sixth_form.domain.progression.work_experience import (
        work_experience as _we,
    )
    try:
        p = _we.get_placement(int(placement_id))
    except (TypeError, ValueError):
        p = None
    if p is None:
        raise ValidationError(f"No placement with id {placement_id}")
    return p


# ── Insurance ───────────────────────────────────────────────────────

def add_insurance(employer_id: int, data: dict[str, Any]) -> dict[str, Any]:
    init_db()
    _employer(employer_id)
    insurer = _text(data.get("insurer"))
    if not insurer:
        raise ValidationError("Insurer is required")
    start = _date(data.get("start_date"), "Start date")
    expiry = _date(data.get("expiry_date"), "Expiry date", required=True)
    if start and expiry < start:
        raise ValidationError("Expiry is before the start date")
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO we_employer_insurance
                   (employer_id, insurer, policy_number, cover_amount, start_date,
                    expiry_date, seen_by, seen_on, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (int(employer_id), insurer, _text(data.get("policy_number")),
             _text(data.get("cover_amount")), start, expiry, _text(data.get("seen_by")),
             _date(data.get("seen_on"), "Seen on"), _text(data.get("notes"))))
        conn.commit()
        return dict(conn.execute("SELECT * FROM we_employer_insurance WHERE insurance_id=?",
                                 (cur.lastrowid,)).fetchone())


def list_insurance(employer_id: int | None = None) -> list[dict[str, Any]]:
    init_db()
    where, args = ("WHERE i.employer_id = ?", (employer_id,)) if employer_id else ("", ())
    with _connect() as conn:
        return [dict(r) for r in conn.execute(
            f"""SELECT i.*, e.name AS employer_name FROM we_employer_insurance i
                  JOIN we_employers e ON e.employer_id = i.employer_id
                  {where} ORDER BY i.expiry_date DESC""", args)]


def delete_insurance(insurance_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute("DELETE FROM we_employer_insurance WHERE insurance_id=?",
                           (insurance_id,))
        conn.commit()
    return bool(cur.rowcount)


def insurance_in_force(employer_id: int, on_date: str) -> dict[str, Any] | None:
    """The policy covering *on_date*, latest expiry first, or None."""
    init_db()
    with _connect() as conn:
        r = conn.execute(
            """SELECT * FROM we_employer_insurance
                WHERE employer_id = ? AND expiry_date >= ?
                  AND (start_date IS NULL OR start_date <= ?)
                ORDER BY expiry_date DESC LIMIT 1""",
            (employer_id, on_date, on_date)).fetchone()
    return dict(r) if r else None


def insurance_problem(employer_id: int, start_date: str) -> str | None:
    """Why a placement starting *start_date* cannot go ahead on insurance
    grounds, or None. Checks the start date and today, whichever is later,
    so an expired certificate blocks a placement that has already begun."""
    check = max(start_date, _dt.date.today().isoformat())
    if insurance_in_force(employer_id, check):
        return None
    latest = list_insurance(employer_id)
    if not latest:
        return ("No employer's liability insurance is recorded for this employer — "
                "record the certificate first.")
    return (f"The employer's liability insurance expired on {latest[0]['expiry_date']} "
            f"— record the renewed certificate before confirming.")


def expiring_insurance(*, within_days: int = 30) -> list[dict[str, Any]]:
    """Employers whose latest policy expires within *within_days* or has
    expired, and who have placements Planned or In Progress."""
    init_db()
    today = _dt.date.today()
    cutoff = (today + _dt.timedelta(days=within_days)).isoformat()
    with _connect() as conn:
        rows = conn.execute(
            """SELECT e.employer_id, e.name, MAX(i.expiry_date) AS expiry,
                      (SELECT COUNT(*) FROM we_placements p
                        WHERE p.employer_id = e.employer_id
                          AND p.status IN ('Planned', 'In Progress')) AS live
                 FROM we_employers e
                 LEFT JOIN we_employer_insurance i ON i.employer_id = e.employer_id
                GROUP BY e.employer_id""").fetchall()
    out = []
    for r in rows:
        if not r["live"]:
            continue
        if r["expiry"] is None or r["expiry"] <= cutoff:
            out.append({"employer_id": r["employer_id"], "name": r["name"],
                        "expiry": r["expiry"] or "none recorded",
                        "live_placements": r["live"],
                        "state": ("Expired / missing" if r["expiry"] is None
                                  or r["expiry"] < today.isoformat() else "Expiring soon")})
    return out


# ── Risk assessments ────────────────────────────────────────────────

def add_risk_assessment(employer_id: int, data: dict[str, Any]) -> dict[str, Any]:
    init_db()
    _employer(employer_id)
    placement_id = data.get("placement_id")
    if placement_id not in (None, ""):
        p = _placement(placement_id)
        if p.employer_id != int(employer_id):
            raise ValidationError("That placement is at a different employer")
        placement_id = p.placement_id
    else:
        placement_id = None
    reviewer = _text(data.get("reviewer"))
    hazards = _text(data.get("hazards"))
    if not reviewer:
        raise ValidationError("Reviewer is required")
    if not hazards:
        raise ValidationError("List the hazards identified")
    level = _text(data.get("risk_level")) or "Low"
    outcome = _text(data.get("outcome")) or "Approved"
    if level not in RISK_LEVELS:
        raise ValidationError(f"Risk level must be one of: {', '.join(RISK_LEVELS)}")
    if outcome not in RA_OUTCOMES:
        raise ValidationError(f"Outcome must be one of: {', '.join(RA_OUTCOMES)}")
    assessed = _date(data.get("assessed_on"), "Assessed on", required=True)
    review = _date(data.get("next_review_due"), "Next review due")
    if review and review <= assessed:
        raise ValidationError("Next review must be after the assessment date")
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO we_risk_assessments
                   (employer_id, placement_id, assessed_on, reviewer, hazards, controls,
                    risk_level, outcome, next_review_due, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (int(employer_id), placement_id, assessed, reviewer, hazards,
             _text(data.get("controls")), level, outcome, review, _text(data.get("notes"))))
        conn.commit()
        ra = dict(conn.execute("SELECT * FROM we_risk_assessments WHERE ra_id=?",
                               (cur.lastrowid,)).fetchone())
    if placement_id and outcome != "Not approved":
        # Keep the original yes/no tick on the placement truthful.
        with _connect() as conn:
            conn.execute("UPDATE we_placements SET risk_assessment_done=1 WHERE placement_id=?",
                         (placement_id,))
            conn.commit()
    return ra


def list_risk_assessments(*, employer_id: int | None = None,
                          placement_id: int | None = None) -> list[dict[str, Any]]:
    init_db()
    clauses, args = [], []
    if employer_id:
        clauses.append("r.employer_id = ?"); args.append(employer_id)
    if placement_id:
        clauses.append("(r.placement_id = ? OR r.placement_id IS NULL)"); args.append(placement_id)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with _connect() as conn:
        return [dict(r) for r in conn.execute(
            f"""SELECT r.*, e.name AS employer_name FROM we_risk_assessments r
                  JOIN we_employers e ON e.employer_id = r.employer_id
                  {where} ORDER BY r.assessed_on DESC""", args)]


def current_risk_assessment(employer_id: int, placement_id: int | None = None,
                            on_date: str | None = None) -> dict[str, Any] | None:
    """The latest assessment that applies (placement-specific or employer-
    wide), if it approves the placement and its review is not overdue."""
    on_date = on_date or _dt.date.today().isoformat()
    for ra in list_risk_assessments(employer_id=employer_id, placement_id=placement_id):
        if ra["outcome"] == "Not approved":
            return None
        if ra["next_review_due"] and ra["next_review_due"] < on_date:
            return None
        return ra
    return None


def delete_risk_assessment(ra_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute("DELETE FROM we_risk_assessments WHERE ra_id=?", (ra_id,))
        conn.commit()
    return bool(cur.rowcount)


# ── Visits ──────────────────────────────────────────────────────────

def add_visit(placement_id: int, data: dict[str, Any]) -> dict[str, Any]:
    init_db()
    _placement(placement_id)
    vtype = _text(data.get("visit_type")) or "Monitoring"
    if vtype not in VISIT_TYPES:
        raise ValidationError(f"Visit type must be one of: {', '.join(VISIT_TYPES)}")
    who = _text(data.get("visited_by"))
    if not who:
        raise ValidationError("Who made the visit?")
    seen = data.get("student_seen", True)
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO we_placement_visits
                   (placement_id, visit_date, visit_type, visited_by, student_seen,
                    concerns, actions, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (int(placement_id), _date(data.get("visit_date"), "Visit date", required=True),
             vtype, who, 1 if (seen is True or str(seen).lower() in ("1", "y", "yes", "true"))
             else 0, _text(data.get("concerns")), _text(data.get("actions")),
             _text(data.get("notes"))))
        conn.commit()
        return dict(conn.execute("SELECT * FROM we_placement_visits WHERE visit_id=?",
                                 (cur.lastrowid,)).fetchone())


def list_visits(placement_id: int | None = None) -> list[dict[str, Any]]:
    init_db()
    where, args = ("WHERE v.placement_id = ?", (placement_id,)) if placement_id else ("", ())
    with _connect() as conn:
        return [dict(r) for r in conn.execute(
            f"""SELECT v.*, p.student_id, e.name AS employer_name
                  FROM we_placement_visits v
                  JOIN we_placements p ON p.placement_id = v.placement_id
                  JOIN we_employers e ON e.employer_id = p.employer_id
                  {where} ORDER BY v.visit_date DESC""", args)]


def delete_visit(visit_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute("DELETE FROM we_placement_visits WHERE visit_id=?", (visit_id,))
        conn.commit()
    return bool(cur.rowcount)


# ── Safeguarding contact ────────────────────────────────────────────

def get_safeguarding_contact(employer_id: int) -> dict[str, Any]:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT safeguarding_contact_name AS name, safeguarding_contact_phone AS phone, "
            "safeguarding_contact_email AS email FROM we_employers WHERE employer_id=?",
            (employer_id,)).fetchone()
    if r is None:
        raise ValidationError(f"No employer with id {employer_id}")
    return dict(r)


def set_safeguarding_contact(employer_id: int, *, name: str | None, phone: str | None,
                             email: str | None) -> dict[str, Any]:
    init_db()
    _employer(employer_id)
    email = _text(email)
    if email and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        raise ValidationError("Safeguarding contact email is not valid")
    if not _text(name) and (phone or email):
        raise ValidationError("Give the safeguarding contact's name")
    with _connect() as conn:
        conn.execute(
            "UPDATE we_employers SET safeguarding_contact_name=?, safeguarding_contact_phone=?, "
            "safeguarding_contact_email=?, updated_at=datetime('now') WHERE employer_id=?",
            (_text(name), _text(phone), email, employer_id))
        conn.commit()
    return get_safeguarding_contact(employer_id)


# ── Vetting summary and confirmation ────────────────────────────────

@dataclass
class Vetting:
    employer_id: int
    employer_name: str
    insurance: dict[str, Any] | None
    risk_assessment: dict[str, Any] | None
    safeguarding_contact: dict[str, Any]
    problems: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems

    def as_row(self) -> dict[str, Any]:
        return {"employer_id": self.employer_id, "name": self.employer_name,
                "insurance": self.insurance["expiry_date"] if self.insurance else "—",
                "risk_assessment": (f"{self.risk_assessment['assessed_on']} "
                                    f"({self.risk_assessment['outcome']})"
                                    if self.risk_assessment else "—"),
                "safeguarding": self.safeguarding_contact.get("name") or "—",
                "state": "Vetted" if self.ok else "; ".join(self.problems)}


def vetting(employer_id: int, *, placement_id: int | None = None,
            on_date: str | None = None) -> Vetting:
    init_db()
    emp = _employer(employer_id)
    on_date = on_date or _dt.date.today().isoformat()
    ins = insurance_in_force(emp.employer_id, max(on_date, _dt.date.today().isoformat()))
    ra = current_risk_assessment(emp.employer_id, placement_id, on_date)
    sg = get_safeguarding_contact(emp.employer_id)
    problems = []
    ins_problem = insurance_problem(emp.employer_id, on_date)
    if ins_problem:
        problems.append(ins_problem)
    if ra is None:
        problems.append("No current approved risk assessment (missing, not approved, "
                        "or past its review date).")
    if not sg.get("name"):
        problems.append("No safeguarding contact recorded at the employer.")
    return Vetting(emp.employer_id, emp.name, ins, ra, sg, problems)


def employer_vetting_list() -> list[Vetting]:
    from education_system.systems.sixth_form.domain.progression.work_experience import (
        work_experience as _we,
    )
    return [vetting(e.employer_id) for e in _we.list_employers()]


def confirm_placement(placement_id: int, *, confirmed_by: str) -> dict[str, Any]:
    """Confirm a placement can go ahead: insurance in force on its start
    date, a current approved risk assessment and a safeguarding contact."""
    init_db()
    p = _placement(placement_id)
    if p.status == "Cancelled":
        raise ValidationError("A cancelled placement cannot be confirmed")
    if not (confirmed_by or "").strip():
        raise ValidationError("Who is confirming the placement?")
    v = vetting(p.employer_id, placement_id=p.placement_id, on_date=p.start_date)
    if not v.ok:
        raise ValidationError("Cannot confirm: " + " ".join(v.problems))
    with _connect() as conn:
        conn.execute("UPDATE we_placements SET confirmed_on=?, confirmed_by=?, "
                     "updated_at=datetime('now') WHERE placement_id=?",
                     (_dt.date.today().isoformat(), confirmed_by.strip(), p.placement_id))
        conn.commit()
    logger.info("Placement #%d confirmed by %s", p.placement_id, confirmed_by)
    return placement_extras(p.placement_id)


def placement_extras(placement_id: int) -> dict[str, Any]:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT confirmed_on, confirmed_by, tlevel_aim_ref, tlevel_completed_on, "
            "tlevel_signed_off_by FROM we_placements WHERE placement_id=?",
            (placement_id,)).fetchone()
    if r is None:
        raise ValidationError(f"No placement with id {placement_id}")
    return dict(r)


def placement_extras_map() -> dict[int, dict[str, Any]]:
    """:func:`placement_extras` for every placement, in one query."""
    init_db()
    with _connect() as conn:
        return {r["placement_id"]: dict(r) for r in conn.execute(
            "SELECT placement_id, confirmed_on, confirmed_by, tlevel_aim_ref, "
            "tlevel_completed_on, tlevel_signed_off_by FROM we_placements")}


# ── T Level industry placement ──────────────────────────────────────

_AIM_ID_COLS = ("aim_id", "learning_aim_id", "aim_ref", "learning_aim_ref",
                "learning_aim_reference", "id")
_AIM_TITLE_COLS = ("title", "aim_title", "qualification_title", "qualification_name",
                   "name", "qualification")
_TLEVEL_RE = re.compile(r"\bt[\s-]?level", re.I)


def _learning_aims_tables(conn: _sql.Connection) -> list[tuple[str, set[str]]]:
    out = []
    for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' "
                          "AND name LIKE '%aim%'"):
        cols = {c["name"] for c in conn.execute(f"PRAGMA table_info(\"{r['name']}\")")}
        if "student_id" in cols and any(c in cols for c in _AIM_ID_COLS):
            out.append((r["name"], cols))
    return out


def tlevel_aims_for(student_id: str) -> list[dict[str, Any]]:
    """The student's T Level learning aims, or [] when the learning-aims
    table does not exist (yet) or holds none. Read by schema inspection so
    this module has no import dependency on the qualifications area."""
    init_db()
    out: list[dict[str, Any]] = []
    with _connect() as conn:
        for table, cols in _learning_aims_tables(conn):
            id_col = next(c for c in _AIM_ID_COLS if c in cols)
            text_cols = [c for c in cols if c in _AIM_TITLE_COLS or "type" in c
                         or "qualification" in c]
            for r in conn.execute(f'SELECT * FROM "{table}" WHERE student_id = ?',
                                  (student_id,)):
                blob = " ".join(str(r[c] or "") for c in text_cols)
                if _TLEVEL_RE.search(blob):
                    title = next((r[c] for c in _AIM_TITLE_COLS if c in cols and r[c]), blob)
                    out.append({"aim_ref": f"{table}:{r[id_col]}", "title": str(title)[:80]})
    return out


def link_tlevel_aim(placement_id: int, aim_ref: str | None) -> dict[str, Any]:
    """Link a placement to the student's T Level aim (``None`` unlinks)."""
    init_db()
    p = _placement(placement_id)
    ref = _text(aim_ref)
    if ref:
        aims = {a["aim_ref"] for a in tlevel_aims_for(p.student_id)}
        if ref not in aims:
            raise ValidationError(
                "That is not one of this student's T Level learning aims"
                + ("" if aims else " (none are recorded)") + ".")
        employers = {r["employer_id"] for r in _linked_placements(p.student_id, ref)}
        employers.add(p.employer_id)
        if len(employers) > TLEVEL_MAX_EMPLOYERS:
            raise ValidationError(
                f"A T Level placement can be split across at most {TLEVEL_MAX_EMPLOYERS} "
                "employers.")
    with _connect() as conn:
        conn.execute("UPDATE we_placements SET tlevel_aim_ref=?, tlevel_completed_on=NULL, "
                     "tlevel_signed_off_by=NULL, updated_at=datetime('now') "
                     "WHERE placement_id=?", (ref, p.placement_id))
        if not p.hours_required and ref:
            conn.execute("UPDATE we_placements SET hours_required=? WHERE placement_id=?",
                         (TLEVEL_PLACEMENT_HOURS, p.placement_id))
        conn.commit()
    return placement_extras(p.placement_id)


def _linked_placements(student_id: str, aim_ref: str) -> list[_sql.Row]:
    with _connect() as conn:
        return conn.execute(
            "SELECT * FROM we_placements WHERE student_id=? AND tlevel_aim_ref=? "
            "AND status != 'Cancelled'", (student_id, aim_ref)).fetchall()


def tlevel_completion_check(placement_id: int) -> list[str]:
    """What stops this T Level placement being signed off (empty = ready)."""
    init_db()
    p = _placement(placement_id)
    extras = placement_extras(p.placement_id)
    ref = extras["tlevel_aim_ref"]
    if not ref:
        return ["The placement is not linked to a T Level learning aim."]
    linked = _linked_placements(p.student_id, ref)
    total = round(sum(r["hours_completed"] or 0 for r in linked), 2)
    problems = []
    if total < TLEVEL_PLACEMENT_HOURS:
        problems.append(f"{total:g} of {TLEVEL_PLACEMENT_HOURS:g} hours completed across "
                        f"{len(linked)} linked placement(s).")
    unfinished = [r["placement_id"] for r in linked if r["status"] != "Completed"]
    if unfinished:
        problems.append("Placement(s) not marked Completed: "
                        + ", ".join(f"#{i}" for i in unfinished))
    if not any(v["visit_type"] == "Final review" for r in linked
               for v in list_visits(r["placement_id"])):
        problems.append("No final review visit is recorded.")
    unconfirmed = [r["placement_id"] for r in linked if not r["confirmed_on"]]
    if unconfirmed:
        problems.append("Placement(s) never vetted and confirmed: "
                        + ", ".join(f"#{i}" for i in unconfirmed))
    return problems


def sign_off_tlevel(placement_id: int, *, signed_off_by: str) -> dict[str, Any]:
    """Record the T Level industry placement as complete — only once
    :func:`tlevel_completion_check` finds nothing outstanding."""
    init_db()
    if not (signed_off_by or "").strip():
        raise ValidationError("Who is signing the placement off?")
    problems = tlevel_completion_check(placement_id)
    if problems:
        raise ValidationError("Not complete: " + " ".join(problems))
    p = _placement(placement_id)
    ref = placement_extras(placement_id)["tlevel_aim_ref"]
    today = _dt.date.today().isoformat()
    with _connect() as conn:
        conn.execute("UPDATE we_placements SET tlevel_completed_on=?, tlevel_signed_off_by=?, "
                     "updated_at=datetime('now') WHERE student_id=? AND tlevel_aim_ref=? "
                     "AND status != 'Cancelled'",
                     (today, signed_off_by.strip(), p.student_id, ref))
        conn.commit()
    logger.info("T Level placement for %s (%s) signed off by %s", p.student_id, ref,
                signed_off_by)
    return placement_extras(placement_id)


def tlevel_overview() -> list[dict[str, Any]]:
    """Every T Level-linked placement with hours across its aim and state."""
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            """SELECT p.*, e.name AS employer_name,
                      s.first_name || ' ' || s.last_name AS student_name
                 FROM we_placements p
                 JOIN we_employers e ON e.employer_id = p.employer_id
                 LEFT JOIN students s ON s.student_id = p.student_id
                WHERE p.tlevel_aim_ref IS NOT NULL
                ORDER BY p.student_id, p.start_date""").fetchall()
    totals: dict[tuple[str, str], float] = {}
    for r in rows:
        if r["status"] != "Cancelled":
            key = (r["student_id"], r["tlevel_aim_ref"])
            totals[key] = totals.get(key, 0) + (r["hours_completed"] or 0)
    return [{"placement_id": r["placement_id"], "student_id": r["student_id"],
             "student_name": r["student_name"], "employer": r["employer_name"],
             "aim_ref": r["tlevel_aim_ref"], "status": r["status"],
             "hours": r["hours_completed"],
             "aim_hours": f"{totals.get((r['student_id'], r['tlevel_aim_ref']), 0):g}"
                          f"/{TLEVEL_PLACEMENT_HOURS:g}",
             "completed_on": r["tlevel_completed_on"] or "—"} for r in rows]


__all__ = [
    "TLEVEL_PLACEMENT_HOURS", "TLEVEL_MAX_EMPLOYERS", "RISK_LEVELS", "RA_OUTCOMES",
    "VISIT_TYPES", "ValidationError", "Vetting",
    "add_insurance", "list_insurance", "delete_insurance", "insurance_in_force",
    "insurance_problem", "expiring_insurance",
    "add_risk_assessment", "list_risk_assessments", "current_risk_assessment",
    "delete_risk_assessment", "add_visit", "list_visits", "delete_visit",
    "get_safeguarding_contact", "set_safeguarding_contact",
    "vetting", "employer_vetting_list", "confirm_placement", "placement_extras",
    "placement_extras_map",
    "tlevel_aims_for", "link_tlevel_aim", "tlevel_completion_check", "sign_off_tlevel",
    "tlevel_overview",
]
