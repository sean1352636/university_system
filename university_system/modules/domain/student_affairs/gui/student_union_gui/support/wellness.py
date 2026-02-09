import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog
from university_system.infrastructure.database.db import sqlite3
from university_system.modules.shared.constants import paths
from datetime import datetime, timedelta
import hashlib
import json
import sys
import os
import logging
from typing import Dict, List, Optional, Tuple, Any
import threading
import queue
from university_system.infrastructure.email.template_utils import render_template
from university_system.infrastructure.auth import UserAuth
from university_system.infrastructure.shared_context import get_auth

# Import i18n for multi-language support
from university_system.modules.shared.utils.i18n import (
    init_i18n,
    get_text as _t,
    set_language,
    get_current_language,
    get_current_language_name,
    get_available_languages,
)
from university_system.modules.shared.utils.gui_language_selector import show_gui_language_selector

# Use centralized path configuration
DEFAULT_DB_PATH = paths.DEFAULT_DB_PATH

# Import finance integration for student finance account payments
try:
    from university_system.modules.shared.utils.finance_integration import (
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
    from university_system.infrastructure.database.db import get_connection
    from university_system.modules.domain.student_affairs.student_union.administration.student_union_core import init_student_union_db
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

    def create_mental_health_tab(self, parent):
        """Create mental health resources tab"""
        text = scrolledtext.ScrolledText(parent, wrap=tk.WORD, padx=10, pady=10)
        text.pack(fill='both', expand=True)

        content = """MENTAL HEALTH HOTLINES AND RESOURCES

24/7 Crisis Hotlines:
• National Suicide Prevention Lifeline: 1-800-273-8255
• Crisis Text Line: Text HOME to 741741
• SAMHSA National Helpline: 1-800-662-4357

Campus Resources:
• Student Counseling Center: (555) 123-4567
• Campus Health Services: (555) 123-4568
• Student Wellness Office: (555) 123-4569

Online Resources:
• MindBeacon: Online cognitive behavioral therapy
• Headspace: Meditation and mindfulness app
• 7 Cups: Free emotional support chat

Support Groups:
• Anxiety and Depression Support Group
• Mindfulness and Meditation Group
• Stress Management Workshop

Emergency Services:
• If you are in immediate danger, call 911
• Campus Security: (555) 123-9999

Remember: It's okay to ask for help. Taking care of your mental health is just as important as your physical health.
"""
        text.insert(1.0, content)
        text.config(state='disabled')

    def create_counseling_tab(self, parent):
        """Create counseling services tab"""
        text = scrolledtext.ScrolledText(parent, wrap=tk.WORD, padx=10, pady=10)
        text.pack(fill='both', expand=True)

        content = """COUNSELING SERVICES

Student Counseling Center:
• Location: Student Services Building, 2nd Floor
• Hours: Monday-Friday, 8:00 AM - 6:00 PM
• Phone: (555) 123-4567
• Email: counseling@university.edu

Services Offered:
• Individual counseling
• Group therapy
• Couples counseling
• Family therapy
• Crisis intervention
• Psychiatric services

Confidentiality:
• All counseling sessions are confidential
• Your privacy is protected by HIPAA

How to Schedule:
• Call (555) 123-4567 to schedule an appointment
• Walk-in hours: Monday-Friday, 9:00 AM - 11:00 AM
• Emergency services available 24/7

Insurance:
• Most student health plans cover counseling services
• Financial aid available for those without insurance
"""
        text.insert(1.0, content)
        text.config(state='disabled')

    def create_fitness_tab(self, parent):
        """Create fitness programs tab"""
        text = scrolledtext.ScrolledText(parent, wrap=tk.WORD, padx=10, pady=10)
        text.pack(fill='both', expand=True)

        content = """FITNESS PROGRAMS

Campus Fitness Center:
• Location: Recreation Building
• Hours: Monday-Sunday, 6:00 AM - 11:00 PM
• Membership: Free for all students

Facilities:
• Weight room with free weights and machines
• Cardio equipment (treadmills, bikes, ellipticals)
• Group fitness studio
• Indoor track
• Basketball courts
• Swimming pool

Group Fitness Classes:
• Yoga - Monday/Wednesday 7:00 PM
• Spin Class - Tuesday/Thursday 6:00 PM
• Zumba - Wednesday/Friday 5:30 PM
• Boot Camp - Saturday 9:00 AM
• Pilates - Tuesday/Thursday 7:00 PM

Personal Training:
• One-on-one sessions available
• Group training options
• Nutrition counseling included

Intramural Sports:
• Basketball, Soccer, Volleyball
• Sign up at the Recreation Office
"""
        text.insert(1.0, content)
        text.config(state='disabled')

    def create_nutrition_tab(self, parent):
        """Create nutrition resources tab"""
        text = scrolledtext.ScrolledText(parent, wrap=tk.WORD, padx=10, pady=10)
        text.pack(fill='both', expand=True)

        content = """NUTRITION RESOURCES

Campus Nutritionist:
• Location: Student Health Center
• Phone: (555) 123-4570
• Email: nutrition@university.edu

Services:
• Individual nutrition counseling
• Meal planning assistance
• Weight management support
• Sports nutrition guidance
• Eating disorder support

Healthy Dining Options:
• Nutritional information available for all dining halls
• Vegetarian and vegan options
• Gluten-free and allergen-free meals
• Customizable meal plans

Nutrition Workshops:
• Cooking demonstrations
• Meal prep basics
• Reading nutrition labels
• Budget-friendly healthy eating

Food Pantry:
• Location: Student Union, Room 105
• Hours: Monday-Friday, 10:00 AM - 4:00 PM
• Free groceries for students in need
"""
        text.insert(1.0, content)
        text.config(state='disabled')

    def create_stress_tab(self, parent):
        """Create stress management tab"""
        text = scrolledtext.ScrolledText(parent, wrap=tk.WORD, padx=10, pady=10)
        text.pack(fill='both', expand=True)

        content = """STRESS MANAGEMENT TOOLS

Relaxation Techniques:
• Deep breathing exercises
• Progressive muscle relaxation
• Guided imagery
• Mindfulness meditation

Time Management Tips:
• Use a planner or digital calendar
• Break large tasks into smaller steps
• Prioritize your tasks
• Learn to say no
• Schedule breaks and downtime

Study Stress:
• Academic Support Center: (555) 123-4571
• Tutoring services available
• Study skills workshops
• Test anxiety support groups

Campus Resources:
• Meditation Room: Student Union, 3rd Floor
• Quiet Study Spaces: Library
• Nature Trails: Behind Recreation Building

Wellness Apps (Free for Students):
• Calm: Meditation and sleep
• Headspace: Mindfulness
• MyFitnessPal: Nutrition tracking
• Sleep Cycle: Sleep tracking

Remember:
• Regular exercise reduces stress
• Get 7-9 hours of sleep per night
• Maintain social connections
• Practice self-care
"""
        text.insert(1.0, content)
        text.config(state='disabled')


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
        self.dialog.destroy()
        # Would open WellnessResourcesDialog
        messagebox.showinfo("Resources", "Opening full wellness resources library...")

    def create_safety_plan(self):
        messagebox.showinfo("Safety Plan",
                           "Safety plan template:\n\n"
                           "1. Warning signs I notice\n"
                           "2. Coping strategies that work for me\n"
                           "3. People/places that distract me\n"
                           "4. People I can call\n"
                           "5. Professionals to contact\n"
                           "6. How to make environment safe\n\n"
                           "Would you like to create a personalized plan?")



def view_wellness_resources(self):
    """View wellness resources"""
    try:
        dialog = WellnessResourcesDialog(self.root, self.auth_manager)
        self.root.wait_window(dialog.dialog)
    except (tk.TclError, AttributeError) as e:
        messagebox.showerror("Error", f"Failed to open dialog: {str(e)}")


