
from education_system.systems.university.infrastructure.i18n import get_text as _t
from ._common import filedialog, json, messagebox, scrolledtext, tk, ttk

class GDPRChatDialog:
    """Per-user export / erase tools (GDPR)."""

    def __init__(self, parent, dashboard):
        self.dashboard = dashboard
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t('gui.shell.email.email_gui.chat_dialogs.misc_dialogs.windows.my_chat_data_export_erase', default="My chat data (export / erase)"))
        self.dialog.geometry("480x220")
        self.dialog.transient(parent)
        frame = ttk.Frame(self.dialog, padding=15)
        frame.pack(fill=tk.BOTH, expand=True)
        ttk.Label(frame, justify=tk.LEFT, text=(
            _t('gui.shell.email.email_gui.chat_dialogs.misc_dialogs.labels.export_downloads_a_json_copy_of_every_chat_message_you_ve_sent_y', default="Export downloads a JSON copy of every chat message you've sent,\n"
            "your reactions, poll votes, and room memberships.\n\n"
            "Erase soft-deletes the contents of every chat message you've sent\n"
            "and removes your reactions, poll votes, typing/presence rows.\n"
            "This cannot be undone."))).pack(anchor=tk.W)
        btns = ttk.Frame(frame)
        btns.pack(fill=tk.X, pady=(15, 0))
        ttk.Button(btns, text=_t('gui.shell.email.email_gui.chat_dialogs.misc_dialogs.buttons.export_to_json', default="Export to JSON…"),
                   command=self._export).pack(side=tk.LEFT)
        ttk.Button(btns, text=_t('gui.shell.email.email_gui.chat_dialogs.misc_dialogs.buttons.erase_my_chat_history', default="Erase my chat history"),
                   command=self._erase).pack(side=tk.LEFT, padx=10)
        ttk.Button(btns, text=_t('gui.shell.email.email_gui.chat_dialogs.misc_dialogs.buttons.close', default="Close"),
                   command=self.dialog.destroy).pack(side=tk.RIGHT)

    def _export(self):
        try:
            data = self.dashboard.export_user_chat_history()
        except Exception as e:
            messagebox.showerror(_t('gui.shell.email.email_gui.chat_dialogs.misc_dialogs.dialogs.error', default="Error"), str(e), parent=self.dialog)
            return
        if not data:
            messagebox.showerror(_t('gui.shell.email.email_gui.chat_dialogs.misc_dialogs.dialogs.error', default="Error"), _t('gui.shell.email.email_gui.chat_dialogs.misc_dialogs.dialogs.nothing_to_export_or_not_authorised', default="Nothing to export (or not authorised)."),
                                 parent=self.dialog)
            return
        path = filedialog.asksaveasfilename(
            parent=self.dialog, defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("All files", "*.*")],
            initialfile=f"chat_export_user{data.get('user_id')}.json",
        )
        if not path:
            return
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            messagebox.showinfo(_t('gui.shell.email.email_gui.chat_dialogs.misc_dialogs.dialogs.exported', default="Exported"), f"Saved to {path}", parent=self.dialog)
        except Exception as e:
            messagebox.showerror(_t('gui.shell.email.email_gui.chat_dialogs.misc_dialogs.dialogs.error', default="Error"), str(e), parent=self.dialog)

    def _erase(self):
        if not messagebox.askyesno(
            _t('gui.shell.email.email_gui.chat_dialogs.misc_dialogs.dialogs.confirm_erasure', default="Confirm erasure"),
            _t('gui.shell.email.email_gui.chat_dialogs.misc_dialogs.dialogs.this_will_soft_delete_the_contents_of_every_chat_message_you_ve', default="This will soft-delete the contents of every chat message you've sent.\n"
            "It cannot be undone. Continue?"),
            parent=self.dialog,
        ):
            return
        try:
            ok = self.dashboard.erase_user_chat_history()
            if ok:
                messagebox.showinfo(_t('gui.shell.email.email_gui.chat_dialogs.misc_dialogs.dialogs.done', default="Done"), _t('gui.shell.email.email_gui.chat_dialogs.misc_dialogs.dialogs.your_chat_history_has_been_erased', default="Your chat history has been erased."),
                                    parent=self.dialog)
            else:
                messagebox.showerror(_t('gui.shell.email.email_gui.chat_dialogs.misc_dialogs.dialogs.error', default="Error"), _t('gui.shell.email.email_gui.chat_dialogs.misc_dialogs.dialogs.could_not_erase', default="Could not erase."), parent=self.dialog)
        except Exception as e:
            messagebox.showerror(_t('gui.shell.email.email_gui.chat_dialogs.misc_dialogs.dialogs.error', default="Error"), str(e), parent=self.dialog)


class UserProfileDialog:
    """Read-only snapshot of a user's profile (joined to staff_profiles +
    students). Opened on click of a sender name or @mention."""

    def __init__(self, parent, dashboard, user_id):
        self.dashboard = dashboard
        self.user_id = user_id
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t('gui.shell.email.email_gui.chat_dialogs.misc_dialogs.windows.user_profile', default="User profile"))
        self.dialog.geometry("420x420")
        self.dialog.transient(parent)
        self._build()

    def _build(self):
        try:
            profile = self.dashboard.get_user_profile(self.user_id)
        except Exception as e:
            ttk.Label(self.dialog, text=f"Error: {e}", padding=20).pack()
            return
        if not profile:
            ttk.Label(self.dialog, text=_t('gui.shell.email.email_gui.chat_dialogs.misc_dialogs.labels.user_not_found', default="User not found."),
                      padding=20).pack()
            ttk.Button(self.dialog, text=_t('gui.shell.email.email_gui.chat_dialogs.misc_dialogs.buttons.close', default="Close"),
                       command=self.dialog.destroy).pack(pady=(0, 10))
            return
        frame = ttk.Frame(self.dialog, padding=12)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text=profile.get('full_name') or profile.get('username'),
                  font=("TkDefaultFont", 13, "bold")).pack(anchor=tk.W)
        ttk.Label(frame, foreground="#666",
                  text=f"@{profile.get('username') or ''}  ·  "
                       f"role: {profile.get('role') or '—'}"
                  ).pack(anchor=tk.W, pady=(0, 8))
        if profile.get('email'):
            ttk.Label(frame, text=f"Email: {profile['email']}").pack(anchor=tk.W)
        if profile.get('student_id'):
            ttk.Label(frame, text=f"Student ID: {profile['student_id']}"
                      ).pack(anchor=tk.W, pady=(2, 0))
        staff = profile.get('staff') or {}
        if staff:
            ttk.Separator(frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=8)
            ttk.Label(frame, text=_t('gui.shell.email.email_gui.chat_dialogs.misc_dialogs.labels.staff_profile', default="Staff profile"),
                      font=("TkDefaultFont", 10, "bold")).pack(anchor=tk.W)
            for label, key in [
                ("Department", "department"), ("Job title", "job_title"),
                ("Employment", "employment_type"), ("Office", "office"),
                ("Phone ext.", "phone_ext"), ("Manager id", "manager_id"),
                ("Expertise", "expertise"),
            ]:
                v = staff.get(key)
                if v:
                    ttk.Label(frame, text=f"{label}: {v}").pack(anchor=tk.W)
            if staff.get('bio'):
                ttk.Label(frame, text=_t('gui.shell.email.email_gui.chat_dialogs.misc_dialogs.labels.bio', default="Bio:"),
                          font=("TkDefaultFont", 9, "bold")
                          ).pack(anchor=tk.W, pady=(6, 0))
                bio = scrolledtext.ScrolledText(frame, height=4, wrap=tk.WORD)
                bio.insert("1.0", staff['bio'])
                bio.config(state=tk.DISABLED)
                bio.pack(fill=tk.X)
        ttk.Button(frame, text=_t('gui.shell.email.email_gui.chat_dialogs.misc_dialogs.buttons.close', default="Close"),
                   command=self.dialog.destroy).pack(pady=(10, 0))

