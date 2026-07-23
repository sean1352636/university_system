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
from education_system.post_18.university_system.modules.domain.student_affairs.safeguarding.permissions import (
    audit_log,
)

DEFAULT_TRAINING_VALIDITY_DAYS = 365 * 3  # statutory 3-year refresh


def record_training(
    username,
    full_name,
    module,
    completed_at=None,
    valid_days=DEFAULT_TRAINING_VALIDITY_DAYS,
    actor="system",
):
    completed = completed_at or datetime.now().isoformat()
    try:
        completed_dt = datetime.fromisoformat(completed)
    except ValueError:
        completed_dt = datetime.now()
    expires = (completed_dt + timedelta(days=valid_days)).isoformat()
    conn = _connect()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO safeguarding_training"
            "(username, full_name, module, completed_at, expires_at) "
            "VALUES (?,?,?,?,?)",
            (username, full_name, module, completed, expires),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        pass  # duplicate completion record — already on file
    conn.close()
    audit_log(
        actor=actor,
        action="training_record",
        details=f"user={username} module={module} expires={expires}",
    )
    return expires


def training_status(username):
    """Return per-module status: 'Current' / 'Expiring soon' (≤60d) / 'Expired' / 'Missing'."""
    now = datetime.now()
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT module, MAX(completed_at), MAX(expires_at) "
        "FROM safeguarding_training WHERE username=? GROUP BY module",
        (username,),
    )
    rows = cur.fetchall()
    conn.close()
    out = {}
    for module, _completed, expires in rows:
        if not expires:
            out[module] = "Current"
            continue
        try:
            ex_dt = datetime.fromisoformat(expires)
        except ValueError:
            out[module] = "Current"
            continue
        if ex_dt < now:
            out[module] = "Expired"
        elif (ex_dt - now).days <= 60:
            out[module] = "Expiring soon"
        else:
            out[module] = "Current"
    return out


def training_compliance_summary():
    """Aggregate compliance across everyone with a training record on file."""
    conn = _connect()
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT username FROM safeguarding_training")
    users = [r[0] for r in cur.fetchall()]
    conn.close()
    if not users:
        return {
            "users_tracked": 0,
            "current_pct": 0.0,
            "expired": 0,
            "expiring_soon": 0,
            "current": 0,
        }
    current = expired = expiring = 0
    for u in users:
        status = training_status(u)
        # User counts as current only if every recorded module is current.
        states = set(status.values()) or {"Current"}
        if "Expired" in states:
            expired += 1
        elif "Expiring soon" in states:
            expiring += 1
        else:
            current += 1
    return {
        "users_tracked": len(users),
        "current": current,
        "expiring_soon": expiring,
        "expired": expired,
        "current_pct": round(100 * current / len(users), 1),
    }


__all__ = [
    "DEFAULT_TRAINING_VALIDITY_DAYS",
    "record_training",
    "training_status",
    "training_compliance_summary",
]
