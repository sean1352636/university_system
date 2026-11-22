"""CLI: the Batch Operations window's dashboard, settings, database,
duplicate review, "undo the last operation", the full history (jobs and
exports) and the API server - the same rules as the window
(``application/batch/window``, ``student_search_reports``,
``infrastructure/batch/api_server``)."""

from __future__ import annotations

from education_system.systems.university.application.batch import (
    jobs as batch_jobs,
    window as batch_window,
)
from education_system.systems.university.application.students import (
    search_reports as student_search_reports,
)
from education_system.systems.university.shell.cli.batch_cli import _db, _safe


def _dashboard(viewer):
    days = input("Last how many days (blank = 30): ").strip()
    d = _safe(_db, batch_window.dashboard, viewer, int(days) if days.isdigit() else 30)
    if not d:
        return
    rate = "-" if d["success_rate"] is None else f"{d['success_rate']}%"
    print(f"\nLast {d['days']} days: {d['jobs']} job(s), {d['rows']} row(s), {d['succeeded']} "
          f"done, {d['failed']} failed (success {rate}); {d['running']} running; "
          f"{d['exports']} export(s) of {d['rows_exported']} row(s); database "
          f"{d['database']['size_mb']} MB.")
    print("Recent jobs:")
    for j in d["recent"]:
        print(f"  #{j['id']:<5} {j['shown_kind']:<11} {j['started_at']}  {j['actor']:<12} "
              f"{j['status']:<8} done {j['succeeded']}, failed {j['failed']}")
    print("Scheduled tasks:")
    for t in d["scheduled"] or []:
        print(f"  {t['what']} - {t['when']} (next {t['next'] or '-'})")
    if not d["scheduled"]:
        print("  (none)")


def _settings(viewer):
    values = _db(batch_window.settings)
    for key, value in values.items():
        print(f"  {key:<28} {value}")
    if viewer.role not in batch_window.ADMIN_ROLES:
        print("Only an administrator can change these.")
        return
    key = input("Setting to change (blank = none): ").strip()
    if not key:
        return
    if key == "duplicate_rule":
        for k, label in batch_window.DUPLICATE_RULES.items():
            print(f"  {k}: {label}")
    value = input(f"New value for {key}: ").strip()
    if _safe(_db, batch_window.save_settings, viewer, {key: value}, write=True):
        print("Saved.")


def _database():
    info = _db(batch_window.database_info)
    print(f"\nDatabase {info['path']}\n  {info['size_mb']} MB ({info['free_mb']} MB free pages), "
          f"changed {info['modified']}, {info['tables']} tables, journal {info['journal_mode']}")
    for name, count in info["counts"].items():
        print(f"  {name:<22} {'-' if count is None else count}")
    if input("Run an integrity check? (y/N): ").strip().lower() == "y":
        print("  " + "\n  ".join(_db(batch_window.integrity_check)))


def _duplicates(viewer):
    rows = _safe(_db, student_search_reports.duplicates, viewer, False)
    if rows is None:
        return
    for i, r in enumerate(rows[:50], 1):
        print(f"  {i:>3}. {r['student_a']} {r['name_a']}  /  {r['student_b']} {r['name_b']}  "
              f"[{r['reasons']}]")
    if not rows:
        print("  No undecided possible duplicates.")
        return
    pick = input("Decide which pair (number, blank = none): ").strip()
    if not (pick.isdigit() and 0 < int(pick) <= min(len(rows), 50)):
        return
    r = rows[int(pick) - 1]
    decision = {"n": "not_duplicate", "d": "duplicate"}.get(
        input("n = not a duplicate, d = is a duplicate: ").strip().lower())
    if decision and _safe(_db, student_search_reports.review_duplicate, viewer, r["student_a"],
                          r["student_b"], decision, input("Note (optional): "), write=True):
        print("Recorded. Merging a real duplicate is done in Identity Management.")


def _undo_last(viewer):
    job = _db(batch_window.last_undoable, viewer)
    if not job:
        print("You have no finished import that can still be undone.")
        return
    print(f"Job #{job['id']}: {job['kind']}, {job['total']} row(s), {job['started_at']}")
    reason = input("Why is it being undone? (blank = cancel): ").strip()
    if reason:
        result = _safe(batch_jobs.undo, job["id"], viewer, reason)
        if result:
            print(f"{result['undone']} row(s) undone; {len(result['failed'])} not undone.")


def _history():
    shown = {"1": "All", "2": "Imports", "3": "Updates", "4": "Exports"}.get(
        input("Show 1. all  2. imports  3. updates  4. exports: ").strip(), "All")
    days = input("Last how many days (blank = the setting): ").strip()
    if not days.isdigit():
        days = _db(batch_window.setting, "history_days")
    rows = _db(batch_window.history, shown, int(days) if str(days).isdigit() else None)
    for r in rows[:100]:
        print(f"  {r['when']}  {r['operation']:<48} records {r['records']:<5} ok {r['success']:<5} "
              f"errors {r['errors']:<4} {r['by']}")
    if not rows:
        print("  (nothing in that period)")
    path = input("Save as CSV (blank = don't): ").strip()
    if path:
        print(f"Saved {batch_window.export_history_rows(rows, path)} entr(ies) to {path}.")


def _api(viewer):
    if viewer.role not in batch_window.ADMIN_ROLES:
        print("The API server is managed by administrators.")
        return
    from education_system.systems.university.infrastructure.batch import api_server
    s = api_server.status()
    print(f"\nAPI server: {s['state']}\n  {s['url']}  (host {s['host']}, port {s['port']})")
    for name, what in api_server.security():
        print(f"  {name}: {what}")
    choice = input("1. start  2. stop  3. show the log  (blank = back): ").strip()
    if choice == "1":
        if _safe(api_server.start) is not None:
            print("Starting; output goes to the API server log.")
    elif choice == "2":
        if _safe(api_server.stop) is not None:
            print("Stopped.")
    elif choice == "3":
        print(api_server.log_tail(80))


def menu_items(auth, viewer, start) -> dict:
    items = [("Dashboard", lambda: _dashboard(viewer)),
             ("Settings", lambda: _settings(viewer)),
             ("Database and integrity check", _database),
             ("Find duplicates (decide pairs)", lambda: _duplicates(viewer)),
             ("Undo my last operation", lambda: _undo_last(viewer)),
             ("Operation history (jobs and exports)", _history),
             ("API server (administrators)", lambda: _api(viewer))]
    return {str(i): item for i, item in enumerate(items, start)}
