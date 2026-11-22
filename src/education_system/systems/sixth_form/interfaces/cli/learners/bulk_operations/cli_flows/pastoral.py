"""CLI flows for behaviour and pastoral bulk operations.

Split out of ``bulk_operations_cli.py``, which re-exports every name here.
"""

from __future__ import annotations

from datetime import date as _date

from education_system.systems.sixth_form.domain.learners.bulk_operations import ops_behaviour as bulk_ops_behaviour
from education_system.systems.sixth_form.domain.learners.bulk_operations.base import ValidationError

from education_system.systems.sixth_form.interfaces.cli.learners.bulk_operations.cli_flows.prompts import (
    _input,
    _pause,
    _pick_from,
    _pick_students,
    _print_result,
    _UserAbort,
    _yes_no,
)


# ── Operation flows ────────────────────────────────────────────────

def bulk_behaviour() -> None:
    print("\n═══ Bulk Log Behaviour ═══")
    try:
        sids = _pick_students()
        entry_type = _pick_from("Entry type", ["Positive", "Negative"],
                                  default="Positive")
        category = _input("Category", allow_empty=False)
        description = _input("Description", allow_empty=False)
        date_str = _input("Date (YYYY-MM-DD)",
                            default=_date.today().isoformat())
        severity = _input("Severity (Low/Medium/High; optional)") or None
        points_raw = _input("Points", default="0")
        location = _input("Location") or None
        recorded_by = _input("Recorded by") or None
        action = _input("Action taken") or None
        follow_up = _yes_no("Follow-up required?", default=False)
        dry = _yes_no("Preview (dry run)?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        points = int(points_raw or 0)
    except ValueError:
        print("  ✗ Points must be a number.")
        _pause()
        return
    try:
        r = bulk_ops_behaviour.bulk_log_behaviour(
            sids, entry_date=date_str, entry_type=entry_type,
            category=category, description=description,
            severity=severity, points=points, location=location,
            recorded_by=recorded_by, action_taken=action,
            follow_up_required=follow_up, dry_run=dry,
        )
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_accommodation() -> None:
    print("\n═══ Bulk Add Accommodation ═══")
    try:
        sids = _pick_students()
        name = _input("Accommodation name", allow_empty=False)
        category = _input("Category", default="Exam Access")
        description = _input("Description") or None
        status = _input("Status", default="Active")
        start_date = _input("Start date (YYYY-MM-DD)",
                              default=_date.today().isoformat())
        end_date = _input("End date") or None
        approved_by = _input("Approved by") or None
        approved_date = _input("Approved date") or None
        dry = _yes_no("Preview (dry run)?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = bulk_ops_behaviour.bulk_add_accommodation(
            sids, name=name, category=category, description=description,
            status=status, start_date=start_date, end_date=end_date,
            approved_by=approved_by, approved_date=approved_date,
            dry_run=dry,
        )
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_detention_flow() -> None:
    print("\n═══ Bulk Issue Detentions ═══")
    try:
        sids = _pick_students()
        date_str = _input("Date", default=_date.today().isoformat())
        reason = _input("Reason", allow_empty=False)
        duration = int(_input("Duration (minutes)", default="30"))
        room = _input("Room") or None
        severity = _pick_from("Severity",
                                ["Low", "Medium", "High"],
                                default="Low")
        by = _input("Recorded by") or None
        dry = _yes_no("Preview (dry run)?", default=False)
    except (_UserAbort, ValueError):
        print("\n  Cancelled / bad input.")
        return
    try:
        r = bulk_ops_behaviour.bulk_issue_detentions(
            sids, date=date_str, reason=reason,
            duration_minutes=duration, room=room,
            severity=severity, recorded_by=by, dry_run=dry,
        )
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_merits_flow() -> None:
    print("\n═══ Bulk Award Merits / House Points ═══")
    try:
        sids = _pick_students()
        date_str = _input("Date", default=_date.today().isoformat())
        category = _pick_from(
            "Category",
            ["Excellent Work", "Participation", "Helpfulness",
             "Leadership", "Improvement", "Achievement",
             "Attendance", "Effort", "Community Contribution",
             "Other"], default="Achievement")
        description = _input("Description", allow_empty=False)
        points = int(_input("Points", default="5"))
        by = _input("Recorded by") or None
        dry = _yes_no("Preview (dry run)?", default=False)
    except (_UserAbort, ValueError):
        print("\n  Cancelled / bad input.")
        return
    try:
        r = bulk_ops_behaviour.bulk_award_merits(
            sids, date=date_str, category=category,
            description=description, points=points,
            recorded_by=by, dry_run=dry,
        )
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_escalate_flow() -> None:
    print("\n═══ Bulk Escalate Behaviour ═══")
    try:
        sids = _pick_students()
        date_str = _input("Date", default=_date.today().isoformat())
        reason = _input("Reason", allow_empty=False)
        to = _input("Escalate to", default="Senior Tutor")
        follow_up = _input("Follow-up date") or None
        by = _input("Recorded by") or None
        dry = _yes_no("Preview (dry run)?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = bulk_ops_behaviour.bulk_escalate_behaviour(
            sids, date=date_str, reason=reason,
            escalate_to=to, follow_up_date=follow_up,
            recorded_by=by, dry_run=dry,
        )
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_safeguarding_flow() -> None:
    print("\n═══ Bulk Safeguarding Flag ═══")
    try:
        from education_system.systems.sixth_form.domain.safeguarding.safeguarding import (
            CONCERN_TYPES, CATEGORIES, RISK_LEVELS,
        )
        sids = _pick_students()
        cdate = _input("Concern date",
                         default=_date.today().isoformat())
        rdate = _input("Reported date",
                         default=_date.today().isoformat())
        ctype = _pick_from("Concern type", list(CONCERN_TYPES),
                              default=CONCERN_TYPES[0])
        cat = _pick_from("Category", list(CATEGORIES),
                            default=CATEGORIES[0])
        risk = _pick_from("Risk level", list(RISK_LEVELS),
                              default="Medium")
        by = _input("Reported by", allow_empty=False)
        desc = _input("Description", allow_empty=False)
        dsl = _yes_no("DSL notified?", default=False)
        dsl_name = _input("DSL name") or None if dsl else None
        dry = _yes_no("Preview (dry run)?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = bulk_ops_behaviour.bulk_safeguarding_flag(
            sids, concern_date=cdate, reported_date=rdate,
            concern_type=ctype, category=cat, risk_level=risk,
            reported_by=by, description=desc,
            dsl_notified=dsl, dsl_name=dsl_name, dry_run=dry,
        )
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_mentors_flow() -> None:
    print("\n═══ Bulk Assign Mentors ═══")
    try:
        from education_system.systems.sixth_form.domain.pastoral.peer_mentoring.peer_mentoring import (
            PROGRAMMES, FREQUENCIES, DEFAULT_FREQUENCY,
        )
        mentor_id = _input("Mentor student id", allow_empty=False)
        print("  Pick mentees:")
        mentees = _pick_students()
        programme = _pick_from("Programme", list(PROGRAMMES),
                                  default=PROGRAMMES[0])
        start = _input("Start date",
                         default=_date.today().isoformat())
        frequency = _pick_from("Frequency", list(FREQUENCIES),
                                  default=DEFAULT_FREQUENCY)
        coord = _input("Coordinator") or None
        planned_end = _input("Planned end") or None
        sessions_raw = _input("Sessions planned") or ""
        dry = _yes_no("Preview (dry run)?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    sessions = None
    if sessions_raw:
        try:
            sessions = int(sessions_raw)
        except ValueError:
            print("  ✗ Sessions planned must be a number.")
            _pause()
            return
    try:
        r = bulk_ops_behaviour.bulk_assign_mentors(
            mentees, mentor_id=mentor_id, programme=programme,
            start_date=start, frequency=frequency,
            coordinator=coord, planned_end=planned_end,
            sessions_planned=sessions, dry_run=dry,
        )
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


# ── Communications / finance / exams flows ─────────────────────────

def bulk_reset_points_flow() -> None:
    print("\n═══ Bulk Reset Behaviour Points ═══")
    try:
        sids = _pick_students()
        df = _input("Window from (YYYY-MM-DD)", allow_empty=False)
        dt = _input("Window to (YYYY-MM-DD)",
                       default=_date.today().isoformat())
        reset_date = _input("Reset date",
                               default=_date.today().isoformat())
        note = _input("Note", default="Term reset")
        by = _input("Recorded by") or None
        dry = _yes_no("Preview (dry run)?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = bulk_ops_behaviour.bulk_reset_behaviour_points(
            sids, date_from=df, date_to=dt, reset_date=reset_date,
            note=note, recorded_by=by, dry_run=dry)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)
