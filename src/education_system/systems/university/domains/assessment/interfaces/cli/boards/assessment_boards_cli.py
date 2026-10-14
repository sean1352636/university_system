"""Console menu for assessment boards - mirrors room_booking_cli."""
from __future__ import annotations

from typing import Any, Callable

from education_system.systems.university.domains.assessment.domain.boards import service
from education_system.systems.university.infrastructure.i18n import get_text

auth: Any = None
_PREFIX = "cli.assessment.boards"


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
        print(_t("login_required", "You must be logged in to access assessment boards."))
        return False
    if str(user.get("role", "")).lower() not in ("admin", "staff"):
        print(_t("staff_only", "Assessment boards are restricted to staff."))
        return False
    return True


def _ask(prompt: str, default: str = "") -> str:
    value = input(f"{prompt}{f' [{default}]' if default else ''}: ").strip()
    return value or default


def _ask_int(prompt: str) -> int:
    return int(_ask(prompt))


def _ask_float(prompt: str) -> float | None:
    raw = _ask(prompt + " (blank for none)")
    return float(raw) if raw else None


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

def _list_boards() -> None:
    year = _ask("Academic year (blank for all)")
    _print_table(service.list_boards(year or None),
                 [("board_id", 6), ("board_type", 18), ("name", 30), ("academic_year", 8),
                  ("programme_code", 10), ("status", 14), ("version", 4)])


def _show_board() -> None:
    board = service.get_board(_ask_int("Board ID"))
    print(f"\n#{board['board_id']} {board['name']} ({board['board_type']}, "
          f"{board['academic_year']}) [{board['status']}] v{board['version']} "
          f"chair={board['chair_id'] or '-'}")
    print("\nMembers:")
    _print_table(board["members"], [("member_id", 14), ("role", 14)])
    print("\nRules:")
    _print_table(board["rules"], [("rule_id", 6), ("rule_type", 12), ("minimum_mark", 8),
                                  ("maximum_credits", 8), ("active", 6), ("notes", 30)])
    print("\nAgenda:")
    _print_table(board["agenda"], [("student_id", 10), ("programme_code", 10),
                                   ("current_level", 6), ("credits", 7), ("average_mark", 8),
                                   ("proposed_classification", 16), ("status", 8)])
    print("\nDecisions:")
    _print_table(board["decisions"], [("decision_id", 6), ("student_id", 10),
                                      ("module_code", 10), ("decision_type", 10),
                                      ("confirmed_result", 8), ("classification", 14),
                                      ("decided_by", 10)])
    minutes = board["minutes"]
    print("\nMinutes:", "none" if minutes is None else
          f"{'locked' if minutes['locked'] else 'editable'} - {minutes['minutes_text'][:200]}")
    print("\nRatified awards:")
    _print_table(board["awards"], [("award_id", 6), ("student_id", 10), ("award_name", 20),
                                   ("classification", 14), ("status", 16),
                                   ("release_authorised", 8)])


def _create_board() -> None:
    board_id = service.create_board(
        _ask("Board type (module/progression_award)", "progression_award"),
        _ask("Board name"), _ask("Academic year", "2026/27"), created_by=_actor(),
        programme_code=_ask("Programme code (blank for all)") or None,
        module_code=_ask("Module code (blank for all)") or None,
        meeting_at=_ask("Meeting at (YYYY-MM-DD HH:MM)") or None,
        chair_id=_ask("Chair ID") or None)
    print(f"Board #{board_id} created.")


def _add_member() -> None:
    service.add_member(_ask_int("Board ID"), _ask("Member ID"), _ask("Role", "member"))
    print("Member added.")


def _add_rule() -> None:
    rule_id = service.add_rule(
        _ask_int("Board ID"), _ask("Rule type (compensation/condonation)", "compensation"),
        minimum_mark=_ask_float("Minimum mark"), maximum_credits=_ask_float("Maximum credits"),
        exclude_core_modules=_ask("Exclude core modules? (y/n)", "y").lower().startswith("y"),
        notes=_ask("Notes"))
    print(f"Rule #{rule_id} added.")


def _generate_agenda() -> None:
    count = service.generate_agenda(_ask_int("Board ID"))
    print(f"Agenda generated with {count} student(s).")


def _lock_agenda() -> None:
    service.lock_agenda(_ask_int("Board ID"), actor_id=_actor())
    print("Agenda locked.")


def _record_decision() -> None:
    supersedes = _ask("Supersedes decision ID (blank for none)")
    decision_id = service.record_decision(
        _ask_int("Board ID"), _ask("Student ID"),
        _ask("Decision (" + "/".join(sorted(service.DECISIONS)) + ")"),
        decided_by=_actor(), rationale=_ask("Rationale"),
        module_code=_ask("Module code") or None,
        original_result=_ask("Original result") or None,
        confirmed_result=_ask("Confirmed result") or None,
        credits_affected=_ask_float("Credits affected"),
        classification=_ask("Classification (award decisions)") or None,
        supersedes_decision_id=int(supersedes) if supersedes else None)
    print(f"Decision #{decision_id} recorded.")


def _save_minutes() -> None:
    service.save_minutes(_ask_int("Board ID"), _ask("Minutes text"), actor_id=_actor())
    print("Minutes saved.")


def _chair_approve() -> None:
    service.chair_approve(_ask_int("Board ID"), chair_id=_ask("Chair ID", _actor()))
    print("Board chair-approved; minutes locked.")


def _ratify() -> None:
    count = service.ratify(_ask_int("Board ID"), ratified_by=_actor(),
                           award_name=_ask("Award name", "University Award"))
    print(f"Board ratified; {count} award(s) released.")


def _reopen() -> None:
    decision = _ask("Decision ID under correction (blank for none)")
    correction_id = service.reopen(
        _ask_int("Board ID"), requested_by=_ask("Requested by", _actor()),
        approved_by=_ask("Approved by (must differ)"), reason=_ask("Reason"),
        decision_id=int(decision) if decision else None)
    print(f"Board reopened; correction #{correction_id} logged.")


def _releasable_award() -> None:
    award = service.releasable_award(_ask("Student ID"))
    if award is None:
        print(_t("no_award", "No releasable award."))
        return
    print(f"\n{award['award_name']} - {award['classification']} ({award['programme_code']}, "
          f"{award['academic_year']}) ratified {award['ratified_at']} by {award['ratified_by']}")


_ACTIONS: dict[str, tuple[str, Callable[[], None]]] = {
    "1": ("List boards", _list_boards),
    "2": ("Show board", _show_board),
    "3": ("Create board", _create_board),
    "4": ("Add member", _add_member),
    "5": ("Add compensation/condonation rule", _add_rule),
    "6": ("Generate agenda", _generate_agenda),
    "7": ("Lock agenda", _lock_agenda),
    "8": ("Record decision", _record_decision),
    "9": ("Save minutes", _save_minutes),
    "10": ("Chair approve", _chair_approve),
    "11": ("Ratify", _ratify),
    "12": ("Reopen board", _reopen),
    "13": ("Releasable award lookup", _releasable_award),
}


def display_assessment_boards_menu() -> None:
    """Top-level assessment boards menu."""
    if not _require_staff():
        return
    while True:
        print(f"\n{_t('title', 'Assessment Boards')}")
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
        except ValueError as exc:
            print(f"Error: {exc}")
