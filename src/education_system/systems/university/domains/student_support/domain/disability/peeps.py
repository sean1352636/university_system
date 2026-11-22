"""Personal emergency evacuation plans (PEEPs).

A PEEP says how one person — a student (by student number) or a member of
staff (by username) — gets out of the buildings they use when the fire
alarm sounds: where they are (buildings and rooms), what help they need and
how they evacuate, equipment (an evacuation chair, a vibrating pager), their
buddies, the refuge points, how they are alerted, and when the plan is next
reviewed.

Who sees what (``wellbeing/casework/access``): estates and health & safety
staff, disability services, the health team and administrators see the
register (opening a plan is audited, fail closed — a PEEP describes a
disability); estates/H&S and disability services change plans; everyone
sees their own plan.

:func:`send_review_reminders` e-mails (through the outbox) and messages the
person and the plan's manager once per review date when a review is due
within the reminder window; run it from the screens or a daily job.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta

from education_system.systems.university.domains.student_support.domain.disability import (
    dsa_schema,
)
from education_system.systems.university.domains.student_support.domain.wellbeing.casework import (
    access,
)
from education_system.systems.university.infrastructure.database.db import (
    get_connection,
    transaction,
)
from education_system.systems.university.services.bus import wellbeing_bus

PERSON_TYPES = ("student", "staff")
STATUSES = ("draft", "active", "archived")
EVACUATION_METHODS = ("Independent (with alerting)", "Assisted by buddy", "Evacuation chair",
                      "Lift (evacuation lift)", "Refuge and await fire service",
                      "Carry-down by trained staff", "Other")
ALARM_METHODS = ("Audible alarm", "Visual beacon", "Vibrating pager", "Buddy alert",
                 "Text message", "Other")
REMINDER_DAYS = 30
DEFAULT_REVIEW_MONTHS = 12


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _iso(value, what="date") -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10]).isoformat()
    except ValueError:
        raise ValueError(f"The {what} must be a date as YYYY-MM-DD.") from None


def _log(action, **details) -> None:
    try:
        from education_system.systems.university.infrastructure.activity_logger import (
            log_activity,
        )
        log_activity(action, "peep", details=details)
    except Exception:
        pass


def _rows(sql, params=()) -> list[dict]:
    dsa_schema.ensure("peeps")
    conn = get_connection()
    try:
        return [dict(r) for r in conn.execute(sql, params)]
    finally:
        conn.close()


def _plan(peep_id) -> dict:
    found = _rows("SELECT * FROM peeps WHERE peep_id = ?", (int(peep_id),))
    if not found:
        raise ValueError(f"Evacuation plan #{peep_id} was not found.")
    return _decode(found[0])


def _decode(row: dict) -> dict:
    try:
        row["locations"] = json.loads(row.get("locations") or "[]")
    except ValueError:
        row["locations"] = []
    for column in ("assistance_needed", "other_notes"):
        if row.get(column):
            row[column] = wellbeing_bus.reveal(row[column])
    return row


def _me(actor) -> tuple[str, str]:
    """The signed-in person's ``(person_type, person_ref)``."""
    sid = access.own_student_id(actor)
    if sid:
        return "student", str(sid)
    return "staff", access.username(actor)


def _is_own(actor, plan) -> bool:
    try:
        return (plan["person_type"], str(plan["person_ref"])) == _me(actor)
    except PermissionError:
        return False


# ------------------------------------------------------------------ lookups

def known_buildings() -> list[str]:
    """Building names from the estates tables, for the picker (free text is
    still accepted)."""
    names: set[str] = set()
    for sql in ("SELECT building_name FROM buildings", "SELECT DISTINCT building FROM rooms",
                "SELECT building_name FROM campus_buildings"):
        try:
            names.update(str(r[0]).strip() for r in _raw(sql) if r[0] and str(r[0]).strip())
        except Exception:
            continue
    return sorted(names)


def rooms_in(building) -> list[str]:
    try:
        return sorted({str(r[0]) for r in _raw(
            "SELECT room_number FROM rooms WHERE building = ? AND room_number IS NOT NULL",
            (building,))})
    except Exception:
        return []


def _raw(sql, params=()):
    conn = get_connection(row_factory=False)
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def person_name(person_type, person_ref) -> str:
    if person_type == "student":
        found = _raw("SELECT TRIM(COALESCE(first_name, '') || ' ' || COALESCE(last_name, '')) "
                     "FROM students WHERE student_id = ?", (str(person_ref),))
    else:
        found = _raw("SELECT TRIM(COALESCE(first_name, '') || ' ' || COALESCE(last_name, '')) "
                     "FROM users WHERE username = ?", (str(person_ref),))
    return (found[0][0] or "").strip() if found else ""


def person_email(person_type, person_ref) -> str:
    sql = ("SELECT email_address FROM students WHERE student_id = ?" if person_type == "student"
           else "SELECT email FROM users WHERE username = ?")
    found = _raw(sql, (str(person_ref),))
    return (found[0][0] or "") if found else ""


def _exists(person_type, person_ref) -> bool:
    sql = ("SELECT 1 FROM students WHERE student_id = ?" if person_type == "student"
           else "SELECT 1 FROM users WHERE username = ?")
    return bool(_raw(sql, (str(person_ref),)))


# ------------------------------------------------------------------ reading

def register(actor, *, building=None, status=None, review_due_days=None) -> list[dict]:
    """The PEEP register for estates / H&S / disability staff."""
    if not access.is_peep_viewer(actor):
        raise PermissionError("The evacuation plan register is for estates, health & safety "
                              "and disability services staff.")
    clauses, params = [], []
    if status:
        clauses.append("status = ?")
        params.append(status)
    else:
        clauses.append("status <> 'archived'")
    if review_due_days is not None:
        clauses.append("review_date IS NOT NULL AND review_date <= ?")
        params.append((date.today() + timedelta(days=int(review_due_days))).isoformat())
    rows = [_decode(r) for r in _rows(
        "SELECT * FROM peeps WHERE " + " AND ".join(clauses)  # nosec B608
        + " ORDER BY COALESCE(review_date, '9999'), person_name", params)]
    if building:
        wanted = str(building).strip().lower()
        rows = [r for r in rows if any(str(loc.get("building", "")).lower() == wanted
                                       for loc in r["locations"])]
    today = date.today().isoformat()
    for row in rows:
        row["review_overdue"] = bool(row.get("review_date") and row["review_date"] < today)
        row["buildings"] = ", ".join(sorted({str(loc.get("building", ""))
                                             for loc in row["locations"] if loc.get("building")}))
    return rows


def my_plans(actor) -> list[dict]:
    person_type, ref = _me(actor)
    plans = []
    for row in _rows("SELECT * FROM peeps WHERE person_type = ? AND person_ref = ? AND "
                     "status <> 'archived' ORDER BY peep_id DESC", (person_type, ref)):
        plan = _decode(row)
        plan["buddies"] = buddies(plan["peep_id"])
        plans.append(plan)
    return plans


def plan_detail(actor, peep_id) -> dict:
    plan = _plan(peep_id)
    if not _is_own(actor, plan):
        if not access.is_peep_viewer(actor):
            raise PermissionError("That evacuation plan belongs to someone else.")
        access.record_view(actor, "peep",
                           student_id=plan["person_ref"] if plan["person_type"] == "student"
                           else None, record_id=plan["peep_id"])
    plan["buddies"] = buddies(plan["peep_id"])
    return plan


def buddies(peep_id) -> list[dict]:
    return _rows("SELECT * FROM peep_buddies WHERE peep_id = ? ORDER BY id", (int(peep_id),))


# ------------------------------------------------------------------ writing

def _clean_locations(locations) -> list[dict]:
    out = []
    for loc in locations or []:
        if isinstance(loc, str):
            building, _, rooms = loc.partition(":")
            loc = {"building": building, "rooms": rooms}
        building = str(loc.get("building") or "").strip()
        rooms = loc.get("rooms") or ""
        if isinstance(rooms, (list, tuple)):
            rooms = ", ".join(str(r).strip() for r in rooms if str(r).strip())
        if building:
            out.append({"building": building, "rooms": str(rooms).strip()})
    return out


def _fields(data: dict) -> dict:
    assistance = str(data.get("assistance_needed") or "").strip()
    if len(assistance) < 5:
        raise ValueError("Describe the assistance needed to evacuate.")
    locations = _clean_locations(data.get("locations"))
    if not locations:
        raise ValueError("Add at least one building the person uses.")
    status = data.get("status") or "draft"
    if status not in STATUSES:
        raise ValueError("Unknown plan status.")
    review = _iso(data.get("review_date"), "review date")
    if status == "active" and not review:
        raise ValueError("An active plan needs a review date.")
    other = str(data.get("other_notes") or "").strip()
    return {
        "locations": json.dumps(locations),
        "assistance_needed": wellbeing_bus.seal_text(assistance),
        "evacuation_method": str(data.get("evacuation_method") or "").strip() or None,
        "equipment": str(data.get("equipment") or "").strip() or None,
        "refuge_points": str(data.get("refuge_points") or "").strip() or None,
        "alarm_method": str(data.get("alarm_method") or "").strip() or None,
        "other_notes": wellbeing_bus.seal_text(other) if other else None,
        "status": status,
        "review_date": review,
        "manager_username": str(data.get("manager_username") or "").strip() or None,
    }


def _save_buddies(conn, peep_id, people) -> None:
    conn.execute("DELETE FROM peep_buddies WHERE peep_id = ?", (peep_id,))
    for person in people or []:
        name = str(person.get("name") or "").strip()
        if name:
            conn.execute("INSERT INTO peep_buddies (peep_id, name, contact, notes) "
                         "VALUES (?, ?, ?, ?)",
                         (peep_id, name, str(person.get("contact") or "").strip() or None,
                          str(person.get("notes") or "").strip() or None))


def create_plan(actor, person_type, person_ref, data: dict) -> int:
    """A new plan; one current (non-archived) plan per person."""
    access.require_peep_manager(actor)
    if person_type not in PERSON_TYPES:
        raise ValueError("A plan is for a student or a member of staff.")
    person_ref = str(person_ref or "").strip()
    if not person_ref or not _exists(person_type, person_ref):
        raise ValueError(f"No {person_type} {person_ref or '(blank)'}.")
    if _rows("SELECT peep_id FROM peeps WHERE person_type = ? AND person_ref = ? AND "
             "status <> 'archived'", (person_type, person_ref)):
        raise ValueError("This person already has an evacuation plan; edit that one.")
    fields = _fields(data)
    fields["manager_username"] = fields["manager_username"] or access.username(actor)
    columns = ["person_type", "person_ref", "person_name", *fields, "created_by",
               "created_at", "updated_at"]
    values = [person_type, person_ref, person_name(person_type, person_ref), *fields.values(),
              access.username(actor), _now(), _now()]
    with transaction() as conn:
        peep_id = conn.execute(
            f"INSERT INTO peeps ({', '.join(columns)}) "  # nosec B608 - fixed column names
            f"VALUES ({', '.join('?' * len(columns))})", values).lastrowid
        _save_buddies(conn, peep_id, data.get("buddies"))
    _log("create", peep_id=peep_id, person_type=person_type)
    _tell_owner(person_type, person_ref, "An evacuation plan has been recorded for you",
                "A personal emergency evacuation plan (PEEP) has been recorded for you. You "
                "can read it in Disability & Accessibility → My Evacuation Plan. Please tell "
                "disability services if anything in it is wrong.")
    return int(peep_id)


def update_plan(actor, peep_id, data: dict) -> None:
    access.require_peep_manager(actor)
    plan = _plan(peep_id)
    fields = _fields(data)
    fields["manager_username"] = fields["manager_username"] or plan.get("manager_username")
    # A new review date earns a new reminder.
    if fields["review_date"] != plan.get("review_date"):
        fields["reminder_sent_for"] = None
    sets = ", ".join(f"{c} = ?" for c in fields)
    with transaction() as conn:
        conn.execute(f"UPDATE peeps SET {sets}, updated_at = ? WHERE peep_id = ?",  # nosec B608
                     (*fields.values(), _now(), plan["peep_id"]))
        if "buddies" in data:
            _save_buddies(conn, plan["peep_id"], data.get("buddies"))
    _log("update", peep_id=plan["peep_id"])


def mark_reviewed(actor, peep_id, *, next_review=None) -> str:
    """Record a review today and set the next one (default a year on);
    returns the next review date. A draft plan becomes active."""
    access.require_peep_manager(actor)
    plan = _plan(peep_id)
    nxt = _iso(next_review, "next review date") or (
        date.today() + timedelta(days=365 * DEFAULT_REVIEW_MONTHS // 12)).isoformat()
    if nxt <= date.today().isoformat():
        raise ValueError("The next review must be in the future.")
    with transaction() as conn:
        conn.execute("UPDATE peeps SET last_reviewed_by = ?, last_reviewed_at = ?, "
                     "review_date = ?, reminder_sent_for = NULL, status = CASE WHEN "
                     "status = 'draft' THEN 'active' ELSE status END, updated_at = ? "
                     "WHERE peep_id = ?", (access.username(actor), _now(), nxt, _now(),
                                           plan["peep_id"]))
    _log("review", peep_id=plan["peep_id"], next_review=nxt)
    return nxt


def archive_plan(actor, peep_id, reason) -> None:
    access.require_peep_manager(actor)
    reason = (reason or "").strip()
    if len(reason) < 5:
        raise ValueError("Give a reason (e.g. left the university).")
    plan = _plan(peep_id)
    with transaction() as conn:
        conn.execute("UPDATE peeps SET status = 'archived', other_notes = ?, updated_at = ? "
                     "WHERE peep_id = ?",
                     (wellbeing_bus.seal_text(
                         ((plan.get("other_notes") or "") + f"\nArchived {_now()[:10]} by "
                          f"{access.username(actor)}: {reason}").strip()),
                      _now(), plan["peep_id"]))
    _log("archive", peep_id=plan["peep_id"])


# ------------------------------------------------------------------ reminders

def due_reviews(actor=None, within_days=REMINDER_DAYS, today=None) -> list[dict]:
    """Active/draft plans whose review is due within ``within_days`` (or overdue)."""
    if actor is not None and not access.is_peep_viewer(actor):
        raise PermissionError("Review reminders are for the plan managers.")
    today = today or date.today()
    limit = (today + timedelta(days=int(within_days))).isoformat()
    return [_decode(r) for r in _rows(
        "SELECT * FROM peeps WHERE status <> 'archived' AND review_date IS NOT NULL AND "
        "review_date <= ? ORDER BY review_date", (limit,))]


def _tell_owner(person_type, person_ref, subject, body) -> None:
    wellbeing_bus.notify_inbox(person_ref, subject, body)
    wellbeing_bus.send_email(person_email(person_type, person_ref), subject, body)


def send_review_reminders(actor=None, within_days=REMINDER_DAYS, today=None) -> int:
    """Remind the person and the plan's manager of each due review, once per
    review date; returns how many plans were reminded. ``actor`` (when a
    screen runs it) must manage plans; the daily job passes none."""
    if actor is not None:
        access.require_peep_manager(actor)
    sent = 0
    for plan in due_reviews(None, within_days, today):
        if plan.get("reminder_sent_for") == plan["review_date"]:
            continue
        who = plan.get("person_name") or plan["person_ref"]
        subject = f"Evacuation plan review due {plan['review_date']}"
        _tell_owner(plan["person_type"], plan["person_ref"], subject,
                    f"Your personal emergency evacuation plan is due for review on "
                    f"{plan['review_date']}. Disability services or estates will be in touch; "
                    "tell them of any change to the buildings you use or the help you need.")
        manager = plan.get("manager_username") or plan.get("last_reviewed_by") \
            or plan.get("created_by")
        if manager:
            body = (f"The evacuation plan (PEEP #{plan['peep_id']}) for {who} is due for "
                    f"review on {plan['review_date']}. Open Evacuation Plans (PEEPs) to "
                    "review it.")
            wellbeing_bus.notify_inbox(manager, subject, body)
            wellbeing_bus.send_email(person_email("staff", manager), subject, body)
        with transaction() as conn:
            conn.execute("UPDATE peeps SET reminder_sent_for = ? WHERE peep_id = ?",
                         (plan["review_date"], plan["peep_id"]))
        sent += 1
    if sent:
        _log("reminders", count=sent)
    return sent


# ------------------------------------------------------------------ PDF

def plan_pdf(actor, peep_id) -> str:
    """The plan as a PDF to print for the building's fire wardens; its path."""
    from education_system.systems.university.domains.student_support.domain.wellbeing.casework import (
        letters,
    )
    plan = plan_detail(actor, peep_id)
    where = "\n".join(f"{loc['building']}: {loc.get('rooms') or 'all areas'}"
                      for loc in plan["locations"])
    team = "\n".join(f"{b['name']} {b.get('contact') or ''}".strip() for b in plan["buddies"])
    paragraphs = [
        f"Buildings and rooms:\n{where}",
        f"Assistance needed:\n{plan['assistance_needed']}",
        f"Evacuation method: {plan.get('evacuation_method') or 'not set'}",
        f"Equipment: {plan.get('equipment') or 'none'}",
        f"Refuge points: {plan.get('refuge_points') or 'none'}",
        f"Alerted by: {plan.get('alarm_method') or 'not set'}",
        f"Buddies:\n{team or 'none recorded'}",
        f"Status: {plan['status']}. Next review: {plan.get('review_date') or 'not set'}. "
        f"Last reviewed: {plan.get('last_reviewed_at') or 'never'} "
        f"{('by ' + plan['last_reviewed_by']) if plan.get('last_reviewed_by') else ''}",
    ]
    return letters.write_letter(
        reference=f"PEEP-{plan['peep_id']}",
        recipient=plan.get("person_name") or plan["person_ref"],
        subject="Personal Emergency Evacuation Plan", paragraphs=paragraphs,
        signatory=access.username(actor))
