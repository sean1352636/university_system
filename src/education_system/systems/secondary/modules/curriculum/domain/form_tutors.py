"""Form tutors: who tutors each form, and the tutor's record of their work.

Kept from the old system:

* **Assignments**: a tutor for a form in an academic year with a role
  (Tutor, Co-tutor, Cover, Mentor), contact e-mail, start / end date, status
  (Active, Ended, Suspended, Provisional) and notes; the same person can't
  hold the same role on the same form twice in a year; End sets the end
  date; the per-assignment summary and the cohort summary (by status, role,
  year; how many tutors and forms).
* **Meetings**: logged against an assignment - date, type (Form time,
  1-to-1, Parent contact, Pastoral, Behaviour, Attendance, Wellbeing,
  Other), pupils present, agenda, decisions, follow-up actions and notes.

New:

* **One record of the form tutor.** An assignment is made against a *form
  group record*, not a typed form name. The active Tutor (or, while the
  tutor is suspended, the active Cover) is written to the form's tutor name
  and e-mail, and the active Co-tutor to its co-tutor - which is what
  reports to parents, e-mails and the pupil profile already read. A form
  has at most one active Tutor and one active Co-tutor at a time.
  :func:`import_from_forms` brings in tutors already typed on Form Groups;
  :func:`mismatches` shows where the two disagree.
* **Staff logins.** The tutor is picked from the school's staff logins, so
  the tutor can be recognised when they sign in; a typed name still works.
* **Carry forward.** :func:`carry_forward` copies the year's active
  assignments to the next year (forms move up with their tutor at the
  rollover) and ends the old ones on 31 August.
* **Pupils in meetings.** A meeting can be linked to particular pupils
  (a 1-to-1 or a parent contact), so the pupil profile shows their tutor
  contacts and the tutor sees when they last spoke to each tutee.
* **Follow-ups.** A follow-up can have a due date and be marked done;
  :func:`follow_ups` lists the open ones, overdue first.
* **My form.** :func:`form_overview` puts the tutor's tutees side by side:
  attendance this year (and persistent-absence band), open interventions,
  last 1-to-1 and whether the family has a contact who takes e-mail.
* **Coverage.** Forms with no active tutor this year, tutors with more than
  one form, and assignments for forms that have been archived.
* **Who.** The form-tutor lead (:data:`FORM_TUTOR_EDITORS`) assigns tutors
  and sees every meeting. A tutor logs, edits and deletes meetings for
  their own form(s) and sees only those; heads of year see their year's.
  Every change goes in ``form_tutor_audit`` and the activity log (ids only).
"""

from __future__ import annotations

import csv
import datetime as _dt
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from education_system.systems.secondary.modules.curriculum.domain import form_groups as FG
from education_system.systems.secondary.modules.pupils.domain import contacts as C
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import (
    FORM_TUTOR_EDITORS,
    STAFF_ROLES,
    Principal,
)
from education_system.systems.secondary.core.utilities.exports import safe_cell as _safe
from education_system.systems.secondary.core.academic_calendar.school_year import current_year, next_year
from education_system.systems.secondary.core.academic_calendar.school_year import today as _today
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

ValidationError = P.ValidationError
PermissionDenied = P.PermissionDenied
NotFound = P.NotFound

ROLES: tuple[str, ...] = ("Tutor", "Co-tutor", "Cover", "Mentor")
DEFAULT_ROLE = "Tutor"
ASSIGNMENT_STATUSES: tuple[str, ...] = ("Active", "Ended", "Suspended", "Provisional")
DEFAULT_ASSIGNMENT_STATUS = "Active"
MEETING_TYPES: tuple[str, ...] = ("Form time", "1-to-1", "Parent contact", "Pastoral",
                                  "Behaviour", "Attendance", "Wellbeing", "Other")
DEFAULT_MEETING_TYPE = "Form time"
#: Roles that set the form record's tutor / co-tutor (one active each per form).
SINGLE_ROLES = ("Tutor", "Co-tutor")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS form_tutor_assignments (
    assignment_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    form_id         INTEGER NOT NULL REFERENCES form_groups (form_id),
    academic_year   TEXT NOT NULL,
    tutor_name      TEXT NOT NULL,
    tutor_username  TEXT,
    role            TEXT NOT NULL DEFAULT 'Tutor' CHECK (role IN
                    ('Tutor', 'Co-tutor', 'Cover', 'Mentor')),
    contact_email   TEXT,
    start_date      TEXT NOT NULL,
    end_date        TEXT,
    status          TEXT NOT NULL DEFAULT 'Active' CHECK (status IN
                    ('Active', 'Ended', 'Suspended', 'Provisional')),
    notes           TEXT,
    created_by      TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_by      TEXT,
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_form_tutor_one_active
    ON form_tutor_assignments (form_id, academic_year, role)
    WHERE status = 'Active' AND role IN ('Tutor', 'Co-tutor');
CREATE INDEX IF NOT EXISTS ix_form_tutor_form ON form_tutor_assignments (form_id, academic_year);
CREATE TABLE IF NOT EXISTS form_tutor_meetings (
    meeting_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    assignment_id     INTEGER NOT NULL REFERENCES form_tutor_assignments (assignment_id)
                      ON DELETE CASCADE,
    meeting_date      TEXT NOT NULL,
    meeting_type      TEXT NOT NULL DEFAULT 'Form time',
    pupils_present    TEXT,
    agenda            TEXT,
    decisions         TEXT,
    follow_up_actions TEXT,
    follow_up_due     TEXT,
    follow_up_done_at TEXT,
    follow_up_done_by TEXT,
    notes             TEXT,
    created_by        TEXT,
    created_at        TEXT NOT NULL DEFAULT (datetime('now')),
    updated_by        TEXT,
    updated_at        TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS form_tutor_meeting_pupils (
    meeting_id  INTEGER NOT NULL REFERENCES form_tutor_meetings (meeting_id) ON DELETE CASCADE,
    pupil_id    INTEGER NOT NULL REFERENCES pupils (pupil_id) ON DELETE CASCADE,
    PRIMARY KEY (meeting_id, pupil_id)
);
CREATE TABLE IF NOT EXISTS form_tutor_audit (
    audit_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    assignment_id INTEGER,
    meeting_id    INTEGER,
    action        TEXT NOT NULL,
    detail        TEXT,
    actor         TEXT NOT NULL,
    at            TEXT NOT NULL DEFAULT (datetime('now'))
);
"""
database.register_schema("form_tutors", _SCHEMA)


@dataclass(frozen=True)
class TutorAssignment:
    assignment_id: int
    form_id: int
    academic_year: str
    tutor_name: str
    tutor_username: str | None
    role: str
    contact_email: str | None
    start_date: str
    end_date: str | None
    status: str
    notes: str | None
    created_by: str | None
    created_at: str
    updated_by: str | None
    updated_at: str
    year_group: int = 0
    form_group: str = ""
    form_status: str = "active"

    @property
    def form_label(self) -> str:
        return f"{self.form_group} (Year {self.year_group})"


@dataclass(frozen=True)
class TutorMeeting:
    meeting_id: int
    assignment_id: int
    meeting_date: str
    meeting_type: str
    pupils_present: str | None
    agenda: str | None
    decisions: str | None
    follow_up_actions: str | None
    follow_up_due: str | None
    follow_up_done_at: str | None
    follow_up_done_by: str | None
    notes: str | None
    created_by: str | None
    created_at: str
    updated_by: str | None
    updated_at: str
    tutor_name: str | None = None
    year_group: int | None = None
    form_group: str | None = None
    pupil_ids: tuple[int, ...] = ()

    @property
    def follow_up_open(self) -> bool:
        return bool(self.follow_up_actions) and not self.follow_up_done_at


_A_SELECT = ("SELECT a.*, f.year_group, f.name AS form_group, f.status AS form_status "
             "FROM form_tutor_assignments a JOIN form_groups f USING (form_id)")
_A_BASE = tuple(f for f in TutorAssignment.__dataclass_fields__
                if f not in ("year_group", "form_group", "form_status"))
_M_SELECT = ("SELECT m.*, a.tutor_name, a.form_id, f.year_group, f.name AS form_group "
             "FROM form_tutor_meetings m JOIN form_tutor_assignments a USING (assignment_id) "
             "JOIN form_groups f USING (form_id)")
_M_BASE = tuple(f for f in TutorMeeting.__dataclass_fields__
                if f not in ("tutor_name", "year_group", "form_group", "pupil_ids"))


def _assignment(r) -> TutorAssignment:
    return TutorAssignment(**{k: r[k] for k in _A_BASE}, year_group=r["year_group"],
                           form_group=r["form_group"], form_status=r["form_status"])


def _meeting(r, pupils: dict[int, tuple[int, ...]]) -> TutorMeeting:
    return TutorMeeting(**{k: r[k] for k in _M_BASE}, tutor_name=r["tutor_name"],
                        year_group=r["year_group"], form_group=r["form_group"],
                        pupil_ids=pupils.get(r["meeting_id"], ()))


# ── Helpers ──────────────────────────────────────────────────────────

def year_end(year: str) -> str:
    return f"{int(year[:4]) + 1}-08-31"


def is_editor(actor: Principal) -> bool:
    return actor.role in FORM_TUTOR_EDITORS


def _deny(actor: Principal, action: str, target: Any, message: str) -> None:
    activity_log.record(f"form_tutors.{action}", target=target, outcome="denied",
                        principal=actor)
    raise PermissionDenied(message)


def _require_editor(actor: Principal, action: str, target: Any = None) -> None:
    if not is_editor(actor):
        _deny(actor, action, target, "Only the form-tutor lead can change tutor assignments.")


def _audit(conn, action: str, actor: Principal, assignment_id: int | None = None,
           meeting_id: int | None = None, **detail: Any) -> None:
    conn.execute("INSERT INTO form_tutor_audit (assignment_id, meeting_id, action, detail, "
                 "actor) VALUES (?, ?, ?, ?, ?)",
                 (assignment_id, meeting_id, action,
                  json.dumps(detail, default=str) if detail else None,
                  actor.username or "unknown"))


def history(assignment_id: int | None = None, *, limit: int = 300) -> list[dict[str, Any]]:
    sql, params = "SELECT * FROM form_tutor_audit", []
    if assignment_id is not None:
        sql += " WHERE assignment_id = ?"
        params.append(int(assignment_id))
    with database.connect() as conn:
        return [{"at": r["at"], "assignment_id": r["assignment_id"],
                 "meeting_id": r["meeting_id"], "action": r["action"], "actor": r["actor"],
                 "detail": json.loads(r["detail"] or "{}")}
                for r in conn.execute(sql + " ORDER BY audit_id DESC LIMIT ?",
                                      (*params, int(limit)))]


def _date(value: Any, label: str, problems: list[str], *, default: str | None = None
          ) -> str | None:
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        return default
    try:
        return _dt.date.fromisoformat(str(value).strip()).isoformat()
    except ValueError:
        problems.append(f"{label} must be a date (YYYY-MM-DD)")
        return None


def _choice(value: Any, options: tuple[str, ...], label: str, problems: list[str],
            default: str) -> str:
    v = str(value or "").strip()
    if not v:
        return default
    hit = next((o for o in options if o.lower() == v.lower()), None)
    if hit is None:
        problems.append(f"{label} must be one of {', '.join(options)}")
        return default
    return hit


def _text(value: Any, limit: int = 2000) -> str | None:
    t = str(value or "").strip()
    return t[:limit] or None


def _staff() -> list[dict]:
    from education_system.systems.secondary.infrastructure.authentication import accounts
    try:
        return accounts.staff_logins()
    except Exception:  # noqa: BLE001 - the login list is a convenience
        return []


def staff_names() -> list[str]:
    return [f"{s['display_name']} ({s['username']})" for s in _staff()]


def _person(value: Any) -> tuple[str | None, str | None, str | None]:
    """(name, username, e-mail) from a staff pick ("Name (username)"), a
    username, a login's display name, or a typed name."""
    text = _text(value, 100)
    if not text:
        return None, None, None
    key = text.lower()
    if key.endswith(")") and "(" in key:
        key = key[key.rindex("(") + 1:-1].strip()
    for s in _staff():
        if key in (s["username"].lower(), (s["display_name"] or "").lower()):
            return s["display_name"] or s["username"], s["username"], s["email"]
    return text, None, None


def _me(actor: Principal) -> set[str]:
    out = {(actor.username or "").lower()}
    for s in _staff():
        if s["username"].lower() == (actor.username or "").lower():
            out |= {(s["display_name"] or "").lower(), (s["email"] or "").lower()}
    return {x for x in out if x}


def _is_mine(a: TutorAssignment, me: set[str]) -> bool:
    return bool({(a.tutor_username or "").lower(), a.tutor_name.lower(),
                 (a.contact_email or "").lower()} & me - {""})


def _form(form_ref: Any) -> FG.FormGroup:
    if isinstance(form_ref, FG.FormGroup):
        return form_ref
    if isinstance(form_ref, int) or str(form_ref).isdigit():
        return FG.get(int(form_ref))
    raise ValidationError(["Choose the form group"])


# ── Assignments ──────────────────────────────────────────────────────

def get_assignment(assignment_id: int) -> TutorAssignment:
    with database.connect() as conn:
        r = conn.execute(_A_SELECT + " WHERE a.assignment_id = ?",
                         (int(assignment_id),)).fetchone()
    if r is None:
        raise NotFound(f"No tutor assignment #{assignment_id}")
    return _assignment(r)


def list_assignments(*, year_group: int | str | None = None, form_id: int | None = None,
                     academic_year: str | None = None, tutor: str | None = None,
                     status: str | None = None, role: str | None = None
                     ) -> list[TutorAssignment]:
    sql, where, params = _A_SELECT, [], []
    if year_group not in (None, ""):
        where.append("f.year_group = ?")
        params.append(int(year_group))
    for col, val in (("a.form_id", form_id), ("a.academic_year", academic_year),
                     ("a.status", status), ("a.role", role)):
        if val not in (None, ""):
            where.append(f"{col} = ?")
            params.append(val)
    if tutor:
        where.append("(lower(a.tutor_name) = ? OR lower(COALESCE(a.tutor_username, '')) = ?)")
        params += [tutor.lower(), tutor.lower()]
    if where:
        sql += " WHERE " + " AND ".join(where)
    with database.connect() as conn:
        return [_assignment(r) for r in conn.execute(
            sql + " ORDER BY a.academic_year DESC, f.year_group, f.name, CASE a.role WHEN "
                  "'Tutor' THEN 0 WHEN 'Co-tutor' THEN 1 WHEN 'Cover' THEN 2 ELSE 3 END, "
                  "a.tutor_name", params)]


FIELDS = ("form_id", "academic_year", "tutor_name", "tutor_username", "role", "contact_email",
          "start_date", "end_date", "status", "notes")


def _clean(data: dict[str, Any], current: TutorAssignment | None
           ) -> tuple[dict[str, Any], list[str]]:
    problems: list[str] = []
    merged = {k: getattr(current, k) for k in FIELDS} if current else {}
    merged.update({k: v for k, v in data.items() if k in FIELDS or k == "tutor"})
    out: dict[str, Any] = {}
    try:
        f = _form(merged.get("form_id"))
        out["form_id"] = f.form_id
        if not f.is_active and (current is None or current.form_id != f.form_id):
            problems.append(f"{f.label} is archived")
    except (NotFound, ValidationError):
        problems.append("Choose the form group")
        out["form_id"] = None
    ay = str(merged.get("academic_year") or current_year()).strip()
    if len(ay) != 7 or ay[4] != "/" or not ay[:4].isdigit() or not ay[5:].isdigit() or \
            (int(ay[:4]) + 1) % 100 != int(ay[5:]):
        problems.append("Academic year must look like 2026/27")
    out["academic_year"] = ay
    new_person = current is None or bool(data.get("tutor") or data.get("tutor_name"))
    if new_person:
        name, user, login_email = _person(data.get("tutor") or data.get("tutor_name"))
        if not name:
            problems.append("Tutor is required")
        if current is not None and name and user is None and \
                name.lower() == current.tutor_name.lower():
            user = current.tutor_username  # same person re-typed: keep their login
        out["tutor_name"], out["tutor_username"] = name, user
    else:
        login_email = None
        out["tutor_name"], out["tutor_username"] = current.tutor_name, current.tutor_username
    typed = _text(data.get("contact_email"), 254) if "contact_email" in data else (
        None if new_person else current.contact_email)  # type: ignore[union-attr]
    email = typed or login_email
    out["contact_email"] = email.lower() if email else None
    if out["contact_email"] and not C.valid_email(out["contact_email"]):
        problems.append("Contact e-mail is not a valid address")
    out["role"] = _choice(merged.get("role"), ROLES, "Role", problems, DEFAULT_ROLE)
    out["status"] = _choice(merged.get("status"), ASSIGNMENT_STATUSES, "Status", problems,
                            DEFAULT_ASSIGNMENT_STATUS)
    out["start_date"] = _date(merged.get("start_date"), "Start date", problems,
                              default=_today().isoformat())
    out["end_date"] = _date(merged.get("end_date"), "End date", problems)
    if out["start_date"] and out["end_date"] and out["end_date"] < out["start_date"]:
        problems.append("End date cannot be before start date")
    if out["status"] == "Ended" and not out["end_date"]:
        out["end_date"] = max(_today().isoformat(), out["start_date"] or "")
    out["notes"] = _text(merged.get("notes"))
    return out, problems


def _clashes(conn, c: dict[str, Any], exclude: int | None) -> list[str]:
    out = []
    if conn.execute("SELECT 1 FROM form_tutor_assignments WHERE form_id = ? AND academic_year "
                    "= ? AND lower(tutor_name) = lower(?) AND role = ? AND assignment_id != ?",
                    (c["form_id"], c["academic_year"], c["tutor_name"], c["role"],
                     exclude or 0)).fetchone():
        out.append(f"{c['tutor_name']} is already {c['role']} for that form in "
                   f"{c['academic_year']}")
    if c["status"] == "Active" and c["role"] in SINGLE_ROLES:
        r = conn.execute("SELECT tutor_name FROM form_tutor_assignments WHERE form_id = ? AND "
                         "academic_year = ? AND role = ? AND status = 'Active' AND "
                         "assignment_id != ?", (c["form_id"], c["academic_year"], c["role"],
                                                exclude or 0)).fetchone()
        if r:
            out.append(f"{r[0]} is already the active {c['role'].lower()} for that form - "
                       "end or suspend their assignment first")
    return out


def _sync_form(form_id: int, actor: Principal) -> None:
    """Write the current year's active tutor (or cover) and co-tutor to the
    form record."""
    year = current_year()
    f = FG.get(form_id)
    if not f.is_active:
        return
    rows = [a for a in list_assignments(form_id=form_id, academic_year=year)
            if a.status == "Active"]
    tutor = next((a for a in rows if a.role == "Tutor"), None) or \
        next((a for a in rows if a.role == "Cover"), None)
    co = next((a for a in rows if a.role == "Co-tutor"), None)
    if not list_assignments(form_id=form_id, academic_year=year):
        return  # no assignments this year: keep what was typed on Form Groups
    want = {"tutor_name": tutor.tutor_name if tutor else None,
            "tutor_email": tutor.contact_email if tutor else None,
            "co_tutor_name": co.tutor_name if co else None}
    changes = {k: v for k, v in want.items() if getattr(f, k) != v}
    if changes:
        # Only the form-tutor lead gets here; Form Groups' editors are the same set,
        # and the change shows in the form's own history.
        FG.update(form_id, changes, actor=actor)


def create_assignment(data: dict[str, Any], *, actor: Principal) -> TutorAssignment:
    """New assignment (the old New)."""
    _require_editor(actor, "assignment.create")
    c, problems = _clean(data, None)
    with database.connect() as conn:
        if not problems:
            problems += _clashes(conn, c, None)
        if problems:
            activity_log.record("form_tutors.assignment.create", outcome="invalid",
                                principal=actor, problems=len(problems))
            raise ValidationError(problems)
        aid = conn.execute(
            f"INSERT INTO form_tutor_assignments ({', '.join(FIELDS)}, created_by, "
            f"updated_by) VALUES ({', '.join('?' * len(FIELDS))}, ?, ?)",
            (*(c[k] for k in FIELDS), actor.username, actor.username)).lastrowid
        _audit(conn, "assignment.create", actor, aid, role=c["role"], status=c["status"])
    _sync_form(c["form_id"], actor)
    activity_log.record("form_tutors.assignment.create", target=f"FG{c['form_id']}",
                        principal=actor, role=c["role"])
    return get_assignment(aid)


def update_assignment(assignment_id: int, changes: dict[str, Any], *, actor: Principal
                      ) -> TutorAssignment:
    """Edit an assignment (the old Edit)."""
    a = get_assignment(assignment_id)
    _require_editor(actor, "assignment.update", f"FG{a.form_id}")
    c, problems = _clean(changes, a)
    with database.connect() as conn:
        if not problems:
            problems += _clashes(conn, c, a.assignment_id)
        if problems:
            raise ValidationError(problems)
        changed = [k for k in FIELDS if c[k] != getattr(a, k)]
        if not changed:
            return a
        conn.execute("UPDATE form_tutor_assignments SET "
                     + ", ".join(f"{k} = ?" for k in changed)
                     + ", updated_by = ?, updated_at = datetime('now') WHERE assignment_id = ?",
                     (*(c[k] for k in changed), actor.username, a.assignment_id))
        _audit(conn, "assignment.update", actor, a.assignment_id, fields=changed)
    for fid in {a.form_id, c["form_id"]}:
        _sync_form(fid, actor)
    activity_log.record("form_tutors.assignment.update", target=f"FG{c['form_id']}",
                        principal=actor, fields=",".join(changed))
    return get_assignment(a.assignment_id)


def end_assignment(assignment_id: int, end_date: str | None = None, *, actor: Principal
                   ) -> TutorAssignment:
    """The old End: status Ended, end date today unless given."""
    a = get_assignment(assignment_id)
    return update_assignment(a.assignment_id, {
        "status": "Ended", "end_date": end_date or max(_today().isoformat(), a.start_date)},
        actor=actor)


def delete_assignment(assignment_id: int, *, actor: Principal) -> bool:
    """Delete an assignment and its meetings (the old Delete). An assignment
    with meetings is better ended - this asks for that via the caller."""
    a = get_assignment(assignment_id)
    _require_editor(actor, "assignment.delete", f"FG{a.form_id}")
    with database.connect() as conn:
        n = conn.execute("SELECT COUNT(*) FROM form_tutor_meetings WHERE assignment_id = ?",
                         (a.assignment_id,)).fetchone()[0]
        conn.execute("DELETE FROM form_tutor_assignments WHERE assignment_id = ?",
                     (a.assignment_id,))
        _audit(conn, "assignment.delete", actor, a.assignment_id, meetings=n,
               tutor=a.tutor_name, role=a.role)
    _sync_form(a.form_id, actor)
    activity_log.record("form_tutors.assignment.delete", target=f"FG{a.form_id}",
                        principal=actor, meetings=n)
    return True


def meeting_count(assignment_id: int) -> int:
    with database.connect() as conn:
        return conn.execute("SELECT COUNT(*) FROM form_tutor_meetings WHERE assignment_id = ?",
                            (int(assignment_id),)).fetchone()[0]


# ── Joining up with Form Groups ──────────────────────────────────────

def import_from_forms(*, actor: Principal, academic_year: str | None = None) -> dict[str, int]:
    """Create an active Tutor / Co-tutor assignment for each open form whose
    record names a tutor that has no assignment yet this year."""
    _require_editor(actor, "import")
    year = academic_year or current_year()
    made = skipped = 0
    for f in FG.list_forms():
        have = {a.role for a in list_assignments(form_id=f.form_id, academic_year=year)
                if a.status == "Active"}
        for role, name, email in (("Tutor", f.tutor_name, f.tutor_email),
                                  ("Co-tutor", f.co_tutor_name, None)):
            if not name or role in have:
                continue
            try:
                create_assignment({"form_id": f.form_id, "academic_year": year,
                                   "tutor": name, "contact_email": email, "role": role,
                                   "start_date": P.academic_year_start().isoformat(),
                                   "notes": "Taken from the form group record"}, actor=actor)
                made += 1
            except ValidationError:
                skipped += 1
    activity_log.record("form_tutors.import", principal=actor, created=made, skipped=skipped)
    return {"created": made, "skipped": skipped}


def mismatches(academic_year: str | None = None) -> list[dict[str, Any]]:
    """Forms whose record disagrees with this year's active assignments."""
    year = academic_year or current_year()
    out = []
    for f in FG.list_forms():
        rows = [a for a in list_assignments(form_id=f.form_id, academic_year=year)
                if a.status == "Active"]
        tutor = next((a for a in rows if a.role == "Tutor"), None) or \
            next((a for a in rows if a.role == "Cover"), None)
        co = next((a for a in rows if a.role == "Co-tutor"), None)
        for label, on_form, assigned in (
                ("Tutor", f.tutor_name, tutor.tutor_name if tutor else None),
                ("Co-tutor", f.co_tutor_name, co.tutor_name if co else None)):
            if (on_form or None) != (assigned or None):
                out.append({"form": f, "role": label, "on_form": on_form,
                            "assigned": assigned})
    return out


def carry_forward(*, actor: Principal, from_year: str | None = None) -> dict[str, Any]:
    """Copy *from_year*'s active assignments on open forms to the next year
    (the forms moved up with their pupils at the rollover) and end the old
    ones on 31 August."""
    _require_editor(actor, "carry_forward")
    frm = from_year or current_year()
    to = next_year(frm)
    copied, skipped = 0, []
    for a in list_assignments(academic_year=frm, status="Active"):
        if a.form_status != "active":
            continue
        try:
            create_assignment({"form_id": a.form_id, "academic_year": to,
                               "tutor": a.tutor_username or a.tutor_name,
                               "contact_email": a.contact_email, "role": a.role,
                               "start_date": f"{to[:4]}-09-01",
                               "notes": f"Carried forward from {frm}"}, actor=actor)
            copied += 1
        except ValidationError as e:
            skipped.append(f"{a.form_label} {a.role} {a.tutor_name}: {e.problems[0]}")
            continue
        update_assignment(a.assignment_id, {"status": "Ended", "end_date": year_end(frm)},
                          actor=actor)
    activity_log.record("form_tutors.carry_forward", principal=actor, copied=copied,
                        skipped=len(skipped))
    return {"to_year": to, "copied": copied, "skipped": skipped}


# ── Who can see / write meetings ─────────────────────────────────────

def my_assignments(actor: Principal, *, academic_year: str | None = None,
                   active_only: bool = True) -> list[TutorAssignment]:
    me = _me(actor)
    return [a for a in list_assignments(academic_year=academic_year or current_year())
            if _is_mine(a, me) and (a.status == "Active" or not active_only)]


def _head_of_years(actor: Principal) -> set[int]:
    from education_system.systems.secondary.modules.curriculum.domain import year_groups as YG
    me = _me(actor)
    return {y.year_group for y in YG.list_all()
            if {(y.head_of_year or "").lower(), (y.head_of_year_email or "").lower()} & me
            - {""}}


def can_log(actor: Principal, a: TutorAssignment) -> bool:
    return is_editor(actor) or (actor.role in STAFF_ROLES and _is_mine(a, _me(actor)))


def can_see(actor: Principal, a: TutorAssignment) -> bool:
    return can_log(actor, a) or (actor.role in STAFF_ROLES
                                 and a.year_group in _head_of_years(actor))


def my_forms(actor: Principal) -> list[FG.FormGroup]:
    """Forms the signed-in person tutors this year (every open form for the
    lead; their year's forms for a head of year)."""
    if is_editor(actor):
        return FG.list_forms()
    ids = {a.form_id for a in my_assignments(actor)}
    years = _head_of_years(actor)
    return [f for f in FG.list_forms() if f.form_id in ids or f.year_group in years]


# ── Meetings ─────────────────────────────────────────────────────────

def _pupils_for(conn, ids: list[int]) -> dict[int, tuple[int, ...]]:
    out: dict[int, list[int]] = {}
    for start in range(0, len(ids), 500):
        chunk = ids[start:start + 500]
        for r in conn.execute("SELECT meeting_id, pupil_id FROM form_tutor_meeting_pupils "
                              f"WHERE meeting_id IN ({', '.join('?' * len(chunk))}) "
                              "ORDER BY pupil_id", chunk):
            out.setdefault(r[0], []).append(r[1])
    return {k: tuple(v) for k, v in out.items()}


def get_meeting(meeting_id: int) -> TutorMeeting:
    with database.connect() as conn:
        r = conn.execute(_M_SELECT + " WHERE m.meeting_id = ?", (int(meeting_id),)).fetchone()
        if r is None:
            raise NotFound(f"No meeting #{meeting_id}")
        return _meeting(r, _pupils_for(conn, [r["meeting_id"]]))


def list_meetings(*, actor: Principal | None = None, assignment_id: int | None = None,
                  meeting_type: str | None = None, date_from: str | None = None,
                  date_to: str | None = None, pupil_id: int | None = None,
                  form_id: int | None = None) -> list[TutorMeeting]:
    """Meetings, newest first. With *actor*, only the ones they may see."""
    problems: list[str] = []
    sql, where, params = _M_SELECT, [], []
    if assignment_id is not None:
        where.append("m.assignment_id = ?")
        params.append(int(assignment_id))
    if form_id is not None:
        where.append("a.form_id = ?")
        params.append(int(form_id))
    if meeting_type:
        where.append("m.meeting_type = ?")
        params.append(_choice(meeting_type, MEETING_TYPES, "Type", problems, ""))
    for col, val, label in (("m.meeting_date >= ?", date_from, "From date"),
                            ("m.meeting_date <= ?", date_to, "To date")):
        d = _date(val, label, problems)
        if d:
            where.append(col)
            params.append(d)
    if pupil_id is not None:
        where.append("m.meeting_id IN (SELECT meeting_id FROM form_tutor_meeting_pupils WHERE "
                     "pupil_id = ?)")
        params.append(int(pupil_id))
    if problems:
        raise ValidationError(problems)
    if where:
        sql += " WHERE " + " AND ".join(where)
    with database.connect() as conn:
        rows = conn.execute(sql + " ORDER BY m.meeting_date DESC, m.meeting_id DESC",
                            params).fetchall()
        pupils = _pupils_for(conn, [r["meeting_id"] for r in rows])
    out = [_meeting(r, pupils) for r in rows]
    if actor is not None and not is_editor(actor):
        seen: dict[int, bool] = {}
        keep = []
        for m in out:
            if m.assignment_id not in seen:
                seen[m.assignment_id] = can_see(actor, get_assignment(m.assignment_id))
            if seen[m.assignment_id]:
                keep.append(m)
        out = keep
    return out


MEETING_FIELDS = ("meeting_date", "meeting_type", "pupils_present", "agenda", "decisions",
                  "follow_up_actions", "follow_up_due", "notes")


def _clean_meeting(data: dict[str, Any], current: TutorMeeting | None, a: TutorAssignment
                   ) -> tuple[dict[str, Any], list[int], list[str]]:
    problems: list[str] = []
    merged = {k: getattr(current, k) for k in MEETING_FIELDS} if current else {}
    merged.update({k: v for k, v in data.items() if k in MEETING_FIELDS})
    out: dict[str, Any] = {}
    out["meeting_date"] = _date(merged.get("meeting_date"), "Meeting date", problems,
                                default=_today().isoformat())
    if out["meeting_date"] and out["meeting_date"] > _today().isoformat():
        problems.append("A meeting can't be logged for a future date")
    out["meeting_type"] = _choice(merged.get("meeting_type"), MEETING_TYPES, "Meeting type",
                                  problems, DEFAULT_MEETING_TYPE)
    out["pupils_present"] = _text(merged.get("pupils_present"), 500)
    for k in ("agenda", "decisions", "follow_up_actions", "notes"):
        out[k] = _text(merged.get(k))
    out["follow_up_due"] = _date(merged.get("follow_up_due"), "Follow-up due", problems)
    if out["follow_up_due"] and not out["follow_up_actions"]:
        problems.append("A follow-up due date needs the follow-up action")
    if out["follow_up_due"] and out["meeting_date"] and \
            out["follow_up_due"] < out["meeting_date"]:
        problems.append("The follow-up is due before the meeting")
    pupils: list[int] = list(current.pupil_ids) if current else []
    if "pupils" in data:
        pupils = []
        members = {p.pupil_id for p in FG.members(a.form_id)}
        for ref in data.get("pupils") or []:
            p = P.get_pupil(int(ref)) if str(ref).isdigit() else P.find_by_reference(str(ref))
            if p is None:
                problems.append(f"No pupil {ref}")
            elif p.pupil_id not in members and not (current and p.pupil_id in
                                                    current.pupil_ids):
                problems.append(f"{p.display_name} isn't in {a.form_group}")
            else:
                pupils.append(p.pupil_id)
    if out["meeting_type"] in ("1-to-1", "Parent contact") and not pupils:
        problems.append(f"Choose the pupil for a {out['meeting_type'].lower()}")
    return out, list(dict.fromkeys(pupils)), problems


def _save_pupils(conn, meeting_id: int, pupils: list[int]) -> None:
    conn.execute("DELETE FROM form_tutor_meeting_pupils WHERE meeting_id = ?", (meeting_id,))
    conn.executemany("INSERT INTO form_tutor_meeting_pupils (meeting_id, pupil_id) VALUES "
                     "(?, ?)", [(meeting_id, p) for p in pupils])


def add_meeting(assignment_id: int, data: dict[str, Any], *, actor: Principal
                ) -> TutorMeeting:
    """Log a meeting (the old Log meeting). *data* may carry ``pupils``
    (ids or admission numbers in the form)."""
    a = get_assignment(assignment_id)
    if not can_log(actor, a):
        _deny(actor, "meeting.create", f"FG{a.form_id}",
              "Only the form's tutor or the form-tutor lead can log its meetings.")
    c, pupils, problems = _clean_meeting(data, None, a)
    if a.status not in ("Active", "Suspended") and not is_editor(actor):
        problems.append(f"That assignment is {a.status}")
    if c["meeting_date"] and c["meeting_date"] < a.start_date:
        problems.append("That's before the assignment started")
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        mid = conn.execute(
            f"INSERT INTO form_tutor_meetings (assignment_id, {', '.join(MEETING_FIELDS)}, "
            f"created_by, updated_by) VALUES (?, {', '.join('?' * len(MEETING_FIELDS))}, "
            "?, ?)", (a.assignment_id, *(c[k] for k in MEETING_FIELDS), actor.username,
                      actor.username)).lastrowid
        _save_pupils(conn, mid, pupils)
        _audit(conn, "meeting.create", actor, a.assignment_id, mid, type=c["meeting_type"],
               pupils=len(pupils))
    activity_log.record("form_tutors.meeting.create", target=f"FG{a.form_id}",
                        principal=actor, type=c["meeting_type"], pupils=len(pupils))
    return get_meeting(mid)


def _require_meeting(actor: Principal, m: TutorMeeting, action: str) -> TutorAssignment:
    a = get_assignment(m.assignment_id)
    if not can_log(actor, a):
        _deny(actor, action, f"FG{a.form_id}",
              "Only the form's tutor or the form-tutor lead can change its meetings.")
    return a


def update_meeting(meeting_id: int, changes: dict[str, Any], *, actor: Principal
                   ) -> TutorMeeting:
    m = get_meeting(meeting_id)
    a = _require_meeting(actor, m, "meeting.update")
    c, pupils, problems = _clean_meeting(changes, m, a)
    if problems:
        raise ValidationError(problems)
    changed = [k for k in MEETING_FIELDS if c[k] != getattr(m, k)]
    with database.connect() as conn:
        if changed:
            conn.execute("UPDATE form_tutor_meetings SET "
                         + ", ".join(f"{k} = ?" for k in changed)
                         + ", updated_by = ?, updated_at = datetime('now') WHERE meeting_id = ?",
                         (*(c[k] for k in changed), actor.username, m.meeting_id))
        if tuple(pupils) != m.pupil_ids:
            _save_pupils(conn, m.meeting_id, pupils)
            changed.append("pupils")
        if changed:
            _audit(conn, "meeting.update", actor, a.assignment_id, m.meeting_id,
                   fields=changed)
    activity_log.record("form_tutors.meeting.update", target=f"FG{a.form_id}",
                        principal=actor)
    return get_meeting(m.meeting_id)


def delete_meeting(meeting_id: int, *, actor: Principal) -> bool:
    m = get_meeting(meeting_id)
    a = _require_meeting(actor, m, "meeting.delete")
    with database.connect() as conn:
        conn.execute("DELETE FROM form_tutor_meetings WHERE meeting_id = ?", (m.meeting_id,))
        _audit(conn, "meeting.delete", actor, a.assignment_id, m.meeting_id,
               type=m.meeting_type)
    activity_log.record("form_tutors.meeting.delete", target=f"FG{a.form_id}",
                        principal=actor)
    return True


def complete_follow_up(meeting_id: int, *, actor: Principal, undo: bool = False
                       ) -> TutorMeeting:
    m = get_meeting(meeting_id)
    a = _require_meeting(actor, m, "follow_up")
    if not m.follow_up_actions:
        raise ValidationError(["That meeting has no follow-up action"])
    with database.connect() as conn:
        conn.execute("UPDATE form_tutor_meetings SET follow_up_done_at = ?, "
                     "follow_up_done_by = ? WHERE meeting_id = ?",
                     (None if undo else _dt.datetime.now().isoformat(timespec="seconds"),
                      None if undo else actor.username, m.meeting_id))
        _audit(conn, "follow_up.reopen" if undo else "follow_up.done", actor,
               a.assignment_id, m.meeting_id)
    return get_meeting(m.meeting_id)


def follow_ups(*, actor: Principal, include_done: bool = False) -> list[TutorMeeting]:
    """Follow-up actions still to do (overdue first, then by due date)."""
    rows = [m for m in list_meetings(actor=actor) if m.follow_up_actions
            and (include_done or not m.follow_up_done_at)]
    return sorted(rows, key=lambda m: (m.follow_up_due is None, m.follow_up_due or "",
                                       m.meeting_date))


def overdue(m: TutorMeeting) -> bool:
    return m.follow_up_open and bool(m.follow_up_due) and \
        m.follow_up_due < _today().isoformat()  # type: ignore[operator]


# ── Summaries ────────────────────────────────────────────────────────

def assignment_summary(assignment_id: int, *, actor: Principal | None = None
                       ) -> dict[str, Any]:
    """The old per-assignment summary."""
    a = get_assignment(assignment_id)
    if actor is not None and not can_see(actor, a):
        raise PermissionDenied("You can't see that form's meetings.")
    meetings = list_meetings(assignment_id=a.assignment_id)
    return {"assignment": a, "meetings": meetings, "meeting_count": len(meetings),
            "by_type": dict(Counter(m.meeting_type for m in meetings)),
            "open_follow_ups": sum(1 for m in meetings if m.follow_up_open),
            "pupils_seen": len({p for m in meetings for p in m.pupil_ids})}


def cohort_summary(*, academic_year: str | None = None) -> dict[str, Any]:
    """The old cohort summary."""
    rows = list_assignments(academic_year=academic_year)
    return {"total": len(rows), "by_status": dict(Counter(r.status for r in rows)),
            "by_role": dict(Counter(r.role for r in rows)),
            "by_year": dict(Counter(r.year_group for r in rows)),
            "tutors": len({r.tutor_name.lower() for r in rows}),
            "forms": len({r.form_id for r in rows})}


def coverage(academic_year: str | None = None) -> dict[str, Any]:
    """Open forms with no active tutor, tutors with more than one form as
    Tutor, and active assignments on archived forms."""
    year = academic_year or current_year()
    rows = list_assignments(academic_year=year)
    active = [a for a in rows if a.status == "Active"]
    tutored = {a.form_id for a in active if a.role in ("Tutor", "Cover")}
    load = Counter(a.tutor_name for a in active if a.role == "Tutor")
    return {"academic_year": year,
            "no_tutor": [f for f in FG.list_forms() if f.form_id not in tutored],
            "several_forms": {n: [a.form_label for a in active if a.tutor_name == n
                                  and a.role == "Tutor"] for n, c in load.items() if c > 1},
            "archived_forms": [a for a in active if a.form_status != "active"],
            "provisional": [a for a in rows if a.status == "Provisional"]}


def form_overview(form_id: int, *, actor: Principal) -> dict[str, Any]:
    """The tutor's view of their form: each tutee with attendance, open
    interventions, last 1-to-1 / parent contact and e-mailable contact."""
    from education_system.systems.secondary.modules.attendance.domain import attendance as AT
    f = FG.get(form_id)
    if f.form_id not in {x.form_id for x in my_forms(actor)}:
        _deny(actor, "form.view", f"FG{f.form_id}", "That isn't one of your forms.")
    pupils = FG.members(f)
    ids = [p.pupil_id for p in pupils]
    try:
        att = {p.pupil_id: s for p, s in AT.summaries(year_group=f.year_group, form=f.name)}
    except Exception:  # noqa: BLE001 - no registers yet
        att = {}
    try:
        from education_system.systems.secondary.modules.assessment.domain import interventions as IV
        ivs = Counter(i.pupil_id for i in IV.list_interventions(year_group=f.year_group,
                                                                open_only=True))
    except Exception:  # noqa: BLE001
        ivs = Counter()
    emailable = C.emailable_for_pupils(ids)
    last: dict[int, str] = {}
    with database.connect() as conn:
        for start in range(0, len(ids), 500):
            chunk = ids[start:start + 500]
            for r in conn.execute(
                    "SELECT mp.pupil_id, MAX(m.meeting_date) FROM form_tutor_meeting_pupils mp "
                    "JOIN form_tutor_meetings m USING (meeting_id) WHERE mp.pupil_id IN "
                    f"({', '.join('?' * len(chunk))}) GROUP BY mp.pupil_id", chunk):
                last[r[0]] = r[1]
    rows = []
    for p in pupils:
        s = att.get(p.pupil_id)
        rows.append({"pupil": p, "attendance_pct": s.attendance_pct if s else None,
                     "band": s.band if s else "", "late": s.late if s else 0,
                     "interventions": ivs.get(p.pupil_id, 0),
                     "last_contact": last.get(p.pupil_id),
                     "email_contact": bool(emailable.get(p.pupil_id))})
    tutors = [a for a in list_assignments(form_id=f.form_id, academic_year=current_year())
              if a.status == "Active"]
    activity_log.record("form_tutors.form.view", target=f"FG{f.form_id}", principal=actor)
    return {"form": f, "tutors": tutors, "pupils": rows,
            "no_contact_this_term": [r["pupil"] for r in rows
                                     if (r["last_contact"] or "") < _term_start()]}


def _term_start() -> str:
    t = _today()
    if t.month >= 9:
        return f"{t.year}-09-01"
    if t.month >= 4:
        return f"{t.year}-04-15"
    return f"{t.year}-01-01"


def for_pupil(pupil_id: int) -> dict[str, Any]:
    """For the pupil profile: their form's tutors this year and the tutor
    meetings they were part of."""
    p = P.get_pupil(int(pupil_id))
    if p is None:
        raise NotFound(f"No pupil with id {pupil_id}")
    f = FG.find(p.year_group, p.form_group) if p.form_group else None
    tutors = [a for a in list_assignments(form_id=f.form_id, academic_year=current_year())
              if a.status == "Active"] if f else []
    return {"tutors": tutors, "meetings": list_meetings(pupil_id=p.pupil_id)}


# ── Export ───────────────────────────────────────────────────────────

def export_csv(path: str | Path, *, actor: Principal, **filters: Any) -> int:
    if actor.role not in STAFF_ROLES:
        _deny(actor, "export", None, "Only staff can export the tutor roster.")
    rows = list_assignments(**filters)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "academic_year", "year", "form", "tutor", "username", "role",
                    "email", "status", "start", "end", "meetings"])
        for a in rows:
            w.writerow([a.assignment_id, a.academic_year, a.year_group, _safe(a.form_group),
                        _safe(a.tutor_name), _safe(a.tutor_username), a.role,
                        _safe(a.contact_email), a.status, a.start_date, a.end_date or "",
                        meeting_count(a.assignment_id)])
    activity_log.record("form_tutors.export", principal=actor, rows=len(rows))
    return len(rows)
