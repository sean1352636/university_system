from education_system.systems.university.interfaces.gui.academics.course_management_gui.recommendations._imports import (
    tk, ttk, messagebox, sqlite3, _, DEFAULT_DB_PATH, datetime,
)


class WaitlistsMixin:
    def add_to_waitlist_gui(self):
        """
        Add a student to a course waitlist.
        Opens a dialog to select full course and enter student ID.
        """
        dialog = tk.Toplevel(self.root)
        dialog.title("Add Student to Waitlist")
        dialog.geometry("550x350")
        dialog.transient(self.root)

        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Add Student to Course Waitlist",
                 font=('Arial', 12, 'bold')).pack(pady=(0, 10))

        # Course selection (full courses only)
        course_frame = ttk.LabelFrame(main_frame, text="Select Full Course", padding="10")
        course_frame.pack(fill=tk.X, pady=5)

        ttk.Label(course_frame, text="Course:").grid(row=0, column=0, sticky=tk.W, pady=5)
        course_var = tk.StringVar()
        course_combo = ttk.Combobox(course_frame, textvariable=course_var, state='readonly', width=45)
        course_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=5, padx=5)

        # Student ID
        student_frame = ttk.LabelFrame(main_frame, text="Student Information", padding="10")
        student_frame.pack(fill=tk.X, pady=5)

        ttk.Label(student_frame, text="Student ID:").grid(row=0, column=0, sticky=tk.W, pady=5)
        student_id_var = tk.StringVar()
        student_id_entry = ttk.Entry(student_frame, textvariable=student_id_var, width=30)
        student_id_entry.grid(row=0, column=1, sticky=tk.W, pady=5, padx=5)

        # Info label
        info_label = ttk.Label(main_frame, text="", foreground="blue", wraplength=500)
        info_label.pack(pady=10)

        def load_full_courses():
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT id, course_code, course_name, current_enrollment, max_enrollment
                    FROM courses
                    WHERE course_code IS NOT NULL
                      AND course_name IS NOT NULL
                      AND COALESCE(current_enrollment, 0) >= COALESCE(max_enrollment, 0)
                      AND LOWER(COALESCE(status, 'active')) = 'active'
                    ORDER BY course_code
                """)
                courses = cursor.fetchall()
                conn.close()

                if courses:
                    course_list = [f"{code} - {name} ({enr}/{max}) (ID: {id})"
                                 for id, code, name, enr, max in courses]
                    course_combo['values'] = course_list
                    info_label.config(text=f"Found {len(courses)} full course(s)")
                else:
                    course_combo['values'] = ["No full courses available"]
                    info_label.config(text="No full courses found")

            except sqlite3.Error as e:
                messagebox.showerror(_("common.database_error"), f"Failed to load courses: {e}")
                dialog.destroy()

        def add_student():
            if not course_var.get() or course_var.get() == "No full courses available":
                messagebox.showwarning(_("course_management.messages.no_selection"), "Please select a course")
                return

            if not student_id_var.get().strip():
                messagebox.showerror("Missing Data", "Please enter student ID")
                return

            try:
                course_id = int(course_var.get().split("ID: ")[1].rstrip(")"))
                student_id = student_id_var.get().strip()

                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
                try:
                    cursor = conn.cursor()

                    # Validate student exists in database
                    cursor.execute("SELECT student_id, first_name, last_name FROM students WHERE student_id = ?", (student_id,))
                    student_record = cursor.fetchone()

                    if not student_record:
                        messagebox.showerror("Invalid Student",
                                           f"Student ID '{student_id}' does not exist in the database.\n\n"
                                           f"Please enter a valid student ID.")
                finally:
                    conn.close()
                    return

                student_name = f"{student_record[1]} {student_record[2]}"

                # Check if already on waitlist
                cursor.execute("""
                    SELECT id FROM course_waitlist
                    WHERE course_id = ? AND student_id = ?
                """, (course_id, student_id))

                if cursor.fetchone():
                    messagebox.showerror("Duplicate", f"Student {student_name} ({student_id}) is already on the waitlist for this course")
                    conn.close()
                    return

                # Get next position
                cursor.execute("""
                    SELECT COALESCE(MAX(position), 0) + 1
                    FROM course_waitlist WHERE course_id = ?
                """, (course_id,))
                position = cursor.fetchone()[0]

                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                cursor.execute('''
                    INSERT INTO course_waitlist (course_id, student_id, position, added_at, status)
                    VALUES (?, ?, ?, ?, 'Waiting')
                ''', (course_id, student_id, position, timestamp))

                conn.commit()
                conn.close()

                messagebox.showinfo(_("common.success"),
                                  f"Student {student_name} ({student_id}) added to waitlist at position {position}")
                self.update_status(f"Added student {student_name} ({student_id}) to waitlist")
                dialog.destroy()

            except Exception as e:
                messagebox.showerror(_("common.error"), f"Failed to add to waitlist: {e}")

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)

        ttk.Button(button_frame, text="Add to Waitlist", command=add_student).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)

        load_full_courses()

    def view_waitlists_gui(self):
        """
        View waitlists for all courses or a specific course.
        Opens a dialog with waitlist information.
        """
        dialog = tk.Toplevel(self.root)
        dialog.title("View Course Waitlists")
        dialog.geometry("800x600")
        dialog.transient(self.root)

        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Course Waitlists",
                 font=('Arial', 12, 'bold')).pack(pady=(0, 10))

        # Filter frame
        filter_frame = ttk.Frame(main_frame)
        filter_frame.pack(fill=tk.X, pady=5)

        ttk.Label(filter_frame, text="Filter by Course:").pack(side=tk.LEFT, padx=5)
        course_var = tk.StringVar()
        course_combo = ttk.Combobox(filter_frame, textvariable=course_var, state='readonly', width=40)
        course_combo.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        # Treeview for waitlist
        tree_frame = ttk.Frame(main_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        columns = ('Course', 'Position', 'Student ID', 'Added Date', 'Status')
        tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=15)

        for col in columns:
            tree.heading(col, text=col)
            if col == 'Course':
                tree.column(col, width=200)
            elif col == 'Student ID':
                tree.column(col, width=120)
            else:
                tree.column(col, width=100)

        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

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

                course_list = ["-- All Courses --"] + [f"{code} - {name} (ID: {id})" for id, code, name in courses]
                course_combo['values'] = course_list
                course_combo.current(0)

            except sqlite3.Error as e:
                messagebox.showerror(_("common.database_error"), f"Failed to load courses: {e}")

        def load_waitlist(*args):
            # Clear existing items
            for item in tree.get_children():
                tree.delete(item)

            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
                cursor = conn.cursor()

                selected = course_var.get()

                if selected == "-- All Courses --" or not selected:
                    cursor.execute("""
                        SELECT c.course_code, c.course_name, w.position,
                               w.student_id, w.added_at, w.status
                        FROM course_waitlist w
                        JOIN courses c ON w.course_id = c.id
                        ORDER BY c.course_code, w.position
                    """)
                else:
                    course_id = int(selected.split("ID: ")[1].rstrip(")"))
                    cursor.execute("""
                        SELECT c.course_code, c.course_name, w.position,
                               w.student_id, w.added_at, w.status
                        FROM course_waitlist w
                        JOIN courses c ON w.course_id = c.id
                        WHERE w.course_id = ?
                        ORDER BY w.position
                    """, (course_id,))

                waitlist = cursor.fetchall()
                conn.close()

                for entry in waitlist:
                    code, name, position, student, added, status = entry
                    course = f"{code} - {name[:25]}"
                    added_date = added.split()[0] if added else "Unknown"

                    tree.insert('', tk.END, values=(
                        course, position, student, added_date, status
                    ))

                if not waitlist:
                    messagebox.showinfo(_("common.no_results"), "No waitlist entries found")

            except Exception as e:
                messagebox.showerror(_("common.error"), f"Failed to load waitlist: {e}")

        course_combo.bind('<<ComboboxSelected>>', load_waitlist)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)

        ttk.Button(button_frame, text="Refresh", command=load_waitlist).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)

        # Initial load
        load_courses()
        load_waitlist()

    def process_waitlist_gui(self):
        """
        Process waitlist and enroll students when spots become available.
        Opens a dialog to select course and process waitlist.
        """
        messagebox.showinfo("Process Waitlist",
                          "This feature would automatically enroll students from the waitlist\n"
                          "when spots become available in the course.\n\n"
                          "Implementation requires integration with enrollment system.")
