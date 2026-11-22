"""Console menu for academic appeals (``application.cases.appeals``).

Students see and act on their own appeals (submit, review request, withdraw,
save the Completion of Procedures letter); appeals staff run the procedure.
Reached from Case Management (staff) and as "Academic Appeals" in the main
menu (everyone signed in).
"""
from __future__ import annotations

from typing import Any, Callable

from education_system.systems.university.application.cases import appeals
from education_system.systems.university.infrastructure.i18n import get_text

auth: Any = None


def set_auth(auth_object: Any) -> None:
    global auth
    auth = auth_object


def _t(key: str, default: str) -> str:
    return get_text(f"cli.appeals.{key}", default=default)


def _who() -> appeals.Who | None:
    user = getattr(auth, "current_user", None) if auth else None
    return appeals.who_from_user(user) if user else None


def _ask(prompt: str, default: str = "") -> str:
    value = input(f"{prompt}{f' [{default}]' if default else ''}: ").strip()
    return value or default


def _ask_int(prompt: str) -> int:
    return int(_ask(prompt))


def _optional_int(prompt: str) -> int | None:
    raw = _ask(prompt + " (blank for none)")
    return int(raw) if raw else None


def _lines(prompt: str) -> list[str]:
    print(f"{prompt} (one per line, blank line to finish):")
    out = []
    while True:
        line = input("  ").strip()
        if not line:
            return out
        out.append(line)


def _list(who: appeals.Who) -> None:
    stage = _ask("Stage (blank for all)") or None
    rows = appeals.list_appeals(who, stage=stage)
    if not rows:
        print(_t("none", "No appeals."))
        return
    print(f"\n{'ID':<6} {'Student':<10} {'Stage':<14} {'Grounds':<26} {'Module':<10} "
          f"{'Due':<11} {'Outcome':<14}")
    print("-" * 96)
    for r in rows:
        print(f"{r['appeal_id']:<6} {r['student_id']:<10} {r['stage']:<14} {r['grounds']:<26} "
              f"{(r['module_code'] or '-'):<10} {(r['stage_due'] or '-'):<11} "
              f"{(r['outcome'] or '-'):<14}{'  OVERDUE' if r['overdue'] else ''}")
    print(f"\nTotal: {len(rows)}")


def _view(who: appeals.Who) -> None:
    record = appeals.detail(who, _ask_int("Appeal ID"))
    print(f"\n{record['reference']} [{record['stage']}] due {record['stage_due'] or '-'}")
    for key in ("student_id", "grounds", "module_code", "assessment_name", "board_id",
                "handler", "eligibility_decision", "eligibility_reason", "outcome",
                "outcome_rationale", "final_decision_date", "review_outcome", "cop_issued_at",
                "cop_path"):
        if record.get(key) not in (None, ""):
            print(f"  {key.replace('_', ' '):<22} {record[key]}")
    print(f"\n  Statement: {record['statement']}")
    for issue in record["issues_considered"]:
        print(f"   - {issue}")
    for action in record["actions"]:
        print(f"  Action #{action['action_id']} {action['action_type']} [{action['status']}] "
              f"{action['result'] or ''}")
    state = record.get("board_state") or {}
    if state.get("award"):
        award = state["award"]
        print(f"  Current award: {award['award_name']} {award['classification'] or ''} "
              f"[{award['status']}]")


def _submit(who: appeals.Who) -> None:
    student_id = _ask("Student ID") if who.is_staff else who.student_id
    keys = list(appeals.GROUNDS)
    for i, key in enumerate(keys, 1):
        print(f"  {i}. {appeals.GROUNDS[key]}")
    grounds = keys[_ask_int("Grounds") - 1]
    appeal_id = appeals.submit(
        who, student_id, grounds, _ask("What happened and why the decision should change"),
        module_code=_ask("Module code (blank if a board decision)") or None,
        assessment_name=_ask("Assessment (optional)") or None,
        board_id=_optional_int("Board ID"),
        results_released_on=_ask("Results released on (YYYY-MM-DD, blank if unknown)") or None,
        late_reason=_ask("Reason if late (blank if not)") or None)
    print(f"Appeal APL-{appeal_id:05d} submitted.")


def _assign(who):
    appeals.assign(who, _ask_int("Appeal ID"), _ask("Handler username"))
    print("Handler assigned.")


def _start(who):
    appeals.start_eligibility(who, _ask_int("Appeal ID"))
    print("Eligibility check started.")


def _eligibility(who):
    appeal_id = _ask_int("Appeal ID")
    eligible = _ask("Eligible? (y/n)", "y").lower().startswith("y")
    appeals.decide_eligibility(who, appeal_id, eligible, _ask("Reason"))
    print("Eligibility decided.")


def _outcome(who):
    appeal_id = _ask_int("Appeal ID")
    outcome = _ask("Outcome (upheld/partly_upheld/not_upheld)")
    rationale = _ask("Reasons")
    issues = _lines("Issues considered")
    actions = []
    if outcome in appeals.UPHELD:
        if _ask("Re-mark the module result? (y/n)", "n").lower().startswith("y"):
            actions.append({"type": "remark", "assigned_to": _ask("Re-marker username")})
        if _ask("Grant an uncapped resit? (y/n)", "n").lower().startswith("y"):
            actions.append({"type": "uncapped_resit"})
        if _ask("Reconvene the assessment board? (y/n)", "n").lower().startswith("y"):
            actions.append({"type": "board_reconvene",
                            "approved_by": _ask("Independent approver (must differ from you)")})
    result = appeals.record_outcome(who, appeal_id, outcome, rationale, issues, actions)
    print(f"Outcome recorded; action(s) {result['actions'] or 'none'}.")


def _complete_action(who):
    appeals.complete_action(who, _ask_int("Action ID"), _ask("What it produced"))
    print("Action completed.")


def _retry(who):
    print(f"Board reconvene: {appeals.retry_action(who, _ask_int('Action ID'))['status']}")


def _review(who):
    appeals.request_review(who, _ask_int("Appeal ID"), _ask("Why should it be reviewed"))
    print("Review requested.")


def _decide_review(who):
    appeal_id = _ask_int("Appeal ID")
    appeals.decide_review(who, appeal_id, _ask("Review outcome (" + "/".join(
        appeals.REVIEW_OUTCOMES) + ")"), _ask("Reasons"))
    print("Review decided.")


def _close(who):
    result = appeals.close(who, _ask_int("Appeal ID"))
    print(f"Closed. Completion of Procedures letter: {result['path']}\n"
          f"OIA deadline: {result['oia_deadline']}")


def _withdraw(who):
    appeals.withdraw(who, _ask_int("Appeal ID"), _ask("Reason"))
    print("Appeal withdrawn.")


def _save_letter(who):
    appeal_id = _ask_int("Appeal ID")
    path = _ask("Save as", f"COP-APL-{appeal_id:05d}.pdf")
    with open(path, "wb") as handle:
        handle.write(appeals.cop_letter_pdf(who, appeal_id))
    print(f"Saved {path}")


def _reminders(who):
    print(f"Reminders sent for {appeals.send_reminders(who)} overdue appeal(s).")


def _statistics(who):
    stats = appeals.statistics(who, _ask("From (YYYY-MM-DD, blank for all)") or None,
                               _ask("To (YYYY-MM-DD, blank for all)") or None)
    print("\n" + appeals.statistics_text(stats))
    path = _ask("Save as CSV (blank to skip)")
    if path:
        with open(path, "w", encoding="utf-8", newline="") as handle:
            handle.write(appeals.statistics_csv(stats))
        print(f"Saved {path}")


_STUDENT: dict[str, tuple[str, Callable]] = {
    "1": ("My appeals", _list), "2": ("View appeal", _view), "3": ("Submit an appeal", _submit),
    "4": ("Request a review", _review), "5": ("Withdraw an appeal", _withdraw),
    "6": ("Save Completion of Procedures letter", _save_letter),
}
_STAFF: dict[str, tuple[str, Callable]] = {
    "1": ("List appeals", _list), "2": ("View appeal", _view), "3": ("Submit for a student", _submit),
    "4": ("Assign handler", _assign), "5": ("Start eligibility check", _start),
    "6": ("Decide eligibility", _eligibility), "7": ("Record outcome + actions", _outcome),
    "8": ("Complete an action", _complete_action), "9": ("Retry board reconvene", _retry),
    "10": ("Record review request", _review), "11": ("Decide review", _decide_review),
    "12": ("Close + Completion of Procedures letter", _close), "13": ("Withdraw", _withdraw),
    "14": ("Save Completion of Procedures letter", _save_letter),
    "15": ("Send overdue reminders", _reminders), "16": ("OIA case statistics", _statistics),
}


def display_appeals_menu() -> None:
    """Academic appeals: the student's own, or the staff procedure."""
    who = _who()
    if who is None:
        print(_t("login_required", "You must be logged in to use academic appeals."))
        return
    if not (who.is_staff or who.is_student):
        print(_t("not_allowed", "Academic appeals are for students and appeals staff."))
        return
    actions = _STAFF if who.is_staff else _STUDENT
    while True:
        print("\n" + _t("title", "Academic Appeals"))
        print("=" * 30)
        for key, (label, _) in actions.items():
            print(f"{key}. {label}")
        print("0. " + get_text("cli.menu.return", default="Return to Previous Menu"))
        choice = input("\nEnter your choice: ").strip()
        if choice == "0":
            return
        action = actions.get(choice)
        if not action:
            print(get_text("cli.invalid_choice", default="Invalid choice."))
            continue
        try:
            action[1](who)
        except KeyboardInterrupt:
            print("\nCancelled.")
        except (ValueError, PermissionError, IndexError) as exc:
            print(f"Error: {exc}")
