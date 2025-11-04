"""
Learning Management System (LMS) GUI

Full-featured GUI for managing LMS courses, content delivery, video lectures,
discussion forums, quizzes, assessments, and gradebook.
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
from datetime import datetime
from typing import Optional

from university_system.infrastructure.auth.user_authentication import UserAuth
from university_system.modules.domain.academics.services.lms.lms_core import (
    LMSCourseManager,
    LMSContentManager,
    LMSDiscussionManager,
    LMSQuizManager,
    LMSGradebookManager
)
from university_system.modules.domain.academics.services.lms.db_schema import initialize_lms_database
from university_system.infrastructure.database.db import get_connection
from university_system.modules.shared.utils.activity_logger import log_activity


class LMSGUI:
    """Main GUI for Learning Management System"""

    def __init__(self, parent, auth: UserAuth):
        self.root = tk.Toplevel(parent)
        self.root.title("Learning Management System (LMS)")
        self.root.geometry("1200x700")
        self.auth = auth

        # Initialize database
        try:
            initialize_lms_database()
        except Exception as e:
            print(f"Database initialization warning: {e}")

        # Get current user role
        self.user_role = None
        self.user_id = None
        if self.auth and hasattr(self.auth, 'current_user') and self.auth.current_user:
            self.user_id = self.auth.current_user.get('username', 'Unknown')
            self.user_role = self.auth.current_user.get('role', 'student')

        self.create_widgets()
        self.load_courses()

    def create_widgets(self):
        """Create all GUI widgets"""
        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        title = ttk.Label(main_frame, text="Learning Management System (LMS)",
                         font=('Arial', 16, 'bold'))
        title.pack(pady=10)

        # User info
        user_info = ttk.Label(main_frame,
                             text=f"User: {self.user_id} | Role: {self.user_role}",
                             font=('Arial', 10))
        user_info.pack(pady=5)

        # Notebook for tabs
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Create tabs based on user role
        if self.user_role in ['admin', 'instructor']:
            self.create_courses_tab()
            self.create_content_tab()
            self.create_discussions_tab()
            self.create_quizzes_tab()
            self.create_gradebook_tab()

        # Students get My Courses tab
        if self.user_role in ['student', 'admin']:
            self.create_my_courses_tab()

    def create_courses_tab(self):
        """Create LMS Courses management tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text="Courses")

        # Top frame for buttons
        button_frame = ttk.Frame(tab)
        button_frame.pack(fill=tk.X, pady=5)

        ttk.Button(button_frame, text="Create Course",
                  command=self.create_course).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Publish Course",
                  command=self.publish_course).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="View Details",
                  command=self.view_course_details).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Refresh",
                  command=self.load_courses).pack(side=tk.LEFT, padx=5)

        # Courses list
        list_frame = ttk.LabelFrame(tab, text="LMS Courses", padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        # Treeview for courses
        columns = ('ID', 'Module Code', 'Instructor', 'Start Date', 'End Date',
                  'Enrollment Limit', 'Published')
        self.courses_tree = ttk.Treeview(list_frame, columns=columns, show='headings',
                                        height=15)

        for col in columns:
            self.courses_tree.heading(col, text=col)
            width = 150 if col == 'Module Code' else 100
            self.courses_tree.column(col, width=width)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL,
                                 command=self.courses_tree.yview)
        self.courses_tree.configure(yscrollcommand=scrollbar.set)

        self.courses_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def create_content_tab(self):
        """Create Course Content management tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text="Content")

        # Course selection
        select_frame = ttk.Frame(tab)
        select_frame.pack(fill=tk.X, pady=5)

        ttk.Label(select_frame, text="Select Course:").pack(side=tk.LEFT, padx=5)
        self.content_course_combo = ttk.Combobox(select_frame, width=50, state='readonly')
        self.content_course_combo.pack(side=tk.LEFT, padx=5)
        self.content_course_combo.bind('<<ComboboxSelected>>', self.load_course_content)

        ttk.Button(select_frame, text="Load Content",
                  command=self.load_course_content).pack(side=tk.LEFT, padx=5)

        # Button frame
        button_frame = ttk.Frame(tab)
        button_frame.pack(fill=tk.X, pady=5)

        ttk.Button(button_frame, text="Add Content",
                  command=self.add_content).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Add Video Lecture",
                  command=self.add_video_lecture).pack(side=tk.LEFT, padx=5)

        # Content list
        list_frame = ttk.LabelFrame(tab, text="Course Content", padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        columns = ('ID', 'Type', 'Title', 'Description', 'URL', 'Order', 'Release Date')
        self.content_tree = ttk.Treeview(list_frame, columns=columns, show='headings',
                                        height=15)

        for col in columns:
            self.content_tree.heading(col, text=col)
            width = 200 if col in ['Title', 'Description', 'URL'] else 80
            self.content_tree.column(col, width=width)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL,
                                 command=self.content_tree.yview)
        self.content_tree.configure(yscrollcommand=scrollbar.set)

        self.content_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def create_discussions_tab(self):
        """Create Discussion Forums tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text="Discussions")

        # Course selection
        select_frame = ttk.Frame(tab)
        select_frame.pack(fill=tk.X, pady=5)

        ttk.Label(select_frame, text="Select Course:").pack(side=tk.LEFT, padx=5)
        self.discussion_course_combo = ttk.Combobox(select_frame, width=50, state='readonly')
        self.discussion_course_combo.pack(side=tk.LEFT, padx=5)
        self.discussion_course_combo.bind('<<ComboboxSelected>>', self.load_forums)

        ttk.Button(select_frame, text="Load Forums",
                  command=self.load_forums).pack(side=tk.LEFT, padx=5)

        # Button frame
        button_frame = ttk.Frame(tab)
        button_frame.pack(fill=tk.X, pady=5)

        ttk.Button(button_frame, text="Create Forum",
                  command=self.create_forum).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="View Posts",
                  command=self.view_forum_posts).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Add Post",
                  command=self.add_post).pack(side=tk.LEFT, padx=5)

        # Forums list
        list_frame = ttk.LabelFrame(tab, text="Discussion Forums", padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        columns = ('ID', 'Topic', 'Description', 'Created By', 'Pinned', 'Created Date')
        self.forums_tree = ttk.Treeview(list_frame, columns=columns, show='headings',
                                       height=15)

        for col in columns:
            self.forums_tree.heading(col, text=col)
            width = 250 if col in ['Topic', 'Description'] else 100
            self.forums_tree.column(col, width=width)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL,
                                 command=self.forums_tree.yview)
        self.forums_tree.configure(yscrollcommand=scrollbar.set)

        self.forums_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def create_quizzes_tab(self):
        """Create Quizzes & Assessments tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text="Quizzes")

        # Course selection
        select_frame = ttk.Frame(tab)
        select_frame.pack(fill=tk.X, pady=5)

        ttk.Label(select_frame, text="Select Course:").pack(side=tk.LEFT, padx=5)
        self.quiz_course_combo = ttk.Combobox(select_frame, width=50, state='readonly')
        self.quiz_course_combo.pack(side=tk.LEFT, padx=5)
        self.quiz_course_combo.bind('<<ComboboxSelected>>', self.load_quizzes)

        ttk.Button(select_frame, text="Load Quizzes",
                  command=self.load_quizzes).pack(side=tk.LEFT, padx=5)

        # Button frame
        button_frame = ttk.Frame(tab)
        button_frame.pack(fill=tk.X, pady=5)

        ttk.Button(button_frame, text="Create Quiz",
                  command=self.create_quiz).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Add Questions",
                  command=self.add_quiz_questions).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="View Submissions",
                  command=self.view_quiz_submissions).pack(side=tk.LEFT, padx=5)

        # Quizzes list
        list_frame = ttk.LabelFrame(tab, text="Quizzes", padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        columns = ('ID', 'Title', 'Duration (min)', 'Passing Score', 'Max Attempts',
                  'Available From', 'Available Until')
        self.quizzes_tree = ttk.Treeview(list_frame, columns=columns, show='headings',
                                        height=15)

        for col in columns:
            self.quizzes_tree.heading(col, text=col)
            width = 200 if col == 'Title' else 100
            self.quizzes_tree.column(col, width=width)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL,
                                 command=self.quizzes_tree.yview)
        self.quizzes_tree.configure(yscrollcommand=scrollbar.set)

        self.quizzes_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def create_gradebook_tab(self):
        """Create Gradebook management tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text="Gradebook")

        # Course and student selection
        select_frame = ttk.Frame(tab)
        select_frame.pack(fill=tk.X, pady=5)

        ttk.Label(select_frame, text="Course:").grid(row=0, column=0, padx=5, pady=5)
        self.gradebook_course_combo = ttk.Combobox(select_frame, width=40, state='readonly')
        self.gradebook_course_combo.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(select_frame, text="Student ID:").grid(row=0, column=2, padx=5, pady=5)
        self.gradebook_student_entry = ttk.Entry(select_frame, width=20)
        self.gradebook_student_entry.grid(row=0, column=3, padx=5, pady=5)

        ttk.Button(select_frame, text="Load Grades",
                  command=self.load_student_grades).grid(row=0, column=4, padx=5, pady=5)

        # Button frame
        button_frame = ttk.Frame(tab)
        button_frame.pack(fill=tk.X, pady=5)

        ttk.Button(button_frame, text="Add Grade",
                  command=self.add_grade).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Calculate Course Grade",
                  command=self.calculate_course_grade).pack(side=tk.LEFT, padx=5)

        # Grades display
        list_frame = ttk.LabelFrame(tab, text="Gradebook Entries", padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        columns = ('Entry ID', 'Student ID', 'Assignment Type', 'Assignment ID',
                  'Score', 'Max Score', 'Weight', 'Graded By', 'Date')
        self.gradebook_tree = ttk.Treeview(list_frame, columns=columns, show='headings',
                                          height=15)

        for col in columns:
            self.gradebook_tree.heading(col, text=col)
            self.gradebook_tree.column(col, width=100)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL,
                                 command=self.gradebook_tree.yview)
        self.gradebook_tree.configure(yscrollcommand=scrollbar.set)

        self.gradebook_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def create_my_courses_tab(self):
        """Create My Courses tab (for students)"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text="My Courses")

        ttk.Label(tab, text="My Enrolled Courses",
                 font=('Arial', 12, 'bold')).pack(pady=10)

        # Button frame
        button_frame = ttk.Frame(tab)
        button_frame.pack(fill=tk.X, pady=5)

        ttk.Button(button_frame, text="View Materials",
                  command=self.view_student_materials).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="View My Grades",
                  command=self.view_student_grades).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Refresh",
                  command=self.load_student_courses).pack(side=tk.LEFT, padx=5)

        # Courses list
        list_frame = ttk.LabelFrame(tab, text="Enrolled Courses", padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        columns = ('Course ID', 'Module Code', 'Instructor', 'Progress %', 'Last Accessed')
        self.student_courses_tree = ttk.Treeview(list_frame, columns=columns,
                                                show='headings', height=15)

        for col in columns:
            self.student_courses_tree.heading(col, text=col)
            self.student_courses_tree.column(col, width=150)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL,
                                 command=self.student_courses_tree.yview)
        self.student_courses_tree.configure(yscrollcommand=scrollbar.set)

        self.student_courses_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.load_student_courses()

    # ======================== Courses Methods ========================

    def load_courses(self):
        """Load all LMS courses"""
        try:
            if not hasattr(self, 'courses_tree'):
                return

            self.courses_tree.delete(*self.courses_tree.get_children())

            # Load courses based on role
            if self.user_role == 'instructor':
                courses = LMSCourseManager.get_instructor_courses(self.user_id)
            else:
                with get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        SELECT lms_course_id, module_code, instructor_id,
                               start_date, end_date, enrollment_limit, is_published
                        FROM lms_courses
                        ORDER BY created_at DESC
                    ''')
                    courses = [dict(row) for row in cursor.fetchall()]

            # Update course combo boxes
            course_list = []

            for course in courses:
                is_published = "Yes" if course.get('is_published', 0) == 1 else "No"
                self.courses_tree.insert('', tk.END, values=(
                    course.get('lms_course_id'),
                    course.get('module_code'),
                    course.get('instructor_id'),
                    course.get('start_date', ''),
                    course.get('end_date', ''),
                    course.get('enrollment_limit', 0),
                    is_published
                ))
                course_list.append(f"{course.get('lms_course_id')}: {course.get('module_code')}")

            # Update combo boxes
            if hasattr(self, 'content_course_combo'):
                self.content_course_combo['values'] = course_list
            if hasattr(self, 'discussion_course_combo'):
                self.discussion_course_combo['values'] = course_list
            if hasattr(self, 'quiz_course_combo'):
                self.quiz_course_combo['values'] = course_list
            if hasattr(self, 'gradebook_course_combo'):
                self.gradebook_course_combo['values'] = course_list

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load courses: {e}")

    def create_course(self):
        """Create a new LMS course"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Create LMS Course")
        dialog.geometry("500x500")

        fields = {}

        ttk.Label(dialog, text="Module Code:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        fields['module_code'] = ttk.Entry(dialog, width=40)
        fields['module_code'].grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(dialog, text="Instructor ID:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        fields['instructor_id'] = ttk.Entry(dialog, width=40)
        fields['instructor_id'].insert(0, self.user_id)
        fields['instructor_id'].grid(row=1, column=1, padx=5, pady=5)

        ttk.Label(dialog, text="Description:").grid(row=2, column=0, sticky=tk.NW, padx=5, pady=5)
        fields['description'] = tk.Text(dialog, width=40, height=5)
        fields['description'].grid(row=2, column=1, padx=5, pady=5)

        ttk.Label(dialog, text="Syllabus URL:").grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        fields['syllabus_url'] = ttk.Entry(dialog, width=40)
        fields['syllabus_url'].grid(row=3, column=1, padx=5, pady=5)

        ttk.Label(dialog, text="Start Date (YYYY-MM-DD):").grid(row=4, column=0, sticky=tk.W, padx=5, pady=5)
        fields['start_date'] = ttk.Entry(dialog, width=40)
        fields['start_date'].insert(0, datetime.now().strftime('%Y-%m-%d'))
        fields['start_date'].grid(row=4, column=1, padx=5, pady=5)

        ttk.Label(dialog, text="End Date (YYYY-MM-DD):").grid(row=5, column=0, sticky=tk.W, padx=5, pady=5)
        fields['end_date'] = ttk.Entry(dialog, width=40)
        fields['end_date'].grid(row=5, column=1, padx=5, pady=5)

        ttk.Label(dialog, text="Enrollment Limit:").grid(row=6, column=0, sticky=tk.W, padx=5, pady=5)
        fields['enrollment_limit'] = ttk.Entry(dialog, width=40)
        fields['enrollment_limit'].insert(0, "0")
        fields['enrollment_limit'].grid(row=6, column=1, padx=5, pady=5)

        def save_course():
            try:
                module_code = fields['module_code'].get().strip()
                instructor_id = fields['instructor_id'].get().strip()
                description = fields['description'].get('1.0', tk.END).strip()
                syllabus_url = fields['syllabus_url'].get().strip()
                start_date = fields['start_date'].get().strip()
                end_date = fields['end_date'].get().strip()
                enrollment_limit = int(fields['enrollment_limit'].get().strip())

                if not module_code or not instructor_id:
                    messagebox.showerror("Error", "Module code and instructor ID are required")
                    return

                course_id = LMSCourseManager.create_lms_course(
                    module_code=module_code,
                    instructor_id=instructor_id,
                    course_description=description,
                    syllabus_url=syllabus_url,
                    start_date=start_date,
                    end_date=end_date,
                    enrollment_limit=enrollment_limit
                )

                log_activity('create', 'lms_course', str(course_id),
                           {'module_code': module_code, 'instructor_id': instructor_id})

                messagebox.showinfo("Success",
                                  f"LMS course created successfully! ID: {course_id}")
                dialog.destroy()
                self.load_courses()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to create course: {e}")

        ttk.Button(dialog, text="Create Course",
                  command=save_course).grid(row=7, column=0, columnspan=2, pady=20)

    def publish_course(self):
        """Publish an LMS course"""
        selected = self.courses_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a course first")
            return

        course_id = self.courses_tree.item(selected[0])['values'][0]

        try:
            LMSCourseManager.publish_course(course_id)

            log_activity('publish', 'lms_course', str(course_id))

            messagebox.showinfo("Success", "Course published successfully!")
            self.load_courses()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to publish course: {e}")

    def view_course_details(self):
        """View detailed course information"""
        selected = self.courses_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a course first")
            return

        course_id = self.courses_tree.item(selected[0])['values'][0]

        try:
            course = LMSCourseManager.get_course_details(course_id)
            if course:
                info = (
                    f"Course ID: {course.get('lms_course_id')}\n"
                    f"Module Code: {course.get('module_code')}\n"
                    f"Instructor: {course.get('instructor_id')}\n"
                    f"Description: {course.get('course_description', 'N/A')}\n"
                    f"Start Date: {course.get('start_date', 'N/A')}\n"
                    f"End Date: {course.get('end_date', 'N/A')}\n"
                    f"Enrollment Limit: {course.get('enrollment_limit', 0)}\n"
                    f"Published: {'Yes' if course.get('is_published') else 'No'}\n"
                )
                messagebox.showinfo("Course Details", info)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load course details: {e}")

    # ======================== Content Methods ========================

    def load_course_content(self, event=None):
        """Load content for selected course"""
        try:
            selection = self.content_course_combo.get()
            if not selection:
                return

            course_id = int(selection.split(':')[0])

            self.content_tree.delete(*self.content_tree.get_children())

            content_list = LMSContentManager.get_course_content(course_id)

            for content in content_list:
                self.content_tree.insert('', tk.END, values=(
                    content.get('content_id'),
                    content.get('content_type'),
                    content.get('title'),
                    content.get('description', '')[:50],
                    content.get('content_url', ''),
                    content.get('content_order', 0),
                    content.get('release_date', '')
                ))

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load content: {e}")

    def add_content(self):
        """Add content to a course"""
        selection = self.content_course_combo.get()
        if not selection:
            messagebox.showwarning("Warning", "Please select a course first")
            return

        course_id = int(selection.split(':')[0])

        dialog = tk.Toplevel(self.root)
        dialog.title("Add Course Content")
        dialog.geometry("500x500")

        fields = {}

        ttk.Label(dialog, text="Content Type:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        fields['type'] = ttk.Combobox(dialog,
                                     values=['Lecture', 'Reading', 'Video', 'Assignment', 'Quiz'],
                                     width=38, state='readonly')
        fields['type'].current(0)
        fields['type'].grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(dialog, text="Title:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        fields['title'] = ttk.Entry(dialog, width=40)
        fields['title'].grid(row=1, column=1, padx=5, pady=5)

        ttk.Label(dialog, text="Description:").grid(row=2, column=0, sticky=tk.NW, padx=5, pady=5)
        fields['description'] = tk.Text(dialog, width=40, height=5)
        fields['description'].grid(row=2, column=1, padx=5, pady=5)

        ttk.Label(dialog, text="Content URL:").grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        fields['url'] = ttk.Entry(dialog, width=40)
        fields['url'].grid(row=3, column=1, padx=5, pady=5)

        ttk.Button(dialog, text="Browse File",
                  command=lambda: self.browse_file(fields['url'])).grid(row=3, column=2, padx=5)

        ttk.Label(dialog, text="Content Order:").grid(row=4, column=0, sticky=tk.W, padx=5, pady=5)
        fields['order'] = ttk.Entry(dialog, width=40)
        fields['order'].insert(0, "0")
        fields['order'].grid(row=4, column=1, padx=5, pady=5)

        ttk.Label(dialog, text="Release Date (YYYY-MM-DD):").grid(row=5, column=0, sticky=tk.W, padx=5, pady=5)
        fields['release_date'] = ttk.Entry(dialog, width=40)
        fields['release_date'].insert(0, datetime.now().strftime('%Y-%m-%d'))
        fields['release_date'].grid(row=5, column=1, padx=5, pady=5)

        def save_content():
            try:
                title = fields['title'].get().strip()
                if not title:
                    messagebox.showerror("Error", "Title is required")
                    return

                content_id = LMSContentManager.add_content(
                    lms_course_id=course_id,
                    content_type=fields['type'].get(),
                    title=title,
                    description=fields['description'].get('1.0', tk.END).strip(),
                    content_url=fields['url'].get().strip(),
                    content_order=int(fields['order'].get()),
                    release_date=fields['release_date'].get().strip()
                )

                log_activity('create', 'lms_content', str(content_id),
                           {'course_id': course_id, 'title': title})

                messagebox.showinfo("Success",
                                  f"Content added successfully! ID: {content_id}")
                dialog.destroy()
                self.load_course_content()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to add content: {e}")

        ttk.Button(dialog, text="Add Content",
                  command=save_content).grid(row=6, column=0, columnspan=2, pady=20)

    def add_video_lecture(self):
        """Add a video lecture to content"""
        selected = self.content_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a content item first")
            return

        content_id = self.content_tree.item(selected[0])['values'][0]

        dialog = tk.Toplevel(self.root)
        dialog.title("Add Video Lecture")
        dialog.geometry("500x450")

        fields = {}

        ttk.Label(dialog, text="Video URL:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        fields['video_url'] = ttk.Entry(dialog, width=40)
        fields['video_url'].grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(dialog, text="Duration (minutes):").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        fields['duration'] = ttk.Entry(dialog, width=40)
        fields['duration'].insert(0, "0")
        fields['duration'].grid(row=1, column=1, padx=5, pady=5)

        ttk.Label(dialog, text="Thumbnail URL:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        fields['thumbnail'] = ttk.Entry(dialog, width=40)
        fields['thumbnail'].grid(row=2, column=1, padx=5, pady=5)

        ttk.Label(dialog, text="Transcript URL:").grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        fields['transcript'] = ttk.Entry(dialog, width=40)
        fields['transcript'].grid(row=3, column=1, padx=5, pady=5)

        ttk.Label(dialog, text="Video Quality:").grid(row=4, column=0, sticky=tk.W, padx=5, pady=5)
        fields['quality'] = ttk.Combobox(dialog,
                                        values=['360p', '480p', '720p', '1080p', '4K'],
                                        width=38, state='readonly')
        fields['quality'].current(2)
        fields['quality'].grid(row=4, column=1, padx=5, pady=5)

        def save_video():
            try:
                video_url = fields['video_url'].get().strip()
                if not video_url:
                    messagebox.showerror("Error", "Video URL is required")
                    return

                video_id = LMSContentManager.add_video_lecture(
                    content_id=content_id,
                    video_url=video_url,
                    duration_minutes=int(fields['duration'].get()),
                    thumbnail_url=fields['thumbnail'].get().strip(),
                    transcript_url=fields['transcript'].get().strip(),
                    video_quality=fields['quality'].get()
                )

                log_activity('create', 'lms_video_lecture', str(video_id),
                           {'content_id': content_id})

                messagebox.showinfo("Success",
                                  f"Video lecture added successfully! ID: {video_id}")
                dialog.destroy()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to add video: {e}")

        ttk.Button(dialog, text="Add Video",
                  command=save_video).grid(row=5, column=0, columnspan=2, pady=20)

    def browse_file(self, entry_widget):
        """Browse for file and update entry widget"""
        filename = filedialog.askopenfilename(title="Select File")
        if filename:
            entry_widget.delete(0, tk.END)
            entry_widget.insert(0, filename)

    # ======================== Discussion Methods ========================

    def load_forums(self, event=None):
        """Load discussion forums for selected course"""
        try:
            selection = self.discussion_course_combo.get()
            if not selection:
                return

            course_id = int(selection.split(':')[0])

            self.forums_tree.delete(*self.forums_tree.get_children())

            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT forum_id, topic, description, created_by, is_pinned, created_at
                    FROM lms_discussion_forums
                    WHERE lms_course_id = ?
                    ORDER BY is_pinned DESC, created_at DESC
                ''', (course_id,))

                for row in cursor.fetchall():
                    pinned = "Yes" if row[4] == 1 else "No"
                    self.forums_tree.insert('', tk.END, values=(
                        row[0], row[1], row[2], row[3], pinned, row[5]
                    ))

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load forums: {e}")

    def create_forum(self):
        """Create a new discussion forum"""
        selection = self.discussion_course_combo.get()
        if not selection:
            messagebox.showwarning("Warning", "Please select a course first")
            return

        course_id = int(selection.split(':')[0])

        dialog = tk.Toplevel(self.root)
        dialog.title("Create Discussion Forum")
        dialog.geometry("500x400")

        ttk.Label(dialog, text="Topic:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        topic_entry = ttk.Entry(dialog, width=40)
        topic_entry.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(dialog, text="Description:").grid(row=1, column=0, sticky=tk.NW, padx=5, pady=5)
        desc_text = tk.Text(dialog, width=40, height=8)
        desc_text.grid(row=1, column=1, padx=5, pady=5)

        pin_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(dialog, text="Pin this forum",
                       variable=pin_var).grid(row=2, column=1, sticky=tk.W, padx=5, pady=5)

        def save_forum():
            try:
                topic = topic_entry.get().strip()
                if not topic:
                    messagebox.showerror("Error", "Topic is required")
                    return

                forum_id = LMSDiscussionManager.create_forum(
                    lms_course_id=course_id,
                    topic=topic,
                    description=desc_text.get('1.0', tk.END).strip(),
                    created_by=self.user_id,
                    is_pinned=pin_var.get()
                )

                log_activity('create', 'lms_forum', str(forum_id),
                           {'course_id': course_id, 'topic': topic})

                messagebox.showinfo("Success",
                                  f"Forum created successfully! ID: {forum_id}")
                dialog.destroy()
                self.load_forums()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to create forum: {e}")

        ttk.Button(dialog, text="Create Forum",
                  command=save_forum).grid(row=3, column=0, columnspan=2, pady=20)

    def view_forum_posts(self):
        """View posts in a forum"""
        selected = self.forums_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a forum first")
            return

        forum_id = self.forums_tree.item(selected[0])['values'][0]

        try:
            posts = LMSDiscussionManager.get_forum_posts(forum_id)

            dialog = tk.Toplevel(self.root)
            dialog.title(f"Forum Posts - Forum {forum_id}")
            dialog.geometry("800x600")

            # Posts display
            posts_frame = ttk.LabelFrame(dialog, text="Posts", padding="10")
            posts_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            posts_text = scrolledtext.ScrolledText(posts_frame, wrap=tk.WORD,
                                                   width=80, height=30)
            posts_text.pack(fill=tk.BOTH, expand=True)

            for post in posts:
                posts_text.insert(tk.END,
                    f"Post ID: {post.get('post_id')}\n"
                    f"User: {post.get('user_id')}\n"
                    f"Date: {post.get('created_at')}\n"
                    f"Likes: {post.get('likes_count', 0)}\n"
                    f"Content: {post.get('content')}\n"
                    f"{'-' * 80}\n\n"
                )

            posts_text.config(state='disabled')

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load posts: {e}")

    def add_post(self):
        """Add a post to a forum"""
        selected = self.forums_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a forum first")
            return

        forum_id = self.forums_tree.item(selected[0])['values'][0]

        dialog = tk.Toplevel(self.root)
        dialog.title("Add Post")
        dialog.geometry("500x400")

        ttk.Label(dialog, text="Post Content:").grid(row=0, column=0, sticky=tk.NW, padx=5, pady=5)
        content_text = tk.Text(dialog, width=50, height=15)
        content_text.grid(row=0, column=1, padx=5, pady=5)

        def save_post():
            try:
                content = content_text.get('1.0', tk.END).strip()
                if not content:
                    messagebox.showerror("Error", "Post content is required")
                    return

                post_id = LMSDiscussionManager.add_post(
                    forum_id=forum_id,
                    user_id=self.user_id,
                    content=content
                )

                log_activity('create', 'lms_post', str(post_id),
                           {'forum_id': forum_id})

                messagebox.showinfo("Success", f"Post added successfully! ID: {post_id}")
                dialog.destroy()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to add post: {e}")

        ttk.Button(dialog, text="Add Post",
                  command=save_post).grid(row=1, column=0, columnspan=2, pady=20)

    # ======================== Quiz Methods ========================

    def load_quizzes(self, event=None):
        """Load quizzes for selected course"""
        try:
            selection = self.quiz_course_combo.get()
            if not selection:
                return

            course_id = int(selection.split(':')[0])

            self.quizzes_tree.delete(*self.quizzes_tree.get_children())

            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT quiz_id, title, duration_minutes, passing_score,
                           max_attempts, available_from, available_until
                    FROM lms_quizzes
                    WHERE lms_course_id = ?
                    ORDER BY created_at DESC
                ''', (course_id,))

                for row in cursor.fetchall():
                    self.quizzes_tree.insert('', tk.END, values=row)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load quizzes: {e}")

    def create_quiz(self):
        """Create a new quiz"""
        selection = self.quiz_course_combo.get()
        if not selection:
            messagebox.showwarning("Warning", "Please select a course first")
            return

        course_id = int(selection.split(':')[0])

        dialog = tk.Toplevel(self.root)
        dialog.title("Create Quiz")
        dialog.geometry("500x550")

        fields = {}

        ttk.Label(dialog, text="Quiz Title:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        fields['title'] = ttk.Entry(dialog, width=40)
        fields['title'].grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(dialog, text="Description:").grid(row=1, column=0, sticky=tk.NW, padx=5, pady=5)
        fields['description'] = tk.Text(dialog, width=40, height=5)
        fields['description'].grid(row=1, column=1, padx=5, pady=5)

        ttk.Label(dialog, text="Duration (minutes):").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        fields['duration'] = ttk.Entry(dialog, width=40)
        fields['duration'].insert(0, "60")
        fields['duration'].grid(row=2, column=1, padx=5, pady=5)

        ttk.Label(dialog, text="Passing Score (%):").grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        fields['passing_score'] = ttk.Entry(dialog, width=40)
        fields['passing_score'].insert(0, "70")
        fields['passing_score'].grid(row=3, column=1, padx=5, pady=5)

        ttk.Label(dialog, text="Max Attempts:").grid(row=4, column=0, sticky=tk.W, padx=5, pady=5)
        fields['max_attempts'] = ttk.Entry(dialog, width=40)
        fields['max_attempts'].insert(0, "1")
        fields['max_attempts'].grid(row=4, column=1, padx=5, pady=5)

        ttk.Label(dialog, text="Available From (YYYY-MM-DD):").grid(row=5, column=0, sticky=tk.W, padx=5, pady=5)
        fields['available_from'] = ttk.Entry(dialog, width=40)
        fields['available_from'].insert(0, datetime.now().strftime('%Y-%m-%d'))
        fields['available_from'].grid(row=5, column=1, padx=5, pady=5)

        ttk.Label(dialog, text="Available Until (YYYY-MM-DD):").grid(row=6, column=0, sticky=tk.W, padx=5, pady=5)
        fields['available_until'] = ttk.Entry(dialog, width=40)
        fields['available_until'].grid(row=6, column=1, padx=5, pady=5)

        def save_quiz():
            try:
                title = fields['title'].get().strip()
                if not title:
                    messagebox.showerror("Error", "Quiz title is required")
                    return

                quiz_id = LMSQuizManager.create_quiz(
                    lms_course_id=course_id,
                    title=title,
                    description=fields['description'].get('1.0', tk.END).strip(),
                    duration_minutes=int(fields['duration'].get()),
                    passing_score=float(fields['passing_score'].get()),
                    max_attempts=int(fields['max_attempts'].get()),
                    available_from=fields['available_from'].get().strip(),
                    available_until=fields['available_until'].get().strip()
                )

                log_activity('create', 'lms_quiz', str(quiz_id),
                           {'course_id': course_id, 'title': title})

                messagebox.showinfo("Success",
                                  f"Quiz created successfully! ID: {quiz_id}")
                dialog.destroy()
                self.load_quizzes()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to create quiz: {e}")

        ttk.Button(dialog, text="Create Quiz",
                  command=save_quiz).grid(row=7, column=0, columnspan=2, pady=20)

    def add_quiz_questions(self):
        """Add questions to a quiz"""
        selected = self.quizzes_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a quiz first")
            return

        quiz_id = self.quizzes_tree.item(selected[0])['values'][0]

        dialog = tk.Toplevel(self.root)
        dialog.title(f"Add Questions to Quiz {quiz_id}")
        dialog.geometry("600x550")

        ttk.Label(dialog, text="Question Text:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        question_text = tk.Text(dialog, width=50, height=5)
        question_text.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(dialog, text="Question Type:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        type_combo = ttk.Combobox(dialog,
                                 values=['Multiple Choice', 'True/False', 'Short Answer', 'Essay'],
                                 width=48, state='readonly')
        type_combo.current(0)
        type_combo.grid(row=1, column=1, padx=5, pady=5)

        ttk.Label(dialog, text="Correct Answer:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        answer_entry = ttk.Entry(dialog, width=50)
        answer_entry.grid(row=2, column=1, padx=5, pady=5)

        ttk.Label(dialog, text="Points:").grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        points_entry = ttk.Entry(dialog, width=50)
        points_entry.insert(0, "1")
        points_entry.grid(row=3, column=1, padx=5, pady=5)

        ttk.Label(dialog, text="Options (JSON):").grid(row=4, column=0, sticky=tk.NW, padx=5, pady=5)
        options_text = tk.Text(dialog, width=50, height=5)
        options_text.insert('1.0', '["Option A", "Option B", "Option C", "Option D"]')
        options_text.grid(row=4, column=1, padx=5, pady=5)

        ttk.Label(dialog, text="Explanation:").grid(row=5, column=0, sticky=tk.NW, padx=5, pady=5)
        explanation_text = tk.Text(dialog, width=50, height=5)
        explanation_text.grid(row=5, column=1, padx=5, pady=5)

        def save_question():
            try:
                text = question_text.get('1.0', tk.END).strip()
                if not text:
                    messagebox.showerror("Error", "Question text is required")
                    return

                question_id = LMSQuizManager.add_question(
                    quiz_id=quiz_id,
                    question_text=text,
                    question_type=type_combo.get(),
                    correct_answer=answer_entry.get().strip(),
                    points=int(points_entry.get()),
                    options=options_text.get('1.0', tk.END).strip(),
                    explanation=explanation_text.get('1.0', tk.END).strip()
                )

                messagebox.showinfo("Success", f"Question added! ID: {question_id}")
                question_text.delete('1.0', tk.END)
                answer_entry.delete(0, tk.END)
                explanation_text.delete('1.0', tk.END)

            except Exception as e:
                messagebox.showerror("Error", f"Failed to add question: {e}")

        ttk.Button(dialog, text="Add Question",
                  command=save_question).grid(row=6, column=0, columnspan=2, pady=20)

    def view_quiz_submissions(self):
        """View quiz submissions"""
        selected = self.quizzes_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a quiz first")
            return

        quiz_id = self.quizzes_tree.item(selected[0])['values'][0]

        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT submission_id, student_id, attempt_number, score,
                           total_points, time_taken_minutes, submitted_at
                    FROM lms_quiz_submissions
                    WHERE quiz_id = ?
                    ORDER BY submitted_at DESC
                ''', (quiz_id,))

                submissions = cursor.fetchall()

            dialog = tk.Toplevel(self.root)
            dialog.title(f"Quiz Submissions - Quiz {quiz_id}")
            dialog.geometry("900x600")

            # Submissions display
            list_frame = ttk.LabelFrame(dialog, text="Submissions", padding="10")
            list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            columns = ('Submission ID', 'Student ID', 'Attempt', 'Score',
                      'Total Points', 'Time (min)', 'Submitted At')
            tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=20)

            for col in columns:
                tree.heading(col, text=col)
                tree.column(col, width=120)

            for submission in submissions:
                tree.insert('', tk.END, values=submission)

            scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=tree.yview)
            tree.configure(yscrollcommand=scrollbar.set)

            tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load submissions: {e}")

    # ======================== Gradebook Methods ========================

    def load_student_grades(self):
        """Load grades for a student in a course"""
        try:
            selection = self.gradebook_course_combo.get()
            student_id = self.gradebook_student_entry.get().strip()

            if not selection or not student_id:
                messagebox.showwarning("Warning", "Please select a course and enter student ID")
                return

            course_id = int(selection.split(':')[0])

            self.gradebook_tree.delete(*self.gradebook_tree.get_children())

            grades = LMSGradebookManager.get_student_grades(course_id, student_id)

            for grade in grades:
                self.gradebook_tree.insert('', tk.END, values=(
                    grade.get('entry_id'),
                    grade.get('student_id'),
                    grade.get('assignment_type'),
                    grade.get('assignment_id'),
                    grade.get('score'),
                    grade.get('max_score'),
                    grade.get('weight'),
                    grade.get('graded_by'),
                    grade.get('graded_at')
                ))

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load grades: {e}")

    def add_grade(self):
        """Add a grade entry to gradebook"""
        selection = self.gradebook_course_combo.get()
        if not selection:
            messagebox.showwarning("Warning", "Please select a course first")
            return

        course_id = int(selection.split(':')[0])

        dialog = tk.Toplevel(self.root)
        dialog.title("Add Grade Entry")
        dialog.geometry("500x500")

        fields = {}

        ttk.Label(dialog, text="Student ID:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        fields['student_id'] = ttk.Entry(dialog, width=40)
        fields['student_id'].grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(dialog, text="Assignment Type:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        fields['assignment_type'] = ttk.Combobox(dialog,
                                                values=['Quiz', 'Assignment', 'Exam', 'Project', 'Participation'],
                                                width=38, state='readonly')
        fields['assignment_type'].current(0)
        fields['assignment_type'].grid(row=1, column=1, padx=5, pady=5)

        ttk.Label(dialog, text="Assignment ID:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        fields['assignment_id'] = ttk.Entry(dialog, width=40)
        fields['assignment_id'].grid(row=2, column=1, padx=5, pady=5)

        ttk.Label(dialog, text="Score:").grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        fields['score'] = ttk.Entry(dialog, width=40)
        fields['score'].grid(row=3, column=1, padx=5, pady=5)

        ttk.Label(dialog, text="Max Score:").grid(row=4, column=0, sticky=tk.W, padx=5, pady=5)
        fields['max_score'] = ttk.Entry(dialog, width=40)
        fields['max_score'].grid(row=4, column=1, padx=5, pady=5)

        ttk.Label(dialog, text="Weight:").grid(row=5, column=0, sticky=tk.W, padx=5, pady=5)
        fields['weight'] = ttk.Entry(dialog, width=40)
        fields['weight'].insert(0, "1.0")
        fields['weight'].grid(row=5, column=1, padx=5, pady=5)

        ttk.Label(dialog, text="Feedback:").grid(row=6, column=0, sticky=tk.NW, padx=5, pady=5)
        fields['feedback'] = tk.Text(dialog, width=40, height=5)
        fields['feedback'].grid(row=6, column=1, padx=5, pady=5)

        def save_grade():
            try:
                student_id = fields['student_id'].get().strip()
                if not student_id:
                    messagebox.showerror("Error", "Student ID is required")
                    return

                entry_id = LMSGradebookManager.add_grade_entry(
                    lms_course_id=course_id,
                    student_id=student_id,
                    assignment_type=fields['assignment_type'].get(),
                    assignment_id=int(fields['assignment_id'].get()),
                    score=float(fields['score'].get()),
                    max_score=float(fields['max_score'].get()),
                    weight=float(fields['weight'].get()),
                    feedback=fields['feedback'].get('1.0', tk.END).strip(),
                    graded_by=self.user_id
                )

                log_activity('create', 'lms_grade', str(entry_id),
                           {'course_id': course_id, 'student_id': student_id})

                messagebox.showinfo("Success",
                                  f"Grade added successfully! Entry ID: {entry_id}")
                dialog.destroy()
                self.load_student_grades()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to add grade: {e}")

        ttk.Button(dialog, text="Add Grade",
                  command=save_grade).grid(row=7, column=0, columnspan=2, pady=20)

    def calculate_course_grade(self):
        """Calculate overall course grade for a student"""
        try:
            selection = self.gradebook_course_combo.get()
            student_id = self.gradebook_student_entry.get().strip()

            if not selection or not student_id:
                messagebox.showwarning("Warning", "Please select a course and enter student ID")
                return

            course_id = int(selection.split(':')[0])

            grade = LMSGradebookManager.calculate_course_grade(course_id, student_id)

            messagebox.showinfo("Course Grade",
                              f"Overall Grade for {student_id}:\n{grade:.2f}%")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to calculate grade: {e}")

    # ======================== Student Methods ========================

    def load_student_courses(self):
        """Load courses enrolled by current student"""
        try:
            if not hasattr(self, 'student_courses_tree'):
                return

            self.student_courses_tree.delete(*self.student_courses_tree.get_children())

            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT e.lms_course_id, c.module_code, c.instructor_id,
                           e.progress_percentage, e.last_accessed
                    FROM lms_student_enrollment e
                    JOIN lms_courses c ON e.lms_course_id = c.lms_course_id
                    WHERE e.student_id = ? AND e.is_active = 1 AND c.is_published = 1
                    ORDER BY e.enrollment_date DESC
                ''', (self.user_id,))

                for row in cursor.fetchall():
                    self.student_courses_tree.insert('', tk.END, values=row)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load enrolled courses: {e}")

    def view_student_materials(self):
        """View course materials for enrolled course"""
        selected = self.student_courses_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a course first")
            return

        course_id = self.student_courses_tree.item(selected[0])['values'][0]

        try:
            content_list = LMSContentManager.get_course_content(course_id)

            dialog = tk.Toplevel(self.root)
            dialog.title(f"Course Materials - Course {course_id}")
            dialog.geometry("900x600")

            # Materials display
            list_frame = ttk.LabelFrame(dialog, text="Course Materials", padding="10")
            list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            columns = ('Content ID', 'Type', 'Title', 'Description', 'Release Date')
            tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=20)

            for col in columns:
                tree.heading(col, text=col)
                width = 250 if col in ['Title', 'Description'] else 100
                tree.column(col, width=width)

            for content in content_list:
                tree.insert('', tk.END, values=(
                    content.get('content_id'),
                    content.get('content_type'),
                    content.get('title'),
                    content.get('description', '')[:100],
                    content.get('release_date', '')
                ))

            scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=tree.yview)
            tree.configure(yscrollcommand=scrollbar.set)

            tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load materials: {e}")

    def view_student_grades(self):
        """View grades for current student in enrolled course"""
        selected = self.student_courses_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a course first")
            return

        course_id = self.student_courses_tree.item(selected[0])['values'][0]

        try:
            grades = LMSGradebookManager.get_student_grades(course_id, self.user_id)
            overall_grade = LMSGradebookManager.calculate_course_grade(course_id, self.user_id)

            dialog = tk.Toplevel(self.root)
            dialog.title(f"My Grades - Course {course_id}")
            dialog.geometry("900x600")

            # Overall grade display
            overall_frame = ttk.LabelFrame(dialog, text="Overall Grade", padding="10")
            overall_frame.pack(fill=tk.X, padx=10, pady=10)

            ttk.Label(overall_frame,
                     text=f"Course Grade: {overall_grade:.2f}%",
                     font=('Arial', 14, 'bold')).pack(pady=5)

            # Individual grades
            list_frame = ttk.LabelFrame(dialog, text="Individual Grades", padding="10")
            list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            columns = ('Assignment Type', 'Assignment ID', 'Score', 'Max Score',
                      'Weight', 'Graded By', 'Date')
            tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=15)

            for col in columns:
                tree.heading(col, text=col)
                tree.column(col, width=120)

            for grade in grades:
                tree.insert('', tk.END, values=(
                    grade.get('assignment_type'),
                    grade.get('assignment_id'),
                    grade.get('score'),
                    grade.get('max_score'),
                    grade.get('weight'),
                    grade.get('graded_by'),
                    grade.get('graded_at')
                ))

            scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=tree.yview)
            tree.configure(yscrollcommand=scrollbar.set)

            tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load grades: {e}")


def launch_lms_gui(root, auth):
    """Launch the LMS GUI"""
    try:
        if not auth or not hasattr(auth, 'current_user') or not auth.current_user:
            messagebox.showerror("Error", "You must be logged in to access the Learning Management System.")
            return

        LMSGUI(root, auth)

    except Exception as e:
        messagebox.showerror("Error", f"Failed to launch LMS: {e}")


__all__ = ['LMSGUI', 'launch_lms_gui']
