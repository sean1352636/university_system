"""Extracted function implementation."""

from .. import bulk_operations_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def show_mass_email(self):
    """Show mass email interface"""
    if not self.search_results:
        messagebox.showwarning(_t("advanced_search.bulk_operations.no_results_title"), _t("advanced_search.bulk_operations.search_first_msg"))
        return

    dialog = tk.Toplevel(self.master)
    dialog.title(f"📧 {_t('advanced_search.mass_email_dialog_title')}")
    dialog.geometry("1000x800")
    dialog.transient(self.master)
    dialog.grab_set()

    frame = ttk.Frame(dialog, padding="20")
    frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(frame, text=_t("advanced_search.bulk_operations.mass_email_title", count=len(self.search_results)),
             style='Title.TLabel').pack(pady=(0, 20))

    # Email composition
    ttk.Label(frame, text=_t("advanced_search.bulk_operations.subject_label")).pack(anchor='w')
    subject_var = tk.StringVar()
    ttk.Entry(frame, textvariable=subject_var, width=60).pack(fill=tk.X, pady=(0, 10))

    ttk.Label(frame, text=_t("advanced_search.bulk_operations.message_label")).pack(anchor='w')
    message_text = scrolledtext.ScrolledText(frame, height=15, wrap=tk.WORD)
    message_text.pack(fill=tk.BOTH, expand=True, pady=(0, 20))

    # Email template buttons
    template_frame = ttk.Frame(frame)
    template_frame.pack(fill=tk.X, pady=(0, 20))

    def load_template(template_type):
        template_map = {
            "welcome": "welcome_message",
            "reminder": "reminder_message",
            "announcement": "announcement_message"
        }

        if template_type in template_map:
            try:
                from education_system.systems.university.infrastructure.email.template_utils import render_template
                subject, message = render_template(template_map[template_type], {})
                subject_var.set(subject)
                message_text.delete(1.0, tk.END)
                message_text.insert(1.0, message)
            except Exception:

                pass

    ttk.Label(template_frame, text=_t("advanced_search.bulk_operations.quick_templates")).pack(side=tk.LEFT)
    ttk.Button(template_frame, text=_t("advanced_search.bulk_operations.template_welcome"),
              command=lambda: load_template("welcome")).pack(side=tk.LEFT, padx=(10, 5))
    ttk.Button(template_frame, text=_t("advanced_search.bulk_operations.template_reminder"),
              command=lambda: load_template("reminder")).pack(side=tk.LEFT, padx=(0, 5))
    ttk.Button(template_frame, text=_t("advanced_search.bulk_operations.template_announcement"),
              command=lambda: load_template("announcement")).pack(side=tk.LEFT)

    # Send mass email function
    def send_mass_email():
        subject = subject_var.get().strip()
        message = message_text.get(1.0, tk.END).strip()

        if not subject or not message:
            messagebox.showwarning(_t("advanced_search.bulk_operations.incomplete_title"), _t("advanced_search.bulk_operations.enter_subject_and_message"))
            return

        # Get valid email recipients
        recipients = [s[1] for s in self.search_results if s[1] and '@' in s[1]]

        if not recipients:
            messagebox.showwarning(_t("advanced_search.bulk_operations.no_recipients_title"), _t("advanced_search.bulk_operations.no_valid_emails"))
            return

        # Show confirmation
        confirmation = _t("advanced_search.bulk_operations.confirm_send_msg",
                          subject=subject, count=len(recipients), length=len(message),
                          preview=', '.join(recipients[:5]) + ('...' if len(recipients) > 5 else ''))

        if messagebox.askyesno(_t("advanced_search.bulk_operations.confirm_send_title"), confirmation):
            try:
                from education_system.systems.university.infrastructure.email.email_service import send_email

                # Send emails to all recipients
                success_count = 0
                failed_count = 0
                failed_addresses = []

                for recipient_email in recipients:
                    try:
                        result = send_email(
                            recipient_email=recipient_email,
                            subject=subject,
                            body=message
                        )
                        if result is not False:
                            success_count += 1
                        else:
                            failed_count += 1
                            failed_addresses.append(recipient_email)
                    except Exception as e:
                        failed_count += 1
                        failed_addresses.append(recipient_email)
                        print_error(f"Failed to send to {recipient_email}: {str(e)}")

                # Show results
                result_message = _t("advanced_search.bulk_operations.mass_email_results_msg",
                                    success=success_count, failed=failed_count,
                                    failed_list=chr(10).join(failed_addresses[:10]),
                                    extra=len(failed_addresses)-10 if len(failed_addresses) > 10 else 0)

                messagebox.showinfo(_t("advanced_search.bulk_operations.email_sent_title"), result_message)
                dialog.destroy()

            except Exception as e:
                messagebox.showerror(_t("advanced_search.bulk_operations.email_error_title"),
                                   _t("advanced_search.bulk_operations.email_error_msg", error=str(e)))
                print(f"Mass email error: {str(e)}")

    button_frame = ttk.Frame(frame)
    button_frame.pack(fill=tk.X)

    ttk.Button(button_frame, text=f"📧 {_t('advanced_search.bulk_operations.send_email_btn')}", command=send_mass_email).pack(side=tk.LEFT)
    ttk.Button(button_frame, text=f"💾 {_t('advanced_search.bulk_operations.save_draft_btn')}",
              command=lambda: messagebox.showinfo(_t("advanced_search.bulk_operations.draft_title"), _t("advanced_search.bulk_operations.draft_saved_msg"))).pack(side=tk.LEFT, padx=(10, 0))
    ttk.Button(button_frame, text=f"❌ {_t('advanced_search.cancel_button')}", command=dialog.destroy).pack(side=tk.RIGHT)
