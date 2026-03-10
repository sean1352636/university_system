from tkinter import messagebox, simpledialog
import threading

from ._imports import (
    GRADE_CALCULATION_AVAILABLE,
    record_assessment_grades,
    update_grades,
    view_student_grades,
    update_module_grade,
    calculate_gpa,
    calculate_student_gpa,
    generate_transcript,
)


class StudentManagementMixin:
    # Student & Assessment Management
    def record_assessment_grades_gui(self):
        """Record grades for students for specific assessment"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to record grades.")
            return

        if not self.auth.check_permission('manage_grades'):
            messagebox.showerror("Error", "You don't have permission to record grades.")
            return

        try:
            if GRADE_CALCULATION_AVAILABLE:
                thread = threading.Thread(target=record_assessment_grades, daemon=True)
                thread.start()
            else:
                messagebox.showerror("Error", "Record assessment grades not available.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to record assessment grades: {str(e)}")

    def update_grades_gui(self):
        """Update existing grades for assessments"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to update grades.")
            return

        if not self.auth.check_permission('manage_grades'):
            messagebox.showerror("Error", "You don't have permission to update grades.")
            return

        try:
            if GRADE_CALCULATION_AVAILABLE:
                thread = threading.Thread(target=update_grades, daemon=True)
                thread.start()
            else:
                messagebox.showerror("Error", "Update grades not available.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to update grades: {str(e)}")

    def view_student_grades_gui(self):
        """View grades for specific student"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to view student grades.")
            return

        try:
            if GRADE_CALCULATION_AVAILABLE:
                thread = threading.Thread(target=view_student_grades, daemon=True)
                thread.start()
            else:
                messagebox.showerror("Error", "View student grades not available.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to view student grades: {str(e)}")

    def update_module_grade_gui(self, student_id=None, module_code=None):
        """Update final grade for student in module"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to update module grades.")
            return

        if not self.auth.check_permission('manage_grades'):
            messagebox.showerror("Error", "You don't have permission to update module grades.")
            return

        try:
            if GRADE_CALCULATION_AVAILABLE:
                from education_system.university_system.infrastructure.database.db import get_connection

                if not student_id:
                    student_id = simpledialog.askstring("Student ID", "Enter Student ID:", parent=self.root)
                    if not student_id:
                        return

                if not module_code:
                    module_code = simpledialog.askstring("Module Code", "Enter Module Code:", parent=self.root)
                    if not module_code:
                        return

                def update():
                    try:
                        conn = get_connection()
                        cursor = conn.cursor()
                        update_module_grade(cursor, student_id, module_code)
                        conn.close()
                    except Exception as e:
                        print(f"Error updating module grade: {e}")

                thread = threading.Thread(target=update, daemon=True)
                thread.start()
            else:
                messagebox.showerror("Error", "Update module grade not available.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to update module grade: {str(e)}")

    # GPA & Transcript Functions
    def calculate_gpa_gui(self):
        """Calculate GPA for student or all students"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to calculate GPA.")
            return

        try:
            if GRADE_CALCULATION_AVAILABLE:
                thread = threading.Thread(target=calculate_gpa, daemon=True)
                thread.start()
            else:
                messagebox.showerror("Error", "Calculate GPA not available.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to calculate GPA: {str(e)}")

    def calculate_student_gpa_gui(self, student_id=None):
        """Calculate GPA for specific student"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to calculate student GPA.")
            return

        try:
            if GRADE_CALCULATION_AVAILABLE:
                from education_system.university_system.infrastructure.database.db import get_connection

                if not student_id:
                    student_id = simpledialog.askstring("Student ID", "Enter Student ID:", parent=self.root)
                    if not student_id:
                        return

                def calculate():
                    try:
                        conn = get_connection()
                        cursor = conn.cursor()
                        gpa = calculate_student_gpa(cursor, student_id)
                        print(f"GPA for {student_id}: {gpa}")
                        conn.close()
                    except Exception as e:
                        print(f"Error calculating student GPA: {e}")

                thread = threading.Thread(target=calculate, daemon=True)
                thread.start()
            else:
                messagebox.showerror("Error", "Calculate student GPA not available.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to calculate student GPA: {str(e)}")

    def generate_transcript_gui(self):
        """Generate official transcript for student"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to generate transcripts.")
            return

        try:
            if GRADE_CALCULATION_AVAILABLE:
                thread = threading.Thread(target=generate_transcript, daemon=True)
                thread.start()
            else:
                messagebox.showerror("Error", "Generate transcript not available.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate transcript: {str(e)}")
