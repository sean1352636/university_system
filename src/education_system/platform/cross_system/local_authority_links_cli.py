"""Local Authority - the school's text menu (see ``local_authority_links``).

Used by the Primary and Secondary CLIs: list the school's notifications with
the authority's latest update, show one notification's updates, list the
school places the authority has allocated here and, for the head or
admissions office, send a new notification.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date

from education_system.platform.cross_system import local_authority_links as service

TITLE = "Local Authority"
_PREFIX = f"{service.LABEL}: "


def _yes(prompt: str) -> bool:
    return input(f"  {prompt} [y/N]: ").strip().lower() == "y"


def _pick(title: str, options: list[str]) -> int | None:
    print(f"  {title}:")
    for n, text in enumerate(options, 1):
        print(f"    {n}) {text}")
    got = input("  Choose: ").strip()
    return int(got) - 1 if got.isdigit() and 0 < int(got) <= len(options) else None


def show(school: str) -> list[dict]:
    rows = service.notifications_from(school)
    print(f"\n  {TITLE} - notifications")
    print("  " + "-" * 96)
    for n, row in enumerate(rows, 1):
        print(f"  {n:>2}. {row.get('pupil') or '':<24} {(row.get('reason') or '')[:28]:<28} "
              f"{row['label']:<12} {(row.get('latest') or '')[:40]}")
    if not rows:
        print("  No notifications yet.")
    return rows


def show_places(school: str) -> None:
    rows = service.places_for(school)
    print(f"\n  {TITLE} - school places allocated here")
    print("  " + "-" * 96)
    for row in rows:
        place = row.get("place") or {}
        print(f"  {row.get('pupil') or '':<24} {(place.get('round') or '')[:24]:<24} "
              f"{(place.get('basis') or '')[:24]:<24} {place.get('start_date') or '':<11} "
              f"{row['label']}")
    if not rows:
        print("  No places from the local authority.")
    else:
        print("  " + ("Enrol each one on Admissions when the child starts."
                      if school == "primary" else
                      "Match or create each pupil under Incoming pupils."))


def updates(rows: list[dict]) -> None:
    got = input("  Notification number: ").strip()
    if not (got.isdigit() and 0 < int(got) <= len(rows)):
        return
    notes = service.updates_for(rows[int(got) - 1]["transition_id"])
    if not notes:
        print("  No updates from the local authority yet.")
    for n in notes:
        print(f"  {(n.get('at') or '')[:10]}  {(n.get('note') or '').removeprefix(_PREFIX)}")


def new_notification(school: str, pupils: Callable[[], list[tuple[str, str]]], *,
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
    k = _pick("Notification", list(service.KINDS))
    if k is None:
        return
    kind = service.KINDS[k]
    details: dict[str, str] = {}
    for key, label, how, choices in service.NOTICE_FIELDS[kind]:
        if how == "choice":
            c = _pick(label, list(choices))
            details[key] = choices[c] if c is not None else ""
            continue
        default = date.today().isoformat() if key in ("start_date", "notice_date") else ""
        got = input(f"  {label}" + (f" [{default}]" if default else "") + ": ").strip()
        details[key] = got or default
    who = input(f"  Sent by [{referrer}]: ").strip() or referrer
    consent = _yes("The parent consents to sharing SEN, medical and exclusion history?")
    sg = input("  Safeguarding file reference (a reference only, optional): ").strip() or None
    try:
        row = service.notify(school, str(matches[i][0]), kind=kind, details=details,
                             referrer=who, consent=consent, safeguarding_reference=sg,
                             actor_user_id=actor_user_id)
    except Exception as exc:  # noqa: BLE001 - shown to the user
        print(f"  Not sent: {exc}")
        return
    print(f"  Sent. Status: {service.NOTICE_LABELS.get(row['status'], row['status'])}.")


def menu(school: str, pupils: Callable[[], list[tuple[str, str]]], *,
         can_notify: bool = False, referrer: str = "",
         actor_user_id: int | None = None) -> None:
    while True:
        try:
            rows = show(school)
        except Exception as exc:  # noqa: BLE001
            print(f"  The platform can't be read: {exc}")
            return
        print("\n  U) Updates on a notification\n  P) School places allocated here"
              + ("\n  N) New notification" if can_notify else ""))
        choice = input("  Choose (Enter to go back): ").strip().lower()
        if choice == "u":
            updates(rows)
        elif choice == "p":
            try:
                show_places(school)
            except Exception as exc:  # noqa: BLE001
                print(f"  The platform can't be read: {exc}")
        elif choice == "n" and can_notify:
            new_notification(school, pupils, referrer=referrer, actor_user_id=actor_user_id)
        else:
            return


__all__ = ["TITLE", "show", "show_places", "updates", "new_notification", "menu"]
