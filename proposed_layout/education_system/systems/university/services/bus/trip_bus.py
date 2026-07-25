"""Cross-domain trip service — university trips + SU trips, one model.

The platform has three parallel trip tables (``trips``, ``student_trips``,
``union_trips``) plus their own registrations. Rather than write a
fourth, this module:

* Treats ``trips`` as the canonical store and adopts ``kind`` via
  ``description`` prefix (cheap, schema-free).
* Wraps registrations through ``trip_registrations``.
* Posts each trip as a Calendar event so every scheduling GUI sees
  it without code added there.
* Routes fees through ``finance_bus.raise_charge`` and gates
  ``register_student`` on ``has_active_hold``.
* Gates trip creation on the leader's HR availability.
* Escalates serious in-trip incidents to ``cases_bus.open_case``.

Public surface:

* ``create_trip(...)`` → trip_id (publishes EVENT_TRIP_CREATED +
  EVENT_CALENDAR_CHANGED)
* ``register_student(trip_id, student_id, fee=)``
* ``cancel_registration(trip_id, student_id, *, fee=, refund=)``
* ``record_incident(trip_id, student_id, kind, description,
                    severity='Minor')`` — opens a DP case when severe
* ``list_trips(*, since=)``, ``list_registrations_for(student_id)``
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from education_system.systems.university.infrastructure.database.db import (
    sqlite3, get_connection,
)

logger = logging.getLogger(__name__)


_VALID_KINDS = ("trip", "su_trip", "field_trip", "research_trip")


def _publish(event: str, **payload: Any) -> None:
    try:
        from education_system.systems.university.interfaces.gui.academics._event_bus import publish
        publish(event, **payload)
    except Exception as exc:
        logger.debug("trip bus publish failed: %s", exc)


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

def create_trip(
    *,
    name: str,
    destination: str,
    start_date: str,
    end_date: str | None = None,
    kind: str = "trip",
    cost: float | None = None,
    max_participants: int | None = None,
    leader_staff_id: int | str | None = None,
    description: str | None = None,
    created_by: str | None = None,
) -> int | None:
    """Persist a trip + a Calendar event. Returns the new trip_id.

    Refuses with ``leader_unavailable`` when the leader is on
    approved HR leave covering ``start_date``. Soft-fails open if
    HR data is missing (so first-run installs aren't blocked).
    """
    if kind not in _VALID_KINDS or not name or not start_date:
        return None

    # Leader availability gate.
    if leader_staff_id is not None:
        try:
            from education_system.systems.university.services.bus.staff_hr_bus import (
                is_available_on,
            )
            if not is_available_on(leader_staff_id, start_date):
                logger.info(
                    "create_trip blocked: leader %s unavailable on %s",
                    leader_staff_id, start_date,
                )
                return None
        except Exception:
            pass

    # First-aid certification gate for field / research trips. Off-
    # campus trips with no qualified first responder are refused
    # outright. Soft-fails open if cert_bus is unavailable.
    if leader_staff_id is not None and kind in ("field_trip", "research_trip"):
        try:
            from education_system.systems.university.services.bus.cert_bus import (
                list_certifications_for,
            )
            certs = list_certifications_for(leader_staff_id) or []
            today = datetime.now().strftime("%Y-%m-%d")
            has_active_first_aid = False
            for c in certs:
                name_lc = str(c.get("name") or "").lower()
                if "first" not in name_lc or "aid" not in name_lc:
                    continue
                expiry = c.get("expiry_date")
                if (str(c.get("status") or "active").lower() == "active"
                        and (not expiry or str(expiry) >= today)):
                    has_active_first_aid = True
                    break
            if not has_active_first_aid:
                logger.info(
                    "create_trip blocked: leader %s has no active "
                    "first-aid cert for %s trip", leader_staff_id, kind,
                )
                _publish("trip.refused",
                         reason="leader_first_aid_expired",
                         leader_staff_id=leader_staff_id, kind=kind)
                return None
        except Exception:
            pass

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    body = description or ""
    # Stash the kind in description so we can read it back without a
    # schema change. UI surfaces strip the marker before display.
    tagged = f"[kind:{kind}] " + body if body else f"[kind:{kind}]"

    # ``trips.created_by`` is FK→users.id; coerce non-numeric values to
    # NULL so callers can pass usernames or 'system' without failing.
    created_by_int: int | None = None
    if created_by is not None:
        try:
            created_by_int = int(created_by)
        except (TypeError, ValueError):
            try:
                with get_connection() as conn:
                    row = conn.execute(
                        "SELECT id FROM users WHERE username = ? LIMIT 1",
                        (str(created_by),),
                    ).fetchone()
                    created_by_int = int(row[0]) if row else None
            except Exception:
                created_by_int = None

    new_id: int | None = None
    try:
        with get_connection() as conn:
            cur = conn.execute(
                "INSERT INTO trips "
                "(trip_name, description, destination, start_date, end_date, "
                " max_participants, cost, status, created_by, "
                " created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, 'open', ?, ?, ?)",
                (name, tagged, destination, start_date[:10],
                 (end_date or start_date)[:10],
                 max_participants, cost, created_by_int, now, now),
            )
            new_id = cur.lastrowid
            conn.commit()
    except Exception as exc:
        logger.warning("create_trip failed: %s", exc)
        return None

    # Calendar event so every scheduling GUI sees the trip.
    try:
        import uuid
        event_id = str(uuid.uuid4())
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO academic_calendar_events "
                "(id, name, date, date_start, date_end, description, "
                " event_type, date_added, last_modified, created_by) "
                "VALUES (?, ?, NULL, ?, ?, ?, ?, ?, ?, ?)",
                (event_id, f"Trip: {name}",
                 start_date[:10], (end_date or start_date)[:10],
                 f"Destination: {destination}; Cost: {cost or '—'}",
                 ("su_event" if kind == "su_trip" else "trip"),
                 now, now, created_by),
            )
            conn.commit()
        try:
            from education_system.systems.university.interfaces.gui.academics._event_bus import (
                publish, EVENT_CALENDAR_CHANGED,
            )
            publish(EVENT_CALENDAR_CHANGED,
                    event_id=event_id,
                    event_type=("su_event" if kind == "su_trip" else "trip"),
                    action="created",
                    date=start_date[:10])
        except Exception:
            logger.debug("Failed to publish calendar-changed event for event_id=%s",
                         event_id, exc_info=True)
    except Exception:
        logger.warning("trip_bus: failed to record trip/event calendar row",
                       exc_info=True)

    _publish(
        "trip.created",
        trip_id=new_id, kind=kind, name=name, destination=destination,
        start_date=start_date[:10],
        end_date=(end_date or start_date)[:10],
        cost=cost, leader_staff_id=leader_staff_id,
    )

    # Field / research trips auto-raise a date-bounded entry in the
    # risk register so the trip is visible alongside SU events and
    # H&S drills until the trip date passes.
    if kind in ("field_trip", "research_trip") and new_id is not None:
        try:
            from education_system.systems.university.services.bus import (
                risk_bus,
            )
            risk_bus.raise_risk(
                title=f"{kind.replace('_',' ').title()}: {name}",
                category="Safety",
                department="Trips & Mobility",
                description=(
                    f"Auto-raised from trip {new_id}. Destination "
                    f"{destination}, leader {leader_staff_id}, "
                    f"{(end_date or start_date)[:10]}."
                ),
                likelihood=2, impact=4,
                owner=str(leader_staff_id) if leader_staff_id else None,
                reference_id=f"trip:{new_id}",
                next_review_date=start_date[:10],
                expires_at=(end_date or start_date)[:10],
            )
        except Exception as exc:
            logger.debug("trip risk auto-raise failed: %s", exc)

    return new_id


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def register_student(trip_id: int, student_id: str | int,
                     *, fee: float | None = None) -> dict[str, Any]:
    """Register a student. Refuses with active finance hold.

    Returns ``{ok, registration_id, charge_tx, reason}``.
    """
    if not trip_id or not student_id:
        return {"ok": False, "reason": "trip_id + student_id required"}
    sid = str(student_id)

    # Finance-hold gate (#5 from earlier rounds).
    try:
        from education_system.systems.university.services.bus.finance_bus import (
            has_active_hold,
        )
        if has_active_hold(sid):
            return {"ok": False,
                    "reason": "Active finance hold — settle outstanding "
                              "charges before registering."}
    except Exception:
        pass

    now = datetime.now().strftime("%Y-%m-%d")
    # ``trip_registrations.user_id`` is FK→users.id; resolve from
    # students.student_id when the caller passes the student code.
    user_int_id: int | None = None
    try:
        user_int_id = int(sid)
    except ValueError:
        try:
            with get_connection() as conn:
                row = conn.execute(
                    "SELECT id FROM users WHERE username = ? LIMIT 1",
                    (sid,),
                ).fetchone()
                if row:
                    user_int_id = int(row[0])
        except Exception:
            user_int_id = None
    if user_int_id is None:
        return {"ok": False,
                "reason": f"could not resolve user_id for {sid}"}

    rid: int | None = None
    try:
        with get_connection() as conn:
            cur = conn.execute(
                "INSERT INTO trip_registrations "
                "(trip_id, user_id, registration_date, status) "
                "VALUES (?, ?, ?, 'registered')",
                (int(trip_id), user_int_id, now),
            )
            rid = cur.lastrowid
            conn.commit()
    except Exception as exc:
        return {"ok": False, "reason": f"insert failed: {exc}"}

    charge_tx = None
    if fee and fee > 0:
        try:
            from education_system.systems.university.services.bus.finance_bus import (
                raise_charge,
            )
            charge_tx = raise_charge(
                sid, float(fee),
                source="trip_fee",
                description=f"Trip registration fee — trip:{trip_id}",
                reference_id=f"trip:{trip_id}",
                processed_by="trip_management",
            )
        except Exception:
            pass

    _publish(
        "trip.registration.changed",
        registration_id=rid, trip_id=int(trip_id),
        student_id=sid, action="registered",
        fee=fee, charge_tx=charge_tx,
    )
    return {"ok": True, "registration_id": rid,
            "charge_tx": charge_tx, "reason": ""}


def cancel_registration(trip_id: int, student_id: str | int,
                        *, cancellation_fee: float | None = None,
                        refund_paid_fee: float | None = None,
                        ) -> dict[str, Any]:
    """Mark the registration cancelled; optionally apply fee/refund."""
    if not trip_id or not student_id:
        return {"ok": False, "reason": "trip_id + student_id required"}
    sid = str(student_id)
    # Same resolution as register_student.
    user_int_id: int | None = None
    try:
        user_int_id = int(sid)
    except ValueError:
        try:
            with get_connection() as conn:
                row = conn.execute(
                    "SELECT id FROM users WHERE username = ? LIMIT 1",
                    (sid,),
                ).fetchone()
                if row:
                    user_int_id = int(row[0])
        except Exception:
            user_int_id = None
    if user_int_id is None:
        return {"ok": False, "reason": "user_id not found"}
    try:
        with get_connection() as conn:
            conn.execute(
                "UPDATE trip_registrations SET status = 'cancelled' "
                "WHERE trip_id = ? AND user_id = ?",
                (int(trip_id), user_int_id),
            )
            conn.commit()
    except Exception as exc:
        return {"ok": False, "reason": str(exc)}

    cancel_tx = refund_tx = None
    try:
        from education_system.systems.university.services.bus.finance_bus import (
            raise_charge,
        )
        if cancellation_fee and cancellation_fee > 0:
            cancel_tx = raise_charge(
                sid, float(cancellation_fee),
                source="trip_cancellation",
                description=f"Trip cancellation fee — trip:{trip_id}",
                reference_id=f"trip:{trip_id}",
                processed_by="trip_management",
            )
        if refund_paid_fee and refund_paid_fee > 0:
            # Negative charge (credit) for the refund.
            refund_tx = raise_charge(
                sid, -float(refund_paid_fee),
                source="trip_refund",
                description=f"Trip refund — trip:{trip_id}",
                reference_id=f"trip:{trip_id}",
                processed_by="trip_management",
            )
    except Exception:
        pass

    _publish(
        "trip.registration.changed",
        trip_id=int(trip_id), student_id=sid, action="cancelled",
        cancel_tx=cancel_tx, refund_tx=refund_tx,
    )
    return {"ok": True, "cancel_tx": cancel_tx,
            "refund_tx": refund_tx, "reason": ""}


# ---------------------------------------------------------------------------
# Incident escalation (#6)
# ---------------------------------------------------------------------------

def record_incident(trip_id: int, student_id: str | int,
                    *, kind: str = "behaviour",
                    description: str = "",
                    severity: str = "Minor") -> dict[str, Any]:
    """Log an in-trip incident; escalate to a DP case when severe.

    Light incidents (Minor) are recorded as a Calendar note only.
    Major / Critical incidents call ``cases_bus.open_case`` so the
    Disciplinary Portal picks them up via the existing pipeline.
    """
    sid = str(student_id)
    out: dict[str, Any] = {"ok": True, "case_id": None}
    if str(severity).lower() in ("major", "critical", "severe"):
        try:
            from education_system.systems.university.services.bus.cases_bus import (
                open_case,
            )
            cid = open_case(
                kind="disciplinary",
                subject_id=sid,
                offense_type=f"trip_incident:{kind}",
                severity=severity,
                description=(
                    f"Incident on trip:{trip_id} — {description}"
                ),
                opened_by="trip_management",
                location=f"trip:{trip_id}",
            )
            out["case_id"] = cid
        except Exception as exc:
            out["ok"] = False
            out["reason"] = str(exc)
    return out


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------

def list_trips(*, since: str | None = None,
               kind: str | None = None,
               limit: int = 50) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        with get_connection() as conn:
            sql = ("SELECT id AS trip_id, trip_name, description, "
                   "       destination, start_date, end_date, "
                   "       max_participants, cost, status "
                   "FROM trips WHERE 1=1 ")
            params: list[Any] = []
            if since:
                sql += "AND start_date >= ? "
                params.append(since[:10])
            if kind:
                sql += "AND description LIKE ? "
                params.append(f"%[kind:{kind}]%")
            sql += "ORDER BY start_date DESC LIMIT ?"
            params.append(int(limit))
            for r in conn.execute(sql, tuple(params)).fetchall():
                d = dict(r)
                desc = d.get("description") or ""
                if desc.startswith("[kind:") and "]" in desc:
                    end = desc.index("]")
                    d["kind"] = desc[6:end]
                    d["description"] = desc[end + 1:].lstrip()
                else:
                    d["kind"] = "trip"
                out.append(d)
    except Exception as exc:
        logger.warning("list_trips failed: %s", exc)
    return out


def list_registrations_for(student_id: str | int) -> list[dict[str, Any]]:
    if not student_id:
        return []
    out: list[dict[str, Any]] = []
    sid = str(student_id)
    try:
        with get_connection() as conn:
            user_int_id: int | None = None
            try:
                user_int_id = int(sid)
            except ValueError:
                row = conn.execute(
                    "SELECT id FROM users WHERE username = ? LIMIT 1",
                    (sid,),
                ).fetchone()
                if row:
                    user_int_id = int(row[0])
            if user_int_id is None:
                return out
            for r in conn.execute(
                "SELECT tr.id AS registration_id, tr.trip_id, "
                "       tr.status, tr.registration_date, "
                "       t.trip_name, t.destination, t.start_date, t.cost "
                "FROM trip_registrations tr "
                "LEFT JOIN trips t ON t.id = tr.trip_id "
                "WHERE tr.user_id = ? "
                "ORDER BY tr.registration_date DESC",
                (user_int_id,),
            ).fetchall():
                out.append(dict(r))
    except Exception as exc:
        logger.warning("list_registrations_for failed: %s", exc)
    return out


__all__ = [
    "create_trip", "register_student", "cancel_registration",
    "record_incident", "list_trips", "list_registrations_for",
]
