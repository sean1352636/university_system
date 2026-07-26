"""Tkinter views for Allergies & Dietary Requirements (Nursery System).

Renders into the shared content pane of ``main_gui.NurseryMainGUI`` (the
``host``). Lists dietary / allergy records with a tree + toolbar and an
add/edit form dialog — the GUI counterpart of ``allergies_cli.py``.
"""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable

from education_system.systems.nursery.domain.pastoral.health.allergies import (
    allergies as data,
)
from education_system.systems.nursery.domain.pastoral.health.allergies.allergies import (
    CATEGORIES,
    SEVERITIES,
    STATUSES,
    ValidationError,
)

logger = logging.getLogger(__name__)


def _safe_view(func: Callable[..., None]) -> Callable[..., None]:
    @functools.wraps(func)
    def wrapper(host, *args, **kwargs):
        parent = getattr(host, "root", None)
        try:
            return func(host, *args, **kwargs)
        except ValidationError as e:
            logger.warning("%s validation: %s", func.__name__, e)
            try:
                messagebox.showerror(func.__name__, str(e), parent=parent)
            except Exception:
                logger.debug("Could not show validation dialog", exc_info=True)
        except Exception as e:  # noqa: BLE001
            logger.exception("%s failed", func.__name__)
            try:
                messagebox.showerror(
                    "Error",
                    f"An unexpected error occurred:\n\n{e}\n\nSee logs for details.",
                    parent=parent)
            except Exception:
                logger.debug("Could not show error dialog", exc_info=True)
    return wrapper


# (field key, label, kind). Kinds: entry, category, severity, status, check.
_FIELDS: list[tuple[str, str, str]] = [
    ("category",        "Category",         "category"),
    ("allergen",        "Allergen",         "entry"),
    ("severity",        "Severity",         "severity"),
    ("reaction",        "Reaction",         "entry"),
    ("action_required", "Action required",  "entry"),
    ("epipen_required", "EpiPen required",  "check"),
    ("care_plan_ref",   "Care-plan ref",    "entry"),
    ("status",          "Status",           "status"),
    ("notes",           "Notes",            "entry"),
]


def _clear(host) -> ttk.Frame:
    host._clear_content()
    assert host.content_frame is not None
    return host.content_frame


def _header(parent: ttk.Frame, title: str) -> None:
    ttk.Label(parent, text=title, font=("", 16, "bold")).pack(
        anchor="w", pady=(0, 8))


def _pupil_choices() -> list[tuple[str, str]]:
    try:
        return data.list_pupil_choices()
    except Exception:
        logger.exception("Could not load child choices")
        return []


@_safe_view
def open_manager(host) -> None:
    logger.debug("GUI: allergies open_manager")
    root = _clear(host)
    _header(root, "Allergies & Dietary Requirements")

    summary = ttk.Label(root, foreground="#555")
    summary.pack(anchor="w", pady=(0, 6))

    status_var = tk.StringVar(value="(all)")
    category_var = tk.StringVar(value="(all)")

    def _filters() -> tuple[str | None, str | None]:
        st = status_var.get()
        ct = category_var.get()
        return (None if st == "(all)" else st,
                None if ct == "(all)" else ct)

    bar = ttk.Frame(root)
    bar.pack(fill="x", pady=(0, 8))
    ttk.Button(bar, text="Add Record",
               command=lambda: open_add(host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Edit",
               command=lambda: _edit_selected(tree, host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Delete",
               command=lambda: _delete_selected(tree, host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: _refresh(tree, summary, *_filters())).pack(
        side="left", padx=2)

    ttk.Label(bar, text="Status:").pack(side="left", padx=(12, 2))
    sc = ttk.Combobox(bar, textvariable=status_var, width=10, state="readonly",
                      values=["(all)", *STATUSES])
    sc.pack(side="left", padx=2)
    sc.bind("<<ComboboxSelected>>",
            lambda _e: _refresh(tree, summary, *_filters()))
    ttk.Label(bar, text="Category:").pack(side="left", padx=(8, 2))
    cc = ttk.Combobox(bar, textvariable=category_var, width=12, state="readonly",
                      values=["(all)", *CATEGORIES])
    cc.pack(side="left", padx=2)
    cc.bind("<<ComboboxSelected>>",
            lambda _e: _refresh(tree, summary, *_filters()))

    cols = ("id", "child", "category", "allergen", "severity", "epipen", "status")
    tree = ttk.Treeview(root, columns=cols, show="headings", height=17)
    for c, label, w in [
        ("id", "ID", 70), ("child", "Child", 170), ("category", "Category", 100),
        ("allergen", "Allergen", 150), ("severity", "Severity", 100),
        ("epipen", "EpiPen", 70), ("status", "Status", 80),
    ]:
        tree.heading(c, text=label)
        tree.column(c, width=w, anchor="w")
    tree.tag_configure("alert", foreground="#b00020")
    tree.pack(fill="both", expand=True)
    tree.bind("<Double-1>", lambda _e: _edit_selected(tree, host))

    _refresh(tree, summary, *_filters())
    host.status_var.set("Allergies & dietary requirements loaded")


def _refresh(tree: ttk.Treeview, summary: ttk.Label,
             status: str | None, category: str | None) -> None:
    for i in tree.get_children():
        tree.delete(i)
    try:
        rows = data.list_records(status=status, category=category)
        s = data.summary()
    except Exception:
        logger.exception("Could not refresh allergies")
        try:
            messagebox.showerror("Allergies", "Could not load — see logs.")
        except Exception:
            logger.debug("Could not show refresh-error dialog", exc_info=True)
        return
    for r in rows:
        epipen = "Yes" if r.epipen_required else "No"
        tags = ()
        if r.severity == "anaphylaxis" or r.epipen_required:
            tags = ("alert",)
        tree.insert("", "end", iid=r.record_id, values=(
            r.record_id, r.child_name or "-", r.category, r.allergen or "-",
            r.severity or "-", epipen, r.status), tags=tags)
    by_cat = "  ".join(f"{k}={v}" for k, v in sorted(s["by_category"].items()))
    summary.config(text=f"Active records: {s['records']}   "
                        f"EpiPen children: {s['epipen_children']}   "
                        f"Anaphylaxis: {s['anaphylaxis']}"
                        + (f"   ·   {by_cat}" if by_cat else ""))


def _selected(tree: ttk.Treeview, host, verb: str) -> str | None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Allergies", f"Select a record to {verb}.",
                            parent=host.root)
        return None
    return sel


def _edit_selected(tree: ttk.Treeview, host) -> None:
    sel = _selected(tree, host, "edit")
    if sel:
        open_edit(host, sel)


def _delete_selected(tree: ttk.Treeview, host) -> None:
    sel = _selected(tree, host, "delete")
    if not sel:
        return
    r = data.get_record(sel)
    if r is None:
        return
    if not messagebox.askyesno(
            "Delete record",
            f"Delete dietary record {sel} for {r.child_name}?",
            parent=host.root):
        return
    try:
        data.delete_record(sel)
    except Exception as e:  # noqa: BLE001
        logger.exception("Failed to delete dietary %s", sel)
        messagebox.showerror("Delete record", f"Could not delete:\n\n{e}",
                             parent=host.root)
        return
    open_manager(host)
    host.status_var.set(f"Deleted dietary record {sel}")


# ── Form dialog ──────────────────────────────────────────────────────────────

def _form_dialog(host, title: str, *, initial: dict[str, Any] | None = None,
                 is_edit: bool = False,
                 pupil_choices: list[tuple[str, str]] | None = None
                 ) -> dict[str, Any] | None:
    dlg = tk.Toplevel(host.root)
    dlg.title(title)
    dlg.transient(host.root)
    dlg.geometry("480x540")
    try:
        dlg.wait_visibility(); dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped", exc_info=True)
    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    initial = initial or {}
    vars_: dict[str, tk.Variable] = {}
    row = 0

    # Child picker only when adding a new record.
    pid_id_by_label: dict[str, str] = {}
    if not is_edit:
        ttk.Label(frm, text="Child:").grid(row=row, column=0, sticky="nw", pady=2)
        choices = pupil_choices or []
        pid_id_by_label = {lbl: sid for sid, lbl in choices}
        pvar = tk.StringVar()
        ttk.Combobox(frm, textvariable=pvar,
                     values=[lbl for _i, lbl in choices],
                     state="readonly" if choices else "normal", width=34).grid(
            row=row, column=1, sticky="ew", pady=2)
        vars_["__pupil_label"] = pvar
        row += 1

    for key, label, kind in _FIELDS:
        if key == "status" and not is_edit:
            continue
        if kind == "check":
            v = tk.BooleanVar(value=bool(initial.get(key)))
            ttk.Checkbutton(frm, text=label, variable=v).grid(
                row=row, column=0, columnspan=2, sticky="w", pady=2)
            vars_[key] = v
            row += 1
            continue
        ttk.Label(frm, text=f"{label}:").grid(row=row, column=0, sticky="nw", pady=2)
        cur = initial.get(key)
        if kind == "category":
            v = tk.StringVar(value=str(cur or "allergy"))
            ttk.Combobox(frm, textvariable=v, values=list(CATEGORIES),
                         state="readonly", width=32).grid(
                row=row, column=1, sticky="ew", pady=2)
        elif kind == "severity":
            v = tk.StringVar(value=str(cur or ""))
            ttk.Combobox(frm, textvariable=v, values=["", *SEVERITIES],
                         state="readonly", width=32).grid(
                row=row, column=1, sticky="ew", pady=2)
        elif kind == "status":
            v = tk.StringVar(value=str(cur or "active"))
            ttk.Combobox(frm, textvariable=v, values=list(STATUSES),
                         state="readonly", width=32).grid(
                row=row, column=1, sticky="ew", pady=2)
        else:
            v = tk.StringVar(value="" if cur is None else str(cur))
            ttk.Entry(frm, textvariable=v, width=34).grid(
                row=row, column=1, sticky="ew", pady=2)
        vars_[key] = v
        row += 1
    frm.columnconfigure(1, weight=1)

    result: dict[str, Any] | None = None

    def _save() -> None:
        nonlocal result
        out: dict[str, Any] = {}
        for k, v in vars_.items():
            if k == "__pupil_label":
                out["pupil_id"] = pid_id_by_label.get((v.get() or "").strip(), "")
            elif isinstance(v, tk.BooleanVar):
                out[k] = 1 if v.get() else 0
            else:
                out[k] = (v.get() or "").strip()
        result = out
        dlg.destroy()

    btns = ttk.Frame(frm)
    btns.grid(row=row, column=0, columnspan=2, sticky="e", pady=(12, 0))
    ttk.Button(btns, text="Cancel", command=dlg.destroy).pack(side="right", padx=4)
    ttk.Button(btns, text="Save", command=_save).pack(side="right")
    dlg.wait_window()
    return result


@_safe_view
def open_add(host) -> None:
    logger.debug("GUI: allergies open_add")
    fields = _form_dialog(host, "Add Dietary Record",
                          pupil_choices=_pupil_choices())
    if not fields:
        host.status_var.set("Add dietary record cancelled")
        open_manager(host)
        return
    if not fields.get("pupil_id"):
        messagebox.showerror("Add record", "Please choose a child.",
                             parent=host.root)
        open_manager(host)
        return
    try:
        r = data.create_record(fields)
    except ValidationError as e:
        messagebox.showerror("Add record", str(e), parent=host.root)
        open_manager(host)
        return
    messagebox.showinfo(
        "Record added",
        f"{r.child_name} — {r.category}\nAllergen: {r.allergen or '-'}",
        parent=host.root)
    host.status_var.set(f"Added dietary record {r.record_id}")
    open_manager(host)


@_safe_view
def open_edit(host, record_id: str) -> None:
    logger.debug("GUI: allergies open_edit(%s)", record_id)
    r = data.get_record(record_id)
    if r is None:
        messagebox.showerror("Edit record", f"No record with id {record_id}",
                             parent=host.root)
        return
    initial = {key: getattr(r, key) for key, _l, _k in _FIELDS}
    fields = _form_dialog(host, f"Edit {r.child_name} — dietary record",
                          initial=initial, is_edit=True)
    if not fields:
        return
    try:
        data.update_record(record_id, fields)
    except ValidationError as e:
        messagebox.showerror("Edit record", str(e), parent=host.root)
        return
    host.status_var.set(f"Updated dietary record {record_id}")
    open_manager(host)


def build(parent: tk.Misc, auth=None) -> ttk.Frame:
    frame = ttk.Frame(parent, padding=16)
    ttk.Label(frame, text="Allergies & Dietary Requirements",
              font=("", 14, "bold")).pack(anchor="w", pady=(0, 6))
    ttk.Label(frame, text="Open Allergies & Dietary Requirements from the "
              "navigation menu.").pack(anchor="w")
    return frame
