from education_system.university_system.infrastructure.database.db import DEFAULT_DB_PATH, get_connection, transaction  # injected
from education_system.university_system.core.exceptions import (
    CourseNotFoundError,
    ValidationError,
)

# Import internationalization (i18n) for multi-language support
try:
    from education_system.university_system.core.i18n import (
        get_text as _t,
        get_current_language,
        get_current_language_name,
        set_language,
        get_available_language_list,
        init_i18n,
    )
    from education_system.university_system.modules.shared.utils.gui_language_selector import (
        show_gui_language_selector,
    )
    I18N_AVAILABLE = True
    GUI_LANG_SELECTOR_AVAILABLE = True
    # Initialize i18n if not already done
    init_i18n()
except ImportError:
    I18N_AVAILABLE = False
    GUI_LANG_SELECTOR_AVAILABLE = False
    _t = lambda key, **kwargs: key  # Fallback: return key as-is
    get_current_language = lambda: "en"
    get_current_language_name = lambda: "English"
    set_language = lambda lang, save=True: False
    get_available_language_list = lambda: [("en", "English")]
    show_gui_language_selector = lambda parent=None: "en"

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
from tkinter.font import Font
import os
import sys
from datetime import datetime, timedelta
import threading
import subprocess
import webbrowser
from pathlib import Path

# This ensures full backward compatibility
try:
    from education_system.university_system.modules.domain.academics.services.module_scheduling import (
        ModuleScheduler, DAYS_OF_WEEK, TIME_SLOTS, SESSION_TYPES, ROOM_TYPES,
        display_enhanced_scheduling_menu  # Keep CLI available
    )
except ImportError:
    # If the original module isn't available, we'll define basic constants
    DAYS_OF_WEEK = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    TIME_SLOTS = ['09:00', '10:00', '11:00', '12:00', '13:00', '14:00', '15:00', '16:00', '17:00']
    SESSION_TYPES = ['Lecture', 'Lab', 'Tutorial', 'Seminar', 'Workshop']
    ROOM_TYPES = ['Lecture Hall', 'Lab', 'Tutorial Room', 'Seminar Room', 'Workshop Room', 'Computer Lab', 'Other']

    # Import the ModuleScheduler class from the document
    try:
        from education_system.university_system.modules.domain.academics.services.module_scheduling import (ModuleScheduler, DAYS_OF_WEEK, TIME_SLOTS, SESSION_TYPES, ROOM_TYPES, display_enhanced_scheduling_menu)
    except Exception:
        class ModuleScheduler: pass

from education_system.university_system.modules.domain.academics.gui.module_scheduling.main_gui import ModuleSchedulingGUI
from education_system.university_system.modules.domain.academics.gui.module_scheduling.dialogs import AddHolidayDialog

def create_settings_tab(self):
    """Create the settings tab"""
    settings_frame = ttk.Frame(self.notebook)
    self.notebook.add(settings_frame, text=_t("scheduling.tabs.settings"))

    # System settings
    system_frame = ttk.LabelFrame(settings_frame, text=_t("scheduling.system_settings"), padding=15)
    system_frame.pack(fill=tk.X, padx=20, pady=10)

    # Institution name
    ttk.Label(system_frame, text=_t("scheduling.institution_name") + ":").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
    self.institution_var = tk.StringVar()
    ttk.Entry(system_frame, textvariable=self.institution_var, width=30).grid(row=0, column=1, padx=5, pady=5)

    # Semester dates
    ttk.Label(system_frame, text=_t("scheduling.semester_start") + ":").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
    self.semester_start_var = tk.StringVar()
    ttk.Entry(system_frame, textvariable=self.semester_start_var, width=30).grid(row=1, column=1, padx=5, pady=5)

    ttk.Label(system_frame, text=_t("scheduling.semester_end") + ":").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
    self.semester_end_var = tk.StringVar()
    ttk.Entry(system_frame, textvariable=self.semester_end_var, width=30).grid(row=2, column=1, padx=5, pady=5)

    # Default session duration
    ttk.Label(system_frame, text=_t("scheduling.session_duration") + ":").grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
    self.session_duration_var = tk.StringVar()
    ttk.Entry(system_frame, textvariable=self.session_duration_var, width=30).grid(row=3, column=1, padx=5, pady=5)

    # Email notifications
    self.email_notifications_var = tk.BooleanVar()
    ttk.Checkbutton(system_frame, text=_t("scheduling.enable_email_notifications"),
                   variable=self.email_notifications_var).grid(row=4, column=0, columnspan=2, sticky=tk.W, padx=5, pady=5)

    # Auto backup
    self.auto_backup_var = tk.BooleanVar()
    ttk.Checkbutton(system_frame, text=_t("scheduling.enable_auto_backups"),
                   variable=self.auto_backup_var).grid(row=5, column=0, columnspan=2, sticky=tk.W, padx=5, pady=5)

    # Save settings button
    ttk.Button(system_frame, text=_t("scheduling.save_settings"),
              command=self.save_settings).grid(row=6, column=0, columnspan=2, pady=10)

    # Holidays management
    holidays_frame = ttk.LabelFrame(settings_frame, text=_t("scheduling.holidays_management"), padding=15)
    holidays_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

    # Holiday controls
    holiday_controls = ttk.Frame(holidays_frame)
    holiday_controls.pack(fill=tk.X, pady=5)

    ttk.Button(holiday_controls, text=_t("scheduling.add_holiday"),
              command=self.add_holiday).pack(side=tk.LEFT, padx=5)
    ttk.Button(holiday_controls, text=_t("scheduling.view_calendar"),
              command=self.view_calendar).pack(side=tk.LEFT, padx=5)

    # Holidays list
    holidays_tree_frame = ttk.Frame(holidays_frame)
    holidays_tree_frame.pack(fill=tk.BOTH, expand=True, pady=5)

    columns = ("Name", "Start Date", "End Date", "Recurring", "Description")
    self.holidays_tree = ttk.Treeview(holidays_tree_frame, columns=columns, show="headings",
                                      height=8, selectmode="extended")

    for col in columns:
        self.holidays_tree.heading(col, text=col)
        if col == "Description":
            self.holidays_tree.column(col, width=200)
        else:
            self.holidays_tree.column(col, width=120)

    # Scrollbar for holidays
    holidays_scrollbar = ttk.Scrollbar(holidays_tree_frame, orient=tk.VERTICAL, command=self.holidays_tree.yview)
    self.holidays_tree.configure(yscrollcommand=holidays_scrollbar.set)

    self.holidays_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    holidays_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

ModuleSchedulingGUI.create_settings_tab = create_settings_tab

def load_settings(self):
    """Load system settings into the interface"""
    try:
        # Load settings from backend
        self.institution_var.set(self.scheduler.get_system_setting('institution_name', 'University'))
        self.semester_start_var.set(self.scheduler.get_system_setting('semester_start', ''))
        self.semester_end_var.set(self.scheduler.get_system_setting('semester_end', ''))
        self.session_duration_var.set(self.scheduler.get_system_setting('default_session_duration', '60'))

        email_notifications = self.scheduler.get_system_setting('email_notifications', 'False') == 'True'
        self.email_notifications_var.set(email_notifications)

        auto_backup = self.scheduler.get_system_setting('auto_backup', 'True') == 'True'
        self.auto_backup_var.set(auto_backup)

    except Exception as e:
        messagebox.showerror("Error", f"Failed to load settings: {str(e)}", parent=self.root)

ModuleSchedulingGUI.load_settings = load_settings

def save_settings(self):
    """Save system settings"""
    try:
        # Save all settings
        self.scheduler.update_system_setting('institution_name', self.institution_var.get())
        self.scheduler.update_system_setting('semester_start', self.semester_start_var.get())
        self.scheduler.update_system_setting('semester_end', self.semester_end_var.get())
        self.scheduler.update_system_setting('default_session_duration', self.session_duration_var.get())
        self.scheduler.update_system_setting('email_notifications', str(self.email_notifications_var.get()))
        self.scheduler.update_system_setting('auto_backup', str(self.auto_backup_var.get()))

        messagebox.showinfo("Success", "Settings saved successfully!", parent=self.root)
        self.update_activity_log("System settings updated")

    except Exception as e:
        messagebox.showerror("Error", f"Failed to save settings: {str(e)}", parent=self.root)

ModuleSchedulingGUI.save_settings = save_settings

def add_holiday(self):
    """Add a new holiday"""
    dialog = AddHolidayDialog(self.root, self.scheduler)
    if dialog.result:
        self.refresh_holidays()
        self.update_activity_log("Holiday added")

        # Also add to academic calendar GUI if available
        try:
            self._sync_holiday_to_academic_calendar()
        except Exception as e:
            print(f"Note: Could not sync to academic calendar: {e}")

ModuleSchedulingGUI.add_holiday = add_holiday

def _sync_holiday_to_academic_calendar(self):
    """Sync holidays with the academic calendar GUI"""
    try:
        # Get the most recently added holiday
        from education_system.university_system.infrastructure.database.db import get_connection
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, holiday_name, start_date, end_date, description, recurring
                FROM holidays
                ORDER BY id DESC
                LIMIT 1
            ''')
            holiday = cursor.fetchone()

        if holiday:
            holiday_id, name, start_date, end_date, description, recurring = holiday

            # Check if this holiday already exists in academic calendar
            event_title = f"Holiday: {name}"

            # Add as an event to the academic calendar
            # The academic calendar has its own events table
            try:
                with get_connection() as conn:
                    cursor = conn.cursor()
                    # Check if calendar_events table exists
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='calendar_events'")
                    if cursor.fetchone():
                        # Add event to calendar
                        cursor.execute('''
                            INSERT OR IGNORE INTO calendar_events (title, description, start_date, end_date, event_type, is_recurring)
                            VALUES (?, ?, ?, ?, 'holiday', ?)
                        ''', (event_title, description or '', start_date, end_date or start_date, 1 if recurring else 0))
                        conn.commit()
            except Exception as e:
                print(f"Could not sync to calendar_events: {e}")

    except Exception as e:
        print(f"Error syncing holiday to academic calendar: {e}")

ModuleSchedulingGUI._sync_holiday_to_academic_calendar = _sync_holiday_to_academic_calendar

def refresh_holidays(self):
    """Refresh the holidays treeview"""
    try:
        # Clear existing items
        for item in self.holidays_tree.get_children():
            self.holidays_tree.delete(item)

        from education_system.university_system.infrastructure.database.db import sqlite3
        with get_connection(str(DEFAULT_DB_PATH), row_factory=False) as conn:
            cursor = conn.cursor()

            cursor.execute('''
            SELECT holiday_name, start_date, end_date, recurring, description
            FROM holidays
            ORDER BY start_date
            ''')

            holidays = cursor.fetchall()

        for holiday in holidays:
            name, start_date, end_date, recurring, description = holiday
            recurring_str = "Yes" if recurring else "No"
            description = description or ""

            self.holidays_tree.insert("", tk.END, values=(
                name, start_date, end_date, recurring_str, description
            ))

    except Exception as e:
        messagebox.showerror("Error", f"Failed to refresh holidays: {str(e)}", parent=self.root)

ModuleSchedulingGUI.refresh_holidays = refresh_holidays

def list_holidays(self):
    """List all holidays in a dialog"""
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute('''
        SELECT name, start_date, end_date, description, recurring
        FROM holidays
        ORDER BY start_date
        ''')

        holidays = cursor.fetchall()

    # Create dialog
    dialog = tk.Toplevel(self.root)
    dialog.title("Academic Holidays")
    dialog.geometry("900x500")
    dialog.transient(self.root)

    # Create treeview
    columns = ('Name', 'Start Date', 'End Date', 'Description', 'Recurring')
    tree = ttk.Treeview(dialog, columns=columns, show='headings')

    for col in columns:
        tree.heading(col, text=col)

    tree.column('Name', width=180)
    tree.column('Start Date', width=120)
    tree.column('End Date', width=120)
    tree.column('Description', width=300)
    tree.column('Recurring', width=80)

    for holiday in holidays:
        name, start, end, desc, recurring = holiday
        tree.insert('', tk.END, values=(name, start, end, desc or '', 'Yes' if recurring else 'No'))

    tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    # Buttons
    btn_frame = ttk.Frame(dialog)
    btn_frame.pack(fill=tk.X, padx=10, pady=5)

    ttk.Button(btn_frame, text="Close", command=dialog.destroy).pack(side=tk.RIGHT)

ModuleSchedulingGUI.list_holidays = list_holidays

def check_holiday_conflicts(self, date):
    """Check if a date falls on a holiday"""
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute('''
        SELECT name, description
        FROM holidays
        WHERE ? BETWEEN start_date AND end_date
        ''', (date,))

        holiday = cursor.fetchone()

    if holiday:
        name, description = holiday
        messagebox.showwarning(
            "Holiday Conflict",
            f"This date falls on a holiday: {name}\n\n"
            f"{description if description else 'No description available.'}"
        , parent=self.root)
        return True

    return False

ModuleSchedulingGUI.check_holiday_conflicts = check_holiday_conflicts

def save_template(self):
    """Save current schedule as template"""
    try:
        template_name = tk.simpledialog.askstring("Save Template",
                                                 "Enter template name:",
                                                 parent=self.root)

        if template_name:
            description = tk.simpledialog.askstring("Save Template",
                                                   "Enter description (optional):",
                                                   parent=self.root)

            success = self.scheduler.save_schedule_template(template_name, description or "")

            if success:
                # Also save as JSON file
                try:
                    import json
                    with get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute('''
                        SELECT module_code, day_of_week, start_time, end_time,
                               room_id, instructor_id, session_type
                        FROM module_schedule
                        ORDER BY module_code, day_of_week, start_time
                        ''')
                        schedules = [
                            {
                                'module_code': r[0], 'day_of_week': r[1],
                                'start_time': r[2], 'end_time': r[3],
                                'room_id': r[4], 'instructor_id': r[5],
                                'session_type': r[6]
                            }
                            for r in cursor.fetchall()
                        ]
                    _save_template_json_file(template_name, description or "", schedules)
                except Exception as json_err:
                    print(f"Warning: Could not save JSON file: {json_err}")

                messagebox.showinfo("Success", f"Template '{template_name}' saved successfully!", parent=self.root)
                self.update_activity_log(f"Saved template: {template_name}")
            else:
                messagebox.showerror("Error", "Failed to save template.", parent=self.root)

    except Exception as e:
        messagebox.showerror("Error", f"Failed to save template: {str(e)}", parent=self.root)

ModuleSchedulingGUI.save_template = save_template

def load_template(self):
    """Load a schedule template"""
    try:
        # First list templates
        self.list_templates()

        template_name = tk.simpledialog.askstring("Load Template",
                                                 "Enter template name to load:",
                                                 parent=self.root)

        if template_name:
            clear_existing = messagebox.askyesno("Load Template",
                                               "Clear existing schedules before loading template?", parent=self.root)

            success = self.scheduler.load_schedule_template(template_name, clear_existing)

            if success:
                messagebox.showinfo("Success", f"Template '{template_name}' loaded successfully!", parent=self.root)
                self.refresh_all_data()
                self.update_activity_log(f"Loaded template: {template_name}")
            else:
                messagebox.showerror("Error", "Failed to load template.", parent=self.root)

    except Exception as e:
        messagebox.showerror("Error", f"Failed to load template: {str(e)}", parent=self.root)

ModuleSchedulingGUI.load_template = load_template

def list_templates(self):
    """List all available templates"""
    try:
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)

        from education_system.university_system.infrastructure.database.db import sqlite3
        with get_connection(str(DEFAULT_DB_PATH), row_factory=False) as conn:
            cursor = conn.cursor()

            cursor.execute('''
            SELECT template_name, description, created_date, created_by
            FROM schedule_templates
            ORDER BY created_date DESC
            ''')

            templates = cursor.fetchall()

        if not templates:
            self.log_text.insert(tk.END, "No schedule templates found.\n")
        else:
            self.log_text.insert(tk.END, "Schedule Templates:\n")
            self.log_text.insert(tk.END, "=" * 80 + "\n")
            self.log_text.insert(tk.END, f"{'Name':<20} {'Description':<30} {'Created':<15} {'By':<10}\n")
            self.log_text.insert(tk.END, "-" * 80 + "\n")

            for template in templates:
                name, desc, created, created_by = template
                created_date = datetime.fromisoformat(created).strftime("%Y-%m-%d")
                desc = desc or "N/A"
                self.log_text.insert(tk.END, f"{name:<20} {desc[:28]:<30} {created_date:<15} {created_by:<10}\n")

            self.log_text.insert(tk.END, "=" * 80 + "\n")

        self.log_text.config(state=tk.DISABLED)
        self.notebook.select(7)  # Switch to management tab

    except Exception as e:
        messagebox.showerror("Error", f"Failed to list templates: {str(e)}", parent=self.root)

ModuleSchedulingGUI.list_templates = list_templates

def save_schedule_template(self):
    """Save current schedule as a template"""
    # Create dialog for template details
    dialog = tk.Toplevel(self.root)
    dialog.title("Save Schedule Template")
    dialog.geometry("400x200")
    dialog.transient(self.root)
    dialog.grab_set()

    ttk.Label(dialog, text="Template Name:").pack(pady=5)
    name_entry = ttk.Entry(dialog, width=40)
    name_entry.pack(pady=5)

    ttk.Label(dialog, text="Description:").pack(pady=5)
    desc_text = tk.Text(dialog, width=40, height=4)
    desc_text.pack(pady=5)

    def save_template():
        template_name = name_entry.get().strip()
        description = desc_text.get("1.0", tk.END).strip()

        if not template_name:
            messagebox.showwarning("Warning", "Please enter a template name.", parent=self.root)
            return

        try:
            with transaction() as conn:
                cursor = conn.cursor()

                # Save all current schedules as a template
                cursor.execute('''
                SELECT module_code, day_of_week, start_time, end_time, room_id, instructor_id, session_type
                FROM module_schedule
                ''')
                schedules = cursor.fetchall()

                import json
                # Build structured template data
                template_entries = []
                for s in schedules:
                    template_entries.append({
                        'module_code': s[0],
                        'day_of_week': s[1],
                        'start_time': s[2],
                        'end_time': s[3],
                        'room_id': s[4],
                        'instructor_id': s[5],
                        'session_type': s[6]
                    })

                template_data = json.dumps(template_entries, indent=2)

                cursor.execute('''
                INSERT INTO schedule_templates (template_name, template_data, description)
                VALUES (?, ?, ?)
                ''', (template_name, template_data, description))

            # Also save as JSON file
            _save_template_json_file(template_name, description, template_entries)

            messagebox.showinfo("Success", f"Template '{template_name}' saved successfully!", parent=self.root)
            dialog.destroy()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to save template: {str(e)}", parent=self.root)

    ttk.Button(dialog, text="Save", command=save_template).pack(pady=10)

ModuleSchedulingGUI.save_schedule_template = save_schedule_template

def _save_template_json_file(template_name, description, schedules):
    """Save a schedule template as a JSON file in templates/scheduling/"""
    import json
    from education_system.university_system.core.paths import TEMPLATES_DIR
    templates_dir = TEMPLATES_DIR / "scheduling"
    templates_dir.mkdir(parents=True, exist_ok=True)

    # Sanitise filename
    safe_name = "".join(c if c.isalnum() or c in ('-', '_') else '_' for c in template_name)
    file_path = templates_dir / f"{safe_name}.json"

    template_json = {
        "template_name": template_name,
        "description": description or "",
        "created_date": datetime.now().isoformat(),
        "schedule_count": len(schedules),
        "schedules": schedules
    }

    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(template_json, f, indent=2, ensure_ascii=False)

    print(f"Template JSON saved to: {file_path}")

def load_schedule_template(self):
    """Load a schedule template"""
    # Get list of templates
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT id, template_name, description, created_date FROM schedule_templates ORDER BY created_date DESC')
        templates = cursor.fetchall()

    if not templates:
        messagebox.showinfo("No Templates", "No schedule templates found.", parent=self.root)
        return

    # Create selection dialog
    dialog = tk.Toplevel(self.root)
    dialog.title("Load Schedule Template")
    dialog.geometry("700x400")
    dialog.transient(self.root)
    dialog.grab_set()

    # Create listbox
    listbox = tk.Listbox(dialog, font=('Arial', 10))
    for template_id, name, desc, date in templates:
        listbox.insert(tk.END, f"{name} - {date}")
    listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    def load_selected():
        if not listbox.curselection():
            messagebox.showwarning("Warning", "Please select a template.", parent=self.root)
            return

        idx = listbox.curselection()[0]
        template_id = templates[idx][0]

        # Confirm
        confirm = messagebox.askyesno(
            "Confirm Load",
            "This will REPLACE all current schedules with the template.\n\n"
            "Are you sure you want to continue?"
        , parent=self.root)

        if not confirm:
            return

        try:
            with transaction() as conn:
                cursor = conn.cursor()

                # Get template data
                cursor.execute('SELECT template_data FROM schedule_templates WHERE id = ?', (template_id,))
                result = cursor.fetchone()

                if not result:
                    messagebox.showerror("Error", "Template not found.", parent=self.root)
                    return

                import json
                schedules = json.loads(result[0])

                # Clear existing schedules
                cursor.execute('DELETE FROM module_schedule')

                # Insert template schedules
                for schedule in schedules:
                    cursor.execute('''
                    INSERT INTO module_schedule
                    (module_code, day_of_week, start_time, end_time, room_id, instructor_id, session_type)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', schedule)

            messagebox.showinfo("Success", f"Template loaded successfully!\nLoaded {len(schedules)} schedules.", parent=self.root)
            self.refresh_all_data()
            dialog.destroy()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load template: {str(e)}", parent=self.root)

    ttk.Button(dialog, text="Load", command=load_selected).pack(pady=5)
    ttk.Button(dialog, text="Cancel", command=dialog.destroy).pack(pady=5)

ModuleSchedulingGUI.load_schedule_template = load_schedule_template

def list_schedule_templates(self):
    """List all schedule templates"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
        SELECT template_name, description, created_date,
               (SELECT COUNT(*) FROM json_each(template_data)) as schedule_count
        FROM schedule_templates
        ORDER BY created_date DESC
        ''')
        templates = cursor.fetchall()

    if not templates:
        messagebox.showinfo("No Templates", "No schedule templates found.", parent=self.root)
        return

    # Create dialog
    dialog = tk.Toplevel(self.root)
    dialog.title("Schedule Templates")
    dialog.geometry("900x500")
    dialog.transient(self.root)

    # Create treeview
    columns = ('Name', 'Description', 'Created Date', 'Schedules')
    tree = ttk.Treeview(dialog, columns=columns, show='headings')

    for col in columns:
        tree.heading(col, text=col)

    tree.column('Name', width=200)
    tree.column('Description', width=350)
    tree.column('Created Date', width=150)
    tree.column('Schedules', width=100)

    for template in templates:
        name, desc, date, count = template
        tree.insert('', tk.END, values=(name, desc or '', date, count or 0))

    tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    # Buttons
    btn_frame = ttk.Frame(dialog)
    btn_frame.pack(fill=tk.X, padx=10, pady=5)

    ttk.Button(btn_frame, text="Close", command=dialog.destroy).pack(side=tk.RIGHT)

ModuleSchedulingGUI.list_schedule_templates = list_schedule_templates

def update_system_setting(self, key, value):
    """Update a system setting"""
    try:
        with transaction() as conn:
            cursor = conn.cursor()

            cursor.execute('''
            UPDATE scheduling_system_settings
            SET value = ?, last_modified = CURRENT_TIMESTAMP
            WHERE key = ?
            ''', (value, key))

            if cursor.rowcount == 0:
                # Setting doesn't exist, create it
                cursor.execute('''
                INSERT INTO scheduling_system_settings (key, value, description)
                VALUES (?, ?, ?)
                ''', (key, value, f"Custom setting: {key}"))

        messagebox.showinfo("Success", f"System setting '{key}' updated to '{value}'", parent=self.root)

    except Exception as e:
        messagebox.showerror("Error", f"Error updating setting: {str(e)}", parent=self.root)

ModuleSchedulingGUI.update_system_setting = update_system_setting

def list_system_settings(self):
    """List all system settings in a dialog"""
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute('''
        SELECT key, value, description, last_modified
        FROM scheduling_system_settings
        ORDER BY key
        ''')

        settings = cursor.fetchall()

    # Create dialog
    dialog = tk.Toplevel(self.root)
    dialog.title("System Settings")
    dialog.geometry("900x500")
    dialog.transient(self.root)

    # Create treeview
    columns = ('Key', 'Value', 'Description', 'Last Modified')
    tree = ttk.Treeview(dialog, columns=columns, show='headings')

    for col in columns:
        tree.heading(col, text=col)

    tree.column('Key', width=200)
    tree.column('Value', width=200)
    tree.column('Description', width=300)
    tree.column('Last Modified', width=180)

    for setting in settings:
        key, value, description, last_modified = setting
        tree.insert('', tk.END, values=(key, value or '', description or '', last_modified or ''))

    tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    # Buttons
    btn_frame = ttk.Frame(dialog)
    btn_frame.pack(fill=tk.X, padx=10, pady=5)

    ttk.Button(btn_frame, text="Close", command=dialog.destroy).pack(side=tk.RIGHT)

ModuleSchedulingGUI.list_system_settings = list_system_settings

