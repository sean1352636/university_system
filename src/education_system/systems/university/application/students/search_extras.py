"""The working tools around a student search: favourite students, follow-ups,
your own search history, groups, email lists and moving saved searches
between people as files.

* **Favourites** are per member of staff (``student_search_favourites``).
* **Follow-ups** (``student_followups``) mark students for attention with a
  reason, priority, optional due date and assignee; closing one records who
  and the outcome. Marking needs ``can_view_all``; the assignee is e-mailed.
* **History** is your own entries in the search audit, newest first, each
  with its criteria so it can be run again.
* **Groups** split a result into groups (by course, status, year, age band,
  alphabetically or at random in groups of N) to view or export.
* **Email lists** give the matches' addresses in the chosen layout (personal
  addresses only for those who may see them).
* **Saved searches** export to / import from a JSON file.

Functions take an open connection and do not commit.
"""

from __future__ import annotations

import json
import random
import re
from collections import defaultdict
from datetime import date

from education_system.systems.university.application.students import search
from education_system.systems.university.application.students import search_saved as saved
from education_system.systems.university.application.students.search import Viewer

PRIORITIES = ("high", "medium", "low")
GROUP_METHODS = {"course": "By course", "status": "By status", "year_of_study": "By year",
                 "age_band": "By age band", "alphabetical": "Alphabetical, groups of N",
                 "random": "Random, groups of N"}
LIST_LAYOUTS = {"lines": "One per line", "comma": "Comma-separated",
                "semicolon": "Semicolon-separated (Outlook)"}
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _staff(viewer: Viewer):
    if not viewer.can_view_all:
        raise ValueError("This is for staff who can see every student")


def _student(conn, student_id) -> tuple:
    row = conn.execute(f"SELECT s.student_id, {search.FIELDS['name'].expr}, {search._COURSE}, "  # nosec B608
                       f"{search._STATUS}, s.email_address FROM students s WHERE "
                       "s.student_id = ? AND s.student_id NOT LIKE 'ERASED-%'",
                       (str(student_id),)).fetchone()
    if not row:
        raise ValueError(f"No student {student_id}")
    return row


def _dicts(cur) -> list[dict]:
    names = [d[0] for d in cur.description]
    return [dict(zip(names, tuple(r))) for r in cur.fetchall()]


# ── favourites ──────────────────────────────────────────────────────────


def add_favourite(conn, viewer: Viewer, student_id, note="") -> None:
    _staff(viewer)
    search.ensure(conn)
    _student(conn, student_id)
    conn.execute("INSERT INTO student_search_favourites (owner, student_id, note) VALUES "
                 "(?, ?, ?) ON CONFLICT(owner, student_id) DO UPDATE SET note = excluded.note",
                 (viewer.username, str(student_id), str(note or "").strip() or None))


def remove_favourite(conn, viewer: Viewer, student_id) -> None:
    search.ensure(conn)
    conn.execute("DELETE FROM student_search_favourites WHERE owner = ? AND student_id = ?",
                 (viewer.username, str(student_id)))


def favourites(conn, viewer: Viewer) -> list[dict]:
    search.ensure(conn)
    return _dicts(conn.execute(
        f"SELECT f.student_id, {search.FIELDS['name'].expr} AS name, {search._COURSE} AS course, "  # nosec B608
        f"{search._STATUS} AS status, f.note, f.added_at FROM student_search_favourites f JOIN "
        "students s ON s.student_id = f.student_id WHERE f.owner = ? AND s.student_id NOT LIKE "
        "'ERASED-%' ORDER BY f.added_at DESC", (viewer.username,)))


# ── follow-ups ──────────────────────────────────────────────────────────


def _user_email(conn, username):
    row = conn.execute("SELECT email FROM users WHERE username = ? COLLATE NOCASE",
                       (username,)).fetchone()
    return row[0] if row and row[0] and _EMAIL.match(row[0]) else None


def mark_followup(conn, viewer: Viewer, student_ids, reason, priority="medium", due_on=None,
                  assigned_to=None) -> dict:
    """Mark students for follow-up. Returns ``{"marked", "emails"}``."""
    _staff(viewer)
    search.ensure(conn)
    ids = list(dict.fromkeys(str(s) for s in student_ids if s))
    if not ids:
        raise ValueError("No students selected")
    if len(ids) > 500:
        raise ValueError("At most 500 students at a time")
    reason = str(reason or "").strip()
    if not reason:
        raise ValueError("Give the reason for the follow-up")
    if priority not in PRIORITIES:
        raise ValueError(f"Priority must be one of {', '.join(PRIORITIES)}")
    if due_on:
        try:
            due_on = date.fromisoformat(str(due_on).strip()).isoformat()
        except ValueError:
            raise ValueError("Give the due date as YYYY-MM-DD") from None
    assigned_to = str(assigned_to or "").strip() or None
    if assigned_to and not conn.execute("SELECT 1 FROM users WHERE username = ? COLLATE NOCASE",
                                        (assigned_to,)).fetchone():
        raise ValueError(f"No user {assigned_to}")
    for sid in ids:
        _student(conn, sid)
    conn.executemany("INSERT INTO student_followups (student_id, reason, priority, due_on, "
                     "assigned_to, created_by) VALUES (?, ?, ?, ?, ?, ?)",
                     [(sid, reason, priority, due_on, assigned_to, viewer.username)
                      for sid in ids])
    search.record(conn, viewer.username, "bulk", None, len(ids),
                  f"follow-up ({priority}): {reason}"
                  + (f"; assigned to {assigned_to}" if assigned_to else ""))
    emails = []
    address = _user_email(conn, assigned_to) if assigned_to else None
    if address and assigned_to.lower() != viewer.username.lower():
        emails.append((address, f"{len(ids)} student follow-up(s) assigned to you",
                       f"{viewer.username} asked you to follow up {len(ids)} student(s): "
                       f"{reason}. Priority {priority}"
                       + (f", due {due_on}" if due_on else "") + ". See Advanced Search, "
                       "Follow-ups."))
    return {"marked": len(ids), "emails": emails}


def followups(conn, viewer: Viewer, status="open", mine=False) -> list[dict]:
    _staff(viewer)
    search.ensure(conn)
    sql = (f"SELECT f.*, {search.FIELDS['name'].expr} AS name, {search._COURSE} AS course "  # nosec B608
           "FROM student_followups f LEFT JOIN students s ON s.student_id = f.student_id "
           "WHERE 1 = 1")
    args: list = []
    if status:
        sql += " AND f.status = ?"
        args.append(status)
    if mine:
        sql += " AND (f.assigned_to = ? OR (f.assigned_to IS NULL AND f.created_by = ?))"
        args += [viewer.username, viewer.username]
    sql += (" ORDER BY f.status, CASE f.priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 "
            "ELSE 2 END, COALESCE(f.due_on, '9999'), f.id")
    return _dicts(conn.execute(sql, args))


def close_followup(conn, viewer: Viewer, followup_id, outcome) -> None:
    _staff(viewer)
    search.ensure(conn)
    row = conn.execute("SELECT status FROM student_followups WHERE id = ?",
                       (followup_id,)).fetchone()
    if not row:
        raise ValueError(f"No follow-up {followup_id}")
    if row[0] == "done":
        raise ValueError("That follow-up is already closed")
    if not str(outcome or "").strip():
        raise ValueError("Say what was done")
    conn.execute("UPDATE student_followups SET status = 'done', closed_by = ?, closed_at = "
                 "datetime('now'), outcome = ? WHERE id = ?",
                 (viewer.username, outcome.strip(), followup_id))


# ── your search history ─────────────────────────────────────────────────


def history(conn, viewer: Viewer, limit=100) -> list[dict]:
    """Your own searches, exports, bulk actions and reports, newest first;
    ``criteria`` is the search that can be run again."""
    search.ensure(conn)
    rows = conn.execute("SELECT id, action, criteria_json, result_count, detail, at FROM "
                        "student_search_audit WHERE actor = ? ORDER BY id DESC LIMIT ?",
                        (viewer.username, int(limit))).fetchall()
    out = []
    for rid, action, crit, count, detail, at in rows:
        try:
            criteria = json.loads(crit) if crit else None
        except ValueError:
            criteria = None
        out.append({"id": rid, "action": action, "criteria": criteria,
                    "search": search.describe(criteria) if criteria else "", "count": count,
                    "detail": detail or "", "at": at})
    return out


def last_search(conn, viewer: Viewer) -> dict | None:
    for entry in history(conn, viewer, 50):
        if entry["action"] == "search" and entry["criteria"] is not None:
            return entry["criteria"]
    return None


# ── groups and email lists ──────────────────────────────────────────────


def _age_band(dob) -> str:
    try:
        born = date.fromisoformat(str(dob)[:10])
    except ValueError:
        return "Unknown"
    today = date.today()
    age = today.year - born.year - ((today.month, today.day) < (born.month, born.day))
    for limit, label in ((18, "Under 18"), (21, "18-20"), (25, "21-24"), (30, "25-29"),
                         (40, "30-39")):
        if age < limit:
            return label
    return "40+"


def _size(size) -> int:
    try:
        size = int(size)
    except (TypeError, ValueError):
        raise ValueError("Group size must be a whole number") from None
    if size < 1:
        raise ValueError("Group size must be at least 1")
    return size


def _split(conn, rows, method, size, seed) -> dict:
    groups: dict = defaultdict(list)
    if method in ("alphabetical", "random"):
        size = _size(size)
        if method == "random":
            ordered = rows[:]
            random.Random(seed).shuffle(ordered)
        else:
            ordered = sorted(rows, key=lambda r: (str(r.get("name") or "").split()[-1:] or [""],
                                                  r.get("name") or ""))
        for i, r in enumerate(ordered):
            groups[f"Group {i // size + 1}"].append(r)
    elif method == "age_band":
        dobs = dict(conn.execute(
            f"SELECT student_id, dob FROM students WHERE student_id IN "  # nosec B608
            f"({','.join('?' * len(rows))})", [r["student_id"] for r in rows]).fetchall())
        for r in rows:
            groups[_age_band(dobs.get(r["student_id"]))].append(r)
    else:
        for r in rows:
            groups[str(r.get(method) or "Not recorded")].append(r)
    return groups


def make_groups(conn, criteria, viewer: Viewer, method, size=5, ids=None, seed=None) -> dict:
    """Split the matches (or ``ids`` of them) into named groups of students."""
    _staff(viewer)
    if method not in GROUP_METHODS:
        raise ValueError(f"Choose one of {', '.join(GROUP_METHODS)}")
    rows = search.search(conn, criteria or {}, viewer, page_size=search.MAX_EXPORT,
                         audit=False)["rows"]
    if ids:
        wanted = {str(i) for i in ids}
        rows = [r for r in rows if str(r["student_id"]) in wanted]
    if not rows:
        raise ValueError("No students to group")
    groups = _split(conn, rows, method, size, seed)
    search.record(conn, viewer.username, "report", criteria, len(rows),
                  f"groups {method}" + (f" of {size}" if method in ("alphabetical", "random")
                                        else "") + f": {len(groups)} group(s)")
    return dict(sorted(groups.items()))


def groups_table(groups: dict) -> tuple[list, list]:
    """Groups as export columns and rows."""
    rows = [{"group": name, "student_id": r["student_id"], "name": r.get("name"),
             "course": r.get("course"), "status": r.get("status"),
             "email_address": r.get("email_address")} for name, members in groups.items()
            for r in members]
    return ["group", "student_id", "name", "course", "status", "email_address"], rows


def email_list(conn, criteria, viewer: Viewer, layout="lines", personal=False,
               ids=None) -> dict:
    """The matches' addresses: ``{"text", "count", "missing"}``."""
    _staff(viewer)
    if layout not in LIST_LAYOUTS:
        raise ValueError(f"Layout must be one of {', '.join(LIST_LAYOUTS)}")
    if personal and not viewer.can_view_sensitive:
        raise ValueError("Only an administrator can list personal email addresses")
    found = search.all_ids(conn, criteria or {}, viewer)
    if ids:
        wanted = {str(i) for i in ids}
        found = [i for i in found if i in wanted]
    column = "personal_email" if personal else "email_address"
    addresses, missing = [], []
    for start in range(0, len(found), 500):
        chunk = found[start:start + 500]
        rows = dict(conn.execute(f"SELECT student_id, {column} FROM students WHERE student_id "  # nosec B608
                                 f"IN ({','.join('?' * len(chunk))})", chunk).fetchall())
        for sid in chunk:
            value = str(rows.get(sid) or "").strip()
            (addresses if _EMAIL.match(value) else missing).append(value if value else sid)
    addresses = list(dict.fromkeys(addresses))
    joiner = {"lines": "\n", "comma": ", ", "semicolon": "; "}[layout]
    search.record(conn, viewer.username, "export", criteria, len(addresses),
                  f"email list ({'personal' if personal else 'university'}, {layout})")
    return {"text": joiner.join(addresses), "count": len(addresses), "missing": missing}


# ── saved searches as files ─────────────────────────────────────────────


def export_saved(conn, viewer: Viewer, saved_id, path) -> str:
    item = saved.get(conn, viewer, saved_id)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump({"name": item["name"], "criteria": item["criteria"],
                   "exported_by": viewer.username, "exported_on": date.today().isoformat()},
                  handle, indent=2)
    return path


def import_saved(conn, viewer: Viewer, path, shared=False) -> int:
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError) as exc:
        raise ValueError(f"That file is not a saved search: {exc}") from None
    if not isinstance(data, dict) or not isinstance(data.get("criteria"), dict):
        raise ValueError("That file is not a saved search")
    search.validate(data["criteria"], viewer)
    name = str(data.get("name") or "Imported search").strip()[:80]
    existing = {s["name"] for s in saved.saved(conn, viewer) if s["owner"] == viewer.username}
    base, n = name, 2
    while name in existing:
        name, n = f"{base} ({n})", n + 1
    return saved.save(conn, viewer, name, data["criteria"], shared)
