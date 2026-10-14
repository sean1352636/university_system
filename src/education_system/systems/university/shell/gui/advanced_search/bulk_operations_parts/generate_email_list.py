"""Extracted function implementation."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import bulk_operations_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def generate_email_list(self):
    """Generate email list from search results"""
    if not self.search_results:
        messagebox.showwarning(_t("advanced_search.bulk_operations.no_results_title"), _t("advanced_search.bulk_operations.no_results_available"))
        return

    emails = [student[1] for student in self.search_results if student[1]]

    if not emails:
        messagebox.showwarning(_t("advanced_search.bulk_operations.no_emails_title"), _t("advanced_search.bulk_operations.no_emails_found"))
        return

    dialog = tk.Toplevel(self.master)
    dialog.title(f"📧 {_t('advanced_search.email_list_dialog_title')}")
    dialog.geometry("900x700")
    dialog.transient(self.master)
    dialog.grab_set()

    frame = ttk.Frame(dialog, padding="20")
    frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(frame, text=_t("advanced_search.bulk_operations.email_list_title", count=len(emails)),
             style='Title.TLabel').pack(pady=(0, 20))

    # Email list display
    email_text = scrolledtext.ScrolledText(frame, height=15, wrap=tk.WORD)
    email_text.pack(fill=tk.BOTH, expand=True, pady=(0, 20))

    # Format options
    format_frame = ttk.LabelFrame(frame, text=_t("advanced_search.bulk_operations.format_options"), padding="10")
    format_frame.pack(fill=tk.X, pady=(0, 20))

    format_var = tk.StringVar(value=_t('gui.shell.advanced_search.bulk_operations_parts.generate_email_list.values.list', default="list"))
    ttk.Radiobutton(format_frame, text=_t("advanced_search.bulk_operations.one_per_line"), variable=format_var, value="list").pack(anchor='w')
    ttk.Radiobutton(format_frame, text=_t("advanced_search.bulk_operations.comma_separated"), variable=format_var, value="comma").pack(anchor='w')
    ttk.Radiobutton(format_frame, text=_t("advanced_search.bulk_operations.semicolon_separated"), variable=format_var, value="semicolon").pack(anchor='w')

    def update_format():
        email_text.delete(1.0, tk.END)
        format_type = format_var.get()

        if format_type == "list":
            email_text.insert(tk.END, "\n".join(emails))
        elif format_type == "comma":
            email_text.insert(tk.END, ", ".join(emails))
        elif format_type == "semicolon":
            email_text.insert(tk.END, "; ".join(emails))

    for widget in format_frame.winfo_children():
        if isinstance(widget, ttk.Radiobutton):
            widget.configure(command=update_format)

    update_format()  # Initial format

    def save_email_list():
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"email_list_{timestamp}.txt"

        with open(filename, 'w', encoding='utf-8') as f:
            f.write(email_text.get(1.0, tk.END))

        messagebox.showinfo(_t("advanced_search.bulk_operations.email_list_saved_title"), _t("advanced_search.bulk_operations.email_list_saved_msg", filename=filename))
        dialog.destroy()

    button_frame = ttk.Frame(frame)
    button_frame.pack(fill=tk.X)

    ttk.Button(button_frame, text=f"💾 {_t('advanced_search.bulk_operations.save_list')}", command=save_email_list).pack(side=tk.LEFT)
    ttk.Button(button_frame, text=f"📋 {_t('advanced_search.bulk_operations.copy_btn')}",
              command=lambda: self.master.clipboard_clear() or
                             self.master.clipboard_append(email_text.get(1.0, tk.END))).pack(side=tk.LEFT, padx=(10, 0))
    ttk.Button(button_frame, text=f"❌ {_t('advanced_search.close_button')}", command=dialog.destroy).pack(side=tk.RIGHT)
