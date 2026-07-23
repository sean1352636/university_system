"""Tkinter About dialog for the Sixth Form System."""

from __future__ import annotations

import logging
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any
from education_system.post_16.sixthform_system.modules.shared import about as data
from education_system.shared import branding

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "780x680"
WIN_MINSIZE = (640, 560)


def open_about_window(parent=None, *, auth: Any = None) -> None:
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"About — {branding.SYSTEM_NAME}")
    win.geometry(WIN_GEOMETRY)
    win.minsize(*WIN_MINSIZE)
    AboutDialog(win, auth=auth)


class AboutDialog:
    def __init__(self, root: tk.Misc, *, auth: Any = None) -> None:
        self.root = root
        self.auth = auth
        self.info = data.build(auth=auth)
        self._build()

    def _build(self) -> None:
        # Header
        head = ttk.Frame(self.root)
        head.pack(fill="x", padx=16, pady=(16, 8))
        ttk.Label(head, text=self.info.system_name,
                   font=("", 18, "bold")).pack(anchor="w")
        ttk.Label(head,
                   text=f"v{self.info.version}   "
                        f"·  {self.info.release_name}   "
                        f"·  {self.info.release_date}",
                   foreground="#555").pack(anchor="w")
        ttk.Separator(self.root, orient="horizontal").pack(
            fill="x", padx=16, pady=4)

        # Notebook of sections
        nb = ttk.Notebook(self.root)
        nb.pack(fill="both", expand=True, padx=16, pady=8)
        self._build_overview(nb)
        self._build_stats(nb)
        self._build_runtime(nb)
        self._build_credits(nb)

        # Footer
        bar = ttk.Frame(self.root)
        bar.pack(fill="x", padx=16, pady=(0, 14))
        ttk.Button(bar, text="Copy as text",
                    command=self._copy).pack(side="left")
        ttk.Button(bar, text="Save report…",
                    command=self._save).pack(side="left", padx=6)
        ttk.Button(bar, text="Close",
                    command=self.root.destroy).pack(side="right")

    def _build_overview(self, nb: ttk.Notebook) -> None:
        frame = ttk.Frame(nb)
        nb.add(frame, text="Overview")
        inner = ttk.Frame(frame)
        inner.pack(fill="x", padx=12, pady=12)
        rows = [
            ("System name",   self.info.system_name),
            ("Slug",          self.info.system_slug),
            ("System key",    self.info.system_key),
            ("Version",       self.info.version),
            ("Release",       self.info.release_name),
            ("Release date",  self.info.release_date),
            ("",              ""),
            ("Signed in as",  self.info.current_user or "(none)"),
            ("Role (sixth-form)", self.info.current_role or "—"),
            ("",              ""),
            ("License",       self.info.license),
            ("Support",       self.info.support),
        ]
        for i, (k, v) in enumerate(rows):
            if not k and not v:
                ttk.Separator(inner, orient="horizontal").grid(
                    row=i, column=0, columnspan=2, sticky="ew", pady=6)
                continue
            ttk.Label(inner, text=f"{k}:", foreground="#555").grid(
                row=i, column=0, sticky="ne", padx=(0, 8), pady=2)
            ttk.Label(inner, text=v, wraplength=520,
                       justify="left").grid(
                row=i, column=1, sticky="w", pady=2)

    def _build_stats(self, nb: ttk.Notebook) -> None:
        frame = ttk.Frame(nb)
        nb.add(frame, text="Quick stats")
        bar = ttk.Frame(frame)
        bar.pack(fill="x", padx=12, pady=(12, 4))
        ttk.Label(bar, text="Row counts from the local database.",
                   foreground="#444").pack(side="left")
        ttk.Button(bar, text="Refresh",
                    command=self._refresh).pack(side="right")

        table_frame = ttk.Frame(frame)
        table_frame.pack(fill="both", expand=True, padx=12,
                            pady=(4, 12))
        cols = ("label", "rows", "table")
        widths = {"label": 220, "rows": 100, "table": 240}
        self.stats_tree = ttk.Treeview(table_frame, columns=cols,
                                          show="headings")
        heads = {"label": "Category", "rows": "Rows",
                 "table": "Table"}
        for c in cols:
            self.stats_tree.heading(c, text=heads[c])
            anchor = "e" if c == "rows" else "w"
            self.stats_tree.column(c, width=widths[c], anchor=anchor)
        vs = ttk.Scrollbar(table_frame, orient="vertical",
                            command=self.stats_tree.yview)
        self.stats_tree.configure(yscrollcommand=vs.set)
        self.stats_tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.stats_tree.tag_configure("missing", foreground="#888",
                                          background="#f6f6f6")
        self._fill_stats()

    def _fill_stats(self) -> None:
        for i in self.stats_tree.get_children():
            self.stats_tree.delete(i)
        for s in self.info.table_stats:
            rows = "—" if s.rows is None else str(s.rows)
            tags = ("missing",) if s.rows is None else ()
            self.stats_tree.insert("", "end", values=(
                s.label, rows, s.table), tags=tags)

    def _build_runtime(self, nb: ttk.Notebook) -> None:
        frame = ttk.Frame(nb)
        nb.add(frame, text="Runtime")
        inner = ttk.Frame(frame)
        inner.pack(fill="x", padx=12, pady=12)
        rows = [
            ("Python",       self.info.python_version),
            ("Platform",     self.info.platform),
            ("Machine",      self.info.machine),
            ("Working dir",  self.info.cwd),
            ("",             ""),
            ("Database",     self.info.db_path),
            ("DB exists",    "Yes" if self.info.db_exists else "No"),
            ("DB size (KB)", (str(self.info.db_size_kb)
                                if self.info.db_exists else "—")),
            ("Generated at", self.info.generated_at),
        ]
        for i, (k, v) in enumerate(rows):
            if not k and not v:
                ttk.Separator(inner, orient="horizontal").grid(
                    row=i, column=0, columnspan=2, sticky="ew", pady=6)
                continue
            ttk.Label(inner, text=f"{k}:", foreground="#555").grid(
                row=i, column=0, sticky="ne", padx=(0, 8), pady=2)
            ttk.Label(inner, text=v, wraplength=540,
                       justify="left").grid(
                row=i, column=1, sticky="w", pady=2)

    def _build_credits(self, nb: ttk.Notebook) -> None:
        frame = ttk.Frame(nb)
        nb.add(frame, text="Credits")
        inner = ttk.Frame(frame)
        inner.pack(fill="both", expand=True, padx=12, pady=12)
        ttk.Label(inner, text="Authors & credits",
                   font=("", 11, "bold")).pack(anchor="w",
                                                  pady=(0, 6))
        for line in self.info.authors:
            ttk.Label(inner, text=f"• {line}",
                       wraplength=540, justify="left").pack(
                anchor="w", pady=1)
        ttk.Separator(inner, orient="horizontal").pack(
            fill="x", pady=10)
        ttk.Label(inner,
                   text=f"License: {self.info.license}",
                   wraplength=540, justify="left").pack(anchor="w")
        ttk.Label(inner,
                   text=f"Support: {self.info.support}",
                   wraplength=540, justify="left").pack(anchor="w",
                                                          pady=(4, 0))

    def _refresh(self) -> None:
        self.info = data.build(auth=self.auth)
        self._fill_stats()

    def _copy(self) -> None:
        body = data.text_report(self.info)
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(body)
            messagebox.showinfo(
                "Copied",
                "About info copied to the clipboard.")
        except tk.TclError as e:
            messagebox.showerror("Copy", str(e))

    def _save(self) -> None:
        body = data.text_report(self.info)
        path = filedialog.asksaveasfilename(
            initialfile="about.txt",
            defaultextension=".txt",
            filetypes=[("Text", "*.txt"), ("Markdown", "*.md"),
                       ("All files", "*.*")])
        if not path:
            return
        try:
            Path(path).write_text(body + "\n", encoding="utf-8")
        except Exception as e:
            messagebox.showerror("Save", str(e))
            return
        messagebox.showinfo("Save", f"Wrote {path}")
