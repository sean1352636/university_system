"""Extracted ChurchManagementSystem behaviour."""
from ... import *

class ChurchUiDialogsAttendanceDialogMixin:
    def record_attendance(self):
        """Record attendance for a service."""
        dialog = tk.Toplevel(self.root)
        dialog.title(_t("church.attendance.record_title"))
        dialog.geometry("400x300")
        dialog.configure(bg="white")
        dialog.transient(self.root)

        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - 400) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 300) // 2
        dialog.geometry(f"+{x}+{y}")
        dialog.wait_visibility()
        dialog.grab_set()

        tk.Label(dialog, text=_t("church.attendance.fields.service"), bg="white").grid(row=0, column=0, padx=20, pady=10)
        service = ttk.Combobox(dialog, values=["Sunday Morning", "Sunday Evening", "Wednesday", "Special Event"])
        service.grid(row=0, column=1, padx=20, pady=10)
        service.set("Sunday Morning")

        tk.Label(dialog, text=_t("church.attendance.fields.adults"), bg="white").grid(row=1, column=0, padx=20, pady=10)
        adults = tk.Entry(dialog)
        adults.grid(row=1, column=1, padx=20, pady=10)

        tk.Label(dialog, text=_t("church.attendance.fields.children"), bg="white").grid(row=2, column=0, padx=20, pady=10)
        children = tk.Entry(dialog)
        children.grid(row=2, column=1, padx=20, pady=10)

        tk.Label(dialog, text=_t("church.donations.fields.notes"), bg="white").grid(row=3, column=0, padx=20, pady=10)
        notes = tk.Entry(dialog, width=30)
        notes.grid(row=3, column=1, padx=20, pady=10)

        def save():
            try:
                record = {
                    'date': datetime.now().strftime("%Y-%m-%d"),
                    'service': service.get(),
                    'adults': int(adults.get() or 0),
                    'children': int(children.get() or 0),
                    'notes': notes.get(),
                    'recorded_by': self.current_user.get('username', 'Unknown')
                }
                self.attendance_records.append(record)
                self.save_data()
                messagebox.showinfo(_t("church.common.success"), _t("church.attendance.success_recorded"))
                dialog.destroy()
                self.show_attendance()
            except ValueError:
                messagebox.showerror(_t("church.common.error"), _t("church.errors.valid_numbers"))

        tk.Button(dialog, text=_t("church.common.save"), command=save, bg="#27ae60", fg="white",
                 cursor="hand2").grid(row=4, column=0, columnspan=2, pady=20)
