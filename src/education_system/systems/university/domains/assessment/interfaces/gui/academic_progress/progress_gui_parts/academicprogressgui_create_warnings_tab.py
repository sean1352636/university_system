"""Methods create_warnings_tab through create_transcript_tab."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import progress_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class AcademicProgressGUI:
    def create_warnings_tab(self):
        """Create warnings management tab."""
        warnings_tab = ttk.Frame(self.notebook)
        self.notebook.add(warnings_tab, text=_t("academic_progress.tabs.warnings", default="⚠️ Warnings"))

        # Action buttons
        button_frame = ttk.Frame(warnings_tab)
        button_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(button_frame, text=_t('gui.assessment.academic_progress.progress_gui_parts.academicprogressgui_create_warnings_tab.buttons.check_active_warnings', default="Check Active Warnings"),
                  command=self.load_active_warnings).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_t('gui.assessment.academic_progress.progress_gui_parts.academicprogressgui_create_warnings_tab.buttons.run_warning_scan', default="Run Warning Scan"),
                  command=self.run_warning_scan).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_t('gui.assessment.academic_progress.progress_gui_parts.academicprogressgui_create_warnings_tab.buttons.acknowledge_warning', default="Acknowledge Warning"),
                  command=self.acknowledge_warning_gui).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_t('gui.assessment.academic_progress.progress_gui_parts.academicprogressgui_create_warnings_tab.buttons.resolve_warning', default="Resolve Warning"),
                  command=self.resolve_warning_gui).pack(side=tk.LEFT, padx=5)

        # Warnings display
        self.warnings_text = scrolledtext.ScrolledText(warnings_tab, height=30, wrap=tk.WORD)
        self.warnings_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Auto-load warnings
        self.load_active_warnings()

    def load_active_warnings(self):
        """Load active warnings."""
        student_id = self.auth.get_current_user()['id']

        try:
            warnings = self.service.get_active_warnings(student_id)

            self.warnings_text.delete('1.0', tk.END)

            self.warnings_text.insert(tk.END, "═" * 80 + "\n", 'header')
            self.warnings_text.insert(tk.END, "  ACTIVE ACADEMIC WARNINGS\n".center(80), 'header')
            self.warnings_text.insert(tk.END, "═" * 80 + "\n\n", 'header')

            if not warnings:
                self.warnings_text.insert(tk.END, "✓ No active warnings! You're doing great!\n", 'positive')
                return

            self.warnings_text.insert(tk.END, f"Total Active Warnings: {len(warnings)}\n\n", 'bold')

            for warning in warnings:
                severity_symbol = {
                    'High': '🔴',
                    'Medium': '🟡',
                    'Low': '🟢'
                }.get(warning['severity'], '⚪')

                self.warnings_text.insert(tk.END, "─" * 80 + "\n", 'separator')
                self.warnings_text.insert(tk.END,
                    f"{severity_symbol} WARNING ID: {warning['warning_id']} - "
                    f"{warning['warning_type']} [{warning['severity']}]\n", 'warning_header')

                self.warnings_text.insert(tk.END, f"\n{warning['warning_message']}\n")

                if warning['trigger_metric']:
                    self.warnings_text.insert(tk.END, f"\nTrigger: {warning['trigger_metric']} = {warning['trigger_value']}\n")

                if warning['recommendations_json']:
                    import json
                    recommendations = json.loads(warning['recommendations_json'])
                    if recommendations:
                        self.warnings_text.insert(tk.END, "\n💡 RECOMMENDATIONS:\n", 'bold')
                        for rec in recommendations:
                            self.warnings_text.insert(tk.END, f"  • {rec}\n")

                ack_status = "✓ Acknowledged" if warning['acknowledged'] else "○ Not Acknowledged"
                self.warnings_text.insert(tk.END, f"\nStatus: {ack_status}\n")
                self.warnings_text.insert(tk.END, f"Created: {warning['created_at']}\n\n")

            # Configure tags
            self.warnings_text.tag_config('header', font=('Arial', 11, 'bold'))
            self.warnings_text.tag_config('bold', font=('Arial', 10, 'bold'))
            self.warnings_text.tag_config('separator', foreground='gray')
            self.warnings_text.tag_config('warning_header', font=('Arial', 10, 'bold'), foreground='red')
            self.warnings_text.tag_config('positive', font=('Arial', 11, 'bold'), foreground='green')

        except Exception as e:
            messagebox.showerror(_t('gui.assessment.academic_progress.progress_gui_parts.academicprogressgui_create_warnings_tab.dialogs.error', default="Error"), f"Failed to load warnings: {str(e)}")

    def run_warning_scan(self):
        """Run warning scan."""
        student_id = self.auth.get_current_user()['id']

        response = messagebox.askyesno(_t('gui.assessment.academic_progress.progress_gui_parts.academicprogressgui_create_warnings_tab.dialogs.run_warning_scan', default="Run Warning Scan"),
                                       _t('gui.assessment.academic_progress.progress_gui_parts.academicprogressgui_create_warnings_tab.dialogs.this_will_scan_your_academic_records_for_warning_indicators_cont', default="This will scan your academic records for warning indicators.\nContinue?"))
        if not response:
            return

        try:
            warnings = self.service.check_early_warnings(student_id)

            if warnings:
                messagebox.showinfo(_t('gui.assessment.academic_progress.progress_gui_parts.academicprogressgui_create_warnings_tab.dialogs.scan_complete', default="Scan Complete"),
                                   f"Warning scan complete.\n{len(warnings)} warning(s) detected.\n\nView the Warnings tab for details.")
            else:
                messagebox.showinfo(_t('gui.assessment.academic_progress.progress_gui_parts.academicprogressgui_create_warnings_tab.dialogs.scan_complete', default="Scan Complete"),
                                   _t('gui.assessment.academic_progress.progress_gui_parts.academicprogressgui_create_warnings_tab.dialogs.warning_scan_complete_no_warnings_detected_your_academic_perform', default="Warning scan complete.\nNo warnings detected! Your academic performance looks good."))

            # Refresh warnings display
            self.load_active_warnings()

        except Exception as e:
            messagebox.showerror(_t('gui.assessment.academic_progress.progress_gui_parts.academicprogressgui_create_warnings_tab.dialogs.error', default="Error"), f"Failed to run warning scan: {str(e)}")

    def _get_warning_id_from_user(self, action_name):
        """Get warning ID via a dropdown of active warnings instead of free-text entry."""
        try:
            student_id = self.auth.current_user.get('student_id') or self.auth.current_user.get('id') or self.auth.current_user.get('username')
            warnings = self.service.get_active_warnings(str(student_id))
            if not warnings:
                messagebox.showinfo(_t('gui.assessment.academic_progress.progress_gui_parts.academicprogressgui_create_warnings_tab.dialogs.info', default="Info"), _t('gui.assessment.academic_progress.progress_gui_parts.academicprogressgui_create_warnings_tab.dialogs.no_active_warnings_found', default="No active warnings found."))
                return None

            dlg = tk.Toplevel(self.root)
            dlg.title(f"{action_name} Warning")
            dlg.geometry("400x200")
            dlg.transient(self.root)
            dlg.grab_set()

            ttk.Label(dlg, text=f"Select warning to {action_name.lower()}:").pack(padx=10, pady=(15, 5), anchor=tk.W)
            warning_var = tk.StringVar()
            combo = ttk.Combobox(dlg, textvariable=warning_var, state='readonly', width=50)
            options = [f"{w['id']} - {w.get('type', w.get('warning_type', 'Warning'))} [{w.get('severity', 'medium')}]" for w in warnings]
            combo['values'] = options
            if options:
                combo.current(0)
            combo.pack(padx=10, pady=5)

            result = [None]

            def on_ok():
                sel = warning_var.get()
                if sel:
                    try:
                        result[0] = int(sel.split(' - ')[0])
                    except (ValueError, IndexError):
                        pass
                dlg.destroy()

            btn_frame = ttk.Frame(dlg)
            btn_frame.pack(pady=15)
            ttk.Button(btn_frame, text=_t('gui.assessment.academic_progress.progress_gui_parts.academicprogressgui_create_warnings_tab.buttons.ok', default="OK"), command=on_ok).pack(side=tk.LEFT, padx=5)
            ttk.Button(btn_frame, text=_t('gui.assessment.academic_progress.progress_gui_parts.academicprogressgui_create_warnings_tab.buttons.cancel', default="Cancel"), command=dlg.destroy).pack(side=tk.LEFT, padx=5)

            dlg.wait_window()
            return result[0]
        except Exception:
            return tk.simpledialog.askinteger(f"{action_name} Warning", "Enter Warning ID:")

    def acknowledge_warning_gui(self):
        """Acknowledge a warning."""
        warning_id = self._get_warning_id_from_user("Acknowledge")
        if warning_id is None:
            return

        try:
            success = self.service.acknowledge_warning(warning_id)
            if success:
                messagebox.showinfo(_t('gui.assessment.academic_progress.progress_gui_parts.academicprogressgui_create_warnings_tab.dialogs.success', default="Success"), f"Warning {warning_id} has been acknowledged.")
                self.load_active_warnings()
            else:
                messagebox.showerror(_t('gui.assessment.academic_progress.progress_gui_parts.academicprogressgui_create_warnings_tab.dialogs.error', default="Error"), f"Failed to acknowledge warning {warning_id}.")
        except Exception as e:
            messagebox.showerror(_t('gui.assessment.academic_progress.progress_gui_parts.academicprogressgui_create_warnings_tab.dialogs.error', default="Error"), f"Failed to acknowledge warning: {str(e)}")

    def resolve_warning_gui(self):
        """Resolve a warning."""
        warning_id = self._get_warning_id_from_user("Resolve")
        if warning_id is None:
            return

        notes = tk.simpledialog.askstring("Resolution Notes",
                                         "Enter resolution notes (optional):")

        try:
            success = self.service.resolve_warning(warning_id, notes)
            if success:
                messagebox.showinfo(_t('gui.assessment.academic_progress.progress_gui_parts.academicprogressgui_create_warnings_tab.dialogs.success', default="Success"), f"Warning {warning_id} has been resolved!")
                self.load_active_warnings()
            else:
                messagebox.showerror(_t('gui.assessment.academic_progress.progress_gui_parts.academicprogressgui_create_warnings_tab.dialogs.error', default="Error"), f"Failed to resolve warning {warning_id}.")
        except Exception as e:
            messagebox.showerror(_t('gui.assessment.academic_progress.progress_gui_parts.academicprogressgui_create_warnings_tab.dialogs.error', default="Error"), f"Failed to resolve warning: {str(e)}")

    def create_forecast_tab(self):
        """Create graduation forecast tab."""
        forecast_tab = ttk.Frame(self.notebook)
        self.notebook.add(forecast_tab, text=_t("academic_progress.tabs.forecast", default="🎓 Forecast"))

        # Program selector
        selector_frame = ttk.Frame(forecast_tab)
        selector_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(selector_frame, text=_t('gui.assessment.academic_progress.progress_gui_parts.academicprogressgui_create_warnings_tab.labels.program_code', default="Program Code:"), font=('Arial', 10, 'bold')).pack(side=tk.LEFT, padx=5)
        self.forecast_program_var = tk.StringVar()

        # Get available programs
        try:
            available_programs = self.service.get_available_programs()
            program_codes = [p['program_code'] for p in available_programs]
            program_combo = ttk.Combobox(selector_frame, textvariable=self.forecast_program_var,
                                        values=program_codes, width=15, state='readonly')
            program_combo.pack(side=tk.LEFT, padx=5)
        except Exception:
            ttk.Entry(selector_frame, textvariable=self.forecast_program_var, width=15).pack(side=tk.LEFT, padx=5)

        ttk.Button(selector_frame, text=_t('gui.assessment.academic_progress.progress_gui_parts.academicprogressgui_create_warnings_tab.buttons.generate_forecast', default="Generate Forecast"),
                  command=self.generate_forecast).pack(side=tk.LEFT, padx=5)

        # Results
        self.forecast_text = scrolledtext.ScrolledText(forecast_tab, height=30, wrap=tk.WORD)
        self.forecast_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    def generate_forecast(self):
        """Generate graduation forecast."""
        program_code = self.forecast_program_var.get().strip().upper()
        if not program_code:
            messagebox.showwarning(_t("academic_progress.errors.missing_info", default="Missing Info"),
                                 _t("academic_progress.messages.please_enter_program_code", default="Please enter a program code."))
            return

        student_id = self.auth.get_current_user()['id']

        try:
            forecast = self.service.forecast_graduation(student_id, program_code)

            self.forecast_text.delete('1.0', tk.END)

            self.forecast_text.insert(tk.END, "═" * 80 + "\n", 'header')
            self.forecast_text.insert(tk.END, f"  GRADUATION FORECAST - {program_code}\n".center(80), 'header')
            self.forecast_text.insert(tk.END, "═" * 80 + "\n\n", 'header')

            # Status
            on_track_text = "✓ ON TRACK" if forecast['on_track'] else "⚠ DELAYED"
            status_tag = 'positive' if forecast['on_track'] else 'negative'
            self.forecast_text.insert(tk.END, f"Status: {on_track_text}\n\n", status_tag)

            # Timeline
            self.forecast_text.insert(tk.END, f"Estimated Graduation: {forecast['estimated_semester']}\n", 'bold')
            self.forecast_text.insert(tk.END, f"  ({forecast['estimated_graduation_date']})\n\n")

            # Requirements
            self.forecast_text.insert(tk.END, "REMAINING REQUIREMENTS:\n", 'bold')
            self.forecast_text.insert(tk.END, f"  Credits Remaining:      {forecast['remaining_credits']}\n")
            self.forecast_text.insert(tk.END, f"  Semesters Needed:       {forecast['semesters_needed']}\n")
            self.forecast_text.insert(tk.END, f"  Avg Credits/Semester:   {forecast['avg_credits_per_semester']:.1f}\n")
            self.forecast_text.insert(tk.END, f"  Confidence Level:       {forecast['confidence_level']*100:.0f}%\n\n")

            # Delays
            if forecast['delay_reasons']:
                self.forecast_text.insert(tk.END, "⚠ POTENTIAL DELAY FACTORS:\n", 'warning')
                for reason in forecast['delay_reasons']:
                    self.forecast_text.insert(tk.END, f"  • {reason}\n")
                self.forecast_text.insert(tk.END, "\n")

            # Acceleration
            if forecast['acceleration_options']:
                self.forecast_text.insert(tk.END, "💡 ACCELERATION OPTIONS:\n", 'bold')
                for option in forecast['acceleration_options']:
                    self.forecast_text.insert(tk.END, f"\n  {option['option']}\n", 'option')
                    self.forecast_text.insert(tk.END, f"    Impact: {option['impact']}\n")
                    self.forecast_text.insert(tk.END, f"    Credits: {option['credits']}\n")

            # Configure tags
            self.forecast_text.tag_config('header', font=('Arial', 11, 'bold'))
            self.forecast_text.tag_config('bold', font=('Arial', 10, 'bold'))
            self.forecast_text.tag_config('positive', font=('Arial', 11, 'bold'), foreground='green')
            self.forecast_text.tag_config('negative', font=('Arial', 11, 'bold'), foreground='orange')
            self.forecast_text.tag_config('warning', font=('Arial', 10, 'bold'), foreground='red')
            self.forecast_text.tag_config('option', font=('Arial', 10, 'bold'), foreground='blue')

        except Exception as e:
            messagebox.showerror(_t('gui.assessment.academic_progress.progress_gui_parts.academicprogressgui_create_warnings_tab.dialogs.error', default="Error"), f"Failed to generate forecast: {str(e)}")

    @staticmethod
    def _to_letter(grade):
        if grade is None:
            return 'N/A'
        try:
            numeric = float(grade)
            for threshold, letter in AcademicProgressGUI._LETTER_THRESHOLDS:
                if numeric >= threshold:
                    return letter
            return 'F'
        except (ValueError, TypeError):
            return str(grade)

    @staticmethod
    def _gpa_points(grade):
        if letter_to_gpa is not None:
            letter = AcademicProgressGUI._to_letter(grade)
            return letter_to_gpa(letter)
        return 0.0

    @staticmethod
    def _format_grade(grade):
        if grade is None:
            return "N/A"
        if isinstance(grade, (int, float)):
            return f"{grade:.1f}"
        return str(grade)

    def _get_student_id(self):
        if self.auth and hasattr(self.auth, 'current_user') and self.auth.current_user:
            u = self.auth.current_user
            if isinstance(u, dict):
                return u.get('student_id') or u.get('user_id') or u.get('id')
            return getattr(u, 'student_id', getattr(u, 'user_id', getattr(u, 'id', None)))
        return None

    def create_my_grades_tab(self):
        """Create the My Grades tab with detailed grade table."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t("academic_progress.tabs.my_grades", default="My Grades"))

        header = ttk.Frame(tab)
        header.pack(fill=tk.X, padx=10, pady=(10, 0))
        ttk.Label(header, text=_t('gui.assessment.academic_progress.progress_gui_parts.academicprogressgui_create_warnings_tab.labels.my_grades', default="My Grades"), font=('Arial', 14, 'bold')).pack(side='left')
        ttk.Button(header, text=_t('gui.assessment.academic_progress.progress_gui_parts.academicprogressgui_create_warnings_tab.buttons.refresh', default="Refresh"), command=self._populate_grades_tree).pack(side='right')

        columns = ('Module Code', 'Module Name', 'Grade', 'Letter Grade', 'GPA Points')
        col_widths = {'Module Code': 120, 'Module Name': 250, 'Grade': 80,
                      'Letter Grade': 100, 'GPA Points': 100}

        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill='both', expand=True, padx=10, pady=10)

        self._grades_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=15)
        for col in columns:
            self._grades_tree.heading(col, text=col)
            self._grades_tree.column(col, width=col_widths.get(col, 100), anchor='w')

        vsb = ttk.Scrollbar(tree_frame, orient='vertical', command=self._grades_tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient='horizontal', command=self._grades_tree.xview)
        self._grades_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self._grades_tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        self._populate_grades_tree()

    def _populate_grades_tree(self):
        """Fetch grades and populate the grades Treeview."""
        for item in self._grades_tree.get_children():
            self._grades_tree.delete(item)

        student_id = self._get_student_id()
        if not student_id:
            self._grades_tree.insert('', 'end', values=('--', 'Not logged in', '--', '--', '--'))
            return

        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    '''SELECT mg.module_code, m.module_name, mg.final_grade
                       FROM module_grades mg
                       JOIN modules m ON mg.module_code = m.module_code
                       WHERE mg.student_id = ?''',
                    (student_id,),
                )
                module_rows = cursor.fetchall()

                cursor.execute(
                    '''SELECT a.module_code, a.title, sub.grade
                       FROM assignment_submissions sub
                       JOIN assignments a ON sub.assignment_id = a.id
                       WHERE sub.student_id = ? AND sub.grade IS NOT NULL
                       ORDER BY sub.graded_date DESC''',
                    (student_id,),
                )
                assignment_rows = cursor.fetchall()

            all_rows = list(module_rows) + list(assignment_rows)
            if not all_rows:
                self._grades_tree.insert('', 'end', values=('--', 'No grades found', '--', '--', '--'))
                return

            for code, name, grade in all_rows:
                letter = self._to_letter(grade)
                points = self._gpa_points(grade)
                self._grades_tree.insert('', 'end', values=(
                    code, name, self._format_grade(grade), letter, f'{points:.2f}',
                ))
        except Exception as e:
            self._grades_tree.insert('', 'end', values=('--', f'Error: {e}', '--', '--', '--'))

    def create_transcript_tab(self):
        """Create the Transcript tab with exportable academic record."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t("academic_progress.tabs.transcript", default="Transcript"))

        header = ttk.Frame(tab)
        header.pack(fill=tk.X, padx=10, pady=(10, 0))
        ttk.Label(header, text=_t('gui.assessment.academic_progress.progress_gui_parts.academicprogressgui_create_warnings_tab.labels.academic_transcript', default="Academic Transcript"), font=('Arial', 14, 'bold')).pack(side='left')
        ttk.Button(header, text=_t('gui.assessment.academic_progress.progress_gui_parts.academicprogressgui_create_warnings_tab.buttons.export', default="Export"), command=self._export_transcript).pack(side='right')

        self._transcript_text = scrolledtext.ScrolledText(
            tab, wrap='word', font=('Courier', 10), state='disabled',
        )
        self._transcript_text.pack(fill='both', expand=True, padx=10, pady=10)

        self._render_transcript()
