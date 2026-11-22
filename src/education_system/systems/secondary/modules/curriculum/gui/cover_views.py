"""Cover screen.

The old Cover window is the Cover tab: Date / Status / Absent filters, Filter,
New, Edit, Assign, Set status, Delete, Daily load and Refresh, with the old
columns. The old Cover Agency window is the Supply staff tab (Add, Edit,
Toggle active, Delete, Refresh, and the bookings list). Added: absences that
create cover from the timetable, a free-staff picker, e-mailing the cover,
the day's cover sheet, My cover, supply costs and the weekly cover limit.
Rules live in :mod:`modules.curriculum.domain.cover`.
"""

from __future__ import annotations

import datetime as _dt
import logging
import tkinter as tk
from tkinter import ttk
from typing import Callable

from education_system.platform.delivery.gui.parented_dialogs import (
    make_toplevel,
    messagebox,
)
from education_system.systems.secondary.modules.curriculum.domain import cover as CV
from education_system.systems.secondary.modules.curriculum.domain import teaching_groups as TG
from education_system.systems.secondary.modules.curriculum.domain import timetable as TT
from education_system.systems.secondary.core.permissions.access import COVER_EDITORS, Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.gui.components import widgets as W

logger = logging.getLogger(__name__)
ALL = "All"
STATUS_BG = {"Pending": "#fde2e2", "Assigned": "#fff6d5", "Confirmed": "#e6f2ff",
             "Completed": "#e7f6ea", "Cancelled": "#eeeeee"}


_problems = W.problems


def _tree(parent, columns, height: int = 10) -> ttk.Treeview:
    return W.tree(parent, columns, height=height,
                  stretch={"absent", "cover", "name", "notes", "work"}, tags=STATUS_BG)


def _cover_row(c: CV.Cover) -> tuple:
    return (c.cover_id, c.date, c.period, c.year_group or "", c.group_code,
            c.subject_code or "", c.absent_name, c.cover_name or "-", c.room or "",
            c.status)


_COVER_COLS = (("id", "ID", 45), ("date", "Date", 90), ("p", "P", 35), ("yr", "Yr", 35),
               ("form", "Group", 80), ("subj", "Subj", 60), ("absent", "Absent", 140),
               ("cover", "Cover", 140), ("room", "Room", 60), ("status", "Status", 85))


def _text_window(owner, title: str, text: str, *, save_name: str | None = None,
                 principal: Principal | None = None) -> None:
    W.text_window(owner, title, text, save_name=save_name,
                  on_save=lambda _path: activity_log.record("cover.sheet_export",
                                                            principal=principal))


class CoverPage:
    TABS = ("Cover", "Absences", "My cover", "Supply staff", "Settings")

    def __init__(self, parent: ttk.Frame, *, principal: Principal, state: dict) -> None:
        self.parent, self.principal, self.state = parent, principal, state
        self.editor = principal.role in COVER_EDITORS
        activity_log.record("cover.view")
        ttk.Label(parent, text="Cover", font=("", 16, "bold")).pack(anchor="w")
        self.summary_var = tk.StringVar()
        ttk.Label(parent, textvariable=self.summary_var, foreground="#666").pack(anchor="w",
                                                                                 pady=(0, 6))
        self.book = ttk.Notebook(parent)
        self.book.pack(fill="both", expand=True)
        self.tabs = {n: ttk.Frame(self.book, padding=8) for n in self.TABS}
        for n, f in self.tabs.items():
            self.book.add(f, text=n)
        self._build_cover(self.tabs["Cover"])
        self.book.select(self.TABS.index(state.get("tab", "Cover")))
        self.book.bind("<<NotebookTabChanged>>", self._on_tab)
        self._on_tab()

    def _on_tab(self, _e=None) -> None:
        name = self.TABS[self.book.index(self.book.select())]
        self.state["tab"] = name
        if name == "Cover":
            self.refresh()
            return
        tab = self.tabs[name]
        for w in tab.winfo_children():
            w.destroy()
        try:
            {"Absences": self._draw_absences, "My cover": self._draw_mine,
             "Supply staff": self._draw_supply, "Settings": self._draw_settings}[name](tab)
        except Exception:
            logger.exception("Cover tab %s failed", name)
            ttk.Label(tab, text="Couldn't load this tab - see the log.",
                      foreground="#a00").pack(anchor="w")

    # ── Cover tab (old window) ───────────────────────────────────────

    def _build_cover(self, tab: ttk.Frame) -> None:
        st = self.state
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        self.date_var = tk.StringVar(value=st.get("date", _dt.date.today().isoformat()))
        self.status_var = tk.StringVar(value=st.get("status", ALL))
        self.absent_var = tk.StringVar(value=st.get("absent", ""))
        ttk.Label(bar, text="Date:").pack(side="left", padx=(0, 4))
        ttk.Entry(bar, textvariable=self.date_var, width=11).pack(side="left")
        ttk.Label(bar, text="Status:").pack(side="left", padx=(8, 4))
        ttk.Combobox(bar, textvariable=self.status_var, values=[ALL, *CV.STATUSES],
                     state="readonly", width=10).pack(side="left")
        ttk.Label(bar, text="Absent:").pack(side="left", padx=(8, 4))
        ttk.Entry(bar, textvariable=self.absent_var, width=14).pack(side="left")
        buttons = [("Filter", self.refresh), ("New", self.new), ("Edit", self.edit),
                   ("Assign", self.assign), ("Set status", self.set_status),
                   ("Delete", self.delete), ("Daily load", self.daily_load),
                   ("Refresh", self.refresh)]
        for text, cmd in buttons:
            ttk.Button(bar, text=text, command=cmd).pack(side="left", padx=2)
        bar2 = ttk.Frame(tab)
        bar2.pack(fill="x", pady=(0, 4))
        for delta, text in ((-1, "◀ Day"), (1, "Day ▶")):
            ttk.Button(bar2, text=text, command=lambda d=delta: self._step(d)).pack(
                side="left", padx=2)
        ttk.Button(bar2, text="All dates from today", command=lambda: (
            self.date_var.set(""), self.refresh())).pack(side="left", padx=2)
        for text, cmd in (("E-mail the cover…", self.notify), ("Cover sheet", self.sheet),
                          ("Unassign", self.unassign), ("History", self.history)):
            ttk.Button(bar2, text=text, command=cmd).pack(side="left", padx=(8, 2))
        self.status_var.trace_add("write", lambda *_: self.refresh())
        self.tree = _tree(tab, _COVER_COLS, height=14)
        self.tree.bind("<<TreeviewSelect>>", lambda _e: self._detail())
        self.tree.bind("<Double-1>", lambda _e: self.assign() if self.editor else self.edit())
        box = ttk.LabelFrame(tab, text="Selected cover", padding=8)
        box.pack(fill="x", pady=(8, 0))
        self.detail_var = tk.StringVar(value="(select a row to see the details and work)")
        ttk.Label(box, textvariable=self.detail_var, justify="left",
                  wraplength=1100).pack(anchor="w")
        self.rows: dict[str, CV.Cover] = {}

    def _step(self, days: int) -> None:
        try:
            d = _dt.date.fromisoformat(self.date_var.get().strip())
        except ValueError:
            d = _dt.date.today()
        self.date_var.set((d + _dt.timedelta(days=days)).isoformat())
        self.refresh()

    def refresh(self) -> None:
        st = self.state
        st.update(date=self.date_var.get(), status=self.status_var.get(),
                  absent=self.absent_var.get())
        date = self.date_var.get().strip()
        status = self.status_var.get()
        try:
            rows = CV.list_covers(date=date or None,
                                  date_from=None if date else _dt.date.today(),
                                  status=None if status == ALL else status,
                                  absent=self.absent_var.get().strip() or None)
        except CV.ValidationError as e:
            messagebox.showerror("Cover", _problems(e), parent=self.parent)
            return
        self.tree.delete(*self.tree.get_children())
        self.rows.clear()
        for c in rows:
            iid = self.tree.insert("", "end", tags=(c.status,), values=_cover_row(c))
            self.rows[iid] = c
        pending = sum(1 for c in rows if c.status == "Pending")
        self.summary_var.set(f"{len(rows)} cover request(s)"
                             + (f" · {pending} still to assign" if pending else "")
                             + ("" if self.editor else " · you can set work for your own "
                                "lessons and confirm cover you've been given"))
        self.detail_var.set("(select a row to see the details and work)")

    def _selected(self) -> CV.Cover | None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Cover", "Select a cover request first.", parent=self.parent)
            return None
        return self.rows[sel[0]]

    def _detail(self) -> None:
        sel = self.tree.selection()
        if sel:
            c = self.rows[sel[0]]
            extra = f"\nNotes: {c.notes}" if c.notes else ""
            told = f"\nE-mailed {c.notified_at}" if c.notified_at else ""
            self.detail_var.set(CV.details_text(c) + extra + told)

    def new(self) -> None:
        if not self.editor:
            messagebox.showinfo("Cover", "Report your absence on the Absences tab; the cover "
                                "manager adds single lessons.", parent=self.parent)
            return
        new_cover_dialog(self.parent, self.principal, self.refresh,
                         day=self.date_var.get().strip())

    def edit(self) -> None:
        c = self._selected()
        if c:
            edit_cover_dialog(self.parent, self.principal, c, self.refresh)

    def assign(self) -> None:
        c = self._selected()
        if c:
            assign_dialog(self.parent, self.principal, c, self.refresh)

    def unassign(self) -> None:
        c = self._selected()
        if not c:
            return
        try:
            CV.unassign(c.cover_id, actor=self.principal)
        except (CV.ValidationError, CV.PermissionDenied) as e:
            messagebox.showerror("Unassign", _problems(e), parent=self.parent)
            return
        self.refresh()

    def set_status(self) -> None:
        c = self._selected()
        if c:
            status_dialog(self.parent, self.principal, c, self.refresh)

    def delete(self) -> None:
        c = self._selected()
        if not c or not messagebox.askyesno("Delete", f"Delete cover for {c.group_code} "
                                            f"{c.when}?", parent=self.parent):
            return
        try:
            CV.delete(c.cover_id, actor=self.principal)
        except (CV.ValidationError, CV.PermissionDenied) as e:
            messagebox.showerror("Delete", _problems(e), parent=self.parent)
            return
        self.refresh()

    def daily_load(self) -> None:
        day = self.date_var.get().strip() or _dt.date.today().isoformat()
        try:
            load = CV.daily_load(day)
        except CV.ValidationError as e:
            messagebox.showerror("Daily load", _problems(e), parent=self.parent)
            return
        lines = [f"Daily load - {day}", f"{load['total']} lesson(s) covered, "
                 f"{load['unassigned']} unassigned", "", "By cover teacher:"]
        lines += [f"  {who:<30} {n} slot(s)" for who, n in load["by_cover"].items()] or [
            "  (none)"]
        lines += ["", "Arrangements:"] + [
            f"  P{c.period:<3}{c.group_code:<12}{c.absent_name[:20]:<21}-> "
            f"{c.cover_name or 'UNASSIGNED'} [{c.status}]" for c in load["covers"]]
        _text_window(self.parent, "Daily load", "\n".join(lines))

    def notify(self) -> None:
        c = self._selected()
        if not c:
            return
        try:
            mid = CV.notify(c.cover_id, actor=self.principal)
        except (CV.ValidationError, CV.PermissionDenied, CV.NotFound) as e:
            messagebox.showerror("E-mail the cover", _problems(e), parent=self.parent)
            return
        from education_system.systems.secondary.modules.communication.gui import email_views

        def done(report, error) -> None:
            if error:
                messagebox.showwarning("E-mail the cover", f"Saved in the outbox but not "
                                       f"sent yet: {error}", parent=self.parent)
            self.refresh()
        email_views.deliver_in_background(self.parent, mid, self.principal, done)
        messagebox.showinfo("E-mail the cover", f"E-mail to {c.cover_name} is on its way "
                            "(see Email for delivery).", parent=self.parent)

    def sheet(self) -> None:
        day = self.date_var.get().strip() or _dt.date.today().isoformat()
        try:
            text = CV.cover_sheet(day)
        except CV.ValidationError as e:
            messagebox.showerror("Cover sheet", _problems(e), parent=self.parent)
            return
        _text_window(self.parent, "Cover sheet", text, save_name=f"cover-{day}.txt",
                     principal=self.principal)

    def history(self) -> None:
        c = self._selected()
        if c:
            rows = CV.history(cover_id=c.cover_id)
            _text_window(self.parent, "History", "\n".join(
                f"{h['at']}  {h['actor']:<14} {h['action']}"
                + (f"  {h['detail'].get('from')} → {h['detail'].get('to')}"
                   if h["action"] == "status" else "") for h in rows) or "No changes.")

    # ── Absences ─────────────────────────────────────────────────────

    def _draw_absences(self, tab: ttk.Frame) -> None:
        start = tk.StringVar(value=self.state.get("abs_from", _dt.date.today().isoformat()))
        show_cancelled = tk.BooleanVar(value=False)
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 6))
        ttk.Label(bar, text="From:").pack(side="left")
        ttk.Entry(bar, textvariable=start, width=11).pack(side="left", padx=4)
        ttk.Checkbutton(bar, text="Show cancelled", variable=show_cancelled).pack(side="left")
        ttk.Label(tab, text="Recording an absence creates cover for each timetabled lesson. "
                            "Reasons are categories only - no medical details.",
                  foreground="#555").pack(anchor="w")
        tree = _tree(tab, (("name", "Teacher", 160), ("dates", "Dates", 190),
                           ("periods", "Periods", 80), ("reason", "Reason", 130),
                           ("cover", "Cover (open / all)", 120), ("status", "Status", 80),
                           ("notes", "Notes", 200)), height=14)
        rows: dict[str, CV.Absence] = {}

        def show(*_a) -> None:
            tree.delete(*tree.get_children())
            rows.clear()
            self.state["abs_from"] = start.get()
            for a in CV.list_absences(date_from=start.get().strip() or None,
                                      include_cancelled=show_cancelled.get()):
                covers = CV.list_covers(absence_id=a.absence_id)
                open_n = sum(1 for c in covers if c.is_open)
                iid = tree.insert("", "end", values=(
                    a.teacher_name, a.dates_label, a.periods_label, a.reason,
                    f"{open_n} / {len(covers)}", a.status.title(), a.notes or ""))
                rows[iid] = a

        def selected() -> CV.Absence | None:
            sel = tree.selection()
            if not sel:
                messagebox.showinfo("Absences", "Select an absence first.", parent=tab)
                return None
            return rows[sel[0]]

        def cancel() -> None:
            a = selected()
            if not a or not messagebox.askyesno(
                    "Cancel absence", f"{a.teacher_name} is in after all? Their open cover "
                    "will be cancelled.", parent=tab):
                return
            try:
                n = CV.cancel_absence(a.absence_id, actor=self.principal)
            except (CV.ValidationError, CV.PermissionDenied) as e:
                messagebox.showerror("Cancel absence", _problems(e), parent=tab)
                return
            messagebox.showinfo("Cancel absence", f"Cancelled {n} cover request(s).",
                                parent=tab)
            show()

        def its_cover() -> None:
            a = selected()
            if a:
                self.date_var.set("")
                self.absent_var.set(a.teacher_username or a.teacher_name)
                self.book.select(0)

        ttk.Button(bar, text="Show", command=show).pack(side="left", padx=6)
        ttk.Button(bar, text="New absence", command=lambda: absence_dialog(
            tab, self.principal, None, show)).pack(side="left", padx=2)
        ttk.Button(bar, text="Edit", command=lambda: (a := selected()) and absence_dialog(
            tab, self.principal, a, show)).pack(side="left", padx=2)
        ttk.Button(bar, text="Cancel absence", command=cancel).pack(side="left", padx=2)
        ttk.Button(bar, text="Show its cover", command=its_cover).pack(side="left", padx=2)
        tree.bind("<Double-1>", lambda _e: (a := selected()) and absence_dialog(
            tab, self.principal, a, show))
        show_cancelled.trace_add("write", show)
        show()

    # ── My cover ─────────────────────────────────────────────────────

    def _draw_mine(self, tab: ttk.Frame) -> None:
        me = self.principal.username
        ttk.Label(tab, text="Cover I'm doing", font=("", 10, "bold")).pack(anchor="w")
        doing = _tree(tab, _COVER_COLS, height=7)
        rows: dict[str, CV.Cover] = {}
        for c in CV.my_cover(self.principal):
            rows[doing.insert("", "end", tags=(c.status,), values=_cover_row(c))] = c
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=4)

        def confirm(status: str) -> None:
            sel = doing.selection()
            if not sel:
                return
            try:
                CV.set_status(rows[sel[0]].cover_id, status, actor=self.principal)
            except (CV.ValidationError, CV.PermissionDenied) as e:
                messagebox.showerror("My cover", _problems(e), parent=tab)
                return
            self._on_tab()

        ttk.Button(bar, text="Confirm", command=lambda: confirm("Confirmed")).pack(side="left")
        ttk.Button(bar, text="Done (completed)", command=lambda: confirm("Completed")).pack(
            side="left", padx=4)
        ttk.Button(bar, text="Details", command=lambda: doing.selection() and _text_window(
            tab, "Cover details", CV.details_text(rows[doing.selection()[0]]))).pack(
            side="left")
        ttk.Label(tab, text="Cover for my lessons (set the work)",
                  font=("", 10, "bold")).pack(anchor="w", pady=(8, 0))
        mine = _tree(tab, _COVER_COLS, height=7)
        mine_rows: dict[str, CV.Cover] = {}
        for c in CV.list_covers(absent=me, date_from=_dt.date.today(),
                                include_cancelled=False):
            mine_rows[mine.insert("", "end", tags=(c.status,), values=_cover_row(c))] = c

        def work(_e=None) -> None:
            sel = mine.selection()
            if sel:
                edit_cover_dialog(tab, self.principal, mine_rows[sel[0]], self._on_tab)
        ttk.Button(tab, text="Set cover work…", command=work).pack(anchor="w", pady=4)
        mine.bind("<Double-1>", work)

    # ── Supply staff (old Cover Agency) ──────────────────────────────

    def _draw_supply(self, tab: ttk.Frame) -> None:
        s_bar = ttk.Frame(tab)
        s_bar.pack(fill="x", pady=(0, 4))
        tree = _tree(tab, (("name", "Name", 160), ("agency", "Agency", 130),
                           ("role", "Role", 120), ("rate", "Rate/hr", 70), ("dbs", "DBS", 110),
                           ("email", "E-mail", 170), ("phone", "Phone", 100),
                           ("active", "Active", 55)), height=7)
        rows: dict[str, CV.Supply] = {}

        def show() -> None:
            tree.delete(*tree.get_children())
            rows.clear()
            for s in CV.list_supply():
                rows[tree.insert("", "end", values=(
                    s.full_name, s.agency_name or "", s.role,
                    "" if s.hourly_rate is None else f"£{s.hourly_rate:.2f}",
                    f"Yes ({s.dbs_checked_on})" if s.dbs_cleared else "NOT CLEARED",
                    s.email or "", s.phone or "", "Yes" if s.is_active else "No"))] = s

        def selected() -> CV.Supply | None:
            sel = tree.selection()
            if not sel:
                messagebox.showinfo("Supply staff", "Select someone first.", parent=tab)
                return None
            return rows[sel[0]]

        def act(fn) -> None:
            s = selected()
            if not s:
                return
            if fn is CV.delete_supply and not messagebox.askyesno(
                    "Delete", f"Delete {s.full_name}?", parent=tab):
                return
            try:
                fn(s.supply_id, actor=self.principal)
            except (CV.ValidationError, CV.PermissionDenied) as e:
                messagebox.showerror("Supply staff", _problems(e), parent=tab)
                return
            show()

        if self.editor:
            ttk.Button(s_bar, text="Add", command=lambda: supply_dialog(
                tab, self.principal, None, show)).pack(side="left", padx=2)
            ttk.Button(s_bar, text="Edit", command=lambda: (s := selected()) and supply_dialog(
                tab, self.principal, s, show)).pack(side="left", padx=2)
            ttk.Button(s_bar, text="Toggle active", command=lambda: act(CV.toggle_supply)).pack(
                side="left", padx=2)
            ttk.Button(s_bar, text="Delete", command=lambda: act(CV.delete_supply)).pack(
                side="left", padx=2)
        ttk.Button(s_bar, text="Refresh", command=show).pack(side="left", padx=2)
        show()

        ttk.Label(tab, text="Bookings and cost", font=("", 10, "bold")).pack(anchor="w",
                                                                              pady=(8, 0))
        b_bar = ttk.Frame(tab)
        b_bar.pack(fill="x", pady=(0, 4))
        today = _dt.date.today()
        start = tk.StringVar(value=(today.replace(day=1)).isoformat())
        end = tk.StringVar(value=today.isoformat())
        for text, var in (("From:", start), ("To:", end)):
            ttk.Label(b_bar, text=text).pack(side="left", padx=(4, 2))
            ttk.Entry(b_bar, textvariable=var, width=11).pack(side="left")
        cost = ttk.Label(tab, foreground="#555")
        cost.pack(anchor="w")
        bookings = _tree(tab, _COVER_COLS, height=6)

        def apply() -> None:
            bookings.delete(*bookings.get_children())
            try:
                covers = [c for c in CV.list_covers(date_from=start.get(), date_to=end.get(),
                                                    include_cancelled=False) if c.supply_id]
                report = CV.supply_report(start.get(), end.get())
            except CV.ValidationError as e:
                messagebox.showerror("Bookings", _problems(e), parent=tab)
                return
            for c in covers:
                bookings.insert("", "end", tags=(c.status,), values=_cover_row(c))
            cost.configure(text="; ".join(
                f"{r['supply'].full_name} ({r['supply'].agency_name or 'no agency'}): "
                f"{r['periods']} period(s), £{r['cost']:.2f}" for r in report)
                or "No supply cover in these dates.")

        ttk.Button(b_bar, text="Apply", command=apply).pack(side="left", padx=4)
        ttk.Button(b_bar, text="Refresh", command=apply).pack(side="left")
        apply()

    # ── Settings ─────────────────────────────────────────────────────

    def _draw_settings(self, tab: ttk.Frame) -> None:
        box = ttk.LabelFrame(tab, text="Weekly cover limit", padding=8)
        box.pack(fill="x")
        ttk.Label(box, text="Warn when a member of staff is given more cover than this in a "
                            "week:").pack(side="left")
        e = ttk.Entry(box, width=5)
        e.insert(0, str(CV.weekly_limit()))
        e.pack(side="left", padx=6)

        def save() -> None:
            try:
                CV.set_weekly_limit(e.get(), actor=self.principal)
            except (CV.ValidationError, CV.PermissionDenied) as err:
                messagebox.showerror("Settings", _problems(err), parent=tab)
                return
            messagebox.showinfo("Settings", "Saved.", parent=tab)
        if self.editor:
            ttk.Button(box, text="Save", command=save).pack(side="left")
        else:
            e.state(["disabled"])
        fair = ttk.LabelFrame(tab, text="Cover done this half term (last 6 weeks)", padding=8)
        fair.pack(fill="both", expand=True, pady=(8, 0))
        today = _dt.date.today()
        counts = CV.cover_counts(today - _dt.timedelta(days=42), today)
        t = _tree(fair, (("name", "Member of staff", 220), ("n", "Lessons covered", 120)),
                  height=10)
        for who, n in counts.items():
            t.insert("", "end", values=(who, n))
        if not counts:
            ttk.Label(fair, text="No cover in the last six weeks.", foreground="#888").pack(
                anchor="w")


def draw_cover(parent: ttk.Frame, *, principal: Principal, state: dict | None = None
               ) -> CoverPage:
    return CoverPage(parent, principal=principal, state=state if state is not None else {})


# ── Dialogs ──────────────────────────────────────────────────────────

def _grid_rows(frm, rows) -> None:
    for i, (text, w) in enumerate(rows):
        ttk.Label(frm, text=text).grid(row=i, column=0, sticky="nw", pady=2, padx=(0, 8))
        w.grid(row=i, column=1, sticky="w", pady=2)


def _buttons(frm, row: int, win, save, label: str = "Save") -> None:
    bar = ttk.Frame(frm)
    bar.grid(row=row, column=0, columnspan=2, sticky="e", pady=(8, 0))
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="right")
    ttk.Button(bar, text=label, command=save).pack(side="right", padx=(0, 6))


def new_cover_dialog(owner, principal: Principal, after: Callable[[], None], *,
                     day: str = "") -> None:
    win = make_toplevel(owner.winfo_toplevel())
    win.title("New cover")
    win.resizable(False, False)
    frm = ttk.Frame(win, padding=12)
    frm.pack(fill="both", expand=True)
    groups = {f"{i.group.code} - {i.subject.code} Y{i.group.year_group}"
              + (f" ({i.group.teacher_name})" if i.group.teacher_name else ""): i.group
              for i in TG.info(TG.list_groups())}
    date_e = ttk.Entry(frm, width=12)
    date_e.insert(0, day or _dt.date.today().isoformat())
    plabels = [f"{p.label} ({p.times})" for p in TT.periods()]
    period_cb = ttk.Combobox(frm, values=plabels, state="readonly", width=20)
    group_cb = ttk.Combobox(frm, values=list(groups), state="readonly", width=46)
    absent = ttk.Entry(frm, width=30)
    room = ttk.Entry(frm, width=10)
    notes = ttk.Entry(frm, width=46)

    def fill(_e=None) -> None:
        g = groups.get(group_cb.get())
        if g and not absent.get().strip():
            absent.insert(0, g.teacher_name or "")
    group_cb.bind("<<ComboboxSelected>>", fill)
    _grid_rows(frm, (("Date *", date_e), ("Period *", period_cb), ("Group *", group_cb),
                     ("Absent teacher *", absent), ("Room", room), ("Notes", notes)))

    def save() -> None:
        g = groups.get(group_cb.get())
        try:
            CV.create({"date": date_e.get(), "period": period_cb.current() + 1
                       if period_cb.get() else None, "group_id": g.group_id if g else None,
                       "absent_name": absent.get(), "room": room.get(), "notes": notes.get()},
                      actor=principal)
        except (CV.ValidationError, CV.PermissionDenied) as e:
            messagebox.showerror("New cover", _problems(e), parent=win)
            return
        win.destroy()
        after()
    _buttons(frm, 6, win, save)


def edit_cover_dialog(owner, principal: Principal, c: CV.Cover,
                      after: Callable[[], None]) -> None:
    """Old 'Edit': room and notes (cover manager) and the cover work."""
    editor = principal.role in COVER_EDITORS
    win = make_toplevel(owner.winfo_toplevel())
    win.title(f"Cover - {c.group_code} {c.when}")
    win.resizable(False, False)
    frm = ttk.Frame(win, padding=12)
    frm.pack(fill="both", expand=True)
    ttk.Label(frm, text=f"{c.group_code} · {c.subject_code or ''} · {c.when} · for "
                        f"{c.absent_name} · {c.status}", font=("", 10, "bold")).grid(
        row=0, column=0, columnspan=2, sticky="w")
    plan = CV.lesson_plan_for(c)
    ttk.Label(frm, text=(f"Lesson plan: {plan.title} ({plan.status})" if plan else
                         "No lesson plan for this lesson."), foreground="#555").grid(
        row=1, column=0, columnspan=2, sticky="w")
    room = ttk.Entry(frm, width=10)
    room.insert(0, c.room or "")
    notes = ttk.Entry(frm, width=50)
    notes.insert(0, c.notes or "")
    work = tk.Text(frm, width=60, height=8, wrap="word")
    work.insert("1.0", c.work_set or "")
    for i, (text, w) in enumerate((("Room", room), ("Notes", notes), ("Cover work", work)), 2):
        ttk.Label(frm, text=text).grid(row=i, column=0, sticky="nw", pady=2, padx=(0, 8))
        w.grid(row=i, column=1, sticky="w", pady=2)
    if not editor:
        room.state(["disabled"])
        notes.state(["disabled"])
    can_work = editor or CV._same(principal.username, c.absent_username)
    if not can_work:
        work.configure(state="disabled")

    def save() -> None:
        changes = {"work_set": work.get("1.0", "end").strip()}
        if editor:
            changes.update(room=room.get(), notes=notes.get())
        try:
            CV.update(c.cover_id, changes, actor=principal)
        except (CV.ValidationError, CV.PermissionDenied) as e:
            messagebox.showerror("Cover", _problems(e), parent=win)
            return
        win.destroy()
        after()
    bar = ttk.Frame(frm)
    bar.grid(row=5, column=0, columnspan=2, sticky="e", pady=(8, 0))
    ttk.Button(bar, text="Close" if not can_work else "Cancel", command=win.destroy).pack(
        side="right")
    if can_work:
        ttk.Button(bar, text="Save", command=save).pack(side="right", padx=(0, 6))


def assign_dialog(owner, principal: Principal, c: CV.Cover, after: Callable[[], None]) -> None:
    """Old 'Assign': pick from free staff (fewest covers this week first) or supply."""
    if principal.role not in COVER_EDITORS:
        messagebox.showinfo("Assign", "Only the cover manager assigns cover.", parent=owner)
        return
    try:
        people = CV.available(c.date, c.period, cover_id=c.cover_id)
    except CV.ValidationError as e:
        messagebox.showerror("Assign", _problems(e), parent=owner)
        return
    win = make_toplevel(owner.winfo_toplevel())
    win.title(f"Assign cover - {c.group_code} {c.when}")
    win.geometry("560x460")
    frm = ttk.Frame(win, padding=12)
    frm.pack(fill="both", expand=True)
    ttk.Label(frm, text=f"{c.group_code} {c.subject_code or ''} · {c.when} · room "
                        f"{c.room or '-'} · for {c.absent_name}",
              font=("", 10, "bold")).pack(anchor="w")
    ttk.Label(frm, text="Free then (fewest covers this week first; ⚠ = at the weekly limit):",
              foreground="#555").pack(anchor="w", pady=(4, 2))
    tree = _tree(frm, (("name", "Name", 220), ("kind", "Staff / supply", 100),
                       ("n", "Covers this week", 120)), height=12)
    found: dict[str, CV.Candidate] = {}
    for p in people:
        iid = tree.insert("", "end", values=(("⚠ " if p.over_limit else "") + p.name, p.kind,
                                             p.covers_this_week if p.kind == "Staff" else ""))
        found[iid] = p
    if not people:
        ttk.Label(frm, text="Nobody is free then - book supply staff (Supply staff tab).",
                  foreground="#a00").pack(anchor="w")
    other = ttk.Frame(frm)
    other.pack(fill="x", pady=(6, 0))
    ttk.Label(other, text="Or type a name:").pack(side="left")
    typed = ttk.Entry(other, width=26)
    typed.pack(side="left", padx=4)

    def save(_e=None) -> None:
        sel = tree.selection()
        try:
            if sel:
                p = found[sel[0]]
                _c, warnings = CV.assign(c.cover_id, actor=principal, username=p.username,
                                         name=p.name, supply_id=p.supply_id)
            elif typed.get().strip():
                _c, warnings = CV.assign(c.cover_id, actor=principal, name=typed.get())
            else:
                messagebox.showinfo("Assign", "Choose someone.", parent=win)
                return
        except (CV.ValidationError, CV.PermissionDenied, CV.NotFound) as e:
            messagebox.showerror("Assign", _problems(e), parent=win)
            return
        win.destroy()
        if warnings:
            messagebox.showwarning("Assign", "\n".join(warnings), parent=owner)
        after()

    tree.bind("<Double-1>", save)
    bar = ttk.Frame(frm)
    bar.pack(fill="x", pady=(8, 0))
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="right")
    ttk.Button(bar, text="Assign", command=save).pack(side="right", padx=(0, 6))


def status_dialog(owner, principal: Principal, c: CV.Cover, after: Callable[[], None]) -> None:
    win = make_toplevel(owner.winfo_toplevel())
    win.title("Set status")
    win.resizable(False, False)
    frm = ttk.Frame(win, padding=12)
    frm.pack(fill="both", expand=True)
    ttk.Label(frm, text=f"{c.group_code} {c.when} - currently {c.status}").pack(anchor="w")
    var = tk.StringVar(value=c.status)
    for s in CV.STATUSES:
        ttk.Radiobutton(frm, text=s, variable=var, value=s).pack(anchor="w")
    ttk.Label(frm, text="Note (needed to cancel, e.g. 'group on a trip'):").pack(anchor="w",
                                                                                pady=(6, 0))
    note = ttk.Entry(frm, width=50)
    note.pack(anchor="w")

    def save() -> None:
        try:
            CV.set_status(c.cover_id, var.get(), actor=principal, note=note.get() or None)
        except (CV.ValidationError, CV.PermissionDenied) as e:
            messagebox.showerror("Set status", _problems(e), parent=win)
            return
        win.destroy()
        after()
    bar = ttk.Frame(frm)
    bar.pack(fill="x", pady=(8, 0))
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="right")
    ttk.Button(bar, text="Save", command=save).pack(side="right", padx=(0, 6))


def absence_dialog(owner, principal: Principal, a: CV.Absence | None,
                   after: Callable[[], None]) -> None:
    editor = principal.role in COVER_EDITORS
    win = make_toplevel(owner.winfo_toplevel())
    win.title("Edit absence" if a else "New absence")
    win.resizable(False, False)
    frm = ttk.Frame(win, padding=12)
    frm.pack(fill="both", expand=True)
    staff = {t["display_name"] or t["username"]: t for t in TG.teacher_choices()}
    who = ttk.Combobox(frm, values=list(staff), width=30,
                       state="readonly" if editor else "disabled")
    if a:
        who.set(a.teacher_name)
    else:
        me = next((k for k, t in staff.items()
                   if t["username"].lower() == principal.username.lower()), "")
        who.set(me)
    today = _dt.date.today().isoformat()
    start, end = ttk.Entry(frm, width=12), ttk.Entry(frm, width=12)
    start.insert(0, a.start_date if a else today)
    end.insert(0, a.end_date if a else today)
    plabels = ["(all day)", *(f"{p.label} ({p.times})" for p in TT.periods())]
    p_from = ttk.Combobox(frm, values=plabels, state="readonly", width=18)
    p_to = ttk.Combobox(frm, values=plabels, state="readonly", width=18)
    p_from.set(plabels[a.from_period] if a and a.from_period else plabels[0])
    p_to.set(plabels[a.to_period] if a and a.to_period else plabels[0])
    reason = ttk.Combobox(frm, values=list(CV.REASONS), state="readonly", width=22)
    reason.set(a.reason if a else "")
    notes = ttk.Entry(frm, width=46)
    notes.insert(0, a.notes or "" if a else "")
    _grid_rows(frm, (("Who *", who), ("First day *", start), ("Last day *", end),
                     ("From period", p_from), ("To period", p_to), ("Reason *", reason),
                     ("Notes for cover", notes)))
    ttk.Label(frm, text="No medical details - this is seen by the cover team.",
              foreground="#888").grid(row=7, column=0, columnspan=2, sticky="w")

    def save() -> None:
        t = staff.get(who.get())
        data = {"teacher_username": t["username"] if t else (a.teacher_username if a else None),
                "teacher_name": who.get() or None, "start_date": start.get(),
                "end_date": end.get(), "from_period": p_from.current() or None,
                "to_period": p_to.current() or None, "reason": reason.get(),
                "notes": notes.get()}
        try:
            if a is None:
                _ab, n = CV.create_absence(data, actor=principal)
                msg = f"Recorded. {n} lesson(s) need cover."
            else:
                _ab, added, cancelled = CV.update_absence(a.absence_id, data, actor=principal)
                msg = f"Saved. {added} lesson(s) added to cover, {cancelled} cancelled."
        except (CV.ValidationError, CV.PermissionDenied) as e:
            messagebox.showerror("Absence", _problems(e), parent=win)
            return
        win.destroy()
        messagebox.showinfo("Absence", msg, parent=owner)
        after()
    _buttons(frm, 8, win, save)


def supply_dialog(owner, principal: Principal, s: CV.Supply | None,
                  after: Callable[[], None]) -> None:
    win = make_toplevel(owner.winfo_toplevel())
    win.title(f"Edit - {s.full_name}" if s else "Add supply staff")
    win.resizable(False, False)
    frm = ttk.Frame(win, padding=12)
    frm.pack(fill="both", expand=True)
    ents: dict[str, ttk.Entry] = {}
    rows = []
    for key, text, w in (("full_name", "Name *", 30), ("agency_name", "Agency", 30),
                         ("hourly_rate", "Hourly rate (£)", 8), ("email", "E-mail", 30),
                         ("phone", "Phone", 16), ("dbs_checked_on", "DBS seen on", 12),
                         ("notes", "Notes", 40)):
        e = ttk.Entry(frm, width=w)
        v = getattr(s, key) if s else None
        e.insert(0, "" if v is None else str(v))
        ents[key] = e
        rows.append((text, e))
    role = ttk.Combobox(frm, values=list(CV.SUPPLY_ROLES), state="readonly", width=20)
    role.set(s.role if s else CV.SUPPLY_ROLES[0])
    dbs = tk.BooleanVar(value=s.dbs_cleared if s else False)
    rows.insert(2, ("Role", role))
    rows.append(("DBS cleared", ttk.Checkbutton(frm, variable=dbs)))
    _grid_rows(frm, rows)

    def save() -> None:
        data = {k: e.get() for k, e in ents.items()}
        data.update(role=role.get(), dbs_cleared=dbs.get())
        try:
            if s is None:
                CV.create_supply(data, actor=principal)
            else:
                CV.update_supply(s.supply_id, data, actor=principal)
        except (CV.ValidationError, CV.PermissionDenied) as e:
            messagebox.showerror("Supply staff", _problems(e), parent=win)
            return
        win.destroy()
        after()
    _buttons(frm, len(rows), win, save)
