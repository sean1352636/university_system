"""SEND Service Requests - the school's text menu (see ``send_referrals``).

Used by the Primary and Secondary CLIs: list the school's requests with the
SEND service's latest decision, show one request's updates and, for the
SENCO, send a new request.
"""

from __future__ import annotations

from collections.abc import Callable

from education_system.platform.cross_system import send_referrals as service

TITLE = "SEND Service Requests"


def _yes(prompt: str) -> bool:
    return input(f"  {prompt} [y/N]: ").strip().lower() == "y"


def _pick(title: str, options: list[str]) -> int | None:
    print(f"  {title}:")
    for n, text in enumerate(options, 1):
        print(f"    {n}) {text}")
    got = input("  Choose: ").strip()
    return int(got) - 1 if got.isdigit() and 0 < int(got) <= len(options) else None


def show(school: str) -> list[dict]:
    rows = service.requests_from(school)
    print(f"\n  {TITLE}")
    print("  " + "-" * 96)
    for n, row in enumerate(rows, 1):
        print(f"  {n:>2}. {row.get('pupil') or '':<24} {(row.get('reason') or '')[:28]:<28} "
              f"{row['label']:<12} {(row.get('latest') or '')[:40]}")
    if not rows:
        print("  No requests yet.")
    return rows


def updates(rows: list[dict]) -> None:
    got = input("  Request number: ").strip()
    if not (got.isdigit() and 0 < int(got) <= len(rows)):
        return
    notes = service.updates_for(rows[int(got) - 1]["transition_id"])
    if not notes:
        print("  No updates from the SEND service yet.")
    for n in notes:
        print(f"  {(n.get('at') or '')[:10]}  "
              f"{(n.get('note') or '').removeprefix('SEND service: ')}")


def new_request(school: str, pupils: Callable[[], list[tuple[str, str]]], *,
                referrer: str = "", actor_user_id: int | None = None) -> None:
    options = list(pupils())
    if not options:
        print("  There are no pupils on roll.")
        return
    term = input("  Pupil (part of the name, Enter for all): ").strip().lower()
    matches = [o for o in options if term in o[1].lower()][:30]
    if not matches:
        print("  No pupil matches.")
        return
    i = _pick("Pupil", [label for _id, label in matches])
    if i is None:
        return
    k = _pick("Request", list(service.REQUESTS))
    if k is None:
        return
    when = input("  Date (YYYY-MM-DD, Enter for today): ").strip() or None
    summary = input("  Why: ").strip()
    tried = input("  What the school has tried: ").strip()
    who = input(f"  Requested by [{referrer}]: ").strip() or referrer
    consent = _yes("The parent consents to sharing SEN, medical and support details?")
    sg = input("  Safeguarding file reference (a reference only, optional): ").strip() or None
    try:
        row = service.refer(school, str(matches[i][0]), request=service.REQUESTS[k],
                            summary=summary, tried=tried, referrer=who,
                            request_date=when, consent=consent,
                            safeguarding_reference=sg, actor_user_id=actor_user_id)
    except Exception as exc:  # noqa: BLE001 - shown to the user
        print(f"  Not sent: {exc}")
        return
    print(f"  Sent. Status: {service.STATUS_LABELS.get(row['status'], row['status'])}. "
          "The SEND service has it on its School Requests page.")


def menu(school: str, pupils: Callable[[], list[tuple[str, str]]], *,
         can_request: bool = False, referrer: str = "",
         actor_user_id: int | None = None) -> None:
    while True:
        try:
            rows = show(school)
        except Exception as exc:  # noqa: BLE001
            print(f"  The platform's requests can't be read: {exc}")
            return
        print("\n  U) Updates on a request" + ("\n  N) New request" if can_request else ""))
        choice = input("  Choose (Enter to go back): ").strip().lower()
        if choice == "u":
            updates(rows)
        elif choice == "n" and can_request:
            new_request(school, pupils, referrer=referrer, actor_user_id=actor_user_id)
        else:
            return


__all__ = ["TITLE", "show", "updates", "new_request", "menu"]
