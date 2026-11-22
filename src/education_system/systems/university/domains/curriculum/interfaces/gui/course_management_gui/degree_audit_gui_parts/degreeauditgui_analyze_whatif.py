"""Methods analyze_whatif through load_appointments."""
import logging

logger = logging.getLogger(__name__)

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import degree_audit_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})

# Imported after the namespace splat so it cannot be shadowed.
from .. import report_widgets as _report
from education_system.platform.delivery.gui.tk_threads import start_thread, ui


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

            with get_connection() as conn:
                figures = self._whatif_figures(conn, student_id, target_course)
            if figures is None:
                messagebox.showerror(_("common.error"), f"Student {student_id} not found")
                return
            self._show_whatif_results(**figures)
            self.refresh_whatif_scenarios()

        except Exception as e:
            messagebox.showerror(_("common.error"), f"Failed to analyze scenario: {e}")

    def _whatif_figures(self, conn, student_id, target_course):
        """Where a student would stand on another course; None if no such student."""
        from education_system.systems.university.domains.progression.domain.degree_audit.progress import (
            earned_progress,
            module_progress,
            required_credits_for_course,
        )
        cursor = conn.cursor()
        cursor.execute(
            'SELECT course, first_name, last_name FROM students WHERE student_id = ?',
            (student_id,))
        student_data = cursor.fetchone()
        if not student_data:
            return None
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

        return {
            "student_id": student_id, "student_name": student_name,
            "current_course": student_data[0], "target_course": target_course,
            "progress": progress, "required_credits": required_credits,
            "target_modules": target_modules, "carried": carried,
            "carried_credits": carried_credits,
        }

    @staticmethod
    def _whatif_outlook(student_name, target_course, progress, pct, remaining):
        """(ok, headline, detail, neutral) for a what-if comparison.

        Reads off credits carried, not a module count against a made-up
        "40 modules for a degree" constant.
        """
        if progress["modules_graded"] == 0:
            return (None, "No marked work yet",
                    f"{student_name} has no graded modules, so nothing has been earned to "
                    f"carry across. The comparison below is based on enrolment only and "
                    f"will change once work is marked.", True)
        if pct >= 50:
            return (True, "Feasible",
                    f"Over half of {target_course}'s credits are already earned. "
                    f"About {remaining:.0f} credits would remain.", False)
        if pct >= 25:
            return (False, "Possible, with significant extra work",
                    f"{pct:.1f}% of {target_course}'s credits are earned; "
                    f"about {remaining:.0f} credits would remain.", False)
        return (False, "Consider carefully",
                f"Only {pct:.1f}% of {target_course}'s credits are earned. "
                f"About {remaining:.0f} credits would remain, which is close "
                f"to starting the course afresh.", False)

    def refresh_whatif_scenarios(self):
        """Fill the results box with the selected student's saved scenarios."""
        tree = self.whatif_tree
        tree.delete(*tree.get_children())
        self._whatif_row_targets = {}
        student_id = self._whatif_student_id()
        if not student_id:
            self.whatif_status.config(
                text="Select a student to see their saved scenarios.")
            return
        try:
            with get_connection() as conn:
                saved = conn.execute(
                    "SELECT s.scenario_id, s.scenario_name, p.program_code, s.created_at "
                    "FROM degree_what_if_scenarios s "
                    "LEFT JOIN degree_programs p ON p.program_id = s.target_program_id "
                    "WHERE s.student_id = ? ORDER BY s.created_at DESC, s.scenario_id DESC",
                    (student_id,)).fetchall()
                for scenario_id, name, target, created in saved:
                    figures = self._whatif_figures(conn, student_id, target) if target else None
                    if figures is None:
                        values = (name, target or "—", "—", "—", "—", "Course no longer available",
                                  str(created or "")[:16].replace("T", " "))
                    else:
                        required = figures["required_credits"]
                        carried = figures["carried_credits"]
                        remaining = max(0, required - carried)
                        pct = (carried / required * 100) if required else 0.0
                        headline = self._whatif_outlook(
                            figures["student_name"], target, figures["progress"], pct, remaining)[1]
                        values = (name, target, f"{carried:.0f}", f"{remaining:.0f}", f"{pct:.1f}%",
                                  headline, str(created or "")[:16].replace("T", " "))
                        self._whatif_row_targets[str(scenario_id)] = target
                    tree.insert('', tk.END, iid=str(scenario_id), values=values)
        except Exception as e:  # noqa: BLE001 - shown in the box itself
            logger.warning("Could not load what-if scenarios", exc_info=True)
            self.whatif_status.config(text=f"Could not load saved scenarios: {e}")
            return
        self.whatif_status.config(
            text=(f"{len(saved)} saved scenario(s) for {student_id}. "
                  "Double-click one for the full comparison.") if saved
            else f"No saved scenarios for {student_id} yet. Create one above.")

    def _open_selected_whatif(self, _event=None):
        """Open the full comparison for the double-clicked scenario."""
        selected = self.whatif_tree.focus()
        target = self._whatif_row_targets.get(selected)
        if not target:
            return
        try:
            with get_connection() as conn:
                figures = self._whatif_figures(conn, self._whatif_student_id(), target)
            if figures:
                self._show_whatif_results(**figures)
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

        ok, headline, detail, neutral = self._whatif_outlook(
            student_name, target_course, progress, pct, remaining)
        _report.verdict(surface, ok, headline, detail, neutral=neutral)

        window.lift()

    def schedule_appointment(self):
        """Schedule an advising appointment"""
        try:
            fields = self.appointment_fields

            student_id = self._student_id_from_label(fields['student'].get())
            advisor_id = self._student_id_from_label(fields['advisor'].get())
            date = fields['date'].get().strip()
            time = fields['time'].get().strip()
            appt_type = fields['type'].get()
            duration = int(fields['duration'].get())
            topic = fields['topic'].get().strip()
            notes = fields['notes'].get('1.0', tk.END).strip()

            if not all([student_id, advisor_id, date, time]):
                messagebox.showwarning(_("common.warning"), _("degree_audit.messages.appointment_fields_required"))
                return
            if date < datetime.now().strftime('%Y-%m-%d'):
                messagebox.showwarning(
                    _("common.warning"),
                    _t('gui.academics.course_management_gui.degree_audit_gui_parts.degreeauditgui_analyze_whatif.dialogs.appointment_date_has_passed',
                       default="That date has already passed. Please choose today or a later date."))
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
            fields['student'].set("")
            fields['advisor'].set("")
            fields['topic'].set("")
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
            # to the main thread via ``tk_threads.ui``.
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
                        ui(root, _notify_failure, email_err)
                    except Exception:
                        logger.debug("Suppressed exception", exc_info=True)
            else:
                if root is not None:
                    try:
                        ui(root, lambda s=sent: _status(_describe_email_result(s),
                                                        "#16a34a" if s.get("sent")
                                                        else "#d97706"))
                    except Exception:
                        logger.debug("Suppressed exception", exc_info=True)

        if root is not None:
            start_thread(root, _worker, name="advising-email")
        else:
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
