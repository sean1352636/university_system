"""Adult Education's screens drive the platform for adults FE College referred.

Each function is a record type's ``after_commit`` hook: it runs once the
save has committed and returns lines for the person who saved (the form
shows them). If the platform call fails, the record still stands; the
failure becomes a notice and is logged (see ``core.records``).

* **Referrals from FE College**: *Declined* or *Withdrawn* (with the reason)
  goes back to the college.
* **Enrolments**: enrolling a referred learner on a class completes their
  open referrals - the college sees *Enrolled*, and its FE place stays open.

Records with no platform link (a learner nobody referred, a referral
recorded by hand) are untouched. The outgoing links - to FE College and to
university - are the platform's own boards (Refer to FE College, University
Applications), so nothing here drives them.
"""

from __future__ import annotations

from datetime import date

from education_system.systems.adult_education.core import records as r


def _service():
    from education_system.platform.cross_system import adult_education_applications
    return adult_education_applications


def referral_saved(row: dict, old: dict | None) -> list[str] | None:
    tid = row.get("transition_id")
    if not tid or old is None or row.get("status") == old.get("status"):
        return None
    status, why = row.get("status"), (row.get("decision_reason") or "").strip()
    if status == "Declined":
        _service().decline(tid, reason=why)
        return ["FE College has been told the referral was declined."]
    if status == "Withdrawn":
        _service().withdraw(tid, reason=why or "Referral withdrawn")
        return ["FE College has been told the referral was withdrawn."]
    return None


def enrolment_saved(row: dict, old: dict | None) -> list[str] | None:
    if row.get("status") != "Enrolled" or (old or {}).get("status") == "Enrolled":
        return None
    from education_system.systems.adult_education.modules import courses, referrals
    open_refs = referrals.open_linked(int(row["learner_id"]))
    if not open_refs:
        return None
    today = date.today().isoformat()
    start = min(str(row.get("enrolled_on") or today)[:10], today)
    klass = r.get(courses.CLASSES, int(row["class_id"])) or {}
    out: list[str] = []
    for ref in open_refs:
        _service().enrol(ref["transition_id"], local_student_id=str(row["learner_id"]),
                         start_date=start, consent=bool(ref.get("consent_to_share")))
        r.save(referrals.FE_REFERRALS,
               {"status": "Enrolled", "course_id": ref.get("course_id")
                or klass.get("course_id")}, record_id=ref["id"], actor="platform")
        out.append(f"{ref.get('college') or 'FE College'} has been told the learner "
                   f"enrolled (referral for {ref.get('course')}).")
    return out


__all__ = ["referral_saved", "enrolment_saved"]
