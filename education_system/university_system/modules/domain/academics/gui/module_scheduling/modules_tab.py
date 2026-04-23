from education_system.university_system.infrastructure.database.db import DEFAULT_DB_PATH, get_connection, transaction  # injected
from education_system.university_system.infrastructure.exceptions import (
    CourseNotFoundError,
    ValidationError,
)
from education_system.university_system.core.sql_safety import validate_table_name

# Import internationalization (i18n) for multi-language support
try:
    from education_system.university_system.modules.shared.utils.i18n import (
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
from tkinter import ttk, messagebox, filedialog, scrolledtext, simpledialog
from tkinter.font import Font
import os
import sys
from datetime import datetime, timedelta
import threading
import subprocess
import webbrowser
from pathlib import Path
from education_system.university_system.infrastructure.database.db import sqlite3
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

def create_modules_tab(self):
    """Create the modules management tab"""
    modules_frame = ttk.Frame(self.notebook)
    self.notebook.add(modules_frame, text=_t("scheduling.tabs.modules"))

    # Controls frame
    controls_frame = ttk.Frame(modules_frame)
    controls_frame.pack(fill=tk.X, padx=10, pady=5)

    ttk.Button(controls_frame, text=_t("scheduling.buttons.add_module"),
              command=self.show_add_module_dialog).pack(side=tk.LEFT, padx=5)
    ttk.Button(controls_frame, text=_t("common.edit_selected"),
              command=self.edit_selected_module).pack(side=tk.LEFT, padx=5)
    ttk.Button(controls_frame, text=_t("common.delete_selected"),
              command=self.delete_selected_module).pack(side=tk.LEFT, padx=5)
    ttk.Button(controls_frame, text=_t("scheduling.actions.generate_report"),
              command=self.generate_module_report).pack(side=tk.LEFT, padx=5)

    # Search
    search_frame = ttk.Frame(controls_frame)
    search_frame.pack(side=tk.RIGHT, padx=5)

    ttk.Label(search_frame, text=_t("common.search") + ":").pack(side=tk.LEFT)
    self.module_search_var = tk.StringVar()
    self.module_search_var.trace('w', self.filter_modules)
    ttk.Entry(search_frame, textvariable=self.module_search_var, width=20).pack(side=tk.LEFT, padx=5)

    # Modules treeview
    tree_frame = ttk.Frame(modules_frame)
    tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

    columns = ("ID", "Code", "Name", "Credits", "Semester", "Type", "Instructor")
    self.modules_tree = ttk.Treeview(tree_frame, columns=columns, show="headings",
                                     style='Data.Treeview', selectmode="extended")

    for col in columns:
        self.modules_tree.heading(col, text=col)
        if col == "ID":
            self.modules_tree.column(col, width=50)
        elif col == "Name":
            self.modules_tree.column(col, width=200)
        else:
            self.modules_tree.column(col, width=100)

    # Scrollbars
    v_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.modules_tree.yview)
    self.modules_tree.configure(yscrollcommand=v_scrollbar.set)

    self.modules_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    self.modules_tree.bind("<Double-1>", lambda e: self.edit_selected_module())

ModuleSchedulingGUI.create_modules_tab = create_modules_tab

def show_modules_tab(self):
    """Switch to modules tab"""
    # Find the modules tab index and select it
    for i in range(self.notebook.index('end')):
        if 'Modules' in self.notebook.tab(i, 'text'):
            self.notebook.select(i)
            break

ModuleSchedulingGUI.show_modules_tab = show_modules_tab

def refresh_modules(self):
    """Refresh the module list in the treeview"""
    # Clear existing rows
    for row in self.modules_tree.get_children():
        self.modules_tree.delete(row)

    try:
        modules = self.scheduler.get_all_modules()
    except Exception as e:
        self.log_activity(f"Error loading modules: {e}")
        return

    for m in modules:
        self.modules_tree.insert(
            "", tk.END, values=(
                m.get("id", ""),
                m.get("code", ""),
                m.get("name", ""),
                m.get("credits", ""),
                m.get("semester", ""),
                m.get("type", ""),
                m.get("instructor", ""),
            )
        )

    self.log_activity("Modules refreshed")

ModuleSchedulingGUI.refresh_modules = refresh_modules

def get_all_modules(self):
    """Get all modules from the database"""
    with get_connection(str(DEFAULT_DB_PATH), row_factory=False) as conn:
        cursor = conn.cursor()
        # Use the implicit rowid as the module identifier.  Many parts of the
        # system define a modules table without an explicit id column.  Selecting
        # rowid as "id" provides a stable unique integer for each row and
        # preserves compatibility with code that expects an id field.
        cursor.execute('SELECT rowid AS id, module_code, module_name, module_type FROM modules')
        modules = cursor.fetchall()

    result = []
    for module in modules:
        result.append({
            'id': module[0],
            'code': module[1],
            'name': module[2],
            'credits': '',  # Not available in modules table
            'semester': '',  # Not available in modules table
            'type': module[3],
            'instructor': ''  # Not available in modules table
        })

    return result

ModuleSchedulingGUI.get_all_modules = get_all_modules

def add_module(self, module_data):
    """Add a new module with course association"""
    with get_connection(str(DEFAULT_DB_PATH), row_factory=False) as conn:
        cursor = conn.cursor()

        # Extract course code from the formatted string "CODE - Name"
        course_info = module_data.get('course', '')
        course_code = course_info.split(' - ')[0] if ' - ' in course_info else course_info

        cursor.execute('''
        INSERT INTO modules (module_code, module_name, module_type, credits, semester, department)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            module_data['code'],
            module_data['name'],
            module_data['type'],
            int(module_data.get('credits', 3)),
            module_data.get('semester', 'Fall'),
            course_code
        ))

        conn.commit()

ModuleSchedulingGUI.add_module = add_module

def update_module(self, module_id, module_data):
    """Update module data"""
    with get_connection(str(DEFAULT_DB_PATH), row_factory=False) as conn:
        cursor = conn.cursor()

        cursor.execute('''
        UPDATE modules
        SET module_code=?, module_name=?, module_type=?
        WHERE rowid=?
        ''', (module_data['code'], module_data['name'], module_data['type'], module_id))

        conn.commit()

ModuleSchedulingGUI.update_module = update_module

def delete_module(self, module_id):
    """Delete a module and handle foreign key constraints"""
    with get_connection(str(DEFAULT_DB_PATH), row_factory=False) as conn:
        cursor = conn.cursor()

        # First, get the module_code for the module being deleted
        cursor.execute('SELECT module_code FROM modules WHERE rowid = ?', (module_id,))
        result = cursor.fetchone()
        if not result:
            raise CourseNotFoundError(f"Module {module_id}")

        module_code = result[0]

        # Check for dependencies in various tables
        dependencies = []

        # Check module_schedule
        cursor.execute('SELECT COUNT(*) FROM module_schedule WHERE module_code = ?', (module_code,))
        if cursor.fetchone()[0] > 0:
            dependencies.append("module_schedule")

        # Check attendance if table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='attendance'")
        if cursor.fetchone():
            cursor.execute('SELECT COUNT(*) FROM attendance WHERE module_code = ?', (module_code,))
            if cursor.fetchone()[0] > 0:
                dependencies.append("attendance")

        # Check document_repository if table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='document_repository'")
        if cursor.fetchone():
            cursor.execute('SELECT COUNT(*) FROM document_repository WHERE module_code = ?', (module_code,))
            if cursor.fetchone()[0] > 0:
                dependencies.append("document_repository")

        # Check for other tables that might reference this module
        cursor.execute('''
        SELECT DISTINCT tbl_name FROM sqlite_master
        WHERE type='table' AND sql LIKE '%module_code%'
        AND tbl_name NOT IN ('modules', 'module_schedule', 'attendance', 'document_repository')
        ''')
        other_tables = cursor.fetchall()

        for (table_name,) in other_tables:
            try:
                safe_table = validate_table_name(table_name, conn=conn)
                cursor.execute('SELECT COUNT(*) FROM [' + safe_table + '] WHERE module_code = ?', (module_code,))
                if cursor.fetchone()[0] > 0:
                    dependencies.append(table_name)
            except Exception:
                # Skip tables we can't query
                pass

        # If there are dependencies, ask user what to do
        if dependencies:
            import tkinter.messagebox as mb
            response = mb.askyesnocancel(
                "Dependencies Found",
                f"Module {module_code} is referenced by the following tables:\n" +
                "\n".join(f"- {dep}" for dep in dependencies) +
                f"\n\nClick 'Yes' to delete the module and all related records.\n" +
                f"Click 'No' to cancel deletion.\n" +
                f"Click 'Cancel' to view dependencies first."
            )

            if response is None:  # Cancel
                raise ValidationError("Deletion cancelled - dependencies exist")
            elif response is False:  # No
                raise ValidationError("Deletion cancelled by user")
            else:  # Yes - proceed with cascade delete
                # Delete related records first
                if "module_schedule" in dependencies:
                    cursor.execute('DELETE FROM module_schedule WHERE module_code = ?', (module_code,))
                    print(f"Deleted module_schedule records for {module_code}")

                if "attendance" in dependencies:
                    cursor.execute('DELETE FROM attendance WHERE module_code = ?', (module_code,))
                    print(f"Deleted attendance records for {module_code}")

                if "document_repository" in dependencies:
                    cursor.execute('DELETE FROM document_repository WHERE module_code = ?', (module_code,))
                    print(f"Deleted document_repository records for {module_code}")

                # Delete assignments and related data for this module
                self.delete_assignments_for_module(cursor, module_code)

                # Delete from other tables that reference this module
                for table_name in dependencies:
                    if table_name not in ["module_schedule", "attendance", "document_repository"]:
                        try:
                            safe_table = validate_table_name(table_name, conn=conn)
                            cursor.execute('DELETE FROM [' + safe_table + '] WHERE module_code = ?', (module_code,))
                            print(f"Deleted {table_name} records for {module_code}")
                        except Exception as e:
                            print(f"Could not delete from {table_name}: {e}")

        # Finally delete the module itself
        cursor.execute('DELETE FROM modules WHERE rowid = ?', (module_id,))
        conn.commit()
        print(f"Successfully deleted module {module_code}")

ModuleSchedulingGUI.delete_module = delete_module

def delete_assignments_for_module(self, cursor, module_code):
    """Delete all assignments and related data for a specific module"""
    try:
        # Get all assignment IDs for this module
        cursor.execute('SELECT id FROM assignments WHERE module_code = ?', (module_code,))
        assignment_ids = [row[0] for row in cursor.fetchall()]

        if assignment_ids:
            # Delete assignment submissions first
            for assignment_id in assignment_ids:
                cursor.execute('DELETE FROM assignment_submissions WHERE assignment_id = ?', (assignment_id,))

            # Delete peer reviews for these assignments
            for assignment_id in assignment_ids:
                cursor.execute('DELETE FROM peer_reviews WHERE assignment_id = ?', (assignment_id,))

            # Delete extension requests for these assignments
            for assignment_id in assignment_ids:
                cursor.execute('DELETE FROM extension_requests WHERE assignment_id = ?', (assignment_id,))

            # Delete the assignments themselves
            cursor.execute('DELETE FROM assignments WHERE module_code = ?', (module_code,))

            print(f"Deleted {len(assignment_ids)} assignments and related data for module {module_code}")

        # Also delete any assessments for this module (if assessments table exists)
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='assessments'")
        if cursor.fetchone():
            cursor.execute('DELETE FROM assessments WHERE module_code = ?', (module_code,))
            print(f"Deleted assessments for module {module_code}")

    except Exception as e:
        print(f"Error deleting assignments for module {module_code}: {e}")

ModuleSchedulingGUI.delete_assignments_for_module = delete_assignments_for_module

def get_available_courses(self):
    """Get list of available courses from the courses table"""
    try:
        with get_connection(str(DEFAULT_DB_PATH), row_factory=False) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT course_code, course_name FROM courses
                WHERE status = 'active' AND course_code IS NOT NULL
                AND course_code != ''
                ORDER BY course_code
            ''')
            courses = cursor.fetchall()
            # Format as "CODE - Name" for display
            return [f"{code} - {name}" for code, name in courses] if courses else ["CS - Computer Science", "DS - Data Science"]
    except Exception as e:
        print(f"Error fetching courses: {e}")
        return ["CS - Computer Science", "DS - Data Science"]

ModuleSchedulingGUI.get_available_courses = get_available_courses

def show_add_module_dialog(self):
    """Dialog to add a new module with course selection"""
    dialog = tk.Toplevel(self.root)
    dialog.title("Add New Module")
    dialog.geometry("500x300")

    # Get available courses from the courses table
    available_courses = self.get_available_courses()

    fields = {
        "Code": tk.StringVar(),
        "Name": tk.StringVar(),
        "Type": tk.StringVar(),
        "Course": tk.StringVar(),
        "Credits": tk.StringVar(value="3"),
        "Semester": tk.StringVar(value="Fall"),
    }

    # Create form fields
    row = 0
    for label, var in fields.items():
        ttk.Label(dialog, text=label + ":").grid(row=row, column=0, sticky="w", padx=10, pady=5)

        if label == "Course":
            # Create dropdown for course selection
            course_combo = ttk.Combobox(dialog, textvariable=var, width=27)
            course_combo['values'] = available_courses
            course_combo.grid(row=row, column=1, padx=10, pady=5)
            if available_courses:
                course_combo.set(available_courses[0])  # Set default selection
        elif label == "Type":
            # Create dropdown for module type
            type_combo = ttk.Combobox(dialog, textvariable=var, width=27)
            type_combo['values'] = ["Core", "Elective", "Lab", "Seminar", "Project"]
            type_combo.grid(row=row, column=1, padx=10, pady=5)
            type_combo.set("Core")  # Set default
        elif label == "Semester":
            # Create dropdown for semester
            semester_combo = ttk.Combobox(dialog, textvariable=var, width=27)
            semester_combo['values'] = ["Fall", "Spring", "Summer"]
            semester_combo.grid(row=row, column=1, padx=10, pady=5)
        else:
            ttk.Entry(dialog, textvariable=var, width=30).grid(row=row, column=1, padx=10, pady=5)
        row += 1

    def save():
        try:
            module_data = {k.lower(): v.get() for k, v in fields.items()}
            self.add_module(module_data)
            self.refresh_modules()
            self.log_activity(f"Module added: {module_data['code']} - {module_data['name']}")
            dialog.destroy()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to add module: {e}", parent=self.root)

    ttk.Button(dialog, text="Save", command=save, style="Success.TButton").grid(
        row=len(fields), column=0, columnspan=2, pady=15
    )

ModuleSchedulingGUI.show_add_module_dialog = show_add_module_dialog

def edit_selected_module(self):
    """Edit the currently selected module"""
    selected = self.modules_tree.selection()
    if not selected:
        messagebox.showwarning("No Selection", "Please select a module to edit.", parent=self.root)
        return

    values = self.modules_tree.item(selected[0], "values")
    module_id = values[0]

    # Prefill with current values
    dialog = tk.Toplevel(self.root)
    dialog.title("Edit Module")
    dialog.geometry("400x200")

    fields = {
        "Code": tk.StringVar(value=values[1]),
        "Name": tk.StringVar(value=values[2]),
        "Type": tk.StringVar(value=values[5]),
    }

    for i, (label, var) in enumerate(fields.items()):
        ttk.Label(dialog, text=label + ":").grid(row=i, column=0, sticky="w", padx=10, pady=5)
        ttk.Entry(dialog, textvariable=var, width=30).grid(row=i, column=1, padx=10, pady=5)

    def save():
        try:
            updated_data = {k.lower(): v.get() for k, v in fields.items()}
            self.update_module(module_id, updated_data)
            self.refresh_modules()
            self.log_activity(f"Module updated: {updated_data['code']} - {updated_data['name']}")
            dialog.destroy()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to update module: {e}", parent=self.root)

    ttk.Button(dialog, text="Save Changes", command=save, style="Success.TButton").grid(
        row=len(fields), column=0, columnspan=2, pady=15
    )

ModuleSchedulingGUI.edit_selected_module = edit_selected_module

def delete_selected_module(self):
    """Delete the selected module"""
    selected = self.modules_tree.selection()
    if not selected:
        messagebox.showwarning("No Selection", "Please select a module to delete.", parent=self.root)
        return

    values = self.modules_tree.item(selected[0], "values")
    module_id, module_code, module_name = values[0], values[1], values[2]

    confirm = messagebox.askyesno(
        "Confirm Delete",
        f"Are you sure you want to delete module {module_code} - {module_name}?"
    , parent=self.root)
    if not confirm:
        return

    try:
        self.delete_module(module_id)
        self.refresh_modules()
        self.log_activity(f"Module deleted: {module_code} - {module_name}")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to delete module: {e}", parent=self.root)

ModuleSchedulingGUI.delete_selected_module = delete_selected_module

def filter_modules(self, *args):
    """Filter module list based on search entry"""
    query = self.module_search_var.get().lower()
    for row in self.modules_tree.get_children():
        values = self.modules_tree.item(row, "values")
        if any(query in str(v).lower() for v in values):
            self.modules_tree.reattach(row, "", "end")
        else:
            self.modules_tree.detach(row)

ModuleSchedulingGUI.filter_modules = filter_modules

def generate_module_report(self):
    """Generate a simple module report"""
    try:
        modules = self.scheduler.get_all_modules()
        if not modules:
            messagebox.showinfo("Report", "No modules available.", parent=self.root)
            return

        report = "Module Report\n\n"
        for m in modules:
            report += f"{m.get('code')} - {m.get('name')} ({m.get('credits')} credits, Semester {m.get('semester')})\n"

        report_window = tk.Toplevel(self.root)
        report_window.title("Module Report")
        report_window.geometry("900x600")
        report_window.transient(self.root)
        text = scrolledtext.ScrolledText(report_window, width=80, height=25)
        text.pack(fill=tk.BOTH, expand=True)
        text.insert(tk.END, report)
        text.config(state=tk.DISABLED)

        button_frame = ttk.Frame(report_window)
        button_frame.pack(fill=tk.X, padx=10, pady=10)

        def save_report():
            filename = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
                initialfile=f"module_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            )
            if not filename:
                return
            try:
                with open(filename, "w", encoding="utf-8") as handle:
                    handle.write(report)
                messagebox.showinfo("Report Saved", f"Report saved to {filename}", parent=self.root)
            except Exception as exc:
                messagebox.showerror("Save Error", f"Failed to save report: {exc}", parent=self.root)

        def email_report():
            recipient_email = self._get_admin_email()
            if not recipient_email:
                recipient_email = simpledialog.askstring(
                    "Admin Email",
                    "Enter admin email address:",
                    parent=report_window,
                )
            if not recipient_email or "@" not in recipient_email:
                messagebox.showwarning("Invalid Email", "Please enter a valid admin email address.", parent=self.root)
                return
            try:
                from education_system.university_system.infrastructure.email.email_service import send_email
                from education_system.university_system.infrastructure.email.template_utils import render_template

                subject, email_body = render_template('academics/module_scheduling_report', {
                    'report_title': "Module Report",
                    'report_content': f"""Module Report

{'=' * 80}
{report}
{'=' * 80}

Report Type: Module Report
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

This email was sent from the Module Scheduling GUI."""
                })

                if not subject or not email_body:
                    subject = "Module Scheduling Report - Module Report"
                    email_body = f"""Module Report

{'=' * 80}
{report}
{'=' * 80}

Report Type: Module Report
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

This email was sent from the Module Scheduling GUI.
"""

                send_email(
                    recipient_email=recipient_email,
                    subject=subject,
                    body=email_body,
                )
                messagebox.showinfo("Email Sent", f"Report sent to {recipient_email}.", parent=self.root)
                self.update_activity_log(f"Emailed module report to {recipient_email}")
            except Exception as exc:
                messagebox.showerror("Email Error", f"Failed to send email: {exc}", parent=self.root)

        ttk.Button(button_frame, text="Save as TXT", command=save_report).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Email to Admin", command=email_report).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", command=report_window.destroy).pack(side=tk.RIGHT, padx=5)

        self.log_activity("Module report generated")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to generate report: {e}", parent=self.root)

ModuleSchedulingGUI.generate_module_report = generate_module_report

def quick_add_module(self):
    """Quick add module from dashboard"""
    self.notebook.select(2)  # Switch to modules tab (adjust index as needed)
    self.show_add_module_dialog()

ModuleSchedulingGUI.quick_add_module = quick_add_module
