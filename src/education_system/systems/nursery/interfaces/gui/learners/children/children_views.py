"""Tkinter views for Child Directory (Nursery System).

Renders into the shared content pane of ``gui_main.NurseryMainGUI`` (the
``host``). Provides a directory with a tree + toolbar, an add/edit form
dialog, a search screen and a profile screen — the GUI counterparts of the
flows in ``children_cli.py``.

Every entry point is wrapped by :func:`_safe_view`: domain/DB errors are
logged and surfaced in a dialog rather than crashing the GUI. A legacy
:func:`build` is kept so the old placeholder call site still works.
"""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable

from education_system.platform.delivery.gui.date_picker import (
    DatePicker,
    birth_years,
    recent_years,
)
from education_system.systems.nursery.domain.learners.children import children as data
from education_system.systems.nursery.domain.learners.children import primary_transfer
from education_system.systems.nursery.domain.learners.children.children import (
    FUNDED_HOURS_OPTIONS,
    ROOMS,
    ValidationError,
)

logger = logging.getLogger(__name__)


def _safe_view(func: Callable[..., None]) -> Callable[..., None]:
    """Catch unexpected errors in a Tk view; log and show an error dialog."""
    @functools.wraps(func)
    def wrapper(host, *args, **kwargs):
        parent = getattr(host, "root", None)
        try:
            return func(host, *args, **kwargs)
        except ValidationError as e:
            logger.warning("%s validation: %s", func.__name__, e)
            try:
                messagebox.showerror(func.__name__, str(e), parent=parent)
            except Exception:
                logger.debug("Could not show validation dialog", exc_info=True)
        except Exception as e:  # noqa: BLE001 - last-resort GUI guard
            logger.exception("%s failed", func.__name__)
            try:
                messagebox.showerror(
                    "Error",
                    f"An unexpected error occurred:\n\n{e}\n\nSee logs for details.",
                    parent=parent,
                )
            except Exception:
                logger.debug("Could not show error dialog", exc_info=True)
    return wrapper


def _clear(host) -> ttk.Frame:
    host._clear_content()
    assert host.content_frame is not None
    return host.content_frame


def _header(parent: ttk.Frame, title: str) -> None:
    ttk.Label(parent, text=title, font=("", 16, "bold")).pack(
        anchor="w", pady=(0, 8))


def _key_person_choices() -> list[tuple[str, str]]:
    try:
        return data.list_key_person_choices()
    except Exception:
        logger.exception("Could not load key-person choices")
        return []


# ── Directory ────────────────────────────────────────────────────────────────

@_safe_view
def open_directory(host) -> None:
    logger.debug("GUI: open_directory")
    root = _clear(host)
    _header(root, "Child Directory")

    show_left = tk.BooleanVar(value=False)

    bar = ttk.Frame(root)
    bar.pack(fill="x", pady=(0, 8))
    ttk.Button(bar, text="Add Child",
               command=lambda: open_add_child(host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Edit Selected",
               command=lambda: _edit_selected(tree, host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Delete Selected",
               command=lambda: _delete_selected(tree, host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Move to Primary School",
               command=lambda: _move_selected_to_primary(tree, host)).pack(
        side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: _refresh(tree, show_left.get())).pack(
        side="left", padx=2)
    ttk.Checkbutton(
        bar, text="Show leavers", variable=show_left,
        command=lambda: _refresh(tree, show_left.get()),
    ).pack(side="left", padx=(12, 2))

    cols = ("id", "name", "room", "funded", "key_person", "status")
    tree = ttk.Treeview(root, columns=cols, show="headings", height=20)
    for c, label, w in [
        ("id", "ID", 80), ("name", "Name", 200), ("room", "Room", 130),
        ("funded", "Funded hours", 150), ("key_person", "Key person", 180),
        ("status", "Status", 70),
    ]:
        tree.heading(c, text=label)
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True)
    tree.bind("<Double-1>", lambda _e: _edit_selected(tree, host))

    _refresh(tree, show_left.get())
    host.status_var.set("Child directory loaded")


def _refresh(tree: ttk.Treeview, include_left: bool = False) -> None:
    for i in tree.get_children():
        tree.delete(i)
    try:
        rows = data.list_children(include_left=include_left)
    except Exception:
        logger.exception("Could not refresh child directory")
        try:
            messagebox.showerror(
                "Child directory",
                "Could not load the child list — see logs for details.",
            )
        except Exception:
            logger.debug("Could not show refresh-error dialog", exc_info=True)
        return
    for c in rows:
        tree.insert("", "end", iid=c.pupil_id, values=(
            c.pupil_id, c.full_name, c.room or "-",
            c.funded_hours or "-", c.key_person_name or "-",
            c.roll_status_label,
        ))


def _edit_selected(tree: ttk.Treeview, host) -> None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Edit child", "Select a child first.",
                            parent=host.root)
        return
    open_edit_child(host, sel, on_done=lambda: _refresh(tree))


def _delete_selected(tree: ttk.Treeview, host) -> None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Delete child", "Select a child first.",
                            parent=host.root)
        return
    try:
        c = data.get_child(sel)
    except Exception:
        logger.exception("Lookup failed before delete for id=%s", sel)
        messagebox.showerror("Delete child", "Could not look up child.",
                             parent=host.root)
        return
    if c is None:
        return
    if not messagebox.askyesno(
            "Delete child",
            f"Permanently delete {c.full_name} ({c.pupil_id})?\n\n"
            "To keep the record but take the child off roll, edit and set "
            "the roll status to 'Left' instead.",
            parent=host.root):
        return
    try:
        data.delete_child(sel)
    except Exception as e:  # noqa: BLE001
        logger.exception("Failed to delete child id=%s", sel)
        messagebox.showerror("Delete child",
                             f"Could not delete child:\n\n{e}",
                             parent=host.root)
        return
    _refresh(tree)
    host.status_var.set(f"Deleted child {sel}")
    logger.info("GUI deleted child %s", sel)


# ── Move to Primary School ───────────────────────────────────────────────────

def _open_move_dialog(host, c: data.Child, *, on_success: Callable[[], None]) -> None:
    """Confirm year group / class, run the move, and report the new pupil."""
    dlg = tk.Toplevel(host.root)
    dlg.title("Move to Primary School")
    dlg.transient(host.root)
    dlg.geometry("440x240")
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped", exc_info=True)

    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    ttk.Label(
        frm,
        text=f"Move {c.full_name} ({c.pupil_id}) into the primary school system?",
        wraplength=400,
        justify="left",
    ).pack(anchor="w", pady=(0, 10))

    year_group = tk.StringVar(value=primary_transfer.DEFAULT_YEAR_GROUP)
    class_name = tk.StringVar()
    medical_consent = tk.BooleanVar(value=False)
    support_consent = tk.BooleanVar(value=False)

    grid = ttk.Frame(frm)
    grid.pack(fill="x", expand=True)
    ttk.Label(grid, text="Year group:").grid(row=0, column=0, sticky="w", pady=3)
    ttk.Combobox(grid, textvariable=year_group,
                 values=list(primary_transfer.primary_year_groups()),
                 state="readonly", width=29).grid(row=0, column=1, sticky="ew", pady=3)
    ttk.Label(grid, text="Class (optional):").grid(row=1, column=0, sticky="w",
                                                    pady=3)
    ttk.Entry(grid, textvariable=class_name, width=32).grid(
        row=1, column=1, sticky="ew", pady=3)
    # The handover spec treats medical, SEND and communication detail as
    # sensitive: it crosses only with the parent's recorded consent, and
    # medical alerts are required, so the move needs that one.
    ttk.Checkbutton(
        grid, variable=medical_consent,
        text="Parent consents to sharing allergies and medical alerts (required)",
    ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(8, 2))
    ttk.Checkbutton(
        grid, variable=support_consent,
        text="Parent consents to sharing SEND and communication needs",
    ).grid(row=3, column=0, columnspan=2, sticky="w", pady=2)
    grid.columnconfigure(1, weight=1)

    def _go() -> None:
        if not messagebox.askyesno(
                "Move to Primary School",
                "This will hand the child over to the primary school through "
                "the platform and take them off the nursery roll (status set "
                "to 'left'; the nursery record is kept). Continue?",
                parent=dlg):
            return
        try:
            result = primary_transfer.move_to_primary_school(
                c.pupil_id,
                year_group=year_group.get().strip() or None,
                class_name=class_name.get().strip() or None,
                consent=primary_transfer.consent_for(
                    medical=medical_consent.get(),
                    support=support_consent.get()),
            )
        except ValidationError as e:
            messagebox.showerror("Move to Primary School", str(e), parent=dlg)
            return
        except Exception as e:  # noqa: BLE001
            logger.exception("Primary transfer failed for %s", c.pupil_id)
            messagebox.showerror(
                "Move to Primary School",
                f"Could not move child:\n\n{e}\n\nSee logs for details.",
                parent=dlg,
            )
            return
        host.status_var.set(
            f"Moved {c.pupil_id} to primary as {result.primary_pupil_id}")
        extra = ""
        if result.withheld:
            extra += "\nNot shared (no consent): " + ", ".join(result.withheld)
        if result.warnings:
            extra += "\n\n" + "\n".join(result.warnings)
        messagebox.showinfo(
            "Moved to Primary School",
            "Primary pupil created.\n\n"
            f"Primary ID: {result.primary_pupil_id}\n"
            f"Year group: {result.year_group}\n"
            f"School email: {result.primary_email}" + extra,
            parent=dlg,
        )
        dlg.destroy()
        try:
            on_success()
        except Exception:
            logger.exception("on_success callback failed after primary transfer")

    btns = ttk.Frame(frm)
    btns.pack(fill="x", pady=(12, 0))
    ttk.Button(btns, text="Move", command=_go).pack(side="right")
    ttk.Button(btns, text="Cancel",
               command=dlg.destroy).pack(side="right", padx=(0, 8))


def _lookup_movable(host, child_id: str) -> data.Child | None:
    """Fetch a child and verify they can still be moved; else show why."""
    try:
        c = data.get_child(child_id)
    except Exception:
        logger.exception("Lookup failed before primary transfer for id=%s",
                         child_id)
        messagebox.showerror("Move to Primary School", "Could not look up child.",
                             parent=host.root)
        return None
    if c is None:
        messagebox.showerror("Move to Primary School",
                             f"No child with id {child_id}", parent=host.root)
        return None
    if c.status == "left":
        messagebox.showinfo(
            "Move to Primary School",
            f"{c.full_name} ({c.pupil_id}) has already left the nursery.",
            parent=host.root)
        return None
    return c


def _move_selected_to_primary(tree: ttk.Treeview, host) -> None:
    """Directory toolbar flow — move the child selected in the tree."""
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Move to Primary School", "Select a child first.",
                            parent=host.root)
        return
    c = _lookup_movable(host, sel)
    if c is not None:
        _open_move_dialog(host, c, on_success=lambda: _refresh(tree))


@_safe_view
def open_move_to_primary(host) -> None:
    """Menu-driven screen — look up a child by ID and move them to primary."""
    logger.debug("GUI: open_move_to_primary")
    root = _clear(host)
    _header(root, "Move to Primary School")

    ttk.Label(
        root,
        text="Move a child onto the primary school roll (Reception by "
             "default). The nursery record is kept and marked as 'left'.",
        foreground="#555", wraplength=600, justify="left",
    ).pack(anchor="w", pady=(0, 8))

    bar = ttk.Frame(root)
    bar.pack(fill="x", pady=(0, 8))
    ttk.Label(bar, text="Child ID:").pack(side="left", padx=(0, 6))
    pidvar = tk.StringVar()
    entry = ttk.Entry(bar, textvariable=pidvar, width=20)
    entry.pack(side="left")
    entry.focus_set()

    def _go() -> None:
        pid = pidvar.get().strip()
        if not pid:
            messagebox.showinfo("Move to Primary School", "Enter a child ID.",
                                parent=host.root)
            return
        c = _lookup_movable(host, pid)
        if c is not None:
            _open_move_dialog(host, c, on_success=lambda: open_move_to_primary(host))

    ttk.Button(bar, text="Move…", command=_go).pack(side="left", padx=4)
    entry.bind("<Return>", lambda _e: _go())


# ── Form dialog ──────────────────────────────────────────────────────────────
# The add/edit child form asks the same things, in the same sections and
# order, as the primary and secondary schools' Add Pupil (Identity,
# Admission, Address, Needs, Parent / carer, Medical), plus a Nursery
# section for the setting's own details. Dates and fixed lists are picked,
# never typed. Nursery has no shared GUI kit, so the few widgets it needs
# are built here on the platform DatePicker and read-only Comboboxes.

_SECTIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Identity", ("first_name", "middle_names", "last_name", "preferred_name",
                  "date_of_birth", "gender", "upn")),
    ("Admission", ("start_date", "roll_status", "left_date", "exit_reason")),
    ("Address", ("address_line1", "address_line2", "town", "postcode")),
    ("Needs", ("sen_status", "fsm_eligible", "eal", "notes")),
    ("Parent / carer", ("parent_name", "parent_relationship", "parent_phone",
                        "parent_email")),
    ("Medical", ("medical_notes",)),
    ("Nursery", ("room", "key_person", "funded_hours", "allergies")),
)
_FIELDS = [key for _title, keys in _SECTIONS for key in keys]

_LABELS = {
    "first_name": "Legal first name", "middle_names": "Middle names",
    "last_name": "Legal last name", "preferred_name": "Preferred name",
    "date_of_birth": "Date of birth", "gender": "Gender", "upn": "UPN",
    "start_date": "Start (admission) date", "roll_status": "Roll status",
    "left_date": "Leaving date", "exit_reason": "Leaving reason",
    "address_line1": "Address line 1", "address_line2": "Address line 2",
    "town": "Town", "postcode": "Postcode", "sen_status": "SEN",
    "fsm_eligible": "Eligible for free school meals",
    "eal": "English as an additional language", "notes": "Notes",
    "parent_name": "Name", "parent_relationship": "Relationship",
    "parent_phone": "Phone", "parent_email": "E-mail",
    "medical_notes": "Medical / care notes",
    "room": "Room", "key_person": "Key person", "funded_hours": "Funded hours",
    "allergies": "Allergies",
}
#: Required on Add Child (as on the schools' Add Pupil).
_REQUIRED = {"first_name", "last_name", "date_of_birth", "gender"}
_CHECKS = {"fsm_eligible", "eal"}
_TEXTS = {"notes": 3, "medical_notes": 4}
_DATES = {"date_of_birth", "start_date", "left_date"}

_SEN_CHOICES = tuple((k, f"{k} – {v}") for k, v in data.SEN_STATUSES.items())
_ROLL_CHOICES = tuple((k, data.ROLL_STATUS_LABELS[k]) for k in data.ROLL_STATUSES)


def _truthy(value: Any) -> bool:
    return str(value).strip().lower() in ("1", "true", "yes", "y")


def _initial_from(c: data.Child) -> dict[str, Any]:
    """The edit form's starting values for child *c*."""
    return {key: getattr(c, key, None) for key in _FIELDS}


def _room_choices() -> list[str]:
    """The setting's rooms (Rooms screen), else the default age bands."""
    try:
        from education_system.systems.nursery.domain.operations.rooms import rooms
        names = rooms.list_room_choices(open_only=True)
    except Exception:
        logger.exception("Could not load room choices")
        names = []
    return list(dict.fromkeys([*names, *ROOMS]))


class _Choice(ttk.Combobox):
    """A read-only drop-down of ``(value, label)`` pairs; ``value()`` is
    what is saved. A stored value the list no longer offers stays visible
    rather than being silently blanked."""

    def __init__(self, master: tk.Misc, choices: Any, current: str = "", *,
                 blank: bool = False, width: int = 28) -> None:
        pairs = [(str(c[0]), str(c[1])) if isinstance(c, (tuple, list))
                 else (str(c), str(c)) for c in choices if c not in ("",)]
        if blank:
            pairs.insert(0, ("", ""))
        if current and current not in {v for v, _l in pairs}:
            pairs.append((current, current))
        self._by_label = {lbl: val for val, lbl in pairs}
        super().__init__(master, values=[lbl for _v, lbl in pairs],
                         state="readonly", width=width)
        self.set(dict(pairs).get(current, ""))

    def value(self) -> str:
        return self._by_label.get(self.get(), "")


def _date_picker(master: tk.Misc, key: str, current: str) -> DatePicker:
    years = (birth_years(youngest=0, oldest=8) if key == "date_of_birth"
             else recent_years(ahead=1, back=8))
    if current[:4].isdigit() and current[:4] not in years:
        years = sorted({*years, current[:4]}, reverse=True)
    return DatePicker(master, value=current or None, years=years)


def _set_date_enabled(picker: DatePicker, enabled: bool) -> None:
    for box in (picker.cb_day, picker.cb_month, picker.cb_year):
        box.configure(state="readonly" if enabled else "disabled")
    for child in picker.winfo_children():
        if isinstance(child, ttk.Button):
            child.state(["!disabled"] if enabled else ["disabled"])


def _scrolled_form(win: tk.Misc, padding: int = 12) -> tuple[ttk.Frame, ttk.Frame]:
    """``(body, footer)`` packed into *win*: fields go in *body*, which
    scrolls on a small screen; Save/Cancel go in *footer*, which stays
    visible however tall the form is."""
    footer = ttk.Frame(win, padding=(padding, 6, padding, padding))
    footer.pack(side="bottom", fill="x")
    ttk.Separator(win, orient="horizontal").pack(side="bottom", fill="x")
    holder = ttk.Frame(win)
    holder.pack(side="top", fill="both", expand=True)
    canvas = tk.Canvas(holder, highlightthickness=0, borderwidth=0)
    bar = ttk.Scrollbar(holder, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=bar.set)
    bar.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)
    body = ttk.Frame(canvas, padding=padding)
    item = canvas.create_window(0, 0, window=body, anchor="nw")
    body.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.bind("<Configure>",
                lambda e: canvas.itemconfigure(item, width=max(e.width, body.winfo_reqwidth())))

    def wheel(e: tk.Event) -> str | None:
        if isinstance(e.widget, (tk.Text, tk.Listbox)):
            return None
        if body.winfo_reqheight() <= canvas.winfo_height():
            return None
        canvas.yview_scroll(-1 if (getattr(e, "num", None) == 4
                                   or getattr(e, "delta", 0) > 0) else 1, "units")
        return "break"

    for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
        win.bind(seq, wheel, add="+")
    return body, footer


def _form_dialog(host, title: str, initial: dict[str, Any] | None = None,
                 *, is_edit: bool = False) -> dict[str, str] | None:
    """The add/edit child form. Modal: waits for Save or Cancel and returns
    the field values as text (or None when cancelled)."""
    import datetime as _dt

    from education_system.platform.delivery.gui import window_sizing

    adding = not is_edit
    dlg = tk.Toplevel(host.root)
    dlg.title(title)
    dlg.transient(host.root)
    window_sizing.fit(dlg, "900x720", (760, 560))
    dlg.update_idletasks()
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped — dialog not viewable", exc_info=True)

    body, footer = _scrolled_form(dlg)
    body.columnconfigure(0, weight=1, uniform="f")
    body.columnconfigure(1, weight=1, uniform="f")

    initial = dict(initial or {})
    if adding:
        initial.setdefault("start_date", _dt.date.today().isoformat())
        initial.setdefault("roll_status", data.ON_ROLL)
        initial.setdefault("sen_status", "N")
    kp_choices = _key_person_choices()

    vars_: dict[str, tk.Variable] = {}
    texts: dict[str, tk.Text] = {}
    dates: dict[str, DatePicker] = {}
    choices: dict[str, _Choice] = {}

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
        if key in _DATES:
            dates[key] = _date_picker(frame, key, start(key))
            return dates[key]
        pick: _Choice | None = None
        if key == "gender":
            pick = _Choice(frame, data.GENDERS, start(key), blank=True, width=18)
        elif key == "roll_status":
            pick = _Choice(frame, _ROLL_CHOICES, start(key), width=12)
        elif key == "exit_reason":
            pick = _Choice(frame, data.LEAVING_REASONS, start(key), blank=True,
                           width=26)
        elif key == "sen_status":
            pick = _Choice(frame, _SEN_CHOICES, start(key), blank=not adding,
                           width=30)
        elif key == "parent_relationship":
            pick = _Choice(frame, data.PARENT_RELATIONSHIPS, start(key),
                           blank=True, width=16)
        elif key == "room":
            pick = _Choice(frame, _room_choices(), start(key), blank=True)
        elif key == "key_person":
            pick = _Choice(frame, kp_choices, start(key), blank=True, width=32)
        elif key == "funded_hours":
            pick = _Choice(frame, FUNDED_HOURS_OPTIONS, start(key), blank=True)
        if pick is not None:
            choices[key] = pick
            return pick
        sv = tk.StringVar(value=start(key))
        vars_[key] = sv
        width = 12 if key in ("postcode", "upn") else 30
        return ttk.Entry(frame, textvariable=sv, width=width)

    for n, (section, keys) in enumerate(_SECTIONS):
        box = ttk.LabelFrame(body, text=section, padding=10)
        box.grid(row=n // 2, column=n % 2, sticky="nsew", padx=4, pady=4)
        box.columnconfigure(1, weight=1)
        for r, key in enumerate(keys):
            widget = make(box, key)
            if key in _CHECKS:
                widget.grid(row=r, column=0, columnspan=2, sticky="w", pady=2)
                continue
            star = " *" if adding and key in _REQUIRED else ""
            ttk.Label(box, text=f"{_LABELS[key]}{star}").grid(
                row=r, column=0, sticky="nw", padx=(0, 8), pady=3)
            widget.grid(row=r, column=1, sticky="ew" if key in _TEXTS else "w", pady=3)

    # Leaving date / reason only apply to a child who has left.
    def _sync_leaving(*_a: Any) -> None:
        left = choices["roll_status"].value() == "left"
        _set_date_enabled(dates["left_date"], left)
        choices["exit_reason"].configure(state="readonly" if left else "disabled")

    choices["roll_status"].bind("<<ComboboxSelected>>", _sync_leaving, add="+")
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
            elif key in dates:
                out[key] = dates[key].get()
            elif key in choices:
                out[key] = choices[key].value()
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
def open_add_child(host) -> None:
    logger.debug("GUI: open_add_child")
    root = _clear(host)
    _header(root, "Add Child")
    ttk.Label(root, text="Opening add-child form…", foreground="#666").pack(
        anchor="w")
    fields = _form_dialog(host, "Add Child")
    if not fields:
        host.status_var.set("Add child cancelled")
        open_directory(host)
        return
    try:
        try:
            c = data.create_child(fields, complete=True, check_duplicate=True)
        except data.DuplicateChild as dup:
            if not messagebox.askyesno(
                    "Possible duplicate",
                    f"{dup}\n\nAdd this as a different child anyway?",
                    parent=host.root):
                host.status_var.set("Add child cancelled (possible duplicate)")
                open_directory(host)
                return
            c = data.create_child(fields, complete=True)
    except ValidationError as e:
        messagebox.showerror("Add child", str(e), parent=host.root)
        open_directory(host)
        return
    messagebox.showinfo(
        "Child added",
        f"Created {c.full_name}\nID: {c.pupil_id}\nRoom: {c.room or '-'}",
        parent=host.root,
    )
    host.status_var.set(f"Added child {c.pupil_id}")
    open_directory(host)


@_safe_view
def open_edit_child(host, pupil_id: str, *, on_done=None) -> None:
    logger.debug("GUI: open_edit_child(%s)", pupil_id)
    c = data.get_child(pupil_id)
    if c is None:
        messagebox.showerror("Edit child", f"No child with id {pupil_id}",
                             parent=host.root)
        return
    fields = _form_dialog(host, f"Edit {c.full_name}", initial=_initial_from(c),
                          is_edit=True)
    if not fields:
        return
    try:
        data.update_child(pupil_id, fields)
    except ValidationError as e:
        messagebox.showerror("Edit child", str(e), parent=host.root)
        return
    host.status_var.set(f"Updated child {pupil_id}")
    if on_done:
        try:
            on_done()
        except Exception:
            logger.exception("on_done callback failed after edit")


# ── Search ───────────────────────────────────────────────────────────────────

@_safe_view
def open_search(host) -> None:
    logger.debug("GUI: open_search")
    root = _clear(host)
    _header(root, "Search Children")

    bar = ttk.Frame(root)
    bar.pack(fill="x", pady=(0, 8))
    ttk.Label(bar, text="Query:").pack(side="left", padx=(0, 6))
    qvar = tk.StringVar()
    entry = ttk.Entry(bar, textvariable=qvar, width=40)
    entry.pack(side="left")
    entry.focus_set()

    cols = ("id", "name", "room", "funded", "parent")
    tree = ttk.Treeview(root, columns=cols, show="headings", height=20)
    for c, label, w in [
        ("id", "ID", 80), ("name", "Name", 200), ("room", "Room", 130),
        ("funded", "Funded hours", 150), ("parent", "Parent", 200),
    ]:
        tree.heading(c, text=label)
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True, pady=(8, 0))
    tree.bind("<Double-1>",
              lambda _e: _open_profile_for(host, tree.focus()) if tree.focus()
              else None)

    status = ttk.Label(root, text="", foreground="#666")
    status.pack(anchor="w", pady=(6, 0))

    def _do_search(*_a) -> None:
        for i in tree.get_children():
            tree.delete(i)
        try:
            rows = data.search_children(qvar.get())
        except Exception:
            logger.exception("Search failed")
            status.config(text="Search failed — see logs", foreground="#a00")
            return
        for c in rows:
            tree.insert("", "end", iid=c.pupil_id, values=(
                c.pupil_id, c.full_name, c.room or "-",
                c.funded_hours or "-", c.parent_name or "-",
            ))
        status.config(text=f"{len(rows)} match(es)", foreground="#666")

    ttk.Button(bar, text="Search", command=_do_search).pack(side="left", padx=4)
    entry.bind("<Return>", _do_search)
    _do_search()


# ── Profile ──────────────────────────────────────────────────────────────────

def _open_profile_for(host, pupil_id: str) -> None:
    open_profile(host, preset_id=pupil_id)


@_safe_view
def open_profile(host, preset_id: str | None = None) -> None:
    logger.debug("GUI: open_profile")
    root = _clear(host)
    _header(root, "Child Profile")

    bar = ttk.Frame(root)
    bar.pack(fill="x", pady=(0, 8))
    ttk.Label(bar, text="Child ID:").pack(side="left", padx=(0, 6))
    pidvar = tk.StringVar(value=preset_id or "")
    entry = ttk.Entry(bar, textvariable=pidvar, width=20)
    entry.pack(side="left")
    entry.focus_set()

    # The profile runs to seven sections, so it scrolls; Edit sits below it.
    holder = ttk.Frame(root)
    holder.pack(fill="both", expand=True)
    body, footer = _scrolled_form(holder, padding=4)

    def _load() -> None:
        for w in (*body.winfo_children(), *footer.winfo_children()):
            w.destroy()
        pid = pidvar.get().strip()
        if not pid:
            ttk.Label(body, text="Enter a child ID and press Load.",
                      foreground="#666").pack(anchor="w")
            return
        try:
            c = data.get_child(pid)
        except Exception:
            logger.exception("Profile lookup failed for id=%s", pid)
            ttk.Label(body, text="Lookup failed — see logs.",
                      foreground="#a00").pack(anchor="w")
            return
        if c is None:
            ttk.Label(body, text="No child with that ID.",
                      foreground="#a00").pack(anchor="w")
            return
        r = 0
        for section, items in _profile_sections(c):
            ttk.Label(body, text=section, font=("", 11, "bold")).grid(
                row=r, column=0, columnspan=2, sticky="w", pady=(8 if r else 0, 2))
            r += 1
            for lbl, val in items:
                ttk.Label(body, text=f"{lbl}:", foreground="#555").grid(
                    row=r, column=0, sticky="nw", padx=(12, 12), pady=1)
                ttk.Label(body, text=val, wraplength=480, justify="left").grid(
                    row=r, column=1, sticky="w", pady=1)
                r += 1
        ttk.Button(footer, text="Edit",
                   command=lambda: open_edit_child(host, c.pupil_id)).pack(side="left")

    ttk.Button(bar, text="Load", command=_load).pack(side="left", padx=4)
    entry.bind("<Return>", lambda _e: _load())
    if preset_id:
        _load()


def _yes_no(value: bool) -> str:
    return "Yes" if value else "No"


def _profile_sections(c: data.Child) -> list[tuple[str, list[tuple[str, str]]]]:
    """The profile, in the same sections as the add/edit form."""
    leaving = []
    if c.status == "left":
        leaving = [("Leaving date", c.left_date or "-"),
                   ("Leaving reason", c.exit_reason or "-")]
    return [
        ("Identity", [
            ("Name", c.full_name),
            ("Legal name", c.legal_name),
            ("Preferred name", c.preferred_name or "-"),
            ("Date of birth", c.date_of_birth or "-"),
            ("Gender", c.gender or "-"),
            ("UPN", c.upn or "Not recorded"),
            ("Child ID", c.pupil_id),
        ]),
        ("Admission", [
            ("Start date", c.start_date or "-"),
            ("Roll status", c.roll_status_label),
            *leaving,
        ]),
        ("Address", [
            ("Address", ", ".join(x for x in (c.address_line1, c.address_line2) if x)
             or "-"),
            ("Town", c.town or "-"),
            ("Postcode", c.postcode or "-"),
        ]),
        ("Needs", [
            ("SEN", f"{c.sen_status} \u2013 {c.sen_label}" if c.sen_status
             else "Not recorded"),
            ("Free school meals", "Eligible" if c.fsm_eligible else "Not eligible"),
            ("English as an additional language", _yes_no(c.eal)),
            ("Notes", c.notes or "-"),
        ]),
        ("Parent / carer", [
            ("Parent / carer", c.parent_name or "-"),
            ("Relationship", c.parent_relationship or "-"),
            ("Parent phone", c.parent_phone or "-"),
            ("Parent email", c.parent_email or "-"),
        ]),
        ("Medical", [
            ("Medical notes", c.medical_notes or "-"),
        ]),
        ("Nursery", [
            ("Room", c.room or "-"),
            ("Key person", c.key_person_name or c.key_person or "-"),
            ("Funded hours", c.funded_hours or "-"),
            ("Allergies", c.allergies or "-"),
        ]),
    ]


# ── Legacy placeholder entry point ───────────────────────────────────────────

def build(parent: tk.Misc, auth=None) -> ttk.Frame:
    """Standalone frame fallback (kept for the old placeholder call site)."""
    frame = ttk.Frame(parent, padding=16)
    ttk.Label(frame, text="Child Directory",
              font=("", 14, "bold")).pack(anchor="w", pady=(0, 6))
    ttk.Label(
        frame,
        text="Open the Child Directory from the navigation menu.",
    ).pack(anchor="w")
    return frame
