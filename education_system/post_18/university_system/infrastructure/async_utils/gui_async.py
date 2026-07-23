"""
GUI Async Utilities

Provides utilities for running async operations in Tkinter GUIs
without freezing the interface.
"""

import threading
import queue
import logging
import time
from typing import Callable, Any, Optional, TypeVar
from functools import wraps
from dataclasses import dataclass

from education_system.post_18.university_system.core.i18n import get_text, _

logger = logging.getLogger(__name__)

T = TypeVar('T')


@dataclass
class AsyncOperation:
    """Represents an async operation for the GUI."""
    func: Callable
    args: tuple
    kwargs: dict
    on_complete: Optional[Callable[[Any], None]]
    on_error: Optional[Callable[[Exception], None]]
    on_progress: Optional[Callable[[float, str], None]]


class TkinterAsyncBridge:
    """
    Bridge between async operations and Tkinter's event loop.

    This class allows running long operations in background threads
    while safely updating the GUI through Tkinter's main thread.

    Example:
        class MyApp:
            def __init__(self, root):
                self.root = root
                self.async_bridge = TkinterAsyncBridge(root)

            def load_data(self):
                def fetch_data():
                    # Long operation
                    time.sleep(2)
                    return get_all_students()

                def on_complete(students):
                    self.populate_list(students)

                def on_error(error):
                    messagebox.showerror("Error", str(error))

                self.async_bridge.run(
                    fetch_data,
                    on_complete=on_complete,
                    on_error=on_error
                )
    """

    def __init__(self, root, poll_interval: int = 100):
        """
        Initialize the async bridge.

        Args:
            root: Tkinter root window
            poll_interval: How often to check for results (ms)
        """
        self.root = root
        self.poll_interval = poll_interval
        self._result_queue = queue.Queue()
        self._active_tasks = 0
        self._polling = False

    def run(
        self,
        func: Callable[..., T],
        *args,
        on_complete: Optional[Callable[[T], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
        on_progress: Optional[Callable[[float, str], None]] = None,
        **kwargs
    ) -> None:
        """
        Run a function in a background thread.

        Args:
            func: Function to run
            *args: Arguments for the function
            on_complete: Called with result on success (in main thread)
            on_error: Called with exception on failure (in main thread)
            on_progress: Called with (progress, message) updates
            **kwargs: Keyword arguments for the function
        """
        self._active_tasks += 1

        if not self._polling:
            self._start_polling()

        def worker():
            try:
                # If function accepts progress callback, provide it
                if on_progress:
                    def progress_wrapper(progress: float, message: str = ""):
                        self._result_queue.put(('progress', on_progress, progress, message))

                    try:
                        result = func(*args, _progress_callback=progress_wrapper, **kwargs)
                    except TypeError:
                        result = func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)

                self._result_queue.put(('success', on_complete, result))

            except Exception as e:
                logger.error(f"Async operation failed: {e}")
                self._result_queue.put(('error', on_error, e))

            finally:
                self._active_tasks -= 1

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

    def _start_polling(self):
        """Start polling for results."""
        self._polling = True
        self._poll_results()

    def _poll_results(self):
        """Check for completed operations and call callbacks."""
        try:
            while True:
                try:
                    item = self._result_queue.get_nowait()

                    if item[0] == 'success':
                        _, callback, result = item
                        if callback:
                            try:
                                callback(result)
                            except Exception as e:
                                logger.error(f"Error in success callback: {e}")

                    elif item[0] == 'error':
                        _, callback, error = item
                        if callback:
                            try:
                                callback(error)
                            except Exception as e:
                                logger.error(f"Error in error callback: {e}")

                    elif item[0] == 'progress':
                        _, callback, progress, message = item
                        if callback:
                            try:
                                callback(progress, message)
                            except Exception as e:
                                logger.error(f"Error in progress callback: {e}")

                except queue.Empty:
                    break

        except Exception as e:
            logger.error(f"Error polling results: {e}")

        # Continue polling if there are active tasks
        if self._active_tasks > 0 or not self._result_queue.empty():
            self.root.after(self.poll_interval, self._poll_results)
        else:
            self._polling = False

    def run_with_loading(
        self,
        func: Callable[..., T],
        *args,
        loading_message: str = "Loading...",
        on_complete: Optional[Callable[[T], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
        **kwargs
    ) -> None:
        """
        Run a function with a loading indicator.

        Shows a loading message while the operation runs.

        Args:
            func: Function to run
            loading_message: Message to show during operation
            on_complete: Called with result on success
            on_error: Called with exception on failure
        """
        # Show loading (implementation depends on your GUI structure)
        # This is a placeholder - override in your implementation
        logger.info(f"Starting: {loading_message}")

        def complete_wrapper(result):
            logger.info("Operation complete")
            if on_complete:
                on_complete(result)

        def error_wrapper(error):
            logger.error(f"Operation failed: {error}")
            if on_error:
                on_error(error)

        self.run(
            func, *args,
            on_complete=complete_wrapper,
            on_error=error_wrapper,
            **kwargs
        )


class GUIAsyncMixin:
    """
    Mixin class to add async capabilities to Tkinter windows.

    Add this as a parent class to your Tkinter Frame/Window classes
    to gain easy async operation support.

    Example:
        class StudentListWindow(tk.Frame, GUIAsyncMixin):
            def __init__(self, parent):
                tk.Frame.__init__(self, parent)
                self.init_async(parent)

                self.load_students()

            def load_students(self):
                self.run_async(
                    self._fetch_students,
                    on_complete=self._display_students,
                    on_error=lambda e: messagebox.showerror("Error", str(e))
                )

            def _fetch_students(self):
                # This runs in background thread
                return database.get_all_students()

            def _display_students(self, students):
                # This runs in main thread
                for student in students:
                    self.listbox.insert(tk.END, student.name)
    """

    _async_bridge: Optional[TkinterAsyncBridge] = None

    def init_async(self, root=None):
        """
        Initialize async support.

        Call this in your __init__ after initializing the Tkinter component.

        Args:
            root: Tkinter root window (defaults to winfo_toplevel())
        """
        if root is None:
            root = self.winfo_toplevel()
        self._async_bridge = TkinterAsyncBridge(root)

    def run_async(
        self,
        func: Callable[..., T],
        *args,
        on_complete: Optional[Callable[[T], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
        on_progress: Optional[Callable[[float, str], None]] = None,
        **kwargs
    ) -> None:
        """
        Run a function asynchronously.

        Args:
            func: Function to run in background
            *args: Arguments for the function
            on_complete: Callback for success (runs in main thread)
            on_error: Callback for failure (runs in main thread)
            on_progress: Callback for progress updates
            **kwargs: Keyword arguments for the function
        """
        if self._async_bridge is None:
            self.init_async()

        self._async_bridge.run(
            func, *args,
            on_complete=on_complete,
            on_error=on_error,
            on_progress=on_progress,
            **kwargs
        )

    def run_async_with_progress(
        self,
        func: Callable,
        *args,
        progress_bar=None,
        progress_label=None,
        on_complete: Optional[Callable] = None,
        on_error: Optional[Callable] = None,
        **kwargs
    ) -> None:
        """
        Run async operation with progress bar updates.

        Args:
            func: Function to run (should accept _progress_callback)
            progress_bar: Tkinter ttk.Progressbar widget
            progress_label: Tkinter Label for progress message
            on_complete: Success callback
            on_error: Error callback
        """
        def update_progress(progress: float, message: str):
            if progress_bar:
                progress_bar['value'] = progress * 100
            if progress_label:
                progress_label.config(text=message)

        self.run_async(
            func, *args,
            on_complete=on_complete,
            on_error=on_error,
            on_progress=update_progress,
            **kwargs
        )


def schedule_gui_update(root, callback: Callable, delay_ms: int = 0):
    """
    Schedule a GUI update to run in the main thread.

    Use this when you need to update GUI elements from a background thread.

    Args:
        root: Tkinter root window
        callback: Function to call in main thread
        delay_ms: Delay before calling (milliseconds)

    Example:
        def background_task():
            result = long_calculation()
            schedule_gui_update(root, lambda: label.config(text=result))

        threading.Thread(target=background_task).start()
    """
    root.after(delay_ms, callback)


def run_async_operation(
    root,
    operation: Callable[..., T],
    *args,
    on_complete: Optional[Callable[[T], None]] = None,
    on_error: Optional[Callable[[Exception], None]] = None,
    **kwargs
) -> None:
    """
    Convenience function to run an async operation.

    Args:
        root: Tkinter root window
        operation: Function to run in background
        *args: Arguments for the function
        on_complete: Success callback
        on_error: Error callback
        **kwargs: Keyword arguments

    Example:
        def load_data():
            return fetch_from_database()

        def on_loaded(data):
            populate_tree(data)

        run_async_operation(root, load_data, on_complete=on_loaded)
    """
    bridge = TkinterAsyncBridge(root)
    bridge.run(operation, *args, on_complete=on_complete, on_error=on_error, **kwargs)


def async_gui_method(
    on_complete_attr: str = None,
    on_error_attr: str = None,
    show_loading: bool = False
):
    """
    Decorator to make a method run asynchronously with GUI updates.

    The decorated method will run in a background thread.
    Results are automatically passed to the specified callback method.

    Args:
        on_complete_attr: Name of method to call with result
        on_error_attr: Name of method to call on error
        show_loading: Whether to show loading indicator

    Example:
        class MyWindow(tk.Frame, GUIAsyncMixin):
            def __init__(self, parent):
                tk.Frame.__init__(self, parent)
                self.init_async(parent)

            @async_gui_method(on_complete_attr='_on_data_loaded')
            def load_data(self):
                # Runs in background
                return fetch_all_data()

            def _on_data_loaded(self, data):
                # Runs in main thread
                self.display(data)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            if not hasattr(self, '_async_bridge') or self._async_bridge is None:
                if hasattr(self, 'init_async'):
                    self.init_async()
                else:
                    raise RuntimeError(
                        "Class must have init_async method or inherit GUIAsyncMixin"
                    )

            on_complete = None
            on_error = None

            if on_complete_attr:
                on_complete = getattr(self, on_complete_attr, None)
            if on_error_attr:
                on_error = getattr(self, on_error_attr, None)

            def operation():
                return func(self, *args, **kwargs)

            self._async_bridge.run(
                operation,
                on_complete=on_complete,
                on_error=on_error
            )

        return wrapper
    return decorator


class ProgressDialog:
    """
    A simple progress dialog for long operations.

    Example:
        dialog = ProgressDialog(root, "Loading Data", "Please wait...")

        def long_operation(_progress_callback=None):
            for i in range(100):
                time.sleep(0.1)
                if _progress_callback:
                    _progress_callback(i / 100, f"Step {i + 1} of 100")
            return "Done!"

        def on_complete(result):
            dialog.close()
            messagebox.showinfo("Success", result)

        dialog.show()
        run_async_operation(
            root, long_operation,
            on_complete=on_complete,
            on_progress=dialog.update_progress
        )
    """

    def __init__(
        self,
        parent,
        title: str = "Progress",
        message: str = "Please wait...",
        cancellable: bool = False
    ):
        """
        Initialize the progress dialog.

        Args:
            parent: Parent Tkinter window
            title: Dialog title
            message: Initial message
            cancellable: Whether to show cancel button
        """
        import tkinter as tk
        from tkinter import ttk

        self.parent = parent
        self.cancelled = False
        self._dialog = None
        self._progress_var = None
        self._message_var = None

        # Create dialog
        self._dialog = tk.Toplevel(parent)
        self._dialog.title(title)
        self._dialog.transient(parent)
        self._dialog.grab_set()

        # Center the dialog
        self._dialog.geometry("300x120")
        self._dialog.resizable(False, False)

        # Message
        self._message_var = tk.StringVar(value=message)
        label = ttk.Label(
            self._dialog,
            textvariable=self._message_var,
            wraplength=280
        )
        label.pack(pady=(20, 10))

        # Progress bar
        self._progress_var = tk.DoubleVar(value=0)
        self._progress_bar = ttk.Progressbar(
            self._dialog,
            variable=self._progress_var,
            maximum=100,
            length=250
        )
        self._progress_bar.pack(pady=10)

        # Cancel button
        if cancellable:
            cancel_btn = ttk.Button(
                self._dialog,
                text="Cancel",
                command=self._on_cancel
            )
            cancel_btn.pack(pady=10)

        # Prevent closing
        self._dialog.protocol("WM_DELETE_WINDOW", lambda: None)

        # Initially hidden
        self._dialog.withdraw()

    def show(self):
        """Show the progress dialog."""
        self._dialog.deiconify()
        self._dialog.update()

    def close(self):
        """Close the progress dialog."""
        if self._dialog:
            self._dialog.grab_release()
            self._dialog.destroy()
            self._dialog = None

    def update_progress(self, progress: float, message: str = ""):
        """
        Update the progress display.

        Args:
            progress: Progress value (0.0 to 1.0)
            message: Progress message
        """
        if self._dialog:
            self._progress_var.set(progress * 100)
            if message:
                self._message_var.set(message)
            self._dialog.update()

    def _on_cancel(self):
        """Handle cancel button click."""
        self.cancelled = True
