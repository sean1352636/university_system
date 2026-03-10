import os

from education_system.university_system.modules.shared.utils.i18n import get_text as _t
from education_system.university_system.modules.shared.constants.paths import DEFAULT_DB_PATH

from .validation import ValidationMixin
from .duplicates import DuplicatesMixin
from .import_ops import ImportOpsMixin
from .db_operations import DbOperationsMixin
from .export_ops import ExportOpsMixin
from .reporting import ReportingMixin
from .templates import TemplatesMixin
from .backup import BackupMixin
from .scheduling import SchedulingMixin
from .api import ApiMixin
from .external import ExternalMixin


class BatchOperationManager(
    ValidationMixin,
    DuplicatesMixin,
    ImportOpsMixin,
    DbOperationsMixin,
    ExportOpsMixin,
    ReportingMixin,
    TemplatesMixin,
    BackupMixin,
    SchedulingMixin,
    ApiMixin,
    ExternalMixin,
):
    """Main class for managing batch operations"""

    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = str(DEFAULT_DB_PATH)
        self.db_path = db_path
        from education_system.university_system.modules.shared.constants import paths
        self.backup_dir = str(paths.BACKUP_DIR)
        self.import_history = []
        self.api_app = None
        self.ensure_backup_directory()

    def ensure_backup_directory(self):
        """Ensure backup directory exists"""
        os.makedirs(self.backup_dir, exist_ok=True)

    def display_batch_menu(self):
        """Display the enhanced batch operations menu"""
        while True:
            print("\n" + "="*60)
            print(_t("shared.utils.batch_operations.menu_title"))
            print("="*60)
            print("\n" + _t("shared.utils.batch_operations.section_import"))
            print(_t("shared.utils.batch_operations.menu_import_csv"))
            print(_t("shared.utils.batch_operations.menu_import_excel"))
            print(_t("shared.utils.batch_operations.menu_multi_file"))
            print(_t("shared.utils.batch_operations.menu_duplicate_detection"))
            print(_t("shared.utils.batch_operations.menu_preview_import"))
            print(_t("shared.utils.batch_operations.menu_resume_import"))

            print("\n" + _t("shared.utils.batch_operations.section_update"))
            print(_t("shared.utils.batch_operations.menu_batch_update"))
            print(_t("shared.utils.batch_operations.menu_bulk_module"))
            print(_t("shared.utils.batch_operations.menu_import_grades"))

            print("\n" + _t("shared.utils.batch_operations.section_export"))
            print(_t("shared.utils.batch_operations.menu_export_students"))
            print(_t("shared.utils.batch_operations.menu_export_stats"))
            print(_t("shared.utils.batch_operations.menu_generate_reports"))

            print("\n" + _t("shared.utils.batch_operations.section_quality"))
            print(_t("shared.utils.batch_operations.menu_validate_clean"))
            print(_t("shared.utils.batch_operations.menu_find_duplicates"))
            print(_t("shared.utils.batch_operations.menu_quality_dashboard"))

            print("\n" + _t("shared.utils.batch_operations.section_utilities"))
            print(_t("shared.utils.batch_operations.menu_generate_template"))
            print(_t("shared.utils.batch_operations.menu_create_backup"))
            print(_t("shared.utils.batch_operations.menu_undo_import"))
            print(_t("shared.utils.batch_operations.menu_import_history"))

            print("\n" + _t("shared.utils.batch_operations.section_automation"))
            print(_t("shared.utils.batch_operations.menu_schedule_imports"))
            print(_t("shared.utils.batch_operations.menu_start_api"))
            print(_t("shared.utils.batch_operations.menu_external_integration"))

            print("\n" + _t("shared.utils.batch_operations.menu_return"))

            choice = input("\n" + _t("shared.utils.batch_operations.prompt_choice")).strip()

            if choice == '1':
                self.import_from_csv()
            elif choice == '2':
                self.import_from_excel()
            elif choice == '3':
                self.multi_file_import()
            elif choice == '4':
                self.import_with_duplicate_detection()
            elif choice == '5':
                self.preview_import()
            elif choice == '6':
                self.resume_failed_import()
            elif choice == '7':
                self.batch_update_records()
            elif choice == '8':
                self.bulk_module_operations()
            elif choice == '9':
                self.import_grade_data()
            elif choice == '10':
                self.export_students_to_file()
            elif choice == '11':
                self.export_enrollment_statistics()
            elif choice == '12':
                self.generate_import_reports()
            elif choice == '13':
                self.validate_and_clean_data()
            elif choice == '14':
                self.find_duplicate_students()
            elif choice == '15':
                self.data_quality_dashboard()
            elif choice == '16':
                self.generate_import_template()
            elif choice == '17':
                self.create_database_backup()
            elif choice == '18':
                self.undo_last_import()
            elif choice == '19':
                self.show_import_history()
            elif choice == '20':
                self.schedule_automated_imports()
            elif choice == '21':
                self.start_api_server()
            elif choice == '22':
                self.external_system_integration()
            elif choice in ('0', '25'):
                print(_t("shared.utils.batch_operations.returning_to_menu"))
                break
            else:
                print(_t("shared.utils.batch_operations.invalid_choice"))
