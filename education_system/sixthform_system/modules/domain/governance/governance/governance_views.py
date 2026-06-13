"""GUI panels for the Sixth Form Governance register.

Three-tab notebook:

  * Governors — filterable list with row actions (edit, delete) and a
                top-level "New governor" form.
  * Meetings  — filterable list with edit / mark-held / delete row
                actions and a "New meeting" form.
  * Summary   — headline tiles and breakdown trees.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any

from education_system.sixthform_system.modules.domain.governance.governance import governance as data
from education_system.sixthform_system.modules.domain.governance.governance.governance import (
    DEFAULT_GOVERNOR_ROLE,
    DEFAULT_GOVERNOR_STATUS,
    DEFAULT_MEETING_KIND,
    DEFAULT_MEETING_STATUS,
    GOVERNOR_ROLES,
    GOVERNOR_STATUSES,
    Governor,
    Meeting,
    MEETING_KINDS,
    MEETING_STATUSES,
    ValidationError,
)

logger = logging.getLogger(__name__)


def _clear(gui) -> ttk.Frame:
    for w in gui.content_frame.winfo_children():
        w.destroy()
    return gui.content_frame


def _heading(parent, text: str) -> None:
    ttk.Label(parent, text=text, font=("", 16, "bold")).pack(
        anchor="w", pady=(0, 8))


def open_governance_window(gui) -> None:
    frame = _clear(gui)
    _heading(frame, "Governance")

    nb = ttk.Notebook(frame)
    nb.pack(fill="both", expand=True)

    governors_tab = ttk.Frame(nb, padding=8)
    meetings_tab = ttk.Frame(nb, padding=8)
    summary_tab = ttk.Frame(nb, padding=8)
    nb.add(governors_tab, text="Governors")
    nb.add(meetings_tab,  text="Meetings")
    nb.add(summary_tab,   text="Summary")

    state: dict[str, Any] = {
        "refresh_governors": None,
        "refresh_meetings": None,
        "refresh_summary": None,
    }

    def refresh_all() -> None:
        for k in state:
            if state[k]:
                state[k]()

    _build_governors_tab(gui, governors_tab, state, refresh_all)
    _build_meetings_tab(gui, meetings_tab, state, refresh_all)
    _build_summary_tab(gui, summary_tab, state)


# ── Governors tab ──────────────────────────────────────────────────

def _build_governors_tab(gui, parent: ttk.Frame, state: dict,
                           refresh_all) -> None:
    filt = ttk.Frame(parent)
    filt.pack(anchor="w", fill="x", pady=(0, 6))

    role_var = tk.StringVar()
    status_var = tk.StringVar()
    query_var = tk.StringVar()

    ttk.Label(filt, text="Role:").pack(side="left")
    ttk.Combobox(filt, textvariable=role_var,
                  values=["", *GOVERNOR_ROLES], state="readonly", width=18
                  ).pack(side="left", padx=(4, 10))
    ttk.Label(filt, text="Status:").pack(side="left")
    ttk.Combobox(filt, textvariable=status_var,
                  values=["", *GOVERNOR_STATUSES], state="readonly", width=12
                  ).pack(side="left", padx=(4, 10))
    ttk.Label(filt, text="Search:").pack(side="left")
    ttk.Entry(filt, textvariable=query_var, width=20
              ).pack(side="left", padx=(4, 4))

    table_holder = ttk.Frame(parent)
    table_holder.pack(fill="both", expand=True, pady=(2, 4))
    footer = ttk.Label(parent, text="", foreground="#555")
    footer.pack(anchor="w")
    actions = ttk.Frame(parent)
    actions.pack(anchor="w", pady=(6, 6))

    new_form = ttk.LabelFrame(parent, text="New governor", padding=6)
    new_form.pack(fill="x")

    n_name = tk.StringVar()
    n_role = tk.StringVar(value=DEFAULT_GOVERNOR_ROLE)
    n_email = tk.StringVar()
    n_term_start = tk.StringVar()
    n_term_end = tk.StringVar()
    n_status = tk.StringVar(value=DEFAULT_GOVERNOR_STATUS)

    row1 = ttk.Frame(new_form)
    row1.pack(fill="x", pady=2)
    ttk.Label(row1, text="Name:").pack(side="left")
    ttk.Entry(row1, textvariable=n_name, width=24
              ).pack(side="left", padx=(4, 12))
    ttk.Label(row1, text="Role:").pack(side="left")
    ttk.Combobox(row1, textvariable=n_role, values=list(GOVERNOR_ROLES),
                  state="readonly", width=18
                  ).pack(side="left", padx=(4, 12))
    ttk.Label(row1, text="Status:").pack(side="left")
    ttk.Combobox(row1, textvariable=n_status, values=list(GOVERNOR_STATUSES),
                  state="readonly", width=12
                  ).pack(side="left", padx=(4, 0))

    row2 = ttk.Frame(new_form)
    row2.pack(fill="x", pady=2)
    ttk.Label(row2, text="Email:").pack(side="left")
    ttk.Entry(row2, textvariable=n_email, width=26
              ).pack(side="left", padx=(4, 12))
    ttk.Label(row2, text="Term start:").pack(side="left")
    ttk.Entry(row2, textvariable=n_term_start, width=12
              ).pack(side="left", padx=(4, 12))
    ttk.Label(row2, text="Term end:").pack(side="left")
    ttk.Entry(row2, textvariable=n_term_end, width=12
              ).pack(side="left", padx=(4, 12))

    def _create_governor() -> None:
        try:
            data.create_governor({
                "full_name": n_name.get(),
                "role": n_role.get(),
                "email": n_email.get() or None,
                "term_start": n_term_start.get() or None,
                "term_end": n_term_end.get() or None,
                "status": n_status.get(),
            })
        except ValidationError as e:
            messagebox.showerror("Cannot save", str(e), parent=gui.root)
            return
        except Exception as e:
            logger.exception("create_governor crashed")
            messagebox.showerror("Error", str(e), parent=gui.root)
            return
        n_name.set("")
        n_email.set("")
        n_term_start.set("")
        n_term_end.set("")
        refresh_all()

    ttk.Button(new_form, text="Create governor", command=_create_governor
                ).pack(anchor="w", pady=(4, 0))

    def refresh() -> None:
        for w in table_holder.winfo_children():
            w.destroy()
        for w in actions.winfo_children():
            w.destroy()
        try:
            rows = data.list_governors(
                role=role_var.get() or None,
                status=status_var.get() or None,
                query=query_var.get().strip() or None,
            )
        except ValidationError as e:
            ttk.Label(table_holder, text=str(e),
                      foreground="#a33").pack(anchor="w")
            return

        cols = ("id", "name", "role", "email", "term", "status")
        headings = {
            "id":     ("#",         50),
            "name":   ("Name",      200),
            "role":   ("Role",      150),
            "email":  ("Email",     200),
            "term":   ("Term end",  100),
            "status": ("Status",    100),
        }
        tree = ttk.Treeview(table_holder, columns=cols,
                              show="headings", height=14)
        for col in cols:
            text, width = headings[col]
            tree.heading(col, text=text)
            tree.column(col, width=width, anchor="w")
        vs = ttk.Scrollbar(table_holder, orient="vertical",
                            command=tree.yview)
        tree.configure(yscrollcommand=vs.set)
        tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        for g in rows:
            tree.insert("", "end", iid=str(g.governor_id), values=(
                g.governor_id, g.full_name, g.role,
                g.email or "", g.term_end or "—", g.status,
            ))
        footer.configure(text=f"{len(rows)} governor(s).")

        def _sel() -> int | None:
            sel = tree.selection()
            return int(sel[0]) if sel else None

        def _edit() -> None:
            gid = _sel()
            if gid is None:
                messagebox.showinfo("No selection", "Pick a governor first.",
                                      parent=gui.root)
                return
            _edit_governor_dialog(gui, gid, refresh_all)

        def _delete() -> None:
            gid = _sel()
            if gid is None:
                messagebox.showinfo("No selection", "Pick a governor first.",
                                      parent=gui.root)
                return
            existing = data.get_governor(gid)
            if existing is None:
                refresh_all()
                return
            if not messagebox.askyesno(
                    "Delete governor",
                    f"Delete '#{gid} — {existing.full_name}'?",
                    parent=gui.root):
                return
            try:
                data.delete_governor(gid)
            except Exception as e:
                logger.exception("delete_governor crashed")
                messagebox.showerror("Error", str(e), parent=gui.root)
                return
            refresh_all()

        ttk.Button(actions, text="Edit", command=_edit
                    ).pack(side="left", padx=(0, 6))
        ttk.Button(actions, text="Delete", command=_delete
                    ).pack(side="left", padx=(0, 6))
        ttk.Button(actions, text="Refresh", command=refresh_all
                    ).pack(side="left", padx=(12, 0))
        gui.status_var.set(f"Governance: {len(rows)} governor match(es)")

    ttk.Button(filt, text="Apply", command=refresh
                ).pack(side="left", padx=(8, 0))
    ttk.Button(filt, text="Clear",
                command=lambda: (role_var.set(""), status_var.set(""),
                                  query_var.set(""), refresh())
                ).pack(side="left", padx=(4, 0))

    state["refresh_governors"] = refresh
    refresh()


def _edit_governor_dialog(gui, gid: int, refresh_all) -> None:
    existing = data.get_governor(gid)
    if existing is None:
        return
    win = tk.Toplevel(gui.root)
    win.title(f"Edit governor #{gid}")
    win.transient(gui.root)
    win.after_idle(win.grab_set)
    frm = ttk.Frame(win, padding=12)
    frm.grid()

    name = tk.StringVar(value=existing.full_name)
    role = tk.StringVar(value=existing.role)
    email = tk.StringVar(value=existing.email or "")
    phone = tk.StringVar(value=existing.phone or "")
    ts = tk.StringVar(value=existing.term_start or "")
    te = tk.StringVar(value=existing.term_end or "")
    status = tk.StringVar(value=existing.status)
    notes = tk.StringVar(value=existing.notes or "")

    rows = [
        ("Name:", name, "entry", None),
        ("Role:", role, "combo", list(GOVERNOR_ROLES)),
        ("Email:", email, "entry", None),
        ("Phone:", phone, "entry", None),
        ("Term start:", ts, "date", None),
        ("Term end:", te, "date", None),
        ("Status:", status, "combo", list(GOVERNOR_STATUSES)),
        ("Notes:", notes, "entry", None),
    ]
    for i, (label, var, kind, values) in enumerate(rows):
        ttk.Label(frm, text=label).grid(row=i, column=0, sticky="e",
                                          padx=(0, 6), pady=2)
        if kind == "combo":
            ttk.Combobox(frm, textvariable=var, values=values,
                          state="readonly", width=22
                          ).grid(row=i, column=1, sticky="w", pady=2)
        elif kind == "date":
            ttk.Entry(frm, textvariable=var, width=18
                      ).grid(row=i, column=1, sticky="w", pady=2)
        else:
            ttk.Entry(frm, textvariable=var, width=38
                      ).grid(row=i, column=1, sticky="w", pady=2)

    def save() -> None:
        try:
            data.update_governor(gid, {
                "full_name": name.get(), "role": role.get(),
                "email": email.get() or None, "phone": phone.get() or None,
                "term_start": ts.get() or None, "term_end": te.get() or None,
                "status": status.get(), "notes": notes.get() or None,
            })
        except ValidationError as e:
            messagebox.showerror("Cannot save", str(e), parent=win)
            return
        except Exception as e:
            logger.exception("update_governor crashed")
            messagebox.showerror("Error", str(e), parent=win)
            return
        win.destroy()
        refresh_all()

    bar = ttk.Frame(frm)
    bar.grid(row=len(rows), column=0, columnspan=2, pady=(10, 0), sticky="e")
    ttk.Button(bar, text="Save", command=save).pack(side="left", padx=(0, 6))
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="left")


# ── Meetings tab ───────────────────────────────────────────────────

def _build_meetings_tab(gui, parent: ttk.Frame, state: dict,
                          refresh_all) -> None:
    filt = ttk.Frame(parent)
    filt.pack(anchor="w", fill="x", pady=(0, 6))

    kind_var = tk.StringVar()
    status_var = tk.StringVar()
    query_var = tk.StringVar()

    ttk.Label(filt, text="Kind:").pack(side="left")
    ttk.Combobox(filt, textvariable=kind_var,
                  values=["", *MEETING_KINDS], state="readonly", width=14
                  ).pack(side="left", padx=(4, 10))
    ttk.Label(filt, text="Status:").pack(side="left")
    ttk.Combobox(filt, textvariable=status_var,
                  values=["", *MEETING_STATUSES], state="readonly", width=12
                  ).pack(side="left", padx=(4, 10))
    ttk.Label(filt, text="Search:").pack(side="left")
    ttk.Entry(filt, textvariable=query_var, width=22
              ).pack(side="left", padx=(4, 4))

    table_holder = ttk.Frame(parent)
    table_holder.pack(fill="both", expand=True, pady=(2, 4))
    footer = ttk.Label(parent, text="", foreground="#555")
    footer.pack(anchor="w")
    actions = ttk.Frame(parent)
    actions.pack(anchor="w", pady=(6, 6))

    new_form = ttk.LabelFrame(parent, text="New meeting", padding=6)
    new_form.pack(fill="x")

    m_date = tk.StringVar()
    m_kind = tk.StringVar(value=DEFAULT_MEETING_KIND)
    m_title = tk.StringVar()
    m_chair = tk.StringVar()
    m_status = tk.StringVar(value=DEFAULT_MEETING_STATUS)

    row1 = ttk.Frame(new_form)
    row1.pack(fill="x", pady=2)
    ttk.Label(row1, text="Date:").pack(side="left")
    ttk.Entry(row1, textvariable=m_date, width=14
              ).pack(side="left", padx=(4, 12))
    ttk.Label(row1, text="Kind:").pack(side="left")
    ttk.Combobox(row1, textvariable=m_kind, values=list(MEETING_KINDS),
                  state="readonly", width=14
                  ).pack(side="left", padx=(4, 12))
    ttk.Label(row1, text="Status:").pack(side="left")
    ttk.Combobox(row1, textvariable=m_status, values=list(MEETING_STATUSES),
                  state="readonly", width=12
                  ).pack(side="left", padx=(4, 0))

    row2 = ttk.Frame(new_form)
    row2.pack(fill="x", pady=2)
    ttk.Label(row2, text="Title:").pack(side="left")
    ttk.Entry(row2, textvariable=m_title, width=40
              ).pack(side="left", padx=(4, 12))
    ttk.Label(row2, text="Chair:").pack(side="left")
    ttk.Entry(row2, textvariable=m_chair, width=22
              ).pack(side="left", padx=(4, 0))

    def _create_meeting() -> None:
        try:
            data.create_meeting({
                "meeting_date": m_date.get(), "kind": m_kind.get(),
                "title": m_title.get(), "chair": m_chair.get() or None,
                "status": m_status.get(),
            })
        except ValidationError as e:
            messagebox.showerror("Cannot save", str(e), parent=gui.root)
            return
        except Exception as e:
            logger.exception("create_meeting crashed")
            messagebox.showerror("Error", str(e), parent=gui.root)
            return
        m_date.set("")
        m_title.set("")
        m_chair.set("")
        refresh_all()

    ttk.Button(new_form, text="Create meeting", command=_create_meeting
                ).pack(anchor="w", pady=(4, 0))

    def refresh() -> None:
        for w in table_holder.winfo_children():
            w.destroy()
        for w in actions.winfo_children():
            w.destroy()
        try:
            rows = data.list_meetings(
                kind=kind_var.get() or None,
                status=status_var.get() or None,
                query=query_var.get().strip() or None,
            )
        except ValidationError as e:
            ttk.Label(table_holder, text=str(e),
                      foreground="#a33").pack(anchor="w")
            return

        cols = ("id", "date", "kind", "title", "chair",
                "attendees", "status")
        headings = {
            "id":        ("#",          50),
            "date":      ("Date",      100),
            "kind":      ("Kind",      120),
            "title":     ("Title",     280),
            "chair":     ("Chair",     150),
            "attendees": ("Att.",       60),
            "status":    ("Status",    100),
        }
        tree = ttk.Treeview(table_holder, columns=cols,
                              show="headings", height=14)
        for col in cols:
            text, width = headings[col]
            tree.heading(col, text=text)
            tree.column(col, width=width, anchor="w")
        vs = ttk.Scrollbar(table_holder, orient="vertical",
                            command=tree.yview)
        tree.configure(yscrollcommand=vs.set)
        tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        for m in rows:
            tree.insert("", "end", iid=str(m.meeting_id), values=(
                m.meeting_id, m.meeting_date, m.kind, m.title,
                m.chair or "", m.attendees, m.status,
            ))
        footer.configure(text=f"{len(rows)} meeting(s).")

        def _sel() -> int | None:
            sel = tree.selection()
            return int(sel[0]) if sel else None

        def _edit() -> None:
            mid = _sel()
            if mid is None:
                messagebox.showinfo("No selection", "Pick a meeting first.",
                                      parent=gui.root)
                return
            _edit_meeting_dialog(gui, mid, refresh_all)

        def _held() -> None:
            mid = _sel()
            if mid is None:
                messagebox.showinfo("No selection", "Pick a meeting first.",
                                      parent=gui.root)
                return
            _mark_held_dialog(gui, mid, refresh_all)

        def _delete() -> None:
            mid = _sel()
            if mid is None:
                messagebox.showinfo("No selection", "Pick a meeting first.",
                                      parent=gui.root)
                return
            existing = data.get_meeting(mid)
            if existing is None:
                refresh_all()
                return
            if not messagebox.askyesno(
                    "Delete meeting",
                    f"Delete '#{mid} — {existing.title}'?",
                    parent=gui.root):
                return
            try:
                data.delete_meeting(mid)
            except Exception as e:
                logger.exception("delete_meeting crashed")
                messagebox.showerror("Error", str(e), parent=gui.root)
                return
            refresh_all()

        ttk.Button(actions, text="Edit", command=_edit
                    ).pack(side="left", padx=(0, 6))
        ttk.Button(actions, text="Mark held", command=_held
                    ).pack(side="left", padx=(0, 6))
        ttk.Button(actions, text="Delete", command=_delete
                    ).pack(side="left", padx=(0, 6))
        ttk.Button(actions, text="Refresh", command=refresh_all
                    ).pack(side="left", padx=(12, 0))
        gui.status_var.set(f"Governance: {len(rows)} meeting match(es)")

    ttk.Button(filt, text="Apply", command=refresh
                ).pack(side="left", padx=(8, 0))
    ttk.Button(filt, text="Clear",
                command=lambda: (kind_var.set(""), status_var.set(""),
                                  query_var.set(""), refresh())
                ).pack(side="left", padx=(4, 0))

    state["refresh_meetings"] = refresh
    refresh()


def _edit_meeting_dialog(gui, mid: int, refresh_all) -> None:
    existing = data.get_meeting(mid)
    if existing is None:
        return
    win = tk.Toplevel(gui.root)
    win.title(f"Edit meeting #{mid}")
    win.transient(gui.root)
    win.after_idle(win.grab_set)
    frm = ttk.Frame(win, padding=12)
    frm.grid()

    date_v = tk.StringVar(value=existing.meeting_date)
    kind_v = tk.StringVar(value=existing.kind)
    title_v = tk.StringVar(value=existing.title)
    chair_v = tk.StringVar(value=existing.chair or "")
    att_v = tk.StringVar(value=str(existing.attendees))
    minutes_v = tk.StringVar(value=existing.minutes_ref or "")
    decisions_v = tk.StringVar(value=existing.decisions or "")
    status_v = tk.StringVar(value=existing.status)

    rows = [
        ("Date:", date_v, "date", None),
        ("Kind:", kind_v, "combo", list(MEETING_KINDS)),
        ("Title:", title_v, "entry", None),
        ("Chair:", chair_v, "entry", None),
        ("Attendees:", att_v, "date", None),
        ("Minutes ref:", minutes_v, "entry", None),
        ("Decisions:", decisions_v, "entry", None),
        ("Status:", status_v, "combo", list(MEETING_STATUSES)),
    ]
    for i, (label, var, kind, values) in enumerate(rows):
        ttk.Label(frm, text=label).grid(row=i, column=0, sticky="e",
                                          padx=(0, 6), pady=2)
        if kind == "combo":
            ttk.Combobox(frm, textvariable=var, values=values,
                          state="readonly", width=22
                          ).grid(row=i, column=1, sticky="w", pady=2)
        elif kind == "date":
            ttk.Entry(frm, textvariable=var, width=18
                      ).grid(row=i, column=1, sticky="w", pady=2)
        else:
            ttk.Entry(frm, textvariable=var, width=42
                      ).grid(row=i, column=1, sticky="w", pady=2)

    def save() -> None:
        try:
            data.update_meeting(mid, {
                "meeting_date": date_v.get(), "kind": kind_v.get(),
                "title": title_v.get(),
                "chair": chair_v.get() or None,
                "attendees": att_v.get(),
                "minutes_ref": minutes_v.get() or None,
                "decisions": decisions_v.get() or None,
                "status": status_v.get(),
            })
        except ValidationError as e:
            messagebox.showerror("Cannot save", str(e), parent=win)
            return
        except Exception as e:
            logger.exception("update_meeting crashed")
            messagebox.showerror("Error", str(e), parent=win)
            return
        win.destroy()
        refresh_all()

    bar = ttk.Frame(frm)
    bar.grid(row=len(rows), column=0, columnspan=2, pady=(10, 0), sticky="e")
    ttk.Button(bar, text="Save", command=save).pack(side="left", padx=(0, 6))
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="left")


def _mark_held_dialog(gui, mid: int, refresh_all) -> None:
    existing = data.get_meeting(mid)
    if existing is None:
        return
    win = tk.Toplevel(gui.root)
    win.title(f"Mark meeting held — #{mid}")
    win.transient(gui.root)
    win.after_idle(win.grab_set)
    frm = ttk.Frame(win, padding=12)
    frm.grid()
    ttk.Label(frm, text=existing.title, foreground="#555"
              ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))

    att = tk.StringVar(value=str(existing.attendees))
    minutes = tk.StringVar(value=existing.minutes_ref or "")
    decisions = tk.StringVar(value=existing.decisions or "")

    ttk.Label(frm, text="Attendees:").grid(row=1, column=0, sticky="e",
                                             padx=(0, 6), pady=2)
    ttk.Entry(frm, textvariable=att, width=10
              ).grid(row=1, column=1, sticky="w", pady=2)
    ttk.Label(frm, text="Minutes ref:").grid(row=2, column=0, sticky="e",
                                               padx=(0, 6), pady=2)
    ttk.Entry(frm, textvariable=minutes, width=38
              ).grid(row=2, column=1, sticky="w", pady=2)
    ttk.Label(frm, text="Decisions:").grid(row=3, column=0, sticky="e",
                                             padx=(0, 6), pady=2)
    ttk.Entry(frm, textvariable=decisions, width=42
              ).grid(row=3, column=1, sticky="w", pady=2)

    def save() -> None:
        try:
            atts: int | None = int(att.get()) if att.get() else None
        except ValueError:
            messagebox.showerror("Cannot save",
                                  "Attendees must be a whole number.",
                                  parent=win)
            return
        try:
            data.mark_held(mid, attendees=atts,
                             minutes_ref=minutes.get() or None,
                             decisions=decisions.get() or None)
        except ValidationError as e:
            messagebox.showerror("Cannot save", str(e), parent=win)
            return
        except Exception as e:
            logger.exception("mark_held crashed")
            messagebox.showerror("Error", str(e), parent=win)
            return
        win.destroy()
        refresh_all()

    bar = ttk.Frame(frm)
    bar.grid(row=4, column=0, columnspan=2, pady=(10, 0), sticky="e")
    ttk.Button(bar, text="Mark held", command=save
                ).pack(side="left", padx=(0, 6))
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="left")


# ── Summary tab ────────────────────────────────────────────────────

def _build_summary_tab(gui, parent: ttk.Frame, state: dict) -> None:
    tiles = ttk.Frame(parent)
    tiles.pack(anchor="w", fill="x", pady=(0, 12))

    gov_var = tk.StringVar(value="—")
    active_var = tk.StringVar(value="—")
    expiring_var = tk.StringVar(value="—")
    sched_var = tk.StringVar(value="—")
    held_var = tk.StringVar(value="—")
    next_var = tk.StringVar(value="(none)")

    def _tile(col: int, label: str, var: tk.StringVar,
               hint: str, fg: str = "#222") -> None:
        tile = ttk.LabelFrame(tiles, padding=10)
        tile.grid(row=0, column=col, padx=4, sticky="nsew")
        tiles.columnconfigure(col, weight=1, uniform="t")
        ttk.Label(tile, text=label, foreground="#666").pack(anchor="w")
        ttk.Label(tile, textvariable=var, font=("", 20, "bold"),
                   foreground=fg).pack(anchor="w", pady=(2, 0))
        ttk.Label(tile, text=hint, foreground="#888",
                   font=("", 9)).pack(anchor="w")

    _tile(0, "Governors",    gov_var,     "Total on register")
    _tile(1, "Active",       active_var,  "Currently serving")
    _tile(2, "Terms in 90d", expiring_var, "Expiring soon", fg="#a36")
    _tile(3, "Scheduled",    sched_var,   "Upcoming meetings")
    _tile(4, "Held",         held_var,    "Completed meetings")

    next_panel = ttk.LabelFrame(parent, text="Next meeting", padding=8)
    next_panel.pack(fill="x", pady=(0, 12))
    ttk.Label(next_panel, textvariable=next_var, foreground="#222").pack(
        anchor="w")

    breakdown = ttk.Frame(parent)
    breakdown.pack(fill="both", expand=True)
    breakdown.columnconfigure(0, weight=1, uniform="b")
    breakdown.columnconfigure(1, weight=1, uniform="b")

    role_frame = ttk.LabelFrame(breakdown, text="Governors by role", padding=6)
    role_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
    role_tree = ttk.Treeview(role_frame, columns=("name", "count"),
                                show="headings", height=10)
    role_tree.heading("name", text="Role")
    role_tree.heading("count", text="Count")
    role_tree.column("name", width=200, anchor="w")
    role_tree.column("count", width=70, anchor="e")
    role_tree.pack(fill="both", expand=True)

    status_frame = ttk.LabelFrame(breakdown, text="Governors by status",
                                    padding=6)
    status_frame.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
    status_tree = ttk.Treeview(status_frame, columns=("name", "count"),
                                  show="headings", height=10)
    status_tree.heading("name", text="Status")
    status_tree.heading("count", text="Count")
    status_tree.column("name", width=200, anchor="w")
    status_tree.column("count", width=70, anchor="e")
    status_tree.pack(fill="both", expand=True)

    def refresh() -> None:
        try:
            s = data.summary()
        except Exception as e:
            logger.exception("governance summary failed")
            messagebox.showerror("Error", str(e), parent=gui.root)
            return
        gov_var.set(str(s.governors_total))
        active_var.set(str(s.governors_active))
        expiring_var.set(str(s.term_expiring_90d))
        sched_var.set(str(s.meetings_scheduled))
        held_var.set(str(s.meetings_held))
        if s.next_meeting:
            n = s.next_meeting
            next_var.set(
                f"#{n.meeting_id} · {n.meeting_date} · "
                f"{n.kind} · {n.title}"
                + (f" (chair: {n.chair})" if n.chair else ""))
        else:
            next_var.set("(no upcoming meetings scheduled)")
        for child in role_tree.get_children():
            role_tree.delete(child)
        for r in GOVERNOR_ROLES:
            role_tree.insert(
                "", "end", values=(r, s.governors_by_role.get(r, 0)))
        for child in status_tree.get_children():
            status_tree.delete(child)
        for st in GOVERNOR_STATUSES:
            status_tree.insert(
                "", "end", values=(st, s.governors_by_status.get(st, 0)))
        gui.status_var.set("Governance summary refreshed")

    ttk.Button(parent, text="Refresh", command=refresh
                ).pack(anchor="w", pady=(8, 0))
    state["refresh_summary"] = refresh
    refresh()
