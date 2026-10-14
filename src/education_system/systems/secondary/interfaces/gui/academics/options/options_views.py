"""Tk views for the GCSE options process."""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import Any, Callable

from education_system.systems.secondary.domain.academics.options import (
    options as data,
)
from education_system.systems.secondary.domain.academics.options.options import (
    ROUND_STATUSES,
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
                messagebox.showerror("Options", str(e),
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


# ── Round-editor dialog ────────────────────────────────────────────

def _round_dialog(host, title: str,
                  initial: dict[str, Any] | None = None
                  ) -> dict[str, Any] | None:
    dlg = tk.Toplevel(host.root)
    dlg.title(title)
    dlg.transient(host.root)
    dlg.geometry("460x430")
    dlg.update_idletasks()
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped — dialog not viewable", exc_info=True)

    initial = initial or {}
    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    name_var    = tk.StringVar(value=str(initial.get("name") or ""))
    year_var    = tk.StringVar(value=str(initial.get("year_group") or "9"))
    status_var  = tk.StringVar(value=str(initial.get("status") or "Draft"))
    opens_var   = tk.StringVar(value=str(initial.get("opens_on") or ""))
    closes_var  = tk.StringVar(value=str(initial.get("closes_on") or ""))
    choices_var = tk.StringVar(value=str(initial.get("choices_required")
                                          or 4))
    reserves_var = tk.StringVar(value=str(initial.get("reserves_required")
                                           or 1))
    notes_var   = tk.StringVar(value=str(initial.get("notes") or ""))

    rows: list[tuple[str, tk.Widget]] = [
        ("Name:",        ttk.Entry(frm, textvariable=name_var, width=34)),
        ("Year group:",  ttk.Combobox(frm, textvariable=year_var,
                                       values=list(YEAR_GROUPS),
                                       state="readonly", width=8)),
        ("Status:",      ttk.Combobox(frm, textvariable=status_var,
                                       values=list(ROUND_STATUSES),
                                       state="readonly", width=10)),
        ("Opens on:",    ttk.Entry(frm, textvariable=opens_var, width=14)),
        ("Closes on:",   ttk.Entry(frm, textvariable=closes_var, width=14)),
        ("Primary picks:", ttk.Spinbox(frm, from_=1, to=20,
                                        textvariable=choices_var, width=6)),
        ("Reserves:",    ttk.Spinbox(frm, from_=0, to=10,
                                      textvariable=reserves_var, width=6)),
        ("Notes:",       ttk.Entry(frm, textvariable=notes_var, width=34)),
    ]
    for i, (label, widget) in enumerate(rows):
        ttk.Label(frm, text=label).grid(row=i, column=0, sticky="w", pady=2)
        widget.grid(row=i, column=1, sticky="ew", pady=2)
    frm.columnconfigure(1, weight=1)

    result: dict[str, Any] | None = None

    def _save() -> None:
        nonlocal result
        result = {
            "name":              name_var.get().strip(),
            "year_group":        year_var.get().strip(),
            "status":            status_var.get().strip(),
            "opens_on":          opens_var.get().strip(),
            "closes_on":         closes_var.get().strip(),
            "choices_required":  choices_var.get().strip(),
            "reserves_required": reserves_var.get().strip(),
            "notes":             notes_var.get().strip(),
        }
        dlg.destroy()

    btns = ttk.Frame(frm)
    btns.grid(row=len(rows), column=0, columnspan=2, sticky="e",
              pady=(12, 0))
    ttk.Button(btns, text="Cancel", command=dlg.destroy).pack(side="right",
                                                               padx=4)
    ttk.Button(btns, text="Save", command=_save).pack(side="right")

    dlg.wait_window()
    return result


# ── Main view ─────────────────────────────────────────────────────

@_safe_view
def open_options(host) -> None:
    logger.debug("GUI: open_options")
    host._clear_content()
    root = host.content_frame
    ttk.Label(root, text="Options Process",
              font=("", 16, "bold")).pack(anchor="w", pady=(0, 8))

    bar = ttk.Frame(root)
    bar.pack(fill="x", pady=(0, 6))
    ttk.Button(bar, text="New round",
               command=lambda: _new_round(host, on_done=_refresh)).pack(
        side="left", padx=2)
    ttk.Button(bar, text="Edit round",
               command=lambda: _edit_round(host, tree, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Set status",
               command=lambda: _set_status(host, tree, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Manage subjects",
               command=lambda: _manage_subjects(host, tree)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Submit choices",
               command=lambda: _submit_choices(host, tree)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Summary",
               command=lambda: _summary(host, tree)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Delete round",
               command=lambda: _delete_round(host, tree, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: _refresh()).pack(side="left", padx=2)

    cols = ("id", "name", "year", "status", "opens", "closes",
            "picks", "reserves")
    tree = ttk.Treeview(root, columns=cols, show="headings", height=14)
    for c, label, w in [
        ("id", "ID", 50), ("name", "Name", 240),
        ("year", "Year", 60), ("status", "Status", 90),
        ("opens", "Opens", 100), ("closes", "Closes", 100),
        ("picks", "Picks", 70), ("reserves", "Reserves", 80),
    ]:
        tree.heading(c, text=label)
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True)

    detail = ttk.LabelFrame(root, text="Selected round", padding=8)
    detail.pack(fill="x", pady=(8, 0))
    detail_var = tk.StringVar(value="(select a row to see details)")
    ttk.Label(detail, textvariable=detail_var, justify="left").pack(
        anchor="w")

    def _refresh() -> None:
        for i in tree.get_children():
            tree.delete(i)
        try:
            rows = data.list_rounds()
        except Exception as e:
            logger.exception("options refresh failed")
            messagebox.showerror("Options",
                                 f"Could not load rounds:\n\n{e}",
                                 parent=host.root)
            return
        for r in rows:
            tree.insert("", "end", iid=str(r.round_id), values=(
                r.round_id, r.name, r.year_group, r.status,
                r.opens_on or "-", r.closes_on or "-",
                r.choices_required, r.reserves_required,
            ))
        detail_var.set("(select a row to see details)")
        host.status_var.set(f"Options: {len(rows)} round(s)")

    def _on_select(_e=None) -> None:
        sel = tree.focus()
        if not sel:
            return
        try:
            rnd = data.get_round(int(sel))
        except Exception:
            logger.exception("options detail lookup failed")
            return
        if rnd is None:
            return
        try:
            subs = data.list_round_subjects(rnd.round_id)
        except Exception:
            logger.exception("list_round_subjects failed")
            subs = []
        detail_var.set(
            f"Round: {rnd.name}    Year: {rnd.year_group}    "
            f"Status: {rnd.status}\n"
            f"Opens: {rnd.opens_on or '-'}    Closes: {rnd.closes_on or '-'}\n"
            f"Picks: {rnd.choices_required} primary + "
            f"{rnd.reserves_required} reserve\n"
            f"Subjects: {len(subs)}    Notes: {rnd.notes or '-'}"
        )

    tree.bind("<<TreeviewSelect>>", _on_select)
    tree.bind("<Double-1>", lambda _e: _edit_round(host, tree,
                                                    on_done=_refresh))
    _refresh()


def _selected_round_id(tree: ttk.Treeview, host) -> int | None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Options", "Select a round first.",
                            parent=host.root)
        return None
    try:
        return int(sel)
    except ValueError:
        return None


@_safe_view
def _new_round(host, *, on_done=None) -> None:
    fields = _round_dialog(host, "New options round")
    if not fields:
        return
    rec = data.create_round(fields)
    messagebox.showinfo("Options",
                        f"Created round '{rec.name}'",
                        parent=host.root)
    if on_done:
        on_done()


@_safe_view
def _edit_round(host, tree: ttk.Treeview, *, on_done=None) -> None:
    rid = _selected_round_id(tree, host)
    if rid is None:
        return
    existing = data.get_round(rid)
    if existing is None:
        return
    initial = {
        "name": existing.name, "year_group": existing.year_group,
        "status": existing.status,
        "opens_on": existing.opens_on, "closes_on": existing.closes_on,
        "choices_required": existing.choices_required,
        "reserves_required": existing.reserves_required,
        "notes": existing.notes,
    }
    fields = _round_dialog(host, f"Edit round #{rid}", initial=initial)
    if not fields:
        return
    data.update_round(rid, fields)
    if on_done:
        on_done()


@_safe_view
def _set_status(host, tree: ttk.Treeview, *, on_done=None) -> None:
    rid = _selected_round_id(tree, host)
    if rid is None:
        return
    rnd = data.get_round(rid)
    if rnd is None:
        return

    dlg = tk.Toplevel(host.root)
    dlg.title(f"Status — round #{rid}")
    dlg.transient(host.root)
    dlg.geometry("320x140")
    dlg.update_idletasks()
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        pass
    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)
    ttk.Label(frm, text=f"Round: {rnd.name}").pack(anchor="w")
    ttk.Label(frm, text=f"Current status: {rnd.status}",
              foreground="#666").pack(anchor="w", pady=(0, 8))
    new_var = tk.StringVar(value=rnd.status)
    ttk.Combobox(frm, textvariable=new_var,
                 values=list(ROUND_STATUSES),
                 state="readonly").pack(fill="x")

    def _save() -> None:
        try:
            data.set_round_status(rid, new_var.get())
        except ValidationError as e:
            messagebox.showerror("Options", str(e), parent=dlg)
            return
        dlg.destroy()
        if on_done:
            on_done()

    btns = ttk.Frame(frm)
    btns.pack(fill="x", pady=(10, 0))
    ttk.Button(btns, text="Cancel", command=dlg.destroy).pack(side="right",
                                                               padx=4)
    ttk.Button(btns, text="Save", command=_save).pack(side="right")


@_safe_view
def _delete_round(host, tree: ttk.Treeview, *, on_done=None) -> None:
    rid = _selected_round_id(tree, host)
    if rid is None:
        return
    rnd = data.get_round(rid)
    if rnd is None:
        return
    if not messagebox.askyesno(
            "Delete round",
            f"Delete round '{rnd.name}' and all linked subjects "
            f"and pupil choices?",
            parent=host.root):
        return
    data.delete_round(rid)
    if on_done:
        on_done()


# ── Subject-management sub-window ──────────────────────────────────

@_safe_view
def _manage_subjects(host, tree: ttk.Treeview) -> None:
    rid = _selected_round_id(tree, host)
    if rid is None:
        return
    rnd = data.get_round(rid)
    if rnd is None:
        return

    dlg = tk.Toplevel(host.root)
    dlg.title(f"Subjects — {rnd.name}")
    dlg.transient(host.root)
    dlg.geometry("720x420")
    dlg.update_idletasks()
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        pass

    frm = ttk.Frame(dlg, padding=10)
    frm.pack(fill="both", expand=True)

    ttk.Label(frm, text="In round", foreground="#444").grid(
        row=0, column=0, sticky="w")
    ttk.Label(frm, text="Active catalogue", foreground="#444").grid(
        row=0, column=2, sticky="w")

    in_round = ttk.Treeview(frm, columns=("code", "name"),
                            show="headings", height=14)
    in_round.heading("code", text="Code")
    in_round.heading("name", text="Name")
    in_round.column("code", width=80)
    in_round.column("name", width=220)
    in_round.grid(row=1, column=0, sticky="nsew", padx=(0, 6))

    btns_col = ttk.Frame(frm)
    btns_col.grid(row=1, column=1, sticky="ns", padx=4)
    ttk.Button(btns_col, text="◀ Add",
               command=lambda: _add_selected()).pack(pady=4)
    ttk.Button(btns_col, text="Remove ▶",
               command=lambda: _remove_selected()).pack(pady=4)

    available = ttk.Treeview(frm, columns=("code", "name", "qual"),
                             show="headings", height=14)
    available.heading("code", text="Code")
    available.heading("name", text="Name")
    available.heading("qual", text="Qualification")
    available.column("code", width=80)
    available.column("name", width=180)
    available.column("qual", width=100)
    available.grid(row=1, column=2, sticky="nsew", padx=(6, 0))

    frm.columnconfigure(0, weight=1)
    frm.columnconfigure(2, weight=1)
    frm.rowconfigure(1, weight=1)

    def _refresh() -> None:
        for i in in_round.get_children():
            in_round.delete(i)
        for i in available.get_children():
            available.delete(i)
        try:
            current = data.list_round_subjects(rid)
            all_active = subjects_data.list_all(active_only=True)
        except Exception as e:
            logger.exception("manage_subjects refresh failed")
            messagebox.showerror("Options",
                                 f"Could not load subjects:\n\n{e}",
                                 parent=dlg)
            return
        already = {s.subject_id for s in current}
        for s in current:
            in_round.insert("", "end", iid=str(s.subject_id),
                            values=(s.code, s.name))
        for s in all_active:
            if s.subject_id in already:
                continue
            available.insert("", "end", iid=str(s.subject_id),
                             values=(s.code, s.name, s.qualification))

    def _add_selected() -> None:
        sel = available.focus()
        if not sel:
            messagebox.showinfo("Options", "Select a subject to add.",
                                parent=dlg)
            return
        try:
            data.add_round_subject(rid, int(sel))
        except ValidationError as e:
            messagebox.showerror("Options", str(e), parent=dlg)
            return
        _refresh()

    def _remove_selected() -> None:
        sel = in_round.focus()
        if not sel:
            messagebox.showinfo("Options", "Select a subject to remove.",
                                parent=dlg)
            return
        try:
            data.remove_round_subject(rid, int(sel))
        except ValidationError as e:
            messagebox.showerror("Options", str(e), parent=dlg)
            return
        _refresh()

    bottom = ttk.Frame(dlg, padding=(10, 0, 10, 10))
    bottom.pack(fill="x")
    ttk.Button(bottom, text="Close",
               command=dlg.destroy).pack(side="right")

    _refresh()


# ── Submit-choices sub-window ──────────────────────────────────────

@_safe_view
def _submit_choices(host, tree: ttk.Treeview) -> None:
    rid = _selected_round_id(tree, host)
    if rid is None:
        return
    rnd = data.get_round(rid)
    if rnd is None:
        return
    if rnd.status != "Open":
        messagebox.showerror(
            "Options",
            f"Round '{rnd.name}' is {rnd.status}. "
            f"Choices can only be submitted while it is Open.",
            parent=host.root,
        )
        return
    avail = data.list_round_subjects(rid)
    if not avail:
        messagebox.showerror("Options",
                             "This round has no subjects yet.",
                             parent=host.root)
        return

    pupil_id = simpledialog.askstring(
        "Submit choices",
        "Pupil ID:", parent=host.root)
    if not pupil_id:
        return
    pupil_id = pupil_id.strip()
    if not pupil_id:
        return

    existing = data.get_pupil_choices(rid, pupil_id)
    existing_primary = [c.subject_id for c in existing if not c.is_reserve]
    existing_reserve = [c.subject_id for c in existing if c.is_reserve]

    dlg = tk.Toplevel(host.root)
    dlg.title(f"Choices — {pupil_id} — {rnd.name}")
    dlg.transient(host.root)
    dlg.geometry("420x560")
    dlg.update_idletasks()
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        pass

    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)
    ttk.Label(frm,
              text=f"Pupil: {pupil_id}    Round: {rnd.name}",
              font=("", 10, "bold")).pack(anchor="w", pady=(0, 6))
    ttk.Label(
        frm,
        text=f"{rnd.choices_required} primary + "
             f"{rnd.reserves_required} reserve choice(s)",
        foreground="#666",
    ).pack(anchor="w", pady=(0, 8))

    by_id = {s.subject_id: s for s in avail}
    options = [f"#{s.subject_id} {s.code} — {s.name}" for s in avail]

    def _label_for(sid: int | None) -> str:
        if sid is None or sid not in by_id:
            return ""
        s = by_id[sid]
        return f"#{s.subject_id} {s.code} — {s.name}"

    primary_vars: list[tk.StringVar] = []
    reserve_vars: list[tk.StringVar] = []

    ttk.Label(frm, text="Primary choices:",
              font=("", 10, "bold")).pack(anchor="w", pady=(4, 4))
    for i in range(rnd.choices_required):
        v = tk.StringVar(
            value=_label_for(existing_primary[i]
                             if i < len(existing_primary) else None))
        row = ttk.Frame(frm)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text=f"#{i+1}:", width=4).pack(side="left")
        ttk.Combobox(row, textvariable=v, values=options,
                     state="readonly", width=40).pack(side="left", fill="x",
                                                       expand=True)
        primary_vars.append(v)

    ttk.Label(frm, text="Reserves:",
              font=("", 10, "bold")).pack(anchor="w", pady=(10, 4))
    for j in range(rnd.reserves_required):
        v = tk.StringVar(
            value=_label_for(existing_reserve[j]
                             if j < len(existing_reserve) else None))
        row = ttk.Frame(frm)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text=f"R{j+1}:", width=4).pack(side="left")
        ttk.Combobox(row, textvariable=v, values=options,
                     state="readonly", width=40).pack(side="left", fill="x",
                                                       expand=True)
        reserve_vars.append(v)

    def _parse(label: str) -> int | None:
        label = (label or "").strip()
        if not label or not label.startswith("#"):
            return None
        try:
            return int(label.split()[0][1:])
        except (ValueError, IndexError):
            return None

    def _save() -> None:
        primary = [_parse(v.get()) for v in primary_vars]
        reserves = [_parse(v.get()) for v in reserve_vars]
        if any(x is None for x in primary + reserves):
            messagebox.showerror("Options",
                                 "Please pick a subject for every slot.",
                                 parent=dlg)
            return
        try:
            data.submit_pupil_choices(
                rid, pupil_id, primary, reserves)
        except ValidationError as e:
            messagebox.showerror("Options", str(e), parent=dlg)
            return
        messagebox.showinfo("Options", "Choices saved.", parent=dlg)
        dlg.destroy()

    def _clear() -> None:
        if not messagebox.askyesno(
                "Clear choices",
                f"Clear all choices for {pupil_id} in this round?",
                parent=dlg):
            return
        data.clear_pupil_choices(rid, pupil_id)
        dlg.destroy()

    btns = ttk.Frame(frm)
    btns.pack(fill="x", pady=(12, 0))
    ttk.Button(btns, text="Cancel",
               command=dlg.destroy).pack(side="right", padx=4)
    ttk.Button(btns, text="Save", command=_save).pack(side="right")
    ttk.Button(btns, text="Clear all",
               command=_clear).pack(side="left")


# ── Summary sub-window ────────────────────────────────────────────

@_safe_view
def _summary(host, tree: ttk.Treeview) -> None:
    rid = _selected_round_id(tree, host)
    if rid is None:
        return
    summary = data.submission_summary(rid)
    rnd = summary["round"]

    dlg = tk.Toplevel(host.root)
    dlg.title(f"Summary — {rnd.name}")
    dlg.transient(host.root)
    dlg.geometry("560x460")
    dlg.update_idletasks()
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        pass

    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)
    ttk.Label(frm,
              text=f"{rnd.name}  ·  Year {rnd.year_group}  ·  {rnd.status}",
              font=("", 11, "bold")).pack(anchor="w", pady=(0, 6))
    ttk.Label(frm,
              text=f"Pupils submitted: {summary['pupils_submitted']}    "
                   f"Complete: {summary['pupils_complete']}    "
                   f"Partial: {summary['pupils_partial']}",
              foreground="#444").pack(anchor="w", pady=(0, 10))

    cols = ("code", "name", "primary", "reserve")
    t = ttk.Treeview(frm, columns=cols, show="headings", height=14)
    for c, label, w in [
        ("code", "Code", 80), ("name", "Name", 260),
        ("primary", "Primary", 80), ("reserve", "Reserve", 80),
    ]:
        t.heading(c, text=label)
        t.column(c, width=w, anchor="w")
    t.pack(fill="both", expand=True)
    for s in summary["subject_picks"]:
        t.insert("", "end", values=(
            s["code"], s["name"], s["primary"], s["reserve"]))

    ttk.Button(frm, text="Close",
               command=dlg.destroy).pack(side="right", pady=(10, 0))
