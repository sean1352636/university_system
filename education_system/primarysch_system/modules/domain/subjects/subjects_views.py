"""Tk views for the subjects catalogue."""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable

from education_system.primarysch_system.modules.domain.subjects import (
    subjects as data,
)
from education_system.primarysch_system.modules.domain.subjects.subjects import (
    KEY_STAGES, QUALIFICATIONS,
)
from education_system.primarysch_system.modules.domain.pupils.pupils import (
    ValidationError,
)

logger = logging.getLogger(__name__)


def _safe_view(func: Callable[..., None]) -> Callable[..., None]:
    @functools.wraps(func)
    def wrapper(host, *args, **kwargs):
        try:
            return func(host, *args, **kwargs)
        except ValidationError as e:
            logger.warning("%s validation: %s", func.__name__, e)
            try:
                messagebox.showerror("Subjects", str(e),
                                     parent=getattr(host, "root", None))
            except Exception:
                pass
        except Exception as e:
            logger.exception("%s failed", func.__name__)
            try:
                messagebox.showerror(
                    "Error",
                    f"An unexpected error occurred:\n\n{e}\n\nSee logs for details.",
                    parent=getattr(host, "root", None),
                )
            except Exception:
                pass
    return wrapper


def _form_dialog(host, title: str, initial: dict[str, Any] | None = None
                 ) -> dict[str, Any] | None:
    dlg = tk.Toplevel(host.root)
    dlg.title(title)
    dlg.transient(host.root)
    dlg.geometry("460x420")
    dlg.update_idletasks()
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped — dialog not viewable", exc_info=True)

    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)
    initial = initial or {}

    code_var  = tk.StringVar(value=str(initial.get("code") or ""))
    name_var  = tk.StringVar(value=str(initial.get("name") or ""))
    ks_var    = tk.StringVar(value=str(initial.get("key_stage") or "Both"))
    qual_var  = tk.StringVar(value=str(initial.get("qualification") or "GCSE"))
    dept_var  = tk.StringVar(value=str(initial.get("department") or ""))
    core_var  = tk.BooleanVar(value=bool(initial.get("is_core")))
    active_var = tk.BooleanVar(
        value=True if initial.get("is_active") is None
        else bool(initial.get("is_active")))
    notes_var = tk.StringVar(value=str(initial.get("notes") or ""))

    rows: list[tuple[str, tk.Widget]] = [
        ("Code:",          ttk.Entry(frm, textvariable=code_var, width=18)),
        ("Name:",          ttk.Entry(frm, textvariable=name_var, width=34)),
        ("Key stage:",     ttk.Combobox(frm, textvariable=ks_var,
                                         values=list(KEY_STAGES),
                                         state="readonly", width=10)),
        ("Qualification:", ttk.Combobox(frm, textvariable=qual_var,
                                         values=list(QUALIFICATIONS),
                                         state="readonly", width=10)),
        ("Department:",    ttk.Entry(frm, textvariable=dept_var, width=34)),
        ("Core?",          ttk.Checkbutton(frm, variable=core_var)),
        ("Active?",        ttk.Checkbutton(frm, variable=active_var)),
        ("Notes:",         ttk.Entry(frm, textvariable=notes_var, width=34)),
    ]
    for i, (label, widget) in enumerate(rows):
        ttk.Label(frm, text=label).grid(row=i, column=0, sticky="w", pady=2)
        widget.grid(row=i, column=1, sticky="ew", pady=2)
    frm.columnconfigure(1, weight=1)

    result: dict[str, Any] | None = None

    def _save() -> None:
        nonlocal result
        result = {
            "code":          code_var.get().strip(),
            "name":          name_var.get().strip(),
            "key_stage":     ks_var.get().strip(),
            "qualification": qual_var.get().strip(),
            "department":    dept_var.get().strip(),
            "is_core":       bool(core_var.get()),
            "is_active":     bool(active_var.get()),
            "notes":         notes_var.get().strip(),
        }
        dlg.destroy()

    btns = ttk.Frame(frm)
    btns.grid(row=len(rows), column=0, columnspan=2, sticky="e",
              pady=(12, 0))
    ttk.Button(btns, text="Cancel", command=dlg.destroy).pack(side="right",
                                                               padx=4)
    ttk.Button(btns, text="Save", command=_save).pack(side="right")

    dlg.wait_window()
    return result


@_safe_view
def open_subjects(host) -> None:
    logger.debug("GUI: open_subjects")
    host._clear_content()
    root = host.content_frame
    ttk.Label(root, text="Subjects (KS3 / GCSE)",
              font=("", 16, "bold")).pack(anchor="w", pady=(0, 8))

    summary_var = tk.StringVar()
    ttk.Label(root, textvariable=summary_var, foreground="#666").pack(
        anchor="w", pady=(0, 8))

    bar = ttk.Frame(root)
    bar.pack(fill="x", pady=(0, 6))
    ttk.Label(bar, text="Key stage:").pack(side="left", padx=(0, 4))
    ks_var = tk.StringVar(value="")
    ttk.Combobox(bar, textvariable=ks_var,
                 values=["", *KEY_STAGES], state="readonly", width=8).pack(
        side="left", padx=(0, 8))
    ttk.Label(bar, text="Qualification:").pack(side="left", padx=(0, 4))
    qual_var = tk.StringVar(value="")
    ttk.Combobox(bar, textvariable=qual_var,
                 values=["", *QUALIFICATIONS], state="readonly", width=8).pack(
        side="left", padx=(0, 8))
    active_var = tk.BooleanVar(value=False)
    ttk.Checkbutton(bar, text="Active only",
                    variable=active_var,
                    command=lambda: _refresh()).pack(side="left", padx=(0, 8))
    ttk.Button(bar, text="New",
               command=lambda: _new(host, on_done=_refresh)).pack(side="left",
                                                                   padx=2)
    ttk.Button(bar, text="Edit",
               command=lambda: _edit_selected(host, tree, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Toggle Active",
               command=lambda: _toggle_selected(host, tree, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Delete",
               command=lambda: _delete_selected(host, tree, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: _refresh()).pack(side="left", padx=2)

    cols = ("id", "code", "name", "ks", "qual", "dept", "core", "active")
    tree = ttk.Treeview(root, columns=cols, show="headings", height=18)
    for c, label, w in [
        ("id", "ID", 50), ("code", "Code", 80),
        ("name", "Name", 220), ("ks", "Key Stage", 80),
        ("qual", "Qualification", 100), ("dept", "Department", 140),
        ("core", "Core", 60), ("active", "Active", 70),
    ]:
        tree.heading(c, text=label)
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True)

    def _refresh() -> None:
        for i in tree.get_children():
            tree.delete(i)
        try:
            rows = data.list_all(
                key_stage=ks_var.get().strip() or None,
                qualification=qual_var.get().strip() or None,
                active_only=bool(active_var.get()),
            )
        except ValidationError as e:
            messagebox.showerror("Subjects", str(e), parent=host.root)
            return
        except Exception as e:
            logger.exception("subjects refresh failed")
            messagebox.showerror("Subjects",
                                 f"Could not load subjects:\n\n{e}",
                                 parent=host.root)
            return
        for s in rows:
            tree.insert("", "end", iid=str(s.subject_id), values=(
                s.subject_id, s.code, s.name, s.key_stage, s.qualification,
                s.department or "-",
                "Yes" if s.is_core else "No",
                "Yes" if s.is_active else "No",
            ))
        try:
            c = data.counts()
            summary_var.set(
                f"Total: {c['total']}    Active: {c['active']}    "
                f"Inactive: {c['inactive']}    Core: {c['core']}")
        except Exception:
            logger.exception("subjects counts failed")
            summary_var.set("(counts unavailable)")
        host.status_var.set(f"Subjects: {len(rows)} record(s)")

    tree.bind("<Double-1>", lambda _e: _edit_selected(host, tree,
                                                       on_done=_refresh))
    ks_var.trace_add("write", lambda *_: _refresh())
    qual_var.trace_add("write", lambda *_: _refresh())
    _refresh()


def _selected_id(tree: ttk.Treeview, host) -> int | None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Subjects", "Select a subject first.",
                            parent=host.root)
        return None
    try:
        return int(sel)
    except ValueError:
        return None


@_safe_view
def _new(host, *, on_done=None) -> None:
    fields = _form_dialog(host, "New subject")
    if not fields:
        return
    rec = data.create(fields)
    messagebox.showinfo("Subjects",
                        f"Created {rec.code} — {rec.name}",
                        parent=host.root)
    if on_done:
        on_done()


@_safe_view
def _edit_selected(host, tree: ttk.Treeview, *, on_done=None) -> None:
    sid = _selected_id(tree, host)
    if sid is None:
        return
    existing = data.get(sid)
    if existing is None:
        messagebox.showerror("Subjects", f"No subject with id {sid}",
                             parent=host.root)
        return
    initial = {
        "code": existing.code, "name": existing.name,
        "key_stage": existing.key_stage,
        "qualification": existing.qualification,
        "department": existing.department,
        "is_core": existing.is_core, "is_active": existing.is_active,
        "notes": existing.notes,
    }
    fields = _form_dialog(host, f"Edit subject #{sid}", initial=initial)
    if not fields:
        return
    data.update(sid, fields)
    if on_done:
        on_done()


@_safe_view
def _toggle_selected(host, tree: ttk.Treeview, *, on_done=None) -> None:
    sid = _selected_id(tree, host)
    if sid is None:
        return
    rec = data.toggle_active(sid)
    messagebox.showinfo(
        "Subjects",
        f"{rec.code} is now "
        f"{'active' if rec.is_active else 'inactive'}.",
        parent=host.root,
    )
    if on_done:
        on_done()


@_safe_view
def _delete_selected(host, tree: ttk.Treeview, *, on_done=None) -> None:
    sid = _selected_id(tree, host)
    if sid is None:
        return
    existing = data.get(sid)
    if existing is None:
        return
    if not messagebox.askyesno(
            "Delete subject",
            f"Delete {existing.code} ({existing.name})?",
            parent=host.root):
        return
    data.delete(sid)
    if on_done:
        on_done()
