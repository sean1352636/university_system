"""First aid rules: RIDDOR assessment, the first-aider certificate register,
first aid kits and AEDs, training course sessions, and the daily reminders.

Tables: ``infrastructure/health/first_aid_schema``. Functions take an open
connection and leave committing to the caller, except :func:`run_daily`
which is the daily job (it commits and returns the e-mails to send).

RIDDOR 2013, as the portal applies it
--------------------------------------
Workers (employees, self-employed):

* death, specified injury, dangerous occurrence — report within 10 days;
* occupational disease — report on diagnosis (10 days given here);
* over-7-day incapacitation — report within 15 days of the accident;
* over-3-day incapacitation — record only, not reported.

Non-workers (students, visitors, the public):

* death — 10 days;
* taken directly from the scene to hospital for treatment — 10 days;
* dangerous occurrence — 10 days (the event is reportable whoever is hurt);
* anything else — not reportable.

Deaths and specified injuries must also be notified to the HSE by the
quickest means (online / phone) without delay; the deadline here is the
latest date for the report.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from education_system.systems.university.domains.health.application.health import access

# ------------------------------------------------------------------ RIDDOR

PERSON_TYPES = {
    "worker": "Worker (employee / self-employed)",
    "non_worker": "Non-worker (student / visitor / public)",
}
CATEGORIES = {
    "death": "Death",
    "specified_injury": "Specified injury (fracture, amputation, serious burn, …)",
    "over_7_day": "Over-7-day incapacitation (worker)",
    "over_3_day": "Over-3-day incapacitation (worker — record only)",
    "occupational_disease": "Occupational disease (worker)",
    "dangerous_occurrence": "Dangerous occurrence",
    "hospital_non_worker": "Non-worker taken to hospital from the scene",
    "not_reportable": "Not reportable",
}
STATUSES = ("not_assessed", "reportable", "reported", "record_only", "not_reportable")
DUE_SOON_DAYS = 3


def riddor_rule(person_type, category) -> tuple[str, int | None]:
    """``(status, days)`` for a person type and category — ``days`` is the
    reporting deadline from the incident date, or None."""
    if person_type not in PERSON_TYPES:
        raise ValueError("Choose whether the person was a worker or a non-worker")
    if category not in CATEGORIES:
        raise ValueError("Choose a RIDDOR category")
    if category == "not_reportable":
        return "not_reportable", None
    if category in ("death", "dangerous_occurrence"):
        return "reportable", 10
    if person_type == "worker":
        if category in ("specified_injury", "occupational_disease"):
            return "reportable", 10
        if category == "over_7_day":
            return "reportable", 15
        if category == "over_3_day":
            return "record_only", None
        return "not_reportable", None             # hospital_non_worker for a worker
    if category == "hospital_non_worker":
        return "reportable", 10
    return "not_reportable", None


#: SQL condition for incidents that are not archived (alias-free).
LIVE = "COALESCE(archived, 0) = 0"


def archive_incident(conn, who, incident_id, reason) -> None:
    """Hide an incident from lists, the RIDDOR queue, reminders and exports
    (``archived = 1`` with who, when and why); the row is kept. Health team
    only. Raises ``PermissionError`` / ``ValueError``. Does not commit."""
    access.require_clinician(who, "archive a first-aid incident")
    reason = (reason or "").strip()
    if len(reason) < 5:
        raise ValueError("Give a reason for archiving the incident")
    row = conn.execute("SELECT COALESCE(archived, 0) FROM first_aid_incidents WHERE id = ?",
                       (incident_id,)).fetchone()
    if row is None:
        raise ValueError(f"No first-aid incident {incident_id}")
    if row[0]:
        raise ValueError(f"First-aid incident {incident_id} is already archived")
    conn.execute("UPDATE first_aid_incidents SET archived = 1, archived_at = ?, archived_by = ?, "
                 "archive_reason = ? WHERE id = ?",
                 (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), who.username, reason,
                  incident_id))


def restore_incident(conn, who, incident_id) -> None:
    """Undo :func:`archive_incident` (health team only). Does not commit."""
    access.require_clinician(who, "restore a first-aid incident")
    conn.execute("UPDATE first_aid_incidents SET archived = 0, archived_at = NULL, "
                 "archived_by = NULL, archive_reason = NULL WHERE id = ?", (incident_id,))


def _require_assessor(who) -> None:
    access.require_clinician(who, "assess or report incidents under RIDDOR")


def _incident(conn, incident_id) -> dict:
    cur = conn.execute("SELECT * FROM first_aid_incidents WHERE id = ?", (incident_id,))
    row = cur.fetchone()
    if row is None:
        raise ValueError(f"No first-aid incident {incident_id}")
    return dict(zip([d[0] for d in cur.description], row))


def assess_riddor(conn, who, incident_id, *, person_type, category, notes=None,
                  incident_date=None) -> dict:
    """Record the RIDDOR assessment; returns status / reportable / deadline."""
    _require_assessor(who)
    incident = _incident(conn, incident_id)
    status, days = riddor_rule(person_type, category)
    when = str(incident_date or incident.get("incident_date")
               or str(incident.get("submitted_at") or "")[:10] or date.today().isoformat())[:10]
    datetime.strptime(when, "%Y-%m-%d")
    deadline = ((datetime.strptime(when, "%Y-%m-%d") + timedelta(days=days)).date().isoformat()
                if days else None)
    if incident.get("riddor_status") == "reported" and status == "reportable":
        status = "reported"                       # re-assessed after reporting
    conn.execute(
        "UPDATE first_aid_incidents SET person_type = ?, riddor_category = ?, "
        "riddor_reportable = ?, riddor_deadline = ?, riddor_status = ?, riddor_notes = ?, "
        "riddor_assessed_by = ?, riddor_assessed_at = ?, incident_date = ? WHERE id = ?",
        (person_type, category, 1 if status in ("reportable", "reported") else 0, deadline,
         status, notes or None, who.username, datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
         when, incident_id))
    return {"status": status, "reportable": status in ("reportable", "reported"),
            "deadline": deadline}


def mark_reported(conn, who, incident_id, hse_reference, reported_on=None) -> None:
    """The report was made to the HSE (its reference is required)."""
    _require_assessor(who)
    incident = _incident(conn, incident_id)
    if not incident.get("riddor_reportable"):
        raise ValueError("Assess the incident as reportable first")
    hse_reference = str(hse_reference or "").strip()
    if not hse_reference:
        raise ValueError("Enter the HSE reference")
    reported_on = str(reported_on or date.today().isoformat())[:10]
    datetime.strptime(reported_on, "%Y-%m-%d")
    conn.execute("UPDATE first_aid_incidents SET hse_reference = ?, riddor_status = 'reported', "
                 "riddor_reported_at = ? WHERE id = ?", (hse_reference, reported_on, incident_id))


def riddor_state(row, today=None) -> str:
    """A one-line state for lists and reports."""
    today = today or date.today().isoformat()
    status = row.get("riddor_status") or "not_assessed"
    if status == "reportable":
        deadline = row.get("riddor_deadline")
        if deadline and deadline < today:
            return f"OVERDUE (was due {deadline})"
        return f"Report by {deadline}" if deadline else "Reportable"
    if status == "reported":
        return f"Reported ({row.get('hse_reference') or 'no ref'})"
    return {"not_assessed": "Not assessed", "record_only": "Record only (over-3-day)",
            "not_reportable": "Not reportable"}.get(status, status)


def riddor_queue(conn, today=None) -> list[dict]:
    """Incidents needing RIDDOR attention: serious ones not yet assessed,
    and reportable ones not yet reported (deadline first)."""
    today = today or date.today().isoformat()
    cur = conn.execute(
        f"SELECT * FROM first_aid_incidents WHERE {LIVE} AND "  # nosec B608 - constant
        "(COALESCE(riddor_status, 'not_assessed') = "
        "'reportable' OR (COALESCE(riddor_status, 'not_assessed') = 'not_assessed' AND "
        "LOWER(COALESCE(severity, '')) IN ('high', 'critical', 'severe'))) "
        "ORDER BY COALESCE(riddor_deadline, '9999'), id")
    names = [d[0] for d in cur.description]
    rows = [dict(zip(names, r)) for r in cur.fetchall()]
    for row in rows:
        row["riddor_state"] = riddor_state(row, today)
    return rows


def riddor_summary(conn, today=None) -> dict:
    today = today or date.today().isoformat()
    soon = (date.fromisoformat(today) + timedelta(days=DUE_SOON_DAYS)).isoformat()
    counts = {s: 0 for s in STATUSES}
    overdue = due_soon = 0
    for status, deadline in conn.execute(
            "SELECT COALESCE(riddor_status, 'not_assessed'), riddor_deadline "
            f"FROM first_aid_incidents WHERE {LIVE}"):  # nosec B608 - constant
        counts[status] = counts.get(status, 0) + 1
        if status == "reportable" and deadline:
            if deadline < today:
                overdue += 1
            elif deadline <= soon:
                due_soon += 1
    return {"by_status": counts, "overdue": overdue, "due_soon": due_soon}


# ------------------------------------------------------------------ first aiders

QUALIFICATIONS = ("First Aid at Work (FAW)", "Emergency First Aid at Work (EFAW)",
                  "Mental Health First Aid", "Paediatric First Aid", "AED / CPR",
                  "Other")
EXPIRY_WARNINGS = (60, 30, 0)


def _require_manager(who, what="manage the first aid registers") -> None:
    access.require_clinician(who, what)


def _rows(cur) -> list[dict]:
    names = [d[0] for d in cur.description]
    return [dict(zip(names, r)) for r in cur.fetchall()]


def save_first_aider(conn, who, data, first_aider_id=None) -> int:
    _require_manager(who)
    name = str(data.get("name") or "").strip()
    qualification = str(data.get("qualification") or "").strip()
    expires_on = str(data.get("expires_on") or "").strip()
    if not name or not qualification or not expires_on:
        raise ValueError("Name, qualification and certificate expiry are required")
    for field in ("issued_on", "expires_on"):
        if data.get(field):
            datetime.strptime(str(data[field]).strip(), "%Y-%m-%d")
    status = str(data.get("status") or "active")
    if status not in ("active", "lapsed", "withdrawn"):
        raise ValueError("Status must be active, lapsed or withdrawn")
    if status == "lapsed" and expires_on >= date.today().isoformat():
        status = "active"                         # renewed
    values = (str(data.get("username") or "").strip() or None, name,
              str(data.get("email") or "").strip() or None, qualification,
              str(data.get("certificate_number") or "").strip() or None,
              str(data.get("issued_on") or "").strip() or None, expires_on,
              str(data.get("location") or "").strip() or None, status,
              str(data.get("notes") or "").strip() or None)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if first_aider_id is None:
        cur = conn.execute(
            "INSERT INTO first_aiders (username, name, email, qualification, certificate_number, "
            "issued_on, expires_on, location, status, notes, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (*values, now))
        return cur.lastrowid
    if not conn.execute("UPDATE first_aiders SET username = ?, name = ?, email = ?, "
                        "qualification = ?, certificate_number = ?, issued_on = ?, "
                        "expires_on = ?, location = ?, status = ?, notes = ?, updated_at = ? "
                        "WHERE id = ?", (*values, now, first_aider_id)).rowcount:
        raise ValueError(f"No first aider {first_aider_id}")
    return first_aider_id


def first_aiders(conn, *, include_withdrawn=False, today=None) -> list[dict]:
    today = today or date.today().isoformat()
    soon = (date.fromisoformat(today) + timedelta(days=EXPIRY_WARNINGS[0])).isoformat()
    sql = "SELECT * FROM first_aiders"
    if not include_withdrawn:
        sql += " WHERE status <> 'withdrawn'"
    rows = _rows(conn.execute(sql + " ORDER BY expires_on, name"))
    for row in rows:
        if row["status"] == "withdrawn":
            row["certificate_state"] = "Withdrawn"
        elif row["expires_on"] < today:
            row["certificate_state"] = "EXPIRED"
        elif row["expires_on"] <= soon:
            row["certificate_state"] = f"Expires {row['expires_on']}"
        else:
            row["certificate_state"] = "Valid"
    return rows


def coverage_by_location(conn, today=None) -> list[dict]:
    """Valid first aiders per location, including places with incidents or
    kits but nobody qualified (coverage gaps first)."""
    today = today or date.today().isoformat()
    places: dict[str, dict] = {}

    def place(name):
        key = str(name or "").strip()
        if not key:
            return None
        return places.setdefault(key.lower(), {"location": key, "valid": 0, "expiring": 0,
                                               "expired": 0, "incidents_90d": 0, "kits": 0,
                                               "aeds": 0})
    soon = (date.fromisoformat(today) + timedelta(days=30)).isoformat()
    for location, expires_on, status in conn.execute(
            "SELECT location, expires_on, status FROM first_aiders WHERE status <> 'withdrawn'"):
        entry = place(location)
        if entry is None:
            continue
        if expires_on < today:
            entry["expired"] += 1
        else:
            entry["valid"] += 1
            if expires_on <= soon:
                entry["expiring"] += 1
    cutoff = (date.fromisoformat(today) - timedelta(days=90)).isoformat()
    for location, count in conn.execute(
            f"SELECT location, COUNT(*) FROM first_aid_incidents WHERE {LIVE} AND "  # nosec B608
            "substr(submitted_at, 1, 10) >= ? GROUP BY location", (cutoff,)):
        entry = place(location)
        if entry is not None:
            entry["incidents_90d"] += count
    for location, kind in conn.execute(
            "SELECT location, kind FROM first_aid_kits WHERE status <> 'retired'"):
        entry = place(location)
        if entry is not None:
            entry["aeds" if kind == "aed" else "kits"] += 1
    out = list(places.values())
    for entry in out:
        entry["gap"] = entry["valid"] == 0
    out.sort(key=lambda e: (not e["gap"], e["location"].lower()))
    return out


# ------------------------------------------------------------------ kits / AEDs

KIT_KINDS = {"kit": "First aid kit", "aed": "AED (defibrillator)", "eyewash": "Eyewash station",
             "burns": "Burns kit"}
KIT_EXPIRY_FIELDS = {"contents_expiry": "contents", "aed_pads_expiry": "AED pads",
                     "aed_battery_expiry": "AED battery"}
KIT_WARNING_DAYS = 30


def save_kit(conn, who, data, kit_id=None) -> int:
    _require_manager(who)
    kind = str(data.get("kind") or "kit")
    if kind not in KIT_KINDS:
        raise ValueError("Unknown kind of equipment")
    label = str(data.get("label") or "").strip()
    location = str(data.get("location") or "").strip()
    if not label or not location:
        raise ValueError("Label and location are required")
    for field in (*KIT_EXPIRY_FIELDS, "last_checked"):
        if data.get(field):
            datetime.strptime(str(data[field]).strip(), "%Y-%m-%d")
    try:
        every = int(data.get("check_every_days") or (7 if kind == "aed" else 30))
    except (TypeError, ValueError):
        raise ValueError("Check interval must be a number of days") from None
    if every < 1:
        raise ValueError("Check interval must be at least a day")
    status = str(data.get("status") or "in_service")
    values = (kind, label, location, str(data.get("detail") or "").strip() or None,
              str(data.get("last_checked") or "").strip() or None, every,
              *(str(data.get(f) or "").strip() or None for f in KIT_EXPIRY_FIELDS), status)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if kit_id is None:
        cur = conn.execute(
            "INSERT INTO first_aid_kits (kind, label, location, detail, last_checked, "
            "check_every_days, contents_expiry, aed_pads_expiry, aed_battery_expiry, status, "
            "created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (*values, now))
        return cur.lastrowid
    if not conn.execute(
            "UPDATE first_aid_kits SET kind = ?, label = ?, location = ?, detail = ?, "
            "last_checked = ?, check_every_days = ?, contents_expiry = ?, aed_pads_expiry = ?, "
            "aed_battery_expiry = ?, status = ?, updated_at = ? WHERE id = ?",
            (*values, now, kit_id)).rowcount:
        raise ValueError(f"No kit {kit_id}")
    return kit_id


def inspect_kit(conn, who, kit_id, outcome, notes=None, *, inspected_by=None) -> int:
    """Record a check. ``faulty`` takes the item out of service; ``ok`` /
    ``restocked`` put it back in service."""
    if outcome not in ("ok", "restocked", "faulty"):
        raise ValueError("Outcome must be ok, restocked or faulty")
    if who is None:
        raise PermissionError("Sign in to record a check")
    if not who.is_clinician:
        raise PermissionError("Only the health team or a first aider can record checks")
    now = datetime.now()
    cur = conn.execute("INSERT INTO first_aid_kit_inspections (kit_id, inspected_at, "
                       "inspected_by, outcome, notes) VALUES (?, ?, ?, ?, ?)",
                       (kit_id, now.strftime("%Y-%m-%d %H:%M:%S"),
                        inspected_by or who.username, outcome, notes or None))
    conn.execute("UPDATE first_aid_kits SET last_checked = ?, status = ?, updated_at = ? "
                 "WHERE id = ?", (now.date().isoformat(),
                                  "out_of_service" if outcome == "faulty" else "in_service",
                                  now.strftime("%Y-%m-%d %H:%M:%S"), kit_id))
    return cur.lastrowid


def kits(conn, *, include_retired=False, today=None) -> list[dict]:
    today = today or date.today().isoformat()
    soon = (date.fromisoformat(today) + timedelta(days=KIT_WARNING_DAYS)).isoformat()
    sql = "SELECT * FROM first_aid_kits"
    if not include_retired:
        sql += " WHERE status <> 'retired'"
    rows = _rows(conn.execute(sql + " ORDER BY location, kind, label"))
    for row in rows:
        problems = []
        if row["last_checked"]:
            due = (date.fromisoformat(row["last_checked"][:10])
                   + timedelta(days=int(row["check_every_days"] or 30))).isoformat()
        else:
            due = today
        row["next_check"] = due
        if due < today or not row["last_checked"]:
            problems.append("check overdue" if row["last_checked"] else "never checked")
        for field, label in KIT_EXPIRY_FIELDS.items():
            when = row.get(field)
            if when and when < today:
                problems.append(f"{label} expired {when}")
            elif when and when <= soon:
                problems.append(f"{label} expire {when}")
        if row["status"] != "in_service":
            problems.append(row["status"].replace("_", " "))
        row["attention"] = "; ".join(problems) or "OK"
    return rows


def kit_inspections(conn, kit_id) -> list[dict]:
    return _rows(conn.execute("SELECT * FROM first_aid_kit_inspections WHERE kit_id = ? "
                              "ORDER BY inspected_at DESC", (kit_id,)))


# ------------------------------------------------------------------ course sessions

COURSES = ("CPR & AED Training", "Emergency First Aid at Work (EFAW)",
           "First Aid at Work (FAW)", "Mental Health First Aid", "First Aid Refresher")


def save_session(conn, who, data, session_id=None) -> int:
    _require_manager(who, "schedule first aid courses")
    course = str(data.get("course") or "").strip()
    starts_at = str(data.get("starts_at") or "").strip()
    if not course or not starts_at:
        raise ValueError("Course and start date/time are required")
    datetime.strptime(starts_at[:16], "%Y-%m-%d %H:%M" if len(starts_at) > 10 else "%Y-%m-%d")
    try:
        capacity = int(data.get("capacity") or 12)
    except (TypeError, ValueError):
        raise ValueError("Capacity must be a number") from None
    if capacity < 1:
        raise ValueError("Capacity must be at least 1")
    values = (course, starts_at, str(data.get("ends_at") or "").strip() or None,
              str(data.get("location") or "").strip() or None,
              str(data.get("trainer") or "").strip() or None, capacity,
              str(data.get("description") or "").strip() or None)
    if session_id is None:
        cur = conn.execute(
            "INSERT INTO first_aid_course_sessions (course, starts_at, ends_at, location, "
            "trainer, capacity, description, status, created_by, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, 'scheduled', ?, ?)",
            (*values, who.username, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        return cur.lastrowid
    if not conn.execute("UPDATE first_aid_course_sessions SET course = ?, starts_at = ?, "
                        "ends_at = ?, location = ?, trainer = ?, capacity = ?, description = ? "
                        "WHERE id = ?", (*values, session_id)).rowcount:
        raise ValueError(f"No session {session_id}")
    return session_id


def set_session_status(conn, who, session_id, status) -> list[tuple]:
    """Cancel or complete a session; cancelling returns e-mails for the
    people booked on it (send after commit)."""
    _require_manager(who, "change first aid courses")
    if status not in ("scheduled", "cancelled", "completed"):
        raise ValueError("Unknown session status")
    session = conn.execute("SELECT course, starts_at FROM first_aid_course_sessions "
                           "WHERE id = ?", (session_id,)).fetchone()
    if session is None:
        raise ValueError(f"No session {session_id}")
    conn.execute("UPDATE first_aid_course_sessions SET status = ? WHERE id = ?",
                 (status, session_id))
    if status != "cancelled":
        return []
    return [(email, f"Cancelled: {session[0]} on {session[1]}",
             f"The {session[0]} session on {session[1]} has been cancelled. Please book "
             "another date in the First Aid portal.")
            for (email,) in conn.execute(
                "SELECT DISTINCT email FROM first_aid_training_registrations WHERE session_id = ? "
                "AND COALESCE(email, '') <> ''", (session_id,))]


def sessions(conn, *, upcoming_only=True, course=None, today=None) -> list[dict]:
    today = today or date.today().isoformat()
    sql = ("SELECT s.*, (SELECT COUNT(*) FROM first_aid_training_registrations r "
           "WHERE r.session_id = s.id) AS booked FROM first_aid_course_sessions s WHERE 1 = 1")
    args: list = []
    if upcoming_only:
        sql += " AND s.status = 'scheduled' AND substr(s.starts_at, 1, 10) >= ?"
        args.append(today)
    if course:
        sql += " AND s.course = ?"
        args.append(course)
    rows = _rows(conn.execute(sql + " ORDER BY s.starts_at", args))
    for row in rows:
        row["places_left"] = max(0, int(row["capacity"] or 0) - int(row["booked"] or 0))
    return rows


def check_booking(conn, session_id, user_id=None, email=None) -> dict:
    """The session a registration is for, refusing full, past, cancelled or
    duplicate bookings."""
    rows = [r for r in sessions(conn, upcoming_only=False) if r["id"] == int(session_id)]
    if not rows:
        raise ValueError("That session no longer exists")
    session = rows[0]
    if session["status"] != "scheduled":
        raise ValueError(f"That session is {session['status']}")
    if str(session["starts_at"])[:10] < date.today().isoformat():
        raise ValueError("That session has already happened")
    if session["places_left"] <= 0:
        raise ValueError("That session is full — choose another date")
    who_key = [k for k in (user_id, email) if k]
    for key in who_key:
        if conn.execute("SELECT 1 FROM first_aid_training_registrations WHERE session_id = ? "
                        "AND (user_id = ? OR email = ?)", (session_id, key, key)).fetchone():
            raise ValueError("You are already booked on that session")
    return session


# ------------------------------------------------------------------ daily reminders

def _coordinators(conn) -> list[str]:
    return sorted({r[0] for r in conn.execute(
        "SELECT email FROM users WHERE LOWER(role) IN ('health_admin', 'admin') "
        "AND COALESCE(email, '') <> ''")})


def _once(conn, kind, ref) -> bool:
    """True the first time ``(kind, ref)`` is seen (then remembered)."""
    return conn.execute("INSERT OR IGNORE INTO first_aid_reminders (kind, ref, sent_at) "
                        "VALUES (?, ?, ?)", (kind, ref, datetime.now().strftime(
                            "%Y-%m-%d %H:%M:%S"))).rowcount == 1


def _certificate_reminders(conn, day, coordinators, tell) -> None:
    """60 / 30 days before expiry and on expiry (then lapsed)."""
    for fid, name, email, qualification, expires_on in conn.execute(
            "SELECT id, name, email, qualification, expires_on FROM first_aiders "
            "WHERE status = 'active'").fetchall():
        left = (date.fromisoformat(expires_on[:10]) - day).days
        stages = [w for w in EXPIRY_WARNINGS if left <= w]
        if not stages:
            continue
        stage = min(stages)                       # the nearest warning reached
        if _once(conn, "certificate", f"{fid}:{expires_on}:{stage}"):
            if stage == 0:
                subject = f"First aid certificate expired: {name}"
                body = (f"{name}'s {qualification} certificate expired on {expires_on}. They "
                        "are no longer counted as a first aider until it is renewed.")
            else:
                subject = f"First aid certificate expires in {left} days: {name}"
                body = (f"{name}'s {qualification} certificate expires on {expires_on}. "
                        "Please book a requalification or refresher course in the First Aid "
                        "portal.")
            tell([email, *coordinators], subject, body)
        if left < 0:
            conn.execute("UPDATE first_aiders SET status = 'lapsed', updated_at = ? "
                         "WHERE id = ?", (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), fid))


def _riddor_reminders(conn, day, coordinators, tell) -> None:
    """Daily while due within DUE_SOON_DAYS or overdue."""
    today = day.isoformat()
    soon = (day + timedelta(days=DUE_SOON_DAYS)).isoformat()
    for iid, deadline, category, location in conn.execute(
            "SELECT id, riddor_deadline, riddor_category, location FROM first_aid_incidents "
            f"WHERE {LIVE} AND riddor_status = 'reportable' AND "  # nosec B608 - constant
            "riddor_deadline IS NOT NULL "
            "AND riddor_deadline <= ?", (soon,)).fetchall():
        if not _once(conn, "riddor", f"{iid}:{today}"):
            continue
        late = deadline < today
        tell(coordinators,
             f"RIDDOR report {'OVERDUE' if late else 'due'}: first-aid incident FA-{iid}",
             f"First-aid incident FA-{iid} at {location or 'an unrecorded location'} is "
             f"reportable under RIDDOR ({CATEGORIES.get(category, category)}). The report "
             f"{'was due' if late else 'is due'} by {deadline}. Report it to the HSE and "
             "record the HSE reference in the First Aid portal (Registers & RIDDOR).")


def _kit_reminders(conn, day, coordinators, tell) -> None:
    """Checks due, and items expiring within KIT_WARNING_DAYS."""
    today = day.isoformat()
    for row in kits(conn, today=today):
        if row["next_check"] <= today and _once(conn, "kit_check",
                                                f"{row['id']}:{row['next_check']}"):
            tell(coordinators, f"{KIT_KINDS[row['kind']]} check due: {row['label']}",
                 f"{row['label']} at {row['location']} is due its check "
                 f"({row['attention']}). Record the check in the First Aid portal.")
        for field, label in KIT_EXPIRY_FIELDS.items():
            when = row.get(field)
            if not when or (date.fromisoformat(when[:10]) - day).days > KIT_WARNING_DAYS:
                continue
            if _once(conn, "kit_expiry", f"{row['id']}:{field}:{when}"):
                tell(coordinators, f"{label[0].upper()}{label[1:]} expiring: {row['label']}",
                     f"The {label} for {row['label']} at {row['location']} "
                     f"{'expired' if when < today else 'expire'} on {when}. Replace and "
                     "update the register.")


def run_daily(conn, today=None) -> list[tuple]:
    """Certificate expiries, RIDDOR deadlines and kit/AED checks; each
    reminder goes once (per stage, or per day for RIDDOR). Lapses expired
    certificates. Returns e-mails (send after the caller commits)."""
    day = date.fromisoformat(today or date.today().isoformat())
    coordinators = _coordinators(conn)
    emails: list[tuple] = []

    def tell(addresses, subject, body):
        for address in sorted({a for a in addresses if a}):
            emails.append((address, subject, body))

    _certificate_reminders(conn, day, coordinators, tell)
    _riddor_reminders(conn, day, coordinators, tell)
    _kit_reminders(conn, day, coordinators, tell)
    return emails


__all__ = [
    "PERSON_TYPES", "CATEGORIES", "STATUSES", "riddor_rule", "assess_riddor", "mark_reported",
    "riddor_state", "riddor_queue", "riddor_summary", "QUALIFICATIONS", "save_first_aider",
    "first_aiders", "coverage_by_location", "KIT_KINDS", "save_kit", "inspect_kit", "kits",
    "kit_inspections", "COURSES", "save_session", "set_session_status", "sessions",
    "check_booking", "run_daily",
]
