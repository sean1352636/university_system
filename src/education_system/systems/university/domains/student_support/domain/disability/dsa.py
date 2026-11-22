"""Disabled Students' Allowances (DSA) casework.

One case per application to a funding body — Student Finance England,
Student Finance Wales, SAAS or Student Finance NI — tracked from "not
applied" through eligibility (the DSA1 letter), the needs assessment, the
recommendations (the DSA2 letter) to support in place, with:

* the **needs assessment** booking (centre, assessor, date, attended);
* the **recommendations**, by category; a reasonable-adjustment one becomes
  an approved adjustment in the Disability & Accessibility portal
  (``wellbeing_bus.add_adjustment``), and existing adjustments can be linked
  to the case;
* **non-medical help** (support worker, type, band, hours allocated) with a
  log of hours used and what is left;
* **equipment** (supplier, ordered, delivered, training);
* **exam access arrangements**, applied as an ``accommodations`` row that
  ``accommodation_bus.reconcile`` carries to exam accommodations — this
  module never writes exam tables.

Access is the portal's (``disability/access``): disability services and the
health team work every case (and opening one is audited, fail closed); a
student sees their own, read-only. Nothing here is sent to the funding
body: statuses record what the student or the assessor reports.
"""

from __future__ import annotations

from datetime import date, datetime

from education_system.systems.university.domains.student_support.domain.disability import (
    access,
    dsa_schema,
)
from education_system.systems.university.infrastructure.database.db import (
    get_connection,
    transaction,
)
from education_system.systems.university.services.bus import wellbeing_bus

FUNDING_BODIES = {
    "SFE": "Student Finance England",
    "SFW": "Student Finance Wales",
    "SAAS": "Student Awards Agency Scotland",
    "SFNI": "Student Finance NI",
    "NHS": "NHS Learning Support (DSA-equivalent)",
    "OTHER": "Other / institutional funding",
}
STATUSES = ("not_applied", "applied", "eligible", "assessment_booked", "assessed",
            "dsa2_received", "support_in_place", "closed")
STATUS_LABELS = {
    "not_applied": "Not yet applied",
    "applied": "Applied to funding body",
    "eligible": "Eligibility confirmed (DSA1 letter)",
    "assessment_booked": "Needs assessment booked",
    "assessed": "Needs assessment done",
    "dsa2_received": "Recommendations received (DSA2 letter)",
    "support_in_place": "Support in place",
    "closed": "Closed",
}
STATUS_DATE_COLUMN = {
    "applied": "applied_date", "eligible": "eligibility_date",
    "assessment_booked": "assessment_booked_date", "assessed": "assessed_date",
    "dsa2_received": "dsa2_date", "support_in_place": "support_in_place_date",
    "closed": "closed_date",
}
CATEGORIES = ("equipment", "nmh_support", "exam_access", "reasonable_adjustment", "other")
CATEGORY_LABELS = {"equipment": "Equipment", "nmh_support": "Non-medical help",
                   "exam_access": "Exam access arrangement",
                   "reasonable_adjustment": "Reasonable adjustment", "other": "Other"}
RECOMMENDATION_STATUSES = ("recommended", "in_progress", "in_place", "declined")
NMH_TYPES = ("Specialist study skills", "Specialist mentor", "Note-taker",
             "BSL interpreter", "Assistive technology trainer", "Reader", "Scribe",
             "Exam support worker", "Other")
NMH_BANDS = ("Band 1", "Band 2", "Band 3", "Band 4")
EQUIPMENT_STATUSES = ("recommended", "ordered", "delivered", "training_done", "returned",
                      "cancelled")
EXAM_TYPE = "Exam Access Arrangements"
MAX_SESSION_HOURS = 12


# ------------------------------------------------------------------ helpers

def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _iso(value, what="date", required=False) -> str | None:
    text = str(value or "").strip()
    if not text:
        if required:
            raise ValueError(f"Enter the {what} (YYYY-MM-DD).")
        return None
    try:
        return date.fromisoformat(text[:10]).isoformat()
    except ValueError:
        raise ValueError(f"The {what} must be a date as YYYY-MM-DD.") from None


def _log(action, entity, **details) -> None:
    try:
        from education_system.systems.university.infrastructure.activity_logger import (
            log_activity,
        )
        log_activity(action, entity, details=details)
    except Exception:
        pass


def _rows(sql, params=()) -> list[dict]:
    dsa_schema.ensure("dsa")
    conn = get_connection()
    try:
        return [dict(r) for r in conn.execute(sql, params)]
    finally:
        conn.close()


def _one(sql, params=()) -> dict | None:
    found = _rows(sql, params)
    return found[0] if found else None


def _case(case_id) -> dict:
    case = _one("SELECT * FROM dsa_cases WHERE case_id = ?", (int(case_id),))
    if not case:
        raise ValueError(f"DSA case #{case_id} was not found.")
    return case


def _require_manager(actor) -> None:
    access.require_staff(actor)
    if not access.may_manage(actor):
        raise PermissionError("Only disability services can change DSA cases.")


def _student_exists(student_id) -> bool:
    return bool(_one("SELECT student_id FROM students WHERE student_id = ?",
                     (str(student_id),)))


def _notify(student_id, subject, body) -> None:
    wellbeing_bus.notify_inbox(student_id, subject, body)


def _reveal(row: dict, *columns) -> dict:
    for column in columns:
        if row.get(column):
            row[column] = wellbeing_bus.reveal(row[column])
    return row


# ------------------------------------------------------------------ cases

def open_case(actor, student_id, *, funding_body="SFE", sfe_reference="", notes="") -> int:
    """A new DSA case for ``student_id``; one open case per student."""
    _require_manager(actor)
    student_id = str(student_id or "").strip()
    if not student_id or not _student_exists(student_id):
        raise ValueError(f"No student {student_id or '(blank)'}.")
    if funding_body not in FUNDING_BODIES:
        raise ValueError("Choose the funding body.")
    if _one("SELECT case_id FROM dsa_cases WHERE student_id = ? AND status <> 'closed'",
            (student_id,)):
        raise ValueError("This student already has an open DSA case.")
    with transaction() as conn:
        case_id = conn.execute(
            "INSERT INTO dsa_cases (student_id, funding_body, sfe_reference, notes, "
            "created_by, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (student_id, funding_body, (sfe_reference or "").strip() or None,
             wellbeing_bus.seal_text(notes.strip()) if notes and notes.strip() else None,
             access.username(actor), _now(), _now())).lastrowid
        conn.execute("INSERT INTO dsa_status_history (case_id, from_status, to_status, "
                     "changed_by, note) VALUES (?, NULL, 'not_applied', ?, 'Case opened')",
                     (case_id, access.username(actor)))
    _log("create", "dsa_case", case_id=case_id, student_id=student_id)
    return int(case_id)


def list_cases(actor, *, include_closed=False, status=None) -> list[dict]:
    """Staff: every case (with the student's name); a student: their own."""
    scoped = access.scope(actor)
    clauses, params = [], []
    if scoped is not None:
        clauses.append("c.student_id = ?")
        params.append(scoped)
    if status:
        clauses.append("c.status = ?")
        params.append(status)
    elif not include_closed:
        clauses.append("c.status <> 'closed'")
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    rows = _rows(
        "SELECT c.case_id, c.student_id, c.funding_body, c.sfe_reference, c.status, "
        "c.updated_at, TRIM(COALESCE(s.first_name, '') || ' ' || COALESCE(s.last_name, '')) "
        "AS student_name FROM dsa_cases c LEFT JOIN students s ON s.student_id = c.student_id "
        f"{where} ORDER BY c.updated_at DESC, c.case_id DESC", params)  # nosec B608
    for row in rows:
        row["status_label"] = STATUS_LABELS.get(row["status"], row["status"])
    return rows


def my_cases(actor) -> list[dict]:
    sid = access.own_student_id(actor)
    if not sid:
        raise PermissionError("These pages are for students; your account has no student "
                              "record.")
    return list_cases(actor, include_closed=True)


def case_detail(actor, case_id) -> dict:
    """Everything on one case. A staff look is audited first (fail closed)."""
    case = _case(case_id)
    access.require_student(actor, case["student_id"])
    if access.scope(actor) is None:
        person = access.who(actor)
        if person is None:
            raise PermissionError("Sign in first.")
        wellbeing_bus.record_view(person, "dsa_case", student_id=case["student_id"],
                                  record_id=case["case_id"])
    cid = case["case_id"]
    _reveal(case, "notes")
    case["status_label"] = STATUS_LABELS.get(case["status"], case["status"])
    case["funding_body_label"] = FUNDING_BODIES.get(case["funding_body"], case["funding_body"])
    case["history"] = _rows("SELECT * FROM dsa_status_history WHERE case_id = ? ORDER BY id",
                            (cid,))
    case["assessments"] = [_reveal(r, "notes") for r in _rows(
        "SELECT * FROM dsa_needs_assessments WHERE case_id = ? ORDER BY assessment_date DESC",
        (cid,))]
    case["recommendations"] = _rows(
        "SELECT * FROM dsa_recommendations WHERE case_id = ? ORDER BY id", (cid,))
    case["nmh"] = nmh_summary(cid)
    case["equipment"] = _rows("SELECT * FROM dsa_equipment WHERE case_id = ? ORDER BY id",
                              (cid,))
    case["exam_arrangements"] = _rows(
        "SELECT * FROM dsa_exam_arrangements WHERE case_id = ? ORDER BY id DESC", (cid,))
    case["adjustments"] = _adjustments(case)
    return case


def next_statuses(status) -> tuple:
    """Forward steps from ``status`` (any later one, so a step the student
    reports late is not blocked), and closing."""
    if status not in STATUSES or status == "closed":
        return ()
    return STATUSES[STATUSES.index(status) + 1:]


def set_status(actor, case_id, new_status, *, on_date=None, note="") -> None:
    _require_manager(actor)
    case = _case(case_id)
    if new_status not in next_statuses(case["status"]):
        raise ValueError(f"A case that is '{STATUS_LABELS.get(case['status'])}' cannot move "
                         f"to '{STATUS_LABELS.get(new_status, new_status)}'.")
    when = _iso(on_date, "date") or date.today().isoformat()
    column = STATUS_DATE_COLUMN[new_status]
    with transaction() as conn:
        conn.execute(f"UPDATE dsa_cases SET status = ?, {column} = ?, updated_at = ? "  # nosec B608
                     "WHERE case_id = ?", (new_status, when, _now(), case["case_id"]))
        conn.execute("INSERT INTO dsa_status_history (case_id, from_status, to_status, "
                     "changed_by, note) VALUES (?, ?, ?, ?, ?)",
                     (case["case_id"], case["status"], new_status, access.username(actor),
                      (note or "").strip() or None))
    _log("update", "dsa_case", case_id=case["case_id"], status=new_status)
    _notify(case["student_id"], "Your DSA case has been updated",
            f"Your Disabled Students' Allowances case is now: {STATUS_LABELS[new_status]} "
            f"(from {when}).\n\nContact disability services if this is not what you expected.")


def update_case(actor, case_id, *, funding_body=None, sfe_reference=None, notes=None) -> None:
    _require_manager(actor)
    case = _case(case_id)
    fields, values = [], []
    if funding_body is not None:
        if funding_body not in FUNDING_BODIES:
            raise ValueError("Choose the funding body.")
        fields.append("funding_body = ?")
        values.append(funding_body)
    if sfe_reference is not None:
        fields.append("sfe_reference = ?")
        values.append(sfe_reference.strip() or None)
    if notes is not None:
        fields.append("notes = ?")
        values.append(wellbeing_bus.seal_text(notes.strip()) if notes.strip() else None)
    if not fields:
        return
    with transaction() as conn:
        conn.execute(f"UPDATE dsa_cases SET {', '.join(fields)}, updated_at = ? "  # nosec B608
                     "WHERE case_id = ?", (*values, _now(), case["case_id"]))
    _log("update", "dsa_case", case_id=case["case_id"],
         fields=[f.split(" = ")[0] for f in fields])


def _advance(conn, case, target, actor, note) -> None:
    """Move the case forward to ``target`` if it is still before it."""
    if case["status"] == "closed" or STATUSES.index(case["status"]) >= STATUSES.index(target):
        return
    column = STATUS_DATE_COLUMN[target]
    conn.execute(f"UPDATE dsa_cases SET status = ?, {column} = ?, updated_at = ? "  # nosec B608
                 "WHERE case_id = ?", (target, date.today().isoformat(), _now(),
                                       case["case_id"]))
    conn.execute("INSERT INTO dsa_status_history (case_id, from_status, to_status, changed_by, "
                 "note) VALUES (?, ?, ?, ?, ?)",
                 (case["case_id"], case["status"], target, access.username(actor), note))


# ------------------------------------------------------------------ needs assessment

def book_assessment(actor, case_id, *, assessment_date, assessment_time="", centre="",
                    assessor="", mode="in person", notes="") -> int:
    _require_manager(actor)
    case = _case(case_id)
    when = _iso(assessment_date, "assessment date", required=True)
    if not (centre or "").strip() and not (assessor or "").strip():
        raise ValueError("Enter the assessment centre or the assessor.")
    with transaction() as conn:
        new_id = conn.execute(
            "INSERT INTO dsa_needs_assessments (case_id, centre, assessor, assessment_date, "
            "assessment_time, mode, notes, booked_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (case["case_id"], centre.strip() or None, assessor.strip() or None, when,
             (assessment_time or "").strip() or None, mode or "in person",
             wellbeing_bus.seal_text(notes.strip()) if notes and notes.strip() else None,
             access.username(actor))).lastrowid
        _advance(conn, case, "assessment_booked", actor, f"Needs assessment booked for {when}")
    _log("create", "dsa_needs_assessment", case_id=case["case_id"], id=new_id)
    _notify(case["student_id"], "Your DSA needs assessment",
            f"Your needs assessment is booked for {when}"
            f"{' at ' + assessment_time if assessment_time else ''}"
            f"{' with ' + assessor if assessor else ''}"
            f"{' (' + centre + ')' if centre else ''}.")
    return int(new_id)


def record_attendance(actor, assessment_id, attended: bool) -> None:
    _require_manager(actor)
    row = _one("SELECT * FROM dsa_needs_assessments WHERE id = ?", (int(assessment_id),))
    if not row:
        raise ValueError(f"Assessment #{assessment_id} was not found.")
    case = _case(row["case_id"])
    with transaction() as conn:
        conn.execute("UPDATE dsa_needs_assessments SET attended = ? WHERE id = ?",
                     (1 if attended else 0, row["id"]))
        if attended:
            _advance(conn, case, "assessed", actor, "Needs assessment attended")
    _log("update", "dsa_needs_assessment", id=row["id"], attended=bool(attended))


# ------------------------------------------------------------------ recommendations

def add_recommendation(actor, case_id, category, text) -> int:
    _require_manager(actor)
    case = _case(case_id)
    if category not in CATEGORIES:
        raise ValueError("Choose a category.")
    text = (text or "").strip()
    if len(text) < 3:
        raise ValueError("Describe the recommendation.")
    with transaction() as conn:
        new_id = conn.execute(
            "INSERT INTO dsa_recommendations (case_id, category, recommendation, created_by, "
            "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (case["case_id"], category, text, access.username(actor), _now(),
             _now())).lastrowid
    _log("create", "dsa_recommendation", case_id=case["case_id"], id=new_id)
    return int(new_id)


def set_recommendation_status(actor, rec_id, status) -> None:
    _require_manager(actor)
    if status not in RECOMMENDATION_STATUSES:
        raise ValueError("Unknown status.")
    with transaction() as conn:
        if not conn.execute("UPDATE dsa_recommendations SET status = ?, updated_at = ? "
                            "WHERE id = ?", (status, _now(), int(rec_id))).rowcount:
            raise ValueError(f"Recommendation #{rec_id} was not found.")
    _log("update", "dsa_recommendation", id=rec_id, status=status)


def adjustment_from_recommendation(actor, rec_id, accommodation_type, *, description=None,
                                   start_date=None, end_date=None) -> int:
    """Turn a reasonable-adjustment recommendation into an approved
    adjustment in the portal (and link it to the case); its id."""
    _require_manager(actor)
    if not access.may_decide(actor):
        raise PermissionError("Approving an adjustment needs a disability adviser or an "
                              "accommodation approver.")
    rec = _one("SELECT * FROM dsa_recommendations WHERE id = ?", (int(rec_id),))
    if not rec:
        raise ValueError(f"Recommendation #{rec_id} was not found.")
    if rec["category"] != "reasonable_adjustment":
        raise ValueError("Only a reasonable-adjustment recommendation becomes an adjustment "
                         "(exam arrangements are applied from their own tab).")
    if rec["accommodation_id"]:
        raise ValueError("This recommendation is already an adjustment.")
    case = _case(rec["case_id"])
    acc_id = wellbeing_bus.add_adjustment(
        case["student_id"], accommodation_type, (description or rec["recommendation"]).strip(),
        approved_by=access.username(actor), start_date=_iso(start_date, "start date"),
        end_date=_iso(end_date, "end date"), notes=f"DSA case #{case['case_id']}")
    with transaction() as conn:
        conn.execute("UPDATE dsa_recommendations SET accommodation_id = ?, status = 'in_place', "
                     "updated_at = ? WHERE id = ?", (acc_id, _now(), rec["id"]))
        conn.execute("INSERT OR IGNORE INTO dsa_case_adjustments (case_id, accommodation_id, "
                     "linked_by) VALUES (?, ?, ?)",
                     (case["case_id"], acc_id, access.username(actor)))
    _log("create", "dsa_adjustment", case_id=case["case_id"], accommodation_id=acc_id)
    _notify(case["student_id"], "A reasonable adjustment is now in place",
            f"From your DSA recommendations: {accommodation_type}. You can see it under "
            "My Support in Disability & Accessibility.")
    return int(acc_id)


def _adjustments(case) -> list[dict]:
    linked = {r["accommodation_id"] for r in _rows(
        "SELECT accommodation_id FROM dsa_case_adjustments WHERE case_id = ?",
        (case["case_id"],))}
    rows = wellbeing_bus.student_adjustments(case["student_id"])
    for row in rows:
        row["linked"] = row["id"] in linked
    return rows


def link_adjustment(actor, case_id, accommodation_id, *, linked=True) -> None:
    """Link (or unlink) one of the student's existing adjustments to the case."""
    _require_manager(actor)
    case = _case(case_id)
    ids = {r["id"] for r in wellbeing_bus.student_adjustments(case["student_id"])}
    if int(accommodation_id) not in ids:
        raise ValueError("That adjustment belongs to another student.")
    with transaction() as conn:
        if linked:
            conn.execute("INSERT OR IGNORE INTO dsa_case_adjustments (case_id, "
                         "accommodation_id, linked_by) VALUES (?, ?, ?)",
                         (case["case_id"], int(accommodation_id), access.username(actor)))
        else:
            conn.execute("DELETE FROM dsa_case_adjustments WHERE case_id = ? AND "
                         "accommodation_id = ?", (case["case_id"], int(accommodation_id)))
    _log("update", "dsa_case_adjustment", case_id=case["case_id"],
         accommodation_id=accommodation_id, linked=linked)


# ------------------------------------------------------------------ non-medical help

def add_nmh_support(actor, case_id, *, support_type, hours_allocated, worker_name="",
                    agency="", band="", start_date=None, end_date=None) -> int:
    _require_manager(actor)
    case = _case(case_id)
    if not (support_type or "").strip():
        raise ValueError("Choose the type of support.")
    try:
        hours = float(hours_allocated)
    except (TypeError, ValueError):
        raise ValueError("Hours allocated must be a number.") from None
    if hours <= 0:
        raise ValueError("Hours allocated must be more than 0.")
    with transaction() as conn:
        new_id = conn.execute(
            "INSERT INTO dsa_nmh_support (case_id, worker_name, agency, support_type, band, "
            "hours_allocated, start_date, end_date, created_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (case["case_id"], worker_name.strip() or None, agency.strip() or None,
             support_type.strip(), band or None, hours, _iso(start_date, "start date"),
             _iso(end_date, "end date"), access.username(actor))).lastrowid
    _log("create", "dsa_nmh_support", case_id=case["case_id"], id=new_id)
    return int(new_id)


def log_hours(actor, support_id, *, session_date, hours, notes="") -> dict:
    """Record hours used; returns ``{'id', 'used', 'remaining', 'over'}``.
    Hours beyond the allocation are recorded (the session happened) and
    flagged so staff ask the funding body for more."""
    _require_manager(actor)
    support = _one("SELECT * FROM dsa_nmh_support WHERE id = ?", (int(support_id),))
    if not support:
        raise ValueError(f"Support #{support_id} was not found.")
    try:
        hours = float(hours)
    except (TypeError, ValueError):
        raise ValueError("Hours must be a number.") from None
    if hours <= 0 or hours > MAX_SESSION_HOURS:
        raise ValueError(f"Hours must be between 0 and {MAX_SESSION_HOURS}.")
    when = _iso(session_date, "session date", required=True)
    if when > date.today().isoformat():
        raise ValueError("Log a session once it has happened.")
    with transaction() as conn:
        new_id = conn.execute(
            "INSERT INTO dsa_nmh_hours (support_id, session_date, hours, notes, logged_by) "
            "VALUES (?, ?, ?, ?, ?)", (support["id"], when, hours, (notes or "").strip() or None,
                                       access.username(actor))).lastrowid
    _log("create", "dsa_nmh_hours", support_id=support["id"], hours=hours)
    used = _used(support["id"])
    remaining = round(float(support["hours_allocated"]) - used, 2)
    return {"id": int(new_id), "used": used, "remaining": remaining, "over": remaining < 0}


def _used(support_id) -> float:
    row = _one("SELECT COALESCE(SUM(hours), 0) AS used FROM dsa_nmh_hours WHERE support_id = ?",
               (int(support_id),))
    return round(float(row["used"] if row else 0), 2)


def nmh_summary(case_id) -> list[dict]:
    out = []
    for row in _rows("SELECT * FROM dsa_nmh_support WHERE case_id = ? ORDER BY id",
                     (int(case_id),)):
        row["hours_used"] = _used(row["id"])
        row["hours_remaining"] = round(float(row["hours_allocated"]) - row["hours_used"], 2)
        row["over_allocation"] = row["hours_remaining"] < 0
        row["log"] = _rows("SELECT * FROM dsa_nmh_hours WHERE support_id = ? "
                           "ORDER BY session_date DESC, id DESC", (row["id"],))
        out.append(row)
    return out


def end_nmh_support(actor, support_id) -> None:
    _require_manager(actor)
    with transaction() as conn:
        conn.execute("UPDATE dsa_nmh_support SET status = 'ended', end_date = COALESCE("
                     "end_date, ?) WHERE id = ?", (date.today().isoformat(), int(support_id)))
    _log("update", "dsa_nmh_support", id=support_id, status="ended")


# ------------------------------------------------------------------ equipment

def add_equipment(actor, case_id, item, *, supplier="", notes="") -> int:
    _require_manager(actor)
    case = _case(case_id)
    if not (item or "").strip():
        raise ValueError("Enter the item.")
    with transaction() as conn:
        new_id = conn.execute(
            "INSERT INTO dsa_equipment (case_id, item, supplier, notes, created_by, created_at, "
            "updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (case["case_id"], item.strip(), supplier.strip() or None, notes.strip() or None,
             access.username(actor), _now(), _now())).lastrowid
    _log("create", "dsa_equipment", case_id=case["case_id"], id=new_id)
    return int(new_id)


_EQUIPMENT_DATES = {"ordered": "ordered_date", "delivered": "delivered_date",
                    "training_done": "training_date"}


def set_equipment_status(actor, equipment_id, status, *, on_date=None) -> None:
    _require_manager(actor)
    if status not in EQUIPMENT_STATUSES:
        raise ValueError("Unknown equipment status.")
    when = _iso(on_date, "date") or date.today().isoformat()
    column = _EQUIPMENT_DATES.get(status)
    extra = f", {column} = ?" if column else ""
    params = (status, _now(), *((when,) if column else ()), int(equipment_id))
    with transaction() as conn:
        if not conn.execute(f"UPDATE dsa_equipment SET status = ?, updated_at = ?{extra} "  # nosec B608
                            "WHERE id = ?", params).rowcount:
            raise ValueError(f"Equipment #{equipment_id} was not found.")
    _log("update", "dsa_equipment", id=equipment_id, status=status)


# ------------------------------------------------------------------ exam access arrangements

def recommend_exam_arrangements(actor, case_id, *, extra_percent=0, separate_room=False,
                                rest_breaks=False, reader=False, scribe=False,
                                assistive_technology="", other="", valid_from=None,
                                valid_to=None) -> int:
    _require_manager(actor)
    case = _case(case_id)
    try:
        extra = int(extra_percent or 0)
    except (TypeError, ValueError):
        raise ValueError("Extra time must be a whole percentage.") from None
    if not 0 <= extra <= 100:
        raise ValueError("Extra time must be between 0% and 100%.")
    start, end = _iso(valid_from, "start date"), _iso(valid_to, "end date")
    if start and end and end < start:
        raise ValueError("The end date is before the start date.")
    text = wellbeing_bus.describe_exam_arrangements(
        extra_percent=extra, separate_room=separate_room, reader=reader, scribe=scribe,
        assistive_technology=assistive_technology, rest_breaks=rest_breaks, other=other)
    if not text:
        raise ValueError("Choose at least one arrangement.")
    with transaction() as conn:
        new_id = conn.execute(
            "INSERT INTO dsa_exam_arrangements (case_id, student_id, extra_percent, "
            "separate_room, rest_breaks, reader, scribe, assistive_technology, other, "
            "valid_from, valid_to, created_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (case["case_id"], case["student_id"], extra, int(bool(separate_room)),
             int(bool(rest_breaks)), int(bool(reader)), int(bool(scribe)),
             (assistive_technology or "").strip() or None, (other or "").strip() or None,
             start, end, access.username(actor))).lastrowid
    _log("create", "dsa_exam_arrangement", case_id=case["case_id"], id=new_id)
    return int(new_id)


def arrangement_text(row: dict) -> str:
    return wellbeing_bus.describe_exam_arrangements(
        extra_percent=row.get("extra_percent") or 0, separate_room=bool(row.get("separate_room")),
        reader=bool(row.get("reader")), scribe=bool(row.get("scribe")),
        assistive_technology=row.get("assistive_technology") or "",
        rest_breaks=bool(row.get("rest_breaks")), other=row.get("other") or "")


def apply_exam_arrangements(actor, arrangement_id) -> int:
    """Make the arrangements live: an approved ``accommodations`` row that
    accommodation_bus carries to every exam. Returns its id."""
    _require_manager(actor)
    if not access.may_decide(actor):
        raise PermissionError("Applying exam arrangements needs a disability adviser or an "
                              "accommodation approver.")
    row = _one("SELECT * FROM dsa_exam_arrangements WHERE id = ?", (int(arrangement_id),))
    if not row:
        raise ValueError(f"Arrangement #{arrangement_id} was not found.")
    if row["status"] != "recommended":
        raise ValueError(f"These arrangements are already {row['status']}.")
    acc_id = wellbeing_bus.add_adjustment(
        row["student_id"], EXAM_TYPE, arrangement_text(row), approved_by=access.username(actor),
        start_date=row["valid_from"], end_date=row["valid_to"],
        notes=f"DSA case #{row['case_id']} exam access arrangements")
    with transaction() as conn:
        conn.execute("UPDATE dsa_exam_arrangements SET status = 'applied', accommodation_id = ?, "
                     "applied_by = ?, applied_at = ? WHERE id = ?",
                     (acc_id, access.username(actor), _now(), row["id"]))
        conn.execute("INSERT OR IGNORE INTO dsa_case_adjustments (case_id, accommodation_id, "
                     "linked_by) VALUES (?, ?, ?)",
                     (row["case_id"], acc_id, access.username(actor)))
    _log("update", "dsa_exam_arrangement", id=row["id"], accommodation_id=acc_id)
    _notify(row["student_id"], "Your exam access arrangements are in place",
            f"From your DSA needs assessment: {arrangement_text(row)}. They apply to your "
            "exams from now on; exams staff see the arrangements, not the reason.")
    return int(acc_id)


def withdraw_exam_arrangements(actor, arrangement_id, reason) -> None:
    _require_manager(actor)
    reason = (reason or "").strip()
    if len(reason) < 5:
        raise ValueError("Give a reason for withdrawing them.")
    row = _one("SELECT * FROM dsa_exam_arrangements WHERE id = ?", (int(arrangement_id),))
    if not row:
        raise ValueError(f"Arrangement #{arrangement_id} was not found.")
    if row["status"] == "withdrawn":
        raise ValueError("These arrangements are already withdrawn.")
    if row["accommodation_id"]:
        wellbeing_bus.withdraw_adjustment(row["accommodation_id"], reason=reason,
                                          by=access.username(actor))
    with transaction() as conn:
        conn.execute("UPDATE dsa_exam_arrangements SET status = 'withdrawn', "
                     "withdrawn_reason = ? WHERE id = ?", (reason, row["id"]))
    _log("update", "dsa_exam_arrangement", id=row["id"], status="withdrawn")
    if row["accommodation_id"]:
        _notify(row["student_id"], "Your exam access arrangements have changed",
                f"Your exam access arrangements ({arrangement_text(row)}) have been withdrawn: "
                f"{reason}")


# ------------------------------------------------------------------ reporting

def statistics(actor) -> dict:
    access.require_staff(actor)
    counts = {s: 0 for s in STATUSES}
    for row in _rows("SELECT status, COUNT(*) AS n FROM dsa_cases GROUP BY status"):
        counts[row["status"]] = row["n"]
    over = sum(1 for r in _rows("SELECT id, hours_allocated FROM dsa_nmh_support "
                                "WHERE status = 'active'")
               if _used(r["id"]) > float(r["hours_allocated"]))
    return {"by_status": counts, "open": sum(v for k, v in counts.items() if k != "closed"),
            "nmh_over_allocation": over}
