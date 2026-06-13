"""Tk views for form-tutor assignments and meetings."""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import Any, Callable

from education_system.secondarysch_system.modules.domain.pastoral.form_tutors import (
    form_tutors as data,
)
from education_system.secondarysch_system.modules.domain.pastoral.form_tutors.form_tutors import (
    ROLES, ASSIGNMENT_STATUSES, MEETING_TYPES,
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
                messagebox.showerror("Form Tutors", str(e),
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


def _assignment_dialog(host, title: str,
                        initial: dict[str, Any] | None = None
                        ) -> dict[str, Any] | None:
    dlg = tk.Toplevel(host.root)
    dlg.title(title)
    dlg.transient(host.root)
    dlg.geometry("480x460")
    dlg.update_idletasks()
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped — dialog not viewable", exc_info=True)

    initial = initial or {}
    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    year_var   = tk.StringVar(value=str(initial.get("year_group")
                                          or "7"))
    form_var   = tk.StringVar(value=str(initial.get("form_group")
                                          or ""))
    ay_var     = tk.StringVar(value=str(initial.get("academic_year")
                                          or ""))
    tutor_var  = tk.StringVar(value=str(initial.get("tutor_name")
                                          or ""))
    role_var   = tk.StringVar(value=str(initial.get("role") or "Tutor"))
    email_var  = tk.StringVar(value=str(initial.get("contact_email")
                                          or ""))
    start_var  = tk.StringVar(value=str(initial.get("start_date") or ""))
    end_var    = tk.StringVar(value=str(initial.get("end_date") or ""))
    status_var = tk.StringVar(value=str(initial.get("status")
                                          or "Active"))

    rows: list[tuple[str, tk.Widget]] = [
        ("Year:",         ttk.Combobox(frm, textvariable=year_var,
                                        values=list(YEAR_GROUPS),
                                        state="readonly", width=8)),
        ("Form:",         ttk.Entry(frm, textvariable=form_var,
                                      width=12)),
        ("Academic year:", ttk.Entry(frm, textvariable=ay_var,
                                       width=10)),
        ("Tutor:",        ttk.Entry(frm, textvariable=tutor_var,
                                      width=28)),
        ("Role:",         ttk.Combobox(frm, textvariable=role_var,
                                        values=list(ROLES),
                                        state="readonly", width=12)),
        ("Email:",        ttk.Entry(frm, textvariable=email_var,
                                      width=30)),
        ("Start date:",   ttk.Entry(frm, textvariable=start_var,
                                      width=14)),
        ("End date:",     ttk.Entry(frm, textvariable=end_var,
                                      width=14)),
        ("Status:",       ttk.Combobox(frm, textvariable=status_var,
                                        values=list(ASSIGNMENT_STATUSES),
                                        state="readonly", width=14)),
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

    def _save() -> None:
        nonlocal result
        result = {
            "year_group":    year_var.get().strip(),
            "form_group":    form_var.get().strip(),
            "academic_year": ay_var.get().strip(),
            "tutor_name":    tutor_var.get().strip(),
            "role":          role_var.get().strip(),
            "contact_email": email_var.get().strip(),
            "start_date":    start_var.get().strip(),
            "end_date":      end_var.get().strip(),
            "status":        status_var.get().strip(),
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


def _meeting_dialog(host, assignment_id: int,
                     initial: dict[str, Any] | None = None
                     ) -> dict[str, Any] | None:
    dlg = tk.Toplevel(host.root)
    dlg.title(f"Meeting — assignment #{assignment_id}")
    dlg.transient(host.root)
    dlg.geometry("520x540")
    dlg.update_idletasks()
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        pass

    initial = initial or {}
    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    date_var = tk.StringVar(value=str(initial.get("meeting_date") or ""))
    type_var = tk.StringVar(value=str(initial.get("meeting_type")
                                         or "Form time"))
    pupils_var = tk.StringVar(value=str(initial.get("pupils_present")
                                           or ""))

    rows: list[tuple[str, tk.Widget]] = [
        ("Date:",    ttk.Entry(frm, textvariable=date_var, width=14)),
        ("Type:",    ttk.Combobox(frm, textvariable=type_var,
                                    values=list(MEETING_TYPES),
                                    state="readonly", width=18)),
        ("Pupils present:", ttk.Entry(frm, textvariable=pupils_var,
                                         width=40)),
    ]
    for label, widget in rows:
        row = ttk.Frame(frm)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text=label, width=16).pack(side="left")
        widget.pack(in_=row, side="left", padx=4)

    text_fields = [("Agenda:", "agenda", 3),
                   ("Decisions:", "decisions", 3),
                   ("Follow-up actions:", "follow_up_actions", 3),
                   ("Notes:", "notes", 2)]
    text_widgets: dict[str, tk.Text] = {}
    for label, key, lines in text_fields:
        ttk.Label(frm, text=label).pack(anchor="w", pady=(8, 0))
        t = tk.Text(frm, width=54, height=lines, wrap="word")
        t.insert("1.0", str(initial.get(key) or ""))
        t.pack(fill="x")
        text_widgets[key] = t

    result: dict[str, Any] | None = None

    def _save() -> None:
        nonlocal result
        result = {
            "assignment_id":  assignment_id,
            "meeting_date":   date_var.get().strip(),
            "meeting_type":   type_var.get().strip(),
            "pupils_present": pupils_var.get().strip(),
        }
        for k, w in text_widgets.items():
            result[k] = w.get("1.0", "end").strip()
        dlg.destroy()

    btns = ttk.Frame(frm)
    btns.pack(fill="x", pady=(10, 0))
    ttk.Button(btns, text="Cancel",
               command=dlg.destroy).pack(side="right", padx=4)
    ttk.Button(btns, text="Save", command=_save).pack(side="right")
    dlg.wait_window()
    return result


@_safe_view
def open_form_tutors(host) -> None:
    logger.debug("GUI: open_form_tutors")
    host._clear_content()
    root = host.content_frame
    ttk.Label(root, text="Form Tutors",
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
    ttk.Label(bar, text="Academic year:").pack(side="left", padx=(0, 4))
    ay_var = tk.StringVar(value="")
    ttk.Entry(bar, textvariable=ay_var, width=10).pack(
        side="left", padx=(0, 6))
    ttk.Label(bar, text="Status:").pack(side="left", padx=(0, 4))
    status_var = tk.StringVar(value="")
    ttk.Combobox(bar, textvariable=status_var,
                 values=["", *ASSIGNMENT_STATUSES], state="readonly",
                 width=12).pack(side="left", padx=(0, 6))
    ttk.Label(bar, text="Role:").pack(side="left", padx=(0, 4))
    role_var = tk.StringVar(value="")
    ttk.Combobox(bar, textvariable=role_var,
                 values=["", *ROLES], state="readonly",
                 width=10).pack(side="left", padx=(0, 8))
    ttk.Button(bar, text="Apply",
               command=lambda: _refresh()).pack(side="left", padx=2)
    ttk.Button(bar, text="New",
               command=lambda: _new(host, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Edit",
               command=lambda: _edit(host, tree, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="End",
               command=lambda: _end(host, tree, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Meetings",
               command=lambda: _open_meetings(host, tree)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Delete",
               command=lambda: _delete(host, tree, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: _refresh()).pack(side="left", padx=2)

    cols = ("id", "ay", "year", "form", "tutor", "role", "status",
            "start", "end")
    tree = ttk.Treeview(root, columns=cols, show="headings", height=18)
    for c, label, w in [
        ("id", "ID", 50), ("ay", "Academic yr", 90),
        ("year", "Yr", 50), ("form", "Form", 70),
        ("tutor", "Tutor", 220), ("role", "Role", 90),
        ("status", "Status", 100),
        ("start", "Start", 100), ("end", "End", 100),
    ]:
        tree.heading(c, text=label)
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True)

    def _refresh() -> None:
        for i in tree.get_children():
            tree.delete(i)
        try:
            rows = data.list_assignments(
                year_group=year_var.get().strip() or None,
                academic_year=ay_var.get().strip() or None,
                status=status_var.get().strip() or None,
                role=role_var.get().strip() or None,
            )
        except ValidationError as e:
            messagebox.showerror("Form Tutors", str(e),
                                 parent=host.root)
            return
        except Exception as e:
            logger.exception("form_tutors refresh failed")
            messagebox.showerror("Form Tutors",
                                 f"Could not load:\n\n{e}",
                                 parent=host.root)
            return
        for a in rows:
            tree.insert("", "end", iid=str(a.assignment_id), values=(
                a.assignment_id, a.academic_year, a.year_group,
                a.form_group, a.tutor_name, a.role, a.status,
                a.start_date, a.end_date or "-",
            ))
        try:
            s = data.cohort_summary(
                academic_year=ay_var.get().strip() or None)
            summary_var.set(
                f"Assignments: {s['total']}    "
                f"Tutors: {s['tutors']}    "
                f"Forms: {s['forms']}    "
                + "    ".join(f"{k}: {v}"
                                for k, v in s["by_status"].items()))
        except Exception:
            summary_var.set(f"{len(rows)} assignment(s)")
        host.status_var.set(f"Form Tutors: {len(rows)} record(s)")

    tree.bind("<Double-1>", lambda _e: _open_meetings(host, tree))
    year_var.trace_add("write", lambda *_: _refresh())
    status_var.trace_add("write", lambda *_: _refresh())
    role_var.trace_add("write", lambda *_: _refresh())
    _refresh()


def _selected_id(tree: ttk.Treeview, host) -> int | None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Form Tutors",
                            "Select an assignment first.",
                            parent=host.root)
        return None
    try:
        return int(sel)
    except ValueError:
        return None


@_safe_view
def _new(host, *, on_done=None) -> None:
    fields = _assignment_dialog(host, "New tutor assignment")
    if not fields:
        return
    a = data.create_assignment(fields)
    messagebox.showinfo(
        "Form Tutors",
        f"Assigned {a.tutor_name} to Yr{a.year_group}/{a.form_group} "
        f"({a.role}, {a.academic_year})",
        parent=host.root,
    )
    if on_done:
        on_done()


@_safe_view
def _edit(host, tree: ttk.Treeview, *, on_done=None) -> None:
    aid = _selected_id(tree, host)
    if aid is None:
        return
    existing = data.get_assignment(aid)
    if existing is None:
        return
    initial = {k: getattr(existing, k) for k in (
        "year_group", "form_group", "academic_year",
        "tutor_name", "role", "contact_email",
        "start_date", "end_date", "status", "notes")}
    fields = _assignment_dialog(host, f"Edit assignment #{aid}",
                                  initial=initial)
    if not fields:
        return
    data.update_assignment(aid, fields)
    if on_done:
        on_done()


@_safe_view
def _end(host, tree: ttk.Treeview, *, on_done=None) -> None:
    aid = _selected_id(tree, host)
    if aid is None:
        return
    existing = data.get_assignment(aid)
    if existing is None:
        return
    end_date = simpledialog.askstring(
        "End assignment",
        f"End date for {existing.tutor_name} "
        f"(YYYY-MM-DD, blank = today):",
        parent=host.root)
    if end_date is None:
        return
    data.end_assignment(aid, end_date=end_date.strip() or None)
    if on_done:
        on_done()


@_safe_view
def _delete(host, tree: ttk.Treeview, *, on_done=None) -> None:
    aid = _selected_id(tree, host)
    if aid is None:
        return
    existing = data.get_assignment(aid)
    if existing is None:
        return
    if not messagebox.askyesno(
            "Delete assignment",
            f"Delete {existing.tutor_name} from Yr{existing.year_group}"
            f"/{existing.form_group} and all logged meetings?",
            parent=host.root):
        return
    data.delete_assignment(aid)
    if on_done:
        on_done()


@_safe_view
def _open_meetings(host, tree: ttk.Treeview) -> None:
    aid = _selected_id(tree, host)
    if aid is None:
        return
    rec = data.get_assignment(aid)
    if rec is None:
        return

    dlg = tk.Toplevel(host.root)
    dlg.title(f"Meetings — Yr{rec.year_group}/{rec.form_group} "
              f"({rec.tutor_name})")
    dlg.transient(host.root)
    dlg.geometry("820x520")
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
    ttk.Button(bar, text="Log meeting",
               command=lambda: _do_add()).pack(side="left", padx=2)
    ttk.Button(bar, text="Edit",
               command=lambda: _do_edit()).pack(side="left", padx=2)
    ttk.Button(bar, text="Delete",
               command=lambda: _do_delete()).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: _refresh()).pack(side="left", padx=2)

    t = ttk.Treeview(frm,
                       columns=("id", "date", "type", "agenda",
                                 "follow_up"),
                       show="headings", height=14)
    for c, label, w in [
        ("id", "ID", 50), ("date", "Date", 100),
        ("type", "Type", 140), ("agenda", "Agenda", 280),
        ("follow_up", "Follow-up", 240),
    ]:
        t.heading(c, text=label)
        t.column(c, width=w, anchor="w")
    t.pack(fill="both", expand=True)

    def _refresh() -> None:
        for i in t.get_children():
            t.delete(i)
        try:
            s = data.assignment_summary(aid)
        except Exception as e:
            logger.exception("assignment_summary failed")
            messagebox.showerror("Form Tutors",
                                 f"Could not load:\n\n{e}",
                                 parent=dlg)
            return
        header_var.set(
            f"#{aid}  Yr{rec.year_group}/{rec.form_group}    "
            f"{rec.tutor_name}    {rec.academic_year}    "
            f"Meetings: {s['meeting_count']}")
        for m in s["meetings"]:
            t.insert("", "end", iid=str(m.meeting_id), values=(
                m.meeting_id, m.meeting_date, m.meeting_type,
                (m.agenda or "-")[:80],
                (m.follow_up_actions or "-")[:80],
            ))

    def _do_add() -> None:
        fields = _meeting_dialog(host, aid)
        if not fields:
            return
        try:
            data.add_meeting(fields)
        except ValidationError as e:
            messagebox.showerror("Form Tutors", str(e), parent=dlg)
            return
        _refresh()

    def _do_edit() -> None:
        sel = t.focus()
        if not sel:
            messagebox.showinfo("Form Tutors",
                                "Select a meeting first.", parent=dlg)
            return
        try:
            mid = int(sel)
        except ValueError:
            return
        existing = data.get_meeting(mid)
        if existing is None:
            return
        initial = {k: getattr(existing, k) for k in (
            "meeting_date", "meeting_type", "pupils_present",
            "agenda", "decisions", "follow_up_actions", "notes")}
        fields = _meeting_dialog(host, aid, initial=initial)
        if not fields:
            return
        try:
            data.update_meeting(mid, fields)
        except ValidationError as e:
            messagebox.showerror("Form Tutors", str(e), parent=dlg)
            return
        _refresh()

    def _do_delete() -> None:
        sel = t.focus()
        if not sel:
            messagebox.showinfo("Form Tutors",
                                "Select a meeting first.", parent=dlg)
            return
        try:
            mid = int(sel)
        except ValueError:
            return
        if not messagebox.askyesno(
                "Delete meeting",
                f"Delete meeting #{mid}?", parent=dlg):
            return
        data.delete_meeting(mid)
        _refresh()

    t.bind("<Double-1>", lambda _e: _do_edit())
    _refresh()
