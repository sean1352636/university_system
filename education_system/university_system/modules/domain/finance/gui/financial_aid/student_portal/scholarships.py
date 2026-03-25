"""
Scholarships mixin - browsing, viewing details, and applying for scholarships.
"""

from typing import Dict

from education_system.university_system.modules.domain.finance.gui.financial_aid.common_imports import (
    tk,
    ttk,
    scrolledtext,
    logging,
    datetime,
    get_connection,
    log_activity,
    create_data_table,
    create_scrollable_frame,
    create_search_filter_bar,
    format_currency,
    format_date,
    validate_date,
    show_error,
    show_success,
    show_warning,
    get_current_academic_year,
    get_status_color,
    clear_frame,
)
from education_system.university_system.modules.shared.utils.i18n import get_text
from education_system.university_system.infrastructure.email.email_service import send_email
from education_system.university_system.infrastructure.email.template_utils import render_template

logger = logging.getLogger(__name__)


class ScholarshipsMixin:
    """Scholarship browsing, details, and application"""

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
                            subject = get_text("financial_aid.student_portal.email.scholarship_submitted_subject", "Scholarship Application Submitted")
                            body = get_text("financial_aid.student_portal.email.scholarship_submitted_body", "Your application for scholarship ID {scholarship_id} has been submitted successfully.", scholarship_id=scholarship_id)

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

    def _show_scholarship_details_dialog(self, scholarship_id: int):
        """Show detailed scholarship information in dialog"""
        try:
            from education_system.university_system.modules.domain.scholarship_finder.services.scholarship_service import ScholarshipDatabase

            scholarship = ScholarshipDatabase.get_scholarship_details(scholarship_id)
            if not scholarship:
                show_error(get_text("financial_aid.student_portal.errors.title", "Error"), get_text("financial_aid.student_portal.errors.scholarship_not_found", "Scholarship not found."))
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
            text.insert(tk.END, f"{get_text('financial_aid.student_portal.profile.detail_labels.award_amount', 'Award Amount: {amount} ({type})', amount=award_range, type=scholarship['award_type'])}\n")

            text.insert(tk.END, f"{get_text('financial_aid.student_portal.profile.detail_labels.deadline', 'Deadline: {date}', date=scholarship['application_deadline'])}\n\n")

            text.insert(tk.END, f"{get_text('financial_aid.student_portal.profile.detail_labels.description', 'Description:')}\n", 'heading')
            text.tag_config('heading', font=('Arial', 11, 'bold'))
            text.insert(tk.END, f"{scholarship['description']}\n\n")

            if scholarship.get('eligibility_criteria'):
                text.insert(tk.END, f"{get_text('financial_aid.student_portal.profile.detail_labels.eligibility', 'Eligibility Criteria:')}\n", 'heading')
                text.insert(tk.END, f"{scholarship['eligibility_criteria']}\n\n")

            text.insert(tk.END, f"{get_text('financial_aid.student_portal.profile.detail_labels.requirements', 'Requirements:')}\n", 'heading')
            if scholarship.get('min_gpa'):
                text.insert(tk.END, f"  \u2022 {get_text('financial_aid.student_portal.profile.detail_labels.min_gpa', 'Minimum GPA: {gpa}', gpa=scholarship['min_gpa'])}\n")
            if scholarship.get('academic_level'):
                text.insert(tk.END, f"  \u2022 {get_text('financial_aid.student_portal.profile.detail_labels.academic_level', 'Academic Level: {level}', level=scholarship['academic_level'])}\n")
            if scholarship.get('essay_required'):
                text.insert(tk.END, f"  \u2022 {get_text('financial_aid.student_portal.profile.detail_labels.essay_required', 'Essay required')}\n")
            if scholarship.get('recommendation_letters_required'):
                text.insert(tk.END, f"  \u2022 {get_text('financial_aid.student_portal.profile.detail_labels.recommendation_letters', '{count} recommendation letters', count=scholarship['recommendation_letters_required'])}\n")
            if scholarship.get('transcript_required'):
                text.insert(tk.END, f"  \u2022 {get_text('financial_aid.student_portal.profile.detail_labels.official_transcript', 'Official transcript')}\n")

            text.insert(tk.END, "\n")

            if scholarship.get('application_url'):
                text.insert(tk.END, f"{get_text('financial_aid.student_portal.profile.detail_labels.application_url', 'Application URL: {url}', url=scholarship['application_url'])}\n\n")

            if scholarship.get('contact_email'):
                text.insert(tk.END, f"{get_text('financial_aid.student_portal.profile.detail_labels.contact', 'Contact: {email}', email=scholarship['contact_email'])}\n")

            text.config(state=tk.DISABLED)

            # Close button
            ttk.Button(dialog, text=get_text("financial_aid.student_portal.buttons.close", "Close"), command=dialog.destroy).pack(pady=10)

        except Exception as e:
            logger.error(f"Error showing scholarship details: {e}")
            show_error(get_text("financial_aid.student_portal.errors.title", "Error"), get_text("financial_aid.student_portal.errors.failed_load_scholarship_details", "Failed to load scholarship details: {error}", error=str(e)))
