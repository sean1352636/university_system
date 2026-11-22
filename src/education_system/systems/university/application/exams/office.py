"""Exam office records: incidents in the exam room, and exam papers.

Incidents — late arrivals, leaving early, illness, disruption, a fire alarm,
suspected malpractice — had nowhere to go for a sit-down exam (the integrity
tools cover online proctoring only). A suspected-malpractice incident is
referred into an academic integrity case (``integrity_review.open_case``,
source ``exam_incident``, the incident added as evidence), so it is
investigated rather than just noted.

Exam papers move through a fixed sequence: draft → internally checked →
externally approved → printed → secured. A step cannot be skipped, the
external examiner's name is recorded at approval, and every change is kept
in ``exam_paper_history``. :func:`paper_deadline_report` lists sittings whose
paper is behind.

Functions take an open connection and do not commit.
"""

from __future__ import annotations

from datetime import datetime, timedelta

INCIDENT_TYPES = {
    "late_arrival": "Late arrival",
    "left_early": "Left early",
    "illness": "Illness during the exam",
    "disruption": "Disruption",
    "fire_alarm": "Fire alarm / evacuation",
    "malpractice_suspected": "Suspected malpractice",
    "technical": "Technical problem",
    "other": "Other",
}
#: Paper workflow, in order.
PAPER_STATES = ("draft", "internally_checked", "externally_approved", "printed", "secured")
PRINT_LEAD_DAYS = 14


class ExamOfficeError(ValueError):
    """An exam office rule refused the action; the message is safe to show."""


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _exam_date(conn, exam_id):
    row = conn.execute("SELECT date, module_code FROM exams WHERE id = ?", (exam_id,)).fetchone()
    if row is None:
        raise ExamOfficeError(f"Exam {exam_id} not found.")
    return row


# ── incidents ───────────────────────────────────────────────────────────


def log_incident(conn, exam_id, incident_type, description, *, student_id=None,
                 minutes_late=None, action_taken=None, reported_by=None, occurred_at=None) -> int:
    if incident_type not in INCIDENT_TYPES:
        raise ExamOfficeError(f"Incident type must be one of: {', '.join(INCIDENT_TYPES)}.")
    if not (description or "").strip():
        raise ExamOfficeError("Describe what happened.")
    if incident_type in ("late_arrival", "left_early", "illness", "malpractice_suspected") and not student_id:
        raise ExamOfficeError("This kind of incident needs the student it concerns.")
    _exam_date(conn, exam_id)
    return conn.execute(
        "INSERT INTO exam_incidents (exam_id, student_id, incident_type, description, minutes_late, "
        "action_taken, occurred_at, reported_by, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (exam_id, str(student_id) if student_id else None, incident_type, description.strip(),
         int(minutes_late) if minutes_late not in (None, "") else None, action_taken,
         occurred_at or _now(), reported_by, _now())).lastrowid


def incidents(conn, exam_id=None, student_id=None) -> list[dict]:
    where, params = [], []
    if exam_id:
        where.append("i.exam_id = ?")
        params.append(exam_id)
    if student_id:
        where.append("i.student_id = ?")
        params.append(str(student_id))
    cur = conn.execute(
        "SELECT i.*, e.module_code, e.date FROM exam_incidents i JOIN exams e ON e.id = i.exam_id "
        + ("WHERE " + " AND ".join(where) + " " if where else "") + "ORDER BY i.occurred_at DESC",
        params)  # nosec B608 - fixed clauses
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def refer_to_misconduct(conn, incident_id, opened_by, outbox=None) -> int:
    """Open an academic integrity case for a suspected-malpractice incident,
    in the caller's transaction. Returns the case id, also stored on the
    incident. E-mails to the student and the integrity officers are added to
    ``outbox`` (when given) for the caller to send after commit."""
    row = conn.execute(
        "SELECT i.student_id, i.incident_type, i.description, e.module_code, e.date, i.case_id, "
        "i.occurred_at, i.reported_by FROM exam_incidents i JOIN exams e ON e.id = i.exam_id "
        "WHERE i.id = ?", (incident_id,)).fetchone()
    if row is None:
        raise ExamOfficeError("Incident not found.")
    student_id, kind, description, module_code, date, case_id, occurred, reporter = row
    if case_id:
        return case_id
    if kind != "malpractice_suspected" or not student_id:
        raise ExamOfficeError("Only a suspected-malpractice incident about a student can be referred.")
    from education_system.systems.university.application.integrity import (
        review as integrity_review,
    )
    out = integrity_review.open_case(
        conn, None, student_id=str(student_id), case_type="cheating",
        description=f"Exam malpractice suspected: {module_code} on {date} — {description}",
        module_code=module_code, source="exam_incident", source_ref=incident_id,
        actor=opened_by or "exam_office",
        evidence_items=[{"kind": "exam_incident", "ref": incident_id,
                         "title": f"Exam incident {incident_id} ({module_code}, {date})",
                         "detail": f"Reported by {reporter or 'the invigilator'} at "
                                   f"{occurred or date}: {description}"}])
    conn.execute("UPDATE exam_incidents SET case_id = ? WHERE id = ?", (out["case_id"], incident_id))
    if outbox is not None:
        outbox.extend(out["emails"])
    return out["case_id"]


# ── exam papers ─────────────────────────────────────────────────────────


def paper(conn, exam_id, create=True) -> dict | None:
    cur = conn.execute("SELECT * FROM exam_papers WHERE exam_id = ?", (exam_id,))
    row = cur.fetchone()
    if row is None and create:
        date, _module = _exam_date(conn, exam_id)
        deadline = None
        try:
            deadline = (datetime.strptime(date, "%Y-%m-%d") - timedelta(days=PRINT_LEAD_DAYS)).strftime("%Y-%m-%d")
        except (TypeError, ValueError):
            pass
        conn.execute("INSERT INTO exam_papers (exam_id, status, print_deadline, updated_at) "
                     "VALUES (?, 'draft', ?, ?)", (exam_id, deadline, _now()))
        cur = conn.execute("SELECT * FROM exam_papers WHERE exam_id = ?", (exam_id,))
        row = cur.fetchone()
    if row is None:
        return None
    return dict(zip([d[0] for d in cur.description], row))


def _stamp_fields(to_state, actor, examiner, location):
    if to_state == "internally_checked":
        return {"internal_checker": actor, "internal_checked_at": _now()}
    if to_state == "externally_approved":
        if not (examiner or "").strip():
            raise ExamOfficeError("Record the external examiner who approved the paper.")
        return {"external_examiner": examiner.strip(), "external_approved_at": _now()}
    if to_state == "printed":
        return {"printed_at": _now()}
    if to_state == "secured":
        if not (location or "").strip():
            raise ExamOfficeError("Record where the printed papers are secured.")
        return {"secured_location": location.strip()}
    return {}


def advance_paper(conn, exam_id, to_state, actor=None, *, external_examiner=None,
                  secured_location=None, notes=None, setter=None) -> dict:
    """Move a paper to the next state. Steps cannot be skipped; moving back
    to 'draft' (a rework) is allowed from any state and is recorded."""
    current = paper(conn, exam_id)
    if to_state not in PAPER_STATES:
        raise ExamOfficeError(f"State must be one of {', '.join(PAPER_STATES)}.")
    here = PAPER_STATES.index(current["status"])
    there = PAPER_STATES.index(to_state)
    if to_state != "draft" and there != here + 1:
        raise ExamOfficeError(f"A paper at '{current['status']}' can only move to "
                              f"'{PAPER_STATES[here + 1] if here + 1 < len(PAPER_STATES) else '—'}' "
                              "(or back to draft).")
    fields = _stamp_fields(to_state, actor, external_examiner, secured_location)
    fields.update({"status": to_state, "updated_at": _now()})
    if setter:
        fields["setter"] = setter
    if notes:
        fields["notes"] = notes
    sets = ", ".join(f'"{k}" = ?' for k in fields)
    conn.execute(f"UPDATE exam_papers SET {sets} WHERE id = ?",  # nosec B608 - fixed keys
                 (*fields.values(), current["id"]))
    conn.execute("INSERT INTO exam_paper_history (paper_id, from_status, to_status, actor, notes, changed_at) "
                 "VALUES (?, ?, ?, ?, ?, ?)", (current["id"], current["status"], to_state, actor, notes, _now()))
    return paper(conn, exam_id)


def paper_history(conn, exam_id) -> list[dict]:
    cur = conn.execute(
        "SELECT h.from_status, h.to_status, h.actor, h.notes, h.changed_at FROM exam_paper_history h "
        "JOIN exam_papers p ON p.id = h.paper_id WHERE p.exam_id = ? ORDER BY h.id", (exam_id,))
    return [dict(zip(("from_status", "to_status", "actor", "notes", "changed_at"), r)) for r in cur.fetchall()]


def paper_deadline_report(conn, days_ahead=42) -> list[dict]:
    """Upcoming sittings whose paper is not printed, flagged when the print
    deadline has passed or external approval is still missing."""
    today = datetime.now().date()
    horizon = (today + timedelta(days=days_ahead)).isoformat()
    out = []
    for exam_id, module_code, date in conn.execute(
            "SELECT id, module_code, date FROM exams WHERE date >= ? AND date <= ? ORDER BY date",
            (today.isoformat(), horizon)).fetchall():
        # A report should not create rows: a sitting with no paper record is a draft.
        p = paper(conn, exam_id, create=False) or {
            "status": "draft",
            "print_deadline": (datetime.strptime(date, "%Y-%m-%d")
                               - timedelta(days=PRINT_LEAD_DAYS)).strftime("%Y-%m-%d")}
        if PAPER_STATES.index(p["status"]) >= PAPER_STATES.index("printed"):
            continue
        overdue = bool(p["print_deadline"] and p["print_deadline"] < today.isoformat())
        out.append({"exam_id": exam_id, "module_code": module_code, "date": date,
                    "status": p["status"], "print_deadline": p["print_deadline"], "overdue": overdue,
                    "needs_external": PAPER_STATES.index(p["status"]) < PAPER_STATES.index("externally_approved")})
    return out
