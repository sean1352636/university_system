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
from education_system.post_18.university_system.modules.domain.student_affairs.safeguarding.i18n import tr
from education_system.post_18.university_system.modules.domain.student_affairs.safeguarding.permissions import (
    audit_log,
)

RETENTION_DAYS_BY_OUTCOME = {
    None: 365 * 7,  # open / not yet closed: 7y default
    "NFA": 365 * 1,
    "UNFOUNDED": 365 * 1,
    "DUPLICATE": 365 * 1,
    "WITHDRAWN": 365 * 1,
    "SUPPORT": 365 * 3,
    "MONITORING": 365 * 5,
    "REFERRED": 365 * 7,
    "DISCIPLINE": 365 * 7,
    "MERGED": 365 * 1,
}


def _compute_retention_until(severity, outcome):
    days = RETENTION_DAYS_BY_OUTCOME.get(outcome, RETENTION_DAYS_BY_OUTCOME[None])
    # Critical cases get +3 years statutory retention bump.
    if severity == "CRITICAL":
        days += 365 * 3
    return datetime.now() + timedelta(days=days)


def _compute_retention_until_for_id(case_id, outcome):
    conn = _connect()
    cur = conn.cursor()
    cur.execute("SELECT severity FROM safeguarding_submissions WHERE id=?", (case_id,))
    row = cur.fetchone()
    conn.close()
    sev = row[0] if row else "NONE"
    return _compute_retention_until(sev, outcome)


def purge_due_records(actor="system", dry_run=False):
    """Soft-purge any closed case whose retention horizon has passed.
    Blanks out free-text content, attachments, audio, transcription and
    triage answers; preserves the row + categorical/aggregate fields so
    statutory counts stay accurate."""
    now = datetime.now().isoformat()
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT id FROM safeguarding_submissions "
        "WHERE COALESCE(purged,0)=0 AND lifecycle_state='Closed' "
        "AND retention_until IS NOT NULL AND retention_until < ?",
        (now,),
    )
    ids = [r[0] for r in cur.fetchall()]
    if dry_run or not ids:
        conn.close()
        return len(ids), ids
    placeholders = ",".join("?" for _ in ids)
    cur.execute(
        f"UPDATE safeguarding_submissions "
        f"SET content='', content_blob=NULL, content_encrypted=0, "
        f"    transcription='', transcription_blob=NULL, "
        f"    transcription_encrypted=0, attachments=NULL, audio_path=NULL, "
        f"    triage=NULL, review_note=NULL, purged=1 "
        f"WHERE id IN ({placeholders})",
        ids,
    )
    # Also drop case notes which are free-text by nature.
    cur.execute(
        f"DELETE FROM safeguarding_case_notes WHERE case_id IN ({placeholders})",
        ids,
    )
    conn.commit()
    conn.close()
    audit_log(actor=actor, action="purge_due", details=f"ids={ids}")
    return len(ids), ids


def generate_sar_bundle(subject_username, out_dir, actor):
    from education_system.post_18.university_system.modules.domain.student_affairs.safeguarding.services.submissions import (
        resolve_content,
    )

    """Build a zip containing all rows + notes + actions + referrals +
    notifications + audit entries for a given subject. Returns the zip path."""
    import csv
    import io
    import zipfile

    os.makedirs(out_dir, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    safe_user = re.sub(r"[^A-Za-z0-9_-]", "_", subject_username)[:40]
    out_path = os.path.join(out_dir, f"sar_{safe_user}_{stamp}.zip")

    # SHA-256 (not SHA-1) linking key; must match analytics.canonical_subject_id.
    subj_hash = hashlib.sha256(subject_username.lower().strip().encode("utf-8")).hexdigest()[:16]
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT id FROM safeguarding_submissions "
        "WHERE username=? OR reporter_username=? OR linked_subject_id=?",
        (subject_username, subject_username, subj_hash),
    )
    ids = [r[0] for r in cur.fetchall()]
    conn.close()

    def _q_to_csv(query, params):
        conn = _connect()
        cur = conn.cursor()
        cur.execute(query, params)
        cols = [d[0] for d in cur.description] if cur.description else []
        rows = cur.fetchall()
        conn.close()
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(cols)
        for r in rows:
            w.writerow(r)
        return buf.getvalue()

    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # Top-level submissions (rich, with decrypted content)
        rich_rows = []
        for sid in ids:
            conn = _connect()
            cur = conn.cursor()
            cur.execute("SELECT * FROM safeguarding_submissions WHERE id=?", (sid,))
            row = cur.fetchone()
            cols = [d[0] for d in cur.description]
            conn.close()
            row_dict = dict(zip(cols, row))
            # Resolve encrypted fields for the SAR copy.
            ct, tr = resolve_content(sid)
            row_dict["content"] = ct
            row_dict["transcription"] = tr
            row_dict.pop("content_blob", None)
            row_dict.pop("transcription_blob", None)
            rich_rows.append(row_dict)
        zf.writestr("submissions.json", json.dumps(rich_rows, indent=2, default=str))

        placeholders = ",".join("?" for _ in ids) or "''"
        if ids:
            zf.writestr(
                "case_notes.csv",
                _q_to_csv(
                    f"SELECT * FROM safeguarding_case_notes WHERE case_id IN ({placeholders})", ids
                ),
            )
            zf.writestr(
                "action_items.csv",
                _q_to_csv(
                    f"SELECT * FROM safeguarding_action_items WHERE case_id IN ({placeholders})",
                    ids,
                ),
            )
            zf.writestr(
                "referrals.csv",
                _q_to_csv(
                    f"SELECT * FROM safeguarding_case_referrals WHERE case_id IN ({placeholders})",
                    ids,
                ),
            )
            zf.writestr(
                "assignments.csv",
                _q_to_csv(
                    f"SELECT * FROM safeguarding_assignments WHERE case_id IN ({placeholders})", ids
                ),
            )
            zf.writestr(
                "notifications.csv",
                _q_to_csv(
                    f"SELECT * FROM safeguarding_notifications WHERE case_id IN ({placeholders})",
                    ids,
                ),
            )
            zf.writestr(
                "audit_log.csv",
                _q_to_csv(
                    f"SELECT * FROM safeguarding_audit_log WHERE case_id IN ({placeholders})", ids
                ),
            )

        zf.writestr(
            "README.txt",
            f"Subject Access Request bundle\n"
            f"Subject: {subject_username}\n"
            f"Generated: {datetime.now().isoformat()}\n"
            f"Cases included: {ids}\n",
        )

    audit_log(
        actor=actor,
        action="sar_export",
        details=f"subject={subject_username} cases={ids} path={out_path}",
    )
    return out_path, len(ids)


__all__ = [
    "RETENTION_DAYS_BY_OUTCOME",
    "_compute_retention_until",
    "_compute_retention_until_for_id",
    "purge_due_records",
    "generate_sar_bundle",
]
