"""Extracted function implementation."""

from .. import bulk_operations_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def show_groups_result(self, groups):
    """Show the created groups result"""
    dialog = tk.Toplevel(self.master)
    dialog.title(f"👥 {_t('advanced_search.created_groups_dialog_title')}")
    dialog.geometry("1100x800")
    dialog.transient(self.master)

    frame = ttk.Frame(dialog, padding="20")
    frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(frame, text=_t("advanced_search.bulk_operations.created_groups_title", count=len(groups)),
             style='Title.TLabel').pack(pady=(0, 20))

    # Groups display
    groups_text = scrolledtext.ScrolledText(frame, height=20, wrap=tk.WORD)
    groups_text.pack(fill=tk.BOTH, expand=True, pady=(0, 20))

    for group_name, students in groups.items():
        groups_text.insert(tk.END, f"\n{group_name} ({len(students)} students):\n")
        groups_text.insert(tk.END, "-" * 50 + "\n")
        for student in students:
            name = f"{student[3]} {student[5]}"
            groups_text.insert(tk.END, f"  • {student[0]} - {name} ({student[1]})\n")
        groups_text.insert(tk.END, "\n")

    def export_groups():
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"student_groups_{timestamp}.txt"

        with open(filename, 'w', encoding='utf-8') as f:
            f.write(groups_text.get(1.0, tk.END))

        messagebox.showinfo(_t("advanced_search.bulk_operations.groups_exported_title"), _t("advanced_search.bulk_operations.groups_exported_msg", filename=filename))

    button_frame = ttk.Frame(frame)
    button_frame.pack(fill=tk.X)

    ttk.Button(button_frame, text=f"💾 {_t('advanced_search.bulk_operations.export_btn')}", command=export_groups).pack(side=tk.LEFT)
    ttk.Button(button_frame, text=f"❌ {_t('advanced_search.close_button')}", command=dialog.destroy).pack(side=tk.RIGHT)
