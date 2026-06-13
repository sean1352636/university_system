"""CLI flows for Sixth Form Prevent Duty."""

from __future__ import annotations

import logging
from datetime import date as _date
from typing import Any, Callable

from education_system.sixthform_system.modules.domain.pastoral.prevent_duty import (
    prevent_duty as data,
)
from education_system.sixthform_system.modules.domain.pastoral.prevent_duty.prevent_duty import (
    CONCERN_STATUSES,
    CONCERN_TYPES,
    DEFAULT_CONCERN_STATUS,
    DEFAULT_CONCERN_TYPE,
    DEFAULT_REFERRAL_AUTHORITY,
    DEFAULT_REFERRAL_STATUS,
    DEFAULT_RISK_LEVEL,
    DEFAULT_TRAINING_TYPE,
    Concern,
    Referral,
    REFERRAL_AUTHORITIES,
    REFERRAL_STATUSES,
    RISK_LEVELS,
    TRAINING_TYPES,
    Training,
    ValidationError,
)
from education_system.sixthform_system.modules.domain.staff_comms.staff import (
    staff as _staff,
)
from education_system.sixthform_system.modules.domain.students.students import (
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
            return _input(prompt, default=default, allow_empty=False)
        return ""
    return s


def _pause() -> None:
    try:
        input("\n  Press Enter to continue...")
    except (EOFError, KeyboardInterrupt):
        pass


def _pick(prompt: str, choices: tuple[str, ...], *,
          default: str | None = None) -> str:
    print(f"\n  {prompt}:")
    for i, c in enumerate(choices, 1):
        mark = " (default)" if c == default else ""
        print(f"    {i:2d}) {c}{mark}")
    while True:
        raw = _input("Choice (number or name)",
                     default=default or "", allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(choices):
                return choices[n - 1]
        elif raw in choices:
            return raw
        print("    Invalid selection.")


def _today() -> str:
    return _date.today().isoformat()


def _student_id() -> str:
    sid = _input("Student ID", allow_empty=False)
    if _students.get_student(sid) is None:
        print(f"    ✗ No student with id {sid}")
        raise _UserAbort
    return sid


def _staff_id() -> str:
    sid = _input("Staff ID", allow_empty=False)
    if _staff.get_staff(sid) is None:
        print(f"    ✗ No staff member with id {sid}")
        raise _UserAbort
    return sid


def _student_name(sid: str) -> str:
    s = _students.get_student(sid)
    return s.full_name if s else "(unknown)"


def _staff_name(sid: str) -> str:
    s = _staff.get_staff(sid)
    return s.full_name if s else "(unknown)"


# ── Concerns ───────────────────────────────────────────────────────

def _print_concern(c: Concern) -> None:
    name = _student_name(c.student_id)
    print(f"\n  #{c.concern_id}  {c.report_date}  [{c.risk_level}] "
          f"[{c.status}]")
    print(f"    Student: {c.student_id} — {name}")
    print(f"    Type:    {c.concern_type}")
    print(f"    Summary: {c.summary}")
    if c.details:
        print(f"    Details: {c.details}")
    if c.reported_by:
        print(f"    Reporter: {c.reported_by}")
    if c.closed_date:
        print(f"    Closed:  {c.closed_date}  "
              f"outcome: {c.outcome or '—'}")


def concern_add() -> None:
    print("\n── Log Prevent Concern ──")
    try:
        sid = _student_id()
        date = _input("Report date", default=_today(), allow_empty=False)
        ctype = _pick("Concern type", CONCERN_TYPES,
                      default=DEFAULT_CONCERN_TYPE)
        risk = _pick("Risk level", RISK_LEVELS,
                     default=DEFAULT_RISK_LEVEL)
        summary = _input("Summary (≤200 chars)", allow_empty=False)
        details = _input("Details (full description)")
        reporter = _input("Reported by")
        c = data.create_concern({
            "student_id": sid, "report_date": date,
            "concern_type": ctype, "risk_level": risk,
            "summary": summary, "details": details,
            "reported_by": reporter,
        })
        print(f"\n  ✓ Created concern #{c.concern_id}")
    except _UserAbort:
        return
    except ValidationError as e:
        print(f"\n  ✗ {e}")


def concern_list(*, open_only: bool = False) -> None:
    rows = data.list_concerns(open_only=open_only)
    title = "Open Concerns" if open_only else "All Concerns"
    print(f"\n── {title} ({len(rows)}) ──")
    if not rows:
        print("  (none)")
        return
    for c in rows[:80]:
        _print_concern(c)
    if len(rows) > 80:
        print(f"\n  …and {len(rows) - 80} more")


def concern_view() -> None:
    try:
        cid = int(_input("Concern id", allow_empty=False))
    except _UserAbort:
        return
    except ValueError:
        print("  ✗ Must be a number")
        return
    c = data.get_concern(cid)
    if c is None:
        print(f"  ✗ No concern with id {cid}")
        return
    _print_concern(c)
    refs = data.list_referrals(concern_id=cid)
    print(f"\n  Referrals on this concern: {len(refs)}")
    for r in refs:
        _print_referral(r)


def concern_edit() -> None:
    try:
        cid = int(_input("Concern id", allow_empty=False))
    except _UserAbort:
        return
    except ValueError:
        print("  ✗ Must be a number")
        return
    existing = data.get_concern(cid)
    if existing is None:
        print(f"  ✗ No concern with id {cid}")
        return
    _print_concern(existing)
    try:
        upd: dict[str, Any] = {}
        upd["report_date"] = _input("Report date",
                                     default=existing.report_date)
        upd["concern_type"] = _pick("Concern type", CONCERN_TYPES,
                                     default=existing.concern_type)
        upd["risk_level"] = _pick("Risk level", RISK_LEVELS,
                                    default=existing.risk_level)
        upd["summary"] = _input("Summary", default=existing.summary)
        upd["details"] = _input("Details (blank to clear)",
                                 default=existing.details or "")
        upd["reported_by"] = _input("Reported by",
                                     default=existing.reported_by or "")
        upd["status"] = _pick("Status", CONCERN_STATUSES,
                               default=existing.status)
        if upd["status"] in ("No Further Action", "Closed"):
            upd["closed_date"] = _input(
                "Closed date",
                default=existing.closed_date or _today())
            upd["outcome"] = _input("Outcome",
                                     default=existing.outcome or "")
        else:
            upd["closed_date"] = ""
            upd["outcome"] = existing.outcome or ""
        out = data.update_concern(cid, upd)
        print(f"\n  ✓ Updated concern #{out.concern_id}")
    except _UserAbort:
        return
    except ValidationError as e:
        print(f"\n  ✗ {e}")


def concern_close() -> None:
    try:
        cid = int(_input("Concern id to close", allow_empty=False))
    except _UserAbort:
        return
    except ValueError:
        print("  ✗ Must be a number")
        return
    try:
        outcome = _input("Outcome / closing note", default="")
        c = data.close_concern(cid, outcome=outcome or None)
        print(f"  ✓ Concern #{c.concern_id} closed on {c.closed_date}")
    except _UserAbort:
        return
    except ValidationError as e:
        print(f"  ✗ {e}")


def concern_delete() -> None:
    try:
        cid = int(_input("Concern id to delete", allow_empty=False))
    except _UserAbort:
        return
    except ValueError:
        print("  ✗ Must be a number")
        return
    c = data.get_concern(cid)
    if c is None:
        print(f"  ✗ No concern with id {cid}")
        return
    _print_concern(c)
    refs = data.list_referrals(concern_id=cid)
    if refs:
        print(f"\n  This will also delete {len(refs)} referral(s).")
    try:
        confirm = _input("Type DELETE to confirm", allow_empty=False)
    except _UserAbort:
        return
    if confirm != "DELETE":
        print("  Cancelled.")
        return
    if data.delete_concern(cid):
        print(f"  ✓ Deleted concern #{cid}")


# ── Referrals ──────────────────────────────────────────────────────

def _print_referral(r: Referral) -> None:
    print(f"    ↳ Referral #{r.referral_id}  {r.referral_date}  "
          f"[{r.authority}]  [{r.status}]")
    if r.case_officer:
        print(f"      Case officer: {r.case_officer}")
    if r.panel_date:
        print(f"      Panel date:   {r.panel_date}")
    if r.outcome:
        print(f"      Outcome:      {r.outcome}")
    if r.notes:
        print(f"      Notes:        {r.notes}")


def referral_add() -> None:
    print("\n── Add Channel Referral ──")
    try:
        cid = int(_input("Concern id", allow_empty=False))
    except _UserAbort:
        return
    except ValueError:
        print("  ✗ Must be a number")
        return
    if data.get_concern(cid) is None:
        print(f"  ✗ No concern with id {cid}")
        return
    try:
        date = _input("Referral date", default=_today(), allow_empty=False)
        authority = _pick("Authority", REFERRAL_AUTHORITIES,
                          default=DEFAULT_REFERRAL_AUTHORITY)
        officer = _input("Case officer (optional)")
        panel = _input("Channel panel date (optional)")
        status = _pick("Status", REFERRAL_STATUSES,
                        default=DEFAULT_REFERRAL_STATUS)
        outcome = _input("Outcome (optional)")
        notes = _input("Notes")
        r = data.create_referral({
            "concern_id": cid, "referral_date": date,
            "authority": authority, "case_officer": officer,
            "panel_date": panel, "status": status,
            "outcome": outcome, "notes": notes,
        })
        print(f"\n  ✓ Created referral #{r.referral_id}")
    except _UserAbort:
        return
    except ValidationError as e:
        print(f"\n  ✗ {e}")


def referral_list(*, open_only: bool = False) -> None:
    rows = data.list_referrals_with_detail(open_only=open_only)
    title = "Open Channel Referrals" if open_only else "All Channel Referrals"
    print(f"\n── {title} ({len(rows)}) ──")
    if not rows:
        print("  (none)")
        return
    for rr in rows[:80]:
        r = rr.referral
        print(f"\n  #{r.referral_id}  concern #{r.concern_id}  "
              f"{rr.student_id} — {rr.student_name}")
        _print_referral(r)


def referral_edit() -> None:
    try:
        rid = int(_input("Referral id", allow_empty=False))
    except _UserAbort:
        return
    except ValueError:
        print("  ✗ Must be a number")
        return
    existing = data.get_referral(rid)
    if existing is None:
        print(f"  ✗ No referral with id {rid}")
        return
    print(f"\n  Referral #{rid} on concern #{existing.concern_id}")
    _print_referral(existing)
    try:
        upd: dict[str, Any] = {}
        upd["referral_date"] = _input(
            "Referral date", default=existing.referral_date)
        upd["authority"] = _pick("Authority", REFERRAL_AUTHORITIES,
                                  default=existing.authority)
        upd["case_officer"] = _input(
            "Case officer (blank to clear)",
            default=existing.case_officer or "")
        upd["panel_date"] = _input(
            "Panel date (blank to clear)",
            default=existing.panel_date or "")
        upd["status"] = _pick("Status", REFERRAL_STATUSES,
                               default=existing.status)
        upd["outcome"] = _input("Outcome",
                                 default=existing.outcome or "")
        upd["notes"] = _input("Notes", default=existing.notes or "")
        out = data.update_referral(rid, upd)
        print(f"\n  ✓ Updated referral #{out.referral_id}")
    except _UserAbort:
        return
    except ValidationError as e:
        print(f"\n  ✗ {e}")


def referral_delete() -> None:
    try:
        rid = int(_input("Referral id to delete", allow_empty=False))
    except _UserAbort:
        return
    except ValueError:
        print("  ✗ Must be a number")
        return
    r = data.get_referral(rid)
    if r is None:
        print(f"  ✗ No referral with id {rid}")
        return
    _print_referral(r)
    try:
        confirm = _input("Type DELETE to confirm", allow_empty=False)
    except _UserAbort:
        return
    if confirm != "DELETE":
        print("  Cancelled.")
        return
    if data.delete_referral(rid):
        print(f"  ✓ Deleted referral #{rid}")


# ── Training ──────────────────────────────────────────────────────

def _print_training(t: Training) -> None:
    name = _staff_name(t.staff_id)
    badge = ""
    if t.expiry_date:
        if t.is_expired():
            badge = "  [EXPIRED]"
        else:
            d = t.days_to_expiry()
            if d is not None and d <= 60:
                badge = f"  [expires in {d}d]"
    print(f"\n  #{t.training_id}  {t.staff_id} — {name}{badge}")
    print(f"    {t.training_type}  completed {t.completed_date}  "
          f"expires {t.expiry_date or '—'}")
    if t.provider:
        print(f"    Provider: {t.provider}")
    if t.certificate_ref:
        print(f"    Cert ref: {t.certificate_ref}")
    if t.notes:
        print(f"    Notes: {t.notes}")


def training_add() -> None:
    print("\n── Add Training Record ──")
    try:
        sid = _staff_id()
        ttype = _pick("Training type", TRAINING_TYPES,
                       default=DEFAULT_TRAINING_TYPE)
        completed = _input("Completed date", default=_today(),
                            allow_empty=False)
        expiry = _input("Expiry date (optional, e.g. completed + 2y)")
        provider = _input("Provider")
        cert = _input("Certificate ref")
        notes = _input("Notes")
        t = data.create_training({
            "staff_id": sid, "training_type": ttype,
            "completed_date": completed, "expiry_date": expiry,
            "provider": provider, "certificate_ref": cert,
            "notes": notes,
        })
        print(f"\n  ✓ Created training record #{t.training_id}")
    except _UserAbort:
        return
    except ValidationError as e:
        print(f"\n  ✗ {e}")


def training_list() -> None:
    rows = data.list_training()
    print(f"\n── Training Records ({len(rows)}) ──")
    if not rows:
        print("  (none)")
        return
    for t in rows[:80]:
        _print_training(t)


def training_expired() -> None:
    rows = data.list_training(expired_only=True)
    print(f"\n── Expired Training ({len(rows)}) ──")
    if not rows:
        print("  (none)")
        return
    for t in rows:
        _print_training(t)


def training_expiring_soon() -> None:
    rows = data.list_training(expiring_within_days=60)
    print(f"\n── Training expiring within 60 days ({len(rows)}) ──")
    if not rows:
        print("  (none)")
        return
    for t in rows:
        _print_training(t)


def training_edit() -> None:
    try:
        tid = int(_input("Training id", allow_empty=False))
    except _UserAbort:
        return
    except ValueError:
        print("  ✗ Must be a number")
        return
    existing = data.get_training(tid)
    if existing is None:
        print(f"  ✗ No training record with id {tid}")
        return
    _print_training(existing)
    try:
        upd: dict[str, Any] = {}
        upd["training_type"] = _pick("Training type", TRAINING_TYPES,
                                      default=existing.training_type)
        upd["completed_date"] = _input(
            "Completed date", default=existing.completed_date)
        upd["expiry_date"] = _input(
            "Expiry date (blank to clear)",
            default=existing.expiry_date or "")
        upd["provider"] = _input("Provider",
                                  default=existing.provider or "")
        upd["certificate_ref"] = _input(
            "Certificate ref",
            default=existing.certificate_ref or "")
        upd["notes"] = _input("Notes", default=existing.notes or "")
        out = data.update_training(tid, upd)
        print(f"\n  ✓ Updated training #{out.training_id}")
    except _UserAbort:
        return
    except ValidationError as e:
        print(f"\n  ✗ {e}")


def training_delete() -> None:
    try:
        tid = int(_input("Training id to delete", allow_empty=False))
    except _UserAbort:
        return
    except ValueError:
        print("  ✗ Must be a number")
        return
    t = data.get_training(tid)
    if t is None:
        print(f"  ✗ No training with id {tid}")
        return
    _print_training(t)
    try:
        confirm = _input("Type DELETE to confirm", allow_empty=False)
    except _UserAbort:
        return
    if confirm != "DELETE":
        print("  Cancelled.")
        return
    if data.delete_training(tid):
        print(f"  ✓ Deleted training #{tid}")


def training_per_staff() -> None:
    try:
        sid = _staff_id()
    except _UserAbort:
        return
    s = data.per_staff_training(sid)
    print(f"\n  {sid} — {_staff_name(sid)}")
    if s.record_count == 0:
        print("    No training records on file.")
        return
    badge = "EXPIRED" if s.expired else ("in date" if s.in_date else "—")
    print(f"    Records: {s.record_count}    Status: {badge}")
    print(f"    Latest:  {s.latest_type} (completed "
          f"{s.latest_completed}, expires {s.latest_expiry or '—'})")


# ── Overview ──────────────────────────────────────────────────────

def overall_summary() -> None:
    s = data.summary()
    print("\n── Prevent Duty Overview ──")
    print(f"  Concerns:   {s.total_concerns}  "
          f"(open {s.concerns_open}, high-risk open {s.high_risk_open})")
    print(f"  Referrals:  {s.total_referrals}  (open {s.referrals_open})")
    print(f"  Training:   {s.total_training}  "
          f"(expired {s.training_expired}, "
          f"expiring ≤60d {s.training_expiring_soon}, "
          f"staff covered {s.staff_with_training})")

    print("\n  Concerns by status:")
    for k, v in s.concerns_by_status.items():
        if v:
            print(f"    {k:22s} {v}")
    print("\n  Concerns by risk level:")
    for k, v in s.concerns_by_risk.items():
        if v:
            print(f"    {k:22s} {v}")
    print("\n  Referrals by status:")
    for k, v in s.referrals_by_status.items():
        if v:
            print(f"    {k:22s} {v}")


# ── Menu ───────────────────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None] | None]] = [
    ("── Concerns ──",            None),
    ("Log a concern",              concern_add),
    ("List open concerns",         lambda: concern_list(open_only=True)),
    ("List all concerns",          lambda: concern_list(open_only=False)),
    ("View concern + referrals",   concern_view),
    ("Edit concern",               concern_edit),
    ("Close concern",              concern_close),
    ("Delete concern",             concern_delete),
    ("── Channel Referrals ──",   None),
    ("Add referral",                referral_add),
    ("List open referrals",         lambda: referral_list(open_only=True)),
    ("List all referrals",          lambda: referral_list(open_only=False)),
    ("Edit referral",               referral_edit),
    ("Delete referral",             referral_delete),
    ("── Training ──",             None),
    ("Add training record",         training_add),
    ("List all training",           training_list),
    ("Expired training",            training_expired),
    ("Training expiring ≤60d",      training_expiring_soon),
    ("Edit training",               training_edit),
    ("Delete training",             training_delete),
    ("Per-staff training summary",  training_per_staff),
    ("── Summary ──",              None),
    ("Overview",                    overall_summary),
]


def run() -> None:
    while True:
        print("\n── Prevent Duty ──")
        for i, (label, handler) in enumerate(_MENU, 1):
            if handler is None:
                print(f"   {label}")
            else:
                print(f"  {i:2d}) {label}")
        print("   0) Back")
        try:
            choice = input("Select: ").strip()
        except (EOFError, KeyboardInterrupt):
            return
        if choice == "0":
            return
        if not choice.isdigit() or not (1 <= int(choice) <= len(_MENU)):
            print("  Invalid selection.")
            continue
        label, handler = _MENU[int(choice) - 1]
        if handler is None:
            continue
        try:
            handler()
        except _UserAbort:
            print("\n  Cancelled.")
        except Exception as e:
            logger.exception("Prevent Duty CLI crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Prevent Duty":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Prevent Duty CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
