"""Tkinter views for Primary School Parent / Guardian Contacts."""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import simpledialog, ttk
from typing import Callable
from education_system.systems.primary.domain.operations.communications.parent_contacts import parent_contacts
from education_system.systems.primary.domain.operations.communications.parent_contacts import parent_contacts as data
from education_system.systems.primary.domain import _pupils_bridge as student_data
from education_system.platform.delivery.gui.parented_dialogs import make_toplevel, messagebox
from education_system.systems.primary.interfaces.gui import kit
from education_system.systems.primary.domain import access
from education_system.systems.primary.domain.operations.communications.parent_contacts.parent_contacts import (
    Contact,
    DEFAULT_LANGUAGE,
    DEFAULT_PREFERRED_METHOD,
    DEFAULT_RELATIONSHIP,
    LANGUAGES,
    PREFERRED_CONTACT_METHODS,
    RELATIONSHIPS,
    ValidationError,
)

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)


_TITLES = ("Mr", "Mrs", "Ms", "Miss", "Mx", "Dr")


def open_directory(parent=None) -> None:
    data.init_db()
    kit.show_page(parent, "Parent Contacts",
                  lambda frame: _draw_directory(frame, parent))


def _draw_directory(frame: ttk.Frame, host=None) -> None:
    kit.page_heading(frame, "Parent Contacts",
                     "Parents, carers and emergency contacts for every pupil.")
    ContactsDirectory(frame, auth=getattr(host, "auth", None))


def _ask_pupil(parent: tk.Misc, title: str, prompt: str) -> str | None:
    """A small modal pupil picker; returns the chosen pupil id or None."""
    win = make_toplevel(parent.winfo_toplevel())
    win.title(title)
    win.after_idle(win.grab_set)
    frm = ttk.Frame(win, padding=12)
    frm.pack(fill="both", expand=True)
    ttk.Label(frm, text=prompt, justify="left", wraplength=460).pack(anchor="w",
                                                                      pady=(0, 6))
    var = tk.StringVar()
    kit.PupilPicker(frm, var).pack(anchor="w")
    result: dict = {"value": None}

    def ok() -> None:
        if not var.get():
            messagebox.showerror(title, "Pick a pupil.", parent=win)
            return
        result["value"] = var.get()
        win.destroy()

    bar = ttk.Frame(frm)
    bar.pack(fill="x", pady=(12, 0))
    ttk.Button(bar, text="OK", command=ok).pack(side="right", padx=4)
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="right")
    win.wait_window()
    return result["value"]


def _student_options() -> list[tuple[str, str]]:
    rows = sorted(student_data.list_students(),
                   key=lambda s: s.student_id)
    return [(s.student_id, f"{s.student_id} — {s.full_name}") for s in rows]


def _name_lookup() -> dict[str, str]:
    return {s.student_id: s.full_name for s in student_data.list_students()}


class ContactsDirectory:
    def __init__(self, root: tk.Misc, auth=None) -> None:
        self.root = root
        self.auth = auth
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.root)
        bar.pack(fill="x", padx=10, pady=(10, 4))
        ttk.Label(bar, text="Search:").pack(side="left")
        self.q_e = ttk.Entry(bar, width=24)
        self.q_e.pack(side="left", padx=(2, 10))
        self.q_e.bind("<Return>", lambda _e: self.refresh())

        ttk.Label(bar, text="Pupil:").pack(side="left")
        self.v_student = tk.StringVar()
        self.f_student = kit.PupilPicker(bar, self.v_student, width=34)
        self.f_student.bind_change(lambda _v: self.refresh())
        self.f_student.pack(side="left", padx=(2, 10))

        ttk.Label(bar, text="Relationship:").pack(side="left")
        self.v_rel = tk.StringVar()
        self.f_rel = kit.ChoiceField(bar, self.v_rel, choices=RELATIONSHIPS, blank=True,
                                     width=16, on_change=lambda _v: self.refresh())
        self.f_rel.pack(side="left", padx=(2, 10))

        self.f_primary = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Primary",
                          variable=self.f_primary,
                          command=self.refresh).pack(side="left", padx=(0, 6))
        self.f_emerg = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Emergency",
                          variable=self.f_emerg,
                          command=self.refresh).pack(side="left", padx=(0, 6))
        self.f_comms = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Comms",
                          variable=self.f_comms,
                          command=self.refresh).pack(side="left")

        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left", padx=(10, 4))
        ttk.Button(bar, text="Clear",
                    command=self._clear).pack(side="left")

        table_frame = ttk.Frame(self.root)
        table_frame.pack(fill="both", expand=True, padx=10, pady=4)
        cols = ("id", "student", "student_name", "contact", "rel",
                "email", "phone", "method", "flags")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings")
        widths = {"id": 60, "student": 90, "student_name": 180,
                  "contact": 200, "rel": 110, "email": 200,
                  "phone": 130, "method": 130, "flags": 80}
        headings = {"id": "#", "student": "Student",
                    "student_name": "Student name",
                    "contact": "Contact", "rel": "Relationship",
                    "email": "Email", "phone": "Phone",
                    "method": "Pref. method", "flags": "Flags"}
        for c in cols:
            self.tree.heading(c, text=headings[c])
            self.tree.column(c, width=widths[c], anchor="w")
        vs = ttk.Scrollbar(table_frame, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.tag_configure("primary",
                                  background="#e0f0ff", font=("", 9, "bold"))
        self.tree.bind("<Double-1>", lambda _e: self._view_selected())

        self.count_var = tk.StringVar(value="")
        ttk.Label(self.root, textvariable=self.count_var,
                   anchor="w").pack(fill="x", padx=10)

        self.actions_holder = ttk.Frame(self.root)
        self.actions_holder.pack(fill="x", padx=10, pady=(4, 10))
        self._build_actions()

    def _build_actions(self) -> None:
        for w in self.actions_holder.winfo_children():
            w.destroy()
        bar = ttk.Frame(self.actions_holder)
        bar.pack(fill="x")
        ttk.Button(bar, text="View",
                    command=self._view_selected).pack(side="left")
        ttk.Button(bar, text="New",
                    command=self._new).pack(side="left", padx=4)
        ttk.Button(bar, text="Edit",
                    command=self._edit_selected).pack(side="left", padx=4)
        ttk.Button(bar, text="Make Primary",
                    command=self._make_primary).pack(side="left", padx=4)
        ttk.Button(bar, text="Delete",
                    command=self._delete_selected).pack(side="left", padx=4)
        if self.auth is not None and access.from_auth(self.auth).is_admin:
            ttk.Button(bar, text="Link Parent Login",
                       command=self._link_parent_login).pack(side="left", padx=4)
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="right")

    def _link_parent_login(self) -> None:
        """Admin only: tie a parent's login to their child, by exact values."""
        from education_system.platform.cross_system.own_record_access import OwnRecordError
        from education_system.systems.primary.domain.learners.own_records import own_records

        username = simpledialog.askstring(
            "Link Parent Login", "Parent login username:",
            parent=self.root.winfo_toplevel())
        if not username:
            return
        try:
            linked = own_records.linked_children_of(self.auth, username)
            now = ", ".join(f"{c.pupil_id} {c.name}" for c in linked) or "no children"
            pupil_id = _ask_pupil(
                self.root, "Link Parent Login",
                f"{username} is linked to: {now}.\n\nPupil to link:")
            if not pupil_id:
                return
            child = own_records.link_parent_login(self.auth, username, pupil_id)
        except (OwnRecordError, ValueError) as refused:
            messagebox.showerror("Link Parent Login", str(refused), parent=self.root)
            return
        messagebox.showinfo("Link Parent Login",
                            f"{username} is now linked to {child.name}.", parent=self.root)

    def _clear(self) -> None:
        self.q_e.delete(0, "end")
        self.v_student.set("")
        self.v_rel.set("")
        self.f_primary.set(False)
        self.f_emerg.set(False)
        self.f_comms.set(False)
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        q = self.q_e.get().strip()
        try:
            if q:
                rows = data.search_contacts(q)
            else:
                rows = data.list_contacts(
                    student_id=self.v_student.get().strip() or None,
                    relationship=self.f_rel.get() or None,
                    primary_only=self.f_primary.get(),
                    emergency_only=self.f_emerg.get(),
                    receives_only=self.f_comms.get(),
                )
        except ValidationError as e:
            messagebox.showerror("Filter error", str(e))
            return
        names = _name_lookup()
        for c in rows:
            flags = "".join([
                "P" if c.is_primary else "-",
                "E" if c.is_emergency_contact else "-",
                "C" if c.receives_communications else "-",
                "L" if c.lives_with_student else "-",
            ])
            tags = ("primary",) if c.is_primary else ()
            self.tree.insert("", "end", iid=str(c.contact_id), values=(
                c.contact_id, c.student_id, names.get(c.student_id, "?"),
                c.full_name, c.relationship, c.email or "—",
                c.primary_phone or "—", c.preferred_method, flags,
            ), tags=tags)
        self.count_var.set(
            f"{len(rows)} contact(s).  "
            f"(Flags: P=Primary E=Emergency C=Comms L=LivesWith)")
        self._build_actions()

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        if not sel:
            return None
        return int(sel[0])

    def _view_selected(self) -> None:
        cid = self._selected_id()
        if cid is None:
            messagebox.showinfo("View", "Select a contact first.")
            return
        c = data.get_contact(cid)
        if c is None:
            return
        names = _name_lookup()
        lines = [
            f"Contact      : #{c.contact_id}",
            f"Student      : {c.student_id} — {names.get(c.student_id, '?')}",
            f"Relationship : {c.relationship}",
            f"Name         : {c.full_name}",
            f"Email        : {c.email or '—'}",
            f"Primary phone: {c.primary_phone or '—'}",
            f"Secondary    : {c.secondary_phone or '—'}",
            f"Address      : {c.address or '—'}",
            f"Pref. method : {c.preferred_method}",
            f"Language     : {c.preferred_language}",
            "",
            f"Primary?     : {'Yes' if c.is_primary else 'No'}",
            f"Emergency?   : "
            f"{'Yes' if c.is_emergency_contact else 'No'}",
            f"Parental resp: "
            f"{'Yes' if c.has_parental_responsibility else 'No'}",
            f"Receives comms: "
            f"{'Yes' if c.receives_communications else 'No'}",
            f"Lives with   : "
            f"{'Yes' if c.lives_with_student else 'No'}",
            "",
            "Notes:",
            c.notes or "  —",
        ]
        messagebox.showinfo(f"Contact #{c.contact_id}", "\n".join(lines))

    def _new(self) -> None:
        ContactDialog(self.root, existing=None, on_save=self.refresh)

    def _edit_selected(self) -> None:
        cid = self._selected_id()
        if cid is None:
            messagebox.showinfo("Edit", "Select a contact first.")
            return
        existing = data.get_contact(cid)
        if existing is None:
            return
        ContactDialog(self.root, existing=existing,
                       on_save=self.refresh)

    def _make_primary(self) -> None:
        cid = self._selected_id()
        if cid is None:
            messagebox.showinfo("Primary", "Select a contact first.")
            return
        existing = data.get_contact(cid)
        if existing is None:
            return
        if existing.is_primary:
            messagebox.showinfo("Primary",
                                  f"#{cid} is already the primary contact.")
            return
        if not messagebox.askyesno(
                "Make Primary",
                f"Make #{cid} ({existing.full_name}) the primary contact "
                f"for {existing.student_id}?\n\n"
                f"Any other primary for this student will be cleared."):
            return
        try:
            data.set_primary(cid)
        except Exception as e:
            messagebox.showerror("Failed", str(e))
            return
        self.refresh()

    def _delete_selected(self) -> None:
        cid = self._selected_id()
        if cid is None:
            messagebox.showinfo("Delete", "Select a contact first.")
            return
        existing = data.get_contact(cid)
        if existing is None:
            return
        if not messagebox.askyesno(
                "Delete",
                f"Delete contact #{cid} ({existing.full_name})?"):
            return
        try:
            data.delete_contact(cid)
        except Exception as e:
            messagebox.showerror("Delete failed", str(e))
            return
        self.refresh()


class ContactDialog:
    def __init__(self, parent: tk.Misc, *,
                 existing: Contact | None,
                 on_save: Callable[[], None]) -> None:
        self.existing = existing
        self.on_save = on_save
        self.win = make_toplevel(parent.winfo_toplevel())
        self.win.title("Edit Contact" if existing else "New Contact")
        self.win.geometry("700x680")
        self.win.after_idle(self.win.grab_set)
        self._build()

    def _build(self) -> None:
        form, footer = kit.scrolled_form(self.win)
        r = 0

        ttk.Label(form, text="Student:").grid(row=r, column=0,
                                                sticky="e", pady=3)
        if self.existing:
            self.student_cb = None
            self._student_id = self.existing.student_id
            names = _name_lookup()
            ttk.Label(form,
                       text=f"{self._student_id} — "
                            f"{names.get(self._student_id, '?')}"
                       ).grid(row=r, column=1, sticky="w", padx=6)
        else:
            self.student_var = tk.StringVar()
            self.student_cb = kit.PupilPicker(form, self.student_var)
            self.student_cb.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        ttk.Label(form, text="Relationship:").grid(row=r, column=0,
                                                     sticky="e", pady=3)
        self.rel_cb = kit.ChoiceField(
            form, tk.StringVar(value=self.existing.relationship if self.existing
                               else DEFAULT_RELATIONSHIP),
            choices=RELATIONSHIPS, width=18)
        self.rel_cb.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        ttk.Label(form, text="Title:").grid(row=r, column=0,
                                              sticky="e", pady=3)
        self.title_e = kit.ChoiceField(
            form, tk.StringVar(value=(self.existing.title or "") if self.existing else ""),
            choices=_TITLES, blank=True, editable=True, width=8)
        self.title_e.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        ttk.Label(form, text="First name:").grid(row=r, column=0,
                                                   sticky="e", pady=3)
        self.fn_e = ttk.Entry(form, width=30)
        if self.existing:
            self.fn_e.insert(0, self.existing.first_name)
        self.fn_e.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        ttk.Label(form, text="Last name:").grid(row=r, column=0,
                                                  sticky="e", pady=3)
        self.ln_e = ttk.Entry(form, width=30)
        if self.existing:
            self.ln_e.insert(0, self.existing.last_name)
        self.ln_e.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        ttk.Label(form, text="Email:").grid(row=r, column=0,
                                              sticky="e", pady=3)
        self.email_e = ttk.Entry(form, width=40)
        if self.existing and self.existing.email:
            self.email_e.insert(0, self.existing.email)
        self.email_e.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        ttk.Label(form, text="Primary phone:").grid(row=r, column=0,
                                                      sticky="e", pady=3)
        self.pp_e = ttk.Entry(form, width=24)
        if self.existing and self.existing.primary_phone:
            self.pp_e.insert(0, self.existing.primary_phone)
        self.pp_e.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        ttk.Label(form, text="Secondary phone:").grid(row=r, column=0,
                                                       sticky="e", pady=3)
        self.sp_e = ttk.Entry(form, width=24)
        if self.existing and self.existing.secondary_phone:
            self.sp_e.insert(0, self.existing.secondary_phone)
        self.sp_e.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        ttk.Label(form, text="Address:").grid(row=r, column=0,
                                                sticky="ne", pady=3)
        self.addr_text = tk.Text(form, width=50, height=3, wrap="word")
        if self.existing and self.existing.address:
            self.addr_text.insert("1.0", self.existing.address)
        self.addr_text.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        ttk.Label(form, text="Preferred method:").grid(row=r, column=0,
                                                          sticky="e", pady=3)
        self.method_cb = kit.ChoiceField(
            form, tk.StringVar(value=self.existing.preferred_method if self.existing
                               else DEFAULT_PREFERRED_METHOD),
            choices=PREFERRED_CONTACT_METHODS, width=18)
        self.method_cb.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        ttk.Label(form, text="Language:").grid(row=r, column=0,
                                                  sticky="e", pady=3)
        self.lang_cb = kit.ChoiceField(
            form, tk.StringVar(value=self.existing.preferred_language if self.existing
                               else DEFAULT_LANGUAGE),
            choices=LANGUAGES, width=14)
        self.lang_cb.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        ttk.Label(form, text="Flags:").grid(row=r, column=0,
                                              sticky="ne", pady=3)
        fl = ttk.Frame(form)
        fl.grid(row=r, column=1, sticky="w", padx=6)
        self.primary_var = tk.BooleanVar(
            value=self.existing.is_primary if self.existing else False)
        self.emerg_var = tk.BooleanVar(
            value=self.existing.is_emergency_contact
                  if self.existing else True)
        self.pr_var = tk.BooleanVar(
            value=self.existing.has_parental_responsibility
                  if self.existing else True)
        self.comms_var = tk.BooleanVar(
            value=self.existing.receives_communications
                  if self.existing else True)
        self.lives_var = tk.BooleanVar(
            value=self.existing.lives_with_student
                  if self.existing else True)
        ttk.Checkbutton(fl, text="Primary contact",
                          variable=self.primary_var).grid(row=0, column=0,
                                                            sticky="w")
        ttk.Checkbutton(fl, text="Emergency contact",
                          variable=self.emerg_var).grid(row=0, column=1,
                                                          sticky="w", padx=10)
        ttk.Checkbutton(fl, text="Parental responsibility",
                          variable=self.pr_var).grid(row=1, column=0,
                                                       sticky="w")
        ttk.Checkbutton(fl, text="Receives comms",
                          variable=self.comms_var).grid(row=1, column=1,
                                                          sticky="w", padx=10)
        ttk.Checkbutton(fl, text="Lives with student",
                          variable=self.lives_var).grid(row=2, column=0,
                                                          sticky="w")
        r += 1

        ttk.Label(form, text="Notes:").grid(row=r, column=0,
                                              sticky="ne", pady=3)
        self.notes_text = tk.Text(form, width=50, height=4, wrap="word")
        if self.existing and self.existing.notes:
            self.notes_text.insert("1.0", self.existing.notes)
        self.notes_text.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        ttk.Button(footer, text="Cancel",
                    command=self.win.destroy).pack(side="right", padx=(6, 0))
        ttk.Button(footer, text="Save", command=self._save).pack(side="right")

    def _save(self) -> None:
        if self.student_cb is not None:
            sid = self.student_var.get()
            if not sid:
                messagebox.showerror("Validation", "Pick a student.", parent=self.win)
                return
        else:
            sid = self._student_id
        payload = {
            "student_id":       sid,
            "relationship":     self.rel_cb.get(),
            "title":            self.title_e.get().strip(),
            "first_name":       self.fn_e.get().strip(),
            "last_name":        self.ln_e.get().strip(),
            "email":            self.email_e.get().strip(),
            "primary_phone":    self.pp_e.get().strip(),
            "secondary_phone":  self.sp_e.get().strip(),
            "address":          self.addr_text.get("1.0", "end").strip(),
            "preferred_method": self.method_cb.get(),
            "preferred_language": self.lang_cb.get(),
            "is_primary":           self.primary_var.get(),
            "is_emergency_contact": self.emerg_var.get(),
            "has_parental_responsibility": self.pr_var.get(),
            "receives_communications":     self.comms_var.get(),
            "lives_with_student":          self.lives_var.get(),
            "notes":            self.notes_text.get("1.0", "end").strip(),
        }
        try:
            if self.existing:
                data.update_contact(self.existing.contact_id, payload)
            else:
                data.create_contact(payload)
        except ValidationError as e:
            messagebox.showerror("Validation", str(e))
            return
        except Exception as e:
            logger.exception("save contact failed")
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()
