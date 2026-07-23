"""GUI utility mixin for the Student Analytics GUI."""
from education_system.post_18.university_system.modules.shared.gui.student_analytics_gui._imports import (
    tk, ttk, messagebox, filedialog, scrolledtext,
    plt, sys, queue, _t, CONFIG,
)


class GUIUtilsMixin:
    """Mixin providing output capture, navigation, dialog launchers, and misc utilities."""

    def setup_output_capture(self):
        """Setup output capture for console messages"""
        class OutputCapture:
            def __init__(self, queue_obj):
                self.queue = queue_obj
                self.original_stdout = sys.stdout

            def write(self, text):
                self.queue.put(text)
                self.original_stdout.write(text)

            def flush(self):
                self.original_stdout.flush()

        # Redirect stdout to capture print statements. Keep the original on
        # self so on_closing() can restore it — otherwise prints after the
        # window closes go into an undrained queue.
        self._original_stdout = sys.stdout
        sys.stdout = OutputCapture(self.output_queue)

    def monitor_output(self):
        """Monitor the output queue and update GUI"""
        # Bail if the window is gone; otherwise the rescheduled after()
        # fires against a destroyed interpreter and Tk logs
        # `invalid command name "...monitor_output"`.
        try:
            if not self.root.winfo_exists():
                return
        except tk.TclError:
            return

        try:
            while True:
                text = self.output_queue.get_nowait()
                self.output_text.insert('end', text)
                self.output_text.see('end')
        except queue.Empty:
            pass

        # Schedule next check
        try:
            self._monitor_after_id = self.root.after(100, self.monitor_output)
        except tk.TclError:
            self._monitor_after_id = None

    def clear_output(self):
        """Clear the output text area"""
        self.output_text.delete('1.0', 'end')

    def save_output(self):
        """Save output to file"""
        filename = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[(_t("analytics.file_types.text_files"), "*.txt"), (_t("common.all_files"), "*.*")]
        )
        if filename:
            with open(filename, 'w') as f:
                f.write(self.output_text.get('1.0', 'end'))
            messagebox.showinfo(_t("analytics.dialogs.saved"),
                               _t("analytics.messages.output_saved", filename=filename))

    def copy_output(self):
        """Copy output to clipboard"""
        self.root.clipboard_clear()
        self.root.clipboard_append(self.output_text.get('1.0', 'end'))
        messagebox.showinfo(_t("analytics.dialogs.copied"),
                           _t("analytics.messages.output_copied"))

    def test_database(self):
        """Test database connection"""
        from education_system.post_18.university_system.infrastructure.database.db import sqlite3
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM students")
            count = cursor.fetchone()[0]

            messagebox.showinfo(_t("analytics.dialogs.database_test"),
                               _t("analytics.messages.database_success", count=count))

        except sqlite3.Error as e:
            if conn:
                conn.rollback()
            messagebox.showerror(_t("analytics.dialogs.database_error"),
                                _t("analytics.error.database_failed", error=str(e)))

        except Exception as e:
            if conn:
                conn.rollback()
            messagebox.showerror(_t("analytics.dialogs.database_error"),
                                _t("analytics.error.database_failed", error=str(e)))

        finally:
            if conn:
                conn.close()

    def refresh_data(self):
        """Refresh data cache"""
        self.custom_filters.clear()
        self.refresh_stats()
        messagebox.showinfo(_t("analytics.dialogs.data_refreshed"),
                           _t("analytics.messages.data_refreshed"))

    def clear_filters(self):
        """Clear all applied filters"""
        self.analytics.custom_filters.clear()
        self.update_filter_status()
        messagebox.showinfo(_t("analytics.dialogs.filters_cleared"),
                           _t("analytics.messages.filters_cleared"))

    def update_filter_status(self):
        """Update filter status display"""
        if self.analytics.custom_filters:
            filter_count = len(self.analytics.custom_filters)
            self.filter_status.config(text=_t("analytics.messages.filters_applied_count", filter_count=filter_count))
        else:
            self.filter_status.config(text=_t("analytics.messages.no_filters_applied"))

    def return_to_main_menu(self):
        """Return to the main menu"""
        try:
            # Use the gui_launcher utility to avoid circular imports
            from education_system.post_18.university_system.modules.shared.gui.gui_launcher import return_to_main_menu
            return_to_main_menu(self, self.auth)
        except Exception as e:
            print(f"Error returning to main menu: {e}")
            import traceback
            traceback.print_exc()

    # Dialog launchers

    def show_filters_dialog(self):
        """Show advanced filters dialog"""
        from education_system.post_18.university_system.modules.shared.gui.student_analytics_gui.dialogs import FilterDialog
        dialog = FilterDialog(self.root, self.analytics)
        self.root.wait_window(dialog.dialog)
        self.update_filter_status()

    def show_custom_report_dialog(self):
        """Show custom report builder dialog"""
        from education_system.post_18.university_system.modules.shared.gui.student_analytics_gui.dialogs import CustomReportDialog
        dialog = CustomReportDialog(self.root, self.analytics)
        self.root.wait_window(dialog.dialog)

    def show_config_dialog(self):
        """Show configuration dialog"""
        from education_system.post_18.university_system.modules.shared.gui.student_analytics_gui.dialogs import ConfigDialog
        dialog = ConfigDialog(self.root, self.analytics)
        self.root.wait_window(dialog.dialog)

    def show_color_dialog(self):
        """Show color scheme dialog"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Color Scheme Settings")
        dialog.geometry("500x400")
        dialog.transient(self.root)
        dialog.grab_set()

        # Create main frame
        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_t("analytics.dialogs.color_scheme_settings"), font=('Arial', 14, 'bold')).pack(pady=10)

        # Color scheme selection
        ttk.Label(main_frame, text=_t("analytics.labels.select_color_scheme")).pack(pady=5)

        schemes = {
            "Default": ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b'],
            "Viridis": ['#440154', '#31688e', '#35b779', '#fde724', '#90d743', '#21918c'],
            "Pastel": ['#aec7e8', '#ffbb78', '#98df8a', '#ff9896', '#c5b0d5', '#c49c94'],
            "Bold": ['#e41a1c', '#377eb8', '#4daf4a', '#984ea3', '#ff7f00', '#ffff33']
        }

        selected_scheme = tk.StringVar(value="Default")

        for scheme_name in schemes.keys():
            ttk.Radiobutton(main_frame, text=scheme_name, variable=selected_scheme,
                          value=scheme_name).pack(anchor=tk.W, padx=20)

        # Preview frame
        preview_frame = ttk.LabelFrame(main_frame, text=_t("analytics.labels.preview"), padding="10")
        preview_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        preview_canvas = tk.Canvas(preview_frame, height=100)
        preview_canvas.pack(fill=tk.BOTH, expand=True)

        def update_preview(*args):
            preview_canvas.delete("all")
            colors = schemes[selected_scheme.get()]
            width = 400 // len(colors)
            for i, color in enumerate(colors):
                preview_canvas.create_rectangle(i*width, 0, (i+1)*width, 100, fill=color, outline="")

        selected_scheme.trace('w', update_preview)
        update_preview()

        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=10)

        def apply_colors():
            CONFIG['colors'] = schemes[selected_scheme.get()]
            messagebox.showinfo(_t("common.success"), _t("analytics.messages.color_scheme_applied"))
            dialog.destroy()

        ttk.Button(button_frame, text=_t("common.apply"), command=apply_colors).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_t("common.cancel"), command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def show_export_dialog(self):
        """Show export preferences dialog"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_t("analytics.dialogs.export_preferences"))
        dialog.geometry("500x450")
        dialog.transient(self.root)
        dialog.grab_set()

        # Create main frame
        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_t("analytics.dialogs.export_preferences"), font=('Arial', 14, 'bold')).pack(pady=10)

        # Export format section
        format_frame = ttk.LabelFrame(main_frame, text=_t("analytics.labels.export_formats"), padding="10")
        format_frame.pack(fill=tk.X, pady=10)

        formats = {
            'PNG': tk.BooleanVar(value=True),
            'PDF': tk.BooleanVar(value=False),
            'SVG': tk.BooleanVar(value=False),
            'Excel': tk.BooleanVar(value=False)
        }

        for fmt, var in formats.items():
            ttk.Checkbutton(format_frame, text=fmt, variable=var).pack(anchor=tk.W)

        # Quality settings
        quality_frame = ttk.LabelFrame(main_frame, text=_t("analytics.labels.quality_settings"), padding="10")
        quality_frame.pack(fill=tk.X, pady=10)

        ttk.Label(quality_frame, text=_t("analytics.labels.dpi")).grid(row=0, column=0, sticky=tk.W, pady=5)
        dpi_var = tk.StringVar(value=str(CONFIG['dpi']))
        dpi_combo = ttk.Combobox(quality_frame, textvariable=dpi_var, values=['150', '300', '600'], width=10)
        dpi_combo.grid(row=0, column=1, sticky=tk.W, pady=5)

        ttk.Label(quality_frame, text=_t("analytics.labels.figure_size")).grid(row=1, column=0, sticky=tk.W, pady=5)
        size_var = tk.StringVar(value="15x10")
        size_combo = ttk.Combobox(quality_frame, textvariable=size_var, values=['10x8', '15x10', '20x15'], width=10)
        size_combo.grid(row=1, column=1, sticky=tk.W, pady=5)

        # File naming
        naming_frame = ttk.LabelFrame(main_frame, text=_t("analytics.labels.file_naming"), padding="10")
        naming_frame.pack(fill=tk.X, pady=10)

        ttk.Label(naming_frame, text=_t("analytics.labels.prefix")).grid(row=0, column=0, sticky=tk.W, pady=5)
        prefix_var = tk.StringVar(value="analytics_")
        ttk.Entry(naming_frame, textvariable=prefix_var, width=20).grid(row=0, column=1, sticky=tk.W, pady=5)

        include_timestamp = tk.BooleanVar(value=True)
        ttk.Checkbutton(naming_frame, text=_t("analytics.labels.include_timestamp"),
                       variable=include_timestamp).grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=5)

        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=10)

        def apply_settings():
            # Parse figure size
            width, height = map(int, size_var.get().split('x'))
            CONFIG['figure_size'] = (width, height)
            CONFIG['dpi'] = int(dpi_var.get())
            CONFIG['export_formats'] = [fmt.lower() for fmt, var in formats.items() if var.get()]

            messagebox.showinfo(_t("common.success"), _t("analytics.messages.export_preferences_saved"))
            dialog.destroy()

        ttk.Button(button_frame, text=_t("common.apply"), command=apply_settings).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_t("common.cancel"), command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def show_help(self):
        """Show help documentation"""
        help_text = _t("analytics.help.content")

        help_window = tk.Toplevel(self.root)
        help_window.title(_t("analytics.dialogs.help"))
        help_window.geometry("600x500")

        text_widget = scrolledtext.ScrolledText(help_window, wrap='word')
        text_widget.pack(fill='both', expand=True, padx=10, pady=10)
        text_widget.insert('1.0', help_text)
        text_widget.config(state='disabled')

    def show_about(self):
        """Show about dialog"""
        about_text = _t("analytics.about.content")
        messagebox.showinfo(_t("analytics.dialogs.about"), about_text)

    def show_system_info(self):
        """Show system information"""
        import platform
        import matplotlib

        info = _t("analytics.system_info.content",
                  platform=platform.platform(),
                  python_version=platform.python_version(),
                  matplotlib_version=matplotlib.__version__,
                  gui_backend=matplotlib.get_backend(),
                  database=self.analytics.db_path,
                  plots_dir=self.analytics.plots_dir,
                  reports_dir=self.analytics.reports_dir)
        messagebox.showinfo(_t("analytics.dialogs.system_info"), info)
