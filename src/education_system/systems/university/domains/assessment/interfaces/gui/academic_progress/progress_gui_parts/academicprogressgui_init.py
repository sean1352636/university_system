"""Methods __init__ through calculate_progress."""

from .. import progress_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class AcademicProgressGUI:
    def __init__(self, parent=None, auth=None):
        """Initialize the Academic Progress GUI."""
        self.service = ProgressService()
        self.auth = auth or get_auth()

        if parent:
            self.root = tk.Toplevel(parent)
        else:
            self.root = tk.Tk()

        self.root.title(_t("academic_progress.window_title", default="Academic Progress Dashboard"))
        self.root.geometry("1400x900")

        # Store references for refresh
        self.current_program_code = None

        self.setup_ui()

    def setup_ui(self):
        """Set up the user interface."""
        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Check if user is logged in
        if not self.auth.current_user:
            ttk.Label(main_frame, text=_t("academic_progress.messages.login_required", default="Please log in to access academic progress features."),
                     font=('Arial', 14)).grid(row=0, column=0, pady=20)
            return

        # Status header
        self.create_status_header(main_frame)

        # Create notebook for different sections
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)

        # Create tabs
        self.create_overview_tab()
        self.create_my_grades_tab()
        self.create_transcript_tab()
        self.create_degree_progress_tab()
        self.create_milestones_tab()
        self.create_gpa_calculator_tab()
        self.create_warnings_tab()
        self.create_forecast_tab()
        self.create_analytics_report_tab()
        self.create_history_tab()

        # Configure grid weights
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

    def create_status_header(self, parent):
        """Create status header with quick info."""
        header_frame = ttk.LabelFrame(parent, text=_t("academic_progress.labels.quick_status", default="Quick Status"), padding="10")
        header_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

        student_id = self.auth.get_current_user()['id']

        try:
            # Get current stats
            gpa_stats = self.service._calculate_current_gpa(student_id)
            warnings = self.service.get_active_warnings(student_id)

            # Display info
            info_frame = ttk.Frame(header_frame)
            info_frame.pack(fill=tk.X)

            gpa_text = _t("academic_progress.labels.gpa", default="GPA: {gpa}").format(gpa=f"{gpa_stats['current_gpa']:.3f}")
            ttk.Label(info_frame, text=gpa_text,
                     font=('Arial', 11, 'bold')).pack(side=tk.LEFT, padx=10)

            credits_text = _t("academic_progress.labels.credits", default="Credits: {credits}").format(credits=gpa_stats['total_credits'])
            ttk.Label(info_frame, text=credits_text,
                     font=('Arial', 11)).pack(side=tk.LEFT, padx=10)

            standing = self.service._determine_class_standing(gpa_stats['total_credits'])
            standing_text = _t("academic_progress.labels.standing", default="Standing: {standing}").format(standing=standing)
            ttk.Label(info_frame, text=standing_text,
                     font=('Arial', 11)).pack(side=tk.LEFT, padx=10)

            warning_color = 'red' if len(warnings) > 0 else 'green'
            warning_text = _t("academic_progress.labels.active_warnings", default="⚠ {count} Active Warnings").format(count=len(warnings)) if warnings else _t("academic_progress.labels.no_warnings", default="✓ No Warnings")
            warning_label = ttk.Label(info_frame, text=warning_text, font=('Arial', 11, 'bold'))
            warning_label.pack(side=tk.LEFT, padx=10)

        except Exception:
            ttk.Label(header_frame, text=_t("academic_progress.labels.unable_to_load_status", default="Unable to load status")).pack()

    def create_overview_tab(self):
        """Create overview dashboard tab."""
        overview = ttk.Frame(self.notebook)
        self.notebook.add(overview, text=_t("academic_progress.tabs.overview", default="📊 Overview"))

        # Create scrollable frame
        canvas = tk.Canvas(overview)
        scrollbar = ttk.Scrollbar(overview, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Program selector
        selector_frame = ttk.Frame(scrollable_frame)
        selector_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(selector_frame, text=_t("academic_progress.labels.program_code", default="Program Code:"), font=('Arial', 10, 'bold')).pack(side=tk.LEFT, padx=5)
        self.overview_program_var = tk.StringVar()

        # Get available programs
        try:
            available_programs = self.service.get_available_programs()
            program_codes = [p['program_code'] for p in available_programs]

            if program_codes:
                program_combo = ttk.Combobox(selector_frame, textvariable=self.overview_program_var,
                                            values=program_codes, width=15, state='readonly')
                program_combo.pack(side=tk.LEFT, padx=5)
                if program_codes:
                    program_combo.current(0)  # Select first program by default
            else:
                ttk.Label(selector_frame, text=_t("academic_progress.labels.no_programs_configured", default="No programs with courses configured"),
                         foreground='red').pack(side=tk.LEFT, padx=5)
        except Exception:
            # Fallback to entry field if error getting programs
            program_entry = ttk.Entry(selector_frame, textvariable=self.overview_program_var, width=15)
            program_entry.pack(side=tk.LEFT, padx=5)

        ttk.Button(selector_frame, text=_t("academic_progress.buttons.load_progress", default="Load Progress"),
                  command=self.load_overview).pack(side=tk.LEFT, padx=5)

        # Overview content frame
        self.overview_content = ttk.Frame(scrollable_frame)
        self.overview_content.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def load_overview(self):
        """Load overview dashboard."""
        program_code = self.overview_program_var.get().strip().upper()
        if not program_code:
            messagebox.showwarning(_t("academic_progress.errors.missing_info", default="Missing Info"),
                                 _t("academic_progress.messages.please_enter_program_code", default="Please enter a program code."))
            return

        self.current_program_code = program_code
        student_id = self.auth.get_current_user()['id']

        # Clear existing content
        for widget in self.overview_content.winfo_children():
            widget.destroy()

        try:
            # Get all data
            progress = self.service.calculate_degree_progress(student_id, program_code)
            milestones = self.service.track_milestones(student_id, program_code)
            forecast = self.service.forecast_graduation(student_id, program_code)
            warnings = self.service.get_active_warnings(student_id)

            # Create overview sections
            # 1. Degree Progress Card
            progress_card = ttk.LabelFrame(self.overview_content, text=_t("academic_progress.labels.degree_progress", default="Degree Progress"), padding="10")
            progress_card.pack(fill=tk.X, pady=(0, 10))

            program_text = _t("academic_progress.labels.program", default="Program: {program}").format(program=program_code)
            ttk.Label(progress_card, text=program_text,
                     font=('Arial', 11, 'bold')).pack(anchor=tk.W)

            completion_frame = ttk.Frame(progress_card)
            completion_frame.pack(fill=tk.X, pady=5)
            completion_text = _t("academic_progress.labels.overall_completion", default="Overall Completion: {percent}%").format(percent=f"{progress['overall_completion']:.1f}")
            ttk.Label(completion_frame, text=completion_text,
                     font=('Arial', 10)).pack(side=tk.LEFT)

            # Progress bar
            progress_bar = ttk.Progressbar(progress_card, length=400, mode='determinate')
            progress_bar['value'] = progress['overall_completion']
            progress_bar.pack(fill=tk.X, pady=5)

            completed_text = _t("academic_progress.labels.completed", default="Completed: {count}").format(count=progress['total_credits_completed'])
            in_progress_text = _t("academic_progress.labels.in_progress", default="In Progress: {count}").format(count=progress['total_credits_in_progress'])
            remaining_text = _t("academic_progress.labels.remaining", default="Remaining: {count} of {total}").format(count=progress['total_credits_remaining'], total=progress['total_credits_required'])
            credits_text = f"{completed_text} | {in_progress_text} | {remaining_text}"
            ttk.Label(progress_card, text=credits_text).pack(anchor=tk.W)

            # 2. Graduation Forecast Card
            forecast_card = ttk.LabelFrame(self.overview_content, text=_t("academic_progress.labels.graduation_forecast", default="Graduation Forecast"), padding="10")
            forecast_card.pack(fill=tk.X, pady=(0, 10))

            on_track_status = _t("academic_progress.labels.on_track", default="✓ On Track") if forecast['on_track'] else _t("academic_progress.labels.delayed", default="⚠ Delayed")
            on_track_color = 'green' if forecast['on_track'] else 'orange'

            status_frame = ttk.Frame(forecast_card)
            status_frame.pack(fill=tk.X)
            status_text = _t("academic_progress.labels.status", default="Status: {status}").format(status=on_track_status)
            ttk.Label(status_frame, text=status_text,
                     font=('Arial', 10, 'bold')).pack(side=tk.LEFT)

            estimated_grad_text = _t("academic_progress.labels.estimated_graduation", default="Estimated Graduation: {semester}").format(semester=forecast['estimated_semester'])
            ttk.Label(forecast_card, text=estimated_grad_text,
                     font=('Arial', 10)).pack(anchor=tk.W, pady=2)
            semesters_text = _t("academic_progress.labels.semesters_remaining", default="Semesters Remaining: {count}").format(count=forecast['semesters_needed'])
            ttk.Label(forecast_card, text=semesters_text).pack(anchor=tk.W)

            # 3. Milestones Card
            milestones_card = ttk.LabelFrame(self.overview_content, text=_t("academic_progress.labels.milestone_progress", default="Milestone Progress"), padding="10")
            milestones_card.pack(fill=tk.X, pady=(0, 10))

            achieved = sum(1 for m in milestones['milestones'] if m['achieved'])
            total = len(milestones['milestones'])

            achieved_text = _t("academic_progress.labels.achieved_milestones", default="Achieved: {achieved}/{total} milestones").format(achieved=achieved, total=total)
            ttk.Label(milestones_card, text=achieved_text,
                     font=('Arial', 10)).pack(anchor=tk.W)

            milestone_bar = ttk.Progressbar(milestones_card, length=400, mode='determinate')
            milestone_bar['value'] = (achieved / total * 100) if total > 0 else 0
            milestone_bar.pack(fill=tk.X, pady=5)

            # 4. Warnings Card
            warnings_card = ttk.LabelFrame(self.overview_content, text=_t("academic_progress.labels.academic_warnings", default="Academic Warnings"), padding="10")
            warnings_card.pack(fill=tk.X, pady=(0, 10))

            if warnings:
                warning_count_text = _t("academic_progress.labels.active_warning_count", default="⚠ {count} Active Warning(s)").format(count=len(warnings))
                ttk.Label(warnings_card, text=warning_count_text,
                         font=('Arial', 10, 'bold'), foreground='red').pack(anchor=tk.W)

                high_severity = sum(1 for w in warnings if w['severity'] == 'High')
                if high_severity > 0:
                    high_severity_text = _t("academic_progress.labels.including_high_severity", default="Including {count} high severity").format(count=high_severity)
                    ttk.Label(warnings_card, text=high_severity_text,
                             foreground='red').pack(anchor=tk.W)

                ttk.Button(warnings_card, text=_t("academic_progress.buttons.view_warnings", default="View Warnings"),
                          command=lambda: self.notebook.select(4)).pack(anchor=tk.W, pady=5)
            else:
                ttk.Label(warnings_card, text=_t("academic_progress.labels.no_active_warnings", default="✓ No Active Warnings"),
                         font=('Arial', 10), foreground='green').pack(anchor=tk.W)

            # 5. Progress Chart
            self.create_progress_chart(self.overview_content, progress)

        except ValueError as e:
            # Show helpful error message for validation failures
            error_msg = str(e)
            if "has no courses configured" in error_msg or "does not exist" in error_msg:
                available_programs = self.service.get_available_programs()
                if available_programs:
                    prog_list = "\n".join([f"  • {p['program_code']}: {p['program_name']} ({p['course_count']} courses)"
                                          for p in available_programs[:5]])
                    error_text = _t("academic_progress.errors.program_error_with_list", default="{error}\n\nAvailable programs:\n{programs}").format(error=error_msg, programs=prog_list)
                    messagebox.showerror(_t("academic_progress.errors.invalid_program", default="Invalid Program"),
                                       error_text)
                else:
                    error_text = _t("academic_progress.errors.program_has_no_courses", default="{error}\n\nNo programs have courses configured yet.").format(error=error_msg)
                    messagebox.showerror(_t("academic_progress.errors.invalid_program", default="Invalid Program"),
                                       error_text)
            else:
                messagebox.showerror(_t("academic_progress.errors.error", default="Error"), error_msg)
        except Exception as e:
            error_text = _t("academic_progress.errors.failed_to_load_overview", default="Failed to load overview: {error}").format(error=str(e))
            messagebox.showerror(_t("academic_progress.errors.error", default="Error"), error_text)

    def create_progress_chart(self, parent, progress):
        """Create progress visualization chart."""
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        from matplotlib.figure import Figure
        chart_frame = ttk.LabelFrame(parent, text=_t("academic_progress.labels.progress_by_category", default="Progress by Category"), padding="10")
        chart_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        fig = Figure(figsize=(10, 5), dpi=80)
        ax = fig.add_subplot(111)

        categories = list(progress['by_category'].keys())
        completed = [progress['by_category'][cat]['completed'] for cat in categories]
        in_progress = [progress['by_category'][cat]['in_progress'] for cat in categories]
        remaining = [progress['by_category'][cat]['remaining'] for cat in categories]

        x = range(len(categories))
        width = 0.25

        ax.bar([i - width for i in x], completed, width, label='Completed', color='#2ecc71')
        ax.bar(x, in_progress, width, label='In Progress', color='#f39c12')
        ax.bar([i + width for i in x], remaining, width, label='Remaining', color='#e74c3c')

        ax.set_xlabel('Category')
        ax.set_ylabel('Credits')
        ax.set_title('Degree Progress by Category')
        ax.set_xticks(x)
        ax.set_xticklabels(categories, rotation=45, ha='right')
        ax.legend()
        ax.grid(True, alpha=0.3, axis='y')

        fig.tight_layout()

        canvas = FigureCanvasTkAgg(fig, chart_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def create_degree_progress_tab(self):
        """Create degree progress tab."""
        progress_tab = ttk.Frame(self.notebook)
        self.notebook.add(progress_tab, text=_t("academic_progress.tabs.degree_progress", default="🎓 Degree Progress"))

        # Program selector
        selector_frame = ttk.Frame(progress_tab)
        selector_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(selector_frame, text=_t("academic_progress.labels.program_code", default="Program Code:"), font=('Arial', 10, 'bold')).pack(side=tk.LEFT, padx=5)
        self.progress_program_var = tk.StringVar()

        # Get available programs
        try:
            available_programs = self.service.get_available_programs()
            program_codes = [p['program_code'] for p in available_programs]
            program_combo = ttk.Combobox(selector_frame, textvariable=self.progress_program_var,
                                        values=program_codes, width=15, state='readonly')
            program_combo.pack(side=tk.LEFT, padx=5)
        except Exception:
            ttk.Entry(selector_frame, textvariable=self.progress_program_var, width=15).pack(side=tk.LEFT, padx=5)

        ttk.Button(selector_frame, text=_t("academic_progress.buttons.calculate_progress", default="Calculate Progress"),
                  command=self.calculate_progress).pack(side=tk.LEFT, padx=5)

        # Results area
        self.progress_results = ReportPane(progress_tab, title=_t('academic_progress.tabs.degree_progress_title', default="Degree Progress"))
        self.progress_results.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    def calculate_progress(self):
        """Calculate and display degree progress."""
        program_code = self.progress_program_var.get().strip().upper()
        if not program_code:
            messagebox.showwarning(_t("academic_progress.errors.missing_info", default="Missing Info"),
                                 _t("academic_progress.messages.please_enter_program_code", default="Please enter a program code."))
            return

        student_id = self.auth.get_current_user()['id']

        try:
            progress = self.service.calculate_degree_progress(student_id, program_code)

            self.progress_results.delete('1.0', tk.END)

            # Header
            self.progress_results.insert(tk.END, "═" * 80 + "\n", 'header')
            self.progress_results.insert(tk.END, f"  DEGREE PROGRESS - {program_code}\n".center(80), 'header')
            self.progress_results.insert(tk.END, "═" * 80 + "\n\n", 'header')

            # Overall completion
            self.progress_results.insert(tk.END, f"OVERALL COMPLETION: {progress['overall_completion']:.1f}%\n\n", 'bold')

            # Credits summary
            self.progress_results.insert(tk.END, "CREDITS SUMMARY:\n", 'bold')
            self.progress_results.insert(tk.END, f"  Total Required:    {progress['total_credits_required']}\n")
            self.progress_results.insert(tk.END, f"  Completed:         {progress['total_credits_completed']}\n")
            self.progress_results.insert(tk.END, f"  In Progress:       {progress['total_credits_in_progress']}\n")
            self.progress_results.insert(tk.END, f"  Remaining:         {progress['total_credits_remaining']}\n\n")

            # By category
            self.progress_results.insert(tk.END, "─" * 80 + "\n", 'separator')
            self.progress_results.insert(tk.END, "PROGRESS BY CATEGORY\n", 'bold')
            self.progress_results.insert(tk.END, "─" * 80 + "\n\n", 'separator')

            for category, data in progress['by_category'].items():
                self.progress_results.insert(tk.END, f"{category}:\n", 'category')
                self.progress_results.insert(tk.END, f"  Required: {data['required']} | ")
                self.progress_results.insert(tk.END, f"Completed: {data['completed']} | ")
                self.progress_results.insert(tk.END, f"In Progress: {data['in_progress']} | ")
                self.progress_results.insert(tk.END, f"Remaining: {data['remaining']}\n")
                self.progress_results.insert(tk.END, f"  Completion: {data['completion_percentage']:.1f}%\n\n")

            self.progress_results.insert(tk.END, f"\nLast Updated: {progress['last_updated']}\n")

            # Configure tags
            self.progress_results.tag_config('header', font=('Arial', 11, 'bold'))
            self.progress_results.tag_config('bold', font=('Arial', 10, 'bold'))
            self.progress_results.tag_config('category', font=('Arial', 10, 'bold'), foreground='blue')
            self.progress_results.tag_config('separator', foreground='gray')

        except Exception as e:
            error_text = _t("academic_progress.errors.failed_to_calculate_progress", default="Failed to calculate progress: {error}").format(error=str(e))
            messagebox.showerror(_t("academic_progress.errors.error", default="Error"), error_text)
