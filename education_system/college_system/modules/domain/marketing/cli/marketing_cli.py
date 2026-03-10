"""Marketing & Open Days CLI module."""

from education_system.college_system.modules.shared.cli.cli_main import (
    print_header, print_menu, get_choice,
)
from education_system.college_system.modules.domain.marketing.services.marketing_service import MarketingService
from education_system.college_system.infrastructure.auth.core import UserAuth


def marketing_menu(auth: UserAuth):
    """Marketing & Open Days management menu."""
    svc = MarketingService(auth._db_path)

    while True:
        print_header("Marketing & Open Days")
        options = [
            ("1", "List Open Day Events"),
            ("2", "New Open Day Event"),
            ("3", "View Event Details"),
            ("4", "Edit Event"),
            ("5", "Delete Event"),
            ("6", "List Registrations"),
            ("7", "New Registration"),
            ("8", "Edit Registration"),
            ("9", "Delete Registration"),
            ("A", "Mark Attended"),
            ("B", "Mark Follow-up Sent"),
            ("C", "List Campaigns"),
            ("D", "New Campaign"),
            ("E", "Edit Campaign"),
            ("F", "Delete Campaign"),
            ("G", "Statistics"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice().upper()
        if choice == "1":
            _list_events(svc)
        elif choice == "2":
            _new_event(svc)
        elif choice == "3":
            _view_event(svc)
        elif choice == "4":
            _edit_event(svc)
        elif choice == "5":
            _delete_event(svc)
        elif choice == "6":
            _list_registrations(svc)
        elif choice == "7":
            _new_registration(svc)
        elif choice == "8":
            _edit_registration(svc)
        elif choice == "9":
            _delete_registration(svc)
        elif choice == "A":
            _mark_attended(svc)
        elif choice == "B":
            _mark_follow_up(svc)
        elif choice == "C":
            _list_campaigns(svc)
        elif choice == "D":
            _new_campaign(svc)
        elif choice == "E":
            _edit_campaign(svc)
        elif choice == "F":
            _delete_campaign(svc)
        elif choice == "G":
            _show_stats(svc)
        elif choice == "0":
            break
        else:
            print("\n  Invalid option.")


# ── Open Day Events ──

def _list_events(svc):
    print_header("Open Day Events")
    try:
        status = input("  Filter by status (planned/confirmed/completed/cancelled) [all]: ").strip() or None
        event_type = input("  Filter by type (open_day/taster_day/tour) [all]: ").strip() or None
        events = svc.list_events(status=status, event_type=event_type)
        if not events:
            print("\n  No events found.")
            return
        print(f"\n  {'ID':<5} {'Name':<25} {'Date':<12} {'Type':<12} {'Cap':<6} {'Regs':<6} {'Att':<6} {'Status'}")
        print(f"  {'-'*80}")
        for ev in events:
            print(f"  {ev['id']:<5} {ev['event_name'][:24]:<25} {ev['event_date']:<12} "
                  f"{(ev.get('event_type') or '-'):<12} "
                  f"{str(ev.get('capacity') or '-'):<6} "
                  f"{ev.get('registrations', 0):<6} {ev.get('attendees', 0):<6} "
                  f"{ev.get('status', 'planned')}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _new_event(svc):
    print_header("New Open Day Event")
    try:
        name = input("  Event Name: ").strip()
        if not name:
            print("\n  Event name is required.")
            return
        date = input("  Date (YYYY-MM-DD): ").strip()
        if not date:
            print("\n  Date is required.")
            return
        etype = input("  Type (open_day/taster_day/tour) [open_day]: ").strip() or "open_day"
        start = input("  Start Time (HH:MM): ").strip() or None
        end = input("  End Time (HH:MM): ").strip() or None
        cap_str = input("  Capacity [unlimited]: ").strip()
        cap = int(cap_str) if cap_str else None
        location = input("  Location: ").strip() or None
        description = input("  Description: ").strip() or None
        audience = input("  Target Audience: ").strip() or None

        ev = svc.create_event(name, date, etype, start, end, cap, location, description, audience)
        print(f"\n  Event created (ID: {ev['id']}).")
    except Exception as e:
        print(f"\n  Error: {e}")


def _view_event(svc):
    try:
        eid = int(input("  Event ID: ").strip())
        ev = svc.get_event(eid)
        if not ev:
            print("\n  Event not found.")
            return
        print()
        for k, v in ev.items():
            print(f"  {k}: {v}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _edit_event(svc):
    print_header("Edit Event")
    try:
        eid = int(input("  Event ID: ").strip())
        ev = svc.get_event(eid)
        if not ev:
            print("\n  Event not found.")
            return
        print(f"  Editing: {ev['event_name']} ({ev['event_date']})")
        print("  (Leave blank to keep current value)\n")

        updates = {}
        name = input(f"  Event Name [{ev['event_name']}]: ").strip()
        if name:
            updates["event_name"] = name
        date = input(f"  Date [{ev['event_date']}]: ").strip()
        if date:
            updates["event_date"] = date
        etype = input(f"  Type [{ev.get('event_type', '')}]: ").strip()
        if etype:
            updates["event_type"] = etype
        start = input(f"  Start Time [{ev.get('start_time', '')}]: ").strip()
        if start:
            updates["start_time"] = start
        end = input(f"  End Time [{ev.get('end_time', '')}]: ").strip()
        if end:
            updates["end_time"] = end
        cap = input(f"  Capacity [{ev.get('capacity', '')}]: ").strip()
        if cap:
            updates["capacity"] = int(cap)
        loc = input(f"  Location [{ev.get('location', '')}]: ").strip()
        if loc:
            updates["location"] = loc
        desc = input(f"  Description [{(ev.get('description') or '')[:30]}]: ").strip()
        if desc:
            updates["description"] = desc
        audience = input(f"  Target Audience [{ev.get('target_audience', '')}]: ").strip()
        if audience:
            updates["target_audience"] = audience
        status = input(f"  Status [{ev.get('status', 'planned')}]: ").strip()
        if status:
            updates["status"] = status

        if not updates:
            print("\n  No changes made.")
            return
        svc.update_event(eid, **updates)
        print("\n  Event updated.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _delete_event(svc):
    try:
        eid = int(input("  Event ID: ").strip())
        confirm = input("  This will delete the event and all registrations. Continue? (y/n): ").strip().lower()
        if confirm != "y":
            print("\n  Cancelled.")
            return
        svc.delete_event(eid)
        print("\n  Event deleted.")
    except Exception as e:
        print(f"\n  Error: {e}")


# ── Registrations ──

def _list_registrations(svc):
    print_header("Open Day Registrations")
    try:
        eid_str = input("  Event ID [all]: ").strip()
        eid = int(eid_str) if eid_str else None
        search = input("  Search (name/email/school) [none]: ").strip() or None
        regs = svc.list_registrations(event_id=eid, search=search)
        if not regs:
            print("\n  No registrations found.")
            return
        print(f"\n  {'ID':<5} {'Event':<6} {'Name':<20} {'Email':<22} {'School':<15} "
              f"{'Yr':<4} {'Att':<4} {'F/U':<4} {'App'}")
        print(f"  {'-'*90}")
        for r in regs:
            print(f"  {r['id']:<5} {r['event_id']:<6} {r['student_name'][:19]:<20} "
                  f"{(r.get('email') or '-')[:21]:<22} {(r.get('school') or '-')[:14]:<15} "
                  f"{(r.get('year_group') or '-'):<4} "
                  f"{'Y' if r['attended'] else 'N':<4} "
                  f"{'Y' if r['follow_up_sent'] else 'N':<4} "
                  f"{'Y' if r['applied'] else 'N'}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _new_registration(svc):
    print_header("New Registration")
    try:
        eid = int(input("  Event ID: ").strip())
        name = input("  Student Name: ").strip()
        if not name:
            print("\n  Student name is required.")
            return
        email = input("  Email: ").strip() or None
        phone = input("  Phone: ").strip() or None
        school = input("  School: ").strip() or None
        year_group = input("  Year Group: ").strip() or None
        interests = input("  Interests: ").strip() or None

        reg = svc.create_registration(eid, name, email, phone, school, year_group, interests)
        print(f"\n  Registration created (ID: {reg['id']}).")
    except Exception as e:
        print(f"\n  Error: {e}")


def _edit_registration(svc):
    print_header("Edit Registration")
    try:
        rid = int(input("  Registration ID: ").strip())
        print("  (Leave blank to keep current value)\n")

        updates = {}
        name = input("  Student Name: ").strip()
        if name:
            updates["student_name"] = name
        email = input("  Email: ").strip()
        if email:
            updates["email"] = email
        phone = input("  Phone: ").strip()
        if phone:
            updates["phone"] = phone
        school = input("  School: ").strip()
        if school:
            updates["school"] = school
        year = input("  Year Group: ").strip()
        if year:
            updates["year_group"] = year
        interests = input("  Interests: ").strip()
        if interests:
            updates["interests"] = interests
        applied = input("  Applied (0/1): ").strip()
        if applied in ("0", "1"):
            updates["applied"] = int(applied)

        if not updates:
            print("\n  No changes made.")
            return
        svc.update_registration(rid, **updates)
        print("\n  Registration updated.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _delete_registration(svc):
    try:
        rid = int(input("  Registration ID: ").strip())
        confirm = input("  Delete this registration? (y/n): ").strip().lower()
        if confirm != "y":
            print("\n  Cancelled.")
            return
        svc.delete_registration(rid)
        print("\n  Registration deleted.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _mark_attended(svc):
    try:
        rid = int(input("  Registration ID: ").strip())
        svc.mark_attended(rid)
        print("\n  Marked as attended.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _mark_follow_up(svc):
    try:
        rid = int(input("  Registration ID: ").strip())
        svc.mark_follow_up(rid)
        print("\n  Follow-up marked as sent.")
    except Exception as e:
        print(f"\n  Error: {e}")


# ── Campaigns ──

def _list_campaigns(svc):
    print_header("Marketing Campaigns")
    try:
        status = input("  Filter by status (planned/active/completed/cancelled) [all]: ").strip() or None
        ctype = input("  Filter by type (digital/print/social/email/event) [all]: ").strip() or None
        campaigns = svc.list_campaigns(status=status, campaign_type=ctype)
        if not campaigns:
            print("\n  No campaigns found.")
            return
        print(f"\n  {'ID':<5} {'Campaign':<22} {'Type':<8} {'Start':<12} {'End':<12} "
              f"{'Budget':<10} {'Spend':<10} {'Enq':<5} {'Apps':<5} {'Status'}")
        print(f"  {'-'*95}")
        for c in campaigns:
            print(f"  {c['id']:<5} {c['campaign_name'][:21]:<22} "
                  f"{(c.get('campaign_type') or '-'):<8} "
                  f"{(c.get('start_date') or '-'):<12} {(c.get('end_date') or '-'):<12} "
                  f"{c.get('budget', 0):<10.2f} {c.get('spend', 0):<10.2f} "
                  f"{c.get('enquiries', 0):<5} {c.get('applications', 0):<5} "
                  f"{c.get('status', 'planned')}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _new_campaign(svc):
    print_header("New Campaign")
    try:
        name = input("  Campaign Name: ").strip()
        if not name:
            print("\n  Campaign name is required.")
            return
        ctype = input("  Type (digital/print/social/email/event) [digital]: ").strip() or "digital"
        start = input("  Start Date (YYYY-MM-DD): ").strip() or None
        end = input("  End Date (YYYY-MM-DD): ").strip() or None
        budget_str = input("  Budget [0]: ").strip()
        budget = float(budget_str) if budget_str else 0
        audience = input("  Target Audience: ").strip() or None
        channels = input("  Channels: ").strip() or None
        notes = input("  Notes: ").strip() or None

        camp = svc.create_campaign(name, ctype, start, end, budget, audience, channels, notes)
        print(f"\n  Campaign created (ID: {camp['id']}).")
    except Exception as e:
        print(f"\n  Error: {e}")


def _edit_campaign(svc):
    print_header("Edit Campaign")
    try:
        cid = int(input("  Campaign ID: ").strip())
        camp = svc.get_campaign(cid)
        if not camp:
            print("\n  Campaign not found.")
            return
        print(f"  Editing: {camp['campaign_name']}")
        print("  (Leave blank to keep current value)\n")

        updates = {}
        name = input(f"  Campaign Name [{camp['campaign_name']}]: ").strip()
        if name:
            updates["campaign_name"] = name
        ctype = input(f"  Type [{camp.get('campaign_type', '')}]: ").strip()
        if ctype:
            updates["campaign_type"] = ctype
        start = input(f"  Start Date [{camp.get('start_date', '')}]: ").strip()
        if start:
            updates["start_date"] = start
        end = input(f"  End Date [{camp.get('end_date', '')}]: ").strip()
        if end:
            updates["end_date"] = end
        budget = input(f"  Budget [{camp.get('budget', 0)}]: ").strip()
        if budget:
            updates["budget"] = float(budget)
        spend = input(f"  Spend [{camp.get('spend', 0)}]: ").strip()
        if spend:
            updates["spend"] = float(spend)
        audience = input(f"  Target Audience [{camp.get('target_audience', '')}]: ").strip()
        if audience:
            updates["target_audience"] = audience
        channels = input(f"  Channels [{camp.get('channels', '')}]: ").strip()
        if channels:
            updates["channels"] = channels
        impressions = input(f"  Impressions [{camp.get('impressions', 0)}]: ").strip()
        if impressions:
            updates["impressions"] = int(impressions)
        enquiries = input(f"  Enquiries [{camp.get('enquiries', 0)}]: ").strip()
        if enquiries:
            updates["enquiries"] = int(enquiries)
        applications = input(f"  Applications [{camp.get('applications', 0)}]: ").strip()
        if applications:
            updates["applications"] = int(applications)
        notes = input(f"  Notes [{(camp.get('notes') or '')[:30]}]: ").strip()
        if notes:
            updates["notes"] = notes
        status = input(f"  Status [{camp.get('status', 'planned')}]: ").strip()
        if status:
            updates["status"] = status

        if not updates:
            print("\n  No changes made.")
            return
        svc.update_campaign(cid, **updates)
        print("\n  Campaign updated.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _delete_campaign(svc):
    try:
        cid = int(input("  Campaign ID: ").strip())
        confirm = input("  Delete this campaign? (y/n): ").strip().lower()
        if confirm != "y":
            print("\n  Cancelled.")
            return
        svc.delete_campaign(cid)
        print("\n  Campaign deleted.")
    except Exception as e:
        print(f"\n  Error: {e}")


# ── Statistics ──

def _show_stats(svc):
    print_header("Marketing Statistics")
    try:
        s = svc.get_stats()
        print("\n  === Open Day Events ===")
        print(f"  Total Events:        {s['total_events']}")
        print(f"  Total Registrations: {s['total_registrations']}")
        print(f"  Total Attended:      {s['total_attended']}")
        print(f"  Attendance Rate:     {s['attendance_rate']}%")
        print(f"  Follow-ups Sent:     {s['total_followed_up']}")
        print(f"  Applied After Visit: {s['total_applied']}")
        print(f"  Application Rate:    {s['application_rate']}%")
        print()
        print("  === Marketing Campaigns ===")
        print(f"  Total Campaigns:     {s['total_campaigns']}")
        print(f"  Total Budget:        ${s['total_budget']:,.2f}")
        print(f"  Total Spend:         ${s['total_spend']:,.2f}")
        print(f"  Budget Utilisation:  {s['budget_utilisation']}%")
        print(f"  Total Impressions:   {s['total_impressions']:,}")
        print(f"  Total Enquiries:     {s['total_enquiries']}")
        print(f"  Total Applications:  {s['total_applications']}")
    except Exception as e:
        print(f"\n  Error: {e}")
