"""CLI: Advanced student search - the same rules as the Advanced Search
window (``application/students/search``, ``student_search_saved``,
``student_bulk_actions``). Reports, follow-ups, favourites, history,
groups, email lists and exports are in ``student_search_tools_cli``."""

from __future__ import annotations

from contextlib import closing

from education_system.systems.university.application.students import bulk_actions as bulk
from education_system.systems.university.application.students import search
from education_system.systems.university.application.students import search_saved as saved
from education_system.systems.university.infrastructure.database.db import get_connection


def _viewer(auth):
    user = getattr(auth, "current_user", None) or {}
    check = getattr(auth, "check_permission", None) or (lambda _p: False)
    return search.Viewer.from_check(user.get("username") or "", user.get("role") or "", check,
                                    user.get("student_id") or user.get("username"))


def _run(fn, *args, write=False, **kwargs):
    try:
        with closing(get_connection(row_factory=False)) as conn:
            result = fn(conn, *args, **kwargs)
            if write:
                conn.commit()
    except ValueError as exc:
        print(f"Refused: {exc}")
        return None
    emails = result.get("emails") if isinstance(result, dict) else None
    if write and emails:
        from education_system.systems.university.application.teaching import (
            occurrences as timetable_occurrences,
        )
        timetable_occurrences.send_emails(emails)
    return True if result is None else result


def _reports_dir():
    from education_system.paths import UNIVERSITY_EXPORTS_DIR
    return str(UNIVERSITY_EXPORTS_DIR / "student_reports")


def _pick(options, prompt):
    for i, label in enumerate(options, 1):
        print(f"  {i}. {label}")
    pick = input(f"{prompt} (number, blank = done): ").strip()
    return int(pick) - 1 if pick.isdigit() and 0 < int(pick) <= len(options) else None


def _build_criteria(viewer):
    presets = list(saved.PRESETS)
    if input("Start from a ready-made search? (y/N): ").strip().lower() == "y":
        i = _pick(presets, "Ready-made search")
        if i is not None:
            return dict(saved.PRESETS[presets[i]])
    criteria = {"match": "all", "conditions": [], "text": input("Free text (blank = none): ").strip()}
    if criteria["text"]:
        criteria["all_fields"] = input("Look in every field, not just ID/name/email/course? "
                                       "(y/N): ").strip().lower() == "y"
    fields = search.fields_for(viewer)
    while len(criteria["conditions"]) < 8:
        i = _pick([f.label for f in fields], "Add a condition on")
        if i is None:
            break
        f = fields[i]
        ops = search.OPS[f.kind]
        j = _pick(ops, f"{f.label}")
        if j is None:
            continue
        value = "" if ops[j] in ("is empty", "is not empty") else input("Value: ").strip()
        criteria["conditions"].append({"field": f.key, "op": ops[j], "value": value})
    if len(criteria["conditions"]) > 1 and input("Match any instead of all? (y/N): ").lower() == "y":
        criteria["match"] = "any"
    return criteria


def _show(criteria, viewer, page=0, audit=False):
    result = _run(search.search, criteria, viewer, page=page, page_size=25, audit=audit,
                  write=audit)
    if not isinstance(result, dict):
        return None
    cols = result["columns"]
    print(f"\n{result['total']} student(s) - page {page + 1}: {search.describe(criteria)}")
    print("  " + " | ".join(search.FIELDS[c].label for c in cols))
    for row in result["rows"]:
        print("  " + " | ".join(str(row.get(c) if row.get(c) is not None else "") for c in cols))
    return result


def _browse(criteria, viewer):
    page, first = 0, True
    while True:
        result = _show(criteria, viewer, page, audit=first)
        first = False
        if not result:
            return
        choice = input("n next, p previous, s summary, c chart, e export, v save, "
                       "b bulk action, r reports, g groups, l email list, f follow-up, "
                       "a favourite, blank = back: ").strip().lower()
        if choice == "n" and (page + 1) * 25 < result["total"]:
            page += 1
        elif choice == "p" and page:
            page -= 1
        elif choice in _ACTIONS:
            _ACTIONS[choice](criteria, viewer)
        elif not choice:
            return


def _summary(criteria, viewer):
    result = _run(saved.summary, criteria, viewer)
    if isinstance(result, dict):
        print(saved.summary_text("Search summary", criteria, result))


def _chart(criteria, viewer):
    """The matches counted by one field, as text bars."""
    fields = saved.chart_fields(viewer)
    if not fields:
        print("There is nothing you can chart these results by.")
        return
    pick = _pick([label for _k, label in fields], "Chart by")
    if pick is None:
        return
    data = _run(saved.chart_data, criteria, viewer, fields[pick][0], write=True)
    if isinstance(data, dict):
        print()
        print(saved.chart_text(data) if data["values"] else "No values to chart.")


def _export(criteria, viewer):
    _tools().export_matches(criteria, viewer)


def _save(criteria, viewer):
    name = input("Name for this search: ").strip()
    shared = input("Share with other staff? (y/N): ").strip().lower() == "y"
    if name and _run(saved.save, viewer, name, criteria, shared, write=True):
        print("Saved.")


def _bulk(criteria, viewer):
    keys = list(bulk.ACTIONS)
    i = _pick([bulk.ACTIONS[k] for k in keys], "Action")
    if i is None:
        return
    key = keys[i]
    ids = _run(search.all_ids, criteria, viewer) or []
    value, subject = None, ""
    if key == "set_field":
        field = input(f"Field ({'/'.join(bulk.SETTABLE)}): ").strip()
        value = (field, input("New value: ").strip())
    elif key == "email":
        subject = input("Subject: ").strip()
        value = input("Message: ").strip()
    elif key not in ("withdraw", "reinstate"):
        value = input("Course code (transfer) or module code: ").strip()
    reason = "" if key == "email" else input("Reason (recorded on each student): ").strip()
    if input(f"{bulk.ACTIONS[key]} for {len(ids)} student(s)? (y/N): ").strip().lower() != "y":
        return
    try:
        result = bulk.run(key, ids, viewer, value=value, reason=reason, subject=subject)
    except ValueError as exc:
        print(f"Refused: {exc}")
        return
    print(f"Done: {result['done']}")
    for sid, why in result["failed"]:
        print(f"  {sid}: {why}")


def _tools():
    from education_system.systems.university.shell.cli import student_search_tools_cli
    return student_search_tools_cli


_ACTIONS = {"s": _summary, "c": _chart, "e": _export, "v": _save, "b": _bulk,
            "r": lambda c, v: _tools().reports_menu(c, v),
            "g": lambda c, v: _tools().groups(c, v),
            "l": lambda c, v: _tools().email_list(c, v),
            "f": lambda c, v: _tools().followup(c, v),
            "a": lambda c, v: _tools().favourite(c, v)}


def _saved_menu(viewer):
    rows = _run(saved.saved, viewer) or []
    for i, r in enumerate(rows, 1):
        print(f"  {i}. {r['name']} ({r['owner']}{', shared' if r['shared'] else ''}): "
              f"{r['summary']}")
    pick = input("Search number (i = import one from a file, blank = back): ").strip()
    if pick.lower() == "i":
        _tools().import_saved(viewer)
        return
    if not pick.isdigit() or not 0 < int(pick) <= len(rows):
        return
    r = rows[int(pick) - 1]
    choice = input("r run, s share/unshare, d delete, p schedule a report, x export to a "
                   "file: ").strip().lower()
    if choice == "r":
        _browse(r["criteria"], viewer)
    elif choice == "s":
        _run(saved.set_shared, viewer, r["id"], not r["shared"], write=True)
    elif choice == "d":
        _run(saved.delete, viewer, r["id"], write=True)
    elif choice == "p":
        _run(saved.schedule, viewer, r["id"], input("daily/weekly/monthly: ").strip().lower(),
             input("Email the summary to (comma-separated): "), write=True) and print("Scheduled.")
    elif choice == "x":
        _tools().export_saved(viewer, r)


def _schedules_menu(viewer):
    rows = _run(saved.schedules, viewer) or []
    for i, r in enumerate(rows, 1):
        print(f"  {i}. {r['name']} ({r['frequency']}, next {r['next_run_on']}, "
              f"{'active' if r['active'] else 'paused'}) -> {r['recipients']}; last: "
              f"{r['last_result'] or '-'}")
    pick = input("Report number (blank = back): ").strip()
    if not pick.isdigit() or not 0 < int(pick) <= len(rows):
        return
    r = rows[int(pick) - 1]
    choice = input("r run now, p pause/resume, d delete: ").strip().lower()
    if choice == "r":
        result = _run(saved.run_report, r, _reports_dir(), write=True)
        if isinstance(result, dict):
            print(f"{result['count']} student(s) saved to {result['file']}.")
    elif choice == "p":
        _run(saved.set_active, viewer, r["id"], not r["active"], write=True)
    elif choice == "d":
        _run(saved.remove_schedule, viewer, r["id"], write=True)


def _audit():
    for r in _run(search.audit_tail, 50) or []:
        count = r["count"] if r["count"] is not None else ""
        print(f"  {r['at']} {r['actor']:<12} {r['action']:<7} {count:>5}  "
              f"{r['criteria']} {r['detail'] or ''}")


def display_student_search_menu(auth=None):
    if auth is None:
        from education_system.systems.university.shell.cli.imports import get_auth
        auth = get_auth()
    viewer = _viewer(auth)
    if not viewer.username:
        print("You must be logged in to search student records.")
        return
    due = _run(saved.run_due, _reports_dir(), write=True)
    if isinstance(due, dict) and due["ran"]:
        print(f"Ran {due['ran']} scheduled report(s).")
    while True:
        staff = viewer.can_view_all
        print("\nAdvanced student search\n  1. New search\n  2. Saved searches\n"
              "  3. Scheduled reports" + ("\n  4. Search and export audit"
                                          if viewer.role in search.ADMIN_ROLES else "") +
              ("\n  5. Reports\n  6. Follow-ups\n  7. Favourites" if staff else "") +
              "\n  8. My search history\n  9. Repeat my last search\n  0. Back")
        choice = input("Choose: ").strip()
        if choice == "1":
            _browse(_build_criteria(viewer), viewer)
        elif choice == "2":
            _saved_menu(viewer)
        elif choice == "3":
            _schedules_menu(viewer)
        elif choice == "4" and viewer.role in search.ADMIN_ROLES:
            _audit()
        elif choice == "5" and staff:
            _tools().reports_menu({}, viewer)
        elif choice == "6" and staff:
            _tools().followups_menu(viewer)
        elif choice == "7" and staff:
            _tools().favourites_menu(viewer)
        elif choice == "8":
            _tools().history_menu(viewer)
        elif choice == "9":
            _tools().repeat_last(viewer)
        elif choice in ("0", ""):
            return


#: Name the admin-tools menu has always called.
display_enhanced_menu = display_student_search_menu
