"""Update operations manager for batch operations GUI."""
import os
import threading

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

from education_system.post_18.university_system.modules.shared.gui.batch_operations.constants import _t, logger
from education_system.post_18.university_system.modules.shared.gui.batch_operations.progress_dialog import GUIProgressDialog


class UpdateManager:
    """Manages update operations for BatchOperationsGUI."""

    def __init__(self, gui):
        self.gui = gui

    def batch_update_records(self):
        """GUI version of batch update records"""
        file_path = filedialog.askopenfilename(
            title="Select file with update data (must contain student_id column)",
            filetypes=[("CSV files", "*.csv"), ("Excel files", "*.xlsx *.xls"), ("All files", "*.*")]
        )

        if not file_path:
            return

        # Show update confirmation
        if not messagebox.askyesno(_t("batch_ops.msg_titles.batch_update"),
                                  "This will update existing student records.\n"
                                  "A backup will be created automatically.\n\n"
                                  "Continue?"):
            return

        def update_worker():
            try:
                progress_dialog = GUIProgressDialog(self.gui.root, "Batch Update", "Updating student records")

                result = self.gui.backend.batch_update_from_file(file_path, progress_callback=progress_dialog.update_progress)

                progress_dialog.close()
                self.gui.show_import_results(result, "Batch Update")

            except Exception as e:
                messagebox.showerror(_t("batch_ops.msg_titles.error"), _t("batch_ops.errors.generic_error", error=str(e)))

        thread = threading.Thread(target=update_worker)
        thread.daemon = True
        thread.start()

    def bulk_module_operations(self):
        """GUI version of bulk module operations"""
        dialog = tk.Toplevel(self.gui.root)
        dialog.title(_t("batch_ops.windows.bulk_modules"))
        dialog.geometry("600x500")
        dialog.transient(self.gui.root)
        dialog.grab_set()

        # Center dialog
        dialog.geometry("+%d+%d" % (self.gui.root.winfo_rootx() + 100, self.gui.root.winfo_rooty() + 100))

        # Header
        header = ttk.Label(dialog, text=_t("batch_ops.labels.bulk_module_ops"), font=("Arial", 14, "bold"))
        header.pack(pady=10)

        # Operation selection
        operation_frame = ttk.LabelFrame(dialog, text=_t("batch_ops.labels.select_operation"), padding="10")
        operation_frame.pack(fill=tk.X, padx=20, pady=10)

        operation_var = tk.StringVar(value="add")

        ttk.Radiobutton(operation_frame, text="Add module to multiple students",
                       variable=operation_var, value="add").pack(anchor='w')
        ttk.Radiobutton(operation_frame, text="Remove module from multiple students",
                       variable=operation_var, value="remove").pack(anchor='w')
        ttk.Radiobutton(operation_frame, text="Replace module for multiple students",
                       variable=operation_var, value="replace").pack(anchor='w')
        ttk.Radiobutton(operation_frame, text="Import module enrollments from file",
                       variable=operation_var, value="import").pack(anchor='w')

        # Student selection
        student_frame = ttk.LabelFrame(dialog, text=_t("batch_ops.labels.select_students"), padding="10")
        student_frame.pack(fill=tk.X, padx=20, pady=10)

        student_selection_var = tk.StringVar(value="course")

        ttk.Radiobutton(student_frame, text="Filter by course",
                       variable=student_selection_var, value="course").pack(anchor='w')
        ttk.Radiobutton(student_frame, text="Upload student ID list",
                       variable=student_selection_var, value="file").pack(anchor='w')
        ttk.Radiobutton(student_frame, text="All students",
                       variable=student_selection_var, value="all").pack(anchor='w')

        # Course selection
        course_frame = ttk.Frame(student_frame)
        course_frame.pack(fill=tk.X, pady=5)

        ttk.Label(course_frame, text=_t("batch_ops.labels.course")).pack(side=tk.LEFT)
        course_var = ttk.Combobox(course_frame, values=["CS", "DS"], state="readonly", width=10)
        course_var.set("CS")
        course_var.pack(side=tk.LEFT, padx=(10, 0))

        # Module details
        module_frame = ttk.LabelFrame(dialog, text=_t("batch_ops.labels.module_details"), padding="10")
        module_frame.pack(fill=tk.X, padx=20, pady=10)

        ttk.Label(module_frame, text=_t("batch_ops.labels.module_code")).grid(row=0, column=0, sticky='w', pady=5)
        module_code_entry = ttk.Entry(module_frame, width=20)
        module_code_entry.grid(row=0, column=1, padx=(10, 0), pady=5)

        ttk.Label(module_frame, text=_t("batch_ops.labels.module_name")).grid(row=1, column=0, sticky='w', pady=5)
        module_name_entry = ttk.Entry(module_frame, width=40)
        module_name_entry.grid(row=1, column=1, padx=(10, 0), pady=5)

        ttk.Label(module_frame, text=_t("batch_ops.labels.module_type")).grid(row=2, column=0, sticky='w', pady=5)
        module_type_combo = ttk.Combobox(module_frame, values=["compulsory", "optional", "CS", "DS"],
                                        state="readonly", width=20)
        module_type_combo.set("optional")
        module_type_combo.grid(row=2, column=1, padx=(10, 0), pady=5)

        # Buttons
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=20)

        def execute_operation():
            operation = operation_var.get()
            student_selection = student_selection_var.get()

            if operation == "import":
                # File import operation
                file_path = filedialog.askopenfilename(
                    title="Select module enrollment file",
                    filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
                )
                if file_path:
                    dialog.destroy()
                    self.execute_module_import(file_path)
            else:
                # Other operations require module details
                module_code = module_code_entry.get().strip()
                module_name = module_name_entry.get().strip()
                module_type = module_type_combo.get()

                if not module_code:
                    messagebox.showerror(_t("batch_ops.msg_titles.error"), "Module code is required")
                    return

                if operation in ["add", "replace"] and not module_name:
                    messagebox.showerror(_t("batch_ops.msg_titles.error"), "Module name is required for add/replace operations")
                    return

                course = course_var.get()
                dialog.destroy()
                self.execute_bulk_module_operation(operation, student_selection, course,
                                                 module_code, module_name, module_type)

        ttk.Button(button_frame, text=_t("batch_ops.buttons.execute"), command=execute_operation).pack(side=tk.LEFT, padx=10)
        ttk.Button(button_frame, text=_t("batch_ops.buttons.cancel"), command=dialog.destroy).pack(side=tk.LEFT)

    def execute_bulk_module_operation(self, operation, student_selection, course, module_code, module_name, module_type):
        """Execute bulk module operation"""
        def operation_worker():
            try:
                # Get student IDs based on selection
                if student_selection == "course":
                    student_ids = self.gui.backend.get_students_by_course(course)
                elif student_selection == "file":
                    file_path = filedialog.askopenfilename(
                        title="Select file with student IDs",
                        filetypes=[("CSV files", "*.csv"), ("Text files", "*.txt"), ("All files", "*.*")]
                    )
                    if not file_path:
                        return
                    student_ids = self.gui.backend.read_student_ids_from_file(file_path)
                else:  # all
                    student_ids = self.gui.backend.get_all_student_ids()

                if not student_ids:
                    messagebox.showerror(_t("batch_ops.msg_titles.error"), "No students found matching criteria")
                    return

                # Confirm operation
                if not messagebox.askyesno(_t("batch_ops.msg_titles.confirm_operation"),
                                         f"{operation.title()} module {module_code} for {len(student_ids)} students?"):
                    return

                progress_dialog = GUIProgressDialog(self.gui.root, "Module Operation", f"{operation.title()}ing modules")
                progress_dialog.set_total(len(student_ids))

                success_count = self.gui.backend.execute_bulk_module_operation(
                    operation, student_ids, module_code, module_name, module_type,
                    progress_callback=progress_dialog.update_progress
                )

                progress_dialog.close()

                messagebox.showinfo(_t("batch_ops.msg_titles.operation_complete"),
                                   f"Successfully {operation}ed module for {success_count} students")

            except Exception as e:
                messagebox.showerror(_t("batch_ops.msg_titles.error"), _t("batch_ops.errors.generic_error", error=str(e)))

        thread = threading.Thread(target=operation_worker)
        thread.daemon = True
        thread.start()

    def execute_module_import(self, file_path):
        """Execute module enrollment import"""
        def import_worker():
            try:
                progress_dialog = GUIProgressDialog(self.gui.root, "Module Import", "Importing module enrollments")

                result = self.gui.backend.import_module_enrollments_from_file(
                    file_path, progress_callback=progress_dialog.update_progress
                )

                progress_dialog.close()
                self.gui.show_import_results(result, "Module Enrollment Import")

            except Exception as e:
                messagebox.showerror(_t("batch_ops.msg_titles.error"), _t("batch_ops.errors.generic_error", error=str(e)))

        thread = threading.Thread(target=import_worker)
        thread.daemon = True
        thread.start()

    def import_grade_data(self):
        """GUI version of grade data import"""
        file_path = filedialog.askopenfilename(
            title="Select grade data file (CSV with student_id, module_code, grade columns)",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )

        if not file_path:
            return

        def import_worker():
            try:
                progress_dialog = GUIProgressDialog(self.gui.root, "Grade Import", "Importing grade data")

                result = self.gui.backend.import_grade_data_from_file(
                    file_path, progress_callback=progress_dialog.update_progress
                )

                progress_dialog.close()
                self.gui.show_import_results(result, "Grade Data Import")

            except Exception as e:
                messagebox.showerror(_t("batch_ops.msg_titles.error"), _t("batch_ops.errors.generic_error", error=str(e)))

        thread = threading.Thread(target=import_worker)
        thread.daemon = True
        thread.start()
