"""CLI: the Batch Operations items beyond import / bulk actions / jobs /
watched folders - export, statistics, resume, history, data quality,
reports, the schedule, e-mail campaigns, role permissions and the
administrator utilities. Same rules as the window (``application/
batch_exports``, ``batch_reports``, ``batch_schedule``, ``batch_admin``)."""

from __future__ import annotations

from education_system.systems.university.application.batch import (
    admin as batch_admin,
    exports as batch_exports,
    imports as batch_imports,
    reports as batch_reports,
    schedule as batch_schedule,
)
from education_system.systems.university.application.students import (
    search_saved as student_search_saved,
)
from education_system.systems.university.shell.cli.batch_cli import _db, _safe

FORMATS = {"1": "csv", "2": "xlsx", "3": "json"}
REPORTS = {"1": "success", "2": "errors", "3": "performance", "4": "comprehensive",
           "5": "statistics"}


def _admin(viewer):
    return viewer.role in batch_exports.ADMIN_ROLES


def _group():
    groups = list(student_search_saved.PRESETS) + ["All students"]
    for i, g in enumerate(groups, 1):
        print(f"  {i}. {g}")
    pick = input("Students (number, blank = current students): ").strip()
    if pick.isdigit() and 0 < int(pick) <= len(groups):
        return groups[int(pick) - 1]
    return "Current students"


def _export(viewer):
    fmt = FORMATS.get(input("Format 1. CSV  2. Excel  3. JSON: ").strip(), "csv")
    group = _group()
    course = input("Only course (blank = any): ").strip() or None
    start = input("Registered from (YYYY-MM-DD, blank = any): ").strip() or None
    end = input("Registered to (YYYY-MM-DD, blank = any): ").strip() or None
    modules = input("Include each student's modules? (y/N): ").strip().lower() == "y"
    path = input(f"Save to (.{fmt}): ").strip()
    if not path:
        return
    n = _safe(_db, batch_exports.export_students, viewer, path, fmt=fmt, group=group,
              course=course, date_from=start, date_to=end, include_modules=modules, write=True)
    if n is not None:
        print(f"Exported {n} student(s) to {path}.")


def _statistics(viewer):
    report = _safe(_db, batch_reports.enrolment_statistics, viewer)
    if report:
        print(batch_reports.as_text(report))
        _offer_save(report)


def _offer_save(report):
    path = input("Save as (.json or .csv, blank = don't): ").strip()
    if path:
        saved = _safe(batch_reports.write_report, report, path)
        if saved:
            print(f"Saved {saved}")


def _resume(auth, viewer):
    found = _db(batch_imports.interrupted)
    if not found:
        print("No import was interrupted part-way.")
        return
    for j in found:
        print(f"  #{j['id']} {j['kind']} {j['source'] or ''}: {j['rows_done']} row(s) done"
              + ("" if j["resumable"] else " (file gone)"))
    pick = input("Resume job number (blank = back): ").strip()
    if pick.isdigit():
        result = _safe(batch_imports.resume, int(pick), viewer, auth=auth)
        if result:
            counts = ", ".join(f"{k}: {v}" for k, v in result["counts"].items())
            print(f"Resumed as job #{result['job_id']} ({result['rows_remaining']} row(s) "
                  f"left): {counts}")


def _history(viewer):
    kind = input("Kind (students/marks/staff/enrolments/actions, blank = all): ").strip() or None
    path = input("Save history to (.csv): ").strip()
    if path:
        n = _safe(_db, batch_reports.export_history, viewer, path, kind)
        if n is not None:
            print(f"{n} job(s) saved to {path}.")


def _quality(viewer):
    dash = _safe(_db, batch_admin.quality_dashboard, viewer)
    if not dash:
        return
    print(batch_admin.quality_report_text(dash))
    fixable = [i for i in dash["list"] if i["fix"]]
    choice = input(f"f fix all {len(fixable)} safe issue(s), e e-mail the report to the "
                   "administrators, blank = back: ").strip().lower()
    if choice == "f" and fixable and input("Apply them? Each is written to the change "
                                           "history. (y/N): ").strip().lower() == "y":
        n = _safe(_db, batch_admin.apply_quality_fixes, viewer, [i["key"] for i in fixable],
                  write=True)
        if n is not None:
            print(f"{n} record(s) corrected.")
    elif choice == "e":
        emails = _safe(_db, batch_admin.quality_report_emails, viewer, write=True)
        if emails:
            from education_system.systems.university.infrastructure.ui.record_screens import (
                send_emails,
            )
            print(f"Sent to {send_emails(emails)} administrator(s).")
    print("Duplicates are merged in Identity Management (a second person approves).")


def _reports(viewer):
    print("  1. Success rates  2. Error analysis  3. Performance trends  4. Comprehensive  "
          "5. Enrolment statistics  6. System status")
    pick = input("Report: ").strip()
    if pick == "6":
        report = _safe(batch_reports.system_status, viewer)
        if report:
            print(batch_reports.as_text({**report, "title": "System status"}))
        return
    key = REPORTS.get(pick)
    if not key:
        return
    days = input("Last how many days (blank = all): ").strip()
    report = _safe(_db, batch_schedule.build_report, viewer, key) if not days.isdigit() else \
        _safe(_db, {"success": batch_reports.success_rates, "errors": batch_reports.error_analysis,
                    "performance": batch_reports.performance,
                    "comprehensive": batch_reports.comprehensive,
                    "statistics": lambda c, v, _d: batch_reports.enrolment_statistics(c, v)}[key],
              viewer, int(days))
    if report:
        print(batch_reports.as_text(report))
        _offer_save(report)


def _schedule(viewer):
    for t in _db(batch_schedule.scheduled_tasks, viewer):
        print(f"  {t['type']:<15} #{t['id']:<3} {t['what'][:60]:<60} {t['when']:<16} "
              f"next {t['next']}")
    choice = input("a add a report, p pause/resume a report, r remove a report, n run anything "
                   "due now, blank = back: ").strip().lower()
    if choice == "a":
        print("  1. Success rates  2. Error analysis  3. Performance  4. Comprehensive  "
              "5. Enrolment statistics")
        key = REPORTS.get(input("Report: ").strip())
        frequency = input("daily / weekly / monthly: ").strip().lower()
        if key:
            _safe(_db, batch_schedule.add_report_schedule, viewer, key, frequency,
                  input("E-mail to (comma-separated): ").strip(), write=True)
    elif choice in ("p", "r"):
        sid = input("Report number: ").strip()
        if not sid.isdigit():
            return
        if choice == "r":
            _safe(_db, batch_schedule.remove_report_schedule, viewer, int(sid), write=True)
        else:
            current = {s["id"]: s for s in _db(batch_schedule.report_schedules, viewer)}
            if int(sid) in current:
                _safe(_db, batch_schedule.set_report_active, viewer, int(sid),
                      not current[int(sid)]["active"], write=True)
    elif choice == "n":
        from education_system.systems.university.infrastructure.batch import scheduler
        report = scheduler.run_once()
        print(f"{len(report.get('watches') or [])} watched folder(s) run, "
              f"{report.get('reports') or 0} report e-mail(s) sent.")


def _campaign(auth, viewer):
    segments = list(batch_admin.SEGMENTS)
    for i, k in enumerate(segments, 1):
        print(f"  {i}. {batch_admin.SEGMENTS[k]}")
    pick = input("Send to: ").strip()
    if not pick.isdigit() or not 0 < int(pick) <= len(segments):
        return
    segment = segments[int(pick) - 1]
    course = input("Course: ").strip() if segment == "course" else None
    addresses = input("Addresses (comma-separated): ") if segment == "addresses" else None
    preview = _safe(_db, batch_admin.campaign_preview, segment, course, addresses)
    if not preview:
        return
    print(f"{preview['count']} recipient(s), e.g. {', '.join(preview['sample'][:5])}")
    subject = input("Subject: ").strip()
    body = input("Message: ").strip()
    if input("Send? (y/N): ").strip().lower() != "y":
        return
    user = getattr(auth, "current_user", None) or {}
    result = _safe(_db, batch_admin.campaign, user.get("username") or "", user.get("role") or "",
                   segment=segment, subject=subject, body=body, course=course,
                   addresses=addresses, write=True)
    if result:
        from education_system.systems.university.infrastructure.email import outbox_delivery
        outbox_delivery.kick()
        print(f"{result['recipients']} recipient(s): {result['queued']} queued, "
              f"{result['stored']} in-app only, {result['suppressed']} not sent.")


def _roles(auth, viewer):
    pm = getattr(auth, "permission_manager", None)
    if not (_admin(viewer) and pm):
        print("Only an administrator signed in to the university system can do this.")
        return
    print("Roles: " + ", ".join(r["role_name"] for r in pm.list_roles()))
    role = input("Role: ").strip()
    source = input("File of permission names (blank = type them): ").strip()
    names = (_safe(batch_admin.read_permission_list, source) if source else
             input("Permissions (comma-separated): ").replace(",", " ").split()) or []
    grant = input("g grant / r revoke: ").strip().lower() == "g"
    if names and input(f"{'Grant' if grant else 'Revoke'} {len(names)} permission(s) for "
                       f"{role}? (y/N): ").strip().lower() == "y":
        result = _safe(batch_admin.apply_role_permissions, pm, role, names, grant)
        if result:
            print(f"{len(result['changed'])} changed; unknown: {result['unknown'] or 'none'}; "
                  f"refused: {result['refused'] or 'none'}")


def _admin_tools(viewer):
    if not _admin(viewer):
        print("Only an administrator can do this.")
        return
    choice = input("1. back up the database now  2. application log  3. send students to "
                   "another database  4. send students to an endpoint: ").strip()
    if choice == "1":
        from education_system.systems.university.infrastructure.database import data_backup
        path = data_backup.create_backup(manual=True, operation_name="batch_operations")
        print(f"Backup saved to {path}" if path else "The backup did not complete; see the log.")
    elif choice == "2":
        found = _safe(batch_admin.log_lines, viewer,
                      input("Level (ERROR / WARNING / blank = all): ").strip() or None,
                      input("Containing (blank = anything): ").strip() or None, 200)
        if found:
            print(f"{found['path'] or 'No log file found'}")
            print("\n".join(found["lines"]))
    elif choice in ("3", "4"):
        group = _group()
        modules = input("Include modules? (y/N): ").strip().lower() == "y"
        if input("Only where a data sharing agreement allows it. Continue? (y/N): ").strip() \
                .lower() != "y":
            return
        if choice == "3":
            kind = input("sqlite / postgresql / mysql: ").strip().lower() or "sqlite"
            config = {"type": kind}
            if kind == "sqlite":
                config["path"] = input("SQLite file: ").strip()
            else:
                import getpass
                config.update(host=input("Host: ").strip(), port=input("Port: ").strip(),
                              database=input("Database: ").strip(), user=input("User: ").strip(),
                              password=getpass.getpass("Password: "))
            table = input("Table (blank = students_export): ").strip() or "students_export"
            n = _safe(_db, batch_exports.export_to_database, viewer, config, table=table,
                      group=group, include_modules=modules, write=True)
            if n is not None:
                print(f"{n} row(s) written to {table}.")
        else:
            import getpass
            url = input("HTTPS address: ").strip()
            token = getpass.getpass("Bearer token (blank = none): ") or None
            result = _safe(_db, batch_exports.push_to_endpoint, viewer, url, token=token,
                           group=group, include_modules=modules, write=True)
            if result:
                print(f"{result['sent']} student(s) sent (HTTP {result['status']}).")


def _guide():
    print(batch_admin.GUIDE)


def menu_items(auth, viewer, start=6) -> dict:
    items = [("Export students (CSV / Excel / JSON)", lambda: _export(viewer)),
             ("Enrolment statistics", lambda: _statistics(viewer)),
             ("Resume an interrupted import", lambda: _resume(auth, viewer)),
             ("Export the job history", lambda: _history(viewer)),
             ("Data quality: check and fix student records", lambda: _quality(viewer)),
             ("Reports and system status", lambda: _reports(viewer)),
             ("Schedule: watched folders and e-mailed reports", lambda: _schedule(viewer)),
             ("E-mail campaign", lambda: _campaign(auth, viewer)),
             ("Role permissions in bulk (administrators)", lambda: _roles(auth, viewer)),
             ("Backup, log and sending to other systems (administrators)",
              lambda: _admin_tools(viewer)),
             ("User guide", _guide)]
    return {str(i): item for i, item in enumerate(items, start)}
