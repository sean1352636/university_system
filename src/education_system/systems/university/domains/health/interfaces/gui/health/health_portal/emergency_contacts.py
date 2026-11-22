from education_system.systems.university.infrastructure.i18n import get_text as _t
import tkinter as tk
from tkinter import ttk
from education_system.systems.university.domains.health.interfaces.gui.health._dialogs import messagebox

from education_system.systems.university.domains.health.domain.health.services import (
    contacts as contacts_service,
)
from education_system.systems.university.domains.health.interfaces.gui.health.health_portal import access_ui


class EmergencyContactsMixin:
    """Mixin for emergency contact management.

    Reads and writes ``emergency_contacts`` through
    ``domain/health/services/contacts`` (one layout, keyed on the student
    number): the health team works on any student, a student on their own
    (their number is filled in and locked). Every look is audited."""

    def create_manage_emergency_contacts(self):
        """Manage emergency contacts interface"""
        content_frame = ttk.Frame(self.content_area)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        title_label = ttk.Label(content_frame, text=_t('gui.pastoral.health.health_portal.emergency_contacts.labels.emergency_contacts_management', default="Emergency Contacts Management"),
                               font=('Arial', 16, 'bold'))
        title_label.pack(pady=(0, 20))

        student_row = ttk.Frame(content_frame)
        student_row.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(student_row, text="Student number:*").pack(side=tk.LEFT)
        self.contact_student_var = tk.StringVar()
        self.contact_student = ttk.Entry(student_row, textvariable=self.contact_student_var,
                                         width=16)
        self.contact_student.pack(side=tk.LEFT, padx=(10, 10))
        ttk.Button(student_row, text="Show contacts",
                   command=self.load_emergency_contacts_display).pack(side=tk.LEFT)
        access_ui.lock_to_own(self.auth, self.contact_student_var, self.contact_student)
        self.editing_contact_id = None

        form_frame = ttk.LabelFrame(content_frame, text=_t('gui.pastoral.health.health_portal.emergency_contacts.labels.add_emergency_contact', default="Add Emergency Contact"), padding=15)
        form_frame.pack(fill=tk.X, pady=(0, 20))
        self.contact_form_frame = form_frame

        ttk.Label(form_frame, text=_t('gui.pastoral.health.health_portal.emergency_contacts.labels.full_name', default="Full Name:*")).grid(row=0, column=0, sticky=tk.W, pady=5)
        self.contact_name = ttk.Entry(form_frame, width=25)
        self.contact_name.grid(row=0, column=1, sticky=tk.W, padx=(10, 20), pady=5)

        ttk.Label(form_frame, text=_t('gui.pastoral.health.health_portal.emergency_contacts.labels.relationship', default="Relationship:*")).grid(row=0, column=2, sticky=tk.W, pady=5)
        self.contact_relationship = ttk.Combobox(form_frame, width=22, values=[
            "Parent", "Guardian", "Spouse", "Partner", "Sibling", "Relative", "Friend", "Other"
        ])
        self.contact_relationship.grid(row=0, column=3, sticky=tk.W, padx=(10, 0), pady=5)

        ttk.Label(form_frame, text=_t('gui.pastoral.health.health_portal.emergency_contacts.labels.phone_number', default="Phone Number:*")).grid(row=1, column=0, sticky=tk.W, pady=5)
        self.contact_phone = ttk.Entry(form_frame, width=25)
        self.contact_phone.grid(row=1, column=1, sticky=tk.W, padx=(10, 20), pady=5)

        ttk.Label(form_frame, text=_t('gui.pastoral.health.health_portal.emergency_contacts.labels.email', default="Email:")).grid(row=1, column=2, sticky=tk.W, pady=5)
        self.contact_email = ttk.Entry(form_frame, width=22)
        self.contact_email.grid(row=1, column=3, sticky=tk.W, padx=(10, 0), pady=5)

        ttk.Label(form_frame, text="Other phone:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.contact_phone2 = ttk.Entry(form_frame, width=25)
        self.contact_phone2.grid(row=2, column=1, sticky=tk.W, padx=(10, 20), pady=5)

        ttk.Label(form_frame, text="Address:").grid(row=2, column=2, sticky=tk.W, pady=5)
        self.contact_address = ttk.Entry(form_frame, width=22)
        self.contact_address.grid(row=2, column=3, sticky=tk.W, padx=(10, 0), pady=5)

        self.contact_primary = tk.BooleanVar()
        self.contact_decision_maker = tk.BooleanVar()
        ttk.Checkbutton(form_frame, text="Primary contact",
                        variable=self.contact_primary).grid(row=3, column=1, sticky=tk.W)
        ttk.Checkbutton(form_frame, text="Medical decision maker",
                        variable=self.contact_decision_maker).grid(row=3, column=3, sticky=tk.W)

        button_frame = ttk.Frame(content_frame)
        button_frame.pack(fill=tk.X, pady=10)

        self.contact_save_button = ttk.Button(button_frame, text=_t('gui.pastoral.health.health_portal.emergency_contacts.buttons.add_contact', default="Add Contact"),
                  command=self.save_emergency_contact)
        self.contact_save_button.pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text=_t('gui.pastoral.health.health_portal.emergency_contacts.buttons.clear_form', default="Clear Form"),
                  command=self.clear_contact_form).pack(side=tk.LEFT)
        ttk.Button(button_frame, text="Edit selected",
                   command=self.edit_selected_contact).pack(side=tk.LEFT, padx=(10, 0))
        ttk.Button(button_frame, text="Make primary",
                   command=self.make_selected_contact_primary).pack(side=tk.LEFT, padx=(10, 0))
        ttk.Button(button_frame, text="Remove selected",
                   command=self.remove_selected_contact).pack(side=tk.LEFT, padx=(10, 0))

        display_frame = ttk.LabelFrame(content_frame, text=_t('gui.pastoral.health.health_portal.emergency_contacts.labels.current_emergency_contacts', default="Current Emergency Contacts"), padding=15)
        display_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("id", "name", "relationship", "phone", "other", "email", "primary",
                   "decision")
        headings = ("ID", "Name", "Relationship", "Phone", "Other phone", "Email", "Primary",
                    "Medical decisions")
        self.contacts_tree = ttk.Treeview(display_frame, columns=columns, show="headings",
                                          height=8)
        for column, heading in zip(columns, headings):
            self.contacts_tree.heading(column, text=heading)
            self.contacts_tree.column(column, width=60 if column in ("id", "primary") else 130)
        scroll = ttk.Scrollbar(display_frame, orient=tk.VERTICAL,
                               command=self.contacts_tree.yview)
        self.contacts_tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.contacts_tree.pack(fill=tk.BOTH, expand=True)
        self.contacts_tree.bind("<Double-1>", lambda _e: self.edit_selected_contact())
        self._contact_rows = {}

        if self.contact_student_var.get():
            self.load_emergency_contacts_display()

    def _contact_student(self):
        typed = self.contact_student_var.get().strip()
        if not typed and access_ui.own_student_id(self.auth) is None:
            messagebox.showerror(access_ui.TITLE, "Enter the student number first.",
                                 parent=self.root)
            return None
        sid = access_ui.scoped_student(self.root, self.auth, typed,
                                       var=self.contact_student_var,
                                       widget=self.contact_student)
        return sid or None

    def save_emergency_contact(self):
        """Save new emergency contact (or the one being edited)"""
        if not self.validate_contact_form():
            return
        student_id = self._contact_student()
        if not student_id:
            return
        data = {
            "contact_name": self.contact_name.get().strip(),
            "relationship": self.contact_relationship.get().strip(),
            "phone_primary": self.contact_phone.get().strip(),
            "phone_secondary": self.contact_phone2.get().strip() or None,
            "email": self.contact_email.get().strip() or None,
            "address": self.contact_address.get().strip() or None,
            "is_primary": self.contact_primary.get(),
            "medical_decision_maker": self.contact_decision_maker.get(),
        }
        editing = self.editing_contact_id
        try:
            contacts_service.save_contact(access_ui.who(self.auth), student_id, data,
                                          contact_id=editing)
        except (PermissionError, ValueError) as e:
            messagebox.showerror(_t('gui.pastoral.health.health_portal.emergency_contacts.dialogs.error', default="Error"), str(e), parent=self.root)
            return
        except Exception as e:
            messagebox.showerror(_t('gui.pastoral.health.health_portal.emergency_contacts.dialogs.error', default="Error"), f"Failed to save emergency contact: {str(e)}", parent=self.root)
            return
        self.clear_contact_form()
        self.load_emergency_contacts_display()
        messagebox.showinfo(_t('gui.pastoral.health.health_portal.emergency_contacts.dialogs.success', default="Success"),
                            "Emergency contact updated." if editing else _t('gui.pastoral.health.health_portal.emergency_contacts.dialogs.emergency_contact_added_successfully', default="Emergency contact added successfully!"),
                            parent=self.root)

    def validate_contact_form(self):
        """Validate emergency contact form"""
        if not self.contact_name.get().strip():
            messagebox.showerror(_t('gui.pastoral.health.health_portal.emergency_contacts.dialogs.validation_error', default="Validation Error"), _t('gui.pastoral.health.health_portal.emergency_contacts.dialogs.contact_name_is_required', default="Contact name is required."))
            return False

        if not self.contact_relationship.get():
            messagebox.showerror(_t('gui.pastoral.health.health_portal.emergency_contacts.dialogs.validation_error', default="Validation Error"), _t('gui.pastoral.health.health_portal.emergency_contacts.dialogs.relationship_is_required', default="Relationship is required."))
            return False

        if not self.contact_phone.get().strip():
            messagebox.showerror(_t('gui.pastoral.health.health_portal.emergency_contacts.dialogs.validation_error', default="Validation Error"), _t('gui.pastoral.health.health_portal.emergency_contacts.dialogs.phone_number_is_required', default="Phone number is required."))
            return False

        return True

    def clear_contact_form(self):
        """Clear the emergency contact form"""
        self.contact_name.delete(0, tk.END)
        self.contact_relationship.set('')
        self.contact_phone.delete(0, tk.END)
        self.contact_email.delete(0, tk.END)
        self.contact_phone2.delete(0, tk.END)
        self.contact_address.delete(0, tk.END)
        self.contact_primary.set(False)
        self.contact_decision_maker.set(False)
        self.editing_contact_id = None
        self.contact_form_frame.configure(text=_t('gui.pastoral.health.health_portal.emergency_contacts.labels.add_emergency_contact', default="Add Emergency Contact"))
        self.contact_save_button.configure(text=_t('gui.pastoral.health.health_portal.emergency_contacts.buttons.add_contact', default="Add Contact"))

    def load_emergency_contacts_display(self):
        """Load and display the student's emergency contacts"""
        for item in self.contacts_tree.get_children():
            self.contacts_tree.delete(item)
        self._contact_rows = {}
        student_id = self._contact_student()
        if not student_id:
            return
        try:
            rows = contacts_service.list_contacts(access_ui.who(self.auth), student_id)
        except PermissionError as e:
            messagebox.showerror(access_ui.TITLE, str(e), parent=self.root)
            return
        except Exception as e:
            messagebox.showerror(access_ui.TITLE, f"Error loading contacts: {str(e)}",
                                 parent=self.root)
            return
        for row in rows:
            self._contact_rows[str(row["id"])] = row
            self.contacts_tree.insert("", tk.END, iid=str(row["id"]), values=(
                row["id"], row["contact_name"] or "", row["relationship"] or "",
                row["phone_primary"] or "", row["phone_secondary"] or "", row["email"] or "",
                "Yes" if row["is_primary"] else "", "Yes" if row["medical_decision_maker"] else ""))
        if not rows:
            self.contacts_tree.insert("", tk.END, values=("", "No emergency contacts yet — "
                                                          "add one above", "", "", "", "", "",
                                                          ""))

    def _selected_contact(self):
        selected = self.contacts_tree.selection()
        row = self._contact_rows.get(selected[0]) if selected else None
        if row is None:
            messagebox.showinfo(access_ui.TITLE, "Select a contact first.", parent=self.root)
        return row

    def edit_selected_contact(self):
        row = self._selected_contact()
        if row is None:
            return
        self.clear_contact_form()
        self.contact_name.insert(0, row["contact_name"] or "")
        self.contact_relationship.set(row["relationship"] or "")
        self.contact_phone.insert(0, row["phone_primary"] or "")
        self.contact_phone2.insert(0, row["phone_secondary"] or "")
        self.contact_email.insert(0, row["email"] or "")
        self.contact_address.insert(0, row["address"] or "")
        self.contact_primary.set(bool(row["is_primary"]))
        self.contact_decision_maker.set(bool(row["medical_decision_maker"]))
        self.editing_contact_id = row["id"]
        self.contact_form_frame.configure(text=f"Edit Emergency Contact #{row['id']}")
        self.contact_save_button.configure(text="Save Changes")

    def make_selected_contact_primary(self):
        row = self._selected_contact()
        if row is None:
            return
        try:
            contacts_service.set_primary(access_ui.who(self.auth), row["student_id"], row["id"])
        except Exception as e:
            messagebox.showerror(access_ui.TITLE, str(e), parent=self.root)
            return
        self.load_emergency_contacts_display()

    def remove_selected_contact(self):
        row = self._selected_contact()
        if row is None:
            return
        if not messagebox.askyesno(access_ui.TITLE, f"Remove {row['contact_name']} as an "
                                   "emergency contact?", parent=self.root):
            return
        try:
            contacts_service.delete_contact(access_ui.who(self.auth), row["student_id"],
                                            row["id"])
        except Exception as e:
            messagebox.showerror(access_ui.TITLE, str(e), parent=self.root)
            return
        self.clear_contact_form()
        self.load_emergency_contacts_display()
