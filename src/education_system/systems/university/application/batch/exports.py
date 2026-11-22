"""Exports and student selection for Batch Operations.

* :func:`export_students` — the students in a group (a preset, a saved
  search, a course, a registration date range), as CSV, Excel (.xlsx,
  needs openpyxl) or JSON, optionally with the modules each is enrolled on.
  Built on ``student_search``: only the columns the person may see, never
  erased records, and every export is recorded in the search audit.
* :func:`select_students` — the student IDs a bulk action applies to: a
  pasted or file list, everyone on a course, a preset group or a saved
  search (permission-scoped the same way).
* :func:`export_to_database` / :func:`push_to_endpoint` — administrators
  can send the same export to another database (SQLite, or PostgreSQL /
  MySQL when their driver is installed; written by
  ``infrastructure/batch/external_export``) or POST it as JSON to an HTTPS
  endpoint (an external system's import API). Both are audited; the
  connection details are never stored.
"""

from __future__ import annotations

import csv
import json
import re
from datetime import date

from education_system.systems.university.application.students import search
from education_system.systems.university.application.students import search_saved as saved

FORMATS = ("csv", "xlsx", "json")
_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,62}$")
ADMIN_ROLES = search.ADMIN_ROLES


def _date(value, label):
    if not value:
        return None
    try:
        return date.fromisoformat(str(value).strip()).isoformat()
    except ValueError:
        raise ValueError(f"{label} must be a date (YYYY-MM-DD)") from None


def criteria_for(conn, viewer, *, group=None, saved_id=None, course=None, date_from=None,
                 date_to=None) -> dict:
    """Search criteria for the export / selection options."""
    if saved_id:
        criteria = json.loads(json.dumps(saved.get(conn, viewer, int(saved_id))["criteria"]))
    elif group and group != "All students":
        if group not in saved.PRESETS:
            raise ValueError(f"Unknown group {group!r}")
        criteria = json.loads(json.dumps(saved.PRESETS[group]))
    else:
        criteria = {"match": "all", "conditions": []}
    start, end = _date(date_from, "From"), _date(date_to, "To")
    if criteria.get("match") == "any" and (course or start or end):
        # "Any of" groups cannot take extra "and" conditions; filter afterwards.
        criteria["_then"] = {"course": course, "from": start, "to": end}
        return criteria
    conditions = criteria.setdefault("conditions", [])
    if course:
        conditions.append({"field": "course", "op": "is", "value": str(course).strip()})
    if start and end:
        conditions.append({"field": "registration", "op": "between", "value": f"{start}, {end}"})
    elif start:
        conditions.append({"field": "registration", "op": "after", "value": start})
    elif end:
        conditions.append({"field": "registration", "op": "before", "value": end})
    return criteria


def _rows(conn, viewer, criteria, fields=None):
    if not viewer.can_export:
        raise ValueError("You do not have permission to export student data")
    allowed = [f.key for f in search.columns_for(viewer)]
    chosen = [k for k in (fields or allowed) if k in allowed] or allowed
    return chosen, [{k: r.get(k) for k in chosen} for r in _matches(conn, criteria, viewer)]


def _plain(criteria) -> dict:
    return {k: v for k, v in criteria.items() if k != "_then"}


def _matches(conn, criteria, viewer) -> list[dict]:
    then = criteria.get("_then")
    rows = search.search(conn, _plain(criteria), viewer, page=0, page_size=search.MAX_EXPORT,
                         audit=False)["rows"]
    if then:
        course = (then.get("course") or "").lower()
        rows = [r for r in rows
                if (not course or str(r.get("course") or "").lower() == course)
                and (not then.get("from") or str(r.get("registration") or "") > then["from"])
                and (not then.get("to") or str(r.get("registration") or "")[:10] < then["to"])]
    return rows


def _with_modules(conn, rows):
    ids = [r["student_id"] for r in rows if r.get("student_id")]
    modules: dict[str, list[str]] = {}
    for i in range(0, len(ids), 500):
        chunk = ids[i:i + 500]
        marks = ",".join("?" * len(chunk))
        for sid, code in conn.execute(
                f"SELECT student_id, module_code FROM student_modules WHERE student_id IN "  # nosec B608
                f"({marks}) AND LOWER(COALESCE(status, 'enrolled')) IN ('enrolled', 'active', "
                "'registered') ORDER BY module_code", chunk):
            modules.setdefault(sid, []).append(code)
    for r in rows:
        r["modules"] = "; ".join(modules.get(r.get("student_id"), []))


def export_students(conn, viewer, path, *, fmt="csv", group=None, saved_id=None, course=None,
                    date_from=None, date_to=None, include_modules=False, fields=None) -> int:
    """Write the students to ``path``. Returns how many."""
    if fmt not in FORMATS:
        raise ValueError(f"Format must be one of {', '.join(FORMATS)}")
    criteria = criteria_for(conn, viewer, group=group, saved_id=saved_id, course=course,
                            date_from=date_from, date_to=date_to)
    chosen, rows = _rows(conn, viewer, criteria, fields)
    labels = {k: search.FIELDS[k].label for k in chosen}
    if include_modules:
        _with_modules(conn, rows)
        chosen = chosen + ["modules"]
        labels["modules"] = "Modules enrolled"
    if fmt == "json":
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(rows, handle, indent=2, default=str)
    elif fmt == "xlsx":
        try:
            from openpyxl import Workbook
        except ImportError:
            raise ValueError("Excel export needs openpyxl; choose CSV instead") from None
        book = Workbook()
        sheet = book.active
        sheet.title = "Students"
        sheet.append([labels[k] for k in chosen])
        for r in rows:
            sheet.append(["" if r.get(k) is None else r.get(k) for k in chosen])
        book.save(path)
    else:
        with open(path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=chosen)
            writer.writerow(labels)
            writer.writerows(rows)
    search.record(conn, viewer.username, "export", _plain(criteria), len(rows),
                  f"{fmt} to {path}; fields: {', '.join(chosen)}")
    return len(rows)


def select_students(conn, viewer, how, value=None) -> list[str]:
    """``how``: ``list`` (``value`` = IDs, text or iterable), ``course``,
    ``group`` (a preset name) or ``saved`` (a saved search id)."""
    if how == "list":
        text = value if isinstance(value, str) else "\n".join(map(str, value or []))
        return list(dict.fromkeys(t for t in re.split(r"[\s,;]+", text) if t))
    if how == "course":
        if not value:
            raise ValueError("Choose the course")
        criteria = criteria_for(conn, viewer, course=value)
    elif how == "group":
        criteria = criteria_for(conn, viewer, group=value)
    elif how == "saved":
        criteria = criteria_for(conn, viewer, saved_id=value)
    else:
        raise ValueError(f"Unknown way to choose students: {how!r}")
    return [r["student_id"] for r in _matches(conn, criteria, viewer) if r.get("student_id")]


# ── to another system (administrators) ──────────────────────────────────


def _admin(viewer):
    if viewer.role not in ADMIN_ROLES:
        raise ValueError("Only an administrator can send student data to another system")


def export_to_database(conn, viewer, config, *, table="students_export", replace=False,
                       group=None, saved_id=None, course=None, include_modules=False,
                       fields=None) -> int:
    """Copy the export into ``table`` of another database (created if
    missing; emptied first with ``replace``). Returns rows written."""
    _admin(viewer)
    if not _IDENT.match(table or ""):
        raise ValueError("The table name may use letters, digits and _ only")
    criteria = criteria_for(conn, viewer, group=group, saved_id=saved_id, course=course)
    chosen, rows = _rows(conn, viewer, criteria, fields)
    if include_modules:
        _with_modules(conn, rows)
        chosen = chosen + ["modules"]
    from education_system.systems.university.infrastructure.batch import external_export
    external_export.write_rows(config, table, chosen, rows, replace=replace)
    where = config.get("path") or f"{config.get('type')}://{config.get('host')}/{config.get('database')}"
    search.record(conn, viewer.username, "export", _plain(criteria), len(rows),
                  f"external database {where} table {table}; fields: {', '.join(chosen)}")
    return len(rows)


def push_to_endpoint(conn, viewer, url, *, token=None, group=None, saved_id=None, course=None,
                     include_modules=False, fields=None, timeout=30) -> dict:
    """POST the export as JSON ``{"students": [...]}`` to an HTTPS endpoint.
    Returns ``{"sent", "status"}``."""
    import urllib.error
    import urllib.request
    _admin(viewer)
    if not str(url or "").lower().startswith("https://"):
        raise ValueError("Use an https:// address; student data is never sent unencrypted")
    criteria = criteria_for(conn, viewer, group=group, saved_id=saved_id, course=course)
    chosen, rows = _rows(conn, viewer, criteria, fields)
    if include_modules:
        _with_modules(conn, rows)
    body = json.dumps({"students": rows}, default=str).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # nosec B310 - https only
            status = response.status
    except urllib.error.HTTPError as exc:
        raise ValueError(f"The endpoint refused the data (HTTP {exc.code})") from None
    except (urllib.error.URLError, TimeoutError) as exc:
        raise ValueError(f"The endpoint could not be reached: {exc}") from None
    search.record(conn, viewer.username, "export", _plain(criteria), len(rows),
                  f"POST to {url} (HTTP {status}); fields: {', '.join(chosen)}")
    return {"sent": len(rows), "status": status}
