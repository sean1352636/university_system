"""Reports to parents: the termly report each family receives.

There was no reports-to-parents screen in the old system (only the menu
entry), so this is new. It builds on what the school already records rather
than asking teachers to type grades twice:

* **A report cycle** ("Autumn report", Interim / Full / End of year) covers
  some year groups and is built on one *assessment point*: each subject's
  working-at and predicted grade, attitude to learning, homework and the
  subject teacher's comment come from that point. It also says what the
  report includes - attendance, targets (with progress against them),
  attitude, homework, subject comments, a form-tutor comment and a
  head-of-year comment - an introduction from the school, when comments are
  due and the issue date. It goes Draft -> Writing -> Checking -> Closed.
* **Comments.** While a cycle is Writing, each form tutor writes a comment
  for their tutees and each head of year for their year (the reports lead,
  :data:`REPORT_EDITORS`, can write any). A shared comment bank gives
  starting points; ``{first_name}`` and ``{name}`` are filled in.
* **Checking.** :func:`problems` lists what's missing from a pupil's report
  (no grades, a subject they're taught with no grade, a comment not written,
  the assessment point not yet published). The lead marks reports Ready (or
  Withheld, with a reason - e.g. a family the school mustn't send to).
* **Issuing.** Ready reports are issued only once the assessment point is
  published: the report is frozen as it stands (later changes to grades
  don't alter what parents were sent), appears in the parent and pupil
  portals, and is e-mailed to each contact with parental responsibility who
  accepts school e-mail. An issued report can be withdrawn (with a reason),
  corrected and issued again as a new version.
* **Families.** The portal shows issued reports only, records when a
  parent first opens one, and lets them acknowledge it.
* **Reports.** Progress by form (comments written, ready, issued, viewed),
  print-ready HTML (one file per pupil), and CSV.

Every change goes in ``report_audit`` and the activity log (ids only).
"""

from __future__ import annotations

import csv
import datetime as _dt
import html
import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import REPORT_EDITORS, STAFF_ROLES, Principal
from education_system.systems.secondary.core.utilities.exports import safe_cell as _safe
from education_system.systems.secondary.core.academic_calendar.school_year import today as _today
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

ValidationError = P.ValidationError
PermissionDenied = P.PermissionDenied
NotFound = P.NotFound

REPORT_TYPES: tuple[str, ...] = ("Interim", "Full", "End of year")
CYCLE_STATUSES: tuple[str, ...] = ("Draft", "Writing", "Checking", "Closed")
_CYCLE_MOVES = {("Draft", "Writing"), ("Writing", "Draft"), ("Writing", "Checking"),
                ("Checking", "Writing"), ("Checking", "Closed"), ("Closed", "Checking")}
REPORT_STATUSES: tuple[str, ...] = ("Draft", "Ready", "Issued", "Withheld")
COMMENT_KINDS: dict[str, str] = {"tutor": "Form tutor", "hoy": "Head of year"}
INCLUDES: dict[str, str] = {
    "include_attendance": "Attendance", "include_targets": "Targets",
    "include_attitude": "Attitude to learning", "include_homework": "Homework",
    "include_subject_comments": "Subject comments", "include_tutor": "Form tutor comment",
    "include_hoy": "Head of year comment"}
MAX_COMMENT = 1500
MIN_COMMENT = 20
TEMPLATE = "report_issued"
_PLACEHOLDER_RE = re.compile(r"\{([A-Za-z_]+)\}")
COMMENT_PLACEHOLDERS = ("first_name", "name")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS report_cycles (
    cycle_id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    academic_year            TEXT NOT NULL,
    name                     TEXT NOT NULL,
    report_type              TEXT NOT NULL DEFAULT 'Full',
    point_id                 INTEGER NOT NULL REFERENCES assessment_points (point_id),
    year_groups              TEXT NOT NULL,
    include_attendance       INTEGER NOT NULL DEFAULT 1,
    include_targets          INTEGER NOT NULL DEFAULT 1,
    include_attitude         INTEGER NOT NULL DEFAULT 1,
    include_homework         INTEGER NOT NULL DEFAULT 1,
    include_subject_comments INTEGER NOT NULL DEFAULT 1,
    include_tutor            INTEGER NOT NULL DEFAULT 1,
    include_hoy              INTEGER NOT NULL DEFAULT 0,
    intro                    TEXT,
    comments_due             TEXT,
    issue_date               TEXT,
    status                   TEXT NOT NULL DEFAULT 'Draft' CHECK (status IN
                             ('Draft', 'Writing', 'Checking', 'Closed')),
    notes                    TEXT,
    created_by               TEXT,
    created_at               TEXT NOT NULL DEFAULT (datetime('now')),
    updated_by               TEXT,
    updated_at               TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (academic_year, name)
);
CREATE TABLE IF NOT EXISTS report_comments (
    comment_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    cycle_id     INTEGER NOT NULL REFERENCES report_cycles (cycle_id) ON DELETE CASCADE,
    pupil_id     INTEGER NOT NULL REFERENCES pupils (pupil_id) ON DELETE CASCADE,
    kind         TEXT NOT NULL CHECK (kind IN ('tutor', 'hoy')),
    comment      TEXT NOT NULL,
    written_by   TEXT,
    updated_at   TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (cycle_id, pupil_id, kind)
);
CREATE TABLE IF NOT EXISTS report_comment_bank (
    bank_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    kind         TEXT NOT NULL DEFAULT 'any' CHECK (kind IN ('tutor', 'hoy', 'any')),
    category     TEXT NOT NULL DEFAULT 'General',
    text         TEXT NOT NULL,
    created_by   TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS pupil_reports (
    report_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    cycle_id         INTEGER NOT NULL REFERENCES report_cycles (cycle_id) ON DELETE CASCADE,
    pupil_id         INTEGER NOT NULL REFERENCES pupils (pupil_id) ON DELETE CASCADE,
    status           TEXT NOT NULL DEFAULT 'Draft' CHECK (status IN
                     ('Draft', 'Ready', 'Issued', 'Withheld')),
    version          INTEGER NOT NULL DEFAULT 0,
    content          TEXT,
    withheld_reason  TEXT,
    checked_by       TEXT,
    checked_at       TEXT,
    issued_by        TEXT,
    issued_at        TEXT,
    first_viewed_at  TEXT,
    view_count       INTEGER NOT NULL DEFAULT 0,
    acknowledged_by  TEXT,
    acknowledged_at  TEXT,
    UNIQUE (cycle_id, pupil_id)
);
CREATE TABLE IF NOT EXISTS report_audit (
    audit_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    cycle_id     INTEGER,
    pupil_id     INTEGER,
    action       TEXT NOT NULL,
    detail       TEXT,
    actor        TEXT NOT NULL,
    at           TEXT NOT NULL DEFAULT (datetime('now'))
);
"""
database.register_schema("reports_to_parents", _SCHEMA)


@dataclass(frozen=True)
class Cycle:
    cycle_id: int
    academic_year: str
    name: str
    report_type: str
    point_id: int
    year_groups: str
    include_attendance: bool
    include_targets: bool
    include_attitude: bool
    include_homework: bool
    include_subject_comments: bool
    include_tutor: bool
    include_hoy: bool
    intro: str | None
    comments_due: str | None
    issue_date: str | None
    status: str
    notes: str | None
    created_by: str | None
    created_at: str
    updated_by: str | None
    updated_at: str
    point_name: str = ""
    point_status: str = ""

    @property
    def years(self) -> tuple[int, ...]:
        return tuple(int(y) for y in self.year_groups.split(",") if y)

    @property
    def years_label(self) -> str:
        return ", ".join(map(str, self.years))

    @property
    def title(self) -> str:
        return f"{self.name} {self.academic_year}"


@dataclass(frozen=True)
class Report:
    report_id: int
    cycle_id: int
    pupil_id: int
    status: str
    version: int
    content: str | None
    withheld_reason: str | None
    checked_by: str | None
    checked_at: str | None
    issued_by: str | None
    issued_at: str | None
    first_viewed_at: str | None
    view_count: int
    acknowledged_by: str | None
    acknowledged_at: str | None

    @property
    def snapshot(self) -> dict[str, Any] | None:
        return json.loads(self.content) if self.content else None


@dataclass(frozen=True)
class BankComment:
    bank_id: int
    kind: str
    category: str
    text: str
    created_by: str | None
    created_at: str


_C_SELECT = ("SELECT c.*, a.name AS point_name, a.status AS point_status FROM report_cycles c "
             "JOIN assessment_points a USING (point_id)")
_C_BASE = tuple(f for f in Cycle.__dataclass_fields__ if f not in ("point_name", "point_status"))


def _cycle(r) -> Cycle:
    d = {k: r[k] for k in _C_BASE}
    for k in INCLUDES:
        d[k] = bool(d[k])
    return Cycle(**d, point_name=r["point_name"], point_status=r["point_status"])


def _report(r) -> Report:
    return Report(**{k: r[k] for k in Report.__dataclass_fields__})


# ── Helpers ──────────────────────────────────────────────────────────

def _now() -> str:
    return _dt.datetime.now().isoformat(timespec="seconds")


def is_editor(actor: Principal) -> bool:
    return actor.role in REPORT_EDITORS


def _deny(actor: Principal, action: str, target: Any, message: str) -> None:
    activity_log.record(f"reports.{action}", target=target, outcome="denied", principal=actor)
    raise PermissionDenied(message)


def _require_editor(actor: Principal, action: str, target: Any = None) -> None:
    if not is_editor(actor):
        _deny(actor, action, target, "Only the reports lead can do that.")


def _audit(conn, action: str, actor: Principal, cycle_id: int | None, pupil_id: int | None,
           **detail: Any) -> None:
    conn.execute("INSERT INTO report_audit (cycle_id, pupil_id, action, detail, actor) VALUES "
                 "(?, ?, ?, ?, ?)", (cycle_id, pupil_id, action,
                                     json.dumps(detail, default=str) if detail else None,
                                     actor.username or "unknown"))


def history(cycle_id: int | None = None, *, pupil_id: int | None = None, limit: int = 300
            ) -> list[dict[str, Any]]:
    sql, where, params = "SELECT * FROM report_audit", [], []
    if cycle_id is not None:
        where.append("cycle_id = ?")
        params.append(int(cycle_id))
    if pupil_id is not None:
        where.append("pupil_id = ?")
        params.append(int(pupil_id))
    if where:
        sql += " WHERE " + " AND ".join(where)
    with database.connect() as conn:
        return [{"at": r["at"], "pupil_id": r["pupil_id"], "action": r["action"],
                 "actor": r["actor"], "detail": json.loads(r["detail"] or "{}")}
                for r in conn.execute(sql + " ORDER BY audit_id DESC LIMIT ?",
                                      (*params, int(limit)))]


def _date(value: Any, label: str, problems: list[str]) -> str | None:
    if value in (None, ""):
        return None
    try:
        return _dt.date.fromisoformat(str(value).strip()).isoformat()
    except ValueError:
        problems.append(f"{label} must be a date (YYYY-MM-DD)")
        return None


def _flag(v: Any) -> int:
    if isinstance(v, str):
        return int(v.strip().lower() in ("1", "y", "yes", "true", "on"))
    return int(bool(v))


def _me(actor: Principal) -> set[str]:
    """The signed-in person's username, name and e-mail (lower case), for
    matching them to a form tutor / head of year."""
    from education_system.systems.secondary.infrastructure.authentication import accounts
    out = {(actor.username or "").lower()}
    try:
        for s in accounts.staff_logins():
            if s["username"].lower() == (actor.username or "").lower():
                out |= {(s["display_name"] or "").lower(), (s["email"] or "").lower()}
    except Exception:  # noqa: BLE001 - matching falls back to the username
        pass
    return {x for x in out if x}


def tutor_for(pupil: P.Pupil) -> dict[str, str]:
    from education_system.systems.secondary.modules.curriculum.domain import form_groups as FG
    d = FG.details_for(pupil)
    f = FG.find(pupil.year_group, pupil.form_group) if pupil.form_group else None
    return {"name": d["form_tutor"], "email": d["form_tutor_email"],
            "co_tutor": (f.co_tutor_name if f else "") or ""}


def head_of_year(year_group: int) -> dict[str, str]:
    from education_system.systems.secondary.modules.curriculum.domain import year_groups as YG
    y = YG.get(year_group)
    return {"name": y.head_of_year or "", "email": y.head_of_year_email or ""}


def can_write(actor: Principal, pupil: P.Pupil, kind: str) -> bool:
    """The reports lead, the pupil's form tutor (tutor comment) or their head
    of year (either comment)."""
    if is_editor(actor):
        return True
    if actor.role not in STAFF_ROLES:
        return False
    me = _me(actor)
    hoy = head_of_year(pupil.year_group)
    if {hoy["name"].lower(), hoy["email"].lower()} & me - {""}:
        return True
    if kind == "tutor":
        t = tutor_for(pupil)
        return bool({t["name"].lower(), t["email"].lower(), t["co_tutor"].lower()} & me
                    - {""})
    return False


# ── Cycles ───────────────────────────────────────────────────────────

def get_cycle(cycle_id: int) -> Cycle:
    with database.connect() as conn:
        r = conn.execute(_C_SELECT + " WHERE c.cycle_id = ?", (int(cycle_id),)).fetchone()
    if r is None:
        raise NotFound(f"No report cycle #{cycle_id}")
    return _cycle(r)


def list_cycles(*, academic_year: str | None = None, status: str | None = None
                ) -> list[Cycle]:
    sql, where, params = _C_SELECT, [], []
    if academic_year:
        where.append("c.academic_year = ?")
        params.append(academic_year)
    if status:
        where.append("c.status = ?")
        params.append(status)
    if where:
        sql += " WHERE " + " AND ".join(where)
    with database.connect() as conn:
        return [_cycle(r) for r in conn.execute(
            sql + " ORDER BY c.academic_year DESC, COALESCE(c.issue_date, c.created_at) DESC, "
                  "c.cycle_id DESC", params)]


EDITABLE_FIELDS = ("name", "report_type", "point_id", "year_groups", *INCLUDES, "intro",
                   "comments_due", "issue_date", "notes")


def _clean_cycle(data: dict[str, Any], current: Cycle | None) -> dict[str, Any]:
    from education_system.systems.secondary.modules.assessment.domain import assessment_points as AP
    problems: list[str] = []
    merged = {k: getattr(current, k) for k in EDITABLE_FIELDS} if current else {}
    merged.update({k: v for k, v in data.items() if k in EDITABLE_FIELDS})
    out: dict[str, Any] = {}
    name = " ".join(str(merged.get("name") or "").split())
    if not name:
        problems.append("Name is required")
    elif len(name) > 80:
        problems.append("Name is too long")
    out["name"] = name
    rt = str(merged.get("report_type") or "Full").strip()
    hit = next((t for t in REPORT_TYPES if t.lower() == rt.lower()), None)
    if hit is None:
        problems.append(f"Type must be one of {', '.join(REPORT_TYPES)}")
    out["report_type"] = hit
    pt = None
    try:
        pt = AP.get_point(int(merged.get("point_id") or 0))
    except (ValueError, TypeError, NotFound):
        problems.append("Choose the assessment point the report is built on")
    out["point_id"] = pt.point_id if pt else None
    raw = merged.get("year_groups")
    if isinstance(raw, (list, tuple)):
        raw = ",".join(map(str, raw))
    years = sorted({int(y) for y in re.split(r"[,\s]+", str(raw or "")) if y.isdigit()})
    if not years:
        years = list(pt.years) if pt else []
    if not years or any(y not in range(7, 12) for y in years):
        problems.append("Year groups must be between 7 and 11")
    elif pt and set(years) - set(pt.years):
        problems.append(f"{pt.name} doesn't cover Year "
                        + ", ".join(map(str, sorted(set(years) - set(pt.years)))))
    out["year_groups"] = ",".join(map(str, years))
    for k in INCLUDES:
        out[k] = _flag(merged.get(k, 1 if k != "include_hoy" else 0))
    out["intro"] = (str(merged.get("intro") or "").strip()[:3000]) or None
    out["notes"] = (str(merged.get("notes") or "").strip()[:2000]) or None
    out["comments_due"] = _date(merged.get("comments_due"), "Comments due", problems)
    out["issue_date"] = _date(merged.get("issue_date"), "Issue date", problems)
    if out["comments_due"] and out["issue_date"] and out["issue_date"] < out["comments_due"]:
        problems.append("The issue date is before comments are due")
    if problems:
        raise ValidationError(problems)
    out["academic_year"] = pt.academic_year  # type: ignore[union-attr]
    return out


def create_cycle(data: dict[str, Any], *, actor: Principal) -> Cycle:
    _require_editor(actor, "cycle.create")
    c = _clean_cycle(data, None)
    cols = ["academic_year", *EDITABLE_FIELDS]
    with database.connect() as conn:
        if conn.execute("SELECT 1 FROM report_cycles WHERE academic_year = ? AND name = ?",
                        (c["academic_year"], c["name"])).fetchone():
            raise ValidationError([f"There is already a '{c['name']}' for "
                                   f"{c['academic_year']}"])
        cid = conn.execute(
            f"INSERT INTO report_cycles ({', '.join(cols)}, created_by, updated_by) VALUES "
            f"({', '.join('?' * len(cols))}, ?, ?)",
            (*(c[k] for k in cols), actor.username, actor.username)).lastrowid
        _audit(conn, "cycle.create", actor, cid, None, name=c["name"])
    activity_log.record("reports.cycle.create", target=f"cycle:{cid}", principal=actor)
    return get_cycle(cid)


def update_cycle(cycle_id: int, changes: dict[str, Any], *, actor: Principal) -> Cycle:
    cy = get_cycle(cycle_id)
    _require_editor(actor, "cycle.update", f"cycle:{cy.cycle_id}")
    if cy.status == "Closed":
        raise ValidationError(["The cycle is closed - reopen it to make changes"])
    c = _clean_cycle(changes, cy)
    if (c["point_id"] != cy.point_id or c["year_groups"] != cy.year_groups) and \
            _ever_issued(cy.cycle_id):
        raise ValidationError(["Reports have been issued - the assessment point and years "
                               "can't change now"])
    changed = [k for k in ("academic_year", *EDITABLE_FIELDS)
               if c[k] != (int(getattr(cy, k)) if k in INCLUDES else getattr(cy, k))]
    if not changed:
        return cy
    with database.connect() as conn:
        if "name" in changed and conn.execute(
                "SELECT 1 FROM report_cycles WHERE academic_year = ? AND name = ? AND "
                "cycle_id != ?", (c["academic_year"], c["name"], cy.cycle_id)).fetchone():
            raise ValidationError([f"There is already a '{c['name']}' for "
                                   f"{c['academic_year']}"])
        conn.execute("UPDATE report_cycles SET " + ", ".join(f"{k} = ?" for k in changed)
                     + ", updated_by = ?, updated_at = datetime('now') WHERE cycle_id = ?",
                     (*(c[k] for k in changed), actor.username, cy.cycle_id))
        _audit(conn, "cycle.update", actor, cy.cycle_id, None, fields=changed)
    activity_log.record("reports.cycle.update", target=f"cycle:{cy.cycle_id}", principal=actor)
    return get_cycle(cy.cycle_id)


def set_cycle_status(cycle_id: int, status: str, *, actor: Principal) -> Cycle:
    cy = get_cycle(cycle_id)
    _require_editor(actor, "cycle.status", f"cycle:{cy.cycle_id}")
    st = next((s for s in CYCLE_STATUSES if s.lower() == str(status).lower()), None)
    if st is None:
        raise ValidationError([f"Status must be one of {', '.join(CYCLE_STATUSES)}"])
    if st == cy.status:
        return cy
    if (cy.status, st) not in _CYCLE_MOVES:
        raise ValidationError([f"A cycle that is {cy.status} can't move to {st}"])
    if st == "Closed":
        open_ = [r for r in list_reports(cy.cycle_id) if r[1] and r[1].status == "Ready"]
        if open_:
            raise ValidationError([f"{len(open_)} report(s) are Ready but not issued - issue "
                                   "or reset them first"])
    with database.connect() as conn:
        conn.execute("UPDATE report_cycles SET status = ?, updated_by = ?, updated_at = "
                     "datetime('now') WHERE cycle_id = ?", (st, actor.username, cy.cycle_id))
        _audit(conn, "cycle.status", actor, cy.cycle_id, None, frm=cy.status, to=st)
    activity_log.record("reports.cycle.status", target=f"cycle:{cy.cycle_id}",
                        principal=actor, status=st)
    return get_cycle(cy.cycle_id)


def delete_cycle(cycle_id: int, *, actor: Principal) -> bool:
    cy = get_cycle(cycle_id)
    _require_editor(actor, "cycle.delete", f"cycle:{cy.cycle_id}")
    if issued_count(cy.cycle_id) or _ever_issued(cy.cycle_id):
        raise ValidationError(["Reports from this cycle have been sent to families - it can't "
                               "be deleted"])
    with database.connect() as conn:
        conn.execute("DELETE FROM report_cycles WHERE cycle_id = ?", (cy.cycle_id,))
        _audit(conn, "cycle.delete", actor, cy.cycle_id, None, name=cy.name)
    activity_log.record("reports.cycle.delete", target=f"cycle:{cy.cycle_id}", principal=actor)
    return True


def issued_count(cycle_id: int) -> int:
    with database.connect() as conn:
        return conn.execute("SELECT COUNT(*) FROM pupil_reports WHERE cycle_id = ? AND "
                            "status = 'Issued'", (int(cycle_id),)).fetchone()[0]


def _ever_issued(cycle_id: int) -> bool:
    with database.connect() as conn:
        return conn.execute("SELECT 1 FROM pupil_reports WHERE cycle_id = ? AND version > 0",
                            (int(cycle_id),)).fetchone() is not None


# ── Pupils and their reports ─────────────────────────────────────────

def pupils_in(cycle: Cycle | int, *, form_group: str | None = None) -> list[P.Pupil]:
    cy = cycle if isinstance(cycle, Cycle) else get_cycle(cycle)
    out: list[P.Pupil] = []
    for y in cy.years:
        out += P.list_pupils(year_group=y, form_group=form_group or None)
    return out


def get_report(report_id: int) -> Report:
    with database.connect() as conn:
        r = conn.execute("SELECT * FROM pupil_reports WHERE report_id = ?",
                         (int(report_id),)).fetchone()
    if r is None:
        raise NotFound(f"No report #{report_id}")
    return _report(r)


def report_for(cycle_id: int, pupil_id: int) -> Report | None:
    with database.connect() as conn:
        r = conn.execute("SELECT * FROM pupil_reports WHERE cycle_id = ? AND pupil_id = ?",
                         (int(cycle_id), int(pupil_id))).fetchone()
    return _report(r) if r else None


def _ensure(conn, cycle_id: int, pupil_id: int) -> Report:
    conn.execute("INSERT OR IGNORE INTO pupil_reports (cycle_id, pupil_id) VALUES (?, ?)",
                 (cycle_id, pupil_id))
    return _report(conn.execute("SELECT * FROM pupil_reports WHERE cycle_id = ? AND "
                                "pupil_id = ?", (cycle_id, pupil_id)).fetchone())


def list_reports(cycle_id: int, *, form_group: str | None = None, year_group: int | None = None,
                 status: str | None = None) -> list[tuple[P.Pupil, Report | None]]:
    """Every pupil the cycle covers (on roll now, or with a report) with their
    report row, if one exists yet. ``status='Draft'`` includes pupils with
    no row."""
    cy = get_cycle(cycle_id)
    with database.connect() as conn:
        rows = {r["pupil_id"]: _report(r) for r in conn.execute(
            "SELECT * FROM pupil_reports WHERE cycle_id = ?", (cy.cycle_id,))}
    pupils = {p.pupil_id: p for p in pupils_in(cy)}
    for pid in rows:
        if pid not in pupils:
            p = P.get_pupil(pid)
            if p:
                pupils[pid] = p
    out = []
    for p in sorted(pupils.values(), key=lambda p: (p.year_group, p.form_group or "",
                                                    p.legal_last_name.lower(),
                                                    p.legal_first_name.lower())):
        if form_group and p.form_group != form_group:
            continue
        if year_group and p.year_group != int(year_group):
            continue
        r = rows.get(p.pupil_id)
        if status and (r.status if r else "Draft") != status:
            continue
        out.append((p, r))
    return out


def _covers(cy: Cycle, pupil: P.Pupil) -> None:
    if pupil.year_group not in cy.years and report_for(cy.cycle_id, pupil.pupil_id) is None:
        raise ValidationError([f"{pupil.display_name} is in Year {pupil.year_group}, which "
                               f"{cy.name} doesn't cover"])


def _pupil(pupil_id: int) -> P.Pupil:
    p = P.get_pupil(int(pupil_id))
    if p is None:
        raise NotFound(f"No pupil with id {pupil_id}")
    return p


# ── Comments ─────────────────────────────────────────────────────────

def comments(cycle_id: int, pupil_id: int | None = None) -> dict[tuple[int, str], dict]:
    sql, params = "SELECT * FROM report_comments WHERE cycle_id = ?", [int(cycle_id)]
    if pupil_id is not None:
        sql += " AND pupil_id = ?"
        params.append(int(pupil_id))
    with database.connect() as conn:
        return {(r["pupil_id"], r["kind"]): {"comment": r["comment"],
                                             "written_by": r["written_by"],
                                             "updated_at": r["updated_at"]}
                for r in conn.execute(sql, params)}


def fill_placeholders(text: str, pupil: P.Pupil) -> str:
    first = pupil.preferred_name or pupil.legal_first_name
    values = {"first_name": first, "name": f"{first} {pupil.legal_last_name}"}
    return _PLACEHOLDER_RE.sub(lambda m: values.get(m.group(1), m.group(0)), text)


def set_comment(cycle_id: int, pupil_id: int, kind: str, text: str, *, actor: Principal
                ) -> str | None:
    """Write (or, with blank text, remove) a tutor / head-of-year comment.
    Returns the saved comment."""
    cy = get_cycle(cycle_id)
    p = _pupil(pupil_id)
    if kind not in COMMENT_KINDS:
        raise ValidationError([f"Comment kind must be one of {', '.join(COMMENT_KINDS)}"])
    if not can_write(actor, p, kind):
        _deny(actor, "comment", p.admission_no,
              f"Only {p.display_name}'s {'form tutor, ' if kind == 'tutor' else ''}head of "
              f"year or the reports lead can write this comment.")
    problems: list[str] = []
    if cy.status != "Writing" and not (cy.status == "Checking" and is_editor(actor)):
        problems.append(f"{cy.name} isn't open for comments (it's {cy.status})")
    if not getattr(cy, f"include_{kind}"):
        problems.append(f"{cy.name} doesn't include a {COMMENT_KINDS[kind].lower()} comment")
    _covers(cy, p)
    rep = report_for(cy.cycle_id, p.pupil_id)
    if rep and rep.status in ("Issued", "Ready"):
        problems.append(f"{p.display_name}'s report is {rep.status} - the reports lead must "
                        "reset it before the comment can change")
    body = fill_placeholders((text or "").replace("\r\n", "\n").strip(), p)
    left = _PLACEHOLDER_RE.findall(body)
    if left:
        problems.append("Unknown placeholder(s): " + ", ".join("{" + x + "}" for x in left))
    if body and len(body) > MAX_COMMENT:
        problems.append(f"The comment is too long ({len(body)} characters; the limit is "
                        f"{MAX_COMMENT})")
    if body and len(body) < MIN_COMMENT:
        problems.append(f"The comment is too short (at least {MIN_COMMENT} characters)")
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        if body:
            conn.execute(
                "INSERT INTO report_comments (cycle_id, pupil_id, kind, comment, written_by) "
                "VALUES (?, ?, ?, ?, ?) ON CONFLICT (cycle_id, pupil_id, kind) DO UPDATE SET "
                "comment = excluded.comment, written_by = excluded.written_by, updated_at = "
                "datetime('now')", (cy.cycle_id, p.pupil_id, kind, body, actor.username))
        else:
            conn.execute("DELETE FROM report_comments WHERE cycle_id = ? AND pupil_id = ? AND "
                         "kind = ?", (cy.cycle_id, p.pupil_id, kind))
        _audit(conn, "comment" if body else "comment.clear", actor, cy.cycle_id, p.pupil_id,
               kind=kind, chars=len(body))
    activity_log.record("reports.comment", target=p.admission_no, principal=actor, kind=kind)
    return body or None


def my_pupils(cycle_id: int, actor: Principal, kind: str = "tutor") -> list[P.Pupil]:
    """The pupils whose *kind* comment the signed-in person can write."""
    cy = get_cycle(cycle_id)
    return [p for p in pupils_in(cy) if can_write(actor, p, kind)]


# ── Comment bank ─────────────────────────────────────────────────────

def bank(kind: str | None = None) -> list[BankComment]:
    sql, params = "SELECT * FROM report_comment_bank", []
    if kind:
        sql += " WHERE kind IN (?, 'any')"
        params.append(kind)
    with database.connect() as conn:
        return [BankComment(**{k: r[k] for k in BankComment.__dataclass_fields__})
                for r in conn.execute(sql + " ORDER BY category COLLATE NOCASE, bank_id",
                                      params)]


def add_bank(text: str, *, actor: Principal, kind: str = "any", category: str = "General"
             ) -> BankComment:
    if actor.role not in STAFF_ROLES:
        _deny(actor, "bank.add", None, "Only staff can add to the comment bank.")
    problems = []
    t = (text or "").strip()
    if len(t) < MIN_COMMENT or len(t) > MAX_COMMENT:
        problems.append(f"A bank comment is {MIN_COMMENT}-{MAX_COMMENT} characters")
    bad = [x for x in _PLACEHOLDER_RE.findall(t) if x not in COMMENT_PLACEHOLDERS]
    if bad:
        problems.append("Unknown placeholder(s): " + ", ".join("{" + x + "}" for x in bad)
                        + " - use {first_name} or {name}")
    if kind not in ("tutor", "hoy", "any"):
        problems.append("Kind must be tutor, hoy or any")
    if problems:
        raise ValidationError(problems)
    cat = " ".join((category or "General").split())[:40] or "General"
    with database.connect() as conn:
        bid = conn.execute("INSERT INTO report_comment_bank (kind, category, text, created_by) "
                           "VALUES (?, ?, ?, ?)", (kind, cat, t, actor.username)).lastrowid
        _audit(conn, "bank.add", actor, None, None, bank_id=bid)
        r = conn.execute("SELECT * FROM report_comment_bank WHERE bank_id = ?",
                         (bid,)).fetchone()
    return BankComment(**{k: r[k] for k in BankComment.__dataclass_fields__})


def delete_bank(bank_id: int, *, actor: Principal) -> bool:
    with database.connect() as conn:
        r = conn.execute("SELECT created_by FROM report_comment_bank WHERE bank_id = ?",
                         (int(bank_id),)).fetchone()
    if r is None:
        raise NotFound(f"No bank comment {bank_id}")
    if not is_editor(actor) and (r[0] or "").lower() != (actor.username or "").lower():
        _deny(actor, "bank.delete", None, "Only the person who added it or the reports lead "
                                          "can remove a bank comment.")
    with database.connect() as conn:
        conn.execute("DELETE FROM report_comment_bank WHERE bank_id = ?", (int(bank_id),))
        _audit(conn, "bank.delete", actor, None, None, bank_id=int(bank_id))
    return True


# ── What a report says ───────────────────────────────────────────────

def content(cycle_id: int, pupil_id: int) -> dict[str, Any]:
    """The report as it stands now (an issued one is frozen in its
    snapshot instead)."""
    from education_system.systems.secondary.modules.assessment.domain import assessment_points as AP
    from education_system.systems.secondary.modules.assessment.domain import target_grades as TGR
    cy = get_cycle(cycle_id)
    p = _pupil(pupil_id)
    tutor = tutor_for(p)
    out: dict[str, Any] = {
        "cycle": {"id": cy.cycle_id, "name": cy.name, "title": cy.title,
                  "type": cy.report_type, "academic_year": cy.academic_year,
                  "issue_date": cy.issue_date or _today().isoformat(), "intro": cy.intro,
                  "point": cy.point_name,
                  "includes": {k: getattr(cy, k) for k in INCLUDES}},
        "pupil": {"id": p.pupil_id, "name": p.display_name, "admission_no": p.admission_no,
                  "first_name": p.preferred_name or p.legal_first_name,
                  "year_group": p.year_group, "form_group": p.form_group or "",
                  "tutor": tutor["name"], "tutor_email": tutor["email"]},
    }
    targets = {}
    if cy.include_targets:
        targets = {t.subject_id: t.target_grade for t in TGR.list_targets(pupil_id=p.pupil_id)}
    subjects = []
    from education_system.systems.secondary.modules.curriculum.domain import subjects as S
    for g in AP.pupil_report(cy.point_id, p.pupil_id):
        try:
            name = S.get(g.subject_id).name
        except Exception:  # noqa: BLE001 - a removed subject shows its code
            name = g.subject_code
        row: dict[str, Any] = {"subject": name, "code": g.subject_code,
                               "working_at": g.working_at, "predicted": g.predicted}
        if cy.include_targets:
            tgt = targets.get(g.subject_id)
            row["target"] = tgt
            row["progress"] = TGR.progress_status(tgt, g.working_at) if tgt else None
        if cy.include_attitude:
            row["attitude"] = g.attitude
        if cy.include_homework:
            row["homework"] = g.homework
        if cy.include_subject_comments:
            row["comment"] = g.comment
        subjects.append(row)
    out["subjects"] = sorted(subjects, key=lambda r: r["subject"].lower())
    if cy.include_attendance:
        from education_system.systems.secondary.modules.attendance.domain import attendance as AT
        try:
            s = AT.pupil_summary(p.pupil_id)
            out["attendance"] = {"pct": s.attendance_pct, "possible": s.possible,
                                 "authorised": s.authorised, "unauthorised": s.unauthorised,
                                 "late": s.late, "band": s.band}
        except Exception:  # noqa: BLE001 - no register data yet
            out["attendance"] = None
    cm = comments(cy.cycle_id, p.pupil_id)
    out["comments"] = {k: (cm.get((p.pupil_id, k)) or {}).get("comment")
                       for k in COMMENT_KINDS if getattr(cy, f"include_{k}")}
    out["key"] = {"attitude": {str(k): v for k, v in AP.ATTITUDE.items()}}
    return out


def problems(cycle_id: int, pupil_id: int) -> list[str]:
    """What's missing from a pupil's report."""
    from education_system.systems.secondary.modules.curriculum.domain import teaching_groups as TG
    cy = get_cycle(cycle_id)
    p = _pupil(pupil_id)
    c = content(cy.cycle_id, p.pupil_id)
    out = []
    if cy.point_status != "Published":
        out.append(f"{cy.point_name} isn't published yet")
    if not c["subjects"]:
        out.append(f"No grades in {cy.point_name}")
    else:
        have = {s["code"] for s in c["subjects"] if s["working_at"]}
        taught = {g.subject.code for g in TG.groups_for_pupil(p.pupil_id, cy.academic_year)}
        missing = sorted(taught - have)
        if missing:
            out.append("No grade for " + ", ".join(missing))
    for k, label in COMMENT_KINDS.items():
        if getattr(cy, f"include_{k}") and not c["comments"].get(k):
            out.append(f"No {label.lower()} comment")
    return out


def _set_status(conn, rep: Report, status: str, actor: Principal, **extra: Any) -> None:
    sets = {"status": status, **extra}
    conn.execute("UPDATE pupil_reports SET " + ", ".join(f"{k} = ?" for k in sets)
                 + " WHERE report_id = ?", (*sets.values(), rep.report_id))


def mark_ready(cycle_id: int, pupil_ids: list[int], *, actor: Principal,
               force: bool = False) -> dict[str, Any]:
    """Mark reports checked and ready to issue. Ones with problems are
    skipped unless *force*. Returns {'ready': n, 'skipped': {adm: [why]}}."""
    cy = get_cycle(cycle_id)
    _require_editor(actor, "ready", f"cycle:{cy.cycle_id}")
    if cy.status not in ("Writing", "Checking"):
        raise ValidationError([f"{cy.name} is {cy.status} - move it to Checking first"])
    n, skipped = 0, {}
    for pid in dict.fromkeys(int(x) for x in pupil_ids):
        p = _pupil(pid)
        _covers(cy, p)
        rep = report_for(cy.cycle_id, pid)
        if rep and rep.status in ("Issued", "Withheld"):
            skipped[p.admission_no] = [f"already {rep.status.lower()}"]
            continue
        issues = [x for x in problems(cy.cycle_id, pid) if "isn't published" not in x]
        if issues and not force:
            skipped[p.admission_no] = issues
            continue
        with database.connect() as conn:
            rep = _ensure(conn, cy.cycle_id, pid)
            _set_status(conn, rep, "Ready", actor, checked_by=actor.username, checked_at=_now())
            _audit(conn, "ready", actor, cy.cycle_id, pid, forced=bool(issues))
        n += 1
    activity_log.record("reports.ready", target=f"cycle:{cy.cycle_id}", principal=actor,
                        ready=n, skipped=len(skipped))
    return {"ready": n, "skipped": skipped}


def reset(cycle_id: int, pupil_id: int, *, actor: Principal) -> Report:
    """Ready / Withheld back to Draft (so comments can change)."""
    cy = get_cycle(cycle_id)
    _require_editor(actor, "reset", f"cycle:{cy.cycle_id}")
    rep = report_for(cy.cycle_id, pupil_id)
    if rep is None or rep.status == "Draft":
        raise ValidationError(["That report is already a draft"])
    if rep.status == "Issued":
        raise ValidationError(["An issued report is withdrawn, not reset"])
    with database.connect() as conn:
        _set_status(conn, rep, "Draft", actor, withheld_reason=None, checked_by=None,
                    checked_at=None)
        _audit(conn, "reset", actor, cy.cycle_id, rep.pupil_id, frm=rep.status)
    return get_report(rep.report_id)


def withhold(cycle_id: int, pupil_id: int, reason: str, *, actor: Principal) -> Report:
    cy = get_cycle(cycle_id)
    _require_editor(actor, "withhold", f"cycle:{cy.cycle_id}")
    p = _pupil(pupil_id)
    _covers(cy, p)
    why = " ".join((reason or "").split())[:300]
    if not why:
        raise ValidationError(["Give a reason for withholding the report"])
    rep = report_for(cy.cycle_id, p.pupil_id)
    if rep and rep.status == "Issued":
        raise ValidationError(["The report has been issued - withdraw it instead"])
    with database.connect() as conn:
        rep = _ensure(conn, cy.cycle_id, p.pupil_id)
        _set_status(conn, rep, "Withheld", actor, withheld_reason=why)
        _audit(conn, "withhold", actor, cy.cycle_id, p.pupil_id)
    activity_log.record("reports.withhold", target=p.admission_no, principal=actor)
    return get_report(rep.report_id)


def _recipients(pupil_ids: list[int]) -> dict[int, list[tuple[str, str]]]:
    from education_system.systems.secondary.modules.pupils.domain import contacts as C
    found = C.emailable_for_pupils(pupil_ids)
    return {pid: [(c.email, c.full_name) for c in cs if c.email and c.parental_responsibility]
            for pid, cs in found.items()}


def issue(cycle_id: int, pupil_ids: list[int] | None = None, *, actor: Principal,
          email: bool = True) -> dict[str, Any]:
    """Issue Ready reports (all of them, or the pupils given). Each is frozen,
    shown in the portals and e-mailed to contacts with parental
    responsibility. Returns {'issued': [Report], 'message_id': id or None,
    'emails': n, 'no_email': [Pupil], 'skipped': {adm: why}}."""
    from education_system.systems.secondary.modules.communication.domain import email_outbox as E
    from education_system.systems.secondary.modules.communication.domain import email_templates
    cy = get_cycle(cycle_id)
    _require_editor(actor, "issue", f"cycle:{cy.cycle_id}")
    problems_: list[str] = []
    if cy.status != "Checking":
        problems_.append(f"{cy.name} is {cy.status} - reports are issued while it's Checking")
    if cy.point_status != "Published":
        problems_.append(f"Publish {cy.point_name} first - its grades aren't final yet")
    if problems_:
        raise ValidationError(problems_)
    rows = {p.pupil_id: (p, r) for p, r in list_reports(cy.cycle_id)}
    wanted = list(rows) if pupil_ids is None else [int(x) for x in pupil_ids]
    todo, skipped = [], {}
    for pid in wanted:
        p, r = rows.get(pid, (P.get_pupil(pid), None))
        if p is None:
            continue
        if r is None or r.status != "Ready":
            if pupil_ids is not None:
                skipped[p.admission_no] = f"not ready ({r.status if r else 'Draft'})"
            continue
        if p.roll_status != "on_roll":
            skipped[p.admission_no] = "no longer on roll"
            continue
        todo.append((p, r))
    if not todo:
        raise ValidationError(["No reports are ready to issue"
                               + (": " + "; ".join(f"{k} {v}" for k, v in skipped.items())
                                  if skipped else "")])
    issued, letters, no_email = [], [], []
    send_to = _recipients([p.pupil_id for p, _r in todo]) if email else {}
    template = email_templates.load_template(TEMPLATE) if email else None
    for p, r in todo:
        snap = content(cy.cycle_id, p.pupil_id)
        snap["version"] = r.version + 1
        snap["issued_at"] = _now()
        with database.connect() as conn:
            _set_status(conn, r, "Issued", actor, content=json.dumps(snap, default=str),
                        version=r.version + 1, issued_by=actor.username,
                        issued_at=snap["issued_at"], first_viewed_at=None, view_count=0,
                        acknowledged_by=None, acknowledged_at=None)
            _audit(conn, "issue", actor, cy.cycle_id, p.pupil_id, version=r.version + 1)
        issued.append(get_report(r.report_id))
        if template is None:
            continue
        to = send_to.get(p.pupil_id, [])
        if not to:
            no_email.append(p)
        tutor = snap["pupil"]["tutor"]
        line = (f" ({tutor}" + (f", {snap['pupil']['tutor_email']}"
                                if snap["pupil"]["tutor_email"] else "") + ")") if tutor else ""
        text = render_text(snap)
        for address, name in to:
            subject, body = template.render({
                "recipient_name": name, "pupil_name": p.display_name,
                "pupil_first_name": snap["pupil"]["first_name"], "report_name": cy.title,
                "report": text, "tutor_line": line})
            letters.append((address, name, subject, body))
    mid = None
    if letters:
        mid = E.save_prepared("report_to_parents", cy.title, cy.title,
                              "(one report per pupil)", letters, actor=actor)
    activity_log.record("reports.issue", target=f"cycle:{cy.cycle_id}", principal=actor,
                        issued=len(issued), emails=len(letters))
    return {"issued": issued, "message_id": mid, "emails": len(letters), "no_email": no_email,
            "skipped": skipped}


def withdraw(report_id: int, reason: str, *, actor: Principal) -> Report:
    """Take an issued report back (families no longer see it) so it can be
    corrected and issued again as a new version."""
    rep = get_report(report_id)
    _require_editor(actor, "withdraw", f"report:{rep.report_id}")
    why = " ".join((reason or "").split())[:300]
    if rep.status != "Issued":
        raise ValidationError(["Only an issued report can be withdrawn"])
    if not why:
        raise ValidationError(["Give a reason for withdrawing the report"])
    cy = get_cycle(rep.cycle_id)
    if cy.status == "Closed":
        raise ValidationError(["The cycle is closed - reopen it (Checking) first"])
    with database.connect() as conn:
        _set_status(conn, rep, "Draft", actor, content=None, checked_by=None, checked_at=None)
        _audit(conn, "withdraw", actor, rep.cycle_id, rep.pupil_id, reason=why,
               version=rep.version)
    activity_log.record("reports.withdraw", target=f"report:{rep.report_id}", principal=actor)
    return get_report(rep.report_id)


# ── Progress ─────────────────────────────────────────────────────────

def progress(cycle_id: int) -> list[dict[str, Any]]:
    """Per form: pupils, tutor / head-of-year comments written, ready,
    issued, withheld, viewed by a family."""
    cy = get_cycle(cycle_id)
    cm = comments(cy.cycle_id)
    groups: dict[tuple[int, str], dict[str, Any]] = {}
    for p, r in list_reports(cy.cycle_id):
        key = (p.year_group, p.form_group or "")
        g = groups.setdefault(key, {"year_group": key[0], "form_group": key[1] or "(no form)",
                                    "tutor": tutor_for(p)["name"], "pupils": 0, "tutor_done": 0,
                                    "hoy_done": 0, **{s: 0 for s in REPORT_STATUSES},
                                    "viewed": 0})
        g["pupils"] += 1
        g["tutor_done"] += (p.pupil_id, "tutor") in cm
        g["hoy_done"] += (p.pupil_id, "hoy") in cm
        g[r.status if r else "Draft"] += 1
        g["viewed"] += bool(r and r.status == "Issued" and r.first_viewed_at)
    return [groups[k] for k in sorted(groups)]


def summary(cycle_id: int) -> dict[str, Any]:
    rows = progress(cycle_id)
    tot = Counter()
    for r in rows:
        for k in ("pupils", "tutor_done", "hoy_done", *REPORT_STATUSES, "viewed"):
            tot[k] += r[k]
    return dict(tot)


# ── Families ─────────────────────────────────────────────────────────

def for_family(pupil_id: int) -> list[tuple[Cycle, Report]]:
    """Issued reports, newest first (what the portals show)."""
    with database.connect() as conn:
        rows = conn.execute("SELECT * FROM pupil_reports WHERE pupil_id = ? AND status = "
                            "'Issued' ORDER BY issued_at DESC", (int(pupil_id),)).fetchall()
    return [(get_cycle(r["cycle_id"]), _report(r)) for r in rows]


def family_view(report_id: int, pupil_id: int, *, principal: Principal) -> dict[str, Any]:
    """The frozen report for a portal (the caller has checked the link to
    *pupil_id*). A parent opening it is recorded."""
    rep = get_report(report_id)
    if rep.pupil_id != int(pupil_id) or rep.status != "Issued":
        raise NotFound("That report isn't available")
    if principal.is_parent:
        with database.connect() as conn:
            conn.execute("UPDATE pupil_reports SET view_count = view_count + 1, "
                         "first_viewed_at = COALESCE(first_viewed_at, ?) WHERE report_id = ?",
                         (_now(), rep.report_id))
        activity_log.record("reports.viewed", target=f"report:{rep.report_id}",
                            principal=principal)
        rep = get_report(rep.report_id)
    return {"report": rep, "content": rep.snapshot}


def acknowledge(report_id: int, pupil_id: int, *, principal: Principal) -> Report:
    """A parent confirms they've read it."""
    rep = get_report(report_id)
    if rep.pupil_id != int(pupil_id) or rep.status != "Issued":
        raise NotFound("That report isn't available")
    if not principal.is_parent:
        raise PermissionDenied("Only a parent or carer can acknowledge a report.")
    if rep.acknowledged_at:
        return rep
    with database.connect() as conn:
        conn.execute("UPDATE pupil_reports SET acknowledged_by = ?, acknowledged_at = ?, "
                     "first_viewed_at = COALESCE(first_viewed_at, ?) WHERE report_id = ?",
                     (principal.username, _now(), _now(), rep.report_id))
        _audit(conn, "acknowledge", principal, rep.cycle_id, rep.pupil_id)
    activity_log.record("reports.acknowledge", target=f"report:{rep.report_id}",
                        principal=principal)
    return get_report(rep.report_id)


def for_pupil(pupil_id: int) -> list[dict[str, Any]]:
    """Staff view for the pupil profile: every cycle the pupil has a report in."""
    with database.connect() as conn:
        rows = conn.execute("SELECT * FROM pupil_reports WHERE pupil_id = ? ORDER BY "
                            "report_id DESC", (int(pupil_id),)).fetchall()
    return [{"cycle": get_cycle(r["cycle_id"]), "report": _report(r)} for r in rows]


# ── Rendering ────────────────────────────────────────────────────────

def _label(v: Any, key: dict[str, str] | None = None) -> str:
    if v in (None, ""):
        return "-"
    return f"{v} ({key[str(v)]})" if key and str(v) in key else str(v)


def render_text(c: dict[str, Any]) -> str:
    cy, p, inc = c["cycle"], c["pupil"], c["cycle"]["includes"]
    att_key = c.get("key", {}).get("attitude", {})
    lines = [f"{cy['title']} - {p['name']}",
             f"Year {p['year_group']}" + (f", form {p['form_group']}" if p["form_group"] else "")
             + (f" - tutor {p['tutor']}" if p["tutor"] else ""),
             f"Issued {cy['issue_date']}", ""]
    if cy.get("intro"):
        lines += [cy["intro"], ""]
    if c["subjects"]:
        lines.append("Subjects")
        for s in c["subjects"]:
            bits = [f"working at {_label(s['working_at'])}"]
            if s.get("predicted"):
                bits.append(f"predicted {s['predicted']}")
            if inc.get("include_targets") and s.get("target"):
                bits.append(f"target {s['target']} ({s.get('progress') or 'no data'})")
            if inc.get("include_attitude") and s.get("attitude"):
                bits.append(f"attitude {_label(s['attitude'], att_key)}")
            if inc.get("include_homework") and s.get("homework"):
                bits.append(f"homework {_label(s['homework'], att_key)}")
            lines.append(f"  {s['subject']}: " + ", ".join(bits))
            if inc.get("include_subject_comments") and s.get("comment"):
                lines.append(f"    {s['comment']}")
        lines.append("")
    a = c.get("attendance")
    if inc.get("include_attendance"):
        lines.append("Attendance this year: " + (
            f"{a['pct']}% ({a['late']} late mark(s), {a['unauthorised']} unauthorised "
            f"session(s))" if a and a.get("pct") is not None else "no figures yet"))
        lines.append("")
    for k, label in COMMENT_KINDS.items():
        if k in c.get("comments", {}):
            lines += [f"{label}:", c["comments"][k] or "-", ""]
    if inc.get("include_attitude") or inc.get("include_homework"):
        lines.append("Attitude and homework: " + ", ".join(f"{k} = {v.lower()}"
                                                          for k, v in att_key.items()))
    return "\n".join(lines).strip()


def render_html(c: dict[str, Any], *, school_name: str = "Secondary School") -> str:
    e = html.escape
    cy, p, inc = c["cycle"], c["pupil"], c["cycle"]["includes"]
    att_key = c.get("key", {}).get("attitude", {})
    cols = ["Subject", "Working at", "Predicted"]
    if inc.get("include_targets"):
        cols += ["Target", "Progress"]
    if inc.get("include_attitude"):
        cols.append("Attitude")
    if inc.get("include_homework"):
        cols.append("Homework")
    rows = []
    for s in c["subjects"]:
        cells = [s["subject"], _label(s["working_at"]), _label(s.get("predicted"))]
        if inc.get("include_targets"):
            cells += [_label(s.get("target")), _label(s.get("progress"))]
        if inc.get("include_attitude"):
            cells.append(_label(s.get("attitude")))
        if inc.get("include_homework"):
            cells.append(_label(s.get("homework")))
        rows.append("<tr>" + "".join(f"<td>{e(str(x))}</td>" for x in cells) + "</tr>")
        if inc.get("include_subject_comments") and s.get("comment"):
            rows.append(f'<tr class="c"><td colspan="{len(cols)}">{e(s["comment"])}</td></tr>')
    a = c.get("attendance")
    parts = [f"<h1>{e(school_name)}</h1>", f"<h2>{e(cy['title'])}</h2>",
             f"<p><b>{e(p['name'])}</b> &middot; Year {p['year_group']}"
             + (f" &middot; form {e(p['form_group'])}" if p["form_group"] else "")
             + (f" &middot; tutor {e(p['tutor'])}" if p["tutor"] else "")
             + f"<br>Issued {e(cy['issue_date'])}</p>"]
    if cy.get("intro"):
        parts.append(f"<p>{e(cy['intro'])}</p>")
    if rows:
        parts.append("<table><tr>" + "".join(f"<th>{e(x)}</th>" for x in cols) + "</tr>"
                     + "".join(rows) + "</table>")
    if inc.get("include_attendance"):
        parts.append("<p><b>Attendance this year:</b> " + (
            f"{a['pct']}% &middot; {a['late']} late &middot; {a['unauthorised']} unauthorised"
            if a and a.get("pct") is not None else "no figures yet") + "</p>")
    for k, label in COMMENT_KINDS.items():
        if k in c.get("comments", {}):
            parts.append(f"<h3>{e(label)}</h3><p>{e(c['comments'][k] or '-')}</p>")
    if inc.get("include_attitude") or inc.get("include_homework"):
        parts.append('<p class="k">Attitude and homework: '
                     + ", ".join(f"{e(k)} = {e(v.lower())}" for k, v in att_key.items())
                     + "</p>")
    return ("<!doctype html><html><head><meta charset='utf-8'><title>"
            f"{e(cy['title'])} - {e(p['name'])}</title><style>"
            "body{font-family:sans-serif;max-width:800px;margin:2em auto;color:#222}"
            "table{border-collapse:collapse;width:100%}td,th{border:1px solid #bbb;"
            "padding:4px 6px;text-align:left}tr.c td{color:#444;font-style:italic}"
            ".k{color:#666;font-size:90%}@media print{body{margin:0}}"
            "</style></head><body>" + "".join(parts) + "</body></html>")


def _school_name() -> str:
    from education_system.systems.secondary.modules.communication.domain import letters
    return letters.school_name()


def view(cycle_id: int, pupil_id: int) -> dict[str, Any]:
    """The issued snapshot if there is one, else the live draft."""
    rep = report_for(cycle_id, pupil_id)
    if rep and rep.status == "Issued" and rep.snapshot:
        return rep.snapshot
    return content(cycle_id, pupil_id)


def export_html(cycle_id: int, folder: str | Path, *, actor: Principal,
                pupil_ids: list[int] | None = None, form_group: str | None = None) -> int:
    """One print-ready HTML file per pupil (issued snapshot, or the draft)."""
    if actor.role not in STAFF_ROLES:
        _deny(actor, "export_html", None, "Only staff can export reports.")
    cy = get_cycle(cycle_id)
    out = Path(folder)
    out.mkdir(parents=True, exist_ok=True)
    school = _school_name()
    pupils = [p for p, _r in list_reports(cy.cycle_id, form_group=form_group)
              if pupil_ids is None or p.pupil_id in set(pupil_ids)]
    for p in pupils:
        safe = re.sub(r"[^A-Za-z0-9_-]+", "_", f"{p.admission_no}_{p.legal_last_name}")
        (out / f"{safe}.html").write_text(render_html(view(cy.cycle_id, p.pupil_id),
                                                      school_name=school), encoding="utf-8")
    activity_log.record("reports.export_html", target=f"cycle:{cy.cycle_id}", principal=actor,
                        files=len(pupils))
    return len(pupils)


def export_csv(cycle_id: int, path: str | Path, *, actor: Principal) -> int:
    """Where every pupil's report has got to."""
    if actor.role not in STAFF_ROLES:
        _deny(actor, "export_csv", None, "Only staff can export reports.")
    cy = get_cycle(cycle_id)
    cm = comments(cy.cycle_id)
    rows = list_reports(cy.cycle_id)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["admission_no", "pupil", "year", "form", "tutor_comment", "hoy_comment",
                    "status", "version", "issued_at", "first_viewed_at", "acknowledged_at",
                    "withheld_reason"])
        for p, r in rows:
            w.writerow([_safe(p.admission_no), _safe(p.display_name), p.year_group,
                        _safe(p.form_group), "yes" if (p.pupil_id, "tutor") in cm else "",
                        "yes" if (p.pupil_id, "hoy") in cm else "",
                        r.status if r else "Draft", r.version if r else 0,
                        (r.issued_at or "") if r else "", (r.first_viewed_at or "") if r else "",
                        (r.acknowledged_at or "") if r else "",
                        _safe(r.withheld_reason) if r else ""])
    activity_log.record("reports.export_csv", target=f"cycle:{cy.cycle_id}", principal=actor,
                        rows=len(rows))
    return len(rows)
