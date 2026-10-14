"""Methods create_milestones_tab through load_sim_history."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import progress_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class AcademicProgressGUI:
    def create_milestones_tab(self):
        """Create milestones tracking tab."""
        milestones_tab = ttk.Frame(self.notebook)
        self.notebook.add(milestones_tab, text=_t("academic_progress.tabs.milestones", default="🎯 Milestones"))

        # Program selector
        selector_frame = ttk.Frame(milestones_tab)
        selector_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(selector_frame, text=_t("academic_progress.labels.program_code", default="Program Code:"), font=('Arial', 10, 'bold')).pack(side=tk.LEFT, padx=5)
        self.milestone_program_var = tk.StringVar()

        # Get available programs
        try:
            available_programs = self.service.get_available_programs()
            program_codes = [p['program_code'] for p in available_programs]
            program_combo = ttk.Combobox(selector_frame, textvariable=self.milestone_program_var,
                                        values=program_codes, width=15, state='readonly')
            program_combo.pack(side=tk.LEFT, padx=5)
        except Exception:
            ttk.Entry(selector_frame, textvariable=self.milestone_program_var, width=15).pack(side=tk.LEFT, padx=5)

        ttk.Button(selector_frame, text=_t("academic_progress.buttons.load_milestones", default="Load Milestones"),
                  command=self.load_milestones).pack(side=tk.LEFT, padx=5)

        # Milestones display
        self.milestones_frame = ttk.Frame(milestones_tab)
        self.milestones_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    def load_milestones(self):
        """Load and display milestones."""
        program_code = self.milestone_program_var.get().strip().upper()
        if not program_code:
            messagebox.showwarning(_t("academic_progress.errors.missing_info", default="Missing Info"),
                                 _t("academic_progress.messages.please_enter_program_code", default="Please enter a program code."))
            return

        student_id = self.auth.get_current_user()['id']

        # Clear existing
        for widget in self.milestones_frame.winfo_children():
            widget.destroy()

        try:
            milestone_data = self.service.track_milestones(student_id, program_code)

            # Stats card
            stats_frame = ttk.LabelFrame(self.milestones_frame, text=_t('gui.assessment.academic_progress.progress_gui_parts.academicprogressgui_create_milestones_tab.labels.your_current_stats', default="Your Current Stats"), padding="10")
            stats_frame.pack(fill=tk.X, pady=(0, 10))

            stats = milestone_data['student_stats']
            ttk.Label(stats_frame, text=f"Total Credits: {stats['total_credits']}",
                     font=('Arial', 10)).pack(anchor=tk.W)
            ttk.Label(stats_frame, text=f"Current GPA: {stats['gpa']:.2f}",
                     font=('Arial', 10)).pack(anchor=tk.W)

            # Milestones list
            achieved_count = 0
            for milestone_info in milestone_data['milestones']:
                milestone = milestone_info['milestone']
                achieved = milestone_info['achieved']

                if achieved:
                    achieved_count += 1

                milestone_frame = ttk.LabelFrame(self.milestones_frame,
                                                text=milestone['milestone_name'],
                                                padding="10")
                milestone_frame.pack(fill=tk.X, pady=(0, 10))

                # Status indicator
                status_text = "✓ ACHIEVED" if achieved else "○ Not Achieved"
                status_color = 'green' if achieved else 'gray'
                status_label = tk.Label(milestone_frame, text=status_text,
                                       font=('Arial', 11, 'bold'), fg=status_color)
                status_label.pack(anchor=tk.W)

                # Details
                ttk.Label(milestone_frame, text=f"Type: {milestone['milestone_type']}").pack(anchor=tk.W)
                ttk.Label(milestone_frame,
                         text=f"Requirements: {milestone['required_credits']} credits, "
                              f"{milestone['required_gpa']:.1f} GPA").pack(anchor=tk.W)
                ttk.Label(milestone_frame,
                         text=f"Typical Semester: {milestone['typical_semester']}").pack(anchor=tk.W)

                if milestone['description']:
                    ttk.Label(milestone_frame, text=f"Description: {milestone['description']}",
                             wraplength=600).pack(anchor=tk.W, pady=(5, 0))

            # Summary
            summary_frame = ttk.Frame(self.milestones_frame)
            summary_frame.pack(fill=tk.X, pady=(10, 0))
            total = len(milestone_data['milestones'])
            ttk.Label(summary_frame, text=f"Milestones Achieved: {achieved_count}/{total}",
                     font=('Arial', 11, 'bold')).pack()

        except Exception as e:
            error_text = _t("academic_progress.errors.failed_to_load_milestones", default="Failed to load milestones: {error}").format(error=str(e))
            messagebox.showerror(_t("academic_progress.errors.error", default="Error"), error_text)

    def create_gpa_calculator_tab(self):
        """Create GPA calculator tab."""
        gpa_tab = ttk.Frame(self.notebook)
        self.notebook.add(gpa_tab, text=_t("academic_progress.tabs.gpa_calculator", default="📈 GPA Calculator"))

        # Create two sub-tabs
        sub_notebook = ttk.Notebook(gpa_tab)
        sub_notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # What-If Calculator
        self.create_what_if_tab(sub_notebook)

        # Target GPA Calculator
        self.create_target_gpa_tab(sub_notebook)

        # Simulation History
        self.create_sim_history_tab(sub_notebook)

    def create_what_if_tab(self, parent):
        """Create what-if GPA calculator."""
        what_if_tab = ttk.Frame(parent)
        parent.add(what_if_tab, text=_t('gui.assessment.academic_progress.progress_gui_parts.academicprogressgui_create_milestones_tab.tabs.what_if_scenario', default="What-If Scenario"))

        # Input section
        input_frame = ttk.LabelFrame(what_if_tab, text=_t('gui.assessment.academic_progress.progress_gui_parts.academicprogressgui_create_milestones_tab.labels.simulation_setup', default="Simulation Setup"), padding="10")
        input_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(input_frame, text=_t('gui.assessment.academic_progress.progress_gui_parts.academicprogressgui_create_milestones_tab.labels.simulation_name', default="Simulation Name:")).grid(row=0, column=0, sticky=tk.W, pady=2)
        self.sim_name_var = tk.StringVar()
        ttk.Entry(input_frame, textvariable=self.sim_name_var, width=30).grid(row=0, column=1, sticky=tk.W, pady=2)

        # Course entry
        course_frame = ttk.LabelFrame(what_if_tab, text=_t('gui.assessment.academic_progress.progress_gui_parts.academicprogressgui_create_milestones_tab.labels.add_courses', default="Add Courses"), padding="10")
        course_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(course_frame, text=_t('gui.assessment.academic_progress.progress_gui_parts.academicprogressgui_create_milestones_tab.labels.course_id', default="Course ID:")).grid(row=0, column=0, sticky=tk.W, pady=2)
        self.course_id_var = tk.StringVar()
        ttk.Entry(course_frame, textvariable=self.course_id_var, width=15).grid(row=0, column=1, sticky=tk.W, pady=2)

        ttk.Label(course_frame, text=_t('gui.assessment.academic_progress.progress_gui_parts.academicprogressgui_create_milestones_tab.labels.credits', default="Credits:")).grid(row=0, column=2, sticky=tk.W, pady=2, padx=(10, 0))
        self.course_credits_var = tk.StringVar()
        ttk.Entry(course_frame, textvariable=self.course_credits_var, width=10).grid(row=0, column=3, sticky=tk.W, pady=2)

        ttk.Label(course_frame, text=_t('gui.assessment.academic_progress.progress_gui_parts.academicprogressgui_create_milestones_tab.labels.expected_grade', default="Expected Grade:")).grid(row=0, column=4, sticky=tk.W, pady=2, padx=(10, 0))
        self.course_grade_var = tk.StringVar()
        grade_combo = ttk.Combobox(course_frame, textvariable=self.course_grade_var, width=8)
        grade_combo['values'] = ('A+', 'A', 'A-', 'B+', 'B', 'B-', 'C+', 'C', 'C-', 'D+', 'D', 'F')
        grade_combo.grid(row=0, column=5, sticky=tk.W, pady=2)

        ttk.Button(course_frame, text=_t("academic_progress.buttons.add_course", default="Add Course"), command=self.add_what_if_course).grid(row=0, column=6, padx=10)

        # Course list
        self.what_if_courses = []
        list_frame = ttk.LabelFrame(what_if_tab, text=_t("academic_progress.labels.simulation_courses", default="Simulation Courses"), padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.what_if_listbox = tk.Listbox(list_frame, height=10)
        self.what_if_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        list_scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.what_if_listbox.yview)
        list_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.what_if_listbox.config(yscrollcommand=list_scrollbar.set)

        # Buttons
        button_frame = ttk.Frame(what_if_tab)
        button_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(button_frame, text=_t("academic_progress.buttons.clear_courses", default="Clear Courses"), command=self.clear_what_if_courses).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_t("academic_progress.buttons.calculate_gpa", default="Calculate GPA"), command=self.calculate_what_if).pack(side=tk.LEFT, padx=5)

        # Results
        self.what_if_results = ReportPane(what_if_tab, title=_t('academic_progress.tabs.what_if_title', default="GPA Simulation"))
        self.what_if_results.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    def add_what_if_course(self):
        """Add a course to what-if simulation."""
        course_id = self.course_id_var.get().strip()
        credits_str = self.course_credits_var.get().strip()
        grade = self.course_grade_var.get().strip()

        if not course_id or not credits_str or not grade:
            messagebox.showwarning(_t("academic_progress.errors.missing_info", default="Missing Info"),
                                 _t("academic_progress.messages.fill_all_course_fields", default="Please fill in all course fields."))
            return

        try:
            credits = int(credits_str)
            if credits <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror(_t("academic_progress.errors.invalid_input", default="Invalid Input"),
                               _t("academic_progress.errors.credits_must_be_positive", default="Credits must be a positive integer."))
            return

        course = {
            'course_id': course_id,
            'credits': credits,
            'expected_grade': grade
        }

        self.what_if_courses.append(course)
        self.what_if_listbox.insert(tk.END, f"{course_id} - {credits} credits - {grade}")

        # Clear inputs
        self.course_id_var.set('')
        self.course_credits_var.set('')
        self.course_grade_var.set('')

    def clear_what_if_courses(self):
        """Clear all what-if courses."""
        self.what_if_courses = []
        self.what_if_listbox.delete(0, tk.END)

    def calculate_what_if(self):
        """Calculate what-if GPA."""
        simulation_name = self.sim_name_var.get().strip()
        if not simulation_name:
            messagebox.showwarning(_t("academic_progress.errors.missing_info", default="Missing Info"),
                                 _t("academic_progress.messages.enter_simulation_name", default="Please enter a simulation name."))
            return

        if not self.what_if_courses:
            messagebox.showwarning(_t("academic_progress.errors.missing_info", default="Missing Info"),
                                 _t("academic_progress.messages.no_courses_to_add", default="Please add at least one course."))
            return

        student_id = self.auth.get_current_user()['id']

        try:
            result = self.service.calculate_what_if_gpa(student_id, simulation_name, self.what_if_courses)

            self.what_if_results.delete('1.0', tk.END)

            self.what_if_results.insert(tk.END, "═" * 80 + "\n", 'header')
            self.what_if_results.insert(tk.END, f"  WHAT-IF GPA RESULTS - {simulation_name}\n".center(80), 'header')
            self.what_if_results.insert(tk.END, "═" * 80 + "\n\n", 'header')

            self.what_if_results.insert(tk.END, f"CURRENT GPA:     {result['current_gpa']:.3f}\n", 'bold')
            self.what_if_results.insert(tk.END, f"PROJECTED GPA:   {result['projected_gpa']:.3f}\n", 'bold')

            change_text = f"GPA CHANGE:      {result['gpa_change']:+.3f}\n"
            change_tag = 'positive' if result['gpa_change'] >= 0 else 'negative'
            self.what_if_results.insert(tk.END, change_text, change_tag)

            self.what_if_results.insert(tk.END, "\nCREDITS:\n")
            self.what_if_results.insert(tk.END, f"  Simulated:   {result['credits_simulated']}\n")
            self.what_if_results.insert(tk.END, f"  Total After: {result['total_credits_after']}\n")

            self.what_if_results.insert(tk.END, "\n📊 IMPACT ANALYSIS:\n", 'bold')
            self.what_if_results.insert(tk.END, f"  {result['impact_analysis']}\n")

            self.what_if_results.insert(tk.END, f"\nSimulation ID: {result['simulation_id']}\n")

            # Configure tags
            self.what_if_results.tag_config('header', font=('Arial', 11, 'bold'))
            self.what_if_results.tag_config('bold', font=('Arial', 10, 'bold'))
            self.what_if_results.tag_config('positive', font=('Arial', 10, 'bold'), foreground='green')
            self.what_if_results.tag_config('negative', font=('Arial', 10, 'bold'), foreground='red')

            messagebox.showinfo(_t("academic_progress.dialogs.success", default="Success"),
                              _t("academic_progress.messages.gpa_calculation_complete", default="What-If GPA calculation complete!"))

        except Exception as e:
            error_text = _t("academic_progress.errors.failed_to_calculate_gpa", default="Failed to calculate GPA: {error}").format(error=str(e))
            messagebox.showerror(_t("academic_progress.errors.error", default="Error"), error_text)

    def create_target_gpa_tab(self, parent):
        """Create target GPA calculator."""
        target_tab = ttk.Frame(parent)
        parent.add(target_tab, text=_t('gui.assessment.academic_progress.progress_gui_parts.academicprogressgui_create_milestones_tab.tabs.target_gpa', default="Target GPA"))

        # Input frame
        input_frame = ttk.LabelFrame(target_tab, text=_t('gui.assessment.academic_progress.progress_gui_parts.academicprogressgui_create_milestones_tab.labels.target_gpa_calculator', default="Target GPA Calculator"), padding="20")
        input_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(input_frame, text=_t('gui.assessment.academic_progress.progress_gui_parts.academicprogressgui_create_milestones_tab.labels.target_gpa_0_0_4_0', default="Target GPA (0.0-4.0):"), font=('Arial', 10)).grid(row=0, column=0, sticky=tk.W, pady=10, padx=5)
        self.target_gpa_var = tk.StringVar()
        ttk.Entry(input_frame, textvariable=self.target_gpa_var, width=15).grid(row=0, column=1, sticky=tk.W, pady=10, padx=5)

        ttk.Label(input_frame, text=_t('gui.assessment.academic_progress.progress_gui_parts.academicprogressgui_create_milestones_tab.labels.credits_planning_to_take', default="Credits Planning to Take:"), font=('Arial', 10)).grid(row=1, column=0, sticky=tk.W, pady=10, padx=5)
        self.target_credits_var = tk.StringVar()
        ttk.Entry(input_frame, textvariable=self.target_credits_var, width=15).grid(row=1, column=1, sticky=tk.W, pady=10, padx=5)

        ttk.Button(input_frame, text=_t('gui.assessment.academic_progress.progress_gui_parts.academicprogressgui_create_milestones_tab.buttons.calculate_requirements', default="Calculate Requirements"), command=self.calculate_target_gpa).grid(row=2, column=0, columnspan=2, pady=10)

        # Results
        self.target_results = ReportPane(target_tab, title=_t('academic_progress.tabs.target_title', default="Target GPA"))
        self.target_results.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    def calculate_target_gpa(self):
        """Calculate target GPA requirements."""
        gpa_str = self.target_gpa_var.get().strip()
        if not gpa_str:
            messagebox.showwarning(_t('gui.assessment.academic_progress.progress_gui_parts.academicprogressgui_create_milestones_tab.dialogs.input_required', default="Input Required"), _t('gui.assessment.academic_progress.progress_gui_parts.academicprogressgui_create_milestones_tab.dialogs.please_enter_a_target_gpa', default="Please enter a target GPA."))
            return
        try:
            target_gpa = float(gpa_str)
            if not 0.0 <= target_gpa <= 4.0:
                messagebox.showerror(_t('gui.assessment.academic_progress.progress_gui_parts.academicprogressgui_create_milestones_tab.dialogs.invalid_input', default="Invalid Input"), _t('gui.assessment.academic_progress.progress_gui_parts.academicprogressgui_create_milestones_tab.dialogs.gpa_must_be_between_0_0_and_4_0', default="GPA must be between 0.0 and 4.0."))
                return
        except ValueError:
            messagebox.showerror(_t('gui.assessment.academic_progress.progress_gui_parts.academicprogressgui_create_milestones_tab.dialogs.invalid_input', default="Invalid Input"), _t('gui.assessment.academic_progress.progress_gui_parts.academicprogressgui_create_milestones_tab.dialogs.please_enter_a_valid_number_for_gpa', default="Please enter a valid number for GPA."))
            return

        credits_str = self.target_credits_var.get().strip()
        if not credits_str:
            messagebox.showwarning(_t('gui.assessment.academic_progress.progress_gui_parts.academicprogressgui_create_milestones_tab.dialogs.input_required', default="Input Required"), _t('gui.assessment.academic_progress.progress_gui_parts.academicprogressgui_create_milestones_tab.dialogs.please_enter_credits_to_take', default="Please enter credits to take."))
            return
        try:
            credits_to_take = int(credits_str)
            if credits_to_take <= 0:
                messagebox.showerror(_t('gui.assessment.academic_progress.progress_gui_parts.academicprogressgui_create_milestones_tab.dialogs.invalid_input', default="Invalid Input"), _t('gui.assessment.academic_progress.progress_gui_parts.academicprogressgui_create_milestones_tab.dialogs.credits_must_be_a_positive_number', default="Credits must be a positive number."))
                return
        except ValueError:
            messagebox.showerror(_t('gui.assessment.academic_progress.progress_gui_parts.academicprogressgui_create_milestones_tab.dialogs.invalid_input', default="Invalid Input"), _t('gui.assessment.academic_progress.progress_gui_parts.academicprogressgui_create_milestones_tab.dialogs.please_enter_a_valid_number_for_credits', default="Please enter a valid number for credits."))
            return

        student_id = self.auth.get_current_user()['id']

        try:
            result = self.service.calculate_target_gpa_requirements(student_id, target_gpa, credits_to_take)

            self.target_results.delete('1.0', tk.END)

            self.target_results.insert(tk.END, "═" * 80 + "\n", 'header')
            self.target_results.insert(tk.END, "  TARGET GPA ANALYSIS\n".center(80), 'header')
            self.target_results.insert(tk.END, "═" * 80 + "\n\n", 'header')

            self.target_results.insert(tk.END, f"CURRENT GPA:          {result['current_gpa']:.3f}\n")
            self.target_results.insert(tk.END, f"TARGET GPA:           {result['target_gpa']:.3f}\n", 'bold')
            self.target_results.insert(tk.END, f"CURRENT CREDITS:      {result['current_credits']}\n")
            self.target_results.insert(tk.END, f"CREDITS TO TAKE:      {result['credits_to_take']}\n")

            self.target_results.insert(tk.END, "\n" + "─" * 80 + "\n", 'separator')
            self.target_results.insert(tk.END, "REQUIREMENTS\n", 'bold')
            self.target_results.insert(tk.END, "─" * 80 + "\n\n", 'separator')

            self.target_results.insert(tk.END, f"Required Average Grade: {result['required_average_grade']:.2f}\n", 'bold')
            self.target_results.insert(tk.END, f"Required Grade Letter:  {result['required_grade_letter']}\n\n", 'bold')

            self.target_results.insert(tk.END, "📊 FEASIBILITY:\n", 'bold')
            if result['achievable']:
                self.target_results.insert(tk.END, f"  ✓ {result['feasibility']}\n", 'positive')
            else:
                self.target_results.insert(tk.END, f"  ✗ {result['feasibility']}\n", 'negative')
                self.target_results.insert(tk.END, "\n💡 Consider taking more credits or adjusting your target GPA.\n")

            # Configure tags
            self.target_results.tag_config('header', font=('Arial', 11, 'bold'))
            self.target_results.tag_config('bold', font=('Arial', 10, 'bold'))
            self.target_results.tag_config('separator', foreground='gray')
            self.target_results.tag_config('positive', foreground='green', font=('Arial', 10, 'bold'))
            self.target_results.tag_config('negative', foreground='red', font=('Arial', 10, 'bold'))

        except Exception as e:
            messagebox.showerror(_t('gui.assessment.academic_progress.progress_gui_parts.academicprogressgui_create_milestones_tab.dialogs.error', default="Error"), f"Failed to calculate target GPA: {str(e)}")

    def create_sim_history_tab(self, parent):
        """Create simulation history tab."""
        history_tab = ttk.Frame(parent)
        parent.add(history_tab, text=_t('gui.assessment.academic_progress.progress_gui_parts.academicprogressgui_create_milestones_tab.tabs.simulation_history', default="Simulation History"))

        ttk.Button(history_tab, text=_t('gui.assessment.academic_progress.progress_gui_parts.academicprogressgui_create_milestones_tab.buttons.load_history', default="Load History"), command=self.load_sim_history).pack(pady=10)

        self.sim_history_text = ReportPane(history_tab, title=_t('academic_progress.tabs.sim_history_title', default="Simulation History"))
        self.sim_history_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    def load_sim_history(self):
        """Load simulation history."""
        student_id = self.auth.get_current_user()['id']

        try:
            simulations = self.service.get_simulation_history(student_id)

            self.sim_history_text.delete('1.0', tk.END)

            if not simulations:
                self.sim_history_text.insert(tk.END, "No simulation history found.\n")
                return

            self.sim_history_text.insert(tk.END, "═" * 80 + "\n", 'header')
            self.sim_history_text.insert(tk.END, "  GPA SIMULATION HISTORY\n".center(80), 'header')
            self.sim_history_text.insert(tk.END, "═" * 80 + "\n\n", 'header')

            self.sim_history_text.insert(tk.END, f"Total Simulations: {len(simulations)}\n\n")

            for i, sim in enumerate(simulations, 1):
                self.sim_history_text.insert(tk.END, "─" * 80 + "\n", 'separator')
                self.sim_history_text.insert(tk.END, f"[{i}] {sim['simulation_name']}\n", 'bold')
                self.sim_history_text.insert(tk.END, f"    Date: {sim['created_at']}\n")
                self.sim_history_text.insert(tk.END, f"    Current GPA: {sim['current_gpa']:.3f}\n")
                self.sim_history_text.insert(tk.END, f"    Projected GPA: {sim['projected_gpa']:.3f}\n")

                change = sim['projected_gpa'] - sim['current_gpa']
                change_tag = 'positive' if change >= 0 else 'negative'
                self.sim_history_text.insert(tk.END, f"    Change: {change:+.3f}\n", change_tag)
                self.sim_history_text.insert(tk.END, f"    Credits Simulated: {sim['credits_simulated']}\n\n")

            # Configure tags
            self.sim_history_text.tag_config('header', font=('Arial', 11, 'bold'))
            self.sim_history_text.tag_config('bold', font=('Arial', 10, 'bold'))
            self.sim_history_text.tag_config('separator', foreground='gray')
            self.sim_history_text.tag_config('positive', foreground='green')
            self.sim_history_text.tag_config('negative', foreground='red')

        except Exception as e:
            messagebox.showerror(_t('gui.assessment.academic_progress.progress_gui_parts.academicprogressgui_create_milestones_tab.dialogs.error', default="Error"), f"Failed to load simulation history: {str(e)}")
