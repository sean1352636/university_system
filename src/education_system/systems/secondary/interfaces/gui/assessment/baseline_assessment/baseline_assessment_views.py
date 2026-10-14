"""Tk views for baseline assessment."""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import Any, Callable

from education_system.systems.secondary.domain.assessment.baseline_assessment import (
    baseline_assessment as data,
)
from education_system.systems.secondary.domain.assessment.baseline_assessment.baseline_assessment import (
    TEST_TYPES,
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
                messagebox.showerror("Baseline Assessment", str(e),
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


def _test_dialog(host, title: str,
                 initial: dict[str, Any] | None = None
                 ) -> dict[str, Any] | None:
    dlg = tk.Toplevel(host.root)
    dlg.title(title)
    dlg.transient(host.root)
    dlg.geometry("460x440")
    dlg.update_idletasks()
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped — dialog not viewable", exc_info=True)

    initial = initial or {}
    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    name_var  = tk.StringVar(value=str(initial.get("name") or ""))
    year_var  = tk.StringVar(value=str(initial.get("year_group") or "7"))
    type_var  = tk.StringVar(value=str(initial.get("test_type")
                                         or "School"))
    date_var  = tk.StringVar(value=str(initial.get("test_date") or ""))
    max_var   = tk.StringVar(value=str(initial.get("max_marks") or ""))

    try:
        subjects = subjects_data.list_all(active_only=True)
    except Exception:
        subjects = []
    subject_labels = [""] + [f"#{s.subject_id} {s.code} — {s.name}"
                              for s in subjects]
    subject_var = tk.StringVar(value="")
    initial_sid = initial.get("subject_id")
    if initial_sid is not None:
        for s in subjects:
            if s.subject_id == int(initial_sid):
                subject_var.set(f"#{s.subject_id} {s.code} — {s.name}")
                break

    rows: list[tuple[str, tk.Widget]] = [
        ("Name:",     ttk.Entry(frm, textvariable=name_var, width=40)),
        ("Subject:",  ttk.Combobox(frm, textvariable=subject_var,
                                    values=subject_labels,
                                    state="readonly", width=38)),
        ("Year:",     ttk.Combobox(frm, textvariable=year_var,
                                    values=list(YEAR_GROUPS),
                                    state="readonly", width=8)),
        ("Type:",     ttk.Combobox(frm, textvariable=type_var,
                                    values=list(TEST_TYPES),
                                    state="readonly", width=12)),
        ("Date:",     ttk.Entry(frm, textvariable=date_var, width=14)),
        ("Max marks:", ttk.Entry(frm, textvariable=max_var, width=8)),
    ]
    for i, (label, widget) in enumerate(rows):
        ttk.Label(frm, text=label).grid(row=i, column=0, sticky="w",
                                         pady=2)
        widget.grid(row=i, column=1, sticky="ew", pady=2)
    frm.columnconfigure(1, weight=1)

    ttk.Label(frm, text="Notes:").grid(row=len(rows), column=0,
                                        sticky="nw", pady=2)
    notes_w = tk.Text(frm, width=40, height=4, wrap="word")
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
            "name":       name_var.get().strip(),
            "subject_id": _parse_subject(subject_var.get()),
            "year_group": year_var.get().strip(),
            "test_type":  type_var.get().strip(),
            "test_date":  date_var.get().strip(),
            "max_marks":  max_var.get().strip(),
            "notes":      notes_w.get("1.0", "end").strip(),
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


def _result_dialog(host, test: data.BaselineTest,
                    existing: data.BaselineResult | None,
                    initial_pupil: str | None = None
                    ) -> dict[str, Any] | None:
    dlg = tk.Toplevel(host.root)
    dlg.title(f"Result — {test.name}")
    dlg.transient(host.root)
    dlg.geometry("420x340")
    dlg.update_idletasks()
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        pass
    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)
    ttk.Label(frm, text=f"Test: {test.name}",
              font=("", 10, "bold")).pack(anchor="w", pady=(0, 6))
    if test.max_marks is not None:
        ttk.Label(frm, text=f"Max marks: {test.max_marks}",
                  foreground="#666").pack(anchor="w", pady=(0, 8))

    pupil_var = tk.StringVar(value=str(
        (existing.pupil_id if existing else initial_pupil) or ""))
    marks_var = tk.StringVar(value=str(
        existing.marks_awarded if existing
        and existing.marks_awarded is not None else ""))
    ss_var = tk.StringVar(value=str(
        existing.standardised_score if existing
        and existing.standardised_score is not None else ""))
    grade_var = tk.StringVar(value=str(
        existing.baseline_grade if existing else ""))

    rows: list[tuple[str, tk.Widget]] = [
        ("Pupil ID:",  ttk.Entry(frm, textvariable=pupil_var, width=14,
                                  state=("readonly" if existing
                                          else "normal"))),
        ("Marks:",     ttk.Entry(frm, textvariable=marks_var, width=8)),
        ("Std score:", ttk.Entry(frm, textvariable=ss_var, width=8)),
        ("Grade:",     ttk.Entry(frm, textvariable=grade_var, width=6)),
    ]
    for label, widget in rows:
        row = ttk.Frame(frm)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text=label, width=12).pack(side="left")
        widget.pack(in_=row, side="left", padx=4)

    ttk.Label(frm, text="Notes:").pack(anchor="w", pady=(8, 0))
    notes_w = tk.Text(frm, width=44, height=4, wrap="word")
    notes_w.insert("1.0", str(existing.notes if existing else ""))
    notes_w.pack(fill="x", pady=2)

    result: dict[str, Any] | None = None

    def _save() -> None:
        nonlocal result
        result = {
            "pupil_id":           pupil_var.get().strip(),
            "marks_awarded":      marks_var.get().strip(),
            "standardised_score": ss_var.get().strip(),
            "baseline_grade":     grade_var.get().strip(),
            "notes":              notes_w.get("1.0", "end").strip(),
        }
        dlg.destroy()

    btns = ttk.Frame(frm)
    btns.pack(fill="x", pady=(10, 0))
    ttk.Button(btns, text="Cancel",
               command=dlg.destroy).pack(side="right", padx=4)
    ttk.Button(btns, text="Save", command=_save).pack(side="right")
    dlg.wait_window()
    return result


@_safe_view
def open_baseline_assessment(host) -> None:
    logger.debug("GUI: open_baseline_assessment")
    host._clear_content()
    root = host.content_frame
    ttk.Label(root, text="Baseline Assessment",
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
    ttk.Label(bar, text="Type:").pack(side="left", padx=(0, 4))
    type_var = tk.StringVar(value="")
    ttk.Combobox(bar, textvariable=type_var,
                 values=["", *TEST_TYPES], state="readonly",
                 width=10).pack(side="left", padx=(0, 8))
    ttk.Button(bar, text="New test",
               command=lambda: _new_test(host, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Edit test",
               command=lambda: _edit_test(host, tree, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Results",
               command=lambda: _open_results(host, tree)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Summary",
               command=lambda: _summary(host, tree)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Delete test",
               command=lambda: _delete_test(host, tree,
                                              on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: _refresh()).pack(side="left", padx=2)

    cols = ("id", "date", "year", "type", "subj", "name", "max")
    tree = ttk.Treeview(root, columns=cols, show="headings", height=18)
    for c, label, w in [
        ("id", "ID", 50), ("date", "Date", 100),
        ("year", "Yr", 50), ("type", "Type", 90),
        ("subj", "Subj", 80), ("name", "Name", 280),
        ("max", "Max", 70),
    ]:
        tree.heading(c, text=label)
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True)

    def _refresh() -> None:
        for i in tree.get_children():
            tree.delete(i)
        try:
            rows = data.list_tests(
                year_group=year_var.get().strip() or None,
                test_type=type_var.get().strip() or None,
            )
        except ValidationError as e:
            messagebox.showerror("Baseline Assessment", str(e),
                                 parent=host.root)
            return
        except Exception as e:
            logger.exception("baseline tests refresh failed")
            messagebox.showerror("Baseline Assessment",
                                 f"Could not load tests:\n\n{e}",
                                 parent=host.root)
            return
        for t in rows:
            tree.insert("", "end", iid=str(t.test_id), values=(
                t.test_id, t.test_date, t.year_group, t.test_type,
                t.subject_code or "-", t.name,
                t.max_marks if t.max_marks else "-",
            ))
        summary_var.set(f"{len(rows)} test(s) listed")
        host.status_var.set(f"Baseline: {len(rows)} test(s)")

    tree.bind("<Double-1>", lambda _e: _open_results(host, tree))
    year_var.trace_add("write", lambda *_: _refresh())
    type_var.trace_add("write", lambda *_: _refresh())
    _refresh()


def _selected_id(tree: ttk.Treeview, host) -> int | None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Baseline Assessment",
                            "Select a test first.",
                            parent=host.root)
        return None
    try:
        return int(sel)
    except ValueError:
        return None


@_safe_view
def _new_test(host, *, on_done=None) -> None:
    fields = _test_dialog(host, "New baseline test")
    if not fields:
        return
    t = data.create_test(fields)
    messagebox.showinfo("Baseline Assessment",
                        f"Created {t.name} (Yr{t.year_group})",
                        parent=host.root)
    if on_done:
        on_done()


@_safe_view
def _edit_test(host, tree: ttk.Treeview, *, on_done=None) -> None:
    tid = _selected_id(tree, host)
    if tid is None:
        return
    existing = data.get_test(tid)
    if existing is None:
        return
    initial = {k: getattr(existing, k) for k in (
        "name", "subject_id", "year_group", "test_type",
        "test_date", "max_marks", "notes")}
    fields = _test_dialog(host, f"Edit test #{tid}", initial=initial)
    if not fields:
        return
    data.update_test(tid, fields)
    if on_done:
        on_done()


@_safe_view
def _delete_test(host, tree: ttk.Treeview, *, on_done=None) -> None:
    tid = _selected_id(tree, host)
    if tid is None:
        return
    t = data.get_test(tid)
    if t is None:
        return
    if not messagebox.askyesno(
            "Delete test",
            f"Delete '{t.name}' and ALL its results?",
            parent=host.root):
        return
    data.delete_test(tid)
    if on_done:
        on_done()


@_safe_view
def _summary(host, tree: ttk.Treeview) -> None:
    tid = _selected_id(tree, host)
    if tid is None:
        return
    s = data.test_summary(tid)
    t = s["test"]
    lines = [
        f"{t.name}",
        f"Yr {t.year_group}    {t.test_type}    {t.test_date}",
        "",
        f"Results: {s['count']}",
        f"Avg %: {s['avg_pct'] if s['avg_pct'] is not None else '-'}    "
        f"Min %: {s['min_pct'] if s['min_pct'] is not None else '-'}    "
        f"Max %: {s['max_pct'] if s['max_pct'] is not None else '-'}",
    ]
    if s["avg_standardised"] is not None:
        lines.append(
            f"Avg standardised score: {s['avg_standardised']}")
    if s["grades"]:
        lines.append("")
        lines.append("Grades:")
        for k, v in sorted(s["grades"].items()):
            lines.append(f"   {k}: {v}")
    messagebox.showinfo("Baseline — summary", "\n".join(lines),
                        parent=host.root)


@_safe_view
def _open_results(host, tree: ttk.Treeview) -> None:
    tid = _selected_id(tree, host)
    if tid is None:
        return
    t = data.get_test(tid)
    if t is None:
        return

    dlg = tk.Toplevel(host.root)
    dlg.title(f"Results — {t.name}")
    dlg.transient(host.root)
    dlg.geometry("780x500")
    dlg.update_idletasks()
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        pass

    frm = ttk.Frame(dlg, padding=10)
    frm.pack(fill="both", expand=True)
    ttk.Label(frm,
              text=f"{t.name}    Yr {t.year_group}    "
                   f"{t.test_type}    {t.test_date}    "
                   f"max {t.max_marks or '-'}",
              font=("", 10, "bold")).pack(anchor="w")

    bar = ttk.Frame(frm)
    bar.pack(fill="x", pady=(8, 4))
    ttk.Button(bar, text="Add result",
               command=lambda: _do_upsert(None)).pack(side="left", padx=2)
    ttk.Button(bar, text="Edit selected",
               command=lambda: _do_upsert("selected")
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Delete selected",
               command=lambda: _do_delete()).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: _refresh()).pack(side="left", padx=2)

    res_tree = ttk.Treeview(frm,
                             columns=("id", "pupil", "year", "marks",
                                       "pct", "ss", "grade", "notes"),
                             show="headings", height=14)
    for c, label, w in [
        ("id", "ID", 50), ("pupil", "Pupil", 100),
        ("year", "Yr", 50), ("marks", "Marks", 80),
        ("pct", "%", 50), ("ss", "Std", 60),
        ("grade", "Grade", 60), ("notes", "Notes", 240),
    ]:
        res_tree.heading(c, text=label)
        res_tree.column(c, width=w, anchor="w")
    res_tree.pack(fill="both", expand=True)

    def _refresh() -> None:
        for i in res_tree.get_children():
            res_tree.delete(i)
        try:
            rows = data.list_results(tid)
        except Exception as e:
            logger.exception("baseline results list failed")
            messagebox.showerror("Baseline Assessment",
                                 f"Could not load:\n\n{e}",
                                 parent=dlg)
            return
        for r in rows:
            marks = ("-" if r.marks_awarded is None
                     else (f"{r.marks_awarded:g}/{r.test_max:g}"
                            if r.test_max else f"{r.marks_awarded:g}"))
            res_tree.insert("", "end", iid=str(r.result_id), values=(
                r.result_id, r.pupil_id, r.pupil_year or "-",
                marks,
                f"{r.mark_pct:.0f}" if r.mark_pct is not None else "-",
                (f"{r.standardised_score:.0f}"
                 if r.standardised_score is not None else "-"),
                r.baseline_grade or "-",
                (r.notes or "-")[:60],
            ))

    def _do_upsert(mode: str | None) -> None:
        existing: data.BaselineResult | None = None
        initial_pupil: str | None = None
        if mode == "selected":
            sel = res_tree.focus()
            if not sel:
                messagebox.showinfo("Baseline Assessment",
                                    "Select a result first.",
                                    parent=dlg)
                return
            try:
                existing = data.get_result(int(sel))
            except Exception:
                logger.exception("get_result failed")
                return
        else:
            initial_pupil = simpledialog.askstring(
                "Pupil ID", "Pupil ID:", parent=dlg)
            if not initial_pupil:
                return
        fields = _result_dialog(host, t, existing,
                                  initial_pupil=initial_pupil)
        if not fields:
            return
        try:
            data.upsert_result(tid, fields)
        except ValidationError as e:
            messagebox.showerror("Baseline Assessment", str(e),
                                 parent=dlg)
            return
        _refresh()

    def _do_delete() -> None:
        sel = res_tree.focus()
        if not sel:
            messagebox.showinfo("Baseline Assessment",
                                "Select a result first.", parent=dlg)
            return
        try:
            rid = int(sel)
        except ValueError:
            return
        if not messagebox.askyesno(
                "Delete result",
                f"Delete result #{rid}?", parent=dlg):
            return
        data.delete_result(rid)
        _refresh()

    res_tree.bind("<Double-1>", lambda _e: _do_upsert("selected"))
    _refresh()
