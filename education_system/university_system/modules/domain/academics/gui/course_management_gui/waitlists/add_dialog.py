# AddToWaitlistDialog – add a student to a course waitlist
from education_system.university_system.core.sql_safety import escape_like
from education_system.university_system.modules.domain.academics.gui.course_management_gui.waitlists._imports import (
    _, datetime, messagebox, tk, ttk, Toplevel, sqlite3, DEFAULT_DB_PATH,
)


class AddToWaitlistDialog:
    def __init__(self, parent, auth):
        self.parent = parent; self.auth = auth
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Add to Course Waitlist")
        self.dialog.geometry("420x240")
        self.dialog.transient(parent); self.dialog.grab_set()
        self._ui()

    def _ui(self):
        frm = ttk.Frame(self.dialog); frm.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        ttk.Label(frm, text="Course:").grid(row=0, column=0, sticky=tk.W)
        self.course_combo = ttk.Combobox(frm, width=45); self.course_combo.grid(row=0, column=1, sticky=tk.W, padx=6, columnspan=2)
        ttk.Label(frm, text="Student ID:").grid(row=1, column=0, sticky=tk.W, pady=(8,0))
        self.student_var = tk.StringVar()
        ttk.Entry(frm, textvariable=self.student_var, width=20).grid(row=1, column=1, sticky=tk.W, padx=6, pady=(8,0))
        ttk.Button(frm, text="Lookup", command=self._lookup_student).grid(row=1, column=2, sticky=tk.W, padx=6, pady=(8,0))

        self._load_courses()
        btns = ttk.Frame(frm); btns.grid(row=3, column=0, columnspan=3, sticky=tk.EW, pady=12)
        ttk.Button(btns, text="Add", command=self._add).pack(side=tk.RIGHT, padx=6)
        ttk.Button(btns, text="Cancel", command=self.dialog.destroy).pack(side=tk.RIGHT)

    def _load_courses(self):
        from education_system.university_system.infrastructure.database.db import sqlite3
        self._course_id = {}
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH)); cur = conn.cursor()
            cur.execute(
                "SELECT id, course_code, course_name "
                "FROM courses "
                "WHERE course_code IS NOT NULL "
                "AND course_name IS NOT NULL "
                "AND LOWER(COALESCE(status, 'active')) = 'active' "
                "ORDER BY course_code"
            )
            rows = cur.fetchall(); conn.close()
            vals = [f"{r[1]} - {r[2]}" for r in rows]
            self._course_id = {f"{r[1]} - {r[2]}": r[0] for r in rows}
            self.course_combo['values'] = vals
        except sqlite3.Error as e:
            messagebox.showerror(_("common.database_error"), f"Failed to load courses: {e}")

    def _lookup_student(self):
        """Open student lookup dialog"""
        lookup_dialog = tk.Toplevel(self.dialog)
        lookup_dialog.title("Lookup Student")
        lookup_dialog.geometry("600x400")
        lookup_dialog.transient(self.dialog)
        lookup_dialog.grab_set()

        lookup_frame = ttk.Frame(lookup_dialog, padding=10)
        lookup_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(lookup_frame, text="Search for Student", font=('Arial', 12, 'bold')).pack(pady=(0, 10))

        # Search field
        search_frame = ttk.Frame(lookup_frame)
        search_frame.pack(fill=tk.X, pady=5)
        ttk.Label(search_frame, text="Search (ID, Name):").pack(side=tk.LEFT)
        search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=search_var, width=30)
        search_entry.pack(side=tk.LEFT, padx=5)

        # Student list
        columns = ('ID', 'Name', 'Email')
        tree = ttk.Treeview(lookup_frame, columns=columns, show='headings', height=12)
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=180)
        tree.pack(fill=tk.BOTH, expand=True, pady=5)

        # Scrollbar
        scrollbar = ttk.Scrollbar(lookup_frame, orient=tk.VERTICAL, command=tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        tree.configure(yscrollcommand=scrollbar.set)

        def search_students():
            """Search and display students"""
            for item in tree.get_children():
                tree.delete(item)

            search_text = search_var.get().strip()
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()

                if search_text:
                    cursor.execute("""
                        SELECT student_id, first_name || ' ' || last_name, email_address
                        FROM students
                        WHERE student_id LIKE ? OR first_name LIKE ? OR last_name LIKE ? OR email_address LIKE ?
                        ORDER BY student_id
                        LIMIT 100
                    """, (f"%{escape_like(search_text)}%", f"%{escape_like(search_text)}%", f"%{escape_like(search_text)}%", f"%{escape_like(search_text)}%"))
                else:
                    cursor.execute("""
                        SELECT student_id, first_name || ' ' || last_name, email_address
                        FROM students
                        ORDER BY student_id
                        LIMIT 100
                    """)

                students = cursor.fetchall()
                for student in students:
                    tree.insert('', tk.END, values=student)

                conn.close()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to search students: {str(e)}")

        def select_student():
            """Select the highlighted student"""
            selection = tree.selection()
            if selection:
                item = tree.item(selection[0])
                student_id = item['values'][0]
                self.student_var.set(student_id)
                lookup_dialog.destroy()
            else:
                messagebox.showwarning("No Selection", "Please select a student")

        ttk.Button(search_frame, text="Search", command=search_students).pack(side=tk.LEFT, padx=5)

        # Button frame
        btn_frame = ttk.Frame(lookup_frame)
        btn_frame.pack(fill=tk.X, pady=5)
        ttk.Button(btn_frame, text="Select", command=select_student).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=lookup_dialog.destroy).pack(side=tk.LEFT, padx=5)

        # Initial load
        search_students()

        # Bind double-click
        tree.bind('<Double-1>', lambda e: select_student())

    def _add(self):
        from education_system.university_system.infrastructure.database.db import sqlite3
        course_key = self.course_combo.get().strip()
        student_id = self.student_var.get().strip()
        if course_key not in self._course_id:
            messagebox.showwarning(_("common.validation"), "Select a course."); return
        if not student_id:
            messagebox.showwarning(_("common.validation"), "Enter a student ID."); return
        course_id = self._course_id[course_key]

        conn = None
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=10.0)
            conn.execute("PRAGMA busy_timeout = 10000")
            cur = conn.cursor()
            # ensure waitlist table
            cur.execute("""
            CREATE TABLE IF NOT EXISTS course_waitlist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                course_id INTEGER NOT NULL,
                student_id INTEGER NOT NULL,
                position INTEGER NOT NULL,
                added_at TEXT NOT NULL,
                status TEXT DEFAULT 'Waiting',
                FOREIGN KEY(course_id) REFERENCES courses(id),
                UNIQUE(course_id, student_id)
            )
            """)
            cur.execute("SELECT id FROM course_waitlist WHERE course_id = ? AND student_id = ?", (course_id, student_id))
            if cur.fetchone():
                messagebox.showwarning("Already on Waitlist", "This student is already on the waitlist for this course.", parent=self.dialog)
                conn.close()
                return
            cur.execute("SELECT COALESCE(MAX(position),0) + 1 FROM course_waitlist WHERE course_id = ?", (course_id,))
            pos = cur.fetchone()[0] or 1
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cur.execute("INSERT INTO course_waitlist (course_id, student_id, position, added_at) VALUES (?, ?, ?, ?)",
                        (course_id, student_id, pos, timestamp))
            conn.commit()

            # Send waitlist confirmation email
            try:
                cur.execute(
                    "SELECT email_address, first_name FROM students WHERE student_id = ?",
                    (student_id,)
                )
                stu_row = cur.fetchone()
                # Parse course_key "CODE - Name"
                parts = course_key.split(" - ", 1)
                c_code = parts[0] if parts else ""
                c_name = parts[1] if len(parts) > 1 else ""
                if stu_row and stu_row[0]:
                    from education_system.university_system.infrastructure.email.template_utils import render_template
                    from education_system.university_system.infrastructure.email.email_service import send_email
                    try:
                        subj, body = render_template("course_waitlist_added", {
                            "first_name": stu_row[1] or "Student",
                            "course_code": c_code,
                            "course_name": c_name,
                            "position": str(pos),
                            "added_at": timestamp,
                        })
                        if not subj or not body:
                            raise ValueError("Template returned empty subject/body")
                    except Exception:
                        subj = f"Waitlist Confirmation: {c_code} - {c_name}"
                        body = (
                            f"Dear {stu_row[1] or 'Student'},\n\n"
                            f"You have been added to the waitlist for {c_code} - {c_name}.\n\n"
                            f"Position: {pos}\n"
                            f"Date Added: {timestamp}\n\n"
                            f"You will be notified when a spot becomes available.\n\n"
                            f"Best regards,\nAcademic Administration"
                        )
                    send_email(stu_row[0], subj, body)
            except Exception as email_err:
                print(f"Waitlist email notification failed: {email_err}")

            messagebox.showinfo(_("common.success"), f"Added student {student_id} to waitlist (position {pos}).")
            self.dialog.destroy()
        except sqlite3.Error as e:
            messagebox.showerror(_("common.database_error"), f"Failed to add to waitlist: {e}")
        finally:
            if conn:
                conn.close()
