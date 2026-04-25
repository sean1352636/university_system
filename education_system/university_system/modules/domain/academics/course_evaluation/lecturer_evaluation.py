"""
University Lecturer/Instructor Evaluation System
A GUI application for students to evaluate lecturers and for administrators
to view aggregated evaluation reports.

Built with Tkinter and SQLite3 (both in Python standard library).
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import sqlite3
import hashlib
from datetime import datetime
import os


# ---------------------------------------------------------------------------
# DATABASE LAYER
# ---------------------------------------------------------------------------
class Database:
    """Handles all database operations for the evaluation system."""

    def __init__(self, db_name="lecturer_evaluation.db"):
        self.db_name = db_name
        self.conn = sqlite3.connect(db_name)
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.create_tables()
        self.seed_data()

    def create_tables(self):
        cur = self.conn.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id     INTEGER PRIMARY KEY AUTOINCREMENT,
                username    TEXT UNIQUE NOT NULL,
                password    TEXT NOT NULL,
                full_name   TEXT NOT NULL,
                role        TEXT NOT NULL CHECK(role IN ('student','admin')),
                student_id  TEXT UNIQUE
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS lecturers (
                lecturer_id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name   TEXT NOT NULL,
                department  TEXT NOT NULL,
                email       TEXT,
                title       TEXT
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS courses (
                course_id   INTEGER PRIMARY KEY AUTOINCREMENT,
                course_code TEXT UNIQUE NOT NULL,
                course_name TEXT NOT NULL,
                lecturer_id INTEGER NOT NULL,
                semester    TEXT NOT NULL,
                FOREIGN KEY (lecturer_id) REFERENCES lecturers(lecturer_id)
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS evaluations (
                evaluation_id     INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id        INTEGER NOT NULL,
                course_id         INTEGER NOT NULL,
                lecturer_id       INTEGER NOT NULL,
                knowledge         INTEGER NOT NULL,
                communication     INTEGER NOT NULL,
                preparation       INTEGER NOT NULL,
                engagement        INTEGER NOT NULL,
                fairness          INTEGER NOT NULL,
                availability      INTEGER NOT NULL,
                overall           INTEGER NOT NULL,
                comments          TEXT,
                submitted_at      TEXT NOT NULL,
                FOREIGN KEY (student_id)  REFERENCES users(user_id),
                FOREIGN KEY (course_id)   REFERENCES courses(course_id),
                FOREIGN KEY (lecturer_id) REFERENCES lecturers(lecturer_id),
                UNIQUE(student_id, course_id)
            )
        """)

        self.conn.commit()

    def seed_data(self):
        """Insert sample data only if tables are empty."""
        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(*) FROM users")
        if cur.fetchone()[0] > 0:
            return

        # Default accounts
        users = [
            ("admin",    hash_pw("admin123"),    "System Administrator", "admin",   None),
            ("student1", hash_pw("student123"),  "Alice Johnson",        "student", "S1001"),
            ("student2", hash_pw("student123"),  "Bob Williams",         "student", "S1002"),
            ("student3", hash_pw("student123"),  "Carol Davis",          "student", "S1003"),
        ]
        cur.executemany(
            "INSERT INTO users (username, password, full_name, role, student_id) VALUES (?,?,?,?,?)",
            users
        )

        lecturers = [
            ("Dr. Margaret Thompson", "Computer Science",    "m.thompson@uni.edu", "Senior Lecturer"),
            ("Prof. David Chen",      "Mathematics",         "d.chen@uni.edu",     "Professor"),
            ("Dr. Sarah O'Connor",    "Physics",             "s.oconnor@uni.edu",  "Lecturer"),
            ("Dr. James Ferguson",    "Computer Science",    "j.ferguson@uni.edu", "Associate Professor"),
            ("Prof. Linda Patel",     "Business Studies",    "l.patel@uni.edu",    "Professor"),
        ]
        cur.executemany(
            "INSERT INTO lecturers (full_name, department, email, title) VALUES (?,?,?,?)",
            lecturers
        )

        courses = [
            ("CS101", "Introduction to Programming",  1, "2026 Spring"),
            ("CS201", "Data Structures",              1, "2026 Spring"),
            ("MA201", "Linear Algebra",               2, "2026 Spring"),
            ("MA301", "Advanced Calculus",            2, "2026 Spring"),
            ("PH101", "Classical Mechanics",          3, "2026 Spring"),
            ("CS301", "Database Systems",             4, "2026 Spring"),
            ("CS401", "Software Engineering",         4, "2026 Spring"),
            ("BS201", "Principles of Management",     5, "2026 Spring"),
        ]
        cur.executemany(
            "INSERT INTO courses (course_code, course_name, lecturer_id, semester) VALUES (?,?,?,?)",
            courses
        )

        self.conn.commit()

    # -- auth ---------------------------------------------------------------
    def authenticate(self, username, password):
        cur = self.conn.cursor()
        cur.execute(
            "SELECT user_id, full_name, role FROM users WHERE username=? AND password=?",
            (username, hash_pw(password))
        )
        return cur.fetchone()

    def register_student(self, username, password, full_name, student_id):
        try:
            cur = self.conn.cursor()
            cur.execute(
                "INSERT INTO users (username, password, full_name, role, student_id) VALUES (?,?,?,?,?)",
                (username, hash_pw(password), full_name, "student", student_id)
            )
            self.conn.commit()
            return True, "Registration successful."
        except sqlite3.IntegrityError as e:
            return False, f"Registration failed: {e}"

    # -- reads --------------------------------------------------------------
    def get_courses(self):
        cur = self.conn.cursor()
        cur.execute("""
            SELECT c.course_id, c.course_code, c.course_name,
                   l.full_name, l.department, c.semester, l.lecturer_id
            FROM courses c
            JOIN lecturers l ON c.lecturer_id = l.lecturer_id
            ORDER BY c.course_code
        """)
        return cur.fetchall()

    def get_lecturers(self):
        cur = self.conn.cursor()
        cur.execute("SELECT lecturer_id, full_name, department, email, title FROM lecturers ORDER BY full_name")
        return cur.fetchall()

    def has_evaluated(self, student_id, course_id):
        cur = self.conn.cursor()
        cur.execute(
            "SELECT 1 FROM evaluations WHERE student_id=? AND course_id=?",
            (student_id, course_id)
        )
        return cur.fetchone() is not None

    def submit_evaluation(self, data):
        try:
            cur = self.conn.cursor()
            cur.execute("""
                INSERT INTO evaluations
                    (student_id, course_id, lecturer_id,
                     knowledge, communication, preparation, engagement,
                     fairness, availability, overall, comments, submitted_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """, data)
            self.conn.commit()
            return True, "Evaluation submitted successfully."
        except sqlite3.IntegrityError:
            return False, "You have already evaluated this course."

    def get_lecturer_report(self, lecturer_id):
        cur = self.conn.cursor()
        cur.execute("""
            SELECT COUNT(*),
                   AVG(knowledge), AVG(communication), AVG(preparation),
                   AVG(engagement), AVG(fairness),     AVG(availability),
                   AVG(overall)
            FROM evaluations
            WHERE lecturer_id = ?
        """, (lecturer_id,))
        return cur.fetchone()

    def get_lecturer_comments(self, lecturer_id):
        cur = self.conn.cursor()
        cur.execute("""
            SELECT c.course_code, e.comments, e.submitted_at
            FROM evaluations e
            JOIN courses c ON e.course_id = c.course_id
            WHERE e.lecturer_id = ? AND e.comments IS NOT NULL AND TRIM(e.comments) <> ''
            ORDER BY e.submitted_at DESC
        """, (lecturer_id,))
        return cur.fetchall()

    def get_all_lecturer_summaries(self):
        cur = self.conn.cursor()
        cur.execute("""
            SELECT l.lecturer_id, l.full_name, l.department, l.title,
                   COUNT(e.evaluation_id), AVG(e.overall)
            FROM lecturers l
            LEFT JOIN evaluations e ON l.lecturer_id = e.lecturer_id
            GROUP BY l.lecturer_id
            ORDER BY l.full_name
        """)
        return cur.fetchall()

    def add_lecturer(self, name, dept, email, title):
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO lecturers (full_name, department, email, title) VALUES (?,?,?,?)",
            (name, dept, email, title)
        )
        self.conn.commit()

    def add_course(self, code, name, lecturer_id, semester):
        try:
            cur = self.conn.cursor()
            cur.execute(
                "INSERT INTO courses (course_code, course_name, lecturer_id, semester) VALUES (?,?,?,?)",
                (code, name, lecturer_id, semester)
            )
            self.conn.commit()
            return True, "Course added."
        except sqlite3.IntegrityError:
            return False, "A course with that code already exists."

    def close(self):
        self.conn.close()


def hash_pw(password: str) -> str:
    """Hash passwords with SHA-256 before storing / comparing."""
    return hashlib.sha256(password.encode()).hexdigest()


# ---------------------------------------------------------------------------
# UI THEME
# ---------------------------------------------------------------------------
class Theme:
    PRIMARY     = "#1e3a5f"   # deep navy
    SECONDARY   = "#2d6a9f"   # mid blue
    ACCENT      = "#c9a961"   # academic gold
    SUCCESS     = "#2d8659"
    DANGER      = "#b84242"
    BG          = "#f4f1ea"   # warm off-white
    CARD        = "#ffffff"
    TEXT        = "#1a1a1a"
    TEXT_MUTED  = "#666666"
    BORDER      = "#d0cabf"

    FONT_TITLE   = ("Georgia", 22, "bold")
    FONT_HEADING = ("Georgia", 14, "bold")
    FONT_BODY    = ("Segoe UI", 10)
    FONT_BOLD    = ("Segoe UI", 10, "bold")
    FONT_SMALL   = ("Segoe UI", 9)


# ---------------------------------------------------------------------------
# LOGIN WINDOW
# ---------------------------------------------------------------------------
class LoginWindow:
    def __init__(self, root, db, on_success):
        self.root = root
        self.db = db
        self.on_success = on_success

        self.root.title("University Lecturer Evaluation System")
        self.root.geometry("500x620")
        self.root.configure(bg=Theme.BG)
        self.root.resizable(False, False)

        self.build_ui()

    def build_ui(self):
        # Header band
        header = tk.Frame(self.root, bg=Theme.PRIMARY, height=140)
        header.pack(fill="x")
        header.pack_propagate(False)

        tk.Label(header, text="🎓", bg=Theme.PRIMARY, fg=Theme.ACCENT,
                 font=("Segoe UI Emoji", 40)).pack(pady=(20, 0))
        tk.Label(header, text="Lecturer Evaluation System",
                 bg=Theme.PRIMARY, fg="white",
                 font=Theme.FONT_TITLE).pack()
        tk.Label(header, text="University Teaching Quality Portal",
                 bg=Theme.PRIMARY, fg=Theme.ACCENT,
                 font=Theme.FONT_SMALL).pack()

        # Card
        card = tk.Frame(self.root, bg=Theme.CARD,
                        highlightbackground=Theme.BORDER, highlightthickness=1)
        card.pack(padx=40, pady=30, fill="both", expand=True)

        tk.Label(card, text="Sign In", bg=Theme.CARD, fg=Theme.TEXT,
                 font=Theme.FONT_HEADING).pack(pady=(25, 20))

        # Username
        tk.Label(card, text="Username", bg=Theme.CARD, fg=Theme.TEXT,
                 font=Theme.FONT_BOLD).pack(anchor="w", padx=40)
        self.username_entry = tk.Entry(card, font=Theme.FONT_BODY,
                                       bg="white", relief="solid", bd=1)
        self.username_entry.pack(fill="x", padx=40, pady=(5, 15), ipady=6)

        # Password
        tk.Label(card, text="Password", bg=Theme.CARD, fg=Theme.TEXT,
                 font=Theme.FONT_BOLD).pack(anchor="w", padx=40)
        self.password_entry = tk.Entry(card, font=Theme.FONT_BODY,
                                       bg="white", relief="solid", bd=1, show="●")
        self.password_entry.pack(fill="x", padx=40, pady=(5, 20), ipady=6)
        self.password_entry.bind("<Return>", lambda e: self.login())

        # Buttons
        tk.Button(card, text="Login", bg=Theme.PRIMARY, fg="white",
                  font=Theme.FONT_BOLD, relief="flat", cursor="hand2",
                  activebackground=Theme.SECONDARY, activeforeground="white",
                  command=self.login).pack(fill="x", padx=40, ipady=9)

        tk.Button(card, text="Register New Student", bg=Theme.CARD, fg=Theme.SECONDARY,
                  font=Theme.FONT_BODY, relief="flat", cursor="hand2",
                  activebackground=Theme.CARD, activeforeground=Theme.PRIMARY,
                  command=self.open_register).pack(pady=(12, 0))

        # Demo hint
        hint = tk.Frame(card, bg="#f7f3e8",
                        highlightbackground=Theme.ACCENT, highlightthickness=1)
        hint.pack(fill="x", padx=40, pady=(20, 25))
        tk.Label(hint, text="Demo Accounts", bg="#f7f3e8", fg=Theme.PRIMARY,
                 font=Theme.FONT_BOLD).pack(pady=(8, 0))
        tk.Label(hint,
                 text="Admin:    admin / admin123\nStudent:  student1 / student123",
                 bg="#f7f3e8", fg=Theme.TEXT_MUTED,
                 font=Theme.FONT_SMALL, justify="left").pack(pady=(2, 8))

        self.username_entry.focus()

    def login(self):
        u = self.username_entry.get().strip()
        p = self.password_entry.get().strip()
        if not u or not p:
            messagebox.showwarning("Missing Information", "Please enter both username and password.")
            return
        user = self.db.authenticate(u, p)
        if user:
            self.on_success(user)
        else:
            messagebox.showerror("Login Failed", "Invalid username or password.")
            self.password_entry.delete(0, "end")

    def open_register(self):
        RegisterWindow(self.root, self.db)


# ---------------------------------------------------------------------------
# REGISTRATION WINDOW
# ---------------------------------------------------------------------------
class RegisterWindow:
    def __init__(self, parent, db):
        self.db = db
        self.win = tk.Toplevel(parent)
        self.win.title("Student Registration")
        self.win.geometry("450x480")
        self.win.configure(bg=Theme.BG)
        self.win.resizable(False, False)
        self.win.transient(parent)
        self.win.grab_set()

        tk.Label(self.win, text="Student Registration", bg=Theme.BG, fg=Theme.PRIMARY,
                 font=Theme.FONT_HEADING).pack(pady=(25, 20))

        self.fields = {}
        for label in ("Full Name", "Student ID", "Username", "Password"):
            tk.Label(self.win, text=label, bg=Theme.BG, fg=Theme.TEXT,
                     font=Theme.FONT_BOLD).pack(anchor="w", padx=50)
            show = "●" if label == "Password" else ""
            entry = tk.Entry(self.win, font=Theme.FONT_BODY, bg="white",
                             relief="solid", bd=1, show=show)
            entry.pack(fill="x", padx=50, pady=(4, 12), ipady=5)
            self.fields[label] = entry

        tk.Button(self.win, text="Create Account", bg=Theme.PRIMARY, fg="white",
                  font=Theme.FONT_BOLD, relief="flat", cursor="hand2",
                  activebackground=Theme.SECONDARY, activeforeground="white",
                  command=self.register).pack(fill="x", padx=50, pady=(15, 5), ipady=8)

        tk.Button(self.win, text="Cancel", bg=Theme.BG, fg=Theme.TEXT_MUTED,
                  font=Theme.FONT_BODY, relief="flat", cursor="hand2",
                  command=self.win.destroy).pack(pady=5)

    def register(self):
        name    = self.fields["Full Name"].get().strip()
        sid     = self.fields["Student ID"].get().strip()
        uname   = self.fields["Username"].get().strip()
        pw      = self.fields["Password"].get().strip()

        if not all([name, sid, uname, pw]):
            messagebox.showwarning("Missing Information", "All fields are required.")
            return
        if len(pw) < 6:
            messagebox.showwarning("Weak Password", "Password must be at least 6 characters.")
            return

        ok, msg = self.db.register_student(uname, pw, name, sid)
        if ok:
            messagebox.showinfo("Success", msg)
            self.win.destroy()
        else:
            messagebox.showerror("Error", msg)


# ---------------------------------------------------------------------------
# STUDENT DASHBOARD
# ---------------------------------------------------------------------------
class StudentDashboard:
    def __init__(self, root, db, user, on_logout):
        self.root = root
        self.db = db
        self.user_id, self.full_name, self.role = user
        self.on_logout = on_logout

        for w in root.winfo_children():
            w.destroy()

        root.title(f"Student Portal - {self.full_name}")
        root.geometry("1000x680")
        root.configure(bg=Theme.BG)
        root.resizable(True, True)

        self.build_ui()
        self.load_courses()

    def build_ui(self):
        # Header
        header = tk.Frame(self.root, bg=Theme.PRIMARY, height=70)
        header.pack(fill="x")
        header.pack_propagate(False)

        tk.Label(header, text="🎓  Student Portal", bg=Theme.PRIMARY, fg="white",
                 font=Theme.FONT_HEADING).pack(side="left", padx=25, pady=18)

        right = tk.Frame(header, bg=Theme.PRIMARY)
        right.pack(side="right", padx=25, pady=15)
        tk.Label(right, text=f"👤  {self.full_name}", bg=Theme.PRIMARY, fg="white",
                 font=Theme.FONT_BODY).pack(side="left", padx=(0, 15))
        tk.Button(right, text="Logout", bg=Theme.DANGER, fg="white",
                  font=Theme.FONT_BOLD, relief="flat", cursor="hand2",
                  padx=15, pady=5, command=self.on_logout).pack(side="left")

        # Body
        body = tk.Frame(self.root, bg=Theme.BG)
        body.pack(fill="both", expand=True, padx=25, pady=20)

        tk.Label(body, text="Your Courses — Evaluate Your Lecturers",
                 bg=Theme.BG, fg=Theme.TEXT, font=Theme.FONT_HEADING).pack(anchor="w")
        tk.Label(body,
                 text="Select a course below to submit an anonymous evaluation of the lecturer. "
                      "Your feedback helps improve teaching quality.",
                 bg=Theme.BG, fg=Theme.TEXT_MUTED, font=Theme.FONT_SMALL,
                 wraplength=900, justify="left").pack(anchor="w", pady=(2, 15))

        # Table
        table_frame = tk.Frame(body, bg=Theme.CARD,
                               highlightbackground=Theme.BORDER, highlightthickness=1)
        table_frame.pack(fill="both", expand=True)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview",
                        background=Theme.CARD, fieldbackground=Theme.CARD,
                        foreground=Theme.TEXT, rowheight=32,
                        font=Theme.FONT_BODY, borderwidth=0)
        style.configure("Treeview.Heading",
                        background=Theme.PRIMARY, foreground="white",
                        font=Theme.FONT_BOLD, relief="flat", padding=8)
        style.map("Treeview", background=[("selected", Theme.SECONDARY)])

        cols = ("code", "course", "lecturer", "department", "semester", "status")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings", height=14)

        widths = {"code": 90, "course": 260, "lecturer": 200,
                  "department": 180, "semester": 110, "status": 130}
        headings = {"code": "Code", "course": "Course", "lecturer": "Lecturer",
                    "department": "Department", "semester": "Semester", "status": "Status"}
        for c in cols:
            self.tree.heading(c, text=headings[c])
            self.tree.column(c, width=widths[c], anchor="w")

        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", lambda e: self.open_evaluation())

        self.tree.tag_configure("done", foreground=Theme.SUCCESS)
        self.tree.tag_configure("pending", foreground=Theme.TEXT)

        # Actions
        actions = tk.Frame(body, bg=Theme.BG)
        actions.pack(fill="x", pady=(15, 0))
        tk.Button(actions, text="📝  Evaluate Selected Course",
                  bg=Theme.PRIMARY, fg="white", font=Theme.FONT_BOLD,
                  relief="flat", cursor="hand2", padx=20, pady=10,
                  command=self.open_evaluation).pack(side="left")
        tk.Button(actions, text="🔄  Refresh", bg=Theme.SECONDARY, fg="white",
                  font=Theme.FONT_BOLD, relief="flat", cursor="hand2",
                  padx=20, pady=10, command=self.load_courses).pack(side="left", padx=10)

    def load_courses(self):
        self.tree.delete(*self.tree.get_children())
        for cid, code, name, lecturer, dept, sem, _ in self.db.get_courses():
            done = self.db.has_evaluated(self.user_id, cid)
            status = "✓ Evaluated" if done else "Pending"
            tag = "done" if done else "pending"
            self.tree.insert("", "end", iid=str(cid),
                             values=(code, name, lecturer, dept, sem, status), tags=(tag,))

    def open_evaluation(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("No Selection", "Please select a course to evaluate.")
            return
        cid = int(sel[0])
        if self.db.has_evaluated(self.user_id, cid):
            messagebox.showinfo("Already Evaluated",
                                "You have already submitted an evaluation for this course.")
            return
        EvaluationForm(self.root, self.db, self.user_id, cid, self.load_courses)


# ---------------------------------------------------------------------------
# EVALUATION FORM
# ---------------------------------------------------------------------------
class EvaluationForm:
    CRITERIA = [
        ("knowledge",     "Subject Knowledge",        "Demonstrates deep understanding of the subject matter"),
        ("communication", "Communication Skills",     "Explains concepts clearly and effectively"),
        ("preparation",   "Lecture Preparation",      "Classes are well-prepared and organized"),
        ("engagement",    "Student Engagement",       "Keeps students engaged and encourages participation"),
        ("fairness",      "Fairness in Assessment",   "Grades and assessments are fair and transparent"),
        ("availability",  "Availability for Help",    "Accessible outside class for questions and support"),
        ("overall",       "Overall Rating",           "Your overall impression of this lecturer"),
    ]

    def __init__(self, parent, db, student_id, course_id, on_submit):
        self.db = db
        self.student_id = student_id
        self.course_id = course_id
        self.on_submit = on_submit

        # Find the course / lecturer info
        info = None
        for row in db.get_courses():
            if row[0] == course_id:
                info = row
                break
        self.course_code, self.course_name = info[1], info[2]
        self.lecturer_name, self.lecturer_id = info[3], info[6]

        self.win = tk.Toplevel(parent)
        self.win.title("Lecturer Evaluation Form")
        self.win.geometry("760x780")
        self.win.configure(bg=Theme.BG)
        self.win.transient(parent)
        self.win.grab_set()

        self.ratings = {}
        self.build_ui()

    def build_ui(self):
        # Header
        header = tk.Frame(self.win, bg=Theme.PRIMARY, height=100)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Lecturer Evaluation Form", bg=Theme.PRIMARY, fg="white",
                 font=Theme.FONT_HEADING).pack(anchor="w", padx=25, pady=(18, 0))
        tk.Label(header, text=f"{self.course_code} — {self.course_name}",
                 bg=Theme.PRIMARY, fg=Theme.ACCENT,
                 font=Theme.FONT_BOLD).pack(anchor="w", padx=25)
        tk.Label(header, text=f"Lecturer: {self.lecturer_name}",
                 bg=Theme.PRIMARY, fg="white", font=Theme.FONT_SMALL).pack(anchor="w", padx=25)

        # Scrollable body
        container = tk.Frame(self.win, bg=Theme.BG)
        container.pack(fill="both", expand=True)

        canvas = tk.Canvas(container, bg=Theme.BG, highlightthickness=0)
        scroll = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=Theme.BG)
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw", width=740)
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True, padx=(15, 0), pady=15)
        scroll.pack(side="right", fill="y", pady=15)

        # Instructions
        info = tk.Frame(inner, bg="#f7f3e8",
                        highlightbackground=Theme.ACCENT, highlightthickness=1)
        info.pack(fill="x", padx=10, pady=(0, 15))
        tk.Label(info, text="📋  Rating Scale",
                 bg="#f7f3e8", fg=Theme.PRIMARY, font=Theme.FONT_BOLD).pack(anchor="w", padx=12, pady=(8, 2))
        tk.Label(info,
                 text="1 = Poor   •   2 = Below Average   •   3 = Average   •   4 = Good   •   5 = Excellent",
                 bg="#f7f3e8", fg=Theme.TEXT, font=Theme.FONT_SMALL).pack(anchor="w", padx=12, pady=(0, 8))

        # Criteria
        for key, label, desc in self.CRITERIA:
            self.build_criterion(inner, key, label, desc)

        # Comments
        tk.Label(inner, text="Additional Comments (Optional)",
                 bg=Theme.BG, fg=Theme.TEXT, font=Theme.FONT_BOLD).pack(anchor="w", padx=10, pady=(10, 4))
        tk.Label(inner, text="Share any specific feedback, suggestions, or praise.",
                 bg=Theme.BG, fg=Theme.TEXT_MUTED, font=Theme.FONT_SMALL).pack(anchor="w", padx=10)
        self.comments = scrolledtext.ScrolledText(inner, height=5, font=Theme.FONT_BODY,
                                                  relief="solid", bd=1, wrap="word")
        self.comments.pack(fill="x", padx=10, pady=(6, 15))

        # Buttons
        btns = tk.Frame(inner, bg=Theme.BG)
        btns.pack(fill="x", padx=10, pady=(0, 10))
        tk.Button(btns, text="Submit Evaluation", bg=Theme.SUCCESS, fg="white",
                  font=Theme.FONT_BOLD, relief="flat", cursor="hand2",
                  padx=25, pady=10, command=self.submit).pack(side="left")
        tk.Button(btns, text="Cancel", bg=Theme.BG, fg=Theme.TEXT_MUTED,
                  font=Theme.FONT_BODY, relief="flat", cursor="hand2",
                  padx=25, pady=10, command=self.win.destroy).pack(side="left", padx=10)

    def build_criterion(self, parent, key, label, desc):
        frame = tk.Frame(parent, bg=Theme.CARD,
                         highlightbackground=Theme.BORDER, highlightthickness=1)
        frame.pack(fill="x", padx=10, pady=5)

        tk.Label(frame, text=label, bg=Theme.CARD, fg=Theme.TEXT,
                 font=Theme.FONT_BOLD).pack(anchor="w", padx=12, pady=(8, 0))
        tk.Label(frame, text=desc, bg=Theme.CARD, fg=Theme.TEXT_MUTED,
                 font=Theme.FONT_SMALL).pack(anchor="w", padx=12)

        radio = tk.Frame(frame, bg=Theme.CARD)
        radio.pack(anchor="w", padx=12, pady=(6, 10))
        var = tk.IntVar(value=0)
        self.ratings[key] = var
        labels = {1: "Poor", 2: "Below Avg", 3: "Average", 4: "Good", 5: "Excellent"}
        for i in range(1, 6):
            rb = tk.Radiobutton(radio, text=f"{i} — {labels[i]}", variable=var, value=i,
                                bg=Theme.CARD, fg=Theme.TEXT, font=Theme.FONT_SMALL,
                                activebackground=Theme.CARD,
                                selectcolor="white", cursor="hand2")
            rb.pack(side="left", padx=(0, 15))

    def submit(self):
        # Validate
        missing = [label for key, label, _ in self.CRITERIA if self.ratings[key].get() == 0]
        if missing:
            messagebox.showwarning("Incomplete",
                                   "Please rate all criteria:\n\n• " + "\n• ".join(missing))
            return

        comments = self.comments.get("1.0", "end").strip()
        data = (
            self.student_id, self.course_id, self.lecturer_id,
            self.ratings["knowledge"].get(),
            self.ratings["communication"].get(),
            self.ratings["preparation"].get(),
            self.ratings["engagement"].get(),
            self.ratings["fairness"].get(),
            self.ratings["availability"].get(),
            self.ratings["overall"].get(),
            comments,
            datetime.now().isoformat(timespec="seconds"),
        )
        ok, msg = self.db.submit_evaluation(data)
        if ok:
            messagebox.showinfo("Thank You",
                                "Your evaluation has been submitted anonymously.\nThank you for your feedback!")
            self.on_submit()
            self.win.destroy()
        else:
            messagebox.showerror("Error", msg)


# ---------------------------------------------------------------------------
# ADMIN DASHBOARD
# ---------------------------------------------------------------------------
class AdminDashboard:
    def __init__(self, root, db, user, on_logout):
        self.root = root
        self.db = db
        self.user_id, self.full_name, self.role = user
        self.on_logout = on_logout

        for w in root.winfo_children():
            w.destroy()

        root.title(f"Administrator Portal - {self.full_name}")
        root.geometry("1100x720")
        root.configure(bg=Theme.BG)
        root.resizable(True, True)

        self.build_ui()

    def build_ui(self):
        # Header
        header = tk.Frame(self.root, bg=Theme.PRIMARY, height=70)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="🏛  Administrator Portal", bg=Theme.PRIMARY, fg="white",
                 font=Theme.FONT_HEADING).pack(side="left", padx=25, pady=18)

        right = tk.Frame(header, bg=Theme.PRIMARY)
        right.pack(side="right", padx=25, pady=15)
        tk.Label(right, text=f"👤  {self.full_name}", bg=Theme.PRIMARY, fg="white",
                 font=Theme.FONT_BODY).pack(side="left", padx=(0, 15))
        tk.Button(right, text="Logout", bg=Theme.DANGER, fg="white",
                  font=Theme.FONT_BOLD, relief="flat", cursor="hand2",
                  padx=15, pady=5, command=self.on_logout).pack(side="left")

        # Tabs
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TNotebook", background=Theme.BG, borderwidth=0)
        style.configure("TNotebook.Tab", padding=(18, 10),
                        font=Theme.FONT_BOLD, background=Theme.BORDER,
                        foreground=Theme.TEXT)
        style.map("TNotebook.Tab",
                  background=[("selected", Theme.CARD)],
                  foreground=[("selected", Theme.PRIMARY)])

        self.nb = ttk.Notebook(self.root)
        self.nb.pack(fill="both", expand=True, padx=20, pady=15)

        self.tab_reports   = tk.Frame(self.nb, bg=Theme.BG)
        self.tab_lecturers = tk.Frame(self.nb, bg=Theme.BG)
        self.tab_courses   = tk.Frame(self.nb, bg=Theme.BG)

        self.nb.add(self.tab_reports,   text="  📊  Evaluation Reports  ")
        self.nb.add(self.tab_lecturers, text="  👨‍🏫  Manage Lecturers  ")
        self.nb.add(self.tab_courses,   text="  📚  Manage Courses  ")

        self.build_reports_tab()
        self.build_lecturers_tab()
        self.build_courses_tab()

    # -- Reports tab --------------------------------------------------------
    def build_reports_tab(self):
        tab = self.tab_reports
        tk.Label(tab, text="Lecturer Performance Summary",
                 bg=Theme.BG, fg=Theme.TEXT, font=Theme.FONT_HEADING).pack(anchor="w", padx=10, pady=(10, 4))
        tk.Label(tab, text="Double-click a lecturer to view their detailed evaluation report.",
                 bg=Theme.BG, fg=Theme.TEXT_MUTED, font=Theme.FONT_SMALL).pack(anchor="w", padx=10, pady=(0, 10))

        frame = tk.Frame(tab, bg=Theme.CARD,
                         highlightbackground=Theme.BORDER, highlightthickness=1)
        frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        cols = ("name", "title", "department", "count", "rating")
        self.lecturer_tree = ttk.Treeview(frame, columns=cols, show="headings", height=15)
        widths = {"name": 240, "title": 180, "department": 200, "count": 140, "rating": 180}
        headings = {"name": "Lecturer", "title": "Title", "department": "Department",
                    "count": "# Evaluations", "rating": "Overall Rating"}
        for c in cols:
            self.lecturer_tree.heading(c, text=headings[c])
            self.lecturer_tree.column(c, width=widths[c], anchor="w")

        vsb = ttk.Scrollbar(frame, orient="vertical", command=self.lecturer_tree.yview)
        self.lecturer_tree.configure(yscrollcommand=vsb.set)
        self.lecturer_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.lecturer_tree.bind("<Double-1>", lambda e: self.view_report())

        actions = tk.Frame(tab, bg=Theme.BG)
        actions.pack(fill="x", padx=10, pady=5)
        tk.Button(actions, text="📄  View Detailed Report",
                  bg=Theme.PRIMARY, fg="white", font=Theme.FONT_BOLD,
                  relief="flat", cursor="hand2", padx=18, pady=8,
                  command=self.view_report).pack(side="left")
        tk.Button(actions, text="🔄  Refresh", bg=Theme.SECONDARY, fg="white",
                  font=Theme.FONT_BOLD, relief="flat", cursor="hand2",
                  padx=18, pady=8, command=self.load_summaries).pack(side="left", padx=10)

        self.load_summaries()

    def load_summaries(self):
        self.lecturer_tree.delete(*self.lecturer_tree.get_children())
        for lid, name, dept, title, count, avg in self.db.get_all_lecturer_summaries():
            rating = f"{avg:.2f} / 5.00  {self.stars(avg)}" if avg else "— No evaluations —"
            self.lecturer_tree.insert("", "end", iid=str(lid),
                                       values=(name, title or "", dept, count, rating))

    @staticmethod
    def stars(avg):
        if not avg:
            return ""
        filled = round(avg)
        return "★" * filled + "☆" * (5 - filled)

    def view_report(self):
        sel = self.lecturer_tree.selection()
        if not sel:
            messagebox.showinfo("No Selection", "Please select a lecturer.")
            return
        LecturerReportWindow(self.root, self.db, int(sel[0]))

    # -- Lecturers tab ------------------------------------------------------
    def build_lecturers_tab(self):
        tab = self.tab_lecturers
        tk.Label(tab, text="Lecturer Directory",
                 bg=Theme.BG, fg=Theme.TEXT, font=Theme.FONT_HEADING).pack(anchor="w", padx=10, pady=(10, 10))

        frame = tk.Frame(tab, bg=Theme.CARD,
                         highlightbackground=Theme.BORDER, highlightthickness=1)
        frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        cols = ("name", "title", "department", "email")
        self.lect_tree = ttk.Treeview(frame, columns=cols, show="headings", height=14)
        for c, w, h in [("name", 220, "Full Name"), ("title", 180, "Title"),
                        ("department", 200, "Department"), ("email", 260, "Email")]:
            self.lect_tree.heading(c, text=h)
            self.lect_tree.column(c, width=w, anchor="w")
        self.lect_tree.pack(fill="both", expand=True)

        # Add form
        form = tk.Frame(tab, bg=Theme.CARD,
                        highlightbackground=Theme.BORDER, highlightthickness=1)
        form.pack(fill="x", padx=10, pady=(0, 10))

        tk.Label(form, text="Add New Lecturer", bg=Theme.CARD, fg=Theme.PRIMARY,
                 font=Theme.FONT_BOLD).grid(row=0, column=0, columnspan=4, sticky="w", padx=10, pady=(10, 5))

        labels = ["Full Name", "Title", "Department", "Email"]
        self.lect_entries = {}
        for i, lbl in enumerate(labels):
            tk.Label(form, text=lbl, bg=Theme.CARD, fg=Theme.TEXT,
                     font=Theme.FONT_BODY).grid(row=1, column=i, sticky="w", padx=10)
            ent = tk.Entry(form, font=Theme.FONT_BODY, bg="white", relief="solid", bd=1)
            ent.grid(row=2, column=i, sticky="we", padx=10, pady=(2, 10), ipady=4)
            self.lect_entries[lbl] = ent
        for i in range(4):
            form.grid_columnconfigure(i, weight=1)

        tk.Button(form, text="➕  Add Lecturer", bg=Theme.SUCCESS, fg="white",
                  font=Theme.FONT_BOLD, relief="flat", cursor="hand2",
                  padx=15, pady=6, command=self.add_lecturer
                  ).grid(row=3, column=0, columnspan=4, pady=(0, 10))

        self.load_lecturers()

    def load_lecturers(self):
        self.lect_tree.delete(*self.lect_tree.get_children())
        for lid, name, dept, email, title in self.db.get_lecturers():
            self.lect_tree.insert("", "end", values=(name, title or "", dept, email or ""))

    def add_lecturer(self):
        name  = self.lect_entries["Full Name"].get().strip()
        title = self.lect_entries["Title"].get().strip()
        dept  = self.lect_entries["Department"].get().strip()
        email = self.lect_entries["Email"].get().strip()
        if not name or not dept:
            messagebox.showwarning("Missing", "Full Name and Department are required.")
            return
        self.db.add_lecturer(name, dept, email, title)
        for e in self.lect_entries.values():
            e.delete(0, "end")
        self.load_lecturers()
        self.load_summaries()
        self.load_course_lecturer_options()
        messagebox.showinfo("Success", f"Lecturer '{name}' has been added.")

    # -- Courses tab --------------------------------------------------------
    def build_courses_tab(self):
        tab = self.tab_courses
        tk.Label(tab, text="Course Directory",
                 bg=Theme.BG, fg=Theme.TEXT, font=Theme.FONT_HEADING).pack(anchor="w", padx=10, pady=(10, 10))

        frame = tk.Frame(tab, bg=Theme.CARD,
                         highlightbackground=Theme.BORDER, highlightthickness=1)
        frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        cols = ("code", "name", "lecturer", "department", "semester")
        self.course_tree = ttk.Treeview(frame, columns=cols, show="headings", height=12)
        for c, w, h in [("code", 90, "Code"), ("name", 250, "Course Name"),
                        ("lecturer", 200, "Lecturer"), ("department", 180, "Department"),
                        ("semester", 130, "Semester")]:
            self.course_tree.heading(c, text=h)
            self.course_tree.column(c, width=w, anchor="w")
        self.course_tree.pack(fill="both", expand=True)

        # Add form
        form = tk.Frame(tab, bg=Theme.CARD,
                        highlightbackground=Theme.BORDER, highlightthickness=1)
        form.pack(fill="x", padx=10, pady=(0, 10))
        tk.Label(form, text="Add New Course", bg=Theme.CARD, fg=Theme.PRIMARY,
                 font=Theme.FONT_BOLD).grid(row=0, column=0, columnspan=4, sticky="w", padx=10, pady=(10, 5))

        self.course_entries = {}

        tk.Label(form, text="Course Code", bg=Theme.CARD,
                 font=Theme.FONT_BODY).grid(row=1, column=0, sticky="w", padx=10)
        e_code = tk.Entry(form, font=Theme.FONT_BODY, bg="white", relief="solid", bd=1)
        e_code.grid(row=2, column=0, sticky="we", padx=10, pady=(2, 10), ipady=4)
        self.course_entries["code"] = e_code

        tk.Label(form, text="Course Name", bg=Theme.CARD,
                 font=Theme.FONT_BODY).grid(row=1, column=1, sticky="w", padx=10)
        e_name = tk.Entry(form, font=Theme.FONT_BODY, bg="white", relief="solid", bd=1)
        e_name.grid(row=2, column=1, sticky="we", padx=10, pady=(2, 10), ipady=4)
        self.course_entries["name"] = e_name

        tk.Label(form, text="Lecturer", bg=Theme.CARD,
                 font=Theme.FONT_BODY).grid(row=1, column=2, sticky="w", padx=10)
        self.lecturer_combo = ttk.Combobox(form, state="readonly", font=Theme.FONT_BODY)
        self.lecturer_combo.grid(row=2, column=2, sticky="we", padx=10, pady=(2, 10), ipady=3)

        tk.Label(form, text="Semester", bg=Theme.CARD,
                 font=Theme.FONT_BODY).grid(row=1, column=3, sticky="w", padx=10)
        e_sem = tk.Entry(form, font=Theme.FONT_BODY, bg="white", relief="solid", bd=1)
        e_sem.insert(0, "2026 Spring")
        e_sem.grid(row=2, column=3, sticky="we", padx=10, pady=(2, 10), ipady=4)
        self.course_entries["sem"] = e_sem

        for i in range(4):
            form.grid_columnconfigure(i, weight=1)

        tk.Button(form, text="➕  Add Course", bg=Theme.SUCCESS, fg="white",
                  font=Theme.FONT_BOLD, relief="flat", cursor="hand2",
                  padx=15, pady=6, command=self.add_course
                  ).grid(row=3, column=0, columnspan=4, pady=(0, 10))

        self.load_courses_list()
        self.load_course_lecturer_options()

    def load_courses_list(self):
        self.course_tree.delete(*self.course_tree.get_children())
        for _, code, name, lecturer, dept, sem, _ in self.db.get_courses():
            self.course_tree.insert("", "end", values=(code, name, lecturer, dept, sem))

    def load_course_lecturer_options(self):
        if not hasattr(self, "lecturer_combo"):
            return
        lecturers = self.db.get_lecturers()
        self.lecturer_map = {f"{l[1]} ({l[2]})": l[0] for l in lecturers}
        self.lecturer_combo["values"] = list(self.lecturer_map.keys())

    def add_course(self):
        code = self.course_entries["code"].get().strip().upper()
        name = self.course_entries["name"].get().strip()
        sem  = self.course_entries["sem"].get().strip()
        lec  = self.lecturer_combo.get()
        if not all([code, name, sem, lec]):
            messagebox.showwarning("Missing", "All fields are required.")
            return
        lecturer_id = self.lecturer_map.get(lec)
        ok, msg = self.db.add_course(code, name, lecturer_id, sem)
        if ok:
            for e in self.course_entries.values():
                e.delete(0, "end")
            self.course_entries["sem"].insert(0, "2026 Spring")
            self.lecturer_combo.set("")
            self.load_courses_list()
            messagebox.showinfo("Success", msg)
        else:
            messagebox.showerror("Error", msg)


# ---------------------------------------------------------------------------
# LECTURER REPORT WINDOW
# ---------------------------------------------------------------------------
class LecturerReportWindow:
    CRITERIA_LABELS = [
        ("Subject Knowledge",      1),
        ("Communication Skills",   2),
        ("Lecture Preparation",    3),
        ("Student Engagement",     4),
        ("Fairness in Assessment", 5),
        ("Availability for Help",  6),
        ("Overall Rating",         7),
    ]

    def __init__(self, parent, db, lecturer_id):
        self.db = db
        self.lecturer_id = lecturer_id

        # Fetch lecturer info
        lecturer = next((l for l in db.get_lecturers() if l[0] == lecturer_id), None)
        if not lecturer:
            return
        _, self.name, self.dept, self.email, self.title = lecturer

        self.win = tk.Toplevel(parent)
        self.win.title(f"Evaluation Report - {self.name}")
        self.win.geometry("780x700")
        self.win.configure(bg=Theme.BG)
        self.win.transient(parent)

        self.build_ui()

    def build_ui(self):
        # Header
        header = tk.Frame(self.win, bg=Theme.PRIMARY, height=110)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text=self.name, bg=Theme.PRIMARY, fg="white",
                 font=Theme.FONT_TITLE).pack(anchor="w", padx=25, pady=(15, 0))
        tk.Label(header, text=f"{self.title or 'Lecturer'} • {self.dept}",
                 bg=Theme.PRIMARY, fg=Theme.ACCENT, font=Theme.FONT_BOLD).pack(anchor="w", padx=25)
        if self.email:
            tk.Label(header, text=self.email, bg=Theme.PRIMARY, fg="white",
                     font=Theme.FONT_SMALL).pack(anchor="w", padx=25)

        body = tk.Frame(self.win, bg=Theme.BG)
        body.pack(fill="both", expand=True, padx=20, pady=15)

        # Stats
        stats = self.db.get_lecturer_report(self.lecturer_id)
        count = stats[0]

        if count == 0:
            tk.Label(body, text="No evaluations have been submitted yet.",
                     bg=Theme.BG, fg=Theme.TEXT_MUTED, font=Theme.FONT_HEADING).pack(pady=60)
            tk.Button(body, text="Close", bg=Theme.PRIMARY, fg="white",
                      font=Theme.FONT_BOLD, relief="flat", cursor="hand2",
                      padx=20, pady=8, command=self.win.destroy).pack()
            return

        # Summary cards
        summary = tk.Frame(body, bg=Theme.BG)
        summary.pack(fill="x")

        def card(parent, label, value, color):
            f = tk.Frame(parent, bg=color,
                         highlightbackground=Theme.BORDER, highlightthickness=1)
            f.pack(side="left", expand=True, fill="both", padx=5)
            tk.Label(f, text=label, bg=color, fg="white", font=Theme.FONT_SMALL).pack(pady=(10, 0))
            tk.Label(f, text=value, bg=color, fg="white",
                     font=("Georgia", 20, "bold")).pack(pady=(2, 10))

        card(summary, "Total Evaluations", str(count), Theme.PRIMARY)
        card(summary, "Overall Rating", f"{stats[7]:.2f} / 5", Theme.SECONDARY)

        # Star rating display
        stars_filled = round(stats[7])
        star_str = "★" * stars_filled + "☆" * (5 - stars_filled)
        card(summary, "Stars", star_str, Theme.ACCENT)

        # Breakdown
        tk.Label(body, text="Rating Breakdown", bg=Theme.BG, fg=Theme.TEXT,
                 font=Theme.FONT_HEADING).pack(anchor="w", pady=(20, 8))

        breakdown = tk.Frame(body, bg=Theme.CARD,
                             highlightbackground=Theme.BORDER, highlightthickness=1)
        breakdown.pack(fill="x")

        for label, idx in self.CRITERIA_LABELS:
            avg = stats[idx]
            row = tk.Frame(breakdown, bg=Theme.CARD)
            row.pack(fill="x", padx=15, pady=6)
            tk.Label(row, text=label, bg=Theme.CARD, fg=Theme.TEXT,
                     font=Theme.FONT_BODY, width=25, anchor="w").pack(side="left")
            # Bar
            bar_bg = tk.Frame(row, bg="#e8e4d8", height=18, width=300)
            bar_bg.pack(side="left", padx=(0, 10))
            bar_bg.pack_propagate(False)
            fill_w = int(300 * (avg / 5))
            fill_color = self.rating_color(avg)
            tk.Frame(bar_bg, bg=fill_color, height=18, width=fill_w).pack(side="left")
            tk.Label(row, text=f"{avg:.2f}", bg=Theme.CARD, fg=Theme.TEXT,
                     font=Theme.FONT_BOLD, width=6).pack(side="left")

        # Comments
        tk.Label(body, text="Student Comments", bg=Theme.BG, fg=Theme.TEXT,
                 font=Theme.FONT_HEADING).pack(anchor="w", pady=(20, 8))

        comments_frame = tk.Frame(body, bg=Theme.CARD,
                                   highlightbackground=Theme.BORDER, highlightthickness=1)
        comments_frame.pack(fill="both", expand=True)

        text = scrolledtext.ScrolledText(comments_frame, font=Theme.FONT_BODY,
                                         bg=Theme.CARD, relief="flat", bd=0,
                                         wrap="word", padx=12, pady=10)
        text.pack(fill="both", expand=True)

        comments = self.db.get_lecturer_comments(self.lecturer_id)
        if not comments:
            text.insert("end", "No written comments have been submitted.", "muted")
            text.tag_config("muted", foreground=Theme.TEXT_MUTED, font=Theme.FONT_SMALL)
        else:
            for i, (code, comment, date) in enumerate(comments):
                if i > 0:
                    text.insert("end", "\n" + "─" * 70 + "\n\n")
                text.insert("end", f"[{code}]  ", "course")
                text.insert("end", f"{date[:10]}\n", "date")
                text.insert("end", f"{comment}\n", "body")
        text.tag_config("course", foreground=Theme.PRIMARY, font=Theme.FONT_BOLD)
        text.tag_config("date",   foreground=Theme.TEXT_MUTED, font=Theme.FONT_SMALL)
        text.tag_config("body",   foreground=Theme.TEXT, font=Theme.FONT_BODY)
        text.config(state="disabled")

        tk.Button(body, text="Close", bg=Theme.PRIMARY, fg="white",
                  font=Theme.FONT_BOLD, relief="flat", cursor="hand2",
                  padx=25, pady=8, command=self.win.destroy).pack(pady=(15, 0))

    @staticmethod
    def rating_color(avg):
        if avg >= 4.5: return Theme.SUCCESS
        if avg >= 3.5: return Theme.SECONDARY
        if avg >= 2.5: return Theme.ACCENT
        return Theme.DANGER


# ---------------------------------------------------------------------------
# APPLICATION CONTROLLER
# ---------------------------------------------------------------------------
class App:
    def __init__(self):
        self.db = Database()
        self.root = tk.Tk()
        self.show_login()

    def show_login(self):
        for w in self.root.winfo_children():
            w.destroy()
        self.root.geometry("500x620")
        LoginWindow(self.root, self.db, self.on_login_success)

    def on_login_success(self, user):
        _, _, role = user
        if role == "admin":
            AdminDashboard(self.root, self.db, user, self.show_login)
        else:
            StudentDashboard(self.root, self.db, user, self.show_login)

    def run(self):
        self.root.mainloop()
        self.db.close()


if __name__ == "__main__":
    App().run()
