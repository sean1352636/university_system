"""Console menu for the academic year: years, terms, key dates, teaching
weeks, vacations, checks, importing dates, publishing, rollover — plus each
person's calendar feed and reminders, and the administrator tools (undated
events, calendar administrators, audit log).

Every action runs one rule from ``university/application/academic_calendar/`` in
its own transaction; the rules check permissions themselves.
"""

from __future__ import annotations

import json

from education_system.systems.university.application.academic_calendar import access as ca
from education_system.systems.university.application.academic_calendar import dates as cd
from education_system.systems.university.application.academic_calendar import events as ce
from education_system.systems.university.application.academic_calendar import year as cy


# ── console helpers ─────────────────────────────────────────────────────


def _ask(prompt, default=""):
    value = input(f"{prompt}{f' [{default}]' if default else ''}: ").strip()
    return value or default


def _confirm(prompt) -> bool:
    return _ask(f"{prompt} (y/n)").lower() in ("y", "yes")


def _emails(result):
    if isinstance(result, dict):
        return result.get("emails")
    if isinstance(result, list) and result and all(
            isinstance(e, tuple) and len(e) == 3 for e in result):
        return result
    return None


def _run(fn, *args, write=False, **kwargs):
    """Run ``fn(conn, *args)``; print refusals; ``None`` when refused."""
    from education_system.systems.university.infrastructure.database.db import get_connection
    from education_system.systems.university.infrastructure.ui import record_screens
    conn = get_connection(row_factory=False)
    try:
        result = fn(conn, *args, **kwargs)
        if write:
            conn.commit()
    except (ValueError, PermissionError) as exc:
        conn.rollback()
        print(f"\n  ✗ {exc}")
        return None
    except Exception as exc:
        conn.rollback()
        print(f"\n  ✗ That did not work: {exc}")
        return None
    finally:
        conn.close()
    emails = _emails(result) if write else None
    if emails:
        record_screens.send_emails(emails)
    return True if result is None else result


def _table(rows, columns):
    if not rows:
        print("  (nothing to show)")
        return
    print("  " + "  ".join(f"{name:<{width}}" for name, width in columns))
    for r in rows:
        print("  " + "  ".join(f"{str(r.get(name) if r.get(name) is not None else '—')[:width]:<{width}}"
                               for name, width in columns))


def _menu(title, items):
    """``items``: ``[(label, action)]``. Loops until 0."""
    while True:
        print(f"\n{title}\n" + "-" * len(title))
        for n, (label, _action) in enumerate(items, 1):
            print(f"  {n}. {label}")
        print("  0. Back")
        choice = _ask("Select")
        if choice in ("0", ""):
            return
        if choice.isdigit() and 1 <= int(choice) <= len(items):
            items[int(choice) - 1][1]()
        else:
            print("  Please choose a number from the list.")


# ── years ───────────────────────────────────────────────────────────────


def _list_years():
    rows = _run(cy.years) or []
    _table(rows if rows is not True else [], [("year_code", 10), ("start_date", 10),
                                               ("end_date", 10), ("status", 9), ("version", 7),
                                               ("bank_holiday_region", 18)])
    return rows if isinstance(rows, list) else []


def _pick_year():
    rows = _list_years()
    if not rows:
        return None
    code = _ask("Year (e.g. 2026/2027)", rows[0]["year_code"])
    return code.replace("-", "/") if code else None


def _new_year(who):
    first = _ask("First calendar year of the academic year (e.g. 2026)")
    if not first.isdigit():
        print("  Enter a year like 2026.")
        return
    start, end = cy.default_year_dates(int(first))
    start = _ask("Starts", start)
    end = _ask("Ends", end)
    region = _ask("Bank holidays for (" + " / ".join(cd.REGIONS) + ")", cd.REGIONS[0])
    code = _run(cy.create_year, who, f"{first}/{int(first) + 1}", start, end, region,
                write=True)
    if code:
        print(f"  ✓ {code} created as a draft, with its bank holidays.")


def _rollover(who):
    code = _pick_year()
    if not code:
        return
    new = _run(cd.rollover, who, code, write=True)
    if new:
        print(f"  ✓ {new} created as a draft from {code}. Check the dates marked "
              "'rolled forward' before publishing.")


# ── one year ────────────────────────────────────────────────────────────


def _show_year(code):
    row = _run(cy.year, code)
    if isinstance(row, dict):
        print(f"\n  {row['year_code']}: {row['start_date']} – {row['end_date']}  "
              f"[{row['status']}, version {row['version']}]  bank holidays: "
              f"{row['bank_holiday_region']}")


def _terms(code):
    _table(_run(cy.terms, code) or [], [("term_id", 7), ("name", 16), ("start_date", 10),
                                         ("end_date", 10)])


def _save_term(who, code, edit=False):
    term_id = None
    if edit:
        _terms(code)
        term_id = _ask("Term id to edit")
        if not term_id.isdigit():
            return
        term_id = int(term_id)
    name = _ask("Term name (e.g. Autumn)")
    start = _ask("Starts (YYYY-MM-DD)")
    end = _ask("Ends (YYYY-MM-DD)")
    if _run(cy.save_term, who, code, name, start, end, term_id, write=True):
        print("  ✓ Saved.")


def _delete_term(who, code):
    _terms(code)
    term_id = _ask("Term id to delete")
    if term_id.isdigit() and _confirm("Delete it?") and \
            _run(cy.delete_term, who, code, int(term_id), write=True):
        print("  ✓ Deleted.")


def _key_dates(code):
    _table(_run(cy.key_dates, code) or [], [("key_date_id", 5), ("kind", 16), ("title", 28),
                                             ("start_date", 10), ("end_date", 10),
                                             ("audience", 8), ("source", 10)])


def _save_key_date(who, code, edit=False):
    key_id = None
    if edit:
        _key_dates(code)
        key_id = _ask("Key date id to edit")
        if not key_id.isdigit():
            return
        key_id = int(key_id)
    print("  Kinds: " + ", ".join(cy.KINDS))
    kind = _ask("Kind", "other")
    title = _ask("Title", cy.KINDS.get(kind, ""))
    start = _ask("Date / starts (YYYY-MM-DD)")
    end = _ask("Ends (YYYY-MM-DD, blank for one day)")
    audience = _ask("Audience (all / students / staff)", "all")
    if _run(cy.save_key_date, who, code, kind, title, start, end or None, audience,
            key_date_id=key_id, write=True):
        print("  ✓ Saved.")


def _delete_key_date(who, code):
    _key_dates(code)
    key_id = _ask("Key date id to delete")
    if key_id.isdigit() and _confirm("Delete it?") and \
            _run(cy.delete_key_date, who, code, int(key_id), write=True):
        print("  ✓ Deleted.")


def _weeks(code):
    _table(_run(cd.weeks, code) or [], [("term", 12), ("week", 4), ("teaching_week", 13),
                                         ("start", 10), ("end", 10), ("why_not", 12)])


def _vacations(code):
    _table(_run(cd.vacation_periods, code) or [], [("start", 10), ("end", 10),
                                                    ("before", 14)])


def _checks(code):
    result = _run(cd.check_year, code)
    if isinstance(result, dict):
        _print_check(result)


def _print_check(result):
    for label, key in (("Problems (stop publishing)", "errors"), ("Warnings", "warnings"),
                       ("Clashes", "clashes")):
        items = result.get(key) or []
        print(f"\n  {label}: {len(items)}")
        for item in items:
            print(f"    • {item}")
    weeks = result.get("teaching_weeks") or {}
    if weeks:
        print("  Teaching weeks: " + ", ".join(f"{t} {n}" for t, n in weeks.items()))


def _import(who, code):
    counts = _run(cd.import_dates, who, code, write=True)
    if isinstance(counts, dict):
        print("  ✓ Imported: " + (", ".join(f"{k} {v}" for k, v in counts.items()) or
                                   "nothing found"))


def _edit_year(who, code):
    row = _run(cy.year, code)
    if not isinstance(row, dict):
        return
    start = _ask("Starts", row["start_date"])
    end = _ask("Ends", row["end_date"])
    if _run(cy.update_year, who, code, start, end, write=True):
        print("  ✓ Saved (bank holidays recomputed).")


def _publish(who, code):
    preview = _run(cy.preview_publish, who, code)
    if not isinstance(preview, dict):
        return
    _print_check(preview)
    print(f"\n  Changes since the last publication ({len(preview['changes'])}):")
    for change in preview["changes"]:
        print(f"    • {change}")
    if preview["supersedes"]:
        print("\n  These existing terms overlap the year and will be marked Superseded:")
        for t in preview["supersedes"]:
            print(f"    • {t['name']} ({t['academic_year']}) {t['start_date']} – {t['end_date']}")
    if preview["errors"]:
        print("\n  Fix the problems above before publishing.")
        return
    if not _confirm(f"Publish {code} as version {preview['version']} and tell staff and "
                    "students?"):
        return
    note = _ask("Note for the announcement (optional)")
    result = _run(cy.publish, who, code, note, write=True)
    if isinstance(result, dict):
        print(f"  ✓ Published version {result['version']}; {len(result['emails'])} e-mail(s).")


def _reopen(who, code):
    if _confirm(f"Reopen {code} as a draft? (Nothing changes for anyone until it is "
                "published again.)") and _run(cy.reopen, who, code, write=True):
        print("  ✓ Reopened.")


def _change_log(code):
    for entry in _run(cy.change_log, code) or []:
        print(f"\n  Version {entry['version']} — {entry['published_at']} by "
              f"{entry['published_by']}")
        for change in entry["changes"] or ["(first publication)"]:
            print(f"    • {change}")


def _year_menu(who, code):
    _show_year(code)
    _menu(f"Academic year {code}", [
        ("Terms", lambda: _terms(code)),
        ("Add a term", lambda: _save_term(who, code)),
        ("Edit a term", lambda: _save_term(who, code, edit=True)),
        ("Delete a term", lambda: _delete_term(who, code)),
        ("Key dates", lambda: _key_dates(code)),
        ("Add a key date", lambda: _save_key_date(who, code)),
        ("Edit a key date", lambda: _save_key_date(who, code, edit=True)),
        ("Delete a key date", lambda: _delete_key_date(who, code)),
        ("Teaching weeks", lambda: _weeks(code)),
        ("Vacation periods", lambda: _vacations(code)),
        ("Checks and clashes", lambda: _checks(code)),
        ("Import dates from registration, exams, graduation and boards",
         lambda: _import(who, code)),
        ("Edit the year's dates", lambda: _edit_year(who, code)),
        ("Preview and publish", lambda: _publish(who, code)),
        ("Reopen as a draft", lambda: _reopen(who, code)),
        ("Change log", lambda: _change_log(code)),
    ])


def _open_year(who):
    code = _pick_year()
    if code:
        _year_menu(who, code)


def _term_time():
    day = _ask("Date (YYYY-MM-DD)", ca.today())
    answer = _run(cd.is_term_time, day)
    term = _run(cd.term_for, day)
    if answer is None:
        print(f"  No published academic year covers {day}.")
    elif answer is True:
        print(f"  {day} is term time ({term['name']} {term['year_code']}).")
    elif isinstance(term, dict):
        print(f"  {day} is in {term['name']} {term['year_code']} but has no teaching "
              "(reading week, closure or bank holiday).")
    else:
        print(f"  {day} is vacation (between terms).")


# ── personal ────────────────────────────────────────────────────────────


def _feed(who):
    if _confirm("Make a new private calendar-feed link? (Any older link stops working.)"):
        result = _run(ce.create_feed, who, write=True)
        if isinstance(result, dict):
            print("\n  Subscribe to this address in Outlook or Google Calendar. It is shown "
                  "once and not stored:\n")
            print(f"  {result['url']}\n")
    elif _confirm("Turn off your current feed link instead?"):
        count = _run(ce.revoke_feed, who, write=True)
        print(f"  ✓ {count if isinstance(count, int) else 0} link(s) turned off.")


def _reminders(who):
    def show():
        _table(_run(ce.my_reminders, who) or [], [("reminder_id", 5), ("event_id", 38),
                                                  ("remind_at", 16)])

    def add():
        start = _ask("Events from (YYYY-MM-DD)", ca.today())
        end = _ask("to (YYYY-MM-DD)", start)
        events = _run(ce.visible_events, who, start, end) or []
        events = [e for e in events if e["source"] == "event"] if isinstance(events, list) \
            else []
        _table(events, [("id", 38), ("title", 30), ("start", 16)])
        event_id = _ask("Event id")
        minutes = _ask("Minutes before", "60")
        if event_id and minutes.isdigit() and _run(ce.add_reminder, who, event_id,
                                                   int(minutes), write=True):
            print("  ✓ Reminder set.")

    def cancel():
        show()
        rid = _ask("Reminder id to cancel")
        if rid.isdigit() and _run(ce.cancel_reminder, who, int(rid), write=True):
            print("  ✓ Cancelled.")

    _menu("My reminders", [("List", show), ("Add a reminder", add), ("Cancel a reminder",
                                                                       cancel)])


# ── administrators ──────────────────────────────────────────────────────


def _undated(who):
    rows = _run(ce.undated_events) or []
    _table(rows, [("event_id", 6), ("title", 32), ("event_date", 10), ("created_by", 10)])
    if not rows or not isinstance(rows, list):
        return
    if _confirm("Give each its start from its event date?"):
        delete = _confirm("Also delete the ones with no date at all?")
        result = _run(ce.repair_undated, who, delete, write=True)
        if isinstance(result, dict):
            print(f"  ✓ Fixed {result['fixed']}, deleted {result['removed']}.")


def _admins(who):
    def show():
        _table(_run(ca.admins) or [], [("username", 16), ("granted_by", 12),
                                       ("granted_at", 19)])

    def grant():
        username = _ask("Username")
        if username and _run(ca.grant, who, username, write=True):
            print("  ✓ Granted.")

    def revoke():
        show()
        username = _ask("Username")
        if username and _run(ca.revoke, who, username, write=True):
            print("  ✓ Removed.")

    _menu("Calendar administrators", [("List", show), ("Grant", grant), ("Remove", revoke)])


def _audit():
    rows = _run(ca.history) or []
    for r in rows if isinstance(rows, list) else []:
        detail = json.loads(r["detail"]) if r.get("detail") else ""
        print(f"  {r['at']}  {r['actor'] or '—':<12} {r['entity']}/{r['entity_id']}  "
              f"{r['action']}  {detail if detail else ''}"[:160])


# ── entry ───────────────────────────────────────────────────────────────


def _who(auth):
    user = getattr(auth, "current_user", None) if auth is not None else None
    if not user:
        try:
            from education_system.systems.university.infrastructure.shared_context import (
                get_auth,
            )
            shared = get_auth()
            user = getattr(shared, "current_user", None) if shared else None
        except Exception:
            user = None
    if not user:
        return None
    who = _run(ca.from_user, user, write=True)
    return who if isinstance(who, ca.CalendarUser) else None


def display_academic_year_menu(auth=None):
    """The Academic year menu (from the calendar CLI)."""
    who = _who(auth)
    if who is None:
        print("\n  You must be signed in to use the academic calendar.")
        return
    items = [("Academic years", _list_years), ("Open a year", lambda: _open_year(who)),
             ("Is a date term time?", _term_time),
             ("My calendar feed (Outlook / Google)", lambda: _feed(who)),
             ("My reminders", lambda: _reminders(who))]
    if who.is_admin:
        items[2:2] = [("New academic year", lambda: _new_year(who)),
                      ("Roll a year forward", lambda: _rollover(who))]
        items += [("Events with no start date", lambda: _undated(who)),
                  ("Calendar administrators", lambda: _admins(who)),
                  ("Calendar audit log", _audit)]
    _menu(f"Academic year — {who.username}" + (" (calendar administrator)" if who.is_admin
                                               else ""), items)


__all__ = ["display_academic_year_menu"]
