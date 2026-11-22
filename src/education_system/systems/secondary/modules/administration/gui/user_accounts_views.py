"""User Accounts (admin): the portal logins.

Tabs: Pupil logins (made when a pupil is added), Parent logins (made from
contacts with parental responsibility and an e-mail - "Create parent logins
from contacts" catches up any that are missing, "Send waiting e-mails"
delivers their welcome e-mails), and Linked logins (link an existing login
to a pupil as that pupil or as a parent, or remove a link). Rules live in
:mod:`modules.portals.domain.portal_accounts`.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from typing import Callable

from education_system.platform.delivery.gui.parented_dialogs import make_toplevel, messagebox
from education_system.systems.secondary.modules.portals.domain import portal_accounts as PA
from education_system.systems.secondary.modules.pupils.domain import pupil_accounts
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.ui.gui.components import widgets as W

logger = logging.getLogger(__name__)
_ERRORS = (PA.ValidationError, PA.PermissionDenied, PA.NotFound)


_problems = W.problems


def _tree(parent, columns, height: int = 14) -> ttk.Treeview:
    return W.tree(parent, columns, height=height, stretch={"name"},
                  tags={"removed": {"foreground": "#999"}}, minwidth=0)


def deliver_waiting(owner: tk.Misc, principal: Principal, *, pupil_id: int | None = None,
                    quiet: bool = False, after: Callable[[], None] | None = None) -> None:
    """Deliver parent portal e-mails still in the outbox, in the background."""
    from education_system.systems.secondary.modules.communication.gui import email_views
    ids = PA.undelivered(pupil_id=pupil_id)
    if not ids:
        if not quiet:
            messagebox.showinfo("Parent e-mails", "No parent portal e-mails are waiting.",
                                parent=owner.winfo_toplevel())
        return
    results: list[str] = []

    def done(report, err) -> None:
        results.append(err or email_views._report_text(report))
        if len(results) == len(ids):
            if not quiet or any("fail" in r.lower() for r in results):
                messagebox.showinfo("Parent e-mails", f"{len(ids)} parent portal e-mail(s): "
                                    + "; ".join(results), parent=owner.winfo_toplevel())
            if after:
                after()
    for mid in ids:
        email_views.deliver_in_background(owner, mid, principal, done)


class UserAccountsPage:
    TABS = ("Pupil logins", "Parent logins", "Linked logins")

    def __init__(self, parent: ttk.Frame, *, principal: Principal, state: dict) -> None:
        self.parent, self.principal, self.state = parent, principal, state
        ttk.Label(parent, text="User Accounts", font=("", 16, "bold")).pack(anchor="w")
        ttk.Label(parent, text="Pupil and parent portal logins. Staff logins are managed "
                               "centrally.", foreground="#666").pack(anchor="w", pady=(0, 6))
        self.book = ttk.Notebook(parent)
        self.book.pack(fill="both", expand=True)
        self.tabs = {n: ttk.Frame(self.book, padding=8) for n in self.TABS}
        for n, f in self.tabs.items():
            self.book.add(f, text=n)
        self._build_pupils(self.tabs["Pupil logins"])
        self._build_parents(self.tabs["Parent logins"])
        self._build_links(self.tabs["Linked logins"])
        self.book.select(self.TABS.index(state.get("tab", "Pupil logins")))
        self.book.bind("<<NotebookTabChanged>>", self._on_tab)
        self._on_tab()

    def _top(self):
        return self.parent.winfo_toplevel()

    def _on_tab(self, _e=None) -> None:
        name = self.TABS[self.book.index(self.book.select())]
        self.state["tab"] = name
        {"Pupil logins": self.refresh_pupils, "Parent logins": self.refresh_parents,
         "Linked logins": self.refresh_links}[name]()

    # Pupils
    def _build_pupils(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 6))
        ttk.Label(bar, text="A pupil's login is made when they are added (Create login on "
                            "their profile if it failed).", foreground="#666").pack(side="left")
        ttk.Button(bar, text="Refresh", command=self.refresh_pupils).pack(side="right")
        self.p_tree = _tree(tab, [("adm", "Adm no", 90), ("name", "Pupil", 200),
                                  ("year", "Yr", 40), ("user", "Username", 140),
                                  ("email", "School e-mail", 240), ("status", "Status", 80),
                                  ("made", "Created", 140)])
        self.p_info = tk.StringVar()
        ttk.Label(tab, textvariable=self.p_info, foreground="#666").pack(anchor="w")

    def refresh_pupils(self) -> None:
        self.p_tree.delete(*self.p_tree.get_children())
        accts = {a.pupil_id: a for a in pupil_accounts.list_accounts()}
        pupils = P.list_pupils()
        missing = 0
        for p in pupils:
            a = accts.get(p.pupil_id)
            missing += a is None
            self.p_tree.insert("", "end", tags=("removed",) if a is None or a.status !=
                               "active" else (), values=(
                p.admission_no, p.display_name, p.year_group, a.username if a else "",
                a.school_email if a else "", a.status if a else "no login",
                (a.created_at or "")[:16] if a else ""))
        self.p_info.set(f"{len(pupils)} pupil(s) on roll · {missing} without a login")

    # Parents
    def _build_parents(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 6))
        ttk.Button(bar, text="Create parent logins from contacts",
                   command=self.sync_all).pack(side="left")
        self.wait_btn = ttk.Button(bar, text="Send waiting e-mails",
                                   command=lambda: deliver_waiting(
                                       self.parent, self.principal, after=self.refresh_parents))
        self.wait_btn.pack(side="left", padx=(6, 0))
        ttk.Button(bar, text="Refresh", command=self.refresh_parents).pack(side="right")
        ttk.Label(tab, text="Every contact with parental responsibility and an e-mail gets a "
                            "login (username firstname.lastname, matched on their e-mail). "
                            "One login covers all their children. Change or remove the "
                            "contact to change the link.",
                  foreground="#666", wraplength=900, justify="left").pack(anchor="w")
        self.pa_tree = _tree(tab, [("user", "Username", 240), ("name", "Name", 180),
                                   ("children", "Children", 300), ("new", "Login", 120),
                                   ("made", "Created", 140)])

    def refresh_parents(self) -> None:
        self.pa_tree.delete(*self.pa_tree.get_children())
        for r in PA.parent_logins():
            kids = r["children"]
            self.pa_tree.insert("", "end", tags=() if kids else ("removed",), values=(
                r["username"], r["display_name"] or "",
                ", ".join(f"{k.pupil_name} ({k.admission_no})" for k in kids) or "none now",
                "made here" if r["created_new"] else "existing login",
                (r["created_at"] or "")[:16]))
        n = len(PA.undelivered())
        self.wait_btn.configure(text=f"Send waiting e-mails ({n})" if n else
                                "Send waiting e-mails")

    def sync_all(self) -> None:
        if not messagebox.askyesno("Parent logins", "Create a parent portal login for every "
                                   "contact with parental responsibility and an e-mail who "
                                   "hasn't got one, and e-mail them their details?",
                                   parent=self._top()):
            return
        try:
            counts = PA.sync_all(actor=self.principal)
        except _ERRORS as e:
            messagebox.showerror("Parent logins", _problems(e), parent=self._top())
            return
        words = {"created": "new login(s)", "linked": "linked to an existing login",
                 "moved": "moved", "removed": "link(s) removed", "unchanged": "already set up",
                 "skipped": "skipped (no e-mail / no parental responsibility)"}
        text = "\n".join(f"{n} {words.get(k, k)}" for k, n in counts.items() if n) or \
            "Nothing to do."
        messagebox.showinfo("Parent logins", text, parent=self._top())
        self.refresh_parents()
        deliver_waiting(self.parent, self.principal, quiet=True, after=self.refresh_parents)

    # Links
    def _build_links(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 6))
        ttk.Button(bar, text="Link a login…", command=self.link_dialog).pack(side="left")
        ttk.Button(bar, text="Remove link", command=self.unlink).pack(side="left", padx=(6, 0))
        self.l_removed = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Show removed", variable=self.l_removed,
                        command=self.refresh_links).pack(side="left", padx=(12, 0))
        ttk.Button(bar, text="Refresh", command=self.refresh_links).pack(side="right")
        self.l_tree = _tree(tab, [("user", "Username", 200), ("kind", "As", 70),
                                  ("name", "Pupil", 200), ("adm", "Adm no", 90),
                                  ("src", "From", 90), ("status", "Status", 80),
                                  ("made", "Linked", 140)])

    def refresh_links(self) -> None:
        self.l_tree.delete(*self.l_tree.get_children())
        for x in PA.list_links(include_removed=self.l_removed.get()):
            self.l_tree.insert("", "end", iid=str(x.link_id), tags=() if x.active else (
                "removed",), values=(x.username, x.kind, x.pupil_name, x.admission_no,
                                     "contact" if x.source == "contact" else "by hand",
                                     x.status, (x.created_at or "")[:16]))

    def link_dialog(self) -> None:
        win = make_toplevel(self._top())
        win.title("Link a login")
        frm = ttk.Frame(win, padding=12)
        frm.pack(fill="both", expand=True)
        user = tk.StringVar()
        pupil = tk.StringVar()
        kind = tk.StringVar(value="parent")
        for i, (label, widget) in enumerate((
                ("Username:", ttk.Entry(frm, textvariable=user, width=30)),
                ("Pupil (adm no or UPN):", ttk.Entry(frm, textvariable=pupil, width=16)))):
            ttk.Label(frm, text=label).grid(row=i, column=0, sticky="w", pady=3, padx=(0, 8))
            widget.grid(row=i, column=1, sticky="w", pady=3)
        ttk.Label(frm, text="Link as:").grid(row=2, column=0, sticky="w", pady=3)
        kinds = ttk.Frame(frm)
        kinds.grid(row=2, column=1, sticky="w")
        ttk.Radiobutton(kinds, text="Parent", value="parent", variable=kind).pack(side="left")
        ttk.Radiobutton(kinds, text="The pupil", value="pupil", variable=kind).pack(
            side="left", padx=(8, 0))
        ttk.Label(frm, text="A login with no Secondary role is given the pupil or parent "
                            "role. A staff login can be linked as a parent.",
                  foreground="#666", wraplength=380, justify="left").grid(
            row=3, column=0, columnspan=2, sticky="w", pady=(6, 0))

        def save() -> None:
            p = P.find_by_reference(pupil.get().strip()) if pupil.get().strip() else None
            if p is None:
                messagebox.showerror("Link a login", "No pupil with that admission number.",
                                     parent=win)
                return
            try:
                link = PA.link_login(user.get(), p.pupil_id, kind.get(), actor=self.principal)
            except _ERRORS as e:
                messagebox.showerror("Link a login", _problems(e), parent=win)
                return
            win.destroy()
            messagebox.showinfo("Link a login", f"{link.username} can now see "
                                f"{link.pupil_name} in the {link.kind} portal.",
                                parent=self._top())
            self.refresh_links()

        bar = ttk.Frame(frm)
        bar.grid(row=4, column=0, columnspan=2, sticky="e", pady=(10, 0))
        ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="right", padx=(6, 0))
        ttk.Button(bar, text="Link", command=save).pack(side="right")

    def unlink(self) -> None:
        sel = self.l_tree.selection()
        if not sel:
            messagebox.showinfo("Remove link", "Select a link first.", parent=self._top())
            return
        x = PA.get_link(int(sel[0]))
        if not messagebox.askyesno("Remove link", f"Stop {x.username} seeing {x.pupil_name}?",
                                   parent=self._top()):
            return
        try:
            PA.unlink(x.link_id, actor=self.principal)
        except _ERRORS as e:
            messagebox.showerror("Remove link", _problems(e), parent=self._top())
            return
        self.refresh_links()


def draw_user_accounts(parent: ttk.Frame, *, principal: Principal,
                       state: dict) -> UserAccountsPage:
    return UserAccountsPage(parent, principal=principal, state=state)
