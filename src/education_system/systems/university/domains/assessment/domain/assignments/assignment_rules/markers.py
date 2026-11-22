"""Dividing a cohort's submissions between markers. An assignment with no
allocations works as before: any marker can mark any submission on it."""

from __future__ import annotations

from datetime import datetime


def _has_table(conn, name) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
                        (name,)).fetchone() is not None


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def candidates(conn, assignment_id) -> list[str]:
    """Staff attached to the module; otherwise every instructor and member of
    staff, because many modules have no staff recorded yet."""
    row = conn.execute("SELECT module_code, created_by FROM assignments WHERE id = ?",
                       (assignment_id,)).fetchone()
    if not row:
        return []
    names: set[str] = set()
    if _has_table(conn, "module_staff"):
        names |= {r[0] for r in conn.execute(
            "SELECT username FROM module_staff WHERE module_code = ?", (row[0],))}
    if not names:
        names |= {r[0] for r in conn.execute(
            "SELECT username FROM users WHERE LOWER(role) IN ('instructor', 'staff') "
            "AND COALESCE(service_account, 0) = 0" if _has_service_column(conn) else
            "SELECT username FROM users WHERE LOWER(role) IN ('instructor', 'staff')")}
    return sorted(n for n in names if n)


def _has_service_column(conn) -> bool:
    return "service_account" in {r[1] for r in conn.execute("PRAGMA table_info(users)")}


def rows(conn, assignment_id) -> list[dict]:
    """Current submissions on the assignment and who marks each."""
    out = conn.execute(
        "SELECT s.id, s.student_id, s.grade, m.marker_username FROM assignment_submissions s "
        "LEFT JOIN assignment_marker_allocations m ON m.assignment_id = s.assignment_id "
        "AND m.student_id = s.student_id WHERE s.assignment_id = ? "
        "AND COALESCE(s.is_final_submission, 1) = 1 AND COALESCE(s.status, '') <> 'withdrawn' "
        "ORDER BY s.id", (assignment_id,)).fetchall()
    latest = {r[1]: r for r in out}  # allocations are per student
    return [{"submission_id": r[0], "student_id": r[1], "grade": r[2], "marker": r[3]}
            for r in latest.values()]


def share_evenly(conn, assignment_id, markers, allocated_by) -> int:
    """Give each unallocated, unmarked submission to whoever has fewest.
    Returns how many were allocated."""
    markers = [m for m in dict.fromkeys(str(x).strip() for x in markers) if m]
    if not markers:
        raise ValueError("Choose at least one marker")
    current = rows(conn, assignment_id)
    load = {m: 0 for m in markers}
    for row in current:
        if row["marker"] in load:
            load[row["marker"]] += 1
    done = 0
    for row in current:
        if row["marker"] or row["grade"] is not None:
            continue
        marker = min(markers, key=lambda m: (load[m], markers.index(m)))
        conn.execute("INSERT OR REPLACE INTO assignment_marker_allocations (assignment_id, "
                     "student_id, marker_username, allocated_by, allocated_at) "
                     "VALUES (?, ?, ?, ?, ?)",
                     (assignment_id, row["student_id"], marker, allocated_by, _now()))
        load[marker] += 1
        done += 1
    return done


def set_marker(conn, assignment_id, student_id, marker, allocated_by) -> None:
    """Move one student's work to ``marker``; an empty marker removes it."""
    marker = str(marker or "").strip()
    if not marker:
        conn.execute("DELETE FROM assignment_marker_allocations WHERE assignment_id = ? AND "
                     "student_id = ?", (assignment_id, student_id))
        return
    conn.execute("INSERT OR REPLACE INTO assignment_marker_allocations (assignment_id, student_id, "
                 "marker_username, allocated_by, allocated_at) VALUES (?, ?, ?, ?, ?)",
                 (assignment_id, student_id, marker, allocated_by, _now()))


def clear(conn, assignment_id) -> int:
    return conn.execute("DELETE FROM assignment_marker_allocations WHERE assignment_id = ?",
                        (assignment_id,)).rowcount


def queue_filter(username, role, alias="s") -> tuple[str, list]:
    """``(" AND …", params)`` leaving out work allocated to someone else."""
    if str(role or "").lower() == "admin":
        return "", []
    return (f" AND NOT EXISTS (SELECT 1 FROM assignment_marker_allocations mk "
            f"WHERE mk.assignment_id = {alias}.assignment_id AND mk.student_id = {alias}.student_id "
            "AND mk.marker_username <> ? COLLATE NOCASE)", [str(username or "")])


def allocated_elsewhere(conn, submission_id, username, role) -> str | None:
    """The other marker this submission belongs to, or ``None``."""
    if str(role or "").lower() == "admin" or not _has_table(conn, "assignment_marker_allocations"):
        return None
    row = conn.execute(
        "SELECT m.marker_username FROM assignment_submissions s "
        "JOIN assignment_marker_allocations m ON m.assignment_id = s.assignment_id "
        "AND m.student_id = s.student_id WHERE s.id = ? "
        "AND m.marker_username <> ? COLLATE NOCASE", (submission_id, str(username or ""))).fetchone()
    return row[0] if row else None
