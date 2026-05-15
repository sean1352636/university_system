"""Tk views for medical records."""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable

from education_system.primarysch_system.modules.domain.medical_records import (
    medical_records as data,
)
from education_system.primarysch_system.modules.domain.medical_records.medical_records import (
    MedicalRecord, RECORD_TYPES, RECORD_TYPE_LABELS, SEVERITIES, SEVERITY_LABELS,
)
from education_system.primarysch_system.modules.domain.pupils import (
    pupils as pupils_data,
)
from education_system.primarysch_system.modules.domain.pupils.pupils import (
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
                messagebox.showerror("Medical Records", str(e),
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


@_safe_view
def open_medical(host) -> None:
    logger.debug("GUI: open_medical")

    win = tk.Toplevel(host.root)
    win.title("Medical Records")
    win.transient(host.root)
    win.geometry("1180x640")

    top = ttk.Frame(win, padding=10)
    top.pack(fill="x")
    summary_var = tk.StringVar()
    ttk.Label(top, textvariable=summary_var,
              font=("Segoe UI", 10, "bold")).pack(side="left")

    filt = ttk.Frame(win, padding=(10, 0, 10, 6))
    filt.pack(fill="x")
    ttk.Label(filt, text="Type:").pack(side="left")
    type_var = tk.StringVar(value="All")
    ttk.Combobox(filt, textvariable=type_var,
                 values=["All"] + list(RECORD_TYPES),
                 state="readonly", width=12).pack(side="left", padx=(4, 10))
    ttk.Label(filt, text="Severity:").pack(side="left")
    sev_var = tk.StringVar(value="All")
    ttk.Combobox(filt, textvariable=sev_var,
                 values=["All"] + list(SEVERITIES),
                 state="readonly", width=10).pack(side="left", padx=(4, 10))
    ttk.Label(filt, text="Year:").pack(side="left")
    py_var = tk.StringVar(value="All")
    ttk.Combobox(filt, textvariable=py_var,
                 values=["All"] + list(YEAR_GROUPS),
                 state="readonly", width=6).pack(side="left", padx=(4, 10))
    active_var = tk.BooleanVar(value=True)
    ttk.Checkbutton(filt, text="Active only",
                    variable=active_var).pack(side="left")
    critical_var = tk.BooleanVar(value=False)
    ttk.Checkbutton(filt, text="Critical only",
                    variable=critical_var).pack(side="left", padx=(8, 0))
    ttk.Label(filt, text="Search:").pack(side="left", padx=(10, 0))
    search_var = tk.StringVar()
    ttk.Entry(filt, textvariable=search_var, width=22).pack(
        side="left", padx=(4, 0))

    cols = ("record_id", "pupil_id", "name", "year", "record_type",
            "severity", "title", "active", "contact")
    tree = ttk.Treeview(win, columns=cols, show="headings", height=16)
    for col, label, width, anchor in [
        ("record_id", "#", 50, "center"),
        ("pupil_id", "Pupil ID", 90, "w"),
        ("name", "Name", 180, "w"),
        ("year", "Yr", 40, "center"),
        ("record_type", "Type", 110, "w"),
        ("severity", "Severity", 90, "center"),
        ("title", "Title", 260, "w"),
        ("active", "Active", 70, "center"),
        ("contact", "Contact", 220, "w"),
    ]:
        tree.heading(col, text=label)
        tree.column(col, width=width, anchor=anchor)
    tree.tag_configure("critical", background="#fdecea", foreground="#a32118")
    tree.tag_configure("high", background="#fff4e5")
    tree.pack(fill="both", expand=True, padx=10, pady=(0, 6))

    btns = ttk.Frame(win, padding=10)
    btns.pack(fill="x")

    def _refresh() -> None:
        try:
            rt = None if type_var.get() == "All" else type_var.get()
            sev = None if sev_var.get() == "All" else sev_var.get()
            py = None if py_var.get() == "All" else py_var.get()
            rows = data.list_records(
                record_type=rt, severity=sev, year_group=py,
                active_only=active_var.get(),
                critical_only=critical_var.get(),
                search=search_var.get().strip() or None,
            )
        except ValidationError as e:
            messagebox.showerror("Medical Records", str(e), parent=win)
            return
        except Exception:
            logger.exception("medical refresh failed")
            messagebox.showerror("Error", "Could not load — see logs.",
                                 parent=win)
            return
        for iid in tree.get_children():
            tree.delete(iid)
        for rec, p in rows:
            tags = ()
            if rec.severity == "critical":
                tags = ("critical",)
            elif rec.severity == "high":
                tags = ("high",)
            contact = ""
            if rec.contact_name or rec.contact_phone:
                contact = f"{rec.contact_name or ''} {rec.contact_phone or ''}".strip()
            tree.insert("", "end", iid=str(rec.record_id), values=(
                rec.record_id, rec.pupil_id,
                p.full_name if p else "(unknown)",
                p.year_group if p else "-",
                rec.record_type, rec.severity, rec.title,
                "yes" if rec.is_active else "no",
                contact,
            ), tags=tags)
        try:
            s = data.summary()
        except Exception:
            s = {"total": 0, "active": 0, "critical_active": 0,
                 "pupils_with_records": 0}
        summary_var.set(
            f"Active: {s['active']}/{s['total']}   "
            f"Critical (active): {s['critical_active']}   "
            f"Pupils with records: {s['pupils_with_records']}   "
            f"Showing: {len(rows)}"
        )

    def _selected_id() -> int | None:
        sel = tree.selection()
        if not sel:
            messagebox.showinfo("Medical Records",
                                "Select a record first.", parent=win)
            return None
        return int(sel[0])

    def _add() -> None:
        _open_form_dialog(win, record_id=None, on_saved=_refresh)

    def _edit() -> None:
        rid = _selected_id()
        if rid is None:
            return
        _open_form_dialog(win, record_id=rid, on_saved=_refresh)

    def _view() -> None:
        rid = _selected_id()
        if rid is None:
            return
        _open_view_dialog(win, rid)

    def _toggle() -> None:
        rid = _selected_id()
        if rid is None:
            return
        try:
            data.toggle_active(rid)
        except Exception:
            logger.exception("toggle_active(%s) failed", rid)
            messagebox.showerror("Error", "Could not toggle — see logs.",
                                 parent=win)
            return
        _refresh()

    def _delete() -> None:
        rid = _selected_id()
        if rid is None:
            return
        if not messagebox.askyesno(
                "Delete record",
                f"Delete medical record #{rid}? This cannot be undone.",
                parent=win):
            return
        try:
            data.delete(rid)
        except Exception:
            logger.exception("delete(%s) failed", rid)
            messagebox.showerror("Error", "Could not delete — see logs.",
                                 parent=win)
            return
        _refresh()

    def _help() -> None:
        msg = "Types:\n" + "\n".join(
            f"{t}  —  {RECORD_TYPE_LABELS[t]}" for t in RECORD_TYPES)
        msg += "\n\nSeverities:\n" + "\n".join(
            f"{s}  —  {SEVERITY_LABELS[s]}" for s in SEVERITIES)
        messagebox.showinfo("Medical Records", msg, parent=win)

    ttk.Button(btns, text="New record", command=_add).pack(side="left")
    ttk.Button(btns, text="Edit", command=_edit).pack(
        side="left", padx=(8, 0))
    ttk.Button(btns, text="View...", command=_view).pack(
        side="left", padx=(8, 0))
    ttk.Button(btns, text="Toggle active", command=_toggle).pack(
        side="left", padx=(8, 0))
    ttk.Button(btns, text="Delete", command=_delete).pack(
        side="left", padx=(8, 0))
    ttk.Button(btns, text="Help", command=_help).pack(
        side="left", padx=(8, 0))
    ttk.Button(btns, text="Refresh", command=_refresh).pack(
        side="left", padx=(8, 0))
    ttk.Button(btns, text="Close", command=win.destroy).pack(side="right")

    tree.bind("<Double-Button-1>", lambda _e: _view())
    for v in (type_var, sev_var, py_var, active_var, critical_var, search_var):
        v.trace_add("write", lambda *_: _refresh())

    _refresh()


def _set_text(text: tk.Text, value: str | None) -> None:
    text.delete("1.0", "end")
    if value:
        text.insert("1.0", value)


def _get_text(text: tk.Text) -> str:
    return text.get("1.0", "end").strip()


def _open_form_dialog(parent, *, record_id: int | None,
                      on_saved: Callable[[], None]) -> None:
    existing: MedicalRecord | None = None
    if record_id is not None:
        try:
            existing = data.get(record_id)
        except Exception:
            logger.exception("get(%s) failed", record_id)
            messagebox.showerror("Error", "Could not load — see logs.",
                                 parent=parent)
            return
        if existing is None:
            messagebox.showerror("Medical Records",
                                 f"No record #{record_id}", parent=parent)
            return

    dlg = tk.Toplevel(parent)
    dlg.title("Medical record" if existing else "New medical record")
    dlg.transient(parent)
    dlg.geometry("640x640")
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped", exc_info=True)

    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    pupil_var = tk.StringVar(value=existing.pupil_id if existing else "")
    pupil_label = tk.StringVar(value="")
    ttk.Label(frm, text="Pupil ID *").grid(row=0, column=0, sticky="w", pady=3)
    ttk.Entry(frm, textvariable=pupil_var, width=14).grid(
        row=0, column=1, sticky="w", pady=3)
    ttk.Label(frm, textvariable=pupil_label, foreground="#666").grid(
        row=0, column=2, sticky="w", padx=(8, 0))

    def _lookup_pupil(*_a) -> None:
        pid = pupil_var.get().strip()
        if not pid:
            pupil_label.set("")
            return
        try:
            p = pupils_data.get_pupil(pid)
        except Exception:
            pupil_label.set("(error)")
            return
        pupil_label.set(
            f"{p.full_name} (year {p.year_group})" if p else "(unknown)")
    pupil_var.trace_add("write", _lookup_pupil)
    _lookup_pupil()

    ttk.Label(frm, text="Type *").grid(row=1, column=0, sticky="w", pady=3)
    type_var = tk.StringVar(
        value=existing.record_type if existing else RECORD_TYPES[0])
    ttk.Combobox(frm, textvariable=type_var, values=list(RECORD_TYPES),
                 state="readonly", width=14).grid(
        row=1, column=1, sticky="w", pady=3)

    ttk.Label(frm, text="Title *").grid(row=2, column=0, sticky="w", pady=3)
    title_var = tk.StringVar(value=existing.title if existing else "")
    ttk.Entry(frm, textvariable=title_var, width=46).grid(
        row=2, column=1, columnspan=2, sticky="ew", pady=3)

    ttk.Label(frm, text="Severity *").grid(row=3, column=0, sticky="w", pady=3)
    sev_var = tk.StringVar(value=existing.severity if existing else "low")
    ttk.Combobox(frm, textvariable=sev_var, values=list(SEVERITIES),
                 state="readonly", width=10).grid(
        row=3, column=1, sticky="w", pady=3)

    ttk.Label(frm, text="Start date (YYYY-MM-DD)").grid(
        row=4, column=0, sticky="w", pady=3)
    sd_var = tk.StringVar(value=existing.start_date or "" if existing else "")
    ttk.Entry(frm, textvariable=sd_var, width=14).grid(
        row=4, column=1, sticky="w", pady=3)

    ttk.Label(frm, text="End date (YYYY-MM-DD)").grid(
        row=5, column=0, sticky="w", pady=3)
    ed_var = tk.StringVar(value=existing.end_date or "" if existing else "")
    ttk.Entry(frm, textvariable=ed_var, width=14).grid(
        row=5, column=1, sticky="w", pady=3)

    ttk.Label(frm, text="Contact name").grid(
        row=6, column=0, sticky="w", pady=3)
    cn_var = tk.StringVar(
        value=existing.contact_name or "" if existing else "")
    ttk.Entry(frm, textvariable=cn_var, width=30).grid(
        row=6, column=1, sticky="w", pady=3)

    ttk.Label(frm, text="Contact phone").grid(
        row=7, column=0, sticky="w", pady=3)
    cp_var = tk.StringVar(
        value=existing.contact_phone or "" if existing else "")
    ttk.Entry(frm, textvariable=cp_var, width=20).grid(
        row=7, column=1, sticky="w", pady=3)

    active_var = tk.BooleanVar(value=existing.is_active if existing else True)
    ttk.Checkbutton(frm, text="Active",
                    variable=active_var).grid(
        row=8, column=1, sticky="w", pady=3)

    ttk.Label(frm, text="Description").grid(
        row=9, column=0, sticky="nw", pady=(8, 0))
    desc_text = tk.Text(frm, height=4, width=60, wrap="word")
    desc_text.grid(row=9, column=1, columnspan=2, sticky="nsew", pady=(8, 0))
    _set_text(desc_text, existing.description if existing else None)

    ttk.Label(frm, text="Action plan").grid(
        row=10, column=0, sticky="nw", pady=(8, 0))
    plan_text = tk.Text(frm, height=4, width=60, wrap="word")
    plan_text.grid(row=10, column=1, columnspan=2, sticky="nsew", pady=(8, 0))
    _set_text(plan_text, existing.action_plan if existing else None)

    ttk.Label(frm, text="Notes").grid(row=11, column=0, sticky="w", pady=3)
    notes_var = tk.StringVar(value=existing.notes or "" if existing else "")
    ttk.Entry(frm, textvariable=notes_var, width=46).grid(
        row=11, column=1, columnspan=2, sticky="ew", pady=3)

    frm.columnconfigure(1, weight=1)
    frm.columnconfigure(2, weight=1)
    frm.rowconfigure(9, weight=1)
    frm.rowconfigure(10, weight=1)

    def _save() -> None:
        payload = {
            "pupil_id": pupil_var.get(),
            "record_type": type_var.get(),
            "title": title_var.get(),
            "description": _get_text(desc_text),
            "severity": sev_var.get(),
            "start_date": sd_var.get(),
            "end_date": ed_var.get(),
            "action_plan": _get_text(plan_text),
            "contact_name": cn_var.get(),
            "contact_phone": cp_var.get(),
            "is_active": active_var.get(),
            "notes": notes_var.get(),
        }
        try:
            if existing is None:
                data.create(payload)
            else:
                data.update(existing.record_id, payload)
        except ValidationError as e:
            messagebox.showerror("Medical Records", str(e), parent=dlg)
            return
        except Exception:
            logger.exception("save medical failed")
            messagebox.showerror("Error", "Could not save — see logs.",
                                 parent=dlg)
            return
        on_saved()
        dlg.destroy()

    btn_row = ttk.Frame(frm)
    btn_row.grid(row=12, column=0, columnspan=3, sticky="ew", pady=(14, 0))
    ttk.Button(btn_row, text="Save", command=_save).pack(side="right")
    ttk.Button(btn_row, text="Cancel",
               command=dlg.destroy).pack(side="right", padx=(0, 8))


def _open_view_dialog(parent, record_id: int) -> None:
    try:
        rec = data.get(record_id)
    except Exception:
        logger.exception("get(%s) failed", record_id)
        messagebox.showerror("Error", "Could not load — see logs.",
                             parent=parent)
        return
    if rec is None:
        messagebox.showerror("Medical Records",
                             f"No record #{record_id}", parent=parent)
        return

    dlg = tk.Toplevel(parent)
    dlg.title(f"Medical record #{rec.record_id}")
    dlg.transient(parent)
    dlg.geometry("620x560")
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped", exc_info=True)

    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    header = (f"Pupil {rec.pupil_id}  —  {RECORD_TYPE_LABELS[rec.record_type]}  "
              f"—  Severity: {rec.severity}")
    colour = "#a32118" if rec.is_critical else "#222"
    ttk.Label(frm, text=header,
              font=("Segoe UI", 11, "bold"),
              foreground=colour).pack(anchor="w")
    ttk.Label(frm,
              text=f"Title: {rec.title}",
              font=("Segoe UI", 10, "italic"),
              wraplength=580).pack(anchor="w", pady=(2, 4))
    line = (f"{'ACTIVE' if rec.is_active else 'INACTIVE'}   "
            f"{rec.start_date or '-'} -> {rec.end_date or '-'}   "
            f"Contact: {rec.contact_name or '-'} "
            f"{rec.contact_phone or ''}")
    ttk.Label(frm, text=line, foreground="#444").pack(anchor="w", pady=(0, 8))

    text = tk.Text(frm, wrap="word", height=20)
    text.pack(fill="both", expand=True)
    text.tag_configure("h", font=("Segoe UI", 10, "bold"),
                       spacing1=4, spacing3=2)

    def _section(title: str, body: str | None) -> None:
        text.insert("end", f"{title}\n", "h")
        text.insert("end", (body or "—") + "\n\n")

    _section("Description", rec.description)
    _section("Action plan", rec.action_plan)
    if rec.notes:
        _section("Notes", rec.notes)
    text.config(state="disabled")

    ttk.Button(frm, text="Close",
               command=dlg.destroy).pack(anchor="e", pady=(10, 0))
