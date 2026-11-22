"""Personal emergency evacuation plans — CLI twin of the PEEPs tab
(``domain/disability/peeps``).

Estates, health & safety and disability services staff get the register;
anyone else sees their own plan.
"""

from __future__ import annotations

from education_system.systems.university.domains.student_support.domain.disability import peeps
from education_system.systems.university.domains.student_support.domain.wellbeing.casework import (
    access,
)


def _ask(prompt, default=""):
    value = input(f"{prompt}{f' [{default}]' if default else ''}: ").strip()
    return value or default


def _print_plan(plan):
    print("\n" + "=" * 70)
    print(f"PEEP #{plan['peep_id']} — {plan.get('person_name') or plan['person_ref']} "
          f"({plan['person_type']} {plan['person_ref']})")
    print(f"Status: {plan['status']}   Review due: {plan.get('review_date') or '—'}   "
          f"Last reviewed: {plan.get('last_reviewed_at') or 'never'}")
    print("Buildings:")
    for loc in plan["locations"]:
        print(f"  • {loc['building']}: {loc.get('rooms') or 'all areas'}")
    print(f"Assistance needed: {plan.get('assistance_needed') or '—'}")
    print(f"Evacuation method: {plan.get('evacuation_method') or '—'}")
    print(f"Equipment: {plan.get('equipment') or '—'}")
    print(f"Refuge points: {plan.get('refuge_points') or '—'}")
    print(f"Alerted by: {plan.get('alarm_method') or '—'}")
    print("Buddies:")
    for b in plan.get("buddies", []) or []:
        print(f"  • {b['name']} {b.get('contact') or ''} {b.get('notes') or ''}")
    if plan.get("other_notes"):
        print(f"Notes: {plan['other_notes']}")
    print("=" * 70)


def _lines(prompt):
    print(f"{prompt} (blank line to finish):")
    out = []
    while True:
        line = input("  > ").strip()
        if not line:
            return out
        out.append(line)


def _plan_data(existing=None) -> dict:
    existing = existing or {}
    print("Buildings — one per line as 'Building: rooms'. Known buildings: "
          + (", ".join(peeps.known_buildings()) or "none recorded"))
    locations = []
    for line in _lines("Buildings"):
        building, _, rooms = line.partition(":")
        locations.append({"building": building.strip(), "rooms": rooms.strip()})
    buddies = []
    for line in _lines("Buddies — 'Name; contact; notes'"):
        parts = [p.strip() for p in line.split(";")]
        buddies.append({"name": parts[0], "contact": parts[1] if len(parts) > 1 else "",
                        "notes": parts[2] if len(parts) > 2 else ""})
    print("Evacuation methods: " + "; ".join(peeps.EVACUATION_METHODS))
    return {
        "locations": locations or existing.get("locations", []),
        "buddies": buddies or existing.get("buddies", []),
        "assistance_needed": _ask("Assistance needed", existing.get("assistance_needed") or ""),
        "evacuation_method": _ask("Evacuation method", existing.get("evacuation_method") or ""),
        "equipment": _ask("Equipment", existing.get("equipment") or ""),
        "refuge_points": _ask("Refuge points", existing.get("refuge_points") or ""),
        "alarm_method": _ask("How alerted (" + ", ".join(peeps.ALARM_METHODS) + ")",
                             existing.get("alarm_method") or ""),
        "review_date": _ask("Review date (YYYY-MM-DD)", existing.get("review_date") or ""),
        "status": _ask("Status (draft/active)", existing.get("status") or "draft"),
        "manager_username": _ask("Plan manager username (blank = you)",
                                 existing.get("manager_username") or ""),
        "other_notes": _ask("Other notes", existing.get("other_notes") or ""),
    }


def run(auth):
    """The PEEPs menu: the register for estates / H&S / disability services,
    or the signed-in person's own plan."""
    if not access.current_user(auth):
        print("\n❌ Sign in first.")
        return
    if not access.is_peep_viewer(auth):
        try:
            plans = peeps.my_plans(auth)
        except (PermissionError, ValueError) as exc:
            print(f"\n❌ {exc}")
            return
        if not plans:
            print("\nYou have no evacuation plan. If you would need help to leave a building "
                  "in an emergency, ask disability services (students) or health & safety "
                  "(staff) to make one with you.")
        for plan in plans:
            _print_plan(plan)
        input("\nPress Enter to continue...")
        return
    manager = access.may_manage_peeps(auth)
    while True:
        print("\n" + "=" * 50)
        print("  EVACUATION PLANS (PEEPs)")
        print("=" * 50)
        print("1. Register\n2. Register for one building\n3. Reviews due\n4. Open a plan")
        if manager:
            print("5. New plan\n6. Edit a plan\n7. Mark a plan reviewed\n8. Archive a plan\n"
                  "9. Send review reminders")
        print("P. Print a plan (PDF)\n0. Back")
        choice = input("\nEnter your choice: ").strip().lower()
        try:
            if choice == "0":
                return
            _dispatch(auth, choice, manager)
        except (PermissionError, ValueError) as exc:
            print(f"❌ {exc}")
        except KeyboardInterrupt:
            return


def _list(rows):
    if not rows:
        print("  No plans.")
    for r in rows:
        overdue = " OVERDUE" if r.get("review_overdue") else ""
        print(f"  #{r['peep_id']} {r['person_type']:<7} {r['person_ref']:<12} "
              f"{(r.get('person_name') or '')[:22]:<22} {r['buildings'][:30]:<30} "
              f"{r['status']:<7} review {r.get('review_date') or '—'}{overdue}")


def _dispatch(auth, choice, manager):  # noqa: C901 - a flat menu dispatch
    if choice == "1":
        _list(peeps.register(auth))
    elif choice == "2":
        _list(peeps.register(auth, building=_ask("Building")))
    elif choice == "3":
        _list(peeps.register(auth, review_due_days=peeps.REMINDER_DAYS))
    elif choice == "4":
        _print_plan(peeps.plan_detail(auth, int(_ask("Plan #"))))
    elif choice == "p":
        print(f"✅ Saved: {peeps.plan_pdf(auth, int(_ask('Plan #')))}")
    elif not manager:
        print("❌ Invalid choice.")
    elif choice == "5":
        person_type = _ask("For a student or staff member", "student")
        ref = _ask("Student number" if person_type == "student" else "Staff username")
        print(f"✅ Plan #{peeps.create_plan(auth, person_type, ref, _plan_data())} recorded.")
    elif choice == "6":
        pid = int(_ask("Plan #"))
        peeps.update_plan(auth, pid, _plan_data(peeps.plan_detail(auth, pid)))
        print("✅ Saved.")
    elif choice == "7":
        nxt = peeps.mark_reviewed(auth, int(_ask("Plan #")),
                                  next_review=_ask("Next review (blank = a year)"))
        print(f"✅ Reviewed. Next review {nxt}.")
    elif choice == "8":
        peeps.archive_plan(auth, int(_ask("Plan #")), _ask("Reason"))
        print("✅ Archived.")
    elif choice == "9":
        print(f"✅ Reminders sent for {peeps.send_review_reminders(auth)} plan(s).")
    else:
        print("❌ Invalid choice.")
