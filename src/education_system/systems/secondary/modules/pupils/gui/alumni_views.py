"""Alumni screens: list with filters, selected-alumnus panel, and the new /
edit / status / promote / add-leavers / e-mail / delete dialogs. Rules live
in :mod:`modules.pupils.domain.alumni`."""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from typing import Callable

from education_system.platform.delivery.gui import window_sizing
from education_system.platform.delivery.gui.date_picker import (
    DatePicker,
    birth_years,
    recent_years,
)
from education_system.platform.delivery.gui.parented_dialogs import make_toplevel, messagebox
from education_system.systems.secondary.modules.pupils.domain import alumni as AL
from education_system.systems.secondary.modules.pupils.domain import enrolment as EN
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.gui.components import widgets as W
from education_system.systems.secondary.ui.gui.layouts.scroll import scrolled_form

logger = logging.getLogger(__name__)

_ALL = "All"
_ERRORS = (AL.ValidationError, AL.PermissionDenied, AL.NotFound)


def _problems(e: Exception) -> str:
    return W.problems(e, "Please fix:")


# ── Page ─────────────────────────────────────────────────────────────

def draw_alumni(parent: ttk.Frame, *, principal: Principal,
                open_pupil: Callable[[int], None], state: dict | None = None) -> None:
    state = state if state is not None else {}
    activity_log.record("alumni.open")
    head = ttk.Frame(parent)
    head.pack(fill="x", pady=(0, 4))
    ttk.Label(head, text="Alumni", font=("", 16, "bold")).pack(side="left")
    totals = ttk.Label(head, foreground="#555")
    totals.pack(side="left", padx=12, pady=(4, 0))

    bar = ttk.Frame(parent)
    bar.pack(fill="x", pady=(0, 4))
    status_var = tk.StringVar(value=state.get("status", _ALL))
    year_var = tk.StringVar(value=state.get("year", _ALL))
    act_var = tk.StringVar(value=state.get("activity", _ALL))
    search_var = tk.StringVar(value=state.get("search", ""))
    contact_var = tk.BooleanVar(value=state.get("contactable", False))
    ttk.Label(bar, text="Status:").pack(side="left", padx=(0, 4))
    ttk.Combobox(bar, textvariable=status_var, state="readonly", width=10,
                 values=[_ALL, *AL.STATUS_LABELS.values()]).pack(side="left", padx=(0, 10))
    ttk.Label(bar, text="Year:").pack(side="left", padx=(0, 4))
    ttk.Combobox(bar, textvariable=year_var, state="readonly", width=9,
                 values=[_ALL, *AL.leaving_year_choices()]).pack(side="left", padx=(0, 10))
    ttk.Label(bar, text="Now doing:").pack(side="left", padx=(0, 4))
    ttk.Combobox(bar, textvariable=act_var, state="readonly", width=20,
                 values=[_ALL, *AL.ACTIVITIES]).pack(side="left", padx=(0, 10))
    ttk.Label(bar, text="Search:").pack(side="left", padx=(0, 4))
    ttk.Entry(bar, textvariable=search_var, width=20).pack(side="left", padx=(0, 10))
    ttk.Checkbutton(bar, text="Can be e-mailed", variable=contact_var).pack(side="left")

    buttons = ttk.Frame(parent)
    buttons.pack(fill="x", pady=(0, 6))

    body = ttk.Panedwindow(parent, orient="vertical")
    body.pack(fill="both", expand=True)
    top = ttk.Frame(body)
    body.add(top, weight=3)
    columns = (("ref", "Ref", 80), ("name", "Name", 180), ("year", "Year left", 75),
               ("yr", "Last yr", 55), ("doing", "Now doing", 150), ("org", "Organisation", 160),
               ("contact", "E-mail", 110), ("status", "Status", 75))
    tree = ttk.Treeview(top, columns=[c for c, _h, _w in columns], show="headings",
                        selectmode="extended")
    for col, heading, width in columns:
        tree.heading(col, text=heading)
        tree.column(col, width=width, anchor="w", stretch=col in {"name", "org"})
    sb = ttk.Scrollbar(top, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=sb.set)
    tree.pack(side="left", fill="both", expand=True)
    sb.pack(side="right", fill="y")
    detail = ttk.LabelFrame(body, text="Selected alumnus", padding=8)
    body.add(detail, weight=2)
    shown: list[AL.Alumnus] = []

    def status_key() -> str | None:
        label = status_var.get()
        return next((k for k, v in AL.STATUS_LABELS.items() if v == label), None)

    def refresh(*_a) -> None:
        state.update(status=status_var.get(), year=year_var.get(), activity=act_var.get(),
                     search=search_var.get(), contactable=contact_var.get())
        keep = set(tree.selection())
        tree.delete(*tree.get_children())
        try:
            rows = AL.list_alumni(
                search=search_var.get().strip() or None, status=status_key(),
                leaving_year=None if year_var.get() == _ALL else year_var.get(),
                activity=None if act_var.get() == _ALL else act_var.get(),
                contactable=True if contact_var.get() else None)
            s = AL.summary()
        except Exception as e:  # noqa: BLE001
            logger.exception("Alumni list failed")
            totals.configure(text=f"Couldn't load alumni: {e}", foreground="#a00")
            return
        shown[:] = rows
        for a in rows:
            tree.insert("", "end", iid=str(a.alumni_id), values=(
                a.alumni_ref, a.display_name, a.leaving_year, a.last_year_group or "",
                a.current_activity or "", a.organisation or "",
                "Yes" if a.can_contact else (a.contact_problem or ""), a.status_label))
        again = [i for i in keep if tree.exists(i)]
        if again:
            tree.selection_set(again)
        totals.configure(
            foreground="#555",
            text=f"{s.total} alumni · {s.contactable} can be e-mailed · {s.can_help} happy "
                 f"to help · showing {len(rows)}")
        show_detail()

    def selected_ids() -> list[int]:
        return [int(i) for i in tree.selection()]

    def one(title: str) -> AL.Alumnus | None:
        ids = selected_ids()
        if len(ids) != 1:
            messagebox.showinfo(title, "Select one alumnus first.", parent=parent)
            return None
        return AL.get_alumnus(ids[0])

    def show_detail(_e=None) -> None:
        for child in detail.winfo_children():
            child.destroy()
        ids = selected_ids()
        if len(ids) != 1:
            ttk.Label(detail, foreground="#888", text=(
                f"{len(ids)} selected - E-mail… writes to these." if ids else
                "Select an alumnus to see their details.")).pack(anchor="w")
            return
        a = AL.get_alumnus(ids[0])
        if a is None:
            return
        _draw_detail(detail, a, open_pupil)

    status_var.trace_add("write", refresh)
    year_var.trace_add("write", refresh)
    act_var.trace_add("write", refresh)
    search_var.trace_add("write", refresh)
    contact_var.trace_add("write", refresh)
    tree.bind("<<TreeviewSelect>>", show_detail)

    def do_new() -> None:
        alumnus_form(parent, principal=principal, alumnus=None, after=refresh)

    def do_edit(_e=None) -> None:
        a = one("Edit")
        if a:
            alumnus_form(parent, principal=principal, alumnus=a, after=refresh)

    def do_status() -> None:
        a = one("Set Status")
        if a:
            status_dialog(parent, principal=principal, alumnus=a, after=refresh)

    def do_promote() -> None:
        promote_dialog(parent, principal=principal, after=refresh)

    def do_leavers() -> None:
        add_leavers_dialog(parent, principal=principal, after=refresh)

    def do_email() -> None:
        ids = selected_ids() or [a.alumni_id for a in shown]
        if not ids:
            messagebox.showinfo("E-mail", "Nobody listed to e-mail.", parent=parent)
            return
        email_dialog(parent, principal=principal, alumni_ids=ids,
                     chosen=bool(selected_ids()), after=refresh)

    def do_delete() -> None:
        a = one("Delete")
        if a:
            delete_dialog(parent, principal=principal, alumnus=a, after=refresh)

    tree.bind("<Double-1>", do_edit)
    for text, cmd in (("New…", do_new), ("Edit…", do_edit), ("Set Status…", do_status),
                      ("Promote Pupil…", do_promote), ("Add Year 11 Leavers…", do_leavers),
                      ("E-mail…", do_email), ("Delete…", do_delete)):
        ttk.Button(buttons, text=text, command=cmd).pack(side="left", padx=(0, 6))
    ttk.Button(buttons, text="↻ Refresh", command=refresh).pack(side="right")
    refresh()


def _draw_detail(frame: ttk.Frame, a: AL.Alumnus, open_pupil) -> None:
    cols = ttk.Frame(frame)
    cols.pack(fill="x")
    link = AL.pupil_link(a)

    def block(col: int, items: list[tuple[str, str]]) -> None:
        box = ttk.Frame(cols)
        box.grid(row=0, column=col, sticky="nw", padx=(0, 24))
        for r, (k, v) in enumerate(items):
            ttk.Label(box, text=f"{k}:", foreground="#555").grid(row=r, column=0, sticky="nw",
                                                                 padx=(0, 8))
            ttk.Label(box, text=v or "—", wraplength=300, justify="left").grid(
                row=r, column=1, sticky="w")

    block(0, [("Name", f"{a.first_name} {a.last_name}"
               + (f" ({a.preferred_name})" if a.preferred_name else "")),
              ("Ref", a.alumni_ref), ("Admission no.", a.admission_no or ""),
              ("Date of birth", a.date_of_birth or ""),
              ("Left", f"{a.leaving_year}" + (f", Year {a.last_year_group}"
                                              if a.last_year_group else "")
               + (f" on {a.leaving_date}" if a.leaving_date else "")),
              ("Post-16 (leaving record)", link.post16_destination or ""),
              ("Status", a.status_label + (f" - {a.status_reason}" if a.status_reason else ""))])
    block(1, [("E-mail", a.email or ""), ("Phone", a.phone or ""), ("Town", a.town or ""),
              ("Now doing", a.current_activity or ""),
              ("Organisation", " · ".join(x for x in (a.organisation, a.course_or_role) if x)),
              ("Happy to help", "Yes" if a.can_help else "No"),
              ("Contact consent", (f"Yes, {a.consent_date} ({a.consent_source})"
                                   if a.contact_consent else "No"))])
    if a.notes:
        ttk.Label(frame, text=f"Notes: {a.notes}", wraplength=900, justify="left").pack(
            anchor="w", pady=(6, 0))
    foot = ttk.Frame(frame)
    foot.pack(fill="x", pady=(6, 0))
    if link.note:
        ttk.Label(foot, text=link.note, foreground="#a60").pack(side="left")
    if link.pupil is not None:
        ttk.Button(foot, text="Open pupil record",
                   command=lambda: open_pupil(link.pupil.pupil_id)).pack(side="right")
    hist = AL.history(a.alumni_id)[:5]
    if hist:
        ttk.Label(frame, text="Recent changes: " + "; ".join(
            f"{h['at'][:16]} {h['actor']} {_describe(h)}" for h in hist),
                  foreground="#888", wraplength=900, justify="left").pack(anchor="w",
                                                                         pady=(4, 0))


def _describe(h: dict) -> str:
    d = h["detail"]
    if h["action"] == "update":
        return "changed " + ", ".join(AL.FIELD_LABELS.get(f, f).lower()
                                      for f in d.get("fields", []))
    if h["action"] == "status":
        return f"status {d.get('from')} → {d.get('to')}"
    if h["action"] == "email":
        return f"e-mailed (message {d.get('message_id')})"
    return h["action"] + ("d" if h["action"].endswith("e") else "ed")


# ── Dialogs ──────────────────────────────────────────────────────────

class _Fields:
    """The editable alumnus fields on a grid; reused by New/Edit and Promote."""

    def __init__(self, body: ttk.Frame, row: int, a: AL.Alumnus | None, *,
                 identity: bool, locked: bool = False):
        self.w: dict[str, object] = {}
        self.row = row
        self.body = body

        def val(key: str) -> str:
            v = getattr(a, key, None) if a else None
            return "" if v is None else str(v)

        if identity:
            state = "disabled" if locked else "normal"
            for key in ("first_name", "last_name", "preferred_name"):
                e = ttk.Entry(body, width=30)
                e.insert(0, val(key))
                if key != "preferred_name":
                    e.configure(state=state)
                self._put(key, e, required=key != "preferred_name")
            dob = DatePicker(body, value=val("date_of_birth") or None,
                             years=birth_years(youngest=14, oldest=90))
            if locked:
                for cb in (dob.cb_day, dob.cb_month, dob.cb_year):
                    cb.configure(state="disabled")
            self._put("date_of_birth", dob)
            year = ttk.Combobox(body, values=AL.leaving_year_choices(), width=9,
                                state="disabled" if locked else "readonly")
            year.set(val("leaving_year"))
            self._put("leaving_year", year, required=True)
            yg = ttk.Combobox(body, values=["", "7", "8", "9", "10", "11"], width=5,
                              state="disabled" if locked else "readonly")
            yg.set(val("last_year_group"))
            self._put("last_year_group", yg)
            if locked:
                ttk.Label(body, text="Name, date of birth and year left come from the pupil "
                                     "record.", foreground="#888").grid(
                    row=self.row, column=1, sticky="w")
                self.row += 1
            self.locked = locked
        else:
            self.locked = True
        for key, width in (("email", 34), ("phone", 18), ("town", 24)):
            e = ttk.Entry(body, width=width)
            e.insert(0, val(key))
            self._put(key, e)
        act = ttk.Combobox(body, values=["", *AL.ACTIVITIES], state="readonly", width=26)
        act.set(val("current_activity"))
        self._put("current_activity", act)
        for key in ("organisation", "course_or_role"):
            e = ttk.Entry(body, width=34)
            e.insert(0, val(key))
            self._put(key, e)
        self.help_var = tk.BooleanVar(value=bool(a.can_help) if a else False)
        self._put("can_help", ttk.Checkbutton(body, text="Happy to help the school (careers "
                                                         "talks, mentoring)",
                                              variable=self.help_var))
        consent = ttk.LabelFrame(body, text="Contact consent", padding=6)
        consent.grid(row=self.row, column=0, columnspan=2, sticky="ew", pady=(6, 2))
        self.row += 1
        self.consent_var = tk.BooleanVar(value=bool(a.contact_consent) if a else False)
        ttk.Checkbutton(consent, text="Agreed to be contacted by the school",
                        variable=self.consent_var).grid(row=0, column=0, columnspan=2,
                                                        sticky="w")
        ttk.Label(consent, text="Date agreed").grid(row=1, column=0, sticky="w", padx=(0, 8))
        self.consent_date = DatePicker(consent, value=val("consent_date") or None,
                                       years=recent_years(ahead=0, back=15))
        self.consent_date.grid(row=1, column=1, sticky="w", pady=2)
        ttk.Label(consent, text="How").grid(row=2, column=0, sticky="w", padx=(0, 8))
        self.consent_source = ttk.Combobox(consent, values=["", *AL.CONSENT_SOURCES],
                                           state="readonly", width=16)
        self.consent_source.set(val("consent_source"))
        self.consent_source.grid(row=2, column=1, sticky="w", pady=2)
        ttk.Label(body, text="Notes").grid(row=self.row, column=0, sticky="nw", pady=2)
        self.notes = tk.Text(body, width=46, height=4, wrap="word")
        self.notes.insert("1.0", val("notes"))
        self.notes.grid(row=self.row, column=1, sticky="w", pady=2)
        self.row += 1

    def _put(self, key: str, widget, *, required: bool = False) -> None:
        label = AL.FIELD_LABELS[key] + (" *" if required else "")
        if key != "can_help":
            ttk.Label(self.body, text=label).grid(row=self.row, column=0, sticky="w", pady=2,
                                                  padx=(0, 8))
        widget.grid(row=self.row, column=1, sticky="w", pady=2)
        self.w[key] = widget
        self.row += 1

    def values(self) -> dict:
        out: dict = {}
        for key, widget in self.w.items():
            if key == "can_help":
                continue
            if self.locked and key in {"first_name", "last_name", "date_of_birth",
                                       "leaving_year", "last_year_group"}:
                continue
            out[key] = widget.get()  # type: ignore[attr-defined]
        out["can_help"] = self.help_var.get()
        out["contact_consent"] = self.consent_var.get()
        out["consent_date"] = self.consent_date.get()
        out["consent_source"] = self.consent_source.get()
        out["notes"] = self.notes.get("1.0", "end").strip()
        return out


def _form_window(owner: tk.Misc, title: str, size: str = "720x700"):
    win = make_toplevel(owner.winfo_toplevel())
    win.title(title)
    window_sizing.fit(win, size, (600, 480))
    body, footer = scrolled_form(win)
    error_var = tk.StringVar()
    ttk.Label(footer, textvariable=error_var, foreground="#a00", wraplength=660,
              justify="left").pack(anchor="w")
    bar = ttk.Frame(footer)
    bar.pack(anchor="e", pady=(4, 0))
    return win, body, error_var, bar


def alumnus_form(owner: tk.Misc, *, principal: Principal, alumnus: AL.Alumnus | None,
                 after: Callable[[], None]) -> None:
    editing = alumnus is not None
    activity_log.record("alumni.form.open", target=alumnus.alumni_ref if alumnus else "new")
    win, body, error_var, bar = _form_window(
        owner, f"Edit {alumnus.display_name}" if alumnus else "New alumnus")
    if not editing:
        ttk.Label(body, text="For someone who left before the school used this system. To "
                             "add a pupil who has left, use Promote Pupil.",
                  foreground="#666", wraplength=600, justify="left").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))
    form = _Fields(body, 1, alumnus, identity=True,
                   locked=bool(alumnus and alumnus.pupil_id is not None))

    def save(allow_duplicate: bool = False) -> None:
        try:
            if alumnus:
                AL.update_alumnus(alumnus.alumni_id, form.values(), actor=principal)
            else:
                AL.create_alumnus(form.values(), actor=principal,
                                  allow_duplicate=allow_duplicate)
        except AL.DuplicateAlumnus as e:
            if messagebox.askyesno("Possible duplicate", f"{e}\n\nAdd anyway?", parent=win):
                save(allow_duplicate=True)
            return
        except AL.ValidationError as e:
            error_var.set(_problems(e))
            return
        except _ERRORS as e:
            messagebox.showerror("Alumni", str(e), parent=win)
            return
        except Exception as e:  # noqa: BLE001
            logger.exception("Saving alumnus failed")
            messagebox.showerror("Alumni", f"Something went wrong:\n{e}", parent=win)
            return
        win.destroy()
        after()

    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="right")
    ttk.Button(bar, text="Save" if editing else "Add alumnus", command=save).pack(
        side="right", padx=(0, 6))


def promote_dialog(owner: tk.Misc, *, principal: Principal,
                   after: Callable[[], None]) -> None:
    """Pick a pupil who has left and make them an alumnus (the pupil record stays)."""
    activity_log.record("alumni.promote.open")
    win, body, error_var, bar = _form_window(owner, "Promote pupil to alumni", "760x760")
    ttk.Label(body, text="Pupils who have left and aren't alumni yet. Their pupil record is "
                         "kept.", foreground="#666").grid(row=0, column=0, columnspan=2,
                                                          sticky="w")
    search_var = tk.StringVar()
    ttk.Entry(body, textvariable=search_var, width=36).grid(row=1, column=0, columnspan=2,
                                                            sticky="w", pady=4)
    pick = tk.Listbox(body, height=7, width=78, exportselection=False)
    pick.grid(row=2, column=0, columnspan=2, sticky="w")
    found: list = []

    def fill(*_a) -> None:
        pick.delete(0, "end")
        found[:] = AL.leavers_not_alumni(search=search_var.get().strip() or None)
        for p in found:
            pick.insert("end", f"{p.display_name} · {p.admission_no} · Year {p.year_group} · "
                               f"left {p.leaving_date} ({p.leaving_reason})")
        if not found:
            pick.insert("end", "No leavers waiting - record a leaver in Enrolment & Leavers.")

    search_var.trace_add("write", fill)
    fill()
    ttk.Separator(body).grid(row=3, column=0, columnspan=2, sticky="ew", pady=8)
    form = _Fields(body, 4, None, identity=False)

    def save() -> None:
        sel = pick.curselection()
        if not sel or sel[0] >= len(found):
            error_var.set("Choose the pupil from the list.")
            return
        pupil = found[sel[0]]
        try:
            a = AL.add_from_pupil(pupil.pupil_id, form.values(), actor=principal)
        except AL.ValidationError as e:
            error_var.set(_problems(e))
            return
        except _ERRORS as e:
            messagebox.showerror("Promote pupil", str(e), parent=win)
            return
        except Exception as e:  # noqa: BLE001
            logger.exception("Promote failed")
            messagebox.showerror("Promote pupil", f"Something went wrong:\n{e}", parent=win)
            return
        win.destroy()
        messagebox.showinfo("Alumni", f"{a.display_name} added as {a.alumni_ref}.",
                            parent=owner)
        after()

    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="right")
    ttk.Button(bar, text="Add to alumni", command=save).pack(side="right", padx=(0, 6))


def add_leavers_dialog(owner: tk.Misc, *, principal: Principal,
                       after: Callable[[], None]) -> None:
    win = make_toplevel(owner.winfo_toplevel())
    win.title("Add Year 11 leavers")
    win.resizable(False, False)
    frm = ttk.Frame(win, padding=14)
    frm.pack(fill="both", expand=True)
    ttk.Label(frm, text="Make alumni of everyone who left at the end of Year 11 in:").grid(
        row=0, column=0, columnspan=2, sticky="w")
    year = ttk.Combobox(frm, values=AL.leaving_year_choices(), state="readonly", width=9)
    year.grid(row=1, column=0, sticky="w", pady=6)
    count = ttk.Label(frm, foreground="#555", wraplength=380, justify="left")
    count.grid(row=2, column=0, columnspan=2, sticky="w")

    def update(_e=None) -> None:
        n = len(AL.leavers_not_alumni(academic_year=year.get(), reasons=(EN.END_OF_Y11,)))
        count.configure(text=f"{n} leaver{'s' if n != 1 else ''} to add. Nobody is e-mailed "
                             "until they agree to be contacted.")

    year.bind("<<ComboboxSelected>>", update)
    choices = AL.leaving_year_choices()
    year.set(choices[1] if len(choices) > 1 else choices[0])  # last year's leavers
    update()

    def go() -> None:
        try:
            added = AL.add_leavers(year.get(), actor=principal)
        except _ERRORS as e:
            messagebox.showerror("Add leavers", _problems(e), parent=win)
            return
        win.destroy()
        messagebox.showinfo("Alumni", f"{len(added)} added.", parent=owner)
        after()

    bar = ttk.Frame(frm)
    bar.grid(row=3, column=0, columnspan=2, sticky="e", pady=(12, 0))
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="right")
    ttk.Button(bar, text="Add", command=go).pack(side="right", padx=(0, 6))


def status_dialog(owner: tk.Misc, *, principal: Principal, alumnus: AL.Alumnus,
                  after: Callable[[], None]) -> None:
    win = make_toplevel(owner.winfo_toplevel())
    win.title(f"Status - {alumnus.display_name}")
    win.resizable(False, False)
    frm = ttk.Frame(win, padding=14)
    frm.pack(fill="both", expand=True)
    ttk.Label(frm, text=f"Now: {alumnus.status_label}").grid(row=0, column=0, columnspan=2,
                                                             sticky="w")
    ttk.Label(frm, text="New status").grid(row=1, column=0, sticky="w", pady=(8, 2))
    status = ttk.Combobox(frm, values=list(AL.STATUS_LABELS.values()), state="readonly",
                          width=12)
    status.grid(row=1, column=1, sticky="w", pady=(8, 2))
    ttk.Label(frm, text="Reason").grid(row=2, column=0, sticky="w")
    reason = ttk.Entry(frm, width=40)
    reason.grid(row=2, column=1, sticky="w")
    ttk.Label(frm, text="Inactive and deceased records are never e-mailed.",
              foreground="#888").grid(row=3, column=0, columnspan=2, sticky="w", pady=(6, 0))

    def go() -> None:
        key = next((k for k, v in AL.STATUS_LABELS.items() if v == status.get()), "")
        try:
            AL.set_status(alumnus.alumni_id, key, actor=principal, reason=reason.get())
        except _ERRORS as e:
            messagebox.showerror("Set status", _problems(e), parent=win)
            return
        win.destroy()
        after()

    bar = ttk.Frame(frm)
    bar.grid(row=4, column=0, columnspan=2, sticky="e", pady=(12, 0))
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="right")
    ttk.Button(bar, text="Save", command=go).pack(side="right", padx=(0, 6))


def delete_dialog(owner: tk.Misc, *, principal: Principal, alumnus: AL.Alumnus,
                  after: Callable[[], None]) -> None:
    win = make_toplevel(owner.winfo_toplevel())
    win.title("Delete alumni record")
    win.resizable(False, False)
    frm = ttk.Frame(win, padding=14)
    frm.pack(fill="both", expand=True)
    ttk.Label(frm, text=f"Delete the alumni record for {alumnus.display_name} "
                        f"({alumnus.alumni_ref})? Their pupil record, if any, is kept.\n\n"
                        "Use this for an erasure request or a record made in error.",
              wraplength=400, justify="left").grid(row=0, column=0, columnspan=2, sticky="w")
    ttk.Label(frm, text="Reason *").grid(row=1, column=0, sticky="w", pady=(10, 0))
    reason = ttk.Entry(frm, width=40)
    reason.grid(row=1, column=1, sticky="w", pady=(10, 0))

    def go() -> None:
        try:
            AL.delete_alumnus(alumnus.alumni_id, actor=principal, reason=reason.get())
        except _ERRORS as e:
            messagebox.showerror("Delete", _problems(e), parent=win)
            return
        win.destroy()
        after()

    bar = ttk.Frame(frm)
    bar.grid(row=2, column=0, columnspan=2, sticky="e", pady=(12, 0))
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="right")
    ttk.Button(bar, text="Delete", command=go).pack(side="right", padx=(0, 6))


def email_dialog(owner: tk.Misc, *, principal: Principal, alumni_ids: list[int],
                 chosen: bool, after: Callable[[], None]) -> None:
    from education_system.systems.secondary.modules.communication.gui import email_views
    plan = AL.plan_email(alumni_ids)
    activity_log.record("alumni.email.open", recipients=len(plan.recipients),
                        skipped=len(plan.skipped))
    win, body, error_var, bar = _form_window(owner, "E-mail alumni", "720x620")
    who = "the selected alumni" if chosen else "everyone listed"
    ttk.Label(body, text=f"To {who}: {len(plan.recipients)} will receive it, "
                         f"{len(plan.skipped)} skipped (no consent, no e-mail or not active).",
              wraplength=640, justify="left").grid(row=0, column=0, columnspan=2, sticky="w")
    ttk.Label(body, text="Subject").grid(row=1, column=0, sticky="w", pady=(8, 2))
    subject = ttk.Entry(body, width=60)
    subject.grid(row=1, column=1, sticky="w", pady=(8, 2))
    ttk.Label(body, text="Message").grid(row=2, column=0, sticky="nw")
    text = tk.Text(body, width=64, height=14, wrap="word")
    text.insert("1.0", "Dear {first_name},\n\n")
    text.grid(row=2, column=1, sticky="w")
    ttk.Label(body, text="You can use " + ", ".join("{" + k + "}" for k in AL.PLACEHOLDERS)
                         + ". A line saying how to stop these e-mails is added at the end.",
              foreground="#888", wraplength=600, justify="left").grid(
        row=3, column=1, sticky="w", pady=(4, 0))

    def send() -> None:
        try:
            message_id, sent = AL.send_email(subject.get(), text.get("1.0", "end"),
                                             alumni_ids, actor=principal)
        except AL.ValidationError as e:
            error_var.set(_problems(e))
            return
        except _ERRORS as e:
            messagebox.showerror("E-mail alumni", str(e), parent=win)
            return
        win.destroy()

        def done(report, err) -> None:
            msg = (f"Saved, but delivery failed:\n{err}\n\nRetry it from Email." if err
                   else f"{len(sent.recipients)} e-mail(s): "
                        + email_views._report_text(report))
            messagebox.showinfo("E-mail alumni", msg, parent=owner)
            after()

        email_views.deliver_in_background(owner, message_id, principal, done)

    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="right")
    ttk.Button(bar, text="Send", command=send).pack(side="right", padx=(0, 6))
