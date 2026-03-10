"""Alumni Network CLI module."""

from education_system.college_system.modules.shared.cli.cli_main import (
    print_header, print_menu, get_choice,
)
from education_system.college_system.modules.domain.alumni.services.alumni_service import AlumniService
from education_system.college_system.infrastructure.auth.core import UserAuth


def alumni_menu(auth: UserAuth):
    """Alumni Network management menu."""
    svc = AlumniService(auth._db_path)

    while True:
        print_header("Alumni Network")
        options = [
            ("1", "List Alumni"),
            ("2", "Search Alumni"),
            ("3", "View Alumni"),
            ("4", "New Alumni Record"),
            ("5", "Update Alumni Record"),
            ("6", "Delete Alumni Record"),
            ("7", "List Events"),
            ("8", "New Event"),
            ("9", "Update Event"),
            ("10", "List Surveys"),
            ("11", "New Survey"),
            ("12", "Statistics"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "0":
            break

        elif choice == "1":
            year = input("  Graduation year (or Enter for all): ").strip() or None
            records = svc.list_records(graduation_year=year)
            for r in records:
                mentor = "M" if r.get("willing_to_mentor") else ""
                speaker = "S" if r.get("willing_to_speak") else ""
                flags = f" [{mentor}{speaker}]" if mentor or speaker else ""
                print(f"  [{r['id']}] {r['first_name']} {r['last_name']} "
                      f"({r.get('graduation_year', '?')}) "
                      f"{r.get('current_employer', '') or r.get('university_attended', '')}"
                      f"{flags}")
            if not records:
                print("  No alumni records found.")

        elif choice == "2":
            term = input("  Search (name/email/employer): ").strip()
            if not term:
                print("  No search term entered.")
                continue
            records = svc.list_records(search=term)
            for r in records:
                print(f"  [{r['id']}] {r['first_name']} {r['last_name']} "
                      f"- {r.get('email', '')} - {r.get('current_employer', '')}")
            if not records:
                print("  No results found.")

        elif choice == "3":
            try:
                rid = int(input("  Alumni ID: ").strip())
                rec = svc.get_record(rid)
                if not rec:
                    print("  Record not found.")
                    continue
                print(f"\n  Name:         {rec['first_name']} {rec['last_name']}")
                print(f"  Email:        {rec.get('email', '')}")
                print(f"  Phone:        {rec.get('phone', '')}")
                print(f"  Grad Year:    {rec.get('graduation_year', '')}")
                print(f"  Courses:      {rec.get('courses_studied', '')}")
                print(f"  Employer:     {rec.get('current_employer', '')}")
                print(f"  Role:         {rec.get('current_role', '')}")
                print(f"  University:   {rec.get('university_attended', '')}")
                print(f"  Degree:       {rec.get('degree_achieved', '')}")
                print(f"  Mentor:       {'Yes' if rec.get('willing_to_mentor') else 'No'}")
                print(f"  Speaker:      {'Yes' if rec.get('willing_to_speak') else 'No'}")
                print(f"  Notes:        {rec.get('notes', '')}")
            except ValueError:
                print("  Invalid ID.")

        elif choice == "4":
            try:
                fn = input("  First Name: ").strip()
                ln = input("  Last Name: ").strip()
                if not fn or not ln:
                    print("  First and last name are required.")
                    continue
                email = input("  Email: ").strip() or None
                phone = input("  Phone: ").strip() or None
                year = input("  Graduation Year: ").strip() or None
                courses = input("  Courses Studied: ").strip() or None
                employer = input("  Current Employer: ").strip() or None
                role = input("  Current Role: ").strip() or None
                uni = input("  University Attended: ").strip() or None
                degree = input("  Degree Achieved: ").strip() or None
                mentor = input("  Willing to Mentor? (y/n): ").strip().lower() == "y"
                speaker = input("  Willing to Speak? (y/n): ").strip().lower() == "y"
                notes = input("  Notes: ").strip() or None
                rec = svc.create_record(
                    fn, ln, email=email, phone=phone,
                    graduation_year=year, courses_studied=courses,
                    current_employer=employer, current_role=role,
                    university_attended=uni, degree_achieved=degree,
                    willing_to_mentor=1 if mentor else 0,
                    willing_to_speak=1 if speaker else 0,
                    notes=notes)
                print(f"\n  Alumni record #{rec['id']} created.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "5":
            try:
                rid = int(input("  Alumni ID to update: ").strip())
                rec = svc.get_record(rid)
                if not rec:
                    print("  Record not found.")
                    continue
                print(f"  Current: {rec['first_name']} {rec['last_name']}")
                print("  (Press Enter to keep current value)")
                kwargs = {}
                for field, label in [
                    ("email", "Email"), ("phone", "Phone"),
                    ("current_employer", "Current Employer"),
                    ("current_role", "Current Role"),
                    ("university_attended", "University"),
                    ("degree_achieved", "Degree"),
                ]:
                    val = input(f"  {label} [{rec.get(field, '')}]: ").strip()
                    if val:
                        kwargs[field] = val
                m = input(f"  Willing to Mentor [{rec.get('willing_to_mentor', 0)}] (y/n/Enter): ").strip().lower()
                if m in ("y", "n"):
                    kwargs["willing_to_mentor"] = 1 if m == "y" else 0
                s = input(f"  Willing to Speak [{rec.get('willing_to_speak', 0)}] (y/n/Enter): ").strip().lower()
                if s in ("y", "n"):
                    kwargs["willing_to_speak"] = 1 if s == "y" else 0
                notes = input(f"  Notes [{(rec.get('notes', '') or '')[:40]}]: ").strip()
                if notes:
                    kwargs["notes"] = notes
                if kwargs:
                    svc.update_record(rid, **kwargs)
                    print("  Record updated.")
                else:
                    print("  Nothing to update.")
            except ValueError:
                print("  Invalid ID.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "6":
            try:
                rid = int(input("  Alumni ID to delete: ").strip())
                confirm = input(f"  Delete alumni #{rid}? (y/n): ").strip().lower()
                if confirm == "y":
                    svc.delete_record(rid)
                    print("  Record deleted.")
                else:
                    print("  Cancelled.")
            except ValueError:
                print("  Invalid ID.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "7":
            events = svc.list_events()
            for ev in events:
                print(f"  [{ev['id']}] {ev['event_name']} - {ev.get('event_date', '')} "
                      f"({ev.get('event_type', '')}) [{ev.get('status', '')}] "
                      f"Attendees: {ev.get('attendee_count', 0)}")
            if not events:
                print("  No events found.")

        elif choice == "8":
            try:
                name = input("  Event Name: ").strip()
                date = input("  Event Date (YYYY-MM-DD): ").strip()
                if not name or not date:
                    print("  Name and date are required.")
                    continue
                etype = input("  Type (reunion/networking/careers_talk/fundraiser/open_day/other): ").strip() or "reunion"
                location = input("  Location: ").strip() or None
                desc = input("  Description: ").strip() or None
                ev = svc.create_event(name, date, event_type=etype,
                                       location=location, description=desc)
                print(f"\n  Event #{ev['id']} created.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "9":
            try:
                eid = int(input("  Event ID to update: ").strip())
                ev = svc.get_event(eid)
                if not ev:
                    print("  Event not found.")
                    continue
                print(f"  Current: {ev['event_name']} ({ev.get('status', '')})")
                kwargs = {}
                status = input(f"  Status [{ev.get('status', '')}] (planned/confirmed/completed/cancelled): ").strip()
                if status:
                    kwargs["status"] = status
                ac = input(f"  Attendee Count [{ev.get('attendee_count', 0)}]: ").strip()
                if ac:
                    kwargs["attendee_count"] = int(ac)
                loc = input(f"  Location [{ev.get('location', '')}]: ").strip()
                if loc:
                    kwargs["location"] = loc
                if kwargs:
                    svc.update_event(eid, **kwargs)
                    print("  Event updated.")
                else:
                    print("  Nothing to update.")
            except ValueError:
                print("  Invalid input.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "10":
            aid = input("  Alumni ID (or Enter for all): ").strip()
            surveys = svc.list_surveys(alumni_id=int(aid) if aid else None)
            for s in surveys:
                name = f"{s.get('first_name', '')} {s.get('last_name', '')}".strip() or f"Alumni #{s.get('alumni_id', '')}"
                print(f"  [{s['id']}] {name} - Year: {s.get('survey_year', '?')} "
                      f"Employment: {s.get('employment_status', '?')} "
                      f"Rating: {s.get('satisfaction_rating', '?')}/5 "
                      f"Recommend: {'Yes' if s.get('would_recommend') else 'No'}")
            if not surveys:
                print("  No surveys found.")

        elif choice == "11":
            try:
                aid = int(input("  Alumni ID: ").strip())
                year = input("  Survey Year: ").strip() or None
                emp = input("  Employment Status (employed/self_employed/further_education/unemployed/gap_year/other): ").strip() or None
                sat = input("  Satisfaction Rating (1-5): ").strip()
                rec = input("  Would Recommend? (y/n): ").strip().lower() != "n"
                fb = input("  Feedback: ").strip() or None
                s = svc.create_survey(
                    aid, survey_year=year, employment_status=emp,
                    satisfaction_rating=int(sat) if sat else None,
                    would_recommend=1 if rec else 0, feedback=fb)
                print(f"\n  Survey #{s['id']} recorded.")
            except ValueError:
                print("  Invalid input.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "12":
            try:
                stats = svc.get_stats()
                print(f"\n  Total Alumni:        {stats['total_alumni']}")
                print(f"  Willing to Mentor:   {stats['willing_to_mentor']}")
                print(f"  Willing to Speak:    {stats['willing_to_speak']}")
                print(f"  At University:       {stats['at_university']}")
                print(f"  Currently Employed:  {stats['employed']}")
                print(f"  Total Events:        {stats['total_events']}")
                print(f"  Total Surveys:       {stats['total_surveys']}")
                sat = stats['avg_satisfaction']
                print(f"  Avg Satisfaction:    {sat}/5" if sat else "  Avg Satisfaction:    N/A")
            except Exception as e:
                print(f"\n  Error: {e}")

        else:
            print("\n  Invalid option.")
