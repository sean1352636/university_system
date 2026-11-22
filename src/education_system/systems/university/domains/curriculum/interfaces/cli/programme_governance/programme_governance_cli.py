"""Console menu for programme governance - mirrors room_booking_cli."""
from __future__ import annotations

import json
from typing import Any, Callable

from education_system.systems.university.domains.curriculum.domain.programme_governance import (
    service,
)
from education_system.systems.university.infrastructure.i18n import get_text

auth: Any = None
_PREFIX = "cli.academics.programme_governance"


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
        print(_t("login_required", "You must be logged in to access programme governance."))
        return False
    if str(user.get("role", "")).lower() not in ("admin", "staff"):
        print(_t("staff_only", "Programme governance is restricted to staff."))
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


def _ask_json(prompt: str, default: str = "{}") -> dict[str, Any]:
    raw = _ask(prompt + " (JSON object)", default)
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("Expected a JSON object")
    return value


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

def _list_programmes() -> None:
    _print_table(
        service.list_programmes(),
        [("programme_id", 6), ("programme_code", 12), ("programme_name", 30),
         ("award_type", 10), ("status", 10), ("latest_version", 8)],
    )


def _show_programme() -> None:
    record = service.programme_record(_ask_int("Programme ID"))
    print(f"\n{record['programme_code']} - {record['programme_name']} "
          f"[{record['status']}] ({record['award_type']})")
    print("\nProposals:")
    _print_table(record["proposals"], [("proposal_id", 6), ("proposed_start_year", 8),
                                       ("status", 22), ("rationale", 40)])
    print("\nBusiness cases:")
    _print_table(record["business_cases"], [("business_case_id", 6), ("proposal_id", 6),
                                            ("approved", 8), ("approved_by", 14)])
    print("\nVersions:")
    _print_table(record["versions"], [("version_id", 6), ("version_number", 4),
                                      ("effective_academic_year", 10), ("status", 12),
                                      ("validation_outcome", 12), ("approved_by", 14)])
    print("\nAmendments:")
    _print_table(record["amendments"], [("amendment_id", 6), ("source_version_id", 6),
                                        ("target_version_id", 6), ("amendment_type", 12),
                                        ("status", 10), ("summary", 30)])
    print("\nAccreditations:")
    _print_table(record["accreditations"], [("accreditation_id", 6), ("body_name", 20),
                                            ("status", 12), ("valid_until", 10)])
    print("\nTeach-out plans:")
    _print_table(record["teach_out_plans"], [("plan_id", 6), ("last_intake_year", 10),
                                             ("final_delivery_year", 10), ("status", 10)])
    print("\nHistory:")
    _print_table(record["history"], [("created_at", 20), ("action", 24), ("actor_id", 14),
                                     ("version_id", 6), ("reason", 30)])


def _create_proposal() -> None:
    programme_id, proposal_id = service.create_proposal(
        _ask("Programme code"), _ask("Programme name"), _ask("Award type", "BSc"),
        _ask("Proposed start year", "2027/28"),
        created_by=_actor(), rationale=_ask("Rationale"),
        market_need=_ask("Market need"), strategic_alignment=_ask("Strategic alignment"),
        owning_school=_ask("Owning school"),
    )
    print(f"Programme #{programme_id} created with proposal #{proposal_id}.")


def _record_business_case() -> None:
    case_id = service.record_business_case(
        _ask_int("Proposal ID"),
        forecast_students=_ask_json("Forecast students", '{"year1": 30}'),
        income=_ask_json("Income", '{"year1": 0}'),
        costs=_ask_json("Costs", '{"year1": 0}'),
        staffing_plan=_ask("Staffing plan"), facilities_plan=_ask("Facilities plan"),
        risk_register=_ask("Risk register"),
    )
    print(f"Business case #{case_id} recorded.")


def _approve_business_case() -> None:
    service.approve_business_case(_ask_int("Business case ID"), approved_by=_actor())
    print("Business case approved.")


def _create_version() -> None:
    supersedes = _ask("Supersedes version ID (blank for none)")
    version_id = service.create_version(
        _ask_int("Programme ID"), _ask("Effective academic year", "2027/28"),
        curriculum=_ask_json("Curriculum", '{"modules": []}'),
        regulations=_ask_json("Regulations", '{"pass_mark": 40}'),
        created_by=_actor(),
        supersedes_version_id=int(supersedes) if supersedes else None,
    )
    print(f"Draft version #{version_id} created.")


def _amend_draft() -> None:
    version_id = _ask_int("Draft version ID")
    curriculum = _ask("New curriculum JSON (blank to keep)")
    regulations = _ask("New regulations JSON (blank to keep)")
    service.amend_draft(
        version_id,
        curriculum=json.loads(curriculum) if curriculum else None,
        regulations=json.loads(regulations) if regulations else None,
        actor_id=_actor(),
    )
    print("Draft amended.")


def _propose_amendment() -> None:
    amendment_id, target = service.propose_amendment(
        _ask_int("Approved source version ID"), _ask("Amendment type", "minor"),
        _ask("Summary"), _ask("Impact assessment"),
        requested_by=_actor(), effective_academic_year=_ask("Effective academic year"),
    )
    print(f"Amendment #{amendment_id} proposed; new draft version #{target}.")


def _list_committees() -> None:
    _print_table(service.list_committees(),
                 [("committee_id", 6), ("name", 30), ("committee_type", 16), ("quorum", 6)])


def _create_committee() -> None:
    committee_id = service.create_committee(
        _ask("Committee name"), _ask("Committee type", "validation"), _ask_int("Quorum"))
    print(f"Committee #{committee_id} created.")


def _validate_version() -> None:
    validation_id = service.validate_version(
        _ask_int("Draft version ID"), _ask_int("Committee ID"),
        _ask("Meeting at (YYYY-MM-DD HH:MM)"), _ask_list("Members present"),
        external_advisers=_ask_list("External advisers"),
        outcome=_ask("Outcome (approved/conditional/rejected)", "approved"),
        conditions=_ask_list("Conditions"), minutes_reference=_ask("Minutes reference"),
        chair_id=_ask("Chair ID", _actor()),
    )
    print(f"Validation #{validation_id} recorded.")


def _approve_version() -> None:
    service.approve_version(_ask_int("Validated version ID"), approved_by=_actor())
    print("Version approved and frozen.")


def _record_accreditation() -> None:
    version = _ask("Version ID (blank for none)")
    accreditation_id = service.record_accreditation(
        _ask_int("Programme ID"), _ask("Accrediting body"), _ask("Status", "accredited"),
        version_id=int(version) if version else None,
        accreditation_reference=_ask("Reference"),
        valid_from=_ask("Valid from (YYYY-MM-DD)") or None,
        valid_until=_ask("Valid until (YYYY-MM-DD)") or None,
        conditions=_ask("Conditions"), evidence_reference=_ask("Evidence reference"),
    )
    print(f"Accreditation #{accreditation_id} recorded.")


def _create_teach_out() -> None:
    version = _ask("Version ID (blank for none)")
    plan_id = service.create_teach_out(
        _ask_int("Programme ID"), version_id=int(version) if version else None,
        last_intake_year=_ask("Last intake year"), final_delivery_year=_ask("Final delivery year"),
        student_communication=_ask("Student communication plan"),
        staffing_commitment=_ask("Staffing commitment"),
        module_availability=_ask_json("Module availability", "{}"), approved_by=_actor(),
    )
    print(f"Teach-out plan #{plan_id} created; programme is now in teach-out.")


def _set_status() -> None:
    service.set_programme_status(
        _ask_int("Programme ID"), _ask("Status (active/suspended/teach_out/closed)"),
        actor_id=_actor(), reason=_ask("Reason"))
    print("Programme status updated.")


def _assign_student() -> None:
    assignment_id = service.assign_student(
        _ask("Student ID"), _ask_int("Programme ID"), _ask_int("Approved version ID"),
        assigned_by=_actor(), reason=_ask("Reason", "Regulation assignment"))
    print(f"Assignment #{assignment_id} recorded.")


def _student_regulations() -> None:
    programme = _ask("Programme ID (blank for any)")
    record = service.regulation_for_student(
        _ask("Student ID"), int(programme) if programme else None)
    if record is None:
        print(_t("no_assignment", "No active regulation assignment."))
        return
    print(f"\n{record['programme_code']} v{record['version_number']} "
          f"({record['effective_academic_year']}) hash={record['snapshot_hash']}")
    print(json.dumps(record["regulations"], indent=2))


_ACTIONS: dict[str, tuple[str, Callable[[], None]]] = {
    "1": ("List programmes", _list_programmes),
    "2": ("Show programme", _show_programme),
    "3": ("Create proposal", _create_proposal),
    "4": ("Record business case", _record_business_case),
    "5": ("Approve business case", _approve_business_case),
    "6": ("Create draft version", _create_version),
    "7": ("Amend draft", _amend_draft),
    "8": ("Propose amendment", _propose_amendment),
    "9": ("List committees", _list_committees),
    "10": ("Create committee", _create_committee),
    "11": ("Validate version", _validate_version),
    "12": ("Approve version", _approve_version),
    "13": ("Record accreditation", _record_accreditation),
    "14": ("Create teach-out plan", _create_teach_out),
    "15": ("Set programme status", _set_status),
    "16": ("Assign student regulations", _assign_student),
    "17": ("Student regulation lookup", _student_regulations),
}


def display_programme_governance_menu() -> None:
    """Top-level programme governance menu."""
    if not _require_staff():
        return
    while True:
        print(f"\n{_t('title', 'Programme Governance')}")
        print("=" * 30)
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
