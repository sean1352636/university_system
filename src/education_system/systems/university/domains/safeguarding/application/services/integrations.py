import base64
import hashlib
import json
import logging
import os
import re
import secrets
import shutil
import sys
from datetime import datetime, timedelta
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)

from education_system.systems.university.domains.safeguarding.infrastructure.db import (
    _connect,
)
from education_system.systems.university.domains.safeguarding.domain.permissions import (
    audit_log,
)
from education_system.systems.university.domains.safeguarding.application.services.cases import (
    add_case_note,
    add_referral,
)


def create_wellbeing_appointment(case_id, when_iso, service="Wellbeing", notes="", actor="system"):
    """Book a wellbeing (counselling) appointment for the case's linked
    student through the Pastoral wellness service, and link it to the case.

    The case note says exactly what happened: "booked" only when the
    appointment exists; otherwise "requested, not booked" with the reason
    (no linked student, a bad date, or the booking failing), so a case never
    claims a booking that wasn't made. Returns the reference stored on the
    case (``COUNS-<id>`` when booked, ``REQ-…`` when only requested)."""
    conn = _connect()
    cur = conn.cursor()
    cur.execute("SELECT linked_subject_id FROM safeguarding_submissions WHERE id=?", (case_id,))
    row = cur.fetchone()
    conn.close()
    student_id = row[0] if row and row[0] else None
    booked_id, reason = None, None
    when = str(when_iso or "").replace("T", " ").strip()
    day, _, clock = when.partition(" ")
    if not student_id:
        reason = "no student is linked to the case"
    elif not day:
        reason = "no date was given"
    else:
        try:
            from education_system.systems.university.domains.student_support.domain.wellbeing.wellness.services.wellness_service import (  # noqa: E501
                WellnessService,
            )
            booked_id = WellnessService().schedule_counseling(
                str(student_id), day, (clock or "09:00")[:5], service,
                notes or f"Safeguarding case {case_id}")
        except Exception as exc:
            logger.warning("Wellbeing booking for case %s failed: %s", case_id, exc)
            reason = f"the booking failed ({exc})"
    if booked_id:
        ref, outcome = f"COUNS-{booked_id}", "booked"
    else:
        ref, outcome = f"REQ-{case_id}-{datetime.now():%Y%m%d%H%M%S}", "requested, not booked"
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "UPDATE safeguarding_submissions SET linked_wellbeing_appt=? WHERE id=?",
        (ref, case_id),
    )
    conn.commit()
    conn.close()
    add_case_note(case_id, actor, f"[wellbeing] appointment {outcome}: {ref} @ {when_iso} "
                                  f"({service})" + (f" — {reason}" if reason else ""))
    audit_log(
        actor=actor,
        action="wellbeing_booked" if booked_id else "wellbeing_requested",
        case_id=case_id,
        details=f"ref={ref} when={when_iso}" + (f" reason={reason}" if reason else ""),
    )
    return ref


def link_conduct_case(case_id, conduct_ref, actor="system"):
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "UPDATE safeguarding_submissions SET linked_conduct_case=? WHERE id=?",
        (conduct_ref, case_id),
    )
    conn.commit()
    conn.close()
    add_case_note(case_id, actor, f"[conduct] linked to conduct case {conduct_ref}")
    audit_log(actor=actor, action="link_conduct", case_id=case_id, details=f"ref={conduct_ref}")


def link_halls_incident(case_id, incident_ref, actor="system"):
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "UPDATE safeguarding_submissions SET linked_halls_incident=? WHERE id=?",
        (incident_ref, case_id),
    )
    conn.commit()
    conn.close()
    add_case_note(case_id, actor, f"[halls] linked to accommodation incident {incident_ref}")
    audit_log(actor=actor, action="link_halls", case_id=case_id, details=f"ref={incident_ref}")


def create_health_referral(case_id, consent, notes="", actor="system"):
    if not consent:
        raise PermissionError("Health-Centre referrals require explicit student consent.")
    now = datetime.now().isoformat()
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "UPDATE safeguarding_submissions "
        "SET health_referral_consent=1, health_referral_sent_at=? WHERE id=?",
        (now, case_id),
    )
    conn.commit()
    conn.close()
    add_referral(
        case_id,
        "Health Centre",
        contact="health-centre@example.edu",
        reference_no=f"HC-{case_id}-{datetime.now():%Y%m%d%H%M%S}",
        note=notes,
    )
    audit_log(
        actor=actor,
        action="health_referral",
        case_id=case_id,
        details=f"consent=1 notes={notes[:60]}",
    )


__all__ = [
    "create_wellbeing_appointment",
    "link_conduct_case",
    "link_halls_incident",
    "create_health_referral",
]
