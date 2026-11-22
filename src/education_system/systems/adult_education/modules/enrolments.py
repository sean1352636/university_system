"""Joining and attending: enquiries, enrolments, fees, attendance and assessments.

Rules:

* an archived learner can't be enrolled, nor enrolled twice on one class;
* enrolling on a full class puts the learner on the waiting list instead;
  when a place frees up the first on the waiting list is moved in;
* enrolling moves a learner from Enquiry to Active;
* the fee due defaults from the course fee and the funding outcome (fully
  funded pays nothing; a concession halves a co-funded fee);
* withdrawing needs a date and reason; completing needs an outcome; a
  certificate is only for an achieved outcome;
* a refund can't exceed what's been paid;
* an attendance mark is for an enrolled learner, on a date the class runs,
  once per learner per session.
"""

from __future__ import annotations

from datetime import date

from education_system.systems.adult_education.core import records as r
from education_system.systems.adult_education.core.records import Field, RecordType, ValidationError
from education_system.systems.adult_education.infrastructure import database as db
from education_system.systems.adult_education.modules import courses, funding, learners

ENROL_STATUSES = ("Enrolled", "Waiting list", "Withdrawn", "Completed", "Transferred")
OPEN_STATUSES = ("Enrolled", "Waiting list")
OUTCOMES = ("Pending", "Achieved", "Partially achieved", "Not achieved")
FUNDING = (*funding.OUTCOMES[:3], "Full fee (not funded)")
CONCESSIONS = ("None", "On benefits", "Low income", "Over 60", "Staff")
MARKS = ("Present", "Late", "Authorised absence", "Unauthorised absence")
PRESENT = frozenset({"Present", "Late"})


def _today() -> str:
    return date.today().isoformat()


def _check_enquiry(values: dict, old: dict | None) -> None:
    learners.check_email(values)
    learners.check_phone(values)
    merged = {**(old or {}), **values}
    if not (merged.get("email") or merged.get("phone")):
        raise ValidationError("Give at least a phone number or an e-mail address.")
    if merged.get("status") == "Closed" and not merged.get("closed_reason"):
        raise ValidationError("Say why the enquiry was closed.")


def _follow_up_flag(row: dict) -> str:
    due = r.to_date(row.get("follow_up"))
    if row.get("status") in ("Enrolled", "Closed") or not due:
        return ""
    return "Overdue" if due < date.today() else ("Today" if due == date.today() else "")


ENQUIRIES = RecordType(
    key="enquiries", title="Enquiries", singular="enquiry",
    order_by="status, follow_up", check=_check_enquiry, filters=("status", "source"),
    computed=(("Follow-up", _follow_up_flag),),
    describe=lambda row: f"{row.get('name')} ({row.get('received_on')})",
    fields=(
        Field("name", "Name", required=True),
        Field("email", "E-mail"),
        Field("phone", "Phone"),
        Field("course_id", "Interested in", "ref", ref="courses"),
        Field("interest", "Or describe interest", listed=False),
        Field("received_on", "Received", "date", required=True, default=_today),
        Field("source", "Source", "choice", ("Website", "Phone", "Walk-in", "Referral",
                                             "Event", "Social media")),
        Field("status", "Status", "choice", ("New", "Contacted", "Booked on IAG",
                                             "Enrolled", "Closed"),
              required=True, default="New"),
        Field("follow_up", "Follow up by", "date"),
        Field("closed_reason", "Closed because", listed=False),
        Field("notes", "Notes", "long", listed=False),
    ),
)


# ── enrolments ───────────────────────────────────────────────────────

def _class_and_course(class_id: int) -> tuple[dict, dict]:
    klass = r.get(courses.CLASSES, int(class_id))
    if klass is None:
        raise ValidationError("Choose the class.")
    return klass, r.get(courses.COURSES, klass["course_id"]) or {}


def default_fee(course_fee: float | None, funding_choice: str | None,
                concession: str | None) -> float:
    fee = float(course_fee or 0)
    if funding_choice == funding.FULLY:
        return 0.0
    if funding_choice == funding.CO and concession not in (None, "", "None"):
        return round(fee / 2, 2)
    return fee


def _check_enrolment(values: dict, old: dict | None) -> None:
    merged = {**(old or {}), **values}
    learner = r.get(learners.LEARNERS, int(merged["learner_id"]))
    klass, course = _class_and_course(merged["class_id"])
    status, was = merged.get("status"), (old or {}).get("status")
    if old is None:
        if learner is None or learner["status"] == "Archived":
            raise ValidationError("This learner is archived. Restore them before enrolling.")
        if klass["status"] in ("Completed", "Cancelled"):
            raise ValidationError(f"That class is {klass['status'].lower()}.")
        with db.connect() as conn:
            dup = conn.execute(
                "SELECT status FROM enrolments WHERE learner_id = ? AND class_id = ? AND "
                "status IN ('Enrolled', 'Waiting list', 'Completed')",
                (merged["learner_id"], merged["class_id"])).fetchone()
            if dup:
                raise ValidationError(f"The learner is already on this class ({dup[0]}).")
            full = courses.enrolled_count(conn, klass["id"]) >= (klass["capacity"] or 0)
        if status == "Enrolled" and full:
            values["status"] = status = "Waiting list"
        if not merged.get("funding"):
            outcome = funding.latest_outcome(learner["id"])
            values["funding"] = outcome if outcome in FUNDING else "Full fee (not funded)"
        if merged.get("fee_due") in (None, ""):
            values["fee_due"] = default_fee(course.get("fee"), values.get("funding") or
                                            merged.get("funding"), merged.get("concession"))
    elif status == "Enrolled" and was == "Waiting list":
        with db.connect() as conn:
            if courses.enrolled_count(conn, klass["id"]) >= (klass["capacity"] or 0):
                raise ValidationError("The class is still full.")
    if status == "Withdrawn":
        values.setdefault("withdrawn_on", merged.get("withdrawn_on") or _today())
        if not merged.get("withdrawal_reason"):
            raise ValidationError("Give the reason for withdrawing.")
    if status == "Completed" and merged.get("outcome") in (None, "Pending"):
        raise ValidationError("Record the outcome (achieved or not) before completing.")
    if merged.get("certificate_issued") and merged.get("outcome") != "Achieved":
        raise ValidationError("A certificate is only issued for an achieved outcome.")
    enrolled = r.to_date(r.parse_date(merged.get("enrolled_on")))
    left = r.to_date(r.parse_date(values.get("withdrawn_on") or merged.get("withdrawn_on")))
    if enrolled and left and left < enrolled:
        raise ValidationError("Withdrawal can't be before enrolment.")


def _after_enrolment(conn, row: dict, old: dict | None) -> None:
    if row["status"] == "Enrolled":
        learners.set_status(conn, row["learner_id"], "Active", only_if="Enquiry")
    left = (old or {}).get("status") == "Enrolled" and row["status"] in ("Withdrawn",
                                                                         "Transferred")
    if left:   # a place freed up: move the longest-waiting learner in
        nxt = conn.execute("SELECT id, learner_id FROM enrolments WHERE class_id = ? AND "
                           "status = 'Waiting list' ORDER BY enrolled_on, id LIMIT 1",
                           (row["class_id"],)).fetchone()
        if nxt:
            conn.execute("UPDATE enrolments SET status = 'Enrolled', updated_at = "
                         "datetime('now') WHERE id = ?", (nxt[0],))
            learners.set_status(conn, nxt[1], "Active", only_if="Enquiry")
            conn.execute("INSERT INTO history (actor, record_type, record_id, learner_id, "
                         "action, summary) VALUES ('system', 'enrolments', ?, ?, 'updated', "
                         "'Moved off the waiting list into a freed place')", (nxt[0], nxt[1]))


def paid(enrolment_id: int) -> float:
    with db.connect() as conn:
        row = conn.execute("SELECT COALESCE(SUM(CASE WHEN kind = 'Refund' THEN -amount "
                           "ELSE amount END), 0) FROM payments WHERE enrolment_id = ?",
                           (enrolment_id,)).fetchone()
    return float(row[0])


def balance(row: dict) -> float:
    if row.get("status") in ("Waiting list",):
        return 0.0
    return round(float(row.get("fee_due") or 0) - paid(row["id"]), 2)


def attendance_rate(row: dict) -> float | None:
    with db.connect() as conn:
        marks = [m[0] for m in conn.execute(
            "SELECT mark FROM attendance WHERE learner_id = ? AND class_id = ?",
            (row["learner_id"], row["class_id"]))]
    return round(100 * sum(m in PRESENT for m in marks) / len(marks)) if marks else None


def _bal(row: dict) -> str:
    b = balance(row)
    return f"£{b:,.2f}" if b else ""


def _att(row: dict) -> str:
    rate = attendance_rate(row)
    if rate is None:
        return ""
    return f"{rate}%" + (" - low, overdue for a check-in" if rate < 80 and
                         row.get("status") == "Enrolled" else "")


def enrolment_label(row: dict) -> str:
    klass = r.get(courses.CLASSES, row["class_id"]) if row.get("class_id") else None
    return (f"{row.get('learner_name') or ''}: "
            f"{courses.class_label(klass) if klass else 'class'} ({row.get('status')})")


ENROLMENTS = RecordType(
    key="enrolments", title="Enrolments", singular="enrolment",
    order_by="enrolled_on DESC, id DESC", check=_check_enrolment,
    after_save=_after_enrolment, filters=("status", "funding", "outcome"),
    after_commit=learners.platform_hook("enrolment_saved"),
    describe=enrolment_label,
    computed=(("Balance", _bal), ("Attendance", _att)),
    fields=(
        Field("learner_id", "Learner", "learner", required=True),
        Field("class_id", "Class", "ref", ref="classes", required=True),
        Field("enrolled_on", "Enrolled", "date", required=True, default=_today),
        Field("status", "Status", "choice", ENROL_STATUSES, required=True, default="Enrolled",
              help="A full class puts the learner on the waiting list"),
        Field("funding", "Funding", "choice", FUNDING,
              help="Left blank: the learner's latest funding assessment"),
        Field("concession", "Concession", "choice", CONCESSIONS, default="None",
              listed=False),
        Field("fee_due", "Fee due", "money",
              help="Left blank: worked out from the course fee and funding"),
        Field("outcome", "Outcome", "choice", OUTCOMES, required=True, default="Pending"),
        Field("certificate_issued", "Certificate issued", "date", listed=False),
        Field("withdrawn_on", "Withdrawn", "date", listed=False),
        Field("withdrawal_reason", "Withdrawal reason", listed=False),
    ),
)


def _enrolment_learner(values: dict, old: dict | None) -> dict:
    eid = values.get("enrolment_id") or (old or {}).get("enrolment_id")
    row = r.get(ENROLMENTS, int(eid)) if eid else None
    if row is None:
        raise ValidationError("Choose the enrolment.")
    values["learner_id"] = row["learner_id"]
    return row


def _check_payment(values: dict, old: dict | None) -> None:
    enrolment = _enrolment_learner(values, old)
    merged = {**(old or {}), **values}
    amount = float(merged.get("amount") or 0)
    if amount <= 0:
        raise ValidationError("Enter an amount above £0.")
    if merged.get("kind") == "Refund":
        already = paid(enrolment["id"]) - (float(old["amount"]) if old and
                                           old.get("kind") != "Refund" else 0)
        if amount > already + 0.001:
            raise ValidationError(f"Only £{already:,.2f} has been paid, so a refund can't be "
                                  "more than that.")


PAYMENTS = RecordType(
    key="payments", title="Fees & Payments", singular="payment",
    order_by="paid_on DESC, id DESC", check=_check_payment, filters=("kind", "method"),
    describe=lambda row: f"{row.get('kind')} £{row.get('amount')}",
    fields=(
        Field("enrolment_id", "Enrolment", "ref", ref="enrolments", required=True),
        Field("learner_id", "Learner", "learner", form=False),
        Field("paid_on", "Date", "date", required=True, default=_today),
        Field("kind", "Type", "choice", ("Payment", "Instalment", "Refund"), required=True,
              default="Payment"),
        Field("amount", "Amount", "money", required=True),
        Field("method", "Method", "choice", ("Card", "Cash", "Bank transfer", "Direct debit",
                                             "Invoice to employer", "Learner Loan")),
        Field("reference", "Reference", listed=False),
    ),
)


def _check_mark(values: dict, old: dict | None) -> None:
    merged = {**(old or {}), **values}
    klass, _course = _class_and_course(merged["class_id"])
    on = r.to_date(r.parse_date(merged.get("session_date")))
    start, end = r.to_date(klass.get("start_date")), r.to_date(klass.get("end_date"))
    if on and ((start and on < start) or (end and on > end)):
        raise ValidationError("That date is outside the class's dates.")
    if on and on > date.today():
        raise ValidationError("Attendance can't be marked for a future session.")
    with db.connect() as conn:
        enrolled = conn.execute(
            "SELECT 1 FROM enrolments WHERE learner_id = ? AND class_id = ? AND status IN "
            "('Enrolled', 'Completed', 'Withdrawn')",
            (merged["learner_id"], merged["class_id"])).fetchone()
        if not enrolled:
            raise ValidationError("The learner isn't enrolled on that class.")
        dup = conn.execute("SELECT 1 FROM attendance WHERE learner_id = ? AND class_id = ? AND "
                           "session_date = ? AND id IS NOT ?",
                           (merged["learner_id"], merged["class_id"],
                            on.isoformat() if on else None, (old or {}).get("id"))).fetchone()
        if dup:
            raise ValidationError("That learner already has a mark for this session.")


ATTENDANCE = RecordType(
    key="attendance", title="Attendance Marks", singular="attendance mark",
    order_by="session_date DESC, id DESC", check=_check_mark, filters=("mark",),
    describe=lambda row: f"{row.get('session_date')} {row.get('mark')}",
    fields=(
        Field("class_id", "Class", "ref", ref="classes", required=True),
        Field("learner_id", "Learner", "learner", required=True),
        Field("session_date", "Session", "date", required=True, default=_today),
        Field("mark", "Mark", "choice", MARKS, required=True, default="Present"),
        Field("note", "Note"),
    ),
)


def register(class_id: int, on: date) -> list[dict]:
    """Learners due on the register for *class_id* on *on*, with any mark already made."""
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT e.learner_id, l.first_name || ' ' || l.last_name AS name, l.learner_ref, "
            "a.mark, a.id AS mark_id FROM enrolments e JOIN learners l ON l.id = e.learner_id "
            "LEFT JOIN attendance a ON a.learner_id = e.learner_id AND a.class_id = e.class_id "
            "AND a.session_date = ? WHERE e.class_id = ? AND e.status IN ('Enrolled', "
            "'Completed') ORDER BY l.last_name, l.first_name", (on.isoformat(), class_id))
        return [dict(x) for x in rows]


def save_register(class_id: int, on: date, marks: dict[int, str], *, actor: str) -> int:
    """Save a whole register (learner_id -> mark). Returns marks written."""
    existing = {x["learner_id"]: x["mark_id"] for x in register(class_id, on)}
    n = 0
    for learner_id, mark in marks.items():
        if not mark:
            continue
        r.save(ATTENDANCE, {"class_id": class_id, "learner_id": learner_id,
                            "session_date": on.isoformat(), "mark": mark},
               record_id=existing.get(learner_id), actor=actor)
        n += 1
    return n


def _check_assessment(values: dict, old: dict | None) -> None:
    _enrolment_learner(values, old)


ASSESSMENTS = RecordType(
    key="assessments", title="Assessments & Results", singular="assessment",
    order_by="assessed_on DESC, id DESC", check=_check_assessment,
    filters=("kind", "result"),
    describe=lambda row: f"{row.get('name')} ({row.get('result')})",
    fields=(
        Field("enrolment_id", "Enrolment", "ref", ref="enrolments", required=True,
              on_delete="CASCADE"),
        Field("learner_id", "Learner", "learner", form=False),
        Field("name", "Assessment", required=True),
        Field("kind", "Type", "choice", ("Initial", "Diagnostic", "Formative", "Summative",
                                         "Exam", "RARPA review"), required=True),
        Field("assessed_on", "Date", "date", default=_today),
        Field("result", "Result", "choice", ("Not yet assessed", "Pass", "Merit",
                                             "Distinction", "Fail", "Referred"),
              required=True, default="Not yet assessed"),
        Field("feedback", "Feedback", "long", listed=False),
    ),
)
