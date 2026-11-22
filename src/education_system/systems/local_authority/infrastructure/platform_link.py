"""The authority's screens drive the platform for children at the linked
primary and secondary schools.

Each function is a record type's ``after_commit`` hook: it runs once the
save has committed and returns lines for the person who saved (the form
shows them). If the platform call fails, the record still stands; the
failure becomes a notice and is logged (see ``core.records``).

* **Applications & Offers / Fair Access Panel**: an offer *Accepted* (or a
  fair access allocation) at a school marked as this platform's primary or
  secondary hands the place to that school; declining or withdrawing it
  before the child starts withdraws it there.
* **Attendance Cases, Penalty Notices, Suspensions & Exclusions, Children
  Missing Education, Elective Home Education**: a change the school should
  know about goes back as a note on the school's notification.
* **EHC Needs Assessments / EHC Plans**: each decision goes onto the
  school's SEN record (the request, the decision to assess or not, the
  draft and final plan, no plan, a plan ceasing) - for any child on a
  linked school's roll, whoever asked for the assessment.

A child with no platform journey (never notified by, or placed at, a linked
school) is untouched.
"""

from __future__ import annotations

from datetime import date

from education_system.systems.local_authority.core import records as r


def _links():
    from education_system.platform.cross_system import local_authority_links
    return local_authority_links


def _journey(child_id) -> str | None:
    from education_system.systems.local_authority.modules import children
    row = r.get(children.CHILDREN, int(child_id)) if child_id else None
    return (row or {}).get("journey_id") or None


def _update(row: dict, update: dict) -> list[str]:
    journey = _journey(row.get("learner_id"))
    if not journey:
        return []
    if row.get("transition_id"):
        update = dict(update, transition_id=row["transition_id"])
    return _links().record_update(str(row["learner_id"]), update, journey_id=journey)


def _changed(row: dict, old: dict | None, *keys: str) -> bool:
    return any((old or {}).get(k) != row.get(k) for k in keys)


# ── school places ────────────────────────────────────────────────────

def _year_for(child_id: int, round_: str | None, entry_year) -> str:
    from education_system.systems.local_authority.modules import admissions, children
    child = r.get(children.CHILDREN, int(child_id)) or {}
    dob = r.to_date(child.get("dob"))
    if round_ in admissions.ROUND_YEAR and entry_year:
        return admissions.ROUND_YEAR[round_]
    return children.year_group(dob)


def _hand_over(record_type, row: dict, school_id, details: dict) -> list[str]:
    from education_system.systems.local_authority.infrastructure.cross_system_adapter import (
        school_year,
    )
    from education_system.systems.local_authority.modules import schools
    system = schools.platform_system(school_id)
    if system is None:
        return []
    details = dict(details, year_group=school_year(details.get("year_group") or "", system))
    transition, lines = _links().place(str(row["learner_id"]), system, details=details,
                                       journey_id=_journey(row["learner_id"]))
    if transition is not None:
        r.save(record_type, {"place_transition_id": transition["transition_id"]},
               record_id=row["id"], actor="platform")
    _stamp_journey(row["learner_id"])
    return lines


def _stamp_journey(child_id) -> None:
    """A place can be the child's first platform link: keep the journey."""
    from education_system.platform.cross_system import identity_service
    from education_system.systems.local_authority.infrastructure import database as db
    if _journey(child_id):
        return
    found = identity_service.find_by_student("local_authority", str(child_id))
    if found:
        with db.connect() as conn:
            conn.execute("UPDATE learners SET journey_id = ? WHERE id = ?",
                         (found["journey_id"], int(child_id)))


def _withdraw(record_type, row: dict, reason: str) -> list[str]:
    tid = row.get("place_transition_id")
    if not tid:
        return []
    links = _links()
    school = links.school_for_place(tid)
    try:
        links.withdraw_place(tid, reason=reason)
    except links.LinkError as exc:
        return [str(exc)]
    r.save(record_type, {"place_transition_id": None}, record_id=row["id"], actor="platform")
    return [f"{links.SCHOOL_LABELS.get(school, 'The school')} has been told the place was "
            "withdrawn."]


def application_saved(row: dict, old: dict | None) -> list[str] | None:
    from education_system.systems.local_authority.modules import admissions
    status, was = row.get("status"), (old or {}).get("status")
    if status == "Accepted" and (was != "Accepted" or _changed(row, old, "offered_school_id")):
        out = []
        if row.get("place_transition_id") and _changed(row, old, "offered_school_id"):
            out += _withdraw(admissions.APPLICATIONS, row, "The offer changed school")
            row = dict(row, place_transition_id=None)
        if row.get("place_transition_id"):
            return out or None
        start = (date(int(row["entry_year"]), 9, 1).isoformat() if row.get("entry_year")
                 else None)
        return (out + _hand_over(admissions.APPLICATIONS, row, row.get("offered_school_id"), {
            "round": row.get("round"), "entry_year": row.get("entry_year"),
            "basis": row.get("offer_basis"), "offered_on": row.get("offered_on"),
            "start_date": start,
            "year_group": _year_for(row["learner_id"], row.get("round"), row.get("entry_year")),
            "reference": f"LA application #{row['id']}"})) or None
    if was == "Accepted" and status in ("Declined", "Withdrawn", "Refused"):
        return _withdraw(admissions.APPLICATIONS, row,
                         f"Place {status.lower()} with the local authority") or None
    return None


def fair_access_saved(row: dict, old: dict | None) -> list[str] | None:
    from education_system.systems.local_authority.modules import admissions
    if row.get("decision") == "Allocated" and not row.get("place_transition_id") and \
            ((old or {}).get("decision") != "Allocated" or _changed(row, old, "school_id")):
        return _hand_over(admissions.FAIR_ACCESS, row, row.get("school_id"), {
            "round": "In-year (fair access)", "basis": "Fair access",
            "offered_on": row.get("panel_on"), "start_date": row.get("on_roll_on"),
            "year_group": _year_for(row["learner_id"], None, None),
            "category": row.get("category"),
            "reference": f"Fair access referral #{row['id']}"}) or None
    if (old or {}).get("decision") == "Allocated" and row.get("decision") != "Allocated":
        return _withdraw(admissions.FAIR_ACCESS, row, "Fair access allocation withdrawn") \
            or None
    return None


# ── casework going back to the school ────────────────────────────────

def attendance_saved(row: dict, old: dict | None) -> list[str] | None:
    if old is None or not _changed(row, old, "stage", "status"):
        return None
    closed = row.get("status") == "Closed"
    return _update(row, {"kind": "attendance", "stage": row.get("stage"),
                         "officer": row.get("officer"), "closed": closed,
                         "outcome": (row.get("outcome") or "")[:200] if closed else None,
                         "on": date.today().isoformat()}) or None


def penalty_notice_saved(row: dict, old: dict | None) -> list[str] | None:
    if old is not None and not _changed(row, old, "status"):
        return None
    return _update(row, {"kind": "penalty_notice", "status": row.get("status"),
                         "reason": row.get("reason"),
                         "on": row.get("paid_on") if row.get("status") == "Paid"
                         else row.get("issued_on")}) or None


def exclusion_saved(row: dict, old: dict | None) -> list[str] | None:
    if old is None:
        return None
    lines = []
    if _changed(row, old, "provision_from", "provision") and row.get("provision_from"):
        lines.append(f"full-time provision from {row['provision_from']}"
                     + (f": {row['provision']}" if row.get("provision") else ""))
    if _changed(row, old, "irp_requested_on") and row.get("irp_requested_on"):
        lines.append(f"independent review requested {row['irp_requested_on']}")
    if _changed(row, old, "outcome") and row.get("outcome") not in (None, "Awaiting review"):
        lines.append(f"recorded as {str(row['outcome']).lower()}")
    if not lines:
        return None
    return _update(row, {"kind": "exclusion",
                         "text": f"{str(row.get('kind') or 'exclusion').lower()} - "
                                 + "; ".join(lines)}) or None


def cme_saved(row: dict, old: dict | None) -> list[str] | None:
    if old is None or not _changed(row, old, "status"):
        return None
    return _update(row, {"kind": "cme", "outcome": row.get("status"),
                         "on": row.get("closed_on")}) or None


def ehe_saved(row: dict, old: dict | None) -> list[str] | None:
    if old is None or not _changed(row, old, "status", "suitability", "sao_stage"):
        return None
    bits = []
    if _changed(row, old, "suitability"):
        bits.append(f"education judged: {str(row.get('suitability')).lower()}")
    if _changed(row, old, "sao_stage") and row.get("sao_stage") not in (None, "None"):
        bits.append(f"school attendance order: {str(row['sao_stage']).lower()}")
    if _changed(row, old, "status"):
        bits.append(f"home education: {str(row.get('status')).lower()}")
    return _update(row, {"kind": "ehe", "text": "; ".join(bits)}) or None


_ASSESS_STAGE = {"Agreed to assess": "Assessing", "Refused to assess": "Refused to assess"}


def ehc_request_saved(row: dict, old: dict | None) -> list[str] | None:
    stages = []
    if old is None:
        stages.append("Requested")
    if _changed(row, old, "assess_decision") and row.get("assess_decision") in _ASSESS_STAGE:
        stages.append(_ASSESS_STAGE[row["assess_decision"]])
    if _changed(row, old, "draft_issued_on") and row.get("draft_issued_on"):
        stages.append("Draft issued")
    if _changed(row, old, "final_issued_on") and row.get("final_issued_on"):
        stages.append("Final issued")
    if _changed(row, old, "plan_decision") and row.get("plan_decision") == \
            "No plan - SEN support":
        stages.append("Not issued")
    out: list[str] = []
    for stage in stages:
        out += _update(row, {"kind": "ehcp", "stage": stage,
                             "request_date": row.get("received_on"),
                             "decision_date": row.get("decided_on") or date.today().isoformat(),
                             "draft_date": row.get("draft_issued_on"),
                             "final_date": row.get("final_issued_on")})
    return out or None


def ehc_plan_saved(row: dict, old: dict | None) -> list[str] | None:
    if old is None or not _changed(row, old, "status") or row.get("status") != "Ceased":
        return None
    return _update(row, {"kind": "ehcp", "stage": "Ceased",
                         "cease_date": date.today().isoformat(),
                         "reason": row.get("cease_reason")}) or None


__all__ = ["application_saved", "fair_access_saved", "attendance_saved",
           "penalty_notice_saved", "exclusion_saved", "cme_saved", "ehe_saved",
           "ehc_request_saved", "ehc_plan_saved"]
