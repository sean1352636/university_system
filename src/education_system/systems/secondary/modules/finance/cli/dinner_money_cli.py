"""Dinner Money in the terminal (new - the old system had none).

1 Accounts, 2 Pupil statement, 3 Top up, 4 Meal at the till, 5 Meal register,
6 Charge a register, 7 Adjust, 8 Void a line, 9 Refund balance, 10 Write off
debt, 11 Dietary needs, 12 Arrears, 13 Debt letters, 14 Low balances,
15 Low-balance alerts, 16 E-mail a statement, 17 Cash-up, 18 Takings over a
range, 19 Meal prices, 20 Low-balance level, 21 Leavers with a balance,
22 Year end carry-forward, 23 Ledger, 24 History, 25 Export CSV.
Rules live in :mod:`modules.finance.domain.dinner_money`.
"""

from __future__ import annotations

from typing import Any

from education_system.systems.secondary.modules.finance.domain import dinner_money as DM
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.cli.prompts import prompts
from education_system.systems.secondary.ui.cli.prompts.prompts import pause as _pause
from education_system.systems.secondary.ui.cli.prompts.prompts import prompt as _prompt
from education_system.systems.secondary.ui.cli.prompts.prompts import yes as _yes

_ERRORS = (DM.ValidationError, DM.PermissionDenied, DM.NotFound)
_problem = prompts.problem
_pick = prompts.pick
_m = DM.money


def _accounts_table(rows: list[DM.Account]) -> None:
    if not rows:
        print("  (none)")
        return
    print(f"  {'Pupil':<30} {'Yr':<3} {'Form':<5} {'FSM':<4} {'Balance':>9}  Dietary / allergies")
    for a in rows:
        print(f"  {(a.pupil_name + ' (' + a.admission_no + ')')[:30]:<30} {a.year_group:<3} "
              f"{(a.form_group or ''):<5} {'Yes' if a.fsm else '':<4} {_m(a.balance_pence):>9}"
              f"  {a.needs_flag}")


def _ref() -> str:
    return _prompt("  Pupil (ID / admission no.): ")


def _accounts(_p: Principal) -> None:
    year = _prompt("  Year group (blank = all): ")
    rows = DM.accounts(year_group=year or None, search=_prompt("  Search (blank = all): "))
    if _yes("  Overdrawn only?"):
        rows = [a for a in rows if a.balance_pence < 0]
    _accounts_table(rows)


def _statement(_p: Principal) -> None:
    s = DM.statement(_ref(), date_from=_prompt("  From (blank = start): ") or None,
                     date_to=_prompt("  To (blank = today): ") or None)
    print("\n" + "\n".join("  " + line for line in DM.statement_text(s).splitlines()))


def _top_up(principal: Principal) -> None:
    a = DM.account(_ref())
    print(f"  {a.pupil_name}: balance {_m(a.balance_pence)}")
    t = DM.top_up(a.pupil_id, _prompt("  Amount (£): "), actor=principal,
                  method=_pick("Method", DM.METHODS, DM.DEFAULT_METHOD) or DM.DEFAULT_METHOD,
                  day=_prompt("  Date (blank = today): ") or None,
                  reference=_prompt("  Reference (blank ok for cash / card): "),
                  notes=_prompt("  Notes: "))
    print(f"  Top-up #{t.txn_id}. Balance now {_m(DM.balance(a.pupil_id))}.")


def _meal_types() -> list[str]:
    return [p.meal_type for p in DM.list_prices(active_only=True)]


def _till(principal: Principal) -> None:
    a = DM.account(_ref())
    if a.needs_flag:
        print(f"  !! {a.needs_flag}")
    types = _meal_types()
    r = DM.record_meal(a.pupil_id, _pick("Meal", types, types[0] if types else None) or "",
                       actor=principal, day=_prompt("  Date (blank = today): ") or None)
    print(("  Free school meal recorded." if r["fsm"] else f"  Charged {_m(r['price_pence'])}.")
          + f" Balance now {_m(r['balance_pence'])}.")


def _register(principal: Principal) -> None:
    day = _prompt("  Date (blank = today): ") or None
    types = _meal_types()
    meal = _pick("Meal", types, types[0] if types else None) or ""
    form = _prompt("  Form (blank = whole school): ") or None
    rows = DM.register(day, meal, form_group=form)
    for i, r in enumerate(rows, 1):
        print(f"  {i:>3}) {'[x]' if r.had_meal else '[ ]'} {r.pupil_name[:26]:<26} "
              f"{'FSM' if r.fsm else '   '} {_m(r.balance_pence):>8} {r.needs}")
    raw = _prompt("  Numbers who had the meal (comma list; 'all'; blank = keep): ")
    if not raw:
        return
    picked = {r.pupil_id for r in rows} if raw.lower() == "all" else {
        rows[int(x) - 1].pupil_id for x in raw.replace(" ", "").split(",")
        if x.isdigit() and 1 <= int(x) <= len(rows)}
    res = DM.save_register(day, meal, sorted(picked), actor=principal,
                           scope=[r.pupil_id for r in rows])
    print(f"  Added {res['added']}, took off {res['removed']}.")


def _charge(principal: Principal) -> None:
    day = _prompt("  Date (blank = today): ") or None
    meal = _pick("Meal (blank = all)", _meal_types())
    r = DM.charge_register(day, meal or None, actor=principal)
    print(f"  Charged {r['charged']} meal(s), {_m(r['total_pence'])}; {r['fsm']} free school "
          "meal(s) recorded.")


def _adjust(principal: Principal) -> None:
    a = DM.account(_ref())
    DM.adjust(a.pupil_id, _prompt("  Amount (£, -1.20 takes money off): "), actor=principal,
              reason=_prompt("  Why: "))
    print(f"  Balance now {_m(DM.balance(a.pupil_id))}.")


def _void(principal: Principal) -> None:
    tid = prompts.ask_int("  Line (transaction) ID: ")
    if tid:
        t = DM.get_txn(tid)
        print(f"  {t.txn_date} {t.pupil_name} {t.kind} {_m(t.amount_pence)}")
        DM.void(tid, actor=principal, reason=_prompt("  Why: "))
        print("  Voided.")


def _refund(principal: Principal) -> None:
    a = DM.account(_ref())
    print(f"  Balance {_m(a.balance_pence)}")
    DM.refund_balance(a.pupil_id, actor=principal,
                      amount=_prompt("  Amount (£, blank = whole balance): ") or None,
                      method=_pick("Method", DM.METHODS, "Bank transfer") or "Bank transfer",
                      reference=_prompt("  Reference: "), notes=_prompt("  Notes: "))
    print("  Refund recorded.")


def _write_off(principal: Principal) -> None:
    a = DM.account(_ref())
    print(f"  Balance {_m(a.balance_pence)}")
    if _yes("  Write the debt off?"):
        DM.write_off(a.pupil_id, actor=principal, reason=_prompt("  Why: "))
        print("  Written off.")


def _needs(principal: Principal) -> None:
    a = DM.account(_ref())
    cur = DM.get_needs(a.pupil_id)
    vals: dict[str, Any] = {}
    for key, label in (("dietary", "Dietary requirements"), ("allergies", "Allergies"),
                       ("notes", "Notes")):
        v = prompts.ask(label, cur[key])
        vals[key] = cur[key] if v is None else v
    DM.set_needs(a.pupil_id, actor=principal, **vals)
    print("  Saved.")


def _arrears(_p: Principal) -> None:
    _accounts_table(DM.arrears(include_leavers=_yes("  Include leavers?")))


def _deliver(res: dict[str, Any], principal: Principal) -> None:
    from education_system.systems.secondary.modules.communication.domain import email_outbox as E
    if res.get("no_email"):
        print(f"  No e-mail address for {len(res['no_email'])} pupil(s).")
    if res.get("skipped"):
        print(f"  Skipped {len(res['skipped'])} written to in the last week.")
    if not res.get("message_id"):
        return
    print(f"  {res['emails']} e-mail(s) saved.")
    try:
        E.deliver(res["message_id"], principal=principal)
        print("  Sent.")
    except Exception as e:  # noqa: BLE001 - they stay in the outbox
        print(f"  Saved in the outbox; not sent yet ({e}).")


def _ids() -> list[int] | None:
    raw = _prompt("  Pupil IDs (comma list, blank = everyone due one): ")
    return [int(x) for x in raw.replace(" ", "").split(",") if x.isdigit()] or None


def _debt_letters(principal: Principal) -> None:
    _deliver(DM.send_debt_letters(actor=principal, pupil_ids=_ids()), principal)


def _low(_p: Principal) -> None:
    print(f"  Below {_m(DM.low_balance_threshold())} (not FSM):")
    _accounts_table(DM.low_balance())


def _low_alerts(principal: Principal) -> None:
    _deliver(DM.send_low_balance_alerts(actor=principal, pupil_ids=_ids()), principal)


def _email_statement(principal: Principal) -> None:
    _deliver(DM.email_statement(_ref(), actor=principal,
                                date_from=_prompt("  From (blank = start): ") or None,
                                date_to=_prompt("  To (blank = today): ") or None), principal)


def _cash_up(_p: Principal) -> None:
    c = DM.cash_up(_prompt("  Day (blank = today): ") or None)
    print("\n" + "\n".join("  " + line for line in DM.cash_up_text(c).splitlines()))


def _takings(_p: Principal) -> None:
    rows = DM.takings(_prompt("  From: "), _prompt("  To: "))
    for r in rows:
        print(f"  {r['day']}  " + "  ".join(f"{k} {_m(v)}" for k, v in r["by_method"].items())
              + f"  net {_m(r['net_pence'])}  meals {r['meals']}")
    print(f"  Total {_m(sum(r['net_pence'] for r in rows))}")


def _prices(principal: Principal) -> None:
    for p in DM.list_prices():
        print(f"  {p.meal_type:<14} {_m(p.price_pence):>8}  FSM {'yes' if p.fsm_covered else 'no':<3}"
              f"  {'in use' if p.active else 'not in use'}")
    if not _yes("  Set a price?"):
        return
    meal = _pick("Meal type (or type a new one)", DM.MEAL_TYPES, DM.DEFAULT_MEAL) or ""
    cur = DM.get_price(meal)
    DM.set_price(meal, _prompt("  Price (£): "), actor=principal,
                 fsm_covered=_yes("  Covered by free school meals?") if cur or meal != "Lunch"
                 else True, active=not _yes("  Take it out of use?"))
    print("  Saved.")


def _low_level(principal: Principal) -> None:
    print(f"  Now: {_m(DM.low_balance_threshold())}")
    n = DM.set_low_balance_threshold(_prompt("  Alert below (£): "), actor=principal)
    print(f"  Saved: {_m(n)}")


def _leavers(_p: Principal) -> None:
    _accounts_table(DM.leavers_with_balance())


def _year_end(principal: Principal) -> None:
    for r in DM.year_ends():
        print(f"  {r['academic_year']} carried forward on {r['closed_on']} ({r['pupils']})")
    year = _prompt(f"  School year to close [{DM.current_year()}]: ") or DM.current_year()
    if _yes(f"  Carry every balance from {year} into the next year?"):
        r = DM.year_end(year, actor=principal)
        print(f"  Carried {r['pupils']} balance(s): credit {_m(r['credit_pence'])}, debt "
              f"{_m(r['debt_pence'])}. {len(r['leavers'])} leaver(s) hold a balance.")


def _ledger(_p: Principal) -> None:
    ref = _prompt("  Pupil (blank = everyone): ")
    pupil = DM._pupil(ref) if ref else None
    rows = DM.transactions(pupil_id=pupil.pupil_id if pupil else None,
                           date_from=_prompt("  From (blank = any): ") or None,
                           date_to=_prompt("  To (blank = any): ") or None, limit=500)
    for t in rows:
        print(f"  #{t.txn_id:<6} {t.txn_date} {t.pupil_name[:22]:<22} {t.kind:<16} "
              f"{_m(t.amount_pence):>9} {(t.meal_type or t.method or ''):<14}"
              + (" VOID" if t.voided else ""))


def _history(_p: Principal) -> None:
    ref = _prompt("  Pupil (blank = everyone): ")
    pupil = DM._pupil(ref) if ref else None
    for h in DM.history(pupil.pupil_id if pupil else None):
        print(f"  {h['at']}  {h['actor']:<12} {h['action']:<16} "
              + ", ".join(f"{k}={v}" for k, v in h["detail"].items()))


def _export(principal: Principal) -> None:
    kind = _pick("Export", ("balances", "transactions"), "balances") or "balances"
    path = _prompt("  Save CSV to (e.g. meal-balances.csv): ")
    if path:
        print(f"  Exported {DM.export_csv(path, actor=principal, kind=kind)} row(s).")


_OPTIONS = {"1": _accounts, "2": _statement, "3": _top_up, "4": _till, "5": _register,
            "6": _charge, "7": _adjust, "8": _void, "9": _refund, "10": _write_off,
            "11": _needs, "12": _arrears, "13": _debt_letters, "14": _low, "15": _low_alerts,
            "16": _email_statement, "17": _cash_up, "18": _takings, "19": _prices,
            "20": _low_level, "21": _leavers, "22": _year_end, "23": _ledger, "24": _history,
            "25": _export}
_LABELS = ("Accounts", "Pupil statement", "Top up", "Meal at the till", "Meal register",
           "Charge a register", "Adjust", "Void a line", "Refund balance", "Write off debt",
           "Dietary needs", "Arrears", "Debt letters", "Low balances", "Low-balance alerts",
           "E-mail a statement", "Cash-up", "Takings over a range", "Meal prices",
           "Low-balance level", "Leavers with a balance", "Year end carry-forward", "Ledger",
           "History", "Export CSV")


def menu(principal: Principal) -> None:
    while True:
        activity_log.record("dinner_money.view")
        print("\n  ── Dinner Money ──")
        for i, label in enumerate(_LABELS, 1):
            print(f"   {i:>2}) {label}")
        print("    0) Back")
        choice = _prompt("Select: ")
        if choice in ("0", ""):
            return
        fn = _OPTIONS.get(choice)
        if fn is None:
            print("  Invalid selection.")
            continue
        try:
            fn(principal)
        except _ERRORS as e:
            _problem(e)
        _pause()
