"""Year 6 Transition: induction / taster days, new-parents' evening,
summer school and enhanced-transition visits for the incoming cohort.

Each event has a date, times, a type and an audience (fixed lists); children
are invited (the audience, or chosen children) and marked attended / absent
/ apologies; :func:`register` and :func:`export_register` give the register.
Cohort, permissions and the audit trail are in
:mod:`modules.progression.domain.year6_transition`.
"""

from __future__ import annotations

import csv
import datetime as _dt
from pathlib import Path
from typing import Any, Iterable

from education_system.systems.secondary.core.utilities.exports import safe_cell as _safe
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.database import connection as database
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.modules.progression.domain.year6_transition import (
    ATTENDANCE,
    AUDIENCES,
    EVENT_TYPES,
    NotFound,
    ValidationError,
    _TIME_RE,
    _audit,
    _date,
    _long,
    _require_editor,
    _require_staff,
    _text,
    _year,
    cohort,
)


def _clean_event(data: dict[str, Any], problems: list[str]) -> dict[str, Any]:
    out = {"title": _text(data.get("title"), 120), "event_type": data.get("event_type"),
           "event_date": _date(data.get("event_date"), "Date", problems),
           "start_time": _text(data.get("start_time"), 5),
           "end_time": _text(data.get("end_time"), 5), "audience": data.get("audience"),
           "location": _text(data.get("location"), 120),
           "notes": _long(data.get("notes"), 2000)}
    if out["event_type"] not in EVENT_TYPES:
        problems.append("Choose the type of event")
    if not out["title"]:
        out["title"] = out["event_type"] if out["event_type"] in EVENT_TYPES else None
    if not out["title"]:
        problems.append("Give the event a title")
    if out["audience"] not in AUDIENCES:
        problems.append("Choose who the event is for")
    for k, label in (("start_time", "Start time"), ("end_time", "End time")):
        if out[k] and not _TIME_RE.match(out[k]):
            problems.append(f"{label} must be a time like 09:30")
    if out["start_time"] and out["end_time"] and out["end_time"] <= out["start_time"]:
        problems.append("The end time must be after the start time")
    return out


def create_event(intake_year: str, data: dict[str, Any], *, actor: Principal) -> int:
    _require_editor(actor, "event")
    year = _year(intake_year)
    problems: list[str] = []
    clean = _clean_event(data, problems)
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        cols = list(clean)
        cur = conn.execute(f"INSERT INTO y6_events (intake_year, {', '.join(cols)}, created_by) "  # noqa: S608 - fixed keys
                           f"VALUES (?, {', '.join('?' for _ in cols)}, ?)",
                           [year, *clean.values(), actor.username])
        eid = int(cur.lastrowid)
        _audit(conn, "event_add", actor, year, event=eid, type=clean["event_type"])
    activity_log.record("year6.event_add", target=eid, principal=actor)
    return eid


def _event_row(conn, event_id: int) -> dict[str, Any]:
    r = conn.execute("SELECT * FROM y6_events WHERE event_id = ?", (int(event_id),)).fetchone()
    if r is None:
        raise NotFound(f"No transition event {event_id}")
    return dict(r)


def get_event(event_id: int, *, actor: Principal) -> dict[str, Any]:
    _require_staff(actor, "view", event_id)
    with database.connect() as conn:
        return _event_row(conn, event_id)


def update_event(event_id: int, data: dict[str, Any], *, actor: Principal) -> None:
    _require_editor(actor, "event")
    with database.connect() as conn:
        ev = _event_row(conn, event_id)
        problems: list[str] = []
        clean = _clean_event({**ev, **data}, problems)
        if problems:
            raise ValidationError(problems)
        conn.execute(f"UPDATE y6_events SET {', '.join(f'{k} = ?' for k in clean)}, "  # noqa: S608 - fixed keys
                     "updated_at = datetime('now') WHERE event_id = ?",
                     [*clean.values(), int(event_id)])
        _audit(conn, "event_update", actor, ev["intake_year"], event=event_id)
    activity_log.record("year6.event_update", target=event_id, principal=actor)


def delete_event(event_id: int, *, actor: Principal) -> None:
    """Delete an event (its invitations and attendance go with it)."""
    _require_editor(actor, "event")
    with database.connect() as conn:
        ev = _event_row(conn, event_id)
        n = conn.execute("SELECT COUNT(*) FROM y6_event_invites WHERE event_id = ?",
                         (int(event_id),)).fetchone()[0]
        conn.execute("DELETE FROM y6_events WHERE event_id = ?", (int(event_id),))
        _audit(conn, "event_delete", actor, ev["intake_year"], event=event_id,
               title=ev["title"], date=ev["event_date"], invites=n)
    activity_log.record("year6.event_delete", target=event_id, principal=actor)


def events(intake_year: str, *, actor: Principal) -> list[dict[str, Any]]:
    """Events in date order with invited / attended counts."""
    _require_staff(actor, "view")
    with database.connect() as conn:
        rows = [dict(r) for r in conn.execute(
            "SELECT e.*, (SELECT COUNT(*) FROM y6_event_invites i WHERE i.event_id = e.event_id)"
            " AS invited, (SELECT COUNT(*) FROM y6_event_invites i WHERE i.event_id = "
            "e.event_id AND i.attendance = 'attended') AS attended FROM y6_events e WHERE "
            "e.intake_year = ? ORDER BY e.event_date, e.start_time", (_year(intake_year),))]
    return rows


def audience_ids(event_id: int, *, actor: Principal) -> list[int]:
    """The children the event's audience means (active cohort, or the
    enhanced-transition group); none for "Invited pupils"."""
    ev = get_event(event_id, actor=actor)
    if ev["audience"] == "Invited pupils":
        return []
    rows = cohort(ev["intake_year"], actor=actor)
    if ev["audience"] == "Enhanced transition group":
        rows = [r for r in rows if r.enhanced]
    return [r.cohort_id for r in rows]


def invite(event_id: int, cohort_ids: Iterable[int] | None = None, *,
           actor: Principal) -> int:
    """Invite children (default: the event's audience). Returns how many were added."""
    _require_editor(actor, "invite", event_id)
    ids = list(dict.fromkeys(int(c) for c in (cohort_ids if cohort_ids is not None
                                             else audience_ids(event_id, actor=actor))))
    with database.connect() as conn:
        ev = _event_row(conn, event_id)
        valid = {r["cohort_id"] for r in conn.execute(
            "SELECT cohort_id FROM y6_cohort WHERE intake_year = ?", (ev["intake_year"],))}
        bad = [c for c in ids if c not in valid]
        if bad:
            raise ValidationError([f"{len(bad)} chosen child(ren) aren't in the "
                                   f"{ev['intake_year']} cohort"])
        n = 0
        for c in ids:
            n += conn.execute("INSERT OR IGNORE INTO y6_event_invites (event_id, cohort_id, "
                              "invited_by) VALUES (?, ?, ?)",
                              (int(event_id), c, actor.username)).rowcount or 0
        _audit(conn, "invite", actor, ev["intake_year"], event=event_id, added=n)
    activity_log.record("year6.invite", target=event_id, principal=actor, added=n)
    return n


def uninvite(event_id: int, cohort_ids: Iterable[int], *, actor: Principal) -> int:
    _require_editor(actor, "invite", event_id)
    with database.connect() as conn:
        ev = _event_row(conn, event_id)
        n = 0
        for c in dict.fromkeys(int(c) for c in cohort_ids):
            n += conn.execute("DELETE FROM y6_event_invites WHERE event_id = ? AND cohort_id = ?",
                              (int(event_id), c)).rowcount or 0
        _audit(conn, "uninvite", actor, ev["intake_year"], event=event_id, removed=n)
    return n


def mark(event_id: int, cohort_ids: Iterable[int], attendance: str, *,
         actor: Principal) -> int:
    """Mark invited children attended / absent / apologies (or back to invited)."""
    _require_editor(actor, "mark", event_id)
    if attendance not in ATTENDANCE:
        raise ValidationError(["Attendance must be invited, attended, absent or apologies"])
    with database.connect() as conn:
        ev = _event_row(conn, event_id)
        if attendance in ("attended", "absent") and ev["event_date"] > \
                _dt.date.today().isoformat():
            raise ValidationError(["The event hasn't happened yet"])
        n = 0
        for c in dict.fromkeys(int(c) for c in cohort_ids):
            n += conn.execute(
                "UPDATE y6_event_invites SET attendance = ?, marked_by = ?, marked_at = "
                "datetime('now') WHERE event_id = ? AND cohort_id = ?",
                (attendance, actor.username, int(event_id), c)).rowcount or 0
        _audit(conn, "mark", actor, ev["intake_year"], event=event_id, attendance=attendance,
               count=n)
    activity_log.record("year6.mark", target=event_id, principal=actor, attendance=attendance)
    return n


def register(event_id: int, *, actor: Principal) -> list[dict[str, Any]]:
    """Who is invited and their attendance, by name."""
    ev = get_event(event_id, actor=actor)
    rows = {r.cohort_id: r for r in cohort(ev["intake_year"], actor=actor,
                                           include_inactive=True)}
    with database.connect() as conn:
        inv = [dict(r) for r in conn.execute("SELECT * FROM y6_event_invites WHERE event_id = ?",
                                             (int(event_id),))]
    out = [{"cohort_id": i["cohort_id"], "row": rows[i["cohort_id"]],
            "attendance": i["attendance"], "marked_by": i["marked_by"],
            "marked_at": i["marked_at"]} for i in inv if i["cohort_id"] in rows]
    return sorted(out, key=lambda d: d["row"].name)


def export_register(event_id: int, path: str | Path, *, actor: Principal) -> int:
    ev = get_event(event_id, actor=actor)
    rows = register(event_id, actor=actor)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow([_safe(ev["title"]), ev["event_type"], ev["event_date"],
                    ev.get("start_time") or "", ev.get("end_time") or "", ev["audience"]])
        w.writerow(["surname", "first name", "feeder school", "form", "attendance"])
        for d in rows:
            r = d["row"]
            w.writerow([_safe(r.last_name), _safe(r.preferred_name or r.first_name),
                        _safe(r.feeder_school), _safe(r.form_name),
                        ATTENDANCE[d["attendance"]]])
    activity_log.record("year6.export", principal=actor, rows=len(rows), what="register")
    return len(rows)
