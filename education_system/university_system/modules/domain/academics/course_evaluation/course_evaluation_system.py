"""
University Course Evaluation System
A GUI application for students to evaluate courses and instructors.
Built with Tkinter and SQLite for data persistence.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
from datetime import datetime


# ---------- Database Setup ----------
class Database:
    def __init__(self, db_name="course_evaluations.db"):
        self.conn = sqlite3.connect(db_name)
        self.cursor = self.conn.cursor()
        self.create_tables()
        self.seed_data()

    def create_tables(self):
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS courses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                instructor TEXT NOT NULL,
                department TEXT NOT NULL
            )
        """)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS evaluations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                course_id INTEGER NOT NULL,
                student_id TEXT NOT NULL,
                teaching_quality INTEGER NOT NULL,
                course_content INTEGER NOT NULL,
                workload INTEGER NOT NULL,
                communication INTEGER NOT NULL,
                overall INTEGER NOT NULL,
                comments TEXT,
                submitted_at TEXT NOT NULL,
                FOREIGN KEY (course_id) REFERENCES courses(id)
            )
        """)
        self.conn.commit()

    def seed_data(self):
        self.cursor.execute("SELECT COUNT(*) FROM courses")
        if self.cursor.fetchone()[0] == 0:
            sample = [
                ("CS101", "Introduction to Computer Science", "Dr. Sarah Chen", "Computer Science"),
                ("CS202", "Data Structures and Algorithms", "Prof. Michael Rodriguez", "Computer Science"),
                ("MATH201", "Linear Algebra", "Dr. Emily Watson", "Mathematics"),
                ("PHYS101", "Classical Mechanics", "Prof. David Kim", "Physics"),
                ("ENG105", "Academic Writing", "Dr. Jessica Brown", "English"),
                ("BUS220", "Principles of Management", "Prof. Robert Taylor", "Business"),
            ]
            self.cursor.executemany(
                "INSERT INTO courses (code, name, instructor, department) VALUES (?, ?, ?, ?)",
                sample,
            )
            self.conn.commit()

    def get_courses(self):
        self.cursor.execute("SELECT id, code, name, instructor, department FROM courses ORDER BY code")
        return self.cursor.fetchall()

    def get_course_by_id(self, course_id):
        self.cursor.execute("SELECT id, code, name, instructor, department FROM courses WHERE id=?", (course_id,))
        return self.cursor.fetchone()

    def submit_evaluation(self, data):
        self.cursor.execute("""
            INSERT INTO evaluations
            (course_id, student_id, teaching_quality, course_content,
             workload, communication, overall, comments, submitted_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, data)
        self.conn.commit()

    def get_evaluation_stats(self, course_id):
        self.cursor.execute("""
            SELECT COUNT(*),
                   AVG(teaching_quality), AVG(course_content),
                   AVG(workload), AVG(communication), AVG(overall)
            FROM evaluations WHERE course_id=?
        """, (course_id,))
        return self.cursor.fetchone()

    def get_evaluations(self, course_id):
        self.cursor.execute("""
            SELECT student_id, teaching_quality, course_content, workload,
                   communication, overall, comments, submitted_at
            FROM evaluations WHERE course_id=? ORDER BY submitted_at DESC
        """, (course_id,))
        return self.cursor.fetchall()

    def add_course(self, code, name, instructor, department):
        try:
            self.cursor.execute(
                "INSERT INTO courses (code, name, instructor, department) VALUES (?, ?, ?, ?)",
                (code, name, instructor, department),
            )
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def close(self):
        self.conn.close()


# ---------- Main Application ----------
class CourseEvaluationApp:
    def __init__(self, root):
        self.root = root
        self.root.title("University Course Evaluation System")
        self.root.geometry("900x650")
        self.root.configure(bg="#f0f4f8")

        self.db = Database()
        self.current_ratings = {}

        self.setup_styles()
        self.create_header()
        self.create_notebook()

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TNotebook", background="#f0f4f8", borderwidth=0)
        style.configure("TNotebook.Tab", padding=[20, 10], font=("Arial", 10, "bold"))
        style.configure("TFrame", background="#f0f4f8")
        style.configure("TLabel", background="#f0f4f8", font=("Arial", 10))
        style.configure("Header.TLabel", font=("Arial", 11, "bold"), foreground="#1a365d")
        style.configure("TButton", font=("Arial", 10, "bold"), padding=8)
        style.configure("Treeview", font=("Arial", 9), rowheight=25)
        style.configure("Treeview.Heading", font=("Arial", 10, "bold"))

    def create_header(self):
        header = tk.Frame(self.root, bg="#1a365d", height=70)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(
            header, text="🎓 University Course Evaluation System",
            font=("Arial", 18, "bold"), bg="#1a365d", fg="white"
        ).pack(pady=18)

    def create_notebook(self):
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=15, pady=15)

        self.eval_frame = ttk.Frame(self.notebook)
        self.results_frame = ttk.Frame(self.notebook)
        self.admin_frame = ttk.Frame(self.notebook)

        self.notebook.add(self.eval_frame, text="  Submit Evaluation  ")
        self.notebook.add(self.results_frame, text="  View Results  ")
        self.notebook.add(self.admin_frame, text="  Manage Courses  ")

        self.build_eval_tab()
        self.build_results_tab()
        self.build_admin_tab()

    # ---------- Evaluation Tab ----------
    def build_eval_tab(self):
        container = ttk.Frame(self.eval_frame)
        container.pack(fill="both", expand=True, padx=20, pady=20)

        # Student ID
        ttk.Label(container, text="Student ID:", style="Header.TLabel").grid(row=0, column=0, sticky="w", pady=5)
        self.student_id_entry = ttk.Entry(container, width=30, font=("Arial", 10))
        self.student_id_entry.grid(row=0, column=1, sticky="w", pady=5, padx=10)

        # Course selection
        ttk.Label(container, text="Select Course:", style="Header.TLabel").grid(row=1, column=0, sticky="w", pady=5)
        self.course_combo = ttk.Combobox(container, width=50, font=("Arial", 10), state="readonly")
        self.course_combo.grid(row=1, column=1, sticky="w", pady=5, padx=10)
        self.refresh_course_combo()

        # Rating section
        ratings_frame = ttk.LabelFrame(container, text=" Rate the Course (1 = Poor, 5 = Excellent) ", padding=15)
        ratings_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=15)

        self.rating_vars = {}
        categories = [
            ("teaching_quality", "Teaching Quality"),
            ("course_content", "Course Content"),
            ("workload", "Workload Balance"),
            ("communication", "Instructor Communication"),
            ("overall", "Overall Satisfaction"),
        ]
        for i, (key, label) in enumerate(categories):
            ttk.Label(ratings_frame, text=label + ":").grid(row=i, column=0, sticky="w", pady=6)
            var = tk.IntVar(value=3)
            self.rating_vars[key] = var
            scale_frame = ttk.Frame(ratings_frame)
            scale_frame.grid(row=i, column=1, sticky="w", padx=20)
            for val in range(1, 6):
                ttk.Radiobutton(scale_frame, text=str(val), variable=var, value=val).pack(side="left", padx=5)

        # Comments
        ttk.Label(container, text="Comments (optional):", style="Header.TLabel").grid(row=3, column=0, sticky="nw", pady=5)
        self.comments_text = tk.Text(container, width=55, height=5, font=("Arial", 10), wrap="word")
        self.comments_text.grid(row=3, column=1, sticky="w", pady=5, padx=10)

        # Buttons
        btn_frame = ttk.Frame(container)
        btn_frame.grid(row=4, column=0, columnspan=2, pady=20)
        submit_btn = tk.Button(
            btn_frame, text="Submit Evaluation", command=self.submit_evaluation,
            bg="#2c7a3e", fg="white", font=("Arial", 11, "bold"),
            padx=25, pady=8, cursor="hand2", relief="flat"
        )
        submit_btn.pack(side="left", padx=10)

        clear_btn = tk.Button(
            btn_frame, text="Clear Form", command=self.clear_form,
            bg="#718096", fg="white", font=("Arial", 11, "bold"),
            padx=25, pady=8, cursor="hand2", relief="flat"
        )
        clear_btn.pack(side="left", padx=10)

    def refresh_course_combo(self):
        courses = self.db.get_courses()
        self.course_map = {f"{c[1]} - {c[2]} ({c[3]})": c[0] for c in courses}
        self.course_combo["values"] = list(self.course_map.keys())
        if courses:
            self.course_combo.current(0)

    def submit_evaluation(self):
        student_id = self.student_id_entry.get().strip()
        course_selection = self.course_combo.get()

        if not student_id:
            messagebox.showwarning("Missing Info", "Please enter your Student ID.")
            return
        if not course_selection:
            messagebox.showwarning("Missing Info", "Please select a course.")
            return

        course_id = self.course_map[course_selection]
        comments = self.comments_text.get("1.0", "end-1c").strip()

        data = (
            course_id, student_id,
            self.rating_vars["teaching_quality"].get(),
            self.rating_vars["course_content"].get(),
            self.rating_vars["workload"].get(),
            self.rating_vars["communication"].get(),
            self.rating_vars["overall"].get(),
            comments,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )
        self.db.submit_evaluation(data)
        messagebox.showinfo("Success", "Thank you! Your evaluation has been submitted.")
        self.clear_form()
        self.refresh_results()

    def clear_form(self):
        self.student_id_entry.delete(0, "end")
        self.comments_text.delete("1.0", "end")
        for var in self.rating_vars.values():
            var.set(3)

    # ---------- Results Tab ----------
    def build_results_tab(self):
        container = ttk.Frame(self.results_frame)
        container.pack(fill="both", expand=True, padx=20, pady=20)

        top = ttk.Frame(container)
        top.pack(fill="x", pady=5)
        ttk.Label(top, text="Select Course:", style="Header.TLabel").pack(side="left")
        self.results_combo = ttk.Combobox(top, width=50, font=("Arial", 10), state="readonly")
        self.results_combo.pack(side="left", padx=10)
        self.results_combo.bind("<<ComboboxSelected>>", lambda e: self.show_course_results())
        ttk.Button(top, text="Refresh", command=self.refresh_results).pack(side="left", padx=5)

        # Stats display
        self.stats_frame = ttk.LabelFrame(container, text=" Statistics ", padding=15)
        self.stats_frame.pack(fill="x", pady=10)
        self.stats_label = ttk.Label(self.stats_frame, text="Select a course to view statistics.", font=("Arial", 10))
        self.stats_label.pack(anchor="w")

        # Evaluations list
        list_frame = ttk.LabelFrame(container, text=" Individual Evaluations ", padding=10)
        list_frame.pack(fill="both", expand=True, pady=5)

        columns = ("student", "teaching", "content", "workload", "comm", "overall", "date")
        self.tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=10)
        headings = [
            ("student", "Student ID", 100),
            ("teaching", "Teaching", 80),
            ("content", "Content", 80),
            ("workload", "Workload", 80),
            ("comm", "Communication", 110),
            ("overall", "Overall", 70),
            ("date", "Date", 140),
        ]
        for col, label, width in headings:
            self.tree.heading(col, text=label)
            self.tree.column(col, width=width, anchor="center")

        scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", self.show_comment)

        # Comment display
        self.comment_label = ttk.Label(container, text="Click a row to view comments.", font=("Arial", 9, "italic"), wraplength=800)
        self.comment_label.pack(fill="x", pady=5)

        self.refresh_results()

    def refresh_results(self):
        courses = self.db.get_courses()
        self.results_map = {f"{c[1]} - {c[2]}": c[0] for c in courses}
        self.results_combo["values"] = list(self.results_map.keys())
        if courses:
            if not self.results_combo.get():
                self.results_combo.current(0)
            self.show_course_results()

    def show_course_results(self):
        selection = self.results_combo.get()
        if not selection:
            return
        course_id = self.results_map[selection]

        stats = self.db.get_evaluation_stats(course_id)
        count = stats[0]
        if count == 0:
            self.stats_label.config(text="No evaluations submitted yet for this course.")
        else:
            text = (
                f"Total Evaluations: {count}\n"
                f"Teaching Quality: {stats[1]:.2f} / 5.0\n"
                f"Course Content: {stats[2]:.2f} / 5.0\n"
                f"Workload Balance: {stats[3]:.2f} / 5.0\n"
                f"Communication: {stats[4]:.2f} / 5.0\n"
                f"Overall Satisfaction: {stats[5]:.2f} / 5.0"
            )
            self.stats_label.config(text=text)

        for item in self.tree.get_children():
            self.tree.delete(item)

        self.evaluations_cache = self.db.get_evaluations(course_id)
        for ev in self.evaluations_cache:
            self.tree.insert("", "end", values=(ev[0], ev[1], ev[2], ev[3], ev[4], ev[5], ev[7]))

    def show_comment(self, event):
        selection = self.tree.selection()
        if not selection:
            return
        index = self.tree.index(selection[0])
        if index < len(self.evaluations_cache):
            comment = self.evaluations_cache[index][6]
            if comment:
                self.comment_label.config(text=f"💬 Comment: {comment}")
            else:
                self.comment_label.config(text="💬 No comment provided.")

    # ---------- Admin Tab ----------
    def build_admin_tab(self):
        container = ttk.Frame(self.admin_frame)
        container.pack(fill="both", expand=True, padx=20, pady=20)

        # Add course form
        form = ttk.LabelFrame(container, text=" Add New Course ", padding=15)
        form.pack(fill="x", pady=5)

        fields = [("Course Code:", "code"), ("Course Name:", "name"),
                  ("Instructor:", "instructor"), ("Department:", "department")]
        self.admin_entries = {}
        for i, (label, key) in enumerate(fields):
            ttk.Label(form, text=label).grid(row=i, column=0, sticky="w", pady=5)
            entry = ttk.Entry(form, width=45, font=("Arial", 10))
            entry.grid(row=i, column=1, sticky="w", pady=5, padx=10)
            self.admin_entries[key] = entry

        tk.Button(
            form, text="Add Course", command=self.add_course,
            bg="#1a365d", fg="white", font=("Arial", 10, "bold"),
            padx=20, pady=6, cursor="hand2", relief="flat"
        ).grid(row=4, column=1, sticky="w", pady=10, padx=10)

        # Existing courses list
        list_frame = ttk.LabelFrame(container, text=" Existing Courses ", padding=10)
        list_frame.pack(fill="both", expand=True, pady=10)

        columns = ("code", "name", "instructor", "department")
        self.admin_tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=10)
        for col, label, width in [("code", "Code", 100), ("name", "Course Name", 280),
                                    ("instructor", "Instructor", 200), ("department", "Department", 180)]:
            self.admin_tree.heading(col, text=label)
            self.admin_tree.column(col, width=width)

        scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.admin_tree.yview)
        self.admin_tree.configure(yscrollcommand=scroll.set)
        self.admin_tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        self.refresh_admin_list()

    def add_course(self):
        code = self.admin_entries["code"].get().strip().upper()
        name = self.admin_entries["name"].get().strip()
        instructor = self.admin_entries["instructor"].get().strip()
        department = self.admin_entries["department"].get().strip()

        if not all([code, name, instructor, department]):
            messagebox.showwarning("Missing Info", "Please fill in all fields.")
            return

        if self.db.add_course(code, name, instructor, department):
            messagebox.showinfo("Success", f"Course {code} added successfully.")
            for entry in self.admin_entries.values():
                entry.delete(0, "end")
            self.refresh_admin_list()
            self.refresh_course_combo()
            self.refresh_results()
        else:
            messagebox.showerror("Error", f"Course code '{code}' already exists.")

    def refresh_admin_list(self):
        for item in self.admin_tree.get_children():
            self.admin_tree.delete(item)
        for course in self.db.get_courses():
            self.admin_tree.insert("", "end", values=(course[1], course[2], course[3], course[4]))

    def on_close(self):
        self.db.close()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = CourseEvaluationApp(root)
    root.mainloop()
