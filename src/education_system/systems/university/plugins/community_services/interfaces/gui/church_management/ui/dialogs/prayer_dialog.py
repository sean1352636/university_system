"""Extracted ChurchManagementSystem behaviour."""
from ... import *

class ChurchUiDialogsPrayerDialogMixin:
    def add_prayer_request(self):
        """Add a new prayer request - uses current user."""
        dialog = tk.Toplevel(self.root)
        dialog.title(_t("church.prayer_requests.add_title"))
        dialog.geometry("450x350")
        dialog.configure(bg="white")
        dialog.transient(self.root)

        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - 450) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 350) // 2
        dialog.geometry(f"+{x}+{y}")
        dialog.wait_visibility()
        dialog.grab_set()

        default_name = self.get_user_display_name()

        tk.Label(dialog, text=_t("church.prayer_requests.fields.requester"), bg="white", font=("Arial", 11)).grid(row=0, column=0, padx=20, pady=10, sticky="e")
        name_label = tk.Label(dialog, text=default_name, bg="#f0f0f0", font=("Arial", 11),
                             padx=10, pady=5, width=30, anchor="w")
        name_label.grid(row=0, column=1, padx=20, pady=10)

        tk.Label(dialog, text=_t("church.prayer_requests.fields.request"), bg="white", font=("Arial", 11)).grid(row=1, column=0, padx=20, pady=10, sticky="ne")
        request_text = tk.Text(dialog, width=35, height=8)
        request_text.grid(row=1, column=1, padx=20, pady=10)

        def save():
            prayer = {
                'requested_by': default_name,
                'requester_id': self.current_user.get('username'),
                'request': request_text.get("1.0", tk.END).strip(),
                'date': datetime.now().strftime("%Y-%m-%d"),
                'status': "Active"
            }
            if prayer['request']:
                self.prayer_requests.append(prayer)
                self.save_data()
                messagebox.showinfo(_t("church.common.success"), _t("church.prayer_requests.success_added"))
                dialog.destroy()
                self.show_prayer_requests()
            else:
                messagebox.showerror(_t("church.common.error"), _t("church.errors.prayer_required"))

        tk.Button(dialog, text=_t("church.prayer_requests.submit_request"), command=save, bg="#9b59b6", fg="white",
                  font=("Arial", 11), width=15, cursor="hand2").grid(row=2, column=0, columnspan=2, pady=20)
