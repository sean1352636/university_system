"""Expense claims in the terminal.

The old menu keeps its numbers: 1 List all, 2 Open, 3 Awaiting payment,
4 Paid, 5 For claimant, 6 Filter, 7 View claim, 8 View lines, 10 New claim,
11 Edit claim, 12 Add line, 13 Edit line, 14 Delete line, 15 Submit, 16 Begin
review, 17 Approve, 18 Reject, 19 Pay, 20 Cancel, 21 Change status, 22 Delete
claim, 24 Summary (9 and 23 were the separators). New, under "More":
25 My claims, 26 Approval queue, 27 Reopen a rejected claim, 28 Payment run
(CSV), 29 Past payment runs, 30 Mileage rate and receipts, 31 Category
limits, 32 Notify claimant, 33 History, 34 Export CSV, 35 Budget codes.
Rules live in :mod:`modules.finance.domain.expense_claims`.
"""

from __future__ import annotations

from typing import Any

from education_system.systems.secondary.modules.finance.domain import budgets as B
from education_system.systems.secondary.modules.finance.domain import expense_claims as X
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.cli.prompts import prompts
from education_system.systems.secondary.ui.cli.prompts.prompts import pause as _pause
from education_system.systems.secondary.ui.cli.prompts.prompts import prompt as _prompt
from education_system.systems.secondary.ui.cli.prompts.prompts import yes as _yes

_ERRORS = (X.ValidationError, X.PermissionDenied, X.NotFound)
_problem = prompts.problem
_int = prompts.ask_int
_pick = prompts.pick


def _print_claims(rows: list[X.Claim]) -> None:
    if not rows:
        print("\n  (none)")
        return
    print(f"\n  {'#':>4}  {'Ref':<14}  {'Claimant':<22}  {'Title':<26}  {'Category':<16}  "
          f"{'Budget':<9}  {'Submitted':<10}  {'Status':<12}  {'Lines':>5}  {'Total':>10}")
    for c in rows:
        print(f"  {c.claim_id:>4}  {c.claim_ref[:14]:<14}  "
              f"{(c.claimant_name or c.claimant_id)[:22]:<22}  {c.title[:26]:<26}  "
              f"{c.category[:16]:<16}  {(c.budget_code or '')[:9]:<9}  "
              f"{c.submitted_on or '':<10}  {c.status:<12}  {c.line_count:>5}  {c.total:>10}")
    print(f"\n  {len(rows)} claim(s).")


def _print_lines(rows: list[X.ClaimLine]) -> None:
    if not rows:
        print("\n  (no lines)")
        return
    print(f"\n  {'#':>4}  {'Incurred':<10}  {'Category':<16}  {'Description':<26}  "
          f"{'Supplier':<14}  {'Qty':>7}  {'Unit':>9}  {'VAT':>8}  {'Gross':>9}  Receipt")
    for ln in rows:
        qty = f"{ln.mileage_miles:g}mi" if ln.mileage_miles is not None else str(ln.quantity)
        unit = f"{ln.mileage_rate_pence}p" if ln.mileage_rate_pence else X.money(ln.unit_pence)
        print(f"  {ln.line_id:>4}  {ln.incurred_on:<10}  {ln.category[:16]:<16}  "
              f"{(ln.description or '')[:26]:<26}  {(ln.supplier or '')[:14]:<14}  {qty:>7}  "
              f"{unit:>9}  {X.money(ln.vat_pence):>8}  {X.money(ln.gross_pence):>9}  "
              f"{ln.receipt_ref or ln.receipt_path or ''}")


def _show(c: X.Claim) -> None:
    print(f"\n    #{c.claim_id}  {c.claim_ref}  - {c.title}")
    for label, v in (("Claimant", f"{c.claimant_type} :: {c.claimant_id}"
                                  + (f" ({c.claimant_name})" if c.claimant_name else "")),
                     ("Department", c.department), ("Category", c.category),
                     ("Budget code", f"{c.budget_code} ({c.centre_name})" if c.budget_code
                      else None), ("Purpose", c.purpose),
                     ("Incurred", f"{c.incurred_from or '-'} to {c.incurred_to or '-'}"),
                     ("Submitted on", c.submitted_on),
                     ("Approved on/by", f"{c.approved_on} / {c.approved_by}"
                      if c.approved_on else None),
                     ("Rejected on", c.rejected_on), ("Rejection reason", c.rejection_reason),
                     ("Paid on", c.paid_on), ("Payment method", c.payment_method),
                     ("Payment ref", c.payment_reference), ("Status", c.status),
                     ("Lines / Total", f"{c.line_count} / {c.total}"),
                     ("Receipts attached", "yes" if c.receipts_attached else "no"),
                     ("Description", c.description), ("Notes", c.notes)):
        if v not in (None, ""):
            print(f"    {label:<17}: {v}")


def _claim(principal: Principal) -> X.Claim | None:
    ref = _prompt("  Claim id or ref: ")
    if not ref:
        return None
    if ref.isdigit():
        return X.get_claim(int(ref), actor=principal)
    c = X.get_claim_by_ref(ref)
    if c is None:
        print("  No matching claim.")
        return None
    return X.get_claim(c.claim_id, actor=principal)


def _ask(label: str, cur: Any = None) -> str:
    return _prompt(f"  {label}" + (f" [{cur}]" if cur not in (None, "") else "") + ": ")


def _budget_code(current: X.Claim | None = None) -> int | None | str:
    """A budget line id from the open codes; '' = keep."""
    codes = B.codes_for_claims()
    if not codes:
        print("  (no budget codes are set up yet - ask the finance office)")
        return ""
    labels = [c["label"] for c in codes]
    v = _pick("Budget code", labels, None)
    if not v:
        return ""
    hit = next((c for c in codes if c["label"] == v or c["code"].lower() == v.lower()), None)
    if hit is None:
        print("  No such budget code - left as it was.")
        return ""
    return hit["line_id"]


def _header(principal: Principal, current: X.Claim | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if X.is_approver(principal):
        for key, label in (("claim_ref", "Claim ref (blank = automatic)"),):
            v = _ask(label, current.claim_ref if current else "")
            if v:
                out[key] = v
        t = _pick("Claimant type", X.CLAIMANT_TYPES,
                  current.claimant_type if current else X.DEFAULT_CLAIMANT_TYPE)
        if t:
            out["claimant_type"] = t
        v = _ask("Claimant id (staff login)", current.claimant_id if current else
                 principal.username)
        if v:
            out["claimant_id"] = v
    for key, label in (("claimant_name", "Claimant name"), ("department", "Department"),
                       ("title", "Title"), ("purpose", "Purpose"),
                       ("incurred_from", "Incurred from (YYYY-MM-DD)"),
                       ("incurred_to", "Incurred to (YYYY-MM-DD)"),
                       ("description", "Description"), ("notes", "Notes")):
        v = _ask(label, getattr(current, key) if current else "")
        if v:
            out[key] = v
    cat = _pick("Category", X.CATEGORIES, current.category if current else X.DEFAULT_CATEGORY)
    if cat:
        out["category"] = cat
    pm = _pick("Payment method", X.PAYMENT_METHODS,
               current.payment_method if current else X.DEFAULT_PAYMENT_METHOD)
    if pm:
        out["payment_method"] = pm
    line = _budget_code(current)
    if line != "":
        out["budget_line_id"] = line
    return out


def _line_data(current: X.ClaimLine | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {}
    cat = _pick("Category", X.CATEGORIES, current.category if current else None)
    if cat:
        out["category"] = cat
    mileage = (cat or (current.category if current else "")) == X.MILEAGE
    fields = [("incurred_on", "Incurred on (YYYY-MM-DD)"), ("description", "Description"),
              ("supplier", "Supplier"), ("receipt_ref", "Receipt ref"),
              ("receipt_path", "Receipt file path")]
    fields += [("mileage_miles", f"Miles (at {X.mileage_rate()}p a mile)")] if mileage else [
        ("quantity", "Quantity"), ("unit_amount", "Unit amount (£)"),
        ("vat_amount", "VAT amount (£)")]
    fields.append(("notes", "Notes"))
    for key, label in fields:
        cur = None
        if current is not None:
            cur = {"unit_amount": X.pounds(current.unit_pence),
                   "vat_amount": X.pounds(current.vat_pence)}.get(key, getattr(current, key,
                                                                               None))
        v = _ask(label, cur)
        if v:
            out[key] = v
    return out


# ── The old options ──────────────────────────────────────────────────

def _list_all(p: Principal) -> None:
    _print_claims(X.list_claims(actor=p))


def _list_open(p: Principal) -> None:
    _print_claims(X.list_claims(scope="open", actor=p))


def _list_awaiting(p: Principal) -> None:
    _print_claims(X.list_claims(scope="awaiting", actor=p))


def _list_paid(p: Principal) -> None:
    _print_claims(X.list_claims(scope="paid", actor=p))


def _for_claimant(p: Principal) -> None:
    t = _pick("Claimant type", X.CLAIMANT_TYPES, X.DEFAULT_CLAIMANT_TYPE)
    cid = _prompt("  Claimant id: ")
    if cid:
        _print_claims(X.list_claims(claimant_type=t, claimant_id=cid, actor=p))


def _filter(p: Principal) -> None:
    t = _pick("Claimant type (blank = any)", X.CLAIMANT_TYPES)
    cat = _pick("Category (blank = any)", X.CATEGORIES)
    st = _pick("Status (blank = any)", X.CLAIM_STATUSES)
    title = _prompt("  Title contains (blank = any): ")
    _print_claims(X.list_claims(claimant_type=t or None, category=cat or None,
                                status=st or None, title=title or None, actor=p))


def _view(p: Principal) -> None:
    c = _claim(p)
    if c:
        _show(c)
        _print_lines(X.lines_for_claim(c.claim_id))


def _view_lines(p: Principal) -> None:
    c = _claim(p)
    if c:
        _print_lines(X.lines_for_claim(c.claim_id))


def _new(p: Principal) -> None:
    c = X.create_claim(_header(p), actor=p)
    print(f"  Created {c.claim_ref} (draft). Add lines (12), then submit (15).")


def _edit(p: Principal) -> None:
    c = _claim(p)
    if c is None:
        return
    changes = _header(p, c)
    if changes:
        X.update_claim(c.claim_id, changes, actor=p)
        print("  Saved.")


def _add_line(p: Principal) -> None:
    c = _claim(p)
    if c:
        ln = X.add_line(c.claim_id, _line_data(), actor=p)
        print(f"  Added line #{ln.line_id}: {X.money(ln.gross_pence)}.")


def _line(p: Principal) -> X.ClaimLine | None:
    c = _claim(p)
    if c is None:
        return None
    _print_lines(X.lines_for_claim(c.claim_id))
    lid = _int("  Line #: ")
    return X.get_line(lid) if lid else None


def _edit_line(p: Principal) -> None:
    ln = _line(p)
    if ln:
        X.update_line(ln.line_id, _line_data(ln), actor=p)
        print("  Saved.")


def _delete_line(p: Principal) -> None:
    ln = _line(p)
    if ln and _yes(f"  Delete line #{ln.line_id}?"):
        X.delete_line(ln.line_id, actor=p)
        print("  Deleted.")


def _submit(p: Principal) -> None:
    c = _claim(p)
    if c and _yes(f"  Submit {c.claim_ref} ({c.total}) for approval?"):
        X.submit(c.claim_id, actor=p)
        print("  Submitted.")


def _review(p: Principal) -> None:
    c = _claim(p)
    if c:
        X.begin_review(c.claim_id, actor=p)
        print("  Under review.")


def _offer_notice(p: Principal, c: X.Claim) -> None:
    if "notify" in X.allowed_actions(p, c) and _yes("  E-mail the claimant?"):
        _send_notice(p, c)


def _approve(p: Principal) -> None:
    c = _claim(p)
    if c is None:
        return
    for w in X.approval_warnings(c.claim_id):
        print(f"  ! {w}")
    if _yes(f"  Approve {c.claim_ref} for {c.total} (charged to {c.budget_code})?"):
        c = X.approve(c.claim_id, actor=p, note=_prompt("  Note (blank ok): ") or None)
        print("  Approved and posted to the budget.")
        _offer_notice(p, c)


def _reject(p: Principal) -> None:
    c = _claim(p)
    if c:
        c = X.reject(c.claim_id, actor=p, reason=_prompt("  Reason: "))
        print("  Rejected.")
        _offer_notice(p, c)


def _pay(p: Principal) -> None:
    c = _claim(p)
    if c is None:
        return
    method = _pick("Payment method", X.PAYMENT_METHODS, c.payment_method)
    c = X.pay(c.claim_id, actor=p, payment_reference=_prompt("  Payment reference: "),
              paid_on=_prompt("  Paid on (blank = today): ") or None, payment_method=method)
    print("  Paid.")
    _offer_notice(p, c)


def _cancel(p: Principal) -> None:
    c = _claim(p)
    if c and _yes(f"  Cancel {c.claim_ref}?"):
        X.cancel(c.claim_id, actor=p, reason=_prompt("  Why (blank ok): ") or None)
        print("  Cancelled.")


def _set_status(p: Principal) -> None:
    c = _claim(p)
    if c is None:
        return
    st = _pick("Status", X.CLAIM_STATUSES, c.status)
    reason = _prompt("  Reason / note (Rejected, Cancelled; blank ok): ") \
        if st in ("Rejected", "Cancelled", "Approved") else None
    ref = _prompt("  Payment reference: ") if st == "Paid" else None
    X.set_status(c.claim_id, st or c.status, actor=p, reason=reason or None,
                 payment_reference=ref)
    print("  Status saved.")


def _delete(p: Principal) -> None:
    c = _claim(p)
    if c and _yes(f"  Delete {c.claim_ref} and its lines?"):
        X.delete_claim(c.claim_id, actor=p)
        print("  Deleted.")


def _summary(p: Principal) -> None:
    s = X.summary(actor=p)
    print(f"\n  Total claims       : {s.total_claims}")
    for label, n in (("Drafts", s.drafts), ("Submitted", s.submitted),
                     ("Under review", s.under_review), ("Approved", s.approved),
                     ("Paid", s.paid), ("Rejected", s.rejected), ("Cancelled", s.cancelled),
                     ("Distinct claimants", s.distinct_claimants)):
        print(f"  {label:<19}: {n}")
    print(f"  Total value        : {X.money(s.total_value)}")
    print(f"  Awaiting payment   : {X.money(s.awaiting_payment_value)}")
    print(f"  Paid value         : {X.money(s.paid_value)}")
    for title, data in (("By category", s.by_category), ("By claimant type",
                                                          s.by_claimant_type),
                        ("By status", s.by_status), ("By payment method",
                                                     s.by_payment_method)):
        print(f"\n  {title}:")
        for k, n in sorted(data.items()):
            print(f"    {k:<20}: {n}")


# ── New ──────────────────────────────────────────────────────────────

def _mine(p: Principal) -> None:
    _print_claims(X.my_claims(p))


def _queue(p: Principal) -> None:
    _print_claims(X.approval_queue(p))


def _reopen(p: Principal) -> None:
    c = _claim(p)
    if c:
        X.reopen(c.claim_id, actor=p)
        print("  Back to draft - change it and submit again.")


def _payment_run(p: Principal) -> None:
    rows = X.payable(p)
    _print_claims(rows)
    if not rows:
        return
    ids = _prompt("  Claim ids to pay (comma separated, blank = all listed): ")
    chosen = [int(x) for x in ids.replace(" ", "").split(",") if x.isdigit()] or None
    path = _prompt("  Save the CSV to (e.g. payment_run.csv): ")
    if path and _yes("  Mark these claims paid?"):
        r = X.payment_run(path, actor=p, claim_ids=chosen,
                          paid_on=_prompt("  Paid on (blank = today): ") or None)
        print(f"  Run {r['reference']}: {r['claims']} claim(s), {X.money(r['total_pence'])}.")


def _runs(p: Principal) -> None:
    runs = X.list_payment_runs()
    for r in runs:
        print(f"  #{r.run_id:<4} {r.reference:<8} {r.run_date}  {r.claims:>4} claim(s)  "
              f"{X.money(r.total_pence):>12}  {r.file_name or ''}")
    if not runs:
        print("  (no payment runs)")
        return
    rid = _int("  Export a run again - run # (blank = no): ")
    if rid:
        path = _prompt("  Save to: ")
        if path:
            print(f"  Exported {X.export_payment_run(rid, path, actor=p)} claim(s).")


def _settings(p: Principal) -> None:
    s = X.settings()
    print(f"  Mileage rate: {s['mileage_rate_pence']}p a mile (HMRC {X.HMRC_MILEAGE_PENCE}p). "
          f"Receipts needed over {X.money(s['receipt_over_pence'])}.")
    rate = _prompt("  New mileage rate in pence (blank = keep): ")
    over = _prompt("  Receipts needed over £ (blank = keep): ")
    changes = {k: v for k, v in (("mileage_rate_pence", rate), ("receipt_over_pence", over))
               if v}
    if changes:
        X.set_settings(changes, actor=p)
        print("  Saved.")


def _limits(p: Principal) -> None:
    for cat, n in sorted(X.limits().items()):
        print(f"  {cat:<20} {X.money(n)}")
    cat = _pick("Category to set (blank = none)", X.CATEGORIES)
    if cat:
        X.set_limit(cat, _prompt("  Limit per claim £ (blank = no limit): "), actor=p)
        print("  Saved.")


def _send_notice(p: Principal, c: X.Claim) -> None:
    from education_system.systems.secondary.modules.communication.domain import email_outbox as E
    mid = X.notify_claimant(c.claim_id, actor=p)
    if not mid:
        print("  The claimant has no e-mail address.")
        return
    try:
        E.deliver(mid, principal=p)
        print("  Sent.")
    except Exception as e:  # noqa: BLE001 - the notice stays in the outbox
        print(f"  Saved in the outbox; not sent yet ({e}).")


def _notify(p: Principal) -> None:
    c = _claim(p)
    if c:
        _send_notice(p, c)


def _history(p: Principal) -> None:
    c = _claim(p)
    if c:
        for h in X.history(c.claim_id):
            print(f"  {h['at']}  {h['actor']:<12} {h['action']:<12} "
                  + ", ".join(f"{k}={v}" for k, v in h["detail"].items()))


def _export(p: Principal) -> None:
    path = _prompt("  Save CSV to (e.g. expense_claims.csv): ")
    if path:
        print(f"  Exported {X.export_csv(path, actor=p)} claim(s).")


def _codes(_p: Principal) -> None:
    rows = B.codes_for_claims()
    for c in rows:
        print(f"  {c['label']}")
    if not rows:
        print("  (no budget codes are set up)")


_OPTIONS = {"1": _list_all, "2": _list_open, "3": _list_awaiting, "4": _list_paid,
            "5": _for_claimant, "6": _filter, "7": _view, "8": _view_lines, "10": _new,
            "11": _edit, "12": _add_line, "13": _edit_line, "14": _delete_line, "15": _submit,
            "16": _review, "17": _approve, "18": _reject, "19": _pay, "20": _cancel,
            "21": _set_status, "22": _delete, "24": _summary, "25": _mine, "26": _queue,
            "27": _reopen, "28": _payment_run, "29": _runs, "30": _settings, "31": _limits,
            "32": _notify, "33": _history, "34": _export, "35": _codes}


def menu(principal: Principal) -> None:
    while True:
        activity_log.record("expenses.view")
        print("\n  ── Expense Claims ──")
        print("    1) List all\n    2) Open\n    3) Awaiting payment\n    4) Paid"
              "\n    5) For claimant\n    6) Filter\n    7) View claim\n    8) View lines")
        print("      ──────────────────")
        print("   10) New claim\n   11) Edit claim\n   12) Add line\n   13) Edit line"
              "\n   14) Delete line\n   15) Submit\n   16) Begin review\n   17) Approve"
              "\n   18) Reject\n   19) Pay\n   20) Cancel\n   21) Change status"
              "\n   22) Delete claim")
        print("      ──────────────────")
        print("   24) Summary")
        print("  More")
        print("   25) My claims\n   26) Approval queue\n   27) Reopen a rejected claim"
              "\n   28) Payment run (CSV)\n   29) Past payment runs"
              "\n   30) Mileage rate and receipts\n   31) Category limits"
              "\n   32) Notify claimant\n   33) History\n   34) Export CSV\n   35) Budget codes")
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


_MINE = {"1": _mine, "2": _new, "3": _view, "4": _edit, "5": _add_line, "6": _edit_line,
         "7": _delete_line, "8": _submit, "9": _cancel, "10": _reopen, "11": _queue,
         "12": _approve, "13": _reject, "14": _codes}


def menu_mine(principal: Principal) -> None:
    """Every member of staff: their own claims, and claims waiting for them as
    a cost centre holder."""
    while True:
        activity_log.record("expenses.view_mine")
        print("\n  ── My Expense Claims ──")
        print("    1) My claims\n    2) New claim\n    3) View claim\n    4) Edit claim"
              "\n    5) Add line\n    6) Edit line\n    7) Delete line\n    8) Submit"
              "\n    9) Cancel\n   10) Reopen a rejected claim\n   11) Waiting for my approval"
              "\n   12) Approve\n   13) Reject\n   14) Budget codes")
        print("    0) Back")
        choice = _prompt("Select: ")
        if choice in ("0", ""):
            return
        fn = _MINE.get(choice)
        if fn is None:
            print("  Invalid selection.")
            continue
        try:
            fn(principal)
        except _ERRORS as e:
            _problem(e)
        _pause()
