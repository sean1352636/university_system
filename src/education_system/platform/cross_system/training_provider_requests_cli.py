"""Training Provider Requests - the sender's text menu (see
``training_provider_requests``)."""

from __future__ import annotations

from collections.abc import Callable

from education_system.platform.cross_system import training_provider_requests as service

TITLE = "Training Provider Requests"


def _yes(prompt: str) -> bool:
    return input(f"  {prompt} [y/N]: ").strip().lower() == "y"


def _pick(title: str, options: list[str]) -> int | None:
    print(f"  {title}:")
    for n, text in enumerate(options, 1):
        print(f"    {n}) {text}")
    got = input("  Choose: ").strip()
    return int(got) - 1 if got.isdigit() and 0 < int(got) <= len(options) else None


def show(source_system: str) -> list[dict]:
    rows = service.requests_from(source_system)
    print(f"\n  {TITLE}")
    print("  " + "-" * 96)
    for n, row in enumerate(rows, 1):
        latest = row.get("latest") or row.get("decision_reason") or ""
        print(f"  {n:>2}. {row.get('learner') or '':<22} {(row.get('course') or '')[:22]:<22} "
              f"{row['label']:<26} {latest[:34]}")
    if not rows:
        print("  No requests yet.")
    return rows


def outcomes(rows: list[dict]) -> None:
    got = input("  Request number: ").strip()
    if not (got.isdigit() and 0 < int(got) <= len(rows)):
        return
    notes = service.outcomes_for(rows[int(got) - 1]["transition_id"])
    if not notes:
        print("  No outcome from the training provider yet.")
    for n in notes:
        print(f"  {(n.get('at') or '')[:10]}  "
              f"{n['note'].removeprefix('Training provider: ')}")


def new_request(source_system: str, learners: Callable[[], list[tuple[str, str]]], *,
                referrer: str = "", actor_user_id: int | None = None) -> None:
    options = list(learners())
    if not options:
        print("  There are no learners to send.")
        return
    term = input("  Learner (part of the name, Enter for all): ").strip().lower()
    matches = [o for o in options if term in o[1].lower()][:30]
    if not matches:
        print("  No learner matches.")
        return
    i = _pick("Learner", [label for _id, label in matches])
    if i is None:
        return
    course = input("  Course: ").strip()
    reason = input("  Why: ").strip()
    needed = input("  Needed by (YYYY-MM-DD, optional): ").strip() or None
    k = _pick("Who pays", list(service.PAYERS))
    if k is None:
        return
    po = input("  Purchase order number (optional): ").strip()
    who = input(f"  Requested by [{referrer}]: ").strip() or referrer
    consent = _yes("The learner consents to sharing their support needs?")
    sg = input("  Safeguarding file reference (a reference only, optional): ").strip() or None
    try:
        row = service.request(source_system, str(matches[i][0]), course=course,
                              reason=reason, needed_by=needed, payer=service.PAYERS[k],
                              po_number=po, referrer=who, consent=consent,
                              safeguarding_reference=sg, actor_user_id=actor_user_id)
    except Exception as exc:  # noqa: BLE001 - shown to the user
        print(f"  Not sent: {exc}")
        return
    print(f"  Sent. Status: {service.STATUS_LABELS.get(row['status'], row['status'])}. "
          "The training provider has it on its Training Requests page.")


def menu(source_system: str, learners: Callable[[], list[tuple[str, str]]], *,
         can_request: bool = True, referrer: str = "",
         actor_user_id: int | None = None) -> None:
    while True:
        try:
            rows = show(source_system)
        except Exception as exc:  # noqa: BLE001
            print(f"  The platform's requests can't be read: {exc}")
            return
        print("\n  O) Outcomes on a request" + ("\n  N) New request" if can_request else ""))
        choice = input("  Choose (Enter to go back): ").strip().lower()
        if choice == "o":
            outcomes(rows)
        elif choice == "n" and can_request:
            new_request(source_system, learners, referrer=referrer,
                        actor_user_id=actor_user_id)
        else:
            return


__all__ = ["TITLE", "show", "outcomes", "new_request", "menu"]
