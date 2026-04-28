"""Bridge between the exam scheduler and student-support accommodations.

Accommodations live in two tables:

- ``student_accommodations`` — general approved accommodations across all
  assessments (extended_time with a ``time_multiplier``, alt_format,
  screen_reader, large_text, etc.). Filtered to ``is_active=1`` and not
  expired.
- ``exam_accommodations`` — exam-specific arrangements (``extended_time``
  in minutes, ``separate_room``, ``reader_scribe``,
  ``assistive_technology``) tied to an ``exam_id``. Filtered to
  ``status='active'``.

This module exposes a small service layer the deferred / scheduling
flows call to look up what arrangements apply to a student, compute the
adjusted end time for a resit, and copy exam-specific arrangements onto
a freshly-scheduled resit so the student-support team doesn't have to
re-enter them.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


def _connect():
    try:
        from education_system.university_system.infrastructure.database.db import get_connection
        return get_connection()
    except Exception as exc:
        logger.debug("DB unavailable for accommodations: %s", exc)
        return None


def get_active_accommodations(student_id, exam_id=None) -> Dict:
    """Return a merged view of a student's active accommodations.

    The returned dict has:
      ``time_multiplier``  — float, default 1.0; max across general
                              ``student_accommodations.extended_time``
                              entries.
      ``extended_minutes`` — int, default 0; from the matching
                              ``exam_accommodations`` row when *exam_id*
                              is given.
      ``separate_room``    — bool.
      ``reader_scribe``    — bool.
      ``assistive_tech``   — str (free-text), or "".
      ``general``          — list of {type, details, time_multiplier}
                              from student_accommodations.
      ``exam_specific``    — dict copied from exam_accommodations or {}.
    """
    out = {
        "time_multiplier": 1.0,
        "extended_minutes": 0,
        "separate_room": False,
        "reader_scribe": False,
        "assistive_tech": "",
        "general": [],
        "exam_specific": {},
    }
    conn = _connect()
    if conn is None:
        return out

    try:
        # General accommodations
        for row in conn.execute(
            """SELECT accommodation_type, details, time_multiplier,
                      expires_at
               FROM student_accommodations
               WHERE student_id = ?
                 AND is_active = 1
                 AND (expires_at IS NULL OR expires_at >= date('now'))""",
            (str(student_id),),
        ).fetchall():
            atype, details, mult, _exp = row
            out["general"].append({
                "type": atype, "details": details or "",
                "time_multiplier": mult or 1.0,
            })
            if atype == "extended_time" and mult and mult > out["time_multiplier"]:
                out["time_multiplier"] = float(mult)

        # Exam-specific accommodations
        if exam_id is not None:
            es = conn.execute(
                """SELECT extended_time, separate_room, reader_scribe,
                          assistive_technology
                   FROM exam_accommodations
                   WHERE student_id = ? AND exam_id = ?
                     AND COALESCE(status, 'active') = 'active'
                   ORDER BY accommodation_id DESC LIMIT 1""",
                (str(student_id), exam_id),
            ).fetchone()
            if es:
                ext, sep, rs, tech = es
                out["extended_minutes"] = int(ext or 0)
                out["separate_room"] = bool(sep)
                out["reader_scribe"] = bool(rs)
                out["assistive_tech"] = tech or ""
                out["exam_specific"] = {
                    "extended_time": int(ext or 0),
                    "separate_room": bool(sep),
                    "reader_scribe": bool(rs),
                    "assistive_technology": tech or "",
                }
        return out
    except Exception as exc:
        logger.debug("get_active_accommodations failed: %s", exc)
        return out
    finally:
        try:
            conn.close()
        except Exception:
            pass


def compute_extended_end_time(start_time: str, base_end_time: str,
                              acc: Dict) -> str:
    """Adjust ``base_end_time`` for the accommodation in *acc*.

    Applies (in order):
    1. ``extended_minutes`` — add as flat minutes.
    2. ``time_multiplier`` — extend the (start→end) duration by the
       multiplier when > 1.0.

    Returns the new ``HH:MM`` string. Falls back to ``base_end_time`` on
    parse errors.
    """
    try:
        start = datetime.strptime(start_time, "%H:%M")
        end = datetime.strptime(base_end_time, "%H:%M")
        if end <= start:
            return base_end_time
        extra = timedelta(minutes=int(acc.get("extended_minutes") or 0))
        mult = float(acc.get("time_multiplier") or 1.0)
        if mult > 1.0:
            duration = end - start
            extra += duration * (mult - 1.0)
        new_end = end + extra
        return new_end.strftime("%H:%M")
    except Exception as exc:
        logger.debug("compute_extended_end_time failed: %s", exc)
        return base_end_time


def clone_exam_accommodation(student_id, original_exam_id,
                             new_exam_id) -> bool:
    """Copy an active ``exam_accommodations`` row from the original exam
    onto the new resit so student-support arrangements carry over.

    Returns True if a row was copied (or there was nothing to copy).
    """
    conn = _connect()
    if conn is None:
        return False
    try:
        with conn:
            row = conn.execute(
                """SELECT extended_time, separate_room, reader_scribe,
                          assistive_technology, notes
                   FROM exam_accommodations
                   WHERE student_id = ? AND exam_id = ?
                     AND COALESCE(status,'active') = 'active'
                   ORDER BY accommodation_id DESC LIMIT 1""",
                (str(student_id), original_exam_id),
            ).fetchone()
            if not row:
                return True  # nothing to copy — not an error

            ext, sep, rs, tech, notes = row
            # Avoid duplicates if the resit already has an accommodation row
            existing = conn.execute(
                """SELECT 1 FROM exam_accommodations
                   WHERE student_id = ? AND exam_id = ?
                     AND COALESCE(status,'active') = 'active'""",
                (str(student_id), new_exam_id),
            ).fetchone()
            if existing:
                return True

            conn.execute(
                """INSERT INTO exam_accommodations
                   (student_id, exam_id, extended_time, separate_room,
                    reader_scribe, assistive_technology, status, notes)
                   VALUES (?, ?, ?, ?, ?, ?, 'active', ?)""",
                (str(student_id), new_exam_id, ext, sep, rs, tech,
                 (notes or "") + " [carried over from resit]"),
            )
        return True
    except Exception as exc:
        logger.error("clone_exam_accommodation failed: %s", exc)
        return False


def summarize_accommodations(acc: Dict) -> List[str]:
    """Return human-readable bullets describing the active accommodations."""
    bullets: List[str] = []
    if acc.get("time_multiplier", 1.0) > 1.0:
        bullets.append(f"Extended time × {acc['time_multiplier']}")
    if acc.get("extended_minutes"):
        bullets.append(f"+{acc['extended_minutes']} min on this exam")
    if acc.get("separate_room"):
        bullets.append("Separate room required")
    if acc.get("reader_scribe"):
        bullets.append("Reader / scribe")
    if acc.get("assistive_tech"):
        bullets.append(f"Assistive tech: {acc['assistive_tech']}")
    for g in acc.get("general", []):
        if g["type"] != "extended_time":
            label = g["type"].replace("_", " ").title()
            if g.get("details"):
                label += f" — {g['details']}"
            bullets.append(label)
    return bullets
