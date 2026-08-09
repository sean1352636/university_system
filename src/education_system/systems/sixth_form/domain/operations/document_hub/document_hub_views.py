"""Tkinter views for Sixth Form Document Hub."""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import messagebox, ttk

from education_system.platform import branding
from education_system.systems.sixth_form.domain.operations.document_hub import (
    document_hub as data,
)
from education_system.systems.sixth_form.domain.operations.document_hub.document_hub import (
    ACCESS_LEVELS,
    AUDIENCES,
    CATEGORIES,
    DEFAULT_ACCESS,
    DEFAULT_AUDIENCE,
    DEFAULT_CATEGORY,
    DEFAULT_STATUS,
    Document,
    STATUSES,
    ValidationError,
)

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)

_STATUS_TAGS = {
    "Draft":        ("#fff7e6", "#7a5800"),
    "Under Review": ("#e6f0ff", "#1a3f8c"),
    "Approved":     ("#d6ffd6", "#0d6b2a"),
    "Published":    ("#e6f7e6", "#0d6b2a"),
    "Superseded":   ("#eeeeee", "#666666"),
    "Withdrawn":    ("#ffd1d1", "#8c0d0d"),
    "Archived":     ("#dddddd", "#444444"),
}


def open_document_hub_window(parent=None) -> None:
    data.init_db()
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"Document Hub — {branding.SYSTEM_NAME}")
    win.geometry(WIN_GEOMETRY)
    win.minsize(*WIN_MINSIZE)

    nb = ttk.Notebook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)

    DocumentsTab(nb, scope="current",      label="Current")
    DocumentsTab(nb, scope="overdue",      label="Overdue Review")
    DocumentsTab(nb, scope="drafts",       label="Drafts")
    DocumentsTab(nb, scope="under_review", label="Under Review")
    DocumentsTab(nb, scope="all",          label="All")
    SummaryTab(nb)


class DocumentsTab:
    def __init__(self, nb: ttk.Notebook, *,
                 scope: str, label: str) -> None:
        self.scope = scope
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text=label)
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Category:").pack(side="left")
        self.f_cat = ttk.Combobox(
            bar, values=("",) + CATEGORIES,
            state="readonly", width=18)
        self.f_cat.current(0)
        self.f_cat.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Audience:").pack(side="left")
        self.f_aud = ttk.Combobox(
            bar, values=("",) + AUDIENCES,
            state="readonly", width=16)
        self.f_aud.current(0)
        self.f_aud.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Access:").pack(side="left")
        self.f_acc = ttk.Combobox(
            bar, values=("",) + ACCESS_LEVELS,
            state="readonly", width=14)
        self.f_acc.current(0)
        self.f_acc.pack(side="left", padx=(2, 8))
        if self.scope == "all":
            ttk.Label(bar, text="Status:").pack(side="left")
            self.f_status = ttk.Combobox(
                bar, values=("",) + STATUSES,
                state="readonly", width=14)
            self.f_status.current(0)
            self.f_status.pack(side="left", padx=(2, 8))
        else:
            self.f_status = None
        ttk.Label(bar, text="Title:").pack(side="left")
        self.f_title = ttk.Entry(bar, width=20)
        self.f_title.pack(side="left", padx=(2, 8))
        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left",
                                                 padx=4)
        ttk.Button(bar, text="New",
                    command=self._new).pack(side="left",
                                              padx=(16, 0))

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True,
                            padx=8, pady=4)
        cols = ("id", "ov", "title", "category", "audience",
                "access", "version", "issued", "review",
                "status", "downloads")
        self.tree = ttk.Treeview(table_frame, columns=cols,
                                   show="headings",
                                   selectmode="browse")
        widths = {"id": 50, "ov": 40, "title": 260,
                   "category": 140, "audience": 140,
                   "access": 110, "version": 80,
                   "issued": 100, "review": 100,
                   "status": 110, "downloads": 80}
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=widths[c],
                              anchor=("center"
                                       if c in ("id", "ov",
                                                  "version",
                                                  "downloads")
                                       else "w"))
        vsb = ttk.Scrollbar(table_frame, orient="vertical",
                              command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        for status, (bg, fg) in _STATUS_TAGS.items():
            self.tree.tag_configure(status, background=bg,
                                       foreground=fg)
        self.tree.tag_configure("overdue",
                                  background="#ffd1d1",
                                  foreground="#8c0d0d")
        self.tree.bind("<Double-Button-1>",
                         lambda _e: self._edit())

        actions = ttk.Frame(self.frame)
        actions.pack(fill="x", padx=8, pady=(4, 8))
        for label, cmd in (
                ("Edit",            self._edit),
                ("Submit review",   self._submit),
                ("Approve",         self._approve),
                ("Publish",         self._publish),
                ("Withdraw",        self._withdraw),
                ("Archive",         self._archive),
                ("Supersede",       self._supersede),
                ("Change status",   self._set_status),
                ("Auto-archive",    self._auto_archive),
                ("Delete",          self._delete),
                ("Refresh",         self.refresh),
        ):
            ttk.Button(actions, text=label,
                        command=cmd).pack(side="left", padx=4)
        self.count = ttk.Label(actions, text="")
        self.count.pack(side="right")

    def _filters(self) -> dict:
        f: dict = {}
        if self.f_cat.get():
            f["category"] = self.f_cat.get()
        if self.f_aud.get():
            f["audience"] = self.f_aud.get()
        if self.f_acc.get():
            f["access_level"] = self.f_acc.get()
        if self.f_status is not None and self.f_status.get():
            f["status"] = self.f_status.get()
        if self.f_title.get().strip():
            f["title_like"] = self.f_title.get().strip()
        if self.scope == "current":
            f["current_only"] = True
        elif self.scope == "overdue":
            f["overdue_review_only"] = True
        elif self.scope == "drafts":
            f["status"] = "Draft"
        elif self.scope == "under_review":
            f["status"] = "Under Review"
        return f

    def refresh(self) -> None:
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        try:
            rows = data.list_documents(**self._filters())
        except ValidationError as e:
            messagebox.showerror("Document Hub", str(e),
                                    parent=self.frame)
            return
        for d in rows:
            tag = ("overdue" if d.is_overdue_review
                     else d.status)
            self.tree.insert(
                "", "end", iid=str(d.document_id),
                values=(d.document_id,
                         "!" if d.is_overdue_review else "",
                         d.title, d.category, d.audience,
                         d.access_level, d.version,
                         d.issued_on or "—",
                         d.review_on or "—",
                         d.status, d.download_count),
                tags=(tag,))
        self.count.config(text=f"{len(rows)} document(s)")

    def _selected(self) -> Document | None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Document Hub",
                                  "Select a document first.",
                                  parent=self.frame)
            return None
        return data.get_document(int(sel[0]))

    def _new(self) -> None:
        if DocumentEditor(self.frame).result is not None:
            self.refresh()

    def _edit(self) -> None:
        d = self._selected()
        if d and DocumentEditor(
                self.frame,
                document=d).result is not None:
            self.refresh()

    def _submit(self) -> None:
        d = self._selected()
        if not d:
            return
        try:
            data.submit_for_review(d.document_id)
        except ValidationError as e:
            messagebox.showerror("Document Hub", str(e),
                                    parent=self.frame)
            return
        self.refresh()

    def _approve(self) -> None:
        d = self._selected()
        if not d:
            return
        approver = _prompt_text(self.frame, "Approved by",
                                  initial=d.approved_by or "")
        try:
            data.approve(d.document_id,
                              approved_by=approver or None)
        except ValidationError as e:
            messagebox.showerror("Document Hub", str(e),
                                    parent=self.frame)
            return
        self.refresh()

    def _publish(self) -> None:
        d = self._selected()
        if not d:
            return
        try:
            data.publish(d.document_id)
        except ValidationError as e:
            messagebox.showerror("Document Hub", str(e),
                                    parent=self.frame)
            return
        self.refresh()

    def _withdraw(self) -> None:
        d = self._selected()
        if not d:
            return
        try:
            data.withdraw(d.document_id)
        except ValidationError as e:
            messagebox.showerror("Document Hub", str(e),
                                    parent=self.frame)
            return
        self.refresh()

    def _archive(self) -> None:
        d = self._selected()
        if not d:
            return
        try:
            data.archive(d.document_id)
        except ValidationError as e:
            messagebox.showerror("Document Hub", str(e),
                                    parent=self.frame)
            return
        self.refresh()

    def _supersede(self) -> None:
        d = self._selected()
        if not d:
            return
        new_v = _prompt_text(
            self.frame,
            f"New version (current: {d.version})",
            initial="")
        if not new_v:
            return
        try:
            data.supersede(d.document_id,
                                new_version=new_v,
                                carry_over=True)
        except ValidationError as e:
            messagebox.showerror("Document Hub", str(e),
                                    parent=self.frame)
            return
        self.refresh()

    def _set_status(self) -> None:
        d = self._selected()
        if not d:
            return
        new = _prompt_choice(self.frame, "New status",
                                list(STATUSES),
                                default=d.status)
        if not new:
            return
        try:
            data.set_status(d.document_id, new)
        except ValidationError as e:
            messagebox.showerror("Document Hub", str(e),
                                    parent=self.frame)
            return
        self.refresh()

    def _auto_archive(self) -> None:
        n = data.auto_archive_expired()
        messagebox.showinfo("Document Hub",
                              f"{n} document(s) archived.",
                              parent=self.frame)
        self.refresh()

    def _delete(self) -> None:
        d = self._selected()
        if not d:
            return
        if not messagebox.askyesno(
                "Document Hub",
                f"Delete document #{d.document_id}?",
                parent=self.frame):
            return
        data.delete_document(d.document_id)
        self.refresh()


class SummaryTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Summary")
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="left")
        self.text = tk.Text(self.frame, wrap="word",
                              font=("TkFixedFont", 10))
        self.text.pack(fill="both", expand=True, padx=8,
                          pady=(4, 8))
        self.refresh()

    def refresh(self) -> None:
        s = data.summary()
        self.text.config(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("end", "Document Hub Summary\n")
        self.text.insert("end", "=" * 60 + "\n\n")
        self.text.insert("end",
                            f"Total                : {s.total}\n"
                            f"Drafts               : {s.drafts}\n"
                            f"Under review         : {s.under_review}\n"
                            f"Approved             : {s.approved}\n"
                            f"Published            : {s.published}\n"
                            f"Superseded           : {s.superseded}\n"
                            f"Archived             : {s.archived}\n"
                            f"Overdue for review   : {s.overdue_review}\n"
                            f"Expired unprocessed  : {s.expired_unprocessed}\n"
                            f"Confidential         : {s.confidential}\n"
                            f"Total downloads      : {s.total_downloads}\n\n")
        self.text.insert("end", "By category:\n")
        for k in CATEGORIES:
            n = s.by_category.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<22}: {n}\n")
        self.text.insert("end", "\nBy audience:\n")
        for k in AUDIENCES:
            n = s.by_audience.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<22}: {n}\n")
        self.text.insert("end", "\nBy access:\n")
        for k in ACCESS_LEVELS:
            n = s.by_access.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<14}: {n}\n")
        self.text.insert("end", "\nBy status:\n")
        for k in STATUSES:
            n = s.by_status.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<14}: {n}\n")
        self.text.config(state="disabled")


# ── Editor ──────────────────────────────────────────────

class DocumentEditor:
    def __init__(self, parent, *,
                 document: Document | None = None) -> None:
        self.document = document
        self.result: Document | None = None
        self.win = tk.Toplevel(parent)
        self.win.title(
            f"Edit document #{document.document_id}"
            if document else "New document")
        self.win.geometry("900x820")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        self._build()
        if document:
            self._load()
        self.win.wait_window()

    def _build(self) -> None:
        body = ttk.Frame(self.win)
        body.pack(fill="both", expand=True, padx=12, pady=10)
        body.grid_columnconfigure(1, weight=1)
        body.grid_columnconfigure(3, weight=1)
        self.vars: dict[str, tk.Variable] = {}
        self.texts: dict[str, tk.Text] = {}

        def entry(row, col, label, key, width=22):
            ttk.Label(body, text=label).grid(
                row=row, column=col, sticky="w",
                padx=4, pady=2)
            v = tk.StringVar()
            self.vars[key] = v
            ttk.Entry(body, textvariable=v, width=width).grid(
                row=row, column=col + 1, sticky="ew",
                padx=4, pady=2)

        def combo(row, col, label, key, values, width=22):
            ttk.Label(body, text=label).grid(
                row=row, column=col, sticky="w",
                padx=4, pady=2)
            v = tk.StringVar()
            self.vars[key] = v
            ttk.Combobox(body, textvariable=v, values=values,
                          state="readonly", width=width).grid(
                row=row, column=col + 1, sticky="ew",
                padx=4, pady=2)

        entry(0, 0, "Title*", "title", width=48)
        combo(1, 0, "Category*", "category", CATEGORIES)
        combo(1, 2, "Audience*", "audience", AUDIENCES)
        combo(2, 0, "Access level*", "access_level",
                 ACCESS_LEVELS)
        combo(2, 2, "Status*", "status", STATUSES)
        entry(3, 0, "Version*", "version")
        entry(3, 2, "Supersedes id", "supersedes_id")
        entry(4, 0, "File ref / URL", "file_ref", width=48)
        entry(5, 0, "File format", "file_format")
        entry(5, 2, "File size (kB)", "file_size_kb")
        entry(6, 0, "Author", "author")
        entry(6, 2, "Owner department", "owner_department")
        entry(7, 0, "Approved by", "approved_by")
        entry(7, 2, "Linked to", "linked_to")
        entry(8, 0, "Issued on (YYYY-MM-DD)", "issued_on")
        entry(8, 2, "Review on (YYYY-MM-DD)", "review_on")
        entry(9, 0, "Expires on (YYYY-MM-DD)", "expires_on")
        entry(10, 0, "Keywords (CSV)", "keywords", width=48)

        row = 11
        for key, label, h in (
                ("description", "Description", 4),
                ("notes",       "Notes", 3),
        ):
            ttk.Label(body, text=label).grid(
                row=row, column=0, sticky="nw",
                padx=4, pady=(6, 2))
            t = tk.Text(body, height=h, width=74, wrap="word")
            t.grid(row=row, column=1, columnspan=3,
                     sticky="ew", padx=4, pady=(6, 2))
            self.texts[key] = t
            row += 1

        bar = ttk.Frame(self.win)
        bar.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="right",
                                               padx=4)
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="right")

        self.vars["category"].set(DEFAULT_CATEGORY)
        self.vars["audience"].set(DEFAULT_AUDIENCE)
        self.vars["access_level"].set(DEFAULT_ACCESS)
        self.vars["status"].set(DEFAULT_STATUS)
        self.vars["version"].set("1.0")

    def _load(self) -> None:
        d = self.document
        assert d is not None
        for key in ("title", "category", "audience",
                     "access_level", "status", "version",
                     "file_ref", "file_format", "author",
                     "owner_department", "approved_by",
                     "linked_to", "issued_on", "review_on",
                     "expires_on", "keywords"):
            self.vars[key].set(getattr(d, key) or "")
        self.vars["file_size_kb"].set(
            str(d.file_size_kb or ""))
        self.vars["supersedes_id"].set(
            str(d.supersedes_id or ""))
        for k in self.texts:
            self.texts[k].delete("1.0", "end")
            self.texts[k].insert("1.0", getattr(d, k) or "")

    def _save(self) -> None:
        payload: dict = {}
        for k, v in self.vars.items():
            payload[k] = v.get().strip()
        for k, t in self.texts.items():
            payload[k] = t.get("1.0", "end").rstrip()
        try:
            if self.document:
                self.result = data.update_document(
                    self.document.document_id, payload)
            else:
                self.result = data.create_document(payload)
        except ValidationError as exc:
            messagebox.showerror("Document Hub", str(exc),
                                    parent=self.win)
            return
        self.win.destroy()


def _prompt_text(parent, title: str, *,
                  initial: str = "") -> str | None:
    win = tk.Toplevel(parent)
    win.title(title); win.geometry("420x140")
    win.transient(parent); win.after_idle(win.grab_set)
    ttk.Label(win, text=title).pack(anchor="w", padx=8, pady=8)
    var = tk.StringVar(value=initial)
    ttk.Entry(win, textvariable=var).pack(fill="x", padx=8)
    result: dict = {"value": None}

    def ok() -> None:
        result["value"] = var.get().strip()
        win.destroy()

    bar = ttk.Frame(win)
    bar.pack(fill="x", padx=8, pady=12)
    ttk.Button(bar, text="OK", command=ok).pack(side="right",
                                                    padx=4)
    ttk.Button(bar, text="Cancel",
                command=win.destroy).pack(side="right")
    win.wait_window()
    return result["value"]


def _prompt_choice(parent, title: str, options: list[str], *,
                    default: str | None = None) -> str | None:
    win = tk.Toplevel(parent)
    win.title(title); win.geometry("360x140")
    win.transient(parent); win.after_idle(win.grab_set)
    ttk.Label(win, text=title).pack(anchor="w", padx=8, pady=8)
    var = tk.StringVar(
        value=default or (options[0] if options else ""))
    ttk.Combobox(win, textvariable=var, values=options,
                  state="readonly").pack(fill="x", padx=8)
    result: dict = {"value": None}

    def ok() -> None:
        result["value"] = var.get()
        win.destroy()

    bar = ttk.Frame(win)
    bar.pack(fill="x", padx=8, pady=12)
    ttk.Button(bar, text="OK", command=ok).pack(side="right",
                                                    padx=4)
    ttk.Button(bar, text="Cancel",
                command=win.destroy).pack(side="right")
    win.wait_window()
    return result["value"]


__all__ = ["open_document_hub_window"]
