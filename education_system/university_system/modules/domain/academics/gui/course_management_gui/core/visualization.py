from education_system.university_system.modules.domain.academics.gui.course_management_gui.core._imports import (
    _, messagebox, tk, ttk, Toplevel, sqlite3, DEFAULT_DB_PATH,
    CHARTS_AVAILABLE, Figure, FigureCanvasTkAgg, np,
)


class VisualizationMixin:
    """Chart visualization and email report operations."""

    def visualize_report(self):
        """Generate and display visual charts for the current report"""
        if not hasattr(self, 'last_report_data'):
            messagebox.showwarning(_("course_management.messages.no_report"), _("course_management.messages.generate_report_first"))
            return

        if not CHARTS_AVAILABLE:
            messagebox.showerror(_("course_management.messages.charts_unavailable"),
                               _("course_management.messages.charts_unavailable"))
            return

        report_type = self.last_report_data['type']

        try:
            # Create chart window
            chart_window = tk.Toplevel(self.root)
            chart_window.title(_("course_management.dialogs.report_visualization", type=report_type))
            chart_window.geometry("1200x800")
            chart_window.transient(self.root)

            # Create main frame
            main_frame = ttk.Frame(chart_window, padding="10")
            main_frame.pack(fill=tk.BOTH, expand=True)

            ttk.Label(main_frame, text=_("course_management.dialogs.report_visualization", type=report_type),
                     font=("Arial", 14, "bold")).pack(pady=10)

            # Create notebook for multiple charts
            chart_notebook = ttk.Notebook(main_frame)
            chart_notebook.pack(fill=tk.BOTH, expand=True, pady=10)

            # Fetch data from database
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()

                if report_type == "Summary":
                    self._create_summary_charts(chart_notebook, cursor)
                elif report_type == "Department":
                    self._create_department_charts(chart_notebook, cursor)
                elif report_type == "Detailed":
                    self._create_detailed_charts(chart_notebook, cursor)
                elif report_type == "Capacity":
                    self._create_capacity_charts(chart_notebook, cursor)

            # Close button
            ttk.Button(main_frame, text=_("common.close"), command=chart_window.destroy).pack(pady=10)

        except Exception as e:
            messagebox.showerror(_("course_management.messages.visualization_error"), _("course_management.messages.failed_create_charts", error=str(e)))
            print(_("course_management.errors.chart_generation", error=str(e)))

    def _create_summary_charts(self, notebook, cursor):
        """Create summary report charts"""
        # Get summary data
        cursor.execute("""
        SELECT
            COUNT(*) as total_courses,
            SUM(COALESCE(current_enrollment, 0)) as total_enrolled,
            SUM(COALESCE(max_enrollment, 0)) as total_capacity,
            AVG(COALESCE(current_enrollment, 0)) as avg_enrollment
        FROM courses
        WHERE status = 'Active'
        """)
        summary = cursor.fetchone()

        # Chart 1: Enrollment Overview (Bar Chart)
        frame1 = ttk.Frame(notebook)
        notebook.add(frame1, text=_("course_management.analytics_tabs.enrollment_overview"))

        fig1 = Figure(figsize=(10, 6), dpi=100)
        ax1 = fig1.add_subplot(111)

        categories = ['Total Courses', 'Total Enrolled', 'Total Capacity', 'Available Spots']
        values = [summary[0], summary[1], summary[2], summary[2] - summary[1]]
        colors = ['#3498db', '#2ecc71', '#e74c3c', '#f39c12']

        ax1.bar(categories, values, color=colors, alpha=0.8)
        ax1.set_ylabel('Count')
        ax1.set_title('Course Enrollment Summary', fontweight='bold', fontsize=14)
        ax1.grid(axis='y', alpha=0.3)

        for i, v in enumerate(values):
            ax1.text(i, v, f'{int(v)}', ha='center', va='bottom', fontweight='bold')

        canvas1 = FigureCanvasTkAgg(fig1, frame1)
        canvas1.draw()
        canvas1.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # Chart 2: Fill Rate Pie Chart
        frame2 = ttk.Frame(notebook)
        notebook.add(frame2, text=_("course_management.analytics_tabs.capacity_fill_rate"))

        fig2 = Figure(figsize=(10, 6), dpi=100)
        ax2 = fig2.add_subplot(111)

        enrolled = summary[1]
        available = summary[2] - summary[1]

        ax2.pie([enrolled, available], labels=['Enrolled', 'Available'],
               autopct='%1.1f%%', startangle=90, colors=['#2ecc71', '#ecf0f1'])
        ax2.set_title(f'System Capacity Utilization\n({enrolled}/{summary[2]} spots filled)',
                     fontweight='bold', fontsize=14)

        canvas2 = FigureCanvasTkAgg(fig2, frame2)
        canvas2.draw()
        canvas2.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def _create_department_charts(self, notebook, cursor):
        """Create department report charts"""
        cursor.execute("""
        SELECT
            COALESCE(department, 'Unknown') as dept,
            COUNT(*) as course_count,
            SUM(COALESCE(current_enrollment, 0)) as total_students,
            SUM(COALESCE(max_enrollment, 0)) as total_capacity
        FROM courses
        WHERE status = 'Active'
        GROUP BY department
        ORDER BY total_students DESC
        """)
        dept_data = cursor.fetchall()

        # Chart 1: Students by Department (Bar Chart)
        frame1 = ttk.Frame(notebook)
        notebook.add(frame1, text=_("course_management.analytics_tabs.students_by_department"))

        fig1 = Figure(figsize=(12, 6), dpi=100)
        ax1 = fig1.add_subplot(111)

        departments = [row[0] for row in dept_data]
        students = [row[2] for row in dept_data]

        ax1.barh(departments, students, color='#3498db', alpha=0.8)
        ax1.set_xlabel('Number of Students')
        ax1.set_title('Student Enrollment by Department', fontweight='bold', fontsize=14)
        ax1.grid(axis='x', alpha=0.3)

        for i, v in enumerate(students):
            ax1.text(v, i, f' {int(v)}', va='center', fontweight='bold')

        fig1.tight_layout()
        canvas1 = FigureCanvasTkAgg(fig1, frame1)
        canvas1.draw()
        canvas1.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # Chart 2: Course Count by Department (Pie Chart)
        frame2 = ttk.Frame(notebook)
        notebook.add(frame2, text=_("course_management.analytics_tabs.courses_by_department"))

        fig2 = Figure(figsize=(10, 6), dpi=100)
        ax2 = fig2.add_subplot(111)

        course_counts = [row[1] for row in dept_data]

        ax2.pie(course_counts, labels=departments, autopct='%1.1f%%', startangle=90)
        ax2.set_title('Course Distribution by Department', fontweight='bold', fontsize=14)

        canvas2 = FigureCanvasTkAgg(fig2, frame2)
        canvas2.draw()
        canvas2.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # Chart 3: Fill Rate by Department
        frame3 = ttk.Frame(notebook)
        notebook.add(frame3, text=_("course_management.analytics_tabs.fill_rate_by_department"))

        fig3 = Figure(figsize=(12, 6), dpi=100)
        ax3 = fig3.add_subplot(111)

        fill_rates = [(row[2] / row[3] * 100) if row[3] > 0 else 0 for row in dept_data]

        ax3.barh(departments, fill_rates, color='#2ecc71', alpha=0.8)
        ax3.set_xlabel('Fill Rate (%)')
        ax3.set_title('Capacity Fill Rate by Department', fontweight='bold', fontsize=14)
        ax3.grid(axis='x', alpha=0.3)

        for i, v in enumerate(fill_rates):
            ax3.text(v, i, f' {v:.1f}%', va='center', fontweight='bold')

        fig3.tight_layout()
        canvas3 = FigureCanvasTkAgg(fig3, frame3)
        canvas3.draw()
        canvas3.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def _create_detailed_charts(self, notebook, cursor):
        """Create detailed report charts"""
        cursor.execute("""
        SELECT course_code, course_name, department,
               COALESCE(current_enrollment, 0), COALESCE(max_enrollment, 0)
        FROM courses
        WHERE status = 'Active'
        ORDER BY current_enrollment DESC
        LIMIT 15
        """)
        course_data = cursor.fetchall()

        # Chart 1: Top 15 Courses by Enrollment
        frame1 = ttk.Frame(notebook)
        notebook.add(frame1, text=_("course_management.analytics_tabs.top_courses"))

        fig1 = Figure(figsize=(12, 8), dpi=100)
        ax1 = fig1.add_subplot(111)

        course_names = [f"{row[0]}\n{row[1][:20]}" for row in course_data]
        enrollments = [row[3] for row in course_data]

        ax1.barh(course_names, enrollments, color='#e74c3c', alpha=0.8)
        ax1.set_xlabel('Enrolled Students')
        ax1.set_title('Top 15 Courses by Enrollment', fontweight='bold', fontsize=14)
        ax1.grid(axis='x', alpha=0.3)

        for i, v in enumerate(enrollments):
            ax1.text(v, i, f' {int(v)}', va='center', fontweight='bold')

        fig1.tight_layout()
        canvas1 = FigureCanvasTkAgg(fig1, frame1)
        canvas1.draw()
        canvas1.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # Chart 2: Enrollment vs Capacity
        frame2 = ttk.Frame(notebook)
        notebook.add(frame2, text=_("course_management.analytics_tabs.enrollment_vs_capacity"))

        fig2 = Figure(figsize=(12, 8), dpi=100)
        ax2 = fig2.add_subplot(111)

        x = np.arange(len(course_data))
        width = 0.35

        enrolled = [row[3] for row in course_data]
        capacity = [row[4] for row in course_data]
        course_codes = [row[0] for row in course_data]

        ax2.bar(x - width/2, enrolled, width, label='Enrolled', color='#3498db', alpha=0.8)
        ax2.bar(x + width/2, capacity, width, label='Capacity', color='#95a5a6', alpha=0.8)

        ax2.set_xlabel('Course Code')
        ax2.set_ylabel('Students')
        ax2.set_title('Enrollment vs Capacity - Top 15 Courses', fontweight='bold', fontsize=14)
        ax2.set_xticks(x)
        ax2.set_xticklabels(course_codes, rotation=45, ha='right')
        ax2.legend()
        ax2.grid(axis='y', alpha=0.3)

        fig2.tight_layout()
        canvas2 = FigureCanvasTkAgg(fig2, frame2)
        canvas2.draw()
        canvas2.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def _create_capacity_charts(self, notebook, cursor):
        """Create capacity report charts"""
        cursor.execute("""
        SELECT course_code, course_name, department,
               COALESCE(current_enrollment, 0) as enrolled,
               COALESCE(max_enrollment, 0) as capacity,
               COALESCE(max_enrollment, 0) - COALESCE(current_enrollment, 0) as available
        FROM courses
        WHERE status = 'Active'
        ORDER BY available DESC
        LIMIT 15
        """)
        capacity_data = cursor.fetchall()

        # Chart 1: Available Spots by Course
        frame1 = ttk.Frame(notebook)
        notebook.add(frame1, text=_("course_management.analytics_tabs.available_spots"))

        fig1 = Figure(figsize=(12, 8), dpi=100)
        ax1 = fig1.add_subplot(111)

        course_names = [f"{row[0]}\n{row[1][:20]}" for row in capacity_data]
        available = [row[5] for row in capacity_data]

        ax1.barh(course_names, available, color='#f39c12', alpha=0.8)
        ax1.set_xlabel('Available Spots')
        ax1.set_title('Top 15 Courses by Available Capacity', fontweight='bold', fontsize=14)
        ax1.grid(axis='x', alpha=0.3)

        for i, v in enumerate(available):
            ax1.text(v, i, f' {int(v)}', va='center', fontweight='bold')

        fig1.tight_layout()
        canvas1 = FigureCanvasTkAgg(fig1, frame1)
        canvas1.draw()
        canvas1.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # Chart 2: Capacity Utilization Breakdown
        frame2 = ttk.Frame(notebook)
        notebook.add(frame2, text=_("course_management.analytics_tabs.utilization_breakdown"))

        fig2 = Figure(figsize=(12, 8), dpi=100)
        ax2 = fig2.add_subplot(111)

        course_codes = [row[0] for row in capacity_data]
        enrolled = [row[3] for row in capacity_data]
        available = [row[5] for row in capacity_data]

        x = np.arange(len(capacity_data))
        ax2.bar(x, enrolled, label='Enrolled', color='#2ecc71', alpha=0.8)
        ax2.bar(x, available, bottom=enrolled, label='Available', color='#ecf0f1', alpha=0.8)

        ax2.set_xlabel('Course Code')
        ax2.set_ylabel('Spots')
        ax2.set_title('Capacity Utilization - Top 15 Courses', fontweight='bold', fontsize=14)
        ax2.set_xticks(x)
        ax2.set_xticklabels(course_codes, rotation=45, ha='right')
        ax2.legend()
        ax2.grid(axis='y', alpha=0.3)

        fig2.tight_layout()
        canvas2 = FigureCanvasTkAgg(fig2, frame2)
        canvas2.draw()
        canvas2.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def email_report(self):
        """Email the current report to admin"""
        if not hasattr(self, 'last_report_data'):
            messagebox.showwarning(_("course_management.messages.no_report"), _("course_management.messages.generate_report_first"))
            return

        if not EMAIL_AVAILABLE:
            messagebox.showerror(_("course_management.messages.email_service_unavailable"),
                               _("course_management.messages.email_service_unavailable"))
            return

        # Create email dialog
        email_dialog = tk.Toplevel(self.root)
        email_dialog.title(_("course_management.dialogs.email_course_report"))
        email_dialog.geometry("1000x750")
        email_dialog.transient(self.root)
        email_dialog.grab_set()

        frame = ttk.Frame(email_dialog, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text=_("course_management.labels.email_course_management_report"),
                 font=("Arial", 14, "bold")).pack(pady=(0, 20))

        # Get admin email from database
        try:
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT email FROM users WHERE LOWER(role) = 'admin' LIMIT 1")
                admin_row = cursor.fetchone()
                default_email = admin_row[0] if admin_row else "admin@university.edu"
        except Exception as e:
            print(_("course_management.warnings.admin_email_fetch_failed", error=str(e)))
            default_email = "admin@university.edu"

        ttk.Label(frame, text=_("course_management.labels.admin_email_address")).pack(anchor='w', pady=(0, 5))
        email_var = tk.StringVar(value=default_email)

        # Create email input frame with refresh button
        email_frame = ttk.Frame(frame)
        email_frame.pack(fill='x', pady=(0, 10))

        email_entry = ttk.Entry(email_frame, textvariable=email_var, width=40)
        email_entry.pack(side='left', fill='x', expand=True)

        def refresh_admin_email():
            """Refresh admin email from database"""
            try:
                with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT username, email FROM users WHERE LOWER(role) = 'admin' ORDER BY username")
                    admins = cursor.fetchall()

                if admins:
                    if len(admins) > 1:
                        # Show selection dialog
                        admin_select_dialog = tk.Toplevel(email_dialog)
                        admin_select_dialog.title(_("course_management.dialogs.select_admin"))
                        admin_select_dialog.geometry("900x700")
                        admin_select_dialog.transient(email_dialog)
                        admin_select_dialog.grab_set()

                        ttk.Label(admin_select_dialog, text=_("course_management.labels.select_admin_user"),
                                 font=('Arial', 12, 'bold')).pack(pady=10)

                        admin_listbox = tk.Listbox(admin_select_dialog, height=10)
                        admin_listbox.pack(fill='both', expand=True, padx=20, pady=10)

                        for username, email in admins:
                            admin_listbox.insert(tk.END, f"{username} ({email})")

                        def select_admin():
                            selection = admin_listbox.curselection()
                            if selection:
                                selected_email = admins[selection[0]][1]
                                email_var.set(selected_email)
                            admin_select_dialog.destroy()

                        ttk.Button(admin_select_dialog, text=_("course_management.buttons.select"),
                                  command=select_admin).pack(pady=10)
                    else:
                        email_var.set(admins[0][1])
                        messagebox.showinfo(_("course_management.messages.admin_email"), _("course_management.messages.using_admin_email", email=admins[0][1]))
                else:
                    messagebox.showwarning(_("course_management.messages.no_admins_found"), _("course_management.messages.no_admins_found"))
            except Exception as e:
                messagebox.showerror(_("common.database_error"), _("course_management.messages.failed_load_course_details", error=str(e)))

        ttk.Button(email_frame, text="\U0001f504", command=refresh_admin_email, width=3).pack(side='left', padx=(5, 0))

        ttk.Label(frame, text=_("course_management.labels.subject")).pack(anchor='w', pady=(10, 5))
        subject_var = tk.StringVar(value=f"Course Management Report - {self.last_report_data['type']}")
        ttk.Entry(frame, textvariable=subject_var, width=60).pack(fill='x', pady=(0, 10))

        ttk.Label(frame, text=_("course_management.labels.message_optional")).pack(anchor='w', pady=(10, 5))
        message_text = ScrolledText(frame, height=8, wrap=tk.WORD)
        message_text.pack(fill='both', expand=True, pady=(0, 10))
        message_text.insert('1.0', "Please find the course management report below.\n\n"
                                   "This report was automatically generated from the Course Management GUI.")

        ttk.Label(frame, text=_("course_management.labels.report_preview")).pack(anchor='w', pady=(10, 5))
        preview_text = ScrolledText(frame, height=10, wrap=tk.WORD)
        preview_text.pack(fill='both', expand=True, pady=(0, 20))
        preview_text.insert('1.0', self.last_report_data['text'])
        preview_text.config(state='disabled')

        def send_email_report():
            try:
                admin_email = email_var.get().strip()
                subject = subject_var.get().strip()
                message = message_text.get('1.0', tk.END).strip()

                if not admin_email or '@' not in admin_email:
                    messagebox.showwarning(_("course_management.messages.invalid_email"), _("course_management.messages.invalid_email"))
                    return

                # Render email from template
                from education_system.university_system.infrastructure.email.template_utils import render_template

                template_subject, template_body = render_template('academics/course_management_report', {
                    'custom_message': message,
                    'separator': '=' * 80,
                    'report_content': self.last_report_data['text'],
                    'report_type': self.last_report_data['type'],
                    'generated_timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })

                # Use template if available, otherwise fallback
                if template_subject and template_body:
                    # Subject from dialog takes precedence
                    body = template_body
                else:
                    # Fallback to hardcoded format
                    body = f"""{message}

{'=' * 80}
{self.last_report_data['text']}
{'=' * 80}

Report Type: {self.last_report_data['type']}
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

This email was sent from the Course Management GUI.
"""

                # Send email
                send_email(
                    recipient_email=admin_email,
                    subject=subject,
                    body=body
                )

                messagebox.showinfo(_("course_management.messages.email_sent_success"),
                                  _("course_management.messages.email_sent_success", email=admin_email, subject=subject))
                email_dialog.destroy()

            except Exception as e:
                messagebox.showerror(_("course_management.messages.email_error_details"),
                                   _("course_management.messages.email_error_details", error=str(e)))
                print(_("course_management.errors.email", error=str(e)))

        # Buttons
        button_frame = ttk.Frame(frame)
        button_frame.pack(fill='x', pady=(10, 0))
        ttk.Button(button_frame, text=_("course_management.buttons.send_email"),
                  command=send_email_report).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_("common.cancel"),
                  command=email_dialog.destroy).pack(side='right')
