from education_system.university_system.modules.domain.academics.gui.course_management_gui.recommendations._imports import (
    tk, ttk, messagebox, ScrolledText, sqlite3, _, DEFAULT_DB_PATH,
)


class RecommendCoursesDialog:
    def __init__(self, parent, auth):
        self.parent = parent
        self.auth = auth

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Course Recommendations")
        self.dialog.geometry("700x600")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.dialog.focus_set()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Recommendation type selection
        type_frame = ttk.LabelFrame(main_frame, text="Recommendation Type", padding=10)
        type_frame.pack(fill=tk.X, pady=5)

        self.rec_type = tk.StringVar(value="popular")

        ttk.Radiobutton(type_frame, text="Most Popular Courses", variable=self.rec_type,
                       value="popular").pack(anchor=tk.W, pady=2)
        ttk.Radiobutton(type_frame, text="Courses with Available Spots", variable=self.rec_type,
                       value="available").pack(anchor=tk.W, pady=2)
        ttk.Radiobutton(type_frame, text="Under-enrolled Courses", variable=self.rec_type,
                       value="under_enrolled").pack(anchor=tk.W, pady=2)
        ttk.Radiobutton(type_frame, text="Prerequisites for Course", variable=self.rec_type,
                       value="prerequisites").pack(anchor=tk.W, pady=2)

        # Course selection for prerequisites (conditional)
        self.prereq_frame = ttk.LabelFrame(main_frame, text="Select Course for Prerequisites", padding=10)
        self.prereq_frame.pack(fill=tk.X, pady=5)

        ttk.Label(self.prereq_frame, text="Course:").pack(side=tk.LEFT)
        self.prereq_course_combo = ttk.Combobox(self.prereq_frame, width=50)
        self.prereq_course_combo.pack(side=tk.LEFT, padx=5)

        # Buttons — pack before results so they stay visible on resize
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10, side=tk.BOTTOM)

        ttk.Button(button_frame, text="Generate Recommendations", command=self.generate_recommendations).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)

        # Results display
        results_frame = ttk.LabelFrame(main_frame, text="Recommendations", padding=10)
        results_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self.results_text = ScrolledText(results_frame, wrap=tk.WORD)
        self.results_text.pack(fill=tk.BOTH, expand=True)

        # Bind radio button changes
        for widget in type_frame.winfo_children():
            if isinstance(widget, ttk.Radiobutton):
                widget.configure(command=self.on_type_change)

        self.load_courses()
        self.on_type_change()

    def load_courses(self):
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()

            cursor.execute(
                "SELECT id, course_code, course_name FROM courses "
                "WHERE course_code IS NOT NULL "
                "AND course_name IS NOT NULL "
                "AND LOWER(COALESCE(status, 'active')) = 'active' "
                "ORDER BY course_code"
            )
            courses = cursor.fetchall()

            course_options = [f"{course[1]} - {course[2]}" for course in courses]
            self.prereq_course_combo['values'] = course_options

            self.course_id_map = {f"{course[1]} - {course[2]}": course[0] for course in courses}

            conn.close()
        except sqlite3.Error as e:
            messagebox.showerror(_("common.database_error"), f"Failed to load courses: {e}")

    def on_type_change(self):
        if self.rec_type.get() == "prerequisites":
            self.prereq_frame.pack(fill=tk.X, pady=5, before=self.results_text.master.master)
        else:
            self.prereq_frame.pack_forget()

    def generate_recommendations(self):
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()

            rec_type = self.rec_type.get()

            self.results_text.delete(1.0, tk.END)
            self.results_text.insert(tk.END, "COURSE RECOMMENDATIONS\n")
            self.results_text.insert(tk.END, "=" * 50 + "\n\n")

            if rec_type == "popular":
                self.results_text.insert(tk.END, "MOST POPULAR COURSES:\n\n")
                cursor.execute("""
                SELECT course_code, course_name, COALESCE(current_enrollment, 0) as enrolled,
                       COALESCE(max_enrollment, 0) as capacity,
                       ROUND(CAST(COALESCE(current_enrollment, 0) AS FLOAT) / COALESCE(max_enrollment, 1) * 100, 1) as popularity
                FROM courses
                WHERE course_code IS NOT NULL
                  AND course_name IS NOT NULL
                  AND LOWER(COALESCE(status, 'active')) = 'active'
                  AND COALESCE(max_enrollment, 0) > 0
                ORDER BY enrolled DESC, popularity DESC
                LIMIT 10
                """)

                courses = cursor.fetchall()
                self.results_text.insert(tk.END, f"{'Code':<10} {'Name':<30} {'Enrolled':<10} {'Popularity':<12}\n")
                self.results_text.insert(tk.END, "-" * 62 + "\n")

                for code, name, enrolled, capacity, popularity in courses:
                    name_short = name[:27] + "..." if len(name) > 30 else name
                    self.results_text.insert(tk.END, f"{code:<10} {name_short:<30} {enrolled:<10} {popularity}%\n")

            elif rec_type == "available":
                self.results_text.insert(tk.END, "COURSES WITH AVAILABLE SPOTS:\n\n")
                cursor.execute("""
                SELECT course_code, course_name, COALESCE(current_enrollment, 0) as enrolled,
                       COALESCE(max_enrollment, 0) as capacity,
                       (COALESCE(max_enrollment, 0) - COALESCE(current_enrollment, 0)) as available
                FROM courses
                WHERE course_code IS NOT NULL
                  AND course_name IS NOT NULL
                  AND LOWER(COALESCE(status, 'active')) = 'active'
                  AND COALESCE(current_enrollment, 0) < COALESCE(max_enrollment, 0)
                ORDER BY available DESC
                LIMIT 15
                """)

                courses = cursor.fetchall()
                self.results_text.insert(tk.END, f"{'Code':<10} {'Name':<30} {'Available':<10} {'Total':<10}\n")
                self.results_text.insert(tk.END, "-" * 60 + "\n")

                for code, name, enrolled, capacity, available in courses:
                    name_short = name[:27] + "..." if len(name) > 30 else name
                    self.results_text.insert(tk.END, f"{code:<10} {name_short:<30} {available:<10} {capacity:<10}\n")

            elif rec_type == "under_enrolled":
                self.results_text.insert(tk.END, "UNDER-ENROLLED COURSES (< 50% capacity):\n\n")
                cursor.execute("""
                SELECT course_code, course_name, COALESCE(current_enrollment, 0) as enrolled,
                       COALESCE(max_enrollment, 0) as capacity
                FROM courses
                WHERE course_code IS NOT NULL
                  AND course_name IS NOT NULL
                  AND LOWER(COALESCE(status, 'active')) = 'active'
                  AND COALESCE(max_enrollment, 0) > 0
                  AND COALESCE(current_enrollment, 0) < (COALESCE(max_enrollment, 0) * 0.5)
                ORDER BY (CAST(COALESCE(current_enrollment, 0) AS FLOAT) / COALESCE(max_enrollment, 1))
                LIMIT 15
                """)

                courses = cursor.fetchall()
                self.results_text.insert(tk.END, f"{'Code':<10} {'Name':<30} {'Fill Rate':<10} {'Enrolled':<10}\n")
                self.results_text.insert(tk.END, "-" * 60 + "\n")

                for code, name, enrolled, capacity in courses:
                    name_short = name[:27] + "..." if len(name) > 30 else name
                    fill_rate = f"{(enrolled/capacity*100):.1f}%" if capacity > 0 else "0%"
                    enrollment_str = f"{enrolled}/{capacity}"
                    self.results_text.insert(tk.END, f"{code:<10} {name_short:<30} {fill_rate:<10} {enrollment_str:<10}\n")

            elif rec_type == "prerequisites":
                selected_text = self.prereq_course_combo.get()
                if selected_text not in self.course_id_map:
                    messagebox.showwarning("No Course Selected", "Please select a course to view prerequisites.")
                    return

                course_id = self.course_id_map[selected_text]

                cursor.execute("""
                SELECT c1.course_code, c1.course_name, c2.course_code, c2.course_name, cp.is_required
                FROM course_prerequisites cp
                JOIN courses c1 ON cp.course_id = c1.id
                JOIN courses c2 ON cp.prerequisite_course_id = c2.id
                WHERE cp.course_id = ?
                ORDER BY cp.is_required DESC, c2.course_code
                """, (course_id,))

                prereqs = cursor.fetchall()

                if prereqs:
                    course_info = prereqs[0]
                    self.results_text.insert(tk.END, f"PREREQUISITES FOR {course_info[0]} - {course_info[1]}:\n\n")
                    self.results_text.insert(tk.END, f"{'Code':<10} {'Name':<30} {'Type':<12}\n")
                    self.results_text.insert(tk.END, "-" * 52 + "\n")

                    for prereq in prereqs:
                        req_type = "Required" if prereq[4] else "Recommended"
                        name_short = prereq[3][:27] + "..." if len(prereq[3]) > 30 else prereq[3]
                        self.results_text.insert(tk.END, f"{prereq[2]:<10} {name_short:<30} {req_type:<12}\n")
                else:
                    self.results_text.insert(tk.END, "No prerequisites found for this course.\n")

            conn.close()

        except sqlite3.Error as e:
            messagebox.showerror(_("common.database_error"), f"Failed to generate recommendations: {e}")
