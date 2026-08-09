"""Methods run_graduation_audit through view_requirements."""

from .. import degree_audit_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class DegreeAuditGUI:
    def run_graduation_audit(self):
        """Run comprehensive graduation audit using actual database data"""
        try:
            student_id = self._student_id_from_label(self.grad_student_entry.get())
            course_selection = self.grad_program_combo.get()

            if not student_id or not course_selection:
                messagebox.showwarning(_("common.warning"), _("degree_audit.messages.enter_student_select_course"))
                return

            # Extract course code from selection
            course_code = course_selection.split(':')[1].split('-')[0].strip()

            # Single source of truth for eligibility — the same check the
            # Graduation Ceremony GUI uses to gate RSVPs, so the two agree.
            from education_system.systems.university.domains.academics.domain.services.degree_audit.graduation_eligibility import (
                check_eligibility,
            )
            report = check_eligibility(student_id)
            if any('No student record' in r for r in report.get('reasons', [])):
                messagebox.showerror(_("common.error"), _("degree_audit.messages.student_not_found_db").format(student_id=student_id))
                return

            student_name = report['student_name']
            enrolled_course = self._student_course(student_id) or ''
            modules_completed = report['modules_completed']
            credits_earned = report['credits_earned']
            current_gpa = report['current_gpa']
            required_credits = report['required_credits']
            required_gpa = report['required_gpa']
            required_modules = report['required_modules']
            credit_met = report['credit_met']
            gpa_met = report['gpa_met']
            modules_met = report['modules_met']
            all_met = report['eligible']

            # Remember the outcome so the "Add to Graduation Ceremony" button
            # only works for an eligible student.
            self._grad_eligible = all_met
            self._grad_student_id = student_id
            if hasattr(self, '_grad_add_ceremony_btn'):
                self._grad_add_ceremony_btn.config(
                    state='normal' if all_met else 'disabled')

            # Update checklist
            self.checklist_vars['all_requirements'].set(all_met)
            self.checklist_vars['gpa_requirement'].set(gpa_met)
            self.checklist_vars['credit_requirement'].set(credit_met)

            # Display results
            self.grad_results_text.delete('1.0', tk.END)
            self.grad_results_text.insert(tk.END, "GRADUATION AUDIT RESULTS\n")
            self.grad_results_text.insert(tk.END, "=" * 60 + "\n\n")
            self.grad_results_text.insert(tk.END, f"Student: {student_name} ({student_id})\n")
            self.grad_results_text.insert(tk.END, f"Enrolled Course: {enrolled_course}\n")
            self.grad_results_text.insert(tk.END, f"Audit Course: {course_code}\n\n")

            self.grad_results_text.insert(tk.END, "PROGRESS:\n")
            self.grad_results_text.insert(tk.END, f"  Modules Completed: {modules_completed} / {required_modules}\n")
            self.grad_results_text.insert(tk.END, f"  Credits Earned: {credits_earned:.0f} / {required_credits}\n")
            self.grad_results_text.insert(tk.END, f"  Current GPA: {current_gpa:.2f} / {required_gpa:.2f}\n\n")

            self.grad_results_text.insert(tk.END, "REQUIREMENT STATUS:\n")
            self.grad_results_text.insert(tk.END, f"  Module Requirement: {'PASS' if modules_met else 'FAIL'}\n")
            self.grad_results_text.insert(tk.END, f"  Credit Requirement: {'PASS' if credit_met else 'FAIL'}\n")
            self.grad_results_text.insert(tk.END, f"  GPA Requirement: {'PASS' if gpa_met else 'FAIL'}\n")
            self.grad_results_text.insert(tk.END, f"  All Requirements: {'PASS' if all_met else 'FAIL'}\n\n")

            if all_met:
                self.grad_results_text.insert(tk.END,
                    "RESULT: ELIGIBLE FOR GRADUATION\n\n"
                    "The student has met all requirements for graduation.\n"
                    "You may proceed with graduation approval.")
            else:
                self.grad_results_text.insert(tk.END,
                    "RESULT: NOT ELIGIBLE FOR GRADUATION\n\n"
                    "The student has not met all requirements.\n")
                if not modules_met:
                    self.grad_results_text.insert(tk.END, f"  - Complete {required_modules - modules_completed} more modules\n")
                if not credit_met:
                    self.grad_results_text.insert(tk.END, f"  - Earn {required_credits - credits_earned:.0f} more credits\n")
                if not gpa_met:
                    self.grad_results_text.insert(tk.END, f"  - Raise GPA by {required_gpa - current_gpa:.2f} points\n")

            log_activity('run', 'graduation_audit', student_id,
                       {'course': course_code, 'can_graduate': all_met})

            messagebox.showinfo(_("common.success"), _("degree_audit.messages.graduation_audit_completed_short"))

        except Exception as e:
            messagebox.showerror(_("common.error"), f"Failed to run audit: {e}")

    def approve_graduation(self):
        """Approve student for graduation"""
        try:
            student_id = self._student_id_from_label(self.grad_student_entry.get())
            course_selection = self.grad_program_combo.get()
            grad_date = self.grad_date_entry.get().strip()

            if not student_id or not course_selection or not grad_date:
                messagebox.showwarning(_("common.warning"), _("degree_audit.messages.student_course_date_required"))
                return

            course_code = course_selection.split(':')[1].split('-')[0].strip()

            # Confirm approval
            confirm = messagebox.askyesno(_("degree_audit.dialogs.confirm_graduation"),
                _("degree_audit.dialogs.confirm_graduation_question").format(student_id=student_id, grad_date=grad_date, course_code=course_code))

            if not confirm:
                return

            with get_connection() as conn:
                cursor = conn.cursor()

                # Check if student exists
                cursor.execute('SELECT student_id, status FROM students WHERE student_id = ?', (student_id,))
                student = cursor.fetchone()
                if not student:
                    messagebox.showerror(_("common.error"), _("degree_audit.messages.student_not_found").format(student_id=student_id))
                    return

                # Update student status to Graduated
                cursor.execute('''
                    UPDATE students
                    SET status = 'Graduated'
                    WHERE student_id = ?
                ''', (student_id,))

                conn.commit()

            log_activity('approve', 'graduation', student_id,
                       {'course': course_code, 'date': grad_date})

            messagebox.showinfo(_("common.success"),
                _("degree_audit.messages.graduation_approved_success").format(student_id=student_id, grad_date=grad_date, course_code=course_code))

            # Approval makes the student a confirmed graduand — offer to enrol
            # them onto a ceremony right away (continuous audit → ceremony flow).
            self._grad_student_id = student_id
            self._grad_eligible = True
            if hasattr(self, '_grad_add_ceremony_btn'):
                self._grad_add_ceremony_btn.config(state='normal')
            if messagebox.askyesno(
                    _("degree_audit.dialogs.add_to_ceremony_title", default="Graduation Ceremony"),
                    _("degree_audit.dialogs.add_to_ceremony_question",
                      default="Add {student_id} to a graduation ceremony now?").format(student_id=student_id)):
                self._add_to_ceremony()

        except Exception as e:
            messagebox.showerror(_("common.error"), f"Failed to approve graduation: {e}")

    def _add_to_ceremony(self):
        """Enrol the audited/approved student onto a graduation ceremony.

        Defence-in-depth: re-checks eligibility here even though the button is
        only enabled for eligible students, so this can never add an ineligible
        graduand regardless of how it's invoked."""
        sid = getattr(self, '_grad_student_id', None) or \
            self._student_id_from_label(self.grad_student_entry.get())
        if not sid:
            messagebox.showwarning(_("common.warning"),
                                   _("degree_audit.messages.run_audit_first",
                                     default="Run a graduation audit for a student first."))
            return

        from education_system.systems.university.domains.academics.domain.services.degree_audit.graduation_eligibility import (
            check_eligibility,
        )
        report = check_eligibility(sid)
        if not report.get('eligible') and not report.get('error'):
            reasons = "\n".join(f"  • {r}" for r in report.get('reasons', []))
            messagebox.showwarning(
                _("degree_audit.dialogs.not_eligible_title", default="Not eligible"),
                f"{report.get('student_name', sid)} is not eligible for "
                f"graduation, so cannot be added to a ceremony:\n\n{reasons}")
            return

        try:
            from education_system.systems.university.domains.academics.domain.services.degree_audit.graduation_ceremony import (
                CeremonyManager, RsvpManager,
            )
        except Exception as e:
            messagebox.showerror(_("common.error"), f"Ceremony service unavailable: {e}")
            return

        ceremonies = CeremonyManager.list_ceremonies(status='scheduled')
        if not ceremonies:
            if messagebox.askyesno(
                    _("degree_audit.dialogs.no_ceremonies_title", default="No ceremonies"),
                    _("degree_audit.dialogs.no_ceremonies_question",
                      default="There are no scheduled ceremonies. Open the Ceremony "
                              "Manager to create one?")):
                self._open_ceremony_gui()
            return

        cid = self._pick_ceremony_dialog(ceremonies)
        if cid is None:
            return
        try:
            RsvpManager.record_rsvp(ceremony_id=cid, student_id=sid, rsvp_status='going')
        except ValueError as ve:
            messagebox.showwarning(_("common.warning"), str(ve))
            return
        except Exception as e:
            messagebox.showerror(_("common.error"), str(e))
            return

        try:
            log_activity('add_to_ceremony', 'graduation_ceremony', sid, {'ceremony_id': cid})
        except Exception:
            pass
        if messagebox.askyesno(
                _("common.success"),
                _("degree_audit.dialogs.added_open_question",
                  default="{name} added to the ceremony as a graduand.\n\n"
                          "Open the Ceremony Manager now?").format(
                      name=report.get('student_name', sid))):
            self._open_ceremony_gui()

    def _pick_ceremony_dialog(self, ceremonies):
        """Small modal to choose a ceremony; returns ceremony_id or None."""
        dlg = tk.Toplevel(self.root)
        dlg.title(_("degree_audit.dialogs.pick_ceremony_title", default="Choose ceremony"))
        dlg.transient(self.root)
        dlg.grab_set()
        ttk.Label(dlg, text=_("degree_audit.labels.ceremony", default="Ceremony:"),
                  padding=8).pack(anchor=tk.W)
        labels, by_label = [], {}
        for c in ceremonies:
            label = f"{c['ceremony_name']} — {c['ceremony_date']} {c.get('ceremony_time','')} @ {c.get('venue','')}"
            labels.append(label)
            by_label[label] = c['ceremony_id']
        combo = ttk.Combobox(dlg, width=56, state='readonly', values=labels)
        combo.current(0)
        combo.pack(padx=10, pady=6)
        chosen = {'id': None}

        def ok():
            chosen['id'] = by_label.get(combo.get())
            dlg.destroy()
        btns = ttk.Frame(dlg, padding=8)
        btns.pack()
        ttk.Button(btns, text=_("common.ok", default="Add"), command=ok).pack(side=tk.LEFT, padx=5)
        ttk.Button(btns, text=_("common.cancel", default="Cancel"),
                   command=dlg.destroy).pack(side=tk.LEFT, padx=5)
        dlg.wait_window()
        return chosen['id']

    def _open_ceremony_gui(self):
        """Launch the Graduation Ceremony manager in its own window."""
        try:
            from education_system.systems.university.domains.academics.interfaces.gui.course_management_gui.graduation_ceremony_gui import (
                GraduationCeremonyGUI,
            )
            GraduationCeremonyGUI(tk.Toplevel(self.root), auth=getattr(self, 'auth', None))
        except Exception as e:
            messagebox.showerror(_("common.error"),
                                 f"Could not open the Graduation Ceremony manager: {e}")

    def view_requirements(self):
        """Show program requirements"""
        messagebox.showinfo(_("degree_audit.dialogs.view_requirements_title"),
                          _("degree_audit.dialogs.view_requirements_message"))
