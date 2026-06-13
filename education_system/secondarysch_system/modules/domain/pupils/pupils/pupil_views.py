"""Tk GUI views for pupil CRUD in the Secondary School System.

Each ``open_*(host)`` swaps content into ``host.content_frame`` (the
right-hand pane managed by ``SecondarySchoolMainGUI``). Add / edit
opens a modal dialog over ``host.root``.
"""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable

from education_system.secondarysch_system.modules.domain.pupils import sixthform_transfer
from education_system.secondarysch_system.modules.domain.pupils.pupils import pupils as data
from education_system.secondarysch_system.modules.domain.pupils.pupils.pupils import (
    ValidationError, YEAR_GROUPS,
)
from education_system.secondarysch_system.modules.domain.pupils.enrolment.enrolment import (
    _bump_form,
)
from education_system.sixthform_system.modules.domain.students.students.students import (
    A_LEVEL_SUBJECTS,
)

logger = logging.getLogger(__name__)


def _safe_view(func: Callable[..., None]) -> Callable[..., None]:
    """Catch unexpected errors in a Tk view; log and show an error dialog."""
    @functools.wraps(func)
    def wrapper(host, *args, **kwargs):
        try:
            return func(host, *args, **kwargs)
        except ValidationError as e:
            logger.warning("%s validation: %s", func.__name__, e)
            try:
                messagebox.showerror(func.__name__, str(e),
                                     parent=getattr(host, "root", None))
            except Exception:
                logger.debug("Could not show validation dialog", exc_info=True)
        except Exception as e:
            logger.exception("%s failed", func.__name__)
            try:
                messagebox.showerror(
                    "Error",
                    f"An unexpected error occurred:\n\n{e}\n\nSee logs for details.",
                    parent=getattr(host, "root", None),
                )
            except Exception:
                logger.debug("Could not show error dialog", exc_info=True)
    return wrapper


_FIELDS = [
    ("first_name",    "First name"),
    ("last_name",     "Last name"),
    ("year_group",    "Year group"),
    ("form_group",    "Form group"),
    ("date_of_birth", "Date of birth (YYYY-MM-DD)"),
    ("phone",         "Phone"),
    ("parent_name",   "Parent name"),
    ("parent_phone",  "Parent phone"),
    ("send_status",   "SEND (yes/no)"),
]


def _clear(host) -> ttk.Frame:
    host._clear_content()
    assert host.content_frame is not None
    return host.content_frame


def _header(parent: ttk.Frame, title: str) -> None:
    ttk.Label(parent, text=title, font=("", 16, "bold")).pack(
        anchor="w", pady=(0, 8))


@_safe_view
def open_directory(host) -> None:
    logger.debug("GUI: open_directory")
    root = _clear(host)
    _header(root, "Pupil Directory")

    bar = ttk.Frame(root)
    bar.pack(fill="x", pady=(0, 8))
    ttk.Button(bar, text="Add Pupil",
               command=lambda: open_add_pupil(host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Edit Selected",
               command=lambda: _edit_selected(tree, host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Delete Selected",
               command=lambda: _delete_selected(tree, host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Move to Sixth Form",
               command=lambda: _move_selected_to_sixth_form(tree, host)).pack(
        side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: _refresh(tree)).pack(side="left", padx=2)

    cols = ("id", "year", "form", "name", "email", "parent", "send")
    tree = ttk.Treeview(root, columns=cols, show="headings", height=20)
    for c, label, w in [
        ("id", "ID", 90), ("year", "Year", 50), ("form", "Form", 60),
        ("name", "Name", 200), ("email", "Email", 220),
        ("parent", "Parent", 160), ("send", "SEND", 60),
    ]:
        tree.heading(c, text=label)
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True)
    tree.bind("<Double-1>", lambda _e: _edit_selected(tree, host))

    _refresh(tree)
    host.status_var.set("Pupil directory loaded")


def _refresh(tree: ttk.Treeview) -> None:
    for i in tree.get_children():
        tree.delete(i)
    try:
        rows = data.list_pupils()
    except Exception:
        logger.exception("Could not refresh pupil directory")
        try:
            messagebox.showerror(
                "Pupil directory",
                "Could not load the pupil list — see logs for details.",
            )
        except Exception:
            pass
        return
    for p in rows:
        tree.insert("", "end", iid=p.pupil_id, values=(
            p.pupil_id, p.year_group, p.form_group or "-",
            p.full_name, p.email, p.parent_name or "-",
            p.send_status or "-",
        ))


def _edit_selected(tree: ttk.Treeview, host) -> None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Edit pupil", "Select a pupil first.",
                            parent=host.root)
        return
    open_edit_pupil(host, sel, on_done=lambda: _refresh(tree))


def _delete_selected(tree: ttk.Treeview, host) -> None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Delete pupil", "Select a pupil first.",
                            parent=host.root)
        return
    try:
        p = data.get_pupil(sel)
    except Exception:
        logger.exception("Lookup failed before delete for id=%s", sel)
        messagebox.showerror("Delete pupil", "Could not look up pupil.",
                             parent=host.root)
        return
    if p is None:
        return
    if not messagebox.askyesno(
            "Delete pupil",
            f"Delete {p.full_name} ({p.pupil_id})? This cannot be undone.",
            parent=host.root):
        return
    try:
        data.delete_pupil(sel)
    except Exception as e:
        logger.exception("Failed to delete pupil id=%s", sel)
        messagebox.showerror("Delete pupil",
                             f"Could not delete pupil:\n\n{e}",
                             parent=host.root)
        return
    _refresh(tree)
    host.status_var.set(f"Deleted pupil {sel}")
    logger.info("GUI deleted pupil %s", sel)


def _move_selected_to_sixth_form(tree: ttk.Treeview, host) -> None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Move to sixth form", "Select a pupil first.",
                            parent=host.root)
        return
    try:
        p = data.get_pupil(sel)
    except Exception:
        logger.exception("Lookup failed before sixth form transfer for id=%s", sel)
        messagebox.showerror("Move to sixth form", "Could not look up pupil.",
                             parent=host.root)
        return
    if p is None:
        messagebox.showerror("Move to sixth form", f"No pupil with id {sel}",
                             parent=host.root)
        return

    dlg = tk.Toplevel(host.root)
    dlg.title("Move to Sixth Form")
    dlg.transient(host.root)
    dlg.geometry("470x360")
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped", exc_info=True)

    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    ttk.Label(
        frm,
        text=f"Move {p.full_name} ({p.pupil_id}) into the sixth form system?",
        wraplength=420,
        justify="left",
    ).pack(anchor="w", pady=(0, 10))
    if p.year_group != "11":
        ttk.Label(
            frm,
            text=f"Current secondary year group is {p.year_group}.",
            foreground="#a45",
        ).pack(anchor="w", pady=(0, 10))

    subjects = [tk.StringVar(), tk.StringVar(), tk.StringVar()]
    destination = tk.StringVar(value=sixthform_transfer.DEFAULT_DESTINATION)
    notes = tk.StringVar()

    grid = ttk.Frame(frm)
    grid.pack(fill="x", expand=True)
    for row, var in enumerate(subjects, start=1):
        ttk.Label(grid, text=f"Subject {row}:").grid(
            row=row - 1, column=0, sticky="w", pady=3)
        ttk.Combobox(
            grid,
            textvariable=var,
            values=A_LEVEL_SUBJECTS,
            width=30,
        ).grid(row=row - 1, column=1, sticky="ew", pady=3)
    for row, (label, var) in enumerate((
        ("Destination", destination),
        ("Notes", notes),
    ), start=3):
        ttk.Label(grid, text=f"{label}:").grid(row=row, column=0, sticky="w",
                                                pady=3)
        ttk.Entry(grid, textvariable=var, width=32).grid(
            row=row, column=1, sticky="ew", pady=3)
    grid.columnconfigure(1, weight=1)

    def _go() -> None:
        selected_subjects = [s.get().strip() for s in subjects]
        if any(not s for s in selected_subjects):
            messagebox.showerror(
                "Move to sixth form",
                "Choose three A-level subjects.",
                parent=dlg,
            )
            return
        if not messagebox.askyesno(
                "Move to sixth form",
                "This will create a sixth form student record, create a login, "
                "record alumni, and remove the secondary pupil. Continue?",
                parent=dlg):
            return
        try:
            result = sixthform_transfer.move_to_sixth_form(
                p.pupil_id,
                subject_1=selected_subjects[0],
                subject_2=selected_subjects[1],
                subject_3=selected_subjects[2],
                destination=destination.get().strip() or None,
                notes=notes.get().strip() or None,
            )
        except ValidationError as e:
            messagebox.showerror("Move to sixth form", str(e), parent=dlg)
            return
        except Exception as e:
            logger.exception("Sixth form transfer failed for %s", p.pupil_id)
            messagebox.showerror(
                "Move to sixth form",
                f"Could not move pupil:\n\n{e}\n\nSee logs for details.",
                parent=dlg,
            )
            return

        _refresh(tree)
        host.status_var.set(
            f"Moved {p.pupil_id} to sixth form as {result.sixthform_student_id}")
        messagebox.showinfo(
            "Moved to sixth form",
            "Sixth form student created.\n\n"
            f"Student ID: {result.sixthform_student_id}\n"
            f"Login email: {result.sixthform_email}\n"
            f"Password: {result.password}\n"
            f"Alumni record: {result.alumni_id}",
            parent=dlg,
        )
        dlg.destroy()

    btns = ttk.Frame(frm)
    btns.pack(fill="x", pady=(12, 0))
    ttk.Button(btns, text="Move", command=_go).pack(side="right")
    ttk.Button(btns, text="Cancel",
               command=dlg.destroy).pack(side="right", padx=(0, 8))


def _form_dialog(host, title: str, initial: dict[str, Any] | None = None,
                 *, year_locked: bool = False) -> dict[str, str] | None:
    """Modal form returning a fields dict or None on cancel."""
    dlg = tk.Toplevel(host.root)
    dlg.title(title)
    dlg.transient(host.root)
    dlg.geometry("420x440")
    dlg.update_idletasks()
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped — dialog not viewable", exc_info=True)

    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    initial = initial or {}
    vars_: dict[str, tk.Variable] = {}

    for i, (key, label) in enumerate(_FIELDS):
        ttk.Label(frm, text=f"{label}:").grid(row=i, column=0, sticky="w",
                                               pady=2)
        if key == "year_group":
            v = tk.StringVar(value=str(initial.get(key, YEAR_GROUPS[0])))
            cb = ttk.Combobox(frm, textvariable=v, values=list(YEAR_GROUPS),
                              state="readonly" if year_locked else "normal",
                              width=10)
            cb.grid(row=i, column=1, sticky="w", pady=2)
        elif key == "send_status":
            v = tk.StringVar(value=str(initial.get(key) or ""))
            cb = ttk.Combobox(frm, textvariable=v, values=["", "yes", "no"],
                              width=10)
            cb.grid(row=i, column=1, sticky="w", pady=2)
        else:
            v = tk.StringVar(value=str(initial.get(key) or ""))
            ttk.Entry(frm, textvariable=v, width=32).grid(
                row=i, column=1, sticky="ew", pady=2)
        vars_[key] = v
    frm.columnconfigure(1, weight=1)

    result: dict[str, str] | None = None

    def _save() -> None:
        nonlocal result
        result = {k: (v.get() or "").strip() for k, v in vars_.items()}
        dlg.destroy()

    btns = ttk.Frame(frm)
    btns.grid(row=len(_FIELDS), column=0, columnspan=2, sticky="e", pady=(12, 0))
    ttk.Button(btns, text="Cancel", command=dlg.destroy).pack(side="right", padx=4)
    ttk.Button(btns, text="Save", command=_save).pack(side="right")

    dlg.wait_window()
    return result


@_safe_view
def open_add_pupil(host) -> None:
    logger.debug("GUI: open_add_pupil")
    root = _clear(host)
    _header(root, "Add Pupil")
    ttk.Label(root, text="Opening add-pupil form…", foreground="#666").pack(
        anchor="w")
    fields = _form_dialog(host, "Add Pupil")
    if not fields:
        host.status_var.set("Add pupil cancelled")
        return
    try:
        p = data.create_pupil(fields)
    except ValidationError as e:
        messagebox.showerror("Add pupil", str(e), parent=host.root)
        return
    messagebox.showinfo(
        "Pupil added",
        f"Created {p.full_name}\nID: {p.pupil_id}\nEmail: {p.email}",
        parent=host.root,
    )
    open_directory(host)


@_safe_view
def open_edit_pupil(host, pupil_id: str, *, on_done=None) -> None:
    logger.debug("GUI: open_edit_pupil(%s)", pupil_id)
    p = data.get_pupil(pupil_id)
    if p is None:
        messagebox.showerror("Edit pupil", f"No pupil with id {pupil_id}",
                             parent=host.root)
        return
    initial = {key: getattr(p, key) for key, _ in _FIELDS}
    fields = _form_dialog(host, f"Edit {p.full_name}", initial=initial)
    if not fields:
        return
    # If the year changed but the form field wasn't touched, bump the
    # form prefix (e.g. 7cbp -> 9cbp) so it follows the pupil up.
    if (fields.get("year_group") != p.year_group
            and fields.get("form_group") == (p.form_group or "")):
        bumped = _bump_form(
            p.year_group, fields["year_group"], p.form_group)
        if bumped is not None:
            fields["form_group"] = bumped
    try:
        data.update_pupil(pupil_id, fields)
    except ValidationError as e:
        messagebox.showerror("Edit pupil", str(e), parent=host.root)
        return
    host.status_var.set(f"Updated pupil {pupil_id}")
    if on_done:
        try:
            on_done()
        except Exception:
            logger.exception("on_done callback failed after edit")


@_safe_view
def open_search(host) -> None:
    logger.debug("GUI: open_search")
    root = _clear(host)
    _header(root, "Search Pupils")

    bar = ttk.Frame(root)
    bar.pack(fill="x", pady=(0, 8))
    ttk.Label(bar, text="Query:").pack(side="left", padx=(0, 6))
    qvar = tk.StringVar()
    entry = ttk.Entry(bar, textvariable=qvar, width=40)
    entry.pack(side="left")
    entry.focus_set()

    cols = ("id", "year", "form", "name", "email")
    tree = ttk.Treeview(root, columns=cols, show="headings", height=20)
    for c, label, w in [
        ("id", "ID", 90), ("year", "Year", 50), ("form", "Form", 60),
        ("name", "Name", 220), ("email", "Email", 240),
    ]:
        tree.heading(c, text=label)
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True, pady=(8, 0))

    status = ttk.Label(root, text="", foreground="#666")
    status.pack(anchor="w", pady=(6, 0))

    def _do_search(*_a) -> None:
        for i in tree.get_children():
            tree.delete(i)
        try:
            rows = data.search_pupils(qvar.get())
        except Exception:
            logger.exception("Search failed")
            status.config(text="Search failed — see logs", foreground="#a00")
            return
        for p in rows:
            tree.insert("", "end", iid=p.pupil_id, values=(
                p.pupil_id, p.year_group, p.form_group or "-",
                p.full_name, p.email,
            ))
        status.config(text=f"{len(rows)} match(es)", foreground="#666")

    ttk.Button(bar, text="Search", command=_do_search).pack(side="left", padx=4)
    entry.bind("<Return>", _do_search)
    _do_search()


@_safe_view
def open_advanced_search(host) -> None:
    logger.debug("GUI: open_advanced_search")
    root = _clear(host)
    _header(root, "Advanced Search")

    # ── Filters panel ──────────────────────────────────────────────
    form = ttk.LabelFrame(root, text="Filters", padding=10)
    form.pack(fill="x", pady=(0, 8))

    name_v   = tk.StringVar()
    year_v   = tk.StringVar()
    form_v   = tk.StringVar()
    email_v  = tk.StringVar()
    parent_v = tk.StringVar()
    send_v   = tk.StringVar()
    dobf_v   = tk.StringVar()
    dobt_v   = tk.StringVar()
    phone_v  = tk.StringVar()
    pcon_v   = tk.StringVar()
    sort_v   = tk.StringVar(value="year")

    rows: list[tuple[str, tk.Variable, list[str] | None]] = [
        ("Name contains",       name_v,   None),
        ("Year group",          year_v,   ["", *YEAR_GROUPS]),
        ("Form group contains", form_v,   None),
        ("Email contains",      email_v,  None),
        ("Parent contains",     parent_v, None),
        ("SEND",                send_v,   ["", "yes", "no"]),
        ("DOB from (YYYY-MM-DD)", dobf_v, None),
        ("DOB to   (YYYY-MM-DD)", dobt_v, None),
        ("Has phone?",          phone_v,  ["", "yes", "no"]),
        ("Has parent contact?", pcon_v,   ["", "yes", "no"]),
        ("Sort by",             sort_v,   ["year", "name", "id", "email", "dob"]),
    ]

    # Lay out in a 2-column grid (label, widget) × (left, right)
    for i, (label, var, choices) in enumerate(rows):
        col = (i % 2) * 2
        r = i // 2
        ttk.Label(form, text=f"{label}:").grid(
            row=r, column=col, sticky="w", padx=(0, 6), pady=2)
        if choices is not None:
            ttk.Combobox(form, textvariable=var, values=choices, width=18,
                         state="readonly" if label != "Sort by" else "readonly"
                         ).grid(row=r, column=col + 1, sticky="w", pady=2)
        else:
            ttk.Entry(form, textvariable=var, width=22).grid(
                row=r, column=col + 1, sticky="ew", pady=2)
    form.columnconfigure(1, weight=1)
    form.columnconfigure(3, weight=1)

    # ── Action bar ─────────────────────────────────────────────────
    bar = ttk.Frame(root)
    bar.pack(fill="x", pady=(0, 6))
    summary_var = tk.StringVar(value="No filters applied yet.")
    ttk.Label(bar, textvariable=summary_var, foreground="#666").pack(
        side="left", padx=(0, 12))
    ttk.Button(bar, text="Search",
               command=lambda: _do_adv_search()).pack(side="right", padx=2)
    ttk.Button(bar, text="Clear",
               command=lambda: _clear_filters()).pack(side="right", padx=2)
    ttk.Button(bar, text="Open Selected",
               command=lambda: _open_selected()).pack(side="right", padx=2)

    # ── Results ────────────────────────────────────────────────────
    cols = ("id", "year", "form", "name", "dob", "email", "parent", "send")
    tree = ttk.Treeview(root, columns=cols, show="headings", height=18)
    for c, label, w in [
        ("id", "ID", 90), ("year", "Year", 50), ("form", "Form", 60),
        ("name", "Name", 200), ("dob", "DOB", 90),
        ("email", "Email", 200), ("parent", "Parent", 150),
        ("send", "SEND", 60),
    ]:
        tree.heading(c, text=label)
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True)
    tree.bind("<Double-1>", lambda _e: _open_selected())

    status_var = tk.StringVar(value="")
    ttk.Label(root, textvariable=status_var, foreground="#666").pack(
        anchor="w", pady=(4, 0))

    # ── Behaviour ──────────────────────────────────────────────────
    def _collect_filters() -> dict[str, str]:
        f = {
            "name":        name_v.get().strip(),
            "year_group":  year_v.get().strip(),
            "form_group":  form_v.get().strip(),
            "email":       email_v.get().strip(),
            "parent_name": parent_v.get().strip(),
            "send_status": send_v.get().strip(),
            "dob_from":    dobf_v.get().strip(),
            "dob_to":      dobt_v.get().strip(),
            "has_phone":   phone_v.get().strip(),
            "has_parent":  pcon_v.get().strip(),
            "sort_by":     sort_v.get().strip() or "year",
        }
        return {k: v for k, v in f.items() if v}

    def _clear_filters() -> None:
        for v in (name_v, year_v, form_v, email_v, parent_v, send_v,
                  dobf_v, dobt_v, phone_v, pcon_v):
            v.set("")
        sort_v.set("year")
        for i in tree.get_children():
            tree.delete(i)
        summary_var.set("No filters applied yet.")
        status_var.set("")
        host.status_var.set("Advanced search cleared")

    def _do_adv_search() -> None:
        filters = _collect_filters()
        for i in tree.get_children():
            tree.delete(i)
        if not filters or set(filters) == {"sort_by"}:
            summary_var.set("No filters applied — showing all pupils.")
        else:
            active = ", ".join(f"{k}={v}" for k, v in filters.items()
                               if k != "sort_by")
            summary_var.set(f"Active filters: {active or '(none)'}")
        try:
            results = data.advanced_search(filters)
        except ValidationError as e:
            status_var.set(f"Filter error: {e}")
            messagebox.showerror("Advanced search", str(e), parent=host.root)
            return
        except Exception as e:
            logger.exception("advanced_search failed in GUI")
            status_var.set("Search failed — see logs.")
            messagebox.showerror(
                "Advanced search",
                f"Search failed:\n\n{e}\n\nSee logs for details.",
                parent=host.root,
            )
            return
        for p in results:
            tree.insert("", "end", iid=p.pupil_id, values=(
                p.pupil_id, p.year_group, p.form_group or "-",
                p.full_name, p.date_of_birth or "-",
                p.email, p.parent_name or "-", p.send_status or "-",
            ))
        status_var.set(f"{len(results)} match(es)")
        host.status_var.set(f"Advanced search: {len(results)} match(es)")

    def _open_selected() -> None:
        sel = tree.focus()
        if not sel:
            messagebox.showinfo("Advanced search",
                                "Select a pupil first (or double-click a row).",
                                parent=host.root)
            return
        open_edit_pupil(host, sel, on_done=_do_adv_search)

    # Initial empty results
    host.status_var.set("Advanced search ready")


@_safe_view
def open_profile(host) -> None:
    logger.debug("GUI: open_profile")
    root = _clear(host)
    _header(root, "Pupil Profile")

    bar = ttk.Frame(root)
    bar.pack(fill="x", pady=(0, 8))
    ttk.Label(bar, text="Pupil ID:").pack(side="left", padx=(0, 6))
    pidvar = tk.StringVar()
    entry = ttk.Entry(bar, textvariable=pidvar, width=20)
    entry.pack(side="left")
    entry.focus_set()

    body = ttk.Frame(root, padding=(0, 8))
    body.pack(fill="both", expand=True)

    def _load() -> None:
        for w in body.winfo_children():
            w.destroy()
        pid = pidvar.get().strip()
        if not pid:
            ttk.Label(body, text="Enter a pupil ID and press Load.",
                      foreground="#666").pack(anchor="w")
            return
        try:
            p = data.get_pupil(pid)
        except Exception:
            logger.exception("Profile lookup failed for id=%s", pid)
            ttk.Label(body, text="Lookup failed — see logs.",
                      foreground="#a00").pack(anchor="w")
            return
        if p is None:
            ttk.Label(body, text="No pupil with that ID.",
                      foreground="#a00").pack(anchor="w")
            return
        rows = [
            ("Name", p.full_name),
            ("Year group", p.year_group),
            ("Form group", p.form_group or "-"),
            ("Date of birth", p.date_of_birth or "-"),
            ("Email", p.email),
            ("Phone", p.phone or "-"),
            ("Parent", p.parent_name or "-"),
            ("Parent phone", p.parent_phone or "-"),
            ("SEND", p.send_status or "-"),
        ]
        for i, (lbl, val) in enumerate(rows):
            ttk.Label(body, text=f"{lbl}:", foreground="#555").grid(
                row=i, column=0, sticky="w", padx=(0, 12), pady=2)
            ttk.Label(body, text=val).grid(row=i, column=1, sticky="w", pady=2)
        ttk.Button(body, text="Edit",
                   command=lambda: open_edit_pupil(host, p.pupil_id)).grid(
            row=len(rows), column=0, columnspan=2, sticky="w", pady=(10, 0))

    ttk.Button(bar, text="Load", command=_load).pack(side="left", padx=4)
    entry.bind("<Return>", lambda _e: _load())
