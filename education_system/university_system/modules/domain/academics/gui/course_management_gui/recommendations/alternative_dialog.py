from education_system.university_system.modules.domain.academics.gui.course_management_gui.recommendations._imports import (
    tk, ttk, messagebox, sqlite3, _, DEFAULT_DB_PATH,
)


class AlternativeCourseDialog:
    def __init__(self, parent, auth):
        self.parent = parent
        self.auth = auth

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Find Alternative Courses")
        self.dialog.geometry("800x600")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.dialog.focus_set()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Course selection
        selection_frame = ttk.LabelFrame(main_frame, text="Select Reference Course", padding=10)
        selection_frame.pack(fill=tk.X, pady=5)

        ttk.Label(selection_frame, text="Course:").pack(side=tk.LEFT)
        self.course_combo = ttk.Combobox(selection_frame, width=50)
        self.course_combo.pack(side=tk.LEFT, padx=5)

        ttk.Button(selection_frame, text="Find Alternatives",
                  command=self.find_alternatives).pack(side=tk.RIGHT, padx=5)

        # Results display
        results_frame = ttk.LabelFrame(main_frame, text="Alternative Courses", padding=10)
        results_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        columns = ("Code", "Name", "Department", "Level", "Match Type", "Available")
        self.results_tree = ttk.Treeview(results_frame, columns=columns, show="headings")

        for col in columns:
            self.results_tree.heading(col, text=col)

        scrollbar = ttk.Scrollbar(results_frame, orient=tk.VERTICAL, command=self.results_tree.yview)
        self.results_tree.configure(yscrollcommand=scrollbar.set)

        self.results_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.load_course_options()

        ttk.Button(main_frame, text="Close", command=self.dialog.destroy).pack(pady=10)

    def load_course_options(self):
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
            self.course_combo['values'] = course_options

            self.course_id_map = {f"{course[1]} - {course[2]}": course[0] for course in courses}

            conn.close()
        except sqlite3.Error as e:
            messagebox.showerror(_("common.database_error"), f"Failed to load courses: {e}")

    def find_alternatives(self):
        selected_text = self.course_combo.get()
        if selected_text not in self.course_id_map:
            messagebox.showwarning(_("common.selection_required"), "Please select a course.")
            return

        course_id = self.course_id_map[selected_text]

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()

            # Get reference course details
            cursor.execute("SELECT course_code, course_name, department, level, credit_hours FROM courses WHERE id = ?", (course_id,))
            ref_course = cursor.fetchone()

            if not ref_course:
                return

            ref_code, ref_name, ref_dept, ref_level, ref_credits = ref_course

            # Find alternatives
            alternatives = []

            # Same department and level
            cursor.execute("""
            SELECT course_code, course_name, department, level, 'Same Dept & Level' as match_type,
                   (COALESCE(max_enrollment, 0) - COALESCE(current_enrollment, 0)) as available
            FROM courses
            WHERE course_code IS NOT NULL
              AND course_name IS NOT NULL
              AND department = ?
              AND level = ?
              AND id != ?
              AND LOWER(COALESCE(status, 'active')) = 'active'
            ORDER BY course_name
            """, (ref_dept, ref_level, course_id))
            alternatives.extend(cursor.fetchall())

            # Same department, different level
            cursor.execute("""
            SELECT course_code, course_name, department, level, 'Same Department' as match_type,
                   (COALESCE(max_enrollment, 0) - COALESCE(current_enrollment, 0)) as available
            FROM courses
            WHERE course_code IS NOT NULL
              AND course_name IS NOT NULL
              AND department = ?
              AND level != ?
              AND id != ?
              AND LOWER(COALESCE(status, 'active')) = 'active'
            ORDER BY course_name
            """, (ref_dept, ref_level, course_id))
            alternatives.extend(cursor.fetchall())

            # Same level, different department
            cursor.execute("""
            SELECT course_code, course_name, department, level, 'Same Level' as match_type,
                   (COALESCE(max_enrollment, 0) - COALESCE(current_enrollment, 0)) as available
            FROM courses
            WHERE course_code IS NOT NULL
              AND course_name IS NOT NULL
              AND level = ?
              AND department != ?
              AND id != ?
              AND LOWER(COALESCE(status, 'active')) = 'active'
            ORDER BY course_name
            """, (ref_level, ref_dept, course_id))
            alternatives.extend(cursor.fetchall())

            # Clear previous results
            for item in self.results_tree.get_children():
                self.results_tree.delete(item)

            # Remove duplicates and populate tree
            seen = set()
            for alt in alternatives:
                key = alt[0]  # course_code
                if key not in seen:
                    seen.add(key)
                    self.results_tree.insert("", tk.END, values=alt)

            conn.close()

            if not alternatives:
                messagebox.showinfo(_("common.no_results"), "No alternative courses found.")

        except sqlite3.Error as e:
            messagebox.showerror(_("common.database_error"), f"Failed to find alternatives: {e}")
