"""Extracted ChurchManagementSystem behaviour."""
from ... import *

class ChurchUiDialogsMemberDialogMixin:
    def add_member(self):
        """Add a new member - auto-fill with current user info."""
        dialog = tk.Toplevel(self.root)
        dialog.title(_t("church.members.add_new_member"))
        dialog.geometry("400x400")
        dialog.configure(bg="white")
        dialog.transient(self.root)

        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - 400) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 400) // 2
        dialog.geometry(f"+{x}+{y}")
        dialog.wait_visibility()
        dialog.grab_set()

        # Pre-fill with current user info
        default_name = self.get_user_display_name()
        default_email = self.get_user_email()

        fields = [
            ("Name:", default_name),
            ("Email:", default_email),
            ("Phone:", ""),
            ("Address:", ""),
        ]
        entries = {}

        for i, (field, default) in enumerate(fields):
            tk.Label(dialog, text=field, bg="white", font=("Arial", 11)).grid(row=i, column=0, padx=20, pady=10, sticky="e")
            entry = tk.Entry(dialog, width=30)
            entry.insert(0, default)
            entry.grid(row=i, column=1, padx=20, pady=10)
            entries[field] = entry

        # Status dropdown
        tk.Label(dialog, text=_t("church.members.fields.status"), bg="white", font=("Arial", 11)).grid(row=4, column=0, padx=20, pady=10, sticky="e")
        status_combo = ttk.Combobox(dialog, values=["Active", "Inactive", "Visitor"], width=27)
        status_combo.set("Active")
        status_combo.grid(row=4, column=1, padx=20, pady=10)
        entries["Status:"] = status_combo

        def save():
            member = {
                'name': entries["Name:"].get(),
                'email': entries["Email:"].get(),
                'phone': entries["Phone:"].get(),
                'address': entries["Address:"].get(),
                'status': entries["Status:"].get(),
                'join_date': datetime.now().strftime("%Y-%m-%d"),
                'added_by': self.current_user.get('username', 'Unknown')
            }
            if member['name']:
                self.members.append(member)
                self.save_data()
                messagebox.showinfo(_t("church.common.success"), _t("church.members.success_added", name=member['name']))
                dialog.destroy()
                self.show_members()
            else:
                messagebox.showerror(_t("church.common.error"), _t("church.errors.name_required"))

        tk.Button(dialog, text=_t("church.common.save"), command=save, bg="#27ae60", fg="white",
                  font=("Arial", 11), width=15, cursor="hand2").grid(row=5, column=0, columnspan=2, pady=20)

    def edit_member(self):
        """Edit an existing member's information."""
        selection = self.member_tree.selection()
        if not selection:
            messagebox.showwarning(_t("church.common.warning"), _t("church.errors.select_member"))
            return

        item = self.member_tree.item(selection[0])
        idx = int(item['values'][0]) - 1
        member = self.members[idx]

        dialog = tk.Toplevel(self.root)
        dialog.title(_t("church.members.edit_member_title"))
        dialog.geometry("400x400")
        dialog.configure(bg="white")
        dialog.transient(self.root)

        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - 400) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 400) // 2
        dialog.geometry(f"+{x}+{y}")
        dialog.wait_visibility()
        dialog.grab_set()

        fields = [("Name:", member['name']), ("Email:", member['email']),
                  ("Phone:", member['phone']), ("Address:", member.get('address', ''))]
        entries = {}

        for i, (field, value) in enumerate(fields):
            tk.Label(dialog, text=field, bg="white", font=("Arial", 11)).grid(row=i, column=0, padx=20, pady=10, sticky="e")
            entry = tk.Entry(dialog, width=30)
            entry.insert(0, value)
            entry.grid(row=i, column=1, padx=20, pady=10)
            entries[field] = entry

        tk.Label(dialog, text=_t("church.members.fields.status"), bg="white", font=("Arial", 11)).grid(row=4, column=0, padx=20, pady=10, sticky="e")
        status_combo = ttk.Combobox(dialog, values=["Active", "Inactive", "Visitor"], width=27)
        status_combo.set(member['status'])
        status_combo.grid(row=4, column=1, padx=20, pady=10)
        entries["Status:"] = status_combo

        def save():
            self.members[idx] = {
                'name': entries["Name:"].get(),
                'email': entries["Email:"].get(),
                'phone': entries["Phone:"].get(),
                'address': entries["Address:"].get(),
                'status': entries["Status:"].get(),
                'join_date': member['join_date']
            }
            self.save_data()
            messagebox.showinfo(_t("church.common.success"), _t("church.members.success_updated"))
            dialog.destroy()
            self.show_members()

        tk.Button(dialog, text=_t("church.common.save_changes"), command=save, bg="#3498db", fg="white",
                  font=("Arial", 11), width=15, cursor="hand2").grid(row=5, column=0, columnspan=2, pady=20)

    def delete_member(self):
        """Delete a member from the church."""
        selection = self.member_tree.selection()
        if not selection:
            messagebox.showwarning(_t("church.common.warning"), _t("church.errors.select_member_delete"))
            return

        item = self.member_tree.item(selection[0])
        idx = int(item['values'][0]) - 1
        name = self.members[idx]['name']

        if messagebox.askyesno(_t("church.common.confirm_delete"), _t("church.members.confirm_delete", name=name)):
            del self.members[idx]
            self.save_data()
            messagebox.showinfo(_t("church.common.success"), _t("church.members.success_deleted"))
            self.show_members()
