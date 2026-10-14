"""Methods analyze_whatif through load_appointments."""
import logging

logger = logging.getLogger(__name__)

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import degree_audit_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})

# Imported after the namespace splat so it cannot be shadowed.
from .. import report_widgets as _report


def _describe_email_result(sent):
    """Wording for the confirmation line after a delivery attempt."""
    ok = sent.get("sent") or []
    skipped = sent.get("skipped") or []
    parts = []
    if ok:
        parts.append("✓ Confirmation emailed to " + " and ".join(ok))
    if skipped:
        parts.append("no email address on file for " + " and ".join(skipped))
    return "; ".join(parts) if parts else "No confirmation emails were sent."


class DegreeAuditGUI:
    def analyze_whatif(self):
        """Analyse switching a student onto another course.

        Opens its own window: the analysis is something you read and act on,
        and it was previously buried in a fixed-height text box on the tab.
        """
        try:
            student_id = self._whatif_student_id()
            course_selection = self.whatif_program_combo.get()

            if not student_id or not course_selection:
                messagebox.showwarning(_("common.warning"), _t('gui.academics.course_management_gui.degree_audit_gui_parts.degreeauditgui_analyze_whatif.dialogs.please_select_a_student_and_target_course', default="Please select a student and target course"))
                return

            target_course = course_selection.split(':')[1].split('-')[0].strip()

            from education_system.systems.university.domains.academics.domain.services.degree_audit.progress import (
                earned_progress,
                module_progress,
                required_credits_for_course,
            )

            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'SELECT course, first_name, last_name FROM students WHERE student_id = ?',
                    (student_id,))
                student_data = cursor.fetchone()
                if not student_data:
                    messagebox.showerror(_("common.error"), f"Student {student_id} not found")
                    return
                current_course = student_data[0]
                student_name = (f"{student_data[1] or ''} {student_data[2] or ''}".strip()
                                or student_id)

                progress = earned_progress(conn, student_id)
                required_credits = required_credits_for_course(conn, target_course)

                # A programme's modules are the ones tagged with its code in
                # modules.course. This matched on module_type instead, which
                # holds 'Core' / 'Elective', so it always counted 0.
                cursor.execute(
                    "SELECT module_code, COALESCE(credits, 0) FROM modules WHERE course = ? "
                    "AND COALESCE(module_code, '') <> '' AND COALESCE(is_active, 1) = 1",
                    (target_course,))
                target_credits = {row[0]: row[1] for row in cursor.fetchall()}
                target_modules = len(target_credits)

                # Seeded modules record no credits; value them at the target
                # programme's share, not the student's current programme's.
                target_share = (round(required_credits / target_modules)
                                if required_credits and target_modules else 0)

                # Modules already taken that also belong to the target course.
                # Read through module_progress so a mark recorded in Grade
                # Tracking (module_grades) shows here, not 'Not graded'.
                carried, carried_credits = [], 0.0
                for r in module_progress(conn, student_id):
                    if r["module_code"] not in target_credits:
                        continue
                    carried.append((
                        r["module_code"], r["module_name"],
                        "Completed" if r["earned"] and r["status"].lower() == "enrolled"
                        else r["status"],
                        r["grade"]))
                    if r["earned"]:
                        carried_credits += target_credits[r["module_code"]] or target_share

            self._show_whatif_results(
                student_id=student_id, student_name=student_name,
                current_course=current_course, target_course=target_course,
                progress=progress, required_credits=required_credits,
                target_modules=target_modules, carried=carried,
                carried_credits=carried_credits)

        except Exception as e:
            messagebox.showerror(_("common.error"), f"Failed to analyze scenario: {e}")

    def _show_whatif_results(self, *, student_id, student_name, current_course,
                             target_course, progress, required_credits,
                             target_modules, carried, carried_credits):
        """Render the what-if analysis in its own window."""
        window, surface = _report.report_window(
            self.root, f"What-if: {current_course} → {target_course}", "880x660")

        _report.banner(surface,
                       f"Switching to {target_course}",
                       f"{student_name} ({student_id}) — currently on {current_course}")

        # Only credit from passed modules that belong to the target counts.
        # This used to be every credit the student had earned, so switching
        # to an unrelated programme claimed credit for modules that list
        # below as not carrying across.
        remaining = max(0, required_credits - carried_credits)
        pct = (carried_credits / required_credits * 100) if required_credits else 0.0

        _report.stat_strip(surface, [
            (f"{carried_credits:.0f}", "Credits carried across"),
            (f"{required_credits}", f"Required for {target_course}"),
            (f"{remaining:.0f}", "Still to earn",
             _report.OK if remaining == 0 else _report.WARN),
            (f"{pct:.1f}%", "Toward the target"),
        ])

        body = _report.card(surface, "Current standing")
        _report.kv_grid(body, [
            ("Current course", current_course or "—"),
            ("Target course", target_course),
            ("Modules enrolled", progress["modules_enrolled"]),
            ("Modules passed", progress["modules_completed"]),
            ("Modules marked so far", progress["modules_graded"]),
            ("Modules available on target", target_modules),
        ])

        if carried:
            _report.card(surface, f"Modules that carry across to {target_course}",
                         accent="#16a34a")
            _report.table(
                surface, ("Code", "Module", "Status", "Grade"),
                [(c, n or "—", st or "—", g or "Not graded") for c, n, st, g in carried],
                widths={"Code": 110, "Module": 280, "Status": 110, "Grade": 100})
        else:
            body = _report.card(surface, f"Modules that carry across to {target_course}",
                                accent=_report.MUTED)
            tk.Label(body,
                     text="None of this student's modules belong to the target "
                          "course, so the switch would start from zero.",
                     bg=_report.CARD, fg=_report.MUTED, font=(_report.FONT, 9),
                     wraplength=620, justify="left").pack(anchor="w")

        # The recommendation reads off credits carried, not a module count
        # against a made-up "40 modules for a degree" constant.
        if progress["modules_graded"] == 0:
            _report.verdict(
                surface, None, "No marked work yet", neutral=True,
                detail=(f"{student_name} has no graded modules, so nothing has "
                        f"been earned to carry across. The comparison below is "
                        f"based on enrolment only and will change once work is "
                        f"marked."))
        elif pct >= 50:
            _report.verdict(surface, True, "Feasible",
                            f"Over half of {target_course}'s credits are already earned. "
                            f"About {remaining:.0f} credits would remain.")
        elif pct >= 25:
            _report.verdict(surface, False, "Possible, with significant extra work",
                            f"{pct:.1f}% of {target_course}'s credits are earned; "
                            f"about {remaining:.0f} credits would remain.")
        else:
            _report.verdict(surface, False, "Consider carefully",
                            f"Only {pct:.1f}% of {target_course}'s credits are earned. "
                            f"About {remaining:.0f} credits would remain, which is close "
                            f"to starting the course afresh.")

        window.lift()

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

        def _status(text, colour):
            """Update the confirmation line under the schedule form."""
            label = getattr(self, "appointment_email_status", None)
            if label is None:
                return
            try:
                label.config(text=text, foreground=colour)
            except Exception:
                logger.debug("Suppressed exception", exc_info=True)

        def _notify_failure(err):
            _status(f"⚠ Appointment saved, but the confirmation emails could "
                    f"not be sent: {err}", "#dc2626")
            messagebox.showwarning(
                _("common.warning"),
                "The appointment was saved, but the confirmation email could "
                f"not be sent:\n{err}",
            )

        _status("Sending confirmation emails…", "#7f8c8d")

        def _worker():
            try:
                sent = self._send_appointment_emails(**kwargs)
            except Exception as email_err:  # noqa: BLE001 - best-effort delivery
                print(f"Appointment email notification failed: {email_err}")
                if root is not None:
                    try:
                        root.after(0, lambda err=email_err: _notify_failure(err))
                    except Exception:
                        logger.debug("Suppressed exception", exc_info=True)
            else:
                if root is not None:
                    try:
                        root.after(0, lambda s=sent: _status(_describe_email_result(s),
                                                             "#16a34a" if s.get("sent")
                                                             else "#d97706"))
                    except Exception:
                        logger.debug("Suppressed exception", exc_info=True)

        threading.Thread(target=_worker, name="advising-email", daemon=True).start()

    def _is_admin(self):
        """True for a role that may see everyone's appointments."""
        user = getattr(self.auth, "current_user", None) if self.auth else None
        role = str((user or {}).get("role", "")).strip().lower()
        return role in ("admin", "superadmin", "staff")

    def _fill_appointments(self, appointments, scope_text):
        self.appointments_tree.delete(*self.appointments_tree.get_children())
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
        label = getattr(self, "appointments_scope", None)
        if label is not None:
            label.config(text=f"{scope_text} — {len(appointments)} appointment(s)")

    def load_appointments(self):
        """Load the signed-in user's advising appointments."""
        try:
            student_id = self.auth.current_user.get('username') if self.auth.current_user else None
            if not student_id:
                messagebox.showwarning(_("common.warning"), _("degree_audit.messages.no_user_logged_in"))
                return
            self._fill_appointments(
                AdvisingAppointmentManager.get_student_appointments(student_id),
                f"Showing appointments for {student_id}")
        except Exception as e:
            messagebox.showerror(_("common.error"), _("degree_audit.messages.failed_load_appointments").format(error=e))

    def load_all_appointments(self):
        """Load every appointment — administrators only."""
        if not self._is_admin():
            messagebox.showwarning(
                _("common.warning"),
                "Only administrators can view all appointments.")
            return
        try:
            self._fill_appointments(
                AdvisingAppointmentManager.get_all_appointments(),
                "Showing all appointments")
        except Exception as e:
            messagebox.showerror(_("common.error"), _("degree_audit.messages.failed_load_appointments").format(error=e))
