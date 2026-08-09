"""Methods analyze_whatif through load_appointments."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import degree_audit_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class DegreeAuditGUI:
    def analyze_whatif(self):
        """Analyze what-if scenario for course switching"""
        try:
            student_id = self._whatif_student_id()
            course_selection = self.whatif_program_combo.get()

            if not student_id or not course_selection:
                messagebox.showwarning(_("common.warning"), _t('gui.academics.course_management_gui.degree_audit_gui_parts.degreeauditgui_analyze_whatif.dialogs.please_select_a_student_and_target_course', default="Please select a student and target course"))
                return

            # Extract target course code
            target_course = course_selection.split(':')[1].split('-')[0].strip()

            with get_connection() as conn:
                cursor = conn.cursor()

                # Get student's current course and modules
                cursor.execute('SELECT course FROM students WHERE student_id = ?', (student_id,))
                student_data = cursor.fetchone()
                if not student_data:
                    messagebox.showerror(_("common.error"), f"Student {student_id} not found")
                    return

                current_course = student_data[0]

                # Get current modules and credits
                cursor.execute('''
                    SELECT COUNT(DISTINCT sm.module_code) as module_count,
                           SUM(COALESCE(m.credits, 0)) as total_credits
                    FROM student_modules sm
                    LEFT JOIN modules m ON sm.module_code = m.module_code
                    WHERE sm.student_id = ?
                ''', (student_id,))

                current_progress = cursor.fetchone()
                current_modules = current_progress[0] or 0
                current_credits = current_progress[1] or 0

                # Get modules of the target course type
                cursor.execute('''
                    SELECT COUNT(*) as available_modules
                    FROM modules
                    WHERE module_type = ? AND is_active = 1
                ''', (target_course,))

                target_modules = cursor.fetchone()[0] or 0

                # Calculate overlap - modules that match target course
                cursor.execute('''
                    SELECT COUNT(*) as matching_modules
                    FROM student_modules sm
                    JOIN modules m ON sm.module_code = m.module_code
                    WHERE sm.student_id = ? AND m.module_type = ?
                ''', (student_id, target_course))

                matching_modules = cursor.fetchone()[0] or 0

            # Calculate analysis
            standard_required = 40  # Typical number of modules for a degree
            completion_pct = (matching_modules / standard_required * 100) if standard_required > 0 else 0
            additional_needed = max(0, standard_required - matching_modules)

            self.whatif_results_text.delete('1.0', tk.END)
            self.whatif_results_text.insert(tk.END, "WHAT-IF SCENARIO ANALYSIS\n")
            self.whatif_results_text.insert(tk.END, "=" * 60 + "\n\n")
            self.whatif_results_text.insert(tk.END, f"Student ID: {student_id}\n")
            self.whatif_results_text.insert(tk.END, f"Current Course: {current_course}\n")
            self.whatif_results_text.insert(tk.END, f"Target Course: {target_course}\n\n")
            self.whatif_results_text.insert(tk.END, f"Current Modules Completed: {current_modules}\n")
            self.whatif_results_text.insert(tk.END, f"Current Credits Earned: {current_credits}\n\n")
            self.whatif_results_text.insert(tk.END, f"Modules Matching Target Course: {matching_modules}\n")
            self.whatif_results_text.insert(tk.END, f"Available {target_course} Modules: {target_modules}\n")
            self.whatif_results_text.insert(tk.END, f"Additional Modules Needed: {additional_needed}\n")
            self.whatif_results_text.insert(tk.END, f"Completion Percentage: {completion_pct:.1f}%\n\n")

            if completion_pct >= 50:
                self.whatif_results_text.insert(tk.END,
                    "RECOMMENDATION: Feasible\n\n"
                    f"You have completed over half of the requirements for {target_course}. "
                    "Switching courses is feasible with manageable additional coursework.")
            elif completion_pct >= 25:
                self.whatif_results_text.insert(tk.END,
                    "RECOMMENDATION: Moderate Effort Required\n\n"
                    f"You have completed {completion_pct:.1f}% of requirements for {target_course}. "
                    "Switching is possible but will require significant additional coursework.")
            else:
                self.whatif_results_text.insert(tk.END,
                    "RECOMMENDATION: Consider Carefully\n\n"
                    f"You have completed only {completion_pct:.1f}% of requirements for {target_course}. "
                    "Switching courses would require substantial additional coursework.")

        except Exception as e:
            messagebox.showerror(_("common.error"), f"Failed to analyze scenario: {e}")

    def _lookup_student_for_appointment(self, entry_widget):
        """Lookup student from database for appointments"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("degree_audit.dialogs.student_lookup_title"))
        dialog.geometry("700x400")
        dialog.transient(self.root)

        ttk.Label(dialog, text=_("degree_audit.labels.search")).pack(pady=5)
        search_entry = ttk.Entry(dialog, width=40)
        search_entry.pack(pady=5)

        tree_frame = ttk.Frame(dialog)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        columns = ('Student ID', 'Name', 'Course')
        tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=10)
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=200)

        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        def search_students():
            tree.delete(*tree.get_children())
            search_text = search_entry.get().strip()

            with get_connection() as conn:
                cursor = conn.cursor()
                if search_text:
                    cursor.execute('''
                        SELECT student_id, first_name || ' ' || last_name, course
                        FROM students
                        WHERE student_id LIKE ? OR first_name LIKE ? OR last_name LIKE ?
                        ORDER BY student_id
                        LIMIT 50
                    ''', (f'%{search_text}%', f'%{search_text}%', f'%{search_text}%'))
                else:
                    cursor.execute('''
                        SELECT student_id, first_name || ' ' || last_name, course
                        FROM students
                        ORDER BY student_id
                        LIMIT 50
                    ''')

                results = cursor.fetchall()
                for row in results:
                    # Convert Row object to tuple
                    student_id = row[0]
                    name = row[1]
                    course = row[2] if row[2] else 'N/A'
                    tree.insert('', tk.END, values=(student_id, name, course))

        def select_student():
            selection = tree.selection()
            if selection:
                item = tree.item(selection[0])
                student_id = item['values'][0]
                entry_widget.delete(0, tk.END)
                entry_widget.insert(0, student_id)
                dialog.destroy()

        search_entry.bind('<Return>', lambda e: search_students())
        ttk.Button(dialog, text=_("degree_audit.buttons.search"), command=search_students).pack(pady=5)
        ttk.Button(dialog, text=_("degree_audit.buttons.select"), command=select_student).pack(pady=5)

        search_students()  # Load initial data

    def _lookup_advisor_for_appointment(self, entry_widget):
        """Lookup advisor/instructor from database for appointments"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("degree_audit.dialogs.advisor_lookup_title"))
        dialog.geometry("700x400")
        dialog.transient(self.root)

        ttk.Label(dialog, text=_("degree_audit.labels.search")).pack(pady=5)
        search_entry = ttk.Entry(dialog, width=40)
        search_entry.pack(pady=5)

        tree_frame = ttk.Frame(dialog)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        columns = ('ID', 'Name', 'Department')
        tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=10)
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=200)

        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        def search_advisors():
            tree.delete(*tree.get_children())
            search_text = search_entry.get().strip()

            with get_connection() as conn:
                cursor = conn.cursor()
                if search_text:
                    cursor.execute('''
                        SELECT id, first_name || ' ' || last_name, department
                        FROM instructors
                        WHERE id LIKE ? OR first_name LIKE ? OR last_name LIKE ?
                        ORDER BY last_name
                        LIMIT 50
                    ''', (f'%{search_text}%', f'%{search_text}%', f'%{search_text}%'))
                else:
                    cursor.execute('''
                        SELECT id, first_name || ' ' || last_name, department
                        FROM instructors
                        ORDER BY last_name
                        LIMIT 50
                    ''')

                results = cursor.fetchall()
                for row in results:
                    # Convert Row object to tuple
                    advisor_id = row[0]
                    name = row[1]
                    department = row[2] if row[2] else 'N/A'
                    tree.insert('', tk.END, values=(advisor_id, name, department))

        def select_advisor():
            selection = tree.selection()
            if selection:
                item = tree.item(selection[0])
                advisor_id = item['values'][0]
                entry_widget.delete(0, tk.END)
                entry_widget.insert(0, advisor_id)
                dialog.destroy()

        search_entry.bind('<Return>', lambda e: search_advisors())
        ttk.Button(dialog, text=_("degree_audit.buttons.search"), command=search_advisors).pack(pady=5)
        ttk.Button(dialog, text=_("degree_audit.buttons.select"), command=select_advisor).pack(pady=5)

        search_advisors()  # Load initial data

    def schedule_appointment(self):
        """Schedule an advising appointment"""
        try:
            fields = self.appointment_fields

            student_id = fields['student'].get().strip()
            advisor_id = fields['advisor'].get().strip()
            date = fields['date'].get().strip()
            time = fields['time'].get().strip()
            appt_type = fields['type'].get()
            duration = int(fields['duration'].get())
            topic = fields['topic'].get().strip()
            notes = fields['notes'].get('1.0', tk.END).strip()

            if not all([student_id, advisor_id, date, time]):
                messagebox.showwarning(_("common.warning"), _("degree_audit.messages.appointment_fields_required"))
                return

            # Validate student exists
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT student_id FROM students WHERE student_id = ?', (student_id,))
                if not cursor.fetchone():
                    messagebox.showerror(_("common.error"), _("degree_audit.messages.student_not_found_db").format(student_id=student_id))
                    return

                cursor.execute('SELECT id FROM instructors WHERE id = ?', (advisor_id,))
                if not cursor.fetchone():
                    messagebox.showerror(_("common.error"), _("degree_audit.messages.advisor_not_found_db").format(advisor_id=advisor_id))
                    return

            appointment_id = AdvisingAppointmentManager.schedule_appointment(
                student_id=student_id,
                advisor_id=advisor_id,
                appointment_date=date,
                appointment_time=time,
                appointment_type=appt_type,
                duration_minutes=duration,
                topic=topic,
                notes=notes
            )

            log_activity('create', 'advising_appointment', str(appointment_id),
                       {'student_id': student_id, 'date': date})

            messagebox.showinfo(_("common.success"), _("degree_audit.messages.appointment_scheduled_success").format(appointment_id=appointment_id))

            # Clear fields now that the appointment is safely stored.
            fields['student'].delete(0, tk.END)
            fields['advisor'].delete(0, tk.END)
            fields['topic'].delete(0, tk.END)
            fields['notes'].delete('1.0', tk.END)

            # Send confirmation emails to student and advisor using the JSON
            # templates at templates/email/academics/advising/.
            #
            # This runs on a background thread: the first send_email() call in
            # a session performs one-off email-DB initialisation that can take
            # several seconds, and doing that on the Tk main thread froze the
            # whole GUI (blank, "not responding" window that the desktop then
            # killed). The appointment is already saved, so email delivery is
            # best-effort and must never block or crash the UI. The worker
            # touches no Tk widgets; any user-facing result is marshalled back
            # to the main thread via ``self.root.after``.
            self._dispatch_appointment_emails(
                student_id=student_id, advisor_id=advisor_id,
                date=date, time=time, duration=duration,
                appointment_type=appt_type, topic=topic, notes=notes,
            )

        except Exception as e:
            messagebox.showerror(_("common.error"), f"Failed to schedule appointment: {e}")

    def _dispatch_appointment_emails(self, **kwargs):
        """Send appointment confirmation emails without blocking the GUI.

        Runs :meth:`_send_appointment_emails` on a daemon thread so the Tk
        event loop stays responsive even during the slow first-call email-DB
        initialisation. Failures are logged and surfaced non-modally; they
        never propagate into the UI thread.
        """
        root = getattr(self, "root", None)

        def _notify_failure(err):
            messagebox.showwarning(
                _("common.warning"),
                "The appointment was saved, but the confirmation email could "
                f"not be sent:\n{err}",
            )

        def _worker():
            try:
                self._send_appointment_emails(**kwargs)
            except Exception as email_err:  # noqa: BLE001 - best-effort delivery
                print(f"Appointment email notification failed: {email_err}")
                if root is not None:
                    try:
                        root.after(0, lambda err=email_err: _notify_failure(err))
                    except Exception:
                        pass

        threading.Thread(target=_worker, name="advising-email", daemon=True).start()

    def load_appointments(self):
        """Load advising appointments for current user"""
        try:
            student_id = self.auth.current_user.get('username') if self.auth.current_user else None
            if not student_id:
                messagebox.showwarning(_("common.warning"), _("degree_audit.messages.no_user_logged_in"))
                return

            self.appointments_tree.delete(*self.appointments_tree.get_children())

            appointments = AdvisingAppointmentManager.get_student_appointments(student_id)

            for appt in appointments:
                self.appointments_tree.insert('', tk.END, values=(
                    appt.get('appointment_id', ''),
                    appt.get('student_id', ''),
                    appt.get('advisor_id', ''),
                    appt.get('appointment_date', ''),
                    appt.get('appointment_time', ''),
                    appt.get('appointment_type', ''),
                    appt.get('topic', ''),
                    appt.get('status', '')
                ))

        except Exception as e:
            messagebox.showerror(_("common.error"), _("degree_audit.messages.failed_load_appointments").format(error=e))
