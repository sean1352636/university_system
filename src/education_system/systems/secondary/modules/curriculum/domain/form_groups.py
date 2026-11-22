"""Form groups (tutor groups) for Years 7-11.

A pupil's form is the ``form_group`` name on their pupil record; this module
keeps the record *of* each form - its year, form tutor, co-tutor, room,
capacity and notes - and the rules for putting pupils in and out of forms.

Rules:

* A form name is 1-10 characters (letters, digits, spaces, hyphens), stored in
  capitals like the pupil record, and unique within its year among open forms.
* Renaming a form renames it on every pupil in it (through the normal pupil
  update, so each pupil's history shows it). A form with pupils can't change
  year - move the pupils with Year Groups instead.
* A form with pupils can't be archived or deleted.
* Pupils are put in a form only if they're on roll and in the form's year.
  Going over the form's capacity needs ``allow_over_capacity``.
* Forms named on pupil records with no form record are "not set up";
  :func:`set_up_missing` creates them.
* At the year-end rollover (:mod:`modules.pupils.domain.year_rollover`) forms move up with
  their pupils - a form named after its year is renamed the same way
  (``7K`` → ``8K``) and Year 11 forms are archived.

Every change goes in ``form_group_audit`` and the activity log (ids, field
names and counts only).
"""

from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any

from education_system.systems.secondary.modules.pupils.domain import contacts as C
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import FORM_GROUP_EDITORS, Principal
from education_system.systems.secondary.core.utilities.exports import safe_cell as _safe
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

MAX_NAME = 10  # same limit as pupils.form_group
MAX_CAPACITY = 60
EDITABLE_FIELDS: tuple[str, ...] = (
    "name", "year_group", "tutor_name", "tutor_email", "co_tutor_name", "room", "capacity",
    "notes",
)
FIELD_LABELS = {
    "name": "Form name", "year_group": "Year group", "tutor_name": "Form tutor",
    "tutor_email": "Tutor e-mail", "co_tutor_name": "Co-tutor", "room": "Room",
    "capacity": "Capacity", "notes": "Notes",
}
_NAME_RE = re.compile(r"^[A-Z0-9][A-Z0-9 \-]*$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS form_groups (
    form_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,
    year_group    INTEGER NOT NULL CHECK (year_group BETWEEN 7 AND 11),
    tutor_name    TEXT,
    tutor_email   TEXT,
    co_tutor_name TEXT,
    room          TEXT,
    capacity      INTEGER CHECK (capacity IS NULL OR capacity > 0),
    notes         TEXT,
    status        TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'archived')),
    archived_at   TEXT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    created_by    TEXT,
    updated_at    TEXT NOT NULL DEFAULT (datetime('now')),
    updated_by    TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_form_groups_open
    ON form_groups (year_group, name) WHERE status = 'active';
CREATE TABLE IF NOT EXISTS form_group_audit (
    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
    form_id  INTEGER NOT NULL,
    action   TEXT NOT NULL CHECK (action IN ('create', 'update', 'archive', 'restore',
                                             'delete', 'assign', 'remove', 'rollover')),
    actor    TEXT NOT NULL,
    detail   TEXT,
    at       TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_form_group_audit ON form_group_audit (form_id, audit_id);
"""

database.register_schema("form_groups", _SCHEMA)

ValidationError = P.ValidationError
PermissionDenied = P.PermissionDenied
NotFound = P.NotFound


@dataclass(frozen=True)
class FormGroup:
    form_id: int
    name: str
    year_group: int
    tutor_name: str | None = None
    tutor_email: str | None = None
    co_tutor_name: str | None = None
    room: str | None = None
    capacity: int | None = None
    notes: str | None = None
    status: str = "active"
    archived_at: str | None = None
    created_at: str | None = None
    created_by: str | None = None
    updated_at: str | None = None
    updated_by: str | None = None

    @property
    def label(self) -> str:
        return f"{self.name} (Year {self.year_group})"

    @property
    def is_active(self) -> bool:
        return self.status == "active"


@dataclass
class FormStats:
    on_roll: int = 0
    female: int = 0
    male: int = 0
    other: int = 0
    sen: int = 0
    fsm: int = 0
    eal: int = 0
    capacity: int | None = None

    @property
    def spaces(self) -> int | None:
        return None if self.capacity is None else self.capacity - self.on_roll

    @property
    def over_capacity(self) -> bool:
        return self.spaces is not None and self.spaces < 0


# ── Helpers ──────────────────────────────────────────────────────────

def _row(r) -> FormGroup:
    return FormGroup(**{f.name: r[f.name] for f in fields(FormGroup)})


def _require(actor: Principal, action: str, target: Any = None) -> None:
    if actor.role not in FORM_GROUP_EDITORS:
        activity_log.record(action, target=target, outcome="denied", principal=actor)
        raise PermissionDenied("Your account can view form groups but not change them.")


def _audit(conn, form_id: int, action: str, actor: str, detail: dict) -> None:
    conn.execute("INSERT INTO form_group_audit (form_id, action, actor, detail) "
                 "VALUES (?, ?, ?, ?)",
                 (form_id, action, actor or "unknown",
                  json.dumps(detail, default=str, sort_keys=True)))


def clean_name(value: Any) -> str | None:
    text = P._clean_text(value, 50)
    return text.upper() if text else None


def _validate(data: dict[str, Any]) -> dict[str, Any]:
    problems: list[str] = []
    unknown = set(data) - set(EDITABLE_FIELDS)
    if unknown:
        problems.append(f"Unknown field(s): {', '.join(sorted(unknown))}")
    out: dict[str, Any] = {}
    if "name" in data:
        name = clean_name(data.get("name"))
        if not name:
            problems.append("Form name is required")
        elif len(name) > MAX_NAME:
            problems.append(f"Form name must be {MAX_NAME} characters or fewer")
        elif not _NAME_RE.match(name):
            problems.append("Form name can only use letters, digits, spaces and hyphens")
        out["name"] = name
    if "year_group" in data:
        try:
            y = int(str(data.get("year_group")).strip())
        except (TypeError, ValueError):
            y = 0
        if y not in P.YEAR_GROUPS:
            problems.append("Year group must be 7, 8, 9, 10 or 11")
        out["year_group"] = y
    for key in ("tutor_name", "co_tutor_name"):
        if key in data:
            out[key] = P._clean_text(data.get(key), 100)
    if "room" in data:
        out["room"] = P._clean_text(data.get("room"), 30)
    if "tutor_email" in data:
        email = P._clean_text(data.get("tutor_email"), 254)
        email = email.lower() if email else None
        if email and not C.valid_email(email):
            problems.append("The tutor's e-mail address doesn't look right")
        out["tutor_email"] = email
    if "capacity" in data:
        raw = data.get("capacity")
        if raw in (None, ""):
            out["capacity"] = None
        else:
            try:
                cap = int(str(raw).strip())
            except ValueError:
                cap = 0
            if not 1 <= cap <= MAX_CAPACITY:
                problems.append(f"Capacity must be a whole number from 1 to {MAX_CAPACITY}")
            out["capacity"] = cap
    if "notes" in data:
        out["notes"] = P._clean_text(data.get("notes"), 2000)
    if problems:
        raise ValidationError(problems)
    return out


def _clash(conn, year: int, name: str, not_id: int | None = None) -> bool:
    return conn.execute(
        "SELECT 1 FROM form_groups WHERE status = 'active' AND year_group = ? AND name = ? "
        "AND form_id IS NOT ?", (year, name, not_id)).fetchone() is not None


# ── Reading ──────────────────────────────────────────────────────────

def get(form_id: int) -> FormGroup:
    with database.connect() as conn:
        r = conn.execute("SELECT * FROM form_groups WHERE form_id = ?", (int(form_id),)
                         ).fetchone()
    if r is None:
        raise NotFound(f"No form group #{form_id}")
    return _row(r)


def find(year_group: int, name: str) -> FormGroup | None:
    """The open form *name* in *year_group*, if it's set up."""
    with database.connect() as conn:
        r = conn.execute("SELECT * FROM form_groups WHERE status = 'active' AND year_group = ? "
                         "AND name = ?", (int(year_group), clean_name(name))).fetchone()
    return _row(r) if r else None


def list_forms(year_group: int | None = None, *, include_archived: bool = False
               ) -> list[FormGroup]:
    sql, params = "SELECT * FROM form_groups WHERE 1=1", []
    if year_group is not None:
        sql += " AND year_group = ?"
        params.append(int(year_group))
    if not include_archived:
        sql += " AND status = 'active'"
    sql += " ORDER BY status, year_group, name"
    with database.connect() as conn:
        return [_row(r) for r in conn.execute(sql, params)]


def names_for_year(year_group: int) -> list[str]:
    """Open form names in a year - for pupil form dropdowns."""
    return [f.name for f in list_forms(year_group)]


def choices_for(year_group: Any, current: str | None = None) -> list[str]:
    """Form names a pupil in *year_group* can be given: the open forms of that year,
    plus *current* if it isn't set up (so editing a record never drops it silently)."""
    try:
        year = int(year_group)
    except (TypeError, ValueError):
        return []
    names = names_for_year(year) if year in P.YEAR_GROUPS else []
    cur = clean_name(current)
    if cur and cur not in names:
        names.append(cur)
    return names


def check_choice(year_group: Any, form: str | None, current: str | None = None) -> None:
    """Raise ValidationError unless *form* is blank, an open form of *year_group*, or
    the pupil's *current* form left unchanged."""
    name = clean_name(form)
    if not name or name == clean_name(current):
        return
    if name not in choices_for(year_group):
        raise ValidationError([f"Form {name} isn't set up for Year {year_group} - choose one "
                               "from the list, or set it up in Form Groups first"])


def details_for(pupil: P.Pupil) -> dict[str, str]:
    """The pupil's form for e-mails: name, tutor, tutor e-mail, room, and a ready-made
    block of lines (``form_details``)."""
    f = find(pupil.year_group, pupil.form_group) if pupil.form_group else None
    out = {"form_group": pupil.form_group or "", "form_tutor": (f.tutor_name if f else "") or "",
           "form_tutor_email": (f.tutor_email if f else "") or "",
           "form_room": (f.room if f else "") or ""}
    if not pupil.form_group:
        lines = [f"    Form:        not set yet (Year {pupil.year_group}) - the school office "
                 "will let you know"]
    else:
        lines = [f"    Form:        {pupil.form_group} (Year {pupil.year_group})"]
        if out["form_tutor"]:
            lines.append(f"    Form tutor:  {out['form_tutor']}"
                         + (f" ({out['form_tutor_email']})" if out["form_tutor_email"] else ""))
        if out["form_room"]:
            lines.append(f"    Form room:   {out['form_room']}")
    out["form_details"] = "\n".join(lines)
    return out


def members(form: FormGroup | int) -> list[P.Pupil]:
    """Pupils on roll in the form, by surname."""
    f = get(form) if isinstance(form, int) else form
    return [p for p in P.list_pupils(year_group=f.year_group, form_group=f.name)
            if (p.form_group or "").upper() == f.name]


def stats(year_group: int | None = None) -> dict[int, FormStats]:
    """{form_id: FormStats} for open forms, counted live from pupil records."""
    forms = list_forms(year_group)
    out = {f.form_id: FormStats(capacity=f.capacity) for f in forms}
    key = {(f.year_group, f.name): f.form_id for f in forms}
    for p in P.list_pupils(year_group=year_group):
        fid = key.get((p.year_group, (p.form_group or "").upper()))
        if fid is None:
            continue
        s = out[fid]
        s.on_roll += 1
        if p.gender == "Female":
            s.female += 1
        elif p.gender == "Male":
            s.male += 1
        else:
            s.other += 1
        s.sen += p.sen_status in {"K", "E"}
        s.fsm += bool(p.fsm_eligible)
        s.eal += bool(p.eal)
    return out


def not_set_up() -> list[tuple[int, str, int]]:
    """(year, form name, pupils) for forms on pupil records with no open form record."""
    with database.connect() as conn:
        rows = conn.execute(
            "SELECT p.year_group AS y, upper(p.form_group) AS f, COUNT(*) AS n FROM pupils p "
            "WHERE p.roll_status = 'on_roll' AND coalesce(p.form_group, '') <> '' "
            "AND NOT EXISTS (SELECT 1 FROM form_groups g WHERE g.status = 'active' "
            "AND g.year_group = p.year_group AND g.name = upper(p.form_group)) "
            "GROUP BY p.year_group, upper(p.form_group) ORDER BY 1, 2").fetchall()
    return [(r["y"], r["f"], r["n"]) for r in rows]


def without_form(year_group: int | None = None) -> list[P.Pupil]:
    return [p for p in P.list_pupils(year_group=year_group) if not p.form_group]


def history(form_id: int) -> list[dict[str, Any]]:
    with database.connect() as conn:
        rows = conn.execute("SELECT * FROM form_group_audit WHERE form_id = ? "
                            "ORDER BY audit_id DESC", (int(form_id),)).fetchall()
    return [{"at": r["at"], "actor": r["actor"], "action": r["action"],
             "detail": json.loads(r["detail"]) if r["detail"] else {}} for r in rows]


# ── Changing forms ───────────────────────────────────────────────────

def create(data: dict[str, Any], *, actor: Principal) -> FormGroup:
    _require(actor, "form_group.create")
    clean = _validate({"name": data.get("name"), "year_group": data.get("year_group"),
                       **{k: v for k, v in data.items() if k not in {"name", "year_group"}}})
    with database.connect() as conn:
        if _clash(conn, clean["year_group"], clean["name"]):
            raise ValidationError([f"Year {clean['year_group']} already has a form "
                                   f"{clean['name']}"])
        cols = list(clean)
        cur = conn.execute(
            f"INSERT INTO form_groups ({', '.join(cols)}, created_by, updated_by) "  # nosec B608 - cols from EDITABLE_FIELDS
            f"VALUES ({', '.join('?' * len(cols))}, ?, ?)",
            (*clean.values(), actor.username, actor.username))
        fid = cur.lastrowid
        _audit(conn, fid, "create", actor.username, {"fields": sorted(clean)})
    activity_log.record("form_group.create", target=f"FG{fid}", principal=actor)
    return get(fid)


def update(form_id: int, changes: dict[str, Any], *, actor: Principal
           ) -> tuple[FormGroup, list[str], int]:
    """Change a form. Returns (form, changed field names, pupils renamed)."""
    _require(actor, "form_group.update", f"FG{form_id}")
    current = get(form_id)
    if not current.is_active:
        raise ValidationError(["Archived forms can't be changed - restore it first"])
    try:
        clean = _validate(changes)
    except ValidationError as e:
        activity_log.record("form_group.update", target=f"FG{form_id}", outcome="invalid",
                            principal=actor, problems=len(e.problems))
        raise
    diff = {k: {"from": getattr(current, k), "to": v} for k, v in clean.items()
            if getattr(current, k) != v}
    if not diff:
        return current, [], 0
    pupils = members(current) if {"name", "year_group"} & set(diff) else []
    if "year_group" in diff and pupils:
        raise ValidationError([f"{current.name} has {len(pupils)} pupil(s) - a form with "
                               "pupils can't change year. Move them with Year Groups, or "
                               "make a new form."])
    new_year = clean.get("year_group", current.year_group)
    new_name = clean.get("name", current.name)
    with database.connect() as conn:
        if _clash(conn, new_year, new_name, form_id):
            raise ValidationError([f"Year {new_year} already has a form {new_name}"])
        sets = ", ".join(f"{k} = ?" for k in diff)
        conn.execute(f"UPDATE form_groups SET {sets}, updated_at = datetime('now'), "  # nosec B608 - keys from EDITABLE_FIELDS
                     "updated_by = ? WHERE form_id = ?",
                     (*(d["to"] for d in diff.values()), actor.username, form_id))
        _audit(conn, form_id, "update", actor.username,
               {k: d for k, d in diff.items() if k not in {"tutor_email", "notes"}}
               | {k: "changed" for k in diff if k in {"tutor_email", "notes"}})
    renamed = 0
    if "name" in diff:
        for p in pupils:
            P.update_pupil(p.pupil_id, {"form_group": new_name}, actor=actor)
            renamed += 1
    activity_log.record("form_group.update", target=f"FG{form_id}", principal=actor,
                        fields=sorted(diff), pupils_renamed=renamed or None)
    return get(form_id), sorted(diff), renamed


def _empty_or_refuse(f: FormGroup, what: str) -> None:
    n = len(members(f))
    if n:
        raise ValidationError([f"{f.name} still has {n} pupil(s) - move them to another form "
                               f"before you {what} it"])


def archive(form_id: int, *, actor: Principal) -> FormGroup:
    _require(actor, "form_group.archive", f"FG{form_id}")
    f = get(form_id)
    if not f.is_active:
        return f
    _empty_or_refuse(f, "archive")
    with database.connect() as conn:
        conn.execute("UPDATE form_groups SET status = 'archived', archived_at = datetime('now'), "
                     "updated_at = datetime('now'), updated_by = ? WHERE form_id = ?",
                     (actor.username, form_id))
        _audit(conn, form_id, "archive", actor.username, {})
    activity_log.record("form_group.archive", target=f"FG{form_id}", principal=actor)
    return get(form_id)


def restore(form_id: int, *, actor: Principal) -> FormGroup:
    _require(actor, "form_group.restore", f"FG{form_id}")
    f = get(form_id)
    if f.is_active:
        return f
    with database.connect() as conn:
        if _clash(conn, f.year_group, f.name, form_id):
            raise ValidationError([f"Year {f.year_group} already has an open form {f.name} - "
                                   "rename that one first"])
        conn.execute("UPDATE form_groups SET status = 'active', archived_at = NULL, "
                     "updated_at = datetime('now'), updated_by = ? WHERE form_id = ?",
                     (actor.username, form_id))
        _audit(conn, form_id, "restore", actor.username, {})
    activity_log.record("form_group.restore", target=f"FG{form_id}", principal=actor)
    return get(form_id)


def delete(form_id: int, *, actor: Principal) -> None:
    """Remove a form record set up by mistake. Its history is kept."""
    _require(actor, "form_group.delete", f"FG{form_id}")
    f = get(form_id)
    if f.is_active:
        _empty_or_refuse(f, "delete")
    with database.connect() as conn:
        # Form Tutors keeps assignments and meeting records against the form.
        if conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = "
                        "'form_tutor_assignments'").fetchone() and conn.execute(
                "SELECT 1 FROM form_tutor_assignments WHERE form_id = ?",
                (form_id,)).fetchone():
            raise ValidationError([f"{f.name} has form tutor records - archive it instead "
                                   "so they're kept"])
        conn.execute("DELETE FROM form_groups WHERE form_id = ?", (form_id,))
        _audit(conn, form_id, "delete", actor.username,
               {"name": f.name, "year_group": f.year_group})
    activity_log.record("form_group.delete", target=f"FG{form_id}", principal=actor)


def set_up_missing(*, actor: Principal) -> list[FormGroup]:
    """Create a form record for every form named on pupil records but not set up."""
    _require(actor, "form_group.create")
    made = []
    for year, name, _n in not_set_up():
        try:
            made.append(create({"name": name, "year_group": year}, actor=actor))
        except ValidationError:
            continue  # a name that breaks the rules: fix it on the pupils first
    return made


# ── Pupils in and out ────────────────────────────────────────────────

def assign(pupil_ids: list[int], form_id: int, *, actor: Principal,
           allow_over_capacity: bool = False) -> tuple[list[P.Pupil], list[tuple[str, str]]]:
    """Put pupils in a form. Returns (assigned, [(admission no., why not)])."""
    _require(actor, "form_group.assign", f"FG{form_id}")
    f = get(form_id)
    if not f.is_active:
        raise ValidationError(["That form is archived"])
    want, refused = [], []
    for pid in dict.fromkeys(pupil_ids):
        p = P.get_pupil(pid)
        if p is None:
            refused.append((str(pid), "no such pupil"))
        elif p.roll_status != "on_roll":
            refused.append((p.admission_no, "not on roll"))
        elif p.year_group != f.year_group:
            refused.append((p.admission_no, f"in Year {p.year_group}, not Year {f.year_group}"))
        elif (p.form_group or "").upper() == f.name:
            refused.append((p.admission_no, f"already in {f.name}"))
        else:
            want.append(p)
    if f.capacity is not None and not allow_over_capacity:
        room = f.capacity - len(members(f))
        if len(want) > room:
            raise ValidationError([f"{f.name} has room for {max(room, 0)} more (capacity "
                                   f"{f.capacity}); {len(want)} chosen"])
    done = []
    for p in want:
        try:
            done.append(P.update_pupil(p.pupil_id, {"form_group": f.name}, actor=actor))
        except (P.ValidationError, P.PermissionDenied) as e:
            refused.append((p.admission_no, str(e)))
    if done:
        with database.connect() as conn:
            _audit(conn, form_id, "assign", actor.username, {"pupils": len(done)})
    activity_log.record("form_group.assign", target=f"FG{form_id}", principal=actor,
                        assigned=len(done), refused=len(refused) or None)
    return done, refused


def remove(pupil_ids: list[int], form_id: int, *, actor: Principal) -> int:
    """Take pupils out of a form (they're left with no form). Returns how many."""
    _require(actor, "form_group.remove", f"FG{form_id}")
    f = get(form_id)
    inside = {p.pupil_id for p in members(f)}
    n = 0
    for pid in dict.fromkeys(pupil_ids):
        if pid in inside:
            P.update_pupil(pid, {"form_group": ""}, actor=actor)
            n += 1
    if n:
        with database.connect() as conn:
            _audit(conn, form_id, "remove", actor.username, {"pupils": n})
    activity_log.record("form_group.remove", target=f"FG{form_id}", principal=actor, removed=n)
    return n


def plan_distribution(year_group: int) -> tuple[list[tuple[P.Pupil, FormGroup]], list[P.Pupil]]:
    """Suggest a form for each pupil in the year with none: keeps forms even in size and
    in girls/boys, within capacity. Returns (plan, pupils with no room). Writes nothing."""
    forms = list_forms(year_group)
    if not forms:
        return [], without_form(year_group)
    st = stats(year_group)
    size = {f.form_id: st[f.form_id].on_roll for f in forms}
    by_gender = {f.form_id: {"Female": st[f.form_id].female, "Male": st[f.form_id].male}
                 for f in forms}
    plan, unplaced = [], []
    for p in sorted(without_form(year_group), key=lambda p: (p.gender, p.legal_last_name,
                                                             p.legal_first_name)):
        open_forms = [f for f in forms if f.capacity is None or size[f.form_id] < f.capacity]
        if not open_forms:
            unplaced.append(p)
            continue
        best = min(open_forms, key=lambda f: (by_gender[f.form_id].get(p.gender, 0),
                                              size[f.form_id], f.name))
        plan.append((p, best))
        size[best.form_id] += 1
        by_gender[best.form_id][p.gender] = by_gender[best.form_id].get(p.gender, 0) + 1
    return plan, unplaced


def apply_distribution(plan: list[tuple[P.Pupil, FormGroup]], *, actor: Principal
                       ) -> tuple[int, list[tuple[str, str]]]:
    _require(actor, "form_group.assign")
    by_form: dict[int, list[int]] = {}
    for p, f in plan:
        by_form.setdefault(f.form_id, []).append(p.pupil_id)
    total, refused = 0, []
    for fid, ids in by_form.items():
        done, bad = assign(ids, fid, actor=actor)
        total += len(done)
        refused += bad
    return total, refused


# ── Class list ───────────────────────────────────────────────────────

def export_class_list(form_id: int, path: str | Path, *, actor: Principal,
                      include_needs: bool = False) -> int:
    """Write the form's pupils to a CSV; returns how many. Needs columns (SEN, FSM,
    EAL) only for pupil editors."""
    if not actor.is_staff:
        raise PermissionDenied("Only staff can export class lists.")
    if include_needs and not actor.can_edit_pupils:
        activity_log.record("form_group.export", target=f"FG{form_id}", outcome="denied",
                            principal=actor)
        raise PermissionDenied("Your account can't export SEN, FSM or EAL details.")
    f = get(form_id)
    rows = members(f)
    cols = ["Admission no", "Surname", "First name", "Preferred name", "Gender",
            "Date of birth"] + (["SEN", "FSM", "EAL"] if include_needs else [])
    with Path(path).open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow([f"Form {f.name}", f"Year {f.year_group}", f"Tutor: {f.tutor_name or ''}"])
        w.writerow(cols)
        for p in rows:
            vals = [p.admission_no, p.legal_last_name, p.legal_first_name, p.preferred_name,
                    p.gender, p.date_of_birth]
            if include_needs:
                vals += [p.sen_status, "Y" if p.fsm_eligible else "", "Y" if p.eal else ""]
            w.writerow([_safe(v) for v in vals])
    activity_log.record("form_group.export", target=f"FG{form_id}", principal=actor,
                        rows=len(rows), needs=include_needs)
    return len(rows)


# ── Year-end rollover ────────────────────────────────────────────────

def roll_forward(conn, label: str, actor: str) -> dict[str, int]:
    """Inside the rollover's transaction: archive Year 11 forms and move every other
    open form up a year, renamed as its pupils' forms are (``7K`` → ``8K``)."""
    from education_system.systems.secondary.modules.pupils.domain.year_rollover import _next_form
    rows = conn.execute("SELECT form_id, name, year_group FROM form_groups "
                        "WHERE status = 'active' ORDER BY year_group DESC").fetchall()
    moved = archived = 0
    for r in rows:
        if r["year_group"] >= max(P.YEAR_GROUPS):
            conn.execute("UPDATE form_groups SET status = 'archived', archived_at = "
                         "datetime('now'), updated_at = datetime('now'), updated_by = ? "
                         "WHERE form_id = ?", (actor, r["form_id"]))
            _audit(conn, r["form_id"], "rollover", actor, {"year": label, "archived": True})
            archived += 1
            continue
        new_year, new_name = r["year_group"] + 1, _next_form(r["name"], r["year_group"])
        if conn.execute("SELECT 1 FROM form_groups WHERE status = 'active' AND year_group = ? "
                        "AND name = ? AND form_id <> ?",
                        (new_year, new_name, r["form_id"])).fetchone():
            # Can't happen when years move top-down; never break the rollover over it.
            conn.execute("UPDATE form_groups SET status = 'archived', archived_at = "
                         "datetime('now') WHERE form_id = ?", (r["form_id"],))
            _audit(conn, r["form_id"], "rollover", actor, {"year": label, "archived": True})
            archived += 1
            continue
        conn.execute("UPDATE form_groups SET year_group = ?, name = ?, updated_at = "
                     "datetime('now'), updated_by = ? WHERE form_id = ?",
                     (new_year, new_name, actor, r["form_id"]))
        _audit(conn, r["form_id"], "rollover", actor,
               {"year": label, "year_group": {"from": r["year_group"], "to": new_year},
                **({"name": {"from": r["name"], "to": new_name}}
                   if new_name != r["name"] else {})})
        moved += 1
    return {"moved": moved, "archived": archived}
