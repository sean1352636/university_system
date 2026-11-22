import html

from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management import _common
from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management._common import sqlite3, get_text, logging, datetime, log_create, log_read, log_update, log_delete
from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management.database import safe_db_operation
from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management import payments

logger = logging.getLogger(__name__)

RECEIPT_TEMPLATE = 'campus_services/mobility/trip_registration_receipt'
CANCELLATION_TEMPLATE = 'campus_services/mobility/trip_cancellation_refund'


def _run_db_operation(operation):
    from education_system.systems.university.domains.operations.domain.campus.mobility.services import trip_management as _tm
    return _tm.safe_db_operation(operation)


def _format_trip_dates(start_date, end_date):
    """One date for a single-day trip, a range otherwise."""
    if not end_date or start_date == end_date:
        return start_date
    return get_text(
        "mobility.trip_management.receipt.date_range", "{start_date} to {end_date}",
    ).format(start_date=start_date, end_date=end_date)


def _send_trip_email(template, recipient, variables, *, what):
    """Render ``template`` and hand it to the email service.

    Never raises: an email that cannot be sent must not undo a payment or a
    cancellation that has already gone through Finance.
    """
    if not recipient:
        logger.info("No email address on file; %s not sent", what)
        return False

    try:
        from education_system.systems.university.infrastructure.email.template_utils import render_template
        from education_system.systems.university.infrastructure.email.email_service import send_email
    except Exception as exc:
        logger.warning("Email service unavailable; %s not sent: %s", what, exc)
        return False

    try:
        subject, body = render_template(template, variables)
        if not subject or not body:
            raise ValueError(f"{template} rendered no content")

        send_email(recipient_email=recipient, subject=subject, body=body)
        return True
    except Exception as exc:
        logger.warning("Could not send %s to %s: %s", what, recipient, exc)
        return False


def send_registration_receipt(booking):
    """Email a payment receipt for a paid trip registration.

    ``booking`` is the dict :func:`register_for_trip` assembles.
    """
    balance_line = ''
    if booking.get('balance_after') is not None:
        balance_line = get_text(
            "mobility.trip_management.receipt.balance_line",
            "Remaining student finance account balance: £{balance:.2f}",
        ).format(balance=booking['balance_after'])

    # The renderer does not escape, and it prefers the HTML body — so free
    # text has to be escaped here, as the report dialog does.
    return _send_trip_email(RECEIPT_TEMPLATE, booking.get('email'), {
        'participant_name': html.escape(booking.get('name') or ''),
        'trip_name': html.escape(booking['trip_name']),
        'destination': html.escape(booking['destination']),
        'trip_dates': html.escape(_format_trip_dates(booking['start_date'], booking['end_date'])),
        'registration_reference': html.escape(booking['reference']),
        'amount_paid': f"{booking['amount']:.2f}",
        'payment_method': html.escape(payments.method_label(booking['method'])),
        'payment_reference': html.escape(str(booking.get('payment_reference') or '')),
        'payment_date': booking['paid_at'],
        'balance_line': html.escape(balance_line),
    }, what="trip receipt")


def send_cancellation_receipt(cancellation):
    """Email confirmation of a cancelled registration and its refund.

    ``cancellation`` is the dict :func:`cancel_trip_registration` assembles,
    with the refund outcome merged in.
    """
    if cancellation.get('balance_after') is not None:
        settlement = get_text(
            "mobility.trip_management.refund.credited_line",
            "This has been credited back to your student finance account "
            "(balance: £{balance:.2f}).",
        ).format(balance=cancellation['balance_after'])
    else:
        settlement = get_text(
            "mobility.trip_management.refund.settlement_line",
            "The refund will be returned to your original payment method by the "
            "finance office.",
        )

    return _send_trip_email(CANCELLATION_TEMPLATE, cancellation.get('email'), {
        'participant_name': html.escape(cancellation.get('name') or ''),
        'trip_name': html.escape(cancellation['trip_name']),
        'destination': html.escape(cancellation['destination']),
        'trip_dates': html.escape(_format_trip_dates(cancellation['start_date'],
                                                     cancellation.get('end_date'))),
        'registration_reference': html.escape(cancellation['reference']),
        'refund_amount': f"{cancellation['amount']:.2f}",
        'payment_method': html.escape(payments.method_label(cancellation['method'])),
        'refund_reference': html.escape(str(cancellation.get('refund_reference') or '')),
        'refund_date': cancellation['refunded_at'],
        'settlement_line': html.escape(settlement),
    }, what="trip cancellation receipt")


# ---------------------------------------------------------------------------
# Domain API — the one place a trip place is taken or given up.
#
# Same contract as trips.py: ``auth`` first, PermissionError / ValueError,
# own short write transaction (``BEGIN IMMEDIATE``, so the capacity check and
# the insert cannot be raced) unless ``conn=`` is given, events and e-mails
# after the commit.
# ---------------------------------------------------------------------------

class TripFullError(ValueError):
    """The trip has no free place (wave 2's waitlist joins people instead)."""


def _db():
    from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management import database
    return database


def _trips():
    from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management import trips
    return trips


def _now():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def _placeholders(values):
    return ", ".join('?' * len(values))


# Details a participant (or staff on their behalf) may record. The health
# columns (medical_info, dietary_requirements, accessibility_needs) are
# special-category data: sealed on write here (``medical.seal_details``) and
# read only through ``medical`` (audited).
PARTICIPANT_DETAIL_FIELDS = (
    'emergency_contact', 'emergency_contact_name', 'emergency_contact_phone',
    'emergency_contact_relationship', 'medical_info', 'dietary_requirements',
    'accessibility_needs', 'passport_expiry', 'visa_status',
)


def _contact_for(conn, user_id, student_id):
    """``(name, email)`` for a participant, from the students row if there is one."""
    name = email = None
    if user_id is not None:
        row = conn.execute("SELECT first_name, last_name, email FROM users WHERE id = ?",
                           (user_id,)).fetchone()
        if row:
            name = " ".join(p for p in (row[0], row[1]) if p).strip() or None
            email = row[2]
    if student_id:
        row = conn.execute("SELECT first_name, last_name, email_address FROM students "
                           "WHERE student_id = ?", (student_id,)).fetchone()
        if row:
            name = " ".join(p for p in (row[0], row[1]) if p).strip() or name
            email = row[2] or email
    return name, email


def resolve_participant(conn, *, student_id=None, user_id=None, username=None):
    """``(user_id, student_id)`` in the university database for a participant.

    ``student_id`` is a student number (they can be all digits — never read
    one as ``users.id``); ``user_id`` is ``users.id``; ``username`` a login
    name. Raises ValueError when nobody matches.
    """
    if student_id not in (None, ''):
        sid = str(student_id).strip()
        row = conn.execute("SELECT id, student_id FROM users WHERE student_id = ? LIMIT 1",
                           (sid,)).fetchone()
        if row:
            return row[0], row[1]
        if conn.execute("SELECT 1 FROM students WHERE student_id = ?", (sid,)).fetchone():
            return None, sid
        raise ValueError(f"no student {sid}")
    if user_id not in (None, ''):
        row = conn.execute("SELECT id, student_id FROM users WHERE id = ?",
                           (int(user_id),)).fetchone()
        if row:
            return row[0], row[1]
        raise ValueError(f"no user {user_id}")
    if username:
        row = conn.execute("SELECT id, student_id FROM users WHERE username = ? COLLATE NOCASE",
                           (str(username),)).fetchone()
        if row:
            return row[0], row[1]
        raise ValueError(f"no user {username}")
    raise ValueError("a participant (student, user or username) is required")


def _find_place(conn, trip_id, user_id, student_id):
    """The participant row for this person on this trip, newest first."""
    if student_id:
        cur = conn.execute("SELECT * FROM trip_participants WHERE trip_id = ? AND student_id = ? "
                           "ORDER BY id DESC LIMIT 1", (trip_id, student_id))
    else:
        cur = conn.execute("SELECT * FROM trip_participants WHERE trip_id = ? AND user_id = ? "
                           "ORDER BY id DESC LIMIT 1", (trip_id, user_id))
    row = cur.fetchone()
    return dict(zip([d[0] for d in cur.description], row)) if row else None


def get_participant(participant_id, conn=None):
    with _db().read_connection(conn) as c:
        cur = c.execute("SELECT * FROM trip_participants WHERE id = ?", (participant_id,))
        row = cur.fetchone()
        return dict(zip([d[0] for d in cur.description], row)) if row else None


def _is_own(who, place):
    return ((who['user_id'] is not None and place.get('user_id') == who['user_id'])
            or (who['student_id'] and place.get('student_id') == who['student_id']))


def _may_manage_people(auth, trip, conn, who):
    return (auth.check_permission('manage_trip_participants')
            or _trips().can_manage_trip(auth, trip, conn=conn, who=who))


def _set_trip_full_flag(conn, trip, who):
    """Keep 'open' / 'full' in step with the number of places taken."""
    return _trips().refresh_capacity_status(conn, trip, who)


def _note_age(c, trip_id, student_id):
    """Flag the trip as involving minors when this student is under 18
    (``safeguarding.note_participant_age``; skipped if that is unavailable)."""
    if not student_id:
        return False
    try:
        from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management import safeguarding
    except ImportError:
        return False
    return bool(safeguarding.note_participant_age(c, trip_id, student_id))


def register(auth, trip_id, *, student_id=None, user_id=None, payment_method=None,
             source=None, waitlist=False, conn=None, pending=None, **details):
    """Take a place on an open trip. Returns the booking dict.

    With ``waitlist=True`` (``waitlist.join_or_waitlist``) a full trip puts
    the person on its waiting list instead of raising: the booking then has
    ``status`` 'waitlisted' and ``position``, and no payment is due yet.
    Medical, dietary and accessibility details are sealed before they are
    written; the free-text ``emergency_contact`` is filled from the
    structured name / relationship / phone when not given.

    Without ``student_id`` / ``user_id`` the signed-in user registers
    themselves (``register_for_trips``); naming someone else needs
    ``manage_trip_participants`` or the right to manage that trip. A
    previous cancelled or removed registration is re-used, so people can
    re-register. Refuses with an active finance hold, when already on the
    trip, and raises :class:`TripFullError` when every place is taken.
    Taking the payment is the caller's next step (it posts to Finance in its
    own transaction).
    """
    trips = _trips()
    db = _db()
    who = trips.actor(auth)
    unknown = set(details) - set(PARTICIPANT_DETAIL_FIELDS)
    if unknown:
        raise ValueError(f"unknown participant field(s): {', '.join(sorted(unknown))}")
    from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management import medical
    details = medical.seal_details(medical.fill_contact_text(
        {k: (v.strip() or None) if isinstance(v, str) else v for k, v in details.items()}))
    for_self = student_id in (None, '') and user_id in (None, '')
    if for_self and not auth.check_permission('register_for_trips'):
        raise PermissionError(get_text("mobility.trip_management.auth.no_permission_register",
                                       "You don't have permission to register for trips."))
    if not for_self and not (auth.check_permission('manage_trip_participants')
                             or auth.check_permission('manage_trips')
                             or auth.check_permission('create_trips')):
        raise PermissionError(get_text("mobility.trip_management.auth.no_permission_manage_participants",
                                       "You don't have permission to manage participants."))

    # Resolve who is going and check finance holds before any write lock.
    with db.read_connection(conn) as c:
        if for_self:
            if who['user_id'] is None and not who['student_id']:
                raise ValueError("your login has no university record, so it cannot hold a trip place")
            p_user, p_student = who['user_id'], who['student_id']
        else:
            p_user, p_student = resolve_participant(c, student_id=student_id, user_id=user_id)
        name, email = _contact_for(c, p_user, p_student)
    holds = payments.active_holds(p_student)
    if holds:
        raise ValueError(get_text("mobility.trip_management.payment.hold_blocked",
                                  "\nYou have an active finance hold, so you cannot register for trips:")
                         .strip() + " " + "; ".join(line.strip() for line in payments.describe_holds(holds)))

    def work(c, p):
        trip = trips.get_trip(trip_id, conn=c)
        if not trip:
            raise ValueError(get_text("mobility.trip_management.trips.trip_not_found", "Trip not found."))
        if not for_self and not _may_manage_people(auth, trip, c, who):
            raise PermissionError(get_text("mobility.trip_management.auth.no_permission_manage_participants",
                                           "You don't have permission to manage participants."))
        # A 'full' trip falls through to the capacity check (TripFullError,
        # or the waiting list).
        if trip['status'] not in ('open', 'full'):
            raise ValueError(get_text("mobility.trip_management.registration.not_open",
                                      "This trip is not taking registrations ({status}).")
                             .format(status=trip['status']))
        existing = _find_place(c, trip_id, p_user, p_student)
        if existing and existing['status'] in db.CURRENT_PARTICIPANT_STATUSES:
            raise ValueError(get_text("mobility.trip_management.registration.already_registered",
                                      "You are already registered for this trip."))
        full = trips.active_participant_count(c, trip_id) >= (trip['max_participants'] or 0)
        if full and not waitlist:
            raise TripFullError(get_text("mobility.trip_management.registration.full", "Trip is full."))

        cost = float(trip['cost'] or 0)
        now = _now()
        position = None
        if full:
            from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management import waitlist as _waitlist
            position = _waitlist.next_position(c, trip_id)
        row = {name_: details.get(name_) for name_ in PARTICIPANT_DETAIL_FIELDS}
        row.update(trip_id=trip_id, student_id=p_student, user_id=p_user, registration_date=now,
                   status='waitlisted' if full else 'registered',
                   payment_status='paid' if cost <= 0 else 'pending',
                   payment_method=payment_method, payment_reference=None,
                   cancellation_date=None, cancellation_reason=None, waitlist_position=position,
                   waitlisted_at=now if full else None, offer_expires_at=None, amount_paid=0,
                   amount_refunded=0, hardship_award=0,
                   source=source or trip.get('source') or 'operations')
        if existing:
            participant_id = existing['id']
            c.execute(f"UPDATE trip_participants SET {', '.join(k + ' = ?' for k in row)} WHERE id = ?",
                      [*row.values(), participant_id])
        else:
            cols = list(row)
            participant_id = c.execute(
                f"INSERT INTO trip_participants ({', '.join(cols)}) VALUES ({_placeholders(cols)})",
                [row[k] for k in cols]).lastrowid
        _note_age(c, trip_id, p_student)
        _set_trip_full_flag(c, trip, who)
        trips._publish_after(p, "trip.registration.changed", registration_id=participant_id,
                             trip_id=trip_id, student_id=p_student, user_id=p_user,
                             action="waitlisted" if full else "registered", fee=cost)
        return {
            'participant_id': participant_id,
            'status': row['status'],
            'position': position,
            'reference': f"TRIP-{trip_id}-{participant_id}",
            'trip_id': trip_id,
            'trip_name': trip['trip_name'],
            'destination': trip['destination'],
            'start_date': trip['start_date'],
            'end_date': trip['end_date'],
            'amount': cost,
            'method': payment_method,
            'student_id': p_student,
            'user_id': p_user,
            'name': name or who['username'],
            'email': email,
            'registered_at': now,
        }

    return trips._in_transaction(conn, pending, work)


def _end_place(auth, participant_id, new_status, reason, *, refund, refund_amount,
               conn, pending):
    trips = _trips()
    db = _db()
    who = trips.actor(auth)
    holder = {}

    def work(c, p):
        place = get_participant(participant_id, conn=c)
        if not place:
            raise ValueError(get_text("mobility.trip_management.participants.not_found",
                                      "Participant not found."))
        trip = trips.get_trip(place['trip_id'], conn=c)
        own = _is_own(who, place)
        if new_status == 'cancelled' and own:
            if not auth.check_permission('cancel_trip_registration'):
                raise PermissionError(get_text("mobility.trip_management.auth.no_permission_cancel",
                                               "You don't have permission to cancel registrations."))
        elif not _may_manage_people(auth, trip, c, who):
            raise PermissionError(get_text("mobility.trip_management.auth.no_permission_manage_participants",
                                           "You don't have permission to manage participants."))
        if place['status'] not in db.CURRENT_PARTICIPANT_STATUSES:
            raise ValueError(f"this registration is already {place['status']}")
        if trip['status'] in ('completed', 'archived'):
            raise ValueError(f"the trip is {trip['status']}")
        c.execute("UPDATE trip_participants SET status = ?, cancellation_date = ?, "
                  "cancellation_reason = ?, offer_expires_at = NULL, waitlist_position = NULL "
                  "WHERE id = ?", (new_status, _now(), reason or None, participant_id))
        _set_trip_full_flag(c, trip, who)
        amount = refund_amount
        if amount is None and new_status == 'cancelled':
            # The participant gave the place up: the trip's refund tiers apply.
            from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management import money
            due = money.refund_due_for(place, trip)
            amount = due['amount']
            holder['refund_due'] = due
        holder.update(place=place, trip=trip)
        trips._publish_after(p, "trip.registration.changed", registration_id=participant_id,
                             trip_id=trip['id'], student_id=place.get('student_id'),
                             user_id=place.get('user_id'), action=new_status, reason=reason)
        if refund and place.get('payment_status') in ('paid', 'partial'):
            p.append(lambda: holder.update(refund=refund_participant(
                place, trip, processed_by=who['username'], amount=amount)))
        if place['status'] in db.ACTIVE_PARTICIPANT_STATUSES:
            p.append(lambda: _offer_freed_place(trip['id']))
        return participant_id

    trips._in_transaction(conn, pending, work)
    place = holder.get('place') or {}
    return {'participant_id': participant_id, 'trip_id': place.get('trip_id'),
            'status': new_status, 'refund': holder.get('refund'),
            'refund_due': holder.get('refund_due')}


def _offer_freed_place(trip_id):
    """After commit: offer a freed place to the waiting list."""
    from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management import waitlist
    waitlist.on_place_freed(trip_id)


def cancel_registration(auth, participant_id, reason="", *, refund=True, refund_amount=None,
                        conn=None, pending=None):
    """Cancel a registration (the participant's own, or as a trip organiser).

    The row is kept with status 'cancelled', ``cancellation_date`` and
    ``cancellation_reason``. A paid place is refunded through
    ``payments.refund_payment`` after the commit — by the trip's refund
    tiers (``money.refund_due_for``; the deposit is kept) unless
    ``refund_amount`` says otherwise — and a freed place is offered to the
    waiting list. Returns ``{'participant_id', 'trip_id', 'status',
    'refund', 'refund_due'}``; ``refund`` is the finance outcome
    (``success`` False with ``message`` when it failed).
    """
    return _end_place(auth, participant_id, 'cancelled', reason, refund=refund,
                      refund_amount=refund_amount, conn=conn, pending=pending)


def remove_participant_record(auth, participant_id, reason="", *, refund=True, conn=None,
                              pending=None):
    """Take someone off a trip as an organiser: status 'removed', row kept."""
    return _end_place(auth, participant_id, 'removed', reason, refund=refund,
                      refund_amount=None, conn=conn, pending=pending)


def set_participant_status(auth, participant_id, status, reason="", *, conn=None, pending=None):
    """Organiser change of a participant's status.

    'cancelled' / 'removed' go through :func:`cancel_registration` /
    :func:`remove_participant_record` (refunds). Moving someone back onto
    a place is capacity-checked in the same transaction.
    """
    db = _db()
    status = db.LEGACY_PARTICIPANT_STATUSES.get(status, status)
    if status not in db.PARTICIPANT_STATUSES:
        raise ValueError(f"unknown participant status {status!r}")
    if status == 'cancelled':
        return cancel_registration(auth, participant_id, reason, conn=conn, pending=pending)
    if status == 'removed':
        return remove_participant_record(auth, participant_id, reason, conn=conn, pending=pending)
    trips = _trips()
    who = trips.actor(auth)

    def work(c, p):
        place = get_participant(participant_id, conn=c)
        if not place:
            raise ValueError(get_text("mobility.trip_management.participants.not_found",
                                      "Participant not found."))
        trip = trips.get_trip(place['trip_id'], conn=c)
        if not _may_manage_people(auth, trip, c, who):
            raise PermissionError(get_text("mobility.trip_management.auth.no_permission_manage_participants",
                                           "You don't have permission to manage participants."))
        if place['status'] == status:
            return place
        takes_place = (status in db.ACTIVE_PARTICIPANT_STATUSES
                       and place['status'] not in db.ACTIVE_PARTICIPANT_STATUSES)
        if takes_place and trips.active_participant_count(c, trip['id']) >= (trip['max_participants'] or 0):
            raise TripFullError(get_text("mobility.trip_management.registration.full", "Trip is full."))
        extra = (", waitlisted_at = COALESCE(waitlisted_at, ?), waitlist_position = ?"
                 if status == 'waitlisted' else "")
        if extra:
            from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management import waitlist as _waitlist
            params = [status, _now(), _waitlist.next_position(c, trip['id']), participant_id]
        else:
            params = [status, participant_id]
        c.execute(f"UPDATE trip_participants SET status = ?{extra} WHERE id = ?", params)
        _set_trip_full_flag(c, trip, who)
        if (place['status'] in db.ACTIVE_PARTICIPANT_STATUSES
                and status not in db.ACTIVE_PARTICIPANT_STATUSES):
            p.append(lambda: _offer_freed_place(trip['id']))
        trips._publish_after(p, "trip.registration.changed", registration_id=participant_id,
                             trip_id=trip['id'], student_id=place.get('student_id'),
                             user_id=place.get('user_id'), action=status, reason=reason)
        return get_participant(participant_id, conn=c)

    return trips._in_transaction(conn, pending, work)


def set_payment_status(auth, participant_id, payment_status, *, amount_paid=None,
                       payment_method=None, payment_reference=None, conn=None, pending=None):
    """Organiser record of a payment taken outside the booking flow."""
    db = _db()
    if payment_status not in db.PAYMENT_STATUSES:
        raise ValueError(f"unknown payment status {payment_status!r}")
    trips = _trips()
    who = trips.actor(auth)

    def work(c, p):
        place = get_participant(participant_id, conn=c)
        if not place:
            raise ValueError(get_text("mobility.trip_management.participants.not_found",
                                      "Participant not found."))
        trip = trips.get_trip(place['trip_id'], conn=c)
        if not _may_manage_people(auth, trip, c, who):
            raise PermissionError(get_text("mobility.trip_management.auth.no_permission_manage_participants",
                                           "You don't have permission to manage participants."))
        sets, params = ["payment_status = ?"], [payment_status]
        if amount_paid is not None:
            if float(amount_paid) < 0:
                raise ValueError("amount_paid cannot be negative")
            sets.append("amount_paid = ?")
            params.append(round(float(amount_paid), 2))
        elif payment_status == 'paid' and not place.get('amount_paid'):
            sets.append("amount_paid = ?")
            params.append(float(trip['cost'] or 0))
        if payment_method is not None:
            sets.append("payment_method = ?")
            params.append(payment_method)
        if payment_reference is not None:
            sets.append("payment_reference = ?")
            params.append(payment_reference)
        c.execute(f"UPDATE trip_participants SET {', '.join(sets)} WHERE id = ?",
                  [*params, participant_id])
        trips._publish_after(p, "trip.registration.changed", registration_id=participant_id,
                             trip_id=trip['id'], action="payment", payment_status=payment_status)
        return get_participant(participant_id, conn=c)

    return trips._in_transaction(conn, pending, work)


def refund_participant(place, trip, *, processed_by=None, amount=None):
    """Refund what a participant paid, through Finance, then e-mail them.

    Call it after the cancellation has committed (Finance runs its own
    transactions). ``amount`` defaults to what was paid and not yet
    refunded. Returns the finance outcome plus ``participant_id`` and
    ``amount``; a failure is returned (``success`` False, ``message``) and
    logged, never swallowed.
    """
    paid = float(place.get('amount_paid') or 0)
    if not paid and place.get('payment_status') == 'paid':
        paid = float(trip.get('cost') or 0)   # paid before amount_paid was tracked
    due = paid - float(place.get('amount_refunded') or 0)
    if amount is not None:
        due = min(float(amount), due)
    outcome = {'participant_id': place['id'], 'amount': round(max(due, 0), 2)}
    if due <= 0:
        outcome.update(success=place.get('payment_status') != 'partial', skipped=True,
                       message='' if place.get('payment_status') != 'partial'
                       else 'part payment of unknown amount: refund by hand')
        return outcome

    result = payments.refund_payment(
        method=place.get('payment_method'), amount=outcome['amount'],
        student_id=place.get('student_id'), trip_id=trip['id'], trip_name=trip['trip_name'],
        payment_reference=place.get('payment_reference'), processed_by=processed_by)
    outcome.update(result)
    if not result.get('success'):
        logger.error("Trip refund failed for registration %s: %s", place['id'], result.get('message'))
        return outcome

    refunded_all = due >= paid - float(place.get('amount_refunded') or 0)
    try:
        with _db().write_transaction() as c:
            c.execute("UPDATE trip_participants SET amount_refunded = COALESCE(amount_refunded, 0) + ?, "
                      "payment_status = CASE WHEN ? THEN 'refunded' ELSE payment_status END "
                      "WHERE id = ?", (outcome['amount'], 1 if refunded_all else 0, place['id']))
    except sqlite3.Error as exc:
        # The money moved in Finance; say so rather than reading as unrefunded.
        logger.error("Refund %s raised but registration %s not updated: %s",
                     result.get('reference'), place['id'], exc)
        outcome['message'] = f"refund raised but the registration was not updated: {exc}"

    with _db().read_connection() as c:
        name, email = _contact_for(c, place.get('user_id'), place.get('student_id'))
    outcome['email_sent'] = send_cancellation_receipt({
        'participant_id': place['id'],
        'reference': f"TRIP-{trip['id']}-{place['id']}",
        'trip_name': trip['trip_name'], 'destination': trip['destination'],
        'start_date': trip['start_date'], 'end_date': trip.get('end_date'),
        'amount': outcome['amount'], 'method': place.get('payment_method'),
        'name': name, 'email': email,
        'refund_reference': result.get('reference'),
        'balance_after': result.get('balance_after'),
        'refunded_at': _now(),
    })
    return outcome


def list_participants(auth, trip_id, *, include_ended=False, conn=None):
    """A trip's participants for its organisers (health fields left out)."""
    trips = _trips()
    who = trips.actor(auth)
    with _db().read_connection(conn) as c:
        trip = trips.get_trip(trip_id, conn=c)
        if not trip:
            raise ValueError(get_text("mobility.trip_management.trips.trip_not_found", "Trip not found."))
        if not _may_manage_people(auth, trip, c, who):
            raise PermissionError(get_text("mobility.trip_management.auth.no_permission_manage_participants",
                                           "You don't have permission to manage participants."))
        sql = ("SELECT tp.id, tp.trip_id, tp.student_id, tp.user_id, tp.registration_date, "
               "tp.status, tp.payment_status, tp.payment_method, tp.amount_paid, tp.amount_refunded, "
               "tp.emergency_contact, tp.emergency_contact_name, tp.emergency_contact_phone, "
               "tp.waitlist_position, tp.offer_expires_at, tp.cancellation_date, tp.cancellation_reason, "
               "tp.source, COALESCE(s.first_name || ' ' || s.last_name, "
               "u.first_name || ' ' || u.last_name, u.username) AS name, "
               "COALESCE(s.email_address, u.email) AS email "
               "FROM trip_participants tp LEFT JOIN students s ON s.student_id = tp.student_id "
               "LEFT JOIN users u ON u.id = tp.user_id WHERE tp.trip_id = ?")
        params = [trip_id]
        if not include_ended:
            statuses = _db().CURRENT_PARTICIPANT_STATUSES
            sql += f" AND tp.status IN ({_placeholders(statuses)})"
            params.extend(statuses)
        sql += " ORDER BY tp.registration_date, tp.id"
        cur = c.execute(sql, params)
        names = [d[0] for d in cur.description]
        return [dict(zip(names, r)) for r in cur.fetchall()]


def list_my_registrations(auth, conn=None):
    """The signed-in user's trip registrations, soonest trip first."""
    who = _trips().actor(auth)
    with _db().read_connection(conn) as c:
        cur = c.execute(
            "SELECT tp.id AS participant_id, t.id AS trip_id, t.trip_name, t.destination, "
            "t.start_date, t.end_date, t.cost, t.status AS trip_status, tp.registration_date, "
            "tp.payment_status, tp.status, tp.payment_method, tp.payment_reference, tp.student_id "
            "FROM trip_participants tp JOIN trips t ON tp.trip_id = t.id "
            "WHERE (tp.user_id IS NOT NULL AND tp.user_id = ?) "
            "   OR (tp.student_id IS NOT NULL AND tp.student_id = ?) "
            "ORDER BY t.start_date ASC", (who['user_id'], who['student_id']))
        names = [d[0] for d in cur.description]
        return [dict(zip(names, r)) for r in cur.fetchall()]


# ---------------------------------------------------------------------------
# CLI — input first, then one short write through the domain API.
# ---------------------------------------------------------------------------

def _cli_auth(key, default):
    auth = _common.get_auth()
    if not auth or not auth.current_user:
        print(get_text(key, default))
        return None
    return auth


def _active_sql():
    return ", ".join(f"'{s}'" for s in _db().ACTIVE_PARTICIPANT_STATUSES)


@log_create(module="trips", description="Registering for trip")
def register_for_trip():
    """Register current user for a trip"""
    auth = _cli_auth("mobility.trip_management.auth.must_login_register", "You must be logged in to register for trips.")
    if not auth:
        return False

    if not auth.check_permission('register_for_trips'):
        print(get_text("mobility.trip_management.auth.no_permission_register", "You don't have permission to register for trips."))
        return False

    who = _trips().actor(auth)

    # Finance hold gate — the same check register() applies. Refuse before
    # the user picks a trip and types in their details.
    holds = payments.active_holds(who['student_id'])
    if holds:
        print(get_text(
            "mobility.trip_management.payment.hold_blocked",
            "\nYou have an active finance hold, so you cannot register for trips:",
        ))
        for line in payments.describe_holds(holds):
            print(line)
        print(get_text(
            "mobility.trip_management.payment.hold_advice",
            "Settle the outstanding charges with the finance office, then try again.",
        ))
        return False

    with _db().read_connection() as conn:
        available_trips = [tuple(r) for r in conn.execute(f'''
        SELECT t.id, t.trip_name, t.destination, t.start_date, t.end_date,
               t.max_participants, t.cost, t.status,
               (SELECT COUNT(*) FROM trip_participants tp WHERE tp.trip_id = t.id
                AND tp.status IN ({_active_sql()})) AS current_participants
        FROM trips t
        WHERE t.status IN ('open', 'full')
        ORDER BY t.start_date ASC
        ''').fetchall()]

    if not available_trips:
        print(get_text("mobility.trip_management.registration.no_trips_available", "No trips available for registration."))
        return False

    print("\n" + get_text("mobility.trip_management.registration.available_trips", "Available Trips:"))
    print("=" * 100)
    print(f"{get_text('mobility.trip_management.headers.id', 'ID'):<5} {get_text('mobility.trip_management.headers.name', 'Name'):<25} {get_text('mobility.trip_management.headers.destination', 'Destination'):<20} {get_text('mobility.trip_management.headers.start_date', 'Start Date'):<12} {get_text('mobility.trip_management.headers.cost', 'Cost'):<10} {get_text('mobility.trip_management.headers.spaces_left', 'Spaces Left'):<12}")
    print("-" * 100)
    for trip in available_trips:
        spaces_left = max(trip[5] - trip[8], 0)  # max_participants - current_participants
        spaces = spaces_left if spaces_left else get_text("mobility.trip_management.registration.waiting_list", "Waiting list")
        print(f"{trip[0]:<5} {trip[1][:24]:<25} {trip[2][:19]:<20} {trip[3]:<12} £{trip[6] or 0:<9.2f} {spaces:<12}")
    print("=" * 100)

    while True:
        try:
            trip_id = int(input(get_text("mobility.trip_management.registration.enter_trip_id", "\nEnter Trip ID to register for: ")))
        except ValueError:
            print(get_text("mobility.trip_management.validation.enter_valid_trip_id", "Please enter a valid trip ID."))
            continue
        selected_trip = next((t for t in available_trips if t[0] == trip_id), None)
        if selected_trip:
            break
        print(get_text("mobility.trip_management.registration.invalid_trip_id", "Invalid trip ID or trip not available."))

    print(get_text("mobility.trip_management.registration.registering_for", "\nRegistering for: {trip_name}").format(trip_name=selected_trip[1]))
    cost = float(selected_trip[6] or 0)
    print(get_text("mobility.trip_management.registration.cost_display", "Cost: £{cost:.2f}").format(cost=cost))

    full = selected_trip[8] >= selected_trip[5]
    if full:
        print(get_text("mobility.trip_management.registration.joining_waitlist",
                       "This trip is full. You will join the waiting list and be e-mailed if a place comes up."))

    details = {
        'emergency_contact_name': input(get_text("mobility.trip_management.registration.emergency_name_prompt", "Emergency contact name: ")).strip(),
        'emergency_contact_relationship': input(get_text("mobility.trip_management.registration.emergency_relationship_prompt", "Their relationship to you: ")).strip(),
        'emergency_contact_phone': input(get_text("mobility.trip_management.registration.emergency_phone_prompt", "Their phone number: ")).strip(),
        'medical_info': input(get_text("mobility.trip_management.registration.medical_info_prompt", "Medical Information (optional): ")).strip(),
        'dietary_requirements': input(get_text("mobility.trip_management.registration.dietary_prompt", "Dietary Requirements (optional): ")).strip(),
        'accessibility_needs': input(get_text("mobility.trip_management.registration.accessibility_prompt", "Accessibility needs (optional): ")).strip(),
    }

    # Choose how to pay before anything is written. The payment itself is
    # taken after the registration commits, because Finance manages its own
    # transactions. Nothing is taken for a waiting-list place.
    method = None
    if cost > 0 and not full:
        balance = payments.account_balance(who['student_id']) if who['student_id'] else None
        method = payments.select_payment_method(cost, balance=balance)
        if method is None:
            print(get_text("mobility.trip_management.registration.cancelled", "\nRegistration cancelled — no payment method chosen."))
            return False

    try:
        booking = register(auth, trip_id, payment_method=method, waitlist=True,
                           **{k: (v or None) for k, v in details.items()})
    except (ValueError, PermissionError) as e:
        print(str(e))
        return False
    except sqlite3.Error as e:
        logger.error("register_for_trip failed: %s", e)
        print(get_text("mobility.trip_management.errors.registering", "Registration failed: {error}").format(error=e))
        return False

    if booking.get('status') == 'waitlisted':
        print(get_text("mobility.trip_management.registration.waitlisted",
                       "\nYou are on the waiting list for '{trip_name}' (position {position}). "
                       "If a place comes up it will be offered to you by e-mail, and you will "
                       "have 48 hours to accept it under My Registrations.").format(
            trip_name=booking['trip_name'], position=booking.get('position')))
        return True

    print(get_text("mobility.trip_management.registration.success", "\nSuccessfully registered for '{trip_name}'!").format(trip_name=booking['trip_name']))
    try:
        from education_system.systems.university.domains.operations.domain.campus.mobility.services import trip_management as _tm
        _tm.log_activity('create', 'trip_registration')
    except Exception:
        logger.debug("Suppressed exception", exc_info=True)

    if not booking['amount']:
        print(get_text("mobility.trip_management.registration.no_payment_required", "No payment is required for this trip."))
        print(get_text("mobility.trip_management.registration.further_info", "\nYou will receive further information about the trip."))
        return True

    return _settle_trip_payment(booking, processed_by=who['username'])


def _resolve_payer(cursor, current_user):
    """Return ``(student_id, display_name, email)`` for the logged-in user.

    Resolved by username: ``current_user['id']`` may be the shared auth.db
    id, which is not a ``users.id`` in the university database.
    """
    student_id = name = email = None
    try:
        row = cursor.execute('SELECT id, student_id FROM users WHERE username = ?',
                             (current_user.get('username'),)).fetchone()
        if row:
            student_id = row[1]
            name, email = _contact_for(cursor.connection if hasattr(cursor, 'connection') else cursor,
                                       row[0], student_id)
    except sqlite3.Error as e:
        logger.warning("Could not resolve user %s: %s", current_user.get('username'), e)
    return student_id, name or current_user.get('username'), email


def _settle_trip_payment(booking, *, processed_by=None):
    """Take payment for a committed registration, then email the receipt.

    Re-prompts for another method while payment keeps failing. Backing out
    leaves the registration in place with payment outstanding, which is a
    state staff can settle from Manage Participants.
    """
    method = booking['method']
    amount = booking['amount']

    while True:
        outcome = payments.take_payment(
            method=method, amount=amount,
            student_id=booking['student_id'],
            trip_id=booking['trip_id'], trip_name=booking['trip_name'],
            processed_by=processed_by,
        )

        if outcome['success']:
            break

        print("\n" + (outcome['message'] or get_text(
            "mobility.trip_management.payment.declined", "The payment was declined.")))
        balance = payments.account_balance(booking['student_id']) if booking['student_id'] else None
        method = payments.select_payment_method(amount, balance=balance)
        if method is None:
            print(get_text(
                "mobility.trip_management.payment.outstanding",
                "\nYour place is held but payment is still outstanding. "
                "Payment Status: Pending",
            ))
            return True

    booking['method'] = method
    booking['payment_reference'] = outcome.get('reference')
    booking['balance_after'] = outcome.get('balance_after')
    booking['paid_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    _mark_registration_paid(booking)

    print(get_text(
        "mobility.trip_management.payment.taken",
        "Payment of £{amount:.2f} received by {method}.",
    ).format(amount=amount, method=payments.method_label(method)))
    if booking['balance_after'] is not None:
        print(get_text(
            "mobility.trip_management.payment.remaining_balance",
            "Remaining student finance account balance: £{balance:.2f}",
        ).format(balance=booking['balance_after']))

    if send_registration_receipt(booking):
        print(get_text(
            "mobility.trip_management.receipt.sent",
            "A receipt has been emailed to {email}.",
        ).format(email=booking['email']))

    return True


def _mark_registration_paid(booking):
    """Flip the registration to paid once Finance has the money."""
    def mark_paid_operation(conn):
        conn.execute(
            "UPDATE trip_participants "
            "SET payment_status = 'paid', payment_method = ?, payment_reference = ?, "
            "    amount_paid = COALESCE(amount_paid, 0) + ? "
            "WHERE id = ?",
            (booking['method'], booking.get('payment_reference'),
             float(booking.get('amount') or 0), booking['participant_id']),
        )
        return True

    if not _run_db_operation(mark_paid_operation):
        # The money is in Finance either way; surface the mismatch rather
        # than letting the registration silently read as unpaid.
        logger.error("Trip payment %s taken but registration %s not marked paid",
                     booking.get('payment_reference'), booking['participant_id'])
        print(get_text(
            "mobility.trip_management.payment.status_not_updated",
            "Payment was taken (reference {reference}) but the registration could not "
            "be marked as paid. Please contact the trips office.",
        ).format(reference=booking.get('payment_reference')))

@log_read(module="trips", description="Viewing own trip registrations")
def view_my_trip_registrations():
    """View current user's trip registrations"""
    auth = _cli_auth("mobility.trip_management.auth.must_login_view_registrations", "You must be logged in to view your registrations.")
    if not auth:
        return False

    if not auth.check_permission('view_own_trip_registrations'):
        print(get_text("mobility.trip_management.auth.no_permission_view_registrations", "You don't have permission to view trip registrations."))
        return False

    registrations = list_my_registrations(auth)
    if not registrations:
        print(get_text("mobility.trip_management.my_registrations.no_registrations", "You are not registered for any trips."))
        return True

    print("\n" + get_text("mobility.trip_management.my_registrations.title", "Your Trip Registrations:"))
    print("=" * 100)
    print(f"{get_text('mobility.trip_management.headers.trip_id', 'Trip ID'):<8} {get_text('mobility.trip_management.headers.name', 'Name'):<25} {get_text('mobility.trip_management.headers.destination', 'Destination'):<20} {get_text('mobility.trip_management.headers.start_date', 'Start Date'):<12} {get_text('mobility.trip_management.headers.cost', 'Cost'):<10} {get_text('mobility.trip_management.headers.payment', 'Payment'):<10} {get_text('mobility.trip_management.headers.status', 'Status'):<10}")
    print("-" * 100)
    for reg in registrations:
        print(f"{reg['trip_id']:<8} {reg['trip_name'][:24]:<25} {(reg['destination'] or '')[:19]:<20} {reg['start_date']:<12} £{reg['cost'] or 0:<9.2f} {(reg['payment_status'] or '').title():<10} {(reg['status'] or '').title():<10}")
    print("=" * 100)
    return True


def _load_trip_participants(trip_id):
    """Rows in the shape the participant menu prints (id, student_id, payment,
    status, registration date, emergency contact, name, email)."""
    with _db().read_connection() as conn:
        return [tuple(r) for r in conn.execute('''
        SELECT tp.id, tp.student_id, tp.payment_status, tp.status,
               tp.registration_date, tp.emergency_contact,
               COALESCE(s.first_name || ' ' || s.last_name,
                        u.first_name || ' ' || u.last_name) AS student_name,
               COALESCE(s.email_address, u.email) AS email
        FROM trip_participants tp
        LEFT JOIN students s ON tp.student_id = s.student_id
        LEFT JOIN users u ON tp.user_id = u.id
        WHERE tp.trip_id = ?
        ORDER BY tp.registration_date
        ''', (trip_id,)).fetchall()]


@log_update(module="trips", description="Managing trip participants")
def manage_trip_participants():
    """Manage participants for trips (staff/admin only)"""
    auth = _cli_auth("mobility.trip_management.auth.must_login_manage_participants", "You must be logged in to manage trip participants.")
    if not auth:
        return False

    if not auth.check_permission('manage_trip_participants'):
        print(get_text("mobility.trip_management.auth.no_permission_manage_participants", "You don't have permission to manage trip participants."))
        return False

    with _db().read_connection() as conn:
        trips = [tuple(r) for r in conn.execute(f'''
        SELECT t.id, t.trip_name, t.destination, t.start_date,
               (SELECT COUNT(*) FROM trip_participants tp WHERE tp.trip_id = t.id
                AND tp.status IN ({_active_sql()})) AS participant_count
        FROM trips t
        WHERE t.status <> 'archived'
        ORDER BY t.start_date DESC
        ''').fetchall()]

    if not trips:
        print(get_text("mobility.trip_management.trips.no_trips_found", "No trips found."))
        return False

    print("\n" + get_text("mobility.trip_management.participants.trips_with_participants", "Trips with Participants:"))
    print("=" * 80)
    print(f"{get_text('mobility.trip_management.headers.id', 'ID'):<5} {get_text('mobility.trip_management.headers.name', 'Name'):<30} {get_text('mobility.trip_management.headers.destination', 'Destination'):<20} {get_text('mobility.trip_management.headers.start_date', 'Start Date'):<12} {get_text('mobility.trip_management.headers.participants', 'Participants'):<12}")
    print("-" * 80)
    for trip in trips:
        print(f"{trip[0]:<5} {trip[1][:29]:<30} {trip[2][:19]:<20} {trip[3]:<12} {trip[4]:<12}")
    print("=" * 80)

    trip_names = {t[0]: t[1] for t in trips}
    while True:
        try:
            choice = input(get_text("mobility.trip_management.participants.enter_trip_id_manage", "\nEnter Trip ID to manage participants (blank to return to the menu): ")).strip()
            # Pressing Enter on its own is the way out.
            if not choice:
                break
            trip_id = int(choice)
            if trip_id == 0:
                break
            if trip_id not in trip_names:
                print(get_text("mobility.trip_management.trips.trip_not_found", "Trip not found."))
                continue
            trip_name = trip_names[trip_id]

            participants = _load_trip_participants(trip_id)

            print(get_text("mobility.trip_management.participants.for_trip", "\nParticipants for '{trip_name}':").format(trip_name=trip_name))
            print("=" * 120)
            print(f"{get_text('mobility.trip_management.headers.id', 'ID'):<5} {get_text('mobility.trip_management.headers.name', 'Name'):<25} {get_text('mobility.trip_management.headers.email', 'Email'):<25} {get_text('mobility.trip_management.headers.payment', 'Payment'):<10} {get_text('mobility.trip_management.headers.status', 'Status'):<10} {get_text('mobility.trip_management.headers.registration', 'Registration'):<12} {get_text('mobility.trip_management.headers.emergency', 'Emergency'):<20}")
            print("-" * 120)
            for participant in participants:
                p_id, student_id, payment, status, reg_date, emergency, name, email = participant
                name = name if name else get_text("mobility.trip_management.participants.student_id", "Student {student_id}").format(student_id=student_id)
                email = email if email else get_text("mobility.trip_management.common.na", "N/A")
                emergency = emergency[:19] if emergency else get_text("mobility.trip_management.common.na", "N/A")
                print(f"{p_id:<5} {name[:24]:<25} {email[:24]:<25} {(payment or '').title():<10} {(status or '').title():<10} {(reg_date or '')[:10]:<12} {emergency:<20}")
            print("=" * 120)

            if not participants:
                print(get_text("mobility.trip_management.participants.no_participants_trip", "No participants registered for this trip."))
                continue

            print("\n" + get_text("mobility.trip_management.participants.management_options", "Management Options:"))
            print(get_text("mobility.trip_management.participants.option_update_payment", "1. Update payment status"))
            print(get_text("mobility.trip_management.participants.option_update_status", "2. Update participant status"))
            print(get_text("mobility.trip_management.participants.option_remove", "3. Remove participant"))
            print(get_text("mobility.trip_management.participants.option_back", "4. Back to trip selection"))

            choice = input(get_text("mobility.trip_management.common.enter_choice_1_4", "Enter choice (1-4): ")).strip()
            if choice == '1':
                update_payment_status(None, trip_id, participants)
            elif choice == '2':
                update_participant_status(None, trip_id, participants)
            elif choice == '3':
                remove_participant(None, trip_id, participants)
            elif choice == '4':
                continue
            else:
                print(get_text("mobility.trip_management.validation.invalid_choice", "Invalid choice."))

        except ValueError:
            print(get_text("mobility.trip_management.validation.enter_valid_number", "Please enter a valid number."))
        except Exception as e:
            print(get_text("mobility.trip_management.errors.managing_participants", "Error managing participants: {error}").format(error=e))
            logging.error(get_text("mobility.trip_management.errors.in_manage_participants", "Error in manage_trip_participants: {error}").format(error=e))

    return True


def _pick_participant(prompt_key, prompt_default, participants):
    participant_id = int(input(get_text(prompt_key, prompt_default)))
    participant = next((p for p in participants if p[0] == participant_id), None)
    if not participant:
        print(get_text("mobility.trip_management.participants.not_found", "Participant not found."))
    return participant


def update_payment_status(conn, trip_id, participants):
    """Update payment status for a participant (``conn`` is unused; kept for callers)."""
    auth = _common.get_auth()
    try:
        participant = _pick_participant("mobility.trip_management.payment.enter_participant_id", "Enter participant ID to update payment: ", participants)
        if not participant:
            return

        payment_options = list(_db().PAYMENT_STATUSES)
        print("\n" + get_text("mobility.trip_management.payment.status_options", "Payment Status Options:"))
        for i, status in enumerate(payment_options, 1):
            print(f"{i}. {status.title()}")

        choice = int(input(get_text("mobility.trip_management.payment.select_status", "Select new payment status (1-4): "))) - 1
        if not 0 <= choice < len(payment_options):
            print(get_text("mobility.trip_management.validation.invalid_choice", "Invalid choice."))
            return
        new_status = payment_options[choice]
        set_payment_status(auth, participant[0], new_status)
        print(get_text("mobility.trip_management.payment.status_updated", "Payment status updated to '{status}'").format(status=new_status.title()))

    except ValueError as e:
        print(str(e) if str(e) and not str(e).startswith('invalid literal') else
              get_text("mobility.trip_management.validation.enter_valid_number", "Please enter a valid number."))
    except (PermissionError, sqlite3.Error) as e:
        print(get_text("mobility.trip_management.errors.updating_payment", "Error updating payment status: {error}").format(error=e))


def update_participant_status(conn, trip_id, participants):
    """Update status for a participant (``conn`` is unused; kept for callers)."""
    auth = _common.get_auth()
    try:
        participant = _pick_participant("mobility.trip_management.status.enter_participant_id", "Enter participant ID to update status: ", participants)
        if not participant:
            return

        status_options = [s for s in _db().PARTICIPANT_STATUSES if s != 'removed']
        print("\n" + get_text("mobility.trip_management.status.participant_options", "Participant Status Options:"))
        for i, status in enumerate(status_options, 1):
            print(f"{i}. {status.replace('_', ' ').title()}")

        choice = int(input(get_text("mobility.trip_management.status.select_status_n", "Select new status (1-{max}): ").format(max=len(status_options)))) - 1
        if not 0 <= choice < len(status_options):
            print(get_text("mobility.trip_management.validation.invalid_choice", "Invalid choice."))
            return
        new_status = status_options[choice]
        outcome = set_participant_status(auth, participant[0], new_status)
        print(get_text("mobility.trip_management.status.updated", "Participant status updated to '{status}'").format(status=new_status.title()))
        _print_refund((outcome or {}).get('refund') if isinstance(outcome, dict) else None)

    except ValueError as e:
        print(str(e) if str(e) and not str(e).startswith('invalid literal') else
              get_text("mobility.trip_management.validation.enter_valid_number", "Please enter a valid number."))
    except (PermissionError, sqlite3.Error) as e:
        print(get_text("mobility.trip_management.errors.updating_participant_status", "Error updating participant status: {error}").format(error=e))


def remove_participant(conn, trip_id, participants):
    """Take a participant off a trip (``conn`` is unused; kept for callers).

    The registration is kept with status 'removed' and a paid place is
    refunded; nothing is deleted.
    """
    auth = _common.get_auth()
    try:
        participant = _pick_participant("mobility.trip_management.remove.enter_participant_id", "Enter participant ID to remove: ", participants)
        if not participant:
            return

        participant_name = participant[6] if participant[6] else get_text("mobility.trip_management.participants.student_id", "Student {student_id}").format(student_id=participant[1])

        confirm = input(get_text("mobility.trip_management.remove.confirm", "Are you sure you want to remove '{name}' from this trip? (y/n): ").format(name=participant_name)).lower()
        if confirm != 'y':
            print(get_text("mobility.trip_management.remove.cancelled", "Removal cancelled."))
            return
        reason = input(get_text("mobility.trip_management.remove.reason_prompt", "Reason (optional): ")).strip()
        outcome = remove_participant_record(auth, participant[0], reason)
        print(get_text("mobility.trip_management.remove.success", "Participant '{name}' removed from trip.").format(name=participant_name))
        _print_refund(outcome.get('refund'))

    except ValueError as e:
        print(str(e) if str(e) and not str(e).startswith('invalid literal') else
              get_text("mobility.trip_management.validation.enter_valid_number", "Please enter a valid number."))
    except (PermissionError, sqlite3.Error) as e:
        print(get_text("mobility.trip_management.errors.removing_participant", "Error removing participant: {error}").format(error=e))


def _print_refund(outcome):
    if not outcome or outcome.get('skipped'):
        if outcome and outcome.get('message'):
            print(outcome['message'])
        return
    if not outcome.get('success'):
        print(get_text(
            "mobility.trip_management.cancel.refund_failed",
            "Your place has been released, but the refund could not be raised "
            "automatically. Please contact the finance office.",
        ))
        return
    if outcome.get('balance_after') is not None:
        print(get_text(
            "mobility.trip_management.cancel.refund_to_account",
            "£{amount:.2f} has been credited back to your student finance account "
            "(balance: £{balance:.2f}).",
        ).format(amount=outcome['amount'], balance=outcome['balance_after']))
    else:
        print(get_text(
            "mobility.trip_management.cancel.refund_raised_plain",
            "A refund of £{amount:.2f} has been raised to the original payment method.",
        ).format(amount=outcome['amount']))
    if outcome.get('email_sent'):
        print(get_text("mobility.trip_management.refund.receipt_sent_plain",
                       "A refund confirmation has been emailed."))


@log_delete(module="trips", description="Cancelling trip registration")
def cancel_trip_registration():
    """Cancel current user's trip registration"""
    auth = _cli_auth("mobility.trip_management.auth.must_login_cancel", "You must be logged in to cancel trip registrations.")
    if not auth:
        return False

    if not auth.check_permission('cancel_trip_registration'):
        print(get_text("mobility.trip_management.auth.no_permission_cancel", "You don't have permission to cancel trip registrations."))
        return False

    current = _db().CURRENT_PARTICIPANT_STATUSES
    registrations = [r for r in list_my_registrations(auth)
                     if r['status'] in current and r['trip_status'] not in ('completed', 'archived')]

    if not registrations:
        print(get_text("mobility.trip_management.cancel.no_active_registrations", "You have no active trip registrations to cancel."))
        return True

    print("\n" + get_text("mobility.trip_management.cancel.active_registrations", "Your Active Trip Registrations:"))
    print("=" * 100)
    print(f"{get_text('mobility.trip_management.headers.id', 'ID'):<5} {get_text('mobility.trip_management.headers.trip_name', 'Trip Name'):<25} {get_text('mobility.trip_management.headers.destination', 'Destination'):<20} {get_text('mobility.trip_management.headers.start_date', 'Start Date'):<12} {get_text('mobility.trip_management.headers.payment', 'Payment'):<10} {get_text('mobility.trip_management.headers.reg_date', 'Reg Date'):<12}")
    print("-" * 100)
    for reg in registrations:
        print(f"{reg['participant_id']:<5} {reg['trip_name'][:24]:<25} {(reg['destination'] or '')[:19]:<20} {reg['start_date']:<12} {(reg['payment_status'] or '').title():<10} {(reg['registration_date'] or '')[:10]:<12}")
    print("=" * 100)

    choice = input(get_text("mobility.trip_management.cancel.enter_registration_id", "\nEnter Registration ID to cancel (blank to return to the menu): ")).strip()
    if not choice:
        return True
    try:
        registration_id = int(choice)
    except ValueError:
        print(get_text("mobility.trip_management.cancel.invalid_registration_id", "Invalid registration ID."))
        return False
    if registration_id == 0:
        return True

    selected = next((r for r in registrations if r['participant_id'] == registration_id), None)
    if not selected:
        print(get_text("mobility.trip_management.cancel.invalid_registration_id", "Invalid registration ID."))
        return False

    print(get_text("mobility.trip_management.cancel.cancelling_for", "\nCancelling registration for: {trip_name}").format(trip_name=selected['trip_name']))
    print(get_text("mobility.trip_management.cancel.destination", "Destination: {destination}").format(destination=selected['destination']))
    print(get_text("mobility.trip_management.cancel.start_date", "Start Date: {start_date}").format(start_date=selected['start_date']))
    print(get_text("mobility.trip_management.cancel.payment_status", "Payment Status: {status}").format(status=(selected['payment_status'] or '').title()))

    if selected['payment_status'] in ('paid', 'partial') and float(selected['cost'] or 0) > 0:
        print(get_text(
            "mobility.trip_management.cancel.refund_due",
            "\nYou paid £{amount:.2f} by {method}. Cancelling will raise a refund.",
        ).format(amount=float(selected['cost'] or 0), method=payments.method_label(selected['payment_method'])))

    confirm = input(get_text("mobility.trip_management.cancel.confirm", "\nAre you sure you want to cancel this registration? (y/n): ")).lower()
    if confirm not in ('y', 'yes'):
        print(get_text("mobility.trip_management.cancel.aborted", "Cancellation aborted."))
        return True

    try:
        outcome = cancel_registration(auth, registration_id, get_text(
            "mobility.trip_management.cancel.by_participant", "Cancelled by participant"))
    except (ValueError, PermissionError) as e:
        print(str(e))
        return False
    except sqlite3.Error as e:
        print(get_text("mobility.trip_management.errors.cancelling_registration", "Error cancelling registration: {error}").format(error=e))
        logging.error(get_text("mobility.trip_management.errors.in_cancel_registration", "Error in cancel_trip_registration: {error}").format(error=e))
        return False

    print(get_text("mobility.trip_management.cancel.success", "\nRegistration for '{trip_name}' has been cancelled successfully.").format(trip_name=selected['trip_name']))
    _print_refund(outcome.get('refund'))
    return True


def _refund_trip_payment(cancellation, *, processed_by=None):
    """Raise the refund for a cancelled registration (older callers).

    ``cancellation`` is the dict older code assembled; this delegates to
    :func:`refund_participant`.
    """
    place = get_participant(cancellation['participant_id']) or {
        'id': cancellation['participant_id'], 'payment_status': 'paid',
        'amount_paid': cancellation.get('amount'),
    }
    place.setdefault('payment_method', cancellation.get('method'))
    trip = _trips().get_trip(cancellation['trip_id']) or {
        'id': cancellation['trip_id'], 'trip_name': cancellation['trip_name'],
        'destination': cancellation.get('destination'), 'start_date': cancellation.get('start_date'),
        'end_date': cancellation.get('end_date'), 'cost': cancellation.get('amount'),
    }
    outcome = refund_participant(place, trip, processed_by=processed_by,
                                 amount=cancellation.get('amount'))
    _print_refund(outcome)
    return bool(outcome.get('success'))
