"""Which institutional connectors hear about which university events.

The outbox dispatcher calls :func:`feed` for every event it delivers. Each
connector gets a record built only from the event payload plus what the
external body needs (never names, addresses or free text it has no use
for), keyed ``<event_id>:<connector>`` so a retried event is never sent
twice. A connector that is not enabled is skipped.

* ``award.ratified`` - degree verification (HEDD) and HESA (qualification
  awarded).
* ``admissions.decision.recorded`` - UCAS, only for an application that came
  through UCAS (a UCAS link or an external reference).
* ``admissions.student.converted`` - identity provider, library and VLE
  accounts.
* ``enrolment.registration.recorded`` / ``enrolment.change.reversed`` - SLC
  attendance confirmation and HESA engagement.
* ``student.deactivated`` / ``student.restored`` - identity provider, library
  and VLE access; SLC change of circumstance on deactivation; the Home
  Office sponsor system for a sponsored student.
* ``student.updated`` / ``student.transferred`` - HESA (and SLC on transfer).
* ``fee.assessed`` - the payments provider (invoice).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from education_system.systems.university.application import connectors
from education_system.systems.university.infrastructure.database.db import transaction

_ACCOUNT_FIELDS = ("student_id",)


def _pick(payload: Mapping[str, Any], *keys: str) -> dict[str, Any]:
    return {k: payload.get(k) for k in keys if k in payload}


def _student_context(student_id: Any) -> dict[str, Any]:
    """Programme, mode and status the external returns key on."""
    with transaction() as conn:
        row = conn.execute(
            "SELECT course, mode_of_study, status, academic_year FROM students "
            "WHERE student_id=?", (str(student_id),),
        ).fetchone()
    return dict(row) if row else {}


def _is_sponsored(student_id: Any) -> bool:
    with transaction() as conn:
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='visa_records'"
        ).fetchone()
        if not exists:
            return False
        return conn.execute(
            "SELECT 1 FROM visa_records WHERE student_id=? AND status='active' LIMIT 1",
            (str(student_id),),
        ).fetchone() is not None


def _came_through_ucas(application_id: Any) -> str | None:
    """The UCAS reference for an application, or ``None`` for a direct one."""
    with transaction() as conn:
        row = conn.execute(
            "SELECT external_reference FROM admission_applications WHERE application_id=?",
            (application_id,),
        ).fetchone()
        if row and row["external_reference"]:
            return str(row["external_reference"])
        linked = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='ucas_application_links'"
        ).fetchone()
        if linked and conn.execute(
            "SELECT 1 FROM ucas_application_links WHERE uni_application_id=? LIMIT 1",
            (application_id,),
        ).fetchone():
            return f"link:{application_id}"
    return None


def _award(p):
    record = _pick(p, "award_id", "student_id", "programme_code", "award_name",
                   "classification")
    return {"degree_verification": record, "hesa_jisc": {"entity": "Qualification", **record}}


def _decision(p):
    reference = _came_through_ucas(p.get("application_id"))
    if not reference:
        return {}
    return {"ucas": {"application_id": p.get("application_id"), "ucas_reference": reference,
                     "decision": p.get("decision")}}


def _converted(p):
    account = {"action": "create", **_pick(p, "student_id", "application_id")}
    return {"idp": account, "library": account, "vle": account}


def _registration(p):
    ctx = _student_context(p.get("student_id"))
    record = {**_pick(p, "student_id", "action", "academic_year", "registration_id",
                      "history_id"),
              "programme": ctx.get("course"), "mode": ctx.get("mode_of_study")}
    return {"slc": {"notice": "attendance_confirmation", **record},
            "hesa_jisc": {"entity": "Engagement", **record}}


def _reversed(p):
    record = _pick(p, "student_id", "history_id", "reversal_history_id")
    return {"slc": {"notice": "change_reversed", **record},
            "hesa_jisc": {"entity": "StudentCourseSession", "change": "reversed", **record}}


def _access(action):
    def build(p):
        sid = p.get("student_id")
        account = {"action": action, "student_id": sid}
        out = {"idp": account, "library": account, "vle": account}
        if action == "disable":
            out["slc"] = {"notice": "change_of_circumstance", "student_id": sid,
                          "status": _student_context(sid).get("status")}
            if _is_sponsored(sid):
                out["ukvi_cas"] = {"report": "student_no_longer_sponsored", "student_id": sid}
        return out
    return build


def _updated(p):
    sid = p.get("student_id")
    ctx = _student_context(sid)
    return {"hesa_jisc": {"entity": "Student", "student_id": sid,
                          "programme": ctx.get("course"), "status": ctx.get("status")}}


def _transferred(p):
    record = _pick(p, "student_id", "from", "to")
    return {"hesa_jisc": {"entity": "StudentCourseSession", "change": "transfer", **record},
            "slc": {"notice": "change_of_course", **record}}


def _fee(p):
    return {"payments": {"invoice": "tuition", **_pick(
        p, "student_fee_id", "student_id", "module_code", "amount", "currency",
        "academic_year")}}


FEEDS: dict[str, Callable[[Mapping[str, Any]], dict[str, dict[str, Any]]]] = {
    "award.ratified": _award,
    "admissions.decision.recorded": _decision,
    "admissions.student.converted": _converted,
    "enrolment.registration.recorded": _registration,
    "enrolment.change.reversed": _reversed,
    "student.deactivated": _access("disable"),
    "student.restored": _access("enable"),
    "student.updated": _updated,
    "student.transferred": _transferred,
    "fee.assessed": _fee,
}


def feed(event_id: str, event_name: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    """Send the event to every enabled connector that hears about it.
    Returns ``{connector: True (sent) / False (already sent) / None (off)}``;
    a failing connector raises so the event is retried."""
    build = FEEDS.get(event_name)
    if build is None:
        return {}
    outcome: dict[str, Any] = {}
    for name, record in build(payload).items():
        outcome[name] = connectors.send(
            name, f"{event_id}:{name}", {"event": event_name, "event_id": event_id, **record}
        )
    return outcome


__all__ = ["FEEDS", "feed"]
