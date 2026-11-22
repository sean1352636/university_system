"""Disabilities in the Disability & Accessibility portal.

* :class:`DisabilityEditor` — a list being entered (category, details, an
  adjustment if one is needed), not yet saved anywhere. Create Student uses
  it for a student who doesn't exist yet; the panels below use it for
  additions.
* :class:`DisabilitiesPanel` — the saved record: staff look up any student
  (audited), add and remove; a student sees their own and can tell us about
  another.

Everything saved goes through ``domain/disability/portal``.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from education_system.systems.university.domains.student_support.domain.disability import access, portal

logger = logging.getLogger(__name__)

TITLE = "Disability & Accessibility Services"
NO_ADJUSTMENT = "None needed"
_LABEL_TO_KEY = {label: key for key, label in portal.DISABILITY_CATEGORIES.items()}


def _show_error(parent, exc):
    if isinstance(exc, (PermissionError, ValueError)):
        messagebox.showerror(TITLE, str(exc), parent=parent)
    else:
        logger.exception("Disability record action failed")
        messagebox.showerror(TITLE, f"That didn't work: {exc}", parent=parent)


class DisabilityEditor(ttk.Frame):
    """Enter one or more disabilities. :meth:`get_items` returns them as
    ``[{'category', 'details', 'adjustment_type'}]``."""

    def __init__(self, master, items=None):
        super().__init__(master, padding=8)
        self._items: list[dict] = []

        form = ttk.LabelFrame(self, text="Disability", padding=8)
        form.pack(side=tk.TOP, fill=tk.X)
        form.columnconfigure(1, weight=1)
        ttk.Label(form, text="Category").grid(row=0, column=0, sticky=tk.W, pady=3)
        self.category = ttk.Combobox(form, values=list(portal.DISABILITY_CATEGORIES.values()),
                                     state="readonly", width=48)
        self.category.grid(row=0, column=1, sticky=tk.W, padx=6)
        ttk.Label(form, text="Details").grid(row=1, column=0, sticky=tk.NW, pady=3)
        self.details = tk.Text(form, height=4, width=60, wrap=tk.WORD)
        self.details.grid(row=1, column=1, sticky=tk.EW, padx=6, pady=3)
        ttk.Label(form, text="Adjustment needed").grid(row=2, column=0, sticky=tk.W, pady=3)
        self.adjustment = ttk.Combobox(form, values=[NO_ADJUSTMENT, *portal.ACCOMMODATION_TYPES],
                                       state="readonly", width=24)
        self.adjustment.set(NO_ADJUSTMENT)
        self.adjustment.grid(row=2, column=1, sticky=tk.W, padx=6)
        ttk.Label(form, text="An adjustment goes to disability services as a request to approve.",
                  foreground="#555555").grid(row=3, column=1, sticky=tk.W, padx=6)
        btns = ttk.Frame(form)
        btns.grid(row=4, column=1, sticky=tk.W, padx=6, pady=(6, 0))
        ttk.Button(btns, text="Add to list", command=self.add).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(btns, text="Update selected", command=self.update_selected).pack(
            side=tk.LEFT, padx=(0, 4))
        ttk.Button(btns, text="Remove selected", command=self.remove_selected).pack(side=tk.LEFT)

        cols = (("category", "Category", 330), ("adjustment", "Adjustment", 150),
                ("details", "Details", 420))
        self.tree = ttk.Treeview(self, columns=[c[0] for c in cols], show="headings", height=6,
                                 selectmode="browse")
        for key, label, width in cols:
            self.tree.heading(key, text=label)
            self.tree.column(key, width=width, anchor=tk.W)
        self.tree.pack(fill=tk.BOTH, expand=True, pady=(8, 0))
        self.tree.bind("<<TreeviewSelect>>", lambda _e: self._load_selected())
        self.set_items(items or [])

    # --------------------------------------------------------------- data
    def _form_item(self) -> dict:
        return {"category": _LABEL_TO_KEY.get(self.category.get(), ""),
                "details": self.details.get("1.0", tk.END).strip(),
                "adjustment_type": ("" if self.adjustment.get() == NO_ADJUSTMENT
                                    else self.adjustment.get())}

    def _clear_form(self):
        self.category.set("")
        self.details.delete("1.0", tk.END)
        self.adjustment.set(NO_ADJUSTMENT)

    def _refresh(self):
        self.tree.delete(*self.tree.get_children())
        for i, item in enumerate(self._items):
            details = item["details"].replace("\n", " ")
            self.tree.insert("", tk.END, iid=str(i), values=(
                portal.DISABILITY_CATEGORIES.get(item["category"], item["category"]),
                item.get("adjustment_type") or "—",
                details[:90] + ("…" if len(details) > 90 else "")))

    def _load_selected(self):
        sel = self.tree.selection()
        if not sel:
            return
        item = self._items[int(sel[0])]
        self.category.set(portal.DISABILITY_CATEGORIES.get(item["category"], ""))
        self.details.delete("1.0", tk.END)
        self.details.insert("1.0", item["details"])
        self.adjustment.set(item.get("adjustment_type") or NO_ADJUSTMENT)

    def _checked(self):
        try:
            return portal.clean_disabilities([self._form_item()])[0]
        except ValueError as exc:
            messagebox.showerror(TITLE, str(exc).replace("Disability 1: ", ""), parent=self)
            return None

    def add(self):
        item = self._checked()
        if item:
            self._items.append(item)
            self._refresh()
            self._clear_form()

    def update_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo(TITLE, "Select a disability in the list first.", parent=self)
            return
        item = self._checked()
        if item:
            self._items[int(sel[0])] = item
            self._refresh()
            self._clear_form()

    def remove_selected(self):
        sel = self.tree.selection()
        if sel:
            del self._items[int(sel[0])]
            self._refresh()
            self._clear_form()

    def get_items(self) -> list[dict]:
        """The list, plus whatever is still in the form if it wasn't added."""
        pending = self._form_item()
        if pending["category"] or pending["details"]:
            item = self._checked()
            if item is None:
                raise ValueError("Finish or clear the disability being typed.")
            return [*self._items, item]
        return list(self._items)

    def set_items(self, items):
        self._items = [dict(i) for i in items]
        self._refresh()


class DisabilitiesPanel(ttk.Frame):
    """The saved disabilities: any student's for staff, their own for a student."""

    COLUMNS = (("id", "#", 50), ("category_label", "Category", 330),
               ("adjustment_type", "Adjustment", 140), ("source", "Told us", 90),
               ("declared_at", "When", 140), ("details", "Details", 360))

    def __init__(self, master, auth):
        super().__init__(master, padding=8)
        self.auth = auth
        self.staff = access.scope(auth) is None
        self.student_id = None if self.staff else portal.my_student_id(auth)

        bar = ttk.Frame(self)
        bar.pack(fill=tk.X, pady=(0, 6))
        if self.staff:
            ttk.Label(bar, text="Student ID").pack(side=tk.LEFT)
            self.sid_var = tk.StringVar()
            entry = ttk.Entry(bar, textvariable=self.sid_var, width=14)
            entry.pack(side=tk.LEFT, padx=6)
            entry.bind("<Return>", lambda _e: self.load())
            ttk.Button(bar, text="Load", command=self.load).pack(side=tk.LEFT)
            ttk.Label(bar, text="Opening a student's record is recorded in the audit log.",
                      foreground="#555555").pack(side=tk.LEFT, padx=10)
        ttk.Button(bar, text="Add…", command=self.add).pack(side=tk.RIGHT)
        if self.staff:
            ttk.Button(bar, text="Remove…", command=self.remove).pack(side=tk.RIGHT, padx=4)

        table = ttk.Frame(self)
        table.pack(fill=tk.BOTH, expand=True)
        self.tree = ttk.Treeview(table, columns=[c[0] for c in self.COLUMNS], show="headings",
                                 selectmode="browse")
        for key, label, width in self.COLUMNS:
            self.tree.heading(key, text=label)
            self.tree.column(key, width=width, anchor=tk.W)
        sb = ttk.Scrollbar(table, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        if not self.staff:
            self.load()

    def _sid(self):
        if not self.staff:
            return self.student_id
        sid = self.sid_var.get().strip()
        if not sid:
            messagebox.showinfo(TITLE, "Enter a student ID first.", parent=self)
        return sid or None

    def load(self):
        sid = self._sid()
        if not sid:
            return
        try:
            rows = portal.list_disabilities(self.auth, sid)
        except Exception as exc:
            _show_error(self, exc)
            return
        self.loaded = sid
        self.tree.delete(*self.tree.get_children())
        for r in rows:
            self.tree.insert("", tk.END, iid=str(r["id"]), values=(
                r["id"], r["category_label"], r.get("adjustment_type") or "—", r["source"],
                str(r["declared_at"])[:16], (r.get("details") or "").replace("\n", " ")))

    def add(self):
        sid = self._sid()
        if not sid:
            return
        win = tk.Toplevel(self)
        win.title(f"Add disabilities — {sid}")
        win.geometry("960x520")
        win.transient(self.winfo_toplevel())
        editor = DisabilityEditor(win)
        bar = ttk.Frame(win, padding=8)
        bar.pack(side=tk.BOTTOM, fill=tk.X)
        editor.pack(fill=tk.BOTH, expand=True)

        def save():
            try:
                items = editor.get_items()
                if not items:
                    raise ValueError("Add at least one disability to the list.")
                result = portal.add_disabilities(self.auth, sid, items)
            except Exception as exc:
                _show_error(win, exc)
                return
            win.destroy()
            note = (f"\n\n{len(result['requests'])} adjustment request(s) sent to disability "
                    "services." if result["requests"] else "")
            messagebox.showinfo(TITLE, f"Saved {len(result['disabilities'])} disability record(s)."
                                + note, parent=self)
            if self.staff:
                self.sid_var.set(sid)
            self.load()

        ttk.Button(bar, text="Save", command=save).pack(side=tk.RIGHT)
        ttk.Button(bar, text="Cancel", command=win.destroy).pack(side=tk.RIGHT, padx=4)

    def remove(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo(TITLE, "Select a disability first.", parent=self)
            return
        reason = simpledialog.askstring(TITLE, "Why is it being removed?", parent=self)
        if reason is None:
            return
        try:
            portal.remove_disability(self.auth, int(sel[0]), reason)
        except Exception as exc:
            _show_error(self, exc)
            return
        self.load()
