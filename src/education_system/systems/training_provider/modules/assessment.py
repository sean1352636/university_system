"""Assessment results and certificates.

Rules:

* a result is for a learner with a place on the session, dated on or after
  the session starts and not in the future; the assessor can't be marking
  their own attempt twice - attempts are numbered automatically;
* the outcome follows the course pass mark when a score is given (Pass at or
  above it, otherwise Fail); an accredited course that needs full attendance
  can't be passed without it;
* a certificate needs a Pass (accredited courses) or an Attended booking
  (non-accredited); its number and expiry (from the course validity) are set
  automatically; one current certificate per learner per session;
* revoking a certificate needs a reason; renewal is due 90 days before it
  expires.
"""

from __future__ import annotations

from datetime import date, timedelta

from education_system.systems.training_provider.core import dates
from education_system.systems.training_provider.core import records as r
from education_system.systems.training_provider.core.records import (
    Field,
    RecordType,
    ValidationError,
)
from education_system.systems.training_provider.infrastructure import database as db
from education_system.systems.training_provider.modules import courses, learners, sessions

METHODS = ("Written exam", "Online test", "Practical", "Observation", "Portfolio",
           "Professional discussion")
OUTCOMES = ("Pass", "Merit", "Distinction", "Fail", "Absent")
PASSES = ("Pass", "Merit", "Distinction")
CERT_STATUSES = ("Issued", "Revoked", "Superseded")
RENEW_DAYS = 90


def _session_course(session_id) -> tuple[dict, dict]:
    session = r.get(sessions.SESSIONS, int(session_id)) if session_id else None
    if session is None:
        raise ValidationError("Choose the session.")
    return session, r.get(courses.COURSES, session["course_id"])


def _check_result(values: dict, old: dict | None) -> None:
    merged = {**(old or {}), **values}
    session, course = _session_course(merged.get("session_id"))
    booking = sessions.booking_for(int(merged["learner_id"]), session["id"])
    if booking is None or booking["status"] not in sessions.PLACE_TAKEN:
        raise ValidationError("That learner has no place on this session.")
    on = r.to_date(merged.get("assessed_on"))
    start = r.to_date(session["start_date"])
    if on and start and on < start:
        raise ValidationError("The assessment can't be before the session starts.")
    if on and on > date.today():
        raise ValidationError("The assessment date can't be in the future.")
    score = merged.get("score")
    if score is not None and not 0 <= float(score) <= 100:
        raise ValidationError("The score is a percentage, 0-100.")
    if merged.get("outcome") in (None, ""):
        if score is None:
            raise ValidationError("Give the score or the outcome.")
        mark = course.get("pass_mark")
        if mark is None:
            raise ValidationError(f"{course['code']} has no pass mark: choose the outcome.")
        values["outcome"] = "Pass" if float(score) >= float(mark) else "Fail"
    outcome = values.get("outcome", merged.get("outcome"))
    if outcome in PASSES and course["kind"] == courses.KINDS[0] and \
            course.get("full_attendance") and \
            not sessions.full_attendance(booking["learner_id"], session["id"]):
        raise ValidationError(f"{course['code']} needs full attendance to pass, and the "
                              "register shows days missed (or not yet marked).")
    if merged.get("assessor_id"):
        assessor = r.get(courses.TRAINERS, int(merged["assessor_id"]))
        if course["kind"] == courses.KINDS[0] and not assessor.get("assessor_qualified"):
            raise ValidationError(f"{assessor['name']} isn't recorded as a qualified "
                                  "assessor.")
    if old is None:
        with db.connect() as conn:
            n = conn.execute("SELECT COUNT(*) FROM results WHERE learner_id = ? AND "
                             "session_id = ?", (merged["learner_id"], session["id"])).fetchone()[0]
            passed = conn.execute(
                "SELECT 1 FROM results WHERE learner_id = ? AND session_id = ? AND outcome IN "
                "('Pass', 'Merit', 'Distinction')",
                (merged["learner_id"], session["id"])).fetchone()
        if passed:
            raise ValidationError("The learner has already passed this assessment.")
        values["attempt"] = n + 1


RESULTS = RecordType(
    key="results", title="Results", singular="result", order_by="assessed_on DESC, id DESC",
    check=_check_result, filters=("outcome", "method"),
    after_commit=learners.platform_hook("result_saved"),
    describe=lambda row: f"{sessions.who(row)}: {row.get('outcome')}",
    computed=(("Session",
               lambda row: sessions.session_label(r.get(sessions.SESSIONS,
                                                        row["session_id"]) or {})),),
    fields=(
        Field("learner_id", "Learner", "learner", required=True),
        Field("session_id", "Session", "ref", ref="sessions", required=True),
        Field("assessed_on", "Assessed", "date", required=True),
        Field("method", "Method", "choice", METHODS, required=True, default="Practical"),
        Field("score", "Score %", "number"),
        Field("outcome", "Outcome", "choice", OUTCOMES, help="Blank: from the pass mark"),
        Field("attempt", "Attempt", "int", form=False),
        Field("assessor_id", "Assessor", "ref", ref="trainers", on_delete="SET NULL"),
        Field("feedback", "Feedback", "long", listed=False),
    ),
)


def latest_result(learner_id: int, session_id: int) -> dict | None:
    rows = r.list_records(RESULTS, equals={"learner_id": learner_id, "session_id": session_id})
    return rows[0] if rows else None


# ── certificates ────────────────────────────────────────────────────

def _check_certificate(values: dict, old: dict | None) -> None:
    merged = {**(old or {}), **values}
    session, course = _session_course(merged.get("session_id"))
    learner_id = int(merged["learner_id"])
    issued = r.to_date(merged.get("issued_on")) or date.today()
    if issued > date.today():
        raise ValidationError("A certificate can't be issued in the future.")
    if old is None or any(k in values and values[k] != old.get(k)
                          for k in ("learner_id", "session_id")):
        if not eligible(learner_id, session["id"]):
            raise ValidationError(f"{course['code']} is accredited: the learner needs a Pass "
                                  "result first." if course["kind"] == courses.KINDS[0] else
                                  "The learner's booking must be marked Attended first.")
        with db.connect() as conn:
            dupe = conn.execute("SELECT cert_no FROM certificates WHERE learner_id = ? AND "
                                "session_id = ? AND status = 'Issued' AND id IS NOT ?",
                                (learner_id, session["id"], (old or {}).get("id"))).fetchone()
        if dupe:
            raise ValidationError(f"Certificate {dupe[0]} is already issued for this.")
    if not merged.get("issued_on"):
        values["issued_on"] = issued.isoformat()
    months = int(course.get("valid_months") or 0)
    if merged.get("expires_on") in (None, "") and months:
        values["expires_on"] = dates.add_months(issued, months).isoformat()
    if merged.get("status") == "Revoked" and not merged.get("revoke_reason"):
        raise ValidationError("Give the reason the certificate was revoked.")
    if old is None:
        with db.connect() as conn:
            n = conn.execute("SELECT COUNT(*) + 1 FROM certificates WHERE cert_no LIKE ?",
                             (f"TP-{issued.year}-%",)).fetchone()[0]
            while conn.execute("SELECT 1 FROM certificates WHERE cert_no = ?",
                               (f"TP-{issued.year}-{n:05d}",)).fetchone():
                n += 1
        values["cert_no"] = f"TP-{issued.year}-{n:05d}"


def eligible(learner_id: int, session_id: int) -> bool:
    """Whether the learner qualifies for a certificate for the session."""
    session = r.get(sessions.SESSIONS, session_id)
    course = r.get(courses.COURSES, session["course_id"]) if session else None
    if course is None:
        return False
    if course["kind"] == courses.KINDS[0]:
        result = latest_result(learner_id, session_id)
        return result is not None and result["outcome"] in PASSES
    booking = sessions.booking_for(learner_id, session_id)
    return booking is not None and booking["status"] == "Attended"


def renewal_due(row: dict) -> date | None:
    until = r.to_date(row.get("expires_on"))
    return until - timedelta(days=RENEW_DAYS) if until else None


def validity(row: dict) -> str:
    until = r.to_date(row.get("expires_on"))
    if row.get("status") != "Issued":
        return row.get("status") or ""
    if until is None:
        return "Doesn't expire"
    if until < date.today():
        return "EXPIRED"
    if renewal_due(row) <= date.today():
        return f"Renew by {dates.uk(until)}"
    return "Valid"


CERTIFICATES = RecordType(
    key="certificates", title="Certificates", singular="certificate",
    order_by="issued_on DESC, id DESC", check=_check_certificate, filters=("status",),
    after_commit=learners.platform_hook("certificate_saved"),
    describe=lambda row: f"{row.get('cert_no')} {sessions.who(row)}",
    computed=(("Course",
               lambda row: sessions.session_label(r.get(sessions.SESSIONS,
                                                        row["session_id"]) or {})),
              ("Validity", validity)),
    fields=(
        Field("cert_no", "Certificate", form=False),
        Field("learner_id", "Learner", "learner", required=True),
        Field("session_id", "Session", "ref", ref="sessions", required=True),
        Field("issued_on", "Issued", "date"),
        Field("expires_on", "Expires", "date", help="Blank: from the course validity"),
        Field("awarding_body_ref", "Awarding body certificate no.", listed=False),
        Field("status", "Status", "choice", CERT_STATUSES, required=True, default="Issued"),
        Field("revoke_reason", "Revocation reason", listed=False),
    ),
)


def expiring(within_days: int = 90) -> list[dict]:
    horizon = date.today() + timedelta(days=within_days)
    out = []
    for c in r.list_records(CERTIFICATES, equals={"status": "Issued"}):
        until = r.to_date(c.get("expires_on"))
        if until and until <= horizon:
            out.append(c)
    return sorted(out, key=lambda c: c["expires_on"])


def issue_due(session_id: int, *, actor: str = "system") -> int:
    """Issue certificates to every eligible learner on a session who has none."""
    issued = 0
    for b in sessions.session_bookings(session_id):
        try:
            r.save(CERTIFICATES, {"learner_id": b["learner_id"], "session_id": session_id},
                   actor=actor)
            issued += 1
        except ValidationError:
            continue
    return issued
