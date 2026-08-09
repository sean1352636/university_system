"""Attendance cohorts for the Sixth Form System.

Sibling to :mod:`attendance`. "Persistent absence" is the single most
used phrase in attendance work and the one this system has had no way of
saying. It has a definition — attendance at or below 90% — and the
learners who meet it are a *cohort*: a group that is tracked, reported
on, and moved in and out of over the year.

What this module adds beyond a filtered list:

* **Membership over time.** A learner enters and leaves a cohort, and
  those transitions are the interesting events. A college that can only
  see today's list cannot tell whether it is getting better.
* **Direction.** :class:`CohortMember` carries the previous period's
  figure alongside the current one, so the list can be read as
  improving, holding or falling. A learner at 88% and rising needs a
  different conversation from one at 88% and falling, and they look
  identical in a sorted list of percentages.
* **Sessions to recover.** :func:`sessions_to_reach` answers the
  question every learner actually asks — how many lessons do I have to
  attend to get back over the line — and sometimes the honest answer is
  that this year it is arithmetically out of reach, which is far better
  said in October than discovered in June.

Bands come from :mod:`attendance_thresholds`, so a college that defines
persistent absence differently gets its own definition everywhere.
"""

from __future__ import annotations

import datetime as _dt
import logging
import math
import sqlite3
from dataclasses import dataclass, field
from typing import Any

from education_system.systems.sixth_form.domain.academics.attendance import (
    attendance as core,
    attendance_thresholds as thresholds,
)
from education_system import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_ATTENDANCE_DB

ValidationError = core.ValidationError


# ── Vocabularies ────────────────────────────────────────────────────

SEVERE: str = "Severe absence"
PERSISTENT: str = "Persistent absence"
AT_RISK: str = "At risk"
ON_TARGET: str = "On target"
BANDS: tuple[str, ...] = (SEVERE, PERSISTENT, AT_RISK, ON_TARGET)
_BAND_RANK: dict[str, int] = {b: i for i, b in enumerate(BANDS)}

# Bands that are a cohort somebody works with.
TRACKED_BANDS: frozenset[str] = frozenset({SEVERE, PERSISTENT, AT_RISK})

IMPROVING: str = "Improving"
HOLDING: str = "Holding"
FALLING: str = "Falling"
NEW: str = "New"
DIRECTIONS: tuple[str, ...] = (IMPROVING, HOLDING, FALLING, NEW)

# Percentage points of movement before it counts as a direction rather
# than noise.
MOVEMENT_THRESHOLD: float = 1.0

# The window a cohort is calculated over by default: half a term.
DEFAULT_WINDOW_DAYS: int = 42

_SCHEMA = """
CREATE TABLE IF NOT EXISTS attendance_cohort_snapshots (
    snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
    taken_on    TEXT NOT NULL,
    window_from TEXT NOT NULL,
    window_to   TEXT NOT NULL,
    label       TEXT,
    taken_by    TEXT,
    created_at  TEXT DEFAULT (datetime('now')),
    UNIQUE(taken_on, label)
);

CREATE TABLE IF NOT EXISTS attendance_cohort_members (
    member_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id INTEGER NOT NULL,
    student_id  TEXT NOT NULL,
    band        TEXT NOT NULL,
    percentage  REAL,
    previous_pct REAL,
    year_group  INTEGER,
    UNIQUE(snapshot_id, student_id),
    FOREIGN KEY (snapshot_id)
        REFERENCES attendance_cohort_snapshots(snapshot_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_att_cohort_member_student
    ON attendance_cohort_members(student_id);
CREATE INDEX IF NOT EXISTS idx_att_cohort_member_band
    ON attendance_cohort_members(band);
"""


# ── Shapes ──────────────────────────────────────────────────────────

@dataclass
class CohortMember:
    """One learner's standing, and which way they are moving."""

    student_id: str
    percentage: float
    band: str
    previous_pct: float | None = None
    sessions: int = 0
    attended: int = 0
    unauthorised: int = 0
    student_name: str | None = None
    year_group: int | None = None

    @property
    def change(self) -> float | None:
        if self.previous_pct is None:
            return None
        return round(self.percentage - self.previous_pct, 1)

    @property
    def direction(self) -> str:
        change = self.change
        if change is None:
            return NEW
        if change >= MOVEMENT_THRESHOLD:
            return IMPROVING
        if change <= -MOVEMENT_THRESHOLD:
            return FALLING
        return HOLDING

    @property
    def arrow(self) -> str:
        return {IMPROVING: "↑", FALLING: "↓", HOLDING: "→", NEW: "·"}[
            self.direction]

    @property
    def label(self) -> str:
        who = self.student_name or self.student_id
        change = "" if self.change is None else f" ({self.change:+.1f})"
        return f"{who} {self.percentage:.1f}%{change} {self.arrow}"


@dataclass
class Cohort:
    """One band, as at one window."""

    band: str
    window_from: str
    window_to: str
    members: list[CohortMember] = field(default_factory=list)

    @property
    def size(self) -> int:
        return len(self.members)

    @property
    def improving(self) -> int:
        return sum(1 for m in self.members if m.direction == IMPROVING)

    @property
    def falling(self) -> int:
        return sum(1 for m in self.members if m.direction == FALLING)

    @property
    def average(self) -> float | None:
        if not self.members:
            return None
        return round(sum(m.percentage for m in self.members)
                     / len(self.members), 1)

    @property
    def label(self) -> str:
        return (f"{self.band}: {self.size} learner(s), "
                f"{self.improving} improving, {self.falling} falling")


@dataclass
class Movement:
    """A learner who changed band between two snapshots."""

    student_id: str
    from_band: str | None
    to_band: str | None
    from_pct: float | None
    to_pct: float | None

    @property
    def improved(self) -> bool:
        if self.from_band is None or self.to_band is None:
            return False
        return _BAND_RANK[self.to_band] > _BAND_RANK[self.from_band]

    @property
    def label(self) -> str:
        return (f"{self.student_id}: {self.from_band or '—'} → "
                f"{self.to_band or '—'}")


@dataclass
class Recovery:
    """What it would take to get back over a line."""

    student_id: str
    current_pct: float
    target_pct: float
    attended: int
    sessions: int
    sessions_needed: int | None
    sessions_remaining: int | None

    @property
    def achievable(self) -> bool | None:
        if self.sessions_needed is None:
            return None
        if self.sessions_remaining is None:
            return True
        return self.sessions_needed <= self.sessions_remaining

    @property
    def label(self) -> str:
        if self.sessions_needed is None:
            return f"{self.student_id} is already at or above the target"
        if self.achievable is False:
            return (f"{self.student_id} cannot reach {self.target_pct:g}% "
                    f"this year — {self.sessions_needed} consecutive "
                    f"session(s) needed, {self.sessions_remaining} remain")
        return (f"{self.student_id} needs {self.sessions_needed} consecutive "
                f"session(s) to reach {self.target_pct:g}%")


# ── DB plumbing ─────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    paths.ensure_sixth_form_directories()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


_DB_READY: bool = False


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    thresholds.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        conn.commit()
    logger.debug("Cohort schema ready at %s", DB_PATH)
    _DB_READY = True


# ── Banding ─────────────────────────────────────────────────────────

def band_for(percentage: float | None, *,
             year_group: int | None = None) -> str | None:
    """Which band a figure falls in.

    Ordered most serious first: a learner at 45% is severely absent, not
    merely persistently absent, and should be counted once.
    """
    if percentage is None:
        return None
    if thresholds.is_breached(thresholds.SEVERE_ABSENCE, percentage,
                              year_group=year_group):
        return SEVERE
    if thresholds.is_breached(thresholds.PERSISTENT_ABSENCE, percentage,
                              year_group=year_group):
        return PERSISTENT
    if thresholds.is_breached(thresholds.TARGET_ATTENDANCE, percentage,
                              year_group=year_group):
        return AT_RISK
    return ON_TARGET


def _year_group_of(student_id: str) -> int | None:
    try:
        from education_system.systems.sixth_form.domain.learners.students import (
            students as _students,
        )
        student = _students.get_student(student_id)
        year = getattr(student, "year_group", None) if student else None
        return int(year) if year not in (None, "") else None
    except Exception:                       # pragma: no cover - defensive
        return None


def member_for(
    student_id: str,
    *,
    date_from: str,
    date_to: str,
    compare_previous: bool = True,
) -> CohortMember | None:
    """One learner's standing over a window, with the previous one for
    comparison."""
    summary = core.summary_for_student(student_id, date_from=date_from,
                                       date_to=date_to)
    if summary.total == 0 or summary.percentage is None:
        return None
    year_group = _year_group_of(student_id)

    previous_pct = None
    if compare_previous:
        span = (_dt.date.fromisoformat(date_to)
                - _dt.date.fromisoformat(date_from)).days or 1
        previous_to = (_dt.date.fromisoformat(date_from)
                       - _dt.timedelta(days=1)).isoformat()
        previous_from = (_dt.date.fromisoformat(previous_to)
                         - _dt.timedelta(days=span)).isoformat()
        previous = core.summary_for_student(student_id,
                                            date_from=previous_from,
                                            date_to=previous_to)
        if previous.total > 0:
            previous_pct = previous.percentage

    return CohortMember(
        student_id=student_id, percentage=summary.percentage,
        band=band_for(summary.percentage, year_group=year_group) or ON_TARGET,
        previous_pct=previous_pct, sessions=summary.total,
        attended=summary.attending, unauthorised=summary.absent,
        year_group=year_group)


def cohort(
    band: str,
    *,
    window_days: int = DEFAULT_WINDOW_DAYS,
    date_to: str | None = None,
    group_id: int | None = None,
    year_group: int | None = None,
    with_names: bool = True,
) -> Cohort:
    """Everybody currently in one band, worst first."""
    init_db()
    if band not in BANDS:
        raise ValidationError(f"Band must be one of: {', '.join(BANDS)}")
    date_to = core._validate_date(date_to or _dt.date.today().isoformat())
    date_from = (_dt.date.fromisoformat(date_to)
                 - _dt.timedelta(days=max(1, window_days))).isoformat()

    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    wanted: set[str] | None = None
    if group_id is not None:
        from education_system.systems.sixth_form.domain.academics.class_groups import (  # noqa: E501
            class_groups as _cg,
        )
        wanted = set(_cg.list_members(group_id))

    out = Cohort(band=band, window_from=date_from, window_to=date_to)
    index = {s.student_id: s for s in _students.list_students()}
    for student_id, student in sorted(index.items()):
        if wanted is not None and student_id not in wanted:
            continue
        if getattr(student, "status", "Active") not in ("Active", None):
            continue
        member = member_for(student_id, date_from=date_from, date_to=date_to)
        if member is None or member.band != band:
            continue
        if year_group is not None and member.year_group != year_group:
            continue
        if with_names:
            member.student_name = student.full_name
        out.members.append(member)
    out.members.sort(key=lambda m: m.percentage)
    return out


def persistent_absentees(**kwargs: Any) -> Cohort:
    """The 90% cohort — the one that gets reported to governors."""
    return cohort(PERSISTENT, **kwargs)


def severe_absentees(**kwargs: Any) -> Cohort:
    """The 50% cohort — a safeguarding matter, not an attendance one."""
    return cohort(SEVERE, **kwargs)


def all_bands(*, window_days: int = DEFAULT_WINDOW_DAYS,
              date_to: str | None = None,
              group_id: int | None = None) -> dict[str, Cohort]:
    """Every band at once, for a dashboard."""
    return {band: cohort(band, window_days=window_days, date_to=date_to,
                         group_id=group_id) for band in BANDS}


def band_counts(*, window_days: int = DEFAULT_WINDOW_DAYS,
                date_to: str | None = None) -> dict[str, int]:
    """Just the sizes."""
    return {band: c.size
            for band, c in all_bands(window_days=window_days,
                                     date_to=date_to).items()}


# ── Snapshots and movement ──────────────────────────────────────────

def take_snapshot(
    *,
    window_days: int = DEFAULT_WINDOW_DAYS,
    date_to: str | None = None,
    label: str | None = None,
    taken_by: str | None = None,
) -> int:
    """Freeze today's banding so movement can be measured later.

    Taken at half term and reported on at the next one. Without
    snapshots, "persistent absence is down" is an assertion; with them
    it is a subtraction.
    """
    init_db()
    date_to = core._validate_date(date_to or _dt.date.today().isoformat())
    date_from = (_dt.date.fromisoformat(date_to)
                 - _dt.timedelta(days=max(1, window_days))).isoformat()
    taken_on = _dt.date.today().isoformat()

    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO attendance_cohort_snapshots
                   (taken_on, window_from, window_to, label, taken_by)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(taken_on, label) DO UPDATE SET
                   window_from = excluded.window_from,
                   window_to = excluded.window_to""",
            (taken_on, date_from, date_to, label, (taken_by or "").strip()
             or None))
        conn.commit()
        snapshot_id = int(cur.lastrowid or 0)

    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    rows: list[tuple[Any, ...]] = []
    for student in _students.list_students():
        if getattr(student, "status", "Active") not in ("Active", None):
            continue
        member = member_for(student.student_id, date_from=date_from,
                            date_to=date_to)
        if member is None:
            continue
        rows.append((snapshot_id, member.student_id, member.band,
                     member.percentage, member.previous_pct,
                     member.year_group))
    with _connect() as conn:
        conn.executemany(
            """INSERT INTO attendance_cohort_members
                   (snapshot_id, student_id, band, percentage, previous_pct,
                    year_group)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(snapshot_id, student_id) DO UPDATE SET
                   band = excluded.band, percentage = excluded.percentage""",
            rows)
        conn.commit()
    logger.info("Cohort snapshot #%d: %d learner(s)", snapshot_id, len(rows))
    return snapshot_id


def list_snapshots(*, limit: int = 20) -> list[dict[str, Any]]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM attendance_cohort_snapshots "
            "ORDER BY snapshot_id DESC LIMIT ?", (max(1, limit),)).fetchall()
    return [dict(r) for r in rows]


def snapshot_bands(snapshot_id: int) -> dict[str, int]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT band, COUNT(*) AS n FROM attendance_cohort_members "
            "WHERE snapshot_id = ? GROUP BY band", (snapshot_id,)).fetchall()
    return {r["band"]: r["n"] for r in rows}


def movement(from_snapshot: int, to_snapshot: int) -> list[Movement]:
    """Who changed band between two snapshots.

    The report that answers "is what we are doing working". Learners who
    improved out of a cohort and learners who fell into one, by name.
    """
    init_db()
    with _connect() as conn:
        before = {r["student_id"]: r for r in conn.execute(
            "SELECT * FROM attendance_cohort_members WHERE snapshot_id = ?",
            (from_snapshot,)).fetchall()}
        after = {r["student_id"]: r for r in conn.execute(
            "SELECT * FROM attendance_cohort_members WHERE snapshot_id = ?",
            (to_snapshot,)).fetchall()}

    out: list[Movement] = []
    for student_id in sorted(set(before) | set(after)):
        old = before.get(student_id)
        new = after.get(student_id)
        old_band = old["band"] if old else None
        new_band = new["band"] if new else None
        if old_band == new_band:
            continue
        out.append(Movement(student_id=student_id, from_band=old_band,
                            to_band=new_band,
                            from_pct=old["percentage"] if old else None,
                            to_pct=new["percentage"] if new else None))
    return out


def movement_summary(from_snapshot: int, to_snapshot: int) -> dict[str, Any]:
    """The headline: how many in, how many out, net."""
    moves = movement(from_snapshot, to_snapshot)
    improved = sum(1 for m in moves if m.improved)
    before = snapshot_bands(from_snapshot)
    after = snapshot_bands(to_snapshot)
    return {
        "moved": len(moves),
        "improved": improved,
        "worsened": len(moves) - improved,
        "persistent_before": before.get(PERSISTENT, 0) + before.get(SEVERE, 0),
        "persistent_after": after.get(PERSISTENT, 0) + after.get(SEVERE, 0),
        "net_change": ((after.get(PERSISTENT, 0) + after.get(SEVERE, 0))
                       - (before.get(PERSISTENT, 0) + before.get(SEVERE, 0))),
    }


# ── Recovery arithmetic ─────────────────────────────────────────────

def sessions_to_reach(
    student_id: str,
    *,
    target_pct: float | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    sessions_remaining: int | None = None,
) -> Recovery:
    """How many consecutive sessions would get a learner over a line.

    Straightforward algebra with an uncomfortable implication: past a
    certain point in the year the answer exceeds the sessions left, and
    the target is arithmetically unreachable. Saying so in October is
    honest and leaves time to set a target that is not; discovering it in
    June helps nobody.
    """
    init_db()
    target = target_pct if target_pct is not None else thresholds.value_of(
        thresholds.PERSISTENT_ABSENCE, default=90.0)
    assert target is not None
    date_to = core._validate_date(date_to or _dt.date.today().isoformat())
    date_from = core._validate_date(
        date_from or (_dt.date.fromisoformat(date_to)
                      - _dt.timedelta(days=DEFAULT_WINDOW_DAYS)).isoformat())
    summary = core.summary_for_student(student_id, date_from=date_from,
                                       date_to=date_to)
    attended, total = summary.attending, summary.total
    current = summary.percentage if summary.percentage is not None else 0.0

    if total == 0 or current >= target:
        return Recovery(student_id=student_id, current_pct=current,
                        target_pct=target, attended=attended, sessions=total,
                        sessions_needed=None,
                        sessions_remaining=sessions_remaining)

    # (attended + n) / (total + n) >= target/100
    ratio = target / 100.0
    if ratio >= 1.0:
        needed = None
    else:
        needed = math.ceil((ratio * total - attended) / (1 - ratio))
        needed = max(0, needed)
    return Recovery(student_id=student_id, current_pct=current,
                    target_pct=target, attended=attended, sessions=total,
                    sessions_needed=needed,
                    sessions_remaining=sessions_remaining)


def unreachable_targets(
    *,
    sessions_remaining: int,
    target_pct: float | None = None,
    window_days: int = DEFAULT_WINDOW_DAYS,
) -> list[Recovery]:
    """Learners for whom the target is already out of reach this year.

    Not a list to give up on — a list to set an honest target for. A
    learner told to reach 90% when it is arithmetically impossible stops
    believing any target the college sets.
    """
    init_db()
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    out: list[Recovery] = []
    for student in _students.list_students():
        if getattr(student, "status", "Active") not in ("Active", None):
            continue
        recovery = sessions_to_reach(
            student.student_id, target_pct=target_pct,
            sessions_remaining=sessions_remaining)
        if recovery.achievable is False:
            out.append(recovery)
    out.sort(key=lambda r: r.current_pct)
    return out


def headroom(student_id: str, *, target_pct: float | None = None,
             sessions_remaining: int = 0) -> int:
    """How many more sessions a learner can miss and stay above a line.

    The other side of the same arithmetic, and the version worth putting
    in front of a learner who is currently fine.
    """
    target = target_pct if target_pct is not None else thresholds.value_of(
        thresholds.TARGET_ATTENDANCE, default=95.0)
    assert target is not None
    date_to = _dt.date.today()
    date_from = date_to - _dt.timedelta(days=DEFAULT_WINDOW_DAYS)
    summary = core.summary_for_student(student_id,
                                       date_from=date_from.isoformat(),
                                       date_to=date_to.isoformat())
    attended = summary.attending
    total = summary.total + max(0, sessions_remaining)
    attended_if_perfect = attended + max(0, sessions_remaining)
    ratio = target / 100.0
    # attended_if_perfect - m >= ratio * total
    allowance = math.floor(attended_if_perfect - ratio * total)
    return max(0, int(allowance))
