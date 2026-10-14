"""Extracted function implementation."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import bulk_operations_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def bulk_enrollment_management(self):
    """Manage bulk enrollment operations"""
    if not self.search_results:
        messagebox.showwarning(_t("advanced_search.bulk_operations.no_results_title"), _t("advanced_search.bulk_operations.no_results_available"))
        return

    dialog = tk.Toplevel(self.master)
    dialog.title(f"🎓 {_t('advanced_search.bulk_enrollment_dialog_title')}")
    dialog.geometry("1000x800")
    dialog.transient(self.master)
    dialog.grab_set()

    frame = ttk.Frame(dialog, padding="20")
    frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(frame, text=_t("advanced_search.bulk_operations.bulk_enrollment_title", count=len(self.search_results)),
             style='Title.TLabel').pack(pady=(0, 20))

    # Operation selection
    ttk.Label(frame, text=_t("advanced_search.bulk_operations.operation_label")).pack(anchor='w')
    operation_var = tk.StringVar(value=_t('gui.shell.advanced_search.bulk_operations_parts.bulk_enrollment_management.values.enroll', default="enroll"))

    operations = [
        (_t("advanced_search.bulk_operations.enroll_in_module"), "enroll"),
        (_t("advanced_search.bulk_operations.unenroll_from_module"), "unenroll"),
        (_t("advanced_search.bulk_operations.transfer_between_modules"), "transfer"),
        (_t("advanced_search.bulk_operations.update_enrollment_status"), "status"),
    ]

    for text, value in operations:
        ttk.Radiobutton(frame, text=text, variable=operation_var, value=value).pack(anchor='w')

    # Module inputs
    module_frame = ttk.LabelFrame(frame, text=_t("advanced_search.bulk_operations.module_information"), padding="10")
    module_frame.pack(fill=tk.X, pady=(20, 0))

    ttk.Label(module_frame, text=_t("advanced_search.bulk_operations.module_code_label")).pack(anchor='w')
    module_var = tk.StringVar()
    ttk.Entry(module_frame, textvariable=module_var, width=20).pack(anchor='w', pady=(0, 10))

    ttk.Label(module_frame, text=_t("advanced_search.bulk_operations.to_module_label")).pack(anchor='w')
    to_module_var = tk.StringVar()
    ttk.Entry(module_frame, textvariable=to_module_var, width=20).pack(anchor='w')

    def execute_bulk_operation():
        operation = operation_var.get()
        module_code = module_var.get().strip()

        if not module_code and operation != "status":
            messagebox.showwarning(_t("advanced_search.bulk_operations.missing_module_title"), _t("advanced_search.bulk_operations.missing_module_msg"))
            return

        # Simulate the operation
        if operation == "enroll":
            message = _t("advanced_search.bulk_operations.enrolled_msg", count=len(self.search_results), module=module_code)
        elif operation == "unenroll":
            message = _t("advanced_search.bulk_operations.unenrolled_msg", count=len(self.search_results), module=module_code)
        elif operation == "transfer":
            to_module = to_module_var.get().strip()
            if not to_module:
                messagebox.showwarning(_t("advanced_search.bulk_operations.missing_target_title"), _t("advanced_search.bulk_operations.missing_target_msg"))
                return
            message = _t("advanced_search.bulk_operations.transferred_msg", count=len(self.search_results), from_module=module_code, to_module=to_module)
        else:
            message = _t("advanced_search.bulk_operations.status_updated_msg", count=len(self.search_results))

        messagebox.showinfo(_t("advanced_search.bulk_operations.operation_complete_title"), message)
        dialog.destroy()

    button_frame = ttk.Frame(frame)
    button_frame.pack(fill=tk.X, pady=(20, 0))

    ttk.Button(button_frame, text=f"🎓 {_t('advanced_search.bulk_operations.execute_btn')}", command=execute_bulk_operation).pack(side=tk.LEFT)
    ttk.Button(button_frame, text=f"❌ {_t('advanced_search.cancel_button')}", command=dialog.destroy).pack(side=tk.RIGHT)
