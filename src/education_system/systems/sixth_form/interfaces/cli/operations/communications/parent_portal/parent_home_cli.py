"""Parent-facing CLI for the Sixth Form System.

The terminal counterpart of :mod:`.parent_home_gui`, and the same rule
applies: a parent must never reach the staff menu, so the launcher sends
the ``parent`` role here instead of ``cli_main``.

A parent can act only on their own linked children (every action goes
through the linked-child checks in :mod:`.parent_portal`): report an
absence, give or withdraw trip consent, start a bursary application,
book parents' evening appointments, and ask the office to update their
contact details. Nothing here edits a record directly.
"""

from __future__ import annotations

import logging

from education_system.systems.sixth_form import SYSTEM_NAME
from education_system.systems.sixth_form.domain.operations.communications.parent_portal import (
    parent_portal as data,
)

logger = logging.getLogger(__name__)

_RULE = "─" * 72


class _UserAbort(Exception):
    """Ctrl-C / EOF at a prompt — unwind to the menu loop."""


def _input(prompt: str, default: str = "") -> str:
    try:
        raw = input(f"  {prompt}: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        raise _UserAbort
    return raw or default


def _pause() -> None:
    try:
        input("\n  Press Enter to continue...")
    except (EOFError, KeyboardInterrupt):
        pass


def _fmt(value, dash: str = "—") -> str:
    return dash if value in (None, "") else str(value)


# ── Screens ──────────────────────────────────────────────────────────

def _print_overview(account) -> list[dict]:
    children = data.linked_students(account.account_id)
    print(f"\n  {SYSTEM_NAME} — Parent Portal")
    print(f"  Signed in as {account.full_name} ({account.username})")
    print(f"  {_RULE}")

    if not children:
        print("\n  No students are linked to your account yet.")
        print("  The college office links each parent account to their child's")
        print("  record — please contact them if you were expecting someone here.")
        return []

    print(f"\n  {'#':>3}  {'Student':<28}{'ID':<12}{'Relationship':<16}")
    print("  " + "-" * 62)
    for i, c in enumerate(children, 1):
        print(f"  {i:>3}  {c['full_name'][:26]:<28}{c['student_id']:<12}"
              f"{c['relationship']:<16}")
    return children


def _print_child(account, student_id: str) -> None:
    try:
        d = data.child_detail(account.account_id, student_id)
    except data.ValidationError as exc:
        print(f"\n  ✗ {exc}")
        return
    except Exception:
        logger.exception("Could not build detail for %s", student_id)
        print("\n  This student's information could not be loaded just now.")
        return

    print(f"\n  {_RULE}")
    print(f"  {d['full_name']}  ({d['student_id']} · {d['status']})")
    print(f"  {_RULE}")

    att_pct = d.get("attendance_pct")
    window = (d.get("attendance") or {}).get("days")
    beh = d.get("behaviour_30d") or {}
    print("\n  Attendance     " + ("—" if att_pct is None
                                   else f"{att_pct}%  (last {window} days)"))
    print(f"  Standing       {_fmt(d.get('risk_band'))}")
    print(f"  Behaviour 30d  +{beh.get('positive', 0)} / -{beh.get('negative', 0)}")
    ucas = d.get("ucas")
    if ucas:
        print(f"  UCAS progress  {ucas['percent']}%  "
              f"({ucas['complete']} of {ucas['total']} steps)")

    _print_subjects(d.get("subjects") or [])
    _print_attendance(d.get("attendance") or {})
    _print_behaviour(d.get("behaviour") or [])
    _print_coursework(d.get("coursework"))
    _print_ucas_tracker(d.get("ucas_tracker"))


def _print_subjects(subjects: list[dict]) -> None:
    if not subjects:
        return
    print("\n  Subjects")
    print(f"  {'Subject':<24}{'Predicted':<11}{'Target':<9}{'Mock':<9}"
          f"{'Forecast':<11}{'On target':<10}")
    print("  " + "-" * 74)
    for s in subjects:
        on_target = ("—" if s.get("on_target") is None
                     else ("yes" if s["on_target"] else "NO"))
        print(f"  {s['subject'][:22]:<24}{_fmt(s.get('predicted')):<11}"
              f"{_fmt(s.get('target')):<9}{_fmt(s.get('latest_mock')):<9}"
              f"{_fmt(s.get('forecast')):<11}{on_target:<10}")


def _print_attendance(att: dict) -> None:
    counts = att.get("counts") or {}
    print(f"\n  Attendance — last {att.get('days', 30)} days")
    if not counts:
        print("    No attendance has been recorded in this period.")
        return
    print("    " + "   ".join(f"{k}: {v}" for k, v in sorted(counts.items())))

    absences = att.get("absences") or []
    if not absences:
        print("    Full attendance — nothing missed.")
        return
    print(f"\n    {'Date':<14}{'Status':<16}{'Minutes late':<14}")
    print("    " + "-" * 44)
    for a in absences[:20]:
        late = a.get("minutes_late")
        print(f"    {a['date']:<14}{a['status']:<16}"
              f"{('—' if late in (None, 0) else str(late)):<14}")
    if len(absences) > 20:
        print(f"    ... and {len(absences) - 20} more")


def _print_behaviour(entries: list[dict]) -> None:
    print("\n  Behaviour record")
    if not entries:
        print("    Nothing recorded.")
        return
    print(f"    {'Date':<13}{'Type':<11}{'Category':<18}{'Pts':>4}  Details")
    print("    " + "-" * 78)
    for e in entries:
        detail = (e.get("description") or "")[:36]
        print(f"    {_fmt(e['date']):<13}{_fmt(e['type']):<11}"
              f"{_fmt(e['category'])[:16]:<18}{e.get('points') or 0:>4}  {detail}")


_TRACK_TEXT = {"done": "done", "current": "next", "pending": "not yet",
               "held": "held until results are released", "n/a": "not applicable"}


def _print_ucas_tracker(steps) -> None:
    """Read-only: where the move to university has got to."""
    if not steps:
        return
    print("\n  Move to university")
    for s in steps:
        print(f"    {s['label']:<24}{_TRACK_TEXT.get(s['state'], s['state']):<34}"
              f"{_fmt(s.get('date')):<12}{s.get('detail') or ''}")


def _print_coursework(work) -> None:
    if not work:
        return
    print("\n  Coursework")
    summary = work.get("summary")
    if isinstance(summary, dict) and summary:
        print("    " + "   ·   ".join(
            f"{k.replace('_', ' ').capitalize()}: {v}" for k, v in summary.items()))
    recent = work.get("recent") or []
    if not recent:
        print("    Nothing set recently.")
        return
    print(f"\n    {'Assignment':<30}{'Subject':<18}{'Due':<12}{'Status':<14}{'Mark':<10}")
    print("    " + "-" * 84)
    for r in recent:
        marks, max_marks = r.get("marks"), r.get("max_marks")
        if r.get("grade"):
            mark = str(r["grade"])
        elif marks is None:
            mark = "—"
        else:
            mark = f"{marks}/{max_marks}" if max_marks else str(marks)
        print(f"    {_fmt(r.get('title'))[:28]:<30}{_fmt(r.get('subject'))[:16]:<18}"
              f"{_fmt(r.get('due_date')):<12}{_fmt(r.get('state'))[:12]:<14}{mark:<10}")


def _email_portal(account) -> None:
    """Browse everything the college has emailed this parent."""
    if not account.email:
        print("\n  There is no email address on your account, so there is")
        print("  nothing to show here. Contact the college office to add one.")
        return

    while True:
        inbox = data.parent_messages(account.account_id)
        print(f"\n  {_RULE}")
        print(f"  My Email — delivered to {account.email}")
        print(f"  {_RULE}")

        if not inbox:
            print("\n  No email yet. Messages the college sends you will appear")
            print("  here as well as in your own inbox.")
            return

        print(f"\n  {'#':>3}  {'Sent':<18}{'From':<26}{'Subject':<40}")
        print("  " + "-" * 88)
        for i, m in enumerate(inbox, 1):
            sender = (m["from_name"] or m["from_address"] or "—")[:24]
            print(f"  {i:>3}  {(m['sent_at'] or '')[:16]:<18}{sender:<26}"
                  f"{m['subject'][:38]:<40}")

        choice = _input("Open which (number), or Enter to go back")
        if not choice:
            return
        if not (choice.isdigit() and 1 <= int(choice) <= len(inbox)):
            print("\n  Not a valid option.")
            continue
        _print_message(account, inbox[int(choice) - 1]["message_id"])
        _pause()


def _print_message(account, message_id: int) -> None:
    try:
        msg = data.parent_message(account.account_id, message_id)
    except data.ValidationError as exc:
        print(f"\n  ✗ {exc}")
        return
    except Exception:
        logger.exception("Could not open message %s", message_id)
        print("\n  This message could not be opened.")
        return

    sender = msg["from_name"] or msg["from_address"] or "The college"
    print(f"\n  {_RULE}")
    print(f"  {msg['subject']}")
    print(f"  From: {sender}")
    print(f"  Sent: {_fmt(msg['sent_at'])}")
    print(f"  {_RULE}\n")
    for line in (msg["body"] or "").splitlines():
        print(f"  {line}")


def _change_password(auth) -> None:
    from education_system.platform.delivery.cli import change_password_cli
    change_password_cli.run(auth)


# ── Child actions ────────────────────────────────────────────────────

def _money(v) -> str:
    return "—" if v is None else f"£{float(v):,.2f}"


def _child_menu(account, child: dict) -> None:
    sid = child["student_id"]
    _print_child(account, sid)
    while True:
        print(f"\n  {child['full_name']} — options")
        print("    t  Timetable           r  Reports")
        print("    a  Report an absence   x  Absences reported")
        print("    c  Trips and consent   b  Bursary")
        print("    Enter to go back")
        choice = _input("Choose").lower()
        if not choice:
            return
        handler = {"t": _child_timetable, "r": _child_reports,
                   "a": _child_absence, "x": _child_absence_list,
                   "c": _child_trips, "b": _child_bursary}.get(choice)
        if handler is None:
            print("\n  Not a valid option.")
            continue
        try:
            handler(account, child)
        except data.ValidationError as exc:
            print(f"\n  ✗ {exc}")
        except _UserAbort:
            raise
        except Exception as exc:
            logger.exception("Parent CLI action %s failed for %s", choice, sid)
            print(f"\n  ✗ {exc}")
        _pause()


def _child_timetable(account, child: dict) -> None:
    rows = data.child_timetable(account.account_id, child["student_id"])
    print(f"\n  Timetable — {child['full_name']}")
    if not rows:
        print("    Nothing timetabled.")
    for r in rows:
        print(f"    {r['day_name']:<5}P{r['period']} {r['start_time']}-{r['end_time']}  "
              f"{r['subject'][:26]:<28}{_fmt(r['room']):<10}{_fmt(r['teacher'])}")


def _child_reports(account, child: dict) -> None:
    sid = child["student_id"]
    cards = data.child_report_cards(account.account_id, sid)
    print(f"\n  Reports — {child['full_name']}")
    if not cards:
        print("    No reports have been published yet.")
        return
    for i, c in enumerate(cards, 1):
        print(f"  {i:>3}) {c['period']:<30} published {_fmt(c['published_at'])}")
    pick = _input("Read which (number), or Enter to go back")
    if not (pick.isdigit() and 1 <= int(pick) <= len(cards)):
        return
    card_id = cards[int(pick) - 1]["card_id"]
    print()
    for line in data.child_report_card_text(account.account_id, sid, card_id).splitlines():
        print(f"  {line}")
    fmt = _input("Save a copy? h)tml / p)df / Enter for no").lower()
    if fmt in ("h", "p"):
        path = data.child_report_card_file(account.account_id, sid, card_id,
                                           fmt="html" if fmt == "h" else "pdf")
        print(f"  ✓ Saved to {path}")


def _child_absence(account, child: dict) -> None:
    import datetime as _dt
    today = _dt.date.today().isoformat()
    print(f"\n  Report an absence — {child['full_name']}")
    date_from = _input(f"First day (YYYY-MM-DD) [{today}]", today)
    date_to = _input(f"Last day (YYYY-MM-DD) [{date_from}]", date_from)
    reason = _input("Reason")
    message = _input("Anything else the college should know")
    rep = data.report_child_absence(account.account_id, child["student_id"],
                                    date_from, date_to=date_to, reason=reason,
                                    message=message)
    print(f"\n  ✓ Thank you — received for {rep.span}.")


def _child_absence_list(account, child: dict) -> None:
    rows = data.child_absence_reports(account.account_id, child["student_id"])
    print(f"\n  Absences reported — {child['full_name']}")
    if not rows:
        print("    None.")
    for r in rows:
        print(f"    {r['dates']:<26}{_fmt(r['reason'])[:30]:<32}{r['reported_by']:<10}"
              f"{r['state']}")


def _child_trips(account, child: dict) -> None:
    sid = child["student_id"]
    rows = data.child_trips(account.account_id, sid)
    print(f"\n  Trips — {child['full_name']}")
    if not rows:
        print("    Not booked on any trips.")
        return
    for i, t in enumerate(rows, 1):
        print(f"  {i:>3}) {t['trip'][:28]:<30}{t['start_date']:<12}"
              f"{t['booking_status']:<12}consent {'given' if t['consent'] else 'NEEDED':<7}"
              f" paid {_money(t['paid'])} / to pay {_money(t['balance'])}")
    pick = _input("Give or withdraw consent for which (number), or Enter")
    if not (pick.isdigit() and 1 <= int(pick) <= len(rows)):
        return
    t = rows[int(pick) - 1]
    yes = _input("Do you give consent? (y/n)").lower().startswith("y")
    medical = _input(f"Medical needs / medication [{_fmt(t['medical_note'])}]",
                     t["medical_note"] or "")
    dietary = _input(f"Dietary needs [{_fmt(t['dietary_note'])}]",
                     t["dietary_note"] or "")
    note = _input("Note for the trip leader (optional)")
    data.set_trip_consent(account.account_id, sid, t["booking_id"], consent=yes,
                          medical_note=medical, dietary_note=dietary, note=note)
    print("\n  ✓ Saved — thank you.")


def _child_bursary(account, child: dict) -> None:
    sid = child["student_id"]
    apps = data.child_bursaries(account.account_id, sid)
    print(f"\n  Bursary — {child['full_name']}")
    if not apps:
        print("    No applications.")
    for a in apps:
        print(f"    {a['type'][:26]:<28}{a['applied']:<12}{a['status']:<16}"
              f"awarded {_money(a['awarded'])}  paid {_money(a['paid'])}  "
              f"to pay {_money(a['remaining'])}")
    if _input("Start a new application? (y/N)").lower() != "y":
        return
    types = data.bursary_types()
    for i, t in enumerate(types, 1):
        print(f"    {i:>2}) {t}")
    pick = _input("Type of support (number)")
    if not (pick.isdigit() and 1 <= int(pick) <= len(types)):
        print("  Not a valid option.")
        return

    def num(v, cast=float):
        try:
            return cast(v) if v else None
        except ValueError:
            raise data.ValidationError(f"'{v}' is not a number") from None
    amount = num(_input("Amount requested (£, optional)"))
    income = num(_input("Household income (£ a year, optional)"))
    size = num(_input("People in the household (optional)"), int)
    reason = _input("What is the support for?")
    app = data.start_bursary_application(
        account.account_id, sid, bursary_type=types[int(pick) - 1], reason=reason,
        amount_requested=amount, household_income=income, household_size=size)
    print(f"\n  ✓ Application #{app.application_id} sent to the finance office.")


def _parents_evening(account) -> None:
    events = data.parents_evening_events()
    children = data.linked_students(account.account_id)
    print(f"\n  {_RULE}\n  Parents' evenings\n  {_RULE}")
    bookings = data.parents_evening_bookings(account.account_id)
    if bookings:
        print("\n  My appointments")
        for i, r in enumerate(bookings, 1):
            print(f"  {i:>3}) {r.event_date} {r.booking.slot_time}  {r.student_name[:20]:<22}"
                  f"{r.staff_name[:20]:<22}{r.booking.status}")
        pick = _input("Cancel which appointment (number), or Enter to skip")
        if pick.isdigit() and 1 <= int(pick) <= len(bookings):
            try:
                data.cancel_parents_evening(account.account_id,
                                            bookings[int(pick) - 1].booking.booking_id)
                print("  ✓ Cancelled.")
            except data.ValidationError as exc:
                print(f"  ✗ {exc}")
    if not events or not children:
        print("\n  No parents' evenings are open for booking at the moment.")
        return
    print("\n  Open for booking")
    for i, e in enumerate(events, 1):
        print(f"  {i:>3}) {e.name} — {e.event_date} {e.start_time}-{e.end_time}"
              f"{' · ' + e.location if e.location else ''}")
    pick = _input("Book at which evening (number), or Enter to go back")
    if not (pick.isdigit() and 1 <= int(pick) <= len(events)):
        return
    event = events[int(pick) - 1]
    if len(children) == 1:
        child = children[0]
    else:
        for i, c in enumerate(children, 1):
            print(f"  {i:>3}) {c['full_name']}")
        pick = _input("For which child (number)")
        if not (pick.isdigit() and 1 <= int(pick) <= len(children)):
            return
        child = children[int(pick) - 1]
    while True:
        opts = data.parents_evening_options(account.account_id, event.event_id,
                                            child["student_id"])
        if not opts:
            print("  No teachers found for this child.")
            return
        for i, o in enumerate(opts, 1):
            print(f"  {i:>3}) {o.staff_name[:22]:<24}{o.subject[:22]:<24}"
                  f"{'booked ' + o.booked_slot if o.booked_slot else str(len(o.free_slots)) + ' free'}")
        pick = _input("Book which teacher (number), or Enter to finish")
        if not (pick.isdigit() and 1 <= int(pick) <= len(opts)):
            return
        o = opts[int(pick) - 1]
        if not o.free_slots:
            print("  No free times left.")
            continue
        print("    Free: " + ", ".join(o.free_slots))
        slot = _input(f"Time [{o.free_slots[0]}]", o.free_slots[0])
        try:
            data.book_parents_evening(account.account_id, event.event_id,
                                      child["student_id"], o.staff_id, slot)
            print(f"  ✓ Booked {o.staff_name} at {slot}.")
        except data.ValidationError as exc:
            print(f"  ✗ {exc}")


def _contact_request(account) -> None:
    print("\n  Update my contact details — fill in only what has changed.")
    print("  The college office checks each change before updating your record.")
    changes = {}
    for key, label in data.CONTACT_REQUEST_FIELDS.items():
        v = _input(label)
        if v:
            changes[key] = v
    note = _input("Note for the office (optional)")
    try:
        data.request_contact_update(account.account_id, changes, note=note)
    except data.ValidationError as exc:
        print(f"\n  ✗ {exc}")
        return
    print("\n  ✓ Sent to the college office.")
    for r in data.my_contact_requests(account.account_id)[:5]:
        print(f"    #{r['request_id']} {r['created_at'] or ''}  {r['status']}")


# ── Menu loop ────────────────────────────────────────────────────────

def run(auth, account) -> int:
    """Run the parent menu for an already-authenticated parent."""
    while True:
        try:
            children = _print_overview(account)

            print("\n  Options")
            if children:
                print("    1-N  View a student in full (and act for them)")
            print("    e    My email")
            print("    v    Parents' evenings (book / cancel)")
            print("    d    Update my contact details")
            print("    f    Pay fees, trips or meals online")
            print("    p    Change my password")
            print("    q    Log out")

            choice = _input("Choose").lower()
            if choice in ("q", "quit", "exit", "logout"):
                break
            if choice == "e":
                _email_portal(account)
                _pause()
                continue
            if choice == "p":
                try:
                    _change_password(auth)
                except Exception:
                    logger.exception("Password change failed")
                    print("\n  Password change is unavailable — please contact "
                          "the college office.")
                _pause()
                continue
            if choice.isdigit() and children and 1 <= int(choice) <= len(children):
                _child_menu(account, children[int(choice) - 1])
                continue
            if choice == "v":
                _parents_evening(account)
                _pause()
                continue
            if choice == "d":
                _contact_request(account)
                _pause()
                continue
            if choice == "f":
                from education_system.systems.sixth_form.domains.finance.interfaces.cli.online_payments import (
                    online_payments_cli,
                )
                online_payments_cli.pay_menu("parent", account.account_id)
                continue
            if choice:
                print("\n  Not a valid option.")
                _pause()
        except _UserAbort:
            break

    from education_system import switch
    try:
        auth.logout()
    except Exception:
        logger.debug("Logout on the shared session failed", exc_info=True)
    switch.request_logout("cli")
    print("\n  Signed out. Goodbye.\n")
    return 0
