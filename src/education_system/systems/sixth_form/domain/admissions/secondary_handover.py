"""Year 11 pupils sent by the Secondary School, arriving as applicants.

The secondary school sends a pupil through the platform's post-16 board;
the platform calls :meth:`SixthFormAdapter.create_applicant`, which hands
a ``source_system == "secondary"`` handover to :func:`receive`. That:

* matches an open applicant (UPN, then name + date of birth) or creates
  one - status Submitted, source Transfer - with the pupil's **full name**,
  date of birth, UPN and sex. Contact details and subject choices may be
  missing; a timeline note lists what admissions still needs;
* records the pupil's **GCSE results** as Actual results (source
  "Transfer");
* records the **SEN details** (only present when the school had consent)
  as the applicant's SEND information, sets the LLDD / EHCP flags and
  leaves a note for the SENCO. Conversion later turns the structured lines
  into the SEND register entry (:func:`register_fields`).

Results day comes after the pupil was sent: when the school releases its
exam results (or a review of marking changes one), the platform calls
:meth:`SixthFormAdapter.update_applicant_results` and :func:`receive_results`
brings the applicant's transferred Actual GCSEs up to date and leaves a
timeline note saying what changed and what is still awaited or under review.
If the pupil then changes their A-level choices (to courses their grades
meet), :func:`receive_choices` rewrites the applicant's subjects.

Afterwards the school is told how it goes: :func:`report_status` (offer,
interview, accepted, declined, withdrawn) and :func:`report_enrolled`
(converted to a student - the school then takes the pupil off roll).

Nothing here imports the secondary school; the platform carries the data.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
from typing import Any

from education_system.systems.sixth_form.domain.admissions import _guard
from education_system.systems.sixth_form.domain.admissions import admissions as _adm
from education_system.systems.sixth_form.domain.admissions import college_intake as _intake

logger = logging.getLogger(__name__)

SOURCE_SYSTEM = "secondary"
MARKER = "secondary-handover"
ACTOR = "secondary-handover"
SENCO_NOTE = "SEN information received from the secondary school, SENCO to review"

#: Sixth form admissions status -> the school's post-16 board stage.
STATUS_TO_STAGE: dict[str, str] = {
    "Interview Scheduled": "Interview/assessment",
    "Offer Made": "Conditional offer",
    "Offer Accepted": "Offer accepted",
    "Offer Declined": "Declined",
    "Rejected": "Declined",
    "Withdrawn": "Withdrawn",
}

#: DfE census need codes -> SEND register need types.
NEED_MAP: dict[str, str] = {
    "SPLD": "Cognition & Learning", "MLD": "Cognition & Learning",
    "SLD": "Cognition & Learning", "PMLD": "Cognition & Learning",
    "SLCN": "Communication & Interaction", "ASD": "Communication & Interaction",
    "SEMH": "Social, Emotional & Mental Health",
    "HI": "Sensory or Physical", "VI": "Sensory or Physical",
    "MSI": "Sensory or Physical", "PD": "Sensory or Physical",
    "OTH": "Other", "NSA": "Other",
}
_SEX = {"female": "female", "f": "female", "male": "male", "m": "male",
        "non-binary": "non-binary", "other": "other",
        "prefer not to say": "prefer not to say"}


def _access():
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )
    return access


def _clean(value: Any) -> str:
    return str(value or "").strip()


# ── Receiving ────────────────────────────────────────────────────────

def _existing(journey_id: str) -> str | None:
    _intake._init_log()
    with _adm._connect() as conn:
        r = conn.execute(
            "SELECT applicant_id FROM admissions_intake_log WHERE journey_id = ? "
            "AND action = 'attached' AND detail = ? AND applicant_id IS NOT NULL "
            "ORDER BY id DESC LIMIT 1", (journey_id, MARKER)).fetchone()
    return r["applicant_id"] if r else None


def _choices(subjects: list[Any]) -> list[str]:
    chosen: list[str] = []
    for s in subjects or []:
        s = _clean(s)
        if s and s not in chosen:
            chosen.append(s)
    return _intake._valid_choices({f"subject_{i}": s
                                   for i, s in enumerate(chosen[:3], 1)})


def sen_text(sen: dict[str, Any]) -> str:
    """The SEN block as structured lines (read back by :func:`register_fields`)."""
    lines = ["From the secondary school's SEN record:"]
    status = _clean(sen.get("sen_status_label") or sen.get("sen_status"))
    if status:
        lines.append(f"SEN status: {status}")
    for key, label in (("primary_need", "Primary need"), ("secondary_need", "Secondary need")):
        code = _clean(sen.get(key)).upper()
        if code:
            name = _clean(sen.get(f"{key}_label"))
            lines.append(f"{label}: {code}" + (f" - {name}" if name else ""))
    ref, issued = _clean(sen.get("ehcp_reference")), _clean(sen.get("ehcp_issued_on"))
    if ref or issued:
        lines.append("EHC plan: " + (ref or "reference not given")
                     + (f", issued {issued}" if issued else ""))
    for key, label in (("provision", "Provision"), ("strategies", "Strategies"),
                       ("exam_access", "Exam access")):
        text = _clean(sen.get(key))
        if text:
            lines.append(f"{label}: {text}")
    return "\n".join(lines)


def register_fields(text: str | None) -> dict[str, str]:
    """SEND register fields read from :func:`sen_text` lines (empty for
    free text): primary_need, secondary_need, register_status,
    ehcp_issued_on."""
    out: dict[str, str] = {}
    for line in (text or "").splitlines():
        m = re.match(r"\s*(Primary need|Secondary need|SEN status|EHC plan):\s*(.+)", line)
        if not m:
            continue
        key, value = m.group(1), m.group(2).strip()
        if key in ("Primary need", "Secondary need"):
            need = NEED_MAP.get(value.split(" ", 1)[0].upper())
            field = "primary_need" if key == "Primary need" else "secondary_need"
            if need and field not in out:
                out[field] = need
        elif key == "SEN status":
            low = value.lower()
            out["register_status"] = ("EHCP" if "plan" in low or low == "e"
                                      else "SEN Support")
        else:
            d = re.search(r"issued (\d{4}-\d{2}-\d{2})", value)
            if d:
                out["ehcp_issued_on"] = d.group(1)
    if out.get("secondary_need") == out.get("primary_need"):
        out.pop("secondary_need", None)
    return out


def _carry_sen(aid: str, sen: dict[str, Any], done: list[str]) -> None:
    from education_system.systems.sixth_form.domain.admissions import (
        applicant_details as _details,
    )
    a = _adm.get_applicant(aid)
    assert a is not None
    flags: dict[str, bool] = {}
    if not a.lldd:
        flags["lldd"] = True
    if _clean(sen.get("sen_status")).upper() == "E" and not a.ehcp:
        flags["ehcp"] = True
    if flags:
        _details.update_profile(aid, **flags)
    text = sen_text(sen)
    old = (_details.sensitive_for_conversion(aid).get("send") or "").strip()
    if text in old:
        return
    _details.set_sensitive(aid, "send", f"{old}\n\n{text}" if old else text,
                           received_from="Secondary school")
    with _adm._connect() as conn:
        _adm._log_event(conn, aid, SENCO_NOTE, kind="sensitive")
        conn.commit()
    done.append("SEN details for the SENCO")


def _carry_gcses(aid: str, results: list[dict[str, Any]], done: list[str]) -> None:
    from education_system.systems.sixth_form.domain.admissions import entry_requirements as ER
    n, skipped = 0, []
    for r in results or []:
        subject, grade = _clean(r.get("subject")), _clean(r.get("grade")).upper()
        kind = _clean(r.get("qualification")) or "GCSE"
        try:
            ER.record_gcse(aid, subject, grade, result_type="Actual",
                           kind=kind if kind in ER.GCSE_KINDS else "GCSE",
                           year=r.get("year"), exam_board=r.get("exam_board"),
                           source="Transfer", entered_by=f"system:{ACTOR}")
            n += 1
        except _adm.ValidationError as e:
            skipped.append(f"{subject or '?'} ({e})")
    if n:
        done.append(f"{n} GCSE result(s)")
    if skipped:
        done.append("GCSEs not recorded: " + "; ".join(skipped))


def receive(handover: Any) -> str:
    """Create or match the applicant for a secondary handover; returns the
    applicant id. Idempotent on the journey."""
    journey_id = handover.journey_id
    access = _access()
    with _guard.system_actor(ACTOR, capabilities=(access.ADMISSIONS, access.SEND)):
        aid = _existing(journey_id)
        if aid and _adm.get_applicant(aid) is not None:
            return aid
        ident = (handover.get("student_identity") or handover.get("learner_identity")
                 or {})
        first, last = _clean(ident.get("first_name")), _clean(ident.get("last_name"))
        dob = _clean(ident.get("date_of_birth"))
        upn = _clean(ident.get("upn")).upper()
        details = handover.get("application_details") or {}
        choices = _choices(details.get("subjects") or [])
        a, how = _intake._match_applicant({"upn": upn}, first, last, dob)
        if a is not None and a.converted_student_id:
            a = None  # already a student: a fresh application is clearer
        done: list[str] = []
        if a is None:
            payload: dict[str, Any] = {
                "first_name": first, "last_name": last, "dob": dob or None,
                "application_source": "Transfer", "status": "Submitted",
                "submitted_at": _dt.date.today().isoformat(),
                "notes": _clean(details.get("personal_statement")) or None,
            }
            payload.update({f"subject_{i}": s for i, s in enumerate(choices, 1)})
            a = _adm.create_applicant(payload, allow_duplicate=True, incomplete_ok=True)
            how = "new applicant"
            done.append("created applicant")
        aid = a.applicant_id
        extra = {}
        if upn and not a.upn:
            extra["upn"] = upn
        if extra:
            _adm._set_extra(aid, event="UPN from the secondary school", **extra)
        sex = _SEX.get(_clean(ident.get("gender")).lower())
        if sex and not a.sex:
            from education_system.systems.sixth_form.domain.admissions import (
                applicant_details as _details,
            )
            try:
                _details.update_profile(aid, sex=sex)
            except _adm.ValidationError:
                pass
        _carry_gcses(aid, handover.get("gcse_results") or [], done)
        sen = handover.get("access_arrangements")
        if isinstance(sen, dict) and sen:
            _carry_sen(aid, sen, done)
        _intake._log(journey_id, "attached", applicant_id=aid, matched_on=how,
                     detail=MARKER)
        a = _adm.get_applicant(aid)
        assert a is not None
        missing = [label for key, label in (("email", "e-mail"), ("phone", "phone"),
                                            ("subject_1", "subject choices"))
                   if not getattr(a, key, None)]
        full = _clean(ident.get("full_name")) or f"{first} {last}"
        lines = [f"Sent by the secondary school as a Year 11 leaver ({full}; "
                 f"journey {journey_id}, {how})."]
        if done:
            lines.append("Received: " + ", ".join(done) + ".")
        if not (isinstance(sen, dict) and sen):
            lines.append("No SEN details were shared.")
        waiting = _waiting(handover.get("gcse_entries") or [])
        if waiting:
            lines.append(waiting)
        if missing:
            lines.append("Still needed from the applicant: " + ", ".join(missing) + ".")
        lines.append("Convert the applicant to enrol them; the school then takes them "
                     "off roll.")
        _adm.add_note(aid, "\n".join(lines), author=f"system:{ACTOR}")
    return aid


# ── Results day ──────────────────────────────────────────────────────

def _waiting(entries: list[dict[str, Any]]) -> str:
    """"Results awaited: Maths; under review: English Language (6)." or ""."""
    parts = []
    for state, label in (("awaited", "Results awaited"), ("under review", "under review"),
                         ("withheld", "withheld by the board")):
        names = [_clean(e.get("subject")) + (f" ({_clean(e.get('grade'))})"
                                             if state == "under review" and e.get("grade")
                                             else "")
                 for e in entries if e.get("result") == state]
        if names:
            parts.append(f"{label}: " + ", ".join(names))
    return ("; ".join(parts) + ".") if parts else ""


def receive_results(handover: Any) -> str:
    """The school's exam results for an applicant it sent earlier. The
    payload's ``gcse_results`` is the full current list: transferred Actual
    GCSEs are brought in line with it (a grade the school no longer sends -
    withheld, or changed back - is removed). Returns the applicant id."""
    from education_system.systems.sixth_form.domain.admissions import entry_requirements as ER
    access = _access()
    with _guard.system_actor(ACTOR, capabilities=(access.ADMISSIONS,)):
        aid = _existing(handover.journey_id)
        if not aid or _adm.get_applicant(aid) is None:
            raise _adm.ValidationError("No applicant from the secondary school for this "
                                       "learner")

        def transferred() -> dict[tuple[str, str], Any]:
            return {(g.subject.lower(), g.kind): g
                    for g in ER.list_gcses(aid, result_type="Actual")
                    if g.source == "Transfer"}
        before = {k: g.grade for k, g in transferred().items()}
        results = handover.get("gcse_results") or []
        done: list[str] = []
        _carry_gcses(aid, results, done)
        keep = {(_clean(r.get("subject")).lower(),
                 _clean(r.get("qualification")) if _clean(r.get("qualification"))
                 in ER.GCSE_KINDS else "GCSE") for r in results}
        removed = []
        for k, g in transferred().items():
            if k not in keep:
                ER.delete_gcse(g.id)
                removed.append(f"{g.subject} ({g.grade})")
        after = {k: g.grade for k, g in transferred().items()}
        changed = [f"{g.subject} {before.get(k) or '-'} -> {g.grade}"
                   for k, g in transferred().items() if before.get(k) != g.grade]
        waiting = _waiting(handover.get("gcse_entries") or [])
        lines = []
        if changed:
            lines.append("Exam results from the secondary school: " + ", ".join(changed) + ".")
        if removed:
            lines.append("No longer sent by the school (withheld or changed): "
                         + ", ".join(removed) + ".")
        if waiting:
            lines.append(waiting)
        # What the admissions team has been told: the grades and what is
        # still to come. A note only when that changes.
        state = ("; ".join(f"{k[0]}/{k[1]}={v}" for k, v in sorted(after.items()))
                 + " | " + waiting)[:500]
        if lines and state != _last_results_note(aid):
            lines.append("Check the offer conditions against the actual grades.")
            _adm.add_note(aid, "\n".join(lines), author=f"system:{ACTOR}")
            _intake._log(handover.journey_id, "results", applicant_id=aid, detail=state)
    return aid


def receive_choices(handover: Any) -> str:
    """The school's pupil changed their A-level choices after being sent
    (e.g. after results day, to courses their grades meet). Rewrites the
    applicant's subject choices and leaves a note for admissions to check
    the offer. Returns the applicant id."""
    access = _access()
    with _guard.system_actor(ACTOR, capabilities=(access.ADMISSIONS,)):
        aid = _existing(handover.journey_id)
        a = _adm.get_applicant(aid) if aid else None
        if a is None:
            raise _adm.ValidationError("No applicant from the secondary school for this "
                                       "learner")
        details = handover.get("application_details") or {}
        new = _choices(details.get("subjects") or [])
        old = [s for s in (a.subject_1, a.subject_2, a.subject_3) if s]
        if new == old:
            return aid
        _adm.update_applicant(aid, {f"subject_{i}": (new[i - 1] if i <= len(new) else None)
                                    for i in (1, 2, 3)})
        _adm.add_note(aid, "A-level choices changed by the pupil at the secondary school: "
                      + (", ".join(new) or "none") + f" (were {', '.join(old) or 'none'}).\n"
                      "Check the offer and its conditions against the new courses.",
                      author=f"system:{ACTOR}")
        _intake._log(handover.journey_id, "choices", applicant_id=aid,
                     detail=", ".join(new)[:500])
    return aid


def _last_results_note(applicant_id: str) -> str | None:
    """The state recorded with the last results note."""
    _intake._init_log()
    with _adm._connect() as conn:
        r = conn.execute("SELECT detail FROM admissions_intake_log WHERE applicant_id = ? AND "
                         "action = 'results' ORDER BY id DESC LIMIT 1",
                         (applicant_id,)).fetchone()
    return r["detail"] if r else None


# ── Reporting back to the school ─────────────────────────────────────

def journey_for(applicant_id: str) -> str | None:
    """The journey of a secondary handover attached to this applicant."""
    try:
        _intake._init_log()
        with _adm._connect() as conn:
            r = conn.execute(
                "SELECT journey_id FROM admissions_intake_log WHERE applicant_id = ? "
                "AND action = 'attached' AND detail = ? ORDER BY id DESC LIMIT 1",
                (applicant_id, MARKER)).fetchone()
    except Exception:  # noqa: BLE001 - reporting never blocks admissions
        return None
    return r["journey_id"] if r else None


def _board():
    from education_system.platform.cross_system import secondary_post16
    return secondary_post16


def report_status(applicant_id: str, status: str) -> bool:
    """Tell the school's post-16 board about a status change. Best effort;
    False when the applicant didn't come from the school."""
    stage = STATUS_TO_STAGE.get(status)
    if stage is None:
        return False
    journey = journey_for(applicant_id)
    if journey is None:
        return False
    try:
        return _board().destination_update(journey, "sixth_form", stage,
                                           details=f"Sixth form status: {status}") is not None
    except Exception:  # noqa: BLE001
        logger.exception("Could not report %s to the secondary school's post-16 board",
                         applicant_id)
        return False


def report_enrolled(applicant_id: str, student_id: str, journey_id: str | None = None
                    ) -> bool:
    """The applicant has become a student: the board shows them enrolled
    and the school takes them off roll. Best effort."""
    own = journey_for(applicant_id)
    if own is None:  # not sent by the school
        return False
    journey = journey_id or own
    try:
        return _board().destination_update(
            journey, "sixth_form", "Enrolled / On Programme",
            details=f"Enrolled as {student_id}", local_student_id=student_id) is not None
    except Exception:  # noqa: BLE001
        logger.exception("Could not report enrolment of %s to the secondary school",
                         applicant_id)
        return False


def converted_student(journey_id: str) -> str | None:
    """The student a secondary-handover applicant was converted to."""
    with _guard.system_actor(ACTOR):
        aid = _existing(journey_id)
        a = _adm.get_applicant(aid) if aid else None
    return a.converted_student_id if a else None
