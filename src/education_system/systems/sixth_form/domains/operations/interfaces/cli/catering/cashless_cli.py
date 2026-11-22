"""CLI flows for Sixth Form cashless catering and biometric consent."""

from __future__ import annotations

import datetime as _dt
import logging

from education_system.systems.sixth_form.domains.operations.domain.catering import (
    biometric_consent as bio,
)
from education_system.systems.sixth_form.domains.operations.domain.catering import (
    cashless as data,
)
from education_system.systems.sixth_form.interfaces.cli.operations._ops_cli import (
    ask,
    choose,
    pause,
    pick_student,
    run_menu,
    table,
    yes_no,
)

logger = logging.getLogger(__name__)


def _accounts(rows) -> None:
    table(["Student", "Name", "Status", "Account", "Balance", "Low below",
           "PIN", "Card", "Biometric"],
          [(v.student_id, v.student_name, v.student_status, v.account_status,
            data.money(v.balance_pence), data.money(v.threshold_pence),
            "Y" if v.has_pin else "", v.card_number, v.biometric)
           for v in rows])


def _txns(rows) -> None:
    table(["#", "When", "Student", "Type", "Balance", "Sale", "Free meal",
           "Method", "Id by", "Till", "Details"],
          [(t.txn_id, t.at[:16], t.student_id,
            t.txn_type + (" (voided)" if t.voided else ""),
            data.money(t.amount_pence),
            data.money(t.gross_pence) if t.gross_pence else "",
            data.money(t.free_meal_pence) if t.free_meal_pence else "",
            t.method, t.id_method, t.till, t.items or t.note) for t in rows])


# ── Till ────────────────────────────────────────────────────────────

def till_sale() -> None:
    till = ask("Till", default="Till 1")
    method = choose("Identify by", data.ID_METHODS, default=data.ID_CARD)
    if method == data.ID_CARD:
        value = ask("Card number", required=True)
        pin = None
    else:
        value = pick_student()
        pin = ask("PIN", required=True) if method == data.ID_PIN else None
    ident = data.identify(method or data.ID_CARD, value, pin=pin)
    allowance, why = data.free_meal_today(ident.student_id)
    print(f"\n  {ident.student_name} ({ident.student_id}) — balance "
          f"{data.money(data.balance_pence(ident.student_id))}"
          + (f" · {why}" if why else ""))
    amount = ask("Sale total (£)", required=True)
    items = ask("Items")
    use_free = yes_no("Use free meal allowance?", default=True) if allowance \
        else False
    t = data.purchase(ident.student_id, amount, id_method=ident.method,
                      items=items, till=till, use_free_meal=use_free,
                      card_number=ident.card_number)
    print(f"\n  ✓ Charged {data.money(-t.amount_pence)}"
          + (f" (free meal {data.money(t.free_meal_pence)})"
             if t.free_meal_pence else "")
          + f"; balance now {data.money(data.balance_pence(t.student_id))}")
    pause()


def cash_topup() -> None:
    sid = pick_student()
    t = data.cash_topup(sid, ask("Amount (£)", required=True),
                        till=ask("Till / office", default="Office"),
                        note=ask("Note"))
    print(f"\n  ✓ Added {data.money(t.amount_pence)}"
          + (f"; receipt #{t.receipt_id}" if t.receipt_id else ""))
    pause()


def bursary_topup() -> None:
    sid = pick_student()
    awards = data.meal_bursaries(sid)
    label = choose("Meal bursary", [
        f"{a.app.application_id} — {a.app.bursary_type} £{a.remaining:.2f} left"
        for a in awards])
    if label is None:
        raise ValueError("No approved meal bursary with money left")
    t = data.bursary_topup(sid, int(label.split(" — ")[0]),
                           ask("Amount (£)", required=True), note=ask("Note"))
    print(f"\n  ✓ Added {data.money(t.amount_pence)} from bursary")
    pause()


def void_txn() -> None:
    sid = ask("Student id (blank = today's sales)")
    rows = data.list_transactions(student_id=sid or None, limit=30) if sid \
        else data.list_transactions(date_from=_dt.date.today().isoformat(), date_to=_dt.date.today().isoformat())
    _txns(rows)
    tid = ask("Transaction # to void", required=True)
    t = data.void_transaction(int(tid), reason=ask("Reason", required=True))
    print(f"\n  ✓ Voided (reversal #{t.txn_id})")
    pause()


# ── Accounts ────────────────────────────────────────────────────────

def list_accounts() -> None:
    _accounts(data.list_accounts(search=ask("Search") or None,
                                 with_account_only=yes_no(
                                     "Only learners with an account?",
                                     default=True)))
    pause()


def statement() -> None:
    sid = pick_student()
    v = data.account_view(sid)
    print(f"\n  {v.student_name}: balance {data.money(v.balance_pence)}, "
          f"account {v.account_status}, biometric: {v.biometric}"
          + (f", {v.free_meal_today}" if v.free_meal_today else ""))
    _txns(data.list_transactions(student_id=sid, limit=100))
    pause()


def set_pin() -> None:
    sid = pick_student()
    data.set_pin(sid, ask("New PIN (4–6 digits)", required=True))
    print("\n  ✓ PIN set")
    pause()


def low_balance() -> None:
    _accounts(data.low_balance_list())
    pause()


def low_level() -> None:
    sid = pick_student()
    data.set_low_balance(sid, ask("Warn below (£; blank = default)") or None)
    print("\n  ✓ Saved")
    pause()


def refund_balance() -> None:
    sid = pick_student()
    bal = data.balance_pence(sid)
    print(f"  Balance {data.money(bal)}")
    method = choose("Method", data.REFUND_METHODS)
    t = data.refund_balance(sid, method=method or "", reason=ask(
        "Reason", required=True), reference=ask("Reference"),
        close=yes_no("Close the account?"))
    print(f"\n  ✓ {'Refunded ' + data.money(-t.amount_pence) if t else 'Nothing to refund'}")
    pause()


def leavers() -> None:
    rows = data.leavers_with_balance()
    _accounts(rows)
    if rows and yes_no("Refund and close one now?"):
        sid = pick_student()
        method = choose("Method", data.REFUND_METHODS)
        t = data.refund_on_leaving(sid, method=method or "",
                                   reference=ask("Reference"))
        print(f"\n  ✓ {'Refunded ' + data.money(-t.amount_pence) if t else 'Nothing to refund'}"
              "; account closed")
    pause()


def transactions() -> None:
    _txns(data.list_transactions(
        student_id=ask("Student id") or None,
        date_from=ask("From (YYYY-MM-DD)") or None,
        date_to=ask("To (YYYY-MM-DD)") or None,
        txn_type=choose("Type (blank = all)", data.TXN_TYPES,
                        allow_blank=True), limit=500))
    pause()


def till_report() -> None:
    r = data.till_report(ask("Day (YYYY-MM-DD)", default=_dt.date.today().isoformat()))
    print(f"\n  Till report {r.day}")
    print(f"    Sales {r.purchases} = {data.money(r.gross_pence)}; free meals "
          f"{r.free_meals} = {data.money(r.free_meal_pence)}; from balances "
          f"{data.money(r.charged_pence)}")
    print(f"    Cash taken {data.money(r.cash_taken_pence)}; refunds "
          f"{data.money(r.refunds_pence)}; voids {r.voids}")
    for k, v in r.topups_by_method.items():
        print(f"    Top-ups {k:<10} {data.money(v)}")
    for k, v in r.by_id_method.items():
        print(f"    Identified by {k:<13} {v}")
    print(f"    Biometric refusals {bio.refusals_on(r.day)}")
    pause()


def settings_flow() -> None:
    cfg = data.settings()
    for k, v in cfg.items():
        print(f"    {k:<20} {data.money(v) if k.endswith('_pence') else v}")
    print(f"    learner_consent_age  {bio.learner_consent_age()}")
    key = choose("Change (blank = none)",
                 list(cfg) + ["learner_consent_age"], allow_blank=True)
    if key == "learner_consent_age":
        bio.set_learner_consent_age(ask("Age (16/17/18)", required=True))
    elif key:
        data.set_setting(key, ask("New value (money in £)", required=True))
    pause()


# ── Biometric consent ───────────────────────────────────────────────

def bio_status() -> None:
    sid = pick_student()
    s = bio.status_for(sid)
    print(f"\n  Biometric: {'ALLOWED' if s.allowed else 'NOT ALLOWED'} — "
          f"{s.reason} (age {s.age if s.age is not None else 'unknown'})")
    table(["#", "Given by", "Name", "Form", "Signed", "Status"],
          [(c.consent_id, c.given_by, c.given_by_name, c.consent_form,
            c.given_on, c.status) for c in bio.list_consents(student_id=sid)])
    table(["#", "Raised by", "Name", "How", "Date", "Status"],
          [(o.objection_id, o.raised_by, o.raised_by_name, o.how, o.raised_on,
            o.status) for o in bio.list_objections(student_id=sid)])
    pause()


def bio_register() -> None:
    rows = bio.register()
    table(["Student", "Age", "Allowed", "Reason", "Enrolled"],
          [(s.student_id, s.age, "Y" if s.allowed else "", s.reason,
            "Y" if s.enrolled else "") for s in rows
           if s.allowed or s.objections or s.enrolled
           or s.learner_consent or s.parent_consent])
    pause()


def bio_consent() -> None:
    sid = pick_student()
    c = bio.record_consent(
        sid, given_by=choose("Given by", bio.PARTIES) or "",
        given_by_name=ask("Name of person consenting", required=True),
        relationship=ask("Relationship (parent/carer)"),
        consent_form=choose("Written form", bio.CONSENT_FORMS) or "",
        document_ref=ask("Document reference"),
        given_on=ask("Date signed (blank = today)") or None)
    print(f"\n  ✓ Consent #{c.consent_id} recorded; "
          f"{bio.status_for(sid).reason}")
    pause()


def bio_withdraw() -> None:
    sid = pick_student()
    current = bio.list_consents(student_id=sid, current_only=True)
    label = choose("Consent", [f"{c.consent_id} — {c.given_by} "
                               f"{c.given_by_name} {c.given_on}"
                               for c in current])
    if label is None:
        raise ValueError("No current consent")
    bio.withdraw_consent(int(label.split(" — ")[0]),
                         withdrawn_by=choose("Withdrawn by", bio.PARTIES) or "",
                         withdrawn_by_name=ask("Name", required=True),
                         note=ask("Note"))
    s = bio.status_for(sid)
    print(f"\n  ✓ Withdrawn; biometric now: {s.reason}")
    if s.enrolled and not s.allowed:
        print("  ! Their template must now be deleted from the reader.")
    pause()


def bio_object() -> None:
    sid = pick_student()
    bio.record_objection(sid, raised_by=choose("Raised by", bio.PARTIES) or "",
                         raised_by_name=ask("Name", required=True),
                         how=choose("How", bio.OBJECTION_HOW) or "",
                         note=ask("Note"))
    s = bio.status_for(sid)
    print(f"\n  ✓ Objection recorded; biometric now: {s.reason}")
    if s.enrolled:
        print("  ! Their template must now be deleted from the reader.")
    pause()


def bio_lift() -> None:
    sid = pick_student()
    objs = bio.list_objections(student_id=sid, active_only=True)
    label = choose("Objection", [f"{o.objection_id} — {o.raised_by} "
                                 f"{o.raised_by_name} {o.raised_on}"
                                 for o in objs])
    if label is None:
        raise ValueError("No active objection")
    bio.lift_objection(int(label.split(" — ")[0]),
                       note=ask("How they asked for it to be lifted",
                                required=True))
    print("\n  ✓ Lifted")
    pause()


def bio_templates() -> None:
    rows = bio.templates_to_delete()
    table(["Student", "Why"], [(s.student_id, s.reason) for s in rows])
    if rows and yes_no("Confirm one deleted now?"):
        bio.confirm_template_deleted(pick_student(), note=ask("Note"))
        print("  ✓ Recorded")
    pause()


def bio_enrol() -> None:
    bio.enrol_template(pick_student())
    print("\n  ✓ Template enrolment recorded")
    pause()


_MENU = [
    ("Till sale", till_sale),
    ("Cash top-up", cash_topup),
    ("Bursary (meal entitlement) top-up", bursary_topup),
    ("Void a transaction", void_txn),
    ("─" * 6, lambda: None),
    ("Accounts", list_accounts),
    ("Statement", statement),
    ("Set a till PIN", set_pin),
    ("Low-balance list", low_balance),
    ("Set a learner's low-balance level", low_level),
    ("Transactions", transactions),
    ("Refund a balance", refund_balance),
    ("Leavers: refund and close", leavers),
    ("─" * 6, lambda: None),
    ("Biometric status for a learner", bio_status),
    ("Biometric consent register", bio_register),
    ("Record written consent", bio_consent),
    ("Withdraw consent", bio_withdraw),
    ("Record an objection", bio_object),
    ("Lift an objection", bio_lift),
    ("Record template enrolled", bio_enrol),
    ("Templates to delete", bio_templates),
    ("─" * 6, lambda: None),
    ("Till report", till_report),
    ("Settings", settings_flow),
]


def cashless_catering_menu() -> None:
    """Entry point for the main CLI menu."""
    run_menu("Cashless Catering", _MENU)


def dispatch(label: str) -> bool:
    if label != "Cashless Catering":
        return False
    try:
        cashless_catering_menu()
    except Exception as e:
        logger.exception("Cashless Catering CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        pause()
    return True
