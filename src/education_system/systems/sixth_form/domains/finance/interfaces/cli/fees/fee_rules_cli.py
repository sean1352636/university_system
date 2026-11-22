"""CLI for over-19 / international fee rules, learner fee profiles,
remissions, fee calculation and tuition invoices.
Reached from the Fees menu (see ``fees_cli._MENU``)."""

from __future__ import annotations

from education_system.systems.sixth_form.domains.finance.domain import (
    finance_calendar as fc,
)
from education_system.systems.sixth_form.domains.finance.domain.fees import (
    fee_rules as fr,
    fees,
)
from education_system.systems.sixth_form.domains.finance.interfaces.cli import (
    _prompts as ui,
)


def _who() -> str:
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )
    return access.current().username or ui.ask("Your name", required=True)


def _year() -> str:
    return fc.normalise_year(ui.ask("Academic year",
                                    default=fc.normalise_year(None)))


@ui.handler
def profiles() -> None:
    rows = fr.list_profiles()
    ui.table(("Student", "Residency", "Continuing", "EHCP", "Notes", "By"),
             [(p.student_id, p.residency_category[:36],
               "Y" if p.continuing_learner else "N",
               "Y" if p.has_ehcp else "N", (p.notes or "")[:24],
               p.updated_by or "") for p in rows],
             empty="(no fee profiles yet)")


@ui.handler
def set_profile() -> None:
    sid = ui.pick_student()
    cur = fr.get_profile(sid)
    p = fr.set_profile(
        sid,
        residency_category=ui.pick(
            "Residency (check current ESFA funding-eligibility rules)",
            list(fr.RESIDENCY_CATEGORIES),
            default=cur.residency_category if cur else None),
        continuing_learner=ui.yes_no(
            "Continuing a programme started before 19?",
            default=cur.continuing_learner if cur else False),
        has_ehcp=ui.yes_no("Has an EHCP?",
                           default=cur.has_ehcp if cur else False),
        notes=ui.ask("Notes", default=(cur.notes or "") if cur else "")
        or None, by=_who())
    print(f"\n  ✓ Profile saved for {p.student_id}.")


@ui.handler
def rules() -> None:
    rows = fr.list_rules()
    ui.table(("#", "Year", "Residency", "Age band", "Fee status",
              "Annual fee", "Pri", "Active", "Description"),
             [(r.rule_id, r.academic_year or "any",
               (r.residency_category or "any")[:30], r.age_band,
               r.fee_status or "any", ui.money(r.annual_fee), r.priority, "Y" if r.active else "N",
               (r.description or "")[:30]) for r in rows],
             empty="(no fee rules — set the college's fees here)")
    action = ui.pick("Action", ["Add rule", "Edit rule", "Deactivate rule",
                                "Nothing"])
    if action == "Add rule":
        fr.create_rule(_rule_form(None))
        print("\n  ✓ Rule added.")
    elif action == "Edit rule":
        rid = ui.ask_int("Rule #")
        r = fr.get_rule(rid)
        if r is None:
            raise fr.ValidationError(f"No rule #{rid}")
        fr.update_rule(rid, _rule_form(r))
        print("\n  ✓ Updated.")
    elif action == "Deactivate rule":
        fr.deactivate_rule(ui.ask_int("Rule #"))
        print("\n  ✓ Deactivated.")


def _rule_form(r: fr.FeeRule | None) -> dict:
    return {
        "academic_year": ui.ask("Academic year (blank = any)",
                                default=(r.academic_year or "") if r else ""),
        "residency_category": ui.pick(
            "Residency (none = any)", list(fr.RESIDENCY_CATEGORIES),
            default=r.residency_category if r else None, allow_none=True),
        "age_band": ui.pick("Age band (age on 31 August)", list(fr.AGE_BANDS),
                            default=r.age_band if r else None),
        "fee_status": ui.pick(
            "Enrolment fee status (none = any; 19+ co-funded needs its own rule)",
            list(fr.FEE_STATUSES), default=r.fee_status if r else None,
            allow_none=True),
        "annual_fee": ui.ask_money("Annual fee (0 = free)",
                                   default=r.annual_fee if r else None),
        "description": ui.ask("Description",
                              default=(r.description or "") if r else ""),
        "priority": ui.ask_int("Priority (lower wins a tie)",
                               default=r.priority if r else 100),
        "active": ui.yes_no("Active?", default=r.active if r else True),
    }


@ui.handler
def remissions() -> None:
    sid = ui.pick_student()
    rows = fr.list_remissions(student_id=sid)
    ui.table(("#", "Year", "Type", "Value", "Reason", "Approved by", "On"),
             [(m.remission_id, m.academic_year, m.remission_type,
               "" if m.remission_type == "Full"
               else (f"{m.value:g}%" if m.remission_type == "Percentage"
                     else ui.money(m.value)),
               m.reason, m.approved_by, m.approved_on) for m in rows],
             empty="(no remissions)")
    action = ui.pick("Action", ["Add remission / waiver", "Remove remission",
                                "Nothing"])
    if action.startswith("Add"):
        rtype = ui.pick("Type", list(fr.REMISSION_TYPES))
        fr.add_remission({
            "student_id": sid, "academic_year": _year(),
            "remission_type": rtype,
            "value": None if rtype == "Full" else ui.ask_money(
                "Percentage" if rtype == "Percentage" else "Amount"),
            "reason": ui.pick("Reason", list(fr.REMISSION_REASONS)),
            "approved_by": _who(), "notes": ui.ask("Notes") or None,
        })
        print("\n  ✓ Remission recorded.")
    elif action.startswith("Remove"):
        if fr.remove_remission(ui.ask_int("Remission #")):
            print("\n  ✓ Removed.")


@ui.handler
def calculate() -> None:
    calc = fr.calculate_fee(ui.pick_student(), _year())
    print(f"\n  {calc.student_name} ({calc.student_id}) — "
          f"{calc.academic_year}")
    for line in calc.explanation:
        print(f"    {line}")
    print(f"\n  Gross {ui.money(calc.gross_fee)} − remission "
          f"{ui.money(calc.remission_amount)} = {ui.money(calc.net_fee)}")


@ui.handler
def raise_invoice() -> None:
    inv = fr.generate_invoice(ui.pick_student(), _year(), issued_by=_who(),
                              due_date=ui.ask("Due date (blank = default)")
                              or None)
    print(f"\n  ✓ {inv.invoice_number}: {ui.money(inv.net_fee)} "
          f"(gross {ui.money(inv.gross_fee)}, remitted "
          f"{ui.money(inv.remission_amount)}).")


@ui.handler
def raise_all() -> None:
    year = _year()
    if not ui.yes_no(f"Raise {year} invoices for every profiled learner "
                     "who owes a fee?"):
        return
    out = fr.generate_invoices(year, issued_by=_who(),
                               due_date=ui.ask("Due date (blank = default)")
                               or None)
    print(f"\n  ✓ {len(out['raised'])} raised · {len(out['no_fee'])} owe "
          f"nothing · {len(out['skipped'])} skipped")
    for s in out["skipped"]:
        print(f"    - {s}")


def _print_invoices(rows: list[fr.Invoice]) -> None:
    out = []
    for i in rows:
        paid, bal, st = fr.invoice_balance(i)
        out.append((i.invoice_id, i.invoice_number, i.student_id,
                    i.academic_year, i.age_band or "", ui.money(i.net_fee),
                    ui.money(paid), ui.money(bal), st))
    ui.table(("#", "Number", "Student", "Year", "Band", "Net", "Paid",
              "Balance", "Status"), out, empty="(no invoices)")


@ui.handler
def invoices() -> None:
    sid = ui.ask("Student ID (blank = all)") or None
    _print_invoices(fr.list_invoices(student_id=sid,
                                     academic_year=_year()))


@ui.handler
def pay_invoice() -> None:
    iid = ui.ask_int("Invoice #")
    inv = fr.get_invoice(iid)
    if inv is None:
        raise fr.ValidationError(f"No invoice #{iid}")
    _paid, bal, _st = fr.invoice_balance(inv)
    pay, rec = fr.pay_invoice(
        iid, amount=ui.ask_money("Amount", default=bal),
        method=ui.pick("Method", list(fees.PAYMENT_METHODS)),
        recorded_by=_who(), reference=ui.ask("Reference") or None,
        receipt=ui.yes_no("Issue a receipt?", default=True))
    print(f"\n  ✓ Payment #{pay.payment_id} recorded"
          + (f"; receipt {getattr(rec, 'receipt_number', '')}" if rec else
             "") + ".")


@ui.handler
def cancel_invoice() -> None:
    iid = ui.ask_int("Invoice #")
    inv = fr.cancel_invoice(iid, reason=ui.ask("Reason", required=True),
                            by=_who())
    print(f"\n  ✓ {inv.invoice_number} cancelled.")


@ui.handler
def summary() -> None:
    s = fr.summary(_year())
    print(f"\n  Fee profiles : {s.profiles}")
    print(f"  Fee rules    : {s.rules}")
    print(f"  Invoices     : {s.invoices_issued} ({ui.money(s.invoiced_total)})")
    print(f"  Paid         : {ui.money(s.paid_total)}")
    print(f"  Outstanding  : {ui.money(s.outstanding_total)}")
    print(f"  Remitted     : {ui.money(s.remitted_total)}")


def dashboard() -> None:
    from education_system.systems.sixth_form.domains.finance.interfaces.cli.finance_hub import (
        finance_hub_cli,
    )
    finance_hub_cli.show_dashboard()


MENU = [
    ("Fee Profiles (residency, continuing, EHCP)", profiles),
    ("Set Fee Profile", set_profile),
    ("Fee Rules (over-19 / international)", rules),
    ("Remissions & Waivers", remissions),
    ("Calculate a Learner's Fee", calculate),
    ("Raise Tuition Invoice", raise_invoice),
    ("Raise Invoices for Everyone", raise_all),
    ("Tuition Invoices", invoices),
    ("Pay Invoice (with receipt)", pay_invoice),
    ("Cancel Invoice", cancel_invoice),
    ("Tuition Summary", summary),
    ("Finance Dashboard", dashboard),
]


def run() -> None:
    ui.menu("Tuition Fees & Invoices", MENU)
