"""Tkinter views for Sixth Form ID cards."""

from __future__ import annotations

import logging
from education_system.platform.delivery.gui.parented_dialogs import messagebox, simpledialog

from education_system.systems.sixth_form.domains.operations.domain.id_cards import (
    id_cards as data,
)
from education_system.systems.sixth_form.interfaces.gui.operations._ops_ui import (
    Field,
    SummaryTab,
    TableTab,
    form_dialog,
    make_window,
    money,
    option_key,
    staff_options,
    student_options,
)

logger = logging.getLogger(__name__)

_CARD_TAGS = {
    data.LOST:      ("#ffd1d1", "#8c0d0d"),
    data.REPLACED:  ("#eeeeee", "#444444"),
    data.CANCELLED: ("#eeeeee", "#444444"),
    data.EXPIRED:   ("#eeeeee", "#444444"),
    "print":        ("#fff7e6", "#7a5800"),
}


def open_id_cards_window(parent=None) -> None:
    data.init_db()
    win, nb = make_window(parent, "ID Cards")
    tabs: list = []

    def refresh_all(_tab=None) -> None:
        for t in tabs:
            t.refresh()

    def card_row(c):
        tag = (c.status if c.status != data.ACTIVE
               else "print" if c.print_status == data.AWAITING_PRINT
               else "")
        return (c.card_id,
                (c.card_id, c.card_number, c.holder_type, c.holder_id,
                 c.holder_name, c.issued_on, c.expires_on, c.status,
                 c.print_status, c.photo_ref or "(no photo)",
                 money(c.charge) if c.charge else "",
                 ("Paid" if c.charge_paid else "Due") if c.charge else "",
                 c.replacement_reason or c.status_reason or ""),
                (tag,) if tag else ())

    cols = [
        ("id", "ID", 45), ("num", "Card no.", 120), ("htype", "Holder", 65),
        ("hid", "Holder ID", 85), ("name", "Name", 160),
        ("iss", "Issued", 90), ("exp", "Expires", 90),
        ("status", "Status", 80), ("print", "Print", 100),
        ("photo", "Photo", 160), ("charge", "Charge", 65),
        ("paid", "Paid", 50), ("why", "Reason", 140)]

    def _card(tab):
        cid = tab.selected()
        return data.get_card(int(cid)) if cid else None

    def issue(tab):
        h = form_dialog(win, "Card holder", [
            Field("holder_type", "Holder type", "combo", data.HOLDER_TYPES,
                  required=True)])
        if not h:
            return
        htype = h["holder_type"]
        people = staff_options() if htype == "Staff" else student_options()
        v = form_dialog(win, f"Issue {htype.lower()} ID card", [
            Field("holder", htype, "combo", people, required=True,
                  width=44),
            Field("photo_ref", "Photo reference (file path)", width=44),
            Field("issued_on", "Issued on (blank = today)"),
            Field("expires_on", "Expires on (blank = default)"),
            Field("issued_by", "Issued by"),
            Field("notes", "Notes", "text"),
        ])
        if v:
            c = data.issue_card(htype, option_key(v["holder"]),
                                photo_ref=v["photo_ref"],
                                issued_on=v["issued_on"] or None,
                                expires_on=v["expires_on"] or None,
                                issued_by=v["issued_by"], notes=v["notes"])
            messagebox.showinfo("Issued", f"Card {c.card_number} issued, "
                                f"expires {c.expires_on}.", parent=win)
            refresh_all()

    def edit(tab):
        c = _card(tab)
        if not c:
            return
        v = form_dialog(win, f"Edit card {c.card_number}", [
            Field("photo_ref", "Photo reference (file path)", width=44),
            Field("expires_on", "Expires on", required=True),
            Field("notes", "Notes", "text"),
        ], vars(c))
        if v:
            data.update_card(c.card_id, v)
            refresh_all()

    def replace(tab):
        c = _card(tab)
        if not c:
            return
        v = form_dialog(win, f"Replace card {c.card_number}", [
            Field("reason", "Reason", "combo", data.REPLACEMENT_REASONS,
                  required=True),
            Field("charge", "Charge £ (blank = default for reason; "
                  f"default {data.replacement_charge():.2f})"),
            Field("photo_ref", "New photo reference (blank = keep)",
                  width=44),
            Field("issued_by", "Issued by"),
        ])
        if v:
            new = data.replace_card(
                c.card_id, reason=v["reason"],
                charge=v["charge"] if v["charge"] else None,
                photo_ref=v["photo_ref"] or None,
                issued_by=v["issued_by"])
            messagebox.showinfo(
                "Replaced", f"New card {new.card_number}"
                + (f" — charge {money(new.charge)}" if new.charge else ""),
                parent=win)
            refresh_all()

    def lost_no_replace(tab):
        c = _card(tab)
        if c and messagebox.askyesno(
                "Lost", f"Mark {c.card_number} lost without issuing a "
                "replacement now?", parent=win):
            data.report_lost(c.card_id, replace=False)
            refresh_all()

    def charge_paid(tab):
        c = _card(tab)
        if c:
            data.record_charge_paid(c.card_id)
            refresh_all()

    def cancel(tab):
        c = _card(tab)
        if not c:
            return
        reason = simpledialog.askstring(
            "Cancel card", f"Reason for cancelling {c.card_number}:",
            parent=win)
        if reason:
            data.cancel_card(c.card_id, reason=reason)
            refresh_all()

    def reprint(tab):
        c = _card(tab)
        if c:
            data.reprint(c.card_id)
            refresh_all()

    def delete(tab):
        c = _card(tab)
        if c and messagebox.askyesno(
                "Delete", f"Delete unprinted card {c.card_number}?",
                parent=win):
            data.delete_card(c.card_id)
            refresh_all()

    def history(tab):
        c = _card(tab)
        if not c:
            return
        rows = data.history_for(c.holder_type, c.holder_id)
        messagebox.showinfo(
            f"Card history — {c.holder_name or c.holder_id}",
            "\n".join(f"{h.card_number}  {h.issued_on} → {h.expires_on}  "
                      f"{h.status}"
                      + (f" ({h.replacement_reason})"
                         if h.replacement_reason else "")
                      for h in rows), parent=win)

    def cards_loader(f):
        return [card_row(c) for c in data.list_cards(
            holder_type=f.get("holder"), status=f.get("status"),
            name_like=f.get("name"),
            charges_outstanding=bool(f.get("charges")))]

    tabs.append(TableTab(
        nb, "Cards", cols, cards_loader,
        filters=[Field("holder", "Holder", "combo", data.HOLDER_TYPES,
                       width=8),
                 Field("status", "Status", "combo", data.STATUSES,
                       width=10),
                 Field("name", "Name / number", width=16),
                 Field("charges", "Charges due", "check")],
        actions=[("Issue card", issue), ("Edit", edit),
                 ("Lost / replace", replace),
                 ("Mark lost (no replacement)", lost_no_replace),
                 ("Charge paid", charge_paid), ("Reprint", reprint),
                 ("Cancel", cancel), ("History", history),
                 ("Delete", delete), ("Settings", lambda t: settings(t))],
        on_double=edit, tag_colours=_CARD_TAGS))

    # ── Printing list ──
    def queue_loader(_f):
        return [card_row(c) for c in data.print_queue()]

    def mark_printed(tab):
        ids = tab.selected_all()
        if not ids:
            messagebox.showinfo("Select", "Select the cards that printed.",
                                parent=win)
            return
        who = simpledialog.askstring("Printed", "Printed by:", parent=win)
        if who is None:
            return
        n = data.mark_printed([int(i) for i in ids], printed_by=who)
        messagebox.showinfo("Printed", f"{n} card(s) marked printed.",
                            parent=win)
        refresh_all()

    def select_all(tab):
        tab.tree.selection_set(tab.tree.get_children())

    tabs.append(TableTab(
        nb, "Printing List", cols, queue_loader,
        actions=[("Select all", select_all),
                 ("Mark selected printed", mark_printed)],
        tag_colours=_CARD_TAGS, selectmode="extended"))

    def expiring_loader(f):
        try:
            days = int(f.get("days") or 30)
        except ValueError:
            days = 30
        return [card_row(c) for c in data.expiring(days)]

    tabs.append(TableTab(
        nb, "Expiring", cols, expiring_loader,
        filters=[Field("days", "Within days (30)", width=5)],
        actions=[("Edit expiry", edit), ("Replace", replace)],
        tag_colours=_CARD_TAGS))

    def without_loader(_f):
        return [(sid, (sid, name), ())
                for sid, name in data.students_without_card()]

    def issue_selected(tab):
        sid = tab.selected()
        if not sid:
            return
        photo = simpledialog.askstring(
            "Issue card", "Photo reference (file path, optional):",
            parent=win)
        if photo is None:
            return
        c = data.issue_card("Student", sid, photo_ref=photo or None)
        messagebox.showinfo("Issued", f"Card {c.card_number} issued.",
                            parent=win)
        refresh_all()

    tabs.append(TableTab(
        nb, "Students Without Card",
        [("sid", "Student ID", 120), ("name", "Student", 300)],
        without_loader, actions=[("Issue card", issue_selected)]))

    def settings(_tab=None):
        v = form_dialog(win, "ID card settings", [
            Field("charge", "Replacement charge (£)", required=True),
            Field("years", "Staff card validity (years)", required=True),
        ], {"charge": f"{data.replacement_charge():.2f}",
            "years": data.staff_validity_years()})
        if v:
            data.set_replacement_charge(v["charge"])
            data.set_staff_validity_years(v["years"])
            refresh_all()

    def render():
        s = data.summary()
        lines = ["ID cards summary", "",
                 f"  Cards on file:          {s.total}",
                 f"  Active:                 {s.active} "
                 + ", ".join(f"{k}: {v}"
                             for k, v in s.by_holder_type.items()),
                 f"  Awaiting print:         {s.awaiting_print}",
                 f"  Active without photo:   {s.no_photo}",
                 f"  Expiring in 30 days:    {s.expiring_30}",
                 f"  Students without card:  {s.students_without_card}",
                 f"  Replacements issued:    {s.replacements}",
                 f"  Charges outstanding:    {money(s.charges_outstanding)}",
                 f"  Charges collected:      {money(s.charges_collected)}",
                 "", "  By status:"]
        lines += [f"    {k:<10} {v}" for k, v in s.by_status.items()]
        lines += ["",
                  f"  Replacement charge:     "
                  f"{money(data.replacement_charge())}",
                  f"  Staff card validity:    "
                  f"{data.staff_validity_years()} year(s)"]
        return lines

    tabs.append(SummaryTab(nb, render))
