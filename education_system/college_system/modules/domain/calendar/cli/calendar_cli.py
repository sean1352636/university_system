"""CLI interface for calendar management."""

import calendar as cal_mod
from datetime import date

from education_system.college_system.modules.shared.cli.cli_main import print_header, print_menu, get_choice
from education_system.college_system.modules.domain.calendar.services.calendar_service import CalendarService
from education_system.college_system.infrastructure.auth.core import UserAuth


def calendar_menu(auth: UserAuth):
    """Calendar management menu."""
    svc = CalendarService(auth._db_path)
    user_id = auth.current_user["user_id"]
    role = auth.current_user.get("role", "student")
    is_admin = role in ("admin", "staff")

    while True:
        print_header("Calendar")
        options = [
            ("1", "View Month"),
            ("2", "View Day"),
            ("3", "Add Event"),
            ("4", "Edit Event"),
            ("5", "Delete Event"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "1":
            _view_month(svc, user_id)
        elif choice == "2":
            _view_day(svc, user_id)
        elif choice == "3":
            _add_event(svc, user_id, is_admin)
        elif choice == "4":
            _edit_event(svc, user_id, is_admin)
        elif choice == "5":
            _delete_event(svc, user_id, is_admin)
        elif choice == "0":
            break


def _view_month(svc, user_id):
    today = date.today()
    month_str = input(f"  Month (1-12) [{today.month}]: ").strip()
    year_str = input(f"  Year [{today.year}]: ").strip()
    month = int(month_str) if month_str else today.month
    year = int(year_str) if year_str else today.year

    events = svc.list_events(user_id=user_id, month=month, year=year)

    print(f"\n  {cal_mod.month_name[month]} {year}")
    print(f"  {'Mon':>5} {'Tue':>5} {'Wed':>5} {'Thu':>5} {'Fri':>5} {'Sat':>5} {'Sun':>5}")

    events_by_day = {}
    for ev in events:
        try:
            day = int(ev["event_date"].split("-")[2])
            events_by_day.setdefault(day, []).append(ev)
        except (ValueError, IndexError):
            pass

    cal_matrix = cal_mod.monthcalendar(year, month)
    for week in cal_matrix:
        row = "  "
        for day in week:
            if day == 0:
                row += "     "
            else:
                marker = "*" if day in events_by_day else " "
                row += f"{day:>4}{marker}"
        print(row)

    if events:
        print(f"\n  Events this month ({len(events)}):")
        for ev in events:
            time_str = f" {ev['start_time']}" if ev.get("start_time") else ""
            print(f"  {ev['event_date']}{time_str} - {ev['title']} [{ev['event_type']}]")


def _view_day(svc, user_id):
    date_str = input(f"  Date (YYYY-MM-DD) [{date.today().isoformat()}]: ").strip()
    if not date_str:
        date_str = date.today().isoformat()

    events = svc.get_events_for_date(user_id, date_str)
    if not events:
        print(f"\n  No events on {date_str}.")
        return

    print(f"\n  Events on {date_str}:")
    for ev in events:
        time_str = ""
        if ev.get("start_time"):
            time_str = f" {ev['start_time']}"
            if ev.get("end_time"):
                time_str += f"-{ev['end_time']}"
        print(f"  [{ev['event_type']}]{time_str} {ev['title']}")
        if ev.get("description"):
            print(f"    {ev['description']}")


def _add_event(svc, user_id, is_admin):
    print_header("Add Event")
    title = input("  Title: ").strip()
    if not title:
        print("\n  Title is required.")
        return
    event_date = input(f"  Date (YYYY-MM-DD) [{date.today().isoformat()}]: ").strip()
    if not event_date:
        event_date = date.today().isoformat()
    start_time = input("  Start time (HH:MM, optional): ").strip() or None
    end_time = input("  End time (HH:MM, optional): ").strip() or None
    types = "personal/academic/deadline"
    if is_admin:
        types += "/college"
    event_type = input(f"  Type ({types}) [personal]: ").strip() or "personal"
    description = input("  Description (optional): ").strip() or None
    all_day = input("  All day? (y/n) [n]: ").strip().lower() == "y"

    try:
        event = svc.create_event(user_id, title, event_date, start_time,
                                 end_time, event_type, description, all_day)
        print(f"\n  Event created (ID: {event['id']})")
    except Exception as e:
        print(f"\n  Error: {e}")


def _edit_event(svc, user_id, is_admin):
    event_id = input("  Event ID: ").strip()
    try:
        event_id = int(event_id)
    except ValueError:
        print("\n  Invalid ID.")
        return

    title = input("  New title (Enter to skip): ").strip() or None
    event_date = input("  New date (Enter to skip): ").strip() or None

    kwargs = {}
    if title:
        kwargs["title"] = title
    if event_date:
        kwargs["event_date"] = event_date

    if not kwargs:
        print("\n  No changes made.")
        return

    try:
        svc.update_event(event_id, user_id, is_admin=is_admin, **kwargs)
        print("\n  Event updated.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _delete_event(svc, user_id, is_admin):
    event_id = input("  Event ID: ").strip()
    try:
        event_id = int(event_id)
    except ValueError:
        print("\n  Invalid ID.")
        return
    confirm = input("  Are you sure? (y/n): ").strip().lower()
    if confirm != "y":
        return
    try:
        svc.delete_event(event_id, user_id, is_admin=is_admin)
        print("\n  Event deleted.")
    except Exception as e:
        print(f"\n  Error: {e}")
