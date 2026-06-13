"""Tk views for bulk operations in the Secondary School System."""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Callable

from education_system.secondarysch_system.modules.domain.pupils.bulk_operations import (
    bulk_operations as data,
)
from education_system.secondarysch_system.modules.domain.pupils.bulk_operations.bulk_operations import (
    BulkResult, BULK_UPDATABLE, IMPORT_COLUMNS, REQUIRED_COLUMNS,
)
from education_system.secondarysch_system.modules.domain.pupils.pupils.pupils import (
    ValidationError, YEAR_GROUPS,
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
                messagebox.showerror("Bulk Operations", str(e),
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


def _format_result(result: BulkResult) -> str:
    lines = [
        f"Processed: {result.processed}",
        f"Succeeded: {result.succeeded}",
        f"Failed:    {result.failed}",
    ]
    if result.created_ids:
        head = ", ".join(result.created_ids[:5])
        more = ("" if len(result.created_ids) <= 5
                else f", … (+{len(result.created_ids) - 5} more)")
        lines.append(f"Created:   {head}{more}")
    return "\n".join(lines)


def _show_result_dialog(parent, title: str, result: BulkResult) -> None:
    dlg = tk.Toplevel(parent)
    dlg.title(title)
    dlg.transient(parent)
    dlg.geometry("560x420")
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped", exc_info=True)

    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)
    summary = _format_result(result)
    ttk.Label(frm, text=summary, justify="left",
              font=("Segoe UI", 10)).pack(anchor="w")

    if result.errors:
        ttk.Label(frm, text=f"\n{len(result.errors)} error(s):",
                  font=("Segoe UI", 10, "bold")).pack(anchor="w")
        text = tk.Text(frm, height=12, wrap="word")
        text.pack(fill="both", expand=True, pady=(4, 0))
        for err in result.errors:
            label = err.raw.get("pupil_id") or f"row {err.row_number}"
            text.insert("end", f"- {label}: {err.message}\n")
        text.config(state="disabled")
    else:
        ttk.Label(frm, text="\nNo errors.",
                  foreground="#27ae60").pack(anchor="w")

    ttk.Button(frm, text="Close",
               command=dlg.destroy).pack(anchor="e", pady=(10, 0))


@_safe_view
def open_bulk_operations(host) -> None:
    logger.debug("GUI: open_bulk_operations")
    win = tk.Toplevel(host.root)
    win.title("Bulk Operations")
    win.transient(host.root)
    win.geometry("520x360")

    frm = ttk.Frame(win, padding=14)
    frm.pack(fill="both", expand=True)

    ttk.Label(frm, text="Bulk Operations",
              font=("Segoe UI", 13, "bold")).pack(anchor="w")
    ttk.Label(frm,
              text="Import, export, or batch-edit pupil records.",
              foreground="#555").pack(anchor="w", pady=(0, 12))

    def _import() -> None:
        path = filedialog.askopenfilename(
            parent=win, title="Choose CSV to import",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            result = data.import_pupils_csv(Path(path))
        except ValidationError as e:
            messagebox.showerror("Import", str(e), parent=win)
            return
        except Exception:
            logger.exception("import_pupils_csv failed")
            messagebox.showerror("Error",
                                 "CSV import failed — see logs.",
                                 parent=win)
            return
        _show_result_dialog(win, "Import results", result)

    def _export() -> None:
        path = filedialog.asksaveasfilename(
            parent=win, title="Export pupils to CSV",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            count = data.export_pupils_csv(Path(path))
        except ValidationError as e:
            messagebox.showerror("Export", str(e), parent=win)
            return
        except Exception:
            logger.exception("export_pupils_csv failed")
            messagebox.showerror("Error",
                                 "CSV export failed — see logs.",
                                 parent=win)
            return
        messagebox.showinfo("Export",
                            f"Wrote {count} pupil(s) to:\n{path}",
                            parent=win)

    def _update() -> None:
        _open_bulk_update_dialog(win)

    def _delete() -> None:
        _open_bulk_delete_dialog(win)

    def _help() -> None:
        msg = (
            "CSV import format\n\n"
            "- UTF-8 encoded with a header row\n"
            f"- Required columns: {', '.join(REQUIRED_COLUMNS)}\n"
            f"- Optional columns: "
            f"{', '.join(c for c in IMPORT_COLUMNS if c not in REQUIRED_COLUMNS)}\n"
            f"- Year group values: {', '.join(YEAR_GROUPS)}\n"
            "- Date of birth: YYYY-MM-DD\n"
            "- send_status: yes / no / blank\n"
            "- pupil_id and email are generated automatically"
        )
        messagebox.showinfo("CSV format", msg, parent=win)

    for label, cmd in [
        ("Import pupils from CSV…", _import),
        ("Export pupils to CSV…", _export),
        ("Bulk update field…", _update),
        ("Bulk delete pupils…", _delete),
        ("CSV format help", _help),
    ]:
        ttk.Button(frm, text=label, command=cmd, width=30).pack(
            anchor="w", pady=3)

    ttk.Button(frm, text="Close",
               command=win.destroy).pack(anchor="e", pady=(14, 0))


def _open_bulk_update_dialog(parent) -> None:
    dlg = tk.Toplevel(parent)
    dlg.title("Bulk update")
    dlg.transient(parent)
    dlg.geometry("440x320")
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped", exc_info=True)

    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    ttk.Label(frm, text="Field:").grid(row=0, column=0, sticky="w", pady=4)
    field_var = tk.StringVar(value=BULK_UPDATABLE[0])
    field_box = ttk.Combobox(frm, textvariable=field_var,
                             values=list(BULK_UPDATABLE),
                             state="readonly", width=20)
    field_box.grid(row=0, column=1, sticky="w", pady=4)

    ttk.Label(frm, text="New value:").grid(row=1, column=0, sticky="w", pady=4)
    value_var = tk.StringVar()
    value_entry = ttk.Entry(frm, textvariable=value_var, width=22)
    value_entry.grid(row=1, column=1, sticky="w", pady=4)

    hint_var = tk.StringVar()
    ttk.Label(frm, textvariable=hint_var, foreground="#666").grid(
        row=2, column=0, columnspan=2, sticky="w", pady=(0, 6))

    def _update_hint(*_a) -> None:
        f = field_var.get()
        if f == "year_group":
            hint_var.set(f"Allowed: {', '.join(YEAR_GROUPS)}")
        elif f == "send_status":
            hint_var.set("Allowed: yes / no / blank to clear")
        else:
            hint_var.set("Leave blank to clear")
    field_var.trace_add("write", _update_hint)
    _update_hint()

    ttk.Label(frm, text="Pupil IDs (one per line or comma-separated):").grid(
        row=3, column=0, columnspan=2, sticky="w", pady=(8, 2))
    ids_text = tk.Text(frm, height=8, width=42)
    ids_text.grid(row=4, column=0, columnspan=2, sticky="nsew")
    frm.rowconfigure(4, weight=1)
    frm.columnconfigure(1, weight=1)

    def _parse_ids() -> list[str]:
        raw = ids_text.get("1.0", "end").strip()
        if not raw:
            return []
        parts: list[str] = []
        for chunk in raw.replace(",", "\n").splitlines():
            chunk = chunk.strip()
            if chunk:
                parts.append(chunk)
        return parts

    def _apply() -> None:
        ids = _parse_ids()
        if not ids:
            messagebox.showinfo("Bulk update",
                                "Enter at least one pupil ID.",
                                parent=dlg)
            return
        if not messagebox.askyesno(
                "Bulk update",
                f"Apply {field_var.get()} = {value_var.get()!r} "
                f"to {len(ids)} pupil(s)?",
                parent=dlg):
            return
        try:
            result = data.bulk_update(ids, field_var.get(), value_var.get())
        except ValidationError as e:
            messagebox.showerror("Bulk update", str(e), parent=dlg)
            return
        except Exception:
            logger.exception("bulk_update failed")
            messagebox.showerror("Error",
                                 "Bulk update failed — see logs.",
                                 parent=dlg)
            return
        dlg.destroy()
        _show_result_dialog(parent, "Bulk update results", result)

    btns = ttk.Frame(frm)
    btns.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(10, 0))
    ttk.Button(btns, text="Apply", command=_apply).pack(side="right")
    ttk.Button(btns, text="Cancel",
               command=dlg.destroy).pack(side="right", padx=(0, 8))


def _open_bulk_delete_dialog(parent) -> None:
    dlg = tk.Toplevel(parent)
    dlg.title("Bulk delete")
    dlg.transient(parent)
    dlg.geometry("420x320")
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped", exc_info=True)

    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    ttk.Label(
        frm,
        text="Pupil IDs to delete (one per line or comma-separated):",
    ).pack(anchor="w")
    ids_text = tk.Text(frm, height=10)
    ids_text.pack(fill="both", expand=True, pady=(4, 6))

    confirm_var = tk.StringVar()
    ttk.Label(frm, text="Type DELETE to confirm:").pack(anchor="w")
    ttk.Entry(frm, textvariable=confirm_var, width=20).pack(anchor="w", pady=(2, 6))

    def _parse_ids() -> list[str]:
        raw = ids_text.get("1.0", "end").strip()
        if not raw:
            return []
        parts: list[str] = []
        for chunk in raw.replace(",", "\n").splitlines():
            chunk = chunk.strip()
            if chunk:
                parts.append(chunk)
        return parts

    def _apply() -> None:
        ids = _parse_ids()
        if not ids:
            messagebox.showinfo("Bulk delete",
                                "Enter at least one pupil ID.",
                                parent=dlg)
            return
        if confirm_var.get() != "DELETE":
            messagebox.showerror("Bulk delete",
                                 "Type DELETE exactly to confirm.",
                                 parent=dlg)
            return
        try:
            result = data.bulk_delete(ids)
        except Exception:
            logger.exception("bulk_delete failed")
            messagebox.showerror("Error",
                                 "Bulk delete failed — see logs.",
                                 parent=dlg)
            return
        dlg.destroy()
        _show_result_dialog(parent, "Bulk delete results", result)

    btns = ttk.Frame(frm)
    btns.pack(fill="x", pady=(8, 0))
    ttk.Button(btns, text="Delete", command=_apply).pack(side="right")
    ttk.Button(btns, text="Cancel",
               command=dlg.destroy).pack(side="right", padx=(0, 8))
