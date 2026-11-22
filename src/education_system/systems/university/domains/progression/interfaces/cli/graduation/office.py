"""Graduation office menus for one ceremony: cohorts and the gown deadline,
graduands and invitations, reminders, RSVPs with named guests, extra
tickets, the summary, the day itself (check-in, completion) and gown
cancellations / refunds.

Every handler takes the CLI object (``cli.who`` is the signed-in
:class:`Officer`; ``cli.require_ceremony()`` picks the ceremony).
"""

from __future__ import annotations

from education_system.systems.university.application.graduation import ceremonies as gcer
from education_system.systems.university.application.graduation import conferral as gc
from education_system.systems.university.domains.progression.interfaces.cli.graduation._io import (
    ask,
    ask_choice,
    ask_int,
    confirm,
    guest_list,
    run,
    section,
    show,
    table,
)


def cohorts(cli) -> None:
    section("Who this ceremony is for")
    cid = cli.require_ceremony()
    if not cid:
        return
    current = run(gcer.cohorts, cid, write=False) or []
    print("  Current: " + (", ".join(f"{c['kind']}={c['value']}" for c in current) or
                           "open to every eligible graduand"))
    print(f"  Enter cohorts as kind=value, separated by ';' (kinds: "
          f"{', '.join(gcer.COHORT_KINDS)}). Blank clears them.")
    raw = ask("Cohorts")
    items = []
    for part in raw.split(";"):
        if "=" in part:
            kind, value = part.split("=", 1)
            items.append((kind.strip(), value.strip()))
    if run(gcer.set_cohorts, cli.who, cid, items) is not None:
        print("\n✓ Cohorts saved.")


def gown_deadline(cli) -> None:
    section("Gown order deadline")
    cid = cli.require_ceremony()
    if cid and run(gcer.set_gown_deadline, cli.who, cid,
                   ask("Gown orders close on (YYYY-MM-DD, blank = none)")) is not None:
        print("\n✓ Saved.")


def graduands(cli) -> None:
    section("Graduands for this ceremony")
    cid = cli.require_ceremony()
    if not cid:
        return
    rows = run(gcer.graduands, cli.who, cid, write=False) or []
    for row in rows:
        row["ok"] = "yes" if row["eligible"] else "; ".join(row["blockers"])[:40]
        row["name_ok"] = "yes" if row["name_confirmed"] else "no"
        row["inv"] = "yes" if row["invited"] else ""
    table(rows, [("student_id", "Student", 12), ("name", "Name", 24), ("award", "Award", 26),
                 ("ok", "Eligible", 26), ("name_ok", "Name ok", 9), ("inv", "Invited", 9),
                 ("rsvp", "Reply", 10)])


def invite(cli) -> None:
    section("Invite graduands")
    cid = cli.require_ceremony()
    if not cid:
        return
    raw = ask("Student ids, comma-separated (blank = every eligible graduand not yet invited)")
    ids = [s.strip() for s in raw.split(",") if s.strip()] or None
    result = run(gcer.invite, cli.who, cid, ids)
    if result:
        print(f"\n✓ Invited {len(result['invited'])}.")
        for sid, why in result["skipped"]:
            print(f"  skipped {sid}: {why}")


def reminders(cli) -> None:
    section("Send RSVP and gown reminders")
    result = run(gcer.send_reminders)
    if result:
        print(f"\n✓ Reminded {result['reminded']} graduand(s).")


def rsvps(cli) -> None:
    section("Replies")
    cid = cli.require_ceremony()
    if not cid:
        return
    from education_system.systems.university.domains.progression.domain.degree_audit.graduation_ceremony import (  # noqa: E501
        RsvpManager,
    )
    rows = RsvpManager.list_rsvps(cid)
    for row in rows:
        row["in"] = "yes" if row.get("attended_at") else ("no-show" if row.get("no_show") else "")
    table(rows, [("student_id", "Student", 12), ("student_name", "Name", 24),
                 ("rsvp_status", "Reply", 11), ("num_guests", "Guests", 8),
                 ("access_needs", "Needs", 20), ("in", "Attended", 10)])
    guests = run(gcer.guests, cid, write=False) or []
    if guests:
        print("\n  Guest tickets:")
        for g in guests:
            print(f"    {g['student_id']:<12}{g['guest_name'][:28]:<30}{g['ticket_ref']}"
                  + (f"  ({g['access_needs']})" if g.get("access_needs") else ""))


def record_rsvp(cli, student_id=None) -> None:
    section("Record a reply")
    cid = cli.require_ceremony()
    if not cid:
        return
    sid = student_id or ask("Student id")
    if not sid:
        return
    status = ask_choice("Reply", gcer.RSVP_STATUSES, "going")
    if not status:
        return
    guests = guest_list(ask("Guests' names, ';' between them, needs in brackets "
                            "(e.g. Ann; Bob (wheelchair))")) if status == "going" else []
    print(f"  Access needs: {', '.join(gcer.ACCESS_NEEDS)}")
    needs = ask("Graduand's access needs, comma-separated (blank = none)")
    notes = ask("Other accessibility notes")
    pron = ask("Name pronunciation")
    extra = ask_int("Extra tickets wanted (waiting list)", 0) or 0
    override = cli.who.is_office and student_id is None and \
        confirm("Override the reply deadline / cohort if needed?")
    result = run(gcer.record_rsvp, cli.who, cid, sid, status, guests=guests,
                 access_needs=needs, notes=notes, name_pronunciation=pron,
                 extra_tickets=extra, override=override)
    if result:
        print(f"\n✓ Reply saved (id {result['rsvp_id']}).")
        for name, ref in result["tickets"]:
            print(f"  Ticket {ref}: {name}")


def extra_tickets(cli) -> None:
    section("Extra ticket requests")
    cid = cli.require_ceremony()
    if not cid:
        return
    rows = run(gcer.ticket_requests, cid, write=False) or []
    table(rows, [("student_id", "Student", 12), ("requested", "Asked", 8),
                 ("granted", "Granted", 9), ("status", "Status", 16),
                 ("requested_at", "Asked on", 20)])
    if rows and confirm("Share out the spare seats now (first come, first served)?"):
        result = run(gcer.allocate_extra_tickets, cli.who, cid)
        if result:
            print(f"\n✓ Granted {result['granted']}; {result['spare_left']} seat(s) still free.")


def summary(cli) -> None:
    section("Ceremony summary")
    cid = cli.require_ceremony()
    if not cid:
        return
    s = run(gcer.summary, cid, write=False)
    if not s:
        return
    c = s["ceremony"]
    show([("Ceremony", f"{c['ceremony_name']} — {c['ceremony_date']} {c['ceremony_time']}"),
          ("Status", c.get("status")), ("Reply deadline", c.get("rsvp_deadline")),
          ("Gown deadline", c.get("gown_order_deadline")),
          ("Cohorts", ", ".join(f"{x['kind']}={x['value']}" for x in s["cohorts"]) or "all"),
          ("Capacity", s["capacity"]), ("Seats taken", s["seats_taken"]),
          ("Invited", s["invited"]), ("Going", s["going"]), ("Guest tickets", s["guests"]),
          ("Extra tickets waiting", s["waiting_tickets"]), ("Checked in", s["attended"]),
          ("No-shows", s["no_shows"]), ("Conferred", s["conferred"])])


# ── on the day ──────────────────────────────────────────────────────────


def check_in(cli) -> None:
    section("Check graduands in")
    cid = cli.require_ceremony()
    if not cid:
        return
    print("  Enter student ids one at a time; blank to stop.")
    while True:
        sid = ask("Student id")
        if not sid:
            return
        if run(gcer.check_in, cli.who, cid, sid) is not None:
            print(f"  ✓ {sid} checked in.")


def undo_check_in(cli) -> None:
    section("Undo a check-in")
    cid = cli.require_ceremony()
    sid = ask("Student id") if cid else ""
    if sid and run(gcer.undo_check_in, cli.who, cid, sid) is not None:
        print("\n✓ Check-in removed.")


def transfer(cli) -> None:
    section("Move a graduand to a later ceremony")
    cid = cli.require_ceremony()
    if not cid:
        return
    sid = ask("Student id")
    to = ask_int("Move to ceremony id")
    if sid and to and run(gcer.transfer, cli.who, cid, sid, to,
                          ask("Reason (optional)")) is not None:
        print(f"\n✓ {sid} moved to ceremony {to} (their reply there is pending).")


def complete(cli) -> None:
    section("Complete the ceremony")
    cid = cli.require_ceremony()
    if not cid:
        return
    print("  Completing confers the award on every checked-in graduand, marks the rest")
    print("  as no-shows and closes the ceremony.")
    if not confirm(f"Complete ceremony {cid}?"):
        return
    result = run(gcer.complete, cli.who, cid)
    if not result:
        return
    for item in result["conferred"]:
        gc.after_commit(item)
        print(f"  ✓ {item['student_id']}: certificate {item['certificate_number']}")
    for sid, why in result["failed"]:
        print(f"  ✗ {sid}: {why}")
    if result["no_shows"]:
        print("  No-shows: " + ", ".join(result["no_shows"]))
    print(f"\n✓ Ceremony completed: {len(result['conferred'])} conferred, "
          f"{len(result['failed'])} not conferred, {len(result['no_shows'])} no-show(s).")


# ── gowns ───────────────────────────────────────────────────────────────


def cancel_gown(cli) -> None:
    section("Cancel a gown order")
    oid = ask_int("Order id")
    if oid and run(gcer.cancel_gown_order, cli.who, oid, ask("Reason")) is not None:
        print("\n✓ Cancelled. A paid order is now marked refund due.")


def refund_gown(cli) -> None:
    section("Refund a cancelled gown order")
    oid = ask_int("Order id")
    if not oid:
        return
    result = run(gcer.refund_gown_order, cli.who, oid)
    if result:
        gcer.post_refund(result, cli.who.username)
        print(f"\n✓ Refunded £{result['amount']:.2f} (refund {result['refund_id']}).")
