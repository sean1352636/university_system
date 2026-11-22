"""Trip Management CLI: the grouped screens beside the original menu.

The original options in ``menu.py`` keep their numbers; these sub-menus are
listed after them: the trip life cycle, approvals, risk assessment,
incidents, safeguarding and staffing, overseas travel, academic links,
places / waiting list / payments, health details, communications, the day
itself (roll call), money and evaluations.

Every screen gathers its input first and then calls one domain function,
which opens and commits its own short transaction — no ``input()`` is asked
while a transaction is open. The domain raises PermissionError / ValueError
with messages written for users; they are shown and the menu carries on.
"""

import logging

from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management import (
    _common,
    academic,
    approvals,
    comms,
    database,
    evaluation,
    incidents,
    medical,
    money,
    overseas,
    payments,
    registrations,
    risk,
    rollcall,
    safeguarding,
    trips,
    waitlist,
)
from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management._common import get_text

logger = logging.getLogger(__name__)

PAGE_SIZE = 20

# Permission groups. The domain checks the exact rule on every call; these
# only decide which entries a menu shows.
ORGANISE = ('manage_trips', 'create_trips')
PEOPLE = ORGANISE + ('manage_trip_participants',)
MONEY = ORGANISE + ('manage_trip_expenses',)
APPROVE = tuple(approvals.STAGE_PERMISSIONS.values())
HS = (risk.SIGN_OFF_PERMISSION,)

_FINISHED = ('completed', 'cancelled', 'archived')


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _t(key, default):
    return get_text(f"mobility.trip_management.cli.{key}", default)


def _auth():
    auth = _common.get_auth()
    if not auth or not getattr(auth, 'current_user', None):
        print(get_text("mobility.trip_management.auth.must_login_access",
                       "You must be logged in to access trip management."))
        return None
    return auth


def _can(auth, *permissions):
    return any(auth.check_permission(p) for p in permissions)


def _is_student(auth):
    return str(auth.current_user.get('role') or '').lower() == 'student'


def _call(func, *args, **kwargs):
    """Run one domain call. A refusal is shown, never raised: ``(ok, result)``."""
    try:
        return True, func(*args, **kwargs)
    except (PermissionError, ValueError) as e:
        print(str(e) or type(e).__name__)
    except Exception as e:
        logger.exception("trip CLI: %s failed", getattr(func, '__name__', func))
        print(_t("errors.failed", "That could not be completed: {error}").format(error=e))
    return False, None


def _ask(key, default):
    return input(_t(key, default)).strip()


def _ask_int(key, default):
    """A whole number, or ``None`` for blank / not a number."""
    raw = _ask(key, default)
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        print(_t("validation.whole_number", "Please enter a whole number."))
        return None


def _ask_amount(key, default):
    """An amount, or ``None`` for blank / not a number."""
    raw = _ask(key, default).lstrip('£')
    if not raw:
        return None
    try:
        return round(float(raw), 2)
    except ValueError:
        print(_t("validation.amount", "Please enter an amount, e.g. 25.00."))
        return None


def _yes(key, default):
    return _ask(key, default).lower() in ('y', 'yes')


def _ask_lines(key, default):
    """Several lines of text, finished by a line holding only '.'."""
    print(_t(key, default))
    lines = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line.strip() == '.':
            break
        lines.append(line)
    return "\n".join(lines).strip()


def _choose(options, labels=None, key="common.choose", default="Choose (1-{max}, blank to go back): "):
    """Pick one of ``options`` by number; ``None`` when blank or invalid."""
    labels = labels or [str(o).replace('_', ' ').title() for o in options]
    for i, label in enumerate(labels, 1):
        print(f"{i}. {label}")
    raw = input(_t(key, default).format(max=len(options))).strip()
    if not raw:
        return None
    if raw.isdigit() and 1 <= int(raw) <= len(options):
        return options[int(raw) - 1]
    print(get_text("mobility.trip_management.validation.invalid_choice", "Invalid choice."))
    return None


def _rule(width=80, char="="):
    print(char * width)


def _money(value):
    return f"£{float(value or 0):.2f}"


def _problems(problems, ok_key, ok_default):
    if not problems:
        print(_t(ok_key, ok_default))
        return
    for problem in problems:
        print(f"  - {problem}")


def _menu(auth, title, entries):
    """Numbered sub-menu over ``entries`` = ``[(label, func(auth))]``."""
    if not entries:
        print(_t("menu.nothing", "There is nothing here you have permission to use."))
        return
    while True:
        print("\n" + title)
        _rule(60)
        for i, (label, _func) in enumerate(entries, 1):
            print(f"{i}. {label}")
        back = len(entries) + 1
        print(f"\n{back}. " + _t("menu.back", "Back"))
        raw = input(_t("menu.choice", "\nEnter your choice (1-{max}): ").format(max=back)).strip()
        if not raw or raw == str(back):
            return
        if not raw.isdigit() or not 1 <= int(raw) <= len(entries):
            print(get_text("mobility.trip_management.validation.invalid_choice_try_again",
                           "Invalid choice. Please try again."))
            continue
        label, func = entries[int(raw) - 1]
        try:
            func(auth)
        except KeyboardInterrupt:
            print(get_text("mobility.trip_management.common.operation_cancelled", "\nOperation cancelled."))
        except Exception as e:
            logger.exception("trip CLI: %s failed", label)
            print(_t("errors.failed", "That could not be completed: {error}").format(error=e))
        input(get_text("mobility.trip_management.common.press_enter", "\nPress Enter to continue..."))


def _entries(auth, spec):
    """``spec`` = ``[(label, func, permissions or None)]`` → the visible entries."""
    return [(label, func) for label, func, perms in spec if perms is None or _can(auth, *perms)]


# ---------------------------------------------------------------------------
# Pickers (each reads on its own short connection, then asks)
# ---------------------------------------------------------------------------

def _trip_rows(auth, manage, statuses, include_archived):
    who = trips.actor(auth) if manage else None
    with database.read_connection() as c:
        rows = trips.list_trips(include_archived=include_archived, conn=c)
        if statuses:
            rows = [t for t in rows if t['status'] in statuses]
        if manage:
            rows = [t for t in rows if trips.can_manage_trip(auth, t, conn=c, who=who)]
    return rows


def _pick_trip(auth, *, manage=False, statuses=None, include_archived=False):
    """List trips (``manage``: only those the user organises) and pick one."""
    ok, rows = _call(_trip_rows, auth, manage, statuses, include_archived)
    if not ok:
        return None
    if not rows:
        print(get_text("mobility.trip_management.trips.no_trips_found", "No trips found."))
        return None
    pages = (len(rows) + PAGE_SIZE - 1) // PAGE_SIZE
    page = 0
    while True:
        print()
        print(f"{'ID':<5} {_t('head.trip', 'Trip'):<29} {_t('head.destination', 'Destination'):<19} "
              f"{_t('head.start', 'Start'):<11} {_t('head.status', 'Status'):<12} {_t('head.places', 'Places')}")
        _rule(90, "-")
        for t in rows[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]:
            print(f"{t['id']:<5} {(t['trip_name'] or '')[:28]:<29} {(t.get('destination') or '')[:18]:<19} "
                  f"{(t.get('start_date') or '')[:10]:<11} {t['status']:<12} "
                  f"{t.get('current_participants') or 0}/{t.get('max_participants') or 0}")
        if pages > 1:
            print(_t("pick.page", "Page {page} of {pages} — n: next page, p: previous page").format(
                page=page + 1, pages=pages))
        raw = _ask("pick.trip_id", "Trip ID (blank to go back): ")
        if not raw:
            return None
        if raw.lower() == 'n' and page + 1 < pages:
            page += 1
            continue
        if raw.lower() == 'p' and page:
            page -= 1
            continue
        trip = next((t for t in rows if raw.isdigit() and t['id'] == int(raw)), None)
        if trip:
            return trip
        print(get_text("mobility.trip_management.validation.invalid_trip_id", "Invalid trip ID."))


def _pick_participant(auth, trip, *, statuses=None, include_ended=False):
    """Pick one of a trip's participants (organisers). Returns the row or ``None``."""
    ok, rows = _call(registrations.list_participants, auth, trip['id'], include_ended=include_ended)
    if not ok:
        return None
    if statuses:
        rows = [r for r in rows if r['status'] in statuses]
    if not rows:
        print(_t("pick.no_participants", "No participants to choose from."))
        return None
    print(f"\n{'ID':<6} {_t('head.name', 'Name'):<26} {_t('head.student', 'Student'):<11} "
          f"{_t('head.status', 'Status'):<11} {_t('head.payment', 'Payment'):<9} {_t('head.paid', 'Paid')}")
    _rule(78, "-")
    for r in rows:
        print(f"{r['id']:<6} {(r.get('name') or '')[:25]:<26} {str(r.get('student_id') or '')[:10]:<11} "
              f"{r['status']:<11} {(r.get('payment_status') or '')[:8]:<9} {_money(r.get('amount_paid'))}")
    pid = _ask_int("pick.participant_id", "Participant ID (blank to go back): ")
    row = next((r for r in rows if r['id'] == pid), None)
    if pid is not None and not row:
        print(_t("pick.not_listed", "That participant is not listed."))
    return row


def _pick_my_place(auth, statuses=None):
    """Pick one of the signed-in user's registrations. Returns the row or ``None``."""
    ok, rows = _call(registrations.list_my_registrations, auth)
    if not ok:
        return None
    if statuses:
        rows = [r for r in rows if r['status'] in statuses]
    if not rows:
        print(_t("pick.no_registrations", "You have no registrations to choose from."))
        return None
    print(f"\n{'ID':<6} {_t('head.trip', 'Trip'):<29} {_t('head.start', 'Start'):<11} "
          f"{_t('head.place', 'Place'):<11} {_t('head.payment', 'Payment'):<9} {_t('head.trip_status', 'Trip status')}")
    _rule(80, "-")
    for r in rows:
        print(f"{r['participant_id']:<6} {(r['trip_name'] or '')[:28]:<29} {(r.get('start_date') or '')[:10]:<11} "
              f"{r['status']:<11} {(r.get('payment_status') or '')[:8]:<9} {r.get('trip_status') or ''}")
    pid = _ask_int("pick.registration_id", "Registration ID (blank to go back): ")
    row = next((r for r in rows if r['participant_id'] == pid), None)
    if pid is not None and not row:
        print(_t("pick.not_listed", "That registration is not listed."))
    return row


def _pick_any_place(auth, statuses=None):
    """The user's own registration or — for organisers — a participant's.

    Returns the participant id, or ``None``.
    """
    if _can(auth, *PEOPLE):
        whose = _choose(['own', 'participant'],
                        [_t("pick.own", "One of my own registrations"),
                         _t("pick.someone", "A participant on a trip I organise")])
        if whose is None:
            return None
        if whose == 'participant':
            trip = _pick_trip(auth, manage=True)
            row = trip and _pick_participant(auth, trip, statuses=statuses)
            return row['id'] if row else None
    row = _pick_my_place(auth, statuses=statuses)
    return row['participant_id'] if row else None


# ---------------------------------------------------------------------------
# Trip details and status
# ---------------------------------------------------------------------------

def show_trip_summary(auth):
    """Key facts, approvals, risk assessment and what still blocks opening."""
    trip = _pick_trip(auth, include_archived=True)
    if not trip:
        return
    ok, state = _call(approvals.approval_state, trip['id'])
    assessment = risk.current(trip['id'])
    print()
    _rule()
    print(f"{trip['trip_name']} (#{trip['id']}) — {trip['status'].replace('_', ' ').title()}")
    print(f"{trip.get('destination') or ''}{', ' + trip['country'] if trip.get('country') else ''}  "
          f"{trip.get('start_date')} → {trip.get('end_date')}")
    print(_t("summary.type", "Type: {type}   Source: {source}{club}").format(
        type=trip.get('trip_type') or 'day', source=trip.get('source') or 'operations',
        club=f" ({trip['organising_club']})" if trip.get('organising_club') else ''))
    print(_t("summary.places", "Places: {taken}/{max}   Cost: {cost}   Budget: {budget}").format(
        taken=trip.get('current_participants') or 0, max=trip.get('max_participants') or 0,
        cost=_money(trip.get('cost')),
        budget=_money(trip['budget']) if trip.get('budget') is not None else '-'))
    flags = [label for key, label in (
        ('is_overseas', _t("flag.overseas", "overseas")), ('high_risk', _t("flag.high_risk", "high risk")),
        ('involves_minors', _t("flag.minors", "under-18s")),
        ('involves_vulnerable_adults', _t("flag.vulnerable", "vulnerable adults")),
        ('counts_as_attendance', _t("flag.attendance", "counts as attendance"))) if trip.get(key)]
    if flags:
        print(_t("summary.flags", "Flags: {flags}").format(flags=", ".join(flags)))
    if trip.get('module_code'):
        print(_t("summary.module", "Module: {module}").format(module=trip['module_code']))
    print(_t("summary.contact", "24/7 contact: {contact}").format(
        contact=trip.get('emergency_contact_24h') or _t("summary.not_set", "not set")))
    if ok:
        _print_approval_state(state)
    if assessment:
        print(_t("summary.risk", "Risk assessment #{id}: {status} (residual {residual})").format(
            id=assessment['id'], status=assessment['status'],
            residual=assessment.get('overall_residual') or assessment.get('computed_residual') or '-'))
    else:
        print(_t("summary.no_risk", "Risk assessment: none yet"))
    if trip['status'] in ('proposed', 'planning', 'approved', 'closed'):
        ok, problems = _call(approvals.gate_problems, trip['id'], 'open')
        if ok:
            print(_t("summary.open_blockers", "Before it can open:"))
            _problems(problems, "summary.nothing_blocks", "  nothing — it can be opened.")
    _rule()


def _print_approval_state(state):
    print(_t("approval.state_title", "Approvals ({done}):").format(
        done=_t("approval.complete", "complete") if state['complete']
        else _t("approval.outstanding", "{n} outstanding").format(n=len(state['outstanding']))))
    for stage in state['required']:
        row = state['stages'][stage]
        line = f"  {approvals.STAGE_LABELS[stage]:<16} {row['decision']}"
        if row.get('decided_by'):
            line += f" — {row['decided_by']} {str(row.get('decided_at') or '')[:16]}"
        print(line)
        if row.get('comments'):
            print(f"      {row['comments']}")


# Settings the original create / update screens don't ask for.
_SETTINGS = (
    ('trip_type', 'choice', "Trip type"),
    ('country', 'text', "Country"),
    ('is_overseas', 'flag', "Overseas"),
    ('high_risk', 'flag', "High risk"),
    ('involves_minors', 'flag', "Involves under-18s"),
    ('involves_vulnerable_adults', 'flag', "Involves vulnerable adults"),
    ('min_staff_ratio', 'int', "Students per member of staff"),
    ('requires_first_aider', 'flag', "Needs a first aider"),
    ('emergency_contact_24h', 'text', "24/7 emergency contact"),
    ('budget', 'amount', "Budget"),
    ('deposit_amount', 'amount', "Deposit"),
    ('deposit_due', 'text', "Deposit due (YYYY-MM-DD)"),
    ('balance_due', 'text', "Balance due (YYYY-MM-DD)"),
    ('refund_policy', 'refunds', "Refund tiers"),
    ('hardship_eligible', 'flag', "Hardship support available"),
)


def _refund_text(value):
    import json
    try:
        tiers = json.loads(value) if value else []
    except (TypeError, ValueError):
        return str(value)
    return ", ".join(f"{int(t['days_before'])}:{float(t['percent']):g}" for t in tiers) or '-'


def _parse_refunds(raw):
    """'28:100, 14:50, 0:0' → tier list. Raises ValueError."""
    tiers = []
    for part in raw.split(','):
        days, _, percent = part.strip().partition(':')
        tiers.append({'days_before': int(days), 'percent': float(percent)})
    return tiers


def edit_trip_settings(auth):
    """Trip type, overseas, safeguarding and money settings."""
    trip = _pick_trip(auth, manage=True)
    if not trip:
        return
    print(_t("settings.intro", "\nLeave blank to keep the current value; '-' clears a text value."))
    changes = {}
    for name, kind, label in _SETTINGS:
        current = trip.get(name)
        if kind == 'flag':
            shown = _t("common.yes", "yes") if current else _t("common.no", "no")
        elif kind == 'refunds':
            shown = _refund_text(current)
        else:
            shown = current if current not in (None, '') else '-'
        prompt = f"{_t('settings.' + name, label)} [{shown}]: "
        if kind == 'choice':
            print(_t("settings.types", "Types: {types}").format(types=", ".join(database.TRIP_TYPES)))
        raw = input(prompt).strip()
        if not raw:
            continue
        if kind == 'flag':
            if raw.lower() in ('y', 'yes', 'n', 'no'):
                changes[name] = raw.lower() in ('y', 'yes')
            else:
                print(_t("settings.yes_no", "Answer y or n — kept as it was."))
        elif kind == 'int':
            if raw.isdigit():
                changes[name] = int(raw)
            else:
                print(_t("validation.whole_number", "Please enter a whole number."))
        elif kind == 'refunds':
            if raw == '-':
                changes[name] = None
                continue
            try:
                changes[name] = _parse_refunds(raw)
            except ValueError:
                print(_t("settings.refund_format",
                         "Write the tiers as days:percent, e.g. 28:100, 14:50, 0:0 — kept as it was."))
        else:
            changes[name] = None if raw == '-' else raw
    if not changes:
        print(get_text("mobility.trip_management.update.no_changes", "No changes to update."))
        return
    ok, updated = _call(trips.update_trip_record, auth, trip['id'], **changes)
    if not ok:
        return
    print(get_text("mobility.trip_management.update.success", "Trip updated successfully!"))
    if updated and updated.get('status') != trip['status']:
        print(_t("settings.status_changed",
                 "The change affects its approvals: the trip is now {status} and must be approved again.").format(
            status=updated['status']))


def change_trip_status(auth):
    """Move a trip along its life cycle; every blocking problem is shown."""
    trip = _pick_trip(auth, manage=True, include_archived=False)
    if not trip:
        return
    options = list(trips.TRIP_STATUS_TRANSITIONS.get(trip['status'], ()))
    if not options:
        print(_t("status.none", "A {status} trip cannot change status.").format(status=trip['status']))
        return
    print(_t("status.current", "\nCurrent status: {status}").format(status=trip['status']))
    for target in ('approved', 'open'):
        if target in options:
            ok, problems = _call(approvals.gate_problems, trip['id'], target)
            if ok and problems:
                print(_t("status.blocked_now", "Blocking '{status}' right now:").format(status=target))
                _problems(problems, "status.none_blocking", "")
    target = _choose(options)
    if not target:
        return
    if target in ('cancelled', 'archived'):
        print(_t("status.release_warning",
                 "Every current place will be released and what was paid refunded "
                 "(a completed trip's places are kept)."))
        if not _yes("status.confirm", "Continue? (y/n): "):
            return
    reason = _ask("status.reason", "Reason (optional): ")
    ok, outcome = _call(trips.set_trip_status, auth, trip['id'], target, reason)
    if not ok:
        return
    print(_t("status.done", "'{name}' is now {status}.").format(
        name=trip['trip_name'], status=outcome['trip']['status']))
    trips._print_refunds(outcome.get('refunds'))
    trips._print_emailed(outcome.get('emailed'))


def show_trip_history(auth):
    """Every recorded change to a trip, newest first (organisers and approvers)."""
    trip = _pick_trip(auth, manage=not _can(auth, 'manage_trips', *APPROVE), include_archived=True)
    if not trip:
        return
    ok, rows = _call(trips.list_history, auth, trip['id'])
    if not ok:
        return
    print("\n" + _t("history.title", "History of '{name}' ({n} change(s), newest first)").format(
        name=trip['trip_name'], n=len(rows)))
    _rule()
    if not rows:
        print(_t("history.none", "No changes recorded."))
        return
    for start in range(0, len(rows), PAGE_SIZE):
        for r in rows[start:start + PAGE_SIZE]:
            change = (r.get('action') or '').replace('_', ' ')
            if r.get('field'):
                change += f" [{r['field']}]"
            line = f"{(r.get('changed_at') or '')[:16]:<17} {(r.get('changed_by') or '-')[:14]:<15} v{r.get('version') or '-':<4} {change}"
            if r.get('old_value') is not None or r.get('new_value') is not None:
                line += f": {r.get('old_value') if r.get('old_value') is not None else '-'} -> " \
                        f"{r.get('new_value') if r.get('new_value') is not None else '-'}"
            print(line)
        if start + PAGE_SIZE < len(rows) and not _yes("history.more", "Show more? (y/n): "):
            break


def trip_lifecycle_menu():
    auth = _auth()
    if not auth:
        return
    _menu(auth, _t("lifecycle.title", "TRIP DETAILS & STATUS"), _entries(auth, [
        (_t("lifecycle.summary", "Trip summary (approvals, risk, what blocks opening)"), show_trip_summary, ('view_trips',)),
        (_t("lifecycle.settings", "Edit trip settings (type, overseas, safeguarding, money)"), edit_trip_settings, ORGANISE),
        (_t("lifecycle.status", "Change trip status / archive"), change_trip_status, ORGANISE),
        (_t("lifecycle.history", "Trip history (every change, who and when)"), show_trip_history,
         ORGANISE + APPROVE),
    ]))


# ---------------------------------------------------------------------------
# Approvals
# ---------------------------------------------------------------------------

def submit_trip_for_approval(auth):
    trip = _pick_trip(auth, manage=True, statuses=('proposed', 'planning'))
    if not trip:
        return
    ok, state = _call(approvals.submit_for_approval, auth, trip['id'])
    if ok:
        print(_t("approval.submitted", "'{name}' was submitted for approval.").format(name=trip['trip_name']))
        _print_approval_state(state)


def approval_queue(auth):
    """The stages waiting on the signed-in user; approve, reject or return."""
    ok, rows = _call(approvals.pending_for, auth)
    if not ok:
        return
    if not rows:
        print(_t("approval.queue_empty", "Nothing is waiting for your decision."))
        return
    print(f"\n{'#':<4} {_t('head.trip', 'Trip'):<29} {_t('head.stage', 'Stage'):<16} "
          f"{_t('head.dates', 'Dates'):<23} {_t('head.status', 'Status')}")
    _rule(85, "-")
    for i, r in enumerate(rows, 1):
        print(f"{i:<4} {(r['trip_name'] or '')[:28]:<29} {approvals.STAGE_LABELS[r['stage']]:<16} "
              f"{(r['start_date'] or '')[:10]} → {(r['end_date'] or '')[:10]:<10} {r['status']}")
    index = _ask_int("approval.pick", "Item number to decide (blank to go back): ")
    if index is None or not 1 <= index <= len(rows):
        return
    row = rows[index - 1]
    trip = trips.get_trip(row['trip_id'])
    assessment = risk.current(row['trip_id'])
    print(f"\n{trip['trip_name']} — {trip.get('destination') or ''}"
          f"{', ' + trip['country'] if trip.get('country') else ''}")
    print(_t("approval.facts", "Cost {cost}, budget {budget}, {places} places, type {type}").format(
        cost=_money(trip.get('cost')),
        budget=_money(trip['budget']) if trip.get('budget') is not None else '-',
        places=trip.get('max_participants') or 0, type=trip.get('trip_type') or 'day'))
    if trip.get('description'):
        print(trip['description'])
    print(_t("approval.risk", "Risk assessment: {risk}").format(
        risk=f"#{assessment['id']} {assessment['status']}" if assessment else _t("approval.no_risk", "none yet")))
    print(_t("approval.deciding", "\nDeciding the {stage} stage:").format(stage=approvals.STAGE_LABELS[row['stage']]))
    decision = _choose(list(approvals.DECISIONS), [_t("approval.approve", "Approve"),
                                                   _t("approval.reject", "Reject"),
                                                   _t("approval.return", "Return for changes")])
    if not decision:
        return
    comments = _ask("approval.comments", "Comments (needed to reject or return): ")
    ok, state = _call(approvals.decide, auth, row['trip_id'], row['stage'], decision, comments)
    if ok:
        print(_t("approval.recorded", "Decision recorded."))
        _print_approval_state(state)
        if state['complete']:
            print(_t("approval.all_done", "Every stage is approved."))


def show_approval_state(auth):
    trip = _pick_trip(auth, manage=not _can(auth, *APPROVE, 'manage_trips'))
    if not trip:
        return
    ok, state = _call(approvals.approval_state, trip['id'])
    if not ok:
        return
    print(f"\n{trip['trip_name']} ({trip['status']})")
    _print_approval_state(state)
    ok, problems = _call(approvals.gate_problems, trip['id'], 'approved')
    if ok and problems:
        print(_t("approval.blockers", "Still needed for approval:"))
        _problems(problems, "approval.none", "")


def approvals_menu():
    auth = _auth()
    if not auth:
        return
    _menu(auth, _t("approvals.title", "TRIP APPROVALS"), _entries(auth, [
        (_t("approvals.submit", "Submit a trip for approval"), submit_trip_for_approval, ORGANISE),
        (_t("approvals.queue", "My approval queue (approve / reject / return)"), approval_queue, APPROVE),
        (_t("approvals.state", "Approval state of a trip"), show_approval_state, ORGANISE + APPROVE),
    ]))


# ---------------------------------------------------------------------------
# Risk assessment
# ---------------------------------------------------------------------------

def _print_assessment(assessment):
    print(_t("risk.header", "\nRisk assessment #{id} ({template}) — {status}, assessor {assessor}").format(
        id=assessment['id'], template=assessment['template'], status=assessment['status'],
        assessor=assessment.get('assessor') or '-'))
    print(_t("risk.residual", "Overall residual risk: {band}").format(
        band=assessment.get('overall_residual') or assessment.get('computed_residual') or '-'))
    if assessment.get('signed_off_by'):
        print(_t("risk.signed", "Decided by {who} on {when}").format(
            who=assessment['signed_off_by'], when=str(assessment.get('signed_off_at') or '')[:16]))
    if assessment.get('review_notes'):
        print(_t("risk.notes", "Notes: {notes}").format(notes=assessment['review_notes']))
    for item in assessment.get('items') or ():
        print(f"\n  #{item['id']} {item['hazard']}")
        print(_t("risk.item_line", "     who: {who} | before {l}x{s}={score} → after {rl}x{rs}={rscore} ({band}) | owner: {owner}").format(
            who=item.get('who_at_risk') or '-', l=item['likelihood'], s=item['severity'], score=item['score'],
            rl=item.get('residual_likelihood') or item['likelihood'],
            rs=item.get('residual_severity') or item['severity'],
            rscore=item['residual_score'], band=item['residual_band'], owner=item.get('owner') or '-'))
        if item.get('controls'):
            print(_t("risk.controls", "     controls: {controls}").format(controls=item['controls']))
    if not assessment.get('items'):
        print(_t("risk.no_items", "  (no hazards yet)"))


def _ask_item(current=None):
    """Item fields; with ``current`` blank keeps a value and only changes are returned."""
    current = current or {}
    fields = {}
    for name, label in (('hazard', "Hazard"), ('who_at_risk', "Who is at risk"),
                        ('controls', "Controls"), ('likelihood', "Likelihood before controls (1-5)"),
                        ('severity', "Severity before controls (1-5)"),
                        ('residual_likelihood', "Likelihood after controls (1-5, blank = same)"),
                        ('residual_severity', "Severity after controls (1-5, blank = same)"),
                        ('owner', "Owner")):
        shown = f" [{current[name]}]" if current.get(name) not in (None, '') else ''
        raw = input(f"{_t('risk.field.' + name, label)}{shown}: ").strip()
        if raw:
            fields[name] = raw
    return fields


def _create_assessment(auth, trip):
    for name in risk.TEMPLATE_NAMES:
        count = len(risk.TEMPLATES.get(name, ()))
        print(_t("risk.template_line", "  {name}: {count} starting hazards").format(name=name, count=count))
    template = _choose(list(risk.TEMPLATE_NAMES))
    if template:
        ok, assessment = _call(risk.create_assessment, auth, trip['id'], template)
        if ok:
            _print_assessment(assessment)


def _add_item(auth, assessment):
    fields = _ask_item()
    if not fields.get('hazard'):
        print(_t("risk.need_hazard", "Describe the hazard."))
        return
    ok, item_id = _call(risk.add_item, auth, assessment['id'], **fields)
    if ok:
        print(_t("risk.item_added", "Hazard #{id} added.").format(id=item_id))


def _pick_item(assessment):
    item_id = _ask_int("risk.pick_item", "Hazard # (blank to go back): ")
    item = next((i for i in assessment.get('items') or () if i['id'] == item_id), None)
    if item_id is not None and not item:
        print(_t("risk.no_such_item", "That hazard is not on this assessment."))
    return item


def _edit_item(auth, assessment):
    item = _pick_item(assessment)
    if not item:
        return
    fields = _ask_item(item)
    if not fields:
        print(get_text("mobility.trip_management.update.no_changes", "No changes to update."))
        return
    if _call(risk.update_item, auth, item['id'], **fields)[0]:
        print(_t("risk.item_updated", "Hazard updated."))


def _remove_item(auth, assessment):
    item = _pick_item(assessment)
    if item and _yes("risk.confirm_remove", "Remove this hazard? (y/n): "):
        if _call(risk.remove_item, auth, item['id'])[0]:
            print(_t("risk.item_removed", "Hazard removed."))


def _submit_assessment(auth, assessment):
    ok, updated = _call(risk.submit, auth, assessment['id'])
    if ok:
        print(_t("risk.submitted", "Submitted for Health & Safety sign-off (residual {band}).").format(
            band=updated.get('overall_residual') or '-'))


def _earlier_assessments(auth, trip):
    for row in risk.list_assessments(trip['id']):
        print(f"  #{row['id']} {row['template']:<10} {row['status']:<11} {str(row.get('created_at') or '')[:10]} "
              f"{row.get('overall_residual') or ''}")


def work_on_risk_assessment(auth):
    """Create from a template, edit hazards and submit — for one trip."""
    trip = _pick_trip(auth, manage=True)
    if not trip:
        return
    actions = [
        ('create', _t("risk.act.create", "Start a new assessment from a template")),
        ('add', _t("risk.act.add", "Add a hazard")),
        ('edit', _t("risk.act.edit", "Edit a hazard")),
        ('remove', _t("risk.act.remove", "Remove a hazard")),
        ('submit', _t("risk.act.submit", "Submit for sign-off")),
        ('history', _t("risk.act.history", "Earlier assessments")),
    ]
    while True:
        assessment = risk.current(trip['id'])
        if assessment:
            _print_assessment(assessment)
        else:
            print(_t("risk.none", "\nThis trip has no risk assessment yet."))
        print()
        action = _choose([a for a, _label in actions], [label for _a, label in actions],
                         key="risk.choose", default="Action (1-{max}, blank when done): ")
        if not action:
            return
        if action == 'create':
            _create_assessment(auth, trip)
        elif action == 'history':
            _earlier_assessments(auth, trip)
        elif not assessment:
            print(_t("risk.create_first", "Start an assessment first."))
        elif action == 'add':
            _add_item(auth, assessment)
        elif action == 'edit':
            _edit_item(auth, assessment)
        elif action == 'remove':
            _remove_item(auth, assessment)
        elif action == 'submit':
            _submit_assessment(auth, assessment)


def _submitted_assessments(auth):
    rows = []
    for trip in _trip_rows(auth, False, None, False):
        assessment = risk.current(trip['id'])
        if assessment and assessment['status'] == 'submitted':
            rows.append((trip, assessment))
    return rows


def risk_sign_off_queue(auth):
    """Health & Safety: sign off or return submitted assessments."""
    ok, rows = _call(_submitted_assessments, auth)
    if not ok:
        return
    if not rows:
        print(_t("risk.queue_empty", "No risk assessments are waiting for sign-off."))
        return
    for i, (trip, assessment) in enumerate(rows, 1):
        print(f"{i:<4} {(trip['trip_name'] or '')[:30]:<31} #{assessment['id']:<5} "
              f"{assessment.get('overall_residual') or '-':<7} {assessment.get('assessor') or ''}")
    index = _ask_int("risk.pick_queue", "Item number (blank to go back): ")
    if index is None or not 1 <= index <= len(rows):
        return
    trip, assessment = rows[index - 1]
    print(f"\n{trip['trip_name']} — {trip.get('destination') or ''} ({trip.get('start_date')})")
    _print_assessment(assessment)
    decision = _choose(['signed_off', 'returned'], [_t("risk.sign", "Sign off"),
                                                    _t("risk.return", "Return to the assessor")])
    if not decision:
        return
    notes = _ask("risk.decision_notes", "Notes (needed to return, or to sign off a high residual risk): ")
    ok, updated = _call(risk.sign_off, auth, assessment['id'], decision, notes)
    if ok:
        print(_t("risk.decided", "Assessment #{id} is now {status}.").format(id=updated['id'], status=updated['status']))


def view_risk_assessment(auth):
    trip = _pick_trip(auth, manage=not _can(auth, 'manage_trips', *HS, *APPROVE), include_archived=True)
    if not trip:
        return
    assessment = risk.current(trip['id'])
    if not assessment:
        print(_t("risk.none", "\nThis trip has no risk assessment yet."))
        return
    _print_assessment(assessment)


def risk_menu():
    auth = _auth()
    if not auth:
        return
    _menu(auth, _t("risk.title", "RISK ASSESSMENT"), _entries(auth, [
        (_t("risk.work", "Create / edit / submit a trip's risk assessment"), work_on_risk_assessment, ORGANISE),
        (_t("risk.queue", "Sign-off queue (sign off / return)"), risk_sign_off_queue, HS),
        (_t("risk.view", "View a trip's risk assessment"), view_risk_assessment, ORGANISE + HS + APPROVE),
    ]))


# ---------------------------------------------------------------------------
# Incidents
# ---------------------------------------------------------------------------

def report_trip_incident(auth):
    trip = _pick_trip(auth, statuses=('approved', 'open', 'full', 'closed', 'in_progress', 'completed'))
    if not trip:
        return
    print(_t("incident.kind", "\nWhat happened?"))
    kind = _choose(list(incidents.KINDS))
    if not kind:
        return
    print(_t("incident.severity", "How serious?"))
    severity = _choose(list(incidents.SEVERITIES))
    if not severity:
        return
    description = _ask("incident.description", "Description: ")
    occurred_at = _ask("incident.when", "When (YYYY-MM-DD HH:MM, blank = now): ") or None
    location = _ask("incident.where", "Where: ")
    persons = _ask("incident.persons", "People involved: ")
    actions = _ask("incident.actions", "Action taken: ")
    riddor_raw = _ask("incident.riddor", "RIDDOR reportable? (y/n, blank = work it out): ").lower()
    riddor = None if not riddor_raw else riddor_raw in ('y', 'yes')
    subject_id = None
    if kind == 'conduct':
        subject_id = _ask("incident.subject", "Student number of the student concerned: ") or None
    ok, incident_id = _call(incidents.report_incident, auth, trip['id'], kind, severity, description,
                            occurred_at, location, persons, actions, riddor, subject_id=subject_id)
    if ok:
        print(_t("incident.reported", "Incident #{id} recorded.").format(id=incident_id))
        if severity in incidents.HS_SEVERITIES or kind in ('injury', 'safeguarding', 'conduct'):
            print(_t("incident.routed", "It has been passed on to the team that must act on it."))


def _print_incidents(rows):
    for r in rows:
        print(f"\n#{r['id']} {r['kind']} / {r['severity']} — {r['status']} "
              f"({str(r.get('occurred_at') or r.get('reported_at') or '')[:16]}, {r.get('reported_by') or ''})")
        print(f"   {r.get('description') or ''}")
        extras = [f"{label}: {r[key]}" for key, label in (
            ('location', 'where'), ('actions_taken', 'action'), ('hs_reference', 'H&S'),
            ('conduct_case_ref', 'case'), ('review_notes', 'review')) if r.get(key)]
        if r.get('riddor_reportable'):
            extras.append("RIDDOR")
        if extras:
            print("   " + " | ".join(extras))


def list_trip_incidents(auth):
    trip = _pick_trip(auth, include_archived=True)
    if not trip:
        return None, []
    ok, rows = _call(incidents.list_incidents, auth, trip['id'])
    if not ok:
        return trip, []
    if not rows:
        print(_t("incident.none", "No incidents recorded for this trip."))
    _print_incidents(rows)
    return trip, rows


def review_trip_incident(auth):
    trip, rows = list_trip_incidents(auth)
    open_rows = [r for r in rows if r['status'] != 'closed']
    if not open_rows:
        if trip:
            print(_t("incident.none_open", "No open incidents to review."))
        return
    incident_id = _ask_int("incident.pick", "\nIncident # to review (blank to go back): ")
    if incident_id not in {r['id'] for r in open_rows}:
        return
    notes = _ask("incident.notes", "Review notes: ")
    close = _yes("incident.close", "Close the incident? (y/n — n keeps it under review): ")
    ok, row = _call(incidents.review_incident, auth, incident_id, notes, close)
    if ok:
        print(_t("incident.reviewed", "Incident #{id} is now {status}.").format(id=row['id'], status=row['status']))


def incidents_menu():
    auth = _auth()
    if not auth:
        return
    _menu(auth, _t("incidents.title", "TRIP INCIDENTS"), _entries(auth, [
        (_t("incidents.report", "Report an incident"), report_trip_incident, ('view_trips',)),
        (_t("incidents.list", "Incidents on a trip"), lambda a: list_trip_incidents(a), ('view_trips',)),
        (_t("incidents.review", "Review / close an incident"), review_trip_incident, ORGANISE + HS),
    ]))


# ---------------------------------------------------------------------------
# Safeguarding and staffing
# ---------------------------------------------------------------------------

def staffing_check(auth):
    trip = _pick_trip(auth, manage=not _can(auth, 'manage_trips', *HS))
    if not trip:
        return
    ok, problems = _call(safeguarding.staffing_check, trip['id'])
    if ok:
        _problems(problems, "safe.staffing_ok", "Staffing is fine: ratio, first aid and DBS checks pass.")


def refresh_staff_checks(auth):
    trip = _pick_trip(auth, manage=True)
    if not trip:
        return
    ok, problems = _call(safeguarding.refresh_staff_checks, auth, trip['id'])
    if ok:
        print(_t("safe.refreshed", "DBS and first-aid records re-checked and saved on the trip's staff."))
        _problems(problems, "safe.staffing_ok", "Staffing is fine: ratio, first aid and DBS checks pass.")


def participant_checks(auth):
    trip = _pick_trip(auth, manage=True)
    if not trip:
        return
    ok, rows = _call(safeguarding.participant_checks, trip['id'])
    if not ok:
        return
    if not rows:
        print(_t("safe.participants_ok", "No participant is missing a consent or code-of-conduct acceptance."))
    for row in rows:
        print(f"  {row['participant_id']:<6} {row.get('student_id') or '':<11} " + "; ".join(row['problems']))


def accept_code_of_conduct(auth):
    row = _pick_my_place(auth, statuses=('registered', 'offered', 'confirmed', 'waitlisted'))
    if not row:
        return
    print(_t("safe.conduct_text",
             "By accepting you agree to follow the trip code of conduct, the leaders' instructions and "
             "the university's student conduct rules for the whole trip."))
    if _yes("safe.conduct_confirm", "Do you accept? (y/n): "):
        if _call(safeguarding.record_conduct_acceptance, auth, row['participant_id'])[0]:
            print(_t("safe.conduct_done", "Thank you — your acceptance is recorded."))


def record_signed_conduct(auth):
    trip = _pick_trip(auth, manage=True)
    row = trip and _pick_participant(auth, trip)
    if row and _call(safeguarding.record_conduct_acceptance, auth, row['id'])[0]:
        print(_t("safe.conduct_recorded", "Signed code of conduct recorded for {name}.").format(name=row.get('name')))


def record_parental_consent(auth):
    trip = _pick_trip(auth, manage=True)
    row = trip and _pick_participant(auth, trip)
    if not row:
        return
    adult = _ask("safe.consent_name", "Name of the parent / guardian who consented: ")
    if adult and _call(safeguarding.record_parental_consent, auth, row['id'], adult)[0]:
        print(_t("safe.consent_done", "Parental consent recorded for {name}.").format(name=row.get('name')))


def safeguarding_menu():
    auth = _auth()
    if not auth:
        return
    _menu(auth, _t("safe.title", "SAFEGUARDING & STAFFING"), _entries(auth, [
        (_t("safe.staffing", "Staffing check (ratio, first aider, DBS)"), staffing_check, ORGANISE + HS),
        (_t("safe.refresh", "Refresh staff DBS / first-aid records"), refresh_staff_checks, ORGANISE),
        (_t("safe.participants", "Participant checks (consents, code of conduct)"), participant_checks, PEOPLE),
        (_t("safe.accept", "Accept the code of conduct for my place"), accept_code_of_conduct, ('register_for_trips',)),
        (_t("safe.signed", "Record a signed code of conduct for a participant"), record_signed_conduct, PEOPLE),
        (_t("safe.consent", "Record parental consent (under-18s)"), record_parental_consent, PEOPLE),
    ]))


# ---------------------------------------------------------------------------
# Overseas travel
# ---------------------------------------------------------------------------

def record_fcdo_check(auth):
    trip = _pick_trip(auth, manage=not _can(auth, 'manage_trips', 'approve_trips_international'))
    if not trip:
        return
    country = trip.get('country') or trip.get('destination') or ''
    url = overseas.advice_url(country)
    print(_t("overseas.read_advice", "\nRead the current GOV.UK travel advice for {country}:").format(country=country))
    print(f"  {url or overseas.ADVICE_BASE_URL}")
    level = _choose(list(overseas.FCDO_LEVELS), [overseas.FCDO_LABELS[k] for k in overseas.FCDO_LEVELS])
    if not level:
        return
    checked_at = _ask("overseas.checked_at", "Date you read it (YYYY-MM-DD, blank = today): ") or None
    ok, out = _call(overseas.record_fcdo_check, auth, trip['id'], level, checked_at)
    if ok:
        print(_t("overseas.recorded", "FCDO check recorded: {label}").format(label=overseas.FCDO_LABELS[level]))
        print(_t("overseas.link", "GOV.UK advice: {url}").format(url=out.get('advice_url') or url))
        if level == 'all_travel':
            print(_t("overseas.all_travel", "The FCDO advises against all travel: the trip cannot open."))


def record_insurance(auth):
    trip = _pick_trip(auth, manage=True)
    if not trip:
        return
    reference = _ask("overseas.insurance", "Travel insurance registration reference: ")
    if reference and _call(overseas.record_insurance, auth, trip['id'], reference)[0]:
        print(_t("overseas.insurance_done", "Insurance reference recorded."))


def participant_documents(auth):
    pid = _pick_any_place(auth)
    if not pid:
        return
    expiry = _ask("overseas.passport", "Passport expiry date (YYYY-MM-DD): ")
    print(_t("overseas.visa", "Visa status:"))
    visa = _choose(list(overseas.VISA_STATUSES))
    if not visa:
        return
    ok, problems = _call(overseas.participant_documents, auth, pid, expiry, visa)
    if ok:
        print(_t("overseas.docs_done", "Travel documents recorded."))
        _problems(problems, "overseas.docs_ok", "Nothing else is needed for this participant.")


def overseas_problems(auth):
    trip = _pick_trip(auth, manage=not _can(auth, 'manage_trips', 'approve_trips_international'))
    if not trip:
        return
    if not trip.get('is_overseas'):
        print(_t("overseas.not_overseas", "This trip is not marked overseas (Edit trip settings)."))
        return
    ok, problems = _call(overseas.overseas_problems, trip['id'])
    if ok:
        print(_t("overseas.fcdo_line", "FCDO: {level} (checked {when}); insurance: {ins}").format(
            level=trip.get('fcdo_advice_level') or '-', when=str(trip.get('fcdo_checked_at') or '-')[:10],
            ins=trip.get('insurance_reference') or '-'))
        _problems(problems, "overseas.ok", "No overseas problems.")


def overseas_menu():
    auth = _auth()
    if not auth:
        return
    intl = ORGANISE + ('approve_trips_international',)
    _menu(auth, _t("overseas.title", "OVERSEAS TRAVEL"), _entries(auth, [
        (_t("overseas.fcdo", "Record FCDO advice check"), record_fcdo_check, intl),
        (_t("overseas.ins", "Record travel insurance"), record_insurance, ORGANISE),
        (_t("overseas.docs", "Passport and visa details"), participant_documents, ('view_trips',)),
        (_t("overseas.problems", "Overseas problems for a trip"), overseas_problems, intl),
    ]))


# ---------------------------------------------------------------------------
# Academic links
# ---------------------------------------------------------------------------

def link_module(auth):
    trip = _pick_trip(auth, manage=True)
    if not trip:
        return
    print(_t("academic.current", "Currently linked: {module}").format(module=trip.get('module_code') or '-'))
    code = _ask("academic.module", "Module code ('none' to unlink, blank to go back): ")
    if not code:
        return
    code = None if code.lower() == 'none' else code
    ok, updated = _call(academic.link_module, auth, trip['id'], code)
    if ok:
        print(_t("academic.linked", "Linked module: {module}").format(module=updated.get('module_code') or '-'))


def toggle_attendance(auth):
    trip = _pick_trip(auth, manage=True)
    if not trip:
        return
    print(_t("academic.counts_now", "Counts as attendance now: {now}").format(
        now=_t("common.yes", "yes") if trip.get('counts_as_attendance') else _t("common.no", "no")))
    raw = _ask("academic.counts", "Count the trip as attendance for its module? (y/n): ").lower()
    if raw not in ('y', 'yes', 'n', 'no'):
        return
    ok, updated = _call(academic.set_counts_as_attendance, auth, trip['id'], raw in ('y', 'yes'))
    if ok:
        print(_t("academic.counts_done", "Saved: counts as attendance = {value}.").format(
            value=bool(updated.get('counts_as_attendance'))))


def timetable_clashes(auth):
    trip = _pick_trip(auth, manage=True)
    if not trip:
        return
    ok, rows = _call(academic.timetable_clashes, trip['id'])
    if not ok:
        return
    if not rows:
        print(_t("academic.no_clashes", "No participant has timetabled sessions during the trip."))
    for row in rows:
        print(f"\n{row.get('name') or ''} ({row.get('student_id') or ''})")
        for s in row['sessions']:
            mark = _t("academic.linked_mark", " [this trip's module]") if s.get('linked_module') else ''
            print(f"   {s['date']} {s.get('start_time') or ''}-{s.get('end_time') or ''} "
                  f"{s.get('module_code') or ''} {s.get('room') or ''}{mark}")


def academic_menu():
    auth = _auth()
    if not auth:
        return
    _menu(auth, _t("academic.title", "ACADEMIC LINKS"), _entries(auth, [
        (_t("academic.link", "Link the trip to a module"), link_module, ORGANISE),
        (_t("academic.attendance", "Count the trip as module attendance"), toggle_attendance, ORGANISE),
        (_t("academic.clashes", "Timetable clashes"), timetable_clashes, ORGANISE),
    ]))


# ---------------------------------------------------------------------------
# Places, waiting list and payments
# ---------------------------------------------------------------------------

def waitlist_positions(auth):
    """Organisers: the trip's waiting list in order."""
    trip = _pick_trip(auth, manage=True)
    if not trip:
        return
    rows = waitlist.positions(trip['id'])
    if not rows:
        print(_t("places.no_waitlist", "Nobody is on the waiting list."))
    for row in rows:
        print(f"  {row['place']:<4} #{row['participant_id']:<6} {(row['name'] or '')[:30]:<31} "
              f"{str(row.get('waitlisted_at') or '')[:16]}")


def my_waitlist_places(auth):
    """Students: where they stand on each waiting list (no other names)."""
    ok, rows = _call(registrations.list_my_registrations, auth)
    if not ok:
        return
    rows = [r for r in rows if r['status'] in ('waitlisted', 'offered')]
    if not rows:
        print(_t("places.not_waiting", "You are not on any waiting list."))
    for r in rows:
        if r['status'] == 'offered':
            place = registrations.get_participant(r['participant_id'])
            print(_t("places.offered", "{trip}: a place is offered to you — accept by {until}.").format(
                trip=r['trip_name'], until=str(place.get('offer_expires_at') or '')[:16]))
            continue
        position = next((p['place'] for p in waitlist.positions(r['trip_id'])
                         if p['participant_id'] == r['participant_id']), None)
        print(_t("places.position", "{trip}: number {position} on the waiting list.").format(
            trip=r['trip_name'], position=position or '?'))


def _pay(auth, participant_id):
    """Take a payment towards a place (input first, then one domain call)."""
    place = registrations.get_participant(participant_id)
    trip = trips.get_trip(place['trip_id']) if place else None
    if not trip:
        print(get_text("mobility.trip_management.participants.not_found", "Participant not found."))
        return
    owed = money.amount_owed(place, trip)
    if owed <= 0:
        print(_t("places.nothing_owed", "Nothing is owed for this place."))
        return
    amount = _ask_amount("places.amount", f"Amount to pay (blank = all £{owed:.2f}): ")
    amount = owed if amount is None else amount
    balance = payments.account_balance(place['student_id']) if place.get('student_id') else None
    method = payments.select_payment_method(amount, balance=balance)
    if not method:
        return
    ok, outcome = _call(payments.pay_for_registration, auth, participant_id, method, amount)
    if not ok:
        return
    if outcome.get('success'):
        print(_t("places.paid", "Paid {amount} ({method}). Still owed: {owed}.").format(
            amount=_money(outcome['amount']), method=payments.method_label(method), owed=_money(outcome['owed'])))
    else:
        print(_t("places.pay_failed", "The payment did not go through: {message}").format(
            message=outcome.get('message') or ''))


def accept_offer(auth):
    row = _pick_my_place(auth, statuses=('offered',))
    if not row:
        return
    if not _yes("places.accept_confirm", "Accept this place? (y/n): "):
        return
    ok, place = _call(waitlist.accept_offer, auth, row['participant_id'])
    if not ok:
        return
    print(_t("places.accepted", "The place on '{trip}' is yours.").format(trip=row['trip_name']))
    if float(row.get('cost') or 0) > 0 and _yes("places.pay_now", "Pay now? (y/n): "):
        _pay(auth, row['participant_id'])


def decline_offer(auth):
    row = _pick_my_place(auth, statuses=('offered',))
    if not row:
        return
    reason = _ask("places.decline_reason", "Reason (optional): ")
    if _yes("places.decline_confirm", "Turn the place down? It goes to the next person. (y/n): "):
        if _call(waitlist.decline_offer, auth, row['participant_id'], reason)[0]:
            print(_t("places.declined", "Offer declined."))


def pay_my_place(auth):
    row = _pick_my_place(auth, statuses=('registered', 'confirmed', 'attended'))
    if row:
        _pay(auth, row['participant_id'])


def record_participant_payment(auth):
    trip = _pick_trip(auth, manage=True)
    row = trip and _pick_participant(auth, trip, statuses=('registered', 'confirmed', 'attended'))
    if row:
        _pay(auth, row['id'])


def what_i_owe(auth):
    ok, rows = _call(registrations.list_my_registrations, auth)
    if not ok:
        return
    rows = [r for r in rows if r['status'] in ('registered', 'confirmed', 'attended')]
    if not rows:
        print(_t("places.no_places", "You hold no trip places."))
    for r in rows:
        place = registrations.get_participant(r['participant_id'])
        trip = trips.get_trip(r['trip_id'])
        print(_t("places.owe_line", "\n{trip} ({start}): cost {cost}, paid {paid}, support {award}, owed {owed}").format(
            trip=r['trip_name'], start=(r.get('start_date') or '')[:10], cost=_money(trip.get('cost')),
            paid=_money(float(place.get('amount_paid') or 0) - float(place.get('amount_refunded') or 0)),
            award=_money(place.get('hardship_award')), owed=_money(money.amount_owed(place, trip))))
        for item in money.instalment_schedule(r['participant_id']):
            state = _t("places.covered", "covered") if item['paid'] else _t("places.due", "due")
            print(f"   {item['due_date'] or '':<11} {item['label'] or '':<24} {_money(item['amount']):>9}  {state}")


def hardship_award(auth):
    trip = _pick_trip(auth, manage=True)
    row = trip and _pick_participant(auth, trip, statuses=('registered', 'offered', 'confirmed'))
    if not row:
        return
    amount = _ask_amount("places.hardship_amount", "Award amount: ")
    if amount is None:
        return
    application_id = _ask_int("places.hardship_app", "Finance hardship application ID (blank if none): ")
    note = _ask("places.hardship_note", "Note: ")
    ok, place = _call(money.apply_hardship, auth, row['id'], amount, application_id=application_id, note=note)
    if ok:
        print(_t("places.hardship_done", "Award of {amount} recorded; payment status {status}.").format(
            amount=_money(amount), status=place.get('payment_status') or '-'))


def places_menu():
    auth = _auth()
    if not auth:
        return
    own = ('register_for_trips', 'view_own_trip_registrations')
    _menu(auth, _t("places.title", "PLACES, WAITING LIST & PAYMENTS"), _entries(auth, [
        (_t("places.my_waiting", "My waiting-list positions and offers"), my_waitlist_places, own),
        (_t("places.accept", "Accept an offered place"), accept_offer, own),
        (_t("places.decline", "Decline an offered place"), decline_offer, own),
        (_t("places.pay", "Pay for my place"), pay_my_place, own),
        (_t("places.owe", "What I owe and my instalments"), what_i_owe, own),
        (_t("places.waitlist", "A trip's waiting list"), waitlist_positions, PEOPLE),
        (_t("places.record_payment", "Record a payment for a participant"), record_participant_payment, PEOPLE),
        (_t("places.hardship", "Hardship award for a participant"), hardship_award, MONEY),
    ]))


# ---------------------------------------------------------------------------
# Health and dietary details (special-category data)
# ---------------------------------------------------------------------------

_HEALTH_FIELDS = (
    ('medical_info', "Medical information"),
    ('dietary_requirements', "Dietary requirements"),
    ('accessibility_needs', "Accessibility needs"),
    ('emergency_contact_name', "Emergency contact name"),
    ('emergency_contact_relationship', "Their relationship to you"),
    ('emergency_contact_phone', "Their phone number"),
)

_AUDIT_NOTICE = ("These details are special-category health data. Viewing them is recorded in the "
                 "audit log with your name; use them only to keep participants safe on this trip.")


def view_my_health(auth):
    row = _pick_my_place(auth)
    if not row:
        return
    ok, details = _call(medical.my_health_details, auth, row['participant_id'])
    if not ok:
        return
    print()
    for name, label in _HEALTH_FIELDS:
        print(f"{_t('health.' + name, label)}: {details.get(name) or '-'}")
    print(_t("health.consent", "Health record sharing: {state}").format(
        state=_t("health.consented", "agreed {when}").format(when=str(details['health_share_consent_at'])[:16])
        if details.get('health_share_consent_at') else _t("health.not_consented", "not agreed")))


def edit_my_health(auth):
    row = _pick_my_place(auth, statuses=('registered', 'offered', 'confirmed', 'waitlisted'))
    if not row:
        return
    print(_t("health.edit_intro", "Leave blank to keep what is recorded; '-' clears it."))
    changes = {}
    for name, label in _HEALTH_FIELDS:
        raw = input(f"{_t('health.' + name, label)}: ").strip()
        if raw:
            changes[name] = None if raw == '-' else raw
    if not changes:
        print(get_text("mobility.trip_management.update.no_changes", "No changes to update."))
        return
    if _call(medical.update_health_details, auth, row['participant_id'], **changes)[0]:
        print(_t("health.saved", "Your details are saved (stored encrypted)."))


def health_sharing_consent(auth):
    row = _pick_my_place(auth, statuses=('registered', 'offered', 'confirmed', 'waitlisted'))
    if not row:
        return
    print(_t("health.consent_text",
             "If you agree, your allergies, conditions, medication and primary emergency contact can be "
             "copied from your university health record onto this trip registration."))
    raw = _ask("health.consent_prompt", "Agree (a), withdraw (w), or blank to go back: ").lower()
    if raw not in ('a', 'w'):
        return
    if _call(medical.give_health_share_consent, auth, row['participant_id'], raw == 'a')[0]:
        print(_t("health.consent_saved", "Saved."))


def import_from_health_record(auth):
    row = _pick_my_place(auth, statuses=('registered', 'offered', 'confirmed', 'waitlisted'))
    if not row:
        return
    ok, filled = _call(medical.import_from_health_record, auth, row['participant_id'])
    if ok:
        if filled:
            print(_t("health.imported", "Copied from your health record: {fields}").format(
                fields=", ".join(f.replace('_', ' ') for f in filled)))
        else:
            print(_t("health.nothing_imported", "Your health record had nothing new to copy."))


def medical_sheet(auth):
    """Leaders and the health team: the restricted medical & dietary sheet."""
    trip = _pick_trip(auth, manage=not _can(auth, 'manage_trips') and _can(auth, *ORGANISE))
    if not trip:
        return
    print("\n" + _t("health.audit_notice", _AUDIT_NOTICE))
    if not _yes("health.audit_confirm", "Show the details? (y/n): "):
        return
    ok, rows = _call(medical.participant_health, auth, trip['id'])
    if not ok:
        return
    if not rows:
        print(_t("pick.no_participants", "No participants to choose from."))
    for r in rows:
        print(f"\n{r.get('name') or ''} ({r.get('student_id') or '-'}) — {r['status']}")
        for name, label in _HEALTH_FIELDS[:3]:
            if r.get(name):
                print(f"   {_t('health.' + name, label)}: {r[name]}")
        contact = " ".join(x for x in (r.get('emergency_contact_name'),
                                       f"({r['emergency_contact_relationship']})" if r.get('emergency_contact_relationship') else '',
                                       r.get('emergency_contact_phone')) if x) or r.get('emergency_contact')
        print(f"   {_t('health.contact', 'Emergency contact')}: {contact or '-'}")


def health_counts(auth):
    trip = _pick_trip(auth, manage=True)
    if not trip:
        return
    counts = medical.counts(trip['id'])
    for name, label in _HEALTH_FIELDS[:3]:
        print(f"  {_t('health.' + name, label)}: {counts.get(name, 0)}")


def health_menu():
    auth = _auth()
    if not auth:
        return
    own = ('register_for_trips', 'view_own_trip_registrations')
    spec = [
        (_t("health.view", "View my health details for a trip"), view_my_health, own),
        (_t("health.edit", "Edit my health details for a trip"), edit_my_health, own),
        (_t("health.share", "Agree to share my health record with a trip"), health_sharing_consent, own),
        (_t("health.import", "Copy details from my health record"), import_from_health_record, own),
        (_t("health.counts", "How many participants have details recorded"), health_counts, ORGANISE),
    ]
    if not _is_student(auth):
        spec.append((_t("health.sheet", "Medical & dietary sheet (restricted, audited)"), medical_sheet,
                     ('view_trips',)))
    _menu(auth, _t("health.title", "HEALTH & DIETARY DETAILS"), _entries(auth, spec))


# ---------------------------------------------------------------------------
# Communications
# ---------------------------------------------------------------------------

def notify_participants(auth):
    trip = _pick_trip(auth, manage=True)
    if not trip:
        return
    subject = _ask("comms.subject", "Subject: ")
    body = _ask_lines("comms.body", "Message (finish with a line holding only '.'):")
    if not subject or not body:
        print(_t("comms.need_both", "A subject and a message are both needed."))
        return
    ok, sent = _call(comms.notify_participants, auth, trip['id'], subject, body)
    if ok:
        print(_t("comms.sent", "{count} e-mail(s) sent.").format(count=sent))


def change_notice(auth):
    trip = _pick_trip(auth, manage=True)
    if not trip:
        return
    what = _ask_lines("comms.what_changed", "What has changed (finish with a line holding only '.'):")
    if not what:
        return
    ok, sent = _call(comms.change_notice, auth, trip['id'], what)
    if ok:
        print(_t("comms.sent", "{count} e-mail(s) sent.").format(count=sent))


def show_itinerary_pack(auth):
    trip = _pick_trip(auth)
    if trip:
        ok, text = _call(comms.itinerary_pack, trip['id'])
        if ok:
            print("\n" + text)


def show_emergency_card(auth):
    trip = _pick_trip(auth)
    if trip:
        ok, card = _call(rollcall.emergency_card, trip['id'])
        if ok:
            print()
            _rule(60)
            print(card['text'])
            _rule(60)


def communications_menu():
    auth = _auth()
    if not auth:
        return
    _menu(auth, _t("comms.title", "TRIP COMMUNICATIONS"), _entries(auth, [
        (_t("comms.notify", "E-mail everyone on a trip"), notify_participants, ORGANISE),
        (_t("comms.change", "Send a change notice"), change_notice, ORGANISE),
        (_t("comms.pack", "Itinerary pack"), show_itinerary_pack, ('view_trips',)),
        (_t("comms.card", "Emergency card"), show_emergency_card, ('view_trips',)),
    ]))


# ---------------------------------------------------------------------------
# On the day: roll call
# ---------------------------------------------------------------------------

def _print_missing(rollcall_id):
    rows = rollcall.missing(rollcall_id)
    if not rows:
        print(_t("day.all_present", "Everyone is accounted for."))
        return rows
    print(_t("day.missing", "\nNOT PRESENT ({n}):").format(n=len(rows)))
    for r in rows:
        contact = " ".join(x for x in (r.get('emergency_contact_name'), r.get('emergency_contact_phone')) if x)
        print(f"  #{r['participant_id']:<6} {(r.get('name') or '')[:28]:<29} {contact or '-'}"
              f"{'  — ' + r['note'] if r.get('note') else ''}")
    return rows


def _mark_people(auth, rollcall_id, people):
    """Ask about everyone first, then record each answer (one short write each)."""
    print(_t("day.mark_help", "For each person: y = present, n = not present, blank = skip; "
                              "add a note after a colon, e.g. 'n: at the hospital with Sam'."))
    answers = []
    for person in people:
        raw = input(f"  {(person.get('name') or '')[:30]:<31} ").strip()
        if not raw:
            continue
        mark, _, note = raw.partition(':')
        if mark.strip().lower() in ('y', 'yes', 'n', 'no'):
            answers.append((person['participant_id'], mark.strip().lower() in ('y', 'yes'), note.strip()))
    saved = 0
    for participant_id, present, note in answers:
        if _call(rollcall.mark, auth, rollcall_id, participant_id, present, note)[0]:
            saved += 1
    print(_t("day.saved", "{n} mark(s) saved.").format(n=saved))


def take_rollcall(auth):
    trip = _pick_trip(auth, manage=True, statuses=('approved', 'open', 'full', 'closed', 'in_progress'))
    if not trip:
        return
    label = _ask("day.label", "Label (e.g. 'Coach departure', blank = time now): ")
    ok, rollcall_id = _call(rollcall.start_rollcall, auth, trip['id'], label)
    if not ok:
        return
    ok, people = _call(registrations.list_participants, auth, trip['id'])
    if not ok:
        return
    people = [{'participant_id': p['id'], 'name': p.get('name')} for p in people
              if p['status'] in rollcall.ON_ROLL]
    print(_t("day.started", "Roll call #{id} started: {n} on the list.").format(id=rollcall_id, n=len(people)))
    _mark_people(auth, rollcall_id, people)
    _print_missing(rollcall_id)


def _pick_rollcall(auth):
    trip = _pick_trip(auth, manage=True, include_archived=True)
    if not trip:
        return None
    rows = rollcall.list_rollcalls(trip['id'])
    if not rows:
        print(_t("day.none", "No roll calls taken for this trip."))
        return None
    for r in rows:
        print(f"  #{r['id']:<5} {str(r['taken_at'])[:16]} {(r.get('label') or '')[:30]:<31} "
              f"{r['present']}/{r['total']} {r.get('taken_by') or ''}")
    rollcall_id = _ask_int("day.pick", "Roll call # (blank to go back): ")
    return rollcall_id if rollcall_id in {r['id'] for r in rows} else None


def continue_rollcall(auth):
    rollcall_id = _pick_rollcall(auth)
    if not rollcall_id:
        return
    missing_rows = _print_missing(rollcall_id)
    if missing_rows:
        _mark_people(auth, rollcall_id, missing_rows)
        _print_missing(rollcall_id)


def missing_list(auth):
    rollcall_id = _pick_rollcall(auth)
    if rollcall_id:
        _print_missing(rollcall_id)


def on_the_day_menu():
    auth = _auth()
    if not auth:
        return
    _menu(auth, _t("day.title", "ON THE DAY"), _entries(auth, [
        (_t("day.start", "Take a roll call"), take_rollcall, ORGANISE),
        (_t("day.continue", "Re-check those not yet present"), continue_rollcall, ORGANISE),
        (_t("day.missing_list", "Missing list"), missing_list, ORGANISE),
        (_t("day.card", "Emergency card"), show_emergency_card, ('view_trips',)),
    ]))


# ---------------------------------------------------------------------------
# Money
# ---------------------------------------------------------------------------

def _print_budget(figures):
    print(_t("money.budget", "\nBudget:    {value}").format(
        value=_money(figures['budget']) if figures['budget'] is not None else '-'))
    for category, amount in figures['expenses'].items():
        print(f"   {category:<20} {_money(amount):>10}")
    print(_t("money.actual", "Spent:     {value}").format(value=_money(figures['actual'])))
    print(_t("money.variance", "Variance:  {value}").format(
        value=_money(figures['variance']) if figures['variance'] is not None else '-'))
    print(_t("money.income", "Income:    {value} (paid {paid}, refunded {refunded}, hardship {hardship})").format(
        value=_money(figures['income']), paid=_money(figures['paid']), refunded=_money(figures['refunded']),
        hardship=_money(figures['hardship'])))
    print(_t("money.net", "Net:       {value}").format(value=_money(figures['net'])))


def budget_vs_actual(auth):
    trip = _pick_trip(auth, manage=True, include_archived=True)
    if trip:
        ok, figures = _call(money.budget_vs_actual, trip['id'])
        if ok:
            _print_budget(figures)


def reconcile_trip(auth):
    trip = _pick_trip(auth, manage=True, statuses=_FINISHED, include_archived=True)
    if not trip:
        return
    existing = money.get_reconciliation(trip['id'])
    if existing and existing.get('signed_off_by'):
        print(_t("money.already", "Already signed off by {who} on {when}.").format(
            who=existing['signed_off_by'], when=str(existing.get('signed_off_at'))[:16]))
        return
    ok, figures = _call(money.budget_vs_actual, trip['id'])
    if not ok:
        return
    _print_budget(figures)
    notes = _ask("money.notes", "Notes: ")
    if _yes("money.confirm", "Sign off these accounts? They cannot be changed afterwards. (y/n): "):
        ok, row = _call(money.reconcile, auth, trip['id'], notes)
        if ok:
            print(_t("money.reconciled", "Accounts signed off by {who}.").format(who=row.get('signed_off_by')))


def manage_instalments(auth):
    trip = _pick_trip(auth, manage=True)
    if not trip:
        return
    actions = [('add', _t("money.add", "Add an instalment")),
               ('edit', _t("money.edit", "Change an instalment")),
               ('remove', _t("money.remove", "Remove an instalment"))]
    while True:
        items = money.list_instalments(trip['id'])
        print(_t("money.schedule", "\nInstalments for '{name}' (cost {cost}):").format(
            name=trip['trip_name'], cost=_money(trip.get('cost'))))
        if not items:
            print(_t("money.no_instalments", "  none — the full cost is due on registration."))
        for item in items:
            print(f"  #{item['id']:<5} {item.get('due_date') or '':<11} {item.get('label') or '':<24} "
                  f"{_money(item['amount']):>9}")
        action = _choose([a for a, _l in actions], [label for _a, label in actions],
                         key="money.choose", default="Action (1-{max}, blank when done): ")
        if not action:
            return
        if action == 'add':
            label = _ask("money.label", "Label (e.g. 'Deposit'): ")
            due = _ask("money.due", "Due date (YYYY-MM-DD): ")
            amount = _ask_amount("money.amount", "Amount: ")
            if amount is not None:
                _call(money.add_instalment, auth, trip['id'], label, due, amount)
            continue
        item_id = _ask_int("money.pick", "Instalment # (blank to go back): ")
        if item_id not in {i['id'] for i in items}:
            continue
        if action == 'remove':
            _call(money.remove_instalment, auth, item_id)
            continue
        label = _ask("money.label_keep", "Label (blank keeps): ") or None
        due = _ask("money.due_keep", "Due date (blank keeps): ") or None
        amount = _ask_amount("money.amount_keep", "Amount (blank keeps): ")
        _call(money.update_instalment, auth, item_id, label=label, due_date=due, amount=amount)


def money_menu():
    auth = _auth()
    if not auth:
        return
    _menu(auth, _t("money.title", "TRIP MONEY"), _entries(auth, [
        (_t("money.bva", "Budget vs actual"), budget_vs_actual, MONEY),
        (_t("money.reconcile", "Reconcile and sign off the accounts"), reconcile_trip, MONEY),
        (_t("money.instalments", "Instalment schedule"), manage_instalments, MONEY),
    ]))


# ---------------------------------------------------------------------------
# Evaluations
# ---------------------------------------------------------------------------

def submit_trip_evaluation(auth):
    trip = _pick_trip(auth, statuses=('in_progress', 'completed', 'archived'), include_archived=True)
    if not trip:
        return
    rating = _ask_int("eval.rating", "Overall rating (1 = poor, 5 = excellent): ")
    if rating is None:
        return
    went_well = _ask("eval.went_well", "What went well: ")
    improve = _ask("eval.improve", "What could be better: ")
    ok, _id = _call(evaluation.submit_evaluation, auth, trip['id'], rating, went_well, improve)
    if ok:
        print(_t("eval.thanks", "Thank you — your evaluation is recorded."))


def evaluation_results(auth):
    trip = _pick_trip(auth, manage=not _can(auth, 'manage_trips', 'view_trip_reports'), include_archived=True)
    if not trip:
        return
    ok, res = _call(evaluation.results, auth, trip['id'])
    if not ok:
        return
    print(_t("eval.summary", "\n{n} response(s); average {avg}").format(
        n=res['responses'], avg=res['average'] if res['average'] is not None else '-'))
    for role, entry in res['by_role'].items():
        print(f"   {role:<12} {entry['count']:>3} × avg {entry['average']}")
    print("   " + "  ".join(f"{n}★ {count}" for n, count in res['distribution'].items()))
    for c in res['comments']:
        who = c['respondent'] or c['role']
        print(f"\n  [{c['rating']}] {who}")
        if c.get('went_well'):
            print(_t("eval.well_line", "    + {text}").format(text=c['went_well']))
        if c.get('improve'):
            print(_t("eval.improve_line", "    - {text}").format(text=c['improve']))


def evaluations_menu():
    auth = _auth()
    if not auth:
        return
    _menu(auth, _t("eval.title", "TRIP EVALUATIONS"), _entries(auth, [
        (_t("eval.submit", "Evaluate a trip I went on or led"), submit_trip_evaluation, ('view_trips',)),
        (_t("eval.results", "Evaluation results"), evaluation_results, ORGANISE + ('view_trip_reports',)),
    ]))


# ---------------------------------------------------------------------------
# What menu.py lists (label key, default label, entry point, permissions)
# ---------------------------------------------------------------------------

def menu_sections():
    """The grouped sub-menus, in display order."""
    return (
        ("trip_details", "Trip Details & Status", trip_lifecycle_menu, ('view_trips',) + ORGANISE),
        ("approvals", "Approvals", approvals_menu, ORGANISE + APPROVE),
        ("risk", "Risk Assessment", risk_menu, ORGANISE + HS + APPROVE),
        ("incidents", "Incidents", incidents_menu, ('view_trips',)),
        ("safeguarding", "Safeguarding & Staffing", safeguarding_menu,
         PEOPLE + HS + ('register_for_trips',)),
        ("overseas", "Overseas Travel", overseas_menu, ('view_trips',)),
        ("academic", "Academic Links", academic_menu, ORGANISE),
        ("places", "Places, Waiting List & Payments", places_menu,
         PEOPLE + MONEY + ('register_for_trips', 'view_own_trip_registrations')),
        ("health", "Health & Dietary Details", health_menu, ('view_trips',)),
        ("communications", "Communications", communications_menu, ('view_trips',)),
        ("on_the_day", "On the Day (Roll Call)", on_the_day_menu, ('view_trips',)),
        ("money", "Trip Money", money_menu, MONEY),
        ("evaluations", "Evaluations", evaluations_menu, ('view_trips',)),
    )
