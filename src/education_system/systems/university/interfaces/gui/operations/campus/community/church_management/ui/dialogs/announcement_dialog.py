"""Extracted ChurchManagementSystem behaviour."""
from ... import *

class ChurchUiDialogsAnnouncementDialogMixin:
    def add_announcement(self):
        """Add a new church announcement."""
        dialog = tk.Toplevel(self.root)
        dialog.title(_t("church.announcements.add_title"))
        dialog.geometry("500x350")
        dialog.configure(bg="white")
        dialog.transient(self.root)

        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - 500) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 350) // 2
        dialog.geometry(f"+{x}+{y}")
        dialog.wait_visibility()
        dialog.grab_set()

        tk.Label(dialog, text=_t("church.announcements.fields.title"), bg="white", font=("Arial", 11)).grid(row=0, column=0, padx=20, pady=10, sticky="e")
        title_entry = tk.Entry(dialog, width=40)
        title_entry.grid(row=0, column=1, padx=20, pady=10)

        tk.Label(dialog, text=_t("church.announcements.fields.content"), bg="white", font=("Arial", 11)).grid(row=1, column=0, padx=20, pady=10, sticky="ne")
        content_text = tk.Text(dialog, width=40, height=8)
        content_text.grid(row=1, column=1, padx=20, pady=10)

        def save():
            announcement = {
                'title': title_entry.get(),
                'content': content_text.get("1.0", tk.END).strip(),
                'date': datetime.now().strftime("%Y-%m-%d %H:%M"),
                'posted_by': self.get_user_display_name()
            }
            if announcement['title'] and announcement['content']:
                self.announcements.insert(0, announcement)
                self.save_data()
                messagebox.showinfo(_t("church.common.success"), _t("church.announcements.success_posted"))
                dialog.destroy()
                self.show_announcements()
            else:
                messagebox.showerror(_t("church.common.error"), _t("church.errors.fill_all_fields"))

        tk.Button(dialog, text=_t("church.announcements.post_announcement"), command=save, bg="#e74c3c", fg="white",
                  font=("Arial", 11), width=15, cursor="hand2").grid(row=2, column=0, columnspan=2, pady=20)
