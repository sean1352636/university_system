"""GUI panel for Sixth Form Parent Portal administration (staff-facing).

Left: list of parent accounts with create / reset / enable / delete.
Right: the selected account's linked children + a preview of the
read-only snapshot a parent would see.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from education_system.post_16.sixthform_system.modules.domain.students.parent_portal import (
    parent_portal as data,
)

logger = logging.getLogger(__name__)


def _clear(gui) -> ttk.Frame:
    for w in gui.content_frame.winfo_children():
        w.destroy()
    return gui.content_frame


def _heading(parent, text: str) -> None:
    ttk.Label(parent, text=text, font=("", 16, "bold")).pack(anchor="w", pady=(0, 8))


def open_directory(gui) -> None:
    parent = _clear(gui)
    _heading(parent, "Parent Portal — Account Administration")

    panes = ttk.Panedwindow(parent, orient="horizontal")
    panes.pack(fill="both", expand=True)
    left = ttk.Frame(panes, padding=(0, 0, 8, 0))
    right = ttk.Frame(panes)
    panes.add(left, weight=1)
    panes.add(right, weight=2)

    cols = ("id", "username", "name", "active", "children")
    tree = ttk.Treeview(left, columns=cols, show="headings", height=16)
    for c, t, w in (("id", "ID", 40), ("username", "Username", 120),
                    ("name", "Name", 140), ("active", "Active", 60),
                    ("children", "Kids", 50)):
        tree.heading(c, text=t)
        tree.column(c, width=w, anchor="w" if c in ("username", "name") else "center")
    tree.pack(fill="both", expand=True)

    btns = ttk.Frame(left)
    btns.pack(fill="x", pady=(6, 0))

    detail = ttk.Frame(right)
    detail.pack(fill="both", expand=True)

    def refresh() -> None:
        tree.delete(*tree.get_children())
        for a in data.list_accounts():
            tree.insert("", "end", iid=str(a["account_id"]),
                        values=(a["account_id"], a["username"], a["full_name"],
                                "yes" if a["is_active"] else "no", a["linked_students"]))

    def selected_id() -> int | None:
        sel = tree.selection()
        return int(sel[0]) if sel else None

    def render_detail(account_id: int) -> None:
        for w in detail.winfo_children():
            w.destroy()
        try:
            dash = data.account_dashboard(account_id)
        except data.ValidationError as e:
            ttk.Label(detail, text=str(e)).pack()
            return
        ttk.Label(detail, text=f"{dash['account']['full_name']} "
                              f"({dash['account']['username']})",
                  font=("", 13, "bold")).pack(anchor="w")

        link_bar = ttk.Frame(detail)
        link_bar.pack(fill="x", pady=(6, 4))
        ttk.Button(link_bar, text="Link student…",
                   command=lambda: do_link(account_id)).pack(side="left")
        ttk.Button(link_bar, text="Unlink selected child",
                   command=lambda: do_unlink(account_id)).pack(side="left", padx=6)

        if not dash["children"]:
            ttk.Label(detail, text="No linked children.").pack(anchor="w", pady=6)
            return
        nb = ttk.Notebook(detail)
        nb.pack(fill="both", expand=True, pady=(6, 0))
        for c in dash["children"]:
            tab = ttk.Frame(nb, padding=8)
            nb.add(tab, text=c["full_name"])
            b = c["behaviour_30d"]
            ttk.Label(tab, text=f"Attendance {c['attendance_pct']}%   "
                              f"Risk band: {c['risk_band']}   "
                              f"Behaviour 30d +{b['positive']}/-{b['negative']}").pack(anchor="w")
            if c["ucas"]:
                ttk.Label(tab, text=f"UCAS progress: {c['ucas']['percent']}%").pack(anchor="w")
            sub = ttk.Treeview(tab, columns=("s", "p", "t", "f", "ot"),
                               show="headings", height=6)
            for cc, tt, ww in (("s", "Subject", 160), ("p", "Predicted", 80),
                               ("t", "Target", 70), ("f", "Forecast", 80),
                               ("ot", "On target", 90)):
                sub.heading(cc, text=tt)
                sub.column(cc, width=ww, anchor="w" if cc == "s" else "center")
            for s in c["subjects"]:
                ot = "—" if s["on_target"] is None else ("yes" if s["on_target"] else "NO")
                sub.insert("", "end", values=(s["subject"], s["predicted"] or "—",
                           s["target"] or "—", s["forecast"] or "—", ot))
            sub.pack(fill="x", pady=(6, 0))
            # remember which child tab is active for unlink
            tab._student_id = c["student_id"]  # type: ignore[attr-defined]
        detail._nb = nb  # type: ignore[attr-defined]

    def on_select(_evt=None) -> None:
        aid = selected_id()
        if aid is not None:
            render_detail(aid)

    def do_create() -> None:
        username = simpledialog.askstring("New account", "Username:")
        if not username:
            return
        full = simpledialog.askstring("New account", "Full name:") or ""
        pw = simpledialog.askstring("New account", "Password (min 8):", show="*") or ""
        try:
            data.create_account(username=username, password=pw, full_name=full)
        except data.ValidationError as e:
            messagebox.showerror("New account", str(e))
            return
        refresh()

    def do_reset() -> None:
        aid = selected_id()
        if aid is None:
            return
        pw = simpledialog.askstring("Reset password", "New password (min 8):", show="*") or ""
        try:
            data.set_password(aid, pw)
        except data.ValidationError as e:
            messagebox.showerror("Reset password", str(e))
            return
        messagebox.showinfo("Parent Portal", "Password reset.")

    def do_toggle() -> None:
        aid = selected_id()
        if aid is None:
            return
        acc = {a["account_id"]: a for a in data.list_accounts()}[aid]
        data.set_active(aid, not acc["is_active"])
        refresh()

    def do_delete() -> None:
        aid = selected_id()
        if aid is not None and messagebox.askyesno("Delete", f"Delete account #{aid}?"):
            data.delete_account(aid)
            refresh()
            for w in detail.winfo_children():
                w.destroy()

    def do_link(account_id: int) -> None:
        sid = simpledialog.askstring("Link student", "Student ID:")
        if not sid:
            return
        rel = simpledialog.askstring("Link student", "Relationship:", initialvalue="Parent") or "Parent"
        try:
            data.link_student(account_id, sid, relationship=rel)
        except data.ValidationError as e:
            messagebox.showerror("Link student", str(e))
            return
        refresh()
        render_detail(account_id)

    def do_unlink(account_id: int) -> None:
        nb = getattr(detail, "_nb", None)
        if not nb:
            return
        cur = nb.nametowidget(nb.select())
        sid = getattr(cur, "_student_id", None)
        if sid and messagebox.askyesno("Unlink", "Remove this child from the account?"):
            data.unlink_student(account_id, sid)
            refresh()
            render_detail(account_id)

    ttk.Button(btns, text="New", command=do_create).pack(side="left")
    ttk.Button(btns, text="Reset PW", command=do_reset).pack(side="left", padx=4)
    ttk.Button(btns, text="On/Off", command=do_toggle).pack(side="left")
    ttk.Button(btns, text="Delete", command=do_delete).pack(side="left", padx=4)
    tree.bind("<<TreeviewSelect>>", on_select)
    refresh()
