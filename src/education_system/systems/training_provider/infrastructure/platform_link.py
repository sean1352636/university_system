"""Training Provider's screens drive the platform for learners a linked
apprenticeship provider or FE college sent.

Each function is a record type's ``after_commit`` hook: it runs once the
save has committed and returns lines for the person who saved (the form
shows them). If the platform call fails, the record still stands; the
failure becomes a notice and is logged (see ``core.records``).

* **Training Requests**: *Declined* or *Withdrawn* (with the reason) goes
  back to the sender.
* **Bookings**: booking a requested learner on a session (or a place coming
  up off the waiting list) marks the request *Booked* and tells the
  sender; *Did not attend* goes back too.
* **Results**: a fail or absence goes back (*Not passed*).
* **Certificates**: a certificate goes back - an apprenticeship provider
  gets it as off-the-job hours awaiting approval, an FE college on the
  learner's prior attainment.

Records with no platform link are untouched. The outgoing links (to an
apprenticeship, to FE) are the platform's own boards, so nothing here
drives them.
"""

from __future__ import annotations

from datetime import date

from education_system.systems.training_provider.core import records as r


def _service():
    from education_system.platform.cross_system import training_provider_requests
    return training_provider_requests


def _session_and_course(session_id) -> tuple[dict, dict]:
    from education_system.systems.training_provider.modules import courses, sessions
    session = r.get(sessions.SESSIONS, int(session_id)) or {}
    course = r.get(courses.COURSES, session["course_id"]) if session else None
    return session, course or {}


def _set(request: dict, **values) -> None:
    from education_system.systems.training_provider.modules import requests
    r.save(requests.TRAINING_REQUESTS, values, record_id=request["id"], actor="platform")


def _booked_request(learner_id: int, session_id: int) -> dict | None:
    """The learner's linked request booked on this session."""
    from education_system.systems.training_provider.modules import requests
    rows = [x for x in requests.linked_for(learner_id, ("Booked",))
            if x.get("session_id") == session_id]
    return rows[0] if rows else None


def _pick(learner_id: int, course_id: int) -> dict | None:
    """The open request a booking on *course_id* answers: one for that
    course, else the oldest not yet tied to a course."""
    from education_system.systems.training_provider.modules import requests
    open_rows = requests.linked_for(learner_id)
    for row in open_rows:
        if row.get("course_id") == course_id:
            return row
    return next((row for row in open_rows if not row.get("course_id")), None)


def _book(request: dict, booking: dict) -> list[str]:
    session, course = _session_and_course(booking["session_id"])
    _service().booked(request["transition_id"], local_student_id=str(booking["learner_id"]),
                      start_date=session.get("start_date") or date.today().isoformat(),
                      consent=bool(request.get("consent_to_share")))
    _set(request, status="Booked", session_id=booking["session_id"],
         course_id=request.get("course_id") or course.get("id"))
    return [f"{request.get('sender') or 'The sender'} has been told the learner is booked "
            f"on {course.get('title') or 'the course'} ({session.get('start_date')})."]


def _outcome(request: dict, outcome: dict, status: str) -> list[str]:
    out = _service().record_outcome(request["transition_id"], outcome)
    _set(request, status=status)
    return out


# ── hooks ────────────────────────────────────────────────────────────

def request_saved(row: dict, old: dict | None) -> list[str] | None:
    tid = row.get("transition_id")
    if not tid or old is None or row.get("status") == old.get("status"):
        return None
    why = (row.get("decision_reason") or "").strip()
    sender = row.get("sender") or "The sender"
    if row.get("status") == "Declined":
        _service().decline(tid, reason=why)
        return [f"{sender} has been told the request was declined."]
    if row.get("status") == "Withdrawn":
        _service().withdraw(tid, reason=why or "Request withdrawn")
        return [f"{sender} has been told the request was withdrawn."]
    return None


def booking_saved(row: dict, old: dict | None) -> list[str] | None:
    from education_system.systems.training_provider.modules import requests, sessions
    out: list[str] = []
    status, was = row.get("status"), (old or {}).get("status")
    learner_id, session_id = int(row["learner_id"]), int(row["session_id"])
    if status != was or (old or {}).get("session_id") != session_id:
        if status in ("Booked", "Waiting list"):
            session, course = _session_and_course(session_id)
            request = _pick(learner_id, course.get("id"))
            if request is not None and status == "Booked":
                out += _book(request, row)
            elif request is not None and request["status"] != "Waiting list":
                _set(request, status="Waiting list", session_id=session_id,
                     course_id=request.get("course_id") or course.get("id"))
                out.append("The request is on the waiting list for this session; the "
                           "sender is told when a place comes up.")
        elif status == "Did not attend":
            request = _booked_request(learner_id, session_id)
            if request is not None:
                session, course = _session_and_course(session_id)
                out += _outcome(request, {"kind": "did_not_attend",
                                          "course": course.get("title"),
                                          "outcome": "did not attend",
                                          "on": session.get("start_date")}, "Did not attend")
    # A cancellation may have moved a requested learner off the waiting list
    # (``sessions._promote`` does it inside the save, with no hook of its own).
    for request in r.list_records(requests.TRAINING_REQUESTS,
                                  equals={"status": "Waiting list"}):
        if not request.get("transition_id") or not request.get("session_id"):
            continue
        place = sessions.booking_for(int(request["learner_id"]), int(request["session_id"]))
        if place and place.get("status") == "Booked" and place.get("id") != row.get("id"):
            out += _book(request, place)
    return out or None


def result_saved(row: dict, old: dict | None) -> list[str] | None:
    if row.get("outcome") not in ("Fail", "Absent") or \
            (old or {}).get("outcome") == row.get("outcome"):
        return None
    request = _booked_request(int(row["learner_id"]), int(row["session_id"]))
    if request is None:
        return None
    _session, course = _session_and_course(row["session_id"])
    return _outcome(request, {"kind": "result", "course": course.get("title"),
                              "outcome": "not passed" if row["outcome"] == "Fail"
                              else "absent from the assessment",
                              "on": row.get("assessed_on")}, "Not passed")


def certificate_saved(row: dict, old: dict | None) -> list[str] | None:
    if old is not None or row.get("status") != "Issued":
        return None
    from education_system.systems.training_provider.modules import requests
    learner_id, session_id = int(row["learner_id"]), int(row["session_id"])
    request = _booked_request(learner_id, session_id) or next(
        (x for x in requests.linked_for(learner_id, ("Not passed",))
         if x.get("session_id") == session_id), None)
    if request is None:
        return None
    _session, course = _session_and_course(session_id)
    return _outcome(request, {
        "kind": "certificate", "course": course.get("title"), "level": course.get("level")
        if course.get("level") not in (None, "", "Not levelled") else None,
        "awarding_body": course.get("awarding_body"),
        "guided_hours": course.get("guided_hours"), "cert_no": row.get("cert_no"),
        "issued_on": row.get("issued_on"), "expires_on": row.get("expires_on")},
        "Certificated")


__all__ = ["request_saved", "booking_saved", "result_saved", "certificate_saved"]
