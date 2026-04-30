"""Authorised absence on exam day → auto-deferred exam.

When the absence subsystem approves a request whose date covers a
scheduled exam (or whose ``is_missed_exam`` flag is set with an
``exam_id``), this module mirrors the user-facing "schedule resit"
flow that the Exam Scheduler's Deferred-Exams tab does interactively
— but headless, so it can fire from
``AbsenceTracker.decide_request`` and any other approval path.

Contract:

  defer_exam_for_authorised_absence(student_id, module_code,
                                    *, absence_date, exam_id=None,
                                    decided_by=None,
                                    default_offset_days=14,
                                    auto_attach=True) -> list[dict]

Returns one dict per affected exam:
  {original_exam_id, resit_exam_id, action: 'attached'|'created'|'skipped'}

Side-effects:
  * Inserts/updates rows in ``exams`` (resit row with
    parent_exam_id set, or roster appended).
  * Clones per-exam accommodations via the canonical
    ``accommodations.clone_exam_accommodation`` so extended-time and
    other arrangements carry over.
  * Fires ``EVENT_EXAM_CHANGED`` on the cross-GUI bus so any open
    Exam scheduler refreshes.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Any

from education_system.university_system.infrastructure.database.db import sqlite3, get_connection

logger = logging.getLogger(__name__)


def _parse_ids(raw: Any) -> list[str]:
    if not raw:
        return []
    if isinstance(raw, list):
        return [str(x) for x in raw]
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [str(x) for x in parsed]
    except Exception:
        pass
    return [s.strip() for s in str(raw).split(",") if s.strip()]


def _matching_exams_for_date(
    conn: sqlite3.Connection,
    *,
    student_id: str,
    module_code: str,
    on_date: str,
    exam_id: int | None,
) -> list[sqlite3.Row]:
    """Return the candidate exam rows that the absence overlaps.

    If the absence request explicitly carries ``exam_id`` we use it
    directly. Otherwise we look up exams scheduled on ``on_date`` for
    ``module_code`` whose roster includes ``student_id``.
    """
    if exam_id:
        rows = conn.execute(
            "SELECT id, module_code, module_name, date, start_time, end_time, "
            "       COALESCE(room,'') AS room, instructor_id, instructor_name, "
            "       enrolled_student_ids "
            "FROM exams WHERE id = ?",
            (int(exam_id),),
        ).fetchall()
        return list(rows)

    rows = conn.execute(
        "SELECT id, module_code, module_name, date, start_time, end_time, "
        "       COALESCE(room,'') AS room, instructor_id, instructor_name, "
        "       enrolled_student_ids "
        "FROM exams WHERE module_code = ? AND date = ?",
        (module_code, on_date),
    ).fetchall()
    out = []
    for r in rows:
        if str(student_id) in _parse_ids(r["enrolled_student_ids"]):
            out.append(r)
    return out


def _existing_resit(
    conn: sqlite3.Connection, original_exam_id: int
) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT id, enrolled_student_ids, students_enrolled, date, "
        "       start_time, end_time, room "
        "FROM exams WHERE parent_exam_id = ? "
        "ORDER BY date DESC LIMIT 1",
        (int(original_exam_id),),
    ).fetchone()


def _next_resit_date(orig_date: str, default_offset_days: int) -> str:
    """Pick a resit date: original + offset, or today + offset on parse error."""
    try:
        return (datetime.strptime(orig_date, "%Y-%m-%d")
                + timedelta(days=default_offset_days)).strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return (datetime.now() + timedelta(days=default_offset_days)).strftime("%Y-%m-%d")


def defer_exam_for_authorised_absence(
    student_id: str | int,
    module_code: str,
    *,
    absence_date: str,
    exam_id: int | None = None,
    decided_by: str | None = None,
    default_offset_days: int = 14,
    auto_attach: bool = True,
) -> list[dict[str, Any]]:
    """Mirror an authorised absence into deferred-exam rows.

    Idempotent — if the student is already on a resit for the matched
    exam, returns ``action='attached'`` without re-adding.
    """
    sid = str(student_id)
    results: list[dict[str, Any]] = []

    if not module_code or not absence_date:
        return results

    try:
        conn = get_connection()
    except Exception as exc:
        logger.warning("defer_exam_for_authorised_absence: connect failed: %s", exc)
        return results

    try:
        exams = _matching_exams_for_date(
            conn,
            student_id=sid,
            module_code=module_code,
            on_date=absence_date,
            exam_id=exam_id,
        )
        if not exams:
            return results

        # Pull accommodations once via the canonical service.
        try:
            from education_system.university_system.modules.domain.academics.gui.exam_management import (
                accommodations as accommodations_service,
            )
        except ImportError:
            accommodations_service = None

        for exam in exams:
            orig_id = exam["id"]
            orig_date = exam["date"]
            orig_st = exam["start_time"]
            orig_et = exam["end_time"]
            orig_room = exam["room"] or ""
            instr_id = exam["instructor_id"]
            instr_name = exam["instructor_name"] or ""
            mname = exam["module_name"] or module_code

            # Compute extended end time per the student's accommodations.
            resit_end = orig_et
            if accommodations_service is not None:
                try:
                    acc = accommodations_service.get_active_accommodations(
                        sid, exam_id=orig_id
                    )
                    resit_end = accommodations_service.compute_extended_end_time(
                        orig_st, orig_et, acc
                    )
                except Exception:
                    pass

            existing = _existing_resit(conn, orig_id)
            if auto_attach and existing:
                ids = _parse_ids(existing["enrolled_student_ids"])
                if sid in ids:
                    results.append({
                        "original_exam_id": orig_id,
                        "resit_exam_id": existing["id"],
                        "action": "skipped",
                        "note": "already on existing resit",
                    })
                    continue
                ids.append(sid)
                conn.execute(
                    "UPDATE exams SET enrolled_student_ids = ?, "
                    "students_enrolled = ?, updated_at = CURRENT_TIMESTAMP "
                    "WHERE id = ?",
                    (json.dumps(ids),
                     (existing["students_enrolled"] or 0) + 1,
                     existing["id"]),
                )
                conn.commit()
                if accommodations_service is not None:
                    try:
                        accommodations_service.clone_exam_accommodation(
                            sid, orig_id, existing["id"]
                        )
                    except Exception:
                        pass
                results.append({
                    "original_exam_id": orig_id,
                    "resit_exam_id": existing["id"],
                    "action": "attached",
                    "resit_date": existing["date"],
                })
                continue

            # No existing resit (or auto_attach=False) — create one.
            resit_date = _next_resit_date(orig_date, default_offset_days)
            resit_name = mname if "(Resit)" in mname else f"{mname} (Resit)"
            cur = conn.execute(
                "INSERT INTO exams "
                "(module_code, module_name, date, start_time, end_time, "
                " room, instructor_id, instructor_name, "
                " students_enrolled, enrolled_student_ids, "
                " parent_exam_id, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, "
                "        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
                (module_code, resit_name, resit_date, orig_st, resit_end,
                 orig_room, instr_id, instr_name,
                 json.dumps([sid]), orig_id),
            )
            conn.commit()
            new_id = cur.lastrowid
            if accommodations_service is not None:
                try:
                    accommodations_service.clone_exam_accommodation(
                        sid, orig_id, new_id
                    )
                except Exception:
                    pass
            results.append({
                "original_exam_id": orig_id,
                "resit_exam_id": new_id,
                "action": "created",
                "resit_date": resit_date,
                "decided_by": decided_by,
            })
    except Exception as exc:
        logger.warning(
            "defer_exam_for_authorised_absence(%s, %s, %s) failed: %s",
            sid, module_code, absence_date, exc,
        )
    finally:
        try:
            conn.close()
        except Exception:
            pass

    # Broadcast on the cross-GUI bus so any open Exam scheduler reloads.
    if results:
        try:
            from education_system.university_system.modules.domain.academics.gui._event_bus import (
                publish, EVENT_EXAM_CHANGED,
            )
            for r in results:
                if r["action"] in ("created", "attached"):
                    publish(EVENT_EXAM_CHANGED,
                            exam_id=r["resit_exam_id"],
                            module_code=module_code,
                            action=f"resit_{r['action']}")
        except Exception:
            pass

    # Bill the resit fee. Only on freshly created resits — re-attaching
    # to an existing resit means the student was already billed once.
    # A configurable per-module fee would live in a settings table; for
    # now we use a flat default the institution can override later.
    RESIT_FEE_DEFAULT = 50.00
    try:
        from education_system.university_system.modules.services.finance_bus import raise_charge
        for r in results:
            if r.get("action") == "created":
                raise_charge(
                    sid, RESIT_FEE_DEFAULT,
                    source="exam_resit",
                    description=(
                        f"Resit fee — {module_code} on {r.get('resit_date')}"
                    ),
                    reference_id=f"resit:{r['resit_exam_id']}",
                    processed_by="exam_deferral_processor",
                )
    except Exception as fee_err:
        logger.warning("resit fee billing failed: %s", fee_err)

    return results


__all__ = ["defer_exam_for_authorised_absence"]
