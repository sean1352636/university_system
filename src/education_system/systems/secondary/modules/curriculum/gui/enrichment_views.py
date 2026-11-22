"""Enrichment & Clubs screen.

The old window is the Clubs tab: "Active only" and Category filters, New,
Edit, Toggle active, Members, Delete and Refresh, with the old columns. The
old Members window keeps Add pupil, Set status, Delete and Refresh. Added:
leaders as staff logins, waiting lists that move up, consent, registers for
each meeting, cancelling a meeting and e-mailing families, exporting a club
list, history, the clubs timetable and participation (including FSM and SEN).
Rules live in :mod:`modules.curriculum.domain.enrichment`.
"""

from __future__ import annotations

import datetime as _dt
import logging
import tkinter as tk
from tkinter import ttk
from typing import Callable

from education_system.platform.delivery.gui.parented_dialogs import (
    filedialog,
    make_toplevel,
    messagebox,
)
from education_system.systems.secondary.modules.curriculum.domain import enrichment as EN
from education_system.systems.secondary.modules.curriculum.domain import teaching_groups as TG
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.gui.components import widgets as W

logger = logging.getLogger(__name__)
ALL = "All"
YEARS = ("7", "8", "9", "10", "11")
STATUS_BG = {"Active": "#ffffff", "Waitlisted": "#fff6d5", "Suspended": "#fde2e2",
             "Left": "#eeeeee", "inactive": "#eeeeee", "full": "#fff6d5",
             "P": "#e7f6ea", "A": "#fde2e2", "E": "#eeeeee", "cancelled": "#eeeeee"}
_ERRORS = (EN.ValidationError, EN.PermissionDenied, EN.NotFound)


_problems = W.problems


def _tree(parent, columns, height: int = 10, *, multi: bool = False) -> ttk.Treeview:
    return W.tree(parent, columns, height=height, select="extended" if multi else "browse",
                  stretch={"name", "pupil", "notes", "clubs"}, tags=STATUS_BG)


_text_window = W.text_window


def _grid_rows(frm, rows, start: int = 0) -> None:
    for i, (text, w) in enumerate(rows, start):
        ttk.Label(frm, text=text).grid(row=i, column=0, sticky="nw", pady=2, padx=(0, 8))
        w.grid(row=i, column=1, sticky="w", pady=2)


def _buttons(frm, row: int, win, save, label: str = "Save") -> None:
    bar = ttk.Frame(frm)
    bar.grid(row=row, column=0, columnspan=2, sticky="e", pady=(8, 0))
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="right")
    ttk.Button(bar, text=label, command=save).pack(side="right", padx=(0, 6))


def _pct(v) -> str:
    return "-" if v is None else f"{v}%"


_CLUB_COLS = (("id", "ID", 45), ("name", "Name", 200), ("cat", "Category", 80),
              ("day", "Day", 50), ("time", "Time", 90), ("room", "Room", 70),
              ("leader", "Leader", 140), ("cap", "Cap", 45), ("years", "Years", 80),
              ("active", "Active", 55), ("members", "Members", 70), ("wait", "Waiting", 60))


def _club_row(c: EN.Club) -> tuple:
    return (c.club_id, c.name, c.category, c.day_of_week or "", c.time_label, c.room or "",
            c.leader or "", c.max_capacity or "", c.years_label, "Yes" if c.is_active
            else "No", c.active_members, c.waiting or "")


class EnrichmentPage:
    TABS = ("Clubs", "Clubs timetable", "Participation")

    def __init__(self, parent: ttk.Frame, *, principal: Principal, state: dict,
                 open_pupil: Callable[[int], None] | None = None) -> None:
        self.parent, self.principal, self.state = parent, principal, state
        self.open_pupil = open_pupil
        self.editor = EN.is_editor(principal)
        activity_log.record("clubs.view")
        ttk.Label(parent, text="Enrichment & Clubs", font=("", 16, "bold")).pack(anchor="w")
        self.summary_var = tk.StringVar()
        ttk.Label(parent, textvariable=self.summary_var, foreground="#666").pack(anchor="w",
                                                                                 pady=(0, 6))
        self.book = ttk.Notebook(parent)
        self.book.pack(fill="both", expand=True)
        self.tabs = {n: ttk.Frame(self.book, padding=8) for n in self.TABS}
        for n, f in self.tabs.items():
            self.book.add(f, text=n)
        self._build_clubs(self.tabs["Clubs"])
        self.book.select(self.TABS.index(state.get("tab", "Clubs")))
        self.book.bind("<<NotebookTabChanged>>", self._on_tab)
        self._on_tab()

    def _on_tab(self, _e=None) -> None:
        name = self.TABS[self.book.index(self.book.select())]
        self.state["tab"] = name
        if name == "Clubs":
            self.refresh()
            return
        tab = self.tabs[name]
        for w in tab.winfo_children():
            w.destroy()
        try:
            {"Clubs timetable": self._draw_timetable,
             "Participation": self._draw_participation}[name](tab)
        except Exception:
            logger.exception("Enrichment tab %s failed", name)
            ttk.Label(tab, text="Couldn't load this tab - see the log.",
                      foreground="#a00").pack(anchor="w")

    # ── Clubs tab (old window) ───────────────────────────────────────

    def _build_clubs(self, tab: ttk.Frame) -> None:
        st = self.state
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        self.active_var = tk.BooleanVar(value=st.get("active_only", False))
        ttk.Checkbutton(bar, text="Active only", variable=self.active_var,
                        command=self.refresh).pack(side="left")
        self.cat_var = tk.StringVar(value=st.get("category", ALL))
        ttk.Label(bar, text="Category:").pack(side="left", padx=(8, 4))
        ttk.Combobox(bar, textvariable=self.cat_var, values=[ALL, *EN.CATEGORIES],
                     state="readonly", width=10).pack(side="left")
        for text, cmd in (("New", self.new), ("Edit", self.edit),
                          ("Toggle active", self.toggle), ("Members", self.members),
                          ("Delete", self.delete), ("Refresh", self.refresh)):
            ttk.Button(bar, text=text, command=cmd).pack(side="left", padx=2)
        bar2 = ttk.Frame(tab)
        bar2.pack(fill="x", pady=(0, 4))
        self.year_var = tk.StringVar(value=st.get("year", ALL))
        ttk.Label(bar2, text="Year:").pack(side="left", padx=(0, 4))
        ttk.Combobox(bar2, textvariable=self.year_var, values=[ALL, *YEARS],
                     state="readonly", width=5).pack(side="left")
        self.mine_var = tk.BooleanVar(value=st.get("mine", False))
        ttk.Checkbutton(bar2, text="Clubs I lead", variable=self.mine_var,
                        command=self.refresh).pack(side="left", padx=(8, 0))
        ttk.Label(bar2, text="Search:").pack(side="left", padx=(8, 4))
        self.search_var = tk.StringVar(value=st.get("search", ""))
        search = ttk.Entry(bar2, textvariable=self.search_var, width=18)
        search.pack(side="left")
        search.bind("<Return>", lambda _e: self.refresh())
        for text, cmd in (("Register…", self.take_register), ("Summary", self.show_summary),
                          ("Export list…", self.export), ("History", self.history)):
            ttk.Button(bar2, text=text, command=cmd).pack(side="left", padx=(8, 2))
        for var in (self.cat_var, self.year_var):
            var.trace_add("write", lambda *_: self.refresh())
        self.tree = _tree(tab, _CLUB_COLS, height=14)
        self.tree.bind("<<TreeviewSelect>>", lambda _e: self._detail())
        self.tree.bind("<Double-1>", lambda _e: self.members())
        box = ttk.LabelFrame(tab, text="Selected club", padding=8)
        box.pack(fill="x", pady=(8, 0))
        self.detail_var = tk.StringVar(value="(select a club to see the details)")
        ttk.Label(box, textvariable=self.detail_var, justify="left",
                  wraplength=1100).pack(anchor="w")
        self.rows: dict[str, EN.Club] = {}

    def refresh(self) -> None:
        st = self.state
        st.update(active_only=self.active_var.get(), category=self.cat_var.get(),
                  year=self.year_var.get(), mine=self.mine_var.get(),
                  search=self.search_var.get())
        cat, year = self.cat_var.get(), self.year_var.get()
        rows = EN.list_clubs(active_only=self.active_var.get(),
                             category=None if cat == ALL else cat,
                             year_group=None if year == ALL else int(year),
                             leader=self.principal.username if self.mine_var.get() else None,
                             search=self.search_var.get().strip() or None)
        self.tree.delete(*self.tree.get_children())
        self.rows = {}
        for c in rows:
            iid = str(c.club_id)
            self.rows[iid] = c
            tag = "inactive" if not c.is_active else ("full" if c.spaces is not None
                                                      and c.spaces <= 0 else "Active")
            self.tree.insert("", "end", iid=iid, values=_club_row(c), tags=(tag,))
        o = EN.overview()
        self.summary_var.set(f"Clubs: {o['total']} · active {o['active']} · active "
                             f"memberships {o['active_memberships']} · pupils in a club "
                             f"{o['pupils_in_clubs']} · waiting {o['waiting']}")
        self._detail()

    def _selected(self, quiet: bool = False) -> EN.Club | None:
        sel = self.tree.selection()
        if not sel:
            if not quiet:
                messagebox.showinfo("Enrichment & Clubs", "Select a club first.",
                                    parent=self.parent)
            return None
        return self.rows.get(sel[0])

    def _detail(self) -> None:
        c = self._selected(quiet=True)
        if c is None:
            self.detail_var.set("(select a club to see the details)")
            return
        bits = [f"{c.name} · {c.category} · {c.when}" + (f" · {c.room}" if c.room else "")
                + (f" · led by {c.leader}" if c.leader else "")
                + (f" ({c.leader_username})" if c.leader_username else ""),
                f"Years {c.years_label} · "
                + (f"{c.active_members}/{c.max_capacity} places" if c.max_capacity
                   else f"{c.active_members} members (no limit)")
                + (f" · {c.waiting} waiting" if c.waiting else "")
                + (" · parental consent needed" if c.consent_required else "")
                + (f" · £{c.cost:.2f} a term" if c.cost else "")
                + (f" · runs {c.starts_on or '?'} to {c.ends_on or '?'}"
                   if c.starts_on or c.ends_on else "")
                + ("" if c.is_active else " · INACTIVE")]
        if c.description:
            bits.append(c.description[:300])
        if c.notes:
            bits.append(f"Notes: {c.notes[:200]}")
        self.detail_var.set("\n".join(bits))

    def new(self) -> None:
        club_dialog(self.parent, self.principal, None, self.refresh)

    def edit(self) -> None:
        c = self._selected()
        if c:
            club_dialog(self.parent, self.principal, c, self.refresh)

    def toggle(self) -> None:
        c = self._selected()
        if not c:
            return
        try:
            EN.toggle_active(c.club_id, actor=self.principal)
        except _ERRORS as e:
            messagebox.showerror("Toggle active", _problems(e), parent=self.parent)
            return
        self.refresh()

    def members(self) -> None:
        c = self._selected()
        if c:
            MembersWindow(self.parent, self.principal, c, on_close=self.refresh,
                          open_pupil=self.open_pupil)

    def delete(self) -> None:
        c = self._selected()
        if not c or not messagebox.askyesno(
                "Delete club", f"Delete {c.name} and its {c.active_members + c.waiting} "
                "membership(s)?", parent=self.parent):
            return
        try:
            EN.delete_club(c.club_id, actor=self.principal)
        except _ERRORS as e:
            messagebox.showerror("Delete club", _problems(e), parent=self.parent)
            return
        self.refresh()

    def take_register(self) -> None:
        c = self._selected()
        if c:
            register_dialog(self.parent, self.principal, c, self.refresh)

    def show_summary(self) -> None:
        c = self._selected()
        if c:
            _text_window(self.parent, f"{c.name} - summary", summary_text(c.club_id))

    def export(self) -> None:
        c = self._selected()
        if not c:
            return
        path = filedialog.asksaveasfilename(parent=self.parent, defaultextension=".csv",
                                            initialfile=f"club-{c.club_id}-members.csv",
                                            filetypes=[("CSV", "*.csv")])
        if not path:
            return
        try:
            n = EN.export_members(c.club_id, path, actor=self.principal)
        except (*_ERRORS, OSError) as e:
            messagebox.showerror("Export list", _problems(e), parent=self.parent)
            return
        messagebox.showinfo("Export list", f"Saved {n} pupil(s) to {path}.",
                            parent=self.parent)

    def history(self) -> None:
        c = self._selected()
        if not c:
            return
        lines = []
        for h in EN.history(c.club_id):
            d = h["detail"]
            extra = ", ".join(f"{k}: {v}" for k, v in d.items())
            lines.append(f"{h['at']}  {h['actor']:<14} {h['action']:<14} {extra}")
        _text_window(self.parent, f"{c.name} - history", "\n".join(lines) or "No changes yet.")

    # ── Clubs timetable ──────────────────────────────────────────────

    def _draw_timetable(self, tab: ttk.Frame) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 6))
        year = tk.StringVar(value=self.state.get("tt_year", ALL))
        ttk.Label(bar, text="Clubs open to Year:").pack(side="left", padx=(0, 4))
        ttk.Combobox(bar, textvariable=year, values=[ALL, *YEARS], state="readonly",
                     width=5).pack(side="left")
        tree = _tree(tab, (("day", "Day", 60), ("time", "Time", 100), ("name", "Club", 220),
                           ("room", "Room", 80), ("leader", "Leader", 150),
                           ("years", "Years", 90), ("places", "Places", 90)), height=20)

        def fill(*_a) -> None:
            self.state["tt_year"] = year.get()
            tree.delete(*tree.get_children())
            tt = EN.timetable(year_group=None if year.get() == ALL else int(year.get()))
            for day, clubs in tt.items():
                for c in clubs:
                    places = (f"{c.spaces} free" if c.spaces and c.spaces > 0
                              else "full" if c.spaces is not None else "open")
                    tree.insert("", "end", values=(day, c.time_label, c.name, c.room or "",
                                                   c.leader or "", c.years_label, places),
                                tags=("full",) if places == "full" else ())
            if not tt:
                tree.insert("", "end", values=("", "", "No active clubs"))
        year.trace_add("write", fill)
        fill()

    # ── Participation ────────────────────────────────────────────────

    def _draw_participation(self, tab: ttk.Frame) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 6))
        year = tk.StringVar(value=self.state.get("part_year", ALL))
        ttk.Label(bar, text="Year:").pack(side="left", padx=(0, 4))
        ttk.Combobox(bar, textvariable=year, values=[ALL, *YEARS], state="readonly",
                     width=5).pack(side="left")
        info = tk.StringVar()
        ttk.Label(tab, textvariable=info, justify="left").pack(anchor="w", pady=(0, 6))
        ttk.Label(tab, text="Pupils not in any active club (double-click to open):",
                  font=("", 10, "bold")).pack(anchor="w")
        tree = _tree(tab, (("adm", "Admission no", 100), ("pupil", "Pupil", 220),
                           ("year", "Year", 45), ("form", "Form", 70), ("fsm", "FSM", 45),
                           ("sen", "SEN", 45)), height=16)
        ids: dict[str, int] = {}

        def fill(*_a) -> None:
            self.state["part_year"] = year.get()
            r = EN.participation(year_group=None if year.get() == ALL else int(year.get()))
            info.set(f"{r['taking_part']} of {r['pupils']} pupils take part in a club "
                     f"({_pct(r['all_pct'])}) · FSM pupils {_pct(r['fsm_pct'])} · SEN pupils "
                     f"{_pct(r['sen_pct'])}\nBy year: "
                     + " · ".join(f"Y{y} {_pct(v)}" for y, v in r["by_year"].items()))
            tree.delete(*tree.get_children())
            ids.clear()
            for p in r["not_in_a_club"]:
                iid = tree.insert("", "end", values=(
                    p.admission_no, f"{p.legal_last_name}, {p.preferred_name or p.legal_first_name}",
                    p.year_group, p.form_group or "", "Yes" if p.fsm_eligible else "",
                    p.sen_status if p.sen_status != "N" else ""))
                ids[iid] = p.pupil_id

        def open_row(_e=None) -> None:
            sel = tree.selection()
            if sel and self.open_pupil and sel[0] in ids:
                self.open_pupil(ids[sel[0]])
        tree.bind("<Double-1>", open_row)
        year.trace_add("write", fill)
        fill()


def draw_enrichment(parent: ttk.Frame, *, principal: Principal, state: dict | None = None,
                    open_pupil: Callable[[int], None] | None = None) -> EnrichmentPage:
    return EnrichmentPage(parent, principal=principal, state=state if state is not None else {},
                          open_pupil=open_pupil)


def summary_text(club_id: int) -> str:
    s = EN.club_summary(club_id)
    c = s["club"]
    lines = [f"{c.name} ({c.category}, {c.when})", "",
             f"Members:      {s['total']}"]
    lines += [f"  {k:<12} {v}" for k, v in s["by_status"].items()]
    lines += ["", f"Capacity:     {s['capacity'] or 'no limit'}",
              f"Spaces:       {s['spaces'] if s['spaces'] is not None else '-'}",
              f"Meetings:     {s['meetings']} with a register",
              f"Attendance:   {_pct(s['attendance_pct'])}"]
    if c.consent_required:
        lines.append(f"No consent:   {len(s['no_consent'])}"
                     + (" - " + ", ".join(m.pupil_name for m in s["no_consent"][:10])
                        if s["no_consent"] else ""))
    return "\n".join(lines)


# ── Members window (old) ─────────────────────────────────────────────

_MEMBER_COLS = (("id", "ID", 45), ("pupil", "Pupil", 180), ("year", "Yr", 35),
                ("form", "Form", 60), ("joined", "Joined", 90), ("status", "Status", 85),
                ("consent", "Consent", 85), ("att", "Attendance", 80), ("notes", "Notes", 220))


class MembersWindow:
    def __init__(self, owner, principal: Principal, club: EN.Club, *,
                 on_close: Callable[[], None],
                 open_pupil: Callable[[int], None] | None = None) -> None:
        self.principal, self.club, self.on_close = principal, club, on_close
        self.open_pupil = open_pupil
        self.win = win = make_toplevel(owner.winfo_toplevel())
        win.title(f"Members - {club.name}")
        win.geometry("980x560")
        win.protocol("WM_DELETE_WINDOW", self.close)
        frm = ttk.Frame(win, padding=10)
        frm.pack(fill="both", expand=True)
        self.head = tk.StringVar()
        ttk.Label(frm, textvariable=self.head, font=("", 11, "bold")).pack(anchor="w")
        bar = ttk.Frame(frm)
        bar.pack(fill="x", pady=6)
        for text, cmd in (("Add pupil", self.add), ("Set status", self.set_status),
                          ("Delete", self.delete), ("Refresh", self.refresh)):
            ttk.Button(bar, text=text, command=cmd).pack(side="left", padx=2)
        for text, cmd in (("Consent…", self.consent), ("Register…", self.register),
                          ("Cancel a meeting…", self.cancel_meeting),
                          ("E-mail families…", self.email), ("Open pupil", self.open)):
            ttk.Button(bar, text=text, command=cmd).pack(side="left", padx=(8, 2))
        self.tree = _tree(frm, _MEMBER_COLS, height=16)
        self.tree.bind("<Double-1>", lambda _e: self.open())
        self.rows: dict[str, EN.Member] = {}
        self.refresh()

    def close(self) -> None:
        self.win.destroy()
        self.on_close()

    def refresh(self) -> None:
        try:
            self.club = EN.get_club(self.club.club_id)
            rows = EN.list_members(self.club.club_id)
            att = EN.member_attendance(self.club.club_id)
        except Exception as e:  # noqa: BLE001
            logger.exception("Members refresh failed")
            messagebox.showerror("Enrichment & Clubs", str(e), parent=self.win)
            return
        c = self.club
        self.head.set(f"{c.name} · {c.when} · "
                      + (f"{c.active_members}/{c.max_capacity} places" if c.max_capacity
                         else f"{c.active_members} members")
                      + (f" · {c.waiting} waiting" if c.waiting else "")
                      + ("" if c.is_active else " · INACTIVE"))
        self.tree.delete(*self.tree.get_children())
        self.rows = {}
        for i, m in enumerate(rows, 1):
            iid = str(m.member_id)
            self.rows[iid] = m
            consent = (m.consent_on or "needed") if c.consent_required else ""
            pct = att.get(m.pupil_id, {}).get("pct")
            status = m.status + (f" #{i - c.active_members}" if m.status == "Waitlisted"
                                 else "")
            self.tree.insert("", "end", iid=iid, values=(
                m.member_id, m.pupil_name, m.year_group, m.form_group or "", m.joined_on,
                status, consent, _pct(pct), m.notes or ""), tags=(m.status,))

    def _selected(self) -> EN.Member | None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Members", "Select a member first.", parent=self.win)
            return None
        return self.rows.get(sel[0])

    def add(self) -> None:
        add_pupils_dialog(self.win, self.principal, self.club, self.refresh)

    def set_status(self) -> None:
        m = self._selected()
        if m:
            status_dialog(self.win, self.principal, self.club, m, self.refresh)

    def delete(self) -> None:
        m = self._selected()
        if not m or not messagebox.askyesno(
                "Delete membership", f"Remove {m.pupil_name} from {self.club.name}?\n\n"
                "(To keep the record, set their status to Left instead.)", parent=self.win):
            return
        try:
            EN.delete_member(m.member_id, actor=self.principal)
        except _ERRORS as e:
            messagebox.showerror("Delete membership", _problems(e), parent=self.win)
            return
        self.refresh()

    def consent(self) -> None:
        m = self._selected()
        if not m:
            return
        given = not m.has_consent
        if not messagebox.askyesno(
                "Consent", f"Record parental consent for {m.pupil_name} (today)?" if given
                else f"{m.pupil_name}'s consent was recorded {m.consent_on}. Withdraw it?",
                parent=self.win):
            return
        try:
            EN.record_consent(m.member_id, actor=self.principal, given=given)
        except _ERRORS as e:
            messagebox.showerror("Consent", _problems(e), parent=self.win)
            return
        self.refresh()

    def register(self) -> None:
        register_dialog(self.win, self.principal, self.club, self.refresh)

    def cancel_meeting(self) -> None:
        cancel_dialog(self.win, self.principal, self.club, self.refresh)

    def email(self) -> None:
        email_dialog(self.win, self.principal, self.club, None, None)

    def open(self) -> None:
        m = self._selected()
        if m and self.open_pupil:
            self.open_pupil(m.pupil_id)


# ── Dialogs ──────────────────────────────────────────────────────────

def club_dialog(owner, principal: Principal, club: EN.Club | None,
                after: Callable[[], None]) -> None:
    """New / Edit club: the old fields plus the leader's login, consent, cost and
    dates."""
    win = make_toplevel(owner.winfo_toplevel())
    win.title("Edit club" if club else "New club")
    win.resizable(False, False)
    frm = ttk.Frame(win, padding=12)
    frm.pack(fill="both", expand=True)
    staff = {f"{t['display_name']} ({t['username']})": t for t in TG.teacher_choices()}
    get = (lambda k: getattr(club, k)) if club else (lambda _k: None)
    v = {k: tk.StringVar(value="" if get(k) is None else str(get(k)))
         for k in ("name", "room", "leader", "max_capacity", "start_time", "end_time",
                   "starts_on", "ends_on")}
    cost = tk.StringVar(value=f"{club.cost:.2f}" if club and club.cost else "")
    cat = tk.StringVar(value=club.category if club else "Other")
    day = tk.StringVar(value=(club.day_of_week or "") if club else "")
    login = tk.StringVar(value=next((k for k, t in staff.items() if club and
                                     t["username"] == club.leader_username), ""))
    consent = tk.BooleanVar(value=bool(club and club.consent_required))
    yrs = {y: tk.BooleanVar(value=bool(club and club.eligible_years and y in club.years))
           for y in EN.YEARS}
    desc = tk.Text(frm, width=56, height=3, wrap="word")
    desc.insert("1.0", (club.description or "") if club else "")
    notes = tk.Text(frm, width=56, height=3, wrap="word")
    notes.insert("1.0", (club.notes or "") if club else "")
    year_box = ttk.Frame(frm)
    for y, var in yrs.items():
        ttk.Checkbutton(year_box, text=str(y), variable=var).pack(side="left")
    ttk.Label(year_box, text="(none ticked = all years)", foreground="#888").pack(
        side="left", padx=6)
    time_box = ttk.Frame(frm)
    ttk.Entry(time_box, textvariable=v["start_time"], width=7).pack(side="left")
    ttk.Label(time_box, text=" to ").pack(side="left")
    ttk.Entry(time_box, textvariable=v["end_time"], width=7).pack(side="left")
    ttk.Label(time_box, text="  HH:MM", foreground="#888").pack(side="left")
    date_box = ttk.Frame(frm)
    ttk.Entry(date_box, textvariable=v["starts_on"], width=12).pack(side="left")
    ttk.Label(date_box, text=" to ").pack(side="left")
    ttk.Entry(date_box, textvariable=v["ends_on"], width=12).pack(side="left")
    ttk.Label(date_box, text="  YYYY-MM-DD, optional", foreground="#888").pack(side="left")
    rows = [("Name:", ttk.Entry(frm, textvariable=v["name"], width=40)),
            ("Category:", ttk.Combobox(frm, textvariable=cat, values=EN.CATEGORIES,
                                       state="readonly", width=12)),
            ("Description:", desc),
            ("Day:", ttk.Combobox(frm, textvariable=day, values=("", *EN.DAYS),
                                  state="readonly", width=6)),
            ("Time:", time_box),
            ("Room:", ttk.Entry(frm, textvariable=v["room"], width=16)),
            ("Leader (staff login):", ttk.Combobox(frm, textvariable=login,
                                                   values=["", *staff], width=40)),
            ("Leader name:", ttk.Entry(frm, textvariable=v["leader"], width=40)),
            ("Max capacity:", ttk.Entry(frm, textvariable=v["max_capacity"], width=6)),
            ("Eligible years:", year_box),
            ("Parental consent:", ttk.Checkbutton(frm, text="Needed before attending",
                                                  variable=consent)),
            ("Cost per term (£):", ttk.Entry(frm, textvariable=cost, width=8)),
            ("Runs:", date_box),
            ("Notes:", notes)]
    _grid_rows(frm, rows)

    def save() -> None:
        pick = staff.get(login.get())
        data = {k: var.get() for k, var in v.items()}
        data.update(category=cat.get(), day_of_week=day.get(), cost=cost.get(),
                    leader_username=pick["username"] if pick else "",
                    consent_required=consent.get(),
                    eligible_years=[y for y, var in yrs.items() if var.get()],
                    description=desc.get("1.0", "end"), notes=notes.get("1.0", "end"))
        if pick and not data["leader"].strip():
            data["leader"] = pick["display_name"]
        try:
            if club:
                EN.update_club(club.club_id, data, actor=principal)
            else:
                EN.create_club(data, actor=principal)
        except _ERRORS as e:
            messagebox.showerror("Club", _problems(e), parent=win)
            return
        win.destroy()
        after()
    _buttons(frm, len(rows), win, save)


def status_dialog(owner, principal: Principal, club: EN.Club, m: EN.Member,
                  after: Callable[[], None]) -> None:
    win = make_toplevel(owner.winfo_toplevel())
    win.title("Set status")
    win.resizable(False, False)
    frm = ttk.Frame(win, padding=12)
    frm.pack(fill="both", expand=True)
    ttk.Label(frm, text=f"{m.pupil_name} in {club.name}").grid(row=0, column=0, columnspan=2,
                                                              sticky="w")
    ttk.Label(frm, text=f"Current status: {m.status}", foreground="#666").grid(
        row=1, column=0, columnspan=2, sticky="w", pady=(0, 6))
    status = tk.StringVar(value=m.status)
    note = ttk.Entry(frm, width=40)
    _grid_rows(frm, [("New status:", ttk.Combobox(frm, textvariable=status,
                                                  values=EN.STATUSES, state="readonly",
                                                  width=12)),
                     ("Reason / note:", note)], start=2)

    def save() -> None:
        try:
            _m, moved = EN.set_status(m.member_id, status.get(), actor=principal,
                                      note=note.get())
        except _ERRORS as e:
            messagebox.showerror("Set status", _problems(e), parent=win)
            return
        win.destroy()
        after()
        if moved:
            messagebox.showinfo("Waiting list", "Moved up from the waiting list: "
                                + ", ".join(x.pupil_name for x in moved), parent=owner)
    _buttons(frm, 4, win, save)


def add_pupils_dialog(owner, principal: Principal, club: EN.Club,
                      after: Callable[[], None]) -> None:
    """The old 'Add pupil', now a list of eligible pupils (or an admission no)."""
    win = make_toplevel(owner.winfo_toplevel())
    win.title(f"Add pupils - {club.name}")
    win.geometry("640x560")
    frm = ttk.Frame(win, padding=10)
    frm.pack(fill="both", expand=True)
    bar = ttk.Frame(frm)
    bar.pack(fill="x", pady=(0, 6))
    years = [str(y) for y in club.years]
    year = tk.StringVar(value=years[0])
    ttk.Label(bar, text="Year:").pack(side="left", padx=(0, 4))
    ttk.Combobox(bar, textvariable=year, values=years, state="readonly", width=5).pack(
        side="left")
    ttk.Label(bar, text="Search:").pack(side="left", padx=(8, 4))
    search = tk.StringVar()
    ent = ttk.Entry(bar, textvariable=search, width=18)
    ent.pack(side="left")
    consent = tk.BooleanVar(value=False)
    if club.consent_required:
        ttk.Checkbutton(bar, text="Consent received", variable=consent).pack(side="left",
                                                                             padx=8)
    ttk.Label(frm, text="Select one or more pupils (Ctrl/Shift-click). Pupils already in "
                        "the club aren't listed.", foreground="#888").pack(anchor="w")
    tree = _tree(frm, (("adm", "Admission no", 100), ("pupil", "Pupil", 240),
                       ("form", "Form", 70)), height=16, multi=True)
    current = {m.pupil_id for m in EN.list_members(club.club_id)
               if m.status in ("Active", "Waitlisted")}

    def fill(*_a) -> None:
        tree.delete(*tree.get_children())
        for p in P.list_pupils(year_group=int(year.get()), search=search.get().strip()
                               or None):
            if p.pupil_id in current:
                continue
            tree.insert("", "end", iid=str(p.pupil_id), values=(
                p.admission_no, f"{p.legal_last_name}, {p.preferred_name or p.legal_first_name}",
                p.form_group or ""))
    year.trace_add("write", fill)
    ent.bind("<Return>", fill)
    fill()

    def add() -> None:
        ids = [int(i) for i in tree.selection()]
        if not ids:
            messagebox.showinfo("Add pupils", "Select at least one pupil.", parent=win)
            return
        notes, errors = [], []
        for pid in ids:
            try:
                _m, warns = EN.join(club.club_id, pid, actor=principal,
                                    consent=consent.get())
                notes += warns
            except _ERRORS as e:
                errors.append(_problems(e))
        win.destroy()
        after()
        msg = "\n".join([*(f"• {w}" for w in notes), *errors])
        if msg:
            (messagebox.showwarning if errors else messagebox.showinfo)(
                "Add pupils", f"Added {len(ids) - len(errors)} of {len(ids)}.\n\n{msg}",
                parent=owner)
    b = ttk.Frame(frm)
    b.pack(fill="x", pady=(8, 0))
    ttk.Button(b, text="Cancel", command=win.destroy).pack(side="right")
    ttk.Button(b, text="Add selected", command=add).pack(side="right", padx=6)


def _date_from(owner, text: str) -> _dt.date | None:
    try:
        return _dt.date.fromisoformat(text.strip())
    except ValueError:
        messagebox.showerror("Date", "Enter the date as YYYY-MM-DD.", parent=owner)
        return None


def _last_meeting_day(club: EN.Club) -> _dt.date:
    today = _dt.date.today()
    if not club.day_of_week:
        return today
    back = (today.weekday() - EN.DAYS.index(club.day_of_week)) % 7
    return today - _dt.timedelta(days=back)


def register_dialog(owner, principal: Principal, club: EN.Club,
                    after: Callable[[], None]) -> None:
    """Take or correct a meeting's register (P / A / E per member)."""
    win = make_toplevel(owner.winfo_toplevel())
    win.title(f"Register - {club.name}")
    win.geometry("640x580")
    frm = ttk.Frame(win, padding=10)
    frm.pack(fill="both", expand=True)
    bar = ttk.Frame(frm)
    bar.pack(fill="x", pady=(0, 6))
    ttk.Label(bar, text="Date:").pack(side="left", padx=(0, 4))
    day = tk.StringVar(value=_last_meeting_day(club).isoformat())
    ent = ttk.Entry(bar, textvariable=day, width=12)
    ent.pack(side="left")
    info = tk.StringVar()
    ttk.Label(frm, textvariable=info, foreground="#666").pack(anchor="w")
    tree = _tree(frm, (("pupil", "Pupil", 240), ("form", "Form", 70),
                       ("consent", "Consent", 80), ("mark", "Mark", 80)), height=16,
                 multi=True)
    marks: dict[int, str] = {}
    names: dict[str, EN.Member] = {}

    def load(*_a) -> None:
        d = _date_from(win, day.get())
        if d is None:
            return
        try:
            rows, meeting = EN.register(club.club_id, d)
        except _ERRORS as e:
            messagebox.showerror("Register", _problems(e), parent=win)
            return
        info.set(f"{d:%A %d %B %Y} · "
                 + ("CANCELLED: " + (meeting.note or "") if meeting and meeting.cancelled
                    else f"taken by {meeting.taken_by} at {meeting.taken_at}"
                    if meeting and meeting.taken_at else "not taken yet - everyone starts "
                                                         "as Present"))
        tree.delete(*tree.get_children())
        marks.clear()
        names.clear()
        for m, mark in rows:
            mark = mark or ("" if meeting and meeting.cancelled else
                            "P" if not club.consent_required or m.has_consent else "A")
            marks[m.pupil_id] = mark
            iid = str(m.pupil_id)
            names[iid] = m
            tree.insert("", "end", iid=iid, values=(
                m.pupil_name, m.form_group or "", (m.consent_on or "needed")
                if club.consent_required else "", EN.MARKS.get(mark, "")),
                tags=(mark or "cancelled",))
    ttk.Button(bar, text="Load", command=load).pack(side="left", padx=6)
    ent.bind("<Return>", load)

    def set_mark(code: str) -> None:
        for iid in tree.selection():
            marks[int(iid)] = code
            tree.set(iid, "mark", EN.MARKS[code])
            tree.item(iid, tags=(code,))
    for code, label in EN.MARKS.items():
        ttk.Button(bar, text=f"Mark {label}", command=lambda c=code: set_mark(c)).pack(
            side="left", padx=2)
    tree.bind("<Double-1>", lambda _e: set_mark(
        {"P": "A", "A": "E", "E": "P"}.get(marks.get(int(tree.selection()[0]), "P"), "P")
        if tree.selection() else "P"))
    load()

    def save() -> None:
        d = _date_from(win, day.get())
        if d is None:
            return
        try:
            _meeting, warns = EN.save_register(club.club_id, d,
                                               {k: v for k, v in marks.items() if v},
                                               actor=principal)
        except _ERRORS as e:
            messagebox.showerror("Register", _problems(e), parent=win)
            return
        win.destroy()
        after()
        if warns:
            messagebox.showwarning("Register", "Saved. Note:\n" + "\n".join(
                f"• {w}" for w in warns), parent=owner)
    b = ttk.Frame(frm)
    b.pack(fill="x", pady=(8, 0))
    ttk.Label(b, text="Select pupils and use the Mark buttons, or double-click to cycle.",
              foreground="#888").pack(side="left")
    ttk.Button(b, text="Cancel", command=win.destroy).pack(side="right")
    ttk.Button(b, text="Save register", command=save).pack(side="right", padx=6)


def cancel_dialog(owner, principal: Principal, club: EN.Club,
                  after: Callable[[], None]) -> None:
    win = make_toplevel(owner.winfo_toplevel())
    win.title(f"Cancel a meeting - {club.name}")
    win.resizable(False, False)
    frm = ttk.Frame(win, padding=12)
    frm.pack(fill="both", expand=True)
    today = _dt.date.today()
    nxt = today
    if club.day_of_week:
        nxt = today + _dt.timedelta(days=(EN.DAYS.index(club.day_of_week) - today.weekday())
                                    % 7)
    day = tk.StringVar(value=nxt.isoformat())
    reason = tk.StringVar()
    tell = tk.BooleanVar(value=True)
    _grid_rows(frm, [("Date:", ttk.Entry(frm, textvariable=day, width=12)),
                     ("Reason:", ttk.Entry(frm, textvariable=reason, width=40)),
                     ("", ttk.Checkbutton(frm, text="E-mail the families next",
                                          variable=tell))])

    def save() -> None:
        d = _date_from(win, day.get())
        if d is None:
            return
        try:
            EN.cancel_meeting(club.club_id, d, reason.get(), actor=principal)
        except _ERRORS as e:
            messagebox.showerror("Cancel meeting", _problems(e), parent=win)
            return
        win.destroy()
        after()
        if tell.get():
            email_dialog(owner, principal, club, *EN.cancellation_text(club, d,
                                                                       reason.get().strip()))
    _buttons(frm, 3, win, save, label="Cancel meeting")


def email_dialog(owner, principal: Principal, club: EN.Club, subject: str | None,
                 body: str | None) -> None:
    win = make_toplevel(owner.winfo_toplevel())
    win.title(f"E-mail families - {club.name}")
    frm = ttk.Frame(win, padding=12)
    frm.pack(fill="both", expand=True)
    ttk.Label(frm, text=f"To the families of {club.name}'s members. Each family gets their "
                        "own copy; {contact_name} and {pupil_first_name} are filled in.",
              foreground="#888", wraplength=600, justify="left").pack(anchor="w")
    subj = tk.StringVar(value=subject or f"{club.name}")
    ttk.Entry(frm, textvariable=subj, width=80).pack(anchor="w", pady=4)
    text = tk.Text(frm, width=80, height=12, wrap="word")
    text.insert("1.0", body or "Dear {contact_name},\n\n\n\nThank you"
                + (f",\n{club.leader}" if club.leader else "."))
    text.pack(fill="both", expand=True)
    waiting = tk.BooleanVar(value=False)
    ttk.Checkbutton(frm, text="Include pupils on the waiting list",
                    variable=waiting).pack(anchor="w", pady=(4, 0))
    bar = ttk.Frame(frm)
    bar.pack(fill="x", pady=(8, 0))

    def send() -> None:
        try:
            result = EN.notify_families(club.club_id, subj.get(), text.get("1.0", "end"),
                                        actor=principal, include_waiting=waiting.get())
        except _ERRORS as e:
            messagebox.showerror("E-mail families", _problems(e), parent=win)
            return
        from education_system.systems.secondary.modules.communication.gui import email_views

        def done(_report, error) -> None:
            if error:
                messagebox.showwarning("E-mail families", f"Saved in the outbox but not "
                                       f"sent yet: {error}", parent=owner)
        email_views.deliver_in_background(owner, result.message_id, principal, done)
        no_email = result.pupils_without_email
        messagebox.showinfo("E-mail families", f"E-mail to {result.recipients} contact(s) is "
                            "on its way (see Email for delivery)."
                            + (f"\n\nNo e-mail address for: "
                               + ", ".join(p.display_name for p in no_email) if no_email
                               else ""), parent=win)
        win.destroy()
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="right")
    ttk.Button(bar, text="Send", command=send).pack(side="right", padx=6)
