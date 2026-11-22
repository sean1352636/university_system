"""Tk GUI views for pupil CRUD in the Primary School System."""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable

from education_system.systems.primary.domain.learners.pupils import pupils as data
from education_system.systems.primary.domain.learners.pupils import secondary_transfer
from education_system.systems.primary.domain.learners.pupils.pupils import (
    ValidationError, YEAR_GROUPS,
)
from education_system.systems.primary.domain.admissions.enrolment.enrolment import (
    _bump_class,
)
from education_system.systems.primary.interfaces.gui import kit

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


#: Every key the add/edit form returns, by section. The same things the
#: secondary school's Add Pupil asks (identity, school, address, needs) plus
#: the parent/carer and medical details both systems now ask on admission.
_SECTIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Identity", ("first_name", "middle_names", "last_name", "preferred_name",
                  "date_of_birth", "gender", "upn")),
    ("School", ("year_group", "class_name", "admission_date", "roll_status",
                "left_date", "exit_reason")),
    ("Address", ("address_line1", "address_line2", "town", "postcode")),
    ("Needs", ("sen_status", "fsm_eligible", "eal", "notes")),
    ("Parent / carer", ("parent_name", "parent_relationship", "parent_phone",
                        "parent_email")),
    ("Medical", ("medical_notes",)),
)
_FIELDS = [key for _title, keys in _SECTIONS for key in keys]

_LABELS = {
    "first_name": "Legal first name", "middle_names": "Middle names",
    "last_name": "Legal last name", "preferred_name": "Preferred name",
    "date_of_birth": "Date of birth", "gender": "Gender", "upn": "UPN",
    "year_group": "Year group", "class_name": "Class",
    "admission_date": "Admission date", "roll_status": "Roll status",
    "left_date": "Leaving date", "exit_reason": "Leaving reason",
    "address_line1": "Address line 1", "address_line2": "Address line 2",
    "town": "Town", "postcode": "Postcode", "sen_status": "SEN",
    "fsm_eligible": "Eligible for free school meals",
    "eal": "English as an additional language", "notes": "Notes",
    "parent_name": "Name", "parent_relationship": "Relationship",
    "parent_phone": "Phone", "parent_email": "E-mail",
    "medical_notes": "Medical / care notes",
}
#: Required on Add Pupil (as in the secondary school).
_REQUIRED = {"first_name", "last_name", "date_of_birth", "gender", "year_group"}
_CHECKS = {"fsm_eligible", "eal"}
_TEXTS = {"notes": 3, "medical_notes": 4}

_SEN_CHOICES = tuple((k, f"{k} \u2013 {v}") for k, v in data.SEN_STATUSES.items())
_ROLL_CHOICES = tuple((k, data.ROLL_STATUS_LABELS[k]) for k in data.ROLL_STATUSES)


def _truthy(value: Any) -> bool:
    return str(value).strip().lower() in ("1", "true", "yes", "y")


def _initial_from(p: data.Pupil) -> dict[str, Any]:
    """The edit form's starting values for pupil *p*."""
    return {key: getattr(p, key, None) for key in _FIELDS}


def _owner(host, widget: tk.Misc | None = None) -> tk.Misc:
    """The window a pop-up or message belongs to: the page's own window
    (main window or pop-out) when known, otherwise the main window."""
    if widget is not None:
        try:
            return widget.winfo_toplevel()
        except tk.TclError:
            pass
    return getattr(host, "root", host)


def _owner_kw(owner: tk.Misc | None) -> dict[str, Any]:
    """``owner=`` for :func:`_form_dialog` only when there is one, so the
    call stays ``_form_dialog(host, title[, initial])`` otherwise."""
    return {"owner": owner} if owner is not None else {}


def _set_status(host, text: str) -> None:
    var = getattr(host, "status_var", None)
    if var is not None:
        var.set(text)


@_safe_view
def open_directory(host) -> None:
    logger.debug("GUI: open_directory")
    kit.show_page(host, "Pupil Directory", lambda parent: _draw_directory(parent, host))


def _draw_directory(parent: ttk.Frame, host) -> None:
    kit.page_heading(parent, "Pupil Directory", "Every pupil on roll.")

    bar = ttk.Frame(parent)
    bar.pack(fill="x", pady=(0, 8))
    ttk.Button(bar, text="Add Pupil",
               command=lambda: open_add_pupil(host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Edit Selected",
               command=lambda: _edit_selected(tree, host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Delete Selected",
               command=lambda: _delete_selected(tree, host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Move to Secondary",
               command=lambda: _move_selected_to_secondary(tree, host)).pack(
        side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: _refresh(tree)).pack(side="left", padx=2)

    tree = kit.tree(parent, [
        ("id", "ID", 90), ("year", "Year", 50), ("klass", "Class", 80),
        ("name", "Name", 220), ("parent", "Parent", 180), ("send", "SEND", 60),
    ], height=20, stretch=("name",))
    tree.bind("<Double-1>", lambda _e: _edit_selected(tree, host))

    _refresh(tree)
    _set_status(host, "Pupil directory loaded")


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
                parent=tree.winfo_toplevel(),
            )
        except Exception:
            pass
        return
    for p in rows:
        tree.insert("", "end", iid=p.pupil_id, values=(
            p.pupil_id, p.year_group, p.class_name or "-",
            p.full_name, p.parent_name or "-", p.send_status or "-",
        ))


def _edit_selected(tree: ttk.Treeview, host) -> None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Edit pupil", "Select a pupil first.",
                            parent=_owner(host, tree))
        return
    open_edit_pupil(host, sel, on_done=lambda: _refresh(tree), owner=tree)


def _delete_selected(tree: ttk.Treeview, host) -> None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Delete pupil", "Select a pupil first.",
                            parent=_owner(host, tree))
        return
    try:
        p = data.get_pupil(sel)
    except Exception:
        logger.exception("Lookup failed before delete for id=%s", sel)
        messagebox.showerror("Delete pupil", "Could not look up pupil.",
                             parent=_owner(host, tree))
        return
    if p is None:
        return
    if not messagebox.askyesno(
            "Delete pupil",
            f"Delete {p.full_name} ({p.pupil_id})? This cannot be undone.",
            parent=_owner(host, tree)):
        return
    try:
        data.delete_pupil(sel)
    except Exception as e:
        logger.exception("Failed to delete pupil id=%s", sel)
        messagebox.showerror("Delete pupil",
                             f"Could not delete pupil:\n\n{e}",
                             parent=_owner(host, tree))
        return
    _refresh(tree)
    _set_status(host, f"Deleted pupil {sel}")
    logger.info("GUI deleted pupil %s", sel)


def _move_selected_to_secondary(tree: ttk.Treeview, host) -> None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Move to secondary", "Select a pupil first.",
                            parent=_owner(host, tree))
        return
    try:
        p = data.get_pupil(sel)
    except Exception:
        logger.exception("Lookup failed before secondary transfer for id=%s", sel)
        messagebox.showerror("Move to secondary", "Could not look up pupil.",
                             parent=_owner(host, tree))
        return
    if p is None:
        messagebox.showerror("Move to secondary", f"No pupil with id {sel}",
                             parent=_owner(host, tree))
        return

    owner = _owner(host, tree)
    dlg = tk.Toplevel(owner)
    dlg.title("Move to Secondary School")
    dlg.transient(owner)
    dlg.geometry("440x260")
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped", exc_info=True)

    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    ttk.Label(
        frm,
        text=f"Move {p.full_name} ({p.pupil_id}) into the secondary system?",
        wraplength=400,
        justify="left",
    ).pack(anchor="w", pady=(0, 10))
    if p.year_group != "6":
        ttk.Label(
            frm,
            text=f"Current primary year group is {p.year_group}.",
            foreground="#a45",
        ).pack(anchor="w", pady=(0, 10))

    form_group = tk.StringVar()
    destination = tk.StringVar(value=secondary_transfer.DEFAULT_DESTINATION)
    notes = tk.StringVar()
    share_sensitive = tk.BooleanVar(value=False)

    grid = ttk.Frame(frm)
    grid.pack(fill="x", expand=True)
    for row, (label, var) in enumerate((
        ("Form group", form_group),
        ("Destination", destination),
        ("Notes", notes),
    )):
        ttk.Label(grid, text=f"{label}:").grid(row=row, column=0, sticky="w",
                                                pady=3)
        ttk.Entry(grid, textvariable=var, width=32).grid(
            row=row, column=1, sticky="ew", pady=3)
    # SEND, medical, pupil-premium and intervention detail are sensitive in
    # the primary→secondary handover spec: they cross only with consent.
    ttk.Checkbutton(
        grid, variable=share_sensitive,
        text="Parent consents to sharing SEND, medical and support detail",
    ).grid(row=3, column=0, columnspan=2, sticky="w", pady=(8, 2))
    grid.columnconfigure(1, weight=1)

    def _go() -> None:
        if not messagebox.askyesno(
                "Move to secondary",
                "This will hand the pupil over to the secondary school through "
                "the platform (which creates their pupil record and login), "
                "record a leaver, and take the pupil off the primary roll. "
                "The primary record is kept. Continue?",
                parent=dlg):
            return
        try:
            result = secondary_transfer.move_to_secondary_school(
                p.pupil_id,
                form_group=form_group.get().strip() or None,
                destination_school=destination.get().strip() or None,
                notes=notes.get().strip() or None,
                consent=(set(secondary_transfer.CONSENT_FIELDS)
                         if share_sensitive.get() else None),
            )
        except ValidationError as e:
            messagebox.showerror("Move to secondary", str(e), parent=dlg)
            return
        except Exception as e:
            logger.exception("Secondary transfer failed for %s", p.pupil_id)
            messagebox.showerror(
                "Move to secondary",
                f"Could not move pupil:\n\n{e}\n\nSee logs for details.",
                parent=dlg,
            )
            return

        _refresh(tree)
        _set_status(
            host, f"Moved {p.pupil_id} to secondary as {result.secondary_pupil_id}")
        password = result.password or "(login already existed — unchanged)"
        extra = ""
        if result.withheld:
            extra += "\nNot shared (no consent): " + ", ".join(result.withheld)
        if result.warnings:
            extra += "\n\n" + "\n".join(result.warnings)
        messagebox.showinfo(
            "Moved to secondary",
            "Secondary pupil created.\n\n"
            f"Secondary ID: {result.secondary_pupil_id}\n"
            f"Login email: {result.secondary_email}\n"
            f"Password: {password}\n"
            f"Leaver record: {result.leaver_id or '—'}" + extra,
            parent=dlg,
        )
        dlg.destroy()

    btns = ttk.Frame(frm)
    btns.pack(fill="x", pady=(12, 0))
    ttk.Button(btns, text="Move", command=_go).pack(side="right")
    ttk.Button(btns, text="Cancel",
               command=dlg.destroy).pack(side="right", padx=(0, 8))


def _form_dialog(host, title: str, initial: dict[str, Any] | None = None,
                 *, owner: tk.Misc | None = None) -> dict[str, str] | None:
    """The add/edit pupil form, in sections (Identity, School, Address,
    Needs, Parent / carer, Medical). Modal: waits for Save or Cancel and
    returns the field values as text (or None when cancelled)."""
    import datetime as _dt

    from education_system.platform.delivery.gui import window_sizing

    parent_win = _owner(host, owner)
    adding = initial is None
    dlg = tk.Toplevel(parent_win)
    dlg.title(title)
    dlg.transient(parent_win)
    window_sizing.fit(dlg, "900x720", (760, 560))
    dlg.update_idletasks()
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped — dialog not viewable", exc_info=True)

    body, footer = kit.scrolled_form(dlg)
    body.columnconfigure(0, weight=1, uniform="f")
    body.columnconfigure(1, weight=1, uniform="f")

    initial = dict(initial or {})
    if adding:
        initial.setdefault("admission_date", _dt.date.today().isoformat())
        initial.setdefault("roll_status", data.ON_ROLL)
        initial.setdefault("sen_status", "N")
        initial.setdefault("year_group", YEAR_GROUPS[0])
    vars_: dict[str, tk.Variable] = {}
    texts: dict[str, tk.Text] = {}
    widgets: dict[str, tk.Misc] = {}

    def start(key: str) -> str:
        v = initial.get(key)
        return "" if v is None else str(v)

    def make(frame: ttk.Frame, key: str) -> tk.Misc:
        if key in _CHECKS:
            var: tk.Variable = tk.BooleanVar(value=_truthy(initial.get(key)))
            vars_[key] = var
            return ttk.Checkbutton(frame, text=_LABELS[key], variable=var)
        if key in _TEXTS:
            t = tk.Text(frame, height=_TEXTS[key], width=34, wrap="word")
            t.insert("1.0", start(key))
            texts[key] = t
            return t
        sv = tk.StringVar(value=start(key))
        vars_[key] = sv
        if key == "year_group":
            return kit.YearGroupPicker(frame, sv)
        if key == "class_name":
            return kit.ClassPicker(frame, sv, year_group=start("year_group") or None)
        if key == "date_of_birth":
            return kit.DateField(frame, sv, years=kit.pupil_birth_years(), today=False)
        if key in ("admission_date", "left_date"):
            return kit.DateField(frame, sv)
        if key == "gender":
            return kit.ChoiceField(frame, sv, choices=data.GENDERS, blank=True, width=18)
        if key == "roll_status":
            return kit.ChoiceField(frame, sv, choices=_ROLL_CHOICES, width=12)
        if key == "exit_reason":
            return kit.ChoiceField(frame, sv, choices=data.LEAVING_REASONS, blank=True,
                                   width=26)
        if key == "sen_status":
            return kit.ChoiceField(frame, sv, choices=_SEN_CHOICES, blank=not adding,
                                   width=30)
        if key == "parent_relationship":
            return kit.ChoiceField(frame, sv, choices=data.PARENT_RELATIONSHIPS,
                                   blank=True, width=16)
        width = 12 if key in ("postcode", "upn") else 30
        return ttk.Entry(frame, textvariable=sv, width=width)

    for n, (section, keys) in enumerate(_SECTIONS):
        box = ttk.LabelFrame(body, text=section, padding=10)
        box.grid(row=n // 2, column=n % 2, sticky="nsew", padx=4, pady=4)
        box.columnconfigure(1, weight=1)
        for r, key in enumerate(keys):
            widget = make(box, key)
            widgets[key] = widget
            if key in _CHECKS:
                widget.grid(row=r, column=0, columnspan=2, sticky="w", pady=2)
                continue
            star = " *" if adding and key in _REQUIRED else ""
            ttk.Label(box, text=f"{_LABELS[key]}{star}").grid(
                row=r, column=0, sticky="nw", padx=(0, 8), pady=3)
            widget.grid(row=r, column=1, sticky="ew" if key in _TEXTS else "w", pady=3)

    # Offer the classes of the chosen year group (the box still takes a
    # class that has not been set up yet).
    cp = widgets["class_name"]
    vars_["year_group"].trace_add(
        "write", lambda *_a: cp.for_year(vars_["year_group"].get() or None))

    # Leaving date / reason only apply to a pupil who has left.
    def _sync_leaving(*_a: Any) -> None:
        left = vars_["roll_status"].get() == "left"
        widgets["left_date"].state_disabled(not left)
        widgets["exit_reason"].box.configure(state="readonly" if left else "disabled")

    vars_["roll_status"].trace_add("write", _sync_leaving)
    _sync_leaving()

    if adding:
        ttk.Label(footer, text="* required", foreground="#666").pack(side="left")
    result: dict[str, str] | None = None

    def _save() -> None:
        nonlocal result
        out: dict[str, str] = {}
        for key in _FIELDS:
            if key in texts:
                out[key] = texts[key].get("1.0", "end").strip()
            elif key in _CHECKS:
                out[key] = "yes" if vars_[key].get() else "no"
            else:
                out[key] = (vars_[key].get() or "").strip()
        if out.get("roll_status") != "left":
            out["left_date"], out["exit_reason"] = "", ""
        result = out
        dlg.destroy()

    ttk.Button(footer, text="Cancel", command=dlg.destroy).pack(side="right", padx=4)
    ttk.Button(footer, text="Save", command=_save).pack(side="right")

    dlg.wait_window()
    return result


@_safe_view
def open_add_pupil(host) -> None:
    logger.debug("GUI: open_add_pupil")
    kit.show_page(host, "Add Pupil", lambda parent: _draw_add_pupil(parent, host))
    _add_pupil_flow(host)


def _draw_add_pupil(parent: ttk.Frame, host) -> None:
    kit.page_heading(parent, "Add Pupil", "Put a new pupil on roll.")
    ttk.Label(parent, text="The add-pupil form opens in its own window.",
              foreground="#666").pack(anchor="w")
    bar = ttk.Frame(parent)
    bar.pack(fill="x", pady=(8, 0))
    ttk.Button(bar, text="Add Pupil…",
               command=lambda: _add_pupil_flow(host, owner=parent)).pack(side="left")
    ttk.Button(bar, text="Pupil Directory",
               command=lambda: open_directory(host)).pack(side="left", padx=6)


@_safe_view
def _add_pupil_flow(host, *, owner: tk.Misc | None = None) -> None:
    fields = _form_dialog(host, "Add Pupil", **_owner_kw(owner))
    if not fields:
        _set_status(host, "Add pupil cancelled")
        return
    win = _owner(host, owner)
    try:
        try:
            p = data.create_pupil(fields, complete=True, check_duplicate=True)
        except data.DuplicatePupil as dup:
            if not messagebox.askyesno(
                    "Possible duplicate",
                    f"{dup}\n\nAdd this as a different pupil anyway?", parent=win):
                _set_status(host, "Add pupil cancelled (possible duplicate)")
                return
            p = data.create_pupil(fields, complete=True)
    except ValidationError as e:
        messagebox.showerror("Add pupil", str(e), parent=win)
        return
    messagebox.showinfo(
        "Pupil added",
        f"Created {p.full_name}\nID: {p.pupil_id}\nEmail: {p.email}",
        parent=win,
    )
    open_directory(host)


@_safe_view
def open_edit_pupil(host, pupil_id: str, *, on_done=None,
                    owner: tk.Misc | None = None) -> None:
    logger.debug("GUI: open_edit_pupil(%s)", pupil_id)
    win = _owner(host, owner)
    p = data.get_pupil(pupil_id)
    if p is None:
        messagebox.showerror("Edit pupil", f"No pupil with id {pupil_id}",
                             parent=win)
        return
    initial = _initial_from(p)
    fields = _form_dialog(host, f"Edit {p.full_name}", initial=initial,
                          **_owner_kw(owner))
    if not fields:
        return
    # If the year changed but the class field wasn't touched, bump the
    # class prefix (e.g. 3A -> 4A) so it follows the pupil up.
    if (fields.get("year_group") != p.year_group
            and fields.get("class_name") == (p.class_name or "")):
        bumped = _bump_class(
            p.year_group, fields["year_group"], p.class_name)
        if bumped is not None:
            fields["class_name"] = bumped
    try:
        data.update_pupil(pupil_id, fields)
    except ValidationError as e:
        messagebox.showerror("Edit pupil", str(e), parent=win)
        return
    _set_status(host, f"Updated pupil {pupil_id}")
    if on_done:
        try:
            on_done()
        except Exception:
            logger.exception("on_done callback failed after edit")


@_safe_view
def open_search(host) -> None:
    logger.debug("GUI: open_search")
    kit.show_page(host, "Search Pupils", lambda parent: _draw_search(parent, host))


def _draw_search(parent: ttk.Frame, host) -> None:
    kit.page_heading(parent, "Search Pupils",
                     "Search by name, pupil ID, class or parent; narrow by year group.")

    bar = ttk.Frame(parent)
    bar.pack(fill="x", pady=(0, 8))
    ttk.Label(bar, text="Query:").pack(side="left", padx=(0, 6))
    qvar = tk.StringVar()
    entry = ttk.Entry(bar, textvariable=qvar, width=40)
    entry.pack(side="left")
    entry.focus_set()
    ttk.Label(bar, text="Year:").pack(side="left", padx=(12, 6))
    year_var = tk.StringVar()
    kit.YearGroupPicker(bar, year_var, blank=True).pack(side="left")

    tree = kit.tree(parent, [
        ("id", "ID", 90), ("year", "Year", 50), ("klass", "Class", 80),
        ("name", "Name", 220), ("parent", "Parent", 200),
    ], height=20, stretch=("name",))
    tree.bind("<Double-1>", lambda _e: _edit_from(tree))

    status = ttk.Label(parent, text="", foreground="#666")
    status.pack(anchor="w", pady=(6, 0))

    def _edit_from(t: ttk.Treeview) -> None:
        sel = t.focus()
        if sel:
            open_edit_pupil(host, sel, on_done=_do_search, owner=t)

    def _do_search(*_a) -> None:
        for i in tree.get_children():
            tree.delete(i)
        try:
            rows = data.search_pupils(qvar.get())
        except Exception:
            logger.exception("Search failed")
            status.config(text="Search failed — see logs", foreground="#a00")
            return
        year = year_var.get()
        if year:
            rows = [p for p in rows if p.year_group == year]
        for p in rows:
            tree.insert("", "end", iid=p.pupil_id, values=(
                p.pupil_id, p.year_group, p.class_name or "-",
                p.full_name, p.parent_name or "-",
            ))
        status.config(text=f"{len(rows)} match(es)", foreground="#666")

    ttk.Button(bar, text="Search", command=_do_search).pack(side="left", padx=4)
    entry.bind("<Return>", _do_search)
    year_var.trace_add("write", _do_search)
    _do_search()


@_safe_view
def open_profile(host) -> None:
    logger.debug("GUI: open_profile")
    kit.show_page(host, "Pupil Profile", lambda parent: _draw_profile(parent, host))


def _draw_profile(parent: ttk.Frame, host) -> None:
    kit.page_heading(parent, "Pupil Profile", "Choose a pupil to see their record.")

    bar = ttk.Frame(parent)
    bar.pack(fill="x", pady=(0, 8))
    ttk.Label(bar, text="Pupil:").pack(side="left", padx=(0, 6))
    pidvar = tk.StringVar()
    picker = kit.PupilPicker(bar, pidvar, include_off_roll=True)
    picker.pack(side="left")
    picker.box.focus_set()

    body = ttk.Frame(parent, padding=(0, 8))
    body.pack(fill="both", expand=True)

    def _load() -> None:
        for w in body.winfo_children():
            w.destroy()
        pid = pidvar.get().strip()
        if not pid:
            ttk.Label(body, text="Choose a pupil and press Load.",
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
        sections = _profile_sections(p)
        row = 0
        for title, items in sections:
            ttk.Label(body, text=title, font=("", 10, "bold")).grid(
                row=row, column=0, columnspan=2, sticky="w", pady=(8 if row else 0, 2))
            row += 1
            for lbl, val in items:
                ttk.Label(body, text=f"{lbl}:", foreground="#555").grid(
                    row=row, column=0, sticky="nw", padx=(0, 12), pady=1)
                ttk.Label(body, text=val or "-", wraplength=520, justify="left").grid(
                    row=row, column=1, sticky="w", pady=1)
                row += 1
        ttk.Button(body, text="Edit",
                   command=lambda: open_edit_pupil(host, p.pupil_id, on_done=_load,
                                                   owner=body)).grid(
            row=row, column=0, columnspan=2, sticky="w", pady=(10, 0))

    ttk.Button(bar, text="Load", command=_load).pack(side="left", padx=4)
    picker.bind_change(lambda _v: _load())
    _load()


def _yes_no(value: bool) -> str:
    return "Yes" if value else "No"


def _profile_sections(p: data.Pupil) -> list[tuple[str, list[tuple[str, str]]]]:
    """The profile, in the same sections as the add/edit form."""
    leaving = []
    if p.roll_status == "left":
        leaving = [("Leaving date", p.left_date or "-"),
                   ("Leaving reason", p.exit_reason or "-")]
    return [
        ("Identity", [
            ("Legal name", p.legal_name),
            ("Preferred name", p.preferred_name or "-"),
            ("Date of birth", p.date_of_birth or "-"),
            ("Gender", p.gender or "-"),
            ("UPN", p.upn or "Not recorded"),
            ("Pupil ID", p.pupil_id),
            ("Email", p.email),
        ]),
        ("School", [
            ("Year group", kit.YEAR_GROUP_LABELS.get(p.year_group, p.year_group)),
            ("Class", p.class_name or "-"),
            ("Admission date", p.admission_date or "-"),
            ("Roll status", p.roll_status_label),
            *leaving,
        ]),
        ("Address", [
            ("Address", ", ".join(x for x in (p.address_line1, p.address_line2) if x)
             or "-"),
            ("Town", p.town or "-"),
            ("Postcode", p.postcode or "-"),
        ]),
        ("Needs", [
            ("SEN", f"{p.sen_status} \u2013 {p.sen_label}" if p.sen_status
             else "Not recorded"),
            ("SEND", p.send_status or "-"),
            ("Free school meals", "Eligible" if p.fsm_eligible else "Not eligible"),
            ("English as an additional language", _yes_no(p.eal)),
            ("Notes", p.notes or "-"),
        ]),
        ("Parent / carer", [
            ("Parent", p.parent_name or "-"),
            ("Relationship", p.parent_relationship or "-"),
            ("Parent phone", p.parent_phone or "-"),
            ("Parent e-mail", p.parent_email or "-"),
        ]),
        ("Medical", [
            ("Medical notes", p.medical_notes or "-"),
        ]),
    ]
