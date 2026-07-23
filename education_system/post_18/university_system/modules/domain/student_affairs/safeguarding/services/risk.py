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

from education_system.post_18.university_system.modules.domain.student_affairs.safeguarding.db import (
    _connect,
)

DEFAULT_RISK_MATRIX = {
    # severity -> (default likelihood, default impact)
    "CRITICAL": (5, 5),
    "HIGH": (4, 4),
    "MEDIUM": (3, 3),
    "LOW": (2, 2),
    "NONE": (1, 1),
}
VULNERABILITY_FLAGS = (
    "Minor (<18)",
    "Care-leaver",
    "Disability",
    "PREVENT concern",
    "International student",
    "Estranged from family",
    "Pregnant",
)


def compute_risk_score(severity, triage, vulnerability_flags):
    """Return (likelihood, impact, score) on a 1..25 scale."""
    likelihood, impact = DEFAULT_RISK_MATRIX.get(severity or "NONE", (1, 1))
    # Triage answers can amplify likelihood/impact
    if (triage or {}).get("q3") == "yes":  # immediate danger
        impact = min(5, impact + 1)
        likelihood = min(5, likelihood + 1)
    if (triage or {}).get("q4") == "no":  # nobody else knows yet
        likelihood = min(5, likelihood + 1)
    for _flag in vulnerability_flags or ():
        impact = min(5, impact + 1)
    return likelihood, impact, likelihood * impact


SLA_HOURS = {"CRITICAL": 1, "HIGH": 4, "MEDIUM": 24, "LOW": 72, "NONE": 168}


def compute_sla_due(severity):
    hours = SLA_HOURS.get(severity)
    if not hours:
        return None
    return datetime.now() + timedelta(hours=hours)


def refresh_sla_breach_flags():
    """Mark any pending case whose SLA has passed as breached. Called on staff
    dashboard refresh. Cheap — only touches the small subset of open rows."""
    now = datetime.now().isoformat()
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "UPDATE safeguarding_submissions SET sla_breached=1 "
        "WHERE sla_breached=0 AND lifecycle_state!='Closed' "
        "AND sla_due_at IS NOT NULL AND sla_due_at < ?",
        (now,),
    )
    conn.commit()
    conn.close()


__all__ = [
    "DEFAULT_RISK_MATRIX",
    "VULNERABILITY_FLAGS",
    "compute_risk_score",
    "SLA_HOURS",
    "compute_sla_due",
    "refresh_sla_breach_flags",
]
