"""Whether a student can submit or withdraw, on every path a submission can
take (the Submit screen, the typed form, group work, the CLI and the API)."""

from __future__ import annotations

from datetime import datetime, timedelta

from education_system.systems.university.domains.assessment.domain.assignments.assignment_rules.visibility import (
    parse_when,
)


def _stamp(when: datetime) -> str:
    return when.strftime("%Y-%m-%d %H:%M:%S")


def _columns(conn, table) -> set[str]:
    return {r[1] for r in conn.execute(f'PRAGMA table_info("{table}")')}


def _has_table(conn, name) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
                        (name,)).fetchone() is not None


def effective_due(conn, assignment_id, student_id, due_date) -> datetime | None:
    """The deadline for this student: the assignment's, or a later approved
    extension. A mitigating-circumstances extension counts as well."""
    best = parse_when(due_date)
    if _has_table(conn, "extension_requests"):
        cols = _columns(conn, "extension_requests")
        fields = [c for c in ("new_due_date", "requested_due_date") if c in cols]
        if fields:
            rows = conn.execute(
                f"SELECT COALESCE({', '.join(fields)}, NULL) FROM extension_requests "  # nosec B608
                "WHERE assignment_id = ? AND student_id = ? AND LOWER(status) = 'approved'",
                (assignment_id, student_id)).fetchall()
            for row in rows:
                later = parse_when(row[0])
                if later and (best is None or later > best):
                    best = later
    try:
        from education_system.systems.university.domains.assessment.domain.mitigating_circumstances.integration import (
            get_active_extension,
        )
        info = conn.execute("SELECT module_code, title FROM assignments WHERE id = ?",
                            (assignment_id,)).fetchone()
        if info:
            ext = get_active_extension(student_id, info[0], info[1])
            later = parse_when((ext or {}).get("new_deadline"))
            if later and (best is None or later > best):
                best = later
    except Exception:  # an unavailable MC service must not block a submission
        pass
    return best


def attempts_used(conn, assignment_id, student_id) -> int:
    """Withdrawn versions don't count."""
    return conn.execute("SELECT COUNT(*) FROM assignment_submissions WHERE assignment_id = ? "
                        "AND student_id = ? AND COALESCE(status, '') <> 'withdrawn'",
                        (assignment_id, student_id)).fetchone()[0]


def check_can_submit(conn, assignment_id, student_id, now=None) -> dict:
    """``{"due", "late", "late_days"}``, or ``ValueError`` saying why not."""
    now = now or datetime.now()
    cols = _columns(conn, "assignments")
    wanted = ["is_active", "due_date", "allow_late_submission", "assignment_type", "max_late_days",
              "max_attempts", "status", "available_from"]
    fields = ", ".join(c if c in cols else f"NULL AS {c}" for c in wanted)
    row = conn.execute(f"SELECT {fields} FROM assignments WHERE id = ?",  # nosec B608
                       (assignment_id,)).fetchone()
    if not row:
        raise ValueError("That assignment no longer exists")
    is_active, due_date, allow_late, kind, max_late, max_attempts, status, opens = row
    if str(status or "").lower() == "scheduled":
        raise ValueError(f"This assignment opens on {opens}")
    if is_active is not None and not is_active:
        raise ValueError("This assignment is not open for submissions")
    if str(kind or "").lower() == "quiz":
        raise ValueError("This is a quiz. Sit it from My Quizzes instead of uploading a file.")

    if max_attempts and attempts_used(conn, assignment_id, student_id) >= int(max_attempts):
        raise ValueError(f"You have used all {int(max_attempts)} attempt(s) for this assignment. "
                         "Withdraw a submission first if the deadline hasn't passed.")

    due = effective_due(conn, assignment_id, student_id, due_date)
    late = bool(due and now > due)
    if late:
        if allow_late is not None and not allow_late:
            raise ValueError("Late submissions are not allowed for this assignment")
        if max_late and now - due > timedelta(days=int(max_late)):
            raise ValueError(f"Late submissions closed {int(max_late)} day(s) after the deadline")
    return {"due": due, "late": late, "late_days": (now - due).days if late else 0}


def record_declaration(conn, submission_id, now=None) -> None:
    """Note when the student confirmed the work is their own."""
    if "declaration_at" in _columns(conn, "assignment_submissions"):
        conn.execute("UPDATE assignment_submissions SET declaration_at = ? WHERE id = ?",
                     (_stamp(now or datetime.now()), submission_id))


def record_scan(conn, submission_id, result) -> None:
    if "virus_scan" in _columns(conn, "assignment_submissions"):
        conn.execute("UPDATE assignment_submissions SET virus_scan = ? WHERE id = ?",
                     (result, submission_id))


def withdrawal_problem(conn, sub, now=None) -> str | None:
    """Why this submission can't be withdrawn, or ``None``. ``sub`` has id,
    assignment_id, student_id, grade, status, group_id and due_date."""
    now = now or datetime.now()
    if str(sub["status"] or "") == "withdrawn":
        return "This submission has already been withdrawn."
    if sub["grade"] is not None:
        return "This submission has been marked, so it can't be withdrawn."
    if sub["group_id"]:
        return "Group work is submitted for the whole group, so it can't be withdrawn here. " \
               "Ask your module leader."
    due = effective_due(conn, sub["assignment_id"], sub["student_id"], sub["due_date"])
    if due and now > due:
        return "The deadline has passed, so this submission can't be withdrawn."
    if _has_table(conn, "integrity_cases") and conn.execute(
            "SELECT 1 FROM integrity_cases WHERE submission_id = ? AND "
            "COALESCE(stage, 'referred') NOT IN ('decided', 'closed')",
            (sub["id"],)).fetchone():
        return "This submission is part of an open academic integrity case, so it can't be " \
               "withdrawn."
    return None


def withdraw(conn, submission_id, student_id, now=None) -> dict:
    """Withdraw the student's own submission before the deadline. The file and
    its check results stay on record; an earlier version becomes current
    again. Returns ``{"assignment_id", "title", "restored_version"}``."""
    now = now or datetime.now()
    row = conn.execute(
        "SELECT s.id, s.assignment_id, s.student_id, s.grade, s.status, s.group_id, "
        "a.due_date, a.title FROM assignment_submissions s JOIN assignments a "
        "ON a.id = s.assignment_id WHERE s.id = ?", (submission_id,)).fetchone()
    if not row or str(row[2]) != str(student_id):
        raise ValueError("That isn't one of your submissions")
    sub = dict(zip(("id", "assignment_id", "student_id", "grade", "status", "group_id",
                    "due_date", "title"), row))
    problem = withdrawal_problem(conn, sub, now)
    if problem:
        raise ValueError(problem)
    conn.execute("UPDATE assignment_submissions SET status = 'withdrawn', is_final_submission = 0, "
                 "withdrawn_at = ? WHERE id = ?", (_stamp(now), submission_id))
    earlier = conn.execute(
        "SELECT id, version_number FROM assignment_submissions WHERE assignment_id = ? AND "
        "student_id = ? AND COALESCE(status, '') <> 'withdrawn' ORDER BY id DESC LIMIT 1",
        (sub["assignment_id"], student_id)).fetchone()
    if earlier:
        conn.execute("UPDATE assignment_submissions SET is_final_submission = 1 WHERE id = ?",
                     (earlier[0],))
    if _has_table(conn, "peer_reviews"):
        conn.execute("DELETE FROM peer_reviews WHERE status = 'pending' AND "
                     "COALESCE(submission_id, reviewee_submission_id) = ?", (submission_id,))
    if _has_table(conn, "submission_history"):
        conn.execute("INSERT INTO submission_history (submission_id, student_id, action, "
                     "action_date, details) VALUES (?, ?, 'withdrawn', ?, ?)",
                     (submission_id, student_id, _stamp(now), "Withdrawn by the student"))
    return {"assignment_id": sub["assignment_id"], "title": sub["title"],
            "restored_version": earlier[1] if earlier else None}
