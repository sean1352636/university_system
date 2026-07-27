"""Tkinter views for the Accident / Incident Report (Nursery System).

Renders into the shared content pane of ``gui_main.NurseryMainGUI`` (the
``host``): a summary line, type / status filters and a "RIDDOR only" toggle, a
Treeview of the accident / incident / near-miss register and an add/edit form
dialog — the GUI counterpart of ``accident_report_cli.py``. Open / RIDDOR-
reportable rows are flagged red.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Any

from education_system.systems.nursery.domain.pastoral.health.accident_report import (
    accident_report as data,
)
from education_system.systems.nursery.domain.pastoral.health.accident_report.accident_report import (
    RECORD_TYPES,
    SEVERITIES,
    STATUSES,
    ValidationError,
)

logger = logging.getLogger(__name__)


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


def open_accident_report_window(host) -> None:
    """Open the Accident / Incident Report in the GUI host's content pane."""
    try:
        host._clear_content()
        root = host.content_frame
        ttk.Label(root, text="Accident / Incident Report",
                  font=("", 16, "bold")).pack(anchor="w", pady=(0, 8))

        summary = ttk.Label(root, foreground="#555")
        summary.pack(anchor="w", pady=(0, 6))

        type_var = tk.StringVar(value="(all)")
        status_var = tk.StringVar(value="(all)")
        riddor_var = tk.BooleanVar(value=False)

        bar = ttk.Frame(root)
        bar.pack(fill="x", pady=(0, 8))

        cols = ("date", "child", "type", "severity", "injury",
                "parent", "riddor", "status")
        tree = ttk.Treeview(root, columns=cols, show="headings", height=16)

        def refresh() -> None:
            _refresh(tree, summary, type_var.get(), status_var.get(),
                     riddor_var.get())

        ttk.Button(bar, text="Add",
                   command=lambda: _open_add(host)).pack(side="left", padx=2)
        ttk.Button(bar, text="Edit",
                   command=lambda: _edit_selected(host, tree)).pack(side="left", padx=2)
        ttk.Button(bar, text="Delete",
                   command=lambda: _delete_selected(host, tree)).pack(side="left", padx=2)
        ttk.Button(bar, text="Export CSV",
                   command=lambda: _export(host)).pack(side="left", padx=2)
        ttk.Button(bar, text="Refresh",
                   command=refresh).pack(side="left", padx=2)

        ttk.Label(bar, text="Type:").pack(side="left", padx=(12, 2))
        ttk.Combobox(bar, textvariable=type_var, width=11, state="readonly",
                     values=["(all)", *RECORD_TYPES]).pack(side="left")
        ttk.Label(bar, text="Status:").pack(side="left", padx=(8, 2))
        ttk.Combobox(bar, textvariable=status_var, width=9, state="readonly",
                     values=["(all)", *STATUSES]).pack(side="left")
        ttk.Checkbutton(bar, text="RIDDOR only", variable=riddor_var,
                        command=refresh).pack(side="left", padx=(8, 2))
        type_var.trace_add("write", lambda *_a: refresh())
        status_var.trace_add("write", lambda *_a: refresh())

        for c, label, w in [
            ("date", "Date", 90), ("child", "Child", 160), ("type", "Type", 90),
            ("severity", "Severity", 80), ("injury", "Injury", 150),
            ("parent", "Parent informed", 110), ("riddor", "RIDDOR", 70),
            ("status", "Status", 70),
        ]:
            tree.heading(c, text=label)
            tree.column(c, width=w, anchor="w")
        tree.tag_configure("alert", foreground="#c0392b")
        tree.pack(fill="both", expand=True)
        tree.bind("<Double-1>", lambda _e: _edit_selected(host, tree))

        refresh()
        host.status_var.set("Accident / Incident Report loaded")
    except Exception:
        logger.exception("open_accident_report_window failed")
        try:
            messagebox.showerror(
                "Accident / Incident Report",
                "Could not open the report — see logs for details.",
                parent=getattr(host, "root", None))
        except Exception:
            logger.debug("Could not show error dialog", exc_info=True)


def _refresh(tree: ttk.Treeview, summary: ttk.Label, type_filter: str,
             status_filter: str, riddor_only: bool) -> None:
    for i in tree.get_children():
        tree.delete(i)
    rt = None if type_filter in ("", "(all)") else type_filter
    st = None if status_filter in ("", "(all)") else status_filter
    try:
        rows = data.list_records(record_type=rt, status=st, riddor_only=riddor_only)
        s = data.summary()
    except Exception:
        logger.exception("Could not refresh accident report")
        try:
            messagebox.showerror("Accident / Incident Report",
                                 "Could not load — see logs.")
        except Exception:
            logger.debug("Could not show refresh-error dialog", exc_info=True)
        return
    for r in rows:
        tag = ("alert",) if (r.riddor_reportable or r.status == "open") else ()
        tree.insert("", "end", iid=r.record_id, tags=tag, values=(
            r.occurred_date or "-", r.child_name or "-", r.record_type,
            r.severity, (r.injury or "-")[:30],
            "Yes" if r.parent_informed else "No",
            "Yes" if r.riddor_reportable else "No", r.status))
    by_type = "  ".join(f"{k}={v}" for k, v in sorted(s["by_type"].items()))
    summary.config(
        text=f"Total: {s['total']}   Open: {s['open_count']}   "
             f"RIDDOR: {s['riddor_count']}   "
             f"Parent informed: {s['parent_informed_rate']}%   "
             f"Last 30 days: {s['last_30_days']}"
             + (f"   ·   {by_type}" if by_type else ""),
        foreground="#a00" if (s["open_count"] or s["riddor_count"]) else "#555")


def _selected(host, tree: ttk.Treeview, verb: str) -> str | None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Accident / Incident Report",
                            f"Select a record to {verb}.", parent=host.root)
        return None
    return sel


def _edit_selected(host, tree: ttk.Treeview) -> None:
    sel = _selected(host, tree, "edit")
    if sel:
        _open_edit(host, sel)


def _delete_selected(host, tree: ttk.Treeview) -> None:
    sel = _selected(host, tree, "delete")
    if not sel:
        return
    r = data.get_record(sel)
    if r is None:
        return
    if not messagebox.askyesno(
            "Delete record",
            f"Delete record {sel} for {r.child_name}?", parent=host.root):
        return
    try:
        data.delete_record(sel)
    except Exception as e:  # noqa: BLE001
        logger.exception("Failed to delete accident %s", sel)
        messagebox.showerror("Delete record", f"Could not delete:\n\n{e}",
                             parent=host.root)
        return
    open_accident_report_window(host)
    host.status_var.set(f"Deleted record {sel}")


# ── Form dialog ──────────────────────────────────────────────────────────────

# (field key, label, kind). Kinds: entry, type, severity, status, check.
_FIELDS: list[tuple[str, str, str]] = [
    ("record_type",       "Type",                       "type"),
    ("occurred_date",     "Date (YYYY-MM-DD)",          "entry"),
    ("occurred_time",     "Time (HH:MM)",               "entry"),
    ("location",          "Location",                   "entry"),
    ("description",       "Description",                "entry"),
    ("injury",            "Injury",                     "entry"),
    ("body_part",         "Body part",                  "entry"),
    ("treatment",         "Treatment given",            "entry"),
    ("severity",          "Severity",                   "severity"),
    ("parent_informed",   "Parent informed",            "check"),
    ("parent_signed",     "Parent signed",              "check"),
    ("riddor_reportable", "RIDDOR-reportable",          "check"),
    ("action_taken",      "Action taken",               "entry"),
    ("recorded_by",       "Recorded by",                "entry"),
    ("notes",             "Notes",                      "entry"),
    ("status",            "Status",                     "status"),
]


def _form_dialog(host, title: str, *, initial: dict[str, Any] | None = None,
                 is_edit: bool = False) -> dict[str, Any] | None:
    dlg = tk.Toplevel(host.root)
    dlg.title(title)
    dlg.transient(host.root)
    dlg.geometry("480x640")
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped", exc_info=True)
    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    initial = initial or {}
    vars_: dict[str, tk.Variable] = {}
    row = 0

    # Child picker only when adding a new record.
    pid_by_label: dict[str, str] = {}
    if not is_edit:
        ttk.Label(frm, text="Child:").grid(row=row, column=0, sticky="nw", pady=2)
        choices = _pupil_choices()
        pid_by_label = {lbl: sid for sid, lbl in choices}
        pvar = tk.StringVar()
        ttk.Combobox(frm, textvariable=pvar, values=[lbl for _i, lbl in choices],
                     state="readonly" if choices else "normal", width=36).grid(
            row=row, column=1, sticky="ew", pady=2)
        vars_["__pupil_label"] = pvar
        row += 1

    # First-aider picker (optional).
    staff = _staff_choices()
    aid_by_label = {lbl: sid for sid, lbl in staff}
    aid_label_by_id = {sid: lbl for sid, lbl in staff}
    ttk.Label(frm, text="First-aider:").grid(row=row, column=0, sticky="nw", pady=2)
    avar = tk.StringVar(value=aid_label_by_id.get(initial.get("first_aider"), ""))
    ttk.Combobox(frm, textvariable=avar, values=["", *[lbl for _i, lbl in staff]],
                 state="readonly" if staff else "normal", width=36).grid(
        row=row, column=1, sticky="ew", pady=2)
    vars_["__aider_label"] = avar
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
        if kind == "type":
            v = tk.StringVar(value=str(cur or "accident"))
            ttk.Combobox(frm, textvariable=v, values=list(RECORD_TYPES),
                         state="readonly", width=34).grid(
                row=row, column=1, sticky="ew", pady=2)
        elif kind == "severity":
            v = tk.StringVar(value=str(cur or "minor"))
            ttk.Combobox(frm, textvariable=v, values=list(SEVERITIES),
                         state="readonly", width=34).grid(
                row=row, column=1, sticky="ew", pady=2)
        elif kind == "status":
            v = tk.StringVar(value=str(cur or "open"))
            ttk.Combobox(frm, textvariable=v, values=list(STATUSES),
                         state="readonly", width=34).grid(
                row=row, column=1, sticky="ew", pady=2)
        else:
            v = tk.StringVar(value="" if cur is None else str(cur))
            ttk.Entry(frm, textvariable=v, width=36).grid(
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
                out["pupil_id"] = pid_by_label.get((v.get() or "").strip(), "")
            elif k == "__aider_label":
                out["first_aider"] = aid_by_label.get((v.get() or "").strip(), "")
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


def _open_add(host) -> None:
    try:
        fields = _form_dialog(host, "Add Accident / Incident Record")
    except Exception:
        logger.exception("accident add dialog failed")
        messagebox.showerror("Add record", "Could not open form — see logs.",
                             parent=getattr(host, "root", None))
        return
    if not fields:
        host.status_var.set("Add accident record cancelled")
        return
    if not fields.get("pupil_id"):
        messagebox.showerror("Add record", "Please choose a child.",
                             parent=host.root)
        return
    try:
        r = data.create_record(fields)
    except ValidationError as e:
        messagebox.showerror("Add record", str(e), parent=host.root)
        return
    except Exception as e:  # noqa: BLE001
        logger.exception("create_record failed")
        messagebox.showerror("Add record", f"Could not save:\n\n{e}",
                             parent=host.root)
        return
    host.status_var.set(f"Added accident record {r.record_id}")
    open_accident_report_window(host)


def _open_edit(host, record_id: str) -> None:
    r = data.get_record(record_id)
    if r is None:
        messagebox.showerror("Edit record", f"No record with id {record_id}",
                             parent=host.root)
        return
    initial = {key: getattr(r, key) for key, _l, _k in _FIELDS}
    initial["first_aider"] = r.first_aider
    try:
        fields = _form_dialog(host, f"Edit {r.child_name} — {r.record_type}",
                              initial=initial, is_edit=True)
    except Exception:
        logger.exception("accident edit dialog failed")
        messagebox.showerror("Edit record", "Could not open form — see logs.",
                             parent=getattr(host, "root", None))
        return
    if not fields:
        return
    try:
        data.update_record(record_id, fields)
    except ValidationError as e:
        messagebox.showerror("Edit record", str(e), parent=host.root)
        return
    except Exception as e:  # noqa: BLE001
        logger.exception("update_record failed")
        messagebox.showerror("Edit record", f"Could not save:\n\n{e}",
                             parent=host.root)
        return
    host.status_var.set(f"Updated accident record {record_id}")
    open_accident_report_window(host)


def _export(host) -> None:
    path = filedialog.asksaveasfilename(
        parent=getattr(host, "root", None), title="Export Accident / Incident Report",
        defaultextension=".csv", filetypes=[("CSV files", "*.csv")],
        initialfile="accident_report.csv")
    if not path:
        return
    try:
        res = data.export_csv(path)
        messagebox.showinfo(
            "Accident / Incident Report",
            f"Wrote {res['row_count']} row(s) to:\n{res['path']}",
            parent=getattr(host, "root", None))
        host.status_var.set(f"Exported accident report → {res['path']}")
    except OSError as e:
        messagebox.showerror("Accident / Incident Report", str(e),
                             parent=getattr(host, "root", None))


def build(parent: tk.Misc, auth=None) -> ttk.Frame:
    frame = ttk.Frame(parent, padding=16)
    ttk.Label(frame, text="Accident / Incident Report",
              font=("", 14, "bold")).pack(anchor="w", pady=(0, 6))
    ttk.Label(frame, text="Open the Accident / Incident Report from the "
              "navigation menu.").pack(anchor="w")
    return frame
