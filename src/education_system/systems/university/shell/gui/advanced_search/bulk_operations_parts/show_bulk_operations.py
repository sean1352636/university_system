"""Extracted function implementation."""

from .. import bulk_operations_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def show_bulk_operations(self):
    """Show bulk operations menu"""
    if not self.search_results:
        messagebox.showwarning(_t("advanced_search.bulk_operations.no_results_title"), _t("advanced_search.bulk_operations.search_first_msg"))
        return

    dialog = tk.Toplevel(self.master)
    dialog.title(f"🔧 {_t('advanced_search.bulk_operations_dialog_title')}")
    dialog.geometry("1000x750")
    dialog.transient(self.master)
    dialog.grab_set()

    frame = ttk.Frame(dialog, padding="20")
    frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(frame, text=_t("advanced_search.bulk_operations.title_with_count", count=len(self.search_results)),
             style='Title.TLabel').pack(pady=(0, 20))

    # Operation buttons
    operations = [
        (f"💾 {_t('advanced_search.bulk_operations.export_selected_students')}", self.bulk_export),
        (f"📧 {_t('advanced_search.bulk_operations.generate_email_list')}", self.generate_email_list),
        (f"👥 {_t('advanced_search.bulk_operations.create_student_groups')}", self.create_student_groups),
        (f"📌 {_t('advanced_search.bulk_operations.mark_for_followup')}", self.mark_for_followup),
        (f"🎓 {_t('advanced_search.bulk_operations.bulk_enrollment_management')}", self.bulk_enrollment_management),
    ]

    for text, command in operations:
        ttk.Button(frame, text=text, command=command, width=30).pack(pady=5)

    ttk.Button(frame, text=f"❌ {_t('advanced_search.close_button')}", command=dialog.destroy).pack(pady=(20, 0))
