"""The portal sections fed by the linked areas, in the terminal: Messages
(announcements, letters home with the reply slip, parents' evening booking),
Money (trips and dinner money) and Wellbeing (the pupil's own check-in).
:mod:`portal_cli` dispatches to ``_messages`` / ``_money`` / ``_wellbeing``.
"""

from __future__ import annotations

import datetime as _dt
from typing import Any

from education_system.systems.secondary.modules.portals.domain import portal as PT
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.ui.cli.prompts.prompts import pick, problem, prompt

_ERRORS = (PT.ValidationError, PT.PermissionDenied, PT.NotFound)


def _d(iso: str | None) -> str:
    try:
        return _dt.date.fromisoformat(str(iso)[:10]).strftime("%a %d %b") if iso else ""
    except ValueError:
        return str(iso)


def home_lines(h: dict[str, Any]) -> None:
    """Extra lines for the portal home: unread notices, money and consent."""
    an = h.get("announcements") or {}
    if an.get("unread"):
        print("\n  New notices: " + "; ".join(a.title for a in an["unread"][:5])
              + " (Messages to read them)")
    dinner = h.get("dinner") or {}
    if dinner.get("overdrawn"):
        print(f"\n  Dinner money is overdrawn: {dinner['balance']}")
    elif dinner.get("low"):
        print(f"\n  Dinner money is running low: {dinner['balance']}")
    for t in h.get("trips") or []:
        if t["balance_pence"]:
            print(f"  {t['trip']}: {t['balance']} to pay"
                  + (f" ({t['next_due']})" if t["next_due"] else ""))
        if t["consent"] == "Not given":
            print(f"  {t['trip']}: consent not given yet")


def _messages(principal: Principal, pid: int) -> None:
    while True:
        m = PT.messages(principal, pid)
        an = m["announcements"]
        unread = {a.announcement_id for a in an["unread"]}
        ack = {a.announcement_id for a in an["to_acknowledge"]}
        print("\n  Announcements:")
        for a in an["active"]:
            print(f"   A{a.announcement_id}) " + ("* " if a.announcement_id in unread else "")
                  + a.title + ("  (please confirm you have read it)"
                               if a.announcement_id in ack else ""))
        if not an["active"]:
            print("    none")
        if not principal.is_student:
            print("\n  Parents' evenings:")
            pe = m["parents_evenings"]
            if not pe:
                print("    none coming up")
            for x in pe:
                e = x["event"]
                print(f"    E{e.event_id}) {e.name} {_d(e.event_date)} {e.start_time}-"
                      f"{e.end_time}" + ("" if x["can_book"] else f" ({e.status.lower()})"))
                for t in x["teachers"]:
                    b = t["booking"]
                    print(f"        {t['teacher']}: " + (
                        f"booked {b.slot_time} (cancel: X{b.booking_id})" if b is not None
                        else f"{len(t['free'])} free slot(s)" if t["free"] else "-"))
            print("\n  Letters home:")
            if not m["letters"]:
                print("    none")
            for r in m["letters"]:
                state = ""
                if r.reply_question:
                    state = f" - replied {r.reply}" if r.reply else " - REPLY NEEDED"
                print(f"   L{r.recipient_id}) {_d(r.sent_at)} {r.subject}{state}")
        choice = prompt("\n  A<n> read · E<n> book · X<n> cancel · L<n> letter · "
                        "Enter to go back: ").strip().upper()
        if not choice:
            return
        try:
            _act(principal, pid, choice, m, ack)
        except _ERRORS as e:
            problem(e)


def _act(principal: Principal, pid: int, choice: str, m: dict[str, Any], ack: set) -> None:
    kind, num = choice[:1], choice[1:].strip()
    if not num.isdigit():
        print("  Type a letter and a number, e.g. A3.")
        return
    n = int(num)
    if kind == "A":
        a = next((x for x in m["announcements"]["active"] if x.announcement_id == n), None)
        if a is None:
            print("  Not in the list.")
            return
        print(f"\n  {a.title}\n\n{a.body}\n")
        ok = n in ack and prompt("  Type YES to confirm you have read and understood it: "
                                 ).strip().upper() == "YES"
        PT.read_announcement(principal, n, acknowledge=ok)
    elif kind == "E" and not principal.is_student:
        x = next((y for y in m["parents_evenings"] if y["event"].event_id == n), None)
        if x is None:
            print("  Not in the list.")
            return
        free = [t for t in x["teachers"] if t["free"] and t["booking"] is None]
        if not free:
            print("  No teachers with free slots.")
            return
        who = pick("Teacher", [t["teacher"] for t in free])
        t = next((y for y in free if y["teacher"] == who), None)
        if t is None:
            return
        slot = pick("Time", list(t["free"]), t["free"][0])
        b = PT.book_parents_evening(principal, n, pid, t["teacher_key"], slot or "")
        print(f"  Booked {b.slot_time} with {b.teacher_name}.")
    elif kind == "X" and not principal.is_student:
        PT.cancel_parents_evening(principal, n)
        print("  Cancelled.")
    elif kind == "L" and not principal.is_student:
        r = next((y for y in m["letters"] if y.recipient_id == n), None)
        if r is None:
            print("  Not in the list.")
            return
        print(f"\n  {r.subject}\n\n{r.body}\n")
        if r.reply_question and not r.reply:
            reply = pick(r.reply_question, ["Yes", "No"])
            if reply:
                note = prompt("  Note (optional): ").strip() or None
                PT.reply_to_letter(principal, r.recipient_id, reply, note)
                print("  Thank you - your reply has been sent.")
    else:
        print("  Not an option here.")


def _money(principal: Principal, pid: int) -> None:
    d = PT.dinner_money(principal, pid)
    print(f"\n  Dinner money balance: {d['balance']}" + (" (free school meals)" if d["fsm"]
                                                        else ""))
    if d["overdrawn"]:
        print("  The account is overdrawn - please top it up.")
    elif d["low"]:
        print("  The balance is running low.")
    for x in d["recent"]:
        print(f"    {_d(x['date']):<11} {x['what'][:30]:<30} {x['amount']:>9}")
    print("\n  Trips:")
    rows = PT.trips(principal, pid)
    if not rows:
        print("    none coming up")
    for t in rows:
        print(f"    {t['trip']} ({t['dates']}) consent: {t['consent']}"
              + (f" · cost {t['cost']} paid {t['paid']} to pay {t['balance']}"
                 if t["charging"] else "")
              + (f" · next: {t['next_due']}" if t["next_due"] else ""))


def _wellbeing(principal: Principal, pid: int) -> None:
    w = PT.wellbeing(principal, pid)
    for s in w["surveys"]:
        print(f"\n  {s.title}" + (f" - {s.question}" if s.question else ""))
    if not w["can_check_in"]:
        print("  Only the pupil can check in.")
        return
    lo, hi = w["scale"]
    print(f"\n  Score each from {lo} (not good) to {hi} (great). A member of staff reads "
          "these - if you need help now, talk to your tutor or any adult you trust.")
    data = {"mood_rating": prompt("  My mood: ").strip() or None,
            "confidence_rating": prompt("  How confident I feel: ").strip() or None,
            "connection_rating": prompt("  How connected I feel to others: ").strip() or None,
            "notes": prompt("  Anything you want to tell us (optional): ").strip() or None}
    if not any(data.values()):
        print("  Nothing saved.")
        return
    PT.check_in(principal, pid, data)
    print("  Thank you - your check-in has been saved.")


__all__ = ["home_lines", "_messages", "_money", "_wellbeing"]
