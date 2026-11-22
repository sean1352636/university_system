"""Tkinter views for Sixth Form Lockers."""

from __future__ import annotations

import logging
from education_system.platform.delivery.gui.parented_dialogs import messagebox, simpledialog

from education_system.systems.sixth_form.domains.operations.domain.lockers import (
    lockers as data,
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
    student_options,
)

logger = logging.getLogger(__name__)

_LOCKER_TAGS = {
    data.AVAILABLE:    ("#e6f7e6", "#0d6b2a"),
    data.ALLOCATED:    ("#e6f0ff", "#1a3f8c"),
    data.OUT_OF_ORDER: ("#ffd1d1", "#8c0d0d"),
}
_ALLOC_TAGS = {
    "overdue": ("#ffd1d1", "#8c0d0d"),
    "due":     ("#fff7e6", "#7a5800"),
    data.RETURNED: ("#eeeeee", "#444444"),
}


def open_lockers_window(parent=None) -> None:
    data.init_db()
    win, nb = make_window(parent, "Lockers")
    tabs: list = []

    def refresh_all(_tab=None) -> None:
        for t in tabs:
            t.refresh()

    def bank_options() -> list[str]:
        return [option_label(b.bank_id, b.name) for b in data.list_banks()]

    # ── Banks ──
    bank_fields = [
        Field("name", "Bank name", required=True),
        Field("location", "Location"),
        Field("locker_size", "Locker size", "combo", data.LOCKER_SIZES,
              required=True),
        Field("active", "Active", "check"),
        Field("notes", "Notes", "text"),
    ]

    def banks_loader(_f):
        counts: dict[int, dict[str, int]] = {}
        for lk in data.list_lockers():
            c = counts.setdefault(lk.bank_id, {})
            c[lk.status] = c.get(lk.status, 0) + 1
        return [(b.bank_id,
                 (b.bank_id, b.name, b.location, b.locker_size,
                  "Yes" if b.active else "No",
                  sum(counts.get(b.bank_id, {}).values()),
                  counts.get(b.bank_id, {}).get(data.AVAILABLE, 0)),
                 ()) for b in data.list_banks()]

    def new_bank(tab):
        v = form_dialog(win, "New locker bank", bank_fields, {"active": True})
        if v:
            data.create_bank(v)
            refresh_all()

    def edit_bank(tab):
        bid = tab.selected()
        if not bid:
            return
        b = data.get_bank(int(bid))
        v = form_dialog(win, f"Edit {b.name}", bank_fields, vars(b))
        if v:
            data.update_bank(b.bank_id, v)
            refresh_all()

    def add_run(tab):
        bid = tab.selected()
        if not bid:
            return
        v = form_dialog(win, "Add numbered lockers", [
            Field("prefix", "Number prefix (e.g. A)"),
            Field("first", "First number", required=True),
            Field("count", "How many", required=True),
            Field("width", "Zero-pad to width (0 = none)"),
        ], {"first": 1, "count": 10, "width": 0})
        if v:
            made = data.add_lockers(int(bid), int(v["first"]),
                                    int(v["count"]), prefix=v["prefix"],
                                    width=int(v["width"] or 0))
            messagebox.showinfo("Lockers", f"Added {len(made)} locker(s).",
                                parent=win)
            refresh_all()

    def delete_bank(tab):
        bid = tab.selected()
        if bid and messagebox.askyesno("Delete", "Delete this empty bank?",
                                       parent=win):
            data.delete_bank(int(bid))
            refresh_all()

    tabs.append(TableTab(
        nb, "Banks",
        [("id", "ID", 50), ("name", "Name", 200), ("loc", "Location", 220),
         ("size", "Size", 110), ("active", "Active", 70),
         ("lockers", "Lockers", 80), ("free", "Available", 80)],
        banks_loader,
        actions=[("New bank", new_bank), ("Edit", edit_bank),
                 ("Add numbered lockers", add_run),
                 ("Delete", delete_bank)],
        on_double=edit_bank))

    # ── Lockers ──
    def lockers_loader(f):
        bank = option_key(f.get("bank"))
        active = {a.locker_id: a for a in data.list_allocations(
            active_only=True)}
        rows = []
        for lk in data.list_lockers(bank_id=int(bank) if bank else None,
                                    status=f.get("status"),
                                    number_like=f.get("number")):
            a = active.get(lk.locker_id)
            rows.append((lk.locker_id,
                         (lk.locker_id, lk.bank_name, lk.number, lk.code,
                          lk.key_number, lk.status,
                          f"{a.student_id} {a.student_name or ''}" if a
                          else "", a.academic_year if a else "",
                          lk.notes), (lk.status,)))
        return rows

    def new_locker(tab):
        v = form_dialog(win, "New locker", [
            Field("bank", "Bank", "combo", bank_options(), required=True),
            Field("number", "Locker number", required=True),
            Field("code", "Combination code"),
            Field("key_number", "Key number"),
            Field("notes", "Notes", "text"),
        ])
        if v:
            v["bank_id"] = option_key(v.pop("bank"))
            data.create_locker(v)
            refresh_all()

    def edit_locker(tab):
        lid = tab.selected()
        if not lid:
            return
        lk = data.get_locker(int(lid))
        v = form_dialog(win, f"Edit locker {lk.label}", [
            Field("number", "Locker number", required=True),
            Field("code", "Combination code"),
            Field("key_number", "Key number"),
            Field("notes", "Notes", "text"),
        ], vars(lk))
        if v:
            data.update_locker(lk.locker_id, v)
            refresh_all()

    def allocate(tab):
        lid = tab.selected()
        if not lid:
            return
        lk = data.get_locker(int(lid))
        v = form_dialog(win, f"Allocate locker {lk.label}", [
            Field("student", "Student", "combo", student_options(),
                  required=True, width=44),
            Field("academic_year", "Academic year", required=True),
            Field("deposit_amount", "Deposit (£)"),
            Field("deposit_paid", "Deposit paid now", "check"),
            Field("key_issued", "Key issued", "check"),
            Field("code", "Code given to student"),
            Field("allocated_by", "Allocated by"),
            Field("notes", "Notes", "text"),
        ], {"academic_year": data.current_academic_year(),
            "deposit_amount": f"{data.DEFAULT_DEPOSIT:.2f}",
            "code": lk.code})
        if v:
            data.allocate(lk.locker_id, option_key(v["student"]),
                          academic_year=v["academic_year"],
                          deposit_amount=v["deposit_amount"] or 0,
                          deposit_paid=v["deposit_paid"],
                          key_issued=v["key_issued"], code=v["code"],
                          allocated_by=v["allocated_by"], notes=v["notes"])
            refresh_all()

    def toggle_ooo(tab):
        lid = tab.selected()
        if not lid:
            return
        lk = data.get_locker(int(lid))
        new = (data.AVAILABLE if lk.status == data.OUT_OF_ORDER
               else data.OUT_OF_ORDER)
        data.set_locker_status(lk.locker_id, new)
        refresh_all()

    def delete_locker(tab):
        lid = tab.selected()
        if lid and messagebox.askyesno("Delete", "Delete this locker?",
                                       parent=win):
            data.delete_locker(int(lid))
            refresh_all()

    tabs.append(TableTab(
        nb, "Lockers",
        [("id", "ID", 50), ("bank", "Bank", 150), ("num", "Number", 80),
         ("code", "Code", 80), ("key", "Key no.", 80),
         ("status", "Status", 100), ("holder", "Holder", 220),
         ("year", "Year", 80), ("notes", "Notes", 220)],
        lockers_loader,
        filters=[Field("bank", "Bank", "combo", bank_options(), width=20),
                 Field("status", "Status", "combo", data.LOCKER_STATUSES,
                       width=14),
                 Field("number", "Number", width=10)],
        actions=[("New locker", new_locker), ("Edit", edit_locker),
                 ("Allocate", allocate),
                 ("Out of order / back in use", toggle_ooo),
                 ("Delete", delete_locker)],
        on_double=edit_locker, tag_colours=_LOCKER_TAGS))

    # ── Allocations ──
    def alloc_rows(rows, overdue_ids):
        out = []
        for a in rows:
            tag = (data.RETURNED if not a.is_active
                   else "overdue" if a.allocation_id in overdue_ids
                   else "due" if a.deposit_outstanding else "")
            out.append((a.allocation_id,
                        (a.allocation_id, a.locker_label, a.student_id,
                         a.student_name, a.academic_year, a.allocated_on,
                         "Yes" if a.key_issued else "No", a.code_issued,
                         money(a.deposit_amount), a.deposit_status,
                         a.status, a.returned_on, a.return_condition,
                         a.deposit_retained_reason),
                        (tag,) if tag else ()))
        return out

    def allocations_loader(f):
        overdue = {a.allocation_id for a in data.overdue_returns()}
        rows = data.list_allocations(
            student_id=f.get("student"),
            academic_year=f.get("year"),
            active_only=bool(f.get("active")),
            deposit_status=f.get("deposit"))
        return alloc_rows(rows, overdue)

    def _alloc(tab):
        aid = tab.selected()
        return data.get_allocation(int(aid)) if aid else None

    def deposit_paid(tab):
        a = _alloc(tab)
        if a:
            data.record_deposit_paid(a.allocation_id)
            refresh_all()

    def key_issued(tab):
        a = _alloc(tab)
        if not a:
            return
        code = simpledialog.askstring(
            "Key / code", "Code given (blank to keep):", parent=win,
            initialvalue=a.code_issued or "")
        if code is None:
            return
        data.issue_key(a.allocation_id, key_issued=True, code=code or None)
        refresh_all()

    def return_locker(tab):
        a = _alloc(tab)
        if not a:
            return
        v = form_dialog(win, f"Return {a.locker_label}", [
            Field("returned_on", "Returned on (YYYY-MM-DD)"),
            Field("condition", "Condition", "combo",
                  data.RETURN_CONDITIONS, required=True),
            Field("refund_deposit", "Refund deposit", "check"),
            Field("retain_reason", "Reason if retained"),
            Field("notes", "Notes", "text"),
        ], {"refund_deposit": True, "condition": "Good"})
        if v:
            data.return_locker(a.allocation_id,
                               returned_on=v["returned_on"] or None,
                               condition=v["condition"],
                               refund_deposit=v["refund_deposit"],
                               retain_reason=v["retain_reason"],
                               notes=v["notes"])
            refresh_all()

    alloc_cols = [
        ("id", "ID", 50), ("locker", "Locker", 130),
        ("sid", "Student ID", 90), ("name", "Student", 150),
        ("year", "Year", 70), ("from", "Allocated", 90),
        ("key", "Key", 50), ("code", "Code", 70),
        ("dep", "Deposit", 70), ("dstat", "Deposit status", 100),
        ("status", "Status", 80), ("ret", "Returned", 90),
        ("cond", "Condition", 90), ("why", "Retained because", 160)]
    alloc_actions = [("Deposit paid", deposit_paid),
                     ("Key / code issued", key_issued),
                     ("Return locker", return_locker)]
    tabs.append(TableTab(
        nb, "Allocations", alloc_cols, allocations_loader,
        filters=[Field("student", "Student ID", width=10),
                 Field("year", "Year (2026/27)", width=9),
                 Field("deposit", "Deposit", "combo", data.DEPOSIT_STATUSES,
                       width=10),
                 Field("active", "Active only", "check")],
        actions=alloc_actions, tag_colours=_ALLOC_TAGS))

    def overdue_loader(f):
        rows = data.overdue_returns(academic_year=f.get("year"))
        return alloc_rows(rows, {a.allocation_id for a in rows})

    tabs.append(TableTab(
        nb, "Overdue Returns", alloc_cols, overdue_loader,
        filters=[Field("year", "All still out for year", width=9)],
        actions=alloc_actions, tag_colours=_ALLOC_TAGS))

    def render():
        s = data.summary()
        lines = [
            "Lockers summary", "",
            f"  Banks:               {s.banks}",
            f"  Lockers:             {s.lockers}",
        ]
        lines += [f"    {k:<18} {v}" for k, v in s.by_status.items()]
        lines += [
            "",
            f"  Active allocations:  {s.active_allocations}",
            f"  Overdue returns:     {s.overdue_returns}",
            f"  Deposits held:       {money(s.deposits_held)}",
            f"  Deposits due:        {s.deposits_due}",
            f"  Deposits retained:   {money(s.deposits_retained)}",
            "", "  By bank:"]
        for bank, counts in s.by_bank.items():
            lines.append(f"    {bank:<20} " + ", ".join(
                f"{k}: {v}" for k, v in counts.items()))
        return lines

    tabs.append(SummaryTab(nb, render))
