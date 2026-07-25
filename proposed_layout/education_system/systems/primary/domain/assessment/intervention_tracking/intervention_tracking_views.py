"""Tk views for intervention tracking."""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import Any, Callable

from education_system.systems.primary.domain.assessment.intervention_tracking import (
    intervention_tracking as data,
)
from education_system.systems.primary.domain.assessment.intervention_tracking.intervention_tracking import (
    INTERVENTION_TYPES, INTERVENTION_STATUSES, FREQUENCIES, OUTCOMES,
)
from education_system.systems.primary.domain.academics.subjects import (
    subjects as subjects_data,
)
from education_system.systems.primary.domain.learners.pupils.pupils import (
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
                messagebox.showerror("Intervention Tracking", str(e),
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


def _intervention_dialog(host, title: str,
                          initial: dict[str, Any] | None = None
                          ) -> dict[str, Any] | None:
    dlg = tk.Toplevel(host.root)
    dlg.title(title)
    dlg.transient(host.root)
    dlg.geometry("520x680")
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
    type_var   = tk.StringVar(value=str(initial.get("intervention_type")
                                         or "Catch-up"))
    start_var  = tk.StringVar(value=str(initial.get("start_date") or ""))
    end_var    = tk.StringVar(value=str(initial.get("end_date") or ""))
    status_var = tk.StringVar(value=str(initial.get("status")
                                         or "Planned"))
    ledby_var  = tk.StringVar(value=str(initial.get("led_by") or ""))
    loc_var    = tk.StringVar(value=str(initial.get("location") or ""))
    freq_var   = tk.StringVar(value=str(initial.get("frequency")
                                          or "Weekly"))
    baseline_var = tk.StringVar(value=str(initial.get("baseline_grade")
                                            or ""))
    target_var   = tk.StringVar(value=str(initial.get("target_grade")
                                            or ""))
    current_var  = tk.StringVar(value=str(initial.get("current_grade")
                                            or ""))
    outcome_var  = tk.StringVar(value=str(initial.get("outcome") or ""))

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
        ("Pupil ID:",    ttk.Entry(frm, textvariable=pupil_var,
                                     width=14)),
        ("Subject:",     ttk.Combobox(frm, textvariable=subject_var,
                                       values=subject_labels,
                                       state="readonly", width=42)),
        ("Type:",        ttk.Combobox(frm, textvariable=type_var,
                                       values=list(INTERVENTION_TYPES),
                                       state="readonly", width=18)),
        ("Start date:",  ttk.Entry(frm, textvariable=start_var, width=14)),
        ("End date:",    ttk.Entry(frm, textvariable=end_var, width=14)),
        ("Status:",      ttk.Combobox(frm, textvariable=status_var,
                                       values=list(INTERVENTION_STATUSES),
                                       state="readonly", width=12)),
        ("Led by:",      ttk.Entry(frm, textvariable=ledby_var, width=28)),
        ("Location:",    ttk.Entry(frm, textvariable=loc_var, width=20)),
        ("Frequency:",   ttk.Combobox(frm, textvariable=freq_var,
                                       values=list(FREQUENCIES),
                                       state="readonly", width=14)),
        ("Baseline grade:", ttk.Entry(frm, textvariable=baseline_var,
                                       width=6)),
        ("Target grade:",   ttk.Entry(frm, textvariable=target_var,
                                       width=6)),
        ("Current grade:",  ttk.Entry(frm, textvariable=current_var,
                                       width=6)),
        ("Outcome:",     ttk.Combobox(frm, textvariable=outcome_var,
                                       values=["", *OUTCOMES],
                                       state="readonly", width=14)),
    ]
    for i, (label, widget) in enumerate(rows):
        ttk.Label(frm, text=label).grid(row=i, column=0, sticky="w",
                                         pady=2)
        widget.grid(row=i, column=1, sticky="ew", pady=2)
    frm.columnconfigure(1, weight=1)

    ttk.Label(frm, text="Goal:").grid(row=len(rows), column=0,
                                        sticky="nw", pady=2)
    goal_w = tk.Text(frm, width=44, height=3, wrap="word")
    goal_w.insert("1.0", str(initial.get("goal") or ""))
    goal_w.grid(row=len(rows), column=1, sticky="ew", pady=2)

    ttk.Label(frm, text="Notes:").grid(row=len(rows) + 1, column=0,
                                        sticky="nw", pady=2)
    notes_w = tk.Text(frm, width=44, height=3, wrap="word")
    notes_w.insert("1.0", str(initial.get("notes") or ""))
    notes_w.grid(row=len(rows) + 1, column=1, sticky="ew", pady=2)

    result: dict[str, Any] | None = None

    def _parse_subject(label: str) -> str:
        label = (label or "").strip()
        if not label.startswith("#"):
            return ""
        return label.split()[0][1:]

    def _save() -> None:
        nonlocal result
        result = {
            "pupil_id":          pupil_var.get().strip(),
            "subject_id":        _parse_subject(subject_var.get()),
            "intervention_type": type_var.get().strip(),
            "start_date":        start_var.get().strip(),
            "end_date":          end_var.get().strip(),
            "status":            status_var.get().strip(),
            "led_by":            ledby_var.get().strip(),
            "location":          loc_var.get().strip(),
            "frequency":         freq_var.get().strip(),
            "baseline_grade":    baseline_var.get().strip(),
            "target_grade":      target_var.get().strip(),
            "current_grade":     current_var.get().strip(),
            "outcome":           outcome_var.get().strip(),
            "goal":              goal_w.get("1.0", "end").strip(),
            "notes":             notes_w.get("1.0", "end").strip(),
        }
        dlg.destroy()

    btns = ttk.Frame(frm)
    btns.grid(row=len(rows) + 2, column=0, columnspan=2, sticky="e",
              pady=(12, 0))
    ttk.Button(btns, text="Cancel",
               command=dlg.destroy).pack(side="right", padx=4)
    ttk.Button(btns, text="Save", command=_save).pack(side="right")
    dlg.wait_window()
    return result


def _review_dialog(host, intervention_id: int,
                    existing: data.InterventionReview | None = None
                    ) -> dict[str, Any] | None:
    dlg = tk.Toplevel(host.root)
    dlg.title(f"Review — intervention #{intervention_id}")
    dlg.transient(host.root)
    dlg.geometry("440x420")
    dlg.update_idletasks()
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        pass
    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    date_var     = tk.StringVar(value=str(
        existing.review_date if existing else ""))
    reviewer_var = tk.StringVar(value=str(
        existing.reviewer if existing else ""))
    att_var      = tk.StringVar(value=str(
        existing.attendance_pct if existing
        and existing.attendance_pct is not None else ""))
    on_track_var = tk.BooleanVar(value=(existing.on_track
                                          if existing else True))
    next_var     = tk.StringVar(value=str(
        existing.next_action if existing else ""))

    rows: list[tuple[str, tk.Widget]] = [
        ("Review date:", ttk.Entry(frm, textvariable=date_var,
                                     width=14)),
        ("Reviewer:",    ttk.Entry(frm, textvariable=reviewer_var,
                                     width=24)),
        ("Attendance %:", ttk.Entry(frm, textvariable=att_var, width=8)),
        ("On-track:",    ttk.Checkbutton(frm, variable=on_track_var)),
        ("Next action:", ttk.Entry(frm, textvariable=next_var, width=30)),
    ]
    for label, widget in rows:
        row = ttk.Frame(frm)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text=label, width=14).pack(side="left")
        widget.pack(in_=row, side="left", padx=4)

    ttk.Label(frm, text="Progress notes:").pack(anchor="w",
                                                  pady=(8, 0))
    notes_w = tk.Text(frm, width=44, height=4, wrap="word")
    notes_w.insert("1.0", str(existing.progress_notes if existing
                                else ""))
    notes_w.pack(fill="x", pady=2)

    result: dict[str, Any] | None = None

    def _save() -> None:
        nonlocal result
        result = {
            "intervention_id": intervention_id,
            "review_date":     date_var.get().strip(),
            "reviewer":        reviewer_var.get().strip(),
            "attendance_pct":  att_var.get().strip(),
            "on_track":        bool(on_track_var.get()),
            "next_action":     next_var.get().strip(),
            "progress_notes":  notes_w.get("1.0", "end").strip(),
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
def open_intervention_tracking(host) -> None:
    logger.debug("GUI: open_intervention_tracking")
    host._clear_content()
    root = host.content_frame
    ttk.Label(root, text="Intervention Tracking",
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
    ttk.Label(bar, text="Status:").pack(side="left", padx=(0, 4))
    status_var = tk.StringVar(value="")
    ttk.Combobox(bar, textvariable=status_var,
                 values=["", *INTERVENTION_STATUSES],
                 state="readonly", width=10).pack(
        side="left", padx=(0, 6))
    ttk.Label(bar, text="Type:").pack(side="left", padx=(0, 4))
    type_var = tk.StringVar(value="")
    ttk.Combobox(bar, textvariable=type_var,
                 values=["", *INTERVENTION_TYPES], state="readonly",
                 width=14).pack(side="left", padx=(0, 8))
    ttk.Button(bar, text="Apply",
               command=lambda: _refresh()).pack(side="left", padx=2)
    ttk.Button(bar, text="New",
               command=lambda: _new(host, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Edit",
               command=lambda: _edit(host, tree, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Status",
               command=lambda: _status(host, tree, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Reviews",
               command=lambda: _open_reviews(host, tree)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Summary",
               command=lambda: _summary(host,
                                          year_var.get().strip() or None)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Delete",
               command=lambda: _delete(host, tree, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: _refresh()).pack(side="left", padx=2)

    cols = ("id", "pupil", "year", "subj", "type", "start", "led",
            "freq", "status", "outcome")
    tree = ttk.Treeview(root, columns=cols, show="headings", height=18)
    for c, label, w in [
        ("id", "ID", 50), ("pupil", "Pupil", 90),
        ("year", "Yr", 50), ("subj", "Subj", 70),
        ("type", "Type", 130), ("start", "Start", 100),
        ("led", "Led by", 130), ("freq", "Freq", 100),
        ("status", "Status", 90), ("outcome", "Outcome", 100),
    ]:
        tree.heading(c, text=label)
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True)

    def _refresh() -> None:
        for i in tree.get_children():
            tree.delete(i)
        try:
            rows = data.list_interventions(
                year_group=year_var.get().strip() or None,
                status=status_var.get().strip() or None,
                intervention_type=type_var.get().strip() or None,
            )
        except ValidationError as e:
            messagebox.showerror("Intervention Tracking", str(e),
                                 parent=host.root)
            return
        except Exception as e:
            logger.exception("interventions refresh failed")
            messagebox.showerror("Intervention Tracking",
                                 f"Could not load:\n\n{e}",
                                 parent=host.root)
            return
        for i in rows:
            tree.insert("", "end", iid=str(i.intervention_id), values=(
                i.intervention_id, i.pupil_id, i.pupil_year or "-",
                i.subject_code or "-", i.intervention_type,
                i.start_date, i.led_by or "-", i.frequency,
                i.status, i.outcome or "-",
            ))
        try:
            s = data.cohort_summary(
                year_group=year_var.get().strip() or None)
            summary_var.set(
                f"Total: {s['total']}    "
                + "    ".join(f"{k}: {v}"
                                for k, v in s["by_status"].items()))
        except Exception:
            summary_var.set(f"{len(rows)} intervention(s)")
        host.status_var.set(f"Interventions: {len(rows)} record(s)")

    tree.bind("<Double-1>", lambda _e: _open_reviews(host, tree))
    year_var.trace_add("write", lambda *_: _refresh())
    status_var.trace_add("write", lambda *_: _refresh())
    type_var.trace_add("write", lambda *_: _refresh())
    _refresh()


def _selected_id(tree: ttk.Treeview, host) -> int | None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Intervention Tracking",
                            "Select an intervention first.",
                            parent=host.root)
        return None
    try:
        return int(sel)
    except ValueError:
        return None


@_safe_view
def _new(host, *, on_done=None) -> None:
    fields = _intervention_dialog(host, "New intervention")
    if not fields:
        return
    i = data.create(fields)
    messagebox.showinfo("Intervention Tracking",
                        f"Created intervention #{i.intervention_id} for "
                        f"{i.pupil_id}",
                        parent=host.root)
    if on_done:
        on_done()


@_safe_view
def _edit(host, tree: ttk.Treeview, *, on_done=None) -> None:
    iid = _selected_id(tree, host)
    if iid is None:
        return
    existing = data.get(iid)
    if existing is None:
        return
    initial = {k: getattr(existing, k) for k in (
        "pupil_id", "subject_id", "intervention_type", "goal",
        "start_date", "end_date", "status", "led_by", "location",
        "frequency", "baseline_grade", "target_grade",
        "current_grade", "outcome", "notes")}
    fields = _intervention_dialog(host,
                                     f"Edit intervention #{iid}",
                                     initial=initial)
    if not fields:
        return
    data.update(iid, fields)
    if on_done:
        on_done()


@_safe_view
def _status(host, tree: ttk.Treeview, *, on_done=None) -> None:
    iid = _selected_id(tree, host)
    if iid is None:
        return
    existing = data.get(iid)
    if existing is None:
        return
    dlg = tk.Toplevel(host.root)
    dlg.title(f"Status — #{iid}")
    dlg.transient(host.root)
    dlg.geometry("340x200")
    dlg.update_idletasks()
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        pass
    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)
    ttk.Label(frm,
              text=f"{existing.pupil_id} — "
                   f"{existing.intervention_type}").pack(anchor="w")
    ttk.Label(frm, text=f"Current: {existing.status}    "
                          f"Outcome: {existing.outcome or '-'}",
              foreground="#666").pack(anchor="w", pady=(0, 8))
    status_var = tk.StringVar(value=existing.status)
    ttk.Label(frm, text="New status:").pack(anchor="w")
    ttk.Combobox(frm, textvariable=status_var,
                 values=list(INTERVENTION_STATUSES),
                 state="readonly").pack(fill="x")
    outcome_var = tk.StringVar(value=existing.outcome or "")
    ttk.Label(frm, text="Outcome (required if Complete / Cancelled):"
              ).pack(anchor="w", pady=(8, 0))
    ttk.Combobox(frm, textvariable=outcome_var,
                 values=["", *OUTCOMES],
                 state="readonly").pack(fill="x")

    def _save() -> None:
        try:
            data.set_status(iid, status_var.get(),
                             outcome=outcome_var.get().strip() or None)
        except ValidationError as ex:
            messagebox.showerror("Intervention Tracking", str(ex),
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
    iid = _selected_id(tree, host)
    if iid is None:
        return
    existing = data.get(iid)
    if existing is None:
        return
    if not messagebox.askyesno(
            "Delete intervention",
            f"Delete intervention #{iid} ({existing.pupil_id}, "
            f"{existing.intervention_type}) and all reviews?",
            parent=host.root):
        return
    data.delete(iid)
    if on_done:
        on_done()


@_safe_view
def _summary(host, year_group: str | None) -> None:
    s = data.cohort_summary(year_group=year_group)
    lines = [f"Total interventions: {s['total']}"]
    if s["by_status"]:
        lines.append("")
        lines.append("By status:")
        for k, v in s["by_status"].items():
            lines.append(f"  {k:<12} {v}")
    if s["by_type"]:
        lines.append("")
        lines.append("By type:")
        for k, v in sorted(s["by_type"].items(), key=lambda kv: -kv[1]):
            lines.append(f"  {k:<18} {v}")
    if s["by_outcome"]:
        lines.append("")
        lines.append("By outcome:")
        for k, v in s["by_outcome"].items():
            lines.append(f"  {k:<14} {v}")
    messagebox.showinfo("Interventions — summary",
                        "\n".join(lines), parent=host.root)


@_safe_view
def _open_reviews(host, tree: ttk.Treeview) -> None:
    iid = _selected_id(tree, host)
    if iid is None:
        return
    rec = data.get(iid)
    if rec is None:
        return

    dlg = tk.Toplevel(host.root)
    dlg.title(f"Reviews — intervention #{iid}")
    dlg.transient(host.root)
    dlg.geometry("760x500")
    dlg.update_idletasks()
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        pass

    frm = ttk.Frame(dlg, padding=10)
    frm.pack(fill="both", expand=True)
    header_var = tk.StringVar()
    ttk.Label(frm, textvariable=header_var,
              font=("", 10, "bold")).pack(anchor="w")

    bar = ttk.Frame(frm)
    bar.pack(fill="x", pady=(8, 4))
    ttk.Button(bar, text="Add review",
               command=lambda: _do_add()).pack(side="left", padx=2)
    ttk.Button(bar, text="Delete selected",
               command=lambda: _do_delete()).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: _refresh()).pack(side="left", padx=2)

    t = ttk.Treeview(frm,
                       columns=("id", "date", "reviewer", "att",
                                 "on_track", "notes", "next"),
                       show="headings", height=14)
    for c, label, w in [
        ("id", "ID", 50), ("date", "Date", 100),
        ("reviewer", "Reviewer", 140), ("att", "Att %", 60),
        ("on_track", "On-track", 70), ("notes", "Notes", 220),
        ("next", "Next action", 160),
    ]:
        t.heading(c, text=label)
        t.column(c, width=w, anchor="w")
    t.pack(fill="both", expand=True)

    def _refresh() -> None:
        for i in t.get_children():
            t.delete(i)
        try:
            s = data.intervention_summary(iid)
        except Exception as e:
            logger.exception("intervention_summary failed")
            messagebox.showerror("Intervention Tracking",
                                 f"Could not load:\n\n{e}", parent=dlg)
            return
        i = s["intervention"]
        header_var.set(
            f"#{i.intervention_id}  {i.pupil_id} ({i.pupil_name or '-'}, "
            f"Yr {i.pupil_year or '-'}) — {i.intervention_type}    "
            f"Reviews: {s['review_count']}    "
            f"Avg att%: "
            f"{s['avg_attendance'] if s['avg_attendance'] is not None else '-'}    "
            f"On-track: {s['on_track']}/{s['review_count']}")
        for r in s["reviews"]:
            t.insert("", "end", iid=str(r.review_id), values=(
                r.review_id, r.review_date, r.reviewer or "-",
                f"{r.attendance_pct:.0f}" if r.attendance_pct is not None
                else "-",
                "Yes" if r.on_track else "No",
                (r.progress_notes or "-")[:80],
                (r.next_action or "-")[:80],
            ))

    def _do_add() -> None:
        fields = _review_dialog(host, iid)
        if not fields:
            return
        try:
            data.add_review(fields)
        except ValidationError as e:
            messagebox.showerror("Intervention Tracking", str(e),
                                 parent=dlg)
            return
        _refresh()

    def _do_delete() -> None:
        sel = t.focus()
        if not sel:
            messagebox.showinfo("Intervention Tracking",
                                "Select a review first.", parent=dlg)
            return
        try:
            rid = int(sel)
        except ValueError:
            return
        if not messagebox.askyesno(
                "Delete review",
                f"Delete review #{rid}?", parent=dlg):
            return
        data.delete_review(rid)
        _refresh()

    _refresh()
