"""Tk views for Progress 8."""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable

from education_system.systems.secondary.domain.assessment.progress_8 import (
    progress_8 as data,
)
from education_system.systems.secondary.domain.learners.pupils.pupils import (
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
                messagebox.showerror("Progress 8", str(e),
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


def _record_dialog(host, title: str,
                    initial: dict[str, Any] | None = None
                    ) -> dict[str, Any] | None:
    dlg = tk.Toplevel(host.root)
    dlg.title(title)
    dlg.transient(host.root)
    dlg.geometry("440x420")
    dlg.update_idletasks()
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped — dialog not viewable", exc_info=True)

    initial = initial or {}
    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    pupil_var    = tk.StringVar(value=str(initial.get("pupil_id") or ""))
    ay_var       = tk.StringVar(value=str(initial.get("academic_year")
                                            or ""))
    ks2_var      = tk.StringVar(value=str(initial.get("ks2_prior") or ""))
    expected_var = tk.StringVar(value=str(initial.get("expected_a8") or ""))
    a8_var       = tk.StringVar(value=str(initial.get("attainment_8")
                                            or ""))
    rec_var      = tk.StringVar(value=str(initial.get("recorded_by") or ""))

    rows: list[tuple[str, tk.Widget]] = [
        ("Pupil ID:",       ttk.Entry(frm, textvariable=pupil_var,
                                        width=14,
                                        state=("readonly"
                                                if initial.get("pupil_id")
                                                else "normal"))),
        ("Academic year:",  ttk.Entry(frm, textvariable=ay_var,
                                        width=10)),
        ("KS2 prior (0–6):", ttk.Entry(frm, textvariable=ks2_var,
                                         width=8)),
        ("Expected A8\n(blank = est. from KS2):",
                            ttk.Entry(frm, textvariable=expected_var,
                                       width=8)),
        ("Attainment 8\n(blank = look up):",
                            ttk.Entry(frm, textvariable=a8_var, width=8)),
        ("Recorded by:",    ttk.Entry(frm, textvariable=rec_var,
                                        width=24)),
    ]
    for i, (label, widget) in enumerate(rows):
        ttk.Label(frm, text=label).grid(row=i, column=0, sticky="nw",
                                         pady=2)
        widget.grid(row=i, column=1, sticky="ew", pady=2)
    frm.columnconfigure(1, weight=1)

    ttk.Label(frm, text="Notes:").grid(row=len(rows), column=0,
                                        sticky="nw", pady=2)
    notes_w = tk.Text(frm, width=40, height=4, wrap="word")
    notes_w.insert("1.0", str(initial.get("notes") or ""))
    notes_w.grid(row=len(rows), column=1, sticky="ew", pady=2)

    result: dict[str, Any] | None = None

    def _save() -> None:
        nonlocal result
        result = {
            "pupil_id":      pupil_var.get().strip(),
            "academic_year": ay_var.get().strip(),
            "ks2_prior":     ks2_var.get().strip(),
            "expected_a8":   expected_var.get().strip(),
            "attainment_8":  a8_var.get().strip(),
            "recorded_by":   rec_var.get().strip(),
            "notes":         notes_w.get("1.0", "end").strip(),
        }
        dlg.destroy()

    btns = ttk.Frame(frm)
    btns.grid(row=len(rows) + 1, column=0, columnspan=2, sticky="e",
              pady=(12, 0))
    ttk.Button(btns, text="Cancel",
               command=dlg.destroy).pack(side="right", padx=4)
    ttk.Button(btns, text="Save", command=_save).pack(side="right")
    dlg.wait_window()
    return result


@_safe_view
def open_progress_8(host) -> None:
    logger.debug("GUI: open_progress_8")
    host._clear_content()
    root = host.content_frame
    ttk.Label(root, text="Progress 8",
              font=("", 16, "bold")).pack(anchor="w", pady=(0, 8))

    summary_var = tk.StringVar()
    ttk.Label(root, textvariable=summary_var, foreground="#666").pack(
        anchor="w", pady=(0, 8))

    bar = ttk.Frame(root)
    bar.pack(fill="x", pady=(0, 6))
    ttk.Label(bar, text="Year:").pack(side="left", padx=(0, 4))
    year_var = tk.StringVar(value="")
    ttk.Combobox(bar, textvariable=year_var,
                 values=["", *YEAR_GROUPS], state="readonly",
                 width=5).pack(side="left", padx=(0, 6))
    ttk.Label(bar, text="Academic yr:").pack(side="left", padx=(0, 4))
    ay_var = tk.StringVar(value="")
    ttk.Entry(bar, textvariable=ay_var, width=10).pack(
        side="left", padx=(0, 8))
    ttk.Button(bar, text="Apply",
               command=lambda: _refresh()).pack(side="left", padx=2)
    ttk.Button(bar, text="New / update",
               command=lambda: _new(host, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Edit",
               command=lambda: _edit(host, tree, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh A8",
               command=lambda: _refresh_a8(host, tree, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Summary",
               command=lambda: _summary(host,
                                          year_var.get().strip() or None,
                                          ay_var.get().strip() or None)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Delete",
               command=lambda: _delete(host, tree, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: _refresh()).pack(side="left", padx=2)

    cols = ("id", "pupil", "year", "ay", "ks2", "exp", "a8", "p8",
            "src")
    tree = ttk.Treeview(root, columns=cols, show="headings", height=18)
    for c, label, w in [
        ("id", "ID", 50), ("pupil", "Pupil", 90),
        ("year", "Yr", 50), ("ay", "Academic yr", 90),
        ("ks2", "KS2", 60), ("exp", "Exp A8", 70),
        ("a8", "A8", 60), ("p8", "P8", 70),
        ("src", "A8 source", 110),
    ]:
        tree.heading(c, text=label)
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True)

    def _refresh() -> None:
        for i in tree.get_children():
            tree.delete(i)
        try:
            rows = data.list_records(
                year_group=year_var.get().strip() or None,
                academic_year=ay_var.get().strip() or None,
            )
        except ValidationError as e:
            messagebox.showerror("Progress 8", str(e), parent=host.root)
            return
        except Exception as e:
            logger.exception("progress_8 refresh failed")
            messagebox.showerror("Progress 8",
                                 f"Could not load:\n\n{e}",
                                 parent=host.root)
            return
        for r in rows:
            a8 = (f"{r.attainment_8:.2f}"
                  if r.attainment_8 is not None else "-")
            p8 = (f"{r.progress_8:+.2f}"
                  if r.progress_8 is not None else "-")
            tree.insert("", "end", iid=str(r.record_id), values=(
                r.record_id, r.pupil_id, r.pupil_year or "-",
                r.academic_year,
                f"{r.ks2_prior:.2f}", f"{r.expected_a8:.2f}",
                a8, p8, r.a8_source or "-",
            ))
        summary_var.set(f"{len(rows)} record(s) listed")
        host.status_var.set(f"Progress 8: {len(rows)} record(s)")

    tree.bind("<Double-1>", lambda _e: _edit(host, tree,
                                              on_done=_refresh))
    year_var.trace_add("write", lambda *_: _refresh())
    _refresh()


def _selected_id(tree: ttk.Treeview, host) -> int | None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Progress 8",
                            "Select a record first.",
                            parent=host.root)
        return None
    try:
        return int(sel)
    except ValueError:
        return None


@_safe_view
def _new(host, *, on_done=None) -> None:
    fields = _record_dialog(host, "New / update Progress 8")
    if not fields:
        return
    r = data.upsert(fields)
    if r.progress_8 is not None:
        msg = (f"Saved {r.pupil_id} ({r.academic_year})\n"
               f"KS2: {r.ks2_prior}    Expected: {r.expected_a8}    "
               f"A8: {r.attainment_8}    P8: {r.progress_8:+.2f}")
    else:
        msg = (f"Saved {r.pupil_id} ({r.academic_year})\n"
               f"A8 not yet available — Progress 8 not computed")
    messagebox.showinfo("Progress 8", msg, parent=host.root)
    if on_done:
        on_done()


@_safe_view
def _edit(host, tree: ttk.Treeview, *, on_done=None) -> None:
    rid = _selected_id(tree, host)
    if rid is None:
        return
    existing = data.get(rid)
    if existing is None:
        return
    initial = {
        "pupil_id": existing.pupil_id,
        "academic_year": existing.academic_year,
        "ks2_prior": existing.ks2_prior,
        "expected_a8": existing.expected_a8,
        "attainment_8": existing.attainment_8,
        "recorded_by": existing.recorded_by,
        "notes": existing.notes,
    }
    fields = _record_dialog(host, f"Edit Progress 8 #{rid}",
                              initial=initial)
    if not fields:
        return
    data.upsert(fields)
    if on_done:
        on_done()


@_safe_view
def _refresh_a8(host, tree: ttk.Treeview, *, on_done=None) -> None:
    rid = _selected_id(tree, host)
    if rid is None:
        return
    r = data.refresh_progress_8(rid)
    messagebox.showinfo(
        "Progress 8",
        f"Refreshed {r.pupil_id} ({r.academic_year})\n"
        f"A8: {r.attainment_8 if r.attainment_8 is not None else '-'}    "
        f"P8: {r.progress_8 if r.progress_8 is not None else '-'}",
        parent=host.root,
    )
    if on_done:
        on_done()


@_safe_view
def _delete(host, tree: ttk.Treeview, *, on_done=None) -> None:
    rid = _selected_id(tree, host)
    if rid is None:
        return
    existing = data.get(rid)
    if existing is None:
        return
    if not messagebox.askyesno(
            "Delete record",
            f"Delete Progress 8 for {existing.pupil_id} "
            f"({existing.academic_year})?",
            parent=host.root):
        return
    data.delete(rid)
    if on_done:
        on_done()


@_safe_view
def _summary(host, year_group: str | None,
              academic_year: str | None) -> None:
    s = data.cohort_summary(year_group=year_group,
                              academic_year=academic_year)
    lines = [
        f"Records: {s['count']}",
        f"With P8: {s['with_p8']}    Without P8: {s['without_p8']}",
        "",
        f"Avg P8: {s['avg_p8'] if s['avg_p8'] is not None else '-'}",
        f"Min P8: {s['min_p8'] if s['min_p8'] is not None else '-'}",
        f"Max P8: {s['max_p8'] if s['max_p8'] is not None else '-'}",
    ]
    if s["bands"]:
        lines.append("")
        lines.append("Bands:")
        for band in ("+1.0 or more", "+0.5 to +0.99", "0 to +0.49",
                     "-0.5 to -0.01", "-1.0 to -0.51",
                     "worse than -1.0"):
            n = s["bands"].get(band, 0)
            if n:
                lines.append(f"  {band:<18} {n}")
    messagebox.showinfo("Progress 8 — summary",
                        "\n".join(lines), parent=host.root)
