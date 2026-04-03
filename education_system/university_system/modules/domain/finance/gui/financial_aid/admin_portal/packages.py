"""
Aid package creation mixin for AdminPortal.
"""

from education_system.university_system.modules.domain.finance.gui.financial_aid.admin_portal._imports import (
    tk, ttk, logging,
    log_activity,
    clear_frame,
    format_currency,
    show_error, show_success,
    get_current_academic_year, get_academic_year_list,
    get_text,
    Dict,
)

logger = logging.getLogger(__name__)


class PackagesMixin:
    """Methods for creating financial aid packages."""

    def show_create_package(self, student_id: str = None, academic_year: str = None):
        """Show create aid package interface"""
        self._prepare_view_parent()

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
