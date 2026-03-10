"""Hearing scheduling for the Academic Misconduct Panel."""

from ._imports import (
    tk, ttk, messagebox, _t, datetime, timedelta,
    EMAIL_AVAILABLE, queue_email,
)


class MisconductHearingsMixin:
    """Mixin providing hearing scheduling functionality."""

    def schedule_hearing(self):
        """Schedule a hearing for the case with calendar selection."""
        if not self.selected_case:
            messagebox.showwarning(_t("misconduct.msg_titles.no_selection"), "Please select a case first.")
            return

        # Create scheduling dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Schedule Hearing")
        dialog.geometry("500x600")
        dialog.configure(bg=self.colors['light'])
        dialog.transient(self.root)
        dialog.grab_set()

        content = tk.Frame(dialog, bg=self.colors['light'])
        content.pack(fill=tk.BOTH, expand=True, padx=30, pady=30)

        tk.Label(
            content,
            text=_t("misconduct.btn.schedule_hearing"),
            font=('Segoe UI', 16, 'bold'),
            fg=self.colors['text_dark'],
            bg=self.colors['light']
        ).pack(anchor='w', pady=(0, 20))

        tk.Label(content, text=f"Case: {self.selected_case['id']} - {self.selected_case['student']}",
                 font=('Segoe UI', 10), fg=self.colors['text_muted'], bg=self.colors['light']).pack(anchor='w', pady=(0, 20))

        # Date selection
        tk.Label(content, text=_t("misconduct.labels.hearing_date"), font=('Segoe UI', 10),
                 fg=self.colors['text_muted'], bg=self.colors['light']).pack(anchor='w', pady=(0, 5))

        date_frame = tk.Frame(content, bg=self.colors['light'])
        date_frame.pack(fill=tk.X, pady=(0, 15))

        # Simple date entry (YYYY-MM-DD format)
        date_entry = tk.Entry(date_frame, font=('Segoe UI', 11), bg=self.colors['light'],
                              fg=self.colors['text_dark'], insertbackground=self.colors['text_dark'],
                              relief='flat', width=15)
        date_entry.pack(side=tk.LEFT, ipady=8)
        date_entry.insert(0, (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d'))

        tk.Label(date_frame, text=_t("misconduct.labels.date_format"), font=('Segoe UI', 9),
                 fg=self.colors['text_muted'], bg=self.colors['light']).pack(side=tk.LEFT)

        # Quick date buttons
        quick_frame = tk.Frame(content, bg=self.colors['light'])
        quick_frame.pack(fill=tk.X, pady=(0, 15))

        for days, label in [(7, "1 Week"), (14, "2 Weeks"), (21, "3 Weeks")]:
            future_date = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d')
            btn = tk.Button(quick_frame, text=label, font=('Segoe UI', 9),
                           bg=self.colors['white'], fg=self.colors['text_muted'],
                           relief='flat', padx=10, pady=5,
                           command=lambda d=future_date: (date_entry.delete(0, tk.END), date_entry.insert(0, d)))
            btn.pack(side=tk.LEFT, padx=(0, 10))

        # Time selection
        tk.Label(content, text=_t("misconduct.labels.hearing_time"), font=('Segoe UI', 10),
                 fg=self.colors['text_muted'], bg=self.colors['light']).pack(anchor='w', pady=(0, 5))

        time_frame = tk.Frame(content, bg=self.colors['light'])
        time_frame.pack(fill=tk.X, pady=(0, 15))

        time_var = tk.StringVar(value="10:00 AM")
        times = ["9:00 AM", "10:00 AM", "11:00 AM", "1:00 PM", "2:00 PM", "3:00 PM", "4:00 PM"]
        time_combo = ttk.Combobox(time_frame, textvariable=time_var, values=times,
                                   font=('Segoe UI', 11), state='readonly', width=12)
        time_combo.pack(side=tk.LEFT)

        # Location
        tk.Label(content, text=_t("misconduct.labels.location"), font=('Segoe UI', 10),
                 fg=self.colors['text_muted'], bg=self.colors['light']).pack(anchor='w', pady=(0, 5))

        location_entry = tk.Entry(content, font=('Segoe UI', 11), bg=self.colors['light'],
                                  fg=self.colors['text_dark'], insertbackground=self.colors['text_dark'], relief='flat')
        location_entry.pack(fill=tk.X, ipady=8)
        location_entry.insert(0, "Academic Integrity Office, Room 201")

        # Student email for notification
        tk.Label(content, text=_t("misconduct.labels.student_email_notification"), font=('Segoe UI', 10),
                 fg=self.colors['text_muted'], bg=self.colors['light']).pack(anchor='w', pady=(15, 5))

        email_entry = tk.Entry(content, font=('Segoe UI', 11), bg=self.colors['light'],
                               fg=self.colors['text_dark'], insertbackground=self.colors['text_dark'], relief='flat')
        email_entry.pack(fill=tk.X, ipady=8)
        email_entry.insert(0, self.selected_case.get('student_email', ''))

        # Send notification checkbox
        send_email_var = tk.BooleanVar(value=True)
        tk.Checkbutton(content, text=_t("misconduct.labels.send_email_notification"), variable=send_email_var,
                       font=('Segoe UI', 10), fg=self.colors['text_muted'], bg=self.colors['light'],
                       selectcolor=self.colors['light'], activebackground=self.colors['light']).pack(anchor='w', pady=(15, 0))

        def schedule():
            hearing_date = date_entry.get().strip()
            hearing_time = time_var.get()
            location = location_entry.get().strip()
            email = email_entry.get().strip()

            if not hearing_date or not hearing_time or not location:
                messagebox.showwarning(_t("misconduct.msg_titles.missing_info"), "Please fill in all fields.")
                return

            # Update case
            self.selected_case['hearing_date'] = hearing_date
            self.selected_case['hearing_time'] = hearing_time
            self.selected_case['hearing_location'] = location
            self.selected_case['status'] = 'Pending Hearing'
            self.selected_case['student_email'] = email

            if self.update_case_in_db(self.selected_case):
                self.add_case_history(self.selected_case['id'],
                                      f"Hearing scheduled for {hearing_date} at {hearing_time} in {location}", 'info')

                # Reload cases and update tree
                self.load_cases_from_db()
                self.populate_tree()

                # Send email notification if requested
                if send_email_var.get() and email and EMAIL_AVAILABLE and queue_email:
                    try:
                        from education_system.university_system.infrastructure.email.template_utils import render_template

                        subject, body = render_template('academics/misconduct_hearing_scheduled', {
                            'student_name': self.selected_case['student'],
                            'case_id': self.selected_case['id'],
                            'hearing_date': hearing_date,
                            'hearing_time': hearing_time,
                            'location': location
                        })

                        # Fallback if template not found
                        if not subject or not body:
                            subject = f"Academic Integrity Hearing Scheduled - Case {self.selected_case['id']}"
                            body = f"Dear {self.selected_case['student']},\n\nA hearing has been scheduled for case {self.selected_case['id']}.\n\nDate: {hearing_date}\nTime: {hearing_time}\nLocation: {location}\n\nSincerely,\nOffice of Academic Integrity"
                    except Exception as e:
                        print(f"Error rendering email template: {e}")
                        subject = f"Academic Integrity Hearing Scheduled - Case {self.selected_case['id']}"
                        body = f"Dear {self.selected_case['student']},\n\nA hearing has been scheduled for case {self.selected_case['id']}.\n\nDate: {hearing_date}\nTime: {hearing_time}\nLocation: {location}\n\nSincerely,\nOffice of Academic Integrity"

                    try:
                        if queue_email(email, subject, body):
                            self.add_case_history(self.selected_case['id'],
                                                  f"Hearing notification sent to {email}", 'warning')
                            messagebox.showinfo(_t("misconduct.msg_titles.success"), f"Hearing scheduled and notification sent to {email}")
                        else:
                            messagebox.showinfo(_t("misconduct.msg_titles.partial_success"), "Hearing scheduled, but email notification failed.")
                    except Exception as e:
                        messagebox.showinfo(_t("misconduct.msg_titles.partial_success"), f"Hearing scheduled, but email failed: {str(e)}")
                else:
                    messagebox.showinfo(_t("misconduct.msg_titles.success"), "Hearing scheduled successfully.")

                dialog.destroy()
                self.create_overview_fields()
            else:
                messagebox.showerror(_t("misconduct.msg_titles.error"), "Failed to save hearing details.")

        # Buttons
        btn_frame = tk.Frame(content, bg=self.colors['light'])
        btn_frame.pack(fill=tk.X, pady=(30, 0))

        self.create_button(btn_frame, "Cancel", dialog.destroy, 'secondary').pack(side=tk.RIGHT, padx=(10, 0))
        self.create_button(btn_frame, "📅 Schedule Hearing", schedule, 'primary').pack(side=tk.RIGHT)
