"""Tk views for Attainment 8."""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable

from education_system.secondarysch_system.modules.domain.assessment.attainment_8 import (
    attainment_8 as data,
)
from education_system.secondarysch_system.modules.domain.assessment.attainment_8.attainment_8 import (
    SOURCES, SLOT_LABELS,
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
                messagebox.showerror("Attainment 8", str(e),
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
    dlg.geometry("460x620")
    dlg.update_idletasks()
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped — dialog not viewable", exc_info=True)

    initial = initial or {}
    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    pupil_var = tk.StringVar(value=str(initial.get("pupil_id") or ""))
    year_var  = tk.StringVar(value=str(initial.get("academic_year") or ""))
    src_var   = tk.StringVar(value=str(initial.get("record_source")
                                         or "Estimated"))
    setby_var = tk.StringVar(value=str(initial.get("recorded_by") or ""))

    rows: list[tuple[str, tk.Widget]] = [
        ("Pupil ID:",       ttk.Entry(frm, textvariable=pupil_var,
                                        width=14, state=(
                                            "readonly" if initial.get("pupil_id")
                                            else "normal"))),
        ("Academic year:",  ttk.Entry(frm, textvariable=year_var,
                                        width=10)),
        ("Source:",         ttk.Combobox(frm, textvariable=src_var,
                                          values=list(SOURCES),
                                          state="readonly", width=12)),
        ("Recorded by:",    ttk.Entry(frm, textvariable=setby_var,
                                        width=24)),
    ]
    for i, (label, widget) in enumerate(rows):
        ttk.Label(frm, text=label).grid(row=i, column=0, sticky="w",
                                         pady=2)
        widget.grid(row=i, column=1, sticky="ew", pady=2)
    frm.columnconfigure(1, weight=1)

    ttk.Label(frm, text="Slots (1–9 or U)",
              font=("", 10, "bold")).grid(
        row=len(rows), column=0, columnspan=2, sticky="w",
        pady=(10, 4))
    slot_vars: dict[str, tk.StringVar] = {}
    for j, label in enumerate(SLOT_LABELS):
        nice = label.replace("_grade", "").replace("_", " ").title()
        v = tk.StringVar(value=str(initial.get(label) or ""))
        slot_vars[label] = v
        ttk.Label(frm, text=f"  {nice}:").grid(
            row=len(rows) + 1 + j, column=0, sticky="w", pady=1)
        ttk.Entry(frm, textvariable=v, width=6).grid(
            row=len(rows) + 1 + j, column=1, sticky="w", pady=1)

    notes_row = len(rows) + 1 + len(SLOT_LABELS)
    ttk.Label(frm, text="Notes:").grid(row=notes_row, column=0,
                                        sticky="nw", pady=(10, 0))
    notes_w = tk.Text(frm, width=40, height=3, wrap="word")
    notes_w.insert("1.0", str(initial.get("notes") or ""))
    notes_w.grid(row=notes_row, column=1, sticky="ew",
                  pady=(10, 0))

    result: dict[str, Any] | None = None

    def _save() -> None:
        nonlocal result
        result = {
            "pupil_id":      pupil_var.get().strip(),
            "academic_year": year_var.get().strip(),
            "record_source": src_var.get().strip(),
            "recorded_by":   setby_var.get().strip(),
            "notes":         notes_w.get("1.0", "end").strip(),
        }
        for label, v in slot_vars.items():
            result[label] = v.get().strip()
        dlg.destroy()

    btns = ttk.Frame(frm)
    btns.grid(row=notes_row + 1, column=0, columnspan=2, sticky="e",
              pady=(12, 0))
    ttk.Button(btns, text="Cancel",
               command=dlg.destroy).pack(side="right", padx=4)
    ttk.Button(btns, text="Save", command=_save).pack(side="right")
    dlg.wait_window()
    return result


@_safe_view
def open_attainment_8(host) -> None:
    logger.debug("GUI: open_attainment_8")
    host._clear_content()
    root = host.content_frame
    ttk.Label(root, text="Attainment 8",
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
        side="left", padx=(0, 6))
    ttk.Label(bar, text="Source:").pack(side="left", padx=(0, 4))
    src_var = tk.StringVar(value="")
    ttk.Combobox(bar, textvariable=src_var,
                 values=["", *SOURCES], state="readonly",
                 width=10).pack(side="left", padx=(0, 8))
    ttk.Button(bar, text="Apply",
               command=lambda: _refresh()).pack(side="left", padx=2)
    ttk.Button(bar, text="New / update",
               command=lambda: _new(host, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Edit",
               command=lambda: _edit(host, tree, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Summary",
               command=lambda: _summary(host,
                                          year_var.get().strip() or None,
                                          ay_var.get().strip() or None,
                                          src_var.get().strip() or None)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Delete",
               command=lambda: _delete(host, tree, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: _refresh()).pack(side="left", padx=2)

    cols = ("id", "pupil", "year", "ay", "src", "eng", "mth", "eb",
            "open", "total", "a8")
    tree = ttk.Treeview(root, columns=cols, show="headings", height=18)
    for c, label, w in [
        ("id", "ID", 50), ("pupil", "Pupil", 90),
        ("year", "Yr", 50), ("ay", "Academic yr", 90),
        ("src", "Source", 90),
        ("eng", "Eng", 50), ("mth", "Mth", 50),
        ("eb", "EBacc", 100), ("open", "Open", 100),
        ("total", "Total", 70), ("a8", "A8", 70),
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
                record_source=src_var.get().strip() or None,
            )
        except ValidationError as e:
            messagebox.showerror("Attainment 8", str(e),
                                 parent=host.root)
            return
        except Exception as e:
            logger.exception("attainment_8 refresh failed")
            messagebox.showerror("Attainment 8",
                                 f"Could not load:\n\n{e}",
                                 parent=host.root)
            return
        for r in rows:
            eb = "/".join((r.ebacc1_grade or '-', r.ebacc2_grade or '-',
                            r.ebacc3_grade or '-'))
            op = "/".join((r.open1_grade or '-', r.open2_grade or '-',
                            r.open3_grade or '-'))
            tree.insert("", "end", iid=str(r.record_id), values=(
                r.record_id, r.pupil_id, r.pupil_year or "-",
                r.academic_year, r.record_source,
                r.english_grade or "-", r.maths_grade or "-",
                eb, op,
                r.total_points if r.total_points is not None else "-",
                r.attainment_8 if r.attainment_8 is not None else "-",
            ))
        summary_var.set(f"{len(rows)} record(s) listed")
        host.status_var.set(f"Attainment 8: {len(rows)} record(s)")

    tree.bind("<Double-1>", lambda _e: _edit(host, tree,
                                              on_done=_refresh))
    year_var.trace_add("write", lambda *_: _refresh())
    src_var.trace_add("write", lambda *_: _refresh())
    _refresh()


def _selected_id(tree: ttk.Treeview, host) -> int | None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Attainment 8",
                            "Select a record first.",
                            parent=host.root)
        return None
    try:
        return int(sel)
    except ValueError:
        return None


@_safe_view
def _new(host, *, on_done=None) -> None:
    fields = _record_dialog(host, "New / update A8 record")
    if not fields:
        return
    r = data.upsert(fields)
    if r.attainment_8 is not None:
        msg = (f"Saved {r.pupil_id} ({r.academic_year}, "
               f"{r.record_source})\nA8: {r.attainment_8}    "
               f"Total: {r.total_points}")
    else:
        msg = (f"Saved {r.pupil_id} ({r.slots_filled}/8 slots filled — "
               f"A8 not computed)")
    messagebox.showinfo("Attainment 8", msg, parent=host.root)
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
        "record_source": existing.record_source,
        "recorded_by": existing.recorded_by,
        "notes": existing.notes,
    }
    for label in SLOT_LABELS:
        initial[label] = getattr(existing, label)
    fields = _record_dialog(host, f"Edit A8 #{rid}", initial=initial)
    if not fields:
        return
    data.upsert(fields)
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
            f"Delete A8 record for {existing.pupil_id} "
            f"({existing.academic_year} {existing.record_source})?",
            parent=host.root):
        return
    data.delete(rid)
    if on_done:
        on_done()


@_safe_view
def _summary(host, year_group: str | None,
             academic_year: str | None,
             record_source: str | None) -> None:
    s = data.cohort_summary(year_group=year_group,
                              academic_year=academic_year,
                              record_source=record_source)
    lines = [
        f"Records: {s['count']}",
        f"Complete: {s['complete']}    Incomplete: {s['incomplete']}",
        "",
        f"Avg A8: {s['avg_a8'] if s['avg_a8'] is not None else '-'}",
        f"Min A8: {s['min_a8'] if s['min_a8'] is not None else '-'}",
        f"Max A8: {s['max_a8'] if s['max_a8'] is not None else '-'}",
    ]
    if s["bands"]:
        lines.append("")
        lines.append("Bands:")
        for band in ("8.0+", "7.0–7.9", "6.0–6.9", "5.0–5.9",
                     "4.0–4.9", "3.0–3.9", "<3.0"):
            n = s["bands"].get(band, 0)
            if n:
                lines.append(f"  {band:<8} {n}")
    messagebox.showinfo("Attainment 8 — summary",
                        "\n".join(lines), parent=host.root)
