"""Trips & Payments: places on a trip, the waiting list and consent.

Part of :mod:`modules.trips.domain.trips`, which re-exports everything here -
import it from there (trips.invite ...), not from this module.
"""

from __future__ import annotations

from typing import Any

from education_system.systems.secondary.modules.trips.domain.trips import (  # noqa: F401
    _NON_PAYMENT,
    APPROVAL_LABELS,
    BOOKING_STATUSES,
    CONSENT_CHOICES,
    DEFAULT_BOOKING_STATUS,
    PAYING_STATUSES,
    PLACE_STATUSES,
    RELEASED,
    Booking,
    Trip,
    ValidationError,
    _audit,
    _choice,
    _date,
    _deny,
    _flag,
    _pupil,
    _require_editor,
    _require_staff,
    _staff_name,
    _text,
    can_run_day,
    due_by,
    get,
    get_booking,
    is_editor,
    list_bookings,
    list_payments,
    list_trips,
    money,
    plain,
    schedule,
)
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.core.academic_calendar.school_year import today as _today
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

# ── Places ───────────────────────────────────────────────────────────

def _booking_status(t: Trip, wanted: str, conn, skip: int | None = None) -> str:
    """Confirmed only while there's room; otherwise the waiting list."""
    if wanted != "Confirmed" or t.capacity is None:
        return wanted
    taken = conn.execute("SELECT COUNT(*) FROM trip_bookings WHERE trip_id = ? AND status IN "
                         "('Confirmed', 'Attended') AND booking_id != ?",
                         (t.trip_id, skip or 0)).fetchone()[0]
    return "Confirmed" if taken < t.capacity else "Waitlist"


def _booking_problems(t: Trip) -> list[str]:
    if t.status in ("Cancelled", "Completed"):
        return [f"The trip is {t.status.lower()}"]
    return []


def create_booking(trip_id: int, data: dict[str, Any], *, actor: Principal) -> Booking:
    """The old New booking (*data* carries ``pupil_id`` - id or admission no.).
    Confirming beyond capacity puts the pupil on the waiting list."""
    t = get(trip_id)
    _require_editor(actor, "book", f"trip:{t.trip_id}")
    problems = _booking_problems(t)
    ref = data.get("pupil_id") or data.get("student_id") or data.get("pupil")
    p = _pupil(ref)
    if p is None:
        problems.append("Pupil is required" if not ref else f"No pupil {ref}")
    elif p.roll_status != "on_roll":
        problems.append(f"{p.display_name} is not on roll")
    day = _date(data.get("booking_date"), "Booking date", problems) or _today().isoformat()
    status = _choice(data.get("status"), BOOKING_STATUSES, "Status", problems,
                     DEFAULT_BOOKING_STATUS)
    consent = _consent_value(data, problems)
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        if conn.execute("SELECT 1 FROM trip_bookings WHERE trip_id = ? AND pupil_id = ?",
                        (t.trip_id, p.pupil_id)).fetchone():
            raise ValidationError([f"{p.display_name} is already booked on this trip"])
        status = _booking_status(t, status, conn)
        bid = conn.execute(
            "INSERT INTO trip_bookings (trip_id, pupil_id, booking_date, status, consent, "
            "consent_date, consent_note, medical_note, dietary_note, notes, created_by) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (t.trip_id, p.pupil_id, day, status, consent,
             _today().isoformat() if consent else None, _text(data.get("consent_note"), 500),
             _text(data.get("medical_note"), 1000), _text(data.get("dietary_note"), 500),
             _text(data.get("notes"), 2000), actor.username)).lastrowid
        _audit(conn, "book", actor, trip_id=t.trip_id, booking_id=bid, pupil_id=p.pupil_id,
               status=status)
    activity_log.record("trips.book", target=p.admission_no, principal=actor, trip=t.trip_id)
    return get_booking(bid)


def _consent_value(data: dict[str, Any], problems: list[str]) -> str | None:
    if "consent" in data:
        v = data["consent"]
        if isinstance(v, bool):
            return "Yes" if v else "No"
        return _choice(v, CONSENT_CHOICES, "Consent", problems, None)
    if "consent_received" in data:
        return "Yes" if _flag(data["consent_received"]) else None
    return None


def invite(trip_id: int, *, actor: Principal, year_group: int | str | None = None,
           form_group: str | None = None, teaching_group: str | None = None,
           pupil_ids: list[int] | None = None, status: str = "Interested"
           ) -> dict[str, int]:
    """Put a year group, form, teaching group (code) or chosen pupils on the
    trip as Interested (or Confirmed / Waitlist as places allow). Pupils
    already booked are left alone. Returns {'added', 'already', 'waitlist'}."""
    t = get(trip_id)
    _require_editor(actor, "invite", f"trip:{t.trip_id}")
    problems = _booking_problems(t)
    wanted = _choice(status, BOOKING_STATUSES, "Status", problems, "Interested")
    pupils: list[P.Pupil] = []
    if year_group not in (None, ""):
        try:
            pupils += P.list_pupils(year_group=int(str(year_group).strip().split()[-1]))
        except ValueError:
            problems.append("Year group must be 7-11")
    if form_group:
        found = P.list_pupils(form_group=form_group)
        if not found:
            problems.append(f"No pupils in form {form_group}")
        pupils += found
    if teaching_group:
        from education_system.systems.secondary.modules.curriculum.domain import (
            teaching_groups as TG,
        )
        g = TG.find(teaching_group.strip())
        if g is None:
            problems.append(f"No teaching group {teaching_group}")
        else:
            pupils += TG.members(g.group_id)
    for pid in pupil_ids or []:
        p = P.get_pupil(int(pid))
        if p is None:
            problems.append(f"No pupil #{pid}")
        elif p.roll_status == "on_roll":
            pupils.append(p)
    if not pupils and not problems:
        problems.append("Choose a year group, form, teaching group or pupils")
    if problems:
        raise ValidationError(problems)
    added = already = waiting = 0
    seen: set[int] = set()
    with database.connect() as conn:
        for p in pupils:
            if p.pupil_id in seen:
                continue
            seen.add(p.pupil_id)
            if conn.execute("SELECT 1 FROM trip_bookings WHERE trip_id = ? AND pupil_id = ?",
                            (t.trip_id, p.pupil_id)).fetchone():
                already += 1
                continue
            st = _booking_status(t, wanted, conn)
            waiting += st == "Waitlist"
            conn.execute("INSERT INTO trip_bookings (trip_id, pupil_id, booking_date, status, "
                         "created_by) VALUES (?, ?, ?, ?, ?)",
                         (t.trip_id, p.pupil_id, _today().isoformat(), st, actor.username))
            added += 1
        label = ", ".join(x for x in (f"Year {year_group}" if year_group else "",
                                      form_group or "", teaching_group or "") if x)
        if label and not t.group_label:
            conn.execute("UPDATE trips SET group_label = ? WHERE trip_id = ?",
                         (label[:120], t.trip_id))
        _audit(conn, "invite", actor, trip_id=t.trip_id, added=added, already=already)
    activity_log.record("trips.invite", target=f"trip:{t.trip_id}", principal=actor,
                        added=added)
    return {"added": added, "already": already, "waitlist": waiting}


def update_booking(booking_id: int, changes: dict[str, Any], *, actor: Principal) -> Booking:
    """The old Edit booking: date, notes, consent, medical and dietary notes
    (status has its own call)."""
    b = get_booking(booking_id)
    t = get(b.trip_id)
    if not (is_editor(actor) or can_run_day(actor, t)):
        _deny(actor, "booking", b.admission_no, "Only the finance office or the trip leader "
                                                "can change a booking.")
    problems: list[str] = []
    vals: dict[str, Any] = {}
    if "booking_date" in changes:
        vals["booking_date"] = _date(changes["booking_date"], "Booking date", problems) or \
            b.booking_date
    for k, n in (("consent_note", 500), ("medical_note", 1000), ("dietary_note", 500),
                 ("notes", 2000), ("consent_by", 120)):
        if k in changes:
            vals[k] = _text(changes[k], n)
    if "consent" in changes or "consent_received" in changes:
        vals["consent"] = _consent_value(changes, problems)
        if vals["consent"] != b.consent:
            vals["consent_date"] = _date(changes.get("consent_date"), "Consent date",
                                         problems) or (_today().isoformat()
                                                       if vals["consent"] else None)
    if "status" in changes and changes["status"] not in (None, "", b.status):
        problems.append("Change the status with Status (places and the waiting list move)")
    if problems:
        raise ValidationError(problems)
    vals = {k: v for k, v in vals.items() if v != getattr(b, k)}
    if not vals:
        return b
    with database.connect() as conn:
        conn.execute("UPDATE trip_bookings SET " + ", ".join(f"{k} = ?" for k in vals)
                     + ", updated_at = datetime('now') WHERE booking_id = ?",
                     (*vals.values(), b.booking_id))
        _audit(conn, "booking", actor, trip_id=b.trip_id, booking_id=b.booking_id,
               pupil_id=b.pupil_id, fields=list(vals))
    activity_log.record("trips.booking", target=b.admission_no, principal=actor,
                        trip=b.trip_id)
    return get_booking(b.booking_id)


def _promote(conn, t: Trip, actor: Principal) -> int | None:
    """Give a free place to the first pupil waiting."""
    if t.capacity is None:
        return None
    taken = conn.execute("SELECT COUNT(*) FROM trip_bookings WHERE trip_id = ? AND status IN "
                         "('Confirmed', 'Attended')", (t.trip_id,)).fetchone()[0]
    if taken >= t.capacity:
        return None
    r = conn.execute("SELECT booking_id, pupil_id FROM trip_bookings WHERE trip_id = ? AND "
                     "status = 'Waitlist' ORDER BY booking_id LIMIT 1",
                     (t.trip_id,)).fetchone()
    if r is None:
        return None
    conn.execute("UPDATE trip_bookings SET status = 'Confirmed', updated_at = datetime('now') "
                 "WHERE booking_id = ?", (r["booking_id"],))
    _audit(conn, "promoted", actor, trip_id=t.trip_id, booking_id=r["booking_id"],
           pupil_id=r["pupil_id"])
    return int(r["booking_id"])


def set_booking_status(booking_id: int, status: str, *, actor: Principal,
                       reason: str | None = None) -> tuple[Booking, Booking | None]:
    """The old Change booking status. Confirming beyond capacity goes to the
    waiting list; releasing a place gives it to the first pupil waiting.
    Cancelling or withdrawing needs a reason, and on a voluntary-contribution
    trip it can never be for not paying. Returns (booking, promoted or None)."""
    b = get_booking(booking_id)
    t = get(b.trip_id)
    _require_editor(actor, "booking_status", b.admission_no)
    problems: list[str] = []
    st = _choice(status, BOOKING_STATUSES, "Status", problems, None)
    if st is None and not problems:
        problems.append("Choose a status")
    why = " ".join(str(reason or "").split())
    if st in RELEASED and b.status not in RELEASED:
        if not why:
            problems.append(f"Say why the place is {st.lower()}")
        elif t.is_voluntary and any(w in why.lower() for w in _NON_PAYMENT):
            problems.append("This trip asks for a voluntary contribution: no pupil can be "
                            "left out because their family hasn't paid (DfE charging policy)")
    if st == "Attended" and not b.departed:
        problems.append("Mark the pupil as departed on the day (On the day) instead")
    if st in PLACE_STATUSES | {"Waitlist", "Interested"} and b.status not in PLACE_STATUSES:
        problems += _booking_problems(t)
    if problems:
        raise ValidationError(problems)
    promoted = None
    with database.connect() as conn:
        new = _booking_status(t, st, conn, skip=b.booking_id) if b.status not in \
            PLACE_STATUSES else st
        conn.execute("UPDATE trip_bookings SET status = ?, notes = CASE WHEN ? = '' THEN notes "
                     "ELSE TRIM(COALESCE(notes, '') || char(10) || ?) END, "
                     "updated_at = datetime('now') WHERE booking_id = ?",
                     (new, why, f"{new} {_today().isoformat()}: {why}", b.booking_id))
        _audit(conn, "booking_status", actor, trip_id=b.trip_id, booking_id=b.booking_id,
               pupil_id=b.pupil_id, status=new)
        if b.status in PLACE_STATUSES and new not in PLACE_STATUSES:
            promoted = _promote(conn, t, actor)
    activity_log.record("trips.booking_status", target=b.admission_no, principal=actor,
                        trip=b.trip_id, status=new)
    return get_booking(b.booking_id), (get_booking(promoted) if promoted else None)


def confirm_place(booking_id: int, *, actor: Principal) -> Booking:
    return set_booking_status(booking_id, "Confirmed", actor=actor)[0]


def delete_booking(booking_id: int, *, actor: Principal) -> bool:
    """The old Delete booking - refused while it holds money."""
    b = get_booking(booking_id)
    _require_editor(actor, "booking_delete", b.admission_no)
    if b.paid_pence > 0:
        raise ValidationError([f"The booking holds {money(b.paid_pence)} - record a refund "
                               "first (or cancel the place and keep the record)"])
    t = get(b.trip_id)
    with database.connect() as conn:
        conn.execute("DELETE FROM trip_bookings WHERE booking_id = ?", (b.booking_id,))
        _audit(conn, "booking_delete", actor, trip_id=b.trip_id, booking_id=b.booking_id,
               pupil_id=b.pupil_id)
        if b.status in PLACE_STATUSES:
            _promote(conn, t, actor)
    activity_log.record("trips.booking_delete", target=b.admission_no, principal=actor,
                        trip=b.trip_id)
    return True


# ── Consent ──────────────────────────────────────────────────────────

def record_consent(booking_id: int, given: Any, *, actor: Principal, day: str | None = None,
                   by: str | None = None, medical_note: str | None = None,
                   dietary_note: str | None = None, note: str | None = None) -> Booking:
    """Parental consent (yes / no, when, who) with the medical and dietary
    notes captured on the form."""
    b = get_booking(booking_id)
    t = get(b.trip_id)
    if not can_run_day(actor, t):
        _deny(actor, "consent", b.admission_no, "Only the finance office or the trip leader "
                                                "can record consent.")
    problems: list[str] = []
    value = _consent_value({"consent": given}, problems)
    if value is None and not problems:
        problems.append("Consent must be Yes or No")
    d = _date(day, "Consent date", problems) or _today().isoformat()
    if d > _today().isoformat():
        problems.append("The consent date can't be in the future")
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        conn.execute("UPDATE trip_bookings SET consent = ?, consent_date = ?, consent_by = ?, "
                     "medical_note = COALESCE(?, medical_note), dietary_note = COALESCE(?, "
                     "dietary_note), consent_note = COALESCE(?, consent_note), "
                     "updated_at = datetime('now') WHERE booking_id = ?",
                     (value, d, _text(by, 120), _text(medical_note, 1000),
                      _text(dietary_note, 500), _text(note, 500), b.booking_id))
        _audit(conn, "consent", actor, trip_id=b.trip_id, booking_id=b.booking_id,
               pupil_id=b.pupil_id, consent=value)
    activity_log.record("trips.consent", target=b.admission_no, principal=actor,
                        trip=b.trip_id)
    return get_booking(b.booking_id)


def consent_missing(trip_id: int | None = None) -> list[Booking]:
    return list_bookings(trip_id, consent_missing=True)


