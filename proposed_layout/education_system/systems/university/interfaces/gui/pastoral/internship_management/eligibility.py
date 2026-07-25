from education_system.systems.university.infrastructure.sql_safety import escape_like
from education_system.systems.university.interfaces.gui.pastoral.internship_management._imports import tk, ttk, messagebox, scrolledtext, get_connection


class EligibilityMixin:
    def check_student_eligibility(self, student_id, min_gpa=2.5, required_courses=None):
        """Check if student meets academic requirements for internship"""
        try:
            # Connect to database to get student grades
            conn = get_connection()
            cursor = conn.cursor()

            # Get student's overall GPA
            cursor.execute('''
                SELECT AVG(
                    CASE grade
                        WHEN 'A+' THEN 4.3
                        WHEN 'A' THEN 4.0
                        WHEN 'A-' THEN 3.7
                        WHEN 'B+' THEN 3.3
                        WHEN 'B' THEN 3.0
                        WHEN 'B-' THEN 2.7
                        WHEN 'C+' THEN 2.3
                        WHEN 'C' THEN 2.0
                        WHEN 'C-' THEN 1.7
                        WHEN 'D+' THEN 1.3
                        WHEN 'D' THEN 1.0
                        WHEN 'F' THEN 0.0
                        ELSE 0.0
                    END
                ) as gpa
                FROM student_grades sg
                JOIN students s ON sg.student_id = s.student_id
                WHERE s.student_id = ? AND sg.grade IS NOT NULL
            ''', (student_id,))

            gpa_result = cursor.fetchone()
            current_gpa = gpa_result[0] if gpa_result and gpa_result[0] else 0.0

            # Check if GPA meets minimum requirement
            gpa_meets_requirement = current_gpa >= min_gpa

            # Get student details for display
            cursor.execute('''
                SELECT first_name, last_name, email, course_year
                FROM students
                WHERE student_id = ?
            ''', (student_id,))

            student_result = cursor.fetchone()
            if not student_result:
                conn.close()
                return False, "Student not found"

            first_name, last_name, email, course_year = student_result

            # Check specific course requirements if provided
            courses_met = True
            missing_courses = []

            if required_courses:
                for course in required_courses:
                    cursor.execute('''
                        SELECT grade
                        FROM student_grades sg
                        JOIN course_modules cm ON sg.module_id = cm.module_id
                        WHERE sg.student_id = ? AND cm.module_name LIKE ?
                        AND sg.grade NOT IN ('F', 'Fail')
                    ''', (student_id, f"%{escape_like(course)}%"))

                    if not cursor.fetchone():
                        courses_met = False
                        missing_courses.append(course)

            conn.close()

            # Prepare eligibility result
            eligible = gpa_meets_requirement and courses_met

            eligibility_info = {
                'eligible': eligible,
                'student_name': f"{first_name} {last_name}",
                'student_email': email,
                'course_year': course_year,
                'current_gpa': round(current_gpa, 2),
                'min_gpa_required': min_gpa,
                'gpa_meets_requirement': gpa_meets_requirement,
                'courses_met': courses_met,
                'missing_courses': missing_courses
            }

            return eligible, eligibility_info

        except Exception as e:
            print(f"Error checking student eligibility: {e}")
            return False, f"Error checking eligibility: {e}"

    def show_eligibility_dialog(self, student_id, internship_title, requirements=""):
        """Show detailed eligibility information for student"""
        try:
            # Parse requirements to extract GPA and courses
            min_gpa = 2.5  # Default
            required_courses = []

            if requirements:
                # Simple parsing for GPA requirement
                if "GPA" in requirements.upper() or "gpa" in requirements:
                    import re
                    gpa_match = re.search(r'(\d+\.?\d*)\s*GPA', requirements, re.IGNORECASE)
                    if gpa_match:
                        min_gpa = float(gpa_match.group(1))

                # Simple parsing for course requirements
                if "course" in requirements.lower():
                    # Extract potential course names (simplified)
                    course_keywords = ["programming", "computer science", "mathematics", "statistics", "engineering"]
                    for keyword in course_keywords:
                        if keyword.lower() in requirements.lower():
                            required_courses.append(keyword)

            eligible, eligibility_info = self.check_student_eligibility(student_id, min_gpa, required_courses)

            # Create eligibility dialog
            dialog = tk.Toplevel(self.root)
            dialog.title(f"Eligibility Check: {internship_title}")
            dialog.geometry("600x500")
            dialog.transient(self.root)
            dialog.grab_set()

            main_frame = tk.Frame(dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            # Title
            title_label = tk.Label(main_frame, text="Eligibility Assessment",
                                  font=('Arial', 14, 'bold'))
            title_label.pack(pady=10)

            if isinstance(eligibility_info, str):
                # Error case
                error_label = tk.Label(main_frame, text=eligibility_info,
                                      font=('Arial', 12), fg='red')
                error_label.pack(pady=20)
            else:
                # Success case - show detailed info
                info_text = scrolledtext.ScrolledText(main_frame, height=15, width=70)
                info_text.pack(fill='both', expand=True, pady=10)

                status_color = "green" if eligible else "red"
                status_text = "✅ ELIGIBLE" if eligible else "❌ NOT ELIGIBLE"

                gpa_status = "✅ Met" if eligibility_info['gpa_meets_requirement'] else "❌ Not Met"
                course_status = "✅ All requirements met" if eligibility_info['courses_met'] else "❌ Missing requirements"

                details = f"""ELIGIBILITY STATUS: {status_text}

Student: {eligibility_info['student_name']}
Course Year: {eligibility_info['course_year']}
Position: {internship_title}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ACADEMIC REQUIREMENTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

GPA Requirement:
• Required: {eligibility_info['min_gpa_required']} or higher
• Current: {eligibility_info['current_gpa']}
• Status: {gpa_status}

Course Requirements:
• Status: {course_status}"""

                if eligibility_info['missing_courses']:
                    details += f"\n• Missing: {', '.join(eligibility_info['missing_courses'])}"

                if not eligible:
                    details += "\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\nRECOMMendations:\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"

                    if not eligibility_info['gpa_meets_requirement']:
                        details += f"• Improve your GPA to at least {eligibility_info['min_gpa_required']}\n"

                    if eligibility_info['missing_courses']:
                        details += f"• Complete required courses: {', '.join(eligibility_info['missing_courses'])}\n"

                    details += "• Consider academic support and tutoring services\n"
                    details += "• Speak with your academic advisor for guidance\n"

                info_text.insert('1.0', details)
                info_text.config(state='disabled')

            # Buttons
            button_frame = tk.Frame(main_frame)
            button_frame.pack(pady=20)

            if eligible:
                tk.Button(button_frame, text="✅ Proceed with Application",
                         command=lambda: [dialog.destroy(), self.show_application_form()],
                         bg='green', fg='white', font=('Arial', 10, 'bold')).pack(side='left', padx=5)

            tk.Button(button_frame, text="View Full Grade Report",
                     command=lambda: self.open_grade_report(student_id)).pack(side='left', padx=5)
            tk.Button(button_frame, text="Close", command=dialog.destroy).pack(side='left', padx=5)

        except Exception as e:
            messagebox.showerror("Error", f"Could not check eligibility: {e}")

    def show_my_eligibility(self):
        """Show eligibility check dialog for current student - allows selecting an internship"""
        try:
            # Get current student's ID
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('SELECT student_id FROM users WHERE id = ?', (self.auth.current_user['id'],))
            result = cursor.fetchone()

            if not result or not result[0]:
                messagebox.showerror("Error", "Could not find your student record.")
                conn.close()
                return

            student_id = result[0]

            # Get available internships
            cursor.execute('''
                SELECT internship_id, title, company, requirements
                FROM internships
                WHERE status = 'active'
                ORDER BY title
            ''')
            internships = cursor.fetchall()
            conn.close()

            if not internships:
                messagebox.showinfo("No Internships", "There are no active internships available.")
                return

            # Create selection dialog
            dialog = tk.Toplevel(self.root)
            dialog.title("Check My Eligibility")
            dialog.geometry("500x300")
            dialog.transient(self.root)
            dialog.grab_set()

            main_frame = tk.Frame(dialog, padx=20, pady=20)
            main_frame.pack(fill='both', expand=True)

            tk.Label(main_frame, text="Select an Internship to Check Eligibility",
                    font=('Arial', 14, 'bold')).pack(pady=(0, 20))

            tk.Label(main_frame, text="Internship:",
                    font=('Arial', 11)).pack(anchor='w')

            internship_var = tk.StringVar()
            internship_combo = ttk.Combobox(main_frame, textvariable=internship_var,
                                           state='readonly', width=50)

            # Format options and store mapping
            options = []
            internship_map = {}
            for intern in internships:
                option_text = f"{intern[1]} at {intern[2]}"
                options.append(option_text)
                internship_map[option_text] = {
                    'id': intern[0],
                    'title': intern[1],
                    'requirements': intern[3] or ''
                }

            internship_combo['values'] = options
            if options:
                internship_combo.current(0)
            internship_combo.pack(fill='x', pady=10)

            def check_eligibility():
                selected = internship_var.get()
                if not selected:
                    messagebox.showwarning("Selection Required", "Please select an internship.")
                    return

                intern_info = internship_map[selected]
                dialog.destroy()
                self.show_eligibility_dialog(student_id, intern_info['title'], intern_info['requirements'])

            btn_frame = tk.Frame(main_frame)
            btn_frame.pack(pady=20)

            tk.Button(btn_frame, text="Check Eligibility",
                     command=check_eligibility,
                     bg='#9b59b6', fg='white', font=('Arial', 11, 'bold'),
                     padx=20, pady=8).pack(side='left', padx=5)

            tk.Button(btn_frame, text="Cancel",
                     command=dialog.destroy,
                     bg='#6c757d', fg='white', font=('Arial', 11),
                     padx=20, pady=8).pack(side='left', padx=5)

        except Exception as e:
            messagebox.showerror("Error", f"Could not open eligibility check: {e}")

    def open_grade_report(self, student_id):
        """Open the grade management GUI for detailed grade view"""
        try:
            from education_system.systems.university.interfaces.gui.academics.grade_tracking_management_gui import GradeTrackingManagementGUI as GradeManagementGUI

            grade_window = tk.Toplevel(self.root)
            grade_window.title("Student Grade Report")
            grade_window.geometry("1000x700")

            grade_gui = GradeManagementGUI(grade_window, auth=self.auth)

            # Pre-filter for specific student if method exists
            if hasattr(grade_gui, 'filter_student_grades'):
                grade_gui.filter_student_grades(student_id)

            messagebox.showinfo("Grade Report", f"Grade report opened for student ID: {student_id}")

        except ImportError:
            messagebox.showerror("Error", "Grade management system is not available")
        except Exception as e:
            messagebox.showerror("Error", f"Could not open grade system: {e}")

    def check_eligibility_before_application(self, internship_id):
        """Check eligibility before allowing application"""
        try:
            # Get current student ID
            if not self.auth or not self.auth.current_user:
                messagebox.showerror("Error", "Please log in to apply for internships")
                return False

            # Get student ID from auth
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT student_id FROM students s
                JOIN users u ON s.user_id = u.id
                WHERE u.username = ?
            ''', (self.auth.current_user['username'],))

            student_result = cursor.fetchone()
            if not student_result:
                messagebox.showerror("Error", "Student record not found")
                conn.close()
                return False

            student_id = student_result[0]

            # Get internship requirements
            cursor.execute('''
                SELECT title, requirements FROM internships WHERE id = ?
            ''', (internship_id,))

            internship_result = cursor.fetchone()
            conn.close()

            if not internship_result:
                messagebox.showerror("Error", "Internship not found")
                return False

            internship_title, requirements = internship_result

            # Show eligibility dialog
            self.show_eligibility_dialog(student_id, internship_title, requirements or "")

            return True

        except Exception as e:
            messagebox.showerror("Error", f"Could not check eligibility: {e}")
            return False
