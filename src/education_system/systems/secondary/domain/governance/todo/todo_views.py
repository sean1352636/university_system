"""Tkinter views for Secondary School To-Do."""

from __future__ import annotations

import logging
import tkinter as tk
from datetime import date as _date
from tkinter import messagebox, ttk
from typing import Callable

from education_system.systems.secondary.domain.governance.todo import todo as data
from education_system.platform import branding
from education_system.systems.secondary.domain.governance.todo.todo import (
    DEFAULT_PRIORITY,
    DEFAULT_STATUS,
    PRIORITIES,
    STATUSES,
    Todo,
    ValidationError,
)

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)


def open_todo_window(parent=None) -> None:
    data.init_db()
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"To-Do — {branding.SYSTEM_NAME}")
    win.geometry(WIN_GEOMETRY)
    win.minsize(*WIN_MINSIZE)
    nb = ttk.Notebook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)
    BoardTab(nb)
    AllTodosTab(nb)
    OverdueTab(nb)
    SummaryTab(nb)


# ══ Board tab (open todos as cards) ═══════════════════════════════

class BoardTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Board")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Open to-dos.").pack(side="left")
        ttk.Button(bar, text="New",
                    command=self._new).pack(side="right", padx=(4, 0))
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="right")

        canvas = tk.Canvas(self.frame, borderwidth=0,
                              highlightthickness=0)
        scroll = ttk.Scrollbar(self.frame, orient="vertical",
                                  command=canvas.yview)
        self.inner = ttk.Frame(canvas)
        self.inner.bind(
            "<Configure>",
            lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        win = canvas.create_window((0, 0), window=self.inner, anchor="nw")
        canvas.bind(
            "<Configure>",
            lambda e: canvas.itemconfigure(win, width=e.width))
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True, padx=8, pady=4)
        scroll.pack(side="right", fill="y")

        self.status_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.status_var,
                   anchor="w").pack(fill="x", padx=8, pady=(0, 8))

    def refresh(self) -> None:
        for w in self.inner.winfo_children():
            w.destroy()
        rows = data.list_todos(open_only=True)
        if not rows:
            ttk.Label(self.inner, text="No open to-dos.",
                       foreground="#666").pack(anchor="w", padx=6, pady=20)
        for t in rows:
            self._render_card(t)
        self.status_var.set(f"{len(rows)} open to-do(s).")

    def _render_card(self, t: Todo) -> None:
        bg = {
            "Urgent": "#ffd0d0",
            "High":   "#ffe6d0",
            "Normal": "#f7f7f7",
            "Low":    "#f0f0f0",
        }.get(t.priority, "#f7f7f7")
        if t.is_overdue:
            bg = "#ffd0d0"
        card = tk.Frame(self.inner, bg=bg, bd=1, relief="solid")
        card.pack(fill="x", padx=4, pady=4)
        head = tk.Frame(card, bg=bg)
        head.pack(fill="x", padx=8, pady=(8, 0))
        tk.Label(head, text=t.title, bg=bg,
                  font=("", 12, "bold"), anchor="w").pack(side="left")
        tk.Label(head, text=f"#{t.todo_id}",
                  bg=bg, fg="#666").pack(side="right")
        meta = tk.Frame(card, bg=bg)
        meta.pack(fill="x", padx=8, pady=(0, 4))
        info_parts = [t.status, t.priority]
        if t.category:
            info_parts.append(t.category)
        info_parts.append(f"due {t.due_date or '—'}"
                           + ("  ⚠ overdue" if t.is_overdue else ""))
        if t.owner:
            info_parts.append(f"owner: {t.owner}")
        if t.assignee:
            info_parts.append(f"assignee: {t.assignee}")
        tk.Label(meta, text="  •  ".join(info_parts), bg=bg, fg="#444",
                  font=("", 9), anchor="w").pack(side="left")

        if t.description:
            tk.Label(card, text=t.description, bg="white",
                      wraplength=1100, justify="left", anchor="w"
                      ).pack(fill="x", padx=8, pady=(2, 6))

        actions = tk.Frame(card, bg=bg)
        actions.pack(fill="x", padx=8, pady=(0, 8))
        ttk.Button(actions, text="View",
                    command=lambda: self._view(t.todo_id)).pack(side="left")
        ttk.Button(actions, text="Edit",
                    command=lambda: self._edit(t.todo_id)
                    ).pack(side="left", padx=4)
        ttk.Button(actions, text="Done",
                    command=lambda: self._mark_done(t.todo_id)
                    ).pack(side="left", padx=4)
        ttk.Button(actions, text="Delete",
                    command=lambda: self._delete(t.todo_id)
                    ).pack(side="left", padx=4)

    def _view(self, tid: int) -> None:
        t = data.get_todo(tid)
        if t is None:
            return
        lines = [
            f"To-Do      : #{t.todo_id}",
            f"Title      : {t.title}",
            f"Status     : {t.status}",
            f"Priority   : {t.priority}",
            f"Owner      : {t.owner or '—'}",
            f"Assignee   : {t.assignee or '—'}",
            f"Category   : {t.category or '—'}",
            f"Due date   : {t.due_date or '—'}"
            + ("  (overdue)" if t.is_overdue else ""),
            f"Completed  : {t.completed_at or '—'}",
        ]
        if t.description:
            lines.extend(["", "Description:", t.description])
        messagebox.showinfo(f"To-Do #{t.todo_id}", "\n".join(lines))

    def _edit(self, tid: int) -> None:
        t = data.get_todo(tid)
        if t is None:
            return
        TodoDialog(self.frame.winfo_toplevel(), existing=t,
                    on_save=self.refresh)

    def _new(self) -> None:
        TodoDialog(self.frame.winfo_toplevel(), existing=None,
                    on_save=self.refresh)

    def _mark_done(self, tid: int) -> None:
        try:
            data.mark_done(tid)
        except ValidationError as e:
            messagebox.showerror("Failed", str(e))
            return
        self.refresh()

    def _delete(self, tid: int) -> None:
        if not messagebox.askyesno("Delete",
                                     f"Delete to-do #{tid}?"):
            return
        data.delete_todo(tid)
        self.refresh()


# ══ All To-Dos tab ═══════════════════════════════════════════════

class AllTodosTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="All To-Dos")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Search:").pack(side="left")
        self.q_e = ttk.Entry(bar, width=24)
        self.q_e.pack(side="left", padx=(2, 10))
        self.q_e.bind("<Return>", lambda _e: self.refresh())
        ttk.Label(bar, text="Status:").pack(side="left")
        self.f_status = ttk.Combobox(bar, values=("",) + STATUSES,
                                        state="readonly", width=12)
        self.f_status.current(0)
        self.f_status.pack(side="left", padx=(2, 10))
        ttk.Label(bar, text="Priority:").pack(side="left")
        self.f_pri = ttk.Combobox(bar, values=("",) + PRIORITIES,
                                     state="readonly", width=10)
        self.f_pri.current(0)
        self.f_pri.pack(side="left", padx=(2, 10))
        ttk.Label(bar, text="Owner:").pack(side="left")
        self.f_owner = ttk.Entry(bar, width=16)
        self.f_owner.pack(side="left", padx=(2, 10))
        ttk.Label(bar, text="Category:").pack(side="left")
        self.f_cat = ttk.Entry(bar, width=16)
        self.f_cat.pack(side="left", padx=(2, 10))
        self.f_open = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Open only",
                          variable=self.f_open,
                          command=self.refresh).pack(side="left")
        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left", padx=(10, 4))
        ttk.Button(bar, text="Clear",
                    command=self._clear).pack(side="left")

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("id", "status", "pri", "due", "owner", "assignee",
                "category", "title")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings")
        widths = {"id": 60, "status": 100, "pri": 70, "due": 100,
                  "owner": 120, "assignee": 120, "category": 130,
                  "title": 460}
        headings = {"id": "#", "status": "Status", "pri": "Priority",
                    "due": "Due", "owner": "Owner",
                    "assignee": "Assignee", "category": "Category",
                    "title": "Title"}
        for c in cols:
            self.tree.heading(c, text=headings[c])
            self.tree.column(c, width=widths[c], anchor="w")
        vs = ttk.Scrollbar(table_frame, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.tag_configure("Urgent", background="#ffd0d0")
        self.tree.tag_configure("High", background="#ffe6d0")
        self.tree.tag_configure("Done", foreground="#888")
        self.tree.tag_configure("Cancelled", foreground="#888",
                                  background="#f0f0f0")
        self.tree.tag_configure("overdue", background="#ffd0d0")
        self.tree.bind("<Double-1>", lambda _e: self._view_selected())

        self.count_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.count_var,
                   anchor="w").pack(fill="x", padx=8)

        actions = ttk.Frame(self.frame)
        actions.pack(fill="x", padx=8, pady=(4, 8))
        ttk.Button(actions, text="View",
                    command=self._view_selected).pack(side="left")
        ttk.Button(actions, text="New",
                    command=self._new).pack(side="left", padx=4)
        ttk.Button(actions, text="Edit",
                    command=self._edit_selected).pack(side="left", padx=4)
        ttk.Button(actions, text="Done",
                    command=self._done_selected).pack(side="left", padx=4)
        ttk.Button(actions, text="Reopen",
                    command=self._reopen_selected).pack(side="left", padx=4)
        ttk.Button(actions, text="Delete",
                    command=self._delete_selected).pack(side="left", padx=4)
        ttk.Button(actions, text="Clear Completed",
                    command=self._clear_completed).pack(side="left", padx=4)
        ttk.Button(actions, text="Refresh",
                    command=self.refresh).pack(side="right")

    def _clear(self) -> None:
        self.q_e.delete(0, "end")
        self.f_status.current(0)
        self.f_pri.current(0)
        self.f_owner.delete(0, "end")
        self.f_cat.delete(0, "end")
        self.f_open.set(False)
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        q = self.q_e.get().strip()
        try:
            if q:
                rows = data.search_todos(q)
            else:
                rows = data.list_todos(
                    status=self.f_status.get() or None,
                    priority=self.f_pri.get() or None,
                    owner=self.f_owner.get().strip() or None,
                    category=self.f_cat.get().strip() or None,
                    open_only=self.f_open.get(),
                )
        except ValidationError as e:
            messagebox.showerror("Filter error", str(e))
            return
        for t in rows:
            tags: list[str] = []
            if t.priority in ("Urgent", "High"):
                tags.append(t.priority)
            if t.status in ("Done", "Cancelled"):
                tags.append(t.status)
            if t.is_overdue:
                tags.append("overdue")
            due = t.due_date or "—"
            if t.is_overdue:
                due = f"⚠ {due}"
            self.tree.insert("", "end", iid=str(t.todo_id), values=(
                t.todo_id, t.status, t.priority, due,
                t.owner or "—", t.assignee or "—",
                t.category or "—", t.title,
            ), tags=tuple(tags))
        self.count_var.set(f"{len(rows)} to-do(s).")

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def _view_selected(self) -> None:
        tid = self._selected_id()
        if tid is None:
            messagebox.showinfo("View", "Select a to-do first.")
            return
        t = data.get_todo(tid)
        if t is None:
            return
        lines = [
            f"To-Do      : #{t.todo_id}",
            f"Title      : {t.title}",
            f"Status     : {t.status}",
            f"Priority   : {t.priority}",
            f"Owner      : {t.owner or '—'}",
            f"Assignee   : {t.assignee or '—'}",
            f"Category   : {t.category or '—'}",
            f"Due date   : {t.due_date or '—'}"
            + ("  (overdue)" if t.is_overdue else ""),
            f"Completed  : {t.completed_at or '—'}",
        ]
        if t.description:
            lines.extend(["", "Description:", t.description])
        messagebox.showinfo(f"To-Do #{t.todo_id}", "\n".join(lines))

    def _new(self) -> None:
        TodoDialog(self.frame.winfo_toplevel(), existing=None,
                    on_save=self.refresh)

    def _edit_selected(self) -> None:
        tid = self._selected_id()
        if tid is None:
            messagebox.showinfo("Edit", "Select a to-do first.")
            return
        t = data.get_todo(tid)
        if t is None:
            return
        TodoDialog(self.frame.winfo_toplevel(), existing=t,
                    on_save=self.refresh)

    def _done_selected(self) -> None:
        tid = self._selected_id()
        if tid is None:
            messagebox.showinfo("Done", "Select a to-do first.")
            return
        try:
            data.mark_done(tid)
        except ValidationError as e:
            messagebox.showerror("Failed", str(e))
            return
        self.refresh()

    def _reopen_selected(self) -> None:
        tid = self._selected_id()
        if tid is None:
            messagebox.showinfo("Reopen", "Select a to-do first.")
            return
        try:
            data.reopen(tid)
        except ValidationError as e:
            messagebox.showerror("Failed", str(e))
            return
        self.refresh()

    def _delete_selected(self) -> None:
        tid = self._selected_id()
        if tid is None:
            messagebox.showinfo("Delete", "Select a to-do first.")
            return
        if not messagebox.askyesno("Delete",
                                     f"Delete to-do #{tid}?"):
            return
        data.delete_todo(tid)
        self.refresh()

    def _clear_completed(self) -> None:
        if not messagebox.askyesno(
                "Clear Completed",
                "Remove all Done/Cancelled to-dos?"):
            return
        n = data.clear_completed()
        messagebox.showinfo("Done", f"Removed {n} to-do(s).")
        self.refresh()


# ══ Overdue tab ══════════════════════════════════════════════════

class OverdueTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Overdue & Due Today")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Overdue and due-today items.").pack(side="left")
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="right")

        cols = ("id", "status", "pri", "due", "owner", "title")
        widths = {"id": 60, "status": 100, "pri": 80, "due": 110,
                  "owner": 140, "title": 600}
        headings = {"id": "#", "status": "Status", "pri": "Priority",
                    "due": "Due", "owner": "Owner", "title": "Title"}

        def make_tree(parent: ttk.Frame) -> ttk.Treeview:
            tree = ttk.Treeview(parent, columns=cols, show="headings",
                                  height=10)
            for c in cols:
                tree.heading(c, text=headings[c])
                tree.column(c, width=widths[c], anchor="w")
            return tree

        ttk.Label(self.frame, text="Overdue:",
                   font=("", 10, "bold")).pack(anchor="w", padx=10)
        wrap1 = ttk.Frame(self.frame)
        wrap1.pack(fill="both", expand=True, padx=8, pady=(0, 6))
        self.tree_over = make_tree(wrap1)
        vs1 = ttk.Scrollbar(wrap1, orient="vertical",
                              command=self.tree_over.yview)
        self.tree_over.configure(yscrollcommand=vs1.set)
        self.tree_over.pack(side="left", fill="both", expand=True)
        vs1.pack(side="right", fill="y")
        self.tree_over.tag_configure("overdue", background="#ffd0d0")

        ttk.Label(self.frame, text="Due today:",
                   font=("", 10, "bold")).pack(anchor="w", padx=10,
                                                pady=(6, 0))
        wrap2 = ttk.Frame(self.frame)
        wrap2.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.tree_today = make_tree(wrap2)
        vs2 = ttk.Scrollbar(wrap2, orient="vertical",
                              command=self.tree_today.yview)
        self.tree_today.configure(yscrollcommand=vs2.set)
        self.tree_today.pack(side="left", fill="both", expand=True)
        vs2.pack(side="right", fill="y")
        self.tree_today.tag_configure("due", background="#ffe6d0")

    def refresh(self) -> None:
        for tree in (self.tree_over, self.tree_today):
            for i in tree.get_children():
                tree.delete(i)
        for t in data.list_todos(overdue_only=True):
            self.tree_over.insert("", "end", iid=str(t.todo_id),
                                    values=(t.todo_id, t.status, t.priority,
                                            t.due_date or "—",
                                            t.owner or "—", t.title),
                                    tags=("overdue",))
        for t in data.list_todos(
                due_on=_date.today().isoformat()):
            if not t.is_open:
                continue
            self.tree_today.insert("", "end", iid=str(t.todo_id),
                                     values=(t.todo_id, t.status, t.priority,
                                             t.due_date or "—",
                                             t.owner or "—", t.title),
                                     tags=("due",))


# ══ Summary tab ══════════════════════════════════════════════════

class SummaryTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Summary")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Owner filter:").pack(side="left")
        self.owner_e = ttk.Entry(bar, width=20)
        self.owner_e.pack(side="left", padx=(2, 10))
        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left", padx=(4, 4))
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="right")

        self.text = tk.Text(self.frame, wrap="word",
                              font=("TkFixedFont", 10))
        self.text.pack(fill="both", expand=True, padx=8, pady=8)

    def refresh(self) -> None:
        owner = self.owner_e.get().strip() or None
        s = data.summary(owner=owner)
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        lines = [
            f"Total       : {s.total}",
            f"Open        : {s.open}",
            f"In Progress : {s.in_progress}",
            f"Blocked     : {s.blocked}",
            f"Done        : {s.done}",
            f"Cancelled   : {s.cancelled}",
            "",
            f"Overdue     : {s.overdue}",
            f"Due today   : {s.due_today}",
            f"Due in 7d   : {s.due_within_7d}",
            "",
            "By priority:",
        ]
        for p in PRIORITIES:
            lines.append(f"  {p:<10} : {s.by_priority.get(p, 0)}")
        if s.by_owner:
            lines.extend(["", "By owner (top 10):"])
            for o, n in sorted(s.by_owner.items(),
                                  key=lambda x: -x[1])[:10]:
                lines.append(f"  {o[:24]:<24} : {n}")
        if s.by_category:
            lines.extend(["", "By category (top 10):"])
            for c, n in sorted(s.by_category.items(),
                                  key=lambda x: -x[1])[:10]:
                lines.append(f"  {c[:24]:<24} : {n}")
        self.text.insert("1.0", "\n".join(lines))
        self.text.configure(state="disabled")


# ══ Dialog ═══════════════════════════════════════════════════════

class TodoDialog(tk.Toplevel):
    def __init__(self, master, existing: Todo | None,
                  on_save: Callable[[], None]) -> None:
        super().__init__(master)
        self.title("To-Do" if existing is None else f"Edit #{existing.todo_id}")
        self.on_save = on_save
        self.existing = existing
        self.transient(master)
        body = ttk.Frame(self, padding=10)
        body.pack(fill="both", expand=True)

        ttk.Label(body, text="Title:").grid(row=0, column=0, sticky="e",
                                              padx=4, pady=2)
        self.e_title = ttk.Entry(body, width=60)
        self.e_title.grid(row=0, column=1, sticky="we", padx=4, pady=2)

        ttk.Label(body, text="Description:").grid(row=1, column=0,
                                                    sticky="ne", padx=4,
                                                    pady=2)
        self.t_desc = tk.Text(body, width=60, height=8, wrap="word")
        self.t_desc.grid(row=1, column=1, sticky="we", padx=4, pady=2)

        ttk.Label(body, text="Owner:").grid(row=2, column=0, sticky="e",
                                              padx=4, pady=2)
        self.e_owner = ttk.Entry(body, width=30)
        self.e_owner.grid(row=2, column=1, sticky="w", padx=4, pady=2)

        ttk.Label(body, text="Assignee:").grid(row=3, column=0, sticky="e",
                                                 padx=4, pady=2)
        self.e_assignee = ttk.Entry(body, width=30)
        self.e_assignee.grid(row=3, column=1, sticky="w", padx=4, pady=2)

        ttk.Label(body, text="Status:").grid(row=4, column=0, sticky="e",
                                               padx=4, pady=2)
        self.cb_status = ttk.Combobox(body, values=STATUSES,
                                        state="readonly", width=14)
        self.cb_status.grid(row=4, column=1, sticky="w", padx=4, pady=2)

        ttk.Label(body, text="Priority:").grid(row=5, column=0, sticky="e",
                                                 padx=4, pady=2)
        self.cb_pri = ttk.Combobox(body, values=PRIORITIES,
                                     state="readonly", width=14)
        self.cb_pri.grid(row=5, column=1, sticky="w", padx=4, pady=2)

        ttk.Label(body, text="Category:").grid(row=6, column=0, sticky="e",
                                                 padx=4, pady=2)
        self.e_cat = ttk.Entry(body, width=30)
        self.e_cat.grid(row=6, column=1, sticky="w", padx=4, pady=2)

        ttk.Label(body, text="Due date (YYYY-MM-DD):").grid(
            row=7, column=0, sticky="e", padx=4, pady=2)
        self.e_due = ttk.Entry(body, width=16)
        self.e_due.grid(row=7, column=1, sticky="w", padx=4, pady=2)

        bar = ttk.Frame(body)
        bar.grid(row=8, column=0, columnspan=2, sticky="e", pady=(8, 0))
        ttk.Button(bar, text="Cancel",
                    command=self.destroy).pack(side="right", padx=4)
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="right")

        body.columnconfigure(1, weight=1)

        if existing is not None:
            self.e_title.insert(0, existing.title)
            if existing.description:
                self.t_desc.insert("1.0", existing.description)
            self.e_owner.insert(0, existing.owner or "")
            self.e_assignee.insert(0, existing.assignee or "")
            self.cb_status.set(existing.status)
            self.cb_pri.set(existing.priority)
            self.e_cat.insert(0, existing.category or "")
            self.e_due.insert(0, existing.due_date or "")
        else:
            self.cb_status.set(DEFAULT_STATUS)
            self.cb_pri.set(DEFAULT_PRIORITY)

    def _save(self) -> None:
        payload = {
            "title": self.e_title.get(),
            "description": self.t_desc.get("1.0", "end").rstrip("\n"),
            "owner": self.e_owner.get(),
            "assignee": self.e_assignee.get(),
            "status": self.cb_status.get(),
            "priority": self.cb_pri.get(),
            "category": self.e_cat.get(),
            "due_date": self.e_due.get(),
        }
        try:
            if self.existing is None:
                data.create_todo(payload)
            else:
                data.update_todo(self.existing.todo_id, payload)
        except ValidationError as e:
            messagebox.showerror("Validation", str(e), parent=self)
            return
        self.on_save()
        self.destroy()
