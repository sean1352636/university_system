"""
Roommate Finder GUI Interface

Full-featured GUI for roommate matching, profile management, and messaging.
"""

from education_system.systems.university.infrastructure.i18n import get_text as _t

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime
from typing import Optional, List, Dict
from education_system.systems.university.infrastructure.database.db import sqlite3
from education_system.systems.university.infrastructure.shared_context import get_auth
from education_system.systems.university.domain.operations.campus.housing.services.roommate_finder.roommate_service import RoommateService

class RoommateFinderGUI:
    """Main GUI for Roommate Finder System.

    Two construction modes:
      - RoommateFinderGUI(parent, auth=...)                — opens a Toplevel
      - RoommateFinderGUI(parent, auth=..., container=frame) — embeds into
        ``frame``, used by HousingGUI to host this as a student sub-view
    """

    def __init__(self, parent, auth=None, container=None):
        if container is not None:
            self._embed_parent = container
            self._is_embedded = True
            # self.root is only used for Toplevel dialogs spawned later
            self.root = container.winfo_toplevel()
        else:
            self.root = tk.Toplevel(parent)
            self.root.title(_t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.windows.roommate_finder', default="Roommate Finder"))
            self.root.geometry("1200x800")
            self._embed_parent = self.root
            self._is_embedded = False

        self.auth = auth or get_auth()
        self.service = RoommateService()

        # Store current profile
        self.current_profile = None

        # Question widgets storage
        self.question_widgets = []

        self.create_widgets()
        self.load_profile()

    def create_widgets(self):
        """Create all GUI widgets"""
        # Main container — lives inside the Toplevel or the embed frame
        main_frame = ttk.Frame(self._embed_parent, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        title = ttk.Label(main_frame, text=_t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.labels.roommate_finder', default="Roommate Finder"),
                         font=('Arial', 18, 'bold'))
        title.pack(pady=10)

        # Notebook for tabs
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Create tabs
        self.create_profile_tab()
        self.create_questionnaire_tab()
        self.create_matches_tab()
        self.create_messages_tab()
        self.create_stats_tab()

    def create_profile_tab(self):
        """Create Profile Management tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text=_t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.tabs.my_profile', default="My Profile"))

        # Scrollable frame
        canvas = tk.Canvas(tab)
        scrollbar = ttk.Scrollbar(tab, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Profile fields
        profile_frame = ttk.LabelFrame(scrollable_frame, text=_t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.labels.profile_information', default="Profile Information"), padding="10")
        profile_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Basic Information
        row = 0
        ttk.Label(profile_frame, text=_t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.labels.display_name', default="Display Name:")).grid(row=row, column=0, sticky=tk.W, pady=5)
        self.display_name_var = tk.StringVar()
        ttk.Entry(profile_frame, textvariable=self.display_name_var, width=40).grid(row=row, column=1, pady=5, sticky=tk.W)

        row += 1
        ttk.Label(profile_frame, text=_t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.labels.bio', default="Bio:")).grid(row=row, column=0, sticky=tk.NW, pady=5)
        self.bio_text = tk.Text(profile_frame, width=40, height=4)
        self.bio_text.grid(row=row, column=1, pady=5, sticky=tk.W)

        # Budget
        row += 1
        ttk.Label(profile_frame, text=_t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.labels.budget_month', default="Budget ($/month):")).grid(row=row, column=0, sticky=tk.W, pady=5)
        budget_frame = ttk.Frame(profile_frame)
        budget_frame.grid(row=row, column=1, sticky=tk.W, pady=5)

        ttk.Label(budget_frame, text=_t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.labels.min', default="Min:")).pack(side=tk.LEFT)
        self.budget_min_var = tk.StringVar()
        ttk.Entry(budget_frame, textvariable=self.budget_min_var, width=10).pack(side=tk.LEFT, padx=5)

        ttk.Label(budget_frame, text=_t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.labels.max', default="Max:")).pack(side=tk.LEFT, padx=(10, 0))
        self.budget_max_var = tk.StringVar()
        ttk.Entry(budget_frame, textvariable=self.budget_max_var, width=10).pack(side=tk.LEFT, padx=5)

        # Move-in date
        row += 1
        ttk.Label(profile_frame, text=_t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.labels.move_in_date_yyyy_mm_dd', default="Move-in Date (YYYY-MM-DD):")).grid(row=row, column=0, sticky=tk.W, pady=5)
        self.move_in_var = tk.StringVar()
        ttk.Entry(profile_frame, textvariable=self.move_in_var, width=20).grid(row=row, column=1, pady=5, sticky=tk.W)

        # Gender preference
        row += 1
        ttk.Label(profile_frame, text=_t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.labels.gender_preference', default="Gender Preference:")).grid(row=row, column=0, sticky=tk.W, pady=5)
        self.gender_pref_var = tk.StringVar()
        gender_combo = ttk.Combobox(profile_frame, textvariable=self.gender_pref_var,
                                    values=['No preference', 'Male', 'Female', 'Non-binary'],
                                    state='readonly', width=37)
        gender_combo.grid(row=row, column=1, pady=5, sticky=tk.W)
        gender_combo.current(0)

        # Age
        row += 1
        ttk.Label(profile_frame, text=_t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.labels.age', default="Age:")).grid(row=row, column=0, sticky=tk.W, pady=5)
        self.age_var = tk.StringVar()
        ttk.Entry(profile_frame, textvariable=self.age_var, width=10).grid(row=row, column=1, pady=5, sticky=tk.W)

        # Major
        row += 1
        ttk.Label(profile_frame, text=_t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.labels.major', default="Major:")).grid(row=row, column=0, sticky=tk.W, pady=5)
        self.major_var = tk.StringVar()
        ttk.Entry(profile_frame, textvariable=self.major_var, width=40).grid(row=row, column=1, pady=5, sticky=tk.W)

        # Year of Study
        row += 1
        ttk.Label(profile_frame, text=_t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.labels.year_of_study', default="Year of Study:")).grid(row=row, column=0, sticky=tk.W, pady=5)
        self.year_var = tk.StringVar()
        year_combo = ttk.Combobox(profile_frame, textvariable=self.year_var,
                                  values=['Freshman', 'Sophomore', 'Junior', 'Senior', 'Graduate'],
                                  state='readonly', width=37)
        year_combo.grid(row=row, column=1, pady=5, sticky=tk.W)

        # Smoking preference
        row += 1
        ttk.Label(profile_frame, text=_t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.labels.smoking_preference', default="Smoking Preference:")).grid(row=row, column=0, sticky=tk.W, pady=5)
        self.smoking_var = tk.StringVar()
        smoking_combo = ttk.Combobox(profile_frame, textvariable=self.smoking_var,
                                     values=['No', 'Yes', 'Occasionally'],
                                     state='readonly', width=37)
        smoking_combo.grid(row=row, column=1, pady=5, sticky=tk.W)
        smoking_combo.current(0)

        # Pet preference
        row += 1
        ttk.Label(profile_frame, text=_t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.labels.pet_preference', default="Pet Preference:")).grid(row=row, column=0, sticky=tk.W, pady=5)
        self.pet_var = tk.StringVar()
        pet_combo = ttk.Combobox(profile_frame, textvariable=self.pet_var,
                                values=['No pets', 'Cats only', 'Dogs only', 'Any pets welcome'],
                                state='readonly', width=37)
        pet_combo.grid(row=row, column=1, pady=5, sticky=tk.W)
        pet_combo.current(0)

        # Buttons
        button_frame = ttk.Frame(scrollable_frame)
        button_frame.pack(fill=tk.X, pady=10)

        ttk.Button(button_frame, text=_t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.buttons.save_profile', default="Save Profile"), command=self.save_profile).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.buttons.refresh', default="Refresh"), command=self.load_profile).pack(side=tk.LEFT, padx=5)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def create_questionnaire_tab(self):
        """Create Compatibility Questionnaire tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text=_t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.tabs.questionnaire', default="Questionnaire"))

        # Instructions
        ttk.Label(tab, text=_t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.labels.complete_this_questionnaire_to_find_compatible_roommates', default="Complete this questionnaire to find compatible roommates"),
                 font=('Arial', 12, 'bold')).pack(pady=10)

        # Scrollable frame for questions
        canvas = tk.Canvas(tab)
        scrollbar = ttk.Scrollbar(tab, orient="vertical", command=canvas.yview)
        self.questions_frame = ttk.Frame(canvas)

        self.questions_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=self.questions_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Load questions button
        button_frame = ttk.Frame(tab)
        button_frame.pack(fill=tk.X, pady=5)

        ttk.Button(button_frame, text=_t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.buttons.load_questionnaire', default="Load Questionnaire"), command=self.load_questionnaire).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.buttons.submit_answers', default="Submit Answers"), command=self.submit_questionnaire).pack(side=tk.LEFT, padx=5)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def create_matches_tab(self):
        """Create Roommate Matches tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text=_t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.tabs.matches', default="Matches"))

        # Top buttons
        button_frame = ttk.Frame(tab)
        button_frame.pack(fill=tk.X, pady=5)

        ttk.Button(button_frame, text=_t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.buttons.find_new_matches', default="Find New Matches"), command=self.find_matches).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.buttons.refresh_matches', default="Refresh Matches"), command=self.load_matches).pack(side=tk.LEFT, padx=5)

        # Matches list frame
        list_frame = ttk.LabelFrame(tab, text=_t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.labels.your_matches', default="Your Matches"), padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        # Treeview for matches
        columns = ('Match ID', 'Name', 'Score', 'Major', 'Year', 'Budget', 'Status')
        self.matches_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=15)

        for col in columns:
            self.matches_tree.heading(col, text=col)
            width = 150 if col == 'Name' else 100
            self.matches_tree.column(col, width=width)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.matches_tree.yview)
        self.matches_tree.configure(yscrollcommand=scrollbar.set)

        self.matches_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Match details frame
        details_frame = ttk.LabelFrame(tab, text=_t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.labels.match_details', default="Match Details"), padding="10")
        details_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self.match_details_text = scrolledtext.ScrolledText(details_frame, wrap=tk.WORD, height=10)
        self.match_details_text.pack(fill=tk.BOTH, expand=True)

        # Bind selection event
        self.matches_tree.bind('<<TreeviewSelect>>', self.on_match_selected)

        # Action buttons
        action_frame = ttk.Frame(tab)
        action_frame.pack(fill=tk.X, pady=5)

        ttk.Button(action_frame, text=_t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.buttons.mark_interested', default="Mark Interested"), command=lambda: self.update_match_status('Interested')).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text=_t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.buttons.mark_connected', default="Mark Connected"), command=lambda: self.update_match_status('Connected')).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text=_t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.buttons.decline', default="Decline"), command=lambda: self.update_match_status('Declined')).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text=_t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.buttons.send_message', default="Send Message"), command=self.open_message_dialog).pack(side=tk.LEFT, padx=5)

    def create_messages_tab(self):
        """Create Messages tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text=_t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.tabs.messages', default="Messages"))

        # Match selection
        select_frame = ttk.Frame(tab)
        select_frame.pack(fill=tk.X, pady=5)

        ttk.Label(select_frame, text=_t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.labels.select_match', default="Select Match:")).pack(side=tk.LEFT, padx=5)
        self.message_match_combo = ttk.Combobox(select_frame, width=50, state='readonly')
        self.message_match_combo.pack(side=tk.LEFT, padx=5)
        self.message_match_combo.bind('<<ComboboxSelected>>', self.load_messages)

        ttk.Button(select_frame, text=_t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.buttons.refresh', default="Refresh"), command=self.refresh_message_matches).pack(side=tk.LEFT, padx=5)

        # Messages display
        msg_frame = ttk.LabelFrame(tab, text=_t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.labels.conversation', default="Conversation"), padding="10")
        msg_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self.messages_text = scrolledtext.ScrolledText(msg_frame, wrap=tk.WORD, height=20)
        self.messages_text.pack(fill=tk.BOTH, expand=True)
        self.messages_text.config(state=tk.DISABLED)

        # Message input
        input_frame = ttk.Frame(tab)
        input_frame.pack(fill=tk.X, pady=5)

        ttk.Label(input_frame, text=_t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.labels.new_message', default="New Message:")).pack(anchor=tk.W)
        self.message_input = tk.Text(input_frame, height=3, wrap=tk.WORD)
        self.message_input.pack(fill=tk.X, pady=5)

        ttk.Button(input_frame, text=_t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.buttons.send_message', default="Send Message"), command=self.send_message).pack(anchor=tk.E)

    def create_stats_tab(self):
        """Create Statistics tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text=_t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.tabs.statistics', default="Statistics"))

        ttk.Label(tab, text=_t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.labels.roommate_finder_statistics', default="Roommate Finder Statistics"),
                 font=('Arial', 14, 'bold')).pack(pady=10)

        # Stats display
        stats_frame = ttk.LabelFrame(tab, text=_t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.labels.your_activity', default="Your Activity"), padding="10")
        stats_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self.stats_text = scrolledtext.ScrolledText(stats_frame, wrap=tk.WORD, height=25)
        self.stats_text.pack(fill=tk.BOTH, expand=True)

        # Refresh button
        ttk.Button(tab, text=_t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.buttons.refresh_statistics', default="Refresh Statistics"), command=self.load_statistics).pack(pady=10)

    # ======================== Helper Methods ========================

    def load_profile(self):
        """Load current user's profile"""
        user = self.auth.get_current_user()
        if not user:
            messagebox.showerror(_t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.dialogs.error', default="Error"), _t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.dialogs.user_not_logged_in', default="User not logged in"))
            return

        student_id = user['username']
        profile = self.service.get_profile_by_student(student_id)

        if profile:
            self.current_profile = profile
            self.display_name_var.set(profile['display_name'])
            self.bio_text.delete('1.0', tk.END)
            self.bio_text.insert('1.0', profile['bio'] or '')
            self.budget_min_var.set(str(profile['budget_min']))
            self.budget_max_var.set(str(profile['budget_max']))
            self.move_in_var.set(profile['move_in_date'] or '')
            self.gender_pref_var.set(profile['preferred_gender'])
            self.age_var.set(str(profile['age']) if profile['age'] else '')
            self.major_var.set(profile['major'] or '')
            self.year_var.set(profile['year_of_study'] or '')
            self.smoking_var.set(profile['smoking_preference'])
            self.pet_var.set(profile['pet_preference'])
        else:
            self.current_profile = None

    def save_profile(self):
        """Save or update profile"""
        user = self.auth.get_current_user()
        if not user:
            messagebox.showerror(_t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.dialogs.error', default="Error"), _t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.dialogs.user_not_logged_in', default="User not logged in"))
            return

        student_id = user['username']
        display_name = self.display_name_var.get().strip()

        if not display_name:
            messagebox.showerror(_t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.dialogs.error', default="Error"), _t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.dialogs.display_name_is_required', default="Display name is required"))
            return

        # Validate budget values
        try:
            budget_min = int(self.budget_min_var.get()) if self.budget_min_var.get() else 0
            budget_max = int(self.budget_max_var.get()) if self.budget_max_var.get() else 0

            if budget_min < 0 or budget_max < 0:
                messagebox.showerror(_t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.dialogs.error', default="Error"), _t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.dialogs.budget_values_cannot_be_negative', default="Budget values cannot be negative"))
                return

            if budget_max > 0 and budget_min > budget_max:
                messagebox.showerror(_t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.dialogs.error', default="Error"), _t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.dialogs.minimum_budget_cannot_exceed_maximum_budget', default="Minimum budget cannot exceed maximum budget"))
                return
        except ValueError:
            messagebox.showerror(_t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.dialogs.error', default="Error"), _t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.dialogs.budget_values_must_be_valid_numbers', default="Budget values must be valid numbers"))
            return

        # Validate age
        try:
            age = int(self.age_var.get()) if self.age_var.get() else None
            if age is not None and (age < 16 or age > 100):
                messagebox.showerror(_t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.dialogs.error', default="Error"), _t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.dialogs.age_must_be_between_16_and_100', default="Age must be between 16 and 100"))
                return
        except ValueError:
            messagebox.showerror(_t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.dialogs.error', default="Error"), _t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.dialogs.age_must_be_a_valid_number', default="Age must be a valid number"))
            return

        try:
            bio = self.bio_text.get('1.0', tk.END).strip()

            if self.current_profile:
                # Update existing profile
                self.service.update_profile(
                    self.current_profile['profile_id'],
                    display_name=display_name,
                    bio=bio,
                    budget_min=budget_min,
                    budget_max=budget_max,
                    move_in_date=self.move_in_var.get() or None,
                    preferred_gender=self.gender_pref_var.get(),
                    age=age,
                    major=self.major_var.get(),
                    year_of_study=self.year_var.get(),
                    smoking_preference=self.smoking_var.get(),
                    pet_preference=self.pet_var.get()
                )
                messagebox.showinfo(_t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.dialogs.success', default="Success"), _t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.dialogs.profile_updated_successfully', default="Profile updated successfully!"))
            else:
                # Create new profile
                profile_id = self.service.create_profile(
                    student_id=student_id,
                    display_name=display_name,
                    bio=bio,
                    budget_min=budget_min,
                    budget_max=budget_max,
                    move_in_date=self.move_in_var.get() or None,
                    preferred_gender=self.gender_pref_var.get(),
                    age=age,
                    major=self.major_var.get(),
                    year_of_study=self.year_var.get(),
                    smoking_preference=self.smoking_var.get(),
                    pet_preference=self.pet_var.get()
                )
                messagebox.showinfo(_t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.dialogs.success', default="Success"), f"Profile created successfully! ID: {profile_id}")

            self.load_profile()
        except sqlite3.IntegrityError as e:
            if "UNIQUE constraint failed" in str(e):
                messagebox.showerror(_t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.dialogs.error', default="Error"), _t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.dialogs.a_profile_already_exists_for_this_user', default="A profile already exists for this user"))
            else:
                messagebox.showerror(_t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.dialogs.error', default="Error"), f"Database integrity error: {e}")
        except Exception as e:
            messagebox.showerror(_t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.dialogs.error', default="Error"), f"Failed to save profile: {e}")

    def load_questionnaire(self):
        """Load compatibility questionnaire"""
        if not self.current_profile:
            messagebox.showwarning(_t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.dialogs.warning', default="Warning"), _t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.dialogs.please_create_a_profile_first', default="Please create a profile first"))
            return

        # Clear existing widgets
        for widget in self.questions_frame.winfo_children():
            widget.destroy()
        self.question_widgets.clear()

        questions = self.service.get_questions()
        if not questions:
            messagebox.showinfo(_t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.dialogs.info', default="Info"), _t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.dialogs.no_questionnaire_available', default="No questionnaire available"))
            return

        current_category = None
        row = 0

        for question in questions:
            if question['category'] != current_category:
                current_category = question['category']
                # Category header
                cat_label = ttk.Label(self.questions_frame, text=current_category,
                                     font=('Arial', 12, 'bold'))
                cat_label.grid(row=row, column=0, columnspan=3, sticky=tk.W, pady=(10, 5))
                row += 1

            # Question text
            q_label = ttk.Label(self.questions_frame, text=f"Q{question['question_id']}: {question['question_text']}",
                               wraplength=400)
            q_label.grid(row=row, column=0, sticky=tk.W, pady=5, padx=5)

            # Response widget
            if question['response_type'] == 'scale':
                response_var = tk.StringVar()
                response_widget = ttk.Spinbox(self.questions_frame, from_=1, to=5,
                                             textvariable=response_var, width=10)
            elif question['response_type'] == 'choice':
                response_var = tk.StringVar()
                options = question['options'].split('|')
                response_widget = ttk.Combobox(self.questions_frame, textvariable=response_var,
                                              values=options, state='readonly', width=30)
            else:
                response_var = tk.StringVar()
                response_widget = ttk.Entry(self.questions_frame, textvariable=response_var, width=30)

            response_widget.grid(row=row, column=1, pady=5, padx=5)

            # Importance level
            importance_var = tk.StringVar()
            importance_combo = ttk.Combobox(self.questions_frame, textvariable=importance_var,
                                           values=['Low', 'Medium', 'High', 'Critical'],
                                           state='readonly', width=10)
            importance_combo.grid(row=row, column=2, pady=5, padx=5)
            importance_combo.current(1)  # Default to Medium

            self.question_widgets.append({
                'question_id': question['question_id'],
                'response_var': response_var,
                'importance_var': importance_var
            })

            row += 1

        messagebox.showinfo(_t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.dialogs.success', default="Success"), f"Loaded {len(questions)} questions")

    def submit_questionnaire(self):
        """Submit questionnaire responses"""
        if not self.current_profile:
            messagebox.showwarning(_t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.dialogs.warning', default="Warning"), _t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.dialogs.please_create_a_profile_first', default="Please create a profile first"))
            return

        if not self.question_widgets:
            messagebox.showwarning(_t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.dialogs.warning', default="Warning"), _t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.dialogs.please_load_the_questionnaire_first', default="Please load the questionnaire first"))
            return

        responses = []
        for widget_data in self.question_widgets:
            response_value = widget_data['response_var'].get()
            if not response_value:
                messagebox.showwarning(_t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.dialogs.warning', default="Warning"), _t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.dialogs.please_answer_all_questions', default="Please answer all questions"))
                return

            responses.append({
                'question_id': widget_data['question_id'],
                'response_value': response_value,
                'importance_level': widget_data['importance_var'].get()
            })

        try:
            self.service.submit_questionnaire(self.current_profile['profile_id'], responses)
            messagebox.showinfo(_t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.dialogs.success', default="Success"), _t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.dialogs.questionnaire_submitted_successfully_you_can_now_find_matches', default="Questionnaire submitted successfully!\nYou can now find matches."))
        except Exception as e:
            messagebox.showerror(_t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.dialogs.error', default="Error"), f"Failed to submit questionnaire: {e}")

    def find_matches(self):
        """Find new roommate matches"""
        if not self.current_profile:
            messagebox.showwarning(_t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.dialogs.warning', default="Warning"), _t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.dialogs.please_create_a_profile_first', default="Please create a profile first"))
            return

        # Ask for minimum score
        dialog = tk.Toplevel(self.root)
        dialog.title(_t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.windows.find_matches', default="Find Matches"))
        dialog.geometry("300x150")

        ttk.Label(dialog, text=_t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.labels.minimum_compatibility_score_0_100', default="Minimum Compatibility Score (0-100):")).pack(pady=10)
        score_var = tk.StringVar(value="50")
        ttk.Entry(dialog, textvariable=score_var, width=10).pack(pady=5)

        ttk.Label(dialog, text=_t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.labels.maximum_results', default="Maximum Results:")).pack(pady=5)
        limit_var = tk.StringVar(value="20")
        ttk.Entry(dialog, textvariable=limit_var, width=10).pack(pady=5)

        def search():
            try:
                min_score = float(score_var.get())
                limit = int(limit_var.get())
                matches = self.service.find_matches(self.current_profile['profile_id'], min_score, limit)
                dialog.destroy()
                messagebox.showinfo(_t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.dialogs.success', default="Success"), f"Found {len(matches)} matches!")
                self.load_matches()
            except Exception as e:
                messagebox.showerror(_t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.dialogs.error', default="Error"), f"Failed to find matches: {e}")

        ttk.Button(dialog, text=_t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.buttons.search', default="Search"), command=search).pack(pady=10)

    def load_matches(self):
        """Load all matches"""
        if not self.current_profile:
            return

        self.matches_tree.delete(*self.matches_tree.get_children())

        try:
            matches = self.service.get_matches(self.current_profile['profile_id'])

            for match in matches:
                # Parse match_reasons if it's a JSON string
                import json
                try:
                    reasons = json.loads(match['match_reasons']) if isinstance(match['match_reasons'], str) else match['match_reasons']
                except (ValueError, json.JSONDecodeError):
                    reasons = []

                # Determine which profile is the match
                other_profile_id = match['profile_id_2'] if match['profile_id_1'] == self.current_profile['profile_id'] else match['profile_id_1']
                other_profile = self.service.get_profile(other_profile_id)

                if other_profile:
                    budget = f"£{other_profile['budget_min']}-£{other_profile['budget_max']}"
                    self.matches_tree.insert('', tk.END, values=(
                        match['match_id'],
                        match['display_name'],
                        f"{match['compatibility_score']:.1f}%",
                        match['major'] or 'N/A',
                        match['year_of_study'] or 'N/A',
                        budget,
                        match['status']
                    ), tags=(str(match['match_id']),))

            self.refresh_message_matches()
        except Exception as e:
            messagebox.showerror(_t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.dialogs.error', default="Error"), f"Failed to load matches: {e}")

    def on_match_selected(self, event):
        """Handle match selection"""
        selected = self.matches_tree.selection()
        if not selected:
            return

        match_id = int(self.matches_tree.item(selected[0])['values'][0])

        try:
            matches = self.service.get_matches(self.current_profile['profile_id'])
            match = next((m for m in matches if m['match_id'] == match_id), None)

            if match:
                # Get full profile
                other_profile_id = match['profile_id_2'] if match['profile_id_1'] == self.current_profile['profile_id'] else match['profile_id_1']
                other_profile = self.service.get_profile(other_profile_id)

                # Parse reasons
                import json
                try:
                    reasons = json.loads(match['match_reasons']) if isinstance(match['match_reasons'], str) else match['match_reasons']
                except (ValueError, json.JSONDecodeError):
                    reasons = []

                # Display details
                self.match_details_text.config(state=tk.NORMAL)
                self.match_details_text.delete('1.0', tk.END)

                details = f"Match ID: {match_id}\n"
                details += f"Compatibility Score: {match['compatibility_score']:.1f}%\n"
                details += f"Status: {match['status']}\n\n"

                if other_profile:
                    details += f"Name: {other_profile['display_name']}\n"
                    details += f"Bio: {other_profile['bio'] or 'Not provided'}\n"
                    details += f"Major: {other_profile['major'] or 'Not specified'}\n"
                    details += f"Year: {other_profile['year_of_study'] or 'Not specified'}\n"
                    details += f"Budget: £{other_profile['budget_min']}-£{other_profile['budget_max']}/month\n"
                    details += f"Move-in: {other_profile['move_in_date'] or 'Flexible'}\n"
                    details += f"Gender Preference: {other_profile['preferred_gender']}\n"
                    details += f"Smoking: {other_profile['smoking_preference']}\n"
                    details += f"Pets: {other_profile['pet_preference']}\n\n"

                details += "Match Reasons:\n"
                for reason in reasons:
                    details += f"  - {reason}\n"

                self.match_details_text.insert('1.0', details)
                self.match_details_text.config(state=tk.DISABLED)
        except Exception as e:
            messagebox.showerror(_t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.dialogs.error', default="Error"), f"Failed to load match details: {e}")

    def update_match_status(self, status: str):
        """Update match status"""
        selected = self.matches_tree.selection()
        if not selected:
            messagebox.showwarning(_t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.dialogs.warning', default="Warning"), _t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.dialogs.please_select_a_match_first', default="Please select a match first"))
            return

        match_id = int(self.matches_tree.item(selected[0])['values'][0])

        try:
            self.service.update_match_status(match_id, status)
            messagebox.showinfo(_t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.dialogs.success', default="Success"), f"Match status updated to: {status}")
            self.load_matches()
        except Exception as e:
            messagebox.showerror(_t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.dialogs.error', default="Error"), f"Failed to update status: {e}")

    def open_message_dialog(self):
        """Open message dialog for selected match"""
        selected = self.matches_tree.selection()
        if not selected:
            messagebox.showwarning(_t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.dialogs.warning', default="Warning"), _t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.dialogs.please_select_a_match_first', default="Please select a match first"))
            return

        match_id = int(self.matches_tree.item(selected[0])['values'][0])

        dialog = tk.Toplevel(self.root)
        dialog.title(f"Send Message - Match #{match_id}")
        dialog.geometry("400x300")

        ttk.Label(dialog, text=_t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.labels.your_message', default="Your Message:")).pack(pady=10)
        message_text = tk.Text(dialog, height=10, wrap=tk.WORD)
        message_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        def send():
            text = message_text.get('1.0', tk.END).strip()
            if not text:
                messagebox.showwarning(_t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.dialogs.warning', default="Warning"), _t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.dialogs.message_cannot_be_empty', default="Message cannot be empty"))
                return

            try:
                self.service.send_message(match_id, self.current_profile['profile_id'], text)
                messagebox.showinfo(_t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.dialogs.success', default="Success"), _t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.dialogs.message_sent', default="Message sent!"))
                dialog.destroy()
            except Exception as e:
                messagebox.showerror(_t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.dialogs.error', default="Error"), f"Failed to send message: {e}")

        ttk.Button(dialog, text=_t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.buttons.send', default="Send"), command=send).pack(pady=10)

    def refresh_message_matches(self):
        """Refresh message match combo box"""
        if not self.current_profile:
            return

        matches = self.service.get_matches(self.current_profile['profile_id'])
        match_list = [f"{m['match_id']}: {m['display_name']}" for m in matches]
        self.message_match_combo['values'] = match_list

    def load_messages(self, event=None):
        """Load messages for selected match"""
        if not self.current_profile:
            return

        selected = self.message_match_combo.get()
        if not selected:
            return

        try:
            match_id = int(selected.split(':')[0])
            messages = self.service.get_messages(match_id, self.current_profile['profile_id'])

            self.messages_text.config(state=tk.NORMAL)
            self.messages_text.delete('1.0', tk.END)

            if not messages:
                self.messages_text.insert('1.0', "No messages in this conversation yet.")
            else:
                for msg in messages:
                    sender = "You" if msg['direction'] == 'sent' else "Them"
                    timestamp = msg['sent_at']
                    read = "[Read]" if msg['is_read'] else "[Unread]"

                    self.messages_text.insert(tk.END, f"{sender} - {timestamp} {read if msg['direction'] == 'sent' else ''}\n", 'header')
                    self.messages_text.insert(tk.END, f"{msg['message_text']}\n\n", 'message')
                    self.messages_text.insert(tk.END, "-" * 60 + "\n\n")

                # Mark as read
                self.service.mark_messages_read(match_id, self.current_profile['profile_id'])

            self.messages_text.config(state=tk.DISABLED)
        except Exception as e:
            messagebox.showerror(_t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.dialogs.error', default="Error"), f"Failed to load messages: {e}")

    def send_message(self):
        """Send a message"""
        if not self.current_profile:
            messagebox.showwarning(_t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.dialogs.warning', default="Warning"), _t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.dialogs.please_create_a_profile_first', default="Please create a profile first"))
            return

        selected = self.message_match_combo.get()
        if not selected:
            messagebox.showwarning(_t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.dialogs.warning', default="Warning"), _t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.dialogs.please_select_a_match_first', default="Please select a match first"))
            return

        message_text = self.message_input.get('1.0', tk.END).strip()
        if not message_text:
            messagebox.showwarning(_t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.dialogs.warning', default="Warning"), _t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.dialogs.message_cannot_be_empty', default="Message cannot be empty"))
            return

        try:
            match_id = int(selected.split(':')[0])
            self.service.send_message(match_id, self.current_profile['profile_id'], message_text)
            messagebox.showinfo(_t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.dialogs.success', default="Success"), _t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.dialogs.message_sent', default="Message sent!"))
            self.message_input.delete('1.0', tk.END)
            self.load_messages()
        except Exception as e:
            messagebox.showerror(_t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.dialogs.error', default="Error"), f"Failed to send message: {e}")

    def load_statistics(self):
        """Load profile statistics"""
        if not self.current_profile:
            messagebox.showwarning(_t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.dialogs.warning', default="Warning"), _t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.dialogs.please_create_a_profile_first', default="Please create a profile first"))
            return

        try:
            stats = self.service.get_profile_stats(self.current_profile['profile_id'])
            unread = self.service.get_unread_count(self.current_profile['profile_id'])

            self.stats_text.delete('1.0', tk.END)

            text = "ROOMMATE FINDER STATISTICS\n"
            text += "=" * 60 + "\n\n"

            match_stats = stats.get('matches', {})
            message_stats = stats.get('messages', {})

            text += "Matching Statistics:\n"
            text += f"  Total Matches: {match_stats.get('total_matches', 0)}\n"
            text += f"  Average Compatibility: {match_stats.get('avg_score', 0):.1f}%\n"
            text += f"  Highest Compatibility: {match_stats.get('max_score', 0):.1f}%\n\n"

            text += "Messaging Statistics:\n"
            text += f"  Total Messages: {message_stats.get('total_messages', 0)}\n"
            text += f"  Messages Sent: {message_stats.get('sent_count', 0)}\n"
            text += f"  Messages Received: {message_stats.get('received_count', 0)}\n"
            text += f"  Unread Messages: {unread}\n\n"

            text += "Profile Information:\n"
            text += f"  Display Name: {self.current_profile['display_name']}\n"
            text += f"  Profile Created: {self.current_profile['created_at']}\n"
            text += f"  Last Updated: {self.current_profile['updated_at']}\n"
            text += f"  Status: {'Active' if self.current_profile['is_active'] else 'Inactive'}\n"

            self.stats_text.insert('1.0', text)
        except Exception as e:
            messagebox.showerror(_t('gui.operations.campus.housing.housing_accommodation_gui.roommate_finder.dialogs.error', default="Error"), f"Failed to load statistics: {e}")

def main():
    """Main entry point for GUI"""
    root = tk.Tk()
    root.withdraw()  # Hide main window
    app = RoommateFinderGUI(root)
    root.mainloop()

if __name__ == '__main__':
    main()
