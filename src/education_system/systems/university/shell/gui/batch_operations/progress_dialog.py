"""
Batch Operations GUI - Progress Dialog

Custom progress dialog for GUI operations with ETA tracking
and cancel support.

Batch operations run on worker threads, and this dialog is constructed,
updated and closed from those threads — a backend often gets
``update_progress`` handed to it as a progress callback. Tk is
single-threaded, so the widget work is marshalled onto the main loop here,
once, rather than at every call site: construction blocks the worker just
long enough for the main loop to build the window, and updates/close are
fire-and-forget. Callers need no thread awareness.
"""

from education_system.systems.university.shell.gui.batch_operations.constants import tk, ttk, time, Progressbar, _t
from education_system.systems.university.shell.gui.batch_operations.thread_ui import call_and_wait, post


class GUIProgressDialog:
    """Custom progress dialog for GUI operations"""

    def __init__(self, parent, title=_t("batch_ops.labels.processing"), operation_name=_t("batch_ops.labels.processing")):
        self.parent = parent
        self.operation_name = operation_name

        # Progress tracking
        self.start_time = time.time()
        self.total_items = 0
        self.current_item = 0
        self.cancelled = False

        # Widgets are built on the main loop; the worker waits for them so the
        # object is fully usable when the constructor returns.
        call_and_wait(parent, lambda: self._build(parent, title, operation_name))

    def _build(self, parent, title, operation_name):
        """Create the dialog's widgets. Main loop only."""
        # Create dialog window
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("500x200")
        self.dialog.resizable(False, False)
        self.dialog.transient(parent)
        self.dialog.grab_set()

        # Center the dialog
        self.dialog.geometry("+%d+%d" % (parent.winfo_rootx() + 50, parent.winfo_rooty() + 50))

        # Main frame
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Operation label
        self.operation_label = ttk.Label(main_frame, text=operation_name, font=("Arial", 12, "bold"))
        self.operation_label.pack(pady=(0, 10))

        # Progress bar
        self.progress_var = tk.DoubleVar()
        self.progress_bar = Progressbar(main_frame, variable=self.progress_var, maximum=100, length=400)
        self.progress_bar.pack(pady=(0, 10))

        # Status label
        self.status_label = ttk.Label(main_frame, text=_t("batch_ops.labels.starting"))
        self.status_label.pack(pady=(0, 10))

        # ETA label
        self.eta_label = ttk.Label(main_frame, text="")
        self.eta_label.pack(pady=(0, 10))

        # Cancel button
        self.cancel_button = ttk.Button(main_frame, text=_t("batch_ops.buttons.cancel"), command=self.cancel_operation)
        self.cancel_button.pack(pady=(10, 0))

    def set_total(self, total_items):
        """Set total number of items to process"""
        self.total_items = total_items

    def update_progress(self, current_item, status_text=""):
        """Update progress display. Safe to call from a worker thread."""
        self.current_item = current_item

        if self.total_items > 0:
            percentage = (current_item / self.total_items) * 100

            # Calculate ETA
            elapsed_time = time.time() - self.start_time
            if current_item > 0:
                estimated_total_time = elapsed_time * (self.total_items / current_item)
                eta = estimated_total_time - elapsed_time
                eta_str = f"ETA: {int(eta//60)}:{int(eta%60):02d}"
            else:
                eta_str = "ETA: --:--"

            status = f"{current_item}/{self.total_items} - {status_text}"
        else:
            percentage = None
            eta_str = None
            status = status_text

        def apply():
            if percentage is not None:
                self.progress_var.set(percentage)
                self.eta_label.config(text=eta_str)
            self.status_label.config(text=status)

        # The main loop repaints itself; the old dialog.update() forced it from
        # whichever thread happened to be reporting progress.
        post(self.dialog, apply)

    def cancel_operation(self):
        """Cancel the current operation"""
        self.cancelled = True
        self.cancel_button.config(state="disabled", text=_t("batch_ops.labels.cancelling"))

    def close(self):
        """Close the progress dialog. Safe to call from a worker thread."""
        def destroy():
            if self.dialog.winfo_exists():
                self.dialog.grab_release()
                self.dialog.destroy()

        post(self.dialog, destroy)
