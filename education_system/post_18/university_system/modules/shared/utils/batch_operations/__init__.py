"""
Batch Operations Package

Split from a single batch_operations.py into focused submodules:
- models: ImportResult dataclass and ProgressTracker
- validation: Data validation and cleaning
- duplicates: Duplicate detection and conflict resolution
- import_ops: CSV/Excel file import operations
- db_operations: Database insert/update/module operations
- export_ops: Data export operations
- reporting: Reports, history, and data quality dashboard
- templates: Import template generation
- backup: Database backup and undo operations
- scheduling: Automated import scheduling and notifications
- api: REST API server (Flask)
- external: External system integrations
- manager: BatchOperationManager class composing all mixins
"""

from education_system.post_18.university_system.modules.shared.utils.batch_operations.models import ImportResult, ProgressTracker
from education_system.post_18.university_system.modules.shared.utils.batch_operations.manager import BatchOperationManager

from education_system.post_18.university_system.core.i18n import get_text as _t


def main():
    """Main function to demonstrate the enhanced batch operations system"""
    print(_t("shared.utils.batch_operations.system_title"))
    print("=" * 60)

    # Initialize the batch operation manager
    batch_manager = BatchOperationManager()

    # Start the enhanced menu system
    batch_manager.display_batch_menu()


__all__ = [
    'ImportResult',
    'ProgressTracker',
    'BatchOperationManager',
    'main',
]
