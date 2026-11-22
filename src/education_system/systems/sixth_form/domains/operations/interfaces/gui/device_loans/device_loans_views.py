"""Tkinter window: device loans and the IT acceptable-use policy."""

from __future__ import annotations

import datetime as _dt
import logging
from education_system.platform.delivery.gui.parented_dialogs import messagebox, simpledialog

from education_system.systems.sixth_form.domains.operations.domain.device_loans import (
    acceptable_use as aup,
)
from education_system.systems.sixth_form.domains.operations.domain.device_loans import (
    device_loans as data,
)
from education_system.systems.sixth_form.interfaces.gui.operations._ops_ui import (
    Field,
    SummaryTab,
    TableTab,
    form_dialog,
    make_window,
    money,
    option_key,
    option_label,
    staff_options,
    student_options,
)

logger = logging.getLogger(__name__)

_DEVICE_TAGS = {
    "available": ("#e6f7e6", "#0d6b2a"),
    "loan": ("#e6f0ff", "#1a3f8c"),
    "unusable": ("#ffd1d1", "#8c0d0d"),
}
_LOAN_TAGS = {
    "overdue": ("#ffd1d1", "#8c0d0d"),
    "charge": ("#fff7e6", "#7a5800"),
    "closed": ("#eeeeee", "#444444"),
}


def open_device_loans_window(parent=None) -> None:
    data.init_db()
    win, nb = make_window(parent, "Device Loans")
    tabs: list = []

    def refresh_all(_tab=None) -> None:
        for t in tabs:
            t.refresh()

    today = _dt.date.today().isoformat()

    # ── Devices ──
    def devices_loader(f):
        rows = data.list_devices(pool=f.get("pool"),
                                 available_only=bool(f.get("available")),
                                 search=f.get("search"))
        out = []
        for d in rows:
            tag = ("loan" if d.open_loan_id else "available" if d.available
                   else "unusable")
            out.append((d.asset_id,
                        (d.asset_id, d.asset_tag, d.name, d.category,
                         d.serial_number, d.loan_pool, d.condition,
                         d.asset_status, "Yes" if d.loanable else "No",
                         "Yes" if d.includes_charger else "No",
                         d.accessories, d.borrower or "", d.due_on or ""),
                        (tag,)))
        return out

    pool_fields = [
        Field("loan_pool", "Loan pool"),
        Field("includes_charger", "Goes out with a charger", "check"),
        Field("accessories", "Other accessories"),
        Field("default_loan_days", "Usual loan length (days)"),
        Field("notes", "Notes", "text"),
    ]
    pool_defaults = {"loan_pool": data.DEFAULT_POOL, "includes_charger": True,
                     "default_loan_days": data.DEFAULT_LOAN_DAYS}

    def register(tab):
        from education_system.systems.sixth_form.domains.operations.domain.assets import (
            assets as _assets,
        )
        v = form_dialog(win, "Register loan device", [
            Field("asset_tag", "Asset tag", required=True),
            Field("name", "Name", required=True),
            Field("category", "Category", "combo", _assets.CATEGORIES,
                  required=True),
            Field("manufacturer", "Manufacturer"), Field("model", "Model"),
            Field("serial_number", "Serial number"),
            Field("location", "Kept at", required=True),
            Field("condition", "Condition", "combo", data.conditions(),
                  required=True),
            Field("purchase_date", "Purchase date (YYYY-MM-DD)"),
            Field("purchase_cost", "Purchase cost (£)"),
        ] + pool_fields, {**pool_defaults, "category": data.DEFAULT_CATEGORY,
                          "condition": "Good"})
        if v:
            data.register_device(v)
            refresh_all()

    def add_existing(tab):
        options = [option_label(a.asset_id, f"{a.asset_tag} {a.name} "
                                f"({a.category}, {a.status})")
                   for a in data.assets_not_in_pool()]
        if not options:
            messagebox.showinfo("Assets", "Every usable asset is already in "
                                "the pool.", parent=win)
            return
        v = form_dialog(win, "Add asset to the loan pool", [
            Field("asset", "Asset", "combo", options, required=True,
                  width=50)] + pool_fields, pool_defaults)
        if v:
            data.add_to_pool(int(option_key(v.pop("asset"))), v)
            refresh_all()

    def _dev(tab):
        aid = tab.selected()
        return data.get_device(int(aid)) if aid else None

    def edit_device(tab):
        d = _dev(tab)
        if not d:
            return
        v = form_dialog(win, f"Edit {d.label}", [
            Field("name", "Name", required=True),
            Field("serial_number", "Serial number"),
            Field("location", "Kept at", required=True),
            Field("loanable", "Available for loan", "check")] + pool_fields,
            vars(d))
        if v:
            data.update_device(d.asset_id, v)
            refresh_all()

    def issue(tab):
        d = _dev(tab)
        if not d:
            return
        v = form_dialog(win, f"Lend {d.label}", [
            Field("borrower_type", "Borrower is a", "combo",
                  data.BORROWER_TYPES, required=True),
            Field("student", "Student", "combo", [""] + student_options(),
                  width=44),
            Field("staff", "Staff member", "combo", [""] + staff_options(),
                  width=44),
            Field("issued_on", "Issued on (YYYY-MM-DD)"),
            Field("due_on", "Due back (blank = usual length)"),
            Field("condition_out", "Condition out", "combo",
                  data.conditions(), required=True),
            Field("charger_issued", "Charger issued", "check"),
            Field("accessories_issued", "Accessories issued"),
            Field("bursary_application_id",
                  "Bursary application no. (funds it)"),
            Field("bursary_funded", "Bursary funded (no application)",
                  "check"),
            Field("allow_second", "Allow a second device", "check"),
            Field("notes", "Notes", "text"),
        ], {"borrower_type": data.STUDENT, "issued_on": today,
            "condition_out": d.condition,
            "charger_issued": d.includes_charger,
            "accessories_issued": d.accessories})
        if v:
            v["student_id"] = option_key(v.pop("student"))
            v["staff_id"] = option_key(v.pop("staff"))
            ln = data.issue_loan(d.asset_id, v)
            messagebox.showinfo(
                "Lent", f"{ln.device_label} lent to {ln.borrower_name or ln.borrower_id}"
                f" until {ln.due_on} (AUP v{ln.aup_version}).", parent=win)
            refresh_all()

    def repair(tab):
        d = _dev(tab)
        if d and messagebox.askyesno("Repair", f"Send {d.label} for repair?",
                                     parent=win):
            data.send_for_repair(d.asset_id)
            refresh_all()

    def repaired(tab):
        d = _dev(tab)
        if not d:
            return
        note = simpledialog.askstring("Repaired", "What was done?",
                                      parent=win)
        if note is not None:
            data.send_for_repair(d.asset_id, repaired=True, notes=note)
            refresh_all()

    def remove(tab):
        d = _dev(tab)
        if d and messagebox.askyesno(
                "Remove", f"Take {d.label} out of the loan pool? It stays "
                "in the asset register.", parent=win):
            removed = data.remove_from_pool(d.asset_id)
            if not removed:
                messagebox.showinfo("Remove", "It has loan history, so it "
                                    "was marked not available instead.",
                                    parent=win)
            refresh_all()

    def history(tab):
        d = _dev(tab)
        if not d:
            return
        rows = data.device_history(d.asset_id)
        messagebox.showinfo(
            f"History — {d.label}",
            "\n".join(f"#{ln.loan_id} {ln.issued_on} → "
                      f"{ln.returned_on or ln.lost_on or 'out'}  "
                      f"{ln.borrower_name or ln.borrower_id}  {ln.status}"
                      for ln in rows) or "Never lent", parent=win)

    tabs.append(TableTab(
        nb, "Devices",
        [("id", "Asset", 55), ("tag", "Tag", 95), ("name", "Name", 150),
         ("cat", "Category", 85), ("serial", "Serial", 100),
         ("pool", "Pool", 85), ("cond", "Condition", 75),
         ("status", "Asset status", 100), ("loanable", "Loanable", 65),
         ("charger", "Charger", 60), ("acc", "Accessories", 110),
         ("who", "On loan to", 150), ("due", "Due", 85)],
        devices_loader,
        filters=[Field("pool", "Pool", "combo", data.pools(), width=14),
                 Field("search", "Search", width=14),
                 Field("available", "Available only", "check")],
        actions=[("Register device", register),
                 ("Add existing asset", add_existing),
                 ("Edit", edit_device), ("Lend", issue),
                 ("Send for repair", repair), ("Repaired", repaired),
                 ("History", history), ("Remove from pool", remove)],
        on_double=edit_device, tag_colours=_DEVICE_TAGS))

    # ── Loans ──
    def loan_rows(rows):
        out = []
        for ln in rows:
            tag = ("overdue" if ln.is_overdue(today)
                   else "charge" if ln.charge_status == data.CHARGE_DUE
                   else "closed" if not ln.is_open else "")
            out.append((ln.loan_id,
                        (ln.loan_id, ln.device_label, ln.borrower_type,
                         ln.borrower_id, ln.borrower_name, ln.issued_on,
                         ln.due_on, ln.status,
                         ln.returned_on or ln.lost_on or "",
                         ln.condition_out, ln.condition_in or "",
                         ("Yes" if ln.charger_issued else "No")
                         + ("" if ln.charger_returned in (None, True)
                            else " (not back)"),
                         ("Yes" + (f" #{ln.bursary_application_id}"
                                   if ln.bursary_application_id else ""))
                         if ln.bursary_funded else "",
                         money(ln.charge_amount) if ln.charge_amount else "",
                         ln.charge_status if ln.charge_amount else "",
                         ln.aup_version),
                        (tag,) if tag else ()))
        return out

    def loans_loader(f):
        who = (f.get("borrower") or "").strip()
        rows = data.list_loans(
            student_id=who if who and not who.upper().startswith("T")
            else None,
            staff_id=who if who.upper().startswith("T") else None,
            status=f.get("status"), open_only=bool(f.get("open")),
            bursary_only=bool(f.get("bursary")),
            charge_status=f.get("charge"))
        return loan_rows(rows)

    def _loan(tab):
        lid = tab.selected()
        return data.get_loan(int(lid)) if lid else None

    def extend(tab):
        ln = _loan(tab)
        if not ln:
            return
        v = form_dialog(win, f"Extend loan #{ln.loan_id}", [
            Field("due_on", "New due date (YYYY-MM-DD)", required=True),
            Field("reason", "Reason")], {"due_on": ln.due_on})
        if v:
            data.extend_loan(ln.loan_id, v["due_on"], reason=v["reason"])
            refresh_all()

    def book_in(tab):
        ln = _loan(tab)
        if not ln:
            return
        v = form_dialog(win, f"Return {ln.device_label}", [
            Field("returned_on", "Returned on (YYYY-MM-DD)"),
            Field("condition_in", "Condition", "combo", data.conditions(),
                  required=True),
            Field("charger_returned", "Charger back", "check"),
            Field("damage_notes", "Damage (required if Damaged)", "text"),
            Field("charge_amount", "Charge to borrower (£)"),
            Field("notes", "Notes", "text"),
        ], {"returned_on": today, "condition_in": ln.condition_out,
            "charger_returned": ln.charger_issued})
        if v:
            data.return_loan(ln.loan_id, **v)
            refresh_all()

    def lost(tab):
        ln = _loan(tab)
        if not ln:
            return
        v = form_dialog(win, f"Report {ln.device_label} lost", [
            Field("lost_on", "Lost on (YYYY-MM-DD)"),
            Field("charge_amount", "Charge to borrower (£)"),
            Field("notes", "What happened", "text")], {"lost_on": today})
        if v:
            data.report_lost(ln.loan_id, **v)
            refresh_all()

    def found(tab):
        ln = _loan(tab)
        if not ln:
            return
        v = form_dialog(win, f"{ln.device_label} found", [
            Field("returned_on", "Back on (YYYY-MM-DD)"),
            Field("condition_in", "Condition", "combo", data.conditions(),
                  required=True),
            Field("notes", "Notes")], {"returned_on": today,
                                       "condition_in": ln.condition_out})
        if v:
            data.mark_found(ln.loan_id, **v)
            refresh_all()

    def charge_paid(tab):
        ln = _loan(tab)
        if ln:
            data.record_charge_paid(ln.loan_id)
            refresh_all()

    def waive(tab):
        ln = _loan(tab)
        if not ln:
            return
        why = simpledialog.askstring("Waive charge", "Reason:", parent=win)
        if why is not None:
            data.waive_charge(ln.loan_id, why)
            refresh_all()

    def set_charge(tab):
        ln = _loan(tab)
        if not ln:
            return
        v = form_dialog(win, f"Charge for loan #{ln.loan_id}", [
            Field("amount", "Amount (£)", required=True),
            Field("note", "Note")], {"amount": ln.charge_amount or ""})
        if v:
            data.set_charge(ln.loan_id, v["amount"], note=v["note"])
            refresh_all()

    def cancel(tab):
        ln = _loan(tab)
        if ln and messagebox.askyesno(
                "Cancel", "Delete this loan as issued in error?", parent=win):
            data.cancel_loan(ln.loan_id)
            refresh_all()

    loan_cols = [
        ("id", "Loan", 50), ("device", "Device", 150), ("type", "Who", 60),
        ("bid", "ID", 80), ("name", "Borrower", 140),
        ("issued", "Issued", 85), ("due", "Due", 85),
        ("status", "Status", 110), ("back", "Back / lost", 85),
        ("out", "Out", 65), ("in", "In", 65), ("charger", "Charger", 90),
        ("bursary", "Bursary", 70), ("charge", "Charge", 65),
        ("cstat", "Charge status", 85), ("aup", "AUP", 45)]
    loan_actions = [("Extend", extend), ("Return", book_in),
                    ("Report lost", lost), ("Found", found),
                    ("Set charge", set_charge),
                    ("Charge paid", charge_paid), ("Waive charge", waive),
                    ("Cancel (issued in error)", cancel)]
    tabs.append(TableTab(
        nb, "Loans", loan_cols, loans_loader,
        filters=[Field("borrower", "Student / staff ID", width=10),
                 Field("status", "Status", "combo", data.LOAN_STATUSES,
                       width=14),
                 Field("charge", "Charge", "combo", data.CHARGE_STATUSES,
                       width=8),
                 Field("open", "Open only", "check"),
                 Field("bursary", "Bursary funded", "check")],
        actions=loan_actions, tag_colours=_LOAN_TAGS))
    tabs.append(TableTab(
        nb, "Overdue", loan_cols,
        lambda _f: loan_rows(data.overdue_loans()),
        actions=loan_actions, tag_colours=_LOAN_TAGS))

    # ── Acceptable use ──
    def acc_loader(f):
        rows = aup.list_acceptances(
            user_type=f.get("type"), person_id=f.get("person"),
            current_only=bool(f.get("current")),
            include_withdrawn=not f.get("live"))
        return [(a.acceptance_id,
                 (a.acceptance_id, a.user_type, a.person_id, a.person_name,
                  a.version, a.accepted_on, a.method, a.recorded_by,
                  a.withdrawn_on or "", a.withdrawn_reason or ""),
                 ("closed",) if not a.is_live else ())
                for a in rows]

    def setup_policy(tab):
        v = form_dialog(win, "Set up the IT acceptable-use policy", [
            Field("title", "Title", required=True, width=44),
            Field("version", "Version", required=True),
            Field("approved_on", "Approved on (YYYY-MM-DD)"),
            Field("approved_by", "Approved by"),
            Field("owner", "Owner"),
            Field("document_ref", "Where the text is (link / file ref)",
                  width=44),
            Field("summary", "Summary", "text")],
            {"title": "IT Acceptable Use Policy", "version": "1.0",
             "approved_on": today})
        if v:
            aup.create_aup_policy(v)
            refresh_all()

    def choose_policy(tab):
        from education_system.systems.sixth_form.domain.governance.policies import (
            policies as _pol,
        )
        options = [option_label(p.policy_id, f"{p.title} v{p.version} "
                                f"({p.status})")
                   for p in _pol.list_policies()]
        if not options:
            messagebox.showwarning("Policies", "The policy register is "
                                   "empty — use 'Set up AUP'.", parent=win)
            return
        v = form_dialog(win, "Use an existing policy as the IT AUP", [
            Field("policy", "Policy", "combo", options, required=True,
                  width=50)])
        if v:
            aup.set_aup_policy(int(option_key(v["policy"])))
            refresh_all()

    def new_version(tab):
        cur = aup.current_aup()
        v = form_dialog(win, "Publish a new AUP version", [
            Field("version", "New version", required=True),
            Field("revised_on", "Approved on (YYYY-MM-DD)"),
            Field("approved_by", "Approved by"),
            Field("changes", "What changed", "text")],
            {"revised_on": today,
             "version": "" if cur is None else cur.version})
        if v:
            out = aup.publish_version(v)
            messagebox.showinfo("Published", f"Version {out.version} is now "
                                "current — everyone must accept it again "
                                "before their next loan.", parent=win)
            refresh_all()

    def record(tab, preset: tuple[str, str] | None = None):
        cur = aup.current_aup()
        if cur is None:
            messagebox.showwarning("No policy", "Set up the IT acceptable-"
                                   "use policy first.", parent=win)
            return
        v = form_dialog(win, f"Record acceptance of v{cur.version}", [
            Field("user_type", "Person is a", "combo", aup.USER_TYPES,
                  required=True),
            Field("student", "Student", "combo", [""] + student_options(),
                  width=44),
            Field("staff", "Staff member", "combo", [""] + staff_options(),
                  width=44),
            Field("accepted_on", "Accepted on (YYYY-MM-DD)"),
            Field("method", "How", "combo", aup.METHODS, required=True),
            Field("notes", "Notes")],
            {"user_type": preset[0] if preset else aup.STUDENT,
             "accepted_on": today, "method": aup.DEFAULT_METHOD})
        if v:
            pid = option_key(v["student"] if v["user_type"] == aup.STUDENT
                             else v["staff"])
            aup.record_acceptance(v["user_type"], pid,
                                  accepted_on=v["accepted_on"],
                                  method=v["method"], notes=v["notes"])
            refresh_all()

    def withdraw(tab):
        aid = tab.selected()
        if not aid:
            return
        why = simpledialog.askstring("Withdraw acceptance", "Reason:",
                                     parent=win)
        if why is not None:
            aup.withdraw_acceptance(int(aid), why)
            refresh_all()

    def show_versions(tab):
        revs = aup.versions()
        pol = aup.aup_policy()
        messagebox.showinfo(
            "AUP versions",
            (f"{pol.title} (policy #{pol.policy_id}, {pol.status})\n\n"
             if pol else "No policy chosen.\n\n")
            + "\n".join(f"v{r.version}  {r.revised_on}  approved by "
                        f"{r.approved_by or '—'}  {r.changes or ''}"
                        for r in revs), parent=win)

    tabs.append(TableTab(
        nb, "Acceptable Use",
        [("id", "ID", 50), ("type", "Who", 65), ("pid", "ID", 85),
         ("name", "Name", 170), ("ver", "Version", 60),
         ("on", "Accepted", 85), ("how", "How", 170),
         ("by", "Recorded by", 120), ("wd", "Withdrawn", 85),
         ("why", "Reason", 180)],
        acc_loader,
        filters=[Field("type", "Who", "combo", aup.USER_TYPES, width=8),
                 Field("person", "ID", width=10),
                 Field("current", "Current version only", "check"),
                 Field("live", "Hide withdrawn", "check")],
        actions=[("Set up AUP", setup_policy),
                 ("Use existing policy", choose_policy),
                 ("Publish new version", new_version),
                 ("Versions", show_versions),
                 ("Record acceptance", record), ("Withdraw", withdraw)],
        tag_colours=_LOAN_TAGS))

    def outstanding_loader(f):
        ut = f.get("type") or aup.STUDENT
        return [(pid, (pid, name, ut), ()) for pid, name in
                aup.outstanding(ut)]

    def record_selected(tab):
        pid = tab.selected()
        if not pid:
            return
        ut = tab.filters().get("type") or aup.STUDENT
        v = form_dialog(win, f"Record acceptance — {pid}", [
            Field("accepted_on", "Accepted on (YYYY-MM-DD)"),
            Field("method", "How", "combo", aup.METHODS, required=True)],
            {"accepted_on": today, "method": aup.DEFAULT_METHOD})
        if v:
            aup.record_acceptance(ut, pid, **v)
            refresh_all()

    tabs.append(TableTab(
        nb, "Not Yet Accepted",
        [("id", "ID", 100), ("name", "Name", 260), ("type", "Who", 80)],
        outstanding_loader,
        filters=[Field("type", "Who", "combo", aup.USER_TYPES, width=8)],
        actions=[("Record acceptance", record_selected)]))

    def render():
        s = data.summary()
        cur = aup.current_aup()
        lines = [
            "Device loans", "",
            f"  Devices in pool:      {s.devices}",
            f"  Available:            {s.available}",
            f"  On loan:              {s.on_loan}",
            f"  Unusable / repair:    {s.unusable}",
            f"  Overdue:              {s.overdue}",
            f"  Bursary-funded out:   {s.bursary_funded_open}",
            f"  Lost (not found):     {s.lost}",
            f"  Returned damaged:     {s.damaged}",
            f"  Charges due:          {money(s.charges_due)}",
            f"  Charges paid:         {money(s.charges_paid)}",
            "", "  By pool:"]
        for pool, counts in s.by_pool.items():
            lines.append(f"    {pool:<16} " + ", ".join(
                f"{k}: {v}" for k, v in counts.items()))
        lines += ["", "IT acceptable-use policy",
                  f"  Current: {cur.title} v{cur.version} "
                  f"(approved {cur.approved_on or '—'})" if cur
                  else "  Not set up — no device can be lent",
                  f"  Students yet to accept: {s.students_without_aup}"]
        return lines

    tabs.append(SummaryTab(nb, render))
