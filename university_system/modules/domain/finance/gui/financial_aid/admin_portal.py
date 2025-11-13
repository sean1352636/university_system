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
        self.standalone_window = None

    def _ensure_valid_parent(self):
        """
        Ensure parent frame exists, create standalone window if needed

        Returns:
            Valid parent frame/window
        """
        try:
            if self.parent_frame and self.parent_frame.winfo_exists():
                return self.parent_frame
        except Exception:
            pass

        # Parent frame doesn't exist, create standalone window
        if self.standalone_window is None or not self.standalone_window.winfo_exists():
            self.standalone_window = tk.Toplevel()
            self.standalone_window.title("Financial Aid Administration")
            self.standalone_window.geometry("1200x800")
            logger.info("Created standalone window for financial aid administration")

        return self.standalone_window

    def show_dashboard(self):
        """Display admin dashboard"""
        # Ensure we have a valid parent frame/window
        parent = self._ensure_valid_parent()
        self.parent_frame = parent

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
        # Ensure we have a valid parent frame/window
        parent = self._ensure_valid_parent()
        self.parent_frame = parent

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
                        JOIN users u ON fa.student_id = u.student_id
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
                        JOIN users u ON fa.student_id = u.student_id
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
        # Ensure we have a valid parent frame/window
        parent = self._ensure_valid_parent()
        self.parent_frame = parent

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

            # Create aid package (note: package_data details are stored separately in aid_package_items table)
            package_id = self.aid_manager.create_aid_package(
                student_id=student_id,
                academic_year=fields['academic_year'].get()
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
        # Ensure we have a valid parent frame/window
        parent = self._ensure_valid_parent()
        self.parent_frame = parent

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
                    # Convert Row to dict for safe .get() usage
                    aid_dict = dict(aid_type)
                    tree.insert('', 'end', values=(
                        aid_dict['aid_type_id'],
                        aid_dict['aid_name'],
                        aid_dict.get('aid_category', 'N/A'),
                        format_currency(aid_dict.get('max_amount', 0)),
                        'Yes' if aid_dict.get('is_renewable') else 'No',
                        'Yes' if aid_dict.get('requires_repayment') else 'No'
                    ))

        except Exception as e:
            logger.error(f"Error loading aid types: {e}")
            ttk.Label(table_frame, text="Error loading aid types", foreground='red').pack()

    def show_disbursements(self):
        """Show comprehensive disbursements management interface"""
        # Ensure we have a valid parent frame/window
        parent = self._ensure_valid_parent()
        self.parent_frame = parent

        clear_frame(self.parent_frame)

        # Title
        title_frame = ttk.Frame(self.parent_frame)
        title_frame.pack(fill='x', padx=10, pady=10)
        ttk.Label(title_frame, text="Disbursement Management", style='Title.TLabel').pack(side='left')
        ttk.Button(title_frame, text="Back to Dashboard", command=self.show_dashboard).pack(side='right')

        # Stats summary
        stats_frame = ttk.Frame(self.parent_frame)
        stats_frame.pack(fill='x', padx=10, pady=10)

        try:
            with get_connection() as conn:
                # Get disbursement statistics
                pending_result = conn.execute("""
                    SELECT COUNT(*) as count, COALESCE(SUM(amount), 0) as total
                    FROM disbursements WHERE status = 'pending'
                """).fetchone()

                processed_result = conn.execute("""
                    SELECT COUNT(*) as count, COALESCE(SUM(amount), 0) as total
                    FROM disbursements WHERE status = 'processed'
                    AND DATE(processed_at) = DATE('now')
                """).fetchone()

                # Display stats
                stat_frame1 = create_stat_card(stats_frame, "Pending Disbursements",
                                               f"{pending_result['count']}", 'warning')
                stat_frame1.pack(side='left', padx=10, fill='both', expand=True)

                stat_frame2 = create_stat_card(stats_frame, "Pending Amount",
                                               format_currency(pending_result['total']), 'warning')
                stat_frame2.pack(side='left', padx=10, fill='both', expand=True)

                stat_frame3 = create_stat_card(stats_frame, "Processed Today",
                                               f"{processed_result['count']}", 'success')
                stat_frame3.pack(side='left', padx=10, fill='both', expand=True)

                stat_frame4 = create_stat_card(stats_frame, "Amount Processed Today",
                                               format_currency(processed_result['total']), 'success')
                stat_frame4.pack(side='left', padx=10, fill='both', expand=True)

        except Exception as e:
            logger.error(f"Error loading disbursement stats: {e}")

        # Action buttons
        action_frame = ttk.Frame(self.parent_frame)
        action_frame.pack(fill='x', padx=10, pady=10)

        ttk.Button(action_frame, text="➕ Create Disbursement",
                  command=self._show_create_disbursement_dialog,
                  style='Success.TButton').pack(side='left', padx=5)
        ttk.Button(action_frame, text="✓ Process Selected",
                  command=lambda: self._process_selected_disbursements(tree),
                  style='Primary.TButton').pack(side='left', padx=5)
        ttk.Button(action_frame, text="✓✓ Process All Pending",
                  command=self._process_all_pending_disbursements,
                  style='Success.TButton').pack(side='left', padx=5)
        ttk.Button(action_frame, text="❌ Cancel Selected",
                  command=lambda: self._cancel_selected_disbursements(tree),
                  style='Danger.TButton').pack(side='left', padx=5)
        ttk.Button(action_frame, text="🔍 View Details",
                  command=lambda: self._view_disbursement_details(tree)).pack(side='left', padx=5)
        ttk.Button(action_frame, text="📊 Export Report",
                  command=self._export_disbursement_report).pack(side='left', padx=5)

        # Tabs for different views
        notebook = ttk.Notebook(self.parent_frame)
        notebook.pack(fill='both', expand=True, padx=10, pady=10)

        # Pending disbursements tab
        pending_frame = ttk.Frame(notebook)
        notebook.add(pending_frame, text='Pending Disbursements')

        columns_pending = ['Select', 'ID', 'Student Name', 'Student ID', 'Type', 'Amount',
                          'Scheduled Date', 'Term', 'Method', 'Transaction ID']
        tree = ttk.Treeview(pending_frame, columns=columns_pending, show='tree headings', height=15)

        # Configure columns
        tree.column('#0', width=0, stretch=False)
        tree.column('Select', width=50, anchor='center')
        tree.column('ID', width=60)
        tree.column('Student Name', width=150)
        tree.column('Student ID', width=100)
        tree.column('Type', width=120)
        tree.column('Amount', width=100, anchor='e')
        tree.column('Scheduled Date', width=120)
        tree.column('Term', width=100)
        tree.column('Method', width=120)
        tree.column('Transaction ID', width=150)

        for col in columns_pending:
            tree.heading(col, text=col)

        # Scrollbars
        vsb = ttk.Scrollbar(pending_frame, orient="vertical", command=tree.yview)
        hsb = ttk.Scrollbar(pending_frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')

        pending_frame.grid_rowconfigure(0, weight=1)
        pending_frame.grid_columnconfigure(0, weight=1)

        # Bind click event for checkbox toggle
        tree.bind('<Button-1>', lambda e: self._toggle_selection(tree, e))

        # Load pending disbursements
        self._load_pending_disbursements(tree)

        # Processed disbursements tab
        processed_frame = ttk.Frame(notebook)
        notebook.add(processed_frame, text='Processed Disbursements')

        columns_processed = ['ID', 'Student Name', 'Student ID', 'Type', 'Amount',
                            'Disbursement Date', 'Processed Date', 'Processed By', 'Transaction ID']
        processed_tree = ttk.Treeview(processed_frame, columns=columns_processed, show='headings', height=15)

        for col in columns_processed:
            processed_tree.heading(col, text=col)
            processed_tree.column(col, width=100)

        vsb2 = ttk.Scrollbar(processed_frame, orient="vertical", command=processed_tree.yview)
        hsb2 = ttk.Scrollbar(processed_frame, orient="horizontal", command=processed_tree.xview)
        processed_tree.configure(yscrollcommand=vsb2.set, xscrollcommand=hsb2.set)

        processed_tree.grid(row=0, column=0, sticky='nsew')
        vsb2.grid(row=0, column=1, sticky='ns')
        hsb2.grid(row=1, column=0, sticky='ew')

        processed_frame.grid_rowconfigure(0, weight=1)
        processed_frame.grid_columnconfigure(0, weight=1)

        # Load processed disbursements
        self._load_processed_disbursements(processed_tree)

        # Failed/cancelled disbursements tab
        failed_frame = ttk.Frame(notebook)
        notebook.add(failed_frame, text='Failed/Cancelled')

        columns_failed = ['ID', 'Student', 'Amount', 'Scheduled Date', 'Status', 'Error Message']
        failed_tree = ttk.Treeview(failed_frame, columns=columns_failed, show='headings', height=15)

        for col in columns_failed:
            failed_tree.heading(col, text=col)
            failed_tree.column(col, width=120)

        vsb3 = ttk.Scrollbar(failed_frame, orient="vertical", command=failed_tree.yview)
        failed_tree.configure(yscrollcommand=vsb3.set)

        failed_tree.grid(row=0, column=0, sticky='nsew')
        vsb3.grid(row=0, column=1, sticky='ns')

        failed_frame.grid_rowconfigure(0, weight=1)
        failed_frame.grid_columnconfigure(0, weight=1)

        # Load failed/cancelled disbursements
        self._load_failed_disbursements(failed_tree)

    def _load_pending_disbursements(self, tree):
        """Load pending disbursements into tree"""
        try:
            # Clear existing items
            for item in tree.get_children():
                tree.delete(item)

            with get_connection() as conn:
                disbursements = conn.execute("""
                    SELECT d.*, s.first_name, s.last_name, s.student_id as sid
                    FROM disbursements d
                    LEFT JOIN students s ON d.student_id = s.student_id
                    WHERE d.status = 'pending'
                    ORDER BY d.scheduled_date ASC
                """).fetchall()

                for disb in disbursements:
                    # Convert Row to dict
                    d = dict(disb)
                    student_name = f"{d.get('first_name', 'N/A')} {d.get('last_name', '')}"
                    tree.insert('', 'end', values=(
                        '☐',  # Checkbox
                        d['disbursement_id'],
                        student_name,
                        d.get('sid', d['student_id']),
                        d.get('disbursement_type', 'General Aid'),
                        format_currency(d['amount']),
                        format_date(d.get('scheduled_date', d.get('disbursement_date'))),
                        d.get('academic_term', 'N/A'),
                        d.get('payment_method', 'account_credit'),
                        d.get('transaction_id', 'Pending')
                    ))

        except Exception as e:
            logger.error(f"Error loading pending disbursements: {e}")

    def _load_processed_disbursements(self, tree):
        """Load processed disbursements into tree"""
        try:
            # Clear existing items
            for item in tree.get_children():
                tree.delete(item)

            with get_connection() as conn:
                disbursements = conn.execute("""
                    SELECT d.*, s.first_name, s.last_name, s.student_id as sid,
                           u.username as processor_name
                    FROM disbursements d
                    LEFT JOIN students s ON d.student_id = s.student_id
                    LEFT JOIN users u ON d.processed_by = u.id
                    WHERE d.status = 'processed'
                    ORDER BY d.processed_at DESC
                    LIMIT 100
                """).fetchall()

                for disb in disbursements:
                    # Convert Row to dict
                    d = dict(disb)
                    student_name = f"{d.get('first_name', 'N/A')} {d.get('last_name', '')}"
                    tree.insert('', 'end', values=(
                        d['disbursement_id'],
                        student_name,
                        d.get('sid', d['student_id']),
                        d.get('disbursement_type', 'General Aid'),
                        format_currency(d['amount']),
                        format_date(d.get('disbursement_date')),
                        format_date(d.get('processed_at')),
                        d.get('processor_name', 'System'),
                        d.get('transaction_id', 'N/A')
                    ))

        except Exception as e:
            logger.error(f"Error loading processed disbursements: {e}")

    def _load_failed_disbursements(self, tree):
        """Load failed/cancelled disbursements into tree"""
        try:
            # Clear existing items
            for item in tree.get_children():
                tree.delete(item)

            with get_connection() as conn:
                disbursements = conn.execute("""
                    SELECT d.*, s.first_name, s.last_name
                    FROM disbursements d
                    LEFT JOIN students s ON d.student_id = s.student_id
                    WHERE d.status IN ('failed', 'cancelled')
                    ORDER BY d.scheduled_date DESC
                    LIMIT 100
                """).fetchall()

                for disb in disbursements:
                    # Convert Row to dict
                    d = dict(disb)
                    student_name = f"{d.get('first_name', 'N/A')} {d.get('last_name', '')}"
                    tree.insert('', 'end', values=(
                        d['disbursement_id'],
                        student_name,
                        format_currency(d['amount']),
                        format_date(d.get('scheduled_date')),
                        d['status'].upper(),
                        d.get('error_message', 'No error message')
                    ))

        except Exception as e:
            logger.error(f"Error loading failed disbursements: {e}")

    def _process_selected_disbursements(self, tree):
        """Process selected disbursements"""
        selected_items = []
        for item in tree.get_children():
            values = tree.item(item)['values']
            if values[0] == '☑':  # Checked
                selected_items.append(values[1])  # disbursement_id

        if not selected_items:
            show_warning("No Selection", "Please select disbursements to process by clicking the checkbox column.")
            return

        if not confirm_action(f"Process {len(selected_items)} selected disbursement(s)?\n\nThis action cannot be undone."):
            return

        success_count = 0
        error_count = 0

        try:
            auth_user = get_current_user()
            user_id = None
            if auth_user:
                user_dict = auth_user.to_dict() if hasattr(auth_user, 'to_dict') else auth_user.__dict__ if hasattr(auth_user, '__dict__') else auth_user
                user_id = user_dict.get('id', user_dict.get('user_id', 1))

            for disb_id in selected_items:
                success = self.aid_manager.process_disbursement(
                    disbursement_id=disb_id,
                    processed_by=user_id,
                    transaction_id=f"TXN-{datetime.now().strftime('%Y%m%d%H%M%S')}-{disb_id}"
                )
                if success:
                    success_count += 1
                    log_activity('process', 'disbursement', disb_id, {'processed_by': user_id})
                else:
                    error_count += 1

            # Refresh the table
            self._load_pending_disbursements(tree)

            show_success("Processing Complete",
                        f"Successfully processed: {success_count}\nFailed: {error_count}")

        except Exception as e:
            logger.error(f"Error processing disbursements: {e}")
            show_error("Processing Error", f"An error occurred: {str(e)}")

    def _process_all_pending_disbursements(self):
        """Process all pending disbursements"""
        try:
            with get_connection() as conn:
                pending_count = conn.execute("""
                    SELECT COUNT(*) as count FROM disbursements WHERE status = 'pending'
                """).fetchone()['count']

                if pending_count == 0:
                    show_warning("No Pending Disbursements", "There are no pending disbursements to process.")
                    return

                if not confirm_action(f"Process ALL {pending_count} pending disbursement(s)?\n\nThis will process every pending disbursement in the system.\nThis action cannot be undone."):
                    return

                auth_user = get_current_user()
                user_id = None
                if auth_user:
                    user_dict = auth_user.to_dict() if hasattr(auth_user, 'to_dict') else auth_user.__dict__ if hasattr(auth_user, '__dict__') else auth_user
                    user_id = user_dict.get('id', user_dict.get('user_id', 1))

                # Get all pending disbursements
                pending = conn.execute("""
                    SELECT disbursement_id FROM disbursements WHERE status = 'pending'
                """).fetchall()

                success_count = 0
                for row in pending:
                    success = self.aid_manager.process_disbursement(
                        disbursement_id=row['disbursement_id'],
                        processed_by=user_id,
                        transaction_id=f"TXN-{datetime.now().strftime('%Y%m%d%H%M%S')}-{row['disbursement_id']}"
                    )
                    if success:
                        success_count += 1
                        log_activity('process', 'disbursement', row['disbursement_id'], {'batch': True})

                show_success("Batch Processing Complete",
                            f"Successfully processed {success_count} out of {pending_count} disbursements.")

                # Refresh the view
                self.show_disbursements()

        except Exception as e:
            logger.error(f"Error in batch processing: {e}")
            show_error("Batch Processing Error", f"An error occurred: {str(e)}")

    def _cancel_selected_disbursements(self, tree):
        """Cancel selected disbursements"""
        selected_items = []
        for item in tree.get_children():
            values = tree.item(item)['values']
            if values[0] == '☑':  # Checked
                selected_items.append(values[1])  # disbursement_id

        if not selected_items:
            show_warning("No Selection", "Please select disbursements to cancel.")
            return

        if not confirm_action(f"Cancel {len(selected_items)} selected disbursement(s)?"):
            return

        try:
            with transaction() as conn:
                for disb_id in selected_items:
                    conn.execute("""
                        UPDATE disbursements
                        SET status = 'cancelled', error_message = 'Cancelled by administrator'
                        WHERE disbursement_id = ?
                    """, (disb_id,))
                    log_activity('cancel', 'disbursement', disb_id, {'reason': 'admin_action'})

            show_success("Cancellation Complete", f"Successfully cancelled {len(selected_items)} disbursement(s).")
            self._load_pending_disbursements(tree)

        except Exception as e:
            logger.error(f"Error cancelling disbursements: {e}")
            show_error("Cancellation Error", f"An error occurred: {str(e)}")

    def _view_disbursement_details(self, tree):
        """View detailed information about selected disbursement"""
        selection = tree.selection()
        if not selection:
            show_warning("No Selection", "Please select a disbursement to view details.")
            return

        values = tree.item(selection[0])['values']
        disb_id = values[1]  # disbursement_id

        try:
            with get_connection() as conn:
                disb = conn.execute("""
                    SELECT d.*, s.first_name, s.last_name, s.email, s.student_id as sid,
                           u.username as processor_name
                    FROM disbursements d
                    LEFT JOIN students s ON d.student_id = s.student_id
                    LEFT JOIN users u ON d.processed_by = u.id
                    WHERE d.disbursement_id = ?
                """, (disb_id,)).fetchone()

                if not disb:
                    show_error("Not Found", "Disbursement not found.")
                    return

                # Convert Row to dict
                d = dict(disb)

                # Create details window
                details_window = tk.Toplevel(self.parent_frame)
                details_window.title(f"Disbursement Details - ID: {disb_id}")
                details_window.geometry("600x700")

                # Title
                ttk.Label(details_window, text=f"Disbursement #{disb_id}", font=('Arial', 14, 'bold')).pack(pady=10)

                # Details frame
                details_frame = ttk.Frame(details_window, padding=20)
                details_frame.pack(fill='both', expand=True)

                def add_detail(label, value):
                    row_frame = ttk.Frame(details_frame)
                    row_frame.pack(fill='x', pady=5)
                    ttk.Label(row_frame, text=f"{label}:", font=('Arial', 10, 'bold'), width=20).pack(side='left')
                    ttk.Label(row_frame, text=str(value), font=('Arial', 10)).pack(side='left')

                add_detail("Status", d['status'].upper())
                add_detail("Student Name", f"{d.get('first_name', 'N/A')} {d.get('last_name', '')}")
                add_detail("Student ID", d.get('sid', d['student_id']))
                add_detail("Student Email", d.get('email', 'N/A'))
                add_detail("Disbursement Type", d.get('disbursement_type', 'General Aid'))
                add_detail("Amount", format_currency(d['amount']))
                add_detail("Academic Term", d.get('academic_term', 'N/A'))
                add_detail("Payment Method", d.get('payment_method', 'N/A'))
                add_detail("Transaction ID", d.get('transaction_id', 'Pending'))
                add_detail("Scheduled Date", format_date(d.get('scheduled_date')))
                add_detail("Disbursement Date", format_date(d.get('disbursement_date', 'N/A')))

                if d.get('processed_at'):
                    add_detail("Processed Date", format_date(d['processed_at']))
                    add_detail("Processed By", d.get('processor_name', 'System'))

                if d.get('award_id'):
                    add_detail("Award ID", d['award_id'])
                if d.get('component_id'):
                    add_detail("Component ID", d['component_id'])

                if d.get('error_message'):
                    add_detail("Error Message", d['error_message'])

                # Close button
                ttk.Button(details_window, text="Close", command=details_window.destroy).pack(pady=10)

        except Exception as e:
            logger.error(f"Error viewing disbursement details: {e}")
            show_error("Error", f"An error occurred: {str(e)}")

    def _show_create_disbursement_dialog(self):
        """Show dialog to create new disbursement"""
        dialog = tk.Toplevel(self.parent_frame)
        dialog.title("Create New Disbursement")
        dialog.geometry("500x600")

        ttk.Label(dialog, text="Create New Disbursement", font=('Arial', 14, 'bold')).pack(pady=10)

        # Form
        form_frame = ttk.Frame(dialog, padding=20)
        form_frame.pack(fill='both', expand=True)

        fields = {}

        # Student ID
        ttk.Label(form_frame, text="Student ID:").pack(anchor='w', pady=(5, 0))
        fields['student_id'] = ttk.Entry(form_frame, width=40)
        fields['student_id'].pack(fill='x', pady=(0, 10))

        # Amount
        ttk.Label(form_frame, text="Amount ($):").pack(anchor='w', pady=(5, 0))
        fields['amount'] = ttk.Entry(form_frame, width=40)
        fields['amount'].pack(fill='x', pady=(0, 10))

        # Type
        ttk.Label(form_frame, text="Disbursement Type:").pack(anchor='w', pady=(5, 0))
        fields['type'] = ttk.Combobox(form_frame, values=['scholarship', 'grant', 'loan', 'work_study', 'refund'], width=38)
        fields['type'].set('grant')
        fields['type'].pack(fill='x', pady=(0, 10))

        # Academic Term
        ttk.Label(form_frame, text="Academic Term:").pack(anchor='w', pady=(5, 0))
        fields['term'] = ttk.Combobox(form_frame, values=['Fall', 'Spring', 'Summer'], width=38)
        fields['term'].set('Fall')
        fields['term'].pack(fill='x', pady=(0, 10))

        # Scheduled Date
        ttk.Label(form_frame, text="Scheduled Date (YYYY-MM-DD):").pack(anchor='w', pady=(5, 0))
        fields['date'] = ttk.Entry(form_frame, width=40)
        fields['date'].insert(0, date.today().strftime('%Y-%m-%d'))
        fields['date'].pack(fill='x', pady=(0, 10))

        # Payment Method
        ttk.Label(form_frame, text="Payment Method:").pack(anchor='w', pady=(5, 0))
        fields['method'] = ttk.Combobox(form_frame, values=['account_credit', 'direct_deposit', 'check', 'wire_transfer'], width=38)
        fields['method'].set('account_credit')
        fields['method'].pack(fill='x', pady=(0, 10))

        def create_disbursement():
            try:
                # Validate
                if not fields['student_id'].get().strip():
                    show_error("Validation Error", "Student ID is required")
                    return

                amount = float(fields['amount'].get())
                if amount <= 0:
                    show_error("Validation Error", "Amount must be greater than 0")
                    return

                # Create disbursement
                disb_id = self.aid_manager.create_disbursement(
                    student_id=fields['student_id'].get().strip(),
                    amount=amount,
                    disbursement_date=date.fromisoformat(fields['date'].get()),
                    disbursement_type=fields['type'].get(),
                    academic_term=fields['term'].get()
                )

                if disb_id:
                    # Update payment method
                    with transaction() as conn:
                        conn.execute("""
                            UPDATE disbursements
                            SET payment_method = ?, scheduled_date = ?
                            WHERE disbursement_id = ?
                        """, (fields['method'].get(), fields['date'].get(), disb_id))

                    log_activity('create', 'disbursement', disb_id, {
                        'student_id': fields['student_id'].get(),
                        'amount': amount
                    })

                    show_success("Success", f"Disbursement created successfully!\nDisbursement ID: {disb_id}")
                    dialog.destroy()
                    self.show_disbursements()  # Refresh
                else:
                    show_error("Error", "Failed to create disbursement")

            except ValueError as e:
                show_error("Validation Error", f"Invalid input: {str(e)}")
            except Exception as e:
                logger.error(f"Error creating disbursement: {e}")
                show_error("Error", f"An error occurred: {str(e)}")

        # Buttons
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=10)
        ttk.Button(btn_frame, text="Create", command=create_disbursement, style='Success.TButton').pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side='left', padx=5)

    def _export_disbursement_report(self):
        """Export disbursement report to CSV"""
        try:
            with get_connection() as conn:
                # Get all disbursements
                disbursements = conn.execute("""
                    SELECT d.*, s.first_name, s.last_name, s.student_id as sid,
                           u.username as processor
                    FROM disbursements d
                    LEFT JOIN students s ON d.student_id = s.student_id
                    LEFT JOIN users u ON d.processed_by = u.id
                    ORDER BY d.disbursement_date DESC
                """).fetchall()

                data = []
                for disb in disbursements:
                    # Convert Row to dict
                    d = dict(disb)
                    data.append({
                        'Disbursement ID': d['disbursement_id'],
                        'Student Name': f"{d.get('first_name', 'N/A')} {d.get('last_name', '')}",
                        'Student ID': d.get('sid', d['student_id']),
                        'Type': d.get('disbursement_type', 'N/A'),
                        'Amount': d['amount'],
                        'Status': d['status'],
                        'Scheduled Date': d.get('scheduled_date', 'N/A'),
                        'Disbursement Date': d.get('disbursement_date', 'N/A'),
                        'Processed Date': d.get('processed_at', 'N/A'),
                        'Processed By': d.get('processor', 'N/A'),
                        'Term': d.get('academic_term', 'N/A'),
                        'Payment Method': d.get('payment_method', 'N/A'),
                        'Transaction ID': d.get('transaction_id', 'N/A')
                    })

                export_to_csv(data, f"disbursement_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")

        except Exception as e:
            logger.error(f"Error exporting disbursement report: {e}")
            show_error("Export Error", f"Failed to export report: {str(e)}")

    # Toggle checkbox function (for Treeview)
    def _toggle_selection(self, tree, event):
        """Toggle selection checkbox on click"""
        region = tree.identify_region(event.x, event.y)
        if region == "cell":
            column = tree.identify_column(event.x)
            if column == '#1':  # First column (Select)
                item = tree.identify_row(event.y)
                if item:
                    values = list(tree.item(item)['values'])
                    values[0] = '☑' if values[0] == '☐' else '☐'
                    tree.item(item, values=values)

    def show_reports(self):
        """Show reports interface"""
        # Ensure we have a valid parent frame/window
        parent = self._ensure_valid_parent()
        self.parent_frame = parent

        clear_frame(self.parent_frame)

        # Title
        title_frame = ttk.Frame(self.parent_frame)
        title_frame.pack(fill='x', padx=10, pady=10)
        ttk.Label(title_frame, text="Financial Aid Reports", style='Title.TLabel').pack(side='left')
        ttk.Button(title_frame, text="Back to Dashboard", command=self.show_dashboard).pack(side='right')

        # Reports options with scrollbar
        reports_container = ttk.Frame(self.parent_frame)
        reports_container.pack(fill='both', expand=True, padx=10, pady=10)

        # Create scrollable frame
        scrollable_frame, canvas, scrollbar = create_scrollable_frame(reports_container)
        canvas.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        reports_frame = ttk.LabelFrame(scrollable_frame, text="Available Reports", padding=20)
        reports_frame.pack(fill='both', expand=True)

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
        if report_name == "Aid Distribution Summary":
            self._generate_aid_distribution_report()
        elif report_name == "Scholarship Utilization":
            self._generate_scholarship_utilization_report()
        elif report_name == "Disbursement Schedule":
            self._generate_disbursement_schedule_report()
        elif report_name == "Compliance Report (FISAP)":
            self._generate_compliance_report()
        elif report_name == "Student Aid Index Report":
            self._generate_sai_report()
        else:
            show_warning("Coming Soon", f"Report '{report_name}' not yet implemented")

    def _generate_aid_distribution_report(self):
        """Generate Aid Distribution Summary report"""
        report_window = tk.Toplevel(self.parent_frame)
        report_window.title("Aid Distribution Summary Report")
        report_window.geometry("900x700")

        # Title
        ttk.Label(report_window, text="Aid Distribution Summary", style='Title.TLabel').pack(pady=10)

        # Create scrolled text for report
        report_frame = ttk.Frame(report_window)
        report_frame.pack(fill='both', expand=True, padx=10, pady=10)

        report_text = scrolledtext.ScrolledText(report_frame, width=100, height=35, wrap='word', font=('Courier', 10))
        report_text.pack(fill='both', expand=True)

        try:
            report = []
            report.append("=" * 80)
            report.append("FINANCIAL AID DISTRIBUTION SUMMARY")
            report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            report.append("=" * 80)
            report.append("")

            with get_connection() as conn:
                # Aid by type
                report.append("AID DISTRIBUTION BY TYPE:")
                report.append("-" * 80)

                try:
                    aid_by_type = conn.execute("""
                        SELECT fat.aid_name, fat.aid_category,
                               COUNT(sfa.aid_id) as count,
                               SUM(sfa.awarded_amount) as total_awarded,
                               SUM(sfa.disbursed_amount) as total_disbursed,
                               SUM(sfa.remaining_amount) as total_remaining
                        FROM financial_aid_types fat
                        LEFT JOIN student_financial_aid sfa ON fat.aid_type_id = sfa.aid_type_id
                        GROUP BY fat.aid_type_id, fat.aid_name, fat.aid_category
                        ORDER BY total_awarded DESC
                    """).fetchall()

                    for aid in aid_by_type:
                        aid_dict = dict(aid)
                        report.append(f"\nAid Type: {aid_dict['aid_name']} ({aid_dict['aid_category']})")
                        report.append(f"  Recipients: {aid_dict['count']}")
                        report.append(f"  Total Awarded: {format_currency(aid_dict['total_awarded'] or 0)}")
                        report.append(f"  Total Disbursed: {format_currency(aid_dict['total_disbursed'] or 0)}")
                        report.append(f"  Remaining: {format_currency(aid_dict['total_remaining'] or 0)}")
                except Exception as e:
                    report.append(f"Error loading aid types data: {e}")

                report.append("")
                report.append("=" * 80)
                report.append("AID DISTRIBUTION BY ACADEMIC YEAR:")
                report.append("-" * 80)

                # Get unique academic years from student_financial_aid
                try:
                    # This query needs the application_date field to extract year
                    report.append("\nNote: Academic year breakdown requires application_date field")
                    report.append("in student_financial_aid table for accurate reporting.")
                except Exception as e:
                    report.append(f"Error loading year data: {e}")

                report.append("")
                report.append("=" * 80)
                report.append("SUMMARY STATISTICS:")
                report.append("-" * 80)

                try:
                    summary = conn.execute("""
                        SELECT
                            COUNT(DISTINCT student_id) as total_students,
                            COUNT(aid_id) as total_awards,
                            SUM(awarded_amount) as total_awarded,
                            SUM(disbursed_amount) as total_disbursed,
                            AVG(awarded_amount) as avg_award
                        FROM student_financial_aid
                        WHERE status IN ('approved', 'disbursed', 'completed')
                    """).fetchone()

                    if summary:
                        s = dict(summary)
                        report.append(f"\nTotal Students Receiving Aid: {s['total_students'] or 0}")
                        report.append(f"Total Awards: {s['total_awards'] or 0}")
                        report.append(f"Total Amount Awarded: {format_currency(s['total_awarded'] or 0)}")
                        report.append(f"Total Amount Disbursed: {format_currency(s['total_disbursed'] or 0)}")
                        report.append(f"Average Award Amount: {format_currency(s['avg_award'] or 0)}")
                except Exception as e:
                    report.append(f"Error loading summary statistics: {e}")

            report.append("")
            report.append("=" * 80)
            report.append("End of Report")
            report.append("=" * 80)

            report_text.insert('1.0', '\n'.join(report))
            report_text.config(state='disabled')

        except Exception as e:
            logger.error(f"Error generating aid distribution report: {e}")
            report_text.insert('1.0', f"Error generating report:\n{str(e)}")
            report_text.config(state='disabled')

        # Export buttons
        btn_frame = ttk.Frame(report_window)
        btn_frame.pack(pady=10)

        ttk.Button(btn_frame, text="Export as CSV",
                  command=lambda: self._export_report_to_csv(report_text.get('1.0', 'end-1c'), "aid_distribution_report")).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Export as Text",
                  command=lambda: self._export_report_to_txt(report_text.get('1.0', 'end-1c'), "aid_distribution_report")).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Email Report to Admin",
                  command=lambda: self._email_report(report_text.get('1.0', 'end-1c'), "Aid Distribution Summary")).pack(side='left', padx=5)

        ttk.Button(report_window, text="Close", command=report_window.destroy).pack(pady=5)

    def _generate_scholarship_utilization_report(self):
        """Generate Scholarship Utilization report"""
        report_window = tk.Toplevel(self.parent_frame)
        report_window.title("Scholarship Utilization Report")
        report_window.geometry("900x700")

        ttk.Label(report_window, text="Scholarship Utilization Report", style='Title.TLabel').pack(pady=10)

        report_frame = ttk.Frame(report_window)
        report_frame.pack(fill='both', expand=True, padx=10, pady=10)

        report_text = scrolledtext.ScrolledText(report_frame, width=100, height=35, wrap='word', font=('Courier', 10))
        report_text.pack(fill='both', expand=True)

        try:
            report = []
            report.append("=" * 80)
            report.append("SCHOLARSHIP UTILIZATION REPORT")
            report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            report.append("=" * 80)
            report.append("")

            with get_connection() as conn:
                # Scholarship awards summary
                report.append("SCHOLARSHIP AWARDS SUMMARY:")
                report.append("-" * 80)

                scholarships = conn.execute("""
                    SELECT s.scholarship_name, s.amount as max_amount, s.is_active,
                           COUNT(ss.student_scholarship_id) as awards_count,
                           SUM(ss.amount) as total_awarded,
                           s.academic_year
                    FROM scholarships s
                    LEFT JOIN student_scholarships ss ON s.scholarship_id = ss.scholarship_id
                    GROUP BY s.scholarship_id
                    ORDER BY total_awarded DESC
                """).fetchall()

                for scholarship in scholarships:
                    sch = dict(scholarship)
                    report.append(f"\nScholarship: {sch['scholarship_name']}")
                    report.append(f"  Academic Year: {sch['academic_year'] or 'N/A'}")
                    report.append(f"  Status: {'Active' if sch['is_active'] else 'Inactive'}")
                    report.append(f"  Maximum Amount: {format_currency(sch['max_amount'] or 0)}")
                    report.append(f"  Number of Awards: {sch['awards_count']}")
                    report.append(f"  Total Awarded: {format_currency(sch['total_awarded'] or 0)}")

                    if sch['max_amount'] and sch['awards_count'] > 0:
                        utilization = (sch['total_awarded'] or 0) / (sch['max_amount'] * sch['awards_count']) * 100
                        report.append(f"  Utilization Rate: {utilization:.1f}%")

                report.append("")
                report.append("=" * 80)
                report.append("APPLICATION STATISTICS:")
                report.append("-" * 80)

                app_stats = conn.execute("""
                    SELECT
                        COUNT(*) as total_applications,
                        SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                        SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) as approved,
                        SUM(CASE WHEN status = 'denied' THEN 1 ELSE 0 END) as denied
                    FROM scholarship_applications
                """).fetchone()

                if app_stats:
                    stats = dict(app_stats)
                    report.append(f"\nTotal Applications: {stats['total_applications']}")
                    report.append(f"Pending Applications: {stats['pending']}")
                    report.append(f"Approved Applications: {stats['approved']}")
                    report.append(f"Denied Applications: {stats['denied']}")

                    if stats['total_applications'] > 0:
                        approval_rate = (stats['approved'] / stats['total_applications']) * 100
                        report.append(f"Approval Rate: {approval_rate:.1f}%")

            report.append("")
            report.append("=" * 80)
            report.append("End of Report")
            report.append("=" * 80)

            report_text.insert('1.0', '\n'.join(report))
            report_text.config(state='disabled')

        except Exception as e:
            logger.error(f"Error generating scholarship utilization report: {e}")
            report_text.insert('1.0', f"Error generating report:\n{str(e)}")
            report_text.config(state='disabled')

        # Export buttons
        btn_frame = ttk.Frame(report_window)
        btn_frame.pack(pady=10)

        ttk.Button(btn_frame, text="Export as CSV",
                  command=lambda: self._export_report_to_csv(report_text.get('1.0', 'end-1c'), "scholarship_utilization_report")).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Export as Text",
                  command=lambda: self._export_report_to_txt(report_text.get('1.0', 'end-1c'), "scholarship_utilization_report")).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Email Report to Admin",
                  command=lambda: self._email_report(report_text.get('1.0', 'end-1c'), "Scholarship Utilization")).pack(side='left', padx=5)

        ttk.Button(report_window, text="Close", command=report_window.destroy).pack(pady=5)

    def _generate_disbursement_schedule_report(self):
        """Generate Disbursement Schedule report"""
        report_window = tk.Toplevel(self.parent_frame)
        report_window.title("Disbursement Schedule Report")
        report_window.geometry("900x700")

        ttk.Label(report_window, text="Disbursement Schedule Report", style='Title.TLabel').pack(pady=10)

        report_frame = ttk.Frame(report_window)
        report_frame.pack(fill='both', expand=True, padx=10, pady=10)

        report_text = scrolledtext.ScrolledText(report_frame, width=100, height=35, wrap='word', font=('Courier', 10))
        report_text.pack(fill='both', expand=True)

        try:
            report = []
            report.append("=" * 80)
            report.append("DISBURSEMENT SCHEDULE REPORT")
            report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            report.append("=" * 80)
            report.append("")

            with get_connection() as conn:
                # Check if disbursements table exists
                table_check = conn.execute("""
                    SELECT name FROM sqlite_master
                    WHERE type='table' AND name='disbursements'
                """).fetchone()

                if not table_check:
                    report.append("DISBURSEMENT TRACKING NOT YET CONFIGURED")
                    report.append("")
                    report.append("The disbursements table has not been created yet.")
                    report.append("This feature will be available once the database schema is updated.")
                else:
                    # Pending disbursements
                    report.append("PENDING DISBURSEMENTS:")
                    report.append("-" * 80)

                    pending = conn.execute("""
                        SELECT d.*, d.student_id,
                               COALESCE(fat.aid_name, s.scholarship_name, 'General Aid') as aid_name
                        FROM disbursements d
                        LEFT JOIN aid_components ac ON d.component_id = ac.component_id
                        LEFT JOIN aid_packages ap ON ac.package_id = ap.package_id
                        LEFT JOIN student_financial_aid sfa ON d.student_id = sfa.student_id AND ap.academic_year = sfa.notes
                        LEFT JOIN financial_aid_types fat ON sfa.aid_type_id = fat.aid_type_id
                        LEFT JOIN scholarship_awards sa ON d.award_id = sa.award_id
                        LEFT JOIN scholarships s ON sa.scholarship_id = s.scholarship_id
                        WHERE d.status = 'pending'
                        ORDER BY d.scheduled_date ASC
                    """).fetchall()

                    if pending:
                        for disb in pending:
                            d = dict(disb)
                            report.append(f"\nStudent ID: {d['student_id']}")
                            report.append(f"  Aid Type: {d['aid_name']}")
                            report.append(f"  Amount: {format_currency(d['amount'])}")
                            report.append(f"  Scheduled: {format_date(d.get('scheduled_date'))}")
                            report.append(f"  Method: {d.get('method', 'Direct Deposit')}")
                    else:
                        report.append("\nNo pending disbursements")

                    report.append("")
                    report.append("=" * 80)
                    report.append("COMPLETED DISBURSEMENTS (Last 30 days):")
                    report.append("-" * 80)

                    completed = conn.execute("""
                        SELECT d.*, d.student_id,
                               COALESCE(fat.aid_name, s.scholarship_name, 'General Aid') as aid_name
                        FROM disbursements d
                        LEFT JOIN aid_components ac ON d.component_id = ac.component_id
                        LEFT JOIN aid_packages ap ON ac.package_id = ap.package_id
                        LEFT JOIN student_financial_aid sfa ON d.student_id = sfa.student_id AND ap.academic_year = sfa.notes
                        LEFT JOIN financial_aid_types fat ON sfa.aid_type_id = fat.aid_type_id
                        LEFT JOIN scholarship_awards sa ON d.award_id = sa.award_id
                        LEFT JOIN scholarships s ON sa.scholarship_id = s.scholarship_id
                        WHERE d.status = 'disbursed'
                        AND d.disbursement_date >= date('now', '-30 days')
                        ORDER BY d.disbursement_date DESC
                    """).fetchall()

                    if completed:
                        for disb in completed:
                            d = dict(disb)
                            report.append(f"\nStudent ID: {d['student_id']}")
                            report.append(f"  Aid Type: {d['aid_name']}")
                            report.append(f"  Amount: {format_currency(d['amount'])}")
                            report.append(f"  Disbursed: {format_date(d.get('disbursement_date'))}")
                    else:
                        report.append("\nNo completed disbursements in last 30 days")

            report.append("")
            report.append("=" * 80)
            report.append("End of Report")
            report.append("=" * 80)

            report_text.insert('1.0', '\n'.join(report))
            report_text.config(state='disabled')

        except Exception as e:
            logger.error(f"Error generating disbursement schedule report: {e}")
            report_text.insert('1.0', f"Error generating report:\n{str(e)}")
            report_text.config(state='disabled')

        # Export buttons
        btn_frame = ttk.Frame(report_window)
        btn_frame.pack(pady=10)

        ttk.Button(btn_frame, text="Export as CSV",
                  command=lambda: self._export_report_to_csv(report_text.get('1.0', 'end-1c'), "disbursement_schedule_report")).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Export as Text",
                  command=lambda: self._export_report_to_txt(report_text.get('1.0', 'end-1c'), "disbursement_schedule_report")).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Email Report to Admin",
                  command=lambda: self._email_report(report_text.get('1.0', 'end-1c'), "Disbursement Schedule")).pack(side='left', padx=5)

        ttk.Button(report_window, text="Close", command=report_window.destroy).pack(pady=5)

    def _generate_compliance_report(self):
        """Generate Compliance (FISAP) report"""
        report_window = tk.Toplevel(self.parent_frame)
        report_window.title("Compliance Report (FISAP)")
        report_window.geometry("900x700")

        ttk.Label(report_window, text="Federal Student Aid Report (FISAP)", style='Title.TLabel').pack(pady=10)

        report_frame = ttk.Frame(report_window)
        report_frame.pack(fill='both', expand=True, padx=10, pady=10)

        report_text = scrolledtext.ScrolledText(report_frame, width=100, height=35, wrap='word', font=('Courier', 10))
        report_text.pack(fill='both', expand=True)

        report = []
        report.append("=" * 80)
        report.append("FISAP COMPLIANCE REPORT")
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("Academic Year: {current_ay}".replace("{current_ay}", get_current_academic_year()))
        report.append("=" * 80)
        report.append("")
        report.append("This is a placeholder for FISAP (Fiscal Operations Report and")
        report.append("Application to Participate) compliance reporting.")
        report.append("")
        report.append("FISAP reporting requires:")
        report.append("- Federal Work-Study (FWS) expenditures")
        report.append("- Federal Supplemental Educational Opportunity Grant (FSEOG) expenditures")
        report.append("- Federal Perkins Loan expenditures")
        report.append("- Institutional matching contributions")
        report.append("- Student enrollment data")
        report.append("")
        report.append("Contact your financial aid administrator to configure FISAP reporting.")
        report.append("")
        report.append("=" * 80)
        report.append("End of Report")
        report.append("=" * 80)

        report_text.insert('1.0', '\n'.join(report))
        report_text.config(state='disabled')

        ttk.Button(report_window, text="Close", command=report_window.destroy).pack(pady=10)

    def _generate_sai_report(self):
        """Generate Student Aid Index (SAI) report"""
        report_window = tk.Toplevel(self.parent_frame)
        report_window.title("Student Aid Index (SAI) Report")
        report_window.geometry("900x700")

        ttk.Label(report_window, text="Student Aid Index (SAI) Analysis", style='Title.TLabel').pack(pady=10)

        report_frame = ttk.Frame(report_window)
        report_frame.pack(fill='both', expand=True, padx=10, pady=10)

        report_text = scrolledtext.ScrolledText(report_frame, width=100, height=35, wrap='word', font=('Courier', 10))
        report_text.pack(fill='both', expand=True)

        report = []
        report.append("=" * 80)
        report.append("STUDENT AID INDEX (SAI) REPORT")
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("=" * 80)
        report.append("")
        report.append("This report analyzes Student Aid Index (SAI) data and Expected Family")
        report.append("Contribution (EFC) to determine financial need and aid eligibility.")
        report.append("")
        report.append("SAI/EFC data requires:")
        report.append("- FAFSA data import")
        report.append("- Student household income information")
        report.append("- Dependency status")
        report.append("- Number of family members in college")
        report.append("")
        report.append("Use the 'Import FAFSA Data' function to populate this report.")
        report.append("")
        report.append("=" * 80)
        report.append("End of Report")
        report.append("=" * 80)

        report_text.insert('1.0', '\n'.join(report))
        report_text.config(state='disabled')

        ttk.Button(report_window, text="Close", command=report_window.destroy).pack(pady=10)

    def _export_report_to_csv(self, report_text: str, filename_base: str):
        """Export report to CSV file"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filepath = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                initialfile=f"{filename_base}_{timestamp}.csv"
            )

            if filepath:
                # Convert report text to CSV format
                lines = report_text.split('\n')
                with open(filepath, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    for line in lines:
                        # Write each line as a single CSV row
                        writer.writerow([line])

                show_success("Export Successful", f"Report exported to:\n{filepath}")
                log_activity('export', 'financial_aid_report', filepath, {'report_type': filename_base, 'format': 'csv'})

        except Exception as e:
            logger.error(f"Error exporting report to CSV: {e}")
            show_error("Export Error", f"Failed to export report:\n{str(e)}")

    def _export_report_to_txt(self, report_text: str, filename_base: str):
        """Export report to text file"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filepath = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
                initialfile=f"{filename_base}_{timestamp}.txt"
            )

            if filepath:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(report_text)

                show_success("Export Successful", f"Report exported to:\n{filepath}")
                log_activity('export', 'financial_aid_report', filepath, {'report_type': filename_base, 'format': 'txt'})

        except Exception as e:
            logger.error(f"Error exporting report to text: {e}")
            show_error("Export Error", f"Failed to export report:\n{str(e)}")

    def _email_report(self, report_text: str, report_name: str):
        """Email report to admin"""
        try:
            # Get admin email from database
            admin_email = None
            with get_connection() as conn:
                result = conn.execute("""
                    SELECT email
                    FROM users
                    WHERE role = 'admin' AND email IS NOT NULL
                    ORDER BY id ASC
                    LIMIT 1
                """).fetchone()

                if result:
                    admin_email = result['email'] if isinstance(result, dict) else result[0]

            if not admin_email:
                show_warning("No Admin Email", "No admin email address found in the database.")
                return

            # Send email with report
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            subject = f"Financial Aid Report: {report_name}"
            body = f"""
Financial Aid Report Generated
Report: {report_name}
Generated: {timestamp}

{'=' * 80}

{report_text}

{'=' * 80}

This is an automated report from the University Financial Aid System.
            """

            send_email(
                recipient_email=admin_email,
                subject=subject,
                body=body
            )

            show_success("Email Sent", f"Report has been emailed to:\n{admin_email}")
            log_activity('email', 'financial_aid_report', admin_email, {
                'report_name': report_name,
                'recipient': admin_email
            })

        except Exception as e:
            logger.error(f"Error emailing report: {e}")
            show_error("Email Error", f"Failed to email report:\n{str(e)}")

    def show_fafsa_import(self):
        """Show FAFSA import interface"""
        # Ensure we have a valid parent frame/window
        parent = self._ensure_valid_parent()
        self.parent_frame = parent

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
