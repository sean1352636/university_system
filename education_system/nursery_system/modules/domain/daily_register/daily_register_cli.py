"""CLI flow for the Daily Register (Nursery System).

Shows the per-date register over every active child (reusing the
``attendance_report`` domain via ``daily_register``): print the day's register
and summary, mark a child, or mark all unmarked children present.
"""

from __future__ import annotations

import logging

from education_system.nursery_system.modules.domain.daily_register import (
    daily_register as data,
)

logger = logging.getLogger(__name__)


def _pause() -> None:
    try:
        input("\n  Press Enter to continue...")
    except (EOFError, KeyboardInterrupt):
        pass


def _ask(prompt: str, default: str = "") -> str | None:
    try:
        raw = input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        return None
    return raw or default


def _print_register(when: str) -> list[dict]:
    rows = data.register_for_date(when)
    print(f"\n═══ Daily Register  {when} ═══")
    print(f"  {'#':>3}  {'Child':<24} {'Room':<14} {'Status':<10}")
    print("  " + "-" * 54)
    for idx, r in enumerate(rows, start=1):
        status = r["status"] or "not marked"
        print(f"  {idx:>3}  {r['name'][:24]:<24} "
              f"{(r['room'] or '-')[:14]:<14} {status:<10}")
    s = data.day_summary(when)
    print("\n  " + "   ".join(
        f"{k}: {s[k]}" for k in
        (*data.STATUSES, "not_marked", "total")))
    return rows


def _mark_child(when: str, rows: list[dict]) -> None:
    if not rows:
        print("  No active children on roll.")
        return
    raw = _ask("\n  Child number to mark: ", "")
    if not raw:
        return
    try:
        idx = int(raw)
    except ValueError:
        print("  ✗ Enter a child number from the list.")
        return
    if not 1 <= idx <= len(rows):
        print("  ✗ Enter a child number from the list.")
        return
    child = rows[idx - 1]
    print("  Status: " + ", ".join(
        f"{i}) {st}" for i, st in enumerate(data.STATUSES, start=1)))
    sraw = _ask(f"  Status for {child['name']} [1]: ", "1")
    if sraw is None:
        return
    try:
        status = data.STATUSES[int(sraw) - 1]
    except (ValueError, IndexError):
        status = sraw.strip().lower()
    reason = None
    if status in ("absent", "sick"):
        reason = _ask("  Absence reason (optional): ", "") or None
    try:
        data.mark(child["pupil_id"], when, status,
                  room=child["room"], absence_reason=reason)
        print(f"  ✓ {child['name']} marked {status}.")
    except data.ValidationError as e:
        print(f"  ✗ {e}")


def _mark_all(when: str) -> None:
    try:
        count = data.mark_all_present(when)
        print(f"  ✓ Marked {count} unmarked child(ren) present for {when}.")
    except data.ValidationError as e:
        print(f"  ✗ {e}")


def run(auth=None) -> None:
    """Entry point for the Daily Register CLI screen."""
    when = data.today()
    new_when = _ask(f"\n  Register date [{when}]: ", when)
    if new_when is None:
        return
    when = new_when
    while True:
        try:
            rows = _print_register(when)
        except data.ValidationError as e:
            print(f"  ✗ {e}")
            rows = []
        except Exception as e:  # noqa: BLE001
            logger.exception("Could not load daily register")
            print(f"  ✗ Could not load register: {e}")
            rows = []
        print("\n   1) Mark a child")
        print("   2) Mark all unmarked present")
        print("   3) Change date")
        print("   0) Back")
        choice = _ask("  Select: ", "")
        if choice is None:
            return
        if choice == "1":
            _mark_child(when, rows)
            _pause()
        elif choice == "2":
            _mark_all(when)
            _pause()
        elif choice == "3":
            nd = _ask(f"  Register date [{when}]: ", when)
            if nd is not None:
                when = nd
        elif choice in ("0", ""):
            return
        else:
            print("  Invalid selection.")


def dispatch(label: str) -> bool:
    if label != "Daily Register":
        return False
    run()
    return True
