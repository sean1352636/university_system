"""CLI: Batch operations - the same rules as the Batch Operations window
(``application/batch/files``, ``batch_imports``, ``batch_enrolments``,
``batch_jobs``, ``batch_exports``; the reports, data quality, schedule,
e-mail and admin items are in ``batch_cli_extra``)."""

from __future__ import annotations

from contextlib import closing

from education_system.systems.university.application.batch import (
    files as batch_files,
    imports as batch_imports,
    jobs as batch_jobs,
)
from education_system.systems.university.application.students import bulk_actions as bulk
from education_system.systems.university.application.students import search as student_search
from education_system.systems.university.infrastructure.database.db import get_connection

KINDS = {"1": "students", "2": "marks", "3": "staff", "4": "enrolments"}


def _viewer(auth):
    user = getattr(auth, "current_user", None) or {}
    check = getattr(auth, "check_permission", None) or (lambda _p: False)
    return student_search.Viewer.from_check(user.get("username") or "", user.get("role") or "",
                                            check)


def _db(fn, *args, write=False, **kwargs):
    with closing(get_connection(row_factory=False)) as conn:
        result = fn(conn, *args, **kwargs)
        if write:
            conn.commit()
        return result


def _safe(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except ValueError as exc:
        print(f"Refused: {exc}")
        return None


def _print_result(result):
    for r in result["rows"]:
        print(f"  row {r['row_no']:>4}  {r['action']:<9} {r.get('ref') or '':<12} "
              f"{r.get('message') or ''}")
    print("  " + ", ".join(f"{k}: {v}" for k, v in result["counts"].items()) +
          (f"  (job #{result['job_id']})" if result.get("job_id") else "  (preview only)"))


def _import(auth, viewer):
    kind = KINDS.get(input("Import 1. students  2. marks  3. staff accounts  "
                           "4. module enrolments: ").strip())
    if not kind:
        return
    mode = None
    if kind == "students":
        mode = {"1": "create", "2": "update", "3": "both"}.get(
            input("1. add new  2. update existing (by student_id)  3. add or update: ").strip(),
            "create")
    path = input("File (.csv, .xlsx or .json; several separated by ';'): ").strip()
    if ";" in path:
        _import_many([p.strip() for p in path.split(";") if p.strip()], kind, mode, auth,
                     viewer)
        return
    sheet = None
    sheets = _safe(batch_files.sheet_names, path) or []
    if len(sheets) > 1:
        for i, name in enumerate(sheets, 1):
            print(f"  {i}. {name}")
        pick = input("Sheet (blank = first): ").strip()
        sheet = sheets[int(pick) - 1] if pick.isdigit() and 0 < int(pick) <= len(sheets) \
            else None
    loaded = _safe(batch_imports.read_and_map, path, kind, None, mode, sheet)
    if not loaded:
        return
    rows, mapping = loaded
    print("Columns used: " + ", ".join(f"{k} <- {v}" for k, v in mapping.items()))
    reason = input("Reason (recorded on each change): ").strip()
    preview = _run(kind, rows, viewer, mode, reason, path, True, auth)
    if preview:
        _print_result(preview)
        if input("Import for real? (y/N): ").strip().lower() == "y":
            result = _run(kind, rows, viewer, mode, reason, path, False, auth)
            if result:
                _print_result(result)


def _import_many(paths, kind, mode, auth, viewer):
    reason = input("Reason (recorded on each change): ").strip()
    if input(f"Import {len(paths)} file(s), each as its own job? (y/N): ").strip().lower() != "y":
        return
    for r in _safe(batch_imports.import_files, paths, kind, viewer, mode=mode or "create",
                   reason=reason, auth=auth) or []:
        counts = ", ".join(f"{k}: {v}" for k, v in r["counts"].items())
        print(f"  {r['file']}: " + (f"failed - {r['error']}" if r["error"]
                                    else f"job #{r['job_id']} ({counts})"))


def _run(kind, rows, viewer, mode, reason, path, dry_run, auth):
    if kind == "enrolments":
        from education_system.systems.university.application.batch import (
            enrolments as batch_enrolments,
        )
        override = (not dry_run and viewer.role in ("admin", "administrator", "superadmin")
                    and input("Override module rules where they refuse? (y/N): ").strip()
                    .lower() == "y")
        return _safe(batch_enrolments.import_enrolments, rows, viewer, reason=reason,
                     source=path, dry_run=dry_run, override=override)
    if kind == "marks":
        return _safe(batch_imports.import_marks, rows, viewer, reason=reason, source=path,
                     dry_run=dry_run)
    if kind == "staff":
        return _safe(batch_imports.import_staff, rows, viewer, reason=reason, source=path,
                     dry_run=dry_run, auth=auth)
    return _safe(batch_imports.import_students, rows, viewer, mode=mode, reason=reason,
                 source=path, dry_run=dry_run, auth=auth)


def _actions(viewer):
    keys = list(bulk.ACTIONS)
    for i, k in enumerate(keys, 1):
        print(f"  {i}. {bulk.ACTIONS[k]}")
    pick = input("Action: ").strip()
    if not pick.isdigit() or not 0 < int(pick) <= len(keys):
        return
    key = keys[int(pick) - 1]
    from education_system.systems.university.application.batch import exports as batch_exports
    how = input("Students: 1. file  2. type IDs  3. everyone on a course  4. a group  "
                "5. a saved search: ").strip()
    source = ""
    if how == "1":
        source = input("File with a student_id column: ").strip()
        loaded = _safe(batch_imports.read_and_map, source, "actions")
        rows = loaded[0] if loaded else []
    elif how in ("3", "4", "5"):
        choice = _pick_selection(how, viewer)
        if not choice:
            return
        method, value, source = choice
        ids = _safe(_db, batch_exports.select_students, viewer, method, value) or []
        rows = [{"student_id": s} for s in ids]
    else:
        rows = [{"student_id": s} for s in input("Student IDs (comma-separated): ").split(",")
                if s.strip()]
    print(f"{len(rows)} student(s) chosen.")
    if not rows:
        return
    value, subject = None, ""
    if key == "set_field":
        value = (input(f"Field ({'/'.join(bulk.SETTABLE)}): ").strip(), input("Value: ").strip())
    elif key == "email":
        subject, value = input("Subject: ").strip(), input("Message: ").strip()
    elif key not in ("withdraw", "reinstate"):
        value = input("Course code (transfer) or module code: ").strip()
    reason = "" if key == "email" else input("Reason: ").strip()
    result = _safe(batch_imports.run_actions, rows, viewer, key, value=value, reason=reason,
                   subject=subject, source=source or "typed list")
    if result:
        print(f"Job #{result['job_id']}: {result['done']} done")
        for sid, why in result["failed"]:
            print(f"  {sid}: {why}")


def _pick_selection(how, viewer):
    from education_system.systems.university.application.students import (
        search_saved as student_search_saved,
    )
    if how == "3":
        course = input("Course: ").strip()
        return ("course", course, f"course {course}") if course else None
    if how == "4":
        groups = list(student_search_saved.PRESETS)
        for i, g in enumerate(groups, 1):
            print(f"  {i}. {g}")
        pick = input("Group: ").strip()
        if pick.isdigit() and 0 < int(pick) <= len(groups):
            return "group", groups[int(pick) - 1], groups[int(pick) - 1]
        return None
    saved = _db(student_search_saved.saved, viewer)
    for s in saved:
        print(f"  {s['id']}. {s['name']}")
    pick = input("Saved search number: ").strip()
    return ("saved", int(pick), f"saved search {pick}") if pick.isdigit() else None


def _jobs(viewer):
    for j in _db(batch_jobs.jobs, limit=30):
        print(f"  #{j['id']:<4} {j['kind']:<8} {j['started_at']} {j['actor']:<10} {j['status']:<7} "
              f"done {j['succeeded']} skipped {j['skipped']} failed {j['failed']}  "
              f"{j['source'] or ''}")
    pick = input("Job number for details/undo (blank = back): ").strip()
    if not pick.isdigit():
        return
    detail = _safe(_db, batch_jobs.job, int(pick))
    if not detail:
        return
    for r in detail["rows"]:
        print(f"  row {r['row_no']:>4} {r['outcome']:<9} {r['ref'] or '':<12} {r['message'] or ''}")
    if input("Undo this job? (y/N): ").strip().lower() == "y":
        result = _safe(batch_jobs.undo, int(pick), viewer, input("Reason: ").strip())
        if result:
            print(f"{result['undone']} row(s) undone; {len(result['failed'])} not.")


def _watch(viewer):
    for w in _db(batch_jobs.watches, viewer):
        print(f"  #{w['id']} {w['kind']} {w['folder']} ({'active' if w['active'] else 'paused'})"
              f" daily at: {w.get('run_at') or 'manual'} last: {w['last_result'] or '-'}")
    choice = input("a add, t set daily time, p pause/resume, r remove, n run now, "
                   "blank = back: ").strip().lower()
    if choice == "t":
        from education_system.systems.university.application.batch import (
            schedule as batch_schedule,
        )
        wid = input("Folder number: ").strip()
        if wid.isdigit():
            _safe(_db, batch_schedule.set_watch_time, viewer, int(wid),
                  input("Daily at (HH:MM, blank = manual only): ").strip(), write=True)
        return
    if choice == "a":
        kind = "marks" if input("Marks folder? (y = marks, n = students): ").lower() == "y" \
            else "students"
        _safe(_db, batch_jobs.add_watch, viewer, kind, input("Folder: ").strip(),
              input("Reason recorded on each change: ").strip(), write=True)
    elif choice in ("p", "r"):
        wid = input("Folder number: ").strip()
        if wid.isdigit() and choice == "r":
            _safe(_db, batch_jobs.remove_watch, viewer, int(wid), write=True)
        elif wid.isdigit():
            current = {w["id"]: w for w in _db(batch_jobs.watches, viewer)}.get(int(wid))
            if current:
                _safe(_db, batch_jobs.set_watch_active, viewer, int(wid),
                      not current["active"], write=True)
    elif choice == "n":
        for wid, result in batch_imports.run_watch_folders()["watches"]:
            print(f"  #{wid}: {result}")


def _template():
    kind = KINDS.get(input("Template for 1. students  2. marks  3. staff accounts  "
                           "4. module enrolments: ").strip())
    if kind:
        path = input("Save to (.csv): ").strip()
        if path:
            print(f"Saved {batch_files.write_template(kind, path)}")


def display_batch_menu(auth=None):
    if auth is None:
        from education_system.systems.university.shell.cli.imports import get_auth
        auth = get_auth()
    viewer = _viewer(auth)
    if not (viewer.can_update or viewer.can_mark or viewer.can_manage_users):
        print("You do not have permission to use batch operations.")
        return
    ran = _safe(batch_imports.run_watch_folders)
    if ran and ran["watches"]:
        print("Watched folders: " + "; ".join(f"#{w}: {r}" for w, r in ran["watches"]))
    menu = {"1": ("Import from a file (preview, then import)", lambda: _import(auth, viewer)),
            "2": ("Bulk action on a list of students", lambda: _actions(viewer)),
            "3": ("Jobs: details and undo", lambda: _jobs(viewer)),
            "4": ("Watched folders", lambda: _watch(viewer)),
            "5": ("Download a template", _template)}
    from education_system.systems.university.shell.cli import batch_cli_extra
    menu.update(batch_cli_extra.menu_items(auth, viewer, start=6))
    from education_system.systems.university.shell.cli import batch_cli_window
    menu.update(batch_cli_window.menu_items(auth, viewer, start=len(menu) + 1))
    while True:
        print("\nBatch operations")
        for key, (label, _fn) in menu.items():
            print(f"  {key}. {label}")
        print("  0. Back")
        choice = input("Choose: ").strip()
        if choice in menu:
            menu[choice][1]()
        elif choice in ("0", ""):
            return
