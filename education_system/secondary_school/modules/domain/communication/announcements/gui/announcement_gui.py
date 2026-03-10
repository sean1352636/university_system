"""Announcements GUI."""

import tkinter as tk
from tkinter import ttk, messagebox
from education_system.secondary_school.modules.domain.communication.announcements.services.announcement_service import (
    AnnouncementService, AUDIENCES, PRIORITIES,
)

HEADER_BG = "#1a5276"
MAIN_BG = "#ecf0f1"


class AnnouncementFrame(tk.Frame):
    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = AnnouncementService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg=MAIN_BG)
        header = tk.Frame(self, bg=HEADER_BG, height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Announcements", font=("Helvetica", 15, "bold"),
                 bg=HEADER_BG, fg="white").pack(side="left", padx=20, pady=10)
        toolbar = tk.Frame(self, bg=MAIN_BG, pady=8)
        toolbar.pack(fill="x", padx=15)
        ttk.Button(toolbar, text="New Announcement", command=self._on_add).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Toggle Publish", command=self._on_toggle).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Delete", command=self._on_delete).pack(side="left", padx=4)

        tree_frame = tk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=15, pady=(0, 5))
        cols = ("priority", "title", "audience", "year", "by", "date", "published")
        self._tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")
        for col, h, w in [("priority", "Priority", 55), ("title", "Title", 220),
                           ("audience", "Audience", 70), ("year", "Year", 40),
                           ("by", "By", 80), ("date", "Date", 120), ("published", "Published", 55)]:
            self._tree.heading(col, text=h)
            self._tree.column(col, width=w, anchor="center")
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        self._tree.bind("<<TreeviewSelect>>", self._on_select)
        self._preview = tk.Text(self, height=5, wrap="word", font=("Helvetica", 10),
                                state="disabled", bg="white")
        self._preview.pack(fill="x", padx=15, pady=(0, 10))

        self._status_var = tk.StringVar(value="Ready")
        tk.Label(self, textvariable=self._status_var, bg=MAIN_BG, anchor="w",
                 font=("Helvetica", 9), fg="#7f8c8d").pack(fill="x", padx=15, pady=(0, 8))
        self._data = {}

    def refresh(self):
        self._load()

    def _load(self):
        self._tree.delete(*self._tree.get_children())
        self._data.clear()
        try:
            anns = self._svc.list_announcements(published_only=False)
            for a in anns:
                iid = str(a["id"])
                self._tree.insert("", "end", iid=iid, values=(
                    a["priority"], a["title"], a["audience"],
                    a.get("year_group") or "", a.get("created_by") or "",
                    a["created_at"][:16] if a.get("created_at") else "",
                    "Yes" if a["published"] else "No"))
                self._data[iid] = a
            self._status_var.set(f"{len(anns)} announcement(s)")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_select(self, _=None):
        sel = self._tree.selection()
        self._preview.configure(state="normal")
        self._preview.delete("1.0", "end")
        if sel and sel[0] in self._data:
            self._preview.insert("1.0", self._data[sel[0]].get("body", ""))
        self._preview.configure(state="disabled")

    def _on_add(self):
        dlg = tk.Toplevel(self)
        dlg.title("New Announcement")
        dlg.geometry("500x380")
        dlg.resizable(False, False)
        pad = {"padx": 10, "pady": 4}
        c = tk.Frame(dlg, padx=15, pady=10)
        c.pack(fill="both", expand=True)
        vars_ = {}
        for row, (l, k, d, vals) in enumerate([
            ("Title", "title", "", None), ("Audience", "audience", "all", list(AUDIENCES)),
            ("Year Group", "year_group", "", None), ("Priority", "priority", "normal", list(PRIORITIES))]):
            tk.Label(c, text=l, font=("Helvetica", 9, "bold")).grid(row=row, column=0, sticky="w", **pad)
            vars_[k] = tk.StringVar(value=d)
            if vals:
                ttk.Combobox(c, textvariable=vars_[k], values=vals, state="readonly", width=28).grid(row=row, column=1, **pad)
            else:
                ttk.Entry(c, textvariable=vars_[k], width=30).grid(row=row, column=1, **pad)
        row = 4
        tk.Label(c, text="Body", font=("Helvetica", 9, "bold")).grid(row=row, column=0, sticky="nw", **pad)
        body_text = tk.Text(c, width=35, height=8, wrap="word", font=("Helvetica", 10))
        body_text.grid(row=row, column=1, sticky="nsew", **pad)
        result = [None]
        def save():
            t = vars_["title"].get().strip()
            b = body_text.get("1.0", "end").strip()
            if not t or not b:
                messagebox.showwarning("Validation", "Title and body required.")
                return
            result[0] = {"title": t, "body": b}
            for k in ("audience", "year_group", "priority"):
                result[0][k] = vars_[k].get().strip() or None
            dlg.destroy()
        ttk.Button(c, text="Publish", command=save).grid(row=5, column=0, columnspan=2, pady=10)
        self.wait_window(dlg)
        if result[0] is None:
            return
        d = result[0]
        created_by = self._auth.get("username") if self._auth else None
        self._svc.create(d["title"], d["body"], d.get("audience") or "all",
                         d.get("year_group"), d.get("priority") or "normal", created_by)
        self._load()

    def _on_toggle(self):
        sel = self._tree.selection()
        if not sel:
            return
        self._svc.toggle_publish(int(sel[0]))
        self._load()

    def _on_delete(self):
        sel = self._tree.selection()
        if not sel:
            return
        if messagebox.askyesno("Confirm", "Delete this announcement?"):
            self._svc.delete(int(sel[0]))
            self._load()
