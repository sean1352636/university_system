"""Tk views for first-aid incidents."""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable

from education_system.primarysch_system.modules.domain.first_aid import (
    first_aid as data,
)
from education_system.primarysch_system.modules.domain.first_aid.first_aid import (
    INJURY_TYPES, SEVERITIES, OUTCOMES,
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
                messagebox.showerror("First Aid", str(e),
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


def _incident_dialog(host, title: str,
                       initial: dict[str, Any] | None = None
                       ) -> dict[str, Any] | None:
    dlg = tk.Toplevel(host.root)
    dlg.title(title)
    dlg.transient(host.root)
    dlg.geometry("560x760")
    dlg.update_idletasks()
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped", exc_info=True)

    initial = initial or {}
    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    pupil_var    = tk.StringVar(value=str(initial.get("pupil_id") or ""))
    date_var     = tk.StringVar(value=str(initial.get("incident_date") or ""))
    time_var     = tk.StringVar(value=str(initial.get("incident_time") or ""))
    loc_var      = tk.StringVar(value=str(initial.get("location") or ""))
    injury_var   = tk.StringVar(value=str(initial.get("injury_type")
                                              or "Bump/Bruise"))
    sev_var      = tk.StringVar(value=str(initial.get("severity")
                                              or "Minor"))
    body_var     = tk.StringVar(value=str(initial.get("body_part") or ""))
    treated_var  = tk.StringVar(value=str(initial.get("treated_by") or ""))
    outcome_var  = tk.StringVar(value=str(initial.get("outcome")
                                              or "Returned to lesson"))
    abr_var      = tk.StringVar(value=str(initial.get("accident_book_ref")
                                              or ""))
    pct_var      = tk.StringVar(value=str(initial.get("parent_contact_time")
                                              or ""))
    pc_var       = tk.BooleanVar(value=bool(initial.get("parent_contacted")))
    hosp_var     = tk.BooleanVar(value=bool(initial.get("hospital_referral")))
    riddor_var   = tk.BooleanVar(value=bool(initial.get("riddor_reportable")))

    rows: list[tuple[str, tk.Widget]] = [
        ("Pupil ID:",     ttk.Entry(frm, textvariable=pupil_var, width=14)),
        ("Date:",         ttk.Entry(frm, textvariable=date_var, width=14)),
        ("Time:",         ttk.Entry(frm, textvariable=time_var, width=8)),
        ("Location:",     ttk.Entry(frm, textvariable=loc_var, width=28)),
        ("Injury type:",  ttk.Combobox(frm, textvariable=injury_var,
                                          values=list(INJURY_TYPES),
                                          state="readonly", width=24)),
        ("Severity:",     ttk.Combobox(frm, textvariable=sev_var,
                                          values=list(SEVERITIES),
                                          state="readonly", width=14)),
        ("Body part:",    ttk.Entry(frm, textvariable=body_var, width=22)),
        ("Treated by:",   ttk.Entry(frm, textvariable=treated_var, width=28)),
        ("Outcome:",      ttk.Combobox(frm, textvariable=outcome_var,
                                          values=list(OUTCOMES),
                                          state="readonly", width=24)),
        ("Parent contacted:", ttk.Checkbutton(frm, variable=pc_var)),
        ("Parent contact time:", ttk.Entry(frm, textvariable=pct_var,
                                              width=8)),
        ("Hospital referral:", ttk.Checkbutton(frm, variable=hosp_var)),
        ("Accident book #:", ttk.Entry(frm, textvariable=abr_var, width=14)),
        ("RIDDOR reportable:", ttk.Checkbutton(frm, variable=riddor_var)),
    ]
    for i, (label, widget) in enumerate(rows):
        ttk.Label(frm, text=label).grid(row=i, column=0, sticky="w",
                                          pady=2)
        widget.grid(row=i, column=1, sticky="w", pady=2)
    frm.columnconfigure(1, weight=1)

    text_fields = [("Description:", "description", 3),
                    ("Treatment:",   "treatment", 3),
                    ("Follow-up:",   "follow_up", 2),
                    ("Notes:",       "notes", 2)]
    text_widgets: dict[str, tk.Text] = {}
    for i, (label, key, lines) in enumerate(text_fields,
                                              start=len(rows)):
        ttk.Label(frm, text=label).grid(row=i, column=0, sticky="nw",
                                          pady=2)
        t = tk.Text(frm, width=46, height=lines, wrap="word")
        t.insert("1.0", str(initial.get(key) or ""))
        t.grid(row=i, column=1, sticky="ew", pady=2)
        text_widgets[key] = t

    result: dict[str, Any] | None = None

    def _save() -> None:
        nonlocal result
        result = {
            "pupil_id":         pupil_var.get().strip(),
            "incident_date":    date_var.get().strip(),
            "incident_time":    time_var.get().strip(),
            "location":         loc_var.get().strip(),
            "injury_type":      injury_var.get().strip(),
            "severity":         sev_var.get().strip(),
            "body_part":        body_var.get().strip(),
            "treated_by":       treated_var.get().strip(),
            "outcome":          outcome_var.get().strip(),
            "parent_contacted": bool(pc_var.get()),
            "parent_contact_time": pct_var.get().strip(),
            "hospital_referral": bool(hosp_var.get()),
            "accident_book_ref": abr_var.get().strip(),
            "riddor_reportable": bool(riddor_var.get()),
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
def open_first_aid(host) -> None:
    logger.debug("GUI: open_first_aid")
    host._clear_content()
    root = host.content_frame
    ttk.Label(root, text="First Aid",
                font=("", 16, "bold")).pack(anchor="w", pady=(0, 8))

    summary_var = tk.StringVar()
    ttk.Label(root, textvariable=summary_var,
                foreground="#666").pack(anchor="w", pady=(0, 8))

    bar = ttk.Frame(root)
    bar.pack(fill="x", pady=(0, 6))
    ttk.Label(bar, text="Severity:").pack(side="left", padx=(0, 4))
    sev_var = tk.StringVar(value="")
    ttk.Combobox(bar, textvariable=sev_var,
                   values=["", *SEVERITIES], state="readonly",
                   width=10).pack(side="left", padx=(0, 6))
    riddor_var = tk.BooleanVar(value=False)
    ttk.Checkbutton(bar, text="RIDDOR only",
                       variable=riddor_var).pack(side="left", padx=4)
    hosp_var = tk.BooleanVar(value=False)
    ttk.Checkbutton(bar, text="Hospital only",
                       variable=hosp_var).pack(side="left", padx=4)
    ttk.Button(bar, text="Apply",
                  command=lambda: _refresh()).pack(side="left", padx=2)
    ttk.Button(bar, text="New",
                  command=lambda: _new(host, on_done=_refresh)
                  ).pack(side="left", padx=2)
    ttk.Button(bar, text="Edit",
                  command=lambda: _edit(host, tree, on_done=_refresh)
                  ).pack(side="left", padx=2)
    ttk.Button(bar, text="Delete",
                  command=lambda: _delete(host, tree, on_done=_refresh)
                  ).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
                  command=lambda: _refresh()).pack(side="left", padx=2)

    cols = ("id", "date", "time", "pupil", "yr", "injury",
              "sev", "outcome", "pc", "hosp", "riddor")
    tree = ttk.Treeview(root, columns=cols, show="headings", height=18)
    for c, label, w in [
        ("id", "ID", 50), ("date", "Date", 90),
        ("time", "Time", 60), ("pupil", "Pupil", 180),
        ("yr", "Yr", 40), ("injury", "Injury", 150),
        ("sev", "Severity", 80), ("outcome", "Outcome", 170),
        ("pc", "P", 30), ("hosp", "H", 30), ("riddor", "R", 30),
    ]:
        tree.heading(c, text=label)
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True)
    tree.tag_configure("severe",   background="#ffe4b3")
    tree.tag_configure("critical", background="#fde7e7")
    tree.tag_configure("riddor",   foreground="#c00000")

    def _refresh() -> None:
        for i in tree.get_children():
            tree.delete(i)
        try:
            rows = data.list_incidents(
                severity=sev_var.get().strip() or None,
                riddor_only=riddor_var.get(),
                hospital_only=hosp_var.get(),
            )
        except ValidationError as e:
            messagebox.showerror("First Aid", str(e),
                                   parent=host.root)
            return
        except Exception as e:
            logger.exception("first_aid refresh failed")
            messagebox.showerror("First Aid",
                                   f"Could not load:\n\n{e}",
                                   parent=host.root)
            return
        for r in rows:
            pupil = f"{r.pupil_id} ({r.pupil_name or '-'})"
            tags = []
            if r.severity == "Critical":
                tags.append("critical")
            elif r.severity == "Severe":
                tags.append("severe")
            if r.riddor_reportable:
                tags.append("riddor")
            tree.insert("", "end", iid=str(r.incident_id), values=(
                r.incident_id, r.incident_date,
                r.incident_time or "-", pupil, r.pupil_year or "-",
                r.injury_type, r.severity, r.outcome,
                "✓" if r.parent_contacted else "",
                "✓" if r.hospital_referral else "",
                "✓" if r.riddor_reportable else "",
            ), tags=tuple(tags))
        try:
            s = data.cohort_summary()
            summary_var.set(
                f"Incidents: {s['total']}    "
                f"Pupils: {s['pupils']}    "
                f"Hospital: {s['hospital']}    "
                f"RIDDOR: {s['riddor']}    "
                f"Parent contacted: {s['parent_contacted']}")
        except Exception:
            summary_var.set(f"{len(rows)} incident(s)")
        host.status_var.set(
            f"First Aid: {len(rows)} record(s)")

    tree.bind("<Double-1>",
                lambda _e: _edit(host, tree, on_done=_refresh))
    sev_var.trace_add("write", lambda *_: _refresh())
    riddor_var.trace_add("write", lambda *_: _refresh())
    hosp_var.trace_add("write", lambda *_: _refresh())
    _refresh()


def _selected_id(tree: ttk.Treeview, host) -> int | None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("First Aid",
                              "Select an incident first.",
                              parent=host.root)
        return None
    try:
        return int(sel)
    except ValueError:
        return None


@_safe_view
def _new(host, *, on_done=None) -> None:
    fields = _incident_dialog(host, "New first-aid incident")
    if not fields:
        return
    r = data.create(fields)
    messagebox.showinfo(
        "First Aid",
        f"Created incident #{r.incident_id}: {r.pupil_id} — "
        f"{r.injury_type} ({r.severity})",
        parent=host.root,
    )
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
        "pupil_id", "incident_date", "incident_time", "location",
        "injury_type", "severity", "body_part", "description",
        "treatment", "treated_by", "outcome", "parent_contacted",
        "parent_contact_time", "hospital_referral",
        "accident_book_ref", "riddor_reportable",
        "follow_up", "notes")}
    fields = _incident_dialog(host, f"Edit incident #{iid}",
                                initial=initial)
    if not fields:
        return
    data.update(iid, fields)
    if on_done:
        on_done()


@_safe_view
def _delete(host, tree: ttk.Treeview, *, on_done=None) -> None:
    iid = _selected_id(tree, host)
    if iid is None:
        return
    existing = data.get(iid)
    if existing is None:
        return
    if not messagebox.askyesno(
            "Delete incident",
            f"Delete incident #{iid} ({existing.pupil_id}, "
            f"{existing.injury_type})?",
            parent=host.root):
        return
    data.delete(iid)
    if on_done:
        on_done()
