"""Cross-module integration bus for the six university subsystems.

Wires Clearing/Adjustment, Module Scheduling, Course Management,
Staff HR, KPI Dashboard, and Finance Reporting through the shared
academic event bus. One module, one place to audit.

Three responsibilities:

1. Owns ``integration_log`` (every cross-module event lands here so
   ops can debug missed fan-outs and the KPI dashboard can render an
   activity widget without scraping per-module logs).
2. Exposes ``publish_*`` helpers each origin service can call without
   importing every consumer's schema.
3. Registers ``wire_subscribers()`` — the single entry point that
   subscribes the consumer side of every cross-module feature.
   Idempotent and safe to call from any process startup hook.

All handlers fail-open: a broken consumer must never block the
writer that triggered the event.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta
from typing import Any

from education_system.university_system.infrastructure.database.db import (
    get_connection,
    transaction,
)
from education_system.university_system.modules.domain.academics.gui._event_bus import (
    EVENT_CASE_OPENED,
    EVENT_CERT_CHANGED,
    EVENT_CHARGE_RAISED,
    EVENT_COURSE_CHANGED,
    EVENT_ENROLMENT_CHANGED,
    EVENT_EXAM_CHANGED,
    EVENT_INCIDENT_LOGGED,
    EVENT_MODULE_SCHEDULE_CHANGED,
    EVENT_SELECTION_CHANGED,
    EVENT_STAFF_AVAILABILITY_CHANGED,
    EVENT_TERM_CHANGED,
    publish,
    subscribe,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Schema — integration_log table
# ---------------------------------------------------------------------------

_LOG_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS integration_log (
    log_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    event_name    TEXT NOT NULL,
    source_module TEXT NOT NULL,
    payload_json  TEXT NOT NULL,
    created_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
)
"""

_LOG_INDEX_SQL = (
    "CREATE INDEX IF NOT EXISTS idx_integration_log_event "
    "ON integration_log(event_name, created_at DESC)"
)


def _ensure_log_table() -> None:
    try:
        with get_connection() as conn:
            conn.executescript(_LOG_SCHEMA_SQL)
            conn.execute(_LOG_INDEX_SQL)
            conn.commit()
    except Exception as exc:
        logger.debug("integration_log table init failed: %s", exc)


# ---------------------------------------------------------------------------
# Payload contracts — keep the keys here so consumers don't drift
# ---------------------------------------------------------------------------
#
# EVENT_COURSE_CHANGED payload shapes used by this module:
#   {action: "clearing_accepted", student_ref, course_code, year}
#   {action: "adjustment_approved", student_id, from_course, to_course}
#   {action: "waitlist_promoted",   student_id, course_code, plan_id}
#   {action: "demand_forecast",     course_code, predicted_enrollment, year}
#
# EVENT_MODULE_SCHEDULE_CHANGED:
#   {action: "timetable_locked", user_ids: [...], academic_year}
#   {action: "enrollment_delta", course_code, delta}
#
# EVENT_STAFF_AVAILABILITY_CHANGED:
#   {staff_id, action: "approved"|"cancelled"|"updated", start_date, end_date,
#    leave_type, source: "leave"|"sabbatical"|"sickness"}
#
# EVENT_CERT_CHANGED:
#   {user_id, training_id, expiry_date, days_to_expiry, role_critical: bool}
#
# EVENT_CHARGE_RAISED is published by finance_bus.raise_charge directly.
# This module subscribes only.


def log_and_publish(event: str, *, source: str, **payload: Any) -> None:
    """Record the event in ``integration_log`` then fan out via the bus.

    Best-effort logging — a logging failure must never silence the
    publish.
    """
    try:
        _ensure_log_table()
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO integration_log (event_name, source_module, payload_json) "
                "VALUES (?, ?, ?)",
                (event, source, json.dumps(payload, default=str)),
            )
            conn.commit()
    except Exception as exc:
        logger.debug("integration_log write failed (%s): %s", event, exc)
    publish(event, **payload)


def recent_events(limit: int = 50) -> list[dict[str, Any]]:
    """Return the most recent integration events. Used by the KPI activity widget."""
    _ensure_log_table()
    try:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT log_id, event_name, source_module, payload_json, created_at "
                "FROM integration_log ORDER BY log_id DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
            out = []
            for r in rows:
                d = dict(r)
                try:
                    d["payload"] = json.loads(d.pop("payload_json"))
                except Exception:
                    d["payload"] = {}
                out.append(d)
            return out
    except Exception as exc:
        logger.warning("recent_events failed: %s", exc)
        return []


# ---------------------------------------------------------------------------
# Identity resolver — bridges student_id ↔ ucas_id ↔ user_id
# ---------------------------------------------------------------------------

def resolve_student_id(*, ucas_id: str | None = None,
                       application_id: int | None = None) -> str | None:
    """Resolve a clearing applicant to a real student_id, if one exists.

    Falls through gracefully when the link tables aren't present —
    callers (e.g. clearing acceptance) treat None as "create-on-demand
    elsewhere" rather than a hard error.
    """
    try:
        with get_connection() as conn:
            if ucas_id:
                row = conn.execute(
                    "SELECT student_id FROM students WHERE ucas_id = ? LIMIT 1",
                    (str(ucas_id),),
                ).fetchone()
                if row and row[0]:
                    return str(row[0])
            if application_id is not None:
                row = conn.execute(
                    "SELECT ucas_id, applicant_name FROM clearing_applications "
                    "WHERE id = ?",
                    (int(application_id),),
                ).fetchone()
                if row:
                    return f"clearing:{application_id}"  # opaque ref
    except Exception as exc:
        logger.debug("resolve_student_id failed: %s", exc)
    return None


# ---------------------------------------------------------------------------
# Publishers — origin services call these
# ---------------------------------------------------------------------------

def publish_clearing_accepted(application_id: int, *, course_code: str,
                              ucas_id: str | None = None,
                              applicant_name: str | None = None,
                              academic_year: str | None = None) -> None:
    """Feature 1: clearing acceptance fan-out.

    Triggered by ClearingAdjustmentService.update_application_status('accepted').
    """
    student_ref = (
        resolve_student_id(ucas_id=ucas_id, application_id=application_id)
        or f"clearing:{application_id}"
    )
    log_and_publish(
        EVENT_COURSE_CHANGED,
        source="clearing_adjustment",
        action="clearing_accepted",
        application_id=int(application_id),
        student_ref=student_ref,
        ucas_id=ucas_id,
        applicant_name=applicant_name,
        course_code=course_code,
        academic_year=academic_year or _current_year(),
    )


def publish_adjustment_approved(request_id: int, *, student_id: str,
                                from_course: str, to_course: str) -> None:
    """Feature 3: adjustment approved fan-out."""
    log_and_publish(
        EVENT_COURSE_CHANGED,
        source="clearing_adjustment",
        action="adjustment_approved",
        request_id=int(request_id),
        student_id=str(student_id),
        from_course=from_course,
        to_course=to_course,
    )


def publish_apl_approved(claim_id: int, *, student_id: str,
                         credits_awarded: int,
                         claim_type: str | None = None,
                         decision: str = "approved",
                         target_course: str | None = None) -> None:
    """APL/RPL claim decision fan-out.

    Triggered by ``PriorLearningService.review_claim`` when the
    decision is ``approved`` or ``partial``. Logged on
    ``EVENT_COURSE_CHANGED`` so HESA Export, External QA, and degree
    audit subscribers can pick it up without the APL module having to
    know who's listening.
    """
    log_and_publish(
        EVENT_COURSE_CHANGED,
        source="prior_learning_recognition",
        action="apl_approved",
        claim_id=int(claim_id),
        student_id=str(student_id),
        credits_awarded=int(credits_awarded or 0),
        claim_type=claim_type,
        decision=decision,
        target_course=target_course,
    )


def publish_leave_decision(staff_id: str, *, action: str,
                           start_date: str | None = None,
                           end_date: str | None = None,
                           leave_type: str | None = None,
                           source: str = "leave") -> None:
    """Feature 2: leave/sabbatical/sickness fan-out."""
    log_and_publish(
        EVENT_STAFF_AVAILABILITY_CHANGED,
        source="staff_hr",
        staff_id=str(staff_id),
        action=action,
        start_date=start_date,
        end_date=end_date,
        leave_type=leave_type,
        source_kind=source,
    )


def publish_timetable_locked(user_ids: list[str], *, academic_year: str | None = None,
                             semester: str | None = None) -> None:
    """Feature 4: lock-down fan-out."""
    log_and_publish(
        EVENT_MODULE_SCHEDULE_CHANGED,
        source="module_scheduling",
        action="timetable_locked",
        user_ids=[str(u) for u in user_ids],
        academic_year=academic_year or _current_year(),
        semester=semester,
    )


def publish_demand_forecast(course_code: str, *, predicted_enrollment: int,
                            academic_year: str | None = None) -> None:
    """Feature 6: KPI → clearing vacancy planner."""
    log_and_publish(
        EVENT_COURSE_CHANGED,
        source="kpi_dashboard",
        action="demand_forecast",
        course_code=course_code,
        predicted_enrollment=int(predicted_enrollment),
        academic_year=academic_year or _current_year(),
    )


def publish_appraisal_completed(user_id: str, *, cycle_id: int,
                                rating: float) -> None:
    """Feature 7: appraisal → merit-pay proposal."""
    log_and_publish(
        EVENT_SELECTION_CHANGED,
        source="staff_hr",
        action="appraisal_completed",
        user_id=str(user_id),
        cycle_id=int(cycle_id),
        rating=float(rating),
    )


def publish_cert_expiry(user_id: str, *, training_id: int | None,
                        cert_name: str, expiry_date: str,
                        role_critical: bool = False) -> None:
    """Feature 8: certification expiry alert."""
    try:
        days = (datetime.strptime(expiry_date[:10], "%Y-%m-%d").date()
                - date.today()).days
    except Exception:
        days = None
    log_and_publish(
        EVENT_CERT_CHANGED,
        source="staff_hr",
        user_id=str(user_id),
        training_id=training_id,
        cert_name=cert_name,
        expiry_date=expiry_date,
        days_to_expiry=days,
        role_critical=bool(role_critical),
    )


def publish_waitlist_promoted(student_id: str, *, course_code: str,
                              plan_id: int | None = None,
                              fee_amount: float | None = None) -> None:
    """Feature 9: waitlist atomic enrol+bill (publish step)."""
    log_and_publish(
        EVENT_COURSE_CHANGED,
        source="course_management",
        action="waitlist_promoted",
        student_id=str(student_id),
        course_code=course_code,
        plan_id=plan_id,
        fee_amount=fee_amount,
    )


# ---------------------------------------------------------------------------
# Feature 1 — Clearing acceptance → capacity decrement + fee + KPI
# ---------------------------------------------------------------------------

def _on_clearing_accepted(**payload: Any) -> None:
    if payload.get("action") != "clearing_accepted":
        return
    course_code = payload.get("course_code")
    student_ref = payload.get("student_ref") or ""
    year = payload.get("academic_year")

    # Module Scheduling: drop one seat from any matching module_schedule row.
    try:
        with transaction() as conn:
            tbl = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='module_schedule'"
            ).fetchone()
            if tbl:
                conn.execute(
                    "UPDATE module_schedule "
                    "SET enrolled = COALESCE(enrolled, 0) + 1 "
                    "WHERE module_code = ?",
                    (course_code,),
                )
                conn.commit()
    except Exception as exc:
        logger.debug("clearing→scheduling capacity update failed: %s", exc)

    # Finance: raise the program fee charge if we have a real student_id.
    if student_ref and not student_ref.startswith("clearing:"):
        try:
            from education_system.university_system.modules.services.finance_bus import (
                raise_charge,
            )
            fee = _lookup_program_fee(course_code, year)
            if fee and fee > 0:
                raise_charge(
                    student_ref, fee,
                    source="clearing",
                    description=f"Tuition: {course_code} {year}",
                    reference_id=f"clearing:{payload.get('application_id')}",
                )
        except Exception as exc:
            logger.debug("clearing→finance charge failed: %s", exc)

    # KPI: bump enrolment counter for the year.
    _bump_kpi(category="enrollment", increment=1)


# ---------------------------------------------------------------------------
# Feature 2 — Leave approved → cover request + payroll prorate
# ---------------------------------------------------------------------------

def _on_staff_availability_changed(**payload: Any) -> None:
    if payload.get("action") not in ("approved", "cancelled"):
        return
    staff_id = payload.get("staff_id")
    start = payload.get("start_date")
    end = payload.get("end_date")
    if not (staff_id and start and end):
        return

    if payload.get("action") == "approved":
        # CoverManager: open a cover request for each affected day.
        try:
            from education_system.university_system.modules.domain.staff_comms.staff_hr.services.managers.cover_manager import (
                CoverManager,
            )
            for d in _date_range(start, end):
                try:
                    CoverManager.create_request(
                        requester_id=str(staff_id),
                        cover_date=d,
                        reason=f"{payload.get('source_kind', 'leave')} approved",
                        priority="normal",
                    )
                except Exception as exc:
                    logger.debug("cover create failed for %s: %s", d, exc)
        except Exception as exc:
            logger.debug("cover_manager unavailable: %s", exc)

        # Payroll: tag the affected period(s) so prorate calc picks them up.
        _tag_payroll_leave(str(staff_id), start, end,
                           leave_type=payload.get("leave_type"))


# ---------------------------------------------------------------------------
# Feature 3 — Adjustment approved → re-plan + finance credit/debit pair
# ---------------------------------------------------------------------------

def _on_adjustment_approved(**payload: Any) -> None:
    if payload.get("action") != "adjustment_approved":
        return
    student_id = payload.get("student_id")
    from_course = payload.get("from_course")
    to_course = payload.get("to_course")
    request_id = payload.get("request_id")
    if not (student_id and from_course and to_course):
        return

    # Course Management: swap the entry in plan_courses if the table exists.
    try:
        with transaction() as conn:
            tbl = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='plan_courses'"
            ).fetchone()
            if tbl:
                conn.execute(
                    "UPDATE plan_courses SET course_code = ? "
                    "WHERE plan_id IN (SELECT plan_id FROM student_plans WHERE student_id = ?) "
                    "AND course_code = ?",
                    (to_course, str(student_id), from_course),
                )
                conn.commit()
    except Exception as exc:
        logger.debug("adjustment→plan swap failed: %s", exc)

    # Finance: credit the dropped course, debit the new one (idempotent on request_id).
    try:
        from education_system.university_system.modules.services.finance_bus import (
            raise_charge,
        )
        old_fee = _lookup_program_fee(from_course, None) or 0.0
        new_fee = _lookup_program_fee(to_course, None) or 0.0
        if old_fee:
            raise_charge(
                student_id, -float(old_fee),
                source="adjustment",
                description=f"Credit: {from_course} (adjustment)",
                reference_id=f"adjustment:{request_id}:credit",
            )
        if new_fee:
            raise_charge(
                student_id, float(new_fee),
                source="adjustment",
                description=f"Debit: {to_course} (adjustment)",
                reference_id=f"adjustment:{request_id}:debit",
            )
    except Exception as exc:
        logger.debug("adjustment→finance failed: %s", exc)


# ---------------------------------------------------------------------------
# Feature 4 — Timetable locked → contracted hours + workload + KPI
# ---------------------------------------------------------------------------

def _on_timetable_locked(**payload: Any) -> None:
    if payload.get("action") != "timetable_locked":
        return
    user_ids = payload.get("user_ids") or []
    if not user_ids:
        return

    try:
        with transaction() as conn:
            for uid in user_ids:
                hours = _sum_weekly_block_hours(conn, str(uid))
                if hours is None:
                    continue
                # Stamp into payroll_periods if the column exists.
                try:
                    conn.execute(
                        "UPDATE payroll_periods SET contracted_hours = ? "
                        "WHERE status = 'open' AND ? IN ("
                        "  SELECT user_id FROM faculty_schedule_blocks "
                        "  WHERE user_id = ?)",
                        (float(hours), str(uid), str(uid)),
                    )
                except Exception as exc:
                    logger.debug("payroll_periods stamp skipped: %s", exc)
            conn.commit()
    except Exception as exc:
        logger.debug("timetable_locked payroll stamp failed: %s", exc)

    # KPI: write/refresh staff_utilisation summary.
    avg = _avg_utilisation(user_ids)
    if avg is not None:
        _set_kpi(name="Staff Utilisation", category="staff", value=avg)


def _sum_weekly_block_hours(conn: Any, user_id: str) -> float | None:
    try:
        rows = conn.execute(
            "SELECT start_time, end_time FROM faculty_schedule_blocks "
            "WHERE user_id = ? AND COALESCE(is_locked, 0) = 1",
            (user_id,),
        ).fetchall()
    except Exception:
        return None
    total = 0.0
    for r in rows:
        try:
            s = datetime.strptime(r[0][:5], "%H:%M")
            e = datetime.strptime(r[1][:5], "%H:%M")
            total += (e - s).total_seconds() / 3600.0
        except Exception:
            continue
    return total


def _avg_utilisation(user_ids: list[str]) -> float | None:
    if not user_ids:
        return None
    try:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT user_id, COALESCE(SUM(end_time - start_time), 0) "
                "FROM faculty_schedule_blocks WHERE user_id IN (%s) "
                "GROUP BY user_id"
                % ",".join("?" * len(user_ids)),
                tuple(user_ids),
            ).fetchall()
        if not rows:
            return None
        return float(sum(r[1] or 0 for r in rows) / len(rows))
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Feature 5 — Degree audit batch → graduation forecast
# ---------------------------------------------------------------------------

def run_degree_audit_sweep(*, cohort_year: int) -> dict[str, Any]:
    """Sweep degree audits for ``cohort_year`` and refresh the graduation KPI.

    Public entry point — call from the Course Management GUI's "Run audit"
    button or a scheduled job. Reads ``student_plans`` + ``plan_courses``,
    computes the on-track ratio, writes it into kpi_metrics under
    "Graduation Forecast", and returns the result for display.
    """
    on_track = 0
    total = 0
    try:
        with get_connection() as conn:
            tbl = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='student_plans'"
            ).fetchone()
            if not tbl:
                return {"cohort_year": cohort_year, "on_track": 0, "total": 0, "rate": None}
            rows = conn.execute(
                "SELECT plan_id, student_id FROM student_plans "
                "WHERE academic_year = ?",
                (str(cohort_year),),
            ).fetchall()
            total = len(rows)
            for r in rows:
                if _plan_is_on_track(conn, r[0]):
                    on_track += 1
    except Exception as exc:
        logger.warning("degree audit sweep failed: %s", exc)
        return {"cohort_year": cohort_year, "on_track": 0, "total": 0, "rate": None}

    rate = (on_track / total) if total else None
    if rate is not None:
        _set_kpi(name="Graduation Forecast", category="graduation", value=rate * 100)
    log_and_publish(
        EVENT_SELECTION_CHANGED,
        source="course_management",
        action="degree_audit_swept",
        cohort_year=cohort_year,
        on_track=on_track,
        total=total,
        rate=rate,
    )
    return {"cohort_year": cohort_year, "on_track": on_track,
            "total": total, "rate": rate}


def _plan_is_on_track(conn: Any, plan_id: int) -> bool:
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM plan_courses "
            "WHERE plan_id = ? AND status NOT IN ('completed', 'in_progress')",
            (plan_id,),
        ).fetchone()
        return bool(row and row[0] == 0)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# APL/RPL approved → log only (degree-audit + transcript queries read
# directly from apl_credit_awards, so no cross-table mutation here).
# ---------------------------------------------------------------------------

def _on_apl_approved(**payload: Any) -> None:
    if payload.get("action") != "apl_approved":
        return
    student_id = payload.get("student_id")
    credits = payload.get("credits_awarded")
    if not student_id:
        return
    logger.info(
        "APL approved: student=%s credits=%s claim=%s type=%s",
        student_id, credits, payload.get("claim_id"),
        payload.get("claim_type"),
    )


# ---------------------------------------------------------------------------
# Feature 6 — KPI demand forecast → suggested clearing places
# ---------------------------------------------------------------------------

def _on_demand_forecast(**payload: Any) -> None:
    if payload.get("action") != "demand_forecast":
        return
    course_code = payload.get("course_code")
    predicted = payload.get("predicted_enrollment")
    year = payload.get("academic_year")
    if not course_code or predicted is None:
        return
    try:
        with transaction() as conn:
            # Add the column lazily if missing.
            cols = {r[1] for r in conn.execute(
                "PRAGMA table_info(clearing_vacancies)").fetchall()}
            if "suggested_places" not in cols:
                conn.execute(
                    "ALTER TABLE clearing_vacancies ADD COLUMN suggested_places INTEGER"
                )
            conn.execute(
                "UPDATE clearing_vacancies SET suggested_places = ? "
                "WHERE course_code = ? AND (academic_year = ? OR ? IS NULL)",
                (int(predicted), course_code, year, year),
            )
            conn.commit()
    except Exception as exc:
        logger.debug("demand_forecast→vacancy update failed: %s", exc)


# ---------------------------------------------------------------------------
# Feature 7 — Appraisal → merit pay proposal
# ---------------------------------------------------------------------------

# Appraisal-rating → suggested allowance percent. Conservative bands;
# HR signs off before the row becomes active.
_MERIT_BANDS = (
    (4.5, 0.05),  # outstanding → +5%
    (4.0, 0.03),  # exceeds      → +3%
    (3.5, 0.015), # solid        → +1.5%
)


def _on_appraisal_completed(**payload: Any) -> None:
    if payload.get("action") != "appraisal_completed":
        return
    user_id = payload.get("user_id")
    rating = payload.get("rating")
    cycle_id = payload.get("cycle_id")
    if not user_id or rating is None:
        return

    pct = next((p for thr, p in _MERIT_BANDS if rating >= thr), 0.0)
    if pct <= 0:
        return

    try:
        # Look up current salary, then propose an allowance row.
        with get_connection() as conn:
            row = conn.execute(
                "SELECT salary FROM employees WHERE user_id = ? LIMIT 1",
                (str(user_id),),
            ).fetchone()
            salary = float(row[0]) if row and row[0] else 0.0
        if salary <= 0:
            return
        amount = round(salary * pct, 2)
        from education_system.university_system.modules.domain.staff_comms.staff_hr.services.managers.payroll_manager import (
            PayrollManager,
        )
        PayrollManager.add_allowance(
            user_id=str(user_id),
            allowance_type="merit_proposal",
            amount=amount,
            description=(
                f"Proposed merit (cycle {cycle_id}, rating {rating:.2f}). "
                "Pending HR approval — set is_active=1 to apply."
            ),
            is_active=False,
        )
    except Exception as exc:
        logger.debug("merit-pay proposal failed: %s", exc)


# ---------------------------------------------------------------------------
# Feature 8 — Cert expiry → operational risk KPI
# ---------------------------------------------------------------------------

def sweep_expiring_certifications(*, within_days: int = 30) -> int:
    """Scan certifications for upcoming expiries and publish events.

    Public entry point — call from a daily cron or HR dashboard
    refresh. Returns the number of expiring certs found.
    """
    found = 0
    try:
        from education_system.university_system.modules.domain.staff_comms.staff_hr.services.managers.training_manager import (
            TrainingManager,
        )
        rows = TrainingManager.get_expiring_certs(days=within_days)
    except Exception as exc:
        logger.debug("training_manager.get_expiring_certs unavailable: %s", exc)
        rows = []

    critical_count = 0
    for r in rows:
        found += 1
        critical = _is_role_critical(r.get("user_id"))
        if critical:
            critical_count += 1
        publish_cert_expiry(
            user_id=r.get("user_id"),
            training_id=r.get("certification_id") or r.get("course_id"),
            cert_name=r.get("name") or r.get("course_name") or "certification",
            expiry_date=r.get("expiry_date") or r.get("expires_on") or "",
            role_critical=critical,
        )
    # KPI risk gauge: ratio of critical expiring certs to total expiring.
    if found:
        ratio = (critical_count / found) * 100
        _set_kpi(name="Compliance Risk", category="risk", value=ratio)
    return found


def _is_role_critical(user_id: str | None) -> bool:
    if not user_id:
        return False
    critical_titles = ("compliance", "auditor", "safety", "first aid", "lab manager")
    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT job_title FROM employees WHERE user_id = ? LIMIT 1",
                (str(user_id),),
            ).fetchone()
            if not row or not row[0]:
                return False
            title = row[0].lower()
            return any(k in title for k in critical_titles)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Feature 9 — Waitlist promotion → atomic enrol + bill
# ---------------------------------------------------------------------------

def promote_from_waitlist(student_id: str, course_code: str, *,
                           plan_id: int | None = None,
                           academic_year: str | None = None) -> bool:
    """Atomic enrol-and-bill from a waitlist offer.

    Inserts/updates plan_courses, decrements module_schedule capacity,
    raises a fee charge, then publishes a single event. Either all four
    succeed or the SQL transaction is rolled back; the finance charge
    fires after commit so a publish-only failure won't double-bill.
    """
    sid = str(student_id)
    fee = _lookup_program_fee(course_code, academic_year) or 0.0
    success = False
    try:
        with transaction() as conn:
            tbl = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='plan_courses'"
            ).fetchone()
            if tbl and plan_id is not None:
                conn.execute(
                    "INSERT INTO plan_courses (plan_id, course_code, status) "
                    "VALUES (?, ?, 'in_progress') "
                    "ON CONFLICT(plan_id, course_code) DO UPDATE SET status = 'in_progress'",
                    (plan_id, course_code),
                )
            sched = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='module_schedule'"
            ).fetchone()
            if sched:
                conn.execute(
                    "UPDATE module_schedule SET enrolled = COALESCE(enrolled, 0) + 1 "
                    "WHERE module_code = ?",
                    (course_code,),
                )
            conn.commit()
            success = True
    except Exception as exc:
        logger.warning("waitlist promote db step failed: %s", exc)
        return False

    if success and fee > 0:
        try:
            from education_system.university_system.modules.services.finance_bus import (
                raise_charge,
            )
            raise_charge(
                sid, fee,
                source="waitlist",
                description=f"Tuition: {course_code} (waitlist promote)",
                reference_id=f"waitlist:{plan_id}:{course_code}",
            )
        except Exception as exc:
            logger.warning("waitlist promote charge failed: %s", exc)

    publish_waitlist_promoted(
        sid, course_code=course_code, plan_id=plan_id, fee_amount=fee,
    )
    return success


# ---------------------------------------------------------------------------
# KPI helpers — single point of contact with kpi_metrics
# ---------------------------------------------------------------------------

def _set_kpi(*, name: str, category: str, value: float) -> None:
    try:
        with transaction() as conn:
            tbl = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='kpi_metrics'"
            ).fetchone()
            if not tbl:
                return
            row = conn.execute(
                "SELECT kpi_id FROM kpi_metrics WHERE kpi_name = ? LIMIT 1", (name,),
            ).fetchone()
            today = date.today().isoformat()
            if row:
                conn.execute(
                    "UPDATE kpi_metrics SET current_value = ?, measurement_date = ? "
                    "WHERE kpi_id = ?",
                    (float(value), today, row[0]),
                )
            else:
                conn.execute(
                    "INSERT INTO kpi_metrics (kpi_name, kpi_category, current_value, "
                    "  target_value, measurement_date, period, trend) "
                    "VALUES (?, ?, ?, ?, ?, 'monthly', 'flat')",
                    (name, category, float(value), float(value), today),
                )
            conn.commit()
    except Exception as exc:
        logger.debug("_set_kpi(%s) failed: %s", name, exc)


def _bump_kpi(*, category: str, increment: float) -> None:
    try:
        with transaction() as conn:
            tbl = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='kpi_metrics'"
            ).fetchone()
            if not tbl:
                return
            row = conn.execute(
                "SELECT kpi_id, current_value FROM kpi_metrics "
                "WHERE kpi_category = ? ORDER BY kpi_id LIMIT 1",
                (category,),
            ).fetchone()
            if not row:
                return
            new_val = float(row[1] or 0) + float(increment)
            conn.execute(
                "UPDATE kpi_metrics SET current_value = ?, measurement_date = ? "
                "WHERE kpi_id = ?",
                (new_val, date.today().isoformat(), row[0]),
            )
            conn.commit()
    except Exception as exc:
        logger.debug("_bump_kpi(%s) failed: %s", category, exc)


# ---------------------------------------------------------------------------
# Misc helpers
# ---------------------------------------------------------------------------

def _current_year() -> str:
    today = date.today()
    # Sept onwards belongs to the next academic year (e.g. 2025/26).
    if today.month >= 9:
        return f"{today.year}/{str(today.year + 1)[-2:]}"
    return f"{today.year - 1}/{str(today.year)[-2:]}"


def _date_range(start: str, end: str):
    try:
        s = datetime.strptime(start[:10], "%Y-%m-%d").date()
        e = datetime.strptime(end[:10], "%Y-%m-%d").date()
    except Exception:
        return
    cur = s
    while cur <= e:
        yield cur.isoformat()
        cur += timedelta(days=1)


def _lookup_program_fee(course_code: str | None,
                       academic_year: str | None) -> float | None:
    if not course_code:
        return None
    try:
        with get_connection() as conn:
            tbl = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='program_fees'"
            ).fetchone()
            if not tbl:
                return None
            sql = "SELECT amount FROM program_fees WHERE course = ?"
            params: list[Any] = [course_code]
            if academic_year:
                sql += " AND (academic_year = ? OR academic_year IS NULL)"
                params.append(academic_year)
            sql += " ORDER BY academic_year DESC LIMIT 1"
            row = conn.execute(sql, tuple(params)).fetchone()
            return float(row[0]) if row and row[0] is not None else None
    except Exception:
        return None


def _tag_payroll_leave(user_id: str, start: str, end: str,
                       *, leave_type: str | None) -> None:
    """Best-effort: stamp open payroll period with a leave note for prorate."""
    try:
        with transaction() as conn:
            tbl = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='payroll_periods'"
            ).fetchone()
            if not tbl:
                return
            cols = {r[1] for r in conn.execute(
                "PRAGMA table_info(payroll_periods)").fetchall()}
            if "leave_notes" not in cols:
                conn.execute(
                    "ALTER TABLE payroll_periods ADD COLUMN leave_notes TEXT"
                )
            note = f"{user_id}:{leave_type or 'leave'}:{start}..{end};"
            conn.execute(
                "UPDATE payroll_periods "
                "SET leave_notes = COALESCE(leave_notes, '') || ? "
                "WHERE status = 'open' "
                "  AND start_date <= ? AND end_date >= ?",
                (note, end, start),
            )
            conn.commit()
    except Exception as exc:
        logger.debug("payroll leave tag failed: %s", exc)


# ===========================================================================
# Exam + Email features (10–17)
# ===========================================================================

# Cached current term window — populated by EVENT_TERM_CHANGED. Used by
# Feature 16 to refuse exams scheduled outside the active term.
_current_term: dict[str, Any] = {"start": None, "end": None, "name": None}


def _on_term_changed(**payload: Any) -> None:
    if payload.get("start_date"):
        _current_term["start"] = str(payload["start_date"])[:10]
    if payload.get("end_date"):
        _current_term["end"] = str(payload["end_date"])[:10]
    if payload.get("term") or payload.get("name"):
        _current_term["name"] = str(payload.get("term") or payload.get("name"))


# ---------------------------------------------------------------------------
# Feature 10 — Exam published → email enrolled roster
# ---------------------------------------------------------------------------

def publish_exam_event(exam_id: int, *, action: str,
                       module_code: str | None = None,
                       exam_title: str | None = None,
                       start_time: str | None = None,
                       duration_minutes: int | None = None,
                       pass_mark: float | None = None,
                       student_id: str | None = None,
                       score: float | None = None,
                       total_marks: float | None = None,
                       percentage: float | None = None,
                       passed: bool | None = None) -> None:
    """Publish an exam lifecycle event.

    ``action`` is one of: ``"published"``, ``"unpublished"``,
    ``"graded"``, ``"pending_grade"``. Origin: ExamPortalService.
    """
    log_and_publish(
        EVENT_EXAM_CHANGED,
        source="exam_management",
        exam_id=int(exam_id),
        action=action,
        module_code=module_code,
        exam_title=exam_title,
        start_time=start_time,
        duration_minutes=duration_minutes,
        pass_mark=pass_mark,
        student_id=student_id,
        score=score,
        total_marks=total_marks,
        percentage=percentage,
        passed=passed,
    )


def _enrolled_students_for_module(module_code: str) -> list[str]:
    """Best-effort roster lookup. Tries student_enrolment, then plan_courses."""
    if not module_code:
        return []
    try:
        with get_connection() as conn:
            for sql in (
                "SELECT DISTINCT student_id FROM student_enrolment WHERE module_code = ?",
                "SELECT DISTINCT sp.student_id FROM plan_courses pc "
                "JOIN student_plans sp ON sp.plan_id = pc.plan_id "
                "WHERE pc.course_code = ?",
            ):
                try:
                    rows = conn.execute(sql, (module_code,)).fetchall()
                    if rows:
                        return [str(r[0]) for r in rows if r[0]]
                except Exception:
                    continue
    except Exception:
        pass
    return []


def _on_exam_event(**payload: Any) -> None:
    action = payload.get("action")
    if action == "published":
        _fanout_exam_published(payload)
    elif action == "graded":
        _fanout_exam_graded(payload)


def _fanout_exam_published(payload: dict[str, Any]) -> None:
    module_code = payload.get("module_code") or ""
    students = _enrolled_students_for_module(module_code)
    try:
        from education_system.university_system.modules.services.email_bus import (
            send_templated,
        )
        ctx = {
            "exam_title": payload.get("exam_title") or f"Exam #{payload.get('exam_id')}",
            "module_code": module_code,
            "start_time": payload.get("start_time") or "TBA",
            "duration_minutes": payload.get("duration_minutes") or "?",
            "pass_mark": payload.get("pass_mark") or 50,
        }
        for sid in students:
            try:
                send_templated(sid, "exam.scheduled", ctx,
                               related_to=f"exam:{payload.get('exam_id')}")
            except Exception as exc:
                logger.debug("exam.scheduled email failed for %s: %s", sid, exc)
    except Exception as exc:
        logger.debug("email_bus unavailable for exam roster: %s", exc)


def _fanout_exam_graded(payload: dict[str, Any]) -> None:
    sid = payload.get("student_id")
    if not sid:
        return
    try:
        from education_system.university_system.modules.services.email_bus import (
            send_templated,
        )
        send_templated(
            sid, "exam.graded",
            {
                "exam_title": payload.get("exam_title")
                              or f"Exam #{payload.get('exam_id')}",
                "score": payload.get("score") or 0,
                "total_marks": payload.get("total_marks") or 0,
                "percentage": round(payload.get("percentage") or 0.0, 1),
                "result": "passed" if payload.get("passed") else "review",
            },
            related_to=f"exam:{payload.get('exam_id')}",
        )
    except Exception as exc:
        logger.debug("exam.graded email failed: %s", exc)


# ---------------------------------------------------------------------------
# Feature 11 — Hold blocks exam start (read-helper, no event)
# ---------------------------------------------------------------------------

def can_student_start_exam(student_id: str) -> tuple[bool, str | None]:
    """Return ``(allowed, reason)`` for an exam-start gate.

    Wraps ``finance_bus.has_active_hold``. Callers (exam_service) can
    plug this in without learning the holds schema.
    """
    if not student_id:
        return True, None
    try:
        from education_system.university_system.modules.services.finance_bus import (
            has_active_hold, list_active_holds,
        )
        if not has_active_hold(student_id):
            return True, None
        holds = list_active_holds(student_id) or []
        reason = (holds[0].get("reason") if holds else None) or "active finance hold"
        return False, reason
    except Exception as exc:
        logger.debug("hold check failed for %s: %s — allowing", student_id, exc)
        return True, None


# ---------------------------------------------------------------------------
# Feature 13 — Module reschedule → exam room conflict
# ---------------------------------------------------------------------------

def _on_module_schedule_changed_for_exams(**payload: Any) -> None:
    if payload.get("action") == "timetable_locked":
        return  # already handled by Feature 4
    module_code = payload.get("module_code")
    if not module_code:
        return
    new_start = payload.get("start_time")
    new_end = payload.get("end_time")
    new_room = payload.get("room_id")
    if not (new_start and new_end):
        return
    try:
        with get_connection() as conn:
            tbl = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name='exam_portal_exams'"
            ).fetchone()
            if not tbl:
                return
            rows = conn.execute(
                "SELECT id, title, start_time, end_time, room_id "
                "FROM exam_portal_exams "
                "WHERE module_code = ? AND status = 'published' "
                "  AND start_time IS NOT NULL AND end_time IS NOT NULL",
                (module_code,),
            ).fetchall()
    except Exception:
        return

    for exam in rows:
        if not _windows_overlap(new_start, new_end,
                                 exam["start_time"], exam["end_time"]):
            continue
        if new_room and exam["room_id"] and new_room != exam["room_id"]:
            continue  # different rooms, no real conflict
        log_and_publish(
            EVENT_INCIDENT_LOGGED,
            source="integration_bus",
            kind="exam_room_conflict",
            severity="medium",
            module_code=module_code,
            exam_id=exam["id"],
            exam_title=exam["title"],
            location=exam["room_id"] or new_room,
        )
        # Notify the scheduler/admin via email_bus.
        try:
            from education_system.university_system.modules.services.email_bus import (
                send_templated,
            )
            send_templated(
                _admin_user_id() or "admin", "exam.room_conflict",
                {
                    "exam_title": exam["title"] or f"Exam #{exam['id']}",
                    "module_code": module_code,
                    "when": exam["start_time"],
                },
                related_to=f"exam:{exam['id']}",
                force=True,
            )
        except Exception as exc:
            logger.debug("conflict email failed: %s", exc)


def _windows_overlap(a_start: str, a_end: str, b_start: str, b_end: str) -> bool:
    try:
        return not (a_end <= b_start or b_end <= a_start)
    except Exception:
        return False


def _admin_user_id() -> str | None:
    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT user_id FROM users WHERE LOWER(role) = 'admin' "
                "AND email IS NOT NULL LIMIT 1"
            ).fetchone()
            return str(row[0]) if row else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Feature 14 — Finance report → email_bus
# ---------------------------------------------------------------------------

def send_finance_report(report_title: str, summary: str,
                        *, recipient_user_id: str | None = None,
                        related_to: str | None = None) -> str | None:
    """Route a finance report through email_bus so it lands in
    ``email_log`` and fires ``EVENT_EMAIL_SENT`` for audit.

    Returns the message_id on success.
    """
    target = recipient_user_id or _admin_user_id() or "admin"
    try:
        from education_system.university_system.modules.services.email_bus import (
            send_templated,
        )
        return send_templated(
            target, "finance.report.sent",
            {
                "report_title": report_title,
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "summary": summary[:1500],
            },
            related_to=related_to or "finance_report",
            force=True,
        )
    except Exception as exc:
        logger.warning("send_finance_report failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Feature 15 — Ungraded sweep
# ---------------------------------------------------------------------------

def sweep_ungraded_exams(*, reminder_after_days: int = 7,
                         hold_after_days: int = 14) -> dict[str, int]:
    """Daily sweep over ``exam_portal_attempts``.

    - Attempts submitted >= reminder_after_days ago and still not
      graded → email the instructor.
    - Attempts submitted >= hold_after_days ago and still not graded
      → place a finance hold against the student so transcripts
      can't release.
    Returns ``{"reminded": N, "held": M}``.
    """
    reminded = 0
    held = 0
    try:
        with get_connection() as conn:
            tbl = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name='exam_portal_attempts'"
            ).fetchone()
            if not tbl:
                return {"reminded": 0, "held": 0}

            stale = conn.execute(
                "SELECT a.id, a.student_id, a.submitted_at, "
                "       e.id as exam_id, e.title, e.created_by, e.module_code "
                "FROM exam_portal_attempts a "
                "JOIN exam_portal_exams e ON e.id = a.exam_id "
                "WHERE a.graded_at IS NULL "
                "  AND a.submitted_at IS NOT NULL "
                "  AND julianday('now') - julianday(a.submitted_at) >= ?",
                (int(reminder_after_days),),
            ).fetchall()
    except Exception as exc:
        logger.warning("sweep_ungraded_exams query failed: %s", exc)
        return {"reminded": 0, "held": 0}

    # Group by instructor for one email per instructor per sweep.
    by_instructor: dict[str, list[dict[str, Any]]] = {}
    for r in stale:
        d = dict(r)
        by_instructor.setdefault(str(d.get("created_by") or "admin"), []).append(d)

    try:
        from education_system.university_system.modules.services.email_bus import (
            send_templated,
        )
        for instructor_id, attempts in by_instructor.items():
            oldest = min(a.get("submitted_at") or "" for a in attempts)
            send_templated(
                instructor_id, "exam.pending_grade",
                {
                    "exam_title": attempts[0].get("title") or "exam",
                    "count": len(attempts),
                    "oldest_submitted": oldest,
                },
                related_to=f"exam:{attempts[0].get('exam_id')}",
                force=True,
            )
            reminded += len(attempts)
    except Exception as exc:
        logger.debug("ungraded sweep email failed: %s", exc)

    # Holds for older still-ungraded attempts.
    try:
        from education_system.university_system.modules.services.finance_bus import (
            place_hold,
        )
        for r in stale:
            d = dict(r)
            sub = d.get("submitted_at") or ""
            try:
                age_days = (datetime.now() - datetime.strptime(
                    sub[:19], "%Y-%m-%d %H:%M:%S")).days
            except Exception:
                age_days = 0
            if age_days >= hold_after_days and d.get("student_id"):
                place_hold(
                    d["student_id"],
                    reason=f"Exam '{d.get('title')}' awaiting grading",
                    source="exam_management",
                    reference_id=f"attempt:{d.get('id')}",
                )
                held += 1
    except Exception as exc:
        logger.debug("ungraded sweep hold failed: %s", exc)

    return {"reminded": reminded, "held": held}


# ---------------------------------------------------------------------------
# Feature 16 — Exam outside term → refuse
# ---------------------------------------------------------------------------

def is_exam_within_term(start_time: str | None, end_time: str | None) -> bool:
    """Return True if the exam window falls inside the cached term.

    Returns True (permissive) when no term has been broadcast yet —
    the integration check shouldn't block an admin who never set a
    term in the first place.
    """
    if not _current_term["start"] or not _current_term["end"]:
        return True
    if not start_time or not end_time:
        return True
    try:
        s = str(start_time)[:10]
        e = str(end_time)[:10]
        return _current_term["start"] <= s and e <= _current_term["end"]
    except Exception:
        return True


# ---------------------------------------------------------------------------
# Feature 17 — Withdraw → cancel attempts + refund preview
# ---------------------------------------------------------------------------

_REFUND_PREVIEW_SQL = """
CREATE TABLE IF NOT EXISTS refund_previews (
    preview_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id  TEXT NOT NULL,
    course_code TEXT NOT NULL,
    amount      REAL NOT NULL DEFAULT 0,
    reason      TEXT,
    status      TEXT NOT NULL DEFAULT 'pending',
    created_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
)
"""


def publish_enrolment_withdrew(student_id: str, course_code: str,
                               *, reason: str | None = None) -> None:
    """Course Management calls this when a student drops a module."""
    log_and_publish(
        EVENT_ENROLMENT_CHANGED,
        source="course_management",
        action="withdrew",
        student_id=str(student_id),
        course_code=course_code,
        reason=reason,
    )


def _on_enrolment_withdrew(**payload: Any) -> None:
    if payload.get("action") != "withdrew":
        return
    student_id = payload.get("student_id")
    course_code = payload.get("course_code")
    if not (student_id and course_code):
        return

    # Cancel any in-progress exam attempts for that module.
    try:
        with transaction() as conn:
            tbl = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name='exam_portal_attempts'"
            ).fetchone()
            if tbl:
                conn.execute(
                    "UPDATE exam_portal_attempts SET status = 'cancelled' "
                    "WHERE student_id = ? AND status = 'in_progress' "
                    "  AND exam_id IN ("
                    "      SELECT id FROM exam_portal_exams WHERE module_code = ?)",
                    (str(student_id), course_code),
                )
            conn.commit()
    except Exception as exc:
        logger.debug("withdraw → cancel attempts failed: %s", exc)

    # Queue a refund preview row (no auto-charge).
    try:
        with transaction() as conn:
            conn.executescript(_REFUND_PREVIEW_SQL)
            fee = _lookup_program_fee(course_code, None) or 0.0
            conn.execute(
                "INSERT INTO refund_previews "
                "(student_id, course_code, amount, reason, status) "
                "VALUES (?, ?, ?, ?, 'pending')",
                (str(student_id), course_code, float(fee),
                 payload.get("reason") or "withdrawal"),
            )
            conn.commit()
    except Exception as exc:
        logger.debug("withdraw → refund preview failed: %s", exc)


# ===========================================================================
# Tier-1 safeguarding / accommodation features
# ===========================================================================

# Default risk-score floor that promotes a health risk_assessment row
# to a safeguarding event. Tunable via the kpi_metrics row
# 'Safeguarding Risk Threshold' if an admin wants to tighten it.
_SAFEGUARDING_THRESHOLD = 70


def publish_health_risk_assessment(student_id: str, *, assessment_type: str,
                                    risk_score: int,
                                    risk_factors: list[str] | None = None,
                                    follow_up_date: str | None = None,
                                    assessed_by: str | None = None) -> None:
    """Publish a health risk assessment.

    Origin: ``health.portal.data_privacy.conduct_risk_assessment``.
    Subscribers (this module) raise an incident and an open case
    when the score crosses the safeguarding threshold.
    """
    log_and_publish(
        EVENT_INCIDENT_LOGGED,
        source="health",
        kind="health_risk_assessment",
        severity=_severity_for_score(risk_score),
        student_id=str(student_id),
        assessment_type=assessment_type,
        risk_score=int(risk_score),
        risk_factors=risk_factors or [],
        follow_up_date=follow_up_date,
        assessed_by=assessed_by,
    )


def _severity_for_score(score: int) -> str:
    if score >= 85:
        return "critical"
    if score >= _SAFEGUARDING_THRESHOLD:
        return "high"
    if score >= 40:
        return "medium"
    return "low"


def _on_health_risk_assessment(**payload: Any) -> None:
    if payload.get("kind") != "health_risk_assessment":
        return
    score = int(payload.get("risk_score") or 0)
    if score < _SAFEGUARDING_THRESHOLD:
        return  # below threshold — no auto-escalation
    student_id = payload.get("student_id")
    if not student_id:
        return

    # 1. Open a safeguarding case via cases_bus (idempotent on
    # subject_id+kind so repeat assessments don't pile up cases).
    try:
        from education_system.university_system.modules.services.cases_bus import (
            open_case,
        )
        open_case(
            kind="safeguarding",
            subject_id=str(student_id),
            severity=payload.get("severity") or "high",
            description=(
                f"Health risk assessment: {payload.get('assessment_type')} "
                f"score {score}"
            ),
            opened_by=payload.get("assessed_by") or "health_portal",
        )
    except Exception as exc:
        logger.debug("cases_bus open_case failed: %s", exc)

    # 2. Email the designated safeguarding lead.
    try:
        from education_system.university_system.modules.services.email_bus import (
            send_templated,
        )
        dsl = _designated_safeguarding_lead() or _admin_user_id() or "admin"
        send_templated(
            dsl, "hs.incident.logged",
            {
                "incident_id": f"health:{student_id}:{score}",
                "severity": payload.get("severity") or "high",
                "location": "health portal",
            },
            related_to=f"safeguarding:{student_id}",
            force=True,
        )
    except Exception as exc:
        logger.debug("safeguarding email failed: %s", exc)


def _designated_safeguarding_lead() -> str | None:
    """Look up the DSL user_id. Falls back to None if not configured.

    The convention here is a row in ``users`` with
    ``role='safeguarding_lead'``; if that role doesn't exist, callers
    fall through to the admin recipient.
    """
    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT user_id FROM users "
                "WHERE LOWER(role) IN ('safeguarding_lead', 'dsl', 'designated_lead') "
                "AND email IS NOT NULL LIMIT 1"
            ).fetchone()
            return str(row[0]) if row else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Tier-1 Item 3 — accessibility accommodation → exam tag
# ---------------------------------------------------------------------------

def publish_accommodation_decision(request_id: int, *, student_id: str,
                                    status: str, accommodation_type: str,
                                    extended_time_pct: int = 0,
                                    separate_room: bool = False,
                                    reader_scribe: bool = False,
                                    assistive_technology: str | None = None,
                                    exam_id: int | None = None) -> None:
    """Publish an accommodation decision.

    Origin: ``AccommodationRequestManager.review_request`` and
    ``ExamAccommodationManager.create_accommodation``. Subscribers
    (this module) tag matching ``exam_portal_attempts`` rows so the
    invigilator knows extra time / reader service applies, and they
    extend the per-attempt ``time_remaining`` proportionally.
    """
    log_and_publish(
        EVENT_SELECTION_CHANGED,
        source="student_affairs",
        action="accommodation_decided",
        request_id=int(request_id),
        student_id=str(student_id),
        status=status,
        accommodation_type=accommodation_type,
        extended_time_pct=int(extended_time_pct or 0),
        separate_room=bool(separate_room),
        reader_scribe=bool(reader_scribe),
        assistive_technology=assistive_technology,
        exam_id=exam_id,
    )


def _on_accommodation_decided(**payload: Any) -> None:
    if payload.get("action") != "accommodation_decided":
        return
    if payload.get("status") != "approved":
        return
    student_id = payload.get("student_id")
    if not student_id:
        return
    extra_pct = int(payload.get("extended_time_pct") or 0)

    try:
        with transaction() as conn:
            tbl = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name='exam_portal_attempts'"
            ).fetchone()
            if not tbl:
                return
            cols = {r[1] for r in conn.execute(
                "PRAGMA table_info(exam_portal_attempts)").fetchall()}
            if "accommodation_notes" not in cols:
                conn.execute(
                    "ALTER TABLE exam_portal_attempts "
                    "ADD COLUMN accommodation_notes TEXT"
                )
            note = _format_accommodation_note(payload)

            # Tag any in-progress / not-yet-started attempts. Done
            # attempts stay untouched — the accommodation can't
            # retroactively change a graded score.
            sql_filter = "student_id = ? AND status IN ('in_progress', 'pending', 'scheduled')"
            params: list[Any] = [str(student_id)]
            if payload.get("exam_id") is not None:
                sql_filter += " AND exam_id = ?"
                params.append(int(payload["exam_id"]))

            conn.execute(
                f"UPDATE exam_portal_attempts "
                f"SET accommodation_notes = COALESCE(accommodation_notes, '') || ? "
                f"WHERE {sql_filter}",
                (note + "; ", *params),
            )
            if extra_pct > 0:
                conn.execute(
                    f"UPDATE exam_portal_attempts "
                    f"SET time_remaining = CAST("
                    f"  COALESCE(time_remaining, 0) * (1 + ?/100.0) AS INTEGER) "
                    f"WHERE {sql_filter}",
                    (extra_pct, *params),
                )
            conn.commit()
    except Exception as exc:
        logger.debug("accommodation→exam tag failed: %s", exc)


def _format_accommodation_note(payload: dict[str, Any]) -> str:
    bits = [payload.get("accommodation_type") or "accommodation"]
    if payload.get("extended_time_pct"):
        bits.append(f"+{payload['extended_time_pct']}% time")
    if payload.get("separate_room"):
        bits.append("separate room")
    if payload.get("reader_scribe"):
        bits.append("reader/scribe")
    if payload.get("assistive_technology"):
        bits.append(f"AT: {payload['assistive_technology']}")
    return ", ".join(bits)


# ===========================================================================
# Tier-2 money-flow features (mail, housing, mobility, research)
# ===========================================================================

# Mail storage cadence — matches mail_post_core's FREE_STORAGE_DAYS /
# DAILY_STORAGE_FEE so the sweep produces the same numbers the
# package GUI surfaces.
_MAIL_FREE_DAYS = 7
_MAIL_DAILY_FEE = 0.50


def sweep_overdue_mail(*, free_days: int = _MAIL_FREE_DAYS,
                       daily_fee: float = _MAIL_DAILY_FEE) -> dict[str, int]:
    """Sweep ``mail_packages`` for unclaimed packages past the free
    window. Idempotent — uses ``reference_id='package:<id>'`` so a
    second sweep on the same day doesn't double-bill.

    Returns ``{"charged": N, "emailed": M}``.
    """
    charged = 0
    emailed = 0
    try:
        with get_connection() as conn:
            tbl = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name='mail_packages'"
            ).fetchone()
            if not tbl:
                return {"charged": 0, "emailed": 0}
            rows = conn.execute(
                "SELECT package_id, recipient_id, recipient_name, "
                "       recipient_email, tracking_number, received_date "
                "FROM mail_packages "
                "WHERE LOWER(status) IN ('received', 'stored') "
                "  AND julianday('now') - julianday(received_date) > ?",
                (int(free_days),),
            ).fetchall()
    except Exception as exc:
        logger.warning("sweep_overdue_mail query failed: %s", exc)
        return {"charged": 0, "emailed": 0}

    try:
        from education_system.university_system.modules.services.finance_bus import (
            raise_charge,
        )
        from education_system.university_system.modules.services.email_bus import (
            send_templated,
        )
    except Exception:
        return {"charged": 0, "emailed": 0}

    for r in rows:
        d = dict(r)
        try:
            received = datetime.strptime(
                str(d["received_date"])[:10], "%Y-%m-%d").date()
        except Exception:
            continue
        days_over = max((date.today() - received).days - free_days, 0)
        if days_over <= 0:
            continue
        amount = round(days_over * float(daily_fee), 2)
        ref = f"package:{d['package_id']}:{date.today().isoformat()}"
        if not d.get("recipient_id"):
            continue
        try:
            tx = raise_charge(
                d["recipient_id"], amount,
                source="mail_storage",
                description=(
                    f"Mail storage overdue ({days_over}d): "
                    f"{d.get('tracking_number') or ''}"
                ),
                reference_id=ref,
            )
            if tx:
                charged += 1
        except Exception as exc:
            logger.debug("mail charge failed for %s: %s",
                         d["package_id"], exc)
            continue
        try:
            send_templated(
                d["recipient_id"], "mail.overdue",
                {
                    "tracking_number": d.get("tracking_number") or "",
                    "days_over": days_over,
                    "amount": amount,
                },
                related_to=f"package:{d['package_id']}",
                force=True,
            )
            emailed += 1
        except Exception as exc:
            logger.debug("mail email failed: %s", exc)

    return {"charged": charged, "emailed": emailed}


# ---------------------------------------------------------------------------
# Tier-2 #5 — Housing move-out → refund preview + final inspection
# ---------------------------------------------------------------------------

def publish_housing_move_out(assignment_id: int, *, student_id: str,
                              room_id: str, building_id: str | None = None,
                              actual_move_out_date: str,
                              new_status: str) -> None:
    """Publish a housing move-out / termination.

    Origin: ``housing.assignments.update_assignment_status`` when
    new_status ∈ {'Terminated', 'Expired'}. Subscribers (this
    module) queue a deposit refund preview row and email the
    inspector to schedule a checkout walk-through.
    """
    log_and_publish(
        EVENT_INCIDENT_LOGGED,
        source="housing",
        kind="housing_move_out",
        severity="low",
        assignment_id=int(assignment_id),
        student_id=str(student_id),
        room_id=str(room_id),
        building_id=str(building_id) if building_id else None,
        actual_move_out_date=actual_move_out_date,
        new_status=new_status,
    )


def _on_housing_move_out(**payload: Any) -> None:
    if payload.get("kind") != "housing_move_out":
        return
    student_id = payload.get("student_id")
    if not student_id:
        return

    # Queue a refund preview using whatever deposit can be looked up.
    deposit = _lookup_housing_deposit(payload.get("assignment_id"))
    try:
        with transaction() as conn:
            conn.executescript(_REFUND_PREVIEW_SQL)
            conn.execute(
                "INSERT INTO refund_previews "
                "(student_id, course_code, amount, reason, status) "
                "VALUES (?, ?, ?, ?, 'pending')",
                (str(student_id),
                 f"housing:{payload.get('room_id')}",
                 float(deposit),
                 f"Housing move-out ({payload.get('new_status')})"),
            )
            conn.commit()
    except Exception as exc:
        logger.debug("housing→refund_previews failed: %s", exc)

    # Email the inspector (first user with an inspections role; fallback admin).
    try:
        from education_system.university_system.modules.services.email_bus import (
            send_templated,
        )
        recipient = _housing_inspector_user_id() or _admin_user_id() or "admin"
        send_templated(
            recipient, "hs.incident.logged",
            {
                "incident_id": f"checkout:{payload.get('assignment_id')}",
                "severity": "low",
                "location": f"room {payload.get('room_id')}",
            },
            related_to=f"housing_assignment:{payload.get('assignment_id')}",
            force=True,
        )
    except Exception as exc:
        logger.debug("housing inspector email failed: %s", exc)


def _lookup_housing_deposit(assignment_id: Any) -> float:
    if assignment_id is None:
        return 0.0
    try:
        with get_connection() as conn:
            for sql in (
                "SELECT deposit_amount FROM housing_assignments WHERE assignment_id = ?",
                "SELECT amount FROM housing_payments "
                "WHERE assignment_id = ? AND LOWER(payment_type) = 'deposit' "
                "ORDER BY payment_id DESC LIMIT 1",
            ):
                try:
                    row = conn.execute(sql, (assignment_id,)).fetchone()
                    if row and row[0] is not None:
                        return float(row[0])
                except Exception:
                    continue
    except Exception:
        pass
    return 0.0


def _housing_inspector_user_id() -> str | None:
    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT user_id FROM users "
                "WHERE LOWER(role) IN ('housing_inspector', 'inspector', "
                "                      'housing_manager') "
                "AND email IS NOT NULL LIMIT 1"
            ).fetchone()
            return str(row[0]) if row else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Tier-2 #6 — Mobility permit issued → finance + email
# ---------------------------------------------------------------------------

def publish_permit_issued(permit_id: str, *, holder_id: str,
                          fee: float, zone: str, permit_type: str,
                          plate: str | None = None,
                          email: str | None = None,
                          start_date: str | None = None,
                          end_date: str | None = None) -> None:
    """Publish a permit issuance from the legacy CLI/GUI writer
    paths that don't go through ``parking_bus.issue_permit``.

    Subscriber raises the charge against the holder's finance
    account and emails the holder. Idempotent on
    ``reference_id='permit:<permit_id>'``.
    """
    log_and_publish(
        EVENT_INCIDENT_LOGGED,
        source="mobility",
        kind="permit_issued",
        severity="low",
        permit_id=str(permit_id),
        holder_id=str(holder_id),
        fee=float(fee or 0),
        zone=zone,
        permit_type=permit_type,
        plate=plate,
        email=email,
        start_date=start_date,
        end_date=end_date,
    )


def _on_permit_issued(**payload: Any) -> None:
    if payload.get("kind") != "permit_issued":
        return
    fee = float(payload.get("fee") or 0)
    holder_id = payload.get("holder_id")
    if not holder_id or fee <= 0:
        return
    try:
        from education_system.university_system.modules.services.finance_bus import (
            raise_charge,
        )
        raise_charge(
            holder_id, fee,
            source="parking_permit",
            description=(
                f"Parking permit fee — {payload.get('permit_type')} "
                f"({payload.get('zone')}); plate {payload.get('plate') or 'n/a'}"
            ),
            reference_id=f"permit:{payload.get('permit_id')}",
        )
    except Exception as exc:
        logger.debug("permit→finance failed: %s", exc)


# ---------------------------------------------------------------------------
# Tier-2 #7 — Research grant approved → grant ledger
# ---------------------------------------------------------------------------

def publish_grant_decision(application_id: int, *, status: str,
                           grant_name: str | None = None,
                           awarded_amount: float = 0.0,
                           pi_id: str | None = None,
                           grant_period_start: str | None = None,
                           grant_period_end: str | None = None) -> None:
    """Publish a grant decision so finance can ledger the award.

    Origin: ``GrantApplicationManager.update_decision``. The PI
    becomes the budget owner; subscribers ledger the awarded
    amount via ``finance_bus.raise_charge`` with
    ``reference_id='grant:<id>'`` so ``finance_bus.grant_balance``
    can subtract spend from the same ref family.
    """
    log_and_publish(
        EVENT_SELECTION_CHANGED,
        source="research",
        action="grant_decided",
        application_id=int(application_id),
        status=status,
        grant_name=grant_name,
        awarded_amount=float(awarded_amount or 0),
        pi_id=pi_id,
        grant_period_start=grant_period_start,
        grant_period_end=grant_period_end,
    )


def _on_grant_decided(**payload: Any) -> None:
    if payload.get("action") != "grant_decided":
        return
    if (payload.get("status") or "").lower() not in (
            "approved", "awarded", "accepted"):
        return
    amount = float(payload.get("awarded_amount") or 0)
    if amount <= 0:
        return
    pi_id = payload.get("pi_id")
    application_id = payload.get("application_id")
    if not pi_id:
        return
    try:
        from education_system.university_system.modules.services.finance_bus import (
            raise_charge,
        )
        # Negative-amount charge represents a *credit* into the
        # grant's tracked balance. We post it against the PI so the
        # row appears in their finance summary, with reference_id
        # tied to the grant so grant_balance() reads it back.
        raise_charge(
            pi_id, -amount,
            source="research_grant",
            description=(
                f"Grant award credit: {payload.get('grant_name') or application_id}"
            ),
            reference_id=f"grant:{application_id}",
        )
    except Exception as exc:
        logger.debug("grant→finance ledger failed: %s", exc)


# ===========================================================================
# Tier-3 engagement / yield / safeguarding-light features
# ===========================================================================

# Application-fee defaults for a clearing/admissions accept when the
# application doesn't carry one. Override per-row by setting
# admission_applications.application_fee.
_DEFAULT_APPLICATION_FEE = 25.0


# ---------------------------------------------------------------------------
# Tier-3 #8 — Event check-in → engagement KPI
# ---------------------------------------------------------------------------

def publish_event_attendance(event_id: int, *, user_id: str,
                             event_name: str | None = None,
                             event_category: str | None = None) -> None:
    """Publish an event check-in. Origin: ``EventsService.check_in_to_event``."""
    log_and_publish(
        EVENT_SELECTION_CHANGED,
        source="events",
        action="event_check_in",
        event_id=int(event_id),
        user_id=str(user_id),
        event_name=event_name,
        event_category=event_category,
    )


def _on_event_check_in(**payload: Any) -> None:
    if payload.get("action") != "event_check_in":
        return
    # Bump the Student Engagement KPI by 1. _set_kpi handles the
    # "create on first sight" path so a fresh deploy doesn't need a
    # seed migration.
    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT current_value FROM kpi_metrics "
                "WHERE kpi_name = 'Student Engagement' LIMIT 1"
            ).fetchone()
            current = float(row[0] or 0) if row else 0.0
    except Exception:
        current = 0.0
    _set_kpi(name="Student Engagement", category="engagement",
             value=current + 1)


# ---------------------------------------------------------------------------
# Tier-3 #9 — Internship placement → KPI + employer email
# ---------------------------------------------------------------------------

def publish_internship_placement(placement_id: int, *, student_id: str,
                                  internship_id: int,
                                  company: str | None = None,
                                  supervisor_email: str | None = None,
                                  start_date: str | None = None,
                                  end_date: str | None = None) -> None:
    """Publish a confirmed internship placement.

    Origin: ``internship_management.review_application`` after the
    placement INSERT.
    """
    log_and_publish(
        EVENT_SELECTION_CHANGED,
        source="careers",
        action="internship_placed",
        placement_id=int(placement_id),
        student_id=str(student_id),
        internship_id=int(internship_id),
        company=company,
        supervisor_email=supervisor_email,
        start_date=start_date,
        end_date=end_date,
    )


def _on_internship_placed(**payload: Any) -> None:
    if payload.get("action") != "internship_placed":
        return

    # Bump Internship Placements KPI.
    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT current_value FROM kpi_metrics "
                "WHERE kpi_name = 'Internship Placements' LIMIT 1"
            ).fetchone()
            current = float(row[0] or 0) if row else 0.0
    except Exception:
        current = 0.0
    _set_kpi(name="Internship Placements", category="careers",
             value=current + 1)

    # Email the employer supervisor — direct address (not a user_id).
    supervisor_email = payload.get("supervisor_email")
    if not supervisor_email:
        return
    try:
        from education_system.university_system.modules.services.email_bus import (
            send_templated,
        )
        # email_bus resolves recipients by user_id; we use the email
        # as the user_id and force send so prefs lookup doesn't 404.
        send_templated(
            supervisor_email, "careers.engagement.started",
            {
                "kind": "internship",
                "role": payload.get("company") or "internship",
                "hours_required": "see contract",
            },
            related_to=f"placement:{payload.get('placement_id')}",
            force=True,
        )
    except Exception as exc:
        logger.debug("internship→employer email failed: %s", exc)


# ---------------------------------------------------------------------------
# Tier-3 #10 — Admissions decision → yield KPI + application fee
# ---------------------------------------------------------------------------

def publish_admissions_decision(application_id: int, *,
                                decision: str,
                                applicant_id: str | None = None,
                                course: str | None = None,
                                application_fee: float | None = None,
                                fee_paid: bool = False) -> None:
    """Publish an admissions decision (pre-clearing track).

    Origin: ``admissions_crm_core.ApplicationManager.make_decision``.
    Subscriber updates yield-rate KPI (offers vs accepts) and, on
    a positive decision with unpaid fee, raises the application
    fee charge.
    """
    log_and_publish(
        EVENT_SELECTION_CHANGED,
        source="admissions",
        action="admissions_decision",
        application_id=int(application_id),
        decision=decision,
        applicant_id=str(applicant_id) if applicant_id else None,
        course=course,
        application_fee=float(application_fee) if application_fee is not None else None,
        fee_paid=bool(fee_paid),
    )


def _on_admissions_decision(**payload: Any) -> None:
    if payload.get("action") != "admissions_decision":
        return
    decision = (payload.get("decision") or "").lower()

    # Yield-rate metric: ratio of accepts to total decisions.
    _bump_yield_rate(decision)

    # Fee charge on accept when not already paid.
    if decision in ("accepted", "offer", "approved"):
        applicant_id = payload.get("applicant_id")
        if applicant_id and not payload.get("fee_paid"):
            fee = payload.get("application_fee") or _DEFAULT_APPLICATION_FEE
            try:
                from education_system.university_system.modules.services.finance_bus import (
                    raise_charge,
                )
                raise_charge(
                    applicant_id, float(fee),
                    source="admissions",
                    description="Application fee",
                    reference_id=f"admission_app:{payload.get('application_id')}",
                )
            except Exception as exc:
                logger.debug("admissions→fee charge failed: %s", exc)


def _bump_yield_rate(decision: str) -> None:
    """Update the running Yield Rate (%) KPI: accepted / decisions_made."""
    try:
        with get_connection() as conn:
            tbl = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name='admission_applications'"
            ).fetchone()
            if not tbl:
                return
            total = conn.execute(
                "SELECT COUNT(*) FROM admission_applications "
                "WHERE decision IS NOT NULL AND decision != ''"
            ).fetchone()[0] or 0
            accepted = conn.execute(
                "SELECT COUNT(*) FROM admission_applications "
                "WHERE LOWER(decision) IN ('accepted', 'offer', 'approved')"
            ).fetchone()[0] or 0
    except Exception:
        return
    if total <= 0:
        return
    rate = (accepted / total) * 100
    _set_kpi(name="Yield Rate", category="admissions", value=rate)


# ---------------------------------------------------------------------------
# Tier-3 #11 — Urgent complaint → cases_bus + dean email
# ---------------------------------------------------------------------------

def publish_complaint_filed(complaint_id: str | int, *,
                            user_id: str | None,
                            email: str | None = None,
                            category: str | None = None,
                            priority: str | None = None,
                            subject: str | None = None) -> None:
    """Publish a complaint submission.

    Origin: ``complaints_portal.insert_complaint``. Only urgent /
    high-priority complaints auto-escalate; lower priorities save
    silently.
    """
    log_and_publish(
        EVENT_INCIDENT_LOGGED,
        source="complaints",
        kind="complaint_filed",
        severity=_severity_for_priority(priority),
        complaint_id=str(complaint_id),
        user_id=str(user_id) if user_id else None,
        email=email,
        category=category,
        priority=priority,
        subject=subject,
    )


def _severity_for_priority(priority: str | None) -> str:
    p = (priority or "").lower()
    if p in ("urgent", "critical", "p0"):
        return "critical"
    if p in ("high", "p1"):
        return "high"
    if p in ("medium", "p2"):
        return "medium"
    return "low"


def _on_complaint_filed(**payload: Any) -> None:
    if payload.get("kind") != "complaint_filed":
        return
    priority = (payload.get("priority") or "").lower()
    if priority not in ("urgent", "critical", "p0", "high", "p1"):
        return  # auto-escalation only for genuine fires

    user_id = payload.get("user_id") or "unknown"

    # Open a case so disciplinary / pastoral pipelines see it.
    try:
        from education_system.university_system.modules.services.cases_bus import (
            open_case,
        )
        open_case(
            kind="complaint",
            subject_id=str(user_id),
            severity=payload.get("severity") or "high",
            description=(
                f"Urgent complaint #{payload.get('complaint_id')} — "
                f"{payload.get('category') or 'uncategorised'}: "
                f"{payload.get('subject') or ''}"
            ),
            opened_by="complaints_portal",
        )
    except Exception as exc:
        logger.debug("complaint→cases_bus failed: %s", exc)

    # Email the Dean of Students (or fallback admin).
    try:
        from education_system.university_system.modules.services.email_bus import (
            send_templated,
        )
        recipient = _dean_of_students_user_id() or _admin_user_id() or "admin"
        send_templated(
            recipient, "case.opened",
            {
                "case_id": payload.get("complaint_id"),
                "kind": "complaint",
                "severity": payload.get("severity") or "high",
            },
            related_to=f"complaint:{payload.get('complaint_id')}",
            force=True,
        )
    except Exception as exc:
        logger.debug("complaint→dean email failed: %s", exc)


def _dean_of_students_user_id() -> str | None:
    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT user_id FROM users "
                "WHERE LOWER(role) IN ('dean', 'dean_of_students', "
                "                      'student_affairs_dean') "
                "AND email IS NOT NULL LIMIT 1"
            ).fetchone()
            return str(row[0]) if row else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Tier-3 #12 — Health appointment booked → calendar conflict check
# ---------------------------------------------------------------------------

def publish_health_appointment(appointment_id: int, *, student_id: str,
                                appointment_date: str,
                                appointment_time: str,
                                provider: str | None = None,
                                appointment_type: str | None = None) -> None:
    """Publish a booked health appointment so the calendar checker
    can flag class-time clashes.

    Origin: health appointment_booking schedule_appointment.
    """
    log_and_publish(
        EVENT_INCIDENT_LOGGED,
        source="health",
        kind="health_appointment_booked",
        severity="low",
        appointment_id=int(appointment_id),
        student_id=str(student_id),
        appointment_date=str(appointment_date),
        appointment_time=str(appointment_time),
        provider=provider,
        appointment_type=appointment_type,
    )


def _on_health_appointment_booked(**payload: Any) -> None:
    if payload.get("kind") != "health_appointment_booked":
        return
    student_id = payload.get("student_id")
    appt_date = payload.get("appointment_date") or ""
    appt_time = payload.get("appointment_time") or ""
    if not (student_id and appt_date and appt_time):
        return

    # Compute the day-of-week and a 1-hour window around the
    # appointment, then check student timetable / module_schedule.
    try:
        dt = datetime.strptime(
            f"{appt_date[:10]} {appt_time[:5]}", "%Y-%m-%d %H:%M")
    except Exception:
        return
    day_name = dt.strftime("%A")
    window_start = dt.strftime("%H:%M")
    window_end = (dt + timedelta(hours=1)).strftime("%H:%M")

    clash = _has_class_at(student_id, day_name, window_start, window_end)
    if not clash:
        return

    # Notify the student via email + flag the appointment as
    # 'has_conflict' (column added lazily) so the GUI can render a
    # warning badge.
    try:
        with transaction() as conn:
            cols = {r[1] for r in conn.execute(
                "PRAGMA table_info(health_appointments)").fetchall()}
            if "has_conflict" not in cols:
                conn.execute(
                    "ALTER TABLE health_appointments "
                    "ADD COLUMN has_conflict INTEGER DEFAULT 0"
                )
            conn.execute(
                "UPDATE health_appointments SET has_conflict = 1 "
                "WHERE appointment_id = ?",
                (int(payload.get("appointment_id")),),
            )
            conn.commit()
    except Exception as exc:
        logger.debug("health appt conflict flag failed: %s", exc)

    try:
        from education_system.university_system.modules.services.email_bus import (
            send_templated,
        )
        send_templated(
            student_id, "hs.incident.logged",
            {
                "incident_id": f"appt_clash:{payload.get('appointment_id')}",
                "severity": "medium",
                "location": (
                    f"{appt_date} {appt_time} — clashes with "
                    f"{clash.get('module_code') or 'class'}"
                ),
            },
            related_to=f"appt:{payload.get('appointment_id')}",
            force=True,
        )
    except Exception as exc:
        logger.debug("health appt clash email failed: %s", exc)


def _has_class_at(student_id: str, day_of_week: str,
                   start_time: str, end_time: str) -> dict[str, Any] | None:
    """Look for a module_schedule row the student is enrolled in
    that overlaps the window.
    """
    try:
        with get_connection() as conn:
            # student_enrolment is the canonical roster table; fall
            # back to plan_courses if the former isn't present.
            for sql in (
                "SELECT ms.module_code, ms.start_time, ms.end_time "
                "FROM module_schedule ms "
                "JOIN student_enrolment se ON se.module_code = ms.module_code "
                "WHERE se.student_id = ? AND ms.day_of_week = ? "
                "  AND NOT (ms.end_time <= ? OR ms.start_time >= ?) "
                "LIMIT 1",
                "SELECT ms.module_code, ms.start_time, ms.end_time "
                "FROM module_schedule ms "
                "JOIN plan_courses pc ON pc.course_code = ms.module_code "
                "JOIN student_plans sp ON sp.plan_id = pc.plan_id "
                "WHERE sp.student_id = ? AND ms.day_of_week = ? "
                "  AND NOT (ms.end_time <= ? OR ms.start_time >= ?) "
                "LIMIT 1",
            ):
                try:
                    row = conn.execute(
                        sql, (str(student_id), day_of_week,
                              start_time, end_time),
                    ).fetchone()
                    if row:
                        return {"module_code": row[0],
                                "start_time": row[1],
                                "end_time": row[2]}
                except Exception:
                    continue
    except Exception:
        pass
    return None


# ===========================================================================
# Tier-4 academic-loop features (attendance, tutor groups, study matching)
# ===========================================================================

# Cohort attendance % below this triggers a module-level risk row.
_COHORT_RISK_THRESHOLD = 65.0


def sweep_cohort_attendance_risk(*, threshold_pct: float = _COHORT_RISK_THRESHOLD,
                                  weeks: int = 3) -> dict[str, int]:
    """Scan recent attendance per module; raise risk for cohorts below threshold.

    Reads ``attendance_records`` over the last ``weeks`` weeks,
    computes the cohort attendance % per module_code, and routes
    each below-threshold module through
    ``attendance_bus.flag_module_attendance_risk`` (which writes
    into the canonical ``risks`` table via risk_bus).

    Returns ``{"checked": N, "raised": M}``. Idempotent — risk_bus
    keys on ``reference_id='module:<code>'`` so a second sweep on
    the same window won't double-raise.
    """
    checked = 0
    raised = 0
    try:
        with get_connection() as conn:
            tbl = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name='attendance_records'"
            ).fetchone()
            if not tbl:
                return {"checked": 0, "raised": 0}
            rows = conn.execute(
                "SELECT module_code, "
                "       SUM(CASE WHEN LOWER(status) IN ('present','late','excused') "
                "                THEN 1 ELSE 0 END) AS attended, "
                "       COUNT(*) AS total "
                "FROM attendance_records "
                "WHERE julianday('now') - julianday(date) <= ? "
                "GROUP BY module_code",
                (int(weeks * 7),),
            ).fetchall()
    except Exception as exc:
        logger.warning("sweep_cohort_attendance_risk query failed: %s", exc)
        return {"checked": 0, "raised": 0}

    try:
        from education_system.university_system.modules.services.attendance_bus import (
            flag_module_attendance_risk,
        )
    except Exception:
        return {"checked": 0, "raised": 0}

    for r in rows:
        d = dict(r)
        if not d["total"]:
            continue
        checked += 1
        pct = float(d["attended"] or 0) / float(d["total"]) * 100.0
        if pct < threshold_pct:
            try:
                rid = flag_module_attendance_risk(
                    d["module_code"],
                    cohort_pct=pct, weeks_observed=weeks,
                )
                if rid:
                    raised += 1
            except Exception as exc:
                logger.debug("flag_module_attendance_risk failed for %s: %s",
                             d["module_code"], exc)

    return {"checked": checked, "raised": raised}


# ---------------------------------------------------------------------------
# Tier-4 #20 — attendance concern → tutor group agenda
# ---------------------------------------------------------------------------

def _on_case_opened_for_tutor_group(**payload: Any) -> None:
    """Append a pastoral agenda item to the next tutor-group meeting
    when an attendance_concern case is opened.

    cases_bus publishes via EVENT_CASE_OPENED. We filter on
    ``kind='attendance_concern'`` so other case kinds don't crowd
    the tutor's calendar.
    """
    if (payload.get("kind") or "").lower() != "attendance_concern":
        return
    student_id = payload.get("subject_id")
    case_id = payload.get("case_id") or payload.get("record_id")
    if not student_id:
        return

    try:
        with get_connection() as conn:
            tbl = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name='tutor_group_members'"
            ).fetchone()
            if not tbl:
                return
            grp = conn.execute(
                "SELECT m.group_id FROM tutor_group_members m "
                "WHERE m.student_id = ? AND m.is_active = 1 "
                "ORDER BY m.membership_id DESC LIMIT 1",
                (str(student_id),),
            ).fetchone()
            if not grp:
                return
            group_id = grp[0]
            meeting = conn.execute(
                "SELECT meeting_id, agenda FROM tutor_group_meetings "
                "WHERE group_id = ? AND status = 'scheduled' "
                "  AND scheduled_at >= datetime('now') "
                "ORDER BY scheduled_at ASC LIMIT 1",
                (group_id,),
            ).fetchone()
    except Exception as exc:
        logger.debug("tutor_group lookup failed: %s", exc)
        return

    note = (
        f"Attendance concern: student {student_id} "
        f"(case #{case_id}) — review intervention plan."
    )
    try:
        with transaction() as conn:
            if meeting and meeting[0]:
                # Append to the next scheduled meeting's agenda.
                existing = (meeting[1] or "").rstrip()
                new_agenda = f"{existing}\n• {note}".lstrip()
                conn.execute(
                    "UPDATE tutor_group_meetings SET agenda = ? "
                    "WHERE meeting_id = ?",
                    (new_agenda, meeting[0]),
                )
            else:
                # No upcoming meeting — drop a placeholder so the
                # tutor sees the flag on the dashboard.
                conn.execute(
                    "INSERT INTO tutor_group_meetings "
                    "(group_id, scheduled_at, duration_minutes, agenda, status) "
                    "VALUES (?, ?, 30, ?, 'pending')",
                    (group_id,
                     datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                     f"• {note}"),
                )
            conn.commit()
    except Exception as exc:
        logger.debug("tutor_group agenda update failed: %s", exc)


# ---------------------------------------------------------------------------
# Tier-4 #21 — enrolment → study matching auto-suggest
# ---------------------------------------------------------------------------

# Cap on auto-suggestions per enrolment so a popular module doesn't
# spam the suggestion table.
_STUDY_MATCH_LIMIT = 3


def publish_enrolment_added(student_id: str, course_code: str,
                            *, source: str = "course_management") -> None:
    """Origin: enrolment writers (student_registration, course
    catalog, grade_tracking module_manager). Publishes through the
    canonical EVENT_ENROLMENT_CHANGED so consumers (study matching
    auto-suggest, exam roster, finance) can react.
    """
    log_and_publish(
        EVENT_ENROLMENT_CHANGED,
        source=source,
        action="enrolled",
        student_id=str(student_id),
        course_code=course_code,
    )


def _on_enrolment_added(**payload: Any) -> None:
    if payload.get("action") not in ("enrolled", "added"):
        return
    student_id = payload.get("student_id")
    course_code = payload.get("course_code")
    if not (student_id and course_code):
        return

    try:
        from education_system.university_system.modules.domain.academics.study_matching.services.study_matching_service import (
            StudyMatchingService,
        )
        svc = StudyMatchingService()
        matches = svc.find_study_matches(
            str(student_id), course_id=course_code, limit=_STUDY_MATCH_LIMIT,
        ) or []
    except Exception as exc:
        logger.debug("study matches lookup failed: %s", exc)
        return

    for m in matches:
        peer_id = m.get("student_id") or m.get("matched_student_id")
        if not peer_id:
            continue
        try:
            svc.create_match_suggestion(
                str(student_id), str(peer_id),
                course_id=course_code,
            )
        except Exception as exc:
            logger.debug("create_match_suggestion failed: %s", exc)


# ---------------------------------------------------------------------------
# Wire-up
# ---------------------------------------------------------------------------

_WIRED = False


def wire_subscribers() -> None:
    """Idempotently subscribe every consumer-side handler.

    Safe to call multiple times — internal flag prevents duplicate
    registrations. Call from the unified launcher or each GUI's
    bootstrap if running in isolation.
    """
    global _WIRED
    if _WIRED:
        return
    _ensure_log_table()
    subscribe(EVENT_COURSE_CHANGED, _on_clearing_accepted)
    subscribe(EVENT_COURSE_CHANGED, _on_adjustment_approved)
    subscribe(EVENT_COURSE_CHANGED, _on_apl_approved)
    subscribe(EVENT_COURSE_CHANGED, _on_demand_forecast)
    subscribe(EVENT_STAFF_AVAILABILITY_CHANGED, _on_staff_availability_changed)
    subscribe(EVENT_MODULE_SCHEDULE_CHANGED, _on_timetable_locked)
    subscribe(EVENT_MODULE_SCHEDULE_CHANGED, _on_module_schedule_changed_for_exams)
    subscribe(EVENT_SELECTION_CHANGED, _on_appraisal_completed)
    subscribe(EVENT_EXAM_CHANGED, _on_exam_event)
    subscribe(EVENT_TERM_CHANGED, _on_term_changed)
    subscribe(EVENT_ENROLMENT_CHANGED, _on_enrolment_withdrew)
    subscribe(EVENT_INCIDENT_LOGGED, _on_health_risk_assessment)
    subscribe(EVENT_INCIDENT_LOGGED, _on_housing_move_out)
    subscribe(EVENT_INCIDENT_LOGGED, _on_permit_issued)
    subscribe(EVENT_INCIDENT_LOGGED, _on_complaint_filed)
    subscribe(EVENT_INCIDENT_LOGGED, _on_health_appointment_booked)
    subscribe(EVENT_SELECTION_CHANGED, _on_accommodation_decided)
    subscribe(EVENT_SELECTION_CHANGED, _on_grant_decided)
    subscribe(EVENT_SELECTION_CHANGED, _on_event_check_in)
    subscribe(EVENT_SELECTION_CHANGED, _on_internship_placed)
    subscribe(EVENT_SELECTION_CHANGED, _on_admissions_decision)
    subscribe(EVENT_CASE_OPENED, _on_case_opened_for_tutor_group)
    subscribe(EVENT_ENROLMENT_CHANGED, _on_enrolment_added)
    _WIRED = True
    logger.info("integration_bus subscribers wired")


def reset_for_tests() -> None:
    """Test-only — flip the wired flag back so wire_subscribers can re-run."""
    global _WIRED
    _WIRED = False


__all__ = [
    "log_and_publish",
    "recent_events",
    "resolve_student_id",
    "publish_clearing_accepted",
    "publish_adjustment_approved",
    "publish_apl_approved",
    "publish_leave_decision",
    "publish_timetable_locked",
    "publish_demand_forecast",
    "publish_appraisal_completed",
    "publish_cert_expiry",
    "publish_waitlist_promoted",
    "promote_from_waitlist",
    "run_degree_audit_sweep",
    "sweep_expiring_certifications",
    "publish_exam_event",
    "can_student_start_exam",
    "send_finance_report",
    "sweep_ungraded_exams",
    "is_exam_within_term",
    "publish_enrolment_withdrew",
    "publish_health_risk_assessment",
    "publish_accommodation_decision",
    "sweep_overdue_mail",
    "publish_housing_move_out",
    "publish_permit_issued",
    "publish_grant_decision",
    "publish_event_attendance",
    "publish_internship_placement",
    "publish_admissions_decision",
    "publish_complaint_filed",
    "publish_health_appointment",
    "publish_enrolment_added",
    "sweep_cohort_attendance_risk",
    "wire_subscribers",
    "reset_for_tests",
]
