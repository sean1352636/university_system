"""Tkinter views for Sixth Form Parent / Guardian Contacts."""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable
from education_system.systems.sixth_form.domain.operations.communications.parent_contacts import parent_contacts
from education_system.systems.sixth_form.domain.operations.communications.parent_contacts import parent_contacts as data
from education_system.systems.sixth_form.domain.learners.students import students as student_data
from education_system.platform import branding
from education_system.systems.sixth_form.domain.operations.communications.parent_contacts.parent_contacts import (
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


def open_directory(parent=None) -> None:
    data.init_db()
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"Parent Contacts — {branding.SYSTEM_NAME}")
    win.geometry(WIN_GEOMETRY)
    win.minsize(*WIN_MINSIZE)
    ContactsDirectory(win)


def _student_options() -> list[tuple[str, str]]:
    rows = sorted(student_data.list_students(),
                   key=lambda s: s.student_id)
    return [(s.student_id, f"{s.student_id} — {s.full_name}") for s in rows]


def _name_lookup() -> dict[str, str]:
    return {s.student_id: s.full_name for s in student_data.list_students()}


class ContactsDirectory:
    def __init__(self, root: tk.Misc) -> None:
        self.root = root
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.root)
        bar.pack(fill="x", padx=10, pady=(10, 4))
        ttk.Label(bar, text="Search:").pack(side="left")
        self.q_e = ttk.Entry(bar, width=24)
        self.q_e.pack(side="left", padx=(2, 10))
        self.q_e.bind("<Return>", lambda _e: self.refresh())

        ttk.Label(bar, text="Student ID:").pack(side="left")
        self.f_student = ttk.Entry(bar, width=12)
        self.f_student.pack(side="left", padx=(2, 10))

        ttk.Label(bar, text="Relationship:").pack(side="left")
        self.f_rel = ttk.Combobox(bar, values=("",) + RELATIONSHIPS,
                                     state="readonly", width=16)
        self.f_rel.current(0)
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
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="right")

    def _clear(self) -> None:
        self.q_e.delete(0, "end")
        self.f_student.delete(0, "end")
        self.f_rel.current(0)
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
                    student_id=self.f_student.get().strip() or None,
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
        self.win = tk.Toplevel(parent)
        self.win.title("Edit Contact" if existing else "New Contact")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        self._build()

    def _build(self) -> None:
        form = ttk.Frame(self.win)
        form.pack(fill="both", expand=True, padx=12, pady=12)
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
            opts = _student_options()
            self._student_ids = [s for s, _ in opts]
            self.student_cb = ttk.Combobox(
                form, values=[l for _, l in opts],
                state="readonly", width=40)
            if opts:
                self.student_cb.current(0)
            self.student_cb.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        ttk.Label(form, text="Relationship:").grid(row=r, column=0,
                                                     sticky="e", pady=3)
        self.rel_cb = ttk.Combobox(form, values=RELATIONSHIPS,
                                      state="readonly", width=18)
        self.rel_cb.set(self.existing.relationship if self.existing
                          else DEFAULT_RELATIONSHIP)
        self.rel_cb.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        ttk.Label(form, text="Title:").grid(row=r, column=0,
                                              sticky="e", pady=3)
        self.title_e = ttk.Entry(form, width=10)
        if self.existing and self.existing.title:
            self.title_e.insert(0, self.existing.title)
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
        self.method_cb = ttk.Combobox(form,
                                          values=PREFERRED_CONTACT_METHODS,
                                          state="readonly", width=18)
        self.method_cb.set(self.existing.preferred_method
                              if self.existing
                              else DEFAULT_PREFERRED_METHOD)
        self.method_cb.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        ttk.Label(form, text="Language:").grid(row=r, column=0,
                                                  sticky="e", pady=3)
        self.lang_cb = ttk.Combobox(form, values=LANGUAGES,
                                       state="readonly", width=14)
        self.lang_cb.set(self.existing.preferred_language
                            if self.existing else DEFAULT_LANGUAGE)
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

        bar = ttk.Frame(form)
        bar.grid(row=r, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Save", command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        if self.student_cb is not None:
            idx = self.student_cb.current()
            if idx < 0:
                messagebox.showerror("Validation", "Pick a student.")
                return
            sid = self._student_ids[idx]
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
