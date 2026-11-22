"""Parent/carer contact screens: the list on a pupil's profile, the add/edit
form, and the Parent Contacts page (pick a pupil, manage their contacts)."""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from typing import Callable

from education_system.platform.delivery.gui.parented_dialogs import make_toplevel, messagebox
from education_system.systems.secondary.modules.pupils.domain import contacts as C
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log

logger = logging.getLogger(__name__)

_COLUMNS = (
    ("priority", "#", 30),
    ("name", "Name", 170),
    ("rel", "Relationship", 100),
    ("email", "E-mail", 200),
    ("phone", "Phone", 120),
    ("pr", "Parental resp.", 90),
    ("mail", "School e-mail", 90),
)


def draw_contacts_section(parent: tk.Misc, pupil: P.Pupil, *, principal: Principal,
                          on_changed: Callable[[], None]) -> ttk.LabelFrame:
    """A 'Contacts' box listing *pupil*'s contacts, with add/edit/delete for editors.
    The caller packs or grids the returned frame."""
    box = ttk.LabelFrame(parent, text="Parent / carer contacts", padding=8)
    tree = ttk.Treeview(box, columns=[c for c, _h, _w in _COLUMNS], show="headings",
                        height=4, selectmode="browse")
    for col, heading, width in _COLUMNS:
        tree.heading(col, text=heading)
        tree.column(col, width=width, anchor="w", stretch=col in {"name", "email"})
    tree.pack(fill="x", expand=True)
    try:
        rows = C.list_for_pupil(pupil.pupil_id)
    except Exception as e:  # noqa: BLE001
        logger.exception("Could not load contacts")
        ttk.Label(box, text=f"Couldn't load contacts: {e}", foreground="#a00").pack(anchor="w")
        return box
    for c in rows:
        tree.insert("", "end", iid=str(c.contact_id), values=(
            c.priority, c.full_name, c.relationship, c.email or "—", c.phone or "—",
            "Yes" if c.parental_responsibility else "No",
            "Yes" if c.receives_email else "No"))
    if not rows:
        ttk.Label(box, text="No contacts recorded. The school can't e-mail or call "
                            "anyone about this pupil until one is added.",
                  foreground="#a60").pack(anchor="w", pady=(4, 0))
    elif not any(c.can_be_emailed for c in rows):
        ttk.Label(box, text="No contact accepts school e-mail, so this pupil's family "
                            "won't receive e-mails.", foreground="#a60").pack(
            anchor="w", pady=(4, 0))

    if not principal.can_edit_pupils:
        return box

    def selected() -> C.Contact | None:
        sel = tree.selection()
        if not sel:
            messagebox.showinfo("Contacts", "Select a contact first.", parent=box)
            return None
        return C.get_contact(int(sel[0]))

    def add() -> None:
        open_contact_form(box, principal=principal, pupil=pupil, contact=None,
                          on_saved=on_changed)

    def edit(_e=None) -> None:
        c = selected()
        if c:
            open_contact_form(box, principal=principal, pupil=pupil, contact=c,
                              on_saved=on_changed)

    def delete() -> None:
        c = selected()
        if c is None:
            return
        if not messagebox.askyesno("Delete contact",
                                   f"Remove {c.full_name} ({c.relationship}) as a contact "
                                   f"for {pupil.display_name}?", parent=box):
            activity_log.record("contact.delete", target=pupil.admission_no,
                                outcome="cancelled", contact=c.contact_id)
            return
        try:
            C.delete_contact(c.contact_id, actor=principal)
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Contacts", f"Could not delete the contact:\n{e}", parent=box)
            return
        _deliver_parent_mail(box, principal, pupil.pupil_id)
        on_changed()

    tree.bind("<Double-1>", edit)
    bar = ttk.Frame(box)
    bar.pack(fill="x", pady=(6, 0))
    ttk.Button(bar, text="Add contact", command=add).pack(side="left")
    ttk.Button(bar, text="Edit", command=edit).pack(side="left", padx=4)
    ttk.Button(bar, text="Delete", command=delete).pack(side="left")
    return box


def _deliver_parent_mail(widget: tk.Misc, principal: Principal, pupil_id: int) -> None:
    """A contact change can make (or move) a parent portal login: deliver its
    e-mail now, in the background, and say so only if something went wrong."""
    try:
        from education_system.systems.secondary.modules.administration.gui import (
            user_accounts_views,
        )
        user_accounts_views.deliver_waiting(widget.winfo_toplevel(), principal,
                                            pupil_id=pupil_id, quiet=True)
    except Exception:  # noqa: BLE001 - the contact is saved; the e-mail stays queued
        logger.exception("Delivering parent portal e-mail failed")


def open_contact_form(parent: tk.Misc, *, principal: Principal, pupil: P.Pupil,
                      contact: C.Contact | None, on_saved: Callable[[], None]) -> None:
    action = "contact.update" if contact else "contact.create"
    if not principal.can_edit_pupils:
        activity_log.record(action, target=pupil.admission_no, outcome="denied")
        messagebox.showwarning("Contacts", "Your account can view contacts but not change "
                                           "them.", parent=parent)
        return
    activity_log.record("contact.form.open", target=pupil.admission_no,
                        mode="edit" if contact else "add",
                        contact=contact.contact_id if contact else None)
    win = make_toplevel(parent.winfo_toplevel())
    win.title(f"{'Edit' if contact else 'Add'} contact – {pupil.display_name}")
    win.resizable(False, False)
    frm = ttk.Frame(win, padding=14)
    frm.pack(fill="both", expand=True)

    def cur(name: str, default=""):
        return getattr(contact, name) if contact else default

    vars_: dict[str, tk.Variable] = {
        "full_name": tk.StringVar(value=cur("full_name")),
        "relationship": tk.StringVar(value=cur("relationship", "Mother")),
        "priority": tk.StringVar(value=str(cur("priority", 1))),
        "email": tk.StringVar(value=cur("email") or ""),
        "phone": tk.StringVar(value=cur("phone") or ""),
        "parental_responsibility": tk.BooleanVar(value=cur("parental_responsibility", True)),
        "receives_email": tk.BooleanVar(value=cur("receives_email", True)),
    }
    rows = [("Name *", ttk.Entry(frm, textvariable=vars_["full_name"], width=34)),
            ("Relationship *", ttk.Combobox(frm, textvariable=vars_["relationship"],
                                            values=list(C.RELATIONSHIPS), state="readonly",
                                            width=31)),
            ("Priority (1 = first)", ttk.Spinbox(frm, from_=1, to=C.MAX_PRIORITY,
                                                 textvariable=vars_["priority"], width=5)),
            ("E-mail", ttk.Entry(frm, textvariable=vars_["email"], width=34)),
            ("Phone", ttk.Entry(frm, textvariable=vars_["phone"], width=34))]
    for r, (label, widget) in enumerate(rows):
        ttk.Label(frm, text=label).grid(row=r, column=0, sticky="w", pady=3, padx=(0, 10))
        widget.grid(row=r, column=1, sticky="w", pady=3)
    r = len(rows)
    ttk.Checkbutton(frm, text="Has parental responsibility",
                    variable=vars_["parental_responsibility"]).grid(
        row=r, column=1, sticky="w", pady=3)
    ttk.Checkbutton(frm, text="Agrees to receive school e-mail",
                    variable=vars_["receives_email"]).grid(row=r + 1, column=1, sticky="w")
    ttk.Label(frm, text="Notes").grid(row=r + 2, column=0, sticky="nw", pady=3)
    notes = tk.Text(frm, width=34, height=3, wrap="word")
    notes.grid(row=r + 2, column=1, sticky="w", pady=3)
    notes.insert("1.0", cur("notes") or "")
    ttk.Label(frm, text="An e-mail address or a phone number is required.",
              foreground="#666").grid(row=r + 3, column=0, columnspan=2, sticky="w", pady=(6, 0))

    def save() -> None:
        data = {k: v.get() for k, v in vars_.items()}
        data["notes"] = notes.get("1.0", "end").strip()
        try:
            if contact:
                C.update_contact(contact.contact_id, data, actor=principal)
            else:
                C.add_contact(pupil.pupil_id, data, actor=principal)
        except C.ValidationError as e:
            messagebox.showerror("Contacts", str(e), parent=win)
            return
        except Exception as e:  # noqa: BLE001
            logger.exception("Saving contact failed")
            messagebox.showerror("Contacts", f"Could not save the contact:\n{e}", parent=win)
            return
        win.destroy()
        _deliver_parent_mail(parent, principal, pupil.pupil_id)
        on_saved()

    def cancel() -> None:
        activity_log.record("contact.form.cancel", target=pupil.admission_no)
        win.destroy()

    bar = ttk.Frame(frm)
    bar.grid(row=r + 4, column=0, columnspan=2, sticky="e", pady=(12, 0))
    ttk.Button(bar, text="Cancel", command=cancel).pack(side="right")
    ttk.Button(bar, text="Save", command=save).pack(side="right", padx=(0, 6))
    win.protocol("WM_DELETE_WINDOW", cancel)
    win.bind("<Escape>", lambda _e: cancel())
    rows[0][1].focus_set()


def draw_contacts_page(parent: ttk.Frame, pupil_id: int, *, principal: Principal,
                       on_changed: Callable[[], None], on_back: Callable[[], None]) -> None:
    """Parent Contacts for one pupil (reached from the Parent Contacts picker)."""
    pupil = P.get_pupil(pupil_id)
    if pupil is None:
        ttk.Label(parent, text="This pupil record no longer exists.",
                  foreground="#a00").pack(anchor="w")
        return
    activity_log.record("contact.list", target=pupil.admission_no)
    head = ttk.Frame(parent)
    head.pack(fill="x", pady=(0, 8))
    ttk.Label(head, text=pupil.display_name, font=("", 16, "bold")).pack(side="left")
    ttk.Label(head, text=f"  {pupil.admission_no} · Year {pupil.year_group}"
                         f"{' · ' + pupil.form_group if pupil.form_group else ''}",
              foreground="#555").pack(side="left", pady=(4, 0))
    ttk.Button(head, text="← Choose another pupil", command=on_back).pack(side="right")
    draw_contacts_section(parent, pupil, principal=principal,
                          on_changed=on_changed).pack(fill="x")
