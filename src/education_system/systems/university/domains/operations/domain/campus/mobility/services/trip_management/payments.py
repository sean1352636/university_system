"""Taking payment for a trip registration, through the Finance system.

Three methods are offered at the point of registration. All three post to
Finance through its port, ``services/bus/finance_bus`` (which wraps
``finance.infrastructure.finance_integration`` — the same entry points the
Shop, Restaurant, Library and Betting Shop use), so a trip payment lands in
the ``payments`` table the Finance GUI reads, and is posted to the general
ledger:

* cash / card       → ``finance_bus.record_payment``
* student account   → ``finance_bus.pay_from_student_account``, which
  re-checks the balance atomically, debits ``student_finance_accounts``,
  writes the ledger rows and fires the low-balance alert.

Those helpers own their own database transactions and commit independently,
so payment is taken *after* the registration row is committed. A payment
that fails or is cancelled therefore leaves the registration on
``payment_status='pending'`` — a state the schema already models and staff
can settle from Manage Participants — rather than taking money for a
registration that was never written.
"""

from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management._common import (
    get_text, logging,
)

logger = logging.getLogger(__name__)

CASH = 'cash'
CARD = 'card'
STUDENT_ACCOUNT = 'student_account'

# Source name this service files its payments under in Finance, alongside
# "Library", "Housing", "Shop", "BettingShop".
TRANSACTION_SOURCE = 'Trips'

_METHOD_LABELS = {
    CASH: ("mobility.trip_management.payment.method_cash", "Cash"),
    CARD: ("mobility.trip_management.payment.method_card", "Card"),
    STUDENT_ACCOUNT: ("mobility.trip_management.payment.method_student_account",
                      "Student finance account"),
}

# What Finance records as the payment_method. Kept in the existing house
# style ("Cash", "Student Finance Account") so finance reporting groups
# trip payments with everything else.
_FINANCE_METHOD_NAMES = {CASH: 'Cash', CARD: 'Card'}


def method_label(method):
    """Human-readable name for a payment method."""
    if not method:
        return get_text("mobility.trip_management.common.na", "N/A")
    key, default = _METHOD_LABELS.get(method, (None, None))
    return get_text(key, default) if key else str(method).replace('_', ' ').title()


def _finance():
    """Finance's port (``services/bus/finance_bus``), imported lazily;
    ``None`` when unavailable. Operations may not import Finance itself."""
    try:
        from education_system.systems.university.services.bus import finance_bus
        return finance_bus
    except Exception as exc:  # pragma: no cover - optional dependency
        logger.warning("Finance integration unavailable: %s", exc)
        return None


def _finance_bus():
    """Import the finance bus lazily; ``None`` when unavailable."""
    try:
        from education_system.systems.university.services.bus import finance_bus
        return finance_bus
    except Exception as exc:  # pragma: no cover - optional dependency
        logger.warning("Finance bus unavailable: %s", exc)
        return None


def active_holds(student_id):
    """Active finance holds for the student, newest first.

    An enrolment-blocking hold means the student owes the university money;
    ``trip_bus.register_student`` gates on the same check. Fails open — an
    unreachable finance bus must not lock everyone out of trips.
    """
    if not student_id:
        return []
    bus = _finance_bus()
    if bus is None:
        return []
    try:
        return bus.list_active_holds(str(student_id)) or []
    except Exception as exc:
        logger.warning("Could not read finance holds for %s: %s — treating as none",
                       student_id, exc)
        return []


def describe_holds(holds):
    """Render active holds as lines fit to show the student."""
    lines = []
    for hold in holds:
        amount = hold.get('amount') or 0
        lines.append(get_text(
            "mobility.trip_management.payment.hold_line",
            "  - {reason} (£{amount:.2f}, from {source})",
        ).format(reason=hold.get('reason') or get_text("mobility.trip_management.common.na", "N/A"),
                 amount=float(amount),
                 source=hold.get('source') or get_text("mobility.trip_management.common.na", "N/A")))
    return lines


def account_balance(student_id):
    """The student's finance account balance, or ``None`` if they have no account."""
    if not student_id:
        return None
    finance = _finance()
    if finance is None:
        return None
    try:
        return finance.account_balance(str(student_id))
    except Exception as exc:
        logger.warning("Could not read finance balance for %s: %s", student_id, exc)
        return None


def select_payment_method(amount, *, balance=None):
    """Prompt for a payment method, re-prompting on insufficient funds.

    ``balance`` is the student finance account balance, or ``None`` when
    the payer has no account — in which case that option is not offered.
    Returns the chosen method, or ``None`` if the user backed out.
    """
    print("\n" + get_text("mobility.trip_management.payment.amount_due", "Amount due: £{amount:.2f}").format(amount=amount))
    print(get_text("mobility.trip_management.payment.method_prompt_title", "Payment Method:"))

    while True:
        options = [CASH, CARD]
        print("1. " + method_label(CASH))
        print("2. " + method_label(CARD))
        if balance is None:
            print(get_text(
                "mobility.trip_management.payment.no_student_account",
                "   (Student finance account unavailable — no account on record.)",
            ))
        else:
            options.append(STUDENT_ACCOUNT)
            print("3. " + method_label(STUDENT_ACCOUNT) + " " + get_text(
                "mobility.trip_management.payment.balance_suffix",
                "(balance: £{balance:.2f})",
            ).format(balance=balance))

        choice = input(get_text(
            "mobility.trip_management.payment.select_method",
            "Select payment method (1-{max}, or blank to cancel): ",
        ).format(max=len(options))).strip()

        if not choice:
            return None

        if not choice.isdigit() or not (1 <= int(choice) <= len(options)):
            print(get_text("mobility.trip_management.validation.invalid_choice", "Invalid choice."))
            continue

        method = options[int(choice) - 1]

        if method == STUDENT_ACCOUNT and balance is not None and balance < amount:
            print(get_text(
                "mobility.trip_management.payment.insufficient_funds",
                "\nInsufficient funds: your student finance account holds £{balance:.2f} "
                "but £{amount:.2f} is due.\nPlease choose another payment method.\n",
            ).format(balance=balance, amount=amount))
            continue

        return method


def take_payment(*, method, amount, student_id, trip_id, trip_name,
                 processed_by=None):
    """Post a trip payment to Finance.

    Returns ``{'success', 'message', 'method', 'reference', 'payment_id',
    'balance_after'}``. ``balance_after`` is only set for student-account
    payments. Never raises — a failure comes back as ``success=False`` with
    a message fit to show the user, so the caller can offer another method.
    """
    result = {
        'success': False,
        'message': '',
        'method': method,
        'reference': f"TRIP-{trip_id}",
        'payment_id': None,
        'balance_after': None,
    }

    finance = _finance()
    if finance is None:
        result['message'] = get_text(
            "mobility.trip_management.payment.finance_unavailable",
            "The finance system is unavailable, so payment could not be taken.",
        )
        return result

    description = get_text(
        "mobility.trip_management.payment.description",
        "Trip registration: {trip_name}",
    ).format(trip_name=trip_name)

    try:
        if method == STUDENT_ACCOUNT:
            # check_balance=True re-verifies against the live balance inside
            # Finance's own transaction, so a balance that moved between the
            # prompt and here is caught here rather than going overdrawn.
            outcome = finance.pay_from_student_account(
                student_id=str(student_id),
                amount=amount,
                description=description,
                transaction_source=TRANSACTION_SOURCE,
                transaction_ref=result['reference'],
                processed_by=processed_by or 'System',
                check_balance=True,
            )
            result['success'] = bool(outcome.get('success'))
            result['message'] = outcome.get('message') or ''
            result['balance_after'] = outcome.get('new_balance')
            if outcome.get('transaction_id'):
                result['reference'] = outcome['transaction_id']
            return result

        if method in _FINANCE_METHOD_NAMES:
            payment_id = finance.record_payment(
                student_id=str(student_id) if student_id else None,
                amount=amount,
                payment_method=_FINANCE_METHOD_NAMES[method],
                transaction_source=TRANSACTION_SOURCE,
                transaction_ref=result['reference'],
                notes=description,
                created_by=processed_by or 'System',
            )
            result['payment_id'] = payment_id
            result['success'] = payment_id is not None
            if not result['success']:
                result['message'] = get_text(
                    "mobility.trip_management.payment.not_recorded",
                    "The payment could not be recorded in the finance system.",
                )
            return result

        result['message'] = f"unknown payment method: {method!r}"
        return result

    except Exception as exc:
        logger.error("Trip payment failed (%s, £%s, trip %s): %s",
                     method, amount, trip_id, exc, exc_info=True)
        result['message'] = get_text(
            "mobility.trip_management.payment.failed",
            "Payment failed: {error}",
        ).format(error=exc)
        return result


def refund_payment(*, method, amount, student_id, trip_id, trip_name,
                   payment_reference=None, processed_by=None):
    """Refund a trip payment through Finance.

    The refund is always recorded in ``unified_refunds`` (and posted to the
    ledger) via ``finance_bus.record_refund``. A student-account payment is
    additionally credited straight back to the balance, so the student gets
    the money without the finance office settling anything by hand; cash and
    card refunds are recorded against the original method for the office to
    pay out.

    Returns ``{'success', 'message', 'refund_id', 'balance_after'}`` and
    never raises.
    """
    result = {
        'success': False,
        'message': '',
        'refund_id': None,
        # The reference record_refund_to_finance files the refund under, so
        # the participant can quote the same string the finance office sees.
        'reference': f"{TRANSACTION_SOURCE.upper()}-TRIP-{trip_id}",
        'balance_after': None,
    }

    finance = _finance()
    if finance is None:
        result['message'] = get_text(
            "mobility.trip_management.payment.finance_unavailable",
            "The finance system is unavailable, so payment could not be taken.",
        )
        return result

    reason = get_text(
        "mobility.trip_management.payment.refund_reason",
        "Trip registration cancelled: {trip_name}",
    ).format(trip_name=trip_name)

    try:
        refund_id = finance.record_refund(
            student_id=str(student_id) if student_id else None,
            refund_amount=amount,
            original_payment_id=None,
            refund_reason=reason,
            refund_type='full',
            transaction_source=TRANSACTION_SOURCE,
            transaction_ref=f"TRIP-{trip_id}",
            refund_method=_FINANCE_METHOD_NAMES.get(method, 'original_payment_method'),
            requested_by=processed_by or 'System',
            notes=f"Original payment reference: {payment_reference}" if payment_reference else None,
        )
        result['refund_id'] = refund_id
        result['success'] = refund_id is not None
        if not result['success']:
            result['message'] = get_text(
                "mobility.trip_management.payment.refund_not_recorded",
                "The refund could not be recorded in the finance system.",
            )
            return result

        if method == STUDENT_ACCOUNT and student_id:
            credited = finance.credit_student_account(
                student_id=str(student_id),
                amount=amount,
                payment_method='refund',
                processed_by=processed_by or 'System',
                description=reason,
            )
            if credited.get('success'):
                result['balance_after'] = credited.get('new_balance')
            else:
                # The refund is on record either way; flag that the balance
                # did not move so it is settled rather than silently lost.
                result['success'] = False
                result['message'] = credited.get('message') or get_text(
                    "mobility.trip_management.payment.refund_not_credited",
                    "The refund was recorded but could not be credited to the account.",
                )

        return result

    except Exception as exc:
        logger.error("Trip refund failed (%s, £%s, trip %s): %s",
                     method, amount, trip_id, exc, exc_info=True)
        result['message'] = get_text(
            "mobility.trip_management.payment.refund_failed_error",
            "Refund failed: {error}",
        ).format(error=exc)
        return result


def pay_for_registration(auth, participant_id, method, amount=None):
    """Take a payment towards a trip place — operations and Students' Union
    trips alike — through Finance (:func:`take_payment`), then record it on
    the place: ``amount_paid`` goes up and ``payment_status`` becomes
    'paid' once nothing is owed (cost less any hardship award), else
    'partial'. ``amount`` defaults to everything still owed (an instalment
    can be paid by giving its amount). The participant pays for their own
    place; trip organisers may record a payment for anyone.

    Returns the :func:`take_payment` outcome plus ``amount`` and ``owed``
    (what is left). Raises PermissionError / ValueError before any money
    moves; a Finance failure comes back as ``success`` False.
    """
    from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management import (
        database, money, registrations, trips,
    )
    if method not in (CASH, CARD, STUDENT_ACCOUNT):
        raise ValueError(f"unknown payment method {method!r}")
    who = trips.actor(auth)
    with database.read_connection() as c:
        place = registrations.get_participant(participant_id, conn=c)
        if not place:
            raise ValueError(get_text("mobility.trip_management.participants.not_found",
                                      "Participant not found."))
        trip = trips.get_trip(place['trip_id'], conn=c)
        own = ((who['user_id'] is not None and place.get('user_id') == who['user_id'])
               or (who['student_id'] and place.get('student_id') == who['student_id']))
        if not own and not (auth.check_permission('manage_trip_participants')
                            or trips.can_manage_trip(auth, trip, conn=c, who=who)):
            raise PermissionError(get_text("mobility.trip_management.auth.no_permission_manage_participants",
                                           "You don't have permission to manage participants."))
    if place['status'] not in ('registered', 'confirmed', 'attended'):
        raise ValueError(f"no payment is taken for a {place['status']} registration")
    owed = money.amount_owed(place, trip)
    amount = owed if amount is None else round(float(amount), 2)
    if amount <= 0 or amount - owed > 0.005:
        raise ValueError(f"amount must be more than zero and no more than £{owed:.2f} owed")
    if method == STUDENT_ACCOUNT and not place.get('student_id'):
        raise ValueError("only a student can pay from a student finance account")
    trip_name = trip['trip_name']
    if (trip.get('source') or 'operations') == 'su':
        trip_name = f"{trip_name} (Students' Union{': ' + trip['organising_club'] if trip.get('organising_club') else ''})"
    outcome = take_payment(method=method, amount=amount, student_id=place.get('student_id'),
                           trip_id=trip['id'], trip_name=trip_name, processed_by=who['username'])
    outcome['amount'] = amount
    outcome['owed'] = owed
    if not outcome.get('success'):
        return outcome
    left = round(owed - amount, 2)
    try:
        with database.write_transaction() as c:
            c.execute("UPDATE trip_participants SET amount_paid = COALESCE(amount_paid, 0) + ?, "
                      "payment_method = ?, payment_reference = ?, payment_status = ? WHERE id = ?",
                      (amount, method, outcome.get('reference'),
                       'paid' if left <= 0.005 else 'partial', participant_id))
    except Exception as exc:
        # The money is in Finance; say so rather than reading as unpaid.
        logger.error("Trip payment %s taken but registration %s not updated: %s",
                     outcome.get('reference'), participant_id, exc)
        outcome['message'] = f"payment taken but the registration was not updated: {exc}"
    outcome['owed'] = max(left, 0.0)
    return outcome
