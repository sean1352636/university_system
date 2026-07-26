import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog
from education_system.systems.university.infrastructure.database.db import sqlite3
from education_system.systems.university.infrastructure import paths
from datetime import datetime, timedelta
import hashlib
import json
import sys
import os
import logging
from typing import Dict, List, Optional, Tuple, Any
import threading
import queue
from education_system.systems.university.infrastructure.email.template_utils import render_template
from education_system.systems.university.infrastructure.auth import UserAuth
from education_system.systems.university.infrastructure.shared_context import get_auth

# Import i18n for multi-language support
from education_system.systems.university.infrastructure.i18n import (
    init_i18n,
    get_text as _t,
    set_language,
    get_current_language,
    get_current_language_name,
    get_available_languages,
)
from education_system.systems.university.infrastructure.utils.gui_language_selector import show_gui_language_selector

# Use centralized path configuration
DEFAULT_DB_PATH = paths.DEFAULT_DB_PATH

# Import finance integration for student finance account payments
try:
    from education_system.systems.university.infrastructure.utils.finance_integration import (
        process_student_finance_account_payment,
        get_student_finance_account_balance,
        get_student_info,
        LOW_BALANCE_THRESHOLD
    )
    FINANCE_ACCOUNT_AVAILABLE = True
except ImportError:
    FINANCE_ACCOUNT_AVAILABLE = False
    print("Warning: Student finance account integration not available")

try:
    # Import CLI components to maintain backwards compatibility. If available,
    # include the full database initializer so the GUI can create the
    # comprehensive schema when running stand‑alone.
    from education_system.systems.university.infrastructure.database.db import get_connection
    from education_system.systems.university.domain.pastoral.student_life.student_union.administration.student_union_core import init_student_union_db
    CLI_AVAILABLE = True
except (ImportError, ModuleNotFoundError):
    print("Warning: CLI system not available. Some features may be limited.")
    student_union_cli = None
    init_student_union_db = None
    CLI_AVAILABLE = False


class WellnessResourcesDialog:
    """Dialog for viewing wellness resources"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Wellness Resources")
        self.dialog.geometry("800x700")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Title
        title_label = ttk.Label(main_frame, text="Wellness Resources", font=('Arial', 14, 'bold'))
        title_label.pack(pady=(0, 10))

        # Create notebook for different resource categories
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill='both', expand=True, pady=(0, 10))

        # Mental Health tab
        mental_health_frame = ttk.Frame(notebook)
        notebook.add(mental_health_frame, text="Mental Health")
        self.create_mental_health_tab(mental_health_frame)

        # Counseling Services tab
        counseling_frame = ttk.Frame(notebook)
        notebook.add(counseling_frame, text="Counseling")
        self.create_counseling_tab(counseling_frame)

        # Fitness Programs tab
        fitness_frame = ttk.Frame(notebook)
        notebook.add(fitness_frame, text="Fitness")
        self.create_fitness_tab(fitness_frame)

        # Nutrition tab
        nutrition_frame = ttk.Frame(notebook)
        notebook.add(nutrition_frame, text="Nutrition")
        self.create_nutrition_tab(nutrition_frame)

        # Stress Management tab
        stress_frame = ttk.Frame(notebook)
        notebook.add(stress_frame, text="Stress Management")
        self.create_stress_tab(stress_frame)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side='right')

    def _ensure_wellness_tables(self, conn):
        """Ensure wellness_resources table exists"""
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS wellness_resources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                contact TEXT,
                url TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            )
        ''')
        conn.commit()

    def _load_resources_by_category(self, category):
        """Load wellness resources from DB for a given category"""
        resources = []
        conn = None
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            self._ensure_wellness_tables(conn)
            cursor = conn.cursor()
            cursor.execute(
                'SELECT id, title, description, contact, url FROM wellness_resources WHERE category = ? ORDER BY title',
                (category,))
            resources = cursor.fetchall()
        except sqlite3.Error:
            pass
        finally:
            if conn:
                conn.close()
        return resources

    def _add_resource_dialog(self, category, refresh_callback):
        """Open a dialog to add a new wellness resource"""
        add_win = tk.Toplevel(self.dialog)
        add_win.title(f"Add {category} Resource")
        add_win.geometry("500x400")
        add_win.transient(self.dialog)
        add_win.grab_set()

        frame = ttk.Frame(add_win)
        frame.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(frame, text="Title:").pack(anchor='w', pady=(0, 2))
        title_var = tk.StringVar()
        ttk.Entry(frame, textvariable=title_var, width=50).pack(fill='x', pady=(0, 8))

        ttk.Label(frame, text="Description:").pack(anchor='w', pady=(0, 2))
        desc_text = scrolledtext.ScrolledText(frame, height=6, wrap=tk.WORD)
        desc_text.pack(fill='both', expand=True, pady=(0, 8))

        ttk.Label(frame, text="Contact (phone/email):").pack(anchor='w', pady=(0, 2))
        contact_var = tk.StringVar()
        ttk.Entry(frame, textvariable=contact_var, width=50).pack(fill='x', pady=(0, 8))

        ttk.Label(frame, text="URL (optional):").pack(anchor='w', pady=(0, 2))
        url_var = tk.StringVar()
        ttk.Entry(frame, textvariable=url_var, width=50).pack(fill='x', pady=(0, 8))

        def save():
            title = title_var.get().strip()
            desc = desc_text.get(1.0, tk.END).strip()
            contact = contact_var.get().strip()
            url = url_var.get().strip()
            if not title:
                messagebox.showwarning("Warning", "Title is required.", parent=add_win)
                return
            conn = None
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                self._ensure_wellness_tables(conn)
                cursor = conn.cursor()
                cursor.execute(
                    'INSERT INTO wellness_resources (category, title, description, contact, url) VALUES (?, ?, ?, ?, ?)',
                    (category, title, desc, contact, url))
                conn.commit()
                messagebox.showinfo("Success", "Resource added successfully.", parent=add_win)
                add_win.destroy()
                refresh_callback()
            except sqlite3.Error as e:
                messagebox.showerror("Error", f"Failed to add resource: {e}", parent=add_win)
            finally:
                if conn:
                    conn.close()

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill='x', pady=(5, 0))
        ttk.Button(btn_frame, text="Save", command=save).pack(side='left', padx=(0, 10))
        ttk.Button(btn_frame, text="Cancel", command=add_win.destroy).pack(side='left')

    def _is_admin(self):
        """Check if current user has admin privileges"""
        try:
            role = self.auth.current_user.get('role', '').lower()
            return role in ('admin', 'superadmin', 'administrator', 'staff')
        except (AttributeError, TypeError):
            return False

    def create_mental_health_tab(self, parent):
        """Create mental health resources tab - DB-backed"""
        container = ttk.Frame(parent)
        container.pack(fill='both', expand=True, padx=5, pady=5)

        # Default content for when DB is empty
        defaults = [
            ("National Suicide Prevention Lifeline", "24/7 crisis support for people in distress", "1-800-273-8255", "https://suicidepreventionlifeline.org"),
            ("Crisis Text Line", "24/7 text-based crisis support", "Text HOME to 741741", "https://www.crisistextline.org"),
            ("SAMHSA National Helpline", "Free treatment referral and information service", "1-800-662-4357", "https://www.samhsa.gov"),
            ("Student Counseling Center", "On-campus professional counseling services", "(555) 123-4567", ""),
            ("Campus Health Services", "General health and mental health support", "(555) 123-4568", ""),
            ("MindBeacon", "Online cognitive behavioral therapy platform", "", "https://www.mindbeacon.com"),
            ("Headspace", "Meditation and mindfulness app (free for students)", "", "https://www.headspace.com"),
            ("7 Cups", "Free emotional support chat with trained listeners", "", "https://www.7cups.com"),
        ]

        # Treeview for resources
        tree_frame = ttk.Frame(container)
        tree_frame.pack(fill='both', expand=True, pady=(0, 5))

        columns = ('Title', 'Description', 'Contact', 'URL')
        tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=10)
        for col in columns:
            tree.heading(col, text=col)
            if col == 'Description':
                tree.column(col, width=300)
            elif col == 'Title':
                tree.column(col, width=200)
            else:
                tree.column(col, width=150)

        vsb = ttk.Scrollbar(tree_frame, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')

        # Info label
        info_label = ttk.Label(container, text="Remember: It's okay to ask for help. Taking care of your mental health is just as important as your physical health.",
                               font=('Arial', 9, 'italic'), wraplength=700)
        info_label.pack(pady=(0, 5))

        def load():
            for item in tree.get_children():
                tree.delete(item)
            resources = self._load_resources_by_category('Mental Health')
            if resources:
                for r in resources:
                    tree.insert('', 'end', values=(r[1], r[2] or '', r[3] or '', r[4] or ''))
            else:
                for title, desc, contact, url in defaults:
                    tree.insert('', 'end', values=(title, desc, contact, url))

        load()

        # Admin add button
        if self._is_admin():
            ttk.Button(container, text="Add Resource",
                       command=lambda: self._add_resource_dialog('Mental Health', load)).pack(anchor='e', pady=(5, 0))

    def create_counseling_tab(self, parent):
        """Create counseling services tab - DB-backed"""
        container = ttk.Frame(parent)
        container.pack(fill='both', expand=True, padx=5, pady=5)

        defaults = [
            ("Individual Counseling", "One-on-one sessions with a licensed counselor", "(555) 123-4567", ""),
            ("Group Therapy", "Facilitated group sessions on various topics", "(555) 123-4567", ""),
            ("Couples Counseling", "Relationship support for student couples", "(555) 123-4567", ""),
            ("Crisis Intervention", "Immediate support for students in crisis - 24/7", "(555) 123-HELP", ""),
            ("Psychiatric Services", "Medication management and psychiatric evaluation", "(555) 123-4567", ""),
        ]

        # Info section
        info_frame = ttk.LabelFrame(container, text="Counseling Center Information")
        info_frame.pack(fill='x', pady=(0, 10))

        info_text = ("Location: Student Services Building, 2nd Floor  |  "
                     "Hours: Mon-Fri 8:00 AM - 6:00 PM  |  "
                     "Walk-in: Mon-Fri 9:00 AM - 11:00 AM  |  "
                     "Email: counseling@university.edu")
        ttk.Label(info_frame, text=info_text, wraplength=700, font=('Arial', 9)).pack(padx=10, pady=8)

        # Counselor availability Treeview
        avail_frame = ttk.LabelFrame(container, text="Services & Availability")
        avail_frame.pack(fill='both', expand=True, pady=(0, 5))

        columns = ('Service', 'Description', 'Contact', 'URL')
        tree = ttk.Treeview(avail_frame, columns=columns, show='headings', height=8)
        for col in columns:
            tree.heading(col, text=col)
            if col == 'Description':
                tree.column(col, width=300)
            elif col == 'Service':
                tree.column(col, width=180)
            else:
                tree.column(col, width=130)

        vsb = ttk.Scrollbar(avail_frame, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')

        ttk.Label(container, text="All counseling sessions are confidential and protected by HIPAA. Most student health plans cover counseling services.",
                  font=('Arial', 9, 'italic'), wraplength=700).pack(pady=(0, 5))

        def load():
            for item in tree.get_children():
                tree.delete(item)
            resources = self._load_resources_by_category('Counseling')
            if resources:
                for r in resources:
                    tree.insert('', 'end', values=(r[1], r[2] or '', r[3] or '', r[4] or ''))
            else:
                for title, desc, contact, url in defaults:
                    tree.insert('', 'end', values=(title, desc, contact, url))

        load()

        if self._is_admin():
            ttk.Button(container, text="Add Resource",
                       command=lambda: self._add_resource_dialog('Counseling', load)).pack(anchor='e', pady=(5, 0))

    def create_fitness_tab(self, parent):
        """Create fitness programs tab - DB-backed"""
        container = ttk.Frame(parent)
        container.pack(fill='both', expand=True, padx=5, pady=5)

        defaults = [
            ("Yoga", "Monday/Wednesday 7:00 PM - Group fitness studio", "Recreation Building", ""),
            ("Spin Class", "Tuesday/Thursday 6:00 PM - Cycling studio", "Recreation Building", ""),
            ("Zumba", "Wednesday/Friday 5:30 PM - Group fitness studio", "Recreation Building", ""),
            ("Boot Camp", "Saturday 9:00 AM - Outdoor fitness area", "Recreation Building", ""),
            ("Pilates", "Tuesday/Thursday 7:00 PM - Group fitness studio", "Recreation Building", ""),
            ("Personal Training", "One-on-one sessions available by appointment", "Recreation Office", ""),
            ("Intramural Sports", "Basketball, Soccer, Volleyball - sign up at Recreation Office", "Recreation Office", ""),
        ]

        # Facility info
        info_frame = ttk.LabelFrame(container, text="Campus Fitness Center")
        info_frame.pack(fill='x', pady=(0, 10))

        info_text = ("Location: Recreation Building  |  Hours: Mon-Sun 6:00 AM - 11:00 PM  |  "
                     "Membership: FREE for all students\n"
                     "Facilities: Weight room, Cardio equipment, Group fitness studio, Indoor track, "
                     "Basketball courts, Swimming pool")
        ttk.Label(info_frame, text=info_text, wraplength=700, font=('Arial', 9)).pack(padx=10, pady=8)

        # Schedule Treeview
        sched_frame = ttk.LabelFrame(container, text="Fitness Classes & Programs")
        sched_frame.pack(fill='both', expand=True, pady=(0, 5))

        columns = ('Class/Program', 'Schedule/Description', 'Location', 'URL')
        tree = ttk.Treeview(sched_frame, columns=columns, show='headings', height=8)
        for col in columns:
            tree.heading(col, text=col)
            if col == 'Schedule/Description':
                tree.column(col, width=300)
            elif col == 'Class/Program':
                tree.column(col, width=150)
            else:
                tree.column(col, width=130)

        vsb = ttk.Scrollbar(sched_frame, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')

        def load():
            for item in tree.get_children():
                tree.delete(item)
            resources = self._load_resources_by_category('Fitness')
            if resources:
                for r in resources:
                    tree.insert('', 'end', values=(r[1], r[2] or '', r[3] or '', r[4] or ''))
            else:
                for title, desc, contact, url in defaults:
                    tree.insert('', 'end', values=(title, desc, contact, url))

        load()

        if self._is_admin():
            ttk.Button(container, text="Add Resource",
                       command=lambda: self._add_resource_dialog('Fitness', load)).pack(anchor='e', pady=(5, 0))

    def create_nutrition_tab(self, parent):
        """Create nutrition resources tab - DB-backed"""
        container = ttk.Frame(parent)
        container.pack(fill='both', expand=True, padx=5, pady=5)

        defaults = [
            ("Individual Nutrition Counseling", "One-on-one sessions with a registered dietitian", "(555) 123-4570", ""),
            ("Meal Planning Assistance", "Help creating balanced, budget-friendly meal plans", "(555) 123-4570", ""),
            ("Sports Nutrition Guidance", "Optimize performance through proper nutrition", "(555) 123-4570", ""),
            ("Eating Disorder Support", "Confidential support and referrals for eating disorders", "(555) 123-4570", ""),
            ("Cooking Demonstrations", "Hands-on workshops for healthy cooking techniques", "nutrition@university.edu", ""),
            ("Food Pantry", "Free groceries for students in need - Student Union Room 105, Mon-Fri 10AM-4PM", "Student Union Room 105", ""),
        ]

        # Info section
        info_frame = ttk.LabelFrame(container, text="Campus Nutritionist")
        info_frame.pack(fill='x', pady=(0, 10))

        info_text = ("Location: Student Health Center  |  Phone: (555) 123-4570  |  "
                     "Email: nutrition@university.edu\n"
                     "Dining halls offer nutritional info, vegetarian/vegan options, "
                     "gluten-free and allergen-free meals, and customizable meal plans.")
        ttk.Label(info_frame, text=info_text, wraplength=700, font=('Arial', 9)).pack(padx=10, pady=8)

        # Resources Treeview
        res_frame = ttk.LabelFrame(container, text="Nutrition Services & Programs")
        res_frame.pack(fill='both', expand=True, pady=(0, 5))

        columns = ('Service', 'Description', 'Contact', 'URL')
        tree = ttk.Treeview(res_frame, columns=columns, show='headings', height=8)
        for col in columns:
            tree.heading(col, text=col)
            if col == 'Description':
                tree.column(col, width=300)
            elif col == 'Service':
                tree.column(col, width=180)
            else:
                tree.column(col, width=130)

        vsb = ttk.Scrollbar(res_frame, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')

        def load():
            for item in tree.get_children():
                tree.delete(item)
            resources = self._load_resources_by_category('Nutrition')
            if resources:
                for r in resources:
                    tree.insert('', 'end', values=(r[1], r[2] or '', r[3] or '', r[4] or ''))
            else:
                for title, desc, contact, url in defaults:
                    tree.insert('', 'end', values=(title, desc, contact, url))

        load()

        if self._is_admin():
            ttk.Button(container, text="Add Resource",
                       command=lambda: self._add_resource_dialog('Nutrition', load)).pack(anchor='e', pady=(5, 0))

    def create_stress_tab(self, parent):
        """Create stress management tab - DB-backed"""
        container = ttk.Frame(parent)
        container.pack(fill='both', expand=True, padx=5, pady=5)

        defaults = [
            ("Deep Breathing Exercises", "Guided breathing techniques for immediate stress relief", "", ""),
            ("Progressive Muscle Relaxation", "Systematic tension and release exercises for full-body relaxation", "", ""),
            ("Mindfulness Meditation", "Guided meditation sessions - Meditation Room, Student Union 3rd Floor", "", ""),
            ("Academic Support Center", "Tutoring, study skills workshops, and test anxiety support groups", "(555) 123-4571", ""),
            ("Calm App", "Meditation and sleep app - free for students", "", "https://www.calm.com"),
            ("Headspace App", "Mindfulness and meditation app - free for students", "", "https://www.headspace.com"),
            ("Sleep Cycle App", "Sleep tracking and smart alarm - free for students", "", "https://www.sleepcycle.com"),
            ("Stress Management Workshop", "Weekly workshops on coping strategies and time management", "(555) 123-4571", ""),
        ]

        # Tips section
        tips_frame = ttk.LabelFrame(container, text="Quick Tips")
        tips_frame.pack(fill='x', pady=(0, 10))

        tips_text = ("Use a planner  |  Break tasks into smaller steps  |  "
                     "Prioritize and learn to say no  |  Schedule breaks  |  "
                     "Get 7-9 hours of sleep  |  Exercise regularly  |  Maintain social connections")
        ttk.Label(tips_frame, text=tips_text, wraplength=700, font=('Arial', 9)).pack(padx=10, pady=8)

        # Resources Treeview
        res_frame = ttk.LabelFrame(container, text="Stress Management Resources & Workshops")
        res_frame.pack(fill='both', expand=True, pady=(0, 5))

        columns = ('Resource', 'Description', 'Contact', 'URL')
        tree = ttk.Treeview(res_frame, columns=columns, show='headings', height=8)
        for col in columns:
            tree.heading(col, text=col)
            if col == 'Description':
                tree.column(col, width=300)
            elif col == 'Resource':
                tree.column(col, width=180)
            else:
                tree.column(col, width=130)

        vsb = ttk.Scrollbar(res_frame, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')

        ttk.Label(container, text="Campus quiet spaces: Meditation Room (Student Union 3rd Floor), Library quiet areas, Nature Trails (behind Recreation Building)",
                  font=('Arial', 9, 'italic'), wraplength=700).pack(pady=(0, 5))

        def load():
            for item in tree.get_children():
                tree.delete(item)
            resources = self._load_resources_by_category('Stress Management')
            if resources:
                for r in resources:
                    tree.insert('', 'end', values=(r[1], r[2] or '', r[3] or '', r[4] or ''))
            else:
                for title, desc, contact, url in defaults:
                    tree.insert('', 'end', values=(title, desc, contact, url))

        load()

        if self._is_admin():
            ttk.Button(container, text="Add Resource",
                       command=lambda: self._add_resource_dialog('Stress Management', load)).pack(anchor='e', pady=(5, 0))


class CrisisResourcesDialog:
    """Immediate crisis resources and support"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Crisis Resources - IMMEDIATE HELP")
        self.dialog.geometry("900x700")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        # Red background for urgency
        self.dialog.configure(bg='#FFE6E6')

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        # Emergency header
        emergency_frame = tk.Frame(main_frame, bg='#FF0000', relief='raised', bd=3)
        emergency_frame.pack(fill='x', pady=(0, 20))

        ttk.Label(emergency_frame, text="🆘 CRISIS RESOURCES - IMMEDIATE HELP",
                 font=('Arial', 16, 'bold'), background='#FF0000',
                 foreground='white').pack(pady=15)

        # If in immediate danger
        danger_frame = ttk.LabelFrame(main_frame, text="⚠️ IF YOU ARE IN IMMEDIATE DANGER")
        danger_frame.pack(fill='x', pady=(0, 15))

        danger_text = """CALL 911 IMMEDIATELY
or go to the nearest emergency room

Campus Police: (555) 123-9111 (24/7)
"""
        ttk.Label(danger_frame, text=danger_text, font=('Arial', 12, 'bold'),
                 foreground='red', justify='center').pack(padx=20, pady=15)

        # Quick access buttons
        quick_frame = ttk.LabelFrame(main_frame, text="Quick Access - Click to Call/Text")
        quick_frame.pack(fill='x', pady=(0, 15))

        buttons_grid = ttk.Frame(quick_frame)
        buttons_grid.pack(fill='x', padx=10, pady=10)

        crisis_contacts = [
            ("National Suicide Prevention Lifeline", "1-800-273-8255", "24/7 Support"),
            ("Crisis Text Line", "Text HOME to 741741", "24/7 Text Support"),
            ("Campus Counseling Crisis", "(555) 123-HELP", "After Hours"),
            ("NAMI Helpline", "1-800-950-6264", "Mon-Fri 10AM-6PM")
        ]

        for i, (name, number, hours) in enumerate(crisis_contacts):
            btn_frame = ttk.Frame(buttons_grid)
            btn_frame.grid(row=i//2, column=i%2, padx=10, pady=5, sticky='ew')

            ttk.Label(btn_frame, text=name, font=('Arial', 10, 'bold')).pack(anchor='w')
            ttk.Label(btn_frame, text=number, font=('Arial', 11),
                     foreground='blue').pack(anchor='w')
            ttk.Label(btn_frame, text=hours, font=('Arial', 9, 'italic')).pack(anchor='w')

        buttons_grid.columnconfigure(0, weight=1)
        buttons_grid.columnconfigure(1, weight=1)

        # Safety planning
        safety_frame = ttk.LabelFrame(main_frame, text="Safety Planning")
        safety_frame.pack(fill='both', expand=True, pady=(0, 15))

        safety_text = scrolledtext.ScrolledText(safety_frame, height=10, wrap=tk.WORD,
                                                font=('Arial', 10))
        safety_text.pack(fill='both', expand=True, padx=5, pady=5)

        safety_content = """IF YOU'RE HAVING THOUGHTS OF SELF-HARM:

1. TELL SOMEONE
   • Call a crisis hotline above
   • Text a friend or family member
   • Go to someone you trust
   • Go to a public place

2. REMOVE MEANS
   • Give medications to trusted person
   • Remove sharp objects
   • Get rid of items that could be harmful

3. USE COPING STRATEGIES
   • Deep breathing exercises
   • Go for a walk
   • Listen to calming music
   • Hold ice cubes
   • Take a cold shower
   • Call or text a friend

4. DISTRACT YOURSELF
   • Watch a favorite movie/show
   • Play a game
   • Exercise
   • Draw or color
   • Write in a journal

5. SEEK PROFESSIONAL HELP
   • Call counseling center
   • Go to emergency room
   • Call 911
   • Use crisis services above

WARNING SIGNS TO WATCH FOR:
  • Talking about wanting to die or to hurt oneself
  • Looking for a way to kill oneself
  • Talking about feeling hopeless or having no purpose
  • Talking about feeling trapped or being in unbearable pain
  • Talking about being a burden to others
  • Increasing use of alcohol or drugs
  • Acting anxious, agitated, or recklessly
  • Sleeping too little or too much
  • Withdrawing or feeling isolated
  • Showing rage or talking about seeking revenge
  • Displaying extreme mood swings

YOU ARE NOT ALONE. PEOPLE CARE ABOUT YOU. HELP IS AVAILABLE.
"""
        safety_text.insert(1.0, safety_content)
        safety_text.config(state='disabled')

        # Bottom buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="View All Wellness Resources",
                  command=self.view_all_resources).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Create Safety Plan",
                  command=self.create_safety_plan).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Close",
                  command=self.dialog.destroy).pack(side='right')

    def view_all_resources(self):
        """Open Toplevel showing all crisis/wellness resources from DB"""
        res_win = tk.Toplevel(self.dialog)
        res_win.title("All Wellness Resources")
        res_win.geometry("900x600")
        res_win.transient(self.dialog)

        main_frame = ttk.Frame(res_win)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(main_frame, text="Complete Wellness Resources Library",
                  font=('Arial', 14, 'bold')).pack(pady=(0, 10))

        # Filter by category
        filter_frame = ttk.Frame(main_frame)
        filter_frame.pack(fill='x', pady=(0, 10))

        ttk.Label(filter_frame, text="Category:").pack(side='left', padx=(0, 5))
        cat_var = tk.StringVar(value="All")
        cat_combo = ttk.Combobox(filter_frame, textvariable=cat_var, width=20, state='readonly')
        cat_combo['values'] = ('All', 'Mental Health', 'Counseling', 'Fitness', 'Nutrition', 'Stress Management', 'Crisis')
        cat_combo.pack(side='left', padx=(0, 10))

        columns = ('Category', 'Title', 'Description', 'Contact', 'URL')
        tree = ttk.Treeview(main_frame, columns=columns, show='headings', height=18)
        for col in columns:
            tree.heading(col, text=col)
            if col == 'Description':
                tree.column(col, width=280)
            elif col in ('Title', 'Category'):
                tree.column(col, width=140)
            else:
                tree.column(col, width=130)

        vsb = ttk.Scrollbar(main_frame, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)

        tree_frame = ttk.Frame(main_frame)
        tree_frame.pack(fill='both', expand=True, pady=(0, 10))
        tree.pack(in_=tree_frame, side='left', fill='both', expand=True)
        vsb.pack(in_=tree_frame, side='right', fill='y')

        def load_all():
            for item in tree.get_children():
                tree.delete(item)
            conn = None
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS wellness_resources (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        category TEXT NOT NULL,
                        title TEXT NOT NULL,
                        description TEXT,
                        contact TEXT,
                        url TEXT,
                        created_at TEXT DEFAULT (datetime('now'))
                    )
                ''')
                cursor = conn.cursor()
                selected_cat = cat_var.get()
                if selected_cat == "All":
                    cursor.execute('SELECT category, title, description, contact, url FROM wellness_resources ORDER BY category, title')
                else:
                    cursor.execute('SELECT category, title, description, contact, url FROM wellness_resources WHERE category = ? ORDER BY title',
                                   (selected_cat,))
                rows = cursor.fetchall()
                if rows:
                    for r in rows:
                        tree.insert('', 'end', values=(r[0], r[1], r[2] or '', r[3] or '', r[4] or ''))
                else:
                    # Show built-in crisis defaults
                    crisis_defaults = [
                        ("Crisis", "National Suicide Prevention Lifeline", "24/7 crisis support", "1-800-273-8255", "https://suicidepreventionlifeline.org"),
                        ("Crisis", "Crisis Text Line", "24/7 text-based crisis support", "Text HOME to 741741", "https://www.crisistextline.org"),
                        ("Crisis", "SAMHSA National Helpline", "Treatment referral service", "1-800-662-4357", "https://www.samhsa.gov"),
                        ("Crisis", "Campus Counseling Crisis Line", "After-hours campus support", "(555) 123-HELP", ""),
                        ("Crisis", "NAMI Helpline", "Mental health information and referrals", "1-800-950-6264", ""),
                        ("Crisis", "Campus Police", "Emergency services on campus", "(555) 123-9111", ""),
                        ("Mental Health", "Student Counseling Center", "Professional counseling services", "(555) 123-4567", ""),
                        ("Mental Health", "Campus Health Services", "General health support", "(555) 123-4568", ""),
                        ("Counseling", "Walk-in Counseling", "Mon-Fri 9:00 AM - 11:00 AM, no appointment needed", "(555) 123-4567", ""),
                        ("Stress Management", "Academic Support Center", "Tutoring and study skills", "(555) 123-4571", ""),
                    ]
                    for row in crisis_defaults:
                        if selected_cat == "All" or row[0] == selected_cat:
                            tree.insert('', 'end', values=row)
            except sqlite3.Error as e:
                messagebox.showerror("Error", f"Failed to load resources: {e}", parent=res_win)
            finally:
                if conn:
                    conn.close()

        cat_combo.bind('<<ComboboxSelected>>', lambda e: load_all())
        load_all()

        ttk.Button(main_frame, text="Close", command=res_win.destroy).pack(anchor='e')

    def _ensure_safety_plans_table(self, conn):
        """Ensure safety_plans table exists"""
        conn.execute('''
            CREATE TABLE IF NOT EXISTS safety_plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                warning_signs TEXT,
                coping_strategies TEXT,
                distractions TEXT,
                support_people TEXT,
                professionals TEXT,
                safe_environment TEXT,
                emergency_contacts TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            )
        ''')
        conn.commit()

    def create_safety_plan(self):
        """Open Toplevel with a safety plan form and save to DB"""
        plan_win = tk.Toplevel(self.dialog)
        plan_win.title("Create Personal Safety Plan")
        plan_win.geometry("700x750")
        plan_win.transient(self.dialog)
        plan_win.grab_set()

        main_frame = ttk.Frame(plan_win)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(main_frame, text="Personal Safety Plan",
                  font=('Arial', 14, 'bold')).pack(pady=(0, 5))
        ttk.Label(main_frame, text="This plan is private and confidential. Fill in what feels right for you.",
                  font=('Arial', 9, 'italic')).pack(pady=(0, 10))

        # Scrollable form
        canvas = tk.Canvas(main_frame)
        scrollbar = ttk.Scrollbar(main_frame, orient='vertical', command=canvas.yview)
        form_frame = ttk.Frame(canvas)

        form_frame.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.create_window((0, 0), window=form_frame, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        fields = {}
        field_defs = [
            ("warning_signs", "1. Warning Signs I Notice",
             "What thoughts, feelings, or behaviours indicate a crisis may be developing?"),
            ("coping_strategies", "2. Coping Strategies That Work For Me",
             "What can I do on my own to take my mind off problems or help me feel better?"),
            ("distractions", "3. People and Places That Provide Distraction",
             "People I can contact or places I can go to take my mind off things:"),
            ("support_people", "4. People I Can Call For Support",
             "Friends, family, or others I trust (include names and phone numbers):"),
            ("professionals", "5. Professionals or Agencies to Contact",
             "Counselors, therapists, crisis lines (include names and phone numbers):"),
            ("safe_environment", "6. Making My Environment Safe",
             "Steps I can take to make my surroundings safer:"),
            ("emergency_contacts", "7. Emergency Contacts",
             "People to contact in an emergency (name, relationship, phone):"),
        ]

        for key, label, hint in field_defs:
            ttk.Label(form_frame, text=label, font=('Arial', 10, 'bold')).pack(anchor='w', padx=5, pady=(10, 2))
            ttk.Label(form_frame, text=hint, font=('Arial', 8, 'italic'), wraplength=600).pack(anchor='w', padx=5, pady=(0, 3))
            text_widget = scrolledtext.ScrolledText(form_frame, height=3, wrap=tk.WORD, width=75)
            text_widget.pack(fill='x', padx=5, pady=(0, 5))
            fields[key] = text_widget

        # Load existing plan if present
        user_id = self.auth.current_user.get('id', 0) if self.auth and self.auth.current_user else 0
        conn = None
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            self._ensure_safety_plans_table(conn)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT warning_signs, coping_strategies, distractions, support_people,
                       professionals, safe_environment, emergency_contacts
                FROM safety_plans WHERE user_id = ? ORDER BY updated_at DESC LIMIT 1
            ''', (user_id,))
            existing = cursor.fetchone()
            if existing:
                col_keys = ['warning_signs', 'coping_strategies', 'distractions', 'support_people',
                            'professionals', 'safe_environment', 'emergency_contacts']
                for i, key in enumerate(col_keys):
                    if existing[i]:
                        fields[key].insert(1.0, existing[i])
        except sqlite3.Error:
            pass
        finally:
            if conn:
                conn.close()

        def save_plan():
            data = {}
            for key, widget in fields.items():
                data[key] = widget.get(1.0, tk.END).strip()

            if not any(data.values()):
                messagebox.showwarning("Warning", "Please fill in at least one section.", parent=plan_win)
                return

            conn = None
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                self._ensure_safety_plans_table(conn)
                cursor = conn.cursor()

                # Check for existing plan
                cursor.execute('SELECT id FROM safety_plans WHERE user_id = ? ORDER BY updated_at DESC LIMIT 1', (user_id,))
                existing_row = cursor.fetchone()

                if existing_row:
                    cursor.execute('''
                        UPDATE safety_plans SET warning_signs=?, coping_strategies=?, distractions=?,
                               support_people=?, professionals=?, safe_environment=?, emergency_contacts=?,
                               updated_at=datetime('now')
                        WHERE id=?
                    ''', (data['warning_signs'], data['coping_strategies'], data['distractions'],
                          data['support_people'], data['professionals'], data['safe_environment'],
                          data['emergency_contacts'], existing_row[0]))
                else:
                    cursor.execute('''
                        INSERT INTO safety_plans (user_id, warning_signs, coping_strategies, distractions,
                                                  support_people, professionals, safe_environment, emergency_contacts)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (user_id, data['warning_signs'], data['coping_strategies'], data['distractions'],
                          data['support_people'], data['professionals'], data['safe_environment'],
                          data['emergency_contacts']))

                conn.commit()
                messagebox.showinfo("Saved", "Your safety plan has been saved securely.", parent=plan_win)
            except sqlite3.Error as e:
                messagebox.showerror("Error", f"Failed to save safety plan: {e}", parent=plan_win)
            finally:
                if conn:
                    conn.close()

        # Buttons at bottom (outside the canvas)
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill='x', pady=(10, 0), side='bottom')
        ttk.Button(btn_frame, text="Save Plan", command=save_plan).pack(side='left', padx=(0, 10))
        ttk.Button(btn_frame, text="Cancel", command=plan_win.destroy).pack(side='left')



def view_wellness_resources(self):
    """View wellness resources"""
    try:
        dialog = WellnessResourcesDialog(self.root, self.auth_manager)
        self.root.wait_window(dialog.dialog)
    except (tk.TclError, AttributeError) as e:
        messagebox.showerror("Error", f"Failed to open dialog: {str(e)}")


