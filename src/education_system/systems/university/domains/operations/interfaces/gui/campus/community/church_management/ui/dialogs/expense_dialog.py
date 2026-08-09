"""Extracted ChurchManagementSystem behaviour."""
from ... import *

class ChurchUiDialogsExpenseDialogMixin:
    def add_expense(self):
        """Add a new expense."""
        dialog = tk.Toplevel(self.root)
        dialog.title(_t("church.expenses.add_title"))
        dialog.geometry("400x350")
        dialog.configure(bg="white")
        dialog.transient(self.root)

        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - 400) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 350) // 2
        dialog.geometry(f"+{x}+{y}")
        dialog.wait_visibility()
        dialog.grab_set()

        fields = {
            "Description:": None,
            "Amount (£):": None,
            "Category:": ["Utilities", "Supplies", "Salaries", "Maintenance", "Missions", "Events", "Other"],
            "Approved By:": None
        }
        entries = {}

        for i, (field, options) in enumerate(fields.items()):
            tk.Label(dialog, text=field, bg="white").grid(row=i, column=0, padx=20, pady=10, sticky="e")
            if options:
                entry = ttk.Combobox(dialog, values=options, width=27)
                entry.set(options[0])
            else:
                entry = tk.Entry(dialog, width=30)
            entry.grid(row=i, column=1, padx=20, pady=10)
            entries[field] = entry

        def save():
            try:
                expense = {
                    'description': entries["Description:"].get(),
                    'amount': float(entries["Amount (£):"].get()),
                    'category': entries["Category:"].get(),
                    'approved_by': entries["Approved By:"].get() or self.get_user_display_name(),
                    'date': datetime.now().strftime("%Y-%m-%d"),
                    'recorded_by': self.current_user.get('username', 'Unknown')
                }
                self.expenses.append(expense)
                self.save_data()
                messagebox.showinfo(_t("church.common.success"), _t("church.expenses.success_recorded"))
                dialog.destroy()
                self.show_expenses()
            except ValueError:
                messagebox.showerror(_t("church.common.error"), _t("church.errors.valid_amount"))

        tk.Button(dialog, text=_t("church.common.save"), command=save, bg="#e74c3c", fg="white",
                 cursor="hand2").grid(row=len(fields), column=0, columnspan=2, pady=20)
