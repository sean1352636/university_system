"""Year groups (Years 7-11): who leads each year, how big it should be, and
a live profile of the pupils in it.

Rules shared by the GUI and CLI:

* There are always five year groups; their settings (head of year and their
  e-mail, assistant head of year, capacity, notes) start empty. *Clear*
  empties them again. Every change is kept in ``year_group_audit``.
* Numbers are never stored - :func:`profile` works them out from the pupil
  records each time, so they can't drift: on roll, by gender, by form, SEN /
  FSM / EAL counts, joiners and leavers this academic year, and pupils whose
  age doesn't fit the year (taught out of year group - often deliberate, but
  worth seeing).
* :func:`move_pupils` moves on-roll pupils to another year group (repeating or
  skipping a year). A form named after the old year ("8K") is cleared, since
  it won't fit the new year; other forms are kept.
* Only :data:`access.YEAR_GROUP_EDITORS` change settings or move pupils; all
  staff can read.
"""

from __future__ import annotations

import datetime as _dt
import json
import re
from dataclasses import dataclass, field, fields
from typing import Any

from education_system.systems.secondary.modules.pupils.domain import contacts as C
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import YEAR_GROUP_EDITORS, Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

KEY_STAGES = {7: "KS3", 8: "KS3", 9: "KS3", 10: "KS4", 11: "KS4"}
MAX_CAPACITY = 500
EDITABLE_FIELDS: tuple[str, ...] = (
    "head_of_year", "head_of_year_email", "assistant_head", "capacity", "notes",
)
FIELD_LABELS = {
    "head_of_year": "Head of year", "head_of_year_email": "Head of year e-mail",
    "assistant_head": "Assistant head of year", "capacity": "Capacity", "notes": "Notes",
}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS year_groups (
    year_group         INTEGER PRIMARY KEY CHECK (year_group BETWEEN 7 AND 11),
    head_of_year       TEXT,
    head_of_year_email TEXT,
    assistant_head     TEXT,
    capacity           INTEGER CHECK (capacity IS NULL OR capacity >= 0),
    notes              TEXT,
    updated_at         TEXT,
    updated_by         TEXT
);
CREATE TABLE IF NOT EXISTS year_group_audit (
    audit_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    year_group INTEGER NOT NULL,
    action     TEXT NOT NULL CHECK (action IN ('update', 'clear', 'move_pupils')),
    actor      TEXT NOT NULL,
    detail     TEXT,
    at         TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_year_group_audit ON year_group_audit (year_group, audit_id);
"""

database.register_schema("year_groups", _SCHEMA)

ValidationError = P.ValidationError
PermissionDenied = P.PermissionDenied


@dataclass(frozen=True)
class YearGroup:
    year_group: int
    head_of_year: str | None = None
    head_of_year_email: str | None = None
    assistant_head: str | None = None
    capacity: int | None = None
    notes: str | None = None
    updated_at: str | None = None
    updated_by: str | None = None

    @property
    def label(self) -> str:
        return f"Year {self.year_group}"

    @property
    def key_stage(self) -> str:
        return KEY_STAGES[self.year_group]


def _check_year(year_group: Any) -> int:
    try:
        y = int(year_group)
    except (TypeError, ValueError):
        y = 0
    if y not in P.YEAR_GROUPS:
        raise ValidationError(["Year group must be 7, 8, 9, 10 or 11"])
    return y


def _require(actor: Principal, action: str, target: Any) -> None:
    if actor.role not in YEAR_GROUP_EDITORS:
        activity_log.record(action, target=target, outcome="denied", principal=actor)
        raise PermissionDenied("Your account can view year groups but not change them.")


def _audit(conn, year: int, action: str, actor: Principal, detail: dict) -> None:
    conn.execute("INSERT INTO year_group_audit (year_group, action, actor, detail) "
                 "VALUES (?, ?, ?, ?)",
                 (year, action, actor.username or "unknown",
                  json.dumps(detail, default=str, sort_keys=True)))


# ── Settings ─────────────────────────────────────────────────────────

def get(year_group: int) -> YearGroup:
    y = _check_year(year_group)
    with database.connect() as conn:
        r = conn.execute("SELECT * FROM year_groups WHERE year_group = ?", (y,)).fetchone()
    return YearGroup(**{f.name: r[f.name] for f in fields(YearGroup)}) if r else YearGroup(y)


def list_all() -> list[YearGroup]:
    with database.connect() as conn:
        rows = {r["year_group"]: r for r in conn.execute("SELECT * FROM year_groups")}
    return [YearGroup(**{f.name: rows[y][f.name] for f in fields(YearGroup)}) if y in rows
            else YearGroup(y) for y in P.YEAR_GROUPS]


def _validate(data: dict[str, Any]) -> dict[str, Any]:
    problems: list[str] = []
    unknown = set(data) - set(EDITABLE_FIELDS)
    if unknown:
        problems.append(f"Unknown field(s): {', '.join(sorted(unknown))}")
    out: dict[str, Any] = {}
    for key in ("head_of_year", "assistant_head"):
        if key in data:
            out[key] = P._clean_text(data.get(key), 100)
    if "head_of_year_email" in data:
        email = P._clean_text(data.get("head_of_year_email"), 254)
        email = email.lower() if email else None
        if email and not C.valid_email(email):
            problems.append("The head of year's e-mail address doesn't look right")
        out["head_of_year_email"] = email
    if "capacity" in data:
        raw = data.get("capacity")
        if raw in (None, ""):
            out["capacity"] = None
        else:
            try:
                cap = int(str(raw).strip())
            except ValueError:
                cap = -1
            if not 0 <= cap <= MAX_CAPACITY:
                problems.append(f"Capacity must be a whole number from 0 to {MAX_CAPACITY}")
            out["capacity"] = cap
    if "notes" in data:
        out["notes"] = P._clean_text(data.get("notes"), 2000)
    if problems:
        raise ValidationError(problems)
    return out


def update(year_group: int, changes: dict[str, Any], *, actor: Principal) -> tuple[YearGroup,
                                                                                   list[str]]:
    """Change some settings; returns (year group, changed field names)."""
    y = _check_year(year_group)
    _require(actor, "year_group.update", f"Y{y}")
    try:
        clean = _validate(changes)
    except ValidationError as e:
        activity_log.record("year_group.update", target=f"Y{y}", outcome="invalid",
                            principal=actor, problems=len(e.problems))
        raise
    current = get(y)
    diff = {k: {"from": getattr(current, k), "to": v} for k, v in clean.items()
            if getattr(current, k) != v}
    if diff:
        merged = {k: getattr(current, k) for k in EDITABLE_FIELDS}
        merged.update({k: d["to"] for k, d in diff.items()})
        with database.connect() as conn:
            conn.execute(
                "INSERT INTO year_groups (year_group, head_of_year, head_of_year_email, "
                "assistant_head, capacity, notes, updated_at, updated_by) VALUES "
                "(?, ?, ?, ?, ?, ?, datetime('now'), ?) ON CONFLICT (year_group) DO UPDATE SET "
                "head_of_year = excluded.head_of_year, head_of_year_email = "
                "excluded.head_of_year_email, assistant_head = excluded.assistant_head, "
                "capacity = excluded.capacity, notes = excluded.notes, "
                "updated_at = excluded.updated_at, updated_by = excluded.updated_by",
                (y, *(merged[k] for k in EDITABLE_FIELDS), actor.username))
            _audit(conn, y, "update", actor, diff)
    activity_log.record("year_group.update", target=f"Y{y}", principal=actor,
                        outcome="ok" if diff else "no_change", fields=sorted(diff) or None)
    return get(y), sorted(diff)


def clear(year_group: int, *, actor: Principal) -> YearGroup:
    """Empty a year group's settings (pupils aren't touched)."""
    y = _check_year(year_group)
    _require(actor, "year_group.clear", f"Y{y}")
    current = get(y)
    had = {k: getattr(current, k) for k in EDITABLE_FIELDS if getattr(current, k) is not None}
    with database.connect() as conn:
        conn.execute("DELETE FROM year_groups WHERE year_group = ?", (y,))
        if had:
            _audit(conn, y, "clear", actor, {"cleared": had})
    activity_log.record("year_group.clear", target=f"Y{y}", principal=actor,
                        outcome="ok" if had else "no_change")
    return get(y)


def history(year_group: int) -> list[dict[str, Any]]:
    y = _check_year(year_group)
    with database.connect() as conn:
        rows = conn.execute("SELECT * FROM year_group_audit WHERE year_group = ? "
                            "ORDER BY audit_id DESC", (y,)).fetchall()
    return [{"at": r["at"], "actor": r["actor"], "action": r["action"],
             "detail": json.loads(r["detail"]) if r["detail"] else {}} for r in rows]


# ── Live profile ─────────────────────────────────────────────────────

@dataclass
class Profile:
    year_group: int
    on_roll: int = 0
    by_gender: dict[str, int] = field(default_factory=dict)
    forms: dict[str, int] = field(default_factory=dict)
    no_form: int = 0
    sen_support: int = 0
    ehcp: int = 0
    fsm: int = 0
    eal: int = 0
    joined_this_year: int = 0
    left_this_year: int = 0
    out_of_year: list[tuple[P.Pupil, int]] = field(default_factory=list)  # (pupil, expected)
    capacity: int | None = None

    @property
    def spaces(self) -> int | None:
        return None if self.capacity is None else self.capacity - self.on_roll

    @property
    def over_capacity(self) -> bool:
        return self.spaces is not None and self.spaces < 0


def _profiles(today: _dt.date) -> dict[int, Profile]:
    start = P.academic_year_start(today)
    lo, hi = start.isoformat(), _dt.date(start.year + 1, 8, 31).isoformat()
    caps = {g.year_group: g.capacity for g in list_all()}
    out = {y: Profile(y, capacity=caps[y]) for y in P.YEAR_GROUPS}
    for p in P.list_pupils(roll_status=None):
        pr = out.get(p.year_group)
        if pr is None:
            continue
        if p.roll_status == "left":
            if p.leaving_date and lo <= p.leaving_date <= hi:
                pr.left_this_year += 1
            continue
        pr.on_roll += 1
        pr.by_gender[p.gender] = pr.by_gender.get(p.gender, 0) + 1
        if p.form_group:
            pr.forms[p.form_group] = pr.forms.get(p.form_group, 0) + 1
        else:
            pr.no_form += 1
        pr.sen_support += p.sen_status == "K"
        pr.ehcp += p.sen_status == "E"
        pr.fsm += bool(p.fsm_eligible)
        pr.eal += bool(p.eal)
        if lo <= (p.admission_date or "") <= hi:
            pr.joined_this_year += 1
        expected = P.expected_year_group(p.date_of_birth, today)
        if expected != p.year_group:
            pr.out_of_year.append((p, expected))
    for pr in out.values():
        pr.forms = dict(sorted(pr.forms.items()))
    return out


def profile(year_group: int, today: _dt.date | None = None) -> Profile:
    return _profiles(today or _dt.date.today())[_check_year(year_group)]


def overview(today: _dt.date | None = None) -> list[tuple[YearGroup, Profile]]:
    profiles = _profiles(today or _dt.date.today())
    return [(g, profiles[g.year_group]) for g in list_all()]


# ── Moving pupils ────────────────────────────────────────────────────

def form_after_move(form: str | None, old: int, new: int) -> str | None:
    """A form named after the old year ("8K") doesn't fit the new one."""
    if form and re.match(rf"^{old}(?!\d)", form):
        return None
    return form


def move_pupils(pupil_ids: list[int], to_year: int, *, actor: Principal
                ) -> tuple[list[P.Pupil], list[tuple[str, str]]]:
    """Move on-roll pupils to *to_year*. Returns (moved, [(admission no., why not)])."""
    to_year = _check_year(to_year)
    _require(actor, "year_group.move", f"Y{to_year}")
    moved, refused = [], []
    by_from: dict[int, int] = {}
    for pid in dict.fromkeys(pupil_ids):
        p = P.get_pupil(pid)
        if p is None:
            refused.append((str(pid), "no such pupil"))
        elif p.roll_status != "on_roll":
            refused.append((p.admission_no, "not on roll"))
        elif p.year_group == to_year:
            refused.append((p.admission_no, f"already in Year {to_year}"))
        else:
            try:
                new = P.update_pupil(p.pupil_id, {
                    "year_group": to_year,
                    "form_group": form_after_move(p.form_group, p.year_group, to_year) or ""},
                    actor=actor)
            except (P.ValidationError, P.PermissionDenied) as e:
                refused.append((p.admission_no, str(e)))
                continue
            moved.append(new)
            by_from[p.year_group] = by_from.get(p.year_group, 0) + 1
    if moved:
        with database.connect() as conn:
            _audit(conn, to_year, "move_pupils", actor,
                   {"moved_in": len(moved), "from_years": by_from})
    activity_log.record("year_group.move", target=f"Y{to_year}", principal=actor,
                        moved=len(moved), refused=len(refused) or None)
    return moved, refused
