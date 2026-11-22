"""The SEND service's screens drive the platform for pupils a linked school sent.

Each function is a record type's ``after_commit`` hook: it runs once the
SEND save has committed and returns lines for the person who saved (the
form shows them). If the platform call fails, the SEND record still stands;
the failure becomes a notice and is logged (see ``core.records``).

* **EHCP Tracker**: a new stage (requested, agreed / refused to assess,
  draft, final issued, not issued, ceased) goes to the school that has the
  pupil on roll now. Final issued makes the school's SEN status EHC plan;
  ceased returns it to SEN support.
* **Annual Reviews**: the review and the LA's decision are logged for the
  school (the school keeps its own review record).
* **SEND Register**: archiving a linked learner closes the case on the
  platform (the school is told), making them active again re-opens it, and
  "No longer SEN" is logged for the school.

Learners not linked to a school on the platform are untouched.
"""

from __future__ import annotations

from education_system.systems.special_education.core import records as r

_EHCP_DATES = ("request_date", "decision_date", "draft_date", "final_date", "cease_date")


def _service():
    from education_system.platform.cross_system import send_referrals
    return send_referrals


def _learner(learner_id) -> dict:
    from education_system.systems.special_education.modules import learners
    try:
        return r.get(learners.LEARNERS, int(learner_id)) or {}
    except (TypeError, ValueError):
        return {}


def _lines(out: list[str]) -> list[str] | None:
    return out or None


# ── hooks ────────────────────────────────────────────────────────────

def ehcp_saved(row: dict, old: dict | None) -> list[str] | None:
    if old is not None and row.get("stage") == old.get("stage") and all(
            row.get(k) == old.get(k) for k in _EHCP_DATES):
        return None
    learner = _learner(row.get("learner_id"))
    if not learner.get("journey_id"):
        return None
    update = {"kind": "ehcp", "stage": row.get("stage"),
              **{k: row.get(k) for k in _EHCP_DATES}}
    return _lines(_service().record_update(str(learner["id"]), update,
                                           journey_id=learner["journey_id"]))


def review_saved(row: dict, old: dict | None) -> list[str] | None:
    keys = ("meeting_date", "recommendation", "outcome", "la_decision")
    if old is not None and all(row.get(k) == old.get(k) for k in keys):
        return None
    learner = _learner(row.get("learner_id"))
    if not learner.get("journey_id"):
        return None
    update = {"kind": "annual_review", **{k: row.get(k) for k in keys}}
    return _lines(_service().record_update(str(learner["id"]), update,
                                           journey_id=learner["journey_id"]))


def learner_saved(row: dict, old: dict | None) -> list[str] | None:
    if old is None or not row.get("journey_id"):
        return None
    svc, lid, jid = _service(), str(row["id"]), row["journey_id"]
    out: list[str] = []
    if row.get("status") == "Archived" and old.get("status") != "Archived":
        out += svc.close_case(lid, reason="Archived on the SEND register", journey_id=jid)
        out.append("The case is closed on the platform.")
    elif row.get("status") == "Active" and old.get("status") == "Archived":
        if svc.reopen_case(lid, journey_id=jid):
            out.append("The case is open again on the platform.")
    if row.get("sen_status") != old.get("sen_status") and \
            row.get("sen_status") == "No longer SEN":
        out += svc.record_update(lid, {"kind": "register", "sen_status": row["sen_status"]},
                                 journey_id=jid)
    return _lines(out)


__all__ = ["ehcp_saved", "review_saved", "learner_saved"]
