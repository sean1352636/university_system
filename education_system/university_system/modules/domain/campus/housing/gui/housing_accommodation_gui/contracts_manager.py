"""Contract / lease document attachment screen.

Pick an assignment, upload PDFs/scans, list/open/delete attached
documents. Files are stored under ``data/housing/contracts/<asg>/``;
metadata in ``housing_contract_documents``.
"""

from __future__ import annotations

import logging
import sqlite3
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import ttk, messagebox, filedialog

from education_system.university_system.infrastructure.database.db import (
    get_connection,
)
from education_system.university_system.modules.shared.utils.simple_activity_logger import (
    log_activity,
)
from education_system.university_system.modules.domain.campus.housing.services.housing_accommodation import (
    extras,
)

logger = logging.getLogger(__name__)


def show_contracts(gui_instance) -> None:
    extras.init_extras_schemas()
    gui_instance.clear_content()
    parent = gui_instance.content_frame

    ttk.Label(parent, text="Lease / Contract Documents",
              font=("Arial", 14, "bold")).pack(anchor="w", padx=8,
                                                pady=(8, 4))

    pick = ttk.Frame(parent)
    pick.pack(fill="x", padx=8, pady=4)
    ttk.Label(pick, text="Assignment:").pack(side="left", padx=(0, 4))
    asg_var = tk.StringVar()
    combo = ttk.Combobox(pick, textvariable=asg_var, state="readonly",
                          width=68)
    asgs = _load_assignments()
    combo['values'] = [a[1] for a in asgs] or ["(no assignments)"]
    if asgs:
        combo.current(0)
    else:
        combo.configure(state="disabled")
    combo.pack(side="left")

    cols = ("doc_id", "filename", "uploaded_by", "uploaded_at", "notes")
    tree = ttk.Treeview(parent, columns=cols, show="headings", height=12)
    for k, lbl, w in [
        ("doc_id", "Doc ID", 130),
        ("filename", "Filename", 320),
        ("uploaded_by", "Uploaded by", 140),
        ("uploaded_at", "Uploaded at", 160),
        ("notes", "Notes", 280),
    ]:
        tree.heading(k, text=lbl)
        tree.column(k, width=w, anchor="w")
    tree.pack(fill="both", expand=True, padx=8, pady=4)

    summary_var = tk.StringVar()
    ttk.Label(parent, textvariable=summary_var,
              foreground="#666").pack(anchor="w", padx=8)

    def reload() -> None:
        for it in tree.get_children():
            tree.delete(it)
        i = combo.current()
        if i < 0 or i >= len(asgs):
            summary_var.set("")
            return
        docs = extras.list_contract_documents(asgs[i][0])
        for d in docs:
            tree.insert("", "end", iid=d['doc_id'], values=(
                d['doc_id'], d['original_filename'], d['uploaded_by'],
                d['uploaded_at'], d.get('notes') or ''))
        summary_var.set(f"{len(docs)} document(s)")

    combo.bind("<<ComboboxSelected>>", lambda _e: reload())

    bar = ttk.Frame(parent)
    bar.pack(fill="x", padx=8, pady=(0, 6))

    def upload():
        i = combo.current()
        if i < 0 or i >= len(asgs):
            return
        path = filedialog.askopenfilename(
            parent=gui_instance.root,
            title="Select contract document",
            filetypes=[("PDF / scans", "*.pdf *.png *.jpg *.jpeg *.tif"),
                       ("All files", "*.*")])
        if not path:
            return
        notes = tk.simpledialog.askstring("Notes",
                                            "Optional notes:",
                                            parent=gui_instance.root) \
            if hasattr(tk, 'simpledialog') else None
        who = (gui_instance.auth.current_user.get('username')
                if gui_instance.auth and gui_instance.auth.current_user
                else 'housing-admin')
        try:
            did = extras.save_contract_document(
                asgs[i][0], path, uploaded_by=who, notes=notes)
        except Exception as e:
            logger.exception("Contract upload failed")
            messagebox.showerror("Upload", f"Upload failed:\n\n{e}",
                                  parent=gui_instance.root)
            return
        if not did:
            messagebox.showerror("Upload",
                                  "Upload failed (see logs).",
                                  parent=gui_instance.root)
            return
        log_activity(f"Contract document {did} attached to {asgs[i][0]}")
        reload()

    def open_selected():
        sel = tree.focus()
        if not sel:
            return
        try:
            conn = get_connection()
            try:
                row = conn.execute(
                    "SELECT stored_path FROM housing_contract_documents "
                    "WHERE doc_id = ?", (sel,)).fetchone()
            finally:
                conn.close()
        except sqlite3.Error as e:
            logger.exception("Open contract failed")
            messagebox.showerror("Open", f"DB error:\n\n{e}",
                                  parent=gui_instance.root)
            return
        if not row:
            return
        path = Path(row[0])
        if not path.exists():
            messagebox.showerror("Open",
                                  f"File missing on disk:\n{path}",
                                  parent=gui_instance.root)
            return
        _open_with_default_app(str(path))

    def delete_selected():
        sel = tree.focus()
        if not sel:
            return
        if not messagebox.askyesno("Delete",
                                     f"Delete document {sel}?",
                                     parent=gui_instance.root):
            return
        if extras.delete_contract_document(sel):
            log_activity(f"Contract document {sel} deleted")
            reload()
        else:
            messagebox.showerror("Delete",
                                  "Delete failed (see logs).",
                                  parent=gui_instance.root)

    ttk.Button(bar, text="Upload…", command=upload).pack(side="left")
    ttk.Button(bar, text="Open selected",
               command=open_selected).pack(side="left", padx=4)
    ttk.Button(bar, text="Delete selected",
               command=delete_selected).pack(side="left", padx=4)
    ttk.Button(bar, text="Refresh",
               command=reload).pack(side="right")

    reload()


def _load_assignments() -> list[tuple[str, str]]:
    try:
        conn = get_connection()
        try:
            return [(r[0], r[1]) for r in conn.execute('''
                SELECT a.assignment_id,
                       a.assignment_id || ' · '
                       || s.first_name || ' ' || s.last_name
                       || ' · Room ' || r.room_number
                       || ' · ' || b.building_name
                       || ' (' || a.status || ')'
                FROM housing_assignments a
                JOIN students s ON s.student_id = a.student_id
                JOIN housing_rooms r ON r.room_id = a.room_id
                JOIN housing_buildings b ON b.building_id = r.building_id
                ORDER BY a.status='Active' DESC, b.building_name, r.room_number
            ''')]
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("Could not list assignments for contracts")
        return []


def _open_with_default_app(path: str) -> None:
    try:
        if sys.platform.startswith('darwin'):
            subprocess.run(['open', path], check=False)
        elif sys.platform.startswith('win'):
            import os as _os
            _os.startfile(path)  # type: ignore[attr-defined]
        else:
            subprocess.run(['xdg-open', path], check=False)
    except Exception:
        logger.exception("Could not open file via system handler: %s", path)
