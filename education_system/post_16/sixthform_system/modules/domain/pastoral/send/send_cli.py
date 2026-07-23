"""CLI flows for Sixth Form SEND register."""

from __future__ import annotations

import logging
from datetime import date as _date
from typing import Any, Callable
from education_system.post_16.sixthform_system.modules.domain.pastoral.send import (
    send as data,
)
from education_system.post_16.sixthform_system.modules.domain.pastoral.send.send import (
    CYCLE_STAGES,
    DEFAULT_CYCLE_STAGE,
    DEFAULT_NEED_TYPE,
    DEFAULT_REGISTER_STATUS,
    DEFAULT_STATUS,
    NEED_TYPES,
    REGISTER_STATUSES,
    SENDEntry,
    STATUSES,
    ValidationError,
)
from education_system.post_16.sixthform_system.modules.domain.students.students import (
    students as _students,
)

logger = logging.getLogger(__name__)


class _UserAbort(Exception):
    pass


def _input(prompt: str, *, default: str = "",
            allow_empty: bool = True) -> str:
    suffix = f" [{default}]" if default else ""
    try:
        raw = input(f"  {prompt}{suffix}: ")
    except (EOFError, KeyboardInterrupt):
        print()
        raise _UserAbort
    s = raw.strip()
    if s.lower() == "cancel":
        raise _UserAbort
    if not s:
        if default:
            return default
        if not allow_empty:
            print("    Value is required.")
            return _input(prompt, default=default,
                            allow_empty=False)
        return ""
    return s


def _pause() -> None:
    try:
        input("\n  Press Enter to continue...")
    except (EOFError, KeyboardInterrupt):
        pass


def _yes_no(prompt: str, *, default: bool = False) -> bool:
    raw = _input(f"{prompt} (y/n)",
                  default="y" if default else "n").strip().lower()
    return raw in ("y", "yes")


def _multiline(prompt: str, *, default: str = "") -> str:
    print(f"\n  {prompt} (end with '.'; ENTER for default)")
    if default:
        for line in default.splitlines():
            print(f"    | {line}")
    lines: list[str] = []
    try:
        while True:
            ln = input("  > ")
            if ln.strip() == ".":
                break
            if not lines and not ln:
                return default
            lines.append(ln)
    except (EOFError, KeyboardInterrupt):
        print()
        raise _UserAbort
    return "\n".join(lines)


def _pick_from(label: str, options: list[str],
                default: str | None = None) -> str:
    print(f"\n  {label}:")
    for i, opt in enumerate(options, 1):
        marker = " *" if opt == default else "  "
        print(f"    {marker}{i:>2}) {opt or '(none)'}")
    while True:
        raw = _input(f"  Pick #1..{len(options)}",
                      default=default or "")
        if default and raw == default:
            return default
        if not raw.isdigit():
            print("    Enter a number.")
            continue
        n = int(raw)
        if not (1 <= n <= len(options)):
            print("    Out of range.")
            continue
        return options[n - 1]


def _pick_student() -> str:
    rows = _students.list_students()
    if not rows:
        print("    No students.")
        raise _UserAbort
    print("\n  Students:")
    for i, s in enumerate(rows, 1):
        full = f"{getattr(s, 'first_name', '')} " \
               f"{getattr(s, 'last_name', '')}".strip()
        print(f"    {i:>3}) {s.student_id:<12}  {full}")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or id)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1].student_id
        match = next((s for s in rows if s.student_id == raw), None)
        if match:
            return match.student_id
        print("    No matching student.")


def _pick_entry() -> SENDEntry:
    rows = data.list_entries()
    if not rows:
        print("    No SEND entries yet.")
        raise _UserAbort
    print("\n  SEND entries:")
    for i, e in enumerate(rows, 1):
        flag = "!" if e.review_overdue else " "
        print(f"    {i:>3}){flag}#{e.entry_id}  "
              f"{e.student_id:<12}  {e.register_status[:12]:<12}  "
              f"{e.primary_need[:24]:<24}  "
              f"cycle {e.cycle_number}-{e.cycle_stage[:6]:<6}  "
              f"[{e.status}]")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or id)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1]
            match = next((e for e in rows if e.entry_id == n), None)
            if match:
                return match
        print("    No matching entry.")


def _print_table(rows: list[SENDEntry]) -> None:
    if not rows:
        print("\n  (none)")
        return
    print()
    print(f"  {'#':>4}  {'Student':<12}  {'Register':<14}  "
          f"{'Primary need':<26}  Cycle    "
          f"{'Status':<14}  Next review")
    print("  " + "-" * 110)
    for e in rows:
        cyc = f"{e.cycle_number}-{e.cycle_stage[:6]}"
        nr = e.next_review_due or "—"
        if e.review_overdue:
            nr = f"OVERDUE ({nr})"
        print(f"  {e.entry_id:>4}  {e.student_id:<12}  "
              f"{e.register_status[:14]:<14}  "
              f"{e.primary_need[:26]:<26}  "
              f"{cyc:<8}  {e.status:<14}  {nr}")
    print(f"\n  {len(rows)} entry(ies).")


def _print_full(e: SENDEntry) -> None:
    print()
    print(f"    #{e.entry_id}  Student {e.student_id}")
    print(f"    Register status   : {e.register_status}")
    print(f"    Primary need      : {e.primary_need}")
    print(f"    Secondary need    : {e.secondary_need or '—'}")
    print(f"    EHCP ref / issued : "
          f"{e.ehcp_reference or '—'}  {e.ehcp_issued_on or '—'}")
    print(f"    Date added        : {e.date_added}")
    print(f"    Cycle             : {e.cycle_number} — "
          f"{e.cycle_stage}")
    print(f"    Next review       : {e.next_review_due or '—'}"
          + ("  (OVERDUE)" if e.review_overdue else ""))
    print(f"    Last review       : {e.last_review_on or '—'}")
    print(f"    Key worker / SENCo: "
          f"{e.key_worker or '—'} / {e.senco or '—'}")
    print(f"    Parent consent    : "
          f"{'yes' if e.parent_consent else 'no'}")
    print(f"    Status            : {e.status}")
    if e.exit_reason:
        print(f"    Exit              : {e.exit_on or '—'} — "
              f"{e.exit_reason}")
    for label, val in (
            ("Provision summary",   e.provision_summary),
            ("Outcomes",            e.outcomes),
            ("Strategies",          e.strategies),
            ("External agencies",   e.external_agencies),
            ("Pupil voice",         e.pupil_voice),
            ("Notes",               e.notes),
    ):
        if val:
            print(f"\n    {label}:")
            for line in val.splitlines():
                print(f"      {line}")


# ── Flows ────────────────────────────────────────────────────────

def list_all() -> None:
    print("\n═══ All SEND Entries ═══")
    _print_table(data.list_entries())
    _pause()


def list_open() -> None:
    print("\n═══ Open SEND Entries ═══")
    _print_table(data.list_entries(open_only=True))
    _pause()


def list_overdue() -> None:
    print("\n═══ Overdue Reviews ═══")
    _print_table(data.list_entries(overdue_only=True))
    _pause()


def filter_flow() -> None:
    print("\n═══ Filter ═══")
    try:
        student = _input("Student id") or None
        reg = _input(
            f"Register ({'/'.join(REGISTER_STATUSES[:3])}…)") or None
        need = _input(
            f"Primary need ({'/'.join(NEED_TYPES[:2])}…)") or None
        stage = _input(
            f"Cycle stage ({'/'.join(CYCLE_STAGES)})") or None
        status = _input(f"Status ({'/'.join(STATUSES)})") or None
        kw = _input("Key worker contains") or None
        senco = _input("SENCo contains") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        rows = data.list_entries(
            student_id=student, register_status=reg,
            primary_need=need, cycle_stage=stage,
            status=status, key_worker_like=kw,
            senco_like=senco)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    _print_table(rows)
    _pause()


def per_student_flow() -> None:
    print("\n═══ Per-Student SEND History ═══")
    try:
        sid = _pick_student()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _print_table(data.entries_for_student(sid))
    _pause()


def view_flow() -> None:
    print("\n═══ View Entry ═══")
    try:
        e = _pick_entry()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _print_full(e)
    _pause()


def _collect_form(existing: SENDEntry | None) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    is_edit = existing is not None
    if is_edit:
        payload["student_id"] = existing.student_id
    else:
        payload["student_id"] = _pick_student()
    payload["register_status"] = _pick_from(
        "Register status", list(REGISTER_STATUSES),
        default=(existing.register_status if is_edit
                  else DEFAULT_REGISTER_STATUS))
    payload["primary_need"] = _pick_from(
        "Primary need", list(NEED_TYPES),
        default=(existing.primary_need if is_edit
                  else DEFAULT_NEED_TYPE))
    payload["secondary_need"] = _pick_from(
        "Secondary need", [""] + list(NEED_TYPES),
        default=(existing.secondary_need if is_edit else ""))
    payload["ehcp_reference"] = _input(
        "EHCP reference",
        default=(existing.ehcp_reference or "")
        if is_edit else "")
    payload["ehcp_issued_on"] = _input(
        "EHCP issued on (YYYY-MM-DD)",
        default=(existing.ehcp_issued_on or "")
        if is_edit else "")
    payload["date_added"] = _input(
        "Date added (YYYY-MM-DD)",
        default=(existing.date_added if is_edit
                  else _date.today().isoformat()),
        allow_empty=False)
    payload["cycle_number"] = _input(
        "Cycle number",
        default=(str(existing.cycle_number) if is_edit else "1"))
    payload["cycle_stage"] = _pick_from(
        "Cycle stage", list(CYCLE_STAGES),
        default=(existing.cycle_stage if is_edit
                  else DEFAULT_CYCLE_STAGE))
    payload["next_review_due"] = _input(
        "Next review due (YYYY-MM-DD)",
        default=(existing.next_review_due or "")
        if is_edit else "")
    payload["last_review_on"] = _input(
        "Last review on (YYYY-MM-DD)",
        default=(existing.last_review_on or "")
        if is_edit else "")
    try:
        payload["provision_summary"] = _multiline(
            "Provision summary",
            default=(existing.provision_summary or "")
            if is_edit else "")
        payload["outcomes"] = _multiline(
            "Outcomes / targets",
            default=(existing.outcomes or "") if is_edit else "")
        payload["strategies"] = _multiline(
            "Strategies",
            default=(existing.strategies or "")
            if is_edit else "")
        payload["external_agencies"] = _multiline(
            "External agencies",
            default=(existing.external_agencies or "")
            if is_edit else "")
        payload["pupil_voice"] = _multiline(
            "Pupil voice",
            default=(existing.pupil_voice or "")
            if is_edit else "")
    except _UserAbort:
        raise
    payload["key_worker"] = _input(
        "Key worker",
        default=(existing.key_worker or "") if is_edit else "")
    payload["senco"] = _input(
        "SENCo",
        default=(existing.senco or "") if is_edit else "")
    payload["parent_consent"] = _yes_no(
        "Parent consent?",
        default=(existing.parent_consent if is_edit else True))
    payload["status"] = _pick_from(
        "Status", list(STATUSES),
        default=(existing.status if is_edit else DEFAULT_STATUS))
    if payload["status"] == "Exited":
        payload["exit_reason"] = _input(
            "Exit reason",
            default=(existing.exit_reason or "")
            if is_edit else "")
        payload["exit_on"] = _input(
            "Exit date (YYYY-MM-DD)",
            default=(existing.exit_on or _date.today().isoformat())
            if is_edit else _date.today().isoformat())
    payload["notes"] = _input(
        "Notes",
        default=(existing.notes or "") if is_edit else "")
    return payload


def new_entry() -> None:
    print("\n═══ New SEND Entry ═══")
    try:
        payload = _collect_form(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        e = data.create_entry(payload)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ Created #{e.entry_id}")
    _pause()


def edit_entry() -> None:
    print("\n═══ Edit SEND Entry ═══")
    try:
        e = _pick_entry()
        payload = _collect_form(e)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_entry(e.entry_id, payload)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ Updated #{e.entry_id}")
    _pause()


def advance_cycle_flow() -> None:
    print("\n═══ Advance APDR Cycle ═══")
    try:
        e = _pick_entry()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        e2 = data.advance_cycle(e.entry_id)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ Now cycle {e2.cycle_number} — {e2.cycle_stage}")
    _pause()


def record_review_flow() -> None:
    print("\n═══ Record Review ═══")
    try:
        e = _pick_entry()
        when = _input("Reviewed on (YYYY-MM-DD)",
                        default=_date.today().isoformat())
        next_due = _input("Next review due (YYYY-MM-DD)",
                            default=e.next_review_due or "")
        outcomes = _multiline("Outcomes update",
                                default=e.outcomes or "")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.record_review(e.entry_id,
                                next_review_due=next_due or None,
                                outcomes=outcomes or None,
                                reviewed_on=when)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ Review recorded on #{e.entry_id}")
    _pause()


def exit_flow() -> None:
    print("\n═══ Exit Register ═══")
    try:
        e = _pick_entry()
        reason = _input("Exit reason", allow_empty=False)
        when = _input("Exit date (YYYY-MM-DD)",
                        default=_date.today().isoformat())
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.exit_register(e.entry_id, reason=reason, exit_on=when)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{e.entry_id} exited register")
    _pause()


def set_status_flow() -> None:
    print("\n═══ Change Status ═══")
    try:
        e = _pick_entry()
        new_status = _pick_from("New status", list(STATUSES),
                                  default=e.status)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.set_status(e.entry_id, new_status)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{e.entry_id} → {new_status}")
    _pause()


def delete_flow() -> None:
    print("\n═══ Delete ═══")
    try:
        e = _pick_entry()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if _input(f"Delete entry #{e.entry_id}? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_entry(e.entry_id):
        print(f"\n  ✓ Deleted #{e.entry_id}")
    _pause()


def summary_flow() -> None:
    print("\n═══ SEND Summary ═══")
    s = data.summary()
    print(f"\n  Total              : {s.total}")
    print(f"  Open               : {s.open_count}")
    print(f"  EHCP entries       : {s.ehcp_count}")
    print(f"  Overdue reviews    : {s.overdue_reviews}")
    print(f"  Distinct students  : {s.distinct_students}")
    print("\n  By register status:")
    for k in REGISTER_STATUSES:
        n = s.by_register_status.get(k, 0)
        if n:
            print(f"    {k:<22}: {n}")
    print("\n  By primary need:")
    for k in NEED_TYPES:
        n = s.by_primary_need.get(k, 0)
        if n:
            print(f"    {k:<34}: {n}")
    print("\n  By cycle stage:")
    for k in CYCLE_STAGES:
        n = s.by_cycle_stage.get(k, 0)
        if n:
            print(f"    {k:<10}: {n}")
    print("\n  By status:")
    for k in STATUSES:
        n = s.by_status.get(k, 0)
        if n:
            print(f"    {k:<18}: {n}")
    _pause()


_MENU: list[tuple[str, Callable[[], None]]] = [
    ("List all",            list_all),
    ("List open",           list_open),
    ("Overdue reviews",     list_overdue),
    ("Filter",              filter_flow),
    ("Per-student",         per_student_flow),
    ("View",                view_flow),
    ("─" * 6,               lambda: None),
    ("New entry",           new_entry),
    ("Edit entry",          edit_entry),
    ("Advance APDR cycle",  advance_cycle_flow),
    ("Record review",       record_review_flow),
    ("Exit register",       exit_flow),
    ("Change status",       set_status_flow),
    ("Delete",              delete_flow),
    ("─" * 6,               lambda: None),
    ("Summary",             summary_flow),
]


def run() -> None:
    while True:
        print("\n── SEND Register ──")
        for i, (label, _) in enumerate(_MENU, 1):
            if label.startswith("─"):
                print(f"      {label * 3}")
            else:
                print(f"  {i:>2}) {label}")
        print("   0) Back")
        try:
            choice = input("  Select: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if choice == "0":
            return
        if not choice.isdigit() or not (1 <= int(choice) <= len(_MENU)):
            print("  Invalid selection.")
            continue
        label, handler = _MENU[int(choice) - 1]
        if label.startswith("─"):
            continue
        try:
            handler()
        except _UserAbort:
            print("\n  Cancelled.")
        except Exception as e:
            logger.exception("SEND CLI crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "SEND":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("SEND CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
