"""PDF Export GUI for University Management System.

This module provides a graphical interface for exporting database data to PDF
with options for charts, tables, and customization.
"""

from __future__ import annotations

import logging
import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from education_system.university_system.infrastructure.auth import UserAuth

# Import internationalization (i18n) for multi-language support
try:
    from education_system.university_system.core.i18n import (
        get_text as _t,
        get_current_language,
    )
    I18N_AVAILABLE = True
except ImportError:
    I18N_AVAILABLE = False
    _t = lambda key, **kwargs: key if "default" not in kwargs else kwargs.get("default")  # Fallback: return default or key
    get_current_language = lambda: "en"

logger = logging.getLogger(__name__)


class PDFExportGUI:
    """GUI interface for PDF database export."""

    def __init__(self, root: tk.Tk, auth: Optional["UserAuth"] = None):
        """Initialize the PDF Export GUI.

        Args:
            root: Parent Tkinter window.
            auth: Optional authentication manager.
        """
        self.root = root
        self.auth = auth
        self.export_window: Optional[tk.Toplevel] = None
        self.progress_var = tk.DoubleVar(value=0)
        self.status_var = tk.StringVar(value="Ready")
        self.is_exporting = False

    def show_export_window(self):
        """Display the PDF export dialog window."""
        if self.export_window and self.export_window.winfo_exists():
            self.export_window.lift()
            return

        self.export_window = tk.Toplevel(self.root)
        self.export_window.title(_t("pdf_export.window_title", default="PDF Database Export"))
        self.export_window.geometry("600x550")
        self.export_window.minsize(500, 450)
        self.export_window.transient(self.root)

        # Center window
        self.export_window.update_idletasks()
        x = (self.export_window.winfo_screenwidth() - 600) // 2
        y = (self.export_window.winfo_screenheight() - 550) // 2
        self.export_window.geometry(f"+{x}+{y}")

        self._create_widgets()
        self._load_preview()

    def _create_widgets(self):
        """Create the GUI widgets."""
        main_frame = ttk.Frame(self.export_window, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        title_label = ttk.Label(
            main_frame,
            text=_t("pdf_export.title", default="Export Database to PDF"),
            font=("Arial", 14, "bold"),
        )
        title_label.pack(pady=(0, 10))

        description = ttk.Label(
            main_frame,
            text=_t("pdf_export.description", default="Generate a comprehensive PDF report with charts, tables, and statistics."),
            wraplength=500,
        )
        description.pack(pady=(0, 15))

        # Options Frame
        options_frame = ttk.LabelFrame(main_frame, text=_t("pdf_export.export_options", default="Export Options"), padding="10")
        options_frame.pack(fill=tk.X, pady=(0, 10))

        # Include data checkbox
        self.include_data_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            options_frame,
            text=_t("pdf_export.include_table_data", default="Include table data (first N rows of each table)"),
            variable=self.include_data_var,
        ).grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=2)

        # Include charts checkbox
        self.include_charts_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            options_frame,
            text=_t("pdf_export.include_charts", default="Include charts and visualizations"),
            variable=self.include_charts_var,
        ).grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=2)

        # Max rows per table
        ttk.Label(options_frame, text=_t("pdf_export.max_rows_per_table", default="Max rows per table:")).grid(
            row=2, column=0, sticky=tk.W, pady=5
        )
        self.max_rows_var = tk.StringVar(value="50")
        max_rows_entry = ttk.Entry(options_frame, textvariable=self.max_rows_var, width=10)
        max_rows_entry.grid(row=2, column=1, sticky=tk.W, pady=5)

        # Output location frame
        output_frame = ttk.LabelFrame(main_frame, text=_t("pdf_export.output_location", default="Output Location"), padding="10")
        output_frame.pack(fill=tk.X, pady=(0, 10))

        self.output_path_var = tk.StringVar()
        output_entry = ttk.Entry(output_frame, textvariable=self.output_path_var, width=50)
        output_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))

        browse_btn = ttk.Button(output_frame, text=_t("common.browse", default="Browse..."), command=self._browse_output)
        browse_btn.pack(side=tk.RIGHT)

        # Set default output path
        try:
            from education_system.university_system.core import paths
            from datetime import datetime

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            default_path = os.path.join(str(paths.EXPORTS_PDF_DIR), f"database_export_{timestamp}.pdf")
            self.output_path_var.set(default_path)
        except Exception:
            self.output_path_var.set("database_export.pdf")

        # Preview Frame
        preview_frame = ttk.LabelFrame(main_frame, text=_t("pdf_export.export_preview", default="Export Preview"), padding="10")
        preview_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Preview text area
        self.preview_text = tk.Text(preview_frame, height=8, width=60, state=tk.DISABLED)
        preview_scrollbar = ttk.Scrollbar(preview_frame, command=self.preview_text.yview)
        self.preview_text.configure(yscrollcommand=preview_scrollbar.set)

        self.preview_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        preview_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Progress Frame
        progress_frame = ttk.Frame(main_frame)
        progress_frame.pack(fill=tk.X, pady=(0, 10))

        self.progress_bar = ttk.Progressbar(
            progress_frame,
            variable=self.progress_var,
            maximum=100,
            mode="determinate",
        )
        self.progress_bar.pack(fill=tk.X, pady=(0, 5))

        status_label = ttk.Label(progress_frame, textvariable=self.status_var)
        status_label.pack()

        # Buttons Frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)

        self.export_btn = ttk.Button(
            button_frame,
            text=_t("pdf_export.export_to_pdf", default="Export to PDF"),
            command=self._start_export,
            style="Accent.TButton",
        )
        self.export_btn.pack(side=tk.LEFT, padx=(0, 10))

        self.cancel_btn = ttk.Button(
            button_frame,
            text=_t("common.cancel", default="Cancel"),
            command=self._close_window,
        )
        self.cancel_btn.pack(side=tk.LEFT)

        refresh_btn = ttk.Button(
            button_frame,
            text=_t("pdf_export.refresh_preview", default="Refresh Preview"),
            command=self._load_preview,
        )
        refresh_btn.pack(side=tk.RIGHT)

    def _browse_output(self):
        """Open file dialog to select output location."""
        filename = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
            initialdir=os.path.dirname(self.output_path_var.get()),
            title=_t("pdf_export.save_as_title", default="Save PDF Export As"),
        )
        if filename:
            self.output_path_var.set(filename)

    def _load_preview(self):
        """Load and display the export preview."""
        self.preview_text.configure(state=tk.NORMAL)
        self.preview_text.delete(1.0, tk.END)
        self.preview_text.insert(tk.END, _t("pdf_export.loading_preview", default="Loading preview...") + "\n")
        self.preview_text.configure(state=tk.DISABLED)

        def load_in_thread():
            try:
                from education_system.university_system.modules.shared.services.pdf_export import PDFExportManager

                manager = PDFExportManager()
                preview = manager.get_export_preview()

                stats = preview.get("statistics", {})
                categories = preview.get("categories", {})

                preview_lines = [
                    "DATABASE EXPORT PREVIEW",
                    "=" * 40,
                    "",
                    f"Total Tables: {stats.get('total_tables', 0)}",
                    f"Total Records: {stats.get('total_records', 0):,}",
                    f"Tables with Data: {stats.get('tables_with_data', 0)}",
                    f"Empty Tables: {stats.get('empty_tables', 0)}",
                    f"Estimated Pages: ~{preview.get('estimated_pages', 0)}",
                    "",
                    "CATEGORIES:",
                    "-" * 30,
                ]

                for category, info in categories.items():
                    table_count = info.get("table_count", 0)
                    total_rows = sum(t.get("rows", 0) for t in info.get("tables", []))
                    preview_lines.append(f"  {category}: {table_count} tables, {total_rows:,} rows")

                preview_lines.extend(["", "TOP TABLES BY SIZE:", "-" * 30])

                largest = stats.get("largest_tables", [])[:8]
                for table_name, count in largest:
                    display_name = table_name.replace("_", " ").title()[:25]
                    preview_lines.append(f"  {display_name}: {count:,} records")

                preview_text = "\n".join(preview_lines)

                self._safe_after(lambda: self._update_preview(preview_text))

            except Exception as e:
                error_msg = f"Error loading preview: {e}"
                logger.error(error_msg)
                self._safe_after(lambda: self._update_preview(error_msg))

        thread = threading.Thread(target=load_in_thread, daemon=True)
        thread.start()

    def _update_preview(self, text: str):
        """Update the preview text widget."""
        self.preview_text.configure(state=tk.NORMAL)
        self.preview_text.delete(1.0, tk.END)
        self.preview_text.insert(tk.END, text)
        self.preview_text.configure(state=tk.DISABLED)

    def _start_export(self):
        """Start the PDF export process."""
        if self.is_exporting:
            messagebox.showwarning(
                _t("pdf_export.export_in_progress_title", default="Export in Progress"),
                _t("pdf_export.export_in_progress_msg", default="An export is already in progress.")
            )
            return

        output_path = self.output_path_var.get().strip()
        if not output_path:
            messagebox.showerror(
                _t("common.error", default="Error"),
                _t("pdf_export.specify_output_path", default="Please specify an output file path.")
            )
            return

        try:
            max_rows = int(self.max_rows_var.get())
            if max_rows < 1:
                raise ValueError(_t("pdf_export.max_rows_at_least_1", default="Max rows must be at least 1"))
        except ValueError as e:
            messagebox.showerror(
                _t("common.error", default="Error"),
                _t("pdf_export.invalid_max_rows", default="Invalid max rows value: {error}").format(error=e)
            )
            return

        self.is_exporting = True
        self.export_btn.configure(state=tk.DISABLED)
        self.progress_var.set(0)
        self.status_var.set(_t("pdf_export.starting_export", default="Starting export..."))

        def export_thread():
            try:
                from education_system.university_system.modules.shared.services.pdf_export import PDFExportManager

                manager = PDFExportManager()

                # Ensure output directory exists
                output_dir = os.path.dirname(output_path)
                if output_dir:
                    os.makedirs(output_dir, exist_ok=True)

                manager.output_dir = output_dir if output_dir else manager.output_dir

                def progress_callback(msg, pct):
                    self._safe_after(lambda: self._update_progress(msg, pct))

                result_path = manager.export_full_database(
                    output_filename=os.path.basename(output_path),
                    include_data=self.include_data_var.get(),
                    include_charts=self.include_charts_var.get(),
                    max_rows_per_table=max_rows,
                    progress_callback=progress_callback,
                )

                self._safe_after(lambda: self._export_complete(result_path))

            except Exception as e:
                error_msg = str(e)
                logger.error(f"Export failed: {error_msg}")
                self._safe_after(lambda: self._export_failed(error_msg))

        thread = threading.Thread(target=export_thread, daemon=True)
        thread.start()

    def _update_progress(self, message: str, percent: int):
        """Update progress bar and status."""
        self.progress_var.set(percent)
        self.status_var.set(message)

    def _export_complete(self, output_path: str):
        """Handle successful export completion."""
        self.is_exporting = False
        self.export_btn.configure(state=tk.NORMAL)
        self.progress_var.set(100)
        self.status_var.set(_t("pdf_export.export_complete", default="Export complete!"))

        result = messagebox.askyesno(
            _t("pdf_export.export_complete_title", default="Export Complete"),
            _t("pdf_export.export_complete_msg", default="PDF exported successfully to:\n{path}\n\nWould you like to open the file?").format(path=output_path),
        )

        if result:
            try:
                import subprocess
                import sys

                if sys.platform == "darwin":
                    subprocess.run(["open", output_path], check=True)
                elif sys.platform == "win32":
                    os.startfile(output_path)
                else:
                    subprocess.run(["xdg-open", output_path], check=True)
            except Exception as e:
                messagebox.showwarning(
                    _t("common.warning", default="Warning"),
                    _t("pdf_export.could_not_open_file", default="Could not open file: {error}").format(error=e)
                )

    def _export_failed(self, error_message: str):
        """Handle export failure."""
        self.is_exporting = False
        self.export_btn.configure(state=tk.NORMAL)
        self.status_var.set(_t("pdf_export.export_failed", default="Export failed"))
        messagebox.showerror(
            _t("pdf_export.export_failed_title", default="Export Failed"),
            _t("pdf_export.export_failed_msg", default="Failed to export PDF:\n{error}").format(error=error_message)
        )

    def _safe_after(self, callback):
        """Safely schedule a callback on the main thread.

        Args:
            callback: The function to call on the main thread.

        Returns:
            True if callback was scheduled, False if window is gone.
        """
        try:
            if self.export_window and self.export_window.winfo_exists():
                self.export_window.after(0, callback)
                return True
        except tk.TclError:
            # Window was destroyed
            pass
        return False

    def _close_window(self):
        """Close the export window."""
        if self.is_exporting:
            if not messagebox.askyesno(
                _t("pdf_export.cancel_export_title", default="Cancel Export"),
                _t("pdf_export.cancel_export_msg", default="An export is in progress. Are you sure you want to cancel?"),
            ):
                return

        if self.export_window:
            self.export_window.destroy()
            self.export_window = None


def show_pdf_export_gui(root: tk.Tk, auth: Optional["UserAuth"] = None):
    """Convenience function to show the PDF export GUI.

    Args:
        root: Parent Tkinter window.
        auth: Optional authentication manager.
    """
    gui = PDFExportGUI(root, auth)
    gui.show_export_window()
