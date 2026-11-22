"""CLI: the reports, follow-ups, favourites, history, groups, email lists,
exports and saved-search files of Advanced student search - the same rules
as the window (``application/students/search_reports``,
``student_search_extras``, ``student_search``)."""

from __future__ import annotations

from education_system.systems.university.application.students import search
from education_system.systems.university.application.students import search_extras as extras
from education_system.systems.university.application.students import search_reports as reports
from education_system.systems.university.infrastructure.data_management import table_export


def _cli():
    from education_system.systems.university.shell.cli import student_search_cli
    return student_search_cli


def _ask_ids(criteria, viewer):
    raw = input("Student IDs (comma-separated, blank = every match): ").strip()
    if raw:
        return [s.strip() for s in raw.split(",") if s.strip()]
    return _cli()._run(search.all_ids, criteria, viewer) or []


def _ask_format(default_name):
    keys = [k for k in table_export.FORMATS]
    i = _cli()._pick([table_export.FORMATS[k] for k in keys], "Format")
    if i is None:
        return None
    fmt = keys[i]
    path = input(f"Save to [{default_name}{table_export.EXTENSIONS[fmt]}]: ").strip() \
        or f"{default_name}{table_export.EXTENSIONS[fmt]}"
    if not path.lower().endswith(table_export.EXTENSIONS[fmt]):
        path += table_export.EXTENSIONS[fmt]
    delimiter = ","
    if fmt == "delimited":
        delimiter = input("Delimiter (one character): ").strip()[:1] or ";"
    return path, fmt, delimiter


# ── from a result list ──────────────────────────────────────────────────


def export_matches(criteria, viewer):
    target = _ask_format("students")
    if not target:
        return
    path, fmt, delimiter = target
    fields = [f.key for f in search.columns_for(viewer)]
    print("Fields: " + ", ".join(fields))
    chosen = input("Fields to include (comma-separated, blank = all): ").strip()
    picked = [f.strip() for f in chosen.split(",") if f.strip()] or None
    raw = input("Only these student IDs (comma-separated, blank = every match): ").strip()
    ids = [s.strip() for s in raw.split(",") if s.strip()] or None
    n = _cli()._run(search.export, criteria, viewer, path, picked, fmt, ids=ids,
                    delimiter=delimiter, write=True)
    if n is not None:
        print(f"Exported {n} student(s) to {path} (recorded in the audit).")


def groups(criteria, viewer):
    keys = list(extras.GROUP_METHODS)
    i = _cli()._pick([extras.GROUP_METHODS[k] for k in keys], "Group")
    if i is None:
        return
    size = input("Group size (for N-sized groups) [5]: ").strip() or "5"
    made = _cli()._run(extras.make_groups, criteria, viewer, keys[i], size, write=True)
    if not isinstance(made, dict):
        return
    for name, members in made.items():
        print(f"\n{name} ({len(members)})")
        for r in members:
            print(f"  {r['student_id']}  {r.get('name') or ''}  {r.get('course') or ''}")
    if input("\nExport the groups? (y/N): ").strip().lower() == "y":
        target = _ask_format("groups")
        if target:
            path, fmt, delimiter = target
            columns, rows = extras.groups_table(made)
            table_export.write(path, columns, rows, fmt, title="Student groups",
                               delimiter=delimiter)
            print(f"Saved {len(rows)} row(s) to {path}.")


def email_list(criteria, viewer):
    keys = list(extras.LIST_LAYOUTS)
    i = _cli()._pick([extras.LIST_LAYOUTS[k] for k in keys], "Layout")
    if i is None:
        return
    personal = viewer.can_view_sensitive and \
        input("Personal addresses instead of university ones? (y/N): ").strip().lower() == "y"
    result = _cli()._run(extras.email_list, criteria, viewer, keys[i], personal, write=True)
    if isinstance(result, dict):
        print(f"\n{result['text']}\n\n{result['count']} address(es)"
              + (f"; without a valid address: {', '.join(result['missing'])}"
                 if result["missing"] else ""))


def followup(criteria, viewer):
    ids = _ask_ids(criteria, viewer)
    if not ids:
        return
    reason = input("Reason: ").strip()
    priority = input("Priority (high/medium/low) [medium]: ").strip().lower() or "medium"
    due = input("Due (YYYY-MM-DD, blank = none): ").strip() or None
    assignee = input("Assign to (username, blank = nobody): ").strip() or None
    result = _cli()._run(extras.mark_followup, viewer, ids, reason, priority, due, assignee,
                         write=True)
    if isinstance(result, dict):
        print(f"{result['marked']} student(s) marked for follow-up.")


def favourite(criteria, viewer):
    raw = input("Student IDs to add to your favourites (comma-separated): ").strip()
    ids = [s.strip() for s in raw.split(",") if s.strip()]
    if not ids:
        return
    note = input("Note (optional): ").strip()

    def add_all(conn):
        for sid in ids:
            extras.add_favourite(conn, viewer, sid, note)

    if _cli()._run(add_all, write=True):
        print(f"{len(ids)} added.")


# ── menus ───────────────────────────────────────────────────────────────


def _print_report(report):
    print()
    print(report["text"])


def reports_menu(criteria, viewer):
    if not viewer.can_view_all:
        print("Reports are for staff who can see every student.")
        return
    admin = viewer.role in search.ADMIN_ROLES
    names = [k for k in reports.REPORTS if admin or k not in reports.ADMIN_REPORTS]
    i = _cli()._pick([reports.REPORTS[k] for k in names], "Report")
    if i is None:
        return
    name = names[i]
    scope = criteria if criteria and input(
        "Only the current search's students? (Y/n): ").strip().lower() != "n" else {}
    options = {}
    if name == "crosstab":
        dims = _cli()._run(reports.available_dimensions) or {}
        keys = list(dims)
        r = _cli()._pick([dims[k] for k in keys], "Rows")
        c = _cli()._pick([dims[k] for k in keys], "Columns")
        if r is None or c is None:
            return
        options.update(row=keys[r], col=keys[c])
    elif name == "student_performance":
        options["student_id"] = input("Student ID: ").strip()
    report = _cli()._run(reports.generate, name, scope, viewer, write=True, **options)
    if not isinstance(report, dict):
        return
    _print_report(report)
    if name == "duplicates" and viewer.can_update and report["rows"] and \
            input("\nRecord a decision on a pair? (y/N): ").strip().lower() == "y":
        a, b = input("First student ID: ").strip(), input("Second student ID: ").strip()
        decision = "duplicate" if input("Is it a duplicate? (y/N): ").strip().lower() == "y" \
            else "not_duplicate"
        if _cli()._run(reports.review_duplicate, viewer, a, b, decision,
                       input("Note: ").strip(), write=True):
            print("Recorded.")
    if name == "system" and admin and \
            input("\nRefresh the query statistics (optimise)? (y/N): ").strip().lower() == "y":
        print(_cli()._run(reports.optimise, viewer, write=True))
    if viewer.can_export and input("\nExport this report? (y/N): ").strip().lower() == "y":
        target = _ask_format("report")
        if target:
            path, fmt, delimiter = target
            n = _cli()._run(reports.export, report, viewer, path, fmt, delimiter, write=True)
            if n is not None:
                print(f"Saved {n} row(s) to {path}.")


def followups_menu(viewer):
    if not viewer.can_view_all:
        print("Follow-ups are for staff who can see every student.")
        return
    mine = input("Only mine? (y/N): ").strip().lower() == "y"
    rows = _cli()._run(extras.followups, viewer, "open", mine) or []
    for r in rows:
        print(f"  #{r['id']} [{r['priority']}] {r['student_id']} {r.get('name') or ''}: "
              f"{r['reason']} (due {r['due_on'] or '-'}, for {r['assigned_to'] or '-'}, "
              f"by {r['created_by']})")
    if not rows:
        print("  No open follow-ups.")
        return
    pick = input("Close follow-up number (blank = back): ").strip().lstrip("#")
    if pick.isdigit():
        outcome = input("What was done? ").strip()
        if _cli()._run(extras.close_followup, viewer, int(pick), outcome, write=True):
            print("Closed.")


def favourites_menu(viewer):
    rows = _cli()._run(extras.favourites, viewer) or []
    for r in rows:
        print(f"  {r['student_id']}  {r['name']}  {r['course'] or ''}  {r['status'] or ''}"
              f"  {r['note'] or ''}")
    if not rows:
        print("  No favourites yet (add them from a search result: a).")
        return
    choice = input("r remove, p performance, blank = back: ").strip().lower()
    if choice in ("r", "p"):
        sid = input("Student ID: ").strip()
        if choice == "r" and _cli()._run(extras.remove_favourite, viewer, sid, write=True):
            print("Removed.")
        elif choice == "p":
            report = _cli()._run(reports.generate, "student_performance", {}, viewer,
                                 student_id=sid, write=True)
            if isinstance(report, dict):
                _print_report(report)


def history_menu(viewer):
    rows = _cli()._run(extras.history, viewer, 40) or []
    for i, r in enumerate(rows, 1):
        print(f"  {i}. {r['at']} {r['action']:<7} {r['count'] if r['count'] is not None else '':>5}"
              f"  {r['search']} {r['detail']}")
    pick = input("Run again (number, blank = back): ").strip()
    if pick.isdigit() and 0 < int(pick) <= len(rows) and rows[int(pick) - 1]["criteria"]:
        _cli()._browse(rows[int(pick) - 1]["criteria"], viewer)


def repeat_last(viewer):
    criteria = _cli()._run(extras.last_search, viewer)
    if isinstance(criteria, dict):
        _cli()._browse(criteria, viewer)
    else:
        print("You have no earlier search.")


def export_saved(viewer, saved_row):
    path = input(f"Save to [{saved_row['name']}.json]: ").strip() or f"{saved_row['name']}.json"
    if _cli()._run(extras.export_saved, viewer, saved_row["id"], path):
        print(f"Saved to {path}.")


def import_saved(viewer):
    path = input("Saved search file (.json): ").strip()
    if not path:
        return
    shared = input("Share with other staff? (y/N): ").strip().lower() == "y"
    if _cli()._run(extras.import_saved, viewer, path, shared, write=True):
        print("Imported.")
