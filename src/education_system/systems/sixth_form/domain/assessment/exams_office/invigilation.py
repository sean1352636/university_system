"""Invigilator pool and rota.

Invigilators are allocated to exam sittings (one paper in one room at
one time, from :mod:`attendance_exams`). For each sitting the rota
checks the JCQ ratio, the readers / scribes needed by candidates with
access arrangements, and that nobody is in two rooms at once.

The sitting's old free-text ``invigilator`` column is kept in step with
the allocations (lead first) so the existing register screens still
show who is in the room.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any

from education_system.systems.sixth_form.domain.assessment.exams_office import store
from education_system.systems.sixth_form.domain.assessment.exams_office.store import (
    ValidationError,
)

logger = logging.getLogger(__name__)

# JCQ Instructions for Conducting Examinations: one invigilator for
# every 30 candidates, plus one for each further 30 or part of 30.
CANDIDATES_PER_INVIGILATOR: int = 30

ROLES: tuple[str, ...] = ("Lead", "Invigilator", "Reader", "Scribe",
                          "Reader/Scribe", "Prompter", "Practical assistant")
_FACILITATOR_ROLES = {"Reader", "Scribe", "Reader/Scribe"}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS exams_invigilators (
    invigilator_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name           TEXT NOT NULL,
    staff_id       TEXT,
    email          TEXT,
    phone          TEXT,
    trained_on     TEXT,
    can_read_scribe INTEGER NOT NULL DEFAULT 0,
    is_active      INTEGER NOT NULL DEFAULT 1,
    notes          TEXT,
    created_at     TEXT DEFAULT (datetime('now')),
    UNIQUE(name)
);

CREATE TABLE IF NOT EXISTS exams_invigilation_allocations (
    allocation_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    sitting_id     INTEGER NOT NULL,
    invigilator_id INTEGER NOT NULL,
    role           TEXT NOT NULL DEFAULT 'Invigilator',
    student_id     TEXT,
    notes          TEXT,
    allocated_by   TEXT,
    allocated_at   TEXT DEFAULT (datetime('now')),
    UNIQUE(sitting_id, invigilator_id),
    FOREIGN KEY (sitting_id) REFERENCES attendance_exam_sittings(sitting_id)
        ON DELETE CASCADE,
    FOREIGN KEY (invigilator_id) REFERENCES exams_invigilators(invigilator_id)
        ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_exams_invig_alloc_inv
    ON exams_invigilation_allocations(invigilator_id);
"""


def _attendance_init() -> None:
    from education_system.systems.sixth_form.domain.academics.attendance import (
        attendance_exams as _exams,
    )
    _exams.init_db()


def init_db() -> None:
    store.ensure("invigilation", _SCHEMA, after=(_attendance_init,))


def required_invigilators(candidates: int) -> int:
    """JCQ minimum for a room of *candidates*."""
    if candidates <= 0:
        return 0
    return math.ceil(candidates / CANDIDATES_PER_INVIGILATOR)


# ── Shapes ──────────────────────────────────────────────────────────

@dataclass
class Invigilator:
    invigilator_id: int
    name: str
    staff_id: str | None
    email: str | None
    phone: str | None
    trained_on: str | None
    can_read_scribe: bool
    is_active: bool
    notes: str | None


@dataclass
class Allocation:
    allocation_id: int
    sitting_id: int
    invigilator_id: int
    invigilator_name: str
    role: str
    student_id: str | None
    notes: str | None


@dataclass
class SittingCover:
    """Ratio check for one sitting."""
    sitting: Any
    candidates: int
    required: int
    allocated: int
    facilitators_needed: int
    facilitators_allocated: int
    allocations: list[Allocation] = field(default_factory=list)

    @property
    def short(self) -> int:
        return max(0, self.required - self.allocated)

    @property
    def facilitators_short(self) -> int:
        return max(0, self.facilitators_needed - self.facilitators_allocated)

    @property
    def ok(self) -> bool:
        return self.short == 0 and self.facilitators_short == 0


@dataclass
class Conflict:
    invigilator_name: str
    first: Any
    second: Any


def _inv(r) -> Invigilator:
    return Invigilator(
        invigilator_id=r["invigilator_id"], name=r["name"], staff_id=r["staff_id"],
        email=r["email"], phone=r["phone"], trained_on=r["trained_on"],
        can_read_scribe=bool(r["can_read_scribe"]), is_active=bool(r["is_active"]),
        notes=r["notes"])


# ── Pool ────────────────────────────────────────────────────────────

def save_invigilator(data: dict[str, Any], *,
                     invigilator_id: int | None = None) -> Invigilator:
    init_db()
    name = store.text(data.get("name"), "Name", limit=120, required=True)
    staff_id = store.text(data.get("staff_id"), "Staff ID", limit=40)
    if staff_id:
        from education_system.systems.sixth_form.domain.staff import staff as _staff
        if _staff.get_staff(staff_id) is None:
            raise ValidationError(f"No staff member {staff_id}")
    vals = (name, staff_id, store.text(data.get("email"), "Email", limit=200),
            store.text(data.get("phone"), "Phone", limit=40),
            store.date(data.get("trained_on"), "Trained on"),
            store.flag(data.get("can_read_scribe")),
            store.flag(data.get("is_active", True)),
            store.text(data.get("notes"), "Notes", limit=500))
    try:
        with store.connect() as conn:
            if invigilator_id is None:
                cur = conn.execute(
                    """INSERT INTO exams_invigilators
                           (name, staff_id, email, phone, trained_on,
                            can_read_scribe, is_active, notes)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""", vals)
                invigilator_id = int(cur.lastrowid)
            else:
                conn.execute(
                    """UPDATE exams_invigilators SET name = ?, staff_id = ?,
                           email = ?, phone = ?, trained_on = ?,
                           can_read_scribe = ?, is_active = ?, notes = ?
                       WHERE invigilator_id = ?""", (*vals, invigilator_id))
            conn.commit()
    except store.IntegrityError as e:
        raise ValidationError(f"An invigilator called {name} already exists") from e
    out = get_invigilator(invigilator_id)
    assert out is not None
    return out


def add_from_staff(staff_id: str) -> Invigilator:
    """Put a staff member into the pool using their directory details."""
    from education_system.systems.sixth_form.domain.staff import staff as _staff
    s = _staff.get_staff(staff_id)
    if s is None:
        raise ValidationError(f"No staff member {staff_id}")
    existing = next((i for i in list_invigilators(active_only=False)
                     if i.staff_id == s.staff_id), None)
    if existing:
        return existing
    return save_invigilator({
        "name": f"{s.first_name} {s.last_name}".strip(), "staff_id": s.staff_id,
        "email": s.email, "phone": s.work_phone})


def get_invigilator(invigilator_id: int) -> Invigilator | None:
    init_db()
    with store.connect() as conn:
        r = conn.execute("SELECT * FROM exams_invigilators WHERE invigilator_id = ?",
                         (invigilator_id,)).fetchone()
    return _inv(r) if r else None


def list_invigilators(*, active_only: bool = True) -> list[Invigilator]:
    init_db()
    sql = "SELECT * FROM exams_invigilators"
    if active_only:
        sql += " WHERE is_active = 1"
    with store.connect() as conn:
        return [_inv(r) for r in conn.execute(sql + " ORDER BY name")]


def delete_invigilator(invigilator_id: int) -> bool:
    init_db()
    with store.connect() as conn:
        cur = conn.execute("DELETE FROM exams_invigilators WHERE invigilator_id = ?",
                           (invigilator_id,))
        conn.commit()
    return bool(cur.rowcount)


# ── Allocations ─────────────────────────────────────────────────────

def _sitting_window(sitting) -> tuple[str, str, str]:
    """(date, start, end) including the longest extra-time finish."""
    end = (getattr(sitting, "extended_end_time", None) or sitting.end_time
           or store.add_minutes(sitting.start_time, 60))
    return sitting.date, sitting.start_time, end


def _overlaps(a, b) -> bool:
    da, sa, ea = _sitting_window(a)
    db, sb, eb = _sitting_window(b)
    return da == db and sa < eb and sb < ea


def list_allocations(*, sitting_id: int | None = None,
                     invigilator_id: int | None = None) -> list[Allocation]:
    init_db()
    clauses, args = [], []
    if sitting_id is not None:
        clauses.append("a.sitting_id = ?")
        args.append(int(sitting_id))
    if invigilator_id is not None:
        clauses.append("a.invigilator_id = ?")
        args.append(int(invigilator_id))
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with store.connect() as conn:
        rows = conn.execute(
            f"""SELECT a.*, i.name AS invigilator_name
                  FROM exams_invigilation_allocations a
                  JOIN exams_invigilators i ON i.invigilator_id = a.invigilator_id
                {where}
                ORDER BY a.sitting_id,
                         CASE a.role WHEN 'Lead' THEN 0 ELSE 1 END, i.name""",
            args).fetchall()
    return [Allocation(r["allocation_id"], r["sitting_id"], r["invigilator_id"],
                       r["invigilator_name"], r["role"], r["student_id"], r["notes"])
            for r in rows]


def _sync_sitting_text(sitting_id: int) -> None:
    names = [a.invigilator_name for a in list_allocations(sitting_id=sitting_id)]
    with store.connect() as conn:
        conn.execute("UPDATE attendance_exam_sittings SET invigilator = ? "
                     "WHERE sitting_id = ?", (", ".join(names) or None, sitting_id))
        conn.commit()


def allocate(sitting_id: int, invigilator_id: int, *, role: str = "Invigilator",
             student_id: str | None = None, notes: str | None = None,
             allow_conflict: bool = False) -> Allocation:
    """Put an invigilator in a sitting's room. Refuses a double booking."""
    init_db()
    from education_system.systems.sixth_form.domain.academics.attendance import (
        attendance_exams as _exams,
    )
    sitting = _exams.get_sitting(int(sitting_id))
    if sitting is None:
        raise ValidationError(f"No sitting #{sitting_id}")
    inv = get_invigilator(int(invigilator_id))
    if inv is None:
        raise ValidationError(f"No invigilator #{invigilator_id}")
    if not inv.is_active:
        raise ValidationError(f"{inv.name} is not active in the pool")
    role = store.choice(role, "Role", ROLES, default="Invigilator")
    if role in _FACILITATOR_ROLES and not inv.can_read_scribe:
        raise ValidationError(f"{inv.name} is not marked as a trained reader/scribe")
    sid = store.student(student_id) if student_id else None
    if not allow_conflict:
        for a in list_allocations(invigilator_id=inv.invigilator_id):
            if a.sitting_id == sitting.sitting_id:
                continue
            other = _exams.get_sitting(a.sitting_id)
            if other and _overlaps(sitting, other) and (other.room or "") != (sitting.room or ""):
                raise ValidationError(
                    f"{inv.name} is already in {other.room or 'another room'} for "
                    f"{other.label} at that time")
    with store.connect() as conn:
        conn.execute(
            """INSERT INTO exams_invigilation_allocations
                   (sitting_id, invigilator_id, role, student_id, notes, allocated_by)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(sitting_id, invigilator_id) DO UPDATE SET
                   role = excluded.role, student_id = excluded.student_id,
                   notes = excluded.notes""",
            (sitting.sitting_id, inv.invigilator_id, role, sid,
             store.text(notes, "Notes", limit=500), store.actor()))
        conn.commit()
    _sync_sitting_text(sitting.sitting_id)
    logger.info("Allocated %s to sitting #%d as %s", inv.name, sitting.sitting_id, role)
    return next(a for a in list_allocations(sitting_id=sitting.sitting_id)
                if a.invigilator_id == inv.invigilator_id)


def unallocate(allocation_id: int) -> bool:
    init_db()
    with store.connect() as conn:
        r = conn.execute("SELECT sitting_id FROM exams_invigilation_allocations "
                         "WHERE allocation_id = ?", (allocation_id,)).fetchone()
        cur = conn.execute("DELETE FROM exams_invigilation_allocations "
                           "WHERE allocation_id = ?", (allocation_id,))
        conn.commit()
    if r:
        _sync_sitting_text(r["sitting_id"])
    return bool(cur.rowcount)


# ── Checks ──────────────────────────────────────────────────────────

def cover(sitting_id: int) -> SittingCover:
    from education_system.systems.sixth_form.domain.academics.attendance import (
        attendance_exams as _exams,
    )
    sitting = _exams.get_sitting(int(sitting_id))
    if sitting is None:
        raise ValidationError(f"No sitting #{sitting_id}")
    cands = [c for c in _exams.list_candidates(sitting.sitting_id)
             if c.state != _exams.WITHDRAWN]
    allocs = list_allocations(sitting_id=sitting.sitting_id)
    general = [a for a in allocs if a.role not in _FACILITATOR_ROLES]
    facilitators = [a for a in allocs if a.role in _FACILITATOR_ROLES]
    needed = sum(1 for c in cands if getattr(c, "reader", 0) or getattr(c, "scribe", 0))
    return SittingCover(sitting, len(cands), required_invigilators(len(cands)),
                        len(general), needed, len(facilitators), allocs)


def cover_report(*, date_from: str | None = None,
                 date_to: str | None = None) -> list[SittingCover]:
    from education_system.systems.sixth_form.domain.academics.attendance import (
        attendance_exams as _exams,
    )
    init_db()
    return [cover(s.sitting_id)
            for s in _exams.list_sittings(date_from=date_from, date_to=date_to)]


def conflicts(*, date_from: str | None = None,
              date_to: str | None = None) -> list[Conflict]:
    """Invigilators booked into two rooms whose sittings overlap."""
    from education_system.systems.sixth_form.domain.academics.attendance import (
        attendance_exams as _exams,
    )
    init_db()
    sittings = {s.sitting_id: s for s in _exams.list_sittings(
        date_from=date_from, date_to=date_to)}
    by_inv: dict[int, list[Allocation]] = {}
    for a in list_allocations():
        if a.sitting_id in sittings:
            by_inv.setdefault(a.invigilator_id, []).append(a)
    out: list[Conflict] = []
    for allocs in by_inv.values():
        for i, a in enumerate(allocs):
            for b in allocs[i + 1:]:
                sa, sb = sittings[a.sitting_id], sittings[b.sitting_id]
                if _overlaps(sa, sb) and (sa.room or "") != (sb.room or ""):
                    out.append(Conflict(a.invigilator_name, sa, sb))
    return out


def printable_rota(*, date_from: str | None = None,
                   date_to: str | None = None) -> str:
    """The rota as plain text, one block per day, ready to print."""
    from education_system.systems.sixth_form.domain.academics.attendance import (
        attendance_exams as _exams,
    )
    init_db()
    sittings = _exams.list_sittings(date_from=date_from, date_to=date_to)
    lines = ["INVIGILATION ROTA",
             f"{date_from or 'start'} to {date_to or 'end'}  "
             f"(ratio 1 per {CANDIDATES_PER_INVIGILATOR} candidates)", ""]
    day = None
    for s in sittings:
        if s.date != day:
            day = s.date
            lines += ["", "=" * 72, day, "=" * 72]
        c = cover(s.sitting_id)
        _, start, end = _sitting_window(s)
        gaps = []
        if c.short:
            gaps.append(f"{c.short} invigilator(s)")
        if c.facilitators_short:
            gaps.append(f"{c.facilitators_short} reader/scribe")
        status = "OK" if c.ok else "SHORT " + " + ".join(gaps)
        lines.append(f"{start}-{end}  {s.room or '(no room)':<14} {s.paper_code:<12} "
                     f"{(s.paper_title or '')[:28]:<28} cands {c.candidates:>3}  "
                     f"need {c.required}  [{status}]")
        for a in c.allocations:
            extra = f" for {a.student_id}" if a.student_id else ""
            lines.append(f"      {a.role:<14} {a.invigilator_name}{extra}")
        if not c.allocations:
            lines.append("      (nobody allocated)")
    clash = conflicts(date_from=date_from, date_to=date_to)
    if clash:
        lines += ["", "CONFLICTS"]
        for k in clash:
            lines.append(f"  {k.invigilator_name}: {k.first.label} and {k.second.label}")
    return "\n".join(lines) + "\n"
