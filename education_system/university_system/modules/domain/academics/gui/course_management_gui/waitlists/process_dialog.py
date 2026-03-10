# ProcessWaitlistDialog – process waitlists and enroll students
from ._imports import _, messagebox, tk, ttk, sqlite3, DEFAULT_DB_PATH


class ProcessWaitlistDialog:
    def __init__(self, parent, auth):
        self.parent = parent
        self.auth = auth
        self.result = None

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Process Course Waitlists")
        self.dialog.geometry("700x500")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_waitlist_data()
        self.dialog.focus_set()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        ttk.Label(main_frame, text="Courses with Available Spots and Waitlists",
                 font=("Arial", 12, "bold")).pack(pady=10)

        # Course waitlist display
        columns = ("Course ID", "Code", "Name", "Available", "Waitlist Count")
        self.waitlist_tree = ttk.Treeview(main_frame, columns=columns, show="headings")

        for col in columns:
            self.waitlist_tree.heading(col, text=col)
            if col == "Course ID":
                self.waitlist_tree.column(col, width=80)
            elif col == "Code":
                self.waitlist_tree.column(col, width=80)
            elif col == "Name":
                self.waitlist_tree.column(col, width=250)
            else:
                self.waitlist_tree.column(col, width=100)

        self.waitlist_tree.pack(fill=tk.BOTH, expand=True, pady=5)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)

        ttk.Button(button_frame, text="Process Selected", command=self.process_selected).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Process All", command=self.process_all).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Refresh", command=self.load_waitlist_data).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)

    def load_waitlist_data(self):
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()

            cursor.execute("""
            SELECT c.id, c.course_code, c.course_name,
                   (COALESCE(c.max_enrollment, 0) - COALESCE(c.current_enrollment, 0)) as available_spots,
                   COUNT(w.id) as waitlist_count
            FROM courses c
            LEFT JOIN course_waitlist w ON c.id = w.course_id AND LOWER(w.status) = 'waiting'
            WHERE LOWER(COALESCE(c.status, 'active')) = 'active'
              AND COALESCE(c.current_enrollment, 0) < COALESCE(c.max_enrollment, 0)
            GROUP BY c.id, c.course_code, c.course_name, c.current_enrollment, c.max_enrollment
            HAVING waitlist_count > 0
            ORDER BY available_spots DESC, waitlist_count DESC
            """)

            courses = cursor.fetchall()

            for item in self.waitlist_tree.get_children():
                self.waitlist_tree.delete(item)

            for course in courses:
                self.waitlist_tree.insert("", tk.END, values=course)

            conn.close()
        except sqlite3.Error as e:
            messagebox.showerror(_("common.database_error"), f"Failed to load waitlist data: {e}")

    def process_selected(self):
        selection = self.waitlist_tree.selection()
        if not selection:
            messagebox.showwarning(_("course_management.messages.no_selection"), "Please select a course to process.")
            return

        course_data = self.waitlist_tree.item(selection[0])['values']
        course_id = course_data[0]

        if self.process_course_waitlist(course_id):
            self.load_waitlist_data()

    def process_all(self):
        if messagebox.askyesno(_("common.confirm"), "Process all waitlists? This will enroll students from waitlists where spots are available."):
            processed = 0
            for item in self.waitlist_tree.get_children():
                course_data = self.waitlist_tree.item(item)['values']
                course_id = course_data[0]
                if self.process_course_waitlist(course_id, show_messages=False):
                    processed += 1

            messagebox.showinfo("Complete", f"Processed waitlists for {processed} courses.")
            self.load_waitlist_data()

    def process_course_waitlist(self, course_id, show_messages=True):
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()

            # Get course info and available spots
            cursor.execute("""
            SELECT course_code, course_name,
                   current_enrollment, max_enrollment
            FROM courses WHERE id = ?
            """, (course_id,))

            course_info = cursor.fetchone()
            if not course_info:
                return False

            code, name, current_enrolled, max_enrolled = course_info
            available_spots = max_enrolled - current_enrolled

            if available_spots <= 0:
                if show_messages:
                    messagebox.showwarning("No Spots", f"No available spots in {code}")
                return False

            # Get waitlist students
            cursor.execute("""
            SELECT id, student_id FROM course_waitlist
            WHERE course_id = ? AND status = 'Waiting'
            ORDER BY position
            LIMIT ?
            """, (course_id, available_spots))

            waitlist_students = cursor.fetchall()

            if not waitlist_students:
                return False

            # Process each student
            enrolled_count = 0
            for waitlist_id, student_id in waitlist_students:
                # Update waitlist status
                cursor.execute("UPDATE course_waitlist SET status = 'Enrolled' WHERE id = ?", (waitlist_id,))
                enrolled_count += 1

                # Send enrollment confirmation email
                try:
                    cursor.execute(
                        "SELECT email_address, first_name FROM students WHERE student_id = ?",
                        (student_id,)
                    )
                    stu_row = cursor.fetchone()
                    if stu_row and stu_row[0]:
                        from education_system.university_system.infrastructure.email.template_utils import render_template
                        from education_system.university_system.infrastructure.email.email_service import send_email
                        try:
                            subj, body = render_template("course_waitlist_enrolled", {
                                "first_name": stu_row[1] or "Student",
                                "course_code": code or "",
                                "course_name": name or "",
                            })
                            if not subj or not body:
                                raise ValueError("Template returned empty subject/body")
                        except Exception:
                            subj = f"Enrollment Confirmed: {code} - {name}"
                            body = (
                                f"Dear {stu_row[1] or 'Student'},\n\n"
                                f"You have been enrolled in {code} - {name} from the waitlist.\n\n"
                                f"Please check your course schedule for class times and locations.\n\n"
                                f"Best regards,\nAcademic Administration"
                            )
                        send_email(stu_row[0], subj, body)
                except Exception as email_err:
                    print(f"Waitlist enrollment email failed for {student_id}: {email_err}")

            # Update course enrollment
            cursor.execute("""
            UPDATE courses SET current_enrollment = current_enrollment + ?
            WHERE id = ?
            """, (enrolled_count, course_id))

            # Update remaining waitlist positions
            cursor.execute("""
            UPDATE course_waitlist
            SET position = position - ?
            WHERE course_id = ? AND status = 'Waiting'
            """, (enrolled_count, course_id))

            conn.commit()
            conn.close()

            if show_messages:
                messagebox.showinfo(_("common.success"), f"Enrolled {enrolled_count} students from waitlist for {code}")

            return True

        except sqlite3.Error as e:
            if show_messages:
                messagebox.showerror(_("common.database_error"), f"Failed to process waitlist: {e}")
            return False
