"""
Batch Operations GUI - Backend Manager

Contains the EnhancedBatchOperationManager class which provides all
backend batch operation logic including import, export, validation,
duplicate detection, and data quality features.

The class is composed from mixins in the mixins/ package, each providing
a cohesive group of related methods.
"""

from contextlib import contextmanager

from education_system.post_18.university_system.modules.shared.gui.batch_operations.constants import (
    DEFAULT_BATCH_DB,
    DatabaseManager,
)

from education_system.post_18.university_system.modules.shared.gui.batch_operations.models import (
    OriginalBatchOperationManager,
)

from education_system.post_18.university_system.modules.shared.gui.batch_operations.mixins import (
    ImportHandlersMixin,
    BatchUpdatesMixin,
    ValidationMixin,
    DuplicatesMixin,
    ModuleOperationsMixin,
    GradeManagementMixin,
    ExportReportingMixin,
    DataQualityMixin,
    BackupRestoreMixin,
    TemplatesMixin,
    SchedulingMixin,
    ExternalIntegrationMixin,
    ApiServiceMixin,
    UtilsMixin,
)


class EnhancedBatchOperationManager(
    ImportHandlersMixin,
    BatchUpdatesMixin,
    ValidationMixin,
    DuplicatesMixin,
    ModuleOperationsMixin,
    GradeManagementMixin,
    ExportReportingMixin,
    DataQualityMixin,
    BackupRestoreMixin,
    TemplatesMixin,
    SchedulingMixin,
    ExternalIntegrationMixin,
    ApiServiceMixin,
    UtilsMixin,
    OriginalBatchOperationManager,
):
    """Enhanced backend manager with GUI-specific methods.

    Composed from mixins:
    - ImportHandlersMixin: CSV/Excel imports, file I/O, import history
    - BatchUpdatesMixin: Batch record updates, module updates
    - ValidationMixin: Data validation, cleaning, format standardization
    - DuplicatesMixin: Duplicate detection, confidence scoring, merging
    - ModuleOperationsMixin: Bulk module add/remove/replace
    - GradeManagementMixin: Grade import and processing
    - ExportReportingMixin: Data export and report generation
    - DataQualityMixin: Quality dashboard and metrics
    - BackupRestoreMixin: Database backup, restore, undo
    - TemplatesMixin: Import template generation
    - SchedulingMixin: Automated import scheduling
    - ExternalIntegrationMixin: External DB/API/file share integration
    - ApiServiceMixin: Flask REST API server
    - UtilsMixin: Student queries and navigation
    """

    def __init__(self, db_path: str = DEFAULT_BATCH_DB):
        super().__init__(db_path)
        self.db_manager = _DbManagerAdapter(self.db_path)
        self.progress_callback = None


class _DbManagerAdapter:
    """Adapter that provides the get_connection/close/db_path interface
    expected by the batch operation mixins, backed by DatabaseManager."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    @contextmanager
    def get_connection(self):
        with DatabaseManager(self.db_path) as db:
            yield db.conn

    def close(self):
        pass  # connections are closed by the context manager


# ========================================
# MAIN APPLICATION ENTRY POINT
# ========================================

def main():
    """Main entry point - supports both GUI and command-line modes"""
    import sys

    # Check command line arguments for mode selection
    if len(sys.argv) > 1 and sys.argv[1] == '--cli':
        # Start in command-line mode
        print("\U0001f393 Enhanced Student Records Batch Operations System")
        print("=" * 60)
        print("Starting in Command-Line Mode")

        batch_manager = OriginalBatchOperationManager()
        batch_manager.display_batch_menu()
    else:
        # Start in GUI mode (default)
        print("\U0001f393 Enhanced Student Records Batch Operations System")
        print("=" * 60)
        print("Starting GUI Interface...")

        # Import here to avoid circular imports
        from education_system.post_18.university_system.modules.shared.gui.batch_operations.main_gui import BatchOperationsGUI

        # Create and run GUI application
        app = BatchOperationsGUI()

        # Replace backend with enhanced version
        app.backend = EnhancedBatchOperationManager(app.backend.db_path)

        app.run()


if __name__ == "__main__":
    main()
