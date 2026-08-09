"""CLI flows for Sixth Form Bursary Applications."""

from __future__ import annotations

import logging
from datetime import date as _date
from typing import Any, Callable
from education_system.systems.sixth_form.domain.finance.bursaries import bursaries
from education_system.systems.sixth_form.domain.finance.bursaries import bursaries as data
from education_system.systems.sixth_form.domain.learners.students import students as student_data
from education_system.systems.sixth_form.domain.finance.bursaries.bursaries import (
    Application,
    BURSARY_TYPES,
    CURRENCY_SYMBOL,
    DEFAULT_DISBURSEMENT_METHOD,
    DEFAULT_DISBURSEMENT_STATUS,
    DEFAULT_STATUS,
    DEFAULT_TYPE,
    Disbursement,
    DISBURSEMENT_METHODS,
    DISBURSEMENT_STATUSES,
    ELIGIBILITY_BASES,
    STATUSES,
    ValidationError,
)

logger = logging.getLogger(__name__)


class _UserAbort(Exception):
    pass


# ── Prompt helpers ─────────────────────────────────────────────────

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


def _pick_from(label: str, options: list[str],
                default: str | None = None) -> str:
    print(f"\n  {label}:")
    for i, opt in enumerate(options, 1):
        marker = " *" if opt == default else "  "
        print(f"    {marker}{i:>2}) {opt}")
    while True:
        raw = _input(f"  Pick #1..{len(options)}", default=default or "")
        if default and raw == default:
            return default
        if not raw.isdigit():
            print("    Enter a number (or 'cancel').")
            continue
        n = int(raw)
        if not (1 <= n <= len(options)):
            print("    Out of range.")
            continue
        return options[n - 1]


def _yes_no(prompt: str, default: bool = False) -> bool:
    raw = _input(f"{prompt} (y/n)", default="y" if default else "n")
    return raw.lower() in ("y", "yes")


def _pick_student() -> str:
    students = student_data.list_students()
    if not students:
        print("    No students.")
        raise _UserAbort
    print("\n  Students:")
    for i, s in enumerate(students, 1):
        print(f"    {i:>3}) {s.student_id}  {s.full_name}")
    while True:
        raw = _input(f"  Pick #1..{len(students)} (or student ID)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(students):
                return students[n - 1].student_id
            continue
        m = next((s for s in students
                   if s.student_id.lower() == raw.lower()), None)
        if m:
            return m.student_id
        print("    No matching student.")


def _money(v: float | None) -> str:
    if v is None:
        return "—"
    return f"{CURRENCY_SYMBOL}{v:.2f}"


# ── Print helpers ──────────────────────────────────────────────────

def _print_views(rows: list[data.ApplicationView]) -> None:
    if not rows:
        print("\n  (no applications)")
        return
    print()
    print(f"  {'#':>4}  {'Student':<10}  {'Name':<22}  "
          f"{'Type':<22}  {'Applied':<10}  "
          f"{'Req':>10}  {'Awd':>10}  {'Paid':>10}  {'Rem':>10}  Status")
    print("  " + "-" * 140)
    req = awd = paid = rem = 0.0
    for v in rows:
        a = v.app
        if a.amount_requested: req += a.amount_requested
        if a.amount_awarded:   awd += a.amount_awarded
        paid += v.paid
        rem  += v.remaining if a.is_approved else 0
        print(f"  {a.application_id:>4}  {a.student_id:<10}  "
              f"{v.student_name[:22]:<22}  "
              f"{a.bursary_type[:22]:<22}  "
              f"{a.application_date:<10}  "
              f"{_money(a.amount_requested):>10}  "
              f"{_money(a.amount_awarded):>10}  "
              f"{_money(v.paid):>10}  "
              f"{_money(v.remaining):>10}  {a.status}")
    print("  " + "-" * 140)
    print(f"  TOTALS: requested {_money(req)}  awarded {_money(awd)}"
          f"  paid {_money(paid)}  remaining {_money(rem)}")
    print(f"\n  {len(rows)} application(s).")


def _print_disbursements(rows: list[Disbursement]) -> None:
    if not rows:
        print("\n  (no disbursements)")
        return
    print()
    print(f"  {'#':>4}  {'App':>4}  {'Paid on':<10}  "
          f"{'Amount':>10}  {'Method':<18}  {'Status':<10}  Reference")
    print("  " + "-" * 90)
    paid_total = 0.0
    for d in rows:
        if d.status == "Paid":
            paid_total += d.amount
        print(f"  {d.disbursement_id:>4}  {d.application_id:>4}  "
              f"{d.paid_on:<10}  {_money(d.amount):>10}  "
              f"{d.method:<18}  {d.status:<10}  {d.reference or '—'}")
    print(f"\n  {len(rows)} disbursement(s).  "
          f"Paid total: {_money(round(paid_total, 2))}")


# ── Application flows ─────────────────────────────────────────────

def list_active() -> None:
    print("\n═══ Active Applications ═══")
    _print_views(data.list_views(active_only=True))
    _row_action_loop()


def list_all() -> None:
    print("\n═══ All Applications ═══")
    _print_views(data.list_views())
    _row_action_loop()


def list_approved() -> None:
    print("\n═══ Approved Applications ═══")
    _print_views(data.list_views(approved_only=True))
    _row_action_loop()


def filter_applications() -> None:
    print("\n═══ Filter Applications ═══")
    try:
        sid = _input("Student ID") or None
        btype = _input("Bursary type") or None
        status = _input(f"Status ({'/'.join(STATUSES)})") or None
        year = _input("Academic year") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        rows = data.list_views(
            student_id=sid, bursary_type=btype, status=status,
            academic_year=year)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    _print_views(rows)
    _row_action_loop()


def per_student() -> None:
    print("\n═══ Per-Student Applications ═══")
    try:
        sid = _pick_student()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    student = student_data.get_student(sid)
    print(f"\n  {student.student_id}  {student.full_name}")
    _print_views(data.list_views(student_id=sid))
    aw, pd, rm = data.student_summary(sid)
    print(f"\n  Totals  awarded: {_money(aw)}  paid: {_money(pd)}  "
          f"remaining: {_money(rm)}")
    _row_action_loop()


def view_application(application_id: int | None = None) -> None:
    print("\n═══ View Application ═══")
    try:
        aid = application_id if application_id is not None else int(
            _input("Application ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    v = data.view_application(aid)
    if v is None:
        print(f"  ✗ No application #{aid}")
        _pause()
        return
    a = v.app
    print()
    print(f"    Application ID   : #{a.application_id}")
    print(f"    Student          : {a.student_id}  {v.student_name}")
    print(f"    Type             : {a.bursary_type}")
    print(f"    Academic year    : {a.academic_year or '—'}")
    print(f"    Applied          : {a.application_date}")
    print(f"    Status           : {a.status}")
    print(f"    Eligibility basis: {a.eligibility_basis or '—'}")
    print(f"    Household income : {_money(a.household_income)}")
    print(f"    Household size   : {a.household_size or '—'}")
    print(f"    Evidence         : "
          f"{'Yes' if a.evidence_received else 'No'}"
          + (f"  ({a.evidence_note})" if a.evidence_note else ""))
    print(f"    Requested        : {_money(a.amount_requested)}")
    print(f"    Awarded          : {_money(a.amount_awarded)}")
    print(f"    Paid             : {_money(v.paid)}")
    print(f"    Remaining        : {_money(v.remaining)}")
    if a.assessed_by:
        print(f"    Assessed by      : {a.assessed_by}  "
              f"on {a.assessed_on or '—'}")
    if a.reason:
        print("\n    Reason:")
        for line in a.reason.splitlines() or [""]:
            print(f"      {line}")
    if a.decision_note:
        print("\n    Decision note:")
        for line in a.decision_note.splitlines() or [""]:
            print(f"      {line}")
    if a.notes:
        print("\n    Notes:")
        for line in a.notes.splitlines() or [""]:
            print(f"      {line}")
    print(f"\n  Disbursements ({v.disbursement_count}):")
    _print_disbursements(data.list_disbursements(application_id=aid))
    _pause()


def _collect_form(existing: Application | None) -> dict[str, Any]:
    is_edit = existing is not None
    p: dict[str, Any] = {}
    if is_edit:
        print(f"\n  Editing application #{existing.application_id} "
              f"for {existing.student_id}")
        p["student_id"] = existing.student_id
    else:
        p["student_id"] = _pick_student()

    p["bursary_type"] = _pick_from(
        "Bursary type", list(BURSARY_TYPES),
        default=existing.bursary_type if is_edit else DEFAULT_TYPE)
    p["academic_year"] = _input(
        "Academic year (e.g. 2025-26, optional)",
        default=(existing.academic_year or "") if is_edit else "")
    p["application_date"] = _input(
        "Application date (YYYY-MM-DD)",
        default=existing.application_date if is_edit
        else _date.today().isoformat(), allow_empty=False)
    p["amount_requested"] = _input(
        f"Amount requested ({CURRENCY_SYMBOL}, optional)",
        default=(f"{existing.amount_requested:.2f}"
                  if is_edit and existing.amount_requested is not None
                  else ""))
    p["amount_awarded"] = _input(
        f"Amount awarded ({CURRENCY_SYMBOL}, blank if not yet approved)",
        default=(f"{existing.amount_awarded:.2f}"
                  if is_edit and existing.amount_awarded is not None
                  else ""))
    p["status"] = _pick_from(
        "Status", list(STATUSES),
        default=existing.status if is_edit else DEFAULT_STATUS)
    p["eligibility_basis"] = _pick_from(
        "Eligibility basis", list(ELIGIBILITY_BASES) + ["(none)"],
        default=(existing.eligibility_basis if is_edit
                  and existing.eligibility_basis else "(none)"))
    if p["eligibility_basis"] == "(none)":
        p["eligibility_basis"] = ""
    p["household_income"] = _input(
        f"Household income ({CURRENCY_SYMBOL}, optional)",
        default=(f"{existing.household_income:.2f}"
                  if is_edit and existing.household_income is not None
                  else ""))
    p["household_size"] = _input(
        "Household size (optional)",
        default=(str(existing.household_size)
                  if is_edit and existing.household_size is not None
                  else ""))
    p["evidence_received"] = _yes_no(
        "Evidence received?",
        default=existing.evidence_received if is_edit else False)
    p["evidence_note"] = _input(
        "Evidence note (optional)",
        default=(existing.evidence_note or "") if is_edit else "")
    p["reason"] = _input(
        "Reason / need (single line)",
        default=(existing.reason or "") if is_edit else "")
    p["assessed_by"] = _input(
        "Assessed by (staff ID, optional)",
        default=(existing.assessed_by or "") if is_edit else "")
    p["assessed_on"] = _input(
        "Assessed on (YYYY-MM-DD, optional)",
        default=(existing.assessed_on or "") if is_edit else "")
    p["decision_note"] = _input(
        "Decision note (optional)",
        default=(existing.decision_note or "") if is_edit else "")
    p["notes"] = _input(
        "Notes (optional)",
        default=(existing.notes or "") if is_edit else "")
    return p


def new_application() -> None:
    print("\n═══ New Application ═══")
    try:
        payload = _collect_form(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        a = data.create_application(payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Created application #{a.application_id} ({a.status})")
    _pause()


def edit_application(application_id: int | None = None) -> None:
    print("\n═══ Edit Application ═══")
    try:
        aid = application_id if application_id is not None else int(
            _input("Application ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    existing = data.get_application(aid)
    if existing is None:
        print(f"  ✗ No application #{aid}")
        _pause()
        return
    try:
        payload = _collect_form(existing)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_application(aid, payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Updated #{aid}")
    _pause()


def approve_flow(application_id: int | None = None) -> None:
    print("\n═══ Approve Application ═══")
    try:
        aid = application_id if application_id is not None else int(
            _input("Application ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    existing = data.get_application(aid)
    if existing is None:
        print(f"  ✗ No application #{aid}")
        _pause()
        return
    try:
        award = _input(
            f"Amount awarded ({CURRENCY_SYMBOL})",
            default=(f"{existing.amount_requested:.2f}"
                      if existing.amount_requested else ""),
            allow_empty=False)
        by = _input("Assessed by (staff ID)")
        note = _input("Decision note (optional)")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.approve(aid, float(award), by or None, note or None)
    except (ValidationError, ValueError) as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Approved #{aid} ({_money(float(award))})")
    _pause()


def reject_flow(application_id: int | None = None) -> None:
    print("\n═══ Reject Application ═══")
    try:
        aid = application_id if application_id is not None else int(
            _input("Application ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    if data.get_application(aid) is None:
        print(f"  ✗ No application #{aid}")
        _pause()
        return
    try:
        note = _input("Decision note (required)", allow_empty=False)
        by = _input("Assessed by (optional)")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.reject(aid, note, by or None)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Rejected #{aid}")
    _pause()


def set_status_flow(application_id: int | None = None) -> None:
    print("\n═══ Change Status ═══")
    try:
        aid = application_id if application_id is not None else int(
            _input("Application ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    existing = data.get_application(aid)
    if existing is None:
        print(f"  ✗ No application #{aid}")
        _pause()
        return
    try:
        new = _pick_from("New status", list(STATUSES),
                            default=existing.status)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.set_status(aid, new)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{aid} → {new}")
    _pause()


def delete_application_flow(application_id: int | None = None) -> None:
    print("\n═══ Delete Application ═══")
    print("  ⚠ This also deletes all disbursements.")
    try:
        aid = application_id if application_id is not None else int(
            _input("Application ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    existing = data.get_application(aid)
    if existing is None:
        print(f"  ✗ No application #{aid}")
        _pause()
        return
    if _input(f"Delete application #{aid}? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_application(aid):
        print(f"\n  ✓ Deleted #{aid}")
    _pause()


# ── Disbursement flows ────────────────────────────────────────────

def add_disbursement_flow(application_id: int | None = None) -> None:
    print("\n═══ Add Disbursement ═══")
    try:
        aid = application_id if application_id is not None else int(
            _input("Application ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    v = data.view_application(aid)
    if v is None:
        print(f"  ✗ No application #{aid}")
        _pause()
        return
    print(f"\n  Application #{aid}: {v.app.bursary_type}")
    print(f"    Awarded   : {_money(v.app.amount_awarded)}")
    print(f"    Paid      : {_money(v.paid)}")
    print(f"    Remaining : {_money(v.remaining)}")
    try:
        amount = _input(f"Amount ({CURRENCY_SYMBOL})", allow_empty=False)
        paid_on = _input("Paid on", default=_date.today().isoformat(),
                          allow_empty=False)
        method = _pick_from("Method", list(DISBURSEMENT_METHODS),
                              default=DEFAULT_DISBURSEMENT_METHOD)
        status = _pick_from("Status", list(DISBURSEMENT_STATUSES),
                              default=DEFAULT_DISBURSEMENT_STATUS)
        ref = _input("Reference (optional)")
        by = _input("Recorded by (optional)")
        notes = _input("Notes (optional)")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        d = data.add_disbursement(aid, {
            "amount": amount, "paid_on": paid_on, "method": method,
            "status": status, "reference": ref,
            "recorded_by": by, "notes": notes,
        })
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Recorded disbursement #{d.disbursement_id} "
          f"({_money(d.amount)})")
    # Refresh status if auto-rolled.
    after = data.get_application(aid)
    if after and after.status != v.app.status:
        print(f"    Application status updated → {after.status}")
    _pause()


def list_disbursements_flow() -> None:
    print("\n═══ List Disbursements ═══")
    try:
        aid = _input("Application ID (optional)") or None
        sid = _input("Student ID (optional)") or None
        status = _input(
            f"Status ({'/'.join(DISBURSEMENT_STATUSES)})") or None
        df = _input("From (YYYY-MM-DD, optional)") or None
        dt = _input("To (YYYY-MM-DD, optional)") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        rows = data.list_disbursements(
            application_id=int(aid) if aid else None,
            student_id=sid, status=status,
            date_from=df, date_to=dt)
    except (ValidationError, ValueError) as e:
        print(f"  ✗ {e}")
        _pause()
        return
    _print_disbursements(rows)
    _pause()


def edit_disbursement_flow() -> None:
    print("\n═══ Edit Disbursement ═══")
    try:
        did = int(_input("Disbursement ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    existing = data.get_disbursement(did)
    if existing is None:
        print(f"  ✗ No disbursement #{did}")
        _pause()
        return
    try:
        amount = _input(f"Amount ({CURRENCY_SYMBOL})",
                          default=f"{existing.amount:.2f}",
                          allow_empty=False)
        paid_on = _input("Paid on", default=existing.paid_on,
                          allow_empty=False)
        method = _pick_from("Method", list(DISBURSEMENT_METHODS),
                              default=existing.method)
        status = _pick_from("Status", list(DISBURSEMENT_STATUSES),
                              default=existing.status)
        ref = _input("Reference", default=existing.reference or "")
        by = _input("Recorded by", default=existing.recorded_by or "")
        notes = _input("Notes", default=existing.notes or "")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_disbursement(did, {
            "amount": amount, "paid_on": paid_on, "method": method,
            "status": status, "reference": ref,
            "recorded_by": by, "notes": notes,
        })
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Updated disbursement #{did}")
    _pause()


def delete_disbursement_flow() -> None:
    print("\n═══ Delete Disbursement ═══")
    try:
        did = int(_input("Disbursement ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    if data.get_disbursement(did) is None:
        print(f"  ✗ No disbursement #{did}")
        _pause()
        return
    if _input(f"Delete disbursement #{did}? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_disbursement(did):
        print(f"\n  ✓ Deleted #{did}")
    _pause()


# ── Summary ──────────────────────────────────────────────────────

def summary() -> None:
    print("\n═══ Bursary Summary ═══")
    s = data.summary()
    print(f"\n  Total applications  : {s.total_applications}")
    print(f"  Submitted / Awaiting: {s.submitted}")
    print(f"  Under Review        : {s.under_review}")
    print(f"  Approved (active)   : {s.approved_active}")
    print(f"  Paid in Full        : {s.paid_in_full}")
    print(f"  Rejected            : {s.rejected}")
    print(f"  Cancelled/Withdrawn : {s.cancelled_withdrawn}")
    print()
    print(f"  Total requested     : {_money(s.total_requested)}")
    print(f"  Total awarded       : {_money(s.total_awarded)}")
    print(f"  Total paid out      : {_money(s.total_paid)}")
    print(f"  Remaining commitment: {_money(s.total_remaining)}")
    if s.avg_award is not None:
        print(f"  Average award       : {_money(s.avg_award)}")
    print("\n  By type:")
    for t in BURSARY_TYPES:
        n = s.by_type.get(t, 0)
        if n:
            print(f"    {t:<28} : {n}")
    print("\n  By status:")
    for st in STATUSES:
        n = s.by_status.get(st, 0)
        if n:
            print(f"    {st:<18} : {n}")
    if any(s.by_basis.values()):
        print("\n  By eligibility basis:")
        for b in ELIGIBILITY_BASES:
            n = s.by_basis.get(b, 0)
            if n:
                print(f"    {b:<30} : {n}")
    if s.top_recipients:
        print("\n  Top recipients:")
        for sid, name, paid in s.top_recipients:
            print(f"    {sid}  {name[:24]:<24}  {_money(paid)}")
    _pause()


# ── Row-action loop ───────────────────────────────────────────────

def _row_action_loop() -> None:
    print()
    print("  Actions:  V) View   E) Edit   A) Approve   R) Reject   "
          "P) Add disbursement   S) Status   D) Delete   "
          "(Enter to go back)")
    while True:
        try:
            choice = input("  Action: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not choice:
            return
        if choice not in ("v", "e", "a", "r", "p", "s", "d"):
            print("    Pick V, E, A, R, P, S, D, or Enter.")
            continue
        try:
            raw = _input("Application ID", allow_empty=False)
        except _UserAbort:
            return
        try:
            aid = int(raw)
        except ValueError:
            print("    Application ID must be a whole number.")
            continue
        if choice == "v":
            view_application(aid)
        elif choice == "e":
            edit_application(aid)
        elif choice == "a":
            approve_flow(aid)
        elif choice == "r":
            reject_flow(aid)
        elif choice == "p":
            add_disbursement_flow(aid)
        elif choice == "s":
            set_status_flow(aid)
        elif choice == "d":
            delete_application_flow(aid)
        return


# ── Submenu ───────────────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Active Applications",   list_active),
    ("All Applications",      list_all),
    ("Approved Applications", list_approved),
    ("Filter",                filter_applications),
    ("Per-Student",           per_student),
    ("View Application",      view_application),
    ("New Application",       new_application),
    ("Edit Application",      edit_application),
    ("Approve",               approve_flow),
    ("Reject",                reject_flow),
    ("Change Status",         set_status_flow),
    ("Delete Application",    delete_application_flow),
    ("Add Disbursement",      add_disbursement_flow),
    ("List Disbursements",    list_disbursements_flow),
    ("Edit Disbursement",     edit_disbursement_flow),
    ("Delete Disbursement",   delete_disbursement_flow),
    ("Summary",               summary),
]


def run() -> None:
    while True:
        print("\n── Bursary Applications ──")
        for i, (label, _) in enumerate(_MENU, 1):
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
        _, handler = _MENU[int(choice) - 1]
        try:
            handler()
        except _UserAbort:
            print("\n  Cancelled.")
        except Exception as e:
            logger.exception("Bursaries CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Bursary Applications":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Bursaries CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
