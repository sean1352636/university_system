"""Move-in / move-out checklists with photo attachments.

Pick an assignment, see existing checklists, or create a new one from
the move-in / move-out template. Walk the items, mark each item's
condition, attach photos.
"""

from __future__ import annotations

import logging
import sqlite3
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import ttk, messagebox, filedialog, simpledialog

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


def show_checklists(gui_instance) -> None:
    extras.init_extras_schemas()
    gui_instance.clear_content()
    parent = gui_instance.content_frame

    ttk.Label(parent, text="Move-in / Move-out Checklists",
              font=("Arial", 14, "bold")).pack(anchor="w", padx=8,
                                                pady=(8, 4))

    pick = ttk.Frame(parent)
    pick.pack(fill="x", padx=8, pady=4)
    ttk.Label(pick, text="Assignment:").pack(side="left", padx=(0, 4))
    asg_var = tk.StringVar()
    asg_combo = ttk.Combobox(pick, textvariable=asg_var, state="readonly",
                               width=68)
    asgs = _load_assignments()
    asg_combo['values'] = [a[1] for a in asgs] or ["(no assignments)"]
    if asgs:
        asg_combo.current(0)
    else:
        asg_combo.configure(state="disabled")
    asg_combo.pack(side="left")

    body = ttk.Frame(parent)
    body.pack(fill="both", expand=True, padx=8, pady=4)

    def reload_for_assignment() -> None:
        for w in body.winfo_children():
            w.destroy()
        i = asg_combo.current()
        if i < 0 or i >= len(asgs):
            return
        asg_id = asgs[i][0]

        bar = ttk.Frame(body)
        bar.pack(fill="x")
        ttk.Button(bar, text="New move-in checklist",
                   command=lambda: _new_checklist(
                       gui_instance, asg_id, 'move-in',
                       reload_for_assignment)).pack(side="left")
        ttk.Button(bar, text="New move-out checklist",
                   command=lambda: _new_checklist(
                       gui_instance, asg_id, 'move-out',
                       reload_for_assignment)).pack(side="left", padx=4)
        ttk.Button(bar, text="Refresh",
                   command=reload_for_assignment).pack(side="right")

        cols = ("checklist_id", "template", "created", "completed_by",
                "completed_at")
        tree = ttk.Treeview(body, columns=cols, show="headings", height=6)
        for k, lbl, w in [
            ("checklist_id", "Checklist ID", 140),
            ("template", "Template", 100),
            ("created", "Created", 160),
            ("completed_by", "Completed by", 140),
            ("completed_at", "Completed at", 160),
        ]:
            tree.heading(k, text=lbl)
            tree.column(k, width=w, anchor="w")
        tree.pack(fill="x", pady=4)

        for cl in extras.list_checklists(asg_id):
            tree.insert("", "end", iid=cl['checklist_id'], values=(
                cl['checklist_id'], cl['template'], cl['created_at'],
                cl.get('completed_by') or '—',
                cl.get('completed_at') or '—'))

        def open_selected():
            sel = tree.focus()
            if not sel:
                return
            _open_checklist_window(gui_instance, sel)

        ttk.Button(body, text="Open selected →",
                   command=open_selected).pack(anchor="e", pady=(0, 4))

    asg_combo.bind("<<ComboboxSelected>>", lambda _e: reload_for_assignment())
    reload_for_assignment()


def _new_checklist(gui_instance, asg_id: str, template: str, on_done):
    cl_id = extras.create_checklist(asg_id, template)
    if not cl_id:
        messagebox.showerror("Checklist",
                              "Failed to create checklist (see logs).",
                              parent=gui_instance.root)
        return
    log_activity(f"Checklist {cl_id} ({template}) created for {asg_id}")
    on_done()
    _open_checklist_window(gui_instance, cl_id)


def _open_checklist_window(gui_instance, checklist_id: str):
    win = tk.Toplevel(gui_instance.root)
    win.title(f"Checklist {checklist_id}")
    win.geometry("900x600")
    win.transient(gui_instance.root)

    canvas = tk.Canvas(win, highlightthickness=0)
    sb = ttk.Scrollbar(win, orient="vertical", command=canvas.yview)
    inner = ttk.Frame(canvas)
    inner.bind("<Configure>",
               lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.create_window((0, 0), window=inner, anchor="nw")
    canvas.configure(yscrollcommand=sb.set)
    canvas.pack(side="left", fill="both", expand=True)
    sb.pack(side="right", fill="y")

    items = extras.list_checklist_items(checklist_id)
    if not items:
        ttk.Label(inner, text="No items.",
                  foreground="#a00").pack(padx=10, pady=10)
        return

    condition_vars: dict[str, tk.StringVar] = {}
    notes_vars: dict[str, tk.StringVar] = {}

    for row in items:
        item_id = row['item_id']
        block = ttk.LabelFrame(inner, text=f"{row['area']} — {row['description']}",
                               padding=6)
        block.pack(fill="x", padx=8, pady=4)

        line = ttk.Frame(block)
        line.pack(fill="x")
        ttk.Label(line, text="Condition:").pack(side="left", padx=(0, 4))
        cvar = tk.StringVar(value=row.get('condition') or '')
        condition_vars[item_id] = cvar
        ttk.Combobox(line, textvariable=cvar, state="readonly", width=12,
                     values=["", "Good", "Damaged", "Missing"]).pack(
            side="left", padx=(0, 12))

        ttk.Label(line, text="Notes:").pack(side="left", padx=(0, 4))
        nvar = tk.StringVar(value=row.get('notes') or '')
        notes_vars[item_id] = nvar
        ttk.Entry(line, textvariable=nvar, width=60).pack(side="left",
                                                            fill="x",
                                                            expand=True)

        photo_row = ttk.Frame(block)
        photo_row.pack(fill="x", pady=(4, 0))
        existing = extras.list_photos(item_id)
        ttk.Label(photo_row,
                  text=f"Photos: {len(existing)}").pack(side="left",
                                                         padx=(0, 6))
        ttk.Button(photo_row, text="Add photo…",
                   command=lambda iid=item_id, blk=block:
                   _add_photo(gui_instance, iid, blk)).pack(side="left")
        if existing:
            for ph in existing:
                ttk.Button(photo_row, text="View",
                           command=lambda p=ph['stored_path']:
                           _open_path(p)).pack(side="left", padx=2)

    def save_and_complete():
        try:
            for iid, cvar in condition_vars.items():
                extras.update_checklist_item(
                    iid, condition=cvar.get() or None,
                    notes=notes_vars[iid].get().strip() or None)
            who = (gui_instance.auth.current_user.get('username')
                    if gui_instance.auth and gui_instance.auth.current_user
                    else 'housing-admin')
            extras.complete_checklist(checklist_id, completed_by=who)
            log_activity(f"Checklist {checklist_id} completed by {who}")
            win.destroy()
        except Exception as e:
            logger.exception("Checklist save failed")
            messagebox.showerror("Checklist", f"Save failed:\n\n{e}",
                                  parent=win)

    def save_only():
        try:
            for iid, cvar in condition_vars.items():
                extras.update_checklist_item(
                    iid, condition=cvar.get() or None,
                    notes=notes_vars[iid].get().strip() or None)
            log_activity(f"Checklist {checklist_id} updated")
            messagebox.showinfo("Checklist", "Saved.", parent=win)
        except Exception as e:
            logger.exception("Checklist save failed")
            messagebox.showerror("Checklist", f"Save failed:\n\n{e}",
                                  parent=win)

    bar = ttk.Frame(inner)
    bar.pack(fill="x", padx=8, pady=10)
    ttk.Button(bar, text="Save", command=save_only).pack(side="right",
                                                          padx=4)
    ttk.Button(bar, text="Save & complete",
               command=save_and_complete).pack(side="right")


def _add_photo(gui_instance, item_id: str, parent_widget):
    path = filedialog.askopenfilename(
        parent=gui_instance.root, title="Select photo",
        filetypes=[("Images", "*.jpg *.jpeg *.png *.heic *.gif"),
                   ("All files", "*.*")])
    if not path:
        return
    caption = simpledialog.askstring("Caption", "Optional caption:",
                                       parent=gui_instance.root)
    pid = extras.attach_photo(item_id, path, caption=caption)
    if not pid:
        messagebox.showerror("Photo", "Failed to attach photo (see logs).",
                              parent=gui_instance.root)
        return
    log_activity(f"Photo {pid} attached to checklist item {item_id}")
    messagebox.showinfo("Photo", "Photo attached. Reopen the checklist to "
                                  "see it in the list.",
                         parent=gui_instance.root)


def _open_path(path: str) -> None:
    try:
        if sys.platform.startswith('darwin'):
            subprocess.run(['open', path], check=False)
        elif sys.platform.startswith('win'):
            import os as _os
            _os.startfile(path)  # type: ignore[attr-defined]
        else:
            subprocess.run(['xdg-open', path], check=False)
    except Exception:
        logger.exception("Could not open path: %s", path)


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
        logger.exception("Could not list assignments for checklists")
        return []
