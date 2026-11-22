"""Pupil profile sections fed by the linked areas (staff only), shared by
the GUI profile and the terminal profile:

* the safeguarding line - leads only, and only when something is on record;
* SEND, medical and pupil premium;
* attendance case, wellbeing and (for the complaints lead) open complaints;
* trips and dinner money;
* parents' evening appointments and letters home.

Each section reads from the area that owns the data and is left out when
that area has nothing for the pupil. One area failing never stops the
profile. :func:`sections` returns ``[(title, [(text, level)])]`` where
*level* is ``""``, ``"warn"`` or ``"bad"``.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import STAFF_ROLES, Principal

logger = logging.getLogger(__name__)

_WARN, _BAD = "warn", "bad"
Line = tuple[str, str]
Section = tuple[str, list[Line]]


def _safe(label: str, fn: Callable[[], Any], default: Any = None) -> Any:
    try:
        return fn()
    except Exception:  # noqa: BLE001 - one area failing mustn't stop the profile
        logger.exception("Profile box %s failed", label)
        return default


def _line(box: list[Line], text: str, level: str = "") -> None:
    box.append((text, level))


def safeguarding_flag(pupil: P.Pupil, *, principal: Principal) -> str | None:
    """The one line for a safeguarding lead (need to know: nobody else sees
    that a record exists)."""
    from education_system.systems.secondary.modules.safeguarding.domain import (
        safeguarding_records as SR,
    )
    return _safe("safeguarding", lambda: SR.profile_line(pupil.pupil_id, actor=principal))


def sections(pupil: P.Pupil, *, principal: Principal) -> list[Section]:
    if principal.role not in STAFF_ROLES:
        return []
    out: list[Section] = []
    for title, fn in (("SEND, medical and pupil premium", lambda: _needs(pupil)),
                      ("Attendance case, wellbeing and complaints",
                       lambda: _pastoral(pupil, principal)),
                      ("Trips and dinner money", lambda: _money(pupil)),
                      ("Parents' evenings and letters home", lambda: _home_contact(pupil))):
        lines = _safe(title, fn, [])
        if lines:
            out.append((title, lines))
    return out


def _needs(pupil: P.Pupil) -> list[Line]:
    from education_system.systems.secondary.modules.medical.domain import medical as M
    from education_system.systems.secondary.modules.finance.domain import pupil_premium as PP
    from education_system.systems.secondary.modules.send.domain import send as S
    pid = pupil.pupil_id
    send = _safe("send", lambda: S.for_profile(pid))
    med = _safe("medical", lambda: M.for_pupil(pid), {}) or {}
    pp = _safe("pupil premium", lambda: PP.is_pupil_premium(pid), False)
    conds = med.get("conditions") or []     # active only (the list default)
    algs = med.get("allergies") or []
    if not (send or conds or algs or pp):
        return []
    box: list[Line] = []
    if send:
        _line(box, f"SEND: {send['stage']}" + (f" - {send['needs']}" if send["needs"] else "")
              + (f" · keyworker {send['keyworker']}" if send.get("keyworker") else "")
              + (f" · review {send['next_review']}" if send.get("next_review") else ""))
        if send["strategies"]:
            _line(box, "What helps: " + send["strategies"].replace("\n", "; "))
        if send["exam_access"]:
            _line(box, f"Exam access: {send['exam_access']}")
        if send.get("ehcp_due"):
            _line(box, f"EHCP annual review due {send['ehcp_due']}", _WARN)
    for a in algs:
        _line(box, f"Allergy: {a.allergen}" + (" - ANAPHYLAXIS" if a.anaphylaxis else ""),
              _BAD if a.anaphylaxis else _WARN)
    for c in conds:
        # Care notes taken on Add Pupil are an "Other" condition with notes.
        detail = c.what_to_do or getattr(c, "notes", None)
        _line(box, f"Medical: {c.condition} ({c.severity.lower()})"
              + (f" - {detail}" if detail else ""),
              _BAD if c.severity in M.SERIOUS else "")
    if pp:
        _line(box, "Pupil premium: eligible this year")
    return box


def _pastoral(pupil: P.Pupil, principal: Principal) -> list[Line]:
    from education_system.systems.secondary.modules.attendance.domain import (
        attendance_concerns as AC,
    )
    from education_system.systems.secondary.modules.administration.domain import complaints as CM
    from education_system.systems.secondary.modules.wellbeing.domain import wellbeing as WB
    pid = pupil.pupil_id
    ac = _safe("attendance concerns", lambda: AC.for_pupil(pid), {}) or {}
    wb = _safe("wellbeing", lambda: WB.for_pupil(pid, actor=principal), {}) or {}
    cms = _safe("complaints", lambda: CM.list_complaints(pupil_id=pid, open_only=True), []) \
        if CM.is_editor(principal) else []
    case = ac.get("open")
    latest = wb.get("latest") if wb.get("visible") else None
    plan = wb.get("plan") if wb.get("visible") else None
    refs = wb.get("referrals") or [] if wb.get("visible") else []
    if not (case or ac.get("band") or latest or plan or refs or cms):
        return []
    box: list[Line] = []
    if ac.get("band"):
        _line(box, f"Attendance {ac['pct']}% - {ac['band']} absence", _BAD
              if ac["band"] == "severe" else _WARN)
    if case:
        _line(box, f"Open attendance case: {case.stage} since "
                   f"{case.stage_date or case.opened_date}"
              + (f" · next review {case.next_review_date}" if case.next_review_date else "")
              + (f" · key worker {case.key_worker}" if case.key_worker else ""))
    if latest:
        avg = latest.average_rating
        _line(box, f"Last wellbeing check-in {latest.checkin_date}"
              + (f": average {avg} / {WB.MAX_RATING}" if avg is not None else "")
              + (" · action needed" if latest.action_needed else ""),
              _WARN if latest.action_needed else "")
    if plan:
        _line(box, f"Wellbeing plan active (review {plan.review_date})",
              _WARN if plan.review_due else "")
    for r in refs:
        _line(box, f"Referral: {r.service} ({r.status}, {r.referral_date})")
    for c in cms[:3]:
        _line(box, f"Open complaint #{c.complaint_id}: {c.subject} ({c.stage}, {c.status})")
    return box


def _money(pupil: P.Pupil) -> list[Line]:
    from education_system.systems.secondary.modules.finance.domain import dinner_money as DM
    from education_system.systems.secondary.modules.trips.domain import trips as TR
    pid = pupil.pupil_id
    acct = _safe("dinner money", lambda: DM.account(pid))
    bookings = [b for b in _safe("trips", lambda: TR.trips_for_pupil(pid), []) or []
                if b.is_active and b.trip_status != "Cancelled"]
    if acct is None and not bookings:
        return []
    box: list[Line] = []
    if acct is not None:
        _line(box, f"Dinner money: {DM.money(acct.balance_pence)}"
              + (" · free school meals" if acct.fsm else "")
              + (f" · {acct.needs_flag}" if acct.needs_flag else ""),
              _BAD if acct.balance_pence < 0 else "")
    for b in sorted(bookings, key=lambda x: x.trip_start, reverse=True)[:5]:
        _line(box, f"Trip: {b.trip_title} ({b.trip_start}) - {b.status}, consent "
                   f"{b.consent or 'not given'}"
              + (f", {TR.money(b.balance_pence)} to pay" if b.balance_pence > 0 else ""),
              _WARN if b.balance_pence > 0 or b.consent != "Yes" else "")
    return box


def _home_contact(pupil: P.Pupil) -> list[Line]:
    from education_system.systems.secondary.modules.communication.domain import letters as L
    from education_system.systems.secondary.modules.communication.domain import (
        parents_evenings as PE,
    )
    pid = pupil.pupil_id
    appts = [b for b in _safe("parents evenings", lambda: PE.for_pupil(pid), []) or []
             if b.status != "Cancelled"]
    letters = _safe("letters", lambda: L.for_pupil(pid), []) or []
    if not (appts or letters):
        return []
    box: list[Line] = []
    for b in appts[:4]:
        _line(box, f"Parents' evening: {b.slot_time} with {b.teacher_name} ({b.status})"
              + (f" - {b.teacher_notes}" if b.teacher_notes else ""))
    for r in letters[:5]:
        reply = ""
        if r.reply_question:
            reply = f" · reply: {r.reply}" if r.reply else " · no reply yet"
        _line(box, f"Letter {str(r.sent_at)[:10]}: {r.subject}{reply}",
              _WARN if r.reply_question and not r.reply else "")
    return box


__all__ = ["safeguarding_flag", "sections"]
