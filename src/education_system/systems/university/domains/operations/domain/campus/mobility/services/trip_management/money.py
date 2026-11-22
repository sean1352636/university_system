"""Trip money: instalments, refund tiers, hardship, budget against actual,
and the post-trip reconciliation.

Refunds follow the trip's ``refund_policy`` — a JSON list of
``{days_before, percent}`` tiers: cancelling at least ``days_before`` days
before the start refunds ``percent`` of what was paid beyond the deposit.
With no policy the default applies (28+ days 100%, 14+ days 50%, otherwise
nothing). The deposit (``deposit_amount``) is not refundable unless the
university cancels, in which case everything paid comes back.

A hardship award reduces what a participant owes; it is recorded on the
place (``hardship_award``) and, when the award came from a bursary
application (Finance's hardship fund), the application is linked in the
trip history.
"""

import json

from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management._common import (
    get_text, logging, datetime,
)

logger = logging.getLogger(__name__)

DEFAULT_REFUND_POLICY = ({'days_before': 28, 'percent': 100.0},
                         {'days_before': 14, 'percent': 50.0},
                         {'days_before': 0, 'percent': 0.0})


def _db():
    from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management import database
    return database


def _trips():
    from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management import trips
    return trips


def _now():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def _money(value):
    try:
        return round(float(value or 0), 2)
    except (TypeError, ValueError):
        raise ValueError(f"not an amount: {value!r}") from None


def _load_trip(c, trip_id):
    trip = _trips().get_trip(trip_id, conn=c)
    if not trip:
        raise ValueError(get_text("mobility.trip_management.trips.trip_not_found", "Trip not found."))
    return trip


def _require_manager(auth, trip, c, who):
    if not (_trips().can_manage_trip(auth, trip, conn=c, who=who)
            or auth.check_permission('manage_trip_expenses')):
        raise PermissionError(get_text("mobility.trip_management.money.not_manager",
                                       "Only the trip's organisers can manage its money."))


# ---------------------------------------------------------------------------
# Instalments
# ---------------------------------------------------------------------------

def list_instalments(trip_id, conn=None):
    with _db().read_connection(conn) as c:
        cur = c.execute("SELECT id, trip_id, label, due_date, amount FROM trip_instalments "
                        "WHERE trip_id = ? ORDER BY due_date, id", (trip_id,))
        names = [d[0] for d in cur.description]
        return [dict(zip(names, r)) for r in cur.fetchall()]


def _clean_instalment(label, due_date, amount):
    label = str(label or '').strip()
    if not label:
        raise ValueError("an instalment needs a label")
    try:
        due_date = datetime.strptime(str(due_date).strip()[:10], '%Y-%m-%d').strftime('%Y-%m-%d')
    except (TypeError, ValueError):
        raise ValueError("due date must be YYYY-MM-DD") from None
    amount = _money(amount)
    if amount <= 0:
        raise ValueError("an instalment must be more than zero")
    return label, due_date, amount


def _check_total(c, trip, exclude_id=None, adding=0.0):
    total = c.execute("SELECT COALESCE(SUM(amount), 0) FROM trip_instalments WHERE trip_id = ? "
                      "AND id IS NOT ?", (trip['id'], exclude_id)).fetchone()[0] + adding
    if total - float(trip.get('cost') or 0) > 0.005:
        raise ValueError(f"instalments (£{total:.2f}) would exceed the trip cost "
                         f"(£{float(trip.get('cost') or 0):.2f})")


def add_instalment(auth, trip_id, label, due_date, amount):
    """Add a payment instalment to the trip's schedule. Returns its id."""
    who = _trips().actor(auth)
    label, due_date, amount = _clean_instalment(label, due_date, amount)
    with _db().write_transaction() as c:
        trip = _load_trip(c, trip_id)
        _require_manager(auth, trip, c, who)
        _check_total(c, trip, adding=amount)
        new_id = c.execute("INSERT INTO trip_instalments (trip_id, label, due_date, amount) "
                           "VALUES (?, ?, ?, ?)", (trip_id, label, due_date, amount)).lastrowid
        _trips().record_history(c, trip_id, version=trip.get('version'), changed_by=who['username'],
                                action='instalment_added', field=label, new_value=f"{due_date} £{amount:.2f}")
        return new_id


def update_instalment(auth, instalment_id, *, label=None, due_date=None, amount=None):
    who = _trips().actor(auth)
    with _db().write_transaction() as c:
        row = c.execute("SELECT trip_id, label, due_date, amount FROM trip_instalments WHERE id = ?",
                        (instalment_id,)).fetchone()
        if not row:
            raise ValueError("no such instalment")
        trip = _load_trip(c, row[0])
        _require_manager(auth, trip, c, who)
        new = _clean_instalment(row[1] if label is None else label,
                                row[2] if due_date is None else due_date,
                                row[3] if amount is None else amount)
        _check_total(c, trip, exclude_id=instalment_id, adding=new[2])
        c.execute("UPDATE trip_instalments SET label = ?, due_date = ?, amount = ? WHERE id = ?",
                  (*new, instalment_id))
        _trips().record_history(c, trip['id'], version=trip.get('version'), changed_by=who['username'],
                                action='instalment_changed', field=new[0],
                                old_value=f"{row[2]} £{float(row[3] or 0):.2f}",
                                new_value=f"{new[1]} £{new[2]:.2f}")
    return True


def remove_instalment(auth, instalment_id):
    who = _trips().actor(auth)
    with _db().write_transaction() as c:
        row = c.execute("SELECT trip_id, label FROM trip_instalments WHERE id = ?",
                        (instalment_id,)).fetchone()
        if not row:
            raise ValueError("no such instalment")
        trip = _load_trip(c, row[0])
        _require_manager(auth, trip, c, who)
        c.execute("DELETE FROM trip_instalments WHERE id = ?", (instalment_id,))
        _trips().record_history(c, trip['id'], version=trip.get('version'), changed_by=who['username'],
                                action='instalment_removed', field=row[1])
    return True


def amount_owed(place, trip):
    """What the participant still owes: cost less hardship award, less paid
    (net of refunds), never below zero."""
    cost = _money(trip.get('cost'))
    paid = _money(place.get('amount_paid')) - _money(place.get('amount_refunded'))
    return max(round(cost - _money(place.get('hardship_award')) - paid, 2), 0.0)


def instalment_schedule(participant_id):
    """The trip's instalments for one participant, each with ``paid`` (covered
    by what they have paid so far, after any hardship award)."""
    from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management import registrations
    with _db().read_connection() as c:
        place = registrations.get_participant(participant_id, conn=c)
        if not place:
            raise ValueError("Participant not found.")
        items = list_instalments(place['trip_id'], conn=c)
    credit = (_money(place.get('amount_paid')) - _money(place.get('amount_refunded'))
              + _money(place.get('hardship_award')))
    for item in items:
        item['paid'] = credit + 0.005 >= item['amount']
        credit = max(credit - item['amount'], 0)
    return items


# ---------------------------------------------------------------------------
# Refunds
# ---------------------------------------------------------------------------

def refund_policy(trip):
    """The trip's tiers, highest ``days_before`` first."""
    tiers = None
    raw = trip.get('refund_policy')
    if raw:
        try:
            tiers = json.loads(raw) if isinstance(raw, str) else list(raw)
        except (TypeError, ValueError):
            logger.warning("trip %s: unreadable refund_policy, using the default", trip.get('id'))
            tiers = None
    tiers = tiers or [dict(t) for t in DEFAULT_REFUND_POLICY]
    return sorted(({'days_before': int(t['days_before']), 'percent': float(t['percent'])}
                   for t in tiers), key=lambda t: -t['days_before'])


def refund_due_for(place, trip, cancel_date=None, *, university_cancelled=False):
    """The refund for a place (dicts): ``{'amount', 'percent', 'days_before',
    'paid', 'deposit_retained', 'already_refunded'}``."""
    paid = _money(place.get('amount_paid'))
    if not paid and place.get('payment_status') == 'paid':
        paid = _money(trip.get('cost')) - _money(place.get('hardship_award'))
    refunded = _money(place.get('amount_refunded'))
    when = cancel_date or datetime.now()
    if isinstance(when, str):
        when = datetime.strptime(when[:10], '%Y-%m-%d')
    if isinstance(when, datetime):
        when = when.date()
    start = datetime.strptime(str(trip['start_date'])[:10], '%Y-%m-%d').date()
    days = (start - when).days
    if university_cancelled:
        percent, deposit = 100.0, 0.0
    else:
        percent = next((t['percent'] for t in refund_policy(trip) if days >= t['days_before']), 0.0)
        deposit = min(_money(trip.get('deposit_amount')), paid)
    amount = round((paid - deposit) * percent / 100.0 - refunded, 2)
    return {'amount': max(amount, 0.0), 'percent': percent, 'days_before': days, 'paid': paid,
            'deposit_retained': deposit,
            'already_refunded': refunded}


def refund_due(participant_id, cancel_date=None, *, university_cancelled=False):
    """:func:`refund_due_for` for a participant id."""
    from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management import registrations
    with _db().read_connection() as c:
        place = registrations.get_participant(participant_id, conn=c)
        if not place:
            raise ValueError("Participant not found.")
        trip = _load_trip(c, place['trip_id'])
    return refund_due_for(place, trip, cancel_date, university_cancelled=university_cancelled)


# ---------------------------------------------------------------------------
# Hardship
# ---------------------------------------------------------------------------

def apply_hardship(auth, participant_id, amount, *, application_id=None, note=""):
    """Award ``amount`` of hardship support towards a participant's trip cost.

    Trip organisers (or ``manage_trip_expenses``) only, on a trip that is
    ``hardship_eligible``. The award replaces any earlier one; the total of
    award and payments can't exceed the cost. ``application_id`` links a
    Finance bursary application from a hardship (or emergency) fund — it
    must be the participant's own and approved or awarded. When the award
    covers what is left, the place is marked paid. Returns the place.
    """
    from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management import registrations
    amount = _money(amount)
    if amount < 0:
        raise ValueError("a hardship award cannot be negative")
    link = None
    if application_id not in (None, ''):
        from education_system.systems.university.services.bus import trip_care_bus
        link = trip_care_bus.hardship_application(application_id)
    trips = _trips()
    who = trips.actor(auth)
    with _db().write_transaction() as c:
        place = registrations.get_participant(participant_id, conn=c)
        if not place:
            raise ValueError("Participant not found.")
        trip = _load_trip(c, place['trip_id'])
        _require_manager(auth, trip, c, who)
        if not int(trip.get('hardship_eligible') if trip.get('hardship_eligible') is not None else 1):
            raise ValueError("this trip is not eligible for hardship support")
        if place['status'] not in _db().CURRENT_PARTICIPANT_STATUSES:
            raise ValueError(f"this registration is {place['status']}")
        if link:
            if str(link['student_id'] or '') != str(place.get('student_id') or ''):
                raise ValueError("that bursary application belongs to another student")
            if link['fund_type'] not in ('hardship', 'emergency'):
                raise ValueError(f"bursary application {link['application_id']} is from a "
                                 f"{link['fund_type']} fund, not a hardship fund")
            if link['status'] not in ('approved', 'awarded'):
                raise ValueError(f"bursary application {link['application_id']} is {link['status']}")
        cost = _money(trip.get('cost'))
        paid = _money(place.get('amount_paid')) - _money(place.get('amount_refunded'))
        if amount + paid - cost > 0.005:
            raise ValueError(f"award (£{amount:.2f}) plus payments (£{paid:.2f}) would exceed "
                             f"the cost (£{cost:.2f})")
        covered = cost > 0 and amount + paid + 0.005 >= cost
        c.execute("UPDATE trip_participants SET hardship_award = ?, payment_status = CASE "
                  "WHEN ? THEN 'paid' WHEN payment_status = 'paid' THEN payment_status "
                  "WHEN ? > 0 THEN 'partial' ELSE payment_status END WHERE id = ?",
                  (amount, 1 if covered else 0, paid, participant_id))
        trips.record_history(c, trip['id'], version=trip.get('version'), changed_by=who['username'],
                             action='hardship', field=f"participant:{participant_id}",
                             old_value=place.get('hardship_award'), new_value=amount)
        if link:
            trips.record_history(c, trip['id'], version=trip.get('version'),
                                 changed_by=who['username'], action='hardship_link',
                                 field=f"participant:{participant_id}",
                                 new_value=f"bursary_application:{link['application_id']} "
                                           f"({link['fund_name']})")
        if note:
            trips.record_history(c, trip['id'], version=trip.get('version'),
                                 changed_by=who['username'], action='hardship_note',
                                 field=f"participant:{participant_id}", new_value=str(note))
        return registrations.get_participant(participant_id, conn=c)


# ---------------------------------------------------------------------------
# Budget, actual and reconciliation
# ---------------------------------------------------------------------------

def budget_vs_actual(trip_id):
    """``{'budget', 'expenses': {category: amount}, 'actual', 'income',
    'paid', 'refunded', 'hardship', 'variance', 'net'}``. ``variance`` is
    budget less actual spend (negative = overspent); ``net`` is income less
    actual spend."""
    with _db().read_connection() as c:
        trip = _load_trip(c, trip_id)
        expenses = {r[0] or 'other': round(float(r[1] or 0), 2) for r in c.execute(
            "SELECT category, SUM(amount) FROM trip_expenses WHERE trip_id = ? "
            "GROUP BY category ORDER BY category", (trip_id,)).fetchall()}
        paid, refunded, hardship = (float(v or 0) for v in c.execute(
            "SELECT SUM(amount_paid), SUM(amount_refunded), SUM(hardship_award) "
            "FROM trip_participants WHERE trip_id = ?", (trip_id,)).fetchone())
    actual = round(sum(expenses.values()), 2)
    income = round(paid - refunded, 2)
    budget = None if trip.get('budget') is None else _money(trip['budget'])
    return {'trip_id': trip_id, 'budget': budget, 'expenses': expenses, 'actual': actual,
            'income': income, 'paid': round(paid, 2), 'refunded': round(refunded, 2),
            'hardship': round(hardship, 2),
            'variance': None if budget is None else round(budget - actual, 2),
            'net': round(income - actual, 2)}


def get_reconciliation(trip_id):
    with _db().read_connection() as c:
        cur = c.execute("SELECT * FROM trip_reconciliations WHERE trip_id = ?", (trip_id,))
        row = cur.fetchone()
        return dict(zip([d[0] for d in cur.description], row)) if row else None


def reconcile(auth, trip_id, notes=""):
    """Sign off the trip's accounts once it has finished (completed or
    cancelled): budget, actual spend and income are frozen into
    ``trip_reconciliations``. Once signed off it can't be signed again.
    Returns the reconciliation."""
    figures = budget_vs_actual(trip_id)
    trips = _trips()
    who = trips.actor(auth)
    with _db().write_transaction() as c:
        trip = _load_trip(c, trip_id)
        _require_manager(auth, trip, c, who)
        if trip['status'] not in ('completed', 'cancelled', 'archived'):
            raise ValueError("a trip's accounts are reconciled after it has finished")
        existing = c.execute("SELECT signed_off_by, signed_off_at FROM trip_reconciliations "
                             "WHERE trip_id = ?", (trip_id,)).fetchone()
        if existing and existing[0]:
            raise ValueError(f"already signed off by {existing[0]} on {existing[1]}")
        c.execute(
            "INSERT INTO trip_reconciliations (trip_id, budget, actual, income, notes, "
            "signed_off_by, signed_off_at) VALUES (?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT (trip_id) DO UPDATE SET budget = excluded.budget, actual = excluded.actual, "
            "income = excluded.income, notes = excluded.notes, signed_off_by = excluded.signed_off_by, "
            "signed_off_at = excluded.signed_off_at",
            (trip_id, figures['budget'], figures['actual'], figures['income'],
             str(notes or '').strip() or None, who['username'], _now()))
        trips.record_history(c, trip_id, version=trip.get('version'), changed_by=who['username'],
                             action='reconciled', new_value=f"actual £{figures['actual']:.2f}, "
                                                            f"income £{figures['income']:.2f}")
    return get_reconciliation(trip_id)
