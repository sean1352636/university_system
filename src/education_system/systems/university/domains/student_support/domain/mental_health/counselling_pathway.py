"""The counselling service's pathway, from referral to discharge.

1. **Referral** — a student refers themselves, or any member of staff refers
   a student (:func:`refer`). One open referral per student.
2. **Triage** — a member of the counselling team rates the risk (low,
   moderate, high, urgent) and names the triage clinician (:func:`triage`).
   High and urgent go on the **same-day pathway** (due today, top of the
   list) and raise a CRITICAL concern in the safeguarding register — the
   crisis pathway every other part of the university uses
   (``wellbeing_bus.raise_crisis_concern``, after the triage is committed).
   Triage may instead close the referral with signposting (:func:`decline`).
3. **Waiting list** — triaged referrals by priority, then by date, with the
   days each has waited (:func:`waiting_list`); a student sees their own
   position (:func:`my_referrals`).
4. **Allocation** to an active counsellor from the counsellor register
   (``mental_health_core.CounselorManager``) with a session cap (default
   :data:`DEFAULT_SESSION_CAP`) (:func:`allocate`, :func:`extend_cap`).
5. **Sessions** — booked within the cap (:func:`book_session`; mirrored into
   ``counseling_appointments`` so the student's "My Appointments" shows them),
   then recorded as attended, did not attend or cancelled, with sealed
   clinical notes (:func:`record_session`); case notes (:func:`add_case_note`);
   outcome measures at the first, review and last session
   (:func:`record_measure`, scored by :mod:`.outcome_measures`).
6. **Discharge** with a reason (:func:`discharge`); future sessions are
   cancelled.

Only the counselling team (``casework.access.counselling_scope`` is
``None``) works the pathway, and every look at a student's case is written
to the audit log first (refused if that fails). Students never see triage,
notes or scores. Clinical text is sealed at rest.
"""

from __future__ import annotations

import json
from datetime import date, datetime

from education_system.systems.university.domains.student_support.domain.mental_health import (
    counselling_schema,
    outcome_measures,
)
from education_system.systems.university.domains.student_support.domain.wellbeing.casework import (
    access,
)
from education_system.systems.university.infrastructure.database.db import (
    get_connection,
    transaction,
)
from education_system.systems.university.services.bus import wellbeing_bus

RISK_LEVELS = ("low", "moderate", "high", "urgent")
#: risk → (priority, pathway); priority 1 is seen first.
RISK_ROUTES = {"urgent": (1, "crisis"), "high": (2, "same_day"),
               "moderate": (3, "priority"), "low": (4, "routine")}
SAME_DAY_RISKS = ("high", "urgent")
DEFAULT_SESSION_CAP = 6
MAX_SESSION_CAP = 20
OPEN_STATUSES = ("referred", "waiting", "allocated")
SESSION_STATUSES = ("booked", "attended", "dna", "cancelled")
SESSION_STAGES = ("first", "review", "last", "standard")
APPOINTMENT_STATUS = {"booked": "Scheduled", "attended": "Completed", "dna": "No-show",
                      "cancelled": "Cancelled"}
DISCHARGE_REASONS = ("Planned ending", "Session cap reached", "Referred on to another service",
                     "Did not attend", "Student ended counselling", "No longer required",
                     "Left the university")
PRESENTING_ISSUES = ("Anxiety", "Low mood / depression", "Stress", "Relationships",
                     "Bereavement / loss", "Trauma", "Self-harm", "Eating difficulties",
                     "Identity", "Academic pressure", "Other")
STATUS_LABELS = {"referred": "Awaiting triage", "waiting": "On the waiting list",
                 "allocated": "Allocated to a counsellor", "discharged": "Discharged",
                 "closed": "Closed (signposted)"}


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _log(action, entity, **details) -> None:
    try:
        from education_system.systems.university.infrastructure.activity_logger import (
            log_activity,
        )
        log_activity(action, entity, details=details)
    except Exception:  # the write is committed; the activity log is secondary
        pass


def _days_between(start, end=None) -> int | None:
    if not start:
        return None
    first = date.fromisoformat(str(start)[:10])
    last = date.fromisoformat(str(end)[:10]) if end else date.today()
    return (last - first).days


def _referral(conn, referral_id) -> dict:
    row = conn.execute("SELECT * FROM counselling_referrals WHERE referral_id = ?",
                       (int(referral_id),)).fetchone()
    if not row:
        raise ValueError(f"Referral #{referral_id} was not found.")
    return dict(row)


def _require_status(ref, allowed, what) -> None:
    if ref["status"] not in allowed:
        raise ValueError(f"Referral #{ref['referral_id']} is "
                         f"{STATUS_LABELS.get(ref['status'], ref['status']).lower()}; "
                         f"it cannot {what}.")


def _student(conn, student_id) -> dict:
    row = conn.execute(
        "SELECT s.student_id, TRIM(COALESCE(s.first_name, '') || ' ' || "
        "COALESCE(s.last_name, '')) AS name, s.email_address, "
        "(SELECT u.username FROM users u WHERE u.student_id = s.student_id LIMIT 1) "
        "AS username FROM students s WHERE s.student_id = ?", (str(student_id),)).fetchone()
    if not row:
        raise ValueError(f"No student {student_id}.")
    return dict(row)


def _counsellor(conn, counselor_id, *, active=True) -> dict:
    row = conn.execute("SELECT * FROM mental_health_counselors WHERE counselor_id = ?",
                       (int(counselor_id),)).fetchone()
    if not row:
        raise ValueError(f"Counsellor #{counselor_id} was not found.")
    if active and not row["is_active"]:
        raise ValueError(f"{row['name']} is not taking referrals (inactive).")
    return dict(row)


def _reveal(value):
    return wellbeing_bus.reveal(value) if value else value


# ------------------------------------------------------------------ referral

def refer(actor, student_id=None, reason="", *, presenting_issue="",
          consent_to_contact=True) -> int:
    """A referral to counselling; returns its id. A student refers themselves
    (``student_id`` may be left out); staff refer any student."""
    student_id = student_id or access.own_student_id(actor)
    if not student_id:
        raise ValueError("Choose the student to refer.")
    source = access.require_referrer(actor, student_id)
    reason = str(reason or "").strip()
    if len(reason) < 10:
        raise ValueError("Say briefly why counselling is wanted (at least a sentence).")
    counselling_schema.ensure()
    by = access.username(actor)
    with transaction() as conn:
        student = _student(conn, student_id)
        open_ref = conn.execute(
            "SELECT referral_id FROM counselling_referrals WHERE student_id = ? AND status "
            "IN (?, ?, ?)", (str(student_id), *OPEN_STATUSES)).fetchone()
        if open_ref:
            raise ValueError(f"{student['name'] or student_id} already has an open "
                             f"counselling referral (#{open_ref[0]}).")
        now = _now()
        referral_id = conn.execute(
            "INSERT INTO counselling_referrals (student_id, source, referred_by, "
            "presenting_issue, reason, consent_to_contact, referred_at, status, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, 'referred', ?)",
            (str(student_id), source, by, str(presenting_issue or "").strip() or None,
             wellbeing_bus.seal_text(reason), 1 if consent_to_contact else 0, now,
             now)).lastrowid
    _log("create", "counselling_referral", referral_id=referral_id, source=source)
    wellbeing_bus.notify_inbox(
        student_id, "Your counselling referral has been received",
        "The counselling team has received a referral for you"
        + ("" if source == "self" else " from a member of staff")
        + ". A member of the team will review it and contact you about next steps.\n\n"
        "If you are in crisis now, call 999, Samaritans on 116 123 (free, 24 hours) "
        "or text SHOUT to 85258.")
    return int(referral_id)


def triage_queue(actor) -> list[dict]:
    """Referrals awaiting triage, oldest first (counselling team)."""
    access.require_counselling_team(actor)
    counselling_schema.ensure()
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT r.referral_id, r.student_id, r.source, r.referred_by, r.presenting_issue, "
            "r.referred_at, TRIM(COALESCE(s.first_name, '') || ' ' || "
            "COALESCE(s.last_name, '')) AS student_name FROM counselling_referrals r "
            "LEFT JOIN students s ON s.student_id = r.student_id "
            "WHERE r.status = 'referred' ORDER BY r.referred_at").fetchall()
    finally:
        conn.close()
    out = [dict(r) for r in rows]
    for row in out:
        row["days_waiting"] = _days_between(row["referred_at"])
    return out


# ------------------------------------------------------------------ triage

def triage(actor, referral_id, risk_rating, *, notes="", triage_clinician=None) -> dict:
    """Rate the risk and put the referral on the waiting list.

    Returns ``{'referral_id', 'priority', 'pathway', 'same_day',
    'concern_id', 'concern_error'}``; a high or urgent rating raises the
    safeguarding concern after commit (``concern_error`` says why it could
    not be raised, so the screen can tell the clinician to raise it by
    hand)."""
    access.require_counselling_team(actor)
    risk = str(risk_rating or "").strip().lower()
    if risk not in RISK_LEVELS:
        raise ValueError(f"Choose a risk rating: {', '.join(RISK_LEVELS)}.")
    notes = str(notes or "").strip()
    if risk in SAME_DAY_RISKS and len(notes) < 10:
        raise ValueError("Record the risk you have identified in the triage notes.")
    counselling_schema.ensure()
    by = access.username(actor)
    clinician = str(triage_clinician or "").strip() or by
    priority, pathway = RISK_ROUTES[risk]
    same_day = risk in SAME_DAY_RISKS
    with transaction() as conn:
        ref = _referral(conn, referral_id)
        _require_status(ref, ("referred", "waiting"), "be triaged")
        now = _now()
        conn.execute(
            "UPDATE counselling_referrals SET status = 'waiting', risk_rating = ?, "
            "priority = ?, pathway = ?, triaged_by = ?, triage_clinician = ?, triaged_at = ?, "
            "triage_notes = ?, same_day_due = ?, updated_at = ? WHERE referral_id = ?",
            (risk, priority, pathway, by, clinician, now,
             wellbeing_bus.seal_text(notes) if notes else None,
             now[:10] if same_day else None, now, int(referral_id)))
        student = _student(conn, ref["student_id"])
    _log("triage", "counselling_referral", referral_id=int(referral_id), risk=risk)
    result = {"referral_id": int(referral_id), "priority": priority, "pathway": pathway,
              "same_day": same_day, "concern_id": None, "concern_error": None}
    if same_day:
        result.update(_raise_concern(int(referral_id), student, by, risk, notes))
    return result


def _raise_concern(referral_id, student, by, risk, notes) -> dict:
    subject = {"username": student.get("username") or student["student_id"],
               "full_name": student.get("name") or student["student_id"], "role": "student"}
    content = (f"Counselling triage of referral #{referral_id} rated the risk {risk.upper()} "
               f"and put {subject['full_name']} ({student['student_id']}) on the same-day "
               f"pathway. Triage notes: {notes}")
    try:
        concern_id = wellbeing_bus.raise_crisis_concern(subject, content, snippet=notes[:300],
                                                        reporter_username=by)
    except Exception as exc:
        return {"concern_id": None, "concern_error": str(exc) or exc.__class__.__name__}
    with transaction() as conn:
        conn.execute("UPDATE counselling_referrals SET safeguarding_concern_id = ? "
                     "WHERE referral_id = ?", (int(concern_id), referral_id))
    _log("escalate", "counselling_referral", referral_id=referral_id, concern_id=concern_id)
    return {"concern_id": int(concern_id), "concern_error": None}


def escalate(actor, referral_id, reason) -> dict:
    """Move an open referral onto the crisis pathway at any point (a risk item
    scored, something said in session): urgent risk, priority 1, and a
    safeguarding concern."""
    access.require_counselling_team(actor)
    reason = str(reason or "").strip()
    if len(reason) < 10:
        raise ValueError("Record the risk you have identified (at least a sentence).")
    counselling_schema.ensure()
    by = access.username(actor)
    with transaction() as conn:
        ref = _referral(conn, referral_id)
        _require_status(ref, OPEN_STATUSES, "be escalated")
        now = _now()
        conn.execute(
            "UPDATE counselling_referrals SET risk_rating = 'urgent', priority = 1, "
            "pathway = 'crisis', same_day_due = COALESCE(same_day_due, ?), updated_at = ? "
            "WHERE referral_id = ?", (now[:10], now, int(referral_id)))
        _insert_note(conn, ref, "escalation", reason, by)
        student = _student(conn, ref["student_id"])
    return _raise_concern(int(referral_id), student, by, "urgent", reason)


def decline(actor, referral_id, reason) -> None:
    """Close a referral at triage with signposting (counselling is not the
    right service); the student is told."""
    access.require_counselling_team(actor)
    reason = str(reason or "").strip()
    if len(reason) < 10:
        raise ValueError("Say where the student has been signposted (at least a sentence).")
    counselling_schema.ensure()
    by = access.username(actor)
    with transaction() as conn:
        ref = _referral(conn, referral_id)
        _require_status(ref, ("referred", "waiting"), "be closed at triage")
        now = _now()
        conn.execute(
            "UPDATE counselling_referrals SET status = 'closed', discharged_by = ?, "
            "discharged_at = ?, discharge_reason = 'Signposted at triage', "
            "discharge_summary = ?, updated_at = ? WHERE referral_id = ?",
            (by, now, wellbeing_bus.seal_text(reason), now, int(referral_id)))
    _log("decline", "counselling_referral", referral_id=int(referral_id))
    wellbeing_bus.notify_inbox(
        ref["student_id"], "Your counselling referral",
        "The counselling team has reviewed your referral and will be in touch about the "
        "support that suits you best. You can refer yourself again at any time.")


# ------------------------------------------------------------------ waiting list

def waiting_list(actor) -> list[dict]:
    """Triaged referrals waiting for a counsellor: same-day first, then by
    priority and date, with each one's position and days waiting."""
    access.require_counselling_team(actor)
    counselling_schema.ensure()
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT r.referral_id, r.student_id, r.risk_rating, r.priority, r.pathway, "
            "r.triage_clinician, r.triaged_at, r.referred_at, r.same_day_due, "
            "r.safeguarding_concern_id, r.presenting_issue, "
            "TRIM(COALESCE(s.first_name, '') || ' ' || COALESCE(s.last_name, '')) "
            "AS student_name FROM counselling_referrals r "
            "LEFT JOIN students s ON s.student_id = r.student_id "
            "WHERE r.status = 'waiting' ORDER BY r.priority, r.referred_at").fetchall()
    finally:
        conn.close()
    out = []
    for position, row in enumerate(rows, start=1):
        item = dict(row)
        item["position"] = position
        item["days_waiting"] = _days_between(item["referred_at"])
        item["same_day"] = bool(item["same_day_due"])
        out.append(item)
    return out


def _position(conn, ref) -> int | None:
    if ref["status"] != "waiting":
        return None
    ahead = conn.execute(
        "SELECT COUNT(*) FROM counselling_referrals WHERE status = 'waiting' AND "
        "(priority < ? OR (priority = ? AND referred_at < ?))",
        (ref["priority"], ref["priority"], ref["referred_at"])).fetchone()[0]
    return int(ahead) + 1


def my_referrals(actor) -> list[dict]:
    """The signed-in student's referrals: status, waiting-list position, days
    waited, counsellor and appointments — never triage, notes or scores."""
    student_id = access.own_student_id(actor)
    if not student_id:
        raise PermissionError("This page is for students.")
    counselling_schema.ensure()
    conn = get_connection()
    try:
        refs = [dict(r) for r in conn.execute(
            "SELECT r.*, c.name AS counsellor_name FROM counselling_referrals r "
            "LEFT JOIN mental_health_counselors c ON c.counselor_id = r.counsellor_id "
            "WHERE r.student_id = ? ORDER BY r.referred_at DESC", (student_id,))]
        out = []
        for ref in refs:
            sessions = conn.execute(
                "SELECT session_number, session_date, session_time, status FROM "
                "counselling_sessions WHERE referral_id = ? ORDER BY session_date, "
                "session_time", (ref["referral_id"],)).fetchall()
            out.append({
                "referral_id": ref["referral_id"], "referred_at": ref["referred_at"],
                "status": ref["status"],
                "status_label": STATUS_LABELS.get(ref["status"], ref["status"]),
                "position": _position(conn, ref),
                "days_waiting": (_days_between(ref["referred_at"])
                                 if ref["status"] in ("referred", "waiting") else None),
                "counsellor_name": ref["counsellor_name"],
                "session_cap": ref["session_cap"],
                "sessions": [dict(s) for s in sessions]})
        return out
    finally:
        conn.close()


# ------------------------------------------------------------------ allocation

def allocate(actor, referral_id, counselor_id, *, session_cap=DEFAULT_SESSION_CAP) -> None:
    """Allocate a waiting referral to an active counsellor with a session cap."""
    access.require_counselling_team(actor)
    cap = _valid_cap(session_cap)
    counselling_schema.ensure()
    by = access.username(actor)
    with transaction() as conn:
        ref = _referral(conn, referral_id)
        _require_status(ref, ("waiting",), "be allocated (triage it first)")
        counsellor = _counsellor(conn, counselor_id)
        now = _now()
        conn.execute(
            "UPDATE counselling_referrals SET status = 'allocated', counsellor_id = ?, "
            "allocated_by = ?, allocated_at = ?, session_cap = ?, updated_at = ? "
            "WHERE referral_id = ?",
            (counsellor["counselor_id"], by, now, cap, now, int(referral_id)))
    _log("allocate", "counselling_referral", referral_id=int(referral_id),
         counsellor_id=counsellor["counselor_id"], session_cap=cap)
    wellbeing_bus.notify_inbox(
        ref["student_id"], "You have been allocated a counsellor",
        f"{counsellor['name']} will be your counsellor. You can have up to {cap} sessions; "
        "your counsellor will arrange the first one with you.")


def _valid_cap(value) -> int:
    try:
        cap = int(value)
    except (TypeError, ValueError):
        raise ValueError("The session cap must be a whole number.") from None
    if not 1 <= cap <= MAX_SESSION_CAP:
        raise ValueError(f"The session cap must be between 1 and {MAX_SESSION_CAP}.")
    return cap


def extend_cap(actor, referral_id, new_cap, reason) -> None:
    """Raise (or lower) the session cap of an allocated referral, with a
    reason kept as a case note."""
    access.require_counselling_team(actor)
    cap = _valid_cap(new_cap)
    reason = str(reason or "").strip()
    if len(reason) < 5:
        raise ValueError("Give the clinical reason for changing the cap.")
    counselling_schema.ensure()
    by = access.username(actor)
    with transaction() as conn:
        ref = _referral(conn, referral_id)
        _require_status(ref, ("allocated",), "have its cap changed")
        used = _sessions_used(conn, referral_id)
        if cap < used:
            raise ValueError(f"{used} sessions are already booked or held.")
        conn.execute("UPDATE counselling_referrals SET session_cap = ?, updated_at = ? "
                     "WHERE referral_id = ?", (cap, _now(), int(referral_id)))
        _insert_note(conn, ref, "cap_change",
                     f"Session cap {ref['session_cap']} → {cap}: {reason}", by)


def caseload(actor, counselor_id=None) -> list[dict]:
    """Allocated referrals (one counsellor's, or everyone's) with sessions
    used against the cap."""
    access.require_counselling_team(actor)
    counselling_schema.ensure()
    sql = ("SELECT r.referral_id, r.student_id, r.risk_rating, r.pathway, r.allocated_at, "
           "r.session_cap, r.counsellor_id, c.name AS counsellor_name, "
           "TRIM(COALESCE(s.first_name, '') || ' ' || COALESCE(s.last_name, '')) "
           "AS student_name, (SELECT COUNT(*) FROM counselling_sessions x WHERE "
           "x.referral_id = r.referral_id AND COALESCE(x.status, 'booked') <> 'cancelled') "
           "AS sessions_used, (SELECT MIN(x.session_date) FROM counselling_sessions x "
           "WHERE x.referral_id = r.referral_id AND x.status = 'booked' AND "
           "x.session_date >= date('now')) AS next_session "
           "FROM counselling_referrals r "
           "LEFT JOIN mental_health_counselors c ON c.counselor_id = r.counsellor_id "
           "LEFT JOIN students s ON s.student_id = r.student_id WHERE r.status = 'allocated'")
    params: tuple = ()
    if counselor_id:
        sql += " AND r.counsellor_id = ?"
        params = (int(counselor_id),)
    conn = get_connection()
    try:
        return [dict(r) for r in conn.execute(sql + " ORDER BY c.name, r.allocated_at",
                                              params)]
    finally:
        conn.close()


# ------------------------------------------------------------------ sessions

def _sessions_used(conn, referral_id) -> int:
    return int(conn.execute(
        "SELECT COUNT(*) FROM counselling_sessions WHERE referral_id = ? AND "
        "COALESCE(status, 'booked') <> 'cancelled'", (int(referral_id),)).fetchone()[0])


def _valid_when(session_date, session_time) -> tuple[str, str]:
    try:
        day = date.fromisoformat(str(session_date).strip()).isoformat()
        time = datetime.strptime(str(session_time).strip(), "%H:%M").strftime("%H:%M")
    except ValueError:
        raise ValueError("Give the date as YYYY-MM-DD and the time as HH:MM.") from None
    return day, time


def book_session(actor, referral_id, session_date, session_time, *, duration_minutes=50,
                 mode="in-person", stage=None) -> int:
    """Book the next session of an allocated referral within its cap; returns
    the session id. Also books the student's appointment."""
    access.require_counselling_team(actor)
    day, time = _valid_when(session_date, session_time)
    if stage and stage not in SESSION_STAGES:
        raise ValueError(f"Stage must be one of {', '.join(SESSION_STAGES)}.")
    counselling_schema.ensure()
    by = access.username(actor)
    with transaction() as conn:
        ref = _referral(conn, referral_id)
        _require_status(ref, ("allocated",), "have sessions booked")
        used = _sessions_used(conn, referral_id)
        if used >= int(ref["session_cap"]):
            raise ValueError(f"All {ref['session_cap']} sessions in the cap are used; "
                             "extend the cap (with a reason) or discharge.")
        counsellor = _counsellor(conn, ref["counsellor_id"], active=False)
        number = used + 1
        stage = stage or ("first" if number == 1 else "standard")
        appointment_id = conn.execute(
            "INSERT INTO counseling_appointments (student_id, appointment_date, "
            "appointment_time, counselor_name, appointment_type, status) "
            "VALUES (?, ?, ?, ?, 'Individual Counselling', 'Scheduled')",
            (ref["student_id"], day, time, counsellor["name"])).lastrowid
        session_id = conn.execute(
            "INSERT INTO counselling_sessions (student_id, counsellor, session_date, "
            "referral_id, counsellor_id, session_number, session_stage, session_time, "
            "duration_minutes, mode, status, appointment_id, recorded_by, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'booked', ?, ?, ?)",
            (ref["student_id"], counsellor["name"], day, int(referral_id),
             counsellor["counselor_id"], number, stage, time, int(duration_minutes or 50),
             mode, appointment_id, by, _now())).lastrowid
    _log("book", "counselling_session", session_id=session_id, referral_id=int(referral_id))
    wellbeing_bus.notify_inbox(
        ref["student_id"], "Counselling session booked",
        f"Your counselling session {number} with {counsellor['name']} is on {day} at "
        f"{time} ({mode}). If you cannot attend, please let the counselling team know.")
    return int(session_id)


def _session(conn, session_id) -> dict:
    row = conn.execute("SELECT * FROM counselling_sessions WHERE id = ?",
                       (int(session_id),)).fetchone()
    if not row or not row["referral_id"]:
        raise ValueError(f"Session #{session_id} was not found.")
    return dict(row)


def record_session(actor, session_id, status, *, notes=None, outcome=None, stage=None) -> None:
    """Record a session as attended, did not attend (``dna``) or cancelled,
    with sealed clinical notes and outcome."""
    access.require_counselling_team(actor)
    if status not in SESSION_STATUSES[1:]:
        raise ValueError("Record the session as attended, dna or cancelled.")
    if stage and stage not in SESSION_STAGES:
        raise ValueError(f"Stage must be one of {', '.join(SESSION_STAGES)}.")
    counselling_schema.ensure()
    by = access.username(actor)
    with transaction() as conn:
        sess = _session(conn, session_id)
        _require_status(_referral(conn, sess["referral_id"]), ("allocated",),
                        "have sessions recorded")
        conn.execute(
            "UPDATE counselling_sessions SET status = ?, notes = COALESCE(?, notes), "
            "outcome = COALESCE(?, outcome), session_stage = COALESCE(?, session_stage), "
            "recorded_by = ?, updated_at = ? WHERE id = ?",
            (status, wellbeing_bus.seal("counselling_sessions", "notes", notes)
             if notes else None,
             wellbeing_bus.seal("counselling_sessions", "outcome", outcome)
             if outcome else None, stage, by, _now(), int(session_id)))
        if sess.get("appointment_id"):
            conn.execute("UPDATE counseling_appointments SET status = ? "
                         "WHERE appointment_id = ?",
                         (APPOINTMENT_STATUS[status], sess["appointment_id"]))
    _log("record", "counselling_session", session_id=int(session_id), status=status)


def _insert_note(conn, ref, note_type, text, by) -> int:
    return int(conn.execute(
        "INSERT INTO counselling_case_notes (referral_id, student_id, note_type, note, "
        "author, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (ref["referral_id"], ref["student_id"], note_type, wellbeing_bus.seal_text(text),
         by, _now())).lastrowid)


def add_case_note(actor, referral_id, text, note_type="note") -> int:
    access.require_counselling_team(actor)
    text = str(text or "").strip()
    if not text:
        raise ValueError("The note is empty.")
    counselling_schema.ensure()
    with transaction() as conn:
        ref = _referral(conn, referral_id)
        note_id = _insert_note(conn, ref, str(note_type or "note"), text,
                               access.username(actor))
    _log("create", "counselling_case_note", referral_id=int(referral_id), note_id=note_id)
    return note_id


# ------------------------------------------------------------------ outcome measures

def record_measure(actor, referral_id, measure, stage, answers, *, session_id=None) -> dict:
    """Score and store one questionnaire at the first, review or last stage;
    returns the score (``outcome_measures.score``) with ``measure_id``. A
    scored risk item is noted on the case; :func:`escalate` takes it on."""
    access.require_counselling_team(actor)
    if stage not in outcome_measures.STAGES:
        raise ValueError(f"Stage must be one of {', '.join(outcome_measures.STAGES)}.")
    result = outcome_measures.score(measure, answers)
    counselling_schema.ensure()
    by = access.username(actor)
    with transaction() as conn:
        ref = _referral(conn, referral_id)
        _require_status(ref, ("waiting", "allocated"), "have measures recorded")
        if session_id is not None:
            _session(conn, session_id)
        measure_id = conn.execute(
            "INSERT INTO counselling_measures (referral_id, student_id, measure, stage, "
            "session_id, items, total, band, risk_flag, recorded_by, recorded_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (int(referral_id), ref["student_id"], result["measure"], stage, session_id,
             json.dumps(result["items"]), result["total"], result["band"],
             1 if result["risk_flag"] else 0, by, _now())).lastrowid
        if result["risk_flag"]:
            _insert_note(conn, ref, "risk_item",
                         f"{result['measure']} ({stage}): the risk item was scored "
                         f"{result['risk_item_score']}. Review risk and escalate if needed.",
                         by)
    _log("create", "counselling_measure", referral_id=int(referral_id),
         measure=result["measure"], stage=stage)
    return {**result, "measure_id": int(measure_id), "stage": stage}


# ------------------------------------------------------------------ the case

def case_detail(actor, referral_id) -> dict:
    """Everything about one episode of care, unsealed, for the counselling
    team only. The look is audited first (refused if that fails)."""
    access.require_counselling_team(actor)
    counselling_schema.ensure()
    conn = get_connection()
    try:
        ref = _referral(conn, referral_id)
        access.record_view(actor, "counselling", student_id=ref["student_id"],
                           record_id=ref["referral_id"])
        student = _student(conn, ref["student_id"])
        sessions = wellbeing_bus.unseal_rows(conn.execute(
            "SELECT * FROM counselling_sessions WHERE referral_id = ? ORDER BY "
            "session_number, id", (int(referral_id),)).fetchall())
        notes = [dict(r) for r in conn.execute(
            "SELECT * FROM counselling_case_notes WHERE referral_id = ? ORDER BY created_at",
            (int(referral_id),))]
        measures = [dict(r) for r in conn.execute(
            "SELECT * FROM counselling_measures WHERE referral_id = ? ORDER BY recorded_at",
            (int(referral_id),))]
        counsellor = (dict(conn.execute(
            "SELECT counselor_id, name FROM mental_health_counselors WHERE counselor_id = ?",
            (ref["counsellor_id"],)).fetchone() or {}) if ref["counsellor_id"] else {})
    finally:
        conn.close()
    for key in ("reason", "triage_notes", "discharge_summary"):
        ref[key] = _reveal(ref.get(key))
    for note in notes:
        note["note"] = _reveal(note["note"])
    for row in measures:
        row["items"] = json.loads(row["items"] or "[]")
    ref["status_label"] = STATUS_LABELS.get(ref["status"], ref["status"])
    ref["days_waiting"] = _days_between(ref["referred_at"])
    return {"referral": ref, "student": student, "counsellor": counsellor,
            "sessions": sessions, "notes": notes, "measures": measures}


def student_episodes(actor, student_id) -> list[dict]:
    """A student's referrals (no clinical text) for the counselling team."""
    access.require_counselling_team(actor)
    counselling_schema.ensure()
    conn = get_connection()
    try:
        return [dict(r) for r in conn.execute(
            "SELECT referral_id, status, risk_rating, pathway, referred_at, discharged_at, "
            "discharge_reason FROM counselling_referrals WHERE student_id = ? "
            "ORDER BY referred_at DESC", (str(student_id),))]
    finally:
        conn.close()


# ------------------------------------------------------------------ discharge

def discharge(actor, referral_id, reason, *, summary="") -> int:
    """Discharge an episode (any open status) with a reason; future booked
    sessions are cancelled. Returns how many were cancelled."""
    access.require_counselling_team(actor)
    if reason not in DISCHARGE_REASONS:
        raise ValueError(f"Choose a discharge reason: {', '.join(DISCHARGE_REASONS)}.")
    counselling_schema.ensure()
    by = access.username(actor)
    with transaction() as conn:
        ref = _referral(conn, referral_id)
        _require_status(ref, OPEN_STATUSES, "be discharged")
        now = _now()
        booked = [dict(r) for r in conn.execute(
            "SELECT id, appointment_id FROM counselling_sessions WHERE referral_id = ? "
            "AND status = 'booked'", (int(referral_id),))]
        for sess in booked:
            conn.execute("UPDATE counselling_sessions SET status = 'cancelled', "
                         "updated_at = ? WHERE id = ?", (now, sess["id"]))
            if sess["appointment_id"]:
                conn.execute("UPDATE counseling_appointments SET status = 'Cancelled' "
                             "WHERE appointment_id = ?", (sess["appointment_id"],))
        conn.execute(
            "UPDATE counselling_referrals SET status = 'discharged', discharged_by = ?, "
            "discharged_at = ?, discharge_reason = ?, discharge_summary = ?, updated_at = ? "
            "WHERE referral_id = ?",
            (by, now, reason, wellbeing_bus.seal_text(summary) if summary else None, now,
             int(referral_id)))
    _log("discharge", "counselling_referral", referral_id=int(referral_id), reason=reason)
    wellbeing_bus.notify_inbox(
        ref["student_id"], "Your counselling has ended",
        "Your episode of counselling has been closed. You are welcome to refer yourself "
        "again at any time. If you are in crisis, call 999, Samaritans on 116 123 or text "
        "SHOUT to 85258.")
    return len(booked)


# ------------------------------------------------------------------ counsellor register

def _manager():
    from education_system.systems.university.domains.student_support.domain.mental_health.mental_health_core import (
        CounselorManager,
    )
    return CounselorManager


def counsellors(actor, *, active_only=False) -> list[dict]:
    """The counsellor register with open caseloads (counselling team)."""
    access.require_counselling_team(actor)
    counselling_schema.ensure()
    return _manager().list_counselors(active_only=active_only)


def active_counsellors_public() -> list[dict]:
    """Names, specialisms and availability of active counsellors — what a
    student may see before booking (no caseloads, no account ids)."""
    counselling_schema.ensure()
    return [{"name": c["name"], "specialization": c.get("specialization") or "",
             "qualifications": c.get("qualifications") or "",
             "availability_schedule": c.get("availability_schedule") or ""}
            for c in _manager().list_counselors(active_only=True)]


def register_counsellor(actor, username, name, *, specialization="", qualifications="",
                        availability_schedule="", max_daily_appointments=8) -> int:
    access.require_counselling_team(actor)
    username, name = str(username or "").strip(), str(name or "").strip()
    if not username or not name:
        raise ValueError("A counsellor needs a username (their sign-in) and a name.")
    counselling_schema.ensure()
    counselor_id = _manager().register_counselor(
        username, name, specialization, qualifications, availability_schedule,
        int(max_daily_appointments or 8))
    _log("create", "counsellor", counselor_id=counselor_id)
    return int(counselor_id)


def update_counsellor(actor, counselor_id, **fields) -> bool:
    access.require_counselling_team(actor)
    counselling_schema.ensure()
    changed = _manager().update_counselor(int(counselor_id), **fields)
    _log("update", "counsellor", counselor_id=int(counselor_id), fields=sorted(fields))
    return changed


def set_counsellor_active(actor, counselor_id, active: bool) -> bool:
    access.require_counselling_team(actor)
    counselling_schema.ensure()
    changed = _manager().set_active(int(counselor_id), bool(active))
    _log("update", "counsellor", counselor_id=int(counselor_id), active=bool(active))
    return changed
