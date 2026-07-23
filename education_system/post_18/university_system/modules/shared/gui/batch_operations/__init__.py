"""
Batch Operations GUI Package

Provides the BatchOperationsGUI for managing batch import, export,
update, and quality operations on student records.

This package splits the original batch_operations_gui.py monolith
into modular manager files following the composition pattern used
throughout the codebase (see assignment_system/, grade_tracking/).
"""

from education_system.post_18.university_system.modules.shared.gui.batch_operations.main_gui import (
    BatchOperationsGUI,
)
from education_system.post_18.university_system.modules.shared.gui.batch_operations.backend import (
    EnhancedBatchOperationManager,
    main,
)
from education_system.post_18.university_system.modules.shared.gui.batch_operations.models import (
    ImportResult,
    ProgressTracker,
    OriginalBatchOperationManager,
)
from education_system.post_18.university_system.modules.shared.gui.batch_operations.progress_dialog import (
    GUIProgressDialog,
)

__all__ = [
    'BatchOperationsGUI',
    'EnhancedBatchOperationManager',
    'ImportResult',
    'ProgressTracker',
    'OriginalBatchOperationManager',
    'GUIProgressDialog',
    'main',
]
