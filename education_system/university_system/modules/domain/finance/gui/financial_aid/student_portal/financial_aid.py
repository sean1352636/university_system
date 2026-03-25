"""
Financial Aid mixin - applying for financial aid.
"""

from typing import Dict, Optional

from education_system.university_system.modules.domain.finance.gui.financial_aid.common_imports import (
    tk,
    ttk,
    scrolledtext,
    logging,
    datetime,
    get_connection,
    log_activity,
    clear_frame,
    show_error,
    show_success,
    get_current_academic_year,
    get_academic_year_list,
)
from education_system.university_system.modules.shared.utils.i18n import get_text
from education_system.university_system.infrastructure.email.email_service import send_email
from education_system.university_system.infrastructure.email.template_utils import render_template

logger = logging.getLogger(__name__)


class FinancialAidMixin:
    """Financial aid application functionality"""

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
                            subject = get_text("financial_aid.student_portal.email.aid_submitted_subject", "Financial Aid Application Submitted")
                            body = get_text("financial_aid.student_portal.email.aid_submitted_body", "Your financial aid application for {academic_year} has been submitted.", academic_year=app_data['academic_year'])

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
