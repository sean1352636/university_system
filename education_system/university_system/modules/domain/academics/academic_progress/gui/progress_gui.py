"""
Academic Progress Dashboard GUI Interface

Provides graphical interface for degree tracking, GPA simulation, and early warnings.
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import matplotlib
matplotlib.use('TkAgg')
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from education_system.university_system.modules.domain.academics.academic_progress.services.progress_service import ProgressService
from education_system.university_system.infrastructure.database.db import get_connection
from education_system.university_system.infrastructure.shared_context import get_auth
from education_system.university_system.infrastructure.localization import get_translation

try:
    from education_system.university_system.modules.domain.academics.grading.grade_calculation import (
        calculate_student_gpa, letter_to_gpa,
    )
except ImportError:
    calculate_student_gpa = None
    letter_to_gpa = None

# Translation helper
_t = get_translation


class AcademicProgressGUI:
    """Graphical interface for Academic Progress Dashboard."""

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

        except Exception as e:
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
        self.progress_results = scrolledtext.ScrolledText(progress_tab, height=30, width=100, wrap=tk.WORD)
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
            stats_frame = ttk.LabelFrame(self.milestones_frame, text="Your Current Stats", padding="10")
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
        parent.add(what_if_tab, text="What-If Scenario")

        # Input section
        input_frame = ttk.LabelFrame(what_if_tab, text="Simulation Setup", padding="10")
        input_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(input_frame, text="Simulation Name:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.sim_name_var = tk.StringVar()
        ttk.Entry(input_frame, textvariable=self.sim_name_var, width=30).grid(row=0, column=1, sticky=tk.W, pady=2)

        # Course entry
        course_frame = ttk.LabelFrame(what_if_tab, text="Add Courses", padding="10")
        course_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(course_frame, text="Course ID:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.course_id_var = tk.StringVar()
        ttk.Entry(course_frame, textvariable=self.course_id_var, width=15).grid(row=0, column=1, sticky=tk.W, pady=2)

        ttk.Label(course_frame, text="Credits:").grid(row=0, column=2, sticky=tk.W, pady=2, padx=(10, 0))
        self.course_credits_var = tk.StringVar()
        ttk.Entry(course_frame, textvariable=self.course_credits_var, width=10).grid(row=0, column=3, sticky=tk.W, pady=2)

        ttk.Label(course_frame, text="Expected Grade:").grid(row=0, column=4, sticky=tk.W, pady=2, padx=(10, 0))
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
        self.what_if_results = scrolledtext.ScrolledText(what_if_tab, height=10, wrap=tk.WORD)
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

            self.what_if_results.insert(tk.END, f"\nCREDITS:\n")
            self.what_if_results.insert(tk.END, f"  Simulated:   {result['credits_simulated']}\n")
            self.what_if_results.insert(tk.END, f"  Total After: {result['total_credits_after']}\n")

            self.what_if_results.insert(tk.END, f"\n📊 IMPACT ANALYSIS:\n", 'bold')
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
        parent.add(target_tab, text="Target GPA")

        # Input frame
        input_frame = ttk.LabelFrame(target_tab, text="Target GPA Calculator", padding="20")
        input_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(input_frame, text="Target GPA (0.0-4.0):", font=('Arial', 10)).grid(row=0, column=0, sticky=tk.W, pady=10, padx=5)
        self.target_gpa_var = tk.StringVar()
        ttk.Entry(input_frame, textvariable=self.target_gpa_var, width=15).grid(row=0, column=1, sticky=tk.W, pady=10, padx=5)

        ttk.Label(input_frame, text="Credits Planning to Take:", font=('Arial', 10)).grid(row=1, column=0, sticky=tk.W, pady=10, padx=5)
        self.target_credits_var = tk.StringVar()
        ttk.Entry(input_frame, textvariable=self.target_credits_var, width=15).grid(row=1, column=1, sticky=tk.W, pady=10, padx=5)

        ttk.Button(input_frame, text="Calculate Requirements", command=self.calculate_target_gpa).grid(row=2, column=0, columnspan=2, pady=10)

        # Results
        self.target_results = scrolledtext.ScrolledText(target_tab, height=20, wrap=tk.WORD)
        self.target_results.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    def calculate_target_gpa(self):
        """Calculate target GPA requirements."""
        gpa_str = self.target_gpa_var.get().strip()
        if not gpa_str:
            messagebox.showwarning("Input Required", "Please enter a target GPA.")
            return
        try:
            target_gpa = float(gpa_str)
            if not 0.0 <= target_gpa <= 4.0:
                messagebox.showerror("Invalid Input", "GPA must be between 0.0 and 4.0.")
                return
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter a valid number for GPA.")
            return

        credits_str = self.target_credits_var.get().strip()
        if not credits_str:
            messagebox.showwarning("Input Required", "Please enter credits to take.")
            return
        try:
            credits_to_take = int(credits_str)
            if credits_to_take <= 0:
                messagebox.showerror("Invalid Input", "Credits must be a positive number.")
                return
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter a valid number for credits.")
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
            messagebox.showerror("Error", f"Failed to calculate target GPA: {str(e)}")

    def create_sim_history_tab(self, parent):
        """Create simulation history tab."""
        history_tab = ttk.Frame(parent)
        parent.add(history_tab, text="Simulation History")

        ttk.Button(history_tab, text="Load History", command=self.load_sim_history).pack(pady=10)

        self.sim_history_text = scrolledtext.ScrolledText(history_tab, height=25, wrap=tk.WORD)
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
                self.sim_history_text.insert(tk.END, f"─" * 80 + "\n", 'separator')
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
            messagebox.showerror("Error", f"Failed to load simulation history: {str(e)}")

    def create_warnings_tab(self):
        """Create warnings management tab."""
        warnings_tab = ttk.Frame(self.notebook)
        self.notebook.add(warnings_tab, text=_t("academic_progress.tabs.warnings", default="⚠️ Warnings"))

        # Action buttons
        button_frame = ttk.Frame(warnings_tab)
        button_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(button_frame, text="Check Active Warnings",
                  command=self.load_active_warnings).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Run Warning Scan",
                  command=self.run_warning_scan).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Acknowledge Warning",
                  command=self.acknowledge_warning_gui).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Resolve Warning",
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
            messagebox.showerror("Error", f"Failed to load warnings: {str(e)}")

    def run_warning_scan(self):
        """Run warning scan."""
        student_id = self.auth.get_current_user()['id']

        response = messagebox.askyesno("Run Warning Scan",
                                       "This will scan your academic records for warning indicators.\nContinue?")
        if not response:
            return

        try:
            warnings = self.service.check_early_warnings(student_id)

            if warnings:
                messagebox.showinfo("Scan Complete",
                                   f"Warning scan complete.\n{len(warnings)} warning(s) detected.\n\nView the Warnings tab for details.")
            else:
                messagebox.showinfo("Scan Complete",
                                   "Warning scan complete.\nNo warnings detected! Your academic performance looks good.")

            # Refresh warnings display
            self.load_active_warnings()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to run warning scan: {str(e)}")

    def _get_warning_id_from_user(self, action_name):
        """Get warning ID via a dropdown of active warnings instead of free-text entry."""
        try:
            student_id = self.auth.current_user.get('student_id') or self.auth.current_user.get('id') or self.auth.current_user.get('username')
            warnings = self.service.get_active_warnings(str(student_id))
            if not warnings:
                messagebox.showinfo("Info", "No active warnings found.")
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
            ttk.Button(btn_frame, text="OK", command=on_ok).pack(side=tk.LEFT, padx=5)
            ttk.Button(btn_frame, text="Cancel", command=dlg.destroy).pack(side=tk.LEFT, padx=5)

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
                messagebox.showinfo("Success", f"Warning {warning_id} has been acknowledged.")
                self.load_active_warnings()
            else:
                messagebox.showerror("Error", f"Failed to acknowledge warning {warning_id}.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to acknowledge warning: {str(e)}")

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
                messagebox.showinfo("Success", f"Warning {warning_id} has been resolved!")
                self.load_active_warnings()
            else:
                messagebox.showerror("Error", f"Failed to resolve warning {warning_id}.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to resolve warning: {str(e)}")

    def create_forecast_tab(self):
        """Create graduation forecast tab."""
        forecast_tab = ttk.Frame(self.notebook)
        self.notebook.add(forecast_tab, text=_t("academic_progress.tabs.forecast", default="🎓 Forecast"))

        # Program selector
        selector_frame = ttk.Frame(forecast_tab)
        selector_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(selector_frame, text="Program Code:", font=('Arial', 10, 'bold')).pack(side=tk.LEFT, padx=5)
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

        ttk.Button(selector_frame, text="Generate Forecast",
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
            messagebox.showerror("Error", f"Failed to generate forecast: {str(e)}")

    # ------------------------------------------------------------------
    # Grade helpers (merged from StudentGradesPortal)
    # ------------------------------------------------------------------

    _LETTER_THRESHOLDS = [
        (97, 'A+'), (93, 'A'), (90, 'A-'),
        (87, 'B+'), (83, 'B'), (80, 'B-'),
        (77, 'C+'), (73, 'C'), (70, 'C-'),
        (67, 'D+'), (63, 'D'), (60, 'D-'),
        (0, 'F'),
    ]

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

    # ------------------------------------------------------------------
    # My Grades tab (merged from StudentGradesPortal)
    # ------------------------------------------------------------------

    def create_my_grades_tab(self):
        """Create the My Grades tab with detailed grade table."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t("academic_progress.tabs.my_grades", default="My Grades"))

        header = ttk.Frame(tab)
        header.pack(fill=tk.X, padx=10, pady=(10, 0))
        ttk.Label(header, text="My Grades", font=('Arial', 14, 'bold')).pack(side='left')
        ttk.Button(header, text="Refresh", command=self._populate_grades_tree).pack(side='right')

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

    # ------------------------------------------------------------------
    # Transcript tab (merged from StudentGradesPortal)
    # ------------------------------------------------------------------

    def create_transcript_tab(self):
        """Create the Transcript tab with exportable academic record."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t("academic_progress.tabs.transcript", default="Transcript"))

        header = ttk.Frame(tab)
        header.pack(fill=tk.X, padx=10, pady=(10, 0))
        ttk.Label(header, text="Academic Transcript", font=('Arial', 14, 'bold')).pack(side='left')
        ttk.Button(header, text="Export", command=self._export_transcript).pack(side='right')

        self._transcript_text = scrolledtext.ScrolledText(
            tab, wrap='word', font=('Courier', 10), state='disabled',
        )
        self._transcript_text.pack(fill='both', expand=True, padx=10, pady=10)

        self._render_transcript()

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
            messagebox.showinfo('Export Successful', f'Transcript saved to:\n{filepath}')
        except Exception as e:
            messagebox.showerror('Export Error', f'Failed to save transcript: {e}')

    def create_history_tab(self):
        """Create progress history tab."""
        history_tab = ttk.Frame(self.notebook)
        self.notebook.add(history_tab, text=_t("academic_progress.tabs.history", default="📜 History"))

        button_frame = ttk.Frame(history_tab)
        button_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(button_frame, text="Load Progress History",
                  command=self.load_progress_history).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Create Snapshot",
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
            messagebox.showerror("Error", f"Failed to load progress history: {str(e)}")

    def create_snapshot_gui(self):
        """Create a progress snapshot."""
        semester = tk.simpledialog.askstring("Create Snapshot",
                                            "Enter semester (e.g., Fall 2025):")
        if not semester:
            return

        student_id = self.auth.get_current_user()['id']

        try:
            snapshot_id = self.service.create_progress_snapshot(student_id, semester)
            messagebox.showinfo("Success",
                               f"Progress snapshot created successfully!\nSnapshot ID: {snapshot_id}")
            self.load_progress_history()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create snapshot: {str(e)}")

    def run(self):
        """Run the GUI application."""
        self.root.mainloop()


# Add import for simpledialog
import tkinter.simpledialog


# Entry point for direct execution
if __name__ == "__main__":
    gui = AcademicProgressGUI()
    gui.run()
