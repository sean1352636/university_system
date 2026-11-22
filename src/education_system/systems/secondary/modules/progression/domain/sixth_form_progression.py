"""Move Year 11 pupils on to the Sixth Form.

The school sends a Year 11 pupil to the Sixth Form as an **applicant**: the
sixth form's admissions team then interviews, offers and converts them in
the usual way. What goes with the pupil:

* their **full name** (legal first, middle and last names, preferred name),
  date of birth, gender, UPN and admission number - enough to match them;
* their **GCSE results** (:mod:`modules.examinations.domain.gcse_results`) - not grades from an
  exam series still under embargo;
* their **GCSE entries** (:mod:`modules.examinations.domain.exam_entries`) and where each
  stands - awaited, under review, withheld or issued
  (:mod:`modules.examinations.domain.exam_results`);
* their **SEN details** (:mod:`modules.pupils.domain.sen_details`) - only with recorded
  consent, because the platform treats SEND provision as sensitive.

Pupils are usually sent before results day. When the exams officer
releases a series - and whenever a released result changes later (a late
result, a review of marking) - :func:`send_results` updates each open
application with the new grades and entries, so the sixth form can check
its offer conditions. It can also be run by hand.

The pupil stays on the school roll until the sixth form enrols them; the
sixth form then reports back (offer, accepted, declined, enrolled) on the
platform's post-16 board, and enrolment takes the pupil off roll here as an
end-of-Year-11 leaver with "Sixth form college" as the destination.

Nothing here imports the sixth form: the platform's post-16 board and
adapter registry carry the handover.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass
from typing import Any

from education_system.systems.secondary.modules.examinations.domain import gcse_results as G
from education_system.systems.secondary.modules.pupils.domain import enrolment as E
from education_system.systems.secondary.modules.pupils.domain import sen_details as SEN
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import SIXTH_FORM_SENDERS, Principal
from education_system.systems.secondary.core.academic_calendar.school_year import today as _today
from education_system.systems.secondary.infrastructure.logging import activity_log

DESTINATION = "sixth_form"
DESTINATION_LABEL = "Sixth Form"
LEAVER_DESTINATION = "Sixth form college"
SYSTEM_ACTOR = Principal("system:sixth-form-progression", "admin")
#: Stages after which a pupil can be sent again.
CLOSED_STAGES = frozenset({"Declined", "Withdrawn"})

ValidationError = P.ValidationError
PermissionDenied = P.PermissionDenied
NotFound = P.NotFound


def _post16():
    from education_system.platform.cross_system import secondary_post16
    return secondary_post16


def offered_subjects() -> tuple[str, ...]:
    """The sixth form's published subject list (empty if unavailable),
    asked through the platform adapter registry."""
    try:
        from education_system.platform.cross_system import route_support
        fn = getattr(route_support.adapter_for(DESTINATION), "offered_subjects", None)
        return tuple(fn()) if fn else ()
    except Exception:  # the sixth form isn't installed / reachable
        return ()


def is_sender(actor: Principal) -> bool:
    return actor.role in SIXTH_FORM_SENDERS


@dataclass(frozen=True)
class Candidate:
    pupil: P.Pupil
    gcse_count: int
    sen_recorded: bool
    application: dict[str, Any] | None
    exam_results: str = ""

    @property
    def stage(self) -> str:
        return self.application["stage"] if self.application else "Not sent"

    @property
    def can_send(self) -> bool:
        return self.application is None or self.application["stage"] in CLOSED_STAGES


def application_for(pupil_id: int, *, db_path: str | None = None) -> dict[str, Any] | None:
    """The pupil's latest sixth form application on the post-16 board."""
    try:
        rows = _post16().list_applications(pupil_id=str(int(pupil_id)),
                                           destination=DESTINATION, db_path=db_path)
    except Exception:  # the board is unreachable: show "Not sent", never crash
        return None
    return rows[0] if rows else None


def cohort(*, search: str | None = None, db_path: str | None = None) -> list[Candidate]:
    """Year 11 pupils on roll, with what would go and where they are."""
    pupils = P.list_pupils(year_group=P.YEAR_GROUPS[-1], search=search)
    try:
        apps = _post16().list_applications(destination=DESTINATION, db_path=db_path)
    except Exception:
        apps = []
    latest: dict[str, dict] = {}
    for a in apps:  # newest first
        latest.setdefault(str(a["pupil_id"]), a)
    sen = {p.pupil_id for p, d in SEN.register(year_group=P.YEAR_GROUPS[-1]) if d}
    from education_system.systems.secondary.modules.examinations.domain import exam_results as ER
    states = ER.result_states()
    return [Candidate(p, len(G.for_pupil(p.pupil_id)), p.pupil_id in sen,
                      latest.get(str(p.pupil_id)), results_summary(p.pupil_id, states))
            for p in pupils]


def sent(*, db_path: str | None = None) -> list[tuple[P.Pupil | None, dict[str, Any]]]:
    """Every sixth form application from this school, newest first."""
    out = []
    for a in _post16().list_applications(destination=DESTINATION, db_path=db_path):
        pid = str(a["pupil_id"])
        out.append((P.get_pupil(int(pid)) if pid.isdigit() else None, a))
    return out


def _check(pupil_id: int, actor: Principal, action: str) -> P.Pupil:
    p = P.get_pupil(int(pupil_id))
    if p is None:
        raise NotFound(f"No pupil with id {pupil_id}")
    if not is_sender(actor):
        activity_log.record(action, target=p.admission_no, outcome="denied", principal=actor)
        raise PermissionDenied("Only the head of year or an administrator can send pupils "
                               "to the sixth form.")
    return p


def _fields(*, actor: Principal, consent_sen: bool, consent_reference: str | None,
            subjects: list[str] | None, notes: str | None) -> dict[str, Any]:
    return {
        "predicted_grades": None, "prior_attainment": None,
        "consent_record": {"reference": (consent_reference or "").strip() or "school-consent",
                           "recorded_by": actor.username, "sen": bool(consent_sen)},
        "consent": {"access_arrangements"} if consent_sen else None,
        "subjects": [s.strip() for s in (subjects or []) if s and s.strip()],
        "personal_statement": (notes or "").strip() or None,
    }


def _problems(p: P.Pupil, subjects: list[str] | None, consent_sen: bool) -> list[str]:
    problems = []
    if p.roll_status != "on_roll":
        problems.append(f"{p.display_name} is not on roll")
    if p.year_group != P.YEAR_GROUPS[-1]:
        problems.append(f"{p.display_name} is in Year {p.year_group}; only Year "
                        f"{P.YEAR_GROUPS[-1]} pupils move on to the sixth form")
    chosen = [s.strip().lower() for s in (subjects or []) if s and s.strip()]
    if len(chosen) != len(set(chosen)):
        problems.append("Each subject choice must be different")
    if chosen and len(chosen) != 3:
        problems.append("Choose three A-levels (or none, to choose later)")
    return problems


def _subjects(pupil_id: int, subjects: list[str] | None) -> list[str]:
    """The subjects to send: those given, else the pupil's saved choices
    (:mod:`modules.progression.domain.sixth_form_choices`)."""
    given = [s.strip() for s in (subjects or []) if s and s.strip()]
    if given:
        return given
    from education_system.systems.secondary.modules.progression.domain import (
        sixth_form_choices as SC,
    )
    return SC.courses_for(pupil_id)


def preview(pupil_id: int, *, actor: Principal, consent_sen: bool = False,
            consent_reference: str | None = None, subjects: list[str] | None = None,
            notes: str | None = None):
    """What the sixth form would receive (a platform ``Preview``)."""
    p = _check(pupil_id, actor, "progression.preview")
    subjects = _subjects(p.pupil_id, subjects)
    return _post16().preview(str(p.pupil_id), DESTINATION, **_fields(
        actor=actor, consent_sen=consent_sen, consent_reference=consent_reference,
        subjects=subjects, notes=notes))


def send(pupil_id: int, *, actor: Principal, consent_sen: bool = False,
         consent_reference: str | None = None, subjects: list[str] | None = None,
         notes: str | None = None, destination_label: str | None = None,
         db_path: str | None = None) -> dict[str, Any]:
    """Send one Year 11 pupil to the sixth form as an applicant.

    *consent_sen* says the pupil/parent agreed to share SEN details; without
    it the SEN block is withheld. Sending again while an application is
    open returns that application.
    """
    p = _check(pupil_id, actor, "progression.send")
    given = [s.strip() for s in (subjects or []) if s and s.strip()]
    subjects = _subjects(p.pupil_id, subjects)
    problems = _problems(p, subjects, consent_sen)
    if consent_sen and not (consent_reference or "").strip():
        problems.append("Give the consent reference (e.g. the signed form) for sharing "
                        "SEN details")
    current = application_for(p.pupil_id, db_path=db_path)
    if current and current["stage"] not in CLOSED_STAGES:
        problems.append(f"{p.display_name} was already sent (stage: {current['stage']})")
    if problems:
        activity_log.record("progression.send", target=p.admission_no, outcome="invalid",
                            principal=actor, problems=len(problems))
        raise ValidationError(problems)
    if given:  # chosen here: they become the pupil's A-level choices
        from education_system.systems.secondary.modules.progression.domain import (
            sixth_form_choices as SC,
        )
        if [x.lower() for x in given] != [x.lower() for x in SC.courses_for(p.pupil_id)]:
            subjects = SC.save(p.pupil_id, given, actor=actor)["choices"]
    post16 = _post16()
    try:
        app = post16.submit(
            str(p.pupil_id), DESTINATION,
            destination_label=(destination_label or "").strip()[:80] or DESTINATION_LABEL,
            programme_label=", ".join(s.strip() for s in subjects or [] if s.strip()),
            actor_user_id=actor.user_id if isinstance(actor.user_id, int) else None,
            db_path=db_path, **_fields(actor=actor, consent_sen=consent_sen,
                                       consent_reference=consent_reference,
                                       subjects=subjects, notes=notes))
    except post16.Post16Error as exc:
        activity_log.record("progression.send", target=p.admission_no, outcome="failed",
                            principal=actor)
        raise ValidationError([str(exc)]) from exc
    activity_log.record("progression.send", target=p.admission_no, principal=actor,
                        sen_shared=bool(consent_sen))
    return app


def send_many(pupil_ids: list[int], *, actor: Principal, consent_sen_for: set[int] = frozenset(),  # type: ignore[assignment]
              consent_reference: str | None = None, db_path: str | None = None
              ) -> dict[str, Any]:
    """Send several pupils (with their saved A-level choices, if any). Each
    is separate; returns
    {'sent': [admission_no], 'failed': {admission_no: reason}}."""
    if not is_sender(actor):
        activity_log.record("progression.send", outcome="denied", principal=actor)
        raise PermissionDenied("Only the head of year or an administrator can send pupils "
                               "to the sixth form.")
    out: dict[str, Any] = {"sent": [], "failed": {}}
    for pid in pupil_ids:
        p = P.get_pupil(int(pid))
        label = p.admission_no if p else f"id:{pid}"
        try:
            send(int(pid), actor=actor, consent_sen=int(pid) in consent_sen_for,
                 consent_reference=consent_reference, db_path=db_path)
            out["sent"].append(label)
        except (ValidationError, NotFound) as exc:
            out["failed"][label] = "; ".join(getattr(exc, "problems", None) or [str(exc)])
    return out


def withdraw(pupil_id: int, *, actor: Principal, reason: str = "",
             db_path: str | None = None) -> dict[str, Any]:
    """The school withdraws an open application (e.g. sent in error)."""
    p = _check(pupil_id, actor, "progression.withdraw")
    app = application_for(p.pupil_id, db_path=db_path)
    if app is None or app["stage"] in CLOSED_STAGES | {"Enrolled / On Programme"}:
        raise ValidationError([f"{p.display_name} has no open sixth form application"])
    out = _post16().update_status(app["transition_id"], "Withdrawn",
                                  details=(reason or "").strip(), db_path=db_path)
    activity_log.record("progression.withdraw", target=p.admission_no, principal=actor)
    return out


# ── Exam results after the pupil was sent ────────────────────────────

def _open_for_results(app: dict[str, Any] | None) -> bool:
    """Results still go to an application unless it was declined or
    withdrawn (an enrolled learner's record still takes a late review)."""
    return app is not None and app["stage"] not in CLOSED_STAGES


def results_summary(pupil_id: int, states: dict | None = None) -> str:
    """e.g. "6 issued, 2 awaited, 1 under review" ("" with no entries).
    Pass *states* (:func:`exam_results.result_states`) when listing many."""
    from education_system.systems.secondary.modules.examinations.domain import exam_results as ER
    n = (states if states is not None else ER.result_states()).get(int(pupil_id), {})
    return ", ".join(f"{n[k]} {k}" for k in ("issued", "awaited", "under review",
                                              "withheld") if n.get(k))


def send_results(pupil_ids: list[int] | None = None, *, actor: Principal,
                 quiet: bool = False, db_path: str | None = None) -> dict[str, Any]:
    """Update the open sixth form applications of *pupil_ids* (default: every
    pupil with one) with their current GCSE results and entries. Embargoed
    grades stay back. Returns {'sent': [admission_no], 'skipped':
    {admission_no: reason}}; *quiet* leaves out pupils with no application
    (used after a release, which covers the whole series)."""
    from education_system.systems.secondary.modules.examinations.domain import exam_results as ER
    if not (is_sender(actor) or ER.is_editor(actor)):
        activity_log.record("progression.results", outcome="denied", principal=actor)
        raise PermissionDenied("Only the exams officer, the head of year or an "
                               "administrator can send results to the sixth form.")
    post16 = _post16()
    if pupil_ids is None:
        apps = post16.list_applications(destination=DESTINATION, db_path=db_path)
        latest: dict[str, dict] = {}
        for a in apps:
            latest.setdefault(str(a["pupil_id"]), a)
        pupil_ids = sorted(int(k) for k, a in latest.items()
                           if k.isdigit() and _open_for_results(a))
    out: dict[str, Any] = {"sent": [], "skipped": {}}
    for pid in pupil_ids:
        p = P.get_pupil(int(pid))
        label = p.admission_no if p else f"id:{pid}"
        app = application_for(int(pid), db_path=db_path)
        if not _open_for_results(app):
            if not quiet:
                out["skipped"][label] = ("no open sixth form application" if app is None
                                         else f"application {app['stage'].lower()}")
            continue
        try:
            post16.update_results(
                str(int(pid)), DESTINATION, gcse_results=G.handover_list(int(pid)),
                gcse_entries=ER.entries_for_handover(int(pid)), db_path=db_path)
            out["sent"].append(label)
        except Exception as exc:  # noqa: BLE001 - one pupil never stops the rest
            out["skipped"][label] = str(exc) or type(exc).__name__
    activity_log.record("progression.results", principal=actor, sent=len(out["sent"]),
                        skipped=len(out["skipped"]))
    return out


# ── Called by the platform when the sixth form enrols the pupil ──────

def close_for_sixth_form(pupil_id: int | str, *, end_date: str | None = None,
                         reason: str = "") -> bool:
    """Take the pupil off roll as an end-of-Year-11 leaver to the sixth form.
    Returns False when they had already left (nothing to do)."""
    p = P.get_pupil(int(pupil_id))
    if p is None or p.roll_status != "on_roll":
        return False
    today = _today()
    date = end_date or today.isoformat()
    try:
        if _dt.date.fromisoformat(date) > today:
            date = today.isoformat()
    except ValueError:
        date = today.isoformat()
    if p.year_group == P.YEAR_GROUPS[-1]:
        reason_code, details = E.END_OF_Y11, {"post16_destination": LEAVER_DESTINATION}
    else:
        reason_code, details = E.OTHER, {"notes": f"Enrolled at the sixth form. {reason}".strip()}
    E.record_leaver(p.pupil_id, leaving_date=date, reason=reason_code, details=details,
                    actor=SYSTEM_ACTOR, today=today)
    return True
