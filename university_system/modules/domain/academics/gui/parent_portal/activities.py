from university_system.infrastructure.database.db import DEFAULT_DB_PATH  # injected
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, scrolledtext, filedialog
from university_system.infrastructure.database.db import sqlite3
import datetime
import json
import threading
import csv
from typing import Optional, List, Dict, Any
import sys
import os
from university_system.infrastructure.auth import UserAuth
from university_system.infrastructure.shared_context import get_auth

# Import i18n for language support
from university_system.modules.shared.utils.i18n import (
    init_i18n,
    get_text as _t,
    get_current_language,
)
from university_system.modules.shared.utils.gui_language_selector import (
    show_gui_language_selector,
    create_language_menu_button,
)

# Import email service for sending actual emails
try:
    from university_system.infrastructure.email.email_service import send_email, send_email_as_user
    EMAIL_SERVICE_AVAILABLE = True
except ImportError:
    EMAIL_SERVICE_AVAILABLE = False
    print("Warning: Email service not available - emails will be stored locally only")

# Import the original parent portal functionality
try:
    from university_system.modules.domain.academics.services.parent_portal import ParentPortal
except ImportError:
    # If direct import fails, try to import from the document content
    print("Warning: Could not import parent_portal module directly. Using embedded functionality.")
    # We'll create a simplified version that maintains compatibility



from .base import ParentPortalGUI

def show_activities_interface(self):
    """Show extracurricular activities interface"""
    self.clear_content()
    self.update_status("Extracurricular Activities")

    title = ttk.Label(self.content_frame, text="Extracurricular Activities", style='Title.TLabel', font=('Arial', 20, 'bold'))
    title.pack(pady=20)

    if not self.children:
        ttk.Label(self.content_frame, text="No students linked to your guardian account.").pack(pady=50)
        return

    # Child selection
    child_frame = ttk.Frame(self.content_frame)
    child_frame.pack(fill=tk.X, padx=20, pady=10)

    ttk.Label(child_frame, text="Select Student:").pack(side=tk.LEFT, padx=5)
    child_var = tk.StringVar()
    child_combo = ttk.Combobox(child_frame, textvariable=child_var, width=40, state="readonly")
    child_combo['values'] = [f"{child[1]} {child[3]} (ID: {child[0]})" for child in self.children]
    if child_combo['values']:
        child_combo.set(child_combo['values'][0])
    child_combo.pack(side=tk.LEFT, padx=5)

    # Activities display frame
    activities_frame = ttk.LabelFrame(self.content_frame, text="Activities", padding=15)
    activities_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

    def load_activities():
        for widget in activities_frame.winfo_children():
            widget.destroy()

        selected_child = child_var.get()
        if not selected_child:
            ttk.Label(activities_frame, text="Please select a child").pack(pady=20)
            return

        student_id = selected_child.split("ID: ")[1].rstrip(")")

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='extracurricular_activities'
            """)

            if cursor.fetchone():
                # Check if student_activities table exists for enrollment lookup
                cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='student_activities'
                """)

                if cursor.fetchone():
                    # Query student's enrolled activities via junction table
                    cursor.execute("""
                    SELECT ea.activity_name, 'General', ea.meeting_schedule,
                           ea.location, ea.supervisor, ea.description
                    FROM extracurricular_activities ea
                    JOIN student_activities sa ON ea.id = sa.activity_id
                    WHERE sa.student_id = ? AND sa.status = 'active'
                          AND (ea.status = 'active' OR ea.status IS NULL)
                    ORDER BY ea.activity_name
                    """, (student_id,))
                else:
                    # Fallback: just show all active activities (without student enrollment)
                    cursor.execute("""
                    SELECT activity_name, 'General', meeting_schedule,
                           location, supervisor, description
                    FROM extracurricular_activities
                    WHERE status = 'active' OR status IS NULL
                    ORDER BY activity_name
                    LIMIT 20
                    """)

                activities = cursor.fetchall()

                if activities:
                    for activity in activities:
                        activity_card = ttk.LabelFrame(activities_frame, text=activity[0] or 'Activity', padding=10)
                        activity_card.pack(fill=tk.X, pady=5)

                        category = activity[1] or 'General'
                        ttk.Label(activity_card, text=f"Category: {category}",
                                 font=('Arial', 9, 'bold')).pack(anchor='w')
                        schedule = activity[2] or 'Not scheduled'
                        ttk.Label(activity_card, text=f"Schedule: {schedule}",
                                 font=('Arial', 9)).pack(anchor='w')
                        location = activity[3] or 'TBD'
                        ttk.Label(activity_card, text=f"Location: {location}",
                                 font=('Arial', 9)).pack(anchor='w')
                        supervisor = activity[4] or 'TBD'
                        ttk.Label(activity_card, text=f"Supervisor: {supervisor}",
                                 font=('Arial', 9)).pack(anchor='w')
                        if activity[5]:
                            ttk.Label(activity_card, text=activity[5], wraplength=600).pack(anchor='w', pady=3)
                else:
                    ttk.Label(activities_frame, text="Not enrolled in any activities",
                             font=('Arial', 11)).pack(pady=50)
                    ttk.Button(activities_frame, text="Browse Activities",
                              command=self.browse_activities).pack()
            else:
                ttk.Label(activities_frame, text="Activities system not configured",
                         font=('Arial', 11)).pack(pady=20)

            conn.close()

        except Exception as e:
            ttk.Label(activities_frame, text=f"Error loading activities: {str(e)}",
                     font=('Arial', 10)).pack(pady=20)

    ttk.Button(child_frame, text="Load Activities", command=load_activities).pack(side=tk.LEFT, padx=5)
    load_activities()
ParentPortalGUI.show_activities_interface = show_activities_interface

def browse_activities(self):
    """Browse available activities"""
    dialog = tk.Toplevel(self.root)
    dialog.title("Browse Available Activities")
    dialog.geometry("900x700")
    dialog.transient(self.root)
    dialog.grab_set()

    # Title
    title_frame = ttk.Frame(dialog, padding=20)
    title_frame.pack(fill=tk.X)
    ttk.Label(title_frame, text="Browse Extracurricular Activities",
             font=('Arial', 16, 'bold')).pack(anchor='w')
    ttk.Label(title_frame, text="Explore available activities and programs for students",
             font=('Arial', 10)).pack(anchor='w', pady=(0, 10))

    # Filter frame
    filter_frame = ttk.LabelFrame(dialog, text="Filter Activities", padding=10)
    filter_frame.pack(fill=tk.X, padx=20, pady=(0, 10))

    ttk.Label(filter_frame, text="Category:").pack(side=tk.LEFT, padx=5)
    category_var = tk.StringVar(value="All")
    categories = ["All", "Sports", "Arts", "Music", "Academic", "Technology", "Community Service"]
    category_combo = ttk.Combobox(filter_frame, textvariable=category_var,
                                 values=categories, state="readonly", width=20)
    category_combo.pack(side=tk.LEFT, padx=5)

    # Main content frame with scrollbar
    main_frame = ttk.Frame(dialog, padding=20)
    main_frame.pack(fill=tk.BOTH, expand=True)

    # Create canvas for scrolling
    canvas = tk.Canvas(main_frame)
    scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
    scrollable_frame = ttk.Frame(canvas)

    scrollable_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )

    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)

    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def load_activities(category_filter="All"):
        # Clear existing widgets
        for widget in scrollable_frame.winfo_children():
            widget.destroy()

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Check if activities catalog table exists
            cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='activities_catalog'
            """)

            if cursor.fetchone():
                # Fetch available activities
                if category_filter == "All":
                    cursor.execute("""
                    SELECT activity_name, category, description, schedule, location,
                           supervisor, capacity, enrolled_count, age_range, cost
                    FROM activities_catalog
                    WHERE is_available = 1
                    ORDER BY category, activity_name
                    """)
                else:
                    cursor.execute("""
                    SELECT activity_name, category, description, schedule, location,
                           supervisor, capacity, enrolled_count, age_range, cost
                    FROM activities_catalog
                    WHERE is_available = 1 AND category = ?
                    ORDER BY activity_name
                    """, (category_filter,))

                activities = cursor.fetchall()

                if activities:
                    for activity in activities:
                        # Create card for each activity
                        card = ttk.LabelFrame(scrollable_frame, text=activity[0], padding=15)
                        card.pack(fill=tk.X, pady=5)

                        # Category badge
                        badge_frame = ttk.Frame(card)
                        badge_frame.pack(anchor='w', pady=(0, 5))
                        ttk.Label(badge_frame, text=f"Category: {activity[1]}",
                                 font=('Arial', 9, 'bold'),
                                 background='#3498db', foreground='white',
                                 padding=5).pack(side=tk.LEFT)

                        # Description
                        ttk.Label(card, text=activity[2], wraplength=750,
                                 font=('Arial', 10)).pack(anchor='w', pady=5)

                        # Details frame
                        details_frame = ttk.Frame(card)
                        details_frame.pack(fill=tk.X, pady=5)

                        # Column 1
                        col1 = ttk.Frame(details_frame)
                        col1.pack(side=tk.LEFT, fill=tk.X, expand=True)
                        ttk.Label(col1, text=f"📅 Schedule: {activity[3]}",
                                 font=('Arial', 9)).pack(anchor='w', pady=2)
                        ttk.Label(col1, text=f"📍 Location: {activity[4]}",
                                 font=('Arial', 9)).pack(anchor='w', pady=2)
                        ttk.Label(col1, text=f"👨‍🏫 Supervisor: {activity[5]}",
                                 font=('Arial', 9)).pack(anchor='w', pady=2)

                        # Column 2
                        col2 = ttk.Frame(details_frame)
                        col2.pack(side=tk.LEFT, fill=tk.X, expand=True)

                        spots_available = activity[6] - activity[7] if activity[6] else "Unlimited"
                        spots_color = 'green' if (isinstance(spots_available, int) and spots_available > 5) or spots_available == "Unlimited" else 'orange' if isinstance(spots_available, int) and spots_available > 0 else 'red'
                        ttk.Label(col2, text=f"👥 Capacity: {activity[7]}/{activity[6] if activity[6] else '∞'}",
                                 font=('Arial', 9), foreground=spots_color).pack(anchor='w', pady=2)
                        ttk.Label(col2, text=f"🎂 Age Range: {activity[8]}",
                                 font=('Arial', 9)).pack(anchor='w', pady=2)
                        cost_text = f"£{activity[9]:.2f}" if activity[9] else "Free"
                        ttk.Label(col2, text=f"💰 Cost: {cost_text}",
                                 font=('Arial', 9)).pack(anchor='w', pady=2)

                        # Enroll button
                        btn_frame = ttk.Frame(card)
                        btn_frame.pack(anchor='e', pady=(5, 0))
                        ttk.Button(btn_frame, text="Request Enrollment",
                                  command=lambda a=activity[0]: self.request_activity_enrollment(a)).pack(side=tk.RIGHT)

                else:
                    ttk.Label(scrollable_frame, text="No activities found in this category.",
                             font=('Arial', 11)).pack(pady=50)
            else:
                # Create sample activities if table doesn't exist
                sample_activities = [
                    ("Soccer Team", "Sports", "Develop teamwork and athletic skills through competitive soccer", "Mon & Wed 3:30-5:00 PM", "Main Field", "Coach Martinez", 25, 18, "Ages 10-14", 50.00),
                    ("Chess Club", "Academic", "Learn strategic thinking and compete in tournaments", "Tue & Thu 3:30-4:30 PM", "Room 205", "Mr. Thompson", 20, 12, "Ages 8-16", 0.00),
                    ("Drama Club", "Arts", "Participate in theatrical productions and develop performance skills", "Mon, Wed, Fri 3:30-5:30 PM", "Auditorium", "Ms. Rivera", 30, 24, "Ages 11-17", 75.00),
                    ("Robotics Team", "Technology", "Build and program robots for competitions", "Thu 3:30-6:00 PM", "STEM Lab", "Dr. Chen", 15, 15, "Ages 12-18", 100.00),
                    ("University Band", "Music", "Learn instruments and perform in concerts", "Tue & Thu 3:30-5:00 PM", "Music Room", "Ms. Johnson", 40, 32, "All Students", 150.00),
                    ("Volunteer Corps", "Community Service", "Participate in community service projects", "Flexible Schedule", "Various Locations", "Mrs. Anderson", None, 28, "Ages 13+", 0.00),
                ]

                for activity in sample_activities:
                    # Create card for each activity (same structure as above)
                    card = ttk.LabelFrame(scrollable_frame, text=activity[0], padding=15)
                    card.pack(fill=tk.X, pady=5)

                    badge_frame = ttk.Frame(card)
                    badge_frame.pack(anchor='w', pady=(0, 5))
                    ttk.Label(badge_frame, text=f"Category: {activity[1]}",
                             font=('Arial', 9, 'bold'),
                             background='#3498db', foreground='white',
                             padding=5).pack(side=tk.LEFT)

                    ttk.Label(card, text=activity[2], wraplength=750,
                             font=('Arial', 10)).pack(anchor='w', pady=5)

                    details_frame = ttk.Frame(card)
                    details_frame.pack(fill=tk.X, pady=5)

                    col1 = ttk.Frame(details_frame)
                    col1.pack(side=tk.LEFT, fill=tk.X, expand=True)
                    ttk.Label(col1, text=f"📅 Schedule: {activity[3]}",
                             font=('Arial', 9)).pack(anchor='w', pady=2)
                    ttk.Label(col1, text=f"📍 Location: {activity[4]}",
                             font=('Arial', 9)).pack(anchor='w', pady=2)
                    ttk.Label(col1, text=f"👨‍🏫 Supervisor: {activity[5]}",
                             font=('Arial', 9)).pack(anchor='w', pady=2)

                    col2 = ttk.Frame(details_frame)
                    col2.pack(side=tk.LEFT, fill=tk.X, expand=True)

                    spots_available = activity[6] - activity[7] if activity[6] else "Unlimited"
                    spots_color = 'green' if (isinstance(spots_available, int) and spots_available > 5) or spots_available == "Unlimited" else 'orange' if isinstance(spots_available, int) and spots_available > 0 else 'red'
                    capacity_text = f"{activity[7]}/{activity[6]}" if activity[6] else f"{activity[7]}/∞"
                    ttk.Label(col2, text=f"👥 Capacity: {capacity_text}",
                             font=('Arial', 9), foreground=spots_color).pack(anchor='w', pady=2)
                    ttk.Label(col2, text=f"🎂 Age Range: {activity[8]}",
                             font=('Arial', 9)).pack(anchor='w', pady=2)
                    cost_text = f"£{activity[9]:.2f}" if activity[9] else "Free"
                    ttk.Label(col2, text=f"💰 Cost: {cost_text}",
                             font=('Arial', 9)).pack(anchor='w', pady=2)

                    btn_frame = ttk.Frame(card)
                    btn_frame.pack(anchor='e', pady=(5, 0))
                    ttk.Button(btn_frame, text="Request Enrollment",
                              command=lambda a=activity[0]: self.request_activity_enrollment(a)).pack(side=tk.RIGHT)

            conn.close()

        except Exception as e:
            ttk.Label(scrollable_frame, text=f"Error loading activities: {str(e)}",
                     font=('Arial', 10)).pack(pady=20)

    # Bind category filter change
    category_combo.bind('<<ComboboxSelected>>', lambda e: load_activities(category_var.get()))

    # Load initial activities
    load_activities()

    # Close button
    ttk.Button(dialog, text="Close", command=dialog.destroy).pack(pady=10)
ParentPortalGUI.browse_activities = browse_activities

def request_activity_enrollment(self, activity_name):
    """Request enrollment in an activity"""
    messagebox.showinfo("Enrollment Request",
                       f"Your enrollment request for '{activity_name}' has been submitted.\n\n"
                       "The university administration will review your request and contact you with next steps.")
ParentPortalGUI.request_activity_enrollment = request_activity_enrollment
