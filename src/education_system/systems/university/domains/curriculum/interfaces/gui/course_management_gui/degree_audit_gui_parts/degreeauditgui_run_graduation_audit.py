"""Methods run_graduation_audit through view_requirements."""
import logging

logger = logging.getLogger(__name__)

from .. import degree_audit_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})

# Imported after the namespace splat so it cannot be shadowed.
from .. import report_widgets as _report


class DegreeAuditGUI:
    def run_graduation_audit(self):
        """Run the graduation audit and show the result in its own window."""
        try:
            student_id = self._student_id_from_label(self.grad_student_entry.get())
            course_selection = self.grad_program_combo.get()

            if not student_id or not course_selection:
                messagebox.showwarning(_("common.warning"), _("degree_audit.messages.enter_student_select_course"))
                return

            course_code = course_selection.split(':')[1].split('-')[0].strip()

            # Single source of truth for eligibility — the same check the
            # Graduation Ceremony GUI uses to gate RSVPs, so the two agree.
            from education_system.systems.university.domains.progression.domain.degree_audit.graduation_eligibility import (
                check_eligibility,
            )
            report = check_eligibility(student_id)
            if any('No student record' in r for r in report.get('reasons', [])):
                messagebox.showerror(_("common.error"), _("degree_audit.messages.student_not_found_db").format(student_id=student_id))
                return

            all_met = report['eligible']

            # Remember the outcome so "Add to Graduation Ceremony" only works
            # for an eligible student.
            self._grad_eligible = all_met
            self._grad_student_id = student_id
            if hasattr(self, '_grad_add_ceremony_btn'):
                self._grad_add_ceremony_btn.config(
                    state='normal' if all_met else 'disabled')

            self._update_grad_checklist(report)
            self._show_graduation_results(student_id, course_code, report)

            log_activity('run', 'graduation_audit', student_id,
                         {'course': course_code, 'can_graduate': all_met})

        except Exception as e:
            messagebox.showerror(_("common.error"), f"Failed to run audit: {e}")

    def _update_grad_checklist(self, report):
        """Refresh the on-tab checklist from the audit result.

        The items are outcomes, not inputs, so they are not editable — but
        they used to be ``ttk.Checkbutton(state='disabled')``, which renders
        grey whether ticked or not, so the result was unreadable. Two of the
        five were never populated at all. They are now ✓ / ✗ / — indicators,
        with "—" meaning *not assessed* rather than failed.
        """
        results = {
            'all_requirements': report.get('eligible'),
            # No GPA rule in a UK award: shown as not assessed.
            'gpa_requirement': None,
            'credit_requirement': report.get('credit_met'),
            # Not modelled anywhere yet: say so rather than showing a cross
            # that reads as "this student failed it".
            'residency': None,
            'financial': None,
        }
        for key, indicator in getattr(self, '_checklist_indicators', {}).items():
            value = results.get(key)
            mark, colour = ("\u2713", "#16a34a") if value else (
                ("\u2014", "#95a5a6") if value is None else ("\u2717", "#dc2626"))
            suffix = "" if value is not None else "  (not assessed)"
            indicator.config(text=f"{mark} {indicator._label}{suffix}", foreground=colour)
            if key in self.checklist_vars:
                self.checklist_vars[key].set(bool(value))

    def _show_graduation_results(self, student_id, course_code, report):
        """Render the audit in its own window."""
        eligible = report['eligible']
        window, surface = _report.report_window(
            self.root, f"Graduation audit — {report['student_name']}", "900x700")

        _report.banner(
            surface, f"Graduation audit — {report['student_name']}",
            f"{student_id} · audited against {course_code}")

        credits = report['credits_earned']
        required = report['required_credits']
        _report.stat_strip(surface, [
            (f"{credits:.0f}", "Credits recorded",
             _report.OK if report['credit_met'] else _report.WARN),
            (f"{required}", "Programme award needs"),
            (f"{report['modules_completed']}", "Modules passed"),
            ("Yes" if report.get('award_ratified') else "No", "Award ratified",
             _report.OK if report.get('award_ratified') else _report.WARN),
        ])

        body = _report.card(surface, "Progress (advisory — the board's ratification decides)")
        pairs = [
            ("Credits recorded", f"{credits:.0f} / {required}"),
            ("Modules passed", f"{report['modules_completed']}"),
        ]
        if report.get('modules_enrolled') is not None:
            pairs.append(("Modules enrolled", report.get('modules_enrolled', 0)))
            pairs.append(("Modules marked", report.get('modules_graded', 0)))
        if report.get('certificate_name'):
            pairs.append(("Name on certificate", report['certificate_name'] + (
                "" if report.get('name_confirmed') else "  (not yet confirmed)")))
        _report.kv_grid(body, pairs)

        body = _report.card(surface, "Requirements", accent="#9b59b6")
        _report.status_list(body, [
            (report.get('award_ratified'), "Ratified award",
             "released by an assessment board" if report.get('award_ratified')
             else "no ratified, release-authorised award"),
            (not report.get('reasons'), "No graduation holds",
             "none" if not report.get('reasons') else f"{len(report['reasons'])} blocking"),
            (report['credit_met'] or None, "Credits against the programme rule",
             f"{credits:.0f} of {required} (advisory)"),
        ])

        warnings = report.get('warnings') or []
        if warnings:
            body = _report.card(surface, "Warnings (not blocking)", accent=_report.WARN)
            _report.kv_grid(body, [(f"{n}", w) for n, w in enumerate(warnings, 1)])

        if report.get('ratified_award'):
            award = report['ratified_award']
            body = _report.card(surface, "Ratified award", accent=_report.OK)
            _report.kv_grid(body, [
                ("Award", award.get('award_name', '—')),
                ("Classification", award.get('classification', '—')),
                ("Academic year", award.get('academic_year', '—')),
                ("Ratified at", award.get('ratified_at', '—')),
            ])

        reasons = report.get('reasons') or []
        if eligible:
            _report.verdict(surface, True, "Eligible for graduation",
                            "All requirements are met. You may proceed with approval.")
        else:
            _report.verdict(
                surface, False, "Not eligible for graduation",
                "\n".join(f"• {r}" for r in reasons)
                if reasons else "One or more requirements are outstanding.")

        window.lift()

    def _grad_officer(self):
        """The signed-in user as a graduation Officer (``None`` if signed out)."""
        from education_system.systems.university.application.graduation import access as ga
        from education_system.systems.university.domains.research.interfaces.gui.research.research_portal import (
            common,
        )
        user = getattr(getattr(self, 'auth', None), 'current_user', None)
        return common.call(self.root, ga.from_user, user, quiet=True) if user else None

    def approve_graduation(self):
        """Confer the award in absentia, or invite the student to a ceremony.

        This used to set ``students.status = 'Graduated'`` directly. Conferral
        now goes through ``university/application/graduation/conferral``,
        which checks the ratified award, holds and the certificate name."""
        from education_system.systems.university.application.graduation import conferral as gc
        from education_system.systems.university.domains.research.interfaces.gui.research.research_portal import (
            common,
        )
        student_id = self._student_id_from_label(self.grad_student_entry.get())
        grad_date = (self.grad_date_entry.get().strip()
                     if hasattr(self, 'grad_date_entry') else "") or None
        if not student_id:
            messagebox.showwarning(_("common.warning"),
                                   _("degree_audit.messages.run_audit_first",
                                     default="Run a graduation audit for a student first."))
            return
        who = self._grad_officer()
        if who is None or not who.is_office:
            messagebox.showerror(_("common.error"),
                                 "Only the graduation office can confer awards.")
            return
        choice = messagebox.askyesnocancel(
            _("degree_audit.dialogs.confirm_graduation", default="Graduation"),
            f"Confer {student_id}'s award in absentia now?\n\n"
            "Yes – confer in absentia (certificate posted)\n"
            "No – invite them to a ceremony instead")
        if choice is None:
            return
        if not choice:
            self._add_to_ceremony()
            return
        result = common.call(self.root, gc.confer, who, student_id, mode="in_absentia",
                             conferral_date=grad_date, write=True)
        if result is None:
            return
        gc.after_commit(result)
        log_activity('confer', 'graduation', student_id,
                     {'mode': 'in_absentia', 'certificate': result['certificate_number']})
        messagebox.showinfo(
            _("common.success"),
            f"Award conferred.\nCertificate {result['certificate_number']}\n"
            f"Verification code {result['verification_code']}")

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

        from education_system.systems.university.domains.progression.domain.degree_audit.graduation_eligibility import (
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
            from education_system.systems.university.application.graduation import (
                ceremonies as gcer,
            )
            from education_system.systems.university.domains.progression.domain.degree_audit.graduation_ceremony import (
                CeremonyManager,
            )
            from education_system.systems.university.domains.research.interfaces.gui.research.research_portal import (
                common,
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
        who = self._grad_officer()
        result = common.call(self.root, gcer.invite, who, cid, [sid], write=True)
        if result is None:
            return
        if result.get('skipped'):
            messagebox.showwarning(_("common.warning"),
                                   "\n".join(f"{s}: {why}" for s, why in result['skipped']))
            return

        try:
            log_activity('add_to_ceremony', 'graduation_ceremony', sid, {'ceremony_id': cid})
        except Exception:
            logger.debug("Suppressed exception", exc_info=True)
        if messagebox.askyesno(
                _("common.success"),
                _("degree_audit.dialogs.invited_open_question",
                  default="{name} has been invited to the ceremony.\n\n"
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
            from education_system.systems.university.domains.curriculum.interfaces.gui.course_management_gui.graduation_ceremony_gui import (
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
