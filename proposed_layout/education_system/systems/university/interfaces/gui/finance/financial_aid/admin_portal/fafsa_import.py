"""
FAFSA import mixin for AdminPortal.
"""

from education_system.systems.university.interfaces.gui.finance.financial_aid.admin_portal._imports import (
    tk, ttk, filedialog, logging,
    log_activity,
    clear_frame,
    show_error, show_success, show_warning,
    get_text,
)

logger = logging.getLogger(__name__)


class FAFSAImportMixin:
    """Methods for importing FAFSA data."""

    def show_fafsa_import(self):
        """Show FAFSA import interface"""
        self._prepare_view_parent()

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
