"""Tkinter views for Medication Log (Nursery System).

Renders into the shared content pane of ``gui_main.NurseryMainGUI`` (the
``host``). Lists medication records with a tree + toolbar and an add/edit form
dialog — the GUI counterpart of ``medication_log_cli.py``. Administered records
held without parental consent are flagged in red.
"""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable

from education_system.systems.nursery.domain.pastoral.health.medication_log import (
    medication_log as data,
)
from education_system.systems.nursery.domain.pastoral.health.medication_log.medication_log import (
    ROUTES,
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


def _staff_choices() -> list[tuple[str, str]]:
    try:
        return data.list_staff_choices()
    except Exception:
        logger.exception("Could not load staff choices")
        return []


@_safe_view
def open_manager(host) -> None:
    logger.debug("GUI: medication_log open_manager")
    root = _clear(host)
    _header(root, "Medication Log")

    summary = ttk.Label(root, foreground="#555")
    summary.pack(anchor="w", pady=(0, 6))

    status_filter = tk.StringVar(value="(all)")

    bar = ttk.Frame(root)
    bar.pack(fill="x", pady=(0, 8))
    ttk.Button(bar, text="Add Record",
               command=lambda: open_add(host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Edit",
               command=lambda: _edit_selected(tree, host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Delete",
               command=lambda: _delete_selected(tree, host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: _refresh(tree, summary, status_filter.get())).pack(
        side="left", padx=2)
    ttk.Label(bar, text="Status:").pack(side="left", padx=(12, 2))
    ttk.Combobox(bar, textvariable=status_filter,
                 values=["(all)", *STATUSES], state="readonly", width=14,
                 ).pack(side="left", padx=2)
    status_filter.trace_add(
        "write", lambda *_a: _refresh(tree, summary, status_filter.get()))

    cols = ("id", "date", "child", "medication", "dose", "route",
            "consent", "status")
    tree = ttk.Treeview(root, columns=cols, show="headings", height=17)
    for c, label, w in [
        ("id", "ID", 70), ("date", "Date", 90), ("child", "Child", 160),
        ("medication", "Medication", 140), ("dose", "Dose", 80),
        ("route", "Route", 80), ("consent", "Consent", 70),
        ("status", "Status", 90),
    ]:
        tree.heading(c, text=label)
        tree.column(c, width=w, anchor="w")
    tree.tag_configure("no_consent", foreground="#c0392b")
    tree.pack(fill="both", expand=True)
    tree.bind("<Double-1>", lambda _e: _edit_selected(tree, host))

    _refresh(tree, summary, status_filter.get())
    host.status_var.set("Medication log loaded")


def _refresh(tree: ttk.Treeview, summary: ttk.Label, status: str) -> None:
    for i in tree.get_children():
        tree.delete(i)
    flt = None if status in ("", "(all)") else status
    try:
        rows = data.list_records(status=flt)
        s = data.summary()
    except Exception:
        logger.exception("Could not refresh medication log")
        try:
            messagebox.showerror("Medication log", "Could not load — see logs.")
        except Exception:
            logger.debug("Could not show refresh-error dialog", exc_info=True)
        return
    for r in rows:
        flagged = r.status == "administered" and not r.parent_consent
        tree.insert("", "end", iid=r.record_id, values=(
            r.record_id, r.administered_date or "-", r.child_name or "-",
            r.medication_name, r.dose or "-", r.route or "-",
            "Yes" if r.parent_consent else "No", r.status),
            tags=("no_consent",) if flagged else ())
    summary.config(
        text=f"Records: {s['records']}   Administered: {s['administered']}   "
             f"Scheduled: {s['scheduled']}   Refused: {s['refused']}   "
             f"No consent: {s['no_consent']}")


def _selected(tree: ttk.Treeview, host, verb: str) -> str | None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Medication log", f"Select a record to {verb}.",
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
            f"Delete medication record {sel} for {r.child_name}?",
            parent=host.root):
        return
    try:
        data.delete_record(sel)
    except Exception as e:  # noqa: BLE001
        logger.exception("Failed to delete medication-log %s", sel)
        messagebox.showerror("Delete record", f"Could not delete:\n\n{e}",
                             parent=host.root)
        return
    open_manager(host)
    host.status_var.set(f"Deleted medication record {sel}")


# ── Form dialog ──────────────────────────────────────────────────────────────

def _form_dialog(host, title: str, *, initial: dict[str, Any] | None = None,
                 is_edit: bool = False,
                 pupil_choices: list[tuple[str, str]] | None = None,
                 staff_choices: list[tuple[str, str]] | None = None
                 ) -> dict[str, Any] | None:
    dlg = tk.Toplevel(host.root)
    dlg.title(title)
    dlg.transient(host.root)
    dlg.geometry("480x620")
    try:
        dlg.wait_visibility(); dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped", exc_info=True)
    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    initial = initial or {}
    vars_: dict[str, tk.Variable] = {}
    row = 0

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

    staff = staff_choices or []
    staff_id_by_label = {lbl: sid for sid, lbl in staff}
    staff_label_by_id = {sid: lbl for sid, lbl in staff}

    def _entry(key: str, label: str) -> None:
        nonlocal row
        ttk.Label(frm, text=f"{label}:").grid(
            row=row, column=0, sticky="nw", pady=2)
        cur = initial.get(key)
        v = tk.StringVar(value="" if cur is None else str(cur))
        ttk.Entry(frm, textvariable=v, width=34).grid(
            row=row, column=1, sticky="ew", pady=2)
        vars_[key] = v
        row += 1

    def _combo(key: str, label: str, options: list[str], default: str) -> None:
        nonlocal row
        ttk.Label(frm, text=f"{label}:").grid(
            row=row, column=0, sticky="nw", pady=2)
        cur = initial.get(key)
        v = tk.StringVar(value=str(cur or default))
        ttk.Combobox(frm, textvariable=v, values=options, state="readonly",
                     width=32).grid(row=row, column=1, sticky="ew", pady=2)
        vars_[key] = v
        row += 1

    def _staff_combo(key: str, label: str) -> None:
        nonlocal row
        ttk.Label(frm, text=f"{label}:").grid(
            row=row, column=0, sticky="nw", pady=2)
        cur_id = initial.get(key)
        v = tk.StringVar(value=staff_label_by_id.get(cur_id or "", ""))
        ttk.Combobox(frm, textvariable=v,
                     values=["", *[lbl for _i, lbl in staff]],
                     state="readonly" if staff else "normal", width=32).grid(
            row=row, column=1, sticky="ew", pady=2)
        vars_[f"__staff_{key}"] = v
        row += 1

    _entry("medication_name", "Medication name (required)")
    _entry("dose", "Dose")
    _combo("route", "Route", list(ROUTES), "Oral")
    _entry("reason", "Reason")
    _entry("administered_date", "Administered date (YYYY-MM-DD)")
    _entry("administered_time", "Administered time (HH:MM)")
    _staff_combo("administered_by", "Administered by")
    _staff_combo("witnessed_by", "Witnessed by")

    ttk.Label(frm, text="Parent consent:").grid(
        row=row, column=0, sticky="nw", pady=2)
    consent_var = tk.BooleanVar(value=bool(initial.get("parent_consent")))
    ttk.Checkbutton(frm, text="Written consent held",
                    variable=consent_var).grid(
        row=row, column=1, sticky="w", pady=2)
    vars_["parent_consent"] = consent_var
    row += 1

    _entry("expiry_date", "Expiry date (YYYY-MM-DD)")
    _combo("status", "Status", list(STATUSES), "administered")
    _entry("notes", "Notes")
    frm.columnconfigure(1, weight=1)

    result: dict[str, Any] | None = None

    def _save() -> None:
        nonlocal result
        out: dict[str, Any] = {}
        for k, v in vars_.items():
            if k == "__pupil_label":
                out["pupil_id"] = pid_id_by_label.get((v.get() or "").strip(), "")
            elif k.startswith("__staff_"):
                key = k[len("__staff_"):]
                out[key] = staff_id_by_label.get((v.get() or "").strip(), "")
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
    logger.debug("GUI: medication_log open_add")
    fields = _form_dialog(host, "Add Medication Record",
                          pupil_choices=_pupil_choices(),
                          staff_choices=_staff_choices())
    if not fields:
        host.status_var.set("Add medication cancelled")
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
        f"{r.child_name} — {r.medication_name}\nStatus: {r.status}",
        parent=host.root)
    host.status_var.set(f"Added medication {r.record_id}")
    open_manager(host)


@_safe_view
def open_edit(host, record_id: str) -> None:
    logger.debug("GUI: medication_log open_edit(%s)", record_id)
    r = data.get_record(record_id)
    if r is None:
        messagebox.showerror("Edit record", f"No record with id {record_id}",
                             parent=host.root)
        return
    initial = {
        "medication_name": r.medication_name, "dose": r.dose, "route": r.route,
        "reason": r.reason, "administered_date": r.administered_date,
        "administered_time": r.administered_time,
        "administered_by": r.administered_by, "witnessed_by": r.witnessed_by,
        "parent_consent": r.parent_consent, "expiry_date": r.expiry_date,
        "status": r.status, "notes": r.notes,
    }
    fields = _form_dialog(host, f"Edit {r.child_name} — medication",
                          initial=initial, is_edit=True,
                          staff_choices=_staff_choices())
    if not fields:
        return
    try:
        data.update_record(record_id, fields)
    except ValidationError as e:
        messagebox.showerror("Edit record", str(e), parent=host.root)
        return
    host.status_var.set(f"Updated medication {record_id}")
    open_manager(host)


def build(parent: tk.Misc, auth=None) -> ttk.Frame:
    frame = ttk.Frame(parent, padding=16)
    ttk.Label(frame, text="Medication Log",
              font=("", 14, "bold")).pack(anchor="w", pady=(0, 6))
    ttk.Label(frame, text="Open Medication Log from the navigation menu."
              ).pack(anchor="w")
    return frame
