"""Extracted function implementation."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import bulk_operations_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def show_batch_updates(self):
    """Show batch data updates interface"""
    if not self.search_results:
        messagebox.showwarning(_t("advanced_search.bulk_operations.no_results_title"), _t("advanced_search.bulk_operations.search_first_msg"))
        return

    dialog = tk.Toplevel(self.master)
    dialog.title(f"📝 {_t('advanced_search.batch_updates_dialog_title')}")
    dialog.geometry("1000x750")
    dialog.transient(self.master)
    dialog.grab_set()

    frame = ttk.Frame(dialog, padding="20")
    frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(frame, text=_t("advanced_search.bulk_operations.batch_updates_label", count=len(self.search_results)),
             style='Title.TLabel').pack(pady=(0, 20))

    # Update operations
    operations = [
        (_t("advanced_search.bulk_operations.update_course"), "course"),
        (_t("advanced_search.bulk_operations.update_registration_status"), "status"),
        (_t("advanced_search.bulk_operations.add_note_flag"), "note"),
        (_t("advanced_search.bulk_operations.update_contact_information"), "contact"),
    ]

    operation_var = tk.StringVar(value=_t('gui.shell.advanced_search.bulk_operations_parts.show_batch_updates.values.course', default="course"))

    for text, value in operations:
        ttk.Radiobutton(frame, text=text, variable=operation_var, value=value).pack(anchor='w', pady=2)

    # Update values frame
    values_frame = ttk.LabelFrame(frame, text=_t("advanced_search.bulk_operations.update_values"), padding="10")
    values_frame.pack(fill=tk.X, pady=(20, 0))

    ttk.Label(values_frame, text=_t("advanced_search.bulk_operations.new_value_label")).pack(anchor='w')
    new_value_var = tk.StringVar()
    ttk.Entry(values_frame, textvariable=new_value_var, width=30).pack(fill=tk.X, pady=(0, 10))

    ttk.Label(values_frame, text=_t("advanced_search.bulk_operations.reason_for_change")).pack(anchor='w')
    reason_text = tk.Text(values_frame, height=4, wrap=tk.WORD)
    reason_text.pack(fill=tk.X)

    def execute_batch_update():
        operation = operation_var.get()
        new_value = new_value_var.get().strip()
        reason = reason_text.get(1.0, tk.END).strip()

        if not new_value:
            messagebox.showwarning(_t("advanced_search.bulk_operations.missing_value_title"), _t("advanced_search.bulk_operations.please_enter_value"))
            return

        # Get operation text from operations list
        operation_text = next((text for text, value in operations if value == operation), operation)

        # Confirmation dialog
        confirmation = _t("advanced_search.bulk_operations.batch_update_confirmation",
                          operation=operation_text, new_value=new_value,
                          count=len(self.search_results),
                          reason=reason if reason else _t("advanced_search.bulk_operations.not_specified"))

        if messagebox.askyesno(_t("advanced_search.bulk_operations.confirm_update_title"), confirmation):
            messagebox.showinfo(_t("advanced_search.bulk_operations.update_complete_title"),
                              _t("advanced_search.bulk_operations.batch_update_complete_msg", count=len(self.search_results)))
            dialog.destroy()

    button_frame = ttk.Frame(frame)
    button_frame.pack(fill=tk.X, pady=(20, 0))

    ttk.Button(button_frame, text=f"📝 {_t('advanced_search.bulk_operations.update_btn')}", command=execute_batch_update).pack(side=tk.LEFT)
    ttk.Button(button_frame, text=f"❌ {_t('advanced_search.cancel_button')}", command=dialog.destroy).pack(side=tk.RIGHT)
