"""Referrals to Alternative Provision - the school's text menu (see ``ap_referrals``).

Used by the Primary and Secondary CLIs: list the school's referrals and,
for staff allowed to, refer a pupil.
"""

from __future__ import annotations

from collections.abc import Callable

from education_system.platform.cross_system import ap_referrals as service

TITLE = "Referrals to Alternative Provision"


def _yes(prompt: str) -> bool:
    return input(f"  {prompt} [y/N]: ").strip().lower() == "y"


def _pick(title: str, options: list[str]) -> int | None:
    print(f"  {title}:")
    for n, text in enumerate(options, 1):
        print(f"    {n}) {text}")
    got = input("  Choose: ").strip()
    return int(got) - 1 if got.isdigit() and 0 < int(got) <= len(options) else None


def show(school: str) -> list[dict]:
    rows = service.referrals_from(school)
    print(f"\n  {TITLE}")
    print("  " + "-" * 92)
    for n, row in enumerate(rows, 1):
        note = row.get("decision_reason") or row.get("cancelled_reason") or ""
        print(f"  {n:>2}. {row.get('pupil') or '':<26} {row['label']:<30} "
              f"{(row.get('reason') or '')[:30]:<30} {note[:30]}")
    if not rows:
        print("  No referrals yet.")
    return rows


def refer(school: str, pupils: Callable[[], list[tuple[str, str]]], *,
          referrer: str = "", actor_user_id: int | None = None) -> None:
    options = list(pupils())
    if not options:
        print("  There are no pupils on roll to refer.")
        return
    term = input("  Pupil (part of the name, Enter for all): ").strip().lower()
    matches = [o for o in options if term in o[1].lower()][:30]
    if not matches:
        print("  No pupil matches.")
        return
    i = _pick("Pupil", [label for _id, label in matches])
    if i is None:
        return
    r = _pick("Reason", list(service.REASONS))
    if r is None:
        return
    reason = service.REASONS[r]
    if reason == service.REASONS[0]:
        reg = service.SOLE
        print("  Permanent exclusion: sole registration.")
    else:
        reg = service.SOLE if _yes("Sole registration (the pupil comes off this school's "
                                   "roll)?") else service.DUAL
    excluded = None
    if reason in service.EXCLUSION_REASONS:
        excluded = input("  First day of the exclusion (YYYY-MM-DD): ").strip() or None
    summary = input("  Background: ").strip()
    who = input(f"  Referred by [{referrer}]: ").strip() or referrer
    consent = _yes("The parent consents to sharing SEN, medical, behaviour and exclusion "
                   "details?")
    sg = input("  Safeguarding file reference (a reference only, optional): ").strip() or None
    try:
        row = service.refer(school, str(matches[i][0]), reason=reason, registration=reg,
                            excluded_from=excluded, summary=summary, referrer=who,
                            consent=consent, safeguarding_reference=sg,
                            actor_user_id=actor_user_id)
    except Exception as exc:  # noqa: BLE001 - shown to the user
        print(f"  Not referred: {exc}")
        return
    print(f"  Referred. Status: {service.STATUS_LABELS.get(row['status'], row['status'])}. "
          "The AP has it on its Referrals page.")


def menu(school: str, pupils: Callable[[], list[tuple[str, str]]], *,
         can_refer: bool = False, referrer: str = "",
         actor_user_id: int | None = None) -> None:
    while True:
        try:
            show(school)
        except Exception as exc:  # noqa: BLE001
            print(f"  The platform's referral queue can't be read: {exc}")
            return
        print("\n  R) Refer a pupil" if can_refer else "")
        choice = input("  Choose (Enter to go back): ").strip().lower()
        if choice == "r" and can_refer:
            refer(school, pupils, referrer=referrer, actor_user_id=actor_user_id)
        else:
            return


__all__ = ["TITLE", "show", "refer", "menu"]
