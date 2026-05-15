"""Tk views for Prevent-duty referrals."""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import Any, Callable

from education_system.primarysch_system.modules.domain.prevent_duty import (
    prevent_duty as data,
)
from education_system.primarysch_system.modules.domain.prevent_duty.prevent_duty import (
    CONCERN_TYPES, RISK_LEVELS, REFERRAL_PATHWAYS, STATUSES, OUTCOMES,
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
                messagebox.showerror("Prevent Duty", str(e),
                                       parent=getattr(host, "root", None))
            except Exception:
                pass
        except Exception as e:
            logger.exception("%s failed", func.__name__)
            try:
                messagebox.showerror(
                    "Error",
                    f"An unexpected error occurred:\n\n{e}\n\n"
                    f"See logs for details.",
                    parent=getattr(host, "root", None),
                )
            except Exception:
                pass
    return wrapper


def _referral_dialog(host, title: str,
                       initial: dict[str, Any] | None = None
                       ) -> dict[str, Any] | None:
    dlg = tk.Toplevel(host.root)
    dlg.title(title)
    dlg.transient(host.root)
    dlg.geometry("620x860")
    dlg.update_idletasks()
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped", exc_info=True)

    initial = initial or {}
    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    pupil_var   = tk.StringVar(value=str(initial.get("pupil_id") or ""))
    concern_var = tk.StringVar(value=str(initial.get("concern_type")
                                            or "Vulnerability to radicalisation"))
    risk_var    = tk.StringVar(value=str(initial.get("risk_level") or "Low"))
    raised_by_var = tk.StringVar(value=str(initial.get("raised_by") or ""))
    raised_date_var = tk.StringVar(value=str(initial.get("raised_date") or ""))
    dsl_var     = tk.BooleanVar(value=bool(initial.get("dsl_informed")))
    dsl_name_var = tk.StringVar(value=str(initial.get("dsl_name") or ""))
    dsl_date_var = tk.StringVar(value=str(initial.get("dsl_informed_date") or ""))
    pathway_var = tk.StringVar(value=str(initial.get("referral_pathway")
                                            or "Internal monitoring"))
    rdate_var   = tk.StringVar(value=str(initial.get("referral_date") or ""))
    rref_var    = tk.StringVar(value=str(initial.get("referral_ref") or ""))
    agencies_var = tk.StringVar(value=str(initial.get("agencies_involved")
                                             or ""))
    parents_var = tk.BooleanVar(value=bool(initial.get("parents_informed")))
    parents_date_var = tk.StringVar(
        value=str(initial.get("parents_informed_date") or ""))
    review_var  = tk.StringVar(value=str(initial.get("next_review_date")
                                             or ""))
    status_var  = tk.StringVar(value=str(initial.get("status") or "Open"))
    outcome_var = tk.StringVar(value=str(initial.get("outcome") or "Pending"))
    closed_date_var = tk.StringVar(
        value=str(initial.get("closed_date") or ""))

    rows: list[tuple[str, tk.Widget]] = [
        ("Pupil ID:",     ttk.Entry(frm, textvariable=pupil_var, width=14)),
        ("Concern:",      ttk.Combobox(frm, textvariable=concern_var,
                                          values=list(CONCERN_TYPES),
                                          state="readonly", width=44)),
        ("Risk level:",   ttk.Combobox(frm, textvariable=risk_var,
                                          values=list(RISK_LEVELS),
                                          state="readonly", width=12)),
        ("Raised by:",    ttk.Entry(frm, textvariable=raised_by_var,
                                       width=24)),
        ("Raised date:",  ttk.Entry(frm, textvariable=raised_date_var,
                                       width=14)),
        ("DSL informed:", ttk.Checkbutton(frm, variable=dsl_var)),
        ("DSL name:",     ttk.Entry(frm, textvariable=dsl_name_var,
                                       width=24)),
        ("DSL informed date:", ttk.Entry(frm, textvariable=dsl_date_var,
                                            width=14)),
        ("Pathway:",      ttk.Combobox(frm, textvariable=pathway_var,
                                          values=list(REFERRAL_PATHWAYS),
                                          state="readonly", width=32)),
        ("Referral date:", ttk.Entry(frm, textvariable=rdate_var, width=14)),
        ("Referral ref:",  ttk.Entry(frm, textvariable=rref_var, width=20)),
        ("Agencies:",     ttk.Entry(frm, textvariable=agencies_var,
                                       width=32)),
        ("Parents informed:", ttk.Checkbutton(frm, variable=parents_var)),
        ("Parents informed date:", ttk.Entry(frm,
                                                textvariable=parents_date_var,
                                                width=14)),
        ("Next review:",  ttk.Entry(frm, textvariable=review_var, width=14)),
        ("Status:",       ttk.Combobox(frm, textvariable=status_var,
                                          values=list(STATUSES),
                                          state="readonly", width=32)),
        ("Outcome:",      ttk.Combobox(frm, textvariable=outcome_var,
                                          values=list(OUTCOMES),
                                          state="readonly", width=22)),
        ("Closed date:",  ttk.Entry(frm, textvariable=closed_date_var,
                                       width=14)),
    ]
    for i, (label, widget) in enumerate(rows):
        ttk.Label(frm, text=label).grid(row=i, column=0, sticky="w",
                                          pady=2)
        widget.grid(row=i, column=1, sticky="w", pady=2)
    frm.columnconfigure(1, weight=1)

    text_fields = [("Description:",     "description", 3),
                    ("Indicators:",      "indicators", 2),
                    ("Online activity:", "online_activity", 2),
                    ("Closure notes:",   "closure_notes", 2),
                    ("Notes:",           "notes", 2)]
    text_widgets: dict[str, tk.Text] = {}
    for i, (label, key, lines) in enumerate(text_fields,
                                              start=len(rows)):
        ttk.Label(frm, text=label).grid(row=i, column=0, sticky="nw",
                                          pady=2)
        t = tk.Text(frm, width=54, height=lines, wrap="word")
        t.insert("1.0", str(initial.get(key) or ""))
        t.grid(row=i, column=1, sticky="ew", pady=2)
        text_widgets[key] = t

    result: dict[str, Any] | None = None

    def _save() -> None:
        nonlocal result
        result = {
            "pupil_id":         pupil_var.get().strip(),
            "concern_type":     concern_var.get().strip(),
            "risk_level":       risk_var.get().strip(),
            "raised_by":        raised_by_var.get().strip(),
            "raised_date":      raised_date_var.get().strip(),
            "dsl_informed":     bool(dsl_var.get()),
            "dsl_name":         dsl_name_var.get().strip(),
            "dsl_informed_date": dsl_date_var.get().strip(),
            "referral_pathway": pathway_var.get().strip(),
            "referral_date":    rdate_var.get().strip(),
            "referral_ref":     rref_var.get().strip(),
            "agencies_involved": agencies_var.get().strip(),
            "parents_informed": bool(parents_var.get()),
            "parents_informed_date": parents_date_var.get().strip(),
            "next_review_date": review_var.get().strip(),
            "status":           status_var.get().strip(),
            "outcome":          outcome_var.get().strip(),
            "closed_date":      closed_date_var.get().strip(),
        }
        for k, w in text_widgets.items():
            result[k] = w.get("1.0", "end").strip()
        dlg.destroy()

    btns = ttk.Frame(frm)
    btns.grid(row=len(rows) + len(text_fields), column=0,
                columnspan=2, sticky="e", pady=(12, 0))
    ttk.Button(btns, text="Cancel",
                 command=dlg.destroy).pack(side="right", padx=4)
    ttk.Button(btns, text="Save", command=_save).pack(side="right")
    dlg.wait_window()
    return result


@_safe_view
def open_prevent_duty(host) -> None:
    logger.debug("GUI: open_prevent_duty")
    host._clear_content()
    root = host.content_frame
    ttk.Label(root, text="Prevent Duty",
                font=("", 16, "bold")).pack(anchor="w", pady=(0, 8))

    summary_var = tk.StringVar()
    ttk.Label(root, textvariable=summary_var,
                foreground="#666").pack(anchor="w", pady=(0, 8))

    bar = ttk.Frame(root)
    bar.pack(fill="x", pady=(0, 6))
    ttk.Label(bar, text="Status:").pack(side="left", padx=(0, 4))
    status_var = tk.StringVar(value="")
    ttk.Combobox(bar, textvariable=status_var,
                   values=["", *STATUSES], state="readonly",
                   width=22).pack(side="left", padx=(0, 6))
    ttk.Label(bar, text="Risk:").pack(side="left", padx=(0, 4))
    risk_var = tk.StringVar(value="")
    ttk.Combobox(bar, textvariable=risk_var,
                   values=["", *RISK_LEVELS], state="readonly",
                   width=10).pack(side="left", padx=(0, 6))
    open_only_var = tk.BooleanVar(value=False)
    ttk.Checkbutton(bar, text="Open only",
                       variable=open_only_var).pack(side="left", padx=4)
    ttk.Button(bar, text="Apply",
                  command=lambda: _refresh()).pack(side="left", padx=2)
    ttk.Button(bar, text="New",
                  command=lambda: _new(host, on_done=_refresh)
                  ).pack(side="left", padx=2)
    ttk.Button(bar, text="Edit",
                  command=lambda: _edit(host, tree, on_done=_refresh)
                  ).pack(side="left", padx=2)
    ttk.Button(bar, text="Close",
                  command=lambda: _close(host, tree, on_done=_refresh)
                  ).pack(side="left", padx=2)
    ttk.Button(bar, text="Delete",
                  command=lambda: _delete(host, tree, on_done=_refresh)
                  ).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
                  command=lambda: _refresh()).pack(side="left", padx=2)

    cols = ("id", "pupil", "yr", "raised", "concern", "risk",
              "pathway", "status", "outcome")
    tree = ttk.Treeview(root, columns=cols, show="headings", height=18)
    for c, label, w in [
        ("id", "ID", 50), ("pupil", "Pupil", 180),
        ("yr", "Yr", 40), ("raised", "Raised", 90),
        ("concern", "Concern", 160), ("risk", "Risk", 80),
        ("pathway", "Pathway", 170), ("status", "Status", 160),
        ("outcome", "Outcome", 120),
    ]:
        tree.heading(c, text=label)
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True)
    tree.tag_configure("imminent", background="#fde7e7")
    tree.tag_configure("high",     background="#ffe4b3")
    tree.tag_configure("closed",   foreground="#888")

    def _refresh() -> None:
        for i in tree.get_children():
            tree.delete(i)
        try:
            rows = data.list_referrals(
                status=status_var.get().strip() or None,
                risk_level=risk_var.get().strip() or None,
                open_only=open_only_var.get(),
            )
        except ValidationError as e:
            messagebox.showerror("Prevent Duty", str(e),
                                   parent=host.root)
            return
        except Exception as e:
            logger.exception("prevent_duty refresh failed")
            messagebox.showerror("Prevent Duty",
                                   f"Could not load:\n\n{e}",
                                   parent=host.root)
            return
        for r in rows:
            pupil = f"{r.pupil_id} ({r.pupil_name or '-'})"
            tags = []
            if r.risk_level == "Imminent":
                tags.append("imminent")
            elif r.risk_level == "High":
                tags.append("high")
            if r.status.startswith("Closed"):
                tags.append("closed")
            tree.insert("", "end", iid=str(r.referral_id), values=(
                r.referral_id, pupil, r.pupil_year or "-",
                r.raised_date, r.concern_type, r.risk_level,
                r.referral_pathway, r.status, r.outcome,
            ), tags=tuple(tags))
        try:
            s = data.cohort_summary()
            summary_var.set(
                f"Referrals: {s['total']}    Open: {s['open']}    "
                f"High-risk: {s['high_risk']}    "
                f"Channel: {s['channel']}    "
                f"Police: {s['police']}    "
                f"Pupils: {s['pupils']}")
        except Exception:
            summary_var.set(f"{len(rows)} referral(s)")
        host.status_var.set(
            f"Prevent Duty: {len(rows)} record(s)")

    tree.bind("<Double-1>",
                lambda _e: _edit(host, tree, on_done=_refresh))
    status_var.trace_add("write", lambda *_: _refresh())
    risk_var.trace_add("write", lambda *_: _refresh())
    open_only_var.trace_add("write", lambda *_: _refresh())
    _refresh()


def _selected_id(tree: ttk.Treeview, host) -> int | None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Prevent Duty",
                              "Select a referral first.",
                              parent=host.root)
        return None
    try:
        return int(sel)
    except ValueError:
        return None


@_safe_view
def _new(host, *, on_done=None) -> None:
    fields = _referral_dialog(host, "New Prevent referral")
    if not fields:
        return
    r = data.create(fields)
    messagebox.showinfo(
        "Prevent Duty",
        f"Created referral #{r.referral_id}: {r.pupil_id} — "
        f"{r.concern_type} ({r.risk_level})",
        parent=host.root,
    )
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
    initial = {k: getattr(existing, k) for k in (
        "pupil_id", "concern_type", "risk_level", "raised_by",
        "raised_date", "dsl_informed", "dsl_name",
        "dsl_informed_date", "description", "indicators",
        "online_activity", "referral_pathway", "referral_date",
        "referral_ref", "agencies_involved", "parents_informed",
        "parents_informed_date", "next_review_date", "status",
        "outcome", "closed_date", "closure_notes", "notes")}
    fields = _referral_dialog(host, f"Edit referral #{rid}",
                                 initial=initial)
    if not fields:
        return
    data.update(rid, fields)
    if on_done:
        on_done()


@_safe_view
def _close(host, tree: ttk.Treeview, *, on_done=None) -> None:
    rid = _selected_id(tree, host)
    if rid is None:
        return
    closed_statuses = [s for s in STATUSES if s.startswith("Closed")]

    dlg = tk.Toplevel(host.root)
    dlg.title(f"Close referral #{rid}")
    dlg.transient(host.root)
    dlg.geometry("420x260")
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        pass
    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)
    ttk.Label(frm, text="Closed status:").grid(row=0, column=0, sticky="w")
    status_var = tk.StringVar(value=closed_statuses[0])
    ttk.Combobox(frm, textvariable=status_var,
                   values=closed_statuses, state="readonly",
                   width=28).grid(row=0, column=1, sticky="w")
    ttk.Label(frm, text="Outcome:").grid(row=1, column=0, sticky="w",
                                          pady=4)
    outcome_var = tk.StringVar(value="No further action")
    ttk.Combobox(frm, textvariable=outcome_var,
                   values=list(OUTCOMES), state="readonly",
                   width=22).grid(row=1, column=1, sticky="w")
    ttk.Label(frm, text="Closure notes:").grid(row=2, column=0,
                                                sticky="nw")
    notes_t = tk.Text(frm, width=40, height=6, wrap="word")
    notes_t.grid(row=2, column=1, sticky="ew")
    frm.columnconfigure(1, weight=1)

    done = {"ok": False}

    def _ok() -> None:
        done["ok"] = True
        dlg.destroy()

    btns = ttk.Frame(frm)
    btns.grid(row=3, column=0, columnspan=2, sticky="e", pady=(8, 0))
    ttk.Button(btns, text="Cancel",
                 command=dlg.destroy).pack(side="right", padx=4)
    ttk.Button(btns, text="Close referral",
                 command=_ok).pack(side="right")
    dlg.wait_window()
    if not done["ok"]:
        return
    data.close_referral(
        rid,
        status=status_var.get().strip(),
        outcome=outcome_var.get().strip(),
        closure_notes=notes_t.get("1.0", "end").strip() or None,
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
            "Delete referral",
            f"Delete referral #{rid} ({existing.pupil_id}, "
            f"{existing.concern_type})?",
            parent=host.root):
        return
    data.delete(rid)
    if on_done:
        on_done()
