"""
Student Portal for Financial Aid & Scholarships

This module provides the student-facing interface for viewing scholarships,
applying for aid, tracking applications, and managing awards.
"""

from typing import Any, Dict, Optional

from .common_imports import (
    tk,
    ttk,
    scrolledtext,
    logging,
    datetime,
    get_connection,
    log_activity,
    get_auth,
    FinancialAidManager,
    ScholarshipManager,
    clear_frame,
    create_data_table,
    create_stat_card,
    create_scrollable_frame,
    create_search_filter_bar,
    format_currency,
    format_date,
    validate_date,
    show_error,
    show_success,
    show_warning,
    get_current_user,
    get_student_id,
    get_current_academic_year,
    get_academic_year_list,
    get_status_color,
    COLORS,
)
from university_system.modules.shared.utils.i18n import get_text
from university_system.infrastructure.email.email_service import send_email
from university_system.infrastructure.email.template_utils import render_template
from tkinter import filedialog
import os

# Import secure file upload handler
try:
    from university_system.infrastructure.security.file_upload import (
        validate_upload,
        secure_filename,
    )
    SECURE_UPLOAD_AVAILABLE = True
except ImportError:
    SECURE_UPLOAD_AVAILABLE = False
    validate_upload = None
    def secure_filename(x):
        return x

logger = logging.getLogger(__name__)


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
        ttk.Label(title_frame, text=get_text("financial_aid.student_portal.dashboard_title", "My Financial Aid Dashboard"), style='Title.TLabel').pack(anchor='w')

        # Statistics cards
        stats_frame = ttk.Frame(self.parent_frame)
        stats_frame.pack(fill='x', padx=10, pady=10)

        try:
            # Get student statistics
            stats = self._get_student_stats()

            # Create stat cards
            cards = [
                (get_text("financial_aid.student_portal.stats.total_awards", "Total Awards"), format_currency(stats['total_awards']), 'success'),
                (get_text("financial_aid.student_portal.stats.pending_applications", "Pending Applications"), str(stats['pending_apps']), 'warning'),
                (get_text("financial_aid.student_portal.stats.available_scholarships", "Available Scholarships"), str(stats['available_scholarships']), 'info'),
                (get_text("financial_aid.student_portal.stats.total_disbursed", "Total Disbursed"), format_currency(stats['total_disbursed']), 'primary')
            ]

            for i, (title, value, color) in enumerate(cards):
                card = create_stat_card(stats_frame, title, value, color)
                card.grid(row=0, column=i, padx=10, pady=5, sticky='ew')
                stats_frame.grid_columnconfigure(i, weight=1)

        except Exception as e:
            logger.error(f"Error loading stats: {e}")
            ttk.Label(stats_frame, text=get_text("financial_aid.student_portal.errors.loading_statistics", "Error loading statistics"), foreground='red').pack()

        # Quick actions
        actions_frame = ttk.LabelFrame(self.parent_frame, text=get_text("financial_aid.student_portal.quick_actions", "Quick Actions"), padding=10)
        actions_frame.pack(fill='x', padx=10, pady=10)

        actions = [
            (get_text("financial_aid.student_portal.actions.browse_scholarships", "Browse Scholarships"), self.show_scholarships),
            (get_text("financial_aid.student_portal.actions.recommendations", "Recommendations"), self.show_recommendations),
            (get_text("financial_aid.student_portal.actions.my_applications", "My Applications"), self.show_my_applications),
            (get_text("financial_aid.student_portal.actions.deadlines", "Deadlines"), self.show_deadlines),
            (get_text("financial_aid.student_portal.actions.documents", "Documents"), self.show_documents),
            (get_text("financial_aid.student_portal.actions.profile", "My Profile"), self.show_profile),
            (get_text("financial_aid.student_portal.actions.apply_financial_aid", "Apply for Financial Aid"), self.show_apply_aid),
            (get_text("financial_aid.student_portal.actions.my_awards", "My Awards"), self.show_my_awards)
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
        activity_frame = ttk.LabelFrame(self.parent_frame, text=get_text("financial_aid.student_portal.recent_activity", "Recent Activity"), padding=10)
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
                                           [get_text("financial_aid.student_portal.columns.type", "Type"),
                                            get_text("financial_aid.student_portal.columns.name", "Name"),
                                            get_text("financial_aid.student_portal.columns.date", "Date"),
                                            get_text("financial_aid.student_portal.columns.status", "Status")],
                                           {get_text("financial_aid.student_portal.columns.type", "Type"): 100,
                                            get_text("financial_aid.student_portal.columns.name", "Name"): 300,
                                            get_text("financial_aid.student_portal.columns.date", "Date"): 120,
                                            get_text("financial_aid.student_portal.columns.status", "Status"): 100})

                    for activity in activities:
                        tree.insert('', 'end', values=(
                            activity['type'].title(),
                            activity['name'],
                            format_date(activity['date']),
                            activity['status'].title()
                        ))
                else:
                    ttk.Label(activity_frame, text=get_text("financial_aid.student_portal.no_recent_activity", "No recent activity")).pack()

        except Exception as e:
            logger.error(f"Error loading activity: {e}")
            ttk.Label(activity_frame, text=get_text("financial_aid.student_portal.errors.loading_recent_activity", "Error loading recent activity"), foreground='red').pack()

    def show_scholarships(self):
        """Display available scholarships"""
        clear_frame(self.parent_frame)

        # Title
        title_frame = ttk.Frame(self.parent_frame)
        title_frame.pack(fill='x', padx=10, pady=10)
        ttk.Label(title_frame, text=get_text("financial_aid.student_portal.available_scholarships", "Available Scholarships"), style='Title.TLabel').pack(side='left')
        ttk.Button(title_frame, text=get_text("financial_aid.student_portal.buttons.back_to_dashboard", "Back to Dashboard"), command=self.show_dashboard).pack(side='right')

        # Search and filter
        search_entry, filter_combo = create_search_filter_bar(
            self.parent_frame,
            lambda: self._load_scholarships(search_entry.get(), filter_combo.get() if filter_combo else None),
            [get_text("financial_aid.student_portal.filters.all", "All"),
             get_text("financial_aid.student_portal.filters.merit_based", "Merit-Based"),
             get_text("financial_aid.student_portal.filters.need_based", "Need-Based"),
             get_text("financial_aid.student_portal.filters.athletic", "Athletic"),
             get_text("financial_aid.student_portal.filters.departmental", "Departmental")]
        )

        # Scholarships table
        table_frame = ttk.Frame(self.parent_frame)
        table_frame.pack(fill='both', expand=True, padx=10, pady=10)

        columns = [get_text("financial_aid.student_portal.columns.id", "ID"),
                   get_text("financial_aid.student_portal.columns.name", "Name"),
                   get_text("financial_aid.student_portal.columns.amount", "Amount"),
                   get_text("financial_aid.student_portal.columns.deadline", "Deadline"),
                   get_text("financial_aid.student_portal.columns.type", "Type"),
                   get_text("financial_aid.student_portal.columns.status", "Status")]
        self.scholarships_tree = create_data_table(table_frame, columns, {
            get_text("financial_aid.student_portal.columns.id", "ID"): 80,
            get_text("financial_aid.student_portal.columns.name", "Name"): 250,
            get_text("financial_aid.student_portal.columns.amount", "Amount"): 100,
            get_text("financial_aid.student_portal.columns.deadline", "Deadline"): 100,
            get_text("financial_aid.student_portal.columns.type", "Type"): 120,
            get_text("financial_aid.student_portal.columns.status", "Status"): 100
        })

        # Action buttons
        btn_frame = ttk.Frame(self.parent_frame)
        btn_frame.pack(fill='x', padx=10, pady=10)

        ttk.Button(btn_frame, text=get_text("financial_aid.student_portal.buttons.view_details", "View Details"), command=self._view_scholarship_details).pack(side='left', padx=5)
        ttk.Button(btn_frame, text=get_text("financial_aid.student_portal.buttons.apply", "Apply"), command=self._apply_for_scholarship, style='Success.TButton').pack(side='left', padx=5)

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
                sch_name = scholarship.get('scholarship_name', scholarship.get('name', ''))
                if search_term and search_term.lower() not in str(sch_name).lower():
                    continue
                if filter_type and filter_type != 'All':
                    # Would need criteria field to filter by type
                    pass

                # Check if already applied
                has_applied = self._check_application_exists(scholarship['scholarship_id'])
                status = get_text("financial_aid.student_portal.status.applied", "Applied") if has_applied else get_text("financial_aid.student_portal.status.available", "Available")

                self.scholarships_tree.insert('', 'end', values=(
                    scholarship['scholarship_id'],
                    scholarship.get('scholarship_name', scholarship.get('name', 'Unknown')),
                    format_currency(scholarship['amount']),
                    format_date(scholarship.get('deadline', 'N/A')),
                    str(scholarship.get('eligibility_criteria', scholarship.get('criteria', 'General')))[:20],
                    status
                ))

        except Exception as e:
            logger.error(f"Error loading scholarships: {e}")
            show_error(get_text("financial_aid.student_portal.errors.title", "Error"),
                      get_text("financial_aid.student_portal.errors.failed_load_scholarships", "Failed to load scholarships"))

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
        except Exception:
            return False

    def _view_scholarship_details(self):
        """View detailed scholarship information"""
        selection = self.scholarships_tree.selection()
        if not selection:
            show_warning(get_text("financial_aid.student_portal.warnings.selection_required_title", "Selection Required"),
                        get_text("financial_aid.student_portal.warnings.select_scholarship_view", "Please select a scholarship to view details"))
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
            show_error(get_text("financial_aid.student_portal.errors.title", "Error"),
                      get_text("financial_aid.student_portal.errors.failed_load_details", "Failed to load scholarship details"))

    def _show_scholarship_details_window(self, scholarship: Dict):
        """Show scholarship details in popup window"""
        details_window = tk.Toplevel(self.parent_frame)
        details_window.title(get_text("financial_aid.student_portal.scholarship_details_title", "Scholarship Details") + f" - {scholarship['scholarship_name']}")
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
            (get_text("financial_aid.student_portal.details.amount", "Amount"), format_currency(scholarship['amount'])),
            (get_text("financial_aid.student_portal.details.academic_year", "Academic Year"), scholarship.get('academic_year', 'N/A')),
            (get_text("financial_aid.student_portal.details.deadline", "Deadline"), format_date(scholarship.get('deadline', 'N/A'))),
            (get_text("financial_aid.student_portal.details.description", "Description"), scholarship.get('description', get_text("financial_aid.student_portal.details.no_description", "No description available"))),
            (get_text("financial_aid.student_portal.details.criteria", "Criteria"), scholarship.get('criteria', get_text("financial_aid.student_portal.details.see_office", "See financial aid office"))),
            (get_text("financial_aid.student_portal.details.status", "Status"), get_text("financial_aid.student_portal.status.active", "Active") if scholarship.get('is_active') else get_text("financial_aid.student_portal.status.inactive", "Inactive"))
        ]

        for label, value in details:
            frame = ttk.Frame(scrollable_frame)
            frame.pack(fill='x', padx=20, pady=5)
            ttk.Label(frame, text=f"{label}:", font=('Arial', 10, 'bold')).pack(anchor='w')
            ttk.Label(frame, text=str(value), wraplength=500).pack(anchor='w', padx=20)

        # Apply button
        ttk.Button(scrollable_frame, text=get_text("financial_aid.student_portal.buttons.apply_for_scholarship", "Apply for This Scholarship"),
                  command=lambda: [details_window.destroy(), self._apply_for_scholarship()],
                  style='Success.TButton').pack(pady=20)

    def _apply_for_scholarship(self):
        """Apply for selected scholarship"""
        selection = self.scholarships_tree.selection()
        if not selection:
            show_warning(get_text("financial_aid.student_portal.warnings.selection_required_title", "Selection Required"),
                        get_text("financial_aid.student_portal.warnings.select_scholarship_apply", "Please select a scholarship to apply for"))
            return

        item = self.scholarships_tree.item(selection[0])
        scholarship_id = item['values'][0]
        scholarship_name = item['values'][1]

        # Check if already applied
        if self._check_application_exists(scholarship_id):
            show_warning(get_text("financial_aid.student_portal.warnings.already_applied_title", "Already Applied"),
                        get_text("financial_aid.student_portal.warnings.already_applied_message", "You have already submitted an application for this scholarship"))
            return

        # Show application form
        self._show_application_form(scholarship_id, scholarship_name)

    def _show_application_form(self, scholarship_id: str, scholarship_name: str):
        """Show scholarship application form"""
        app_window = tk.Toplevel(self.parent_frame)
        app_window.title(get_text("financial_aid.student_portal.apply_for", "Apply for") + f" {scholarship_name}")
        app_window.geometry("700x600")

        # Title
        ttk.Label(app_window, text=get_text("financial_aid.student_portal.scholarship_application", "Scholarship Application"), style='Title.TLabel').pack(pady=10)
        ttk.Label(app_window, text=scholarship_name, font=('Arial', 12)).pack()

        # Create scrollable frame
        scrollable_frame, canvas, scrollbar = create_scrollable_frame(app_window)
        canvas.pack(side='left', fill='both', expand=True, padx=10, pady=10)
        scrollbar.pack(side='right', fill='y')

        # Application fields
        fields = {}

        # Essay
        ttk.Label(scrollable_frame, text=get_text("financial_aid.student_portal.form.personal_statement", "Personal Statement / Essay *"), font=('Arial', 10, 'bold')).pack(anchor='w', pady=(10, 5))
        essay_text = scrolledtext.ScrolledText(scrollable_frame, width=60, height=10)
        essay_text.pack(fill='x', pady=5)
        fields['essay'] = essay_text

        # GPA
        gpa_frame = ttk.Frame(scrollable_frame)
        gpa_frame.pack(fill='x', pady=10)
        ttk.Label(gpa_frame, text=get_text("financial_aid.student_portal.form.gpa", "GPA *"), font=('Arial', 10, 'bold')).pack(side='left')
        gpa_var = tk.StringVar()
        gpa_entry = ttk.Entry(gpa_frame, textvariable=gpa_var, width=10)
        gpa_entry.pack(side='left', padx=10)
        fields['gpa'] = gpa_var

        # Expected graduation
        grad_frame = ttk.Frame(scrollable_frame)
        grad_frame.pack(fill='x', pady=10)
        ttk.Label(grad_frame, text=get_text("financial_aid.student_portal.form.expected_graduation", "Expected Graduation *"), font=('Arial', 10, 'bold')).pack(side='left')
        grad_var = tk.StringVar()
        grad_entry = ttk.Entry(grad_frame, textvariable=grad_var, width=15)
        grad_entry.pack(side='left', padx=10)
        ttk.Label(grad_frame, text=get_text("financial_aid.student_portal.form.date_format", "(YYYY-MM-DD)"), foreground='gray').pack(side='left')
        fields['graduation'] = grad_var

        # References
        ttk.Label(scrollable_frame, text=get_text("financial_aid.student_portal.form.reference_name", "Reference Name"), font=('Arial', 10, 'bold')).pack(anchor='w', pady=(10, 5))
        ref_name_var = tk.StringVar()
        ttk.Entry(scrollable_frame, textvariable=ref_name_var, width=40).pack(fill='x', pady=5)
        fields['reference_name'] = ref_name_var

        ttk.Label(scrollable_frame, text=get_text("financial_aid.student_portal.form.reference_email", "Reference Email"), font=('Arial', 10, 'bold')).pack(anchor='w', pady=(10, 5))
        ref_email_var = tk.StringVar()
        ttk.Entry(scrollable_frame, textvariable=ref_email_var, width=40).pack(fill='x', pady=5)
        fields['reference_email'] = ref_email_var

        # Additional documents note
        ttk.Label(scrollable_frame, text="\n" + get_text("financial_aid.student_portal.form.documents_note", "Note: Transcripts and additional documents can be uploaded after submission."),
                 font=('Arial', 9), foreground='blue', wraplength=600).pack(pady=10)

        # Buttons
        btn_frame = ttk.Frame(scrollable_frame)
        btn_frame.pack(pady=20)

        def submit_application():
            if self._validate_and_submit_application(scholarship_id, fields, app_window):
                app_window.destroy()

        ttk.Button(btn_frame, text=get_text("financial_aid.student_portal.buttons.submit_application", "Submit Application"), command=submit_application,
                  style='Success.TButton').pack(side='left', padx=5)
        ttk.Button(btn_frame, text=get_text("financial_aid.student_portal.buttons.cancel", "Cancel"), command=app_window.destroy).pack(side='left', padx=5)

    def _validate_and_submit_application(self, scholarship_id: str, fields: Dict, window) -> bool:
        """Validate and submit scholarship application"""
        try:
            # Validate student ID
            if not self.student_id:
                show_error(get_text("financial_aid.student_portal.errors.student_id_not_found_title", "Student ID Not Found"),
                          get_text("financial_aid.student_portal.errors.student_id_not_found_message",
                                   "Unable to determine your student ID. Please ensure you are logged in as a student.\n\nIf you continue to see this error, contact the system administrator."))
                logger.error(f"Student ID is None for user: {self.current_user}")
                return False

            # Get values
            essay = fields['essay'].get('1.0', 'end-1c').strip()
            gpa = fields['gpa'].get().strip()
            graduation = fields['graduation'].get().strip()

            # Validate required fields
            if not essay:
                show_error(get_text("financial_aid.student_portal.validation.error_title", "Validation Error"),
                          get_text("financial_aid.student_portal.validation.essay_required", "Personal statement is required"))
                return False

            if not gpa:
                show_error(get_text("financial_aid.student_portal.validation.error_title", "Validation Error"),
                          get_text("financial_aid.student_portal.validation.gpa_required", "GPA is required"))
                return False

            try:
                gpa_float = float(gpa)
                if gpa_float < 0 or gpa_float > 4.0:
                    show_error(get_text("financial_aid.student_portal.validation.error_title", "Validation Error"),
                              get_text("financial_aid.student_portal.validation.gpa_range", "GPA must be between 0.0 and 4.0"))
                    return False
            except ValueError:
                show_error(get_text("financial_aid.student_portal.validation.error_title", "Validation Error"),
                          get_text("financial_aid.student_portal.validation.gpa_invalid", "Invalid GPA format"))
                return False

            if not graduation or not validate_date(graduation):
                show_error(get_text("financial_aid.student_portal.validation.error_title", "Validation Error"),
                          get_text("financial_aid.student_portal.validation.graduation_required", "Valid graduation date is required (YYYY-MM-DD)"))
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

                show_success(get_text("financial_aid.student_portal.success.title", "Success"),
                            get_text("financial_aid.student_portal.success.scholarship_submitted", "Your scholarship application has been submitted successfully!"))

                # Send confirmation email using template
                try:
                    user_dict = self.current_user.to_dict() if hasattr(self.current_user, 'to_dict') else self.current_user
                    email = user_dict.get('email')
                    student_name = f"{user_dict.get('first_name', '')} {user_dict.get('last_name', '')}".strip() or "Student"

                    if email:
                        subject, body = render_template('finance/scholarship_application_submitted', {
                            'student_name': student_name,
                            'scholarship_id': scholarship_id,
                            'scholarship_name': '',
                            'submission_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        })

                        # Fallback if template not found
                        if not subject or not body:
                            subject = "Scholarship Application Submitted"
                            body = f"Your application for scholarship ID {scholarship_id} has been submitted successfully."

                        send_email(
                            recipient_email=email,
                            subject=subject,
                            body=body
                        )
                except Exception as e:
                    logger.error(f"Failed to send confirmation email: {e}")

                # Refresh scholarships list
                self.show_scholarships()
                return True
            else:
                show_error(get_text("financial_aid.student_portal.errors.title", "Error"),
                          get_text("financial_aid.student_portal.errors.failed_submit_application", "Failed to submit application. Please try again."))
                return False

        except Exception as e:
            logger.error(f"Error submitting application: {e}")
            show_error(get_text("financial_aid.student_portal.errors.title", "Error"),
                      get_text("financial_aid.student_portal.errors.generic", "An error occurred:") + f" {str(e)}")
            return False

    def show_apply_aid(self):
        """Show financial aid application form"""
        clear_frame(self.parent_frame)

        # Title
        title_frame = ttk.Frame(self.parent_frame)
        title_frame.pack(fill='x', padx=10, pady=10)
        ttk.Label(title_frame, text=get_text("financial_aid.student_portal.apply_financial_aid_title", "Apply for Financial Aid"), style='Title.TLabel').pack(side='left')
        ttk.Button(title_frame, text=get_text("financial_aid.student_portal.buttons.back_to_dashboard", "Back to Dashboard"), command=self.show_dashboard).pack(side='right')

        # Check if student ID exists
        if not self.student_id:
            error_frame = ttk.Frame(self.parent_frame, relief='solid', borderwidth=2)
            error_frame.pack(fill='both', expand=True, padx=10, pady=10)
            ttk.Label(error_frame,
                     text=get_text("financial_aid.student_portal.errors.student_id_warning", "Student ID Not Found"),
                     font=('Arial', 14, 'bold'),
                     foreground='red').pack(pady=(20, 10))
            ttk.Label(error_frame,
                     text=get_text("financial_aid.student_portal.errors.student_id_explanation",
                                   "Unable to determine your student ID. This may occur if:\n\n- You are logged in as an admin or staff member (not a student)\n- Your student account has not been properly configured\n- There is a database issue with your user record\n\nPlease contact your system administrator for assistance."),
                     wraplength=600,
                     justify='left').pack(padx=20, pady=20)
            ttk.Button(error_frame, text=get_text("financial_aid.student_portal.buttons.back_to_dashboard", "Back to Dashboard"),
                      command=self.show_dashboard).pack(pady=20)
            logger.error(f"Student ID is None when accessing financial aid application. User: {self.current_user}")
            return

        # Info message
        info_frame = ttk.Frame(self.parent_frame, relief='solid', borderwidth=1)
        info_frame.pack(fill='x', padx=10, pady=10)
        ttk.Label(info_frame, text=get_text("financial_aid.student_portal.info.fafsa_note", "Complete this form to apply for financial aid. FAFSA data can be imported if available."),
                 foreground='blue', wraplength=700).pack(padx=10, pady=10)

        # Check existing application
        existing_app = self._check_existing_aid_application()
        if existing_app:
            ttk.Label(self.parent_frame,
                     text=get_text("financial_aid.student_portal.info.existing_application", "You have an existing application (Status: {status})").format(status=existing_app['status']),
                     font=('Arial', 11, 'bold'), foreground='orange').pack(pady=10)

        # Simple aid application form
        form_frame = ttk.LabelFrame(self.parent_frame, text=get_text("financial_aid.student_portal.financial_aid_application", "Financial Aid Application"), padding=20)
        form_frame.pack(fill='both', expand=True, padx=10, pady=10)

        fields = {}

        # Academic year
        year_frame = ttk.Frame(form_frame)
        year_frame.pack(fill='x', pady=10)
        ttk.Label(year_frame, text=get_text("financial_aid.student_portal.form.academic_year", "Academic Year:"), width=20).pack(side='left')
        year_var = tk.StringVar(value=get_current_academic_year())
        ttk.Combobox(year_frame, textvariable=year_var, values=get_academic_year_list(), state='readonly', width=15).pack(side='left')
        fields['academic_year'] = year_var

        # Aid type
        type_frame = ttk.Frame(form_frame)
        type_frame.pack(fill='x', pady=10)
        ttk.Label(type_frame, text=get_text("financial_aid.student_portal.form.aid_type", "Aid Type Requested:"), width=20).pack(side='left')
        type_var = tk.StringVar(value='Grant')
        ttk.Combobox(type_frame, textvariable=type_var, values=[
            get_text("financial_aid.student_portal.aid_types.grant", "Grant"),
            get_text("financial_aid.student_portal.aid_types.loan", "Loan"),
            get_text("financial_aid.student_portal.aid_types.work_study", "Work-Study"),
            get_text("financial_aid.student_portal.aid_types.emergency", "Emergency Aid")
        ], state='readonly', width=20).pack(side='left')
        fields['aid_type'] = type_var

        # Household income
        income_frame = ttk.Frame(form_frame)
        income_frame.pack(fill='x', pady=10)
        ttk.Label(income_frame, text=get_text("financial_aid.student_portal.form.household_income", "Household Income:"), width=20).pack(side='left')
        income_var = tk.StringVar()
        ttk.Entry(income_frame, textvariable=income_var, width=20).pack(side='left')
        ttk.Label(income_frame, text=get_text("financial_aid.student_portal.form.income_note", "(Annual, USD)"), foreground='gray').pack(side='left', padx=5)
        fields['income'] = income_var

        # Number of dependents
        dep_frame = ttk.Frame(form_frame)
        dep_frame.pack(fill='x', pady=10)
        ttk.Label(dep_frame, text=get_text("financial_aid.student_portal.form.dependents", "Number of Dependents:"), width=20).pack(side='left')
        dep_var = tk.StringVar(value='0')
        ttk.Spinbox(dep_frame, from_=0, to=10, textvariable=dep_var, width=10).pack(side='left')
        fields['dependents'] = dep_var

        # Additional information
        ttk.Label(form_frame, text=get_text("financial_aid.student_portal.form.additional_info", "Additional Information / Special Circumstances:"), font=('Arial', 10, 'bold')).pack(anchor='w', pady=(20, 5))
        info_text = scrolledtext.ScrolledText(form_frame, height=6, width=70)
        info_text.pack(fill='x', pady=5)
        fields['additional_info'] = info_text

        # Buttons
        btn_frame = ttk.Frame(form_frame)
        btn_frame.pack(pady=20)

        def submit_aid_application():
            if self._submit_aid_application(fields):
                self.show_dashboard()

        ttk.Button(btn_frame, text=get_text("financial_aid.student_portal.buttons.submit_application", "Submit Application"), command=submit_aid_application, style='Success.TButton').pack(side='left', padx=5)
        ttk.Button(btn_frame, text=get_text("financial_aid.student_portal.buttons.cancel", "Cancel"), command=self.show_dashboard).pack(side='left', padx=5)

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
                show_error(get_text("financial_aid.student_portal.errors.student_id_not_found_title", "Student ID Not Found"),
                          get_text("financial_aid.student_portal.errors.student_id_not_found_message",
                                   "Unable to determine your student ID. Please ensure you are logged in as a student.\n\nIf you continue to see this error, contact the system administrator."))
                logger.error(f"Student ID is None for user: {self.current_user}")
                return False

            # Validate income
            income_str = fields['income'].get().strip()
            if not income_str:
                show_error(get_text("financial_aid.student_portal.validation.error_title", "Validation Error"),
                          get_text("financial_aid.student_portal.validation.income_required", "Household income is required"))
                return False

            try:
                income = float(income_str.replace(',', ''))
            except ValueError:
                show_error(get_text("financial_aid.student_portal.validation.error_title", "Validation Error"),
                          get_text("financial_aid.student_portal.validation.income_invalid", "Invalid income format"))
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

                show_success(get_text("financial_aid.student_portal.success.title", "Success"),
                            get_text("financial_aid.student_portal.success.aid_submitted", "Your financial aid application has been submitted successfully!"))

                # Send confirmation email using template
                try:
                    user_dict = self.current_user.to_dict() if hasattr(self.current_user, 'to_dict') else self.current_user
                    email = user_dict.get('email')
                    student_name = f"{user_dict.get('first_name', '')} {user_dict.get('last_name', '')}".strip() or "Student"

                    if email:
                        subject, body = render_template('finance/financial_aid_application_submitted', {
                            'student_name': student_name,
                            'academic_year': app_data['academic_year'],
                            'submission_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        })

                        # Fallback if template not found
                        if not subject or not body:
                            subject = "Financial Aid Application Submitted"
                            body = f"Your financial aid application for {app_data['academic_year']} has been submitted."

                        send_email(
                            recipient_email=email,
                            subject=subject,
                            body=body
                        )
                except Exception as e:
                    logger.error(f"Failed to send confirmation email: {e}")

                return True
            else:
                show_error(get_text("financial_aid.student_portal.errors.title", "Error"),
                          get_text("financial_aid.student_portal.errors.failed_submit_application", "Failed to submit application"))
                return False

        except Exception as e:
            logger.error(f"Error submitting aid application: {e}")
            show_error(get_text("financial_aid.student_portal.errors.title", "Error"),
                      get_text("financial_aid.student_portal.errors.generic", "An error occurred:") + f" {str(e)}")
            return False

    def show_my_applications(self):
        """Show student's applications"""
        clear_frame(self.parent_frame)

        # Title
        title_frame = ttk.Frame(self.parent_frame)
        title_frame.pack(fill='x', padx=10, pady=10)
        ttk.Label(title_frame, text=get_text("financial_aid.student_portal.my_applications_title", "My Applications"), style='Title.TLabel').pack(side='left')
        ttk.Button(title_frame, text=get_text("financial_aid.student_portal.buttons.back_to_dashboard", "Back to Dashboard"), command=self.show_dashboard).pack(side='right')

        # Tabs for different application types
        notebook = ttk.Notebook(self.parent_frame)
        notebook.pack(fill='both', expand=True, padx=10, pady=10)

        # Scholarship applications tab
        scholarship_frame = ttk.Frame(notebook)
        notebook.add(scholarship_frame, text=get_text("financial_aid.student_portal.tabs.scholarship_applications", "Scholarship Applications"))
        self._show_scholarship_applications(scholarship_frame)

        # Financial aid applications tab
        aid_frame = ttk.Frame(notebook)
        notebook.add(aid_frame, text=get_text("financial_aid.student_portal.tabs.financial_aid_applications", "Financial Aid Applications"))
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
                    columns = [get_text("financial_aid.student_portal.columns.app_id", "App ID"),
                               get_text("financial_aid.student_portal.columns.scholarship", "Scholarship"),
                               get_text("financial_aid.student_portal.columns.amount", "Amount"),
                               get_text("financial_aid.student_portal.columns.submitted", "Submitted"),
                               get_text("financial_aid.student_portal.columns.status", "Status")]
                    tree = create_data_table(parent, columns, {
                        get_text("financial_aid.student_portal.columns.app_id", "App ID"): 80,
                        get_text("financial_aid.student_portal.columns.scholarship", "Scholarship"): 250,
                        get_text("financial_aid.student_portal.columns.amount", "Amount"): 100,
                        get_text("financial_aid.student_portal.columns.submitted", "Submitted"): 120,
                        get_text("financial_aid.student_portal.columns.status", "Status"): 100
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
                    ttk.Label(parent, text=get_text("financial_aid.student_portal.no_scholarship_applications", "No scholarship applications found")).pack(expand=True)

        except Exception as e:
            logger.error(f"Error loading scholarship applications: {e}")
            ttk.Label(parent, text=get_text("financial_aid.student_portal.errors.loading_applications", "Error loading applications"), foreground='red').pack()

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
                    columns = [get_text("financial_aid.student_portal.columns.aid_id", "Aid ID"),
                               get_text("financial_aid.student_portal.columns.type", "Type"),
                               get_text("financial_aid.student_portal.columns.awarded", "Awarded"),
                               get_text("financial_aid.student_portal.columns.disbursed", "Disbursed"),
                               get_text("financial_aid.student_portal.columns.status", "Status"),
                               get_text("financial_aid.student_portal.columns.applied", "Applied")]
                    tree = create_data_table(parent, columns, {
                        get_text("financial_aid.student_portal.columns.aid_id", "Aid ID"): 80,
                        get_text("financial_aid.student_portal.columns.type", "Type"): 150,
                        get_text("financial_aid.student_portal.columns.awarded", "Awarded"): 100,
                        get_text("financial_aid.student_portal.columns.disbursed", "Disbursed"): 100,
                        get_text("financial_aid.student_portal.columns.status", "Status"): 100,
                        get_text("financial_aid.student_portal.columns.applied", "Applied"): 120
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
                    ttk.Label(parent, text=get_text("financial_aid.student_portal.no_aid_applications", "No financial aid applications found")).pack(expand=True)

        except Exception as e:
            logger.error(f"Error loading aid applications: {e}")
            ttk.Label(parent, text=get_text("financial_aid.student_portal.errors.loading_applications", "Error loading applications"), foreground='red').pack()

    def show_my_awards(self):
        """Show student's awards"""
        clear_frame(self.parent_frame)

        # Title
        title_frame = ttk.Frame(self.parent_frame)
        title_frame.pack(fill='x', padx=10, pady=10)
        ttk.Label(title_frame, text=get_text("financial_aid.student_portal.my_awards_title", "My Awards"), style='Title.TLabel').pack(side='left')
        ttk.Button(title_frame, text=get_text("financial_aid.student_portal.buttons.back_to_dashboard", "Back to Dashboard"), command=self.show_dashboard).pack(side='right')

        # Summary stats
        stats_frame = ttk.LabelFrame(self.parent_frame, text=get_text("financial_aid.student_portal.award_summary", "Award Summary"), padding=10)
        stats_frame.pack(fill='x', padx=10, pady=10)

        try:
            stats = self._get_award_stats()

            summary_text = f"""
{get_text("financial_aid.student_portal.summary.total_awards", "Total Awards")}: {format_currency(stats['total_awarded'])}
{get_text("financial_aid.student_portal.summary.total_disbursed", "Total Disbursed")}: {format_currency(stats['total_disbursed'])}
{get_text("financial_aid.student_portal.summary.remaining", "Remaining")}: {format_currency(stats['remaining'])}
{get_text("financial_aid.student_portal.summary.active_awards", "Active Awards")}: {stats['active_count']}
            """
            ttk.Label(stats_frame, text=summary_text, font=('Arial', 10)).pack()

        except Exception as e:
            logger.error(f"Error loading award stats: {e}")
            ttk.Label(stats_frame, text=get_text("financial_aid.student_portal.errors.loading_statistics", "Error loading statistics"), foreground='red').pack()

        # Awards table
        table_frame = ttk.Frame(self.parent_frame)
        table_frame.pack(fill='both', expand=True, padx=10, pady=10)

        columns = [get_text("financial_aid.student_portal.columns.award_id", "Award ID"),
                   get_text("financial_aid.student_portal.columns.type", "Type"),
                   get_text("financial_aid.student_portal.columns.name", "Name"),
                   get_text("financial_aid.student_portal.columns.amount", "Amount"),
                   get_text("financial_aid.student_portal.columns.awarded_date", "Awarded Date"),
                   get_text("financial_aid.student_portal.columns.status", "Status")]
        tree = create_data_table(table_frame, columns, {
            get_text("financial_aid.student_portal.columns.award_id", "Award ID"): 80,
            get_text("financial_aid.student_portal.columns.type", "Type"): 100,
            get_text("financial_aid.student_portal.columns.name", "Name"): 200,
            get_text("financial_aid.student_portal.columns.amount", "Amount"): 100,
            get_text("financial_aid.student_portal.columns.awarded_date", "Awarded Date"): 120,
            get_text("financial_aid.student_portal.columns.status", "Status"): 100
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
                        award['name'] or get_text("financial_aid.student_portal.general_aid", "General Aid"),
                        format_currency(award['awarded_amount']),
                        format_date(award['approval_date']),
                        award['status'].title()
                    ))

        except Exception as e:
            logger.error(f"Error loading awards: {e}")
            show_error(get_text("financial_aid.student_portal.errors.title", "Error"),
                      get_text("financial_aid.student_portal.errors.failed_load_awards", "Failed to load awards"))

    # ========== ADVANCED SCHOLARSHIP FINDER FEATURES ==========

    def show_recommendations(self):
        """Display personalized scholarship recommendations"""
        clear_frame(self.parent_frame)

        # Title
        title_frame = ttk.Frame(self.parent_frame)
        title_frame.pack(fill='x', padx=10, pady=10)
        ttk.Label(title_frame, text="Personalized Scholarship Recommendations", style='Title.TLabel').pack(side='left')
        ttk.Button(title_frame, text="Back to Dashboard", command=self.show_dashboard).pack(side='right')

        # Control buttons
        button_frame = ttk.Frame(self.parent_frame)
        button_frame.pack(pady=10)

        ttk.Button(button_frame, text="Generate New Recommendations",
                  command=self._generate_recommendations).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Refresh", command=self._load_recommendations).pack(side='left', padx=5)

        # Recommendations table
        table_frame = ttk.Frame(self.parent_frame)
        table_frame.pack(fill='both', expand=True, padx=10, pady=10)

        columns = ['Name', 'Award', 'Deadline', 'Match Score', 'Priority', 'Eligibility']
        self.rec_tree = create_data_table(table_frame, columns, {
            'Name': 250, 'Award': 120, 'Deadline': 100,
            'Match Score': 80, 'Priority': 80, 'Eligibility': 120
        })

        # Details panel
        details_frame = ttk.LabelFrame(self.parent_frame, text="Recommendation Details", padding=10)
        details_frame.pack(fill='both', expand=True, padx=10, pady=10)

        self.rec_details_text = scrolledtext.ScrolledText(details_frame, wrap=tk.WORD, height=10)
        self.rec_details_text.pack(fill='both', expand=True)

        # Action buttons
        btn_frame = ttk.Frame(self.parent_frame)
        btn_frame.pack(fill='x', padx=10, pady=10)

        ttk.Button(btn_frame, text="Start Application",
                  command=self._start_application_from_rec, style='Success.TButton').pack(side='left', padx=5)
        ttk.Button(btn_frame, text="View Full Details",
                  command=self._view_rec_details).pack(side='left', padx=5)

        # Bind selection
        self.rec_tree.bind('<<TreeviewSelect>>', self._on_rec_selection)

        # Load recommendations
        self._load_recommendations()

    def _load_recommendations(self):
        """Load and display recommendations"""
        try:
            # Clear tree
            for item in self.rec_tree.get_children():
                self.rec_tree.delete(item)

            from university_system.modules.domain.scholarship_finder.services.scholarship_service import RecommendationEngine

            recommendations = RecommendationEngine.get_cached_recommendations(self.student_id)

            if not recommendations:
                show_warning("No Recommendations",
                           "No recommendations found. Click 'Generate New Recommendations'.")
                return

            for rec in recommendations:
                award_range = f"${rec['award_amount_min']:,.0f}"
                if rec.get('award_amount_max'):
                    award_range += f"-${rec['award_amount_max']:,.0f}"

                self.rec_tree.insert('', 'end', values=(
                    rec['scholarship_name'][:40],
                    award_range,
                    format_date(rec['application_deadline']),
                    f"{rec['match_score']:.0f}%",
                    rec['priority_level'].upper(),
                    rec['eligibility_status']
                ), tags=(str(rec['scholarship_id']), str(rec['match_score'])))

            # Color code by priority
            for item in self.rec_tree.get_children():
                values = self.rec_tree.item(item)['values']
                if 'HIGH' in str(values):
                    self.rec_tree.item(item, tags=('high',))
                elif 'MEDIUM' in str(values):
                    self.rec_tree.item(item, tags=('medium',))

            self.rec_tree.tag_configure('high', background='#d4edda')
            self.rec_tree.tag_configure('medium', background='#fff3cd')

        except Exception as e:
            logger.error(f"Error loading recommendations: {e}")
            show_error("Error", f"Failed to load recommendations: {e}")

    def _generate_recommendations(self):
        """Generate new recommendations"""
        from tkinter import messagebox
        if messagebox.askyesno("Confirm", "Generate new personalized recommendations?\n\nThis will analyze your profile and find matching scholarships."):
            try:
                from university_system.modules.domain.scholarship_finder.services.scholarship_service import RecommendationEngine

                recommendations = RecommendationEngine.generate_recommendations(self.student_id, limit=20)

                if recommendations:
                    show_success("Success", f"Generated {len(recommendations)} recommendations!")
                    self._load_recommendations()
                else:
                    show_warning("Warning",
                               "Could not generate recommendations.\n\nPlease complete your profile in the Profile tab.")

            except Exception as e:
                logger.error(f"Error generating recommendations: {e}")
                show_error("Error", f"Failed to generate recommendations: {e}")

    def _on_rec_selection(self, event):
        """Handle recommendation selection"""
        selection = self.rec_tree.selection()
        if not selection:
            return

        try:
            tags = self.rec_tree.item(selection[0])['tags']
            if tags:
                scholarship_id = int(tags[0])
                from university_system.modules.domain.scholarship_finder.services.scholarship_service import ScholarshipDatabase
                scholarship = ScholarshipDatabase.get_scholarship_details(scholarship_id)
                if scholarship:
                    self._display_recommendation_details(scholarship, tags)
        except Exception as e:
            logger.error(f"Error on selection: {e}")

    def _display_recommendation_details(self, scholarship: dict, tags: tuple):
        """Display recommendation details"""
        self.rec_details_text.delete('1.0', tk.END)

        self.rec_details_text.insert(tk.END, f"{scholarship['scholarship_name']}\n", 'title')
        self.rec_details_text.tag_config('title', font=('Arial', 12, 'bold'))

        if len(tags) > 1:
            self.rec_details_text.insert(tk.END, f"\nMatch Score: {tags[1]}%\n", 'score')
            self.rec_details_text.tag_config('score', foreground='green', font=('Arial', 10, 'bold'))

        self.rec_details_text.insert(tk.END, f"\nOrganization: {scholarship['organization']}\n")

        award_range = f"${scholarship['award_amount_min']:,.0f}"
        if scholarship.get('award_amount_max'):
            award_range += f" - ${scholarship['award_amount_max']:,.0f}"
        self.rec_details_text.insert(tk.END, f"Award: {award_range}\n")

        self.rec_details_text.insert(tk.END, f"Deadline: {scholarship['application_deadline']}\n\n")
        self.rec_details_text.insert(tk.END, f"{scholarship['description']}\n\n")

        self.rec_details_text.insert(tk.END, "Requirements:\n", 'subtitle')
        self.rec_details_text.tag_config('subtitle', font=('Arial', 10, 'bold'))

        if scholarship.get('min_gpa'):
            self.rec_details_text.insert(tk.END, f"  • Min GPA: {scholarship['min_gpa']}\n")
        if scholarship.get('essay_required'):
            self.rec_details_text.insert(tk.END, "  • Essay required\n")
        if scholarship.get('recommendation_letters_required'):
            self.rec_details_text.insert(tk.END,
                f"  • {scholarship['recommendation_letters_required']} recommendation letters\n")

    def _start_application_from_rec(self):
        """Start application from recommendation"""
        selection = self.rec_tree.selection()
        if not selection:
            show_warning("Warning", "Please select a recommendation.")
            return

        try:
            tags = self.rec_tree.item(selection[0])['tags']
            if not tags:
                return

            scholarship_id = int(tags[0])
            match_score = float(tags[1]) if len(tags) > 1 else None

            from tkinter import messagebox
            if messagebox.askyesno("Confirm", "Start application for this scholarship?"):
                from university_system.modules.domain.scholarship_finder.services.scholarship_service import ApplicationManager

                app_id = ApplicationManager.start_application(self.student_id, scholarship_id, match_score)
                show_success("Success", f"Application started! ID: {app_id}")
                self.show_my_applications()

        except Exception as e:
            logger.error(f"Error starting application: {e}")
            show_error("Error", f"Failed to start application: {e}")

    def _view_rec_details(self):
        """View full details from recommendation"""
        selection = self.rec_tree.selection()
        if not selection:
            show_warning("Warning", "Please select a recommendation.")
            return

        tags = self.rec_tree.item(selection[0])['tags']
        if tags:
            scholarship_id = int(tags[0])
            self._show_scholarship_details_dialog(scholarship_id)

    def show_deadlines(self):
        """Display upcoming deadlines calendar"""
        clear_frame(self.parent_frame)

        # Title
        title_frame = ttk.Frame(self.parent_frame)
        title_frame.pack(fill='x', padx=10, pady=10)
        ttk.Label(title_frame, text="Upcoming Deadlines", style='Title.TLabel').pack(side='left')
        ttk.Button(title_frame, text="Back to Dashboard", command=self.show_dashboard).pack(side='right')

        # Control frame
        control_frame = ttk.Frame(self.parent_frame)
        control_frame.pack(pady=10)

        ttk.Label(control_frame, text="Show deadlines within:").pack(side='left', padx=5)
        self.deadline_days_var = tk.StringVar(value="14")
        ttk.Entry(control_frame, textvariable=self.deadline_days_var, width=10).pack(side='left', padx=5)
        ttk.Label(control_frame, text="days").pack(side='left', padx=5)

        ttk.Button(control_frame, text="Refresh", command=self._load_deadlines).pack(side='left', padx=10)

        # Deadlines table
        table_frame = ttk.Frame(self.parent_frame)
        table_frame.pack(fill='both', expand=True, padx=10, pady=10)

        columns = ['Scholarship', 'Deadline', 'Days Left', 'Status', 'Progress', 'Urgency']
        self.deadline_tree = create_data_table(table_frame, columns, {
            'Scholarship': 300, 'Deadline': 120, 'Days Left': 100,
            'Status': 120, 'Progress': 150, 'Urgency': 100
        })

        # Load deadlines
        self._load_deadlines()

    def _load_deadlines(self):
        """Load and display upcoming deadlines"""
        try:
            # Clear tree
            for item in self.deadline_tree.get_children():
                self.deadline_tree.delete(item)

            days = int(self.deadline_days_var.get().strip())

            from university_system.modules.domain.scholarship_finder.services.scholarship_service import ApplicationManager

            deadlines = ApplicationManager.get_upcoming_deadlines(self.student_id, days)

            for app in deadlines:
                deadline = datetime.strptime(app['deadline_date'], '%Y-%m-%d')
                days_left = (deadline - datetime.now()).days

                if days_left <= 3:
                    urgency = "URGENT!"
                elif days_left <= 7:
                    urgency = "Soon"
                else:
                    urgency = "Upcoming"

                progress = app.get('application_progress', 0)
                progress_bar = "█" * int(progress / 10) + "░" * (10 - int(progress / 10))

                self.deadline_tree.insert('', 'end', values=(
                    app['scholarship_name'][:45],
                    app['deadline_date'],
                    f"{days_left} days",
                    app['status'].upper(),
                    f"{progress_bar} {progress:.0f}%",
                    urgency
                ))

            # Color code by urgency
            for item in self.deadline_tree.get_children():
                values = self.deadline_tree.item(item)['values']
                urgency = values[5]
                if urgency == "URGENT!":
                    self.deadline_tree.item(item, tags=('urgent',))
                elif urgency == "Soon":
                    self.deadline_tree.item(item, tags=('soon',))

            self.deadline_tree.tag_configure('urgent', background='#f8d7da', foreground='darkred')
            self.deadline_tree.tag_configure('soon', background='#fff3cd')

        except Exception as e:
            logger.error(f"Error loading deadlines: {e}")
            show_error("Error", f"Failed to load deadlines: {e}")

    def show_documents(self):
        """Display document vault"""
        clear_frame(self.parent_frame)

        # Title
        title_frame = ttk.Frame(self.parent_frame)
        title_frame.pack(fill='x', padx=10, pady=10)
        ttk.Label(title_frame, text="Document Vault", style='Title.TLabel').pack(side='left')
        ttk.Button(title_frame, text="Back to Dashboard", command=self.show_dashboard).pack(side='right')

        # Control frame
        control_frame = ttk.Frame(self.parent_frame)
        control_frame.pack(pady=10)

        ttk.Label(control_frame, text="Filter by Type:").pack(side='left', padx=5)
        self.doc_type_var = tk.StringVar(value="All")
        doc_types = ['All', 'Essay', 'Transcript', 'Resume', 'Recommendation', 'Financial Document',
                     'Certificate', 'Portfolio', 'Other']
        ttk.Combobox(control_frame, textvariable=self.doc_type_var, values=doc_types,
                    width=15, state='readonly').pack(side='left', padx=5)

        ttk.Button(control_frame, text="Filter", command=self._load_documents).pack(side='left', padx=10)
        ttk.Button(control_frame, text="Upload New", command=self._upload_document_dialog).pack(side='left', padx=5)
        ttk.Button(control_frame, text="Refresh", command=self._load_documents).pack(side='left', padx=5)

        # Documents table
        table_frame = ttk.Frame(self.parent_frame)
        table_frame.pack(fill='both', expand=True, padx=10, pady=10)

        columns = ['ID', 'Name', 'Type', 'Upload Date', 'File Path', 'Usage']
        self.doc_tree = create_data_table(table_frame, columns, {
            'ID': 50, 'Name': 250, 'Type': 150,
            'Upload Date': 120, 'File Path': 300, 'Usage': 80
        })

        # Load documents
        self._load_documents()

    def _load_documents(self):
        """Load and display documents"""
        try:
            # Clear tree
            for item in self.doc_tree.get_children():
                self.doc_tree.delete(item)

            doc_type = self.doc_type_var.get()
            doc_type_filter = None if doc_type == "All" else doc_type.lower().replace(' ', '-')

            from university_system.modules.domain.scholarship_finder.services.scholarship_service import DocumentVaultManager

            documents = DocumentVaultManager.get_student_documents(self.student_id, doc_type_filter)

            for doc in documents:
                file_path = doc.get('file_path', '')
                file_display = file_path[:50] + '...' if len(file_path) > 50 else file_path

                self.doc_tree.insert('', 'end', values=(
                    doc['document_id'],
                    doc['document_name'],
                    doc['document_type'],
                    format_date(doc['upload_date']),
                    file_display,
                    f"{doc.get('usage_count', 0)} times"
                ))

        except Exception as e:
            logger.error(f"Error loading documents: {e}")
            show_error("Error", f"Failed to load documents: {e}")

    def _upload_document_dialog(self):
        """Open dialog to upload document"""
        from tkinter import filedialog

        dialog = tk.Toplevel(self.parent_frame)
        dialog.title("Upload Document")
        dialog.geometry("500x400")

        ttk.Label(dialog, text="Upload Document", font=('Arial', 14, 'bold')).pack(pady=10)

        # Document type
        ttk.Label(dialog, text="Document Type:").pack(pady=5)
        doc_type_var = tk.StringVar()
        doc_types = ['essay', 'transcript', 'resume', 'recommendation', 'financial-document',
                     'certificate', 'portfolio', 'other']
        type_combo = ttk.Combobox(dialog, textvariable=doc_type_var, values=doc_types, state='readonly')
        type_combo.pack(pady=5)
        type_combo.current(0)

        # Document name
        ttk.Label(dialog, text="Document Name:").pack(pady=5)
        name_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=name_var, width=40).pack(pady=5)

        # File path
        ttk.Label(dialog, text="File Path:").pack(pady=5)
        path_frame = ttk.Frame(dialog)
        path_frame.pack(pady=5)
        path_var = tk.StringVar()
        ttk.Entry(path_frame, textvariable=path_var, width=35).pack(side='left', padx=5)

        def browse_file():
            filename = filedialog.askopenfilename()
            if filename:
                path_var.set(filename)

        ttk.Button(path_frame, text="Browse", command=browse_file).pack(side='left')

        # Description
        ttk.Label(dialog, text="Description (optional):").pack(pady=5)
        desc_text = scrolledtext.ScrolledText(dialog, wrap=tk.WORD, height=5)
        desc_text.pack(fill='both', expand=True, padx=20, pady=5)

        # Tags
        ttk.Label(dialog, text="Tags (comma-separated):").pack(pady=5)
        tags_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=tags_var, width=40).pack(pady=5)

        # Buttons
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=15)

        def save_document():
            doc_type = doc_type_var.get()
            name = name_var.get().strip()
            path = path_var.get().strip()

            if not name or not path:
                show_error("Error", "Name and file path are required.")
                return

            # Security: Validate file before upload
            if SECURE_UPLOAD_AVAILABLE and validate_upload and os.path.exists(path):
                try:
                    with open(path, 'rb') as f:
                        file_content = f.read()
                    original_filename = os.path.basename(path)
                    validation = validate_upload(original_filename, file_content, category='documents')
                    if not validation['valid']:
                        show_error(
                            "Security Error",
                            f"File validation failed: {validation['error']}"
                        )
                        log_activity(
                            'security_blocked',
                            'financial_aid_document',
                            student_id=self.student_id,
                            filename=original_filename,
                            reason=validation['error']
                        )
                        return
                except Exception as e:
                    logger.warning(f"File validation warning: {e}")

            description = desc_text.get('1.0', tk.END).strip()
            tags = tags_var.get().strip()

            try:
                from university_system.modules.domain.scholarship_finder.services.scholarship_service import DocumentVaultManager

                doc_id = DocumentVaultManager.upload_document(
                    self.student_id, name, doc_type, path,
                    description=description, tags=tags
                )
                show_success("Success", f"Document uploaded! ID: {doc_id}")
                dialog.destroy()
                self._load_documents()

            except Exception as e:
                show_error("Error", f"Failed to upload document: {e}")

        ttk.Button(button_frame, text="Upload", command=save_document).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='left', padx=5)

    def show_profile(self):
        """Display student profile management"""
        clear_frame(self.parent_frame)

        # Title
        title_frame = ttk.Frame(self.parent_frame)
        title_frame.pack(fill='x', padx=10, pady=10)
        ttk.Label(title_frame, text="Scholarship Profile", style='Title.TLabel').pack(side='left')
        ttk.Button(title_frame, text="Back to Dashboard", command=self.show_dashboard).pack(side='right')

        # Profile completeness
        try:
            from university_system.modules.domain.scholarship_finder.services.scholarship_service import StudentProfileManager

            profile = StudentProfileManager.get_student_profile(self.student_id) or {}
            completeness = profile.get('profile_completeness', 0)

            completeness_frame = ttk.Frame(self.parent_frame)
            completeness_frame.pack(pady=10)

            ttk.Label(completeness_frame, text=f"Profile Completeness: {completeness:.1f}%",
                     font=('Arial', 12, 'bold')).pack()

            progress_bar = ttk.Progressbar(completeness_frame, length=400, mode='determinate')
            progress_bar['value'] = completeness
            progress_bar.pack(pady=5)

        except Exception as e:
            logger.error(f"Error loading profile: {e}")
            profile = {}
            ttk.Label(self.parent_frame, text="Profile not created yet", font=('Arial', 12)).pack(pady=10)

        # Profile notebook
        profile_notebook = ttk.Notebook(self.parent_frame)
        profile_notebook.pack(fill='both', expand=True, padx=10, pady=10)

        # Create profile tabs
        self._create_basic_info_tab(profile_notebook, profile)
        self._create_academic_info_tab(profile_notebook, profile)
        self._create_activities_tab(profile_notebook, profile)
        self._create_preferences_tab(profile_notebook, profile)

    def _create_basic_info_tab(self, parent, profile):
        """Create basic information tab"""
        tab = ttk.Frame(parent, padding=20)
        parent.add(tab, text="Basic Info")

        form_frame = ttk.Frame(tab)
        form_frame.pack(fill='both', expand=True)

        # Citizenship
        ttk.Label(form_frame, text="Citizenship Status:").grid(row=0, column=0, sticky='w', pady=5)
        self.citizenship_var = tk.StringVar(value=profile.get('citizenship_status', ''))
        ttk.Entry(form_frame, textvariable=self.citizenship_var, width=30).grid(row=0, column=1, pady=5)

        # State residency
        ttk.Label(form_frame, text="State Residency:").grid(row=1, column=0, sticky='w', pady=5)
        self.state_var = tk.StringVar(value=profile.get('state_residency', ''))
        ttk.Entry(form_frame, textvariable=self.state_var, width=30).grid(row=1, column=1, pady=5)

        # Ethnicity
        ttk.Label(form_frame, text="Ethnicity:").grid(row=2, column=0, sticky='w', pady=5)
        self.ethnicity_var = tk.StringVar(value=profile.get('ethnicity', ''))
        ttk.Entry(form_frame, textvariable=self.ethnicity_var, width=30).grid(row=2, column=1, pady=5)

        # Gender
        ttk.Label(form_frame, text="Gender:").grid(row=3, column=0, sticky='w', pady=5)
        self.gender_var = tk.StringVar(value=profile.get('gender', ''))
        ttk.Entry(form_frame, textvariable=self.gender_var, width=30).grid(row=3, column=1, pady=5)

        # First generation
        self.first_gen_var = tk.BooleanVar(value=bool(profile.get('first_generation', 0)))
        ttk.Checkbutton(form_frame, text="First Generation College Student",
                       variable=self.first_gen_var).grid(row=4, column=0, columnspan=2, sticky='w', pady=5)

        # Military affiliation
        ttk.Label(form_frame, text="Military Affiliation:").grid(row=5, column=0, sticky='w', pady=5)
        self.military_var = tk.StringVar(value=profile.get('military_affiliation', ''))
        ttk.Entry(form_frame, textvariable=self.military_var, width=30).grid(row=5, column=1, pady=5)

        # Save button
        ttk.Button(form_frame, text="Save Basic Info",
                  command=self._save_basic_info, style='Success.TButton').grid(row=6, column=0, columnspan=2, pady=20)

    def _create_academic_info_tab(self, parent, profile):
        """Create academic information tab"""
        tab = ttk.Frame(parent, padding=20)
        parent.add(tab, text="Academic & Career")

        form_frame = ttk.Frame(tab)
        form_frame.pack(fill='both', expand=True)

        # Financial need
        ttk.Label(form_frame, text="Financial Need Level:").grid(row=0, column=0, sticky='w', pady=5)
        self.financial_need_var = tk.StringVar(value=profile.get('financial_need_level', 'none'))
        needs = ['none', 'low', 'moderate', 'high', 'exceptional']
        ttk.Combobox(form_frame, textvariable=self.financial_need_var, values=needs,
                    state='readonly', width=28).grid(row=0, column=1, pady=5)

        # Career field
        ttk.Label(form_frame, text="Intended Career Field:").grid(row=1, column=0, sticky='w', pady=5)
        self.career_var = tk.StringVar(value=profile.get('intended_career_field', ''))
        ttk.Entry(form_frame, textvariable=self.career_var, width=30).grid(row=1, column=1, pady=5)

        # Save button
        ttk.Button(form_frame, text="Save Academic Info",
                  command=self._save_academic_info, style='Success.TButton').grid(row=2, column=0, columnspan=2, pady=20)

    def _create_activities_tab(self, parent, profile):
        """Create activities and achievements tab"""
        tab = ttk.Frame(parent, padding=20)
        parent.add(tab, text="Activities")

        form_frame = ttk.Frame(tab)
        form_frame.pack(fill='both', expand=True)

        # Community service hours
        ttk.Label(form_frame, text="Community Service Hours:").grid(row=0, column=0, sticky='w', pady=5)
        self.service_hours_var = tk.StringVar(value=str(profile.get('community_service_hours', 0)))
        ttk.Entry(form_frame, textvariable=self.service_hours_var, width=30).grid(row=0, column=1, pady=5)

        # Leadership positions
        ttk.Label(form_frame, text="Leadership Positions:").grid(row=1, column=0, sticky='w', pady=5)
        self.leadership_var = tk.StringVar(value=profile.get('leadership_positions', ''))
        ttk.Entry(form_frame, textvariable=self.leadership_var, width=30).grid(row=1, column=1, pady=5)

        # Academic honors
        ttk.Label(form_frame, text="Academic Honors:").grid(row=2, column=0, sticky='w', pady=5)
        self.honors_var = tk.StringVar(value=profile.get('academic_honors', ''))
        ttk.Entry(form_frame, textvariable=self.honors_var, width=30).grid(row=2, column=1, pady=5)

        # Extracurriculars
        ttk.Label(form_frame, text="Extracurricular Activities:").grid(row=3, column=0, sticky='w', pady=5)
        self.activities_var = tk.StringVar(value=profile.get('extracurricular_activities', ''))
        ttk.Entry(form_frame, textvariable=self.activities_var, width=30).grid(row=3, column=1, pady=5)

        # Special talents
        ttk.Label(form_frame, text="Special Talents:").grid(row=4, column=0, sticky='w', pady=5)
        self.talents_var = tk.StringVar(value=profile.get('special_talents', ''))
        ttk.Entry(form_frame, textvariable=self.talents_var, width=30).grid(row=4, column=1, pady=5)

        # Languages
        ttk.Label(form_frame, text="Languages Spoken:").grid(row=5, column=0, sticky='w', pady=5)
        self.languages_var = tk.StringVar(value=profile.get('languages_spoken', ''))
        ttk.Entry(form_frame, textvariable=self.languages_var, width=30).grid(row=5, column=1, pady=5)

        # Study abroad interest
        self.study_abroad_var = tk.BooleanVar(value=bool(profile.get('study_abroad_interest', 0)))
        ttk.Checkbutton(form_frame, text="Interested in Study Abroad",
                       variable=self.study_abroad_var).grid(row=6, column=0, columnspan=2, sticky='w', pady=5)

        # Research interest
        self.research_var = tk.BooleanVar(value=bool(profile.get('research_interest', 0)))
        ttk.Checkbutton(form_frame, text="Interested in Research",
                       variable=self.research_var).grid(row=7, column=0, columnspan=2, sticky='w', pady=5)

        # Save button
        ttk.Button(form_frame, text="Save Activities",
                  command=self._save_activities, style='Success.TButton').grid(row=8, column=0, columnspan=2, pady=20)

    def _create_preferences_tab(self, parent, profile):
        """Create preferences tab"""
        tab = ttk.Frame(parent, padding=20)
        parent.add(tab, text="Preferences")

        form_frame = ttk.Frame(tab)
        form_frame.pack(fill='both', expand=True)

        # Preferred scholarship types
        ttk.Label(form_frame, text="Preferred Scholarship Types:").grid(row=0, column=0, sticky='w', pady=5)
        self.pref_types_var = tk.StringVar(value=profile.get('preferred_scholarship_types', ''))
        ttk.Entry(form_frame, textvariable=self.pref_types_var, width=30).grid(row=0, column=1, pady=5)

        # Minimum award amount
        ttk.Label(form_frame, text="Minimum Award Amount ($):").grid(row=1, column=0, sticky='w', pady=5)
        self.min_award_pref_var = tk.StringVar(value=str(profile.get('minimum_award_amount', 0)))
        ttk.Entry(form_frame, textvariable=self.min_award_pref_var, width=30).grid(row=1, column=1, pady=5)

        # Willing to write essays
        self.essays_var = tk.BooleanVar(value=bool(profile.get('willing_to_write_essays', 1)))
        ttk.Checkbutton(form_frame, text="Willing to Write Essays",
                       variable=self.essays_var).grid(row=2, column=0, columnspan=2, sticky='w', pady=5)

        # Max recommendation letters
        ttk.Label(form_frame, text="Max Recommendation Letters:").grid(row=3, column=0, sticky='w', pady=5)
        self.max_letters_var = tk.StringVar(value=str(profile.get('max_recommendation_letters', 3)))
        ttk.Entry(form_frame, textvariable=self.max_letters_var, width=30).grid(row=3, column=1, pady=5)

        # Save button
        ttk.Button(form_frame, text="Save Preferences",
                  command=self._save_preferences, style='Success.TButton').grid(row=4, column=0, columnspan=2, pady=20)

    def _save_basic_info(self):
        """Save basic information"""
        try:
            from university_system.modules.domain.scholarship_finder.services.scholarship_service import StudentProfileManager

            profile_data = {
                'citizenship_status': self.citizenship_var.get().strip(),
                'state_residency': self.state_var.get().strip(),
                'ethnicity': self.ethnicity_var.get().strip(),
                'gender': self.gender_var.get().strip(),
                'first_generation': 1 if self.first_gen_var.get() else 0,
                'military_affiliation': self.military_var.get().strip()
            }

            StudentProfileManager.create_or_update_profile(self.student_id, **profile_data)
            show_success("Success", "Basic information saved!")

        except Exception as e:
            logger.error(f"Error saving profile: {e}")
            show_error("Error", f"Failed to save profile: {e}")

    def _save_academic_info(self):
        """Save academic information"""
        try:
            from university_system.modules.domain.scholarship_finder.services.scholarship_service import StudentProfileManager

            profile_data = {
                'financial_need_level': self.financial_need_var.get(),
                'intended_career_field': self.career_var.get().strip()
            }

            StudentProfileManager.create_or_update_profile(self.student_id, **profile_data)
            show_success("Success", "Academic information saved!")

        except Exception as e:
            logger.error(f"Error saving profile: {e}")
            show_error("Error", f"Failed to save profile: {e}")

    def _save_activities(self):
        """Save activities information"""
        try:
            from university_system.modules.domain.scholarship_finder.services.scholarship_service import StudentProfileManager

            service_hours = int(self.service_hours_var.get().strip()) if self.service_hours_var.get().strip() else 0

            profile_data = {
                'community_service_hours': service_hours,
                'leadership_positions': self.leadership_var.get().strip(),
                'academic_honors': self.honors_var.get().strip(),
                'extracurricular_activities': self.activities_var.get().strip(),
                'special_talents': self.talents_var.get().strip(),
                'languages_spoken': self.languages_var.get().strip(),
                'study_abroad_interest': 1 if self.study_abroad_var.get() else 0,
                'research_interest': 1 if self.research_var.get() else 0
            }

            StudentProfileManager.create_or_update_profile(self.student_id, **profile_data)
            show_success("Success", "Activities saved!")

        except Exception as e:
            logger.error(f"Error saving profile: {e}")
            show_error("Error", f"Failed to save profile: {e}")

    def _save_preferences(self):
        """Save preferences"""
        try:
            from university_system.modules.domain.scholarship_finder.services.scholarship_service import StudentProfileManager

            min_amount = float(self.min_award_pref_var.get().strip()) if self.min_award_pref_var.get().strip() else 0
            max_letters = int(self.max_letters_var.get().strip()) if self.max_letters_var.get().strip() else 3

            profile_data = {
                'preferred_scholarship_types': self.pref_types_var.get().strip(),
                'minimum_award_amount': min_amount,
                'willing_to_write_essays': 1 if self.essays_var.get() else 0,
                'max_recommendation_letters': max_letters
            }

            StudentProfileManager.create_or_update_profile(self.student_id, **profile_data)
            show_success("Success", "Preferences saved!")

        except Exception as e:
            logger.error(f"Error saving profile: {e}")
            show_error("Error", f"Failed to save profile: {e}")

    def _show_scholarship_details_dialog(self, scholarship_id: int):
        """Show detailed scholarship information in dialog"""
        try:
            from university_system.modules.domain.scholarship_finder.services.scholarship_service import ScholarshipDatabase

            scholarship = ScholarshipDatabase.get_scholarship_details(scholarship_id)
            if not scholarship:
                show_error("Error", "Scholarship not found.")
                return

            dialog = tk.Toplevel(self.parent_frame)
            dialog.title(f"Scholarship Details - {scholarship['scholarship_name']}")
            dialog.geometry("700x600")

            # Scrollable text
            text = scrolledtext.ScrolledText(dialog, wrap=tk.WORD)
            text.pack(fill='both', expand=True, padx=10, pady=10)

            # Build detailed text
            text.insert(tk.END, f"{scholarship['scholarship_name']}\n", 'title')
            text.tag_config('title', font=('Arial', 14, 'bold'))

            text.insert(tk.END, f"\n{scholarship['organization']} ({scholarship['organization_type']})\n\n")

            award_range = f"${scholarship['award_amount_min']:,.0f}"
            if scholarship.get('award_amount_max'):
                award_range += f" - ${scholarship['award_amount_max']:,.0f}"
            text.insert(tk.END, f"Award Amount: {award_range} ({scholarship['award_type']})\n")

            text.insert(tk.END, f"Deadline: {scholarship['application_deadline']}\n\n")

            text.insert(tk.END, "Description:\n", 'heading')
            text.tag_config('heading', font=('Arial', 11, 'bold'))
            text.insert(tk.END, f"{scholarship['description']}\n\n")

            if scholarship.get('eligibility_criteria'):
                text.insert(tk.END, "Eligibility Criteria:\n", 'heading')
                text.insert(tk.END, f"{scholarship['eligibility_criteria']}\n\n")

            text.insert(tk.END, "Requirements:\n", 'heading')
            if scholarship.get('min_gpa'):
                text.insert(tk.END, f"  • Minimum GPA: {scholarship['min_gpa']}\n")
            if scholarship.get('academic_level'):
                text.insert(tk.END, f"  • Academic Level: {scholarship['academic_level']}\n")
            if scholarship.get('essay_required'):
                text.insert(tk.END, "  • Essay required\n")
            if scholarship.get('recommendation_letters_required'):
                text.insert(tk.END, f"  • {scholarship['recommendation_letters_required']} recommendation letters\n")
            if scholarship.get('transcript_required'):
                text.insert(tk.END, "  • Official transcript\n")

            text.insert(tk.END, "\n")

            if scholarship.get('application_url'):
                text.insert(tk.END, f"Application URL: {scholarship['application_url']}\n\n")

            if scholarship.get('contact_email'):
                text.insert(tk.END, f"Contact: {scholarship['contact_email']}\n")

            text.config(state=tk.DISABLED)

            # Close button
            ttk.Button(dialog, text="Close", command=dialog.destroy).pack(pady=10)

        except Exception as e:
            logger.error(f"Error showing scholarship details: {e}")
            show_error("Error", f"Failed to load scholarship details: {e}")
