"""Extracted function implementation."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import bulk_operations_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def mass_email_students(self):
    """
    Send mass emails to students from search results (CLI-equivalent function).

    This function provides a comprehensive mass email interface with:
    - Recipient list display
    - Subject and message composition
    - Email simulation mode
    - Integration with email infrastructure if available
    """
    if not self.search_results:
        messagebox.showwarning(_t("advanced_search.bulk_operations.no_results_title"), _t("advanced_search.bulk_operations.no_results_for_mass_email"))
        return

    dialog = tk.Toplevel(self.master)
    dialog.title(f"📧 {_t('advanced_search.mass_email_dialog_title')}")
    dialog.geometry("1200x850")
    dialog.transient(self.master)
    dialog.grab_set()

    frame = ttk.Frame(dialog, padding="20")
    frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(frame, text=_t("advanced_search.bulk_operations.mass_email_title", count=len(self.search_results)),
             style='Title.TLabel').pack(pady=(0, 20))

    # Recipient summary
    recipient_frame = ttk.LabelFrame(frame, text=_t("advanced_search.bulk_operations.recipients_label"), padding="10")
    recipient_frame.pack(fill=tk.X, pady=(0, 10))

    recipient_text = scrolledtext.ScrolledText(recipient_frame, height=5, wrap=tk.WORD)
    recipient_text.pack(fill=tk.BOTH, expand=True)

    # Show first 10 recipients and total count
    for i, student in enumerate(self.search_results[:10]):
        name = f"{student[3]} {student[5]}"
        email = student[1]
        recipient_text.insert(tk.END, f"{i+1}. {name} ({email})\n")

    if len(self.search_results) > 10:
        recipient_text.insert(tk.END, _t("advanced_search.bulk_operations.and_more_recipients", count=len(self.search_results) - 10))

    recipient_text.config(state='disabled')

    # Email composition
    composition_frame = ttk.LabelFrame(frame, text=_t("advanced_search.bulk_operations.email_content"), padding="10")
    composition_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

    ttk.Label(composition_frame, text=_t("advanced_search.bulk_operations.subject_label")).pack(anchor='w')
    subject_var = tk.StringVar()
    ttk.Entry(composition_frame, textvariable=subject_var, width=60).pack(fill=tk.X, pady=(0, 10))

    ttk.Label(composition_frame, text=_t("advanced_search.bulk_operations.message_label")).pack(anchor='w')
    message_text = scrolledtext.ScrolledText(composition_frame, height=12, wrap=tk.WORD)
    message_text.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

    # Email mode selection
    mode_frame = ttk.Frame(composition_frame)
    mode_frame.pack(fill=tk.X, pady=(10, 0))

    mode_var = tk.StringVar(value=_t('gui.shell.advanced_search.bulk_operations_parts.mass_email_students.values.simulation', default="simulation"))
    ttk.Radiobutton(mode_frame, text=_t("advanced_search.bulk_operations.simulation_mode"),
                   variable=mode_var, value="simulation").pack(anchor='w')
    ttk.Radiobutton(mode_frame, text=_t("advanced_search.bulk_operations.real_email_mode"),
                   variable=mode_var, value="real").pack(anchor='w')

    def send_emails():
        subject = subject_var.get().strip()
        message = message_text.get(1.0, tk.END).strip()

        if not subject or not message:
            messagebox.showwarning(_t("advanced_search.bulk_operations.incomplete_title"), _t("advanced_search.bulk_operations.provide_subject_and_message"))
            return

        mode = mode_var.get()

        if mode == "simulation":
            # Simulation mode
            result_msg = _t("advanced_search.bulk_operations.simulation_complete_msg",
                           count=len(self.search_results), subject=subject, length=len(message))
            messagebox.showinfo(_t("advanced_search.bulk_operations.simulation_complete_title"), result_msg)
        else:
            # Real email mode
            try:
                # Try to use email infrastructure if available
                from education_system.systems.university.infrastructure.email.email_service import send_email

                success_count = 0
                failed_count = 0

                for student in self.search_results:
                    try:
                        send_email(
                            to_email=student[1],
                            subject=subject,
                            body=message
                        )
                        success_count += 1
                    except Exception:
                        failed_count += 1

                messagebox.showinfo(_t("advanced_search.bulk_operations.email_sent_title"),
                                  _t("advanced_search.bulk_operations.mass_email_completed_msg",
                                     success=success_count, failed=failed_count))

            except ImportError:
                messagebox.showwarning(_t("advanced_search.bulk_operations.email_not_configured_title"),
                                     _t("advanced_search.bulk_operations.email_not_configured_msg"))
                return

        dialog.destroy()

    button_frame = ttk.Frame(frame)
    button_frame.pack(fill=tk.X, pady=(20, 0))

    ttk.Button(button_frame, text=f"📧 {_t('advanced_search.bulk_operations.send_btn')}", command=send_emails).pack(side=tk.LEFT)
    ttk.Button(button_frame, text=f"❌ {_t('advanced_search.cancel_button')}", command=dialog.destroy).pack(side=tk.RIGHT)
