"""
Background Task Runner

Provides utilities for running long operations in background threads
without blocking the main application thread.
"""

import threading
import queue
import time
import logging
import traceback
from concurrent.futures import ThreadPoolExecutor, Future
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Any, Optional, Dict, List
from functools import wraps
import uuid

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """Status of a background task."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TaskResult:
    """Result of a background task execution."""
    task_id: str
    status: TaskStatus
    result: Any = None
    error: Optional[str] = None
    error_traceback: Optional[str] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    progress: float = 0.0
    progress_message: str = ""

    @property
    def duration(self) -> Optional[float]:
        """Get task duration in seconds."""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return None

    @property
    def is_complete(self) -> bool:
        """Check if task has finished (success or failure)."""
        return self.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED)


class BackgroundTaskRunner:
    """
    Manages background task execution with thread pooling.

    Features:
    - Configurable thread pool size
    - Task progress tracking
    - Task cancellation support
    - Callback on completion
    - Error handling and logging

    Example:
        runner = BackgroundTaskRunner(max_workers=4)

        def long_operation():
            time.sleep(5)
            return "Done!"

        task_id = runner.submit(long_operation, on_complete=print)

        # Check status
        result = runner.get_result(task_id)
        print(result.status)

        # Shutdown when done
        runner.shutdown()
    """

    _instance: Optional['BackgroundTaskRunner'] = None
    _lock = threading.Lock()

    def __init__(self, max_workers: int = 4):
        """
        Initialize the task runner.

        Args:
            max_workers: Maximum number of concurrent threads
        """
        self.max_workers = max_workers
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._tasks: Dict[str, TaskResult] = {}
        self._futures: Dict[str, Future] = {}
        self._callbacks: Dict[str, Callable] = {}
        self._progress_callbacks: Dict[str, Callable] = {}
        self._cancelled: set = set()
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls, max_workers: int = 4) -> 'BackgroundTaskRunner':
        """Get singleton instance of the task runner."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(max_workers=max_workers)
        return cls._instance

    def submit(
        self,
        func: Callable,
        *args,
        on_complete: Optional[Callable[[TaskResult], None]] = None,
        on_progress: Optional[Callable[[float, str], None]] = None,
        task_name: str = "",
        **kwargs
    ) -> str:
        """
        Submit a task for background execution.

        Args:
            func: Function to execute
            *args: Positional arguments for the function
            on_complete: Callback when task completes (receives TaskResult)
            on_progress: Callback for progress updates (receives progress float, message)
            task_name: Optional name for the task
            **kwargs: Keyword arguments for the function

        Returns:
            Task ID for tracking
        """
        task_id = str(uuid.uuid4())[:8]

        # Initialize task result
        task_result = TaskResult(
            task_id=task_id,
            status=TaskStatus.PENDING,
            progress_message=task_name or f"Task {task_id}"
        )

        with self._lock:
            self._tasks[task_id] = task_result
            if on_complete:
                self._callbacks[task_id] = on_complete
            if on_progress:
                self._progress_callbacks[task_id] = on_progress

        # Wrap function to track execution
        def wrapper():
            return self._execute_task(task_id, func, args, kwargs)

        # Submit to executor
        future = self._executor.submit(wrapper)
        self._futures[task_id] = future

        logger.debug(f"Submitted task {task_id}: {task_name or func.__name__}")
        return task_id

    def _execute_task(
        self,
        task_id: str,
        func: Callable,
        args: tuple,
        kwargs: dict
    ) -> Any:
        """Execute a task and track its status."""
        task_result = self._tasks[task_id]
        task_result.status = TaskStatus.RUNNING
        task_result.start_time = time.time()

        try:
            # Check if cancelled before starting
            if task_id in self._cancelled:
                task_result.status = TaskStatus.CANCELLED
                task_result.end_time = time.time()
                return None

            # Create progress reporter for the function
            def report_progress(progress: float, message: str = ""):
                self.update_progress(task_id, progress, message)

            # Add progress reporter to kwargs if function accepts it
            kwargs_with_progress = kwargs.copy()
            kwargs_with_progress['_progress_callback'] = report_progress

            # Try to call with progress callback, fall back without
            try:
                result = func(*args, **kwargs_with_progress)
            except TypeError:
                # Function doesn't accept _progress_callback
                result = func(*args, **kwargs)

            # Check if cancelled during execution
            if task_id in self._cancelled:
                task_result.status = TaskStatus.CANCELLED
                task_result.end_time = time.time()
                return None

            task_result.result = result
            task_result.status = TaskStatus.COMPLETED
            task_result.progress = 1.0

            logger.debug(f"Task {task_id} completed successfully")

        except Exception as e:
            task_result.status = TaskStatus.FAILED
            task_result.error = str(e)
            task_result.error_traceback = traceback.format_exc()
            logger.error(f"Task {task_id} failed: {e}")

        finally:
            task_result.end_time = time.time()

            # Call completion callback
            callback = self._callbacks.get(task_id)
            if callback:
                try:
                    callback(task_result)
                except Exception as e:
                    logger.error(f"Error in task callback: {e}")

        return task_result.result

    def update_progress(self, task_id: str, progress: float, message: str = ""):
        """
        Update task progress.

        Args:
            task_id: Task ID
            progress: Progress value (0.0 to 1.0)
            message: Progress message
        """
        if task_id in self._tasks:
            self._tasks[task_id].progress = min(max(progress, 0.0), 1.0)
            if message:
                self._tasks[task_id].progress_message = message

            # Call progress callback
            callback = self._progress_callbacks.get(task_id)
            if callback:
                try:
                    callback(progress, message)
                except Exception as e:
                    logger.error(f"Error in progress callback: {e}")

    def cancel(self, task_id: str) -> bool:
        """
        Request cancellation of a task.

        Note: This sets a flag that the task should check periodically.
        It cannot forcefully stop a running task.

        Args:
            task_id: Task ID to cancel

        Returns:
            True if cancellation was requested
        """
        if task_id in self._tasks:
            self._cancelled.add(task_id)

            # Try to cancel the future if it hasn't started
            future = self._futures.get(task_id)
            if future and not future.running():
                future.cancel()
                self._tasks[task_id].status = TaskStatus.CANCELLED
                return True

            return True
        return False

    def is_cancelled(self, task_id: str) -> bool:
        """Check if a task has been cancelled."""
        return task_id in self._cancelled

    def get_result(self, task_id: str) -> Optional[TaskResult]:
        """
        Get the result of a task.

        Args:
            task_id: Task ID

        Returns:
            TaskResult or None if task not found
        """
        return self._tasks.get(task_id)

    def wait(self, task_id: str, timeout: Optional[float] = None) -> Optional[TaskResult]:
        """
        Wait for a task to complete.

        Args:
            task_id: Task ID
            timeout: Maximum time to wait in seconds

        Returns:
            TaskResult or None if timeout/not found
        """
        future = self._futures.get(task_id)
        if future:
            try:
                future.result(timeout=timeout)
            except Exception:
                pass  # Result is in TaskResult

        return self._tasks.get(task_id)

    def get_active_tasks(self) -> List[TaskResult]:
        """Get all currently running tasks."""
        return [
            task for task in self._tasks.values()
            if task.status == TaskStatus.RUNNING
        ]

    def get_all_tasks(self) -> List[TaskResult]:
        """Get all tasks (active and completed)."""
        return list(self._tasks.values())

    def clear_completed(self):
        """Remove completed tasks from memory."""
        with self._lock:
            completed = [
                task_id for task_id, task in self._tasks.items()
                if task.is_complete
            ]
            for task_id in completed:
                del self._tasks[task_id]
                self._futures.pop(task_id, None)
                self._callbacks.pop(task_id, None)
                self._progress_callbacks.pop(task_id, None)
                self._cancelled.discard(task_id)

    def shutdown(self, wait: bool = True):
        """
        Shutdown the task runner.

        Args:
            wait: Whether to wait for running tasks to complete
        """
        self._executor.shutdown(wait=wait)
        logger.info("BackgroundTaskRunner shutdown complete")


# Global task runner instance
_global_runner: Optional[BackgroundTaskRunner] = None


def get_task_runner(max_workers: int = 4) -> BackgroundTaskRunner:
    """Get the global task runner instance."""
    global _global_runner
    if _global_runner is None:
        _global_runner = BackgroundTaskRunner(max_workers=max_workers)
    return _global_runner


def run_in_background(
    func: Optional[Callable] = None,
    *,
    on_complete: Optional[Callable[[TaskResult], None]] = None,
    on_progress: Optional[Callable[[float, str], None]] = None,
):
    """
    Decorator/function to run a function in background.

    Can be used as decorator or direct call:

    As decorator:
        @run_in_background(on_complete=print)
        def slow_function():
            time.sleep(5)
            return "Done"

        task_id = slow_function()  # Returns immediately with task_id

    Direct call:
        task_id = run_in_background(slow_function, on_complete=print)
    """
    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        def wrapper(*args, **kwargs):
            runner = get_task_runner()
            return runner.submit(
                fn, *args,
                on_complete=on_complete,
                on_progress=on_progress,
                task_name=fn.__name__,
                **kwargs
            )
        return wrapper

    if func is not None:
        # Direct call: run_in_background(func)
        runner = get_task_runner()
        return runner.submit(
            func,
            on_complete=on_complete,
            on_progress=on_progress,
            task_name=getattr(func, '__name__', 'anonymous'),
        )

    # Decorator usage
    return decorator


def run_with_progress(
    func: Callable,
    *args,
    on_progress: Callable[[float, str], None],
    on_complete: Optional[Callable[[TaskResult], None]] = None,
    **kwargs
) -> str:
    """
    Run a function with progress tracking.

    The function should accept a _progress_callback parameter
    and call it periodically with (progress, message).

    Example:
        def process_files(files, _progress_callback=None):
            for i, file in enumerate(files):
                process(file)
                if _progress_callback:
                    _progress_callback((i + 1) / len(files), f"Processing {file}")

        task_id = run_with_progress(
            process_files,
            files=['a.txt', 'b.txt'],
            on_progress=lambda p, m: print(f"{p*100:.0f}% - {m}")
        )
    """
    runner = get_task_runner()
    return runner.submit(
        func, *args,
        on_complete=on_complete,
        on_progress=on_progress,
        **kwargs
    )


def cancel_task(task_id: str) -> bool:
    """Cancel a running task."""
    runner = get_task_runner()
    return runner.cancel(task_id)


def get_task_status(task_id: str) -> Optional[TaskResult]:
    """Get the status of a task."""
    runner = get_task_runner()
    return runner.get_result(task_id)
