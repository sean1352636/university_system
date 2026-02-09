"""
Async Utilities Package

Provides asynchronous execution utilities for the University Management System:
- Background task execution for GUI operations
- Thread pool management
- Async database query wrappers
- Progress tracking for long operations
"""

from university_system.infrastructure.async_utils.background_tasks import (
    BackgroundTaskRunner,
    TaskStatus,
    TaskResult,
    run_in_background,
    run_with_progress,
    cancel_task,
    get_task_status,
)

from university_system.infrastructure.async_utils.async_database import (
    AsyncDatabaseWrapper,
    async_query,
    async_execute,
    async_transaction,
)

from university_system.infrastructure.async_utils.gui_async import (
    GUIAsyncMixin,
    TkinterAsyncBridge,
    schedule_gui_update,
    run_async_operation,
)

__all__ = [
    # Background Tasks
    'BackgroundTaskRunner',
    'TaskStatus',
    'TaskResult',
    'run_in_background',
    'run_with_progress',
    'cancel_task',
    'get_task_status',
    # Async Database
    'AsyncDatabaseWrapper',
    'async_query',
    'async_execute',
    'async_transaction',
    # GUI Async
    'GUIAsyncMixin',
    'TkinterAsyncBridge',
    'schedule_gui_update',
    'run_async_operation',
]
