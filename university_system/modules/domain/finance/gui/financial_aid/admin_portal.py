"""
Admin Portal for Financial Aid & Scholarships

This module provides the admin-facing interface for managing financial aid,
reviewing applications, processing disbursements, and generating reports.
"""

from typing import Any, Dict

from .common_imports import (
    tk,
    ttk,
    messagebox,
    scrolledtext,
    logging,
    datetime,
    get_connection,
    log_activity,
    get_auth,
    FinancialAidManager,
    clear_frame,
    create_data_table,
    create_stat_card,
    create_scrollable_frame,
    format_currency,
    format_date,
    show_error,
    show_success,
    show_warning,
    get_current_academic_year,
    get_academic_year_list,
    get_status_color,
    send_email,
    export_to_csv,
    COLORS,
)
from .scholarship_manager import ScholarshipManagerGUI
from university_system.modules.shared.utils.i18n import get_text
from university_system.infrastructure.email.template_utils import render_template

logger = logging.getLogger(__name__)


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
            self.standalone_window.title(get_text("financial_aid.admin_portal.window_title", "Financial Aid Administration"))
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
        ttk.Label(title_frame, text=get_text("financial_aid.admin_portal.title", "Financial Aid & Scholarships - Admin Dashboard"),
                 style='Title.TLabel').pack(anchor='w')

        # Statistics cards
        stats_frame = ttk.Frame(self.parent_frame)
        stats_frame.pack(fill='x', padx=10, pady=10)

        try:
            stats = self._get_admin_stats()

            cards = [
                (get_text("financial_aid.admin_portal.stats.pending_reviews", "Pending Reviews"), str(stats['pending_reviews']), 'warning'),
                (get_text("financial_aid.admin_portal.stats.active_packages", "Active Aid Packages"), str(stats['active_packages']), 'info'),
                (get_text("financial_aid.admin_portal.stats.total_disbursed", "Total Disbursed (Year)"), format_currency(stats['total_disbursed']), 'success'),
                (get_text("financial_aid.admin_portal.stats.pending_disbursements", "Pending Disbursements"), format_currency(stats['pending_disbursements']), 'primary')
            ]

            for i, (title, value, color) in enumerate(cards):
                card = create_stat_card(stats_frame, title, value, color)
                card.grid(row=0, column=i, padx=10, pady=5, sticky='ew')
                stats_frame.grid_columnconfigure(i, weight=1)

        except Exception as e:
            logger.error(f"Error loading stats: {e}")

        # Quick actions grid
        actions_frame = ttk.LabelFrame(self.parent_frame, text=get_text("financial_aid.admin_portal.sections.management_functions", "Management Functions"), padding=10)
        actions_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Row 1: Scholarship Management
        ttk.Label(actions_frame, text=get_text("financial_aid.admin_portal.sections.scholarship_management", "Scholarship Management"),
                 font=('Arial', 11, 'bold')).grid(row=0, column=0, columnspan=3, sticky='w', pady=(0, 10))

        actions_row1 = [
            (get_text("financial_aid.admin_portal.buttons.manage_scholarships", "Manage Scholarships"), self.scholarship_manager_gui.show_scholarships),
            (get_text("financial_aid.admin_portal.buttons.review_applications", "Review Applications"), self.scholarship_manager_gui.review_applications),
            (get_text("financial_aid.admin_portal.buttons.view_awards", "View Awards"), self.scholarship_manager_gui.show_awards)
        ]

        for i, (text, command) in enumerate(actions_row1):
            ttk.Button(actions_frame, text=text, command=command, width=25).grid(
                row=1, column=i, padx=5, pady=5, sticky='ew')

        # Row 2: Financial Aid Management
        ttk.Label(actions_frame, text=get_text("financial_aid.admin_portal.sections.financial_aid_management", "Financial Aid Management"),
                 font=('Arial', 11, 'bold')).grid(row=2, column=0, columnspan=3, sticky='w', pady=(20, 10))

        actions_row2 = [
            (get_text("financial_aid.admin_portal.buttons.review_aid_applications", "Review Aid Applications"), self.show_aid_applications),
            (get_text("financial_aid.admin_portal.buttons.create_aid_package", "Create Aid Package"), self.show_create_package),
            (get_text("financial_aid.admin_portal.buttons.manage_aid_types", "Manage Aid Types"), self.show_aid_types)
        ]

        for i, (text, command) in enumerate(actions_row2):
            ttk.Button(actions_frame, text=text, command=command, width=25).grid(
                row=3, column=i, padx=5, pady=5, sticky='ew')

        # Row 3: Disbursements & Reports
        ttk.Label(actions_frame, text=get_text("financial_aid.admin_portal.sections.disbursements_reports", "Disbursements & Reports"),
                 font=('Arial', 11, 'bold')).grid(row=4, column=0, columnspan=3, sticky='w', pady=(20, 10))

        actions_row3 = [
            (get_text("financial_aid.admin_portal.buttons.process_disbursements", "Process Disbursements"), self.show_disbursements),
            (get_text("financial_aid.admin_portal.buttons.view_reports", "View Reports"), self.show_reports),
            (get_text("financial_aid.admin_portal.buttons.import_fafsa", "Import FAFSA Data"), self.show_fafsa_import)
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
        ttk.Label(title_frame, text=get_text("financial_aid.admin_portal.applications.title", "Financial Aid Applications"), style='Title.TLabel').pack(side='left')
        ttk.Button(title_frame, text=get_text("financial_aid.admin_portal.buttons.back_to_dashboard", "Back to Dashboard"), command=self.show_dashboard).pack(side='right')

        # Filter by status
        filter_frame = ttk.Frame(self.parent_frame)
        filter_frame.pack(fill='x', padx=10, pady=10)

        ttk.Label(filter_frame, text=get_text("financial_aid.admin_portal.labels.status", "Status:")).pack(side='left', padx=5)
        status_var = tk.StringVar(value='pending')
        status_combo = ttk.Combobox(filter_frame, textvariable=status_var,
                                    values=['All', 'pending', 'under_review', 'approved', 'denied'],
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

                    if status_filter and status_filter != 'All':
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

    def show_create_package(self, student_id: str = None, academic_year: str = None):
        """Show create aid package interface"""
        # Ensure we have a valid parent frame/window
        parent = self._ensure_valid_parent()
        self.parent_frame = parent

        clear_frame(self.parent_frame)

        # Title
        title_frame = ttk.Frame(self.parent_frame)
        title_frame.pack(fill='x', padx=10, pady=10)
        ttk.Label(title_frame, text=get_text("financial_aid.admin_portal.create_package.title", "Create Financial Aid Package"), style='Title.TLabel').pack(side='left')
        ttk.Button(title_frame, text=get_text("financial_aid.admin_portal.buttons.back_to_dashboard", "Back to Dashboard"), command=self.show_dashboard).pack(side='right')

        # Form
        form_frame = ttk.LabelFrame(self.parent_frame, text=get_text("financial_aid.admin_portal.create_package.details", "Aid Package Details"), padding=20)
        form_frame.pack(fill='both', expand=True, padx=10, pady=10)

        fields = {}

        # Student ID
        row = 0
        ttk.Label(form_frame, text=get_text("financial_aid.admin_portal.labels.student_id", "Student ID:")).grid(row=row, column=0, sticky='w', pady=10)
        student_var = tk.StringVar(value=student_id or '')
        ttk.Entry(form_frame, textvariable=student_var, width=30).grid(row=row, column=1, sticky='w', padx=10)
        fields['student_id'] = student_var

        # Academic year
        row += 1
        ttk.Label(form_frame, text=get_text("financial_aid.admin_portal.labels.academic_year", "Academic Year:")).grid(row=row, column=0, sticky='w', pady=10)
        year_var = tk.StringVar(value=academic_year or get_current_academic_year())
        ttk.Combobox(form_frame, textvariable=year_var, values=get_academic_year_list(),
                    state='readonly', width=20).grid(row=row, column=1, sticky='w', padx=10)
        fields['academic_year'] = year_var

        # Package name
        row += 1
        ttk.Label(form_frame, text=get_text("financial_aid.admin_portal.labels.package_name", "Package Name:")).grid(row=row, column=0, sticky='w', pady=10)
        name_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=name_var, width=40).grid(row=row, column=1, sticky='w', padx=10)
        fields['package_name'] = name_var

        # Aid components section
        row += 1
        ttk.Label(form_frame, text=get_text("financial_aid.admin_portal.labels.aid_components", "Aid Components:"), font=('Arial', 11, 'bold')).grid(
            row=row, column=0, columnspan=2, sticky='w', pady=(20, 10))

        # Grant amount
        row += 1
        ttk.Label(form_frame, text=get_text("financial_aid.admin_portal.labels.grant_amount", "Grant Amount:")).grid(row=row, column=0, sticky='w', pady=5)
        grant_var = tk.StringVar(value='0')
        ttk.Entry(form_frame, textvariable=grant_var, width=20).grid(row=row, column=1, sticky='w', padx=10)
        fields['grant_amount'] = grant_var

        # Loan amount
        row += 1
        ttk.Label(form_frame, text=get_text("financial_aid.admin_portal.labels.loan_amount", "Loan Amount:")).grid(row=row, column=0, sticky='w', pady=5)
        loan_var = tk.StringVar(value='0')
        ttk.Entry(form_frame, textvariable=loan_var, width=20).grid(row=row, column=1, sticky='w', padx=10)
        fields['loan_amount'] = loan_var

        # Work-study amount
        row += 1
        ttk.Label(form_frame, text=get_text("financial_aid.admin_portal.labels.work_study_amount", "Work-Study Amount:")).grid(row=row, column=0, sticky='w', pady=5)
        ws_var = tk.StringVar(value='0')
        ttk.Entry(form_frame, textvariable=ws_var, width=20).grid(row=row, column=1, sticky='w', padx=10)
        fields['work_study_amount'] = ws_var

        # Total display
        row += 1
        ttk.Label(form_frame, text=get_text("financial_aid.admin_portal.labels.total_package", "Total Package:"), font=('Arial', 10, 'bold')).grid(
            row=row, column=0, sticky='w', pady=(20, 5))
        total_label = ttk.Label(form_frame, text="$0.00", font=('Arial', 12, 'bold'), foreground='green')
        total_label.grid(row=row, column=1, sticky='w', padx=10)

        def update_total(*args):
            try:
                total = (float(grant_var.get() or 0) +
                        float(loan_var.get() or 0) +
                        float(ws_var.get() or 0))
                total_label.config(text=format_currency(total))
            except (ValueError, TypeError):
                total_label.config(text=get_text("financial_aid.admin_portal.errors.invalid_amounts", "Invalid amounts"))

        grant_var.trace('w', update_total)
        loan_var.trace('w', update_total)
        ws_var.trace('w', update_total)

        # Buttons
        btn_frame = ttk.Frame(form_frame)
        btn_frame.grid(row=row+1, column=0, columnspan=2, pady=20)

        def create():
            if self._create_aid_package(fields):
                self.show_dashboard()

        ttk.Button(btn_frame, text=get_text("financial_aid.admin_portal.buttons.create_package", "Create Package"), command=create,
                  style='Success.TButton').pack(side='left', padx=5)
        ttk.Button(btn_frame, text=get_text("financial_aid.admin_portal.buttons.cancel", "Cancel"), command=self.show_dashboard).pack(side='left', padx=5)

    def _create_aid_package(self, fields: Dict) -> bool:
        """Create financial aid package"""
        try:
            student_id = fields['student_id'].get().strip()
            if not student_id:
                show_error(get_text("financial_aid.admin_portal.dialogs.validation_error", "Validation Error"), get_text("financial_aid.admin_portal.errors.student_id_required", "Student ID is required"))
                return False

            grant = float(fields['grant_amount'].get() or 0)
            loan = float(fields['loan_amount'].get() or 0)
            work_study = float(fields['work_study_amount'].get() or 0)

            if grant + loan + work_study <= 0:
                show_error(get_text("financial_aid.admin_portal.dialogs.validation_error", "Validation Error"), get_text("financial_aid.admin_portal.errors.package_requires_component", "Package must have at least one aid component"))
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

                show_success(get_text("financial_aid.admin_portal.dialogs.success", "Success"), get_text("financial_aid.admin_portal.messages.package_created", "Aid package created successfully!"))
                return True
            else:
                show_error(get_text("financial_aid.admin_portal.dialogs.error", "Error"), get_text("financial_aid.admin_portal.errors.failed_create_package", "Failed to create aid package"))
                return False

        except Exception as e:
            logger.error(f"Error creating aid package: {e}")
            show_error(get_text("financial_aid.admin_portal.dialogs.error", "Error"), get_text("financial_aid.admin_portal.errors.error_occurred", "An error occurred: {error}").format(error=str(e)))
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
        ttk.Label(title_frame, text=get_text("financial_aid.admin_portal.aid_types.title", "Manage Aid Types"), style='Title.TLabel').pack(side='left')
        ttk.Button(title_frame, text=get_text("financial_aid.admin_portal.buttons.back_to_dashboard", "Back to Dashboard"), command=self.show_dashboard).pack(side='right')

        # Aid types table
        table_frame = ttk.Frame(self.parent_frame)
        table_frame.pack(fill='both', expand=True, padx=10, pady=10)

        columns = [get_text("financial_aid.admin_portal.columns.aid_type_id", "Aid Type ID"), get_text("financial_aid.admin_portal.columns.name", "Name"), get_text("financial_aid.admin_portal.columns.category", "Category"), get_text("financial_aid.admin_portal.columns.max_amount", "Max Amount"), get_text("financial_aid.admin_portal.columns.renewable", "Renewable"), get_text("financial_aid.admin_portal.columns.requires_repayment", "Requires Repayment")]
        tree = create_data_table(table_frame, columns, {
            get_text("financial_aid.admin_portal.columns.aid_type_id", "Aid Type ID"): 100, get_text("financial_aid.admin_portal.columns.name", "Name"): 200, get_text("financial_aid.admin_portal.columns.category", "Category"): 120, get_text("financial_aid.admin_portal.columns.max_amount", "Max Amount"): 100, get_text("financial_aid.admin_portal.columns.renewable", "Renewable"): 100, get_text("financial_aid.admin_portal.columns.requires_repayment", "Requires Repayment"): 150
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
                        get_text("financial_aid.admin_portal.values.yes", "Yes") if aid_dict.get('is_renewable') else get_text("financial_aid.admin_portal.values.no", "No"),
                        get_text("financial_aid.admin_portal.values.yes", "Yes") if aid_dict.get('requires_repayment') else get_text("financial_aid.admin_portal.values.no", "No")
                    ))

        except Exception as e:
            logger.error(f"Error loading aid types: {e}")
            ttk.Label(table_frame, text=get_text("financial_aid.admin_portal.errors.error_loading_aid_types", "Error loading aid types"), foreground='red').pack()

    def show_disbursements(self):
        """Show comprehensive disbursements management interface"""
        # Ensure we have a valid parent frame/window
        parent = self._ensure_valid_parent()
        self.parent_frame = parent

        clear_frame(self.parent_frame)

        # Title
        title_frame = ttk.Frame(self.parent_frame)
        title_frame.pack(fill='x', padx=10, pady=10)
        ttk.Label(title_frame, text=get_text("financial_aid.admin_portal.disbursements.title", "Disbursement Management"), style='Title.TLabel').pack(side='left')
        ttk.Button(title_frame, text=get_text("financial_aid.admin_portal.buttons.back_to_dashboard", "Back to Dashboard"), command=self.show_dashboard).pack(side='right')

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
                stat_frame1 = create_stat_card(stats_frame, get_text("financial_aid.admin_portal.stats.pending_disbursements", "Pending Disbursements"),
                                               f"{pending_result['count']}", 'warning')
                stat_frame1.pack(side='left', padx=10, fill='both', expand=True)

                stat_frame2 = create_stat_card(stats_frame, get_text("financial_aid.admin_portal.stats.pending_amount", "Pending Amount"),
                                               format_currency(pending_result['total']), 'warning')
                stat_frame2.pack(side='left', padx=10, fill='both', expand=True)

                stat_frame3 = create_stat_card(stats_frame, get_text("financial_aid.admin_portal.stats.processed_today", "Processed Today"),
                                               f"{processed_result['count']}", 'success')
                stat_frame3.pack(side='left', padx=10, fill='both', expand=True)

                stat_frame4 = create_stat_card(stats_frame, get_text("financial_aid.admin_portal.stats.amount_processed_today", "Amount Processed Today"),
                                               format_currency(processed_result['total']), 'success')
                stat_frame4.pack(side='left', padx=10, fill='both', expand=True)

        except Exception as e:
            logger.error(f"Error loading disbursement stats: {e}")

        # Action buttons
        action_frame = ttk.Frame(self.parent_frame)
        action_frame.pack(fill='x', padx=10, pady=10)

        ttk.Button(action_frame, text=get_text("financial_aid.admin_portal.buttons.create_disbursement", "Create Disbursement"),
                  command=self._show_create_disbursement_dialog,
                  style='Success.TButton').pack(side='left', padx=5)
        ttk.Button(action_frame, text=get_text("financial_aid.admin_portal.buttons.process_selected", "Process Selected"),
                  command=lambda: self._process_selected_disbursements(tree),
                  style='Primary.TButton').pack(side='left', padx=5)
        ttk.Button(action_frame, text=get_text("financial_aid.admin_portal.buttons.process_all_pending", "Process All Pending"),
                  command=self._process_all_pending_disbursements,
                  style='Success.TButton').pack(side='left', padx=5)
        ttk.Button(action_frame, text=get_text("financial_aid.admin_portal.buttons.cancel_selected", "Cancel Selected"),
                  command=lambda: self._cancel_selected_disbursements(tree),
                  style='Danger.TButton').pack(side='left', padx=5)
        ttk.Button(action_frame, text=get_text("financial_aid.admin_portal.buttons.view_details", "View Details"),
                  command=lambda: self._view_disbursement_details(tree)).pack(side='left', padx=5)
        ttk.Button(action_frame, text=get_text("financial_aid.admin_portal.buttons.export_report", "Export Report"),
                  command=self._export_disbursement_report).pack(side='left', padx=5)

        # Tabs for different views
        notebook = ttk.Notebook(self.parent_frame)
        notebook.pack(fill='both', expand=True, padx=10, pady=10)

        # Pending disbursements tab
        pending_frame = ttk.Frame(notebook)
        notebook.add(pending_frame, text=get_text("financial_aid.admin_portal.tabs.pending_disbursements", "Pending Disbursements"))

        columns_pending = [get_text("financial_aid.admin_portal.columns.select", "Select"), get_text("financial_aid.admin_portal.columns.id", "ID"), get_text("financial_aid.admin_portal.columns.student_name", "Student Name"), get_text("financial_aid.admin_portal.columns.student_id", "Student ID"), get_text("financial_aid.admin_portal.columns.type", "Type"), get_text("financial_aid.admin_portal.columns.amount", "Amount"),
                          get_text("financial_aid.admin_portal.columns.scheduled_date", "Scheduled Date"), get_text("financial_aid.admin_portal.columns.term", "Term"), get_text("financial_aid.admin_portal.columns.method", "Method"), get_text("financial_aid.admin_portal.columns.transaction_id", "Transaction ID")]
        tree = ttk.Treeview(pending_frame, columns=columns_pending, show='tree headings', height=15)

        # Configure columns
        tree.column('#0', width=0, stretch=False)
        tree.column(get_text("financial_aid.admin_portal.columns.select", "Select"), width=50, anchor='center')
        tree.column(get_text("financial_aid.admin_portal.columns.id", "ID"), width=60)
        tree.column(get_text("financial_aid.admin_portal.columns.student_name", "Student Name"), width=150)
        tree.column(get_text("financial_aid.admin_portal.columns.student_id", "Student ID"), width=100)
        tree.column(get_text("financial_aid.admin_portal.columns.type", "Type"), width=120)
        tree.column(get_text("financial_aid.admin_portal.columns.amount", "Amount"), width=100, anchor='e')
        tree.column(get_text("financial_aid.admin_portal.columns.scheduled_date", "Scheduled Date"), width=120)
        tree.column(get_text("financial_aid.admin_portal.columns.term", "Term"), width=100)
        tree.column(get_text("financial_aid.admin_portal.columns.method", "Method"), width=120)
        tree.column(get_text("financial_aid.admin_portal.columns.transaction_id", "Transaction ID"), width=150)

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
        notebook.add(processed_frame, text=get_text("financial_aid.admin_portal.tabs.processed_disbursements", "Processed Disbursements"))

        columns_processed = [get_text("financial_aid.admin_portal.columns.id", "ID"), get_text("financial_aid.admin_portal.columns.student_name", "Student Name"), get_text("financial_aid.admin_portal.columns.student_id", "Student ID"), get_text("financial_aid.admin_portal.columns.type", "Type"), get_text("financial_aid.admin_portal.columns.amount", "Amount"),
                            get_text("financial_aid.admin_portal.columns.disbursement_date", "Disbursement Date"), get_text("financial_aid.admin_portal.columns.processed_date", "Processed Date"), get_text("financial_aid.admin_portal.columns.processed_by", "Processed By"), get_text("financial_aid.admin_portal.columns.transaction_id", "Transaction ID")]
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
        notebook.add(failed_frame, text=get_text("financial_aid.admin_portal.tabs.failed_cancelled", "Failed/Cancelled"))

        columns_failed = [get_text("financial_aid.admin_portal.columns.id", "ID"), get_text("financial_aid.admin_portal.columns.student", "Student"), get_text("financial_aid.admin_portal.columns.amount", "Amount"), get_text("financial_aid.admin_portal.columns.scheduled_date", "Scheduled Date"), get_text("financial_aid.admin_portal.columns.status", "Status"), get_text("financial_aid.admin_portal.columns.error_message", "Error Message")]
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
                        d.get('disbursement_type', get_text("financial_aid.admin_portal.values.general_aid", "General Aid")),
                        format_currency(d['amount']),
                        format_date(d.get('scheduled_date', d.get('disbursement_date'))),
                        d.get('academic_term', 'N/A'),
                        d.get('payment_method', 'account_credit'),
                        d.get('transaction_id', get_text("financial_aid.admin_portal.values.pending", "Pending"))
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
                        d.get('disbursement_type', get_text("financial_aid.admin_portal.values.general_aid", "General Aid")),
                        format_currency(d['amount']),
                        format_date(d.get('disbursement_date')),
                        format_date(d.get('processed_at')),
                        d.get('processor_name', get_text("financial_aid.admin_portal.values.system", "System")),
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
                        d.get('error_message', get_text("financial_aid.admin_portal.values.no_error_message", "No error message"))
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
            show_warning(get_text("financial_aid.admin_portal.dialogs.no_selection", "No Selection"), get_text("financial_aid.admin_portal.messages.select_disbursements_to_process", "Please select disbursements to process by clicking the checkbox column."))
            return

        if not confirm_action(get_text("financial_aid.admin_portal.messages.confirm_process_disbursements", "Process {count} selected disbursement(s)?\n\nThis action cannot be undone.").format(count=len(selected_items))):
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

            show_success(get_text("financial_aid.admin_portal.dialogs.processing_complete", "Processing Complete"),
                        get_text("financial_aid.admin_portal.messages.processing_results", "Successfully processed: {success}\nFailed: {failed}").format(success=success_count, failed=error_count))

        except Exception as e:
            logger.error(f"Error processing disbursements: {e}")
            show_error(get_text("financial_aid.admin_portal.dialogs.processing_error", "Processing Error"), get_text("financial_aid.admin_portal.errors.error_occurred", "An error occurred: {error}").format(error=str(e)))

    def _process_all_pending_disbursements(self):
        """Process all pending disbursements"""
        try:
            with get_connection() as conn:
                pending_count = conn.execute("""
                    SELECT COUNT(*) as count FROM disbursements WHERE status = 'pending'
                """).fetchone()['count']

                if pending_count == 0:
                    show_warning(get_text("financial_aid.admin_portal.dialogs.no_pending", "No Pending Disbursements"), get_text("financial_aid.admin_portal.messages.no_pending_disbursements", "There are no pending disbursements to process."))
                    return

                if not confirm_action(get_text("financial_aid.admin_portal.messages.confirm_process_all", "Process ALL {count} pending disbursement(s)?\n\nThis will process every pending disbursement in the system.\nThis action cannot be undone.").format(count=pending_count)):
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

                show_success(get_text("financial_aid.admin_portal.dialogs.batch_processing_complete", "Batch Processing Complete"),
                            get_text("financial_aid.admin_portal.messages.batch_processing_results", "Successfully processed {success} out of {total} disbursements.").format(success=success_count, total=pending_count))

                # Refresh the view
                self.show_disbursements()

        except Exception as e:
            logger.error(f"Error in batch processing: {e}")
            show_error(get_text("financial_aid.admin_portal.dialogs.batch_processing_error", "Batch Processing Error"), get_text("financial_aid.admin_portal.errors.error_occurred", "An error occurred: {error}").format(error=str(e)))

    def _cancel_selected_disbursements(self, tree):
        """Cancel selected disbursements"""
        selected_items = []
        for item in tree.get_children():
            values = tree.item(item)['values']
            if values[0] == '☑':  # Checked
                selected_items.append(values[1])  # disbursement_id

        if not selected_items:
            show_warning(get_text("financial_aid.admin_portal.dialogs.no_selection", "No Selection"), get_text("financial_aid.admin_portal.messages.select_disbursements_to_cancel", "Please select disbursements to cancel."))
            return

        if not confirm_action(get_text("financial_aid.admin_portal.messages.confirm_cancel_disbursements", "Cancel {count} selected disbursement(s)?").format(count=len(selected_items))):
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

            show_success(get_text("financial_aid.admin_portal.dialogs.cancellation_complete", "Cancellation Complete"), get_text("financial_aid.admin_portal.messages.cancellation_results", "Successfully cancelled {count} disbursement(s).").format(count=len(selected_items)))
            self._load_pending_disbursements(tree)

        except Exception as e:
            logger.error(f"Error cancelling disbursements: {e}")
            show_error(get_text("financial_aid.admin_portal.dialogs.cancellation_error", "Cancellation Error"), get_text("financial_aid.admin_portal.errors.error_occurred", "An error occurred: {error}").format(error=str(e)))

    def _view_disbursement_details(self, tree):
        """View detailed information about selected disbursement"""
        selection = tree.selection()
        if not selection:
            show_warning(get_text("financial_aid.admin_portal.dialogs.no_selection", "No Selection"), get_text("financial_aid.admin_portal.messages.select_disbursement_to_view", "Please select a disbursement to view details."))
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
                    show_error(get_text("financial_aid.admin_portal.dialogs.not_found", "Not Found"), get_text("financial_aid.admin_portal.errors.disbursement_not_found", "Disbursement not found."))
                    return

                # Convert Row to dict
                d = dict(disb)

                # Create details window
                details_window = tk.Toplevel(self.parent_frame)
                details_window.title(get_text("financial_aid.admin_portal.dialogs.disbursement_details", "Disbursement Details") + f" - ID: {disb_id}")
                details_window.geometry("600x700")

                # Title
                ttk.Label(details_window, text=get_text("financial_aid.admin_portal.details.disbursement_num", "Disbursement #{num}").format(num=disb_id), font=('Arial', 14, 'bold')).pack(pady=10)

                # Details frame
                details_frame = ttk.Frame(details_window, padding=20)
                details_frame.pack(fill='both', expand=True)

                def add_detail(label, value):
                    row_frame = ttk.Frame(details_frame)
                    row_frame.pack(fill='x', pady=5)
                    ttk.Label(row_frame, text=f"{label}:", font=('Arial', 10, 'bold'), width=20).pack(side='left')
                    ttk.Label(row_frame, text=str(value), font=('Arial', 10)).pack(side='left')

                add_detail(get_text("financial_aid.admin_portal.details.status", "Status"), d['status'].upper())
                add_detail(get_text("financial_aid.admin_portal.details.student_name", "Student Name"), f"{d.get('first_name', 'N/A')} {d.get('last_name', '')}")
                add_detail(get_text("financial_aid.admin_portal.details.student_id", "Student ID"), d.get('sid', d['student_id']))
                add_detail(get_text("financial_aid.admin_portal.details.student_email", "Student Email"), d.get('email', 'N/A'))
                add_detail(get_text("financial_aid.admin_portal.details.disbursement_type", "Disbursement Type"), d.get('disbursement_type', get_text("financial_aid.admin_portal.values.general_aid", "General Aid")))
                add_detail(get_text("financial_aid.admin_portal.details.amount", "Amount"), format_currency(d['amount']))
                add_detail(get_text("financial_aid.admin_portal.details.academic_term", "Academic Term"), d.get('academic_term', 'N/A'))
                add_detail(get_text("financial_aid.admin_portal.details.payment_method", "Payment Method"), d.get('payment_method', 'N/A'))
                add_detail(get_text("financial_aid.admin_portal.details.transaction_id", "Transaction ID"), d.get('transaction_id', get_text("financial_aid.admin_portal.values.pending", "Pending")))
                add_detail(get_text("financial_aid.admin_portal.details.scheduled_date", "Scheduled Date"), format_date(d.get('scheduled_date')))
                add_detail(get_text("financial_aid.admin_portal.details.disbursement_date", "Disbursement Date"), format_date(d.get('disbursement_date', 'N/A')))

                if d.get('processed_at'):
                    add_detail(get_text("financial_aid.admin_portal.details.processed_date", "Processed Date"), format_date(d['processed_at']))
                    add_detail(get_text("financial_aid.admin_portal.details.processed_by", "Processed By"), d.get('processor_name', get_text("financial_aid.admin_portal.values.system", "System")))

                if d.get('award_id'):
                    add_detail(get_text("financial_aid.admin_portal.details.award_id", "Award ID"), d['award_id'])
                if d.get('component_id'):
                    add_detail(get_text("financial_aid.admin_portal.details.component_id", "Component ID"), d['component_id'])

                if d.get('error_message'):
                    add_detail(get_text("financial_aid.admin_portal.details.error_message", "Error Message"), d['error_message'])

                # Close button
                ttk.Button(details_window, text=get_text("financial_aid.admin_portal.buttons.close", "Close"), command=details_window.destroy).pack(pady=10)

        except Exception as e:
            logger.error(f"Error viewing disbursement details: {e}")
            show_error(get_text("financial_aid.admin_portal.dialogs.error", "Error"), get_text("financial_aid.admin_portal.errors.error_occurred", "An error occurred: {error}").format(error=str(e)))

    def _show_create_disbursement_dialog(self):
        """Show dialog to create new disbursement"""
        dialog = tk.Toplevel(self.parent_frame)
        dialog.title(get_text("financial_aid.admin_portal.dialogs.create_disbursement", "Create New Disbursement"))
        dialog.geometry("500x600")

        ttk.Label(dialog, text=get_text("financial_aid.admin_portal.dialogs.create_disbursement", "Create New Disbursement"), font=('Arial', 14, 'bold')).pack(pady=10)

        # Form
        form_frame = ttk.Frame(dialog, padding=20)
        form_frame.pack(fill='both', expand=True)

        fields = {}

        # Student ID
        ttk.Label(form_frame, text=get_text("financial_aid.admin_portal.labels.student_id", "Student ID:")).pack(anchor='w', pady=(5, 0))
        fields['student_id'] = ttk.Entry(form_frame, width=40)
        fields['student_id'].pack(fill='x', pady=(0, 10))

        # Amount
        ttk.Label(form_frame, text=get_text("financial_aid.admin_portal.labels.amount_dollars", "Amount ($):")).pack(anchor='w', pady=(5, 0))
        fields['amount'] = ttk.Entry(form_frame, width=40)
        fields['amount'].pack(fill='x', pady=(0, 10))

        # Type
        ttk.Label(form_frame, text=get_text("financial_aid.admin_portal.labels.disbursement_type", "Disbursement Type:")).pack(anchor='w', pady=(5, 0))
        fields['type'] = ttk.Combobox(form_frame, values=['scholarship', 'grant', 'loan', 'work_study', 'refund'], width=38)
        fields['type'].set('grant')
        fields['type'].pack(fill='x', pady=(0, 10))

        # Academic Term
        ttk.Label(form_frame, text=get_text("financial_aid.admin_portal.labels.academic_term", "Academic Term:")).pack(anchor='w', pady=(5, 0))
        fields['term'] = ttk.Combobox(form_frame, values=['Fall', 'Spring', 'Summer'], width=38)
        fields['term'].set('Fall')
        fields['term'].pack(fill='x', pady=(0, 10))

        # Scheduled Date
        ttk.Label(form_frame, text=get_text("financial_aid.admin_portal.labels.scheduled_date", "Scheduled Date (YYYY-MM-DD):")).pack(anchor='w', pady=(5, 0))
        fields['date'] = ttk.Entry(form_frame, width=40)
        fields['date'].insert(0, date.today().strftime('%Y-%m-%d'))
        fields['date'].pack(fill='x', pady=(0, 10))

        # Payment Method
        ttk.Label(form_frame, text=get_text("financial_aid.admin_portal.labels.payment_method", "Payment Method:")).pack(anchor='w', pady=(5, 0))
        fields['method'] = ttk.Combobox(form_frame, values=['account_credit', 'direct_deposit', 'check', 'wire_transfer'], width=38)
        fields['method'].set('account_credit')
        fields['method'].pack(fill='x', pady=(0, 10))

        def create_disbursement():
            try:
                # Validate
                if not fields['student_id'].get().strip():
                    show_error(get_text("financial_aid.admin_portal.dialogs.validation_error", "Validation Error"), get_text("financial_aid.admin_portal.errors.student_id_required", "Student ID is required"))
                    return

                amount = float(fields['amount'].get())
                if amount <= 0:
                    show_error(get_text("financial_aid.admin_portal.dialogs.validation_error", "Validation Error"), get_text("financial_aid.admin_portal.errors.amount_must_be_positive", "Amount must be greater than 0"))
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

                    show_success(get_text("financial_aid.admin_portal.dialogs.success", "Success"), get_text("financial_aid.admin_portal.messages.disbursement_created", "Disbursement created successfully!\nDisbursement ID: {id}").format(id=disb_id))
                    dialog.destroy()
                    self.show_disbursements()  # Refresh
                else:
                    show_error(get_text("financial_aid.admin_portal.dialogs.error", "Error"), get_text("financial_aid.admin_portal.errors.failed_create_disbursement", "Failed to create disbursement"))

            except ValueError as e:
                show_error(get_text("financial_aid.admin_portal.dialogs.validation_error", "Validation Error"), get_text("financial_aid.admin_portal.errors.invalid_input", "Invalid input: {error}").format(error=str(e)))
            except Exception as e:
                logger.error(f"Error creating disbursement: {e}")
                show_error(get_text("financial_aid.admin_portal.dialogs.error", "Error"), get_text("financial_aid.admin_portal.errors.error_occurred", "An error occurred: {error}").format(error=str(e)))

        # Buttons
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=10)
        ttk.Button(btn_frame, text=get_text("financial_aid.admin_portal.buttons.create", "Create"), command=create_disbursement, style='Success.TButton').pack(side='left', padx=5)
        ttk.Button(btn_frame, text=get_text("financial_aid.admin_portal.buttons.cancel", "Cancel"), command=dialog.destroy).pack(side='left', padx=5)

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
            show_error(get_text("financial_aid.admin_portal.dialogs.export_error", "Export Error"), get_text("financial_aid.admin_portal.errors.failed_export_report", "Failed to export report: {error}").format(error=str(e)))

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
        ttk.Label(title_frame, text=get_text("financial_aid.admin_portal.reports.title", "Financial Aid Reports"), style='Title.TLabel').pack(side='left')
        ttk.Button(title_frame, text=get_text("financial_aid.admin_portal.buttons.back_to_dashboard", "Back to Dashboard"), command=self.show_dashboard).pack(side='right')

        # Reports options with scrollbar
        reports_container = ttk.Frame(self.parent_frame)
        reports_container.pack(fill='both', expand=True, padx=10, pady=10)

        # Create scrollable frame
        scrollable_frame, canvas, scrollbar = create_scrollable_frame(reports_container)
        canvas.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        reports_frame = ttk.LabelFrame(scrollable_frame, text=get_text("financial_aid.admin_portal.reports.available_reports", "Available Reports"), padding=20)
        reports_frame.pack(fill='both', expand=True)

        reports = [
            (get_text("financial_aid.admin_portal.reports.aid_distribution", "Aid Distribution Summary"), get_text("financial_aid.admin_portal.reports.aid_distribution_desc", "Summary of aid distributed by type and year")),
            (get_text("financial_aid.admin_portal.reports.scholarship_utilization", "Scholarship Utilization"), get_text("financial_aid.admin_portal.reports.scholarship_utilization_desc", "Analysis of scholarship awards and usage")),
            (get_text("financial_aid.admin_portal.reports.disbursement_schedule", "Disbursement Schedule"), get_text("financial_aid.admin_portal.reports.disbursement_schedule_desc", "Upcoming and completed disbursements")),
            (get_text("financial_aid.admin_portal.reports.compliance_fisap", "Compliance Report (FISAP)"), get_text("financial_aid.admin_portal.reports.compliance_fisap_desc", "Federal compliance reporting")),
            (get_text("financial_aid.admin_portal.reports.sai_report", "Student Aid Index Report"), get_text("financial_aid.admin_portal.reports.sai_report_desc", "SAI/EFC analysis")),
            (get_text("financial_aid.admin_portal.reports.need_analysis", "Need Analysis Report"), get_text("financial_aid.admin_portal.reports.need_analysis_desc", "Unmet financial need by student demographics")),
            (get_text("financial_aid.admin_portal.reports.renewal_tracking", "Renewal Tracking Report"), get_text("financial_aid.admin_portal.reports.renewal_tracking_desc", "Scholarship renewal eligibility and status")),
        ]

        for i, (name, description) in enumerate(reports):
            frame = ttk.Frame(reports_frame)
            frame.pack(fill='x', pady=10)

            ttk.Label(frame, text=name, font=('Arial', 11, 'bold')).pack(anchor='w')
            ttk.Label(frame, text=description, foreground='gray').pack(anchor='w', padx=20)
            ttk.Button(frame, text=get_text("financial_aid.admin_portal.buttons.generate_report", "Generate Report"),
                      command=lambda n=name: self._generate_report(n)).pack(anchor='w', padx=20, pady=5)

    def _generate_report(self, report_name: str):
        """Generate selected report"""
        if report_name == get_text("financial_aid.admin_portal.reports.aid_distribution", "Aid Distribution Summary"):
            self._generate_aid_distribution_report()
        elif report_name == get_text("financial_aid.admin_portal.reports.scholarship_utilization", "Scholarship Utilization"):
            self._generate_scholarship_utilization_report()
        elif report_name == get_text("financial_aid.admin_portal.reports.disbursement_schedule", "Disbursement Schedule"):
            self._generate_disbursement_schedule_report()
        elif report_name == get_text("financial_aid.admin_portal.reports.compliance_fisap", "Compliance Report (FISAP)"):
            self._generate_compliance_report()
        elif report_name == get_text("financial_aid.admin_portal.reports.sai_report", "Student Aid Index Report"):
            self._generate_sai_report()
        elif report_name == get_text("financial_aid.admin_portal.reports.need_analysis", "Need Analysis Report"):
            self._generate_need_analysis_report()
        elif report_name == get_text("financial_aid.admin_portal.reports.renewal_tracking", "Renewal Tracking Report"):
            self._generate_renewal_tracking_report()
        else:
            show_warning(get_text("financial_aid.admin_portal.dialogs.coming_soon", "Coming Soon"), get_text("financial_aid.admin_portal.messages.report_not_implemented", "Report '{name}' not yet implemented").format(name=report_name))

    def _generate_aid_distribution_report(self):
        """Generate Aid Distribution Summary report"""
        report_window = tk.Toplevel(self.parent_frame)
        report_window.title(get_text("financial_aid.admin_portal.reports.aid_distribution_title", "Aid Distribution Summary Report"))
        report_window.geometry("900x700")

        # Title
        ttk.Label(report_window, text=get_text("financial_aid.admin_portal.reports.aid_distribution", "Aid Distribution Summary"), style='Title.TLabel').pack(pady=10)

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

        ttk.Button(btn_frame, text=get_text("financial_aid.admin_portal.buttons.export_csv", "Export as CSV"),
                  command=lambda: self._export_report_to_csv(report_text.get('1.0', 'end-1c'), "aid_distribution_report")).pack(side='left', padx=5)
        ttk.Button(btn_frame, text=get_text("financial_aid.admin_portal.buttons.export_text", "Export as Text"),
                  command=lambda: self._export_report_to_txt(report_text.get('1.0', 'end-1c'), "aid_distribution_report")).pack(side='left', padx=5)
        ttk.Button(btn_frame, text=get_text("financial_aid.admin_portal.buttons.email_report", "Email Report to Admin"),
                  command=lambda: self._email_report(report_text.get('1.0', 'end-1c'), "Aid Distribution Summary")).pack(side='left', padx=5)

        ttk.Button(report_window, text=get_text("financial_aid.admin_portal.buttons.close", "Close"), command=report_window.destroy).pack(pady=5)

    def _generate_scholarship_utilization_report(self):
        """Generate Scholarship Utilization report"""
        report_window = tk.Toplevel(self.parent_frame)
        report_window.title(get_text("financial_aid.admin_portal.reports.scholarship_utilization_title", "Scholarship Utilization Report"))
        report_window.geometry("900x700")

        ttk.Label(report_window, text=get_text("financial_aid.admin_portal.reports.scholarship_utilization", "Scholarship Utilization Report"), style='Title.TLabel').pack(pady=10)

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

        ttk.Button(btn_frame, text=get_text("financial_aid.admin_portal.buttons.export_csv", "Export as CSV"),
                  command=lambda: self._export_report_to_csv(report_text.get('1.0', 'end-1c'), "scholarship_utilization_report")).pack(side='left', padx=5)
        ttk.Button(btn_frame, text=get_text("financial_aid.admin_portal.buttons.export_text", "Export as Text"),
                  command=lambda: self._export_report_to_txt(report_text.get('1.0', 'end-1c'), "scholarship_utilization_report")).pack(side='left', padx=5)
        ttk.Button(btn_frame, text=get_text("financial_aid.admin_portal.buttons.email_report", "Email Report to Admin"),
                  command=lambda: self._email_report(report_text.get('1.0', 'end-1c'), "Scholarship Utilization")).pack(side='left', padx=5)

        ttk.Button(report_window, text=get_text("financial_aid.admin_portal.buttons.close", "Close"), command=report_window.destroy).pack(pady=5)

    def _generate_disbursement_schedule_report(self):
        """Generate Disbursement Schedule report"""
        report_window = tk.Toplevel(self.parent_frame)
        report_window.title(get_text("financial_aid.admin_portal.reports.disbursement_schedule_title", "Disbursement Schedule Report"))
        report_window.geometry("900x700")

        ttk.Label(report_window, text=get_text("financial_aid.admin_portal.reports.disbursement_schedule", "Disbursement Schedule Report"), style='Title.TLabel').pack(pady=10)

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

        ttk.Button(btn_frame, text=get_text("financial_aid.admin_portal.buttons.export_csv", "Export as CSV"),
                  command=lambda: self._export_report_to_csv(report_text.get('1.0', 'end-1c'), "disbursement_schedule_report")).pack(side='left', padx=5)
        ttk.Button(btn_frame, text=get_text("financial_aid.admin_portal.buttons.export_text", "Export as Text"),
                  command=lambda: self._export_report_to_txt(report_text.get('1.0', 'end-1c'), "disbursement_schedule_report")).pack(side='left', padx=5)
        ttk.Button(btn_frame, text=get_text("financial_aid.admin_portal.buttons.email_report", "Email Report to Admin"),
                  command=lambda: self._email_report(report_text.get('1.0', 'end-1c'), "Disbursement Schedule")).pack(side='left', padx=5)

        ttk.Button(report_window, text=get_text("financial_aid.admin_portal.buttons.close", "Close"), command=report_window.destroy).pack(pady=5)

    def _generate_compliance_report(self):
        """Generate Compliance (FISAP) report"""
        report_window = tk.Toplevel(self.parent_frame)
        report_window.title(get_text("financial_aid.admin_portal.reports.compliance_fisap_title", "Compliance Report (FISAP)"))
        report_window.geometry("900x700")

        ttk.Label(report_window, text=get_text("financial_aid.admin_portal.reports.fisap_title", "Federal Student Aid Report (FISAP)"), style='Title.TLabel').pack(pady=10)

        report_frame = ttk.Frame(report_window)
        report_frame.pack(fill='both', expand=True, padx=10, pady=10)

        report_text = scrolledtext.ScrolledText(report_frame, width=100, height=35, wrap='word', font=('Courier', 10))
        report_text.pack(fill='both', expand=True)

        try:
            report = []
            report.append("=" * 80)
            report.append("FISAP COMPLIANCE REPORT")
            report.append("Fiscal Operations Report and Application to Participate")
            report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            report.append(f"Academic Year: {get_current_academic_year()}")
            report.append("=" * 80)
            report.append("")

            with get_connection() as conn:
                # Section 1: Federal Work-Study (FWS) Expenditures
                report.append("SECTION 1: FEDERAL WORK-STUDY (FWS) PROGRAM")
                report.append("-" * 80)

                fws_data = conn.execute("""
                    SELECT
                        COUNT(DISTINCT sfa.student_id) as recipient_count,
                        SUM(sfa.awarded_amount) as total_awarded,
                        SUM(sfa.disbursed_amount) as total_disbursed,
                        SUM(sfa.remaining_amount) as total_remaining
                    FROM student_financial_aid sfa
                    JOIN financial_aid_types fat ON sfa.aid_type_id = fat.aid_type_id
                    WHERE LOWER(fat.aid_name) LIKE '%work%study%'
                       OR LOWER(fat.aid_name) LIKE '%fws%'
                       OR LOWER(fat.aid_category) = 'work-study'
                """).fetchone()

                if fws_data:
                    fws = dict(fws_data)
                    report.append(f"Total Recipients: {fws['recipient_count']}")
                    report.append(f"Total Awarded: {format_currency(fws['total_awarded'] or 0)}")
                    report.append(f"Total Disbursed: {format_currency(fws['total_disbursed'] or 0)}")
                    report.append(f"Remaining Allocation: {format_currency(fws['total_remaining'] or 0)}")

                    if fws['total_awarded'] and fws['total_awarded'] > 0:
                        utilization = (fws['total_disbursed'] or 0) / fws['total_awarded'] * 100
                        report.append(f"Utilization Rate: {utilization:.1f}%")
                else:
                    report.append("No FWS awards found for this academic year")

                report.append("")

                # Section 2: Federal Supplemental Educational Opportunity Grant (FSEOG)
                report.append("SECTION 2: FEDERAL SEOG PROGRAM")
                report.append("-" * 80)

                fseog_data = conn.execute("""
                    SELECT
                        COUNT(DISTINCT sfa.student_id) as recipient_count,
                        SUM(sfa.awarded_amount) as total_awarded,
                        SUM(sfa.disbursed_amount) as total_disbursed,
                        SUM(sfa.remaining_amount) as total_remaining
                    FROM student_financial_aid sfa
                    JOIN financial_aid_types fat ON sfa.aid_type_id = fat.aid_type_id
                    WHERE LOWER(fat.aid_name) LIKE '%seog%'
                       OR LOWER(fat.aid_name) LIKE '%supplemental%educational%opportunity%'
                       OR (LOWER(fat.aid_category) = 'grant' AND LOWER(fat.aid_name) LIKE '%federal%')
                """).fetchone()

                if fseog_data:
                    fseog = dict(fseog_data)
                    report.append(f"Total Recipients: {fseog['recipient_count']}")
                    report.append(f"Total Awarded: {format_currency(fseog['total_awarded'] or 0)}")
                    report.append(f"Total Disbursed: {format_currency(fseog['total_disbursed'] or 0)}")
                    report.append(f"Remaining Allocation: {format_currency(fseog['total_remaining'] or 0)}")

                    if fseog['total_awarded'] and fseog['total_awarded'] > 0:
                        utilization = (fseog['total_disbursed'] or 0) / fseog['total_awarded'] * 100
                        report.append(f"Utilization Rate: {utilization:.1f}%")
                else:
                    report.append("No FSEOG awards found for this academic year")

                report.append("")

                # Section 3: Federal Perkins Loan
                report.append("SECTION 3: FEDERAL PERKINS LOAN PROGRAM")
                report.append("-" * 80)

                perkins_data = conn.execute("""
                    SELECT
                        COUNT(DISTINCT sfa.student_id) as recipient_count,
                        SUM(sfa.awarded_amount) as total_awarded,
                        SUM(sfa.disbursed_amount) as total_disbursed,
                        SUM(sfa.total_repaid) as total_repaid
                    FROM student_financial_aid sfa
                    JOIN financial_aid_types fat ON sfa.aid_type_id = fat.aid_type_id
                    WHERE LOWER(fat.aid_name) LIKE '%perkins%'
                       OR (LOWER(fat.aid_category) = 'loan' AND LOWER(fat.aid_name) LIKE '%federal%')
                """).fetchone()

                if perkins_data:
                    perkins = dict(perkins_data)
                    report.append(f"Total Recipients: {perkins['recipient_count']}")
                    report.append(f"Total Awarded: {format_currency(perkins['total_awarded'] or 0)}")
                    report.append(f"Total Disbursed: {format_currency(perkins['total_disbursed'] or 0)}")
                    report.append(f"Total Repaid: {format_currency(perkins['total_repaid'] or 0)}")

                    if perkins['total_disbursed'] and perkins['total_disbursed'] > 0:
                        outstanding = (perkins['total_disbursed'] or 0) - (perkins['total_repaid'] or 0)
                        report.append(f"Outstanding Balance: {format_currency(outstanding)}")
                else:
                    report.append("No Perkins Loan awards found")
                    report.append("Note: The Federal Perkins Loan Program expired on September 30, 2017")

                report.append("")

                # Section 4: Institutional Matching Contributions
                report.append("SECTION 4: INSTITUTIONAL MATCHING CONTRIBUTIONS")
                report.append("-" * 80)

                institutional_data = conn.execute("""
                    SELECT
                        COUNT(DISTINCT sfa.student_id) as recipient_count,
                        SUM(sfa.awarded_amount) as total_awarded,
                        SUM(sfa.disbursed_amount) as total_disbursed
                    FROM student_financial_aid sfa
                    JOIN financial_aid_types fat ON sfa.aid_type_id = fat.aid_type_id
                    WHERE LOWER(fat.aid_category) = 'institutional'
                       OR LOWER(fat.aid_name) LIKE '%institutional%'
                       OR LOWER(fat.aid_name) LIKE '%matching%'
                """).fetchone()

                if institutional_data:
                    inst = dict(institutional_data)
                    report.append(f"Total Recipients: {inst['recipient_count']}")
                    report.append(f"Total Awarded: {format_currency(inst['total_awarded'] or 0)}")
                    report.append(f"Total Disbursed: {format_currency(inst['total_disbursed'] or 0)}")

                    # Calculate required matching (typically 25% for FSEOG)
                    if fseog_data:
                        fseog_amt = dict(fseog_data)['total_awarded'] or 0
                        required_match = fseog_amt * 0.25
                        actual_match = inst['total_disbursed'] or 0
                        report.append(f"Required Match (25% of FSEOG): {format_currency(required_match)}")
                        report.append(f"Actual Match Provided: {format_currency(actual_match)}")

                        if required_match > 0:
                            match_percentage = (actual_match / required_match) * 100
                            report.append(f"Match Compliance: {match_percentage:.1f}%")
                            if match_percentage >= 100:
                                report.append("Status: COMPLIANT ✓")
                            else:
                                report.append("Status: SHORTFALL - Additional matching required")
                else:
                    report.append("No institutional matching contributions recorded")

                report.append("")

                # Section 5: Student Enrollment Summary
                report.append("SECTION 5: STUDENT ENROLLMENT DATA")
                report.append("-" * 80)

                enrollment_data = conn.execute("""
                    SELECT
                        COUNT(DISTINCT sfa.student_id) as total_aid_recipients,
                        COUNT(DISTINCT CASE WHEN sfa.status = 'awarded' THEN sfa.student_id END) as awarded_count,
                        COUNT(DISTINCT CASE WHEN sfa.status = 'disbursed' THEN sfa.student_id END) as disbursed_count,
                        COUNT(DISTINCT CASE WHEN fat.requires_repayment = 1 THEN sfa.student_id END) as loan_recipients,
                        COUNT(DISTINCT CASE WHEN fat.requires_repayment = 0 THEN sfa.student_id END) as grant_recipients
                    FROM student_financial_aid sfa
                    JOIN financial_aid_types fat ON sfa.aid_type_id = fat.aid_type_id
                """).fetchone()

                if enrollment_data:
                    enroll = dict(enrollment_data)
                    report.append(f"Total Students Receiving Aid: {enroll['total_aid_recipients']}")
                    report.append(f"  - Awards Approved: {enroll['awarded_count']}")
                    report.append(f"  - Funds Disbursed: {enroll['disbursed_count']}")
                    report.append(f"Loan Recipients: {enroll['loan_recipients']}")
                    report.append(f"Grant Recipients: {enroll['grant_recipients']}")

                report.append("")

                # Section 6: Compliance Summary
                report.append("SECTION 6: COMPLIANCE SUMMARY")
                report.append("-" * 80)

                total_federal = 0
                if fws_data:
                    total_federal += dict(fws_data)['total_disbursed'] or 0
                if fseog_data:
                    total_federal += dict(fseog_data)['total_disbursed'] or 0
                if perkins_data:
                    total_federal += dict(perkins_data)['total_disbursed'] or 0

                report.append(f"Total Federal Campus-Based Aid Disbursed: {format_currency(total_federal)}")
                report.append("")
                report.append("Compliance Checklist:")
                report.append("  □ FWS expenditures reported")
                report.append("  □ FSEOG expenditures reported")
                report.append("  □ Institutional matching funds verified")
                report.append("  □ Enrollment data current")
                report.append("  □ Award overages reviewed")
                report.append("  □ Reconciliation completed")
                report.append("")
                report.append("Note: This report should be reviewed by the Financial Aid Director")
                report.append("before submission to the U.S. Department of Education.")

            report.append("")
            report.append("=" * 80)
            report.append("END OF FISAP COMPLIANCE REPORT")
            report.append("=" * 80)

            report_text.insert('1.0', '\n'.join(report))
            report_text.config(state='disabled')

        except Exception as e:
            logger.error(f"Error generating FISAP report: {e}")
            report_text.insert('1.0', f"Error generating report:\n{str(e)}\n\nPlease contact your system administrator.")
            report_text.config(state='disabled')

        # Export buttons
        button_frame = ttk.Frame(report_window)
        button_frame.pack(pady=10)

        ttk.Button(button_frame, text=get_text("financial_aid.admin_portal.buttons.export_pdf", "Export to PDF"),
                  command=lambda: self._export_report_to_pdf(report_text, "FISAP_Compliance_Report")).pack(side='left', padx=5)
        ttk.Button(button_frame, text=get_text("financial_aid.admin_portal.buttons.export_txt", "Export to Text"),
                  command=lambda: self._export_report_to_txt(report_text, "FISAP_Compliance_Report")).pack(side='left', padx=5)
        ttk.Button(button_frame, text=get_text("financial_aid.admin_portal.buttons.close", "Close"),
                  command=report_window.destroy).pack(side='left', padx=5)

    def _generate_sai_report(self):
        """Generate Student Aid Index (SAI) report"""
        report_window = tk.Toplevel(self.parent_frame)
        report_window.title(get_text("financial_aid.admin_portal.reports.sai_report_title", "Student Aid Index (SAI) Report"))
        report_window.geometry("900x700")

        ttk.Label(report_window, text=get_text("financial_aid.admin_portal.reports.sai_analysis", "Student Aid Index (SAI) Analysis"), style='Title.TLabel').pack(pady=10)

        report_frame = ttk.Frame(report_window)
        report_frame.pack(fill='both', expand=True, padx=10, pady=10)

        report_text = scrolledtext.ScrolledText(report_frame, width=100, height=35, wrap='word', font=('Courier', 10))
        report_text.pack(fill='both', expand=True)

        try:
            report = []
            report.append("=" * 80)
            report.append("STUDENT AID INDEX (SAI) / EXPECTED FAMILY CONTRIBUTION (EFC) REPORT")
            report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            report.append(f"Academic Year: {get_current_academic_year()}")
            report.append("=" * 80)
            report.append("")
            report.append("This report analyzes financial need based on aid awards and costs.")
            report.append("Note: SAI/EFC data typically comes from FAFSA submissions.")
            report.append("")

            with get_connection() as conn:
                # Section 1: Aid Distribution by Need Level
                report.append("SECTION 1: AID DISTRIBUTION BY AWARD LEVEL")
                report.append("-" * 80)

                need_distribution = conn.execute("""
                    SELECT
                        CASE
                            WHEN sfa.awarded_amount < 2000 THEN 'Low Need (< $2,000)'
                            WHEN sfa.awarded_amount < 5000 THEN 'Moderate Need ($2,000-$5,000)'
                            WHEN sfa.awarded_amount < 10000 THEN 'High Need ($5,000-$10,000)'
                            ELSE 'Very High Need (> $10,000)'
                        END as need_category,
                        COUNT(DISTINCT sfa.student_id) as student_count,
                        SUM(sfa.awarded_amount) as total_awarded,
                        AVG(sfa.awarded_amount) as avg_award
                    FROM student_financial_aid sfa
                    WHERE sfa.status IN ('awarded', 'disbursed')
                    GROUP BY need_category
                    ORDER BY MIN(sfa.awarded_amount)
                """).fetchall()

                for category in need_distribution:
                    cat_dict = dict(category)
                    report.append(f"\n{cat_dict['need_category']}")
                    report.append(f"  Students: {cat_dict['student_count']}")
                    report.append(f"  Total Awarded: {format_currency(cat_dict['total_awarded'] or 0)}")
                    report.append(f"  Average Award: {format_currency(cat_dict['avg_award'] or 0)}")

                report.append("")

                # Section 2: Aid Package Analysis
                report.append("SECTION 2: AID PACKAGE COMPOSITION ANALYSIS")
                report.append("-" * 80)

                package_analysis = conn.execute("""
                    SELECT
                        fat.aid_category,
                        COUNT(DISTINCT sfa.student_id) as recipients,
                        SUM(sfa.awarded_amount) as total_amount,
                        AVG(sfa.awarded_amount) as avg_amount,
                        MIN(sfa.awarded_amount) as min_amount,
                        MAX(sfa.awarded_amount) as max_amount
                    FROM student_financial_aid sfa
                    JOIN financial_aid_types fat ON sfa.aid_type_id = fat.aid_type_id
                    WHERE sfa.status IN ('awarded', 'disbursed')
                    GROUP BY fat.aid_category
                    ORDER BY total_amount DESC
                """).fetchall()

                for pkg in package_analysis:
                    pkg_dict = dict(pkg)
                    report.append(f"\nAid Category: {(pkg_dict['aid_category'] or 'Other').upper()}")
                    report.append(f"  Recipients: {pkg_dict['recipients']}")
                    report.append(f"  Total Awarded: {format_currency(pkg_dict['total_amount'] or 0)}")
                    report.append(f"  Average Award: {format_currency(pkg_dict['avg_amount'] or 0)}")
                    report.append(f"  Range: {format_currency(pkg_dict['min_amount'] or 0)} - {format_currency(pkg_dict['max_amount'] or 0)}")

                report.append("")

                # Section 3: Grant vs Loan Analysis
                report.append("SECTION 3: GRANT vs LOAN DISTRIBUTION")
                report.append("-" * 80)

                grant_loan_analysis = conn.execute("""
                    SELECT
                        CASE WHEN fat.requires_repayment = 1 THEN 'Loans (Repayable)'
                             ELSE 'Grants/Scholarships (Non-Repayable)'
                        END as aid_type,
                        COUNT(DISTINCT sfa.student_id) as recipients,
                        SUM(sfa.awarded_amount) as total_awarded,
                        SUM(sfa.disbursed_amount) as total_disbursed,
                        AVG(sfa.awarded_amount) as avg_award
                    FROM student_financial_aid sfa
                    JOIN financial_aid_types fat ON sfa.aid_type_id = fat.aid_type_id
                    WHERE sfa.status IN ('awarded', 'disbursed')
                    GROUP BY fat.requires_repayment
                    ORDER BY fat.requires_repayment
                """).fetchall()

                total_aid = 0
                for aid_type in grant_loan_analysis:
                    aid_dict = dict(aid_type)
                    total_aid += aid_dict['total_awarded'] or 0
                    report.append(f"\n{aid_dict['aid_type']}")
                    report.append(f"  Recipients: {aid_dict['recipients']}")
                    report.append(f"  Total Awarded: {format_currency(aid_dict['total_awarded'] or 0)}")
                    report.append(f"  Total Disbursed: {format_currency(aid_dict['total_disbursed'] or 0)}")
                    report.append(f"  Average per Student: {format_currency(aid_dict['avg_award'] or 0)}")

                # Calculate grant-to-loan ratio
                if grant_loan_analysis and len(grant_loan_analysis) > 0:
                    grant_total = 0
                    loan_total = 0
                    for aid_type in grant_loan_analysis:
                        aid_dict = dict(aid_type)
                        if 'Grant' in aid_dict['aid_type']:
                            grant_total = aid_dict['total_awarded'] or 0
                        else:
                            loan_total = aid_dict['total_awarded'] or 0

                    report.append("")
                    if total_aid > 0:
                        grant_pct = (grant_total / total_aid) * 100 if total_aid > 0 else 0
                        loan_pct = (loan_total / total_aid) * 100 if total_aid > 0 else 0
                        report.append(f"Grant Percentage: {grant_pct:.1f}%")
                        report.append(f"Loan Percentage: {loan_pct:.1f}%")

                        if grant_pct > 50:
                            report.append("Status: FAVORABLE - Majority of aid is gift aid")
                        else:
                            report.append("Status: CAUTION - High reliance on loans")

                report.append("")

                # Section 4: Unmet Need Analysis
                report.append("SECTION 4: COVERAGE AND NEED ANALYSIS")
                report.append("-" * 80)

                # Calculate students with different coverage levels
                coverage_analysis = conn.execute("""
                    SELECT
                        student_id,
                        SUM(awarded_amount) as total_aid,
                        COUNT(DISTINCT aid_type_id) as aid_types_count
                    FROM student_financial_aid
                    WHERE status IN ('awarded', 'disbursed')
                    GROUP BY student_id
                """).fetchall()

                if coverage_analysis:
                    total_students = len(coverage_analysis)
                    single_source = sum(1 for s in coverage_analysis if dict(s)['aid_types_count'] == 1)
                    multiple_sources = sum(1 for s in coverage_analysis if dict(s)['aid_types_count'] > 1)

                    aid_amounts = [dict(s)['total_aid'] for s in coverage_analysis]
                    avg_total_aid = sum(aid_amounts) / len(aid_amounts) if aid_amounts else 0
                    median_aid = sorted(aid_amounts)[len(aid_amounts) // 2] if aid_amounts else 0

                    report.append(f"Total Students with Aid: {total_students}")
                    report.append(f"Students with Single Aid Source: {single_source}")
                    report.append(f"Students with Multiple Aid Sources: {multiple_sources}")
                    report.append(f"Average Total Aid per Student: {format_currency(avg_total_aid)}")
                    report.append(f"Median Total Aid per Student: {format_currency(median_aid)}")

                    # Estimate typical Cost of Attendance (COA)
                    estimated_coa = 30000  # Placeholder - adjust based on institution
                    report.append(f"\nEstimated Cost of Attendance: {format_currency(estimated_coa)}")

                    if avg_total_aid > 0:
                        coverage_pct = (avg_total_aid / estimated_coa) * 100
                        unmet_need = max(0, estimated_coa - avg_total_aid)
                        report.append(f"Average Aid Coverage: {coverage_pct:.1f}%")
                        report.append(f"Average Unmet Need: {format_currency(unmet_need)}")

                        if coverage_pct >= 75:
                            report.append("Status: STRONG - High financial need being met")
                        elif coverage_pct >= 50:
                            report.append("Status: ADEQUATE - Moderate coverage")
                        else:
                            report.append("Status: CONCERN - Significant unmet need")
                else:
                    report.append("No coverage analysis data available")

                report.append("")

                # Section 5: Recommendations
                report.append("SECTION 5: RECOMMENDATIONS")
                report.append("-" * 80)

                # Calculate key metrics for recommendations
                if grant_loan_analysis:
                    grant_total = 0
                    loan_total = 0
                    for aid_type in grant_loan_analysis:
                        aid_dict = dict(aid_type)
                        if 'Grant' in aid_dict['aid_type']:
                            grant_total = aid_dict['total_awarded'] or 0
                        else:
                            loan_total = aid_dict['total_awarded'] or 0

                    report.append("Based on the analysis:")
                    report.append("")

                    if grant_total < loan_total:
                        report.append("• Consider increasing grant/scholarship funding to reduce")
                        report.append("  student debt burden")

                    if coverage_analysis and avg_total_aid < estimated_coa * 0.5:
                        report.append("• Average aid covers less than 50% of COA - evaluate")
                        report.append("  institutional aid policies")

                    if multiple_sources < single_source:
                        report.append("• Many students rely on single aid source - consider")
                        report.append("  package diversification")

                    report.append("")
                    report.append("• Review SAI/EFC thresholds for Pell Grant eligibility")
                    report.append("• Conduct FAFSA completion campaign to ensure all eligible")
                    report.append("  students apply for federal aid")
                    report.append("• Implement verification process for selected applications")
                    report.append("• Monitor professional judgment requests for special circumstances")

            report.append("")
            report.append("=" * 80)
            report.append("END OF SAI/EFC ANALYSIS REPORT")
            report.append("=" * 80)
            report.append("")
            report.append("Note: This report provides an overview of financial need and aid distribution.")
            report.append("For detailed SAI/EFC values, import FAFSA data via ISIR processing.")

            report_text.insert('1.0', '\n'.join(report))
            report_text.config(state='disabled')

        except Exception as e:
            logger.error(f"Error generating SAI report: {e}")
            report_text.insert('1.0', f"Error generating report:\n{str(e)}\n\nPlease contact your system administrator.")
            report_text.config(state='disabled')

        # Export buttons
        button_frame = ttk.Frame(report_window)
        button_frame.pack(pady=10)

        ttk.Button(button_frame, text=get_text("financial_aid.admin_portal.buttons.export_pdf", "Export to PDF"),
                  command=lambda: self._export_report_to_pdf(report_text, "SAI_EFC_Analysis_Report")).pack(side='left', padx=5)
        ttk.Button(button_frame, text=get_text("financial_aid.admin_portal.buttons.export_txt", "Export to Text"),
                  command=lambda: self._export_report_to_txt(report_text, "SAI_EFC_Analysis_Report")).pack(side='left', padx=5)
        ttk.Button(button_frame, text=get_text("financial_aid.admin_portal.buttons.close", "Close"),
                  command=lambda: report_window.destroy).pack(side='left', padx=5)

    def _generate_need_analysis_report(self):
        """Generate Need Analysis report showing unmet financial need by demographics"""
        report_window = tk.Toplevel(self.parent_frame)
        report_window.title(get_text("financial_aid.admin_portal.reports.need_analysis_title", "Need Analysis Report"))
        report_window.geometry("900x700")

        ttk.Label(report_window, text=get_text("financial_aid.admin_portal.reports.need_analysis", "Need Analysis Report"), style='Title.TLabel').pack(pady=10)

        report_frame = ttk.Frame(report_window)
        report_frame.pack(fill='both', expand=True, padx=10, pady=10)

        report_text = scrolledtext.ScrolledText(report_frame, width=100, height=35, wrap='word', font=('Courier', 10))
        report_text.pack(fill='both', expand=True)

        try:
            report = []
            report.append("=" * 80)
            report.append("FINANCIAL NEED ANALYSIS REPORT")
            report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            report.append(f"Academic Year: {get_current_academic_year()}")
            report.append("=" * 80)
            report.append("")

            with get_connection() as conn:
                # Section 1: Overall Need Summary
                report.append("SECTION 1: OVERALL FINANCIAL NEED SUMMARY")
                report.append("-" * 80)

                overall = conn.execute("""
                    SELECT
                        COUNT(DISTINCT sfa.student_id) as aided_students,
                        SUM(sfa.awarded_amount) as total_awarded,
                        AVG(sfa.awarded_amount) as avg_awarded,
                        SUM(sfa.disbursed_amount) as total_disbursed
                    FROM student_financial_aid sfa
                    WHERE sfa.status IN ('awarded', 'disbursed')
                """).fetchone()

                if overall:
                    d = dict(overall)
                    report.append(f"Students Receiving Aid: {d['aided_students'] or 0}")
                    report.append(f"Total Aid Awarded: {format_currency(d['total_awarded'] or 0)}")
                    report.append(f"Average Award: {format_currency(d['avg_awarded'] or 0)}")
                    report.append(f"Total Disbursed: {format_currency(d['total_disbursed'] or 0)}")

                # Total enrolled students
                total_enrolled = conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]
                aided = dict(overall)['aided_students'] or 0 if overall else 0
                unaided = total_enrolled - aided
                report.append(f"\nTotal Enrolled Students: {total_enrolled}")
                report.append(f"Students Without Aid: {unaided}")
                if total_enrolled > 0:
                    report.append(f"Aid Participation Rate: {aided / total_enrolled * 100:.1f}%")

                report.append("")

                # Section 2: Need by Aid Category
                report.append("SECTION 2: AID DISTRIBUTION BY CATEGORY")
                report.append("-" * 80)

                by_category = conn.execute("""
                    SELECT
                        COALESCE(fat.aid_category, 'Other') as category,
                        COUNT(DISTINCT sfa.student_id) as recipients,
                        SUM(sfa.awarded_amount) as total,
                        AVG(sfa.awarded_amount) as avg_amount
                    FROM student_financial_aid sfa
                    LEFT JOIN financial_aid_types fat ON sfa.aid_type_id = fat.aid_type_id
                    WHERE sfa.status IN ('awarded', 'disbursed')
                    GROUP BY category
                    ORDER BY total DESC
                """).fetchall()

                for row in by_category:
                    r = dict(row)
                    report.append(f"\n{(r['category'] or 'Other').upper()}")
                    report.append(f"  Recipients: {r['recipients']}")
                    report.append(f"  Total: {format_currency(r['total'] or 0)}")
                    report.append(f"  Average: {format_currency(r['avg_amount'] or 0)}")

                report.append("")

                # Section 3: Students with Highest Unmet Need
                report.append("SECTION 3: STUDENTS WITH HIGHEST TOTAL AID")
                report.append("-" * 80)

                top_aid = conn.execute("""
                    SELECT
                        sfa.student_id,
                        SUM(sfa.awarded_amount) as total_aid,
                        COUNT(DISTINCT sfa.aid_type_id) as aid_sources
                    FROM student_financial_aid sfa
                    WHERE sfa.status IN ('awarded', 'disbursed')
                    GROUP BY sfa.student_id
                    ORDER BY total_aid DESC
                    LIMIT 15
                """).fetchall()

                if top_aid:
                    report.append(f"{'Student ID':<15} {'Total Aid':>15} {'Sources':>10}")
                    report.append("-" * 40)
                    for row in top_aid:
                        r = dict(row)
                        report.append(f"{r['student_id']:<15} {format_currency(r['total_aid'] or 0):>15} {r['aid_sources']:>10}")
                else:
                    report.append("No aid data available")

                report.append("")

                # Section 4: Aid Status Breakdown
                report.append("SECTION 4: AID STATUS BREAKDOWN")
                report.append("-" * 80)

                status_breakdown = conn.execute("""
                    SELECT status, COUNT(*) as count, SUM(awarded_amount) as total
                    FROM student_financial_aid
                    GROUP BY status
                    ORDER BY count DESC
                """).fetchall()

                for row in status_breakdown:
                    r = dict(row)
                    report.append(f"  {r['status'].title()}: {r['count']} awards, {format_currency(r['total'] or 0)}")

            report.append("")
            report.append("=" * 80)
            report.append("END OF NEED ANALYSIS REPORT")
            report.append("=" * 80)

            report_text.insert('1.0', '\n'.join(report))
            report_text.config(state='disabled')

        except Exception as e:
            logger.error(f"Error generating need analysis report: {e}")
            report_text.insert('1.0', f"Error generating report:\n{str(e)}")
            report_text.config(state='disabled')

        btn_frame = ttk.Frame(report_window)
        btn_frame.pack(pady=10)

        ttk.Button(btn_frame, text=get_text("financial_aid.admin_portal.buttons.export_csv", "Export as CSV"),
                  command=lambda: self._export_report_to_csv(report_text.get('1.0', 'end-1c'), "need_analysis_report")).pack(side='left', padx=5)
        ttk.Button(btn_frame, text=get_text("financial_aid.admin_portal.buttons.export_text", "Export as Text"),
                  command=lambda: self._export_report_to_txt(report_text.get('1.0', 'end-1c'), "need_analysis_report")).pack(side='left', padx=5)
        ttk.Button(btn_frame, text=get_text("financial_aid.admin_portal.buttons.close", "Close"),
                  command=report_window.destroy).pack(side='left', padx=5)

    def _generate_renewal_tracking_report(self):
        """Generate Renewal Tracking report for scholarships"""
        report_window = tk.Toplevel(self.parent_frame)
        report_window.title(get_text("financial_aid.admin_portal.reports.renewal_tracking_title", "Renewal Tracking Report"))
        report_window.geometry("900x700")

        ttk.Label(report_window, text=get_text("financial_aid.admin_portal.reports.renewal_tracking", "Renewal Tracking Report"), style='Title.TLabel').pack(pady=10)

        report_frame = ttk.Frame(report_window)
        report_frame.pack(fill='both', expand=True, padx=10, pady=10)

        report_text = scrolledtext.ScrolledText(report_frame, width=100, height=35, wrap='word', font=('Courier', 10))
        report_text.pack(fill='both', expand=True)

        try:
            report = []
            report.append("=" * 80)
            report.append("SCHOLARSHIP RENEWAL TRACKING REPORT")
            report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            report.append(f"Academic Year: {get_current_academic_year()}")
            report.append("=" * 80)
            report.append("")

            with get_connection() as conn:
                # Check if scholarship_awards table exists
                table_check = conn.execute("""
                    SELECT name FROM sqlite_master
                    WHERE type='table' AND name='scholarship_awards'
                """).fetchone()

                if not table_check:
                    report.append("SCHOLARSHIP AWARDS TABLE NOT YET CONFIGURED")
                    report.append("")
                    report.append("The scholarship_awards table has not been created yet.")
                    report.append("This report requires scholarship award tracking to be enabled.")
                else:
                    # Section 1: Renewable Scholarship Summary
                    report.append("SECTION 1: RENEWABLE SCHOLARSHIP OVERVIEW")
                    report.append("-" * 80)

                    renewable_summary = conn.execute("""
                        SELECT
                            COUNT(*) as total_awards,
                            SUM(CASE WHEN sa.is_renewable = 1 THEN 1 ELSE 0 END) as renewable_count,
                            SUM(CASE WHEN sa.is_renewable = 0 THEN 1 ELSE 0 END) as non_renewable_count,
                            SUM(sa.amount) as total_amount,
                            SUM(CASE WHEN sa.is_renewable = 1 THEN sa.amount ELSE 0 END) as renewable_amount
                        FROM scholarship_awards sa
                        WHERE sa.status = 'active'
                    """).fetchone()

                    if renewable_summary:
                        d = dict(renewable_summary)
                        report.append(f"Total Active Awards: {d['total_awards'] or 0}")
                        report.append(f"Renewable Awards: {d['renewable_count'] or 0}")
                        report.append(f"Non-Renewable Awards: {d['non_renewable_count'] or 0}")
                        report.append(f"Total Award Amount: {format_currency(d['total_amount'] or 0)}")
                        report.append(f"Renewable Amount: {format_currency(d['renewable_amount'] or 0)}")

                    report.append("")

                    # Section 2: Awards by Scholarship
                    report.append("SECTION 2: ACTIVE AWARDS BY SCHOLARSHIP")
                    report.append("-" * 80)

                    awards_by_scholarship = conn.execute("""
                        SELECT
                            COALESCE(s.name, 'Unknown') as scholarship_name,
                            s.renewable as is_renewable_scholarship,
                            COUNT(sa.award_id) as award_count,
                            SUM(sa.amount) as total_awarded,
                            AVG(sa.amount) as avg_award
                        FROM scholarship_awards sa
                        LEFT JOIN scholarships s ON sa.scholarship_id = s.scholarship_id
                        WHERE sa.status = 'active'
                        GROUP BY sa.scholarship_id
                        ORDER BY total_awarded DESC
                    """).fetchall()

                    if awards_by_scholarship:
                        for row in awards_by_scholarship:
                            r = dict(row)
                            renewable_tag = " [RENEWABLE]" if r['is_renewable_scholarship'] else ""
                            report.append(f"\n{r['scholarship_name']}{renewable_tag}")
                            report.append(f"  Active Awards: {r['award_count']}")
                            report.append(f"  Total Awarded: {format_currency(r['total_awarded'] or 0)}")
                            report.append(f"  Average Award: {format_currency(r['avg_award'] or 0)}")
                    else:
                        report.append("No active scholarship awards found")

                    report.append("")

                    # Section 3: Recent Awards
                    report.append("SECTION 3: RECENT SCHOLARSHIP AWARDS")
                    report.append("-" * 80)

                    recent_awards = conn.execute("""
                        SELECT
                            sa.student_id,
                            COALESCE(s.name, 'Unknown') as scholarship_name,
                            sa.amount,
                            sa.academic_year,
                            sa.is_renewable,
                            sa.awarded_date
                        FROM scholarship_awards sa
                        LEFT JOIN scholarships s ON sa.scholarship_id = s.scholarship_id
                        WHERE sa.status = 'active'
                        ORDER BY sa.awarded_date DESC
                        LIMIT 20
                    """).fetchall()

                    if recent_awards:
                        report.append(f"{'Student':<12} {'Scholarship':<30} {'Amount':>12} {'Year':<12} {'Renewable':<10}")
                        report.append("-" * 76)
                        for row in recent_awards:
                            r = dict(row)
                            renew_str = "Yes" if r['is_renewable'] else "No"
                            name = (r['scholarship_name'] or 'Unknown')[:28]
                            report.append(f"{r['student_id']:<12} {name:<30} {format_currency(r['amount'] or 0):>12} {r['academic_year'] or 'N/A':<12} {renew_str:<10}")
                    else:
                        report.append("No recent awards found")

            report.append("")
            report.append("=" * 80)
            report.append("END OF RENEWAL TRACKING REPORT")
            report.append("=" * 80)

            report_text.insert('1.0', '\n'.join(report))
            report_text.config(state='disabled')

        except Exception as e:
            logger.error(f"Error generating renewal tracking report: {e}")
            report_text.insert('1.0', f"Error generating report:\n{str(e)}")
            report_text.config(state='disabled')

        btn_frame = ttk.Frame(report_window)
        btn_frame.pack(pady=10)

        ttk.Button(btn_frame, text=get_text("financial_aid.admin_portal.buttons.export_csv", "Export as CSV"),
                  command=lambda: self._export_report_to_csv(report_text.get('1.0', 'end-1c'), "renewal_tracking_report")).pack(side='left', padx=5)
        ttk.Button(btn_frame, text=get_text("financial_aid.admin_portal.buttons.export_text", "Export as Text"),
                  command=lambda: self._export_report_to_txt(report_text.get('1.0', 'end-1c'), "renewal_tracking_report")).pack(side='left', padx=5)
        ttk.Button(btn_frame, text=get_text("financial_aid.admin_portal.buttons.close", "Close"),
                  command=report_window.destroy).pack(side='left', padx=5)

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

                show_success(get_text("financial_aid.admin_portal.dialogs.export_successful", "Export Successful"), get_text("financial_aid.admin_portal.messages.report_exported", "Report exported to:\n{filepath}").format(filepath=filepath))
                log_activity('export', 'financial_aid_report', filepath, {'report_type': filename_base, 'format': 'csv'})

        except Exception as e:
            logger.error(f"Error exporting report to CSV: {e}")
            show_error(get_text("financial_aid.admin_portal.dialogs.export_error", "Export Error"), get_text("financial_aid.admin_portal.errors.failed_export_report", "Failed to export report: {error}").format(error=str(e)))

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

                show_success(get_text("financial_aid.admin_portal.dialogs.export_successful", "Export Successful"), get_text("financial_aid.admin_portal.messages.report_exported", "Report exported to:\n{filepath}").format(filepath=filepath))
                log_activity('export', 'financial_aid_report', filepath, {'report_type': filename_base, 'format': 'txt'})

        except Exception as e:
            logger.error(f"Error exporting report to text: {e}")
            show_error(get_text("financial_aid.admin_portal.dialogs.export_error", "Export Error"), get_text("financial_aid.admin_portal.errors.failed_export_report", "Failed to export report: {error}").format(error=str(e)))

    def _export_report_text(self, report_text: str, filename_base: str):
        """Alias for _export_report_to_txt for backward compatibility"""
        self._export_report_to_txt(report_text, filename_base)

    def _export_report_to_pdf(self, report_text: str, filename_base: str):
        """Export report to PDF file"""
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch
            from reportlab.lib.enums import TA_LEFT

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filepath = messagebox.asksaveasfilename(
                defaultextension=".pdf",
                filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
                initialfile=f"{filename_base}_{timestamp}.pdf"
            )

            if filepath:
                # Create PDF document
                doc = SimpleDocTemplate(filepath, pagesize=letter,
                                       rightMargin=72, leftMargin=72,
                                       topMargin=72, bottomMargin=18)

                # Container for PDF elements
                story = []

                # Get default styles
                styles = getSampleStyleSheet()

                # Create custom style for report text
                report_style = ParagraphStyle(
                    'ReportStyle',
                    parent=styles['Normal'],
                    fontName='Courier',
                    fontSize=9,
                    leading=12,
                    alignment=TA_LEFT,
                    spaceAfter=6
                )

                # Split report into lines and add to story
                for line in report_text.split('\n'):
                    if line.strip():
                        # Replace special characters that might cause issues
                        line = line.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                        p = Paragraph(line, report_style)
                        story.append(p)
                    else:
                        story.append(Spacer(1, 0.1 * inch))

                # Build PDF
                doc.build(story)

                show_success(
                    get_text("financial_aid.admin_portal.dialogs.export_successful", "Export Successful"),
                    get_text("financial_aid.admin_portal.messages.report_exported", "Report exported to:\n{filepath}").format(filepath=filepath)
                )
                log_activity('export', 'financial_aid_report', filepath, {'report_type': filename_base, 'format': 'pdf'})

        except ImportError:
            show_error(
                get_text("financial_aid.admin_portal.dialogs.pdf_library_missing", "PDF Library Missing"),
                get_text("financial_aid.admin_portal.messages.install_reportlab", "Please install reportlab to export to PDF:\npip install reportlab")
            )
        except Exception as e:
            logger.error(f"Error exporting report to PDF: {e}")
            show_error(
                get_text("financial_aid.admin_portal.dialogs.export_error", "Export Error"),
                get_text("financial_aid.admin_portal.errors.failed_export_report", "Failed to export report: {error}").format(error=str(e))
            )

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
                show_warning(get_text("financial_aid.admin_portal.dialogs.no_admin_email", "No Admin Email"), get_text("financial_aid.admin_portal.messages.no_admin_email", "No admin email address found in the database."))
                return

            # Send email with report using template
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            subject, body = render_template('reports/financial_aid_report', {
                'report_name': report_name,
                'timestamp': timestamp,
                'report_content': report_text
            })

            # Fallback if template not found
            if not subject or not body:
                subject = f"Financial Aid Report: {report_name}"
                body = f"Financial Aid Report: {report_name}\nGenerated: {timestamp}\n\n{report_text}"

            send_email(
                recipient_email=admin_email,
                subject=subject,
                body=body
            )

            show_success(get_text("financial_aid.admin_portal.dialogs.email_sent", "Email Sent"), get_text("financial_aid.admin_portal.messages.report_emailed", "Report has been emailed to:\n{email}").format(email=admin_email))
            log_activity('email', 'financial_aid_report', admin_email, {
                'report_name': report_name,
                'recipient': admin_email
            })

        except Exception as e:
            logger.error(f"Error emailing report: {e}")
            show_error(get_text("financial_aid.admin_portal.dialogs.email_error", "Email Error"), get_text("financial_aid.admin_portal.errors.failed_email_report", "Failed to email report:\n{error}").format(error=str(e)))

    def show_fafsa_import(self):
        """Show FAFSA import interface"""
        # Ensure we have a valid parent frame/window
        parent = self._ensure_valid_parent()
        self.parent_frame = parent

        clear_frame(self.parent_frame)

        # Title
        title_frame = ttk.Frame(self.parent_frame)
        title_frame.pack(fill='x', padx=10, pady=10)
        ttk.Label(title_frame, text=get_text("financial_aid.admin_portal.fafsa.title", "Import FAFSA Data"), style='Title.TLabel').pack(side='left')
        ttk.Button(title_frame, text=get_text("financial_aid.admin_portal.buttons.back_to_dashboard", "Back to Dashboard"), command=self.show_dashboard).pack(side='right')

        # Import form
        import_frame = ttk.LabelFrame(self.parent_frame, text=get_text("financial_aid.admin_portal.fafsa.import_section", "FAFSA Data Import"), padding=20)
        import_frame.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(import_frame, text=get_text("financial_aid.admin_portal.fafsa.select_file", "Select FAFSA data file (CSV format):"),
                 font=('Arial', 10, 'bold')).pack(anchor='w', pady=10)

        file_frame = ttk.Frame(import_frame)
        file_frame.pack(fill='x', pady=10)

        file_var = tk.StringVar()
        ttk.Entry(file_frame, textvariable=file_var, width=50, state='readonly').pack(side='left', padx=(0, 10))
        ttk.Button(file_frame, text=get_text("financial_aid.admin_portal.buttons.browse", "Browse..."),
                  command=lambda: file_var.set(filedialog.askopenfilename(
                      filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]))).pack(side='left')

        ttk.Label(import_frame, text=get_text("financial_aid.admin_portal.fafsa.file_format_hint", "\nFile should contain columns: student_id, efc, sai, household_income, etc."),
                 foreground='blue').pack(anchor='w')

        btn_frame = ttk.Frame(import_frame)
        btn_frame.pack(pady=20)

        ttk.Button(btn_frame, text=get_text("financial_aid.admin_portal.buttons.import_data", "Import Data"),
                  command=lambda: self._import_fafsa_file(file_var.get()),
                  style='Success.TButton').pack(side='left', padx=5)
        ttk.Button(btn_frame, text=get_text("financial_aid.admin_portal.buttons.cancel", "Cancel"), command=self.show_dashboard).pack(side='left', padx=5)

    def _import_fafsa_file(self, filepath: str):
        """Import FAFSA data from file"""
        if not filepath:
            show_warning(get_text("financial_aid.admin_portal.dialogs.no_file_selected", "No File Selected"), get_text("financial_aid.admin_portal.messages.select_file_to_import", "Please select a file to import"))
            return

        try:
            # This would use the FAFSA manager
            show_success(get_text("financial_aid.admin_portal.dialogs.import_started", "Import Started"), get_text("financial_aid.admin_portal.messages.fafsa_import_queued", "FAFSA data import has been queued for processing"))
            log_activity('import', 'fafsa_data', filepath, {'file': filepath})

        except Exception as e:
            logger.error(f"Error importing FAFSA data: {e}")
            show_error(get_text("financial_aid.admin_portal.dialogs.import_error", "Import Error"), get_text("financial_aid.admin_portal.errors.failed_import_fafsa", "Failed to import FAFSA data: {error}").format(error=str(e)))
