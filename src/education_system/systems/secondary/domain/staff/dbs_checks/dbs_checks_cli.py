"""CLI flows for Secondary School DBS Checks."""

from __future__ import annotations

import logging
from datetime import date as _date
from typing import Any, Callable
from education_system.systems.secondary.domain.staff.dbs_checks import (
    dbs_checks as data,
)
from education_system.systems.secondary.domain.staff.dbs_checks.dbs_checks import (
    CERTIFICATE_TYPES,
    DBSCheck,
    DEFAULT_CERTIFICATE_TYPE,
    DEFAULT_LEVEL,
    DEFAULT_STATUS,
    LEVELS,
    STATUSES,
    ValidationError,
)
from education_system.systems.secondary.domain.staff import (
    staff as _staff,
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


def _pick_staff() -> str:
    rows = _staff.list_staff()
    if not rows:
        print("    No staff.")
        raise _UserAbort
    print("\n  Staff:")
    for i, s in enumerate(rows, 1):
        full = f"{getattr(s, 'first_name', '')} " \
               f"{getattr(s, 'last_name', '')}".strip()
        print(f"    {i:>3}) {s.staff_id:<12}  {full}")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or id)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1].staff_id
        match = next((s for s in rows
                        if s.staff_id == raw.upper()), None)
        if match:
            return match.staff_id
        print("    No matching staff.")


def _pick_check() -> DBSCheck:
    rows = data.list_checks()
    if not rows:
        print("    No DBS checks yet.")
        raise _UserAbort
    print("\n  DBS checks:")
    for i, c in enumerate(rows, 1):
        flag = ""
        if c.is_expired:
            flag = "!"
        elif c.expiring_soon:
            flag = "~"
        print(f"    {i:>3}){flag:<2} #{c.check_id}  "
              f"{c.staff_id:<12}  "
              f"{c.level[:22]:<22}  "
              f"expires {c.expires_on or '—'}  "
              f"[{c.status}]")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or id)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1]
            match = next((r for r in rows
                            if r.check_id == n), None)
            if match:
                return match
        print("    No matching check.")


def _print_table(rows: list[DBSCheck]) -> None:
    if not rows:
        print("\n  (none)")
        return
    print()
    print(f"  {'#':>4}  {'Staff':<12}  {'Level':<26}  "
          f"{'DBS no.':<14}  {'Issued':<10}  "
          f"{'Expires':<10}  US  {'Status':<22}  Flags")
    print("  " + "-" * 140)
    for c in rows:
        flags = []
        if c.is_expired:
            flags.append("EXP")
        elif c.expiring_soon:
            flags.append("SOON")
        if c.update_check_overdue:
            flags.append("UC-OVERDUE")
        if (c.risk_assessment_required
                and not c.risk_assessment_completed_on):
            flags.append("RA-PEND")
        if not c.signed_off_by:
            flags.append("UNSIGNED")
        print(f"  {c.check_id:>4}  {c.staff_id:<12}  "
              f"{c.level[:26]:<26}  "
              f"{(c.dbs_number or '—')[:14]:<14}  "
              f"{(c.issued_on or '—'):<10}  "
              f"{(c.expires_on or '—'):<10}  "
              f"{'y' if c.update_service_subscribed else 'n':<2}  "
              f"{c.status:<22}  {','.join(flags)}")
    print(f"\n  {len(rows)} check(s).")


def _print_full(c: DBSCheck) -> None:
    print()
    print(f"    #{c.check_id}  Staff {c.staff_id}")
    print(f"    Level                : {c.level}")
    print(f"    DBS number           : {c.dbs_number or '—'}")
    print(f"    Applied on           : {c.applied_on or '—'}")
    print(f"    Issued on            : {c.issued_on or '—'}")
    print(f"    Expires on           : {c.expires_on or '—'}"
          + ("  (EXPIRED)" if c.is_expired else
              "  (expiring soon)" if c.expiring_soon else ""))
    print(f"    Certificate type     : {c.certificate_type}")
    print(f"    Certificate seen on  : "
          f"{c.certificate_seen_on or '—'}")
    print(f"    Update service       : "
          f"{'subscribed' if c.update_service_subscribed else 'no'}"
          + (f"  ID {c.update_service_id}"
              if c.update_service_id else ""))
    print(f"    Last update check    : "
          f"{c.last_update_check_on or '—'}")
    print(f"    Next update check    : "
          f"{c.next_update_check_due or '—'}"
          + ("  (OVERDUE)"
              if c.update_check_overdue else ""))
    print(f"    Portability check    : "
          f"{'yes' if c.portability_check else 'no'}")
    print(f"    Risk assess. req.    : "
          f"{'yes' if c.risk_assessment_required else 'no'}")
    print(f"    Risk assess. on      : "
          f"{c.risk_assessment_completed_on or '—'}")
    print(f"    Risk assess. outcome : "
          f"{c.risk_assessment_outcome or '—'}")
    print(f"    Signed off by        : "
          f"{c.signed_off_by or '—'}  on "
          f"{c.signed_off_on or '—'}")
    print(f"    Status               : {c.status}")
    if c.notes:
        print("\n    Notes:")
        for line in c.notes.splitlines():
            print(f"      {line}")


# ── Flows ───────────────────────────────────────────────

def list_all() -> None:
    print("\n═══ All DBS Checks ═══")
    _print_table(data.list_checks())
    _pause()


def list_active() -> None:
    print("\n═══ Active ═══")
    _print_table(data.list_checks(active_only=True))
    _pause()


def list_expired() -> None:
    print("\n═══ Expired ═══")
    _print_table(data.list_checks(expired=True))
    _pause()


def list_expiring_soon() -> None:
    print("\n═══ Expiring Soon (≤90 days) ═══")
    _print_table(data.list_checks(expiring_soon=True))
    _pause()


def list_update_overdue() -> None:
    print("\n═══ Update Check Overdue ═══")
    _print_table(data.list_checks(update_check_overdue=True))
    _pause()


def list_unsigned() -> None:
    print("\n═══ Unsigned ═══")
    _print_table(data.list_checks(unsigned=True))
    _pause()


def list_risk_pending() -> None:
    print("\n═══ Risk Assessment Pending ═══")
    _print_table(data.list_checks(risk_assessment_pending=True))
    _pause()


def filter_flow() -> None:
    print("\n═══ Filter ═══")
    try:
        sid = _input("Staff id") or None
        level = _input(f"Level ({'/'.join(LEVELS[:2])}…)") or None
        status = _input(
            f"Status ({'/'.join(STATUSES[:3])}…)") or None
        ct = _input(
            f"Cert type ({'/'.join(CERTIFICATE_TYPES[:2])}…)") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    rows = data.list_checks(staff_id=sid, level=level,
                                  status=status,
                                  certificate_type=ct)
    _print_table(rows)
    _pause()


def per_staff_flow() -> None:
    print("\n═══ Per-Staff ═══")
    try:
        sid = _pick_staff()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _print_table(data.checks_for_staff(sid))
    _pause()


def view_flow() -> None:
    print("\n═══ View Check ═══")
    try:
        c = _pick_check()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _print_full(c)
    _pause()


def _collect_form(existing: DBSCheck | None) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    is_edit = existing is not None
    if is_edit:
        payload["staff_id"] = existing.staff_id
    else:
        payload["staff_id"] = _pick_staff()
    payload["level"] = _pick_from(
        "Level", list(LEVELS),
        default=(existing.level if is_edit else DEFAULT_LEVEL))
    payload["dbs_number"] = _input(
        "DBS number",
        default=(existing.dbs_number or "")
        if is_edit else "")
    payload["applied_on"] = _input(
        "Applied on (YYYY-MM-DD)",
        default=(existing.applied_on or "")
        if is_edit else "")
    payload["issued_on"] = _input(
        "Issued on (YYYY-MM-DD)",
        default=(existing.issued_on or "")
        if is_edit else "")
    payload["expires_on"] = _input(
        "Expires on (YYYY-MM-DD)",
        default=(existing.expires_on or "")
        if is_edit else "")
    payload["certificate_type"] = _pick_from(
        "Certificate type", list(CERTIFICATE_TYPES),
        default=(existing.certificate_type if is_edit
                  else DEFAULT_CERTIFICATE_TYPE))
    payload["certificate_seen_on"] = _input(
        "Certificate seen on (YYYY-MM-DD)",
        default=(existing.certificate_seen_on or "")
        if is_edit else "")
    payload["update_service_subscribed"] = _yes_no(
        "Update service subscribed?",
        default=(existing.update_service_subscribed
                  if is_edit else False))
    payload["update_service_id"] = _input(
        "Update service ID",
        default=(existing.update_service_id or "")
        if is_edit else "")
    payload["last_update_check_on"] = _input(
        "Last update check on (YYYY-MM-DD)",
        default=(existing.last_update_check_on or "")
        if is_edit else "")
    payload["next_update_check_due"] = _input(
        "Next update check due (YYYY-MM-DD)",
        default=(existing.next_update_check_due or "")
        if is_edit else "")
    payload["portability_check"] = _yes_no(
        "Portability check?",
        default=(existing.portability_check
                  if is_edit else False))
    payload["risk_assessment_required"] = _yes_no(
        "Risk assessment required?",
        default=(existing.risk_assessment_required
                  if is_edit else False))
    if payload["risk_assessment_required"]:
        payload["risk_assessment_completed_on"] = _input(
            "Risk assessment completed on (YYYY-MM-DD)",
            default=(existing.risk_assessment_completed_on or "")
            if is_edit else "")
        try:
            payload["risk_assessment_outcome"] = _multiline(
                "Risk assessment outcome",
                default=(existing.risk_assessment_outcome or "")
                if is_edit else "")
        except _UserAbort:
            raise
    payload["signed_off_by"] = _input(
        "Signed off by",
        default=(existing.signed_off_by or "")
        if is_edit else "")
    payload["signed_off_on"] = _input(
        "Signed off on (YYYY-MM-DD)",
        default=(existing.signed_off_on or "")
        if is_edit else "")
    payload["status"] = _pick_from(
        "Status", list(STATUSES),
        default=(existing.status if is_edit
                  else DEFAULT_STATUS))
    try:
        payload["notes"] = _multiline(
            "Notes",
            default=(existing.notes or "") if is_edit else "")
    except _UserAbort:
        raise
    return payload


def new_check() -> None:
    print("\n═══ New DBS Check ═══")
    try:
        payload = _collect_form(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        c = data.create_check(payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Created check #{c.check_id}")
    _pause()


def edit_check() -> None:
    print("\n═══ Edit Check ═══")
    try:
        c = _pick_check()
        payload = _collect_form(c)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_check(c.check_id, payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Updated #{c.check_id}")
    _pause()


def issue_certificate_flow() -> None:
    print("\n═══ Issue Certificate ═══")
    try:
        c = _pick_check()
        num = _input("DBS number",
                        default=c.dbs_number or "",
                        allow_empty=False)
        issued = _input("Issued on (YYYY-MM-DD)",
                            default=_date.today().isoformat())
        expires = _input("Expires on (YYYY-MM-DD)",
                             default=c.expires_on or "")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.issue_certificate(c.check_id, dbs_number=num,
                                    issued_on=issued,
                                    expires_on=expires or None)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Certificate issued on #{c.check_id}")
    _pause()


def see_certificate_flow() -> None:
    print("\n═══ Mark Certificate Seen ═══")
    try:
        c = _pick_check()
        when = _input("Seen on (YYYY-MM-DD)",
                        default=_date.today().isoformat())
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.see_certificate(c.check_id, seen_on=when)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Certificate seen on #{c.check_id}")
    _pause()


def subscribe_update_service_flow() -> None:
    print("\n═══ Subscribe to Update Service ═══")
    try:
        c = _pick_check()
        uid = _input("Update service ID",
                        default=c.update_service_id or "")
        next_due = _input("Next check due (YYYY-MM-DD)",
                              default=c.next_update_check_due or "")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.subscribe_update_service(
            c.check_id, update_id=uid or None,
            next_check_due=next_due or None)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Subscribed on #{c.check_id}")
    _pause()


def record_update_check_flow() -> None:
    print("\n═══ Record Update Check ═══")
    try:
        c = _pick_check()
        when = _input("Checked on (YYYY-MM-DD)",
                        default=_date.today().isoformat())
        next_due = _input("Next check due (YYYY-MM-DD, "
                              "blank = auto +12mo)")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.record_update_check(c.check_id, checked_on=when,
                                       next_check_due=next_due
                                       or None)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Update check recorded on #{c.check_id}")
    _pause()


def complete_risk_assessment_flow() -> None:
    print("\n═══ Complete Risk Assessment ═══")
    try:
        c = _pick_check()
        outcome = _multiline("Outcome",
                                default=c.risk_assessment_outcome or "")
        when = _input("Completed on (YYYY-MM-DD)",
                        default=_date.today().isoformat())
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if not outcome:
        print("  ✗ Outcome required.")
        _pause()
        return
    try:
        data.complete_risk_assessment(c.check_id,
                                            outcome=outcome,
                                            completed_on=when)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Risk assessment completed on #{c.check_id}")
    _pause()


def sign_off_flow() -> None:
    print("\n═══ Sign Off ═══")
    try:
        c = _pick_check()
        by = _input("Signed off by",
                       default=c.signed_off_by or "",
                       allow_empty=False)
        when = _input("Signed off on (YYYY-MM-DD)",
                        default=_date.today().isoformat())
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.sign_off(c.check_id, signed_off_by=by,
                          signed_off_on=when)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Signed off on #{c.check_id}")
    _pause()


def mark_lapsed_flow() -> None:
    print("\n═══ Mark Lapsed ═══")
    try:
        c = _pick_check()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.mark_lapsed(c.check_id)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{c.check_id} → Lapsed")
    _pause()


def start_renewal_flow() -> None:
    print("\n═══ Start Renewal ═══")
    try:
        c = _pick_check()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.start_renewal(c.check_id)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{c.check_id} → Renewing")
    _pause()


def set_status_flow() -> None:
    print("\n═══ Change Status ═══")
    try:
        c = _pick_check()
        new_status = _pick_from("New status", list(STATUSES),
                                  default=c.status)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.set_status(c.check_id, new_status)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{c.check_id} → {new_status}")
    _pause()


def delete_flow() -> None:
    print("\n═══ Delete ═══")
    try:
        c = _pick_check()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if _input(f"Delete check #{c.check_id}? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_check(c.check_id):
        print(f"\n  ✓ Deleted #{c.check_id}")
    _pause()


def summary_flow() -> None:
    print("\n═══ DBS Summary ═══")
    s = data.summary()
    print(f"\n  Total                 : {s.total}")
    print(f"  Active                : {s.active}")
    print(f"  Cleared               : {s.cleared}")
    print(f"  Pending               : {s.pending}")
    print(f"  Renewing              : {s.renewing}")
    print(f"  Expired               : {s.expired}")
    print(f"  Expiring soon         : {s.expiring_soon}")
    print(f"  Update check overdue  : {s.update_check_overdue}")
    print(f"  Update service subs.  : {s.update_service_subscribed}")
    print(f"  Risk assess. pending  : {s.risk_assessment_pending}")
    print(f"  Unsigned              : {s.unsigned}")
    print(f"  Distinct staff        : {s.distinct_staff}")
    print("\n  By level:")
    for k in LEVELS:
        n = s.by_level.get(k, 0)
        if n:
            print(f"    {k:<32}: {n}")
    print("\n  By status:")
    for k in STATUSES:
        n = s.by_status.get(k, 0)
        if n:
            print(f"    {k:<22}: {n}")
    print("\n  By certificate type:")
    for k in CERTIFICATE_TYPES:
        n = s.by_certificate_type.get(k, 0)
        if n:
            print(f"    {k:<22}: {n}")
    _pause()


_MENU: list[tuple[str, Callable[[], None]]] = [
    ("List all",                list_all),
    ("Active only",             list_active),
    ("Expired",                 list_expired),
    ("Expiring soon",           list_expiring_soon),
    ("Update overdue",          list_update_overdue),
    ("Unsigned",                list_unsigned),
    ("Risk assess. pending",    list_risk_pending),
    ("Filter",                  filter_flow),
    ("Per-staff",               per_staff_flow),
    ("View",                    view_flow),
    ("─" * 6,                   lambda: None),
    ("New check",               new_check),
    ("Edit check",              edit_check),
    ("Issue certificate",       issue_certificate_flow),
    ("Mark certificate seen",   see_certificate_flow),
    ("Subscribe to Update Service", subscribe_update_service_flow),
    ("Record update check",     record_update_check_flow),
    ("Complete risk assessment", complete_risk_assessment_flow),
    ("Sign off",                sign_off_flow),
    ("Mark Lapsed",             mark_lapsed_flow),
    ("Start renewal",           start_renewal_flow),
    ("Change status",           set_status_flow),
    ("Delete",                  delete_flow),
    ("─" * 6,                   lambda: None),
    ("Summary",                 summary_flow),
]


def run() -> None:
    while True:
        print("\n── DBS Checks ──")
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
            logger.exception("DBS CLI crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "DBS Checks":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("DBS CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
