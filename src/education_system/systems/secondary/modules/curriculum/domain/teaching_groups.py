"""Teaching groups: the classes pupils are taught a subject in ("8x/Ma1",
"10B/Hi"), with their teacher, room and pupils.

A group belongs to one academic year ("2026/27"), one subject and one year
group. Groups are made fresh each year: after the year-end rollover last
year's groups are history (still readable, never changed) and the lists show
the current year.

Rules:

* Code: 1-20 characters (letters, digits, spaces, ``/ - .``), unique ignoring
  case within the academic year. Kind: Mixed, Set (with a set number) or
  Option (a KS4 option class).
* The subject must be active and taught in the group's year (its key stage).
* Teacher: a name, and optionally the teacher's secondary login (so "my
  groups" works); choosing a login fills in the name and e-mail.
* Pupils: on roll and in the group's year. A pupil is in at most one group
  for a subject in a year - adding them to another moves them only when asked
  (``move=True``). Capacity needs ``allow_over_capacity`` to go over.
* A group with pupils can't change subject or year, or be deleted; archive it.
* Past years' groups can't be changed.
* :func:`create_from_forms` makes one group per form (KS3 classes taught in
  forms); :func:`coverage` lists pupils with no group for a core subject.

Every change goes in ``teaching_group_audit`` and the activity log (ids,
codes, field names and counts only).
"""

from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any

from education_system.systems.secondary.modules.curriculum.domain import form_groups as FG
from education_system.systems.secondary.modules.curriculum.domain import subjects as S
from education_system.systems.secondary.modules.pupils.domain import contacts as C
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import TEACHING_GROUP_EDITORS, Principal
from education_system.systems.secondary.core.utilities.exports import safe_cell as _safe
from education_system.systems.secondary.core.academic_calendar.school_year import current_year
from education_system.systems.secondary.infrastructure.authentication import accounts
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

KINDS: tuple[str, ...] = ("Mixed", "Set", "Option")
MAX_CAPACITY = 40
EDITABLE_FIELDS: tuple[str, ...] = (
    "code", "subject_id", "year_group", "kind", "set_number", "teacher_name",
    "teacher_username", "teacher_email", "second_teacher", "room", "capacity",
    "lessons_per_week", "notes",
)
FIELD_LABELS = {
    "code": "Group code", "subject_id": "Subject", "year_group": "Year group", "kind": "Kind",
    "set_number": "Set", "teacher_name": "Teacher", "teacher_username": "Teacher's login",
    "teacher_email": "Teacher e-mail", "second_teacher": "Second teacher", "room": "Room",
    "capacity": "Capacity", "lessons_per_week": "Lessons per week", "notes": "Notes",
    "academic_year": "Academic year",
}
_CODE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 /.\-]*$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS teaching_groups (
    group_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    academic_year    TEXT NOT NULL,
    code             TEXT NOT NULL,
    subject_id       INTEGER NOT NULL REFERENCES subjects (subject_id),
    year_group       INTEGER NOT NULL CHECK (year_group BETWEEN 7 AND 11),
    kind             TEXT NOT NULL DEFAULT 'Mixed' CHECK (kind IN ('Mixed', 'Set', 'Option')),
    set_number       INTEGER CHECK (set_number IS NULL OR set_number BETWEEN 1 AND 20),
    teacher_name     TEXT,
    teacher_username TEXT,
    teacher_email    TEXT,
    second_teacher   TEXT,
    room             TEXT,
    capacity         INTEGER CHECK (capacity IS NULL OR capacity BETWEEN 1 AND 40),
    lessons_per_week INTEGER CHECK (lessons_per_week IS NULL OR lessons_per_week BETWEEN 1 AND 20),
    notes            TEXT,
    status           TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'archived')),
    created_at       TEXT NOT NULL DEFAULT (datetime('now')),
    created_by       TEXT,
    updated_at       TEXT NOT NULL DEFAULT (datetime('now')),
    updated_by       TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_teaching_groups_code
    ON teaching_groups (academic_year, code COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS ix_teaching_groups_subject
    ON teaching_groups (academic_year, subject_id, year_group);
CREATE TABLE IF NOT EXISTS teaching_group_members (
    group_id  INTEGER NOT NULL REFERENCES teaching_groups (group_id) ON DELETE CASCADE,
    pupil_id  INTEGER NOT NULL REFERENCES pupils (pupil_id) ON DELETE CASCADE,
    added_at  TEXT NOT NULL DEFAULT (datetime('now')),
    added_by  TEXT,
    PRIMARY KEY (group_id, pupil_id)
);
CREATE INDEX IF NOT EXISTS ix_teaching_group_members_pupil ON teaching_group_members (pupil_id);
CREATE TABLE IF NOT EXISTS teaching_group_audit (
    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id INTEGER NOT NULL,
    action   TEXT NOT NULL CHECK (action IN ('create', 'update', 'archive', 'restore', 'delete',
                                             'add', 'remove', 'move_in', 'move_out')),
    actor    TEXT NOT NULL,
    detail   TEXT,
    at       TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_teaching_group_audit ON teaching_group_audit (group_id, audit_id);
"""

database.register_schema("teaching_groups", _SCHEMA)
S.register_usage("teaching_groups", "subject_id", "teaching group(s)")

ValidationError = P.ValidationError
PermissionDenied = P.PermissionDenied
NotFound = P.NotFound


@dataclass(frozen=True)
class TeachingGroup:
    group_id: int
    academic_year: str
    code: str
    subject_id: int
    year_group: int
    kind: str = "Mixed"
    set_number: int | None = None
    teacher_name: str | None = None
    teacher_username: str | None = None
    teacher_email: str | None = None
    second_teacher: str | None = None
    room: str | None = None
    capacity: int | None = None
    lessons_per_week: int | None = None
    notes: str | None = None
    status: str = "active"
    created_at: str | None = None
    created_by: str | None = None
    updated_at: str | None = None
    updated_by: str | None = None

    @property
    def is_active(self) -> bool:
        return self.status == "active"

    @property
    def is_current(self) -> bool:
        return self.academic_year == current_year()

    @property
    def kind_label(self) -> str:
        return f"Set {self.set_number}" if self.kind == "Set" and self.set_number else self.kind


@dataclass
class GroupInfo:
    """A group with the figures a list needs."""
    group: TeachingGroup
    subject: S.Subject
    pupils: int
    lessons: int | None  # the group's own, else the curriculum plan's

    @property
    def spaces(self) -> int | None:
        return None if self.group.capacity is None else self.group.capacity - self.pupils


# ── Helpers ──────────────────────────────────────────────────────────

def _row(r) -> TeachingGroup:
    return TeachingGroup(**{f.name: r[f.name] for f in fields(TeachingGroup)})


def _require(actor: Principal, action: str, target: Any = None) -> None:
    if actor.role not in TEACHING_GROUP_EDITORS:
        activity_log.record(action, target=target, outcome="denied", principal=actor)
        raise PermissionDenied("Your account can view teaching groups but not change them.")


def _audit(conn, group_id: int, action: str, actor: Principal, detail: dict) -> None:
    conn.execute("INSERT INTO teaching_group_audit (group_id, action, actor, detail) "
                 "VALUES (?, ?, ?, ?)",
                 (group_id, action, actor.username or "unknown",
                  json.dumps(detail, default=str, sort_keys=True)))


def _int(value: Any, label: str, lo: int, hi: int, problems: list[str]) -> int | None:
    if value in (None, ""):
        return None
    try:
        n = int(str(value).strip())
    except ValueError:
        n = lo - 1
    if not lo <= n <= hi:
        problems.append(f"{label} must be a whole number from {lo} to {hi}")
    return n


def teacher_choices() -> list[dict]:
    """Secondary staff logins to pick a teacher from (empty if auth.db can't be read)."""
    try:
        return accounts.staff_logins()
    except Exception:  # noqa: BLE001 - the name can still be typed
        return []


def _validate(data: dict[str, Any], current: TeachingGroup | None) -> dict[str, Any]:
    problems: list[str] = []
    unknown = set(data) - set(EDITABLE_FIELDS)
    if unknown:
        problems.append(f"Unknown field(s): {', '.join(sorted(unknown))}")
    out: dict[str, Any] = {}
    if "code" in data or current is None:
        code = P._clean_text(data.get("code"), 40)
        if not code:
            problems.append("Group code is required")
        elif len(code) > 20:
            problems.append("Group code must be 20 characters or fewer")
        elif not _CODE_RE.match(code):
            problems.append("Group code can use letters, digits, spaces and / - .")
        out["code"] = code
    if "subject_id" in data or current is None:
        sid = data.get("subject_id")
        try:
            subj = S.get(int(sid))  # type: ignore[arg-type]
        except (TypeError, ValueError, S.NotFound):
            subj = None
            problems.append("Choose a subject")
        out["subject_id"] = subj.subject_id if subj else sid
        if subj and not subj.is_active and (current is None
                                            or current.subject_id != subj.subject_id):
            problems.append(f"{subj.code} is inactive - choose an active subject")
    if "year_group" in data or current is None:
        out["year_group"] = _int(data.get("year_group"), "Year group", 7, 11, problems)
        if out["year_group"] is None:
            problems.append("Choose a year group")
    if "kind" in data or current is None:
        kind = P._clean_text(data.get("kind") or "Mixed", 20)
        match = next((k for k in KINDS if k.lower() == (kind or "").lower()), None)
        if match is None:
            problems.append(f"Kind must be one of: {', '.join(KINDS)}")
        out["kind"] = match or kind
    if "set_number" in data:
        out["set_number"] = _int(data.get("set_number"), "Set", 1, 20, problems)
    for key, limit in (("teacher_name", 100), ("second_teacher", 100), ("room", 30),
                       ("notes", 2000)):
        if key in data:
            out[key] = P._clean_text(data.get(key), limit)
    if "teacher_email" in data:
        email = P._clean_text(data.get("teacher_email"), 254)
        email = email.lower() if email else None
        if email and not C.valid_email(email):
            problems.append("The teacher's e-mail address doesn't look right")
        out["teacher_email"] = email
    if "teacher_username" in data:
        username = P._clean_text(data.get("teacher_username"), 100)
        out["teacher_username"] = username
        if username:
            login = next((t for t in teacher_choices()
                          if t["username"].lower() == username.lower()), None)
            if login is None:
                problems.append(f"'{username}' isn't a secondary staff login")
            else:
                out["teacher_username"] = login["username"]
                if not (data.get("teacher_name") or (current and current.teacher_name)):
                    out["teacher_name"] = login["display_name"]
                if not (data.get("teacher_email") or (current and current.teacher_email)):
                    out["teacher_email"] = (login["email"] or "").lower() or None
    if "capacity" in data:
        out["capacity"] = _int(data.get("capacity"), "Capacity", 1, MAX_CAPACITY, problems)
    if "lessons_per_week" in data:
        out["lessons_per_week"] = _int(data.get("lessons_per_week"), "Lessons per week", 1,
                                       S.MAX_LESSONS, problems)

    # Rules on the record as it would be.
    merged = {f: getattr(current, f) if current else None for f in EDITABLE_FIELDS}
    merged.update(out)
    if merged["kind"] == "Set" and not merged["set_number"]:
        problems.append("A set needs a set number")
    if merged["kind"] != "Set" and merged["set_number"]:
        out["set_number"] = None
    if not problems and merged["subject_id"] and merged["year_group"]:
        subj = S.get(int(merged["subject_id"]))
        if merged["year_group"] not in subj.years:
            problems.append(f"{subj.code} isn't taught in Year {merged['year_group']} "
                            f"(key stage {subj.key_stage})")
        if merged["kind"] == "Option" and merged["year_group"] < 10:
            problems.append("Option groups are for Years 10 and 11")
    if problems:
        raise ValidationError(problems)
    return out


def _editable(g: TeachingGroup) -> None:
    if not g.is_current:
        raise ValidationError([f"{g.code} belongs to {g.academic_year} - past years' groups "
                               "can't be changed"])


# ── Reading ──────────────────────────────────────────────────────────

def get(group_id: int) -> TeachingGroup:
    with database.connect() as conn:
        r = conn.execute("SELECT * FROM teaching_groups WHERE group_id = ?", (int(group_id),)
                         ).fetchone()
    if r is None:
        raise NotFound(f"No teaching group #{group_id}")
    return _row(r)


def find(code: str, academic_year: str | None = None) -> TeachingGroup | None:
    with database.connect() as conn:
        r = conn.execute("SELECT * FROM teaching_groups WHERE academic_year = ? AND "
                         "code = ? COLLATE NOCASE",
                         (academic_year or current_year(), (code or "").strip())).fetchone()
    return _row(r) if r else None


def academic_years() -> list[str]:
    with database.connect() as conn:
        years = {r[0] for r in conn.execute("SELECT DISTINCT academic_year FROM teaching_groups")}
    return sorted(years | {current_year()}, reverse=True)


def list_groups(*, academic_year: str | None = None, year_group: int | None = None,
                subject_id: int | None = None, teacher: str | None = None,
                include_archived: bool = False) -> list[TeachingGroup]:
    """Groups in *academic_year* (default: this year), by year, subject, set, code.
    *teacher* keeps those a login teaches (main teacher)."""
    sql = "SELECT g.* FROM teaching_groups g JOIN subjects s USING (subject_id) WHERE " \
          "g.academic_year = ?"
    params: list[Any] = [academic_year or current_year()]
    if year_group is not None:
        sql += " AND g.year_group = ?"
        params.append(int(year_group))
    if subject_id is not None:
        sql += " AND g.subject_id = ?"
        params.append(int(subject_id))
    if teacher:
        sql += " AND lower(g.teacher_username) = lower(?)"
        params.append(teacher)
    if not include_archived:
        sql += " AND g.status = 'active'"
    sql += (" ORDER BY g.status, g.year_group, s.name COLLATE NOCASE, "
            "coalesce(g.set_number, 99), g.code COLLATE NOCASE")
    with database.connect() as conn:
        return [_row(r) for r in conn.execute(sql, params)]


def info(groups: list[TeachingGroup]) -> list[GroupInfo]:
    """Pupil counts (on roll) and lessons for *groups*."""
    if not groups:
        return []
    ids = [g.group_id for g in groups]
    with database.connect() as conn:
        counts = {r[0]: r[1] for r in conn.execute(
            f"SELECT m.group_id, COUNT(*) FROM teaching_group_members m JOIN pupils p "  # nosec B608 - placeholders
            f"USING (pupil_id) WHERE p.roll_status = 'on_roll' AND m.group_id IN "
            f"({', '.join('?' * len(ids))}) GROUP BY m.group_id", ids)}
    plan = S.plan(active_only=False)
    subjects: dict[int, S.Subject] = {}
    out = []
    for g in groups:
        subj = subjects.get(g.subject_id) or subjects.setdefault(g.subject_id, S.get(g.subject_id))
        out.append(GroupInfo(g, subj, counts.get(g.group_id, 0),
                             g.lessons_per_week or plan.get(g.subject_id, {}).get(g.year_group)))
    return out


def members(group_id: int, *, include_left: bool = False) -> list[P.Pupil]:
    """Pupils in the group, by surname (on roll unless *include_left*)."""
    with database.connect() as conn:
        ids = [r[0] for r in conn.execute(
            "SELECT m.pupil_id FROM teaching_group_members m JOIN pupils p USING (pupil_id) "
            "WHERE m.group_id = ?" + ("" if include_left else " AND p.roll_status = 'on_roll'")
            + " ORDER BY p.legal_last_name COLLATE NOCASE, p.legal_first_name COLLATE NOCASE",
            (int(group_id),))]
    return [p for p in (P.get_pupil(i) for i in ids) if p]


def groups_for_pupil(pupil_id: int, academic_year: str | None = None) -> list[GroupInfo]:
    """The pupil's groups this year (or *academic_year*), by subject."""
    with database.connect() as conn:
        rows = conn.execute(
            "SELECT g.* FROM teaching_groups g JOIN teaching_group_members m USING (group_id) "
            "JOIN subjects s USING (subject_id) WHERE m.pupil_id = ? AND g.academic_year = ? "
            "AND g.status = 'active' ORDER BY s.name COLLATE NOCASE",
            (int(pupil_id), academic_year or current_year())).fetchall()
    return info([_row(r) for r in rows])


def _group_for_subject(conn, pupil_id: int, subject_id: int, academic_year: str,
                       not_group: int | None = None):
    return conn.execute(
        "SELECT g.group_id, g.code FROM teaching_groups g JOIN teaching_group_members m "
        "USING (group_id) WHERE m.pupil_id = ? AND g.subject_id = ? AND g.academic_year = ? "
        "AND g.status = 'active' AND g.group_id IS NOT ?",
        (pupil_id, subject_id, academic_year, not_group)).fetchone()


def wrong_year(group_id: int) -> list[P.Pupil]:
    """Members now in a different year from the group (moved year after joining)."""
    g = get(group_id)
    return [p for p in members(group_id) if p.year_group != g.year_group]


def candidates(group_id: int, *, include_grouped: bool = False) -> list[tuple[P.Pupil, str]]:
    """Pupils who could join: on roll, in the group's year, not in it. With the code of
    the group they're in for this subject ("" if none); those already grouped only
    when *include_grouped*."""
    g = get(group_id)
    inside = {p.pupil_id for p in members(group_id, include_left=True)}
    out = []
    with database.connect() as conn:
        for p in P.list_pupils(year_group=g.year_group):
            if p.pupil_id in inside:
                continue
            other = _group_for_subject(conn, p.pupil_id, g.subject_id, g.academic_year)
            if other and not include_grouped:
                continue
            out.append((p, other["code"] if other else ""))
    return out


def coverage(academic_year: str | None = None) -> list[tuple[S.Subject, int, list[P.Pupil]]]:
    """(core subject, year, pupils on roll with no group for it) - only for subject/years
    that have at least one group set up or lessons planned."""
    year = academic_year or current_year()
    plan = S.plan()
    out = []
    with database.connect() as conn:
        grouped = {(r[0], r[1]) for r in conn.execute(
            "SELECT g.subject_id, m.pupil_id FROM teaching_groups g JOIN teaching_group_members "
            "m USING (group_id) WHERE g.academic_year = ? AND g.status = 'active'", (year,))}
        has_groups = {(r[0], r[1]) for r in conn.execute(
            "SELECT DISTINCT subject_id, year_group FROM teaching_groups WHERE academic_year = ? "
            "AND status = 'active'", (year,))}
    pupils_by_year: dict[int, list[P.Pupil]] = {}
    for p in P.list_pupils():
        pupils_by_year.setdefault(p.year_group, []).append(p)
    for s in S.list_subjects():
        if not s.is_core:
            continue
        for y in s.years:
            if (s.subject_id, y) not in has_groups and not plan.get(s.subject_id, {}).get(y):
                continue
            missing = [p for p in pupils_by_year.get(y, [])
                       if (s.subject_id, p.pupil_id) not in grouped]
            if missing:
                out.append((s, y, missing))
    return out


def history(group_id: int) -> list[dict[str, Any]]:
    with database.connect() as conn:
        rows = conn.execute("SELECT * FROM teaching_group_audit WHERE group_id = ? "
                            "ORDER BY audit_id DESC", (int(group_id),)).fetchall()
    return [{"at": r["at"], "actor": r["actor"], "action": r["action"],
             "detail": json.loads(r["detail"]) if r["detail"] else {}} for r in rows]


# ── Changing groups ──────────────────────────────────────────────────

def create(data: dict[str, Any], *, actor: Principal) -> TeachingGroup:
    _require(actor, "teaching_group.create")
    clean = _validate(data, None)
    year = current_year()
    with database.connect() as conn:
        if conn.execute("SELECT 1 FROM teaching_groups WHERE academic_year = ? AND code = ? "
                        "COLLATE NOCASE", (year, clean["code"])).fetchone():
            raise ValidationError([f"There's already a group {clean['code']} in {year}"])
        cols = list(clean)
        cur = conn.execute(
            f"INSERT INTO teaching_groups (academic_year, {', '.join(cols)}, created_by, "  # nosec B608 - cols from EDITABLE_FIELDS
            f"updated_by) VALUES (?, {', '.join('?' * len(cols))}, ?, ?)",
            (year, *clean.values(), actor.username, actor.username))
        gid = cur.lastrowid
        _audit(conn, gid, "create", actor, {"code": clean["code"]})
    activity_log.record("teaching_group.create", target=f"TG{gid}", principal=actor)
    return get(gid)


def update(group_id: int, changes: dict[str, Any], *, actor: Principal
           ) -> tuple[TeachingGroup, list[str]]:
    _require(actor, "teaching_group.update", f"TG{group_id}")
    current = get(group_id)
    _editable(current)
    if not current.is_active:
        raise ValidationError(["Archived groups can't be changed - restore it first"])
    try:
        clean = _validate(changes, current)
    except ValidationError as e:
        activity_log.record("teaching_group.update", target=f"TG{group_id}", outcome="invalid",
                            principal=actor, problems=len(e.problems))
        raise
    diff = {k: {"from": getattr(current, k), "to": v} for k, v in clean.items()
            if getattr(current, k) != v}
    if not diff:
        return current, []
    if {"subject_id", "year_group"} & set(diff) and members(group_id, include_left=True):
        raise ValidationError([f"{current.code} has pupils - a group with pupils can't change "
                               "subject or year. Make a new group instead."])
    with database.connect() as conn:
        if "code" in diff and conn.execute(
                "SELECT 1 FROM teaching_groups WHERE academic_year = ? AND code = ? COLLATE "
                "NOCASE AND group_id <> ?", (current.academic_year, clean["code"], group_id)
                ).fetchone():
            raise ValidationError([f"There's already a group {clean['code']} in "
                                   f"{current.academic_year}"])
        sets = ", ".join(f"{k} = ?" for k in diff)
        conn.execute(f"UPDATE teaching_groups SET {sets}, updated_at = datetime('now'), "  # nosec B608 - keys from EDITABLE_FIELDS
                     "updated_by = ? WHERE group_id = ?",
                     (*(d["to"] for d in diff.values()), actor.username, group_id))
        _audit(conn, group_id, "update", actor,
               {k: ("changed" if k in {"teacher_email", "notes"} else d)
                for k, d in diff.items()})
    activity_log.record("teaching_group.update", target=f"TG{group_id}", principal=actor,
                        fields=sorted(diff))
    return get(group_id), sorted(diff)


def archive(group_id: int, *, actor: Principal) -> TeachingGroup:
    """Close a group. Its pupils come out of it (so they can join another), and the
    history keeps who was in it."""
    _require(actor, "teaching_group.archive", f"TG{group_id}")
    g = get(group_id)
    _editable(g)
    if not g.is_active:
        return g
    with database.connect() as conn:
        n = conn.execute("DELETE FROM teaching_group_members WHERE group_id = ?",
                         (group_id,)).rowcount
        conn.execute("UPDATE teaching_groups SET status = 'archived', updated_at = "
                     "datetime('now'), updated_by = ? WHERE group_id = ?",
                     (actor.username, group_id))
        _audit(conn, group_id, "archive", actor, {"pupils_removed": n})
    activity_log.record("teaching_group.archive", target=f"TG{group_id}", principal=actor,
                        removed=n)
    return get(group_id)


def restore(group_id: int, *, actor: Principal) -> TeachingGroup:
    _require(actor, "teaching_group.restore", f"TG{group_id}")
    g = get(group_id)
    _editable(g)
    if g.is_active:
        return g
    with database.connect() as conn:
        conn.execute("UPDATE teaching_groups SET status = 'active', updated_at = datetime('now'), "
                     "updated_by = ? WHERE group_id = ?", (actor.username, group_id))
        _audit(conn, group_id, "restore", actor, {})
    activity_log.record("teaching_group.restore", target=f"TG{group_id}", principal=actor)
    return get(group_id)


def delete(group_id: int, *, actor: Principal) -> None:
    """Delete a group set up by mistake - refused once it has had pupils."""
    _require(actor, "teaching_group.delete", f"TG{group_id}")
    g = get(group_id)
    _editable(g)
    if any(h["action"] in {"add", "move_in"} for h in history(group_id)):
        raise ValidationError([f"{g.code} has had pupils - archive it instead, so the record "
                               "of who was in it is kept"])
    with database.connect() as conn:
        conn.execute("DELETE FROM teaching_groups WHERE group_id = ?", (group_id,))
        _audit(conn, group_id, "delete", actor, {"code": g.code})
    activity_log.record("teaching_group.delete", target=f"TG{group_id}", principal=actor)


# ── Pupils in and out ────────────────────────────────────────────────

def add_pupils(pupil_ids: list[int], group_id: int, *, actor: Principal, move: bool = False,
               allow_over_capacity: bool = False
               ) -> tuple[list[P.Pupil], list[tuple[str, str]]]:
    """Put pupils in a group. A pupil already in another group for the subject is
    refused, or moved out of it when *move*. Returns (added, [(admission no., why not)])."""
    _require(actor, "teaching_group.add", f"TG{group_id}")
    g = get(group_id)
    _editable(g)
    if not g.is_active:
        raise ValidationError(["That group is archived"])
    inside = {p.pupil_id for p in members(group_id, include_left=True)}
    want: list[tuple[P.Pupil, Any]] = []
    refused: list[tuple[str, str]] = []
    with database.connect() as conn:
        for pid in dict.fromkeys(pupil_ids):
            p = P.get_pupil(pid)
            if p is None:
                refused.append((str(pid), "no such pupil"))
            elif p.roll_status != "on_roll":
                refused.append((p.admission_no, "not on roll"))
            elif p.year_group != g.year_group:
                refused.append((p.admission_no, f"in Year {p.year_group}, not Year {g.year_group}"))
            elif p.pupil_id in inside:
                refused.append((p.admission_no, f"already in {g.code}"))
            else:
                other = _group_for_subject(conn, p.pupil_id, g.subject_id, g.academic_year,
                                           g.group_id)
                if other and not move:
                    refused.append((p.admission_no, f"already in {other['code']} for this subject"))
                else:
                    want.append((p, other))
    if g.capacity is not None and not allow_over_capacity:
        room = g.capacity - len(members(group_id))
        if len(want) > room:
            raise ValidationError([f"{g.code} has room for {max(room, 0)} more (capacity "
                                   f"{g.capacity}); {len(want)} chosen"])
    moved_from: dict[int, int] = {}
    with database.connect() as conn:
        for p, other in want:
            if other:
                conn.execute("DELETE FROM teaching_group_members WHERE group_id = ? AND "
                             "pupil_id = ?", (other["group_id"], p.pupil_id))
                moved_from[other["group_id"]] = moved_from.get(other["group_id"], 0) + 1
            conn.execute("INSERT INTO teaching_group_members (group_id, pupil_id, added_by) "
                         "VALUES (?, ?, ?)", (group_id, p.pupil_id, actor.username))
        for gid, n in moved_from.items():
            _audit(conn, gid, "move_out", actor, {"pupils": n, "to_group": group_id})
        if want:
            moved = sum(moved_from.values())
            if len(want) - moved:
                _audit(conn, group_id, "add", actor, {"pupils": len(want) - moved})
            if moved:
                _audit(conn, group_id, "move_in", actor, {"pupils": moved})
    activity_log.record("teaching_group.add", target=f"TG{group_id}", principal=actor,
                        added=len(want), moved=sum(moved_from.values()) or None,
                        refused=len(refused) or None)
    return [p for p, _o in want], refused


def remove_pupils(pupil_ids: list[int], group_id: int, *, actor: Principal) -> int:
    _require(actor, "teaching_group.remove", f"TG{group_id}")
    g = get(group_id)
    _editable(g)
    with database.connect() as conn:
        n = 0
        for pid in dict.fromkeys(pupil_ids):
            n += conn.execute("DELETE FROM teaching_group_members WHERE group_id = ? AND "
                              "pupil_id = ?", (group_id, int(pid))).rowcount
        if n:
            _audit(conn, group_id, "remove", actor, {"pupils": n})
    activity_log.record("teaching_group.remove", target=f"TG{group_id}", principal=actor,
                        removed=n)
    return n


def add_form(form_id: int, group_id: int, *, actor: Principal, move: bool = False,
             allow_over_capacity: bool = False) -> tuple[list[P.Pupil], list[tuple[str, str]]]:
    """Add every pupil in a form group (same year) to the group."""
    f = FG.get(form_id)
    return add_pupils([p.pupil_id for p in FG.members(f)], group_id, actor=actor, move=move,
                      allow_over_capacity=allow_over_capacity)


def create_from_forms(subject_id: int, year_group: int, *, actor: Principal,
                      teacher_by_form: dict[int, dict[str, Any]] | None = None
                      ) -> tuple[list[TeachingGroup], list[str]]:
    """One group per open form in the year, coded "<form>/<subject code>", holding the
    form's pupils. Forms that already have that group, and pupils already grouped for
    the subject, are skipped. Returns (groups made, notes)."""
    _require(actor, "teaching_group.create")
    subj = S.get(subject_id)
    made, notes = [], []
    for f in FG.list_forms(year_group):
        code = f"{f.name}/{subj.code}"
        if find(code):
            notes.append(f"{code} already exists")
            continue
        extra = (teacher_by_form or {}).get(f.form_id, {})
        g = create({"code": code, "subject_id": subject_id, "year_group": year_group,
                    "kind": "Mixed", "room": f.room, **extra}, actor=actor)
        added, refused = add_pupils([p.pupil_id for p in FG.members(f)], g.group_id,
                                    actor=actor, allow_over_capacity=True)
        made.append(g)
        if refused:
            notes.append(f"{code}: {len(refused)} pupil(s) not added (already grouped)")
    if not FG.list_forms(year_group):
        notes.append(f"Year {year_group} has no forms set up")
    return made, notes


# ── Class list ───────────────────────────────────────────────────────

def export_class_list(group_id: int, path: str | Path, *, actor: Principal,
                      include_needs: bool = False) -> int:
    """Write the group's pupils to a CSV; returns how many. SEN/FSM/EAL columns only
    for pupil editors."""
    if not actor.is_staff:
        raise PermissionDenied("Only staff can export class lists.")
    if include_needs and not actor.can_edit_pupils:
        activity_log.record("teaching_group.export", target=f"TG{group_id}", outcome="denied",
                            principal=actor)
        raise PermissionDenied("Your account can't export SEN, FSM or EAL details.")
    g = get(group_id)
    subj = S.get(g.subject_id)
    rows = members(group_id)
    cols = ["Admission no", "Surname", "First name", "Preferred name", "Form", "Gender"] + (
        ["SEN", "FSM", "EAL"] if include_needs else [])
    with Path(path).open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow([_safe(f"Group {g.code}"), _safe(subj.name), f"Year {g.year_group}",
                    _safe(f"Teacher: {g.teacher_name or ''}"), g.academic_year])
        w.writerow(cols)
        for p in rows:
            vals = [p.admission_no, p.legal_last_name, p.legal_first_name, p.preferred_name,
                    p.form_group, p.gender]
            if include_needs:
                vals += [p.sen_status, "Y" if p.fsm_eligible else "", "Y" if p.eal else ""]
            w.writerow([_safe(v) for v in vals])
    activity_log.record("teaching_group.export", target=f"TG{group_id}", principal=actor,
                        rows=len(rows), needs=include_needs)
    return len(rows)
