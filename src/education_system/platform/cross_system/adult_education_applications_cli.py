"""Referrals to Adult Education - the FE college's text menu (see
``adult_education_applications``)."""

from __future__ import annotations

from collections.abc import Callable

from education_system.platform.cross_system import adult_education_applications as service

TITLE = "Referrals to Adult Education"


def _yes(prompt: str) -> bool:
    return input(f"  {prompt} [y/N]: ").strip().lower() == "y"


def _pick(title: str, options: list[str]) -> int | None:
    print(f"  {title}:")
    for n, text in enumerate(options, 1):
        print(f"    {n}) {text}")
    got = input("  Choose: ").strip()
    return int(got) - 1 if got.isdigit() and 0 < int(got) <= len(options) else None


def show(source_system: str) -> list[dict]:
    rows = service.referrals_from(source_system)
    print(f"\n  {TITLE}")
    print("  " + "-" * 96)
    for n, row in enumerate(rows, 1):
        why = row.get("decision_reason") or row.get("reason") or ""
        print(f"  {n:>2}. {row.get('learner') or '':<24} {(row.get('course') or '')[:24]:<24} "
              f"{row['label']:<22} {why[:30]}")
    if not rows:
        print("  No referrals yet.")
    return rows


def new_referral(source_system: str, learners: Callable[[], list[tuple[str, str]]], *,
                 referrer: str = "", actor_user_id: int | None = None) -> None:
    options = list(learners())
    if not options:
        print("  There are no learners to refer.")
        return
    term = input("  Learner (part of the name, Enter for all): ").strip().lower()
    matches = [o for o in options if term in o[1].lower()][:30]
    if not matches:
        print("  No learner matches.")
        return
    i = _pick("Learner", [label for _id, label in matches])
    if i is None:
        return
    course = input("  Course or subject: ").strip()
    reason = input("  Reason: ").strip()
    start = input("  Intended start (YYYY-MM-DD, optional): ").strip() or None
    who = input(f"  Referred by [{referrer}]: ").strip() or referrer
    consent = _yes("The learner consents to sharing their support needs?")
    sg = input("  Safeguarding file reference (a reference only, optional): ").strip() or None
    try:
        row = service.refer(source_system, str(matches[i][0]), course=course, reason=reason,
                            intended_start=start, referrer=who, consent=consent,
                            safeguarding_reference=sg, actor_user_id=actor_user_id)
    except Exception as exc:  # noqa: BLE001 - shown to the user
        print(f"  Not referred: {exc}")
        return
    print(f"  Referred. Status: {service.STATUS_LABELS.get(row['status'], row['status'])}. "
          "Adult Education has it on its Referrals from FE College page.")


def menu(source_system: str, learners: Callable[[], list[tuple[str, str]]], *,
         can_refer: bool = True, referrer: str = "",
         actor_user_id: int | None = None) -> None:
    while True:
        try:
            show(source_system)
        except Exception as exc:  # noqa: BLE001
            print(f"  The platform's referrals can't be read: {exc}")
            return
        if not can_refer:
            input("  Enter to go back: ")
            return
        choice = input("\n  N) New referral\n  Choose (Enter to go back): ").strip().lower()
        if choice == "n":
            new_referral(source_system, learners, referrer=referrer,
                         actor_user_id=actor_user_id)
        else:
            return


__all__ = ["TITLE", "show", "new_referral", "menu"]
