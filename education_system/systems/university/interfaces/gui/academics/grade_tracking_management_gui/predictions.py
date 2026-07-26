from tkinter import messagebox, simpledialog
import threading

from education_system.systems.university.interfaces.gui.academics.grade_tracking_management_gui._imports import (
    GRADE_CALCULATION_AVAILABLE,
    batch_grade_predictions,
    batch_predict_next_assessments,
    predict_student_next_grade,
    batch_predict_module_grades,
    predict_module_final_grade,
    batch_predict_end_term_gpas,
    predict_end_term_gpa,
    forecast_assessment_performance,
)


class PredictionsMixin:
    # Grade Predictions
    def batch_grade_predictions_gui(self):
        """Perform batch grade predictions for multiple students"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to batch predict grades.")
            return

        if not (self.auth.check_permission('manage_grades') or
                self.auth.check_permission('use_ml_models')):
            messagebox.showerror("Error", "You don't have permission to use batch predictions.")
            return

        try:
            if GRADE_CALCULATION_AVAILABLE:
                from education_system.systems.university.infrastructure.database.db import get_connection

                def predict():
                    try:
                        conn = get_connection()
                        cursor = conn.cursor()
                        batch_grade_predictions(cursor)
                        conn.close()
                    except Exception as e:
                        print(f"Error with batch grade predictions: {e}")

                thread = threading.Thread(target=predict, daemon=True)
                thread.start()
            else:
                messagebox.showerror("Error", "Batch grade predictions not available.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to perform batch predictions: {str(e)}")

    def batch_predict_next_assessments_gui(self):
        """Predict next assessment grades for all students"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to predict next assessments.")
            return

        if not (self.auth.check_permission('manage_grades') or
                self.auth.check_permission('use_ml_models')):
            messagebox.showerror("Error", "You don't have permission to use batch predictions.")
            return

        try:
            if GRADE_CALCULATION_AVAILABLE:
                from education_system.systems.university.infrastructure.database.db import get_connection

                def predict():
                    try:
                        conn = get_connection()
                        cursor = conn.cursor()
                        batch_predict_next_assessments(cursor)
                        conn.close()
                    except Exception as e:
                        print(f"Error predicting next assessments: {e}")

                thread = threading.Thread(target=predict, daemon=True)
                thread.start()
            else:
                messagebox.showerror("Error", "Batch predict next assessments not available.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to predict next assessments: {str(e)}")

    def predict_student_next_grade_gui(self, student_id=None):
        """Predict next grade for specific student"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to predict student grades.")
            return

        try:
            if GRADE_CALCULATION_AVAILABLE:
                from education_system.systems.university.infrastructure.database.db import get_connection

                if not student_id:
                    student_id = simpledialog.askstring("Student ID", "Enter Student ID:", parent=self.root)
                    if not student_id:
                        return

                def predict():
                    try:
                        conn = get_connection()
                        cursor = conn.cursor()
                        prediction = predict_student_next_grade(cursor, student_id)
                        print(f"Predicted next grade for {student_id}: {prediction}")
                        conn.close()
                    except Exception as e:
                        print(f"Error predicting student next grade: {e}")

                thread = threading.Thread(target=predict, daemon=True)
                thread.start()
            else:
                messagebox.showerror("Error", "Predict student next grade not available.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to predict next grade: {str(e)}")

    def batch_predict_module_grades_gui(self):
        """Predict final module grades for specific module"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to predict module grades.")
            return

        if not (self.auth.check_permission('manage_grades') or
                self.auth.check_permission('use_ml_models')):
            messagebox.showerror("Error", "You don't have permission to predict module grades.")
            return

        try:
            if GRADE_CALCULATION_AVAILABLE:
                from education_system.systems.university.infrastructure.database.db import get_connection

                def predict():
                    try:
                        conn = get_connection()
                        cursor = conn.cursor()
                        batch_predict_module_grades(cursor)
                        conn.close()
                    except Exception as e:
                        print(f"Error predicting module grades: {e}")

                thread = threading.Thread(target=predict, daemon=True)
                thread.start()
            else:
                messagebox.showerror("Error", "Batch predict module grades not available.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to predict module grades: {str(e)}")

    def predict_module_final_grade_gui(self, student_id=None, module_code=None):
        """Predict final module grade for student"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to predict module grades.")
            return

        try:
            if GRADE_CALCULATION_AVAILABLE:
                from education_system.systems.university.infrastructure.database.db import get_connection

                if not student_id:
                    student_id = simpledialog.askstring("Student ID", "Enter Student ID:", parent=self.root)
                    if not student_id:
                        return

                if not module_code:
                    module_code = simpledialog.askstring("Module Code", "Enter Module Code:", parent=self.root)
                    if not module_code:
                        return

                def predict():
                    try:
                        conn = get_connection()
                        cursor = conn.cursor()
                        prediction = predict_module_final_grade(cursor, student_id, module_code)
                        print(f"Predicted module grade for {student_id} in {module_code}: {prediction}")
                        conn.close()
                    except Exception as e:
                        print(f"Error predicting module final grade: {e}")

                thread = threading.Thread(target=predict, daemon=True)
                thread.start()
            else:
                messagebox.showerror("Error", "Predict module final grade not available.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to predict module final grade: {str(e)}")

    def batch_predict_end_term_gpas_gui(self):
        """Predict end-of-term GPAs for all students"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to predict end-term GPAs.")
            return

        if not (self.auth.check_permission('manage_grades') or
                self.auth.check_permission('use_ml_models')):
            messagebox.showerror("Error", "You don't have permission to predict GPAs.")
            return

        try:
            if GRADE_CALCULATION_AVAILABLE:
                from education_system.systems.university.infrastructure.database.db import get_connection

                def predict():
                    try:
                        conn = get_connection()
                        cursor = conn.cursor()
                        batch_predict_end_term_gpas(cursor)
                        conn.close()
                    except Exception as e:
                        print(f"Error predicting end-term GPAs: {e}")

                thread = threading.Thread(target=predict, daemon=True)
                thread.start()
            else:
                messagebox.showerror("Error", "Batch predict end-term GPAs not available.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to predict end-term GPAs: {str(e)}")

    def predict_end_term_gpa_gui(self, student_id=None):
        """Predict end-of-term GPA for student"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to predict student GPA.")
            return

        try:
            if GRADE_CALCULATION_AVAILABLE:
                from education_system.systems.university.infrastructure.database.db import get_connection

                if not student_id:
                    student_id = simpledialog.askstring("Student ID", "Enter Student ID:", parent=self.root)
                    if not student_id:
                        return

                def predict():
                    try:
                        conn = get_connection()
                        cursor = conn.cursor()
                        prediction = predict_end_term_gpa(cursor, student_id)
                        print(f"Predicted end-term GPA for {student_id}: {prediction}")
                        conn.close()
                    except Exception as e:
                        print(f"Error predicting end-term GPA: {e}")

                thread = threading.Thread(target=predict, daemon=True)
                thread.start()
            else:
                messagebox.showerror("Error", "Predict end-term GPA not available.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to predict end-term GPA: {str(e)}")

    def forecast_assessment_performance_gui(self):
        """Forecast assessment performance trends"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to forecast assessment performance.")
            return

        if not (self.auth.check_permission('manage_grades') or
                self.auth.check_permission('view_reports')):
            messagebox.showerror("Error", "You don't have permission to forecast performance.")
            return

        try:
            if GRADE_CALCULATION_AVAILABLE:
                from education_system.systems.university.infrastructure.database.db import get_connection

                def forecast():
                    try:
                        conn = get_connection()
                        cursor = conn.cursor()
                        forecast_assessment_performance(cursor)
                        conn.close()
                    except Exception as e:
                        print(f"Error forecasting assessment performance: {e}")

                thread = threading.Thread(target=forecast, daemon=True)
                thread.start()
            else:
                messagebox.showerror("Error", "Forecast assessment performance not available.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to forecast assessment performance: {str(e)}")
