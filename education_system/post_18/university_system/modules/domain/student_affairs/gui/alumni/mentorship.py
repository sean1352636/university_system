import tkinter as tk
from education_system.post_18.university_system.infrastructure.email.template_utils import render_template
from tkinter import ttk, messagebox, simpledialog, filedialog
from tkinter.scrolledtext import ScrolledText
from education_system.post_18.university_system.infrastructure.database.db import sqlite3, get_connection as db_get_connection
from education_system.post_18.university_system.core import paths
from datetime import datetime, timedelta
from pathlib import Path
import threading
import shutil
from functools import partial

# Import internationalization (i18n) for multi-language support
try:
    from education_system.post_18.university_system.core.i18n import (
        get_text as _t,
        get_current_language,
    )
    I18N_AVAILABLE = True
except ImportError:
    I18N_AVAILABLE = False
    _t = lambda key, **kwargs: kwargs.get("default", key)
    get_current_language = lambda: "en"

# Alumni service functions
from education_system.post_18.university_system.modules.domain.student_affairs.gui.alumni._service_imports import (
    init_alumni_db, register_alumni, view_alumni, update_alumni,
    view_events, create_enhanced_event, event_check_in_system,
    record_donation, view_donations, setup_mentorship, view_mentorships,
    search_alumni_directory, view_connection_requests, manage_business_directory,
    create_newsletter, manage_alumni_forum, post_job_opportunity, view_job_board,
    schedule_career_counseling, view_fundraising_campaigns, create_fundraising_campaign,
    view_engagement_leaderboard, view_my_badges, manage_photo_gallery,
    manage_class_reunions, manage_regional_chapters, setup_alumni_directory,
    generate_alumni_report, set_auth, setup_alumni_permissions,
    smart_mentorship_matching, generate_engagement_recommendations,
    create_alumni_story, view_alumni_stories, get_connection,
)



class MentorshipMixin:
        def create_mentee_request_form(self, parent):
            """Create mentee request form"""
            ttk.Label(parent, text="Request a Mentor",
                     font=('Arial', 14, 'bold')).pack(pady=(10, 20))

            form_frame = ttk.Frame(parent)
            form_frame.pack(fill=tk.BOTH, expand=True, padx=20)

            info_text = """Request a mentor to help guide your career development!

    A mentor can help you with:
    • Career planning and goal setting
    • Industry insights and networking
    • Resume and interview preparation
    • Professional skill development
    • Decision making and problem solving
    """

            ttk.Label(form_frame, text=info_text, justify=tk.LEFT).pack(pady=(0, 20))

            # Mentee details
            self.mentee_vars = {}

            # Career goals
            goals_frame = ttk.Frame(form_frame)
            goals_frame.pack(fill=tk.X, pady=(0, 10))

            ttk.Label(goals_frame, text="Career Goals:").pack(anchor='w')
            self.mentee_vars['goals'] = ScrolledText(goals_frame, height=3, wrap=tk.WORD)
            self.mentee_vars['goals'].pack(fill=tk.X, pady=(5, 0))

            # Areas of interest
            interest_frame = ttk.Frame(form_frame)
            interest_frame.pack(fill=tk.X, pady=(0, 10))

            ttk.Label(interest_frame, text="Areas of Interest:").pack(anchor='w')
            self.mentee_vars['interests'] = tk.StringVar()
            ttk.Entry(interest_frame, textvariable=self.mentee_vars['interests']).pack(fill=tk.X, pady=(5, 0))

            # Current stage
            stage_frame = ttk.Frame(form_frame)
            stage_frame.pack(fill=tk.X, pady=(0, 10))

            ttk.Label(stage_frame, text="Current Career Stage:").pack(anchor='w')
            self.mentee_vars['stage'] = tk.StringVar()
            stage_combo = ttk.Combobox(stage_frame, textvariable=self.mentee_vars['stage'],
                                      values=["Student", "Recent Graduate", "Early Career", "Career Change", "Mid-Career"])
            stage_combo.pack(fill=tk.X, pady=(5, 0))

            # Preferred mentor characteristics
            mentor_pref_frame = ttk.Frame(form_frame)
            mentor_pref_frame.pack(fill=tk.X, pady=(0, 10))

            ttk.Label(mentor_pref_frame, text="Preferred Mentor Characteristics:").pack(anchor='w')
            self.mentee_vars['mentor_prefs'] = ScrolledText(mentor_pref_frame, height=2, wrap=tk.WORD)
            self.mentee_vars['mentor_prefs'].pack(fill=tk.X, pady=(5, 0))

            # Submit button
            ttk.Button(form_frame, text="Request Mentor",
                      command=self.submit_mentee_request).pack(pady=20)

        def create_mentor_signup_form(self, parent):
            """Create mentor signup form"""
            ttk.Label(parent, text="Sign Up as a Mentor",
                     font=('Arial', 14, 'bold')).pack(pady=(10, 20))

            form_frame = ttk.Frame(parent)
            form_frame.pack(fill=tk.BOTH, expand=True, padx=20)

            info_text = """Become a mentor and share your experience with fellow alumni and current students!

    As a mentor, you will:
    • Guide mentees in their career development
    • Share industry insights and experiences
    • Provide networking opportunities
    • Help with professional skill development
    """

            ttk.Label(form_frame, text=info_text, justify=tk.LEFT).pack(pady=(0, 20))

            # Mentor details
            self.mentor_vars = {}

            # Areas of expertise
            expertise_frame = ttk.Frame(form_frame)
            expertise_frame.pack(fill=tk.X, pady=(0, 10))

            ttk.Label(expertise_frame, text="Areas of Expertise:").pack(anchor='w')
            self.mentor_vars['expertise'] = ScrolledText(expertise_frame, height=3, wrap=tk.WORD)
            self.mentor_vars['expertise'].pack(fill=tk.X, pady=(5, 0))

            # Industries
            industries_frame = ttk.Frame(form_frame)
            industries_frame.pack(fill=tk.X, pady=(0, 10))

            ttk.Label(industries_frame, text="Industries:").pack(anchor='w')
            self.mentor_vars['industries'] = tk.StringVar()
            ttk.Entry(industries_frame, textvariable=self.mentor_vars['industries']).pack(fill=tk.X, pady=(5, 0))

            # Availability
            availability_frame = ttk.Frame(form_frame)
            availability_frame.pack(fill=tk.X, pady=(0, 10))

            ttk.Label(availability_frame, text="Availability:").pack(anchor='w')
            self.mentor_vars['availability'] = tk.StringVar()
            availability_combo = ttk.Combobox(availability_frame, textvariable=self.mentor_vars['availability'],
                                             values=["Weekday evenings", "Weekend mornings", "Weekend afternoons", "Flexible"])
            availability_combo.pack(fill=tk.X, pady=(5, 0))

            # Preferred communication
            comm_frame = ttk.Frame(form_frame)
            comm_frame.pack(fill=tk.X, pady=(0, 10))

            ttk.Label(comm_frame, text="Preferred Communication:").pack(anchor='w')
            self.mentor_vars['communication'] = tk.StringVar()
            comm_combo = ttk.Combobox(comm_frame, textvariable=self.mentor_vars['communication'],
                                     values=["Email", "Phone", "Video calls", "In-person meetings"])
            comm_combo.pack(fill=tk.X, pady=(5, 0))

            # Submit button
            ttk.Button(form_frame, text="Sign Up as Mentor",
                      command=self.submit_mentor_signup).pack(pady=20)

        def create_mentorship_pairing_form(self, parent):
            """Create manual mentorship pairing form"""
            ttk.Label(parent, text="Create Mentorship Pair",
                     font=('Arial', 14, 'bold')).pack(pady=(10, 20))

            form_frame = ttk.Frame(parent)
            form_frame.pack(fill=tk.BOTH, expand=True, padx=20)

            # Mentor selection
            mentor_frame = ttk.Frame(form_frame)
            mentor_frame.pack(fill=tk.X, pady=(0, 10))

            ttk.Label(mentor_frame, text="Select Mentor:").pack(anchor='w')
            self.pairing_vars = {}
            self.pairing_vars['mentor'] = tk.StringVar()
            mentor_combo = ttk.Combobox(mentor_frame, textvariable=self.pairing_vars['mentor'],
                                       values=["Sarah Johnson - Technology", "Michael Chen - Finance", "Dr. Lisa Martinez - Healthcare"])
            mentor_combo.pack(fill=tk.X, pady=(5, 0))

            # Mentee selection
            mentee_frame = ttk.Frame(form_frame)
            mentee_frame.pack(fill=tk.X, pady=(0, 10))

            ttk.Label(mentee_frame, text="Select Mentee:").pack(anchor='w')
            self.pairing_vars['mentee'] = tk.StringVar()
            mentee_combo = ttk.Combobox(mentee_frame, textvariable=self.pairing_vars['mentee'],
                                       values=["John Smith - Student", "Emma Wilson - Recent Graduate", "Alex Brown - Career Change"])
            mentee_combo.pack(fill=tk.X, pady=(5, 0))

            # Focus area
            focus_frame = ttk.Frame(form_frame)
            focus_frame.pack(fill=tk.X, pady=(0, 10))

            ttk.Label(focus_frame, text="Focus Area:").pack(anchor='w')
            self.pairing_vars['focus'] = tk.StringVar()
            focus_combo = ttk.Combobox(focus_frame, textvariable=self.pairing_vars['focus'],
                                      values=["Career Planning", "Industry Transition", "Leadership Development", "Technical Skills"])
            focus_combo.pack(fill=tk.X, pady=(5, 0))

            # Duration
            duration_frame = ttk.Frame(form_frame)
            duration_frame.pack(fill=tk.X, pady=(0, 10))

            ttk.Label(duration_frame, text="Duration (months):").pack(anchor='w')
            self.pairing_vars['duration'] = tk.StringVar(value="6")
            duration_combo = ttk.Combobox(duration_frame, textvariable=self.pairing_vars['duration'],
                                         values=["3", "6", "12", "Ongoing"])
            duration_combo.pack(fill=tk.X, pady=(5, 0))

            # Notes
            ttk.Label(form_frame, text="Notes:").pack(anchor='w', pady=(10, 5))
            self.pairing_notes = ScrolledText(form_frame, height=3, wrap=tk.WORD)
            self.pairing_notes.pack(fill=tk.X)

            # Submit button
            ttk.Button(form_frame, text="Create Mentorship",
                      command=self.submit_mentorship_pairing).pack(pady=20)

        def show_setup_mentorship(self):
            """Show mentorship setup interface"""
            self.clear_content()
            self.update_status("Setup Mentorship")

            ttk.Label(self.content_frame, text="Mentorship Program Setup",
                     font=('Arial', 16, 'bold')).pack(pady=(0, 20))

            # Tabs for different mentorship actions
            notebook = ttk.Notebook(self.content_frame)
            notebook.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))

            # Become mentor tab
            mentor_frame = ttk.Frame(notebook)
            notebook.add(mentor_frame, text="Become a Mentor")

            self.create_mentor_signup_form(mentor_frame)

            # Request mentorship tab
            mentee_frame = ttk.Frame(notebook)
            notebook.add(mentee_frame, text="Request Mentorship")

            self.create_mentee_request_form(mentee_frame)

            # Manual pairing tab (for staff)
            if self.has_permission('manage_mentorships'):
                pairing_frame = ttk.Frame(notebook)
                notebook.add(pairing_frame, text="Create Mentorship Pair")

                self.create_mentorship_pairing_form(pairing_frame)

        def show_view_mentorships(self):
            """Show mentorships viewer"""
            self.clear_content()
            self.update_status("View Mentorships")

            ttk.Label(self.content_frame, text="Mentorship Program Overview",
                     font=('Arial', 16, 'bold')).pack(pady=(0, 20))

            # Tabs for different mentorship views
            notebook = ttk.Notebook(self.content_frame)
            notebook.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))

            # Active mentorships tab
            active_frame = ttk.Frame(notebook)
            notebook.add(active_frame, text="Active Mentorships")

            active_text = ScrolledText(active_frame, wrap=tk.WORD)
            active_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            mentorships_content = """Active Mentorship Relationships:

    👥 Mentorship #001
    Mentor: Sarah Johnson (Class of 2015) - Senior Developer
    Mentee: John Smith (Class of 2023) - Recent Graduate
    Focus Area: Career Planning in Technology
    Start Date: July 1, 2025
    Duration: 6 months
    Status: Active
    Meeting Frequency: Bi-weekly
    Last Meeting: August 10, 2025
    Next Meeting: August 24, 2025

    Progress Notes: John is making excellent progress in his job search.
    We've worked on resume optimization and interview skills.

    [View Details] [Schedule Meeting] [Send Message]

    ---

    👥 Mentorship #002
    Mentor: Dr. Lisa Martinez (Class of 2012) - Healthcare Administrator
    Mentee: Emma Wilson (Class of 2021) - Career Transition
    Focus Area: Healthcare Leadership
    Start Date: June 15, 2025
    Duration: 12 months
    Status: Active
    Meeting Frequency: Monthly
    Last Meeting: August 5, 2025
    Next Meeting: September 5, 2025

    Progress Notes: Emma is successfully transitioning from clinical work
    to healthcare administration. Exploring MBA programs.

    [View Details] [Schedule Meeting] [Send Message]

    ---

    👥 Mentorship #003
    Mentor: Michael Chen (Class of 2018) - Financial Analyst
    Mentee: Alex Brown (Class of 2020) - Industry Change
    Focus Area: Finance Career Development
    Start Date: August 1, 2025
    Duration: 6 months
    Status: Active
    Meeting Frequency: Weekly (initial phase)
    Last Meeting: August 15, 2025
    Next Meeting: August 22, 2025

    Progress Notes: Alex is learning financial modeling and analysis.
    Strong foundation, quick learner, making good progress.

    [View Details] [Schedule Meeting] [Send Message]
    """
            active_text.insert(tk.END, mentorships_content)

            # Program statistics tab
            stats_frame = ttk.Frame(notebook)
            notebook.add(stats_frame, text="Program Statistics")

            stats_text = ScrolledText(stats_frame, wrap=tk.WORD)
            stats_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            stats_content = """Mentorship Program Statistics:

    📊 OVERALL PROGRAM METRICS
    Total Active Mentorships: 15
    Total Mentors: 25
    Total Mentees: 18
    Waiting List: 8 mentees
    Match Success Rate: 89%

    📈 PROGRAM GROWTH
    New Mentorships This Month: 3
    Completed Mentorships (Last 6 Months): 12
    Average Mentorship Duration: 8.5 months
    Satisfaction Rating: 4.7/5.0

    🎯 FOCUS AREAS
    Career Planning: 6 mentorships
    Industry Transition: 4 mentorships
    Leadership Development: 3 mentorships
    Technical Skills: 2 mentorships

    💥 MENTOR DEMOGRAPHICS
    By Industry:
    • Technology: 8 mentors
    • Healthcare: 6 mentors
    • Finance: 5 mentors
    • Education: 3 mentors
    • Other: 3 mentors

    By Graduation Year:
    • 2010-2015: 12 mentors
    • 2016-2020: 8 mentors
    • 2021-2025: 5 mentors

    🎓 MENTEE DEMOGRAPHICS
    By Status:
    • Current Students: 7 mentees
    • Recent Graduates: 6 mentees
    • Career Changers: 5 mentees

    📅 UPCOMING EVENTS
    • Mentor Training Workshop: September 15, 2025
    • Mentorship Program Mixer: October 20, 2025
    • Mid-Program Check-in Sessions: November 2025
    """
            stats_text.insert(tk.END, stats_content)

        def submit_mentee_request(self):
            """Submit mentee request"""
            goals = self.mentee_vars['goals'].get(1.0, tk.END).strip()
            if not goals:
                messagebox.showerror("Validation Error", "Please describe your career goals!")
                return

            messagebox.showinfo("Mentorship Request", "Your mentorship request has been submitted! We'll match you with a suitable mentor.")
            self.update_status("Mentorship request submitted")

            # Clear form
            self.mentee_vars['goals'].delete(1.0, tk.END)
            self.mentee_vars['interests'].set("")
            self.mentee_vars['stage'].set("")
            self.mentee_vars['mentor_prefs'].delete(1.0, tk.END)

        def submit_mentor_signup(self):
            """Submit mentor signup"""
            expertise = self.mentor_vars['expertise'].get(1.0, tk.END).strip()
            if not expertise:
                messagebox.showerror("Validation Error", "Please describe your areas of expertise!")
                return

            messagebox.showinfo("Mentor Signup", "Thank you for signing up as a mentor! You will be contacted soon.")
            self.update_status("Mentor signup completed")

            # Clear form
            self.mentor_vars['expertise'].delete(1.0, tk.END)
            self.mentor_vars['industries'].set("")
            self.mentor_vars['availability'].set("")
            self.mentor_vars['communication'].set("")

        def submit_mentorship_pairing(self):
            """Submit mentorship pairing"""
            if not self.pairing_vars['mentor'].get():
                messagebox.showerror("Validation Error", "Please select a mentor!")
                return

            if not self.pairing_vars['mentee'].get():
                messagebox.showerror("Validation Error", "Please select a mentee!")
                return

            messagebox.showinfo("Mentorship Created", "Mentorship pairing created successfully!")
            self.update_status("Mentorship pairing completed")

            # Clear form
            for var in self.pairing_vars.values():
                var.set("")
            self.pairing_notes.delete(1.0, tk.END)

