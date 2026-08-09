"""Extracted ChurchManagementSystem behaviour."""
from ... import *

class ChurchUiDialogsSmallGroupDialogMixin:
    def add_small_group(self):
        """Add a new small group."""
        dialog = tk.Toplevel(self.root)
        dialog.title(_t("church.small_groups.add_title"))
        dialog.geometry("400+350")
        dialog.configure(bg="white")
        dialog.transient(self.root)

        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - 400) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 350) // 2
        dialog.geometry(f"400x350+{x}+{y}")
        dialog.wait_visibility()
        dialog.grab_set()

        fields = ["Group Name:", "Leader:", "Meeting Day:", "Location:", "Member Count:"]
        entries = {}

        for i, field in enumerate(fields):
            tk.Label(dialog, text=field, bg="white").grid(row=i, column=0, padx=20, pady=10, sticky="e")
            if field == "Meeting Day:":
                entry = ttk.Combobox(dialog, values=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"])
            else:
                entry = tk.Entry(dialog, width=30)
            entry.grid(row=i, column=1, padx=20, pady=10)
            entries[field] = entry

        def save():
            group = {
                'name': entries["Group Name:"].get(),
                'leader': entries["Leader:"].get(),
                'meeting_day': entries["Meeting Day:"].get(),
                'location': entries["Location:"].get(),
                'member_count': int(entries["Member Count:"].get() or 0)
            }
            if group['name']:
                self.small_groups.append(group)
                self.save_data()
                messagebox.showinfo(_t("church.common.success"), _t("church.small_groups.success_added"))
                dialog.destroy()
                self.show_small_groups()

        tk.Button(dialog, text=_t("church.common.save"), command=save, bg="#27ae60", fg="white",
                 cursor="hand2").grid(row=len(fields), column=0, columnspan=2, pady=20)
