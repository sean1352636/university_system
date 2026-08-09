"""Domain layer for Live Ratio Alerts (Nursery System).

The active warning layer over the Staff : Child Ratios board. ``ratios.py``
answers "does the headcount in each room meet its ratio right now?" from static
room assignments; this module asks the harder operational question — **is this
room about to become non-compliant, and why?** — by cross-reading the live
sources that actually move the numbers:

* **staff absence** — ``staff_absences`` open on the day removes rostered
  adults from the room they were deployed to,
* **child movement** — today's resolved bookings (``sessions``) put children in
  rooms their base assignment doesn't reflect: ad-hoc extras, room swaps and
  children with no room at all,
* **age-band changes** — a child who has aged past their room's band both needs
  moving and changes the ratio the receiving room must hold,
* **late collection** — a child still on the premises after their booked
  session end keeps counting towards ratio while staff are going home.

It owns no table. Everything is derived, so the board is always current, and a
setting that hasn't filled in a rota or a booking calendar still gets a sensible
answer from whatever it does have.

Follows the 4-layer pattern: computation + SQLite access here, CLI in
``ratio_alerts_cli.py``, Tk GUI in ``ratio_alerts_views.py``.
"""

from __future__ import annotations

import datetime as _dt
import logging
import sqlite3
from dataclasses import dataclass, field
from typing import Any

from education_system.systems.nursery.infrastructure.database import connect, init_db
from education_system.systems.nursery.domain.operations.ratios import ratios as _ratios
from education_system.systems.nursery.domain.operations.sessions import sessions as _sessions

logger = logging.getLogger(__name__)

FEATURE_NAME = "Live Ratio Alerts"
CATEGORY = "Staff & Ratios"

# Alert severities, most serious first — used for sorting and colouring.
SEVERITIES = ("breach", "warning", "info")

CATEGORIES = (
    "ratio", "staff-absence", "child-movement", "age-band",
    "late-collection", "capacity", "setup",
)

# Minutes past a booked session end before a child counts as a late collection.
LATE_GRACE_MINUTES = 10

# A room within this many children of its ratio limit is "on the edge" — one
# more child, or one adult leaving, tips it into a breach.
TIGHT_MARGIN = 1


class ValidationError(ValueError):
    """Raised for invalid ratio-alert input."""


@dataclass
class RoomState:
    """Everything the alert rules need to know about one room on one day."""

    room: str
    age_group: str | None
    staff_ratio: str | None
    capacity: int
    min_age_months: int | None
    max_age_months: int | None
    status: str
    children_booked: int
    children_present: int
    children_counted: int
    counted_from: str  # 'register' | 'bookings' | 'roll'
    staff_rostered: int
    staff_absent: int
    staff_from: str  # 'rota' | 'roll'
    absent_staff: list[str] = field(default_factory=list)

    @property
    def staff_available(self) -> int:
        return max(self.staff_rostered - self.staff_absent, 0)

    @property
    def required_staff(self) -> int | None:
        return _ratios.required_staff_for(self.children_counted, self.staff_ratio)

    @property
    def compliant(self) -> bool | None:
        req = self.required_staff
        if req is None:
            return None
        return self.staff_available >= req

    @property
    def shortfall(self) -> int:
        req = self.required_staff
        if req is None:
            return 0
        return max(req - self.staff_available, 0)

    @property
    def spare_places(self) -> int | None:
        """How many more children this room can take at its current staffing."""
        denom = _ratios.parse_ratio(self.staff_ratio)
        if denom is None:
            return None
        return self.staff_available * denom - self.children_counted


@dataclass
class Alert:
    severity: str
    category: str
    room: str | None
    message: str
    detail: str = ""
    subject_id: str | None = None  # pupil / staff id the alert is about

    @property
    def sort_key(self) -> tuple[int, int, str]:
        sev = SEVERITIES.index(self.severity) if self.severity in SEVERITIES else 9
        cat = CATEGORIES.index(self.category) if self.category in CATEGORIES else 9
        return (sev, cat, self.room or "")


def _ensure_schema() -> None:
    try:
        init_db()
    except sqlite3.Error:
        logger.exception("Failed to initialise nursery DB for ratio alerts")
        raise


def _today() -> str:
    return _dt.date.today().isoformat()


def _now() -> str:
    return _dt.datetime.now().strftime("%H:%M")


def _check_date(day: str | None) -> str:
    v = (day or "").strip() or _today()
    try:
        _dt.date.fromisoformat(v)
    except ValueError as e:
        raise ValidationError("Date must be YYYY-MM-DD") from e
    return v


# ── Live sources ─────────────────────────────────────────────────────────────

def absent_staff_today(day: str | None = None) -> dict[str, dict[str, Any]]:
    """``staff_id -> absence detail`` for staff off on ``day``.

    Reads the Staff Absence module's own database. That module is optional in a
    bare install, so a missing table is treated as "nobody is off" rather than
    an error — the rest of the board still works.
    """
    day = _check_date(day)
    try:
        from education_system.systems.nursery.domain.staff.staff_absence import (
            staff_absence as _absence,
        )
        rows = _absence.list_absences(open_only=True)
    except Exception:  # noqa: BLE001 — module or table missing / unreadable
        logger.debug("Staff absence data unavailable for ratio alerts",
                     exc_info=True)
        return {}
    out: dict[str, dict[str, Any]] = {}
    for a in rows:
        if a.absence_date > day:
            continue
        if a.actual_return and a.actual_return <= day:
            continue
        out[a.staff_id] = {
            "type": a.absence_type,
            "since": a.absence_date,
            "cover_source": a.cover_source,
            "cover_required": a.cover_required,
        }
    return out


def _rostered_staff(day: str) -> tuple[dict[str, list[str]], str]:
    """``room -> [staff_id]`` on ``day``, from the rota or the base deployment."""
    _ensure_schema()
    try:
        with connect() as conn:
            shifts = conn.execute(
                "SELECT staff_id, room FROM rota_shifts "
                "WHERE shift_date = ? AND status IN ('scheduled', 'confirmed')",
                (day,)).fetchall()
            if shifts:
                out: dict[str, list[str]] = {}
                for r in shifts:
                    if r["room"]:
                        out.setdefault(r["room"], []).append(r["staff_id"])
                return out, "rota"
            # No rota for that day — fall back to where staff are based.
            base = conn.execute(
                "SELECT staff_id, room FROM staff "
                "WHERE (end_date IS NULL OR end_date = '') AND room IS NOT NULL "
                "AND room <> ''").fetchall()
    except sqlite3.Error:
        logger.exception("_rostered_staff failed")
        raise
    out = {}
    for r in base:
        out.setdefault(r["room"], []).append(r["staff_id"])
    return out, "roll"


def _present_children(day: str) -> dict[str, set[str]]:
    """``room -> {pupil_id}`` marked in on ``day`` from the daily register."""
    _ensure_schema()
    try:
        with connect() as conn:
            rows = conn.execute(
                "SELECT a.pupil_id, COALESCE(NULLIF(a.room, ''), p.room) AS room "
                "FROM attendance_records a "
                "LEFT JOIN pupils p ON p.pupil_id = a.pupil_id "
                "WHERE a.attend_date = ? AND a.status IN ('present', 'late')",
                (day,)).fetchall()
    except sqlite3.Error:
        logger.exception("_present_children failed")
        raise
    out: dict[str, set[str]] = {}
    for r in rows:
        if r["room"]:
            out.setdefault(r["room"], set()).add(r["pupil_id"])
    return out


def _booked_children(day: str) -> tuple[dict[str, set[str]], list[Any]]:
    """``room -> {pupil_id}`` booked in on ``day``, plus the raw sessions."""
    try:
        sessions = _sessions.day_sessions(day)
    except Exception:  # noqa: BLE001 — booking calendar not in use yet
        logger.debug("Booking calendar unavailable for ratio alerts",
                     exc_info=True)
        return {}, []
    out: dict[str, set[str]] = {}
    for s in sessions:
        if s.room:
            out.setdefault(s.room, set()).add(s.pupil_id)
    return out, sessions


def _roll_children(day: str) -> dict[str, set[str]]:
    """``room -> {pupil_id}`` from the plain roll — the last-resort headcount."""
    _ensure_schema()
    try:
        with connect() as conn:
            rows = conn.execute(
                "SELECT pupil_id, room FROM pupils WHERE status = 'active' "
                "AND room IS NOT NULL AND room <> ''").fetchall()
    except sqlite3.Error:
        logger.exception("_roll_children failed")
        raise
    out: dict[str, set[str]] = {}
    for r in rows:
        out.setdefault(r["room"], set()).add(r["pupil_id"])
    return out


# ── Room state ───────────────────────────────────────────────────────────────

def room_states(day: str | None = None) -> list[RoomState]:
    """Per-room live picture for ``day``, blending register, rota and bookings."""
    day = _check_date(day)
    _ensure_schema()
    try:
        with connect() as conn:
            rooms = conn.execute(
                "SELECT name, age_group, staff_ratio, capacity, min_age_months, "
                "max_age_months, status FROM rooms "
                "ORDER BY min_age_months, name").fetchall()
    except sqlite3.Error:
        logger.exception("room_states failed")
        raise

    present = _present_children(day)
    booked, _sessions_today = _booked_children(day)
    roll = _roll_children(day)
    rostered, staff_from = _rostered_staff(day)
    absent = absent_staff_today(day)

    out: list[RoomState] = []
    for r in rooms:
        name = r["name"]
        present_n = len(present.get(name, ()))
        booked_n = len(booked.get(name, ()))
        if present:
            counted, counted_from = present_n, "register"
        elif booked:
            counted, counted_from = booked_n, "bookings"
        else:
            counted, counted_from = len(roll.get(name, ())), "roll"

        staff_ids = rostered.get(name, [])
        absent_here = [s for s in staff_ids if s in absent]
        out.append(RoomState(
            room=name, age_group=r["age_group"], staff_ratio=r["staff_ratio"],
            capacity=int(r["capacity"] or 0),
            min_age_months=r["min_age_months"], max_age_months=r["max_age_months"],
            status=r["status"], children_booked=booked_n,
            children_present=present_n, children_counted=counted,
            counted_from=counted_from, staff_rostered=len(staff_ids),
            staff_absent=len(absent_here), staff_from=staff_from,
            absent_staff=absent_here,
        ))
    return out


# ── Alert rules ──────────────────────────────────────────────────────────────

def _staff_names() -> dict[str, str]:
    try:
        with connect() as conn:
            return {r["staff_id"]: f"{r['first_name']} {r['last_name']}"
                    for r in conn.execute(
                        "SELECT staff_id, first_name, last_name FROM staff"
                    ).fetchall()}
    except sqlite3.Error:
        logger.exception("_staff_names failed")
        return {}


def _age_months(dob: str, day: str) -> int | None:
    try:
        born = _dt.date.fromisoformat(dob)
        on = _dt.date.fromisoformat(day)
    except (TypeError, ValueError):
        return None
    months = (on.year - born.year) * 12 + (on.month - born.month)
    if on.day < born.day:
        months -= 1
    return max(months, 0)


def _ratio_alerts(states: list[RoomState]) -> list[Alert]:
    alerts: list[Alert] = []
    for st in states:
        if st.status != "open":
            continue
        if st.required_staff is None:
            alerts.append(Alert(
                "warning", "setup", st.room,
                f"{st.room} has no staff:child ratio set",
                "Set the room's required ratio so compliance can be checked.",
            ))
            continue
        if st.compliant is False:
            alerts.append(Alert(
                "breach", "ratio", st.room,
                f"{st.room} is {st.shortfall} adult(s) under ratio",
                f"{st.children_counted} children ({st.counted_from}) need "
                f"{st.required_staff} adults at {st.staff_ratio}; "
                f"{st.staff_available} available"
                + (f" ({st.staff_absent} absent)" if st.staff_absent else ""),
            ))
        elif st.spare_places is not None and 0 <= st.spare_places <= TIGHT_MARGIN:
            alerts.append(Alert(
                "warning", "ratio", st.room,
                f"{st.room} is on the edge of its ratio",
                f"{st.children_counted} children with {st.staff_available} "
                f"adults at {st.staff_ratio} — room for only "
                f"{st.spare_places} more child(ren). One absence or one extra "
                "child tips it into a breach.",
            ))
        if st.capacity and st.children_booked > st.capacity:
            alerts.append(Alert(
                "warning", "capacity", st.room,
                f"{st.room} is booked over capacity",
                f"{st.children_booked} booked against a capacity of "
                f"{st.capacity}.",
            ))
    return alerts


def _absence_alerts(states: list[RoomState], staff_names: dict[str, str],
                    day: str) -> list[Alert]:
    alerts: list[Alert] = []
    absent = absent_staff_today(day)
    for st in states:
        for sid in st.absent_staff:
            info = absent.get(sid, {})
            name = staff_names.get(sid, sid)
            severity = "breach" if st.compliant is False else "warning"
            cover = info.get("cover_source")
            cover_note = ("no cover arranged" if info.get("cover_required")
                          and cover in (None, "Pending", "")
                          else f"cover: {cover}" if cover else "")
            alerts.append(Alert(
                severity, "staff-absence", st.room,
                f"{name} is absent from {st.room}"
                + (" — the room is now under ratio"
                   if severity == "breach" else ""),
                " — ".join(x for x in (
                    f"{info.get('type', 'absence')} since "
                    f"{info.get('since', '?')}", cover_note) if x),
                subject_id=sid,
            ))
    # Absent staff who aren't tied to any room still reduce the setting's cover.
    roomed = {sid for st in states for sid in st.absent_staff}
    for sid, info in absent.items():
        if sid in roomed:
            continue
        alerts.append(Alert(
            "info", "staff-absence", None,
            f"{staff_names.get(sid, sid)} is absent (not deployed to a room)",
            f"{info.get('type', 'absence')} since {info.get('since', '?')}",
            subject_id=sid,
        ))
    return alerts


def _movement_alerts(states: list[RoomState], day: str) -> list[Alert]:
    """Children whose whereabouts today differ from their base room."""
    alerts: list[Alert] = []
    by_room = {st.room: st for st in states}

    try:
        sessions = _sessions.day_sessions(day)
    except Exception:  # noqa: BLE001
        logger.debug("Booking calendar unavailable for movement alerts",
                     exc_info=True)
        sessions = []

    base = _roll_children(day)
    base_room = {pid: room for room, pids in base.items() for pid in pids}

    for s in sessions:
        if not s.room:
            alerts.append(Alert(
                "warning", "child-movement", None,
                f"{s.child_name or s.pupil_id} is booked in with no room",
                "Assign a room so they are counted in a ratio.",
                subject_id=s.pupil_id))
            continue
        if s.room not in by_room:
            alerts.append(Alert(
                "warning", "child-movement", s.room,
                f"{s.child_name or s.pupil_id} is booked into '{s.room}', "
                "which is not a defined room",
                "Ratios cannot be checked for an undefined room.",
                subject_id=s.pupil_id))
            continue
        home = base_room.get(s.pupil_id)
        if home and home != s.room:
            st = by_room[s.room]
            severity = "breach" if st.compliant is False else "info"
            alerts.append(Alert(
                severity, "child-movement", s.room,
                f"{s.child_name or s.pupil_id} is in {s.room} today, not "
                f"their usual {home}",
                f"{s.room} now counts {st.children_counted} children against "
                f"{st.staff_available} adults.",
                subject_id=s.pupil_id))
        if s.source == "extra":
            st = by_room[s.room]
            if st.spare_places is not None and st.spare_places <= 0:
                alerts.append(Alert(
                    "breach" if st.compliant is False else "warning",
                    "child-movement", s.room,
                    f"Extra session for {s.child_name or s.pupil_id} leaves "
                    f"{s.room} with no ratio headroom",
                    f"{st.children_counted} children, {st.staff_available} "
                    f"adults at {st.staff_ratio}.",
                    subject_id=s.pupil_id))

    # Children on the roll with no room at all never reach a ratio calculation.
    try:
        unplaced = _ratios.list_unplaced_children()
    except Exception:  # noqa: BLE001
        logger.debug("Could not count unplaced children", exc_info=True)
        unplaced = 0
    if unplaced:
        alerts.append(Alert(
            "warning", "child-movement", None,
            f"{unplaced} active child(ren) are not assigned to a known room",
            "They are not counted in any room's ratio.",
        ))
    return alerts


def _age_band_alerts(states: list[RoomState], day: str) -> list[Alert]:
    """Children who have aged out of their room's band."""
    _ensure_schema()
    try:
        with connect() as conn:
            children = conn.execute(
                "SELECT pupil_id, first_name, last_name, date_of_birth, room "
                "FROM pupils WHERE status = 'active' AND date_of_birth IS NOT "
                "NULL AND date_of_birth <> ''").fetchall()
    except sqlite3.Error:
        logger.exception("_age_band_alerts failed")
        raise

    by_room = {st.room: st for st in states}
    ordered = sorted(
        (st for st in states if st.min_age_months is not None),
        key=lambda st: st.min_age_months or 0)

    alerts: list[Alert] = []
    for c in children:
        st = by_room.get(c["room"])
        if st is None:
            continue
        months = _age_months(c["date_of_birth"], day)
        if months is None:
            continue
        name = f"{c['first_name']} {c['last_name']}"
        if st.max_age_months is not None and months > st.max_age_months:
            nxt = next((o for o in ordered
                        if (o.min_age_months or 0) <= months
                        and (o.max_age_months is None
                             or months <= o.max_age_months)
                        and o.room != st.room), None)
            move_to = f" — ready to move to {nxt.room}" if nxt else ""
            detail = (f"{months} months old; {st.room} covers up to "
                      f"{st.max_age_months} months.")
            if nxt is not None:
                spare = nxt.spare_places
                if spare is not None and spare <= 0:
                    detail += (f" {nxt.room} has no ratio headroom "
                               f"({nxt.children_counted} children, "
                               f"{nxt.staff_available} adults).")
            alerts.append(Alert(
                "warning", "age-band", st.room,
                f"{name} has aged out of {st.room}{move_to}",
                detail, subject_id=c["pupil_id"]))
        elif st.min_age_months is not None and months < st.min_age_months:
            alerts.append(Alert(
                "warning", "age-band", st.room,
                f"{name} is younger than {st.room}'s age band",
                f"{months} months old; {st.room} starts at "
                f"{st.min_age_months} months. A younger child needs a tighter "
                "ratio than this room is staffed for.",
                subject_id=c["pupil_id"]))
    return alerts


def _late_collection_alerts(states: list[RoomState], day: str,
                            now: str | None = None) -> list[Alert]:
    """Children still on site past their booked session end."""
    if day != _today():
        return []  # 'still here' only means anything for today
    clock = now or _now()

    try:
        from education_system.systems.nursery.domain.academics.attendance.sign_in_out import (
            sign_in_out as _sio,
        )
        on_site = {ev.pupil_id: ev for ev in _sio.currently_in(day)}
    except Exception:  # noqa: BLE001 — sign in/out not in use
        logger.debug("Sign in/out data unavailable for late-collection alerts",
                     exc_info=True)
        return []
    if not on_site:
        return []

    try:
        sessions = _sessions.day_sessions(day)
    except Exception:  # noqa: BLE001
        logger.debug("Booking calendar unavailable for late-collection alerts",
                     exc_info=True)
        return []

    by_room = {st.room: st for st in states}
    alerts: list[Alert] = []
    seen: set[str] = set()
    for s in sessions:
        if s.pupil_id not in on_site or s.pupil_id in seen or not s.end_time:
            continue
        late = _minutes_between(s.end_time, clock)
        if late <= LATE_GRACE_MINUTES:
            continue
        seen.add(s.pupil_id)
        st = by_room.get(s.room or "")
        severity = "breach" if st is not None and st.compliant is False \
            else ("warning" if late < 60 else "breach")
        detail = (f"Booked until {s.end_time}; still signed in at {clock}. "
                  "They keep counting towards ratio until collected.")
        if st is not None and st.spare_places is not None and st.spare_places <= 0:
            detail += (f" {st.room} has no headroom "
                       f"({st.children_counted} children, "
                       f"{st.staff_available} adults).")
        if late >= 60:
            detail += " Over an hour — follow the uncollected-child procedure."
        alerts.append(Alert(
            severity, "late-collection", s.room,
            f"{s.child_name or s.pupil_id} is {late} minutes past their "
            "booked collection time", detail, subject_id=s.pupil_id))
    return alerts


def _minutes_between(start: str, end: str) -> int:
    try:
        a = _dt.datetime.strptime(start, "%H:%M")
        b = _dt.datetime.strptime(end, "%H:%M")
    except ValueError:
        return 0
    return max(int((b - a).total_seconds() // 60), 0)


# ── Public API ───────────────────────────────────────────────────────────────

def list_alerts(day: str | None = None, *, now: str | None = None,
                severity: str | None = None,
                category: str | None = None) -> list[Alert]:
    """Every live ratio-compliance warning for ``day``, worst first."""
    day = _check_date(day)
    if _sessions.is_closed(day):
        return [Alert("info", "setup", None,
                      f"The setting is closed on {day}",
                      ", ".join(c.name for c in _sessions.closures_on(day)))]

    states = room_states(day)
    staff_names = _staff_names()
    alerts = (
        _ratio_alerts(states)
        + _absence_alerts(states, staff_names, day)
        + _movement_alerts(states, day)
        + _age_band_alerts(states, day)
        + _late_collection_alerts(states, day, now)
    )
    if severity:
        alerts = [a for a in alerts if a.severity == severity]
    if category:
        alerts = [a for a in alerts if a.category == category]
    alerts.sort(key=lambda a: a.sort_key)
    return alerts


def breaches(day: str | None = None) -> list[Alert]:
    """Only the alerts that mean a room is non-compliant right now."""
    return list_alerts(day, severity="breach")


def summary(day: str | None = None, *, now: str | None = None) -> dict[str, Any]:
    """Headline counts for the alerts board and the dashboard banner."""
    day = _check_date(day)
    alerts = list_alerts(day, now=now)
    states = room_states(day)
    by_category = {c: sum(1 for a in alerts if a.category == c)
                   for c in CATEGORIES}
    return {
        "date": day,
        "alerts": len(alerts),
        "breaches": sum(1 for a in alerts if a.severity == "breach"),
        "warnings": sum(1 for a in alerts if a.severity == "warning"),
        "rooms": len(states),
        "rooms_in_breach": sum(1 for s in states if s.compliant is False),
        "rooms_on_edge": sum(
            1 for s in states
            if s.compliant and s.spare_places is not None
            and 0 <= s.spare_places <= TIGHT_MARGIN),
        "children": sum(s.children_counted for s in states),
        "staff_available": sum(s.staff_available for s in states),
        "staff_absent": sum(s.staff_absent for s in states),
        "counted_from": states[0].counted_from if states else "roll",
        "staff_from": states[0].staff_from if states else "roll",
        "by_category": by_category,
    }


def headline(day: str | None = None) -> str:
    """One line for a dashboard banner — empty when everything is compliant."""
    s = summary(day)
    if s["breaches"]:
        return (f"⚠ {s['breaches']} live ratio breach(es) across "
                f"{s['rooms_in_breach']} room(s)")
    if s["warnings"]:
        return f"{s['warnings']} ratio warning(s) — no room is under ratio yet"
    return ""
