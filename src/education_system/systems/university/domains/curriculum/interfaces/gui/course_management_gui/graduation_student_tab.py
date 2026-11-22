"""My Graduation: a student's own view of their graduation.

* whether they can graduate yet (and why not), in plain words;
* the name on their certificate (confirm it, or ask for a change — a
  change goes to the graduation office to check);
* their ceremony invitations: reply with named guests, access needs,
  name pronunciation and extra tickets; move to a later ceremony; order a
  gown (before the gown order deadline), pay for it from their student
  finance account and see the receipt; cancel a gown order;
* once conferred: the certificate number and verification code, a
  replacement certificate, sharing the transcript with an employer and the
  HEAR (achievements, save as a file).

Everything goes through ``university/application/graduation/``.
``ctx`` is the hosting window: ``who`` (a student ``Officer``), ``root``,
``auth`` and ``refresh_all()``.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, ttk

from education_system.systems.university.application.graduation import ceremonies as gcer
from education_system.systems.university.application.graduation import conferral as gc
from education_system.systems.university.application.graduation import eligibility as ge
from education_system.systems.university.application.graduation import transcripts as gt
from education_system.systems.university.domains.research.interfaces.gui.research.research_portal import (  # noqa: E501
    common,
)
from education_system.systems.university.domains.research.interfaces.gui.research.research_portal.common import (  # noqa: E501
    Detail,
    Field,
    ask,
    call,
    confirm,
    fill,
    info,
    make_tree,
    nice,
    selected,
)

PLAIN = {"going": "Coming", "not_going": "Not coming", "interested": "Interested",
         "pending": "Not replied yet", None: "Not replied yet"}


def _bar(parent):
    bar = ttk.Frame(parent, padding=(0, 4))
    bar.pack(side="bottom", fill="x")
    return bar


def _button(bar, text, command):
    ttk.Button(bar, text=text, command=command).pack(side="left", padx=3, pady=2)


class StudentTab(ttk.Frame):
    def __init__(self, parent, ctx):
        super().__init__(parent)
        self.ctx = ctx
        self.sid = ctx.who.student_id
        self.report = None
        self.ceremonies = {}
        self.conferral = None
        inner = ttk.Notebook(self)
        inner.pack(fill="both", expand=True, padx=4, pady=4)
        self._build_status(inner)
        self._build_ceremonies(inner)
        self._build_award(inner)
        self._build_hear(inner)

    # ── status and name ──
    def _build_status(self, nb):
        page = ttk.Frame(nb, padding=8)
        nb.add(page, text="  Can I graduate?  ")
        bar = _bar(page)
        _button(bar, "Confirm my certificate name…", self.confirm_name)
        _button(bar, "Refresh", self.refresh)
        self.status_detail = Detail(page)
        self.status_detail.pack(fill="both", expand=True)

    def _show_status(self):
        r = self.report
        if r is None:
            self.status_detail.clear("Your graduation details could not be loaded.")
            return
        award = r["award"] or {}
        if r["conferral"]:
            headline = "Your award has been conferred. Congratulations!"
        elif r["eligible"]:
            headline = "You can graduate."
        else:
            headline = "You can't graduate yet."
        name_note = ("You have confirmed this name." if r["name_confirmed"] else
                     "Please confirm this is how your name should appear. If you ask for a "
                     "change, the graduation office checks it before it is printed.")
        self.status_detail.show(headline, [
            ("Your award", [("Award", award.get("award_name") or
                             "not yet ratified by an assessment board"),
                            ("Classification", award.get("classification"))]),
            ("What is stopping you", [f"• {b}" for b in r["blockers"]] or
             ["Nothing — you are clear to graduate."]),
            ("Good to know (does not stop you)", [f"• {w}" for w in r["warnings"]] or
             ["Nothing to note."]),
            ("Name on your certificate", [("Name", r["certificate_name"]), name_note])])

    def confirm_name(self):
        current = self.report["certificate_name"] if self.report else ""
        values = ask(self, "Name on your certificate", [
            Field("name", "Name exactly as it should be printed", required=True,
                  hint="a change goes to the office")], values={"name": current})
        if values and call(self, ge.confirm_name, self.ctx.who, self.sid, values["name"],
                           write=True) is not None:
            self.refresh()

    # ── ceremonies ──
    def _build_ceremonies(self, nb):
        page = ttk.Frame(nb, padding=4)
        nb.add(page, text="  My ceremonies  ")
        self.cer_bar = _bar(page)
        _button(self.cer_bar, "Reply…", self.reply)
        _button(self.cer_bar, "Move to a later ceremony…", self.transfer)
        _button(self.cer_bar, "Order / change gown…", self.order_gown)
        _button(self.cer_bar, "Pay for gown…", self.pay_gown)
        _button(self.cer_bar, "Cancel gown order…", self.cancel_gown)
        panes = ttk.PanedWindow(page, orient="horizontal")
        panes.pack(fill="both", expand=True)
        left, right = ttk.Frame(panes), ttk.Frame(panes)
        panes.add(left, weight=2)
        panes.add(right, weight=3)
        self.cer_tree = make_tree(left, [("name", "Ceremony", 170), ("date", "Date", 90),
                                         ("venue", "Venue", 120), ("reply", "Your reply", 110)])
        self.cer_tree.bind("<<TreeviewSelect>>", lambda _e: self._show_ceremony())
        self.cer_detail = Detail(right)
        self.cer_detail.pack(fill="both", expand=True)
        self.cer_detail.clear("Select a ceremony.")

    def _show_ceremony(self):
        c = self.ceremonies.get(selected(self.cer_tree) or "")
        if not c:
            return
        req = c["ticket_request"]
        gown = c["gown_order"]
        self.cer_detail.show(c["ceremony_name"], [
            ("When and where", [("Date", c["ceremony_date"]), ("Time", c["ceremony_time"]),
                                ("Venue", c["venue"]), ("Reply by", c.get("rsvp_deadline")),
                                ("Order gown by", c.get("gown_order_deadline"))]),
            ("Your reply", [("Reply", PLAIN.get(c["rsvp_status"], nice(c["rsvp_status"]))),
                            ("Access needs", c.get("access_needs")),
                            ("Pronunciation", c.get("name_pronunciation")),
                            ("Guest allowance", c["allowance"])]),
            ("Guest tickets", [(g["guest_name"], g["ticket_ref"]) for g in c["guests"]] or
             ["No guests named."]),
            ("Extra tickets", [("Asked for", req["requested"]), ("Granted", req["granted"]),
                               ("Status", nice(req["status"]))] if req else ["None asked for."]),
            ("Gown", self._gown_lines(gown, c))])

    @staticmethod
    def _gown_lines(gown, c):
        if not gown:
            closes = c.get("gown_order_deadline") or c["ceremony_date"]
            return [f"No gown order. Order one by {closes} (Order / change gown…)."]
        lines = [("Order", gown["order_id"]), ("Status", nice(gown["status"])),
                 ("Gown size", gown.get("gown_size") or "—"),
                 ("Hat size", gown.get("hat_size") or "—"),
                 ("Hood", gown.get("hood_subject") or "—"),
                 ("Price", f"£{float(gown.get('cost') or 0):.2f}"),
                 ("Payment", nice(gown["payment_status"]))]
        receipt = gcer.gown_receipt(gown)
        if receipt:
            lines.append(receipt)
        elif (gown.get("payment_status") or "unpaid") == "unpaid" and \
                gown.get("status") != "cancelled":
            lines.append("Pay from your student finance account (Pay for gown…) or at the gown "
                         "desk on the day.")
        return lines

    def _selected_ceremony(self):
        c = self.ceremonies.get(selected(self.cer_tree) or "")
        if not c:
            info(self, "Select a ceremony first.")
        return c

    def reply(self):
        c = self._selected_ceremony()
        if not c:
            return
        needs = set((c.get("access_needs") or "").split(","))
        fields = [Field("status", "Your reply", "combo",
                        [("going", "Coming"), ("not_going", "Not coming"),
                         ("interested", "Interested")], required=True),
                  Field("guests", f"Guest names, one per line (up to {c['allowance']})",
                        "multiline"),
                  Field("pronunciation", "How to say your name"),
                  Field("extra", "Extra tickets wanted", "number",
                        hint="only if seats are left")]
        fields += [Field(f"need_{n}", f"Access: {n.replace('_', ' ')}", "check")
                   for n in gcer.ACCESS_NEEDS]
        fields.append(Field("notes", "Anything else we should know", "multiline"))
        values = {"status": c["rsvp_status"] if c["rsvp_status"] in ("going", "not_going",
                                                                       "interested") else
                  "going", "guests": "\n".join(g["guest_name"] for g in c["guests"]),
                  "pronunciation": c.get("name_pronunciation") or ""}
        values.update({f"need_{n}": n in needs for n in gcer.ACCESS_NEEDS})
        result = ask(self, f"Reply: {c['ceremony_name']}", fields, values)
        if not result:
            return
        guests = [g.strip() for g in (result["guests"] or "").splitlines() if g.strip()]
        chosen = [n for n in gcer.ACCESS_NEEDS if result[f"need_{n}"]]
        done = call(self, gcer.record_rsvp, self.ctx.who, c["ceremony_id"], self.sid,
                    result["status"], guests=guests, access_needs=chosen,
                    notes=result["notes"], name_pronunciation=result["pronunciation"],
                    extra_tickets=int(result["extra"] or 0), write=True)
        if done is not None:
            if done["tickets"]:
                info(self, "Guest tickets:\n" + "\n".join(f"{n}: {r}" for n, r in done["tickets"]))
            self.refresh()

    def transfer(self):
        c = self._selected_ceremony()
        if not c:
            return
        later = call(self, gcer.later_ceremonies, c["ceremony_id"]) or []
        if not later:
            info(self, "There is no later ceremony to move to yet.")
            return
        values = ask(self, "Move to a later ceremony", [
            Field("to", "Ceremony", "combo",
                  [(x["ceremony_id"], f"{x['ceremony_name']} — {x['ceremony_date']}")
                   for x in later], required=True),
            Field("reason", "Reason", "multiline")])
        if values and call(self, gcer.transfer, self.ctx.who, c["ceremony_id"], self.sid,
                           int(values["to"]), values["reason"], write=True) is not None:
            self.refresh()

    def order_gown(self):
        c = self._selected_ceremony()
        if not c:
            return
        options = gcer.gown_options()
        fees = options["fees"]
        gown = c["gown_order"] or {}
        values = ask(self, f"Gown for {c['ceremony_name']}", [
            Field("gown_size", f"Gown size (hire £{fees['gown']:.2f})", "combo",
                  options["gown_sizes"], required=True),
            Field("hat_size", f"Hat size (£{fees['hat']:.2f}, optional)", "combo",
                  ["", *options["hat_sizes"]]),
            Field("hood_subject", f"Hood subject (£{fees['hood']:.2f}, optional)",
                  hint="as on your award")],
            values={"gown_size": gown.get("gown_size") or "",
                    "hat_size": gown.get("hat_size") or "",
                    "hood_subject": gown.get("hood_subject") or ""})
        if not values:
            return
        price = gcer.gown_quote(values["gown_size"], values["hood_subject"], values["hat_size"])
        if not confirm(self, f"Order this gown for £{price:.2f}? You can pay now from your "
                             "student finance account or at the gown desk."):
            return
        order = call(self, gcer.order_gown, self.ctx.who, c["ceremony_id"], self.sid,
                     gown_size=values["gown_size"], hat_size=values["hat_size"],
                     hood_subject=values["hood_subject"], write=True)
        if order is None:
            return
        self.refresh()
        if confirm(self, f"Gown ordered (£{float(order['cost']):.2f}). Pay now from your "
                         "student finance account?"):
            self._pay(order)

    def pay_gown(self):
        c = self._selected_ceremony()
        if not c:
            return
        gown = c["gown_order"]
        if not gown or gown.get("status") == "cancelled":
            info(self, "Order a gown first.")
            return
        if (gown.get("payment_status") or "unpaid") != "unpaid":
            info(self, gcer.gown_receipt(gown) or "This order has nothing to pay.")
            return
        if confirm(self, f"Pay £{float(gown.get('cost') or 0):.2f} for your gown from your "
                         "student finance account?"):
            self._pay(gown)

    def _pay(self, order):
        result = call(self, gcer.pay_gown_order, self.ctx.who, order["order_id"],
                      "student_finance_account", write=True)
        if result is None:
            return
        gcer.after_gown_payment(result, self.ctx.who.username)
        left = result.get("balance_remaining")
        info(self, f"Paid £{result['amount']:.2f} (reference {result['reference']})."
                   + (f" Finance account balance now £{left:.2f}." if left is not None else "")
                   + " A receipt has been e-mailed to you.")
        self.refresh()

    def cancel_gown(self):
        c = self._selected_ceremony()
        if not c:
            return
        gown = c["gown_order"]
        if not gown or gown.get("status") == "cancelled":
            info(self, "There is no gown order to cancel.")
            return
        reason = common.ask_text(self, "Cancel gown order",
                                 "Why? (a paid order is refunded by the office)")
        if reason and call(self, gcer.cancel_gown_order, self.ctx.who, gown["order_id"], reason,
                           write=True) is not None:
            self.refresh()

    # ── award, replacement, shares ──
    def _build_award(self, nb):
        page = ttk.Frame(nb, padding=4)
        nb.add(page, text="  My award  ")
        bar = _bar(page)
        _button(bar, "Request a replacement certificate…", self.replacement)
        _button(bar, "Share transcript with an employer…", self.share)
        _button(bar, "Withdraw selected share", self.revoke_share)
        self.award_detail = Detail(page)
        self.award_detail.pack(side="top", fill="x")
        self.award_detail.text.configure(height=9)
        ttk.Label(page, text="Transcript shares").pack(side="top", anchor="w", pady=(6, 0))
        self.shares = make_tree(page, [("employer", "Employer", 170), ("email", "E-mail", 190),
                                       ("expires", "Expires", 90), ("opened", "Opened", 70),
                                       ("state", "State", 90)], height=6)

    def _show_award(self):
        conf = self.conferral
        if not conf:
            self.award_detail.clear("Your award has not been conferred yet.")
            fill(self.shares, [], lambda r: 0, lambda r: ())
            return
        self.award_detail.show(f"{conf['award_name']}", [("", [
            ("Classification", conf["classification"]), ("Conferred", conf["conferral_date"]),
            ("In absentia", "yes" if conf["mode"] == "in_absentia" else "no"),
            ("Status", conf["status"]), ("Certificate number", conf["certificate_number"]),
            ("Verification code", conf["verification_code"]),
            "Employers can check your award with the certificate number or verification code."])])
        rows = call(self, gt.shares, self.ctx.who, self.sid) or []
        fill(self.shares, rows, lambda r: r["token_id"],
             lambda r: (r["employer_name"], r["employer_email"], r["expires_at"],
                        r["access_count"] or 0, "withdrawn" if r["revoked"] else "active"))

    def replacement(self):
        if not self.conferral:
            info(self, "Your award has not been conferred yet.")
            return
        values = ask(self, "Replacement certificate", [
            Field("reason", "Why do you need one?", "multiline", required=True),
            Field("delivery", "Delivery", "combo", ["post", "collect"], required=True),
            Field("address", "Postal address", "multiline")], values={"delivery": "post"})
        if not values or not confirm(self, f"A replacement costs £{gc.REPLACEMENT_FEE:.2f}, "
                                           "added to your account. Your old certificate will "
                                           "stop verifying. Continue?"):
            return
        result = call(self, gc.replace_certificate, self.ctx.who, self.conferral["conferral_id"],
                      values["reason"], delivery=values["delivery"],
                      address=values["address"] or None, write=True)
        if result is not None:
            gc.charge_replacement_fee(result, self.ctx.who.username)
            info(self, f"Your new certificate number is {result['certificate_number']}.")
            self.refresh()

    def share(self):
        if not self.conferral:
            info(self, "Your award has not been conferred yet.")
            return
        values = ask(self, "Share your transcript", [
            Field("employer", "Employer", required=True),
            Field("email", "Their e-mail", required=True),
            Field("purpose", "Purpose", hint="e.g. job application"),
            Field("days", "Link lasts (days)", "number")], values={"days": gt.SHARE_DAYS})
        if not values:
            return
        result = call(self, gt.share, self.ctx.who, self.conferral["conferral_id"],
                      values["employer"], values["email"], values["purpose"],
                      days=int(values["days"] or gt.SHARE_DAYS), write=True)
        if result is not None:
            self._show_link(result)
            self.refresh()

    def _show_link(self, result):
        """The link is shown once; only its fingerprint is stored."""
        win = tk.Toplevel(self)
        win.title("Transcript link")
        win.transient(self.winfo_toplevel())
        ttk.Button(win, text="Close", command=win.destroy).pack(side="bottom", pady=6)
        ttk.Label(win, text=f"We e-mailed this link to the employer. It works until "
                            f"{result['expires_at']}. Copy it now if you need it — it cannot be "
                            "shown again.", wraplength=520, padding=10).pack()
        entry = ttk.Entry(win, width=80)
        entry.insert(0, result["url"])
        entry.configure(state="readonly")
        entry.pack(padx=10, pady=6)

    def revoke_share(self):
        tid = selected(self.shares)
        if tid is None:
            info(self, "Select a share first.")
            return
        if confirm(self, "Withdraw this link? The employer will no longer be able to open it.") \
                and call(self, gt.revoke_share, self.ctx.who, int(tid), write=True) is not None:
            self.refresh()

    # ── HEAR ──
    def _build_hear(self, nb):
        page = ttk.Frame(nb, padding=4)
        nb.add(page, text="  HEAR  ")
        ttk.Label(page, text="Your Higher Education Achievement Report lists your results and "
                             "achievements the university has verified. Add achievements here; "
                             "the office verifies them.", wraplength=900,
                  foreground="#555555").pack(side="top", anchor="w")
        bar = _bar(page)
        _button(bar, "Add achievement…", self.add_achievement)
        _button(bar, "Remove selected", self.remove_achievement)
        _button(bar, "Save HEAR…", self.save_hear)
        self.hear_tree = make_tree(page, [("category", "Category", 140),
                                          ("description", "Achievement", 420),
                                          ("verified", "Verified", 140)])

    def _show_hear(self):
        rows = call(self, gt.achievements, self.ctx.who, self.sid, quiet=True) or []
        fill(self.hear_tree, rows, lambda r: r["achievement_id"],
             lambda r: (r["category"], r["description"], r["verified_at"] or "waiting"))

    def add_achievement(self):
        values = ask(self, "Add an achievement", [
            Field("category", "Category", "combo", list(gt.ACHIEVEMENT_CATEGORIES),
                  required=True),
            Field("description", "Description", "multiline", required=True)])
        if values and call(self, gt.add_achievement, self.ctx.who, self.sid,
                           values["category"], values["description"], write=True) is not None:
            self._show_hear()

    def remove_achievement(self):
        aid = selected(self.hear_tree)
        if aid is None:
            info(self, "Select an achievement first.")
            return
        if call(self, gt.remove_achievement, self.ctx.who, int(aid), write=True) is not None:
            self._show_hear()

    def save_hear(self):
        html = call(self, gt.hear_html, self.ctx.who, self.sid)
        if html is None:
            return
        path = filedialog.asksaveasfilename(parent=self, defaultextension=".html",
                                            initialfile=f"HEAR_{self.sid}.html",
                                            filetypes=[("HTML", "*.html")])
        if path:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(html)
            info(self, f"Saved to {path}")

    # ── everything ──
    def refresh(self):
        self.report = call(self, ge.check, self.sid, quiet=True)
        self._show_status()
        rows = call(self, gcer.my_ceremonies, self.ctx.who, self.sid, quiet=True) or []
        self.ceremonies = {str(r["ceremony_id"]): r for r in rows}
        keep = selected(self.cer_tree)
        fill(self.cer_tree, rows, lambda r: r["ceremony_id"],
             lambda r: (r["ceremony_name"], r["ceremony_date"], r["venue"],
                        PLAIN.get(r["rsvp_status"], nice(r["rsvp_status"]))))
        if keep and keep in self.ceremonies:
            self.cer_tree.selection_set(keep)
        mine = call(self, gc.listing, self.ctx.who, quiet=True) or []
        self.conferral = next((c for c in mine if c["status"] in ("conferred", "suspended")),
                              None)
        self._show_award()
        self._show_hear()


def build_student_tab(notebook, ctx, text="  ⭐ My Graduation  "):
    tab = StudentTab(notebook, ctx)
    notebook.add(tab, text=text)
    tab.refresh()
    return tab
