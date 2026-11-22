"""Budgets in the terminal (new in the rebuild).

Options work on the financial year shown in the heading (Y changes it):
1 Cost centres, 2 Budget lines, 3 New cost centre, 4 Edit cost centre,
5 Delete cost centre, 6 New line, 7 Edit line, 8 Delete line, 9 My budgets,
10 Raise order, 11 Order paid (settle), 12 Cancel order, 13 Orders, 14 Add
spend, 15 Delete spend, 16 Spend, 17 Request virement, 18 Approve / reject
virement, 19 Cancel virement, 20 Virements, 21 Monthly profile, 22 Variance
report, 23 Overspend warnings, 24 Financial years, 25 New year, 26 Close /
reopen year, 27 Roll forward, 28 Settings, 29 History, 30 Export CSV,
31 Export transactions. Rules live in :mod:`modules.finance.domain.budgets`.
"""

from __future__ import annotations

from typing import Any

from education_system.systems.secondary.modules.finance.domain import budgets as B
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.cli.prompts import prompts
from education_system.systems.secondary.ui.cli.prompts.prompts import pause as _pause
from education_system.systems.secondary.ui.cli.prompts.prompts import prompt as _prompt
from education_system.systems.secondary.ui.cli.prompts.prompts import yes as _yes

_ERRORS = (B.ValidationError, B.PermissionDenied, B.NotFound)
_problem = prompts.problem
_int = prompts.ask_int
_pick = prompts.pick
_state: dict[str, Any] = {"year": None}


def _year() -> str:
    y = _state["year"] or B.current_year_label()
    if not y:
        raise B.ValidationError(["No financial year yet - add one (option 25)"])
    return y


def _ask(label: str, cur: Any = None) -> str:
    return _prompt(f"  {label}" + (f" [{cur}]" if cur not in (None, "") else "") + ": ")


def _print_positions(rows: list[B.Position]) -> None:
    if not rows:
        print("  (no budget lines)")
        return
    warn = B.settings()["warn_percent"]
    print(f"  {'Code':<10} {'Cost centre':<16} {'Description':<22} {'Budget':>11} "
          f"{'Committed':>11} {'Spent':>11} {'Remaining':>11} {'Used':>5}")
    for p in rows:
        flag = {"over": " OVER", "warn": " !"}.get(p.state(warn), "")
        print(f"  {p.code[:10]:<10} {p.centre_name[:16]:<16} {p.description[:22]:<22} "
              f"{B.money(p.budget):>11} {B.money(p.committed):>11} {B.money(p.spent):>11} "
              f"{B.money(p.remaining):>11} {p.used_percent:>4}%{flag}")


def _centre(p: Principal) -> B.CostCentre | None:
    rows = B.list_centres(_year(), actor=p)
    for c in rows:
        print(f"  #{c.centre_id:<4} {c.name:<24} {c.kind:<14} {c.holder or '-'}")
    cid = _int("  Cost centre #: ")
    return B.get_centre(cid) if cid else None


def _line(p: Principal, label: str = "Budget line") -> B.Line | None:
    rows = B.list_lines(year=_year(), actor=p)
    if not rows:
        print("  (no budget lines you can use)")
        return None
    v = _pick(label, [f"{ln.code} - {ln.centre_name}: {ln.description}" for ln in rows])
    if not v:
        return None
    code = v.split(" - ", 1)[0]
    hit = next((ln for ln in rows if ln.code.lower() == code.lower()), None)
    if hit is None:
        print("  No such line.")
    return hit


def _warn_ok(line_id: int, amount: str) -> bool:
    problems: list[str] = []
    n = B.to_pence(amount, "Amount", problems)
    if problems or not n or n < 0:
        return True
    warnings = B.check_spend(line_id, n)
    for w in warnings:
        print(f"  ! {w}")
    return not warnings or _yes("  Go ahead?")


# ── Cost centres and lines ───────────────────────────────────────────

def _centres(p: Principal) -> None:
    rows = B.centre_totals(_year(), actor=p)
    if not rows:
        print("  (no cost centres)")
    for t in rows:
        print(f"  #{t['centre_id']:<4} {t['name'][:24]:<24} {t['holder'] or '-':<12} "
              f"budget {B.money(t['budget']):>11}  committed {B.money(t['committed']):>10}  "
              f"spent {B.money(t['spent']):>10}  remaining {B.money(t['remaining']):>11}"
              + ("  OVER" if t["over"] else ""))


def _lines(p: Principal) -> None:
    c = _centre(p)
    _print_positions(B.positions(_year(), centre_id=c.centre_id if c else None, actor=p))


def _centre_data(cur: B.CostCentre | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {}
    v = _ask("Name", cur.name if cur else "")
    if v:
        out["name"] = v
    k = _pick("Type", B.CENTRE_KINDS, cur.kind if cur else B.DEFAULT_KIND)
    if k:
        out["kind"] = k
    v = _ask("Holder (staff username; blank = keep)", cur.holder if cur else "")
    if v:
        out["holder"] = v
    v = _ask("Notes", cur.notes if cur else "")
    if v:
        out["notes"] = v
    if cur is not None:
        a = _ask("Active (y/n)", "y" if cur.active else "n")
        if a:
            out["active"] = 1 if a.lower().startswith("y") else 0
    return out


def _new_centre(p: Principal) -> None:
    c = B.create_centre({**_centre_data(), "year": _year()}, actor=p)
    print(f"  Created cost centre #{c.centre_id} ({c.name}).")


def _edit_centre(p: Principal) -> None:
    c = _centre(p)
    if c:
        B.update_centre(c.centre_id, _centre_data(c), actor=p)
        print("  Saved.")


def _delete_centre(p: Principal) -> None:
    c = _centre(p)
    if c and _yes(f"  Delete {c.name} and its lines?"):
        B.delete_centre(c.centre_id, actor=p)
        print("  Deleted.")


def _line_data(cur: B.Line | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, label, val in (("code", "Code", cur.code if cur else ""),
                            ("description", "Description", cur.description if cur else ""),
                            ("allocation", "Allocation (£)",
                             B.pounds(cur.allocation_pence) if cur else ""),
                            ("notes", "Notes", cur.notes if cur else "")):
        v = _ask(label, val)
        if v:
            out[key] = v
    return out


def _new_line(p: Principal) -> None:
    c = _centre(p)
    if c:
        ln = B.create_line(c.centre_id, _line_data(), actor=p)
        print(f"  Created line {ln.code}.")


def _edit_line(p: Principal) -> None:
    ln = _line(p)
    if ln:
        B.update_line(ln.line_id, _line_data(ln), actor=p)
        print("  Saved.")


def _delete_line(p: Principal) -> None:
    ln = _line(p)
    if ln and _yes(f"  Delete line {ln.code}?"):
        B.delete_line(ln.line_id, actor=p)
        print("  Deleted.")


def _mine(p: Principal) -> None:
    groups = B.my_centres(p, _year())
    if not groups:
        print("  You don't hold a cost centre this year.")
    for g in groups:
        print(f"\n  {g['centre'].name}: budget {B.money(g['budget'])}, remaining "
              f"{B.money(g['remaining'])}")
        _print_positions(g["lines"])


# ── Orders, spend, virements ─────────────────────────────────────────

def _raise_order(p: Principal) -> None:
    ln = _line(p)
    if ln is None:
        return
    data = {k: _prompt(f"  {label}: ") for k, label in (
        ("description", "Description"), ("supplier", "Supplier"), ("order_ref", "Order ref"),
        ("amount", "Amount (£)"), ("raised_on", "Order date (blank = today)"))}
    if _warn_ok(ln.line_id, data["amount"]):
        m = B.add_commitment(ln.line_id, data, actor=p)
        print(f"  Order #{m.commitment_id} raised.")


def _orders(p: Principal, status: str | None = None) -> list[B.Commitment]:
    rows = B.list_commitments(year=_year(), status=status, actor=p)
    for m in rows:
        print(f"  #{m.commitment_id:<4} {m.raised_on} {m.code:<10} {m.description[:28]:<28} "
              f"{(m.supplier or '')[:14]:<14} {B.money(m.amount_pence):>10} {m.status}")
    if not rows:
        print("  (no orders)")
    return rows


def _list_orders(p: Principal) -> None:
    _orders(p, _pick("Status (blank = all)", B.COMMITMENT_STATUSES) or None)


def _settle(p: Principal) -> None:
    if not _orders(p, "Open"):
        return
    mid = _int("  Order #: ")
    if mid:
        s = B.settle_commitment(mid, actor=p,
                                amount=_prompt("  Amount paid £ (blank = order value): "),
                                paid_on=_prompt("  Paid on (blank = today): ") or None,
                                reference=_prompt("  Invoice / reference: ") or None)
        print(f"  Recorded as spend #{s.spend_id}.")


def _cancel_order(p: Principal) -> None:
    if not _orders(p, "Open"):
        return
    mid = _int("  Order #: ")
    if mid and _yes(f"  Cancel order #{mid}?"):
        B.cancel_commitment(mid, actor=p)
        print("  Cancelled.")


def _add_spend(p: Principal) -> None:
    ln = _line(p)
    if ln is None:
        return
    data = {k: _prompt(f"  {label}: ") for k, label in (
        ("description", "Description"), ("supplier", "Supplier"),
        ("reference", "Invoice / reference"), ("amount", "Amount £ (negative = refund)"),
        ("spend_date", "Date (blank = today)"))}
    if _warn_ok(ln.line_id, data["amount"]):
        s = B.add_spend(ln.line_id, data, actor=p)
        print(f"  Spend #{s.spend_id} recorded.")


def _spend(p: Principal) -> None:
    rows = B.list_spend(year=_year(), actor=p)
    for s in rows:
        print(f"  #{s.spend_id:<4} {s.spend_date} {s.code:<10} {s.description[:30]:<30} "
              f"{B.money(s.amount_pence):>10}  {s.source.replace('_', ' ')}")
    if not rows:
        print("  (no spend)")


def _delete_spend(p: Principal) -> None:
    _spend(p)
    sid = _int("  Spend #: ")
    if sid and _yes(f"  Delete spend #{sid}?"):
        B.delete_spend(sid, actor=p)
        print("  Deleted.")


def _request_virement(p: Principal) -> None:
    src = _line(p, "From line")
    if src is None:
        return
    every = B.list_lines(year=_year())
    v = _pick("To line", [f"{ln.code} - {ln.centre_name}: {ln.description}" for ln in every])
    dst = next((ln for ln in every if v and ln.code.lower() == v.split(" - ", 1)[0].lower()),
               None)
    if dst is None:
        print("  No such line.")
        return
    vir = B.request_virement({"from_line_id": src.line_id, "to_line_id": dst.line_id,
                              "amount": _prompt("  Amount (£): "),
                              "reason": _prompt("  Reason: ")}, actor=p)
    print(f"  Virement #{vir.virement_id} asked for - another budget editor decides it.")


def _virements(p: Principal, status: str | None = None) -> list[B.Virement]:
    rows = B.list_virements(_year(), status=status, actor=p)
    for v in rows:
        print(f"  #{v.virement_id:<4} {v.from_code:<10} -> {v.to_code:<10} "
              f"{B.money(v.amount_pence):>10} {v.status:<9} {v.requested_by:<10} {v.reason[:30]}")
    if not rows:
        print("  (no virements)")
    return rows


def _list_virements(p: Principal) -> None:
    _virements(p, _pick("Status (blank = all)", B.VIREMENT_STATUSES) or None)


def _decide(p: Principal) -> None:
    if not _virements(p, "Pending"):
        return
    vid = _int("  Virement #: ")
    if vid:
        dec = _pick("Decision", ("Approved", "Rejected"))
        B.decide_virement(vid, dec or "", actor=p, note=_prompt("  Note: ") or None)
        print("  Recorded.")


def _cancel_virement(p: Principal) -> None:
    if not _virements(p, "Pending"):
        return
    vid = _int("  Virement #: ")
    if vid:
        B.cancel_virement(vid, actor=p)
        print("  Cancelled.")


# ── Profile and reports ──────────────────────────────────────────────

def _profile(p: Principal) -> None:
    ln = _line(p)
    if ln is None:
        return
    ms = B.months(ln.year_label)
    cur = B.profile(ln.line_id)
    for m, v in zip(ms, cur):
        print(f"  {B.month_name(m):<9} {B.money(v):>11}")
    if _yes("  Spread it evenly (clear the profile)?"):
        B.set_profile(ln.line_id, None, actor=p)
    elif _yes("  Enter a new profile?"):
        amounts = [_prompt(f"  {B.month_name(m)} £ [{B.pounds(v)}]: ") or B.pounds(v)
                   for m, v in zip(ms, cur)]
        B.set_profile(ln.line_id, amounts, actor=p)
    else:
        return
    print("  Saved.")


def _variance(p: Principal) -> None:
    scope = _pick("Report for", ("Whole year", "A cost centre", "A line"), "Whole year")
    centre_id = line_id = None
    if scope == "A cost centre":
        c = _centre(p)
        centre_id = c.centre_id if c else None
    elif scope == "A line":
        ln = _line(p)
        line_id = ln.line_id if ln else None
    print(f"\n  {'Month':<9} {'Profiled':>11} {'Actual':>11} {'Variance':>11} "
          f"{'To date':>11} {'Actual':>11} {'Variance':>11}")
    for r in B.variance(_year(), centre_id=centre_id, line_id=line_id, actor=p):
        print(f"  {B.month_name(r['month']):<9} {B.money(r['profiled']):>11} "
              f"{B.money(r['actual']):>11} {B.money(r['variance']):>11} "
              f"{B.money(r['cum_profiled']):>11} {B.money(r['cum_actual']):>11} "
              f"{B.money(r['cum_variance']):>11}")


def _overspends(p: Principal) -> None:
    rows = B.overspends(_year(), actor=p)
    if not rows:
        print("  No lines over budget or past the warning.")
    _print_positions([x for x, _s in rows])


# ── Years and settings ───────────────────────────────────────────────

def _years(_p: Principal) -> None:
    for y in B.list_years():
        print(f"  {y.year_label:<8} {y.start_date} to {y.end_date}  {y.status}")
    if not B.list_years():
        print("  (no financial years)")
    v = _prompt("  Work on year (blank = keep): ")
    if v:
        _state["year"] = B.get_year(v).year_label


def _new_year(p: Principal) -> None:
    y = B.create_year(_prompt("  Calendar year it starts in (blank = this one): ") or None,
                      actor=p)
    _state["year"] = y.year_label
    print(f"  Created {y.year_label} ({y.start_date} to {y.end_date}).")


def _year_status(p: Principal) -> None:
    y = B.get_year(_year())
    st = "Open" if y.status == "Closed" else "Closed"
    if _yes(f"  {'Reopen' if st == 'Open' else 'Close'} {y.year_label}?"):
        B.set_year_status(y.year_label, st, actor=p)
        print(f"  {y.year_label} is {st.lower()}.")


def _roll(p: Principal) -> None:
    r = B.roll_forward(_year(), actor=p,
                       uplift_percent=_prompt("  Uplift allocations by % (blank = 0): ") or 0,
                       include_profiles=_yes("  Copy monthly profiles?"))
    print(f"  {r['year']}: {r['centres']} cost centre(s), {r['lines']} line(s) copied.")
    if r["skipped"]:
        print(f"  Skipped (already there): {', '.join(r['skipped'])}")


def _settings(p: Principal) -> None:
    s = B.settings()
    print(f"  Year starts in month {s['year_start_month']} (4 = April, maintained; 9 = "
          f"September, academy). Warn at {s['warn_percent']}%.")
    changes = {k: v for k, v in (
        ("year_start_month", _prompt("  Start month 1-12 (blank = keep): ")),
        ("warn_percent", _prompt("  Warn at % (blank = keep): "))) if v}
    if changes:
        B.set_settings(changes, actor=p)
        print("  Saved.")


def _history(_p: Principal) -> None:
    for h in B.history(year=_year()):
        print(f"  {h['at']}  {h['actor']:<12} {h['action']:<18} "
              + ", ".join(f"{k}={v}" for k, v in h["detail"].items()))


def _export(p: Principal) -> None:
    path = _prompt("  Save CSV to (e.g. budgets.csv): ")
    if path:
        print(f"  Exported {B.export_csv(path, actor=p, year=_year())} line(s).")


def _export_tx(p: Principal) -> None:
    path = _prompt("  Save CSV to (e.g. budget_transactions.csv): ")
    if path:
        print(f"  Exported {B.export_transactions_csv(path, actor=p, year=_year())} row(s).")


_OPTIONS = {"1": _centres, "2": _lines, "3": _new_centre, "4": _edit_centre,
            "5": _delete_centre, "6": _new_line, "7": _edit_line, "8": _delete_line,
            "9": _mine, "10": _raise_order, "11": _settle, "12": _cancel_order,
            "13": _list_orders, "14": _add_spend, "15": _delete_spend, "16": _spend,
            "17": _request_virement, "18": _decide, "19": _cancel_virement,
            "20": _list_virements, "21": _profile, "22": _variance, "23": _overspends,
            "24": _years, "25": _new_year, "26": _year_status, "27": _roll, "28": _settings,
            "29": _history, "30": _export, "31": _export_tx}


def menu(principal: Principal) -> None:
    while True:
        activity_log.record("budgets.view")
        year = _state["year"] or B.current_year_label() or "(none)"
        print(f"\n  ── Budgets - financial year {year} ──")
        print("    1) Cost centres\n    2) Budget lines\n    3) New cost centre"
              "\n    4) Edit cost centre\n    5) Delete cost centre\n    6) New line"
              "\n    7) Edit line\n    8) Delete line\n    9) My budgets")
        print("   10) Raise order\n   11) Order paid (settle)\n   12) Cancel order\n   13) Orders"
              "\n   14) Add spend\n   15) Delete spend\n   16) Spend")
        print("   17) Request virement\n   18) Approve / reject virement"
              "\n   19) Cancel virement\n   20) Virements")
        print("   21) Monthly profile\n   22) Variance report\n   23) Overspend warnings")
        print("   24) Financial years\n   25) New year\n   26) Close / reopen year"
              "\n   27) Roll forward\n   28) Settings\n   29) History\n   30) Export CSV"
              "\n   31) Export transactions")
        print("    Y) Change year\n    0) Back")
        choice = _prompt("Select: ")
        if choice in ("0", ""):
            return
        fn = _years if choice.lower() == "y" else _OPTIONS.get(choice)
        if fn is None:
            print("  Invalid selection.")
            continue
        try:
            fn(principal)
        except _ERRORS as e:
            _problem(e)
        _pause()


_MINE = {"1": _mine, "2": _raise_order, "3": _list_orders, "4": _cancel_order,
         "5": _request_virement, "6": _list_virements, "7": _cancel_virement, "8": _variance,
         "9": _decide}


def menu_mine(principal: Principal) -> None:
    """A budget holder's own cost centres."""
    while True:
        activity_log.record("budgets.view_mine")
        year = _state["year"] or B.current_year_label() or "(none)"
        print(f"\n  ── My Budgets - financial year {year} ──")
        print("    1) My budgets\n    2) Raise order\n    3) Orders\n    4) Cancel order"
              "\n    5) Request virement\n    6) Virements\n    7) Cancel virement"
              "\n    8) Variance report\n    9) Approve / reject virement")
        print("    Y) Change year\n    0) Back")
        choice = _prompt("Select: ")
        if choice in ("0", ""):
            return
        fn = _years if choice.lower() == "y" else _MINE.get(choice)
        if fn is None:
            print("  Invalid selection.")
            continue
        try:
            fn(principal)
        except _ERRORS as e:
            _problem(e)
        _pause()
