"""The administrative side of Batch Operations.

* **Data quality** — :func:`quality_dashboard` summarises
  ``student_data_quality.issues`` (by kind, how many can be fixed safely,
  share of records affected); :func:`apply_quality_fixes` applies the safe
  fixes chosen (each written to the change history);
  :func:`quality_report_emails` sends the findings to the administrators.
  Duplicates are merged in Identity Management (two-person approval), never
  here.
* **E-mail campaigns** — :func:`campaign` sends one message to a segment
  (all students, all staff, everyone, the students on a course, or a list)
  through the e-mail outbox (``email_admin.send_bulk``: permission checked,
  unsubscribes respected, audited); :func:`campaign_preview` counts and
  lists the recipients first.
* **Role permissions in bulk** — :func:`apply_role_permissions` grants or
  revokes a list of permissions for a role through the signed-in
  ``PermissionManager`` (needs ``manage_roles``; each change is logged).
  Per-user permission rows are not offered: the university's permission
  check reads the role only, so they would have no effect.
* :func:`log_lines` — recent lines of the application log, optionally by
  level (administrators).
"""

from __future__ import annotations

import re

from education_system.systems.university.application.students import data_quality as quality

ADMIN_ROLES = ("admin", "administrator", "superadmin")
#: What each part of Batch Operations does (shown by the window and the CLI).
GUIDE = """Batch Operations

Import — students (new, update, or both), marks, staff accounts or module enrolments
from CSV, Excel (choose the sheet) or JSON. Preview first: it checks every row and
changes nothing. Import records a job. Several files can be imported at once, each as
its own job. Columns are matched automatically or with a saved mapping.

Bulk actions — set a field, transfer, enrol on / withdraw from a module, withdraw,
reinstate or e-mail. Choose students by list or file, everyone on a course, a group or a
saved search (Advanced Search). The reason is recorded on each student.

Export — CSV, Excel or JSON, filtered by group, saved search, course and registration
date, optionally with each student's modules. Enrolment statistics are counts only.
Administrators can send an export to another database or an HTTPS endpoint.

Jobs — every import and bulk run. Details, failed rows, undo (students, marks, staff,
module enrolments), resume an import that stopped part-way, export the history.

Watched folders — files dropped in a folder are imported when Batch Operations opens, on
Run now, or daily at a set time (background scheduler).

Data quality — checks on student records; safe fixes can be applied (each is written to
the change history); duplicates are merged in Identity Management with a second person's
approval. The findings can be e-mailed to the administrators.

Reports — success rates, error analysis, performance trends, a comprehensive report
with measured system figures, and enrolment statistics; saved as text, JSON or CSV, or
e-mailed on a schedule (Schedule tab).

Users & e-mail — e-mail a segment through the outbox (unsubscribes respected), and grant
or revoke permissions for a role in bulk (administrators). Staff accounts are imported on
the Import tab.

Utilities — database backup and the application log (administrators), templates for
every kind of import, and this guide.
"""
SEGMENTS = {"students": "All students", "staff": "All staff",
            "all_users": "Everyone with a university login", "course": "Students on a course",
            "addresses": "A list of addresses"}
_LEVEL = re.compile(r"\b(DEBUG|INFO|WARNING|ERROR|CRITICAL)\b")


# ── data quality ────────────────────────────────────────────────────────


def _require_quality(viewer):
    if not viewer.can_update:
        raise ValueError("You do not have permission to check and fix student records")


def quality_dashboard(conn, viewer) -> dict:
    _require_quality(viewer)
    issues = quality.issues(conn)
    total = conn.execute("SELECT COUNT(*) FROM students WHERE student_id NOT LIKE "
                         "'ERASED-%'").fetchone()[0]
    by_kind: dict[str, dict] = {}
    for i in issues:
        k = by_kind.setdefault(i["kind"], {"kind": i["kind"], "issues": 0, "fixable": 0})
        k["issues"] += 1
        k["fixable"] += 1 if i["fix"] else 0
    affected = len({i["student_id"] for i in issues})
    return {"students": total, "issues": len(issues), "fixable": sum(1 for i in issues if i["fix"]),
            "students_affected": affected,
            "clean_percent": round((total - affected) / total * 100, 1) if total else None,
            "by_kind": sorted(by_kind.values(), key=lambda k: -k["issues"]), "list": issues}


def apply_quality_fixes(conn, viewer, keys) -> int:
    _require_quality(viewer)
    if not keys:
        raise ValueError("Choose the issues to fix")
    return quality.apply_fixes(conn, keys, viewer.username)


def quality_report_text(dashboard) -> str:
    lines = ["Student record data check", "=========================",
             f"{dashboard['students']} records, {dashboard['issues']} issue(s) on "
             f"{dashboard['students_affected']} record(s); {dashboard['fixable']} can be fixed "
             "safely in Batch Operations (Data quality).", ""]
    for k in dashboard["by_kind"]:
        lines.append(f"  {k['kind']}: {k['issues']} ({k['fixable']} fixable)")
    lines.append("")
    for i in dashboard["list"][:200]:
        lines.append(f"  {i['student_id']} {i['name']}: {i['detail']}")
    if len(dashboard["list"]) > 200:
        lines.append(f"  … and {len(dashboard['list']) - 200} more")
    return "\n".join(lines)


def admin_emails(conn) -> list[str]:
    marks = ",".join("?" * len(ADMIN_ROLES))
    return sorted({r[0] for r in conn.execute(
        f"SELECT email FROM users WHERE LOWER(role) IN ({marks}) AND "  # nosec B608
        "COALESCE(email, '') LIKE '%@%'", ADMIN_ROLES)})


def quality_report_emails(conn, viewer) -> list[tuple]:
    dashboard = quality_dashboard(conn, viewer)
    body = quality_report_text(dashboard)
    addresses = admin_emails(conn)
    if not addresses:
        raise ValueError("No administrator has an e-mail address")
    from education_system.systems.university.application.students import search as student_search
    student_search.record(conn, viewer.username, "report", None,
                          dashboard["issues"],
                          f"data check e-mailed to {len(addresses)} administrator(s)")
    return [(a, f"Student records data check: {dashboard['issues']} issue(s)", body)
            for a in addresses]


# ── e-mail campaigns ────────────────────────────────────────────────────


def _course_addresses(conn, course) -> list[str]:
    from education_system.systems.university.application.students import search as student_search
    expr = student_search.FIELDS["course"].expr
    return [r[0] for r in conn.execute(
        f"SELECT s.email_address FROM students s WHERE LOWER({expr}) = LOWER(?) AND "  # nosec B608
        "s.student_id NOT LIKE 'ERASED-%' AND COALESCE(s.email_address, '') LIKE '%@%' AND "
        "COALESCE(s.status, '') NOT IN ('Withdrawn', 'Closed')", (course,))]


def _audience(conn, segment, course=None, addresses=None):
    if segment not in SEGMENTS:
        raise ValueError(f"Segment must be one of {', '.join(SEGMENTS)}")
    if segment == "course":
        if not course:
            raise ValueError("Choose the course")
        found = _course_addresses(conn, course)
        if not found:
            raise ValueError(f"No student on {course} has an e-mail address")
        return "addresses", found
    if segment == "addresses":
        found = [a for a in re.split(r"[\s,;]+", str(addresses or "")) if a]
        return "addresses", found
    return segment, None


def campaign_preview(conn, segment, course=None, addresses=None, limit=20) -> dict:
    from education_system.systems.university.application.mail import admin as email_admin
    audience, found = _audience(conn, segment, course, addresses)
    recipients = email_admin.audience_recipients(conn, audience, found)
    return {"count": len(recipients), "sample": [a for a, _u in recipients[:limit]]}


def campaign(conn, actor, actor_role, *, segment, subject, body, course=None, addresses=None,
             category="announcements") -> dict:
    """Queue the message. Does not commit; the caller commits and then
    kicks the outbox."""
    from education_system.systems.university.application.mail import admin as email_admin
    from education_system.systems.university.infrastructure.email import outbox_delivery
    if not str(subject or "").strip():
        raise ValueError("Give the e-mail a subject")
    audience, found = _audience(conn, segment, course, addresses)
    return email_admin.send_bulk(conn, actor, actor_role, audience=audience, subject=subject,
                                 body=body, category=category,
                                 mode=outbox_delivery.delivery_mode(), addresses=found)


# ── role permissions ────────────────────────────────────────────────────


def apply_role_permissions(permission_manager, role, permissions, grant=True) -> dict:
    """Grant (or revoke) each permission for ``role``. Returns
    ``{"changed": [...], "unknown": [...], "refused": [...]}``."""
    if permission_manager is None:
        raise ValueError("Sign in as an administrator to change role permissions")
    known = {p.get("permission_name") or p.get("name")
             for p in (permission_manager.list_permissions() or [])}
    roles = {r.get("role_name") or r.get("name") for r in permission_manager.list_roles() or []}
    if role not in roles:
        raise ValueError(f"No role called {role!r}")
    wanted = list(dict.fromkeys(p.strip() for p in permissions if p and p.strip()))
    if not wanted:
        raise ValueError("List at least one permission")
    out = {"changed": [], "unknown": [], "refused": []}
    for name in wanted:
        if name not in known:
            out["unknown"].append(name)
            continue
        ok = (permission_manager.grant_role_permission(role, name) if grant
              else permission_manager.revoke_role_permission(role, name))
        out["changed" if ok else "refused"].append(name)
    return out


def read_permission_list(path) -> list[str]:
    """Permission names from a file: one per line, or a ``permission``
    column of a CSV/Excel sheet."""
    from pathlib import Path
    from education_system.systems.university.application.batch import files as batch_files
    if Path(path).suffix.lower() in (".csv", ".xlsx", ".xlsm", ".json"):
        headers, rows = batch_files.read_table(path)
        column = next((h for h in headers if h.strip().lower() in ("permission",
                                                                    "permission_name",
                                                                    "name")), None)
        if column:
            return [r[column] for r in rows if r.get(column)]
    return [line.strip() for line in Path(path).read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")]


# ── the application log ─────────────────────────────────────────────────


def log_lines(viewer, level=None, contains=None, limit=500) -> dict:
    """The last ``limit`` matching lines of the live application log."""
    from collections import deque
    from education_system.systems.university.infrastructure.monitoring import system_metrics
    if viewer.role not in ADMIN_ROLES:
        raise ValueError("Only an administrator can read the application log")
    path = system_metrics.resolve_log_path()
    if not path:
        return {"path": None, "lines": []}
    wanted = {"ERROR": ("ERROR", "CRITICAL"), "WARNING": ("WARNING", "ERROR", "CRITICAL")}.get(
        str(level or "").upper(), None)
    needle = str(contains or "").lower()
    keep: deque = deque(maxlen=int(limit))
    with open(path, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if wanted:
                m = _LEVEL.search(line)
                if not m or m.group(1) not in wanted:
                    continue
            if needle and needle not in line.lower():
                continue
            keep.append(line.rstrip("\n"))
    return {"path": str(path), "lines": list(keep)}
