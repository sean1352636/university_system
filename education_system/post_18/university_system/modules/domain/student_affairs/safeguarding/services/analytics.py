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


def canonical_subject_id(user, anonymous=False):
    """Stable id for grouping cases about the same person. Anonymous cases
    get a per-submission unique id so they don't all collide."""
    if anonymous:
        return None
    uname = (user or {}).get("username") or ""
    fname = (user or {}).get("full_name") or ""
    seed = (uname or fname).lower().strip()
    if not seed:
        return None
    # SHA-256 (not SHA-1) for a non-reversible linking key. Must match
    # retention.py's subject-hash computation so cases link consistently.
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]


def find_linked_cases(subject_id, exclude_id=None):
    if not subject_id:
        return []
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, submitted_at, severity, status, lifecycle_state "
        "FROM safeguarding_submissions WHERE linked_subject_id=? "
        "ORDER BY submitted_at DESC",
        (subject_id,),
    )
    rows = cur.fetchall()
    conn.close()
    if exclude_id is not None:
        rows = [r for r in rows if r[0] != exclude_id]
    return rows


_CUMULATIVE_WINDOW_DAYS = 30
_CUMULATIVE_THRESHOLD = 3  # >=3 LOW/MEDIUM/HIGH in window -> escalate flag


def cumulative_concern(subject_id):
    """Return (count_in_window, should_escalate) for the given subject."""
    if not subject_id:
        return 0, False
    cutoff = (datetime.now() - timedelta(days=_CUMULATIVE_WINDOW_DAYS)).isoformat()
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM safeguarding_submissions "
        "WHERE linked_subject_id=? AND submitted_at>=? "
        "AND severity IN ('LOW','MEDIUM','HIGH')",
        (subject_id, cutoff),
    )
    n = cur.fetchone()[0]
    conn.close()
    return n, n >= _CUMULATIVE_THRESHOLD


def incident_heatmap(days=90):
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT COALESCE(case_department,'(unspecified)'), severity, COUNT(*) "
        "FROM safeguarding_submissions WHERE submitted_at>=? "
        "GROUP BY case_department, severity",
        (cutoff,),
    )
    rows = cur.fetchall()
    conn.close()
    grid = {}
    for dept, sev, n in rows:
        grid.setdefault(dept, {})[sev or "NONE"] = n
    return grid


def risk_trend(weeks=8):
    cutoff = (datetime.now() - timedelta(weeks=weeks)).isoformat()
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT strftime('%Y-W%W', submitted_at) AS wk, severity, COUNT(*) "
        "FROM safeguarding_submissions WHERE submitted_at>=? "
        "GROUP BY wk, severity ORDER BY wk ASC",
        (cutoff,),
    )
    rows = cur.fetchall()
    conn.close()
    out = {}
    for wk, sev, n in rows:
        out.setdefault(wk, {})[sev or "NONE"] = n
    return out


def leadership_stats(days=90):
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM safeguarding_submissions "
        "WHERE submitted_at>=? AND COALESCE(purged,0)=0",
        (cutoff,),
    )
    total = cur.fetchone()[0]
    cur.execute(
        "SELECT severity, COUNT(*) FROM safeguarding_submissions "
        "WHERE submitted_at>=? AND COALESCE(purged,0)=0 GROUP BY severity",
        (cutoff,),
    )
    by_sev = dict(cur.fetchall())
    cur.execute(
        "SELECT lifecycle_state, COUNT(*) FROM safeguarding_submissions "
        "WHERE submitted_at>=? AND COALESCE(purged,0)=0 "
        "GROUP BY lifecycle_state",
        (cutoff,),
    )
    by_lifecycle = dict(cur.fetchall())
    cur.execute(
        "SELECT outcome_code, COUNT(*) FROM safeguarding_submissions "
        "WHERE submitted_at>=? AND outcome_code IS NOT NULL "
        "AND COALESCE(purged,0)=0 GROUP BY outcome_code",
        (cutoff,),
    )
    by_outcome = dict(cur.fetchall())
    cur.execute(
        "SELECT COUNT(*) FROM safeguarding_submissions "
        "WHERE submitted_at>=? AND sla_breached=1 "
        "AND COALESCE(purged,0)=0",
        (cutoff,),
    )
    sla_breaches = cur.fetchone()[0]
    cur.execute(
        "SELECT COUNT(*) FROM safeguarding_submissions "
        "WHERE submitted_at>=? AND mandatory_reporting=1 "
        "AND COALESCE(purged,0)=0",
        (cutoff,),
    )
    mandatory = cur.fetchone()[0]
    # Average days-to-close for closed cases in window
    cur.execute(
        "SELECT submitted_at, reviewed_at FROM safeguarding_submissions "
        "WHERE submitted_at>=? AND lifecycle_state='Closed' "
        "AND reviewed_at IS NOT NULL",
        (cutoff,),
    )
    diffs = []
    for sub, rev in cur.fetchall():
        try:
            diffs.append(
                (datetime.fromisoformat(rev) - datetime.fromisoformat(sub)).total_seconds() / 86400
            )
        except (TypeError, ValueError):
            pass
    avg_days = round(sum(diffs) / len(diffs), 1) if diffs else None
    conn.close()
    return {
        "period_days": days,
        "total": total,
        "by_severity": by_sev,
        "by_lifecycle": by_lifecycle,
        "by_outcome": by_outcome,
        "sla_breaches": sla_breaches,
        "mandatory_flags": mandatory,
        "avg_days_to_close": avg_days,
    }


__all__ = [
    "canonical_subject_id",
    "find_linked_cases",
    "_CUMULATIVE_WINDOW_DAYS",
    "_CUMULATIVE_THRESHOLD",
    "cumulative_concern",
    "incident_heatmap",
    "risk_trend",
    "leadership_stats",
]
