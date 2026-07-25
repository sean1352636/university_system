import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime


class EmergencyContactsMixin:
    """Mixin for emergency contact management."""

    def create_manage_emergency_contacts(self):
        """Manage emergency contacts interface"""
        content_frame = ttk.Frame(self.content_area)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        title_label = ttk.Label(content_frame, text="Emergency Contacts Management",
                               font=('Arial', 16, 'bold'))
        title_label.pack(pady=(0, 20))

        form_frame = ttk.LabelFrame(content_frame, text="Add Emergency Contact", padding=15)
        form_frame.pack(fill=tk.X, pady=(0, 20))

        ttk.Label(form_frame, text="Full Name:*").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.contact_name = ttk.Entry(form_frame, width=25)
        self.contact_name.grid(row=0, column=1, sticky=tk.W, padx=(10, 20), pady=5)

        ttk.Label(form_frame, text="Relationship:*").grid(row=0, column=2, sticky=tk.W, pady=5)
        self.contact_relationship = ttk.Combobox(form_frame, width=22, values=[
            "Parent", "Guardian", "Spouse", "Sibling", "Relative", "Friend", "Other"
        ])
        self.contact_relationship.grid(row=0, column=3, sticky=tk.W, padx=(10, 0), pady=5)

        ttk.Label(form_frame, text="Phone Number:*").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.contact_phone = ttk.Entry(form_frame, width=25)
        self.contact_phone.grid(row=1, column=1, sticky=tk.W, padx=(10, 20), pady=5)

        ttk.Label(form_frame, text="Email:").grid(row=1, column=2, sticky=tk.W, pady=5)
        self.contact_email = ttk.Entry(form_frame, width=22)
        self.contact_email.grid(row=1, column=3, sticky=tk.W, padx=(10, 0), pady=5)

        button_frame = ttk.Frame(content_frame)
        button_frame.pack(fill=tk.X, pady=10)

        ttk.Button(button_frame, text="Add Contact",
                  command=self.save_emergency_contact).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="Clear Form",
                  command=self.clear_contact_form).pack(side=tk.LEFT)

        display_frame = ttk.LabelFrame(content_frame, text="Current Emergency Contacts", padding=15)
        display_frame.pack(fill=tk.BOTH, expand=True)

        self.contacts_text = scrolledtext.ScrolledText(display_frame, wrap=tk.WORD, height=10)
        self.contacts_text.pack(fill=tk.BOTH, expand=True)

        self.load_emergency_contacts_display()

    def save_emergency_contact(self):
        """Save new emergency contact"""
        if not self.validate_contact_form():
            return

        try:
            contact_info = f"Name: {self.contact_name.get()}\n"
            contact_info += f"Relationship: {self.contact_relationship.get()}\n"
            contact_info += f"Phone: {self.contact_phone.get()}\n"
            contact_info += f"Email: {self.contact_email.get()}\n"
            contact_info += f"Added: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            contact_info += "-" * 40 + "\n"

            self.contacts_text.insert(tk.END, contact_info)
            self.clear_contact_form()
            messagebox.showinfo("Success", "Emergency contact added successfully!")
            self.log_audit_event('add_emergency_contact', 'emergency_contact', self.contact_name.get())

        except Exception as e:
            messagebox.showerror("Error", f"Failed to save emergency contact: {str(e)}")

    def validate_contact_form(self):
        """Validate emergency contact form"""
        if not self.contact_name.get().strip():
            messagebox.showerror("Validation Error", "Contact name is required.")
            return False

        if not self.contact_relationship.get():
            messagebox.showerror("Validation Error", "Relationship is required.")
            return False

        if not self.contact_phone.get().strip():
            messagebox.showerror("Validation Error", "Phone number is required.")
            return False

        return True

    def clear_contact_form(self):
        """Clear the emergency contact form"""
        self.contact_name.delete(0, tk.END)
        self.contact_relationship.set('')
        self.contact_phone.delete(0, tk.END)
        self.contact_email.delete(0, tk.END)

    def load_emergency_contacts_display(self):
        """Load and display emergency contacts"""
        try:
            empty_state_text = "No emergency contacts are loaded for this session.\n"
            empty_state_text += "Use the form above to add a new emergency contact.\n"
            self.contacts_text.insert(tk.END, empty_state_text)
        except Exception as e:
            self.contacts_text.insert(tk.END, f"Error loading contacts: {str(e)}")
