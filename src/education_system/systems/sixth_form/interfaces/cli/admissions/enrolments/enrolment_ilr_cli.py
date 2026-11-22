"""Enrolment CLI: ILR record per enrolment, aim outcomes, the ILR export,
early leavers, the condition of funding and enrolment fees.

Refusals (ValidationError, AccessDenied) are raised to the submenu, which
prints the message; flows that act on several rows show them per row."""

from __future__ import annotations

import logging
from typing import Any

from education_system.systems.sixth_form.domain.admissions.enrolments import enrolments as data
from education_system.systems.sixth_form.domain.admissions.enrolments import funding
from education_system.systems.sixth_form.domain.admissions.enrolments import ilr
from education_system.systems.sixth_form.interfaces.cli.admissions.enrolments._common import (
    _UserAbort,
    _default_academic_year,
    _input,
    _offer_csv,
    _pause,
    _pick_enrolment_for,
    _pick_from,
    _prompt_academic_year,
    _writes_ok,
)

logger = logging.getLogger(__name__)


def _src(value: Any, source: str) -> str:
    shown = "—" if value in (None, "") else value
    return f"{shown}  ({source})" if source and source != "none" else f"{shown}"


def _print_ilr(r: ilr.ILRRecord) -> None:
    print(f"\n  ILR — enrolment #{r.enrolment_id}  {r.student_id}  "
          f"{r.academic_year}  [{r.status}]  started {r.start_date}")
    fm = (f"{r.fund_model} {ilr.FUND_MODELS.get(r.fund_model, '')}"
          if r.fund_model is not None else None)
    for label, value in (
            ("Fee status", _src(r.fee_status, r.fee_status_source)),
            ("Funding model", fm or "—"),
            ("FFI", r.ffi if r.ffi is not None else "—"),
            ("Mode", _src(r.mode, r.mode_source)),
            ("Planned learning hrs", _src(r.plan_learn_hours, r.plan_learn_hours_source)),
            ("Planned EEP hours", _src(r.plan_eep_hours, r.plan_eep_hours_source)),
            ("Total planned hours", r.total_hours),
            ("Funding band", r.funding_band or "—"),
            ("High needs", "Yes" if r.high_needs else "No"),
            ("Funded", "Yes" if r.funded else "No"),
            ("Fee paying", "Yes" if r.fee_paying else "No"),
            ("Days in learning", r.days_in_learning),
            ("Qualifying period", "met" if r.qualifying_met else
             ("NOT met — early leaver" if r.early_leaver else "not yet")),
            ("Destination", r.destination_label or "—"),
            ("Destination start", r.destination_start or "—"),
            ("Destination collected", r.destination_collected or "—"),
            ("Notes", r.notes or "—"),
            ("Updated", f"{r.updated_at or '—'} by {r.updated_by or '—'}")):
        print(f"    {label:<22}: {value}")
    print("\n    Learning deliveries:")
    for a in r.aims:
        out = (f"{a.outcome} {ilr.OUTCOMES.get(a.outcome, '')} ({a.outcome_source})"
               if a.outcome is not None else "—")
        print(f"      aim #{a.aim_id:<5} {a.label[:34]:<34} "
              f"{ilr.COMP_STATUS_LABELS.get(a.comp_status, a.comp_status):<10} "
              f"outcome {out}"
              + (f", grade {a.grade}" if a.grade else "")
              + ("" if a.counted else "  [not counted]")
              + ("  [withdrawn before qualifying]"
                 if a.withdrawn_before_qualifying else ""))
    if not r.aims:
        print("      (no learning aims in this year)")


def view_ilr() -> None:
    print("\n═══ ILR Record ═══")
    try:
        e = _pick_enrolment_for()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if e is None:
        return
    _print_ilr(ilr.get_ilr(e.enrolment_id))
    _pause()


_FIELD_PROMPTS: tuple[tuple[str, str], ...] = (
    ("fee_status", "Fee status"),
    ("fund_model", "Funding model (25 / 35 / 99)"),
    ("mode", "Mode (Full time / Part time)"),
    ("plan_learn_hours", "Planned learning hours"),
    ("plan_eep_hours", "Planned EEP hours"),
    ("destination_type", "Destination type (" + "/".join(ilr.DESTINATIONS) + ")"),
    ("destination_code", "Destination code"),
    ("destination_start", "Destination start (YYYY-MM-DD)"),
    ("destination_collected", "Destination collected on (YYYY-MM-DD)"),
    ("notes", "Notes"),
)


def set_ilr_fields() -> None:
    """Record ILR fields; '-' clears a recorded value (the derived one
    applies again); blank leaves it as it is."""
    print("\n═══ Set ILR Fields ═══")
    if not _writes_ok():
        return
    try:
        e = _pick_enrolment_for()
        if e is None:
            return
        r = ilr.get_ilr(e.enrolment_id)
        _print_ilr(r)
        print("\n  Blank keeps the value, '-' clears a recorded one (the derived "
              "value applies again).")
        changes: dict[str, Any] = {}
        for key, label in _FIELD_PROMPTS:
            if key == "fee_status":
                options = ["(keep)", "(clear)", *ilr.FEE_STATUSES]
                pick = _pick_from(label, options, default="(keep)")
                if pick == "(clear)":
                    changes[key] = None
                elif pick != "(keep)":
                    changes[key] = pick
                continue
            if key == "destination_type":
                for t, codes in ilr.DESTINATIONS.items():
                    print(f"      {t}: " + "; ".join(f"{c} {lb}" for c, lb in codes.items()))
            raw = _input(label)
            if raw == "-":
                changes[key] = None
            elif raw:
                changes[key] = raw
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if not changes:
        print("  No change.")
        _pause()
        return
    out = ilr.set_ilr(e.enrolment_id, changes)
    print("  ✓ ILR fields saved")
    _print_ilr(out)
    _pause()


def _pick_aim(e: data.Enrolment) -> Any:
    r = ilr.get_ilr(e.enrolment_id)
    if not r.aims:
        print("  (no learning aims in this enrolment's year)")
        _pause()
        return None
    labels = [f"#{a.aim_id} {a.label} [{a.status}]"
              + (f" outcome {a.outcome} ({a.outcome_source})" if a.outcome else "")
              for a in r.aims]
    pick = _pick_from("Learning aim", labels)
    aim_id = int(pick.split()[0].lstrip("#"))
    return next(a for a in r.aims if a.aim_id == aim_id)


def set_aim_outcome() -> None:
    print("\n═══ Set Aim Outcome ═══")
    if not _writes_ok():
        return
    try:
        e = _pick_enrolment_for()
        if e is None:
            return
        aim = _pick_aim(e)
        if aim is None:
            return
        outcome = _pick_from("Outcome", [f"{k} — {v}" for k, v in ilr.OUTCOMES.items()])
        ach = _input("Achievement date (YYYY-MM-DD; outcome 1/2 only, optional)") or None
        grade = _input("Grade (optional)") or None
        notes = _input("Notes (optional)") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    o = ilr.set_aim_outcome(aim.aim_id, int(outcome.split(" — ")[0]),
                            achievement_date=ach, grade=grade, notes=notes)
    print(f"  ✓ Aim #{o.aim_id}: {o.outcome} {ilr.OUTCOMES[o.outcome]}"
          + (f", grade {o.grade}" if o.grade else "")
          + (f", achieved {o.achievement_date}" if o.achievement_date else ""))
    _pause()


def clear_aim_outcome() -> None:
    print("\n═══ Clear Aim Outcome ═══")
    if not _writes_ok():
        return
    try:
        e = _pick_enrolment_for()
        if e is None:
            return
        aim = _pick_aim(e)
        if aim is None:
            return
        if not _input(f"Clear the recorded outcome of aim #{aim.aim_id}? (y/n)",
                      default="n").lower().startswith("y"):
            print("  Cancelled.")
            return
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if ilr.clear_aim_outcome(aim.aim_id):
        print(f"  ✓ Outcome cleared for aim #{aim.aim_id} (the derived one applies)")
    else:
        print(f"  No outcome was recorded for aim #{aim.aim_id}.")
    _pause()


def export_ilr() -> None:
    """The ILR Learner + LearningDelivery CSV for a year, written to a path;
    problems are printed, never hidden. The same file as Census ILR →
    ILR export (ilr.export_csv delegates to the census_ilr builder)."""
    print("\n═══ ILR Export ═══")
    try:
        year = _prompt_academic_year(_default_academic_year())
        path = _input("Write to (path; blank = check only, no file)") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        res = ilr.export_csv(year, path=path)
    except (ValueError, PermissionError) as exc:  # ValidationError, AccessDenied
        print(f"  ✗ {exc}")
        _pause()
        return
    print(f"\n  {res.academic_year}: {res.learners} learner(s), "
          f"{res.deliveries} learning deliver(y/ies)"
          + (f" — written to {res.path}" if res.path else " — no file written"))
    if res.problems:
        print(f"\n  ✗ {len(res.problems)} problem(s) to fix before submitting:")
        for p in res.problems[:200]:
            aim = f" aim #{p.aim_id}" if p.aim_id else ""
            print(f"    {p.severity}: {p.student_id} #{p.enrolment_id}{aim} "
                  f"{p.field}: {p.message}")
        if len(res.problems) > 200:
            print(f"    … {len(res.problems) - 200} more")
        _offer_csv(res.problems, "ilr_problems.csv")
    else:
        print("  ✓ No problems found")
    _pause()


def early_leavers_report() -> None:
    print("\n═══ Early Leavers (withdrawn inside the qualifying period) ═══")
    try:
        year = _prompt_academic_year(_default_academic_year())
    except _UserAbort:
        print("\n  Cancelled.")
        return
    rows = ilr.early_leavers(year)
    print(f"\n  {len(rows)} early leaver(s) in {year} — not funded:")
    for r in rows:
        print(f"    #{r.enrolment_id:<5} {r.student_id:<10} {r.student_name[:22]:<22} "
              f"Y{r.year_group} {r.tutor_group or '—':<6} {r.start_date} → "
              f"{r.withdrawal_date or '?'} ({r.days_in_learning} days) "
              f"{data.withdrawal_reason_label(r.withdrawal_reason) or ''}")
        if r.aims_before_qualifying:
            print(f"          aims: {', '.join(r.aims_before_qualifying)}")
    _offer_csv(rows, "early_leavers.csv")
    _pause()


# ── Condition of funding ────────────────────────────────────────────

def _print_cof(p: funding.CofPosition) -> None:
    print(f"\n  Condition of funding — #{p.enrolment_id} {p.student_id} "
          f"{p.academic_year}: {'applies' if p.applies else 'does not apply'}"
          f" ({p.reason})")
    for a in p.areas:
        print(f"    {a.area:<8} {'✓' if a.met else '✗'} best grade "
              f"{a.best_grade or '—'}, needs {a.requirement}"
              + (" (exempt)" if a.exempt else "") + f" — {a.status}")
    print(f"    Compliant: {'Yes' if p.compliant else 'No'}")


def cof_gaps() -> None:
    print("\n═══ Condition of Funding — One Learner ═══")
    try:
        e = _pick_enrolment_for()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if e is None:
        return
    _print_cof(funding.cof_position(e.enrolment_id))
    gaps = funding.condition_of_funding_gaps(e.enrolment_id)
    for g in gaps:
        print(f"    Gap: {g.area} (grade {g.best_grade or '—'}) — {g.status}; "
              f"suggested {g.suggested_type} (allowed: {', '.join(g.allowed_types)})")
    if gaps and data.can_write():
        try:
            if _input("Add the missing English / maths aims now? (y/n)",
                      default="n").lower().startswith("y"):
                _apply_cof(e.enrolment_id, gaps)
                return
        except _UserAbort:
            print("  Cancelled.")
    _pause()


def _apply_cof(enrolment_id: int, gaps: list[funding.CofGap]) -> None:
    types: dict[str, str] = {}
    areas: list[str] = []
    for g in gaps:
        pick = _pick_from(f"{g.area}: qualification", [*g.allowed_types, "(skip)"],
                          default=g.suggested_type)
        if pick != "(skip)":
            types[g.area] = pick
            areas.append(g.area)
    if not areas:
        print("  Nothing chosen.")
        _pause()
        return
    start = _input("Aim start date (blank = the enrolment's start)") or None
    res = funding.apply_condition_of_funding(
        enrolment_id, qualification_types=types, start_date=start, areas=tuple(areas))
    for a in res.created:
        print(f"  ✓ Added aim #{a.aim_id} {a.label}")
    for p in res.problems:
        print(f"  ✗ {p}")
    _pause()


def cof_apply() -> None:
    print("\n═══ Apply Condition of Funding ═══")
    if not _writes_ok():
        return
    try:
        e = _pick_enrolment_for()
        if e is None:
            return
        gaps = funding.condition_of_funding_gaps(e.enrolment_id)
        if not gaps:
            _print_cof(funding.cof_position(e.enrolment_id))
            print("  ✓ No gaps — nothing to add.")
            _pause()
            return
        _apply_cof(e.enrolment_id, gaps)
    except _UserAbort:
        print("\n  Cancelled.")


def cof_year_report() -> None:
    print("\n═══ Condition of Funding — Year Report ═══")
    try:
        year = _prompt_academic_year(_default_academic_year())
        only_gaps = _input("Only learners with gaps? (y/n)", default="y").lower().startswith("y")
        live_only = _input("Live enrolments only? (y/n)", default="y").lower().startswith("y")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    rows = funding.cof_report(year, only_gaps=only_gaps, live_only=live_only)
    print(f"\n  {len(rows)} enrolment(s):")
    for r in rows:
        p = r.position
        print(f"    #{r.enrolment_id:<5} {r.student_id:<10} {r.student_name[:22]:<22} "
              f"Y{r.year_group} {'n/a' if not p.applies else ('✓' if p.compliant else '✗')}"
              + (f"  gaps: {', '.join(r.gaps)}" if r.gaps else ""))
    _offer_csv(rows, "condition_of_funding.csv")
    _pause()


# ── Fees ────────────────────────────────────────────────────────────

def fee_rates_admin() -> None:
    """Fee rates are finance's fee rules (finance / funding): list them
    and add, edit or deactivate one through finance's Fee Rules menu."""
    try:
        funding.require_fee_rules_access("manage fee rules")
    except PermissionError as exc:
        print(f"  ✗ {exc}")
        _pause()
        return
    from education_system.systems.sixth_form.domains.finance.interfaces.cli.fees import (
        fee_rules_cli,
    )
    print("\n═══ Fee Rates (Finance fee rules) ═══")
    print("  Enrolment fees are worked out from finance's fee rules: age on 31 August,")
    print("  residency (the learner's finance fee profile) and the enrolment fee status.")
    fee_rules_cli.rules()


def _print_fee_due(d: funding.FeeDue) -> None:
    print(f"\n  Fee — #{d.enrolment_id} {d.student_id} {d.academic_year}: "
          f"fee status {d.fee_status or '—'} "
          f"({'fee paying' if d.fee_paying else 'not fee paying'})")
    if d.rule:
        print(f"    Fee rule      : #{d.rule.rule_id} £{d.rule.annual_fee:,.2f} "
              f"({d.age_band}, {d.residency_category})")
    print(f"    Gross fee     : £{d.gross_fee:,.2f}")
    print(f"    Remission     : £{d.remission_amount:,.2f}")
    print(f"    Net fee       : £{d.net_fee:,.2f}")
    print(f"    Already raised: £{d.already_raised:,.2f}")
    print(f"    To raise      : £{d.to_raise:,.2f}")
    for line in d.explanation:
        print(f"      • {line}")
    for p in d.problems:
        print(f"      ✗ {p}")


def _print_charges(enrolment_id: int) -> list[Any]:
    charges = funding.list_charges(enrolment_id)
    print("\n    Charges (finance tuition invoices):")
    for c in charges:
        state = ("live" if c.status == "Issued"
                 else f"CANCELLED: {c.cancelled_reason or ''}")
        print(f"      #{c.invoice_id:<5} {c.invoice_number} {c.fee_status or '':<14} "
              f"net £{c.net_fee:,.2f} (gross £{c.gross_fee:,.2f} − "
              f"£{c.remission_amount:,.2f}) issued {c.issued_on} by "
              f"{c.issued_by or '—'} — {state}")
    if not charges:
        print("      (none)")
    return charges


def enrolment_fees() -> None:
    """Fee due for one enrolment, its charges; raise or cancel a charge."""
    print("\n═══ Enrolment Fee ═══")
    try:
        e = _pick_enrolment_for()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if e is None:
        return
    while True:
        _print_fee_due(funding.fee_due(e.enrolment_id))
        charges = _print_charges(e.enrolment_id)
        print("\n  R) Raise the fee   C) Cancel a charge   (Enter to go back)")
        try:
            choice = _input("Action").lower()
            if not choice:
                return
            if choice == "r":
                due = _input("Due date (YYYY-MM-DD; blank = default)") or None
                if _input("Raise it? (y/n)", default="n").lower().startswith("y"):
                    c = funding.raise_fee(e.enrolment_id, due_date=due)
                    print(f"  ✓ Raised invoice {c.invoice_number}: £{c.net_fee:,.2f}")
            elif choice == "c":
                live = [c for c in charges if c.status == "Issued"]
                if not live:
                    print("  No live charge to cancel.")
                    continue
                pick = _pick_from("Charge", [f"#{c.invoice_id} {c.invoice_number} "
                                             f"£{c.net_fee:,.2f}" for c in live])
                reason = _input("Reason (required)", allow_empty=False)
                c = funding.cancel_fee_charge(int(pick.split()[0].lstrip("#")),
                                              reason=reason)
                print(f"  ✓ Invoice {c.invoice_number} cancelled")
            else:
                print("  ✗ Pick R or C.")
        except _UserAbort:
            return
        except (ValueError, PermissionError) as exc:  # refusal shown, stay here
            print(f"  ✗ {exc}")


MENU = [
    ("View ILR record", view_ilr),
    ("Set ILR fields", set_ilr_fields),
    ("Set aim outcome", set_aim_outcome),
    ("Clear aim outcome", clear_aim_outcome),
    ("ILR export (year)", export_ilr),
    ("Early leavers", early_leavers_report),
    ("Condition of funding — one learner", cof_gaps),
    ("Condition of funding — add missing aims", cof_apply),
    ("Condition of funding — year report", cof_year_report),
    ("Fee rates", fee_rates_admin),
    ("Enrolment fee (due / raise / charges / cancel)", enrolment_fees),
]
