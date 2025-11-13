"""
Student Portal for Financial Aid & Scholarships

This module provides the student-facing interface for viewing scholarships,
applying for aid, tracking applications, and managing awards.
"""

from .common_imports import *


class StudentPortal:
    """Student-facing portal for financial aid and scholarships"""

    def __init__(self, parent_frame, auth_instance=None):
        """
        Initialize student portal

        Args:
            parent_frame: Parent tkinter frame
            auth_instance: Authentication instance
        """
        self.parent_frame = parent_frame
        self.auth = auth_instance or get_auth()
        self.aid_manager = FinancialAidManager()
        self.scholarship_manager = ScholarshipManager()

        # Current user info
        self.student_id = get_student_id()
        self.current_user = get_current_user()

    def show_dashboard(self):
        """Display student dashboard"""
        clear_frame(self.parent_frame)

        # Title
        title_frame = ttk.Frame(self.parent_frame)
        title_frame.pack(fill='x', padx=10, pady=10)
        ttk.Label(title_frame, text="My Financial Aid Dashboard", style='Title.TLabel').pack(anchor='w')

        # Statistics cards
        stats_frame = ttk.Frame(self.parent_frame)
        stats_frame.pack(fill='x', padx=10, pady=10)

        try:
            # Get student statistics
            stats = self._get_student_stats()

            # Create stat cards
            cards = [
                ("Total Awards", format_currency(stats['total_awards']), 'success'),
                ("Pending Applications", str(stats['pending_apps']), 'warning'),
                ("Available Scholarships", str(stats['available_scholarships']), 'info'),
                ("Total Disbursed", format_currency(stats['total_disbursed']), 'primary')
            ]

            for i, (title, value, color) in enumerate(cards):
                card = create_stat_card(stats_frame, title, value, color)
                card.grid(row=0, column=i, padx=10, pady=5, sticky='ew')
                stats_frame.grid_columnconfigure(i, weight=1)

        except Exception as e:
            logger.error(f"Error loading stats: {e}")
            ttk.Label(stats_frame, text="Error loading statistics", foreground='red').pack()

        # Quick actions
        actions_frame = ttk.LabelFrame(self.parent_frame, text="Quick Actions", padding=10)
        actions_frame.pack(fill='x', padx=10, pady=10)

        actions = [
            ("Browse Scholarships", self.show_scholarships),
            ("Apply for Financial Aid", self.show_apply_aid),
            ("My Applications", self.show_my_applications),
            ("My Awards", self.show_my_awards)
        ]

        for i, (text, command) in enumerate(actions):
            ttk.Button(actions_frame, text=text, command=command, width=20).grid(
                row=0, column=i, padx=5, pady=5, sticky='ew')
            actions_frame.grid_columnconfigure(i, weight=1)

        # Recent activity
        self._show_recent_activity()

    def _get_student_stats(self) -> Dict[str, Any]:
        """Get student statistics"""
        stats = {
            'total_awards': 0.0,
            'pending_apps': 0,
            'available_scholarships': 0,
            'total_disbursed': 0.0
        }

        try:
            with get_connection() as conn:
                # Total awards
                result = conn.execute("""
                    SELECT COALESCE(SUM(amount), 0) as total
                    FROM student_scholarships
                    WHERE student_id = ? AND status = 'awarded'
                """, (self.student_id,)).fetchone()
                stats['total_awards'] = float(result['total']) if result else 0.0

                # Pending applications
                result = conn.execute("""
                    SELECT COUNT(*) as count
                    FROM scholarship_applications
                    WHERE student_id = ? AND status = 'pending'
                """, (self.student_id,)).fetchone()
                stats['pending_apps'] = result['count'] if result else 0

                # Available scholarships
                result = conn.execute("""
                    SELECT COUNT(*) as count
                    FROM scholarships
                    WHERE is_active = 1 AND deadline >= date('now')
                """).fetchone()
                stats['available_scholarships'] = result['count'] if result else 0

                # Total disbursed
                try:
                    result = conn.execute("""
                        SELECT COALESCE(SUM(d.amount), 0) as total
                        FROM disbursements d
                        WHERE d.student_id = ? AND d.status = 'disbursed'
                    """, (self.student_id,)).fetchone()
                    stats['total_disbursed'] = float(result['total']) if result else 0.0
                except Exception:
                    # Disbursements table may not exist yet
                    stats['total_disbursed'] = 0.0

        except Exception as e:
            logger.error(f"Error fetching stats: {e}")

        return stats

    def _show_recent_activity(self):
        """Show recent activity section"""
        activity_frame = ttk.LabelFrame(self.parent_frame, text="Recent Activity", padding=10)
        activity_frame.pack(fill='both', expand=True, padx=10, pady=10)

        try:
            with get_connection() as conn:
                # Get recent applications and awards
                activities = conn.execute("""
                    SELECT 'application' as type, sa.application_id as id,
                           s.scholarship_name as name, sa.application_date as date, sa.status
                    FROM scholarship_applications sa
                    JOIN scholarships s ON sa.scholarship_id = s.scholarship_id
                    WHERE sa.student_id = ?
                    UNION ALL
                    SELECT 'award' as type, ss.student_scholarship_id as id,
                           s.scholarship_name as name, ss.awarded_date as date, ss.status
                    FROM student_scholarships ss
                    JOIN scholarships s ON ss.scholarship_id = s.scholarship_id
                    WHERE ss.student_id = ?
                    ORDER BY date DESC
                    LIMIT 10
                """, (self.student_id, self.student_id)).fetchall()

                if activities:
                    tree = create_data_table(activity_frame,
                                           ['Type', 'Name', 'Date', 'Status'],
                                           {'Type': 100, 'Name': 300, 'Date': 120, 'Status': 100})

                    for activity in activities:
                        tree.insert('', 'end', values=(
                            activity['type'].title(),
                            activity['name'],
                            format_date(activity['date']),
                            activity['status'].title()
                        ))
                else:
                    ttk.Label(activity_frame, text="No recent activity").pack()

        except Exception as e:
            logger.error(f"Error loading activity: {e}")
            ttk.Label(activity_frame, text="Error loading recent activity", foreground='red').pack()

    def show_scholarships(self):
        """Display available scholarships"""
        clear_frame(self.parent_frame)

        # Title
        title_frame = ttk.Frame(self.parent_frame)
        title_frame.pack(fill='x', padx=10, pady=10)
        ttk.Label(title_frame, text="Available Scholarships", style='Title.TLabel').pack(side='left')
        ttk.Button(title_frame, text="Back to Dashboard", command=self.show_dashboard).pack(side='right')

        # Search and filter
        search_entry, filter_combo = create_search_filter_bar(
            self.parent_frame,
            lambda: self._load_scholarships(search_entry.get(), filter_combo.get() if filter_combo else None),
            ['All', 'Merit-Based', 'Need-Based', 'Athletic', 'Departmental']
        )

        # Scholarships table
        table_frame = ttk.Frame(self.parent_frame)
        table_frame.pack(fill='both', expand=True, padx=10, pady=10)

        columns = ['ID', 'Name', 'Amount', 'Deadline', 'Type', 'Status']
        self.scholarships_tree = create_data_table(table_frame, columns, {
            'ID': 80, 'Name': 250, 'Amount': 100, 'Deadline': 100, 'Type': 120, 'Status': 100
        })

        # Action buttons
        btn_frame = ttk.Frame(self.parent_frame)
        btn_frame.pack(fill='x', padx=10, pady=10)

        ttk.Button(btn_frame, text="View Details", command=self._view_scholarship_details).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Apply", command=self._apply_for_scholarship, style='Success.TButton').pack(side='left', padx=5)

        # Load scholarships
        self._load_scholarships()

    def _load_scholarships(self, search_term: str = '', filter_type: str = 'All'):
        """Load scholarships into table"""
        try:
            # Clear existing items
            for item in self.scholarships_tree.get_children():
                self.scholarships_tree.delete(item)

            scholarships = self.scholarship_manager.get_available_scholarships()

            for scholarship in scholarships:
                # Apply filters
                if search_term and search_term.lower() not in scholarship['name'].lower():
                    continue
                if filter_type and filter_type != 'All':
                    # Would need criteria field to filter by type
                    pass

                # Check if already applied
                has_applied = self._check_application_exists(scholarship['scholarship_id'])
                status = "Applied" if has_applied else "Available"

                self.scholarships_tree.insert('', 'end', values=(
                    scholarship['scholarship_id'],
                    scholarship['name'],
                    format_currency(scholarship['amount']),
                    format_date(scholarship['deadline']),
                    scholarship.get('criteria', 'General')[:20],
                    status
                ))

        except Exception as e:
            logger.error(f"Error loading scholarships: {e}")
            show_error("Error", "Failed to load scholarships")

    def _check_application_exists(self, scholarship_id: str) -> bool:
        """Check if student has already applied for scholarship"""
        try:
            with get_connection() as conn:
                result = conn.execute("""
                    SELECT COUNT(*) as count
                    FROM scholarship_applications
                    WHERE student_id = ? AND scholarship_id = ?
                """, (self.student_id, scholarship_id)).fetchone()
                return result['count'] > 0 if result else False
        except:
            return False

    def _view_scholarship_details(self):
        """View detailed scholarship information"""
        selection = self.scholarships_tree.selection()
        if not selection:
            show_warning("Selection Required", "Please select a scholarship to view details")
            return

        item = self.scholarships_tree.item(selection[0])
        scholarship_id = item['values'][0]

        try:
            with get_connection() as conn:
                scholarship = conn.execute("""
                    SELECT * FROM scholarships WHERE scholarship_id = ?
                """, (scholarship_id,)).fetchone()

                if scholarship:
                    self._show_scholarship_details_window(dict(scholarship))

        except Exception as e:
            logger.error(f"Error fetching scholarship details: {e}")
            show_error("Error", "Failed to load scholarship details")

    def _show_scholarship_details_window(self, scholarship: Dict):
        """Show scholarship details in popup window"""
        details_window = tk.Toplevel(self.parent_frame)
        details_window.title(f"Scholarship Details - {scholarship['scholarship_name']}")
        details_window.geometry("600x500")

        # Create scrollable frame
        scrollable_frame, canvas, scrollbar = create_scrollable_frame(details_window)
        canvas.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Title
        ttk.Label(scrollable_frame, text=scholarship['scholarship_name'],
                 font=('Arial', 14, 'bold')).pack(pady=10)

        # Details
        details = [
            ("Amount", format_currency(scholarship['amount'])),
            ("Academic Year", scholarship.get('academic_year', 'N/A')),
            ("Deadline", format_date(scholarship.get('deadline', 'N/A'))),
            ("Description", scholarship.get('description', 'No description available')),
            ("Criteria", scholarship.get('criteria', 'See financial aid office')),
            ("Status", "Active" if scholarship.get('is_active') else "Inactive")
        ]

        for label, value in details:
            frame = ttk.Frame(scrollable_frame)
            frame.pack(fill='x', padx=20, pady=5)
            ttk.Label(frame, text=f"{label}:", font=('Arial', 10, 'bold')).pack(anchor='w')
            ttk.Label(frame, text=str(value), wraplength=500).pack(anchor='w', padx=20)

        # Apply button
        ttk.Button(scrollable_frame, text="Apply for This Scholarship",
                  command=lambda: [details_window.destroy(), self._apply_for_scholarship()],
                  style='Success.TButton').pack(pady=20)

    def _apply_for_scholarship(self):
        """Apply for selected scholarship"""
        selection = self.scholarships_tree.selection()
        if not selection:
            show_warning("Selection Required", "Please select a scholarship to apply for")
            return

        item = self.scholarships_tree.item(selection[0])
        scholarship_id = item['values'][0]
        scholarship_name = item['values'][1]

        # Check if already applied
        if self._check_application_exists(scholarship_id):
            show_warning("Already Applied", "You have already submitted an application for this scholarship")
            return

        # Show application form
        self._show_application_form(scholarship_id, scholarship_name)

    def _show_application_form(self, scholarship_id: str, scholarship_name: str):
        """Show scholarship application form"""
        app_window = tk.Toplevel(self.parent_frame)
        app_window.title(f"Apply for {scholarship_name}")
        app_window.geometry("700x600")

        # Title
        ttk.Label(app_window, text=f"Scholarship Application", style='Title.TLabel').pack(pady=10)
        ttk.Label(app_window, text=scholarship_name, font=('Arial', 12)).pack()

        # Create scrollable frame
        scrollable_frame, canvas, scrollbar = create_scrollable_frame(app_window)
        canvas.pack(side='left', fill='both', expand=True, padx=10, pady=10)
        scrollbar.pack(side='right', fill='y')

        # Application fields
        fields = {}

        # Essay
        ttk.Label(scrollable_frame, text="Personal Statement / Essay *", font=('Arial', 10, 'bold')).pack(anchor='w', pady=(10, 5))
        essay_text = scrolledtext.ScrolledText(scrollable_frame, width=60, height=10)
        essay_text.pack(fill='x', pady=5)
        fields['essay'] = essay_text

        # GPA
        gpa_frame = ttk.Frame(scrollable_frame)
        gpa_frame.pack(fill='x', pady=10)
        ttk.Label(gpa_frame, text="GPA *", font=('Arial', 10, 'bold')).pack(side='left')
        gpa_var = tk.StringVar()
        gpa_entry = ttk.Entry(gpa_frame, textvariable=gpa_var, width=10)
        gpa_entry.pack(side='left', padx=10)
        fields['gpa'] = gpa_var

        # Expected graduation
        grad_frame = ttk.Frame(scrollable_frame)
        grad_frame.pack(fill='x', pady=10)
        ttk.Label(grad_frame, text="Expected Graduation *", font=('Arial', 10, 'bold')).pack(side='left')
        grad_var = tk.StringVar()
        grad_entry = ttk.Entry(grad_frame, textvariable=grad_var, width=15)
        grad_entry.pack(side='left', padx=10)
        ttk.Label(grad_frame, text="(YYYY-MM-DD)", foreground='gray').pack(side='left')
        fields['graduation'] = grad_var

        # References
        ttk.Label(scrollable_frame, text="Reference Name", font=('Arial', 10, 'bold')).pack(anchor='w', pady=(10, 5))
        ref_name_var = tk.StringVar()
        ttk.Entry(scrollable_frame, textvariable=ref_name_var, width=40).pack(fill='x', pady=5)
        fields['reference_name'] = ref_name_var

        ttk.Label(scrollable_frame, text="Reference Email", font=('Arial', 10, 'bold')).pack(anchor='w', pady=(10, 5))
        ref_email_var = tk.StringVar()
        ttk.Entry(scrollable_frame, textvariable=ref_email_var, width=40).pack(fill='x', pady=5)
        fields['reference_email'] = ref_email_var

        # Additional documents note
        ttk.Label(scrollable_frame, text="\nNote: Transcripts and additional documents can be uploaded after submission.",
                 font=('Arial', 9), foreground='blue', wraplength=600).pack(pady=10)

        # Buttons
        btn_frame = ttk.Frame(scrollable_frame)
        btn_frame.pack(pady=20)

        def submit_application():
            if self._validate_and_submit_application(scholarship_id, fields, app_window):
                app_window.destroy()

        ttk.Button(btn_frame, text="Submit Application", command=submit_application,
                  style='Success.TButton').pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Cancel", command=app_window.destroy).pack(side='left', padx=5)

    def _validate_and_submit_application(self, scholarship_id: str, fields: Dict, window) -> bool:
        """Validate and submit scholarship application"""
        try:
            # Validate student ID
            if not self.student_id:
                show_error("Student ID Not Found",
                          "Unable to determine your student ID. Please ensure you are logged in as a student.\n\n"
                          "If you continue to see this error, contact the system administrator.")
                logger.error(f"Student ID is None for user: {self.current_user}")
                return False

            # Get values
            essay = fields['essay'].get('1.0', 'end-1c').strip()
            gpa = fields['gpa'].get().strip()
            graduation = fields['graduation'].get().strip()

            # Validate required fields
            if not essay:
                show_error("Validation Error", "Personal statement is required")
                return False

            if not gpa:
                show_error("Validation Error", "GPA is required")
                return False

            try:
                gpa_float = float(gpa)
                if gpa_float < 0 or gpa_float > 4.0:
                    show_error("Validation Error", "GPA must be between 0.0 and 4.0")
                    return False
            except ValueError:
                show_error("Validation Error", "Invalid GPA format")
                return False

            if not graduation or not validate_date(graduation):
                show_error("Validation Error", "Valid graduation date is required (YYYY-MM-DD)")
                return False

            # Submit application
            application_data = {
                'essay': essay,
                'gpa': gpa_float,
                'expected_graduation': graduation,
                'reference_name': fields['reference_name'].get(),
                'reference_email': fields['reference_email'].get()
            }

            application_id = self.scholarship_manager.submit_application(
                scholarship_id=scholarship_id,
                student_id=self.student_id,
                academic_year=get_current_academic_year(),
                application_data=application_data
            )

            if application_id:
                log_activity('create', 'scholarship_application', application_id, {
                    'scholarship_id': scholarship_id,
                    'student_id': self.student_id
                })

                show_success("Success", "Your scholarship application has been submitted successfully!")

                # Send confirmation email
                try:
                    user_dict = self.current_user.to_dict() if hasattr(self.current_user, 'to_dict') else self.current_user
                    email = user_dict.get('email')
                    if email:
                        send_email(
                            to=email,
                            subject="Scholarship Application Submitted",
                            body=f"Your application for scholarship ID {scholarship_id} has been submitted successfully."
                        )
                except Exception as e:
                    logger.error(f"Failed to send confirmation email: {e}")

                # Refresh scholarships list
                self.show_scholarships()
                return True
            else:
                show_error("Error", "Failed to submit application. Please try again.")
                return False

        except Exception as e:
            logger.error(f"Error submitting application: {e}")
            show_error("Error", f"An error occurred: {str(e)}")
            return False

    def show_apply_aid(self):
        """Show financial aid application form"""
        clear_frame(self.parent_frame)

        # Title
        title_frame = ttk.Frame(self.parent_frame)
        title_frame.pack(fill='x', padx=10, pady=10)
        ttk.Label(title_frame, text="Apply for Financial Aid", style='Title.TLabel').pack(side='left')
        ttk.Button(title_frame, text="Back to Dashboard", command=self.show_dashboard).pack(side='right')

        # Check if student ID exists
        if not self.student_id:
            error_frame = ttk.Frame(self.parent_frame, relief='solid', borderwidth=2)
            error_frame.pack(fill='both', expand=True, padx=10, pady=10)
            ttk.Label(error_frame,
                     text="⚠ Student ID Not Found",
                     font=('Arial', 14, 'bold'),
                     foreground='red').pack(pady=(20, 10))
            ttk.Label(error_frame,
                     text="Unable to determine your student ID. This may occur if:\n\n"
                          "• You are logged in as an admin or staff member (not a student)\n"
                          "• Your student account has not been properly configured\n"
                          "• There is a database issue with your user record\n\n"
                          "Please contact your system administrator for assistance.",
                     wraplength=600,
                     justify='left').pack(padx=20, pady=20)
            ttk.Button(error_frame, text="Back to Dashboard",
                      command=self.show_dashboard).pack(pady=20)
            logger.error(f"Student ID is None when accessing financial aid application. User: {self.current_user}")
            return

        # Info message
        info_frame = ttk.Frame(self.parent_frame, relief='solid', borderwidth=1)
        info_frame.pack(fill='x', padx=10, pady=10)
        ttk.Label(info_frame, text="ℹ Complete this form to apply for financial aid. FAFSA data can be imported if available.",
                 foreground='blue', wraplength=700).pack(padx=10, pady=10)

        # Check existing application
        existing_app = self._check_existing_aid_application()
        if existing_app:
            ttk.Label(self.parent_frame,
                     text=f"You have an existing application (Status: {existing_app['status']})",
                     font=('Arial', 11, 'bold'), foreground='orange').pack(pady=10)

        # Simple aid application form
        form_frame = ttk.LabelFrame(self.parent_frame, text="Financial Aid Application", padding=20)
        form_frame.pack(fill='both', expand=True, padx=10, pady=10)

        fields = {}

        # Academic year
        year_frame = ttk.Frame(form_frame)
        year_frame.pack(fill='x', pady=10)
        ttk.Label(year_frame, text="Academic Year:", width=20).pack(side='left')
        year_var = tk.StringVar(value=get_current_academic_year())
        ttk.Combobox(year_frame, textvariable=year_var, values=get_academic_year_list(), state='readonly', width=15).pack(side='left')
        fields['academic_year'] = year_var

        # Aid type
        type_frame = ttk.Frame(form_frame)
        type_frame.pack(fill='x', pady=10)
        ttk.Label(type_frame, text="Aid Type Requested:", width=20).pack(side='left')
        type_var = tk.StringVar(value='Grant')
        ttk.Combobox(type_frame, textvariable=type_var, values=['Grant', 'Loan', 'Work-Study', 'Emergency Aid'], state='readonly', width=20).pack(side='left')
        fields['aid_type'] = type_var

        # Household income
        income_frame = ttk.Frame(form_frame)
        income_frame.pack(fill='x', pady=10)
        ttk.Label(income_frame, text="Household Income:", width=20).pack(side='left')
        income_var = tk.StringVar()
        ttk.Entry(income_frame, textvariable=income_var, width=20).pack(side='left')
        ttk.Label(income_frame, text="(Annual, USD)", foreground='gray').pack(side='left', padx=5)
        fields['income'] = income_var

        # Number of dependents
        dep_frame = ttk.Frame(form_frame)
        dep_frame.pack(fill='x', pady=10)
        ttk.Label(dep_frame, text="Number of Dependents:", width=20).pack(side='left')
        dep_var = tk.StringVar(value='0')
        ttk.Spinbox(dep_frame, from_=0, to=10, textvariable=dep_var, width=10).pack(side='left')
        fields['dependents'] = dep_var

        # Additional information
        ttk.Label(form_frame, text="Additional Information / Special Circumstances:", font=('Arial', 10, 'bold')).pack(anchor='w', pady=(20, 5))
        info_text = scrolledtext.ScrolledText(form_frame, height=6, width=70)
        info_text.pack(fill='x', pady=5)
        fields['additional_info'] = info_text

        # Buttons
        btn_frame = ttk.Frame(form_frame)
        btn_frame.pack(pady=20)

        def submit_aid_application():
            if self._submit_aid_application(fields):
                self.show_dashboard()

        ttk.Button(btn_frame, text="Submit Application", command=submit_aid_application, style='Success.TButton').pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.show_dashboard).pack(side='left', padx=5)

    def _check_existing_aid_application(self) -> Optional[Dict]:
        """Check for existing aid application"""
        try:
            with get_connection() as conn:
                try:
                    app = conn.execute("""
                        SELECT * FROM financial_aid_applications
                        WHERE student_id = ? AND academic_year = ?
                        ORDER BY application_date DESC
                        LIMIT 1
                    """, (self.student_id, get_current_academic_year())).fetchone()
                    return dict(app) if app else None
                except Exception as e:
                    if "no such table" in str(e):
                        # Table doesn't exist yet - no existing application
                        return None
                    raise
        except Exception as e:
            logger.error(f"Error checking aid application: {e}")
            return None

    def _submit_aid_application(self, fields: Dict) -> bool:
        """Submit financial aid application"""
        try:
            # Validate student ID
            if not self.student_id:
                show_error("Student ID Not Found",
                          "Unable to determine your student ID. Please ensure you are logged in as a student.\n\n"
                          "If you continue to see this error, contact the system administrator.")
                logger.error(f"Student ID is None for user: {self.current_user}")
                return False

            # Validate income
            income_str = fields['income'].get().strip()
            if not income_str:
                show_error("Validation Error", "Household income is required")
                return False

            try:
                income = float(income_str.replace(',', ''))
            except ValueError:
                show_error("Validation Error", "Invalid income format")
                return False

            # Prepare application data
            app_data = {
                'academic_year': fields['academic_year'].get(),
                'aid_type': fields['aid_type'].get(),
                'household_income': income,
                'dependents': int(fields['dependents'].get()),
                'additional_info': fields['additional_info'].get('1.0', 'end-1c').strip()
            }

            # Submit via manager
            app_id = self.aid_manager.create_application(
                student_id=self.student_id,
                academic_year=app_data['academic_year'],
                application_data=app_data
            )

            if app_id:
                log_activity('create', 'financial_aid_application', app_id, {
                    'student_id': self.student_id,
                    'academic_year': app_data['academic_year']
                })

                show_success("Success", "Your financial aid application has been submitted successfully!")

                # Send confirmation email
                try:
                    user_dict = self.current_user.to_dict() if hasattr(self.current_user, 'to_dict') else self.current_user
                    email = user_dict.get('email')
                    if email:
                        send_email(
                            to=email,
                            subject="Financial Aid Application Submitted",
                            body=f"Your financial aid application for {app_data['academic_year']} has been submitted."
                        )
                except Exception as e:
                    logger.error(f"Failed to send confirmation email: {e}")

                return True
            else:
                show_error("Error", "Failed to submit application")
                return False

        except Exception as e:
            logger.error(f"Error submitting aid application: {e}")
            show_error("Error", f"An error occurred: {str(e)}")
            return False

    def show_my_applications(self):
        """Show student's applications"""
        clear_frame(self.parent_frame)

        # Title
        title_frame = ttk.Frame(self.parent_frame)
        title_frame.pack(fill='x', padx=10, pady=10)
        ttk.Label(title_frame, text="My Applications", style='Title.TLabel').pack(side='left')
        ttk.Button(title_frame, text="Back to Dashboard", command=self.show_dashboard).pack(side='right')

        # Tabs for different application types
        notebook = ttk.Notebook(self.parent_frame)
        notebook.pack(fill='both', expand=True, padx=10, pady=10)

        # Scholarship applications tab
        scholarship_frame = ttk.Frame(notebook)
        notebook.add(scholarship_frame, text="Scholarship Applications")
        self._show_scholarship_applications(scholarship_frame)

        # Financial aid applications tab
        aid_frame = ttk.Frame(notebook)
        notebook.add(aid_frame, text="Financial Aid Applications")
        self._show_aid_applications(aid_frame)

    def _show_scholarship_applications(self, parent):
        """Show scholarship applications in tab"""
        try:
            with get_connection() as conn:
                applications = conn.execute("""
                    SELECT sa.*, s.scholarship_name, s.amount
                    FROM scholarship_applications sa
                    JOIN scholarships s ON sa.scholarship_id = s.scholarship_id
                    WHERE sa.student_id = ?
                    ORDER BY sa.application_date DESC
                """, (self.student_id,)).fetchall()

                if applications:
                    columns = ['App ID', 'Scholarship', 'Amount', 'Submitted', 'Status']
                    tree = create_data_table(parent, columns, {
                        'App ID': 80, 'Scholarship': 250, 'Amount': 100, 'Submitted': 120, 'Status': 100
                    })

                    for app in applications:
                        tree.insert('', 'end', values=(
                            app['application_id'],
                            app['scholarship_name'],
                            format_currency(app['amount']),
                            format_date(app['submitted_date']),
                            app['status'].title()
                        ), tags=(app['status'],))

                    # Status-based colors
                    tree.tag_configure('pending', foreground=get_status_color('pending'))
                    tree.tag_configure('approved', foreground=get_status_color('approved'))
                    tree.tag_configure('denied', foreground=get_status_color('denied'))
                else:
                    ttk.Label(parent, text="No scholarship applications found").pack(expand=True)

        except Exception as e:
            logger.error(f"Error loading scholarship applications: {e}")
            ttk.Label(parent, text="Error loading applications", foreground='red').pack()

    def _show_aid_applications(self, parent):
        """Show financial aid applications in tab"""
        try:
            with get_connection() as conn:
                applications = conn.execute("""
                    SELECT * FROM student_financial_aid
                    WHERE student_id = ?
                    ORDER BY application_date DESC
                """, (self.student_id,)).fetchall()

                if applications:
                    columns = ['Aid ID', 'Type', 'Awarded', 'Disbursed', 'Status', 'Applied']
                    tree = create_data_table(parent, columns, {
                        'Aid ID': 80, 'Type': 150, 'Awarded': 100, 'Disbursed': 100, 'Status': 100, 'Applied': 120
                    })

                    for app in applications:
                        tree.insert('', 'end', values=(
                            app['aid_id'],
                            app.get('aid_type_id', 'N/A'),
                            format_currency(app.get('awarded_amount', 0)),
                            format_currency(app.get('disbursed_amount', 0)),
                            app['status'].title(),
                            format_date(app.get('application_date'))
                        ))
                else:
                    ttk.Label(parent, text="No financial aid applications found").pack(expand=True)

        except Exception as e:
            logger.error(f"Error loading aid applications: {e}")
            ttk.Label(parent, text="Error loading applications", foreground='red').pack()

    def show_my_awards(self):
        """Show student's awards"""
        clear_frame(self.parent_frame)

        # Title
        title_frame = ttk.Frame(self.parent_frame)
        title_frame.pack(fill='x', padx=10, pady=10)
        ttk.Label(title_frame, text="My Awards", style='Title.TLabel').pack(side='left')
        ttk.Button(title_frame, text="Back to Dashboard", command=self.show_dashboard).pack(side='right')

        # Summary stats
        stats_frame = ttk.LabelFrame(self.parent_frame, text="Award Summary", padding=10)
        stats_frame.pack(fill='x', padx=10, pady=10)

        try:
            stats = self._get_award_stats()

            summary_text = f"""
Total Awards: {format_currency(stats['total_awarded'])}
Total Disbursed: {format_currency(stats['total_disbursed'])}
Remaining: {format_currency(stats['remaining'])}
Active Awards: {stats['active_count']}
            """
            ttk.Label(stats_frame, text=summary_text, font=('Arial', 10)).pack()

        except Exception as e:
            logger.error(f"Error loading award stats: {e}")
            ttk.Label(stats_frame, text="Error loading statistics", foreground='red').pack()

        # Awards table
        table_frame = ttk.Frame(self.parent_frame)
        table_frame.pack(fill='both', expand=True, padx=10, pady=10)

        columns = ['Award ID', 'Type', 'Name', 'Amount', 'Awarded Date', 'Status']
        tree = create_data_table(table_frame, columns, {
            'Award ID': 80, 'Type': 100, 'Name': 200, 'Amount': 100, 'Awarded Date': 120, 'Status': 100
        })

        self._load_student_awards(tree)

    def _get_award_stats(self) -> Dict[str, Any]:
        """Get award statistics"""
        stats = {
            'total_awarded': 0.0,
            'total_disbursed': 0.0,
            'remaining': 0.0,
            'active_count': 0
        }

        try:
            with get_connection() as conn:
                # Scholarship awards
                result = conn.execute("""
                    SELECT COALESCE(SUM(amount), 0) as total, COUNT(*) as count
                    FROM student_scholarships
                    WHERE student_id = ? AND status = 'awarded'
                """, (self.student_id,)).fetchone()
                stats['total_awarded'] = float(result['total']) if result else 0.0
                stats['active_count'] = result['count'] if result else 0

                # Disbursements
                try:
                    result = conn.execute("""
                        SELECT COALESCE(SUM(d.amount), 0) as total
                        FROM disbursements d
                        WHERE d.student_id = ? AND d.status = 'disbursed'
                    """, (self.student_id,)).fetchone()
                    stats['total_disbursed'] = float(result['total']) if result else 0.0
                except Exception:
                    # Disbursements table may not exist yet
                    stats['total_disbursed'] = 0.0

                stats['remaining'] = stats['total_awarded'] - stats['total_disbursed']

        except Exception as e:
            logger.error(f"Error fetching award stats: {e}")

        return stats

    def _load_student_awards(self, tree):
        """Load student awards into tree"""
        try:
            with get_connection() as conn:
                # Scholarship awards
                scholarships = conn.execute("""
                    SELECT ss.student_scholarship_id, 'Scholarship' as type,
                           s.scholarship_name as name, ss.amount, ss.awarded_date, ss.status
                    FROM student_scholarships ss
                    JOIN scholarships s ON ss.scholarship_id = s.scholarship_id
                    WHERE ss.student_id = ?
                    ORDER BY ss.awarded_date DESC
                """, (self.student_id,)).fetchall()

                for award in scholarships:
                    tree.insert('', 'end', values=(
                        award['student_scholarship_id'],
                        award['type'],
                        award['name'],
                        format_currency(award['amount']),
                        format_date(award['awarded_date']),
                        award['status'].title()
                    ))

                # Financial aid awards
                aid = conn.execute("""
                    SELECT sfa.aid_id, 'Financial Aid' as type,
                           fat.aid_name as name, sfa.awarded_amount, sfa.approval_date, sfa.status
                    FROM student_financial_aid sfa
                    LEFT JOIN financial_aid_types fat ON sfa.aid_type_id = fat.aid_type_id
                    WHERE sfa.student_id = ? AND sfa.status = 'approved'
                    ORDER BY sfa.approval_date DESC
                """, (self.student_id,)).fetchall()

                for award in aid:
                    tree.insert('', 'end', values=(
                        award['aid_id'],
                        award['type'],
                        award['name'] or 'General Aid',
                        format_currency(award['awarded_amount']),
                        format_date(award['approval_date']),
                        award['status'].title()
                    ))

        except Exception as e:
            logger.error(f"Error loading awards: {e}")
            show_error("Error", "Failed to load awards")
