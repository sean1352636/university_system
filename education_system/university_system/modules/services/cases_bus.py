"""Unified case spine for Academic Misconduct + Disciplinary Portal.

Both subsystems run the same lifecycle (open → investigate → hear →
sanction → close) against the same kind of subject (student or
staff). They write to different tables today (``academic_misconduct_cases``
and ``disciplinary_records``) for back-compat; this module unifies the
read side and offers a single sanction-application path.

Public surface:

* ``open_case(kind, subject_id, ...)`` — write a row, publish
  ``EVENT_CASE_OPENED``. ``kind='academic_misconduct'`` writes to the
  AM table; anything else (``'disciplinary'``, ``'staff'``) writes to
  ``disciplinary_records``. If ``assignment_submission_id`` is given on
  an academic-misconduct case, the submission is held (#x).
* ``close_case(kind, case_id, outcome)`` — set status, publish
  ``EVENT_CASE_CLOSED``.
* ``apply_sanction(case_id, kind, sanction_type, ...)`` — central
  router that fans out into Finance / cert_bus / DM:
  - ``fine``        → ``raise_charge``
  - ``suspension``  → ``place_hold``
  - ``cert_revoke`` → ``cert_bus.delete_certification``
  Each fan-out preserves the gates / events of its target subsystem.
* ``list_open(subject_id)`` — UNION over both tables.
* ``schedule_hearing(case_id, kind, when, panel_member_ids)`` —
  validates panel availability via HR's ``is_available_on``; persists
  to the calendar as an ``event_type='hearing'`` row.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from education_system.university_system.infrastructure.database.db import (
    sqlite3, get_connection,
)

logger = logging.getLogger(__name__)


_AM_KIND = "academic_misconduct"


def _publish(event: str, **payload: Any) -> None:
    try:
        from education_system.university_system.modules.domain.academics.gui._event_bus import publish
        publish(event, **payload)
    except Exception as exc:
        logger.debug("cases bus publish failed: %s", exc)


# ---------------------------------------------------------------------------
# Open
# ---------------------------------------------------------------------------

def open_case(
    *,
    kind: str,
    subject_id: str | int,
    opened_by: str | int | None = None,
    description: str = "",
    severity: str = "Minor",
    offense_type: str = "Other",
    assignment_submission_id: int | None = None,
    incident_date: str | None = None,
    location: str | None = None,
) -> int | None:
    """Create a new case row and broadcast.

    Returns the inserted ``case_id`` / ``record_id`` depending on
    target table. ``assignment_submission_id`` only applies to AM
    cases; when given the corresponding submission is held.
    """
    if not subject_id or not kind:
        return None
    today = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_id: int | None = None
    try:
        with get_connection() as conn:
            if kind == _AM_KIND:
                # Look up the student's name + course — the AM table
                # has them NOT NULL. Fall back to the subject_id /
                # 'Unknown' when we can't resolve real values.
                student_name = str(subject_id)
                course = "Unknown"
                try:
                    row = conn.execute(
                        "SELECT TRIM(COALESCE(first_name,'') || ' ' || "
                        "             COALESCE(last_name,'')) AS name, "
                        "       COALESCE(course, 'Unknown') AS course "
                        "FROM students WHERE student_id = ?",
                        (str(subject_id),),
                    ).fetchone()
                    if row:
                        student_name = row["name"] or student_name
                        course = row["course"] or course
                except sqlite3.OperationalError:
                    pass

                # Generate a human-readable case_id alongside the row.
                ref = f"AM-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                cur = conn.execute(
                    "INSERT INTO academic_misconduct_cases "
                    "(case_id, student_name, student_id, course, "
                    " violation_type, status, date_filed, severity, notes) "
                    "VALUES (?, ?, ?, ?, ?, 'Under Review', ?, ?, ?)",
                    (ref, student_name, str(subject_id), course,
                     offense_type,
                     (incident_date or today)[:10], severity,
                     description),
                )
                new_id = cur.lastrowid
            else:
                cur = conn.execute(
                    "INSERT INTO disciplinary_records "
                    "(user_id, offense_type, severity, description, "
                    " date_occurred, date_reported, reported_by, "
                    " location, status) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Open')",
                    (str(subject_id), offense_type, severity,
                     description,
                     (incident_date or today)[:10], today[:10],
                     str(opened_by or ""), location or ""),
                )
                new_id = cur.lastrowid
            conn.commit()
    except Exception as exc:
        logger.warning("open_case(%s) failed: %s", kind, exc)
        return None

    # Hold the linked assignment submission while AM is open (#x).
    if kind == _AM_KIND and assignment_submission_id:
        try:
            with get_connection() as conn:
                conn.execute(
                    "UPDATE assignment_submissions "
                    "SET status = 'held' WHERE id = ?",
                    (int(assignment_submission_id),),
                )
                conn.commit()
            try:
                from education_system.university_system.modules.domain.academics.gui._event_bus import (
                    publish, EVENT_GRADE_CHANGED,
                )
                publish(EVENT_GRADE_CHANGED,
                        submission_id=assignment_submission_id,
                        action="held_for_misconduct",
                        case_id=new_id, source="cases_bus")
            except Exception:
                pass
        except Exception as exc:
            logger.warning("submission-hold for AM failed: %s", exc)

    _publish(
        "case.opened",
        case_id=new_id, kind=kind,
        subject_id=str(subject_id), opened_by=opened_by,
        severity=severity, offense_type=offense_type,
    )

    # Cross-domain: high-severity cases (and every security incident)
    # auto-raise a row in the risk register so the legal/risk GUI
    # surfaces live operational risk fed by real events, not just
    # admin entry. Reference back to this case so close_case can
    # fold them when the incident is resolved.
    try:
        sev_norm = (severity or "").strip().lower()
        is_security = (kind or "").lower() == "security_incident"
        if is_security or sev_norm in ("high", "critical", "severe"):
            from education_system.university_system.modules.services import (
                risk_bus,
            )
            cat = "Safety" if is_security else "Compliance"
            risk_bus.raise_risk(
                title=f"{kind} #{new_id}: {offense_type or 'incident'}",
                category=cat,
                department="Security" if is_security else "Compliance",
                description=description or "",
                likelihood=4 if sev_norm in ("critical", "severe") else 3,
                impact=5 if sev_norm in ("critical", "severe")
                       else (4 if sev_norm == "high" else 3),
                owner=str(opened_by) if opened_by else None,
                reference_id=f"case:{new_id}",
            )
    except Exception as exc:
        logger.debug("risk auto-raise from case failed: %s", exc)

    return new_id


# ---------------------------------------------------------------------------
# Close
# ---------------------------------------------------------------------------

def close_case(*, kind: str, case_id: int,
               outcome: str = "closed") -> bool:
    if not case_id:
        return False
    try:
        with get_connection() as conn:
            if kind == _AM_KIND:
                conn.execute(
                    "UPDATE academic_misconduct_cases "
                    "SET status = 'Closed', ruling = ?, "
                    "    updated_at = CURRENT_TIMESTAMP "
                    "WHERE id = ?",
                    (outcome, int(case_id)),
                )
            else:
                conn.execute(
                    "UPDATE disciplinary_records "
                    "SET status = 'Resolved', "
                    "    updated_at = CURRENT_TIMESTAMP "
                    "WHERE record_id = ?",
                    (int(case_id),),
                )
            conn.commit()
    except Exception as exc:
        logger.warning("close_case(%s, %s) failed: %s", kind, case_id, exc)
        return False

    _publish("case.closed", case_id=case_id, kind=kind, outcome=outcome)

    # Cross-domain: fold any auto-raised risk-register entries.
    try:
        from education_system.university_system.modules.services import (
            risk_bus,
        )
        risk_bus.close_risks_for_reference(
            f"case:{case_id}", outcome="case_closed"
        )
    except Exception as exc:
        logger.debug("risk close from case failed: %s", exc)

    return True


# ---------------------------------------------------------------------------
# Sanctions — fan out into the existing Finance / cert / hold paths
# ---------------------------------------------------------------------------

def apply_sanction(
    *,
    case_id: int,
    kind: str,
    sanction_type: str,
    subject_id: str | int,
    amount: float | None = None,
    duration_days: int | None = None,
    cert_id: int | None = None,
    reason: str | None = None,
    applied_by: str | None = None,
) -> dict[str, Any]:
    """Route a sanction into the right subsystem.

    Sanction types:
      * ``fine``        — calls finance_bus.raise_charge
      * ``suspension``  — calls finance_bus.place_hold (acts as the
                         enrolment block)
      * ``cert_revoke`` — calls cert_bus.delete_certification
      * ``warning``     — bus-only, no side-effect

    Returns ``{ok, side_effects: {...}, errors: [...]}`` so the caller
    can render a summary. Always publishes ``EVENT_SANCTION_APPLIED``.
    """
    out: dict[str, Any] = {"ok": True, "side_effects": {}, "errors": []}
    st = (sanction_type or "").lower()

    if st == "fine":
        try:
            from education_system.university_system.modules.services.finance_bus import (
                raise_charge,
            )
            tx = raise_charge(
                subject_id, float(amount or 0),
                source="misconduct_fine",
                description=(
                    f"Misconduct fine — {kind} case #{case_id}"
                    + (f" ({reason})" if reason else "")
                ),
                reference_id=f"case:{case_id}",
                processed_by=applied_by,
            )
            out["side_effects"]["charge_tx"] = tx
        except Exception as exc:
            out["errors"].append(f"fine failed: {exc}")
            out["ok"] = False

    elif st == "suspension":
        try:
            from education_system.university_system.modules.services.finance_bus import (
                place_hold,
            )
            hid = place_hold(
                subject_id,
                reason=(
                    f"Disciplinary suspension"
                    + (f" — {reason}" if reason else "")
                ),
                source="dp_suspension",
                amount=0.0,
                reference_id=f"case:{case_id}",
                placed_by=applied_by,
            )
            out["side_effects"]["hold_id"] = hid
            if duration_days:
                out["side_effects"]["expected_release_in_days"] = duration_days
        except Exception as exc:
            out["errors"].append(f"suspension failed: {exc}")
            out["ok"] = False

    elif st in ("cert_revoke", "revoke_cert"):
        try:
            from education_system.university_system.modules.services.cert_bus import (
                delete_certification,
            )
            ok = bool(cert_id) and delete_certification(int(cert_id))
            out["side_effects"]["cert_revoked"] = ok
            if cert_id and not ok:
                out["errors"].append("cert revocation failed (already inactive?)")
        except Exception as exc:
            out["errors"].append(f"cert_revoke failed: {exc}")
            out["ok"] = False

    elif st == "warning":
        out["side_effects"]["recorded"] = True

    else:
        out["errors"].append(f"unknown sanction type: {sanction_type}")
        out["ok"] = False

    _publish(
        "case.sanction.applied",
        case_id=case_id, kind=kind,
        sanction_type=st, subject_id=str(subject_id),
        amount=amount, duration_days=duration_days, cert_id=cert_id,
        reason=reason, applied_by=applied_by,
        ok=out["ok"],
    )
    return out


# ---------------------------------------------------------------------------
# Read (UNION across both tables)
# ---------------------------------------------------------------------------

def list_open(subject_id: str | int | None = None) -> list[dict[str, Any]]:
    """Return open cases — both AM and DP — for ``subject_id``.

    If ``subject_id`` is None, returns all open cases system-wide.
    """
    out: list[dict[str, Any]] = []
    try:
        with get_connection() as conn:
            tables = {
                r[0] for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            if "academic_misconduct_cases" in tables:
                params: list[Any] = []
                sql = (
                    "SELECT id AS case_id, 'academic_misconduct' AS kind, "
                    "       student_id AS subject_id, "
                    "       violation_type AS offense_type, "
                    "       severity, status, date_filed AS opened_on, "
                    "       hearing_date "
                    "FROM academic_misconduct_cases "
                    "WHERE LOWER(COALESCE(status,'open')) "
                    "      NOT IN ('closed','resolved','dismissed') "
                )
                if subject_id is not None:
                    sql += "AND student_id = ? "
                    params.append(str(subject_id))
                sql += "ORDER BY date_filed DESC"
                for r in conn.execute(sql, tuple(params)).fetchall():
                    out.append(dict(r))
            if "disciplinary_records" in tables:
                params2: list[Any] = []
                sql = (
                    "SELECT record_id AS case_id, 'disciplinary' AS kind, "
                    "       user_id AS subject_id, offense_type, severity, "
                    "       status, date_reported AS opened_on, "
                    "       NULL AS hearing_date "
                    "FROM disciplinary_records "
                    "WHERE LOWER(COALESCE(status,'open')) "
                    "      NOT IN ('closed','resolved','dismissed') "
                )
                if subject_id is not None:
                    sql += "AND user_id = ? "
                    params2.append(str(subject_id))
                sql += "ORDER BY date_reported DESC"
                for r in conn.execute(sql, tuple(params2)).fetchall():
                    out.append(dict(r))
    except Exception as exc:
        logger.warning("list_open(%s) failed: %s", subject_id, exc)
    return out


# ---------------------------------------------------------------------------
# Hearing scheduling — Calendar event + HR availability gate
# ---------------------------------------------------------------------------

def schedule_hearing(
    *,
    case_id: int,
    kind: str,
    when: str,                        # YYYY-MM-DD
    duration_minutes: int = 60,
    panel_member_ids: list | None = None,
    support_attendee_ids: list | None = None,
    location: str | None = None,
    scheduled_by: str | None = None,
) -> dict[str, Any]:
    """Persist a hearing as an academic_calendar_events row + gate panel.

    Refuses if any panel member or support attendee (e.g. SU rep)
    has approved leave covering the date. Returns ``{ok, event_id,
    blocked_by: [ids]}``.
    """
    out: dict[str, Any] = {"ok": True, "event_id": None, "blocked_by": []}
    if not when:
        return {"ok": False, "event_id": None, "blocked_by": [],
                "reason": "date required"}

    # HR availability gate (#10) — extended to cover SU support
    # attendees so the hearing isn't booked when the assigned advocate
    # is on leave either.
    panel = list(panel_member_ids or [])
    attendees = list(support_attendee_ids or [])
    try:
        from education_system.university_system.modules.services.staff_hr_bus import (
            is_available_on,
        )
        for pid in panel + attendees:
            if not is_available_on(pid, when):
                out["blocked_by"].append(pid)
        if out["blocked_by"]:
            out["ok"] = False
            out["reason"] = (
                f"panel/attendee(s) on approved leave: "
                f"{', '.join(map(str, out['blocked_by']))}"
            )
            return out
    except Exception:
        pass  # soft-fail open

    try:
        import uuid
        event_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        with get_connection() as conn:
            descr_bits = [f"Panel: {', '.join(map(str, panel))}"]
            if attendees:
                descr_bits.append(
                    f"Support: {', '.join(map(str, attendees))}"
                )
            descr_bits.append(f"Location: {location or 'TBD'}")
            descr_bits.append(f"Duration: {duration_minutes}m")
            conn.execute(
                "INSERT INTO academic_calendar_events "
                "(id, name, date, description, event_type, "
                " date_added, last_modified, created_by) "
                "VALUES (?, ?, ?, ?, 'hearing', ?, ?, ?)",
                (event_id,
                 f"{kind} hearing — case #{case_id}",
                 when[:10],
                 "; ".join(descr_bits),
                 now, now, scheduled_by),
            )
            conn.commit()
        out["event_id"] = event_id
        try:
            from education_system.university_system.modules.domain.academics.gui._event_bus import (
                publish, EVENT_CALENDAR_CHANGED,
            )
            publish(EVENT_CALENDAR_CHANGED, event_id=event_id,
                    event_type="hearing", action="created",
                    date=when[:10])
        except Exception:
            pass
    except Exception as exc:
        out["ok"] = False
        out["reason"] = str(exc)
    return out


__all__ = [
    "open_case", "close_case", "apply_sanction",
    "list_open", "schedule_hearing",
]
