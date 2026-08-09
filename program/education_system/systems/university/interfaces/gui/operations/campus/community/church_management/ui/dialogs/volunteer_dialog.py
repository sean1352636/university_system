"""Extracted ChurchManagementSystem behaviour."""
from ... import *

class ChurchUiDialogsVolunteerDialogMixin:
    def add_volunteer(self):
        """Add a new volunteer - uses current user info."""
        dialog = tk.Toplevel(self.root)
        dialog.title(_t("church.volunteers.add_title"))
        dialog.geometry("450x450")
        dialog.configure(bg="white")
        dialog.transient(self.root)

        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - 450) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 450) // 2
        dialog.geometry(f"+{x}+{y}")
        dialog.wait_visibility()
        dialog.grab_set()

        default_name = self.get_user_display_name()
        default_email = self.get_user_email()

        entries = {}

        tk.Label(dialog, text=_t("church.volunteers.fields.name"), bg="white", font=("Arial", 11)).grid(row=0, column=0, padx=20, pady=10, sticky="e")
        name_entry = tk.Entry(dialog, width=30)
        name_entry.insert(0, default_name)
        name_entry.grid(row=0, column=1, padx=20, pady=10)
        entries["Name:"] = name_entry

        tk.Label(dialog, text=_t("church.volunteers.fields.ministry"), bg="white", font=("Arial", 11)).grid(row=1, column=0, padx=20, pady=10, sticky="e")
        ministry_combo = ttk.Combobox(dialog, values=["Worship", "Children's", "Youth", "Hospitality", "Tech", "Missions", "Other"], width=27)
        ministry_combo.set("Worship")
        ministry_combo.grid(row=1, column=1, padx=20, pady=10)
        entries["Ministry:"] = ministry_combo

        tk.Label(dialog, text=_t("church.volunteers.fields.role"), bg="white", font=("Arial", 11)).grid(row=2, column=0, padx=20, pady=10, sticky="e")
        role_entry = tk.Entry(dialog, width=30)
        role_entry.grid(row=2, column=1, padx=20, pady=10)
        entries["Role:"] = role_entry

        tk.Label(dialog, text=_t("church.volunteers.fields.phone"), bg="white", font=("Arial", 11)).grid(row=3, column=0, padx=20, pady=10, sticky="e")
        phone_entry = tk.Entry(dialog, width=30)
        phone_entry.grid(row=3, column=1, padx=20, pady=10)
        entries["Phone:"] = phone_entry

        tk.Label(dialog, text=_t("church.donations.fields.email"), bg="white", font=("Arial", 11)).grid(row=4, column=0, padx=20, pady=10, sticky="e")
        email_entry = tk.Entry(dialog, width=30)
        email_entry.insert(0, default_email)
        email_entry.grid(row=4, column=1, padx=20, pady=10)
        entries["Email:"] = email_entry

        tk.Label(dialog, text=_t("church.volunteers.fields.availability"), bg="white", font=("Arial", 11)).grid(row=5, column=0, padx=20, pady=10, sticky="e")
        avail_combo = ttk.Combobox(dialog, values=["Sundays", "Weekdays", "Weekends", "Flexible"], width=27)
        avail_combo.set("Sundays")
        avail_combo.grid(row=5, column=1, padx=20, pady=10)
        entries["Availability:"] = avail_combo

        def save():
            volunteer = {
                'name': entries["Name:"].get(),
                'ministry': entries["Ministry:"].get(),
                'role': entries["Role:"].get(),
                'phone': entries["Phone:"].get(),
                'email': entries["Email:"].get(),
                'availability': entries["Availability:"].get()
            }
            if volunteer['name']:
                self.volunteers.append(volunteer)
                self.save_data()
                messagebox.showinfo(_t("church.common.success"), _t("church.volunteers.success_added"))
                dialog.destroy()
                self.show_volunteers()
            else:
                messagebox.showerror(_t("church.common.error"), _t("church.errors.name_required"))

        tk.Button(dialog, text=_t("church.common.save"), command=save, bg="#27ae60", fg="white",
                  font=("Arial", 11), width=15, cursor="hand2").grid(row=6, column=0, columnspan=2, pady=20)
