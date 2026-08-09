"""
Course-evaluation scheduling & distribution service (features 9-14).

9.  Auto-open/close windows tied to dates
10. Reminder cadence editor (offset days from open/close)
11. Bulk invitations by section / cohort / list of student IDs
12. Anonymous tokenised single-use links
13. QR-code rollout (PNG if `qrcode` is installed, else ASCII fallback)
14. Embargo controls (results gated until grades submitted)
"""

from __future__ import annotations

import io
import secrets
from datetime import datetime, timedelta
from typing import Iterable

from education_system.systems.university.infrastructure.database.db import (
    get_connection,
    transaction,
)


# ---------- Scheduling / windows (feature 9) ----------

def set_window(evaluation_id: int, start: str, end: str,
               *, auto_open: bool = True) -> None:
    with transaction() as conn:
        conn.execute(
            """UPDATE course_evaluations
               SET start_date=?, end_date=?, auto_open=?
               WHERE evaluation_id=?""",
            (start, end, 1 if auto_open else 0, evaluation_id),
        )
        conn.commit()


def auto_transition(now: datetime | None = None) -> dict[str, list[int]]:
    """Open/close evaluations whose window boundaries have passed.

    Returns dict of {"opened": [...], "closed": [...]} evaluation_ids.
    """
    now = now or datetime.now()
    iso = now.isoformat()
    opened: list[int] = []
    closed: list[int] = []
    with transaction() as conn:
        for row in conn.execute(
            "SELECT evaluation_id, start_date, end_date, is_active, auto_open "
            "FROM course_evaluations WHERE auto_open=1"
        ).fetchall():
            d = dict(row)
            if not d["is_active"] and d["start_date"] and d["start_date"] <= iso <= (d["end_date"] or iso):
                conn.execute("UPDATE course_evaluations SET is_active=1 WHERE evaluation_id=?",
                             (d["evaluation_id"],))
                opened.append(d["evaluation_id"])
            elif d["is_active"] and d["end_date"] and d["end_date"] < iso:
                conn.execute("UPDATE course_evaluations SET is_active=0 WHERE evaluation_id=?",
                             (d["evaluation_id"],))
                closed.append(d["evaluation_id"])
        conn.commit()
    return {"opened": opened, "closed": closed}


# ---------- Reminders (feature 10) ----------

def schedule_reminder(evaluation_id: int, offset_days: int,
                      *, channel: str = "email", message: str = "") -> int:
    with transaction() as conn:
        cur = conn.execute(
            """INSERT INTO evaluation_reminders
               (evaluation_id, offset_days, channel, message)
               VALUES (?,?,?,?)""",
            (evaluation_id, offset_days, channel, message),
        )
        conn.commit()
        return cur.lastrowid


def list_reminders(evaluation_id: int) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT * FROM evaluation_reminders WHERE evaluation_id=?
               ORDER BY offset_days""",
            (evaluation_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def delete_reminder(reminder_id: int) -> None:
    with transaction() as conn:
        conn.execute("DELETE FROM evaluation_reminders WHERE reminder_id=?", (reminder_id,))
        conn.commit()


def due_reminders(now: datetime | None = None) -> list[dict]:
    """Reminders whose firing time (start_date + offset_days) has arrived
    and which have not yet been marked sent."""
    now = now or datetime.now()
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT r.*, e.start_date, e.module_code
               FROM evaluation_reminders r
               JOIN course_evaluations e ON e.evaluation_id = r.evaluation_id
               WHERE r.sent_at IS NULL AND e.start_date IS NOT NULL"""
        ).fetchall()
    out = []
    for r in rows:
        try:
            start = datetime.fromisoformat(r["start_date"])
        except ValueError:
            continue
        fire = start + timedelta(days=r["offset_days"])
        if fire <= now:
            out.append(dict(r))
    return out


def mark_reminder_sent(reminder_id: int) -> None:
    with transaction() as conn:
        conn.execute("UPDATE evaluation_reminders SET sent_at=datetime('now') "
                     "WHERE reminder_id=?", (reminder_id,))
        conn.commit()


# ---------- Bulk invitations + tokens (features 11, 12) ----------

def _new_token() -> str:
    return secrets.token_urlsafe(24)


def invite(evaluation_id: int, recipient_id: str, *, cohort: str = "") -> str:
    """Create one tokenised invitation. Returns the token."""
    token = _new_token()
    with transaction() as conn:
        conn.execute(
            """INSERT INTO evaluation_invitations
               (evaluation_id, recipient_id, cohort, token)
               VALUES (?,?,?,?)""",
            (evaluation_id, recipient_id, cohort, token),
        )
        conn.commit()
    return token


def bulk_invite(evaluation_id: int, recipients: Iterable[str],
                *, cohort: str = "") -> list[dict]:
    """Issue one token per recipient. Skips dupes."""
    issued: list[dict] = []
    with transaction() as conn:
        existing = {
            r[0] for r in conn.execute(
                "SELECT recipient_id FROM evaluation_invitations WHERE evaluation_id=?",
                (evaluation_id,),
            ).fetchall()
        }
        for rid in recipients:
            if not rid or rid in existing:
                continue
            token = _new_token()
            conn.execute(
                """INSERT INTO evaluation_invitations
                   (evaluation_id, recipient_id, cohort, token)
                   VALUES (?,?,?,?)""",
                (evaluation_id, rid, cohort, token),
            )
            existing.add(rid)
            issued.append({"recipient_id": rid, "token": token, "cohort": cohort})
        conn.commit()
    return issued


def resolve_token(token: str) -> dict | None:
    """Look up a token. Does NOT mark it used — call `consume_token` on submit."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM evaluation_invitations WHERE token=?", (token,),
        ).fetchone()
    return dict(row) if row else None


def consume_token(token: str) -> bool:
    with transaction() as conn:
        cur = conn.execute(
            "UPDATE evaluation_invitations SET used=1, used_at=datetime('now') "
            "WHERE token=? AND used=0",
            (token,),
        )
        conn.commit()
        return cur.rowcount == 1


def invitation_url(token: str, base_url: str = "https://eval.example.edu/r/") -> str:
    return f"{base_url}{token}"


# ---------- Roster (used by both invitations and response-rate) ----------

def set_roster(evaluation_id: int, student_ids: Iterable[str]) -> int:
    """Replace the roster snapshot for an evaluation. Returns count stored."""
    rows = [(evaluation_id, sid) for sid in {s for s in student_ids if s}]
    with transaction() as conn:
        conn.execute("DELETE FROM evaluation_rosters WHERE evaluation_id=?",
                     (evaluation_id,))
        conn.executemany(
            "INSERT OR IGNORE INTO evaluation_rosters (evaluation_id, student_id) VALUES (?,?)",
            rows,
        )
        conn.commit()
    return len(rows)


def get_roster(evaluation_id: int) -> list[str]:
    with get_connection() as conn:
        return [r[0] for r in conn.execute(
            "SELECT student_id FROM evaluation_rosters WHERE evaluation_id=? ORDER BY student_id",
            (evaluation_id,),
        ).fetchall()]


# ---------- QR codes (feature 13) ----------

def qr_for_token(token: str, *, base_url: str = "https://eval.example.edu/r/",
                 png_path: str | None = None) -> str:
    """Return either a PNG file path (if `qrcode` is installed and a path
    is given) or an ASCII-art rendering suitable for terminals/labels."""
    url = invitation_url(token, base_url)
    try:
        import qrcode  # type: ignore
    except ImportError:
        return _ascii_qr(url)

    img = qrcode.make(url)
    if png_path:
        img.save(png_path)
        return png_path
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return _ascii_qr(url)  # Always also return text for embedding in Tk


def _ascii_qr(url: str) -> str:
    """Tiny deterministic ASCII grid keyed on the URL. NOT a scannable QR —
    just a stable visual placeholder when the `qrcode` package is missing.
    The header line carries the real URL.
    """
    import hashlib
    h = hashlib.sha256(url.encode()).digest()
    rows = []
    rows.append(f"URL: {url}")
    rows.append("+" + "-" * 32 + "+")
    for r in range(16):
        line = "|"
        for c in range(32):
            bit = (h[(r * 32 + c) % len(h)] >> (c % 8)) & 1
            line += "█" if bit else " "
        line += "|"
        rows.append(line)
    rows.append("+" + "-" * 32 + "+")
    return "\n".join(rows)


# ---------- Embargo (feature 14) ----------

def set_embargo(evaluation_id: int, embargoed: bool) -> None:
    with transaction() as conn:
        conn.execute(
            "UPDATE course_evaluations SET embargo_until_grades=? WHERE evaluation_id=?",
            (1 if embargoed else 0, evaluation_id),
        )
        conn.commit()


def mark_grades_submitted(evaluation_id: int, when: datetime | None = None) -> None:
    when = (when or datetime.now()).isoformat()
    with transaction() as conn:
        conn.execute(
            "UPDATE course_evaluations SET grades_submitted_at=? WHERE evaluation_id=?",
            (when, evaluation_id),
        )
        conn.commit()


def results_visible(evaluation_id: int, *, viewer_role: str = "instructor") -> bool:
    """Instructors only see results after grades are submitted when embargoed.
    Admins always see them."""
    if viewer_role == "admin":
        return True
    with get_connection() as conn:
        row = conn.execute(
            "SELECT embargo_until_grades, grades_submitted_at FROM course_evaluations WHERE evaluation_id=?",
            (evaluation_id,),
        ).fetchone()
    if not row:
        return False
    if not row["embargo_until_grades"]:
        return True
    return bool(row["grades_submitted_at"])


__all__ = [
    "set_window", "auto_transition",
    "schedule_reminder", "list_reminders", "delete_reminder",
    "due_reminders", "mark_reminder_sent",
    "invite", "bulk_invite", "resolve_token", "consume_token", "invitation_url",
    "set_roster", "get_roster",
    "qr_for_token",
    "set_embargo", "mark_grades_submitted", "results_visible",
]
