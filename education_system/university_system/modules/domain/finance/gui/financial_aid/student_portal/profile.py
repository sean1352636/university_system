"""
Profile mixin - student scholarship profile management.
"""

from ..common_imports import (
    tk,
    ttk,
    logging,
    clear_frame,
    show_error,
    show_success,
)
from education_system.university_system.modules.shared.utils.i18n import get_text

logger = logging.getLogger(__name__)


class ProfileMixin:
    """Student profile management functionality"""

    def show_profile(self):
        """Display student profile management"""
        clear_frame(self.parent_frame)

        # Title
        title_frame = ttk.Frame(self.parent_frame)
        title_frame.pack(fill='x', padx=10, pady=10)
        ttk.Label(title_frame, text=get_text("financial_aid.student_portal.profile.title", "Scholarship Profile"), style='Title.TLabel').pack(side='left')
        ttk.Button(title_frame, text=get_text("financial_aid.student_portal.buttons.back_to_dashboard", "Back to Dashboard"), command=self.show_dashboard).pack(side='right')

        # Profile completeness
        try:
            from education_system.university_system.modules.domain.scholarship_finder.services.scholarship_service import StudentProfileManager

            profile = StudentProfileManager.get_student_profile(self.student_id) or {}
            completeness = profile.get('profile_completeness', 0)

            completeness_frame = ttk.Frame(self.parent_frame)
            completeness_frame.pack(pady=10)

            ttk.Label(completeness_frame, text=get_text("financial_aid.student_portal.profile.completeness", "Profile Completeness: {percent}%", percent=f"{completeness:.1f}"),
                     font=('Arial', 12, 'bold')).pack()

            progress_bar = ttk.Progressbar(completeness_frame, length=400, mode='determinate')
            progress_bar['value'] = completeness
            progress_bar.pack(pady=5)

        except Exception as e:
            logger.error(f"Error loading profile: {e}")
            profile = {}
            ttk.Label(self.parent_frame, text=get_text("financial_aid.student_portal.profile.not_created", "Profile not created yet"), font=('Arial', 12)).pack(pady=10)

        # Profile notebook
        profile_notebook = ttk.Notebook(self.parent_frame)
        profile_notebook.pack(fill='both', expand=True, padx=10, pady=10)

        # Create profile tabs
        self._create_basic_info_tab(profile_notebook, profile)
        self._create_academic_info_tab(profile_notebook, profile)
        self._create_activities_tab(profile_notebook, profile)
        self._create_preferences_tab(profile_notebook, profile)

    def _create_basic_info_tab(self, parent, profile):
        """Create basic information tab"""
        tab = ttk.Frame(parent, padding=20)
        parent.add(tab, text=get_text("financial_aid.student_portal.profile.tabs.basic_info", "Basic Info"))

        form_frame = ttk.Frame(tab)
        form_frame.pack(fill='both', expand=True)

        # Citizenship
        ttk.Label(form_frame, text=get_text("financial_aid.student_portal.profile.basic.citizenship", "Citizenship Status:")).grid(row=0, column=0, sticky='w', pady=5)
        self.citizenship_var = tk.StringVar(value=profile.get('citizenship_status', ''))
        ttk.Entry(form_frame, textvariable=self.citizenship_var, width=30).grid(row=0, column=1, pady=5)

        # State residency
        ttk.Label(form_frame, text=get_text("financial_aid.student_portal.profile.basic.residency", "State Residency:")).grid(row=1, column=0, sticky='w', pady=5)
        self.state_var = tk.StringVar(value=profile.get('state_residency', ''))
        ttk.Entry(form_frame, textvariable=self.state_var, width=30).grid(row=1, column=1, pady=5)

        # Ethnicity
        ttk.Label(form_frame, text=get_text("financial_aid.student_portal.profile.basic.ethnicity", "Ethnicity:")).grid(row=2, column=0, sticky='w', pady=5)
        self.ethnicity_var = tk.StringVar(value=profile.get('ethnicity', ''))
        ttk.Entry(form_frame, textvariable=self.ethnicity_var, width=30).grid(row=2, column=1, pady=5)

        # Gender
        ttk.Label(form_frame, text=get_text("financial_aid.student_portal.profile.basic.gender", "Gender:")).grid(row=3, column=0, sticky='w', pady=5)
        self.gender_var = tk.StringVar(value=profile.get('gender', ''))
        ttk.Entry(form_frame, textvariable=self.gender_var, width=30).grid(row=3, column=1, pady=5)

        # First generation
        self.first_gen_var = tk.BooleanVar(value=bool(profile.get('first_generation', 0)))
        ttk.Checkbutton(form_frame, text=get_text("financial_aid.student_portal.profile.basic.first_gen", "First Generation College Student"),
                       variable=self.first_gen_var).grid(row=4, column=0, columnspan=2, sticky='w', pady=5)

        # Military affiliation
        ttk.Label(form_frame, text=get_text("financial_aid.student_portal.profile.basic.military", "Military Affiliation:")).grid(row=5, column=0, sticky='w', pady=5)
        self.military_var = tk.StringVar(value=profile.get('military_affiliation', ''))
        ttk.Entry(form_frame, textvariable=self.military_var, width=30).grid(row=5, column=1, pady=5)

        # Save button
        ttk.Button(form_frame, text=get_text("financial_aid.student_portal.buttons.save_basic_info", "Save Basic Info"),
                  command=self._save_basic_info, style='Success.TButton').grid(row=6, column=0, columnspan=2, pady=20)

    def _create_academic_info_tab(self, parent, profile):
        """Create academic information tab"""
        tab = ttk.Frame(parent, padding=20)
        parent.add(tab, text=get_text("financial_aid.student_portal.profile.tabs.academic_career", "Academic & Career"))

        form_frame = ttk.Frame(tab)
        form_frame.pack(fill='both', expand=True)

        # Financial need
        ttk.Label(form_frame, text=get_text("financial_aid.student_portal.profile.academic.financial_need", "Financial Need Level:")).grid(row=0, column=0, sticky='w', pady=5)
        self.financial_need_var = tk.StringVar(value=profile.get('financial_need_level', 'none'))
        needs = ['none', 'low', 'moderate', 'high', 'exceptional']
        ttk.Combobox(form_frame, textvariable=self.financial_need_var, values=needs,
                    state='readonly', width=28).grid(row=0, column=1, pady=5)

        # Career field
        ttk.Label(form_frame, text=get_text("financial_aid.student_portal.profile.academic.career_field", "Intended Career Field:")).grid(row=1, column=0, sticky='w', pady=5)
        self.career_var = tk.StringVar(value=profile.get('intended_career_field', ''))
        ttk.Entry(form_frame, textvariable=self.career_var, width=30).grid(row=1, column=1, pady=5)

        # Save button
        ttk.Button(form_frame, text=get_text("financial_aid.student_portal.buttons.save_academic_info", "Save Academic Info"),
                  command=self._save_academic_info, style='Success.TButton').grid(row=2, column=0, columnspan=2, pady=20)

    def _create_activities_tab(self, parent, profile):
        """Create activities and achievements tab"""
        tab = ttk.Frame(parent, padding=20)
        parent.add(tab, text=get_text("financial_aid.student_portal.profile.tabs.activities", "Activities"))

        form_frame = ttk.Frame(tab)
        form_frame.pack(fill='both', expand=True)

        # Community service hours
        ttk.Label(form_frame, text=get_text("financial_aid.student_portal.profile.activities_form.community_service", "Community Service Hours:")).grid(row=0, column=0, sticky='w', pady=5)
        self.service_hours_var = tk.StringVar(value=str(profile.get('community_service_hours', 0)))
        ttk.Entry(form_frame, textvariable=self.service_hours_var, width=30).grid(row=0, column=1, pady=5)

        # Leadership positions
        ttk.Label(form_frame, text=get_text("financial_aid.student_portal.profile.activities_form.leadership", "Leadership Positions:")).grid(row=1, column=0, sticky='w', pady=5)
        self.leadership_var = tk.StringVar(value=profile.get('leadership_positions', ''))
        ttk.Entry(form_frame, textvariable=self.leadership_var, width=30).grid(row=1, column=1, pady=5)

        # Academic honors
        ttk.Label(form_frame, text=get_text("financial_aid.student_portal.profile.activities_form.honors", "Academic Honors:")).grid(row=2, column=0, sticky='w', pady=5)
        self.honors_var = tk.StringVar(value=profile.get('academic_honors', ''))
        ttk.Entry(form_frame, textvariable=self.honors_var, width=30).grid(row=2, column=1, pady=5)

        # Extracurriculars
        ttk.Label(form_frame, text=get_text("financial_aid.student_portal.profile.activities_form.extracurricular", "Extracurricular Activities:")).grid(row=3, column=0, sticky='w', pady=5)
        self.activities_var = tk.StringVar(value=profile.get('extracurricular_activities', ''))
        ttk.Entry(form_frame, textvariable=self.activities_var, width=30).grid(row=3, column=1, pady=5)

        # Special talents
        ttk.Label(form_frame, text=get_text("financial_aid.student_portal.profile.activities_form.talents", "Special Talents:")).grid(row=4, column=0, sticky='w', pady=5)
        self.talents_var = tk.StringVar(value=profile.get('special_talents', ''))
        ttk.Entry(form_frame, textvariable=self.talents_var, width=30).grid(row=4, column=1, pady=5)

        # Languages
        ttk.Label(form_frame, text=get_text("financial_aid.student_portal.profile.activities_form.languages", "Languages Spoken:")).grid(row=5, column=0, sticky='w', pady=5)
        self.languages_var = tk.StringVar(value=profile.get('languages_spoken', ''))
        ttk.Entry(form_frame, textvariable=self.languages_var, width=30).grid(row=5, column=1, pady=5)

        # Study abroad interest
        self.study_abroad_var = tk.BooleanVar(value=bool(profile.get('study_abroad_interest', 0)))
        ttk.Checkbutton(form_frame, text=get_text("financial_aid.student_portal.profile.activities_form.study_abroad", "Interested in Study Abroad"),
                       variable=self.study_abroad_var).grid(row=6, column=0, columnspan=2, sticky='w', pady=5)

        # Research interest
        self.research_var = tk.BooleanVar(value=bool(profile.get('research_interest', 0)))
        ttk.Checkbutton(form_frame, text=get_text("financial_aid.student_portal.profile.activities_form.research", "Interested in Research"),
                       variable=self.research_var).grid(row=7, column=0, columnspan=2, sticky='w', pady=5)

        # Save button
        ttk.Button(form_frame, text=get_text("financial_aid.student_portal.buttons.save_activities", "Save Activities"),
                  command=self._save_activities, style='Success.TButton').grid(row=8, column=0, columnspan=2, pady=20)

    def _create_preferences_tab(self, parent, profile):
        """Create preferences tab"""
        tab = ttk.Frame(parent, padding=20)
        parent.add(tab, text=get_text("financial_aid.student_portal.profile.tabs.preferences", "Preferences"))

        form_frame = ttk.Frame(tab)
        form_frame.pack(fill='both', expand=True)

        # Preferred scholarship types
        ttk.Label(form_frame, text=get_text("financial_aid.student_portal.profile.preferences_form.preferred_types", "Preferred Scholarship Types:")).grid(row=0, column=0, sticky='w', pady=5)
        self.pref_types_var = tk.StringVar(value=profile.get('preferred_scholarship_types', ''))
        ttk.Entry(form_frame, textvariable=self.pref_types_var, width=30).grid(row=0, column=1, pady=5)

        # Minimum award amount
        ttk.Label(form_frame, text=get_text("financial_aid.student_portal.profile.preferences_form.min_amount", "Minimum Award Amount ($):")).grid(row=1, column=0, sticky='w', pady=5)
        self.min_award_pref_var = tk.StringVar(value=str(profile.get('minimum_award_amount', 0)))
        ttk.Entry(form_frame, textvariable=self.min_award_pref_var, width=30).grid(row=1, column=1, pady=5)

        # Willing to write essays
        self.essays_var = tk.BooleanVar(value=bool(profile.get('willing_to_write_essays', 1)))
        ttk.Checkbutton(form_frame, text=get_text("financial_aid.student_portal.profile.preferences_form.willing_essays", "Willing to Write Essays"),
                       variable=self.essays_var).grid(row=2, column=0, columnspan=2, sticky='w', pady=5)

        # Max recommendation letters
        ttk.Label(form_frame, text=get_text("financial_aid.student_portal.profile.preferences_form.max_letters", "Max Recommendation Letters:")).grid(row=3, column=0, sticky='w', pady=5)
        self.max_letters_var = tk.StringVar(value=str(profile.get('max_recommendation_letters', 3)))
        ttk.Entry(form_frame, textvariable=self.max_letters_var, width=30).grid(row=3, column=1, pady=5)

        # Save button
        ttk.Button(form_frame, text=get_text("financial_aid.student_portal.buttons.save_preferences", "Save Preferences"),
                  command=self._save_preferences, style='Success.TButton').grid(row=4, column=0, columnspan=2, pady=20)

    def _save_basic_info(self):
        """Save basic information"""
        try:
            from education_system.university_system.modules.domain.scholarship_finder.services.scholarship_service import StudentProfileManager

            profile_data = {
                'citizenship_status': self.citizenship_var.get().strip(),
                'state_residency': self.state_var.get().strip(),
                'ethnicity': self.ethnicity_var.get().strip(),
                'gender': self.gender_var.get().strip(),
                'first_generation': 1 if self.first_gen_var.get() else 0,
                'military_affiliation': self.military_var.get().strip()
            }

            StudentProfileManager.create_or_update_profile(self.student_id, **profile_data)
            show_success(get_text("financial_aid.student_portal.success.title", "Success"), get_text("financial_aid.student_portal.success.basic_info_saved", "Basic information saved!"))

        except Exception as e:
            logger.error(f"Error saving profile: {e}")
            show_error(get_text("financial_aid.student_portal.errors.title", "Error"), get_text("financial_aid.student_portal.errors.failed_save_profile", "Failed to save profile: {error}", error=str(e)))

    def _save_academic_info(self):
        """Save academic information"""
        try:
            from education_system.university_system.modules.domain.scholarship_finder.services.scholarship_service import StudentProfileManager

            profile_data = {
                'financial_need_level': self.financial_need_var.get(),
                'intended_career_field': self.career_var.get().strip()
            }

            StudentProfileManager.create_or_update_profile(self.student_id, **profile_data)
            show_success(get_text("financial_aid.student_portal.success.title", "Success"), get_text("financial_aid.student_portal.success.academic_info_saved", "Academic information saved!"))

        except Exception as e:
            logger.error(f"Error saving profile: {e}")
            show_error(get_text("financial_aid.student_portal.errors.title", "Error"), get_text("financial_aid.student_portal.errors.failed_save_profile", "Failed to save profile: {error}", error=str(e)))

    def _save_activities(self):
        """Save activities information"""
        try:
            from education_system.university_system.modules.domain.scholarship_finder.services.scholarship_service import StudentProfileManager

            service_hours = int(self.service_hours_var.get().strip()) if self.service_hours_var.get().strip() else 0

            profile_data = {
                'community_service_hours': service_hours,
                'leadership_positions': self.leadership_var.get().strip(),
                'academic_honors': self.honors_var.get().strip(),
                'extracurricular_activities': self.activities_var.get().strip(),
                'special_talents': self.talents_var.get().strip(),
                'languages_spoken': self.languages_var.get().strip(),
                'study_abroad_interest': 1 if self.study_abroad_var.get() else 0,
                'research_interest': 1 if self.research_var.get() else 0
            }

            StudentProfileManager.create_or_update_profile(self.student_id, **profile_data)
            show_success(get_text("financial_aid.student_portal.success.title", "Success"), get_text("financial_aid.student_portal.success.activities_saved", "Activities saved!"))

        except Exception as e:
            logger.error(f"Error saving profile: {e}")
            show_error(get_text("financial_aid.student_portal.errors.title", "Error"), get_text("financial_aid.student_portal.errors.failed_save_profile", "Failed to save profile: {error}", error=str(e)))

    def _save_preferences(self):
        """Save preferences"""
        try:
            from education_system.university_system.modules.domain.scholarship_finder.services.scholarship_service import StudentProfileManager

            min_amount = float(self.min_award_pref_var.get().strip()) if self.min_award_pref_var.get().strip() else 0
            max_letters = int(self.max_letters_var.get().strip()) if self.max_letters_var.get().strip() else 3

            profile_data = {
                'preferred_scholarship_types': self.pref_types_var.get().strip(),
                'minimum_award_amount': min_amount,
                'willing_to_write_essays': 1 if self.essays_var.get() else 0,
                'max_recommendation_letters': max_letters
            }

            StudentProfileManager.create_or_update_profile(self.student_id, **profile_data)
            show_success(get_text("financial_aid.student_portal.success.title", "Success"), get_text("financial_aid.student_portal.success.preferences_saved", "Preferences saved!"))

        except Exception as e:
            logger.error(f"Error saving profile: {e}")
            show_error(get_text("financial_aid.student_portal.errors.title", "Error"), get_text("financial_aid.student_portal.errors.failed_save_profile", "Failed to save profile: {error}", error=str(e)))
