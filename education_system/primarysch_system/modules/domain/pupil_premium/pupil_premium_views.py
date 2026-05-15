"""Tk views for Pupil Premium."""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable

from education_system.primarysch_system.modules.domain.pupil_premium import (
    pupil_premium as data,
)
from education_system.primarysch_system.modules.domain.pupil_premium.pupil_premium import (
    CATEGORIES, PP_STATUSES, INTERVENTION_STATUSES, IMPACT_RATINGS,
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
                messagebox.showerror("Pupil Premium", str(e),
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
    dlg.geometry("500x520")
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
    ay_var     = tk.StringVar(value=str(initial.get("academic_year")
                                          or ""))
    cat_var    = tk.StringVar(value=str(initial.get("category")
                                          or "Ever 6 FSM"))
    status_var = tk.StringVar(value=str(initial.get("status")
                                          or "Eligible"))
    funding_var = tk.StringVar(value=str(initial.get("funding_amount")
                                            if initial.get("funding_amount")
                                            is not None else ""))
    start_var  = tk.StringVar(value=str(initial.get("start_date") or ""))
    end_var    = tk.StringVar(value=str(initial.get("end_date") or ""))
    source_var = tk.StringVar(value=str(initial.get("eligibility_source")
                                           or ""))
    keyworker_var = tk.StringVar(value=str(initial.get("keyworker")
                                              or ""))

    rows: list[tuple[str, tk.Widget]] = [
        ("Pupil ID:",    ttk.Entry(frm, textvariable=pupil_var,
                                      width=14)),
        ("Academic year:", ttk.Entry(frm, textvariable=ay_var,
                                       width=10)),
        ("Category:",    ttk.Combobox(frm, textvariable=cat_var,
                                        values=list(CATEGORIES),
                                        state="readonly", width=26)),
        ("Status:",      ttk.Combobox(frm, textvariable=status_var,
                                        values=list(PP_STATUSES),
                                        state="readonly", width=14)),
        ("Funding £:",   ttk.Entry(frm, textvariable=funding_var,
                                      width=10)),
        ("Start date:",  ttk.Entry(frm, textvariable=start_var,
                                      width=14)),
        ("End date:",    ttk.Entry(frm, textvariable=end_var,
                                      width=14)),
        ("Source:",      ttk.Entry(frm, textvariable=source_var,
                                      width=30)),
        ("Keyworker:",   ttk.Entry(frm, textvariable=keyworker_var,
                                      width=24)),
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
            "pupil_id":           pupil_var.get().strip(),
            "academic_year":      ay_var.get().strip(),
            "category":           cat_var.get().strip(),
            "status":             status_var.get().strip(),
            "funding_amount":     funding_var.get().strip(),
            "start_date":         start_var.get().strip(),
            "end_date":           end_var.get().strip(),
            "eligibility_source": source_var.get().strip(),
            "keyworker":          keyworker_var.get().strip(),
            "notes":              notes_w.get("1.0", "end").strip(),
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


def _intervention_dialog(host, pp_id: int,
                          initial: dict[str, Any] | None = None
                          ) -> dict[str, Any] | None:
    dlg = tk.Toplevel(host.root)
    dlg.title(f"Intervention — PP record #{pp_id}")
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

    title_var  = tk.StringVar(value=str(initial.get("title") or ""))
    spend_var  = tk.StringVar(value=str(initial.get("spend") or "0"))
    start_var  = tk.StringVar(value=str(initial.get("start_date") or ""))
    end_var    = tk.StringVar(value=str(initial.get("end_date") or ""))
    status_var = tk.StringVar(value=str(initial.get("status")
                                          or "Planned"))
    impact_var = tk.StringVar(value=str(initial.get("impact_rating")
                                          or "Not yet assessed"))

    rows: list[tuple[str, tk.Widget]] = [
        ("Title:",    ttk.Entry(frm, textvariable=title_var, width=40)),
        ("Spend £:",  ttk.Entry(frm, textvariable=spend_var, width=10)),
        ("Start date:", ttk.Entry(frm, textvariable=start_var,
                                    width=14)),
        ("End date:", ttk.Entry(frm, textvariable=end_var, width=14)),
        ("Status:",   ttk.Combobox(frm, textvariable=status_var,
                                     values=list(INTERVENTION_STATUSES),
                                     state="readonly", width=14)),
        ("Impact:",   ttk.Combobox(frm, textvariable=impact_var,
                                     values=list(IMPACT_RATINGS),
                                     state="readonly", width=18)),
    ]
    for label, widget in rows:
        row = ttk.Frame(frm)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text=label, width=12).pack(side="left")
        widget.pack(in_=row, side="left", padx=4)

    text_fields = [("Description:", "description", 3),
                   ("Impact notes:", "impact_notes", 3),
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
            "pp_id":         pp_id,
            "title":         title_var.get().strip(),
            "spend":         spend_var.get().strip(),
            "start_date":    start_var.get().strip(),
            "end_date":      end_var.get().strip(),
            "status":        status_var.get().strip(),
            "impact_rating": impact_var.get().strip(),
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
def open_pupil_premium(host) -> None:
    logger.debug("GUI: open_pupil_premium")
    host._clear_content()
    root = host.content_frame
    ttk.Label(root, text="Pupil Premium",
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
    ttk.Label(bar, text="Category:").pack(side="left", padx=(0, 4))
    cat_var = tk.StringVar(value="")
    ttk.Combobox(bar, textvariable=cat_var,
                 values=["", *CATEGORIES], state="readonly",
                 width=24).pack(side="left", padx=(0, 6))
    ttk.Label(bar, text="Status:").pack(side="left", padx=(0, 4))
    status_var = tk.StringVar(value="")
    ttk.Combobox(bar, textvariable=status_var,
                 values=["", *PP_STATUSES], state="readonly",
                 width=12).pack(side="left", padx=(0, 8))
    ttk.Button(bar, text="Apply",
               command=lambda: _refresh()).pack(side="left", padx=2)
    ttk.Button(bar, text="New / update",
               command=lambda: _new(host, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Edit",
               command=lambda: _edit(host, tree, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Interventions",
               command=lambda: _open_interventions(host, tree)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Delete",
               command=lambda: _delete(host, tree, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: _refresh()).pack(side="left", padx=2)

    cols = ("id", "ay", "pupil", "year", "category", "status",
            "funding", "keyworker")
    tree = ttk.Treeview(root, columns=cols, show="headings", height=18)
    for c, label, w in [
        ("id", "ID", 50), ("ay", "Academic yr", 100),
        ("pupil", "Pupil", 90), ("year", "Yr", 50),
        ("category", "Category", 200), ("status", "Status", 100),
        ("funding", "Funding £", 100),
        ("keyworker", "Keyworker", 160),
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
                category=cat_var.get().strip() or None,
                status=status_var.get().strip() or None,
            )
        except ValidationError as e:
            messagebox.showerror("Pupil Premium", str(e),
                                 parent=host.root)
            return
        except Exception as e:
            logger.exception("pupil_premium refresh failed")
            messagebox.showerror("Pupil Premium",
                                 f"Could not load:\n\n{e}",
                                 parent=host.root)
            return
        for r in rows:
            fund = (f"£{r.funding_amount:.2f}"
                    if r.funding_amount is not None else "-")
            tree.insert("", "end", iid=str(r.pp_id), values=(
                r.pp_id, r.academic_year, r.pupil_id,
                r.pupil_year or "-", r.category, r.status,
                fund, r.keyworker or "-",
            ))
        try:
            s = data.cohort_summary(
                year_group=year_var.get().strip() or None,
                academic_year=ay_var.get().strip() or None)
            summary_var.set(
                f"Records: {s['total']}    "
                f"Funding: £{s['total_funding']:.2f}    "
                f"Spend: £{s['total_spend']:.2f}    "
                f"Remaining: £{s['remaining']:.2f}")
        except Exception:
            summary_var.set(f"{len(rows)} record(s)")
        host.status_var.set(f"Pupil Premium: {len(rows)} record(s)")

    tree.bind("<Double-1>",
              lambda _e: _open_interventions(host, tree))
    year_var.trace_add("write", lambda *_: _refresh())
    cat_var.trace_add("write", lambda *_: _refresh())
    status_var.trace_add("write", lambda *_: _refresh())
    _refresh()


def _selected_id(tree: ttk.Treeview, host) -> int | None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Pupil Premium",
                            "Select a record first.",
                            parent=host.root)
        return None
    try:
        return int(sel)
    except ValueError:
        return None


@_safe_view
def _new(host, *, on_done=None) -> None:
    fields = _record_dialog(host, "New / update PP record")
    if not fields:
        return
    r = data.upsert(fields)
    messagebox.showinfo(
        "Pupil Premium",
        f"Saved {r.pupil_id} ({r.academic_year}, {r.category})",
        parent=host.root,
    )
    if on_done:
        on_done()


@_safe_view
def _edit(host, tree: ttk.Treeview, *, on_done=None) -> None:
    pp = _selected_id(tree, host)
    if pp is None:
        return
    existing = data.get(pp)
    if existing is None:
        return
    initial = {k: getattr(existing, k) for k in (
        "pupil_id", "academic_year", "category", "status",
        "funding_amount", "start_date", "end_date",
        "eligibility_source", "keyworker", "notes")}
    fields = _record_dialog(host, f"Edit PP record #{pp}",
                              initial=initial)
    if not fields:
        return
    data.upsert(fields)
    if on_done:
        on_done()


@_safe_view
def _delete(host, tree: ttk.Treeview, *, on_done=None) -> None:
    pp = _selected_id(tree, host)
    if pp is None:
        return
    existing = data.get(pp)
    if existing is None:
        return
    if not messagebox.askyesno(
            "Delete record",
            f"Delete PP record for {existing.pupil_id} "
            f"({existing.academic_year}) and ALL its interventions?",
            parent=host.root):
        return
    data.delete(pp)
    if on_done:
        on_done()


@_safe_view
def _open_interventions(host, tree: ttk.Treeview) -> None:
    pp = _selected_id(tree, host)
    if pp is None:
        return
    rec = data.get(pp)
    if rec is None:
        return

    dlg = tk.Toplevel(host.root)
    dlg.title(f"Interventions — PP record #{pp}")
    dlg.transient(host.root)
    dlg.geometry("800x520")
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
    ttk.Button(bar, text="Add",
               command=lambda: _do_add()).pack(side="left", padx=2)
    ttk.Button(bar, text="Edit",
               command=lambda: _do_edit()).pack(side="left", padx=2)
    ttk.Button(bar, text="Delete",
               command=lambda: _do_delete()).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: _refresh()).pack(side="left", padx=2)

    t = ttk.Treeview(frm,
                       columns=("id", "start", "status", "spend",
                                 "impact", "title"),
                       show="headings", height=14)
    for c, label, w in [
        ("id", "ID", 50), ("start", "Start", 100),
        ("status", "Status", 100), ("spend", "Spend £", 100),
        ("impact", "Impact", 160), ("title", "Title", 320),
    ]:
        t.heading(c, text=label)
        t.column(c, width=w, anchor="w")
    t.pack(fill="both", expand=True)

    def _refresh() -> None:
        for i in t.get_children():
            t.delete(i)
        try:
            s = data.record_summary(pp)
        except Exception as e:
            logger.exception("record_summary failed")
            messagebox.showerror("Pupil Premium",
                                 f"Could not load:\n\n{e}",
                                 parent=dlg)
            return
        r = s["record"]
        header_var.set(
            f"#{r.pp_id} {r.pupil_id} ({r.academic_year})    "
            f"Funding: "
            f"{('£' + format(r.funding_amount, '.2f')) if r.funding_amount is not None else '-'}    "
            f"Spend: £{s['total_spend']:.2f}    "
            f"Remaining: "
            f"{('£' + format(s['remaining'], '.2f')) if s['remaining'] is not None else '-'}")
        for i in s["interventions"]:
            t.insert("", "end", iid=str(i.intervention_id), values=(
                i.intervention_id, i.start_date, i.status,
                f"£{i.spend:.2f}", i.impact_rating, i.title,
            ))

    def _do_add() -> None:
        fields = _intervention_dialog(host, pp)
        if not fields:
            return
        try:
            data.add_intervention(fields)
        except ValidationError as e:
            messagebox.showerror("Pupil Premium", str(e), parent=dlg)
            return
        _refresh()

    def _do_edit() -> None:
        sel = t.focus()
        if not sel:
            messagebox.showinfo("Pupil Premium",
                                "Select an intervention first.",
                                parent=dlg)
            return
        try:
            iid = int(sel)
        except ValueError:
            return
        existing = data.get_intervention(iid)
        if existing is None:
            return
        initial = {k: getattr(existing, k) for k in (
            "title", "description", "spend", "start_date",
            "end_date", "status", "impact_rating",
            "impact_notes", "notes")}
        fields = _intervention_dialog(host, pp, initial=initial)
        if not fields:
            return
        try:
            data.update_intervention(iid, fields)
        except ValidationError as e:
            messagebox.showerror("Pupil Premium", str(e), parent=dlg)
            return
        _refresh()

    def _do_delete() -> None:
        sel = t.focus()
        if not sel:
            messagebox.showinfo("Pupil Premium",
                                "Select an intervention first.",
                                parent=dlg)
            return
        try:
            iid = int(sel)
        except ValueError:
            return
        if not messagebox.askyesno(
                "Delete intervention",
                f"Delete intervention #{iid}?", parent=dlg):
            return
        data.delete_intervention(iid)
        _refresh()

    t.bind("<Double-1>", lambda _e: _do_edit())
    _refresh()
