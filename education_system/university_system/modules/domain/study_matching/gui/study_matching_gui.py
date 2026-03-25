"""
GUI Interface for Peer Study Matching.

Features:
- Visual study profile with preference indicators
- Match results with compatibility scores
- Study group management interface
- Virtual study room controls
- Q&A board with voting
- Pomodoro timer integration
- Analytics dashboard
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime
from typing import Optional

from education_system.university_system.infrastructure.shared_context import get_auth
from education_system.university_system.modules.domain.study_matching.services.study_matching_service import StudyMatchingService


# Constants
STUDY_STYLES = ["Visual", "Auditory", "Kinesthetic", "Reading/Writing"]
PREFERRED_TIMES = ["Morning", "Afternoon", "Evening", "Night"]
GROUP_SIZES = ["Solo", "Small (2-4)", "Medium (5-8)", "Large (9+)"]
COMMUNICATION_STYLES = ["Collaborative", "Independent", "Mixed"]
NOISE_PREFERENCES = ["Quiet", "Moderate", "Lively"]
QA_CATEGORIES = ["General", "Concepts", "Problem Solving", "Projects", "Exam Prep"]
DIFFICULTY_LEVELS = ["Easy", "Medium", "Hard"]


class StudyMatchingGUI:
    """GUI interface for peer study matching system."""

    def __init__(self, parent, auth=None):
        """Initialize the GUI."""
        self.parent = parent
        self.service = StudyMatchingService()
        self.auth = auth or get_auth()

        self.window = tk.Toplevel(parent)
        self.window.title("Peer Study Matching & Collaboration")
        self.window.geometry("1300x850")

        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to use Peer Study Matching.")
            self.window.destroy()
            return

        # Cache for available modules
        self.available_modules = []
        self._load_available_modules()

        self.setup_ui()

    def setup_ui(self):
        """Setup the user interface."""
        # Main notebook for tabs
        self.notebook = ttk.Notebook(self.window)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Create tabs
        self.create_profile_tab()
        self.create_matches_tab()
        self.create_groups_tab()
        self.create_study_rooms_tab()
        self.create_qa_board_tab()
        self.create_analytics_tab()

    # ========== Helper Methods ==========

    def _load_available_modules(self):
        """Load available modules/courses for dropdowns."""
        from education_system.university_system.infrastructure.database.db import get_connection

        try:
            user_info = self.auth.get_current_user()
            user_id = user_info.get('id')
            user_role = user_info.get('role', '').lower()

            with get_connection() as conn:
                if user_role == 'admin':
                    # Admin can see all active modules
                    modules = conn.execute("""
                        SELECT DISTINCT module_code, module_name
                        FROM modules
                        WHERE is_active = 1
                        ORDER BY module_code
                    """).fetchall()
                else:
                    # Students see only their enrolled modules
                    modules = conn.execute("""
                        SELECT DISTINCT m.module_code, m.module_name
                        FROM modules m
                        INNER JOIN student_modules sm ON m.module_code = sm.module_code
                        WHERE sm.student_id = ?
                        AND m.is_active = 1
                        ORDER BY m.module_code
                    """, (user_id,)).fetchall()

                # Format module list
                self.available_modules = [""] + [f"{m['module_code']} - {m['module_name']}" for m in modules]

        except Exception as e:
            self.available_modules = [""]
            print(f"Error loading modules: {e}")

    def _get_module_code_from_selection(self, selection):
        """Extract module code from combobox selection."""
        if not selection or selection == "":
            return None
        return selection.split(' - ')[0].strip()

    # ========== Profile Tab ==========

    def create_profile_tab(self):
        """Create study profile management tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="My Profile")

        # Header
        header = ttk.Label(tab, text="My Study Profile", font=('Arial', 16, 'bold'))
        header.pack(pady=10)

        # Profile display frame
        self.profile_display = ttk.Frame(tab)
        self.profile_display.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # Buttons
        button_frame = ttk.Frame(tab)
        button_frame.pack(pady=10)

        ttk.Button(button_frame, text="Create/Update Profile", command=self.open_profile_editor).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Refresh", command=self.load_profile).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Compatibility Info", command=self.show_compatibility_info).pack(side=tk.LEFT, padx=5)

        # Load profile
        self.load_profile()

    def load_profile(self):
        """Load and display user's study profile."""
        # Clear display
        for widget in self.profile_display.winfo_children():
            widget.destroy()

        user_id = self.auth.get_current_user()['username']
        profile = self.service.get_study_profile(user_id)

        if not profile:
            # No profile exists
            no_profile_label = ttk.Label(
                self.profile_display,
                text="You haven't created a study profile yet.\n\n"
                     "Create a profile to find compatible study partners!",
                font=('Arial', 12),
                justify=tk.CENTER
            )
            no_profile_label.pack(pady=50)
            return

        # Display profile in a nice layout
        main_frame = ttk.Frame(self.profile_display)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Left column - preferences
        left_frame = ttk.LabelFrame(main_frame, text="Study Preferences", padding=10)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        preferences = [
            ("Study Style:", profile['study_style']),
            ("Preferred Time:", profile['preferred_time']),
            ("Group Size:", profile['group_size_preference']),
            ("Communication:", profile['communication_style']),
            ("Noise Level:", profile['noise_preference']),
        ]

        for label, value in preferences:
            frame = ttk.Frame(left_frame)
            frame.pack(fill=tk.X, pady=5)
            ttk.Label(frame, text=label, font=('Arial', 10, 'bold'), width=18).pack(side=tk.LEFT)
            ttk.Label(frame, text=value, font=('Arial', 10)).pack(side=tk.LEFT)

        # Right column - availability and interests
        right_frame = ttk.LabelFrame(main_frame, text="Availability & Interests", padding=10)
        right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        if profile['availability']:
            ttk.Label(right_frame, text="Availability:", font=('Arial', 10, 'bold')).pack(anchor=tk.W, pady=5)
            avail_text = scrolledtext.ScrolledText(right_frame, height=5, width=40, wrap=tk.WORD)
            avail_text.pack(fill=tk.BOTH, expand=True, pady=5)
            avail_text.insert('1.0', '\n'.join(profile['availability']))
            avail_text.config(state='disabled')

        if profile['interests']:
            ttk.Label(right_frame, text="Interests:", font=('Arial', 10, 'bold')).pack(anchor=tk.W, pady=5)
            interest_text = scrolledtext.ScrolledText(right_frame, height=5, width=40, wrap=tk.WORD)
            interest_text.pack(fill=tk.BOTH, expand=True, pady=5)
            interest_text.insert('1.0', ', '.join(profile['interests']))
            interest_text.config(state='disabled')

        # Bottom - metadata
        meta_frame = ttk.Frame(self.profile_display)
        meta_frame.pack(fill=tk.X, pady=10)
        ttk.Label(meta_frame, text=f"Created: {profile['created_at']} | Last Updated: {profile['updated_at']}",
                  font=('Arial', 9, 'italic')).pack()

    def open_profile_editor(self):
        """Open dialog to create/update profile."""
        dialog = tk.Toplevel(self.window)
        dialog.title("Edit Study Profile")
        dialog.geometry("600x700")

        ttk.Label(dialog, text="Study Profile Editor", font=('Arial', 14, 'bold')).pack(pady=10)

        # Get current profile if exists
        user_id = self.auth.get_current_user()['username']
        current_profile = self.service.get_study_profile(user_id)

        # Create form
        form_frame = ttk.Frame(dialog)
        form_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # Study Style
        ttk.Label(form_frame, text="Study Style:").grid(row=0, column=0, sticky=tk.W, pady=5)
        style_var = tk.StringVar(value=current_profile['study_style'] if current_profile else "Visual")
        style_combo = ttk.Combobox(form_frame, textvariable=style_var, values=STUDY_STYLES, state='readonly', width=30)
        style_combo.grid(row=0, column=1, pady=5)

        # Preferred Time
        ttk.Label(form_frame, text="Preferred Time:").grid(row=1, column=0, sticky=tk.W, pady=5)
        time_var = tk.StringVar(value=current_profile['preferred_time'] if current_profile else "Evening")
        time_combo = ttk.Combobox(form_frame, textvariable=time_var, values=PREFERRED_TIMES, state='readonly', width=30)
        time_combo.grid(row=1, column=1, pady=5)

        # Group Size
        ttk.Label(form_frame, text="Group Size:").grid(row=2, column=0, sticky=tk.W, pady=5)
        size_var = tk.StringVar(value=current_profile['group_size_preference'] if current_profile else "Small (2-4)")
        size_combo = ttk.Combobox(form_frame, textvariable=size_var, values=GROUP_SIZES, state='readonly', width=30)
        size_combo.grid(row=2, column=1, pady=5)

        # Communication Style
        ttk.Label(form_frame, text="Communication:").grid(row=3, column=0, sticky=tk.W, pady=5)
        comm_var = tk.StringVar(value=current_profile['communication_style'] if current_profile else "Collaborative")
        comm_combo = ttk.Combobox(form_frame, textvariable=comm_var, values=COMMUNICATION_STYLES, state='readonly', width=30)
        comm_combo.grid(row=3, column=1, pady=5)

        # Noise Preference
        ttk.Label(form_frame, text="Noise Level:").grid(row=4, column=0, sticky=tk.W, pady=5)
        noise_var = tk.StringVar(value=current_profile['noise_preference'] if current_profile else "Quiet")
        noise_combo = ttk.Combobox(form_frame, textvariable=noise_var, values=NOISE_PREFERENCES, state='readonly', width=30)
        noise_combo.grid(row=4, column=1, pady=5)

        # Availability
        ttk.Label(form_frame, text="Availability:").grid(row=5, column=0, sticky=tk.W, pady=5)
        ttk.Label(form_frame, text="(one per line)", font=('Arial', 8, 'italic')).grid(row=6, column=0, sticky=tk.W)
        avail_text = scrolledtext.ScrolledText(form_frame, height=5, width=35, wrap=tk.WORD)
        avail_text.grid(row=5, column=1, rowspan=2, pady=5)
        if current_profile and current_profile['availability']:
            avail_text.insert('1.0', '\n'.join(current_profile['availability']))

        # Interests
        ttk.Label(form_frame, text="Interests:").grid(row=7, column=0, sticky=tk.W, pady=5)
        ttk.Label(form_frame, text="(comma-separated)", font=('Arial', 8, 'italic')).grid(row=8, column=0, sticky=tk.W)
        interests_text = scrolledtext.ScrolledText(form_frame, height=5, width=35, wrap=tk.WORD)
        interests_text.grid(row=7, column=1, rowspan=2, pady=5)
        if current_profile and current_profile['interests']:
            interests_text.insert('1.0', ', '.join(current_profile['interests']))

        # Buttons
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=20)

        def save_profile():
            availability = [line.strip() for line in avail_text.get('1.0', tk.END).strip().split('\n') if line.strip()]
            interests = [i.strip() for i in interests_text.get('1.0', tk.END).strip().split(',') if i.strip()]

            try:
                self.service.create_study_profile(
                    student_id=user_id,
                    study_style=style_var.get(),
                    preferred_time=time_var.get(),
                    group_size_preference=size_var.get(),
                    communication_style=comm_var.get(),
                    noise_preference=noise_var.get(),
                    availability=availability,
                    interests=interests
                )
                messagebox.showinfo("Success", "Study profile saved successfully!")
                dialog.destroy()
                self.load_profile()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(button_frame, text="Save Profile", command=save_profile).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def show_compatibility_info(self):
        """Show compatibility scoring information."""
        info_text = """COMPATIBILITY SCORING

Your compatibility with other students is calculated based on:

1. Study Style Match (25% weight)
   Visual, Auditory, Kinesthetic, or Reading/Writing

2. Preferred Time Match (20% weight)
   Morning, Afternoon, Evening, or Night

3. Group Size Preference (15% weight)
   Solo, Small, Medium, or Large groups

4. Communication Style (20% weight)
   Collaborative, Independent, or Mixed

5. Noise Preference (10% weight)
   Quiet, Moderate, or Lively environments

6. Interest Overlap (10% weight)
   Shared academic interests and subjects

Minimum Threshold: 30%
High Compatibility: 70%+
        """
        messagebox.showinfo("Compatibility Scoring", info_text)

    # ========== Matches Tab ==========

    def create_matches_tab(self):
        """Create study partner matches tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Find Partners")

        # Header
        header = ttk.Label(tab, text="Find Compatible Study Partners", font=('Arial', 16, 'bold'))
        header.pack(pady=10)

        # Search controls
        search_frame = ttk.Frame(tab)
        search_frame.pack(pady=10)

        ttk.Label(search_frame, text="Module (optional):").pack(side=tk.LEFT, padx=5)
        self.match_course_var = tk.StringVar()
        match_course_combo = ttk.Combobox(search_frame, textvariable=self.match_course_var,
                                         width=30, state='readonly', values=self.available_modules)
        match_course_combo.pack(side=tk.LEFT, padx=5)

        ttk.Label(search_frame, text="Max results:").pack(side=tk.LEFT, padx=5)
        self.match_limit_var = tk.IntVar(value=10)
        ttk.Spinbox(search_frame, from_=5, to=50, textvariable=self.match_limit_var, width=10).pack(side=tk.LEFT, padx=5)

        ttk.Button(search_frame, text="Find Matches", command=self.find_matches).pack(side=tk.LEFT, padx=10)

        # Matches display
        columns = ('Name', 'ID', 'Compatibility', 'Style', 'Time', 'Reason')
        self.matches_tree = ttk.Treeview(tab, columns=columns, show='headings', height=15)

        for col in columns:
            self.matches_tree.heading(col, text=col)

        self.matches_tree.column('Name', width=150)
        self.matches_tree.column('ID', width=100)
        self.matches_tree.column('Compatibility', width=120)
        self.matches_tree.column('Style', width=120)
        self.matches_tree.column('Time', width=100)
        self.matches_tree.column('Reason', width=400)

        self.matches_tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Scrollbar
        scrollbar = ttk.Scrollbar(tab, orient=tk.VERTICAL, command=self.matches_tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.matches_tree.configure(yscrollcommand=scrollbar.set)

        # Action buttons
        action_frame = ttk.Frame(tab)
        action_frame.pack(pady=10)

        ttk.Button(action_frame, text="Send Match Suggestion", command=self.send_match_suggestion).pack(side=tk.LEFT, padx=5)

    def find_matches(self):
        """Find and display study partner matches."""
        user_id = self.auth.get_current_user()['username']

        # Check profile
        profile = self.service.get_study_profile(user_id)
        if not profile:
            messagebox.showwarning("No Profile", "Please create a study profile first!")
            self.notebook.select(0)  # Switch to profile tab
            return

        # Clear tree
        for item in self.matches_tree.get_children():
            self.matches_tree.delete(item)

        # Extract module code from selection
        course_id = self._get_module_code_from_selection(self.match_course_var.get())
        limit = self.match_limit_var.get()

        try:
            matches = self.service.find_study_matches(user_id, course_id, limit)

            if not matches:
                messagebox.showinfo("No Matches", "No compatible study partners found.\nTry adjusting your search criteria.")
                return

            for match in matches:
                compatibility = match['compatibility_score']
                bars = "█" * int(compatibility / 10) + "░" * (10 - int(compatibility / 10))
                compat_display = f"{bars} {compatibility}%"

                self.matches_tree.insert('', tk.END, values=(
                    match['name'],
                    match['student_id'],
                    compat_display,
                    match['study_style'],
                    match['preferred_time'],
                    match['match_reason']
                ), tags=(match['student_id'],))

            messagebox.showinfo("Success", f"Found {len(matches)} compatible study partners!")

        except Exception as e:
            messagebox.showerror("Error", str(e))

    def send_match_suggestion(self):
        """Send match suggestion to selected partner."""
        selection = self.matches_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a match first.")
            return

        item = self.matches_tree.item(selection[0])
        suggested_id = item['tags'][0]

        user_id = self.auth.get_current_user()['username']
        course_id = self.match_course_var.get().strip() or None

        try:
            suggestion_id = self.service.create_match_suggestion(user_id, suggested_id, course_id)
            messagebox.showinfo("Success", f"Match suggestion sent! (ID: {suggestion_id})")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ========== Study Groups Tab ==========

    def create_groups_tab(self):
        """Create study groups management tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Study Groups")

        # Header
        header = ttk.Label(tab, text="Study Groups", font=('Arial', 16, 'bold'))
        header.pack(pady=10)

        # Sub-notebook for my groups vs browse
        sub_notebook = ttk.Notebook(tab)
        sub_notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # My Groups tab
        my_groups_frame = ttk.Frame(sub_notebook)
        sub_notebook.add(my_groups_frame, text="My Groups")
        self.setup_my_groups_tab(my_groups_frame)

        # Browse Groups tab
        browse_groups_frame = ttk.Frame(sub_notebook)
        sub_notebook.add(browse_groups_frame, text="Browse & Join")
        self.setup_browse_groups_tab(browse_groups_frame)

        # Create Group button
        button_frame = ttk.Frame(tab)
        button_frame.pack(pady=10)
        ttk.Button(button_frame, text="Create New Group", command=self.create_study_group_dialog).pack()

    def setup_my_groups_tab(self, parent):
        """Setup my groups display."""
        # Refresh button
        ttk.Button(parent, text="Refresh", command=self.load_my_groups).pack(pady=5)

        # Groups display
        columns = ('ID', 'Name', 'Course', 'Role', 'Members', 'Type', 'Status')
        self.my_groups_tree = ttk.Treeview(parent, columns=columns, show='headings', height=12)

        for col in columns:
            self.my_groups_tree.heading(col, text=col)

        self.my_groups_tree.column('ID', width=50)
        self.my_groups_tree.column('Name', width=200)
        self.my_groups_tree.column('Course', width=100)
        self.my_groups_tree.column('Role', width=80)
        self.my_groups_tree.column('Members', width=80)
        self.my_groups_tree.column('Type', width=80)
        self.my_groups_tree.column('Status', width=80)

        self.my_groups_tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Action buttons
        action_frame = ttk.Frame(parent)
        action_frame.pack(pady=10)
        ttk.Button(action_frame, text="View Details", command=self.view_group_details).pack(side=tk.LEFT, padx=5)

        self.load_my_groups()

    def load_my_groups(self):
        """Load user's study groups."""
        for item in self.my_groups_tree.get_children():
            self.my_groups_tree.delete(item)

        user_id = self.auth.get_current_user()['username']

        try:
            groups = self.service.get_student_study_groups(user_id)

            for group in groups:
                self.my_groups_tree.insert('', tk.END, values=(
                    group['group_id'],
                    group['group_name'],
                    group['course_id'],
                    group['role'],
                    f"{group['current_members']}/{group['max_members']}",
                    'Virtual' if group['is_virtual'] else 'In-Person',
                    group['status']
                ), tags=(group['group_id'],))

        except Exception as e:
            messagebox.showerror("Error", str(e))

    def setup_browse_groups_tab(self, parent):
        """Setup browse groups display."""
        # Search controls
        search_frame = ttk.Frame(parent)
        search_frame.pack(pady=10)

        ttk.Label(search_frame, text="Module:").pack(side=tk.LEFT, padx=5)
        self.browse_course_var = tk.StringVar()
        browse_course_combo = ttk.Combobox(search_frame, textvariable=self.browse_course_var,
                                          width=30, state='readonly', values=self.available_modules)
        browse_course_combo.pack(side=tk.LEFT, padx=5)
        ttk.Button(search_frame, text="Search", command=self.browse_groups).pack(side=tk.LEFT, padx=10)

        # Groups display
        columns = ('ID', 'Name', 'Members', 'Type', 'Location', 'Schedule')
        self.browse_groups_tree = ttk.Treeview(parent, columns=columns, show='headings', height=12)

        for col in columns:
            self.browse_groups_tree.heading(col, text=col)

        self.browse_groups_tree.column('ID', width=50)
        self.browse_groups_tree.column('Name', width=200)
        self.browse_groups_tree.column('Members', width=80)
        self.browse_groups_tree.column('Type', width=80)
        self.browse_groups_tree.column('Location', width=150)
        self.browse_groups_tree.column('Schedule', width=200)

        self.browse_groups_tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Action button
        ttk.Button(parent, text="Join Selected Group", command=self.join_group).pack(pady=10)

    def browse_groups(self):
        """Browse available study groups."""
        # Extract module code from selection
        course_id = self._get_module_code_from_selection(self.browse_course_var.get())
        if not course_id:
            messagebox.showwarning("Missing Input", "Please select a module.")
            return

        for item in self.browse_groups_tree.get_children():
            self.browse_groups_tree.delete(item)

        try:
            groups = self.service.get_available_study_groups(course_id)

            if not groups:
                messagebox.showinfo("No Groups", f"No available study groups found for {course_id}.")
                return

            for group in groups:
                self.browse_groups_tree.insert('', tk.END, values=(
                    group['group_id'],
                    group['group_name'],
                    f"{group['current_members']}/{group['max_members']}",
                    'Virtual' if group['is_virtual'] else 'In-Person',
                    group['location'] or '',
                    group['meeting_schedule'] or ''
                ), tags=(group['group_id'],))

        except Exception as e:
            messagebox.showerror("Error", str(e))

    def create_study_group_dialog(self):
        """Open dialog to create study group."""
        dialog = tk.Toplevel(self.window)
        dialog.title("Create Study Group")
        dialog.geometry("500x450")

        ttk.Label(dialog, text="Create Study Group", font=('Arial', 14, 'bold')).pack(pady=10)

        form_frame = ttk.Frame(dialog)
        form_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # Module
        ttk.Label(form_frame, text="Module:").grid(row=0, column=0, sticky=tk.W, pady=5)
        course_var = tk.StringVar()
        course_combo = ttk.Combobox(form_frame, textvariable=course_var, width=28,
                                    state='readonly', values=self.available_modules)
        course_combo.grid(row=0, column=1, pady=5)

        # Group Name
        ttk.Label(form_frame, text="Group Name:").grid(row=1, column=0, sticky=tk.W, pady=5)
        name_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=name_var, width=30).grid(row=1, column=1, pady=5)

        # Max Members
        ttk.Label(form_frame, text="Max Members:").grid(row=2, column=0, sticky=tk.W, pady=5)
        max_var = tk.IntVar(value=6)
        ttk.Spinbox(form_frame, from_=2, to=20, textvariable=max_var, width=28).grid(row=2, column=1, pady=5)

        # Virtual checkbox
        is_virtual_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(form_frame, text="Virtual Group", variable=is_virtual_var).grid(row=3, column=0, columnspan=2, pady=10)

        # Location
        ttk.Label(form_frame, text="Location/Platform:").grid(row=4, column=0, sticky=tk.W, pady=5)
        location_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=location_var, width=30).grid(row=4, column=1, pady=5)

        # Schedule
        ttk.Label(form_frame, text="Meeting Schedule:").grid(row=5, column=0, sticky=tk.W, pady=5)
        schedule_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=schedule_var, width=30).grid(row=5, column=1, pady=5)

        # Buttons
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=20)

        def create_group():
            # Extract module code from selection
            course = self._get_module_code_from_selection(course_var.get())
            name = name_var.get().strip()

            if not course or not name:
                messagebox.showerror("Missing Input", "Module and Group Name are required.")
                return

            user_id = self.auth.get_current_user()['username']

            try:
                group_id = self.service.create_study_group(
                    course_id=course,
                    group_name=name,
                    creator_id=user_id,
                    max_members=max_var.get(),
                    meeting_schedule=schedule_var.get() or None,
                    location=location_var.get() or None,
                    is_virtual=is_virtual_var.get()
                )
                messagebox.showinfo("Success", f"Study group created! (ID: {group_id})")
                dialog.destroy()
                self.load_my_groups()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(button_frame, text="Create", command=create_group).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def join_group(self):
        """Join selected study group."""
        selection = self.browse_groups_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a group to join.")
            return

        item = self.browse_groups_tree.item(selection[0])
        group_id = int(item['tags'][0])

        user_id = self.auth.get_current_user()['username']

        try:
            if self.service.join_study_group(group_id, user_id):
                messagebox.showinfo("Success", "Successfully joined the study group!")
                self.load_my_groups()
            else:
                messagebox.showinfo("Already Member", "You are already a member of this group.")
        except ValueError as e:
            messagebox.showerror("Error", str(e))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def view_group_details(self):
        """View detailed group information."""
        selection = self.my_groups_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a group first.")
            return

        item = self.my_groups_tree.item(selection[0])
        group_id = int(item['tags'][0])

        try:
            group_data = self.service.get_study_group(group_id)
            if not group_data:
                messagebox.showerror("Error", "Group not found.")
                return

            # Create details window
            details_window = tk.Toplevel(self.window)
            details_window.title(f"Group Details - {group_data['group']['group_name']}")
            details_window.geometry("700x600")

            # Group info
            info_frame = ttk.LabelFrame(details_window, text="Group Information", padding=10)
            info_frame.pack(fill=tk.X, padx=10, pady=10)

            group = group_data['group']
            info_text = f"""
Name: {group['group_name']}
Course: {group['course_id']}
Type: {'Virtual' if group['is_virtual'] else 'In-Person'}
Members: {group['current_members']}/{group['max_members']}
Status: {group['status']}
Location: {group['location'] or 'N/A'}
Schedule: {group['meeting_schedule'] or 'N/A'}
Created: {group['created_at']}
            """
            ttk.Label(info_frame, text=info_text, justify=tk.LEFT).pack()

            # Members list
            members_frame = ttk.LabelFrame(details_window, text="Members", padding=10)
            members_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            columns = ('Name', 'ID', 'Role', 'Joined', 'Attendance', 'Contribution')
            members_tree = ttk.Treeview(members_frame, columns=columns, show='headings', height=10)

            for col in columns:
                members_tree.heading(col, text=col)

            for member in group_data['members']:
                members_tree.insert('', tk.END, values=(
                    f"{member['first_name']} {member['last_name']}",
                    member['student_id'],
                    member['role'],
                    member['joined_at'][:10],
                    member['attendance_count'],
                    member['contribution_score']
                ))

            members_tree.pack(fill=tk.BOTH, expand=True)

        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ========== Virtual Study Rooms Tab ==========

    def create_study_rooms_tab(self):
        """Create virtual study rooms tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Study Rooms")

        # Header
        header = ttk.Label(tab, text="Virtual Study Rooms", font=('Arial', 16, 'bold'))
        header.pack(pady=10)

        # Controls
        control_frame = ttk.Frame(tab)
        control_frame.pack(pady=10)

        ttk.Button(control_frame, text="Create Room", command=self.create_study_room_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Join by Code", command=self.join_room_by_code).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Refresh", command=self.load_study_rooms).pack(side=tk.LEFT, padx=5)

        # Rooms display
        columns = ('Code', 'Name', 'Host', 'Participants', 'Course', 'Pomodoro', 'Sessions')
        self.rooms_tree = ttk.Treeview(tab, columns=columns, show='headings', height=15)

        for col in columns:
            self.rooms_tree.heading(col, text=col)

        self.rooms_tree.column('Code', width=80)
        self.rooms_tree.column('Name', width=200)
        self.rooms_tree.column('Host', width=150)
        self.rooms_tree.column('Participants', width=100)
        self.rooms_tree.column('Course', width=100)
        self.rooms_tree.column('Pomodoro', width=120)
        self.rooms_tree.column('Sessions', width=80)

        self.rooms_tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.load_study_rooms()

    def load_study_rooms(self):
        """Load active study rooms."""
        for item in self.rooms_tree.get_children():
            self.rooms_tree.delete(item)

        try:
            rooms = self.service.get_active_study_rooms()

            for room in rooms:
                pomodoro_info = f"{room['work_duration']}m/{room['break_duration']}m" if room['pomodoro_enabled'] else "Disabled"

                self.rooms_tree.insert('', tk.END, values=(
                    room['room_code'],
                    room['room_name'],
                    f"{room['first_name']} {room['last_name']}",
                    f"{room['current_participants']}/{room['max_participants']}",
                    room['course_id'] or 'N/A',
                    pomodoro_info,
                    room['session_count']
                ))

        except Exception as e:
            messagebox.showerror("Error", str(e))

    def create_study_room_dialog(self):
        """Open dialog to create study room."""
        dialog = tk.Toplevel(self.window)
        dialog.title("Create Virtual Study Room")
        dialog.geometry("500x450")

        ttk.Label(dialog, text="Create Virtual Study Room", font=('Arial', 14, 'bold')).pack(pady=10)

        form_frame = ttk.Frame(dialog)
        form_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # Room Name
        ttk.Label(form_frame, text="Room Name:").grid(row=0, column=0, sticky=tk.W, pady=5)
        name_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=name_var, width=30).grid(row=0, column=1, pady=5)

        # Module (optional)
        ttk.Label(form_frame, text="Module (optional):").grid(row=1, column=0, sticky=tk.W, pady=5)
        course_var = tk.StringVar()
        course_combo = ttk.Combobox(form_frame, textvariable=course_var, width=28,
                                    state='readonly', values=self.available_modules)
        course_combo.grid(row=1, column=1, pady=5)

        # Max Participants
        ttk.Label(form_frame, text="Max Participants:").grid(row=2, column=0, sticky=tk.W, pady=5)
        max_var = tk.IntVar(value=8)
        ttk.Spinbox(form_frame, from_=2, to=20, textvariable=max_var, width=28).grid(row=2, column=1, pady=5)

        # Pomodoro settings
        pomodoro_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(form_frame, text="Enable Pomodoro Timer", variable=pomodoro_var).grid(row=3, column=0, columnspan=2, pady=10)

        ttk.Label(form_frame, text="Work Duration (min):").grid(row=4, column=0, sticky=tk.W, pady=5)
        work_var = tk.IntVar(value=25)
        ttk.Spinbox(form_frame, from_=5, to=60, textvariable=work_var, width=28).grid(row=4, column=1, pady=5)

        ttk.Label(form_frame, text="Break Duration (min):").grid(row=5, column=0, sticky=tk.W, pady=5)
        break_var = tk.IntVar(value=5)
        ttk.Spinbox(form_frame, from_=5, to=30, textvariable=break_var, width=28).grid(row=5, column=1, pady=5)

        # Buttons
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=20)

        def create_room():
            name = name_var.get().strip()
            if not name:
                messagebox.showerror("Missing Input", "Room name is required.")
                return

            user_id = self.auth.get_current_user()['username']
            # Extract module code from selection (optional)
            course = self._get_module_code_from_selection(course_var.get())

            try:
                room = self.service.create_virtual_study_room(
                    host_id=user_id,
                    room_name=name,
                    course_id=course,
                    max_participants=max_var.get(),
                    pomodoro_enabled=pomodoro_var.get(),
                    work_duration=work_var.get(),
                    break_duration=break_var.get()
                )
                messagebox.showinfo("Success", f"Room created!\n\nRoom Code: {room['room_code']}\n\nShare this code with others to invite them.")
                dialog.destroy()
                self.load_study_rooms()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(button_frame, text="Create", command=create_room).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def join_room_by_code(self):
        """Join room by entering code."""
        code = tk.simpledialog.askstring("Join Room", "Enter room code:")
        if not code:
            return

        user_id = self.auth.get_current_user()['username']

        try:
            room = self.service.join_virtual_study_room(code.upper(), user_id)
            messagebox.showinfo("Success", f"Joined room: {room['room_name']}")
            self.load_study_rooms()
        except ValueError as e:
            messagebox.showerror("Error", str(e))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ========== Q&A Board Tab ==========

    def create_qa_board_tab(self):
        """Create Q&A board tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Q&A Board")

        # Header
        header = ttk.Label(tab, text="Anonymous Q&A Board", font=('Arial', 16, 'bold'))
        header.pack(pady=10)

        # Controls
        control_frame = ttk.Frame(tab)
        control_frame.pack(pady=10)

        ttk.Label(control_frame, text="Module:").pack(side=tk.LEFT, padx=5)
        self.qa_course_var = tk.StringVar()
        qa_course_combo = ttk.Combobox(control_frame, textvariable=self.qa_course_var,
                                       width=30, state='readonly', values=self.available_modules)
        qa_course_combo.pack(side=tk.LEFT, padx=5)

        ttk.Label(control_frame, text="Sort:").pack(side=tk.LEFT, padx=5)
        self.qa_sort_var = tk.StringVar(value="recent")
        ttk.Combobox(control_frame, textvariable=self.qa_sort_var, values=["recent", "popular", "unanswered"],
                     state='readonly', width=12).pack(side=tk.LEFT, padx=5)

        ttk.Button(control_frame, text="Load Questions", command=self.load_questions).pack(side=tk.LEFT, padx=10)
        ttk.Button(control_frame, text="Ask Question", command=self.ask_question_dialog).pack(side=tk.LEFT, padx=5)

        # Questions display
        columns = ('ID', 'Title', 'Category', 'Votes', 'Answers', 'Status')
        self.qa_tree = ttk.Treeview(tab, columns=columns, show='headings', height=12)

        for col in columns:
            self.qa_tree.heading(col, text=col)

        self.qa_tree.column('ID', width=60)
        self.qa_tree.column('Title', width=400)
        self.qa_tree.column('Category', width=120)
        self.qa_tree.column('Votes', width=80)
        self.qa_tree.column('Answers', width=80)
        self.qa_tree.column('Status', width=100)

        self.qa_tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Action buttons
        action_frame = ttk.Frame(tab)
        action_frame.pack(pady=10)

        ttk.Button(action_frame, text="View Question", command=self.view_question_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Answer Question", command=self.answer_question_dialog).pack(side=tk.LEFT, padx=5)

    def load_questions(self):
        """Load questions from Q&A board."""
        # Extract module code from selection
        course_id = self._get_module_code_from_selection(self.qa_course_var.get())
        if not course_id:
            messagebox.showwarning("Missing Input", "Please select a module.")
            return

        for item in self.qa_tree.get_children():
            self.qa_tree.delete(item)

        try:
            questions = self.service.get_course_questions(course_id, sort_by=self.qa_sort_var.get())

            if not questions:
                messagebox.showinfo("No Questions", f"No questions found for {course_id}.")
                return

            for q in questions:
                status = "✓ Resolved" if q['is_resolved'] else ("Answered" if q['is_answered'] else "Open")
                votes = q['upvotes'] - q['downvotes']

                self.qa_tree.insert('', tk.END, values=(
                    q['question_id'],
                    q['question_title'],
                    q['category'],
                    f"+{votes}" if votes >= 0 else str(votes),
                    q['answer_count'],
                    status
                ), tags=(q['question_id'],))

        except Exception as e:
            messagebox.showerror("Error", str(e))

    def ask_question_dialog(self):
        """Open dialog to ask a question."""
        # Extract module code from selection
        course_id = self._get_module_code_from_selection(self.qa_course_var.get())
        if not course_id:
            messagebox.showwarning("Missing Input", "Please select a module first.")
            return

        dialog = tk.Toplevel(self.window)
        dialog.title("Ask Question (Anonymous)")
        dialog.geometry("600x500")

        ttk.Label(dialog, text="Ask Question", font=('Arial', 14, 'bold')).pack(pady=10)

        form_frame = ttk.Frame(dialog)
        form_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # Title
        ttk.Label(form_frame, text="Question Title:").pack(anchor=tk.W, pady=5)
        title_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=title_var, width=60).pack(fill=tk.X, pady=5)

        # Question text
        ttk.Label(form_frame, text="Question Details:").pack(anchor=tk.W, pady=5)
        question_text = scrolledtext.ScrolledText(form_frame, height=10, width=60, wrap=tk.WORD)
        question_text.pack(fill=tk.BOTH, expand=True, pady=5)

        # Category
        ttk.Label(form_frame, text="Category:").pack(anchor=tk.W, pady=5)
        category_var = tk.StringVar(value=QA_CATEGORIES[0])
        ttk.Combobox(form_frame, textvariable=category_var, values=QA_CATEGORIES, state='readonly').pack(anchor=tk.W, pady=5)

        # Difficulty
        ttk.Label(form_frame, text="Difficulty:").pack(anchor=tk.W, pady=5)
        difficulty_var = tk.StringVar(value=DIFFICULTY_LEVELS[1])
        ttk.Combobox(form_frame, textvariable=difficulty_var, values=DIFFICULTY_LEVELS, state='readonly').pack(anchor=tk.W, pady=5)

        # Buttons
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=20)

        def post_question():
            title = title_var.get().strip()
            text = question_text.get('1.0', tk.END).strip()

            if not title or not text:
                messagebox.showerror("Missing Input", "Please provide both title and question details.")
                return

            user_id = self.auth.get_current_user()['username']

            try:
                result = self.service.post_question(
                    course_id=course_id,
                    student_id=user_id,
                    question_title=title,
                    question_text=text,
                    category=category_var.get(),
                    difficulty_level=difficulty_var.get()
                )
                messagebox.showinfo("Success", f"Question posted!\n\nQuestion ID: {result['question_id']}\nYour anonymous ID: {result['anonymous_id']}")
                dialog.destroy()
                self.load_questions()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(button_frame, text="Post Question", command=post_question).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def view_question_dialog(self):
        """View question with answers."""
        selection = self.qa_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a question first.")
            return

        item = self.qa_tree.item(selection[0])
        question_id = int(item['tags'][0])

        try:
            data = self.service.get_question_with_answers(question_id)
            if not data:
                messagebox.showerror("Error", "Question not found.")
                return

            # Create view window
            view_window = tk.Toplevel(self.window)
            view_window.title(f"Question #{question_id}")
            view_window.geometry("800x700")

            # Question details
            question = data['question']
            answers = data['answers']

            # Header
            header_frame = ttk.Frame(view_window)
            header_frame.pack(fill=tk.X, padx=10, pady=10)

            ttk.Label(header_frame, text=question['question_title'], font=('Arial', 14, 'bold')).pack(anchor=tk.W)

            meta_text = f"By: {question['anonymous_id']} | Category: {question['category']} | Difficulty: {question['difficulty_level']}"
            ttk.Label(header_frame, text=meta_text, font=('Arial', 9, 'italic')).pack(anchor=tk.W)

            votes = question['upvotes'] - question['downvotes']
            status_text = f"Votes: {votes} | Views: {question['view_count']} | Posted: {question['created_at'][:16]}"
            ttk.Label(header_frame, text=status_text, font=('Arial', 9)).pack(anchor=tk.W)

            # Question text
            q_frame = ttk.LabelFrame(view_window, text="Question", padding=10)
            q_frame.pack(fill=tk.X, padx=10, pady=10)

            q_text = scrolledtext.ScrolledText(q_frame, height=6, width=80, wrap=tk.WORD)
            q_text.pack(fill=tk.BOTH, expand=True)
            q_text.insert('1.0', question['question_text'])
            q_text.config(state='disabled')

            # Answers
            answers_frame = ttk.LabelFrame(view_window, text=f"Answers ({len(answers)})", padding=10)
            answers_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            if answers:
                answers_text = scrolledtext.ScrolledText(answers_frame, height=15, width=80, wrap=tk.WORD)
                answers_text.pack(fill=tk.BOTH, expand=True)

                for i, ans in enumerate(answers, 1):
                    ans_votes = ans['upvotes'] - ans['downvotes']
                    accepted = " ✓ ACCEPTED" if ans['is_accepted'] else ""
                    instructor = " [INSTRUCTOR]" if ans['is_instructor_answer'] else ""

                    answers_text.insert(tk.END, f"\n{'='*70}\n")
                    answers_text.insert(tk.END, f"Answer #{i}{accepted}{instructor}\n")
                    answers_text.insert(tk.END, f"By: {ans['anonymous_id']} | Votes: {ans_votes} | Posted: {ans['created_at'][:16]}\n")
                    answers_text.insert(tk.END, f"{'-'*70}\n")
                    answers_text.insert(tk.END, f"{ans['answer_text']}\n")

                answers_text.config(state='disabled')
            else:
                ttk.Label(answers_frame, text="No answers yet. Be the first to answer!").pack()

        except Exception as e:
            messagebox.showerror("Error", str(e))

    def answer_question_dialog(self):
        """Open dialog to answer a question."""
        selection = self.qa_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a question to answer.")
            return

        item = self.qa_tree.item(selection[0])
        question_id = int(item['tags'][0])
        question_title = item['values'][1]

        dialog = tk.Toplevel(self.window)
        dialog.title(f"Answer Question #{question_id}")
        dialog.geometry("600x400")

        ttk.Label(dialog, text=f"Answer: {question_title}", font=('Arial', 12, 'bold')).pack(pady=10)

        form_frame = ttk.Frame(dialog)
        form_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        ttk.Label(form_frame, text="Your Answer:").pack(anchor=tk.W, pady=5)
        answer_text = scrolledtext.ScrolledText(form_frame, height=12, width=60, wrap=tk.WORD)
        answer_text.pack(fill=tk.BOTH, expand=True, pady=5)

        # Buttons
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=20)

        def post_answer():
            text = answer_text.get('1.0', tk.END).strip()

            if not text:
                messagebox.showerror("Missing Input", "Please enter an answer.")
                return

            user_id = self.auth.get_current_user()['username']

            try:
                answer_id = self.service.post_answer(
                    question_id=question_id,
                    student_id=user_id,
                    answer_text=text
                )
                messagebox.showinfo("Success", f"Answer posted! (ID: {answer_id})")
                dialog.destroy()
                self.load_questions()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(button_frame, text="Post Answer", command=post_answer).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    # ========== Analytics Tab ==========

    def create_analytics_tab(self):
        """Create analytics dashboard tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Analytics")

        # Header
        header = ttk.Label(tab, text="My Study Matching Analytics", font=('Arial', 16, 'bold'))
        header.pack(pady=10)

        # Refresh button
        ttk.Button(tab, text="Refresh Statistics", command=self.load_analytics).pack(pady=5)

        # Analytics display frame
        self.analytics_frame = ttk.Frame(tab)
        self.analytics_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        self.load_analytics()

    def load_analytics(self):
        """Load and display analytics."""
        # Clear frame
        for widget in self.analytics_frame.winfo_children():
            widget.destroy()

        user_id = self.auth.get_current_user()['username']

        try:
            analytics = self.service.get_study_matching_analytics(user_id)

            # Groups stats
            group_frame = ttk.LabelFrame(self.analytics_frame, text="Study Groups", padding=15)
            group_frame.pack(fill=tk.X, pady=10)

            group_stats = analytics.get('groups', {})
            if group_stats:
                stats_text = f"""
Total Groups: {group_stats.get('total_groups', 0)}
Active Groups: {group_stats.get('active_groups', 0)}
Average Contribution: {group_stats.get('avg_contribution', 0) or 0:.1f}
Total Attendance: {group_stats.get('total_attendance', 0)} sessions
                """
                ttk.Label(group_frame, text=stats_text, justify=tk.LEFT, font=('Arial', 10)).pack()
            else:
                ttk.Label(group_frame, text="No group activity yet").pack()

            # Virtual rooms stats
            room_frame = ttk.LabelFrame(self.analytics_frame, text="Virtual Study Rooms", padding=15)
            room_frame.pack(fill=tk.X, pady=10)

            room_stats = analytics.get('virtual_rooms', {})
            if room_stats:
                total_time = room_stats.get('total_study_time', 0) or 0
                stats_text = f"""
Rooms Joined: {room_stats.get('rooms_joined', 0)}
Total Study Time: {total_time} minutes ({total_time / 60:.1f} hours)
Pomodoro Sessions Completed: {room_stats.get('total_pomodoros', 0)}
                """
                ttk.Label(room_frame, text=stats_text, justify=tk.LEFT, font=('Arial', 10)).pack()
            else:
                ttk.Label(room_frame, text="No study room activity yet").pack()

            # Q&A stats
            qa_frame = ttk.LabelFrame(self.analytics_frame, text="Q&A Participation", padding=15)
            qa_frame.pack(fill=tk.X, pady=10)

            qa_stats = analytics.get('qa_participation', {})
            if qa_stats:
                stats_text = f"""
Questions Asked: {qa_stats.get('questions_asked', 0)}
Answers Given: {qa_stats.get('answers_given', 0)}
Question Upvotes: {qa_stats.get('question_upvotes', 0)}
Answer Upvotes: {qa_stats.get('answer_upvotes', 0)}
                """
                ttk.Label(qa_frame, text=stats_text, justify=tk.LEFT, font=('Arial', 10)).pack()
            else:
                ttk.Label(qa_frame, text="No Q&A activity yet").pack()

        except Exception as e:
            messagebox.showerror("Error", str(e))

    def run(self):
        """Run the GUI (for standalone testing)."""
        self.window.mainloop()


def main():
    """Main entry point for GUI."""
    root = tk.Tk()
    root.withdraw()
    app = StudyMatchingGUI(root)
    app.run()


if __name__ == "__main__":
    main()
