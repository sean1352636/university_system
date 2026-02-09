import logging
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
from datetime import datetime, timedelta
from typing import Any, Optional, List, Dict
from university_system.modules.shared.utils.i18n import get_text as _
from university_system.modules.domain.academics.gui.academic_calendar.utils import safe_grab_set

gui_logger = logging.getLogger(__name__)

class ExportDialog:
    """Dialog for exporting calendar data"""

    def __init__(self, parent, calendar_manager):
        self.calendar_manager = calendar_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_("academic_calendar.dialogs.export.title"))
        self.dialog.geometry("450x400")
        self.dialog.transient(parent)
        safe_grab_set(self.dialog, parent)

        self._create_widgets()
        self._center_dialog()

    def _create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        ttk.Label(main_frame, text=_("academic_calendar.dialogs.export.header"), 
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))
        
        # Export format
        format_frame = ttk.LabelFrame(main_frame, text=_("academic_calendar.labels.export_format"), padding=10)
        format_frame.pack(fill=tk.X, pady=(0, 15))

        self.format_var = tk.StringVar(value="csv")
        formats = [
            ("CSV", "csv"),
            ("Excel", "xlsx"),
            ("PDF", "pdf"),
            ("JSON", "json"),
            ("iCal", "ics"),
            ("Text", "txt")
        ]

        for i, (label, value) in enumerate(formats):
            ttk.Radiobutton(format_frame, text=label, variable=self.format_var,
                           value=value).grid(row=i//2, column=i%2, sticky=tk.W, padx=10, pady=2)

        # Academic year filter
        filter_frame = ttk.LabelFrame(main_frame, text=_("academic_calendar.labels.filter_options"), padding=10)
        filter_frame.pack(fill=tk.X, pady=(0, 15))

        ttk.Label(filter_frame, text=_("academic_calendar.labels.academic_year_optional")).pack(anchor=tk.W)
        self.year_var = tk.StringVar()
        year_combo = ttk.Combobox(filter_frame, textvariable=self.year_var, width=40)
        year_combo.pack(fill=tk.X, pady=(5, 0))

        # Load academic years
        try:
            years = self.calendar_manager.db_manager.execute_query(
                "SELECT id FROM academic_years ORDER BY start_date DESC"
            )
            year_list = [_("academic_calendar.labels.all_years")] + [year['id'] for year in years]
            year_combo['values'] = year_list
            self.year_var.set(_("academic_calendar.labels.all_years"))
        except Exception as e:
            gui_logger.warning(f"Failed to load academic years for export: {e}")

        # File selection
        file_frame = ttk.LabelFrame(main_frame, text=_("academic_calendar.labels.output_file"), padding=10)
        file_frame.pack(fill=tk.X, pady=(0, 15))

        self.file_var = tk.StringVar()
        file_entry = ttk.Entry(file_frame, textvariable=self.file_var, width=35)
        file_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        ttk.Button(file_frame, text=_("academic_calendar.buttons.browse"),
                  command=self._browse_file).pack(side=tk.RIGHT, padx=(10, 0))

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(20, 0))

        ttk.Button(button_frame, text=_("common.cancel"), command=self.dialog.destroy).pack(side=tk.RIGHT, padx=(10, 0))
        ttk.Button(button_frame, text=_("academic_calendar.buttons.export_action"), command=self._export_calendar).pack(side=tk.RIGHT)
    
    def _browse_file(self):
        """Browse for output file"""
        format_ext = self.format_var.get()
        filetypes = {
            'csv': [("CSV files", "*.csv"), ("All files", "*.*")],
            'xlsx': [("Excel files", "*.xlsx"), ("All files", "*.*")],
            'pdf': [("PDF files", "*.pdf"), ("All files", "*.*")],
            'json': [("JSON files", "*.json"), ("All files", "*.*")],
            'ics': [("iCal files", "*.ics"), ("All files", "*.*")],
            'txt': [("Text files", "*.txt"), ("All files", "*.*")]
        }
        
        filename = filedialog.asksaveasfilename(
            title=_("academic_calendar.dialogs.import_calendar.save_export_as"),
            defaultextension=f".{format_ext}",
            filetypes=filetypes.get(format_ext, [("All files", "*.*")])
        )
        
        if filename:
            self.file_var.set(filename)
    
    def _center_dialog(self):
        """Center dialog on parent"""
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")
    
    def _export_calendar(self):
        """Export calendar"""
        try:
            format_type = self.format_var.get()
            file_path = self.file_var.get().strip()
            academic_year = self.year_var.get()
            
            if not file_path:
                messagebox.showerror(_("common.error"), _("academic_calendar.messages.select_output_file"))
                return

            academic_year = academic_year if academic_year != _("academic_calendar.labels.all_years") else None

            result = self.calendar_manager.export_calendar(file_path, format_type, academic_year)

            if result['success']:
                messagebox.showinfo(_("common.success"), result['message'])
                if messagebox.askyesno(_("academic_calendar.messages.open_file"), _("academic_calendar.messages.open_file_prompt")):
                    try:
                        self.calendar_manager.safe_open_file(result['file_path'])
                    except Exception as e:
                        messagebox.showerror(_("common.error"), _("academic_calendar.messages.could_not_open_file").format(error=e))
                self.dialog.destroy()
            else:
                messagebox.showerror(_("common.error"), result['message'])

        except Exception as e:
            messagebox.showerror(_("common.error"), _("academic_calendar.messages.export_failed").format(error=e))


class ImportCalendarDialog:
    """Dialog for importing calendar data"""
    
    def __init__(self, parent, calendar_manager, callback=None):
        self.calendar_manager = calendar_manager
        self.callback = callback
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_("academic_calendar.dialogs.import_calendar.title"))
        self.dialog.geometry("400x300")
        self.dialog.transient(parent)
        safe_grab_set(self.dialog, parent)

        self._create_widgets()
        self._center_dialog()

    def _create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_("academic_calendar.dialogs.import_calendar.header"),
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Import options
        options_frame = ttk.LabelFrame(main_frame, text=_("academic_calendar.dialogs.import_calendar.import_options"), padding=10)
        options_frame.pack(fill=tk.X, pady=(0, 15))

        self.import_type = tk.StringVar(value="file")
        ttk.Radiobutton(options_frame, text=_("academic_calendar.dialogs.import_calendar.import_from_file"),
                       variable=self.import_type, value="file").pack(anchor=tk.W)
        ttk.Radiobutton(options_frame, text=_("academic_calendar.dialogs.import_calendar.import_from_url"),
                       variable=self.import_type, value="url").pack(anchor=tk.W)

        # File/URL input
        input_frame = ttk.Frame(main_frame)
        input_frame.pack(fill=tk.X, pady=(0, 15))

        ttk.Label(input_frame, text=_("academic_calendar.dialogs.import_calendar.file_url_label")).pack(anchor=tk.W)

        file_frame = ttk.Frame(input_frame)
        file_frame.pack(fill=tk.X, pady=(5, 0))

        self.file_var = tk.StringVar()
        ttk.Entry(file_frame, textvariable=self.file_var).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(file_frame, text=_("academic_calendar.buttons.browse"),
                  command=self._browse_file).pack(side=tk.RIGHT, padx=(10, 0))

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(20, 0))

        ttk.Button(button_frame, text=_("common.cancel"), command=self.dialog.destroy).pack(side=tk.RIGHT, padx=(10, 0))
        ttk.Button(button_frame, text=_("academic_calendar.buttons.import"), command=self._import_calendar).pack(side=tk.RIGHT)
    
    def _browse_file(self):
        """Browse for import file"""
        filename = filedialog.askopenfilename(
            title=_("academic_calendar.dialogs.import_calendar.select_calendar_file"),
            filetypes=[
                ("iCal files", "*.ics"),
                ("CSV files", "*.csv"),
                ("JSON files", "*.json"),
                ("All files", "*.*")
            ]
        )

        if filename:
            self.file_var.set(filename)

    def _import_calendar(self):
        """Import calendar"""
        try:
            source = self.file_var.get().strip()
            if not source:
                messagebox.showerror(_("common.error"), _("academic_calendar.messages.select_file_or_url"))
                return

            if self.import_type.get() == "url":
                # Import from URL (iCal sync)
                result = self.calendar_manager.calendar_sync(source)
                message = _("academic_calendar.messages.import_success").format(count=result['synced'])
                messagebox.showinfo(_("common.success"), message)
            else:
                # Import from file
                if not os.path.exists(source):
                    messagebox.showerror(_("common.error"), _("academic_calendar.messages.file_not_exist"))
                    return

                imported_count = 0
                error_count = 0

                # Determine file type and import accordingly
                file_ext = os.path.splitext(source)[1].lower()

                if file_ext == '.ics':
                    # Import iCal file
                    try:
                        import ics
                        with open(source, 'r', encoding='utf-8') as f:
                            calendar_data = ics.Calendar(f.read())

                        for event in calendar_data.events:
                            try:
                                # Convert ics event to our format
                                self.calendar_manager.create_event(
                                    title=str(event.name) if event.name else "Imported Event",
                                    start_datetime=event.begin.datetime if event.begin else datetime.now(),
                                    end_datetime=event.end.datetime if event.end else datetime.now() + timedelta(hours=1),
                                    description=str(event.description) if event.description else "",
                                    location=str(event.location) if event.location else ""
                                )
                                imported_count += 1
                            except Exception:
                                error_count += 1
                    except ImportError:
                        messagebox.showerror(_("common.error"), _("academic_calendar.messages.ics_library_unavailable"))
                        return

                elif file_ext == '.json':
                    # Import JSON file
                    try:
                        with open(source, 'r', encoding='utf-8') as f:
                            data = json.load(f)

                        events = data if isinstance(data, list) else data.get('events', [])

                        for event_data in events:
                            try:
                                start_dt = datetime.fromisoformat(event_data.get('start_datetime', datetime.now().isoformat()))
                                end_dt = datetime.fromisoformat(event_data.get('end_datetime', (start_dt + timedelta(hours=1)).isoformat()))

                                self.calendar_manager.create_event(
                                    title=event_data.get('title', 'Imported Event'),
                                    start_datetime=start_dt,
                                    end_datetime=end_dt,
                                    description=event_data.get('description', ''),
                                    location=event_data.get('location', ''),
                                    category=event_data.get('category', 'imported')
                                )
                                imported_count += 1
                            except Exception:
                                error_count += 1
                    except json.JSONDecodeError:
                        messagebox.showerror(_("common.error"), _("academic_calendar.messages.invalid_json_format"))
                        return

                elif file_ext == '.csv':
                    # Import CSV file
                    try:
                        import csv
                        with open(source, 'r', encoding='utf-8') as f:
                            reader = csv.DictReader(f)

                            for row in reader:
                                try:
                                    start_dt = datetime.strptime(row.get('start_datetime', ''), '%Y-%m-%d %H:%M:%S')
                                    end_dt = datetime.strptime(row.get('end_datetime', ''), '%Y-%m-%d %H:%M:%S') if row.get('end_datetime') else start_dt + timedelta(hours=1)

                                    self.calendar_manager.create_event(
                                        title=row.get('title', 'Imported Event'),
                                        start_datetime=start_dt,
                                        end_datetime=end_dt,
                                        description=row.get('description', ''),
                                        location=row.get('location', ''),
                                        category=row.get('category', 'imported')
                                    )
                                    imported_count += 1
                                except Exception:
                                    error_count += 1
                    except Exception:
                        messagebox.showerror(_("common.error"), _("academic_calendar.messages.csv_read_error"))
                        return
                else:
                    messagebox.showerror(_("common.error"), _("academic_calendar.messages.unsupported_format"))
                    return

                # Show import results
                if imported_count > 0:
                    if error_count > 0:
                        message = _("academic_calendar.messages.import_success_with_errors").format(count=imported_count, errors=error_count)
                    else:
                        message = _("academic_calendar.messages.import_success").format(count=imported_count)
                    messagebox.showinfo(_("academic_calendar.messages.import_complete"), message)
                else:
                    messagebox.showwarning(_("academic_calendar.messages.import_warning"), _("academic_calendar.messages.no_events_imported"))

            if self.callback:
                self.callback()
            self.dialog.destroy()

        except Exception as e:
            messagebox.showerror(_("common.error"), _("academic_calendar.messages.import_failed").format(error=e))
    
    def _center_dialog(self):
        """Center dialog on parent"""
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")


class CalendarSyncDialog:
    """Dialog for calendar synchronization"""
    
    def __init__(self, parent, calendar_manager, callback=None):
        self.calendar_manager = calendar_manager
        self.callback = callback
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_("academic_calendar.dialogs.calendar_sync.title"))
        self.dialog.geometry("450x300")
        self.dialog.transient(parent)
        safe_grab_set(self.dialog, parent)

        self._create_widgets()
        self._center_dialog()

    def _create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_("academic_calendar.dialogs.calendar_sync.header"),
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # URL input
        ttk.Label(main_frame, text=_("academic_calendar.dialogs.calendar_sync.ical_url")).pack(anchor=tk.W)
        self.url_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.url_var, width=50).pack(fill=tk.X, pady=(5, 15))

        # Local calendar selection
        ttk.Label(main_frame, text=_("academic_calendar.dialogs.calendar_sync.local_calendar")).pack(anchor=tk.W)
        self.local_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.local_var, width=50).pack(fill=tk.X, pady=(5, 15))

        # Sync options
        options_frame = ttk.LabelFrame(main_frame, text=_("academic_calendar.dialogs.calendar_sync.sync_options"), padding=10)
        options_frame.pack(fill=tk.X, pady=(0, 15))

        self.skip_holidays = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text=_("academic_calendar.dialogs.calendar_sync.skip_holidays"),
                       variable=self.skip_holidays).pack(anchor=tk.W)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(20, 0))

        ttk.Button(button_frame, text=_("common.cancel"), command=self.dialog.destroy).pack(side=tk.RIGHT, padx=(10, 0))
        ttk.Button(button_frame, text=_("academic_calendar.buttons.sync"), command=self._sync_calendar).pack(side=tk.RIGHT)
    
    def _sync_calendar(self):
        """Perform calendar sync"""
        try:
            url = self.url_var.get().strip()
            if not url:
                messagebox.showerror(_("common.error"), _("academic_calendar.messages.enter_ical_url"))
                return

            local_calendar = self.local_var.get().strip() or None

            # Show progress
            progress_dialog = tk.Toplevel(self.dialog)
            progress_dialog.title(_("academic_calendar.messages.syncing"))
            progress_dialog.geometry("300x100")
            progress_dialog.transient(self.dialog)
            progress_dialog.grab_set()

            ttk.Label(progress_dialog, text=_("academic_calendar.messages.syncing_calendar")).pack(pady=20)
            progress = ttk.Progressbar(progress_dialog, mode='indeterminate')
            progress.pack(pady=10)
            progress.start()

            def sync_worker():
                try:
                    result = self.calendar_manager.calendar_sync(url, local_calendar)

                    progress_dialog.after(0, progress_dialog.destroy)

                    message = _("academic_calendar.messages.sync_result").format(
                        synced=result['synced'],
                        skipped=result['skipped_holidays'],
                        conflicts=len(result['conflicts'])
                    )

                    self.dialog.after(0, lambda: messagebox.showinfo(_("academic_calendar.messages.sync_complete"), message))

                    if self.callback:
                        self.dialog.after(0, self.callback)

                    self.dialog.after(0, self.dialog.destroy)

                except Exception as e:
                    progress_dialog.after(0, progress_dialog.destroy)
                    self.dialog.after(0, lambda: messagebox.showerror(_("academic_calendar.messages.sync_error"), _("academic_calendar.messages.sync_failed").format(error=e)))

            sync_thread = threading.Thread(target=sync_worker, daemon=True)
            sync_thread.start()

        except Exception as e:
            messagebox.showerror(_("common.error"), _("academic_calendar.messages.sync_setup_failed").format(error=e))
    
    def _center_dialog(self):
        """Center dialog on parent"""
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")


class ImportHolidaysDialog:
    """Dialog for importing holidays"""
    
    def __init__(self, parent, calendar_manager, callback=None):
        self.calendar_manager = calendar_manager
        self.callback = callback
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_("academic_calendar.dialogs.import_holidays.title"))
        self.dialog.geometry("400x300")
        self.dialog.transient(parent)
        safe_grab_set(self.dialog, parent)

        self._create_widgets()
        self._center_dialog()

    def _create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_("academic_calendar.dialogs.import_holidays.header"),
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Country selection
        ttk.Label(main_frame, text=_("academic_calendar.dialogs.import_holidays.country_code")).pack(anchor=tk.W)
        self.country_var = tk.StringVar(value="US")
        country_combo = ttk.Combobox(main_frame, textvariable=self.country_var, width=40,
                                   values=["US", "UK", "CA", "AU", "DE", "FR", "JP", "IN"])
        country_combo.pack(fill=tk.X, pady=(5, 15))

        # Year selection
        ttk.Label(main_frame, text=_("academic_calendar.dialogs.import_holidays.year")).pack(anchor=tk.W)
        self.year_var = tk.StringVar(value=str(datetime.now().year))
        ttk.Entry(main_frame, textvariable=self.year_var, width=40).pack(fill=tk.X, pady=(5, 15))

        # Region/State (optional)
        ttk.Label(main_frame, text=_("academic_calendar.dialogs.import_holidays.region_optional")).pack(anchor=tk.W)
        self.region_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.region_var, width=40).pack(fill=tk.X, pady=(5, 15))

        # Note
        note_frame = ttk.LabelFrame(main_frame, text=_("academic_calendar.dialogs.import_holidays.note"), padding=5)
        note_frame.pack(fill=tk.X, pady=(10, 15))

        ttk.Label(note_frame, text=_("academic_calendar.dialogs.import_holidays.note_text"), font=('Arial', 9)).pack()

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(20, 0))

        ttk.Button(button_frame, text=_("common.cancel"), command=self.dialog.destroy).pack(side=tk.RIGHT, padx=(10, 0))
        ttk.Button(button_frame, text=_("academic_calendar.buttons.import"), command=self._import_holidays).pack(side=tk.RIGHT)
    
    def _import_holidays(self):
        """Import holidays"""
        try:
            country = self.country_var.get().strip().upper()
            year_str = self.year_var.get().strip()
            region = self.region_var.get().strip() or None

            if not country or not year_str:
                messagebox.showerror(_("common.error"), _("academic_calendar.messages.country_year_required"))
                return

            year = int(year_str)

            success, message = self.calendar_manager.holidays.import_national_holidays(
                country, year, region
            )

            if success:
                messagebox.showinfo(_("common.success"), message)
                if self.callback:
                    self.callback()
                self.dialog.destroy()
            else:
                messagebox.showerror(_("common.error"), message)

        except ValueError:
            messagebox.showerror(_("common.error"), _("academic_calendar.messages.invalid_year_format"))
        except Exception as e:
            messagebox.showerror(_("common.error"), _("academic_calendar.messages.import_failed").format(error=e))
    
    def _center_dialog(self):
        """Center dialog on parent"""
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")


class BulkOperationsDialog:
    """Dialog for bulk operations"""
    
    def __init__(self, parent, calendar_manager, callback=None):
        self.calendar_manager = calendar_manager
        self.callback = callback
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_("academic_calendar.dialogs.bulk_operations.title"))
        self.dialog.geometry("500x400")
        self.dialog.transient(parent)
        safe_grab_set(self.dialog, parent)

        self._create_widgets()
        self._center_dialog()

    def _create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_("academic_calendar.dialogs.bulk_operations.header"),
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Operations
        ops_frame = ttk.LabelFrame(main_frame, text=_("academic_calendar.dialogs.bulk_operations.available_operations"), padding=10)
        ops_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))

        operations = [
            (_("academic_calendar.dialogs.bulk_operations.bulk_create"), _("academic_calendar.dialogs.bulk_operations.bulk_create_desc")),
            (_("academic_calendar.dialogs.bulk_operations.bulk_update"), _("academic_calendar.dialogs.bulk_operations.bulk_update_desc")),
            (_("academic_calendar.dialogs.bulk_operations.create_template"), _("academic_calendar.dialogs.bulk_operations.create_template_desc")),
            (_("academic_calendar.dialogs.bulk_operations.cleanup_data"), _("academic_calendar.dialogs.bulk_operations.cleanup_data_desc"))
        ]

        for op_name, description in operations:
            op_frame = ttk.Frame(ops_frame)
            op_frame.pack(fill=tk.X, pady=5)

            ttk.Button(op_frame, text=op_name, width=25,
                      command=lambda o=op_name: self._perform_operation(o)).pack(side=tk.LEFT)
            ttk.Label(op_frame, text=description).pack(side=tk.LEFT, padx=(10, 0))

        # Note
        note_frame = ttk.LabelFrame(main_frame, text=_("academic_calendar.dialogs.import_holidays.note"), padding=5)
        note_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Label(note_frame, text=_("academic_calendar.dialogs.bulk_operations.note_text"), wraplength=450).pack()

        # Close button
        ttk.Button(main_frame, text=_("common.close"), command=self.dialog.destroy).pack(pady=(15, 0))
    
    def _perform_operation(self, operation):
        """Perform selected bulk operation"""
        bulk_create_key = _("academic_calendar.dialogs.bulk_operations.bulk_create")
        bulk_update_key = _("academic_calendar.dialogs.bulk_operations.bulk_update")
        template_key = _("academic_calendar.dialogs.bulk_operations.create_template")
        cleanup_key = _("academic_calendar.dialogs.bulk_operations.cleanup_data")

        if operation == bulk_create_key:
            messagebox.showinfo(_("common.info"), _("academic_calendar.messages.bulk_create_info"))
        elif operation == bulk_update_key:
            messagebox.showinfo(_("common.info"), _("academic_calendar.messages.bulk_update_info"))
        elif operation == template_key:
            messagebox.showinfo(_("common.info"), _("academic_calendar.messages.template_info"))
        elif operation == cleanup_key:
            self._cleanup_old_data()
    
    def _cleanup_old_data(self):
        """Clean up old data"""
        if messagebox.askyesno(_("academic_calendar.messages.confirm_cleanup"), _("academic_calendar.messages.cleanup_warning")):
            try:
                result = self.calendar_manager.cleanup_old_data()
                if result['success']:
                    message = _("academic_calendar.messages.cleanup_result").format(
                        events=result['cleaned_events'],
                        notifications=result['cleaned_notifications'],
                        logs=result['cleaned_audit_logs']
                    )
                    messagebox.showinfo(_("academic_calendar.messages.cleanup_complete"), message)
                    if self.callback:
                        self.callback()
                else:
                    messagebox.showerror(_("common.error"), result['error'])
            except Exception as e:
                messagebox.showerror(_("common.error"), _("academic_calendar.messages.cleanup_failed").format(error=e))
    
    def _center_dialog(self):
        """Center dialog on parent"""
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")


class HelpDialog:
    """Help dialog with user guide"""

    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_("academic_calendar.dialogs.help.title"))
        self.dialog.geometry("700x600")
        self.dialog.transient(parent)
        safe_grab_set(self.dialog, parent)

        self._create_widgets()
        self._center_dialog()

    def _create_widgets(self):
        """Create help dialog widgets"""
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_("academic_calendar.dialogs.help.header"),
                 font=('Arial', 16, 'bold')).pack(pady=(0, 20))

        # Help content
        help_text = scrolledtext.ScrolledText(main_frame, wrap=tk.WORD, height=25)
        help_text.pack(fill=tk.BOTH, expand=True, pady=(0, 15))

        help_content = _("academic_calendar.dialogs.help.content")

        help_text.insert(1.0, help_content)
        help_text.config(state=tk.DISABLED)

        # Close button
        ttk.Button(main_frame, text=_("common.close"), command=self.dialog.destroy).pack()
    
    def _center_dialog(self):
        """Center dialog on parent"""
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")


class AboutDialog:
    """About dialog with application information"""

    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_("academic_calendar.dialogs.about.title"))
        self.dialog.geometry("450x350")
        self.dialog.transient(parent)
        safe_grab_set(self.dialog, parent)

        self._create_widgets()
        self._center_dialog()

    def _create_widgets(self):
        """Create about dialog widgets"""
        main_frame = ttk.Frame(self.dialog, padding=30)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Application icon/title
        title_frame = ttk.Frame(main_frame)
        title_frame.pack(pady=(0, 20))

        ttk.Label(title_frame, text="📅", font=('Arial', 48)).pack()
        ttk.Label(title_frame, text=_("academic_calendar.dialogs.about.app_name"),
                 font=('Arial', 14, 'bold')).pack(pady=(10, 0))

        # Version info
        info_frame = ttk.Frame(main_frame)
        info_frame.pack(pady=(0, 20))

        info_text = [
            (_("academic_calendar.dialogs.about.version_label"), "2.0 (GUI + CLI)"),
            (_("academic_calendar.dialogs.about.release_label"), "2024"),
            (_("academic_calendar.dialogs.about.license_label"), _("academic_calendar.dialogs.about.license_value")),
            (_("academic_calendar.dialogs.about.interface_label"), _("academic_calendar.dialogs.about.interface_value")),
            (_("academic_calendar.dialogs.about.platform_label"), f"{platform.system()} {platform.release()}")
        ]

        for label, value in info_text:
            row_frame = ttk.Frame(info_frame)
            row_frame.pack(fill=tk.X, pady=2)
            ttk.Label(row_frame, text=label, font=('Arial', 9, 'bold')).pack(side=tk.LEFT)
            ttk.Label(row_frame, text=value).pack(side=tk.LEFT, padx=(10, 0))

        # Features
        features_frame = ttk.LabelFrame(main_frame, text=_("academic_calendar.dialogs.about.key_features"), padding=10)
        features_frame.pack(fill=tk.X, pady=(0, 20))

        features = [
            _("academic_calendar.dialogs.about.feature_calendar"),
            _("academic_calendar.dialogs.about.feature_reporting"),
            _("academic_calendar.dialogs.about.feature_import_export"),
            _("academic_calendar.dialogs.about.feature_trip"),
            _("academic_calendar.dialogs.about.feature_cli"),
            _("academic_calendar.dialogs.about.feature_rbac"),
            _("academic_calendar.dialogs.about.feature_interface")
        ]

        for feature in features:
            ttk.Label(features_frame, text=feature).pack(anchor=tk.W, pady=1)

        # Close button
        ttk.Button(main_frame, text=_("common.close"), command=self.dialog.destroy).pack(pady=(10, 0))
    
    def _center_dialog(self):
        """Center dialog on parent"""
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")


