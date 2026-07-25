"""
Aid application review mixin for AdminPortal.
"""

from education_system.systems.university.interfaces.gui.finance.financial_aid.admin_portal._imports import (
    tk, ttk, scrolledtext, json, logging,
    get_connection, log_activity,
    clear_frame, create_data_table, create_scrollable_frame,
    format_currency, format_date,
    show_error, show_success, show_warning,
    messagebox, get_text,
    Dict,
)

logger = logging.getLogger(__name__)


class ApplicationsMixin:
    """Methods for reviewing financial aid applications."""

    def show_aid_applications(self):
        """Show financial aid applications for review"""
        self._prepare_view_parent()

        # Title
        title_frame = ttk.Frame(self.parent_frame)
        title_frame.pack(fill='x', padx=10, pady=10)
        ttk.Label(title_frame, text=get_text("financial_aid.admin_portal.applications.title", "Financial Aid Applications"), style='Title.TLabel').pack(side='left')
        ttk.Button(title_frame, text=get_text("financial_aid.admin_portal.buttons.back_to_dashboard", "Back to Dashboard"), command=self.show_dashboard).pack(side='right')

        # Filter by status
        filter_frame = ttk.Frame(self.parent_frame)
        filter_frame.pack(fill='x', padx=10, pady=10)

        ttk.Label(filter_frame, text=get_text("financial_aid.admin_portal.labels.status", "Status:")).pack(side='left', padx=5)
        status_var = tk.StringVar(value='pending')
        status_combo = ttk.Combobox(filter_frame, textvariable=status_var,
                                    values=[get_text("financial_aid.admin_portal.disbursements.status_filters.all", "All"), 'pending', 'under_review', 'approved', 'denied'],
                                    state='readonly', width=15)
        status_combo.pack(side='left', padx=5)
        ttk.Button(filter_frame, text=get_text("financial_aid.admin_portal.buttons.filter", "Filter"),
                  command=lambda: self._load_aid_applications(status_var.get())).pack(side='left', padx=5)

        # Applications table
        table_frame = ttk.Frame(self.parent_frame)
        table_frame.pack(fill='both', expand=True, padx=10, pady=10)

        columns = [get_text("financial_aid.admin_portal.columns.app_id", "App ID"), get_text("financial_aid.admin_portal.columns.student", "Student"), get_text("financial_aid.admin_portal.columns.academic_year", "Academic Year"), get_text("financial_aid.admin_portal.columns.aid_type", "Aid Type"), get_text("financial_aid.admin_portal.columns.submitted", "Submitted"), get_text("financial_aid.admin_portal.columns.status", "Status")]
        self.aid_apps_tree = create_data_table(table_frame, columns, {
            get_text("financial_aid.admin_portal.columns.app_id", "App ID"): 80, get_text("financial_aid.admin_portal.columns.student", "Student"): 150, get_text("financial_aid.admin_portal.columns.academic_year", "Academic Year"): 120, get_text("financial_aid.admin_portal.columns.aid_type", "Aid Type"): 120, get_text("financial_aid.admin_portal.columns.submitted", "Submitted"): 120, get_text("financial_aid.admin_portal.columns.status", "Status"): 100
        })

        # Action buttons
        btn_frame = ttk.Frame(self.parent_frame)
        btn_frame.pack(fill='x', padx=10, pady=10)

        ttk.Button(btn_frame, text=get_text("financial_aid.admin_portal.buttons.view_details", "View Details"), command=self._view_aid_application_details).pack(side='left', padx=5)
        ttk.Button(btn_frame, text=get_text("financial_aid.admin_portal.buttons.approve", "Approve"), command=lambda: self._review_aid_application('approved'),
                  style='Success.TButton').pack(side='left', padx=5)
        ttk.Button(btn_frame, text=get_text("financial_aid.admin_portal.buttons.deny", "Deny"), command=lambda: self._review_aid_application('denied'),
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

                    if status_filter and status_filter != get_text("financial_aid.admin_portal.disbursements.status_filters.all", "All"):
                        query += " AND fa.status = ?"
                        params.append(status_filter)

                    query += " ORDER BY fa.application_date DESC"

                    applications = conn.execute(query, params).fetchall()
                except Exception as e:
                    if "no such table" in str(e):
                        # Table doesn't exist yet - show message
                        messagebox.showinfo(get_text("financial_aid.admin_portal.dialogs.table_not_found", "Table Not Found"),
                                          get_text("financial_aid.admin_portal.messages.table_not_found", "The financial_aid_applications table does not exist yet.\n\nThis feature requires database setup."))
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
            show_error(get_text("financial_aid.admin_portal.dialogs.error", "Error"), get_text("financial_aid.admin_portal.errors.failed_load_applications", "Failed to load applications"))

    def _view_aid_application_details(self):
        """View aid application details"""
        selection = self.aid_apps_tree.selection()
        if not selection:
            show_warning(get_text("financial_aid.admin_portal.dialogs.selection_required", "Selection Required"), get_text("financial_aid.admin_portal.messages.select_application", "Please select an application"))
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
                        messagebox.showerror(get_text("financial_aid.admin_portal.dialogs.table_not_found", "Table Not Found"),
                                           get_text("financial_aid.admin_portal.messages.table_not_found_short", "The financial_aid_applications table does not exist yet."))
                        return
                    raise

                if app:
                    self._show_aid_application_details_window(dict(app))

        except Exception as e:
            logger.error(f"Error fetching application: {e}")
            show_error(get_text("financial_aid.admin_portal.dialogs.error", "Error"), get_text("financial_aid.admin_portal.errors.failed_load_application_details", "Failed to load application details"))

    def _show_aid_application_details_window(self, app: Dict):
        """Show aid application details window"""
        details_window = tk.Toplevel(self.parent_frame)
        details_window.title(get_text("financial_aid.admin_portal.dialogs.aid_application", "Aid Application") + f" - {app['application_id']}")
        details_window.geometry("700x600")

        # Create scrollable frame
        scrollable_frame, canvas, scrollbar = create_scrollable_frame(details_window)
        canvas.pack(side='left', fill='both', expand=True, padx=10, pady=10)
        scrollbar.pack(side='right', fill='y')

        # Title
        ttk.Label(scrollable_frame, text=get_text("financial_aid.admin_portal.details.title", "Financial Aid Application Details"),
                 style='Title.TLabel').pack(pady=10)

        # Application data
        app_data = json.loads(app.get('application_data', '{}'))

        details = [
            (get_text("financial_aid.admin_portal.details.application_id", "Application ID"), app['application_id']),
            (get_text("financial_aid.admin_portal.details.student", "Student"), f"{app['username']} ({app['email']})"),
            (get_text("financial_aid.admin_portal.details.academic_year", "Academic Year"), app['academic_year']),
            (get_text("financial_aid.admin_portal.details.aid_type_requested", "Aid Type Requested"), app_data.get('aid_type', 'N/A')),
            (get_text("financial_aid.admin_portal.details.application_date", "Application Date"), format_date(app['application_date'])),
            (get_text("financial_aid.admin_portal.details.status", "Status"), app['status'].title()),
            (get_text("financial_aid.admin_portal.details.household_income", "Household Income"), format_currency(app_data.get('household_income', 0))),
            (get_text("financial_aid.admin_portal.details.num_dependents", "Number of Dependents"), str(app_data.get('dependents', 0))),
        ]

        for label, value in details:
            frame = ttk.Frame(scrollable_frame)
            frame.pack(fill='x', padx=20, pady=5)
            ttk.Label(frame, text=f"{label}:", font=('Arial', 10, 'bold')).pack(anchor='w')
            ttk.Label(frame, text=str(value)).pack(anchor='w', padx=20)

        # Additional information
        if app_data.get('additional_info'):
            ttk.Label(scrollable_frame, text=get_text("financial_aid.admin_portal.details.additional_info", "Additional Information:"),
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

            ttk.Button(btn_frame, text=get_text("financial_aid.admin_portal.buttons.approve", "Approve"), command=approve,
                      style='Success.TButton').pack(side='left', padx=5)
            ttk.Button(btn_frame, text=get_text("financial_aid.admin_portal.buttons.deny", "Deny"), command=deny,
                      style='Danger.TButton').pack(side='left', padx=5)
            ttk.Button(btn_frame, text=get_text("financial_aid.admin_portal.buttons.create_aid_package", "Create Aid Package"),
                      command=lambda: [details_window.destroy(),
                                     self.show_create_package(app['student_id'], app['academic_year'])]).pack(side='left', padx=5)

        ttk.Button(scrollable_frame, text=get_text("financial_aid.admin_portal.buttons.close", "Close"), command=details_window.destroy).pack(pady=10)

    def _review_aid_application(self, status: str):
        """Review selected aid application"""
        selection = self.aid_apps_tree.selection()
        if not selection:
            show_warning(get_text("financial_aid.admin_portal.dialogs.selection_required", "Selection Required"), get_text("financial_aid.admin_portal.messages.select_application", "Please select an application"))
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

                show_success(get_text("financial_aid.admin_portal.dialogs.success", "Success"), get_text("financial_aid.admin_portal.messages.application_reviewed", "Application {status}!").format(status=status))
                self._load_aid_applications()
                return True
            else:
                show_error(get_text("financial_aid.admin_portal.dialogs.error", "Error"), get_text("financial_aid.admin_portal.errors.failed_review_application", "Failed to review application"))
                return False

        except Exception as e:
            logger.error(f"Error reviewing application: {e}")
            show_error(get_text("financial_aid.admin_portal.dialogs.error", "Error"), get_text("financial_aid.admin_portal.errors.error_occurred", "An error occurred: {error}").format(error=str(e)))
            return False
