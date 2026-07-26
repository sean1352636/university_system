"""Tk views for GCSE exam entries."""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable

from education_system.systems.secondary.domain.assessment.exam_entries import (
    exam_entries as data,
)
from education_system.systems.secondary.domain.assessment.exam_entries.exam_entries import (
    EXAM_BOARDS, TIERS, ENTRY_STATUSES,
)
from education_system.systems.secondary.domain.academics.subjects import (
    subjects as subjects_data,
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
                messagebox.showerror("GCSE Exam Entries", str(e),
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


def _entry_dialog(host, title: str,
                   initial: dict[str, Any] | None = None
                   ) -> dict[str, Any] | None:
    dlg = tk.Toplevel(host.root)
    dlg.title(title)
    dlg.transient(host.root)
    dlg.geometry("460x460")
    dlg.update_idletasks()
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped — dialog not viewable", exc_info=True)

    initial = initial or {}
    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    pupil_var  = tk.StringVar(value=str(initial.get("pupil_id") or ""))
    board_var  = tk.StringVar(value=str(initial.get("exam_board")
                                         or "AQA"))
    spec_var   = tk.StringVar(value=str(initial.get("spec_code") or ""))
    tier_var   = tk.StringVar(value=str(initial.get("tier") or "N/A"))
    cand_var   = tk.StringVar(value=str(initial.get("candidate_number")
                                         or ""))
    status_var = tk.StringVar(value=str(initial.get("entry_status")
                                         or "Provisional"))
    date_var   = tk.StringVar(value=str(initial.get("entry_date") or ""))
    fee_var    = tk.StringVar(value=str(initial.get("fee") or ""))

    try:
        subjects = subjects_data.list_all(active_only=True)
    except Exception:
        subjects = []
    subject_labels = [f"#{s.subject_id} {s.code} — {s.name}"
                      for s in subjects]
    subject_var = tk.StringVar(value="")
    initial_sid = initial.get("subject_id")
    if initial_sid is not None:
        for s in subjects:
            if s.subject_id == int(initial_sid):
                subject_var.set(f"#{s.subject_id} {s.code} — {s.name}")
                break

    rows: list[tuple[str, tk.Widget]] = [
        ("Pupil ID:",   ttk.Entry(frm, textvariable=pupil_var, width=14,
                                    state=("readonly"
                                            if initial.get("pupil_id")
                                            else "normal"))),
        ("Subject:",    ttk.Combobox(frm, textvariable=subject_var,
                                      values=subject_labels,
                                      state="readonly", width=42)),
        ("Board:",      ttk.Combobox(frm, textvariable=board_var,
                                      values=list(EXAM_BOARDS),
                                      state="readonly", width=12)),
        ("Spec code:",  ttk.Entry(frm, textvariable=spec_var, width=14)),
        ("Tier:",       ttk.Combobox(frm, textvariable=tier_var,
                                      values=list(TIERS),
                                      state="readonly", width=12)),
        ("Candidate #:", ttk.Entry(frm, textvariable=cand_var, width=14)),
        ("Status:",     ttk.Combobox(frm, textvariable=status_var,
                                      values=list(ENTRY_STATUSES),
                                      state="readonly", width=14)),
        ("Entry date:", ttk.Entry(frm, textvariable=date_var, width=14)),
        ("Fee £:",      ttk.Entry(frm, textvariable=fee_var, width=10)),
    ]
    for i, (label, widget) in enumerate(rows):
        ttk.Label(frm, text=label).grid(row=i, column=0, sticky="w",
                                         pady=2)
        widget.grid(row=i, column=1, sticky="ew", pady=2)
    frm.columnconfigure(1, weight=1)

    ttk.Label(frm, text="Notes:").grid(row=len(rows), column=0,
                                        sticky="nw", pady=2)
    notes_w = tk.Text(frm, width=40, height=3, wrap="word")
    notes_w.insert("1.0", str(initial.get("notes") or ""))
    notes_w.grid(row=len(rows), column=1, sticky="ew", pady=2)

    result: dict[str, Any] | None = None

    def _parse_subject(label: str) -> str:
        label = (label or "").strip()
        if not label.startswith("#"):
            return ""
        return label.split()[0][1:]

    def _save() -> None:
        nonlocal result
        result = {
            "pupil_id":         pupil_var.get().strip(),
            "subject_id":       _parse_subject(subject_var.get()),
            "exam_board":       board_var.get().strip(),
            "spec_code":        spec_var.get().strip(),
            "tier":             tier_var.get().strip(),
            "candidate_number": cand_var.get().strip(),
            "entry_status":     status_var.get().strip(),
            "entry_date":       date_var.get().strip(),
            "fee":              fee_var.get().strip(),
            "notes":            notes_w.get("1.0", "end").strip(),
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
def open_exam_entries(host) -> None:
    logger.debug("GUI: open_exam_entries")
    host._clear_content()
    root = host.content_frame
    ttk.Label(root, text="GCSE Exam Entries",
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
    ttk.Label(bar, text="Board:").pack(side="left", padx=(0, 4))
    board_var = tk.StringVar(value="")
    ttk.Combobox(bar, textvariable=board_var,
                 values=["", *EXAM_BOARDS], state="readonly",
                 width=10).pack(side="left", padx=(0, 6))
    ttk.Label(bar, text="Status:").pack(side="left", padx=(0, 4))
    status_var = tk.StringVar(value="")
    ttk.Combobox(bar, textvariable=status_var,
                 values=["", *ENTRY_STATUSES], state="readonly",
                 width=11).pack(side="left", padx=(0, 8))
    ttk.Button(bar, text="Apply",
               command=lambda: _refresh()).pack(side="left", padx=2)
    ttk.Button(bar, text="New / update",
               command=lambda: _new(host, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Edit",
               command=lambda: _edit(host, tree, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Set status",
               command=lambda: _status(host, tree, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Delete",
               command=lambda: _delete(host, tree, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: _refresh()).pack(side="left", padx=2)

    cols = ("id", "pupil", "year", "subj", "board", "spec", "tier",
            "cand", "status", "fee")
    tree = ttk.Treeview(root, columns=cols, show="headings", height=18)
    for c, label, w in [
        ("id", "ID", 50), ("pupil", "Pupil", 90),
        ("year", "Yr", 50), ("subj", "Subj", 80),
        ("board", "Board", 80), ("spec", "Spec", 90),
        ("tier", "Tier", 90), ("cand", "Cand#", 100),
        ("status", "Status", 100), ("fee", "Fee", 70),
    ]:
        tree.heading(c, text=label)
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True)

    def _refresh() -> None:
        for i in tree.get_children():
            tree.delete(i)
        try:
            rows = data.list_entries(
                year_group=year_var.get().strip() or None,
                exam_board=board_var.get().strip() or None,
                entry_status=status_var.get().strip() or None,
            )
        except ValidationError as e:
            messagebox.showerror("GCSE Exam Entries", str(e),
                                 parent=host.root)
            return
        except Exception as e:
            logger.exception("exam_entries refresh failed")
            messagebox.showerror("GCSE Exam Entries",
                                 f"Could not load:\n\n{e}",
                                 parent=host.root)
            return
        for e in rows:
            fee = f"£{e.fee:g}" if e.fee is not None else "-"
            tree.insert("", "end", iid=str(e.entry_id), values=(
                e.entry_id, e.pupil_id, e.pupil_year or "-",
                e.subject_code or "?", e.exam_board,
                e.spec_code or "-", e.tier,
                e.candidate_number or "-", e.entry_status, fee,
            ))
        try:
            s = data.cohort_summary(
                year_group=year_var.get().strip() or None)
            summary_var.set(
                f"Total: {s['total']}    "
                + "    ".join(f"{k}: {v}"
                                for k, v in s["by_status"].items())
                + f"    Fees: £{s['total_fees']}")
        except Exception:
            summary_var.set(f"{len(rows)} entry(ies) listed")
        host.status_var.set(f"GCSE Entries: {len(rows)} record(s)")

    tree.bind("<Double-1>", lambda _e: _edit(host, tree,
                                              on_done=_refresh))
    year_var.trace_add("write", lambda *_: _refresh())
    board_var.trace_add("write", lambda *_: _refresh())
    status_var.trace_add("write", lambda *_: _refresh())
    _refresh()


def _selected_id(tree: ttk.Treeview, host) -> int | None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("GCSE Exam Entries",
                            "Select an entry first.",
                            parent=host.root)
        return None
    try:
        return int(sel)
    except ValueError:
        return None


@_safe_view
def _new(host, *, on_done=None) -> None:
    fields = _entry_dialog(host, "New / update entry")
    if not fields:
        return
    e = data.upsert(fields)
    messagebox.showinfo(
        "GCSE Exam Entries",
        f"Saved {e.pupil_id} / {e.subject_code} "
        f"({e.exam_board} {e.tier}, {e.entry_status})",
        parent=host.root,
    )
    if on_done:
        on_done()


@_safe_view
def _edit(host, tree: ttk.Treeview, *, on_done=None) -> None:
    eid = _selected_id(tree, host)
    if eid is None:
        return
    existing = data.get(eid)
    if existing is None:
        return
    initial = {k: getattr(existing, k) for k in (
        "pupil_id", "subject_id", "exam_board", "spec_code",
        "tier", "candidate_number", "entry_status", "entry_date",
        "fee", "notes")}
    fields = _entry_dialog(host, f"Edit entry #{eid}", initial=initial)
    if not fields:
        return
    data.upsert(fields)
    if on_done:
        on_done()


@_safe_view
def _status(host, tree: ttk.Treeview, *, on_done=None) -> None:
    eid = _selected_id(tree, host)
    if eid is None:
        return
    e = data.get(eid)
    if e is None:
        return
    dlg = tk.Toplevel(host.root)
    dlg.title(f"Status — #{eid}")
    dlg.transient(host.root)
    dlg.geometry("340x150")
    dlg.update_idletasks()
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        pass
    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)
    ttk.Label(frm,
              text=f"{e.pupil_id} / {e.subject_code}").pack(anchor="w")
    ttk.Label(frm, text=f"Current: {e.entry_status}",
              foreground="#666").pack(anchor="w", pady=(0, 8))
    new_var = tk.StringVar(value=e.entry_status)
    ttk.Combobox(frm, textvariable=new_var,
                 values=list(ENTRY_STATUSES),
                 state="readonly").pack(fill="x")

    def _save() -> None:
        try:
            data.set_status(eid, new_var.get())
        except ValidationError as ex:
            messagebox.showerror("GCSE Exam Entries", str(ex),
                                 parent=dlg)
            return
        dlg.destroy()
        if on_done:
            on_done()

    btns = ttk.Frame(frm)
    btns.pack(fill="x", pady=(10, 0))
    ttk.Button(btns, text="Cancel",
               command=dlg.destroy).pack(side="right", padx=4)
    ttk.Button(btns, text="Save", command=_save).pack(side="right")


@_safe_view
def _delete(host, tree: ttk.Treeview, *, on_done=None) -> None:
    eid = _selected_id(tree, host)
    if eid is None:
        return
    existing = data.get(eid)
    if existing is None:
        return
    if not messagebox.askyesno(
            "Delete entry",
            f"Delete entry for {existing.pupil_id} / "
            f"{existing.subject_code}?",
            parent=host.root):
        return
    data.delete(eid)
    if on_done:
        on_done()
