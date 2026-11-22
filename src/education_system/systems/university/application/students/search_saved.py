"""Saved student searches (per user, optionally shared), ready-made
searches, report summaries and scheduled reports.

* A saved search belongs to its owner; others see it only when shared, and
  only the owner (or an admin) can change, share or delete it.
* A scheduled report re-runs a saved search daily, weekly or monthly with
  the owner's permissions, writes the matches to a CSV in ``out_dir`` and
  emails the recipients a summary (not the personal data). There is no
  scheduler: :func:`run_due` runs whatever is due when staff open Advanced
  Search or its CLI menu.

Functions take an open connection and do not commit; returned ``emails``
are ``(address, subject, body)`` for the caller to send after committing.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path

from education_system.systems.university.application.students import search
from education_system.systems.university.application.students.search import Viewer

FREQUENCIES = {"daily": 1, "weekly": 7, "monthly": 30}
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

#: Ready-made searches offered in the window and CLI.
PRESETS = {
    "Current students": {"match": "all", "conditions": [
        {"field": "status", "op": "is one of",
         "value": "Active, Registration Pending, Interrupted, Suspended, Deferred"}]},
    "At risk: average mark under 40": {"match": "all", "conditions": [
        {"field": "status", "op": "is", "value": "Active"},
        {"field": "average_mark", "op": "<", "value": "40"}]},
    "At risk: attendance under 70%": {"match": "all", "conditions": [
        {"field": "status", "op": "is", "value": "Active"},
        {"field": "attendance", "op": "<", "value": "70"}]},
    "Withdrawn": {"match": "all", "conditions": [
        {"field": "status", "op": "is", "value": "Withdrawn"}]},
    "Interrupted or suspended": {"match": "all", "conditions": [
        {"field": "status", "op": "is one of", "value": "Interrupted, Suspended"}]},
}


def _dicts(cur):
    names = [d[0] for d in cur.description]
    return [dict(zip(names, tuple(r))) for r in cur.fetchall()]


def _admin(viewer: Viewer) -> bool:
    return viewer.role in search.ADMIN_ROLES


# ── saved searches ──────────────────────────────────────────────────────


def save(conn, viewer: Viewer, name, criteria: dict, shared=False) -> int:
    """Save (or overwrite the viewer's own search of that name)."""
    search.ensure(conn)
    name = (name or "").strip()
    if not name:
        raise ValueError("Give the search a name")
    search.validate(criteria, viewer)        # refuse criteria that would not run
    conn.execute("INSERT INTO student_saved_searches (owner, name, criteria_json, shared) "
                 "VALUES (?, ?, ?, ?) ON CONFLICT (owner, name) DO UPDATE SET "
                 "criteria_json = excluded.criteria_json, shared = excluded.shared, "
                 "updated_at = datetime('now')",
                 (viewer.username, name, json.dumps(criteria), int(bool(shared))))
    return conn.execute("SELECT id FROM student_saved_searches WHERE owner = ? AND name = ?",
                        (viewer.username, name)).fetchone()[0]


def saved(conn, viewer: Viewer) -> list[dict]:
    """The viewer's own searches and those others have shared."""
    search.ensure(conn)
    rows = _dicts(conn.execute(
        "SELECT * FROM student_saved_searches WHERE owner = ? OR shared = 1 "
        "ORDER BY owner = ? DESC, name", (viewer.username, viewer.username)))
    for r in rows:
        r["criteria"] = json.loads(r.pop("criteria_json"))
        r["mine"] = r["owner"] == viewer.username
        r["summary"] = search.describe(r["criteria"])
    return rows


def get(conn, viewer: Viewer, saved_id) -> dict:
    row = next((r for r in saved(conn, viewer) if r["id"] == int(saved_id)), None)
    if not row:
        raise ValueError("No such saved search (or it is not shared with you)")
    return row


def _owned(conn, viewer, saved_id):
    row = conn.execute("SELECT owner FROM student_saved_searches WHERE id = ?",
                       (saved_id,)).fetchone()
    if not row:
        raise ValueError("No such saved search")
    if row[0] != viewer.username and not _admin(viewer):
        raise ValueError("Only its owner (or an admin) can change this search")


def set_shared(conn, viewer: Viewer, saved_id, shared: bool):
    search.ensure(conn)
    _owned(conn, viewer, saved_id)
    conn.execute("UPDATE student_saved_searches SET shared = ?, updated_at = datetime('now') "
                 "WHERE id = ?", (int(bool(shared)), saved_id))


def delete(conn, viewer: Viewer, saved_id):
    search.ensure(conn)
    _owned(conn, viewer, saved_id)
    conn.execute("DELETE FROM student_report_schedules WHERE saved_search_id = ?", (saved_id,))
    conn.execute("DELETE FROM student_saved_searches WHERE id = ?", (saved_id,))


# ── report summary ──────────────────────────────────────────────────────


def summary(conn, criteria, viewer: Viewer) -> dict:
    """Counts for the matches: by course and status, mean mark, how many are
    at risk (average under 40 or attendance under 70%)."""
    result = search.search(conn, criteria, viewer, page_size=search.MAX_EXPORT, audit=False)
    rows = result["rows"]
    marks = [r["average_mark"] for r in rows if r.get("average_mark") is not None]
    at_risk = [r for r in rows if (r.get("average_mark") is not None and r["average_mark"] < 40)
               or (r.get("attendance") is not None and r["attendance"] < 70)]
    return {"total": result["total"],
            "by_course": dict(Counter(r.get("course") or "—" for r in rows).most_common()),
            "by_status": dict(Counter(r.get("status") or "—" for r in rows).most_common()),
            "average_mark": round(sum(marks) / len(marks), 1) if marks else None,
            "with_marks": len(marks), "at_risk": len(at_risk)}


def summary_text(title, criteria, result) -> str:
    lines = [title, f"Search: {search.describe(criteria)}", f"Students: {result['total']}"]
    if result["average_mark"] is not None:
        lines.append(f"Average mark: {result['average_mark']} ({result['with_marks']} with marks)")
    lines.append(f"At risk (mark under 40 or attendance under 70%): {result['at_risk']}")
    lines += ["", "By course:"] + [f"  {k}: {v}" for k, v in result["by_course"].items()]
    lines += ["", "By status:"] + [f"  {k}: {v}" for k, v in result["by_status"].items()]
    return "\n".join(lines)


# ── charts ──────────────────────────────────────────────────────────────

#: Fields a search's matches can be charted by, and how. Identifying fields
#: (name, emails, phone, address, date of birth) are never charted.
CHARTS = {
    "course": "bar", "status": "pie", "mode_of_study": "pie", "fee_status": "pie",
    "entry_route": "bar", "gender": "pie", "nationality": "bar", "year_of_study": "bar",
    "registration": "line", "average_mark": "histogram", "attendance": "histogram",
    "age": "histogram",
}
_BINS = {"average_mark": 10, "attendance": 10, "age": 5}
TOP_CATEGORIES = 15


def chart_fields(viewer: Viewer) -> list[tuple[str, str]]:
    """``(key, label)`` of the fields this viewer may chart."""
    allowed = {f.key for f in search.fields_for(viewer)}
    return [(k, search.FIELDS[k].label) for k in CHARTS if k in allowed]


def _bucket(key, value):
    if value is None or value == "":
        return None
    if CHARTS[key] == "histogram":
        width = _BINS[key]
        number = float(value)
        if key in ("average_mark", "attendance") and number >= 100:
            return "100"                       # a percentage tops out at 100
        low = int(number // width * width)
        return f"{low}–{low + width - 1}"
    if key == "registration":
        return str(value)[:7] or None          # YYYY-MM
    return str(value)


def _order(key, counts):
    if CHARTS[key] in ("histogram", "line") or key == "year_of_study":
        def sort_key(label):
            head = label.split("–")[0]
            try:
                return (0, float(head))
            except ValueError:
                return (1, head)
        return sorted(counts.items(), key=lambda kv: sort_key(kv[0]))
    ordered = counts.most_common()
    if len(ordered) > TOP_CATEGORIES:
        rest = sum(v for _k, v in ordered[TOP_CATEGORIES - 1:])
        ordered = ordered[:TOP_CATEGORIES - 1] + [("Other", rest)]
    return ordered


def chart_data(conn, criteria, viewer: Viewer, key) -> dict:
    """The matches of ``criteria`` counted by ``key``, for a chart:
    ``{"field", "label", "chart", "labels", "values", "total", "missing"}``.
    Only students the viewer may see are counted (the search's own rules)."""
    search.ensure(conn)
    if key not in dict(chart_fields(viewer)):
        raise ValueError("You cannot chart the results by that field")
    f = search.FIELDS[key]
    if search._fuzzy(criteria):
        if not f.column:
            raise ValueError(f"Charts by {f.label.lower()} are not available for "
                             "'sounds like' searches")
        rows = search.search(conn, criteria, viewer, page_size=search.MAX_EXPORT,
                             audit=False)["rows"]
        values = [r.get(key) for r in rows]
    else:
        where, args = search._where(criteria, viewer)
        values = [r[0] for r in conn.execute(
            f"SELECT {f.expr} FROM students s WHERE {where} LIMIT {search.MAX_EXPORT}",  # nosec B608
            args)]
    buckets = [_bucket(key, v) for v in values]
    counts = Counter(b for b in buckets if b is not None)
    ordered = _order(key, counts)
    search.record(conn, viewer.username, "report", criteria, len(values),
                  detail=f"chart by {key}")
    return {"field": key, "label": f.label, "chart": CHARTS[key],
            "labels": [k for k, _v in ordered], "values": [v for _k, v in ordered],
            "total": len(values), "missing": sum(1 for b in buckets if b is None)}


def chart_text(data, width=40) -> str:
    """The chart as text bars, for the CLI and the fallback window."""
    lines = [f"{data['label']} — {data['total']} student(s)"
             + (f", {data['missing']} with no value" if data["missing"] else "")]
    peak = max(data["values"] or [1])
    label_width = min(28, max((len(str(lbl)) for lbl in data["labels"]), default=4))
    for label, value in zip(data["labels"], data["values"]):
        bar = "█" * max(1 if value else 0, round(value / peak * width))
        lines.append(f"  {str(label)[:label_width]:<{label_width}} {bar} {value}")
    return "\n".join(lines)


# ── scheduled reports ───────────────────────────────────────────────────


def _recipients(text) -> list[str]:
    emails = [e.strip() for e in re.split(r"[,;\s]+", text or "") if e.strip()]
    bad = [e for e in emails if not _EMAIL.match(e)]
    if not emails or bad:
        raise ValueError("Give at least one valid email address" +
                         (f" (not: {', '.join(bad)})" if bad else ""))
    return emails


def schedule(conn, viewer: Viewer, saved_id, frequency, recipients, name=None,
             fields=None, start=None) -> int:
    search.ensure(conn)
    if not viewer.can_export:
        raise ValueError("Scheduled reports need permission to export student data")
    if frequency not in FREQUENCIES:
        raise ValueError(f"Frequency must be one of {', '.join(FREQUENCIES)}")
    target = get(conn, viewer, saved_id)
    emails = _recipients(recipients)
    return int(conn.execute(
        "INSERT INTO student_report_schedules (owner, name, saved_search_id, frequency, "
        "recipients, fields_json, next_run_on) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (viewer.username, (name or target["name"]).strip(), target["id"], frequency,
         ", ".join(emails), json.dumps(fields) if fields else None,
         (start or date.today()).isoformat())).lastrowid)


def schedules(conn, viewer: Viewer) -> list[dict]:
    search.ensure(conn)
    sql = ("SELECT r.*, s.name AS search_name FROM student_report_schedules r JOIN "
           "student_saved_searches s ON s.id = r.saved_search_id")
    if not _admin(viewer):
        return _dicts(conn.execute(sql + " WHERE r.owner = ? ORDER BY r.id", (viewer.username,)))
    return _dicts(conn.execute(sql + " ORDER BY r.id"))


def _own_schedule(conn, viewer, schedule_id):
    row = conn.execute("SELECT owner FROM student_report_schedules WHERE id = ?",
                       (schedule_id,)).fetchone()
    if not row:
        raise ValueError("No such scheduled report")
    if row[0] != viewer.username and not _admin(viewer):
        raise ValueError("Only its owner (or an admin) can change this report")


def set_active(conn, viewer: Viewer, schedule_id, active: bool):
    search.ensure(conn)
    _own_schedule(conn, viewer, schedule_id)
    conn.execute("UPDATE student_report_schedules SET active = ? WHERE id = ?",
                 (int(bool(active)), schedule_id))


def remove_schedule(conn, viewer: Viewer, schedule_id):
    search.ensure(conn)
    _own_schedule(conn, viewer, schedule_id)
    conn.execute("DELETE FROM student_report_schedules WHERE id = ?", (schedule_id,))


def owner_viewer(conn, username) -> Viewer:
    """The permissions a scheduled report runs with: its owner's role."""
    row = conn.execute("SELECT role FROM users WHERE username = ?", (username,)).fetchone()
    role = str(row[0] if row else "").lower()
    admin = role in search.ADMIN_ROLES
    staff = admin or role in ("staff", "instructor", "lecturer", "faculty", "teacher")
    return Viewer(username=username, role=role, can_view_all=staff, can_view_sensitive=admin,
                  can_export=staff)


def run_report(conn, schedule_row, out_dir, today=None) -> dict:
    """Run one scheduled report now. Returns ``{"file", "emails"}``."""
    today = today or date.today()
    viewer = owner_viewer(conn, schedule_row["owner"])
    target = conn.execute("SELECT criteria_json FROM student_saved_searches WHERE id = ?",
                          (schedule_row["saved_search_id"],)).fetchone()
    criteria = json.loads(target[0])
    folder = Path(out_dir)
    folder.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", schedule_row["name"]).strip("_") or "report"
    path = folder / f"{safe}_{today.isoformat()}.csv"
    fields = json.loads(schedule_row["fields_json"]) if schedule_row.get("fields_json") else None
    count = search.export(conn, criteria, viewer, str(path), fields=fields)
    text = summary_text(f"Scheduled report: {schedule_row['name']}", criteria,
                        summary(conn, criteria, viewer))
    body = (f"{text}\n\nThe list of {count} students is saved at {path} "
            "(not attached, as it holds personal data).")
    search.record(conn, schedule_row["owner"], "report", criteria, count,
                  f"scheduled report #{schedule_row['id']}")
    emails = [(e, f"Report: {schedule_row['name']} ({today.isoformat()})", body)
              for e in _recipients(schedule_row["recipients"])]
    return {"file": str(path), "count": count, "emails": emails}


def run_due(conn, out_dir, now=None) -> dict:
    """Run every active schedule whose next run date has arrived."""
    search.ensure(conn)
    today = (now or datetime.now()).date()
    ran, emails, failures = 0, [], []
    for row in _dicts(conn.execute("SELECT * FROM student_report_schedules WHERE active = 1 AND "
                                   "next_run_on <= ? ORDER BY id", (today.isoformat(),))):
        try:
            result = run_report(conn, row, out_dir, today)
            emails += result["emails"]
            outcome = f"{result['count']} students -> {result['file']}"
            ran += 1
        except Exception as exc:
            outcome = f"failed: {exc}"
            failures.append(f"#{row['id']} {row['name']}: {exc}")
        nxt = today + timedelta(days=FREQUENCIES[row["frequency"]])
        conn.execute("UPDATE student_report_schedules SET last_run_at = datetime('now'), "
                     "last_result = ?, next_run_on = ? WHERE id = ?",
                     (outcome, nxt.isoformat(), row["id"]))
    return {"ran": ran, "failures": failures, "emails": emails}
