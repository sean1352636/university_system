"""Methods _render_transcript through run."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import progress_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class AcademicProgressGUI:
    def _render_transcript(self):
        text = self._build_transcript_text()
        self._transcript_text.configure(state='normal')
        self._transcript_text.delete('1.0', 'end')
        self._transcript_text.insert('1.0', text)
        self._transcript_text.configure(state='disabled')

    def _build_transcript_text(self) -> str:
        lines = []
        sep = '=' * 60
        student_id = self._get_student_id()

        # Student name
        student_name = str(student_id)
        try:
            with get_connection() as conn:
                row = conn.execute(
                    "SELECT first_name, middle_name, last_name FROM students WHERE student_id = ?",
                    (student_id,),
                ).fetchone()
                if row:
                    first, middle, last = row
                    middle_str = f' {middle} ' if middle else ' '
                    student_name = f'{first}{middle_str}{last}'
        except Exception:
            pass

        lines.append(sep)
        lines.append('ACADEMIC TRANSCRIPT')
        lines.append(sep)
        lines.append(f'Student: {student_name}')
        lines.append(f'Student ID: {student_id}')
        lines.append(f'Date: {datetime.now().strftime("%Y-%m-%d")}')
        lines.append(sep)
        lines.append('')

        lines.append(f'{"Module Code":<14} {"Module Name":<30} {"Grade":<10} {"Letter":<10} {"Points":<8}')
        lines.append('-' * 72)

        gpa = None
        total_modules = 0
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

            rows = list(module_rows) + list(assignment_rows)
            if not rows:
                lines.append('No grade records found.')
            else:
                total_points = 0.0
                for code, name, grade in rows:
                    letter = self._to_letter(grade)
                    points = self._gpa_points(grade)
                    total_points += points
                    total_modules += 1
                    lines.append(
                        f'{code:<14} {name:<30} {self._format_grade(grade):<10} {letter:<10} {points:<8.2f}'
                    )
                if total_modules > 0:
                    gpa = total_points / total_modules
        except Exception as e:
            lines.append(f'Error retrieving grades: {e}')

        lines.append('')
        lines.append('-' * 72)
        lines.append(f'Total Modules: {total_modules}')
        lines.append(f'Cumulative GPA: {gpa:.2f}' if gpa is not None else 'Cumulative GPA: N/A')
        lines.append(sep)
        return '\n'.join(lines)

    def _export_transcript(self):
        from tkinter import filedialog
        student_id = self._get_student_id()
        filepath = filedialog.asksaveasfilename(
            defaultextension='.txt',
            filetypes=[('Text files', '*.txt'), ('All files', '*.*')],
            initialfile=f'transcript_{student_id}.txt',
        )
        if not filepath:
            return
        try:
            text = self._build_transcript_text()
            with open(filepath, 'w', encoding='utf-8') as fh:
                fh.write(text)
            messagebox.showinfo(_t('gui.assessment.academic_progress.progress_gui_parts.academicprogressgui_render_transcript.dialogs.export_successful', default='Export Successful'), f'Transcript saved to:\n{filepath}')
        except Exception as e:
            messagebox.showerror(_t('gui.assessment.academic_progress.progress_gui_parts.academicprogressgui_render_transcript.dialogs.export_error', default='Export Error'), f'Failed to save transcript: {e}')

    def create_analytics_report_tab(self):
        """Create analytics & comprehensive report tab."""
        analytics_tab = ttk.Frame(self.notebook)
        self.notebook.add(analytics_tab, text=_t("academic_progress.tabs.analytics", default="📊 Analytics & Report"))

        # Program selector (needed for comprehensive report)
        selector_frame = ttk.Frame(analytics_tab)
        selector_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(selector_frame, text=_t("academic_progress.labels.program_code", default="Program Code:"),
                  font=('Arial', 10, 'bold')).pack(side=tk.LEFT, padx=5)
        self.analytics_program_var = tk.StringVar()

        try:
            available_programs = self.service.get_available_programs()
            program_codes = [p['program_code'] for p in available_programs]
            program_combo = ttk.Combobox(selector_frame, textvariable=self.analytics_program_var,
                                         values=program_codes, width=15, state='readonly')
            program_combo.pack(side=tk.LEFT, padx=5)
        except Exception:
            ttk.Entry(selector_frame, textvariable=self.analytics_program_var, width=15).pack(side=tk.LEFT, padx=5)

        ttk.Button(selector_frame, text=_t('gui.assessment.academic_progress.progress_gui_parts.academicprogressgui_render_transcript.buttons.view_progress_analytics', default="View Progress Analytics"),
                   command=self.view_progress_analytics).pack(side=tk.LEFT, padx=5)
        ttk.Button(selector_frame, text=_t('gui.assessment.academic_progress.progress_gui_parts.academicprogressgui_render_transcript.buttons.comprehensive_progress_report', default="Comprehensive Progress Report"),
                   command=self.generate_comprehensive_report).pack(side=tk.LEFT, padx=5)

        self.analytics_text = scrolledtext.ScrolledText(analytics_tab, height=30, wrap=tk.WORD)
        self.analytics_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Configure tags once
        self.analytics_text.tag_config('header', font=('Arial', 11, 'bold'))
        self.analytics_text.tag_config('bold', font=('Arial', 10, 'bold'))
        self.analytics_text.tag_config('separator', foreground='gray')
        self.analytics_text.tag_config('section', font=('Arial', 10, 'bold'), foreground='blue')
        self.analytics_text.tag_config('positive', foreground='green', font=('Arial', 10, 'bold'))
        self.analytics_text.tag_config('warning', foreground='red', font=('Arial', 10, 'bold'))

    def view_progress_analytics(self):
        """Display progress analytics (mirrors CLI view_progress_analytics)."""
        student_id = self.auth.get_current_user()['id']

        try:
            analytics = self.service.get_progress_analytics(student_id)

            self.analytics_text.delete('1.0', tk.END)

            self.analytics_text.insert(tk.END, "═" * 80 + "\n", 'header')
            self.analytics_text.insert(tk.END, "  PROGRESS ANALYTICS\n".center(80), 'header')
            self.analytics_text.insert(tk.END, "═" * 80 + "\n\n", 'header')

            stats = analytics['current_stats']
            self.analytics_text.insert(tk.END, "CURRENT STATS\n", 'section')
            self.analytics_text.insert(tk.END, f"  Current GPA:   {stats['current_gpa']:.3f}\n")
            self.analytics_text.insert(tk.END, f"  Total Credits: {stats['total_credits']}\n")
            self.analytics_text.insert(tk.END, f"  Total Points:  {stats['total_points']:.2f}\n\n")

            if analytics.get('gpa_trend'):
                self.analytics_text.insert(tk.END, "GPA TREND (Last 8 Semesters)\n", 'section')
                for entry in analytics['gpa_trend']:
                    self.analytics_text.insert(tk.END, f"  {entry['semester']}: {entry['semester_gpa']:.2f}\n")
                self.analytics_text.insert(tk.END, "\n")

            if analytics.get('warning_stats'):
                w_stats = analytics['warning_stats']
                self.analytics_text.insert(tk.END, "WARNING STATISTICS\n", 'section')
                self.analytics_text.insert(tk.END, f"  Total Warnings:         {w_stats.get('total_warnings', 0)}\n")
                self.analytics_text.insert(tk.END, f"  Resolved Warnings:      {w_stats.get('resolved_count', 0)}\n")
                self.analytics_text.insert(tk.END, f"  High Severity Warnings: {w_stats.get('high_severity_count', 0)}\n\n")

            self.analytics_text.insert(tk.END, f"Last Updated: {analytics['last_updated']}\n")

        except Exception as e:
            messagebox.showerror(_t("academic_progress.errors.error", default="Error"),
                                 f"Failed to load analytics: {str(e)}")

    def generate_comprehensive_report(self):
        """Generate the 6-section comprehensive progress report (mirrors CLI)."""
        program_code = self.analytics_program_var.get().strip().upper()
        if not program_code:
            messagebox.showwarning(_t("academic_progress.errors.missing_info", default="Missing Info"),
                                   _t("academic_progress.messages.please_enter_program_code", default="Please enter a program code."))
            return

        student_id = self.auth.get_current_user()['id']

        try:
            progress = self.service.calculate_degree_progress(student_id, program_code)
            milestones = self.service.track_milestones(student_id, program_code)
            forecast = self.service.forecast_graduation(student_id, program_code)
            warnings = self.service.get_active_warnings(student_id)
            analytics = self.service.get_progress_analytics(student_id)

            t = self.analytics_text
            t.delete('1.0', tk.END)

            t.insert(tk.END, "═" * 80 + "\n", 'header')
            t.insert(tk.END, "  COMPREHENSIVE PROGRESS REPORT\n".center(80), 'header')
            t.insert(tk.END, f"  Student ID: {student_id} | Program: {program_code}\n".center(80), 'header')
            t.insert(tk.END, f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n".center(80), 'header')
            t.insert(tk.END, "═" * 80 + "\n\n", 'header')

            # Section 1: Degree Progress
            t.insert(tk.END, "─" * 80 + "\n", 'separator')
            t.insert(tk.END, "1. DEGREE PROGRESS\n", 'section')
            t.insert(tk.END, "─" * 80 + "\n", 'separator')
            t.insert(tk.END, f"Overall Completion: {progress['overall_completion']:.1f}%\n")
            t.insert(tk.END, f"Credits: {progress['total_credits_completed']}/{progress['total_credits_required']} "
                             f"(Remaining: {progress['total_credits_remaining']})\n\n")

            # Section 2: Academic Standing
            t.insert(tk.END, "─" * 80 + "\n", 'separator')
            t.insert(tk.END, "2. ACADEMIC STANDING\n", 'section')
            t.insert(tk.END, "─" * 80 + "\n", 'separator')
            stats = analytics['current_stats']
            t.insert(tk.END, f"Current GPA: {stats['current_gpa']:.3f}\n")
            t.insert(tk.END, f"Total Credits: {stats['total_credits']}\n")
            standing = self.service._determine_class_standing(stats['total_credits'])
            t.insert(tk.END, f"Class Standing: {standing}\n\n")

            # Section 3: Milestones
            t.insert(tk.END, "─" * 80 + "\n", 'separator')
            t.insert(tk.END, "3. MILESTONE PROGRESS\n", 'section')
            t.insert(tk.END, "─" * 80 + "\n", 'separator')
            achieved = sum(1 for m in milestones['milestones'] if m['achieved'])
            total_milestones = len(milestones['milestones'])
            t.insert(tk.END, f"Milestones Achieved: {achieved}/{total_milestones}\n\n")

            # Section 4: Graduation Forecast
            t.insert(tk.END, "─" * 80 + "\n", 'separator')
            t.insert(tk.END, "4. GRADUATION FORECAST\n", 'section')
            t.insert(tk.END, "─" * 80 + "\n", 'separator')
            status = "On Track ✓" if forecast['on_track'] else "Delayed ⚠"
            t.insert(tk.END, f"Status: {status}\n")
            t.insert(tk.END, f"Estimated Graduation: {forecast['estimated_semester']}\n")
            t.insert(tk.END, f"Semesters Remaining: {forecast['semesters_needed']}\n\n")

            # Section 5: Warnings
            t.insert(tk.END, "─" * 80 + "\n", 'separator')
            t.insert(tk.END, "5. ACTIVE WARNINGS\n", 'section')
            t.insert(tk.END, "─" * 80 + "\n", 'separator')
            if warnings:
                t.insert(tk.END, f"Total Active Warnings: {len(warnings)}\n", 'warning')
                high_severity = sum(1 for w in warnings if w['severity'] == 'High')
                if high_severity > 0:
                    t.insert(tk.END, f"⚠ High Severity Warnings: {high_severity}\n", 'warning')
            else:
                t.insert(tk.END, "No active warnings ✓\n", 'positive')
            t.insert(tk.END, "\n")

            # Section 6: Recommendations
            t.insert(tk.END, "─" * 80 + "\n", 'separator')
            t.insert(tk.END, "6. RECOMMENDATIONS\n", 'section')
            t.insert(tk.END, "─" * 80 + "\n", 'separator')
            if warnings:
                t.insert(tk.END, "• Address active academic warnings\n")
            if not forecast['on_track']:
                t.insert(tk.END, "• Consider acceleration options to get back on track\n")
            if stats['current_gpa'] < 3.0:
                t.insert(tk.END, "• Focus on improving GPA through tutoring and study support\n")
            if forecast['on_track'] and not warnings:
                t.insert(tk.END, "• Continue current academic trajectory\n")
                t.insert(tk.END, "• Consider challenging yourself with advanced courses\n")

            t.insert(tk.END, "\n" + "═" * 80 + "\n", 'header')
            t.insert(tk.END, "  END OF REPORT\n".center(80), 'header')
            t.insert(tk.END, "═" * 80 + "\n", 'header')

        except Exception as e:
            messagebox.showerror(_t("academic_progress.errors.error", default="Error"),
                                 f"Failed to generate report: {str(e)}")

    def create_history_tab(self):
        """Create progress history tab."""
        history_tab = ttk.Frame(self.notebook)
        self.notebook.add(history_tab, text=_t("academic_progress.tabs.history", default="📜 History"))

        button_frame = ttk.Frame(history_tab)
        button_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(button_frame, text=_t('gui.assessment.academic_progress.progress_gui_parts.academicprogressgui_render_transcript.buttons.load_progress_history', default="Load Progress History"),
                  command=self.load_progress_history).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_t('gui.assessment.academic_progress.progress_gui_parts.academicprogressgui_render_transcript.buttons.create_snapshot', default="Create Snapshot"),
                  command=self.create_snapshot_gui).pack(side=tk.LEFT, padx=5)

        self.history_text = scrolledtext.ScrolledText(history_tab, height=30, wrap=tk.WORD)
        self.history_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    def load_progress_history(self):
        """Load progress history."""
        student_id = self.auth.get_current_user()['id']

        try:
            history = self.service.get_progress_history(student_id)

            self.history_text.delete('1.0', tk.END)

            self.history_text.insert(tk.END, "═" * 80 + "\n", 'header')
            self.history_text.insert(tk.END, "  PROGRESS HISTORY\n".center(80), 'header')
            self.history_text.insert(tk.END, "═" * 80 + "\n\n", 'header')

            if not history:
                self.history_text.insert(tk.END, "No progress history found.\n")
                return

            self.history_text.insert(tk.END, f"Total Snapshots: {len(history)}\n\n")

            for snapshot in history:
                self.history_text.insert(tk.END, "─" * 80 + "\n", 'separator')
                self.history_text.insert(tk.END, f"Semester: {snapshot['semester']}\n", 'bold')
                self.history_text.insert(tk.END, f"  Overall GPA:     {snapshot['overall_gpa']:.2f}\n")
                self.history_text.insert(tk.END, f"  Semester GPA:    {snapshot['semester_gpa']:.2f}\n")
                self.history_text.insert(tk.END, f"  Total Credits:   {snapshot['total_credits']}\n")
                self.history_text.insert(tk.END, f"  Class Standing:  {snapshot['class_standing']}\n")
                self.history_text.insert(tk.END, f"  Academic Status: {snapshot['academic_status']}\n")
                self.history_text.insert(tk.END, f"  Active Warnings: {snapshot['warnings_count']}\n")
                self.history_text.insert(tk.END, f"  Date: {snapshot['snapshot_date']}\n\n")

            # Configure tags
            self.history_text.tag_config('header', font=('Arial', 11, 'bold'))
            self.history_text.tag_config('bold', font=('Arial', 10, 'bold'))
            self.history_text.tag_config('separator', foreground='gray')

        except Exception as e:
            messagebox.showerror(_t('gui.assessment.academic_progress.progress_gui_parts.academicprogressgui_render_transcript.dialogs.error', default="Error"), f"Failed to load progress history: {str(e)}")

    def create_snapshot_gui(self):
        """Create a progress snapshot."""
        semester = tk.simpledialog.askstring("Create Snapshot",
                                            "Enter semester (e.g., Fall 2025):")
        if not semester:
            return

        student_id = self.auth.get_current_user()['id']

        try:
            snapshot_id = self.service.create_progress_snapshot(student_id, semester)
            messagebox.showinfo(_t('gui.assessment.academic_progress.progress_gui_parts.academicprogressgui_render_transcript.dialogs.success', default="Success"),
                               f"Progress snapshot created successfully!\nSnapshot ID: {snapshot_id}")
            self.load_progress_history()
        except Exception as e:
            messagebox.showerror(_t('gui.assessment.academic_progress.progress_gui_parts.academicprogressgui_render_transcript.dialogs.error', default="Error"), f"Failed to create snapshot: {str(e)}")

    def run(self):
        """Run the GUI application."""
        self.root.mainloop()
