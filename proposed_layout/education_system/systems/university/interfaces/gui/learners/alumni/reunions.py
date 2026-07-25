import tkinter as tk
from education_system.systems.university.infrastructure.email.template_utils import render_template
from tkinter import ttk, messagebox, simpledialog, filedialog
from tkinter.scrolledtext import ScrolledText
from education_system.systems.university.infrastructure.database.db import sqlite3, get_connection as db_get_connection
from education_system.systems.university.infrastructure import paths
from datetime import datetime, timedelta
from pathlib import Path
import threading
import shutil
from functools import partial

# Import internationalization (i18n) for multi-language support
try:
    from education_system.systems.university.infrastructure.i18n import (
        get_text as _t,
        get_current_language,
    )
    I18N_AVAILABLE = True
except ImportError:
    I18N_AVAILABLE = False
    _t = lambda key, **kwargs: kwargs.get("default", key)
    get_current_language = lambda: "en"

# Alumni service functions
from education_system.systems.university.interfaces.gui.learners.alumni._service_imports import (
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



class ReunionsMixin:
        def _cancel_reunion(self):
            """Cancel a reunion"""
            if messagebox.askyesno("Confirm Cancellation",
                                  "Are you sure you want to cancel this reunion? This action cannot be undone."):
                reunion_selection = self.selected_reunion.get()
                if not reunion_selection:
                    return

                # Extract reunion_id
                import re
                match = re.search(r'ID:\s*(\d+)', reunion_selection)
                if not match:
                    return

                reunion_id = int(match.group(1))

                try:
                    with db_get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute("""
                            UPDATE class_reunions
                            SET status = 'cancelled'
                            WHERE reunion_id = ?
                        """, (reunion_id,))
                        conn.commit()

                    messagebox.showinfo("Success", "Reunion cancelled successfully!")
                    self.manage_existing_reunion()  # Reload

                    # Log activity
                    from education_system.systems.university.infrastructure.activity_logger import log_activity
                    log_activity('update', 'reunion', reunion_id=reunion_id,
                               details={'action': 'cancelled'})

                except sqlite3.Error as e:
                    messagebox.showerror("Database Error", f"Failed to cancel reunion: {str(e)}")

        def _load_reunion_for_edit(self):
            """Load selected reunion data into edit form"""
            reunion_selection = self.selected_reunion.get()
            if not reunion_selection or reunion_selection == "No reunions available to manage":
                messagebox.showwarning("No Selection", "Please select a reunion to manage.")
                return

            # Extract reunion_id
            import re
            match = re.search(r'ID:\s*(\d+)', reunion_selection)
            if not match:
                messagebox.showerror("Error", "Invalid reunion selection.")
                return

            reunion_id = int(match.group(1))

            try:
                with db_get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT graduation_year, reunion_date, location, fee,
                               expected_attendees, registration_deadline, status, description
                        FROM class_reunions
                        WHERE reunion_id = ?
                    """, (reunion_id,))
                    reunion = cursor.fetchone()

                    if reunion:
                        self.edit_reunion_vars['graduation_year'].set(reunion[0] or '')
                        self.edit_reunion_vars['reunion_date'].set(reunion[1] or '')
                        self.edit_reunion_vars['location'].set(reunion[2] or '')
                        self.edit_reunion_vars['fee'].set(reunion[3] or '')
                        self.edit_reunion_vars['expected_attendees'].set(reunion[4] or '')
                        self.edit_reunion_vars['reg_deadline'].set(reunion[5] or '')
                        self.edit_reunion_vars['status'].set(reunion[6] or 'planning')

                        self.edit_reunion_description.delete(1.0, tk.END)
                        if reunion[7]:
                            self.edit_reunion_description.insert(tk.END, reunion[7])

                        self.update_status(f"Loaded reunion for Class of {reunion[0]}")
                    else:
                        messagebox.showerror("Error", "Reunion not found.")

            except sqlite3.Error as e:
                messagebox.showerror("Database Error", f"Failed to load reunion: {str(e)}")

        def _save_reunion_changes(self):
            """Save changes to reunion"""
            reunion_selection = self.selected_reunion.get()
            if not reunion_selection:
                return

            # Extract reunion_id
            import re
            match = re.search(r'ID:\s*(\d+)', reunion_selection)
            if not match:
                return

            reunion_id = int(match.group(1))

            # Validation
            if not self.edit_reunion_vars['graduation_year'].get():
                messagebox.showerror("Validation Error", "Graduation year is required!")
                return

            try:
                with db_get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE class_reunions
                        SET graduation_year = ?, reunion_date = ?, location = ?,
                            fee = ?, expected_attendees = ?, registration_deadline = ?,
                            status = ?, description = ?
                        WHERE reunion_id = ?
                    """, (
                        self.edit_reunion_vars['graduation_year'].get(),
                        self.edit_reunion_vars['reunion_date'].get(),
                        self.edit_reunion_vars['location'].get(),
                        self.edit_reunion_vars['fee'].get() or None,
                        self.edit_reunion_vars['expected_attendees'].get() or None,
                        self.edit_reunion_vars['reg_deadline'].get() or None,
                        self.edit_reunion_vars['status'].get(),
                        self.edit_reunion_description.get(1.0, tk.END).strip(),
                        reunion_id
                    ))
                    conn.commit()

                messagebox.showinfo("Success", "Reunion updated successfully!")
                self.update_status("Reunion changes saved")

                # Log activity
                from education_system.systems.university.infrastructure.activity_logger import log_activity
                log_activity('update', 'reunion', reunion_id=reunion_id,
                           details={'graduation_year': self.edit_reunion_vars['graduation_year'].get()})

            except sqlite3.Error as e:
                messagebox.showerror("Database Error", f"Failed to save changes: {str(e)}")

        def create_reunion_form(self, parent):
            """Create reunion planning form"""
            ttk.Label(parent, text="Plan a Class Reunion",
                     font=('Arial', 14, 'bold')).pack(pady=(10, 20))

            form_frame = ttk.Frame(parent)
            form_frame.pack(fill=tk.BOTH, expand=True, padx=20)

            # Basic details
            self.reunion_vars = {}

            basic_fields = [
                ("Graduation Year*", "graduation_year"),
                ("Reunion Date*", "reunion_date"),
                ("Location*", "location"),
                ("Registration Fee", "fee")
            ]

            for label, var_name in basic_fields:
                field_frame = ttk.Frame(form_frame)
                field_frame.pack(fill=tk.X, pady=5)

                ttk.Label(field_frame, text=label, width=15).pack(side=tk.LEFT, padx=(0, 10))
                self.reunion_vars[var_name] = tk.StringVar()
                ttk.Entry(field_frame, textvariable=self.reunion_vars[var_name]).pack(side=tk.LEFT, fill=tk.X, expand=True)

            # Description
            ttk.Label(form_frame, text="Reunion Description:").pack(anchor='w', pady=(10, 5))
            self.reunion_description = ScrolledText(form_frame, height=6, wrap=tk.WORD)
            self.reunion_description.pack(fill=tk.X)

            # Submit button
            ttk.Button(form_frame, text="Submit Reunion Plan",
                      command=self.submit_reunion_plan).pack(pady=20)

        def manage_existing_reunion(self):
            """Edit an existing reunion"""
            self.clear_content()
            self.update_status("Manage Reunion")

            ttk.Label(self.content_frame, text="Manage Existing Reunion",
                     font=('Arial', 16, 'bold')).pack(pady=(0, 20))

            # Reunion selection
            select_frame = ttk.LabelFrame(self.content_frame, text="Select Reunion to Manage", padding=10)
            select_frame.pack(fill=tk.X, padx=20, pady=(0, 20))

            ttk.Label(select_frame, text="Select Reunion:").pack(side=tk.LEFT, padx=(0, 10))
            self.selected_reunion = tk.StringVar()

            # Load reunions from database
            reunion_options = []
            try:
                with db_get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT reunion_id, graduation_year, reunion_date, location
                        FROM class_reunions
                        WHERE organizer_id = ? OR status = 'planning'
                        ORDER BY reunion_date DESC
                    """, (self._current_user_id(),))
                    reunions = cursor.fetchall()
                    reunion_options = [f"Class of {r[1]} - {r[2]} at {r[3]} (ID: {r[0]})" for r in reunions]
            except sqlite3.Error:
                pass  # Silently handle database errors

            if not reunion_options:
                reunion_options = ["No reunions available to manage"]

            reunion_combo = ttk.Combobox(select_frame, textvariable=self.selected_reunion,
                                        values=reunion_options, width=50)
            reunion_combo.pack(side=tk.LEFT, padx=(0, 20))
            if reunion_options and reunion_options[0] != "No reunions available to manage":
                reunion_combo.set(reunion_options[0])

            ttk.Button(select_frame, text="Load Reunion",
                      command=self._load_reunion_for_edit).pack(side=tk.LEFT)

            # Edit form (initially hidden)
            self.reunion_edit_frame = ttk.LabelFrame(self.content_frame, text="Reunion Details", padding=10)
            self.reunion_edit_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))

            # Form fields
            self.edit_reunion_vars = {}

            fields = [
                ("Graduation Year*", "graduation_year"),
                ("Reunion Date*", "reunion_date"),
                ("Location*", "location"),
                ("Registration Fee", "fee"),
                ("Expected Attendees", "expected_attendees"),
                ("Registration Deadline", "reg_deadline")
            ]

            for label, var_name in fields:
                field_frame = ttk.Frame(self.reunion_edit_frame)
                field_frame.pack(fill=tk.X, pady=5)

                ttk.Label(field_frame, text=label, width=20).pack(side=tk.LEFT, padx=(0, 10))
                self.edit_reunion_vars[var_name] = tk.StringVar()
                ttk.Entry(field_frame, textvariable=self.edit_reunion_vars[var_name]).pack(
                    side=tk.LEFT, fill=tk.X, expand=True)

            # Status
            status_frame = ttk.Frame(self.reunion_edit_frame)
            status_frame.pack(fill=tk.X, pady=5)

            ttk.Label(status_frame, text="Status*", width=20).pack(side=tk.LEFT, padx=(0, 10))
            self.edit_reunion_vars['status'] = tk.StringVar()
            status_combo = ttk.Combobox(status_frame, textvariable=self.edit_reunion_vars['status'],
                                       values=["planning", "registration_open", "registration_closed", "completed", "cancelled"])
            status_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)

            # Description
            ttk.Label(self.reunion_edit_frame, text="Description:").pack(anchor='w', pady=(10, 5))
            self.edit_reunion_description = ScrolledText(self.reunion_edit_frame, height=6, wrap=tk.WORD)
            self.edit_reunion_description.pack(fill=tk.X)

            # Action buttons
            button_frame = ttk.Frame(self.reunion_edit_frame)
            button_frame.pack(fill=tk.X, pady=(20, 0))

            ttk.Button(button_frame, text="Save Changes",
                      command=self._save_reunion_changes).pack(side=tk.LEFT, padx=(0, 10))
            ttk.Button(button_frame, text="Cancel Reunion",
                      command=self._cancel_reunion).pack(side=tk.LEFT)

        def show_class_reunions(self):
            """Show class reunions interface"""
            self.clear_content()
            self.update_status("Class Reunions")

            ttk.Label(self.content_frame, text="Class Reunion Management",
                     font=('Arial', 16, 'bold')).pack(pady=(0, 20))

            # Tabs for different reunion views
            notebook = ttk.Notebook(self.content_frame)
            notebook.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))

            # Upcoming reunions tab
            upcoming_frame = ttk.Frame(notebook)
            notebook.add(upcoming_frame, text="Upcoming Reunions")

            upcoming_text = ScrolledText(upcoming_frame, wrap=tk.WORD)
            upcoming_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            reunion_content = """Upcoming Class Reunions:

    🎓 Class of 2020 - 5 Year Reunion
    Date: October 10, 2025
    Location: Campus Alumni Center
    Organizer: Emily Davis
    Registration Fee: £50.00
    Expected Attendees: 150
    Registration Deadline: September 25, 2025
    Status: Registration Open

    Details: Join us for a weekend of reconnection, campus tours, dinner, and celebration.
    Special presentations from notable class members and career networking opportunities.

    [Register Now] [View Details]

    ---

    🎓 Class of 2015 - 10 Year Reunion
    Date: November 15, 2025
    Location: Grand Hotel Downtown
    Organizer: Sarah Johnson
    Registration Fee: £75.00
    Expected Attendees: 200
    Registration Deadline: October 30, 2025
    Status: Planning Phase

    Details: A formal dinner and celebration marking our 10-year milestone.
    Cocktail hour, awards ceremony, and dance with live music.

    [Register Now] [View Details]

    ---

    🎓 Class of 2000 - 25 Year Reunion
    Date: June 20, 2026
    Location: TBD
    Organizer: Needed
    Registration Fee: TBD
    Expected Attendees: TBD
    Status: Organizer Needed

    Details: Planning committee forming for our 25-year celebration.
    Volunteers needed to help organize this milestone event.

    [Volunteer to Organize] [Express Interest]
    """
            upcoming_text.insert(tk.END, reunion_content)

            # Plan reunion tab
            plan_frame = ttk.Frame(notebook)
            notebook.add(plan_frame, text="Plan a Reunion")

            self.create_reunion_form(plan_frame)

        def submit_reunion_plan(self):
            """Submit reunion planning form"""
            required_fields = ['graduation_year', 'reunion_date', 'location']
            for field in required_fields:
                if not self.reunion_vars[field].get().strip():
                    messagebox.showerror("Validation Error", f"{field.replace('_', ' ').title()} is required!")
                    return

            messagebox.showinfo("Reunion Planned", "Class reunion plan submitted successfully!")
            self.update_status("Reunion planning form submitted")

