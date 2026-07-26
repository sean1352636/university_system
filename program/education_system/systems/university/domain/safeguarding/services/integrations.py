import base64
import hashlib
import json
import logging
import os
import re
import secrets
import shutil
import sqlite3
import sys
import tkinter as tk
import webbrowser
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from tkinter import ttk, messagebox, scrolledtext, filedialog

logger = logging.getLogger(__name__)

from education_system.systems.university.domain.safeguarding.db import (
    _connect,
)
from education_system.systems.university.domain.safeguarding.permissions import (
    audit_log,
)
from education_system.systems.university.domain.safeguarding.services.cases import (
    add_case_note,
    add_referral,
)


def create_wellbeing_appointment(case_id, when_iso, service="Wellbeing", notes="", actor="system"):
    """Try to forward to the shared wellbeing booking module if importable;
    otherwise store a stub reference. Returns the booking reference."""
    ref = f"WB-{case_id}-{datetime.now():%Y%m%d%H%M%S}"
    try:
        from education_system.systems.university.domain.pastoral.health.wellness import (
            book_appointment,
        )  # type: ignore

        booked = book_appointment(case_id=case_id, when=when_iso, service=service, notes=notes)
        if booked:
            ref = str(booked)
    except Exception:
        logger.debug("Wellbeing booking module unavailable; using stub ref", exc_info=True)
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "UPDATE safeguarding_submissions SET linked_wellbeing_appt=? WHERE id=?",
        (ref, case_id),
    )
    conn.commit()
    conn.close()
    add_case_note(case_id, actor, f"[wellbeing] appointment booked: {ref} @ {when_iso} ({service})")
    audit_log(
        actor=actor,
        action="wellbeing_booked",
        case_id=case_id,
        details=f"ref={ref} when={when_iso}",
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
