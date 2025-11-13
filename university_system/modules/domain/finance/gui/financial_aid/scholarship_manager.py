"""
Scholarship Manager

This module provides admin interfaces for managing scholarships,
reviewing applications, and awarding scholarships to students.
"""

from .common_imports import *


class ScholarshipManagerGUI:
    """Admin interface for scholarship management"""

    def __init__(self, parent_frame, auth_instance=None):
        """
        Initialize scholarship manager

        Args:
            parent_frame: Parent tkinter frame
            auth_instance: Authentication instance
        """
        self.parent_frame = parent_frame
        self.auth = auth_instance or get_auth()
        self.scholarship_manager = ScholarshipManager()

    def show_main_interface(self):
        """Display main scholarship management interface"""
        # Check if parent frame is valid
        try:
            if not self.parent_frame.winfo_exists():
                logger.debug("Parent frame no longer exists (likely window closed)")
                return
        except Exception as e:
            logger.debug(f"Parent frame check failed: {e}")
            return

        clear_frame(self.parent_frame)

        # Title
        title_frame = ttk.Frame(self.parent_frame)
        title_frame.pack(fill='x', padx=10, pady=10)
        ttk.Label(title_frame, text="Scholarship Management", style='Title.TLabel').pack(anchor='w')

        # Quick stats
        stats_frame = ttk.Frame(self.parent_frame)
        stats_frame.pack(fill='x', padx=10, pady=10)

        try:
            stats = self._get_scholarship_stats()

            cards = [
                ("Active Scholarships", str(stats['active_count']), 'success'),
                ("Pending Applications", str(stats['pending_apps']), 'warning'),
                ("Total Awarded This Year", format_currency(stats['total_awarded']), 'info'),
                ("Available Funds", format_currency(stats['available_funds']), 'primary')
            ]

            for i, (title, value, color) in enumerate(cards):
                card = create_stat_card(stats_frame, title, value, color)
                card.grid(row=0, column=i, padx=10, pady=5, sticky='ew')
                stats_frame.grid_columnconfigure(i, weight=1)

        except Exception as e:
            logger.error(f"Error loading stats: {e}")

        # Action buttons
        actions_frame = ttk.Frame(self.parent_frame)
        actions_frame.pack(fill='x', padx=10, pady=10)

        actions = [
            ("View All Scholarships", self.show_scholarships),
            ("Create New Scholarship", self.create_scholarship),
            ("Review Applications", self.review_applications),
            ("Award Scholarships", self.show_awards)
        ]

        for i, (text, command) in enumerate(actions):
            ttk.Button(actions_frame, text=text, command=command, width=20).grid(
                row=0, column=i, padx=5, pady=5, sticky='ew')
            actions_frame.grid_columnconfigure(i, weight=1)

        # Recent activity
        self._show_recent_activity()

    def _get_scholarship_stats(self) -> Dict[str, Any]:
        """Get scholarship statistics"""
        stats = {
            'active_count': 0,
            'pending_apps': 0,
            'total_awarded': 0.0,
            'available_funds': 0.0
        }

        try:
            with get_connection() as conn:
                # Active scholarships
                result = conn.execute("""
                    SELECT COUNT(*) as count
                    FROM scholarships
                    WHERE is_active = 1
                """).fetchone()
                stats['active_count'] = result['count'] if result else 0

                # Pending applications
                result = conn.execute("""
                    SELECT COUNT(*) as count
                    FROM scholarship_applications
                    WHERE status = 'pending'
                """).fetchone()
                stats['pending_apps'] = result['count'] if result else 0

                # Total awarded this year
                current_year = get_current_academic_year()
                result = conn.execute("""
                    SELECT COALESCE(SUM(ss.amount), 0) as total
                    FROM student_scholarships ss
                    JOIN scholarships s ON ss.scholarship_id = s.scholarship_id
                    WHERE s.academic_year = ? AND ss.status = 'active'
                """, (current_year,)).fetchone()
                stats['total_awarded'] = float(result['total']) if result else 0.0

                # Available funds (total scholarship amounts - awarded amounts)
                result = conn.execute("""
                    SELECT COALESCE(SUM(s.amount), 0) as total
                    FROM scholarships s
                    WHERE s.is_active = 1 AND s.academic_year = ?
                """, (current_year,)).fetchone()
                total_available = float(result['total']) if result else 0.0
                stats['available_funds'] = total_available - stats['total_awarded']

        except Exception as e:
            logger.error(f"Error fetching scholarship stats: {e}")

        return stats

    def _show_recent_activity(self):
        """Show recent scholarship activity"""
        activity_frame = ttk.LabelFrame(self.parent_frame, text="Recent Activity", padding=10)
        activity_frame.pack(fill='both', expand=True, padx=10, pady=10)

        try:
            with get_connection() as conn:
                activities = conn.execute("""
                    SELECT 'application' as type, sa.application_id as id,
                           s.scholarship_name as name, u.username as student,
                           sa.application_date as date, sa.status
                    FROM scholarship_applications sa
                    JOIN scholarships s ON sa.scholarship_id = s.scholarship_id
                    JOIN users u ON sa.student_id = u.student_id
                    ORDER BY sa.application_date DESC
                    LIMIT 15
                """).fetchall()

                if activities:
                    tree = create_data_table(activity_frame,
                                           ['Type', 'Student', 'Scholarship', 'Date', 'Status'],
                                           {'Type': 80, 'Student': 120, 'Scholarship': 250, 'Date': 120, 'Status': 100})

                    for activity in activities:
                        tree.insert('', 'end', values=(
                            activity['type'].title(),
                            activity['student'],
                            activity['name'],
                            format_date(activity['date']),
                            activity['status'].title()
                        ))
                else:
                    ttk.Label(activity_frame, text="No recent activity").pack()

        except Exception as e:
            logger.error(f"Error loading activity: {e}")

    def show_scholarships(self):
        """Display all scholarships"""
        # Check if parent frame is valid
        try:
            if not self.parent_frame.winfo_exists():
                logger.debug("Parent frame no longer exists (likely window closed)")
                return
        except Exception as e:
            logger.debug(f"Parent frame check failed: {e}")
            return

        clear_frame(self.parent_frame)

        # Title
        title_frame = ttk.Frame(self.parent_frame)
        title_frame.pack(fill='x', padx=10, pady=10)
        ttk.Label(title_frame, text="Manage Scholarships", style='Title.TLabel').pack(side='left')
        ttk.Button(title_frame, text="Back", command=self.show_main_interface).pack(side='right')

        # Search and filter
        search_entry, filter_combo = create_search_filter_bar(
            self.parent_frame,
            lambda: self._load_all_scholarships(search_entry.get(), filter_combo.get() if filter_combo else None),
            ['All', 'Active', 'Inactive', 'Expired']
        )

        # Scholarships table
        table_frame = ttk.Frame(self.parent_frame)
        table_frame.pack(fill='both', expand=True, padx=10, pady=10)

        columns = ['ID', 'Name', 'Amount', 'Academic Year', 'Deadline', 'Active']
        self.scholarships_tree = create_data_table(table_frame, columns, {
            'ID': 80, 'Name': 250, 'Amount': 100, 'Academic Year': 120, 'Deadline': 100, 'Active': 80
        })

        # Action buttons
        btn_frame = ttk.Frame(self.parent_frame)
        btn_frame.pack(fill='x', padx=10, pady=10)

        ttk.Button(btn_frame, text="Edit", command=self._edit_scholarship).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Activate", command=lambda: self._change_scholarship_status(True), style='Success.TButton').pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Deactivate", command=lambda: self._change_scholarship_status(False), style='Danger.TButton').pack(side='left', padx=5)
        ttk.Button(btn_frame, text="View Applications", command=self._view_scholarship_applications).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Create New", command=self.create_scholarship, style='Success.TButton').pack(side='right', padx=5)

        # Load scholarships
        self._load_all_scholarships()

    def _load_all_scholarships(self, search_term: str = '', filter_status: str = 'All'):
        """Load all scholarships into table"""
        try:
            # Clear existing
            for item in self.scholarships_tree.get_children():
                self.scholarships_tree.delete(item)

            with get_connection() as conn:
                query = "SELECT * FROM scholarships WHERE 1=1"
                params = []

                if search_term:
                    query += " AND scholarship_name LIKE ?"
                    params.append(f"%{search_term}%")

                if filter_status and filter_status != 'All':
                    if filter_status == 'Active':
                        query += " AND is_active = 1 AND deadline >= date('now')"
                    elif filter_status == 'Inactive':
                        query += " AND is_active = 0"
                    elif filter_status == 'Expired':
                        query += " AND deadline < date('now')"

                query += " ORDER BY created_at DESC"

                scholarships = conn.execute(query, params).fetchall()

                for scholarship in scholarships:
                    # Convert Row to dict to safely use .get()
                    sch_dict = dict(scholarship)
                    self.scholarships_tree.insert('', 'end', values=(
                        sch_dict['scholarship_id'],
                        sch_dict['scholarship_name'],
                        format_currency(sch_dict['amount']),
                        sch_dict.get('academic_year', 'N/A'),
                        format_date(sch_dict.get('deadline', 'N/A')),
                        'Yes' if sch_dict['is_active'] else 'No'
                    ))

        except Exception as e:
            logger.error(f"Error loading scholarships: {e}")
            show_error("Error", "Failed to load scholarships")

    def create_scholarship(self):
        """Create new scholarship"""
        create_window = tk.Toplevel(self.parent_frame)
        create_window.title("Create New Scholarship")
        create_window.geometry("600x700")

        # Title
        ttk.Label(create_window, text="Create New Scholarship", style='Title.TLabel').pack(pady=10)

        # Form frame
        form_frame = ttk.Frame(create_window, padding=20)
        form_frame.pack(fill='both', expand=True)

        fields = {}

        # Scholarship name
        ttk.Label(form_frame, text="Scholarship Name *", font=('Arial', 10, 'bold')).pack(anchor='w', pady=(10, 5))
        name_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=name_var, width=50).pack(fill='x')
        fields['name'] = name_var

        # Amount
        ttk.Label(form_frame, text="Amount (USD) *", font=('Arial', 10, 'bold')).pack(anchor='w', pady=(10, 5))
        amount_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=amount_var, width=20).pack(anchor='w')
        fields['amount'] = amount_var

        # Academic year
        ttk.Label(form_frame, text="Academic Year *", font=('Arial', 10, 'bold')).pack(anchor='w', pady=(10, 5))
        year_var = tk.StringVar(value=get_current_academic_year())
        ttk.Combobox(form_frame, textvariable=year_var, values=get_academic_year_list(), state='readonly', width=20).pack(anchor='w')
        fields['academic_year'] = year_var

        # Deadline
        ttk.Label(form_frame, text="Application Deadline *", font=('Arial', 10, 'bold')).pack(anchor='w', pady=(10, 5))
        deadline_frame = ttk.Frame(form_frame)
        deadline_frame.pack(anchor='w')
        deadline_var = tk.StringVar()
        ttk.Entry(deadline_frame, textvariable=deadline_var, width=20).pack(side='left')
        ttk.Label(deadline_frame, text="(YYYY-MM-DD)", foreground='gray').pack(side='left', padx=5)
        fields['deadline'] = deadline_var

        # Description
        ttk.Label(form_frame, text="Description", font=('Arial', 10, 'bold')).pack(anchor='w', pady=(10, 5))
        desc_text = scrolledtext.ScrolledText(form_frame, height=5, width=50)
        desc_text.pack(fill='x')
        fields['description'] = desc_text

        # Eligibility criteria
        ttk.Label(form_frame, text="Eligibility Criteria", font=('Arial', 10, 'bold')).pack(anchor='w', pady=(10, 5))
        criteria_text = scrolledtext.ScrolledText(form_frame, height=5, width=50)
        criteria_text.pack(fill='x')
        fields['criteria'] = criteria_text

        # Buttons
        btn_frame = ttk.Frame(form_frame)
        btn_frame.pack(pady=20)

        def submit():
            if self._validate_and_create_scholarship(fields):
                create_window.destroy()
                self.show_scholarships()

        ttk.Button(btn_frame, text="Create Scholarship", command=submit, style='Success.TButton').pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Cancel", command=create_window.destroy).pack(side='left', padx=5)

    def _validate_and_create_scholarship(self, fields: Dict) -> bool:
        """Validate and create scholarship"""
        try:
            # Validate required fields
            name = fields['name'].get().strip()
            if not name:
                show_error("Validation Error", "Scholarship name is required")
                return False

            amount_str = fields['amount'].get().strip()
            if not amount_str:
                show_error("Validation Error", "Amount is required")
                return False

            try:
                amount = float(amount_str.replace(',', ''))
                if amount <= 0:
                    show_error("Validation Error", "Amount must be positive")
                    return False
            except ValueError:
                show_error("Validation Error", "Invalid amount format")
                return False

            deadline = fields['deadline'].get().strip()
            if not deadline or not validate_date(deadline):
                show_error("Validation Error", "Valid deadline is required (YYYY-MM-DD)")
                return False

            # Create scholarship
            scholarship_id = self.scholarship_manager.create_scholarship(
                name=name,
                amount=amount,
                academic_year=fields['academic_year'].get(),
                deadline=deadline,
                description=fields['description'].get('1.0', 'end-1c').strip(),
                criteria=fields['criteria'].get('1.0', 'end-1c').strip()
            )

            if scholarship_id:
                log_activity('create', 'scholarship', scholarship_id, {
                    'name': name,
                    'amount': amount
                })

                show_success("Success", f"Scholarship '{name}' created successfully!")
                return True
            else:
                show_error("Error", "Failed to create scholarship")
                return False

        except Exception as e:
            logger.error(f"Error creating scholarship: {e}")
            show_error("Error", f"An error occurred: {str(e)}")
            return False

    def _edit_scholarship(self):
        """Edit selected scholarship"""
        selection = self.scholarships_tree.selection()
        if not selection:
            show_warning("Selection Required", "Please select a scholarship to edit")
            return

        item = self.scholarships_tree.item(selection[0])
        scholarship_id = item['values'][0]

        try:
            with get_connection() as conn:
                scholarship = conn.execute("""
                    SELECT * FROM scholarships WHERE scholarship_id = ?
                """, (scholarship_id,)).fetchone()

                if scholarship:
                    self._show_edit_scholarship_window(dict(scholarship))

        except Exception as e:
            logger.error(f"Error fetching scholarship: {e}")
            show_error("Error", "Failed to load scholarship details")

    def _show_edit_scholarship_window(self, scholarship: Dict):
        """Show edit scholarship window"""
        edit_window = tk.Toplevel(self.parent_frame)
        edit_window.title(f"Edit Scholarship - {scholarship['scholarship_name']}")
        edit_window.geometry("600x700")

        # Title
        ttk.Label(edit_window, text="Edit Scholarship", style='Title.TLabel').pack(pady=10)

        # Form frame (similar to create, but pre-populated)
        form_frame = ttk.Frame(edit_window, padding=20)
        form_frame.pack(fill='both', expand=True)

        fields = {}

        # Scholarship name
        ttk.Label(form_frame, text="Scholarship Name *", font=('Arial', 10, 'bold')).pack(anchor='w', pady=(10, 5))
        name_var = tk.StringVar(value=scholarship['scholarship_name'])
        ttk.Entry(form_frame, textvariable=name_var, width=50).pack(fill='x')
        fields['name'] = name_var

        # Amount
        ttk.Label(form_frame, text="Amount (USD) *", font=('Arial', 10, 'bold')).pack(anchor='w', pady=(10, 5))
        amount_var = tk.StringVar(value=str(scholarship['amount']))
        ttk.Entry(form_frame, textvariable=amount_var, width=20).pack(anchor='w')
        fields['amount'] = amount_var

        # Academic year
        ttk.Label(form_frame, text="Academic Year *", font=('Arial', 10, 'bold')).pack(anchor='w', pady=(10, 5))
        year_var = tk.StringVar(value=scholarship.get('academic_year', get_current_academic_year()))
        ttk.Combobox(form_frame, textvariable=year_var, values=get_academic_year_list(), state='readonly', width=20).pack(anchor='w')
        fields['academic_year'] = year_var

        # Deadline
        ttk.Label(form_frame, text="Application Deadline *", font=('Arial', 10, 'bold')).pack(anchor='w', pady=(10, 5))
        deadline_var = tk.StringVar(value=scholarship.get('deadline', ''))
        ttk.Entry(form_frame, textvariable=deadline_var, width=20).pack(anchor='w')
        fields['deadline'] = deadline_var

        # Description
        ttk.Label(form_frame, text="Description", font=('Arial', 10, 'bold')).pack(anchor='w', pady=(10, 5))
        desc_text = scrolledtext.ScrolledText(form_frame, height=5, width=50)
        desc_text.insert('1.0', scholarship.get('description', ''))
        desc_text.pack(fill='x')
        fields['description'] = desc_text

        # Criteria
        ttk.Label(form_frame, text="Eligibility Criteria", font=('Arial', 10, 'bold')).pack(anchor='w', pady=(10, 5))
        criteria_text = scrolledtext.ScrolledText(form_frame, height=5, width=50)
        criteria_text.insert('1.0', scholarship.get('criteria', ''))
        criteria_text.pack(fill='x')
        fields['criteria'] = criteria_text

        # Buttons
        btn_frame = ttk.Frame(form_frame)
        btn_frame.pack(pady=20)

        def update():
            if self._update_scholarship(scholarship['scholarship_id'], fields):
                edit_window.destroy()
                self.show_scholarships()

        ttk.Button(btn_frame, text="Update", command=update, style='Success.TButton').pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Cancel", command=edit_window.destroy).pack(side='left', padx=5)

    def _update_scholarship(self, scholarship_id: str, fields: Dict) -> bool:
        """Update scholarship"""
        try:
            with transaction() as conn:
                conn.execute("""
                    UPDATE scholarships
                    SET scholarship_name = ?, amount = ?, academic_year = ?,
                        deadline = ?, description = ?, criteria = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE scholarship_id = ?
                """, (
                    fields['name'].get().strip(),
                    float(fields['amount'].get().replace(',', '')),
                    fields['academic_year'].get(),
                    fields['deadline'].get().strip(),
                    fields['description'].get('1.0', 'end-1c').strip(),
                    fields['criteria'].get('1.0', 'end-1c').strip(),
                    scholarship_id
                ))

            log_activity('update', 'scholarship', scholarship_id, {'action': 'updated'})
            show_success("Success", "Scholarship updated successfully!")
            return True

        except Exception as e:
            logger.error(f"Error updating scholarship: {e}")
            show_error("Error", f"Failed to update scholarship: {str(e)}")
            return False

    def _change_scholarship_status(self, activate: bool):
        """Activate or deactivate scholarship"""
        selection = self.scholarships_tree.selection()
        if not selection:
            show_warning("Selection Required", "Please select a scholarship")
            return

        item = self.scholarships_tree.item(selection[0])
        scholarship_id = item['values'][0]
        current_status = item['values'][5]

        # Check if already in desired state
        is_currently_active = (current_status == 'Yes')
        if activate and is_currently_active:
            show_warning("Already Active", "This scholarship is already active")
            return
        if not activate and not is_currently_active:
            show_warning("Already Inactive", "This scholarship is already inactive")
            return

        action = 'Activate' if activate else 'Deactivate'
        if confirm_action(f"{action} this scholarship?"):
            try:
                new_status = 1 if activate else 0

                with transaction() as conn:
                    conn.execute("""
                        UPDATE scholarships
                        SET is_active = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE scholarship_id = ?
                    """, (new_status, scholarship_id))

                log_activity('update', 'scholarship', scholarship_id, {
                    'action': 'activated' if activate else 'deactivated'
                })

                show_success("Success", f"Scholarship {action.lower()}d successfully!")
                self._load_all_scholarships()

            except Exception as e:
                logger.error(f"Error updating scholarship status: {e}")
                show_error("Error", "Failed to update status")

    def _view_scholarship_applications(self):
        """View applications for selected scholarship"""
        selection = self.scholarships_tree.selection()
        if not selection:
            show_warning("Selection Required", "Please select a scholarship")
            return

        item = self.scholarships_tree.item(selection[0])
        scholarship_id = item['values'][0]
        scholarship_name = item['values'][1]

        # Show applications window
        apps_window = tk.Toplevel(self.parent_frame)
        apps_window.title(f"Applications - {scholarship_name}")
        apps_window.geometry("900x600")

        ttk.Label(apps_window, text=f"Applications for: {scholarship_name}", style='Title.TLabel').pack(pady=10)

        # Applications table
        table_frame = ttk.Frame(apps_window)
        table_frame.pack(fill='both', expand=True, padx=10, pady=10)

        columns = ['App ID', 'Student', 'GPA', 'Submitted', 'Status']
        tree = create_data_table(table_frame, columns, {
            'App ID': 80, 'Student': 150, 'GPA': 80, 'Submitted': 120, 'Status': 100
        })

        try:
            with get_connection() as conn:
                applications = conn.execute("""
                    SELECT sa.*, u.username, u.email
                    FROM scholarship_applications sa
                    JOIN users u ON sa.student_id = u.student_id
                    WHERE sa.scholarship_id = ?
                    ORDER BY sa.application_date DESC
                """, (scholarship_id,)).fetchall()

                for app in applications:
                    app_data = json.loads(app.get('application_data', '{}'))
                    tree.insert('', 'end', values=(
                        app['application_id'],
                        app['username'],
                        app_data.get('gpa', 'N/A'),
                        format_date(app['submitted_date']),
                        app['status'].title()
                    ))

        except Exception as e:
            logger.error(f"Error loading applications: {e}")
            ttk.Label(table_frame, text="Error loading applications", foreground='red').pack()

    def review_applications(self):
        """Show application review interface"""
        # Check if parent frame is valid before proceeding
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
        ttk.Label(title_frame, text="Review Scholarship Applications", style='Title.TLabel').pack(side='left')
        ttk.Button(title_frame, text="Back", command=self.show_main_interface).pack(side='right')

        # Pending applications
        table_frame = ttk.Frame(self.parent_frame)
        table_frame.pack(fill='both', expand=True, padx=10, pady=10)

        columns = ['App ID', 'Student', 'Scholarship', 'GPA', 'Submitted', 'Status']
        self.applications_tree = create_data_table(table_frame, columns, {
            'App ID': 80, 'Student': 120, 'Scholarship': 200, 'GPA': 80, 'Submitted': 120, 'Status': 100
        })

        # Action buttons
        btn_frame = ttk.Frame(self.parent_frame)
        btn_frame.pack(fill='x', padx=10, pady=10)

        ttk.Button(btn_frame, text="View Details", command=self._view_application_details).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Approve", command=lambda: self._review_application('approved'), style='Success.TButton').pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Deny", command=lambda: self._review_application('denied'), style='Danger.TButton').pack(side='left', padx=5)

        # Load applications
        self._load_pending_applications()

    def _load_pending_applications(self):
        """Load pending applications"""
        try:
            for item in self.applications_tree.get_children():
                self.applications_tree.delete(item)

            with get_connection() as conn:
                applications = conn.execute("""
                    SELECT sa.*, u.username, s.scholarship_name
                    FROM scholarship_applications sa
                    JOIN users u ON sa.student_id = u.student_id
                    JOIN scholarships s ON sa.scholarship_id = s.scholarship_id
                    WHERE sa.status = 'pending'
                    ORDER BY sa.application_date ASC
                """).fetchall()

                for app in applications:
                    app_data = json.loads(app.get('application_data', '{}'))
                    self.applications_tree.insert('', 'end', values=(
                        app['application_id'],
                        app['username'],
                        app['scholarship_name'],
                        app_data.get('gpa', 'N/A'),
                        format_date(app['submitted_date']),
                        app['status'].title()
                    ))

        except Exception as e:
            logger.error(f"Error loading applications: {e}")
            show_error("Error", "Failed to load applications")

    def _view_application_details(self):
        """View application details"""
        selection = self.applications_tree.selection()
        if not selection:
            show_warning("Selection Required", "Please select an application")
            return

        item = self.applications_tree.item(selection[0])
        app_id = item['values'][0]

        try:
            with get_connection() as conn:
                app = conn.execute("""
                    SELECT sa.*, u.username, u.email, s.scholarship_name, s.amount
                    FROM scholarship_applications sa
                    JOIN users u ON sa.student_id = u.student_id
                    JOIN scholarships s ON sa.scholarship_id = s.scholarship_id
                    WHERE sa.application_id = ?
                """, (app_id,)).fetchone()

                if app:
                    self._show_application_details_window(dict(app))

        except Exception as e:
            logger.error(f"Error fetching application: {e}")
            show_error("Error", "Failed to load application details")

    def _show_application_details_window(self, app: Dict):
        """Show application details window"""
        details_window = tk.Toplevel(self.parent_frame)
        details_window.title(f"Application Details - {app['application_id']}")
        details_window.geometry("700x600")

        # Create scrollable frame
        scrollable_frame, canvas, scrollbar = create_scrollable_frame(details_window)
        canvas.pack(side='left', fill='both', expand=True, padx=10, pady=10)
        scrollbar.pack(side='right', fill='y')

        # Title
        ttk.Label(scrollable_frame, text="Scholarship Application Details", style='Title.TLabel').pack(pady=10)

        # Application info
        app_data = json.loads(app.get('application_data', '{}'))

        details = [
            ("Application ID", app['application_id']),
            ("Student", f"{app['username']} ({app['email']})"),
            ("Scholarship", f"{app['scholarship_name']} - {format_currency(app['amount'])}"),
            ("Submitted Date", format_date(app['submitted_date'])),
            ("Status", app['status'].title()),
            ("GPA", app_data.get('gpa', 'N/A')),
            ("Expected Graduation", app_data.get('expected_graduation', 'N/A')),
            ("Reference Name", app_data.get('reference_name', 'N/A')),
            ("Reference Email", app_data.get('reference_email', 'N/A')),
        ]

        for label, value in details:
            frame = ttk.Frame(scrollable_frame)
            frame.pack(fill='x', padx=20, pady=5)
            ttk.Label(frame, text=f"{label}:", font=('Arial', 10, 'bold')).pack(anchor='w')
            ttk.Label(frame, text=str(value)).pack(anchor='w', padx=20)

        # Essay
        ttk.Label(scrollable_frame, text="Personal Statement / Essay:", font=('Arial', 10, 'bold')).pack(anchor='w', padx=20, pady=(20, 5))
        essay_frame = ttk.Frame(scrollable_frame, relief='sunken', borderwidth=1)
        essay_frame.pack(fill='x', padx=20, pady=5)
        essay_text = scrolledtext.ScrolledText(essay_frame, height=10, width=60, wrap='word')
        essay_text.insert('1.0', app_data.get('essay', 'No essay provided'))
        essay_text.config(state='disabled')
        essay_text.pack(fill='both', expand=True, padx=5, pady=5)

        # Action buttons (if pending)
        if app['status'] == 'pending':
            btn_frame = ttk.Frame(scrollable_frame)
            btn_frame.pack(pady=20)

            def approve():
                if self._review_application_by_id(app['application_id'], 'approved'):
                    details_window.destroy()

            def deny():
                if self._review_application_by_id(app['application_id'], 'denied'):
                    details_window.destroy()

            ttk.Button(btn_frame, text="Approve", command=approve, style='Success.TButton').pack(side='left', padx=5)
            ttk.Button(btn_frame, text="Deny", command=deny, style='Danger.TButton').pack(side='left', padx=5)

        ttk.Button(scrollable_frame, text="Close", command=details_window.destroy).pack(pady=10)

    def _review_application(self, status: str):
        """Review selected application"""
        selection = self.applications_tree.selection()
        if not selection:
            show_warning("Selection Required", "Please select an application")
            return

        item = self.applications_tree.item(selection[0])
        app_id = item['values'][0]

        self._review_application_by_id(app_id, status)

    def _review_application_by_id(self, app_id: str, status: str) -> bool:
        """Review application by ID"""
        try:
            result = self.scholarship_manager.review_application(
                application_id=app_id,
                status=status,
                reviewer_id=get_student_id()
            )

            if result:
                log_activity('update', 'scholarship_application', app_id, {
                    'action': 'reviewed',
                    'status': status
                })

                show_success("Success", f"Application {status}!")
                self._load_pending_applications()
                return True
            else:
                show_error("Error", "Failed to review application")
                return False

        except Exception as e:
            logger.error(f"Error reviewing application: {e}")
            show_error("Error", f"An error occurred: {str(e)}")
            return False

    def show_awards(self):
        """Show scholarship awards interface"""
        # Check if parent frame is valid
        try:
            if not self.parent_frame.winfo_exists():
                logger.debug("Parent frame no longer exists (likely window closed)")
                return
        except Exception as e:
            logger.debug(f"Parent frame check failed: {e}")
            return

        clear_frame(self.parent_frame)

        # Title
        title_frame = ttk.Frame(self.parent_frame)
        title_frame.pack(fill='x', padx=10, pady=10)
        ttk.Label(title_frame, text="Scholarship Awards", style='Title.TLabel').pack(side='left')
        ttk.Button(title_frame, text="Back", command=self.show_main_interface).pack(side='right')

        # Awards table
        table_frame = ttk.Frame(self.parent_frame)
        table_frame.pack(fill='both', expand=True, padx=10, pady=10)

        columns = ['Award ID', 'Student', 'Scholarship', 'Amount', 'Awarded Date', 'Status']
        tree = create_data_table(table_frame, columns, {
            'Award ID': 80, 'Student': 120, 'Scholarship': 200, 'Amount': 100, 'Awarded Date': 120, 'Status': 100
        })

        try:
            with get_connection() as conn:
                awards = conn.execute("""
                    SELECT ss.*, u.username, s.scholarship_name
                    FROM student_scholarships ss
                    JOIN users u ON ss.student_id = u.student_id
                    JOIN scholarships s ON ss.scholarship_id = s.scholarship_id
                    ORDER BY ss.awarded_date DESC
                """).fetchall()

                for award in awards:
                    tree.insert('', 'end', values=(
                        award['student_scholarship_id'],
                        award['username'],
                        award['scholarship_name'],
                        format_currency(award['amount']),
                        format_date(award['awarded_date']),
                        award['status'].title()
                    ))

        except Exception as e:
            logger.error(f"Error loading awards: {e}")
            show_error("Error", "Failed to load awards")
