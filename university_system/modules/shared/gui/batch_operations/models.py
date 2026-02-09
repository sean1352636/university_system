"""
Batch Operations GUI - Models

Fallback model classes for backwards compatibility including
ImportResult, ProgressTracker, and OriginalBatchOperationManager.
"""

from .constants import (
    dataclass, datetime, time, os, List, Dict,
    DEFAULT_BATCH_DB,
)

# Import the original batch operations class for backwards compatibility
try:
    from university_system.modules.shared.utils.batch_operations import BatchOperationManager as OriginalBatchOperationManager
    from university_system.modules.shared.utils.batch_operations import ImportResult, ProgressTracker
except ImportError:
    # If the original module is not available, use the embedded classes

    @dataclass
    class ImportResult:
        """Data class to track import operation results"""
        total_records: int = 0
        successful_imports: int = 0
        failed_imports: int = 0
        duplicates_found: int = 0
        duplicates_skipped: int = 0
        duplicates_updated: int = 0
        errors: List[Dict] = None
        start_time: datetime.datetime = None
        end_time: datetime.datetime = None

        def __post_init__(self):
            if self.errors is None:
                self.errors = []

    class ProgressTracker:
        """Track and display progress for batch operations"""
        def __init__(self, total_items: int, operation_name: str = "Processing"):
            self.total_items = total_items
            self.current_item = 0
            self.operation_name = operation_name
            self.start_time = time.time()
            self.last_update = 0

        def update(self, increment: int = 1):
            self.current_item += increment

        def display_progress(self):
            """Display progress to console (CLI fallback when GUI is not available)"""
            if self.total_items <= 0:
                return

            # Only update display every 100ms to avoid console spam
            current_time = time.time()
            if current_time - self.last_update < 0.1:
                return
            self.last_update = current_time

            # Calculate progress percentage
            percentage = (self.current_item / self.total_items) * 100

            # Calculate elapsed time and ETA
            elapsed = current_time - self.start_time
            if self.current_item > 0:
                estimated_total = elapsed * (self.total_items / self.current_item)
                eta = estimated_total - elapsed
                eta_str = f"ETA: {int(eta//60)}:{int(eta%60):02d}"
            else:
                eta_str = "ETA: --:--"

            # Create progress bar
            bar_width = 40
            filled = int(bar_width * self.current_item / self.total_items)
            bar = "\u2588" * filled + "\u2591" * (bar_width - filled)

            # Print progress (overwrite same line)
            print(f"\r{self.operation_name}: [{bar}] {percentage:.1f}% ({self.current_item}/{self.total_items}) {eta_str}", end="", flush=True)

            # Print newline when complete
            if self.current_item >= self.total_items:
                print()  # Newline at completion

    # Include the original BatchOperationManager class for backwards compatibility
    class OriginalBatchOperationManager:
        """Original command-line batch operations manager for backwards compatibility"""

        def __init__(self, db_path: str = DEFAULT_BATCH_DB):
            self.db_path = db_path
            from university_system.modules.shared.constants import paths
            self.backup_dir = str(paths.BACKUP_DIR)
            self.import_history = []
            self.api_app = None
            self.ensure_backup_directory()

        def ensure_backup_directory(self):
            """Ensure backup directory exists"""
            os.makedirs(self.backup_dir, exist_ok=True)

        # Include all the original methods here (abbreviated for space)
        def display_batch_menu(self):
            """
            Original command-line menu for backwards compatibility

            This method is deprecated in favor of the GUI interface.
            It redirects to the original CLI implementation if needed,
            or displays a message directing users to the GUI.
            """
            try:
                # Try to import and use the original CLI implementation
                from university_system.modules.shared.utils.batch_operations import (
                    BatchOperationManager as OriginalCLIManager
                )

                print("\n" + "="*60)
                print("\u26a0\ufe0f  DEPRECATION NOTICE")
                print("="*60)
                print("\nThis CLI menu is deprecated. Please use the GUI interface:")
                print("  python run.py --gui")
                print("\nOr import the GUI class:")
                print("  from university_system.modules.shared.gui.batch_operations_gui import BatchOperationsGUI")
                print("\n" + "="*60)

                # Ask user if they want to continue with CLI anyway
                response = input("\nContinue with legacy CLI menu anyway? (y/n): ").lower()
                if response == 'y':
                    # Create instance of original manager and call its menu
                    original_manager = OriginalCLIManager(self.db_path)
                    original_manager.display_batch_menu()
                else:
                    print("\nPlease use the GUI interface for batch operations.")
                    print("Exiting...")

            except ImportError:
                print("\n" + "="*60)
                print("\u274c CLI INTERFACE NOT AVAILABLE")
                print("="*60)
                print("\nThe command-line interface is not available.")
                print("Please use the GUI interface:")
                print("  python run.py --gui")
                print("\nFor programmatic access, use BatchOperationsGUI class:")
                print("  from university_system.modules.shared.gui.batch_operations_gui import BatchOperationsGUI")
                print("="*60 + "\n")

        # ... (all other original methods would be included here)
