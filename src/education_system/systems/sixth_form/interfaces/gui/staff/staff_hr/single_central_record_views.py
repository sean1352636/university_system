"""Tkinter views for the single central record (SCR).

:class:`SCRTab` is added to the Staff HR window (and the Safeguarding
window for the DSL). It shows one row per staff member with every
KCSIE pre-appointment check; missing or expired checks are red. Select
a row to see the check history, record a check, void one entered in
error, or set the overseas / role facts that decide which checks apply.
:func:`open_scr_window` opens it on its own.
"""

from __future__ import annotations

import datetime as _dt
import logging
import tkinter as tk
from tkinter import ttk
from education_system.systems.sixth_form.interfaces.gui._sidebar import SidebarBook
from education_system.platform.delivery.gui.parented_dialogs import messagebox, simpledialog

from education_system.platform import branding
from education_system.platform.delivery.gui import window_sizing
from education_system.systems.sixth_form.domain.staff.staff_hr import (
    single_central_record as scr,
)
from education_system.systems.sixth_form.interfaces.gui._ui import (
    grab_when_viewable,
)

logger = logging.getLogger(__name__)


def open_scr_window(parent=None) -> None:
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"Single Central Record — {branding.SYSTEM_NAME}")
    window_sizing.fit(win, "1400x900", (1200, 800))
    nb = SidebarBook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)
    SCRTab(nb)


class SCRTab:
    def __init__(self, nb: ttk.Notebook, *,
                 label: str = "Single Central Record") -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text=label)
        if not scr.can_access():
            ttk.Label(self.frame, foreground="#a33",
                      text="The single central record is restricted to the "
                           "DSL, HR and administrators.").pack(
                anchor="w", padx=8, pady=8)
            return
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        self.missing_only = tk.BooleanVar(value=False)
        self.include_left = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Missing checks only",
                        variable=self.missing_only,
                        command=self.refresh).pack(side="left")
        ttk.Checkbutton(bar, text="Include leavers",
                        variable=self.include_left,
                        command=self.refresh).pack(side="left", padx=8)
        self.summary_lbl = ttk.Label(bar, text="", foreground="#555")
        self.summary_lbl.pack(side="left", padx=12)

        actions = ttk.Frame(self.frame)
        actions.pack(fill="x", padx=8, pady=(0, 4))
        for text, cmd in (("Record check…", self._record),
                          ("Void check…", self._void),
                          ("Overseas / role…", self._profile),
                          ("Export CSV", self._export),
                          ("Refresh", self.refresh)):
            ttk.Button(actions, text=text, command=cmd).pack(
                side="left", padx=(0, 6))

        hist = ttk.LabelFrame(self.frame, text="Check history", padding=6)
        hist.pack(side="bottom", fill="x", padx=8, pady=(6, 8))
        self.hist = ttk.Treeview(hist, columns=(
            "id", "type", "on", "by", "outcome", "ref", "exp", "void"),
            show="headings", height=6)
        for key, text, w in (("id", "#", 50), ("type", "Check", 170),
                             ("on", "Checked on", 90), ("by", "By", 140),
                             ("outcome", "Outcome", 110),
                             ("ref", "Reference", 160),
                             ("exp", "Expires", 90), ("void", "Voided", 260)):
            self.hist.heading(key, text=text)
            self.hist.column(key, width=w, anchor="w")
        self.hist.tag_configure("void", foreground="#999")
        self.hist.pack(fill="x")

        cols = ("staff", "name", "role") + tuple(
            f"c{i}" for i in range(len(scr.SCR_COLUMNS))) + ("missing",)
        holder = ttk.Frame(self.frame)
        holder.pack(fill="both", expand=True, padx=8)
        self.tree = ttk.Treeview(holder, columns=cols, show="headings",
                                 height=16)
        for key, text, w in (("staff", "Staff ID", 80), ("name", "Name", 150),
                             ("role", "Role", 130)):
            self.tree.heading(key, text=text)
            self.tree.column(key, width=w, anchor="w")
        for i, col in enumerate(scr.SCR_COLUMNS):
            self.tree.heading(f"c{i}", text=col)
            self.tree.column(f"c{i}", width=92, anchor="w")
        self.tree.heading("missing", text="Missing")
        self.tree.column("missing", width=260, anchor="w")
        self.tree.tag_configure("gap", foreground="#a33")
        self.tree.tag_configure("ok", foreground="#0d6b2a")
        vs = ttk.Scrollbar(holder, orient="vertical", command=self.tree.yview)
        hs = ttk.Scrollbar(holder, orient="horizontal",
                           command=self.tree.xview)
        self.tree.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)
        holder.columnconfigure(0, weight=1)
        holder.rowconfigure(0, weight=1)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vs.grid(row=0, column=1, sticky="ns")
        hs.grid(row=1, column=0, sticky="ew")
        self.tree.bind("<<TreeviewSelect>>", lambda _e: self._history())


    def refresh(self) -> None:
        self.tree.delete(*self.tree.get_children())
        try:
            rows = scr.scr_report(include_left=self.include_left.get(),
                                  missing_only=self.missing_only.get())
        except Exception as e:
            logger.exception("SCR report failed")
            messagebox.showerror("SCR", str(e), parent=self.frame)
            return
        gaps = 0
        for r in rows:
            if r.missing:
                gaps += 1
            self.tree.insert("", "end", iid=r.staff_id,
                             tags=(("gap",) if r.missing else ("ok",)),
                             values=(r.staff_id, r.name, r.role,
                                     *[r.checks[c].label
                                       for c in scr.SCR_COLUMNS],
                                     "; ".join(r.missing) or "Complete"))
        self.summary_lbl.configure(
            text=f"{len(rows)} staff · {gaps} with missing / expired checks")

    def _selected(self) -> str | None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("SCR", "Select a staff member first.",
                                parent=self.frame)
            return None
        return sel[0]

    def _history(self) -> None:
        sel = self.tree.selection()
        self.hist.delete(*self.hist.get_children())
        if not sel:
            return
        for c in scr.checks_for_staff(sel[0]):
            self.hist.insert("", "end", iid=str(c.check_id),
                             tags=(("void",) if c.voided else ()),
                             values=(c.check_id, c.check_type, c.checked_on,
                                     c.checked_by, c.outcome,
                                     c.reference or "", c.expires_on or "",
                                     (f"{c.voided_reason} ({c.voided_by})"
                                      if c.voided else "")))

    def _record(self) -> None:
        sid = self._selected()
        if sid is None:
            return
        win = tk.Toplevel(self.frame)
        win.title(f"Record SCR check — {sid}")
        win.transient(self.frame.winfo_toplevel())
        grab_when_viewable(win)
        frm = ttk.Frame(win, padding=12)
        frm.pack(fill="both", expand=True)
        row = scr.scr_for_staff(sid)
        first_gap = next(iter(row.missing), scr.CHECK_TYPES[0])
        vars_ = {
            "check_type": tk.StringVar(
                value=first_gap if first_gap in scr.CHECK_TYPES
                else scr.CHECK_TYPES[0]),
            "checked_on": tk.StringVar(value=_dt.date.today().isoformat()),
            "checked_by": tk.StringVar(),
            "outcome": tk.StringVar(value="Clear"),
            "reference": tk.StringVar(),
            "expires_on": tk.StringVar(),
            "notes": tk.StringVar(),
        }
        specs = (("check_type", "Check *", scr.CHECK_TYPES),
                 ("checked_on", "Checked on *", None),
                 ("checked_by", "Checked by (blank = you)", None),
                 ("outcome", "Outcome", scr.OUTCOMES),
                 ("reference", "Document / reference", None),
                 ("expires_on", "Expires on (e.g. visa)", None),
                 ("notes", "Notes", None))
        for i, (key, label, options) in enumerate(specs):
            ttk.Label(frm, text=label).grid(row=i, column=0, sticky="e",
                                            padx=(0, 8), pady=2)
            if options:
                ttk.Combobox(frm, textvariable=vars_[key],
                             values=list(options), state="readonly",
                             width=30).grid(row=i, column=1, sticky="w")
            else:
                ttk.Entry(frm, textvariable=vars_[key], width=34).grid(
                    row=i, column=1, sticky="w")

        def save() -> None:
            try:
                scr.record_check(sid, **{k: v.get() for k, v in
                                         vars_.items()})
            except (scr.ValidationError, scr.access.AccessDenied) as e:
                messagebox.showerror("Cannot save", str(e), parent=win)
                return
            win.destroy()
            self.refresh()
            self.tree.selection_set(sid)

        ttk.Button(frm, text="Save", command=save).grid(
            row=len(specs), column=1, sticky="e", pady=(8, 0))

    def _void(self) -> None:
        sel = self.hist.selection()
        if not sel:
            messagebox.showinfo("SCR", "Select a check in the history first.",
                                parent=self.frame)
            return
        reason = simpledialog.askstring(
            "Void check", "Why was this check entered in error?",
            parent=self.frame)
        if not reason:
            return
        try:
            scr.void_check(int(sel[0]), reason=reason)
        except Exception as e:
            messagebox.showerror("SCR", str(e), parent=self.frame)
            return
        self.refresh()

    def _profile(self) -> None:
        sid = self._selected()
        if sid is None:
            return
        prof = scr.get_profile(sid)
        win = tk.Toplevel(self.frame)
        win.title(f"Which checks apply — {sid}")
        win.transient(self.frame.winfo_toplevel())
        grab_when_viewable(win)
        frm = ttk.Frame(win, padding=12)
        frm.pack(fill="both", expand=True)
        overseas = tk.BooleanVar(value=prof.lived_overseas)
        countries = tk.StringVar(value=prof.overseas_countries or "")
        tri = ("From job title", "Yes", "No")

        def tri_val(v: bool | None) -> str:
            return tri[0] if v is None else (tri[1] if v else tri[2])

        teaching = tk.StringVar(value=tri_val(prof.teaching_role))
        management = tk.StringVar(value=tri_val(prof.management_role))
        notes = tk.StringVar(value=prof.notes or "")
        ttk.Checkbutton(frm, text="Lived or worked overseas (overseas checks "
                                  "apply)", variable=overseas).grid(
            row=0, column=0, columnspan=2, sticky="w")
        for i, (label, w) in enumerate((
                ("Countries", ttk.Entry(frm, textvariable=countries,
                                        width=34)),
                ("Teaching role (prohibition check)",
                 ttk.Combobox(frm, textvariable=teaching, values=tri,
                              state="readonly", width=16)),
                ("Management role (section 128)",
                 ttk.Combobox(frm, textvariable=management, values=tri,
                              state="readonly", width=16)),
                ("Notes", ttk.Entry(frm, textvariable=notes, width=34)),
        ), start=1):
            ttk.Label(frm, text=label).grid(row=i, column=0, sticky="e",
                                            padx=(0, 8), pady=2)
            w.grid(row=i, column=1, sticky="w")

        def from_tri(s: str) -> bool | None:
            return None if s == tri[0] else s == tri[1]

        def save() -> None:
            try:
                scr.set_profile(sid, lived_overseas=overseas.get(),
                                overseas_countries=countries.get(),
                                teaching_role=from_tri(teaching.get()),
                                management_role=from_tri(management.get()),
                                notes=notes.get())
            except Exception as e:
                messagebox.showerror("Cannot save", str(e), parent=win)
                return
            win.destroy()
            self.refresh()

        ttk.Button(frm, text="Save", command=save).grid(
            row=6, column=1, sticky="e", pady=(8, 0))

    def _export(self) -> None:
        try:
            path = scr.export_scr_csv(include_left=self.include_left.get())
        except Exception as e:
            messagebox.showerror("Export", str(e), parent=self.frame)
            return
        messagebox.showinfo("Export", f"Single central record written to:\n"
                                      f"{path}", parent=self.frame)
