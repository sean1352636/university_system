from education_system.systems.university.interfaces.gui.academics.course_management_gui.recommendations._imports import (
    tk, ttk, messagebox, sqlite3, _, DEFAULT_DB_PATH, datetime,
)


class PrerequisitesMixin:
    def add_prerequisite_gui(self):
        """
        Add a prerequisite to a course with circular dependency checking.
        Opens a dialog to select course and prerequisite.
        """
        dialog = tk.Toplevel(self.root)
        dialog.title("Add Course Prerequisite")
        dialog.geometry("500x300")
        dialog.transient(self.root)

        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Add Prerequisite to Course",
                 font=('Arial', 12, 'bold')).pack(pady=(0, 10))

        # Course selection
        course_frame = ttk.LabelFrame(main_frame, text="Select Course", padding="10")
        course_frame.pack(fill=tk.X, pady=5)

        ttk.Label(course_frame, text="Course:").grid(row=0, column=0, sticky=tk.W, pady=5)
        course_var = tk.StringVar()
        course_combo = ttk.Combobox(course_frame, textvariable=course_var, state='readonly', width=40)
        course_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=5, padx=5)

        # Prerequisite selection
        prereq_frame = ttk.LabelFrame(main_frame, text="Select Prerequisite", padding="10")
        prereq_frame.pack(fill=tk.X, pady=5)

        ttk.Label(prereq_frame, text="Prerequisite:").grid(row=0, column=0, sticky=tk.W, pady=5)
        prereq_var = tk.StringVar()
        prereq_combo = ttk.Combobox(prereq_frame, textvariable=prereq_var, state='readonly', width=40)
        prereq_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=5, padx=5)

        # Required checkbox
        required_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(prereq_frame, text="Required (vs. Recommended)",
                       variable=required_var).grid(row=1, column=1, sticky=tk.W, pady=5)

        # Load courses
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
            conn.close()

            course_list = [f"{code} - {name} (ID: {id})" for id, code, name in courses]
            course_combo['values'] = course_list
            prereq_combo['values'] = course_list

        except sqlite3.Error as e:
            messagebox.showerror(_("common.database_error"), f"Failed to load courses: {e}")
            dialog.destroy()
            return

        def save_prerequisite():
            if not course_var.get() or not prereq_var.get():
                messagebox.showwarning("Incomplete", "Please select both course and prerequisite")
                return

            try:
                # Extract IDs from selection
                course_id = int(course_var.get().split("ID: ")[1].rstrip(")"))
                prereq_id = int(prereq_var.get().split("ID: ")[1].rstrip(")"))

                if course_id == prereq_id:
                    messagebox.showerror(_("common.error"), "A course cannot be its own prerequisite")
                    return

                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
                try:
                    cursor = conn.cursor()

                    # Check for circular dependency
                    if self.check_circular_prerequisite_db(cursor, course_id, prereq_id):
                        messagebox.showerror("Circular Dependency",
                                           "Adding this prerequisite would create a circular dependency!")
                finally:
                    conn.close()
                    return

                # Check if already exists
                cursor.execute("""
                    SELECT id FROM course_prerequisites
                    WHERE course_id = ? AND prerequisite_course_id = ?
                """, (course_id, prereq_id))

                if cursor.fetchone():
                    messagebox.showwarning("Duplicate", "This prerequisite already exists")
                    conn.close()
                    return

                # Add prerequisite
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute("""
                    INSERT INTO course_prerequisites (course_id, prerequisite_course_id, is_required, created_at)
                    VALUES (?, ?, ?, ?)
                """, (course_id, prereq_id, 1 if required_var.get() else 0, timestamp))

                conn.commit()
                conn.close()

                messagebox.showinfo(_("common.success"), "Prerequisite added successfully!")
                self.update_status("Prerequisite added successfully")
                dialog.destroy()

            except Exception as e:
                messagebox.showerror(_("common.error"), f"Failed to add prerequisite: {e}")

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)

        ttk.Button(button_frame, text="Save", command=save_prerequisite).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)

    def check_circular_prerequisite_db(self, cursor, course_id, prereq_id):
        """
        Check if adding a prerequisite would create a circular dependency.
        Uses recursive helper function to traverse prerequisite tree.
        """
        visited = set()

        def has_prerequisite(cid, target_id):
            """Nested helper function to recursively check prerequisites"""
            if cid in visited:
                return False
            visited.add(cid)

            cursor.execute("""
                SELECT prerequisite_course_id FROM course_prerequisites
                WHERE course_id = ?
            """, (cid,))
            prereqs = cursor.fetchall()

            for (pid,) in prereqs:
                if pid == target_id:
                    return True
                if has_prerequisite(pid, target_id):
                    return True
            return False

        return has_prerequisite(prereq_id, course_id)

    def view_prerequisites_gui(self):
        """
        View prerequisites for a selected course or all courses.
        Opens a dialog with prerequisite information.
        """
        dialog = tk.Toplevel(self.root)
        dialog.title("View Course Prerequisites")
        dialog.geometry("700x500")
        dialog.transient(self.root)

        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Course Prerequisites",
                 font=('Arial', 12, 'bold')).pack(pady=(0, 10))

        # Course selection
        select_frame = ttk.Frame(main_frame)
        select_frame.pack(fill=tk.X, pady=5)

        ttk.Label(select_frame, text="Select Course:").pack(side=tk.LEFT, padx=5)
        course_var = tk.StringVar()
        course_combo = ttk.Combobox(select_frame, textvariable=course_var, state='readonly', width=40)
        course_combo.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        # Add "All Courses" option
        all_option = "-- All Courses --"

        # Text display
        text_frame = ttk.Frame(main_frame)
        text_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        scrollbar = ttk.Scrollbar(text_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        text_widget = tk.Text(text_frame, wrap=tk.WORD, yscrollcommand=scrollbar.set,
                             font=('Courier', 10))
        text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=text_widget.yview)

        def load_courses():
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
                conn.close()

                course_list = [all_option] + [f"{code} - {name} (ID: {id})" for id, code, name in courses]
                course_combo['values'] = course_list
                course_combo.current(0)

            except sqlite3.Error as e:
                messagebox.showerror(_("common.database_error"), f"Failed to load courses: {e}")

        def show_prerequisites(*args):
            text_widget.delete('1.0', tk.END)

            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
                cursor = conn.cursor()

                selected = course_var.get()

                if selected == all_option or not selected:
                    # Show all prerequisites
                    cursor.execute("""
                        SELECT c1.course_code, c1.course_name, c2.course_code, c2.course_name, cp.is_required
                        FROM course_prerequisites cp
                        JOIN courses c1 ON cp.course_id = c1.id
                        JOIN courses c2 ON cp.prerequisite_course_id = c2.id
                        ORDER BY c1.course_code, c2.course_code
                    """)

                    prereqs = cursor.fetchall()
                    if prereqs:
                        text_widget.insert(tk.END, "ALL COURSE PREREQUISITES\n")
                        text_widget.insert(tk.END, "=" * 70 + "\n\n")

                        current_course = None
                        for course_code, course_name, prereq_code, prereq_name, is_req in prereqs:
                            if current_course != course_code:
                                current_course = course_code
                                text_widget.insert(tk.END, f"\n{course_code} - {course_name}:\n")
                                text_widget.insert(tk.END, "-" * 70 + "\n")

                            req_status = "Required" if is_req else "Recommended"
                            text_widget.insert(tk.END, f"  → {prereq_code} - {prereq_name} ({req_status})\n")
                    else:
                        text_widget.insert(tk.END, "No prerequisites found in the system.\n")
                else:
                    # Show prerequisites for specific course
                    course_id = int(selected.split("ID: ")[1].rstrip(")"))

                    cursor.execute("""
                        SELECT c1.course_code, c1.course_name, c2.course_code, c2.course_name, cp.is_required
                        FROM course_prerequisites cp
                        JOIN courses c1 ON cp.course_id = c1.id
                        JOIN courses c2 ON cp.prerequisite_course_id = c2.id
                        WHERE cp.course_id = ?
                        ORDER BY c2.course_code
                    """, (course_id,))

                    prereqs = cursor.fetchall()
                    if prereqs:
                        course_code, course_name = prereqs[0][0], prereqs[0][1]
                        text_widget.insert(tk.END, f"PREREQUISITES FOR: {course_code} - {course_name}\n")
                        text_widget.insert(tk.END, "=" * 70 + "\n\n")

                        for _, _, prereq_code, prereq_name, is_req in prereqs:
                            req_status = "Required" if is_req else "Recommended"
                            text_widget.insert(tk.END, f"{prereq_code} - {prereq_name} ({req_status})\n")
                    else:
                        text_widget.insert(tk.END, "No prerequisites found for this course.\n")

                conn.close()

            except Exception as e:
                text_widget.insert(tk.END, f"Error loading prerequisites: {e}\n")

        course_combo.bind('<<ComboboxSelected>>', show_prerequisites)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)

        ttk.Button(button_frame, text="Refresh", command=show_prerequisites).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)

        # Initial load
        load_courses()
        show_prerequisites()

    def remove_prerequisite_gui(self):
        """
        Remove a prerequisite from a course.
        Opens a dialog to select and remove prerequisites.
        """
        dialog = tk.Toplevel(self.root)
        dialog.title("Remove Course Prerequisite")
        dialog.geometry("600x400")
        dialog.transient(self.root)

        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Remove Course Prerequisite",
                 font=('Arial', 12, 'bold')).pack(pady=(0, 10))

        # Course selection
        select_frame = ttk.Frame(main_frame)
        select_frame.pack(fill=tk.X, pady=5)

        ttk.Label(select_frame, text="Select Course:").pack(side=tk.LEFT, padx=5)
        course_var = tk.StringVar()
        course_combo = ttk.Combobox(select_frame, textvariable=course_var, state='readonly', width=40)
        course_combo.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        # Prerequisites list
        list_frame = ttk.LabelFrame(main_frame, text="Current Prerequisites", padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        prereq_listbox = tk.Listbox(list_frame, height=10)
        prereq_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=prereq_listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        prereq_listbox.config(yscrollcommand=scrollbar.set)

        # Store prerequisite IDs
        prereq_data = {}

        def load_courses():
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
                conn.close()

                course_list = [f"{code} - {name} (ID: {id})" for id, code, name in courses]
                course_combo['values'] = course_list

            except sqlite3.Error as e:
                messagebox.showerror(_("common.database_error"), f"Failed to load courses: {e}")

        def load_prerequisites(*args):
            prereq_listbox.delete(0, tk.END)
            prereq_data.clear()

            if not course_var.get():
                return

            try:
                course_id = int(course_var.get().split("ID: ")[1].rstrip(")"))

                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT cp.id, c.course_code, c.course_name, cp.is_required
                    FROM course_prerequisites cp
                    JOIN courses c ON cp.prerequisite_course_id = c.id
                    WHERE cp.course_id = ?
                    ORDER BY c.course_code
                """, (course_id,))

                prereqs = cursor.fetchall()
                conn.close()

                for prereq_id, code, name, is_req in prereqs:
                    req_status = "Required" if is_req else "Recommended"
                    display_text = f"{code} - {name} ({req_status})"
                    prereq_listbox.insert(tk.END, display_text)
                    prereq_data[display_text] = prereq_id

                if not prereqs:
                    prereq_listbox.insert(tk.END, "No prerequisites found")

            except Exception as e:
                messagebox.showerror(_("common.error"), f"Failed to load prerequisites: {e}")

        def remove_selected():
            selection = prereq_listbox.curselection()
            if not selection:
                messagebox.showwarning(_("course_management.messages.no_selection"), "Please select a prerequisite to remove")
                return

            selected_text = prereq_listbox.get(selection[0])
            if selected_text == "No prerequisites found":
                return

            prereq_id = prereq_data.get(selected_text)
            if not prereq_id:
                return

            if messagebox.askyesno(_("common.confirm"), f"Remove prerequisite:\n{selected_text}?"):
                try:
                    conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM course_prerequisites WHERE id = ?", (prereq_id,))
                    conn.commit()
                    conn.close()

                    messagebox.showinfo(_("common.success"), "Prerequisite removed successfully!")
                    self.update_status("Prerequisite removed")
                    load_prerequisites()

                except sqlite3.Error as e:
                    messagebox.showerror(_("common.error"), f"Failed to remove prerequisite: {e}")

        course_combo.bind('<<ComboboxSelected>>', load_prerequisites)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)

        ttk.Button(button_frame, text="Remove Selected", command=remove_selected).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)

        # Initial load
        load_courses()
