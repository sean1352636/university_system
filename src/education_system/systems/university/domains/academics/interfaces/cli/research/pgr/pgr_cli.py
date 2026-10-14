"""Console menu for postgraduate research administration - mirrors room_booking_cli."""
from __future__ import annotations

import json
from typing import Any, Callable

from education_system.systems.university.domains.academics.domain.research.pgr import service
from education_system.systems.university.infrastructure.i18n import get_text

auth: Any = None
_PREFIX = "cli.academics.pgr"


def set_auth(auth_object: Any) -> None:
    global auth
    auth = auth_object


def _t(key: str, default: str) -> str:
    return get_text(f"{_PREFIX}.{key}", default=default)


def _actor() -> str:
    user = getattr(auth, "current_user", None) or {}
    return str(user.get("username") or user.get("id") or "cli")


def _require_staff() -> bool:
    user = getattr(auth, "current_user", None) or {}
    if not user:
        print(_t("login_required", "You must be logged in to access PGR administration."))
        return False
    if str(user.get("role", "")).lower() not in ("admin", "staff"):
        print(_t("staff_only", "PGR administration is restricted to staff."))
        return False
    return True


def _ask(prompt: str, default: str = "") -> str:
    value = input(f"{prompt}{f' [{default}]' if default else ''}: ").strip()
    return value or default


def _ask_int(prompt: str) -> int:
    return int(_ask(prompt))


def _ask_list(prompt: str) -> list[str]:
    raw = _ask(prompt + " (comma-separated)")
    return [item.strip() for item in raw.split(",") if item.strip()]


def _print_table(rows: list[dict[str, Any]], columns: list[tuple[str, int]]) -> None:
    if not rows:
        print(_t("no_rows", "Nothing to show."))
        return
    header = " ".join(f"{name:<{width}}" for name, width in columns)
    print("\n" + header)
    print("-" * len(header))
    for row in rows:
        print(" ".join(f"{str(row.get(name) if row.get(name) is not None else '-')[:width]:<{width}}"
                       for name, width in columns))
    print(f"\n{_t('total', 'Total')}: {len(rows)}")


# --- actions ---------------------------------------------------------------

def _list_projects() -> None:
    status = _ask("Filter by status (blank for all)")
    _print_table(service.list_projects(status or None),
                 [("project_id", 6), ("student_id", 10), ("proposal_title", 36),
                  ("route", 10), ("status", 16), ("department", 14)])


def _show_project() -> None:
    record = service.project_record(_ask_int("Project ID"))
    print(f"\n#{record['project_id']} {record['proposal_title']} - {record['student_id']} "
          f"[{record['status']}] route={record['route']} deadline={record['current_deadline']}")
    sections = [
        ("Supervisors", "supervisors", [("allocation_id", 6), ("supervisor_id", 12),
                                        ("role", 10), ("workload_fte", 6), ("active", 6)]),
        ("Meetings", "meetings", [("meeting_id", 6), ("meeting_at", 18),
                                  ("progress_summary", 40), ("next_meeting_date", 12)]),
        ("Training needs", "training_needs", [("need_id", 6), ("category", 14),
                                              ("description", 30), ("priority", 8),
                                              ("status", 10)]),
        ("Reviews", "reviews", [("review_id", 6), ("review_year", 4), ("due_date", 10),
                                ("status", 10), ("outcome", 14)]),
        ("Approvals", "approvals", [("approval_id", 6), ("approval_type", 14),
                                    ("reference", 14), ("status", 10), ("expires_at", 10)]),
        ("Upgrades", "upgrades", [("upgrade_id", 6), ("report_reference", 16),
                                  ("status", 10), ("outcome", 10)]),
        ("Thesis submissions", "submissions", [("submission_id", 6), ("version", 4),
                                               ("thesis_title", 30), ("submitted_at", 20)]),
        ("Examiners", "examiners", [("nomination_id", 6), ("examiner_id", 12),
                                    ("examiner_type", 9), ("institution", 16), ("status", 10)]),
        ("Vivas", "vivas", [("viva_id", 6), ("scheduled_at", 18), ("location", 14),
                            ("status", 10), ("outcome", 16)]),
        ("Corrections", "corrections", [("correction_id", 6), ("correction_type", 16),
                                        ("due_date", 10), ("status", 12)]),
        ("Deposits", "deposits", [("deposit_id", 6), ("repository_reference", 20),
                                  ("licence", 10), ("embargo_until", 10)]),
        ("Milestones", "milestones", [("milestone_id", 6), ("milestone_type", 12),
                                      ("title", 24), ("due_date", 10), ("status", 10),
                                      ("extension_until", 10)]),
        ("History", "history", [("created_at", 20), ("action", 24), ("from_status", 14),
                                ("to_status", 14), ("actor_id", 12)]),
    ]
    for title, key, columns in sections:
        print(f"\n{title}:")
        _print_table(record.get(key, []), columns)


def _create_project() -> None:
    project_id = service.create_project(
        _ask("Student ID"), _ask("Proposal title"), _ask("Abstract"),
        created_by=_actor(), research_questions=_ask("Research questions"),
        methodology=_ask("Methodology"), department=_ask("Department"),
        route=_ask("Route", "MPhil/PhD"),
        start_date=_ask("Start date (YYYY-MM-DD)") or None,
        expected_end_date=_ask("Expected end date (YYYY-MM-DD)") or None,
    )
    print(f"PGR project #{project_id} created.")


def _set_registration() -> None:
    service.set_registration(_ask_int("Project ID"), _ask("Route (mphil/phd)", "mphil"),
                             actor_id=_actor())
    print("Registration recorded.")


def _add_supervisor() -> None:
    allocation_id = service.add_supervisor(
        _ask_int("Project ID"), _ask("Supervisor ID"),
        _ask("Role (primary/secondary/advisor)", "primary"),
        workload_fte=float(_ask("Workload FTE", "0.5")), start_date=_ask("Start date"))
    print(f"Supervisor allocation #{allocation_id} added.")


def _supervisor_workload() -> None:
    workload = service.supervisor_workload(_ask("Supervisor ID"))
    print(f"\nTotal FTE: {workload['total_fte']:.2f}")
    _print_table(workload["projects"], [("project_id", 6), ("student_id", 10),
                                        ("proposal_title", 36), ("role", 10),
                                        ("workload_fte", 6)])


def _log_meeting() -> None:
    meeting_id = service.log_supervision(
        _ask_int("Project ID"), _ask("Meeting at (YYYY-MM-DD HH:MM)"), _ask_list("Attendees"),
        progress_summary=_ask("Progress summary"),
        actions=[{"action": a} for a in _ask_list("Actions")],
        created_by=_actor(), next_meeting_date=_ask("Next meeting date") or None)
    print(f"Supervision meeting #{meeting_id} logged.")


def _add_training_need() -> None:
    need_id = service.add_training_need(
        _ask_int("Project ID"), _ask("Category"), _ask("Description"),
        priority=_ask("Priority", "normal"), planned_activity=_ask("Planned activity"),
        target_date=_ask("Target date") or None)
    print(f"Training need #{need_id} added.")


def _schedule_review() -> None:
    review_id = service.schedule_review(_ask_int("Project ID"), _ask_int("Review year"),
                                        _ask("Due date (YYYY-MM-DD)"))
    print(f"Progress review #{review_id} scheduled.")


def _decide_review() -> None:
    service.decide_review(
        _ask_int("Review ID"), _ask("Outcome (satisfactory/conditional/unsatisfactory)"),
        panel=_ask_list("Panel"), approved_by=_actor(),
        student_report=_ask("Student report"), supervisor_report=_ask("Supervisor report"),
        conditions=_ask("Conditions"))
    print("Review decided.")


def _record_approval() -> None:
    approval_id = service.record_approval(
        _ask_int("Project ID"), _ask("Approval type", "ethics"), reference=_ask("Reference"),
        status=_ask("Status (approved/pending/rejected)", "approved"), approved_by=_actor(),
        risk_level=_ask("Risk level"), expires_at=_ask("Expires at") or None,
        conditions=_ask("Conditions"))
    print(f"Approval #{approval_id} recorded.")


def _submit_upgrade() -> None:
    upgrade_id = service.submit_upgrade(_ask_int("Project ID"), _ask("Report reference"),
                                        _ask_list("Panel"))
    print(f"Upgrade #{upgrade_id} submitted.")


def _decide_upgrade() -> None:
    service.decide_upgrade(_ask_int("Upgrade ID"), _ask("Outcome (approved/revisions/rejected)"),
                           decided_by=_actor(), conditions=_ask("Conditions"))
    print("Upgrade decided.")


def _submit_thesis() -> None:
    submission_id = service.submit_thesis(
        _ask_int("Project ID"), _ask("Thesis title"), _ask("Repository reference"),
        declaration_accepted=_ask("Declaration accepted? (y/n)", "n").lower().startswith("y"))
    print(f"Thesis submission #{submission_id} recorded.")


def _nominate_examiner() -> None:
    nomination_id = service.nominate_examiner(
        _ask_int("Project ID"), _ask("Examiner ID"), _ask("Type (internal/external)"),
        institution=_ask("Institution"), expertise=_ask("Expertise"),
        conflict_declaration=_ask("Conflict declaration"), nominated_by=_actor())
    print(f"Examiner nomination #{nomination_id} recorded.")


def _approve_examiner() -> None:
    service.approve_examiner(_ask_int("Nomination ID"), approved_by=_actor())
    print("Examiner approved.")


def _schedule_viva() -> None:
    viva_id = service.schedule_viva(_ask_int("Project ID"), _ask("Scheduled at (YYYY-MM-DD HH:MM)"),
                                    location=_ask("Location"), chair_id=_ask("Chair ID", _actor()))
    print(f"Viva #{viva_id} scheduled.")


def _record_viva_outcome() -> None:
    service.record_viva_outcome(
        _ask_int("Project ID"),
        _ask("Outcome (pass/minor_corrections/major_corrections/resubmit/fail)"),
        decided_by=_actor(), notes=_ask("Notes"),
        corrections_due=_ask("Corrections due (YYYY-MM-DD, if any)") or None,
        corrections=_ask("Corrections required"))
    print("Viva outcome recorded.")


def _approve_corrections() -> None:
    service.approve_corrections(_ask_int("Correction ID"), approved_by=_actor())
    print("Corrections approved.")


def _final_deposit() -> None:
    deposit_id = service.final_deposit(
        _ask_int("Project ID"), _ask("Repository reference"), licence=_ask("Licence", "CC BY"),
        checked_by=_actor(), embargo_until=_ask("Embargo until") or None)
    print(f"Final deposit #{deposit_id} recorded; project completed.")


def _add_milestone() -> None:
    milestone_id = service.add_milestone(_ask_int("Project ID"), _ask("Milestone type"),
                                         _ask("Title"), _ask("Due date (YYYY-MM-DD)"))
    print(f"Milestone #{milestone_id} added.")


def _extend_milestone() -> None:
    service.extend_milestone(_ask_int("Milestone ID"), _ask("Extension until (YYYY-MM-DD)"),
                             reason=_ask("Reason"), approved_by=_actor())
    print("Milestone extended.")


def _escalate_overdue() -> None:
    created = service.escalate_overdue(as_of=_ask("As of (YYYY-MM-DD, blank for today)") or None)
    print(f"{created} overdue escalation(s) created.")


_ACTIONS: dict[str, tuple[str, Callable[[], None]]] = {
    "1": ("List projects", _list_projects),
    "2": ("Show project", _show_project),
    "3": ("Create proposal", _create_project),
    "4": ("Register (MPhil/PhD)", _set_registration),
    "5": ("Add supervisor", _add_supervisor),
    "6": ("Supervisor workload", _supervisor_workload),
    "7": ("Log supervision meeting", _log_meeting),
    "8": ("Add training need", _add_training_need),
    "9": ("Schedule progress review", _schedule_review),
    "10": ("Decide progress review", _decide_review),
    "11": ("Record ethics/governance approval", _record_approval),
    "12": ("Submit upgrade", _submit_upgrade),
    "13": ("Decide upgrade", _decide_upgrade),
    "14": ("Submit thesis", _submit_thesis),
    "15": ("Nominate examiner", _nominate_examiner),
    "16": ("Approve examiner", _approve_examiner),
    "17": ("Schedule viva", _schedule_viva),
    "18": ("Record viva outcome", _record_viva_outcome),
    "19": ("Approve corrections", _approve_corrections),
    "20": ("Final deposit", _final_deposit),
    "21": ("Add milestone", _add_milestone),
    "22": ("Extend milestone", _extend_milestone),
    "23": ("Escalate overdue items", _escalate_overdue),
}


def display_pgr_menu() -> None:
    """Top-level postgraduate research administration menu."""
    if not _require_staff():
        return
    while True:
        print(f"\n{_t('title', 'Postgraduate Research Administration')}")
        print("=" * 40)
        for key, (label, _) in _ACTIONS.items():
            print(f"{key}. {label}")
        print(f"0. {_t('back', 'Return to Previous Menu')}")
        choice = input(f"\n{_t('choice', 'Enter your choice')}: ").strip()
        if choice == "0":
            return
        action = _ACTIONS.get(choice)
        if not action:
            print(_t("invalid", "Invalid choice."))
            continue
        try:
            action[1]()
        except KeyboardInterrupt:
            print("\nCancelled.")
        except (ValueError, json.JSONDecodeError) as exc:
            print(f"Error: {exc}")
