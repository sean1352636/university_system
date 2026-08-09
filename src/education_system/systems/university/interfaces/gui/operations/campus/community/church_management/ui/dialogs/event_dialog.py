"""Extracted ChurchManagementSystem behaviour."""
from ... import *

class ChurchUiDialogsEventDialogMixin:
    def add_event(self):
        """Add a new church event."""
        dialog = tk.Toplevel(self.root)
        dialog.title(_t("church.events.add_new_event"))
        dialog.geometry("400x350")
        dialog.configure(bg="white")
        dialog.transient(self.root)

        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - 400) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 350) // 2
        dialog.geometry(f"+{x}+{y}")
        dialog.wait_visibility()
        dialog.grab_set()

        fields = ["Event Name:", "Date (YYYY-MM-DD):", "Time:", "Location:", "Description:"]
        entries = {}

        for i, field in enumerate(fields):
            tk.Label(dialog, text=field, bg="white", font=("Arial", 11)).grid(row=i, column=0, padx=20, pady=10, sticky="e")
            entry = tk.Entry(dialog, width=30)
            entry.grid(row=i, column=1, padx=20, pady=10)
            entries[field] = entry

        def save():
            event = {
                'name': entries["Event Name:"].get(),
                'date': entries["Date (YYYY-MM-DD):"].get(),
                'time': entries["Time:"].get(),
                'location': entries["Location:"].get(),
                'description': entries["Description:"].get(),
                'created_by': self.current_user.get('username', 'Unknown')
            }
            if event['name'] and event['date']:
                self.events.append(event)
                self.save_data()
                messagebox.showinfo(_t("church.common.success"), _t("church.events.success_added"))
                dialog.destroy()
                self.show_events()
            else:
                messagebox.showerror(_t("church.common.error"), _t("church.errors.event_required"))

        tk.Button(dialog, text=_t("church.common.save"), command=save, bg="#27ae60", fg="white",
                  font=("Arial", 11), width=15, cursor="hand2").grid(row=len(fields), column=0, columnspan=2, pady=20)
