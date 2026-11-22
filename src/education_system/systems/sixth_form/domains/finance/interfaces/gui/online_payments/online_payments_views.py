"""Tkinter staff window for Sixth Form Online Payments (FINANCE).

Tabs: Requests (check status, cancel, retry, refund, settle offline,
repair, history), Record Payment (offline payments and payment links),
Reconciliation (provider vs posted, compare with provider), Provider
(set-up state and return address) and Summary.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from education_system.platform.delivery.gui.parented_dialogs import messagebox

from education_system.systems.sixth_form.domains.finance.domain.online_payments import (
    online_payments as data,
)
from education_system.systems.sixth_form.domains.finance.interfaces.gui.online_payments._common import (
    open_link,
    run_in_background,
    warn_errors,
)
from education_system.systems.sixth_form.interfaces.gui.operations._ops_ui import (
    Field,
    SummaryTab,
    TableTab,
    form_dialog,
    make_window,
    option_key,
    student_options,
)

logger = logging.getLogger(__name__)

_TAGS = {
    data.PENDING: ("#fff7e6", "#7a5800"),
    data.PAID: ("#e6f7e6", "#0d6b2a"),
    data.FAILED: ("#ffd1d1", "#8c0d0d"),
    data.CANCELLED: ("#eeeeee", "#444444"),
    data.REFUNDED: ("#e6f0ff", "#1a3f8c"),
    "issue": ("#ffd1d1", "#8c0d0d"),
}

_REQ_COLS = [
    ("ref", "Reference", 115), ("created", "Created", 125),
    ("sid", "Student ID", 85), ("name", "Student", 140),
    ("kind", "Item", 95), ("desc", "Description", 220),
    ("amount", "Amount", 75), ("payer", "Payer", 140),
    ("status", "Status", 80), ("provider", "Provider", 80),
    ("posted", "Posted", 70), ("refunded", "Refunded", 75),
    ("note", "Note", 220)]


def _req_row(r: data.PaymentRequest):
    note = r.failure_reason or ""
    if r.is_offline and r.offline_method:
        note = f"{r.offline_method} {note}".strip()
    return (r.request_id,
            (r.reference, r.created_at[:16], r.student_id, r.student_name,
             r.kind_label, r.description, data.money(r.amount_pence),
             f"{r.payer_kind}: {r.payer_name or r.payer_ref}", r.status,
             r.provider, "Yes" if r.is_posted else
             ("Claimed" if r.posting_state else ""),
             data.money(r.refunded_pence) if r.refunded_pence else "", note),
            (r.status,))


def open_online_payments_window(parent=None) -> None:
    data.init_db()
    win, nb = make_window(parent, "Online Payments")
    tabs: list = []

    def refresh_all(_x=None) -> None:
        for t in tabs:
            t.refresh()

    def busy(on: bool) -> None:
        try:
            win.configure(cursor="watch" if on else "")
        except tk.TclError:
            pass

    def bg(fn, done=None) -> None:
        run_in_background(win, fn, done or (lambda _r: refresh_all()),
                          busy=busy)

    def req_of(tab) -> data.PaymentRequest | None:
        rid = tab.selected()
        return data.get_request(int(rid)) if rid else None

    # ── Requests ──
    def requests_loader(f):
        return [_req_row(r) for r in data.list_requests(
            status=f.get("status"), item_kind=f.get("kind"),
            student_id=f.get("student"), search=f.get("search"),
            date_from=f.get("from"), date_to=f.get("to"))]

    def check(tab):
        r = req_of(tab)
        if r:
            bg(lambda: data.check_status(r.request_id),
               lambda out: (refresh_all(), messagebox.showinfo(
                   "Status", f"{out.reference}: {out.status}"
                   + (f" — {out.failure_reason}" if out.failure_reason
                      and out.status != data.PAID else ""), parent=win)))

    def check_all(_tab):
        def done(c):
            refresh_all()
            messagebox.showinfo(
                "Pending payments",
                f"Checked {c['checked']}: {c['paid']} paid, {c['failed']} "
                f"failed, {c['still_pending']} still pending"
                + (f", {c['errors']} could not be checked" if c["errors"]
                   else "") + ".", parent=win)
        bg(data.check_pending, done)

    def open_checkout(tab):
        r = req_of(tab)
        if not r:
            return
        if r.status != data.PENDING or not r.checkout_url:
            messagebox.showwarning("Payment page",
                                   f"{r.reference} has no open payment page.",
                                   parent=win)
            return
        open_link(win, r.checkout_url)

    def cancel(tab):
        r = req_of(tab)
        if r and messagebox.askyesno("Cancel", f"Cancel {r.reference}?",
                                     parent=win):
            bg(lambda: data.cancel(r.request_id, reason="Cancelled by finance"))

    def retry(tab):
        r = req_of(tab)
        if r:
            bg(lambda: data.retry_checkout(r.request_id),
               lambda out: (refresh_all(), out.checkout_url and messagebox.showinfo(
                   "Payment link", f"New payment page for {out.reference}:\n\n"
                   f"{out.checkout_url}\n\n(copied to the clipboard)",
                   parent=win), _copy(out.checkout_url)))

    def _copy(text: str | None) -> None:
        if text:
            win.clipboard_clear()
            win.clipboard_append(text)

    def refund(tab):
        r = req_of(tab)
        if not r:
            return
        fields = [Field("amount", "Amount (£, blank = all remaining)"),
                  Field("reason", "Reason", required=True)]
        if r.is_offline:
            fields.append(Field("method", "Money given back by", "combo",
                                data.OFFLINE_METHODS, required=True))
        v = form_dialog(win, f"Refund {r.reference}", fields)
        if v and messagebox.askyesno(
                "Refund", f"Refund {v['amount'] or 'the remaining amount'} "
                f"on {r.reference}?"
                + ("" if r.is_offline else "\nThe card will be refunded "
                   "through the provider."), parent=win):
            bg(lambda: data.refund(r.request_id, reason=v["reason"],
                                   amount=v["amount"] or None,
                                   method=v.get("method")))

    def settle_offline(tab):
        r = req_of(tab)
        if not r:
            return
        v = form_dialog(win, f"Settle {r.reference} offline", [
            Field("method", "Method", "combo", data.OFFLINE_METHODS,
                  required=True),
            Field("reference", "Reference (cheque no., bank ref)")])
        if v:
            bg(lambda: data.record_offline_payment(
                r.item_kind, amount=None, method=v["method"],
                reference=v["reference"], request_id=r.request_id))

    def repair(tab):
        r = req_of(tab)
        if r:
            bg(lambda: data.repair(r.request_id))

    def history(tab):
        r = req_of(tab)
        if not r:
            return
        rows = data.events(r.request_id)
        dlg = tk.Toplevel(win)
        dlg.title(f"History — {r.reference}")
        dlg.transient(win)
        ttk.Button(dlg, text="Close", command=dlg.destroy).pack(
            side="bottom", anchor="e", padx=8, pady=8)
        txt = tk.Text(dlg, width=100, height=20, wrap="word")
        txt.pack(fill="both", expand=True, padx=8, pady=8)
        head = (f"{r.reference}  {r.kind_label}  {data.money(r.amount_pence)}"
                f"  {r.status}\nSession: {r.provider_session_id or '-'}\n"
                f"Transaction: {r.provider_txn_id or '-'}\n"
                f"Posted payment: {r.posted_payment_id or '-'}   Receipt: "
                f"{r.receipt_id or '-'}\n\n")
        txt.insert("1.0", head + "\n".join(
            f"{e['at']}  {e['event']:<18} {e['detail'] or ''}  "
            f"[{e['actor'] or ''}]" for e in rows))
        txt.configure(state="disabled")

    def w(fn):
        return lambda tab: warn_errors(win, lambda: fn(tab))

    tabs.append(TableTab(
        nb, "Requests", _REQ_COLS, requests_loader,
        filters=[Field("status", "Status", "combo", data.STATUSES, width=10),
                 Field("kind", "Item", "combo", data.ITEM_KINDS, width=9),
                 Field("student", "Student ID", width=10),
                 Field("search", "Search", width=16),
                 Field("from", "From", width=10),
                 Field("to", "To", width=10)],
        actions=[("Check status", w(check)),
                 ("Check all pending", w(check_all)),
                 ("Open payment page", w(open_checkout)),
                 ("Cancel", w(cancel)), ("Try again", w(retry)),
                 ("Refund", w(refund)),
                 ("Settle offline", w(settle_offline)),
                 ("Repair posting", w(repair)), ("History", w(history))],
        on_double=w(history), tag_colours=_TAGS))

    # ── Record Payment ──
    def payable_loader(f):
        sid = option_key(f.get("student")) or f.get("sid")
        if not sid:
            return []
        out = []
        for i, it in enumerate(data.payable_for_student(sid)):
            out.append((f"{it.item_kind}|{it.target_id or ''}|{it.student_id}",
                        (it.student_id, it.student_name,
                         data.ITEM_KIND_LABELS[it.item_kind], it.description,
                         "any" if it.balance_pence is None
                         else data.money(it.balance_pence),
                         it.due_date, it.pending_reference), ()))
        return out

    def _item_from(tab):
        iid = tab.selected()
        if not iid:
            return None
        kind, target, sid = iid.split("|")
        return kind, (int(target) if target else None), sid

    def offline(tab):
        sel = _item_from(tab)
        if not sel:
            return
        kind, target, sid = sel
        v = form_dialog(win, "Record offline payment", [
            Field("amount", "Amount (£)", required=True),
            Field("method", "Method", "combo", data.OFFLINE_METHODS,
                  required=True),
            Field("reference", "Reference (required unless cash)"),
            Field("payer_name", "Paid by (name)")])
        if v:
            out = data.record_offline_payment(
                kind, amount=v["amount"], method=v["method"],
                target_id=target, student_id=sid, reference=v["reference"],
                payer_name=v["payer_name"])
            messagebox.showinfo("Recorded", f"{out.reference} posted"
                                + (f"; receipt #{out.receipt_id}"
                                   if out.receipt_id else ""), parent=win)
            refresh_all()

    def link(tab):
        sel = _item_from(tab)
        if not sel:
            return
        kind, target, sid = sel
        v = form_dialog(win, "Card payment link for the family", [
            Field("amount", "Amount (£)", required=True)])
        if v:
            bg(lambda: data.start_payment(
                data.PAYER_STAFF, None, kind, amount=v["amount"],
                target_id=target, student_id=sid),
               lambda out: (refresh_all(), _copy(out.checkout_url),
                            messagebox.showinfo(
                                "Payment link",
                                f"{out.reference}: send this link to the family"
                                f" (copied to the clipboard):\n\n"
                                f"{out.checkout_url}\n\nThen use Check status "
                                "once they have paid.", parent=win)))

    tabs.append(TableTab(
        nb, "Record Payment",
        [("sid", "Student ID", 90), ("name", "Student", 160),
         ("kind", "Item", 110), ("desc", "Description", 360),
         ("owed", "Owed", 90), ("due", "Due", 90),
         ("pending", "In progress", 110)],
        payable_loader,
        filters=[Field("student", "Student", "combo", student_options(),
                       width=40)],
        actions=[("Record offline payment", w(offline)),
                 ("Card payment link", w(link))]))

    # ── Reconciliation ──
    def recon_loader(f):
        rows = data.reconciliation(date_from=f.get("from"),
                                   date_to=f.get("to"),
                                   issues_only=bool(f.get("issues")))
        out = []
        for x in rows:
            r = x.request
            out.append((r.request_id,
                        (r.reference, r.created_at[:10], r.student_name,
                         r.kind_label, r.status, r.provider,
                         data.money(r.amount_pence),
                         data.money(r.provider_amount_pence),
                         data.money(x.posted_amount_pence),
                         x.posted_status or "", x.receipt_number or "",
                         "; ".join(x.issues)),
                        ("issue",) if x.issues else (r.status,)))
        return out

    def compare(_tab):
        v = form_dialog(win, "Compare with provider",
                        [Field("days", "Look back (days)", required=True)],
                        {"days": "7"})
        if not v:
            return

        def done(rows):
            if not rows:
                messagebox.showinfo(
                    "Compare with provider",
                    "Every paid checkout at the provider is posted here.",
                    parent=win)
                return
            messagebox.showwarning(
                "Compare with provider",
                f"{len(rows)} paid checkout(s) not posted here:\n\n" + "\n".join(
                    f"{r['reference'] or r['session_id']}  "
                    f"{data.money(r['amount_pence'])}  {r['created_at'] or ''}"
                    f"  — {r['issue']}" for r in rows[:30]), parent=win)
            refresh_all()

        bg(lambda: data.compare_with_provider(int(v["days"] or 7)), done)

    tabs.append(TableTab(
        nb, "Reconciliation",
        [("ref", "Reference", 115), ("date", "Date", 85),
         ("name", "Student", 140), ("kind", "Item", 95),
         ("status", "Status", 80), ("provider", "Provider", 80),
         ("amount", "Requested", 80), ("pamount", "Provider took", 90),
         ("posted", "Posted", 80), ("pstatus", "Posted status", 90),
         ("receipt", "Receipt", 110), ("issues", "Issues", 330)],
        recon_loader,
        filters=[Field("from", "From", width=10), Field("to", "To", width=10),
                 Field("issues", "Issues only", "check")],
        actions=[("Check status", w(check)), ("Repair posting", w(repair)),
                 ("Compare with provider", w(compare)),
                 ("History", w(history))],
        tag_colours=_TAGS))

    # ── Provider ──
    def provider_render():
        st = data.provider_state()
        from education_system.systems.sixth_form.domains.finance.infrastructure.payments import (
            stripe_checkout,
        )
        return [
            "Online payment provider", "",
            f"  Ready:          {'Yes' if st.ready else 'No'}",
            f"  Provider:       {st.provider or '(none configured)'}",
            f"  Mode:           {st.mode or '-'}",
            f"  Return address: {st.return_url or '(not set)'}", "",
            "  " + st.message, "",
            "How to set it up",
            f"  1. Put the Stripe secret key in the environment variable "
            f"{stripe_checkout.ENV_VAR}",
            f"     or in the owner-only file {stripe_checkout.secret_file()}",
            "     (chmod 600). Use a test key (sk_test_…) first.",
            "  2. Set the return address below: the web page the payer sees",
            "     after paying (e.g. the college website's thank-you page).",
            "  3. Parents and students can then pay from their portals;",
            "     use Check status / Check all pending to confirm payments",
            "     (there is no webhook — this desktop app polls the provider).",
        ]

    prov = SummaryTab(nb, provider_render, label="Provider")
    tabs.append(prov)

    def set_return():
        v = form_dialog(win, "Return address", [
            Field("url", "https:// address", required=True, width=60)],
            {"url": data.return_url() or ""})
        if v:
            warn_errors(win, lambda: data.set_return_url(v["url"]))
            prov.refresh()

    bar = prov.frame.winfo_children()[0]
    ttk.Button(bar, text="Set return address…", command=set_return).pack(
        side="left", padx=6)

    def summary_render():
        s = data.summary()
        lines = ["Online payments summary", ""]
        lines += [f"  {k:<12} {v}" for k, v in s.by_status.items()]
        lines += [
            "",
            f"  Taken:          {data.money(s.paid_pence)}",
            f"    by card:      {data.money(s.online_paid_pence)}",
            f"    offline:      {data.money(s.offline_paid_pence)}",
            f"  Refunded:       {data.money(s.refunded_pence)}",
            f"  Pending:        {data.money(s.pending_pence)}", "",
            "  Net by item:"]
        lines += [f"    {data.ITEM_KIND_LABELS[k]:<16} {data.money(v)}"
                  for k, v in s.by_kind_pence.items()]
        lines += ["", f"  Reconciliation issues: {s.issues}"]
        return lines

    tabs.append(SummaryTab(nb, summary_render))
