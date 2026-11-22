"""Enrichment and clubs: after-school and lunchtime clubs, who's in them,
weekly registers and who takes part.

**Clubs.** As in the old screen, a club has a name, category, description,
meeting day and times, room, leader, capacity, eligible year groups, notes
and an active flag. Added: the leader's staff login (so they can run the
club), whether parental consent is needed (sport fixtures, trips), a cost per
term and the term dates it runs between.

**Members.** A pupil joins a club they're eligible for (year group, on roll).
When the club is full they go on the waiting list (old "Waitlisted"); when a
member leaves or is suspended the first pupil waiting is moved up. Joining a
club that meets at the same time as another of the pupil's clubs is a warning.
A club that needs consent shows who is still waiting for it, and a register
can't mark a pupil present without it. A member with registers stays on
record: they're marked Left rather than removed.

**Registers.** The leader takes a register for a meeting (present / absent /
excused) - not for a future date, and only for members. A meeting can be
cancelled with a reason; families can be e-mailed.

**Who.** The enrichment lead (:data:`ENRICHMENT_EDITORS`) sets up, changes and
closes clubs. A club's leader manages its members and registers. All staff
can view clubs. Every change goes in ``club_audit`` and the activity log.
"""

from __future__ import annotations

import csv
import datetime as _dt
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import ENRICHMENT_EDITORS, Principal
from education_system.systems.secondary.core.utilities.exports import safe_cell as _safe
from education_system.systems.secondary.core.academic_calendar.school_year import today as _today
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

CATEGORIES: tuple[str, ...] = ("Sport", "Arts", "Academic", "STEM", "Service", "Music",
                               "Drama", "Other")
DAYS: tuple[str, ...] = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat")
STATUSES: tuple[str, ...] = ("Active", "Left", "Suspended", "Waitlisted")
MARKS = {"P": "Present", "A": "Absent", "E": "Excused"}
YEARS = (7, 8, 9, 10, 11)
_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS clubs (
    club_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name             TEXT NOT NULL UNIQUE COLLATE NOCASE,
    category         TEXT NOT NULL DEFAULT 'Other',
    description      TEXT,
    day_of_week      TEXT,
    start_time       TEXT,
    end_time         TEXT,
    room             TEXT,
    leader           TEXT,
    leader_username  TEXT,
    max_capacity     INTEGER,
    eligible_years   TEXT,
    consent_required INTEGER NOT NULL DEFAULT 0,
    cost             REAL,
    starts_on        TEXT,
    ends_on          TEXT,
    is_active        INTEGER NOT NULL DEFAULT 1,
    notes            TEXT,
    created_at       TEXT NOT NULL DEFAULT (datetime('now')),
    created_by       TEXT,
    updated_at       TEXT NOT NULL DEFAULT (datetime('now')),
    updated_by       TEXT
);
CREATE TABLE IF NOT EXISTS club_members (
    member_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    club_id       INTEGER NOT NULL REFERENCES clubs (club_id) ON DELETE CASCADE,
    pupil_id      INTEGER NOT NULL REFERENCES pupils (pupil_id),
    status        TEXT NOT NULL DEFAULT 'Active'
                  CHECK (status IN ('Active', 'Left', 'Suspended', 'Waitlisted')),
    joined_on     TEXT NOT NULL,
    left_on       TEXT,
    queued_at     TEXT NOT NULL DEFAULT (datetime('now')),
    consent_on    TEXT,
    consent_by    TEXT,
    notes         TEXT,
    updated_at    TEXT NOT NULL DEFAULT (datetime('now')),
    updated_by    TEXT,
    UNIQUE (club_id, pupil_id)
);
CREATE INDEX IF NOT EXISTS ix_club_members_pupil ON club_members (pupil_id);
CREATE TABLE IF NOT EXISTS club_meetings (
    meeting_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    club_id      INTEGER NOT NULL REFERENCES clubs (club_id) ON DELETE CASCADE,
    date         TEXT NOT NULL,
    cancelled    INTEGER NOT NULL DEFAULT 0,
    note         TEXT,
    taken_by     TEXT,
    taken_at     TEXT,
    UNIQUE (club_id, date)
);
CREATE TABLE IF NOT EXISTS club_attendance (
    meeting_id  INTEGER NOT NULL REFERENCES club_meetings (meeting_id) ON DELETE CASCADE,
    pupil_id    INTEGER NOT NULL REFERENCES pupils (pupil_id),
    mark        TEXT NOT NULL CHECK (mark IN ('P', 'A', 'E')),
    PRIMARY KEY (meeting_id, pupil_id)
);
CREATE TABLE IF NOT EXISTS club_audit (
    audit_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    club_id   INTEGER,
    pupil_id  INTEGER,
    action    TEXT NOT NULL CHECK (action IN (
        'create', 'update', 'active', 'delete', 'join', 'status', 'consent', 'member_delete',
        'register', 'cancel', 'notify')),
    actor     TEXT NOT NULL,
    detail    TEXT,
    at        TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

database.register_schema("enrichment", _SCHEMA)

ValidationError = P.ValidationError
PermissionDenied = P.PermissionDenied
NotFound = P.NotFound


# ── Records ──────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Club:
    club_id: int
    name: str
    category: str
    description: str | None
    day_of_week: str | None
    start_time: str | None
    end_time: str | None
    room: str | None
    leader: str | None
    leader_username: str | None
    max_capacity: int | None
    eligible_years: str | None
    consent_required: bool
    cost: float | None
    starts_on: str | None
    ends_on: str | None
    is_active: bool
    notes: str | None
    created_at: str
    created_by: str | None
    updated_at: str
    updated_by: str | None
    active_members: int = 0
    waiting: int = 0

    @property
    def years(self) -> tuple[int, ...]:
        if not self.eligible_years:
            return YEARS
        return tuple(int(y) for y in self.eligible_years.split(",") if y.strip())

    @property
    def years_label(self) -> str:
        return "All" if not self.eligible_years else ", ".join(map(str, self.years))

    @property
    def time_label(self) -> str:
        if self.start_time and self.end_time:
            return f"{self.start_time}-{self.end_time}"
        return self.start_time or ""

    @property
    def when(self) -> str:
        return " ".join(x for x in (self.day_of_week, self.time_label) if x) or "-"

    @property
    def spaces(self) -> int | None:
        return None if self.max_capacity is None else self.max_capacity - self.active_members


@dataclass(frozen=True)
class Member:
    member_id: int
    club_id: int
    pupil_id: int
    status: str
    joined_on: str
    left_on: str | None
    queued_at: str
    consent_on: str | None
    consent_by: str | None
    notes: str | None
    updated_at: str
    updated_by: str | None
    pupil_name: str = ""
    admission_no: str = ""
    year_group: int = 0
    form_group: str | None = None
    club_name: str = ""

    @property
    def has_consent(self) -> bool:
        return bool(self.consent_on)


@dataclass(frozen=True)
class Meeting:
    meeting_id: int
    club_id: int
    date: str
    cancelled: bool
    note: str | None
    taken_by: str | None
    taken_at: str | None


_CLUB_SELECT = """
SELECT c.*,
       (SELECT COUNT(*) FROM club_members m WHERE m.club_id = c.club_id
         AND m.status = 'Active') AS active_members,
       (SELECT COUNT(*) FROM club_members m WHERE m.club_id = c.club_id
         AND m.status = 'Waitlisted') AS waiting
FROM clubs c
"""
_MEMBER_SELECT = """
SELECT m.*, p.legal_last_name, p.legal_first_name, p.preferred_name, p.admission_no,
       p.year_group, p.form_group, c.name AS club_name
FROM club_members m JOIN pupils p USING (pupil_id) JOIN clubs c USING (club_id)
"""
_MEMBER_BASE = ("member_id", "club_id", "pupil_id", "status", "joined_on", "left_on",
                "queued_at", "consent_on", "consent_by", "notes", "updated_at", "updated_by")


def _club(r) -> Club:
    d = {k: r[k] for k in Club.__dataclass_fields__}
    d["consent_required"], d["is_active"] = bool(d["consent_required"]), bool(d["is_active"])
    return Club(**d)


def _member(r) -> Member:
    first = r["preferred_name"] or r["legal_first_name"]
    return Member(**{k: r[k] for k in _MEMBER_BASE},
                  pupil_name=f"{r['legal_last_name']}, {first}",
                  admission_no=r["admission_no"], year_group=r["year_group"],
                  form_group=r["form_group"], club_name=r["club_name"])


# ── Helpers ──────────────────────────────────────────────────────────

def _same(a: str | None, b: str | None) -> bool:
    return bool(a) and bool(b) and a.strip().lower() == b.strip().lower()  # type: ignore[union-attr]


def is_editor(actor: Principal) -> bool:
    return actor.role in ENRICHMENT_EDITORS


def can_run(actor: Principal, club: Club) -> bool:
    """The club's leader, or the enrichment lead."""
    return is_editor(actor) or (actor.is_staff and _same(actor.username, club.leader_username))


def _require_editor(actor: Principal, action: str, target: Any = None) -> None:
    if not is_editor(actor):
        activity_log.record(action, target=target, outcome="denied", principal=actor)
        raise PermissionDenied("Only the enrichment lead can set up or change clubs.")


def _require_runner(actor: Principal, club: Club, action: str) -> None:
    if not can_run(actor, club):
        activity_log.record(action, target=f"club:{club.club_id}", outcome="denied",
                            principal=actor)
        raise PermissionDenied(f"Only {club.name}'s leader (or the enrichment lead) can do "
                               "this.")


def _audit(conn, action: str, actor: Principal, *, club_id: int | None = None,
           pupil_id: int | None = None, detail: dict | None = None) -> None:
    conn.execute("INSERT INTO club_audit (club_id, pupil_id, action, actor, detail) "
                 "VALUES (?, ?, ?, ?, ?)",
                 (club_id, pupil_id, action, actor.username or "unknown",
                  json.dumps(detail, default=str, sort_keys=True) if detail else None))


def _date(value: Any, label: str, problems: list[str]) -> _dt.date | None:
    if value in (None, ""):
        return None
    if isinstance(value, _dt.date):
        return value
    try:
        return _dt.date.fromisoformat(str(value).strip())
    except ValueError:
        problems.append(f"{label} must be a date (YYYY-MM-DD)")
        return None


def _minutes(t: str) -> int:
    return int(t[:2]) * 60 + int(t[3:])


# ── Clubs ────────────────────────────────────────────────────────────

def get_club(club_id: int) -> Club:
    with database.connect() as conn:
        r = conn.execute(_CLUB_SELECT + " WHERE c.club_id = ?", (int(club_id),)).fetchone()
    if r is None:
        raise NotFound(f"No club #{club_id}")
    return _club(r)


def list_clubs(*, active_only: bool = False, category: str | None = None,
               day: str | None = None, year_group: int | None = None,
               leader: str | None = None, search: str | None = None) -> list[Club]:
    sql, where, params = _CLUB_SELECT, [], []
    if active_only:
        where.append("c.is_active = 1")
    if category:
        where.append("c.category = ?")
        params.append(category)
    if day:
        where.append("c.day_of_week = ?")
        params.append(day)
    if leader:
        where.append("(lower(c.leader_username) = lower(?) OR lower(c.leader) = lower(?))")
        params += [leader, leader]
    for term in (search or "").split():
        where.append("(c.name LIKE ? OR c.description LIKE ? OR c.leader LIKE ?)")
        params += [f"%{term}%"] * 3
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY c.is_active DESC, c.name COLLATE NOCASE"
    with database.connect() as conn:
        rows = [_club(r) for r in conn.execute(sql, params)]
    if year_group:
        rows = [c for c in rows if int(year_group) in c.years]
    return rows


EDITABLE_FIELDS = ("name", "category", "description", "day_of_week", "start_time",
                   "end_time", "room", "leader", "leader_username", "max_capacity",
                   "eligible_years", "consent_required", "cost", "starts_on", "ends_on",
                   "notes")


def _clean_club(data: dict[str, Any], current: Club | None) -> dict[str, Any]:
    problems: list[str] = []
    unknown = set(data) - set(EDITABLE_FIELDS)
    if unknown:
        problems.append(f"Unknown field(s): {', '.join(sorted(unknown))}")
    merged: dict[str, Any] = {k: getattr(current, k) for k in EDITABLE_FIELDS} if current \
        else {}
    merged.update(data)
    out: dict[str, Any] = {}
    out["name"] = P._clean_text(merged.get("name"), 80)
    if not out["name"]:
        problems.append("Give the club a name")
    cat = (P._clean_text(merged.get("category"), 20) or "Other").title()
    cat = "STEM" if cat == "Stem" else cat
    if cat not in CATEGORIES:
        problems.append(f"Category must be one of {', '.join(CATEGORIES)}")
    out["category"] = cat
    out["description"] = P._clean_text(merged.get("description"), 2000)
    day = P._clean_text(merged.get("day_of_week"), 10)
    if day:
        day = day[:3].title()
        if day not in DAYS:
            problems.append(f"Day must be one of {', '.join(DAYS)}")
    out["day_of_week"] = day
    for key, label in (("start_time", "Start time"), ("end_time", "End time")):
        t = P._clean_text(merged.get(key), 5)
        if t and len(t) == 4 and t[1] == ":":
            t = "0" + t
        if t and not _TIME_RE.match(t):
            problems.append(f"{label} must be HH:MM")
            t = None
        out[key] = t
    if out["start_time"] and out["end_time"] and out["end_time"] <= out["start_time"]:
        problems.append("The end time must be after the start time")
    if out["end_time"] and not out["start_time"]:
        problems.append("Give a start time too")
    out["room"] = P._clean_text(merged.get("room"), 40)
    out["leader"] = P._clean_text(merged.get("leader"), 100)
    out["leader_username"] = P._clean_text(merged.get("leader_username"), 100)
    if out["leader_username"]:
        from education_system.systems.secondary.modules.curriculum.domain import (
            teaching_groups as TG,
        )
        login = next((t for t in TG.teacher_choices()
                      if _same(t["username"], out["leader_username"])), None)
        if login is None:
            if current is None or out["leader_username"] != current.leader_username:
                problems.append(f"'{out['leader_username']}' isn't a secondary staff login")
        else:
            out["leader_username"] = login["username"]
            out["leader"] = out["leader"] or login["display_name"]
    cap = merged.get("max_capacity")
    out["max_capacity"] = None
    if cap not in (None, ""):
        try:
            out["max_capacity"] = int(str(cap).strip())
        except ValueError:
            out["max_capacity"] = 0
        if not 1 <= out["max_capacity"] <= 500:
            problems.append("Capacity must be a whole number from 1 to 500 (blank = no limit)")
    years = merged.get("eligible_years")
    if isinstance(years, (list, tuple, set)):
        years = ",".join(str(y) for y in years)
    ys: list[int] = []
    for part in str(years or "").replace(" ", ",").split(","):
        if not part:
            continue
        if not part.isdigit() or int(part) not in YEARS:
            problems.append("Eligible years must be from 7 to 11 (blank = all)")
            break
        if int(part) not in ys:
            ys.append(int(part))
    out["eligible_years"] = ",".join(map(str, sorted(ys))) if ys and len(ys) < 5 else None
    out["consent_required"] = int(str(merged.get("consent_required") or "").strip().lower()
                                  in {"1", "true", "yes", "y"})
    cost = merged.get("cost")
    out["cost"] = None
    if cost not in (None, ""):
        try:
            out["cost"] = round(float(str(cost).strip().lstrip("£")), 2)
        except ValueError:
            out["cost"] = -1.0
        if not 0 <= out["cost"] <= 1000:
            problems.append("Cost must be from £0 to £1000 (blank = free)")
        elif out["cost"] == 0:
            out["cost"] = None
    s = _date(merged.get("starts_on"), "Starts on", problems)
    e = _date(merged.get("ends_on"), "Ends on", problems)
    if s and e and e < s:
        problems.append("The club can't end before it starts")
    out["starts_on"], out["ends_on"] = (s.isoformat() if s else None,
                                        e.isoformat() if e else None)
    out["notes"] = P._clean_text(merged.get("notes"), 2000)
    if problems:
        raise ValidationError(problems)
    return out


def create_club(data: dict[str, Any], *, actor: Principal) -> Club:
    _require_editor(actor, "clubs.create")
    clean = _clean_club(data, None)
    with database.connect() as conn:
        if conn.execute("SELECT 1 FROM clubs WHERE name = ?", (clean["name"],)).fetchone():
            raise ValidationError([f"There's already a club called '{clean['name']}'"])
        cols = list(clean)
        cid = conn.execute(
            f"INSERT INTO clubs ({', '.join(cols)}, created_by, updated_by) "  # nosec B608 - columns from _clean_club
            f"VALUES ({', '.join('?' * len(cols))}, ?, ?)",
            (*clean.values(), actor.username, actor.username)).lastrowid
        _audit(conn, "create", actor, club_id=cid)
    activity_log.record("clubs.create", target=f"club:{cid}", principal=actor)
    return get_club(cid)


def update_club(club_id: int, changes: dict[str, Any], *, actor: Principal) -> Club:
    c = get_club(club_id)
    _require_editor(actor, "clubs.update", f"club:{c.club_id}")
    clean = _clean_club(changes, c)
    diff = {k: v for k, v in clean.items()
            if getattr(c, k) != (bool(v) if k == "consent_required" else v)}
    if not diff:
        return c
    if clean["max_capacity"] is not None and clean["max_capacity"] < c.active_members:
        raise ValidationError([f"{c.active_members} pupils are already members - capacity "
                               "can't be lower"])
    with database.connect() as conn:
        if "name" in diff and conn.execute("SELECT 1 FROM clubs WHERE name = ? AND "
                                           "club_id != ?", (clean["name"], c.club_id)
                                           ).fetchone():
            raise ValidationError([f"There's already a club called '{clean['name']}'"])
        sets = ", ".join(f"{k} = ?" for k in diff)
        conn.execute(f"UPDATE clubs SET {sets}, updated_at = datetime('now'), "  # nosec B608 - keys from _clean_club
                     "updated_by = ? WHERE club_id = ?", (*diff.values(), actor.username,
                                                          c.club_id))
        _audit(conn, "update", actor, club_id=c.club_id, detail={"fields": sorted(diff)})
    activity_log.record("clubs.update", target=f"club:{c.club_id}", principal=actor,
                        fields=sorted(diff))
    new = get_club(c.club_id)
    if "max_capacity" in diff:
        _promote(new, actor)
    return get_club(c.club_id)


def toggle_active(club_id: int, *, actor: Principal) -> Club:
    """The old 'Toggle active'. A closed club keeps its members and registers."""
    c = get_club(club_id)
    _require_editor(actor, "clubs.active", f"club:{c.club_id}")
    with database.connect() as conn:
        conn.execute("UPDATE clubs SET is_active = ?, updated_at = datetime('now'), "
                     "updated_by = ? WHERE club_id = ?",
                     (0 if c.is_active else 1, actor.username, c.club_id))
        _audit(conn, "active", actor, club_id=c.club_id, detail={"active": not c.is_active})
    activity_log.record("clubs.active", target=f"club:{c.club_id}", principal=actor)
    return get_club(c.club_id)


def delete_club(club_id: int, *, actor: Principal) -> Club:
    c = get_club(club_id)
    _require_editor(actor, "clubs.delete", f"club:{c.club_id}")
    with database.connect() as conn:
        n = conn.execute("SELECT COUNT(*) FROM club_meetings WHERE club_id = ? AND "
                         "taken_at IS NOT NULL", (c.club_id,)).fetchone()[0]
        if n:
            raise ValidationError([f"{c.name} has {n} register(s) - make it inactive "
                                   "instead"])
        conn.execute("DELETE FROM club_members WHERE club_id = ?", (c.club_id,))
        conn.execute("DELETE FROM clubs WHERE club_id = ?", (c.club_id,))
        _audit(conn, "delete", actor, club_id=c.club_id, detail={"name": c.name})
    activity_log.record("clubs.delete", target=f"club:{c.club_id}", principal=actor)
    return c


def overview() -> dict[str, Any]:
    """The old overview line: clubs, active clubs, active memberships."""
    with database.connect() as conn:
        total, active = conn.execute("SELECT COUNT(*), COALESCE(SUM(is_active), 0) FROM "
                                     "clubs").fetchone()
        members, pupils, waiting = conn.execute(
            "SELECT SUM(status = 'Active'), COUNT(DISTINCT CASE WHEN status = 'Active' THEN "
            "pupil_id END), SUM(status = 'Waitlisted') FROM club_members").fetchone()
    return {"total": total, "active": active, "active_memberships": members or 0,
            "pupils_in_clubs": pupils or 0, "waiting": waiting or 0}


def history(club_id: int, *, limit: int = 300) -> list[dict[str, Any]]:
    with database.connect() as conn:
        return [{"at": r["at"], "actor": r["actor"], "action": r["action"],
                 "pupil_id": r["pupil_id"], "detail": json.loads(r["detail"] or "{}")}
                for r in conn.execute("SELECT * FROM club_audit WHERE club_id = ? ORDER BY "
                                      "audit_id DESC LIMIT ?", (int(club_id), int(limit)))]


# ── Members ──────────────────────────────────────────────────────────

def get_member(member_id: int) -> Member:
    with database.connect() as conn:
        r = conn.execute(_MEMBER_SELECT + " WHERE m.member_id = ?", (int(member_id),)
                         ).fetchone()
    if r is None:
        raise NotFound(f"No membership #{member_id}")
    return _member(r)


def find_member(club_id: int, pupil_id: int) -> Member | None:
    with database.connect() as conn:
        r = conn.execute(_MEMBER_SELECT + " WHERE m.club_id = ? AND m.pupil_id = ?",
                         (int(club_id), int(pupil_id))).fetchone()
    return _member(r) if r else None


def list_members(club_id: int, *, status: str | None = None) -> list[Member]:
    """Members, Active first; the waiting list in the order pupils joined it."""
    sql, params = _MEMBER_SELECT + " WHERE m.club_id = ?", [int(club_id)]
    if status:
        if status not in STATUSES:
            raise ValidationError([f"Status must be one of {', '.join(STATUSES)}"])
        sql += " AND m.status = ?"
        params.append(status)
    sql += (" ORDER BY CASE m.status WHEN 'Active' THEN 0 WHEN 'Waitlisted' THEN 1 "
            "WHEN 'Suspended' THEN 2 ELSE 3 END, CASE WHEN m.status = 'Waitlisted' THEN "
            "m.queued_at END, p.legal_last_name COLLATE NOCASE, p.legal_first_name "
            "COLLATE NOCASE")
    with database.connect() as conn:
        return [_member(r) for r in conn.execute(sql, params)]


def for_pupil(pupil_id: int, *, status: str | None = None) -> list[Member]:
    """The old 'Pupil club history'."""
    sql, params = _MEMBER_SELECT + " WHERE m.pupil_id = ?", [int(pupil_id)]
    if status:
        sql += " AND m.status = ?"
        params.append(status)
    with database.connect() as conn:
        return [_member(r) for r in conn.execute(sql + " ORDER BY m.status = 'Active' DESC, "
                                                 "c.name COLLATE NOCASE", params)]


def _clashes(pupil_id: int, club: Club) -> list[str]:
    """The pupil's other active clubs that meet at the same time."""
    if not (club.day_of_week and club.start_time):
        return []
    s1 = _minutes(club.start_time)
    e1 = _minutes(club.end_time) if club.end_time else s1 + 60
    out = []
    for m in for_pupil(pupil_id, status="Active"):
        if m.club_id == club.club_id:
            continue
        o = get_club(m.club_id)
        if o.is_active and o.day_of_week == club.day_of_week and o.start_time:
            s2 = _minutes(o.start_time)
            e2 = _minutes(o.end_time) if o.end_time else s2 + 60
            if s1 < e2 and s2 < e1:
                out.append(f"{o.name} ({o.when})")
    return out


def join(club_id: int, pupil_id: int, *, actor: Principal, joined_on: Any = None,
         notes: str | None = None, consent: bool = False) -> tuple[Member, list[str]]:
    """Add a pupil (the old 'Add pupil'). Full -> Waitlisted. Returns (member,
    warnings)."""
    c = get_club(club_id)
    _require_runner(actor, c, "clubs.join")
    problems: list[str] = []
    if not c.is_active:
        problems.append(f"{c.name} is inactive - make it active first")
    p = P.get_pupil(int(pupil_id))
    if p is None:
        raise NotFound("No such pupil")
    if p.roll_status != "on_roll":
        problems.append(f"{p.display_name} isn't on roll")
    elif p.year_group not in c.years:
        problems.append(f"{p.display_name} is in Year {p.year_group} - {c.name} is for "
                        f"Year(s) {c.years_label}")
    day = _date(joined_on, "Joined on", problems) or _today()
    if day > _today():
        problems.append("The joining date can't be in the future")
    existing = find_member(c.club_id, p.pupil_id)
    if existing and existing.status in ("Active", "Waitlisted"):
        problems.append(f"{p.display_name} is already {existing.status.lower()} in {c.name}"
                        if existing.status == "Active" else
                        f"{p.display_name} is already on {c.name}'s waiting list")
    if problems:
        raise ValidationError(problems)
    status = "Waitlisted" if c.spaces is not None and c.spaces <= 0 else "Active"
    warnings = []
    if status == "Waitlisted":
        warnings.append(f"{c.name} is full ({c.max_capacity}) - {p.display_name} is on the "
                        "waiting list")
    clash = _clashes(p.pupil_id, c)
    if clash:
        warnings.append(f"{p.display_name} is also in {', '.join(clash)} at the same time")
    if c.consent_required and not consent:
        warnings.append(f"{c.name} needs parental consent - record it before "
                        f"{p.display_name} can be marked present")
    consent_on = day.isoformat() if consent else None
    with database.connect() as conn:
        if existing:
            conn.execute("UPDATE club_members SET status = ?, joined_on = ?, left_on = NULL, "
                         "queued_at = datetime('now'), consent_on = COALESCE(?, consent_on), "
                         "consent_by = CASE WHEN ? IS NULL THEN consent_by ELSE ? END, "
                         "notes = COALESCE(?, notes), updated_at = datetime('now'), "
                         "updated_by = ? WHERE member_id = ?",
                         (status, day.isoformat(), consent_on, consent_on, actor.username,
                          P._clean_text(notes, 500), actor.username, existing.member_id))
            mid = existing.member_id
        else:
            mid = conn.execute(
                "INSERT INTO club_members (club_id, pupil_id, status, joined_on, consent_on, "
                "consent_by, notes, updated_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (c.club_id, p.pupil_id, status, day.isoformat(), consent_on,
                 actor.username if consent else None, P._clean_text(notes, 500),
                 actor.username)).lastrowid
        _audit(conn, "join", actor, club_id=c.club_id, pupil_id=p.pupil_id,
               detail={"status": status, "rejoined": bool(existing)})
    activity_log.record("clubs.join", target=f"club:{c.club_id}", principal=actor,
                        status=status)
    return get_member(mid), warnings


def _promote(club: Club, actor: Principal) -> list[Member]:
    """Move pupils up from the waiting list while there's room."""
    if club.max_capacity is None:
        waiting = list_members(club.club_id, status="Waitlisted")
    else:
        room = club.max_capacity - club.active_members
        waiting = list_members(club.club_id, status="Waitlisted")[:max(room, 0)]
    if not waiting or not club.is_active:
        return []
    with database.connect() as conn:
        for m in waiting:
            conn.execute("UPDATE club_members SET status = 'Active', joined_on = ?, "
                         "updated_at = datetime('now'), updated_by = ? WHERE member_id = ?",
                         (_today().isoformat(), actor.username, m.member_id))
            _audit(conn, "status", actor, club_id=club.club_id, pupil_id=m.pupil_id,
                   detail={"from": "Waitlisted", "to": "Active", "auto": True})
    return [get_member(m.member_id) for m in waiting]


def set_status(member_id: int, status: str, *, actor: Principal,
               note: str | None = None) -> tuple[Member, list[Member]]:
    """The old 'Set status'. Leaving or suspension moves the next pupil up from the
    waiting list. Returns (member, pupils moved up)."""
    m = get_member(member_id)
    c = get_club(m.club_id)
    _require_runner(actor, c, "clubs.status")
    status = str(status or "").strip().title()
    if status not in STATUSES:
        raise ValidationError([f"Status must be one of {', '.join(STATUSES)}"])
    if status == m.status:
        return m, []
    if status == "Active":
        if c.spaces is not None and c.spaces <= 0:
            raise ValidationError([f"{c.name} is at capacity ({c.max_capacity})"])
        p = P.get_pupil(m.pupil_id)
        if p and p.roll_status != "on_roll":
            raise ValidationError([f"{p.display_name} isn't on roll"])
    if status == "Suspended" and not P._clean_text(note, 300):
        raise ValidationError(["Say why the pupil is suspended from the club"])
    with database.connect() as conn:
        conn.execute("UPDATE club_members SET status = ?, left_on = ?, "
                     "queued_at = CASE WHEN ? = 'Waitlisted' THEN datetime('now') ELSE "
                     "queued_at END, notes = COALESCE(?, notes), updated_at = datetime('now'), "
                     "updated_by = ? WHERE member_id = ?",
                     (status, _today().isoformat() if status == "Left" else None, status,
                      P._clean_text(note, 500), actor.username, m.member_id))
        _audit(conn, "status", actor, club_id=c.club_id, pupil_id=m.pupil_id,
               detail={"from": m.status, "to": status})
    activity_log.record("clubs.status", target=f"club:{c.club_id}", principal=actor,
                        status=status)
    moved = _promote(get_club(c.club_id), actor) if m.status == "Active" else []
    return get_member(m.member_id), moved


def record_consent(member_id: int, *, actor: Principal, given: bool = True,
                   on: Any = None) -> Member:
    m = get_member(member_id)
    c = get_club(m.club_id)
    _require_runner(actor, c, "clubs.consent")
    problems: list[str] = []
    day = _date(on, "Consent date", problems) or _today()
    if day > _today():
        problems.append("Consent can't be dated in the future")
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        conn.execute("UPDATE club_members SET consent_on = ?, consent_by = ?, "
                     "updated_at = datetime('now'), updated_by = ? WHERE member_id = ?",
                     (day.isoformat() if given else None, actor.username if given else None,
                      actor.username, m.member_id))
        _audit(conn, "consent", actor, club_id=c.club_id, pupil_id=m.pupil_id,
               detail={"given": given})
    return get_member(m.member_id)


def delete_member(member_id: int, *, actor: Principal) -> Member:
    """The old 'Delete' membership - only if they're on no register."""
    m = get_member(member_id)
    c = get_club(m.club_id)
    _require_runner(actor, c, "clubs.member_delete")
    with database.connect() as conn:
        n = conn.execute("SELECT COUNT(*) FROM club_attendance a JOIN club_meetings g USING "
                         "(meeting_id) WHERE g.club_id = ? AND a.pupil_id = ?",
                         (c.club_id, m.pupil_id)).fetchone()[0]
        if n:
            raise ValidationError([f"{m.pupil_name} is on {n} register(s) - mark them as "
                                   "Left instead"])
        conn.execute("DELETE FROM club_members WHERE member_id = ?", (m.member_id,))
        _audit(conn, "member_delete", actor, club_id=c.club_id, pupil_id=m.pupil_id)
    activity_log.record("clubs.member_delete", target=f"club:{c.club_id}", principal=actor)
    if m.status == "Active":
        _promote(get_club(c.club_id), actor)
    return m


def club_summary(club_id: int) -> dict[str, Any]:
    """The old 'Club summary': members by status, capacity and spaces, plus
    attendance and consent."""
    c = get_club(club_id)
    rows = list_members(c.club_id)
    counts = Counter(m.status for m in rows)
    meetings = [g for g in list_meetings(c.club_id) if g.taken_at and not g.cancelled]
    rate = attendance_rate(c.club_id)
    return {"club": c, "total": len(rows),
            "by_status": {s: counts.get(s, 0) for s in STATUSES},
            "active": counts.get("Active", 0), "capacity": c.max_capacity,
            "spaces": c.spaces, "meetings": len(meetings), "attendance_pct": rate,
            "no_consent": [m for m in rows if c.consent_required and m.status == "Active"
                           and not m.has_consent]}


# ── Meetings and registers ───────────────────────────────────────────

def list_meetings(club_id: int) -> list[Meeting]:
    with database.connect() as conn:
        return [Meeting(r["meeting_id"], r["club_id"], r["date"], bool(r["cancelled"]),
                        r["note"], r["taken_by"], r["taken_at"])
                for r in conn.execute("SELECT * FROM club_meetings WHERE club_id = ? "
                                      "ORDER BY date DESC", (int(club_id),))]


def register(club_id: int, day: Any) -> tuple[list[tuple[Member, str | None]], Meeting | None]:
    """The register for a meeting: (members active that day, their mark if taken)."""
    problems: list[str] = []
    d = _date(day, "Date", problems)
    if d is None:
        raise ValidationError(problems or ["Choose the date"])
    with database.connect() as conn:
        g = conn.execute("SELECT * FROM club_meetings WHERE club_id = ? AND date = ?",
                         (int(club_id), d.isoformat())).fetchone()
        marks = {r[0]: r[1] for r in conn.execute(
            "SELECT pupil_id, mark FROM club_attendance WHERE meeting_id = ?",
            (g["meeting_id"],))} if g else {}
    meeting = Meeting(g["meeting_id"], g["club_id"], g["date"], bool(g["cancelled"]),
                      g["note"], g["taken_by"], g["taken_at"]) if g else None
    rows = [(m, marks.get(m.pupil_id)) for m in list_members(club_id)
            if (m.status == "Active" and m.joined_on <= d.isoformat())
            or m.pupil_id in marks]
    return rows, meeting


def _meeting_id(conn, club_id: int, day: str) -> int:
    r = conn.execute("SELECT meeting_id FROM club_meetings WHERE club_id = ? AND date = ?",
                     (club_id, day)).fetchone()
    if r:
        return r[0]
    return conn.execute("INSERT INTO club_meetings (club_id, date) VALUES (?, ?)",
                        (club_id, day)).lastrowid


def save_register(club_id: int, day: Any, marks: dict[int, str], *, actor: Principal
                  ) -> tuple[Meeting, list[str]]:
    """Take (or correct) a meeting's register: {pupil_id: P / A / E}. Returns
    (meeting, warnings)."""
    c = get_club(club_id)
    _require_runner(actor, c, "clubs.register")
    problems: list[str] = []
    d = _date(day, "Date", problems)
    if d is None:
        raise ValidationError(problems or ["Choose the date"])
    if d > _today():
        problems.append("A register can't be taken for a future date")
    warnings = []
    if c.day_of_week and DAYS.index(c.day_of_week) != d.weekday() and d.weekday() < 6:
        warnings.append(f"{c.name} usually meets on {c.day_of_week} - this is a "
                        f"{d:%a}")
    rows, meeting = register(c.club_id, d)
    if meeting and meeting.cancelled:
        problems.append(f"The {d:%d %b} meeting was cancelled")
    members = {m.pupil_id: m for m, _mark in rows}
    clean: dict[int, str] = {}
    for pid, mark in marks.items():
        mark = str(mark or "").strip().upper()[:1]
        m = members.get(int(pid))
        if m is None:
            problems.append(f"Pupil {pid} isn't a member on {d:%d %b}")
        elif mark not in MARKS:
            problems.append(f"{m.pupil_name}: mark must be P, A or E")
        elif mark == "P" and c.consent_required and not m.has_consent:
            problems.append(f"{m.pupil_name} has no parental consent recorded")
        else:
            clean[m.pupil_id] = mark
    if problems:
        raise ValidationError(problems)
    missing = [m.pupil_name for m in members.values() if m.pupil_id not in clean
               and m.status == "Active"]
    if missing:
        warnings.append(f"{len(missing)} member(s) not marked")
    with database.connect() as conn:
        mid = _meeting_id(conn, c.club_id, d.isoformat())
        conn.executemany("INSERT INTO club_attendance (meeting_id, pupil_id, mark) VALUES "
                         "(?, ?, ?) ON CONFLICT (meeting_id, pupil_id) DO UPDATE SET "
                         "mark = excluded.mark", [(mid, pid, mk) for pid, mk in clean.items()])
        conn.execute("UPDATE club_meetings SET taken_by = ?, taken_at = datetime('now') "
                     "WHERE meeting_id = ?", (actor.username, mid))
        _audit(conn, "register", actor, club_id=c.club_id,
               detail={"date": d.isoformat(), "present": sum(1 for v in clean.values()
                                                             if v == "P"),
                       "marked": len(clean)})
    activity_log.record("clubs.register", target=f"club:{c.club_id}", principal=actor)
    out = register(c.club_id, d)[1]
    assert out is not None
    return out, warnings


def cancel_meeting(club_id: int, day: Any, reason: str, *, actor: Principal) -> Meeting:
    c = get_club(club_id)
    _require_runner(actor, c, "clubs.cancel")
    problems: list[str] = []
    d = _date(day, "Date", problems)
    reason = P._clean_text(reason, 300) or ""
    if not reason:
        problems.append("Say why the meeting is cancelled")
    if d is None and not problems:
        problems.append("Choose the date")
    if problems:
        raise ValidationError(problems)
    assert d is not None
    _rows, meeting = register(c.club_id, d)
    if meeting and meeting.taken_at:
        raise ValidationError([f"The {d:%d %b} register has been taken - it can't be "
                               "cancelled"])
    with database.connect() as conn:
        mid = _meeting_id(conn, c.club_id, d.isoformat())
        conn.execute("UPDATE club_meetings SET cancelled = 1, note = ? WHERE meeting_id = ?",
                     (reason, mid))
        _audit(conn, "cancel", actor, club_id=c.club_id, detail={"date": d.isoformat()})
    activity_log.record("clubs.cancel", target=f"club:{c.club_id}", principal=actor)
    out = register(c.club_id, d)[1]
    assert out is not None
    return out


def attendance_rate(club_id: int, pupil_id: int | None = None) -> float | None:
    """Present as a % of marks (excused not counted)."""
    sql = ("SELECT a.mark, COUNT(*) FROM club_attendance a JOIN club_meetings g USING "
           "(meeting_id) WHERE g.club_id = ? AND g.cancelled = 0")
    params: list[Any] = [int(club_id)]
    if pupil_id is not None:
        sql += " AND a.pupil_id = ?"
        params.append(int(pupil_id))
    with database.connect() as conn:
        counts = dict(conn.execute(sql + " GROUP BY a.mark", params).fetchall())
    counted = counts.get("P", 0) + counts.get("A", 0)
    return round(counts.get("P", 0) * 100 / counted, 1) if counted else None


def member_attendance(club_id: int) -> dict[int, dict[str, Any]]:
    """Per pupil: present / absent / excused counts and %."""
    with database.connect() as conn:
        rows = conn.execute(
            "SELECT a.pupil_id, a.mark, COUNT(*) FROM club_attendance a JOIN club_meetings g "
            "USING (meeting_id) WHERE g.club_id = ? AND g.cancelled = 0 GROUP BY a.pupil_id, "
            "a.mark", (int(club_id),)).fetchall()
    out: dict[int, dict[str, Any]] = defaultdict(lambda: {"P": 0, "A": 0, "E": 0})
    for pid, mark, n in rows:
        out[pid][mark] = n
    for v in out.values():
        counted = v["P"] + v["A"]
        v["pct"] = round(v["P"] * 100 / counted, 1) if counted else None
    return dict(out)


# ── Reports ──────────────────────────────────────────────────────────

def participation(*, year_group: int | None = None) -> dict[str, Any]:
    """Who takes part in at least one active club, overall and for disadvantaged
    groups (FSM, SEN), and who doesn't."""
    pupils = P.list_pupils(year_group=year_group)
    with database.connect() as conn:
        inside = {r[0] for r in conn.execute(
            "SELECT DISTINCT m.pupil_id FROM club_members m JOIN clubs c USING (club_id) "
            "WHERE m.status = 'Active' AND c.is_active = 1")}

    def pct(group: list[P.Pupil]) -> float | None:
        return round(sum(1 for p in group if p.pupil_id in inside) * 100 / len(group), 1) \
            if group else None
    by_year = {y: pct([p for p in pupils if p.year_group == y]) for y in YEARS
               if not year_group or y == int(year_group)}
    return {"pupils": len(pupils), "taking_part": sum(1 for p in pupils
                                                       if p.pupil_id in inside),
            "all_pct": pct(pupils), "fsm_pct": pct([p for p in pupils if p.fsm_eligible]),
            "sen_pct": pct([p for p in pupils if p.sen_status in ("K", "E")]),
            "by_year": by_year,
            "not_in_a_club": [p for p in pupils if p.pupil_id not in inside]}


def my_clubs(actor: Principal) -> list[Club]:
    return [c for c in list_clubs(active_only=True) if _same(actor.username, c.leader_username)]


def timetable(*, year_group: int | None = None) -> dict[str, list[Club]]:
    """Active clubs by meeting day, earliest first (for the clubs timetable)."""
    out: dict[str, list[Club]] = {d: [] for d in DAYS}
    out["Other"] = []
    for c in list_clubs(active_only=True, year_group=year_group):
        out[c.day_of_week or "Other"].append(c)
    for v in out.values():
        v.sort(key=lambda c: (c.start_time or "99", c.name.lower()))
    return {k: v for k, v in out.items() if v}


def notify_families(club_id: int, subject: str, body: str, *, actor: Principal,
                    include_waiting: bool = False):
    """E-mail the families of the club's members (e.g. a cancelled meeting).
    Returns the outbox ``SendResult`` (run delivery next)."""
    c = get_club(club_id)
    _require_runner(actor, c, "clubs.notify")
    ids = [m.pupil_id for m in list_members(c.club_id)
           if m.status == "Active" or (include_waiting and m.status == "Waitlisted")]
    if not ids:
        raise ValidationError([f"{c.name} has no members to write to"])
    from education_system.systems.secondary.modules.communication.domain import email_outbox as E
    result = E.send_message(subject, body, E.Audience(kind="pupils", pupil_ids=ids),
                            actor=actor)
    with database.connect() as conn:
        _audit(conn, "notify", actor, club_id=c.club_id,
               detail={"pupils": len(ids), "message_id": result.message_id})
    return result


def cancellation_text(c: Club, day: _dt.date, reason: str) -> tuple[str, str]:
    return (f"{c.name} cancelled on {day:%A %d %B}",
            "Dear {contact_name},\n\n"
            f"{c.name} will not meet on {day:%A %d %B} ({reason}). "
            "Please make sure {pupil_first_name} knows and has arrangements to get home."
            "\n\nThank you" + (f",\n{c.leader}" if c.leader else "."))


def export_members(club_id: int, path: str | Path, *, actor: Principal) -> int:
    c = get_club(club_id)
    if not actor.is_staff:
        raise PermissionDenied("Only school staff can export club lists.")
    rows = list_members(c.club_id)
    att = member_attendance(c.club_id)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["Admission no", "Pupil", "Year", "Form", "Status", "Joined", "Left",
                    "Consent", "Present", "Absent", "Excused", "Attendance %", "Notes"])
        for m in rows:
            a = att.get(m.pupil_id, {"P": 0, "A": 0, "E": 0, "pct": None})
            w.writerow([_safe(x) for x in (
                m.admission_no, m.pupil_name, m.year_group, m.form_group, m.status,
                m.joined_on, m.left_on, m.consent_on or ("needed" if c.consent_required
                                                           else ""),
                a["P"], a["A"], a["E"], a["pct"], m.notes)])
    activity_log.record("clubs.export", target=f"club:{c.club_id}", principal=actor,
                        rows=len(rows))
    return len(rows)
