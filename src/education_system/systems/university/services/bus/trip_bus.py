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
* Records in-trip incidents through Trip Management, which routes them.

Public surface:

* ``create_trip(...)`` → trip_id (publishes EVENT_TRIP_CREATED +
  EVENT_CALENDAR_CHANGED)
* ``register_student(trip_id, student_id, fee=)``
* ``cancel_registration(trip_id, student_id, *, fee=, refund=)``
* ``record_incident(trip_id, student_id, kind, description,
                    severity='Minor')`` — stored as a trip incident and routed
  (H&S / safeguarding / a DP case for conduct)
* ``raise_safeguarding_concern(...)`` — the safeguarding service route
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
# kind -> trips.trip_type
_KIND_TRIP_TYPE = {"trip": "day", "su_trip": "su_social",
                   "field_trip": "fieldwork", "research_trip": "fieldwork"}


def _resolve_user_id(conn, who: Any) -> int | None:
    """``users.id`` for a username, or for a number that is a users.id.

    Returns None for 'system' / unknown values (``created_by`` is nullable).
    """
    if who is None or str(who).strip() == "":
        return None
    row = conn.execute("SELECT id FROM users WHERE username = ? COLLATE NOCASE LIMIT 1",
                       (str(who),)).fetchone()
    if row:
        return int(row[0])
    if str(who).isdigit():
        row = conn.execute("SELECT id FROM users WHERE id = ?", (int(who),)).fetchone()
        if row:
            return int(row[0])
    return None


def _resolve_participant(student_id: str | int) -> tuple[int | None, str | None]:
    """``(users.id, student_id)`` for a student number, username or users.id.

    A student number is tried first — student numbers can be all digits,
    so a number is never assumed to be ``users.id``. Raises ValueError when
    nothing matches.
    """
    from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management import (
        database as tm_db, registrations as tm_reg,
    )
    sid = str(student_id).strip()
    with tm_db.read_connection() as conn:
        try:
            return tm_reg.resolve_participant(conn, student_id=sid)
        except ValueError:
            pass
        try:
            return tm_reg.resolve_participant(conn, username=sid)
        except ValueError:
            pass
        if sid.isdigit():
            return tm_reg.resolve_participant(conn, user_id=int(sid))
    raise ValueError(f"could not resolve a student or user for {sid}")


def _publish(event: str, **payload: Any) -> None:
    try:
        from education_system.systems.university.infrastructure.event_bus import publish
        publish(event, **payload)
    except Exception as exc:
        logger.debug("trip bus publish failed: %s", exc)


def publish_trip_event(event: str, **payload: Any) -> None:
    """Publish a trip event (``trip.created``, ``trip.updated``,
    ``trip.status.changed``, ``trip.registration.changed``…).

    The public entry point for Trip Management — call it after the write
    has committed. Never raises.
    """
    _publish(event, **payload)


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
            logger.debug("Suppressed exception", exc_info=True)

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
            logger.debug("Suppressed exception", exc_info=True)

    body = description or ""
    # Stash the kind in description so older readers can still see it;
    # trip_type / source carry it as columns as well.
    tagged = f"[kind:{kind}] " + body if body else f"[kind:{kind}]"

    from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management import (
        database as tm_db, trips as tm_trips,
    )

    pending: list = []
    new_id: int | None = None
    try:
        # The trip, its history row and its calendar event are one
        # transaction, so a failure leaves nothing half-written.
        with tm_db.write_transaction() as conn:
            created_by_int = _resolve_user_id(conn, created_by)
            fields = tm_trips.clean_trip_fields({
                "trip_name": name, "description": tagged, "destination": destination,
                "start_date": start_date[:10], "end_date": (end_date or start_date)[:10],
                "max_participants": max_participants or 50, "cost": cost or 0.0,
                "trip_type": _KIND_TRIP_TYPE[kind],
            })
            trip = tm_trips.insert_trip(
                conn, fields, created_by=created_by_int,
                changed_by=str(created_by) if created_by is not None else "trip_bus",
                source="su" if kind == "su_trip" else "operations", pending=pending,
                event_payload={"kind": kind, "name": name,
                               "leader_staff_id": leader_staff_id})
            new_id = trip["id"]
    except Exception as exc:
        logger.warning("create_trip failed: %s", exc)
        return None

    # trip.created and the calendar notification go out only after commit.
    tm_db.run_after_commit(pending)

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
    """Register a student on a trip (a ``trip_participants`` row).

    ``student_id`` is a student number (or a username). Refuses with an
    active finance hold, a trip that is not open, a full trip and someone
    already on it — the capacity check and the insert share one
    ``BEGIN IMMEDIATE`` transaction. A cancelled earlier registration is
    re-used. The fee is charged after the commit; a failed charge is
    reported in ``charge_error``, not swallowed.

    Returns ``{ok, registration_id, charge_tx, charge_error, reason}``.
    """
    if not trip_id or not student_id:
        return {"ok": False, "reason": "trip_id + student_id required"}
    try:
        user_id, sid = _resolve_participant(student_id)
    except ValueError as exc:
        return {"ok": False, "reason": str(exc)}

    # Finance-hold gate (#5 from earlier rounds).
    try:
        from education_system.systems.university.services.bus.finance_bus import (
            has_active_hold,
        )
        if sid and has_active_hold(sid):
            return {"ok": False,
                    "reason": "Active finance hold — settle outstanding "
                              "charges before registering."}
    except Exception:
        logger.debug("Suppressed exception", exc_info=True)

    from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management import (
        database as tm_db, trips as tm_trips,
    )
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    rid: int | None = None
    try:
        with tm_db.write_transaction() as conn:
            trip = tm_trips.get_trip(int(trip_id), conn=conn)
            if not trip:
                return {"ok": False, "reason": "trip not found"}
            if trip["status"] != "open":
                return {"ok": False, "reason": f"trip is not open for registration ({trip['status']})"}
            if sid:
                row = conn.execute("SELECT id, status FROM trip_participants WHERE trip_id = ? "
                                   "AND student_id = ? ORDER BY id DESC LIMIT 1",
                                   (int(trip_id), sid)).fetchone()
            else:
                row = conn.execute("SELECT id, status FROM trip_participants WHERE trip_id = ? "
                                   "AND user_id = ? ORDER BY id DESC LIMIT 1",
                                   (int(trip_id), user_id)).fetchone()
            if row and row[1] in tm_db.CURRENT_PARTICIPANT_STATUSES:
                return {"ok": False, "reason": "already registered", "registration_id": row[0]}
            if tm_trips.active_participant_count(conn, int(trip_id)) >= (trip["max_participants"] or 0):
                return {"ok": False, "reason": "trip is full"}
            payment_status = "pending" if (fee or trip["cost"] or 0) > 0 else "paid"
            if row:
                rid = row[0]
                conn.execute(
                    "UPDATE trip_participants SET status = 'registered', registration_date = ?, "
                    "user_id = ?, payment_status = ?, cancellation_date = NULL, "
                    "cancellation_reason = NULL, amount_paid = 0, amount_refunded = 0 "
                    "WHERE id = ?", (now, user_id, payment_status, rid))
            else:
                rid = conn.execute(
                    "INSERT INTO trip_participants (trip_id, student_id, user_id, "
                    "registration_date, status, payment_status, source) "
                    "VALUES (?, ?, ?, ?, 'registered', ?, ?)",
                    (int(trip_id), sid, user_id, now, payment_status,
                     trip.get("source") or "operations")).lastrowid
    except Exception as exc:
        return {"ok": False, "reason": f"insert failed: {exc}"}

    charge_tx = charge_error = None
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
            if charge_tx is None:
                charge_error = "finance did not record the charge"
        except Exception as exc:
            logger.warning("trip fee charge failed for %s on trip %s: %s", sid, trip_id, exc)
            charge_error = str(exc)

    _publish(
        "trip.registration.changed",
        registration_id=rid, trip_id=int(trip_id),
        student_id=sid, action="registered",
        fee=fee, charge_tx=charge_tx,
    )
    return {"ok": True, "registration_id": rid,
            "charge_tx": charge_tx, "charge_error": charge_error, "reason": ""}


def cancel_registration(trip_id: int, student_id: str | int,
                        *, cancellation_fee: float | None = None,
                        refund_paid_fee: float | None = None,
                        reason: str | None = None,
                        ) -> dict[str, Any]:
    """Mark the registration cancelled; optionally apply fee/refund.

    The row is kept (status 'cancelled', ``cancellation_date``). Finance
    calls run after the commit and a failure is returned in
    ``finance_errors`` rather than swallowed.
    """
    if not trip_id or not student_id:
        return {"ok": False, "reason": "trip_id + student_id required"}
    try:
        user_id, sid = _resolve_participant(student_id)
    except ValueError as exc:
        return {"ok": False, "reason": str(exc)}

    from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management import (
        database as tm_db,
    )
    current = tm_db.CURRENT_PARTICIPANT_STATUSES
    marks = ", ".join("?" * len(current))
    try:
        with tm_db.write_transaction() as conn:
            if sid:
                where, who = "student_id = ?", sid
            else:
                where, who = "user_id = ?", user_id
            cur = conn.execute(
                "UPDATE trip_participants SET status = 'cancelled', cancellation_date = ?, "
                "cancellation_reason = ? "
                f"WHERE trip_id = ? AND {where} AND status IN ({marks})",
                (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), reason, int(trip_id), who, *current))
            if cur.rowcount == 0:
                return {"ok": False, "reason": "no current registration"}
    except Exception as exc:
        return {"ok": False, "reason": str(exc)}

    cancel_tx = refund_tx = None
    finance_errors: list[str] = []
    try:
        from education_system.systems.university.services.bus.finance_bus import (
            raise_charge,
        )
    except Exception as exc:
        raise_charge = None
        if (cancellation_fee and cancellation_fee > 0) or (refund_paid_fee and refund_paid_fee > 0):
            finance_errors.append(f"finance unavailable: {exc}")
    if raise_charge is not None:
        if cancellation_fee and cancellation_fee > 0:
            try:
                cancel_tx = raise_charge(
                    sid, float(cancellation_fee),
                    source="trip_cancellation",
                    description=f"Trip cancellation fee — trip:{trip_id}",
                    reference_id=f"trip:{trip_id}",
                    processed_by="trip_management",
                )
                if cancel_tx is None:
                    finance_errors.append("cancellation fee not recorded")
            except Exception as exc:
                finance_errors.append(f"cancellation fee failed: {exc}")
        if refund_paid_fee and refund_paid_fee > 0:
            try:
                # Negative charge (credit) for the refund.
                refund_tx = raise_charge(
                    sid, -float(refund_paid_fee),
                    source="trip_refund",
                    description=f"Trip refund — trip:{trip_id}",
                    reference_id=f"trip:{trip_id}",
                    processed_by="trip_management",
                )
                if refund_tx is None:
                    finance_errors.append("refund not recorded")
            except Exception as exc:
                finance_errors.append(f"refund failed: {exc}")
    for err in finance_errors:
        logger.warning("trip %s cancellation for %s: %s", trip_id, sid or user_id, err)

    _publish(
        "trip.registration.changed",
        trip_id=int(trip_id), student_id=sid, action="cancelled",
        cancel_tx=cancel_tx, refund_tx=refund_tx,
    )
    return {"ok": True, "cancel_tx": cancel_tx,
            "refund_tx": refund_tx, "finance_errors": finance_errors, "reason": ""}


# ---------------------------------------------------------------------------
# Trip Management's domain API, for other university domains
#
# Slices may not import each other, so the Students' Union screens
# (pastoral) and the academic calendar (academics) reach Trip Management
# through these. Each takes the signed-in ``auth`` and raises
# PermissionError / ValueError exactly as Trip Management does.
# ---------------------------------------------------------------------------

def _tm():
    from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management import (
        calendar_integration, database, registrations, trips,
    )
    return trips, registrations, database, calendar_integration


def browse_trips(*, source: str | None = None, club: str | None = None,
                 open_only: bool = False) -> list[dict[str, Any]]:
    """``trips.list_trips`` — trips with their place counts (archived left out)."""
    return _tm()[0].list_trips(source=source, club=club, open_only=open_only)


def create_su_trip(auth: Any, club: str | None, **fields: Any) -> dict[str, Any]:
    """``trips.create_su_trip`` — a 'proposed' Students' Union trip for ``club``.

    Students' Union officers may propose a trip for any club (or none);
    a club's committee for that club only (:func:`su_organiser_scope`).
    Anyone else raises PermissionError. The trip still needs approval
    before it opens.
    """
    club = (club or "").strip() or None
    return _tm()[0].create_su_trip(_su_organiser_auth(auth, club=club, creating=True), club,
                                   **fields)


# ---------------------------------------------------------------------------
# Students' Union organisers
#
# Students hold no ``create_trips`` / ``manage_trips`` permission, so a club
# committee or a Union officer acts on Students' Union trips with those two
# permissions granted for that one call — and only after the checks below
# (officer, or committee of the trip's own club). Everything else (approval
# gates, refunds, history) is Trip Management's as usual.
# ---------------------------------------------------------------------------

_COMMITTEE_ROLES_EXCLUDED = ("", "member")


def su_organiser_scope(auth: Any) -> dict[str, Any]:
    """Which Students' Union trips the signed-in user may organise.

    ``{'all': bool, 'clubs': [club names]}`` — ``all`` for trip staff
    (``create_trips`` / ``manage_trips``) and active Union representatives
    (``union_representatives``); ``clubs`` are the active clubs where the
    user is president, treasurer or secretary, or holds a committee role
    in ``club_members`` (any role other than 'member').
    """
    if not auth or not getattr(auth, "current_user", None):
        return {"all": False, "clubs": []}
    if auth.check_permission("manage_trips") or auth.check_permission("create_trips"):
        return {"all": True, "clubs": _active_club_names()}
    student_id = _tm()[0].actor(auth)["student_id"]
    if not student_id:
        return {"all": False, "clubs": []}
    sid = str(student_id)
    with get_connection() as conn:
        officer = conn.execute(
            "SELECT 1 FROM union_representatives WHERE student_id = ? "
            "AND COALESCE(status, 'active') = 'active' "
            "AND (COALESCE(term_end_date, term_end) IS NULL "
            "     OR COALESCE(term_end_date, term_end) >= date('now')) LIMIT 1",
            (sid,)).fetchone() if _has_table(conn, "union_representatives") else None
        if officer:
            return {"all": True, "clubs": _active_club_names(conn)}
        clubs = {r[0] for r in conn.execute(
            "SELECT club_name FROM student_clubs WHERE COALESCE(status, 'active') = 'active' "
            "AND ? IN (president_id, treasurer_id, secretary_id)", (sid,)).fetchall()}
        if _has_table(conn, "club_members"):
            clubs.update(r[0] for r in conn.execute(
                "SELECT c.club_name FROM club_members m JOIN student_clubs c ON c.club_id = m.club_id "
                "WHERE m.student_id = ? AND COALESCE(c.status, 'active') = 'active' "
                f"AND LOWER(COALESCE(m.role, '')) NOT IN ({', '.join('?' * len(_COMMITTEE_ROLES_EXCLUDED))})",
                (sid, *_COMMITTEE_ROLES_EXCLUDED)).fetchall())
    return {"all": False, "clubs": sorted(clubs)}


def _has_table(conn, name: str) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
                        (name,)).fetchone() is not None


def _active_club_names(conn=None) -> list[str]:
    if conn is None:
        with get_connection() as own:
            return _active_club_names(own)
    if not _has_table(conn, "student_clubs"):
        return []
    return [r[0] for r in conn.execute(
        "SELECT club_name FROM student_clubs WHERE COALESCE(status, 'active') = 'active' "
        "ORDER BY club_name").fetchall()]


class _SUOrganiserAuth:
    """``auth`` with ``create_trips`` / ``manage_trips`` added for one call."""

    _GRANTED = frozenset({"create_trips", "manage_trips"})

    def __init__(self, auth: Any):
        self._auth = auth

    @property
    def current_user(self):
        return self._auth.current_user

    def check_permission(self, permission: str) -> bool:
        return permission in self._GRANTED or self._auth.check_permission(permission)

    def __getattr__(self, name: str):
        return getattr(self._auth, name)


def _su_organiser_auth(auth: Any, *, club: str | None = None, trip_id: int | None = None,
                       creating: bool = False) -> Any:
    """``auth`` itself for trip staff; the organiser wrapper for a Union
    officer or the committee of the club concerned; PermissionError otherwise."""
    if not auth or not getattr(auth, "current_user", None):
        raise PermissionError("You must be logged in.")
    if auth.check_permission("manage_trips") or (creating and auth.check_permission("create_trips")):
        return auth
    trips = _tm()[0]
    if trip_id is not None:
        trip = trips.get_trip(int(trip_id))
        if not trip:
            raise ValueError("Trip not found.")
        if auth.check_permission("create_trips") and trips.can_manage_trip(auth, trip):
            return auth
        if (trip.get("source") or "operations") != "su":
            raise PermissionError("Only Trip Management can change this trip.")
        if trips.can_manage_trip(auth, trip):
            # The SU trip's creator or one of its leaders.
            return _SUOrganiserAuth(auth)
        club = trip.get("organising_club")
    scope = su_organiser_scope(auth)
    if scope["all"] or (club and club in scope["clubs"]):
        return _SUOrganiserAuth(auth)
    raise PermissionError(
        "Only Students' Union officers and club committee members can organise trips"
        + (f" for {club}." if club else "."))


def can_organise_su_trip(auth: Any, trip_id: int) -> bool:
    """True when :func:`update_su_trip` and friends would let this user act."""
    try:
        _su_organiser_auth(auth, trip_id=trip_id)
    except (PermissionError, ValueError):
        return False
    return True


def su_organiser_trips(auth: Any, *, club: str | None = None) -> list[dict[str, Any]]:
    """Students' Union trips (archived left out) the user may organise."""
    rows = browse_trips(source="su", club=club)
    if auth and (auth.check_permission("manage_trips")):
        return rows
    scope = su_organiser_scope(auth)
    trips = _tm()[0]
    who = trips.actor(auth) if auth and getattr(auth, "current_user", None) else None
    out = []
    for row in rows:
        if scope["all"] or (row.get("organising_club") in scope["clubs"]):
            out.append(row)
        elif who and who["user_id"] is not None and row.get("created_by") == who["user_id"]:
            out.append(row)
    return out


def update_su_trip(auth: Any, trip_id: int, **fields: Any) -> dict[str, Any]:
    """``trips.update_trip_record`` for a Students' Union trip's organisers."""
    return _tm()[0].update_trip_record(_su_organiser_auth(auth, trip_id=trip_id), trip_id,
                                       **fields)


def set_su_trip_status(auth: Any, trip_id: int, new_status: str,
                       reason: str = "") -> dict[str, Any]:
    """``trips.set_trip_status`` (cancel releases places and refunds) for organisers."""
    return _tm()[0].set_trip_status(_su_organiser_auth(auth, trip_id=trip_id), trip_id,
                                    new_status, reason)


def archive_su_trip(auth: Any, trip_id: int, reason: str = "") -> dict[str, Any]:
    """``trips.archive_trip`` — the replacement for deleting a trip."""
    return _tm()[0].archive_trip(_su_organiser_auth(auth, trip_id=trip_id), trip_id, reason)


def su_trip_history(auth: Any, trip_id: int) -> list[dict[str, Any]]:
    """``trips.list_history`` for a Students' Union trip's organisers: every
    recorded change, newest first."""
    return _tm()[0].list_history(_su_organiser_auth(auth, trip_id=trip_id), trip_id)


def submit_su_trip_for_approval(auth: Any, trip_id: int) -> dict[str, Any]:
    """``approvals.submit_for_approval`` for a Students' Union trip's organisers."""
    return _tm_module("approvals").submit_for_approval(
        _su_organiser_auth(auth, trip_id=trip_id), trip_id)


def su_trip_participants(auth: Any, trip_id: int, *, include_ended: bool = False
                         ) -> dict[str, Any]:
    """An organiser's view of a trip: ``{'participants', 'waitlist', 'health_counts'}``.

    Health details are never returned — ``health_counts`` says only how many
    participants have medical, dietary or accessibility details recorded.
    """
    organiser = _su_organiser_auth(auth, trip_id=trip_id)
    return {
        "participants": _tm()[1].list_participants(organiser, trip_id, include_ended=include_ended),
        "waitlist": _tm_module("waitlist").positions(trip_id),
        "health_counts": _tm_module("medical").counts(trip_id),
    }


# ---------------------------------------------------------------------------
# A participant's own place: payment, waiting-list offers, health consent
# ---------------------------------------------------------------------------

def pay_for_registration(auth: Any, participant_id: int, method: str,
                         amount: float | None = None) -> dict[str, Any]:
    """``payments.pay_for_registration`` — pay towards a place through Finance."""
    return _tm_module("payments").pay_for_registration(auth, participant_id, method, amount)


def trip_payment_methods() -> list[tuple[str, str]]:
    """``[(method, label)]`` accepted by :func:`pay_for_registration`."""
    payments = _tm_module("payments")
    return [(m, payments.method_label(m))
            for m in (payments.CASH, payments.CARD, payments.STUDENT_ACCOUNT)]


def accept_trip_offer(auth: Any, participant_id: int) -> dict[str, Any]:
    """``waitlist.accept_offer`` — take up a place offered from the waiting list."""
    return _tm_module("waitlist").accept_offer(auth, participant_id)


def decline_trip_offer(auth: Any, participant_id: int, reason: str = "") -> bool:
    """``waitlist.decline_offer`` — pass an offered place to the next person."""
    return _tm_module("waitlist").decline_offer(auth, participant_id, reason)


def give_trip_health_consent(auth: Any, participant_id: int, consent: bool = True) -> bool:
    """``medical.give_health_share_consent`` — the participant's own consent."""
    return _tm_module("medical").give_health_share_consent(auth, participant_id, consent)


def my_trip_places(auth: Any) -> list[dict[str, Any]]:
    """:func:`my_registrations` plus each place's ``owed``, ``waitlist_place``
    (1 = next to be offered) and ``offer_expires_at``."""
    trips, registrations, database, _calendar = _tm()
    money = _tm_module("money")
    rows = registrations.list_my_registrations(auth)
    lists: dict[int, dict[int, int]] = {}
    with database.read_connection() as conn:
        for row in rows:
            place = registrations.get_participant(row["participant_id"], conn=conn) or {}
            trip = trips.get_trip(row["trip_id"], conn=conn) or {}
            row["offer_expires_at"] = place.get("offer_expires_at")
            row["source"] = trip.get("source") or "operations"
            row["organising_club"] = trip.get("organising_club")
            row["owed"] = (money.amount_owed(place, trip)
                           if row["status"] in ("registered", "confirmed", "attended") else 0.0)
            if row["status"] == "waitlisted":
                if row["trip_id"] not in lists:
                    lists[row["trip_id"]] = {
                        p["participant_id"]: p["place"]
                        for p in _tm_module("waitlist").positions(row["trip_id"], conn=conn)}
                row["waitlist_place"] = lists[row["trip_id"]].get(row["participant_id"])
            else:
                row["waitlist_place"] = None
    return rows


def register_participant(auth: Any, trip_id: int, **details: Any) -> dict[str, Any]:
    """``registrations.register`` — take a place (the signed-in user's own by default)."""
    return _tm()[1].register(auth, trip_id, **details)


def cancel_participant(auth: Any, participant_id: int, reason: str = "") -> dict[str, Any]:
    """``registrations.cancel_registration`` — give a place up (refund after commit)."""
    return _tm()[1].cancel_registration(auth, participant_id, reason)


def my_registrations(auth: Any) -> list[dict[str, Any]]:
    """``registrations.list_my_registrations`` for the signed-in user."""
    return _tm()[1].list_my_registrations(auth)


def create_trip_from_calendar_event(auth: Any, event_id: str, **fields: Any) -> dict[str, Any]:
    """Create a 'proposed' trip whose calendar entry is the existing ``event_id``.

    Needs ``create_trips`` or ``manage_trips``. One transaction: the trip,
    its history and the event link commit together. Returns the trip dict.
    """
    trips, _registrations, database, _calendar = _tm()
    who = trips._require(auth, 'create_trips', 'manage_trips')
    cleaned = trips.clean_trip_fields(fields)
    pending: list = []
    with database.write_transaction() as conn:
        trip = trips.insert_trip(conn, cleaned, created_by=who['user_id'],
                                 changed_by=who['username'], pending=pending,
                                 link_event_id=event_id)
    database.run_after_commit(pending)
    return trip


def refresh_trip_calendar_event(trip_id: int, *, changed_by: str | None = None) -> str | None:
    """Write (or refresh) a trip's calendar event the way Trip Management does.

    Returns the event id; ``None`` when the calendar is unavailable. Raises
    ValueError for a missing, cancelled or archived trip.
    """
    trips, _registrations, database, calendar = _tm()
    pending: list = []
    with database.write_transaction() as conn:
        trip = trips.get_trip(trip_id, conn=conn)
        if not trip:
            raise ValueError("Trip not found")
        if trip['status'] in ('cancelled', 'archived'):
            raise ValueError(f"The trip is {trip['status']}")
        event_id = calendar.sync_trip_calendar_event(
            conn, trip_id, trip_name=trip['trip_name'], destination=trip['destination'],
            start_date=trip['start_date'], end_date=trip['end_date'], cost=trip['cost'],
            created_by=changed_by, pending=pending)
    database.run_after_commit(pending)
    return event_id


# ---------------------------------------------------------------------------
# Incident escalation (#6)
# ---------------------------------------------------------------------------

# kind / severity words other systems use -> Trip Management's vocabulary
_INCIDENT_KINDS = {"behaviour": "conduct", "behavior": "conduct", "misconduct": "conduct",
                   "conduct": "conduct", "injury": "injury", "illness": "illness",
                   "safeguarding": "safeguarding", "near_miss": "near_miss",
                   "near miss": "near_miss", "other": "other"}
_INCIDENT_SEVERITIES = {"minor": "minor", "low": "minor", "moderate": "moderate",
                        "medium": "moderate", "major": "serious", "severe": "serious",
                        "serious": "serious", "high": "serious", "critical": "critical"}


def record_incident(trip_id: int, student_id: str | int,
                    *, kind: str = "behaviour",
                    description: str = "",
                    severity: str = "Minor") -> dict[str, Any]:
    """Log an in-trip incident through Trip Management's incident record.

    Every incident — minor ones too — is stored in ``trip_incidents`` and
    routed by ``incidents.route``: injuries / serious ones to Health &
    Safety, safeguarding ones to the safeguarding service, and conduct
    (``behaviour``) of moderate severity or worse to a disciplinary case
    against ``student_id`` (Major / Critical as before). Returns
    ``{ok, case_id, incident_id, hs_id, concern_id}``.
    """
    from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management import (
        incidents,
    )
    tm_kind = _INCIDENT_KINDS.get(str(kind or "").strip().lower(), "incident")
    tm_severity = _INCIDENT_SEVERITIES.get(str(severity or "").strip().lower(), "minor")
    text = (description or "").strip() or f"{kind} incident"
    if len(text) < 5:
        text = f"{kind} incident: {text}"
    try:
        routed = incidents.record_system_incident(
            int(trip_id), tm_kind, tm_severity, text,
            subject_id=str(student_id) if student_id not in (None, "") else None,
            persons_involved=str(student_id) if student_id not in (None, "") else "",
            offense_type=f"trip_incident:{kind}")
    except Exception as exc:
        return {"ok": False, "case_id": None, "reason": str(exc)}
    return {"ok": True, **routed}


def raise_safeguarding_concern(*, reporter: str | None, text: str, severity: str = "HIGH",
                               location: str | None = None) -> int | None:
    """Raise a concern in the safeguarding service on someone's behalf.

    The route the chat reports and the chatbot use
    (``submissions.save_submission``): it lands in the classified
    safeguarding database with risk scoring, SLA and on-call DSL assignment.
    Severity is at least ``severity`` and higher when the text says so.
    Returns the submission id; raises when it could not be raised.
    """
    from education_system.systems.university.domains.safeguarding.application.services import (
        submissions,
    )
    from education_system.systems.university.domains.safeguarding.domain.analysis import (
        SEVERITY_ORDER, analyse_text,
    )
    matches, overall = analyse_text(text)
    categories = {category: m["snippets"] for category, m in matches.items()}
    if overall in SEVERITY_ORDER and SEVERITY_ORDER[overall] > SEVERITY_ORDER.get(severity, 0):
        severity = overall
    full_name, role = reporter or "trip management", "staff"
    try:
        with get_connection() as conn:
            row = conn.execute("SELECT first_name || ' ' || last_name, role FROM users "
                               "WHERE username = ? COLLATE NOCASE", (str(reporter or ""),)).fetchone()
            if row:
                full_name, role = (row[0] or full_name).strip() or full_name, row[1] or role
    except Exception:
        logger.debug("reporter lookup failed", exc_info=True)
    return submissions.save_submission(
        {"username": reporter or "trip_management", "full_name": full_name, "role": role},
        text, severity, categories, on_behalf_of=True, reporter_username=reporter,
        case_location=location, case_department="Trips & Mobility")


# ---------------------------------------------------------------------------
# Trip safety, approval and academic API (wave 2) for other domains
# ---------------------------------------------------------------------------

def _tm_module(name: str):
    import importlib
    return importlib.import_module(
        "education_system.systems.university.domains.operations.domain.campus.mobility."
        f"services.trip_management.{name}")


def trip_approval_state(trip_id: int) -> dict[str, Any]:
    """``approvals.approval_state`` — stages required and their decisions."""
    return _tm_module("approvals").approval_state(trip_id)


def trip_open_problems(trip_id: int) -> list[str]:
    """``approvals.gate_problems(trip_id, 'open')`` — what stops the trip opening."""
    return _tm_module("approvals").gate_problems(trip_id, "open")


def report_trip_incident(auth: Any, trip_id: int, kind: str, severity: str, description: str,
                         **fields: Any) -> int:
    """``incidents.report_incident`` for a signed-in user (staff or participant)."""
    return _tm_module("incidents").report_incident(auth, trip_id, kind, severity, description,
                                                   **fields)


def trip_staffing_problems(trip_id: int) -> list[str]:
    """``safeguarding.staffing_check`` — ratio, first aid and DBS problems."""
    return _tm_module("safeguarding").staffing_check(trip_id)


def trip_participant_age(student_id: str, on_date: str | None = None) -> dict[str, Any]:
    """``safeguarding.age_check`` — age on a date and whether parental consent is needed."""
    return _tm_module("safeguarding").age_check(student_id, on_date)


def trip_timetable_clashes(trip_id: int) -> list[dict[str, Any]]:
    """``academic.timetable_clashes`` — participants with sessions during the trip."""
    return _tm_module("academic").timetable_clashes(trip_id)


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
                   "       max_participants, cost, status, trip_type, source, "
                   "       organising_club "
                   "FROM trips WHERE status <> 'archived' ")
            params: list[Any] = []
            if since:
                sql += "AND start_date >= ? "
                params.append(since[:10])
            if kind:
                sql += "AND (description LIKE ? OR (? = 'su_trip' AND source = 'su')) "
                params.extend([f"%[kind:{kind}]%", kind])
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
                    d["kind"] = "su_trip" if d.get("source") == "su" else "trip"
                out.append(d)
    except Exception as exc:
        logger.warning("list_trips failed: %s", exc)
    return out


def list_registrations_for(student_id: str | int) -> list[dict[str, Any]]:
    """A student's trip registrations (student number, username or users.id)."""
    if not student_id:
        return []
    try:
        user_id, sid = _resolve_participant(student_id)
    except ValueError:
        return []
    out: list[dict[str, Any]] = []
    try:
        with get_connection() as conn:
            for r in conn.execute(
                "SELECT tp.id AS registration_id, tp.trip_id, "
                "       tp.status, tp.registration_date, tp.payment_status, "
                "       t.trip_name, t.destination, t.start_date, t.cost "
                "FROM trip_participants tp "
                "LEFT JOIN trips t ON t.id = tp.trip_id "
                "WHERE (? IS NOT NULL AND tp.student_id = ?) "
                "   OR (? IS NOT NULL AND tp.user_id = ?) "
                "ORDER BY tp.registration_date DESC",
                (sid, sid, user_id, user_id),
            ).fetchall():
                out.append(dict(r))
    except Exception as exc:
        logger.warning("list_registrations_for failed: %s", exc)
    return out


__all__ = [
    "create_trip", "register_student", "cancel_registration", "publish_trip_event",
    "browse_trips", "create_su_trip", "register_participant", "cancel_participant",
    "my_registrations", "create_trip_from_calendar_event", "refresh_trip_calendar_event",
    "record_incident", "raise_safeguarding_concern", "list_trips", "list_registrations_for",
    "trip_approval_state", "trip_open_problems", "report_trip_incident",
    "trip_staffing_problems", "trip_participant_age", "trip_timetable_clashes",
    "su_organiser_scope", "can_organise_su_trip", "su_organiser_trips", "update_su_trip",
    "set_su_trip_status", "archive_su_trip", "submit_su_trip_for_approval",
    "su_trip_participants", "pay_for_registration", "trip_payment_methods",
    "accept_trip_offer", "decline_trip_offer", "give_trip_health_consent", "my_trip_places",
]
