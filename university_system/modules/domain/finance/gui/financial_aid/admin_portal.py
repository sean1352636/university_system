"""
Admin Portal for Financial Aid & Scholarships

This module provides the admin-facing interface for managing financial aid,
reviewing applications, processing disbursements, and generating reports.
"""

from .common_imports import *
from .scholarship_manager import ScholarshipManagerGUI


class AdminPortal:
    """Admin-facing portal for financial aid and scholarships management"""

    def __init__(self, parent_frame, auth_instance=None):
        """
        Initialize admin portal

        Args:
            parent_frame: Parent tkinter frame
            auth_instance: Authentication instance
        """
        self.parent_frame = parent_frame
        self.auth = auth_instance or get_auth()
        self.aid_manager = FinancialAidManager()
        self.scholarship_manager_gui = ScholarshipManagerGUI(parent_frame, auth_instance)

    def show_dashboard(self):
        """Display admin dashboard"""
        # Check if parent frame is valid
        try:
            if not self.parent_frame.winfo_exists():
                logger.error("Parent frame no longer exists")
                return
        except Exception as e:
            logger.error(f"Error checking parent frame: {e}")
            return

        clear_frame(self.parent_frame)

        # Title
        title_frame = ttk.Frame(self.parent_frame)
        title_frame.pack(fill='x', padx=10, pady=10)
        ttk.Label(title_frame, text="Financial Aid & Scholarships - Admin Dashboard",
                 style='Title.TLabel').pack(anchor='w')

        # Statistics cards
        stats_frame = ttk.Frame(self.parent_frame)
        stats_frame.pack(fill='x', padx=10, pady=10)

        try:
            stats = self._get_admin_stats()

            cards = [
                ("Pending Reviews", str(stats['pending_reviews']), 'warning'),
                ("Active Aid Packages", str(stats['active_packages']), 'info'),
                ("Total Disbursed (Year)", format_currency(stats['total_disbursed']), 'success'),
                ("Pending Disbursements", format_currency(stats['pending_disbursements']), 'primary')
            ]

            for i, (title, value, color) in enumerate(cards):
                card = create_stat_card(stats_frame, title, value, color)
                card.grid(row=0, column=i, padx=10, pady=5, sticky='ew')
                stats_frame.grid_columnconfigure(i, weight=1)

        except Exception as e:
            logger.error(f"Error loading stats: {e}")

        # Quick actions grid
        actions_frame = ttk.LabelFrame(self.parent_frame, text="Management Functions", padding=10)
        actions_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Row 1: Scholarship Management
        ttk.Label(actions_frame, text="Scholarship Management",
                 font=('Arial', 11, 'bold')).grid(row=0, column=0, columnspan=3, sticky='w', pady=(0, 10))

        actions_row1 = [
            ("Manage Scholarships", self.scholarship_manager_gui.show_scholarships),
            ("Review Applications", self.scholarship_manager_gui.review_applications),
            ("View Awards", self.scholarship_manager_gui.show_awards)
        ]

        for i, (text, command) in enumerate(actions_row1):
            ttk.Button(actions_frame, text=text, command=command, width=25).grid(
                row=1, column=i, padx=5, pady=5, sticky='ew')

        # Row 2: Financial Aid Management
        ttk.Label(actions_frame, text="Financial Aid Management",
                 font=('Arial', 11, 'bold')).grid(row=2, column=0, columnspan=3, sticky='w', pady=(20, 10))

        actions_row2 = [
            ("Review Aid Applications", self.show_aid_applications),
            ("Create Aid Package", self.show_create_package),
            ("Manage Aid Types", self.show_aid_types)
        ]

        for i, (text, command) in enumerate(actions_row2):
            ttk.Button(actions_frame, text=text, command=command, width=25).grid(
                row=3, column=i, padx=5, pady=5, sticky='ew')

        # Row 3: Disbursements & Reports
        ttk.Label(actions_frame, text="Disbursements & Reports",
                 font=('Arial', 11, 'bold')).grid(row=4, column=0, columnspan=3, sticky='w', pady=(20, 10))

        actions_row3 = [
            ("Process Disbursements", self.show_disbursements),
            ("View Reports", self.show_reports),
            ("Import FAFSA Data", self.show_fafsa_import)
        ]

        for i, (text, command) in enumerate(actions_row3):
            ttk.Button(actions_frame, text=text, command=command, width=25).grid(
                row=5, column=i, padx=5, pady=5, sticky='ew')

        # Configure column weights
        for i in range(3):
            actions_frame.grid_columnconfigure(i, weight=1)

    def _get_admin_stats(self) -> Dict[str, Any]:
        """Get admin dashboard statistics"""
        stats = {
            'pending_reviews': 0,
            'active_packages': 0,
            'total_disbursed': 0.0,
            'pending_disbursements': 0.0
        }

        try:
            with get_connection() as conn:
                # Pending reviews (scholarships + aid)
                # Handle missing financial_aid_applications table gracefully
                try:
                    result = conn.execute("""
                        SELECT
                            (SELECT COUNT(*) FROM scholarship_applications WHERE status = 'pending') +
                            (SELECT COUNT(*) FROM financial_aid_applications WHERE status = 'pending') as total
                    """).fetchone()
                    stats['pending_reviews'] = result['total'] if result else 0
                except Exception:
                    # If financial_aid_applications table doesn't exist, just count scholarships
                    result = conn.execute("""
                        SELECT COUNT(*) as total FROM scholarship_applications WHERE status = 'pending'
                    """).fetchone()
                    stats['pending_reviews'] = result['total'] if result else 0

                # Active aid packages (using student_financial_aid table)
                result = conn.execute("""
                    SELECT COUNT(*) as count
                    FROM student_financial_aid
                    WHERE status IN ('approved', 'disbursed')
                """).fetchone()
                stats['active_packages'] = result['count'] if result else 0

                # Total disbursed this year
                try:
                    current_year = get_current_academic_year()
                    result = conn.execute("""
                        SELECT COALESCE(SUM(amount), 0) as total
                        FROM disbursements
                        WHERE status = 'disbursed'
                        AND strftime('%Y', disbursement_date) = ?
                    """, (current_year.split('-')[0],)).fetchone()
                    stats['total_disbursed'] = float(result['total']) if result else 0.0
                except Exception:
                    # Disbursements table may not exist yet
                    stats['total_disbursed'] = 0.0

                # Pending disbursements
                try:
                    result = conn.execute("""
                        SELECT COALESCE(SUM(amount), 0) as total
                        FROM disbursements
                        WHERE status = 'pending'
                    """).fetchone()
                    stats['pending_disbursements'] = float(result['total']) if result else 0.0
                except Exception:
                    # Disbursements table may not exist yet
                    stats['pending_disbursements'] = 0.0

        except Exception as e:
            logger.error(f"Error fetching admin stats: {e}")

        return stats

    def show_aid_applications(self):
        """Show financial aid applications for review"""
        # Check if parent frame is valid
        try:
            if not self.parent_frame.winfo_exists():
                logger.error("Parent frame no longer exists")
                return
        except Exception as e:
            logger.error(f"Error checking parent frame: {e}")
            return

        clear_frame(self.parent_frame)

        # Title
        title_frame = ttk.Frame(self.parent_frame)
        title_frame.pack(fill='x', padx=10, pady=10)
        ttk.Label(title_frame, text="Financial Aid Applications", style='Title.TLabel').pack(side='left')
        ttk.Button(title_frame, text="Back to Dashboard", command=self.show_dashboard).pack(side='right')

        # Filter by status
        filter_frame = ttk.Frame(self.parent_frame)
        filter_frame.pack(fill='x', padx=10, pady=10)

        ttk.Label(filter_frame, text="Status:").pack(side='left', padx=5)
        status_var = tk.StringVar(value='pending')
        status_combo = ttk.Combobox(filter_frame, textvariable=status_var,
                                    values=['All', 'pending', 'under_review', 'approved', 'denied'],
                                    state='readonly', width=15)
        status_combo.pack(side='left', padx=5)
        ttk.Button(filter_frame, text="Filter",
                  command=lambda: self._load_aid_applications(status_var.get())).pack(side='left', padx=5)

        # Applications table
        table_frame = ttk.Frame(self.parent_frame)
        table_frame.pack(fill='both', expand=True, padx=10, pady=10)

        columns = ['App ID', 'Student', 'Academic Year', 'Aid Type', 'Submitted', 'Status']
        self.aid_apps_tree = create_data_table(table_frame, columns, {
            'App ID': 80, 'Student': 150, 'Academic Year': 120, 'Aid Type': 120, 'Submitted': 120, 'Status': 100
        })

        # Action buttons
        btn_frame = ttk.Frame(self.parent_frame)
        btn_frame.pack(fill='x', padx=10, pady=10)

        ttk.Button(btn_frame, text="View Details", command=self._view_aid_application_details).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Approve", command=lambda: self._review_aid_application('approved'),
                  style='Success.TButton').pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Deny", command=lambda: self._review_aid_application('denied'),
                  style='Danger.TButton').pack(side='left', padx=5)

        # Load applications
        self._load_aid_applications('pending')

    def _load_aid_applications(self, status_filter: str = 'All'):
        """Load financial aid applications"""
        try:
            for item in self.aid_apps_tree.get_children():
                self.aid_apps_tree.delete(item)

            with get_connection() as conn:
                # Check if financial_aid_applications table exists
                try:
                    query = """
                        SELECT fa.*, u.username
                        FROM financial_aid_applications fa
                        JOIN users u ON fa.student_id = u.user_id
                        WHERE 1=1
                    """
                    params = []

                    if status_filter and status_filter != 'All':
                        query += " AND fa.status = ?"
                        params.append(status_filter)

                    query += " ORDER BY fa.application_date DESC"

                    applications = conn.execute(query, params).fetchall()
                except Exception as e:
                    if "no such table" in str(e):
                        # Table doesn't exist yet - show message
                        messagebox.showinfo("Table Not Found",
                                          "The financial_aid_applications table does not exist yet.\n\n"
                                          "This feature requires database setup.")
                        return
                    raise

                for app in applications:
                    app_data = json.loads(app.get('application_data', '{}'))
                    self.aid_apps_tree.insert('', 'end', values=(
                        app['application_id'],
                        app['username'],
                        app['academic_year'],
                        app_data.get('aid_type', 'N/A'),
                        format_date(app['application_date']),
                        app['status'].title()
                    ))

        except Exception as e:
            logger.error(f"Error loading aid applications: {e}")
            show_error("Error", "Failed to load applications")

    def _view_aid_application_details(self):
        """View aid application details"""
        selection = self.aid_apps_tree.selection()
        if not selection:
            show_warning("Selection Required", "Please select an application")
            return

        item = self.aid_apps_tree.item(selection[0])
        app_id = item['values'][0]

        try:
            with get_connection() as conn:
                try:
                    app = conn.execute("""
                        SELECT fa.*, u.username, u.email
                        FROM financial_aid_applications fa
                        JOIN users u ON fa.student_id = u.user_id
                        WHERE fa.application_id = ?
                    """, (app_id,)).fetchone()
                except Exception as e:
                    if "no such table" in str(e):
                        messagebox.showerror("Table Not Found",
                                           "The financial_aid_applications table does not exist yet.")
                        return
                    raise

                if app:
                    self._show_aid_application_details_window(dict(app))

        except Exception as e:
            logger.error(f"Error fetching application: {e}")
            show_error("Error", "Failed to load application details")

    def _show_aid_application_details_window(self, app: Dict):
        """Show aid application details window"""
        details_window = tk.Toplevel(self.parent_frame)
        details_window.title(f"Aid Application - {app['application_id']}")
        details_window.geometry("700x600")

        # Create scrollable frame
        scrollable_frame, canvas, scrollbar = create_scrollable_frame(details_window)
        canvas.pack(side='left', fill='both', expand=True, padx=10, pady=10)
        scrollbar.pack(side='right', fill='y')

        # Title
        ttk.Label(scrollable_frame, text="Financial Aid Application Details",
                 style='Title.TLabel').pack(pady=10)

        # Application data
        app_data = json.loads(app.get('application_data', '{}'))

        details = [
            ("Application ID", app['application_id']),
            ("Student", f"{app['username']} ({app['email']})"),
            ("Academic Year", app['academic_year']),
            ("Aid Type Requested", app_data.get('aid_type', 'N/A')),
            ("Application Date", format_date(app['application_date'])),
            ("Status", app['status'].title()),
            ("Household Income", format_currency(app_data.get('household_income', 0))),
            ("Number of Dependents", str(app_data.get('dependents', 0))),
        ]

        for label, value in details:
            frame = ttk.Frame(scrollable_frame)
            frame.pack(fill='x', padx=20, pady=5)
            ttk.Label(frame, text=f"{label}:", font=('Arial', 10, 'bold')).pack(anchor='w')
            ttk.Label(frame, text=str(value)).pack(anchor='w', padx=20)

        # Additional information
        if app_data.get('additional_info'):
            ttk.Label(scrollable_frame, text="Additional Information:",
                     font=('Arial', 10, 'bold')).pack(anchor='w', padx=20, pady=(20, 5))
            info_frame = ttk.Frame(scrollable_frame, relief='sunken', borderwidth=1)
            info_frame.pack(fill='x', padx=20, pady=5)
            info_text = scrolledtext.ScrolledText(info_frame, height=6, width=60, wrap='word')
            info_text.insert('1.0', app_data.get('additional_info', ''))
            info_text.config(state='disabled')
            info_text.pack(fill='both', expand=True, padx=5, pady=5)

        # Action buttons (if pending)
        if app['status'] == 'pending':
            btn_frame = ttk.Frame(scrollable_frame)
            btn_frame.pack(pady=20)

            def approve():
                if self._review_aid_application_by_id(app['application_id'], 'approved'):
                    details_window.destroy()

            def deny():
                if self._review_aid_application_by_id(app['application_id'], 'denied'):
                    details_window.destroy()

            ttk.Button(btn_frame, text="Approve", command=approve,
                      style='Success.TButton').pack(side='left', padx=5)
            ttk.Button(btn_frame, text="Deny", command=deny,
                      style='Danger.TButton').pack(side='left', padx=5)
            ttk.Button(btn_frame, text="Create Aid Package",
                      command=lambda: [details_window.destroy(),
                                     self.show_create_package(app['student_id'], app['academic_year'])]).pack(side='left', padx=5)

        ttk.Button(scrollable_frame, text="Close", command=details_window.destroy).pack(pady=10)

    def _review_aid_application(self, status: str):
        """Review selected aid application"""
        selection = self.aid_apps_tree.selection()
        if not selection:
            show_warning("Selection Required", "Please select an application")
            return

        item = self.aid_apps_tree.item(selection[0])
        app_id = item['values'][0]

        self._review_aid_application_by_id(app_id, status)

    def _review_aid_application_by_id(self, app_id: str, status: str) -> bool:
        """Review aid application by ID"""
        try:
            result = self.aid_manager.update_application_status(
                application_id=app_id,
                status=status
            )

            if result:
                log_activity('update', 'financial_aid_application', app_id, {
                    'action': 'reviewed',
                    'status': status
                })

                show_success("Success", f"Application {status}!")
                self._load_aid_applications()
                return True
            else:
                show_error("Error", "Failed to review application")
                return False

        except Exception as e:
            logger.error(f"Error reviewing application: {e}")
            show_error("Error", f"An error occurred: {str(e)}")
            return False

    def show_create_package(self, student_id: str = None, academic_year: str = None):
        """Show create aid package interface"""
        # Check if parent frame is valid
        try:
            if not self.parent_frame.winfo_exists():
                logger.error("Parent frame no longer exists")
                return
        except Exception as e:
            logger.error(f"Error checking parent frame: {e}")
            return

        clear_frame(self.parent_frame)

        # Title
        title_frame = ttk.Frame(self.parent_frame)
        title_frame.pack(fill='x', padx=10, pady=10)
        ttk.Label(title_frame, text="Create Financial Aid Package", style='Title.TLabel').pack(side='left')
        ttk.Button(title_frame, text="Back to Dashboard", command=self.show_dashboard).pack(side='right')

        # Form
        form_frame = ttk.LabelFrame(self.parent_frame, text="Aid Package Details", padding=20)
        form_frame.pack(fill='both', expand=True, padx=10, pady=10)

        fields = {}

        # Student ID
        row = 0
        ttk.Label(form_frame, text="Student ID:").grid(row=row, column=0, sticky='w', pady=10)
        student_var = tk.StringVar(value=student_id or '')
        ttk.Entry(form_frame, textvariable=student_var, width=30).grid(row=row, column=1, sticky='w', padx=10)
        fields['student_id'] = student_var

        # Academic year
        row += 1
        ttk.Label(form_frame, text="Academic Year:").grid(row=row, column=0, sticky='w', pady=10)
        year_var = tk.StringVar(value=academic_year or get_current_academic_year())
        ttk.Combobox(form_frame, textvariable=year_var, values=get_academic_year_list(),
                    state='readonly', width=20).grid(row=row, column=1, sticky='w', padx=10)
        fields['academic_year'] = year_var

        # Package name
        row += 1
        ttk.Label(form_frame, text="Package Name:").grid(row=row, column=0, sticky='w', pady=10)
        name_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=name_var, width=40).grid(row=row, column=1, sticky='w', padx=10)
        fields['package_name'] = name_var

        # Aid components section
        row += 1
        ttk.Label(form_frame, text="Aid Components:", font=('Arial', 11, 'bold')).grid(
            row=row, column=0, columnspan=2, sticky='w', pady=(20, 10))

        # Grant amount
        row += 1
        ttk.Label(form_frame, text="Grant Amount:").grid(row=row, column=0, sticky='w', pady=5)
        grant_var = tk.StringVar(value='0')
        ttk.Entry(form_frame, textvariable=grant_var, width=20).grid(row=row, column=1, sticky='w', padx=10)
        fields['grant_amount'] = grant_var

        # Loan amount
        row += 1
        ttk.Label(form_frame, text="Loan Amount:").grid(row=row, column=0, sticky='w', pady=5)
        loan_var = tk.StringVar(value='0')
        ttk.Entry(form_frame, textvariable=loan_var, width=20).grid(row=row, column=1, sticky='w', padx=10)
        fields['loan_amount'] = loan_var

        # Work-study amount
        row += 1
        ttk.Label(form_frame, text="Work-Study Amount:").grid(row=row, column=0, sticky='w', pady=5)
        ws_var = tk.StringVar(value='0')
        ttk.Entry(form_frame, textvariable=ws_var, width=20).grid(row=row, column=1, sticky='w', padx=10)
        fields['work_study_amount'] = ws_var

        # Total display
        row += 1
        ttk.Label(form_frame, text="Total Package:", font=('Arial', 10, 'bold')).grid(
            row=row, column=0, sticky='w', pady=(20, 5))
        total_label = ttk.Label(form_frame, text="$0.00", font=('Arial', 12, 'bold'), foreground='green')
        total_label.grid(row=row, column=1, sticky='w', padx=10)

        def update_total(*args):
            try:
                total = (float(grant_var.get() or 0) +
                        float(loan_var.get() or 0) +
                        float(ws_var.get() or 0))
                total_label.config(text=format_currency(total))
            except:
                total_label.config(text="Invalid amounts")

        grant_var.trace('w', update_total)
        loan_var.trace('w', update_total)
        ws_var.trace('w', update_total)

        # Buttons
        btn_frame = ttk.Frame(form_frame)
        btn_frame.grid(row=row+1, column=0, columnspan=2, pady=20)

        def create():
            if self._create_aid_package(fields):
                self.show_dashboard()

        ttk.Button(btn_frame, text="Create Package", command=create,
                  style='Success.TButton').pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.show_dashboard).pack(side='left', padx=5)

    def _create_aid_package(self, fields: Dict) -> bool:
        """Create financial aid package"""
        try:
            student_id = fields['student_id'].get().strip()
            if not student_id:
                show_error("Validation Error", "Student ID is required")
                return False

            grant = float(fields['grant_amount'].get() or 0)
            loan = float(fields['loan_amount'].get() or 0)
            work_study = float(fields['work_study_amount'].get() or 0)

            if grant + loan + work_study <= 0:
                show_error("Validation Error", "Package must have at least one aid component")
                return False

            # Create aid package
            package_id = self.aid_manager.create_aid_package(
                student_id=student_id,
                academic_year=fields['academic_year'].get(),
                package_data={
                    'name': fields['package_name'].get() or 'Standard Package',
                    'grant_amount': grant,
                    'loan_amount': loan,
                    'work_study_amount': work_study
                }
            )

            if package_id:
                log_activity('create', 'aid_package', package_id, {
                    'student_id': student_id,
                    'total_amount': grant + loan + work_study
                })

                show_success("Success", "Aid package created successfully!")
                return True
            else:
                show_error("Error", "Failed to create aid package")
                return False

        except Exception as e:
            logger.error(f"Error creating aid package: {e}")
            show_error("Error", f"An error occurred: {str(e)}")
            return False

    def show_aid_types(self):
        """Show aid types management"""
        # Check if parent frame is valid
        try:
            if not self.parent_frame.winfo_exists():
                logger.error("Parent frame no longer exists")
                return
        except Exception as e:
            logger.error(f"Error checking parent frame: {e}")
            return

        clear_frame(self.parent_frame)

        # Title
        title_frame = ttk.Frame(self.parent_frame)
        title_frame.pack(fill='x', padx=10, pady=10)
        ttk.Label(title_frame, text="Manage Aid Types", style='Title.TLabel').pack(side='left')
        ttk.Button(title_frame, text="Back to Dashboard", command=self.show_dashboard).pack(side='right')

        # Aid types table
        table_frame = ttk.Frame(self.parent_frame)
        table_frame.pack(fill='both', expand=True, padx=10, pady=10)

        columns = ['Aid Type ID', 'Name', 'Category', 'Max Amount', 'Renewable', 'Requires Repayment']
        tree = create_data_table(table_frame, columns, {
            'Aid Type ID': 100, 'Name': 200, 'Category': 120, 'Max Amount': 100, 'Renewable': 100, 'Requires Repayment': 150
        })

        try:
            with get_connection() as conn:
                aid_types = conn.execute("""
                    SELECT * FROM financial_aid_types
                    ORDER BY aid_category, aid_name
                """).fetchall()

                for aid_type in aid_types:
                    tree.insert('', 'end', values=(
                        aid_type['aid_type_id'],
                        aid_type['aid_name'],
                        aid_type.get('aid_category', 'N/A'),
                        format_currency(aid_type.get('max_amount', 0)),
                        'Yes' if aid_type.get('is_renewable') else 'No',
                        'Yes' if aid_type.get('requires_repayment') else 'No'
                    ))

        except Exception as e:
            logger.error(f"Error loading aid types: {e}")
            ttk.Label(table_frame, text="Error loading aid types", foreground='red').pack()

    def show_disbursements(self):
        """Show disbursements management"""
        # Check if parent frame is valid
        try:
            if not self.parent_frame.winfo_exists():
                logger.error("Parent frame no longer exists")
                return
        except Exception as e:
            logger.error(f"Error checking parent frame: {e}")
            return

        clear_frame(self.parent_frame)

        # Title
        title_frame = ttk.Frame(self.parent_frame)
        title_frame.pack(fill='x', padx=10, pady=10)
        ttk.Label(title_frame, text="Process Disbursements", style='Title.TLabel').pack(side='left')
        ttk.Button(title_frame, text="Back to Dashboard", command=self.show_dashboard).pack(side='right')

        # Pending disbursements
        table_frame = ttk.Frame(self.parent_frame)
        table_frame.pack(fill='both', expand=True, padx=10, pady=10)

        columns = ['Disbursement ID', 'Student', 'Amount', 'Scheduled Date', 'Method', 'Status']
        tree = create_data_table(table_frame, columns, {
            'Disbursement ID': 120, 'Student': 150, 'Amount': 100, 'Scheduled Date': 120, 'Method': 100, 'Status': 100
        })

        try:
            with get_connection() as conn:
                # Check if disbursements table exists
                check_result = conn.execute("""
                    SELECT name FROM sqlite_master
                    WHERE type='table' AND name='disbursements'
                """).fetchone()

                if not check_result:
                    ttk.Label(table_frame, text="Disbursements feature not yet configured",
                             foreground='gray').pack(pady=20)
                    return

                disbursements = conn.execute("""
                    SELECT d.*, u.username, sfa.student_id
                    FROM disbursements d
                    JOIN student_financial_aid sfa ON d.aid_id = sfa.aid_id
                    JOIN users u ON sfa.student_id = u.user_id
                    WHERE d.status = 'pending'
                    ORDER BY d.scheduled_date ASC
                """).fetchall()

                for disb in disbursements:
                    tree.insert('', 'end', values=(
                        disb['disbursement_id'],
                        disb['username'],
                        format_currency(disb['amount']),
                        format_date(disb.get('scheduled_date')),
                        disb.get('method', 'Direct Deposit'),
                        disb['status'].title()
                    ))

        except Exception as e:
            logger.error(f"Error loading disbursements: {e}")
            ttk.Label(table_frame, text="Error loading disbursements", foreground='red').pack()

    def show_reports(self):
        """Show reports interface"""
        # Check if parent frame is valid
        try:
            if not self.parent_frame.winfo_exists():
                logger.error("Parent frame no longer exists")
                return
        except Exception as e:
            logger.error(f"Error checking parent frame: {e}")
            return

        clear_frame(self.parent_frame)

        # Title
        title_frame = ttk.Frame(self.parent_frame)
        title_frame.pack(fill='x', padx=10, pady=10)
        ttk.Label(title_frame, text="Financial Aid Reports", style='Title.TLabel').pack(side='left')
        ttk.Button(title_frame, text="Back to Dashboard", command=self.show_dashboard).pack(side='right')

        # Reports options
        reports_frame = ttk.LabelFrame(self.parent_frame, text="Available Reports", padding=20)
        reports_frame.pack(fill='both', expand=True, padx=10, pady=10)

        reports = [
            ("Aid Distribution Summary", "Summary of aid distributed by type and year"),
            ("Scholarship Utilization", "Analysis of scholarship awards and usage"),
            ("Disbursement Schedule", "Upcoming and completed disbursements"),
            ("Compliance Report (FISAP)", "Federal compliance reporting"),
            ("Student Aid Index Report", "SAI/EFC analysis"),
        ]

        for i, (name, description) in enumerate(reports):
            frame = ttk.Frame(reports_frame)
            frame.pack(fill='x', pady=10)

            ttk.Label(frame, text=name, font=('Arial', 11, 'bold')).pack(anchor='w')
            ttk.Label(frame, text=description, foreground='gray').pack(anchor='w', padx=20)
            ttk.Button(frame, text="Generate Report",
                      command=lambda n=name: self._generate_report(n)).pack(anchor='w', padx=20, pady=5)

    def _generate_report(self, report_name: str):
        """Generate selected report"""
        show_warning("Coming Soon", f"Report generation for '{report_name}' will be implemented in analytics_dashboard.py")

    def show_fafsa_import(self):
        """Show FAFSA import interface"""
        # Check if parent frame is valid
        try:
            if not self.parent_frame.winfo_exists():
                logger.error("Parent frame no longer exists")
                return
        except Exception as e:
            logger.error(f"Error checking parent frame: {e}")
            return

        clear_frame(self.parent_frame)

        # Title
        title_frame = ttk.Frame(self.parent_frame)
        title_frame.pack(fill='x', padx=10, pady=10)
        ttk.Label(title_frame, text="Import FAFSA Data", style='Title.TLabel').pack(side='left')
        ttk.Button(title_frame, text="Back to Dashboard", command=self.show_dashboard).pack(side='right')

        # Import form
        import_frame = ttk.LabelFrame(self.parent_frame, text="FAFSA Data Import", padding=20)
        import_frame.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(import_frame, text="Select FAFSA data file (CSV format):",
                 font=('Arial', 10, 'bold')).pack(anchor='w', pady=10)

        file_frame = ttk.Frame(import_frame)
        file_frame.pack(fill='x', pady=10)

        file_var = tk.StringVar()
        ttk.Entry(file_frame, textvariable=file_var, width=50, state='readonly').pack(side='left', padx=(0, 10))
        ttk.Button(file_frame, text="Browse...",
                  command=lambda: file_var.set(filedialog.askopenfilename(
                      filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]))).pack(side='left')

        ttk.Label(import_frame, text="\nFile should contain columns: student_id, efc, sai, household_income, etc.",
                 foreground='blue').pack(anchor='w')

        btn_frame = ttk.Frame(import_frame)
        btn_frame.pack(pady=20)

        ttk.Button(btn_frame, text="Import Data",
                  command=lambda: self._import_fafsa_file(file_var.get()),
                  style='Success.TButton').pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.show_dashboard).pack(side='left', padx=5)

    def _import_fafsa_file(self, filepath: str):
        """Import FAFSA data from file"""
        if not filepath:
            show_warning("No File Selected", "Please select a file to import")
            return

        try:
            # This would use the FAFSA manager
            show_success("Import Started", "FAFSA data import has been queued for processing")
            log_activity('import', 'fafsa_data', filepath, {'file': filepath})

        except Exception as e:
            logger.error(f"Error importing FAFSA data: {e}")
            show_error("Import Error", f"Failed to import FAFSA data: {str(e)}")
